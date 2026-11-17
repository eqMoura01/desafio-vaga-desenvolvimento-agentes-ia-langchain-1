from src.agent import StepDecision, ask
from src.config import DEFAULT_DB_PATH
from src.prompts import build_user_prompt


class Scripted:
    def __init__(self, decisions: list[StepDecision]):
        self._decisions = list(decisions)
        self.prompts: list[str] = []

    def decide(self, prompt: str) -> StepDecision:
        self.prompts.append(prompt)
        return self._decisions.pop(0)


def test_prompt_includes_the_sqlite_error_and_the_stop_line():
    prompt = build_user_prompt(
        "Quantos clientes?",
        "Tabela clientes",
        [
            {
                "kind": "query",
                "ok": False,
                "sql": "SELECT estado_errado FROM clientes",
                "purpose": "listar",
                "error": "no such column: estado_errado",
            }
        ],
        must_answer=True,
    )
    assert "estado_errado" in prompt
    assert "action=answer" in prompt
    assert "Tabela clientes" in prompt
    assert "Nenhuma pergunta anterior." in prompt


def test_prompt_carries_the_previous_turn():
    prompt = build_user_prompt(
        "E em junho?",
        "Tabela compras",
        [],
        must_answer=False,
        prior=[
            {
                "question": "Quantos clientes compraram via app em maio?",
                "answer": "Foram 12 clientes em maio de 2025.",
                "sql": "SELECT COUNT(DISTINCT cliente_id) AS clientes FROM compras WHERE canal = 'App'",
            }
        ],
    )
    assert "E em junho?" in prompt
    assert "maio de 2025" in prompt
    assert "canal = 'App'" in prompt
    assert "Memória da conversa" in prompt
    assert "canal = 'App'" in prompt


def test_follow_up_keeps_the_month_filter_from_the_first_query():
    prompt = build_user_prompt(
        "mas você me trouxe que somente 3 compraram via app de sc, como que tem 5 clientes?",
        "Tabela compras",
        [],
        must_answer=False,
        prior=[
            {
                "question": "Liste os 5 estados com maior número de clientes que compraram via app em maio.",
                "answer": "Santa Catarina tem 3.",
                "sql": (
                    "SELECT estado, COUNT(DISTINCT cliente_id) AS clientes FROM compras "
                    "JOIN clientes ON compras.cliente_id = clientes.id "
                    "WHERE canal = 'App' AND strftime('%m', data_compra) = '05' "
                    "GROUP BY estado"
                ),
            }
        ],
    )
    assert "strftime('%m', data_compra) = '05'" in prompt
    assert "Memória da conversa" in prompt
    assert "Recorte obrigatório" not in prompt


def test_agent_fixes_a_bad_column_and_then_answers():
    model = Scripted(
        [
            StepDecision(
                thought="Vou listar os estados.",
                action="query",
                sql="SELECT estado_errado FROM clientes",
                purpose="Listar estados",
            ),
            StepDecision(
                thought="A coluna certa é estado.",
                action="query",
                sql=(
                    "SELECT estado, COUNT(*) AS clientes FROM clientes "
                    "GROUP BY estado ORDER BY clientes DESC LIMIT 3"
                ),
                purpose="Contar clientes por estado",
            ),
            StepDecision(
                thought="São Paulo lidera.",
                action="answer",
                answer="São Paulo tem 18 clientes, à frente dos demais.",
                viz_type="bar",
                viz_x="estado",
                viz_y="clientes",
                viz_title="Clientes por estado",
            ),
        ]
    )
    result = ask("Quais estados têm mais clientes?", database=DEFAULT_DB_PATH, model=model)
    assert "no such column" in model.prompts[1]
    queries = [step for step in result.steps if step["kind"] == "query"]
    assert queries[0]["ok"] is False
    assert queries[1]["ok"] is True
    assert result.rows[0] == {"estado": "São Paulo", "clientes": 18}
    assert result.viz["type"] == "bar"
    assert "18" in result.answer


def test_agent_stops_after_three_bad_queries():
    bad = StepDecision(
        thought="Tento de novo.",
        action="query",
        sql="SELECT coluna_que_nao_existe FROM clientes",
        purpose="Tentativa",
    )
    model = Scripted([bad, bad, bad, bad])
    result = ask("Qualquer coisa", database=DEFAULT_DB_PATH, model=model, error_limit=3)
    queries = [step for step in result.steps if step["kind"] == "query"]
    assert len(queries) == 3
    assert all(not step["ok"] for step in queries)
    assert "falharam" in result.answer
    assert len(model.prompts) == 4


def test_empty_may_2024_is_rechecked_against_the_years_in_the_data():
    model = Scripted(
        [
            StepDecision(
                thought="Filtro maio de 2024.",
                action="query",
                sql=(
                    "SELECT estado, COUNT(DISTINCT cliente_id) AS num_clientes "
                    "FROM compras JOIN clientes ON compras.cliente_id = clientes.id "
                    "WHERE compras.canal = 'App' "
                    "AND strftime('%Y-%m', compras.data_compra) = '2024-05' "
                    "GROUP BY estado ORDER BY num_clientes DESC LIMIT 5"
                ),
                purpose="Listar os 5 estados",
            ),
            StepDecision(
                thought="Não achei nada.",
                action="answer",
                answer="Não há registros para a leitura escolhida.",
                viz_type="none",
            ),
            StepDecision(
                thought="Maio só existe em 2025.",
                action="query",
                sql=(
                    "SELECT c.estado, COUNT(DISTINCT c.id) AS clientes "
                    "FROM clientes c JOIN compras co ON co.cliente_id = c.id "
                    "WHERE co.canal = 'App' AND strftime('%m', co.data_compra) = '05' "
                    "GROUP BY c.estado ORDER BY clientes DESC, c.estado LIMIT 5"
                ),
                purpose="Maio nos anos que existem na base",
            ),
            StepDecision(
                thought="São Paulo lidera em maio de 2025.",
                action="answer",
                answer="Em maio de 2025, São Paulo tem 6 clientes.",
                viz_type="bar",
                viz_x="estado",
                viz_y="clientes",
                viz_title="Clientes por estado em maio",
            ),
        ]
    )
    result = ask(
        "Liste os 5 estados com maior número de clientes que compraram via app em maio.",
        database=DEFAULT_DB_PATH,
        model=model,
    )
    assert "0 linhas" in model.prompts[1]
    assert result.rows[0] == {"estado": "São Paulo", "clientes": 6}
    assert "Não há registros" not in result.answer
