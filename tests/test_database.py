import sqlite3

import pytest

from src.config import DEFAULT_DB_PATH
from src.database import connect, inspect_database, run_select
from src.errors import SqlRejected


def test_schema_comes_from_the_file_not_from_the_pdf():
    tables, text = inspect_database(DEFAULT_DB_PATH)
    names = {table["name"] for table in tables}
    assert names == {"clientes", "compras", "suporte", "campanhas_marketing"}
    assert "valor_total_gasto" in text
    assert "data_ultima_compra" in text
    assert "WhatsApp" in text
    assert "Reclamação" in text
    assert "referencia" in text


def test_readonly_connection_rejects_writes():
    with connect(DEFAULT_DB_PATH) as conn:
        with pytest.raises(sqlite3.Error):
            conn.execute("CREATE TABLE hack (id INT)")


def test_run_select_returns_rows():
    with connect(DEFAULT_DB_PATH) as conn:
        result = run_select(conn, "SELECT COUNT(*) AS n FROM clientes")
    assert result.rows == [{"n": 100}]
    assert result.truncated is False


def test_run_select_blocks_a_write_disguised_as_text():
    with connect(DEFAULT_DB_PATH) as conn:
        with pytest.raises(SqlRejected):
            run_select(conn, "SELECT 1; DELETE FROM clientes")
