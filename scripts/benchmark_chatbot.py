#!/usr/bin/env python3
"""Benchmark the Neo4j RAG chatbot against a JSON QA dataset."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

from chatbot_neo4j import DEFAULT_GROQ_CHAT_MODEL, answer_question
from query_neo4j import retrieve

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def tokens(value: str | None) -> list[str]:
    return normalize_text(value).split()


def token_f1(prediction: str | None, gold: str | None) -> float:
    pred_tokens = tokens(prediction)
    gold_tokens = tokens(gold)
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    gold_counts: dict[str, int] = {}
    for token in gold_tokens:
        gold_counts[token] = gold_counts.get(token, 0) + 1
    overlap = 0
    for token in pred_tokens:
        count = gold_counts.get(token, 0)
        if count > 0:
            overlap += 1
            gold_counts[token] = count - 1
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def cosine_similarity(left: list[float], right: list[float]) -> float | None:
    if not left or not right or len(left) != len(right):
        return None
    dot = sum(x * y for x, y in zip(left, right))
    left_norm = math.sqrt(sum(x * x for x in left))
    right_norm = math.sqrt(sum(y * y for y in right))
    if not left_norm or not right_norm:
        return None
    return dot / (left_norm * right_norm)


def embed_texts_for_eval(args: argparse.Namespace, texts: list[str]) -> list[list[float]]:
    if OpenAI is None:
        raise RuntimeError("Install openai package to use semantic answer evaluation.")
    api_key = (
        args.semantic_embedding_api_key
        or args.embedding_api_key
        or os.getenv("OPENAI_EMBEDDING_API_KEY")
        or os.getenv("EMBEDDING_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "Set OPENAI_EMBEDDING_API_KEY/EMBEDDING_API_KEY, pass --embedding-api-key, "
            "or pass --semantic-embedding-api-key to use --semantic-answer."
        )
    base_url = (
        args.semantic_embedding_base_url
        or args.embedding_base_url
        or os.getenv("OPENAI_EMBEDDING_BASE_URL")
        or os.getenv("EMBEDDING_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
    )
    model = args.semantic_embedding_model or args.embedding_model
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def answer_semantic_similarity(args: argparse.Namespace, prediction: str | None, gold: str | None) -> float | None:
    if not prediction or not gold:
        return None
    vectors = embed_texts_for_eval(args, [prediction, gold])
    if len(vectors) != 2:
        return None
    return cosine_similarity(vectors[0], vectors[1])


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("LLM judge response is not a JSON object.")
    return payload


def clamp_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(5.0, score))


def llm_judge(args: argparse.Namespace, item: dict[str, Any], answer: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("Install openai package to use LLM judge evaluation.")
    api_key = args.judge_api_key or os.getenv("JUDGE_API_KEY")
    if not api_key:
        raise RuntimeError("Set JUDGE_API_KEY or pass --judge-api-key to use --llm-judge.")
    client = OpenAI(api_key=api_key, base_url=args.judge_base_url) if args.judge_base_url else OpenAI(api_key=api_key)
    retrieved_context = chunks_text(chunks)
    if args.judge_max_context_chars and len(retrieved_context) > args.judge_max_context_chars:
        retrieved_context = retrieved_context[: args.judge_max_context_chars]
    reference = item.get("reference") or ""
    if args.judge_max_reference_chars and len(reference) > args.judge_max_reference_chars:
        reference = reference[: args.judge_max_reference_chars]

    prompt = f"""Bạn là giám khảo đánh giá chatbot hỏi đáp tiếng Việt.

Chấm câu trả lời của chatbot dựa trên câu hỏi, câu trả lời chuẩn, tài liệu tham chiếu và context đã retrieve.

Rubric điểm 0-5:
5 = đúng đầy đủ, không thiếu ý quan trọng
4 = đúng phần lớn, chỉ thiếu chi tiết nhỏ
3 = đúng một phần, thiếu ý quan trọng
2 = có liên quan nhưng sai hoặc thiếu nhiều
1 = hầu như sai
0 = không trả lời hoặc hoàn toàn sai

Yêu cầu:
- correctness_score: độ đúng so với câu trả lời chuẩn và tài liệu tham chiếu.
- faithfulness_score: câu trả lời có được hỗ trợ bởi tài liệu/context hay không, không bịa.
- completeness_score: câu trả lời có đủ ý cần thiết cho câu hỏi hay không.
- label: một trong correct, mostly_correct, partially_correct, wrong, unsupported.
- reason: giải thích ngắn bằng tiếng Việt.

Chỉ trả về JSON hợp lệ, không thêm markdown.

CÂU HỎI:
{item.get("question") or ""}

CÂU TRẢ LỜI CHUẨN:
{item.get("answer") or ""}

TÀI LIỆU THAM CHIẾU:
{reference}

CONTEXT RETRIEVE ĐƯỢC:
{retrieved_context}

CÂU TRẢ LỜI CHATBOT:
{answer}

JSON cần trả về:
{{
  "correctness_score": 0,
  "faithfulness_score": 0,
  "completeness_score": 0,
  "label": "wrong",
  "reason": "..."
}}
"""

    last_error: Exception | None = None
    for attempt in range(args.judge_retries + 1):
        try:
            response = client.chat.completions.create(
                model=args.judge_model,
                temperature=args.judge_temperature,
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là giám khảo nghiêm khắc. Chỉ trả về JSON hợp lệ.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw = response.choices[0].message.content or "{}"
            payload = parse_json_object(raw)
            return {
                "correctness_score": clamp_score(payload.get("correctness_score")),
                "faithfulness_score": clamp_score(payload.get("faithfulness_score")),
                "completeness_score": clamp_score(payload.get("completeness_score")),
                "label": str(payload.get("label") or ""),
                "reason": str(payload.get("reason") or ""),
                "raw": payload,
            }
        except Exception as exc:
            last_error = exc
            if attempt >= args.judge_retries:
                break
            time.sleep(args.judge_retry_sleep)
    raise RuntimeError(f"LLM judge failed: {last_error}")


def exact_match(prediction: str | None, gold: str | None) -> float:
    return 1.0 if normalize_text(prediction) == normalize_text(gold) else 0.0


def max_reference_chunk_f1(reference: str | None, chunks: list[dict[str, Any]]) -> float:
    if not reference or not chunks:
        return 0.0
    return max(token_f1(chunk.get("content"), reference) for chunk in chunks)


def chunks_text(chunks: list[dict[str, Any]]) -> str:
    return "\n".join(str(chunk.get("content") or "") for chunk in chunks)


def answer_context_f1(answer: str | None, chunks: list[dict[str, Any]]) -> float | None:
    if not answer:
        return None
    context = chunks_text(chunks)
    if not context:
        return 0.0
    return token_f1(answer, context)


def mean_metric(results: list[dict[str, Any]], key: str) -> float | None:
    values = [item.get(key) for item in results if not item.get("error") and item.get(key) is not None]
    if not values:
        return None
    return statistics.fmean(float(value) for value in values)


def load_dataset(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return [item for item in data if isinstance(item, dict) and item.get("question")]


def filter_dataset(data: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = data
    if args.domain:
        rows = [item for item in rows if item.get("domain") == args.domain]
    if args.question_type:
        rows = [item for item in rows if item.get("question_type") == args.question_type]
    if args.topic:
        rows = [item for item in rows if args.topic in (item.get("topic") or [])]
    if args.offset:
        rows = rows[args.offset :]
    if args.limit is not None:
        rows = rows[: args.limit]
    return rows


def build_common_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        uri=args.uri,
        user=args.user,
        password=args.password,
        database=args.database,
        api_key=args.api_key,
        base_url=args.base_url,
        chat_model=args.chat_model,
        embedding_model=args.embedding_model,
        embedding_api_key=args.embedding_api_key,
        embedding_base_url=args.embedding_base_url,
        es_url=args.es_url,
        es_user=args.es_user,
        es_password=args.es_password,
        es_api_key=args.es_api_key,
        es_ca_certs=args.es_ca_certs,
        es_chunks_index=args.es_chunks_index,
        es_num_candidates=args.es_num_candidates,
        entity_k=args.entity_k,
        chunk_k=args.chunk_k,
        relation_k=args.relation_k,
        relations_per_entity=args.relations_per_entity,
        graph_hops=args.graph_hops,
        no_vector=args.no_vector,
        no_es=args.no_es or args.no_vector,
        neo4j_vector=args.neo4j_vector,
        max_context_chars=args.max_context_chars,
        chunk_char_limit=args.chunk_char_limit,
        history_turns=0,
        retrieval_history_turns=0,
        temperature=args.temperature,
        show_sources=False,
        json=False,
    )


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [item for item in results if not item.get("error")]
    latencies = [float(item["latency_seconds"]) for item in completed]
    return {
        "total": len(results),
        "completed": len(completed),
        "errors": len(results) - len(completed),
        "answer_token_f1": mean_metric(results, "answer_token_f1"),
        "answer_semantic_similarity": mean_metric(results, "answer_semantic_similarity"),
        "llm_correctness_score": mean_metric(results, "llm_correctness_score"),
        "llm_faithfulness_score": mean_metric(results, "llm_faithfulness_score"),
        "llm_completeness_score": mean_metric(results, "llm_completeness_score"),
        "answer_context_f1": mean_metric(results, "answer_context_f1"),
        "reference_chunk_f1": mean_metric(results, "reference_chunk_f1"),
        "avg_latency_seconds": statistics.fmean(latencies) if latencies else 0.0,
    }


def ranked_retrieval_cases(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    completed = [item for item in results if not item.get("error")]
    ranked = sorted(completed, key=lambda item: float(item.get("reference_chunk_f1") or 0.0), reverse=True)

    def compact(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "question": item.get("question"),
            "answer": item.get("gold_answer"),
            "reference": item.get("reference"),
            "multi_intent": item.get("multi_intent"),
            "insufficient_context": item.get("insufficient_context"),
            "reasoning_level": item.get("reasoning_level"),
            "topic": item.get("topic"),
            "question_type": item.get("question_type"),
            "domain": item.get("domain"),
            "metrics": {
                "reference_chunk_f1": item.get("reference_chunk_f1"),
                "answer_token_f1": item.get("answer_token_f1"),
                "answer_context_f1": item.get("answer_context_f1"),
                "answer_semantic_similarity": item.get("answer_semantic_similarity"),
                "llm_correctness_score": item.get("llm_correctness_score"),
                "llm_faithfulness_score": item.get("llm_faithfulness_score"),
                "llm_completeness_score": item.get("llm_completeness_score"),
                "llm_judge_label": item.get("llm_judge_label"),
                "latency_seconds": item.get("latency_seconds"),
            },
        }

    return {"retrieval_ranking": [compact(item) for item in ranked]}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_results_jsonl(path: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            item = json.loads(text)
            if not isinstance(item, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}")
            results.append(item)
    return results


def summarize_results_file(results_path: Path, summary_path: Path) -> int:
    results = load_results_jsonl(results_path)
    summary = {
        **summarize(results),
        **ranked_retrieval_cases(results),
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Results: {results_path}")
    print(f"Summary: {summary_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="1k_test_tvst-dao_tao.json")
    parser.add_argument("--output-dir", default="benchmarks")
    parser.add_argument("--run-name", default=time.strftime("chatbot_%Y%m%d_%H%M%S"))
    parser.add_argument("--summarize-results", default=None, help="Create summary.json from an existing results.jsonl file.")
    parser.add_argument("--summary-output", default=None, help="Output path for --summarize-results. Defaults to summary.json next to results.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--domain", default=None)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--question-type", default=None)
    parser.add_argument("--retrieval-only", action="store_true", help="Skip LLM calls and benchmark retrieval only.")
    parser.add_argument("--sleep-between", type=float, default=0.0, help="Seconds to sleep between benchmark rows.")
    parser.add_argument("--llm-retries", type=int, default=0, help="Retries for LLM calls after an error.")
    parser.add_argument("--llm-retry-sleep", type=float, default=60.0, help="Seconds to sleep before retrying LLM calls.")
    parser.add_argument("--semantic-answer", action="store_true", help="Evaluate answer semantic similarity with embeddings.")
    parser.add_argument("--semantic-embedding-model", default=None)
    parser.add_argument("--semantic-embedding-api-key", default=None)
    parser.add_argument("--semantic-embedding-base-url", default=None)
    parser.add_argument("--llm-judge", action="store_true", help="Use another LLM to judge answer correctness/faithfulness/completeness.")
    parser.add_argument("--judge-api-key", default=os.getenv("JUDGE_API_KEY"))
    parser.add_argument("--judge-base-url", default=os.getenv("JUDGE_BASE_URL"))
    parser.add_argument("--judge-model", default=os.getenv("JUDGE_MODEL", "gpt-4o-mini"))
    parser.add_argument("--judge-temperature", type=float, default=0.0)
    parser.add_argument("--judge-retries", type=int, default=1)
    parser.add_argument("--judge-retry-sleep", type=float, default=30.0)
    parser.add_argument("--judge-max-reference-chars", type=int, default=6000)
    parser.add_argument("--judge-max-context-chars", type=int, default=6000)

    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))

    parser.add_argument("--api-key", default=os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--base-url", default=os.getenv("GROQ_CHAT_BASE_URL") or os.getenv("GROQ_BASE_URL"))
    parser.add_argument("--chat-model", default=os.getenv("GROQ_CHAT_MODEL") or DEFAULT_GROQ_CHAT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.0)

    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    parser.add_argument("--embedding-api-key", default=os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_EMBEDDING_API_KEY"))
    parser.add_argument("--embedding-base-url", default=os.getenv("EMBEDDING_BASE_URL") or os.getenv("OPENAI_EMBEDDING_BASE_URL"))
    parser.add_argument("--es-url", default=os.getenv("ELASTICSEARCH_URL"))
    parser.add_argument("--es-user", default=os.getenv("ELASTICSEARCH_USER"))
    parser.add_argument("--es-password", default=os.getenv("ELASTICSEARCH_PASSWORD"))
    parser.add_argument("--es-api-key", default=os.getenv("ELASTICSEARCH_API_KEY"))
    parser.add_argument("--es-ca-certs", default=os.getenv("ELASTICSEARCH_CA_CERTS"))
    parser.add_argument("--es-chunks-index", default=os.getenv("ES_CHUNKS_INDEX", "uet_kg_chunks"))
    parser.add_argument("--es-num-candidates", type=int, default=None)
    parser.add_argument("--no-vector", action="store_true")
    parser.add_argument("--no-es", action="store_true")
    parser.add_argument("--neo4j-vector", action="store_true")

    parser.add_argument("--entity-k", type=int, default=8)
    parser.add_argument("--chunk-k", type=int, default=8)
    parser.add_argument("--relation-k", type=int, default=20)
    parser.add_argument("--relations-per-entity", type=int, default=5)
    parser.add_argument("--graph-hops", type=int, default=2)
    parser.add_argument("--max-context-chars", type=int, default=12000)
    parser.add_argument("--chunk-char-limit", type=int, default=1200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.summarize_results:
        results_path = Path(args.summarize_results)
        summary_path = Path(args.summary_output) if args.summary_output else results_path.with_name("summary.json")
        return summarize_results_file(results_path, summary_path)

    if not args.password:
        raise SystemExit("Set NEO4J_PASSWORD or pass --password.")
    if not args.retrieval_only and not args.api_key:
        raise SystemExit("Set GROQ_API_KEY/OPENAI_API_KEY, pass --api-key, or use --retrieval-only.")
    if args.llm_judge and args.retrieval_only:
        raise SystemExit("--llm-judge requires chatbot answers, so do not use it with --retrieval-only.")
    if args.llm_judge and not args.judge_api_key:
        raise SystemExit("Set JUDGE_API_KEY or pass --judge-api-key to use --llm-judge.")

    rows = filter_dataset(load_dataset(Path(args.dataset)), args)
    if not rows:
        raise SystemExit("No benchmark rows matched the selected filters.")

    run_dir = Path(args.output_dir) / args.run_name
    results_path = run_dir / "results.jsonl"
    summary_path = run_dir / "summary.json"
    common_args = build_common_args(args)
    results: list[dict[str, Any]] = []

    run_dir.mkdir(parents=True, exist_ok=True)
    with results_path.open("w", encoding="utf-8") as f:
        for index, item in enumerate(rows, start=1):
            if index > 1 and args.sleep_between > 0:
                time.sleep(args.sleep_between)
            started = time.perf_counter()
            result: dict[str, Any] = {
                "id": item.get("id"),
                "question": item.get("question"),
                "gold_answer": item.get("answer"),
                "reference": item.get("reference"),
                "multi_intent": item.get("multi_intent"),
                "insufficient_context": item.get("insufficient_context"),
                "reasoning_level": item.get("reasoning_level"),
                "domain": item.get("domain"),
                "topic": item.get("topic"),
                "question_type": item.get("question_type"),
            }
            try:
                if args.retrieval_only:
                    retrieval_args = argparse.Namespace(**vars(common_args), query=item["question"])
                    retrieval = retrieve(retrieval_args)
                    answer = ""
                    sources: list[dict[str, Any]] = []
                else:
                    for attempt in range(args.llm_retries + 1):
                        try:
                            payload = answer_question(common_args, item["question"])
                            break
                        except Exception:
                            if attempt >= args.llm_retries:
                                raise
                            time.sleep(args.llm_retry_sleep)
                    answer = payload.get("answer") or ""
                    sources = payload.get("sources") or []
                    retrieval = payload.get("retrieval") or {}
                chunks = retrieval.get("chunks") or []
                result.update(
                    {
                        "answer": answer,
                        "sources": sources,
                        "retrieval": {
                            "embedding_created": retrieval.get("embedding_created"),
                            "vector_used": retrieval.get("vector_used"),
                            "vector_db": retrieval.get("vector_db"),
                            "semantic_chunk_count": retrieval.get("semantic_chunk_count"),
                            "neo4j_vector_chunk_count": retrieval.get("neo4j_vector_chunk_count"),
                            "neo4j_vector_entity_count": retrieval.get("neo4j_vector_entity_count"),
                            "entity_count": len(retrieval.get("entities") or []),
                            "relation_count": len(retrieval.get("relations") or []),
                            "chunk_count": len(chunks),
                            "warnings": retrieval.get("warnings") or [],
                        },
                        "answer_exact_match": exact_match(answer, item.get("answer")) if not args.retrieval_only else 0.0,
                        "answer_token_f1": token_f1(answer, item.get("answer")) if not args.retrieval_only else None,
                        "answer_semantic_similarity": (
                            answer_semantic_similarity(args, answer, item.get("answer"))
                            if args.semantic_answer and not args.retrieval_only
                            else None
                        ),
                        "answer_context_f1": answer_context_f1(answer, chunks),
                        "reference_chunk_f1": max_reference_chunk_f1(item.get("reference"), chunks),
                    }
                )
                if args.llm_judge and not args.retrieval_only:
                    judge = llm_judge(args, item, answer, chunks)
                    result.update(
                        {
                            "llm_correctness_score": judge.get("correctness_score"),
                            "llm_faithfulness_score": judge.get("faithfulness_score"),
                            "llm_completeness_score": judge.get("completeness_score"),
                            "llm_judge_label": judge.get("label"),
                            "llm_judge_reason": judge.get("reason"),
                            "llm_judge_raw": judge.get("raw"),
                        }
                    )
            except Exception as exc:
                result["error"] = str(exc)
            result["latency_seconds"] = round(time.perf_counter() - started, 3)
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
            results.append(result)
            status = "ERR" if result.get("error") else "OK"
            print(f"[{index}/{len(rows)}] {status} {item.get('id')} {result['latency_seconds']}s")

    summary = {
        **summarize(results),
        **ranked_retrieval_cases(results),
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Results: {results_path}")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
