import base64
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
LOGO = Path(__file__).resolve().parent / "assets" / "franq.png"
LOGO_URI = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Outfit:wght@400;500;600&display=swap');

html, body, [class*="css"] {
  font-family: "Outfit", "Segoe UI", sans-serif;
}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background: #f8f9fb;
  color: #1f1f1f;
}
section[data-testid="stSidebar"] {
  background: #ffffff;
  border-right: 1px solid #eceef5;
}
.block-container { padding-top: 1.4rem; max-width: 760px; }
footer, #MainMenu, [data-testid="stDecoration"] { visibility: hidden; }
[data-testid="stHeaderActionElements"] { display: none; }

.brand { width: 232px; height: auto; display: block; margin: 1.4rem auto 0.2rem; }
.side-brand { width: 148px; height: auto; display: block; margin: 0 0 1.1rem 0; }
.stMarkdown p.greet {
  text-align: center;
  font-size: 2.35rem;
  font-weight: 500;
  line-height: 1.15;
  margin: 0.35rem 0 0.45rem 0;
  background: linear-gradient(90deg, #6c7de2 0%, #8b6cff 48%, #4f8df5 100%) !important;
  -webkit-background-clip: text !important;
  background-clip: text !important;
  color: transparent !important;
}
.stMarkdown p.hero-sub {
  text-align: center;
  max-width: 34rem;
  margin: 0 auto 1.25rem;
  color: #5f6368 !important;
  font-size: 1.02rem;
  line-height: 1.45;
}
.banner { color: #b3261e; text-align: center; margin: 0 0 1rem 0; }
.side-kicker { font-size: 0.92rem; font-weight: 500; margin: 0.2rem 0 0.35rem 0; color: #1f1f1f; }

[data-testid="stBottom"],
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {
  background: #f8f9fb !important;
}
[data-testid="stChatInput"] {
  background: #ffffff !important;
  border: 1px solid #e4e6ef !important;
  border-radius: 28px !important;
  box-shadow: none !important;
}
[data-testid="stChatInputTextArea"] {
  background: transparent !important;
  color: #1f1f1f !important;
  border: none !important;
  border-radius: 28px !important;
  box-shadow: none !important;
  font-family: "Outfit", "Segoe UI", sans-serif !important;
}
[data-testid="stChatInputSubmitButton"] {
  background: #6c7de2 !important;
  color: #ffffff !important;
  border-radius: 999px !important;
  box-shadow: none !important;
}
[data-testid="stChatInput"].is-focus,
[data-testid="stChatInput"].is-typing {
  border-color: #6c7de2 !important;
  box-shadow: none !important;
}

.think { text-align: center; padding: 2.2rem 0 1rem; }
.think-mark {
  width: 210px;
  height: auto;
  animation: breathe 1.6s ease-in-out infinite;
}
@keyframes breathe {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(0.975); opacity: 0.45; }
}
.think-line { position: relative; height: 1.7rem; margin: 0.85rem 0 0; }
.think-line span {
  position: absolute;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 1.12rem;
  font-weight: 500;
  opacity: 0;
  background: linear-gradient(90deg, #b7bbcb, #6c7de2, #a78bfa, #b7bbcb);
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: cycle 4.8s infinite, shimmer 1.5s linear infinite;
}
.think-line span:nth-child(2) { animation-delay: 1.6s, 0s; }
.think-line span:nth-child(3) { animation-delay: 3.2s, 0s; }
@keyframes cycle {
  0%, 6% { opacity: 0; }
  12%, 28% { opacity: 1; }
  36%, 100% { opacity: 0; }
}
@keyframes shimmer {
  to { background-position: 100% 0; }
}

.sheet-question {
  font-size: 1.15rem;
  font-weight: 600;
  color: #1f1f1f;
  margin: 0 0 0.45rem 0;
  line-height: 1.4;
}
.turn-rule { border-top: 1px solid #eceef5; margin: 1.4rem 0 1.15rem; height: 0; }
[data-testid="stElementContainer"]:has(.answer-fresh) + [data-testid="stElementContainer"] .stMarkdown {
  opacity: 0;
  animation: reveal-answer 0.01s linear 0.45s forwards;
}
[data-testid="stElementContainer"]:has(.answer-fresh) + [data-testid="stElementContainer"] .stMarkdown.is-typing {
  opacity: 1;
  animation: none;
}
@keyframes reveal-answer {
  to { opacity: 1; }
}
[data-testid="stElementContainer"]:has(.answer-fresh) + [data-testid="stElementContainer"] .stMarkdown.is-typing p:last-of-type::after {
  content: "";
  display: inline-block;
  width: 0.45rem;
  height: 1.02em;
  margin-left: 3px;
  background: #6c7de2;
  vertical-align: text-bottom;
  animation: caret 0.7s steps(1) infinite;
}
[data-testid="stElementContainer"]:has(.answer-fresh) + [data-testid="stElementContainer"] .stMarkdown.is-done p:last-of-type::after {
  display: none;
}
@keyframes caret {
  0%, 45% { opacity: 1; }
  50%, 100% { opacity: 0; }
}
.stMarkdown, .stMarkdown p, .stMarkdown li { color: #1f1f1f; }
.stMarkdown a { color: #4f5ed4; }
[data-testid="stExpander"] details { background: transparent; border: none; }
[data-testid="stExpander"] summary { color: #4f5ed4; font-size: 0.95rem; }

.metric-row { display: flex; gap: 1.4rem; flex-wrap: wrap; margin: 0.2rem 0 0.8rem; }
.figure-value {
  font-size: 3.3rem;
  font-weight: 500;
  line-height: 0.95;
  letter-spacing: -0.03em;
  color: #6c7de2;
}
.figure-label { margin-top: 0.2rem; color: #5f6368; font-size: 0.95rem; }
.trail { color: #5f6368; font-size: 0.85rem; margin: 0.65rem 0 0.1rem; }
.query { margin: 0 0 1rem; }
.query-purpose { margin: 0 0 0.35rem; color: #1f1f1f; }
.query pre {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 0.78rem;
  line-height: 1.45;
  background: #f7f8fc;
  color: #1f1f1f;
  border: 1px solid #eceef5;
  border-radius: 12px;
  padding: 0.7rem 0.8rem;
  white-space: pre-wrap;
  word-break: break-word;
}
.query-meta { color: #5f6368; font-size: 0.8rem; margin: 0.35rem 0 0; }
.query-error { color: #b3261e; font-size: 0.85rem; margin: 0.35rem 0 0; }
.thought { color: #5f6368; margin: 0 0 0.7rem; }

[data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"] {
  background: #ffffff !important;
  color: #1f1f1f !important;
  border: 1px solid #e4e6ef !important;
  border-radius: 18px !important;
  box-shadow: 0 1px 2px rgba(32, 33, 36, 0.05) !important;
  justify-content: flex-start !important;
  text-align: left;
  padding: 0.85rem 1rem !important;
  min-height: 0 !important;
  height: auto !important;
  font-family: "Outfit", "Segoe UI", sans-serif !important;
}
[data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"] div { justify-content: flex-start !important; }
[data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"] p {
  text-align: left !important;
  width: 100%;
  font-size: 0.98rem;
}
[data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"]:hover {
  border-color: #6c7de2 !important;
  background: #f7f8ff !important;
  color: #1f1f1f !important;
}
[data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"]:focus-visible {
  outline: 2px solid #6c7de2;
  outline-offset: 2px;
}
section[data-testid="stSidebar"] .stButton button {
  background: transparent !important;
  color: #4f5ed4 !important;
  border: 1px solid #d9dcf3 !important;
  border-radius: 999px !important;
  margin-top: 0.7rem;
}
section[data-testid="stSidebar"] .stButton button:hover { background: #f4f5ff !important; }
section[data-testid="stSidebar"] .stButton button:focus-visible {
  outline: 2px solid #6c7de2;
  outline-offset: 2px;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] details {
  background: transparent;
  border-bottom: 1px solid #f0f1f6;
}

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
  .think-line span { position: static; opacity: 1; color: #1f1f1f; background: none; }
  .think-line span:nth-child(n+2) { display: none; }
}
@media (max-width: 700px) {
  .greet { font-size: 1.7rem; }
  .brand { width: 180px; }
  .figure-value { font-size: 2.6rem; }
}
</style>
"""

def main() -> None:
    st.set_page_config(page_title="FRANQ", page_icon=str(LOGO), layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    _bind_typing()
    st.session_state.setdefault("history", [])
    path = db_path()
    pending = st.session_state.pop("pending", None)
    typed = st.chat_input("Pergunte sobre a base")
    question = pending or typed
    if question:
        _run(question, path)
    _sidebar(path)
    history = st.session_state["history"]
    typing = st.session_state.pop("type_latest", False)
    if history:
        last = len(history) - 1
        for index, item in enumerate(history):
            _sheet(item, first=index == 0, fresh=typing and index == last)
        return
    _hero()
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        st.markdown(
            '<p class="banner">Falta OPENAI_API_KEY no arquivo .env desta pasta.</p>',
            unsafe_allow_html=True,
        )
    _examples()


def _bind_typing() -> None:
    st.html(
        """
        <script>
        const root = document.documentElement;
        if (!root.dataset.franqBind) {
          root.dataset.franqBind = "1";
          const paint = () => {
            const area = document.querySelector('[data-testid="stChatInputTextArea"]');
            const box = document.querySelector('[data-testid="stChatInput"]');
            if (!area || !box) return;
            box.classList.toggle("is-typing", (area.value || "").trim().length > 0);
            box.classList.toggle("is-focus", document.activeElement === area);
          };
          document.addEventListener("input", paint, true);
          document.addEventListener("focusin", paint, true);
          document.addEventListener("focusout", paint, true);
          setInterval(paint, 350);
        }
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _hero() -> None:
    st.markdown(
        f'<img class="brand" src="{LOGO_URI}" alt="FRANQ" />'
        '<p class="greet">Pergunte sobre a base.</p>'
        '<p class="hero-sub">Clientes, compras, suporte e campanhas. '
        "A resposta traz o número e a consulta que chegou nele.</p>",
        unsafe_allow_html=True,
    )


def _examples() -> None:
    for example in EXAMPLES:
        if st.button(example, width="stretch"):
            st.session_state["pending"] = example
            st.rerun()


def _thinking(question: str) -> str:
    return (
        f'<p class="sheet-question">{html.escape(question)}</p>'
        '<div class="think">'
        f'<img class="think-mark" src="{LOGO_URI}" alt="" />'
        '<p class="think-line">'
        "<span>Lendo a base</span>"
        "<span>Montando a consulta</span>"
        "<span>Conferindo o número</span>"
        "</p></div>"
    )


def _remember(item: dict) -> None:
    st.session_state["type_latest"] = True
    st.session_state["history"].append(item)


def _run(question: str, path: Path) -> None:
    hold = st.empty()
    hold.markdown(_thinking(question), unsafe_allow_html=True)
    try:
        result = ask(question, database=path, history=_prior(st.session_state["history"]))
    except MissingModelConfig as exc:
        hold.empty()
        _remember(_failed(question, str(exc)))
        return
    except DatabaseNotFound as exc:
        hold.empty()
        _remember(_failed(question, str(exc)))
        return
    except Exception as exc:
        hold.empty()
        _remember(_failed(question, f"A consulta não saiu. {exc}"))
        return
    hold.empty()
    _remember(
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


def _sheet(item: dict, first: bool = False, fresh: bool = False) -> None:
    if not first:
        st.markdown('<div class="turn-rule"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="sheet-question">{html.escape(item["question"])}</p>',
        unsafe_allow_html=True,
    )
    if fresh:
        st.markdown('<div class="answer-fresh" data-type-answer="1"></div>', unsafe_allow_html=True)
    st.markdown(item["answer"])
    if fresh:
        _type_answer()
    _visual(item)
    queries = [step for step in item["steps"] if step.get("kind") == "query"]
    if queries or item["rows"]:
        st.markdown(f'<p class="trail">{_caption(queries)}</p>', unsafe_allow_html=True)
        with st.expander("Ver a consulta"):
            if item["steps"]:
                st.markdown(_ribbon(item["steps"]), unsafe_allow_html=True)
            if item["rows"] and item["viz"].get("type") in {"bar", "line"}:
                st.dataframe(_frame(item), width="stretch", hide_index=True)


def _type_answer() -> None:
    st.html(
        """
        <script>
        let tries = 0;
        const start = () => {
          const mark = document.querySelector('[data-type-answer="1"]');
          if (!mark) {
            if (tries < 40) {
              tries += 1;
              setTimeout(start, 50);
            }
            return;
          }
          if (mark.dataset.started) return;
          const box = mark.closest('[data-testid="stLayoutWrapper"], [data-testid="stElementContainer"]');
          let sibling = box && box.nextElementSibling;
          let md = null;
          for (let i = 0; sibling && i < 6; i += 1) {
            const found = sibling.querySelector(".stMarkdown");
            if (found && !found.querySelector('[data-type-answer="1"]')) {
              md = found;
              break;
            }
            sibling = sibling.nextElementSibling;
          }
          if (!md) {
            if (tries < 40) {
              tries += 1;
              setTimeout(start, 50);
            } else {
              mark.classList.remove("answer-fresh");
            }
            return;
          }
          mark.dataset.started = "1";
          const nodes = [];
          const walker = document.createTreeWalker(md, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode())) {
            if (!node.nodeValue) continue;
            nodes.push({ node, full: node.nodeValue });
          }
          const total = nodes.reduce((sum, item) => sum + item.full.length, 0);
          md.classList.add("is-typing");
          if (!total || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            md.classList.add("is-done");
            return;
          }
          nodes.forEach((item) => { item.node.nodeValue = ""; });
          const begun = performance.now();
          const tick = (now) => {
            const due = Math.min(total, Math.floor(((now - begun) / 5000) * total));
            let shown = 0;
            nodes.forEach((item) => {
              const take = Math.max(0, Math.min(item.full.length, due - shown));
              item.node.nodeValue = item.full.slice(0, take);
              shown += item.full.length;
            });
            if (due < total) requestAnimationFrame(tick);
            else md.classList.add("is-done");
          };
          requestAnimationFrame(tick);
        };
        start();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _visual(item: dict) -> None:
    kind = item["viz"].get("type")
    rows = item["rows"]
    if _one_number(item):
        st.markdown(_metrics(item), unsafe_allow_html=True)
        return
    if kind == "metric" and rows:
        st.markdown(_metrics(item), unsafe_allow_html=True)
        return
    if kind in {"bar", "line"}:
        figure = build_figure(item["viz"], item["columns"], rows)
        if figure is not None:
            st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
            return
    if rows and kind == "table":
        st.dataframe(_frame(item), width="stretch", hide_index=True, height="auto")


def _one_number(item: dict) -> bool:
    rows = item["rows"]
    columns = item["columns"]
    if len(rows) != 1 or len(columns) != 1:
        return False
    return _is_number(rows[0].get(columns[0]))


def _metrics(item: dict) -> str:
    row = item["rows"][0]
    numeric = [column for column in item["columns"] if _is_number(row.get(column))]
    if not numeric:
        return ""
    blocks = []
    for column in numeric:
        label = item["viz"].get("title") if len(numeric) == 1 else column
        shown = (label or column or "").replace("_", " ")
        blocks.append(
            '<div class="figure">'
            f'<div class="figure-value">{html.escape(_format_number(row.get(column)))}</div>'
            f'<div class="figure-label">{html.escape(shown)}</div>'
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
    for step in steps:
        if step.get("kind") == "thought":
            if step.get("text"):
                items.append(f'<p class="thought">{html.escape(step["text"])}</p>')
            continue
        purpose = html.escape(step.get("purpose") or "")
        sql = html.escape(step.get("sql") or "")
        if step.get("ok"):
            meta = _linhas(step.get("row_count") or 0)
            if step.get("truncated"):
                meta += " · truncado"
            extra = f'<p class="query-meta">{html.escape(meta)}</p>'
        else:
            extra = f'<p class="query-error">{html.escape(step.get("error") or "erro")}</p>'
        items.append(
            '<div class="query">'
            f'<p class="query-purpose">{purpose}</p>'
            f"<pre>{sql}</pre>{extra}</div>"
        )
    return f'<div class="queries">{"".join(items)}</div>'


def _sidebar(path: Path) -> None:
    with st.sidebar:
        st.markdown(
            f'<img class="side-brand" src="{LOGO_URI}" alt="FRANQ" />',
            unsafe_allow_html=True,
        )
        st.markdown('<p class="side-kicker">Tabelas</p>', unsafe_allow_html=True)
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
