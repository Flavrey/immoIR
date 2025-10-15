# app.py

import streamlit as st
import pandas as pd
from collections import defaultdict
import numpy_financial as npf
import numpy as np

# --- MOTEUR DE CALCUL DU PRÊT (INCHANGÉ) ---
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

# --- MOTEUR DE CALCUL IMPÔT PLUS-VALUE (INCHANGÉ) ---
def calculer_impot_plus_value(plus_value_brute, duree_detention):
    if plus_value_brute <= 0: return 0, 0, 0, 0
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
    return impot_total_pv, plus_value_brute, base_imposable_ir, base_imposable_ps


# --- MOTEUR DE SIMULATION LMNP (INCHANGÉ) ---
def generer_projection_lmnp(params):
    try: valeurs_num = {k: float(v) for k, v in params.items()}
    except (ValueError, TypeError): return [{"erreur": "Veuillez entrer des nombres valides."}]

    # Initialisation
    prix_achat, cout_travaux, frais_notaire = valeurs_num.get("prix_achat", 0), valeurs_num.get("cout_travaux", 0), valeurs_num.get("frais_notaire", 0)
    apport, frais_dossier = valeurs_num.get("apport_personnel", 0), valeurs_num.get("frais_dossier", 0)
    montant_pret = prix_achat + cout_travaux + frais_notaire - apport
    cout_acquisition = prix_achat + cout_travaux
    base_acquisition_pv = prix_achat + cout_travaux + frais_notaire
    investissement_initial_personnel = apport + frais_dossier # Frais de notaire sont dans le prêt
    duree_pret = int(valeurs_num.get("duree_pret", 0))

    tableau_amortissement_pret = generer_tableau_amortissement(montant_pret, valeurs_num.get("taux_interet_pret", 0), duree_pret)
    mensualite_assurance_base = (montant_pret * (valeurs_num.get("taux_assurance_pret", 0) / 100)) / 12

    loyer_mensuel_base, charges_copro_base, taxe_fonciere_base = valeurs_num.get("loyer_mensuel", 0), valeurs_num.get("charges_copro", 0), valeurs_num.get("taxe_fonciere", 0)
    inflation_pc, revalo_bien_pc = valeurs_num.get("inflation_pc", 0) / 100, valeurs_num.get("revalo_bien_pc", 0) / 100
    tmi_pc, prelevements_sociaux_pc = valeurs_num.get("tmi_pc", 0) / 100, 0.172 # PS sur revenus locatifs sont fixes
    
    cashflow_investisseur_accumule, amortissement_cumule, deficit_reportable = 0, 0, 0
    tresorerie_sarl_cumulee = 0
    abondement_cumule = 0
    flux_tresorerie_tri_annuels = []
    projection = []

    for annee in range(1, duree_pret + 1):
        facteur_inflation = (1 + inflation_pc)**(annee - 1)
        loyer_annuel = (loyer_mensuel_base * 12) * facteur_inflation
        charges_copro_annuelles = (charges_copro_base * 12) * facteur_inflation
        taxe_fonciere_actuelle = taxe_fonciere_base * facteur_inflation
        frais_gestion_annuels = loyer_annuel * (valeurs_num.get("frais_gestion_pc", 0) / 100)
        gli_annuelle = (loyer_annuel + charges_copro_annuelles) * (valeurs_num.get("taux_gli_pc", 0) / 100)
        
        charges_annuelles_cash = (charges_copro_annuelles + taxe_fonciere_actuelle +
            valeurs_num.get("assurance_pno", 0) + frais_gestion_annuels + gli_annuelle +
            (valeurs_num.get("cfe", 0) * facteur_inflation))
        if annee == 1: charges_annuelles_cash += frais_dossier

        interets_annuels = tableau_amortissement_pret.get(annee, {}).get('interet', 0)
        assurance_annuelle = mensualite_assurance_base * 12
        
        charges_annuelles_deductibles = charges_annuelles_cash + interets_annuels + assurance_annuelle
        
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
        mensualite_credit_annuelle = interets_annuels + principal_annuel + assurance_annuelle
        cashflow_sarl_avant_operations = loyer_annuel - charges_annuelles_cash - mensualite_credit_annuelle
        
        tresorerie_avant_distribution = tresorerie_sarl_cumulee + cashflow_sarl_avant_operations
        
        abondement = 0
        if tresorerie_avant_distribution < 0:
            abondement = abs(tresorerie_avant_distribution)
            abondement_cumule += abondement
            tresorerie_sarl_cumulee = 0
        else:
            tresorerie_sarl_cumulee = tresorerie_avant_distribution
            
        taux_distrib = valeurs_num.get("taux_distrib_pc", 100) / 100
        dividendes_disponibles = max(0, resultat_fiscal_avant_deficit)
        dividendes_verses = min(dividendes_disponibles, tresorerie_sarl_cumulee) * taux_distrib
        
        tresorerie_sarl_cumulee -= dividendes_verses
        
        cashflow_net_investisseur_annuel = dividendes_verses - impot_total_annuel - abondement
        cashflow_investisseur_accumule += cashflow_net_investisseur_annuel
        flux_tresorerie_tri_annuels.append(cashflow_net_investisseur_annuel)

        prix_revente = cout_acquisition * (1 + revalo_bien_pc)**annee
        valeur_nette_comptable = base_acquisition_pv - amortissement_cumule
        plus_value_brute = prix_revente - base_acquisition_pv
        
        impot_sur_pv, _, _, _ = calculer_impot_plus_value(plus_value_brute, annee)

        crd = tableau_amortissement_pret.get(annee, {}).get('crd_fin_annee', 0)
        
        cash_net_apres_revente = prix_revente - crd - impot_sur_pv
        cash_net_final_investisseur = cash_net_apres_revente + tresorerie_sarl_cumulee
        
        total_cash_investi = investissement_initial_personnel + abondement_cumule
        total_cash_recu = cashflow_investisseur_accumule - cashflow_net_investisseur_annuel + cash_net_final_investisseur
        benefice_net_total = total_cash_recu - total_cash_investi
        
        cash_flows_annuel = [-investissement_initial_personnel] + flux_tresorerie_tri_annuels[:]
        cash_flows_annuel[-1] += cash_net_final_investisseur
        try: 
            tri = npf.irr(cash_flows_annuel)
            tri_pc = tri * 100 if not np.isnan(tri) else 0
        except: 
            tri_pc = 0

        projection.append({ "Année": annee, "Loyers Annuels": loyer_annuel, "Résultat Fiscal": resultat_fiscal_avant_deficit, "Dividendes Disponibles": dividendes_disponibles, "Impôt (IR+PS)": impot_total_annuel, "Cash-flow Net": cashflow_net_investisseur_annuel, "Tréso. SARL": tresorerie_sarl_cumulee, "PV Brute": plus_value_brute, "Impôt sur PV": impot_sur_pv, "Bénéfice Net Total": benefice_net_total, "TRI (%)": tri_pc })

    # Section post-crédit
    projection_post_credit = {}
    if duree_pret > 0 and len(projection) > 0:
        annee_post_credit = duree_pret + 1; facteur_inflation = (1 + inflation_pc)**(annee_post_credit - 1)
        loyer_annuel = (loyer_mensuel_base * 12) * facteur_inflation; charges_copro_annuelles = (charges_copro_base * 12) * facteur_inflation
        taxe_fonciere_actuelle = taxe_fonciere_base * facteur_inflation
        frais_gestion_annuels = loyer_annuel * (valeurs_num.get("frais_gestion_pc", 0) / 100); gli_annuelle = (loyer_annuel + charges_copro_annuelles) * (valeurs_num.get("taux_gli_pc", 0) / 100)
        charges_annuelles_cash = (charges_copro_annuelles + taxe_fonciere_actuelle + valeurs_num.get("assurance_pno", 0) + frais_gestion_annuels + gli_annuelle + (valeurs_num.get("cfe", 0) * facteur_inflation))
        
        amort_immo = (prix_achat + frais_notaire) * 0.85 / valeurs_num.get("duree_amort_immo", 1) if annee_post_credit <= valeurs_num.get("duree_amort_immo", 0) else 0
        amort_travaux = cout_travaux / 10 if annee_post_credit <= 10 else 0
        amort_meubles = valeurs_num.get("valeur_meubles", 0) / valeurs_num.get("duree_amort_meubles", 1) if annee_post_credit <= valeurs_num.get("duree_amort_meubles", 0) else 0
        amortissement_annuel = amort_immo + amort_travaux + amort_meubles
        resultat_fiscal = loyer_annuel - charges_annuelles_cash - amortissement_annuel
        
        benefice_imposable = max(0, resultat_fiscal - deficit_reportable); impot_total_annuel = benefice_imposable * (tmi_pc + prelevements_sociaux_pc)
        cashflow_sarl_post_credit = loyer_annuel - charges_annuelles_cash
        
        tresorerie_post_credit = tresorerie_sarl_cumulee + cashflow_sarl_post_credit
        
        taux_distrib = valeurs_num.get("taux_distrib_pc", 100) / 100
        dividendes_disponibles = max(0, resultat_fiscal)
        dividendes_verses = min(dividendes_disponibles, tresorerie_post_credit) * taux_distrib
        
        cashflow_net_investisseur_annuel = dividendes_verses - impot_total_annuel
        tresorerie_post_credit -= dividendes_verses
        
        projection_post_credit = {"Année": f"An {annee_post_credit}", "Loyers Annuels": loyer_annuel, "Résultat Fiscal": resultat_fiscal, "Dividendes Disponibles": dividendes_disponibles, "Impôt (IR+PS)": impot_total_annuel, "Cash-flow Net": cashflow_net_investisseur_annuel, "Tréso. SARL": tresorerie_post_credit, "PV Brute": "N/A", "Impôt sur PV": "N/A", "Bénéfice Net Total": "N/A", "TRI (%)": "N/A"}

    return projection, projection_post_credit


# --- INTERFACE GRAPHIQUE STREAMLIT ---

st.set_page_config(layout="wide", page_title="Simulateur SARL de Famille (IR)")

# --- Zone de saisie dans la barre latérale ---
with st.sidebar:
    st.header("⚙️ Paramètres de Simulation")

    # Définition des champs et de leurs valeurs par défaut
    champs = { "bien": {"prix_achat": 120000.0, "cout_travaux": 0.0, "valeur_meubles": 10000.0, "loyer_mensuel": 900.0}, "financement": {"apport_personnel": 30000.0, "frais_notaire": 10000.0, "duree_pret": 25, "taux_interet_pret": 3.5, "taux_assurance_pret": 0.34, "frais_dossier": 0.0}, "fiscalite": {"tmi_pc": 11.0, "duree_amort_immo": 30, "duree_amort_meubles": 7, "taux_distrib_pc": 100.0}, "hypotheses": {"inflation_pc": 2.0, "revalo_bien_pc": 2.0, "charges_copro": 100.0, "taxe_fonciere": 500.0, "frais_gestion_pc": 6.0, "taux_gli_pc": 3.5, "assurance_pno": 120.0, "cfe": 150.0} }
    params = {}

    # Panneaux de saisie
    with st.expander("🏠 Projet Immobilier", expanded=True):
        params["prix_achat"] = st.number_input("Prix d'achat (€)", min_value=0.0, value=champs["bien"]["prix_achat"], step=1000.0, format="%.2f")
        params["cout_travaux"] = st.number_input("Coût des travaux (€)", min_value=0.0, value=champs["bien"]["cout_travaux"], step=500.0, format="%.2f")
        params["valeur_meubles"] = st.number_input("Valeur des meubles (€)", min_value=0.0, value=champs["bien"]["valeur_meubles"], step=100.0, format="%.2f")
        params["loyer_mensuel"] = st.number_input("Loyer mensuel HC (€)", min_value=0.0, value=champs["bien"]["loyer_mensuel"], step=10.0, format="%.2f")
    
    with st.expander("💰 Financement & Frais", expanded=True):
        params["apport_personnel"] = st.number_input("Apport personnel (€)", min_value=0.0, value=champs["financement"]["apport_personnel"], step=1000.0, format="%.2f")
        params["frais_notaire"] = st.number_input("Frais de notaire & annexes (€)", min_value=0.0, value=champs["financement"]["frais_notaire"], step=100.0, format="%.2f")
        params["duree_pret"] = st.number_input("Durée du prêt (ans)", min_value=1, max_value=30, value=champs["financement"]["duree_pret"], step=1)
        params["taux_interet_pret"] = st.number_input("Taux d'intérêt du prêt (%)", min_value=0.0, value=champs["financement"]["taux_interet_pret"], step=0.01, format="%.2f")
        params["taux_assurance_pret"] = st.number_input("Taux d'assurance du prêt (%)", min_value=0.0, value=champs["financement"]["taux_assurance_pret"], step=0.01, format="%.2f")
        params["frais_dossier"] = st.number_input("Frais de dossier bancaire (€)", min_value=0.0, value=champs["financement"]["frais_dossier"], step=50.0, format="%.2f")
        montant_pret = params["prix_achat"] + params["cout_travaux"] + params["frais_notaire"] - params["apport_personnel"]
        st.metric(label="Montant du prêt à financer", value=f"{montant_pret:,.2f} €")

    with st.expander("⚖️ Fiscalité & Distribution", expanded=True):
        params["tmi_pc"] = st.number_input("Taux Marginal d'Imposition (TMI) (%)", min_value=0.0, max_value=100.0, value=champs["fiscalite"]["tmi_pc"], step=1.0, format="%.2f")
        st.info("PS sur revenus locatifs : 17.2%.")
        params["duree_amort_immo"] = st.number_input("Durée d'amortissement de l'immobilier (ans)", min_value=1, max_value=100, value=champs["fiscalite"]["duree_amort_immo"], step=1)
        params["duree_amort_meubles"] = st.number_input("Durée d'amortissement des meubles (ans)", min_value=1, max_value=20, value=champs["fiscalite"]["duree_amort_meubles"], step=1)
        params["taux_distrib_pc"] = st.number_input("Taux de distribution des dividendes (%)", min_value=0.0, max_value=100.0, value=champs["fiscalite"]["taux_distrib_pc"], step=5.0, format="%.2f")

    with st.expander("📈 Hypothèses & Charges Annuelles", expanded=True):
        params["inflation_pc"] = st.number_input("Inflation annuelle (%)", min_value=0.0, max_value=20.0, value=champs["hypotheses"]["inflation_pc"], step=0.1, format="%.2f")
        params["revalo_bien_pc"] = st.number_input("Revalorisation annuelle du bien (%)", min_value=-5.0, max_value=20.0, value=champs["hypotheses"]["revalo_bien_pc"], step=0.1, format="%.2f")
        params["charges_copro"] = st.number_input("Charges de copropriété mensuelles (€)", min_value=0.0, value=champs["hypotheses"]["charges_copro"], step=5.0, format="%.2f")
        params["taxe_fonciere"] = st.number_input("Taxe foncière annuelle (€)", min_value=0.0, value=champs["hypotheses"]["taxe_fonciere"], step=10.0, format="%.2f")
        params["frais_gestion_pc"] = st.number_input("Frais de gestion locative (%)", min_value=0.0, max_value=100.0, value=champs["hypotheses"]["frais_gestion_pc"], step=0.5, format="%.2f")
        params["taux_gli_pc"] = st.number_input("Taux d'assurance loyers impayés (GLI) (%)", min_value=0.0, max_value=10.0, value=champs["hypotheses"]["taux_gli_pc"], step=0.1, format="%.2f")
        params["assurance_pno"] = st.number_input("Assurance PNO annuelle (€)", min_value=0.0, value=champs["hypotheses"]["assurance_pno"], step=5.0, format="%.2f")
        params["cfe"] = st.number_input("Cotisation Foncière des Entreprises (CFE) (€)", min_value=0.0, value=champs["hypotheses"]["cfe"], step=10.0, format="%.2f")


# --- Zone principale pour les titres et les résultats ---
st.title("📈 Simulateur d'Investissement en SARL de Famille (IR)")
st.write("Cet outil permet de simuler la rentabilité d'un investissement locatif meublé (LMNP) via une SARL de famille à l'IR.")
st.divider()

st.header("📊 Projection Financière Annuelle")

projection_data, projection_post_credit = generer_projection_lmnp(params)

if "erreur" in projection_data:
    st.error(projection_data["erreur"])
else:
    df = pd.DataFrame(projection_data)
    
    # Formatage du DataFrame pour affichage
    format_dict = {
        'Loyers Annuels': '{:,.0f} €', 'Résultat Fiscal': '{:,.0f} €', 'Dividendes Disponibles': '{:,.0f} €',
        'Impôt (IR+PS)': '{:,.0f} €', 'Cash-flow Net': '{:,.0f} €', 'Tréso. SARL': '{:,.0f} €',
        'PV Brute': '{:,.0f} €', 'Impôt sur PV': '{:,.0f} €', 'Bénéfice Net Total': '{:,.0f} €',
        'TRI (%)': '{:.1f}%'
    }
    
    df_styled = df.style.format(format_dict)
    
    st.dataframe(df_styled, use_container_width=True)

    if projection_post_credit:
        st.subheader(f"🗓️ Situation après la fin du crédit (An {params['duree_pret'] + 1})")
        
        # Affichage sous forme de métriques pour plus de clarté
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Loyers Annuels", f"{projection_post_credit['Loyers Annuels']:,.0f} €")
        col2.metric("Résultat Fiscal", f"{projection_post_credit['Résultat Fiscal']:,.0f} €")
        col3.metric("Impôt (IR+PS)", f"{projection_post_credit['Impôt (IR+PS)']:,.0f} €", delta_color="inverse")
        col4.metric("Cash-flow Net Investisseur", f"{projection_post_credit['Cash-flow Net']:,.0f} €")


# Explications des colonnes
with st.expander("📘 Cliquez ici pour voir la description des colonnes du tableau"):
    descriptions_calcul = {
        "Année": "L'année de la simulation.",
        "Loyers Annuels": "Total des loyers perçus dans l'année, revalorisés avec l'inflation.",
        "Résultat Fiscal": "Base de calcul de l'impôt annuel : Loyers - Charges déductibles - Amortissements. Peut être négatif (déficit).",
        "Dividendes Disponibles": "Montant maximum distribuable aux associés. Calcul : Résultat Fiscal. Ne peut être distribué que si la trésorerie est suffisante.",
        "Impôt (IR+PS)": "Impôt total payé par l'investisseur sur les bénéfices locatifs, après déduction des déficits antérieurs.",
        "Cash-flow Net": "Argent net reçu par l'investisseur : (Dividendes versés) - (Impôts payés) - (Abondement éventuel pour couvrir un déficit de trésorerie).",
        "Tréso. SARL": "Trésorerie restante dans l'entreprise en fin d'année, après paiement des charges et distribution des dividendes.",
        "PV Brute": "Plus-Value Brute en cas de revente à l'année N : Prix de Vente - Prix d'Acquisition (hors frais).",
        "Impôt sur PV": "Impôt total (IR à 19% + PS à 17.2%) payé sur la plus-value, après abattements pour durée de détention.",
        "Bénéfice Net Total": "Enrichissement net final de l'investisseur en cas de vente. Total des flux (cash net de la revente + dividendes perçus) moins le total du capital investi (apport + abondements).",
        "TRI (%)": "Taux de Rentabilité Interne. Le rendement annualisé de votre capital investi, tenant compte de tous les flux de trésorerie (investissement initial, cash-flows annuels, et revente). C'est un indicateur de performance clé."
    }
    for col, desc in descriptions_calcul.items():
        st.markdown(f"**{col}**: {desc}")
