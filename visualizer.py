import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import networkx as nx

def create_health_gauge(score: int):
    """Generate an interactive modern Gauge chart for the SEO Health Score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "SEO Health Score", 'font': {'size': 22, 'color': '#E2E8F0'}},
        number={'suffix': "/100", 'font': {'size': 36, 'color': '#FFFFFF'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#94A3B8"},
            'bar': {'color': "#6366F1", 'thickness': 0.25},
            'bgcolor': "#1E293B",
            'borderwidth': 2,
            'bordercolor': "#334155",
            'steps': [
                {'range': [0, 49], 'color': 'rgba(239, 68, 68, 0.4)'},
                {'range': [50, 79], 'color': 'rgba(234, 179, 8, 0.4)'},
                {'range': [80, 100], 'color': 'rgba(16, 185, 129, 0.4)'}
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
        height=260,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

def create_status_code_chart(df_pages: pd.DataFrame):
    """Donut chart of HTTP Status Code distribution."""
    if df_pages.empty:
        return go.Figure()

    status_counts = df_pages["status_code"].value_counts().reset_index()
    status_counts.columns = ["Status Code", "Count"]
    status_counts["Status Label"] = status_counts["Status Code"].apply(
        lambda s: f"200 OK" if s == 200 else (f"3xx Redirect ({s})" if 300 <= s < 400 else (f"4xx Error ({s})" if 400 <= s < 500 else f"Other ({s})"))
    )

    color_map = {
        200: "#10B981",
        301: "#3B82F6",
        302: "#60A5FA",
        404: "#EF4444",
        500: "#DC2626",
        0: "#F59E0B"
    }

    fig = px.pie(
        status_counts,
        names="Status Label",
        values="Count",
        hole=0.55,
        color_discrete_sequence=["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6"]
    )
    fig.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#0F172A', width=2)))
    fig.update_layout(
        title={'text': "HTTP Status Distribution", 'font': {'color': '#E2E8F0', 'size': 16}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1"),
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    return fig

def create_issues_bar_chart(df_issues: pd.DataFrame):
    """Horizontal bar chart showing issues sorted by category and severity."""
    if df_issues.empty:
        fig = go.Figure()
        fig.add_annotation(text="No Technical Issues Detected 🎉", showarrow=False, font=dict(size=16, color="#10B981"))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=280)
        return fig

    issue_summary = df_issues.groupby(["category", "type"]).size().reset_index(name="count")
    
    color_discrete_map = {
        "Error": "#EF4444",
        "Warning": "#F59E0B",
        "Notice": "#3B82F6"
    }

    fig = px.bar(
        issue_summary,
        x="count",
        y="category",
        color="type",
        orientation="h",
        color_discrete_map=color_discrete_map,
        labels={"count": "Issue Count", "category": "SEO Category", "type": "Severity"}
    )
    fig.update_layout(
        title={'text': "Issues by Category & Severity", 'font': {'color': '#E2E8F0', 'size': 16}},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1"),
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(gridcolor="#334155"),
        yaxis=dict(gridcolor="#334155")
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

    pos = nx.spring_layout(G, k=0.5, iterations=30, seed=42)

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
        line=dict(width=1, color='#64748B'),
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
        node_text.append(f"{node}<br>Connections: {deg}")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[n[:18] + ".." if len(n) > 18 else n for n in G.nodes()],
        textposition="bottom center",
        hovertext=node_text,
        marker=dict(
            showscale=True,
            colorscale='Viridis',
            size=16,
            color=node_adj,
            colorbar=dict(
                thickness=12,
                title=dict(text='Connections', side='top', font=dict(color='#CBD5E1', size=12)),
                tickfont=dict(color='#CBD5E1')
            ),
            line_width=2,
            line_color='#FFFFFF'
        )
    )

    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        title=dict(text='Internal Linking Architecture Graph', font=dict(color='#E2E8F0', size=16)),
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=450
                    ))
    return fig
