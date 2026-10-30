# プラトンの眼 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 撮った物を写真から消し、その物が分有するイデアを示す展示用システム（観測モード＋探究モード）を、Windows PC で通しで動く形で作る。

**Architecture:** PC 上の Python サーバー（標準ライブラリ＋OpenCV＋NumPy）が画像処理と Gemini REST 通信を受け持ち、静的ファイルとしてブラウザ画面（素の HTML/CSS/ES モジュール）を配る。図鑑とランキングはブラウザの IndexedDB。

**Tech Stack:** Python 3.10+（`http.server`, `urllib`, `unittest`）、opencv-python、numpy、素の JavaScript（ES modules）、IndexedDB。開発時の画面確認のみ Playwright（Windows には入れない）。

**Spec:** `docs/superpowers/specs/2026-10-22-platon-eye-design.md`

## Global Constraints

- 実行時の依存は `opencv-python` と `numpy` だけ。FastAPI・Gemini SDK・npm は使わない
- サーバーは `127.0.0.1`、既定ポート 8000（`.env` の `PORT` で変更）
- `.env`：`GEMINI_API_KEY`、`GEMINI_MODEL`（既定 `gemini-3.8-flash`）、`PORT`。キーが空か「ここに」で始まればお試しモード
- 送る写真は長辺 1600 まで、Gemini へは長辺 1024 の縮小版
- Gemini タイムアウト：輪郭 45秒、イデア 60秒
- 座標：`box_2d` は `[ymin,xmin,ymax,xmax]` 0〜1000、ポリゴンは `[x,y]` 0〜1000
- 画面の文言は日本語のみ。皮肉・冗談なし。エラーは謝らず、何が起きたかと直し方を書く
- 色：紙 `#D8C690`、繊維 `#B49E64`、墨 `#2B2218`、朱 `#8A2A1B`、エジプシャンブルー `#2D5B8E`（選択中・焦点だけ）
- 文字：Shippori Mincho（日本語）、GFS Didot（ギリシャ語）、無ければ Yu Mincho / serif
- タイトル：`Ο ΟΦΘΑΛΜΟΣ ΤΟΥ ΠΛΑΤΩΝΟΣ`、下に「プラトンの眼」
- 消える瞬間のアニメーションなし。動きは押した時の反応だけ
- 探究：制限 90秒（URL `?limit=N` で上書き）、ランキングはお題ごと上位5件、名前なし
- ファイルは UTF-8。Windows で読むときも `encoding="utf-8"` を明示

## Review Focus

1. カメラが無い・許可されない・USB カメラが既定でない → エラー画面に直し方、タイトル画面のカメラ選択で切り替えられる（Task 6 のテスト）
2. Gemini が `【活力】` のような括弧付き・長すぎる語・空の定義を返す → 括弧を外し8字で切る、空なら失敗扱い（Task 3 のテスト）
3. 画像でない本文・空の本文・巨大な本文 → 落ちずに 400 と日本語の説明（Task 5 のテスト）
4. 分析中に Space を連打 → 送信は1回だけ（Task 7 のテスト）
5. 探究で分析中に0秒になる → シャッター時に残りがあれば当たりは有効、はずれなら時間切れ画面（Task 9 のテスト）

---

## File Structure

```
server/config.py        load_config()
server/vision.py        画像処理（試作を TDD で整える）
server/gemini.py        Gemini REST（試作に quest を足す）
server/demo_ideas.py    お試し用10語＋お試し判定
server/pipeline.py      transmute()
server/app.py           HTTP（make_server, main）
web/index.html          全画面の骨組み
web/style.css           パピルス
web/app.js              画面遷移・キー操作・観測モード
web/api.js              サーバー通信
web/camera.js           カメラ
web/compose.js          単語を描く
web/db.js               IndexedDB
web/scroll.js           図鑑（巻物）・詳しい表示
web/quest.js            探究モード（純粋関数＋画面制御）
web/quests.json         お題20語
web/tests/index.html    JS の小さなテスト（ブラウザで開く）
tests/test_*.py         Python テスト
tools/ui_check.py       開発用：Playwright で全画面を通しスクリーンショット
requirements.txt, .env.example, setup.bat, start.bat, README.md
```

---

### Task 1: 設定の読み込み

**Files:**
- Create: `server/config.py`, `tests/test_config.py`
- Modify: `server/app.py`（試作の `load_env` を削除し `load_config` を使う。Task 5 で作り直すので、ここでは import が通るだけでよい）

**Interfaces:**
- Produces: `load_config(root: Path, environ: Mapping[str,str]) -> dict` → `{"api_key": str, "model": str, "port": int, "demo": bool}`

- [ ] **Step 1: テストを書く** `tests/test_config.py`
  - `test_defaults_without_env_file`：空フォルダ・空 environ → `model=="gemini-3.8-flash"`, `port==8000`, `demo is True`
  - `test_reads_env_file_with_bom_and_quotes`：`.env` を `utf-8-sig` で `GEMINI_API_KEY="abc"\nPORT=8123\n# c` → `api_key=="abc"`, `port==8123`, `demo is False`
  - `test_placeholder_key_is_demo`：`GEMINI_API_KEY=ここにキーを貼る` → `demo is True`
  - `test_environ_overrides_file`：environ の `GEMINI_MODEL` がファイルより優先
  - `test_bad_port_falls_back`：`PORT=abc` → 8000
- [ ] **Step 2:** `python -m unittest tests.test_config -v` → FAIL（モジュールなし）
- [ ] **Step 3:** `server/config.py` に `load_config` を書く
- [ ] **Step 4:** 同じコマンド → 5件 PASS
- [ ] **Step 5:** commit `feat: 設定の読み込み`

---

### Task 2: 画像処理（物を消す）

**Files:**
- Modify: `server/vision.py`（試作あり）
- Create: `tests/test_vision.py`, `tests/helpers.py`

**Interfaces:**
- Produces（Task 4 が使う）:
  - `decode_image(data: bytes) -> np.ndarray`（読めなければ `ValueError("画像を読み込めませんでした")`）
  - `encode_jpeg(img, quality=90) -> bytes`、`to_data_url(img, quality=90) -> str`、`limit_size(img, max_side) -> np.ndarray`
  - `erase_object(img, target: dict|None) -> dict` → `{"erased": ndarray, "mask": ndarray, "mask_method": str, "anchor": {"cx","cy","w","h": float}, "coverage": float}`
  - `mask_method` は `gemini-polygon` / `gemini-png` / `grabcut-box` / `grabcut-center`
- `tests/helpers.py`：`synthetic_scene() -> (img, box_2d, polygon_full)`。1280×720、上が明るい壁、下が木目＋ノイズ、中央に赤い缶（x 560〜720, y 180〜560）

- [ ] **Step 1: テストを書く** `tests/test_vision.py`
  - `test_polygon_full_image_basis`：画像全体基準のポリゴン → method `gemini-polygon`、缶の中心画素がマスク内
  - `test_polygon_box_basis`：`[[0,0],[1000,0],[1000,1000],[0,1000]]`（ボックス内基準）→ マスクがボックスとほぼ一致（IoU > 0.9）
  - `test_polygon_too_far_from_box_is_ignored`：ボックスと重ならないポリゴン → method が `grabcut-box`
  - `test_png_mask`：ボックス大の白 PNG の data URL → `gemini-png`
  - `test_box_only_uses_grabcut`、`test_none_uses_center_grabcut`
  - `test_broken_inputs_do_not_raise`：`mask=[[1]]`、`mask="xx"`、`box_2d=[0,0]`、逆向きボックス → 例外なし
  - `test_object_color_removed`：3通りすべてで、缶の範囲の赤み（R−G の平均）が元の 1/4 未満
  - `test_runs_under_one_second`：1280×720 で `erase_object` が 1.0 秒未満
  - `test_anchor_inside_object`：`anchor.cx` が 0.44〜0.56、`anchor.cy` が 0.25〜0.75
  - `test_decode_garbage_raises_value_error`
- [ ] **Step 2:** `python -m unittest tests.test_vision -v` → 失敗するものを確認（試作で通るものがあれば、それは試作がすでに満たしている印として記録）
- [ ] **Step 3:** 失敗したテストだけ直す。境界の扱い：`box_2d` が4未満・数値でない → `target` 無しと同じ扱い
- [ ] **Step 4:** 同じコマンド → 全件 PASS
- [ ] **Step 5:** commit `feat: 物を消す画像処理`

---

### Task 3: Gemini 通信（輪郭・イデア・探究の判定）

**Files:**
- Modify: `server/gemini.py`（試作あり）
- Create: `tests/test_gemini.py`

**Interfaces:**
- Produces:
  - `class GeminiError(RuntimeError)`
  - `ask_json(cfg, prompt, jpeg, schema, minimal_thinking, timeout=60) -> dict`
  - `segment(cfg, jpeg) -> dict|None`（`{"box_2d","mask","label"}`、複数なら面積最大）
  - `idealize(cfg, jpeg, label, quest: str|None = None) -> dict` → `{"word","reading","greek","greek_reading","definition","participation"}`、`quest` ありなら加えて `"quest": {"word": quest, "match": bool, "reason": str}`
- テストは `gemini._post` を差し替える（`unittest.mock.patch`）。通信しない

- [ ] **Step 1: テストを書く** `tests/test_gemini.py`
  - `test_generate_content_text_is_parsed`：`candidates[0].content.parts=[{"thought":true,"text":"x"},{"text":"{\"a\":1}"}]` → `{"a":1}`
  - `test_code_fence_json_is_parsed`：```` ```json\n{...}\n``` ````
  - `test_retry_without_thinking_on_400`：1回目 `HTTP 400` → 2回目の本文に `thinkingConfig` が無い
  - `test_falls_back_to_interactions`：generateContent が `HTTP 404` → URL が `/interactions` で、`outputs=[{"type":"text","text":...}]` を読む
  - `test_401_raises_key_message`：`GeminiError` の文に「APIキー」
  - `test_url_error_message`：`_post` が `GeminiError("接続できませんでした: ...")` → そのまま伝わる（画面で「インターネット」に変換するのは Task 4）
  - `test_segment_picks_largest_and_skips_invalid`
  - `test_idealize_strips_brackets_and_truncates`：`word="【活力そのものの本質】"` → `"活力そのものの本"`（8字）
  - `test_idealize_empty_word_or_definition_raises`
  - `test_idealize_without_quest_has_no_quest_fields`：送ったスキーマに `quest_match` が無い、戻り値に `quest` が無い
  - `test_idealize_with_quest`：プロンプトに `『庇護』` を含み、スキーマの required に `quest_match`,`quest_reason`、戻り値 `quest == {"word":"庇護","match":True,"reason":...}`
- [ ] **Step 2:** `python -m unittest tests.test_gemini -v` → FAIL（quest 関連・空定義・切り詰め）
- [ ] **Step 3:** `idealize` に `quest` を足す。プロンプト追記文（仕様 7章）：
  「この物は『{quest}』のイデアを分有しているか。物の本来のはたらき・あり方が、そのイデアに確かに与っているときだけ真。こじつけは偽。quest_reason は 30〜50字で、なぜそう判定したかを書く。」
  空の `definition` も `GeminiError("イデアの単語が得られませんでした")` と同じ扱い
- [ ] **Step 4:** 同じコマンド → 全件 PASS
- [ ] **Step 5:** commit `feat: Gemini 通信と探究の判定`

---

### Task 4: 1枚を処理する流れ（pipeline）とお試しモード

**Files:**
- Create: `server/pipeline.py`, `tests/test_pipeline.py`
- Modify: `server/demo_ideas.py`

**Interfaces:**
- Consumes: Task 2 `vision.*`、Task 3 `gemini.segment/idealize/GeminiError`、Task 1 の cfg
- Produces:
  - `demo_idea(label: str, quest: str|None = None, rng: random.Random|None = None) -> dict`（idealize と同じ形。quest ありなら `match = rng.random() < 0.5`、reason「お試しモードのため判定は無作為です。」）
  - `transmute(jpeg: bytes, cfg: dict, quest: str|None = None) -> dict`（仕様 6章の JSON そのまま。`ok`,`mode`,`label`,`idea`,`anchor`,`mask_method`,`original`,`erased`,`seconds`、quest ありなら `quest`）
  - `class UserFacingError(Exception)`（画面にそのまま出す文）

- [ ] **Step 1: テストを書く** `tests/test_pipeline.py`
  - `test_demo_mode_shape`：合成画像・`demo=True` → キーがすべてある、`original`/`erased` が `data:image/jpeg;base64,` で始まる、`quest` キーなし
  - `test_demo_mode_with_quest`：`quest="庇護"` → `quest.word=="庇護"`、`match` は bool
  - `test_segment_failure_falls_back_to_grabcut`：segment が `GeminiError` → `mask_method` が `grabcut-*`、結果は返る
  - `test_idea_failure_raises_user_facing`：idealize が `GeminiError("HTTP 500 ...")` → `UserFacingError` の文が「イデアを取り出せませんでした。もう一度撮ってください」で始まる
  - `test_network_error_message`：`接続できませんでした` → 「インターネットにつながっていません」
  - `test_key_error_message`：「APIキー」→ 文に「.env」
  - `test_large_image_is_limited`：3000×2000 → `original` を復号すると長辺 1600
- [ ] **Step 2:** `python -m unittest tests.test_pipeline -v` → FAIL
- [ ] **Step 3:** 実装。試作 `app.py` の `transmute` を移し、cfg と quest を引数にする。ログ1行（物・語・各段の秒）は標準出力
- [ ] **Step 4:** 同じコマンド → PASS。`python -m unittest discover -s tests -v` も全件 PASS
- [ ] **Step 5:** commit `feat: 1枚の処理の流れとお試しモード`

---

### Task 5: HTTP サーバー

**Files:**
- Modify: `server/app.py`（作り直す）
- Create: `tests/test_app.py`、`web/index.html`（中身は Task 6。ここでは `<title>プラトンの眼</title>` だけの仮）

**Interfaces:**
- Consumes: `load_config`、`transmute`、`UserFacingError`
- Produces: `make_server(cfg: dict, host="127.0.0.1", port=0) -> ThreadingHTTPServer`、`main()`
  - `GET /api/status` → `{"mode","model"}`
  - `POST /api/transmute[?quest=]` → 200 JSON / 400 `{"ok":false,"error"}` / 500 同形
  - `GET /` と `web/` 以下の静的ファイル（`..` で外に出られない）、無ければ 404
  - `.js` は `text/javascript; charset=utf-8`、`.json` は `application/json; charset=utf-8`

- [ ] **Step 1: テストを書く** `tests/test_app.py`（`make_server(port=0)` を別スレッドで起動し `urllib` で叩く。cfg は demo）
  - `test_status`、`test_index_served`、`test_js_content_type`、`test_404`、`test_path_traversal_404`（`/../server/app.py`）
  - `test_transmute_ok`：合成 JPEG → 200、`ok is True`
  - `test_transmute_quest_japanese`：`?quest=%E5%BA%87%E8%AD%B7` → `quest.word=="庇護"`
  - `test_quest_too_long_400`：21文字 → 400
  - `test_empty_body_400`、`test_garbage_body_400`（`b"hello"` → 400、文に「画像」）
  - `test_too_large_400`：`Content-Length` 21MB（本文は送らない）→ 400
- [ ] **Step 2:** `python -m unittest tests.test_app -v` → FAIL
- [ ] **Step 3:** 実装。`ValueError` と `UserFacingError` は 400 または 500 に分ける（画像不良 400、Gemini 失敗 500）。起動時のあいさつ（モード、URL、終了方法）は試作どおり
- [ ] **Step 4:** 同じコマンド → PASS、全テスト PASS
- [ ] **Step 5:** commit `feat: HTTP サーバー`

---

### Task 6: 画面の土台（タイトル・パピルス・カメラ・エラー）

**Files:**
- Create: `web/index.html`, `web/style.css`, `web/app.js`, `web/api.js`, `web/camera.js`, `tools/ui_check.py`

**Interfaces:**
- Produces:
  - `index.html`：`<section class="screen" id="...">` を6画面＋探究5画面分。id は `title, observe, analyzing, result, scroll, detail, error, q-intro, q-hunt, q-miss, q-clear, q-timeup`
  - `app.js`：`show(id: string)`、`showError(message: string, back: "title"|"q-hunt")`、キー割り当て表 `keymap[screenId] = {key: handler}`
  - `camera.js`：`listCameras() -> Promise<{deviceId,label}[]>`、`startCamera(video, deviceId?) -> Promise<void>`（失敗は `CameraError` で文は「カメラが見つかりません。USB の差し込みと、ブラウザのカメラ許可を確認してください」）、`captureJpeg(video, maxSide=1600) -> Promise<Blob>`。選んだ id は `localStorage["platon.camera"]`（try/catch）
  - `api.js`：`transmute(blob: Blob, quest?: string) -> Promise<Result>`。通信できない時は `ApiError("サーバーが動いていません。start.bat を起動してください")`、`ok:false` は `ApiError(error)`
  - `tools/ui_check.py`：サーバーを demo で起動 → Chromium（偽カメラ）で開く → 引数のシナリオを実行 → `shots/*.png` を保存。`--no-camera` で偽カメラなし
- 見た目：仕様 8章。巻物の端（上下の丸まり）と繊維の筋（SVG `feTurbulence` を data URL で背景に）。タイトルは碑文風の大文字。ボタンは墨の線と朱の見出し、焦点はエジプシャンブルーの太い輪郭

- [ ] **Step 1:** `tools/ui_check.py title` を書き、タイトル画面に「観測」「探究」「図鑑」と `Ο ΟΦΘΑΛΜΟΣ` があるか確かめる assert を入れる。実行 → FAIL（画面なし）
- [ ] **Step 2:** `index.html`、`style.css`、`app.js` の `show`/キー処理、タイトル画面を作る。キー `1` で観測（撮影画面にカメラ映像）、`Esc` で戻る。タイトルにカメラ選択（`listCameras`）と、`/api/status` が demo なら小さく「お試しモード」
- [ ] **Step 3:** `python tools/ui_check.py title observe` → PASS、`shots/title.png` と `shots/observe.png` を開いて目で見る（文字化け・はみ出し・色）
- [ ] **Step 4:** `python tools/ui_check.py --no-camera observe` → エラー画面にカメラの直し方の文がある（Review Focus 1）
- [ ] **Step 5:** commit `feat: 画面の土台とカメラ`

---

### Task 7: 観測モードを通す（分析中・結果・単語を描く）

**Files:**
- Create: `web/compose.js`, `web/tests/index.html`
- Modify: `web/app.js`, `web/index.html`, `web/style.css`, `tools/ui_check.py`

**Interfaces:**
- Consumes: `api.transmute`、`camera.captureJpeg`
- Produces:
  - `wordFontSize(imgW, imgH, anchor, chars) -> number`：`min(短辺×0.22, anchor.w×imgW×0.9÷chars, anchor.h×imgH×0.6)`、下限 `短辺×0.06`
  - `composeIdea(erasedUrl: string, word: string, anchor) -> Promise<{blob: Blob, url: string}>`（白、明朝、影 `rgba(0,0,0,.45)` ぼかし 短辺×0.02、JPEG 0.9。描く前に `document.fonts.load` で明朝を待つ）
  - `state.current = {result, ideaBlob, ideaUrl, originalBlob}`（Task 8 が保存に使う）
- `web/tests/index.html`：小さな `assert` で JS の純粋関数を試し、結果を `<pre id="out">` に `PASS n / FAIL n` で書く

- [ ] **Step 1:** `web/tests/index.html` に `wordFontSize` のテスト（1280×720、anchor w0.14 h0.58、2字 → 720×0.22=158.4 と 1280×0.14×0.9/2=80.6 と 720×0.58×0.6=250.6 の最小で 80.64。8字の細い物 → 下限 43.2）
- [ ] **Step 2:** `python tools/ui_check.py jstest` → FAIL
- [ ] **Step 3:** `compose.js` を書く → `jstest` PASS
- [ ] **Step 4:** `ui_check.py observe-flow` を足す：撮影 → 分析中 → 結果（元写真・イデア写真・`【語】`・定義・「保存しますか？」）→ `N` で撮影画面。さらに分析中に Space を3回押し、`/api/transmute` への送信が1回だけ（Review Focus 4）。実行 → FAIL
- [ ] **Step 5:** `app.js` に撮影・分析中・結果を作る。送信中フラグで二重送信を防ぐ。エラーは `showError`
- [ ] **Step 6:** `observe-flow` → PASS。`shots/analyzing.png`、`shots/result.png` を目で見る
- [ ] **Step 7:** commit `feat: 観測モードの撮影から結果まで`

---

### Task 8: 図鑑（巻物）・詳しい表示・保存

**Files:**
- Create: `web/db.js`, `web/scroll.js`
- Modify: `web/app.js`, `web/index.html`, `web/style.css`, `web/tests/index.html`, `tools/ui_check.py`

**Interfaces:**
- Produces（`db.js`、DB `platon-eye` 版1、ストア `ideas` と `records`（`word` 索引））:
  - `addIdea(rec) -> Promise<number>`、`listIdeas() -> Promise<Idea[]>`（新しい順）、`getIdea(id)`、`deleteIdea(id)`、`clearIdeas()`
  - `addRecord({word, seconds, thumb}) -> Promise<number>`、`topRecords(word, n=5) -> Promise<Record[]>`（秒の小さい順、同じなら id の小さい順）、`rankOf(word, id) -> Promise<number>`（1始まり）、`clearRecords()`
  - Idea の形は仕様 9章（`questWord`,`questSeconds` は任意）
- `scroll.js`：`renderScroll(el, ideas, highlightId?)`、`openDetail(idea)`、`closeDetail()`。カードの画像は `URL.createObjectURL`、描き直しの前に古い URL を `revokeObjectURL`

- [ ] **Step 1:** `web/tests/index.html` に db のテスト（テスト用に DB 名を `platon-eye-test` に切り替える `useDbName(name)` を `db.js` に用意）：add→list の順、delete、clear で records が残る、`topRecords` の順位と同点の扱い、`rankOf`
- [ ] **Step 2:** `jstest` → FAIL → `db.js` を書く → PASS
- [ ] **Step 3:** `ui_check.py scroll-flow` を足す：結果で `Y` → 図鑑に新しいカードが1枚・目立つ印 → カードをクリック → 詳しい表示（定義・分有の文・日時）→ 削除（確認を承認）→ 0枚で「まだ何も収められていません。観測して最初のイデアを収めましょう」→ ホイールで横に動く。実行 → FAIL
- [ ] **Step 4:** `scroll.js` と画面を作る。巻物：横一列、カードは段（写真の下に `【語】`）、ホイールの縦回転を横移動に変える、`←→` でも動く、「全部消す」は確認あり
- [ ] **Step 5:** `scroll-flow` → PASS。`shots/scroll.png`、`shots/detail.png` を目で見る
- [ ] **Step 6:** commit `feat: 図鑑の巻物と保存`

---

### Task 9: 探究モード

**Files:**
- Create: `web/quest.js`, `web/quests.json`
- Modify: `web/app.js`, `web/index.html`, `web/style.css`, `web/tests/index.html`, `tools/ui_check.py`, `server/demo_ideas.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `api.transmute(blob, quest)`、`db.addRecord/topRecords/rankOf/addIdea`、`compose.composeIdea`
- Produces（純粋関数）:
  - `remaining(startMs, nowMs, limitSec) -> number`（0未満は0、小数切り上げの整数）
  - `shotCounts(startMs, shotMs, limitSec) -> boolean`（`shotMs - startMs < limitSec*1000`）
  - `elapsedAtShot(startMs, shotMs) -> number`（秒、小数1桁）
  - `pickQuest(quests, lastWord, rand=Math.random) -> Quest`（1語しかなければそれ）
  - `limitFromUrl(search: string) -> number`（`?limit=` が 1〜600 の整数ならそれ、ほかは 90）
- `quests.json`：20語。各 `{word, reading, greek, examples[3]}`。会場や持ち物で見つかる語（例：庇護・時間・光明・保持・伝達・記憶・休息・調和・計測・結合・記録・浄化・支え・覆い隠し・飲食・音・温もり・移動・開閉・美）。`greek` は確かな語のみ

- [ ] **Step 1:** `web/tests/index.html` に純粋関数のテスト：`remaining(0, 89100, 90)==1`、`remaining(0, 95000, 90)==0`、`shotCounts(0, 89999, 90)===true`、`shotCounts(0, 90000, 90)===false`、`elapsedAtShot(1000, 13460)==12.5`、`pickQuest` が lastWord を避ける（rand を固定して確認）、`limitFromUrl("?limit=5")==5`、`limitFromUrl("?limit=0")==90`
- [ ] **Step 2:** `jstest` → FAIL → 関数を書く → PASS
- [ ] **Step 3:** `ui_check.py quest-flow` を足す（お試しモードの判定を決めるため、サーバーに開発用の環境変数 `PLATON_DEMO_MATCH=always|never` を用意し、`demo_idea` が従う。Task 4 のテストにも1件足す）：
  - never：タイトル `2` → お題画面（語・上位5件の欄）→ Space → 探す（残り秒が出る）→ Space → はずれ（理由・残り秒）→ Space で探す画面
  - always：撮影 → 達成（秒数・「1位」）→ `Y` → 図鑑のカードに「探究達成」の印 → お題画面に戻ると上位5件に1件
  - `?limit=3`、never：撮影直後に0秒をまたぐ → はずれではなく時間切れ画面（Review Focus 5）
  - `?limit=3`、always：同じ条件 → 達成画面（シャッター時に残りあり）
  - `?limit=2`：何もしない → 時間切れ画面に「例：」と3つの例
  - タイトルで Shift+Delete → 確認を承認 → お題画面の上位5件が空
  実行 → FAIL
- [ ] **Step 4:** `quest.js` の画面制御を作る。タイトルの Shift+Delete で `clearRecords()`（確認あり）。残り秒は `setInterval` 250ms で数字だけ更新。探究中のエラーは `showError(msg, "q-hunt")`。`quests.json` が読めない時はタイトルの探究ボタンを押せなくし「お題の一覧を読み込めません」
- [ ] **Step 5:** `quest-flow` → PASS。`shots/q-*.png` を目で見る
- [ ] **Step 6:** commit `feat: 探究モード`

---

### Task 10: Windows で動かす準備と最終確認

**Files:**
- Create: `requirements.txt`（`opencv-python>=4.8`、`numpy>=1.24`）、`.env.example`、`setup.bat`、`start.bat`、`README.md`
- Modify: なし（不具合があれば該当ファイル）

**Interfaces:**
- `setup.bat`：`py -3 -m venv .venv` → `.venv\Scripts\python -m pip install -r requirements.txt` → `.env` が無ければ `.env.example` をコピー。Python が無ければ python.org の案内を表示して止まる。`chcp 65001`
- `start.bat`：`.venv\Scripts\python server\app.py` を別窓で起動 → 2秒待つ → Chrome をキオスク `--kiosk http://localhost:8000` で開く（Chrome が無ければ既定ブラウザ）
- `README.md`：準備（Python、setup.bat）、Gemini APIキーの取り方（Google AI Studio → Get API key → `.env` に貼る）、起動、操作キー一覧、カメラの選び方、お題の編集方法、困った時（カメラが映らない／APIキー無効／ネット無し）、展示の終わりに図鑑を消す方法

- [ ] **Step 1:** ファイルを書く
- [ ] **Step 2:** `python -m unittest discover -s tests -v` → 全件 PASS
- [ ] **Step 3:** `python tools/ui_check.py all` → 全シナリオ PASS、全スクリーンショットを目で見る
- [ ] **Step 4:** `.bat` を目で読み、CRLF 改行・`chcp 65001`・パスの区切りを確認（ここでは実行できない）
- [ ] **Step 5:** 配布用 zip を作る（`.env`・`shots/`・`__pycache__`・`tools/` は入れない）
- [ ] **Step 6:** commit `feat: Windows 用の準備と説明書`
