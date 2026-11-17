from src.viz import build_figure, coerce_viz


def test_missing_axis_falls_back_to_table():
    spec = coerce_viz(
        {"type": "bar", "x": "nao_existe", "y": "clientes"},
        ["estado", "clientes"],
        [{"estado": "São Paulo", "clientes": 18}],
    )
    assert spec["type"] == "table"


def test_line_figure_uses_the_requested_title():
    rows = [
        {"mes": "2024-07", "canal": "Chat", "reclamacoes": 2},
        {"mes": "2024-08", "canal": "Chat", "reclamacoes": 4},
    ]
    figure = build_figure(
        {"type": "line", "x": "mes", "y": "reclamacoes", "series": "canal", "title": "Reclamações"},
        ["mes", "canal", "reclamacoes"],
        rows,
    )
    assert figure.layout.title.text == "Reclamações"
