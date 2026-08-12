"""大波段反轉系統圖表。"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .external_markets import DISPLAY_NAMES


def score_history_chart(frame, highlight_start: str = "2026-06-01", highlight_end: str = "2026-08-15") -> go.Figure:
    df = frame.dropna(subset=["score"]).tail(180)
    colors = []
    for s in df["score"]:
        if s >= 7:
            colors.append("#c62828")
        elif s >= 5:
            colors.append("#ef6c00")
        elif s >= 3:
            colors.append("#f9a825")
        else:
            colors.append("#2e7d32")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=df["date"], y=df["score"], marker_color=colors, name="轉折分數")
    )
    fig.add_hline(y=3, line_dash="dot", line_color="#f9a825", annotation_text="減碼 20～30%")
    fig.add_hline(y=5, line_dash="dot", line_color="#ef6c00", annotation_text="減碼 50～70%")
    fig.add_hline(y=7, line_dash="dot", line_color="#c62828", annotation_text="大幅減碼／出場")
    fig.add_vrect(
        x0=highlight_start,
        x1=highlight_end,
        fillcolor="rgba(198,40,40,0.08)",
        line_width=0,
        annotation_text="2026/6–8 研究區間",
        annotation_position="top left",
    )
    fig.update_layout(
        title="台指期多單轉折風險分數",
        template="plotly_white",
        height=380,
        yaxis=dict(title="分數", range=[0, 11.5], dtick=1),
        showlegend=False,
    )
    return fig


def trend_ma_chart(frame) -> go.Figure:
    df = frame.tail(160)
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="台指期",
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
        )
    )
    colors = {"ma20": "#1976d2", "ma60": "#7b1fa2", "ma120": "#ef6c00", "ma240": "#5d4037"}
    for col, color in colors.items():
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df["date"], y=df[col], name=col.upper(), line=dict(color=color, width=1.5)))
    fig.update_layout(
        title="趨勢層：台指期 vs 20 / 60 / 120 / 240 日均線",
        template="plotly_white",
        height=520,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.08),
    )
    return fig


def deviation_chart(frame) -> go.Figure:
    df = frame.tail(200)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, subplot_titles=("20MA 乖離 %", "60MA 乖離 %"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["dev20"], name="20MA乖離", line=dict(color="#1976d2")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["dev60"], name="60MA乖離", line=dict(color="#7b1fa2")), row=2, col=1)
    for y, row in ((8, 1), (15, 2)):
        fig.add_hline(y=y, line_dash="dot", line_color="#ef6c00", row=row, col=1)
    fig.update_layout(template="plotly_white", height=520, showlegend=False)
    return fig


def volume_macd_kd_chart(frame) -> go.Figure:
    df = frame.tail(140)
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.40, 0.18, 0.22, 0.20],
        subplot_titles=("台指期 + 成交量背景", "成交量", "MACD 柱狀體", "KD"),
    )
    fig.add_trace(
        go.Candlestick(
            x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="K線", increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
        ),
        row=1, col=1,
    )
    vol_colors = ["#ef5350" if c >= o else "#26a69a" for o, c in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(x=df["date"], y=df["volume"], marker_color=vol_colors, name="成交量"), row=2, col=1)
    if "vol_ma" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["vol_ma"], name="量20MA", line=dict(color="#455a64")), row=2, col=1)

    hist_colors = ["#ef5350" if v >= 0 else "#26a69a" for v in df["macd_hist"]]
    fig.add_trace(go.Bar(x=df["date"], y=df["macd_hist"], marker_color=hist_colors, name="MACD柱"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["macd"], name="MACD", line=dict(color="#3949ab")), row=3, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["macd_signal"], name="Signal", line=dict(color="#f9a825")), row=3, col=1)

    fig.add_trace(go.Scatter(x=df["date"], y=df["k"], name="K", line=dict(color="#1976d2")), row=4, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["d"], name="D", line=dict(color="#ef6c00")), row=4, col=1)
    fig.add_hline(y=80, line_dash="dot", line_color="#bdbdbd", row=4, col=1)
    fig.add_hline(y=20, line_dash="dot", line_color="#bdbdbd", row=4, col=1)

    fig.update_layout(template="plotly_white", height=900, xaxis_rangeslider_visible=False, legend=dict(orientation="h"))
    return fig


def breadth_chart(frame) -> go.Figure:
    df = frame.dropna(subset=["up", "down"]).tail(160)
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
        subplot_titles=("台指期收盤", "上市上漲／下跌家數", "漲跌比（上漲 / (上漲+下跌)）"),
        row_heights=[0.40, 0.35, 0.25],
    )
    fig.add_trace(go.Scatter(x=df["date"], y=df["close"], name="台指期", line=dict(color="#212121")), row=1, col=1)
    fig.add_trace(go.Bar(x=df["date"], y=df["up"], name="上漲", marker_color="#ef5350"), row=2, col=1)
    fig.add_trace(go.Bar(x=df["date"], y=-df["down"], name="下跌", marker_color="#26a69a"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ad_ratio"], name="漲跌比", line=dict(color="#6a1b9a")), row=3, col=1)
    fig.add_hline(y=0.5, line_dash="dot", line_color="#9e9e9e", row=3, col=1)
    fig.add_hline(y=0.4, line_dash="dot", line_color="#c62828", row=3, col=1)
    if "limit_up" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["limit_up"], name="漲停家數", line=dict(color="#ff8a80"), yaxis="y4"),
            row=2, col=1,
        )
    fig.update_layout(template="plotly_white", height=780, barmode="relative", legend=dict(orientation="h"))
    return fig


def external_compare_chart(frame, keys: list[str], title: str) -> go.Figure:
    df = frame.tail(180).copy()
    fig = go.Figure()
    if "close" in df.columns:
        tx = df["close"] / df["close"].dropna().iloc[0] * 100
        fig.add_trace(go.Scatter(x=df["date"], y=tx, name="台指期（再基期=100）", line=dict(color="#212121", width=2.5)))
    for key in keys:
        if key not in df.columns or df[key].dropna().empty:
            continue
        series = df[key]
        base = series.dropna().iloc[0]
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=series / base * 100,
                name=DISPLAY_NAMES.get(key, key),
                line=dict(width=1.8),
            )
        )
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=480,
        yaxis_title="再基期 = 100",
        legend=dict(orientation="h", y=1.08),
    )
    return fig
