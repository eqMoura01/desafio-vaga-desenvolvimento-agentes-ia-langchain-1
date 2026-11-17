import os
import sqlite3
from dataclasses import dataclass, field
from typing import Protocol

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from src.config import db_path, max_queries, model_name
from src.database import connect, inspect_database, run_select
from src.errors import MissingModelConfig, SqlRejected
from src.follow import follow_gap
from src.prompts import SYSTEM_PROMPT, build_user_prompt, latest_query_is_empty
from src.sql_guard import clean_sql
from src.viz import coerce_viz


class StepDecision(BaseModel):
    thought: str = ""
    action: str = Field(description="query ou answer")
    sql: str | None = None
    purpose: str | None = None
    answer: str | None = None
    viz_type: str = "none"
    viz_x: str | None = None
    viz_y: str | None = None
    viz_series: str | None = None
    viz_title: str | None = None


class DecisionModel(Protocol):
    def decide(self, prompt: str) -> StepDecision: ...


@dataclass
class Answer:
    question: str
    answer: str
    steps: list[dict] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    viz: dict = field(default_factory=dict)
    standing: dict = field(default_factory=dict)


class LangchainDecisionModel:
    def __init__(self, llm: ChatOpenAI):
        self._structured = llm.with_structured_output(StepDecision, method="function_calling")

    def decide(self, prompt: str) -> StepDecision:
        from langchain_core.messages import HumanMessage, SystemMessage

        result = self._structured.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        if isinstance(result, StepDecision):
            return result
        return StepDecision.model_validate(result)


def build_model() -> LangchainDecisionModel:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise MissingModelConfig()
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    llm = ChatOpenAI(
        model=model_name(),
        api_key=key,
        base_url=base_url,
        temperature=0,
    )
    return LangchainDecisionModel(llm)


def ask(
    question: str,
    database: str | None = None,
    model: DecisionModel | None = None,
    query_limit: int | None = None,
    error_limit: int = 3,
    history: list[dict] | None = None,
) -> Answer:
    text = (question or "").strip()
    if not text:
        raise ValueError("Pergunta vazia.")
    path = database or db_path()
    _, schema_text = inspect_database(path)
    prior = list(history or [])
    runner = model or build_model()
    graph = _compile(runner, path, query_limit or max_queries(), error_limit)
    final = graph.invoke(
        {
            "question": text,
            "schema_text": schema_text,
            "prior": prior,
            "steps": [],
            "consecutive_errors": 0,
            "query_count": 0,
            "answer": None,
            "viz": _empty_viz(),
            "needs_force": False,
            "empty_recheck": False,
            "recheck_pending": False,
        },
        config={"recursion_limit": 40},
    )
    last = last_success(final["steps"])
    columns = last["columns"] if last else []
    rows = last["rows"] if last else []
    return Answer(
        question=text,
        answer=final["answer"],
        steps=final["steps"],
        columns=columns,
        rows=rows,
        viz=coerce_viz(final.get("viz"), columns, rows),
    )


def last_success(steps: list[dict]) -> dict | None:
    for step in reversed(steps):
        if step.get("kind") == "query" and step.get("ok"):
            return step
    return None


def _compile(model: DecisionModel, path, query_limit: int, error_limit: int):
    def decide(state: dict) -> dict:
        state = {**state, "recheck_pending": False}
        must_answer = (
            state["consecutive_errors"] >= error_limit or state["query_count"] >= query_limit
        )
        prompt = build_user_prompt(
            state["question"],
            state["schema_text"],
            state["steps"],
            must_answer,
            state.get("prior"),
        )
        decision = _as_decision(model.decide(prompt))
        steps = [*state["steps"], _thought(decision.thought)]
        if decision.action.strip().lower() == "answer":
            if (
                not must_answer
                and not state.get("empty_recheck")
                and latest_query_is_empty(steps)
            ):
                return {
                    **state,
                    "steps": [
                        *steps,
                        _thought(
                            "Zero linhas não fecham a conta. Vou conferir o intervalo antes de responder."
                        ),
                    ],
                    "answer": None,
                    "needs_force": False,
                    "empty_recheck": True,
                    "recheck_pending": True,
                }
            prose = (decision.answer or "").strip()
            if not prose:
                prose = (
                    "A última consulta válida está na tabela."
                    if last_success(steps)
                    else "Não há dados para responder."
                )
            return {
                **state,
                "steps": steps,
                "answer": prose,
                "viz": _viz_from(decision),
                "needs_force": False,
            }
        if must_answer:
            return {**state, "steps": steps, "needs_force": True}
        return {
            **state,
            "steps": steps,
            "needs_force": False,
            "answer": None,
            "pending_sql": clean_sql(decision.sql or ""),
            "pending_purpose": (decision.purpose or "").strip() or "Consulta para responder a pergunta",
        }

    def execute(state: dict) -> dict:
        sql = state.get("pending_sql") or ""
        purpose = state.get("pending_purpose") or "Consulta para responder a pergunta"
        try:
            gap = follow_gap(sql, state.get("question") or "", state.get("prior") or [])
            if gap:
                raise SqlRejected(gap)
            with connect(path) as conn:
                result = run_select(conn, sql)
            step = {
                "kind": "query",
                "text": purpose,
                "sql": sql,
                "purpose": purpose,
                "ok": True,
                "error": None,
                "row_count": len(result.rows),
                "truncated": result.truncated,
                "columns": result.columns,
                "rows": result.rows,
            }
            errors = 0
        except (SqlRejected, sqlite3.Error) as exc:
            step = {
                "kind": "query",
                "text": purpose,
                "sql": sql,
                "purpose": purpose,
                "ok": False,
                "error": str(exc),
                "row_count": 0,
                "truncated": False,
                "columns": [],
                "rows": [],
            }
            errors = state["consecutive_errors"] + 1
        return {
            **state,
            "steps": [*state["steps"], step],
            "query_count": state["query_count"] + 1,
            "consecutive_errors": errors,
        }

    def force(state: dict) -> dict:
        found = last_success(state["steps"])
        if found:
            answer = "O limite de tentativas acabou. A tabela mostra a última consulta que o banco aceitou."
            viz = {**_empty_viz(), "type": "table"}
        else:
            answer = "As consultas falharam. A trilha abaixo mostra o erro devolvido pelo banco."
            viz = _empty_viz()
        steps = [*state["steps"], _thought("Encerrei porque as tentativas acabaram.")]
        return {**state, "steps": steps, "answer": answer, "viz": viz, "needs_force": False}

    def route(state: dict) -> str:
        if state.get("answer"):
            return "end"
        if state.get("needs_force"):
            return "force"
        if state.get("recheck_pending"):
            return "decide"
        return "execute"

    graph = StateGraph(dict)
    graph.add_node("decide", decide)
    graph.add_node("execute", execute)
    graph.add_node("force", force)
    graph.set_entry_point("decide")
    graph.add_conditional_edges(
        "decide",
        route,
        {"execute": "execute", "force": "force", "end": END, "decide": "decide"},
    )
    graph.add_edge("execute", "decide")
    graph.add_edge("force", END)
    return graph.compile()


def _as_decision(value) -> StepDecision:
    if isinstance(value, StepDecision):
        return value
    return StepDecision.model_validate(value)


def _thought(text: str) -> dict:
    return {"kind": "thought", "text": (text or "").strip()}


def _viz_from(decision: StepDecision) -> dict:
    kind = (decision.viz_type or "none").strip().lower()
    if kind not in {"table", "bar", "line", "metric", "none"}:
        kind = "table"
    return {
        "type": kind,
        "x": decision.viz_x,
        "y": decision.viz_y,
        "series": decision.viz_series,
        "title": decision.viz_title,
    }


def _empty_viz() -> dict:
    return {"type": "none", "x": None, "y": None, "series": None, "title": None}
