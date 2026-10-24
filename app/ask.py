"""第1回: Gemini APIを使った単発質問と会話履歴つきチャット。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask                 # 単発の既定質問
    uv run python -m app.ask --chat          # 会話履歴を保った対話
    uv run python -m app.ask --chat "私は田中です"  # 最初の質問を指定

対話モードでは、同じchatセッションを利用して会話履歴を引き継ぐ。
終了するには /exit または /quit を入力する。
"""

import argparse

from google import genai
from google.genai import errors

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


def print_token_usage(response: object) -> None:
    """応答に含まれる入力・出力トークン数を表示する。未提供時は推測しない。"""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        print("[tokens] 入力: 計測不可 / 出力: 計測不可")
        return

    input_tokens = getattr(usage, "prompt_token_count", None)
    output_tokens = getattr(usage, "candidates_token_count", None)
    input_label = str(input_tokens) if input_tokens is not None else "計測不可"
    output_label = str(output_tokens) if output_tokens is not None else "計測不可"
    print(f"[tokens] 入力: {input_label} / 出力: {output_label}")


def ask(question: str) -> str:
    """従来どおり、履歴を使わず単発の質問に回答する。"""
    client = genai.Client(api_key=get_api_key())
    response = client.models.generate_content(model=MODEL, contents=question)
    print_token_usage(response)
    return response.text or "（テキスト応答なし）"


def run_chat(initial_question: str | None = None) -> None:
    """1つのチャットセッションで繰り返し質問する（プロセス終了まで履歴保持）。"""
    client = genai.Client(api_key=get_api_key())
    chat = client.chats.create(model=MODEL)
    print("会話モードです。/exit または /quit で終了します。")

    next_question = initial_question
    while True:
        try:
            question = next_question if next_question is not None else input("あなた> ")
        except (EOFError, KeyboardInterrupt):
            print("\n会話を終了します。")
            break
        next_question = None
        question = question.strip()

        if question.lower() in {"/exit", "/quit"}:
            print("会話を終了します。")
            break
        if not question:
            continue

        response = chat.send_message(question)
        print(f"Gemini> {response.text or '（テキスト応答なし）'}")
        print_token_usage(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Geminiに質問する")
    parser.add_argument("question", nargs="?", default=None)
    parser.add_argument("--chat", action="store_true", help="会話履歴を保って質問を続ける")
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    try:
        if args.chat:
            run_chat(args.question)
        else:
            question = args.question or DEFAULT_QUESTION
            print(f"[質問] {question}\n")
            print(ask(question))
    except errors.APIError as e:
        print(api_error_message(e.code, e.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
