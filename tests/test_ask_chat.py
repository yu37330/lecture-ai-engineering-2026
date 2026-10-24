"""第1回宿題の単発・継続会話・トークン表示の動作確認（API呼び出しなし）。"""

from types import SimpleNamespace

from app import ask as ask_module


def test_single_turn_keeps_existing_behavior_and_prints_tokens(monkeypatch, capsys):
    """単発質問はgenerate_contentを使い、モデルに履歴を渡さない。"""
    response = SimpleNamespace(
        text="LoRAの説明",
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=34),
    )
    calls = []

    class FakeModels:
        def generate_content(self, *, model, contents):
            calls.append((model, contents))
            return response

    monkeypatch.setattr(ask_module, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(
        ask_module.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(models=FakeModels()),
    )

    assert ask_module.ask("LoRAとは？") == "LoRAの説明"
    assert calls == [(ask_module.MODEL, "LoRAとは？")]
    assert "入力: 12 / 出力: 34" in capsys.readouterr().out


def test_chat_uses_one_session_for_multiple_questions(monkeypatch, capsys):
    """継続質問は同じchatインスタンスへ順に送る。"""
    messages = []
    created = []

    class FakeChat:
        def send_message(self, question):
            messages.append(question)
            return SimpleNamespace(
                text=f"回答{len(messages)}",
                usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=5),
            )

    class FakeChats:
        def create(self, *, model):
            created.append(model)
            return FakeChat()

    monkeypatch.setattr(ask_module, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(
        ask_module.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(chats=FakeChats()),
    )
    answers = iter(["さっきの質問を覚えていますか？", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    ask_module.run_chat("私の名前は田中です")
    output = capsys.readouterr().out

    assert created == [ask_module.MODEL]
    assert messages == ["私の名前は田中です", "さっきの質問を覚えていますか？"]
    assert "Gemini> 回答1" in output
    assert "Gemini> 回答2" in output
    assert output.count("入力: 10 / 出力: 5") == 2


def test_chat_ignores_blank_and_exits_without_api_call(monkeypatch):
    messages = []

    class FakeChat:
        def send_message(self, question):
            messages.append(question)
            return SimpleNamespace(text="OK", usage_metadata=None)

    monkeypatch.setattr(ask_module, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(
        ask_module.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(
            chats=SimpleNamespace(create=lambda **kwargs: FakeChat())
        ),
    )
    answers = iter(["  ", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    ask_module.run_chat()
    assert messages == []


def test_missing_usage_metadata_is_not_fabricated(capsys):
    ask_module.print_token_usage(SimpleNamespace(usage_metadata=None))
    assert "入力: 計測不可 / 出力: 計測不可" in capsys.readouterr().out
