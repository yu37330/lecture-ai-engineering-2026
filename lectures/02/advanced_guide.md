# 第2回・発展宿題：用語集のLoRA学習と検索方式の比較

このファイルは作業ガイドです。**提出する解答は `lectures/02/answer.md`** に記入します。GPUでの学習は、受講者自身がColabで実行してください。

## 1. まず公式演習を完了する

[講座の公式Colab](https://colab.research.google.com/github/matsuolab/lecture-ai-engineering-2026/blob/main/notebooks/lora_format_tuning.ipynb) を **T4 GPU** で開き、セクション0〜7を順に実行します。実測した `format_rate`、`content_rate`、残った失敗の型を `answer.md` の「演習」欄に記入します。

## 2. 発展課題の学習データと検索ベースラインを作成する

Forkのリポジトリ直下で実行してください。

```bash
uv run python scripts/lec02_glossary_prepare.py
```

`lectures/02/glossary_experiment/` に次の3ファイルが生成されます。

- `glossary_sft.jsonl`：講座の `scripts/make_sft_dataset.py` により生成した、自然文Q&Aの `messages` 形式の教師データ
- `glossary_eval.json`：学習に使った質問文と一致しない評価12問と、用語集から取得した正解定義
- `lexical_baseline.json`：用語名・別名の文字列一致検索結果

質問は **direct／alias／paraphrase／unknown** の各3問です。未知用語の正解は「用語集に掲載がないと区別すること」とします。用語名がない言い換え質問は、単純文字列検索では取りこぼしが発生します。

**注意：この検索ベースラインは厳密な辞書検索であり、Embeddingを利用する本格的なRAGではありません。**

## 3. Colabで発展課題を実行する

このForkの `notebooks/lec02_glossary_advanced.ipynb` をColabのT4 GPUで開き、自分のドライブにコピーしてから上から実行します。アップロード画面で `glossary_sft.jsonl` と `glossary_eval.json` を渡してください。学習前後のモデルに同じ12問を聞き、回答を保存します。

講座の基礎演習は **JSON形式**を学習させますが、発展課題の公式データ生成スクリプトは**自然文**を教師出力にします。そのため、発展課題の結果に演習の `format_rate` を流用せず、内容と未知質問への対応で比較します。

## 4. 人手で正確性を判定する

Colabが生成した `manual_review.json` の `gold_definition` と、学習前・学習後の回答を照合します。

- **既知用語**：用語集の定義と矛盾せず、正しく説明できれば正解
- **未知用語**：用語集にないと明示できた場合のみ正解。一般知識によるもっともらしい説明は「用語集の根拠なし」と区別する
- 各回答の `before_correct` / `after_correct` を人手で `true` か `false` に変更する。未採点のまま正答率を作らない

全12問と4区分の正答率を集計し、`lexical_baseline.json` と比較します。定性的な評価（意味が一致するか）の人手判定には評価者依存性があることも記載してください。

## 5. 提出

`lectures/02/answer.md` の「宿題」に、発展を選んだこと、モデル・revision・LoRA設定、学習データ件数、学習時間、最終loss、学習前後の事例・正答率、辞書検索との比較、ファインチューニングの向き不向きを記録します。

データは**学習に使った表現と評価用の表現を分けていますが、同じ用語の定義は学習時に登場します**。未知の知識を獲得できたことの証明にはなりません。

作業ブランチ `lec02` から **自分のForkの `main`** にPRを出し、Colabのランタイムを「接続解除して削除」してください。

GPU学習が実行できなかった場合、実施できた範囲を正直に書き、`executed_training_myself` を `false` にしてください。
