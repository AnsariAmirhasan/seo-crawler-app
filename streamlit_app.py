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
    page_title="Amir's SEO Spider",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Modern Universal Theme Styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1E1B4B 0%, #312E81 50%, #4338CA 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.3);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }
    .main-title {
        font-size: 2rem;
        font-weight: 800;
        color: #FFFFFF !important;
        margin: 0;
    }
    .main-subtitle {
        color: #C7D2FE !important;
        font-size: 0.95rem;
        margin-top: 4px;
        margin-bottom: 0;
    }
    .metric-card {
        background: rgba(30, 41, 59, 0.85);
        padding: 1.2rem;
        border-radius: 10px;
        border: 1px solid #334155;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        margin-top: 0.3rem;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94A3B8 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .serp-preview-box {
        background: #FFFFFF;
        color: #202124;
        padding: 1rem 1.2rem;
        border-radius: 8px;
        font-family: Arial, sans-serif;
        border: 1px solid #DADCE0;
        margin-top: 0.5rem;
    }
    .serp-title {
        color: #1a0dab !important;
        font-size: 1.15rem;
        cursor: pointer;
        line-height: 1.3;
        margin-bottom: 2px;
        font-weight: 500;
    }
    .serp-url {
        color: #202124 !important;
        font-size: 0.85rem;
        line-height: 1.3;
        margin-bottom: 4px;
    }
    .serp-desc {
        color: #4d5156 !important;
        font-size: 0.9rem;
        line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown("""
<div class="main-header">
    <h1 class="main-title">🕷️ Amir's SEO Spider</h1>
    <p class="main-subtitle">High-speed technical SEO crawler & site audit web app — crawl up to 10,000+ URLs with zero limits!</p>
</div>
""", unsafe_allow_html=True)

# Initialize Session State
if "crawl_results" not in st.session_state:
    st.session_state["crawl_results"] = None
if "is_crawling" not in st.session_state:
    st.session_state["is_crawling"] = False
if "single_inspect_result" not in st.session_state:
    st.session_state["single_inspect_result"] = None

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ Crawl Configuration")
    
    target_url = st.text_input("🌐 Target Website URL", value="https://example.com", help="Enter full website URL")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        max_pages = st.number_input(
            "Max Pages Limit",
            min_value=1,
            max_value=10000,
            value=2000,
            step=250,
            help="Maximum URLs to crawl. You can increase up to 10,000 URLs!"
        )
    with col_c2:
        max_depth = st.number_input(
            "Max Depth",
            min_value=1,
            max_value=15,
            value=5,
            step=1,
            help="Maximum link click depth"
        )

    col_c3, col_c4 = st.columns(2)
    with col_c3:
        concurrency = st.slider("Threads / Speed", min_value=1, max_value=25, value=10, help="Number of concurrent requests")
    with col_c4:
        timeout = st.slider("Timeout (s)", min_value=3, max_value=30, value=8, help="Request timeout")

    with st.expander("🛠️ Advanced Crawl Settings", expanded=False):
        user_agent_choice = st.selectbox(
            "User-Agent",
            options=list(USER_AGENTS.keys()),
            index=0
        )
        respect_robots = st.checkbox("Respect robots.txt directives", value=False)
        include_regex = st.text_input("Include URL Regex", value="", help="Only crawl URLs matching pattern")
        exclude_regex = st.text_input("Exclude URL Regex", value="", help="Skip URLs matching pattern")

    st.markdown("---")
    btn_start = st.button("🚀 Start Unlimited SEO Crawl", type="primary", use_container_width=True)
    st.markdown("---")
    st.markdown("""
    **🔥 Advantages over Screaming Frog Free:**
    - **No 500 URL Limit**: Crawl 2,000 to 10,000+ pages!
    - **Cloud Hosted**: Runs 24/7 on `streamlit.app`
    - **Multi-Tab Excel & CSV**: 100% Free full export
    """)

# Crawl Execution Logic
if btn_start:
    if not target_url or not target_url.startswith(("http://", "https://")):
        st.error("⚠️ Please enter a valid URL starting with http:// or https://")
    else:
        st.session_state["is_crawling"] = True
        progress_bar = st.progress(0, text="Initializing High-Speed SEO Spider Engine...")
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
            exclude_regex=exclude_regex
        )

        def on_progress(crawled_count, max_pages, current_url, status_code):
            pct = min(1.0, crawled_count / max_pages)
            progress_bar.progress(pct, text=f"Crawled ({crawled_count} / {max_pages} URLs): {current_url[:65]}...")
            status_box.info(f"⚡ Crawling URL: `{current_url}` | Status: **{status_code}** | Total Crawled: **{crawled_count}**")

        start_time = time.time()
        with st.spinner("Spider is multi-threading through website structure..."):
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

        status_box.success(f"✅ Crawl Finished! Successfully analyzed **{len(analysis['df_pages'])}** pages in **{elapsed} seconds**.")
        time.sleep(1)
        st.rerun()

# Main Application Tabs
tab_overview, tab_issues, tab_pages, tab_canonicals, tab_titles, tab_headings, tab_links, tab_images, tab_architecture, tab_inspector, tab_sitemap = st.tabs([
    "📊 Overview",
    "🚨 Issues & Fixes",
    "📑 Internal Pages",
    "🎯 Canonicals",
    "🏷️ Page Titles & Meta",
    "🧱 Headings (H1/H2)",
    "🔗 Link Analysis",
    "🖼️ Images Audit",
    "🧭 Site Structure",
    "🔍 URL Quick Inspector",
    "🤖 Robots & Sitemap"
])

results = st.session_state.get("crawl_results")

# TAB 1: OVERVIEW & HEALTH AUDIT
with tab_overview:
    if not results:
        st.info("👈 Enter a URL in the sidebar and click **'Start Unlimited SEO Crawl'** to run a complete technical audit.")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color:#6366F1; margin-top:0;">⚡ 2000+ URL Capacity</h3>
                <p style="color:#94A3B8; font-size:0.9rem; margin-bottom:0;">No 500-page limits. Multi-threaded engine crawls large e-commerce and blogs easily.</p>
            </div>
            """, unsafe_allow_html=True)
        with col_f2:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color:#10B981; margin-top:0;">🔍 50+ SEO Checks</h3>
                <p style="color:#94A3B8; font-size:0.9rem; margin-bottom:0;">Inspect Status Codes, Titles, H1/H2, Canonical tags, Schema, Open Graph, and Broken links.</p>
            </div>
            """, unsafe_allow_html=True)
        with col_f3:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color:#F59E0B; margin-top:0;">📦 Free & Exportable</h3>
                <p style="color:#94A3B8; font-size:0.9rem; margin-bottom:0;">Download full multi-tab Excel workbooks and CSV reports with no restrictions.</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        summary = results["summary"]
        df_pages = results["df_pages"]
        df_issues = results["df_issues"]
        
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        with col_m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Pages Crawled</div>
                <div class="metric-value" style="color:#6366F1;">{summary['total_crawled']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Critical Errors</div>
                <div class="metric-value" style="color:#EF4444;">{summary['critical_errors']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Warnings</div>
                <div class="metric-value" style="color:#F59E0B;">{summary['warnings']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Notices</div>
                <div class="metric-value" style="color:#3B82F6;">{summary['notices']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m5:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Links Found</div>
                <div class="metric-value" style="color:#10B981;">{summary['total_links']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col_g1, col_g2, col_g3 = st.columns([1, 1, 1.2])
        with col_g1:
            st.plotly_chart(create_health_gauge(summary["health_score"]), use_container_width=True)
        with col_g2:
            st.plotly_chart(create_status_code_chart(df_pages), use_container_width=True)
        with col_g3:
            st.plotly_chart(create_issues_bar_chart(df_issues), use_container_width=True)

        st.markdown("---")
        st.subheader("📥 Export Audit Data")
        col_d1, col_d2, col_d3 = st.columns([1, 1, 2])
        with col_d1:
            excel_bytes = generate_excel_report(results, results.get("start_url", ""))
            st.download_button(
                label="📊 Download Excel Report (.xlsx)",
                data=excel_bytes,
                file_name=f"seo_audit_{urlparse(results.get('start_url','')).netloc}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with col_d2:
            csv_pages = generate_csv(df_pages)
            st.download_button(
                label="📑 Download All Pages (CSV)",
                data=csv_pages,
                file_name="crawled_pages.csv",
                mime="text/csv",
                use_container_width=True
            )

# TAB 2: ISSUES & RECOMMENDATIONS
with tab_issues:
    if not results:
        st.info("Run a crawl to see prioritized issues and actionable fixes.")
    else:
        df_issues = results["df_issues"]
        if df_issues.empty:
            st.success("🎉 Outstanding! No technical SEO issues were detected.")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                selected_severity = st.multiselect("Filter by Severity", options=["Error", "Warning", "Notice"], default=["Error", "Warning", "Notice"])
            with col_f2:
                all_categories = sorted(df_issues["category"].unique())
                selected_cat = st.multiselect("Filter by Category", options=all_categories, default=all_categories)

            filtered_issues = df_issues[
                (df_issues["type"].isin(selected_severity)) &
                (df_issues["category"].isin(selected_cat))
            ]

            st.write(f"Showing **{len(filtered_issues)}** issues:")
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

# TAB 3: ALL INTERNAL PAGES EXPLORER
with tab_pages:
    if not results:
        st.info("Run a crawl to explore internal pages table.")
    else:
        df_pages = results["df_pages"]
        search_query = st.text_input("🔍 Search pages by URL or Title", "")
        
        display_df = df_pages.copy()
        if search_query:
            display_df = display_df[
                display_df["url"].str.contains(search_query, case=False, na=False) |
                display_df["title"].str.contains(search_query, case=False, na=False)
            ]

        columns_to_show = [
            "url", "canonical_url", "canonical_status", "status_code", "title", "meta_description", "h1",
            "word_count", "latency_ms", "size_kb",
            "is_indexable", "internal_outlinks_count", "images_count"
        ]
        available_cols = [c for c in columns_to_show if c in display_df.columns]

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
                "latency_ms": st.column_config.NumberColumn("Latency (ms)", format="%.0f ms"),
                "size_kb": st.column_config.NumberColumn("Size (KB)", format="%.1f KB"),
                "is_indexable": st.column_config.CheckboxColumn("Indexable"),
            },
            hide_index=True
        )

# TAB 4: CANONICAL TAGS AUDIT ("Ye Page -> Iska Canonical Ye")
with tab_canonicals:
    if not results:
        st.info("Run a crawl to audit Canonical URLs, mismatches, and self-referential tags.")
    else:
        df_pages = results["df_pages"]
        
        st.subheader("🎯 Canonical URLs Audit (Page URL ➔ Canonical Target)")
        st.caption("Complete breakdown of Page URLs and their associated Canonical tags — detect duplicate content and indexing signals.")

        # Metric breakdown
        total_pages = len(df_pages)
        self_ref_count = len(df_pages[df_pages["canonical_status"] == "Self-Referential"])
        canonicalised_count = len(df_pages[df_pages["canonical_status"] == "Canonicalised"])
        missing_count = len(df_pages[df_pages["canonical_status"] == "Missing"])
        multiple_count = len(df_pages[df_pages["canonical_status"] == "Multiple"])

        cm1, cm2, cm3, cm4 = st.columns(4)
        cm1.metric("Self-Referential (OK)", f"{self_ref_count}", delta=f"{round(self_ref_count/max(total_pages,1)*100)}% of pages")
        cm2.metric("Canonicalised (Points Elsewhere)", f"{canonicalised_count}", delta="Consolidating equity" if canonicalised_count else None)
        cm3.metric("Missing Canonical", f"{missing_count}", delta="Needs tag" if missing_count else None, delta_color="inverse")
        cm4.metric("Multiple Canonicals", f"{multiple_count}", delta="Critical Error" if multiple_count else None, delta_color="inverse")

        # Filters
        fcol1, fcol2 = st.columns([1, 2])
        with fcol1:
            canon_filter = st.selectbox(
                "Filter by Canonical Status:",
                ["All Pages", "Self-Referential", "Canonicalised", "Missing", "Multiple"]
            )
        with fcol2:
            canon_search = st.text_input("🔍 Search Page URL or Canonical URL:", "")

        df_canon = df_pages[["url", "canonical_url", "canonical_status", "status_code", "is_indexable"]].copy()

        if canon_filter != "All Pages":
            df_canon = df_canon[df_canon["canonical_status"] == canon_filter]

        if canon_search:
            df_canon = df_canon[
                df_canon["url"].str.contains(canon_search, case=False, na=False) |
                df_canon["canonical_url"].str.contains(canon_search, case=False, na=False)
            ]

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

        with st.expander("💡 SEO Guide: How Canonical URLs Work"):
            st.markdown("""
            - **Self-Referential (`Page URL == Canonical URL`)**: ✅ Recommended best practice. Protects against duplicate content caused by query parameters, session IDs, trailing slashes, and HTTP/HTTPS protocol variations.
            - **Canonicalised (`Page URL != Canonical URL`)**: 🔀 Directs search engines to index a master version instead of this duplicate/parameterized URL.
            - **Missing Canonical**: ⚠️ No canonical link tag found in `<head>`. Search engines will choose a version on their own.
            - **Multiple Canonicals**: ❌ More than one canonical link tag detected. Google will typically ignore all of them.
            """)

# TAB 5: PAGE TITLES & META DESCRIPTIONS
with tab_titles:
    if not results:
        st.info("Run a crawl to inspect titles, SERP lengths and snippets.")
    else:
        df_pages = results["df_pages"]
        title_df = df_pages[["url", "title", "title_length", "title_pixel_width", "meta_description", "meta_description_length"]].copy()
        
        st.subheader("🏷️ Page Titles & Meta Descriptions Audit")
        st.dataframe(
            title_df,
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("URL"),
                "title": st.column_config.TextColumn("Page Title"),
                "title_length": st.column_config.NumberColumn("Chars"),
                "title_pixel_width": st.column_config.NumberColumn("Pixel Width (px)"),
                "meta_description": st.column_config.TextColumn("Meta Description"),
                "meta_description_length": st.column_config.NumberColumn("Desc Chars"),
            },
            hide_index=True
        )

        st.markdown("---")
        st.subheader("🔍 Google SERP Preview Simulator")
        selected_url = st.selectbox("Select Page URL to preview Google Search snippet:", options=df_pages["url"].tolist())
        
        if selected_url:
            row = df_pages[df_pages["url"] == selected_url].iloc[0]
            p_title = row.get("title") or "Untitled Document"
            p_url = row.get("url")
            p_desc = row.get("meta_description") or "No meta description provided for this page."

            st.markdown(f"""
            <div class="serp-preview-box">
                <div class="serp-url">{p_url}</div>
                <div class="serp-title">{p_title}</div>
                <div class="serp-desc">{p_desc}</div>
            </div>
            """, unsafe_allow_html=True)

# TAB 5: HEADINGS AUDIT
with tab_headings:
    if not results:
        st.info("Run a crawl to inspect H1 and H2 tags.")
    else:
        df_pages = results["df_pages"]
        heading_cols = ["url", "h1", "h1_count", "h2_first", "h2_count"]
        st.subheader("🧱 Heading Hierarchy & Structure")
        st.dataframe(
            df_pages[[c for c in heading_cols if c in df_pages.columns]],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("URL"),
                "h1": st.column_config.TextColumn("H1 Heading Text"),
                "h1_count": st.column_config.NumberColumn("H1 Count"),
                "h2_first": st.column_config.TextColumn("First H2 Text"),
                "h2_count": st.column_config.NumberColumn("H2 Count"),
            },
            hide_index=True
        )

# TAB 6: LINK ANALYSIS
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

            st.write(f"Total Discovered Links: **{len(filtered_links)}**")
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

# TAB 7: IMAGES AUDIT
with tab_images:
    if not results:
        st.info("Run a crawl to inspect image tags and missing alt attributes.")
    else:
        df_images = results["df_images"]
        if df_images.empty:
            st.info("No images detected on crawled pages.")
        else:
            missing_alt_count = len(df_images[df_images["has_alt"] == False])
            st.metric("Total Images Discovered", len(df_images), delta=f"{missing_alt_count} Missing Alt", delta_color="inverse")
            
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

# TAB 8: SITE ARCHITECTURE GRAPH
with tab_architecture:
    if not results:
        st.info("Run a crawl to visualize internal linking topology.")
    else:
        st.subheader("🧭 Internal Link Structure Visualization")
        st.write("Interactive network diagram mapping internal page relationships:")
        df_links = results["df_links"]
        st.plotly_chart(create_site_architecture_graph(df_links), use_container_width=True)

# TAB 9: SINGLE URL QUICK INSPECTOR
with tab_inspector:
    st.subheader("🔍 Single URL Instant Inspector")
    st.caption("Inspect any individual URL instantly without running a full crawl.")
    
    inspect_url = st.text_input("Enter URL to Inspect:", value="https://librecrawl.com")
    btn_inspect = st.button("🔎 Inspect Page", type="secondary")

    if btn_inspect and inspect_url:
        with st.spinner("Fetching and analyzing page SEO metrics..."):
            spider_temp = SEOSpider(start_url=inspect_url, max_pages=1, max_depth=0)
            fetch_res = spider_temp.fetch_single_url(inspect_url)
            audit = parse_page_seo(fetch_res)
            st.session_state["single_inspect_result"] = audit

    inspect_data = st.session_state.get("single_inspect_result")
    if inspect_data:
        col_i1, col_i2, col_i3, col_i4 = st.columns(4)
        with col_i1:
            st.metric("HTTP Status", inspect_data.get("status_code", 0))
        with col_i2:
            st.metric("Latency", f"{inspect_data.get('latency_ms', 0)} ms")
        with col_i3:
            st.metric("Word Count", inspect_data.get("word_count", 0))
        with col_i4:
            st.metric("Indexable", "Yes" if inspect_data.get("is_indexable") else "No")

        st.markdown("### 📋 Meta & Content Details")
        st.json({
            "Title": inspect_data.get("title"),
            "Title Length": inspect_data.get("title_length"),
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
            st.markdown("### 🚨 Page Issues Detected")
            st.dataframe(pd.DataFrame(inspect_data["issues"]), use_container_width=True)

# TAB 10: ROBOTS & SITEMAP TOOL
with tab_sitemap:
    st.subheader("🤖 Robots.txt & XML Sitemap Validator")
    site_base = st.text_input("Enter Root Website URL:", value="https://librecrawl.com")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("📄 Fetch robots.txt"):
            try:
                parsed = urlparse(site_base)
                robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
                r = requests.get(robots_url, timeout=10)
                st.write(f"Status Code: **{r.status_code}** ({robots_url})")
                st.code(r.text, language="text")
            except Exception as e:
                st.error(f"Failed to fetch robots.txt: {e}")

    with col_r2:
        if st.button("🗺️ Fetch & Parse sitemap.xml"):
            try:
                parsed = urlparse(site_base)
                sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
                r = requests.get(sitemap_url, timeout=10)
                st.write(f"Status Code: **{r.status_code}** ({sitemap_url})")
                if r.status_code == 200:
                    root = ET.fromstring(r.content)
                    urls = [loc.text for loc in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
                    st.success(f"Discovered **{len(urls)}** URLs in sitemap:")
                    st.dataframe(pd.DataFrame(urls, columns=["Sitemap URL"]), use_container_width=True)
                else:
                    st.warning("sitemap.xml not found or returned non-200 code.")
            except Exception as e:
                st.error(f"Failed to parse sitemap: {e}")
