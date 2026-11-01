"""第2回・発展課題の学習データ、評価質問、単純検索ベースラインを作る。

使い方: uv run python scripts/lec02_glossary_prepare.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "data" / "glossary.json"
OUTPUT = ROOT / "lectures" / "02" / "glossary_experiment"

# 学習用の質問テンプレートとは重複しない評価専用質問
CASES = [
    ("direct", "LoRAの定義を教えてください。", "lora"),
    ("direct", "MCPの概要を教えてください。", "mcp"),
    ("direct", "過学習とは何ですか？", "overfitting"),
    ("alias", "Low-Rank Adaptationの意味を教えてください。", "lora"),
    ("alias", "Model Context Protocolとは何ですか？", "mcp"),
    ("alias", "オーバーフィッティングの意味は？", "overfitting"),
    ("paraphrase", "基盤モデルを固定して低ランクの追加行列だけ学習する手法は何ですか？", "lora"),
    ("paraphrase", "学習データに過度に適合して未知のデータで性能が落ちる現象は何ですか？", "overfitting"),
    ("paraphrase", "LLMと外部ツールやデータを接続するための共通規格は何ですか？", "mcp"),
    ("unknown", "DPOとは何ですか？", None),
    ("unknown", "GRPOとは何ですか？", None),
    ("unknown", "RAPTOR検索とは何ですか？", None),
]


def normalize(text: str) -> str:
    """空白と大文字小文字の揺れだけを吸収する。意味検索ではない。"""
    return re.sub(r"\s+", "", text).casefold()


def lexical_lookup(question: str, terms: list[dict]) -> dict | None:
    """用語名・別名の文字列一致だけで検索する簡易ベースライン。"""
    q = normalize(question)
    matches: list[tuple[int, str, dict]] = []
    for term in terms:
        for name in [term["term"], *term.get("aliases", [])]:
            value = normalize(name)
            if len(value) < 3:  # 短い別名は部分一致の誤検知が多い
                continue
            if value in q:
                matches.append((len(value), term["id"], term))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    return matches[0][2]


def dump(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    terms = json.loads(GLOSSARY.read_text(encoding="utf-8"))["terms"]
    by_id = {term["id"]: term for term in terms}
    assert len(by_id) == len(terms), "用語IDが重複しています"
    assert all(term_id is None or term_id in by_id for _, _, term_id in CASES)

    # 公式のデータ生成スクリプトをそのまま呼び出す
    script = ROOT / "scripts" / "make_sft_dataset.py"
    proc = subprocess.run([sys.executable, str(script)], check=True, capture_output=True, text=True)
    training = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    train_questions = [row["messages"][0]["content"] for row in training]
    eval_questions = [question for _, question, _ in CASES]
    assert len(train_questions) == len(set(train_questions))
    assert not (set(train_questions) & set(eval_questions)), "学習と評価で質問が重複しています"
    (OUTPUT / "glossary_sft.jsonl").write_text(proc.stdout, encoding="utf-8")

    evaluation = []
    baseline = []
    for i, (kind, question, gold_id) in enumerate(CASES, 1):
        gold_term = by_id.get(gold_id)
        evaluation.append({
            "id": i,
            "category": kind,
            "question": question,
            "expected_term_id": gold_id,
            "gold_definition": gold_term["definition"] if gold_term else None,
            "expected_behavior": "用語集にないことを明示" if gold_id is None else "用語集の定義と矛盾しない説明",
        })
        match = lexical_lookup(question, terms)
        prediction = match["id"] if match else None
        baseline.append({
            "id": i,
            "category": kind,
            "question": question,
            "expected_term_id": gold_id,
            "predicted_term_id": prediction,
            "answer": match["definition"] if match else "用語集には記載がありません。",
            "correct": prediction == gold_id,
        })
    dump(OUTPUT / "glossary_eval.json", evaluation)
    dump(OUTPUT / "lexical_baseline.json", baseline)
    print(f"用語: {len(terms)}、学習行: {len(training)}、評価: {len(CASES)}")
    for category in ("direct", "alias", "paraphrase", "unknown"):
        subset = [row for row in baseline if row["category"] == category]
        print(f"{category}: {sum(row['correct'] for row in subset)}/{len(subset)}")
    print("生成先:", OUTPUT)
    print("注意: 単純辞書検索はEmbedding RAGではありません。")


if __name__ == "__main__":
    main()
