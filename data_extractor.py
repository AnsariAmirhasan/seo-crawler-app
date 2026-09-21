"""
data_extractor.py - SEO Data Extractor & Multi-Tab Audit Workbook Generator
Extracts all crawl errors, creates an 'Index' summary sheet matching the client standard,
and generates individual tabs for each error category with detailed affected URLs.
"""

import io
import re
from urllib.parse import urlparse
from collections import Counter
import pandas as pd
from seo_analyzer import is_pagination_url, get_base_unpaginated_url
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Excel tab name max length is 31 characters according to Excel specification
MAX_TAB_LEN = 31

def sanitize_sheet_title(title: str) -> str:
    """Sanitize sheet title for Excel: max 31 chars, no invalid characters [:\\/?*[]]."""
    clean = re.sub(r'[:\\/?*\[\]]', '', title).strip()
    if len(clean) > MAX_TAB_LEN:
        clean = clean[:MAX_TAB_LEN].strip()
    return clean or "Sheet"

def get_series(df: pd.DataFrame, col: str, default=""):
    """Safely get a Series from df, returning a default Series if col is absent."""
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)

def extract_all_seo_errors(analysis_result: dict) -> tuple[list[dict], dict[str, pd.DataFrame]]:
    """
    Extracts all errors and diagnostics from crawl results.
    Returns:
      - index_rows: List of dicts with keys: ['error_name', 'status', 'comments', 'sheet_name', 'count', 'is_error']
      - error_dfs: Dict mapping sheet_name -> DataFrame of affected URLs and diagnostics.
    """
    df_pages = analysis_result.get("df_pages", pd.DataFrame()).copy()
    df_links = analysis_result.get("df_links", pd.DataFrame()).copy()
    df_images = analysis_result.get("df_images", pd.DataFrame()).copy()
    
    index_rows = []
    error_dfs = {}

    if df_pages.empty:
        return index_rows, error_dfs

    # Helpers
    status_series = get_series(df_pages, "status_code", 0)
    indexable_series = get_series(df_pages, "is_indexable", True)
    is_indexable_200 = (status_series == 200) & (indexable_series == True)
    
    # Exclude noindex pages
    is_noindex_bool = get_series(df_pages, "is_noindex", False) == True
    meta_robots_noindex = get_series(df_pages, "meta_robots", "").fillna("").str.contains("noindex", case=False)
    is_noindex_mask = is_noindex_bool | meta_robots_noindex
    eval_pages = df_pages[is_indexable_200 & (~is_noindex_mask)]

    # -------------------------------------------------------------
    # 1. General Errors / Server Errors (5xx & Crawl Failures)
    # -------------------------------------------------------------
    err_mask = (get_series(df_pages, "status_code", 0) >= 500) | (get_series(df_pages, "error", "").fillna("").str.len() > 0)
    general_err_df = df_pages[err_mask]
    gen_count = len(general_err_df)
    gen_tab = sanitize_sheet_title("General Errors")
    if gen_count > 0:
        cols = [c for c in ["url", "status_code", "status_description", "error", "source_url"] if c in general_err_df.columns]
        edf = general_err_df[cols].copy().rename(columns={
            "url": "Page URL",
            "status_code": "Status Code",
            "status_description": "Status Description",
            "error": "Error Details",
            "source_url": "Found On (Source URL)"
        })
        edf["Recommended Action"] = "Investigate server error logs, server configuration, or network timeouts."
        error_dfs[gen_tab] = edf
        index_rows.append({
            "error_name": "General Errors",
            "status": f"Attention Needed ({gen_count})",
            "comments": f"Found {gen_count} pages with server errors (5xx) or unhandled network failure.",
            "sheet_name": gen_tab,
            "count": gen_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "General Errors",
            "status": "Passed (0)",
            "comments": "No 5xx server errors or fatal crawl exceptions detected.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 2. Internal links are broken (4xx / 5xx internal links)
    # -------------------------------------------------------------
    broken_internal_links = pd.DataFrame()
    if not df_links.empty and "url" in df_pages.columns:
        bad_urls = set(df_pages[get_series(df_pages, "status_code", 0) >= 400]["url"].dropna().unique())
        if bad_urls and "target_url" in df_links.columns:
            broken_internal_links = df_links[
                (get_series(df_links, "is_internal", False) == True) & 
                (df_links["target_url"].isin(bad_urls))
            ].copy()
    
    # Fallback to df_pages with 4xx and inlinks
    if broken_internal_links.empty:
        broken_pages = df_pages[get_series(df_pages, "status_code", 0) >= 400]
        if not broken_pages.empty:
            broken_count = len(broken_pages)
            b_tab = sanitize_sheet_title("Internal links are broken")
            cols = [c for c in ["url", "status_code", "status_description", "source_url", "anchor_text", "inlinks_count"] if c in broken_pages.columns]
            bdf = broken_pages[cols].copy().rename(columns={
                "url": "Broken Target URL",
                "status_code": "Status Code",
                "status_description": "HTTP Status",
                "source_url": "Source Page (Found On)",
                "anchor_text": "Anchor Text",
                "inlinks_count": "Inlinks Count"
            })
            bdf["Recommended Action"] = "Update internal hyperlink destination or implement a 301 redirect to a live page."
            error_dfs[b_tab] = bdf
            index_rows.append({
                "error_name": "Internal links are broken",
                "status": f"Failed ({broken_count})",
                "comments": f"Found {broken_count} internal URLs returning 4xx/5xx status codes.",
                "sheet_name": b_tab,
                "count": broken_count,
                "is_error": True
            })
        else:
            index_rows.append({
                "error_name": "Internal links are broken",
                "status": "Passed (0)",
                "comments": "All crawled internal links returned valid 200 OK responses.",
                "sheet_name": None,
                "count": 0,
                "is_error": False
            })
    else:
        broken_count = len(broken_internal_links)
        b_tab = sanitize_sheet_title("Internal links are broken")
        cols = [c for c in ["source_url", "target_url", "anchor_text"] if c in broken_internal_links.columns]
        bdf = broken_internal_links[cols].copy().rename(columns={
            "source_url": "Source Page (Found On)",
            "target_url": "Broken Target URL",
            "anchor_text": "Anchor Text"
        })
        bdf["Recommended Action"] = "Update or remove broken hyperlink on source page."
        error_dfs[b_tab] = bdf
        index_rows.append({
            "error_name": "Internal links are broken",
            "status": f"Failed ({broken_count})",
            "comments": f"Found {broken_count} broken internal hyperlinks pointing to dead URLs.",
            "sheet_name": b_tab,
            "count": broken_count,
            "is_error": True
        })

    # -------------------------------------------------------------
    # 3. Duplicate Meta Descriptions
    # -------------------------------------------------------------
    meta_s = get_series(eval_pages, "meta_description", "").fillna("").str.strip()
    dup_desc_df = pd.DataFrame()
    dup_descs = set()
    desc_counts = {}
    if not eval_pages.empty and "meta_description" in eval_pages.columns:
        valid_ep = eval_pages[meta_s != ""].copy()
        canon_col = get_series(valid_ep, "canonical_url", "")
        valid_ep["is_pagination"] = [is_pagination_url(u, c) for u, c in zip(valid_ep["url"], canon_col)]
        valid_ep["base_url"] = [get_base_unpaginated_url(u, c) for u, c in zip(valid_ep["url"], canon_col)]

        desc_to_bases = valid_ep.groupby("meta_description")["base_url"].apply(lambda s: set(s)).to_dict()
        dup_descs = {d for d, bases in desc_to_bases.items() if len(bases) > 1}
        # Only non-pagination pages count as duplicate errors
        dup_desc_df = valid_ep[valid_ep["meta_description"].isin(dup_descs) & (~valid_ep["is_pagination"])]
        desc_counts = {d: len(bases) for d, bases in desc_to_bases.items() if len(bases) > 1}
    
    dup_desc_count = len(dup_desc_df)
    dmd_tab = sanitize_sheet_title("Duplicate Meta Descriptions")
    if dup_desc_count > 0:
        cols = [c for c in ["url", "meta_description", "status_code"] if c in dup_desc_df.columns]
        ddf = dup_desc_df[cols].copy().rename(columns={
            "url": "Page URL",
            "meta_description": "Duplicate Meta Description",
            "status_code": "Status Code"
        })
        ddf["Duplicate Count"] = ddf["Duplicate Meta Description"].map(desc_counts)
        ddf["Recommended Action"] = "Write tailored, unique meta descriptions for each distinct page."
        error_dfs[dmd_tab] = ddf
        index_rows.append({
            "error_name": "Duplicate Meta Descriptions",
            "status": f"Failed ({dup_desc_count})",
            "comments": f"Found {dup_desc_count} pages sharing duplicate meta descriptions across {len(dup_descs)} groups.",
            "sheet_name": dmd_tab,
            "count": dup_desc_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Duplicate Meta Descriptions",
            "status": "Passed (0)",
            "comments": "All indexable pages have unique meta descriptions.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 4. 4XX status code
    # -------------------------------------------------------------
    sc_series = get_series(df_pages, "status_code", 0)
    c4xx_df = df_pages[(sc_series >= 400) & (sc_series < 500)]
    c4xx_count = len(c4xx_df)
    tab_4xx = sanitize_sheet_title("4XX status code")
    if c4xx_count > 0:
        cols = [c for c in ["url", "status_code", "status_description", "source_url", "anchor_text"] if c in c4xx_df.columns]
        edf = c4xx_df[cols].copy().rename(columns={
            "url": "Page URL",
            "status_code": "Status Code",
            "status_description": "Status Description",
            "source_url": "Discovered On",
            "anchor_text": "Anchor Text"
        })
        edf["Recommended Action"] = "Fix 404/403 URL, reinstate deleted content, or 301 redirect to relevant active page."
        error_dfs[tab_4xx] = edf
        index_rows.append({
            "error_name": "4XX status code",
            "status": f"Failed ({c4xx_count})",
            "comments": f"Found {c4xx_count} client-error URLs (404 Not Found, 403 Forbidden, etc.).",
            "sheet_name": tab_4xx,
            "count": c4xx_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "4XX status code",
            "status": "Passed (0)",
            "comments": "No 4XX client error status codes detected.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 5. Duplicate title tags
    # -------------------------------------------------------------
    title_s = get_series(eval_pages, "title", "").fillna("").str.strip()
    dup_title_df = pd.DataFrame()
    dup_titles = set()
    title_counts = {}
    if not eval_pages.empty and "title" in eval_pages.columns:
        valid_ep_t = eval_pages[title_s != ""].copy()
        canon_col_t = get_series(valid_ep_t, "canonical_url", "")
        valid_ep_t["is_pagination"] = [is_pagination_url(u, c) for u, c in zip(valid_ep_t["url"], canon_col_t)]
        valid_ep_t["base_url"] = [get_base_unpaginated_url(u, c) for u, c in zip(valid_ep_t["url"], canon_col_t)]

        title_to_bases = valid_ep_t.groupby("title")["base_url"].apply(lambda s: set(s)).to_dict()
        dup_titles = {t for t, bases in title_to_bases.items() if len(bases) > 1}
        # Only non-pagination pages count as duplicate errors
        dup_title_df = valid_ep_t[valid_ep_t["title"].isin(dup_titles) & (~valid_ep_t["is_pagination"])]
        title_counts = {t: len(bases) for t, bases in title_to_bases.items() if len(bases) > 1}
    
    dup_title_count = len(dup_title_df)
    dtt_tab = sanitize_sheet_title("Duplicate title tags")
    if dup_title_count > 0:
        cols = [c for c in ["url", "title", "status_code"] if c in dup_title_df.columns]
        tdf = dup_title_df[cols].copy().rename(columns={
            "url": "Page URL",
            "title": "Duplicate Title Tag",
            "status_code": "Status Code"
        })
        tdf["Duplicate Count"] = tdf["Duplicate Title Tag"].map(title_counts)
        tdf["Recommended Action"] = "Create distinct, keyword-focused title tags for each page."
        error_dfs[dtt_tab] = tdf
        index_rows.append({
            "error_name": "Duplicate title tags",
            "status": f"Failed ({dup_title_count})",
            "comments": f"Found {dup_title_count} pages sharing identical title tags across {len(dup_titles)} groups.",
            "sheet_name": dtt_tab,
            "count": dup_title_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Duplicate title tags",
            "status": "Passed (0)",
            "comments": "No duplicate title tags detected across indexable pages.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 6. Unminified JavaScript and CSS files
    # -------------------------------------------------------------
    unminified_list = []
    if not df_links.empty:
        for _, lr in df_links.iterrows():
            tgt = str(lr.get("target_url", ""))
            src = str(lr.get("source_url", ""))
            clean_tgt = tgt.split("?")[0].lower()
            if (clean_tgt.endswith(".js") or clean_tgt.endswith(".css")) and ".min." not in clean_tgt:
                unminified_list.append({
                    "Page URL (Source)": src,
                    "Unminified Asset URL": tgt,
                    "Asset Type": "JavaScript (.js)" if clean_tgt.endswith(".js") else "Stylesheet (.css)",
                    "Recommended Action": "Minify and bundle JS/CSS files to reduce file transfer size and improve PageSpeed."
                })
    
    unmin_tab = sanitize_sheet_title("Unminified JS & CSS")
    if unminified_list:
        unmin_df = pd.DataFrame(unminified_list).drop_duplicates(subset=["Unminified Asset URL"]).head(500)
        unmin_count = len(unmin_df)
        error_dfs[unmin_tab] = unmin_df
        index_rows.append({
            "error_name": "Unminified JavaScript and CSS files",
            "status": f"Attention Needed ({unmin_count})",
            "comments": f"Found {unmin_count} unminified script and stylesheet resources.",
            "sheet_name": unmin_tab,
            "count": unmin_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Unminified JavaScript and CSS files",
            "status": "Passed (0)",
            "comments": "No unminified static scripts or stylesheet links detected.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 7. Underscores in the URL
    # -------------------------------------------------------------
    def has_underscore(u: str) -> bool:
        path = urlparse(str(u)).path
        return "_" in path

    underscore_df = pd.DataFrame()
    if "url" in df_pages.columns and not df_pages.empty:
        underscore_df = df_pages[df_pages["url"].apply(has_underscore)]
    under_count = len(underscore_df)
    under_tab = sanitize_sheet_title("Underscores in the URL")
    if under_count > 0:
        cols = [c for c in ["url", "status_code"] if c in underscore_df.columns]
        udf = underscore_df[cols].copy().rename(columns={"url": "Page URL", "status_code": "Status Code"})
        udf["Recommended Clean Slug"] = udf["Page URL"].apply(
            lambda u: urlparse(u)._replace(path=urlparse(u).path.replace("_", "-")).geturl()
        )
        udf["Recommended Action"] = "Replace underscores with hyphens in URL slugs per Google SEO guidelines and 301 redirect old URLs."
        error_dfs[under_tab] = udf
        index_rows.append({
            "error_name": "Underscores in the URL",
            "status": f"Attention Needed ({under_count})",
            "comments": f"Found {under_count} URLs with underscores '_' in the slug path.",
            "sheet_name": under_tab,
            "count": under_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Underscores in the URL",
            "status": "Passed (0)",
            "comments": "All URLs use hyphens or clean slugs without underscores.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 8. Don't have meta descriptions
    # -------------------------------------------------------------
    no_desc_mask = get_series(eval_pages, "meta_description", "").fillna("").str.strip() == ""
    no_desc_df = eval_pages[no_desc_mask]
    no_desc_count = len(no_desc_df)
    dhm_tab = sanitize_sheet_title("Don't have meta descriptions")
    if no_desc_count > 0:
        cols = [c for c in ["url", "title", "status_code"] if c in no_desc_df.columns]
        mdf = no_desc_df[cols].copy().rename(columns={
            "url": "Page URL",
            "title": "Page Title",
            "status_code": "Status Code"
        })
        mdf["Recommended Action"] = "Add an engaging, keyword-rich meta description between 120-155 characters."
        error_dfs[dhm_tab] = mdf
        index_rows.append({
            "error_name": "Don't have meta descriptions",
            "status": f"Failed ({no_desc_count})",
            "comments": f"Found {no_desc_count} indexable pages completely missing meta descriptions.",
            "sheet_name": dhm_tab,
            "count": no_desc_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Don't have meta descriptions",
            "status": "Passed (0)",
            "comments": "All indexable crawled pages have meta descriptions.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 9. Missing H1
    # -------------------------------------------------------------
    h1_text = get_series(eval_pages, "h1", "").fillna("").str.strip()
    h1_count_ser = get_series(eval_pages, "h1_count", 0).fillna(0)
    missing_h1_mask = (h1_text == "") | (h1_count_ser == 0)
    missing_h1_df = eval_pages[missing_h1_mask]
    missing_h1_count = len(missing_h1_df)
    mh1_tab = sanitize_sheet_title("Missing H1")
    if missing_h1_count > 0:
        cols = [c for c in ["url", "title", "status_code"] if c in missing_h1_df.columns]
        h1df = missing_h1_df[cols].copy().rename(columns={
            "url": "Page URL",
            "title": "Page Title",
            "status_code": "Status Code"
        })
        h1df["Recommended Action"] = "Add exactly one primary H1 heading describing the core topic of the page."
        error_dfs[mh1_tab] = h1df
        index_rows.append({
            "error_name": "Missing H1",
            "status": f"Failed ({missing_h1_count})",
            "comments": f"Found {missing_h1_count} indexable pages without a primary H1 tag.",
            "sheet_name": mh1_tab,
            "count": missing_h1_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Missing H1",
            "status": "Passed (0)",
            "comments": "All indexable pages contain at least one valid H1 heading tag.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 10. Orphaned pages in sitemaps / site
    # -------------------------------------------------------------
    orphan_mask = get_series(eval_pages, "is_orphan", False) == True
    orphan_df = eval_pages[orphan_mask]
    orphan_count = len(orphan_df)
    orphan_tab = sanitize_sheet_title("Orphaned pages in sitemaps")
    if orphan_count > 0:
        cols = [c for c in ["url", "title", "status_code", "inlinks_count"] if c in orphan_df.columns]
        odf = orphan_df[cols].copy().rename(columns={
            "url": "Page URL",
            "title": "Page Title",
            "status_code": "Status Code",
            "inlinks_count": "Inlinks (0)"
        })
        odf["Recommended Action"] = "Add internal hyperlinks pointing to this URL from top navigation, category pages, or relevant blogs."
        error_dfs[orphan_tab] = odf
        index_rows.append({
            "error_name": "Orphaned pages in sitemaps",
            "status": f"Attention Needed ({orphan_count})",
            "comments": f"Found {orphan_count} indexable orphan pages with 0 internal inlinks.",
            "sheet_name": orphan_tab,
            "count": orphan_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Orphaned pages in sitemaps",
            "status": "Passed (0)",
            "comments": "No orphan pages found; all pages receive internal incoming links.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 11. Page Speed & Heavy Resources
    # -------------------------------------------------------------
    slow_pages = df_pages[get_series(df_pages, "response_time_ms", 0) > 1500]
    heavy_images = df_images[get_series(df_images, "is_over_100kb", False) == True] if not df_images.empty else pd.DataFrame()
    psi_count = len(slow_pages) + len(heavy_images)
    psi_tab = sanitize_sheet_title("Page Speed Insight")
    if psi_count > 0:
        psi_rows = []
        for _, r in slow_pages.iterrows():
            psi_rows.append({
                "Resource / Page URL": r.get("url", ""),
                "Type": "Slow Server Response",
                "Metric": f"{r.get('response_time_ms', 0)} ms",
                "Recommended Action": "Optimize database queries, enable server-side caching or CDN."
            })
        for _, r in heavy_images.iterrows():
            psi_rows.append({
                "Resource / Page URL": r.get("image_url", ""),
                "Type": "Large Image (>100KB)",
                "Metric": f"{r.get('size_kb', 0)} KB",
                "Recommended Action": "Compress or convert image to modern WebP format under 100 KB."
            })
        psidf = pd.DataFrame(psi_rows).head(500)
        error_dfs[psi_tab] = psidf
        index_rows.append({
            "error_name": "Page Speed Insight",
            "status": f"Attention Needed ({psi_count})",
            "comments": f"Found {len(slow_pages)} slow pages (>1.5s) and {len(heavy_images)} heavy images (>100KB).",
            "sheet_name": psi_tab,
            "count": psi_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Page Speed Insight",
            "status": "Passed (0)",
            "comments": "No severe page latency or heavy unoptimized resources detected.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 12. Missing Image Alt Text
    # -------------------------------------------------------------
    missing_alt = pd.DataFrame()
    if not df_images.empty:
        missing_alt = df_images[get_series(df_images, "has_alt", True) == False]
    alt_count = len(missing_alt)
    alt_tab = sanitize_sheet_title("Images Missing Alt Text")
    if alt_count > 0:
        cols = [c for c in ["page_url", "image_url", "loading"] if c in missing_alt.columns]
        altdf = missing_alt[cols].copy().rename(columns={
            "page_url": "Page URL",
            "image_url": "Image URL",
            "loading": "Loading Attribute"
        }).head(1000)
        altdf["Recommended Action"] = "Add descriptive alt attributes to assist accessibility and Google Image ranking."
        error_dfs[alt_tab] = altdf
        index_rows.append({
            "error_name": "Images Missing Alt Text",
            "status": f"Failed ({alt_count})",
            "comments": f"Found {alt_count} images lacking descriptive alt attributes.",
            "sheet_name": alt_tab,
            "count": alt_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Images Missing Alt Text",
            "status": "Passed (0)",
            "comments": "All detected images include descriptive alt attributes.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    # -------------------------------------------------------------
    # 13. Redirect Chains & Loops (3XX)
    # -------------------------------------------------------------
    chain_mask = (get_series(df_pages, "is_redirect_chain", False) == True) | (get_series(df_pages, "is_redirect_loop", False) == True)
    chain_df = df_pages[chain_mask]
    chain_count = len(chain_df)
    chain_tab = sanitize_sheet_title("Redirect Chains & Loops")
    if chain_count > 0:
        cols = [c for c in ["url", "status_code", "redirect_chain_str", "redirect_hops", "final_url"] if c in chain_df.columns]
        cdf = chain_df[cols].copy().rename(columns={
            "url": "Start URL",
            "status_code": "Initial Status",
            "redirect_chain_str": "Redirect Chain",
            "redirect_hops": "Hops Count",
            "final_url": "Final Destination URL"
        })
        cdf["Recommended Action"] = "Update inlinks to point directly to the final 200 OK target URL."
        error_dfs[chain_tab] = cdf
        index_rows.append({
            "error_name": "Redirect Chains & Loops",
            "status": f"Failed ({chain_count})",
            "comments": f"Found {chain_count} URLs involved in multiple redirect hops or loops.",
            "sheet_name": chain_tab,
            "count": chain_count,
            "is_error": True
        })
    else:
        index_rows.append({
            "error_name": "Redirect Chains & Loops",
            "status": "Passed (0)",
            "comments": "No multi-hop redirect chains or infinite loops detected.",
            "sheet_name": None,
            "count": 0,
            "is_error": False
        })

    return index_rows, error_dfs

def build_error_audit_excel_workbook(index_rows: list[dict], error_dfs: dict[str, pd.DataFrame]) -> bytes:
    """
    Builds a beautifully formatted Excel workbook matching the screenshot specification:
    - Sheet 1: 'Index' with merged green header, columns [Errors, Status, Comments]
    - Following Sheets: Dedicated tab for each detected error containing affected URLs.
    """
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Styles
    font_main_header = Font(name="Calibri", size=13, bold=True, color="000000")
    font_col_header = Font(name="Calibri", size=11, bold=True, color="000000")
    font_data = Font(name="Calibri", size=10, color="1F2937")
    font_link = Font(name="Calibri", size=10, color="0B57D0", underline="single")
    font_status_fail = Font(name="Calibri", size=10, bold=True, color="991B1B")
    font_status_pass = Font(name="Calibri", size=10, bold=True, color="166534")

    fill_main_green = PatternFill(start_color="B6D7A8", end_color="B6D7A8", fill_type="solid") # Google Sheets Pale Green
    fill_col_green = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")  # Lighter pale green
    fill_fail = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    fill_pass = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")

    border_thin = Border(
        left=Side(style='thin', color='D3D3D3'),
        right=Side(style='thin', color='D3D3D3'),
        top=Side(style='thin', color='D3D3D3'),
        bottom=Side(style='thin', color='D3D3D3')
    )
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    # -------------------------------------------------------------
    # CREATE 'Index' SHEET
    # -------------------------------------------------------------
    ws_index = wb.create_sheet(title="Index")
    ws_index.views.sheetView[0].showGridLines = True

    # Row 1: Merged 'Index'
    ws_index.merge_cells("A1:C1")
    cell_idx = ws_index["A1"]
    cell_idx.value = "Index"
    cell_idx.font = font_main_header
    cell_idx.fill = fill_main_green
    cell_idx.alignment = align_center
    ws_index.row_dimensions[1].height = 28

    # Apply borders & fill across merged cells
    for col_l in ["A", "B", "C"]:
        c = ws_index[f"{col_l}1"]
        c.border = border_thin
        c.fill = fill_main_green

    # Row 2: Header Columns
    headers = ["Errors", "Status", "Comments"]
    ws_index.row_dimensions[2].height = 22
    for col_num, h_text in enumerate(headers, 1):
        c = ws_index.cell(row=2, column=col_num)
        c.value = h_text
        c.font = font_col_header
        c.fill = fill_col_green
        c.alignment = align_center if col_num == 2 else align_left
        c.border = border_thin

    # Rows 3+: Data Rows
    current_row = 3
    for item in index_rows:
        ws_index.row_dimensions[current_row].height = 20
        c_err = ws_index.cell(row=current_row, column=1)
        c_stat = ws_index.cell(row=current_row, column=2)
        c_comm = ws_index.cell(row=current_row, column=3)

        c_err.value = item["error_name"]
        sheet_target = item.get("sheet_name")
        # If there's an associated error tab, add hyperlink!
        if sheet_target and sheet_target in error_dfs:
            # Excel internal sheet hyperlink formula
            c_err.hyperlink = f"#'{sheet_target}'!A1"
            c_err.font = font_link
        else:
            c_err.font = font_data

        c_err.alignment = align_left
        c_err.border = border_thin

        c_stat.value = item["status"]
        if item.get("is_error", False):
            c_stat.fill = fill_fail
            c_stat.font = font_status_fail
        else:
            c_stat.fill = fill_pass
            c_stat.font = font_status_pass
        c_stat.alignment = align_center
        c_stat.border = border_thin

        c_comm.value = item["comments"]
        c_comm.font = font_data
        c_comm.alignment = align_left
        c_comm.border = border_thin

        current_row += 1

    # Column widths for Index sheet
    ws_index.column_dimensions["A"].width = 38
    ws_index.column_dimensions["B"].width = 24
    ws_index.column_dimensions["C"].width = 65
    ws_index.freeze_panes = "A3"

    # -------------------------------------------------------------
    # CREATE INDIVIDUAL ERROR SHEETS
    # -------------------------------------------------------------
    for sheet_name, df_err in error_dfs.items():
        if df_err.empty:
            continue

        ws_err = wb.create_sheet(title=sheet_name)
        ws_err.views.sheetView[0].showGridLines = True

        # Header Row
        ws_err.row_dimensions[1].height = 24
        col_names = list(df_err.columns)
        for col_idx, col_name in enumerate(col_names, 1):
            c = ws_err.cell(row=1, column=col_idx)
            c.value = str(col_name)
            c.font = font_col_header
            c.fill = fill_col_green
            c.alignment = align_center if "Status" in col_name or "Count" in col_name else align_left
            c.border = border_thin

        # Data Rows
        for r_idx, row_data in enumerate(df_err.itertuples(index=False), 2):
            ws_err.row_dimensions[r_idx].height = 20
            for c_idx, val in enumerate(row_data, 1):
                c = ws_err.cell(row=r_idx, column=c_idx)
                c.value = val if val is not None else ""
                c.font = font_data
                c.border = border_thin
                c.alignment = align_left
                # Link formatting for URLs
                if isinstance(val, str) and val.startswith("http"):
                    c.font = font_link

        # Auto-adjust column widths
        for col in ws_err.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_err.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 70)

        ws_err.freeze_panes = "A2"

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
