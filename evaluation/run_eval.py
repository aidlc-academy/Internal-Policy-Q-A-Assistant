# evaluation/run_eval.py
"""
Evaluation script for the Policy Q&A system.

Reads questions.json, calls /ask endpoint, logs results to eval_results.json

Usage:
    python evaluation/run_eval.py
"""

import json
import httpx
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")
QUESTIONS_FILE = Path("evaluation/questions.json")
RESULTS_FILE = Path("evaluation/eval_results.json")


def run_evaluation():
    """Run all evaluation questions and save results."""
    if not QUESTIONS_FILE.exists():
        print(f"Error: {QUESTIONS_FILE} not found")
        return

    with QUESTIONS_FILE.open("r", encoding="utf-8") as f:
        questions = json.load(f)

    results = []
    print(f"Running evaluation on {len(questions)} questions...\n")

    for q in questions:
        print(f"Q{q['id']}: {q['question'][:80]}...")
        
        try:
            response = httpx.post(
                f"{API_URL}/ask",
                json={"question": q["question"]},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            # Check if expected phrases are in answer
            answer_lower = data.get("answer", "").lower()
            expected_phrases = [p.lower() for p in q.get("expected_answer_contains", [])]
            phrases_found = [p for p in expected_phrases if p in answer_lower]

            # Check if expected pages are in sources
            source_pages = [s["page"] for s in data.get("sources", [])]
            expected_pages = q.get("expected_source_pages", [])
            pages_matched = [p for p in expected_pages if p in source_pages]

            result = {
                "question_id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "status": data.get("status"),
                "answer": data.get("answer"),
                "sources": data.get("sources", []),
                "conflict_warning": data.get("conflict_warning"),
                "expected_phrases_found": phrases_found,
                "expected_phrases_missing": [p for p in expected_phrases if p not in phrases_found],
                "expected_pages_matched": pages_matched,
                "expected_pages_missing": [p for p in expected_pages if p not in source_pages],
                "verdict": "PASS" if (phrases_found or not expected_phrases) and (pages_matched or not expected_pages) else "CHECK",
            }
            results.append(result)
            print(f"  Status: {data.get('status')} | Verdict: {result['verdict']}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "question_id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "error": str(e),
                "verdict": "ERROR",
            })

    # Save results
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Evaluation complete. Results saved to {RESULTS_FILE}")
    print(f"{'='*60}\n")

    # Summary
    pass_count = sum(1 for r in results if r.get("verdict") == "PASS")
    check_count = sum(1 for r in results if r.get("verdict") == "CHECK")
    error_count = sum(1 for r in results if r.get("verdict") == "ERROR")
    
    print(f"PASS:  {pass_count}/{len(results)}")
    print(f"CHECK: {check_count}/{len(results)}")
    print(f"ERROR: {error_count}/{len(results)}")


if __name__ == "__main__":
    run_evaluation()
