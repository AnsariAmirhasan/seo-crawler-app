"""
GA4 + GSC SEO Intelligence & Future Suggestion Engine
======================================================
Deep integration bridging pre-click search visibility (Google Search Console API)
with post-click behavioral engagement and conversions (Google Analytics 4 Data API v1beta).

Key Capabilities:
1. GA4 Data API (v1beta) fetcher for 4 clean datasets:
   - Organic Landing Pages (sessionDefaultChannelGroup == 'Organic Search')
   - Device UX Comparison per landing page (Mobile vs. Desktop bounce gap detection)
   - AI Search & Referral Traffic Tracker (ChatGPT, Perplexity, Gemini, Claude, Copilot)
   - Canonical URL Normalization and GSC + GA4 merger
2. Metric Translation & Rule-Based Future Suggestion Engine:
   - userExperienceBadge (🟢 High Reader Engagement / 🟡 Average / 🔴 High Bounce / ⚪ Connect GA4)
   - plainLanguageDiagnosis (1-sentence 'Kya Ho Raha Hai')
   - futureSuggestion ('Future Plan / Kya Karein' covering Cases A through F)
3. Specialized Renderers for the 6 New Combined Tabs matching CrawlPilot Cyber Cockpit design.
"""

import io
import re
import os
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Google OAuth & Analytics Data API v1beta Safe Imports
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        RunReportRequest,
        FilterExpression,
        Filter
    )
    GA4_LIBS_AVAILABLE = True
except ImportError:
    build = None
    Credentials = None
    BetaAnalyticsDataClient = None
    DateRange = None
    Dimension = None
    Metric = None
    RunReportRequest = None
    FilterExpression = None
    Filter = None
    GA4_LIBS_AVAILABLE = False


# ==============================================================================
# 1. URL NORMALIZATION & FORMATTING HELPERS
# ==============================================================================

def normalize_canonical_path(url_or_path: str) -> str:
    """
    Normalizes GSC full URLs ('https://example.com/blog/post/') and GA4 paths ('/blog/post')
    into a clean canonical path ('/blog/post').
    Strips protocol, www, domain, trailing slash, and tracking query params (utm_*, gclid, etc.).
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

    # Strip marketing parameters while retaining canonical structure
    if raw_query:
        params = urllib.parse.parse_qs(raw_query)
        tracking_keys = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'gclid', 'fbclid', 'msclkid', 'dclid', 'zanpid', 'ref', 'source'
        }
        clean_params = {k: v for k, v in params.items() if k.lower() not in tracking_keys}
        if clean_params:
            path += "?" + urllib.parse.urlencode(clean_params, doseq=True)

    return path.lower()


def format_read_time(seconds: float) -> str:
    """Formats average engagement time in seconds into readable 'Xm Ys' or '0m 25s'."""
    if not seconds or pd.isna(seconds) or seconds <= 0:
        return "0m 00s"
    total_sec = int(round(seconds))
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins}m {secs:02d}s"


# ==============================================================================
# 2. GA4 DATA API (v1beta) BACKEND SERVICE (4 CLEAN DATASETS)
# ==============================================================================

def fetch_live_ga4_datasets(
    creds,
    ga4_property_id: str,
    curr_start: str,
    curr_end: str,
    prev_start: str,
    prev_end: str
) -> Dict[str, Any]:
    """
    Fetches the 4 SEO-relevant GA4 datasets via Data API v1beta:
    1. Organic Landing Page Performance (sessions, users, engagement, bounce, read time, conversions)
    2. Device UX Comparison per landing page (Mobile vs Desktop)
    3. AI Search & Referral Traffic Tracker (ChatGPT, Perplexity, Gemini, Claude, Copilot)
    4. Canonical Normalized Path lookup map
    """
    empty_result = {
        "organic_landing": pd.DataFrame(),
        "device_ux": pd.DataFrame(),
        "device_flags": pd.DataFrame(),
        "ai_search": pd.DataFrame(),
        "lookup": {},
        "has_ga4": False
    }

    if not ga4_property_id or ga4_property_id == "None" or not GA4_LIBS_AVAILABLE or BetaAnalyticsDataClient is None:
        return empty_result

    try:
        data_client = BetaAnalyticsDataClient(credentials=creds)
        prop_str = ga4_property_id if ga4_property_id.startswith("properties/") else f"properties/{ga4_property_id}"

        # ----------------------------------------------------------------------
        # DATASET 1: Organic Landing Page Performance
        # ----------------------------------------------------------------------
        # Filter for Organic Search
        organic_filter = FilterExpression(
            filter=Filter(
                field_name="sessionDefaultChannelGroup",
                string_filter=Filter.StringFilter(
                    value="Organic Search",
                    match_type=Filter.StringFilter.MatchType.EXACT
                )
            )
        )

        # 1a. Current Period Organic Landing Pages
        try:
            req_curr_org = RunReportRequest(
                property=prop_str,
                dimensions=[Dimension(name="landingPagePlusQueryString")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="totalUsers"),
                    Metric(name="engagedSessions"),
                    Metric(name="engagementRate"),
                    Metric(name="bounceRate"),
                    Metric(name="userEngagementDuration"),
                    Metric(name="conversions"),
                    Metric(name="eventCount")
                ],
                dimension_filter=organic_filter,
                date_ranges=[DateRange(start_date=curr_start, end_date=curr_end)],
                limit=15000
            )
            rep_curr_org = data_client.run_report(req_curr_org)
        except Exception as e_org:
            # Fallback without channel group filter if property has custom channel groupings
            print(f"Fallback without channel group filter: {e_org}")
            req_curr_org = RunReportRequest(
                property=prop_str,
                dimensions=[Dimension(name="landingPagePlusQueryString")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="totalUsers"),
                    Metric(name="engagedSessions"),
                    Metric(name="userEngagementDuration"),
                    Metric(name="conversions"),
                    Metric(name="eventCount")
                ],
                date_ranges=[DateRange(start_date=curr_start, end_date=curr_end)],
                limit=15000
            )
            rep_curr_org = data_client.run_report(req_curr_org)

        # 1b. Previous Period Organic Landing Pages (For 30-Day Trend Radar)
        prev_map = {}
        try:
            req_prev_org = RunReportRequest(
                property=prop_str,
                dimensions=[Dimension(name="landingPagePlusQueryString")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="conversions"),
                    Metric(name="userEngagementDuration")
                ],
                dimension_filter=organic_filter,
                date_ranges=[DateRange(start_date=prev_start, end_date=prev_end)],
                limit=15000
            )
            rep_prev_org = data_client.run_report(req_prev_org)
            for row in rep_prev_org.rows:
                raw_u = row.dimension_values[0].value
                norm_p = normalize_canonical_path(raw_u)
                p_sess = int(row.metric_values[0].value) if len(row.metric_values) > 0 else 0
                p_conv = int(row.metric_values[1].value) if len(row.metric_values) > 1 else 0
                prev_map[norm_p] = {"prev_sessions": p_sess, "prev_conversions": p_conv}
        except Exception as e_prev:
            print(f"GA4 Previous period query warning: {e_prev}")

        # Parse Dataset 1 rows
        org_rows = []
        for row in rep_curr_org.rows:
            raw_url = row.dimension_values[0].value
            norm_p = normalize_canonical_path(raw_url)
            m_vals = [m.value for m in row.metric_values]

            sess = int(float(m_vals[0])) if len(m_vals) > 0 else 0
            users = int(float(m_vals[1])) if len(m_vals) > 1 else 0
            eng_sess = int(float(m_vals[2])) if len(m_vals) > 2 else 0

            # If engagementRate and bounceRate were returned directly
            if len(m_vals) >= 8:
                eng_rate = float(m_vals[3])
                bounce_rate = float(m_vals[4])
                duration = float(m_vals[5])
                conv = int(float(m_vals[6]))
                events = int(float(m_vals[7]))
            else:
                eng_rate = (eng_sess / sess) if sess > 0 else 0.0
                bounce_rate = max(0.0, 1.0 - eng_rate)
                duration = float(m_vals[3]) if len(m_vals) > 3 else 0.0
                conv = int(float(m_vals[4])) if len(m_vals) > 4 else 0
                events = int(float(m_vals[5])) if len(m_vals) > 5 else 0

            p_info = prev_map.get(norm_p, {"prev_sessions": 0, "prev_conversions": 0})
            prev_sess = p_info["prev_sessions"]
            prev_conv = p_info["prev_conversions"]

            avg_time = (duration / sess) if sess > 0 else 0.0
            conv_rate = (conv / sess) if sess > 0 else 0.0
            sess_delta = round(((sess - prev_sess) / prev_sess * 100), 1) if prev_sess > 0 else 0.0
            conv_delta = round(((conv - prev_conv) / prev_conv * 100), 1) if prev_conv > 0 else 0.0

            org_rows.append({
                "norm_path": norm_p,
                "raw_landing_page": raw_url,
                "sessions": sess,
                "totalUsers": users,
                "engagedSessions": eng_sess,
                "engagementRate": eng_rate,
                "bounceRate": bounce_rate,
                "avg_engagement_time_sec": avg_time,
                "read_time_formatted": format_read_time(avg_time),
                "conversions": conv,
                "conversion_rate": conv_rate,
                "eventCount": events,
                "prev_sessions": prev_sess,
                "prev_conversions": prev_conv,
                "sessions_delta_pct": sess_delta,
                "conversions_delta_pct": conv_delta
            })

        organic_landing_df = pd.DataFrame(org_rows)
        if not organic_landing_df.empty:
            # Aggregate onto unique canonical paths
            agg_rules = {
                "sessions": "sum",
                "totalUsers": "sum",
                "engagedSessions": "sum",
                "conversions": "sum",
                "eventCount": "sum",
                "prev_sessions": "sum",
                "prev_conversions": "sum",
                "avg_engagement_time_sec": "mean"
            }
            organic_landing_df = organic_landing_df.groupby("norm_path", as_index=False).agg(agg_rules)
            organic_landing_df["engagementRate"] = np.where(
                organic_landing_df["sessions"] > 0,
                organic_landing_df["engagedSessions"] / organic_landing_df["sessions"],
                0.0
            )
            organic_landing_df["bounceRate"] = np.maximum(0.0, 1.0 - organic_landing_df["engagementRate"])
            organic_landing_df["conversion_rate"] = np.where(
                organic_landing_df["sessions"] > 0,
                organic_landing_df["conversions"] / organic_landing_df["sessions"],
                0.0
            )
            organic_landing_df["read_time_formatted"] = organic_landing_df["avg_engagement_time_sec"].apply(format_read_time)
            organic_landing_df["sessions_delta_pct"] = np.where(
                organic_landing_df["prev_sessions"] > 0,
                (organic_landing_df["sessions"] - organic_landing_df["prev_sessions"]) / organic_landing_df["prev_sessions"] * 100,
                0.0
            )
            organic_landing_df["conversions_delta_pct"] = np.where(
                organic_landing_df["prev_conversions"] > 0,
                (organic_landing_df["conversions"] - organic_landing_df["prev_conversions"]) / organic_landing_df["prev_conversions"] * 100,
                0.0
            )

        # ----------------------------------------------------------------------
        # DATASET 2: GA4 Device UX Comparison per Landing Page
        # ----------------------------------------------------------------------
        device_rows = []
        try:
            req_device = RunReportRequest(
                property=prop_str,
                dimensions=[
                    Dimension(name="pagePath"),
                    Dimension(name="deviceCategory")
                ],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="engagedSessions"),
                    Metric(name="userEngagementDuration"),
                    Metric(name="conversions")
                ],
                date_ranges=[DateRange(start_date=curr_start, end_date=curr_end)],
                limit=15000
            )
            rep_device = data_client.run_report(req_device)
            for row in rep_device.rows:
                p_path = row.dimension_values[0].value
                d_cat = row.dimension_values[1].value.lower()
                norm_p = normalize_canonical_path(p_path)

                d_sess = int(float(row.metric_values[0].value)) if len(row.metric_values) > 0 else 0
                d_eng = int(float(row.metric_values[1].value)) if len(row.metric_values) > 1 else 0
                d_dur = float(row.metric_values[2].value) if len(row.metric_values) > 2 else 0.0
                d_conv = int(float(row.metric_values[3].value)) if len(row.metric_values) > 3 else 0

                d_eng_rate = (d_eng / d_sess) if d_sess > 0 else 0.0
                d_read_time = (d_dur / d_sess) if d_sess > 0 else 0.0

                device_rows.append({
                    "norm_path": norm_p,
                    "deviceCategory": d_cat,
                    "sessions": d_sess,
                    "engagedSessions": d_eng,
                    "engagementRate": d_eng_rate,
                    "avg_read_time_sec": d_read_time,
                    "conversions": d_conv
                })
        except Exception as e_dev:
            print(f"GA4 Device query warning: {e_dev}")

        device_ux_df = pd.DataFrame(device_rows)

        # Pivot to compare Mobile vs. Desktop
        device_flags_df = pd.DataFrame()
        if not device_ux_df.empty:
            piv_sess = device_ux_df.pivot_table(index="norm_path", columns="deviceCategory", values="sessions", aggfunc="sum", fill_value=0)
            piv_eng = device_ux_df.pivot_table(index="norm_path", columns="deviceCategory", values="engagementRate", aggfunc="mean", fill_value=0.0)
            piv_time = device_ux_df.pivot_table(index="norm_path", columns="deviceCategory", values="avg_read_time_sec", aggfunc="mean", fill_value=0.0)

            device_flags_df = pd.DataFrame(index=piv_sess.index)
            device_flags_df["mobile_sessions"] = piv_sess.get("mobile", 0)
            device_flags_df["desktop_sessions"] = piv_sess.get("desktop", 0)
            device_flags_df["mobile_engagement_rate"] = piv_eng.get("mobile", 0.0)
            device_flags_df["desktop_engagement_rate"] = piv_eng.get("desktop", 0.0)
            device_flags_df["mobile_read_time"] = piv_time.get("mobile", 0.0)
            device_flags_df["desktop_read_time"] = piv_time.get("desktop", 0.0)

            # Flag: Mobile Engagement >= 20% lower than Desktop
            device_flags_df["mobile_gap"] = device_flags_df["desktop_engagement_rate"] - device_flags_df["mobile_engagement_rate"]
            device_flags_df["has_mobile_ux_alert"] = (
                (device_flags_df["mobile_sessions"] >= 20) &
                (device_flags_df["mobile_gap"] >= 0.20)
            )
            device_flags_df = device_flags_df.reset_index()

        # ----------------------------------------------------------------------
        # DATASET 3: GA4 AI Search & Referral Traffic Tracker
        # ----------------------------------------------------------------------
        ai_rows = []
        try:
            req_ai = RunReportRequest(
                property=prop_str,
                dimensions=[
                    Dimension(name="sessionSource"),
                    Dimension(name="landingPagePlusQueryString")
                ],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="engagedSessions"),
                    Metric(name="conversions")
                ],
                date_ranges=[DateRange(start_date=curr_start, end_date=curr_end)],
                limit=15000
            )
            rep_ai = data_client.run_report(req_ai)
            ai_regex = re.compile(r'(chatgpt|openai|perplexity|gemini|claude|copilot|bing|you\.com)', re.IGNORECASE)

            for row in rep_ai.rows:
                source_raw = row.dimension_values[0].value
                landing_raw = row.dimension_values[1].value

                if ai_regex.search(source_raw):
                    sess_ai = int(float(row.metric_values[0].value)) if len(row.metric_values) > 0 else 0
                    eng_ai = int(float(row.metric_values[1].value)) if len(row.metric_values) > 1 else 0
                    conv_ai = int(float(row.metric_values[2].value)) if len(row.metric_values) > 2 else 0
                    eng_rate_ai = (eng_ai / sess_ai) if sess_ai > 0 else 0.0

                    ai_rows.append({
                        "sessionSource": source_raw,
                        "raw_landing_page": landing_raw,
                        "norm_path": normalize_canonical_path(landing_raw),
                        "sessions": sess_ai,
                        "engagedSessions": eng_ai,
                        "engagementRate": eng_rate_ai,
                        "conversions": conv_ai
                    })
        except Exception as e_ai:
            print(f"GA4 AI Traffic query warning: {e_ai}")

        ai_search_df = pd.DataFrame(ai_rows)

        # ----------------------------------------------------------------------
        # DATASET 4: Fast Canonical Lookup Dictionary
        # ----------------------------------------------------------------------
        lookup = {}
        if not organic_landing_df.empty:
            for _, r in organic_landing_df.iterrows():
                p = r["norm_path"]
                lookup[p] = {
                    "sessions": int(r["sessions"]),
                    "totalUsers": int(r["totalUsers"]),
                    "engagedSessions": int(r["engagedSessions"]),
                    "engagementRate": float(r["engagementRate"]),
                    "bounceRate": float(r["bounceRate"]),
                    "avg_engagement_time_sec": float(r["avg_engagement_time_sec"]),
                    "read_time_formatted": str(r["read_time_formatted"]),
                    "conversions": int(r["conversions"]),
                    "conversion_rate": float(r["conversion_rate"]),
                    "prev_sessions": int(r["prev_sessions"]),
                    "sessions_delta_pct": float(r["sessions_delta_pct"]),
                    "conversions_delta_pct": float(r["conversions_delta_pct"])
                }

        # Merge device mobile gap flags into lookup
        if not device_flags_df.empty:
            for _, r in device_flags_df.iterrows():
                p = r["norm_path"]
                if p in lookup:
                    lookup[p]["mobile_engagement_rate"] = float(r["mobile_engagement_rate"])
                    lookup[p]["desktop_engagement_rate"] = float(r["desktop_engagement_rate"])
                    lookup[p]["mobile_gap"] = float(r["mobile_gap"])
                    lookup[p]["has_mobile_ux_alert"] = bool(r["has_mobile_ux_alert"])

        return {
            "organic_landing": organic_landing_df,
            "device_ux": device_ux_df,
            "device_flags": device_flags_df,
            "ai_search": ai_search_df,
            "lookup": lookup,
            "has_ga4": True
        }

    except Exception as e:
        print(f"Error fetching GA4 datasets: {e}")
        return empty_result


# ==============================================================================
# 3. SAMPLE / DEMO GA4 DATA GENERATOR
# ==============================================================================

def generate_sample_ga4_datasets(domain_name: str, pages_df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    Generates rich, realistic GA4 data matching the domain to provide a stunning demo
    whenever the user clicks 'Load Sample GSC Data' or has not connected live GA4 yet.
    """
    base_clean = domain_name.strip("/").replace("https://", "").replace("http://", "").replace("www.", "")
    if not base_clean:
        base_clean = "airaindia.com"

    sample_landing_records = [
        {
            "norm_path": "/",
            "sessions": 3840,
            "totalUsers": 3120,
            "engagedSessions": 2840,
            "engagementRate": 0.74,
            "bounceRate": 0.26,
            "avg_engagement_time_sec": 94.0,
            "read_time_formatted": "1m 34s",
            "conversions": 168,
            "conversion_rate": 0.0438,
            "eventCount": 24800,
            "prev_sessions": 3450,
            "prev_conversions": 152,
            "sessions_delta_pct": 11.3,
            "conversions_delta_pct": 10.5
        },
        {
            "norm_path": "/products/",
            "sessions": 1950,
            "totalUsers": 1680,
            "engagedSessions": 1380,
            "engagementRate": 0.708,
            "bounceRate": 0.292,
            "avg_engagement_time_sec": 82.0,
            "read_time_formatted": "1m 22s",
            "conversions": 84,
            "conversion_rate": 0.0431,
            "eventCount": 14200,
            "prev_sessions": 2100,
            "prev_conversions": 92,
            "sessions_delta_pct": -7.1,
            "conversions_delta_pct": -8.7
        },
        {
            "norm_path": "/double-off-set-disc-wafer-type-butterfly-valve/",
            "sessions": 860,
            "totalUsers": 740,
            "engagedSessions": 590,
            "engagementRate": 0.686,
            "bounceRate": 0.314,
            "avg_engagement_time_sec": 112.0,
            "read_time_formatted": "1m 52s",
            "conversions": 42,
            "conversion_rate": 0.0488,
            "eventCount": 6800,
            "prev_sessions": 690,
            "prev_conversions": 31,
            "sessions_delta_pct": 24.6,
            "conversions_delta_pct": 35.5
        },
        {
            "norm_path": "/knife-edge-gate-valve/",
            "sessions": 720,
            "totalUsers": 640,
            "engagedSessions": 490,
            "engagementRate": 0.681,
            "bounceRate": 0.319,
            "avg_engagement_time_sec": 88.0,
            "read_time_formatted": "1m 28s",
            "conversions": 28,
            "conversion_rate": 0.0389,
            "eventCount": 5400,
            "prev_sessions": 610,
            "prev_conversions": 24,
            "sessions_delta_pct": 18.0,
            "conversions_delta_pct": 16.7
        },
        {
            "norm_path": "/blog/aira-make-piston-valve/",
            "sessions": 480,
            "totalUsers": 450,
            "engagedSessions": 154,
            "engagementRate": 0.321,  # Case C: Traffic Leak (<40%)
            "bounceRate": 0.679,
            "avg_engagement_time_sec": 16.0,  # <20s
            "read_time_formatted": "0m 16s",
            "conversions": 0,
            "conversion_rate": 0.0000,
            "eventCount": 1120,
            "prev_sessions": 510,
            "prev_conversions": 2,
            "sessions_delta_pct": -5.9,
            "conversions_delta_pct": -100.0
        },
        {
            "norm_path": "/blog/best-control-valves-manufactured-by-aira-euro/",
            "sessions": 620,
            "totalUsers": 580,
            "engagedSessions": 465,
            "engagementRate": 0.750,  # Case D: Good read time >60s + 0 conversions
            "bounceRate": 0.250,
            "avg_engagement_time_sec": 78.0,
            "read_time_formatted": "1m 18s",
            "conversions": 0,
            "conversion_rate": 0.0000,
            "eventCount": 2400,
            "prev_sessions": 590,
            "prev_conversions": 0,
            "sessions_delta_pct": 5.1,
            "conversions_delta_pct": 0.0
        },
        {
            "norm_path": "/technical-specs/valve-torque-calculator",
            "sessions": 320,
            "totalUsers": 290,
            "engagedSessions": 230,
            "engagementRate": 0.719,  # Case E: High Conv (>2%) + Lower Rank
            "bounceRate": 0.281,
            "avg_engagement_time_sec": 95.0,
            "read_time_formatted": "1m 35s",
            "conversions": 16,
            "conversion_rate": 0.0500,
            "eventCount": 2900,
            "prev_sessions": 280,
            "prev_conversions": 12,
            "sessions_delta_pct": 14.3,
            "conversions_delta_pct": 33.3
        },
        {
            "norm_path": "/blog/aira-valves-in-textile-industry/",
            "sessions": 290,
            "totalUsers": 270,
            "engagedSessions": 110,
            "engagementRate": 0.379,  # Traffic drop / decay
            "bounceRate": 0.621,
            "avg_engagement_time_sec": 19.0,
            "read_time_formatted": "0m 19s",
            "conversions": 1,
            "conversion_rate": 0.0034,
            "eventCount": 890,
            "prev_sessions": 460,
            "prev_conversions": 6,
            "sessions_delta_pct": -37.0,  # Significant decay!
            "conversions_delta_pct": -83.3
        }
    ]

    organic_landing_df = pd.DataFrame(sample_landing_records)

    # Sample Device Breakdown with Mobile UX Alert
    sample_device_flags = [
        {
            "norm_path": "/",
            "mobile_sessions": 1920,
            "desktop_sessions": 1820,
            "mobile_engagement_rate": 0.71,
            "desktop_engagement_rate": 0.77,
            "mobile_read_time": 88.0,
            "desktop_read_time": 102.0,
            "mobile_gap": 0.06,
            "has_mobile_ux_alert": False
        },
        {
            "norm_path": "/products/",
            "mobile_sessions": 980,
            "desktop_sessions": 920,
            "mobile_engagement_rate": 0.44,  # Case F: Mobile UX Alert (0.76 - 0.44 = 0.32 >= 0.20)
            "desktop_engagement_rate": 0.76,
            "mobile_read_time": 32.0,
            "desktop_read_time": 95.0,
            "mobile_gap": 0.32,
            "has_mobile_ux_alert": True
        },
        {
            "norm_path": "/double-off-set-disc-wafer-type-butterfly-valve/",
            "mobile_sessions": 380,
            "desktop_sessions": 460,
            "mobile_engagement_rate": 0.65,
            "desktop_engagement_rate": 0.72,
            "mobile_read_time": 98.0,
            "desktop_read_time": 124.0,
            "mobile_gap": 0.07,
            "has_mobile_ux_alert": False
        },
        {
            "norm_path": "/blog/aira-make-piston-valve/",
            "mobile_sessions": 310,
            "desktop_sessions": 160,
            "mobile_engagement_rate": 0.22,  # Mobile UX Alert
            "desktop_engagement_rate": 0.52,
            "mobile_read_time": 12.0,
            "desktop_read_time": 25.0,
            "mobile_gap": 0.30,
            "has_mobile_ux_alert": True
        }
    ]
    device_flags_df = pd.DataFrame(sample_device_flags)

    # Sample AI Search Traffic Tracker
    sample_ai_traffic = [
        {"sessionSource": "ChatGPT (OpenAI)", "norm_path": "/products/", "sessions": 412, "engagedSessions": 348, "engagementRate": 0.845, "conversions": 28},
        {"sessionSource": "Perplexity AI", "norm_path": "/double-off-set-disc-wafer-type-butterfly-valve/", "sessions": 285, "engagedSessions": 242, "engagementRate": 0.849, "conversions": 19},
        {"sessionSource": "Google Gemini", "norm_path": "/", "sessions": 194, "engagedSessions": 158, "engagementRate": 0.814, "conversions": 14},
        {"sessionSource": "Claude AI (Anthropic)", "norm_path": "/knife-edge-gate-valve/", "sessions": 132, "engagedSessions": 108, "engagementRate": 0.818, "conversions": 9},
        {"sessionSource": "Microsoft Copilot", "norm_path": "/technical-specs/valve-torque-calculator", "sessions": 98, "engagedSessions": 76, "engagementRate": 0.776, "conversions": 6}
    ]
    ai_search_df = pd.DataFrame(sample_ai_traffic)

    # Fast Lookup Dict
    lookup = {}
    for _, r in organic_landing_df.iterrows():
        p = r["norm_path"]
        lookup[p] = {
            "sessions": int(r["sessions"]),
            "totalUsers": int(r["totalUsers"]),
            "engagedSessions": int(r["engagedSessions"]),
            "engagementRate": float(r["engagementRate"]),
            "bounceRate": float(r["bounceRate"]),
            "avg_engagement_time_sec": float(r["avg_engagement_time_sec"]),
            "read_time_formatted": str(r["read_time_formatted"]),
            "conversions": int(r["conversions"]),
            "conversion_rate": float(r["conversion_rate"]),
            "prev_sessions": int(r["prev_sessions"]),
            "sessions_delta_pct": float(r["sessions_delta_pct"]),
            "conversions_delta_pct": float(r["conversions_delta_pct"])
        }

    for _, r in device_flags_df.iterrows():
        p = r["norm_path"]
        if p in lookup:
            lookup[p]["mobile_engagement_rate"] = float(r["mobile_engagement_rate"])
            lookup[p]["desktop_engagement_rate"] = float(r["desktop_engagement_rate"])
            lookup[p]["mobile_gap"] = float(r["mobile_gap"])
            lookup[p]["has_mobile_ux_alert"] = bool(r["has_mobile_ux_alert"])

    return {
        "organic_landing": organic_landing_df,
        "device_ux": pd.DataFrame(),
        "device_flags": device_flags_df,
        "ai_search": ai_search_df,
        "lookup": lookup,
        "has_ga4": True
    }


# ==============================================================================
# 4. PART 2: EASY-TO-UNDERSTAND METRIC TRANSLATION & SUGGESTION ENGINE
# ==============================================================================

def generate_page_insights(row: dict) -> dict:
    """
    Translates raw GSC + GA4 metrics into easy-to-understand human badges,
    1-sentence plain language diagnosis, and concrete rule-based Future Suggestions.

    Covers:
    - userExperienceBadge: 🟢 High Reader Engagement / 🟡 Average / 🔴 High Bounce / ⚪ Connect GA4
    - plainLanguageDiagnosis: 1-sentence 'Kya Ho Raha Hai'
    - futureSuggestion: 'Future Plan / Kya Karein' across Cases A through F.
    """
    # GSC metrics
    clicks = int(row.get("clicks", 0)) if pd.notnull(row.get("clicks")) else 0
    impressions = int(row.get("impressions", 0)) if pd.notnull(row.get("impressions")) else 0
    pos = float(row.get("position", 0.0)) if pd.notnull(row.get("position")) else 0.0
    ctr = float(row.get("ctr", 0.0)) if pd.notnull(row.get("ctr")) else 0.0
    if ctr > 1.0:
        ctr = ctr / 100.0  # normalize percentage if needed

    # GA4 metrics
    has_ga4 = bool(row.get("has_ga4", False))
    sessions = int(row.get("sessions", 0)) if pd.notnull(row.get("sessions")) else 0
    eng_rate = float(row.get("engagementRate", 0.0)) if pd.notnull(row.get("engagementRate")) else 0.0
    read_time = float(row.get("avg_engagement_time_sec", 0.0)) if pd.notnull(row.get("avg_engagement_time_sec")) else 0.0
    conv = int(row.get("conversions", 0)) if pd.notnull(row.get("conversions")) else 0
    conv_rate = float(row.get("conversion_rate", 0.0)) if pd.notnull(row.get("conversion_rate")) else 0.0
    mobile_gap = float(row.get("mobile_gap", 0.0)) if pd.notnull(row.get("mobile_gap")) else 0.0
    has_mobile_alert = bool(row.get("has_mobile_ux_alert", False))
    sess_delta = float(row.get("sessions_delta_pct", 0.0)) if pd.notnull(row.get("sessions_delta_pct")) else 0.0

    # 1. userExperienceBadge
    if not has_ga4 or sessions <= 0:
        ux_badge = "⚪ Connect GA4 for Behavior Insights"
        badge_type = "neutral"
    elif eng_rate >= 0.60 and (read_time >= 45.0 or read_time == 0.0):
        ux_badge = "🟢 High Reader Engagement"
        badge_type = "good"
    elif (0.40 <= eng_rate < 0.60) or (read_time >= 20.0 and eng_rate >= 0.35):
        ux_badge = "🟡 Average Experience"
        badge_type = "warning"
    else:
        ux_badge = "🔴 High Bounce / Leaving Fast"
        badge_type = "critical"

    # 2. plainLanguageDiagnosis ("Kya Ho Raha Hai")
    if not has_ga4 or sessions <= 0:
        if pos <= 5.0 and ctr < 0.03 and impressions >= 500:
            diag = f"Google ranks this in Top 5 (Pos {pos:.1f}) with {impressions:,} impressions, but searchers are skipping your result (CTR {ctr*100:.1f}%)."
        elif 8.0 <= pos <= 20.0 and impressions >= 1000:
            diag = f"Ranking in striking distance on Page 2 (Pos {pos:.1f}) with strong impressions ({impressions:,}) but needs ranking lift."
        else:
            diag = f"Google Position {pos:.1f} driving {clicks:,} search clicks with {impressions:,} impressions ({ctr*100:.1f}% CTR)."
    else:
        # GA4 is connected
        if has_mobile_alert and mobile_gap >= 0.20:
            diag = f"Mobile readers are bouncing: Mobile engagement is {mobile_gap*100:.0f}% lower than desktop visitors."
        elif pos <= 5.0 and clicks >= 40 and (eng_rate < 0.40 or read_time < 20.0):
            leave_pct = int(round((1.0 - eng_rate) * 100))
            diag = f"Google ranks this page well (Pos {pos:.1f}) and sends {clicks:,} clicks, but {leave_pct}% of visitors leave in under {int(max(read_time, 15))}s without converting."
        elif eng_rate >= 0.65 and pos >= 8.0:
            diag = f"Visitors love this page ({eng_rate*100:.0f}% engagement, {conv_rate*100:.1f}% conversion rate), but it is stuck at Position {pos:.1f} on Google with low clicks."
        elif sess_delta <= -20.0:
            diag = f"Organic traffic dropped by {abs(sess_delta):.0f}% in the last 28 days indicating content decay or lost ranking."
        elif pos <= 5.0 and ctr < 0.03 and impressions >= 500:
            diag = f"Ranks at prime spot Pos {pos:.1f} with {impressions:,} impressions, but searchers are skipping your link (CTR {ctr*100:.1f}%)."
        elif conv > 0 and pos >= 10.0:
            diag = f"High-intent money page: converts at {conv_rate*100:.1f}% ({conv} leads), but only gets {clicks:,} search clicks due to Page 2 ranking."
        elif clicks >= 30 and read_time >= 60.0 and conv == 0:
            diag = f"Readers spend {format_read_time(read_time)} reading carefully ({clicks:,} clicks), but 0 visitors take action or convert."
        else:
            diag = f"Pos {pos:.1f} driving {clicks:,} clicks and {sessions:,} visits with {eng_rate*100:.0f}% engagement rate ({format_read_time(read_time)} read time)."

    # 3. futureSuggestion ("Future Plan / Kya Karein") - Exact Cases A through F
    if has_mobile_alert or (has_ga4 and mobile_gap >= 0.20):
        # Case F: Mobile UX Alert
        suggestion = "📱 Mobile UX Alert: Mobile readers are bouncing much faster than desktop users. Check mobile font spacing, intrusive popups, or large unoptimized images pushing content down."
        case_tag = "Case F: Mobile UX"

    elif has_ga4 and clicks >= 25 and (eng_rate < 0.40 or (0.0 < read_time < 20.0)):
        # Case C: Content & UX Fix (Traffic Leak)
        suggestion = "🛠️ Content & UX Fix (Traffic Leak): Searchers click your link but leave quickly. Move the main answer to the first paragraph, add a summary table/visuals above the fold, and check if page content matches the search query intent."
        case_tag = "Case C: Traffic Leak"

    elif has_ga4 and clicks >= 25 and read_time >= 60.0 and conv == 0:
        # Case D: CTA & Funnel Fix
        suggestion = "🎯 CTA & Funnel Fix: Visitors are reading your content carefully but taking no next step. Add an inline Call-to-Action (CTA), lead magnet, or link to your main service/product page mid-article."
        case_tag = "Case D: Funnel Fix"

    elif has_ga4 and 10.0 <= pos <= 40.0 and (conv_rate >= 0.02 or conv >= 5):
        # Case E: Scale This Money Page
        suggestion = "💎 Scale This Money Page: This page converts visitors into leads/customers very well. Build backlinks, publish 2 supporting blog posts linking to it, and expand content depth."
        case_tag = "Case E: Money Page"

    elif has_ga4 and 8.0 <= pos <= 20.0 and impressions >= 100 and eng_rate >= 0.55:
        # Case A: Priority Quick Win
        suggestion = "🚀 Priority Quick Win: Users love this page. Add top missing GSC queries into H2/FAQ headings and add 3–5 internal links from high-traffic pages to push it into Top 3."
        case_tag = "Case A: Quick Win"

    elif pos <= 5.0 and impressions >= 500 and ctr < 0.03:
        # Case B: Title / Meta Fix
        suggestion = "✍️ Title/Meta Fix: You already rank on Page 1 top spots, but searchers aren't clicking. Add numbers, current year, or a clear benefit in the SEO Title & Meta Description."
        case_tag = "Case B: CTR Fix"

    elif 8.0 <= pos <= 20.0 and impressions >= 300:
        # Fallback Quick Win when GA4 is not yet connected
        suggestion = "🚀 Priority Quick Win: Rank is in striking distance on Page 2. Incorporate query in H2/FAQ and build 2 contextual internal links from your homepage or top guide."
        case_tag = "Striking Distance"

    elif pos > 40.0 and impressions >= 500:
        # Keyword Gap
        suggestion = "🎯 New Landing Page Opportunity: High search demand with deep ranking. Create a dedicated in-depth guide targeting this specific query."
        case_tag = "Keyword Gap"

    else:
        suggestion = "📈 Monitor & Optimize: Continuously refresh on-page copy, improve answer clarity, and maintain internal linking to sustain authority."
        case_tag = "Maintenance"

    return {
        "userExperienceBadge": ux_badge,
        "badge_type": badge_type,
        "plainLanguageDiagnosis": diag,
        "futureSuggestion": suggestion,
        "case_tag": case_tag
    }


# ==============================================================================
# 5. GSC + GA4 PIPELINE MERGER & DATA ENRICHMENT
# ==============================================================================

def enrich_queries_and_pages_with_ga4(
    queries_df: pd.DataFrame,
    pages_df: pd.DataFrame,
    ga4_datasets: Dict[str, Any],
    base_domain: str = ""
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Enriches GSC Queries and Pages dataframes with normalized canonical path lookups,
    GA4 engagement & conversion metrics, and generates userExperienceBadge,
    plainLanguageDiagnosis, and futureSuggestion for every row.
    """
    lookup = ga4_datasets.get("lookup", {})
    has_ga4 = ga4_datasets.get("has_ga4", False)

    # 1. Enrich Pages DataFrame
    enriched_pages = pages_df.copy() if not pages_df.empty else pd.DataFrame()
    if not enriched_pages.empty:
        if "page" not in enriched_pages.columns:
            first_col = enriched_pages.columns[0]
            enriched_pages["page"] = enriched_pages[first_col]

        enriched_pages["norm_path"] = enriched_pages["page"].apply(normalize_canonical_path)

        # Attach GA4 fields
        for field in ["sessions", "engagementRate", "avg_engagement_time_sec", "read_time_formatted", "conversions", "conversion_rate", "sessions_delta_pct", "mobile_gap", "has_mobile_ux_alert"]:
            enriched_pages[field] = enriched_pages["norm_path"].apply(
                lambda p: lookup.get(p, {}).get(field, 0 if "count" in field or "session" in field or "conversion" in field else 0.0)
            )

        # Set has_ga4 flag on row
        enriched_pages["has_ga4"] = has_ga4

        # Generate insights for each page
        insights = enriched_pages.apply(lambda r: generate_page_insights(r.to_dict()), axis=1)
        enriched_pages["userExperienceBadge"] = [i["userExperienceBadge"] for i in insights]
        enriched_pages["plainLanguageDiagnosis"] = [i["plainLanguageDiagnosis"] for i in insights]
        enriched_pages["futureSuggestion"] = [i["futureSuggestion"] for i in insights]
        enriched_pages["case_tag"] = [i["case_tag"] for i in insights]

    # 2. Enrich Queries DataFrame
    enriched_queries = queries_df.copy() if not queries_df.empty else pd.DataFrame()
    if not enriched_queries.empty:
        # Determine target page column
        target_col = "target_page" if "target_page" in enriched_queries.columns else ("page" if "page" in enriched_queries.columns else "")
        if not target_col:
            enriched_queries["target_page"] = base_domain or "/"
            target_col = "target_page"

        enriched_queries["norm_path"] = enriched_queries[target_col].apply(normalize_canonical_path)

        # Attach GA4 fields to query row based on mapped landing page
        for field in ["sessions", "engagementRate", "avg_engagement_time_sec", "read_time_formatted", "conversions", "conversion_rate", "sessions_delta_pct", "mobile_gap", "has_mobile_ux_alert"]:
            enriched_queries[field] = enriched_queries["norm_path"].apply(
                lambda p: lookup.get(p, {}).get(field, 0 if "count" in field or "session" in field or "conversion" in field else 0.0)
            )

        enriched_queries["has_ga4"] = has_ga4

        q_insights = enriched_queries.apply(lambda r: generate_page_insights(r.to_dict()), axis=1)
        enriched_queries["userExperienceBadge"] = [i["userExperienceBadge"] for i in q_insights]
        enriched_queries["plainLanguageDiagnosis"] = [i["plainLanguageDiagnosis"] for i in q_insights]
        enriched_queries["futureSuggestion"] = [i["futureSuggestion"] for i in q_insights]
        enriched_queries["case_tag"] = [i["case_tag"] for i in q_insights]

    # 3. Build Unified Master URLs DataFrame
    org_landing = ga4_datasets.get("organic_landing", pd.DataFrame())
    if not enriched_pages.empty:
        unified_urls = enriched_pages.copy()
    elif not org_landing.empty:
        unified_urls = org_landing.copy()
        unified_urls["page"] = base_domain.rstrip("/") + unified_urls["norm_path"]
        unified_urls["clicks"] = 0
        unified_urls["impressions"] = 0
        unified_urls["ctr"] = 0.0
        unified_urls["position"] = 0.0
        unified_urls["has_ga4"] = True
        u_insights = unified_urls.apply(lambda r: generate_page_insights(r.to_dict()), axis=1)
        unified_urls["userExperienceBadge"] = [i["userExperienceBadge"] for i in u_insights]
        unified_urls["plainLanguageDiagnosis"] = [i["plainLanguageDiagnosis"] for i in u_insights]
        unified_urls["futureSuggestion"] = [i["futureSuggestion"] for i in u_insights]
        unified_urls["case_tag"] = [i["case_tag"] for i in u_insights]
    else:
        unified_urls = pd.DataFrame()

    return enriched_queries, enriched_pages, unified_urls


# ==============================================================================
# 6. TAB RENDERERS (THE 6 NEW COMBINED GA4 + GSC TABS)
# ==============================================================================

def render_cyber_card(title: str, value: str, subtitle: str, color_hex: str = "#00F0FF", icon: str = "⚡"):
    """Renders a sleek Cyber Cockpit KPI card matching CrawlPilot design."""
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(14, 24, 44, 0.95) 0%, rgba(9, 16, 32, 0.98) 100%);
                border: 1px solid {color_hex}44; border-radius: 14px; padding: 1.15rem 1.3rem;
                box-shadow: 0 8px 24px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
                transition: transform 0.2s ease, border-color 0.2s ease; margin-bottom: 0.8rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
            <span style="font-family: 'Space Grotesk', sans-serif; font-size: 0.82rem; font-weight: 700; color: #94A3B8; letter-spacing: 0.08em; text-transform: uppercase;">
                {title}
            </span>
            <span style="font-size: 1.25rem;">{icon}</span>
        </div>
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 1.85rem; font-weight: 900; color: #FFFFFF; line-height: 1.15; margin-bottom: 0.35rem;">
            {value}
        </div>
        <div style="font-size: 0.78rem; font-weight: 600; color: {color_hex};">
            {subtitle}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# TAB 1: 🧭 30-Day Future SEO Roadmap
# ------------------------------------------------------------------------------
def render_future_seo_roadmap_tab(
    enriched_queries: pd.DataFrame,
    enriched_pages: pd.DataFrame,
    unified_urls: pd.DataFrame,
    ga4_datasets: Dict[str, Any],
    saved_domain: str
):
    """
    Renders the 30-Day Future SEO Roadmap automatically grouped into a visual
    4-Week Action Cards View:
    - Week 1: Stop Traffic Leaks (GA4 + GSC) - Top 5 pages with high clicks but poor engagement/conversions
    - Week 2: Push Money Pages to Top 3 - Top 5 pages ranking Pos 8-20 with highest engagement/conversions
    - Week 3: Recover Dropping Pages (Content Decay) - Top 5 pages losing clicks & sessions over last 28 days
    - Week 4: New Content & AI Search Expansion - Top 5 question/topics from GSC questions & AI topics
    """
    st.markdown("""
    <div style="background: radial-gradient(120% 100% at 50% 0%, rgba(14, 165, 233, 0.18) 0%, rgba(15, 23, 42, 0.6) 100%);
                border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 16px; padding: 1.4rem 1.6rem; margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="font-size: 1.3rem;">🧭</span>
            <span style="font-weight: 900; font-size: 1.3rem; color: #38BDF8; font-family: 'Space Grotesk', sans-serif;">
                30-Day Future SEO Roadmap (4-Week Action Sprint)
            </span>
        </div>
        <div style="color: #CBD5E1; font-size: 0.92rem; line-height: 1.6;">
            A precise, algorithmic step-by-step gameplan built by merging <b>Google Search Console rankings</b> with <b>GA4 reader behavior and conversions</b>. Execute one sprint each week to eliminate traffic leaks and scale commercial revenue.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. Week 1: Stop Traffic Leaks (High clicks, Low engagement <40% or 0 conversions)
    if not unified_urls.empty and "clicks" in unified_urls.columns:
        w1_candidates = unified_urls[
            (unified_urls["clicks"] >= 10) &
            ((unified_urls.get("engagementRate", 0.0) < 0.40) | (unified_urls.get("avg_engagement_time_sec", 0.0) < 20.0))
        ].sort_values("clicks", ascending=False).head(5)
    else:
        w1_candidates = pd.DataFrame()

    # 2. Week 2: Push Money Pages to Top 3 (Pos 8-20 with high engagement >55% or conversions >0)
    if not enriched_queries.empty:
        w2_candidates = enriched_queries[
            (enriched_queries["position"] >= 8.0) &
            (enriched_queries["position"] <= 20.0) &
            (enriched_queries.get("engagementRate", 0.0) >= 0.50)
        ].sort_values("impressions", ascending=False).head(5)
    else:
        w2_candidates = pd.DataFrame()

    # 3. Week 3: Recover Dropping Pages (Sessions delta <= -15% or clicks drop)
    if not unified_urls.empty and "sessions_delta_pct" in unified_urls.columns:
        w3_candidates = unified_urls[
            (unified_urls["sessions_delta_pct"] <= -15.0)
        ].sort_values("sessions_delta_pct", ascending=True).head(5)
    else:
        w3_candidates = pd.DataFrame()

    # 4. Week 4: New Content & AI Expansion (Questions queries with high impressions)
    if not enriched_queries.empty:
        q_regex = r'\b(what|how|why|when|where|which|can|is|are|best|vs)\b'
        w4_candidates = enriched_queries[
            enriched_queries["query"].astype(str).str.lower().str.contains(q_regex, regex=True, na=False)
        ].sort_values("impressions", ascending=False).head(5)
    else:
        w4_candidates = pd.DataFrame()

    # Sprint Progress Overview
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_cyber_card("WEEK 1 GOAL", f"{len(w1_candidates)} Leaks", "Stop High-Bounce Traffic", "#FF6B4A", "🪣")
    with c2:
        render_cyber_card("WEEK 2 GOAL", f"{len(w2_candidates)} Pages", "Push High-Intent to Top 3", "#2DD4BF", "🚀")
    with c3:
        render_cyber_card("WEEK 3 GOAL", f"{len(w3_candidates)} Pages", "Recover Content Decay", "#F59E0B", "📉")
    with c4:
        render_cyber_card("WEEK 4 GOAL", f"{len(w4_candidates)} Topics", "Capture AI & Question Demand", "#C084FC", "🤖")

    st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)

    # 4-Week Accordion Cards View
    # Week 1
    with st.expander("🚨 WEEK 1: Stop Traffic Leaks (GA4 High-Bounce / Low-Conversion Pages)", expanded=True):
        st.markdown("""
        **Objective:** Fix pages where searchers are clicking your Google listing but bouncing in seconds. Moving the direct answer above the fold and matching query intent will plug this leak immediately.
        """)
        if not w1_candidates.empty:
            cols_w1 = [c for c in ["page", "clicks", "read_time_formatted", "userExperienceBadge", "futureSuggestion"] if c in w1_candidates.columns]
            st.dataframe(w1_candidates[cols_w1], use_container_width=True)
            st.markdown("""
            **Week 1 Execution Checklist:**
            - [ ] Open top leak page and check if first 100 words directly answer the search intent.
            - [ ] Remove intrusive popups or large header images pushing text down.
            - [ ] Add a quick summary table or TL;DR bullet box above the fold.
            """)
        else:
            st.success("🎉 Great news! No critical traffic leaks detected. All active landing pages have healthy reader engagement.")

    # Week 2
    with st.expander("💎 WEEK 2: Push High-Engagement Money Pages to Top 3 (Positions 8 to 20)", expanded=True):
        st.markdown("""
        **Objective:** These pages already convert or hold visitors' attention. Moving them from Page 2 to Top 3 will yield the biggest click and lead surge for your site.
        """)
        if not w2_candidates.empty:
            cols_w2 = [c for c in ["query", "target_page", "position", "impressions", "userExperienceBadge", "futureSuggestion"] if c in w2_candidates.columns]
            st.dataframe(w2_candidates[cols_w2], use_container_width=True)
            st.markdown("""
            **Week 2 Execution Checklist:**
            - [ ] Add the primary search query into an H2 sub-heading and inside the first paragraph.
            - [ ] Add 2–3 internal links from your highest-traffic pages (e.g. Homepage or Top Guides).
            - [ ] Add 2 FAQ schema questions targeting informational variations.
            """)
        else:
            st.info("No queries currently in striking distance with high GA4 engagement. Check Tab '⚡ Quick Wins' to see all Page 2 queries.")

    # Week 3
    with st.expander("📉 WEEK 3: Recover Dropping Pages (Content Decay Radar)", expanded=False):
        st.markdown("""
        **Objective:** Prevent competitor takeover by refreshing pages that have lost search visibility or GA4 sessions over the past 28 days.
        """)
        if not w3_candidates.empty:
            cols_w3 = [c for c in ["page", "sessions", "prev_sessions", "sessions_delta_pct", "plainLanguageDiagnosis", "futureSuggestion"] if c in w3_candidates.columns]
            st.dataframe(w3_candidates[cols_w3], use_container_width=True)
            st.markdown("""
            **Week 3 Execution Checklist:**
            - [ ] Update outdated stats, years, and broken links with current 2026 data.
            - [ ] Check if top competing URLs updated their content format or added video/calculators.
            - [ ] Request fresh re-indexing in Google Search Console URL Inspection tool.
            """)
        else:
            st.success("🎉 Site stability is strong! No major page decay (>15% drop) detected over the comparison window.")

    # Week 4
    with st.expander("🤖 WEEK 4: New Content & AI Search Expansion (Question Queries & High Demand)", expanded=False):
        st.markdown("""
        **Objective:** Expand your site's topical authority and capture AI Search citations (ChatGPT, Perplexity, Gemini) by answering unanswered questions.
        """)
        if not w4_candidates.empty:
            cols_w4 = [c for c in ["query", "target_page", "impressions", "position", "futureSuggestion"] if c in w4_candidates.columns]
            st.dataframe(w4_candidates[cols_w4], use_container_width=True)
            st.markdown("""
            **Week 4 Execution Checklist:**
            - [ ] Publish standalone 800-word guides for high-impression questions lacking a dedicated page.
            - [ ] Include clear definition blocks, comparison tables, and FAQPage structured data schema.
            - [ ] Interlink newly published guides to your Week 2 money pages.
            """)
        else:
            st.info("Check Tab '❓ Questions & Informational' for the complete list of conversational search queries.")


# ------------------------------------------------------------------------------
# TAB 2: 💎 Money Pages vs. Traffic Leaks (GSC × GA4)
# ------------------------------------------------------------------------------
def render_money_pages_vs_leaks_tab(
    unified_urls: pd.DataFrame,
    enriched_queries: pd.DataFrame,
    ga4_datasets: Dict[str, Any],
    saved_domain: str
):
    """
    Renders Top Summary KPI cards + Sub-views:
    - Sub-view 1: 💎 Hidden Money Pages (High GA4 Value, Low GSC Rank)
    - Sub-view 2: 🪣 Traffic Leak Pages (High GSC Clicks, Bad GA4 Engagement)
    """
    st.markdown("""
    <div style="background: radial-gradient(120% 100% at 50% 0%, rgba(45, 212, 191, 0.15) 0%, rgba(15, 23, 42, 0.6) 100%);
                border: 1px solid rgba(45, 212, 191, 0.35); border-radius: 16px; padding: 1.4rem 1.6rem; margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="font-size: 1.3rem;">💎</span>
            <span style="font-weight: 900; font-size: 1.3rem; color: #2DD4BF; font-family: 'Space Grotesk', sans-serif;">
                Money Pages vs. Traffic Leaks (GSC × GA4 Intersection)
            </span>
        </div>
        <div style="color: #CBD5E1; font-size: 0.92rem; line-height: 1.6;">
            Raw GSC rankings don't tell you if visitors convert. Raw GA4 metrics don't tell you where visitors came from. This view merges both to separate your highest-converting assets from pages bleeding traffic.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Top KPI Metrics
    total_sess = unified_urls["sessions"].sum() if not unified_urls.empty and "sessions" in unified_urls.columns else 0
    total_conv = unified_urls["conversions"].sum() if not unified_urls.empty and "conversions" in unified_urls.columns else 0
    avg_eng = unified_urls["engagementRate"].mean() if not unified_urls.empty and "engagementRate" in unified_urls.columns else 0.0
    avg_sec = unified_urls["avg_engagement_time_sec"].mean() if not unified_urls.empty and "avg_engagement_time_sec" in unified_urls.columns else 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_cyber_card("GA4 ORGANIC SESSIONS", f"{int(total_sess):,}", "Total Verified Visits", "#00F0FF", "👥")
    with k2:
        render_cyber_card("AVG READ TIME", format_read_time(avg_sec), "Attention Span per Visitor", "#2DD4BF", "⏱️")
    with k3:
        render_cyber_card("ENGAGEMENT RATE", f"{avg_eng*100:.1f}%", "Readers Interacting (>10s)", "#34D399", "📊")
    with k4:
        render_cyber_card("ORGANIC CONVERSIONS", f"{int(total_conv):,}", "Key Events / Inquiries", "#F59E0B", "🎯")

    # Filter into 2 Sub-views
    # Sub-view 1: Hidden Money Pages (High Engagement > 60% or Conv > 0, but Pos > 8.0)
    if not unified_urls.empty:
        money_pages = unified_urls[
            ((unified_urls.get("conversion_rate", 0.0) >= 0.02) | (unified_urls.get("engagementRate", 0.0) >= 0.65)) &
            (unified_urls.get("position", 0.0) >= 7.0)
        ].sort_values(["conversions", "sessions"], ascending=[False, False]).reset_index(drop=True)
    else:
        money_pages = pd.DataFrame()

    # Sub-view 2: Traffic Leaks (Clicks >= 15, Engagement < 40% or Read Time < 20s)
    if not unified_urls.empty and "clicks" in unified_urls.columns:
        leak_pages = unified_urls[
            (unified_urls["clicks"] >= 10) &
            ((unified_urls.get("engagementRate", 0.0) < 0.40) | (unified_urls.get("avg_engagement_time_sec", 0.0) < 20.0))
        ].sort_values("clicks", ascending=False).reset_index(drop=True)
    else:
        leak_pages = pd.DataFrame()

    t_money, t_leaks = st.tabs([
        f"💎 Hidden Money Pages ({len(money_pages)})",
        f"🪣 Traffic Leaks ({len(leak_pages)})"
    ])

    with t_money:
        st.markdown("""
        <div style="background: rgba(45, 212, 191, 0.08); border-left: 4px solid #2DD4BF; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 0.88rem; color: #CBD5E1;">
            <b>💎 What this means:</b> These pages convert visitors into leads/customers at high rates, but they are held back on Google Page 2 or lower. Boosting their GSC rankings will directly generate new revenue.
        </div>
        """, unsafe_allow_html=True)
        if not money_pages.empty:
            cols = [c for c in ["page", "position", "clicks", "sessions", "read_time_formatted", "userExperienceBadge", "conversions", "plainLanguageDiagnosis", "futureSuggestion"] if c in money_pages.columns]
            st.dataframe(money_pages[cols], use_container_width=True, height=360)
        else:
            st.info("No hidden money pages currently matching criteria. As search traffic grows, pages with high conversions will surface here.")

    with t_leaks:
        st.markdown("""
        <div style="background: rgba(239, 68, 68, 0.08); border-left: 4px solid #EF4444; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 0.88rem; color: #CBD5E1;">
            <b>🪣 What this means:</b> You are spending effort ranking these pages and winning search clicks, but readers bounce almost immediately without reading or converting.
        </div>
        """, unsafe_allow_html=True)
        if not leak_pages.empty:
            cols = [c for c in ["page", "clicks", "sessions", "read_time_formatted", "userExperienceBadge", "plainLanguageDiagnosis", "futureSuggestion"] if c in leak_pages.columns]
            st.dataframe(leak_pages[cols], use_container_width=True, height=360)
        else:
            st.success("🎉 No traffic leak pages detected! Every high-click landing page has satisfied readers.")


# ------------------------------------------------------------------------------
# TAB 3: 📊 GA4 Landing Page Health & Conversions
# ------------------------------------------------------------------------------
def render_ga4_landing_health_tab(
    unified_urls: pd.DataFrame,
    ga4_datasets: Dict[str, Any],
    saved_domain: str
):
    """
    Renders a clean, beginner-friendly table of all Organic Landing Pages:
    - Page Path
    - GSC Clicks vs. GA4 Organic Visits
    - Avg Read Time (mm:ss)
    - Reader Experience Badge (🟢 Loved / 🟡 Okay / 🔴 High Bounce)
    - Conversions / Key Events
    - 30-Day Trend (📈 +X% / 📉 -Y%)
    - Future Suggestion (Next Step to Take)
    """
    st.markdown("""
    <div style="background: radial-gradient(120% 100% at 50% 0%, rgba(99, 102, 241, 0.18) 0%, rgba(15, 23, 42, 0.6) 100%);
                border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 16px; padding: 1.4rem 1.6rem; margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="font-size: 1.3rem;">📊</span>
            <span style="font-weight: 900; font-size: 1.3rem; color: #818CF8; font-family: 'Space Grotesk', sans-serif;">
                GA4 Landing Page Health & Conversions
            </span>
        </div>
        <div style="color: #CBD5E1; font-size: 0.92rem; line-height: 1.6;">
            A complete health scorecard for every organic landing page on your domain. Translates complex behavioral engagement into simple badges and concrete action plans.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if unified_urls.empty:
        st.info("No landing pages data available. Connect GA4 or load sample data above to preview.")
        return

    disp_df = unified_urls.copy()
    if "norm_path" not in disp_df.columns and "page" in disp_df.columns:
        disp_df["norm_path"] = disp_df["page"].apply(normalize_canonical_path)

    # 30-Day Trend formatted string
    if "sessions_delta_pct" in disp_df.columns:
        disp_df["30-Day Trend"] = disp_df["sessions_delta_pct"].apply(
            lambda x: f"📈 +{x:.1f}%" if x > 0 else (f"📉 {x:.1f}%" if x < 0 else "➖ 0.0%")
        )
    else:
        disp_df["30-Day Trend"] = "➖ Stable"

    cols = [
        "norm_path",
        "clicks",
        "sessions",
        "read_time_formatted",
        "userExperienceBadge",
        "conversions",
        "30-Day Trend",
        "futureSuggestion"
    ]
    cols = [c for c in cols if c in disp_df.columns]
    rename_map = {
        "norm_path": "Page Path",
        "clicks": "GSC Clicks",
        "sessions": "GA4 Organic Visits",
        "read_time_formatted": "Avg Read Time",
        "userExperienceBadge": "Reader Experience",
        "conversions": "Conversions",
        "futureSuggestion": "Next Step / Action Plan"
    }

    st.dataframe(
        disp_df[cols].rename(columns=rename_map),
        use_container_width=True,
        height=450
    )


# ------------------------------------------------------------------------------
# TAB 4: 📉 Rising & Dropping Pages (30-Day Trend Radar)
# ------------------------------------------------------------------------------
def render_trend_radar_tab(
    unified_urls: pd.DataFrame,
    ga4_datasets: Dict[str, Any],
    saved_domain: str
):
    """
    Compares Current Period vs. Previous Period for GSC and GA4.
    Split into:
    - 📉 Dropping Pages (Need Refresh) with automatic diagnosis of WHY it dropped
    - 🚀 Rising Stars (Double Down)
    """
    st.markdown("""
    <div style="background: radial-gradient(120% 100% at 50% 0%, rgba(245, 158, 11, 0.15) 0%, rgba(15, 23, 42, 0.6) 100%);
                border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 16px; padding: 1.4rem 1.6rem; margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="font-size: 1.3rem;">📉</span>
            <span style="font-weight: 900; font-size: 1.3rem; color: #FBBF24; font-family: 'Space Grotesk', sans-serif;">
                Rising & Dropping Pages (30-Day Trend Radar)
            </span>
        </div>
        <div style="color: #CBD5E1; font-size: 0.92rem; line-height: 1.6;">
            Detects pages losing momentum before traffic flatlines. Compares performance period-over-period, explains <b>why</b> traffic moved, and provides a specific content refresh checklist.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if unified_urls.empty:
        st.info("No comparative trend data available.")
        return

    # Filter Dropping Pages vs Rising Stars
    dropping_df = unified_urls[
        unified_urls.get("sessions_delta_pct", 0.0) <= -15.0
    ].sort_values("sessions_delta_pct", ascending=True).reset_index(drop=True)

    rising_df = unified_urls[
        unified_urls.get("sessions_delta_pct", 0.0) >= 15.0
    ].sort_values("sessions_delta_pct", ascending=False).reset_index(drop=True)

    t_drop, t_rise = st.tabs([
        f"📉 Dropping Pages ({len(dropping_df)})",
        f"🚀 Rising Stars ({len(rising_df)})"
    ])

    with t_drop:
        if not dropping_df.empty:
            st.markdown("""
            <div style="background: rgba(239, 68, 68, 0.08); border-left: 4px solid #EF4444; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 0.88rem; color: #CBD5E1;">
                <b>⚠️ Attention Required:</b> These pages lost 15% or more organic traffic compared to the preceding period. Refresh these first to regain lost impressions.
            </div>
            """, unsafe_allow_html=True)
            cols = [c for c in ["page", "sessions", "prev_sessions", "sessions_delta_pct", "plainLanguageDiagnosis", "futureSuggestion"] if c in dropping_df.columns]
            st.dataframe(dropping_df[cols], use_container_width=True, height=320)

            st.markdown("""
            #### 🛠️ Content Refresh Checklist (Apply to Dropping Pages)
            1. **Verify Competitor Changes:** Search your target keyword in Incognito. Check if new competitor pages have added tables, video embeds, or updated pricing.
            2. **Update Timestamps & Headers:** Refresh the publication date and ensure headings reference current best practices.
            3. **Fix Internal Link Gaps:** Add 2 new links to the decaying page from recently published high-authority articles.
            4. **Ping Google:** Request re-crawling in Search Console URL Inspection.
            """)
        else:
            st.success("🎉 No decaying pages detected. All organic landing pages maintained or grew traffic over the last 30 days!")

    with t_rise:
        if not rising_df.empty:
            st.markdown("""
            <div style="background: rgba(16, 185, 129, 0.08); border-left: 4px solid #10B981; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 0.88rem; color: #CBD5E1;">
                <b>🚀 Double Down:</b> These pages gained +15% or more organic traffic. Turn these into authority hubs by linking them to your money pages.
            </div>
            """, unsafe_allow_html=True)
            cols = [c for c in ["page", "sessions", "prev_sessions", "sessions_delta_pct", "read_time_formatted", "userExperienceBadge", "futureSuggestion"] if c in rising_df.columns]
            st.dataframe(rising_df[cols], use_container_width=True, height=320)
        else:
            st.info("No surging pages detected with >15% growth over the comparison period.")


# ------------------------------------------------------------------------------
# TAB 5: 📱 Mobile vs. Desktop SEO Check (GA4 UX)
# ------------------------------------------------------------------------------
def render_mobile_desktop_tab(
    ga4_datasets: Dict[str, Any],
    unified_urls: pd.DataFrame,
    saved_domain: str
):
    """
    Compares GSC + GA4 performance by Device (Mobile vs. Desktop).
    Flags pages where Mobile traffic is high, but Mobile Engagement Rate is >= 20%
    lower than Desktop, providing clear mobile UX suggestions.
    """
    st.markdown("""
    <div style="background: radial-gradient(120% 100% at 50% 0%, rgba(168, 85, 247, 0.15) 0%, rgba(15, 23, 42, 0.6) 100%);
                border: 1px solid rgba(168, 85, 247, 0.35); border-radius: 16px; padding: 1.4rem 1.6rem; margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="font-size: 1.3rem;">📱</span>
            <span style="font-weight: 900; font-size: 1.3rem; color: #C084FC; font-family: 'Space Grotesk', sans-serif;">
                Mobile vs. Desktop SEO & UX Audit (GA4 Data)
            </span>
        </div>
        <div style="color: #CBD5E1; font-size: 0.92rem; line-height: 1.6;">
            Google indexes mobile versions first. If your mobile visitors bounce much faster than desktop users, rankings across your entire site suffer.
        </div>
    </div>
    """, unsafe_allow_html=True)

    flags_df = ga4_datasets.get("device_flags", pd.DataFrame())

    if flags_df.empty:
        st.info("Device category breakdown is not available for this period. Ensure GA4 is selected.")
        return

    # Summary Metrics
    tot_mob = flags_df["mobile_sessions"].sum() if "mobile_sessions" in flags_df.columns else 0
    tot_desk = flags_df["desktop_sessions"].sum() if "desktop_sessions" in flags_df.columns else 0
    tot_all = max(1, tot_mob + tot_desk)

    avg_mob_eng = flags_df["mobile_engagement_rate"].mean() if "mobile_engagement_rate" in flags_df.columns else 0.0
    avg_desk_eng = flags_df["desktop_engagement_rate"].mean() if "desktop_engagement_rate" in flags_df.columns else 0.0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_cyber_card("MOBILE TRAFFIC SHARE", f"{(tot_mob/tot_all)*100:.1f}%", f"{int(tot_mob):,} Mobile Visits", "#00F0FF", "📱")
    with m2:
        render_cyber_card("DESKTOP TRAFFIC SHARE", f"{(tot_desk/tot_all)*100:.1f}%", f"{int(tot_desk):,} Desktop Visits", "#2DD4BF", "💻")
    with m3:
        render_cyber_card("MOBILE ENGAGEMENT", f"{avg_mob_eng*100:.1f}%", "Mobile Reader Rate", "#C084FC", "📊")
    with m4:
        render_cyber_card("DESKTOP ENGAGEMENT", f"{avg_desk_eng*100:.1f}%", "Desktop Reader Rate", "#34D399", "🖥️")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Filter pages with Mobile Alert
    alert_pages = flags_df[
        (flags_df.get("has_mobile_ux_alert", False) == True) |
        (flags_df.get("mobile_gap", 0.0) >= 0.20)
    ].sort_values("mobile_gap", ascending=False).reset_index(drop=True)

    if not alert_pages.empty:
        st.markdown(f"""
        <div style="background: rgba(239, 68, 68, 0.08); border-left: 4px solid #EF4444; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 0.88rem; color: #CBD5E1;">
            <b>⚠️ Mobile UX Alerts ({len(alert_pages)} Pages):</b> On these pages, mobile readers leave much faster than desktop visitors (gap ≥ 20%). Review responsive layout, tap targets, and image loading.
        </div>
        """, unsafe_allow_html=True)

        disp_alerts = alert_pages.copy()
        disp_alerts["Mobile Eng Rate"] = disp_alerts["mobile_engagement_rate"].apply(lambda x: f"{x*100:.1f}%")
        disp_alerts["Desktop Eng Rate"] = disp_alerts["desktop_engagement_rate"].apply(lambda x: f"{x*100:.1f}%")
        disp_alerts["UX Gap"] = disp_alerts["mobile_gap"].apply(lambda x: f"🔴 -{x*100:.1f}%")
        disp_alerts["Recommendation"] = "📱 Check mobile font spacing, intrusive popups, or large unoptimized images pushing content down."

        show_cols = ["norm_path", "mobile_sessions", "desktop_sessions", "Mobile Eng Rate", "Desktop Eng Rate", "UX Gap", "Recommendation"]
        show_cols = [c for c in show_cols if c in disp_alerts.columns]
        st.dataframe(disp_alerts[show_cols], use_container_width=True, height=280)
    else:
        st.success("🎉 Mobile UX health is excellent! No severe mobile bounce gaps detected across landing pages.")


# ------------------------------------------------------------------------------
# TAB 6: 🤖 AI Search Traffic (ChatGPT, Perplexity, Gemini, Claude)
# ------------------------------------------------------------------------------
def render_ai_search_traffic_tab(
    ga4_datasets: Dict[str, Any],
    unified_urls: pd.DataFrame,
    saved_domain: str
):
    """
    Uses GA4 sessionSource data to show visitors and conversions coming from
    AI platforms (ChatGPT, Perplexity, Gemini, Claude, Copilot) and top cited pages,
    plus concrete suggestions on how to format pages for AI engine citations.
    """
    st.markdown("""
    <div style="background: radial-gradient(120% 100% at 50% 0%, rgba(139, 92, 246, 0.22) 0%, rgba(15, 23, 42, 0.6) 100%);
                border: 1px solid rgba(139, 92, 246, 0.4); border-radius: 16px; padding: 1.4rem 1.6rem; margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="font-size: 1.3rem;">🤖</span>
            <span style="font-weight: 900; font-size: 1.3rem; color: #A78BFA; font-family: 'Space Grotesk', sans-serif;">
                AI Search & Answer Engine Traffic Tracker
            </span>
        </div>
        <div style="color: #CBD5E1; font-size: 0.92rem; line-height: 1.6;">
            Tracks visitors who discovered your brand via generative search platforms: <b>ChatGPT (OpenAI), Perplexity AI, Google Gemini, Claude (Anthropic), and Microsoft Copilot</b>.
        </div>
    </div>
    """, unsafe_allow_html=True)

    ai_df = ga4_datasets.get("ai_search", pd.DataFrame())

    if ai_df.empty:
        st.info("No AI search referral traffic recorded in the selected period. As generative engines index your content, citations will appear here.")
        return

    # KPI Summary
    tot_ai_sess = ai_df["sessions"].sum() if "sessions" in ai_df.columns else 0
    tot_ai_conv = ai_df["conversions"].sum() if "conversions" in ai_df.columns else 0
    avg_ai_eng = ai_df["engagementRate"].mean() if "engagementRate" in ai_df.columns else 0.0

    a1, a2, a3 = st.columns(3)
    with a1:
        render_cyber_card("TOTAL AI ENGINE VISITS", f"{int(tot_ai_sess):,}", "ChatGPT, Perplexity, Gemini", "#A78BFA", "🤖")
    with a2:
        render_cyber_card("AI READER ENGAGEMENT", f"{avg_ai_eng*100:.1f}%", "Highly Targeted Intent", "#34D399", "⚡")
    with a3:
        render_cyber_card("AI ASSISTED CONVERSIONS", f"{int(tot_ai_conv):,}", "Leads from AI Search", "#F59E0B", "🎯")

    st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)

    col_chart, col_pages = st.columns([1.2, 1.8])

    with col_chart:
        st.markdown("#### 🌐 AI Traffic by Engine Source")
        if "sessionSource" in ai_df.columns:
            src_agg = ai_df.groupby("sessionSource", as_index=False)["sessions"].sum().sort_values("sessions", ascending=False)
            fig_ai = px.pie(
                src_agg,
                names="sessionSource",
                values="sessions",
                color_discrete_sequence=["#8B5CF6", "#06B6D4", "#10B981", "#F59E0B", "#EC4899"],
                hole=0.45
            )
            fig_ai.update_layout(
                paper_bgcolor="rgba(15, 23, 42, 0.0)",
                plot_bgcolor="rgba(15, 23, 42, 0.0)",
                font=dict(color="#CBD5E1"),
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_ai, use_container_width=True)

    with col_pages:
        st.markdown("#### 📄 Top Cited Landing Pages in AI Answers")
        p_cols = [c for c in ["norm_path", "sessionSource", "sessions", "conversions"] if c in ai_df.columns]
        st.dataframe(ai_df[p_cols].sort_values("sessions", ascending=False), use_container_width=True, height=260)

    # AI Citation Optimization Guide
    st.markdown("""
    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 12px; padding: 1.2rem; margin-top: 1.2rem;">
        <h4 style="color: #A78BFA; margin-bottom: 0.6rem; font-size: 1.05rem;">
            💡 How to Optimize Your Pages to Get Cited in ChatGPT & Perplexity Answers
        </h4>
        <ul style="color: #CBD5E1; font-size: 0.88rem; line-height: 1.7; margin: 0; padding-left: 1.2rem;">
            <li><b>Direct Answer Paragraph (TL;DR):</b> Put a clear 40–60 word answer to the user's question directly below the H1 heading. AI crawlers favor this definition format.</li>
            <li><b>Structured Comparison Tables:</b> LLMs extract data from HTML tables 3x more reliably than prose. Include feature, price, or spec comparison matrices.</li>
            <li><b>FAQ Schema Markup:</b> Wrap question-answer pairs in valid JSON-LD schema so LLMs recognize authoritative entity relationships.</li>
            <li><b>Authoritative Bullet Points:</b> Use numbered lists for steps and bulleted lists for specifications.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
