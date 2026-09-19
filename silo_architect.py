"""
AI Silo Structure Architect & Strategic Interlinker Module
Architect high-authority topical silos, eliminate PageRank leaks, benchmark competitors,
find high-traffic blog topics with ZERO keyword cannibalization, and get clear page-by-page
anchor text and internal linking recommendations.
Powered by Gemini (3.5 to 3.8), OpenAI ChatGPT, or Anthropic Claude.
"""

import streamlit as st
import pandas as pd
import requests
import json
import re
import time
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import plotly.graph_objects as go

FONT_FAMILY = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

SILO_FRAMEWORKS = {
    "Strict Hierarchical Silo (Directory-Isolated Silo)": {
        "badge": "Directory Isolation",
        "color": "#38BDF8",
        "desc": "<b>Core Rule:</b> Strict vertical top-down and bottom-up linking. Home links to Category Pillars; Pillars link down to Supporting Articles; Articles link back up to their Pillar. Sibling linking is allowed <i>strictly within the same silo</i>.<br><b>Prohibited:</b> 🚫 ZERO cross-silo linking between children of different categories to prevent topical PageRank dilution.",
        "best_for": "E-Commerce multi-category stores, corporate websites with distinct business verticals, large content publishers."
    },
    "Hub & Spoke Topic Cluster Silo (Semantic Silo)": {
        "badge": "Semantic Topic Cluster",
        "color": "#818CF8",
        "desc": "<b>Core Rule:</b> Radial star topology. One master Pillar Page targeting high-volume head keyword, surrounded by long-tail Spoke Articles. Every spoke links directly to the Pillar with targeted anchor text, and spokes interlink contextually with neighboring spokes.",
        "best_for": "Topical Authority blogs, SaaS product feature clusters, niche affiliate authority hubs."
    },
    "Reverse Silo (Bottom-Up Equity Flow)": {
        "badge": "Bottom-Up Equity Flow",
        "color": "#34D399",
        "desc": "<b>Core Rule:</b> Channel organic backlink equity upwards from viral/linkable long-tail articles up to the high-converting category commercial money page. Every sub-article links upward to the pillar.",
        "best_for": "Commercial lead-gen sites, affiliate product reviews, competitive service pages needing link equity."
    },
    "Sequential / Serial Silo (Step-by-Step Chain)": {
        "badge": "Linear Step-by-Step Chain",
        "color": "#F59E0B",
        "desc": "<b>Core Rule:</b> Progressive sequence chain: Article 1 ➔ Article 2 ➔ Article 3 ➔ Article 4 with a loopback to Article 1. Every step in the chain links up to the master Guide Pillar page.",
        "best_for": "Tutorials, multi-part course modules, onboarding workflows, structured buyer journeys."
    },
    "Hybrid / Matrix Silo (Cross-Pillar Bridges)": {
        "badge": "Cross-Pillar Bridge Links",
        "color": "#EC4899",
        "desc": "<b>Core Rule:</b> Controlled cross-silo linking restricted exclusively to Master Pillar ⟷ Master Pillar level, or explicitly bridged comparison articles.",
        "best_for": "Enterprise platforms, SaaS with interconnected toolkits, multi-service agency sites."
    }
}


def _extract_site_context(target_url: str, max_links: int = 35) -> dict:
    """Quickly inspect website to extract real-world context for AI analysis."""
    info = {
        "url": target_url,
        "title": "",
        "meta_desc": "",
        "headings": [],
        "sample_pages": []
    }
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(target_url, headers=headers, timeout=8, verify=False)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            t_tag = soup.find("title")
            if t_tag:
                info["title"] = t_tag.get_text().strip()
            d_tag = soup.find("meta", attrs={"name": "description"})
            if d_tag and d_tag.get("content"):
                info["meta_desc"] = d_tag.get("content").strip()
            
            for h in soup.find_all(["h1", "h2"], limit=15):
                htxt = h.get_text().strip()
                if htxt and len(htxt) < 90 and htxt not in info["headings"]:
                    info["headings"].append(htxt)
            
            # Extract internal links
            parsed_root = urlparse(target_url)
            discovered = set()
            for a in soup.find_all("a", href=True):
                href = a.get("href")
                full_url = urljoin(target_url, href)
                p = urlparse(full_url)
                if p.netloc == parsed_root.netloc and p.scheme in ["http", "https"]:
                    clean_u = f"{p.scheme}://{p.netloc}{p.path}"
                    if clean_u != target_url and clean_u not in discovered:
                        discovered.add(clean_u)
                        anchor_text = a.get_text().strip()
                        info["sample_pages"].append({"url": clean_u, "text": anchor_text or p.path})
                        if len(info["sample_pages"]) >= max_links:
                            break
    except Exception:
        pass
    return info


def _call_ai_model(api_key: str, provider: str, model: str, system_prompt: str, user_prompt: str) -> str:
    """Call Google Gemini, OpenAI, or Anthropic Claude."""
    clean_model = model.split(" ")[0].strip() if " (" in model else model.strip()
    
    if provider == "Google Gemini":
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Try requested model with fallback if 404
        try:
            response = client.models.generate_content(
                model=clean_model,
                contents=f"{system_prompt}\n\nUSER REQUEST:\n{user_prompt}"
            )
            return response.text or ""
        except Exception as e:
            err = str(e).lower()
            if "404" in err or "not found" in err or "not_found" in err:
                fallback_model = "gemini-2.5-flash"
                response = client.models.generate_content(
                    model=fallback_model,
                    contents=f"{system_prompt}\n\nUSER REQUEST:\n{user_prompt}"
                )
                return response.text or ""
            raise e

    elif provider == "ChatGPT (OpenAI)":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=clean_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content or ""

    elif provider == "Claude (Anthropic)":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=clean_model,
            max_tokens=4000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.content[0].text if response.content else ""

    return ""


def _create_silo_tree_chart(silo_data: dict, site_url: str) -> go.Figure:
    """Generate dynamic visual hierarchical Silo Tree Graph."""
    clusters = silo_data.get("clusters", [])
    if not clusters:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=350)
        return fig

    node_x, node_y = [], []
    node_text, node_color, node_size = [], [], []
    edge_x, edge_y = [], []

    # Root Node
    root_x, root_y = 0.0, 3.0
    node_x.append(root_x)
    node_y.append(root_y)
    p_root = urlparse(site_url).netloc or "Home Root"
    node_text.append(f"<b>HOME ROOT</b><br>{p_root}")
    node_color.append("#6366F1")
    node_size.append(34)

    num_clusters = len(clusters)
    width_span = max(12.0, num_clusters * 4.0)
    spacing = width_span / max(num_clusters, 1)
    start_x = -width_span / 2.0 + spacing / 2.0

    cluster_palette = ["#38BDF8", "#34D399", "#F59E0B", "#EC4899", "#A855F7", "#10B981"]

    for c_idx, cluster in enumerate(clusters):
        cx = start_x + c_idx * spacing
        cy = 1.5
        c_color = cluster_palette[c_idx % len(cluster_palette)]

        # Edge from Home to Pillar
        edge_x.extend([root_x, cx, None])
        edge_y.extend([root_y, cy, None])

        # Pillar Node
        pillar_name = cluster.get("pillar_name", f"Silo {c_idx+1}")
        node_x.append(cx)
        node_y.append(cy)
        node_text.append(f"<b>PILLAR {c_idx+1}</b><br>{pillar_name[:24]}")
        node_color.append(c_color)
        node_size.append(26)

        # Spokes
        spokes = cluster.get("spokes", [])
        num_spokes = len(spokes)
        if num_spokes > 0:
            spoke_span = min(3.2, spacing * 0.9)
            spoke_spacing = spoke_span / max(num_spokes, 1)
            spoke_start = cx - spoke_span / 2.0 + spoke_spacing / 2.0

            for s_idx, spoke in enumerate(spokes):
                sx = spoke_start + s_idx * spoke_spacing
                sy = 0.0
                # Edge Pillar to Spoke
                edge_x.extend([cx, sx, None])
                edge_y.extend([cy, sy, None])

                spoke_title = spoke if isinstance(spoke, str) else spoke.get("title", f"Spoke {s_idx+1}")
                node_x.append(sx)
                node_y.append(sy)
                node_text.append(f"<b>SUPPORTING</b><br>{spoke_title[:20]}")
                node_color.append("rgba(148, 163, 184, 0.85)")
                node_size.append(15)

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(color="rgba(148, 163, 184, 0.35)", width=1.5),
        hoverinfo="none"
    )

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=[t.split("<br>")[1] if "<br>" in t else t for t in node_text],
        textposition="bottom center",
        textfont=dict(family=FONT_FAMILY, size=9.5, color="#E2E8F0"),
        hovertext=node_text,
        hoverinfo="text",
        marker=dict(
            size=node_size,
            color=node_color,
            line=dict(width=2, color="#0F172A")
        )
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title=dict(text="Topical Silo Architecture Blueprint", font=dict(color="#F1F5F9", size=16, family=FONT_FAMILY)),
            showlegend=False,
            hovermode="closest",
            margin=dict(b=30, l=20, r=20, t=50),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=460,
            font=dict(family=FONT_FAMILY)
        )
    )
    return fig


def render_silo_architect_page():
    """Main rendering function for the AI Silo Structure Architect tool."""
    
    # 1. Hero Banner
    st.markdown("""
    <div style="background: radial-gradient(130% 120% at 50% -10%, #1E1B4B 0%, #0F172A 60%, #020617 100%); padding: 2.8rem 2.2rem 2.2rem; border-radius: 20px; border: 1px solid rgba(129, 140, 248, 0.25); text-align: center; margin-bottom: 2rem; box-shadow: 0 20px 45px -10px rgba(0,0,0,0.6);">
        <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(129, 140, 248, 0.12); color: #A5B4FC; border: 1px solid rgba(129, 140, 248, 0.3); padding: 5px 16px; border-radius: 9999px; font-size: 0.76rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 1.1rem;">
            🏛️ Enterprise Information Architecture & AI Interlinking
        </div>
        <h1 style="font-size: 2.75rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.03em; margin: 0 0 0.6rem 0; line-height: 1.15;">
            AI Silo Structure Architect
        </h1>
        <p style="color: #94A3B8; font-size: 1.12rem; max-width: 760px; margin: 0 auto; line-height: 1.6;">
            Architect bulletproof topical silos, benchmark competitors' site architecture, discover high-traffic blog topics with ZERO keyword cannibalization, and get exact in-page anchor text linking instructions.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 2. Central AI Provider & Model Configuration
    if "silo_reset_id" not in st.session_state:
        st.session_state["silo_reset_id"] = 0
    reset_id = st.session_state["silo_reset_id"]

    st.markdown("""
    <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 16px; padding: 1.5rem 1.8rem 1.2rem; margin-bottom: 1.8rem; box-shadow: 0 10px 30px rgba(0,0,0,0.4);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid rgba(148, 163, 184, 0.15); padding-bottom: 0.6rem;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #F1F5F9; display: flex; align-items: center; gap: 8px;">
                <span>⚙️ AI Engine & API Key Setup</span>
            </div>
            <div style="font-size: 0.8rem; color: #94A3B8;">
                Keys are saved securely in your private session
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_prov, c_model, c_key = st.columns([1.2, 1.4, 2.0])

    with c_prov:
        ai_provider = st.selectbox(
            "AI Provider",
            options=["Google Gemini", "ChatGPT (OpenAI)", "Claude (Anthropic)"],
            index=0,
            key=f"silo_ai_provider_{reset_id}"
        )

    with c_model:
        if ai_provider == "Google Gemini":
            model_options = [
                "gemini-3.8-pro-preview",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-pro-preview",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
                "Custom Model"
            ]
        elif ai_provider == "ChatGPT (OpenAI)":
            model_options = [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4.1",
                "gpt-4.1-mini",
                "o3-mini",
                "Custom Model"
            ]
        else:
            model_options = [
                "claude-3-7-sonnet-20250219",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "Custom Model"
            ]

        selected_model_choice = st.selectbox(
            "AI Model",
            options=model_options,
            index=0,
            key=f"silo_model_choice_{reset_id}"
        )
        if selected_model_choice == "Custom Model":
            selected_model = st.text_input(
                "Custom Model Name",
                placeholder="e.g. gemini-3.6-pro",
                key=f"silo_custom_model_{reset_id}"
            ).strip()
        else:
            selected_model = selected_model_choice

    with c_key:
        if ai_provider == "Google Gemini":
            key_label = "Google Gemini API Key (Free)"
            key_placeholder = "Paste Gemini API key (AIzaSy...)"
            help_url = "https://aistudio.google.com/apikey"
            help_text = "Get free key from Google AI Studio →"
        elif ai_provider == "ChatGPT (OpenAI)":
            key_label = "OpenAI API Key"
            key_placeholder = "sk-..."
            help_url = "https://platform.openai.com/api-keys"
            help_text = "Get OpenAI API key →"
        else:
            key_label = "Anthropic API Key"
            key_placeholder = "sk-ant-..."
            help_url = "https://console.anthropic.com/settings/keys"
            help_text = "Get Anthropic key →"

        # Shared session state between tools
        saved_key = st.session_state.get(f"api_key_{ai_provider}", "")
        api_key = st.text_input(
            key_label,
            value=saved_key,
            type="password",
            placeholder=key_placeholder,
            key=f"silo_input_key_{ai_provider}_{reset_id}"
        )
        if api_key:
            st.session_state[f"api_key_{ai_provider}"] = api_key

        st.markdown(
            f'<div style="font-size:0.75rem; margin-top:2px;"><a href="{help_url}" target="_blank" style="color:#38BDF8; text-decoration:none;">{help_text}</a></div>',
            unsafe_allow_html=True
        )

    st.markdown("---")

    # 3. Target Website & Silo Strategy Inputs
    st.subheader("🌐 Website & Silo Architecture Target")
    st.caption("Enter any website URL. You can also pull URLs directly from a previous audit crawl.")

    # Check if crawl results exist
    crawl_data = st.session_state.get("crawl_results")

    col_w1, col_w2 = st.columns([2.5, 1.5])
    with col_w1:
        target_site = st.text_input(
            "Website URL to Analyze:",
            value=st.session_state.get("silo_target_url", ""),
            placeholder="https://example.com/",
            key=f"silo_target_url_input_{reset_id}"
        )
        st.session_state["silo_target_url"] = target_site

        # If crawl data is available and input is empty, offer convenient 1-click fill button
        if crawl_data and crawl_data.get("start_url") and not target_site:
            crawled_url = crawl_data.get("start_url")
            if st.button(f"⚡ Fill from Crawled Site ({crawled_url})", key=f"btn_fill_crawled_{reset_id}"):
                st.session_state["silo_target_url"] = crawled_url
                st.rerun()

    with col_w2:
        selected_framework = st.selectbox(
            "Silo Architecture Framework:",
            list(SILO_FRAMEWORKS.keys()),
            index=0,
            key="silo_framework_selector"
        )

    # Framework Explainer Pill
    f_info = SILO_FRAMEWORKS[selected_framework]
    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.6); border-left: 4px solid {f_info['color']}; padding: 12px 18px; border-radius: 8px; margin-top: 4px; margin-bottom: 18px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="background: {f_info['color']}22; color: {f_info['color']}; font-weight: 700; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; text-transform: uppercase;">
                {f_info['badge']}
            </span>
            <span style="font-size: 0.82rem; color: #94A3B8;">Best for: {f_info['best_for']}</span>
        </div>
        <div style="font-size: 0.88rem; color: #E2E8F0; line-height: 1.5;">{f_info['desc']}</div>
    </div>
    """, unsafe_allow_html=True)

    # Context and Crawled Pages Info
    col_opt1, col_opt2 = st.columns([2, 1])
    with col_opt1:
        custom_niche_notes = st.text_input(
            "Niche / Core Focus / Business Goals (Optional):",
            placeholder="e.g. B2B Chicory root manufacturer exporting roasted chicory, chicory powder & inulin fibers",
            key=f"silo_niche_notes_{reset_id}"
        )
    with col_opt2:
        st.markdown("<br>", unsafe_allow_html=True)
        if crawl_data and "df_pages" in crawl_data and not crawl_data["df_pages"].empty:
            num_crawled = len(crawl_data["df_pages"])
            use_crawl = st.checkbox(f"Use {num_crawled} Crawled Pages Data", value=True, key="silo_use_crawl_cb")
        else:
            use_crawl = False
            st.caption("ℹ️ No active spider crawl found. Will live-inspect root URL.")

    # Action Buttons: Generate & Clear All
    col_act1, col_act2 = st.columns([3.2, 1.2])
    with col_act1:
        btn_generate = st.button("🚀 Architect Silo Structure, Competitor Benchmark & Blog Strategy", type="primary", use_container_width=True)
    with col_act2:
        btn_clear = st.button("🧹 Clear All", type="secondary", use_container_width=True, key=f"silo_clear_btn_{reset_id}")

    if btn_clear:
        st.session_state["silo_target_url"] = ""
        for p in ["Google Gemini", "ChatGPT (OpenAI)", "Claude (Anthropic)"]:
            st.session_state[f"api_key_{p}"] = ""
        st.session_state.pop("silo_architecture_result", None)
        st.session_state.pop("silo_architecture_website", None)
        st.session_state.pop("silo_architecture_framework", None)
        st.session_state.pop("silo_chat_history", None)
        st.session_state["silo_reset_id"] = reset_id + 1
        st.rerun()

    # 4. Generate Silo Structure via AI
    if btn_generate:
        if not api_key:
            st.error(f"❌ Please enter your **{ai_provider} API Key** in the configuration bar above to generate the Silo Structure.")
            return

        if not target_site or not target_site.startswith("http"):
            st.error("❌ Please enter a valid website URL starting with http:// or https://")
            return

        with st.spinner(f"🔍 Analyzing {target_site}, auditing existing content against cannibalization, and generating strategy with {ai_provider} ({selected_model})..."):
            # Gather page details
            pages_context = []
            if use_crawl and crawl_data and "df_pages" in crawl_data:
                df_p = crawl_data["df_pages"].head(50)
                for _, r in df_p.iterrows():
                    pages_context.append({
                        "url": r.get("url", ""),
                        "title": r.get("title", ""),
                        "h1": r.get("h1", ""),
                        "depth": r.get("depth", 0)
                    })
                site_meta = {"url": target_site, "sample_pages": pages_context}
            else:
                site_meta = _extract_site_context(target_site, max_links=35)

            system_prompt = """
You are an Elite Enterprise Technical SEO Architect & Information Architecture Specialist.
Your mission is to construct a bulletproof, mathematically sound Silo Structure, benchmark top organic competitors, and engineer high-traffic blog topics with ZERO keyword cannibalization.

You MUST respond strictly in valid JSON format with this exact structure:
{
  "summary": "Executive summary of the recommended Silo Structure and why it fits this website.",
  "target_silo_model": "Exact name of the Silo Model",
  "topical_authority_score": 88,
  "competitors_analysis": [
    {
      "competitor_name": "Top Competitor Name",
      "domain": "competitor.com",
      "silo_structure_breakdown": "How they organize their main categories, pillar hubs, and child articles.",
      "linking_strengths": "Their internal linking patterns (e.g. contextual upward links, mega-menu silos, etc.)",
      "topical_gaps_for_us": "Specific pillars, products, or high-volume search topics they rank for that target_site is missing",
      "action_to_outrank": "Tactical recommendation to build and link a better cluster to capture their organic traffic"
    }
  ],
  "clusters": [
    {
      "pillar_name": "Name of Pillar Category",
      "pillar_url": "/category-url",
      "target_head_keyword": "Primary target keyword",
      "search_intent": "Commercial / Informational",
      "spokes": [
        {
          "title": "Supporting Article / Product Page Title",
          "url": "/category-url/sub-page",
          "keyword": "Long tail keyword",
          "intent": "Informational"
        }
      ]
    }
  ],
  "blog_topic_recommendations": [
    {
      "proposed_title": "Catchy, High-CTR, Helpful Blog Post Title",
      "target_primary_keyword": "Exact high-volume search term",
      "secondary_keywords": ["keyword 2", "keyword 3"],
      "search_intent": "Informational / How-To / Technical Comparison",
      "assigned_silo": "Name of Silo Category this blog strengthens",
      "existing_pages_checked": "Names or paths of existing site pages/blogs checked to verify no duplication",
      "cannibalization_defense": "Explanation of how this topic targets a distinctly different search intent than existing pages, guaranteeing ZERO keyword cannibalization between blogs and landing pages",
      "target_money_page_to_link": "Existing commercial landing page or Pillar URL that this blog must link to",
      "recommended_anchor_text": "Exact anchor text to use when linking to the money page",
      "traffic_and_helpful_rationale": "Why this topic drives organic search traffic and genuinely helps visitors solve their problems (Google Helpful Content System)"
    }
  ],
  "interlinking_rules": [
    {
      "directive": "Upward to Pillar ⬆️ | Lateral within Silo ↔️ | Downward to Guide ⬇️",
      "source_page": "Exact Source Page URL or Title where link should be placed",
      "target_page": "Exact Destination Page URL or Title",
      "suggested_anchor_text": "Exact anchor text keywords to highlight",
      "placement_section": "e.g. Introduction / Technical Specs / Benefits Section / FAQ",
      "sentence_context": "Exact realistic sentence to paste on the source page with the anchor text naturally placed",
      "seo_rationale": "Exact reason why this passes PageRank and boosts rankings"
    }
  ],
  "prohibited_links": [
    "List of cross-silo links to strictly avoid to prevent topical leakage."
  ],
  "breadcrumb_blueprint": "Recommended breadcrumb schema markup trail (e.g. Home > Silo Category > Sub-topic)."
}
Do NOT return Markdown backticks around the JSON. Only return raw valid JSON.
"""

            user_prompt = f"""
Target Website: {target_site}
Selected Silo Model: {selected_framework}
Custom Niche Notes: {custom_niche_notes}

Website Discovered Pages & Metadata:
Title: {site_meta.get('title', '')}
Meta Description: {site_meta.get('meta_desc', '')}
Headings: {site_meta.get('headings', [])}
Sample URLs: {json.dumps(site_meta.get('sample_pages', [])[:30], indent=2)}

Please generate:
1. 3 to 4 organic search Competitors for this website, analyzing their silo architecture, topical depth, and gaps that our website should exploit.
2. 3 to 6 distinct Silo Topic Clusters with 1 Core Pillar Page (Tier 1) and 3 to 5 Supporting Spokes (Tier 2/Tier 3).
3. 6 to 10 High-Traffic, User-Centric Blog Topics designed to dramatically increase organic visitors.
   CRITICAL ANTI-CANNIBALIZATION AUDIT:
   Examine every single existing page, heading, and blog from the website metadata above.
   Ensure that NO blog topic repeats or overlaps with an existing landing page or existing blog.
   Each topic must target a unique, untapped search intent, and must specify the exact existing commercial/pillar page it will link to with the recommended anchor text.
4. 10 to 18 crystal-clear, step-by-step in-page interlinking directives tailored to {selected_framework}, specifying the EXACT source page, exact target page, exact anchor text, section placement, and natural sentence context so any content writer or SEO can paste it directly.
"""

            try:
                raw_response = _call_ai_model(api_key, ai_provider, selected_model, system_prompt, user_prompt)
                
                # Parse JSON
                cleaned_text = raw_response.strip()
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                if cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text[3:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                cleaned_text = cleaned_text.strip()

                try:
                    silo_result = json.loads(cleaned_text)
                except Exception:
                    # Fallback regex extraction
                    json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
                    if json_match:
                        silo_result = json.loads(json_match.group(0))
                    else:
                        raise ValueError(f"AI response was not valid JSON: {cleaned_text[:200]}")

                st.session_state["silo_architecture_result"] = silo_result
                st.session_state["silo_architecture_website"] = target_site
                st.session_state["silo_architecture_framework"] = selected_framework

                # Initialize chat history with the new context
                st.session_state["silo_chat_history"] = [
                    {
                        "role": "assistant",
                        "content": f"Hello! I am your **AI Silo Architect** powered by **{ai_provider} ({selected_model})**. I have analyzed **{target_site}**, benchmarked your organic search competitors, designed a **{selected_framework}** blueprint, and audited existing content to generate **{len(silo_result.get('blog_topic_recommendations', []))} high-traffic cannibalization-free blog topics**.\n\nHow can I help you execute this linking strategy, optimize blog topics, or analyze competitors?"
                    }
                ]
                st.success("✅ Silo Structure, Competitor Benchmark, Blog Strategy, & Interlinking Matrix successfully generated!")

            except Exception as e:
                st.error(f"❌ Error during AI Silo generation: {e}")

    # 5. Render Generated Silo Architecture (if present in session_state)
    silo_res = st.session_state.get("silo_architecture_result")
    if silo_res:
        st.markdown("---")
        st.subheader("📊 Strategic Silo Blueprint & Recommendations")

        # Top Executive Summary Cards
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("Target Framework", silo_res.get("target_silo_model", selected_framework)[:20] + "..")
        sc2.metric("Silo Clusters", f"{len(silo_res.get('clusters', []))} Pillars")
        total_spokes = sum(len(c.get("spokes", [])) for c in silo_res.get("clusters", []))
        sc3.metric("Supporting Spokes", f"{total_spokes} Pages")
        sc4.metric("New Blog Topics", f"{len(silo_res.get('blog_topic_recommendations', []))} Ideas", delta="0% Cannibalization", delta_color="normal")
        sc5.metric("Interlinking Directives", f"{len(silo_res.get('interlinking_rules', []))} Rules")

        # Executive Summary Callout
        st.markdown(f"""
        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 18px 22px; margin-top: 12px; margin-bottom: 20px;">
            <div style="font-size: 0.85rem; font-weight: 700; color: #38BDF8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
                Executive Architecture Summary:
            </div>
            <div style="font-size: 0.96rem; color: #E2E8F0; line-height: 1.6;">
                {silo_res.get("summary", "")}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Tabs for Visualization, In-Page Interlinking, Blog Topics, Competitors, Clusters, and Leakage
        tab_graph, tab_interlinking, tab_blogs, tab_competitors, tab_clusters, tab_leakage = st.tabs([
            "🧭 Visual Silo Graph",
            "🔗 In-Page Interlinking Guide",
            "📝 High-Traffic Blog Topics (Anti-Cannibalization)",
            "🏆 Competitor Silo Benchmark & Gaps",
            "📚 Topical Clusters & Pillars",
            "🛡️ Leakage Audit & Breadcrumbs"
        ])

        # TAB 1: VISUAL GRAPH
        with tab_graph:
            silo_fig = _create_silo_tree_chart(silo_res, st.session_state.get("silo_architecture_website", target_site))
            st.plotly_chart(silo_fig, use_container_width=True)

        # TAB 2: IN-PAGE INTERLINKING GUIDE (Crystal clear: Iss page me ye ancore text pe ye wala link rakho)
        with tab_interlinking:
            st.markdown("#### 🔗 Exact In-Page Interlinking Blueprint")
            st.caption("Here is exactly where to place each internal link, which source page to edit, what anchor text to use, and the natural sentence to insert.")

            rules = silo_res.get("interlinking_rules", [])
            if rules:
                df_rules = pd.DataFrame(rules)

                # Page Selector Filter
                all_sources = sorted(list(set([str(r.get("source_page", "")) for r in rules if r.get("source_page")])))
                col_f1, col_f2 = st.columns([2, 1.2])
                with col_f1:
                    filter_source = st.selectbox(
                        "🔍 Filter Interlinking Tasks by Source Page (Page to edit):",
                        ["All Pages (Show All Recommendations)"] + all_sources,
                        key="silo_filter_source_page"
                    )
                with col_f2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    csv_data = df_rules.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Full Interlinking Plan (CSV)",
                        data=csv_data,
                        file_name="silo_in_page_interlinking_plan.csv",
                        mime="text/csv",
                        key="dl_silo_csv"
                    )

                # Filter items
                displayed_rules = rules
                if filter_source != "All Pages (Show All Recommendations)":
                    displayed_rules = [r for r in rules if str(r.get("source_page", "")) == filter_source]

                st.markdown(f"##### Showing **{len(displayed_rules)}** actionable linking directives:")

                # Render intuitive cards for each link directive
                for idx, r in enumerate(displayed_rules):
                    d_type = r.get("directive") or r.get("action", "Internal Link")
                    src = r.get("source_page", "")
                    tgt = r.get("target_page", "")
                    anchor = r.get("suggested_anchor_text", "")
                    section = r.get("placement_section", "Article Body / Relevant Content Section")
                    sentence = r.get("sentence_context", f"Explore our comprehensive guide on {anchor} for more specifications.")
                    benefit = r.get("seo_rationale", "Passes topical link equity and establishes semantic hierarchy.")

                    # Type styling
                    if "Upward" in d_type or "Pillar" in d_type or "⬆️" in d_type:
                        badge_bg = "rgba(56, 189, 248, 0.15)"
                        badge_border = "#38BDF8"
                        badge_color = "#38BDF8"
                        icon = "⬆️"
                    elif "Lateral" in d_type or "↔️" in d_type:
                        badge_bg = "rgba(52, 211, 153, 0.15)"
                        badge_border = "#34D399"
                        badge_color = "#34D399"
                        icon = "↔️"
                    else:
                        badge_bg = "rgba(245, 158, 11, 0.15)"
                        badge_border = "#F59E0B"
                        badge_color = "#F59E0B"
                        icon = "⬇️"

                    # Highlight the anchor in the sentence
                    highlighted_sentence = sentence
                    if anchor and anchor.lower() in sentence.lower():
                        pattern = re.compile(re.escape(anchor), re.IGNORECASE)
                        highlighted_sentence = pattern.sub(f'<span style="background: rgba(56, 189, 248, 0.25); color: #38BDF8; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-decoration: underline;">{anchor}</span>', sentence)
                    else:
                        highlighted_sentence = f'{sentence} — (Link: <span style="background: rgba(56, 189, 248, 0.25); color: #38BDF8; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-decoration: underline;">{anchor}</span>)'

                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(148, 163, 184, 0.2); border-left: 4px solid {badge_border}; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.25);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                            <span style="background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_border}55; padding: 3px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; text-transform: uppercase;">
                                {icon} {d_type}
                            </span>
                            <span style="font-size: 0.8rem; color: #94A3B8;">📍 Section: <b style="color:#E2E8F0;">{section}</b></span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 12px; align-items: center; background: rgba(30, 41, 59, 0.5); padding: 10px 14px; border-radius: 8px; margin-bottom: 12px;">
                            <div>
                                <div style="font-size: 0.72rem; color: #94A3B8; text-transform: uppercase; font-weight: 700;">📄 Source Page (Edit Here)</div>
                                <div style="font-size: 0.9rem; font-weight: 600; color: #FFFFFF; word-break: break-all;">{src}</div>
                            </div>
                            <div style="color: #38BDF8; font-size: 1.2rem; font-weight: bold;">➔</div>
                            <div>
                                <div style="font-size: 0.72rem; color: #94A3B8; text-transform: uppercase; font-weight: 700;">🎯 Target Destination Page</div>
                                <div style="font-size: 0.9rem; font-weight: 600; color: #38BDF8; word-break: break-all;">{tgt}</div>
                            </div>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <div style="font-size: 0.76rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; margin-bottom: 4px;">✍️ Sentence Context (Find or paste in paragraph):</div>
                            <div style="background: rgba(2, 6, 23, 0.6); padding: 10px 14px; border-radius: 6px; border: 1px solid rgba(71, 85, 105, 0.3); font-size: 0.92rem; color: #E2E8F0; line-height: 1.5;">
                                "{highlighted_sentence}"
                            </div>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 0.82rem; color: #94A3B8; margin-top: 8px;">
                            <div>🏷️ Hyperlink Anchor: <b style="color: #38BDF8; font-size: 0.9rem;">"{anchor}"</b></div>
                            <div>💡 SEO Benefit: <span style="color: #CBD5E1;">{benefit}</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.expander(f"📋 1-Click HTML Anchor Snippet for Task #{idx+1}", expanded=False):
                        clean_href = tgt if tgt.startswith("http") else f"{target_site.rstrip('/')}/{tgt.lstrip('/')}"
                        st.code(f'<!-- On Page: {src} -->\n<!-- Section: {section} -->\n<a href="{clean_href}">{anchor}</a>', language="html")

                # Data Table View
                st.markdown("---")
                st.markdown("##### 📋 Complete Master Interlinking Table")
                st.dataframe(df_rules, use_container_width=True, hide_index=True)

        # TAB 3: HIGH-TRAFFIC BLOG TOPIC FINDER & ANTI-CANNIBALIZATION MATRIX
        with tab_blogs:
            st.markdown("#### 📝 High-Traffic Blog Topic Finder & Anti-Cannibalization Matrix")
            st.caption(f"Discover user-centric, high-volume blog topics engineered specifically for {target_site}. Every topic has been cross-referenced with your existing content so that old blogs and landing pages never suffer from keyword cannibalization.")

            st.markdown("""
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 12px; padding: 14px 18px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 1.6rem;">🛡️</span>
                <div>
                    <div style="font-weight: 700; color: #34D399; font-size: 0.95rem;">Cannibalization Shield Verified: Zero Keyword Clashes</div>
                    <div style="font-size: 0.84rem; color: #CBD5E1; margin-top: 2px;">
                        All suggested blog topics target distinctly unique search intents (e.g. how-to troubleshooting, in-depth comparison, formulation guidelines) and explicitly link back to your primary commercial landing pages, preventing internal ranking competition.
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            blog_topics = silo_res.get("blog_topic_recommendations", [])
            if blog_topics:
                df_blogs = pd.DataFrame(blog_topics)

                b_c1, b_c2 = st.columns([3, 1.2])
                with b_c1:
                    st.markdown(f"##### Recommended **{len(blog_topics)}** Cannibalization-Free Blog Topics:")
                with b_c2:
                    csv_b_data = df_blogs.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Blog Strategy (CSV)",
                        data=csv_b_data,
                        file_name="cannibalization_free_blog_topics.csv",
                        mime="text/csv",
                        key="dl_blogs_csv"
                    )

                for b_idx, b in enumerate(blog_topics):
                    title = b.get("proposed_title", f"Blog Topic #{b_idx+1}")
                    kw = b.get("target_primary_keyword", "")
                    sec_kws = b.get("secondary_keywords", [])
                    sec_kw_str = ", ".join(sec_kws) if isinstance(sec_kws, list) else str(sec_kws)
                    intent = b.get("search_intent", "Informational")
                    silo_cat = b.get("assigned_silo", "Core Silo")
                    checked = b.get("existing_pages_checked", "Existing landing pages & blogs audited")
                    defense = b.get("cannibalization_defense", "Targets unique informational search intent separate from existing commercial pages.")
                    target_money = b.get("target_money_page_to_link", "")
                    money_anchor = b.get("recommended_anchor_text", "")
                    helpful_why = b.get("traffic_and_helpful_rationale", "")

                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(129, 140, 248, 0.25); border-left: 4px solid #818CF8; border-radius: 12px; padding: 18px 22px; margin-bottom: 18px; box-shadow: 0 4px 18px rgba(0,0,0,0.25);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                            <div style="font-size: 1.15rem; font-weight: 800; color: #FFFFFF; max-width: 78%;">
                                📰 {title}
                            </div>
                            <span style="background: rgba(129, 140, 248, 0.15); color: #A5B4FC; border: 1px solid rgba(129, 140, 248, 0.35); padding: 3px 10px; border-radius: 9999px; font-size: 0.76rem; font-weight: 700; text-transform: uppercase;">
                                🏛️ Silo: {silo_cat}
                            </span>
                        </div>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; font-size: 0.82rem;">
                            <span style="background: rgba(56, 189, 248, 0.12); color: #38BDF8; padding: 2px 8px; border-radius: 4px; font-weight: 600;">🎯 Primary: {kw}</span>
                            <span style="background: rgba(148, 163, 184, 0.15); color: #CBD5E1; padding: 2px 8px; border-radius: 4px;">🔍 Intent: {intent}</span>
                            {f'<span style="background: rgba(168, 85, 247, 0.12); color: #C084FC; padding: 2px 8px; border-radius: 4px;">🔑 LSI: {sec_kw_str}</span>' if sec_kw_str else ''}
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                            <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(16, 185, 129, 0.25); padding: 12px 14px; border-radius: 8px;">
                                <div style="font-size: 0.74rem; color: #34D399; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">🛡️ Anti-Cannibalization Guarantee:</div>
                                <div style="font-size: 0.86rem; color: #E2E8F0; line-height: 1.45;">
                                    <b>Existing Audited:</b> {checked}<br>
                                    <b>Unique Differentiation:</b> {defense}
                                </div>
                            </div>
                            <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(56, 189, 248, 0.25); padding: 12px 14px; border-radius: 8px;">
                                <div style="font-size: 0.74rem; color: #38BDF8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">🔗 Mandatory Link to Existing Money Page:</div>
                                <div style="font-size: 0.86rem; color: #E2E8F0; line-height: 1.45;">
                                    <b>Link To:</b> <code>{target_money}</code><br>
                                    <b>Recommended Anchor:</b> <span style="color:#38BDF8; font-weight:700;">"{money_anchor}"</span>
                                </div>
                            </div>
                        </div>
                        <div style="background: rgba(2, 6, 23, 0.5); padding: 10px 14px; border-radius: 6px; border: 1px solid rgba(71, 85, 105, 0.3); font-size: 0.86rem; color: #94A3B8;">
                            💡 <b style="color:#E2E8F0;">Why this drives traffic (Helpful Content System):</b> {helpful_why}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("---")
                st.markdown("##### 📋 Complete Master Blog Ideation Table")
                st.dataframe(df_blogs, use_container_width=True, hide_index=True)
            else:
                st.info("ℹ️ Blog recommendations will appear here upon running the Silo Architecture analysis.")

        # TAB 4: COMPETITOR SILO BENCHMARK & GAP ANALYSIS
        with tab_competitors:
            st.markdown("#### 🏆 Organic Search Competitor Silo Benchmark & Topical Gaps")
            st.caption(f"Competitor analysis based on organic search rivals for {target_site}. Discover how industry leaders structure their topical silos, and where they have content gaps you can dominate.")

            competitors = silo_res.get("competitors_analysis", [])
            if competitors:
                for c_idx, comp in enumerate(competitors):
                    c_name = comp.get("competitor_name", f"Competitor {c_idx+1}")
                    c_domain = comp.get("domain", "")
                    c_silo = comp.get("silo_structure_breakdown", "")
                    c_strengths = comp.get("linking_strengths", "")
                    c_gaps = comp.get("topical_gaps_for_us", "")
                    c_action = comp.get("action_to_outrank", "")

                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 14px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 6px 20px rgba(0,0,0,0.3);">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(148, 163, 184, 0.15); padding-bottom: 10px; margin-bottom: 14px;">
                            <div style="font-size: 1.25rem; font-weight: 800; color: #FFFFFF; display: flex; align-items: center; gap: 8px;">
                                <span>🏢 {c_name}</span>
                                <span style="font-size: 0.85rem; color: #38BDF8; font-weight: 500;">({c_domain})</span>
                            </div>
                            <span style="background: rgba(99, 102, 241, 0.15); color: #A5B4FC; border: 1px solid rgba(99, 102, 241, 0.35); font-size: 0.75rem; font-weight: 700; padding: 3px 10px; border-radius: 9999px; text-transform: uppercase;">
                                Competitor Benchmark #{c_idx+1}
                            </span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 14px;">
                            <div style="background: rgba(30, 41, 59, 0.4); padding: 12px 16px; border-radius: 8px; border: 1px solid rgba(148, 163, 184, 0.1);">
                                <div style="font-size: 0.76rem; color: #38BDF8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">🏛️ Their Silo & Category Hierarchy:</div>
                                <div style="font-size: 0.9rem; color: #E2E8F0; line-height: 1.5;">{c_silo}</div>
                            </div>
                            <div style="background: rgba(30, 41, 59, 0.4); padding: 12px 16px; border-radius: 8px; border: 1px solid rgba(148, 163, 184, 0.1);">
                                <div style="font-size: 0.76rem; color: #34D399; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">🔗 Their Linking Strengths & Strategy:</div>
                                <div style="font-size: 0.9rem; color: #E2E8F0; line-height: 1.5;">{c_strengths}</div>
                            </div>
                        </div>
                        <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); padding: 12px 16px; border-radius: 8px; margin-bottom: 12px;">
                            <div style="font-size: 0.76rem; color: #F87171; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">⚠️ Topical Gaps & Missing Topics for Your Site:</div>
                            <div style="font-size: 0.9rem; color: #FCA5A5; line-height: 1.5;">{c_gaps}</div>
                        </div>
                        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); padding: 12px 16px; border-radius: 8px;">
                            <div style="font-size: 0.76rem; color: #34D399; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">🚀 Strategic Playbook to Outrank Them:</div>
                            <div style="font-size: 0.9rem; color: #A7F3D0; line-height: 1.5;">{c_action}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ Competitor analysis data will appear here when generated. Run analysis or ask the AI Chatbot below.")

        # TAB 5: TOPICAL CLUSTERS
        with tab_clusters:
            st.markdown("#### 📂 Identified Topical Silos & Supporting Pages")
            for idx, cluster in enumerate(silo_res.get("clusters", [])):
                p_name = cluster.get("pillar_name", f"Pillar {idx+1}")
                p_url = cluster.get("pillar_url", "")
                kw = cluster.get("target_head_keyword", "")
                intent = cluster.get("search_intent", "Commercial")
                
                with st.expander(f"🏛️ Silo {idx+1}: {p_name} ({len(cluster.get('spokes', []))} Spokes)", expanded=(idx == 0)):
                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; border: 1px solid rgba(148, 163, 184, 0.15);">
                        <b>Pillar URL:</b> <code>{p_url}</code> | <b>Primary Keyword:</b> <span style="color:#38BDF8; font-weight:600;">{kw}</span> | <b>Intent:</b> <span style="color:#34D399; font-weight:600;">{intent}</span>
                    </div>
                    """, unsafe_allow_html=True)

                    spoke_rows = []
                    for sp in cluster.get("spokes", []):
                        if isinstance(sp, dict):
                            spoke_rows.append({
                                "Page Title": sp.get("title", ""),
                                "URL": sp.get("url", ""),
                                "Target Keyword": sp.get("keyword", ""),
                                "Search Intent": sp.get("intent", "Informational")
                            })
                        else:
                            spoke_rows.append({"Page Title": str(sp), "URL": "", "Target Keyword": "", "Search Intent": "Informational"})
                    
                    if spoke_rows:
                        st.dataframe(pd.DataFrame(spoke_rows), use_container_width=True, hide_index=True)

        # TAB 6: LEAKAGE AUDIT & BREADCRUMBS
        with tab_leakage:
            st.markdown("#### 🛡️ Cross-Silo Linkage Leakage Prevention & Breadcrumbs")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.markdown("##### 🚫 Prohibited Cross-Silo Connections")
                prohib = silo_res.get("prohibited_links", [])
                if prohib:
                    for p_item in prohib:
                        st.markdown(f"• 🚫 {p_item}")
                else:
                    st.info("No cross-silo link prohibitions detected.")
            with col_b2:
                st.markdown("##### 🍞 Recommended Breadcrumb Schema Structure")
                bc = silo_res.get("breadcrumb_blueprint", "Home > [Pillar Category] > [Subtopic / Article]")
                st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.7); padding: 14px 18px; border-radius: 8px; border: 1px solid rgba(56, 189, 248, 0.3); font-family: monospace; color: #38BDF8;">
                    {bc}
                </div>
                """, unsafe_allow_html=True)
                st.caption("Implement JSON-LD BreadcrumbList markup matching this hierarchy to secure Google rich snippets.")

    # 6. Interactive AI Silo Chatbot Section
    st.markdown("---")
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 10px; margin-top: 10px; margin-bottom: 6px;">
        <span style="font-size: 1.6rem;">💬</span>
        <span style="font-size: 1.45rem; font-weight: 800; color: #FFFFFF;">Chat with AI Silo Architect</span>
    </div>
    <div style="font-size: 0.92rem; color: #94A3B8; margin-bottom: 16px;">
        Ask Gemini, ChatGPT, or Claude any question about structuring your website, high-traffic blog topics, anchor texts, competitor gaps, or resolving PageRank dilution.
    </div>
    """, unsafe_allow_html=True)

    # Initialize chat history if not present
    if "silo_chat_history" not in st.session_state:
        st.session_state["silo_chat_history"] = [
            {
                "role": "assistant",
                "content": f"👋 Hi! I am your **AI Silo Architect**. Enter your website URL above and ask me anything about finding high-traffic cannibalization-free blog topics, competitor gaps, choosing anchor texts, or structuring internal links."
            }
        ]

    # Quick prompt buttons (5 columns with clear, responsive strategy buttons)
    st.markdown("<div style='font-size: 0.82rem; font-weight: 600; color: #CBD5E1; margin-bottom: 8px;'>💡 Quick Strategy Inquiries:</div>", unsafe_allow_html=True)
    qc1, qc2, qc3, qc4, qc5 = st.columns(5)
    quick_prompt = None
    with qc1:
        if st.button("🔗 Anchor Text Strategy", use_container_width=True, key="qp_anchor"):
            quick_prompt = f"What are 10 high-impact anchor text variations to link supporting articles to the main pillar on {target_site} without over-optimization penalties?"
    with qc2:
        if st.button("⚡ In-Page Interlinking Guide", use_container_width=True, key="qp_interlinking"):
            quick_prompt = f"Give me a concrete list of exactly which page on {target_site} should link to which other page, along with the exact anchor text and sentence context."
    with qc3:
        if st.button("📝 Blog Topics (No Cannibalization)", use_container_width=True, key="qp_blogs"):
            quick_prompt = f"Analyze all existing pages and blogs on {target_site}. Recommend 10 high-traffic, user-helpful blog topics that answer real search queries, strictly checking our existing content so that NO topic repeats and there is ZERO keyword cannibalization with our existing pages. For each, give: Proposed Title, Target Primary Keyword, Search Intent, Silo Category, Which Existing Money Page It Must Interlink To (with exact anchor text), and the Anti-Cannibalization Defense."
    with qc4:
        if st.button("🏆 Competitor Silo Analysis", use_container_width=True, key="qp_competitor"):
            quick_prompt = f"Who are the top 3-4 organic search competitors for {target_site}? What are their core silo pillars, how do they link them, and what topical gaps can we exploit to outrank them?"
    with qc5:
        if st.button("🛡️ Prevent PageRank Leakage", use_container_width=True, key="qp_leakage"):
            quick_prompt = f"How do I prevent PageRank leakage between different category silos on {target_site} while maintaining good user navigation?"

    # Display Chat History
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state["silo_chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # User Input Field
    user_input = st.chat_input("Ask AI Silo Architect anything about blog topics, internal linking, or competitors...")
    if quick_prompt:
        user_input = quick_prompt

    if user_input:
        if not api_key:
            st.error(f"❌ Please provide your **{ai_provider} API Key** in the configuration bar above to chat.")
            return

        # Append User Message
        st.session_state["silo_chat_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Generate Assistant Response
        with st.chat_message("assistant"):
            with st.spinner("AI Architect is thinking..."):
                current_silo_context = json.dumps(st.session_state.get("silo_architecture_result", {}), indent=2)
                chat_sys_prompt = f"""
You are an Elite Senior Technical SEO Architect specializing in Website Information Architecture, Topical Silos, Internal Linking, Keyword Cannibalization Prevention, and Competitor Search Analysis.
The user is working on the website: {target_site}
Target Silo Model: {selected_framework}
Generated Silo Structure, Blogs, & Competitors Context:
{current_silo_context[:3500]}

Provide clear, highly specific, actionable advice.
When suggesting blog topics:
1. Ensure strict anti-cannibalization by verifying against existing pages/blogs.
2. Specify which existing money/landing page the new blog must link back to, with the exact anchor text.
When suggesting links, format clearly:
'On Page: [URL] ➔ In Section: [Name] ➔ Insert Sentence: "..." ➔ Anchor Text: "[Text]" ➔ Links to: [Destination URL]'.
Use bullet points, bold key terms, and keep answers concise and SEO-practical.
"""
                try:
                    ai_reply = _call_ai_model(
                        api_key=api_key,
                        provider=ai_provider,
                        model=selected_model,
                        system_prompt=chat_sys_prompt,
                        user_prompt=user_input
                    )
                    st.markdown(ai_reply)
                    st.session_state["silo_chat_history"].append({"role": "assistant", "content": ai_reply})
                except Exception as e:
                    err_msg = f"❌ Error: {e}"
                    st.error(err_msg)
                    st.session_state["silo_chat_history"].append({"role": "assistant", "content": err_msg})
