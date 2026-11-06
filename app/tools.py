"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import random
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from uuid import uuid4

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEARNING_LOG_DIR = DATA_DIR.parent / "learning_log"
MAX_RESULTS = 3


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定した回の用語集から確認問題を1問選び、問題と正解を返す。

    講義の復習や理解度確認を頼まれたときに使う。lecture は1始まりの回番号。
    answer は採点用なので、出題時には question だけを見せ、回答後に説明する。
    """
    candidates = [entry for entry in load_glossary() if entry["lecture"] == lecture]
    if not candidates:
        return json.dumps(
            {"error": f"第{lecture}回の用語が見つかりません。別の回を指定してください。"},
            ensure_ascii=False,
        )

    entry = random.choice(candidates)
    return json.dumps(
        {
            "question": f"「{entry['term']}」とは何ですか？",
            "answer": entry["definition"],
        },
        ensure_ascii=False,
    )


def save_learning_log(lecture: int, content: str) -> str:
    """ユーザーが承認した学習内容を、講義回とともに新しいJSONファイルへ保存する。

    学習内容の記録を頼まれたときに使う。lecture は1始まりの回番号、content は
    保存する本文。エージェントの承認確認を通過してから実行すること。
    保存先はリポジトリ直下の learning_log/ に固定し、保存先の指定は受け付けない。
    """
    if lecture <= 0:
        return json.dumps(
            {"saved": False, "path": None, "message": "回番号は1以上の整数で指定してください。"},
            ensure_ascii=False,
        )
    if not content.strip():
        return json.dumps(
            {"saved": False, "path": None, "message": "学習記録の本文が空です。保存する内容を指定してください。"},
            ensure_ascii=False,
        )

    saved_at = datetime.now(timezone.utc)
    filename = f"lec{lecture:02d}_{saved_at.strftime('%Y%m%dT%H%M%S%fZ')}_{uuid4().hex}.json"
    path = LEARNING_LOG_DIR / filename
    record = {"lecture": lecture, "content": content, "saved_at": saved_at.isoformat()}
    LEARNING_LOG_DIR.mkdir(parents=True, exist_ok=True)
    # 排他的な新規作成により、万一同じ名前が生成されても既存の記録を上書きしない。
    with path.open("x", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return json.dumps({"saved": True, "path": str(path)}, ensure_ascii=False)
