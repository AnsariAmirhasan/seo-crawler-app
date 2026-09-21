"""
Brand-First Content Generation Module for CrawlPilot.
Implements the 10-point Brand Analysis framework before creating tailored social creatives:
1. Brand identity
2. Brand colors
3. Logo & visual cues
4. Typography & styling
5. Brand personality & tone
6. Target audience
7. Industry
8. Market/location
9. Existing social presence
10. Campaign objective

Rule: The final creative must feel like it belongs to the brand even if the logo is hidden.
Maintains brand consistency without making every post visually identical.
"""

import io
import json
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Optional, Dict, Any

# ==============================================================================
# 1. BRAND DISCOVERY & AUTOMATED DNA EXTRACTION
# ==============================================================================

def extract_brand_dna_from_url(url: str) -> Dict[str, Any]:
    """
    Scrapes the target domain to extract baseline brand signals:
    Title, Meta description, Logo, Detected brand colors, Font hints, and Heading copy.
    """
    if not url.startswith("http"):
        url = "https://" + url

    dna = {
        "brand_name": "",
        "tagline": "",
        "industry_hint": "",
        "detected_colors": [],
        "logo_url": "",
        "detected_fonts": [],
        "tone_sample": "",
        "market_hint": "Global",
        "url": url
    }

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        if res.status_code != 200:
            return dna

        soup = BeautifulSoup(res.text, "html.parser")
        domain = urlparse(url).netloc.replace("www.", "")

        # 1. Brand Name
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            dna["brand_name"] = og_site["content"].strip()
        else:
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                parts = re.split(r"[-|•—]", title_tag.string)
                dna["brand_name"] = parts[-1].strip() if len(parts) > 1 else parts[0].strip()
            else:
                dna["brand_name"] = domain.split(".")[0].title()

        # 2. Tagline / Value Proposition
        og_desc = soup.find("meta", property="og:description")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            dna["tagline"] = og_desc["content"].strip()
        elif meta_desc and meta_desc.get("content"):
            dna["tagline"] = meta_desc["content"].strip()

        # 3. Logo
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            dna["logo_url"] = og_img["content"].strip()
        else:
            for img in soup.find_all("img"):
                src = img.get("src", "")
                alt = img.get("alt", "")
                if "logo" in src.lower() or "logo" in alt.lower():
                    if src.startswith("//"):
                        dna["logo_url"] = "https:" + src
                    elif src.startswith("/"):
                        dna["logo_url"] = url.rstrip("/") + src
                    elif src.startswith("http"):
                        dna["logo_url"] = src
                    break

        # 4. Detected Colors
        colors = []
        theme_color = soup.find("meta", attrs={"name": "theme-color"})
        if theme_color and theme_color.get("content"):
            colors.append(theme_color["content"].strip())

        raw_snippet = res.text[:25000]
        found_hex = re.findall(r"#(?:[0-9a-fA-F]{3}){1,2}\b", raw_snippet)
        for h in found_hex:
            if h.upper() not in ["#FFFFFF", "#000000", "#FFF", "#000"] and h.upper() not in colors:
                colors.append(h.upper())
                if len(colors) >= 3:
                    break
        dna["detected_colors"] = colors if colors else ["#1E3A8A", "#3B82F6", "#F59E0B"]

        # 5. Detected Fonts
        fonts = []
        for l in soup.find_all("link", rel="stylesheet"):
            href = l.get("href", "")
            if "fonts.googleapis.com" in href and "family=" in href:
                families = re.findall(r"family=([^:&]+)", href)
                for f in families:
                    fonts.append(f.replace("+", " "))
        dna["detected_fonts"] = list(dict.fromkeys(fonts))[:3] if fonts else ["Plus Jakarta Sans", "Inter"]

        # 6. Sample Copy for Tone
        h1s = [h.get_text(strip=True) for h in soup.find_all("h1")[:3]]
        h2s = [h.get_text(strip=True) for h in soup.find_all("h2")[:3]]
        dna["tone_sample"] = " | ".join(h1s + h2s)[:300]

    except Exception:
        pass

    return dna


# ==============================================================================
# 2. AI GENERATION ENGINE FOR BRAND-FIRST CAMPAIGNS
# ==============================================================================

def generate_brand_first_campaign(
    brand_identity: str,
    brand_colors: str,
    logo_info: str,
    typography: str,
    brand_personality: str,
    target_audience: str,
    industry: str,
    market_location: str,
    existing_social_presence: str,
    campaign_objective: str,
    campaign_topic: str,
    platforms: list,
    api_key: str = "",
    provider: str = "Google Gemini",
    model: str = "gemini-2.5-flash"
) -> Dict[str, Any]:
    """
    Executes the Brand-First content generation prompt.
    Analyzes all 10 pillars first, then drafts tailored creatives for selected platforms.
    """
    system_prompt = f"""You are a World-Class Brand Creative Director and Social Media Strategist.
Your core operating principle is:
"NEVER GENERATE SOCIAL CONTENT BEFORE UNDERSTANDING THE BRAND."

First, thoroughly analyze all 10 brand pillars:
1. Brand identity & positioning
2. Brand colors & visual mood
3. Logo & brand mark role
4. Typography & typography hierarchy
5. Brand personality, voice, & tone of voice rules
6. Target audience psychology, desires, & friction points
7. Industry dynamics & category tropes to avoid
8. Market/location context & cultural nuances
9. Existing social presence alignment
10. Campaign objective & conversion mechanism

Rule: The final creative MUST feel unmistakably like it belongs to the brand even if the logo is temporarily hidden.
Maintain strong brand consistency without making every post visually identical.

INPUT BRAND PROFILE:
- Brand Name / Identity: {brand_identity}
- Brand Colors / Aesthetic: {brand_colors}
- Logo & Mark Description: {logo_info}
- Typography / Hierarchy: {typography}
- Brand Personality / Tone of Voice: {brand_personality}
- Target Audience: {target_audience}
- Industry / Niche: {industry}
- Market / Location: {market_location}
- Existing Social Footprint: {existing_social_presence}
- Campaign Objective: {campaign_objective}
- Specific Campaign Topic / Offer: {campaign_topic}
- Target Platforms: {', '.join(platforms)}

Generate a comprehensive, structured output in clean JSON format with these exact keys:
{{
    "brand_dna_analysis": {{
        "core_identity_summary": "1-2 sentences on who the brand is and its core value proposition",
        "visual_mood_and_palette": "Explanation of how brand colors and typography interact",
        "tone_of_voice_rules": ["Rule 1", "Rule 2", "Rule 3"],
        "hidden_logo_test": "Why someone would recognize this post as this specific brand even if the logo is blocked",
        "visual_consistency_without_monotony": "How to vary formats (e.g. bold quotes, diagrams, photography) while keeping the brand cohesive"
    }},
    "instagram_kit": {{
        "carousel_title": "Title of 5-slide educational/value carousel",
        "slides": [
            {{"slide_number": 1, "visual_art_direction": "Visual layout and color usage", "headline": "Hook headline", "body_copy": "Short text"}},
            {{"slide_number": 2, "visual_art_direction": "Visual cue", "headline": "Point 1", "body_copy": "Insight"}},
            {{"slide_number": 3, "visual_art_direction": "Visual cue", "headline": "Point 2", "body_copy": "Insight"}},
            {{"slide_number": 4, "visual_art_direction": "Visual cue", "headline": "Point 3", "body_copy": "Insight"}},
            {{"slide_number": 5, "visual_art_direction": "CTA slide layout", "headline": "Call to Action", "body_copy": "Next step"}}
        ],
        "reel_short_hook": "3-second opening hook and visual script for short-form video",
        "caption": "Full Instagram caption with line breaks, value delivery, and CTA",
        "hashtags": "#brand #niche #industry"
    }},
    "linkedin_thought_leadership": {{
        "hook": "Opening 2 lines to stop the scroll",
        "story_insight": "Body text using conversational paragraphs, vulnerability, or framework",
        "key_takeaway": "Bullet points summarizing the lesson",
        "closing_question": "Discussion prompt to drive comments"
    }},
    "x_twitter_thread": [
        "1/ Tweet 1 - High-curiosity hook statement",
        "2/ Tweet 2 - Core insight or problem breakdown",
        "3/ Tweet 3 - The counter-intuitive solution",
        "4/ Tweet 4 - Actionable framework or steps",
        "5/ Tweet 5 - Wrap up + Call to Action"
    ],
    "art_director_brief": {{
        "recommended_primary_color": "{brand_colors.split(',')[0].strip() if brand_colors else '#1E3A8A'}",
        "recommended_accent_color": "{brand_colors.split(',')[1].strip() if ',' in brand_colors else '#F59E0B'}",
        "font_pairing": "{typography if typography else 'Plus Jakarta Sans'}",
        "do_list": ["Use generous whitespace", "High-contrast text", "Consistent corner radiuses"],
        "dont_list": ["Avoid generic stock photos", "Do not use clashing neon colors", "Don't overload with paragraphs"]
    }}
}}
Return ONLY valid JSON. Do not include markdown code block quotes around the JSON.
"""

    if api_key:
        try:
            from ai_audit_enricher import call_ai_model
            resp = call_ai_model(
                prompt=system_prompt,
                api_key=api_key,
                provider=provider,
                model=model,
                country=market_location,
                temperature=0.3
            )
            clean_resp = resp.strip()
            if clean_resp.startswith("```json"):
                clean_resp = clean_resp[7:]
            if clean_resp.startswith("```"):
                clean_resp = clean_resp[3:]
            if clean_resp.endswith("```"):
                clean_resp = clean_resp[:-3]
            clean_resp = clean_resp.strip()
            return json.loads(clean_resp)
        except Exception as e:
            st.warning(f"AI Provider error: {e}. Falling back to strategic Brand-First template engine.")

    # High-quality offline fallback template reflecting the 10 pillars
    primary_c = brand_colors.split(",")[0].strip() if brand_colors else "#1E3A8A"
    accent_c = brand_colors.split(",")[1].strip() if "," in brand_colors else "#F59E0B"
    return {
        "brand_dna_analysis": {
            "core_identity_summary": f"{brand_identity} stands as an authoritative, customer-centric leader in the {industry} space.",
            "visual_mood_and_palette": f"Rooted in primary tone ({primary_c}) with sharp commercial accents ({accent_c}). Aesthetics prioritize clarity, trust, and premium execution.",
            "tone_of_voice_rules": [
                f"Lead with authority: Frame insights from deep expertise in {industry}.",
                f"Speak directly to {target_audience} without fluff or jargon.",
                f"Embody {brand_personality}: Every sentence must sound intentional, distinct, and confident."
            ],
            "hidden_logo_test": f"Followers recognize this content instantly through proprietary color framing ({primary_c}), consistent typography rhythm ({typography}), and unmistakable {brand_personality} tonality.",
            "visual_consistency_without_monotony": "Alternate between bold typography-led slides, framework diagrams, and high-impact macro product/service visuals while preserving signature margins and accent colors."
        },
        "instagram_kit": {
            "carousel_title": f"The 5 Rules of {campaign_topic or industry} Every Leader Needs to Know",
            "slides": [
                {"slide_number": 1, "visual_art_direction": f"Deep {primary_c} background with bold 48pt typography and subtle accent border.", "headline": f"Why Most Are Getting {campaign_topic or 'Strategy'} Wrong", "body_copy": "Swipe to see the framework that changes everything →"},
                {"slide_number": 2, "visual_art_direction": "Minimalist card layout with high-contrast numerical callout (01).", "headline": "The Common Pitfall", "body_copy": f"Most in {industry} chase vanity metrics instead of sustainable fundamentals."},
                {"slide_number": 3, "visual_art_direction": "Comparison split screen showing 'Old Way' vs 'Our Way'.", "headline": "The Mindset Shift", "body_copy": "True scale begins when you optimize for client outcomes first."},
                {"slide_number": 4, "visual_art_direction": f"Key takeaway box highlighted with {accent_c} accent.", "headline": "The Execution Formula", "body_copy": "Consistent micro-actions compound into insurmountable competitive advantage."},
                {"slide_number": 5, "visual_art_direction": f"Clean closing slide with prominent CTA and {brand_identity} signature.", "headline": "Ready to Elevate Your Standard?", "body_copy": f"Save this post for reference and tap the link in our bio to get started."}
            ],
            "reel_short_hook": f"Stop scrolling if you're trying to figure out {campaign_topic or 'your strategy'} in {market_location}...",
            "caption": f"When it comes to {campaign_topic or industry}, the difference between good and world-class isn't luck—it's intentionality.\n\nAt {brand_identity}, we built our approach around one simple truth: {brand_personality.capitalize() if brand_personality else 'quality'} execution beats noise every single time.\n\nHere is how we look at it:\n1️⃣ Clarity over complexity\n2️⃣ Audience empathy over ego\n3️⃣ Long-term compounding over quick shortcuts\n\nWhich of these points resonates most with where you are today? Drop your thoughts below 👇",
            "hashtags": f"#{brand_identity.replace(' ', '')} #{industry.replace(' ', '')} #Strategy #Excellence #{market_location.replace(' ', '')}"
        },
        "linkedin_thought_leadership": {
            "hook": f"The biggest mistake I see companies in {industry} making right now?\n\nThey're treating {campaign_topic or 'their core offering'} like a transaction instead of a transformational partnership.",
            "story_insight": f"Over the past few quarters at {brand_identity}, we've observed that {target_audience} doesn't want another generic pitch. They want radical transparency, tested methodology, and dependable outcomes.\n\nWhen you cut through the noise, excellence comes down to three non-negotiables:\n\n• Radical alignment with client pain points\n• Relentless focus on measurable ROI\n• Upholding standards even when no one is watching",
            "key_takeaway": f"1. Stop chasing trends that dilute your core identity.\n2. Deepen trust with your primary {target_audience}.\n3. Build for retention, not just acquisition.",
            "closing_question": f"If you're operating in {market_location}, how are you adapting to this shift? Would love to hear your perspective."
        },
        "x_twitter_thread": [
            f"1/ Most brands in {industry} fail at social because they generate content BEFORE understanding their brand DNA.\n\nHere is the exact playbook {brand_identity} uses to stand out (even with the logo hidden) 🧵👇",
            f"2/ Rule #1: Visual Moat\n\nYour palette ({primary_c}) and typography ({typography}) aren't decorations—they are psychological anchors. If your post looks like anyone else's in the feed, you've already lost.",
            f"3/ Rule #2: Tone Distinction\n\nNever sound generic. Our voice is {brand_personality}. We don't speak to everyone—we speak specifically to {target_audience}.",
            f"4/ Rule #3: The Hidden Logo Test\n\nCover your logo with your thumb. Does the post still scream your brand?\n\nIf the answer is no, rewrite it until it does.",
            f"5/ The bottom line: Brand consistency doesn't mean boring repetition—it means consistent excellence across every touchpoint.\n\nRT the first tweet if you found this valuable! 🚀"
        ],
        "art_director_brief": {
            "recommended_primary_color": primary_c,
            "recommended_accent_color": accent_c,
            "font_pairing": typography or "Plus Jakarta Sans + JetBrains Mono",
            "do_list": [
                f"Maintain strict adherence to primary color {primary_c}",
                "Use high typographic hierarchy with ample breathing room",
                "Ensure every carousel has an active curiosity hook on Slide 1"
            ],
            "dont_list": [
                "Never use clashing unbranded stock imagery",
                "Do not overcrowd slides with more than 35 words per card",
                "Avoid generic corporate templates that fail the Hidden Logo Test"
            ]
        }
    }


# ==============================================================================
# 3. STREAMLIT UI RENDERER
# ==============================================================================

def render_brand_first_content_page():
    """Renders the Brand-First Content Generation workspace in CrawlPilot."""

    # 1. Hero Header
    st.markdown("""
    <div style="background: radial-gradient(130% 120% at 50% -10%, #1E1B4B 0%, #0F172A 60%, #020617 100%); padding: 2.8rem 2.2rem 2.2rem; border-radius: 20px; border: 1px solid rgba(139, 92, 246, 0.3); text-align: center; margin-bottom: 2rem; box-shadow: 0 20px 45px -10px rgba(0,0,0,0.6);">
        <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.35); padding: 4px 14px; border-radius: 9999px; margin-bottom: 1rem;">
            <span style="font-size: 0.95rem;">🎨</span>
            <span style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #C4B5FD;">Brand-First Creative Engine</span>
        </div>
        <h1 style="font-size: 2.6rem; font-weight: 900; color: #FFFFFF; letter-spacing: -0.03em; margin: 0 0 0.6rem 0; line-height: 1.15;">
            Brand-First Social Content Generator
        </h1>
        <p style="color: #94A3B8; font-size: 1.05rem; max-width: 720px; margin: 0 auto; line-height: 1.6;">
            <b>Never generate social content before understanding the brand.</b> Deeply analyze brand identity, palette, typography, voice, and audience psychology—then create creatives that pass the <i>Hidden Logo Test</i>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 2. Top URL Quick-Scan Auto-Extract Bar
    st.markdown("<div style='font-size: 0.95rem; font-weight: 800; color: #F8FAFC; margin-bottom: 8px;'>⚡ Step 1: Auto-Scan Brand DNA from Website (Optional)</div>", unsafe_allow_html=True)
    col_u1, col_u2 = st.columns([3.5, 1.2])
    with col_u1:
        auto_url = st.text_input(
            "Website URL to Scan",
            value=st.session_state.get("brand_scanned_url", ""),
            placeholder="https://yourbrand.com (Leave empty to fill manually)",
            label_visibility="collapsed",
            key="brand_url_scan_input"
        )
    with col_u2:
        scan_btn = st.button("🔍 Auto-Extract DNA", use_container_width=True, type="primary")

    if scan_btn and auto_url:
        with st.spinner(f"🌐 Crawling {auto_url} to extract brand colors, typography, and identity..."):
            extracted = extract_brand_dna_from_url(auto_url)
            st.session_state["brand_scanned_dna"] = extracted
            st.session_state["brand_scanned_url"] = auto_url
            st.success(f"✅ Brand DNA extracted for **{extracted['brand_name']}**! Form pre-filled below.")

    dna_cache = st.session_state.get("brand_scanned_dna", {})

    st.markdown("<div style='margin: 1.5rem 0 1rem;'></div>", unsafe_allow_html=True)

    # 3. The 10 Brand Pillars Input Form
    st.markdown("<div style='font-size: 1.1rem; font-weight: 800; color: #F8FAFC; margin-bottom: 12px;'>📋 Step 2: The 10 Brand-First Analysis Pillars</div>", unsafe_allow_html=True)

    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            brand_name = st.text_input(
                "1. Brand Identity & Core Name *",
                value=dna_cache.get("brand_name", "NextGen Biz Solution"),
                help="The core name and primary positioning of the company."
            )
            brand_colors = st.text_input(
                "2. Brand Colors (Hex Codes / Primary, Secondary, Accent) *",
                value=", ".join(dna_cache.get("detected_colors", ["#1E3A8A", "#F59E0B", "#10B981"])),
                help="Comma-separated hex colors (e.g. #1E3A8A, #F59E0B)."
            )
            logo_info = st.text_input(
                "3. Logo & Visual Mark Description",
                value=dna_cache.get("logo_url", "Clean geometric monogram with gold tech accents"),
                help="Describe the logo style, icon, or URL to logo asset."
            )
            typography = st.text_input(
                "4. Typography & Font Styling",
                value=", ".join(dna_cache.get("detected_fonts", ["Plus Jakarta Sans", "Inter"])),
                help="Primary headline and body fonts (e.g. Plus Jakarta Sans, Outfit, Playfair)."
            )
            brand_personality = st.text_input(
                "5. Brand Personality & Tone of Voice *",
                value="Authoritative, sharp, data-backed, yet accessible and customer-first",
                help="Personality traits (e.g. Luxury & Minimalist, Witty & Playful, Bold & Disruptive)."
            )

        with c2:
            target_audience = st.text_input(
                "6. Target Audience Psychology & Demographics *",
                value="Founders, Marketing Directors, and E-commerce Store Owners looking for measurable organic growth",
                help="Who are we speaking to? What are their core desires and fears?"
            )
            industry = st.text_input(
                "7. Industry / Category Niche *",
                value="Digital Marketing & Technical SEO Agency",
                help="Specific niche (e.g. B2B SaaS, Organic Skincare, Luxury Real Estate)."
            )
            market_location = st.text_input(
                "8. Market / Geographical Location *",
                value="United States & Global",
                help="Target geography or cultural region (e.g. USA, UK, India, Canada)."
            )
            existing_social = st.text_input(
                "9. Existing Social Presence & Tone Alignment",
                value="@nextgenbiz on LinkedIn and Instagram (Professional, thought-leadership oriented)",
                help="Current social media handles or active channels."
            )
            campaign_objective = st.selectbox(
                "10. Campaign Objective *",
                options=[
                    "Authority & Thought Leadership (Educate & Build Trust)",
                    "Brand Awareness & Reach (Virality & Follower Growth)",
                    "Lead Generation & Direct Inquiry (High Intent CTA)",
                    "Product / Service Launch Announcement",
                    "Overcoming Objections & Case Study Proof"
                ],
                index=0
            )

    # 4. Campaign Topic & Platform Selection
    col_t1, col_t2 = st.columns([2, 1.5])
    with col_t1:
        campaign_topic = st.text_input(
            "🎯 Specific Topic / Offer / Campaign Angle",
            value="Why Technical SEO & Site Architecture Drive 3X Higher Conversions Than Paid Ads",
            placeholder="e.g. Summer Sale, 5 Common Mistakes in SEO, New Feature Launch"
        )
    with col_t2:
        platforms = st.multiselect(
            "📱 Target Platforms",
            options=["Instagram", "LinkedIn", "X (Twitter)", "Facebook"],
            default=["Instagram", "LinkedIn", "X (Twitter)"]
        )

    # 5. AI Engine Config & Generate Action
    col_ai1, col_ai2, col_ai3 = st.columns([1.5, 2, 1.2])
    with col_ai1:
        ai_prov = st.selectbox("AI Engine", options=["Google Gemini", "ChatGPT (OpenAI)", "Claude (Anthropic)"], index=0)
    with col_ai2:
        saved_key = st.session_state.get("gemini_api_key", "")
        api_k = st.text_input("API Key (Free Gemini / OpenAI)", value=saved_key, type="password", help="Leave blank to use built-in template intelligence")
    with col_ai3:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        gen_btn = st.button("🚀 Generate Brand Content", type="primary", use_container_width=True)

    # 6. Content Generation Execution
    if gen_btn:
        with st.spinner("🧠 Analyzing 10 Brand Pillars and synthesizing creative campaign..."):
            result = generate_brand_first_campaign(
                brand_identity=brand_name,
                brand_colors=brand_colors,
                logo_info=logo_info,
                typography=typography,
                brand_personality=brand_personality,
                target_audience=target_audience,
                industry=industry,
                market_location=market_location,
                existing_social_presence=existing_social,
                campaign_objective=campaign_objective,
                campaign_topic=campaign_topic,
                platforms=platforms,
                api_key=api_k,
                provider=ai_prov
            )
            st.session_state["brand_campaign_result"] = result
            st.success("🎉 Brand-First Content Campaign Generated Successfully!")

    res = st.session_state.get("brand_campaign_result")
    if res:
        st.markdown("<div style='margin: 1.5rem 0 1rem;'></div>", unsafe_allow_html=True)

        # Tabbed Campaign Results Showcase
        res_tab1, res_tab2, res_tab3, res_tab4, res_tab5 = st.tabs([
            "🧬 10-Point Brand DNA",
            "📸 Instagram Carousel & Reel",
            "💼 LinkedIn Thought Leadership",
            "🐦 X (Twitter) Thread",
            "🎨 Art Director & Visual Guide"
        ])

        # TAB 1: Brand DNA
        with res_tab1:
            b_dna = res.get("brand_dna_analysis", {})
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 14px; padding: 1.5rem; margin-bottom: 1.2rem;">
                <div style="font-size: 1.2rem; font-weight: 800; color: #FFFFFF; margin-bottom: 6px;">
                    🧬 Core Identity & Positioning
                </div>
                <div style="color: #CBD5E1; font-size: 0.95rem; line-height: 1.6; margin-bottom: 1rem;">
                    {b_dna.get('core_identity_summary', '')}
                </div>
                
                <div style="font-size: 1.05rem; font-weight: 700; color: #F59E0B; margin-bottom: 6px;">
                    🛡️ The "Hidden Logo Test" Validation:
                </div>
                <div style="background: rgba(245, 158, 11, 0.1); border-left: 3px solid #F59E0B; padding: 10px 14px; border-radius: 6px; color: #E2E8F0; font-size: 0.9rem; line-height: 1.5; margin-bottom: 1rem;">
                    {b_dna.get('hidden_logo_test', '')}
                </div>

                <div style="font-size: 1.05rem; font-weight: 700; color: #38BDF8; margin-bottom: 6px;">
                    🎨 Visual Consistency Without Monotony:
                </div>
                <div style="color: #94A3B8; font-size: 0.88rem; line-height: 1.5;">
                    {b_dna.get('visual_consistency_without_monotony', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("#### 🗣️ Brand Voice & Tone Rules:")
            for rule in b_dna.get("tone_of_voice_rules", []):
                st.markdown(f"- **{rule}**")

        # TAB 2: Instagram
        with res_tab2:
            ig = res.get("instagram_kit", {})
            st.subheader(f"📱 {ig.get('carousel_title', 'Instagram Multi-Slide Carousel')}")
            
            slides = ig.get("slides", [])
            cols_s = st.columns(min(len(slides), 5)) if slides else []
            for idx, sl in enumerate(slides[:5]):
                with cols_s[idx]:
                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(139, 92, 246, 0.4); border-radius: 12px; padding: 12px; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
                        <div>
                            <div style="font-size: 0.72rem; font-weight: 800; color: #A78BFA; text-transform: uppercase;">Slide {sl.get('slide_number', idx+1)}</div>
                            <div style="font-size: 0.88rem; font-weight: 800; color: #FFFFFF; margin: 6px 0;">{sl.get('headline', '')}</div>
                            <div style="font-size: 0.78rem; color: #94A3B8; line-height: 1.4;">{sl.get('body_copy', '')}</div>
                        </div>
                        <div style="margin-top: 10px; font-size: 0.68rem; color: #64748B; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 6px;">
                            🎨 <i>{sl.get('visual_art_direction', '')}</i>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)
            st.markdown("#### 🎥 3-Second Reel / Short Hook:")
            st.info(f"🎬 **Visual & Spoken Hook:** {ig.get('reel_short_hook', '')}")

            st.markdown("#### ✍️ High-Converting Caption & Hashtags:")
            caption_txt = ig.get("caption", "") + "\n\n" + ig.get("hashtags", "")
            st.text_area("Copy Instagram Caption", value=caption_txt, height=200)

        # TAB 3: LinkedIn
        with res_tab3:
            li = res.get("linkedin_thought_leadership", {})
            st.subheader("💼 LinkedIn Thought Leadership Story")
            
            li_full = f"{li.get('hook', '')}\n\n{li.get('story_insight', '')}\n\nKey takeaways:\n{li.get('key_takeaway', '')}\n\n{li.get('closing_question', '')}"
            st.text_area("Copy LinkedIn Post", value=li_full, height=320)

        # TAB 4: X / Twitter
        with res_tab4:
            x_tweets = res.get("x_twitter_thread", [])
            st.subheader("🐦 Viral X (Twitter) Thread")
            for tw in x_tweets:
                st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; color: #F8FAFC; font-size: 0.9rem; line-height: 1.5;">
                    {tw}
                </div>
                """, unsafe_allow_html=True)

            thread_txt = "\n\n---\n\n".join(x_tweets)
            st.download_button("📥 Download Thread as Text", data=thread_txt, file_name="brand_first_twitter_thread.txt", mime="text/plain")

        # TAB 5: Art Direction
        with res_tab5:
            art = res.get("art_director_brief", {})
            st.subheader("🎨 Designer Art Direction & Visual Brief")
            st.caption("Provide this brief to your graphic designers to ensure every creative feels like a cohesive family without duplicate visual templates.")

            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 1.2rem;">
                    <div style="font-weight: 700; color: #F8FAFC; margin-bottom: 8px;">🎨 Color & Font Tokens</div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                        <div style="width: 24px; height: 24px; border-radius: 4px; background: {art.get('recommended_primary_color', '#1E3A8A')}; border: 1px solid #FFF;"></div>
                        <span style="font-size: 0.88rem; color: #CBD5E1;">Primary: <code>{art.get('recommended_primary_color', '#1E3A8A')}</code></span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                        <div style="width: 24px; height: 24px; border-radius: 4px; background: {art.get('recommended_accent_color', '#F59E0B')}; border: 1px solid #FFF;"></div>
                        <span style="font-size: 0.88rem; color: #CBD5E1;">Accent: <code>{art.get('recommended_accent_color', '#F59E0B')}</code></span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.88rem; color: #CBD5E1;">
                        🔤 <b>Font Hierarchy:</b> {art.get('font_pairing', 'Plus Jakarta Sans')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_a2:
                st.markdown("#### ✅ DOs:")
                for d in art.get("do_list", []):
                    st.markdown(f"- <span style='color:#34D399;'>✔</span> {d}", unsafe_allow_html=True)
                st.markdown("#### ❌ DONT's:")
                for dn in art.get("dont_list", []):
                    st.markdown(f"- <span style='color:#F87171;'>✖</span> {dn}", unsafe_allow_html=True)
