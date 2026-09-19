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
/* Custom Button Pills Styling for Filter Controls */
div[data-testid="stPills"] {
    gap: 8px !important;
    flex-wrap: wrap !important;
}
div[data-testid="stPills"] button {
    background: rgba(30, 41, 59, 0.75) !important;
    border: 1px solid rgba(71, 85, 105, 0.6) !important;
    color: #CBD5E1 !important;
    border-radius: 20px !important;
    padding: 6px 14px !important;
    font-size: 0.84rem !important;
    font-weight: 600 !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    cursor: pointer !important;
}
div[data-testid="stPills"] button:hover {
    border-color: #818CF8 !important;
    background: rgba(99, 102, 241, 0.18) !important;
    color: #FFFFFF !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stPills"] button[aria-selected="true"] {
    background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%) !important;
    border-color: #A5B4FC !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35) !important;
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)

# 3. Sidebar: Brand & Tools Suite Navigation
with st.sidebar:
    st.markdown("""
    <div style="padding: 0.5rem 0 1.2rem;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 2.2rem;">🕷️</span>
            <div>
                <div style="font-size: 1.35rem; font-weight: 800; color: #FFFFFF; line-height: 1.2; letter-spacing: -0.02em;">Amir's SEO Spider</div>
                <div style="font-size: 0.75rem; color: #818CF8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px;">Technical Audit Suite</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("##### 🧭 Tools & Modules")
    selected_tool = st.radio(
        "Select Active Tool",
        options=[
            "🕷️ SEO Spider & Crawler",
            "📊 SERP Rank Tracker (Coming Soon)",
            "🔗 Backlink Explorer (Coming Soon)",
            "⚡ Core Web Vitals (Coming Soon)",
            "🗺️ XML Sitemap Generator (Coming Soon)"
        ],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("""
    <div class="sidebar-box">
        <div style="font-weight: 700; color: #F8FAFC; margin-bottom: 8px; font-size: 0.85rem;">⚡ Crawl Engine Specs:</div>
        <div style="font-size: 0.82rem; color: #94A3B8; line-height: 1.65;">
            • <b>Fixed Capacity:</b> <span style="color:#34D399; font-weight:700;">10,000 URLs / Crawl</span><br>
            • <b>Depth Limit:</b> Max 10 Click Depth<br>
            • <b>Engine:</b> 12 Multi-Threaded Workers<br>
            • <b>Default Agent:</b> Chrome Desktop (WAF Safe)<br>
            • <b>Export:</b> Multi-Tab Excel Workbook
        </div>
    </div>
    """, unsafe_allow_html=True)

# 4. Main Page Header Banner
st.markdown("""
<div class="main-header" style="padding: 1.3rem 2rem; margin-bottom: 1.2rem;">
    <div style="font-size:1.55rem; font-weight:800; color:#FFFFFF; letter-spacing:-0.025em; display:flex; align-items:center; gap:8px;">
        <span>⚡ High-Speed Technical SEO Crawler</span>
    </div>
    <div style="font-size:0.92rem; color:#94A3B8; margin-top:4px;">
        Enter any website URL to audit internal links, canonical tags, titles, headings, and images up to 10,000 URLs.
    </div>
</div>
""", unsafe_allow_html=True)

# 5. Screaming Frog Top Search Bar
col_sf_url, col_sf_mode, col_sf_start, col_sf_clear = st.columns([5, 2.2, 1.3, 1.1])

with col_sf_url:
    target_url = st.text_input(
        "Enter URL to spider",
        value=st.session_state.get("cfg_target_url", "https://example.com"),
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
    btn_start = st.button("▶ Start", type="primary", use_container_width=True)

with col_sf_clear:
    btn_clear = st.button("🔄 Clear", use_container_width=True)

if btn_clear:
    st.session_state["crawl_results"] = None
    st.session_state["single_inspect_result"] = None
    st.rerun()

# Fixed Optimized Engine Parameters (10,000 URLs limit)
max_pages = 10000
max_depth = 10
concurrency = 12
timeout = 10
user_agent_choice = "Chrome (Windows 11)"
respect_robots = False
include_regex = ""
exclude_regex = ""

# 6. Crawl Execution Logic
if btn_start:
    if not target_url or not target_url.startswith(("http://", "https://")):
        st.error("⚠️ Please enter a valid URL starting with http:// or https://")
    else:
        st.session_state["cfg_target_url"] = target_url
        st.session_state["is_crawling"] = True
        progress_bar = st.progress(0, text=f"Initializing High-Speed SEO Spider Engine [{crawl_mode} Mode - 10,000 URL Limit]...")
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

if selected_tool != "🕷️ SEO Spider & Crawler":
    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 16px; padding: 3rem 2rem; text-align: center; margin-top: 1.5rem; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
        <div style="font-size: 3.2rem; margin-bottom: 1rem;">🚧</div>
        <h2 style="font-size: 1.85rem; font-weight: 800; color: #FFFFFF; margin-bottom: 0.5rem;">{selected_tool}</h2>
        <p style="color: #94A3B8; font-size: 1.05rem; max-width: 620px; margin: 0 auto 1.5rem; line-height: 1.6;">
            This module is currently being built for <b>Amir's SEO Suite</b>. In the sidebar, select <b>'🕷️ SEO Spider & Crawler'</b> to use the active technical crawler.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Main Application Tabs
tab_overview, tab_issues, tab_pages, tab_responses, tab_canonicals, tab_titles, tab_descriptions, tab_headings, tab_links, tab_images, tab_architecture, tab_inspector, tab_sitemap = st.tabs([
    "📊 Overview",
    "🚨 Issues & Fixes",
    "📑 Internal Pages",
    "🚦 Response Codes",
    "🎯 Canonicals",
    "🏷️ Page Titles",
    "📝 Meta Description",
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
                Enter your target URL in the top search bar, select your crawl mode, and click Start. The crawler will audit internal links, canonical tags, metadata, status codes, and headings up to 10,000 URLs.
            </p>
        </div>
        """, unsafe_allow_html=True)

        col_demo1, col_demo2, col_demo3 = st.columns([1, 2, 1])
        with col_demo2:
            if st.button("🚀 Load Sample Target (books.toscrape.com)", use_container_width=True):
                st.session_state["cfg_target_url"] = "https://books.toscrape.com"
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
        col_g1, col_g2, col_g3 = st.columns([1, 1, 1.6])
        with col_g1:
            st.plotly_chart(create_health_gauge(summary["health_score"]), use_container_width=True, config={'displayModeBar': False})
        with col_g2:
            st.plotly_chart(create_status_code_chart(df_pages), use_container_width=True, config={'displayModeBar': False})
        with col_g3:
            st.plotly_chart(create_issues_bar_chart(df_issues), use_container_width=True, config={'displayModeBar': False})

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
            total_issues_count = len(df_issues)
            err_count = len(df_issues[df_issues["type"] == "Error"])
            warn_count = len(df_issues[df_issues["type"] == "Warning"])
            not_count = len(df_issues[df_issues["type"] == "Notice"])

            # 4 Crisp Metric Summary Cards
            col_im1, col_im2, col_im3, col_im4 = st.columns(4)
            with col_im1:
                st.metric("Total Issues", f"{total_issues_count}", delta=f"{len(df_issues['url'].unique())} pages affected")
            with col_im2:
                st.metric("Critical Errors", f"{err_count}", delta="Requires immediate fix" if err_count else "None", delta_color="inverse" if err_count else "normal")
            with col_im3:
                st.metric("Warnings", f"{warn_count}", delta="Action recommended" if warn_count else "None", delta_color="inverse" if warn_count else "normal")
            with col_im4:
                st.metric("Notices", f"{not_count}", delta="Informational" if not_count else "None", delta_color="normal")

            st.markdown("<div style='margin: 0.8rem 0 0.4rem;'></div>", unsafe_allow_html=True)

            # 1. Severity Filter Buttons (st.pills)
            sev_options = [
                f"All Severities ({total_issues_count})",
                f"🔴 Errors ({err_count})",
                f"🟡 Warnings ({warn_count})",
                f"🔵 Notices ({not_count})"
            ]
            selected_sev = st.pills(
                "Filter by Severity:",
                options=sev_options,
                default=f"All Severities ({total_issues_count})",
                selection_mode="single",
                key="pills_sev_filter"
            )

            # Resolve Active Severity
            if not selected_sev or "All Severities" in selected_sev:
                active_severities = ["Error", "Warning", "Notice"]
                sev_key_suffix = "all"
            elif "Errors" in selected_sev:
                active_severities = ["Error"]
                sev_key_suffix = "error"
            elif "Warnings" in selected_sev:
                active_severities = ["Warning"]
                sev_key_suffix = "warning"
            elif "Notices" in selected_sev:
                active_severities = ["Notice"]
                sev_key_suffix = "notice"
            else:
                active_severities = ["Error", "Warning", "Notice"]
                sev_key_suffix = "all"

            # Filter issues by selected severity FIRST so category buttons only show relevant categories!
            df_sev_subset = df_issues[df_issues["type"].isin(active_severities)]
            sev_total_count = len(df_sev_subset)

            # Resolve Category Counts strictly from the filtered severity subset
            cat_counts = df_sev_subset["category"].value_counts().to_dict()
            cat_options = [f"All Categories ({sev_total_count})"] + [
                f"{cat} ({cat_counts[cat]})" for cat in sorted(cat_counts.keys())
            ]
            
            selected_cat = st.pills(
                "Filter by Issue Category:",
                options=cat_options,
                default=f"All Categories ({sev_total_count})",
                selection_mode="single",
                key=f"pills_cat_filter_{sev_key_suffix}"
            )

            # Resolve Active Category
            if not selected_cat or "All Categories" in selected_cat:
                active_category = None
            else:
                active_category = selected_cat.rsplit(" (", 1)[0]

            filtered_issues = df_sev_subset.copy()
            if active_category:
                filtered_issues = filtered_issues[filtered_issues["category"] == active_category]

            # Search Bar & CSV Download Toolbar
            col_fs1, col_fs2 = st.columns([3, 1.2])
            with col_fs1:
                issue_search = st.text_input("🔍 Search issues, fix recommendations, or URLs:", "", key="issues_search_box")
            with col_fs2:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                csv_iss = generate_csv(filtered_issues)
                st.download_button(
                    label=f"📥 Download Filtered Issues ({len(filtered_issues)})",
                    data=csv_iss,
                    file_name="audit_issues_filtered.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            if issue_search:
                filtered_issues = filtered_issues[
                    filtered_issues["url"].str.contains(issue_search, case=False, na=False) |
                    filtered_issues["issue"].str.contains(issue_search, case=False, na=False) |
                    filtered_issues["recommendation"].str.contains(issue_search, case=False, na=False) |
                    filtered_issues["category"].str.contains(issue_search, case=False, na=False)
                ]

            st.caption(f"Showing **{len(filtered_issues)}** of **{total_issues_count}** technical issues matching active button filters:")
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
# TAB 4: RESPONSE CODES & HTTP STATUS AUDIT
# ==============================================================================
with tab_responses:
    if not results:
        st.info("Run a crawl to audit HTTP response codes, redirection types, errors, and orphan pages.")
    else:
        df_pages = results["df_pages"]
        total_resp_pages = len(df_pages)

        st.subheader("🚦 Response Codes & HTTP Status Breakdown")
        st.caption("Inspect HTTP status codes, redirection chains, server errors, blocked resources, and orphan pages with 0 internal links.")

        # KPI Metrics Row
        c_2xx = len(df_pages[(df_pages["status_code"] >= 200) & (df_pages["status_code"] < 300)])
        c_3xx = len(df_pages[(df_pages["status_code"] >= 300) & (df_pages["status_code"] < 400)])
        c_4xx = len(df_pages[(df_pages["status_code"] >= 400) & (df_pages["status_code"] < 500)])
        c_5xx = len(df_pages[(df_pages["status_code"] >= 500) & (df_pages["status_code"] < 600)])
        c_orphan = int(df_pages["is_orphan"].sum()) if "is_orphan" in df_pages.columns else 0

        rm1, rm2, rm3, rm4, rm5 = st.columns(5)
        rm1.metric("Success (2xx)", f"{c_2xx}", delta=f"{round(c_2xx/max(total_resp_pages,1)*100)}% of pages")
        rm2.metric("Redirection (3xx)", f"{c_3xx}", delta="Redirects" if c_3xx else None)
        rm3.metric("Client Error (4xx)", f"{c_4xx}", delta="Broken links" if c_4xx else None, delta_color="inverse")
        rm4.metric("Server Error (5xx)", f"{c_5xx}", delta="Critical" if c_5xx else None, delta_color="inverse")
        rm5.metric("Orphan URLs (0 Inlinks)", f"{c_orphan}", delta="Needs internal links" if c_orphan else None, delta_color="inverse")

        st.markdown("<div style='margin: 0.8rem 0 0.4rem;'></div>", unsafe_allow_html=True)

        # Build Screaming Frog Filter Options matching user's screenshot + Orphan pages
        c_robots = len(df_pages[df_pages["response_category"] == "Blocked by Robots.txt"]) if "response_category" in df_pages.columns else 0
        c_blocked_res = len(df_pages[df_pages["response_category"] == "Blocked Resource"]) if "response_category" in df_pages.columns else 0
        c_no_resp = len(df_pages[df_pages["response_category"] == "No Response"]) if "response_category" in df_pages.columns else 0
        c_js_red = len(df_pages[df_pages.get("has_js_redirect", False) == True]) if "has_js_redirect" in df_pages.columns else 0
        c_meta_red = len(df_pages[df_pages.get("has_meta_refresh", False) == True]) if "has_meta_refresh" in df_pages.columns else 0

        sf_options = [
            f"All ({total_resp_pages})",
            f"Blocked by Robots.txt ({c_robots})",
            f"Blocked Resource ({c_blocked_res})",
            f"No Response ({c_no_resp})",
            f"Success (2xx) ({c_2xx})",
            f"Redirection (3xx) ({c_3xx})",
            f"Redirection (JavaScript) ({c_js_red})",
            f"Redirection (Meta Refresh) ({c_meta_red})",
            f"Client Error (4xx) ({c_4xx})",
            f"Server Error (5xx) ({c_5xx})",
            f"Orphan URLs (0 Inlinks) ({c_orphan})"
        ]

        rfcol1, rfcol2 = st.columns([1.2, 1.8])
        with rfcol1:
            resp_filter = st.selectbox(
                "Filter by Response Code:",
                options=sf_options,
                index=0,
                key="sb_response_code_filter"
            )
        with rfcol2:
            resp_search = st.text_input(
                "🔍 Search URL, Status Code, or Response Description:",
                "",
                key="txt_response_code_search"
            )

        # Filter the DataFrame
        df_resp_filtered = df_pages.copy()

        filter_choice = resp_filter.split(" (")[0]
        if filter_choice == "Blocked by Robots.txt":
            df_resp_filtered = df_resp_filtered[df_resp_filtered["response_category"] == "Blocked by Robots.txt"]
        elif filter_choice == "Blocked Resource":
            df_resp_filtered = df_resp_filtered[df_resp_filtered["response_category"] == "Blocked Resource"]
        elif filter_choice == "No Response":
            df_resp_filtered = df_resp_filtered[df_resp_filtered["response_category"] == "No Response"]
        elif filter_choice == "Success (2xx)":
            df_resp_filtered = df_resp_filtered[(df_resp_filtered["status_code"] >= 200) & (df_resp_filtered["status_code"] < 300)]
        elif filter_choice == "Redirection (3xx)":
            df_resp_filtered = df_resp_filtered[(df_resp_filtered["status_code"] >= 300) & (df_resp_filtered["status_code"] < 400)]
        elif filter_choice == "Redirection (JavaScript)":
            df_resp_filtered = df_resp_filtered[df_resp_filtered.get("has_js_redirect", False) == True]
        elif filter_choice == "Redirection (Meta Refresh)":
            df_resp_filtered = df_resp_filtered[df_resp_filtered.get("has_meta_refresh", False) == True]
        elif filter_choice == "Client Error (4xx)":
            df_resp_filtered = df_resp_filtered[(df_resp_filtered["status_code"] >= 400) & (df_resp_filtered["status_code"] < 500)]
        elif filter_choice == "Server Error (5xx)":
            df_resp_filtered = df_resp_filtered[(df_resp_filtered["status_code"] >= 500) & (df_resp_filtered["status_code"] < 600)]
        elif filter_choice == "Orphan URLs (0 Inlinks)":
            df_resp_filtered = df_resp_filtered[df_resp_filtered.get("inlinks_count", 0) == 0]

        if resp_search:
            status_desc_col = df_resp_filtered["status_description"] if "status_description" in df_resp_filtered.columns else ""
            final_url_col = df_resp_filtered["final_url"] if "final_url" in df_resp_filtered.columns else ""
            df_resp_filtered = df_resp_filtered[
                df_resp_filtered["url"].str.contains(resp_search, case=False, na=False) |
                status_desc_col.astype(str).str.contains(resp_search, case=False, na=False) |
                df_resp_filtered["status_code"].astype(str).str.contains(resp_search, case=False, na=False) |
                final_url_col.astype(str).str.contains(resp_search, case=False, na=False)
            ]

        # Download button
        col_rdown1, col_rdown2 = st.columns([1.2, 3.8])
        with col_rdown1:
            csv_resp = generate_csv(df_resp_filtered)
            st.download_button(
                label=f"📥 Download Filtered ({len(df_resp_filtered)} URLs)",
                data=csv_resp,
                file_name=f"response_codes_{filter_choice.replace(' ', '_').lower()}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_rdown2:
            st.caption(f"Showing **{len(df_resp_filtered)}** of **{total_resp_pages}** URLs matching filter: `{filter_choice}`")

        # Table Display
        resp_cols = [
            "url", "status_code", "status_description", "response_category",
            "inlinks_count", "internal_outlinks_count", "final_url", "latency_ms",
            "content_type", "is_indexable"
        ]
        available_resp_cols = [c for c in resp_cols if c in df_resp_filtered.columns]

        st.dataframe(
            df_resp_filtered[available_resp_cols],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Page URL"),
                "status_code": st.column_config.NumberColumn("Status Code", format="%d"),
                "status_description": st.column_config.TextColumn("Response Description"),
                "response_category": st.column_config.TextColumn("Response Category"),
                "inlinks_count": st.column_config.NumberColumn("Inlinks (Inbound)", help="Number of internal pages linking to this URL. 0 = Orphan Page!"),
                "internal_outlinks_count": st.column_config.NumberColumn("Outlinks"),
                "final_url": st.column_config.LinkColumn("Redirect Target URL"),
                "latency_ms": st.column_config.NumberColumn("Latency", format="%.0f ms"),
                "content_type": st.column_config.TextColumn("Content Type"),
                "is_indexable": st.column_config.CheckboxColumn("Indexable"),
            },
            hide_index=True
        )

        with st.expander("💡 SEO Guide: Response Codes & Orphan Pages Technical Reference"):
            st.markdown("""
            - **Success (2xx)**: HTTP 200 OK indicates the page was fetched successfully and is fully indexable by search engine bots.
            - **Redirection (3xx)**: Permanent redirects (301, 308) pass equity; temporary redirects (302, 307) signify short-term moves.
            - **Redirection (JavaScript & Meta Refresh)**: Client-side redirects cause crawling latency and index delays. Always prioritize 301 server-side redirects.
            - **Client Error (4xx)**: 404 Not Found or 410 Gone mean broken links. Internal links pointing to 4xx URLs should be fixed or removed.
            - **Server Error (5xx)**: 500, 502, 503, 504 errors indicate host/backend instability. High 5xx rates degrade Google crawl frequency.
            - **Blocked by Robots.txt / Blocked Resource**: URL is barred from crawling by robots.txt directives or authorization.
            - **Orphan URLs (0 Inlinks)**: An orphan page has **zero internal links** pointing to it from anywhere on the website. Search engines may not discover or rank orphan pages unless found via external links or XML sitemaps. Fix by adding contextual internal links from parent categories or menus.
            """)

# ==============================================================================
# TAB 5: CANONICAL TAGS AUDIT ("Ye Page -> Iska Canonical Ye")
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
# TAB 5: PAGE TITLES AUDIT
# ==============================================================================
with tab_titles:
    if not results:
        st.info("Run a crawl to inspect page titles, detect duplicate cannibalization, and verify SERP length.")
    else:
        df_pages = results["df_pages"].copy()
        total_pages = len(df_pages)

        # Prepare Clean Title Columns
        df_titles = df_pages[[
            "url", "status_code", "title", "title_length", "title_pixel_width", "is_indexable"
        ]].copy()

        # Map Duplicate Partners (Only 200 OK & Indexable pages count toward duplicates!)
        valid_titles_df = df_titles[
            (df_titles["status_code"] == 200) & 
            (df_titles["is_indexable"] == True) & 
            (df_titles["title"].str.strip() != "")
        ]
        title_to_urls = valid_titles_df.groupby("title")["url"].apply(list).to_dict()
        dup_titles_set = {t for t, urls in title_to_urls.items() if len(urls) > 1}

        def get_title_dup_info(row):
            if row.get("status_code", 200) != 200 or not row.get("is_indexable", True):
                return 0, "— (Non-Indexable / Redirect)"
            t = str(row["title"]).strip()
            if t and t in title_to_urls and len(title_to_urls[t]) > 1:
                all_urls = title_to_urls[t]
                other_urls = [u for u in all_urls if u != row["url"]]
                return len(all_urls), " | ".join(other_urls)
            return 1, "—"

        dup_title_info = df_titles.apply(get_title_dup_info, axis=1)
        df_titles["duplicate_count"] = [d[0] for d in dup_title_info]
        df_titles["duplicate_matches"] = [d[1] for d in dup_title_info]

        # Title Status Tag
        def get_title_status(row):
            code = row.get("status_code", 200)
            if 300 <= code < 400:
                return f"Redirect ({code})"
            if code >= 400:
                return f"Error ({code})"
            t = str(row["title"]).strip()
            if not t:
                return "Missing"
            if row.get("is_indexable", True) and t in dup_titles_set:
                return "Duplicate"
            if row["title_length"] > 60 or row["title_pixel_width"] > 600:
                return "Over 60 Chars (>600px)"
            if row["title_length"] < 30:
                return "Below 30 Chars"
            return "OK"

        df_titles["title_status"] = df_titles.apply(get_title_status, axis=1)

        # Title Metrics
        ok_titles_count = len(df_titles[df_titles["title_status"] == "OK"])
        missing_titles_count = len(df_titles[df_titles["title_status"] == "Missing"])
        dup_titles_count = len(df_titles[df_titles["title_status"] == "Duplicate"])
        over_titles_count = len(df_titles[df_titles["title_status"] == "Over 60 Chars (>600px)"])
        below_titles_count = len(df_titles[df_titles["title_status"] == "Below 30 Chars"])

        st.subheader("🏷️ Page Titles Audit")
        st.caption("Deep inspection of Page Titles — detect missing titles, isolate duplicate cannibalization with exact matching partner URLs, and verify SERP pixel limits.")

        # 5 Metric Cards
        tm1, tm2, tm3, tm4, tm5 = st.columns(5)
        tm1.metric("Optimal Titles (OK)", f"{ok_titles_count}", delta=f"{round(ok_titles_count/max(total_pages,1)*100)}% of pages")
        tm2.metric("Duplicate Titles", f"{dup_titles_count}", delta=f"{len(dup_titles_set)} unique shared" if dup_titles_count else "Unique", delta_color="inverse" if dup_titles_count else "normal")
        tm3.metric("Missing Titles", f"{missing_titles_count}", delta="Requires <title>" if missing_titles_count else "None", delta_color="inverse" if missing_titles_count else "normal")
        tm4.metric("Over 60 Chars (>600px)", f"{over_titles_count}", delta="SERP Truncated" if over_titles_count else "None", delta_color="inverse" if over_titles_count else "normal")
        tm5.metric("Below 30 Chars", f"{below_titles_count}", delta="Too short" if below_titles_count else "Good", delta_color="inverse" if below_titles_count else "normal")

        # Filters and Search
        fcol1, fcol2 = st.columns([1.5, 2])
        with fcol1:
            title_filter = st.selectbox(
                "Filter Titles by Status:",
                [
                    "All Pages",
                    "Duplicate Title",
                    "Missing Title",
                    "Title Over 60 Chars (>600px)",
                    "Title Below 30 Chars",
                    "Optimal Title (OK)"
                ]
            )
        with fcol2:
            title_search = st.text_input("🔍 Search URL, Page Title, or Duplicate Partner URL:", "", key="title_search_input")

        df_filtered_t = df_titles.copy()

        if title_filter == "Duplicate Title":
            df_filtered_t = df_filtered_t[df_filtered_t["title_status"] == "Duplicate"]
        elif title_filter == "Missing Title":
            df_filtered_t = df_filtered_t[df_filtered_t["title_status"] == "Missing"]
        elif title_filter == "Title Over 60 Chars (>600px)":
            df_filtered_t = df_filtered_t[df_filtered_t["title_status"] == "Over 60 Chars (>600px)"]
        elif title_filter == "Title Below 30 Chars":
            df_filtered_t = df_filtered_t[df_filtered_t["title_status"] == "Below 30 Chars"]
        elif title_filter == "Optimal Title (OK)":
            df_filtered_t = df_filtered_t[df_filtered_t["title_status"] == "OK"]

        if title_search:
            df_filtered_t = df_filtered_t[
                df_filtered_t["url"].str.contains(title_search, case=False, na=False) |
                df_filtered_t["title"].str.contains(title_search, case=False, na=False) |
                df_filtered_t["duplicate_matches"].str.contains(title_search, case=False, na=False)
            ]

        # Download button for filtered data
        col_down1, col_down2 = st.columns([1, 4])
        with col_down1:
            csv_t = generate_csv(df_filtered_t)
            st.download_button(
                label=f"📥 Download Filtered Titles ({len(df_filtered_t)} URLs)",
                data=csv_t,
                file_name=f"page_titles_{title_filter.replace(' ', '_').lower()}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_down2:
            st.caption(f"Showing **{len(df_filtered_t)}** of **{total_pages}** pages matching filter: `{title_filter}`")

        # Display Dataframe with Duplicate Partner URL(s)
        st.dataframe(
            df_filtered_t[[
                "url", "title", "title_status", "duplicate_matches", "duplicate_count",
                "title_length", "title_pixel_width", "status_code"
            ]],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Page URL"),
                "title": st.column_config.TextColumn("Page Title"),
                "title_status": st.column_config.TextColumn("Title Status"),
                "duplicate_matches": st.column_config.TextColumn("Duplicate With (Other URL(s))", help="The exact other URLs on your site sharing this identical title"),
                "duplicate_count": st.column_config.NumberColumn("Total Copies", format="%d", help="Total number of crawled pages with this exact title"),
                "title_length": st.column_config.NumberColumn("Chars"),
                "title_pixel_width": st.column_config.NumberColumn("Pixels (px)"),
                "status_code": st.column_config.NumberColumn("HTTP Status", format="%d")
            },
            hide_index=True
        )

        # Grouped Duplicate Title Clusters Explorer
        if dup_titles_set:
            with st.expander(f"👥 View Grouped Duplicate Titles Clusters ({len(dup_titles_set)} Unique Duplicate Groups)", expanded=(title_filter == "Duplicate Title")):
                st.markdown("Here is the grouped breakdown of duplicate titles and every competing URL:")
                for dup_t in sorted(dup_titles_set, key=lambda x: len(title_to_urls[x]), reverse=True):
                    matched_urls = title_to_urls[dup_t]
                    st.markdown(f"**📌 Title:** `{dup_t}` — *(Shared across **{len(matched_urls)}** pages)*")
                    dup_cluster_df = pd.DataFrame({
                        "Matching Page URL": matched_urls,
                        "Status Code": [df_titles[df_titles["url"] == u]["status_code"].values[0] if not df_titles[df_titles["url"] == u].empty else 200 for u in matched_urls]
                    })
                    st.dataframe(dup_cluster_df, use_container_width=True, hide_index=True)
                    st.markdown("<hr style='margin:0.4rem 0; border-color:#334155;'>", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("🔍 Google SERP Preview Simulator")
        selected_url = st.selectbox("Select Page URL to preview Google Search snippet:", options=df_pages["url"].tolist(), key="serp_title_select")
        
        if selected_url:
            row = df_pages[df_pages["url"] == selected_url].iloc[0]
            p_title = row.get("title") or "Untitled Document"
            p_url = row.get("url") or ""
            p_desc = row.get("meta_description") or "No meta description provided for this page. Search engines will generate a snippet from page body text."
            p_pixels = row.get("title_pixel_width", 0)

            parsed_p = urlparse(p_url)
            domain_display = parsed_p.netloc

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

            col_sp1, col_sp2 = st.columns(2)
            col_sp1.metric("Title Length", f"{len(p_title)} chars", delta="Optimal (30-60)" if 30 <= len(p_title) <= 60 else "Check Length")
            col_sp2.metric("Title Pixel Width", f"{p_pixels} px", delta="Fits Google Desktop (<600px)" if p_pixels <= 600 else "Truncated by Google (>600px)", delta_color="normal" if p_pixels <= 600 else "inverse")

# ==============================================================================
# TAB 6: META DESCRIPTIONS AUDIT
# ==============================================================================
with tab_descriptions:
    if not results:
        st.info("Run a crawl to inspect meta descriptions, detect duplicate snippets, and verify length limits.")
    else:
        df_pages = results["df_pages"].copy()
        total_pages = len(df_pages)

        # Prepare Clean Meta Description Columns
        df_desc = df_pages[[
            "url", "status_code", "meta_description", "meta_description_length", "is_indexable"
        ]].copy()

        # Map Duplicate Partners (Only 200 OK & Indexable pages count toward duplicates!)
        valid_desc_df = df_desc[
            (df_desc["status_code"] == 200) & 
            (df_desc["is_indexable"] == True) & 
            (df_desc["meta_description"].str.strip() != "")
        ]
        desc_to_urls = valid_desc_df.groupby("meta_description")["url"].apply(list).to_dict()
        dup_desc_set = {d for d, urls in desc_to_urls.items() if len(urls) > 1}

        def get_desc_dup_info(row):
            if row.get("status_code", 200) != 200 or not row.get("is_indexable", True):
                return 0, "— (Non-Indexable / Redirect)"
            d = str(row["meta_description"]).strip()
            if d and d in desc_to_urls and len(desc_to_urls[d]) > 1:
                all_urls = desc_to_urls[d]
                other_urls = [u for u in all_urls if u != row["url"]]
                return len(all_urls), " | ".join(other_urls)
            return 1, "—"

        dup_desc_info = df_desc.apply(get_desc_dup_info, axis=1)
        df_desc["duplicate_count"] = [d[0] for d in dup_desc_info]
        df_desc["duplicate_matches"] = [d[1] for d in dup_desc_info]

        # Meta Description Status Tag
        def get_desc_status(row):
            code = row.get("status_code", 200)
            if 300 <= code < 400:
                return f"Redirect ({code})"
            if code >= 400:
                return f"Error ({code})"
            d = str(row["meta_description"]).strip()
            if not d:
                return "Missing"
            if row.get("is_indexable", True) and d in dup_desc_set:
                return "Duplicate"
            if row["meta_description_length"] > 160:
                return "Over 160 Chars"
            if row["meta_description_length"] < 70:
                return "Below 70 Chars"
            return "OK"

        df_desc["meta_desc_status"] = df_desc.apply(get_desc_status, axis=1)

        # Meta Description Metrics
        ok_desc_count = len(df_desc[df_desc["meta_desc_status"] == "OK"])
        missing_desc_count = len(df_desc[df_desc["meta_desc_status"] == "Missing"])
        dup_desc_count = len(df_desc[df_desc["meta_desc_status"] == "Duplicate"])
        over_desc_count = len(df_desc[df_desc["meta_desc_status"] == "Over 160 Chars"])
        below_desc_count = len(df_desc[df_desc["meta_desc_status"] == "Below 70 Chars"])

        st.subheader("📝 Meta Description Audit")
        st.caption("Deep inspection of Meta Descriptions — isolate duplicate snippets with matching partner URLs, detect missing descriptions, and optimize SERP click-through rate.")

        # 5 Metric Cards
        dm1, dm2, dm3, dm4, dm5 = st.columns(5)
        dm1.metric("Optimal Descriptions (OK)", f"{ok_desc_count}", delta=f"{round(ok_desc_count/max(total_pages,1)*100)}% of pages")
        dm2.metric("Duplicate Descriptions", f"{dup_desc_count}", delta=f"{len(dup_desc_set)} unique shared" if dup_desc_count else "Unique", delta_color="inverse" if dup_desc_count else "normal")
        dm3.metric("Missing Descriptions", f"{missing_desc_count}", delta="Needs snippet" if missing_desc_count else "None", delta_color="inverse" if missing_desc_count else "normal")
        dm4.metric("Over 160 Chars", f"{over_desc_count}", delta="SERP Truncated" if over_desc_count else "None", delta_color="inverse" if over_desc_count else "normal")
        dm5.metric("Below 70 Chars", f"{below_desc_count}", delta="Too short" if below_desc_count else "Good", delta_color="inverse" if below_desc_count else "normal")

        # Filters and Search
        dfcol1, dfcol2 = st.columns([1.5, 2])
        with dfcol1:
            desc_filter = st.selectbox(
                "Filter Meta Descriptions by Status:",
                [
                    "All Pages",
                    "Duplicate Meta Description",
                    "Missing Meta Description",
                    "Meta Desc Over 160 Chars",
                    "Meta Desc Below 70 Chars",
                    "Optimal Meta Description (OK)"
                ]
            )
        with dfcol2:
            desc_search = st.text_input("🔍 Search URL, Meta Description, or Duplicate Partner URL:", "", key="desc_search_input")

        df_filtered_d = df_desc.copy()

        if desc_filter == "Duplicate Meta Description":
            df_filtered_d = df_filtered_d[df_filtered_d["meta_desc_status"] == "Duplicate"]
        elif desc_filter == "Missing Meta Description":
            df_filtered_d = df_filtered_d[df_filtered_d["meta_desc_status"] == "Missing"]
        elif desc_filter == "Meta Desc Over 160 Chars":
            df_filtered_d = df_filtered_d[df_filtered_d["meta_desc_status"] == "Over 160 Chars"]
        elif desc_filter == "Meta Desc Below 70 Chars":
            df_filtered_d = df_filtered_d[df_filtered_d["meta_desc_status"] == "Below 70 Chars"]
        elif desc_filter == "Optimal Meta Description (OK)":
            df_filtered_d = df_filtered_d[df_filtered_d["meta_desc_status"] == "OK"]

        if desc_search:
            df_filtered_d = df_filtered_d[
                df_filtered_d["url"].str.contains(desc_search, case=False, na=False) |
                df_filtered_d["meta_description"].str.contains(desc_search, case=False, na=False) |
                df_filtered_d["duplicate_matches"].str.contains(desc_search, case=False, na=False)
            ]

        # Download button for filtered data
        col_ddown1, col_ddown2 = st.columns([1, 4])
        with col_ddown1:
            csv_d = generate_csv(df_filtered_d)
            st.download_button(
                label=f"📥 Download Filtered Meta Descriptions ({len(df_filtered_d)} URLs)",
                data=csv_d,
                file_name=f"meta_descriptions_{desc_filter.replace(' ', '_').lower()}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col_ddown2:
            st.caption(f"Showing **{len(df_filtered_d)}** of **{total_pages}** pages matching filter: `{desc_filter}`")

        # Display Dataframe with Duplicate Partner URL(s)
        st.dataframe(
            df_filtered_d[[
                "url", "meta_description", "meta_desc_status", "duplicate_matches", "duplicate_count",
                "meta_description_length", "status_code"
            ]],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Page URL"),
                "meta_description": st.column_config.TextColumn("Meta Description"),
                "meta_desc_status": st.column_config.TextColumn("Description Status"),
                "duplicate_matches": st.column_config.TextColumn("Duplicate With (Other URL(s))", help="The exact other URLs on your site sharing this identical description"),
                "duplicate_count": st.column_config.NumberColumn("Total Copies", format="%d", help="Total number of crawled pages with this exact description"),
                "meta_description_length": st.column_config.NumberColumn("Chars (Length)"),
                "status_code": st.column_config.NumberColumn("HTTP Status", format="%d")
            },
            hide_index=True
        )

        # Grouped Duplicate Meta Descriptions Clusters Explorer
        if dup_desc_set:
            with st.expander(f"👥 View Grouped Duplicate Descriptions Clusters ({len(dup_desc_set)} Unique Duplicate Groups)", expanded=(desc_filter == "Duplicate Meta Description")):
                st.markdown("Here is the grouped breakdown of duplicate meta descriptions and all URLs sharing them:")
                for dup_d in sorted(dup_desc_set, key=lambda x: len(desc_to_urls[x]), reverse=True):
                    matched_urls = desc_to_urls[dup_d]
                    st.markdown(f"**📌 Meta Description:** `{dup_d}` — *(Shared across **{len(matched_urls)}** pages)*")
                    dup_cluster_df = pd.DataFrame({
                        "Matching Page URL": matched_urls,
                        "Status Code": [df_desc[df_desc["url"] == u]["status_code"].values[0] if not df_desc[df_desc["url"] == u].empty else 200 for u in matched_urls]
                    })
                    st.dataframe(dup_cluster_df, use_container_width=True, hide_index=True)
                    st.markdown("<hr style='margin:0.4rem 0; border-color:#334155;'>", unsafe_allow_html=True)

        with st.expander("💡 SEO Guide: Meta Description Best Practices"):
            st.markdown("""
            - **Unique Snippets for Every Page**: ⚠️ Identical meta descriptions result in duplicate snippets across search results, harming CTR.
            - **Optimal Length (70 - 160 characters)**: Keeps your snippet within Google's desktop and mobile viewports without truncation ellipses (`...`).
            - **Compelling Call-to-Action**: Encourage clicks with clear value propositions and relevant primary keywords.
            """)

# ==============================================================================
# TAB 7: HEADINGS (H1/H2) HIERARCHY AUDIT
# ==============================================================================
with tab_headings:
    if not results:
        st.info("Run a crawl to inspect H1 and H2 tags, missing headings, and duplicate hierarchy.")
    else:
        df_pages = results["df_pages"].copy()
        total_pages = len(df_pages)

        # Prepare Clean Heading Columns with H1-1, H1-2, H2-1, H2-2
        cols_to_extract = ["url", "h1", "h1_count", "h2_first", "h2_count", "status_code", "is_indexable"]
        if "h1_2" in df_pages.columns:
            cols_to_extract.append("h1_2")
        if "h2_2" in df_pages.columns:
            cols_to_extract.append("h2_2")

        df_headings = df_pages[cols_to_extract].copy()
        if "h1_2" not in df_headings.columns:
            df_headings["h1_2"] = ""
        if "h2_2" not in df_headings.columns:
            df_headings["h2_2"] = ""

        # Calculate H1 and H2 duplicates with partner URL matching (Only 200 OK & Indexable pages!)
        valid_h1_df = df_headings[
            (df_headings["status_code"] == 200) & 
            (df_headings["is_indexable"] == True) & 
            (df_headings["h1"].str.strip() != "")
        ]
        h1_to_urls = valid_h1_df.groupby("h1")["url"].apply(list).to_dict()
        dup_h1_set = {h for h, urls in h1_to_urls.items() if len(urls) > 1}

        def get_h1_dup_info(row):
            if row.get("status_code", 200) != 200 or not row.get("is_indexable", True):
                return 0, "— (Non-Indexable / Redirect)"
            h = str(row["h1"]).strip()
            if h and h in h1_to_urls and len(h1_to_urls[h]) > 1:
                all_urls = h1_to_urls[h]
                other_urls = [u for u in all_urls if u != row["url"]]
                return len(all_urls), " | ".join(other_urls)
            return 1, "—"

        dup_h1_info = df_headings.apply(get_h1_dup_info, axis=1)
        df_headings["duplicate_h1_count"] = [d[0] for d in dup_h1_info]
        df_headings["duplicate_h1_matches"] = [d[1] for d in dup_h1_info]

        h2_counts = df_headings[df_headings["h2_first"].str.strip() != ""]["h2_first"].value_counts()
        dup_h2_set = set(h2_counts[h2_counts > 1].index)

        # H1 Status Tag
        def get_h1_status(row):
            code = row.get("status_code", 200)
            if 300 <= code < 400:
                return f"Redirect ({code})"
            if code >= 400:
                return f"Error ({code})"
            h = str(row["h1"]).strip()
            c = row.get("h1_count", 0)
            if not h or c == 0:
                return "Missing"
            if c > 1:
                return "Multiple H1s"
            if row.get("is_indexable", True) and h in dup_h1_set:
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
        st.caption("Inspect heading tags across your site — view primary and secondary H1s (H1-1 / H1-2), detect multiple H1 tags per page, and catch duplicate cannibalization.")

        # 5 Metric Cards
        hm1, hm2, hm3, hm4, hm5 = st.columns(5)
        hm1.metric("H1 Optimal (OK)", f"{h1_ok_count}", delta=f"{round(h1_ok_count/max(total_pages,1)*100)}% of pages")
        hm2.metric("Missing H1", f"{missing_h1_count}", delta="No H1 tag" if missing_h1_count else "None", delta_color="inverse" if missing_h1_count else "normal")
        hm3.metric("Multiple H1s", f"{multiple_h1_count}", delta="2+ H1s on page" if multiple_h1_count else "Clean", delta_color="inverse" if multiple_h1_count else "normal")
        hm4.metric("Duplicate H1", f"{dup_h1_count}", delta=f"{len(dup_h1_set)} unique shared" if dup_h1_count else "Unique", delta_color="inverse" if dup_h1_count else "normal")
        hm5.metric("Missing H2", f"{missing_h2_count}", delta="Needs subheadings" if missing_h2_count else "Structured", delta_color="inverse" if missing_h2_count else "normal")

        # Filters and Search
        hfcol1, hfcol2 = st.columns([1.5, 2])
        with hfcol1:
            heading_filter = st.selectbox(
                "Filter Headings by Status:",
                [
                    "All Headings",
                    "Multiple H1s",
                    "Missing H1",
                    "Duplicate H1",
                    "H1 Over 70 Chars",
                    "Missing H2",
                    "Multiple H2s",
                    "Duplicate H2"
                ]
            )
        with hfcol2:
            heading_search = st.text_input("🔍 Search URL or Heading Text (H1/H2):", "", key="heading_search_input")

        df_filtered_hd = df_headings.copy()

        if heading_filter == "Missing H1":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h1_status"] == "Missing"]
        elif heading_filter == "Multiple H1s":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h1_status"] == "Multiple H1s"]
        elif heading_filter == "Duplicate H1":
            df_filtered_hd = df_filtered_hd[df_filtered_hd["h1_status"] == "Duplicate"]
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
                df_filtered_hd["h1_2"].str.contains(heading_search, case=False, na=False) |
                df_filtered_hd["h2_first"].str.contains(heading_search, case=False, na=False) |
                df_filtered_hd["h2_2"].str.contains(heading_search, case=False, na=False)
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

        # Select clean, contextual columns:
        # If user is specifically looking at cross-page Duplicate H1s, show duplicate partner URL.
        # For Multiple H1s, show H1-1 and H1-2 without confusing duplicate partner column!
        if heading_filter == "Duplicate H1":
            display_cols = [
                "url", "h1", "h1_status", "duplicate_h1_matches", "duplicate_h1_count",
                "h1_count", "h2_first", "status_code"
            ]
        elif heading_filter == "Multiple H1s":
            display_cols = [
                "url", "h1_status", "h1_count", "h1", "h1_2",
                "h2_first", "status_code"
            ]
        else:
            display_cols = [
                "url", "h1_status", "h1_count", "h1", "h1_2",
                "h2_first", "h2_2", "h2_status", "h2_count", "status_code"
            ]

        st.dataframe(
            df_filtered_hd[display_cols],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Page URL"),
                "h1": st.column_config.TextColumn("H1-1 (First H1)"),
                "h1_2": st.column_config.TextColumn("H1-2 (Second H1)", help="Second H1 tag found on this page when Multiple H1s exist"),
                "h1_status": st.column_config.TextColumn("H1 Status"),
                "h1_count": st.column_config.NumberColumn("H1 Count", format="%d", help="Total number of H1 tags on this single page"),
                "duplicate_h1_matches": st.column_config.TextColumn("Duplicate With (Other URL(s))", help="The exact other URLs on your site sharing this identical H1"),
                "duplicate_h1_count": st.column_config.NumberColumn("Total Copies", format="%d"),
                "h2_first": st.column_config.TextColumn("H2-1 (First H2)"),
                "h2_2": st.column_config.TextColumn("H2-2 (Second H2)"),
                "h2_status": st.column_config.TextColumn("H2 Status"),
                "h2_count": st.column_config.NumberColumn("H2 Count", format="%d"),
                "status_code": st.column_config.NumberColumn("HTTP Status", format="%d")
            },
            hide_index=True
        )

        # Grouped Duplicate H1 Explorer
        if dup_h1_set:
            with st.expander(f"👥 View Grouped Duplicate H1 Clusters ({len(dup_h1_set)} Unique Duplicate Groups)", expanded=(heading_filter == "Duplicate H1")):
                st.markdown("Here is the grouped breakdown of duplicate H1 headings and competing URLs:")
                for dup_h in sorted(dup_h1_set, key=lambda x: len(h1_to_urls[x]), reverse=True):
                    matched_urls = h1_to_urls[dup_h]
                    st.markdown(f"**📌 H1 Heading:** `{dup_h}` — *(Shared across **{len(matched_urls)}** pages)*")
                    dup_cluster_df = pd.DataFrame({
                        "Matching Page URL": matched_urls,
                        "Status Code": [df_headings[df_headings["url"] == u]["status_code"].values[0] if not df_headings[df_headings["url"] == u].empty else 200 for u in matched_urls]
                    })
                    st.dataframe(dup_cluster_df, use_container_width=True, hide_index=True)
                    st.markdown("<hr style='margin:0.4rem 0; border-color:#334155;'>", unsafe_allow_html=True)

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
        st.info("Run a crawl to inspect image tags, missing alt attributes, and duplicate alt text.")
    else:
        df_images = results["df_images"].copy()
        if df_images.empty:
            st.info("No images detected on crawled pages.")
        else:
            total_images = len(df_images)

            # Clean and calculate Alt statistics
            df_images["alt_clean"] = df_images["alt"].fillna("").astype(str).str.strip()
            df_images["alt_length"] = df_images["alt_clean"].str.len()
            
            # Identify Duplicate Alt Texts
            alt_counts = df_images[df_images["alt_clean"] != ""]["alt_clean"].value_counts()
            dup_alts_set = set(alt_counts[alt_counts > 1].index)

            # Assign Status Tag
            def get_image_status(row):
                a = row["alt_clean"]
                if not a or not row.get("has_alt", False):
                    return "Missing Alt Text"
                if a in dup_alts_set:
                    return "Duplicate Alt Text"
                if len(a) > 100:
                    return "Alt Text Over 100 Chars"
                return "OK"

            df_images["alt_status"] = df_images.apply(get_image_status, axis=1)

            # KPI Counters
            missing_alt_count = len(df_images[df_images["alt_status"] == "Missing Alt Text"])
            dup_alt_count = len(df_images[df_images["alt_status"] == "Duplicate Alt Text"])
            over_len_alt_count = len(df_images[df_images["alt_status"] == "Alt Text Over 100 Chars"])
            ok_alt_count = len(df_images[df_images["alt_status"] == "OK"])

            st.subheader("🖼️ Images SEO & Alt Text Audit")
            st.caption("Deep inspection of image elements across crawled pages — extract missing alt text, detect duplicate alt descriptions, and identify overly long descriptions.")

            # 5 Metric Cards
            im1, im2, im3, im4, im5 = st.columns(5)
            im1.metric("Total Images", f"{total_images}")
            im2.metric("Alt Text Optimal (OK)", f"{ok_alt_count}", delta=f"{round(ok_alt_count/max(total_images,1)*100)}% of images")
            im3.metric("Missing Alt Text", f"{missing_alt_count}", delta="Needs alt attribute" if missing_alt_count else "None", delta_color="inverse" if missing_alt_count else "normal")
            im4.metric("Duplicate Alt Text", f"{dup_alt_count}", delta="Repeated alt" if dup_alt_count else "Unique", delta_color="inverse" if dup_alt_count else "normal")
            im5.metric("Alt Over 100 Chars", f"{over_len_alt_count}", delta="Too verbose" if over_len_alt_count else "Concise", delta_color="inverse" if over_len_alt_count else "normal")

            # Filters and Search
            ifcol1, ifcol2 = st.columns([1.5, 2])
            with ifcol1:
                img_filter = st.selectbox(
                    "Filter Images by Status:",
                    [
                        "All Images",
                        "Missing Alt Text",
                        "Duplicate Alt Text",
                        "Alt Text Over 100 Chars",
                        "Alt Text Optimal (OK)"
                    ]
                )
            with ifcol2:
                img_search = st.text_input("🔍 Search Image URL, Alt Text, or Page URL:", "")

            df_filtered_img = df_images.copy()

            if img_filter == "Missing Alt Text":
                df_filtered_img = df_filtered_img[df_filtered_img["alt_status"] == "Missing Alt Text"]
            elif img_filter == "Duplicate Alt Text":
                df_filtered_img = df_filtered_img[df_filtered_img["alt_status"] == "Duplicate Alt Text"]
            elif img_filter == "Alt Text Over 100 Chars":
                df_filtered_img = df_filtered_img[df_filtered_img["alt_status"] == "Alt Text Over 100 Chars"]
            elif img_filter == "Alt Text Optimal (OK)":
                df_filtered_img = df_filtered_img[df_filtered_img["alt_status"] == "OK"]

            if img_search:
                df_filtered_img = df_filtered_img[
                    df_filtered_img["page_url"].str.contains(img_search, case=False, na=False) |
                    df_filtered_img["image_url"].str.contains(img_search, case=False, na=False) |
                    df_filtered_img["alt_clean"].str.contains(img_search, case=False, na=False)
                ]

            # Download button for filtered images
            col_idown1, col_idown2 = st.columns([1, 4])
            with col_idown1:
                csv_img = generate_csv(df_filtered_img)
                st.download_button(
                    label=f"📥 Download Filtered Images ({len(df_filtered_img)} URLs)",
                    data=csv_img,
                    file_name=f"images_{img_filter.replace(' ', '_').lower()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col_idown2:
                st.caption(f"Showing **{len(df_filtered_img)}** of **{total_images}** images matching filter: `{img_filter}`")

            st.dataframe(
                df_filtered_img[[
                    "page_url", "image_url", "alt_clean", "alt_status", "alt_length", "has_alt"
                ]],
                use_container_width=True,
                column_config={
                    "page_url": st.column_config.LinkColumn("Found On Page"),
                    "image_url": st.column_config.LinkColumn("Image URL"),
                    "alt_clean": st.column_config.TextColumn("Alt Text"),
                    "alt_status": st.column_config.TextColumn("Alt Status"),
                    "alt_length": st.column_config.NumberColumn("Alt Chars", format="%d"),
                    "has_alt": st.column_config.CheckboxColumn("Has Tag"),
                },
                hide_index=True
            )

            with st.expander("💡 SEO Guide: Image Alt Text Best Practices"):
                st.markdown("""
                - **Descriptive Alt Text**: Describe the visual content clearly for search engines and screen readers.
                - **Avoid Keyword Stuffing**: Keep alt text natural, relevant, and concise (under 100 characters).
                - **Unique Alt Text**: Different images should not share generic alt text (like "image" or "banner").
                """)

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
