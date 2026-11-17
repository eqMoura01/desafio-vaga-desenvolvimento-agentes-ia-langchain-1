from src.agent import StepDecision, ask
from src.config import DEFAULT_DB_PATH
from src.prompts import build_user_prompt
from tests.test_agent import Scripted

PRIOR = [
    {
        "question": "Liste os 5 estados com maior número de clientes que compraram via app em maio.",
        "answer": "Santa Catarina tem 3.",
        "sql": (
            "SELECT estado, COUNT(DISTINCT cliente_id) AS clientes FROM compras "
            "JOIN clientes ON compras.cliente_id = clientes.id "
            "WHERE compras.canal = 'App' AND strftime('%m', compras.data_compra) = '05' "
            "GROUP BY estado"
        ),
        "columns": ["estado", "clientes"],
        "rows": [{"estado": "São Paulo", "clientes": 6}, {"estado": "Santa Catarina", "clientes": 3}],
        "row_count": 5,
    }
]


def test_follow_up_sees_the_whole_previous_turn():
    prompt = build_user_prompt(
        "quais são esses de sc?",
        "Tabela compras",
        [],
        must_answer=False,
        prior=PRIOR,
    )
    assert "quais são esses de sc?" in prompt
    assert "Liste os 5 estados" in prompt
    assert "Santa Catarina tem 3." in prompt
    assert "strftime('%m', compras.data_compra) = '05'" in prompt
    assert "São Paulo" in prompt
    assert "Memória da conversa" in prompt
    assert "Recorte obrigatório" not in prompt
    assert "A SQL tem de filtrar" not in prompt
    assert "mês 05" in prompt
    assert "canal = 'App'" in prompt


def test_a_new_question_can_leave_may_and_app():
    sql = (
        "SELECT CASE WHEN canal = 'App' THEN 'App' ELSE 'Outro' END AS lado, "
        "COUNT(DISTINCT cliente_id) AS clientes FROM compras "
        "WHERE strftime('%m', data_compra) = '04' GROUP BY lado"
    )
    model = Scripted(
        [
            StepDecision(thought="Comparo abril.", action="query", sql=sql, purpose="Abril"),
            StepDecision(
                thought="Pronto.",
                action="answer",
                answer="Em abril, o app e os outros canais estão na tabela.",
                viz_type="bar",
                viz_x="lado",
                viz_y="clientes",
                viz_title="Abril",
            ),
        ]
    )
    result = ask(
        "e em abril, quantos foram do app e quantos não foram?",
        database=DEFAULT_DB_PATH,
        model=model,
        history=PRIOR,
    )
    assert "A SQL tem de filtrar" not in model.prompts[0]
    assert "Liste os 5 estados" in model.prompts[0]
    query = next(step for step in result.steps if step.get("kind") == "query")
    assert query["ok"] is True
    assert query["row_count"] > 0
    assert "04" in query["sql"]
    assert "= '05'" not in query["sql"]


WHATSAPP = [
    {
        "question": "Quantos clientes interagiram com campanhas de WhatsApp em 2024?",
        "answer": "Em 2024, 17 clientes interagiram com campanhas de WhatsApp.",
        "sql": (
            "SELECT COUNT(DISTINCT cliente_id) AS n FROM campanhas_marketing "
            "WHERE canal = 'WhatsApp' AND interagiu = 1 "
            "AND strftime('%Y', data_envio) = '2024'"
        ),
    }
]


def test_desses_de_sc_keeps_the_2024_whatsapp_slice():
    from src.follow import follow_gap

    question = "tem algum desses que é de sc?"
    dropped = (
        "SELECT DISTINCT nome FROM clientes WHERE estado = 'Santa Catarina' "
        "AND id IN (SELECT cliente_id FROM campanhas_marketing "
        "WHERE interagiu = 1 AND canal = 'WhatsApp')"
    )
    assert "2024" in (follow_gap(dropped, question, WHATSAPP) or "")
    kept = (
        "SELECT DISTINCT nome FROM clientes WHERE estado = 'Santa Catarina' "
        "AND id IN (SELECT cliente_id FROM campanhas_marketing "
        "WHERE interagiu = 1 AND canal = 'WhatsApp' "
        "AND strftime('%Y', data_envio) = '2024')"
    )
    assert follow_gap(kept, question, WHATSAPP) is None


def test_agent_rewrites_a_follow_up_that_drops_2024():
    bad = (
        "SELECT DISTINCT clientes.nome AS nome FROM clientes "
        "WHERE estado = 'Santa Catarina' AND id IN ("
        "SELECT cliente_id FROM campanhas_marketing "
        "WHERE interagiu = 1 AND canal = 'WhatsApp')"
    )
    good = (
        "SELECT DISTINCT clientes.nome AS nome FROM clientes "
        "WHERE estado = 'Santa Catarina' AND id IN ("
        "SELECT cliente_id FROM campanhas_marketing "
        "WHERE interagiu = 1 AND canal = 'WhatsApp' "
        "AND strftime('%Y', data_envio) = '2024')"
    )
    model = Scripted(
        [
            StepDecision(thought="Olho SC.", action="query", sql=bad, purpose="SC"),
            StepDecision(thought="Mantenho 2024.", action="query", sql=good, purpose="SC em 2024"),
            StepDecision(
                thought="São dois.",
                action="answer",
                answer="Henrique Sousa e Ísis Sampaio.",
                viz_type="table",
                viz_x="nome",
            ),
        ]
    )
    result = ask(
        "tem algum desses que é de sc?",
        database=DEFAULT_DB_PATH,
        model=model,
        history=WHATSAPP,
    )
    failed = [step for step in result.steps if step.get("kind") == "query" and not step.get("ok")]
    assert failed
    assert "2024" in (failed[0].get("error") or "")
    names = {row["nome"] for row in result.rows}
    assert names == {"Henrique Sousa", "Ísis Sampaio"}


def test_em_2024_filters_the_purchase_date_too():
    from src.follow import follow_gap

    prior = [
        *WHATSAPP,
        {
            "question": "tem algum desses que é de sc?",
            "answer": "Henrique Sousa e Ísis Sampaio.",
            "sql": (
                "SELECT DISTINCT nome FROM clientes WHERE estado = 'Santa Catarina' "
                "AND id IN (SELECT cliente_id FROM campanhas_marketing "
                "WHERE interagiu = 1 AND canal = 'WhatsApp' "
                "AND strftime('%Y', data_envio) = '2024')"
            ),
        },
        {
            "question": "e quais desses compraram pelo app?",
            "answer": "Henrique Sousa e Ísis Sampaio.",
            "sql": (
                "SELECT DISTINCT c.nome FROM clientes c "
                "JOIN compras co ON c.id = co.cliente_id "
                "WHERE c.estado = 'Santa Catarina' AND co.canal = 'App' "
                "AND c.id IN (SELECT cliente_id FROM campanhas_marketing "
                "WHERE interagiu = 1 AND canal = 'WhatsApp' "
                "AND strftime('%Y', data_envio) = '2024')"
            ),
        },
    ]
    loose = (
        "SELECT COUNT(DISTINCT c.id) AS n FROM clientes c "
        "JOIN compras co ON c.id = co.cliente_id "
        "WHERE c.estado = 'Santa Catarina' AND co.canal = 'App' "
        "AND c.id IN (SELECT cliente_id FROM campanhas_marketing "
        "WHERE interagiu = 1 AND canal = 'WhatsApp' "
        "AND strftime('%Y', data_envio) = '2024')"
    )
    assert "data_compra" in (follow_gap(loose, "em 2024?", prior) or "")
    dated = loose.replace(
        "AND co.canal = 'App'",
        "AND co.canal = 'App' AND strftime('%Y', co.data_compra) = '2024'",
    )
    assert follow_gap(dated, "em 2024?", prior) is None
