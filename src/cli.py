import argparse
import sys

from src.agent import ask
from src.config import db_path
from src.errors import DatabaseNotFound, MissingModelConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pergunte ao banco da Mesa")
    parser.add_argument("question", nargs="+")
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)
    try:
        result = ask(" ".join(args.question), database=args.db or db_path())
    except MissingModelConfig as exc:
        print(exc, file=sys.stderr)
        return 2
    except DatabaseNotFound as exc:
        print(exc, file=sys.stderr)
        return 1
    print(result.answer)
    print()
    for step in result.steps:
        if step.get("kind") != "query":
            continue
        status = "ok" if step.get("ok") else "erro"
        print(f"-- {status}: {step.get('purpose')}")
        print(step.get("sql"))
        if step.get("error"):
            print(step["error"])
        else:
            print(f"{step.get('row_count')} linhas")
        print()
    return 0
