"""
Advance GSC Data Analysis Module for CrawlPilot SEO Suite
Integrates deep Google Search Console (GSC) export analysis, striking-distance quick wins,
low-hanging fruit CTR optimization, content gaps, questions intent, traffic projection modeling,
and country/page telemetry.
"""

import io
import re
import os
import zipfile
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from typing import Dict, Any, Tuple, Optional


def read_csv_robust(file_bytes_or_buffer) -> pd.DataFrame:
    """Robustly reads a CSV file trying different encodings, delimiters, and strip BOM."""
    if isinstance(file_bytes_or_buffer, bytes):
        raw_bytes = file_bytes_or_buffer
    else:
        raw_bytes = file_bytes_or_buffer.read()

    # Try common encodings and separators
    for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252', 'utf-16']:
        for sep in [None, ',', ';', '\t']:
            try:
                if sep is None:
                    df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, sep=None, engine='python')
                else:
                    df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, sep=sep)

                if len(df.columns) >= 2 or (len(df) > 0 and len(df.columns) == 1):
                    # Clean column names (strip BOM, quotes, spaces)
                    cleaned_cols = [str(c).replace('\ufeff', '').strip().strip('"').strip("'") for c in df.columns]
                    # If columns were merged because sep sniffing didn't catch it, continue trying
                    if len(cleaned_cols) == 1 and (';' in cleaned_cols[0] or ',' in cleaned_cols[0] or '\t' in cleaned_cols[0]):
                        continue
                    df.columns = cleaned_cols
                    return df
            except Exception:
                continue

    # Ultimate fallback default
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes), encoding_errors='replace')
        df.columns = [str(c).replace('\ufeff', '').strip().strip('"').strip("'") for c in df.columns]
        return df
    except Exception as e:
        st.warning(f"Warning parsing CSV: {e}")
        return pd.DataFrame()


def extract_csv_from_zip(zip_file) -> Dict[str, pd.DataFrame]:
    """Extract all CSV files from the uploaded ZIP file with case-insensitive matching."""
    csv_data = {}
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        for file in zip_ref.namelist():
            if file.lower().endswith('.csv') and not file.startswith('__MACOSX'):
                clean_name = os.path.basename(file).replace('.csv', '').replace('.CSV', '')
                try:
                    df = read_csv_robust(zip_ref.read(file))
                    if not df.empty:
                        csv_data[clean_name] = df
                        csv_data[clean_name.lower()] = df
                except Exception as e:
                    st.warning(f"Warning: Could not parse {file}: {e}")
    return csv_data


def clean_ctr_column(df: pd.DataFrame, column_name: str = 'ctr') -> pd.DataFrame:
    """Convert CTR from percentage string ('2.5%') or scaled float to a proper decimal float."""
    for col in df.columns:
        if col.lower() == column_name.lower() or 'ctr' in col.lower() or 'klickrate' in col.lower() or 'taux' in col.lower():
            try:
                if df[col].dtype == object:
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace('%', '', regex=False)
                        .str.replace(',', '.', regex=False)
                        .str.strip()
                    )
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                else:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

                if df[col].max() > 1.0:
                    df[col] = df[col] / 100.0
            except Exception:
                df[col] = 0.0
            break
    return df


def standardize_columns(df: pd.DataFrame, default_entity_type: str = 'query') -> pd.DataFrame:
    """
    Standardize column names to lowercase with underscores and resolve GSC naming variations.
    Guarantees that query/page/country, clicks, impressions, ctr, position columns exist.
    """
    if df.empty:
        return df

    new_cols = []
    for col in df.columns:
        c = str(col).replace('\ufeff', '').strip().lower().replace(' ', '_').replace('-', '_')
        # Check CTR FIRST so 'click_through_rate' does NOT get matched to 'clicks'
        if 'ctr' in c or 'click_through' in c or 'clickthrough' in c or 'klickrate' in c or 'taux' in c or '%' in c:
            new_cols.append('ctr')
        elif any(k in c for k in ['query', 'queries', 'keyword', 'consulta', 'suchanfrag', 'requêt']):
            new_cols.append('query')
        elif any(k in c for k in ['page', 'url', 'landing_page', 'seite', 'página']):
            new_cols.append('page')
        elif any(k in c for k in ['countr', 'land', 'pays', 'país']):
            new_cols.append('country')
        elif any(k in c for k in ['clicks', 'click', 'clics', 'clic', 'klicks', 'klick', 'cliques', 'clique']):
            new_cols.append('clicks')
        elif any(k in c for k in ['impress', 'view', 'vista', 'vue', 'impressionen']):
            new_cols.append('impressions')
        elif any(k in c for k in ['position', 'pos', 'rang', 'rank', 'platz']):
            new_cols.append('position')
        else:
            new_cols.append(c)

    df.columns = new_cols

    # Positional mapping fallback if standard names weren't present
    # Standard GSC format: Col 0 = Entity, Col 1 = Clicks, Col 2 = Impressions, Col 3 = CTR, Col 4 = Position
    if default_entity_type not in df.columns and len(df.columns) > 0:
        df.rename(columns={df.columns[0]: default_entity_type}, inplace=True)

    if 'clicks' not in df.columns:
        if len(df.columns) > 1 and df.columns[1] not in ['query', 'page', 'country']:
            df.rename(columns={df.columns[1]: 'clicks'}, inplace=True)
        else:
            df['clicks'] = 0

    if 'impressions' not in df.columns:
        if len(df.columns) > 2 and df.columns[2] not in ['query', 'page', 'country', 'clicks']:
            df.rename(columns={df.columns[2]: 'impressions'}, inplace=True)
        else:
            df['impressions'] = 0

    if 'ctr' not in df.columns:
        if len(df.columns) > 3 and df.columns[3] not in ['query', 'page', 'country', 'clicks', 'impressions']:
            df.rename(columns={df.columns[3]: 'ctr'}, inplace=True)
        else:
            df['ctr'] = 0.0

    if 'position' not in df.columns:
        if len(df.columns) > 4 and df.columns[4] not in ['query', 'page', 'country', 'clicks', 'impressions', 'ctr']:
            df.rename(columns={df.columns[4]: 'position'}, inplace=True)
        else:
            df['position'] = 0.0

    return df


def sanitize_dataframe(df: pd.DataFrame, default_entity_type: str = 'query') -> pd.DataFrame:
    """Standardizes, deduplicates, cleans CTR, and casts numeric columns safely without throwing TypeError."""
    if df.empty:
        return df

    # Standardize column headers
    df = standardize_columns(df, default_entity_type=default_entity_type)

    # Deduplicate columns if any duplicate name exists
    df = df.loc[:, ~df.columns.duplicated(keep='first')].copy()

    # Clean CTR column
    df = clean_ctr_column(df, 'ctr')

    # Convert numeric columns safely (handling Series or 1D DataFrame)
    for col in ['clicks', 'impressions']:
        if col in df.columns:
            series = df[col].iloc[:, 0] if isinstance(df[col], pd.DataFrame) else df[col]
            df[col] = pd.to_numeric(series, errors='coerce').fillna(0).astype(int)
        else:
            df[col] = 0

    for col in ['position', 'ctr']:
        if col in df.columns:
            series = df[col].iloc[:, 0] if isinstance(df[col], pd.DataFrame) else df[col]
            df[col] = pd.to_numeric(series, errors='coerce').fillna(0.0).astype(float)
        else:
            df[col] = 0.0

    return df


def generate_sample_gsc_data() -> Dict[str, pd.DataFrame]:
    """Generates a realistic sample GSC dataset for quick testing and demonstration."""
    sample_queries = [
        ("best industrial valves", 1420, 18500, 0.0768, 4.2),
        ("electric actuator valve manufacturer", 980, 14200, 0.0690, 3.8),
        ("knife gate valve installation guide", 450, 12600, 0.0357, 12.4),
        ("pneumatic actuator vs electric actuator", 320, 11400, 0.0281, 14.2),
        ("how does a knife gate valve work", 290, 9800, 0.0296, 11.8),
        ("what is an industrial valve actuator", 260, 8900, 0.0292, 13.5),
        ("ansi 150 valve pressure ratings", 180, 15400, 0.0117, 18.2),
        ("high temperature butterfly valve specs", 140, 16800, 0.0083, 21.4),
        ("zero leakage valve maintenance", 110, 13200, 0.0083, 19.5),
        ("cast steel vs stainless steel valves", 95, 7800, 0.0122, 15.3),
        ("how to calibrate electric actuator", 85, 6400, 0.0133, 16.1),
        ("valve actuator wiring diagram", 70, 5200, 0.0135, 17.8),
        ("why do valve seats leak under pressure", 60, 4800, 0.0125, 14.9),
        ("valve torque calculation formula", 55, 18200, 0.0030, 68.4),
        ("industrial piping flange dimensions table", 42, 22400, 0.0019, 74.2),
        ("severe service slurry gate valves", 38, 14500, 0.0026, 62.1),
        ("top valve suppliers in gujarat", 520, 2400, 0.2167, 1.8),
        ("cair euromatic electric actuators", 610, 1900, 0.3211, 1.2),
        ("industrial automation equipment", 410, 28000, 0.0146, 2.8),
        ("flanged ball valve dimensions", 380, 19500, 0.0195, 2.9),
        ("where to buy actuated valves in india", 190, 4200, 0.0452, 8.4),
        ("when to replace valve gland packing", 115, 3900, 0.0295, 9.6),
    ]
    df_q = pd.DataFrame(sample_queries, columns=['query', 'clicks', 'impressions', 'ctr', 'position'])

    sample_pages = [
        ("https://example.com/products/electric-actuator-valves", 2150, 28400, 0.0757, 4.1),
        ("https://example.com/solution/knife-gate-valves", 1420, 24600, 0.0577, 6.2),
        ("https://example.com/complete-product-listing", 980, 31200, 0.0314, 8.5),
        ("https://example.com/blog/pneumatic-vs-electric-actuators", 540, 19800, 0.0273, 13.8),
        ("https://example.com/blog/how-knife-gate-valves-work", 390, 14200, 0.0275, 12.1),
        ("https://example.com/technical-specs/valve-torque-calculator", 85, 34500, 0.0025, 65.4),
        ("https://example.com/about-us", 650, 4200, 0.1548, 1.4),
        ("https://example.com/contact-quote", 420, 3100, 0.1355, 1.6),
    ]
    df_p = pd.DataFrame(sample_pages, columns=['page', 'clicks', 'impressions', 'ctr', 'position'])

    sample_countries = [
        ("India", 3450, 42500, 0.0812, 5.2),
        ("United States", 1240, 32100, 0.0386, 9.8),
        ("United Arab Emirates", 820, 14800, 0.0554, 7.1),
        ("United Kingdom", 540, 12400, 0.0435, 11.2),
        ("Germany", 410, 9600, 0.0427, 12.5),
        ("Saudi Arabia", 380, 8900, 0.0427, 8.9),
        ("Canada", 290, 7500, 0.0387, 13.1),
        ("Australia", 240, 6800, 0.0353, 14.2),
    ]
    df_c = pd.DataFrame(sample_countries, columns=['country', 'clicks', 'impressions', 'ctr', 'position'])

    return {
        'Queries': df_q,
        'queries': df_q,
        'Pages': df_p,
        'pages': df_p,
        'Countries': df_c,
        'countries': df_c
    }


def render_advance_gsc_analysis_page():
    """Main Streamlit renderer for the Advance GSC data Analysis service."""

    # 1. Header Banner
    st.markdown("""
    <div style="background: radial-gradient(130% 120% at 50% -10%, #1e1b4b 0%, #0F172A 60%, #020617 100%); padding: 2.5rem 2rem 2rem; border-radius: 20px; border: 1px solid rgba(139, 92, 246, 0.35); text-align: center; margin-bottom: 2rem; box-shadow: 0 20px 45px -10px rgba(0,0,0,0.6);">
        <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.4); padding: 5px 16px; border-radius: 999px; margin-bottom: 12px;">
            <span style="font-size: 0.85rem; font-weight: 800; color: #C4B5FD; letter-spacing: 0.06em; text-transform: uppercase;">📈 Google Search Console Deep Intelligence</span>
        </div>
        <h1 style="font-size: 2.75rem; font-weight: 900; color: #FFFFFF; letter-spacing: -0.03em; margin: 0 0 0.6rem 0; line-height: 1.15;">
            Advance GSC Data Analysis
        </h1>
        <p style="color: #94A3B8; font-size: 1.05rem; max-width: 740px; margin: 0 auto; line-height: 1.6;">
            Deep-dive into your Google Search Console performance data. Uncover Page-2 striking distance quick wins, low-hanging fruit CTR fixes, question search intent, and algorithmic traffic potential projections.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 2. Upload and Data Acquisition Area
    col_upload, col_sample = st.columns([3.5, 1.5])
    with col_upload:
        uploaded_file = st.file_uploader(
            "📤 Upload Google Search Console Export (ZIP or CSV format):",
            type=['zip', 'csv'],
            help="In Google Search Console, click 'Export' ➔ 'Download ZIP' (or upload Queries.csv directly)."
        )
    with col_sample:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        load_sample = st.button("🧪 Load Sample GSC Data", use_container_width=True, help="Load an industrial demo dataset to preview all reports and features instantly.")

    csv_files = {}

    if uploaded_file is not None:
        try:
            with st.spinner("📦 Extracting and parsing Google Search Console data..."):
                if uploaded_file.name.lower().endswith('.zip'):
                    csv_files = extract_csv_from_zip(uploaded_file)
                else:
                    # Single CSV uploaded
                    single_df = read_csv_robust(uploaded_file.getvalue())
                    clean_name = os.path.splitext(uploaded_file.name)[0]
                    csv_files[clean_name] = single_df
                    csv_files[clean_name.lower()] = single_df
                    csv_files['queries'] = single_df
                    csv_files['Queries'] = single_df

                st.session_state["gsc_cached_data"] = csv_files
                st.toast("✅ GSC Data successfully loaded and processed!", icon="🚀")
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.info("💡 Please make sure the file is directly exported from Google Search Console.")
            return
    elif load_sample or st.session_state.get("gsc_use_sample"):
        st.session_state["gsc_use_sample"] = True
        csv_files = generate_sample_gsc_data()
        st.session_state["gsc_cached_data"] = csv_files
        st.info("ℹ️ Currently displaying **Sample Industrial GSC Demo Dataset**. Upload your real export above anytime to analyze your live site.")
    elif "gsc_cached_data" in st.session_state:
        csv_files = st.session_state["gsc_cached_data"]
    else:
        # Empty State Helper Card
        st.markdown("""
        <div style="background: rgba(15, 23, 42, 0.7); border: 1px dashed rgba(139, 92, 246, 0.4); border-radius: 16px; padding: 2.5rem 2rem; text-align: center; margin-top: 1rem;">
            <div style="font-size: 2.8rem; margin-bottom: 0.8rem;">📥</div>
            <h3 style="color: #F8FAFC; margin-bottom: 0.5rem; font-weight: 800;">No GSC Data Loaded Yet</h3>
            <p style="color: #94A3B8; font-size: 0.95rem; max-width: 580px; margin: 0 auto 1.5rem; line-height: 1.6;">
                Export your Google Search Console performance data (Performance ➔ Export ➔ Download ZIP), then upload it above or click <b>'Load Sample GSC Data'</b> to see a full live demonstration.
            </p>
            <div style="display: flex; justify-content: center; gap: 15px; font-size: 0.84rem; color: #CBD5E1;">
                <span>✔ <b>Queries.csv</b> Analysis</span>
                <span>✔ <b>Pages.csv</b> Analysis</span>
                <span>✔ <b>Countries.csv</b> Analysis</span>
                <span>✔ Striking Distance Quick Wins</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Intelligently find queries, pages, and countries DataFrames across filenames & languages
    queries_df = pd.DataFrame()
    for k in csv_files:
        if any(w in k.lower() for w in ['quer', 'suchanfrag', 'consult', 'requêt', 'keyword']):
            queries_df = csv_files[k].copy()
            break

    pages_df = pd.DataFrame()
    for k in csv_files:
        if any(w in k.lower() for w in ['page', 'seite', 'págin', 'url']):
            pages_df = csv_files[k].copy()
            break

    countries_df = pd.DataFrame()
    for k in csv_files:
        if any(w in k.lower() for w in ['countr', 'land', 'pays', 'país']):
            countries_df = csv_files[k].copy()
            break

    # If queries_df is still not resolved, take the first available DataFrame
    if queries_df.empty and len(csv_files) > 0:
        first_key = list(csv_files.keys())[0]
        queries_df = csv_files[first_key].copy()

    if queries_df.empty:
        st.error("❌ 'Queries.csv' was not found inside the uploaded ZIP. Please ensure your Google Search Console export contains Queries data.")
        return

    # Standardize, clean, and cast with full column guarantees & deduplication
    queries_df = sanitize_dataframe(queries_df, default_entity_type='query')

    if not pages_df.empty:
        pages_df = sanitize_dataframe(pages_df, default_entity_type='page')

    if not countries_df.empty:
        countries_df = sanitize_dataframe(countries_df, default_entity_type='country')

    # 3. High-Level KPI Summary Cards
    total_clicks = int(queries_df['clicks'].sum()) if 'clicks' in queries_df.columns else 0
    total_impressions = int(queries_df['impressions'].sum()) if 'impressions' in queries_df.columns else 0
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
    avg_position = queries_df['position'].mean() if 'position' in queries_df.columns and len(queries_df) > 0 else 0.0
    total_queries = len(queries_df)
    total_pages = len(pages_df) if not pages_df.empty else 0

    st.markdown(f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 1.8rem;">
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 1.2rem; text-align: center;">
            <div style="color: #94A3B8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">Total Clicks</div>
            <div style="font-size: 1.9rem; font-weight: 900; color: #38BDF8;">{total_clicks:,}</div>
            <div style="font-size: 0.74rem; color: #64748B; margin-top: 4px;">Organic Search Traffic</div>
        </div>
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 12px; padding: 1.2rem; text-align: center;">
            <div style="color: #94A3B8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">Total Impressions</div>
            <div style="font-size: 1.9rem; font-weight: 900; color: #A78BFA;">{total_impressions:,}</div>
            <div style="font-size: 0.74rem; color: #64748B; margin-top: 4px;">Total Search Visibility</div>
        </div>
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 1.2rem; text-align: center;">
            <div style="color: #94A3B8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">Average CTR</div>
            <div style="font-size: 1.9rem; font-weight: 900; color: #34D399;">{avg_ctr:.2f}%</div>
            <div style="font-size: 0.74rem; color: #64748B; margin-top: 4px;">Click-Through Ratio</div>
        </div>
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; padding: 1.2rem; text-align: center;">
            <div style="color: #94A3B8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">Average Position</div>
            <div style="font-size: 1.9rem; font-weight: 900; color: #FBBF24;">{avg_position:.1f}</div>
            <div style="font-size: 0.74rem; color: #64748B; margin-top: 4px;">Mean SERP Rank</div>
        </div>
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(236, 72, 153, 0.3); border-radius: 12px; padding: 1.2rem; text-align: center;">
            <div style="color: #94A3B8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">Indexed Queries</div>
            <div style="font-size: 1.9rem; font-weight: 900; color: #F472B6;">{total_queries:,}</div>
            <div style="font-size: 0.74rem; color: #64748B; margin-top: 4px;">Unique Keyword Terms</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4. Global Analysis Tuning Controls
    with st.expander("⚙️ Analysis Parameters & Sensitivity Thresholds", expanded=False):
        c_p1, c_p2, c_p3 = st.columns(3)
        with c_p1:
            min_impressions = st.slider(
                "Minimum Impressions Filter:",
                min_value=1,
                max_value=10000,
                value=500 if total_impressions > 50000 else 20,
                step=10,
                help="Filters out low volume queries so you only focus on meaningful search traffic."
            )
            top_queries_count = st.slider("Top Queries to Display:", 5, 100, 25, step=5)
        with c_p2:
            min_pos_qw = st.slider("Quick Wins Min Position (Page 2 start):", 5, 20, 11, step=1)
            max_pos_qw = st.slider("Quick Wins Max Position (Page 2 end):", 15, 30, 20, step=1)
        with c_p3:
            max_pos_opp = st.slider("Content Gap Max Position Threshold:", 30, 100, 60, step=5)
            low_hanging_ctr_thresh = st.slider("Low-Hanging Fruit Max CTR Threshold:", 0.05, 0.40, 0.20, step=0.01, format="%.2f")

    def format_gsc_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        if 'ctr' in d.columns:
            d['ctr'] = d['ctr'].apply(lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "0.00%")
        if 'position' in d.columns:
            d['position'] = d['position'].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "0.0")
        if 'clicks' in d.columns:
            d['clicks'] = d['clicks'].fillna(0).astype(int)
        if 'impressions' in d.columns:
            d['impressions'] = d['impressions'].fillna(0).astype(int)
        return d

    # 5. Core Analytical Modules Tabs
    tab_qw, tab_lh, tab_pot, tab_top, tab_quest, tab_opp, tab_cloud, tab_geo_page = st.tabs([
        "⚡ Quick Wins (Pos 11-20)",
        "🍎 Low-Hanging Fruits (CTR)",
        "📈 Traffic Potential Estimator",
        "📊 Top Performing Queries",
        "❓ Questions & Informational",
        "🎯 Keyword Gaps (Pos > 60)",
        "☁️ Keyword Word Cloud",
        "🌍 Countries & Pages"
    ])

    query_cols = [c for c in ['query', 'clicks', 'impressions', 'ctr', 'position'] if c in queries_df.columns]

    # TAB 1: QUICK WINS
    with tab_qw:
        st.markdown(f"""
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 1.2rem;">
            <div style="font-weight: 800; font-size: 1.05rem; color: #10B981; margin-bottom: 4px;">⚡ Page-2 Striking Distance Keywords (Position {min_pos_qw} - {max_pos_qw})</div>
            <div style="font-size: 0.85rem; color: #94A3B8; line-height: 1.5;">
                These keywords rank on <b>Page 2 of Google</b> with at least <b>{min_impressions} impressions</b>. Because Google already trusts your page for these terms, small on-page optimizations (adding keywords to H2s, improving internal links, and refreshing content) can push them into Page 1 and generate massive traffic spikes.
            </div>
        </div>
        """, unsafe_allow_html=True)

        filter_mask = (
            (queries_df['position'] >= min_pos_qw) &
            (queries_df['position'] <= max_pos_qw) &
            (queries_df['impressions'] >= min_impressions)
        )
        sort_cols = [c for c in ['impressions', 'position'] if c in queries_df.columns]
        if sort_cols:
            quick_wins = queries_df[filter_mask][query_cols].sort_values(sort_cols, ascending=[False, True]).reset_index(drop=True)
        else:
            quick_wins = queries_df[filter_mask][query_cols].reset_index(drop=True)

        if len(quick_wins) > 0:
            quick_wins.index = range(1, len(quick_wins) + 1)
            qw_disp = format_gsc_df_for_display(quick_wins)
            st.dataframe(qw_disp, use_container_width=True, height=380)

            qw_csv = quick_wins.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Quick Wins Report (.CSV)",
                data=qw_csv,
                file_name="gsc_quick_wins_striking_distance.csv",
                mime="text/csv",
                key="btn_dl_qw"
            )
        else:
            st.info(f"No quick wins found with position between {min_pos_qw}-{max_pos_qw} and ≥ {min_impressions} impressions. Try lowering the impressions threshold in settings above.")

    # TAB 2: LOW-HANGING FRUITS
    with tab_lh:
        st.markdown(f"""
        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 1.2rem;">
            <div style="font-weight: 800; font-size: 1.05rem; color: #F59E0B; margin-bottom: 4px;">🍎 Low-Hanging Fruit Optimization (Top 3 Positions, CTR < {low_hanging_ctr_thresh*100:.0f}%)</div>
            <div style="font-size: 0.85rem; color: #94A3B8; line-height: 1.5;">
                These queries already hold prime real estate in the <b>Top 3 search results</b>, but searchers aren't clicking. By rewriting your <b>Page Titles and Meta Descriptions</b> to be more compelling, adding numbers, power words, and answering the searcher's intent, you can double your clicks without building a single backlink.
            </div>
        </div>
        """, unsafe_allow_html=True)

        filter_mask = (
            (queries_df['position'] <= 3.5) &
            (queries_df['ctr'] < low_hanging_ctr_thresh) &
            (queries_df['impressions'] >= max(5, min_impressions // 2))
        )
        sort_cols = [c for c in ['impressions', 'ctr'] if c in queries_df.columns]
        if sort_cols:
            low_hanging = queries_df[filter_mask][query_cols].sort_values(sort_cols, ascending=[False, True]).reset_index(drop=True)
        else:
            low_hanging = queries_df[filter_mask][query_cols].reset_index(drop=True)

        if len(low_hanging) > 0:
            low_hanging.index = range(1, len(low_hanging) + 1)
            lh_disp = format_gsc_df_for_display(low_hanging)
            st.dataframe(lh_disp, use_container_width=True, height=380)

            lh_csv = low_hanging.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Low-Hanging Fruits Report (.CSV)",
                data=lh_csv,
                file_name="gsc_low_hanging_fruits.csv",
                mime="text/csv",
                key="btn_dl_lh"
            )
        else:
            st.info("No low-hanging fruit queries found with current thresholds. All top 3 positions have healthy CTR!")

    # TAB 3: TRAFFIC POTENTIAL ESTIMATION
    with tab_pot:
        st.markdown("""
        <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 1.2rem;">
            <div style="font-weight: 800; font-size: 1.05rem; color: #38BDF8; margin-bottom: 4px;">📈 Algorithmic Traffic Growth Projection Engine</div>
            <div style="font-size: 0.85rem; color: #94A3B8; line-height: 1.5;">
                How many extra clicks would your site generate if sub-page-1 keywords reached the first page? This model benchmarks your domain's actual <b>Top 10 average CTR</b> and projects incremental clicks across lower-ranking keywords.
            </div>
        </div>
        """, unsafe_allow_html=True)

        top_10 = queries_df[queries_df['position'] <= 10.0] if 'position' in queries_df.columns else pd.DataFrame()
        avg_ctr_top10 = top_10['ctr'].mean() if len(top_10) > 0 and 'ctr' in top_10.columns and top_10['ctr'].mean() > 0 else 0.045

        calc_df = queries_df.copy()
        if 'clicks' in calc_df.columns and 'position' in calc_df.columns and 'impressions' in calc_df.columns:
            calc_df['potential_clicks'] = calc_df.apply(
                lambda r: r['clicks'] if r['position'] <= 10.0 else (r['impressions'] * avg_ctr_top10),
                axis=1
            )
            calc_df['click_gain'] = calc_df['potential_clicks'] - calc_df['clicks']
        else:
            calc_df['potential_clicks'] = 0
            calc_df['click_gain'] = 0

        current_clicks_sum = calc_df['clicks'].sum() if 'clicks' in calc_df.columns else 0
        potential_clicks_sum = calc_df['potential_clicks'].sum()
        gain_clicks_sum = max(0, potential_clicks_sum - current_clicks_sum)
        gain_pct = (gain_clicks_sum / current_clicks_sum * 100) if current_clicks_sum > 0 else 0

        pot_col1, pot_col2, pot_col3, pot_col4 = st.columns(4)
        with pot_col1:
            st.metric("Top-10 Benchmark CTR", f"{avg_ctr_top10*100:.2f}%")
        with pot_col2:
            st.metric("Current Total Clicks", f"{int(current_clicks_sum):,}")
        with pot_col3:
            st.metric("Estimated Potential Clicks", f"{int(potential_clicks_sum):,}")
        with pot_col4:
            st.metric("Projected Growth", f"+{gain_pct:.1f}%", f"+{int(gain_clicks_sum):,} extra clicks")

        pot_target_cols = [c for c in ['query', 'position', 'clicks', 'potential_clicks', 'click_gain', 'impressions'] if c in calc_df.columns]
        potential_table = calc_df[
            (calc_df['click_gain'] > 1) &
            (calc_df['position'] > 10.0)
        ][pot_target_cols]

        if 'click_gain' in potential_table.columns:
            potential_table = potential_table.sort_values('click_gain', ascending=False)
        potential_table = potential_table.head(30).reset_index(drop=True)

        if len(potential_table) > 0:
            potential_table.index = range(1, len(potential_table) + 1)
            disp_pot = potential_table.copy()
            if 'clicks' in disp_pot.columns: disp_pot['clicks'] = disp_pot['clicks'].astype(int)
            if 'potential_clicks' in disp_pot.columns: disp_pot['potential_clicks'] = disp_pot['potential_clicks'].astype(int)
            if 'click_gain' in disp_pot.columns: disp_pot['click_gain'] = disp_pot['click_gain'].astype(int)
            if 'impressions' in disp_pot.columns: disp_pot['impressions'] = disp_pot['impressions'].astype(int)
            if 'position' in disp_pot.columns: disp_pot['position'] = disp_pot['position'].apply(lambda x: f"{x:.1f}")

            st.markdown("#### 🎯 Top Keywords Ranked by Click Gain Opportunity:")
            st.dataframe(disp_pot, use_container_width=True, height=350)

            pot_csv = potential_table.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Traffic Potential Report (.CSV)",
                data=pot_csv,
                file_name="gsc_traffic_potential_opportunities.csv",
                mime="text/csv",
                key="btn_dl_pot"
            )
        else:
            st.info("No queries found with significant gain potential based on current impressions.")

    # TAB 4: TOP PERFORMING QUERIES
    with tab_top:
        st.markdown(f"#### 📊 Top {top_queries_count} Queries Driving Highest Clicks")
        sort_col = 'clicks' if 'clicks' in queries_df.columns else ('impressions' if 'impressions' in queries_df.columns else queries_df.columns[0])
        top_queries = queries_df.nlargest(min(top_queries_count, len(queries_df)), sort_col)[query_cols].reset_index(drop=True)
        top_queries.index = range(1, len(top_queries) + 1)

        disp_top = format_gsc_df_for_display(top_queries)
        st.dataframe(disp_top, use_container_width=True, height=380)

        if len(top_queries) > 0 and 'clicks' in top_queries.columns:
            fig_top = px.bar(
                top_queries.head(15).sort_values('clicks', ascending=True),
                x='clicks',
                y='query',
                orientation='h',
                title="Top 15 Queries by Organic Clicks",
                color='clicks',
                color_continuous_scale='Purples',
                template="plotly_dark"
            )
            fig_top.update_layout(
                paper_bgcolor='rgba(15, 23, 42, 0.9)',
                plot_bgcolor='rgba(15, 23, 42, 0.9)',
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_top, use_container_width=True)

    # TAB 5: QUESTION QUERIES
    with tab_quest:
        st.markdown("""
        <div style="background: rgba(139, 92, 246, 0.08); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 1.2rem;">
            <div style="font-weight: 800; font-size: 1.05rem; color: #A78BFA; margin-bottom: 4px;">❓ Informational & Question Search Queries</div>
            <div style="font-size: 0.85rem; color: #94A3B8; line-height: 1.5;">
                These queries contain question modifiers (<i>what, how, why, when, where, which, can, is, are</i>). They represent <b>Featured Snippet opportunities</b>, FAQ sections, and high-converting educational blog topics.
            </div>
        </div>
        """, unsafe_allow_html=True)

        question_regex = r'\b(what|how|why|when|where|which|who|can|is|are|should|does|do)\b'
        question_queries = queries_df[
            queries_df['query'].astype(str).str.lower().str.contains(question_regex, regex=True, na=False)
        ][query_cols]

        if 'impressions' in question_queries.columns:
            question_queries = question_queries.sort_values('impressions', ascending=False)
        question_queries = question_queries.reset_index(drop=True)

        if len(question_queries) > 0:
            question_queries.index = range(1, len(question_queries) + 1)
            disp_quest = format_gsc_df_for_display(question_queries)
            st.dataframe(disp_quest, use_container_width=True, height=380)

            q_csv = question_queries.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Question Queries (.CSV)",
                data=q_csv,
                file_name="gsc_question_queries.csv",
                mime="text/csv",
                key="btn_dl_quest"
            )
        else:
            st.info("No question queries found matching question terms (what, how, why, etc.).")

    # TAB 6: KEYWORD OPPORTUNITIES
    with tab_opp:
        st.markdown(f"""
        <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 1.2rem;">
            <div style="font-weight: 800; font-size: 1.05rem; color: #EF4444; margin-bottom: 4px;">🎯 Content Gap Opportunities (Position > {max_pos_opp})</div>
            <div style="font-size: 0.85rem; color: #94A3B8; line-height: 1.5;">
                These keywords rank beyond <b>Position {max_pos_opp}</b> but already generate at least <b>{min_impressions} impressions</b>. They indicate that search engines associate your brand with the topic, but you lack a dedicated, authoritative landing page. Creating targeted content for these queries can unlock brand new rankings.
            </div>
        </div>
        """, unsafe_allow_html=True)

        filter_mask = (
            (queries_df['position'] > max_pos_opp) &
            (queries_df['impressions'] >= min_impressions)
        )
        sort_cols = [c for c in ['impressions', 'position'] if c in queries_df.columns]
        if sort_cols:
            opps = queries_df[filter_mask][query_cols].sort_values(sort_cols, ascending=[False, True]).reset_index(drop=True)
        else:
            opps = queries_df[filter_mask][query_cols].reset_index(drop=True)

        if len(opps) > 0:
            opps.index = range(1, len(opps) + 1)
            disp_opp = format_gsc_df_for_display(opps)
            st.dataframe(disp_opp, use_container_width=True, height=380)

            opp_csv = opps.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Content Gap Opportunities (.CSV)",
                data=opp_csv,
                file_name="gsc_content_gap_opportunities.csv",
                mime="text/csv",
                key="btn_dl_opp"
            )
        else:
            st.info(f"No keyword opportunities found beyond position {max_pos_opp} with ≥ {min_impressions} impressions.")

    # TAB 7: KEYWORD WORD CLOUD
    with tab_cloud:
        st.markdown("#### ☁️ Keyword Semantic Themes & Word Cloud")
        st.write("Visualizes the most frequently occurring terms across your top queries weighted by search impressions.")

        try:
            if 'impressions' in queries_df.columns:
                top_for_cloud = queries_df.nlargest(min(150, len(queries_df)), 'impressions')['query'].astype(str).tolist()
            else:
                top_for_cloud = queries_df['query'].head(150).astype(str).tolist()
            text = ' '.join(top_for_cloud)
            if len(text.strip()) > 5:
                wc = WordCloud(
                    width=900,
                    height=450,
                    background_color='#0F172A',
                    colormap='plasma',
                    max_words=100
                ).generate(text)

                fig_wc, ax = plt.subplots(figsize=(12, 6), facecolor='#0F172A')
                ax.imshow(wc, interpolation='bilinear')
                ax.axis('off')
                st.pyplot(fig_wc)
                plt.close(fig_wc)
            else:
                st.info("Not enough text to generate a word cloud.")
        except Exception as e:
            st.error(f"Could not generate word cloud: {str(e)}")

    # TAB 8: COUNTRIES & PAGES
    with tab_geo_page:
        col_g1, col_g2 = st.columns(2)

        # Countries Section
        if not countries_df.empty:
            c_name_col = 'country' if 'country' in countries_df.columns else countries_df.columns[0]
            with col_g1:
                st.markdown("#### 🌍 Top Countries by Clicks")
                sort_col = 'clicks' if 'clicks' in countries_df.columns else countries_df.columns[min(1, len(countries_df.columns)-1)]
                top_countries = countries_df.sort_values(sort_col, ascending=False).head(10)
                fig_c = px.bar(
                    top_countries.sort_values(sort_col, ascending=True),
                    y=c_name_col,
                    x=sort_col,
                    orientation='h',
                    color=sort_col,
                    color_continuous_scale='Blues',
                    template="plotly_dark"
                )
                fig_c.update_layout(paper_bgcolor='rgba(15, 23, 42, 0.9)', plot_bgcolor='rgba(15, 23, 42, 0.9)', margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_c, use_container_width=True)

            with col_g2:
                st.markdown("#### 🌐 Top Countries by Impressions")
                sort_col_i = 'impressions' if 'impressions' in countries_df.columns else countries_df.columns[min(2, len(countries_df.columns)-1)]
                fig_ci = px.bar(
                    top_countries.sort_values(sort_col_i, ascending=True) if sort_col_i in top_countries.columns else top_countries,
                    y=c_name_col,
                    x=sort_col_i if sort_col_i in top_countries.columns else sort_col,
                    orientation='h',
                    color=sort_col_i if sort_col_i in top_countries.columns else sort_col,
                    color_continuous_scale='Greens',
                    template="plotly_dark"
                )
                fig_ci.update_layout(paper_bgcolor='rgba(15, 23, 42, 0.9)', plot_bgcolor='rgba(15, 23, 42, 0.9)', margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_ci, use_container_width=True)

        # Pages Section
        if not pages_df.empty:
            st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1.5rem 0;'>", unsafe_allow_html=True)
            st.markdown("#### 📄 Top Pages Driving Organic Traffic")
            p_cols = [c for c in ['page', 'clicks', 'impressions', 'ctr', 'position'] if c in pages_df.columns]
            sort_p = 'clicks' if 'clicks' in pages_df.columns else pages_df.columns[0]
            top_pages = pages_df.sort_values(sort_p, ascending=False).head(20).reset_index(drop=True)
            top_pages.index = range(1, len(top_pages) + 1)
            st.dataframe(format_gsc_df_for_display(top_pages[p_cols]), use_container_width=True, height=300)

            st.markdown("#### 📌 Underperforming Pages (High Impressions, Low CTR < 4%)")
            under_mask = (
                (pages_df['impressions'] >= min_impressions) &
                (pages_df['ctr'] < 0.04)
            )
            sort_under = 'impressions' if 'impressions' in pages_df.columns else pages_df.columns[0]
            under_pages = pages_df[under_mask].sort_values(sort_under, ascending=False).head(15).reset_index(drop=True)

            if len(under_pages) > 0:
                under_pages.index = range(1, len(under_pages) + 1)
                st.dataframe(format_gsc_df_for_display(under_pages[p_cols]), use_container_width=True, height=280)
            else:
                st.info("No pages found with high impressions and CTR < 4%.")
