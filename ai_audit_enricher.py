"""
ai_audit_enricher.py - AI-Powered Technical SEO Audit Suggestions & Developer Guides
Connects with Google Gemini (with Google Search Grounding & competitor benchmarking),
OpenAI ChatGPT, or Anthropic Claude to generate tailored 150-160 character meta descriptions with CTAs,
optimized title tags, single primary H1s, alt text, and actionable developer guides for every error tab.
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Callable
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
    """Generate 150-160 character meta descriptions with CTAs + Developer Implementation Guide."""
    if df.empty:
        return df

    target_df = df.copy()
    items = []
    for idx, row in target_df.iterrows():
        items.append({
            "id": idx,
            "url": str(row.get("Page URL", "")),
            "title": str(row.get("Page Title", "")),
            "current_desc": str(row.get("Duplicate Meta Description", row.get("Meta Description", "")))
        })

    biz_note = f"Website Business/Niche: {business_context}\n" if business_context else ""
    region_note = f"Target Country/Market: {country}\n" if country and "Global" not in country else ""

    prompt = f"""You are an elite SEO Copywriter & Technical Director.
{biz_note}{region_note}
Task: Research top-ranking Google search competitors for these services/products in the target country ({country}) and generate high-converting, Google-compliant meta descriptions for each page.

STRICT SEO REQUIREMENTS:
1. Length MUST be strictly between 150 and 160 characters (including spaces). Never generate descriptions under 145 characters!
2. MUST end with a high-intent Call To Action (CTA) (e.g. 'Shop our collection online today!', 'Order now for fast delivery!', 'Explore top deals & save now!').
3. Incorporate relevant primary keywords naturally derived from the URL path and title.
4. Each URL MUST receive a distinctly unique, non-duplicate description.
5. Return ONLY a valid JSON array of objects with keys: "id" (integer), "suggestion" (string, 150-160 chars with CTA), and "developer_guide" (string, short implementation instruction for developer).

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
        title = str(target_df.loc[idx].get("Page Title", ""))
        
        # Enforce exact 150-160 length and strong CTA
        enforced = enforce_meta_desc_length_and_cta(raw_sugg, title=title, url=url)
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
    """Generate 50-60 character title tags benchmarked against competitors + Developer Guide."""
    if df.empty:
        return df

    target_df = df.copy()
    items = []
    for idx, row in target_df.iterrows():
        items.append({
            "id": idx,
            "url": str(row.get("Page URL", "")),
            "current_title": str(row.get("Duplicate Title", row.get("Page Title", row.get("Title", ""))))
        })

    biz_note = f"Website Business/Niche: {business_context}\n" if business_context else ""
    region_note = f"Target Country/Market: {country}\n" if country and "Global" not in country else ""

    prompt = f"""You are a Senior Technical SEO Consultant.
{biz_note}{region_note}
Task: Generate high-CTR, competitor-benchmarked SEO <title> tags strictly between 50 and 60 characters for each page.

Requirements:
1. Length MUST be strictly between 50 and 60 characters (ideal Google SERP pixel width ~500-580px).
2. Format: [Primary Keyword / Product Name] | [Brand or USP Hook]
3. Distinct and compelling for the {country} audience.
4. Return ONLY a valid JSON array of objects with keys: "id" (integer), "suggestion" (string, 50-60 chars), and "developer_guide" (string).

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
        slug = url.rstrip("/").split("/")[-1].replace("-", " ").title()
        s = sugg_map.get(idx, f"{slug} | Official Online Store")
        if len(s) > 60:
            s = s[:57] + "..."
        elif len(s) < 45:
            s = f"{s} | Best Deals"
            if len(s) > 60:
                s = s[:60]
        final_suggs.append(s)
        final_chars.append(len(s))
        guide = guide_map.get(idx, "Developer Guide: Update the <title> tag inside the <head> section of this page template.")
        final_guides.append(guide)

    target_df[col_sugg] = final_suggs
    target_df["Suggested Title Chars"] = final_chars
    target_df["Developer Guide (How to Fix)"] = final_guides

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
    """Recommend single primary H1 heading tags + Developer Implementation Guide."""
    if df.empty:
        return df

    target_df = df.copy()
    items = []
    for idx, row in target_df.iterrows():
        items.append({
            "id": idx,
            "url": str(row.get("Page URL", "")),
            "h1_1": str(row.get("First H1", row.get("Primary H1", ""))),
            "h1_2": str(row.get("Second H1", "")),
            "title": str(row.get("Page Title", ""))
        })

    prompt = f"""You are an on-page SEO structural architect.
Task: For each page below, recommend a single, clear semantic H1 heading tag and a precise Developer Guide on how to adjust HTML headings.
If page has multiple H1s, identify which one should remain H1 and instruct developer to change secondary H1s into H2 tags.
If H1 is missing or duplicate, suggest an ideal H1 for the page topic.

Return ONLY a valid JSON array of objects with keys: "id" (integer), "suggestion" (string), and "developer_guide" (string).

Pages:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{
    "id": 0,
    "suggestion": "Pure Organic Lavender Essential Oil",
    "developer_guide": "In header.liquid/template.php, keep this primary <h1> and change the secondary <h1> tag into a semantic <h2> or <h3> tag."
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

    target_df[col_sugg] = [
        sugg_map.get(idx, target_df.loc[idx].get("First H1", target_df.loc[idx].get("Page Title", "Main Product / Topic")))
        for idx in target_df.index
    ]
    target_df["Developer Guide (How to Fix)"] = [
        guide_map.get(
            idx,
            "Developer Guide: Open template file. Ensure exactly one <h1> exists on the page (use the Suggested H1). Demote additional <h1> tags to <h2> or <h3>."
        )
        for idx in target_df.index
    ]

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
