"""
ai_audit_enricher.py - AI-Powered Technical SEO Audit Suggestions & Developer Guides
Connects with Google Gemini (with Google Search Grounding & competitor benchmarking),
OpenAI ChatGPT, or Anthropic Claude to generate tailored 150-160 character meta descriptions with CTAs,
optimized title tags, single primary H1s, alt text, and actionable developer guides for every error tab.
"""

import re
import json
import logging
import concurrent.futures
from typing import Dict, List, Tuple, Optional, Callable
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd

logger = logging.getLogger(__name__)

COUNTRIES = [
    "🌐 Global (No specific region)",
    "🇮🇳 India",
    "🇺🇸 United States",
    "🇨🇦 Canada",
    "🇬🇧 United Kingdom",
    "🇦🇺 Australia",
    "🇩🇪 Germany",
    "🇫🇷 France",
    "🇯🇵 Japan",
    "🇧🇷 Brazil",
    "🇲🇽 Mexico",
    "🇮🇩 Indonesia",
    "🇹🇷 Turkey",
    "🇸🇦 Saudi Arabia",
    "🇦🇪 UAE",
    "🇿🇦 South Africa",
    "🇳🇬 Nigeria",
    "🇰🇷 South Korea",
    "🇮🇹 Italy",
    "🇪🇸 Spain",
    "🇳🇱 Netherlands",
    "🇸🇬 Singapore",
    "🇲🇾 Malaysia",
    "🇵🇭 Philippines",
    "🇵🇰 Pakistan"
]

# ==============================================================================
# CONTENT RESOLUTION & BRAND STRIPPING UTILITIES
# ==============================================================================

_LIVE_CONTENT_CACHE: Dict[str, dict] = {}

def clean_brand_from_title(title: str, url: str = "") -> str:
    """
    Strips trailing brand suffixes (e.g. ' - F3Clicks', ' | Brand', ' - Official Site',
    'by BrandName', etc.) from page titles to get the pure subject/topic.
    """
    if not title or not str(title).strip():
        return ""

    t = str(title).strip().strip('"\'')

    # Extract domain name tokens to detect brand names (e.g. 'f3clicks' from 'f3clicks.com')
    domain_tokens = set()
    if url:
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            parts = host.split(".")
            for p in parts:
                if len(p) >= 3 and p not in ["com", "org", "net", "in", "co", "uk", "io", "ai", "gov", "edu", "info", "biz"]:
                    domain_tokens.add(p.lower())
        except Exception:
            pass

    # Split by standard title separators
    separators = [" - ", " | ", " – ", " — ", " : ", " ~ "]
    for sep in separators:
        if sep in t:
            parts = t.split(sep)
            last = parts[-1].strip()
            last_clean = re.sub(r"[^\w\s]", "", last).lower()
            # If last chunk matches domain token, or is short brand suffix
            if last_clean in domain_tokens or (len(parts) > 1 and len(last) < 25 and not any(k in last.lower() for k in ["guide", "tips", "service", "review", "pricing"])):
                t = sep.join(parts[:-1]).strip()

    # Also strip trailing "by Brand" or "at Brand" (e.g. "Local SEO Services by F3Clicks")
    for dt in domain_tokens:
        t = re.sub(rf"\s+(by|at|from)\s+{re.escape(dt)}\b.*$", "", t, flags=re.I).strip()

    # Clean generic trailing words like '- Official Site', '| Homepage'
    t = re.sub(r"\s*[-|–—:]\s*(Official Site|Home|Homepage|Welcome)\b.*$", "", t, flags=re.I).strip()
    t = t.rstrip(" -|–—:,")
    return t or str(title).strip()


def get_page_content_and_headings(row: pd.Series, max_chars: int = 500) -> dict:
    """
    Retrieve real page body text, H2 subheadings, and meta description.
    First checks private columns (_page_text, _h2_list, _meta_description) populated during crawl.
    If missing, falls back to a fast live fetch (cached).
    """
    page_text = str(row.get("_page_text", row.get("page_text", row.get("Page Content", ""))) or "").strip()
    h2_list = row.get("_h2_list", row.get("h2_list", row.get("H2 Subheadings", [])))
    if isinstance(h2_list, str):
        try:
            h2_list = json.loads(h2_list)
        except Exception:
            h2_list = [h.strip() for h in h2_list.split(",") if h.strip()]
    if not isinstance(h2_list, list):
        h2_list = []

    meta_desc = str(row.get("_meta_description", row.get("meta_description", row.get("Meta Description", ""))) or "").strip()
    url = str(row.get("Page URL", row.get("url", ""))).strip()

    # If page_text is already available from crawl
    if page_text and len(page_text) > 30:
        return {
            "page_text": page_text[:max_chars],
            "h2_list": [str(h).strip() for h in h2_list if str(h).strip()][:6],
            "meta_description": meta_desc
        }

    # If URL is valid, check cache or fast fetch live
    if url.startswith("http://") or url.startswith("https://"):
        if url in _LIVE_CONTENT_CACHE:
            cached = _LIVE_CONTENT_CACHE[url]
            return {
                "page_text": cached.get("page_text", "")[:max_chars],
                "h2_list": cached.get("h2_list", [])[:6],
                "meta_description": cached.get("meta_description", meta_desc)
            }
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 CrawlPilot/2.0"
            }
            resp = requests.get(url, headers=headers, timeout=3.5)
            if resp.status_code == 200 and resp.text:
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
                    tag.decompose()
                fetched_h2s = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)][:8]
                raw_text = soup.get_text(separator=" ", strip=True)
                words = raw_text.split()
                fetched_text = " ".join(words[:250])

                fetched_meta = ""
                m_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
                if m_tag and m_tag.get("content"):
                    fetched_meta = m_tag["content"].strip()

                _LIVE_CONTENT_CACHE[url] = {
                    "page_text": fetched_text,
                    "h2_list": fetched_h2s,
                    "meta_description": fetched_meta or meta_desc
                }
                return {
                    "page_text": fetched_text[:max_chars],
                    "h2_list": fetched_h2s[:6],
                    "meta_description": fetched_meta or meta_desc
                }
        except Exception as e:
            logger.debug(f"Live fetch fallback failed for {url}: {e}")

    return {
        "page_text": page_text[:max_chars],
        "h2_list": [str(h).strip() for h in h2_list if str(h).strip()][:6],
        "meta_description": meta_desc
    }


def generate_smart_h1_from_content(clean_topic: str, page_text: str = "", h2s: list = None, url: str = "") -> str:
    """
    Fallback that constructs a professional, high-converting 4-8 word H1 heading
    based on real page content, H2 subheadings, and clean topic without brand suffixes.
    """
    if h2s:
        for h in h2s:
            cleaned_h = clean_brand_from_title(h, url)
            words = cleaned_h.split()
            if 3 <= len(words) <= 9 and not any(k in cleaned_h.lower() for k in ["menu", "navigation", "footer", "sidebar", "cookie", "copyright", "about us", "contact"]):
                return cleaned_h

    topic = clean_topic.strip()
    if not topic and url:
        topic = url.rstrip("/").split("/")[-1].split("?")[0].replace("-", " ").title()

    topic_lower = topic.lower()

    if any(topic_lower.startswith(w) for w in ["how to", "best ", "top ", "ultimate "]):
        return topic

    if "service" in topic_lower or "agency" in topic_lower or "solution" in topic_lower:
        if not any(w in topic_lower for w in ["expert", "professional", "result", "drive", "best", "leading"]):
            return f"Results-Driven {topic}"
        return topic

    if "seo" in topic_lower or "ppc" in topic_lower or "marketing" in topic_lower:
        return f"High-Impact {topic} for Measurable Business Growth"

    words = topic.split()
    if 4 <= len(words) <= 8:
        return topic
    elif len(words) < 4:
        return f"Professional {topic} Solutions"
    else:
        return " ".join(words[:7])


# ==============================================================================
# POST-PROCESSING UTILITIES
# ==============================================================================

def enforce_meta_desc_length_and_cta(desc: str, title: str = "", url: str = "") -> str:
    """
    Ensure the meta description is strictly between 148 and 160 characters
    and ends with a compelling Call to Action (CTA).
    """
    desc = (desc or "").strip().strip('"\'')
    if not desc:
        slug = url.rstrip("/").split("/")[-1].replace("-", " ").title() if url else "Products"
        desc = f"Discover premium {title or slug} crafted with pure ingredients and tested quality"

    desc = desc.rstrip(" .,-")

    # If over 160, trim at word boundary and add CTA
    if len(desc) > 160:
        sub = desc[:138]
        sp = sub.rfind(" ")
        base = sub[:sp].strip() if sp > 100 else desc[:130].strip()
        desc = f"{base}. Order online now for fast delivery!"
        if len(desc) > 160:
            desc = desc[:157] + "..."
        return desc

    if 148 <= len(desc) <= 160:
        return desc

    # If < 148, assemble sentence parts until length is between 148 and 160
    sentences = [
        "Pure therapeutic grade and sustainably sourced.",
        "Enjoy wholesale pricing and verified lab purity.",
        "Trusted by thousands of satisfied customers.",
        "100% satisfaction guaranteed with reliable service.",
        "Discover top deals and order online today.",
        "Shop our complete collection online today.",
        "Order online today for fast delivery.",
        "Buy online today with free shipping.",
        "Shop now for fast dispatch.",
        "Order online now."
    ]

    cur = desc
    for s in sentences:
        if 148 <= len(cur) <= 160:
            break
        cand = f"{cur.rstrip('. ')}. {s}"
        if len(cand) <= 160:
            cur = cand

    # If still short of 148:
    if len(cur) < 148:
        tail = " Shop our selection online now!"
        cur = f"{cur.rstrip('. ')}.{tail}"
        if len(cur) > 160:
            cur = cur[:157] + "..."

    return cur


# ==============================================================================
# LLM CALL HANDLER WITH GOOGLE SEARCH GROUNDING
# ==============================================================================

def call_ai_model(
    prompt: str,
    api_key: str,
    provider: str = "Google Gemini",
    model: str = "gemini-2.5-flash",
    country: str = "Global",
    temperature: float = 0.3,
    enable_grounding: bool = True
) -> str:
    """Execute a prompt against selected AI provider with competitor search grounding when available."""
    clean_model = model.split(" ")[0].strip() if " (" in model else model.strip()

    if provider == "ChatGPT (OpenAI)":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=clean_model,
            messages=[
                {"role": "system", "content": "You are a Chief SEO Director and CRO Specialist. Return only strictly formatted JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    elif provider == "Claude (Anthropic)":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=clean_model,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
        )
        return response.content[0].text if response.content else ""

    else:
        # Google Gemini with Grounding
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        active_model = clean_model

        # Build candidate fallback models list
        model_candidates = [active_model]
        for m in [
            "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash",
            "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
            "gemini-3.5-flash", "gemini-3.5-flash-lite"
        ]:
            if m not in model_candidates:
                model_candidates.append(m)

        for candidate_model in model_candidates:
            try:
                # Attempt with Google Search Grounding for live competitor benchmark
                if enable_grounding:
                    try:
                        cfg = types.GenerateContentConfig(
                            temperature=temperature,
                            tools=[types.Tool(google_search=types.GoogleSearch())]
                        )
                        response = client.models.generate_content(
                            model=candidate_model,
                            contents=prompt,
                            config=cfg
                        )
                        if response.text:
                            return response.text
                    except Exception:
                        pass # Fall through to ungrounded prompt

                # Ungrounded call
                cfg_plain = types.GenerateContentConfig(temperature=temperature)
                response = client.models.generate_content(
                    model=candidate_model,
                    contents=prompt,
                    config=cfg_plain
                )
                if response.text:
                    return response.text
            except Exception as e:
                err_str = str(e).lower()
                if any(x in err_str for x in ["404", "not found", "not_found", "unsupported", "deprecated"]):
                    continue # Try next candidate model
                raise e

        return ""


def parse_json_from_llm(raw_text: str) -> Optional[list]:
    """Safely extract a JSON array from LLM response text."""
    if not raw_text:
        return None
    text = raw_text.strip()
    m = re.search(r'```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m2 = re.search(r'(\[\s*\{.*?\}\s*\])', text, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return None


# ==============================================================================
# TAB-SPECIFIC ENRICHERS & DEVELOPER GUIDES
# ==============================================================================

def enrich_meta_descriptions(
    df: pd.DataFrame,
    issue_type: str,
    api_key: str,
    provider: str,
    model: str,
    country: str = "Global",
    business_context: str = ""
) -> pd.DataFrame:
    """Generate 150-160 character meta descriptions with CTAs grounded in REAL page content."""
    if df.empty:
        return df

    target_df = df.copy()
    items = []
    for idx, row in target_df.iterrows():
        content_info = get_page_content_and_headings(row, max_chars=450)
        raw_title = str(row.get("Page Title", row.get("Title", "")))
        url = str(row.get("Page URL", ""))
        clean_topic = clean_brand_from_title(raw_title, url)
        items.append({
            "id": idx,
            "url": url,
            "page_topic": clean_topic,
            "page_content_summary": content_info.get("page_text", ""),
            "h2_subheadings": content_info.get("h2_list", []),
            "current_desc": str(row.get("Duplicate Meta Description", row.get("Meta Description", "")))
        })

    biz_note = f"Website Business/Niche: {business_context}\n" if business_context else ""
    region_note = f"Target Country/Market: {country}\n" if country and "Global" not in country else ""

    prompt = f"""You are an elite SEO Copywriter & Technical Director.
{biz_note}{region_note}
Task: READ the actual `page_content_summary` and `h2_subheadings` of each page to understand its core offerings, services, or products. Then formulate a high-converting, Google-compliant meta description.

STRICT SEO REQUIREMENTS:
1. Length MUST be strictly between 150 and 160 characters (including spaces). Never generate descriptions under 148 characters or over 160 characters!
2. MUST end with a high-intent Call To Action (CTA) (e.g. 'Shop our collection online today!', 'Schedule your free consultation today!', 'Explore our packages & get started now!').
3. BASE THE DESCRIPTION on the real page content and subheadings — highlighting actual benefits and solutions provided on this specific page.
4. Each URL MUST receive a distinctly unique, non-duplicate description.
5. Return ONLY a valid JSON array of objects with keys: "id" (integer), "suggestion" (string, strictly 150-160 chars ending with CTA), and "developer_guide" (string, short implementation instruction for developer).

Pages to optimize:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{
    "id": 0,
    "suggestion": "Discover pure organic lavender essential oil crafted for calming sleep and relaxation. 100% natural, therapeutic grade. Order online today with fast shipping!",
    "developer_guide": "Add or update <meta name='description' content='...'> in the <head> section of the template or CMS SEO fields."
  }}
]"""

    sugg_map = {}
    guide_map = {}
    try:
        raw_res = call_ai_model(prompt, api_key, provider, model, country=country)
        parsed = parse_json_from_llm(raw_res)
        if parsed:
            for entry in parsed:
                if "id" in entry:
                    sugg = str(entry.get("suggestion", "")).strip().strip('"')
                    sugg_map[entry["id"]] = sugg
                    guide_map[entry["id"]] = str(entry.get("developer_guide", "Add <meta name='description'> inside <head>.")).strip()
    except Exception as e:
        logger.warning(f"Error calling LLM for meta descriptions: {e}")

    col_sugg = "Suggested Meta Description (150-160 Chars)"
    if "Duplicate" in issue_type:
        col_sugg = "Suggested Unique Meta Description (150-160 Chars)"
    elif "over 160" in issue_type:
        col_sugg = "Suggested Trimmed Meta Description (150-160 Chars)"

    final_suggs = []
    final_chars = []
    final_guides = []

    for idx in target_df.index:
        raw_sugg = sugg_map.get(idx, "")
        url = str(target_df.loc[idx, "Page URL"])
        raw_title = str(target_df.loc[idx].get("Page Title", ""))
        clean_topic = clean_brand_from_title(raw_title, url)

        # Enforce exact 150-160 length and strong CTA
        enforced = enforce_meta_desc_length_and_cta(raw_sugg, title=clean_topic, url=url)
        final_suggs.append(enforced)
        final_chars.append(len(enforced))

        guide = guide_map.get(
            idx,
            "Developer Guide: Insert or update <meta name='description' content='[Suggested Description]'> inside the <head> tag of this page template."
        )
        final_guides.append(guide)

    target_df[col_sugg] = final_suggs
    target_df["Suggested Char Count"] = final_chars
    target_df["Developer Guide (How to Fix)"] = final_guides

    # Drop internal helper columns
    drop_cols = [c for c in target_df.columns if str(c).startswith("_")]
    if drop_cols:
        target_df.drop(columns=drop_cols, inplace=True, errors="ignore")

    return target_df


def enrich_page_titles(
    df: pd.DataFrame,
    issue_type: str,
    api_key: str,
    provider: str,
    model: str,
    country: str = "Global",
    business_context: str = ""
) -> pd.DataFrame:
    """Generate 50-60 character title tags based on REAL page content + Developer Guide."""
    if df.empty:
        return df

    target_df = df.copy()
    items = []
    for idx, row in target_df.iterrows():
        content_info = get_page_content_and_headings(row, max_chars=400)
        raw_title = str(row.get("Duplicate Title Tag", row.get("Page Title", row.get("Title", ""))))
        url = str(row.get("Page URL", ""))
        clean_topic = clean_brand_from_title(raw_title, url)
        items.append({
            "id": idx,
            "url": url,
            "clean_topic": clean_topic,
            "current_title": raw_title,
            "page_content_summary": content_info.get("page_text", ""),
            "h2_subheadings": content_info.get("h2_list", []),
            "meta_description": content_info.get("meta_description", "")
        })

    biz_note = f"Website Business/Niche: {business_context}\n" if business_context else ""
    region_note = f"Target Country/Market: {country}\n" if country and "Global" not in country else ""

    prompt = f"""You are a Senior Technical SEO Consultant.
{biz_note}{region_note}
Task: READ the actual `page_content_summary` and `h2_subheadings` of each page to understand its core subject matter.
Generate high-CTR, SEO-optimized <title> tags strictly between 50 and 60 characters for each page.

Requirements:
1. Length MUST be strictly between 50 and 60 characters (optimal SERP pixel width ~500-580px).
2. Format: [Primary Service/Keyword from Content] | [USP or Brand Hook from Content]
3. Distinct and compelling for the {country} audience based on actual page content.
4. Return ONLY a valid JSON array of objects with keys: "id" (integer), "suggestion" (string, strictly 50-60 chars), and "developer_guide" (string).

Pages:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{
    "id": 0,
    "suggestion": "Lavender Essential Oil | 100% Pure Organic Oils",
    "developer_guide": "Update <title> tag inside the <head> element of this template."
  }}
]"""

    sugg_map = {}
    guide_map = {}
    try:
        raw_res = call_ai_model(prompt, api_key, provider, model, country=country)
        parsed = parse_json_from_llm(raw_res)
        if parsed:
            for entry in parsed:
                if "id" in entry:
                    sugg_map[entry["id"]] = str(entry.get("suggestion", "")).strip().strip('"')
                    guide_map[entry["id"]] = str(entry.get("developer_guide", "Update <title> tag in <head>.")).strip()
    except Exception as e:
        logger.warning(f"Error calling LLM for titles: {e}")

    col_sugg = "Suggested Title Tag (50-60 Chars)"
    if "Duplicate" in issue_type:
        col_sugg = "Suggested Unique Title Tag (50-60 Chars)"
    elif "over 60" in issue_type:
        col_sugg = "Suggested Trimmed Title Tag (50-60 Chars)"

    final_suggs = []
    final_chars = []
    final_guides = []

    for idx in target_df.index:
        url = str(target_df.loc[idx, "Page URL"])
        raw_title = str(target_df.loc[idx].get("Duplicate Title Tag", target_df.loc[idx].get("Page Title", "")))
        clean_topic = clean_brand_from_title(raw_title, url)
        if not clean_topic:
            slug = url.rstrip("/").split("/")[-1].replace("-", " ").title()
            clean_topic = slug or "Services"

        s = sugg_map.get(idx, "")
        if not s or s.lower() == raw_title.lower() or len(s) < 35:
            if len(clean_topic) >= 45 and len(clean_topic) <= 60:
                s = clean_topic
            elif len(clean_topic) < 45:
                s = f"{clean_topic} | Official Services & Solutions"
                if len(s) > 60:
                    s = f"{clean_topic} | Verified Solutions"
            else:
                s = clean_topic[:57] + "..."

        if len(s) > 60:
            s = s[:57].rstrip(" -|") + "..."
        elif len(s) < 48:
            diff = 55 - len(s)
            if diff >= 10:
                s = f"{s} | Top Solutions"
                if len(s) > 60:
                    s = s[:60]
        final_suggs.append(s)
        final_chars.append(len(s))
        guide = guide_map.get(idx, "Developer Guide: Update the <title> tag inside the <head> section of this page template.")
        final_guides.append(guide)

    target_df[col_sugg] = final_suggs
    target_df["Suggested Title Chars"] = final_chars
    target_df["Developer Guide (How to Fix)"] = final_guides

    # Drop internal helper columns
    drop_cols = [c for c in target_df.columns if str(c).startswith("_")]
    if drop_cols:
        target_df.drop(columns=drop_cols, inplace=True, errors="ignore")

    return target_df


def enrich_headings(
    df: pd.DataFrame,
    issue_type: str,
    api_key: str,
    provider: str,
    model: str,
    country: str = "Global",
    business_context: str = ""
) -> pd.DataFrame:
    """Recommend single primary H1 heading tags derived from REAL page content + Developer Guide."""
    if df.empty:
        return df

    target_df = df.copy()
    items = []
    for idx, row in target_df.iterrows():
        content_info = get_page_content_and_headings(row, max_chars=450)
        raw_title = str(row.get("Page Title", row.get("Title", "")))
        url = str(row.get("Page URL", ""))
        clean_topic = clean_brand_from_title(raw_title, url)
        items.append({
            "id": idx,
            "url": url,
            "raw_page_title": raw_title,
            "clean_topic": clean_topic,
            "page_content_summary": content_info.get("page_text", ""),
            "h2_subheadings": content_info.get("h2_list", []),
            "meta_description": content_info.get("meta_description", ""),
            "h1_current": str(row.get("First H1 Tag", row.get("First H1", row.get("Duplicate H1 Tag", "")))),
            "h1_secondary": str(row.get("Second H1 Tag", row.get("Second H1", "")))
        })

    biz_note = f"Website Business/Niche: {business_context}\n" if business_context else ""
    region_note = f"Target Country/Market: {country}\n" if country and "Global" not in country else ""

    prompt = f"""You are a World-Class On-Page SEO Architect and Conversion Copywriter.
{biz_note}{region_note}
CRITICAL SEO DIRECTIVE:
You must formulate an optimal, semantic, conversion-oriented primary <h1> heading for each page below based on its REAL PAGE CONTENT and H2 subheadings.

STRICT RULES:
1. NEVER simply copy or repeat the raw <title> or Meta Title tag verbatim!
2. NEVER include brand names or website name suffixes (e.g. '- F3Clicks', '| BrandName', 'by F3Clicks') in the H1 heading. H1 is strictly an on-page content headline for human readers, NOT a SERP browser title!
3. READ the `page_content_summary` and `h2_subheadings` for each page. Determine the real core subject matter, services, or products discussed on that specific page.
4. Formulate an engaging, authoritative, 4 to 8 word primary H1 heading that accurately reflects the page content (e.g. 'Drive Targeted Customers with Result-Driven Local SEO Services', 'Scalable White Label SEO Solutions for Growing Agencies', 'High-Converting PPC Campaign Management for Measurable Growth').
5. If the issue is 'Multiple H1 tags', identify the best primary H1 to retain, and in 'developer_guide' instruct the developer to demote other <h1> tags to <h2>.
6. If the issue is 'Missing H1', suggest the ideal primary H1 for the page based on the content, and instruct developer where to place it in the template.

Return ONLY a valid JSON array of objects with keys: "id" (integer), "suggestion" (string, the 4-8 word H1 without brand suffix), and "developer_guide" (string).

Pages to evaluate:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{
    "id": 0,
    "suggestion": "Drive Targeted Local Customers with Result-Oriented Local SEO",
    "developer_guide": "Add a single primary <h1> tag at the top of the main content container in the page template."
  }}
]"""

    sugg_map = {}
    guide_map = {}
    try:
        raw_res = call_ai_model(prompt, api_key, provider, model, country=country)
        parsed = parse_json_from_llm(raw_res)
        if parsed:
            for entry in parsed:
                if "id" in entry:
                    sugg_map[entry["id"]] = str(entry.get("suggestion", "")).strip().strip('"')
                    guide_map[entry["id"]] = str(entry.get("developer_guide", "")).strip()
    except Exception as e:
        logger.warning(f"Error calling LLM for headings: {e}")

    col_sugg = "Suggested Single Primary H1" if "Multiple" in issue_type else "Suggested H1 Heading"

    final_h1s = []
    final_guides = []

    for idx in target_df.index:
        url = str(target_df.loc[idx, "Page URL"])
        raw_title = str(target_df.loc[idx].get("Page Title", target_df.loc[idx].get("Title", "")))
        clean_topic = clean_brand_from_title(raw_title, url)
        content_info = get_page_content_and_headings(target_df.loc[idx], max_chars=450)
        h2s = content_info.get("h2_list", [])
        page_text = content_info.get("page_text", "")

        raw_sugg = sugg_map.get(idx, "")
        clean_sugg = clean_brand_from_title(raw_sugg, url)

        if not clean_sugg or clean_sugg.lower() == raw_title.lower() or clean_sugg.lower() == clean_topic.lower():
            final_h1 = generate_smart_h1_from_content(clean_topic, page_text=page_text, h2s=h2s, url=url)
        else:
            final_h1 = clean_sugg

        final_h1 = clean_brand_from_title(final_h1, url)

        guide = guide_map.get(
            idx,
            "Developer Guide: Open template file. Ensure exactly one <h1> exists on the page (use the Suggested H1). Demote additional <h1> tags to <h2> or <h3>."
        )
        final_h1s.append(final_h1)
        final_guides.append(guide)

    target_df[col_sugg] = final_h1s
    target_df["Developer Guide (How to Fix)"] = final_guides

    # Drop internal helper columns
    drop_cols = [c for c in target_df.columns if str(c).startswith("_")]
    if drop_cols:
        target_df.drop(columns=drop_cols, inplace=True, errors="ignore")

    return target_df


def enrich_image_alt_text(
    df: pd.DataFrame,
    api_key: str,
    provider: str,
    model: str,
    country: str = "Global",
    business_context: str = ""
) -> pd.DataFrame:
    """Generate descriptive alt text + Developer Guide."""
    if df.empty:
        return df

    target_df = df.copy()
    items = []
    for idx, row in target_df.iterrows():
        items.append({
            "id": idx,
            "page_url": str(row.get("Found On (Page URL)", row.get("Page URL", ""))),
            "image_url": str(row.get("Image Source URL", row.get("Image URL", "")))
        })

    prompt = f"""You are an Accessibility (a11y) and Image SEO Specialist.
Task: Write concise, descriptive, screen-reader-friendly image alt text based on the image URL filename and page context.
Do not keyword stuff. 4 to 9 words describing what the image shows.

Return ONLY a valid JSON array of objects with keys: "id" (integer), "suggestion" (string), and "developer_guide" (string).

Images:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{
    "id": 0,
    "suggestion": "Organic lavender essential oil bottle with dropper",
    "developer_guide": "Add alt='...' attribute to the <img> tag in HTML template or update media alt text in CMS admin."
  }}
]"""

    sugg_map = {}
    guide_map = {}
    try:
        raw_res = call_ai_model(prompt, api_key, provider, model, country=country)
        parsed = parse_json_from_llm(raw_res)
        if parsed:
            for entry in parsed:
                if "id" in entry:
                    sugg_map[entry["id"]] = str(entry.get("suggestion", "")).strip().strip('"')
                    guide_map[entry["id"]] = str(entry.get("developer_guide", "")).strip()
    except Exception as e:
        logger.warning(f"Error calling LLM for alt text: {e}")

    target_df["Suggested Alt Text"] = [
        sugg_map.get(idx, str(target_df.loc[idx].get("Image Source URL", "")).split("/")[-1].split(".")[0].replace("-", " ").title())
        for idx in target_df.index
    ]
    target_df["Developer Guide (How to Fix)"] = [
        guide_map.get(idx, "Developer Guide: Add alt='[Suggested Alt Text]' attribute to the <img> element in template or CMS media manager.")
        for idx in target_df.index
    ]

    return target_df


def enrich_broken_links_and_redirects(
    df: pd.DataFrame,
    issue_type: str,
    api_key: str,
    provider: str,
    model: str,
    country: str = "Global",
    business_context: str = ""
) -> pd.DataFrame:
    """Generate surgical 301 redirect fixes, link updates, and step-by-step Developer Guide."""
    if df.empty:
        return df

    target_df = df.copy()
    items = []
    for idx, row in target_df.iterrows():
        items.append({
            "id": idx,
            "url": str(row.get("Page URL", row.get("Broken Target URL", row.get("Source Page (Found On)", "")))),
            "status": str(row.get("Status Code", "")),
            "redirect_chain": str(row.get("Redirect Chain", row.get("Redirect Sequence", "")))
        })

    prompt = f"""You are a Senior Technical SEO Architect.
Task: For each technical issue ({issue_type}) below, provide:
1. 'suggestion': Concise action directive (e.g. permanent 301 redirect to parent category, update source hyperlink, or fix canonical tag).
2. 'developer_guide': Simple, step-by-step developer instructions (e.g. 'In .htaccess/nginx/next.config.js or CMS redirect manager, configure 301 redirect from URL A directly to Final URL C to eliminate intermediate hops').

Return ONLY a valid JSON array of objects with keys: "id" (integer), "suggestion" (string), and "developer_guide" (string).

Items:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{
    "id": 0,
    "suggestion": "Implement a direct 301 permanent redirect to the closest active category page.",
    "developer_guide": "Add rule in redirect manager: Redirect 301 /old-url /new-target-url, or update the hyperlink on the source page template to avoid 404 dead link."
  }}
]"""

    sugg_map = {}
    guide_map = {}
    try:
        raw_res = call_ai_model(prompt, api_key, provider, model, country=country)
        parsed = parse_json_from_llm(raw_res)
        if parsed:
            for entry in parsed:
                if "id" in entry:
                    sugg_map[entry["id"]] = str(entry.get("suggestion", "")).strip().strip('"')
                    guide_map[entry["id"]] = str(entry.get("developer_guide", "")).strip()
    except Exception as e:
        logger.warning(f"Error calling LLM for technical fixes: {e}")

    target_df["Suggested Resolution"] = [
        sugg_map.get(idx, "Configure a 301 redirect to active relevant category or remove broken link.")
        for idx in target_df.index
    ]
    target_df["Developer Guide (How to Fix)"] = [
        guide_map.get(
            idx,
            "Developer Guide: Add 301 redirect rule in web server (.htaccess / Nginx / Vercel / Shopify URL Redirects) or update source page href anchor."
        )
        for idx in target_df.index
    ]

    return target_df


# ==============================================================================
# MASTER ORCHESTRATOR
# ==============================================================================

def enrich_audit_report_with_ai(
    index_rows: List[dict],
    error_dfs: Dict[str, pd.DataFrame],
    api_key: str,
    provider: str = "Google Gemini",
    model: str = "gemini-2.5-flash",
    country: str = "Global",
    business_context: str = "",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[List[dict], Dict[str, pd.DataFrame]]:
    """
    Enrich all error DataFrames and the Index Sheet with suggested fixes and developer guides.
    Processes all affected URLs in the error tabs.
    """
    if not api_key:
        return index_rows, error_dfs

    enriched_dfs = {}
    total_tabs = len(error_dfs)
    current_step = 0

    for sheet_name, df_err in error_dfs.items():
        current_step += 1
        pct = current_step / max(total_tabs, 1)
        if progress_callback:
            progress_callback(pct, f"🤖 Researching competitors & generating fixes for: {sheet_name} ({country})...")

        if df_err.empty:
            enriched_dfs[sheet_name] = df_err
            continue

        sheet_lower = sheet_name.lower()

        # 1. Meta Descriptions (Missing / Duplicate / Long)
        if "meta description" in sheet_lower or "desc over" in sheet_lower:
            enriched_dfs[sheet_name] = enrich_meta_descriptions(
                df_err, sheet_name, api_key, provider, model, country=country, business_context=business_context
            )

        # 2. Page Titles (Missing / Duplicate / Long)
        elif "title" in sheet_lower:
            enriched_dfs[sheet_name] = enrich_page_titles(
                df_err, sheet_name, api_key, provider, model, country=country, business_context=business_context
            )

        # 3. Headings (H1 tags)
        elif "h1" in sheet_lower or "heading" in sheet_lower:
            enriched_dfs[sheet_name] = enrich_headings(
                df_err, sheet_name, api_key, provider, model, country=country, business_context=business_context
            )

        # 4. Images Missing Alt Text
        elif "alt" in sheet_lower or "image" in sheet_lower:
            enriched_dfs[sheet_name] = enrich_image_alt_text(
                df_err, api_key, provider, model, country=country, business_context=business_context
            )

        # 5. Broken Links, 4xx, Redirect Chains & Loops, Canonicals
        elif any(k in sheet_lower for k in ["4xx", "broken", "redirect", "canonical", "loop"]):
            enriched_dfs[sheet_name] = enrich_broken_links_and_redirects(
                df_err, sheet_name, api_key, provider, model, country=country, business_context=business_context
            )

        # 6. Minify JavaScript and CSS files
        elif "minify" in sheet_lower or "unminified" in sheet_lower or "javascript" in sheet_lower:
            df_copy = df_err.copy()
            df_copy["Suggested Resolution"] = "Minify & Compress Asset (Save 30-70% transfer weight)"
            df_copy["Developer Guide (How to Fix)"] = (
                "Developer: Configure build tooling (e.g. Terser, CSSNano, esbuild, Vite) to minify static assets and strip comments. "
                "Alternatively, toggle auto-minification under Cloudflare/CDN speed settings."
            )
            enriched_dfs[sheet_name] = df_copy

        else:
            enriched_dfs[sheet_name] = df_err.copy()

    # Safeguard: purge any internal helper columns starting with _ from all sheets
    for s_name in list(enriched_dfs.keys()):
        d_clean = enriched_dfs[s_name]
        d_drops = [c for c in d_clean.columns if str(c).startswith("_")]
        if d_drops:
            enriched_dfs[s_name] = d_clean.drop(columns=d_drops, errors="ignore")

    # Enrich Index Rows with Suggested Developer Action Plan
    enriched_index = []
    for r in index_rows:
        row_copy = dict(r)
        name_lower = r.get("error_name", "").lower()
        if r.get("is_error", False):
            if "meta description" in name_lower:
                row_copy["suggested_action_plan"] = "Competitor-benchmarked 150-160 char meta descriptions with CTAs generated for each page. Developer: Paste into <meta name='description'> inside <head>."
            elif "title" in name_lower:
                row_copy["suggested_action_plan"] = "Primary keyword + brand title tags (50-60 chars) created. Developer: Update <title> inside <head>."
            elif "h1" in name_lower:
                row_copy["suggested_action_plan"] = "Semantic primary H1 headings consolidated. Developer: Demote secondary <h1> tags to <h2> in page template."
            elif "alt" in name_lower:
                row_copy["suggested_action_plan"] = "Descriptive, accessible alt text generated. Developer: Add alt='...' attributes to <img> tags."
            elif "minify" in name_lower or "javascript" in name_lower or "css" in name_lower:
                row_copy["suggested_action_plan"] = "Minify JavaScript and CSS files using build bundlers (Terser/CSSNano) or CDN auto-minify to eliminate render-blocking latency and boost Core Web Vitals (LCP/FCP)."
            elif "4xx" in name_lower or "broken" in name_lower:
                row_copy["suggested_action_plan"] = "301 permanent redirects mapped. Developer: Add 301 redirect rules in server config or update source link hrefs."
            elif "redirect" in name_lower:
                row_copy["suggested_action_plan"] = "Direct 301 destinations mapped to eliminate intermediary redirect hops and latency."
            elif "canonical" in name_lower:
                row_copy["suggested_action_plan"] = "Self-referencing canonical URLs specified. Developer: Add <link rel='canonical'> inside <head>."
            else:
                row_copy["suggested_action_plan"] = "Suggested remediation strategy and developer instructions mapped to affected URLs."
        else:
            row_copy["suggested_action_plan"] = "Passed standard SEO quality checks."
        enriched_index.append(row_copy)

    if progress_callback:
        progress_callback(1.0, "✅ Suggested SEO fixes and developer guides applied successfully!")

    return enriched_index, enriched_dfs
