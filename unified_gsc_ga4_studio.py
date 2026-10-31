"""
Unified GSC + GA4 Intelligence & Opportunity Engine
===================================================
A master-level technical SEO and behavioral planning studio that bridges pre-click
search visibility (Google Search Console API) with post-click engagement and conversions
(Google Analytics 4 Data API v1beta).

Modules:
- Module 1: Unified URL Data Merger & Period-over-Period Engine (Normalized Path Join)
- Module 2: Combined SEO Opportunity Finder (4 Smart Tabs with Dynamic Sliders)
- Module 3: Automated Content Audit & Action Buckets (Winners, Decay, Merge, Prune)
- Module 4: Keyword Cannibalization Detector (Multi-URL Conflict Resolution)
- Module 5: Topic Cluster & Question Planner (FAQ Briefs & High-Value Keyword Gaps)
- Module 6: SEO Traffic & Conversion Simulator + Interactive Task Board with Impact Tracking
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
    get_date_bounds,
    clean_ctr_val,
    read_csv_robust,
    parse_gsc_and_ga4_upload
)

from gsc_advanced_analyzer import (
    make_clean_export_filename,
    extract_brand_tokens,
    is_brand_query,
    export_action_plan_to_excel,
    export_action_plan_to_docx
)


# ==============================================================================
# MODULE 1: UNIFIED URL DATA MERGER & PERIOD-OVER-PERIOD ENGINE
# ==============================================================================

def normalize_canonical_path(url_or_path: str) -> str:
    """
    Normalizes GSC full URLs and GA4 relative landing pages into a clean canonical path.
    Strips protocol, www, domain, trailing slash, and tracking query params (utm_*, gclid, etc.).
    Example: 'https://example.com/shop/valves/?utm_source=google' -> '/shop/valves'
    """
    if not url_or_path or pd.isna(url_or_path):
        return "/"
    s = str(url_or_path).strip()
    if s.startswith("http://") or s.startswith("https://"):
        parsed = urllib.parse.urlparse(s)
        path = parsed.path
        raw_query = parsed.query
    else:
        parts = s.split("?")
        path = parts[0]
        raw_query = parts[1] if len(parts) > 1 else ""

    path = "/" + path.strip("/")
    if path == "":
        path = "/"

    # Strip standard marketing query params while preserving functional parameters if necessary
    if raw_query:
        params = urllib.parse.parse_qs(raw_query)
        tracking_keys = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'gclid', 'fbclid', 'msclkid', 'yclid', 'ref', 'source', '_ga'
        }
        clean_params = {k: v for k, v in params.items() if k.lower() not in tracking_keys}
        if clean_params:
            path += "?" + urllib.parse.urlencode(clean_params, doseq=True)

    return path.lower()


def fetch_comprehensive_ga4_url_metrics(
    creds,
    ga4_property_id: str,
    curr_start: str,
    curr_end: str,
    prev_start: str,
    prev_end: str
) -> pd.DataFrame:
    """
    Fetches GA4 landing page performance for current and previous periods:
    Sessions, Engaged Sessions, Engagement Duration, Conversions, and Event Count.
    """
    if not ga4_property_id or ga4_property_id == "None" or not GOOGLE_OAUTH_LIBS_AVAILABLE or BetaAnalyticsDataClient is None:
        return pd.DataFrame()

    try:
        data_client = BetaAnalyticsDataClient(credentials=creds)
        prop_str = ga4_property_id if ga4_property_id.startswith("properties/") else f"properties/{ga4_property_id}"

        # Current Period
        req_curr = RunReportRequest(
            property=prop_str,
            dimensions=[Dimension(name="landingPagePlusQueryString")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="engagedSessions"),
                Metric(name="userEngagementDuration"),
                Metric(name="conversions"),
                Metric(name="eventCount")
            ],
            date_ranges=[DateRange(start_date=curr_start, end_date=curr_end)],
            limit=25000
        )
        rep_curr = data_client.run_report(req_curr)

        # Previous Period
        req_prev = RunReportRequest(
            property=prop_str,
            dimensions=[Dimension(name="landingPagePlusQueryString")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="conversions")
            ],
            date_ranges=[DateRange(start_date=prev_start, end_date=prev_end)],
            limit=25000
        )
        rep_prev = data_client.run_report(req_prev)

        prev_map = {}
        for row in rep_prev.rows:
            raw_url = row.dimension_values[0].value
            norm_p = normalize_canonical_path(raw_url)
            p_sess = int(row.metric_values[0].value) if len(row.metric_values) > 0 else 0
            p_conv = int(row.metric_values[1].value) if len(row.metric_values) > 1 else 0
            prev_map[norm_p] = {"prev_sessions": p_sess, "prev_conversions": p_conv}

        rows = []
        for row in rep_curr.rows:
            raw_url = row.dimension_values[0].value
            norm_p = normalize_canonical_path(raw_url)
            sess = int(row.metric_values[0].value) if len(row.metric_values) > 0 else 0
            eng_sess = int(row.metric_values[1].value) if len(row.metric_values) > 1 else 0
            duration = float(row.metric_values[2].value) if len(row.metric_values) > 2 else 0.0
            conv = int(row.metric_values[3].value) if len(row.metric_values) > 3 else 0
            events = int(row.metric_values[4].value) if len(row.metric_values) > 4 else 0

            p_info = prev_map.get(norm_p, {"prev_sessions": 0, "prev_conversions": 0})
            prev_sess = p_info["prev_sessions"]
            prev_conv = p_info["prev_conversions"]

            eng_rate = (eng_sess / sess) if sess > 0 else 0.0
            conv_rate = (conv / sess) if sess > 0 else 0.0
            avg_time = (duration / sess) if sess > 0 else 0.0
            sess_delta = round(((sess - prev_sess) / prev_sess * 100), 1) if prev_sess > 0 else 0.0
            conv_delta = round(((conv - prev_conv) / prev_conv * 100), 1) if prev_conv > 0 else 0.0

            rows.append({
                "norm_path": norm_p,
                "raw_ga4_url": raw_url,
                "sessions": sess,
                "engaged_sessions": eng_sess,
                "engagement_rate": eng_rate,
                "avg_engagement_time_sec": avg_time,
                "conversions": conv,
                "conversion_rate": conv_rate,
                "event_count": events,
                "prev_sessions": prev_sess,
                "prev_conversions": prev_conv,
                "sessions_delta_pct": sess_delta,
                "conversions_delta_pct": conv_delta
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            # Aggregate if multiple raw landing pages map to the same normalized path
            agg_rules = {
                "sessions": "sum",
                "engaged_sessions": "sum",
                "conversions": "sum",
                "event_count": "sum",
                "prev_sessions": "sum",
                "prev_conversions": "sum",
                "avg_engagement_time_sec": "mean"
            }
            df = df.groupby("norm_path", as_index=False).agg(agg_rules)
            df["engagement_rate"] = np.where(df["sessions"] > 0, df["engaged_sessions"] / df["sessions"], 0.0)
            df["conversion_rate"] = np.where(df["sessions"] > 0, df["conversions"] / df["sessions"], 0.0)
            df["sessions_delta_pct"] = np.where(df["prev_sessions"] > 0, (df["sessions"] - df["prev_sessions"]) / df["prev_sessions"] * 100, 0.0)
            df["conversions_delta_pct"] = np.where(df["prev_conversions"] > 0, (df["conversions"] - df["prev_conversions"]) / df["prev_conversions"] * 100, 0.0)
        return df
    except Exception as e:
        print(f"Error fetching GA4 URL metrics: {e}")
        return pd.DataFrame()


def build_unified_url_master(
    queries_df: pd.DataFrame,
    pages_df: pd.DataFrame,
    ga4_df: pd.DataFrame,
    base_domain: str = ""
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Normalizes and merges GSC queries, pages, and GA4 metrics onto canonical paths.
    Returns:
    - unified_urls_df: One row per canonical URL with combined GSC + GA4 performance and deltas.
    - enriched_queries_df: Queries enriched with target landing page and GA4 engagement rate.
    """
    if queries_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 1. Enrich Queries with normalized paths
    enriched_queries = queries_df.copy()
    if "page" not in enriched_queries.columns:
        enriched_queries["page"] = base_domain or "/"

    enriched_queries["norm_path"] = enriched_queries["page"].apply(normalize_canonical_path)

    # Attach Top Queries list per URL
    top_queries_per_url = (
        enriched_queries.sort_values(by=["norm_path", "clicks"], ascending=[True, False])
        .groupby("norm_path")["query"]
        .apply(lambda s: list(s.dropna().unique()[:8]))
        .to_dict()
    )

    # 2. Aggregate GSC metrics per normalized URL
    gsc_url_agg = enriched_queries.groupby("norm_path", as_index=False).agg(
        total_clicks=("clicks", "sum"),
        total_impressions=("impressions", "sum"),
        avg_position=("position", "mean"),
        query_count=("query", "nunique")
    )
    gsc_url_agg["gsc_ctr"] = np.where(
        gsc_url_agg["total_impressions"] > 0,
        gsc_url_agg["total_clicks"] / gsc_url_agg["total_impressions"],
        0.0
    )
    gsc_url_agg["top_queries"] = gsc_url_agg["norm_path"].map(top_queries_per_url).fillna("").apply(list)

    # Incorporate previous period pages comparison if available in pages_df
    if not pages_df.empty and "page" in pages_df.columns:
        pages_copy = pages_df.copy()
        pages_copy["norm_path"] = pages_copy["page"].apply(normalize_canonical_path)
        p_agg = pages_copy.groupby("norm_path", as_index=False).agg({
            c: "sum" for c in ["prev_clicks", "prev_imp"] if c in pages_copy.columns
        })
        gsc_url_agg = pd.merge(gsc_url_agg, p_agg, on="norm_path", how="left").fillna(0)
    else:
        gsc_url_agg["prev_clicks"] = 0
        gsc_url_agg["prev_imp"] = 0

    gsc_url_agg["clicks_delta_pct"] = np.where(
        gsc_url_agg["prev_clicks"] > 0,
        (gsc_url_agg["total_clicks"] - gsc_url_agg["prev_clicks"]) / gsc_url_agg["prev_clicks"] * 100,
        0.0
    )
    gsc_url_agg["imp_delta_pct"] = np.where(
        gsc_url_agg["prev_imp"] > 0,
        (gsc_url_agg["total_impressions"] - gsc_url_agg["prev_imp"]) / gsc_url_agg["prev_imp"] * 100,
        0.0
    )

    # 3. Merge with GA4 URL metrics on norm_path
    if not ga4_df.empty and "norm_path" in ga4_df.columns:
        unified_urls = pd.merge(gsc_url_agg, ga4_df, on="norm_path", how="outer")
    else:
        unified_urls = gsc_url_agg.copy()
        for ga4_col in ["sessions", "engaged_sessions", "engagement_rate", "conversions", "conversion_rate", "sessions_delta_pct", "conversions_delta_pct"]:
            unified_urls[ga4_col] = 0.0

    # Fill NaNs
    fill_zeros = ["total_clicks", "total_impressions", "prev_clicks", "prev_imp", "sessions", "engaged_sessions", "conversions"]
    for col in fill_zeros:
        if col in unified_urls.columns:
            unified_urls[col] = unified_urls[col].fillna(0).astype(int)

    unified_urls["gsc_ctr"] = unified_urls["gsc_ctr"].fillna(0.0)
    unified_urls["avg_position"] = unified_urls["avg_position"].fillna(0.0).round(1)
    unified_urls["engagement_rate"] = unified_urls["engagement_rate"].fillna(0.0)
    unified_urls["conversion_rate"] = unified_urls["conversion_rate"].fillna(0.0)
    unified_urls["top_queries"] = unified_urls["top_queries"].apply(lambda x: x if isinstance(x, list) else [])

    # Format full canonical display URL
    b_domain = base_domain.rstrip("/") if base_domain else "https://yourdomain.com"
    unified_urls["full_canonical_url"] = b_domain + unified_urls["norm_path"]

    # Attach GA4 engagement rate back to enriched queries
    ga4_map = unified_urls.set_index("norm_path")[["engagement_rate", "conversion_rate"]].to_dict(orient="index")
    enriched_queries["page_engagement_rate"] = enriched_queries["norm_path"].map(
        lambda p: ga4_map.get(p, {}).get("engagement_rate", 0.0)
    )
    enriched_queries["page_conversion_rate"] = enriched_queries["norm_path"].map(
        lambda p: ga4_map.get(p, {}).get("conversion_rate", 0.0)
    )

    return unified_urls, enriched_queries


# ==============================================================================
# MODULE 2: COMBINED SEO OPPORTUNITY FINDER (4 SMART TABS)
# ==============================================================================

def compute_seo_opportunities(
    unified_urls: pd.DataFrame,
    enriched_queries: pd.DataFrame,
    min_striking_imp: int = 50,
    striking_min_pos: float = 8.0,
    striking_max_pos: float = 20.0
) -> dict:
    """
    Computes actionable pre-click & post-click opportunities across 4 smart categories.
    """
    if enriched_queries.empty:
        return {"striking": pd.DataFrame(), "ctr_leak": pd.DataFrame(), "intent_mismatch": pd.DataFrame(), "gems": pd.DataFrame()}

    # 1. Striking Distance Keywords (Pos 8 to 20, high impressions)
    striking_df = enriched_queries[
        (enriched_queries["position"] >= striking_min_pos) &
        (enriched_queries["position"] <= striking_max_pos) &
        (enriched_queries["impressions"] >= min_striking_imp)
    ].sort_values(by="impressions", ascending=False).copy()

    striking_df["recommendation"] = "Add query to H2/FAQ, strengthen internal links, and expand topical depth."

    # 2. CTR Opportunity Finder (Title & Meta Optimizer)
    # Expected benchmark: Pos 1 < 15%, Pos 2 < 10%, Pos 3 < 7%, Pos 4-5 < 4%
    def get_expected_ctr(pos: float) -> float:
        if pos <= 1.5:
            return 0.15
        elif pos <= 2.5:
            return 0.10
        elif pos <= 3.5:
            return 0.07
        elif pos <= 5.5:
            return 0.04
        return 0.02

    ctr_candidates = enriched_queries[
        (enriched_queries["position"] <= 5.5) &
        (enriched_queries["impressions"] >= 200)
    ].copy()
    ctr_candidates["benchmark_ctr"] = ctr_candidates["position"].apply(get_expected_ctr)
    ctr_leak_df = ctr_candidates[ctr_candidates["ctr"] < ctr_candidates["benchmark_ctr"]].sort_values(by="impressions", ascending=False).copy()
    ctr_leak_df["ctr_gap_pct"] = (ctr_leak_df["benchmark_ctr"] - ctr_leak_df["ctr"]) * 100
    ctr_leak_df["recommendation"] = "Rewrite Meta Title & Description with emotional hooks & numbers to capture leaked clicks."

    # 3. Traffic vs. Intent Mismatch (UX & Content Fix)
    # High GSC Clicks (top 30% of pages) + Low GA4 Engagement Rate (<40%) or 0 Conversions
    if not unified_urls.empty and "total_clicks" in unified_urls.columns and unified_urls["total_clicks"].max() > 0:
        click_threshold = unified_urls["total_clicks"].quantile(0.70)
        intent_mismatch_df = unified_urls[
            (unified_urls["total_clicks"] >= max(click_threshold, 15)) &
            ((unified_urls["engagement_rate"] < 0.40) | (unified_urls["conversions"] == 0))
        ].sort_values(by="total_clicks", ascending=False).copy()
        intent_mismatch_df["recommendation"] = "Align above-the-fold content with user search intent, improve page speed, and add clear CTAs."
    else:
        intent_mismatch_df = pd.DataFrame()

    # 4. Hidden Conversion Gems (Scale Candidates)
    # High GA4 Conversion Rate (> 2%) or High Engagement (> 70%) + Lower GSC Visibility (Pos 11-30)
    if not unified_urls.empty:
        gems_df = unified_urls[
            ((unified_urls["conversion_rate"] >= 0.02) | (unified_urls["engagement_rate"] >= 0.70)) &
            (unified_urls["avg_position"] >= 10.5) &
            (unified_urls["avg_position"] <= 30.0)
        ].sort_values(by=["conversion_rate", "sessions"], ascending=[False, False]).copy()
        gems_df["recommendation"] = "High commercial affinity! Prioritize backlink acquisition, supporting cluster posts, and menu visibility."
    else:
        gems_df = pd.DataFrame()

    return {
        "striking": striking_df,
        "ctr_leak": ctr_leak_df,
        "intent_mismatch": intent_mismatch_df,
        "gems": gems_df
    }


# ==============================================================================
# MODULE 3: AUTOMATED CONTENT AUDIT & ACTION BUCKETS
# ==============================================================================

def classify_content_audit_buckets(unified_urls: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Categorizes every URL into 1 of 4 strategic SEO action buckets:
    - Keep & Scale (Winners)
    - Update & Refresh (Content Decay)
    - Consolidate (Merge Candidates)
    - Prune / Review (Dead Weight)
    """
    if unified_urls.empty:
        return {"winners": pd.DataFrame(), "decay": pd.DataFrame(), "consolidate": pd.DataFrame(), "prune": pd.DataFrame()}

    urls = unified_urls.copy()

    # 1. Update & Refresh (Decay: clicks dropped >= 20% or avg position dropped >= 3 spots)
    decay_cond = (
        (urls["clicks_delta_pct"] <= -20.0) & (urls["prev_clicks"] >= 15)
    )
    decay_bucket = urls[decay_cond].sort_values(by="total_clicks", ascending=False).copy()
    decay_bucket["bucket"] = "Update & Refresh (Decay)"
    decay_bucket["action_plan"] = "Audit competitor ranking changes, refresh outdated stats/dates, and re-promote on social channels."

    # 2. Prune / Review (Dead Weight: impressions < 50, 0 clicks, < 10 GA4 sessions)
    prune_cond = (
        (urls["total_impressions"] < 50) &
        (urls["total_clicks"] == 0) &
        (urls["sessions"] < 10) &
        (~urls.index.isin(decay_bucket.index))
    )
    prune_bucket = urls[prune_cond].copy()
    prune_bucket["bucket"] = "Prune / Review (Dead Weight)"
    prune_bucket["action_plan"] = "Evaluate whether to set Noindex, consolidate into a cornerstone guide, or 410/301 redirect."

    # 3. Consolidate (Merge Candidates: low traffic, multiple query overlap or thin URLs)
    consolidate_cond = (
        (urls["total_clicks"] <= 5) &
        (urls["total_impressions"] >= 50) &
        (~urls.index.isin(decay_bucket.index)) &
        (~urls.index.isin(prune_bucket.index))
    )
    consolidate_bucket = urls[consolidate_cond].copy()
    consolidate_bucket["bucket"] = "Consolidate (Merge Candidate)"
    consolidate_bucket["action_plan"] = "Merge thin topic variations into a comprehensive authority pillar page and 301 redirect."

    # 4. Keep & Scale (Winners: positive/stable clicks and high engagement)
    winner_cond = (
        (~urls.index.isin(decay_bucket.index)) &
        (~urls.index.isin(prune_bucket.index)) &
        (~urls.index.isin(consolidate_bucket.index))
    )
    winner_bucket = urls[winner_cond].sort_values(by="total_clicks", ascending=False).copy()
    winner_bucket["bucket"] = "Keep & Scale (Winners)"
    winner_bucket["action_plan"] = "Protect rankings, build internal links out to supporting cluster pages, and test micro-conversion CTAs."

    return {
        "winners": winner_bucket,
        "decay": decay_bucket,
        "consolidate": consolidate_bucket,
        "prune": prune_bucket
    }


# ==============================================================================
# MODULE 4: KEYWORD CANNIBALIZATION DETECTOR
# ==============================================================================

def detect_keyword_cannibalization(queries_df: pd.DataFrame, unified_urls: pd.DataFrame) -> pd.DataFrame:
    """
    Groups by query where 2+ distinct URLs receive impressions/clicks and neither URL holds > 85% clicks.
    """
    if queries_df.empty or "page" not in queries_df.columns:
        return pd.DataFrame()

    ga4_eng_map = unified_urls.set_index("norm_path")["engagement_rate"].to_dict() if not unified_urls.empty else {}

    results = []
    for q, group in queries_df.groupby("query"):
        uniq_pages = group["page"].dropna().unique()
        if len(uniq_pages) > 1 and group["impressions"].sum() >= 250:
            total_clicks = group["clicks"].sum()
            max_url_clicks = group["clicks"].max()
            share_of_max = (max_url_clicks / total_clicks) if total_clicks > 0 else 0.0

            # Only flag if traffic is split (< 85% dominance)
            if share_of_max < 0.85:
                url_breakdowns = []
                for _, r in group.sort_values(by="clicks", ascending=False).iterrows():
                    p_url = r["page"]
                    norm_p = normalize_canonical_path(p_url)
                    eng_rate = ga4_eng_map.get(norm_p, 0.0)
                    url_breakdowns.append({
                        "url": p_url,
                        "clicks": int(r["clicks"]),
                        "impressions": int(r["impressions"]),
                        "ctr": float(r["ctr"]),
                        "position": float(r["position"]),
                        "engagement_rate": eng_rate
                    })

                results.append({
                    "query": q,
                    "url_count": len(uniq_pages),
                    "total_clicks": int(total_clicks),
                    "total_impressions": int(group["impressions"].sum()),
                    "best_position": float(group["position"].min()),
                    "severity": "HIGH SEVERITY" if len(uniq_pages) >= 3 else "MODERATE",
                    "competing_pages": url_breakdowns
                })

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by="total_impressions", ascending=False)
    return df


# ==============================================================================
# MODULE 5: TOPIC CLUSTER & QUESTION PLANNER
# ==============================================================================

def generate_topic_cluster_and_questions(enriched_queries: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    1. Question Explorer: Regex filters questions (how, what, why, when, guide, vs, kya, kaise).
    2. New Cluster Opportunities: High impressions (>100), 0 clicks or pos > 15 without a dedicated URL.
    """
    if enriched_queries.empty:
        return pd.DataFrame(), pd.DataFrame()

    q_pattern = r'^(who|what|where|when|why|how|can|should|is|are|best|vs|versus|kaise|kya)\b|\?'
    questions = enriched_queries[
        enriched_queries["query"].str.contains(q_pattern, case=False, na=False, regex=True)
    ].sort_values(by="impressions", ascending=False).copy()
    questions["content_type"] = "FAQ Accordion / Blog Answer"

    # New Cluster Candidates
    cluster_candidates = enriched_queries[
        (enriched_queries["impressions"] >= 100) &
        ((enriched_queries["clicks"] == 0) | (enriched_queries["position"] > 15.0))
    ].sort_values(by="impressions", ascending=False).copy()
    cluster_candidates["opportunity_type"] = "Create Dedicated Sub-Topic Landing Page"

    return questions, cluster_candidates


# ==============================================================================
# MODULE 6: TRAFFIC FORECASTER & INTERACTIVE TASK BOARD
# ==============================================================================

def simulate_traffic_and_revenue_uplift(
    striking_df: pd.DataFrame,
    default_lead_value: float = 50.0
) -> pd.DataFrame:
    """
    Calculates projected monthly clicks and conversions if striking-distance keywords
    advance to Position #1 (25% CTR), Position #2 (15% CTR), or Position #3 (10% CTR).
    """
    if striking_df.empty:
        return pd.DataFrame()

    sim = striking_df.copy()
    sim["proj_clicks_pos_1"] = (sim["impressions"] * 0.25).astype(int)
    sim["proj_clicks_pos_2"] = (sim["impressions"] * 0.15).astype(int)
    sim["proj_clicks_pos_3"] = (sim["impressions"] * 0.10).astype(int)

    sim["net_new_clicks_pos_1"] = np.maximum(sim["proj_clicks_pos_1"] - sim["clicks"], 0)
    sim["net_new_clicks_pos_3"] = np.maximum(sim["proj_clicks_pos_3"] - sim["clicks"], 0)

    # Use page conversion rate or fallback conservative 1.5%
    conv_rates = sim["page_conversion_rate"].replace(0.0, 0.015)
    sim["projected_new_conversions_pos_1"] = (sim["net_new_clicks_pos_1"] * conv_rates).round(1)
    sim["projected_value_gain_pos_1"] = (sim["projected_new_conversions_pos_1"] * default_lead_value).round(2)

    return sim.sort_values(by="net_new_clicks_pos_1", ascending=False)


def add_insight_to_task_board(task_title: str, target_url: str, priority: str, impact_reason: str):
    """Adds a task item to the interactive session task board."""
    if "seo_task_board" not in st.session_state:
        st.session_state["seo_task_board"] = []

    # Check duplicate
    for t in st.session_state["seo_task_board"]:
        if t["title"] == task_title and t["url"] == target_url:
            st.toast(f"Task already exists in your plan: '{task_title}'", icon="ℹ️")
            return

    new_task = {
        "id": f"task_{len(st.session_state['seo_task_board']) + 1}",
        "title": task_title,
        "url": target_url,
        "priority": priority,
        "status": "To Do",
        "impact_reason": impact_reason,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "implemented_at": None
    }
    st.session_state["seo_task_board"].append(new_task)
    st.toast(f"✅ Added to SEO Task Board: '{task_title}'", icon="🚀")


# ==============================================================================
# MAIN PAGE RENDERER & INTERACTIVE DASHBOARD
# ==============================================================================

def render_unified_gsc_ga4_studio():
    """Renders the complete Unified GSC + GA4 Intelligence & Opportunity Engine."""

    # 1. Cockpit Hero Banner matching CrawlPilot Cyber Cockpit Theme
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(11, 20, 38, 0.92) 0%, rgba(6, 12, 24, 0.98) 100%); padding: 2.2rem 2.6rem; border-radius: 20px; border: 1px solid rgba(0, 240, 255, 0.22); margin-bottom: 1.5rem; box-shadow: 0 20px 50px rgba(0,0,0,0.7), 0 0 35px rgba(0, 240, 255, 0.08); position: relative; overflow: hidden; backdrop-filter: blur(20px);">
        <!-- Ambient Cyber Corner Glows -->
        <div style="position: absolute; top: -40px; right: 20%; width: 220px; height: 180px; background: radial-gradient(circle, rgba(0, 240, 255, 0.15) 0%, transparent 70%); pointer-events: none;"></div>
        <div style="position: absolute; bottom: -30px; left: 10%; width: 180px; height: 140px; background: radial-gradient(circle, rgba(45, 212, 191, 0.12) 0%, transparent 70%); pointer-events: none;"></div>

        <div style="position: relative; z-index: 2;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 1rem;">
                <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(16, 185, 129, 0.12); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.35); padding: 4px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; box-shadow: 0 0 12px rgba(16, 185, 129, 0.2);">
                    <span class="hud-beacon"></span> UNIFIED GSC + GA4 ENGINE
                </div>
                <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(0, 240, 255, 0.12); color: #00F0FF; border: 1px solid rgba(0, 240, 255, 0.35); padding: 4px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; box-shadow: 0 0 12px rgba(0, 240, 255, 0.2);">
                    <span>⚡</span> PRE-CLICK & POST-CLICK MERGED
                </div>
                <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(45, 212, 191, 0.12); color: #2DD4BF; border: 1px solid rgba(45, 212, 191, 0.35); padding: 4px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace;">
                    <span>🎯</span> CONVERSION & OPPORTUNITY ENGINE
                </div>
            </div>

            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #00F0FF; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 6px;">
                TECHNICAL SEO ARCHITECTURE • REVENUE & TRAFFIC EXPANSION
            </div>

            <h1 style="font-family: 'Orbitron', 'Space Grotesk', sans-serif; font-size: 2.7rem; font-weight: 900; color: #FFFFFF; margin: 0 0 0.5rem 0; letter-spacing: -0.01em;">
                <span style="color: #FFFFFF; text-shadow: 0 0 30px rgba(255,255,255,0.4);">Unified</span> <span style="background: linear-gradient(135deg, #00F0FF 0%, #2DD4BF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 0 30px rgba(0, 240, 255, 0.45);">(GSC + GA4) Intelligence</span>
            </h1>

            <p style="color: #94A3B8; font-size: 0.98rem; max-width: 860px; margin: 0; line-height: 1.65; font-family: 'Space Grotesk', sans-serif;">
                Actionable SEO Planning & Opportunity Engine that joins pre-click rankings and search intent with post-click behavioral analytics and conversions. Uncover striking distance keywords, CTR opportunities, keyword cannibalization, content decay, and revenue projections.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Ingestion Options (OAuth 2.0 vs Manual Upload)
    data_source_mode = st.radio(
        "Select Acquisition Engine",
        options=[
            "🔗 Connect Live Google Account (Auto-Detect GSC & GA4 - Zero Manual Work)",
            "📁 Manual CSV / ZIP Upload (With 1-Click Demo Dataset)"
        ],
        horizontal=True,
        key="master_studio_ingest_mode"
    )

    client_id, client_secret, redirect_uri = get_oauth_config()

    # --------------------------------------------------------------------------
    # DATA SOURCE: LIVE GOOGLE OAUTH
    # --------------------------------------------------------------------------
    if "Connect Live Google Account" in data_source_mode:
        if not GOOGLE_OAUTH_LIBS_AVAILABLE:
            st.warning(f"⚠️ Google OAuth packages installing. Details: `{GOOGLE_OAUTH_IMPORT_ERROR}`. Switch to 'Manual CSV / ZIP' above to use exports or demo data.")
        else:
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
                st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(6, 12, 24, 0.9) 100%); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 14px; padding: 1.1rem 1.6rem; margin-bottom: 1.3rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span class="hud-beacon"></span>
                        <div>
                            <div style="color: #34D399; font-weight: 800; font-size: 1.05rem; font-family: 'Space Grotesk', sans-serif;">Live Google Account Connected</div>
                            <div style="color: #94A3B8; font-size: 0.82rem; font-family: 'Space Grotesk', sans-serif;">Direct API link active. Select properties to join GSC & GA4 performance data.</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.spinner("Auto-detecting verified Search Console & GA4 properties..."):
                    gsc_properties = fetch_live_gsc_properties(active_creds)
                    ga4_properties = fetch_live_ga4_properties(active_creds)

                col_p1, col_p2, col_p3 = st.columns([1.8, 1.8, 1.2])
                with col_p1:
                    selected_gsc_property = st.selectbox("Select GSC Property", options=gsc_properties) if gsc_properties else None
                with col_p2:
                    ga4_options_labels = ["None (Skip GA4)"] + [p["label"] for p in ga4_properties]
                    selected_ga4_label = st.selectbox("Select GA4 Property", options=ga4_options_labels)
                    selected_ga4_id = None
                    if selected_ga4_label != "None (Skip GA4)":
                        for gp in ga4_properties:
                            if gp["label"] == selected_ga4_label:
                                selected_ga4_id = gp["id"]
                                break
                with col_p3:
                    date_choice = st.selectbox("Date Range", options=["Last 28 Days", "Last 3 Months", "Last 6 Months", "Custom"])

                custom_start, custom_end = None, None
                if date_choice == "Custom":
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        custom_start = st.date_input("Start Date", value=datetime.now() - timedelta(days=28))
                    with col_d2:
                        custom_end = st.date_input("End Date", value=datetime.now() - timedelta(days=3))

                btn_f1, btn_f2 = st.columns([3.5, 1.2])
                with btn_f1:
                    btn_run = st.button("🚀 Fetch & Join GSC + GA4 Intelligence", type="primary", use_container_width=True)
                with btn_f2:
                    if st.button("🔌 Disconnect Google", use_container_width=True):
                        st.session_state["g_oauth_creds"] = None
                        st.session_state["master_dataset"] = None
                        st.rerun()

                if btn_run and selected_gsc_property:
                    c_start, c_end, p_start, p_end = get_date_bounds(date_choice, custom_start, custom_end)
                    with st.spinner(f"Querying GSC & GA4 APIs ({c_start} to {c_end}) with period comparison..."):
                        try:
                            # 1. Fetch GSC
                            gsc_service = build('searchconsole', 'v1', credentials=active_creds, cache_discovery=False)
                            q_res = gsc_service.searchanalytics().query(
                                siteUrl=selected_gsc_property,
                                body={'startDate': c_start, 'endDate': c_end, 'dimensions': ['query', 'page'], 'rowLimit': 25000}
                            ).execute()
                            queries_list = [{
                                'query': str(r.get('keys', ['', ''])[0]),
                                'page': str(r.get('keys', ['', ''])[1]),
                                'clicks': int(r.get('clicks', 0)),
                                'impressions': int(r.get('impressions', 0)),
                                'ctr': float(r.get('ctr', 0.0)),
                                'position': round(float(r.get('position', 0.0)), 1)
                            } for r in q_res.get('rows', [])]
                            live_queries_df = pd.DataFrame(queries_list)

                            # Fetch previous period pages
                            p_prev_res = gsc_service.searchanalytics().query(
                                siteUrl=selected_gsc_property,
                                body={'startDate': p_start, 'endDate': p_end, 'dimensions': ['page'], 'rowLimit': 10000}
                            ).execute()
                            prev_pages_df = pd.DataFrame([{
                                'page': str(r['keys'][0]),
                                'prev_clicks': int(r.get('clicks', 0)),
                                'prev_imp': int(r.get('impressions', 0))
                            } for r in p_prev_res.get('rows', []) if r.get('keys')])

                            # 2. Fetch GA4
                            live_ga4_df = fetch_comprehensive_ga4_url_metrics(
                                active_creds, selected_ga4_id, c_start, c_end, p_start, p_end
                            )

                            st.session_state["master_dataset"] = {
                                "queries": live_queries_df,
                                "pages": prev_pages_df,
                                "ga4": live_ga4_df,
                                "property_gsc": selected_gsc_property,
                                "property_ga4": selected_ga4_id or "None",
                                "date_range": f"{c_start} to {c_end}",
                                "is_mock": False
                            }
                            st.success(f"✅ Merged Data Successfully! Fetched {len(live_queries_df):,} query-page rows.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error executing API calls: {e}")

            else:
                # Login Banner
                st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(11, 20, 38, 0.92) 0%, rgba(6, 12, 24, 0.98) 100%); border: 1px solid rgba(0, 240, 255, 0.22); border-radius: 16px; padding: 1.6rem 2rem; margin-bottom: 1.3rem; box-shadow: 0 15px 35px rgba(0,0,0,0.65), 0 0 25px rgba(0, 240, 255, 0.08); backdrop-filter: blur(20px);">
                    <div style="font-family: 'Space Grotesk', sans-serif; font-weight: 800; color: #FFFFFF; font-size: 1.25rem; margin-bottom: 6px; display: flex; align-items: center; gap: 10px;">
                        <span style="color: #00F0FF; font-size: 1.3rem;">🔗</span> Connect Your Google Account
                    </div>
                    <div style="color: #94A3B8; font-size: 0.92rem; line-height: 1.6; font-family: 'Space Grotesk', sans-serif;">
                        One-click sign in via Google OAuth 2.0 to access your verified Search Console domains and GA4 properties.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander("⚙️ Configure Google OAuth Credentials", expanded=(not client_id or not client_secret)):
                    ui_cid = st.text_input("Client ID", value=client_id, placeholder="xxxx.apps.googleusercontent.com", key="m_oauth_cid")
                    ui_csec = st.text_input("Client Secret", value=client_secret, type="password", placeholder="GOCSPX-xxxx", key="m_oauth_csec")
                    ui_ruri = st.text_input("Authorized Redirect URI", value=redirect_uri, key="m_oauth_ruri")
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
                        st.link_button("🔗 Sign In With Google (Connect GSC & GA4)", url=auth_url, use_container_width=True, type="primary")
                    except Exception as flow_err:
                        st.error(f"Could not initialize Google OAuth flow: {flow_err}")

    # --------------------------------------------------------------------------
    # DATA SOURCE: MANUAL UPLOAD & DEMO DATASET
    # --------------------------------------------------------------------------
    else:
        col_up1, col_up2 = st.columns([3.5, 1.5])
        with col_up1:
            uploaded_files = st.file_uploader(
                "Upload Google Search Console Export (ZIP / CSV) & Optional GA4 Export:",
                type=["zip", "csv"],
                accept_multiple_files=True
            )
        with col_up2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🧪 Load Industrial Demo Dataset", use_container_width=True, help="Load complete simulated industrial GSC + GA4 dataset to test all 6 modules immediately"):
                demo_queries = pd.DataFrame([
                    # Striking Distance (Pos 8-20, high impressions)
                    {"query": "cpvc butterfly valve price list", "page": "https://yukonvalve.com/product/cpvc-butterfly-valve/", "clicks": 115, "impressions": 12500, "ctr": 0.0092, "position": 9.4},
                    {"query": "motorized ball valve 2 inch", "page": "https://yukonvalve.com/product/electrical-actuator-operated-valve/", "clicks": 88, "impressions": 9800, "ctr": 0.0090, "position": 11.2},
                    {"query": "flanged ball valve dimensions chart", "page": "https://yukonvalve.com/product-category/ball-valve/", "clicks": 74, "impressions": 8400, "ctr": 0.0088, "position": 13.5},
                    {"query": "pvc non return valve suppliers", "page": "https://yukonvalve.com/product-category/non-return-valve/", "clicks": 62, "impressions": 7600, "ctr": 0.0081, "position": 14.8},
                    {"query": "high pressure solenoid valve india", "page": "https://yukonvalve.com/product-category/solenoid-valve/", "clicks": 54, "impressions": 6900, "ctr": 0.0078, "position": 12.1},
                    {"query": "pneumatic actuated ball valve price", "page": "https://yukonvalve.com/product/pneumatic-actuator-butterfly-valve/", "clicks": 48, "impressions": 5800, "ctr": 0.0082, "position": 16.4},

                    # CTR Opportunities (Pos <= 5, CTR < Expected Benchmark)
                    {"query": "industrial valves manufacturer", "page": "https://yukonvalve.com/", "clicks": 48, "impressions": 7800, "ctr": 0.0062, "position": 3.2},
                    {"query": "upvc valve supplier in india", "page": "https://yukonvalve.com/", "clicks": 32, "impressions": 5400, "ctr": 0.0059, "position": 2.8},
                    {"query": "pneumatic actuator butterfly valve", "page": "https://yukonvalve.com/product/pneumatic-actuator-butterfly-valve/", "clicks": 25, "impressions": 4200, "ctr": 0.0060, "position": 4.1},
                    {"query": "industrial plastic ball valves catalog", "page": "https://yukonvalve.com/shop/", "clicks": 18, "impressions": 3900, "ctr": 0.0046, "position": 4.8},

                    # Cannibalization (Multiple URLs splitting exact query)
                    {"query": "upvc butterfly valve manufacturer", "page": "https://yukonvalve.com/product/upvc-butterfly-valve/", "clicks": 90, "impressions": 4600, "ctr": 0.0195, "position": 5.8},
                    {"query": "upvc butterfly valve manufacturer", "page": "https://yukonvalve.com/product-category/butterfly-valve/", "clicks": 45, "impressions": 3800, "ctr": 0.0118, "position": 7.4},
                    {"query": "upvc butterfly valve manufacturer", "page": "https://yukonvalve.com/shop/", "clicks": 12, "impressions": 2100, "ctr": 0.0057, "position": 12.2},

                    # Questions
                    {"query": "how does a pneumatic actuator valve work", "page": "https://yukonvalve.com/product/pneumatic-actuator-butterfly-valve/", "clicks": 85, "impressions": 6400, "ctr": 0.0132, "position": 6.8},
                    {"query": "what is the difference between upvc and cpvc valve", "page": "https://yukonvalve.com/product/cpvc-butterfly-valve/", "clicks": 140, "impressions": 8900, "ctr": 0.0157, "position": 4.2},
                    {"query": "which valve is best for chemical slurry", "page": "https://yukonvalve.com/product-category/ball-valve/", "clicks": 38, "impressions": 4100, "ctr": 0.0092, "position": 9.5},

                    # High Performers
                    {"query": "yukon industrial valves catalogue", "page": "https://yukonvalve.com/shop/", "clicks": 320, "impressions": 850, "ctr": 0.376, "position": 1.2},
                    {"query": "yukon valves india", "page": "https://yukonvalve.com/", "clicks": 480, "impressions": 1100, "ctr": 0.436, "position": 1.1}
                ])

                demo_pages = pd.DataFrame([
                    {"page": "https://yukonvalve.com/product-category/ball-valve/", "prev_clicks": 1450, "prev_imp": 38000},
                    {"page": "https://yukonvalve.com/product/pneumatic-actuator-butterfly-valve/", "prev_clicks": 890, "prev_imp": 24000},
                    {"page": "https://yukonvalve.com/product-category/gate-valve/", "prev_clicks": 620, "prev_imp": 16500},
                    {"page": "https://yukonvalve.com/shop/", "prev_clicks": 2100, "prev_imp": 54000},
                    {"page": "https://yukonvalve.com/", "prev_clicks": 3400, "prev_imp": 78000},
                    {"page": "https://yukonvalve.com/product/cpvc-butterfly-valve/", "prev_clicks": 710, "prev_imp": 19000},
                    {"page": "https://yukonvalve.com/old-discontinued-valve-1999/", "prev_clicks": 0, "prev_imp": 12}
                ])

                demo_ga4 = pd.DataFrame([
                    {"norm_path": "/", "sessions": 4850, "engaged_sessions": 3420, "engagement_rate": 0.705, "avg_engagement_time_sec": 84.0, "conversions": 142, "conversion_rate": 0.029, "sessions_delta_pct": 5.4, "conversions_delta_pct": 8.1},
                    {"norm_path": "/shop", "sessions": 2650, "engaged_sessions": 880, "engagement_rate": 0.332, "avg_engagement_time_sec": 24.0, "conversions": 0, "conversion_rate": 0.000, "sessions_delta_pct": -8.5, "conversions_delta_pct": 0.0},
                    {"norm_path": "/product/cpvc-butterfly-valve", "sessions": 1240, "engaged_sessions": 980, "engagement_rate": 0.790, "avg_engagement_time_sec": 110.0, "conversions": 48, "conversion_rate": 0.038, "sessions_delta_pct": 22.0, "conversions_delta_pct": 31.0},
                    {"norm_path": "/product-category/ball-valve", "sessions": 1100, "engaged_sessions": 720, "engagement_rate": 0.654, "avg_engagement_time_sec": 65.0, "conversions": 28, "conversion_rate": 0.025, "sessions_delta_pct": -34.2, "conversions_delta_pct": -28.0},
                    {"norm_path": "/product/pneumatic-actuator-butterfly-valve", "sessions": 740, "engaged_sessions": 510, "engagement_rate": 0.689, "avg_engagement_time_sec": 78.0, "conversions": 22, "conversion_rate": 0.029, "sessions_delta_pct": -38.5, "conversions_delta_pct": -30.0},
                    {"norm_path": "/product-category/gate-valve", "sessions": 510, "engaged_sessions": 340, "engagement_rate": 0.666, "avg_engagement_time_sec": 60.0, "conversions": 12, "conversion_rate": 0.023, "sessions_delta_pct": -32.0, "conversions_delta_pct": -25.0},
                    {"norm_path": "/product/electrical-actuator-operated-valve", "sessions": 380, "engaged_sessions": 310, "engagement_rate": 0.815, "avg_engagement_time_sec": 135.0, "conversions": 19, "conversion_rate": 0.050, "sessions_delta_pct": 14.5, "conversions_delta_pct": 26.0},
                    {"norm_path": "/old-discontinued-valve-1999", "sessions": 2, "engaged_sessions": 0, "engagement_rate": 0.000, "avg_engagement_time_sec": 3.0, "conversions": 0, "conversion_rate": 0.000, "sessions_delta_pct": 0.0, "conversions_delta_pct": 0.0}
                ])

                st.session_state["master_dataset"] = {
                    "queries": demo_queries,
                    "pages": demo_pages,
                    "ga4": demo_ga4,
                    "property_gsc": "https://yukonvalve.com",
                    "property_ga4": "Yukon Valve Global GA4",
                    "date_range": "Last 28 Days (Demo Mode)",
                    "is_mock": True
                }
                st.rerun()

        if uploaded_files:
            parsed = parse_gsc_and_ga4_upload(uploaded_files)
            if not parsed["queries"].empty:
                st.session_state["master_dataset"] = {
                    "queries": parsed["queries"],
                    "pages": parsed["pages"],
                    "ga4": pd.DataFrame(),
                    "property_gsc": "Uploaded Files",
                    "property_ga4": "None",
                    "date_range": "Uploaded Period",
                    "is_mock": False
                }
                st.success("✅ Files processed successfully!")
                st.rerun()

    # --------------------------------------------------------------------------
    # CHECK DATASET STATE
    # --------------------------------------------------------------------------
    master_data = st.session_state.get("master_dataset")
    if not master_data or master_data.get("queries") is None or master_data["queries"].empty:
        st.markdown("""
        <div style="background: rgba(11, 20, 38, 0.6); border: 1px dashed rgba(0, 240, 255, 0.25); border-radius: 16px; padding: 2.8rem 2rem; text-align: center; margin-top: 1.5rem;">
            <div style="font-size: 3rem; margin-bottom: 0.8rem;">⚡</div>
            <h3 style="color: #FFFFFF; font-weight: 800; margin-bottom: 0.5rem; font-family: 'Space Grotesk', sans-serif;">Awaiting GSC & GA4 Data</h3>
            <p style="color: #94A3B8; font-size: 0.98rem; max-width: 620px; margin: 0 auto 1.5rem; line-height: 1.6; font-family: 'Space Grotesk', sans-serif;">
                Click <b>'Sign In With Google'</b> above for instant automatic fetching, or click <b>'Load Industrial Demo Dataset'</b> to inspect all 6 modules immediately.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # --------------------------------------------------------------------------
    # EXECUTE DATA MERGER & MODULES
    # --------------------------------------------------------------------------
    with st.spinner("Executing URL normalization and merging GSC + GA4 performance data..."):
        unified_urls, enriched_queries = build_unified_url_master(
            queries_df=master_data["queries"],
            pages_df=master_data.get("pages", pd.DataFrame()),
            ga4_df=master_data.get("ga4", pd.DataFrame()),
            base_domain=master_data.get("property_gsc", "")
        )

        opportunities = compute_seo_opportunities(
            unified_urls=unified_urls,
            enriched_queries=enriched_queries
        )

        audit_buckets = classify_content_audit_buckets(unified_urls)
        cannibal_df = detect_keyword_cannibalization(master_data["queries"], unified_urls)
        questions_df, cluster_df = generate_topic_cluster_and_questions(enriched_queries)
        forecast_df = simulate_traffic_and_revenue_uplift(opportunities["striking"])

    # --------------------------------------------------------------------------
    # TOP KPI HUD METRICS
    # --------------------------------------------------------------------------
    tot_clicks = int(unified_urls["total_clicks"].sum())
    tot_imp = int(unified_urls["total_impressions"].sum())
    tot_sessions = int(unified_urls["sessions"].sum())
    tot_conv = int(unified_urls["conversions"].sum())
    decay_count = len(audit_buckets["decay"])
    striking_count = len(opportunities["striking"])

    st.markdown(f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 1.6rem;">
        <!-- 1. GSC Clicks -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">🔍</div>
                <span class="kpi-badge kpi-badge-cyan">Pre-Click</span>
            </div>
            <div class="kpi-label">TOTAL GSC CLICKS</div>
            <div class="kpi-value" style="color: #00F0FF; text-shadow: 0 0 20px rgba(0, 240, 255, 0.45);">{tot_clicks:,}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 70%; background: #00F0FF; box-shadow: 0 0 10px #00F0FF;"></div></div>
        </div>

        <!-- 2. GA4 Sessions -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">📊</div>
                <span class="kpi-badge kpi-badge-teal">Post-Click</span>
            </div>
            <div class="kpi-label">GA4 SESSIONS</div>
            <div class="kpi-value" style="color: #2DD4BF; text-shadow: 0 0 20px rgba(45, 212, 191, 0.45);">{tot_sessions:,}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 65%; background: #2DD4BF; box-shadow: 0 0 10px #2DD4BF;"></div></div>
        </div>

        <!-- 3. Conversions -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">🎯</div>
                <span class="kpi-badge kpi-badge-green">Outcomes</span>
            </div>
            <div class="kpi-label">GA4 KEY EVENTS</div>
            <div class="kpi-value" style="color: #34D399; text-shadow: 0 0 20px rgba(52, 211, 153, 0.45);">{tot_conv:,}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 55%; background: #34D399; box-shadow: 0 0 10px #34D399;"></div></div>
        </div>

        <!-- 4. Striking Distance -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">⚡</div>
                <span class="kpi-badge kpi-badge-amber">Quick Wins</span>
            </div>
            <div class="kpi-label">STRIKING KEYWORDS</div>
            <div class="kpi-value" style="color: #FBBF24; text-shadow: 0 0 20px rgba(251, 191, 36, 0.45);">{striking_count:,}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 50%; background: #FBBF24; box-shadow: 0 0 10px #FBBF24;"></div></div>
        </div>

        <!-- 5. Content Decay -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">📉</div>
                <span class="kpi-badge kpi-badge-red">>20% Loss</span>
            </div>
            <div class="kpi-label">DECAYING PAGES</div>
            <div class="kpi-value" style="color: #FF6B4A; text-shadow: 0 0 20px rgba(255, 107, 74, 0.45);">{decay_count:,}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 45%; background: #FF6B4A; box-shadow: 0 0 10px #FF6B4A;"></div></div>
        </div>

        <!-- 6. Cannibalization -->
        <div class="kpi-card-hud">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 1.25rem;">⚔️</div>
                <span class="kpi-badge kpi-badge-red">SERP Conflict</span>
            </div>
            <div class="kpi-label">CANNIBALIZED QUERIES</div>
            <div class="kpi-value" style="color: #F87171; text-shadow: 0 0 20px rgba(248, 113, 113, 0.45);">{len(cannibal_df):,}</div>
            <div class="kpi-line-bg"><div class="kpi-line-fill" style="width: 40%; background: #F87171; box-shadow: 0 0 10px #F87171;"></div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # 6 SPECIALIZED PLANNING TABS (FLOATING RIBBON)
    # --------------------------------------------------------------------------
    tab_opps, tab_buckets, tab_cannibal, tab_clusters, tab_forecaster, tab_board = st.tabs([
        "🎯 SEO Opportunities (4 Smart Tabs)",
        "📦 Content Audit & Action Buckets",
        "⚔️ Keyword Cannibalization Detector",
        "❓ Topic Cluster & Question Planner",
        "📈 Traffic & Revenue Forecaster",
        "📋 SEO Task Board & Impact Tracker"
    ])

    # ==========================================================================
    # TAB 1: COMBINED SEO OPPORTUNITY FINDER (4 SMART TABS)
    # ==========================================================================
    with tab_opps:
        st.markdown("### 🎯 Combined SEO Opportunities (Pre-Click + Post-Click Intent)")
        st.caption("Cross-examines GSC rankings & impressions against GA4 user engagement and conversion rates.")

        # Interactive threshold controls
        with st.expander("⚙️ Dynamic Opportunity Thresholds & Filters", expanded=False):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                thresh_imp = st.slider("Min Impressions Threshold", min_value=10, max_value=2000, value=50, step=10)
            with fc2:
                striking_p1 = st.slider("Striking Distance Min Rank", min_value=5.0, max_value=15.0, value=8.0, step=0.5)
            with fc3:
                striking_p2 = st.slider("Striking Distance Max Rank", min_value=12.0, max_value=30.0, value=20.0, step=0.5)

            # Recompute with user-selected thresholds
            opportunities = compute_seo_opportunities(
                unified_urls, enriched_queries, min_striking_imp=thresh_imp,
                striking_min_pos=striking_p1, striking_max_pos=striking_p2
            )

        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
            "⚡ Striking Distance (Quick Wins)",
            "🍎 CTR Opportunity Finder (Title/Meta)",
            "⚠️ Traffic vs. Intent Mismatch (UX/Content)",
            "💎 Hidden Conversion Gems (Scale)"
        ])

        # 1. Striking Distance
        with sub_tab1:
            st.markdown(f"#### ⚡ Striking Distance Keywords (Positions {striking_p1} to {striking_p2})")
            st.info("💡 **Strategy**: These queries have high impressions and rank just off Page 1. Add them into **H2 headings, FAQ schemas, and internal link anchor text** to surge into the Top 3.")
            st_df = opportunities["striking"]
            if not st_df.empty:
                st.dataframe(
                    st_df[["query", "page", "position", "impressions", "clicks", "ctr", "page_engagement_rate", "recommendation"]],
                    column_config={
                        "page": st.column_config.LinkColumn("Target URL"),
                        "position": st.column_config.NumberColumn("Rank", format="%.1f"),
                        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                        "page_engagement_rate": st.column_config.NumberColumn("GA4 Eng. Rate", format="%.1f%%"),
                        "recommendation": st.column_config.TextColumn("Action Badge")
                    },
                    use_container_width=True
                )
                c_sel, c_act = st.columns([3, 1])
                with c_sel:
                    selected_st_query = st.selectbox("Select Striking Keyword to Add to SEO Plan:", options=st_df["query"].head(50))
                with c_act:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("➕ Add to Task Board", key="btn_add_st"):
                        row = st_df[st_df["query"] == selected_st_query].iloc[0]
                        add_insight_to_task_board(
                            f"Optimize Striking Keyword: '{selected_st_query}'",
                            row["page"],
                            "High",
                            f"Ranking #{row['position']} with {row['impressions']:,} impressions. Inject into H2 & internal anchors."
                        )
            else:
                st.info("No striking distance keywords matching the threshold criteria.")

        # 2. CTR Leak
        with sub_tab2:
            st.markdown("#### 🍎 CTR Opportunity Finder (Title & Meta Optimizer)")
            st.info("💡 **Strategy**: These pages/queries rank in the **Top 5**, but their CTR is significantly below Google SERP benchmarks. Rewriting the Meta Title & Description with psychological triggers and numbers will immediately drive more clicks.")
            ctr_df = opportunities["ctr_leak"]
            if not ctr_df.empty:
                st.dataframe(
                    ctr_df[["query", "page", "position", "impressions", "clicks", "ctr", "benchmark_ctr", "ctr_gap_pct", "recommendation"]],
                    column_config={
                        "page": st.column_config.LinkColumn("Target URL"),
                        "position": st.column_config.NumberColumn("Rank", format="%.1f"),
                        "ctr": st.column_config.NumberColumn("Actual CTR", format="%.2f%%"),
                        "benchmark_ctr": st.column_config.NumberColumn("Expected CTR", format="%.1f%%"),
                        "ctr_gap_pct": st.column_config.NumberColumn("CTR Deficit", format="%.1f%%"),
                        "recommendation": st.column_config.TextColumn("Action Badge")
                    },
                    use_container_width=True
                )
            else:
                st.info("✅ No severe CTR anomalies detected in the Top 5 positions.")

        # 3. Intent Mismatch
        with sub_tab3:
            st.markdown("#### ⚠️ Traffic vs. Intent Mismatch (High Clicks, Low Engagement / 0 Conversions)")
            st.info("💡 **Strategy**: These URLs attract substantial organic clicks (top 30% of your site) but have **under 40% engagement rate or zero conversions**. Visitors bounce because the page fails to deliver on the SERP promise.")
            int_df = opportunities["intent_mismatch"]
            if not int_df.empty:
                st.dataframe(
                    int_df[["full_canonical_url", "total_clicks", "total_impressions", "sessions", "engagement_rate", "conversions", "recommendation"]],
                    column_config={
                        "full_canonical_url": st.column_config.LinkColumn("Landing Page URL"),
                        "engagement_rate": st.column_config.NumberColumn("GA4 Eng. Rate", format="%.1f%%"),
                        "conversions": st.column_config.NumberColumn("Conversions"),
                        "recommendation": st.column_config.TextColumn("Action Badge")
                    },
                    use_container_width=True
                )
            else:
                st.info("✅ Great job! No major intent mismatches detected.")

        # 4. Hidden Gems
        with sub_tab4:
            st.markdown("#### 💎 Hidden Conversion Gems (High Conversion Rate, Low Organic Visibility)")
            st.info("💡 **Strategy**: These URLs achieve **stellar conversion rates (> 2%) or high engagement (> 70%)**, but rank on Page 2 or 3 (positions 11-30). Boosting organic visibility here produces direct revenue gains.")
            gem_df = opportunities["gems"]
            if not gem_df.empty:
                st.dataframe(
                    gem_df[["full_canonical_url", "avg_position", "total_clicks", "sessions", "engagement_rate", "conversion_rate", "conversions", "recommendation"]],
                    column_config={
                        "full_canonical_url": st.column_config.LinkColumn("Landing Page URL"),
                        "avg_position": st.column_config.NumberColumn("Rank", format="%.1f"),
                        "engagement_rate": st.column_config.NumberColumn("GA4 Eng. Rate", format="%.1f%%"),
                        "conversion_rate": st.column_config.NumberColumn("Conv. Rate", format="%.2f%%"),
                        "recommendation": st.column_config.TextColumn("Action Badge")
                    },
                    use_container_width=True
                )
            else:
                st.info("No hidden conversion gems detected currently.")

    # ==========================================================================
    # TAB 2: AUTOMATED CONTENT AUDIT & ACTION BUCKETS
    # ==========================================================================
    with tab_buckets:
        st.markdown("### 📦 Strategic Content Audit & Action Buckets")
        st.caption("Classifies every page into 1 of 4 actionable SEO buckets based on Period-over-Period search trends and GA4 behavior.")

        b_c1, b_c2, b_c3, b_c4 = st.columns(4)
        with b_c1:
            st.metric("🏆 Keep & Scale (Winners)", f"{len(audit_buckets['winners'])} pages")
        with b_c2:
            st.metric("🔄 Update & Refresh (Decay)", f"{len(audit_buckets['decay'])} pages")
        with b_c3:
            st.metric("🔀 Consolidate (Merge)", f"{len(audit_buckets['consolidate'])} pages")
        with b_c4:
            st.metric("🗑️ Prune / Review (Dead Weight)", f"{len(audit_buckets['prune'])} pages")

        bucket_filter = st.radio(
            "Filter Content Bucket:",
            options=["🔄 Update & Refresh (Content Decay)", "🏆 Keep & Scale (Winners)", "🔀 Consolidate (Merge Candidates)", "🗑️ Prune / Review (Dead Weight)"],
            horizontal=True
        )

        target_bucket_map = {
            "🔄 Update & Refresh (Content Decay)": audit_buckets["decay"],
            "🏆 Keep & Scale (Winners)": audit_buckets["winners"],
            "🔀 Consolidate (Merge Candidates)": audit_buckets["consolidate"],
            "🗑️ Prune / Review (Dead Weight)": audit_buckets["prune"]
        }
        active_b_df = target_bucket_map[bucket_filter]

        if not active_b_df.empty:
            st.dataframe(
                active_b_df[["full_canonical_url", "total_clicks", "prev_clicks", "clicks_delta_pct", "total_impressions", "sessions", "engagement_rate", "action_plan"]],
                column_config={
                    "full_canonical_url": st.column_config.LinkColumn("Canonical Landing Page"),
                    "clicks_delta_pct": st.column_config.NumberColumn("Click Delta %", format="%.1f%%"),
                    "engagement_rate": st.column_config.NumberColumn("GA4 Eng. Rate", format="%.1f%%"),
                    "action_plan": st.column_config.TextColumn("Action Guide")
                },
                use_container_width=True
            )
        else:
            st.info(f"No pages in bucket: {bucket_filter}")

    # ==========================================================================
    # TAB 3: KEYWORD CANNIBALIZATION DETECTOR
    # ==========================================================================
    with tab_cannibal:
        st.markdown("### ⚔️ Keyword Cannibalization Detector")
        st.caption("Identifies queries where 2 or more distinct URLs receive impressions and clicks, splitting link equity and ranking potential.")

        if not cannibal_df.empty:
            st.info(f"🚨 Found **{len(cannibal_df)} queries** suffering from keyword cannibalization. Neither competing URL dominates >85% of traffic.")

            for idx, r in cannibal_df.head(25).iterrows():
                with st.expander(f"⚔️ **{r['query']}** — {r['url_count']} Competing URLs ({r['total_impressions']:,} Imp, {r['total_clicks']} Clicks, Best Rank #{r['best_position']})"):
                    st.markdown("**Competing Landing Pages (Decide Primary vs 301 Redirect / Canonicalize):**")
                    comp_df = pd.DataFrame(r["competing_pages"])
                    st.dataframe(
                        comp_df,
                        column_config={
                            "url": st.column_config.LinkColumn("Competing URL"),
                            "position": st.column_config.NumberColumn("Rank", format="%.1f"),
                            "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                            "engagement_rate": st.column_config.NumberColumn("GA4 Eng. Rate", format="%.1f%%")
                        },
                        use_container_width=True
                    )
                    if st.button(f"➕ Add Cannibalization Fix to Plan ('{r['query']}')", key=f"btn_can_{idx}"):
                        add_insight_to_task_board(
                            f"Resolve Cannibalization: '{r['query']}'",
                            r["competing_pages"][0]["url"],
                            "Critical",
                            f"{r['url_count']} URLs competing. Consolidate into top converting URL or re-differentiate intent."
                        )
        else:
            st.success("✅ Excellent! No severe keyword cannibalization detected across primary clusters.")

    # ==========================================================================
    # TAB 4: TOPIC CLUSTER & QUESTION PLANNER
    # ==========================================================================
    with tab_clusters:
        st.markdown("### ❓ Topic Cluster & Question Planner")
        st.caption("Extracts FAQ and long-tail informational queries, plus identifies new sub-topic cluster candidates.")

        c_t1, c_t2 = st.tabs(["❓ Question Explorer (FAQ & Blog Briefs)", "🚀 New Cluster Opportunities (High Imp, 0 Clicks)"])

        with c_t1:
            st.markdown("#### ❓ Question-Based Search Queries")
            st.caption("Perfect for adding FAQ accordion schema to target pages or producing new authoritative guides.")
            if not questions_df.empty:
                st.dataframe(
                    questions_df[["query", "page", "clicks", "impressions", "ctr", "position", "content_type"]].head(100),
                    column_config={
                        "page": st.column_config.LinkColumn("Target Page URL"),
                        "position": st.column_config.NumberColumn("Rank", format="%.1f"),
                        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%")
                    },
                    use_container_width=True
                )
            else:
                st.info("No question queries matching regex patterns found.")

        with c_t2:
            st.markdown("#### 🚀 New Content Cluster Candidates")
            st.caption("High-impression queries (> 100) where your site currently receives zero clicks or ranks past Position 15 because a dedicated page does not exist.")
            if not cluster_df.empty:
                st.dataframe(
                    cluster_df[["query", "impressions", "position", "opportunity_type"]].head(100),
                    column_config={
                        "position": st.column_config.NumberColumn("Rank", format="%.1f")
                    },
                    use_container_width=True
                )
            else:
                st.info("No high-impression cluster gaps found.")

    # ==========================================================================
    # TAB 5: TRAFFIC FORECASTER & REVENUE SIMULATOR
    # ==========================================================================
    with tab_forecaster:
        st.markdown("### 📈 SEO Traffic & Conversion Simulator")
        st.caption("Simulates extra monthly clicks and leads if Striking Distance keywords (Positions 8–20) advance to Top 3.")

        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            st.info("Model assumes standard organic SERP click-through rates: **Position #1 (25% CTR)**, **Position #2 (15% CTR)**, and **Position #3 (10% CTR)**.")
        with f_col2:
            lead_val = st.number_input("Average Value per Lead / Conversion ($):", value=50.0, step=10.0)

        sim_df = simulate_traffic_and_revenue_uplift(opportunities["striking"], default_lead_value=lead_val)

        if not sim_df.empty:
            tot_gain_clicks = int(sim_df["net_new_clicks_pos_1"].sum())
            tot_gain_conv = round(float(sim_df["projected_new_conversions_pos_1"].sum()), 1)
            tot_val_gain = round(float(sim_df["projected_value_gain_pos_1"].sum()), 2)

            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.metric("Projected New Monthly Clicks (If #1)", f"+{tot_gain_clicks:,} clicks")
            with sc2:
                st.metric("Projected New Monthly Conversions", f"+{tot_gain_conv:,} leads")
            with sc3:
                st.metric("Estimated Monthly Value Addition", f"+${tot_val_gain:,.2f}")

            st.dataframe(
                sim_df[["query", "page", "position", "impressions", "clicks", "proj_clicks_pos_1", "net_new_clicks_pos_1", "projected_new_conversions_pos_1", "projected_value_gain_pos_1"]].head(100),
                column_config={
                    "page": st.column_config.LinkColumn("Landing Page URL"),
                    "position": st.column_config.NumberColumn("Current Rank", format="%.1f"),
                    "proj_clicks_pos_1": st.column_config.NumberColumn("Projected #1 Clicks"),
                    "net_new_clicks_pos_1": st.column_config.NumberColumn("Net Clicks Gain", format="+%d"),
                    "projected_new_conversions_pos_1": st.column_config.NumberColumn("Net Leads Gain", format="+%.1f"),
                    "projected_value_gain_pos_1": st.column_config.NumberColumn("Projected Value ($)", format="$%.2f")
                },
                use_container_width=True
            )
        else:
            st.info("No candidates for traffic projection modeling.")

    # ==========================================================================
    # TAB 6: SEO TASK BOARD & IMPACT ANNOTATION TRACKER
    # ==========================================================================
    with tab_board:
        st.markdown("### 📋 SEO Action Task Board & Impact Annotation Tracker")
        st.caption("Track implementation of recommended fixes and measure pre- vs post-implementation performance.")

        tasks = st.session_state.get("seo_task_board", [])

        # Quick Add Custom Task
        with st.expander("➕ Add Custom SEO Task", expanded=False):
            ta1, ta2, ta3 = st.columns([2.5, 2, 1])
            with ta1:
                new_t_title = st.text_input("Task Title", placeholder="e.g., Update Title & H2 on /shop/valves")
            with ta2:
                new_t_url = st.text_input("Target URL", value=master_data.get("property_gsc", ""))
            with ta3:
                new_t_prio = st.selectbox("Priority", options=["Critical", "High", "Medium", "Low"])
            if st.button("Save Task to Board"):
                if new_t_title:
                    add_insight_to_task_board(new_t_title, new_t_url, new_t_prio, "Custom implementation item")
                    st.rerun()

        if tasks:
            for idx, task in enumerate(tasks):
                t_col1, t_col2, t_col3, t_col4 = st.columns([3, 1.2, 1.5, 1])
                with t_col1:
                    st.markdown(f"**{task['title']}**")
                    st.caption(f"URL: `{task['url']}` • {task['impact_reason']}")
                with t_col2:
                    st.markdown(f"Priority: `{task['priority']}`")
                    st.caption(f"Created: {task['created_at']}")
                with t_col3:
                    current_status = task["status"]
                    status_opts = ["To Do", "In Progress", "Implemented"]
                    new_status = st.selectbox(
                        "Status",
                        options=status_opts,
                        index=status_opts.index(current_status),
                        key=f"task_status_{idx}"
                    )
                    if new_status != current_status:
                        task["status"] = new_status
                        if new_status == "Implemented" and not task["implemented_at"]:
                            task["implemented_at"] = datetime.now().strftime("%Y-%m-%d")
                            st.toast(f"Marked '{task['title']}' as Implemented! Tracking impact benchmark.", icon="🎉")
                        st.rerun()
                with t_col4:
                    if task["implemented_at"]:
                        st.success(f"Deployed: {task['implemented_at']}")
                    if st.button("🗑️ Delete", key=f"del_task_{idx}"):
                        tasks.pop(idx)
                        st.session_state["seo_task_board"] = tasks
                        st.rerun()
                st.markdown("---")
        else:
            st.info("ℹ️ Your task board is empty. Click **'➕ Add to Task Board'** in the Opportunities or Cannibalization tabs above to start planning your action items!")
