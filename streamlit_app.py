import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET

from crawler import SEOSpider, USER_AGENTS, normalize_url
from seo_analyzer import analyze_crawl_results, parse_page_seo
from visualizer import (
    create_health_gauge,
    create_status_code_chart,
    create_issues_bar_chart,
    create_site_architecture_graph
)
from exporter import generate_excel_report, generate_csv

# 1. Streamlit Page Configuration - Must be first
st.set_page_config(
    page_title="Amir's SEO Spider | Unlimited Technical SEO Audit",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Modern Universal Theme Styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Header Container */
.main-header {
    background: radial-gradient(130% 120% at 50% -10%, #2A2568 0%, #131A33 50%, #0A0D18 100%);
    padding: 2.2rem 2.5rem;
    border-radius: 18px;
    margin-bottom: 1.8rem;
    border: 1px solid rgba(99, 102, 241, 0.35);
    box-shadow: 0 16px 40px -10px rgba(0, 0, 0, 0.6), inset 0 1px 0 0 rgba(255, 255, 255, 0.12);
    position: relative;
    overflow: hidden;
}
.header-badge-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 0.75rem;
}
.header-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(99, 102, 241, 0.18);
    color: #A5B4FC;
    border: 1px solid rgba(129, 140, 248, 0.4);
    padding: 5px 14px;
    border-radius: 9999px;
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.live-indicator-dot {
    width: 8px;
    height: 8px;
    background-color: #10B981;
    border-radius: 50%;
    box-shadow: 0 0 10px #10B981;
    display: inline-block;
}
.main-title {
    font-size: 2.35rem;
    font-weight: 800;
    background: linear-gradient(135deg, #FFFFFF 20%, #E0E7FF 60%, #A5B4FC 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    letter-spacing: -0.025em;
    line-height: 1.2;
}
.main-subtitle {
    color: #94A3B8;
    font-size: 1.02rem;
    margin-top: 8px;
    margin-bottom: 0;
    line-height: 1.5;
    max-width: 850px;
}
.header-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 1.2rem;
}
.header-pill {
    font-size: 0.82rem;
    padding: 5px 12px;
    border-radius: 8px;
    background: rgba(30, 41, 59, 0.75);
    color: #E2E8F0;
    border: 1px solid rgba(71, 85, 105, 0.45);
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* Modern Tab Styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background-color: rgba(15, 23, 42, 0.75);
    padding: 7px;
    border-radius: 14px;
    border: 1px solid rgba(51, 65, 85, 0.6);
    backdrop-filter: blur(12px);
    margin-bottom: 1.5rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    padding: 8px 18px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    color: #94A3B8 !important;
    border: none !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #FFFFFF !important;
    background: rgba(51, 65, 85, 0.45) !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%) !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 16px rgba(79, 70, 229, 0.45) !important;
}

/* KPI Metric Cards */
.kpi-card {
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.75) 0%, rgba(15, 23, 42, 0.9) 100%);
    padding: 1.3rem 1.4rem;
    border-radius: 14px;
    border: 1px solid rgba(51, 65, 85, 0.65);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    position: relative;
    overflow: hidden;
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    border-color: rgba(99, 102, 241, 0.6);
}
.kpi-card-topbar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3.5px;
}
.kpi-title {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #94A3B8;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.kpi-num {
    font-size: 2.1rem;
    font-weight: 800;
    letter-spacing: -0.025em;
    margin-top: 0.4rem;
    color: #FFFFFF;
}
.kpi-sub {
    font-size: 0.8rem;
    color: #64748B;
    margin-top: 0.25rem;
}

/* Hero Feature Cards */
.feature-card {
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.55) 0%, rgba(15, 23, 42, 0.85) 100%);
    padding: 1.6rem;
    border-radius: 14px;
    border: 1px solid rgba(51, 65, 85, 0.55);
    height: 100%;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.feature-card:hover {
    transform: translateY(-4px);
    border-color: rgba(99, 102, 241, 0.6);
    box-shadow: 0 14px 28px -6px rgba(79, 70, 229, 0.22);
}
.feature-icon-badge {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    margin-bottom: 1.1rem;
}
.feature-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #F8FAFC;
    margin-bottom: 0.5rem;
}
.feature-desc {
    font-size: 0.88rem;
    color: #94A3B8;
    line-height: 1.55;
    margin: 0;
}

/* SERP Google Preview Box */
.serp-card {
    background: #FFFFFF;
    color: #202124;
    padding: 1.35rem 1.6rem;
    border-radius: 14px;
    font-family: Roboto, Arial, sans-serif;
    border: 1px solid #DADCE0;
    box-shadow: 0 2px 10px rgba(32,33,36,0.1);
    margin-top: 0.8rem;
}
.serp-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
}
.serp-favicon {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #E8F0FE;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
}
.serp-domain {
    font-size: 0.88rem;
    color: #202124;
    font-weight: 500;
}
.serp-url-breadcrumb {
    font-size: 0.78rem;
    color: #5F6368;
}
.serp-title-link {
    color: #1a0dab !important;
    font-size: 1.28rem;
    line-height: 1.35;
    font-weight: 400;
    margin-top: 3px;
    margin-bottom: 4px;
    cursor: pointer;
}
.serp-title-link:hover {
    text-decoration: underline;
}
.serp-snippet {
    color: #4d5156;
    font-size: 0.9rem;
    line-height: 1.5;
}

/* Status Chips */
.status-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
}
.status-green {
    background: rgba(16, 185, 129, 0.15);
    color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.35);
}
.status-purple {
    background: rgba(168, 85, 247, 0.15);
    color: #C084FC;
    border: 1px solid rgba(168, 85, 247, 0.35);
}
.status-amber {
    background: rgba(245, 158, 11, 0.15);
    color: #FBBF24;
    border: 1px solid rgba(245, 158, 11, 0.35);
}
.status-red {
    background: rgba(239, 68, 68, 0.15);
    color: #F87171;
    border: 1px solid rgba(239, 68, 68, 0.35);
}

/* Sidebar Custom Details */
.sidebar-box {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(51, 65, 85, 0.5);
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# 3. App Header Banner
st.markdown("""
<div class="main-header">
    <div class="header-badge-row">
        <span class="header-badge"><span class="live-indicator-dot"></span> PRO ENGINE • CLOUD AUDIT</span>
        <span class="header-badge" style="background:rgba(16,185,129,0.15); color:#34D399; border-color:rgba(16,185,129,0.35);">FREE & UNLIMITED</span>
    </div>
    <h1 class="main-title">🕷️ Amir's SEO Spider</h1>
    <p class="main-subtitle">High-speed technical SEO crawler and site audit suite. Deep crawl up to 10,000+ URLs with zero page caps, analyze canonical targets, verify status codes, and export complete multi-tab spreadsheets.</p>
    <div class="header-tags">
        <span class="header-pill">🚀 Multi-Threaded Workers</span>
        <span class="header-pill">🎯 Canonical URL Mapping</span>
        <span class="header-pill">🚨 50+ SEO Health Checks</span>
        <span class="header-pill">📦 Free Multi-Tab Excel Export</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 4. Initialize Session State
if "crawl_results" not in st.session_state:
    st.session_state["crawl_results"] = None
if "is_crawling" not in st.session_state:
    st.session_state["is_crawling"] = False
if "single_inspect_result" not in st.session_state:
    st.session_state["single_inspect_result"] = None

# Config defaults in session state
if "cfg_target_url" not in st.session_state:
    st.session_state["cfg_target_url"] = "https://example.com"
if "cfg_max_pages" not in st.session_state:
    st.session_state["cfg_max_pages"] = 2000
if "cfg_max_depth" not in st.session_state:
    st.session_state["cfg_max_depth"] = 5
if "cfg_threads" not in st.session_state:
    st.session_state["cfg_threads"] = 10

# 5. Screaming Frog Top Search Bar
st.markdown("""
<div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(51, 65, 85, 0.65); border-radius: 14px; padding: 12px 18px; margin-bottom: 1.5rem; backdrop-filter: blur(10px); box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
        <span style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #94A3B8;">
            🕸️ Spider Crawl Target & Scope
        </span>
        <span style="font-size: 0.75rem; color: #64748B;">
            Screaming Frog Style Search & Mode Selection
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

col_sf_url, col_sf_mode, col_sf_start, col_sf_clear = st.columns([5, 2.2, 1.3, 1.1])

with col_sf_url:
    target_url = st.text_input(
        "Enter URL to spider",
        value=st.session_state["cfg_target_url"],
        placeholder="https://www.example.com/",
        label_visibility="collapsed",
        help="Enter starting website URL (e.g. https://www.cairnindia.com/)"
    )

with col_sf_mode:
    crawl_mode = st.selectbox(
        "Crawl Mode",
        options=["Subdomain", "Subfolder", "All Subdomains", "Exact URL"],
        index=0,
        label_visibility="collapsed",
        help="• Subdomain: Crawl within current host\n• Subfolder: Stay inside folder path\n• All Subdomains: Crawl all *.domain.com subdomains\n• Exact URL: Inspect this single page only"
    )

with col_sf_start:
    btn_start_top = st.button("▶ Start", type="primary", use_container_width=True)

with col_sf_clear:
    btn_clear = st.button("🔄 Clear", use_container_width=True)

if btn_clear:
    st.session_state["crawl_results"] = None
    st.session_state["single_inspect_result"] = None
    st.rerun()

# 6. Sidebar Controls & Quick Presets
with st.sidebar:
    st.markdown("### ⚙️ Crawl Configuration")

    preset_choice = st.selectbox(
        "⚡ Quick Scan Preset",
        ["Custom Settings", "⚡ Fast Audit (100 URLs, Depth 3)", "🚀 Standard (1,000 URLs, Depth 5)", "🏢 Deep Spider (5,000 URLs, Depth 8)"],
        index=0,
        help="Quickly populate recommended depth and speed settings"
    )
    if preset_choice == "⚡ Fast Audit (100 URLs, Depth 3)" and st.session_state["cfg_max_pages"] != 100:
        st.session_state["cfg_max_pages"] = 100
        st.session_state["cfg_max_depth"] = 3
        st.session_state["cfg_threads"] = 10
        st.rerun()
    elif preset_choice == "🚀 Standard (1,000 URLs, Depth 5)" and st.session_state["cfg_max_pages"] != 1000:
        st.session_state["cfg_max_pages"] = 1000
        st.session_state["cfg_max_depth"] = 5
        st.session_state["cfg_threads"] = 12
        st.rerun()
    elif preset_choice == "🏢 Deep Spider (5,000 URLs, Depth 8)" and st.session_state["cfg_max_pages"] != 5000:
        st.session_state["cfg_max_pages"] = 5000
        st.session_state["cfg_max_depth"] = 8
        st.session_state["cfg_threads"] = 18
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        max_pages = st.number_input(
            "Max Pages",
            min_value=1,
            max_value=10000,
            value=st.session_state["cfg_max_pages"],
            step=250,
            help="Maximum URLs to crawl. Scale up to 10,000 URLs!"
        )
    with col_c2:
        max_depth = st.number_input(
            "Max Depth",
            min_value=1,
            max_value=15,
            value=st.session_state["cfg_max_depth"],
            step=1,
            help="Maximum link click depth from root"
        )

    col_c3, col_c4 = st.columns(2)
    with col_c3:
        concurrency = st.slider(
            "Concurrency",
            min_value=1,
            max_value=25,
            value=st.session_state["cfg_threads"],
            help="Number of concurrent multi-threaded requests"
        )
    with col_c4:
        timeout = st.slider("Timeout (s)", min_value=3, max_value=30, value=8, help="Per-request timeout in seconds")

    with st.expander("🛠️ Advanced Crawl Settings", expanded=False):
        user_agent_choice = st.selectbox(
            "User-Agent",
            options=list(USER_AGENTS.keys()),
            index=0
        )
        respect_robots = st.checkbox("Respect robots.txt directives", value=False)
        include_regex = st.text_input("Include URL Regex", value="", help="Only crawl URLs matching regex pattern")
        exclude_regex = st.text_input("Exclude URL Regex", value="", help="Skip URLs matching regex pattern")

    st.markdown("---")
    btn_start_sidebar = st.button("🚀 Start SEO Crawl", use_container_width=True)
    st.markdown("---")

    st.markdown("""
    <div class="sidebar-box">
        <div style="font-weight:700; color:#F8FAFC; margin-bottom:6px; font-size:0.88rem;">🔥 Screaming Frog vs Amir's Spider:</div>
        <div style="font-size:0.8rem; color:#94A3B8; line-height:1.5;">
            • <b>Top Search Bar:</b> Enter URL + Mode selector.<br>
            • <b>Unlimited Scale:</b> No 500-page limit.<br>
            • <b>Canonical Mapping:</b> Dedicated audit tab.<br>
            • <b>Free Excel Export:</b> Multi-sheet workbook.
        </div>
    </div>
    """, unsafe_allow_html=True)

btn_start = btn_start_top or btn_start_sidebar

# 7. Crawl Execution Logic
if btn_start:
    if not target_url or not target_url.startswith(("http://", "https://")):
        st.error("⚠️ Please enter a valid URL starting with http:// or https://")
    else:
        st.session_state["cfg_target_url"] = target_url
        st.session_state["is_crawling"] = True
        progress_bar = st.progress(0, text=f"Initializing High-Speed SEO Spider Engine [{crawl_mode} Mode]...")
        status_box = st.empty()

        spider = SEOSpider(
            start_url=target_url,
            max_pages=max_pages,
            max_depth=max_depth,
            concurrency=concurrency,
            user_agent_name=user_agent_choice,
            respect_robots=respect_robots,
            timeout=timeout,
            include_regex=include_regex,
            exclude_regex=exclude_regex,
            crawl_mode=crawl_mode
        )

        def on_progress(crawled_count=0, max_pages=1, current_url="", status_code=200, **kwargs):
            total_limit = max_pages or 1
            pct = min(1.0, crawled_count / max(total_limit, 1))
            progress_bar.progress(pct, text=f"⚡ Crawling ({crawled_count}/{total_limit} URLs) — {current_url[:65]}...")
            status_box.markdown(f"""
            <div style="background:rgba(30,41,59,0.7); border:1px solid #334155; border-radius:10px; padding:10px 14px; font-size:0.88rem; color:#CBD5E1;">
                <b>Crawling URL:</b> <code>{current_url[:75]}</code> &nbsp;|&nbsp; 
                <b>Status:</b> <span class="status-pill status-green">{status_code}</span> &nbsp;|&nbsp; 
                <b>Total Crawled:</b> <b>{crawled_count}</b>
            </div>
            """, unsafe_allow_html=True)

        start_time = time.time()
        with st.spinner("Spider is traversing website architecture..."):
            raw_crawl = spider.crawl(progress_callback=on_progress)
            elapsed = round(time.time() - start_time, 2)

        progress_bar.progress(1.0, text=f"Crawl Completed: {len(raw_crawl['crawled_pages'])} pages in {elapsed}s! Analyzing technical factors...")
        
        with st.spinner("Computing SEO Health Score and Issue Aggregations..."):
            analysis = analyze_crawl_results(
                raw_crawl["crawled_pages"],
                raw_crawl["links"],
                raw_crawl["images"]
            )
            analysis["elapsed_seconds"] = elapsed
            analysis["start_url"] = target_url
            st.session_state["crawl_results"] = analysis
            st.session_state["is_crawling"] = False

        status_box.success(f"✅ Audit Completed! Successfully crawled and analyzed **{len(analysis['df_pages'])}** pages in **{elapsed} seconds**.")
        time.sleep(1)
        st.rerun()

# 7. Navigation Tabs
tab_overview, tab_issues, tab_pages, tab_canonicals, tab_titles, tab_headings, tab_links, tab_images, tab_architecture, tab_inspector, tab_sitemap = st.tabs([
    "📊 Overview",
    "🚨 Issues & Fixes",
    "📑 Internal Pages",
    "🎯 Canonicals",
    "🏷️ Titles & Meta",
    "🧱 Headings (H1/H2)",
    "🔗 Link Analysis",
    "🖼️ Images Audit",
    "🧭 Site Structure",
    "🔍 Quick Inspector",
    "🤖 Robots & Sitemap"
])

results = st.session_state.get("crawl_results")

# ==============================================================================
# TAB 1: OVERVIEW & HEALTH AUDIT
# ==============================================================================
with tab_overview:
    if not results:
        # Gorgeous Empty State Showcase Hero
        st.markdown("""
        <div style="text-align:center; padding: 2rem 1rem 2.5rem;">
            <span class="header-badge" style="background:rgba(99,102,241,0.2); color:#A5B4FC; margin-bottom:1rem;">
                ✨ ENTERPRISE TECHNICAL AUDITS AT CLOUD SCALE
            </span>
            <h2 style="font-size:2.2rem; font-weight:800; color:#F8FAFC; margin-top:0.5rem; letter-spacing:-0.02em;">
                Ready to Audit Any Website with Zero Limitations
            </h2>
            <p style="color:#94A3B8; font-size:1.05rem; max-width:720px; margin:0.6rem auto 1.8rem; line-height:1.6;">
                Configure your target URL in the sidebar, or run an instant quick test to evaluate internal linking, canonical targets, metadata lengths, status codes, and SEO health.
            </p>
        </div>
        """, unsafe_allow_html=True)

        col_demo1, col_demo2, col_demo3 = st.columns([1, 2, 1])
        with col_demo2:
            if st.button("🚀 Load Sample Target (books.toscrape.com)", use_container_width=True):
                st.session_state["cfg_target_url"] = "https://books.toscrape.com"
                st.session_state["cfg_max_pages"] = 100
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # 4 Interactive Feature Cards
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon-badge" style="background:rgba(99,102,241,0.18); color:#818CF8;">⚡</div>
                <div class="feature-title">Unlimited URLs</div>
                <p class="feature-desc">Bypass standard free 500-page limits. Multi-threaded engine comfortably audits up to 10,000+ pages.</p>
            </div>
            """, unsafe_allow_html=True)
        with col_f2:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon-badge" style="background:rgba(168,85,247,0.18); color:#C084FC;">🎯</div>
                <div class="feature-title">Canonical Audit</div>
                <p class="feature-desc">Page URL ➔ Canonical Target tracking. Instantly detect Self-Referential, Canonicalised, Missing, and Multiple tags.</p>
            </div>
            """, unsafe_allow_html=True)
        with col_f3:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon-badge" style="background:rgba(16,185,129,0.18); color:#34D399;">🔍</div>
                <div class="feature-title">50+ SEO Checks</div>
                <p class="feature-desc">Deep inspection of HTTP status codes, title pixel widths, H1/H2 hierarchy, broken links, and Schema markup.</p>
            </div>
            """, unsafe_allow_html=True)
        with col_f4:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon-badge" style="background:rgba(245,158,11,0.18); color:#FBBF24;">📊</div>
                <div class="feature-title">Client-Ready Reports</div>
                <p class="feature-desc">Download multi-tab Excel workbooks (.xlsx) with dedicated sheets for Canonicals, Errors, Images, and Links.</p>
            </div>
            """, unsafe_allow_html=True)

    else:
        summary = results["summary"]
        df_pages = results["df_pages"]
        df_issues = results["df_issues"]
        elapsed = results.get("elapsed_seconds", 0)
        target = results.get("start_url", "")

        # Target Quick Status Strip
        st.markdown(f"""
        <div style="background:rgba(30,41,59,0.6); border:1px solid #334155; border-radius:12px; padding:12px 18px; margin-bottom:1.2rem; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
            <div>
                <span style="color:#94A3B8; font-size:0.85rem; font-weight:600; text-transform:uppercase;">Audited Website:</span>
                <span style="color:#F8FAFC; font-weight:700; margin-left:8px; font-size:1.05rem;">{target}</span>
            </div>
            <div style="display:flex; gap:16px; font-size:0.85rem; color:#94A3B8;">
                <span>⏱️ Crawl Time: <b style="color:#CBD5E1;">{elapsed}s</b></span>
                <span>⚡ Avg Latency: <b style="color:#CBD5E1;">{round(df_pages['latency_ms'].mean(), 1) if not df_pages.empty else 0} ms</b></span>
                <span>🔒 HTTPS Pages: <b style="color:#CBD5E1;">{len(df_pages[df_pages['url'].str.startswith('https://')])} / {len(df_pages)}</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 5 Modern KPI Cards
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        with col_m1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-card-topbar" style="background:#6366F1;"></div>
                <div class="kpi-title">Pages Crawled <span>📄</span></div>
                <div class="kpi-num" style="color:#818CF8;">{summary['total_crawled']}</div>
                <div class="kpi-sub">Total internal documents</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-card-topbar" style="background:#F43F5E;"></div>
                <div class="kpi-title">Critical Errors <span>🚨</span></div>
                <div class="kpi-num" style="color:#F43F5E;">{summary['critical_errors']}</div>
                <div class="kpi-sub">Require immediate fix</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-card-topbar" style="background:#F59E0B;"></div>
                <div class="kpi-title">Warnings <span>⚠️</span></div>
                <div class="kpi-num" style="color:#FBBF24;">{summary['warnings']}</div>
                <div class="kpi-sub">Technical recommendations</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-card-topbar" style="background:#8B5CF6;"></div>
                <div class="kpi-title">Canonicals <span>🎯</span></div>
                <div class="kpi-num" style="color:#A78BFA;">{len(df_pages[df_pages['canonical_status'] == 'Self-Referential'])}</div>
                <div class="kpi-sub">Self-referential tags verified</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m5:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-card-topbar" style="background:#10B981;"></div>
                <div class="kpi-title">Total Links <span>🔗</span></div>
                <div class="kpi-num" style="color:#34D399;">{summary['total_links']}</div>
                <div class="kpi-sub">Graph edge connections</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Visualizer Charts Grid
        col_g1, col_g2, col_g3 = st.columns([1, 1, 1.2])
        with col_g1:
            st.plotly_chart(create_health_gauge(summary["health_score"]), use_container_width=True)
        with col_g2:
            st.plotly_chart(create_status_code_chart(df_pages), use_container_width=True)
        with col_g3:
            st.plotly_chart(create_issues_bar_chart(df_issues), use_container_width=True)

        st.markdown("---")
        
        # Export Actions Section
        st.subheader("📥 Export Client-Ready Audit Reports")
        col_d1, col_d2, col_d3 = st.columns([1.2, 1.2, 1.6])
        with col_d1:
            excel_bytes = generate_excel_report(results, results.get("start_url", ""))
            domain_slug = urlparse(results.get("start_url","")).netloc or "audit"
            st.download_button(
                label="📊 Download Full Excel Report (.xlsx)",
                data=excel_bytes,
                file_name=f"seo_audit_{domain_slug}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with col_d2:
            csv_pages = generate_csv(df_pages)
            st.download_button(
                label="📑 Download All Pages (CSV)",
                data=csv_pages,
                file_name=f"crawled_pages_{domain_slug}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_d3:
            st.caption("✨ Excel report contains dedicated sheets: **Summary**, **Pages**, **Canonicals**, **Issues**, **Images**, and **Links**.")

# ==============================================================================
# TAB 2: ISSUES & ACTIONABLE FIXES
# ==============================================================================
with tab_issues:
    if not results:
        st.info("👈 Enter a URL in the sidebar and run a crawl to view prioritized issues and actionable fixes.")
    else:
        df_issues = results["df_issues"]
        if df_issues.empty:
            st.success("🎉 Outstanding! Zero technical SEO issues detected on crawled pages.")
        else:
            err_count = len(df_issues[df_issues["type"] == "Error"])
            warn_count = len(df_issues[df_issues["type"] == "Warning"])
            not_count = len(df_issues[df_issues["type"] == "Notice"])

            st.markdown(f"""
            <div style="display:flex; gap:12px; margin-bottom:1rem; flex-wrap:wrap;">
                <span class="status-pill status-red">🔴 Critical Errors: {err_count}</span>
                <span class="status-pill status-amber">🟡 Warnings: {warn_count}</span>
                <span class="status-pill status-purple">🔵 Notices: {not_count}</span>
            </div>
            """, unsafe_allow_html=True)

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                selected_severity = st.multiselect(
                    "Filter by Severity",
                    options=["Error", "Warning", "Notice"],
                    default=["Error", "Warning", "Notice"]
                )
            with col_f2:
                all_categories = sorted(df_issues["category"].unique())
                selected_cat = st.multiselect(
                    "Filter by Category",
                    options=all_categories,
                    default=all_categories
                )

            filtered_issues = df_issues[
                (df_issues["type"].isin(selected_severity)) &
                (df_issues["category"].isin(selected_cat))
            ]

            st.caption(f"Displaying **{len(filtered_issues)}** filtered issues:")
            st.dataframe(
                filtered_issues,
                use_container_width=True,
                column_config={
                    "type": st.column_config.TextColumn("Severity"),
                    "category": st.column_config.TextColumn("Category"),
                    "url": st.column_config.LinkColumn("Page URL"),
                    "issue": st.column_config.TextColumn("Issue Detected"),
                    "recommendation": st.column_config.TextColumn("Recommended Action"),
                },
                hide_index=True
            )

# ==============================================================================
# TAB 3: ALL INTERNAL PAGES EXPLORER
# ==============================================================================
with tab_pages:
    if not results:
        st.info("Run a crawl to explore internal pages table.")
    else:
        df_pages = results["df_pages"]
        search_query = st.text_input("🔍 Search pages by URL, Title, or Canonical Target:", "")
        
        display_df = df_pages.copy()
        if search_query:
            display_df = display_df[
                display_df["url"].str.contains(search_query, case=False, na=False) |
                display_df["title"].str.contains(search_query, case=False, na=False) |
                display_df["canonical_url"].str.contains(search_query, case=False, na=False)
            ]

        columns_to_show = [
            "url", "canonical_url", "canonical_status", "status_code", "title", "meta_description", "h1",
            "word_count", "latency_ms", "size_kb",
            "is_indexable", "internal_outlinks_count", "images_count"
        ]
        available_cols = [c for c in columns_to_show if c in display_df.columns]

        st.caption(f"Showing **{len(display_df)}** pages:")
        st.dataframe(
            display_df[available_cols],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Page URL"),
                "canonical_url": st.column_config.LinkColumn("Canonical URL"),
                "canonical_status": st.column_config.TextColumn("Canonical Status"),
                "status_code": st.column_config.NumberColumn("Status", format="%d"),
                "title": st.column_config.TextColumn("Page Title"),
                "meta_description": st.column_config.TextColumn("Meta Description"),
                "h1": st.column_config.TextColumn("H1"),
                "word_count": st.column_config.NumberColumn("Words"),
                "latency_ms": st.column_config.NumberColumn("Latency", format="%.0f ms"),
                "size_kb": st.column_config.NumberColumn("Size", format="%.1f KB"),
                "is_indexable": st.column_config.CheckboxColumn("Indexable"),
            },
            hide_index=True
        )

# ==============================================================================
# TAB 4: CANONICAL TAGS AUDIT ("Ye Page -> Iska Canonical Ye")
# ==============================================================================
with tab_canonicals:
    if not results:
        st.info("Run a crawl to audit Canonical URLs, mismatches, and self-referential tags.")
    else:
        df_pages = results["df_pages"]
        
        st.subheader("🎯 Canonical URLs Audit (Page URL ➔ Canonical Target)")
        st.caption("Complete breakdown of Page URLs and their canonical directives — prevents duplicate content penalties and consolidates link equity.")

        # Metric breakdown
        total_pages = len(df_pages)
        self_ref_count = len(df_pages[df_pages["canonical_status"] == "Self-Referential"])
        canonicalised_count = len(df_pages[df_pages["canonical_status"] == "Canonicalised"])
        missing_count = len(df_pages[df_pages["canonical_status"] == "Missing"])
        multiple_count = len(df_pages[df_pages["canonical_status"] == "Multiple"])

        cm1, cm2, cm3, cm4 = st.columns(4)
        cm1.metric("Self-Referential (OK)", f"{self_ref_count}", delta=f"{round(self_ref_count/max(total_pages,1)*100)}% of pages")
        cm2.metric("Canonicalised (Points Elsewhere)", f"{canonicalised_count}", delta="Consolidating equity" if canonicalised_count else None)
        cm3.metric("Missing Canonical", f"{missing_count}", delta="Needs attention" if missing_count else None, delta_color="inverse")
        cm4.metric("Multiple Canonicals", f"{multiple_count}", delta="Critical conflict" if multiple_count else None, delta_color="inverse")

        # Filters
        fcol1, fcol2 = st.columns([1, 2])
        with fcol1:
            canon_filter = st.selectbox(
                "Filter by Canonical Status:",
                ["All Pages", "Self-Referential", "Canonicalised", "Missing", "Multiple"]
            )
        with fcol2:
            canon_search = st.text_input("🔍 Search Page URL or Canonical Target URL:", "")

        df_canon = df_pages[["url", "canonical_url", "canonical_status", "status_code", "is_indexable"]].copy()

        if canon_filter != "All Pages":
            df_canon = df_canon[df_canon["canonical_status"] == canon_filter]

        if canon_search:
            df_canon = df_canon[
                df_canon["url"].str.contains(canon_search, case=False, na=False) |
                df_canon["canonical_url"].str.contains(canon_search, case=False, na=False)
            ]

        # Download button for filtered canonicals
        col_cdown1, col_cdown2 = st.columns([1, 4])
        with col_cdown1:
            csv_canon = generate_csv(df_canon)
            st.download_button(
                label=f"📥 Download Canonicals ({len(df_canon)} URLs)",
                data=csv_canon,
                file_name=f"canonicals_{canon_filter.replace(' ', '_').lower()}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_cdown2:
            st.caption(f"Showing **{len(df_canon)}** of **{total_pages}** pages matching filter: `{canon_filter}`")

        st.dataframe(
            df_canon,
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Page URL (Crawled)"),
                "canonical_url": st.column_config.LinkColumn("Canonical Target (<link rel='canonical'>)"),
                "canonical_status": st.column_config.TextColumn("Canonical Status"),
                "status_code": st.column_config.NumberColumn("Status Code", format="%d"),
                "is_indexable": st.column_config.CheckboxColumn("Indexable"),
            },
            hide_index=True
        )

        with st.expander("💡 SEO Guide: Understanding Canonical Statuses"):
            st.markdown("""
            - **Self-Referential (`Page URL == Canonical URL`)**: ✅ Recommended best practice. Protects against duplicate content caused by query parameters, session IDs, trailing slashes, and HTTP/HTTPS variations.
            - **Canonicalised (`Page URL != Canonical URL`)**: 🔀 Directs search engines to index a master version instead of this URL.
            - **Missing Canonical**: ⚠️ No canonical link tag found in `<head>`. Search engines will choose a version on their own.
            - **Multiple Canonicals**: ❌ More than one canonical link tag detected. Search engines typically ignore all conflicting tags.
            """)

# ==============================================================================
# TAB 5: PAGE TITLES & META DESCRIPTIONS AUDIT
# ==============================================================================
with tab_titles:
    if not results:
        st.info("Run a crawl to inspect titles, meta descriptions, missing tags, and duplicates.")
    else:
        df_pages = results["df_pages"].copy()
        total_pages = len(df_pages)

        # Prepare Clean Status Columns
        df_titles_meta = df_pages[[
            "url", "status_code", "title", "title_length", "title_pixel_width", 
            "meta_description", "meta_description_length", "is_indexable"
        ]].copy()
        
        # Calculate Title and Description Duplicates
        title_counts = df_titles_meta[df_titles_meta["title"].str.strip() != ""]["title"].value_counts()
        dup_titles_set = set(title_counts[title_counts > 1].index)

        desc_counts = df_titles_meta[df_titles_meta["meta_description"].str.strip() != ""]["meta_description"].value_counts()
        dup_desc_set = set(desc_counts[desc_counts > 1].index)

        # Title Status Tag
        def get_title_status(row):
            t = str(row["title"]).strip()
            if not t:
                return "Missing"
            if t in dup_titles_set:
                return "Duplicate"
            if row["title_length"] > 60 or row["title_pixel_width"] > 600:
                return "Over 60 Chars (>600px)"
            if row["title_length"] < 30:
                return "Below 30 Chars"
            return "OK"

        # Meta Description Status Tag
        def get_desc_status(row):
            d = str(row["meta_description"]).strip()
            if not d:
                return "Missing"
            if d in dup_desc_set:
                return "Duplicate"
            if row["meta_description_length"] > 160:
                return "Over 160 Chars"
            if row["meta_description_length"] < 70:
                return "Below 70 Chars"
            return "OK"

        df_titles_meta["title_status"] = df_titles_meta.apply(get_title_status, axis=1)
        df_titles_meta["meta_desc_status"] = df_titles_meta.apply(get_desc_status, axis=1)

        # KPI Counters
        missing_titles_count = len(df_titles_meta[df_titles_meta["title_status"] == "Missing"])
        dup_titles_count = len(df_titles_meta[df_titles_meta["title_status"] == "Duplicate"])
        missing_desc_count = len(df_titles_meta[df_titles_meta["meta_desc_status"] == "Missing"])
        dup_desc_count = len(df_titles_meta[df_titles_meta["meta_desc_status"] == "Duplicate"])
        ok_titles_count = len(df_titles_meta[df_titles_meta["title_status"] == "OK"])

        st.subheader("🏷️ Page Titles & Meta Descriptions Audit")
        st.caption("Deep inspection of Titles and Meta Descriptions — extract missing tags, identify duplicate metadata, and check SERP lengths.")

        # 5 Metric Cards
        tm1, tm2, tm3, tm4, tm5 = st.columns(5)
        tm1.metric("Titles Optimal (OK)", f"{ok_titles_count}", delta=f"{round(ok_titles_count/max(total_pages,1)*100)}% of pages")
        tm2.metric("Missing Titles", f"{missing_titles_count}", delta="Needs title tag" if missing_titles_count else "None", delta_color="inverse" if missing_titles_count else "normal")
        tm3.metric("Duplicate Titles", f"{dup_titles_count}", delta="Cannibalization" if dup_titles_count else "Unique", delta_color="inverse" if dup_titles_count else "normal")
        tm4.metric("Missing Meta Desc", f"{missing_desc_count}", delta="Needs snippet" if missing_desc_count else "None", delta_color="inverse" if missing_desc_count else "normal")
        tm5.metric("Duplicate Meta Desc", f"{dup_desc_count}", delta="Identical snippet" if dup_desc_count else "Unique", delta_color="inverse" if dup_desc_count else "normal")

        # Filters and Search
        fcol1, fcol2 = st.columns([1.5, 2])
        with fcol1:
            title_filter = st.selectbox(
                "Filter Titles & Meta by Status:",
                [
                    "All Pages",
                    "Missing Title",
                    "Duplicate Title",
                    "Title Over 60 Chars (>600px)",
                    "Title Below 30 Chars",
                    "Missing Meta Description",
                    "Duplicate Meta Description",
                    "Meta Desc Over 160 Chars",
                    "Meta Desc Below 70 Chars"
                ]
            )
        with fcol2:
            title_search = st.text_input("🔍 Search URL, Page Title, or Meta Description:", "")

        df_filtered_tm = df_titles_meta.copy()

        if title_filter == "Missing Title":
            df_filtered_tm = df_filtered_tm[df_filtered_tm["title_status"] == "Missing"]
        elif title_filter == "Duplicate Title":
            df_filtered_tm = df_filtered_tm[df_filtered_tm["title_status"] == "Duplicate"]
        elif title_filter == "Title Over 60 Chars (>600px)":
            df_filtered_tm = df_filtered_tm[df_filtered_tm["title_status"] == "Over 60 Chars (>600px)"]
        elif title_filter == "Title Below 30 Chars":
            df_filtered_tm = df_filtered_tm[df_filtered_tm["title_status"] == "Below 30 Chars"]
        elif title_filter == "Missing Meta Description":
            df_filtered_tm = df_filtered_tm[df_filtered_tm["meta_desc_status"] == "Missing"]
        elif title_filter == "Duplicate Meta Description":
            df_filtered_tm = df_filtered_tm[df_filtered_tm["meta_desc_status"] == "Duplicate"]
        elif title_filter == "Meta Desc Over 160 Chars":
            df_filtered_tm = df_filtered_tm[df_filtered_tm["meta_desc_status"] == "Over 160 Chars"]
        elif title_filter == "Meta Desc Below 70 Chars":
            df_filtered_tm = df_filtered_tm[df_filtered_tm["meta_desc_status"] == "Below 70 Chars"]

        if title_search:
            df_filtered_tm = df_filtered_tm[
                df_filtered_tm["url"].str.contains(title_search, case=False, na=False) |
                df_filtered_tm["title"].str.contains(title_search, case=False, na=False) |
                df_filtered_tm["meta_description"].str.contains(title_search, case=False, na=False)
            ]

        # Download button for filtered data
        col_down1, col_down2 = st.columns([1, 4])
        with col_down1:
            csv_tm = generate_csv(df_filtered_tm)
            st.download_button(
                label=f"📥 Download Filtered Titles & Meta ({len(df_filtered_tm)} URLs)",
                data=csv_tm,
                file_name=f"titles_meta_{title_filter.replace(' ', '_').lower()}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_down2:
            st.caption(f"Showing **{len(df_filtered_tm)}** of **{total_pages}** pages matching filter: `{title_filter}`")

        st.dataframe(
            df_filtered_tm[[
                "url", "title", "title_status", "title_length", "title_pixel_width",
                "meta_description", "meta_desc_status", "meta_description_length", "status_code"
            ]],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Page URL"),
                "title": st.column_config.TextColumn("Page Title"),
                "title_status": st.column_config.TextColumn("Title Status"),
                "title_length": st.column_config.NumberColumn("Title Chars"),
                "title_pixel_width": st.column_config.NumberColumn("Pixels (px)"),
                "meta_description": st.column_config.TextColumn("Meta Description"),
                "meta_desc_status": st.column_config.TextColumn("Meta Status"),
                "meta_description_length": st.column_config.NumberColumn("Meta Chars"),
                "status_code": st.column_config.NumberColumn("HTTP Status", format="%d")
            },
            hide_index=True
        )

        st.markdown("---")
        st.subheader("🔍 Google SERP Preview Simulator")
        selected_url = st.selectbox("Select Page URL to preview Google Search snippet:", options=df_pages["url"].tolist())
        
        if selected_url:
            row = df_pages[df_pages["url"] == selected_url].iloc[0]
            p_title = row.get("title") or "Untitled Document"
            p_url = row.get("url") or ""
            p_desc = row.get("meta_description") or "No meta description provided for this page. Search engines will generate a snippet from page body text."
            p_pixels = row.get("title_pixel_width", 0)

            parsed_p = urlparse(p_url)
            domain_display = parsed_p.netloc
            path_display = parsed_p.path if parsed_p.path != "/" else ""

            st.markdown(f"""
            <div class="serp-card">
                <div class="serp-card-header">
                    <div class="serp-favicon">🌐</div>
                    <div>
                        <div class="serp-domain">{domain_display}</div>
                        <div class="serp-url-breadcrumb">{p_url}</div>
                    </div>
                </div>
                <div class="serp-title-link">{p_title}</div>
                <div class="serp-snippet">{p_desc}</div>
            </div>
            """, unsafe_allow_html=True)

            col_sp1, col_sp2, col_sp3 = st.columns(3)
            col_sp1.metric("Title Length", f"{len(p_title)} chars", delta="Optimal (30-60)" if 30 <= len(p_title) <= 60 else "Check Length")
            col_sp2.metric("Title Pixel Width", f"{p_pixels} px", delta="Fits Google Desktop (<600px)" if p_pixels <= 600 else "Truncated by Google (>600px)", delta_color="normal" if p_pixels <= 600 else "inverse")
            col_sp3.metric("Meta Description", f"{len(p_desc)} chars", delta="Optimal (70-160)" if 70 <= len(p_desc) <= 160 else "Check Length")

# ==============================================================================
# TAB 6: HEADINGS (H1/H2) HIERARCHY AUDIT
# ==============================================================================
with tab_headings:
    if not results:
        st.info("Run a crawl to inspect H1 and H2 tags, missing headings, and duplicate hierarchy.")
    else:
        df_pages = results["df_pages"].copy()
        total_pages = len(df_pages)

        # Prepare Clean Heading Columns
        df_headings = df_pages[[
            "url", "h1", "h1_count", "h2_first", "h2_count", "status_code", "is_indexable"
        ]].copy()

        # Calculate H1 and H2 duplicates
        h1_counts = df_headings[df_headings["h1"].str.strip() != ""]["h1"].value_counts()
        dup_h1_set = set(h1_counts[h1_counts > 1].index)

        h2_counts = df_headings[df_headings["h2_first"].str.strip() != ""]["h2_first"].value_counts()
        dup_h2_set = set(h2_counts[h2_counts > 1].index)

        # H1 Status Tag
        def get_h1_status(row):
            h = str(row["h1"]).strip()
            c = row.get("h1_count", 0)
            if not h or c == 0:
                return "Missing"
            if c > 1:
                return "Multiple H1s"
            if h in dup_h1_set:
                return "Duplicate"
            if len(h) > 70:
                return "Over 70 Chars"
            return "OK"

        # H2 Status Tag
        def get_h2_status(row):
            h = str(row["h2_first"]).strip()
            c = row.get("h2_count", 0)
            if not h or c == 0:
                return "Missing"
            if h in dup_h2_set:
                return "Duplicate"
            if c > 1:
                return "Multiple H2s"
            return "OK"

        df_headings["h1_status"] = df_headings.apply(get_h1_status, axis=1)
        df_headings["h2_status"] = df_headings.apply(get_h2_status, axis=1)

        # Metric Counters
        h1_ok_count = len(df_headings[df_headings["h1_status"] == "OK"])
        missing_h1_count = len(df_headings[df_headings["h1_status"] == "Missing"])
        dup_h1_count = len(df_headings[df_headings["h1_status"] == "Duplicate"])
        multiple_h1_count = len(df_headings[df_headings["h1_status"] == "Multiple H1s"])
        missing_h2_count = len(df_headings[df_headings["h2_status"] == "Missing"])

        st.subheader("🧱 Heading Hierarchy & Structure Audit (H1 / H2)")
        st.caption("Inspect heading tags across your site — isolate missing H1s, identify duplicate headings, and detect multiple H1 tags per page.")

        # 5 Metric Cards
        hm1, hm2, hm3, hm4, hm5 = st.columns(5)
        hm1.metric("H1 Optimal (OK)", f"{h1_ok_count}", delta=f"{round(h1_ok_count/max(total_pages,1)*100)}% of pages")
        hm2.metric("Missing H1", f"{missing_h1_count}", delta="No H1 tag" if missing_h1_count else "None", delta_color="inverse" if missing_h1_count else "normal")
        hm3.metric("Duplicate H1", f"{dup_h1_count}", delta="Shared H1" if dup_h1_count else "Unique", delta_color="inverse" if dup_h1_count else "normal")
        hm4.metric("Multiple H1s", f"{multiple_h1_count}", delta="More than 1 H1" if multiple_h1_count else "Single H1", delta_color="inverse" if multiple_h1_count else "normal")
        hm5.metric("Missing H2", f"{missing_h2_count}", delta="Needs subheadings" if missing_h2_count else "Structured", delta_color="inverse" if missing_h2_count else "normal")

        # Filters and Search
        hfcol1, hfcol2 = st.columns([1.5, 2])
        with hfcol1:
            heading_filter = st.selectbox(
                "Filter Headings by Status:",
                [
                    "All Headings",
                    "Missing H1",
                    "Duplicate H1",
                    "Multiple H1s",
                    "H1 Over 70 Chars",
                    "Missing H2",
                    "Multiple H2s",
                    "Duplicate H2"
                ]
            )
        with hfcol2:
            heading_search = st.text_input("🔍 Search URL or Heading Text (H1/H2):", "")

        df_filtered_hd = df_headings.copy()

        if heading_filter == "Missing H1":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h1_status"] == "Missing"]
        elif heading_filter == "Duplicate H1":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h1_status"] == "Duplicate"]
        elif heading_filter == "Multiple H1s":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h1_status"] == "Multiple H1s"]
        elif heading_filter == "H1 Over 70 Chars":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h1_status"] == "Over 70 Chars"]
        elif heading_filter == "Missing H2":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h2_status"] == "Missing"]
        elif heading_filter == "Multiple H2s":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h2_status"] == "Multiple H2s"]
        elif heading_filter == "Duplicate H2":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h2_status"] == "Duplicate"]

        if heading_search:
            df_filtered_hd = df_filtered_hd[
                df_filtered_hd["url"].str.contains(heading_search, case=False, na=False) |
                df_filtered_hd["h1"].str.contains(heading_search, case=False, na=False) |
                df_filtered_hd["h2_first"].str.contains(heading_search, case=False, na=False)
            ]

        # Download button for filtered headings
        col_hdown1, col_hdown2 = st.columns([1, 4])
        with col_hdown1:
            csv_hd = generate_csv(df_filtered_hd)
            st.download_button(
                label=f"📥 Download Filtered Headings ({len(df_filtered_hd)} URLs)",
                data=csv_hd,
                file_name=f"headings_{heading_filter.replace(' ', '_').lower()}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_hdown2:
            st.caption(f"Showing **{len(df_filtered_hd)}** of **{total_pages}** pages matching filter: `{heading_filter}`")

        st.dataframe(
            df_filtered_hd[[
                "url", "h1", "h1_status", "h1_count", "h2_first", "h2_status", "h2_count", "status_code"
            ]],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Page URL"),
                "h1": st.column_config.TextColumn("H1 Heading"),
                "h1_status": st.column_config.TextColumn("H1 Status"),
                "h1_count": st.column_config.NumberColumn("H1 Count", format="%d"),
                "h2_first": st.column_config.TextColumn("First H2 Subheading"),
                "h2_status": st.column_config.TextColumn("H2 Status"),
                "h2_count": st.column_config.NumberColumn("H2 Count", format="%d"),
                "status_code": st.column_config.NumberColumn("HTTP Status", format="%d")
            },
            hide_index=True
        )

        with st.expander("💡 SEO Guide: Heading Hierarchy Best Practices"):
            st.markdown("""
            - **Exactly One H1 per page**: ✅ The H1 is the main topic of your page. Having 0 H1s hurts topical relevance; having multiple H1s dilutes ranking signals.
            - **Unique H1s**: ⚠️ Every page should have a unique H1 matching its unique title and search intent.
            - **Logical Structure**: Use H2 tags to divide sections under your primary H1 heading.
            """)

# ==============================================================================
# TAB 7: LINK ANALYSIS
# ==============================================================================
with tab_links:
    if not results:
        st.info("Run a crawl to see internal and external link connections.")
    else:
        df_links = results["df_links"]
        if df_links.empty:
            st.info("No outgoing links recorded.")
        else:
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                link_filter = st.selectbox("Filter Link Type", ["All Links", "Internal Only", "External Only", "Nofollow Links"])
            
            filtered_links = df_links.copy()
            if link_filter == "Internal Only":
                filtered_links = filtered_links[filtered_links["is_internal"] == True]
            elif link_filter == "External Only":
                filtered_links = filtered_links[filtered_links["is_internal"] == False]
            elif link_filter == "Nofollow Links":
                filtered_links = filtered_links[filtered_links["nofollow"] == True]

            st.caption(f"Total Discovered Links: **{len(filtered_links)}**")
            st.dataframe(
                filtered_links,
                use_container_width=True,
                column_config={
                    "source_url": st.column_config.LinkColumn("Source Page"),
                    "target_url": st.column_config.LinkColumn("Destination URL"),
                    "anchor_text": st.column_config.TextColumn("Anchor Text"),
                    "is_internal": st.column_config.CheckboxColumn("Internal"),
                    "nofollow": st.column_config.CheckboxColumn("Nofollow"),
                },
                hide_index=True
            )

# ==============================================================================
# TAB 8: IMAGES AUDIT
# ==============================================================================
with tab_images:
    if not results:
        st.info("Run a crawl to inspect image tags and missing alt attributes.")
    else:
        df_images = results["df_images"]
        if df_images.empty:
            st.info("No images detected on crawled pages.")
        else:
            missing_alt_count = len(df_images[df_images["has_alt"] == False])
            st.metric("Total Images Discovered", len(df_images), delta=f"{missing_alt_count} Missing Alt" if missing_alt_count else "All have Alt", delta_color="inverse" if missing_alt_count else "normal")
            
            filter_alt = st.checkbox("Show only images missing ALT text", value=False)
            display_imgs = df_images[df_images["has_alt"] == False] if filter_alt else df_images

            st.dataframe(
                display_imgs,
                use_container_width=True,
                column_config={
                    "page_url": st.column_config.LinkColumn("Found On Page"),
                    "image_url": st.column_config.LinkColumn("Image URL"),
                    "alt": st.column_config.TextColumn("Alt Text"),
                    "has_alt": st.column_config.CheckboxColumn("Has Alt Tag"),
                },
                hide_index=True
            )

# ==============================================================================
# TAB 9: SITE ARCHITECTURE GRAPH
# ==============================================================================
with tab_architecture:
    if not results:
        st.info("Run a crawl to visualize internal linking topology.")
    else:
        st.subheader("🧭 Internal Link Structure Visualization")
        st.caption("Interactive network graph mapping page relationship and cluster architecture:")
        df_links = results["df_links"]
        st.plotly_chart(create_site_architecture_graph(df_links), use_container_width=True)

# ==============================================================================
# TAB 10: SINGLE URL QUICK INSPECTOR
# ==============================================================================
with tab_inspector:
    st.subheader("🔍 Single URL Instant Inspector")
    st.caption("Perform an instant deep technical audit on any single URL without crawling the full website.")
    
    col_in1, col_in2 = st.columns([3, 1])
    with col_in1:
        inspect_url = st.text_input("Enter Page URL to Inspect:", value="https://example.com")
    with col_in2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_inspect = st.button("🔎 Inspect Page Now", type="primary", use_container_width=True)

    if btn_inspect and inspect_url:
        with st.spinner("Fetching and inspecting technical SEO factors..."):
            spider_temp = SEOSpider(start_url=inspect_url, max_pages=1, max_depth=0)
            fetch_res = spider_temp.fetch_single_url(inspect_url)
            audit = parse_page_seo(fetch_res)
            st.session_state["single_inspect_result"] = audit

    inspect_data = st.session_state.get("single_inspect_result")
    if inspect_data:
        st.markdown("---")
        col_i1, col_i2, col_i3, col_i4 = st.columns(4)
        with col_i1:
            st.metric("HTTP Status", inspect_data.get("status_code", 0))
        with col_i2:
            st.metric("Latency", f"{inspect_data.get('latency_ms', 0)} ms")
        with col_i3:
            st.metric("Word Count", inspect_data.get("word_count", 0))
        with col_i4:
            st.metric("Indexable", "Yes ✅" if inspect_data.get("is_indexable") else "No ❌")

        st.markdown("### 📋 Meta & Technical Elements")
        st.json({
            "Title": inspect_data.get("title"),
            "Title Length": inspect_data.get("title_length"),
            "Title Pixel Width": inspect_data.get("title_pixel_width"),
            "Meta Description": inspect_data.get("meta_description"),
            "H1 Heading": inspect_data.get("h1"),
            "Canonical URL": inspect_data.get("canonical_url"),
            "Canonical Status": inspect_data.get("canonical_status"),
            "Meta Robots": inspect_data.get("meta_robots") or "None (Default Index, Follow)",
            "Open Graph Title": inspect_data.get("og_title"),
            "Open Graph Image": inspect_data.get("og_image"),
            "Schema.org Types Detected": inspect_data.get("schema_types", []),
        })

        if inspect_data.get("issues"):
            st.markdown("### 🚨 Issues Detected on Page")
            st.dataframe(pd.DataFrame(inspect_data["issues"]), use_container_width=True)

# ==============================================================================
# TAB 11: ROBOTS & SITEMAP TOOL
# ==============================================================================
with tab_sitemap:
    st.subheader("🤖 Robots.txt & XML Sitemap Validator")
    st.caption("Verify crawl accessibility directives and XML sitemap integrity.")
    
    site_base = st.text_input("Enter Root Website URL:", value="https://example.com")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("📄 Fetch robots.txt", use_container_width=True):
            try:
                parsed = urlparse(site_base)
                robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
                r = requests.get(robots_url, timeout=10)
                st.write(f"Status: **{r.status_code}** (`{robots_url}`)")
                st.code(r.text, language="text")
            except Exception as e:
                st.error(f"Failed to fetch robots.txt: {e}")

    with col_r2:
        if st.button("🗺️ Fetch & Parse sitemap.xml", use_container_width=True):
            try:
                parsed = urlparse(site_base)
                sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
                r = requests.get(sitemap_url, timeout=10)
                st.write(f"Status: **{r.status_code}** (`{sitemap_url}`)")
                if r.status_code == 200:
                    root = ET.fromstring(r.content)
                    urls = [loc.text for loc in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
                    st.success(f"Discovered **{len(urls)}** URLs in sitemap:")
                    st.dataframe(pd.DataFrame(urls, columns=["Sitemap URL"]), use_container_width=True)
                else:
                    st.warning("sitemap.xml not found or returned non-200 code.")
            except Exception as e:
                st.error(f"Failed to parse sitemap: {e}")
