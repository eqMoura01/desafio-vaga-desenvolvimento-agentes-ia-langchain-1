from src.database import connect, run_select
from src.config import DEFAULT_DB_PATH


def _rows(sql: str):
    with connect(DEFAULT_DB_PATH) as conn:
        return run_select(conn, sql).rows


def test_reference_top_states_app_may():
    rows = _rows(
        """
        SELECT c.estado, COUNT(DISTINCT c.id) AS clientes
        FROM clientes c
        JOIN compras co ON co.cliente_id = c.id
        WHERE co.canal = 'App' AND strftime('%m', co.data_compra) = '05'
        GROUP BY c.estado
        ORDER BY clientes DESC, c.estado
        LIMIT 5
        """
    )
    assert [(row["estado"], row["clientes"]) for row in rows] == [
        ("São Paulo", 6),
        ("Minas Gerais", 3),
        ("Santa Catarina", 3),
        ("Alagoas", 2),
        ("Espírito Santo", 2),
    ]


def test_reference_whatsapp_2024():
    rows = _rows(
        """
        SELECT COUNT(DISTINCT cliente_id) AS clientes
        FROM campanhas_marketing
        WHERE canal = 'WhatsApp' AND interagiu = 1
          AND data_envio >= '2024-01-01' AND data_envio < '2025-01-01'
        """
    )
    assert rows == [{"clientes": 17}]


def test_reference_avg_purchases_by_category():
    rows = _rows(
        """
        SELECT categoria, ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT cliente_id), 4) AS media
        FROM compras
        GROUP BY categoria
        ORDER BY media DESC, categoria
        """
    )
    assert [row["categoria"] for row in rows] == [
        "Roupas",
        "Viagens",
        "Livros",
        "Serviços",
        "Eletrônicos",
        "Alimentos",
    ]
    assert rows[0]["media"] == pytest_approx(2.2113)


def test_reference_open_complaints_by_channel():
    rows = _rows(
        """
        SELECT canal, COUNT(*) AS reclamacoes
        FROM suporte
        WHERE tipo_contato = 'Reclamação' AND resolvido = 0
        GROUP BY canal
        ORDER BY reclamacoes DESC, canal
        """
    )
    assert [(row["canal"], row["reclamacoes"]) for row in rows] == [
        ("Telefone", 19),
        ("Chat", 18),
        ("E-mail", 14),
    ]


def test_reference_complaint_trend_covers_the_whole_history():
    rows = _rows(
        """
        SELECT strftime('%Y-%m', data_contato) AS mes, canal, COUNT(*) AS reclamacoes
        FROM suporte
        WHERE tipo_contato = 'Reclamação'
          AND data_contato >= date((SELECT MAX(data_contato) FROM suporte), '-1 year')
        GROUP BY mes, canal
        ORDER BY mes, canal
        """
    )
    assert rows[0]["mes"] == "2024-07"
    assert rows[-1]["mes"] == "2025-07"
    assert sum(row["reclamacoes"] for row in rows) == 97


def pytest_approx(value: float):
    from pytest import approx

    return approx(value, abs=1e-4)
