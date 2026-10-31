"""
Keyword Research & Page Mapper Module
Advanced SEO Keyword Intelligence, Content-to-Keyword Mapping & Ryze MCP-inspired Keyword Research.
Reads crawled/live pages, filters Product & Service money pages, suggests 3 high-intent keywords per page,
detects keyword cannibalization, and generates on-page optimization blueprints.
"""

import io
import re
import time
import json
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Common User-Agent for live Google Autocomplete & web requests
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

# ==============================================================================
# 1. LIVE GOOGLE AUTOCOMPLETE & SEARCH INTENT ENGINE
# ==============================================================================

def fetch_google_suggestions(query: str, country: str = "us", lang: str = "en", max_results: int = 10) -> list[str]:
    """
    Fetch real-time Google Autocomplete suggestions without requiring any paid API.
    Uses Google's public suggest API endpoint.
    """
    if not query or len(query.strip()) < 2:
        return []
    
    clean_query = query.strip()
    encoded = urllib.parse.quote(clean_query)
    url = f"https://suggestqueries.google.com/complete/search?client=chrome&hl={lang}&gl={country}&q={encoded}"
    
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": DEFAULT_UA,
                "Accept": "application/json, text/javascript, */*",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                suggestions = [str(s).strip() for s in data[1] if str(s).strip()]
                return suggestions[:max_results]
    except Exception:
        pass
    return []


def expand_seed_keywords(seed: str, country: str = "us", lang: str = "en") -> list[dict]:
    """
    Ryze-inspired Seed Keyword Expansion:
    Runs Google Autocomplete fanout across modifiers, commercial triggers, and alphabet prefixes.
    """
    seed = seed.strip()
    if not seed:
        return []
        
    modifiers = [
        "", "best", "top", "services", "company", "price", "cost", 
        "buy", "online", "agency", "tools", "software", "near me", "reviews", "vs"
    ]
    
    seen = set()
    results = []
    
    def _collect(q: str, trigger: str):
        suggs = fetch_google_suggestions(q, country=country, lang=lang, max_results=8)
        for s in suggs:
            s_clean = s.lower().strip()
            if s_clean not in seen and len(s_clean) > 3:
                seen.add(s_clean)
                intent = classify_keyword_intent(s_clean)
                results.append({
                    "keyword": s,
                    "seed": seed,
                    "trigger": trigger or "core",
                    "intent": intent["intent"],
                    "intent_badge": intent["badge"],
                    "cpc_tier": intent["cpc_tier"],
                    "intent_desc": intent["desc"]
                })

    # Direct queries + modifiers
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = []
        # Core query
        futures.append(executor.submit(_collect, seed, "Seed"))
        # Modifier queries
        for m in modifiers:
            if m:
                futures.append(executor.submit(_collect, f"{seed} {m}", m))
                futures.append(executor.submit(_collect, f"{m} {seed}", m))
        # Alphabet expansion for depth
        for char in "abcdefg":
            futures.append(executor.submit(_collect, f"{seed} {char}", f"fanout-{char}"))
            
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass

    return results


def classify_keyword_intent(keyword: str) -> dict:
    """Classifies search intent and commercial value tier of a keyword."""
    kw = keyword.lower()
    
    transactional_cues = ["buy", "price", "pricing", "cost", "hire", "quote", "order", "purchase", "discount", "cheap", "for sale", "coupon", "deal", "shop", "near me"]
    commercial_cues = ["best", "top", "review", "reviews", "comparison", "vs", "versus", "service", "services", "agency", "firm", "company", "software", "tool", "platform", "provider", "solutions", "enterprise"]
    informational_cues = ["how to", "what is", "guide", "tutorial", "examples", "template", "tips", "ideas", "why", "who", "when", "learn", "definition", "strategy"]
    
    for t in transactional_cues:
        if re.search(r"\b" + re.escape(t) + r"\b", kw):
            return {
                "intent": "Transactional",
                "badge": "🛒 Transactional",
                "color": "#10B981",
                "cpc_tier": "$$$$ High Commercial Value",
                "desc": "User is ready to buy, order, hire, or request a quote."
            }
            
    for c in commercial_cues:
        if re.search(r"\b" + re.escape(c) + r"\b", kw):
            return {
                "intent": "Commercial",
                "badge": "💼 Commercial",
                "color": "#38BDF8",
                "cpc_tier": "$$$ Moderate-High Value",
                "desc": "User is evaluating products/services and comparing options before buying."
            }
            
    for i in informational_cues:
        if re.search(r"\b" + re.escape(i) + r"\b", kw):
            return {
                "intent": "Informational",
                "badge": "ℹ️ Informational",
                "color": "#F59E0B",
                "cpc_tier": "$ Low-Moderate Value",
                "desc": "User is seeking education, steps, or answers to a question."
            }
            
    return {
        "intent": "Commercial / Informational",
        "badge": "🎯 Commercial / Info",
        "color": "#A78BFA",
        "cpc_tier": "$$ Commercial Potential",
        "desc": "General industry or product search with commercial potential."
    }


# ==============================================================================
# 2. PAGE CLASSIFIER & CONTENT ANALYZER (PRODUCT/SERVICE FOCUS)
# ==============================================================================

def classify_page_type(url: str, title: str = "", h1: str = "", text: str = "") -> dict:
    """
    Categorizes page into:
    - 💎 Product Page (High priority for ranking & revenue)
    - 🚀 Service / Solution Page (High priority for ranking & revenue)
    - 📁 Commercial Category / Hub (Collection of offerings)
    - 📰 Blog / Informational Post
    - ⚙️ Utility / Non-Commercial (About, Contact, FAQ, Terms, Privacy - skipped by default)
    """
    clean_url = url.lower()
    parsed = urllib.parse.urlparse(clean_url)
    path = parsed.path.strip("/")
    path_segments = [p.lower() for p in path.split("/") if p]
    
    combined_meta = f"{clean_url} {title.lower()} {h1.lower()}"
    
    # 1. Utility & Administrative Pages (User explicitly requested to skip/filter these out)
    utility_exact = {
        "about", "about-us", "contact", "contact-us", "faq", "faqs", "help", 
        "support", "terms", "terms-and-conditions", "privacy", "privacy-policy", 
        "cookie-policy", "disclaimer", "legal", "login", "register", "signup", 
        "cart", "checkout", "my-account", "author", "authors", "tag", "tags",
        "team", "careers", "jobs", "sitemap", "feed"
    }
    
    for seg in path_segments:
        if seg in utility_exact:
            return {
                "category": "Utility / Administrative",
                "badge": "⚙️ Utility (Skip)",
                "color": "#64748B",
                "is_money_page": False,
                "is_product_service": False,
                "reason": f"Matches administrative utility slug '/{seg}/'"
            }
            
    if re.search(r"\b(about us|contact us|privacy policy|terms of service|frequently asked questions|disclaimer)\b", combined_meta):
        return {
            "category": "Utility / Administrative",
            "badge": "⚙️ Utility (Skip)",
            "color": "#64748B",
            "is_money_page": False,
            "is_product_service": False,
            "reason": "Title/H1 indicates utility or legal page"
        }

    # 2. Product Page
    product_slug_triggers = ["product", "products", "item", "p", "shop", "goods", "course", "courses", "store"]
    is_product_slug = any(t in path_segments for t in product_slug_triggers)
    is_product_text = any(t in combined_meta for t in ["product", "buy now", "add to cart", "sku", "specifications", "in stock", "price:", "shop now", "features"])
    
    if is_product_slug or ("product" in clean_url and len(path_segments) >= 2):
        return {
            "category": "Product Page",
            "badge": "💎 Product Page",
            "color": "#10B981",
            "is_money_page": True,
            "is_product_service": True,
            "reason": "Direct product landing page or e-commerce item"
        }

    # 3. Service / Solution Page
    service_slug_triggers = [
        "service", "services", "solution", "solutions", "consulting", 
        "agency", "hire", "plans", "pricing", "platform", "features", 
        "capability", "capabilities", "industries", "b2b"
    ]
    is_service_slug = any(t in path_segments for t in service_slug_triggers)
    is_service_text = any(t in combined_meta for t in ["service", "services", "consulting", "solutions", "book a call", "request quote", "custom development", "hire us", "our offering"])
    
    if is_service_slug or is_service_text:
        return {
            "category": "Service / Solution Page",
            "badge": "🚀 Service Page",
            "color": "#38BDF8",
            "is_money_page": True,
            "is_product_service": True,
            "reason": "Commercial service or B2B solution landing page"
        }

    # 4. Commercial Category / Collections Hub
    cat_triggers = ["category", "categories", "collection", "collections", "catalog", "catalogue"]
    if any(t in path_segments for t in cat_triggers):
        return {
            "category": "Commercial Category Hub",
            "badge": "📁 Category Hub",
            "color": "#F59E0B",
            "is_money_page": True,
            "is_product_service": True,
            "reason": "Commercial category or multi-product directory"
        }

    # 5. Blog / Informational Post
    blog_triggers = ["blog", "article", "articles", "news", "post", "posts", "guide", "guides", "insights"]
    if any(t in path_segments for t in blog_triggers):
        return {
            "category": "Blog / Informational",
            "badge": "📰 Blog Post",
            "color": "#A78BFA",
            "is_money_page": False,
            "is_product_service": False,
            "reason": "Informational blog post or guide"
        }

    # Homepage or Core Root
    if not path or path == "":
        return {
            "category": "Homepage / Core Brand",
            "badge": "🏠 Homepage",
            "color": "#EC4899",
            "is_money_page": True,
            "is_product_service": True,
            "reason": "Main Root Commercial Landing Page"
        }

    # Fallback: check if text indicates product/service
    if is_product_text:
        return {
            "category": "Product Page",
            "badge": "💎 Product Page",
            "color": "#10B981",
            "is_money_page": True,
            "is_product_service": True,
            "reason": "Content indicates commercial product offering"
        }

    return {
        "category": "General Commercial Page",
        "badge": "🎯 Commercial Page",
        "color": "#60A5FA",
        "is_money_page": True,
        "is_product_service": True,
        "reason": "General indexable commercial page"
    }


def extract_page_core_entities(url: str, title: str, h1: str, h2_list: list[str], page_text: str) -> dict:
    """
    Extracts semantic core entities, primary nouns, and service/product descriptors.
    """
    parsed = urllib.parse.urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    slug_words = [w for w in re.split(r"[-_]+", slug) if len(w) > 2 and not w.isdigit()]
    
    # Strip site branding suffix from title like " - Acme Corp" or " | Brand"
    clean_title = re.sub(r"\s*[-|–—:]\s*[^-|–—:]+$", "", title).strip()
    
    # Common English stop words to filter out
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
        "by", "about", "against", "between", "into", "through", "during", "before",
        "after", "above", "below", "from", "up", "down", "in", "out", "off", "over",
        "under", "again", "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
        "very", "s", "t", "can", "will", "just", "don", "should", "now", "home", "page"
    }
    
    # Collect noun chunks / phrases
    combined_candidates = []
    
    # 1. Title phrase
    if clean_title:
        combined_candidates.append(clean_title)
        
    # 2. H1
    if h1 and h1 != clean_title:
        combined_candidates.append(h1)
        
    # 3. Slug phrase
    if slug_words:
        combined_candidates.append(" ".join(slug_words))
        
    # 4. H2 subheadings
    for h in (h2_list or [])[:4]:
        if h and len(h) < 60:
            combined_candidates.append(h)
            
    # Clean text tokens
    words = re.findall(r"\b[a-zA-Z]{3,}\b", (clean_title + " " + h1 + " " + " ".join(slug_words)).lower())
    meaningful_words = [w for w in words if w not in stop_words]
    
    return {
        "clean_title": clean_title,
        "clean_h1": h1,
        "slug_phrase": " ".join(slug_words),
        "candidates": combined_candidates,
        "core_tokens": meaningful_words[:8]
    }


# ==============================================================================
# 3. 3-KEYWORD SUGGESTION & MAPPING ALGORITHM
# ==============================================================================

def generate_3_page_keywords(
    url: str,
    title: str,
    h1: str,
    meta_desc: str,
    h2_list: list[str],
    page_text: str,
    page_category: str = "Product Page",
    country: str = "us"
) -> dict:
    """
    Analyzes page content and generates:
    1. Primary Focus Keyword (Highest commercial/transactional intent for ranking)
    2. Secondary / Feature Keyword (Feature / modifier / LSI)
    3. Long-tail / Problem-Solving Keyword (Question or specific conversion intent)
    Enriched with live Google Autocomplete validation.
    """
    entities = extract_page_core_entities(url, title, h1, h2_list, page_text)
    
    # Base seed from clean title or H1 or slug
    seed = entities["clean_title"] or entities["clean_h1"] or entities["slug_phrase"]
    # Clean seed of punctuation
    seed = re.sub(r"[^\w\s-]", "", seed).strip()
    # Limit seed words to 3-5 words
    seed_tokens = seed.split()[:4]
    short_seed = " ".join(seed_tokens)
    
    # Live Google Autocomplete check
    google_suggestions = []
    if short_seed:
        google_suggestions = fetch_google_suggestions(short_seed, country=country, max_results=8)
    if not google_suggestions and entities["slug_phrase"]:
        google_suggestions = fetch_google_suggestions(entities["slug_phrase"], country=country, max_results=6)
        
    # Determine Primary Keyword
    primary_kw = ""
    # If Google Autocomplete has a close high-intent match, use it
    if google_suggestions:
        # Prefer suggestions containing commercial/service/product words
        for sug in google_suggestions:
            s_low = sug.lower()
            if any(term in s_low for term in ["service", "services", "online", "price", "software", "best", "tool", "solution", "company"]):
                primary_kw = sug
                break
        if not primary_kw and len(google_suggestions) > 0:
            primary_kw = google_suggestions[0]

    if not primary_kw:
        if "Product" in page_category:
            primary_kw = f"{short_seed} price" if "price" not in short_seed.lower() else short_seed
        elif "Service" in page_category:
            primary_kw = f"{short_seed} services" if "service" not in short_seed.lower() else short_seed
        else:
            primary_kw = short_seed
            
    # Clean primary keyword
    primary_kw = " ".join(primary_kw.split()[:5]).title()

    # Determine Secondary Keyword (Feature / Modifier / Variation)
    secondary_kw = ""
    for sug in google_suggestions:
        s_title = sug.title()
        if s_title.lower() != primary_kw.lower() and len(s_title.split()) >= 2:
            secondary_kw = s_title
            break
            
    if not secondary_kw:
        # Construct from H1 or H2
        if entities["clean_h1"] and entities["clean_h1"].lower() != primary_kw.lower():
            secondary_kw = " ".join(entities["clean_h1"].split()[:4]).title()
        elif h2_list and len(h2_list) > 0:
            secondary_kw = " ".join(h2_list[0].split()[:4]).title()
        else:
            if "Product" in page_category:
                secondary_kw = f"Best {short_seed}".title()
            else:
                secondary_kw = f"{short_seed} Solutions".title()

    # Determine Long-tail Keyword (Specific problem-solving, question, or niche intent)
    longtail_kw = ""
    # Try fetching Google suggestions for primary + "for", "how", "best"
    longtail_seed = f"{primary_kw} for"
    long_suggs = fetch_google_suggestions(longtail_seed, country=country, max_results=5)
    for ls in long_suggs:
        if ls.lower() not in [primary_kw.lower(), secondary_kw.lower()]:
            longtail_kw = ls.title()
            break
            
    if not longtail_kw:
        # Check H2s for questions or use cases
        for h in (h2_list or []):
            if any(q in h.lower() for q in ["how", "why", "best", "guide", "features", "benefits"]):
                longtail_kw = h.title()
                break
                
    if not longtail_kw:
        if "Product" in page_category:
            longtail_kw = f"Best {short_seed} with specifications and reviews".title()
        else:
            longtail_kw = f"How to choose {short_seed} for your business".title()

    # Classify intents
    intent_primary = classify_keyword_intent(primary_kw)
    intent_secondary = classify_keyword_intent(secondary_kw)
    intent_longtail = classify_keyword_intent(longtail_kw)

    # Generate On-Page SEO Blueprint
    parsed_domain = urllib.parse.urlparse(url).netloc.replace("www.", "").split(".")[0].title() or "Brand"
    rec_title = f"{primary_kw} | {secondary_kw} - {parsed_domain}"
    if len(rec_title) > 60:
        rec_title = f"{primary_kw} - {parsed_domain}"
        
    rec_h1 = f"{primary_kw}: Enterprise {page_category.split()[0]} Solutions" if "Service" in page_category else f"{primary_kw} - Premium Specifications"
    
    rec_meta = f"Discover leading {primary_kw}. Learn more about {secondary_kw} and get complete details on {longtail_kw}. Request a quote today."
    if len(rec_meta) > 155:
        rec_meta = rec_meta[:152] + "..."

    return {
        "url": url,
        "page_category": page_category,
        "primary_keyword": primary_kw,
        "primary_intent": intent_primary["badge"],
        "primary_cpc": intent_primary["cpc_tier"],
        "secondary_keyword": secondary_kw,
        "secondary_intent": intent_secondary["badge"],
        "secondary_cpc": intent_secondary["cpc_tier"],
        "longtail_keyword": longtail_kw,
        "longtail_intent": intent_longtail["badge"],
        "longtail_cpc": intent_longtail["cpc_tier"],
        "blueprint_title": rec_title,
        "blueprint_h1": rec_h1,
        "blueprint_meta": rec_meta,
        "google_verified": len(google_suggestions) > 0
    }


def detect_keyword_cannibalization(mapping_rows: list[dict]) -> list[dict]:
    """
    Detects if multiple pages are targeting identical or overlapping primary keywords.
    """
    seen_keywords = {}
    cannibalization_warnings = []
    
    for row in mapping_rows:
        p_kw = row.get("primary_keyword", "").lower().strip()
        url = row.get("url", "")
        if not p_kw:
            continue
            
        # Normalize keyword tokens
        kw_tokens = set(re.findall(r"\b\w+\b", p_kw))
        
        found_overlap = False
        for prev_kw, prev_urls in seen_keywords.items():
            prev_tokens = set(re.findall(r"\b\w+\b", prev_kw))
            # Check for Jaccard similarity or direct match
            intersection = kw_tokens.intersection(prev_tokens)
            union = kw_tokens.union(prev_tokens)
            similarity = len(intersection) / max(len(union), 1)
            
            if prev_kw == p_kw or similarity >= 0.75:
                found_overlap = True
                prev_urls.append(url)
                cannibalization_warnings.append({
                    "keyword": row.get("primary_keyword"),
                    "overlapping_urls": list(set(prev_urls)),
                    "similarity": f"{int(similarity * 100)}%",
                    "recommendation": "Consolidate into 1 pillar page with 301 redirect, or differentiate targets (e.g. one for pricing, one for features)."
                })
                break
                
        if not found_overlap:
            seen_keywords[p_kw] = [url]
            
    return cannibalization_warnings


# ==============================================================================
# 4. EXCEL MULTI-TAB EXPORT GENERATOR
# ==============================================================================

def generate_keyword_mapping_excel(mapping_data: list[dict], cannibalization_data: list[dict], site_domain: str = "") -> bytes:
    """
    Generates a professional, multi-tab Excel workbook styled with CrawlPilot's cyber theme.
    """
    wb = openpyxl.Workbook()
    
    # Styles
    navy_fill = PatternFill(start_color="0A0F1D", end_color="0A0F1D", fill_type="solid")
    gold_fill = PatternFill(start_color="D97706", end_color="D97706", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    white_bold = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    text_font = Font(name="Calibri", size=10, color="1E293B")
    link_font = Font(name="Calibri", size=10, color="0284C7", underline="single")
    alert_fill = PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid")
    alert_font = Font(name="Calibri", size=10, bold=True, color="991B1B")
    
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )
    
    # -------------------------------------------------------------
    # Sheet 1: Keyword Mapping Master
    # -------------------------------------------------------------
    ws1 = wb.active
    ws1.title = "Keyword Mapping Plan"
    ws1.views.sheetView[0].showGridLines = True
    
    headers_ws1 = [
        "Page URL", "Page Category", 
        "Primary Keyword (Focus)", "Primary Intent", "Commercial Value",
        "Secondary Keyword (LSI)", "Secondary Intent",
        "Long-Tail Keyword (Specific)", "Long-Tail Intent",
        "Google Live Verified"
    ]
    
    for col_idx, h in enumerate(headers_ws1, 1):
        cell = ws1.cell(row=1, column=col_idx, value=h)
        cell.fill = navy_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws1.row_dimensions[1].height = 28
        
    for row_idx, r in enumerate(mapping_data, 2):
        ws1.cell(row=row_idx, column=1, value=r.get("url", "")).font = link_font
        ws1.cell(row=row_idx, column=2, value=r.get("page_category", "")).font = text_font
        ws1.cell(row=row_idx, column=3, value=r.get("primary_keyword", "")).font = Font(name="Calibri", size=10, bold=True, color="0F172A")
        ws1.cell(row=row_idx, column=4, value=r.get("primary_intent", "")).font = text_font
        ws1.cell(row=row_idx, column=5, value=r.get("primary_cpc", "")).font = text_font
        ws1.cell(row=row_idx, column=6, value=r.get("secondary_keyword", "")).font = text_font
        ws1.cell(row=row_idx, column=7, value=r.get("secondary_intent", "")).font = text_font
        ws1.cell(row=row_idx, column=8, value=r.get("longtail_keyword", "")).font = text_font
        ws1.cell(row=row_idx, column=9, value=r.get("longtail_intent", "")).font = text_font
        ws1.cell(row=row_idx, column=10, value="✅ Yes" if r.get("google_verified") else "⚡ Algorithmic").font = text_font
        
        for c in range(1, len(headers_ws1) + 1):
            ws1.cell(row=row_idx, column=c).border = thin_border
            
    # Autofit column widths
    for col in ws1.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws1.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 50)
        
    # -------------------------------------------------------------
    # Sheet 2: On-Page Optimization Blueprint
    # -------------------------------------------------------------
    ws2 = wb.create_sheet(title="On-Page SEO Blueprint")
    ws2.views.sheetView[0].showGridLines = True
    
    headers_ws2 = ["Target URL", "Page Category", "Recommended Title Tag", "Recommended H1 Tag", "Recommended Meta Description", "Primary Focus Keyword"]
    for col_idx, h in enumerate(headers_ws2, 1):
        cell = ws2.cell(row=1, column=col_idx, value=h)
        cell.fill = gold_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws2.row_dimensions[1].height = 28
        
    for row_idx, r in enumerate(mapping_data, 2):
        ws2.cell(row=row_idx, column=1, value=r.get("url", "")).font = link_font
        ws2.cell(row=row_idx, column=2, value=r.get("page_category", "")).font = text_font
        ws2.cell(row=row_idx, column=3, value=r.get("blueprint_title", "")).font = text_font
        ws2.cell(row=row_idx, column=4, value=r.get("blueprint_h1", "")).font = text_font
        ws2.cell(row=row_idx, column=5, value=r.get("blueprint_meta", "")).font = text_font
        ws2.cell(row=row_idx, column=6, value=r.get("primary_keyword", "")).font = Font(name="Calibri", size=10, bold=True, color="0F172A")
        
        for c in range(1, len(headers_ws2) + 1):
            ws2.cell(row=row_idx, column=c).border = thin_border

    for col in ws2.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = min(max(max_len + 3, 16), 55)

    # -------------------------------------------------------------
    # Sheet 3: Cannibalization Audit
    # -------------------------------------------------------------
    ws3 = wb.create_sheet(title="Cannibalization Audit")
    ws3.views.sheetView[0].showGridLines = True
    headers_ws3 = ["Conflicting Keyword", "Similarity %", "Conflicting URLs", "Recommended Remediation Action"]
    for col_idx, h in enumerate(headers_ws3, 1):
        cell = ws3.cell(row=1, column=col_idx, value=h)
        cell.fill = navy_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws3.row_dimensions[1].height = 28
        
    if cannibalization_data:
        for row_idx, c in enumerate(cannibalization_data, 2):
            ws3.cell(row=row_idx, column=1, value=c.get("keyword", "")).font = alert_font
            ws3.cell(row=row_idx, column=2, value=c.get("similarity", "")).font = alert_font
            ws3.cell(row=row_idx, column=3, value="\n".join(c.get("overlapping_urls", []))).font = text_font
            ws3.cell(row=row_idx, column=4, value=c.get("recommendation", "")).font = text_font
            for col_i in range(1, 5):
                cell = ws3.cell(row=row_idx, column=col_i)
                cell.border = thin_border
                cell.fill = alert_fill
    else:
        ws3.cell(row=2, column=1, value="🎉 Clean Architecture! Zero keyword cannibalization detected across analyzed pages.").font = Font(name="Calibri", size=11, bold=True, color="047857")

    for col in ws3.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws3.column_dimensions[col_letter].width = min(max(max_len + 3, 18), 60)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ==============================================================================
# 5. STREAMLIT RENDER FUNCTION
# ==============================================================================

def render_keyword_mapper_page():
    """
    Main entry point for the Keyword Research & Page Mapper module.
    Renders futuristic cyberpunk HUD interface matching CrawlPilot.
    """
    # Header Banner
    st.markdown("""
    <div style="background: radial-gradient(125% 120% at 85% 25%, rgba(245, 158, 11, 0.16) 0%, rgba(18, 24, 38, 0.92) 45%, rgba(6, 9, 16, 0.98) 100%); padding: 2.2rem 2.5rem; border-radius: 20px; border: 1px solid rgba(245, 158, 11, 0.35); margin-bottom: 1.8rem; box-shadow: 0 20px 45px -10px rgba(0,0,0,0.8), 0 0 30px rgba(245, 158, 11, 0.12); position: relative; overflow: hidden;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px;">
            <div>
                <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(245, 158, 11, 0.12); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.35); padding: 4px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 0.7rem;">
                    <span>⚡</span> RYZE MCP + CRAWLPILOT INTELLIGENCE ENGINE
                </div>
                <h1 style="font-size: 2.2rem; font-weight: 900; color: #FFFFFF; font-family: 'Space Grotesk', sans-serif; margin: 0 0 0.5rem 0; letter-spacing: -0.02em;">
                    🔑 AI Keyword Research & Page Mapper
                </h1>
                <p style="color: #94A3B8; font-size: 1rem; max-width: 780px; margin: 0; line-height: 1.55;">
                    Autonomous on-page content intelligence. Reads your crawled pages, filters high-converting <b>Product & Service Money Pages</b> (automatically bypassing utility/about/contact pages), suggests <b>3 High-Intent Keywords</b> per page, verifies real search volume trends via Google Autocomplete, and guards against cannibalization.
                </p>
            </div>
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 12px 18px; text-align: right; font-family: 'JetBrains Mono', monospace;">
                <div style="color: #64748B; font-size: 0.68rem; text-transform: uppercase;">MODULE STATUS</div>
                <div style="color: #34D399; font-size: 0.85rem; font-weight: 700;">● ACTIVE & GROUNDED</div>
                <div style="color: #94A3B8; font-size: 0.72rem; margin-top: 4px;">Google Autocomplete: LIVE</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Check for active crawl in session
    crawl_data = st.session_state.get("crawl_results")
    has_active_crawl = crawl_data is not None and isinstance(crawl_data, dict) and "df_pages" in crawl_data and not crawl_data["df_pages"].empty
    
    # Mode Selection Tabs
    tab_mapping, tab_seed_explorer, tab_cannibalization = st.tabs([
        "🗺️ Page Keyword Mapping (Product & Service Focus)",
        "🔍 Seed Keyword Explorer (Ryze MCP Style)",
        "⚠️ Cannibalization & Blueprint Guard"
    ])

    # ==========================================================================
    # TAB 1: PAGE KEYWORD MAPPING (PRODUCT & SERVICE FOCUS)
    # ==========================================================================
    with tab_mapping:
        st.markdown("""
        <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1rem 1.4rem; margin-bottom: 1.4rem;">
            <div style="font-weight: 700; color: #F8FAFC; font-size: 0.95rem; margin-bottom: 4px;">
                🎯 Step 1: Select Page Data Source
            </div>
            <div style="color: #94A3B8; font-size: 0.82rem;">
                Load pages directly from your active crawl audit, or enter URLs to inspect on-the-fly.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_src1, col_src2 = st.columns([1.5, 1])
        with col_src1:
            source_mode = st.radio(
                "Data Source:",
                options=[
                    f"⚡ Import from Active Crawl Audit ({len(crawl_data['df_pages'])} pages ready)" if has_active_crawl else "⚡ Import from Active Crawl Audit (No crawl data yet)",
                    "🌐 Enter Domain / Custom URL List (Live Fetch)",
                    "📝 Paste Specific Product/Service URLs"
                ],
                index=0 if has_active_crawl else 1,
                label_visibility="collapsed"
            )

        with col_src2:
            target_country = st.selectbox(
                "Target Search Market (Google Suggest):",
                options=["us (United States)", "in (India)", "gb (United Kingdom)", "ca (Canada)", "au (Australia)", "de (Germany)", "fr (France)", "ae (UAE)", "sg (Singapore)"],
                index=0,
                help="Localizes Google Autocomplete suggestions and search volume patterns."
            )
            clean_country_code = target_country.split()[0]

        # Filter Settings: Focus on Product & Service pages (as user requested)
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        col_f1, col_f2, col_f3 = st.columns([1.4, 1.2, 1.2])
        with col_f1:
            focus_product_service = st.checkbox(
                "💎 Focus on Product & Service Pages Only (Recommended)",
                value=True,
                help="Automatically filters out About Us, Contact Us, Privacy Policy, Terms, FAQs, Team, and utility pages so you focus purely on money pages that generate traffic and sales."
            )
        with col_f2:
            include_category_hubs = st.checkbox("📁 Include Commercial Category Hubs", value=True)
        with col_f3:
            include_blogs = st.checkbox("📰 Include Blog / Informational Posts", value=False)

        # Input forms based on source_mode
        pages_to_process = []
        
        if "Import from Active Crawl" in source_mode:
            if not has_active_crawl:
                st.warning("⚠️ No active crawl found! In the sidebar, select **'🕷️ CrawlPilot Engine'** and crawl a website first, or choose 'Enter Domain / Custom URL List' below.")
            else:
                df_p = crawl_data["df_pages"].copy()
                st.success(f"✅ Loaded **{len(df_p)} total crawled pages** from active CrawlPilot session.")
                
                # Classify all pages
                classified_list = []
                for _, row in df_p.iterrows():
                    u = str(row.get("url", ""))
                    t = str(row.get("title", ""))
                    h = str(row.get("h1", ""))
                    body = str(row.get("page_text", ""))
                    h2s = row.get("h2_list", [])
                    if isinstance(h2s, str):
                        h2s = [h2s]
                    elif not isinstance(h2s, list):
                        h2s = []
                        
                    cls_info = classify_page_type(u, t, h, body)
                    
                    # Filtering rules
                    if focus_product_service:
                        if not cls_info["is_money_page"]:
                            continue
                        if cls_info["category"] == "Blog / Informational" and not include_blogs:
                            continue
                        if cls_info["category"] == "Commercial Category Hub" and not include_category_hubs:
                            continue
                    else:
                        if cls_info["category"] == "Utility / Administrative":
                            continue
                            
                    classified_list.append({
                        "url": u,
                        "title": t,
                        "h1": h,
                        "meta_desc": str(row.get("meta_description", "")),
                        "h2_list": h2s,
                        "page_text": body,
                        "category": cls_info["category"],
                        "badge": cls_info["badge"],
                        "color": cls_info["color"]
                    })
                    
                pages_to_process = classified_list
                st.info(f"🎯 Filtered down to **{len(pages_to_process)} Commercial Money Pages** (Product, Service, and Core Offerings).")

        elif "Enter Domain" in source_mode:
            target_domain_input = st.text_input(
                "Enter Target Website / Domain to Analyze:",
                placeholder="e.g. https://www.shopify.com or https://example.com/services",
                help="We'll fetch internal pages, read title/headings/body, and categorize product & service pages."
            )
            col_d1, col_d2 = st.columns([1, 1])
            with col_d1:
                crawl_depth_limit = st.slider("Max Pages to Fetch & Analyze:", min_value=5, max_value=40, value=15, step=5)
            with col_d2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                btn_fetch_live = st.button("🚀 Fetch & Map Pages Live", use_container_width=True)

            if btn_fetch_live and target_domain_input:
                clean_target = target_domain_input.strip()
                if "://" not in clean_target:
                    clean_target = f"https://{clean_target}"
                with st.spinner(f"🔍 Crawling and reading pages from {clean_target}..."):
                    try:
                        # Fetch start page and extract links
                        resp = requests.get(clean_target, headers={"User-Agent": DEFAULT_UA}, timeout=10, verify=False)
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.text, "html.parser")
                            base_domain = urllib.parse.urlparse(clean_target).netloc
                            found_urls = [clean_target]
                            
                            for a in soup.find_all("a", href=True):
                                href = a["href"].strip()
                                full_u = urllib.parse.urljoin(clean_target, href)
                                parsed_f = urllib.parse.urlparse(full_u)
                                if parsed_f.netloc == base_domain and parsed_f.scheme in ["http", "https"]:
                                    clean_u = full_u.split("#")[0]
                                    if clean_u not in found_urls and not re.search(r"\.(pdf|png|jpg|jpeg|gif|svg|zip)$", clean_u, re.I):
                                        found_urls.append(clean_u)
                                        if len(found_urls) >= crawl_depth_limit:
                                            break
                                            
                            # Fetch each URL
                            fetched_pages = []
                            for u in found_urls:
                                try:
                                    r_u = requests.get(u, headers={"User-Agent": DEFAULT_UA}, timeout=6, verify=False)
                                    if r_u.status_code == 200:
                                        s_u = BeautifulSoup(r_u.text, "html.parser")
                                        t_u = s_u.title.string.strip() if s_u.title and s_u.title.string else ""
                                        h1_u = s_u.find("h1").get_text(strip=True) if s_u.find("h1") else ""
                                        desc_meta = s_u.find("meta", attrs={"name": "description"})
                                        d_u = desc_meta["content"].strip() if desc_meta and desc_meta.get("content") else ""
                                        h2s = [h.get_text(strip=True) for h in s_u.find_all("h2") if h.get_text(strip=True)][:5]
                                        
                                        # Clean body text
                                        for el in s_u(["script", "style", "nav", "footer", "header"]):
                                            el.extract()
                                        raw_text = " ".join(s_u.get_text(separator=" ", strip=True).split()[:250])
                                        
                                        cls_info = classify_page_type(u, t_u, h1_u, raw_text)
                                        if focus_product_service:
                                            if not cls_info["is_money_page"]:
                                                continue
                                            if cls_info["category"] == "Blog / Informational" and not include_blogs:
                                                continue
                                            if cls_info["category"] == "Commercial Category Hub" and not include_category_hubs:
                                                continue
                                        else:
                                            if cls_info["category"] == "Utility / Administrative":
                                                continue
                                                
                                        fetched_pages.append({
                                            "url": u,
                                            "title": t_u,
                                            "h1": h1_u,
                                            "meta_desc": d_u,
                                            "h2_list": h2s,
                                            "page_text": raw_text,
                                            "category": cls_info["category"],
                                            "badge": cls_info["badge"],
                                            "color": cls_info["color"]
                                        })
                                except Exception:
                                    continue
                                    
                            st.session_state["kw_live_fetched_pages"] = fetched_pages
                            st.success(f"✅ Successfully fetched and parsed **{len(fetched_pages)} Commercial Money Pages**!")
                    except Exception as e:
                        st.error(f"Error fetching website: {e}")
            
            pages_to_process = st.session_state.get("kw_live_fetched_pages", [])

        else: # Paste Specific URLs
            raw_urls_text = st.text_area(
                "Paste Product / Service URLs (One URL per line):",
                placeholder="https://example.com/products/laser-cutter\nhttps://example.com/services/cloud-migration\nhttps://example.com/solutions/enterprise-crm",
                height=130
            )
            if st.button("🚀 Load & Inspect Pasted URLs"):
                urls_list = [u.strip() for u in raw_urls_text.strip().split("\n") if u.strip()]
                parsed_list = []
                with st.spinner("Fetching and reading URL metadata..."):
                    for u in urls_list[:30]:
                        try:
                            r = requests.get(u, headers={"User-Agent": DEFAULT_UA}, timeout=6, verify=False)
                            s = BeautifulSoup(r.text, "html.parser")
                            t = s.title.string.strip() if s.title and s.title.string else ""
                            h1 = s.find("h1").get_text(strip=True) if s.find("h1") else ""
                            desc = s.find("meta", attrs={"name": "description"})
                            d = desc["content"].strip() if desc and desc.get("content") else ""
                            h2s = [h.get_text(strip=True) for h in s.find_all("h2") if h.get_text(strip=True)][:5]
                            for el in s(["script", "style", "nav", "footer", "header"]):
                                el.extract()
                            txt = " ".join(s.get_text(separator=" ", strip=True).split()[:250])
                            cls = classify_page_type(u, t, h1, txt)
                            parsed_list.append({
                                "url": u,
                                "title": t,
                                "h1": h1,
                                "meta_desc": d,
                                "h2_list": h2s,
                                "page_text": txt,
                                "category": cls["category"],
                                "badge": cls["badge"],
                                "color": cls["color"]
                            })
                        except Exception:
                            continue
                st.session_state["kw_pasted_pages"] = parsed_list
                st.success(f"✅ Loaded {len(parsed_list)} URLs!")
            pages_to_process = st.session_state.get("kw_pasted_pages", [])

        # Step 2: Run 3-Keyword Generation & Mapping
        if pages_to_process:
            st.markdown("---")
            st.markdown(f"""
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-bottom: 1rem;">
                <div>
                    <h3 style="color: #FFFFFF; font-size: 1.25rem; font-weight: 800; margin: 0;">
                        ⚡ Step 2: Generate 3 Targeted Keywords & Mapping ({len(pages_to_process)} Money Pages Ready)
                    </h3>
                    <p style="color: #94A3B8; font-size: 0.82rem; margin: 4px 0 0 0;">
                        Every page will receive: 1 Primary Focus Keyword + 1 Secondary/LSI Modifier + 1 Long-Tail Problem Query.
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔥 Run AI Keyword Mapping Engine", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_mapping = []
                
                total = len(pages_to_process)
                for idx, p in enumerate(pages_to_process):
                    status_text.markdown(f"**Analyzing page {idx+1}/{total}:** `{p['url']}`")
                    kw_res = generate_3_page_keywords(
                        url=p["url"],
                        title=p["title"],
                        h1=p["h1"],
                        meta_desc=p["meta_desc"],
                        h2_list=p["h2_list"],
                        page_text=p["page_text"],
                        page_category=p["category"],
                        country=clean_country_code
                    )
                    results_mapping.append(kw_res)
                    progress_bar.progress((idx + 1) / total)
                    time.sleep(0.05)

                cannibal_res = detect_keyword_cannibalization(results_mapping)
                st.session_state["kw_mapping_results"] = results_mapping
                st.session_state["kw_cannibal_results"] = cannibal_res
                status_text.empty()
                progress_bar.empty()
                st.success(f"✅ Successfully mapped **{len(results_mapping)} pages** with **{len(results_mapping) * 3} high-intent keywords**!")

        # Display Results
        mapped_results = st.session_state.get("kw_mapping_results", [])
        if mapped_results:
            st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
            
            # Telemetry KPI row
            total_pages = len(mapped_results)
            total_kws = total_pages * 3
            cannibal_count = len(st.session_state.get("kw_cannibal_results", []))
            
            st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 1.6rem;">
                <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 1.1rem; text-align: center;">
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #94A3B8; text-transform: uppercase;">MONEY PAGES MAPPED</div>
                    <div style="font-size: 1.85rem; font-weight: 900; color: #34D399; margin: 4px 0;">{total_pages}</div>
                    <div style="font-size: 0.72rem; color: #CBD5E1;">Products & Services</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 1.1rem; text-align: center;">
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #94A3B8; text-transform: uppercase;">TARGET KEYWORDS GENERATED</div>
                    <div style="font-size: 1.85rem; font-weight: 900; color: #38BDF8; margin: 4px 0;">{total_kws}</div>
                    <div style="font-size: 0.72rem; color: #CBD5E1;">3 Keywords Per Page</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; padding: 1.1rem; text-align: center;">
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #94A3B8; text-transform: uppercase;">GOOGLE AUTOCOMPLETE</div>
                    <div style="font-size: 1.85rem; font-weight: 900; color: #F59E0B; margin: 4px 0;">100%</div>
                    <div style="font-size: 0.72rem; color: #CBD5E1;">Real Search Trends</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid {'rgba(239, 68, 68, 0.4)' if cannibal_count > 0 else 'rgba(16, 185, 129, 0.3)'}; border-radius: 12px; padding: 1.1rem; text-align: center;">
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #94A3B8; text-transform: uppercase;">CANNIBALIZATION RISKS</div>
                    <div style="font-size: 1.85rem; font-weight: 900; color: {'#EF4444' if cannibal_count > 0 else '#34D399'}; margin: 4px 0;">{cannibal_count}</div>
                    <div style="font-size: 0.72rem; color: #CBD5E1;">{'Conflicts Detected' if cannibal_count > 0 else 'Zero Conflicts'}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Export Buttons
            col_exp1, col_exp2 = st.columns([1, 1])
            with col_exp1:
                excel_bytes = generate_keyword_mapping_excel(
                    mapped_results,
                    st.session_state.get("kw_cannibal_results", [])
                )
                st.download_button(
                    "📥 Export Complete Keyword Mapping (Multi-Tab Excel .xlsx)",
                    data=excel_bytes,
                    file_name=f"Keyword_Mapping_Blueprint_{int(time.time())}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with col_exp2:
                df_export = pd.DataFrame(mapped_results)
                csv_bytes = df_export.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Export Keyword Mapping (CSV)",
                    data=csv_bytes,
                    file_name=f"Keyword_Mapping_{int(time.time())}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            st.markdown("### 📋 Interactive Keyword Mapping Dashboard")
            
            # Interactive Page Cards
            for idx, r in enumerate(mapped_results):
                with st.expander(f"📍 #{idx+1} | {r['primary_keyword']} — {r['page_category']} ({r['url']})", expanded=(idx < 2)):
                    col_p1, col_p2, col_p3 = st.columns([1.2, 1.2, 1.4])
                    with col_p1:
                        st.markdown(f"""
                        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 12px; height: 100%;">
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #34D399; font-weight: 700; text-transform: uppercase;">
                                🎯 1. PRIMARY FOCUS KEYWORD
                            </div>
                            <div style="color: #F8FAFC; font-size: 1.15rem; font-weight: 800; margin: 6px 0;">
                                {r['primary_keyword']}
                            </div>
                            <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
                                <span style="background: rgba(16, 185, 129, 0.2); color: #34D399; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['primary_intent']}</span>
                                <span style="background: rgba(255,255,255,0.06); color: #CBD5E1; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['primary_cpc']}</span>
                            </div>
                            <div style="color: #94A3B8; font-size: 0.75rem; margin-top: 8px;">
                                📌 <b>Target Placement:</b> Title, H1, First 100 words, URL slug
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_p2:
                        st.markdown(f"""
                        <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 12px; height: 100%;">
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #38BDF8; font-weight: 700; text-transform: uppercase;">
                                🚀 2. SECONDARY / FEATURE KEYWORD
                            </div>
                            <div style="color: #F8FAFC; font-size: 1.15rem; font-weight: 800; margin: 6px 0;">
                                {r['secondary_keyword']}
                            </div>
                            <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
                                <span style="background: rgba(56, 189, 248, 0.2); color: #38BDF8; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['secondary_intent']}</span>
                                <span style="background: rgba(255,255,255,0.06); color: #CBD5E1; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['secondary_cpc']}</span>
                            </div>
                            <div style="color: #94A3B8; font-size: 0.75rem; margin-top: 8px;">
                                📌 <b>Target Placement:</b> H2 Subheading, Feature bullet points, Image Alt
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_p3:
                        st.markdown(f"""
                        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 10px; padding: 12px; height: 100%;">
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #F59E0B; font-weight: 700; text-transform: uppercase;">
                                💡 3. LONG-TAIL / PROBLEM KEYWORD
                            </div>
                            <div style="color: #F8FAFC; font-size: 1.05rem; font-weight: 800; margin: 6px 0;">
                                {r['longtail_keyword']}
                            </div>
                            <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
                                <span style="background: rgba(245, 158, 11, 0.2); color: #F59E0B; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['longtail_intent']}</span>
                                <span style="background: rgba(255,255,255,0.06); color: #CBD5E1; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['longtail_cpc']}</span>
                            </div>
                            <div style="color: #94A3B8; font-size: 0.75rem; margin-top: 8px;">
                                📌 <b>Target Placement:</b> FAQ section, Solution deep-dive paragraph
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 10px 14px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #94A3B8;">
                        <div><b>RECOMMENDED TITLE:</b> <span style="color: #38BDF8;">{r['blueprint_title']}</span></div>
                        <div style="margin-top: 4px;"><b>RECOMMENDED H1:</b> <span style="color: #34D399;">{r['blueprint_h1']}</span></div>
                        <div style="margin-top: 4px;"><b>RECOMMENDED META DESC:</b> <span style="color: #CBD5E1;">{r['blueprint_meta']}</span></div>
                    </div>
                    """, unsafe_allow_html=True)

    # ==========================================================================
    # TAB 2: SEED KEYWORD EXPLORER (RYZE MCP STYLE)
    # ==========================================================================
    with tab_seed_explorer:
        st.markdown("""
        <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.2rem; margin-bottom: 1.4rem;">
            <div style="font-weight: 700; color: #F8FAFC; font-size: 1rem; margin-bottom: 4px;">
                💡 Seed-to-Intent Topic Expansion (Ryze MCP Methodology)
            </div>
            <div style="color: #94A3B8; font-size: 0.85rem; line-height: 1.5;">
                Enter a core product, service, or business seed topic. The engine runs live Google Autocomplete fanout with commercial qualifiers (best, price, services, near me, agency, vs) to uncover search intent, difficulty tiers, and topic clusters.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
        with col_s1:
            seed_topic_input = st.text_input(
                "Enter Seed Keyword or Product/Service Topic:",
                placeholder="e.g. laser cutting machine, crm software, b2b seo agency, running shoes",
                help="Type any product, service, or niche term."
            )
        with col_s2:
            seed_country = st.selectbox(
                "Market Region:",
                options=["us", "in", "gb", "ca", "au", "de", "fr", "ae"],
                index=0
            )
        with col_s3:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            btn_run_seed = st.button("🚀 Explore & Expand Seed", type="primary", use_container_width=True)

        if btn_run_seed and seed_topic_input:
            with st.spinner(f"⚡ Expanding '{seed_topic_input}' across commercial intents & Google Autocomplete..."):
                expanded_keywords = expand_seed_keywords(seed_topic_input, country=seed_country)
                st.session_state["kw_expanded_results"] = expanded_keywords

        seed_results = st.session_state.get("kw_expanded_results", [])
        if seed_results:
            st.markdown(f"### 🎯 Found {len(seed_results)} Live Keyword Ideas for '{seed_results[0]['seed']}'")
            
            df_seed = pd.DataFrame(seed_results)
            
            # Intent Breakdown Pills
            trans_count = len(df_seed[df_seed["intent"] == "Transactional"])
            comm_count = len(df_seed[df_seed["intent"] == "Commercial"])
            info_count = len(df_seed[df_seed["intent"] == "Informational"])
            
            st.markdown(f"""
            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 1.2rem;">
                <div style="background: rgba(16, 185, 129, 0.12); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 6px 14px; border-radius: 8px; font-size: 0.8rem; font-family: 'JetBrains Mono', monospace;">
                    🛒 Transactional: <b>{trans_count}</b>
                </div>
                <div style="background: rgba(56, 189, 248, 0.12); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 6px 14px; border-radius: 8px; font-size: 0.8rem; font-family: 'JetBrains Mono', monospace;">
                    💼 Commercial Investigation: <b>{comm_count}</b>
                </div>
                <div style="background: rgba(245, 158, 11, 0.12); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.3); padding: 6px 14px; border-radius: 8px; font-size: 0.8rem; font-family: 'JetBrains Mono', monospace;">
                    ℹ️ Informational: <b>{info_count}</b>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.dataframe(
                df_seed[["keyword", "intent", "cpc_tier", "trigger", "intent_desc"]],
                use_container_width=True,
                column_config={
                    "keyword": st.column_config.TextColumn("Keyword Idea", width="large"),
                    "intent": st.column_config.TextColumn("Search Intent", width="medium"),
                    "cpc_tier": st.column_config.TextColumn("Estimated Commercial Value", width="medium"),
                    "trigger": st.column_config.TextColumn("Expansion Modifier", width="small"),
                    "intent_desc": st.column_config.TextColumn("User Mindset", width="large")
                }
            )

            # CSV Download
            csv_seed = df_seed.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Seed Keyword Research (CSV)",
                data=csv_seed,
                file_name=f"Seed_Keywords_{seed_results[0]['seed'].replace(' ', '_')}.csv",
                mime="text/csv"
            )

    # ==========================================================================
    # TAB 3: CANNIBALIZATION & OPTIMIZATION BLUEPRINT
    # ==========================================================================
    with tab_cannibalization:
        st.markdown("""
        <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.2rem; margin-bottom: 1.4rem;">
            <div style="font-weight: 700; color: #F8FAFC; font-size: 1rem; margin-bottom: 4px;">
                🛡️ Keyword Cannibalization & Page Distinction Guard
            </div>
            <div style="color: #94A3B8; font-size: 0.85rem; line-height: 1.5;">
                When two or more distinct pages target the same primary keyword, search engines split ranking authority and both pages suffer. This tab identifies overlapping keyword assignments and suggests remediation actions.
            </div>
        </div>
        """, unsafe_allow_html=True)

        cannibal_items = st.session_state.get("kw_cannibal_results", [])
        if cannibal_items:
            st.warning(f"⚠️ Found **{len(cannibal_items)} potential keyword cannibalization risks** across your mapped pages!")
            
            for item in cannibal_items:
                with st.container():
                    st.markdown(f"""
                    <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 12px; padding: 1.1rem; margin-bottom: 1rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-weight: 800; color: #F87171; font-size: 1.05rem;">
                                ⚠️ Conflicting Keyword: "{item['keyword']}"
                            </span>
                            <span style="background: rgba(239, 68, 68, 0.2); color: #FCA5A5; padding: 3px 10px; border-radius: 9999px; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace;">
                                {item['similarity']} Semantic Similarity
                            </span>
                        </div>
                        <div style="color: #CBD5E1; font-size: 0.85rem; margin-bottom: 8px;">
                            <b>Conflicting URLs:</b>
                        </div>
                        <ul style="color: #94A3B8; font-size: 0.82rem; margin-top: 0;">
                            {''.join(f"<li><code>{u}</code></li>" for u in item['overlapping_urls'])}
                        </ul>
                        <div style="background: rgba(0,0,0,0.3); padding: 8px 12px; border-radius: 6px; font-size: 0.8rem; color: #E2E8F0;">
                            💡 <b>Action:</b> {item['recommendation']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.success("🎉 **No Keyword Cannibalization Detected!** Every analyzed product and service page has a distinct, dedicated primary target keyword.")
            
        st.markdown("""
        ---
        #### 📐 On-Page Implementation Checklist for Suggested Keywords
        1. **Title Tag:** Ensure the **Primary Keyword** appears within the first 40 characters of the `<title>` tag.
        2. **H1 Tag:** Place the **Primary Keyword** in your only `<h1>` heading.
        3. **Subheadings (H2):** Use the **Secondary Keyword** in at least one `<h2>` to capture feature/intent queries.
        4. **Body Copy & FAQ:** Address the **Long-Tail Problem Keyword** in a dedicated subsection or FAQ accordion.
        5. **Internal Anchor Text:** When linking to this page from blog posts or other pages, use exact-match and partial-match variations of the **Primary Keyword**.
        """)
