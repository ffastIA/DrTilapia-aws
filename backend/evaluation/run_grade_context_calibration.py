# CAMINHO: backend/evaluation/run_grade_context_calibration.py
"""Calibração de `grade_context` contra o golden set completo
(`add-rag-self-correction-loop`, grupo 2 task 2.3 / grupo 3).

Roda só retrieve + companions + `grade_context` — não gera resposta. Mais
barato e rápido que `run_eval.py --full`, e é tudo que a calibração precisa:
julgar se o veredito de suficiência bate com o resultado esperado por
pergunta (`in_corpus` → sufficient/partial aceitáveis; `out_of_corpus` →
insufficient esperado). Usa `retrieve_for_eval` (mesmo seam de condensação
de follow-up do harness principal) + `_add_data_companion_chunks` +
`_grade_context_verdict`, os mesmos métodos que produção usa — para a
calibração nunca medir um comportamento diferente do que roda de verdade.

Uso:
    python -m evaluation.run_grade_context_calibration
    python -m evaluation.run_grade_context_calibration --label pos-ajuste-prompt
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rag_service import get_rag_service  # noqa: E402
from app.utils.rag_config import DATA_COMPANION_ENABLED  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
GOLDEN_SET_PATH = EVAL_DIR / "golden_set.yaml"
RUNS_DIR = EVAL_DIR / "runs"


def _verdict_matches_expected(verdict: str, scope: str) -> bool:
    """`out_of_corpus` só aceita `insufficient`. `in_corpus` aceita
    `sufficient` OU `partial` — contexto parcialmente relevante para uma
    pergunta respondível ainda é um veredito correto (não é o caso que
    `grade_context` precisa pegar; esse é o out-of-scope disfarçado)."""
    if scope == "out_of_corpus":
        return verdict == "insufficient"
    return verdict in ("sufficient", "partial")


def run(label: str) -> int:
    service = get_rag_service()
    golden = yaml.safe_load(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    questions = golden["questions"]

    results: List[Dict[str, Any]] = []
    for q in questions:
        docs, trace = service.retrieve_for_eval(
            q["question"], q.get("history"), use_llm_expansion=True
        )
        question_type = q.get("question_type", "conceptual")
        if DATA_COMPANION_ENABLED and question_type in ("conceptual", "quantitative"):
            docs = service._add_data_companion_chunks(docs)
        context = "\n\n".join(d.page_content for d in docs)

        # Pergunta condensada (follow-up + histórico), não a crua — mesma
        # correção aplicada ao nó `grade_context` em produção: julgar contra
        # a pergunta crua de um follow-up ("E qual teve o menor?") a torna
        # ininteligível mesmo com o contexto certo.
        question_for_grading = trace.get("retrieval_query") or q["question"]
        verdict = "insufficient" if not docs else service._grade_context_verdict(
            question_for_grading, context
        )
        match = _verdict_matches_expected(verdict, q["scope"])

        results.append({
            "id": q["id"],
            "scope": q["scope"],
            "question_type": question_type,
            "selected_count": len(docs),
            "top_similarity_raw": trace.get("top_similarity_raw"),
            "verdict": verdict,
            "matches_expected": match,
        })
        flag = "OK " if match else "XX "
        print(
            f"{flag}{q['id']:32s} scope={q['scope']:14s} "
            f"verdict={verdict:12s} ndocs={len(docs)}"
        )

    total = len(results)
    correct = sum(1 for r in results if r["matches_expected"])
    by_scope: Dict[str, List[dict]] = {}
    for r in results:
        by_scope.setdefault(r["scope"], []).append(r)

    print()
    print(f"Acurácia geral: {correct}/{total} ({correct / total:.1%})")
    for scope, rows in sorted(by_scope.items()):
        c = sum(1 for r in rows if r["matches_expected"])
        print(f"  {scope}: {c}/{len(rows)} ({c / len(rows):.1%})")

    misses = [r for r in results if not r["matches_expected"]]
    if misses:
        print("\nDivergências:")
        for r in misses:
            print(f"  {r['id']} (scope={r['scope']}) -> verdict={r['verdict']}")

    RUNS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RUNS_DIR / f"{timestamp}-{label}.json"
    out_path.write_text(
        json.dumps(
            {
                "label": label,
                "timestamp": timestamp,
                "accuracy": correct / total,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nSalvo em {out_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="grade-context-calibration")
    args = parser.parse_args()
    raise SystemExit(run(args.label))
