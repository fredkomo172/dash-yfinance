import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes métier
TRADING_DAYS_PER_YEAR = 252  # Nombre de jours de trading par an
DIVIDEND_BAR_WIDTH_MS = 30 * 24 * 60 * 60 * 1000  # 30 jours en millisecondes
MIN_DATA_POINTS = 20  # Minimum de points de données pour une régression fiable
MAX_LOG_SLOPE = 0.5  # Limite pour éviter l'overflow dans exp()
PROJECT_DIR = Path(__file__).parent
CAC40_SEED_FILE = PROJECT_DIR / "cac40.json"
CAC40_FILE = PROJECT_DIR / "data" / "cac40.json"
CAC40_SOURCE_URL = "https://en.wikipedia.org/wiki/CAC_40"
CAC40_REFRESH_DAYS = 7
SP500_SEED_FILE = PROJECT_DIR / "sp500.json"
SP500_FILE = PROJECT_DIR / "data" / "sp500.json"
SP500_SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
INDEX_FILES = {
    "CAC 40": CAC40_FILE,
    "S&P 500": SP500_FILE,
    "SBF 120": PROJECT_DIR / "sbf120.json",
}

# Configuration de la page d'accueil Streamlit
st.set_page_config(page_title="CAC 40 — Régression & Dividendes", layout="wide")

st.title("Analyse Logarithmique & Historique des Dividendes")
st.write(
    "Cette application affiche la droite de régression linéaire avec sa pente (taux annuel), "
    "ainsi que l'historique des dividendes versés sous forme de diagramme à barres."
)

# 1. Listes d'indices locales
def _read_index_file(file_path):
    with file_path.open(encoding="utf-8") as file:
        content = json.load(file)
    companies = content.get("companies")
    if not isinstance(companies, dict):
        raise ValueError(f"Le fichier {file_path.name} ne contient pas de liste valide")
    if any(not isinstance(name, str) or not isinstance(ticker, str) or not ticker
           for name, ticker in companies.items()):
        raise ValueError(f"Le fichier {file_path.name} contient une entrée invalide")
    return content, companies


def _read_cac40_file():
    return _read_index_file(CAC40_FILE)


def _update_cac40_file():
    """Récupère la composition publiée et remplace le JSON uniquement si elle est valide."""
    tables = pd.read_html(CAC40_SOURCE_URL)
    composition = next(
        table for table in tables
        if {"Company", "Ticker"}.issubset(table.columns)
    )
    companies = {}
    for _, row in composition.iterrows():
        name = str(row["Company"]).strip()
        ticker = str(row["Ticker"]).strip()
        if name and ticker and ticker != "nan":
            companies[name] = ticker if ticker.endswith(".PA") else f"{ticker}.PA"
    if len(companies) < 35:
        raise ValueError("La source web ne contient pas une composition CAC 40 crédible")

    content = {
        "updated_at": datetime.now().astimezone().isoformat(),
        "source": CAC40_SOURCE_URL,
        "companies": companies,
    }
    temporary_file = CAC40_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=2)
    temporary_file.replace(CAC40_FILE)
    return companies


def _update_sp500_file():
    """Récupère le CSV public du S&P 500 et remplace le JSON après validation."""
    composition = pd.read_csv(SP500_SOURCE_URL, usecols=["Symbol", "Security"])
    composition = composition.dropna(subset=["Symbol", "Security"])
    companies = {
        str(row["Security"]).strip(): str(row["Symbol"]).strip().replace(".", "-")
        for _, row in composition.iterrows()
    }
    if len(companies) < 450:
        raise ValueError("La source web ne contient pas une composition S&P 500 crédible")

    content = {
        "index": "S&P 500",
        "updated_at": datetime.now().astimezone().isoformat(),
        "source": SP500_SOURCE_URL,
        "source_format": "csv",
        "companies": companies,
    }
    temporary_file = SP500_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=2)
    temporary_file.replace(SP500_FILE)
    return companies


def load_cac40_companies():
    try:
        CAC40_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not CAC40_FILE.exists():
            CAC40_FILE.write_bytes(CAC40_SEED_FILE.read_bytes())
        content, companies = _read_cac40_file()
        updated_at = datetime.fromisoformat(content["updated_at"].replace("Z", "+00:00"))
        age = datetime.now().astimezone() - updated_at
        if age >= timedelta(days=CAC40_REFRESH_DAYS):
            try:
                companies = _update_cac40_file()
                st.toast("La liste CAC 40 a été mise à jour.")
            except (OSError, ValueError, ImportError, StopIteration) as error:
                logger.warning("Mise à jour CAC 40 impossible: %s", error)
                st.info("Mise à jour CAC 40 impossible : utilisation de la dernière liste locale.")
        return companies
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError) as error:
        logger.error("Impossible de charger la liste CAC 40: %s", error)
        st.error(f"Impossible de charger la liste CAC 40 : {error}")
        st.stop()


def load_sp500_companies():
    try:
        SP500_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not SP500_FILE.exists():
            SP500_FILE.write_bytes(SP500_SEED_FILE.read_bytes())
        content, companies = _read_index_file(SP500_FILE)
        updated_at = datetime.fromisoformat(content["updated_at"].replace("Z", "+00:00"))
        is_expired = datetime.now().astimezone() - updated_at >= timedelta(days=CAC40_REFRESH_DAYS)
        if is_expired or len(companies) < 450:
            try:
                companies = _update_sp500_file()
                st.toast("La liste S&P 500 a été mise à jour.")
            except Exception as error:
                logger.warning("Mise à jour S&P 500 impossible: %s", error)
                if not companies:
                    raise ValueError("La liste S&P 500 locale est vide") from error
                st.info("Mise à jour S&P 500 impossible : utilisation de la dernière liste locale.")
        return companies
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError) as error:
        logger.error("Impossible de charger la liste S&P 500: %s", error)
        st.error(f"Impossible de charger la liste S&P 500 : {error}")
        st.stop()


def load_index_companies(index_name):
    if index_name == "CAC 40":
        return load_cac40_companies()
    if index_name == "S&P 500":
        return load_sp500_companies()

    try:
        _, companies = _read_index_file(INDEX_FILES[index_name])
        if not companies:
            raise ValueError(
                f"La liste {index_name} est vide. Sa composition doit encore être importée."
            )
        return companies
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, OSError) as error:
        logger.error("Impossible de charger la liste %s: %s", index_name, error)
        st.error(f"Impossible de charger la liste {index_name} : {error}")
        st.stop()

# --- Configuration de l'analyse ---
st.subheader("Configuration")
col_index, col_select, col_slider = st.columns([1, 1, 1])

with col_index:
    selected_index = st.selectbox(
        "Sélectionnez l'indice :",
        options=list(INDEX_FILES.keys()),
    )

index_companies = load_index_companies(selected_index)

with col_select:
    selected_company = st.selectbox(
        "Sélectionnez l'action à étudier :",
        options=list(index_companies.keys()),
        index=(list(index_companies.keys()).index("LVMH")
               if "LVMH" in index_companies else 0),
    )

with col_slider:
    nb_annees = st.slider(
        "Sélectionnez le nombre d'années d'historique :", 
        min_value=5, max_value=30, value=20, step=1
    )

ticker_symbol = index_companies[selected_company]

# 2. Fonction de téléchargement (Prix + Dividendes)
@st.cache_data(ttl=3600)
def load_data_and_dividends(ticker, years):
    """Télécharge les données de prix et dividendes avec gestion d'erreurs robuste."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    try:
        # Téléchargement des prix de marché
        logger.info(f"Téléchargement des données pour {ticker}...")
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if df.empty:
            logger.error(f"Aucune donnée trouvée pour {ticker}")
            return df, pd.Series(dtype='float64')
            
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement des prix pour {ticker}: {str(e)}")
        return pd.DataFrame(), pd.Series(dtype='float64')
    
    # Récupération des dividendes
    div_series = pd.Series(dtype='float64')
    try:
        tk = yf.Ticker(ticker)
        div_series = tk.dividends
        
        if not div_series.empty:
            # Filtrer pour ne garder que la période sélectionnée
            try:
                # Gérer les fuseaux horaires correctement
                start_date_pd = pd.to_datetime(start_date)
                if div_series.index.tz is not None:
                    start_date_pd = start_date_pd.tz_localize(div_series.index.tz)
                div_series = div_series[div_series.index >= start_date_pd]
                logger.info(f"Dividendes trouvés: {len(div_series)} versements")
            except Exception as e:
                logger.warning(f"Impossible de filtrer les dividendes: {str(e)}")
                div_series = pd.Series(dtype='float64')
        else:
            logger.info(f"Aucun dividende trouvé pour {ticker}")
            
    except Exception as e:
        logger.warning(f"Erreur lors de la récupération des dividendes pour {ticker}: {str(e)}")
        div_series = pd.Series(dtype='float64')
        
    return df, div_series

with st.spinner(f"Téléchargement des données de {selected_company}..."):
    data, dividends = load_data_and_dividends(ticker_symbol, nb_annees)

if not data.empty:
    # Correction des MultiIndex si nécessaire
    if isinstance(data.columns, pd.MultiIndex):
        try:
            data.columns = [col[0] for col in data.columns]
            logger.info("MultiIndex corrigé")
        except Exception as e:
            logger.error(f"Erreur lors de la correction du MultiIndex: {str(e)}")
            st.error("Format de données inattendu. Impossible de traiter.")
            st.stop()
    
    # Sélection de la colonne de prix
    price_col = 'Adj Close' if 'Adj Close' in data.columns else 'Close'
    if price_col not in data.columns:
        st.error(f"Colonne '{price_col}' non trouvée. Colonnes disponibles: {data.columns.tolist()}")
        st.stop()
    
    df_clean = data[[price_col]].dropna().copy()
    df_clean.columns = ['Price']
    
    # Validation: au moins MIN_DATA_POINTS points de données
    if len(df_clean) < MIN_DATA_POINTS:
        st.error(f"Données insuffisantes: {len(df_clean)} points. Minimum requis: {MIN_DATA_POINTS}")
        st.stop()
    
    logger.info(f"Données nettoyées: {len(df_clean)} points de données")
    
    # Validation: pas de prix négatifs ou nuls
    if (df_clean['Price'] <= 0).any():
        st.error("Données invalides: prix négatif ou nul détecté")
        st.stop()
    
    # Étape mathématique : passage au logarithme naturel
    try:
        df_clean['Log_Price'] = np.log(df_clean['Price'])
        df_clean['Ordinal_Time'] = np.arange(len(df_clean))
    except Exception as e:
        st.error(f"Erreur lors du calcul des logarithmes: {str(e)}")
        st.stop()
    
    # Calcul de la Régression Linéaire sur les Logarithmes (y = mx + b)
    try:
        x = df_clean['Ordinal_Time'].values
        y = df_clean['Log_Price'].values
        slopes, res, *_ = np.polyfit(x, y, 1, full=True)
        slope, intercept = slopes[0], slopes[1]
        logger.info(f"Régression calculée: pente={slope:.6f}, ordonnée={intercept:.6f}")
    except Exception as e:
        st.error(f"Erreur lors du calcul de la régression: {str(e)}")
        st.stop()
    
    df_clean['Regression_Log'] = slope * x + intercept

    # --- CALCUL DU COEFFICIENT DE DÉTERMINATION (R²) ---
    try:
        ss_res = res[0] if len(res) > 0 else 0
        ss_tot = np.sum((y - y.mean()) ** 2)
        
        if ss_tot == 0:
            logger.warning("Variance totale nulle: R² indéfini")
            r2 = 0.0
        else:
            r2 = 1 - (ss_res / ss_tot)
            r2 = np.clip(r2, -1, 1)  # R² doit être entre -1 et 1
    except Exception as e:
        logger.error(f"Erreur lors du calcul de R²: {str(e)}")
        r2 = 0.0

    # --- CALCUL DE LA PENTE ANNUELLE (CAGR) ---
    try:
        # Vérifier que la pente n'est pas trop grande (éviter l'overflow)
        if abs(slope) > MAX_LOG_SLOPE:
            logger.warning(f"Pente très élevée ({slope:.6f}), résultats potentiellement non fiables")
        
        pente_annuelle_pct = (np.exp(slope * TRADING_DAYS_PER_YEAR) - 1) * 100
        logger.info(f"Pente annuelle calculée: {pente_annuelle_pct:+.2f}%")
    except (OverflowError, ValueError) as e:
        logger.error(f"Erreur lors du calcul de la pente annuelle: {str(e)}")
        st.error("Pente annuelle non calculable (données extrêmes)")
        pente_annuelle_pct = 0.0
    
    # Calcul des résidus et de l'Écart-Type
    try:
        residuals = df_clean['Log_Price'].values - df_clean['Regression_Log'].values
        std_dev = np.std(residuals)
        logger.info(f"Écart-type calculé: {std_dev:.6f}")
    except Exception as e:
        logger.error(f"Erreur lors du calcul des résidus: {str(e)}")
        std_dev = 0.0
    
    # Conversion inverse vers l'échelle linéaire (euros)
    try:
        df_clean['Regression'] = np.exp(df_clean['Regression_Log'])
        df_clean['+1_STD'] = np.exp(df_clean['Regression_Log'] + std_dev)
        df_clean['+2_STD'] = np.exp(df_clean['Regression_Log'] + 2 * std_dev)
        df_clean['-1_STD'] = np.exp(df_clean['Regression_Log'] - std_dev)
        df_clean['-2_STD'] = np.exp(df_clean['Regression_Log'] - 2 * std_dev)
    except (OverflowError, ValueError) as e:
        logger.error(f"Erreur lors de la conversion logarithmique: {str(e)}")
        st.error("Impossible de calculer les bandes d'écart-type")
        st.stop()
    
    # Indicateurs clés dynamiques
    try:
        col1, col2, col3, col4, col5 = st.columns(5)
        current_price = float(df_clean['Price'].iloc[-1])
        current_reg = float(df_clean['Regression'].iloc[-1])
        
        if current_reg != 0:
            deviation_pct = ((current_price - current_reg) / current_reg) * 100
        else:
            logger.warning("Valeur théorique nulle: écart indéfini")
            deviation_pct = 0.0
    except (IndexError, ValueError) as e:
        logger.error(f"Erreur lors de la récupération des métriques: {str(e)}")
        st.error("Impossible de calculer les indicateurs clés")
        st.stop()
    
    col1.metric(f"Prix Actuel ({selected_company})", f"{current_price:.2f} €")
    col2.metric("Valeur Théorique (Moyenne)", f"{current_reg:.2f} €")
    col3.metric("Écart à la Moyenne", f"{deviation_pct:+.2f} %")
    col4.metric("Pente (Croissance Annuelle)", f"{pente_annuelle_pct:+.2f} % / an")
    col5.metric("Coefficient de Détermination (R2) ", f"{r2:+.2f}")
    
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
        try:
            # Nettoyage des fuseaux horaires pour l'affichage de l'axe X
            if dividends.index.tz is not None:
                dividends_display = dividends.copy()
                dividends_display.index = dividends_display.index.tz_localize(None)
            else:
                dividends_display = dividends
            
            fig_div = go.Figure()
            fig_div.add_trace(go.Bar(
                x=dividends_display.index,
                y=dividends_display.values,
                name="Dividende versé",
                marker_color="#2ca02c", 
                width=DIVIDEND_BAR_WIDTH_MS, 
                text=np.round(dividends_display.values, 2),
                textposition='outside',             
                textfont=dict(size=11, color='black'),
                hovertemplate="<b>Date du détachement :</b> %{x|%d %B %Y}<br><b>Montant :</b> %{y:.2f} €<extra></extra>"
            ))
            
            max_dividend = max(dividends_display.values)
            if max_dividend > 0:
                y_max = max_dividend * 1.15
            else:
                y_max = 1  # Valeur par défaut si max est 0 ou négatif
            
            fig_div.update_layout(
                xaxis=dict(title="Date de versement", fixedrange=True),
                yaxis=dict(
                    title="Montant du Dividende (€)", 
                    fixedrange=True,
                    range=[0, y_max] 
                ),
                template="plotly_white",
                height=350,
                hovermode="x"
            )
            st.plotly_chart(fig_div, use_container_width=True, config=config_graphique)
            logger.info("Graphique des dividendes affiché avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'affichage du graphique des dividendes: {str(e)}")
            st.error(f"Impossible d'afficher le graphique des dividendes: {str(e)}")
    else:
        st.info(f"Aucun dividende n'a été enregistré par Yahoo Finance pour {selected_company} sur cette période.")
        
else:
    st.warning(f"Aucune donnée disponible pour {selected_company}.")