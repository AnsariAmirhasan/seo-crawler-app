"""
Unified GSC + GA4 Deep Intelligence Studio for CrawlPilot SEO Suite
===================================================================
Combines the real-time Google OAuth 2.0 API ingestion and period-over-period decay/GA4 AI audits
with the deep-dive Search Console analytical engine (Query-to-Page NLP mapping, Brand vs Non-Brand,
Striking Distance quick wins, CTR anomaly diagnosis, keyword cannibalization, questions intent,
traffic projection modeling, and complete executive Word (.DOCX) / Excel (.XLSX) strategy exports).
"""

import io
import re
import os
import json
import zipfile
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

try:
    import matplotlib.pyplot as plt
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    plt = None
    WordCloud = None
    WORDCLOUD_AVAILABLE = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import docx
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Google OAuth & API Libraries
try:
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.analytics.admin import AnalyticsAdminServiceClient
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    GOOGLE_OAUTH_LIBS_AVAILABLE = True
    GOOGLE_OAUTH_IMPORT_ERROR = None
except ImportError as _oauth_err:
    Flow = None
    build = None
    Credentials = None
    AnalyticsAdminServiceClient = None
    BetaAnalyticsDataClient = None
    DateRange = None
    Dimension = None
    Metric = None
    RunReportRequest = None
    GOOGLE_OAUTH_LIBS_AVAILABLE = False
    GOOGLE_OAUTH_IMPORT_ERROR = str(_oauth_err)

from full_site_seo_audit import (
    GOOGLE_OAUTH_SCOPES,
    get_oauth_config,
    create_oauth_flow,
    get_authenticated_credentials,
    fetch_live_gsc_properties,
    fetch_live_ga4_properties,
    fetch_live_ga4_traffic,
    get_date_bounds,
    clean_ctr_val,
    read_csv_robust,
    parse_gsc_and_ga4_upload,
    generate_mock_audit_dataset
)

from gsc_advanced_analyzer import (
    make_clean_export_filename,
    extract_csv_from_zip,
    standardize_columns,
    sanitize_dataframe,
    extract_base_domain,
    extract_brand_tokens,
    is_brand_query,
    map_queries_to_pages,
    generate_algorithmic_seo_suggestions,
    generate_ai_seo_action_plan,
    export_action_plan_to_excel,
    export_action_plan_to_docx,
    generate_sample_gsc_data
)


# ==============================================================================
# LIVE GOOGLE SEARCH CONSOLE MULTI-DIMENSIONAL FETCHER
# ==============================================================================

def fetch_live_unified_gsc_data(
    creds,
    site_url: str,
    curr_start: str,
    curr_end: str,
    prev_start: str,
    prev_end: str
) -> dict:
    """
    Fetches multi-dimensional performance intelligence directly from Google Search Console API:
    1. Query + Page (25,000 rows) for current period (powers NLP mapping, CTR anomalies, cannibalization)
    2. Page comparison (current vs previous period) to detect decaying pages (>25% click drops)
    3. Country dimension (1,000 rows)
    4. Device dimension (Desktop, Mobile, Tablet)
    """
    service = build('searchconsole', 'v1', credentials=creds, cache_discovery=False)
    
    # 1. Query + Page Dimensions
    q_body = {
        'startDate': curr_start,
        'endDate': curr_end,
        'dimensions': ['query', 'page'],
        'rowLimit': 25000
    }
    q_res = service.searchanalytics().query(siteUrl=site_url, body=q_body).execute()
    q_rows = q_res.get('rows', [])
    
    queries_list = []
    for r in q_rows:
        keys = r.get('keys', ['', ''])
        queries_list.append({
            'query': str(keys[0]) if len(keys) > 0 else '',
            'page': str(keys[1]) if len(keys) > 1 else '',
            'clicks': int(r.get('clicks', 0)),
            'impressions': int(r.get('impressions', 0)),
            'ctr': float(r.get('ctr', 0.0)),
            'position': round(float(r.get('position', 0.0)), 1)
        })
    queries_df = pd.DataFrame(queries_list)
    
    # 2. Pages Comparison for Content Decay
    p_curr_body = {
        'startDate': curr_start,
        'endDate': curr_end,
        'dimensions': ['page'],
        'rowLimit': 10000
    }
    p_curr_res = service.searchanalytics().query(siteUrl=site_url, body=p_curr_body).execute()
    p_curr_map = {
        r['keys'][0]: {'curr_clicks': int(r.get('clicks', 0)), 'curr_imp': int(r.get('impressions', 0))}
        for r in p_curr_res.get('rows', []) if r.get('keys')
    }
    
    p_prev_body = {
        'startDate': prev_start,
        'endDate': prev_end,
        'dimensions': ['page'],
        'rowLimit': 10000
    }
    p_prev_res = service.searchanalytics().query(siteUrl=site_url, body=p_prev_body).execute()
    p_prev_map = {
        r['keys'][0]: {'prev_clicks': int(r.get('clicks', 0)), 'prev_imp': int(r.get('impressions', 0))}
        for r in p_prev_res.get('rows', []) if r.get('keys')
    }
    
    all_pages = set(list(p_curr_map.keys()) + list(p_prev_map.keys()))
    pages_list = []
    decay_list = []
    
    for p in all_pages:
        curr_info = p_curr_map.get(p, {'curr_clicks': 0, 'curr_imp': 0})
        prev_info = p_prev_map.get(p, {'prev_clicks': 0, 'prev_imp': 0})
        c_clicks = curr_info['curr_clicks']
        p_clicks = prev_info['prev_clicks']
        c_imp = curr_info['curr_imp']
        p_imp = prev_info['prev_imp']
        
        pages_list.append({
            'page': p,
            'clicks': c_clicks,
            'impressions': c_imp,
            'ctr': round((c_clicks / c_imp), 4) if c_imp > 0 else 0.0,
            'prev_clicks': p_clicks,
            'prev_imp': p_imp
        })
        
        # Calculate decay
        if p_clicks >= 25:
            click_diff = c_clicks - p_clicks
            decay_pct = round((click_diff / p_clicks) * 100, 1)
            if decay_pct <= -25.0:
                decay_list.append({
                    'page': p,
                    'prev_clicks': p_clicks,
                    'curr_clicks': c_clicks,
                    'clicks_lost': abs(click_diff),
                    'decay_pct': decay_pct,
                    'prev_imp': p_imp,
                    'curr_imp': c_imp,
                    'status': 'CRITICAL DECAY' if decay_pct <= -40 else 'MODERATE DECAY'
                })
                
    pages_df = pd.DataFrame(pages_list)
    decay_df = pd.DataFrame(decay_list)
    if not decay_df.empty:
        decay_df = decay_df.sort_values(by='clicks_lost', ascending=False)
        
    # 3. Country Breakdown
    country_body = {
        'startDate': curr_start,
        'endDate': curr_end,
        'dimensions': ['country'],
        'rowLimit': 1000
    }
    try:
        c_res = service.searchanalytics().query(siteUrl=site_url, body=country_body).execute()
        countries_df = pd.DataFrame([{
            'country': r['keys'][0],
            'clicks': int(r.get('clicks', 0)),
            'impressions': int(r.get('impressions', 0)),
            'ctr': float(r.get('ctr', 0.0)),
            'position': round(float(r.get('position', 0.0)), 1)
        } for r in c_res.get('rows', []) if r.get('keys')])
    except Exception:
        countries_df = pd.DataFrame()

    # 4. Device Breakdown
    device_body = {
        'startDate': curr_start,
        'endDate': curr_end,
        'dimensions': ['device'],
        'rowLimit': 10
    }
    try:
        d_res = service.searchanalytics().query(siteUrl=site_url, body=device_body).execute()
        devices_df = pd.DataFrame([{
            'device': r['keys'][0],
            'clicks': int(r.get('clicks', 0)),
            'impressions': int(r.get('impressions', 0)),
            'ctr': float(r.get('ctr', 0.0)),
            'position': round(float(r.get('position', 0.0)), 1)
        } for r in d_res.get('rows', []) if r.get('keys')])
    except Exception:
        devices_df = pd.DataFrame()
        
    return {
        "queries": queries_df,
        "pages": pages_df,
        "decay_pages": decay_df,
        "countries": countries_df,
        "devices": devices_df,
        "date_range": f"{curr_start} to {curr_end}",
        "compare_range": f"{prev_start} to {prev_end}"
    }


# ==============================================================================
# AUDIT & SEO ANALYSIS ENGINE
# ==============================================================================

def run_unified_seo_intelligence(
    queries_df: pd.DataFrame,
    pages_df: pd.DataFrame,
    decay_df: pd.DataFrame = None,
    ga4_df: pd.DataFrame = None,
    base_domain: str = ""
) -> dict:
    """
    Executes unified algorithmic SEO intelligence:
    - Target URL mapping
    - Brand vs Non-brand breakdown
    - Striking distance quick wins (Pos 8-20)
    - CTR anomalies in Top 10 rankings
    - Keyword cannibalization (2+ URLs splitting traffic)
    - Informational questions
    - Organic health score computation
    """
    if queries_df.empty:
        return {}
        
    # Extract base domain if empty
    if not base_domain and not pages_df.empty and 'page' in pages_df.columns:
        first_valid_page = str(pages_df['page'].dropna().iloc[0])
        parsed = urllib.parse.urlparse(first_valid_page)
        base_domain = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else first_valid_page
        
    # Brand Token Extraction
    brand_tokens = extract_brand_tokens(base_domain)
    
    # Query NLP Mapping
    mapped_queries_df = map_queries_to_pages(queries_df, pages_df, base_domain=base_domain)
    mapped_queries_df['is_brand'] = mapped_queries_df['query'].apply(lambda q: is_brand_query(str(q), brand_tokens))
    
    # Brand vs Non-Brand Metrics
    brand_df = mapped_queries_df[mapped_queries_df['is_brand'] == True]
    non_brand_df = mapped_queries_df[mapped_queries_df['is_brand'] == False]
    
    total_clicks = int(mapped_queries_df['clicks'].sum()) if 'clicks' in mapped_queries_df.columns else 0
    total_impressions = int(mapped_queries_df['impressions'].sum()) if 'impressions' in mapped_queries_df.columns else 0
    avg_ctr = float(mapped_queries_df['ctr'].mean()) if 'ctr' in mapped_queries_df.columns else 0.0
    avg_pos = float(mapped_queries_df['position'].mean()) if 'position' in mapped_queries_df.columns else 0.0
    
    brand_clicks = int(brand_df['clicks'].sum()) if not brand_df.empty else 0
    non_brand_clicks = int(non_brand_df['clicks'].sum()) if not non_brand_df.empty else 0
    brand_ratio = round((brand_clicks / total_clicks * 100), 1) if total_clicks > 0 else 0.0
    
    # 1. Striking Distance Quick Wins (Pos 8 to 20, high impressions)
    striking_wins = mapped_queries_df[
        (mapped_queries_df['position'] >= 8.0) & 
        (mapped_queries_df['position'] <= 20.0)
    ].sort_values(by='impressions', ascending=False)
    
    # 2. Low-Hanging Fruit & CTR Anomalies (Pos <= 10, impressions >= 800, CTR < 2%)
    ctr_anomalies = mapped_queries_df[
        (mapped_queries_df['position'] <= 10.0) & 
        (mapped_queries_df['impressions'] >= 800) & 
        (mapped_queries_df['ctr'] < 0.02)
    ].sort_values(by='impressions', ascending=False)
    
    # 3. Keyword Cannibalization (Queries with multiple ranking URLs)
    cannibal_list = []
    if 'page' in queries_df.columns:
        query_groups = queries_df.groupby('query')
        for q, group in query_groups:
            uniq_pages = group['page'].dropna().unique()
            if len(uniq_pages) > 1 and group['impressions'].sum() >= 500:
                cannibal_list.append({
                    'query': q,
                    'url_count': len(uniq_pages),
                    'total_clicks': int(group['clicks'].sum()),
                    'total_impressions': int(group['impressions'].sum()),
                    'competing_urls': list(uniq_pages),
                    'best_rank': float(group['position'].min())
                })
    cannibal_df = pd.DataFrame(cannibal_list)
    if not cannibal_df.empty:
        cannibal_df = cannibal_df.sort_values(by='total_impressions', ascending=False)
        
    # 4. Questions & Search Intent Classification
    question_patterns = r'\b(how|what|why|where|when|who|can|which|is|are|guide|tutorial|vs|versus|best|review)\b'
    questions_df = mapped_queries_df[
        mapped_queries_df['query'].str.contains(question_patterns, case=False, na=False, regex=True)
    ].sort_values(by='impressions', ascending=False)
    
    # 5. Organic Health Score Calculation (0 to 100)
    score = 92
    if decay_df is not None and not decay_df.empty:
        score -= min(len(decay_df) * 4, 25)
    if not ctr_anomalies.empty:
        score -= min(len(ctr_anomalies) * 3, 18)
    if not cannibal_df.empty:
        score -= min(len(cannibal_df) * 3, 14)
    if brand_ratio > 75.0 and total_clicks > 100:
        score -= 10  # Excessive brand dependence
    final_score = max(min(score, 100), 38)
    
    return {
        "final_score": final_score,
        "base_domain": base_domain,
        "mapped_queries_df": mapped_queries_df,
        "striking_wins": striking_wins,
        "ctr_anomalies": ctr_anomalies,
        "cannibal_df": cannibal_df,
        "questions_df": questions_df,
        "brand_df": brand_df,
        "non_brand_df": non_brand_df,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr": avg_ctr,
        "avg_pos": avg_pos,
        "brand_clicks": brand_clicks,
        "non_brand_clicks": non_brand_clicks,
        "brand_ratio": brand_ratio
    }


# ==============================================================================
# MAIN PAGE RENDERER
# ==============================================================================

def render_unified_gsc_ga4_studio():
    """Renders the Unified GSC + GA4 Deep Intelligence Studio."""
    
    # 1. Cockpit Hero Banner matching CrawlPilot Engine
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(11, 20, 38, 0.92) 0%, rgba(6, 12, 24, 0.98) 100%); padding: 2.2rem 2.6rem; border-radius: 20px; border: 1px solid rgba(0, 240, 255, 0.22); margin-bottom: 1.5rem; box-shadow: 0 20px 50px rgba(0,0,0,0.7), 0 0 35px rgba(0, 240, 255, 0.08); position: relative; overflow: hidden; backdrop-filter: blur(20px);">
        <!-- Ambient Cyber Corner Glows -->
        <div style="position: absolute; top: -40px; right: 20%; width: 220px; height: 180px; background: radial-gradient(circle, rgba(0, 240, 255, 0.15) 0%, transparent 70%); pointer-events: none;"></div>
        <div style="position: absolute; bottom: -30px; left: 10%; width: 180px; height: 140px; background: radial-gradient(circle, rgba(45, 212, 191, 0.12) 0%, transparent 70%); pointer-events: none;"></div>
        
        <div style="position: relative; z-index: 2;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 1rem;">
                <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(16, 185, 129, 0.12); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.35); padding: 4px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; box-shadow: 0 0 12px rgba(16, 185, 129, 0.2);">
                    <span class="hud-beacon"></span> UNIFIED GSC + GA4 INTEL
                </div>
                <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(0, 240, 255, 0.12); color: #00F0FF; border: 1px solid rgba(0, 240, 255, 0.35); padding: 4px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; box-shadow: 0 0 12px rgba(0, 240, 255, 0.2);">
                    <span>⚡</span> ZERO MANUAL CSV REQUIRED (OAUTH 2.0)
                </div>
                <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(45, 212, 191, 0.12); color: #2DD4BF; border: 1px solid rgba(45, 212, 191, 0.35); padding: 4px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace;">
                    <span>🤖</span> AI CONTENT STRATEGY & EXPORT
                </div>
            </div>
            
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #00F0FF; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 6px;">
                QUANTUM GSC INTELLIGENCE • AUTOMATED INGESTION & AUDIT
            </div>
            
            <h1 style="font-family: 'Orbitron', 'Space Grotesk', sans-serif; font-size: 2.7rem; font-weight: 900; color: #FFFFFF; margin: 0 0 0.5rem 0; letter-spacing: -0.01em;">
                <span style="color: #FFFFFF; text-shadow: 0 0 30px rgba(255,255,255,0.4);">Unified</span> <span style="background: linear-gradient(135deg, #00F0FF 0%, #2DD4BF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 0 30px rgba(0, 240, 255, 0.45);">(GSC + GA4) Intelligence</span>
            </h1>
            
            <p style="color: #94A3B8; font-size: 0.98rem; max-width: 860px; margin: 0; line-height: 1.65; font-family: 'Space Grotesk', sans-serif;">
                Next-generation SEO command center combining <b>live Google OAuth 2.0 automatic ingestion</b> with <b>deep organic intelligence</b>: Period-over-period decaying pages, Query-to-Page NLP mapping, CTR anomalies in top ranks, striking-distance quick wins, keyword cannibalization, brand vs non-brand ratio, and client-ready Word (.DOCX) & Excel (.XLSX) strategy exports.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Data Acquisition Method (Live Google OAuth vs Manual Upload)
    data_source_mode = st.radio(
        "Select Acquisition Mode",
        options=[
            "🔗 Connect Live Google Account (Auto-Detect GSC & GA4 - Recommended)",
            "📁 Manual CSV / ZIP Upload (With 1-Click Demo Dataset)"
        ],
        horizontal=True,
        key="unified_data_source_radio"
    )

    client_id, client_secret, redirect_uri = get_oauth_config()
    raw_dataset = st.session_state.get("unified_raw_dataset")

    # --------------------------------------------------------------------------
    # MODE 1: LIVE GOOGLE OAUTH 2.0 INTEGRATION
    # --------------------------------------------------------------------------
    if "Connect Live Google Account" in data_source_mode:
        if not GOOGLE_OAUTH_LIBS_AVAILABLE:
            st.warning(
                f"⚠️ **Google OAuth packages are currently being configured or installing.**\n\n"
                f"Details: `{GOOGLE_OAUTH_IMPORT_ERROR}`\n\n"
                "You can switch to **'📁 Manual CSV / ZIP Upload'** above anytime to run your audit with exports or demo data!"
            )
        else:
            # Check callback
            auth_code = st.query_params.get("code")
            if auth_code and client_id and client_secret:
                with st.spinner("Exchanging OAuth authorization code with Google Cloud..."):
                    try:
                        flow = create_oauth_flow(client_id, client_secret, redirect_uri)
                        flow.fetch_token(code=auth_code)
                        flow_creds = flow.credentials
                        st.session_state["g_oauth_creds"] = {
                            "token": flow_creds.token,
                            "refresh_token": flow_creds.refresh_token,
                            "token_uri": flow_creds.token_uri,
                            "client_id": flow_creds.client_id,
                            "client_secret": flow_creds.client_secret,
                            "scopes": flow_creds.scopes
                        }
                        st.query_params.clear()
                        st.success("✅ Successfully connected to Google Account!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Authentication token exchange failed: {e}")

            active_creds = get_authenticated_credentials()

            if active_creds:
                # Live Connected Box
                st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(6, 12, 24, 0.9) 100%); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 14px; padding: 1.1rem 1.6rem; margin-bottom: 1.3rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span class="hud-beacon"></span>
                        <div>
                            <div style="color: #34D399; font-weight: 800; font-size: 1.05rem; font-family: 'Space Grotesk', sans-serif;">Live Google Account Connected</div>
                            <div style="color: #94A3B8; font-size: 0.82rem; font-family: 'Space Grotesk', sans-serif;">Direct API link active. Select your properties to pull fresh Search Console & GA4 intelligence.</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.spinner("Auto-detecting verified Search Console & GA4 properties..."):
                    gsc_properties = fetch_live_gsc_properties(active_creds)
                    ga4_properties = fetch_live_ga4_properties(active_creds)

                col_p1, col_p2, col_p3 = st.columns([1.8, 1.8, 1.2])
                with col_p1:
                    if gsc_properties:
                        selected_gsc_property = st.selectbox(
                            "Select GSC Property",
                            options=gsc_properties,
                            help="Choose your verified Search Console domain or URL-prefix property"
                        )
                    else:
                        st.warning("No verified Search Console properties found for this account.")
                        selected_gsc_property = None

                with col_p2:
                    ga4_options_labels = ["None (Skip GA4)"] + [p["label"] for p in ga4_properties]
                    selected_ga4_label = st.selectbox(
                        "Select GA4 Property (Optional)",
                        options=ga4_options_labels,
                        help="Auto-detects AI referral traffic (ChatGPT, Perplexity, Claude, Gemini)"
                    )
                    selected_ga4_id = None
                    if selected_ga4_label != "None (Skip GA4)":
                        for gp in ga4_properties:
                            if gp["label"] == selected_ga4_label:
                                selected_ga4_id = gp["id"]
                                break

                with col_p3:
                    date_range_choice = st.selectbox(
                        "Date Range",
                        options=[
                            "Last 3 Months (Recommended)",
                            "Last 28 Days",
                            "Last 6 Months",
                            "Custom"
                        ]
                    )

                custom_start, custom_end = None, None
                if date_range_choice == "Custom":
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        custom_start = st.date_input("Start Date", value=datetime.now() - timedelta(days=90))
                    with col_d2:
                        custom_end = st.date_input("End Date", value=datetime.now() - timedelta(days=3))

                btn_fetch_col, btn_logout_col = st.columns([3.5, 1.2])
                with btn_fetch_col:
                    btn_run_live = st.button("🚀 Fetch Live Google Intel & Run Deep Analysis", type="primary", use_container_width=True)
                with btn_logout_col:
                    if st.button("🔌 Disconnect Google", use_container_width=True):
                        st.session_state["g_oauth_creds"] = None
                        st.session_state["unified_raw_dataset"] = None
                        st.rerun()

                if btn_run_live and selected_gsc_property:
                    c_start, c_end, p_start, p_end = get_date_bounds(date_range_choice, custom_start, custom_end)
                    with st.spinner(f"Querying GSC API for queries, pages & period-over-period comparison ({c_start} vs {p_start})..."):
                        try:
                            gsc_live_dict = fetch_live_unified_gsc_data(
                                active_creds,
                                selected_gsc_property,
                                c_start,
                                c_end,
                                p_start,
                                p_end
                            )
                            live_ga4 = pd.DataFrame()
                            if selected_ga4_id:
                                with st.spinner("Querying GA4 Data API for AI referrals and user engagement..."):
                                    live_ga4 = fetch_live_ga4_traffic(active_creds, selected_ga4_id, c_start, c_end)

                            st.session_state["unified_raw_dataset"] = {
                                "queries": gsc_live_dict["queries"],
                                "pages": gsc_live_dict["pages"],
                                "decay_pages": gsc_live_dict["decay_pages"],
                                "countries": gsc_live_dict["countries"],
                                "devices": gsc_live_dict["devices"],
                                "ga4": live_ga4,
                                "is_live_oauth": True,
                                "property_gsc": selected_gsc_property,
                                "property_ga4": selected_ga4_id or "None",
                                "date_range": f"{c_start} to {c_end}"
                            }
                            st.success(f"✅ Live Intel Synced! Fetched **{len(gsc_live_dict['queries'])} queries** and **{len(gsc_live_dict['pages'])} pages** for `{selected_gsc_property}`.")
                            st.rerun()
                        except Exception as live_err:
                            st.error(f"Failed to fetch live Google API data: {live_err}")

            else:
                # Login Card
                st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(11, 20, 38, 0.92) 0%, rgba(6, 12, 24, 0.98) 100%); border: 1px solid rgba(0, 240, 255, 0.22); border-radius: 16px; padding: 1.6rem 2rem; margin-bottom: 1.3rem; box-shadow: 0 15px 35px rgba(0,0,0,0.65), 0 0 25px rgba(0, 240, 255, 0.08); backdrop-filter: blur(20px);">
                    <div style="font-family: 'Space Grotesk', sans-serif; font-weight: 800; color: #FFFFFF; font-size: 1.25rem; margin-bottom: 6px; display: flex; align-items: center; gap: 10px;">
                        <span style="color: #00F0FF; font-size: 1.3rem;">🔗</span> Connect Your Google Account
                    </div>
                    <div style="color: #94A3B8; font-size: 0.92rem; line-height: 1.6; font-family: 'Space Grotesk', sans-serif;">
                        One-click sign in with Google OAuth 2.0 (Looker Studio / Data Studio style). Auto-discovers your verified Search Console domains and GA4 properties so you never have to download or upload CSV/ZIP files again.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander("⚙️ Configure Google OAuth Credentials (If not using st.secrets)", expanded=(not client_id or not client_secret)):
                    st.caption("Provide your OAuth 2.0 Web Client ID & Secret from Google Cloud Console.")
                    ui_cid = st.text_input("Client ID", value=client_id, placeholder="xxxx.apps.googleusercontent.com", key="unified_ui_oauth_cid")
                    ui_csec = st.text_input("Client Secret", value=client_secret, type="password", placeholder="GOCSPX-xxxx", key="unified_ui_oauth_csec")
                    ui_ruri = st.text_input("Authorized Redirect URI", value=redirect_uri, key="unified_ui_oauth_ruri")
                    if ui_cid:
                        st.session_state["oauth_custom_client_id"] = ui_cid.strip()
                        client_id = ui_cid.strip()
                    if ui_csec:
                        st.session_state["oauth_custom_client_secret"] = ui_csec.strip()
                        client_secret = ui_csec.strip()
                    if ui_ruri:
                        st.session_state["oauth_custom_redirect_uri"] = ui_ruri.strip()
                        redirect_uri = ui_ruri.strip()

                if client_id and client_secret:
                    try:
                        auth_flow = create_oauth_flow(client_id, client_secret, redirect_uri)
                        auth_url, _ = auth_flow.authorization_url(prompt='consent', access_type='offline', include_granted_scopes='true')
                        st.link_button(
                            "🔗 Sign In With Google (Connect GSC & GA4 Live)",
                            url=auth_url,
                            use_container_width=True,
                            type="primary"
                        )
                    except Exception as flow_err:
                        st.error(f"Could not initialize Google OAuth flow: {flow_err}")
                else:
                    st.info("💡 To connect live with Google, enter your Client ID & Secret in the box above or configure `.streamlit/secrets.toml`.")

    # --------------------------------------------------------------------------
    # MODE 2: MANUAL CSV / ZIP UPLOAD & DEMO DATASET
    # --------------------------------------------------------------------------
    else:
        col_up1, col_up2 = st.columns([3.5, 1.5])
        with col_up1:
            uploaded_files = st.file_uploader(
                "Upload Google Search Console Export (ZIP / CSV) & GA4 Export:",
                type=["zip", "csv"],
                accept_multiple_files=True,
                help="Upload a standard GSC ZIP export, or separate Queries.csv and Pages.csv."
            )
        with col_up2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🧪 Load Industrial Demo Dataset", use_container_width=True, help="Load complete industrial GSC + GA4 dataset to test all features instantly"):
                mock_res = generate_mock_audit_dataset(domain_name="yukonvalve.com")
                st.session_state["unified_raw_dataset"] = {
                    "queries": mock_res["queries"],
                    "pages": mock_res["pages"],
                    "decay_pages": pd.DataFrame([
                        {"page": "https://yukonvalve.com/product-category/ball-valve/", "prev_clicks": 1450, "curr_clicks": 920, "clicks_lost": 530, "decay_pct": -36.5, "status": "CRITICAL DECAY"},
                        {"page": "https://yukonvalve.com/product/pneumatic-actuator-butterfly-valve/", "prev_clicks": 890, "curr_clicks": 540, "clicks_lost": 350, "decay_pct": -39.3, "status": "CRITICAL DECAY"},
                        {"page": "https://yukonvalve.com/product-category/gate-valve/", "prev_clicks": 620, "curr_clicks": 410, "clicks_lost": 210, "decay_pct": -33.8, "status": "MODERATE DECAY"},
                    ]),
                    "countries": pd.DataFrame([
                        {"country": "usa", "clicks": 2840, "impressions": 65000, "ctr": 0.043, "position": 8.4},
                        {"country": "ind", "clicks": 1420, "impressions": 42000, "ctr": 0.033, "position": 9.1},
                        {"country": "gbr", "clicks": 750, "impressions": 18000, "ctr": 0.041, "position": 7.8},
                        {"country": "deu", "clicks": 420, "impressions": 11000, "ctr": 0.038, "position": 10.2},
                    ]),
                    "devices": pd.DataFrame([
                        {"device": "DESKTOP", "clicks": 3480, "impressions": 78000, "ctr": 0.044, "position": 7.9},
                        {"device": "MOBILE", "clicks": 2150, "impressions": 58000, "ctr": 0.037, "position": 9.8},
                        {"device": "TABLET", "clicks": 180, "impressions": 4200, "ctr": 0.042, "position": 8.1},
                    ]),
                    "ga4": mock_res["ga4"],
                    "is_live_oauth": False,
                    "is_mock": True,
                    "property_gsc": "https://yukonvalve.com",
                    "property_ga4": "Yukon Valve Global GA4",
                    "date_range": "Last 90 Days"
                }
                st.rerun()

        if uploaded_files:
            parsed_dfs = parse_gsc_and_ga4_upload(uploaded_files)
            if not parsed_dfs["queries"].empty:
                st.session_state["unified_raw_dataset"] = {
                    "queries": parsed_dfs["queries"],
                    "pages": parsed_dfs["pages"],
                    "decay_pages": pd.DataFrame(),
                    "countries": pd.DataFrame(),
                    "devices": pd.DataFrame(),
                    "ga4": parsed_dfs["ga4"],
                    "is_live_oauth": False,
                    "is_mock": False,
                    "property_gsc": "Uploaded Files",
                    "property_ga4": "Uploaded Files",
                    "date_range": "Uploaded Period"
                }
                st.success("✅ Files processed successfully!")
                st.rerun()

    # --------------------------------------------------------------------------
    # DATA PROCESSING & UNIFIED DASHBOARD
    # --------------------------------------------------------------------------
    raw_data = st.session_state.get("unified_raw_dataset")
    if not raw_data or raw_data.get("queries") is None or raw_data["queries"].empty:
        st.markdown("""
        <div style="background: rgba(11, 20, 38, 0.6); border: 1px dashed rgba(0, 240, 255, 0.25); border-radius: 16px; padding: 2.8rem 2rem; text-align: center; margin-top: 1.5rem;">
            <div style="font-size: 3rem; margin-bottom: 0.8rem;">⚡</div>
            <h3 style="color: #FFFFFF; font-weight: 800; margin-bottom: 0.5rem; font-family: 'Space Grotesk', sans-serif;">Awaiting Google Search Console Intelligence</h3>
            <p style="color: #94A3B8; font-size: 0.98rem; max-width: 620px; margin: 0 auto 1.5rem; line-height: 1.6; font-family: 'Space Grotesk', sans-serif;">
                Click <b>'Sign In With Google'</b> above for instant automatic analysis without downloading CSV files, or click <b>'Load Industrial Demo Dataset'</b> to inspect the full suite with live interactive charts immediately.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    queries_df = raw_data["queries"]
    pages_df = raw_data.get("pages", pd.DataFrame())
    decay_df = raw_data.get("decay_pages", pd.DataFrame())
    countries_df = raw_data.get("countries", pd.DataFrame())
    devices_df = raw_data.get("devices", pd.DataFrame())
    ga4_df = raw_data.get("ga4", pd.DataFrame())
    
    # Run Unified SEO Analytics
    with st.spinner("Executing Quantum NLP query mapping, CTR anomaly modeling, and cannibalization detection..."):
        analysis = run_unified_seo_intelligence(
            queries_df=queries_df,
            pages_df=pages_df,
            decay_df=decay_df,
            ga4_df=ga4_df,
            base_domain=raw_data.get("property_gsc", "")
        )

    score = analysis["final_score"]
    score_color = "#34D399" if score >= 80 else ("#FBBF24" if score >= 60 else "#FF6B4A")
    source_tag = "LIVE GSC + GA4 API" if raw_data.get("is_live_oauth") else ("SAMPLE DEMO DATA" if raw_data.get("is_mock") else "UPLOADED EXPORT DATA")
    prop_info = f" • Property: <b>{raw_data.get('property_gsc')}</b>" if raw_data.get("property_gsc") else ""

    # Executive Verdict Banner
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(11, 20, 38, 0.92) 0%, rgba(6, 12, 24, 0.98) 100%); border: 1px solid rgba(0, 240, 255, 0.22); border-radius: 18px; padding: 1.8rem 2.2rem; margin: 1.5rem 0; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 24px; box-shadow: 0 20px 45px rgba(0,0,0,0.7), 0 0 30px rgba(0, 240, 255, 0.08); backdrop-filter: blur(20px);">
        <div style="flex: 2; min-width: 290px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <span style="background: rgba(0, 240, 255, 0.12); color: #00F0FF; border: 1px solid rgba(0, 240, 255, 0.35); padding: 3px 10px; border-radius: 9999px; font-size: 0.68rem; font-weight: 700; font-family: 'JetBrains Mono', monospace;">{source_tag}</span>
                <span style="color: #94A3B8; font-size: 0.8rem; font-family: 'JetBrains Mono', monospace;">{prop_info} ({raw_data.get('date_range')})</span>
            </div>
            <div style="font-family: 'Space Grotesk', sans-serif; font-size: 1.45rem; font-weight: 800; color: #FFFFFF;">
                🏛️ Executive Audit Verdict: <span style="color: {score_color};">{ 'ORGANIC SEARCH HEALTHY & PRIMED FOR EXPANSION' if score >= 80 else 'ACTION REQUIRED: TRAFFIC LOSS & CTR LEAKAGE DETECTED' }</span>
            </div>
            <div style="color: #94A3B8; font-size: 0.94rem; margin-top: 8px; line-height: 1.6; font-family: 'Space Grotesk', sans-serif;">
                Analyzing <b style="color: #F8FAFC;">{len(queries_df):,} total queries</b> & <b style="color: #F8FAFC;">{len(pages_df):,} landing pages</b>. Detected <b style="color: #F8FAFC;">{len(decay_df):,} decaying pages</b>, <b style="color: #F8FAFC;">{len(analysis['ctr_anomalies']):,} CTR anomalies</b> in top ranks, and <b style="color: #F8FAFC;">{len(analysis['striking_wins']):,} striking-distance keywords</b> ready for Page 1 acceleration.
            </div>
        </div>
        <div style="text-align: right; background: rgba(8, 14, 28, 0.9); padding: 14px 28px; border-radius: 14px; border: 1px solid rgba(0, 240, 255, 0.2); box-shadow: inset 0 0 15px rgba(0, 240, 255, 0.05);">
            <div style="font-size: 0.7rem; color: #94A3B8; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 0.1em;">Organic Health Score</div>
            <div style="font-family: 'Orbitron', monospace; font-size: 2.8rem; font-weight: 900; color: {score_color}; line-height: 1.1; text-shadow: 0 0 20px {score_color}60;">
                {score}<span style="font-size: 1.1rem; color: #64748B;">/100</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 6 Futuristic HUD KPI Telemetry Cards
    st.markdown(f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 1.6rem;">
        <!-- 1. Decaying Pages -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">📉</div>
                <span class="kpi-badge kpi-badge-red">>25% Loss</span>
            </div>
            <div class="kpi-label">DECAYING PAGES</div>
            <div class="kpi-value" style="color: #FF6B4A; text-shadow: 0 0 20px rgba(255, 107, 74, 0.45);">{len(decay_df)}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 50%; background: #FF6B4A; box-shadow: 0 0 10px #FF6B4A;"></div></div>
        </div>
        
        <!-- 2. Striking Distance -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">⚡</div>
                <span class="kpi-badge kpi-badge-cyan">Pos 8-20</span>
            </div>
            <div class="kpi-label">STRIKING DISTANCE</div>
            <div class="kpi-value" style="color: #00F0FF; text-shadow: 0 0 20px rgba(0, 240, 255, 0.45);">{len(analysis['striking_wins'])}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 65%; background: #00F0FF; box-shadow: 0 0 10px #00F0FF;"></div></div>
        </div>

        <!-- 3. CTR Anomalies -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">🎯</div>
                <span class="kpi-badge kpi-badge-amber">CTR &lt; 2%</span>
            </div>
            <div class="kpi-label">CTR ANOMALIES</div>
            <div class="kpi-value" style="color: #FBBF24; text-shadow: 0 0 20px rgba(251, 191, 36, 0.45);">{len(analysis['ctr_anomalies'])}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 45%; background: #FBBF24; box-shadow: 0 0 10px #FBBF24;"></div></div>
        </div>

        <!-- 4. Cannibalization -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">⚔️</div>
                <span class="kpi-badge kpi-badge-red">Multi-URL</span>
            </div>
            <div class="kpi-label">CANNIBALIZATION</div>
            <div class="kpi-value" style="color: #F87171; text-shadow: 0 0 20px rgba(248, 113, 113, 0.45);">{len(analysis['cannibal_df'])}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 40%; background: #F87171; box-shadow: 0 0 10px #F87171;"></div></div>
        </div>

        <!-- 5. GA4 AI Referrals -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">🤖</div>
                <span class="kpi-badge kpi-badge-teal">ChatGPT/Perplexity</span>
            </div>
            <div class="kpi-label">GA4 AI SESSIONS</div>
            <div class="kpi-value" style="color: #2DD4BF; text-shadow: 0 0 20px rgba(45, 212, 191, 0.45);">{int(ga4_df['sessions'].sum()) if not ga4_df.empty and 'sessions' in ga4_df.columns else 0}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 55%; background: #2DD4BF; box-shadow: 0 0 10px #2DD4BF;"></div></div>
        </div>

        <!-- 6. Brand vs Non-Brand -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">🏷️</div>
                <span class="kpi-badge kpi-badge-green">{analysis['brand_ratio']}% Brand</span>
            </div>
            <div class="kpi-label">NON-BRAND CLICKS</div>
            <div class="kpi-value" style="color: #34D399; text-shadow: 0 0 20px rgba(52, 211, 153, 0.45);">{analysis['non_brand_clicks']:,}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: {min(100 - analysis['brand_ratio'], 100)}%; background: #34D399; box-shadow: 0 0 10px #34D399;"></div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # UNIFIED FLOATING TABS RIBBON
    # --------------------------------------------------------------------------
    tab_ai, tab_decay, tab_qw, tab_ctr, tab_cannibal, tab_quest, tab_pot, tab_ga4, tab_map, tab_geo, tab_cloud = st.tabs([
        "🤖 AI SEO Action Plan",
        "📉 Decaying Pages",
        "⚡ Quick Wins (Pos 8-20)",
        "🍎 CTR Anomalies",
        "⚔️ Cannibalization",
        "❓ Questions & Intent",
        "📈 Traffic Forecaster",
        "🤖 GA4 AI Referrals",
        "🗺️ Query-to-Page Mapping",
        "🌍 Countries & Devices",
        "☁️ Keyword Cloud"
    ])

    saved_domain = analysis["base_domain"] or "https://example.com"

    # --------------------------------------------------------------------------
    # TAB 1: AI SEO ACTION PLAN
    # --------------------------------------------------------------------------
    with tab_ai:
        st.markdown("### 🤖 Automated AI Action Plan & Strategy Generator")
        st.caption("Generate complete Page-by-Page Title, H1, Meta Description recommendations, and download a client-ready Word (.DOCX) or Excel (.XLSX) strategy document.")
        
        c_ai1, c_ai2, c_ai3 = st.columns([2.5, 1.5, 1.2])
        with c_ai1:
            gen_model_choice = st.selectbox(
                "Generation Strategy Engine",
                options=[
                    "Algorithmic SEO Engine (Instant, No API Key Required)",
                    "Google Gemini API (Generative Reasoning)",
                    "OpenAI GPT-4o Mini (Advanced Copywriting)"
                ],
                key="unified_action_engine"
            )
        with c_ai2:
            custom_key = st.text_input("API Key (If using Gemini / OpenAI)", type="password", key="unified_ai_key")
        with c_ai3:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            btn_gen_plan = st.button("✨ Generate Full Plan", type="primary", use_container_width=True)

        if btn_gen_plan or "unified_action_plan_data" not in st.session_state:
            with st.spinner("Synthesizing query mappings, striking wins, and decaying pages into action plan..."):
                algo_items = generate_algorithmic_seo_suggestions(
                    queries_df=analysis["mapped_queries_df"],
                    pages_df=pages_df,
                    base_domain=saved_domain
                )
                if "Gemini" in gen_model_choice and custom_key:
                    final_plan = generate_ai_seo_action_plan(algo_items, api_key=custom_key, provider="gemini", model="gemini-1.5-flash")
                elif "OpenAI" in gen_model_choice and custom_key:
                    final_plan = generate_ai_seo_action_plan(algo_items, api_key=custom_key, provider="openai", model="gpt-4o-mini")
                else:
                    final_plan = algo_items
                st.session_state["unified_action_plan_data"] = final_plan

        plan_items = st.session_state.get("unified_action_plan_data", [])
        if plan_items:
            plan_df = pd.DataFrame(plan_items)
            plan_df.index = range(1, len(plan_df) + 1)
            
            # Export Buttons
            exp_c1, exp_c2, exp_c3 = st.columns([1.5, 1.5, 1])
            with exp_c1:
                docx_bytes = export_action_plan_to_docx(plan_df, base_domain=saved_domain)
                st.download_button(
                    "📄 Download Strategy Document (.DOCX)",
                    data=docx_bytes,
                    file_name=make_clean_export_filename("SEO_Action_Plan_Document", saved_domain, "docx"),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="unified_dl_docx",
                    use_container_width=True
                )
            with exp_c2:
                xlsx_bytes = export_action_plan_to_excel(plan_df)
                st.download_button(
                    "📊 Download Multi-Tab Excel (.XLSX)",
                    data=xlsx_bytes,
                    file_name=make_clean_export_filename("SEO_Action_Plan_Workbook", saved_domain, "xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="unified_dl_xlsx",
                    use_container_width=True
                )
            with exp_c3:
                csv_bytes = plan_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Export CSV",
                    data=csv_bytes,
                    file_name=make_clean_export_filename("SEO_Action_Plan", saved_domain, "csv"),
                    mime="text/csv",
                    key="unified_dl_csv",
                    use_container_width=True
                )
                
            st.dataframe(
                plan_df,
                column_config={
                    "page": st.column_config.LinkColumn("Landing Page URL"),
                    "action_priority": st.column_config.TextColumn("Priority"),
                    "strategic_focus": st.column_config.TextColumn("Strategic Focus"),
                    "primary_target_keyword": st.column_config.TextColumn("Primary Keyword"),
                    "recommended_title": st.column_config.TextColumn("Optimized Title"),
                    "recommended_h1": st.column_config.TextColumn("Optimized H1"),
                    "recommended_meta_description": st.column_config.TextColumn("Optimized Meta Description")
                },
                use_container_width=True
            )

    # --------------------------------------------------------------------------
    # TAB 2: DECAYING PAGES
    # --------------------------------------------------------------------------
    with tab_decay:
        st.markdown("### 📉 Content Decay Audit (Period-Over-Period Click Losses)")
        st.caption("Identifies URLs whose search clicks dropped significantly (>25%). Recovering these pages yields the fastest ROI.")
        if decay_df is not None and not decay_df.empty:
            st.dataframe(
                decay_df,
                column_config={
                    "page": st.column_config.LinkColumn("Decaying Page URL"),
                    "prev_clicks": st.column_config.NumberColumn("Previous Clicks"),
                    "curr_clicks": st.column_config.NumberColumn("Current Clicks"),
                    "clicks_lost": st.column_config.NumberColumn("Clicks Lost", format="-%d"),
                    "decay_pct": st.column_config.NumberColumn("Loss %", format="%.1f%%"),
                    "status": st.column_config.TextColumn("Severity")
                },
                use_container_width=True
            )
        else:
            st.info("✅ No severe content decay (>25% drop) detected for this date range, or period comparison data is not provided.")

    # --------------------------------------------------------------------------
    # TAB 3: QUICK WINS & STRIKING DISTANCE
    # --------------------------------------------------------------------------
    with tab_qw:
        st.markdown("### ⚡ Striking Distance Quick Wins (Positions 8 to 20)")
        st.caption("Keywords ranking at the bottom of Page 1 or on Page 2 with massive impression volume. Push these to Top 3 with internal links and refreshed content.")
        if not analysis["striking_wins"].empty:
            st.dataframe(
                analysis["striking_wins"][['query', 'page', 'clicks', 'impressions', 'ctr', 'position']].head(100),
                column_config={
                    "page": st.column_config.LinkColumn("Target Page URL"),
                    "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                    "position": st.column_config.NumberColumn("Rank", format="%.1f")
                },
                use_container_width=True
            )
        else:
            st.info("No striking distance queries found in positions 8 to 20.")

    # --------------------------------------------------------------------------
    # TAB 4: CTR ANOMALIES
    # --------------------------------------------------------------------------
    with tab_ctr:
        st.markdown("### 🍎 CTR Anomalies & Low-Hanging Fruits")
        st.caption("Keywords already ranking in Top 10 with high search impressions but sub-par CTR (< 2%). Rewriting the Meta Title & Description will instantly drive clicks.")
        if not analysis["ctr_anomalies"].empty:
            st.dataframe(
                analysis["ctr_anomalies"][['query', 'page', 'clicks', 'impressions', 'ctr', 'position']].head(100),
                column_config={
                    "page": st.column_config.LinkColumn("Target Page URL"),
                    "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                    "position": st.column_config.NumberColumn("Rank", format="%.1f")
                },
                use_container_width=True
            )
        else:
            st.info("No severe CTR anomalies detected in top 10 positions.")

    # --------------------------------------------------------------------------
    # TAB 5: KEYWORD CANNIBALIZATION
    # --------------------------------------------------------------------------
    with tab_cannibal:
        st.markdown("### ⚔️ Keyword Cannibalization Audit")
        st.caption("Queries where multiple pages from your domain are competing in Google's index, dividing link equity and hurting rankings.")
        if not analysis["cannibal_df"].empty:
            st.dataframe(
                analysis["cannibal_df"],
                column_config={
                    "query": st.column_config.TextColumn("Cannibalized Query"),
                    "url_count": st.column_config.NumberColumn("Competing URLs Count"),
                    "total_clicks": st.column_config.NumberColumn("Combined Clicks"),
                    "total_impressions": st.column_config.NumberColumn("Combined Impressions"),
                    "best_rank": st.column_config.NumberColumn("Highest Rank", format="%.1f")
                },
                use_container_width=True
            )
        else:
            st.info("✅ No keyword cannibalization detected across primary query clusters.")

    # --------------------------------------------------------------------------
    # TAB 6: QUESTIONS & SEARCH INTENT
    # --------------------------------------------------------------------------
    with tab_quest:
        st.markdown("### ❓ Informational Questions & Intent Opportunities")
        st.caption("Discovers question-based queries (how, what, why, guide, best, vs) suitable for FAQ schema, blog guides, and Featured Snippets.")
        if not analysis["questions_df"].empty:
            st.dataframe(
                analysis["questions_df"][['query', 'page', 'clicks', 'impressions', 'ctr', 'position']].head(100),
                column_config={
                    "page": st.column_config.LinkColumn("Page URL"),
                    "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                    "position": st.column_config.NumberColumn("Rank", format="%.1f")
                },
                use_container_width=True
            )
        else:
            st.info("No question queries identified in this dataset.")

    # --------------------------------------------------------------------------
    # TAB 7: TRAFFIC POTENTIAL FORECASTER
    # --------------------------------------------------------------------------
    with tab_pot:
        st.markdown("### 📈 Organic Traffic Potential Forecaster")
        st.caption("Simulates monthly traffic uplift if keywords in positions 4-20 are promoted to Position #1 (30% CTR), Position #3 (10% CTR), or Position #5 (5% CTR).")
        pot_df = analysis["mapped_queries_df"][analysis["mapped_queries_df"]['position'] > 3.0].copy()
        if not pot_df.empty:
            pot_df['est_clicks_pos_1'] = (pot_df['impressions'] * 0.30).astype(int)
            pot_df['est_clicks_pos_3'] = (pot_df['impressions'] * 0.10).astype(int)
            pot_df['potential_gain_pos_1'] = pot_df['est_clicks_pos_1'] - pot_df['clicks']
            pot_df = pot_df.sort_values(by='potential_gain_pos_1', ascending=False)
            
            p_c1, p_c2 = st.columns(2)
            with p_c1:
                st.metric("Total Monthly Potential Gain (If #1)", f"+{pot_df['potential_gain_pos_1'].sum():,} clicks")
            with p_c2:
                st.metric("Total Current Clicks on Candidates", f"{pot_df['clicks'].sum():,} clicks")
                
            st.dataframe(
                pot_df[['query', 'page', 'position', 'clicks', 'impressions', 'est_clicks_pos_1', 'potential_gain_pos_1']].head(100),
                column_config={
                    "page": st.column_config.LinkColumn("Page URL"),
                    "position": st.column_config.NumberColumn("Current Rank", format="%.1f"),
                    "est_clicks_pos_1": st.column_config.NumberColumn("Projected #1 Clicks"),
                    "potential_gain_pos_1": st.column_config.NumberColumn("Net Clicks Gain", format="+%d")
                },
                use_container_width=True
            )

    # --------------------------------------------------------------------------
    # TAB 8: GA4 AI REFERRAL TRAFFIC
    # --------------------------------------------------------------------------
    with tab_ga4:
        st.markdown("### 🤖 GA4 AI Referral Traffic (ChatGPT, Perplexity, Claude, Gemini)")
        st.caption("Identifies referral traffic coming from generative AI engines and chatbots.")
        if not ga4_df.empty:
            st.dataframe(ga4_df, use_container_width=True)
        else:
            st.info("ℹ️ Select a connected GA4 property during Google login to pull live AI referral traffic, or load the demo dataset to preview.")

    # --------------------------------------------------------------------------
    # TAB 9: QUERY-TO-PAGE URL MAPPING
    # --------------------------------------------------------------------------
    with tab_map:
        st.markdown("### 🗺️ Full Query-to-Page NLP Target URL Mapping")
        st.caption("Every query mapped to its most relevant landing page with brand recognition.")
        st.dataframe(
            analysis["mapped_queries_df"][['query', 'page', 'is_brand', 'clicks', 'impressions', 'ctr', 'position']].head(200),
            column_config={
                "page": st.column_config.LinkColumn("Mapped Page URL"),
                "is_brand": st.column_config.CheckboxColumn("Brand Query"),
                "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                "position": st.column_config.NumberColumn("Rank", format="%.1f")
            },
            use_container_width=True
        )

    # --------------------------------------------------------------------------
    # TAB 10: COUNTRIES & DEVICES
    # --------------------------------------------------------------------------
    with tab_geo:
        st.markdown("### 🌍 Geographic & Device Performance Breakdown")
        cg1, cg2 = st.columns(2)
        with cg1:
            st.markdown("#### 🗺️ Top Countries")
            if not countries_df.empty:
                st.dataframe(countries_df.head(20), use_container_width=True)
            else:
                st.info("No country breakdown data available for this query.")
        with cg2:
            st.markdown("#### 📱 Device Share")
            if not devices_df.empty:
                st.dataframe(devices_df, use_container_width=True)
            else:
                st.info("No device breakdown data available for this query.")

    # --------------------------------------------------------------------------
    # TAB 11: KEYWORD WORD CLOUD
    # --------------------------------------------------------------------------
    with tab_cloud:
        st.markdown("### ☁️ Keyword Term Distribution")
        all_query_text = " ".join(analysis["mapped_queries_df"]['query'].dropna().astype(str).tolist())
        if WORDCLOUD_AVAILABLE and WordCloud and all_query_text:
            wc = WordCloud(
                width=1000, 
                height=450, 
                background_color='#060C18', 
                colormap='winter',
                max_words=120
            ).generate(all_query_text)
            
            fig, ax = plt.subplots(figsize=(10, 4.5), facecolor='#060C18')
            ax.imshow(wc, interpolation='bilinear')
            ax.axis('off')
            plt.tight_layout(pad=0)
            st.pyplot(fig)
        else:
            st.info("WordCloud library is optional. Viewing query frequency preview:")
            top_words = pd.Series(all_query_text.lower().split()).value_counts().head(30)
            st.bar_chart(top_words)
