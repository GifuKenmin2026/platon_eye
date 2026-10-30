"""
Gemini API（REST を urllib で直接呼ぶ。追加ライブラリなし）

  segment()  写真の主役の物を1つ選び、輪郭とボックスを返す
  idealize() その物が分有するイデアと辞書定義（お題があれば判定も）を返す

generateContent を使い、だめなら Interactions API で再試行する。
"""
from __future__ import annotations

import base64
import http.client
import json
import ssl
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(RuntimeError):
    pass


# ---------------------------------------------------------------- 通信

def _post(url: str, api_key: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as res:
            raw = res.read()
    except urllib.error.HTTPError as e:
        raise GeminiError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:600]}") from None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
        raise GeminiError(f"接続できませんでした: {getattr(e, 'reason', e)!r}") from None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:  # ログイン画面などの HTML が返ってきた
        raise GeminiError("接続できませんでした: Gemini 以外の応答が返ってきました") from None


def _post_get(url: str, api_key: str, timeout: float) -> dict:
    """GET で JSON を受け取る（接続の確認用）"""
    req = urllib.request.Request(url, headers={"x-goog-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise GeminiError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, ValueError) as e:
        raise GeminiError(f"接続できませんでした: {getattr(e, 'reason', e)!r}") from None


def _text_from_generate(res: dict) -> str:
    for cand in res.get("candidates") or []:
        texts = [p["text"] for p in cand.get("content", {}).get("parts", []) if "text" in p and not p.get("thought")]
        if texts:
            return "".join(texts)
    raise GeminiError(f"応答が空でした（{res.get('promptFeedback') or res.get('candidates')}）")


def _text_from_interaction(res: dict) -> str:
    if isinstance(res.get("output_text"), str):
        return res["output_text"]
    items = []
    for step in res.get("steps") or []:  # REST の形：steps[].type == "model_output"
        if isinstance(step, dict) and step.get("type") == "model_output":
            items += step.get("content") or []
    items += res.get("outputs") or []
    texts = [o["text"] for o in items if isinstance(o, dict) and o.get("type") == "text" and "text" in o]
    if not texts:
        raise GeminiError("応答が空でした（interactions）")
    return "".join(texts)


def _parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t.strip("`")
        t = t.rsplit("```", 1)[0]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        s, e = t.find("{"), t.rfind("}")
        if 0 <= s < e:
            try:
                return json.loads(t[s:e + 1])
            except json.JSONDecodeError:
                pass
    raise GeminiError("JSON を読み取れませんでした: " + t[:200])


def _lower_types(schema):
    if isinstance(schema, dict):
        return {k: (v.lower() if k == "type" and isinstance(v, str) else _lower_types(v)) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_lower_types(v) for v in schema]
    return schema


def _is_key_error(msg: str) -> bool:
    return msg.startswith("HTTP 401") or msg.startswith("HTTP 403") or "API key not valid" in msg


def ask_json(cfg: dict, prompt: str, jpeg: bytes, schema: dict, minimal_thinking: bool, timeout: float = 60,
             max_tokens: int | None = None) -> dict:
    key, model = cfg["api_key"], cfg["model"]
    b64 = base64.b64encode(jpeg).decode("ascii")
    errors = []

    contents = [{"role": "user", "parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": b64}}]}]
    url = f"{API_ROOT}/models/{model}:generateContent"
    # モデルが対応しない思考レベルは 400 になるので、1段ずつ下げる
    levels = ["minimal", "low", None] if minimal_thinking else [None]

    for i, level in enumerate(levels):
        gen_cfg = {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0.7}
        if level:
            gen_cfg["thinkingConfig"] = {"thinkingLevel": level}
        if max_tokens:
            gen_cfg["maxOutputTokens"] = max_tokens
        try:
            return _parse_json(_text_from_generate(_post(url, key, {"contents": contents, "generationConfig": gen_cfg}, timeout)))
        except GeminiError as e:
            msg = str(e)
            if _is_key_error(msg):
                raise GeminiError("APIキーが無効です。.env の GEMINI_API_KEY を確認してください。（" + msg[:200] + "）") from None
            if msg.startswith("HTTP 402"):
                raise GeminiError("Gemini の前払いクレジットが残っていません。（HTTP 402）") from None
            if msg.startswith("接続できませんでした"):
                raise  # つながらない時に別の窓口を試しても待ち時間が倍になるだけ
            if msg.startswith("HTTP 400") and i + 1 < len(levels):
                continue
            errors.append("generateContent: " + msg)
            break

    ibody = {"model": model,
             "input": [{"type": "text", "text": prompt}, {"type": "image", "data": b64, "mime_type": "image/jpeg"}],
             "response_format": {"type": "text", "mime_type": "application/json", "schema": _lower_types(schema)}}
    if minimal_thinking:
        ibody["generation_config"] = {"thinking_level": "low"}
    try:
        return _parse_json(_text_from_interaction(_post(f"{API_ROOT}/interactions", key, ibody, timeout)))
    except GeminiError as e:
        errors.append("interactions: " + str(e))
    raise GeminiError("\n".join(errors))


# ---------------------------------------------------------------- 主役の物

SEGMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {"boxes": {"type": "ARRAY", "items": {
        "type": "OBJECT",
        "properties": {
            "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"},
                       "description": "[ymin, xmin, ymax, xmax] normalized to 0-1000"},
            "label": {"type": "STRING"},
        },
        "required": ["box_2d", "label"],
    }}},
    "required": ["boxes"],
}

SEGMENT_PROMPT = """\
This photo was taken to "observe" one everyday physical object.
Choose exactly ONE object: the main subject being shown (large, in focus, near
the center). Ignore hands holding it, walls, tables, floors and background.
Return JSON {"boxes": [...]} with one entry: the 2D bounding box of that
single object in the key "box_2d" ([ymin, xmin, ymax, xmax] normalized to
0-1000; include the whole object), and a short Japanese name of the object in
the key "label" (e.g. "エナジードリンクの缶", "ノートパソコン").
If there is no clear physical object, return {"boxes": []}.
"""


def segment(cfg: dict, jpeg: bytes) -> dict | None:
    # 輪郭（点の並び）は頼まない：返事が長くなり時間切れの原因になる。モザイクは四角で足りる
    data = ask_json(cfg, SEGMENT_PROMPT, jpeg, SEGMENT_SCHEMA, minimal_thinking=True, timeout=45, max_tokens=512)
    boxes = data.get("boxes") if isinstance(data, dict) else data
    valid = []
    for b in boxes or []:
        try:
            y0, x0, y1, x1 = [float(v) for v in b["box_2d"][:4]]
            if len(b["box_2d"]) >= 4:
                valid.append((abs(y1 - y0) * abs(x1 - x0), b))
        except (TypeError, ValueError, KeyError):
            continue
    return max(valid, key=lambda v: v[0])[1] if valid else None


# ---------------------------------------------------------------- イデア

IDEA_FIELDS = {
    "word": "イデアを表す日本語の名詞1語",
    "reading": "ひらがなの読み",
    "greek": "対応する古代ギリシャ語（多音調表記）",
    "greek_reading": "古代ギリシャ語のカタカナ読み",
    "definition": "辞書風の定義文",
    "participation": "この物体がそのイデアをどう分有しているか",
}

IDEA_PROMPT = """\
あなたはプラトンのイデア論に通じた辞書編纂者です。

プラトンによれば、目に見える個々の事物は、永遠不変の「イデア（形相）」の不完全な写しであり、
事物はイデアを「分有（メテクシス）」することで、そのものとして存在しています。
（例：美しいものは「美そのもの」を分有するから美しい。大工は「寝台のイデア」を見て寝台を作る。）

写真の中の「{label}」を観測してください。
色・形・ブランド・素材といった感覚でとらえられる性質ではなく、
「それがそれであるための本質」にまでさかのぼり、この物が分有しているイデアを答えてください。

規則:
- word: そのイデアを表す日本語の名詞を1語だけ。漢字2〜3字が望ましい（例：時計→「時間」、椅子→「休息」、上着→「庇護」、灯り→「光明」）。
  物の名前そのもの（「缶」「パソコン」など）や、商品名・ブランド名は不可。
- reading: ひらがなの読み。
- greek: そのイデアに対応する古代ギリシャ語の名詞を1語（多音調のアクセント記号付き）。
- greek_reading: その古代ギリシャ語のカタカナ読み。
- definition: 国語辞典の語釈の文体で、イデアそのものを定義する。40〜70字、1〜2文、「〜こと。」「〜もの。」などで終える。
  皮肉・冗談・ひねった比喩は入れず、静かで格調ある文にする。物の名前は出さない。
- participation: 「この{label}は、〜を分有している。」の形で、物とイデアのつながりを30〜50字で述べる。
"""

QUEST_PROMPT = """
さらに、この物は『{quest}』のイデアを分有しているか。物の本来のはたらき・あり方が、そのイデアに確かに与っているときだけ真。こじつけは偽。
- quest_match: 真偽
- quest_reason: 30〜50字で、なぜそう判定したかを書く。
"""


def _idea_schema(with_quest: bool) -> dict:
    props = {k: {"type": "STRING", "description": d} for k, d in IDEA_FIELDS.items()}
    required = list(IDEA_FIELDS)
    if with_quest:
        props["quest_match"] = {"type": "BOOLEAN"}
        props["quest_reason"] = {"type": "STRING"}
        required += ["quest_match", "quest_reason"]
    return {"type": "OBJECT", "properties": props, "required": required}


def idealize(cfg: dict, jpeg: bytes, label: str, quest: str | None = None) -> dict:
    label = (label or "物体").strip()[:40]
    prompt = IDEA_PROMPT.format(label=label) + (QUEST_PROMPT.format(quest=quest) if quest else "")
    data = ask_json(cfg, prompt, jpeg, _idea_schema(bool(quest)), minimal_thinking=False, timeout=60)

    idea = {k: str(data.get(k) or "").strip() for k in IDEA_FIELDS}
    idea["word"] = idea["word"].strip("【】「」『』 　")[:8]
    if not idea["word"] or not idea["definition"]:
        raise GeminiError("イデアの単語が得られませんでした")
    if quest:
        idea["quest"] = {"word": quest, "match": data.get("quest_match") is True,
                         "reason": str(data.get("quest_reason") or "").strip()}
    return idea
