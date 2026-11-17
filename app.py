import html
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.agent import ask
from src.config import db_path, model_name
from src.database import inspect_database
from src.errors import DatabaseNotFound, MissingModelConfig
from src.viz import build_figure

EXAMPLES = [
    "Liste os 5 estados com maior número de clientes que compraram via app em maio.",
    "Quantos clientes interagiram com campanhas de WhatsApp em 2024?",
    "Quais categorias de produto tiveram o maior número de compras em média por cliente?",
    "Qual o número de reclamações não resolvidas por canal?",
    "Qual a tendência de reclamações por canal no último ano?",
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&family=Schibsted+Grotesk:wght@500;600;700&display=swap');

html, body, [class*="css"] {
  font-family: "Atkinson Hyperlegible", "Segoe UI", sans-serif;
}
.stApp { background: #14303a; color: #e7e1d5; }
header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] {
  background: #0e242c;
  border-right: 1px solid #1e3a44;
}
.block-container { padding-top: 2.2rem; max-width: 920px; }
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }

.hero-kicker, .side-kicker, .sheet-label, .ribbon-index {
  font-family: "Schibsted Grotesk", "Segoe UI", sans-serif;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-size: 0.72rem;
}
.hero-kicker { color: #e0b08a; margin: 0 0 0.35rem 0; }
.hero-title {
  font-family: "Schibsted Grotesk", "Segoe UI", sans-serif;
  font-weight: 700;
  font-size: 3.5rem;
  line-height: 0.9;
  letter-spacing: -0.045em;
  margin: 0;
  color: #f4f0e6;
}
.hero-sub { max-width: 38rem; color: #c9d4d6; font-size: 1.05rem; margin: 0.85rem 0 1rem 0; }
.banner {
  border: 1px solid #c4622d;
  color: #f4f0e6;
  padding: 0.75rem 0.9rem;
  margin: 0 0 1rem 0;
}
.side-kicker { color: #e0b08a; margin: 0 0 0.4rem 0; }

[data-testid="stHeaderActionElements"] { display: none; }
[data-testid="stBottom"], [data-testid="stBottomBlockContainer"] { background: #14303a; }
[data-testid="stChatInputTextArea"] {
  background: #0e242c !important;
  color: #f4f0e6 !important;
  border: 1px solid #3d5c66 !important;
  border-radius: 2px !important;
}
[data-testid="stExpander"] summary { color: #e0b08a; }
.sheet-label { color: #c4622d; margin: 0; }
.sheet-question {
  font-family: "Schibsted Grotesk", "Segoe UI", sans-serif;
  font-size: 1.35rem;
  font-weight: 600;
  color: #f4f0e6;
  margin: 0.15rem 0 0.75rem 0;
  letter-spacing: -0.02em;
}
[data-testid="stLayoutWrapper"]:has(.sheet-label) {
  border-radius: 2px;
}
.metric-row { display: flex; gap: 1.6rem; flex-wrap: wrap; margin: 0.2rem 0 0.8rem 0; }
.metric-value {
  font-family: "Schibsted Grotesk", "Segoe UI", sans-serif;
  font-size: 2.7rem;
  letter-spacing: -0.04em;
  line-height: 1;
  color: #f4f0e6;
}
.metric-label { color: #e0b08a; font-size: 0.85rem; margin-top: 0.25rem; }
.trail { color: #c9d4d6; font-size: 0.85rem; margin: 0.6rem 0 0.2rem 0; }

.ribbon { border-left: 2px solid #c4622d; margin: 0.3rem 0 0.2rem 0.15rem; padding-left: 0.9rem; }
.ribbon-item { margin: 0 0 1rem 0; }
.ribbon-index { color: #c4622d; font-family: "IBM Plex Mono", monospace; letter-spacing: 0.08em; }
.ribbon-purpose { margin: 0.15rem 0; color: #f4f0e6; }
.ribbon pre {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.78rem;
  background: #ebe4d6;
  color: #1a2428;
  padding: 0.6rem 0.7rem;
  white-space: pre-wrap;
  word-break: break-word;
}
.ribbon-meta { color: #c9d4d6; font-size: 0.8rem; margin: 0.3rem 0 0 0; }
.ribbon-error { color: #f3b7ad; font-size: 0.85rem; margin: 0.3rem 0 0 0; }
.thought { color: #c9d4d6; font-style: italic; margin: 0 0 0.35rem 0; }

div[data-testid="stExpander"] details { background: transparent; }
.stButton button {
  background: transparent;
  color: #f4f0e6;
  border: 1px solid #3d5c66;
  border-radius: 0;
  justify-content: flex-start;
  text-align: left;
  font-family: "Atkinson Hyperlegible", "Segoe UI", sans-serif;
}
.stButton button div { justify-content: flex-start !important; }
.stButton button p { text-align: left !important; width: 100%; }
.stButton button:hover { border-color: #e0b08a; color: #e0b08a; }
.stButton button:focus { outline: 2px solid #e0b08a; outline-offset: 2px; }
.stButton button p { font-size: 0.95rem; }

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
@media (max-width: 700px) {
  .hero-title { font-size: 2.5rem; }
}
</style>
"""


def main() -> None:
    st.set_page_config(page_title="Mesa", page_icon="▣", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("history", [])
    path = db_path()
    pending = st.session_state.pop("pending", None)
    typed = st.chat_input("Pergunte sobre clientes, compras, suporte ou campanhas")
    question = pending or typed
    if question:
        _run(question, path)
    _sidebar(path)
    history = st.session_state["history"]
    if history:
        for item in history:
            _sheet(item)
        return
    _hero()
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        st.markdown(
            '<p class="banner">Para consultar, grave OPENAI_API_KEY no arquivo .env desta pasta.</p>',
            unsafe_allow_html=True,
        )
    _examples()


def _hero() -> None:
    st.markdown('<p class="hero-kicker">Operação comercial</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title">Mesa</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-sub">Pergunte sobre clientes, compras, suporte e campanhas. '
        "A resposta traz o número e a consulta que chegou nele.</p>",
        unsafe_allow_html=True,
    )


def _examples() -> None:
    for example in EXAMPLES:
        if st.button(example, use_container_width=True):
            st.session_state["pending"] = example
            st.rerun()


def _run(question: str, path: Path) -> None:
    with st.spinner("Consultando o banco"):
        try:
            result = ask(question, database=path, history=_prior(st.session_state["history"]))
        except MissingModelConfig as exc:
            st.session_state["history"].append(_failed(question, str(exc)))
            return
        except DatabaseNotFound as exc:
            st.session_state["history"].append(_failed(question, str(exc)))
            return
        except Exception as exc:
            st.session_state["history"].append(
                _failed(question, f"A consulta não saiu. {exc}")
            )
            return
    st.session_state["history"].append(
        {
            "question": result.question,
            "answer": result.answer,
            "steps": result.steps,
            "columns": result.columns,
            "rows": result.rows,
            "viz": result.viz,
            "standing": result.standing,
        }
    )


def _prior(history: list[dict]) -> list[dict]:
    turns = []
    for item in history:
        sqls = [
            step["sql"]
            for step in item.get("steps") or []
            if step.get("kind") == "query" and step.get("ok") and step.get("sql")
        ]
        last = next(
            (
                step
                for step in reversed(item.get("steps") or [])
                if step.get("kind") == "query" and step.get("ok")
            ),
            None,
        )
        turns.append(
            {
                "question": item.get("question", ""),
                "answer": item.get("answer", ""),
                "sql": sqls[-1] if sqls else "",
                "sqls": sqls,
                "columns": (last or {}).get("columns") or item.get("columns") or [],
                "rows": ((last or {}).get("rows") or item.get("rows") or [])[:8],
                "row_count": (last or {}).get("row_count", len(item.get("rows") or [])),
            }
        )
    return turns


def _failed(question: str, message: str) -> dict:
    return {
        "question": question,
        "answer": message,
        "steps": [],
        "columns": [],
        "rows": [],
        "viz": {"type": "none"},
        "standing": {},
    }


def _sheet(item: dict) -> None:
    with st.container(border=True):
        st.markdown('<p class="sheet-label">Pergunta</p>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="sheet-question">{html.escape(item["question"])}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(item["answer"])
        _visual(item)
        queries = [step for step in item["steps"] if step.get("kind") == "query"]
        if queries or item["rows"]:
            st.markdown(f'<p class="trail">{_caption(queries)}</p>', unsafe_allow_html=True)
            with st.expander("Como cheguei nessa resposta"):
                if item["steps"]:
                    st.markdown(_ribbon(item["steps"]), unsafe_allow_html=True)
                if item["rows"] and item["viz"].get("type") in {"bar", "line"}:
                    st.dataframe(_frame(item), use_container_width=True, hide_index=True)


def _visual(item: dict) -> None:
    kind = item["viz"].get("type")
    if kind == "metric" and item["rows"]:
        st.markdown(_metrics(item), unsafe_allow_html=True)
        return
    if kind in {"bar", "line"}:
        figure = build_figure(item["viz"], item["columns"], item["rows"])
        if figure is not None:
            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
            return
    if item["rows"] and kind == "table":
        st.dataframe(_frame(item), use_container_width=True, hide_index=True, height=320)


def _metrics(item: dict) -> str:
    row = item["rows"][0]
    numeric = [column for column in item["columns"] if _is_number(row.get(column))]
    if not numeric:
        return ""
    blocks = []
    for column in numeric:
        label = item["viz"].get("title") if len(numeric) == 1 else column
        blocks.append(
            "<div>"
            f'<div class="metric-value">{html.escape(_format_number(row.get(column)))}</div>'
            f'<div class="metric-label">{html.escape(label or column)}</div>'
            "</div>"
        )
    return f'<div class="metric-row">{"".join(blocks)}</div>'


def _frame(item: dict) -> pd.DataFrame:
    return pd.DataFrame(item["rows"], columns=item["columns"])


def _caption(queries: list[dict]) -> str:
    if not queries:
        return "Sem consulta ao banco"
    failed = sum(1 for step in queries if not step.get("ok"))
    noun = "consulta" if len(queries) == 1 else "consultas"
    text = f"{len(queries)} {noun}"
    if failed:
        text += f" · {failed} com erro"
    return text


def _ribbon(steps: list[dict]) -> str:
    items: list[str] = []
    index = 0
    for step in steps:
        if step.get("kind") == "thought":
            if step.get("text"):
                items.append(f'<p class="thought">{html.escape(step["text"])}</p>')
            continue
        index += 1
        purpose = html.escape(step.get("purpose") or "")
        sql = html.escape(step.get("sql") or "")
        if step.get("ok"):
            meta = _linhas(step.get("row_count") or 0)
            if step.get("truncated"):
                meta += " · truncado"
            extra = f'<p class="ribbon-meta">{html.escape(meta)}</p>'
        else:
            extra = f'<p class="ribbon-error">{html.escape(step.get("error") or "erro")}</p>'
        items.append(
            '<div class="ribbon-item">'
            f'<span class="ribbon-index">{index:02d}</span>'
            f'<p class="ribbon-purpose">{purpose}</p>'
            f"<pre>{sql}</pre>{extra}</div>"
        )
    return f'<div class="ribbon">{"".join(items)}</div>'


def _sidebar(path: Path) -> None:
    with st.sidebar:
        st.markdown('<p class="side-kicker">Banco</p>', unsafe_allow_html=True)
        try:
            tables, _ = cached_schema(str(path), path.stat().st_mtime_ns if path.exists() else 0)
        except DatabaseNotFound as exc:
            st.write(str(exc))
            tables = []
        for table in tables:
            with st.expander(f"{table['name']} · {table['rows']}", expanded=False):
                for column in table["columns"]:
                    st.markdown(f"`{column['name']}` {column['type']}")
        if st.session_state["history"] and st.button("Limpar conversa"):
            st.session_state["history"] = []
            st.rerun()
        st.caption(f"Modelo {model_name()}")
        st.caption(path.name)


@st.cache_data(show_spinner=False)
def cached_schema(path_str: str, _mtime_ns: int):
    return inspect_database(path_str)


def _linhas(count: int) -> str:
    return "1 linha" if count == 1 else f"{count} linhas"


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _format_number(value) -> str:
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    if isinstance(value, float):
        text = f"{value:,.2f}"
        return text.replace(",", "X").replace(".", ",").replace("X", ".")
    return "" if value is None else str(value)


main()
