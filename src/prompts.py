from src.follow import follow_note

SYSTEM_PROMPT = """Você é um analista júnior. Responda a pergunta somente com o que o SQLite devolver.

Dialeto: SQLite.
- Uma instrução por vez, começando com SELECT ou WITH.
- Datas estão em texto ISO (YYYY-MM-DD). Compare como texto ou use date e strftime.
- Booleanos são 0 ou 1.
- Não invente coluna, tabela ou número. Zero linhas não fecham a pergunta quando o filtro pode estar fora do intervalo. Só diga que não há registros depois de conferir o intervalo da coluna.
- Se a pergunta for ambígua, escolha a leitura mais útil, deixe a premissa na resposta e siga.
- A última consulta bem-sucedida é a que vira tabela ou gráfico. Os aliases precisam ser os nomes em viz_x, viz_y e viz_series.
- Para ranking, tendência ou comparação, agregue no SQL.
- Gráfico com várias séries: resultado em formato longo, com uma coluna de série e uma de valor.
- viz_type: metric para um número ou uma linha de indicadores; table para listas; bar para comparar categorias; line para série temporal; none quando não houver dado para desenhar.
- Resposta final em português, markdown simples, sem HTML. A frase responde a pergunta. A premissa da conta entra na mesma resposta.
- Se uma consulta falhar, leia o erro, corrija e tente de novo. Não repita o mesmo SQL.
- A conversa anterior chega no pedido, com a pergunta, a resposta e a SQL de cada turno.
- Quando a pergunta completa a anterior ("desses", "esses", "em 2024?", "e de SC?"), mantenha os filtros já combinados e acrescente só o que ela pediu. Se o pedido cita um ano, filtre por esse ano toda data que a SQL usar.
- Quando a pergunta abre outro assunto, troca o mês, pede os dois lados ("quantos foram do app e quantos não foram") ou o total, siga só esse pedido.
- A lista de nomes usa os mesmos filtros da contagem a que ela se refere. Se a lista tiver mais gente do que o número daquele turno, a consulta alargou o recorte. Refaça antes de responder.
- canal em compras, suporte e campanhas_marketing são campos diferentes. Filtre o canal na tabela da pergunta.

Glossário, quando a pergunta não definir outra conta:
- compra via app: compras.canal = 'App'
- cliente que comprou: COUNT(DISTINCT cliente_id), não a quantidade de linhas
- interação com campanha: campanhas_marketing.interagiu = 1
- reclamação: suporte.tipo_contato = 'Reclamação'
- reclamação não resolvida: reclamação com resolvido = 0
- média de compras por cliente numa categoria: COUNT(*) / COUNT(DISTINCT cliente_id) na tabela compras
- mês sem ano: não chute 2024 nem o ano corrente. Use o intervalo da coluna no schema e os anos em que aquele mês aparece. Diga quais anos entraram.
- último ano: da data máxima da coluna até um ano antes, inclusive, calculado no SQL
- valor_total_gasto e data_ultima_compra ficam em clientes. Para perguntas sobre compras, calcule a partir da tabela compras. A coluna pronta pode não bater com a soma das compras.
"""


def build_user_prompt(
    question: str,
    schema_text: str,
    steps: list[dict],
    must_answer: bool,
    prior: list[dict] | None = None,
) -> str:
    parts = [f"Pergunta:\n{question.strip()}"]
    note = follow_note(question, prior or [])
    if note:
        parts.append(note)
    parts.extend([
        f"Conversa anterior:\n{_conversation(prior or [])}",
        f"Schema:\n{schema_text}",
        f"Andamento desta pergunta:\n{_history(steps)}",
    ])
    if must_answer:
        parts.append(
            "As tentativas desta pergunta acabaram. "
            "Responda agora com action=answer, usando só as linhas já retornadas. "
            "Não peça outra consulta."
        )
    elif latest_query_is_empty(steps):
        parts.append(
            "A última consulta válida voltou 0 linhas. Não encerre com action=answer. "
            "O filtro pode estar fora do intervalo de datas do schema. "
            "Se a pergunta citou um mês sem ano, não reuse o ano chutado: "
            "consulte os anos em que esse mês existe e refaça a conta."
        )
    else:
        parts.append(
            "Se ainda falta um número, peça uma consulta. "
            "Se as linhas já respondem, devolva action=answer."
        )
    return "\n\n".join(parts)


def latest_query_is_empty(steps: list[dict]) -> bool:
    for step in reversed(steps):
        if step.get("kind") == "query" and step.get("ok"):
            return (step.get("row_count") or 0) == 0
    return False


def _conversation(prior: list[dict]) -> str:
    if not prior:
        return "Nenhuma pergunta anterior."
    blocks = [
        "Memória da conversa. "
        "Se esta pergunta completa a anterior, os filtros dela continuam. "
        "Se abre outro assunto, troca o período, pede os dois lados ou o total, siga só o pedido novo."
    ]
    for turn in prior:
        answer = (turn.get("answer") or "").strip().replace("\n", " ")
        if len(answer) > 500:
            answer = answer[:497] + "..."
        block = f"Pergunta: {turn.get('question', '').strip()}\nResposta: {answer}"
        sql = (turn.get("sql") or "").strip()
        if sql:
            block += f"\nSQL usado:\n{sql}"
        preview = _turn_preview(turn)
        if preview:
            block += f"\nResultado:\n{preview}"
        blocks.append(block)
    return "\n\n".join(blocks)


def _turn_preview(turn: dict, limit: int = 8) -> str:
    columns = turn.get("columns") or []
    rows = turn.get("rows") or []
    if not columns or not rows:
        return ""
    lines = [" | ".join(columns)]
    for row in rows[:limit]:
        lines.append(" | ".join("" if row.get(column) is None else str(row.get(column)) for column in columns))
    remaining = (turn.get("row_count") or len(rows)) - limit
    if remaining > 0:
        lines.append(f"... mais {remaining} linhas")
    return "\n".join(lines)


def _history(steps: list[dict]) -> str:
    if not steps:
        return "Nenhuma consulta ainda."
    blocks: list[str] = []
    for step in steps:
        if step["kind"] == "thought":
            if step.get("text"):
                blocks.append(f"Raciocínio: {step['text']}")
            continue
        if step.get("ok"):
            blocks.append(
                f"Consulta ({step.get('purpose') or 'sem propósito'}):\n"
                f"{step.get('sql')}\n"
                f"Resultado ({step.get('row_count', 0)} linhas):\n"
                f"{_preview(step)}"
            )
            continue
        blocks.append(
            f"Consulta com erro ({step.get('purpose') or 'sem propósito'}):\n"
            f"{step.get('sql')}\n"
            f"Erro: {step.get('error')}"
        )
    return "\n\n".join(blocks)


def _preview(step: dict, limit: int = 12) -> str:
    columns = step.get("columns") or []
    rows = step.get("rows") or []
    if not columns:
        return "(sem colunas)"
    lines = [" | ".join(columns)]
    for row in rows[:limit]:
        lines.append(" | ".join("" if row.get(column) is None else str(row.get(column)) for column in columns))
    remaining = len(rows) - limit
    if remaining > 0:
        lines.append(f"... mais {remaining} linhas")
    if step.get("truncated"):
        lines.append("resultado truncado")
    return "\n".join(lines)
