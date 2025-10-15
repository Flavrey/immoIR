# app.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import numpy_financial as npf
import numpy as np

# --- CONFIGURATION DE LA PAGE STREAMLIT ---
st.set_page_config(
    page_title="Simulateur SCI à l'IS v3",
    page_icon="📊",
    layout="wide"
)

# --- MOTEUR DE CALCUL (INCHANGÉ) ---
def generer_tableau_amortissement(montant_pret, taux_annuel_pc, duree_annees):
    if not (montant_pret > 0 and taux_annuel_pc > 0 and duree_annees > 0): return {}
    taux_mensuel = (taux_annuel_pc / 100) / 12
    nb_mois = int(duree_annees * 12)
    try:
        mensualite = npf.pmt(taux_mensuel, nb_mois, -montant_pret)
    except (ZeroDivisionError, ValueError):
        return {}
    tableau_annuel = defaultdict(lambda: {'interet': 0, 'principal': 0, 'crd_fin_annee': 0})
    capital_restant_du = montant_pret
    for mois in range(1, nb_mois + 1):
        annee = (mois - 1) // 12 + 1
        interet_mois = capital_restant_du * taux_mensuel
        principal_mois = mensualite - interet_mois
        capital_restant_du -= principal_mois
        tableau_annuel[annee]['interet'] += interet_mois
        tableau_annuel[annee]['principal'] += principal_mois
        tableau_annuel[annee]['crd_fin_annee'] = capital_restant_du if capital_restant_du > 0.01 else 0
    return dict(tableau_annuel)

def generer_projection_sci_is(params):
    valeurs_num = params
    prix_achat, cout_travaux, frais_notaire = valeurs_num["prix_achat"], valeurs_num["cout_travaux"], valeurs_num["frais_notaire"]
    apport, frais_dossier = valeurs_num["apport_personnel"], valeurs_num["frais_dossier"]
    loyer_mensuel_base, charges_copro_base, taxe_fonciere_base = valeurs_num["loyer_mensuel"], valeurs_num["charges_copro"], valeurs_num["taxe_fonciere"]
    cout_acquisition = prix_achat + cout_travaux
    base_amortissable = prix_achat + cout_travaux + frais_notaire
    investissement_initial_personnel = apport + frais_dossier
    montant_pret = cout_acquisition + frais_notaire - apport
    duree_pret = int(valeurs_num["duree_pret"])
    tableau_amortissement_pret = generer_tableau_amortissement(montant_pret, valeurs_num["taux_interet_pret"], duree_pret)
    mensualite_assurance = (montant_pret * (valeurs_num["taux_assurance_pret"] / 100)) / 12 if montant_pret > 0 else 0
    inflation_pc, revalo_bien_pc = valeurs_num["inflation_pc"] / 100, valeurs_num["revalo_bien_pc"] / 100
    cashflow_investisseur_accumule, amortissement_cumule, tresorerie_sci_cumulee, abondement_cumule = 0, 0, 0, 0
    flux_tresorerie_tri_annuels = []
    projection = []

    for annee in range(1, duree_pret + 1):
        facteur_inflation = (1 + inflation_pc)**(annee - 1)
        loyer_annuel = (loyer_mensuel_base * 12) * facteur_inflation
        charges_copro_annuelles = (charges_copro_base * 12) * facteur_inflation
        taxe_fonciere_actuelle = taxe_fonciere_base * facteur_inflation
        frais_gestion_annuels = loyer_annuel * (valeurs_num["frais_gestion_pc"] / 100)
        gli_annuelle = (loyer_annuel + charges_copro_annuelles) * (valeurs_num["taux_gli_pc"] / 100)
        charges_annuelles_cash = (charges_copro_annuelles + taxe_fonciere_actuelle + valeurs_num["assurance_pno"] + frais_gestion_annuels + gli_annuelle + (valeurs_num["cfe"] * facteur_inflation))
        if annee == 1: charges_annuelles_cash += frais_dossier
        interets_annuels = tableau_amortissement_pret.get(annee, {}).get('interet', 0)
        principal_annuel = tableau_amortissement_pret.get(annee, {}).get('principal', 0)
        assurance_annuelle = mensualite_assurance * 12
        mensualite_credit_annuelle = interets_annuels + principal_annuel + assurance_annuelle
        amort_immo_et_frais = base_amortissable * 0.85 / valeurs_num["duree_amort_immo"] if annee <= valeurs_num["duree_amort_immo"] else 0
        amort_meubles = valeurs_num["valeur_meubles"] / valeurs_num["duree_amort_meubles"] if annee <= valeurs_num["duree_amort_meubles"] else 0
        amortissement_annuel = amort_immo_et_frais + amort_meubles
        amortissement_cumule += amortissement_annuel
        resultat_fiscal_sci = loyer_annuel - (charges_annuelles_cash + interets_annuels + assurance_annuelle) - amortissement_annuel
        is_a_payer = 0
        if resultat_fiscal_sci > 0:
            benefice_taux_reduit = min(resultat_fiscal_sci, 42500)
            is_a_payer = (benefice_taux_reduit * 0.15) + (max(0, resultat_fiscal_sci - benefice_taux_reduit) * 0.25)
        cashflow_sci_avant_is = loyer_annuel - charges_annuelles_cash - mensualite_credit_annuelle
        resultat_net_comptable = resultat_fiscal_sci - is_a_payer
        tresorerie_sci_avant_operations = tresorerie_sci_cumulee + cashflow_sci_avant_is - is_a_payer
        abondement = -tresorerie_sci_avant_operations if tresorerie_sci_avant_operations < 0 else 0
        abondement_cumule += abondement
        tresorerie_sci_cumulee = max(0, tresorerie_sci_avant_operations)
        taux_distrib = valeurs_num["taux_distrib_pc"] / 100
        dividendes_distribuables = max(0, resultat_net_comptable)
        dividendes_verses = min(dividendes_distribuables, tresorerie_sci_cumulee) * taux_distrib
        impot_dividendes = dividendes_verses * 0.30
        cash_net_investisseur_annuel = dividendes_verses - impot_dividendes
        cashflow_investisseur_accumule += cash_net_investisseur_annuel
        tresorerie_sci_cumulee -= dividendes_verses
        flux_net_investisseur = cash_net_investisseur_annuel - abondement
        flux_tresorerie_tri_annuels.append(flux_net_investisseur)
        prix_revente = cout_acquisition * (1 + revalo_bien_pc)**annee
        valeur_nette_comptable = base_amortissable - amortissement_cumule
        plus_value_pro = max(0, prix_revente - valeur_nette_comptable)
        is_sur_pv = (min(plus_value_pro, 42500) * 0.15) + (max(0, plus_value_pro - 42500) * 0.25)
        crd = tableau_amortissement_pret.get(annee, {}).get('crd_fin_annee', 0)
        cash_revente_in_sci = prix_revente - crd - is_sur_pv
        distribution_finale = tresorerie_sci_cumulee + cash_revente_in_sci
        impot_distribution_finale = distribution_finale * 0.30
        cash_net_final_investisseur = distribution_finale - impot_distribution_finale
        total_cash_investi = investissement_initial_personnel + abondement_cumule
        total_cash_recu = cashflow_investisseur_accumule - cash_net_investisseur_annuel + cash_net_final_investisseur
        benefice_net_total = total_cash_recu - total_cash_investi
        cash_flows_annuel_tri = [-investissement_initial_personnel] + flux_tresorerie_tri_annuels
        cash_flows_annuel_tri[-1] += cash_net_final_investisseur
        tri_pc = 0
        try:
            tri = npf.irr(cash_flows_annuel_tri)
            tri_pc = tri * 100 if not np.isnan(tri) else 0
        except: pass
        projection.append({"Année": annee, "Loyers Annuels": loyer_annuel, "Résultat Fiscal": resultat_fiscal_sci, "Impôt (IS)": is_a_payer, "Dividendes Dispo.": dividendes_distribuables, "Cash-flow Net Invest.": flux_net_investisseur, "Tréso. SCI": tresorerie_sci_cumulee, "PV Imposable": plus_value_pro, "Impôt sur PV": is_sur_pv, "Bénéfice Net Total": benefice_net_total, "TRI (%)": tri_pc})
    if duree_pret > 0 and projection:
        annee_post_credit = duree_pret + 1
        facteur_inflation = (1 + inflation_pc)**(annee_post_credit - 1)
        loyer_annuel = (loyer_mensuel_base * 12) * facteur_inflation
        charges_copro_annuelles = (charges_copro_base * 12) * facteur_inflation
        taxe_fonciere_actuelle = taxe_fonciere_base * facteur_inflation
        frais_gestion_annuels = loyer_annuel * (valeurs_num["frais_gestion_pc"] / 100)
        gli_annuelle = (loyer_annuel + charges_copro_annuelles) * (valeurs_num["taux_gli_pc"] / 100)
        charges_annuelles_cash = (charges_copro_annuelles + taxe_fonciere_actuelle + valeurs_num["assurance_pno"] + frais_gestion_annuels + gli_annuelle + (valeurs_num["cfe"] * facteur_inflation))
        amort_immo_et_frais = base_amortissable * 0.85 / valeurs_num["duree_amort_immo"] if annee_post_credit <= valeurs_num["duree_amort_immo"] else 0
        amort_meubles = valeurs_num["valeur_meubles"] / valeurs_num["duree_amort_meubles"] if annee_post_credit <= valeurs_num["duree_amort_meubles"] else 0
        amortissement_annuel = amort_immo_et_frais + amort_meubles
        resultat_fiscal_sci = loyer_annuel - charges_annuelles_cash - amortissement_annuel
        is_a_payer = 0
        if resultat_fiscal_sci > 0:
            benefice_taux_reduit = min(resultat_fiscal_sci, 42500)
            is_a_payer = (benefice_taux_reduit * 0.15) + (max(0, resultat_fiscal_sci - benefice_taux_reduit) * 0.25)
        cashflow_sci_avant_is = loyer_annuel - charges_annuelles_cash
        resultat_net_comptable = resultat_fiscal_sci - is_a_payer
        tresorerie_sci_post_credit = tresorerie_sci_cumulee + cashflow_sci_avant_is - is_a_payer
        taux_distrib = valeurs_num["taux_distrib_pc"] / 100
        dividendes_distribuables = max(0, resultat_net_comptable)
        dividendes_verses = min(dividendes_distribuables, tresorerie_sci_post_credit) * taux_distrib
        impot_dividendes = dividendes_verses * 0.30
        cash_net_investisseur_annuel = dividendes_verses - impot_dividendes
        tresorerie_sci_post_credit -= dividendes_verses
        projection.append({key: "---" for key in projection[0].keys()})
        projection.append({"Année": f"An {annee_post_credit}", "Loyers Annuels": loyer_annuel, "Résultat Fiscal": resultat_fiscal_sci, "Impôt (IS)": is_a_payer, "Dividendes Dispo.": dividendes_distribuables, "Cash-flow Net Invest.": cash_net_investisseur_annuel, "Tréso. SCI": tresorerie_sci_post_credit, "PV Imposable": None, "Impôt sur PV": None, "Bénéfice Net Total": None, "TRI (%)": None})
    return projection

# --- INTERFACE UTILISATEUR STREAMLIT ---

# --- BARRE LATÉRALE POUR LES PARAMÈTRES ---
st.sidebar.header("Paramètres de Simulation")

# Section Bien & Charges
with st.sidebar.expander("🏠 Projet Immobilier", expanded=True):
    prix_achat = st.number_input("Prix d'achat (€)", min_value=0, value=200000, step=1000)
    cout_travaux = st.number_input("Coût des travaux (€)", min_value=0, value=30000, step=500)
    valeur_meubles = st.number_input("Valeur des meubles (€)", min_value=0, value=15000, step=500)
    loyer_mensuel = st.number_input("Loyer mensuel HC (€)", min_value=0, value=1200, step=10)

# Section Financement
with st.sidebar.expander("🏦 Financement & Frais", expanded=True):
    apport_personnel = st.number_input("Apport personnel (€)", min_value=0, value=20000, step=500)
    frais_notaire = st.number_input("Frais de notaire (€)", min_value=0, value=16000, step=100)
    duree_pret = st.number_input("Durée du prêt (années)", min_value=1, max_value=30, value=20, step=1)
    taux_interet_pret = st.number_input("Taux d'intérêt du prêt (%)", min_value=0.0, value=3.5, step=0.01, format="%.2f")
    taux_assurance_pret = st.number_input("Taux d'assurance du prêt (%)", min_value=0.0, value=0.34, step=0.01, format="%.2f")
    frais_dossier = st.number_input("Frais de dossier bancaire (€)", min_value=0, value=1500, step=50)

# Section Fiscalité & Amortissement
with st.sidebar.expander("🧾 Fiscalité & Amortissement", expanded=False):
    duree_amort_immo = st.number_input("Durée amort. Immobilier (ans)", min_value=1, value=30, step=1)
    duree_amort_meubles = st.number_input("Durée amort. Meubles (ans)", min_value=1, value=7, step=1)
    taux_distrib_pc = st.number_input("Taux de distribution des dividendes (%)", min_value=0.0, max_value=100.0, value=100.0, step=1.0)

# Section Hypothèses & Charges
with st.sidebar.expander("⚙️ Hypothèses & Charges", expanded=False):
    inflation_pc = st.number_input("Inflation / Revalo. loyer (%)", min_value=0.0, value=2.0, step=0.1, format="%.1f")
    revalo_bien_pc = st.number_input("Revalo. annuelle du bien (%)", min_value=0.0, value=3.0, step=0.1, format="%.1f")
    charges_copro = st.number_input("Charges copro / mois (€)", min_value=0, value=100, step=5)
    taxe_fonciere = st.number_input("Taxe foncière (€/an)", min_value=0, value=1000, step=10)
    frais_gestion_pc = st.number_input("Frais de gestion (%)", min_value=0.0, value=7.0, step=0.1, format="%.1f")
    taux_gli_pc = st.number_input("Taux GLI (%)", min_value=0.0, value=3.5, step=0.1, format="%.1f")
    assurance_pno = st.number_input("Assurance PNO (€/an)", min_value=0, value=200, step=10)
    cfe = st.number_input("CFE (€/an)", min_value=0, value=200, step=10)

# --- CORPS PRINCIPAL DE LA PAGE ---
st.title("Simulateur d'Investissement Locatif en SCI à l'IS 📊")
st.markdown("##### Les résultats se mettent à jour automatiquement en fonction des paramètres saisis dans le menu de gauche.")

params = {
    "prix_achat": prix_achat, "cout_travaux": cout_travaux, "frais_notaire": frais_notaire, "valeur_meubles": valeur_meubles,
    "loyer_mensuel": loyer_mensuel, "charges_copro": charges_copro, "taxe_fonciere": taxe_fonciere,
    "apport_personnel": apport_personnel, "duree_pret": duree_pret, "taux_interet_pret": taux_interet_pret,
    "taux_assurance_pret": taux_assurance_pret, "frais_dossier": frais_dossier,
    "inflation_pc": inflation_pc, "revalo_bien_pc": revalo_bien_pc, "assurance_pno": assurance_pno,
    "frais_gestion_pc": frais_gestion_pc, "taux_gli_pc": taux_gli_pc, "taux_distrib_pc": taux_distrib_pc,
    "duree_amort_immo": duree_amort_immo, "duree_amort_meubles": duree_amort_meubles, "cfe": cfe
}
projection_data = generer_projection_sci_is(params)

# --- Indicateurs Clés ---
st.header("Indicateurs Clés du Projet")
montant_pret = prix_achat + cout_travaux + frais_notaire - apport_personnel
df_numerique = pd.DataFrame(projection_data).dropna().loc[pd.to_numeric(pd.DataFrame(projection_data)['Année'], errors='coerce').notna()]
if not df_numerique.empty:
    cashflow_moyen_investisseur = df_numerique["Cash-flow Net Invest."].mean() / 12
    tri_final = df_numerique["TRI (%)"].iloc[-1]
    benefice_final = df_numerique["Bénéfice Net Total"].iloc[-1]
else:
    cashflow_moyen_investisseur = tri_final = benefice_final = 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Montant du Prêt", f"{montant_pret:,.0f} €")
col2.metric("Cash-flow Net Moyen / mois", f"{cashflow_moyen_investisseur:,.0f} €", help="Moyenne du cash-flow net mensuel reçu par l'investisseur pendant la durée du crédit.")
col3.metric(f"TRI à {duree_pret} ans", f"{tri_final:.1f}%", help="Taux de Rentabilité Interne : le rendement annualisé réel de votre capital investi.")
col4.metric(f"Bénéfice Net à {duree_pret} ans", f"{benefice_final:,.0f} €", help="Enrichissement net final en cas de revente la dernière année.")

# --- Tableau de Projection ---
st.header("Projection Financière Annuelle")
if not projection_data:
    st.warning("Veuillez entrer des paramètres valides pour lancer la simulation.")
else:
    df = pd.DataFrame(projection_data)
    formatter_euros = lambda x: f"{x:,.0f} €" if isinstance(x, (int, float)) else x
    formatter_percent = lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x
    format_dict = {col: formatter_euros for col in df.columns if col not in ["Année", "TRI (%)"]}
    format_dict["TRI (%)"] = formatter_percent
    df_formate = df.style.format(format_dict, na_rep='N/A').set_properties(**{'text-align': 'right'})
    st.dataframe(df_formate, use_container_width=True, height=(duree_pret + 3) * 38)
    
with st.expander("🔍 Explication des colonnes du tableau"):
    st.markdown("""
    - **Année**: L'année de la simulation. 'An X' représente la première année type après la fin du crédit.
    - **Loyers Annuels**: Total des loyers bruts perçus par la SCI.
    - **Résultat Fiscal**: Base de calcul de l'IS : `Loyers - Toutes les charges déductibles - Amortissements`.
    - **Impôt (IS)**: Impôt sur les Sociétés payé par la SCI sur son Résultat Fiscal (15% jusqu'à 42.500€, puis 25%).
    - **Dividendes Dispo.**: Montant maximum distribuable aux associés (`Résultat Fiscal - IS`).
    - **Cash-flow Net Invest.**: Argent net reçu par l'investisseur : `(Dividendes versés - Flat Tax 30%) - Abondement`.
    - **Tréso. SCI**: Trésorerie restante dans la SCI en fin d'année.
    - **PV Imposable**: Plus-value professionnelle imposable à l'IS en cas de revente : `Prix de Vente - Valeur Nette Comptable`.
    - **Impôt sur PV**: IS payé par la SCI sur la plus-value de revente.
    - **Bénéfice Net Total**: Enrichissement net final de l'investisseur en cas de vente : `(Total dividendes nets + Cash net revente) - (Apport + Abondements)`.
    - **TRI (%)**: Taux de Rentabilité Interne. Le rendement annualisé de tout le capital investi.
    """)
