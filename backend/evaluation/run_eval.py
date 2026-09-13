"""Executor de avaliação de qualidade do RAG.

Mede recuperação (barato, determinístico) e, opcionalmente, geração (caro).
Cada execução é salva com a configuração vigente, para que duas execuções sejam
comparáveis — foi justamente a ausência disso que permitiu que as regressões de
embedding e chunking passassem despercebidas.

Uso:
    python -m evaluation.run_eval --retrieval-only
    python -m evaluation.run_eval --full
    python -m evaluation.run_eval --compare runs/a.json runs/b.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from langchain_community.callbacks.manager import get_openai_callback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.metrics import (  # noqa: E402
    is_refusal,
    looks_like_empty_skeleton,
    mention_coverage,
    passage_rank,
)
from app.utils.rag_config import (  # noqa: E402
    MULTI_QUERY_EXPANSION_ENABLED,
    MULTI_QUERY_VARIANT_COUNT,
)

# Abaixo disso, `selected_count` (via `retrieve_for_eval`) é considerado
# fome de contexto — medido: hoje a distribuição real nunca cai entre 7 e
# 39 chunks selecionados, só 1-6 (fome) ou 40 (inundação). A change
# `restore-rag-answer-quality` formaliza isso como `CONTEXT_MIN_CHUNKS`;
# até lá, este valor é o mesmo limite observado, hardcoded aqui só para dar
# visibilidade ao problema que motiva aquela mudança.
STARVATION_CHUNK_THRESHOLD = 6

EVAL_DIR = Path(__file__).resolve().parent
GOLDEN_SET_PATH = EVAL_DIR / "golden_set.yaml"
RUNS_DIR = EVAL_DIR / "runs"

# Preços em USD por 1M de tokens. Fonte: tabela pública da OpenAI.
# Mantidos em um único lugar visível — se ficarem desatualizados, o custo
# reportado fica errado de forma silenciosa.
PRICING_USD_PER_1M = {
    "text-embedding-ada-002": {"input": 0.10},
    "text-embedding-3-small": {"input": 0.02},
    "text-embedding-3-large": {"input": 0.13},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


# --------------------------------------------------------------------- config

def capture_config(service: Any, k: int, use_llm_expansion: bool) -> dict:
    """Fotografa a configuração efetiva do RAG.

    Lê os valores REAIS dos objetos, não os presumidos: o modelo de embedding
    atual vem de um default implícito da biblioteca, e é exatamente esse tipo
    de divergência entre o presumido e o efetivo que precisamos flagrar.

    Inclui `k` e o uso de expansão de query por LLM — parâmetros da própria
    execução, não do serviço, mas tão decisivos para o resultado quanto o
    modelo ou o chunk size. Antes viviam soltos no topo do run (fora deste
    dict), então duas execuções só eram comparáveis nesses dois eixos lendo
    o nome do arquivo ou os campos de topo separadamente — não a config em si.
    """
    embeddings = service.embeddings
    splitter = service.text_splitter
    return {
        "embedding_model": getattr(embeddings, "model", "desconhecido"),
        "embedding_dimensions": getattr(embeddings, "dimensions", None),
        "chunk_size": getattr(splitter, "_chunk_size", None),
        "chunk_overlap": getattr(splitter, "_chunk_overlap", None),
        "similarity_threshold": getattr(service, "similarity_threshold", None),
        # `restore-rag-answer-quality` separou o modelo de geração final do
        # modelo utilitário (expansão de query, condensação, juízes) —
        # `llm_model` fica como alias de `generation_model` para não quebrar
        # comparação com runs salvos antes dessa mudança.
        "generation_model": getattr(service.llm_generation, "model_name", None),
        "utility_model": getattr(service.llm_utility, "model_name", None),
        "llm_model": getattr(service.llm_generation, "model_name", None),
        "retrieval_k": k,
        "use_llm_expansion": use_llm_expansion,
        # add-multi-query-retrieval-expansion: lido do config efetivo, não do
        # que este run presume — a flag pode ter sido setada via env var sem
        # o harness saber, e um run salvo precisa registrar o que realmente
        # rodou para ser comparável depois.
        "multi_query_expansion_enabled": MULTI_QUERY_EXPANSION_ENABLED,
        "multi_query_variant_count": MULTI_QUERY_VARIANT_COUNT if MULTI_QUERY_EXPANSION_ENABLED else None,
    }


# ------------------------------------------------------------------ execution

def evaluate_retrieval(service: Any, question: dict, k: int, use_llm_expansion: bool) -> dict:
    """Mede recuperação via `retrieve_for_eval` — o mesmo seam que condensa
    follow-ups com histórico antes de buscar, para que perguntas `fu-*` do
    golden set sejam medidas no mesmo caminho que a produção usa, não pela
    pergunta crua isolada."""
    started = time.perf_counter()
    docs, trace = service.retrieve_for_eval(
        question["question"], question.get("history"), k=k, use_llm_expansion=use_llm_expansion
    )
    elapsed = time.perf_counter() - started

    contents = [doc.page_content for doc in docs]
    similarities = [doc.metadata.get("similarity", 0.0) for doc in docs]

    expected = question.get("expected_passages") or []
    ranks = {passage: passage_rank(passage, contents) for passage in expected}
    found = [p for p, r in ranks.items() if r is not None]
    missed = [p for p, r in ranks.items() if r is None]

    return {
        "retrieved_count": len(docs),
        # `top_similarity`: só entre os docs pós-gate, para compatibilidade
        # com runs antigos. `top_similarity_raw` (via trace) é o sinal
        # confiável — não é contaminado por uma recusa zerando a lista.
        "top_similarity": max(similarities) if similarities else 0.0,
        "min_similarity": min(similarities) if similarities else 0.0,
        "expected_total": len(expected),
        "expected_found": len(found),
        "recall": (len(found) / len(expected)) if expected else None,
        "first_hit_rank": min((r for r in ranks.values() if r is not None), default=None),
        "missed_passages": missed,
        "retrieval_seconds": round(elapsed, 3),
        "retrieval_query": trace.get("retrieval_query"),
        "candidate_count": trace.get("candidate_count"),
        "top_similarity_raw": trace.get("top_similarity_raw"),
        "selected_count": trace.get("selected_count"),
        "context_chars": trace.get("context_chars"),
        "selection_reason": trace.get("selection_reason"),
    }


def evaluate_generation(
    service: Any, question: dict, judge: Any, usefulness_judge: Any = None
) -> dict:
    started = time.perf_counter()
    answer_result = service.get_answer(question["question"], question.get("history") or [])
    answer = answer_result.answer
    elapsed = time.perf_counter() - started

    refused = is_refusal(answer)
    out_of_corpus = question["scope"] == "out_of_corpus"
    # Esqueleto só é um problema de qualidade em uma resposta que NÃO se
    # apresentou como recusa — uma recusa de verdade não deveria ser
    # penalizada por conter os mesmos marcadores de "sem dados".
    skeleton = (not refused) and looks_like_empty_skeleton(answer)

    cited_files = [s.get("file") for s in (answer_result.sources or []) if s.get("file")]
    expected_file = question.get("expected_source_file")
    citation_precision = None
    if expected_file and cited_files:
        citation_precision = sum(1 for f in cited_files if f == expected_file) / len(cited_files)

    result = {
        "answer_chars": len(answer),
        "refused": refused,
        "skeleton": skeleton,
        # Para out_of_corpus, o acerto é recusar. Para in_corpus, é NÃO recusar.
        "refusal_correct": refused if out_of_corpus else (not refused),
        "mention_coverage": (
            None if out_of_corpus else mention_coverage(answer, question.get("must_mention") or [])
        ),
        "generation_seconds": round(elapsed, 3),
        "answer": answer,
        "sources": answer_result.sources,
        "cited_files": cited_files,
        "citation_file_count": len(cited_files),
        # Fração dos arquivos citados que É o esperado — None quando não há
        # arquivo esperado (out_of_corpus) ou nenhuma fonte foi citada.
        # Uma resposta que cita 3 arquivos mas só 1 é o certo pontua 0.33 —
        # visível aqui, não escondido numa média que só olha "acertou ou não".
        "citation_precision": citation_precision,
    }

    if judge is not None and not out_of_corpus:
        real_context = (answer_result.debug or {}).get("context", "")
        result["groundedness"] = judge(question["question"], answer, real_context)

    # Utilidade é medida em toda resposta não recusada, dentro ou fora do
    # escopo — é uma pergunta distinta de "está embasada": um esqueleto
    # vazio pode estar perfeitamente embasado no contexto pobre que recebeu
    # e ainda assim não responder nada de útil ao usuário.
    if usefulness_judge is not None and not refused:
        result["answers_question"] = usefulness_judge(question["question"], answer)

    return result


def build_judge(service: Any):
    """Juiz de embasamento, isolado da geração (decisão 3 do design) — mas
    julgando o CONTEXTO REAL que a resposta recebeu, não um contexto
    re-recuperado de forma independente.

    Antes, este juiz chamava `_retrieve_docs_via_rpc(question, k=20,
    use_llm_expansion=False)` — uma recuperação com parâmetros diferentes da
    que gerou a resposta. `gen-fis-extremos` é o caso medido: a resposta
    continha os valores corretos (groundedness deveria ser alto), mas o
    juiz pontuou 0 porque o SEU PRÓPRIO re-retrieval, não o da resposta,
    não trouxe a tabela. O isolamento em relação à CHAMADA de geração
    continua (é um passo de avaliação separado, não a mesma invocação de
    LLM) — só o contexto passa a ser o mesmo.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    system = SystemMessage(content=(
        "Você avalia se uma resposta está embasada no contexto fornecido. "
        "Responda APENAS com um número de 0 a 100, sem texto adicional. "
        "100 = toda afirmação da resposta se sustenta no contexto. "
        "0 = a resposta é inventada. "
        "Penalize números que não aparecem no contexto."
    ))

    def judge(question: str, answer: str, context: str) -> float | None:
        message = HumanMessage(content=(
            f"CONTEXTO:\n{context[:20000]}\n\n"
            f"PERGUNTA: {question}\n\nRESPOSTA:\n{answer}\n\n"
            "Nota de embasamento (0-100):"
        ))
        try:
            raw = service.llm_utility.invoke([system, message]).content
            digits = "".join(ch for ch in raw if ch.isdigit())
            return float(digits[:3]) if digits else None
        except Exception as exc:  # noqa: BLE001
            print(f"    [aviso] juiz falhou: {exc}")
            return None

    return judge


def build_usefulness_judge(service: Any):
    """Juiz de utilidade — distinto de `groundedness` por desenho.

    Groundedness pergunta "isto está apoiado no contexto?"; um esqueleto de
    seções vazias PODE estar perfeitamente apoiado num contexto pobre e
    ainda assim não responder nada. Este juiz vê só pergunta e resposta,
    SEM o contexto — de propósito, para que não possa justificar um
    esqueleto vazio como "consistente com o contexto disponível".
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    # Calibrado manualmente contra dois casos reais: uma resposta curta com
    # valor numérico concreto (deveria pontuar alto) inicialmente pontuou 20
    # com um prompt mais vago ("responde de verdade... direta, específica e
    # substantiva") — o juiz parecia penalizar concisão em si. Âncoras
    # explícitas de nota alta/baixa com exemplos resolveram: mesma resposta
    # passou a pontuar 90, e o esqueleto de seções vazias permaneceu em 10.
    system = SystemMessage(content=(
        "Você avalia se uma RESPOSTA responde de verdade a uma PERGUNTA — não se "
        "está correta, não se está completa, não se é bem escrita. Você não vê o "
        "contexto que embasou a resposta; julgue só pela forma.\n\n"
        "Responda APENAS com um número inteiro de 0 a 100, sem nenhum texto "
        "adicional, sem explicação, sem pontuação.\n\n"
        "Dê nota ALTA (80-100) para: qualquer resposta direta e específica, "
        "mesmo curta — uma frase com um valor numérico concreto, um fato "
        "específico, ou uma explicação objetiva já conta como resposta útil. "
        "Extensão e elaboração NÃO são critério.\n\n"
        "Dê nota BAIXA (0-20) APENAS para: uma resposta que não contém "
        "informação substantiva alguma — um esqueleto de seções vazias "
        "('dados não disponíveis'), uma esquiva genérica, ou uma frase dizendo "
        "que a informação não foi encontrada, MAS que não se apresenta como uma "
        "recusa clara (se fosse uma recusa clara e honesta, isso é correto, não "
        "seria avaliado aqui).\n\n"
        "Exemplo nota 95: 'O tratamento X teve 64% de eficácia, o maior do estudo.'\n"
        "Exemplo nota 10: 'Dados numéricos não disponíveis no contexto. O contexto "
        "não fornece informações específicas sobre o tema.'"
    ))

    def judge(question: str, answer: str) -> float | None:
        message = HumanMessage(content=(
            f"PERGUNTA: {question}\n\nRESPOSTA:\n{answer}\n\nNota:"
        ))
        try:
            raw = service.llm_utility.invoke([system, message]).content
            digits = "".join(ch for ch in raw if ch.isdigit())
            return float(digits[:3]) if digits else None
        except Exception as exc:  # noqa: BLE001
            print(f"    [aviso] juiz de utilidade falhou: {exc}")
            return None

    return judge


# -------------------------------------------------------------------- summary

def estimate_embedding_calls(question_count: int, use_llm_expansion: bool, full: bool) -> int:
    """Estimativa de chamadas de embedding, que o callback do LangChain não cobre.

    Uma por recuperação — exceto quando `MULTI_QUERY_EXPANSION_ENABLED`, caso
    em que cada recuperação embute `MULTI_QUERY_VARIANT_COUNT` variantes em
    vez de uma só (add-multi-query-retrieval-expansion). No modo completo há
    a recuperação da avaliação, mais a de dentro do `get_answer` (com
    possíveis retries — não contados) e a do juiz.
    """
    variants_per_retrieval = (
        MULTI_QUERY_VARIANT_COUNT if (MULTI_QUERY_EXPANSION_ENABLED and use_llm_expansion) else 1
    )
    per_question = variants_per_retrieval  # recuperação da avaliação
    if full:
        per_question += variants_per_retrieval  # recuperação dentro de get_answer
        per_question += 1  # juiz (chamada avulsa, não escala com variantes)
    return question_count * per_question


def summarize(results: list[dict]) -> dict:
    in_corpus = [r for r in results if r["scope"] == "in_corpus"]
    out_corpus = [r for r in results if r["scope"] == "out_of_corpus"]

    recalls = [r["retrieval"]["recall"] for r in in_corpus
               if r.get("retrieval") and r["retrieval"]["recall"] is not None]
    top_sims = [r["retrieval"]["top_similarity"] for r in results if r.get("retrieval")]

    summary: dict[str, Any] = {
        "questions_total": len(results),
        "questions_in_corpus": len(in_corpus),
        "questions_out_of_corpus": len(out_corpus),
        "mean_recall": round(statistics.mean(recalls), 3) if recalls else None,
        "perfect_recall_rate": (
            round(sum(1 for r in recalls if r == 1.0) / len(recalls), 3) if recalls else None
        ),
        "mean_top_similarity": round(statistics.mean(top_sims), 3) if top_sims else None,
    }

    # Tamanho do contexto selecionado — hoje invisível fora de olhar log por
    # log. `selected_count`/`context_chars` vêm do trace de `retrieve_for_eval`
    # (task 1), presentes em toda pergunta com `retrieval`, independente do
    # modo (`--retrieval-only` ou `--full`).
    selected_counts = [r["retrieval"]["selected_count"] for r in results
                       if r.get("retrieval") and r["retrieval"].get("selected_count") is not None]
    context_chars_list = [r["retrieval"]["context_chars"] for r in results
                          if r.get("retrieval") and r["retrieval"].get("context_chars") is not None]
    if selected_counts:
        summary["mean_selected_chunks"] = round(statistics.mean(selected_counts), 1)
        non_refused_counts = [
            c for r, c in zip(results, selected_counts)
            if r.get("retrieval", {}).get("selection_reason") != "refused"
        ]
        if non_refused_counts:
            summary["starvation_rate"] = round(
                sum(1 for c in non_refused_counts if c <= STARVATION_CHUNK_THRESHOLD)
                / len(non_refused_counts),
                3,
            )
    if context_chars_list:
        summary["p95_context_chars"] = round(
            statistics.quantiles(context_chars_list, n=20)[18]
            if len(context_chars_list) >= 20
            else max(context_chars_list)
        )

    # Recorte por prefixo `col-` (add-multi-query-retrieval-expansion) —
    # perguntas coloquiais/imprecisas, irmãs de perguntas `in_corpus`
    # existentes. Reportado à parte porque é exatamente a categoria que esta
    # change tenta melhorar; misturado na média geral (`mean_recall`) o
    # efeito ficaria diluído por 35+ perguntas que já tinham fraseado exato.
    col_results = [r for r in results if r["id"].startswith("col-")]
    if col_results:
        col_recalls = [r["retrieval"]["recall"] for r in col_results
                       if r.get("retrieval") and r["retrieval"]["recall"] is not None]
        col_top_sims = [r["retrieval"]["top_similarity"] for r in col_results if r.get("retrieval")]
        col_selected = [r["retrieval"]["selected_count"] for r in col_results
                        if r.get("retrieval") and r["retrieval"].get("selected_count") is not None]
        summary["col_questions_total"] = len(col_results)
        summary["col_mean_recall"] = round(statistics.mean(col_recalls), 3) if col_recalls else None
        summary["col_perfect_recall_rate"] = (
            round(sum(1 for r in col_recalls if r == 1.0) / len(col_recalls), 3)
            if col_recalls else None
        )
        summary["col_mean_top_similarity"] = (
            round(statistics.mean(col_top_sims), 3) if col_top_sims else None
        )
        if col_selected:
            summary["col_starvation_rate"] = round(
                sum(1 for c in col_selected if c <= STARVATION_CHUNK_THRESHOLD) / len(col_selected), 3
            )

    generated = [r for r in results if r.get("generation")]
    if generated:
        correct_refusals = [r["generation"]["refusal_correct"] for r in generated]
        summary["refusal_correct_rate"] = round(sum(correct_refusals) / len(correct_refusals), 3)

        oos_generated = [r for r in out_corpus if r.get("generation")]
        if oos_generated:
            summary["out_of_corpus_refusal_rate"] = round(
                sum(1 for r in oos_generated if r["generation"]["refused"]) / len(oos_generated), 3
            )

        grounds = [r["generation"].get("groundedness") for r in generated]
        grounds = [g for g in grounds if g is not None]
        if grounds:
            summary["mean_groundedness"] = round(statistics.mean(grounds), 1)

        # Distinto de groundedness por desenho — ver `build_usefulness_judge`.
        usefulness = [r["generation"].get("answers_question") for r in generated]
        usefulness = [u for u in usefulness if u is not None]
        if usefulness:
            summary["mean_answers_question"] = round(statistics.mean(usefulness), 1)

        coverages = [r["generation"].get("mention_coverage") for r in generated]
        coverages = [c for c in coverages if c is not None]
        if coverages:
            summary["mean_mention_coverage"] = round(statistics.mean(coverages), 3)

        # O sintoma que motivou o programa inteiro, como número: fração de
        # respostas não recusadas que são formalmente estruturadas mas
        # substantivamente vazias.
        non_refused = [r for r in generated if not r["generation"]["refused"]]
        if non_refused:
            skeletons = [r["generation"].get("skeleton", False) for r in non_refused]
            summary["skeleton_rate"] = round(sum(skeletons) / len(skeletons), 3)

            citation_counts = [r["generation"].get("citation_file_count") for r in non_refused]
            citation_counts = [c for c in citation_counts if c is not None]
            if citation_counts:
                summary["citation_file_count_mean"] = round(statistics.mean(citation_counts), 2)

            citation_precisions = [
                r["generation"].get("citation_precision") for r in non_refused
            ]
            citation_precisions = [c for c in citation_precisions if c is not None]
            if citation_precisions:
                summary["citation_precision"] = round(statistics.mean(citation_precisions), 3)

    return summary


def print_report(run: dict) -> None:
    print("\n" + "=" * 78)
    print(f"Execução: {run['run_id']}   modo: {run['mode']}")
    print("=" * 78)
    cfg = run["config"]
    print(f"  embedding      : {cfg['embedding_model']} (dims={cfg['embedding_dimensions']})")
    print(f"  chunk          : size={cfg['chunk_size']} overlap={cfg['chunk_overlap']}")
    print(f"  threshold      : {cfg['similarity_threshold']}   k={run['k']}")
    print(f"  llm            : generation={cfg.get('generation_model', cfg.get('llm_model'))} "
          f"utility={cfg.get('utility_model', '?')}")
    print("-" * 78)
    print(f"{'id':<26}{'recall':>8}{'top_sim':>9}{'rank':>6}{'recusa':>9}")
    print("-" * 78)
    for r in run["results"]:
        ret = r.get("retrieval") or {}
        gen = r.get("generation") or {}
        recall = ret.get("recall")
        recall_text = "—" if recall is None else f"{recall:.2f}"
        rank = ret.get("first_hit_rank")
        rank_text = "—" if rank is None else str(rank)
        if gen:
            refusal = "OK" if gen["refusal_correct"] else "FALHA"
        else:
            refusal = "—"
        print(f"{r['id']:<26}{recall_text:>8}{ret.get('top_similarity', 0):>9.3f}"
              f"{rank_text:>6}{refusal:>9}")

    print("-" * 78)
    for key, value in run["summary"].items():
        print(f"  {key:<28} {value}")

    cost = run.get("cost") or {}
    if cost:
        latencies = [
            (r.get("retrieval") or {}).get("retrieval_seconds", 0)
            + (r.get("generation") or {}).get("generation_seconds", 0)
            for r in run["results"]
        ]
        print(f"\n  custo LLM (USD)              {cost.get('llm_cost_usd')}"
              f"  em {cost.get('llm_calls')} chamadas")
        print(f"  embeddings (estimados)       {cost.get('embedding_calls_estimated')} chamadas")
        if latencies:
            print(f"  latência média/pergunta      {statistics.mean(latencies):.2f}s")
    misses = [(r["id"], p) for r in run["results"]
              for p in (r.get("retrieval") or {}).get("missed_passages", [])]
    if misses:
        print(f"\n  Trechos não recuperados ({len(misses)}):")
        for qid, passage in misses:
            print(f"    [{qid}] {passage[:70]}")
    print("=" * 78 + "\n")


def compare(path_a: Path, path_b: Path) -> None:
    run_a = json.loads(path_a.read_text(encoding="utf-8"))
    run_b = json.loads(path_b.read_text(encoding="utf-8"))

    print("\n" + "=" * 78)
    print(f"Comparação:  A={run_a['run_id']}   B={run_b['run_id']}")
    print("=" * 78)

    print("\nConfiguração:")
    # `retrieval_k`/`use_llm_expansion` já vêm dentro de `config` a partir
    # desta versão do harness; runs salvos por versões anteriores só têm
    # esses valores nos campos soltos `k`/`llm_expansion` no topo do run —
    # o `setdefault` cobre os dois casos sem duplicar a mesma informação
    # sob nomes diferentes quando `config` já é completo.
    def _with_legacy_fallback(run: dict) -> dict:
        config = dict(run["config"])
        config.setdefault("retrieval_k", run.get("k"))
        config.setdefault("use_llm_expansion", run.get("llm_expansion"))
        config["mode"] = run.get("mode")
        return config

    config_a = _with_legacy_fallback(run_a)
    config_b = _with_legacy_fallback(run_b)
    keys = sorted(set(config_a) | set(config_b))
    for key in keys:
        va, vb = config_a.get(key), config_b.get(key)
        marker = "  " if va == vb else "->"
        print(f" {marker} {key:<24} {va}  |  {vb}")

    print("\nMétricas:")
    keys = sorted(set(run_a["summary"]) | set(run_b["summary"]))
    for key in keys:
        va, vb = run_a["summary"].get(key), run_b["summary"].get(key)
        delta = ""
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            diff = vb - va
            delta = f"   ({diff:+.3f})" if diff else "   (=)"
        print(f"    {key:<28} {va}  |  {vb}{delta}")
    print("=" * 78 + "\n")


# ----------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="Avaliação de qualidade do RAG")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--retrieval-only", action="store_true",
                      help="Só métricas de recuperação (barato, determinístico)")
    mode.add_argument("--full", action="store_true",
                      help="Recuperação + geração + juiz de embasamento (caro)")
    mode.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"),
                      help="Compara duas execuções salvas")
    parser.add_argument("--k", type=int, default=20, help="Documentos recuperados (default: 20)")
    parser.add_argument("--no-llm-expansion", action="store_true",
                        help="Desliga a expansão de query por LLM (mais barato e determinístico)")
    parser.add_argument("--label", default="", help="Rótulo para identificar a execução")
    args = parser.parse_args()

    if args.compare:
        compare(Path(args.compare[0]), Path(args.compare[1]))
        return 0

    from app.services.rag_service import get_rag_service

    service = get_rag_service()
    spec = yaml.safe_load(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    questions = spec["questions"]
    use_llm_expansion = not args.no_llm_expansion
    judge = build_judge(service) if args.full else None
    usefulness_judge = build_usefulness_judge(service) if args.full else None

    print(f"Avaliando {len(questions)} perguntas "
          f"(modo={'full' if args.full else 'retrieval-only'}, k={args.k}, "
          f"expansão_llm={use_llm_expansion})...\n")

    results = []
    with get_openai_callback() as usage:
        for index, question in enumerate(questions, start=1):
            print(f"  [{index}/{len(questions)}] {question['id']}")
            entry = {
                "id": question["id"],
                "scope": question["scope"],
                "question_type": question.get("question_type"),
                "question": question["question"],
            }
            try:
                entry["retrieval"] = evaluate_retrieval(
                    service, question, args.k, use_llm_expansion
                )
                if args.full:
                    entry["generation"] = evaluate_generation(
                        service, question, judge, usefulness_judge
                    )
            except Exception as exc:  # noqa: BLE001
                entry["error"] = f"{type(exc).__name__}: {exc}"
                print(f"    [erro] {entry['error']}")
            results.append(entry)

    # O callback do LangChain contabiliza apenas chamadas de chat (geração,
    # expansão de query e juiz). Embeddings NÃO entram nesta conta — são
    # estimados à parte, pelo número de consultas embutidas.
    cost = {
        "llm_calls": usage.successful_requests,
        "llm_prompt_tokens": usage.prompt_tokens,
        "llm_completion_tokens": usage.completion_tokens,
        "llm_cost_usd": round(usage.total_cost, 4),
        "embedding_calls_estimated": estimate_embedding_calls(
            len(questions), use_llm_expansion, args.full
        ),
        "note": "Custo de embeddings não incluído (callback do LangChain cobre só chat).",
    }

    run = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "label": args.label,
        "mode": "full" if args.full else "retrieval-only",
        "k": args.k,
        "llm_expansion": use_llm_expansion,
        "golden_set_version": spec.get("version"),
        "config": capture_config(service, args.k, use_llm_expansion),
        "cost": cost,
        "results": results,
        "summary": summarize(results),
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.label}" if args.label else ""
    output = RUNS_DIR / f"{run['run_id']}{suffix}.json"
    output.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

    print_report(run)
    print(f"Salvo em: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
