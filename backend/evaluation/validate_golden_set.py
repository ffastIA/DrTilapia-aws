"""Valida que cada `expected_passage` do golden set existe de fato na base vetorial.

Um golden set com trechos inexistentes mede o nada: toda pergunta falharia por
erro do conjunto, não do RAG. Este script roda antes de qualquer avaliação.

Uso:
    python -m evaluation.validate_golden_set
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import supabase_admin  # noqa: E402

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.yaml"


def normalize(text: str) -> str:
    """Normaliza para comparação tolerante a ruído de extração de PDF.

    Os PDFs produzem espaçamento irregular, aspas tipográficas e acentos
    decompostos. Comparar cru geraria falsos negativos.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def load_corpus() -> list[dict]:
    response = (
        supabase_admin.table("documents")
        .select("content, metadata")
        .execute()
    )
    return response.data or []


def main() -> int:
    spec = yaml.safe_load(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    corpus = load_corpus()
    haystack = normalize(" \n ".join(row["content"] or "" for row in corpus))

    print(f"Base: {len(corpus)} chunks carregados.")
    print(f"Golden set: {len(spec['questions'])} perguntas.\n")

    missing: list[tuple[str, str]] = []
    checked = 0

    for question in spec["questions"]:
        for passage in question.get("expected_passages") or []:
            checked += 1
            if normalize(passage) not in haystack:
                missing.append((question["id"], passage))

    in_corpus = sum(1 for q in spec["questions"] if q["scope"] == "in_corpus")
    out_corpus = sum(1 for q in spec["questions"] if q["scope"] == "out_of_corpus")
    follow_ups = sum(1 for q in spec["questions"] if q.get("history"))

    print(f"  in_corpus      : {in_corpus}")
    print(f"  out_of_corpus  : {out_corpus}")
    print(f"  com histórico  : {follow_ups}")
    print(f"  trechos checados: {checked}\n")

    if missing:
        print(f"FALHA — {len(missing)} trecho(s) não encontrado(s) na base:\n")
        for qid, passage in missing:
            print(f"  [{qid}]")
            print(f"    {passage[:120]}")
        return 1

    print("OK — todos os trechos esperados existem na base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
