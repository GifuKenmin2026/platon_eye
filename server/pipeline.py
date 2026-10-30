"""1枚の写真を処理する流れ：主役を見つける → 消す → イデアを想起する"""
from __future__ import annotations

import os
import time

import gemini
import vision
from demo_ideas import demo_idea


class UserFacingError(Exception):
    """画面にそのまま出す説明"""


def _user_message(err: gemini.GeminiError) -> str:
    msg = str(err)
    if "クレジット" in msg:
        return "Gemini の利用料の残高がありません。係の人は AI Studio（ai.studio/projects）で残高を追加してください。"
    if "APIキー" in msg:
        return "APIキーが使えません。.env の GEMINI_API_KEY を確認して、start.bat を起動し直してください。"
    if "接続できませんでした" in msg:
        return "インターネットにつながっていません。接続を確認して、もう一度撮ってください。"
    if any(f"HTTP {code}" in msg for code in (429, 502, 503, 504)):
        return "イデアの世界が混み合っています。少し待って、もう一度撮ってください。"
    return "イデアを取り出せませんでした。もう一度撮ってください。（" + msg.splitlines()[0][:120] + "）"


def _log_error(step: str, err: Exception, since: float) -> None:
    """係員が原因を調べられるよう、サーバーの窓に理由と待ち時間を出す"""
    reason = " / ".join(line.strip() for line in str(err).splitlines() if line.strip())[:400]
    print(f"[Gemini エラー] {step}（{time.perf_counter() - since:.1f}秒）: {reason}", flush=True)


def transmute(jpeg: bytes, cfg: dict, quest: str | None = None) -> dict:
    t0 = time.perf_counter()
    img = vision.limit_size(vision.decode_image(jpeg), 1600)
    small = vision.encode_jpeg(vision.limit_size(img, 1024), 88)

    target, label = None, "物体"
    if not cfg["demo"]:
        try:
            target = gemini.segment(cfg, small)
        except gemini.GeminiError as e:
            _log_error("輪郭", e, t0)
            if "APIキー" in str(e) or "クレジット" in str(e):
                raise UserFacingError(_user_message(e)) from None
            target = None  # GrabCut で続ける
        if target and target.get("label"):
            label = str(target["label"]).strip()[:40] or label

    t1 = time.perf_counter()
    erased = vision.erase_object(img, target)
    t2 = time.perf_counter()

    if cfg["demo"]:
        delay = os.environ.get("PLATON_DEMO_DELAY")  # 確認用：分析の待ち時間をまねる
        if delay:
            time.sleep(float(delay))
        idea = demo_idea(label, quest)
    else:
        t_idea = time.perf_counter()
        try:
            idea = gemini.idealize(cfg, small, label, quest=quest)
        except gemini.GeminiError as e:
            _log_error("イデア", e, t_idea)
            raise UserFacingError(_user_message(e)) from None
    t3 = time.perf_counter()

    quest_result = idea.pop("quest", None)
    print(f"[観測] {label} → 【{idea['word']}】 {erased['mask_method']} "
          f"検出{t1 - t0:.1f}s 消去{t2 - t1:.1f}s 想起{t3 - t2:.1f}s"
          + (f" 探究『{quest}』={'当たり' if quest_result and quest_result['match'] else 'はずれ'}" if quest else ""),
          flush=True)

    result = {
        "ok": True,
        "mode": "demo" if cfg["demo"] else "gemini",
        "label": label,
        "idea": idea,
        "anchor": erased["anchor"],
        "mask_method": erased["mask_method"],
        "original": vision.to_data_url(img, 88),
        "erased": vision.to_data_url(erased["erased"], 90),
        "seconds": round(t3 - t0, 1),
    }
    if quest:
        result["quest"] = quest_result or {"word": quest, "match": False, "reason": ""}
    return result
