import re

MONTHS = (
    ("janeiro", "01"),
    ("fevereiro", "02"),
    ("março", "03"),
    ("marco", "03"),
    ("abril", "04"),
    ("maio", "05"),
    ("junho", "06"),
    ("julho", "07"),
    ("agosto", "08"),
    ("setembro", "09"),
    ("outubro", "10"),
    ("novembro", "11"),
    ("dezembro", "12"),
)
CHANNELS = (
    ("whatsapp", "WhatsApp"),
    ("loja física", "Loja Física"),
    ("loja fisica", "Loja Física"),
    ("loja", "Loja Física"),
    ("e-mail", "E-mail"),
    ("email", "E-mail"),
    ("telefone", "Telefone"),
    ("chat", "Chat"),
    ("site", "Site"),
    ("sms", "SMS"),
    ("app", "App"),
)
STATES = (
    ("mato grosso do sul", "Mato Grosso do Sul"),
    ("mato grosso", "Mato Grosso"),
    ("rio grande do sul", "Rio Grande do Sul"),
    ("rio de janeiro", "Rio de Janeiro"),
    ("minas gerais", "Minas Gerais"),
    ("santa catarina", "Santa Catarina"),
    ("espírito santo", "Espírito Santo"),
    ("espirito santo", "Espírito Santo"),
    ("são paulo", "São Paulo"),
    ("sao paulo", "São Paulo"),
    ("alagoas", "Alagoas"),
    ("amazonas", "Amazonas"),
    ("bahia", "Bahia"),
    ("ceará", "Ceará"),
    ("ceara", "Ceará"),
    ("goiás", "Goiás"),
    ("goias", "Goiás"),
    ("paraná", "Paraná"),
    ("parana", "Paraná"),
    ("paraíba", "Paraíba"),
    ("paraiba", "Paraíba"),
    ("pernambuco", "Pernambuco"),
    ("piauí", "Piauí"),
    ("piaui", "Piauí"),
    ("roraima", "Roraima"),
    ("sergipe", "Sergipe"),
    ("tocantins", "Tocantins"),
    ("pará", "Pará"),
    ("para", "Pará"),
    ("ms", "Mato Grosso do Sul"),
    ("mt", "Mato Grosso"),
    ("rs", "Rio Grande do Sul"),
    ("rj", "Rio de Janeiro"),
    ("mg", "Minas Gerais"),
    ("sc", "Santa Catarina"),
    ("es", "Espírito Santo"),
    ("sp", "São Paulo"),
    ("al", "Alagoas"),
    ("am", "Amazonas"),
    ("ba", "Bahia"),
    ("ce", "Ceará"),
    ("go", "Goiás"),
    ("pr", "Paraná"),
    ("pb", "Paraíba"),
    ("pe", "Pernambuco"),
    ("pi", "Piauí"),
    ("rr", "Roraima"),
    ("se", "Sergipe"),
    ("to", "Tocantins"),
    ("pa", "Pará"),
)
DATE_COLUMNS = ("data_compra", "data_envio", "data_contato", "data_ultima_compra")
TABLE_DATES = (
    ("campanhas_marketing", "data_envio"),
    ("compras", "data_compra"),
    ("suporte", "data_contato"),
)
_ANAPHORA = re.compile(
    r"\b(desses|dessas|deles|delas|esses|essas|neles|nelas|aqueles|aquelas|disso|nessa|nesse|nisso)\b"
    r"|você disse|voce disse|você me trouxe|voce me trouxe|você falou|voce falou|como que tem",
    re.IGNORECASE,
)
_SHORT = re.compile(
    r"^(e|em|de|do|da|pelo|pela|no|na|nos|nas|qual|quais|tem|só|somente|mas|sem)\b",
    re.IGNORECASE,
)
_FOLLOW_PHRASE = ("no total", "num total", "um total", "sem ser", "fora de", "exceto ")
_RELEASE_DATE = (
    "qualquer mês",
    "qualquer mes",
    "todos os meses",
    "num total",
    "no total",
    "um total",
    "o ano todo",
    "ano inteiro",
    "em geral",
    "histórico",
    "historico",
    "independente do mês",
    "independente do mes",
    "qualquer ano",
)
_EXCLUDE_MONTH = re.compile(
    r"\b(?:sem ser em|sem ser|fora de|exceto|tirando|menos em|não em|nao em|que não seja|que nao seja)\s+("
    + "|".join(re.escape(name) for name, _ in MONTHS)
    + r")\b",
    re.IGNORECASE,
)
_OPEN_CHANNEL = (
    "quantos não",
    "quais não",
    "quantos nao",
    "quais nao",
    "ou não",
    "ou nao",
    "não foram",
    "nao foram",
    "app ou não",
    "app ou nao",
)


def follow_note(question: str, prior: list[dict]) -> str:
    required = required_predicates(prior, question)
    if not required:
        return ""
    listed = "; ".join(describe(item) for item in required)
    return (
        "Esta pergunta completa a anterior. A SQL tem de incluir "
        f"{listed}. Pode acrescentar filtro. Não tire estes."
    )


def follow_gap(sql: str, question: str, prior: list[dict]) -> str | None:
    required = required_predicates(prior, question)
    missing = [describe(item) for item in required if not has_predicate(sql, item)]
    year = _mentioned_year(question)
    if year:
        for column in _dates_in_play(sql):
            if not _column_has_year(sql, column, year):
                missing.append(f"{column} em {year}")
    if not missing:
        return None
    return (
        "Esta pergunta completa a anterior. A consulta tirou ou não incluiu: "
        + ", ".join(dict.fromkeys(missing))
        + ". Mantenha o recorte já combinado e acrescente só o que foi pedido agora."
    )


def required_predicates(prior: list[dict], question: str) -> list[dict]:
    if not prior or not is_follow_up(question):
        return []
    current: list[dict] = []
    for turn in prior:
        asked = turn.get("question") or ""
        found = extract_predicates(turn.get("sql") or "")
        if not current or not is_follow_up(asked):
            current = found
        else:
            current = _apply(current, asked)
            current = _merge(current, [item for item in found if not _released(item, asked)])
    return _apply(current, question)


def is_follow_up(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    if _ANAPHORA.search(text):
        return True
    low = text.lower()
    if any(phrase in low for phrase in _FOLLOW_PHRASE):
        return True
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    return len(words) <= 6 and bool(_SHORT.search(text))


def extract_predicates(sql: str) -> list[dict]:
    source = re.sub(r"\bcase\b.*?\bend\b", " ", sql or "", flags=re.IGNORECASE | re.DOTALL)
    found: list[dict] = []
    for match in re.finditer(r"strftime\(\s*'%Y'\s*,[^)]*\)\s*=\s*'(\d{4})'", source, re.IGNORECASE):
        found.append({"kind": "year", "year": match.group(1)})
    for match in re.finditer(
        r"strftime\(\s*'%Y-%m'\s*,[^)]*\)\s*=\s*'(\d{4})-(\d{2})'",
        source,
        re.IGNORECASE,
    ):
        found.append({"kind": "year", "year": match.group(1)})
        found.append({"kind": "month", "month": match.group(2)})
    for match in re.finditer(r"strftime\(\s*'%m'\s*,[^)]*\)\s*=\s*'(\d{2})'", source, re.IGNORECASE):
        found.append({"kind": "month", "month": match.group(1)})
    for match in re.finditer(
        r"\b(canal|estado|tipo_contato|nome_campanha|categoria|genero|profissao|cidade)\s*=\s*'([^']+)'",
        source,
        re.IGNORECASE,
    ):
        found.append({"kind": "eq", "column": match.group(1).lower(), "value": match.group(2)})
    for match in re.finditer(r"\b(interagiu|resolvido)\s*=\s*(\d+)", source, re.IGNORECASE):
        found.append({"kind": "eq", "column": match.group(1).lower(), "value": match.group(2)})
    return _dedupe(found)


def has_predicate(sql: str, pred: dict) -> bool:
    kind = pred["kind"]
    if kind == "year":
        return _has_year(sql, pred["year"])
    if kind == "month":
        return _has_month(sql, pred["month"])
    if kind == "month_ne":
        return bool(
            re.search(
                rf"strftime\(\s*'%m'\s*,[^)]*\)\s*(?:!=|<>)\s*'{pred['month']}'",
                sql,
                re.IGNORECASE,
            )
        )
    column = pred["column"]
    value = pred["value"]
    if value.isdigit():
        return bool(re.search(rf"\b{column}\s*=\s*{value}\b", sql, re.IGNORECASE))
    return bool(re.search(rf"\b{column}\s*=\s*'{re.escape(value)}'", sql, re.IGNORECASE))


def describe(pred: dict) -> str:
    kind = pred["kind"]
    if kind == "year":
        return f"ano {pred['year']}"
    if kind == "month":
        return f"mês {pred['month']}"
    if kind == "month_ne":
        return f"mês diferente de {pred['month']}"
    value = pred["value"]
    if str(value).isdigit():
        return f"{pred['column']} = {value}"
    return f"{pred['column']} = '{value}'"


def _apply(current: list[dict], question: str) -> list[dict]:
    kept = [item for item in current if not _released(item, question)]
    return _dedupe(kept + _added(question))


def _added(question: str) -> list[dict]:
    added: list[dict] = []
    excluded = _excluded_month(question)
    if excluded and not _releases_date(question):
        added.append({"kind": "month_ne", "month": excluded})
    elif not _releases_date(question):
        month = _mentioned_month(question)
        if month:
            added.append({"kind": "month", "month": month})
    year = _mentioned_year(question)
    if year and not _releases_date(question):
        added.append({"kind": "year", "year": year})
    if not _opens_channel(question) and "qualquer canal" not in question.lower() and "todos os canais" not in question.lower():
        for channel in _mentioned_channels(question):
            added.append({"kind": "eq", "column": "canal", "value": channel})
    state = _mentioned_state(question)
    low = question.lower()
    if state and "por estado" not in low and "cada estado" not in low and "todos os estados" not in low:
        added.append({"kind": "eq", "column": "estado", "value": state})
    return added


def _released(pred: dict, question: str) -> bool:
    kind = pred["kind"]
    if kind == "year":
        if _releases_date(question):
            return True
        named = _mentioned_year(question)
        return named is not None and named != pred["year"]
    if kind == "month":
        if _releases_date(question) or _excluded_month(question):
            return True
        named = _mentioned_month(question)
        return named is not None and named != pred["month"]
    if kind == "month_ne":
        return _releases_date(question) or _mentioned_month(question) not in {None, pred["month"]}
    if kind == "eq" and pred["column"] == "canal":
        low = question.lower()
        if "qualquer canal" in low or "todos os canais" in low or _opens_channel(question):
            return True
        return False
    if kind == "eq" and pred["column"] == "estado":
        low = question.lower()
        if "todos os estados" in low or "por estado" in low or "cada estado" in low:
            return True
        named = _mentioned_state(question)
        return named is not None and named.lower() != pred["value"].lower()
    return False


def _opens_channel(question: str) -> bool:
    low = question.lower()
    return any(phrase in low for phrase in _OPEN_CHANNEL)


def _releases_date(question: str) -> bool:
    low = question.lower()
    return any(phrase in low for phrase in _RELEASE_DATE)


def _mentioned_year(question: str) -> str | None:
    found = re.search(r"\b(20\d{2})\b", question)
    return found.group(1) if found else None


def _mentioned_month(question: str) -> str | None:
    for name, code in MONTHS:
        if re.search(rf"\b{name}\b", question, re.IGNORECASE):
            return code
    return None


def _excluded_month(question: str) -> str | None:
    found = _EXCLUDE_MONTH.search(question)
    if not found:
        return None
    name = found.group(1).lower()
    for month_name, code in MONTHS:
        if month_name == name:
            return code
    return None


def _mentioned_channels(question: str) -> list[str]:
    found: list[str] = []
    for word, value in CHANNELS:
        if re.search(rf"\b{re.escape(word)}\b", question, re.IGNORECASE) and value not in found:
            found.append(value)
    return found


def _mentioned_state(question: str) -> str | None:
    for name, value in STATES:
        if re.search(rf"\b{re.escape(name)}\b", question, re.IGNORECASE):
            return value
    return None


def _has_year(sql: str, year: str) -> bool:
    return bool(
        re.search(rf"strftime\(\s*'%Y'\s*,[^)]*\)\s*=\s*'{year}'", sql, re.IGNORECASE)
        or re.search(rf"strftime\(\s*'%Y-%m'\s*,[^)]*\)\s*=\s*'{year}-", sql, re.IGNORECASE)
        or re.search(rf"like\s*'%{year}%'", sql, re.IGNORECASE)
        or re.search(rf">=\s*'{year}-", sql, re.IGNORECASE)
    )


def _has_month(sql: str, month: str) -> bool:
    return bool(
        re.search(rf"strftime\(\s*'%m'\s*,[^)]*\)\s*=\s*'{month}'", sql, re.IGNORECASE)
        or re.search(rf"strftime\(\s*'%Y-%m'\s*,[^)]*\)\s*=\s*'\d{{4}}-{month}'", sql, re.IGNORECASE)
    )


def _dates_in_play(sql: str) -> list[str]:
    found = [column for column in DATE_COLUMNS if re.search(rf"\b{column}\b", sql, re.IGNORECASE)]
    for table, column in TABLE_DATES:
        if column not in found and re.search(rf"\b{table}\b", sql, re.IGNORECASE):
            found.append(column)
    return found


def _column_has_year(sql: str, column: str, year: str) -> bool:
    return bool(
        re.search(rf"strftime\(\s*'%Y'\s*,\s*[\w.]*{column}\s*\)\s*=\s*'{year}'", sql, re.IGNORECASE)
        or re.search(rf"strftime\(\s*'%Y-%m'\s*,\s*[\w.]*{column}\s*\)\s*=\s*'{year}-", sql, re.IGNORECASE)
        or re.search(rf"{column}\s*(?:>=|like)\s*'?{year}", sql, re.IGNORECASE)
        or re.search(rf"{column}[^;\n]{{0,48}}{year}", sql, re.IGNORECASE)
    )


def _merge(current: list[dict], extra: list[dict]) -> list[dict]:
    return _dedupe([*current, *extra])


def _dedupe(items: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    unique: list[dict] = []
    for item in items:
        key = tuple(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
