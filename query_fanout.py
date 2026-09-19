"""
Query Fan-Out Extractor Module
Extract hidden sub-queries that Google AI Overviews and search engines run internally to answer prompts.
Supports Google Gemini (with live Google Search Grounding & fallback), OpenAI ChatGPT, and Anthropic Claude.
"""

import streamlit as st
import pandas as pd
import re
import time

COUNTRIES = [
    "🌐 Global (No specific region)",
    "🇮🇳 India",
    "🇺🇸 United States",
    "🇬🇧 United Kingdom",
    "🇨🇦 Canada",
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

def _build_fanout_prompt(query: str, num_queries: int, country: str = None) -> str:
    country_ctx = ""
    if country and "Global" not in country:
        clean_country = country.split(" ", 1)[-1] if " " in country else country
        country_ctx = (
            f"\n\nIMPORTANT: Generate these queries specifically for the **{clean_country}** market/region. "
            f"Include local context, local brands, local regulations, local preferences, and region-specific terminology where relevant. "
            f"The queries should reflect what Google would run for a user searching from {clean_country}."
        )

    return f"""You are an expert Google Search analyst specializing in how Google AI Overviews work internally.

For the search query: "{query}"{country_ctx}

Generate exactly {num_queries} realistic Fan-Out Queries that Google AI Overview would internally execute as sub-searches to build its answer. These are the hidden decomposed queries Google runs behind the scenes.

Rules:
- Each query should target a specific aspect or sub-topic
- Include comparison queries, "best of" queries, technical queries, and informational queries
- Make them realistic — as if Google's internal system generated them
- Return ONLY a numbered list (1. query, 2. query, etc.)
- No explanations, no headers, no extra text"""

def _parse_numbered_list(text: str) -> list:
    fan_out_queries = []
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        match = re.match(r'^\d+[\.\)\-]\s*(.+)$', line)
        if match:
            q = match.group(1).strip().strip('"').strip("'")
            if q:
                fan_out_queries.append(q)
    return fan_out_queries

def extract_via_grounding(client, model: str, query: str, country: str = None):
    from google.genai import types

    search_query = f"{query} in {country}" if (country and "Global" not in country) else query

    response = client.models.generate_content(
        model=model,
        contents=search_query,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        ),
    )

    fan_out_queries = []
    answer_text = response.text or ""

    if response.candidates:
        for candidate in response.candidates:
            gm = candidate.grounding_metadata
            if gm and gm.web_search_queries:
                fan_out_queries.extend(gm.web_search_queries)

    return fan_out_queries, answer_text

def extract_via_prompt(client, model: str, query: str, num_queries: int = 15, country: str = None):
    prompt = _build_fanout_prompt(query, num_queries, country)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    answer_text = response.text or ""
    fan_out_queries = _parse_numbered_list(answer_text)
    return fan_out_queries, answer_text

def extract_via_chatgpt(api_key: str, model: str, query: str, num_queries: int = 15, country: str = None):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    prompt = _build_fanout_prompt(query, num_queries, country)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert Google Search analyst. Return only numbered lists."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    answer_text = response.choices[0].message.content or ""
    fan_out_queries = _parse_numbered_list(answer_text)
    return fan_out_queries, answer_text

def extract_via_claude(api_key: str, model: str, query: str, num_queries: int = 15, country: str = None):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_fanout_prompt(query, num_queries, country)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )
    answer_text = response.content[0].text if response.content else ""
    fan_out_queries = _parse_numbered_list(answer_text)
    return fan_out_queries, answer_text

def run_extraction(api_key: str, model: str, query: str, num_queries: int = 15, provider: str = "Google Gemini", country: str = None):
    fallback_note = ""
    clean_model = model.split(" ")[0].strip() if " (" in model else model.strip()

    if provider == "ChatGPT (OpenAI)":
        fan_out_queries, answer_text = extract_via_chatgpt(api_key, clean_model, query, num_queries, country)
        return fan_out_queries, answer_text, "chatgpt", clean_model, fallback_note

    if provider == "Claude (Anthropic)":
        fan_out_queries, answer_text = extract_via_claude(api_key, clean_model, query, num_queries, country)
        return fan_out_queries, answer_text, "claude", clean_model, fallback_note

    # Gemini path (grounding -> prompt fallback -> 404 smart model fallback)
    from google import genai
    client = genai.Client(api_key=api_key)
    method_used = "grounding"
    actual_model = clean_model

    try:
        fan_out_queries, answer_text = extract_via_grounding(client, actual_model, query, country)
        if not fan_out_queries:
            method_used = "prompt"
            fan_out_queries, answer_text = extract_via_prompt(client, actual_model, query, num_queries, country)
    except Exception as e:
        err = str(e).lower()
        # Handle 404 NOT_FOUND (when model name like gemini-3.6/3.7/3.8 is not yet deployed on Google's endpoint)
        if "404" in err or "not found" in err or "not_found" in err:
            actual_model = "gemini-2.5-flash"
            fallback_note = f"ℹ️ Model '{clean_model}' is not yet deployed on Google's v1beta API endpoint. Automatically switched to Google's active production model '{actual_model}' to complete your extraction."
            try:
                fan_out_queries, answer_text = extract_via_grounding(client, actual_model, query, country)
                if not fan_out_queries:
                    method_used = "prompt"
                    fan_out_queries, answer_text = extract_via_prompt(client, actual_model, query, num_queries, country)
            except Exception as e2:
                method_used = "prompt"
                fan_out_queries, answer_text = extract_via_prompt(client, actual_model, query, num_queries, country)
        elif any(kw in err for kw in ["quota", "rate", "limit", "429", "503", "resource_exhausted", "grounding", "unavailable", "capacity"]):
            method_used = "prompt"
            fan_out_queries, answer_text = extract_via_prompt(client, actual_model, query, num_queries, country)
        else:
            raise e

    return fan_out_queries, answer_text, method_used, actual_model, fallback_note


def render_query_fanout_page():
    """
    Render Query Fan-Out Extractor page with API Configuration directly in the center
    as requested by user ('jo apis hai usse side me na rakh kar bich me rakhna').
    """
    # 1. Hero Header
    st.markdown("""
    <div style="background: radial-gradient(130% 120% at 50% -10%, #1E1B4B 0%, #0F172A 60%, #020617 100%); padding: 2.8rem 2.2rem 2.2rem; border-radius: 20px; border: 1px solid rgba(129, 140, 248, 0.25); text-align: center; margin-bottom: 2rem; box-shadow: 0 20px 45px -10px rgba(0,0,0,0.6);">
        <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(129, 140, 248, 0.12); color: #A5B4FC; border: 1px solid rgba(129, 140, 248, 0.3); padding: 5px 16px; border-radius: 9999px; font-size: 0.76rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 1.1rem;">
            🔍 Google AI Overview Reverse-Engineering
        </div>
        <h1 style="font-size: 2.75rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.03em; margin: 0 0 0.6rem 0; line-height: 1.15;">
            Google Query Fan-Out Extractor
        </h1>
        <p style="color: #94A3B8; font-size: 1.12rem; max-width: 720px; margin: 0 auto; line-height: 1.6;">
            Extract the hidden decomposed sub-queries that Google AI Overviews execute behind the scenes to gather answers.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 2. Central API Configuration Card (Placed in Center of Page)
    st.markdown("""
    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(99, 102, 241, 0.28); border-radius: 16px; padding: 1.4rem 1.6rem 1rem; margin-bottom: 1.6rem;">
        <div style="font-size: 1.1rem; font-weight: 700; color: #F8FAFC; margin-bottom: 4px; display: flex; align-items: center; gap: 8px;">
            <span>🔐</span> <span>AI Engine & API Configuration</span>
        </div>
        <div style="font-size: 0.85rem; color: #94A3B8; margin-bottom: 1rem;">
            Select your preferred AI provider and enter your API key to power query fan-out extraction.
        </div>
    </div>
    """, unsafe_allow_html=True)

    cfg_col1, cfg_col2, cfg_col3 = st.columns([1.4, 2.2, 1.4])

    with cfg_col1:
        ai_provider = st.selectbox(
            "AI Provider",
            options=["Google Gemini", "ChatGPT (OpenAI)", "Claude (Anthropic)"],
            index=0,
            key="fanout_provider"
        )

        if ai_provider == "Google Gemini":
            model_options = [
                "gemini-2.5-flash (Recommended - Active Production)",
                "gemini-2.5-pro (Active Production)",
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-3.8-flash (Preview)",
                "gemini-3.8-pro (Preview)",
                "gemini-3.7-flash (Preview)",
                "gemini-3.7-pro (Preview)",
                "gemini-3.6-flash (Preview)",
                "gemini-3.6-pro (Preview)",
                "gemini-3.5-flash",
                "gemini-3.5-pro",
                "Custom Model"
            ]
        elif ai_provider == "ChatGPT (OpenAI)":
            model_options = [
                "gpt-4.1",
                "gpt-4.1-mini",
                "gpt-4o",
                "gpt-4o-mini",
                "o3-mini",
                "Custom Model"
            ]
        else:
            model_options = [
                "claude-sonnet-4-20250514",
                "claude-haiku-4-20250514",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "Custom Model"
            ]

        selected_model_choice = st.selectbox(
            "Model",
            options=model_options,
            index=0,
            key="fanout_model_choice"
        )
        if selected_model_choice == "Custom Model":
            selected_model = st.text_input(
                "Custom Model Name",
                placeholder="e.g. gemini-3.6-ultra",
                key="fanout_custom_model"
            ).strip()
        else:
            selected_model = selected_model_choice

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
        else:
            key_label = "Anthropic API Key"
            key_placeholder = "sk-ant-..."
            help_url = "https://console.anthropic.com/settings/keys"
            help_text = "Get your Anthropic key →"

        api_key = st.text_input(
            key_label,
            value=st.session_state.get(f"api_key_{ai_provider}", ""),
            type="password",
            placeholder=key_placeholder,
            key=f"input_key_{ai_provider}"
        )
        st.caption(f"🔑 <a href='{help_url}' target='_blank' style='color:#818CF8; text-decoration:none;'>{help_text}</a>", unsafe_allow_html=True)
        if api_key:
            st.session_state[f"api_key_{ai_provider}"] = api_key

    with cfg_col3:
        target_country = st.selectbox(
            "Target Search Region",
            options=COUNTRIES,
            index=0,
            key="fanout_country"
        )
        query_count = st.slider(
            "Number of Queries",
            min_value=5,
            max_value=30,
            value=15,
            step=1,
            key="fanout_count"
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # 3. Central Query Input Search Bar
    st.markdown("##### 🔎 Target Search Prompt / Keyword")
    q_col1, q_col2 = st.columns([4.2, 1.2])

    with q_col1:
        user_query = st.text_input(
            "Search Query",
            value=st.session_state.get("fanout_user_query", ""),
            placeholder="e.g. best running shoes for flat feet, how to start investing in mutual funds, etc.",
            label_visibility="collapsed",
            key="fanout_query_input"
        )

    with q_col2:
        btn_extract = st.button("Extract Fan-Out 🚀", type="primary", use_container_width=True, key="btn_fanout_exec")

    # Example chips
    st.markdown("""
    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; margin-bottom: 24px; font-size: 0.8rem; color: #94A3B8;">
        <span>💡 Quick examples:</span>
        <span style="background: rgba(99,102,241,0.12); color: #A5B4FC; padding: 2px 10px; border-radius: 9999px; border: 1px solid rgba(99,102,241,0.25);">best crm software for small business</span>
        <span style="background: rgba(99,102,241,0.12); color: #A5B4FC; padding: 2px 10px; border-radius: 9999px; border: 1px solid rgba(99,102,241,0.25);">how to fix 404 crawl errors</span>
        <span style="background: rgba(99,102,241,0.12); color: #A5B4FC; padding: 2px 10px; border-radius: 9999px; border: 1px solid rgba(99,102,241,0.25);">seo audit checklist 2026</span>
    </div>
    """, unsafe_allow_html=True)

    # 4. Execution logic
    if btn_extract:
        if not api_key or not api_key.strip():
            st.error(f"⚠️ Please enter your **{ai_provider} API Key** in the configuration panel above to run extraction.")
            st.stop()

        if not selected_model or not str(selected_model).strip():
            st.error("⚠️ Please select or enter a valid model name.")
            st.stop()

        if not user_query or not user_query.strip():
            st.warning("⚠️ Please enter a search query or topic to extract fan-out queries.")
            st.stop()

        st.session_state["fanout_user_query"] = user_query.strip()

        with st.spinner(f"Analyzing prompt with {ai_provider} ({selected_model}) and decomposing into search fan-out queries..."):
            try:
                t0 = time.time()
                queries, answer_text, method_used, actual_model, fallback_note = run_extraction(
                    api_key=api_key.strip(),
                    model=selected_model,
                    query=user_query.strip(),
                    num_queries=query_count,
                    provider=ai_provider,
                    country=target_country
                )
                elapsed = round(time.time() - t0, 2)

                st.session_state["fanout_results"] = {
                    "queries": queries,
                    "answer_text": answer_text,
                    "method_used": method_used,
                    "elapsed": elapsed,
                    "query": user_query.strip(),
                    "provider": ai_provider,
                    "model": actual_model,
                    "country": target_country,
                    "fallback_note": fallback_note
                }
                st.rerun()

            except Exception as e:
                err_str = str(e)
                if any(w in err_str.lower() for w in ["api_key", "invalid", "auth", "401"]):
                    st.error(f"🔑 **Invalid API Key**: Please check your {ai_provider} API key and try again.")
                elif any(w in err_str.lower() for w in ["quota", "exceeded", "limit", "429"]):
                    st.error(f"💳 **Rate Limit or Quota Exceeded**: Your {ai_provider} API quota has been reached.")
                else:
                    st.error(f"❌ Error during extraction: {err_str}")
                st.stop()

    # 5. Render Results
    res = st.session_state.get("fanout_results")
    if res:
        st.markdown("---")

        if res.get("fallback_note"):
            st.info(res["fallback_note"])

        # Method Banner
        method_labels = {
            "grounding": "✅ Extracted via <b>Google Search Grounding</b> — Live sub-queries extracted from Gemini search metadata",
            "chatgpt": f"🤖 Generated via <b>ChatGPT ({res['model']})</b> — AI-decomposed fan-out search queries",
            "claude": f"🧊 Generated via <b>Claude ({res['model']})</b> — AI-predicted fan-out queries",
            "prompt": "🧠 Generated via <b>Gemini AI Prediction</b> — Gemini predicted realistic internal sub-queries"
        }
        b_text = method_labels.get(res["method_used"], method_labels["prompt"])
        st.markdown(f"""
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 12px; padding: 12px 18px; color: #A7F3D0; font-size: 0.92rem; margin-bottom: 1.5rem;">
            {b_text}
        </div>
        """, unsafe_allow_html=True)

        # Metric cards
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🎯 Sub-Queries Extracted", len(res["queries"]))
        total_words = sum(len(q.split()) for q in res["queries"])
        m2.metric("📝 Words in Queries", total_words)
        answer_words = len(res["answer_text"].split()) if res["answer_text"] else 0
        m3.metric("💬 Words in Answer", answer_words)
        m4.metric("⏱️ Execution Time", f"{res['elapsed']}s")

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # Extracted queries list
        st.subheader("🎯 Extracted Fan-Out Queries")
        st.caption("These are the sub-queries that Google AI Overviews runs internally to formulate a comprehensive answer.")

        for idx, q in enumerate(res["queries"], 1):
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 14px; background: rgba(30, 41, 59, 0.6); border: 1px solid #334155; border-radius: 10px; padding: 12px 18px; margin-bottom: 8px;">
                <div style="background: rgba(99, 102, 241, 0.25); color: #C7D2FE; font-weight: 800; border-radius: 8px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; flex-shrink: 0;">
                    {idx}
                </div>
                <div style="color: #F8FAFC; font-size: 0.95rem; font-weight: 500; word-break: break-word;">
                    {q}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # Export & Full Answer
        exp_col1, exp_col2 = st.columns([1, 1])
        with exp_col1:
            df_export = pd.DataFrame({
                "No.": list(range(1, len(res["queries"]) + 1)),
                "Fan-Out Query": res["queries"],
                "Original Search Prompt": [res["query"]] * len(res["queries"]),
                "Target Region": [res["country"]] * len(res["queries"]),
                "Provider": [res["provider"]] * len(res["queries"]),
                "Model": [res["model"]] * len(res["queries"]),
                "Method": [res["method_used"]] * len(res["queries"])
            })
            csv_data = df_export.to_csv(index=False)
            st.download_button(
                "📥 Download Queries as CSV",
                data=csv_data,
                file_name=f"fanout_queries_{res['query'][:25].replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="dl_fanout_csv"
            )

        with exp_col2:
            if res.get("answer_text"):
                with st.expander("🤖 View Full AI Generated Answer", expanded=False):
                    st.markdown(res["answer_text"])
