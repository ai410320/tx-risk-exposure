"""Plotly 圖表。"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import DEVIATION_THRESHOLD


def create_dashboard_chart(
    daily,
    monthly,
    deviation_series,
    threshold: float = DEVIATION_THRESHOLD,
    realtime_price: float | None = None,
) -> go.Figure:
    """建立日K、月K與乖離率綜合圖表。"""
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.06,
        row_heights=[0.45, 0.25, 0.30],
        subplot_titles=("台指期近月 日K（含夜盤）", "月K線", "當日最高 vs MA20 乖離率 (%)"),
    )

    # 日K 蠟燭圖（最近 90 天）
    recent_daily = daily.tail(90)
    fig.add_trace(
        go.Candlestick(
            x=recent_daily["date"],
            open=recent_daily["open"],
            high=recent_daily["high"],
            low=recent_daily["low"],
            close=recent_daily["close"],
            name="日K",
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
        ),
        row=1,
        col=1,
    )

    if deviation_series is not None and not deviation_series.empty:
        ma_col = "ma20" if "ma20" in deviation_series.columns else "monthly_close"
        if ma_col in deviation_series.columns:
            recent_ma = deviation_series.tail(90)
            fig.add_trace(
                go.Scatter(
                    x=recent_ma["date"],
                    y=recent_ma[ma_col],
                    mode="lines",
                    name="MA20（月線）",
                    line=dict(color="#ff9800", width=2),
                ),
                row=1,
                col=1,
            )

    # 月K 蠟燭圖（最近 12 個月）
    recent_monthly = monthly.tail(12)
    month_dates = [f"{m}-01" for m in recent_monthly["month"]]
    fig.add_trace(
        go.Candlestick(
            x=month_dates,
            open=recent_monthly["open"],
            high=recent_monthly["high"],
            low=recent_monthly["low"],
            close=recent_monthly["close"],
            name="月K",
            increasing_line_color="#e53935",
            decreasing_line_color="#00897b",
        ),
        row=2,
        col=1,
    )

    # 乖離率折線
    recent_dev = deviation_series.tail(90)
    colors = [
        "#d32f2f" if abs(v) > threshold else "#1976d2"
        for v in recent_dev["deviation_pct"]
    ]
    fig.add_trace(
        go.Scatter(
            x=recent_dev["date"],
            y=recent_dev["deviation_pct"],
            mode="lines+markers",
            name="乖離率",
            line=dict(color="#1976d2", width=2),
            marker=dict(color=colors, size=5),
        ),
        row=3,
        col=1,
    )

    # 門檻線 ±0.8%
    fig.add_hline(y=threshold, line_dash="dot", line_color="#d32f2f", row=3, col=1)
    fig.add_hline(y=-threshold, line_dash="dot", line_color="#d32f2f", row=3, col=1)
    fig.add_hrect(
        y0=threshold,
        y1=recent_dev["deviation_pct"].max() + 0.2 if not recent_dev.empty else threshold + 1,
        fillcolor="rgba(211,47,47,0.1)",
        line_width=0,
        row=3,
        col=1,
    )
    fig.add_hrect(
        y0=recent_dev["deviation_pct"].min() - 0.2 if not recent_dev.empty else -threshold - 1,
        y1=-threshold,
        fillcolor="rgba(211,47,47,0.1)",
        line_width=0,
        row=3,
        col=1,
    )

    fig.update_layout(
        height=900,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False,
        template="plotly_white",
        title=dict(text="台指期 日K / MA20 乖離率監控", x=0.5),
    )
    fig.update_yaxes(title_text="點位", row=1, col=1)
    fig.update_yaxes(title_text="點位", row=2, col=1)
    fig.update_yaxes(title_text="乖離率 %", row=3, col=1)

    return fig
