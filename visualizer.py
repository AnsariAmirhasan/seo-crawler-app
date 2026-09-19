import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import networkx as nx
import math
from urllib.parse import urlparse

FONT_FAMILY = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

def create_health_gauge(score: int):
    """Generate an interactive modern Gauge chart for the SEO Health Score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "SEO Health Score", 'font': {'size': 18, 'color': '#E2E8F0', 'family': FONT_FAMILY}},
        number={'suffix': "/100", 'font': {'size': 36, 'color': '#FFFFFF', 'family': FONT_FAMILY, 'weight': 800}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#64748B", 'tickfont': {'color': '#94A3B8'}},
            'bar': {'color': "#6366F1", 'thickness': 0.26},
            'bgcolor': "rgba(30, 41, 59, 0.6)",
            'borderwidth': 1.5,
            'bordercolor': "rgba(71, 85, 105, 0.4)",
            'steps': [
                {'range': [0, 49], 'color': 'rgba(239, 68, 68, 0.35)'},
                {'range': [50, 79], 'color': 'rgba(245, 158, 11, 0.35)'},
                {'range': [80, 100], 'color': 'rgba(16, 185, 129, 0.35)'}
            ],
            'threshold': {
                'line': {'color': "#10B981", 'width': 4},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=370,
        margin=dict(l=20, r=20, t=50, b=20),
        font=dict(family=FONT_FAMILY)
    )
    return fig

def create_status_code_chart(df_pages: pd.DataFrame):
    """Donut chart of HTTP Status Code distribution."""
    if df_pages.empty:
        return go.Figure()

    status_counts = df_pages["status_code"].value_counts().reset_index()
    status_counts.columns = ["Status Code", "Count"]
    status_counts["Status Label"] = status_counts["Status Code"].apply(
        lambda s: f"200 OK" if s == 200 else (f"3xx Redirect ({s})" if 300 <= s < 400 else (f"4xx Error ({s})" if 400 <= s < 500 else (f"5xx Server ({s})" if 500 <= s < 600 else f"Other ({s})")))
    )

    color_palette = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]

    fig = px.pie(
        status_counts,
        names="Status Label",
        values="Count",
        hole=0.62,
        color_discrete_sequence=color_palette
    )
    fig.update_traces(
        textposition='auto',
        textinfo='percent',
        hoverinfo='label+percent+value',
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Ratio: %{percent}<extra></extra>",
        marker=dict(line=dict(color='#0F172A', width=2.5))
    )
    fig.update_layout(
        title={
            'text': "HTTP Status Distribution",
            'x': 0.05,
            'xanchor': 'left',
            'font': {'color': '#F1F5F9', 'size': 16, 'family': FONT_FAMILY}
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1", family=FONT_FAMILY),
        height=370,
        margin=dict(l=15, r=15, t=55, b=45),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.05,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#94A3B8")
        )
    )
    return fig

def create_issues_bar_chart(df_issues: pd.DataFrame):
    """Horizontal bar chart showing issues sorted by category and severity."""
    if df_issues.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="✨ No Technical Issues Detected! 100% Clean Audit 🎉",
            showarrow=False,
            font=dict(size=15, color="#10B981", family=FONT_FAMILY)
        )
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=370)
        return fig

    issue_summary = df_issues.groupby(["category", "type"]).size().reset_index(name="count")
    
    color_discrete_map = {
        "Error": "#F43F5E",
        "Warning": "#F59E0B",
        "Notice": "#06B6D4"
    }

    fig = px.bar(
        issue_summary,
        x="count",
        y="category",
        color="type",
        orientation="h",
        color_discrete_map=color_discrete_map,
        labels={"count": "Issues Count", "category": "SEO Category", "type": "Severity"}
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Severity: %{data.name}<br>Issues: %{x}<extra></extra>"
    )
    fig.update_layout(
        title=dict(
            text="Issues by Category & Severity",
            x=0.01,
            y=0.98,
            xanchor="left",
            yanchor="top",
            font=dict(color='#F1F5F9', size=15, family=FONT_FAMILY)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.01,
            title=dict(text=""),
            font=dict(size=11, color="#94A3B8")
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1", family=FONT_FAMILY),
        height=370,
        margin=dict(l=10, r=20, t=80, b=50),
        xaxis=dict(
            title=dict(text="Issues Count", standoff=10, font=dict(size=11, color="#94A3B8")),
            gridcolor="rgba(51, 65, 85, 0.4)",
            tickfont=dict(color="#94A3B8", size=10)
        ),
        yaxis=dict(
            title=None,
            gridcolor="rgba(51, 65, 85, 0.4)",
            tickfont=dict(color="#CBD5E1", size=11),
            automargin=True
        )
    )
    return fig

def create_site_architecture_graph(
    df_links: pd.DataFrame,
    df_pages: pd.DataFrame = None,
    view_mode: str = "Hierarchy by Depth",
    depth_filter: str = "All",
    status_filter: str = "All",
    seo_state_filter: str = "All",
    search_query: str = "",
    selected_url: str = None,
    max_nodes: int = 100
):
    """
    Render professional interactive SEO Site Architecture and Internal Link Graph.
    Supports Hierarchy by Depth, Radial Depth Rings, Force-Directed clustering, and Hubs ranking.
    Highlights 200 OK, 3xx Redirects, 4xx/5xx Broken pages, Orphans, and Hubs.
    """
    if df_links is None or df_links.empty:
        return go.Figure()

    # 1. Build Page Metadata Dictionary
    node_meta = {}
    if df_pages is not None and not df_pages.empty:
        # Determine hub threshold (e.g. top 10% inlinks or >= 12)
        inlinks_series = df_pages["inlinks_count"] if "inlinks_count" in df_pages.columns else pd.Series([0])
        hub_cutoff = max(10, int(inlinks_series.quantile(0.90))) if len(inlinks_series) > 5 else 8

        for _, row in df_pages.iterrows():
            u = str(row.get("url", "")).strip()
            if not u:
                continue

            status = int(row.get("status_code", 200) or 200)
            status_desc = str(row.get("status_description") or f"{status}")
            depth = int(row.get("depth", 0) or 0)
            inlinks = int(row.get("inlinks_count", 0) or 0)
            outlinks = int(row.get("internal_outlinks_count", 0) or 0)
            is_orphan = bool(row.get("is_orphan", False))
            is_indexable = bool(row.get("is_indexable", True))
            canonical = str(row.get("canonical_url", "") or "")
            is_rc = bool(row.get("is_redirect_chain", False))
            is_rl = bool(row.get("is_redirect_loop", False))
            title = str(row.get("title", "") or "").strip()
            path = urlparse(u).path or "/"

            # Assign SEO state & color
            if status >= 500:
                seo_state = "Server Error (5xx)"
                color = "#DC2626"
            elif status >= 400:
                seo_state = "Broken Page (4xx)"
                color = "#EF4444"
            elif is_rc:
                seo_state = "Redirect Chain"
                color = "#F97316"
            elif 300 <= status < 400:
                seo_state = "Redirect (3xx)"
                color = "#F59E0B"
            elif is_orphan:
                seo_state = "Orphan Page"
                color = "#A855F7"
            elif depth == 0 or inlinks >= hub_cutoff:
                seo_state = "Hub / Category"
                color = "#38BDF8"
            else:
                seo_state = "Healthy (200 OK)"
                color = "#10B981"

            node_meta[u] = {
                "url": u,
                "title": title or path,
                "path": path,
                "status": status,
                "status_desc": status_desc,
                "depth": depth,
                "inlinks": inlinks,
                "outlinks": outlinks,
                "is_orphan": is_orphan,
                "is_indexable": is_indexable,
                "canonical": canonical,
                "is_rc": is_rc,
                "is_rl": is_rl,
                "seo_state": seo_state,
                "color": color
            }

    # If df_pages wasn't passed or lacked URLs, backfill from links
    all_link_urls = set(df_links["source_url"].dropna().unique()).union(set(df_links["target_url"].dropna().unique()))
    for u in all_link_urls:
        if u not in node_meta:
            path = urlparse(u).path or "/"
            node_meta[u] = {
                "url": u,
                "title": path,
                "path": path,
                "status": 200,
                "status_desc": "200 OK",
                "depth": 1,
                "inlinks": 1,
                "outlinks": 1,
                "is_orphan": False,
                "is_indexable": True,
                "canonical": "",
                "is_rc": False,
                "is_rl": False,
                "seo_state": "Healthy (200 OK)",
                "color": "#10B981"
            }

    # 2. Filter Candidate Nodes
    candidate_urls = set(node_meta.keys())

    # Depth filter
    if depth_filter != "All":
        if depth_filter == "5+":
            candidate_urls = {u for u in candidate_urls if node_meta[u]["depth"] >= 5}
        else:
            try:
                target_d = int(depth_filter.replace("Depth ", ""))
                candidate_urls = {u for u in candidate_urls if node_meta[u]["depth"] == target_d}
            except Exception:
                pass

    # Status filter
    if status_filter != "All":
        if status_filter == "200 OK":
            candidate_urls = {u for u in candidate_urls if node_meta[u]["status"] == 200}
        elif status_filter == "3xx Redirects":
            candidate_urls = {u for u in candidate_urls if 300 <= node_meta[u]["status"] < 400}
        elif status_filter == "4xx Broken":
            candidate_urls = {u for u in candidate_urls if 400 <= node_meta[u]["status"] < 500}
        elif status_filter == "5xx Server Errors":
            candidate_urls = {u for u in candidate_urls if node_meta[u]["status"] >= 500}

    # SEO State filter
    if seo_state_filter != "All":
        if seo_state_filter == "Healthy":
            candidate_urls = {u for u in candidate_urls if node_meta[u]["seo_state"] == "Healthy (200 OK)"}
        elif seo_state_filter == "Orphans":
            candidate_urls = {u for u in candidate_urls if node_meta[u]["is_orphan"]}
        elif seo_state_filter == "Hubs / Categories":
            candidate_urls = {u for u in candidate_urls if node_meta[u]["seo_state"] == "Hub / Category"}
        elif seo_state_filter == "Broken Pages":
            candidate_urls = {u for u in candidate_urls if node_meta[u]["status"] >= 400}
        elif seo_state_filter == "Redirect Chains":
            candidate_urls = {u for u in candidate_urls if node_meta[u]["is_rc"] or node_meta[u]["is_rl"]}
        elif seo_state_filter == "Redirects":
            candidate_urls = {u for u in candidate_urls if 300 <= node_meta[u]["status"] < 400}

    # Search query
    search_matches = set()
    if search_query:
        sq = search_query.lower().strip()
        for u in candidate_urls:
            m = node_meta[u]
            if sq in u.lower() or sq in m["title"].lower() or sq in m["path"].lower():
                search_matches.add(u)
        if search_matches:
            # Keep matches + immediate connections if candidate pool is large
            pass

    if not candidate_urls:
        return go.Figure()

    # 3. Intelligent Sampling for Large Datasets
    if len(candidate_urls) > max_nodes:
        # Prioritize: 1) Depth 0 (Home), 2) Selected URL, 3) Search matches, 4) Critical Issues, 5) Top Hubs
        prioritized = []
        # Home
        for u in candidate_urls:
            if node_meta[u]["depth"] == 0:
                prioritized.append(u)
        # Selected
        if selected_url and selected_url in candidate_urls and selected_url not in prioritized:
            prioritized.append(selected_url)
        # Search matches
        for u in search_matches:
            if u not in prioritized and len(prioritized) < max_nodes:
                prioritized.append(u)
        # Critical Issues: Broken, Redirect Chains, Orphans
        for u in candidate_urls:
            if u not in prioritized and (node_meta[u]["status"] >= 400 or node_meta[u]["is_rc"] or node_meta[u]["is_orphan"]):
                prioritized.append(u)
                if len(prioritized) >= max_nodes:
                    break
        # Top Hubs by inlinks
        remaining = [u for u in candidate_urls if u not in prioritized]
        remaining.sort(key=lambda u: node_meta[u]["inlinks"], reverse=True)
        for u in remaining:
            if len(prioritized) < max_nodes:
                prioritized.append(u)
            else:
                break
        candidate_urls = set(prioritized)

    # 4. Build NetworkX Graph
    G = nx.DiGraph()
    for u in candidate_urls:
        G.add_node(u)

    internal_links = df_links[df_links["is_internal"] == True]
    filtered_edges = []
    for _, row in internal_links.iterrows():
        src = str(row.get("source_url", "")).strip()
        tgt = str(row.get("target_url", "")).strip()
        if src in candidate_urls and tgt in candidate_urls:
            G.add_edge(src, tgt)
            filtered_edges.append((src, tgt))

    # 5. Layout Calculation
    pos = {}
    shapes = []
    annotations = []

    if view_mode == "Hierarchy by Depth":
        # Group by depth
        depth_buckets = {}
        for u in candidate_urls:
            d = node_meta[u]["depth"]
            depth_buckets.setdefault(d, []).append(u)

        sorted_depths = sorted(depth_buckets.keys())
        y_step = 4.5

        for d in sorted_depths:
            nodes_at_d = depth_buckets[d]
            # Order nodes to minimize crossing: sort by parent's avg position or inlinks
            nodes_at_d.sort(key=lambda u: node_meta[u]["inlinks"], reverse=True)
            cnt = len(nodes_at_d)
            spacing = max(2.5, min(5.0, 60.0 / max(cnt, 1)))
            total_w = (cnt - 1) * spacing
            y_val = -float(d) * y_step

            for i, u in enumerate(nodes_at_d):
                x_val = -total_w / 2.0 + i * spacing
                pos[u] = (x_val, y_val)

            # Depth level guide line and label
            shapes.append(dict(
                type="line",
                xref="paper", yref="y",
                x0=0, x1=1,
                y0=y_val, y1=y_val,
                line=dict(color="rgba(148, 163, 184, 0.08)", width=1, dash="dot")
            ))
            depth_label = "Depth 0 (Home)" if d == 0 else f"Depth {d}"
            annotations.append(dict(
                xref="paper", yref="y",
                x=0.01, y=y_val + 0.5,
                text=f"<b>{depth_label}</b> ({cnt} pages)",
                showarrow=False,
                font=dict(size=10.5, color="#64748B", family=FONT_FAMILY),
                align="left"
            ))

    elif view_mode == "Radial / Depth Rings":
        depth_buckets = {}
        for u in candidate_urls:
            d = node_meta[u]["depth"]
            depth_buckets.setdefault(d, []).append(u)

        for d, nodes_at_d in depth_buckets.items():
            cnt = len(nodes_at_d)
            if d == 0:
                for u in nodes_at_d:
                    pos[u] = (0.0, 0.0)
            else:
                r_val = float(d) * 6.0
                angle_step = (2.0 * math.pi) / max(cnt, 1)
                for i, u in enumerate(nodes_at_d):
                    theta = i * angle_step
                    pos[u] = (r_val * math.cos(theta), r_val * math.sin(theta))

                shapes.append(dict(
                    type="circle",
                    xref="x", yref="y",
                    x0=-r_val, y0=-r_val,
                    x1=r_val, y1=r_val,
                    line=dict(color="rgba(148, 163, 184, 0.10)", width=1, dash="dash")
                ))
                annotations.append(dict(
                    x=0, y=r_val + 0.4,
                    text=f"Depth {d}",
                    showarrow=False,
                    font=dict(size=9.5, color="#64748B", family=FONT_FAMILY)
                ))

    elif view_mode == "Hubs & Authorities":
        # X: Inlinks (log scale), Y: Depth
        for u in candidate_urls:
            inlinks = node_meta[u]["inlinks"]
            d = node_meta[u]["depth"]
            x_val = math.log(max(inlinks, 1) + 1) * 8.0
            # Add subtle jitter to Y to prevent exact overlaps
            import random
            random.seed(hash(u) % 10000)
            jitter = (random.random() - 0.5) * 1.8
            y_val = -float(d) * 4.0 + jitter
            pos[u] = (x_val, y_val)

    else:
        # Default / Fallback: Force-Directed (Organic Clusters)
        k_val = 1.8 / math.sqrt(max(len(G.nodes()), 1))
        pos = nx.spring_layout(G, k=k_val, iterations=55, seed=42)

    # 6. Edges Construction (with Selected In/Out Highlighting)
    if selected_url and selected_url in candidate_urls:
        inc_x, inc_y = [], []
        out_x, out_y = [], []
        dim_x, dim_y = [], []

        for src, tgt in filtered_edges:
            if src in pos and tgt in pos:
                x0, y0 = pos[src]
                x1, y1 = pos[tgt]
                if tgt == selected_url:
                    inc_x.extend([x0, x1, None])
                    inc_y.extend([y0, y1, None])
                elif src == selected_url:
                    out_x.extend([x0, x1, None])
                    out_y.extend([y0, y1, None])
                else:
                    dim_x.extend([x0, x1, None])
                    dim_y.extend([y0, y1, None])

        edge_traces = [
            go.Scatter(
                x=dim_x, y=dim_y,
                mode="lines",
                line=dict(width=0.8, color="rgba(148, 163, 184, 0.12)"),
                hoverinfo="none",
                showlegend=False
            ),
            go.Scatter(
                x=inc_x, y=inc_y,
                mode="lines",
                line=dict(width=2.5, color="#38BDF8"),
                hoverinfo="none",
                name="Incoming Links to Selected"
            ),
            go.Scatter(
                x=out_x, y=out_y,
                mode="lines",
                line=dict(width=2.5, color="#F59E0B"),
                hoverinfo="none",
                name="Outgoing Links from Selected"
            )
        ]
    else:
        edge_x, edge_y = [], []
        for src, tgt in filtered_edges:
            if src in pos and tgt in pos:
                x0, y0 = pos[src]
                x1, y1 = pos[tgt]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

        edge_traces = [
            go.Scatter(
                x=edge_x, y=edge_y,
                mode="lines",
                line=dict(width=1.0, color="rgba(148, 163, 184, 0.30)"),
                hoverinfo="none",
                showlegend=False
            )
        ]

    # 7. Nodes Construction
    node_x = []
    node_y = []
    node_colors = []
    node_sizes = []
    node_labels = []
    node_line_widths = []
    node_line_colors = []
    custom_data = []

    show_all_labels = len(candidate_urls) <= 45

    for u in candidate_urls:
        if u not in pos:
            continue
        x, y = pos[u]
        node_x.append(x)
        node_y.append(y)

        m = node_meta[u]
        node_colors.append(m["color"])

        # Size scaled smoothly by inlinks (clamp 14 to 34)
        sz = 14 + 18 * min(1.0, math.sqrt(m["inlinks"]) / 4.5)
        node_sizes.append(sz)

        # Border formatting
        if selected_url and u == selected_url:
            node_line_widths.append(4.0)
            node_line_colors.append("#FFFFFF")
        elif search_matches and u in search_matches:
            node_line_widths.append(3.5)
            node_line_colors.append("#38BDF8")
        else:
            node_line_widths.append(1.5)
            node_line_colors.append("rgba(15, 23, 42, 0.8)")

        # Display Label: Title + Path
        clean_title = m["title"][:16] + (".." if len(m["title"]) > 16 else "")
        clean_path = m["path"][:14] + (".." if len(m["path"]) > 14 else "")
        
        # Decide if label is shown directly on graph
        if show_all_labels or m["seo_state"] != "Healthy (200 OK)" or m["inlinks"] >= 12 or (selected_url and u == selected_url):
            node_labels.append(f"{clean_title}<br>{clean_path}")
        else:
            node_labels.append("")

        custom_data.append([
            m["title"],
            m["url"],
            m["status_desc"],
            m["depth"],
            m["inlinks"],
            m["outlinks"],
            "Yes" if m["is_indexable"] else "No",
            m["seo_state"]
        ])

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=node_labels,
        textposition="bottom center",
        textfont=dict(family=FONT_FAMILY, size=9.5, color="#E2E8F0"),
        customdata=custom_data,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "<b>URL:</b> %{customdata[1]}<br>"
            "<b>Status:</b> %{customdata[2]}<br>"
            "<b>Crawl Depth:</b> %{customdata[3]}<br>"
            "<b>Incoming Links:</b> %{customdata[4]} | <b>Outgoing Links:</b> %{customdata[5]}<br>"
            "<b>Indexable:</b> %{customdata[6]}<br>"
            "<b>SEO State:</b> %{customdata[7]}"
            "<extra></extra>"
        ),
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=node_line_widths, color=node_line_colors),
            opacity=0.96
        ),
        showlegend=False
    )

    fig = go.Figure(
        data=edge_traces + [node_trace],
        layout=go.Layout(
            showlegend=bool(selected_url),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="right", x=1,
                font=dict(size=11, color="#CBD5E1", family=FONT_FAMILY),
                bgcolor="rgba(15, 23, 42, 0.6)"
            ),
            hovermode="closest",
            margin=dict(b=20, l=20, r=20, t=30),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            shapes=shapes,
            annotations=annotations,
            height=640,
            dragmode="pan",
            font=dict(family=FONT_FAMILY)
        )
    )
    return fig
