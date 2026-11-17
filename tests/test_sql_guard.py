import pytest

from src.errors import SqlRejected
from src.sql_guard import clean_sql, validate_sql


def test_select_passes():
    assert validate_sql("  SELECT 1  ").lower().startswith("select")


def test_with_passes():
    sql = validate_sql("WITH c AS (SELECT 1 AS n) SELECT n FROM c")
    assert sql.lower().startswith("with")


def test_strips_fence():
    assert clean_sql("```sql\nSELECT 1\n```") == "SELECT 1"


def test_rejects_second_statement():
    with pytest.raises(SqlRejected):
        validate_sql("SELECT 1; DROP TABLE clientes")


def test_rejects_write_keywords():
    with pytest.raises(SqlRejected):
        validate_sql("DROP TABLE clientes")
    with pytest.raises(SqlRejected):
        validate_sql("WITH c AS (SELECT 1 AS n) INSERT INTO t SELECT n FROM c")


def test_allows_drop_inside_a_string_and_replace_function():
    validate_sql("SELECT replace(nome, 'drop', 'x') FROM clientes WHERE nome = 'a;b'")


def test_rejects_empty_and_comments_only():
    with pytest.raises(SqlRejected):
        validate_sql("   ")
    with pytest.raises(SqlRejected):
        validate_sql("-- só um comentário")


def test_semicolon_inside_string_is_one_statement():
    validate_sql("SELECT ';' AS sinal")
