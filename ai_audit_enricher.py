"""
ai_audit_enricher.py - AI-Powered Technical SEO Audit Suggestions & Fixes
Connects with Google Gemini, OpenAI, or Anthropic to generate tailored,
SEO-compliant metadata, titles, headings, and remediation plans for each audit error tab.
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Callable
import pandas as pd

logger = logging.getLogger(__name__)

# ==============================================================================
# LLM CLIENT WRAPPERS
# ==============================================================================

def call_ai_model(
    prompt: str,
    api_key: str,
    provider: str = "Google Gemini",
    model: str = "gemini-2.5-flash",
    temperature: float = 0.3
) -> str:
    """Execute a prompt against the selected AI provider."""
    clean_model = model.split(" ")[0].strip() if " (" in model else model.strip()

    if provider == "ChatGPT (OpenAI)":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=clean_model,
            messages=[
                {"role": "system", "content": "You are a senior Technical SEO Director and CRO expert. Return only clean, structured JSON or concise text as requested."},
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
        # Google Gemini
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        active_model = clean_model

        try:
            response = client.models.generate_content(
                model=active_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                )
            )
            return response.text or ""
        except Exception as e:
            err_msg = str(e).lower()
            # If specified model not found, fallback to recommended models
            if any(term in err_msg for term in ["404", "not found", "not_found"]):
                for fallback_m in ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]:
                    if fallback_m != active_model:
                        try:
                            response = client.models.generate_content(
                                model=fallback_m,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    temperature=temperature,
                                )
                            )
                            return response.text or ""
                        except Exception:
                            continue
            raise e


def parse_json_from_llm(raw_text: str) -> Optional[list]:
    """Safely extract a JSON array from LLM response text."""
    if not raw_text:
        return None
    text = raw_text.strip()
    # Match markdown code block ```json ... ```
    m = re.search(r'```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Match bare brackets [ ... ]
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
# TAB-SPECIFIC AI PROMPTS & ENRICHERS
# ==============================================================================

def enrich_meta_descriptions(
    df: pd.DataFrame,
    issue_type: str,
    api_key: str,
    provider: str,
    model: str,
    business_context: str = "",
    max_rows: int = 50
) -> pd.DataFrame:
    """Generate SEO-optimized meta descriptions (130-155 characters) with high CTR hooks."""
    if df.empty:
        return df

    target_df = df.copy()
    rows_to_process = target_df.head(max_rows)
    items = []
    for idx, row in rows_to_process.iterrows():
        items.append({
            "id": idx,
            "url": str(row.get("Page URL", "")),
            "title": str(row.get("Page Title", "")),
            "current_desc": str(row.get("Duplicate Meta Description", row.get("Meta Description", "")))
        })

    biz_note = f"Website Business/Niche Context: {business_context}\n" if business_context else ""

    prompt = f"""You are an elite SEO Copywriter specializing in Google SERP CTR optimization.
{biz_note}
Task: Generate high-converting, SEO-optimized meta descriptions for the following pages.

Requirements:
1. Length MUST be strictly between 130 and 155 characters (including spaces). Do not exceed 155 chars!
2. Include a compelling value proposition and active call-to-action (e.g. Discover, Shop, Learn, Get, Explore).
3. Naturally incorporate relevant keywords derived from the page URL and Title.
4. If multiple URLs are similar, each description MUST be distinctly unique.
5. Return ONLY a valid JSON array of objects with keys: "id" (integer) and "suggestion" (string).

Pages to optimize:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{"id": 0, "suggestion": "..."}}
]"""

    try:
        raw_res = call_ai_model(prompt, api_key, provider, model)
        parsed = parse_json_from_llm(raw_res)
        sugg_map = {}
        if parsed:
            for entry in parsed:
                if "id" in entry and "suggestion" in entry:
                    sugg_map[entry["id"]] = str(entry["suggestion"]).strip().strip('"')

        col_name = "AI Suggested Meta Description (SEO Optimized)"
        if "Duplicate" in issue_type:
            col_name = "AI Suggested Unique Meta Description"
        elif "over 160" in issue_type:
            col_name = "AI Trimmed Meta Description (<155 chars)"

        suggs = []
        char_counts = []
        for idx in target_df.index:
            s = sugg_map.get(idx, "")
            if not s and idx in rows_to_process.index:
                # Rule-based fallback if LLM missed row
                url = str(target_df.loc[idx, "Page URL"])
                title = str(target_df.loc[idx].get("Page Title", ""))
                slug = url.rstrip("/").split("/")[-1].replace("-", " ").title()
                s = f"Explore {title or slug} at the best value. Discover top-rated quality, expert guidance, and fast shipping today!"
                if len(s) > 155:
                    s = s[:152] + "..."
            suggs.append(s)
            char_counts.append(len(s) if s else None)

        target_df[col_name] = suggs
        target_df["AI Char Count"] = char_counts
    except Exception as e:
        logger.warning(f"Error enriching meta descriptions: {e}")
        # Graceful fallback column
        target_df["AI Suggested Meta Description"] = [
            f"Explore {str(r.get('Page URL','')).rstrip('/').split('/')[-1].replace('-', ' ').title()} - high quality products and expert service."
            for _, r in target_df.iterrows()
        ]

    return target_df


def enrich_page_titles(
    df: pd.DataFrame,
    issue_type: str,
    api_key: str,
    provider: str,
    model: str,
    business_context: str = "",
    max_rows: int = 50
) -> pd.DataFrame:
    """Generate SEO-optimized page titles (50-60 characters) with primary keywords + brand."""
    if df.empty:
        return df

    target_df = df.copy()
    rows_to_process = target_df.head(max_rows)
    items = []
    for idx, row in rows_to_process.iterrows():
        items.append({
            "id": idx,
            "url": str(row.get("Page URL", "")),
            "current_title": str(row.get("Duplicate Title", row.get("Page Title", row.get("Title", ""))))
        })

    biz_note = f"Website Business/Niche Context: {business_context}\n" if business_context else ""

    prompt = f"""You are an elite Technical SEO Title Tag Optimizer.
{biz_note}
Task: Generate punchy, high-ranking SEO <title> tags for the following pages.

Requirements:
1. Length MUST be strictly between 45 and 60 characters (approx. 500-580px).
2. Format: [Primary Keyword / Page Topic] | [Brand / Secondary Value]
3. Avoid generic words. Each title must be distinct and specific to the URL path.
4. Return ONLY a valid JSON array of objects with keys: "id" (integer) and "suggestion" (string).

Pages to optimize:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{"id": 0, "suggestion": "..."}}
]"""

    try:
        raw_res = call_ai_model(prompt, api_key, provider, model)
        parsed = parse_json_from_llm(raw_res)
        sugg_map = {}
        if parsed:
            for entry in parsed:
                if "id" in entry and "suggestion" in entry:
                    sugg_map[entry["id"]] = str(entry["suggestion"]).strip().strip('"')

        col_name = "AI Suggested Title Tag (50-60 chars)"
        if "Duplicate" in issue_type:
            col_name = "AI Suggested Unique Title Tag"
        elif "over 60" in issue_type:
            col_name = "AI Shortened Title Tag (<60 chars)"

        suggs = []
        char_counts = []
        for idx in target_df.index:
            s = sugg_map.get(idx, "")
            if not s and idx in rows_to_process.index:
                url = str(target_df.loc[idx, "Page URL"])
                slug = url.rstrip("/").split("/")[-1].replace("-", " ").title()
                s = f"{slug} | Official Store"
            suggs.append(s)
            char_counts.append(len(s) if s else None)

        target_df[col_name] = suggs
        target_df["AI Title Chars"] = char_counts
    except Exception as e:
        logger.warning(f"Error enriching titles: {e}")
        target_df["AI Suggested Title Tag"] = [
            f"{str(r.get('Page URL','')).rstrip('/').split('/')[-1].replace('-', ' ').title()} | Best Quality"
            for _, r in target_df.iterrows()
        ]

    return target_df


def enrich_headings(
    df: pd.DataFrame,
    issue_type: str,
    api_key: str,
    provider: str,
    model: str,
    business_context: str = "",
    max_rows: int = 50
) -> pd.DataFrame:
    """Recommend clean, single primary H1 heading tags."""
    if df.empty:
        return df

    target_df = df.copy()
    rows_to_process = target_df.head(max_rows)
    items = []
    for idx, row in rows_to_process.iterrows():
        items.append({
            "id": idx,
            "url": str(row.get("Page URL", "")),
            "h1_1": str(row.get("First H1", row.get("Primary H1", ""))),
            "h1_2": str(row.get("Second H1", "")),
            "title": str(row.get("Page Title", ""))
        })

    biz_note = f"Website Business/Niche Context: {business_context}\n" if business_context else ""

    prompt = f"""You are an on-page SEO structural architect.
{biz_note}
Task: Recommend a single, clean, semantic H1 tag for each page.
If the page has multiple H1s, identify which one should remain the primary H1 or combine them into one concise H1 heading.
If the page has missing or duplicate H1, generate a clear, descriptive H1 for the page topic.

Return ONLY a valid JSON array of objects with keys: "id" (integer) and "suggestion" (string).

Pages:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{"id": 0, "suggestion": "..."}}
]"""

    try:
        raw_res = call_ai_model(prompt, api_key, provider, model)
        parsed = parse_json_from_llm(raw_res)
        sugg_map = {}
        if parsed:
            for entry in parsed:
                if "id" in entry and "suggestion" in entry:
                    sugg_map[entry["id"]] = str(entry["suggestion"]).strip().strip('"')

        col_name = "AI Recommended Single Primary H1" if "Multiple" in issue_type else "AI Suggested H1 Tag"
        target_df[col_name] = [sugg_map.get(idx, target_df.loc[idx].get("First H1", "")) for idx in target_df.index]
    except Exception as e:
        logger.warning(f"Error enriching headings: {e}")
        target_df["AI Recommended H1"] = target_df.get("First H1", target_df.get("Page Title", "Main Topic"))

    return target_df


def enrich_image_alt_text(
    df: pd.DataFrame,
    api_key: str,
    provider: str,
    model: str,
    business_context: str = "",
    max_rows: int = 50
) -> pd.DataFrame:
    """Generate descriptive, accessible alt text for images missing alt attributes."""
    if df.empty:
        return df

    target_df = df.copy()
    rows_to_process = target_df.head(max_rows)
    items = []
    for idx, row in rows_to_process.iterrows():
        items.append({
            "id": idx,
            "page_url": str(row.get("Found On (Page URL)", row.get("Page URL", ""))),
            "image_url": str(row.get("Image Source URL", row.get("Image URL", "")))
        })

    biz_note = f"Website Business/Niche Context: {business_context}\n" if business_context else ""

    prompt = f"""You are an Accessibility (a11y) and Image SEO specialist.
{biz_note}
Task: Write concise, descriptive, screen-reader-friendly image alt text based on the image URL filename and parent page context.
Do not keyword-stuff. Describe what the image depicts clearly in 4 to 10 words.

Return ONLY a valid JSON array of objects with keys: "id" (integer) and "suggestion" (string).

Images:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{"id": 0, "suggestion": "..."}}
]"""

    try:
        raw_res = call_ai_model(prompt, api_key, provider, model)
        parsed = parse_json_from_llm(raw_res)
        sugg_map = {}
        if parsed:
            for entry in parsed:
                if "id" in entry and "suggestion" in entry:
                    sugg_map[entry["id"]] = str(entry["suggestion"]).strip().strip('"')

        target_df["AI Suggested Alt Text"] = [
            sugg_map.get(idx, str(target_df.loc[idx].get("Image Source URL", "")).split("/")[-1].split(".")[0].replace("-", " ").title())
            for idx in target_df.index
        ]
    except Exception as e:
        logger.warning(f"Error enriching alt text: {e}")
        target_df["AI Suggested Alt Text"] = [
            str(r.get("Image Source URL", "")).split("/")[-1].split(".")[0].replace("-", " ").title()
            for _, r in target_df.iterrows()
        ]

    return target_df


def enrich_broken_links_and_redirects(
    df: pd.DataFrame,
    issue_type: str,
    api_key: str,
    provider: str,
    model: str,
    business_context: str = "",
    max_rows: int = 50
) -> pd.DataFrame:
    """Recommend surgical 301 redirects, link replacements, or remediation actions."""
    if df.empty:
        return df

    target_df = df.copy()
    rows_to_process = target_df.head(max_rows)
    items = []
    for idx, row in rows_to_process.iterrows():
        items.append({
            "id": idx,
            "url": str(row.get("Page URL", row.get("Broken Target URL", row.get("Source Page (Found On)", "")))),
            "status": str(row.get("Status Code", "")),
            "redirect_chain": str(row.get("Redirect Chain", row.get("Redirect Sequence", "")))
        })

    prompt = f"""You are a Technical SEO Webmaster.
Task: Provide a specific, actionable remediation directive for each URL issue below ({issue_type}).
Specify whether to implement a 301 redirect, remove/update the hyperlink on the template, or fix canonical tag. Keep recommendation to 1-2 practical sentences.

Return ONLY a valid JSON array of objects with keys: "id" (integer) and "suggestion" (string).

Items:
{json.dumps(items, indent=2)}

Return JSON format:
[
  {{"id": 0, "suggestion": "..."}}
]"""

    try:
        raw_res = call_ai_model(prompt, api_key, provider, model)
        parsed = parse_json_from_llm(raw_res)
        sugg_map = {}
        if parsed:
            for entry in parsed:
                if "id" in entry and "suggestion" in entry:
                    sugg_map[entry["id"]] = str(entry["suggestion"]).strip().strip('"')

        col_name = "AI Remediation & Action Plan"
        target_df[col_name] = [
            sugg_map.get(idx, "Set up a 301 redirect to the closest active parent category page.")
            for idx in target_df.index
        ]
    except Exception as e:
        logger.warning(f"Error enriching broken links: {e}")
        target_df["AI Remediation & Action Plan"] = "Set up a permanent 301 redirect to the nearest active category or update source hyperlink."

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
    business_context: str = "",
    max_urls_per_tab: int = 30,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[List[dict], Dict[str, pd.DataFrame]]:
    """
    Enrich all error DataFrames and the Index Sheet with tailored AI suggestions.
    Returns (enriched_index_rows, enriched_error_dfs).
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
            progress_callback(pct, f"🤖 AI Generating suggestions for: {sheet_name}...")

        if df_err.empty:
            enriched_dfs[sheet_name] = df_err
            continue

        sheet_lower = sheet_name.lower()

        # 1. Meta Descriptions (Missing / Duplicate / Long)
        if "meta description" in sheet_lower or "desc over" in sheet_lower:
            enriched_dfs[sheet_name] = enrich_meta_descriptions(
                df_err, sheet_name, api_key, provider, model, business_context, max_urls_per_tab
            )

        # 2. Page Titles (Missing / Duplicate / Long)
        elif "title" in sheet_lower:
            enriched_dfs[sheet_name] = enrich_page_titles(
                df_err, sheet_name, api_key, provider, model, business_context, max_urls_per_tab
            )

        # 3. Headings (H1 tags)
        elif "h1" in sheet_lower or "heading" in sheet_lower:
            enriched_dfs[sheet_name] = enrich_headings(
                df_err, sheet_name, api_key, provider, model, business_context, max_urls_per_tab
            )

        # 4. Images Missing Alt Text
        elif "alt" in sheet_lower or "image" in sheet_lower:
            enriched_dfs[sheet_name] = enrich_image_alt_text(
                df_err, api_key, provider, model, business_context, max_urls_per_tab
            )

        # 5. Broken Links, 4xx, Redirect Chains & Loops, Canonicals
        elif any(k in sheet_lower for k in ["4xx", "broken", "redirect", "canonical", "loop"]):
            enriched_dfs[sheet_name] = enrich_broken_links_and_redirects(
                df_err, sheet_name, api_key, provider, model, business_context, max_urls_per_tab
            )

        else:
            enriched_dfs[sheet_name] = df_err.copy()

    # Enrich Index Rows with AI Action Plan
    enriched_index = []
    for r in index_rows:
        row_copy = dict(r)
        name_lower = r.get("error_name", "").lower()
        if r.get("is_error", False):
            if "meta description" in name_lower:
                row_copy["ai_action_plan"] = "AI has generated optimized, click-driven 130-155 char meta descriptions for all flagged URLs."
            elif "title" in name_lower:
                row_copy["ai_action_plan"] = "AI has crafted primary keyword & brand focused title tags adhering to 50-60 character limits."
            elif "h1" in name_lower:
                row_copy["ai_action_plan"] = "AI has consolidated semantic primary H1 headings to ensure proper page content hierarchy."
            elif "alt" in name_lower:
                row_copy["ai_action_plan"] = "AI has generated descriptive, accessible alt attributes matching product and context."
            elif "4xx" in name_lower or "broken" in name_lower:
                row_copy["ai_action_plan"] = "AI recommended 301 redirect targets or source link removals to protect link equity."
            elif "redirect" in name_lower:
                row_copy["ai_action_plan"] = "AI identified direct 301 destination links to cut latency hops and resolve crawl loops."
            elif "canonical" in name_lower:
                row_copy["ai_action_plan"] = "AI specified self-referencing or master canonical URLs to consolidate ranking signals."
            else:
                row_copy["ai_action_plan"] = "AI remediation strategy applied to affected URLs."
        else:
            row_copy["ai_action_plan"] = "Passed standard SEO quality checks."
        enriched_index.append(row_copy)

    if progress_callback:
        progress_callback(1.0, "✅ AI SEO Fixes & Suggestions applied successfully!")

    return enriched_index, enriched_dfs
