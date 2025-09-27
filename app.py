# app.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import numpy_financial as npf
import numpy as np

# --- CONFIGURATION DE LA PAGE STREAMLIT ---
st.set_page_config(
    page_title="Simulateur LMNP au Réel",
    page_icon="🛋️",
    layout="wide"
)

# --- MOTEUR DE CALCUL DU PRÊT ---
def generer_tableau_amortissement(montant_pret, taux_annuel_pc, duree_annees):
    if not (montant_pret > 0 and taux_annuel_pc > 0 and duree_annees > 0): return {}
    taux_mensuel = (taux_annuel_pc / 100) / 12
    nb_mois = int(duree_annees * 12)
    try: mensualite = npf.pmt(taux_mensuel, nb_mois, -montant_pret)
    except ZeroDivisionError: return {}
    tableau_annuel = defaultdict(lambda: {'interet': 0, 'principal': 0, 'crd_fin_annee': 0})
    capital_restant_du = montant_pret
    for mois in range(1, nb_mois + 1):
        annee = (mois - 1) // 12 + 1
        interet_mois = capital_restant_du * taux_mensuel
        principal_mois = mensualite - interet_mois
        capital_restant_du -= principal_mois
        tableau_annuel[annee]['interet'] += interet_mois; tableau_annuel[annee]['principal'] += principal_mois
        tableau_annuel[annee]['crd_fin_annee'] = capital_restant_du if capital_restant_du > 0.01 else 0
    return dict(tableau_annuel)

# --- MOTEUR DE CALCUL IMPÔT PLUS-VALUE ---
def calculer_impot_plus_value(plus_value_brute, duree_detention):
    if plus_value_brute <= 0: return 0, 0
    abattement_ir = 0
    if duree_detention > 5:
        abattement_ir += sum(0.06 for _ in range(6, min(duree_detention, 21) + 1))
        if duree_detention >= 22: abattement_ir += 0.04
    base_imposable_ir = plus_value_brute * (1 - abattement_ir)
    impot_sur_revenu_pv = base_imposable_ir * 0.19
    abattement_ps = 0
    if duree_detention > 5:
        abattement_ps += sum(0.0165 for _ in range(6, min(duree_detention, 21) + 1))
        if duree_detention == 22: abattement_ps += 0.0160
        if duree_detention > 22: abattement_ps += sum(0.09 for _ in range(23, min(duree_detention, 30) + 1))
    base_imposable_ps = plus_value_brute * (1 - abattement_ps)
    prelevements_sociaux_pv = base_imposable_ps * 0.172
    impot_total_pv = max(0, impot_sur_revenu_pv) + max(0, prelevements_sociaux_pv)
    return impot_total_pv, plus_value_brute

# --- MOTEUR DE SIMULATION LMNP ---
def generer_projection_lmnp(params):
    try: valeurs_num = {k: float(v) for k, v in params.items()}
    except (ValueError, TypeError): return [{"erreur": "Veuillez entrer des nombres valides."}]

    prix_achat, cout_travaux, frais_notaire = valeurs_num.get("prix_achat", 0), valeurs_num.get("cout_travaux", 0), valeurs_num.get("frais_notaire", 0)
    apport, frais_dossier = valeurs_num.get("apport_personnel", 0), valeurs_num.get("frais_dossier", 0)
    montant_pret = prix_achat + cout_travaux + frais_notaire - apport
    cout_acquisition = prix_achat + cout_travaux
    base_acquisition_pv = prix_achat + cout_travaux + frais_notaire
    investissement_initial_personnel = apport + frais_notaire + frais_dossier
    duree_pret = int(valeurs_num.get("duree_pret", 0))

    tableau_amortissement_pret = generer_tableau_amortissement(montant_pret, valeurs_num.get("taux_interet_pret", 0), duree_pret)
    mensualite_assurance_base = (montant_pret * (valeurs_num.get("taux_assurance_pret", 0) / 100)) / 12

    loyer_mensuel_base, charges_copro_base, taxe_fonciere_base = valeurs_num.get("loyer_mensuel", 0), valeurs_num.get("charges_copro", 0), valeurs_num.get("taxe_fonciere", 0)
    inflation_pc, revalo_bien_pc = valeurs_num.get("inflation_pc", 0) / 100, valeurs_num.get("revalo_bien_pc", 0) / 100
    tmi_pc, prelevements_sociaux_pc = valeurs_num.get("tmi_pc", 0) / 100, 17.2 / 100
    
    cashflow_net_cumule, amortissement_cumule, deficit_reportable = 0, 0, 0
    flux_tresorerie_tri_annuels = []
    projection = []

    for annee in range(1, duree_pret + 1):
        facteur_inflation = (1 + inflation_pc)**(annee - 1)
        loyer_annuel = (loyer_mensuel_base * 12) * facteur_inflation
        charges_copro_annuelles = (charges_copro_base * 12) * facteur_inflation
        taxe_fonciere_actuelle = taxe_fonciere_base * facteur_inflation
        frais_gestion_annuels = loyer_annuel * (valeurs_num.get("frais_gestion_pc", 0) / 100)
        gli_annuelle = (loyer_annuel + charges_copro_annuelles) * (valeurs_num.get("taux_gli_pc", 0) / 100)
        
        charges_annuelles_deductibles = (charges_copro_annuelles + taxe_fonciere_actuelle +
            valeurs_num.get("assurance_pno", 0) + frais_gestion_annuels + gli_annuelle +
            (valeurs_num.get("cfe", 0) * facteur_inflation) + (frais_dossier if annee == 1 else 0) +
            tableau_amortissement_pret.get(annee, {}).get('interet', 0) + (mensualite_assurance_base * 12))
        
        amort_immo = (prix_achat + frais_notaire) * 0.85 / valeurs_num.get("duree_amort_immo", 1) if annee <= valeurs_num.get("duree_amort_immo", 0) else 0
        amort_travaux = cout_travaux / 10 if annee <= 10 else 0
        amort_meubles = valeurs_num.get("valeur_meubles", 0) / valeurs_num.get("duree_amort_meubles", 1) if annee <= valeurs_num.get("duree_amort_meubles", 0) else 0
        amortissement_annuel = amort_immo + amort_travaux + amort_meubles
        amortissement_cumule += amortissement_annuel

        resultat_fiscal_avant_deficit = loyer_annuel - charges_annuelles_deductibles - amortissement_annuel
        benefice_imposable = max(0, resultat_fiscal_avant_deficit - deficit_reportable)
        deficit_genere = abs(min(0, resultat_fiscal_avant_deficit)); deficit_consomme = min(deficit_reportable, max(0, resultat_fiscal_avant_deficit))
        deficit_reportable = (deficit_reportable - deficit_consomme) + deficit_genere
        impot_total_annuel = benefice_imposable * (tmi_pc + prelevements_sociaux_pc)
        
        principal_annuel = tableau_amortissement_pret.get(annee, {}).get('principal', 0)
        depenses_cash_totales = charges_annuelles_deductibles + principal_annuel
        cashflow_net_annuel = loyer_annuel - depenses_cash_totales - impot_total_annuel
        cashflow_net_cumule += cashflow_net_annuel
        flux_tresorerie_tri_annuels.append(cashflow_net_annuel)

        prix_revente = cout_acquisition * (1 + revalo_bien_pc)**annee
        valeur_nette_comptable = base_acquisition_pv - amortissement_cumule
        plus_value_imposable = prix_revente - valeur_nette_comptable
        impot_sur_pv, pv_brute_calculee = calculer_impot_plus_value(plus_value_imposable, annee)
        crd = tableau_amortissement_pret.get(annee, {}).get('crd_fin_annee', 0)
        cash_net_apres_revente = prix_revente - crd - impot_sur_pv
        
        benefice_net_total = cash_net_apres_revente + cashflow_net_cumule - investissement_initial_personnel
        
        cash_flows_annuel = [-investissement_initial_personnel] + flux_tresorerie_tri_annuels[:]
        cash_flows_annuel[-1] += cash_net_apres_revente
        try: tri = npf.irr(cash_flows_annuel); tri_pc = tri * 100 if not np.isnan(tri) else 0
        except: tri_pc = 0

        projection.append({ "Année": annee, "Loyers Annuels": loyer_annuel, "Résultat Fiscal": resultat_fiscal_avant_deficit, "Impôt (IR+PS)": impot_total_annuel, "Cash-flow Net": cashflow_net_annuel, "PV Imposable": pv_brute_calculee, "Impôt sur PV": impot_sur_pv, "Bénéfice Net Total": benefice_net_total, "TRI (%)": tri_pc })

    if duree_pret > 0 and len(projection) > 0:
        annee_post_credit = duree_pret + 1; facteur_inflation = (1 + inflation_pc)**(annee_post_credit - 1)
        loyer_annuel = (loyer_mensuel_base * 12) * facteur_inflation; charges_copro_annuelles = (charges_copro_base * 12) * facteur_inflation
        taxe_fonciere_actuelle = taxe_fonciere_base * facteur_inflation
        frais_gestion_annuels = loyer_annuel * (valeurs_num.get("frais_gestion_pc", 0) / 100); gli_annuelle = (loyer_annuel + charges_copro_annuelles) * (valeurs_num.get("taux_gli_pc", 0) / 100)
        charges_annuelles_deductibles = (charges_copro_annuelles + taxe_fonciere_actuelle + valeurs_num.get("assurance_pno", 0) + frais_gestion_annuels + gli_annuelle + (valeurs_num.get("cfe", 0) * facteur_inflation))
        amort_immo = (prix_achat + frais_notaire) * 0.85 / valeurs_num.get("duree_amort_immo", 1) if annee_post_credit <= valeurs_num.get("duree_amort_immo", 0) else 0
        amort_travaux = cout_travaux / 10 if annee_post_credit <= 10 else 0
        amort_meubles = valeurs_num.get("valeur_meubles", 0) / valeurs_num.get("duree_amort_meubles", 1) if annee_post_credit <= valeurs_num.get("duree_amort_meubles", 0) else 0
        amortissement_annuel = amort_immo + amort_travaux + amort_meubles
        resultat_fiscal = loyer_annuel - charges_annuelles_deductibles - amortissement_annuel
        benefice_imposable = max(0, resultat_fiscal - deficit_reportable); impot_total_annuel = benefice_imposable * (tmi_pc + prelevements_sociaux_pc)
        cashflow_net_annuel = loyer_annuel - charges_annuelles_deductibles - impot_total_annuel
        
        projection.append({key: "━━━━━━━━━━━━" for key in projection[0].keys()})
        projection.append({"Année": f"An {annee_post_credit} (Post-Crédit)", "Loyers Annuels": loyer_annuel, "Résultat Fiscal": resultat_fiscal, "Impôt (IR+PS)": impot_total_annuel, "Cash-flow Net": cashflow_net_annuel, "PV Imposable": "N/A", "Impôt sur PV": "N/A", "Bénéfice Net Total": "N/A", "TRI (%)": "N/A"})
    return projection

# --- INTERFACE UTILISATEUR (CONSTRUITE AVEC STREAMLIT) ---
st.title("Simulateur d'Investissement LMNP au Régime Réel 💰")
st.markdown("Optimisez la fiscalité de votre investissement meublé et projetez votre enrichissement net.")

# --- BARRE LATÉRALE POUR LES PARAMÈTRES ---
st.sidebar.header("Paramètres de Simulation")

with st.sidebar.expander("🏠 Projet Immobilier", expanded=True):
    prix_achat = st.number_input("Prix d'achat (€)", min_value=0, value=120000, step=1000)
    cout_travaux = st.number_input("Coût des travaux (€)", min_value=0, value=0, step=500)
    valeur_meubles = st.number_input("Valeur des meubles (€)", min_value=0, value=10000, step=500)
    loyer_mensuel = st.number_input("Loyer mensuel HC (€)", min_value=0, value=900, step=10)

with st.sidebar.expander("🏦 Financement & Frais", expanded=True):
    apport_personnel = st.number_input("Apport personnel (€)", min_value=0, value=30000, step=500)
    frais_notaire = st.number_input("Frais de notaire (€)", min_value=0, value=10000, step=100)
    duree_pret = st.number_input("Durée du prêt (années)", min_value=1, max_value=30, value=25, step=1)
    taux_interet_pret = st.number_input("Taux d'intérêt du prêt (%)", min_value=0.0, value=3.5, step=0.01, format="%.2f")
    taux_assurance_pret = st.number_input("Taux d'assurance du prêt (%)", min_value=0.0, value=0.34, step=0.01, format="%.2f")
    frais_dossier = st.number_input("Frais de dossier bancaire (€)", min_value=0, value=0, step=50)

with st.sidebar.expander("📝 Fiscalité Personnelle (IR)", expanded=True):
    tmi_pc = st.selectbox("Taux Marginal d'Imposition (TMI) (%)", [0.0, 11.0, 30.0, 41.0, 45.0], index=1)
    st.info("Les prélèvements sociaux sur les revenus locatifs sont fixés à 17.2%.")
    duree_amort_immo = st.number_input("Durée amortissement Immobilier (ans)", min_value=1, value=30, step=1)
    duree_amort_meubles = st.number_input("Durée amortissement Meubles (ans)", min_value=1, value=7, step=1)

with st.sidebar.expander("⚙️ Hypothèses de Marché & Charges", expanded=False):
    inflation_pc = st.number_input("Inflation / Revalorisation loyer (%)", min_value=0.0, value=2.0, step=0.1, format="%.1f")
    revalo_bien_pc = st.number_input("Revalorisation annuelle du bien (%)", min_value=0.0, value=2.0, step=0.1, format="%.1f")
    charges_copro = st.number_input("Charges copropriété / mois (€)", min_value=0, value=100, step=5)
    taxe_fonciere = st.number_input("Taxe foncière (€/an)", min_value=0, value=500, step=10)
    frais_gestion_pc = st.number_input("Frais de gestion (%)", min_value=0.0, value=6.0, step=0.1, format="%.1f")
    taux_gli_pc = st.number_input("Taux GLI (%)", min_value=0.0, value=3.5, step=0.1, format="%.1f")
    assurance_pno = st.number_input("Assurance PNO (€/an)", min_value=0, value=120, step=10)
    cfe = st.number_input("CFE (€/an)", min_value=0, value=150, step=10)

# --- AFFICHAGE DES RÉSULTATS ---
st.header("Résultats de la Simulation")

params = {
    "prix_achat": prix_achat, "cout_travaux": cout_travaux, "valeur_meubles": valeur_meubles,
    "loyer_mensuel": loyer_mensuel, "apport_personnel": apport_personnel, "frais_notaire": frais_notaire,
    "duree_pret": duree_pret, "taux_interet_pret": taux_interet_pret, "taux_assurance_pret": taux_assurance_pret,
    "frais_dossier": frais_dossier, "tmi_pc": tmi_pc, "duree_amort_immo": duree_amort_immo,
    "duree_amort_meubles": duree_amort_meubles, "inflation_pc": inflation_pc, "revalo_bien_pc": revalo_bien_pc,
    "charges_copro": charges_copro, "taxe_fonciere": taxe_fonciere, "frais_gestion_pc": frais_gestion_pc,
    "taux_gli_pc": taux_gli_pc, "assurance_pno": assurance_pno, "cfe": cfe
}

projection_data = generer_projection_lmnp(params)

if "erreur" in projection_data[0]:
    st.error(f"Une erreur est survenue : {projection_data[0]['erreur']}")
else:
    df = pd.DataFrame(projection_data)
    
    def format_euros(val):
        if isinstance(val, (int, float)):
            return f"{val:_.0f}".replace('_', '\u00A0') + "\u00A0€"
        return val

    final_formatter = {
        "Loyers Annuels": format_euros,
        "Résultat Fiscal": format_euros,
        "Impôt (IR+PS)": format_euros,
        "Cash-flow Net": format_euros,
        "PV Imposable": format_euros,
        "Impôt sur PV": format_euros,
        "Bénéfice Net Total": format_euros,
        "TRI (%)": lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x,
    }
    
    df_formate = df.style.format(final_formatter, na_rep='N/A').set_properties(**{'text-align': 'right'})
    
    st.dataframe(df_formate, use_container_width=True)

    st.header("Indicateurs Clés du Projet")
    montant_pret = prix_achat + cout_travaux + frais_notaire - apport_personnel

    # --- DÉBUT DE LA CORRECTION ---
    # On va chercher les données sur la dernière ligne de la simulation (avant la séparation)
    # L'index est duree_pret - 1. En indexation négative, c'est -3.
    last_data_row_index = -3

    if len(df) > abs(last_data_row_index) and isinstance(df["Bénéfice Net Total"].iloc[last_data_row_index], (int, float)):
        benefice_final = df["Bénéfice Net Total"].iloc[last_data_row_index]
        tri_final = df["TRI (%)"].iloc[last_data_row_index]
    else:
        benefice_final = 0
        tri_final = 0
    # --- FIN DE LA CORRECTION ---

    col1, col2, col3 = st.columns(3)
    
    col1.metric("Montant du Prêt", format_euros(montant_pret))
    col2.metric(f"Bénéfice Net à {duree_pret} ans", format_euros(benefice_final), help="Votre enrichissement total (Cash Net de revente + Cash-flows cumulés - Investissement initial)")
    col3.metric(f"TRI à {duree_pret} ans", f"{tri_final:.1f}%", help="Le Taux de Rentabilité Interne annualise la performance de votre capital investi.")