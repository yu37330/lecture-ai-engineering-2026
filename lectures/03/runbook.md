# 第3回を手を動かして進める

この手順は、共通演習の `make_quiz` と、宿題の「実装：承認付き学習ログ保存」を試すためのものです。コードとAPIを使わないテストは準備済みです。Geminiによる回答・ツール選択・実行回数は、以下を実行して確認します。

## 1. Codespacesで準備する

自分のfork `yu37330/lecture-ai-engineering-2026` のCodespacesを開きます。第1・2回の作業ブランチに未コミットの変更があれば、そのブランチで保存・コミットしてから切り替えます。

```bash
git status --short
git fetch origin
git switch lec03
git pull --ff-only
uv sync --frozen
uv run pytest -q
uv run python -m app.agent --list-tools
```

`lec03` は講座指定の `lec03-start` タグから準備しています。`--list-tools` に `search_glossary`、`get_lecture_summary`、`make_quiz`、`save_learning_log` の4つが表示されることを確かめます。この2つの確認コマンドはAPIキーを使いません。

Geminiの実行には、Codespaces secretの `GEMINI_API_KEY` を使います。キーの値を画面に表示する必要はありません。登録後に環境へ反映されていない場合はCodespacesを停止して開き直します。依存パッケージとモデルの設定は講座のものを使用し、`uv.lock` は変更していません。

## 2. 素のLLMと検索するエージェントを比べる

同じ質問を2つのプログラムへ渡し、実際の結果をログに保存します。資料の出力例を自分の実測として転記しないでください。

```bash
mkdir -p lectures/03/experiment

uv run python -m app.ask "AIE2026の講座の宿題にある「3レベル」とは何ですか？" \
  | tee lectures/03/experiment/01_plain_llm.txt

uv run python -m app.agent --trace "AIE2026の講座の宿題にある「3レベル」とは何ですか？" \
  | tee lectures/03/experiment/02_agent.txt
```

回答が `data/glossary.json` の `homework-levels` と一致するか、`search_glossary` が実際に呼ばれたかを読みます。素のLLMが正しく答えた場合も、その事実を書きます。検索の有無と回答の正誤を分けて考えるのがポイントです。

## 3. ツール名・引数・呼び出し回数を読む

```bash
uv run python -m app.agent --trace "LoRAとQLoRAの違いは？" \
  | tee lectures/03/experiment/03_lora_trace.txt
```

`[tool call]` はモデルの実行依頼、`[tool return]` はプログラムが返した結果です。`[usage]` の `requests` はLLMを呼んだ回数で、ツールを呼んだ回数とは別です。実際の引数、検索回数、回答に使われた根拠を `answer.md` に記録します。

## 4. make_quizを確かめる

```bash
uv run python -m app.agent --trace "第2回の内容から確認問題を1問出して" \
  | tee lectures/03/experiment/04_quiz_trace.txt
```

`make_quiz` が `lecture=2` で呼ばれるか確認します。関数は第2回の用語をランダムに1つ選ぶため、問題文は毎回同じとは限りません。関数は問題と正解をモデルに返し、指示では利用者にまず問題だけを見せるよう求めています。現在のCLIは1コマンド1質問なので、次のコマンドへ会話履歴を保存する対話機能は今回の範囲に含みません。

## 5. 保存を拒否する場合と承認する場合を比べる

まず `learning_log/` 内のファイル数を確認します。フォルダがなければ0件として扱います。

```bash
uv run python -m app.agent --trace "第3回の学習記録として『LLMはツール実行を依頼し、プログラムが実行する。保存には人の承認を挟む。』を保存して" \
  | tee lectures/03/experiment/05_save_denied.txt
```

ツール名・保存予定の回番号と本文が表示されたら、最初は `n` と入力します。ファイルが増えていないことと、拒否がモデルへ返ったことを確認します。次は同じ質問をもう一度実行し、表示された内容を読んで `y` と入力します。

```bash
uv run python -m app.agent --trace "第3回の学習記録として『LLMはツール実行を依頼し、プログラムが実行する。保存には人の承認を挟む。』を保存して" \
  | tee lectures/03/experiment/06_save_approved.txt
```

承認後だけ `learning_log/` に新しいJSONができ、`lecture`、`content`、`saved_at` が入ることを確認します。空入力・`n`・入力の終端（EOF）は拒否として扱います。`y` または `yes` を入力した呼び出しだけを実行します。個人の保存ログは既存の `.gitignore` によってGitの対象外です。

## 6. 変更前後のコードを読む

元の `app/tools.py` には検索と講義要約の関数があり、問題作成・保存は未実装でした。追加した `make_quiz` は対象回の用語を選び、該当する用語がなければ説明を返します。追加した `save_learning_log` は回番号と本文を受け取り、保存先とファイル名をプログラム側で決めます。日時とUUIDによるファイル名を排他的に新規作成し、既存ログを上書きしません。

元の登録・実行の要点は次の形でした。

```python
agent = Agent(instructions=INSTRUCTIONS)
agent.tool_plain(tools.search_glossary)
agent.tool_plain(tools.get_lecture_summary)
result = target.run_sync(args.question, model=build_model())
```

変更後は、問題作成と承認付き保存を登録し、承認待ちも戻り値として受け取ります。

```python
agent = Agent(instructions=INSTRUCTIONS, output_type=[str, DeferredToolRequests])
agent.tool_plain(tools.search_glossary)
agent.tool_plain(tools.get_lecture_summary)
agent.tool_plain(tools.make_quiz)
agent.tool_plain(tools.save_learning_log, requires_approval=True)
result = run_with_approval(target, args.question, build_model())
```

`confirm_tool_calls` が呼び出しごとに内容を示して判断を集め、`run_with_approval` が `message_history` と `deferred_tool_results` を渡して再開します。`RunUsage` を共有するため、表示される `requests` は中断前と再開後の合計です。承認を必要にする仕組みは `requires_approval=True` にあり、モデルへの「確認すること」という指示文だけに依存しません。

変更後の関数全体は [app/tools.py](../../app/tools.py)、登録・CLI・再開処理の全体は [app/agent.py](../../app/agent.py) で確認できます。

## 7. 結果を記録して提出する

`lectures/03/answer.md` の「未実行」箇所を、実際に確かめた結果に置き換えます。補助環境でのテスト結果と、自分のGemini実行結果は区別して記録します。エラーになった場合もエラー内容と実行できた範囲を書きます。

```bash
git add lectures/03/answer.md lectures/03/experiment
git commit -m "第3回：Geminiでの演習・宿題の実測結果を記録"
git push origin lec03
```

このブランチのPRは自分のforkの `main` に向けます。実測を確認したらPRをDraftからReady for reviewへ変更し、講座の提出方法に従って提出します。講義資料の締切は「原則として講義日から1週間」です。2026年11月2日の1週間後は11月9日ですが、正式な時刻や例外は講座の案内を確認してください。作業終了後はCodespacesを停止します。

## 確認済みの範囲

2026年11月7日（日本時間）、補助環境のPython 3.12.7・Pydantic AI 2.57.0で、講座開始コードのテスト11件と変更後のテスト22件が通りました。変更後は、承認前の保存なし、拒否・空入力・EOFでの保存なし、承認した呼び出しだけの保存、履歴の引継ぎ、累計requests、ツール一覧、既存MCPのテストを含みます。Gemini APIは呼んでいません。これらのテストはコードの接続を確かめるもので、実モデルが狙いどおりのツールを選ぶことを実測したものではありません。

## 参照

- [講座の第3回課題（lec03-start）](https://github.com/matsuolab/lecture-ai-engineering-2026/blob/lec03-start/lectures/03/problem.md)
- [Pydantic AI公式：Deferred Tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
