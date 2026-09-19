import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import networkx as nx

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

def create_site_architecture_graph(df_links: pd.DataFrame, max_nodes: int = 50):
    """Render interactive network graph for internal link structure."""
    if df_links.empty:
        return go.Figure()

    internal_links = df_links[df_links["is_internal"] == True].head(max_nodes)
    if internal_links.empty:
        return go.Figure()

    G = nx.DiGraph()
    for _, row in internal_links.iterrows():
        # Shorten node labels for cleanliness
        src = row["source_url"].replace("https://", "").replace("http://", "")[:35]
        tgt = row["target_url"].replace("https://", "").replace("http://", "")[:35]
        G.add_edge(src, tgt)

    pos = nx.spring_layout(G, k=0.55, iterations=35, seed=42)

    edge_x = []
    edge_y = []
    for edge in G.edges():
        if edge[0] in pos and edge[1] in pos:
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1.2, color='rgba(148, 163, 184, 0.4)'),
        hoverinfo='none',
        mode='lines'
    )

    node_x = []
    node_y = []
    node_text = []
    node_adj = []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        deg = G.degree(node)
        node_adj.append(deg)
        node_text.append(f"<b>{node}</b><br>Linked Connections: {deg}")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[n[:16] + ".." if len(n) > 16 else n for n in G.nodes()],
        textposition="bottom center",
        textfont=dict(family=FONT_FAMILY, size=10, color="#CBD5E1"),
        hovertext=node_text,
        marker=dict(
            showscale=True,
            colorscale='Blues',
            size=18,
            color=node_adj,
            colorbar=dict(
                thickness=10,
                title=dict(text='Links', side='top', font=dict(color='#CBD5E1', size=11, family=FONT_FAMILY)),
                tickfont=dict(color='#CBD5E1', family=FONT_FAMILY)
            ),
            line_width=2,
            line_color='#38BDF8'
        )
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title=dict(text='Internal Linking Architecture Topology', font=dict(color='#F1F5F9', size=17, family=FONT_FAMILY)),
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=10, r=10, t=45),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=460,
            font=dict(family=FONT_FAMILY)
        )
    )
    return fig
