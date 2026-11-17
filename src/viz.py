import re

import pandas as pd
import plotly.express as px

COLORS = ["#6c7de2", "#3d4fbf", "#8b7cff", "#5aa0e6", "#2f3d8f", "#c07cff"]
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
        font={"family": "Outfit, Segoe UI, sans-serif", "color": "#1f1f1f", "size": 13},
        title={"text": title, "font": {"family": "Outfit, Segoe UI, sans-serif", "size": 16, "color": "#1f1f1f"}},
        margin={"l": 8, "r": 8, "t": 48 if title else 16, "b": 8},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        colorway=COLORS,
    )
    fig.update_xaxes(showgrid=False, title=None, linecolor="#e6e8f0")
    fig.update_yaxes(gridcolor="#eef0f6", title=None)
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
