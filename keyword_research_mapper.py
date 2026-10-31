"""
Keyword Research & Page Mapper Module
Advanced SEO Keyword Intelligence, Content-to-Keyword Mapping & Gemini AI Crawler Engine.
Deep-crawls websites (up to 500 pages via SEOSpider + XML sitemaps), filters Product & Service money pages,
grounds keywords strictly in the Website's Industry/Niche, provides 2 Focus Keywords + 1 Long-Tail Keyword
(no short keywords), and enforces 100% zero keyword cannibalization across all pages.
"""

import io
import re
import time
import json
import warnings
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore")

# Import enterprise crawler tools
try:
    from crawler import SEOSpider, normalize_url, USER_AGENTS
except ImportError:
    SEOSpider = None
    USER_AGENTS = {}

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

COUNTRIES = [
    "🇮🇳 India",
    "🌐 Global (No specific region)",
    "🇺🇸 United States",
    "🇬🇧 United Kingdom",
    "🇨🇦 Canada",
    "🇦🇺 Australia",
    "🇦🇪 UAE",
    "🇸🇬 Singapore",
    "🇩🇪 Germany",
    "🇫🇷 France",
    "🇯🇵 Japan",
    "🇧🇷 Brazil",
    "🇲🇽 Mexico",
    "🇿🇦 South Africa",
    "🇸🇦 Saudi Arabia"
]

AI_PROVIDERS = [
    "Google Gemini",
    "ChatGPT (OpenAI)",
    "Claude (Anthropic)",
    "Autonomous (Live Google Suggest Engine)"
]

# Comprehensive model lists for all AI providers
GEMINI_MODELS = [
    "gemini-2.5-flash (Recommended - Fast & Accurate)",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.5-pro",
    "gemini-4-argon",
    "gemini-4-argon-thinking",
    "Custom Model"
]

OPENAI_MODELS = [
    "gpt-4o-mini (Recommended - High Speed)",
    "gpt-4o (High Intelligence)",
    "o3-mini",
    "o1",
    "o1-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "Custom Model"
]

CLAUDE_MODELS = [
    "claude-3-5-sonnet-20241022 (Recommended)",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "Custom Model"
]


# ==============================================================================
# 1. LIVE GOOGLE AUTOCOMPLETE & SEARCH INTENT ENGINE
# ==============================================================================

def fetch_google_suggestions(query: str, country_code: str = "in", lang: str = "en", max_results: int = 8) -> list[str]:
    """Fetch real-time Google Autocomplete suggestions without paid API."""
    if not query or len(query.strip()) < 2:
        return []
    clean_query = query.strip()
    encoded = urllib.parse.quote(clean_query)
    url = f"https://suggestqueries.google.com/complete/search?client=chrome&hl={lang}&gl={country_code}&q={encoded}"
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": DEFAULT_UA,
                "Accept": "application/json, text/javascript, */*",
            },
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                return [str(s).strip() for s in data[1] if str(s).strip()][:max_results]
    except Exception:
        pass
    return []


def classify_keyword_intent(keyword: str) -> dict:
    """Classifies search intent and commercial value tier of a keyword."""
    kw = keyword.lower()
    transactional_cues = ["buy", "price", "pricing", "cost", "hire", "quote", "order", "purchase", "discount", "cheap", "for sale", "manufacturer", "suppliers", "near me", "dealer", "exporter"]
    commercial_cues = ["best", "top", "review", "reviews", "comparison", "vs", "versus", "service", "services", "agency", "company", "solutions", "enterprise", "industrial", "actuator", "valve", "specifications", "heavy duty"]
    informational_cues = ["how to", "what is", "guide", "tutorial", "examples", "tips", "why", "who", "when", "working principle", "types of"]

    for t in transactional_cues:
        if re.search(r"\b" + re.escape(t) + r"\b", kw):
            return {
                "intent": "Transactional",
                "badge": "🛒 Transactional",
                "cpc_tier": "$$$$ High Commercial Value"
            }
    for c in commercial_cues:
        if re.search(r"\b" + re.escape(c) + r"\b", kw):
            return {
                "intent": "Commercial",
                "badge": "💼 Commercial",
                "cpc_tier": "$$$ Moderate-High Value"
            }
    for i in informational_cues:
        if re.search(r"\b" + re.escape(i) + r"\b", kw):
            return {
                "intent": "Informational",
                "badge": "ℹ️ Informational",
                "cpc_tier": "$ Low-Moderate Value"
            }
    return {
        "intent": "Commercial / Informational",
        "badge": "🎯 Commercial / Info",
        "cpc_tier": "$$ Commercial Potential"
    }


# ==============================================================================
# 2. PAGE CLASSIFIER (STRICT PRODUCT & SERVICE MONEY PAGE FILTER)
# ==============================================================================

def classify_page_type(url: str, title: str = "", h1: str = "", text: str = "") -> dict:
    """
    Identifies if a page is a Product Page, Service Page, Category Hub,
    or Non-Commercial Utility page (About, Contact, FAQ, History, Terms, Privacy, etc.).
    """
    clean_url = url.lower()
    parsed = urllib.parse.urlparse(clean_url)
    path = parsed.path.strip("/")
    path_segments = [p.lower() for p in path.split("/") if p]
    combined_meta = f"{clean_url} {title.lower()} {h1.lower()}"

    # Utility, Administrative & Non-Product Pages (STRICTLY FILTERED OUT)
    utility_exact = {
        "about", "about-us", "contact", "contact-us", "faq", "faqs", "help",
        "support", "terms", "terms-and-conditions", "privacy", "privacy-policy",
        "cookie-policy", "disclaimer", "legal", "login", "register", "signup",
        "cart", "checkout", "my-account", "author", "authors", "tag", "tags",
        "team", "careers", "jobs", "feed", "history", "our-history", "vision",
        "mission", "values", "milestones", "infrastructure", "quality-policy",
        "quality", "awards", "certificates", "certification", "clients",
        "clientele", "testimonials", "brochure", "downloads", "news", "events",
        "media", "gallery"
    }
    for seg in path_segments:
        if seg in utility_exact:
            return {
                "category": "Utility / Administrative",
                "badge": "⚙️ Utility (Skip)",
                "color": "#64748B",
                "is_money_page": False,
                "reason": f"Non-product slug '/{seg}/'"
            }

    if re.search(r"\b(about us|contact us|privacy policy|terms of service|frequently asked questions|disclaimer|our history|company history|euro currency)\b", combined_meta):
        return {
            "category": "Utility / Administrative",
            "badge": "⚙️ Utility (Skip)",
            "color": "#64748B",
            "is_money_page": False,
            "reason": "Title/H1 indicates utility or informational page"
        }

    # Product Page or Product Category
    product_slug_triggers = ["product", "products", "item", "p", "shop", "goods", "product-category", "product-tag", "valves", "actuator", "accessories"]
    if any(t in path_segments for t in product_slug_triggers):
        if "category" in clean_url or "product-category" in clean_url:
            return {
                "category": "Commercial Category Hub",
                "badge": "📁 Category Hub",
                "color": "#F59E0B",
                "is_money_page": True,
                "reason": "Commercial product category listing"
            }
        return {
            "category": "Product Page",
            "badge": "💎 Product Page",
            "color": "#10B981",
            "is_money_page": True,
            "reason": "Direct product landing page or item"
        }

    # Service / Solution Page
    service_slug_triggers = [
        "service", "services", "solution", "solutions", "consulting",
        "agency", "hire", "plans", "pricing", "platform", "features",
        "capability", "capabilities", "industries", "manufacturing"
    ]
    if any(t in path_segments for t in service_slug_triggers):
        return {
            "category": "Service / Solution Page",
            "badge": "🚀 Service Page",
            "color": "#38BDF8",
            "is_money_page": True,
            "reason": "Commercial service or solution landing page"
        }

    # Blog / Informational Post
    blog_triggers = ["blog", "article", "articles", "post", "posts", "guide", "guides", "insights"]
    if any(t in path_segments for t in blog_triggers):
        return {
            "category": "Blog / Informational",
            "badge": "📰 Blog Post",
            "color": "#A78BFA",
            "is_money_page": False,
            "reason": "Informational blog post or guide"
        }

    # Homepage or Core Root
    if not path or path == "":
        return {
            "category": "Homepage / Core Brand",
            "badge": "🏠 Homepage",
            "color": "#EC4899",
            "is_money_page": True,
            "reason": "Main Root Commercial Landing Page"
        }

    return {
        "category": "Commercial Page",
        "badge": "🎯 Commercial Page",
        "color": "#60A5FA",
        "is_money_page": True,
        "reason": "General indexable commercial page"
    }


# ==============================================================================
# 3. SITEMAP DISCOVERY & DEEP CRAWLER HELPER (UP TO 500 PAGES)
# ==============================================================================

def discover_sitemap_urls(base_url: str, max_urls: int = 600) -> list[str]:
    """Extract internal page URLs from common XML sitemap locations."""
    parsed = urllib.parse.urlparse(base_url)
    root_scheme_netloc = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_paths = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/wp-sitemap.xml",
        "/product-sitemap.xml",
        "/page-sitemap.xml"
    ]
    
    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "text/xml, application/xml, */*"
    }
    
    found_urls = []
    seen = set()

    for p in sitemap_paths:
        sm_url = urllib.parse.urljoin(root_scheme_netloc, p)
        try:
            r = requests.get(sm_url, headers=headers, timeout=6, verify=False)
            if r.status_code == 200 and ("xml" in r.headers.get("Content-Type", "") or "<loc>" in r.text):
                soup = BeautifulSoup(r.text, "html.parser")
                loc_tags = soup.find_all("loc")
                for loc in loc_tags:
                    u = loc.get_text(strip=True)
                    if u.endswith(".xml"):
                        if any(k in u for k in ["product", "page", "post", "category", "service"]):
                            try:
                                sub_r = requests.get(u, headers=headers, timeout=6, verify=False)
                                if sub_r.status_code == 200:
                                    sub_soup = BeautifulSoup(sub_r.text, "html.parser")
                                    for sub_loc in sub_soup.find_all("loc"):
                                        sub_u = sub_loc.get_text(strip=True)
                                        if sub_u not in seen and not sub_u.endswith(".xml"):
                                            seen.add(sub_u)
                                            found_urls.append(sub_u)
                                            if len(found_urls) >= max_urls:
                                                return found_urls
                            except Exception:
                                pass
                    else:
                        if u not in seen and not re.search(r"\.(pdf|png|jpg|jpeg|gif|svg|zip)$", u, re.I):
                            seen.add(u)
                            found_urls.append(u)
                            if len(found_urls) >= max_urls:
                                return found_urls
        except Exception:
            continue

    return found_urls


def detect_website_industry(homepage_title: str, homepage_meta: str, homepage_h1: str) -> str:
    """Auto-detects the core business niche and industry from homepage metadata."""
    combined = f"{homepage_title} {homepage_h1} {homepage_meta}".lower()
    
    # Specific known B2B / Manufacturing niches
    if any(k in combined for k in ["actuator", "valve", "valves", "flow control", "flange", "pneumatic"]):
        return "Industrial Electrical Actuators & Motorized Valves Manufacturing"
    if any(k in combined for k in ["laser", "cnc", "cutting machine", "fiber laser", "sheet metal"]):
        return "CNC Fiber Laser & Metal Fabrication Machinery"
    if any(k in combined for k in ["seo", "digital marketing", "organic growth", "content marketing"]):
        return "B2B SEO, Search Marketing & Digital Growth Agency"
    if any(k in combined for k in ["software", "saas", "crm", "erp", "cloud platform"]):
        return "Enterprise SaaS & Cloud Software Solutions"
    if any(k in combined for k in ["apparel", "clothing", "leather", "footwear", "fashion"]):
        return "Premium Footwear, Leather Goods & Fashion Retail"
    if any(k in combined for k in ["pharmaceutical", "medicine", "pharma", "healthcare"]):
        return "Pharmaceutical & Healthcare Product Manufacturing"
        
    # Generic extraction from title
    clean = re.sub(r"\s*[-|–—:]\s*[^-|–—:]+$", "", homepage_title).strip()
    return clean or "Commercial B2B Products & Services"


def deep_crawl_website_for_keywords(
    start_url: str,
    max_pages: int = 150,
    progress_callback = None
) -> tuple[list[dict], str]:
    """
    Crawls a website completely using SEOSpider combined with XML sitemap extraction.
    Pulls Title, H1, H2s, Meta Description, and clean body text for every page.
    Returns: (parsed_pages, detected_industry)
    """
    clean_start = start_url.strip()
    if "://" not in clean_start:
        clean_start = f"https://{clean_start}"

    if progress_callback:
        progress_callback(0.05, f"🔍 Discovering XML Sitemaps for {clean_start}...")

    # 1. Discover URLs from XML Sitemaps
    sitemap_urls = discover_sitemap_urls(clean_start, max_urls=max_pages * 2)

    # 2. Run SEOSpider for deep crawling
    spider_pages = []
    if SEOSpider:
        if progress_callback:
            progress_callback(0.15, f"🕷️ Quantum Spider crawling internal links across {clean_start} (Up to {max_pages} pages)...")
        try:
            spider = SEOSpider(
                start_url=clean_start,
                max_pages=max_pages,
                max_depth=8,
                concurrency=12,
                user_agent_name="Chrome (Windows 11)",
                respect_robots=False,
                crawl_mode="Subdomain"
            )
            raw_res = spider.crawl()
            spider_pages = raw_res.get("crawled_pages", [])
        except Exception:
            spider_pages = []

    # Combine URLs
    url_to_page_data = {}
    for p in spider_pages:
        u = p.get("url", "")
        if u and p.get("status_code", 0) in [200, 301, 302]:
            url_to_page_data[u] = p

    # If sitemap had URLs not visited by spider, add them to crawl queue
    remaining_urls = [u for u in sitemap_urls if u not in url_to_page_data][:max_pages]
    if remaining_urls:
        if progress_callback:
            progress_callback(0.35, f"📄 Fetching {len(remaining_urls)} sitemap pages...")
            
        def _fetch_single(target_u):
            try:
                r = requests.get(target_u, headers={"User-Agent": DEFAULT_UA}, timeout=8, verify=False)
                if r.status_code == 200:
                    return {"url": target_u, "status_code": 200, "html": r.text}
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(_fetch_single, u): u for u in remaining_urls}
            for fut in as_completed(future_to_url):
                res = fut.result()
                if res:
                    url_to_page_data[res["url"]] = res

    # 3. Parse and extract metadata for every collected page
    parsed_pages = []
    total_found = len(url_to_page_data)
    detected_industry = ""
    
    for idx, (u, pdata) in enumerate(url_to_page_data.items()):
        if progress_callback:
            progress_callback(0.40 + (0.25 * ((idx + 1) / max(total_found, 1))), f"Extracting page content ({idx+1}/{total_found})...")

        status = pdata.get("status_code", 200)
        if status in [301, 302, 307, 308, 404, 500]:
            continue

        html = pdata.get("html", "")
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        h1 = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""
        desc_meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        meta_desc = desc_meta["content"].strip() if desc_meta and desc_meta.get("content") else ""
        h2s = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)][:6]

        # Clean text
        for el in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            el.extract()
        body_text = " ".join(soup.get_text(separator=" ", strip=True).split()[:300])

        # If homepage, detect industry
        parsed_u = urllib.parse.urlparse(u)
        if not parsed_u.path or parsed_u.path == "/" or not detected_industry:
            detected_industry = detect_website_industry(title, meta_desc, h1)

        cls_info = classify_page_type(u, title, h1, body_text)
        
        parsed_pages.append({
            "url": u,
            "title": title,
            "h1": h1,
            "meta_desc": meta_desc,
            "h2_list": h2s,
            "page_text": body_text,
            "category": cls_info["category"],
            "badge": cls_info["badge"],
            "color": cls_info["color"],
            "is_money_page": cls_info["is_money_page"]
        })

    return parsed_pages, (detected_industry or "Industrial B2B Manufacturing & Supply")


# ==============================================================================
# 4. MULTI-MODEL AI KEYWORD BOT (2 FOCUS + 1 LONG-TAIL, NO CANNIBALIZATION)
# ==============================================================================

def call_ai_provider(
    provider: str,
    model_name: str,
    api_key: str,
    prompt: str
) -> str:
    """Unified AI caller supporting Google Gemini, OpenAI ChatGPT, and Claude."""
    clean_model = model_name.split(" ")[0].strip() if " (" in model_name else model_name.strip()

    if provider == "Google Gemini":
        from google import genai
        client = genai.Client(api_key=api_key)

        # Fallback candidate models in case of preview / 404 alias
        candidate_models = [clean_model]
        for fb in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
            if fb not in candidate_models:
                candidate_models.append(fb)

        last_err = None
        for cand in candidate_models:
            try:
                response = client.models.generate_content(
                    model=cand,
                    contents=prompt
                )
                if response.text:
                    return response.text
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise last_err

    elif provider == "ChatGPT (OpenAI)":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=clean_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content or ""

    elif provider == "Claude (Anthropic)":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=clean_model,
            max_tokens=1500,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text if response.content else ""

    return ""


def analyze_page_with_ai_bot(
    page_data: dict,
    api_key: str,
    provider: str = "Google Gemini",
    model_name: str = "gemini-2.5-flash",
    country_name: str = "India",
    industry_niche: str = "Industrial Valves & Actuators Manufacturing",
    assigned_registry: set = None
) -> dict:
    """
    Calls AI to generate:
    - 2 High-Intent Focus Keywords (Commercial & Transactional, 3-6 words, NO SHORT 1-2 words)
    - 1 Long-Tail Buyer Query (4-8 words)
    Strictly grounded in industry_niche and enforced to avoid keyword cannibalization.
    """
    assigned_registry = assigned_registry or set()
    already_assigned_sample = list(assigned_registry)[-15:] if assigned_registry else []
    already_str = ", ".join(already_assigned_sample) if already_assigned_sample else "None so far"

    prompt = f"""You are a senior enterprise SEO strategist specializing in B2B Keyword Mapping & Organic Search Optimization.

WEBSITE INDUSTRY / CORE NICHE: {industry_niche}
TARGET SEARCH MARKET: {country_name}

ANALYZE THIS WEBPAGE:
- URL: {page_data.get('url')}
- Current Title: {page_data.get('title')}
- Primary H1: {page_data.get('h1')}
- Meta Description: {page_data.get('meta_desc')}
- H2 Subheadings: {', '.join(page_data.get('h2_list', []))}
- Page Content Excerpt: {page_data.get('page_text', '')[:400]}

MANDATORY SEO INSTRUCTIONS (FOLLOW STRICTLY):
1. INDUSTRY RELEVANCE: All keywords MUST be directly relevant to the website's industry: "{industry_niche}". NEVER suggest unrelated topics (e.g. no euro currency, no textbook economics, no generic software filler).
2. KEYWORD STRUCTURE (EXACTLY 2 FOCUS KEYWORDS + 1 LONG-TAIL KEYWORD):
   - Focus Keyword 1 (Primary Target): High-intent commercial/transactional money keyword (3 to 6 words). Must include commercial qualifiers (e.g. Manufacturer In India, Supplier, Exporter, Heavy Duty, Industrial). DO NOT provide short 1-2 word keywords!
   - Focus Keyword 2 (Secondary Target): Distinct commercial/specification focus keyword (3 to 6 words) highlighting engineering attributes, model variations, or use cases. DO NOT provide short keywords!
   - Long-tail Keyword: High-converting buyer problem or decision-stage search query (4 to 8 words).
3. ZERO CANNIBALIZATION: Do NOT use or repeat these keywords already assigned to other pages: [{already_str}]. Make these keywords distinct and unique to this specific page's product/service.

OUTPUT MUST BE VALID STRICT JSON ONLY (no markdown blocks, no commentary):
{{
  "focus_keyword_1": "Primary 3-6 word Commercial Focus Keyword",
  "focus_1_intent": "🛒 Transactional",
  "focus_1_cpc": "$$$$ High Commercial Value",
  "focus_keyword_2": "Secondary 3-6 word Commercial Focus Keyword",
  "focus_2_intent": "💼 Commercial",
  "focus_2_cpc": "$$$ Moderate-High Value",
  "longtail_keyword": "4-8 word Problem-Solving Long-Tail Keyword",
  "longtail_intent": "🎯 Commercial / Info",
  "longtail_cpc": "$$ Commercial Potential",
  "blueprint_title": "Optimized Page Title (Under 60 chars)",
  "blueprint_h1": "Optimized Primary H1 Tag",
  "blueprint_meta": "Compelling Meta Description with CTA (Under 155 chars)"
}}"""

    clean_model_id = model_name.split(" ")[0].strip() if " (" in model_name else model_name.strip()

    try:
        raw_text = call_ai_provider(provider, clean_model_id, api_key, prompt)
        clean_json = re.sub(r"^```json\s*", "", raw_text.strip(), flags=re.I)
        clean_json = re.sub(r"```$", "", clean_json.strip())
        data = json.loads(clean_json)

        # Enforce non-cannibalization in registry
        fk1 = data.get("focus_keyword_1", "").strip().title()
        fk2 = data.get("focus_keyword_2", "").strip().title()
        
        # Verify length (must not be short 1-2 words)
        if len(fk1.split()) < 3:
            fk1 = f"{fk1} Manufacturer & Supplier In {country_name}"
        if len(fk2.split()) < 3:
            fk2 = f"Industrial {fk2} Price & Specifications"

        # Check cannibalization against registry
        if fk1.lower() in assigned_registry:
            slug_part = page_data["url"].strip("/").split("/")[-1].replace("-", " ").title()
            fk1 = f"{fk1} - {slug_part}"
        if fk2.lower() in assigned_registry:
            fk2 = f"Custom {fk2} For Industrial Applications"

        assigned_registry.add(fk1.lower())
        assigned_registry.add(fk2.lower())

        return {
            "url": page_data["url"],
            "page_category": page_data.get("category", "Product Page"),
            "focus_keyword_1": fk1,
            "focus_1_intent": data.get("focus_1_intent", "🛒 Transactional"),
            "focus_1_cpc": data.get("focus_1_cpc", "$$$$ High Commercial Value"),
            "focus_keyword_2": fk2,
            "focus_2_intent": data.get("focus_2_intent", "💼 Commercial"),
            "focus_2_cpc": data.get("focus_2_cpc", "$$$ Moderate-High Value"),
            "longtail_keyword": data.get("longtail_keyword", "").strip().title(),
            "longtail_intent": data.get("longtail_intent", "🎯 Commercial / Info"),
            "longtail_cpc": data.get("longtail_cpc", "$$ Commercial Potential"),
            "blueprint_title": data.get("blueprint_title", ""),
            "blueprint_h1": data.get("blueprint_h1", ""),
            "blueprint_meta": data.get("blueprint_meta", ""),
            "engine": f"{provider} ({clean_model_id})"
        }
    except Exception:
        # Fallback to smart algorithmic generator
        return generate_algorithmic_page_keywords(page_data, country_name, industry_niche, assigned_registry)


def generate_algorithmic_page_keywords(
    page_data: dict,
    country_name: str = "India",
    industry_niche: str = "Industrial Valves & Actuators Manufacturing",
    assigned_registry: set = None
) -> dict:
    """
    Algorithmic keyword generation backed by real-time Google Autocomplete.
    Enforces industry context, 2 focus + 1 longtail, no short keywords, and zero cannibalization.
    """
    assigned_registry = assigned_registry or set()
    url = page_data["url"]
    title = page_data.get("title", "")
    h1 = page_data.get("h1", "")
    
    parsed = urllib.parse.urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    slug_words = [w for w in re.split(r"[-_]+", slug) if len(w) > 2 and not w.isdigit()]
    
    clean_title = re.sub(r"\s*[-|–—:]\s*[^-|–—:]+$", "", title).strip()
    clean_seed = " ".join(slug_words).title() if slug_words else clean_title
    if not clean_seed or len(clean_seed) < 4:
        clean_seed = clean_title or h1 or "Industrial Product"
    
    # Query Google suggest with industry anchor
    query_to_suggest = f"{clean_seed} manufacturer"
    suggs = fetch_google_suggestions(query_to_suggest, country_code="in", max_results=6)
    
    # Focus Keyword 1 (3-6 words, commercial/transactional)
    if suggs and len(suggs[0].split()) >= 3:
        fk1 = suggs[0].title()
    else:
        fk1 = f"{clean_seed} Manufacturer In {country_name}"
        
    # Focus Keyword 2 (3-6 words, specification/feature)
    if len(suggs) > 1 and len(suggs[1].split()) >= 3 and suggs[1].lower() != fk1.lower():
        fk2 = suggs[1].title()
    else:
        fk2 = f"Heavy Duty {clean_seed} Price & Specifications"
        
    # Long-tail Keyword (4-8 words, problem/application)
    longtail_kw = f"Best Quality {clean_seed} For Industrial Applications In {country_name}"
    for s in (suggs or []):
        if len(s.split()) >= 4 and s.lower() not in [fk1.lower(), fk2.lower()]:
            longtail_kw = s.title()
            break

    # Prevent Cannibalization
    if fk1.lower() in assigned_registry:
        fk1 = f"Industrial Grade {fk1}"
    if fk2.lower() in assigned_registry:
        fk2 = f"Custom Engineered {fk2}"

    assigned_registry.add(fk1.lower())
    assigned_registry.add(fk2.lower())

    p1_intent = classify_keyword_intent(fk1)
    p2_intent = classify_keyword_intent(fk2)
    lt_intent = classify_keyword_intent(longtail_kw)

    parsed_domain = parsed.netloc.replace("www.", "").split(".")[0].title()
    rec_title = f"{fk1} | {fk2} - {parsed_domain}"[:60]
    rec_h1 = f"{fk1}: Engineered Industrial Solutions"
    rec_meta = f"High-grade {fk1}. View {fk2} with full technical specifications. Contact {parsed_domain} for bulk quotes."[:155]

    return {
        "url": url,
        "page_category": page_data.get("category", "Product Page"),
        "focus_keyword_1": fk1,
        "focus_1_intent": p1_intent["badge"],
        "focus_1_cpc": p1_intent["cpc_tier"],
        "focus_keyword_2": fk2,
        "focus_2_intent": p2_intent["badge"],
        "focus_2_cpc": p2_intent["cpc_tier"],
        "longtail_keyword": longtail_kw,
        "longtail_intent": lt_intent["badge"],
        "longtail_cpc": lt_intent["cpc_tier"],
        "blueprint_title": rec_title,
        "blueprint_h1": rec_h1,
        "blueprint_meta": rec_meta,
        "engine": "Google Suggest Autocomplete"
    }


def detect_keyword_cannibalization(mapping_rows: list[dict]) -> list[dict]:
    """Flags if multiple distinct pages target the same focus keyword."""
    seen_keywords = {}
    warnings = []
    for row in mapping_rows:
        fk1 = row.get("focus_keyword_1", "").lower().strip()
        url = row.get("url", "")
        if not fk1:
            continue
        kw_tokens = set(re.findall(r"\b\w+\b", fk1))
        for prev_kw, prev_urls in seen_keywords.items():
            prev_tokens = set(re.findall(r"\b\w+\b", prev_kw))
            intersection = kw_tokens.intersection(prev_tokens)
            union = kw_tokens.union(prev_tokens)
            similarity = len(intersection) / max(len(union), 1)
            if prev_kw == fk1 or similarity >= 0.85:
                prev_urls.append(url)
                warnings.append({
                    "keyword": row.get("focus_keyword_1"),
                    "overlapping_urls": list(set(prev_urls)),
                    "similarity": f"{int(similarity * 100)}%"
                })
                break
        if fk1 not in seen_keywords:
            seen_keywords[fk1] = [url]
    return warnings


# ==============================================================================
# 5. EXCEL EXPORT GENERATOR
# ==============================================================================

def generate_keyword_mapping_excel(mapping_data: list[dict], site_domain: str = "") -> bytes:
    """Generates styled multi-tab Excel workbook."""
    wb = openpyxl.Workbook()
    navy_fill = PatternFill(start_color="0A0F1D", end_color="0A0F1D", fill_type="solid")
    gold_fill = PatternFill(start_color="D97706", end_color="D97706", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    text_font = Font(name="Calibri", size=10, color="1E293B")
    link_font = Font(name="Calibri", size=10, color="0284C7", underline="single")
    bold_font = Font(name="Calibri", size=10, bold=True, color="0F172A")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    # Sheet 1: Mapping
    ws1 = wb.active
    ws1.title = "Keyword Mapping Plan"
    ws1.views.sheetView[0].showGridLines = True
    headers_ws1 = [
        "Page URL", "Category", 
        "Focus Keyword 1 (Primary)", "Focus 1 Intent", "Commercial Value",
        "Focus Keyword 2 (Secondary)", "Focus 2 Intent",
        "Long-Tail Keyword (Buyer Intent)", "Long-Tail Intent",
        "AI / Grounding Engine"
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
        ws1.cell(row=row_idx, column=3, value=r.get("focus_keyword_1", "")).font = bold_font
        ws1.cell(row=row_idx, column=4, value=r.get("focus_1_intent", "")).font = text_font
        ws1.cell(row=row_idx, column=5, value=r.get("focus_1_cpc", "")).font = text_font
        ws1.cell(row=row_idx, column=6, value=r.get("focus_keyword_2", "")).font = text_font
        ws1.cell(row=row_idx, column=7, value=r.get("focus_2_intent", "")).font = text_font
        ws1.cell(row=row_idx, column=8, value=r.get("longtail_keyword", "")).font = text_font
        ws1.cell(row=row_idx, column=9, value=r.get("longtail_intent", "")).font = text_font
        ws1.cell(row=row_idx, column=10, value=r.get("engine", "Gemini AI")).font = text_font
        for c in range(1, len(headers_ws1) + 1):
            ws1.cell(row=row_idx, column=c).border = thin_border

    for col in ws1.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws1.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 48)

    # Sheet 2: Blueprint
    ws2 = wb.create_sheet(title="On-Page SEO Blueprint")
    ws2.views.sheetView[0].showGridLines = True
    headers_ws2 = ["Target URL", "Page Category", "Focus Keyword 1", "Recommended Title Tag", "Recommended H1 Tag", "Recommended Meta Description"]
    for col_idx, h in enumerate(headers_ws2, 1):
        cell = ws2.cell(row=1, column=col_idx, value=h)
        cell.fill = gold_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws2.row_dimensions[1].height = 28

    for row_idx, r in enumerate(mapping_data, 2):
        ws2.cell(row=row_idx, column=1, value=r.get("url", "")).font = link_font
        ws2.cell(row=row_idx, column=2, value=r.get("page_category", "")).font = text_font
        ws2.cell(row=row_idx, column=3, value=r.get("focus_keyword_1", "")).font = bold_font
        ws2.cell(row=row_idx, column=4, value=r.get("blueprint_title", "")).font = text_font
        ws2.cell(row=row_idx, column=5, value=r.get("blueprint_h1", "")).font = text_font
        ws2.cell(row=row_idx, column=6, value=r.get("blueprint_meta", "")).font = text_font
        for c in range(1, len(headers_ws2) + 1):
            ws2.cell(row=row_idx, column=c).border = thin_border

    for col in ws2.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = min(max(max_len + 3, 16), 55)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ==============================================================================
# 6. STREAMLIT RENDER FUNCTION
# ==============================================================================

def render_keyword_mapper_page():
    """Renders the AI Keyword Research & Page Mapper interface."""

    # Hero Banner
    st.markdown("""
    <div style="background: radial-gradient(125% 120% at 85% 25%, rgba(245, 158, 11, 0.16) 0%, rgba(18, 24, 38, 0.92) 45%, rgba(6, 9, 16, 0.98) 100%); padding: 2.2rem 2.5rem; border-radius: 20px; border: 1px solid rgba(245, 158, 11, 0.35); margin-bottom: 1.6rem; box-shadow: 0 20px 45px -10px rgba(0,0,0,0.8), 0 0 30px rgba(245, 158, 11, 0.12); position: relative; overflow: hidden;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px;">
            <div>
                <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(245, 158, 11, 0.12); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.35); padding: 4px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 0.7rem;">
                    <span>⚡</span> DEEP SPIDER + GEMINI AI KEYWORD ENGINE
                </div>
                <h1 style="font-size: 2.2rem; font-weight: 900; color: #FFFFFF; font-family: 'Space Grotesk', sans-serif; margin: 0 0 0.5rem 0; letter-spacing: -0.02em;">
                    🔑 AI Keyword Research & Page Mapper
                </h1>
                <p style="color: #94A3B8; font-size: 1rem; max-width: 820px; margin: 0; line-height: 1.55;">
                    Autonomous on-page keyword intelligence powered by <b>Google Gemini AI</b> and <b>CrawlPilot Quantum Spider</b>. Deep-crawls websites up to <b>500 pages</b>, filters <b>Product & Service Money Pages</b>, generates <b>2 Focus Keywords + 1 Long-Tail Keyword</b> (strictly relevant to your industry, no short keywords), and enforces <b>Zero Keyword Cannibalization</b>.
                </p>
            </div>
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 12px 18px; text-align: right; font-family: 'JetBrains Mono', monospace;">
                <div style="color: #64748B; font-size: 0.68rem; text-transform: uppercase;">INTELLIGENCE STATUS</div>
                <div style="color: #34D399; font-size: 0.85rem; font-weight: 700;">● ZERO CANNIBALIZATION ACTIVE</div>
                <div style="color: #94A3B8; font-size: 0.72rem; margin-top: 4px;">Crawl Capacity: UP TO 500 URLS</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==============================================================================
    # AI PROVIDER & MODEL CONFIGURATION (All Models in Dropdown)
    # ==============================================================================
    st.markdown("""
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 1.2rem; margin-bottom: 1.4rem;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.85rem; font-weight: 800; color: #F8FAFC; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
            <span style="color: #FFC107;">🤖</span> AI INTELLIGENCE & MODEL SETTINGS
        </div>
    """, unsafe_allow_html=True)

    cfg_col1, cfg_col2, cfg_col3 = st.columns([1.2, 1.8, 1.2])

    with cfg_col1:
        ai_provider = st.selectbox(
            "AI Provider",
            options=AI_PROVIDERS,
            index=0,
            key="kw_ai_provider"
        )
        if ai_provider == "Google Gemini":
            selected_model_choice = st.selectbox(
                "Model",
                options=GEMINI_MODELS,
                index=0,
                key="kw_gemini_model"
            )
        elif ai_provider == "ChatGPT (OpenAI)":
            selected_model_choice = st.selectbox(
                "Model",
                options=OPENAI_MODELS,
                index=0,
                key="kw_openai_model"
            )
        elif ai_provider == "Claude (Anthropic)":
            selected_model_choice = st.selectbox(
                "Model",
                options=CLAUDE_MODELS,
                index=0,
                key="kw_claude_model"
            )
        else:
            selected_model_choice = "Autonomous Suggestion Engine"
            st.info("Uses real-time Google Autocomplete API without API key.")

        if selected_model_choice == "Custom Model":
            selected_model = st.text_input("Enter Custom Model ID:", placeholder="e.g. gemini-2.5-flash", key="kw_custom_model").strip()
        else:
            selected_model = selected_model_choice.split(" ")[0].strip()

    with cfg_col2:
        if ai_provider == "Google Gemini":
            key_label = "Google Gemini API Key (Free)"
            key_placeholder = "Paste your Gemini API key (AIzaSy...)"
            help_url = "https://aistudio.google.com/apikey"
            help_text = "Get your free key from Google AI Studio →"
        elif ai_provider == "ChatGPT (OpenAI)":
            key_label = "OpenAI API Key"
            key_placeholder = "sk-..."
            help_url = "https://platform.openai.com/api-keys"
            help_text = "Get your OpenAI API key →"
        elif ai_provider == "Claude (Anthropic)":
            key_label = "Anthropic API Key"
            key_placeholder = "sk-ant-..."
            help_url = "https://console.anthropic.com/settings/keys"
            help_text = "Get your Anthropic key →"
        else:
            key_label = "Autonomous Mode Active"
            key_placeholder = "No API key required for Autonomous mode"
            help_url = ""
            help_text = ""

        if ai_provider != "Autonomous (Live Google Suggest Engine)":
            api_key = st.text_input(
                key_label,
                value=st.session_state.get(f"api_key_{ai_provider}", ""),
                type="password",
                placeholder=key_placeholder,
                key=f"kw_input_key_{ai_provider}"
            )
            if help_text:
                st.caption(f"🔑 <a href='{help_url}' target='_blank' style='color:#818CF8; text-decoration:none;'>{help_text}</a>", unsafe_allow_html=True)
            if api_key:
                st.session_state[f"api_key_{ai_provider}"] = api_key
        else:
            api_key = ""

        if st.button("🔄 Clear All (Keys & Results)", key="kw_btn_clear"):
            st.session_state["kw_mapping_results"] = []
            st.session_state["kw_crawled_pages"] = []
            st.session_state[f"api_key_{ai_provider}"] = ""
            st.rerun()

    with cfg_col3:
        target_country = st.selectbox(
            "Target Search Region",
            options=COUNTRIES,
            index=0,
            key="kw_target_country"
        )
        # Max pages slider updated to 500 as requested
        max_crawl_pages = st.slider(
            "Max Pages to Crawl & Map",
            min_value=10,
            max_value=500,
            value=150,
            step=10,
            help="Deep crawl will traverse internal links and XML sitemaps up to 500 pages."
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # ==============================================================================
    # WEBSITE URL INPUT & INDUSTRY CONTEXT (ENFORCED RELEVANCE)
    # ==============================================================================
    st.markdown("""
    <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.1rem; margin-bottom: 1.2rem;">
        <div style="font-weight: 700; color: #F8FAFC; font-size: 0.95rem; margin-bottom: 4px;">
            🌐 Target Website & Industry Niche Anchor
        </div>
        <div style="color: #94A3B8; font-size: 0.82rem;">
            Deep-crawls internal pages & sitemaps. All generated keywords will be strictly aligned to your website's industry so no unrelated topics ever appear.
        </div>
    </div>
    """, unsafe_allow_html=True)

    crawl_data = st.session_state.get("crawl_results")
    has_active_crawl = crawl_data is not None and isinstance(crawl_data, dict) and "df_pages" in crawl_data and not crawl_data["df_pages"].empty
    default_url = (crawl_data.get("start_url", "") if has_active_crawl else "") or st.session_state.get("kw_last_url", "https://cairindia.com/")
    
    col_u1, col_u2 = st.columns([3.5, 1.2])
    with col_u1:
        target_website_url = st.text_input(
            "Website URL:",
            value=default_url,
            placeholder="e.g. https://cairindia.com/ or https://example.com/",
            key="kw_target_url_input"
        )
    with col_u2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        btn_start_crawl = st.button("🚀 Deep Crawl & Map", type="primary", use_container_width=True)

    # Industry Niche Anchor (Auto-detected or custom)
    detected_ind_default = st.session_state.get("kw_detected_industry", "Industrial Electrical Actuators & Motorized Valves Manufacturer")
    industry_niche_input = st.text_input(
        "🏭 Website Industry / Core Business Niche (Keywords will strictly anchor to this):",
        value=detected_ind_default,
        help="All keywords will be strictly relevant to this industry. Unrelated topics will be rejected.",
        key="kw_industry_niche"
    )

    # Optional Quick Import from active crawl
    if has_active_crawl:
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 8px; padding: 6px 14px; margin-top: 6px;">
            <span style="color: #34D399; font-size: 0.8rem; font-family: 'JetBrains Mono', monospace;">
                ⚡ Found active crawl audit with <b>{len(crawl_data['df_pages'])} pages</b>.
            </span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("⚡ Use Already Crawled Pages from CrawlPilot Engine", use_container_width=True):
            df_p = crawl_data["df_pages"]
            imported_pages = []
            for _, r in df_p.iterrows():
                u = str(r.get("url", ""))
                t = str(r.get("title", ""))
                h = str(r.get("h1", ""))
                body = str(r.get("page_text", ""))
                h2s = r.get("h2_list", [])
                if isinstance(h2s, str):
                    h2s = [h2s]
                elif not isinstance(h2s, list):
                    h2s = []
                cls = classify_page_type(u, t, h, body)
                imported_pages.append({
                    "url": u,
                    "title": t,
                    "h1": h,
                    "meta_desc": str(r.get("meta_description", "")),
                    "h2_list": h2s,
                    "page_text": body,
                    "category": cls["category"],
                    "badge": cls["badge"],
                    "color": cls["color"],
                    "is_money_page": cls["is_money_page"]
                })
            st.session_state["kw_crawled_pages"] = imported_pages
            st.success(f"✅ Loaded {len(imported_pages)} pages from active audit!")
            st.rerun()

    # Filter Options
    col_f1, col_f2 = st.columns([1.5, 1.5])
    with col_f1:
        focus_money_pages = st.checkbox(
            "💎 Focus on Product & Service Pages Only (Bypasses About/Contact/History/Legal)",
            value=True,
            help="Filters out utility & non-product pages so you get keywords exclusively for commercial pages."
        )
    with col_f2:
        include_categories = st.checkbox("📁 Include Commercial Category Hubs", value=True)

    # Crawling Execution
    if btn_start_crawl and target_website_url:
        st.session_state["kw_last_url"] = target_website_url
        progress_bar = st.progress(0)
        status_box = st.empty()

        def _update_progress(pct, msg):
            progress_bar.progress(pct)
            status_box.markdown(f"**Status:** {msg}")

        crawled_pages, auto_industry = deep_crawl_website_for_keywords(
            start_url=target_website_url,
            max_pages=max_crawl_pages,
            progress_callback=_update_progress
        )

        st.session_state["kw_crawled_pages"] = crawled_pages
        if auto_industry:
            st.session_state["kw_detected_industry"] = auto_industry
            
        progress_bar.progress(1.0)
        status_box.empty()
        progress_bar.empty()
        st.success(f"✅ Deep Crawl Complete! Found **{len(crawled_pages)} total internal pages** with HTML content.")
        st.rerun()

    # ==============================================================================
    # STEP 2: RUN AI KEYWORD MAPPING (2 FOCUS + 1 LONG-TAIL, ZERO CANNIBALIZATION)
    # ==============================================================================
    crawled_pages = st.session_state.get("kw_crawled_pages", [])
    
    if crawled_pages:
        # Filter down to money pages
        filtered_pages = []
        for p in crawled_pages:
            if focus_money_pages:
                if not p.get("is_money_page", True):
                    continue
                if p.get("category") == "Commercial Category Hub" and not include_categories:
                    continue
            else:
                if p.get("category") == "Utility / Administrative":
                    continue
            filtered_pages.append(p)

        st.markdown(f"""
        <div style="background: rgba(14, 20, 34, 0.7); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 12px; padding: 1.1rem; margin: 1.2rem 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <div style="font-weight: 800; color: #FFFFFF; font-size: 1.1rem;">
                    🎯 {len(filtered_pages)} Commercial Money Pages Identified (Filtered from {len(crawled_pages)} Total Pages)
                </div>
                <div style="color: #94A3B8; font-size: 0.82rem; margin-top: 2px;">
                    Excluded non-commercial utility pages (About/Contact/History/Legal). Each page will receive <b>2 Focus Keywords + 1 Long-Tail Keyword</b> with <b>Zero Cannibalization</b>.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🔥 Run AI Keyword Mapping Engine (2 Focus + 1 Long-Tail)", type="primary", use_container_width=True):
            ai_key_active = st.session_state.get(f"api_key_{ai_provider}", "").strip()
            total_p = len(filtered_pages)
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            assigned_registry = set()

            for idx, p in enumerate(filtered_pages):
                status_text.markdown(f"🤖 **AI Bot analyzing ({idx+1}/{total_p}):** `{p['url']}`")
                
                if ai_provider != "Autonomous (Live Google Suggest Engine)" and ai_key_active:
                    kw_data = analyze_page_with_ai_bot(
                        page_data=p,
                        api_key=ai_key_active,
                        provider=ai_provider,
                        model_name=selected_model,
                        country_name=target_country.split(" ", 1)[-1],
                        industry_niche=industry_niche_input,
                        assigned_registry=assigned_registry
                    )
                else:
                    kw_data = generate_algorithmic_page_keywords(
                        page_data=p,
                        country_name=target_country.split(" ", 1)[-1],
                        industry_niche=industry_niche_input,
                        assigned_registry=assigned_registry
                    )
                results.append(kw_data)
                progress_bar.progress((idx + 1) / total_p)
                time.sleep(0.04)

            st.session_state["kw_mapping_results"] = results
            status_text.empty()
            progress_bar.empty()
            st.success(f"🎉 Successfully mapped **{len(results)} pages** with **{len(results) * 3} targeted keywords** without cannibalization!")

    # ==============================================================================
    # STEP 3: INTERACTIVE RESULTS DASHBOARD & EXPORTS
    # ==============================================================================
    mapped_results = st.session_state.get("kw_mapping_results", [])
    if mapped_results:
        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

        # KPI Telemetry
        total_p = len(mapped_results)
        total_kw = total_p * 3
        cannibal_warnings = detect_keyword_cannibalization(mapped_results)

        st.markdown(f"""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 1.5rem;">
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 1.1rem; text-align: center;">
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #94A3B8; text-transform: uppercase;">MONEY PAGES MAPPED</div>
                <div style="font-size: 1.85rem; font-weight: 900; color: #34D399; margin: 4px 0;">{total_p}</div>
                <div style="font-size: 0.72rem; color: #CBD5E1;">Products & Services</div>
            </div>
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 1.1rem; text-align: center;">
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #94A3B8; text-transform: uppercase;">TARGET KEYWORDS GENERATED</div>
                <div style="font-size: 1.85rem; font-weight: 900; color: #38BDF8; margin: 4px 0;">{total_kw}</div>
                <div style="font-size: 0.72rem; color: #CBD5E1;">2 Focus + 1 Long-Tail Per Page</div>
            </div>
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; padding: 1.1rem; text-align: center;">
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #94A3B8; text-transform: uppercase;">INDUSTRY GROUNDED</div>
                <div style="font-size: 1.15rem; font-weight: 900; color: #F59E0B; margin: 6px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{industry_niche_input}</div>
                <div style="font-size: 0.72rem; color: #CBD5E1;">Strict Niche Relevance</div>
            </div>
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid {'rgba(239, 68, 68, 0.4)' if len(cannibal_warnings) > 0 else 'rgba(16, 185, 129, 0.3)'}; border-radius: 12px; padding: 1.1rem; text-align: center;">
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #94A3B8; text-transform: uppercase;">CANNIBALIZATION STATUS</div>
                <div style="font-size: 1.85rem; font-weight: 900; color: {'#EF4444' if len(cannibal_warnings) > 0 else '#34D399'}; margin: 4px 0;">{len(cannibal_warnings)}</div>
                <div style="font-size: 0.72rem; color: #CBD5E1;">{'Conflicts Detected' if len(cannibal_warnings) > 0 else '100% Unique Targets'}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Download Buttons
        col_e1, col_e2 = st.columns([1, 1])
        with col_e1:
            excel_bytes = generate_keyword_mapping_excel(mapped_results)
            st.download_button(
                "📥 Export Complete Keyword Mapping (Multi-Tab Excel .xlsx)",
                data=excel_bytes,
                file_name=f"Keyword_Mapping_{int(time.time())}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with col_e2:
            df_out = pd.DataFrame(mapped_results)
            csv_bytes = df_out.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Export Keyword Mapping (CSV)",
                data=csv_bytes,
                file_name=f"Keyword_Mapping_{int(time.time())}.csv",
                mime="text/csv",
                use_container_width=True
            )

        st.markdown("### 📋 Interactive Keyword Mapping Dashboard (2 Focus Keywords + 1 Long-Tail)")

        # Interactive Row Cards with 2 Focus Keywords + 1 Long-Tail Keyword
        for idx, r in enumerate(mapped_results):
            with st.expander(f"📍 #{idx+1} | {r['focus_keyword_1']} — {r['page_category']} ({r['url']})", expanded=(idx < 2)):
                col_p1, col_p2, col_p3 = st.columns([1.2, 1.2, 1.4])
                with col_p1:
                    st.markdown(f"""
                    <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 12px; height: 100%;">
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #34D399; font-weight: 700; text-transform: uppercase;">
                            🎯 1. FOCUS KEYWORD 1 (PRIMARY)
                        </div>
                        <div style="color: #F8FAFC; font-size: 1.15rem; font-weight: 800; margin: 6px 0;">
                            {r['focus_keyword_1']}
                        </div>
                        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
                            <span style="background: rgba(16, 185, 129, 0.2); color: #34D399; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['focus_1_intent']}</span>
                            <span style="background: rgba(255,255,255,0.06); color: #CBD5E1; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['focus_1_cpc']}</span>
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
                            🚀 2. FOCUS KEYWORD 2 (SECONDARY)
                        </div>
                        <div style="color: #F8FAFC; font-size: 1.15rem; font-weight: 800; margin: 6px 0;">
                            {r['focus_keyword_2']}
                        </div>
                        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
                            <span style="background: rgba(56, 189, 248, 0.2); color: #38BDF8; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['focus_2_intent']}</span>
                            <span style="background: rgba(255,255,255,0.06); color: #CBD5E1; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;">{r['focus_2_cpc']}</span>
                        </div>
                        <div style="color: #94A3B8; font-size: 0.75rem; margin-top: 8px;">
                            📌 <b>Target Placement:</b> H2 Subheading, Feature specs, Image Alt
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with col_p3:
                    st.markdown(f"""
                    <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 10px; padding: 12px; height: 100%;">
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #F59E0B; font-weight: 700; text-transform: uppercase;">
                            💡 3. LONG-TAIL KEYWORD (BUYER INTENT)
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
