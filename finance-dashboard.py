import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuration de la page d'accueil Streamlit
st.set_page_config(page_title="CAC 40 — Régression & Dividendes", layout="wide")

st.title("Analyse Logarithmique & Historique des Dividendes — CAC 40")
st.write(
    "Cette application affiche la droite de régression linéaire avec sa pente (taux annuel), "
    "ainsi que l'historique des dividendes versés sous forme de diagramme à barres."
)

# 1. Base de données locale des 40 actions du CAC 40
CAC40_COMPANIES = {
    "Air Liquide": "AI.PA", "Airbus": "AIR.PA", "Alstom": "ALO.PA", "ArcelorMittal": "MT.PA",
    "AXA": "CS.PA", "BNP Paribas": "BNP.PA", "Bouygues": "EN.PA", "Capgemini": "CAP.PA",
    "Carrefour": "CA.PA", "Crédit Agricole": "ACA.PA", "Danone": "BN.PA", "Dassault Systèmes": "DSY.PA",
    "Edenred": "EDEN.PA", "Engie": "ENGI.PA", "EssilorLuxottica": "EL.PA", "Eurofins Scientific": "ERF.PA",
    "Hermès": "RMS.PA", "Kering": "KER.PA", "L'Oréal": "OR.PA", "Legrand": "LR.PA",
    "LVMH": "MC.PA", "Michelin": "ML.PA", "Orange": "ORA.PA", "Pernod Ricard": "RI.PA",
    "Publicis Groupe": "PUB.PA", "Renault": "RNO.PA", "Safran": "SAF.PA", "Saint-Gobain": "SGO.PA",
    "Sanofi": "SAN.PA", "Schneider Electric": "SU.PA", "Société Générale": "GLE.PA", "Stellantis": "STLAP.PA",
    "STMicroelectronics": "STMPA.PA", "Teleperformance": "TEP.PA", "Thales": "HO.PA", "TotalEnergies": "TTE.PA",
    "Unibail-Rodamco-Westfield": "URW.PA", "Veolia Environnement": "VIE.PA", "Vinci": "DG.PA", "Vivendi": "VIV.PA"
}

# --- Configuration de l'analyse ---
st.subheader("Configuration")
col_select, col_slider = st.columns([1, 1])

with col_select:
    selected_company = st.selectbox(
        "Sélectionnez l'action à étudier :",
        options=list(CAC40_COMPANIES.keys()),
        index=20  # Position de LVMH par défaut
    )

with col_slider:
    nb_annees = st.slider(
        "Sélectionnez le nombre d'années d'historique :", 
        min_value=5, max_value=30, value=20, step=1
    )

ticker_symbol = CAC40_COMPANIES[selected_company]

# 2. Fonction de téléchargement (Prix + Dividendes)
@st.cache_data(ttl=3600)
def load_data_and_dividends(ticker, years):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    # Téléchargement des prix de marché
    df = yf.download(ticker, start=start_date, end=end_date)
    
    # Récupération spécifique des dividendes via l'objet Ticker
    tk = yf.Ticker(ticker)
    try:
        div_series = tk.dividends
        # Filtrer pour ne garder que la période sélectionnée
        start_date_pd = pd.to_datetime(start_date).tz_localize(div_series.index.tz)
        div_series = div_series[div_series.index >= start_date_pd]
    except:
        div_series = pd.Series(dtype='float64')
        
    return df, div_series

with st.spinner(f"Téléchargement des données de {selected_company}..."):
    data, dividends = load_data_and_dividends(ticker_symbol, nb_annees)

if not data.empty:
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]
        
    price_col = 'Adj Close' if 'Adj Close' in data.columns else 'Close'
    df_clean = data[[price_col]].dropna().copy()
    df_clean.columns = ['Price']
    
    # Étape mathématique : passage au logarithme naturel
    df_clean['Log_Price'] = np.log(df_clean['Price'])
    df_clean['Ordinal_Time'] = np.arange(len(df_clean))
    
    # Calcul de la Régression Linéaire sur les Logarithmes (y = mx + b)
    x = df_clean['Ordinal_Time']
    y = df_clean['Log_Price']
    slope, intercept = np.polyfit(x, y, 1)
    
    df_clean['Regression_Log'] = slope * x + intercept
    
    # --- CALCUL DE LA PENTE ANNUELLE (CAGR) ---
    pente_annuelle_pct = (np.exp(slope * 252) - 1) * 100
    
    # Calcul des résidus et de l'Écart-Type
    residuals = df_clean['Log_Price'] - df_clean['Regression_Log']
    std_dev = np.std(residuals)
    
    # Conversion inverse vers l'échelle linéaire (euros)
    df_clean['Regression'] = np.exp(df_clean['Regression_Log'])
    df_clean['+1_STD'] = np.exp(df_clean['Regression_Log'] + std_dev)
    df_clean['+2_STD'] = np.exp(df_clean['Regression_Log'] + 2 * std_dev)
    df_clean['-1_STD'] = np.exp(df_clean['Regression_Log'] - std_dev)
    df_clean['-2_STD'] = np.exp(df_clean['Regression_Log'] - 2 * std_dev)
    
    # Indicateurs clés dynamiques
    col1, col2, col3, col4 = st.columns(4)
    current_price = float(df_clean['Price'].iloc[-1])
    current_reg = float(df_clean['Regression'].iloc[-1])
    deviation_pct = ((current_price - current_reg) / current_reg) * 100
    
    col1.metric(f"Prix Actuel ({selected_company})", f"{current_price:.2f} €")
    col2.metric("Valeur Théorique (Moyenne)", f"{current_reg:.2f} €")
    col3.metric("Écart à la Moyenne", f"{deviation_pct:+.2f} %")
    col4.metric("Pente (Croissance Annuelle)", f"{pente_annuelle_pct:+.2f} % / an")
    
    # --- 1er GRAPHIQUE : RÉGRESSION LOGARITHMIQUE ---
    st.write("### Droite de régression du cours en échelle logarithme")
    fig_reg = go.Figure()
    
    fig_reg.add_trace(go.Scatter(x=df_clean.index, y=df_clean['Price'], name=f'Cours de {selected_company}', line=dict(color='#1f77b4', width=2)))
    fig_reg.add_trace(go.Scatter(x=df_clean.index, y=df_clean['Regression'], name='Régression Linéaire (Tendance)', line=dict(color='orange', width=2)))
    fig_reg.add_trace(go.Scatter(x=df_clean.index, y=df_clean['+1_STD'], name='+1 Écart-type', line=dict(color='green', width=1, dash='dash')))
    fig_reg.add_trace(go.Scatter(x=df_clean.index, y=df_clean['+2_STD'], name='+2 Écart-type', line=dict(color='darkgreen', width=1, dash='dot')))
    fig_reg.add_trace(go.Scatter(x=df_clean.index, y=df_clean['-1_STD'], name='-1 Écart-type', line=dict(color='red', width=1, dash='dash')))
    fig_reg.add_trace(go.Scatter(x=df_clean.index, y=df_clean['-2_STD'], name='-2 Écart-type', line=dict(color='darkred', width=1, dash='dot')))
    
    fig_reg.update_layout(
        xaxis=dict(title="Date", fixedrange=True),
        yaxis=dict(title="Prix (Échelle Logarithmique en €)", type="log", fixedrange=True),
        hovermode="x unified", template="plotly_white", height=800,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    config_graphique = {
        'scrollZoom': False, 'displayModeBar': True,
        'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
    }
    st.plotly_chart(fig_reg, use_container_width=True, config=config_graphique)
    
    # --- 2ème GRAPHIQUE : HISTORIQUE DES DIVIDENDES ---
    st.write("### Historique des Dividendes Versés")
    
    if not dividends.empty:
        # Nettoyage des fuseaux horaires pour l'affichage de l'axe X
        dividends.index = dividends.index.tz_localize(None)
        
        fig_div = go.Figure()
        fig_div.add_trace(go.Bar(
            x=dividends.index,
            y=dividends.values,
            name="Dividende versé",
            marker_color="#2ca02c", 
            width=30 * 24 * 60 * 60 * 1000, 
            text=np.round(dividends.values, 2),
            textposition='outside',             
            textfont=dict(size=11, color='black'),
            hovertemplate="<b>Date du détachement :</b> %{x|%d %B %Y}<br><b>Montant :</b> %{y:.2f} €<extra></extra>"
        ))
        
        fig_div.update_layout(
            xaxis=dict(title="Date de versement", fixedrange=True),
            yaxis=dict(
                title="Montant du Dividende (€)", 
                fixedrange=True,
                range=[0, max(dividends.values) * 1.15] 
            ),
            template="plotly_white",
            height=350,
            hovermode="x"
        )
        st.plotly_chart(fig_div, use_container_width=True, config=config_graphique)
    else:
        st.info(f"Aucun dividende n'a été enregistré par Yahoo Finance pour {selected_company} sur cette période.")
        
else:
    st.warning(f"Aucune donnée disponible pour {selected_company}.")