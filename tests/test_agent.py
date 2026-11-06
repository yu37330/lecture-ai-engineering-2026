"""エージェントの配線テスト。

TestModel は実際のLLMを呼ばない偽モデルで、登録されたツールを全部呼んでから
ダミーの回答を返す。APIキーも利用枠も使わずに、
「ツールが登録され、呼ばれ、結果がモデルに戻るか」を確かめられる。
"""

import json

import pytest
from pydantic_ai import DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent, print_tools, run_with_approval

BASE_TOOLS = {"search_glossary", "get_lecture_summary"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


def test_base_tools_are_registered_and_called():
    model = TestModel()
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered  # 演習でツールを足しても壊れないよう「含む」で判定

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    # 承認が必要なツール（requires_approval=True）は、実行されずに承認待ちになるので戻り値が無い
    waiting = len(result.output.approvals) if isinstance(result.output, DeferredToolRequests) else 0
    assert len(_parts(result, ToolReturnPart)) + waiting == len(_parts(result, ToolCallPart))
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


def _saving_model(contents):
    """実APIを呼ばず、指定内容の保存を1回だけ要求するモデルを作る。"""
    def respond(messages, info):
        returned = [
            part for message in messages for part in message.parts
            if isinstance(part, ToolReturnPart) and part.tool_name == "save_learning_log"
        ]
        if returned:
            return ModelResponse(parts=[TextPart("保存処理の結果を受け取りました。")])
        return ModelResponse(parts=[
            ToolCallPart(
                "save_learning_log",
                {"lecture": 3, "content": content},
                tool_call_id=f"save-{index}",
            )
            for index, content in enumerate(contents)
        ])

    return FunctionModel(respond)


def test_save_is_deferred_until_approval(tmp_path, monkeypatch):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    model = _saving_model(["モデルは実行を依頼し、プログラムがツールを動かす。"])

    pending = agent.run_sync("第3回の学習内容を保存して", model=model)
    assert isinstance(pending.output, DeferredToolRequests)
    assert len(pending.output.approvals) == 1
    assert not log_dir.exists()  # 承認前にはフォルダもファイルも作らない。

    call = pending.output.approvals[0]
    result = agent.run_sync(
        model=model,
        message_history=pending.all_messages(),
        deferred_tool_results=DeferredToolResults(approvals={call.tool_call_id: True}),
    )
    files = list(log_dir.glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text(encoding="utf-8"))["content"] == call.args_as_dict()["content"]
    assert isinstance(result.output, str)


@pytest.mark.parametrize("answer", ["n", ""])
def test_cli_denial_does_not_write(tmp_path, monkeypatch, answer):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    monkeypatch.setattr("builtins.input", lambda prompt: answer)

    result = run_with_approval(agent, "保存して", _saving_model(["保存を拒否する記録"]))
    assert not log_dir.exists()
    returns = _parts(result, ToolReturnPart)
    assert returns and "承認しませんでした" in str(returns[0].content)


def test_cli_without_input_denies_save(tmp_path, monkeypatch):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)

    def no_input(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", no_input)
    result = run_with_approval(agent, "保存して", _saving_model(["入力できない環境の記録"]))
    assert not log_dir.exists()
    assert isinstance(result.output, str)


def test_cli_approves_each_call_and_counts_all_requests(tmp_path, monkeypatch, capsys):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    answers = iter(["y", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    result = run_with_approval(
        agent, "2つの記録を保存して", _saving_model(["承認する記録", "拒否する記録"])
    )
    files = list(log_dir.glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text(encoding="utf-8"))["content"] == "承認する記録"
    assert result.usage.requests == 2  # 中断前と再開後の両方を含む。
    output = capsys.readouterr().out
    assert "承認する記録" in output and "拒否する記録" in output
    assert output.count("[approval required]") == 2


def test_list_tools_includes_new_tools_without_writing(tmp_path, monkeypatch, capsys):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    print_tools(agent)
    output = capsys.readouterr().out
    assert "[make_quiz]" in output
    assert "[save_learning_log]" in output
    assert not log_dir.exists()
