import re

from src.errors import SqlRejected

_BANNED = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|create|attach|detach|pragma|"
    r"vacuum|reindex|grant|revoke|truncate|analyze|begin|commit|"
    r"rollback|savepoint|load_extension"
    r")\b",
    re.IGNORECASE,
)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def clean_sql(sql: str) -> str:
    text = (sql or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def mask_sql(sql: str) -> str:
    """Apaga comentários e literais para o validador não se confundir com o texto."""
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        if sql.startswith("--", i):
            i += 2
            while i < n and sql[i] != "\n":
                i += 1
            out.append(" ")
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end < 0 else end + 2
            out.append(" ")
            continue
        if sql[i] == "'":
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" '' ")
            continue
        out.append(sql[i])
        i += 1
    return "".join(out)


def validate_sql(sql: str) -> str:
    cleaned = clean_sql(sql)
    masked = mask_sql(cleaned)
    if not masked.strip():
        raise SqlRejected("SQL vazio.")
    parts = [part.strip() for part in masked.split(";") if part.strip()]
    if len(parts) != 1:
        raise SqlRejected("Envie uma única instrução SQL.")
    if _BANNED.search(masked):
        raise SqlRejected("Só é permitida leitura. Comece com SELECT ou WITH.")
    first = re.match(r"[A-Za-z_]+", masked.strip())
    if not first or first.group(0).lower() not in {"select", "with"}:
        raise SqlRejected("A instrução precisa começar com SELECT ou WITH.")
    return cleaned


def quote_ident(name: str) -> str:
    if not _IDENT.fullmatch(name or ""):
        raise SqlRejected(f"Identificador inválido: {name}")
    return f'"{name}"'
