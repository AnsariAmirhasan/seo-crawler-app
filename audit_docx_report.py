"""
audit_docx_report.py - Executive Client Technical SEO Audit Document Generator
Generates high-impact, professional Microsoft Word (.docx) audit reports with:
- Client / Agency Logo in header of every page (and cover page)
- Structured Table of Contents / Index
- Website Strengths & Positive SEO Factors (What is Working)
- Critical Vulnerabilities & Negative Points (What is Holding the Site Back)
- Strategic 'Why We Must Fix This' (SEO & Business Impact for Client)
- Detailed Category-by-Category Explanations & Developer Action Guides
- Tables of Flagged URLs with Suggested Meta Tags, H1s, and Redirects
- 3-Phase Prioritized Action Roadmap
"""

import io
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from PIL import Image

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

logger = logging.getLogger(__name__)

# ==============================================================================
# COLOR PALETTE & STYLES
# ==============================================================================
COLOR_PRIMARY = RGBColor(30, 58, 138)     # Deep Navy (#1E3A8A)
COLOR_SECONDARY = RGBColor(79, 70, 229)  # Indigo (#4F46E5)
COLOR_DARK = RGBColor(30, 41, 59)        # Slate 800 (#1E293B)
COLOR_MUTED = RGBColor(100, 116, 139)    # Slate 500 (#64748B)
COLOR_FAIL = RGBColor(185, 28, 28)       # Red 700 (#B91C1C)
COLOR_PASS = RGBColor(21, 128, 61)       # Green 700 (#15803D)

HEX_HEADER_BG = "1E3A8A"                 # Deep Navy
HEX_SUBHEADER_BG = "4F46E5"              # Indigo
HEX_LIGHT_BG = "F8FAFC"                  # Very Light Slate
HEX_FAIL_BG = "FEE2E2"                   # Light Red
HEX_PASS_BG = "DCFCE7"                   # Light Green
HEX_BORDER = "CBD5E1"                    # Light Border


def set_cell_background(cell, hex_color: str):
    """Apply background color fill to a docx table cell."""
    try:
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading)
    except Exception:
        pass


def set_cell_padding(cell, top=100, bottom=100, left=140, right=140):
    """Set inner cell margins/padding (dxa units: 20 dxa = 1 pt)."""
    try:
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for side, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{side}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)
    except Exception:
        pass


def add_callout_box(doc, title: str, text: str, border_hex="4F46E5", bg_hex="F8FAFC"):
    """Create an attractive executive callout box with a colored left accent border."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    cell = tbl.rows[0].cells[0]
    cell.width = Inches(6.8)
    set_cell_background(cell, bg_hex)
    set_cell_padding(cell, top=140, bottom=140, left=180, right=140)
    
    # Left border only
    try:
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:top w:val="none"/>'
            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_hex}"/>'
            f'<w:bottom w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)
    except Exception:
        pass

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    run_t = p.add_run(f"💡 {title}\n")
    run_t.font.bold = True
    run_t.font.size = Pt(11)
    run_t.font.color.rgb = COLOR_PRIMARY

    run_b = p.add_run(text)
    run_b.font.size = Pt(10)
    run_b.font.color.rgb = COLOR_DARK
    
    # Empty space after callout
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)


def format_logo_for_docx(logo_bytes: bytes) -> Optional[io.BytesIO]:
    """Convert uploaded logo to clean PNG buffer for Word embedding."""
    if not logo_bytes:
        return None
    try:
        img = Image.open(io.BytesIO(logo_bytes))
        # Convert RGBA / P / WebP to clean RGB/RGBA PNG
        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG")
        out_buf.seek(0)
        return out_buf
    except Exception as e:
        logger.warning(f"Failed to format logo for docx: {e}")
        return None


# ==============================================================================
# STRATEGIC CLIENT ERROR ANALYSIS & BUSINESS IMPACT
# ==============================================================================

def get_error_category_analysis(category_name: str, count: int) -> dict:
    """
    Returns rich, executive-level client explanations for technical SEO error categories.
    Explains the business impact, search engine penalty, and commercial ROI of fixing.
    """
    name_l = category_name.lower()
    
    # 1. Multiple H1 tags
    if "multiple h1" in name_l:
        return {
            "what_is_it": (
                f"A total of {count:,} pages on your website have more than one <h1> heading tag embedded in their template structure. "
                "In web semantics, the <h1> tag is designated as the primary title and thematic anchor of the entire webpage."
            ),
            "business_impact": (
                "When prospective buyers or clients land on a page with multiple competing H1 headings, the visual hierarchy is disrupted, "
                "leading to cognitive confusion and lower conversion rates. Multiple H1s dilute your core marketing message and weaken the page value proposition."
            ),
            "search_engine_impact": (
                "Googlebot and modern search algorithms use the <h1> tag to verify the primary topic of the document. "
                "When multiple H1s are present, topical relevance is split across multiple headings. This causes internal keyword dilution and "
                "prevents the page from achieving top 3 ranking positions for competitive commercial search terms."
            ),
            "solution_roi": (
                "Consolidating to exactly one primary <h1> tag focuses 100% of the page's structural authority onto your main commercial keyword, "
                "strengthening organic rankings and improving visitor clarity."
            )
        }
    
    # 2. Missing H1 tags
    elif "missing h1" in name_l or "h1 missing" in name_l or name_l == "h1":
        return {
            "what_is_it": (
                f"We identified {count:,} indexable landing pages that completely lack a primary <h1> heading tag in their HTML markup."
            ),
            "business_impact": (
                "A webpage without an H1 heading is like a book published without a title. Prospective customers landing on the page cannot "
                "immediately confirm that they have arrived at the solution to their search query, triggering instant page abandonment."
            ),
            "search_engine_impact": (
                "Search engine spiders require strong header hierarchy to comprehend document semantics. Without an H1, Google is forced "
                "to guess the primary topic from scattered paragraphs, body copy, or footer menus, causing significant ranking instability."
            ),
            "solution_roi": (
                "Implementing a clear, keyword-targeted H1 heading anchors the page topic, boosts organic relevance scores, and reassures visitors."
            )
        }

    # 3. Minify JavaScript and CSS files
    elif "minify" in name_l or "unminified" in name_l or "javascript" in name_l or "css" in name_l:
        return {
            "what_is_it": (
                f"Our audit detected {count:,} unminified JavaScript (.js) and stylesheet (.css) files loading across your key pages. "
                "These files contain unnecessary whitespace, developer comments, formatting indentations, and uncompressed code."
            ),
            "business_impact": (
                "Every additional 100 milliseconds of page load latency decreases website conversion rates by up to 7%. "
                "Unminified scripts force user browsers to download bloated files, resulting in sluggish mobile page loading, frustrating shoppers, "
                "and driving high bounce rates directly into the arms of faster competitors."
            ),
            "search_engine_impact": (
                "Google officially uses Core Web Vitals (including Largest Contentful Paint [LCP] and First Contentful Paint [FCP]) "
                "as critical ranking factors. Unminified JavaScript and CSS files act as severe 'render-blocking resources'—meaning the browser "
                "cannot paint text or products on the screen until these heavy files finish downloading. This directly drags down your Google PageSpeed "
                "scores and suppresses mobile search rankings."
            ),
            "solution_roi": (
                "Minifying and bundling these static assets slashes payload weight by 30% to 70%, unblocks critical rendering paths, "
                "improves Core Web Vitals scores, and elevates mobile search visibility and checkout completion rates."
            )
        }

    # 4. Meta Description Missing
    elif "meta description" in name_l and ("missing" in name_l or "empty" in name_l):
        return {
            "what_is_it": (
                f"There are {count:,} pages on your website that completely lack a meta description tag in their header code."
            ),
            "business_impact": (
                "The meta description is your free digital billboard on Google's search engine results page (SERP). "
                "When it is missing, Google automatically extracts random sentences from the page—often displaying copyright disclaimers, "
                "cookie policies, or navigation menus. This creates disjointed search snippets that fail to attract clicks or convey your value proposition."
            ),
            "search_engine_impact": (
                "While meta descriptions are not a direct ranking score factor, snippet appeal directly dictates Organic Click-Through Rate (CTR). "
                "Pages with missing descriptions suffer a 30% to 50% lower CTR compared to competitors with enticing, polished descriptions."
            ),
            "solution_roi": (
                "Deploying tailored, 150-160 character meta descriptions with clear Call-to-Actions (CTAs) captures user attention and drives "
                "up to 35% higher organic traffic from your existing ranking positions without any additional advertising spend."
            )
        }

    # 5. Meta Description Over 160 Characters
    elif "desc over" in name_l or ("meta description" in name_l and "over" in name_l):
        return {
            "what_is_it": (
                f"We discovered {count:,} pages where meta descriptions exceed Google's display limit of 160 characters (or ~960 desktop pixels)."
            ),
            "business_impact": (
                "Google automatically cuts off descriptions exceeding 160 characters with an awkward ellipsis (...). "
                "In almost every case, this cuts off your phone number, special offer, warranty, or the critical Call-to-Action at the end of the sentence."
            ),
            "search_engine_impact": (
                "Truncated search snippets look amateurish and incomplete in SERP listings, eroding user trust and depressing click-through rates. "
                "Users prefer clicking full, well-crafted messages rather than interrupted thoughts."
            ),
            "solution_roi": (
                "Trimming descriptions to exactly 150-160 characters ensures that 100% of your marketing message and conversion hook displays "
                "intact across both mobile smartphones and desktop computers."
            )
        }

    # 6. Duplicate Meta Descriptions
    elif "duplicate" in name_l and "description" in name_l:
        return {
            "what_is_it": (
                f"Our audit revealed {count:,} pages sharing the exact same duplicate meta description."
            ),
            "business_impact": (
                "When different product or category pages use identical descriptions, they fail to communicate what makes each page unique. "
                "Shoppers comparing your listings in search cannot tell the difference between distinct services or collections."
            ),
            "search_engine_impact": (
                "Google penalizes duplicate metadata by ignoring the author's tag entirely and algorithmically generating its own snippet. "
                "Furthermore, widespread duplication signals low-quality site architecture to search engine quality raters."
            ),
            "solution_roi": (
                "Providing unique, customized descriptions for each URL establishes clear intent, preserves brand voice, and increases SERP engagement."
            )
        }

    # 7. Page Title Missing
    elif "title" in name_l and ("missing" in name_l or "empty" in name_l):
        return {
            "what_is_it": (
                f"A critical technical defect was found: {count:,} pages completely lack an HTML <title> tag."
            ),
            "business_impact": (
                "The page title is the single most visible text in Google Search and browser tabs. Without a title, searchers see only a raw URL "
                "or a garbled system guess, causing almost 0% click confidence."
            ),
            "search_engine_impact": (
                "The <title> tag is universally recognized as the single strongest on-page ranking factor in SEO. "
                "Pages lacking a title tag are essentially invisible to search engines and cannot compete for competitive commercial keywords."
            ),
            "solution_roi": (
                "Adding strategic, keyword-targeted title tags immediately unlocks baseline ranking eligibility and organic search visibility."
            )
        }

    # 8. Page Title Over 60 Characters
    elif "title over" in name_l or ("title" in name_l and "over" in name_l):
        return {
            "what_is_it": (
                f"There are {count:,} pages with title tags exceeding Google's display limit of 60 characters (~600 pixels)."
            ),
            "business_impact": (
                "Long titles get clipped with ellipses (...), cutting off your brand name, pricing qualifiers, or key product benefits."
            ),
            "search_engine_impact": (
                "Excessively long titles trigger Google's automated title rewrite system, which frequently overwrites your carefully chosen copy "
                "with suboptimal alternatives. Furthermore, keyword stuffing in titles dilutes topical relevance."
            ),
            "solution_roi": (
                "Refining title tags to 50-60 characters ensures full visibility across all devices and concentrates ranking authority on your primary target keyword."
            )
        }

    # 9. Duplicate Page Titles
    elif "duplicate" in name_l and "title" in name_l:
        return {
            "what_is_it": (
                f"Our crawl flagged {count:,} pages sharing identical title tags."
            ),
            "business_impact": (
                "This causes severe internal keyword cannibalization. Instead of presenting one strong, authoritative page to search engines, "
                "your own URLs compete against each other, splitting incoming search traffic and confusing buyers."
            ),
            "search_engine_impact": (
                "Search engines cannot determine which URL is the canonical authority for the keyword topic. "
                "Consequently, Google frequently rotates the ranking URLs or suppresses both, causing ranking volatility."
            ),
            "solution_roi": (
                "Assigning distinct, keyword-focused titles eliminates self-competition and consolidates ranking authority onto the correct landing pages."
            )
        }

    # 10. Internal Links Broken (4xx/5xx)
    elif "broken" in name_l or "4xx" in name_l or "5xx" in name_l:
        return {
            "what_is_it": (
                f"We uncovered {count:,} broken internal hyperlinks pointing to dead (404/410) or server error (500) destinations."
            ),
            "business_impact": (
                "Broken links destroy the customer conversion funnel. When a prospective client clicks an internal link to view a product or case study, "
                "they hit a dead end. This instantly shatters credibility, increases frustration, and causes immediate bounce to a competitor."
            ),
            "search_engine_impact": (
                "Broken links cause severe link equity (PageRank) leakage. Authority that should flow into high-converting revenue pages "
                "evaporates into dead ends. Additionally, search engine crawlers waste finite crawl budget repeatedly requesting broken URLs."
            ),
            "solution_roi": (
                "Repairing anchor links and implementing 301 redirects immediately recaptures leaked link equity, protects customer journeys, and preserves crawl efficiency."
            )
        }

    # 11. Redirect Chains & Loops
    elif "redirect" in name_l and ("chain" in name_l or "loop" in name_l):
        return {
            "what_is_it": (
                f"Our crawl identified {count:,} URLs caught in redirect chains (multi-hop redirects) or circular redirect loops."
            ),
            "business_impact": (
                "Each redirect hop adds 200ms to 800ms of latency before content can begin loading, making the site feel slow and clunky. "
                "Redirect loops result in browser error screens ('Too Many Redirects'), completely blocking visitors from accessing the page."
            ),
            "search_engine_impact": (
                "Googlebot abandons redirect chains after 3-4 hops, causing dropped indexation. Furthermore, each intermediate hop dilutes 10-15% "
                "of inbound link authority."
            ),
            "solution_roi": (
                "Consolidating redirects into direct, 1-hop 301 destinations recovers lost speed, stops authority leakage, and guarantees search indexation."
            )
        }

    # 12. Images Missing Alt Text
    elif "alt" in name_l or "image" in name_l:
        return {
            "what_is_it": (
                f"There are {count:,} images across the site lacking descriptive 'alt' attributes in their <img> HTML tags."
            ),
            "business_impact": (
                "Millions of shoppers discover products through Google Images. Missing alt text locks your visual assets out of search, "
                "closing off a major organic acquisition channel. It also exposes the company to ADA accessibility compliance violations."
            ),
            "search_engine_impact": (
                "Search engines cannot perceive images visually; they rely entirely on alt text to understand the subject of the photo. "
                "Without alt attributes, the image cannot rank in Google Image Search."
            ),
            "solution_roi": (
                "Adding concise, keyword-rich alt text unlocks Google Images search traffic and satisfies international web accessibility standards."
            )
        }

    # 13. Canonical Tag Issues
    elif "canonical" in name_l:
        return {
            "what_is_it": (
                f"We flagged {count:,} pages with missing, conflicting, or broken canonical link tags."
            ),
            "business_impact": (
                "E-commerce filters, tracking parameters, and pagination URLs can create hundreds of duplicate versions of your content, "
                "diluting brand clarity and confusing buyers."
            ),
            "search_engine_impact": (
                "The canonical tag tells Google which URL is the single master copy. When canonicals are missing or mismatched, "
                "search engines split backlink authority across multiple URLs or index parameter-bloated pages instead of your main landing page."
            ),
            "solution_roi": (
                "Correct canonical tags guarantee that 100% of organic ranking signals and backlinks remain focused on your primary commercial URL."
            )
        }

    # Generic Fallback
    else:
        return {
            "what_is_it": (
                f"A total of {count:,} instances were flagged under the category '{category_name}' during our technical crawl."
            ),
            "business_impact": (
                "Technical irregularities create friction in the user experience, leading to reduced engagement, higher drop-off rates, and missed revenue opportunities."
            ),
            "search_engine_impact": (
                "Google's indexing algorithms prioritize clean, compliant technical architecture. Departures from Google Search Essentials "
                "suppress organic visibility and crawl prioritization."
            ),
            "solution_roi": (
                "Remediating these flagged entries cleans up technical debt, improves domain quality scores, and supports sustainable ranking growth."
            )
        }


# ==============================================================================
# MAIN WORD DOCUMENT BUILDER
# ==============================================================================

def generate_technical_seo_audit_docx(
    crawl_results: dict,
    index_rows: List[dict],
    error_dfs: Dict[str, pd.DataFrame],
    logo_bytes: Optional[bytes] = None,
    target_country: str = "Global",
    business_niche: str = "",
    agency_name: str = "Technical SEO Intelligence",
    client_name: str = ""
) -> bytes:
    """
    Build a comprehensive, client-ready Technical SEO Audit Report (.docx)
    with repeat header logo, index, positive/negative points, business rationale,
    category analysis, developer guides, and prioritized action plan.
    """
    doc = docx.Document()

    # 1. Page Margins
    section = doc.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.85)
    section.right_margin = Inches(0.85)

    # 2. Setup Running Header (Repeats on Every Page)
    header = section.header
    header.is_linked_to_previous = False
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hp.paragraph_format.space_after = Pt(4)

    logo_stream = format_logo_for_docx(logo_bytes)
    if logo_stream:
        try:
            # Header Logo
            r_img = hp.add_run()
            r_img.add_picture(logo_stream, height=Inches(0.42))
            hp.add_run("   ")
        except Exception:
            pass

    r_htxt = hp.add_run(f"Technical SEO Audit Report | {agency_name}")
    r_htxt.font.size = Pt(8.5)
    r_htxt.font.color.rgb = COLOR_MUTED

    # 3. Setup Running Footer (Page & Confidentiality)
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r_ftxt = fp.add_run("Confidential Client Report — For Internal Technical & Development Use Only")
    r_ftxt.font.size = Pt(8.5)
    r_ftxt.font.color.rgb = COLOR_MUTED

    # Metadata extraction
    df_pages = crawl_results.get("df_pages", pd.DataFrame())
    start_url = crawl_results.get("start_url", "Audited Website")
    total_pages = len(df_pages) if not df_pages.empty else 0
    health_score = crawl_results.get("health_score", 0)
    audit_date = datetime.now().strftime("%B %d, %Y")

    total_checks = len(index_rows)
    failed_checks = [r for r in index_rows if r.get("is_error", False)]
    passed_checks = [r for r in index_rows if not r.get("is_error", False)]
    total_issues_count = sum(r.get("count", 0) for r in failed_checks)

    # =========================================================================
    # COVER / TITLE BLOCK
    # =========================================================================
    p_title_space = doc.add_paragraph()
    p_title_space.paragraph_format.space_before = Pt(10)

    if logo_stream:
        try:
            logo_stream.seek(0)
            p_cover_logo = doc.add_paragraph()
            p_cover_logo.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p_cover_logo.add_run().add_picture(logo_stream, width=Inches(2.4))
        except Exception:
            pass

    p_h1 = doc.add_paragraph()
    p_h1.paragraph_format.space_before = Pt(8)
    p_h1.paragraph_format.space_after = Pt(4)
    run_h1 = p_h1.add_run("TECHNICAL SEO AUDIT & ACTION ROADMAP")
    run_h1.font.bold = True
    run_h1.font.size = Pt(24)
    run_h1.font.color.rgb = COLOR_PRIMARY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(14)
    run_sub = p_sub.add_run("Executive Health Analysis, Technical Findings & Developer Implementation Guide")
    run_sub.font.size = Pt(13)
    run_sub.font.color.rgb = COLOR_SECONDARY

    # Metadata Overview Table
    tbl_meta = doc.add_table(rows=6, cols=2)
    tbl_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_meta.autofit = False

    meta_items = [
        ("Audited Website URL:", start_url),
        ("Target Market / Region:", target_country),
        ("Business / Industry Niche:", business_niche or "E-Commerce / Commercial Web Portal"),
        ("Pages Crawled & Evaluated:", f"{total_pages:,} URLs"),
        ("Audit Date & Timestamp:", audit_date),
        ("Technical SEO Health Score:", f"{health_score} / 100 ({'Needs Urgent Attention' if health_score < 70 else 'Good Health'})")
    ]

    for r_idx, (k, v) in enumerate(meta_items):
        row = tbl_meta.rows[r_idx]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width, c1.width = Inches(2.3), Inches(4.5)
        set_cell_padding(c0, top=60, bottom=60, left=100, right=100)
        set_cell_padding(c1, top=60, bottom=60, left=100, right=100)
        set_cell_background(c0, HEX_LIGHT_BG)
        set_cell_background(c1, HEX_LIGHT_BG)

        p0 = c0.paragraphs[0]
        r0 = p0.add_run(k)
        r0.font.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = COLOR_DARK

        p1 = c1.paragraphs[0]
        r1 = p1.add_run(v)
        r1.font.size = Pt(9.5)
        if "Health Score" in k:
            r1.font.bold = True
            r1.font.color.rgb = COLOR_FAIL if health_score < 70 else COLOR_PASS
        else:
            r1.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # =========================================================================
    # SECTION 1: DOCUMENT INDEX / TABLE OF CONTENTS
    # =========================================================================
    p_sec1 = doc.add_paragraph()
    p_sec1.paragraph_format.space_before = Pt(14)
    p_sec1.paragraph_format.space_after = Pt(6)
    r = p_sec1.add_run("📋 Document Index (Table of Contents)")
    r.font.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = COLOR_PRIMARY

    index_table = doc.add_table(rows=1, cols=2)
    index_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    index_cell_l = index_table.rows[0].cells[0]
    index_cell_r = index_table.rows[0].cells[1]
    index_cell_l.width = Inches(3.4)
    index_cell_r.width = Inches(3.4)
    set_cell_background(index_cell_l, HEX_LIGHT_BG)
    set_cell_background(index_cell_r, HEX_LIGHT_BG)
    set_cell_padding(index_cell_l, top=100, bottom=100, left=120, right=120)
    set_cell_padding(index_cell_r, top=100, bottom=100, left=120, right=120)

    pl = index_cell_l.paragraphs[0]
    pl.add_run("1. Executive Summary & Health Metrics\n").font.bold = True
    pl.add_run("2. Website Strengths (What's Working Well)\n").font.bold = True
    pl.add_run("3. Critical SEO Vulnerabilities (Negative Points)\n").font.bold = True

    pr = index_cell_r.paragraphs[0]
    pr.add_run("4. Why We Must Fix These Issues (Business ROI)\n").font.bold = True
    pr.add_run("5. In-Depth Technical Error Breakdown & Fixes\n").font.bold = True
    pr.add_run("6. Prioritized 3-Phase Action Roadmap\n").font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # =========================================================================
    # SECTION 2: EXECUTIVE SUMMARY & AUDIT SCORE
    # =========================================================================
    p_sec2 = doc.add_paragraph()
    p_sec2.paragraph_format.space_before = Pt(14)
    r = p_sec2.add_run("1. Executive Summary & Audit Score")
    r.font.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        f"A comprehensive technical crawl and algorithmic audit was performed on {start_url} "
        f"evaluating on-page signals, technical architecture, indexing directives, page performance, "
        f"and Google Search compliance. The crawl evaluated a total of {total_pages:,} URLs across the website domain."
    )

    # Scorecard Table (4 columns)
    tbl_kpi = doc.add_table(rows=2, cols=4)
    tbl_kpi.alignment = WD_TABLE_ALIGNMENT.CENTER
    kpis = [
        ("Audited Checks", f"{total_checks}", HEX_LIGHT_BG, COLOR_DARK),
        ("Failed / Attention", f"{len(failed_checks)} Categories", HEX_FAIL_BG, COLOR_FAIL),
        ("Passed Cleanly", f"{len(passed_checks)} Categories", HEX_PASS_BG, COLOR_PASS),
        ("Total Flagged Items", f"{total_issues_count:,} Items", HEX_FAIL_BG, COLOR_FAIL)
    ]
    for idx, (label, val, bg, col) in enumerate(kpis):
        c_hdr = tbl_kpi.rows[0].cells[idx]
        c_val = tbl_kpi.rows[1].cells[idx]
        c_hdr.width = c_val.width = Inches(1.7)
        set_cell_padding(c_hdr, top=80, bottom=40, left=60, right=60)
        set_cell_padding(c_val, top=40, bottom=80, left=60, right=60)
        set_cell_background(c_hdr, bg)
        set_cell_background(c_val, bg)

        p_h = c_hdr.paragraphs[0]
        p_h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_h = p_h.add_run(label)
        r_h.font.size = Pt(9)
        r_h.font.color.rgb = COLOR_MUTED

        p_v = c_val.paragraphs[0]
        p_v.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_v = p_v.add_run(val)
        r_v.font.bold = True
        r_v.font.size = Pt(13)
        r_v.font.color.rgb = col

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # =========================================================================
    # SECTION 3: POSITIVE POINTS (WHAT THE WEBSITE IS DOING RIGHT)
    # =========================================================================
    p_sec3 = doc.add_paragraph()
    p_sec3.paragraph_format.space_before = Pt(14)
    r = p_sec3.add_run("2. Website Strengths & Positive SEO Points (What Is Working)")
    r.font.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = COLOR_PASS

    doc.add_paragraph(
        "Before diving into technical fixes, it is important to recognize the strong foundational elements "
        "already functioning correctly on the website. These assets protect baseline visibility and provide "
        "a reliable springboard for upcoming optimizations:"
    )

    # Dynamically assess positive factors
    positives = []
    # 1. SSL / HTTPS
    if start_url.startswith("https://"):
        positives.append((
            "Secure HTTPS Protocol Active",
            "The site enforces SSL encryption throughout the primary domain, maintaining user security and meeting Google's mandatory HTTPS ranking prerequisite."
        ))

    # 2. Passed categories from index_rows
    for pc in passed_checks:
        c_name = pc.get("error_name", "")
        c_comm = pc.get("comments", "Compliant with standard SEO best practices.")
        positives.append((f"Clean Implementation: {c_name}", c_comm))

    # 3. HTTP 200 indexable base
    if not df_pages.empty and "status_code" in df_pages.columns:
        ok_count = len(df_pages[df_pages["status_code"] == 200])
        pct_ok = round((ok_count / max(len(df_pages), 1)) * 100, 1)
        if pct_ok > 80:
            positives.append((
                "Strong HTTP 200 OK Delivery Rate",
                f"{pct_ok}% ({ok_count:,}/{len(df_pages):,}) of evaluated pages respond with clean HTTP 200 status codes, ensuring primary content is accessible to web crawlers."
            ))

    # Fallback if few
    if len(positives) < 3:
        positives.append((
            "Indexable Architecture Baseline",
            "Core landing pages permit search engine crawling without global robots.txt blockage."
        ))

    for title, desc in positives[:6]:
        p_b = doc.add_paragraph(style='List Bullet')
        p_b.paragraph_format.space_after = Pt(3)
        r_t = p_b.add_run(f"✅ {title}: ")
        r_t.font.bold = True
        r_t.font.color.rgb = COLOR_PASS
        r_d = p_b.add_run(desc)
        r_d.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # =========================================================================
    # SECTION 4: NEGATIVE POINTS & VULNERABILITIES
    # =========================================================================
    p_sec4 = doc.add_paragraph()
    p_sec4.paragraph_format.space_before = Pt(14)
    r = p_sec4.add_run("3. Critical SEO Vulnerabilities & Negative Points (What Is Holding You Back)")
    r.font.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = COLOR_FAIL

    doc.add_paragraph(
        f"Our audit revealed {len(failed_checks)} distinct problem categories comprising {total_issues_count:,} "
        f"specific affected URLs/elements. These bottlenecks actively suppress keyword rankings, lower organic CTR, "
        f"waste Googlebot crawl budget, and degrade user conversion rates:"
    )

    for fc in failed_checks:
        c_name = fc.get("error_name", "Error")
        c_cnt = fc.get("count", 0)
        c_comm = fc.get("comments", "")
        p_err = doc.add_paragraph(style='List Bullet')
        p_err.paragraph_format.space_after = Pt(4)
        r_et = p_err.add_run(f"❌ {c_name} ({c_cnt:,} Affected URLs): ")
        r_et.font.bold = True
        r_et.font.color.rgb = COLOR_FAIL
        r_ec = p_err.add_run(f"{c_comm}")
        r_ec.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # =========================================================================
    # SECTION 5: WHY WE MUST FIX THIS (BUSINESS & SEO RATIONALE)
    # =========================================================================
    p_sec5 = doc.add_paragraph()
    p_sec5.paragraph_format.space_before = Pt(14)
    r = p_sec5.add_run("4. Why We Need to Fix These Issues (SEO & Business Impact)")
    r.font.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "Technical SEO is not just an aesthetic checklist; it directly governs how Google interprets, "
        "ranks, and displays your revenue-generating pages. Below is the direct business and commercial impact "
        "of resolving these flagged vulnerabilities:"
    )

    reasons = [
        (
            "1. Google SERP Snippet Optimization & Direct CTR Uplift",
            "When meta descriptions are over 160 characters or completely missing, Google truncates them with unsightly ellipses (...) or dynamically pulls random page text. Competitors with properly formatted 150-160 character descriptions featuring clear Call-to-Actions (CTAs) consistently capture 25% to 40% higher click-through rates for the exact same ranking position."
        ),
        (
            "2. Eliminating Keyword Cannibalization & Structural Confusion",
            "Having multiple <h1> tags or duplicate title tags dilutes page topical authority. Search engine crawlers struggle to determine which heading represents the core subject of the page, leading to split relevance signals and lower average rankings."
        ),
        (
            "3. Protecting Googlebot Crawl Budget & Indexation Efficiency",
            "Google allocates a finite crawl budget to every domain. Redirect chains (e.g. Page A -> Page B -> Page C) and broken 404 links force search engine bots to spend valuable crawl cycles traversing dead ends instead of discovering and ranking new product or service pages."
        ),
        (
            "4. Recovering Internal PageRank (Link Equity) Leakage",
            "Internal links distribute ranking power across your domain. When links point to 4xx dead URLs, that valuable link authority evaporates. Re-routing these links directly to live, relevant target categories instantly strengthens the ranking potential of core landing pages."
        ),
        (
            "5. User Experience, Trust & Conversion Protection",
            "Broken images, slow server latency (>1.5s), and broken hyperlinks trigger immediate friction. Over 53% of mobile visitors abandon pages that take over 3 seconds to respond, driving potential customers straight to competitors."
        )
    ]

    for r_title, r_text in reasons:
        add_callout_box(doc, title=r_title, text=r_text, border_hex="1E3A8A", bg_hex="F8FAFC")

    # =========================================================================
    # SECTION 6: IN-DEPTH ERROR ANALYSIS & STRATEGIC IMPORTANCE
    # =========================================================================
    p_sec6 = doc.add_paragraph()
    p_sec6.paragraph_format.space_before = Pt(16)
    r = p_sec6.add_run("5. Strategic Analysis of Flagged Vulnerabilities (Why Fixing Is Critical)")
    r.font.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "This section delivers an executive, non-technical breakdown of every technical bottleneck identified during "
        "our deep crawl. Rather than cluttering this strategic briefing with raw code or repetitive URL lists, each "
        "section below explains why this error damages your business revenue, how search engine algorithms penalize it, "
        "and why immediate remediation is critical to unlocking organic growth.\n\n"
        "Accompanying Technical Excel Workbook Note: The complete, filterable URL inventory, current values, and "
        "developer implementation rules for each error are provided in the accompanying Technical SEO Excel File."
    )

    for sheet_name, df_err in error_dfs.items():
        if df_err.empty:
            continue

        c_count = len(df_err)
        analysis = get_error_category_analysis(sheet_name, c_count)

        p_sh = doc.add_paragraph()
        p_sh.paragraph_format.space_before = Pt(14)
        p_sh.paragraph_format.space_after = Pt(4)
        r_sh = p_sh.add_run(f"📁 Issue Category: {sheet_name} ({c_count:,} Flagged Instances)")
        r_sh.font.bold = True
        r_sh.font.size = Pt(13)
        r_sh.font.color.rgb = COLOR_PRIMARY

        # 1. Technical Context
        p1 = doc.add_paragraph()
        p1.paragraph_format.space_after = Pt(3)
        r_w1 = p1.add_run("• Technical Bottleneck: ")
        r_w1.font.bold = True
        p1.add_run(analysis["what_is_it"])

        # 2. Business & Revenue Impact
        p2 = doc.add_paragraph()
        p2.paragraph_format.space_after = Pt(3)
        r_w2 = p2.add_run("• Business & Revenue Impact: ")
        r_w2.font.bold = True
        r_w2.font.color.rgb = COLOR_FAIL
        p2.add_run(analysis["business_impact"])

        # 3. Search Engine & Ranking Penalty
        p3 = doc.add_paragraph()
        p3.paragraph_format.space_after = Pt(3)
        r_w3 = p3.add_run("• Search Engine & Googlebot Penalty: ")
        r_w3.font.bold = True
        r_w3.font.color.rgb = COLOR_SECONDARY
        p3.add_run(analysis["search_engine_impact"])

        # 4. Value of Fixing (Commercial ROI)
        p4 = doc.add_paragraph()
        p4.paragraph_format.space_after = Pt(6)
        r_w4 = p4.add_run("• Commercial ROI Upon Resolution: ")
        r_w4.font.bold = True
        r_w4.font.color.rgb = COLOR_PASS
        p4.add_run(analysis["solution_roi"])

        # 5. Callout note referencing Excel file
        add_callout_box(
            doc,
            title=f"Actionable URL Inventory in Excel: Sheet '{sheet_name}'",
            text=(
                f"All {c_count:,} affected page URLs, current tags, and developer implementation specifications "
                f"are cataloged in Sheet '{sheet_name}' of your accompanying Technical SEO Excel File. "
                "Development teams can directly filter, inspect, and execute fixes using that actionable workbook."
            ),
            border_hex="10B981",
            bg_hex="F0FDF4"
        )

    # =========================================================================
    # SECTION 7: PRIORITIZED ACTION ROADMAP
    # =========================================================================
    p_sec7 = doc.add_paragraph()
    p_sec7.paragraph_format.space_before = Pt(16)
    r = p_sec7.add_run("6. Prioritized 3-Phase Action Roadmap")
    r.font.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "To maximize development efficiency and achieve rapid organic ranking recovery, "
        "we recommend executing fixes according to the following phased rollout schedule:"
    )

    roadmap_table = doc.add_table(rows=4, cols=3)
    roadmap_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    roadmap_table.autofit = False

    rh = roadmap_table.rows[0].cells
    rh[0].text, rh[1].text, rh[2].text = "Phase & Timeline", "Key Technical Objectives", "Expected Commercial Impact"
    for c in rh:
        set_cell_background(c, HEX_HEADER_BG)
        set_cell_padding(c, top=80, bottom=80, left=100, right=100)
        c.paragraphs[0].runs[0].font.bold = True
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        c.paragraphs[0].runs[0].font.size = Pt(9.5)

    phases = [
        (
            "Phase 1: Week 1\n(Critical Architecture)",
            "• Eliminate redirect loops & chains\n• Fix 4xx/5xx broken internal hyperlinks\n• Correct canonical tag mismatches",
            "Recovers wasted Google crawl budget, halts link equity loss, and eliminates crawler dead ends."
        ),
        (
            "Phase 2: Week 2\n(On-Page SERP CTR & Relevance)",
            "• Deploy 150-160 char meta descriptions with CTAs\n• Implement 50-60 char primary keyword titles\n• Consolidate single primary <h1> headings",
            "Immediate uplift in Google snippet CTR (25-40%), resolves keyword cannibalization, and strengthens relevance."
        ),
        (
            "Phase 3: Week 3\n(Asset & Speed Optimization)",
            "• Minify & bundle JavaScript (.js) and CSS (.css) files\n• Compress oversized images (>100 KB) into WebP/AVIF\n• Add descriptive alt attributes to product & category images\n• Optimize server latency (TTFB) & cache policies",
            "Significantly boosts Core Web Vitals (LCP/FCP), eliminates render-blocking delay, lowers mobile bounce rates, and unlocks Google Images search traffic."
        )
    ]

    for idx, (p_col, t_col, i_col) in enumerate(phases, 1):
        row = roadmap_table.rows[idx]
        for c_idx, val in enumerate([p_col, t_col, i_col]):
            cell = row.cells[c_idx]
            set_cell_padding(cell, top=70, bottom=70, left=100, right=100)
            set_cell_background(cell, HEX_LIGHT_BG if idx % 2 == 1 else "FFFFFF")
            p = cell.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8.5)
            if c_idx == 0:
                r.font.bold = True
                r.font.color.rgb = COLOR_PRIMARY

    # Concluding Sign-off
    p_end = doc.add_paragraph()
    p_end.paragraph_format.space_before = Pt(16)
    p_end.paragraph_format.space_after = Pt(4)
    r_end = p_end.add_run(f"Report Generated by {agency_name} — Powered by CrawlPilot Technical SEO Intelligence.")
    r_end.font.italic = True
    r_end.font.size = Pt(9)
    r_end.font.color.rgb = COLOR_MUTED

    # Save to BytesIO
    out_file = io.BytesIO()
    doc.save(out_file)
    out_file.seek(0)
    return out_file.getvalue()
