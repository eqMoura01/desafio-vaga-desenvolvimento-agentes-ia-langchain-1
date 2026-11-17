import re

import pandas as pd
import plotly.express as px

COLORS = ["#1F6F6A", "#C4622D", "#3D4C6B", "#8C4A3A", "#6E8B3D", "#8A6A2F"]
_PERIOD = re.compile(r"\d{4}-\d{2}(-\d{2})?$")


def coerce_viz(viz: dict | None, columns: list[str], rows: list[dict]) -> dict:
    spec = dict(viz or {})
    kind = (spec.get("type") or "none").lower()
    if kind not in {"table", "bar", "line", "metric", "none"}:
        kind = "table"
    if not rows:
        return {**spec, "type": "none"}
    if kind == "none":
        return {**spec, "type": "table"}
    if kind == "metric" and len(rows) > 1:
        kind = "bar" if _has_axes(spec, columns, rows) else "table"
    if kind in {"bar", "line"}:
        if not _has_axes(spec, columns, rows):
            kind = "table"
        elif spec.get("series") not in columns:
            spec["series"] = None
    return {**spec, "type": kind}


def build_figure(viz: dict, columns: list[str], rows: list[dict]):
    if viz.get("type") not in {"bar", "line"} or not rows:
        return None
    frame = pd.DataFrame(rows, columns=columns)
    x, y = viz["x"], viz["y"]
    if viz["type"] == "line":
        frame[x] = _as_dates(frame[x])
        fig = px.line(frame, x=x, y=y, color=viz.get("series"), markers=True, color_discrete_sequence=COLORS)
    else:
        fig = px.bar(frame, x=x, y=y, color=viz.get("series"), barmode="group", color_discrete_sequence=COLORS)
    title = viz.get("title") or ""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Atkinson Hyperlegible, Segoe UI, sans-serif", "color": "#E7E1D5", "size": 13},
        title={"text": title, "font": {"family": "Schibsted Grotesk, Segoe UI, sans-serif", "size": 18, "color": "#F4F0E6"}},
        margin={"l": 8, "r": 8, "t": 48 if title else 16, "b": 8},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        colorway=COLORS,
    )
    fig.update_xaxes(showgrid=False, title=None)
    fig.update_yaxes(gridcolor="#2A4650", title=None)
    return fig


def _has_axes(spec: dict, columns: list[str], rows: list[dict]) -> bool:
    x, y = spec.get("x"), spec.get("y")
    if x not in columns or y not in columns:
        return False
    return all(_is_number(row.get(y)) for row in rows)


def _is_number(value) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def _as_dates(series: pd.Series) -> pd.Series:
    as_text = series.astype(str)
    if as_text.map(lambda item: bool(_PERIOD.fullmatch(item))).all():
        return pd.to_datetime(as_text)
    return series
