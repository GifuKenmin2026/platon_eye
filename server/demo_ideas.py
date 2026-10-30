"""お試しモード（APIキーなし）で使うイデア。物を消す処理は本物が動く。"""
from __future__ import annotations

import os
import random

IDEAS = [
    ("時間", "じかん", "χρόνος", "クロノス", "過ぎ去るものすべてを一つの流れのうちに並べ、前と後とを分かつはたらきそのもの。"),
    ("休息", "きゅうそく", "ἀνάπαυσις", "アナパウシス", "動きつづけるものが働きを止め、ふたたび動くための力を内に満たす状態そのもの。"),
    ("庇護", "ひご", "σκέπη", "スケペー", "外からの厳しさをさえぎり、内にあるものをそのままに保つはたらきそのもの。"),
    ("光明", "こうみょう", "φῶς", "ポース", "見えないものを見えるものにし、事物をそれ本来の姿で現れさせる明るさそのもの。"),
    ("保持", "ほじ", "φυλακή", "ピュラケー", "移ろいやすいものをひとところにとどめ、失われないように守ること。"),
    ("伝達", "でんたつ", "ἀγγελία", "アンゲリアー", "ある心のうちにあるものを、隔たりを越えて別の心へと届けるはたらきそのもの。"),
    ("記憶", "きおく", "μνήμη", "ムネーメー", "過ぎ去ったものを消えないように留め、必要なときにふたたび現前させる力そのもの。"),
    ("活力", "かつりょく", "ἐνέργεια", "エネルゲイア", "可能なものを現実のはたらきへと移し、生きるものを内側から動かす力そのもの。"),
    ("調和", "ちょうわ", "ἁρμονία", "ハルモニアー", "異なるものどうしが互いを損なわず、一つの全体としてふさわしく結び合うこと。"),
    ("美", "び", "κάλλος", "カッロス", "それに触れたものを美しいものたらしめる、変わることも衰えることもない輝きそのもの。"),
]

DEMO_REASON = "お試しモードのため判定は無作為です。"


def demo_idea(label: str, quest: str | None = None, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    word, reading, greek, greek_reading, definition = rng.choice(IDEAS)
    idea = {
        "word": word, "reading": reading, "greek": greek, "greek_reading": greek_reading,
        "definition": definition, "participation": f"この{label}は、{word}を分有している。",
    }
    if quest:
        # 確認用：PLATON_DEMO_MATCH=always / never で判定を固定できる
        forced = os.environ.get("PLATON_DEMO_MATCH", "").lower()
        match = True if forced == "always" else False if forced == "never" else rng.random() < 0.5
        idea["quest"] = {"word": quest, "match": match, "reason": DEMO_REASON}
    return idea
