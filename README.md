# spec_generator

自動車のオーナーズマニュアル（PDF）から、比較可能な型の「ドラフト版要求仕様書」を
メーカーを問わず機械的に生成するツール。**AIを使わず、ルールベース・決定論的**に
動作する（生成される要求文は必ず原文の軽い再構成であり、要約・翻訳・創作ではない）。

## セットアップ

```bash
python -m venv .venv
.venv/Scripts/activate   # Windows。macOS/Linuxは source .venv/bin/activate
pip install -r requirements.txt
```

Gemini APIを使う機能（後述、オプトイン）を使う場合は `.env.example` を `.env` に
コピーし `GEMINI_API_KEY` を設定する。使わない場合は何もしなくてよい。

## 使い方

### Web UI

```bash
python run_web.py
```

`http://127.0.0.1:8711` で起動する（ポート/ホストは `SPECGEN_PORT` / `SPECGEN_HOST`
環境変数で変更可）。マニュアルの登録・章の選択・生成・公開・閾値の入力をブラウザから行える。

### CLI

```bash
python specgen.py <command> ...
```

主なコマンド:

| コマンド | 用途 |
|---|---|
| `add-source` | マニュアルをメタデータ付きで登録 |
| `profile-auto` | プロファイルを自動解決（既存プロファイルへの適合判定→新規レイアウト導出） |
| `profile-fit` / `profile-derive` | 既存プロファイルへの適合判定 / 新規レイアウトの導出（個別実行） |
| `profile-derive-toc-chapters` / `profile-confirm-chapters` | マニュアル自身の目次からの章検出→人間の確認 |
| `profile-classify-chapters` | （オプトイン）Gemini APIによる章候補のREAL/NOISE分類 |
| `generate` | 指定章のドラフト仕様書を生成 |
| `publish` | 生成結果をMarkdown＋図版として書き出す |
| `status` | マニュアルの登録・生成状況を表示 |

`python specgen.py <command> --help` で個別の引数を確認できる。

## テスト

```bash
pytest tests/ -q
python tests/check_domain.py    # ドメイン層の不変条件チェック（PDF/ネットワーク不要）
python tests/check_layers.py    # domain/ がインフラに依存していないことの確認
```

## 構成

```
presentation/   CLI (specgen.py) と Web (FastAPI) — 入出力の窓口
      │
application/    UseCases（3つの動詞: generate / publish / set_parameter）と ports（境界）
      │
domain/         純粋なロジック。PDFライブラリを一切importしない
      │
infrastructure/ 具体的な実装（pdfplumber, pypdfium2, ファイルI/O, Jinja2）
```

- `domain/` は pdfplumber・pypdfium2 を一切importしない。PDFという概念を知らず、
  `Line` / `Bookmark` / `Section` という抽出済みのプレーンなデータ構造だけを扱う
- `application/` はどの具体的インフラクラスも直接importしない。必ず `ports.py` の
  Protocol経由で扱い、具体クラスとProtocolが出会うのは `presentation/composition.py` だけ
- 生成・公開結果の識別子（`content_id`）は内容（SHA-256）由来で、章番号・ページ番号・
  抽出順序を使わない。マニュアル改版で構成が変わっても、同じ内容の要求文・図・閾値は
  同じidを保つ

設計判断の詳しい経緯は `docs/`（リポジトリには含めていない、ローカルの作業メモ）を参照。
