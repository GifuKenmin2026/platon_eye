// 探究モード：お題 → 制限時間内に探す → はずれ／達成／時間切れ
import { $, actions, currentScreen, hooks, keymap, show, showError, showIdeaFail } from "./ui.js";
import { ApiError } from "./api.js";
import { analyze, renderReading, saveCurrent, shrink, state as flow } from "./flow.js";
import { elapsedAtShot, limitFromUrl, pickQuest, remaining, shotCounts } from "./quest-core.js";
import { openScroll } from "./scroll.js";
import * as db from "./db.js";

const limit = limitFromUrl(location.search);
let quests = [];
let quest = null;
let lastWord = null;
let startMs = 0;
let timer = null;
let mountCamera = async () => true;

export function useCamera(fn) { mountCamera = fn; }

// ---------------------------------------------------------------- お題の一覧
export async function loadQuests() {
  try {
    const res = await fetch("quests.json");
    const list = await res.json();
    quests = Array.isArray(list) ? list.filter((q) => q && q.word) : [];
  } catch {
    quests = [];
  }
  $("#gate-quest").disabled = !quests.length;
  $("#quest-unavailable").hidden = quests.length > 0;
}

// ---------------------------------------------------------------- 残り時間
const left = () => remaining(startMs, performance.now(), limit);

function stopTimer() {
  clearInterval(timer);
  timer = null;
}

export function stopQuest() {
  stopTimer();
  quest = null;
}

function tick() {
  const n = String(left());
  for (const el of document.querySelectorAll(".q-remain")) el.textContent = n;
  $("#analyzing .analyzing-remain").textContent = `残り ${n} 秒`;
  if (left() === 0 && !flow.busy && ["q-hunt", "q-miss", "idea-fail"].includes(currentScreen())) timeUp();
}

// ---------------------------------------------------------------- 画面
let rankingUrls = [];
async function renderRanking() {
  rankingUrls.forEach((u) => URL.revokeObjectURL(u));
  rankingUrls = [];
  const list = $("#q-intro .q-ranking-list");
  const top = await db.topRecords(quest.word).catch(() => []);
  if (!top.length) {
    const li = document.createElement("li");
    li.className = "q-ranking-empty";
    li.textContent = "まだ記録はありません。最初の探究者になりましょう。";
    list.replaceChildren(li);
    return;
  }
  list.replaceChildren(...top.map((r) => {
    const li = document.createElement("li");
    if (r.thumb instanceof Blob) {
      const img = document.createElement("img");
      img.src = URL.createObjectURL(r.thumb);
      rankingUrls.push(img.src);
      img.alt = "";
      li.append(img);
    }
    const s = document.createElement("span");
    s.textContent = `${r.seconds.toFixed(1)}秒`;
    li.append(s);
    return li;
  }));
}

async function openIntro() {
  if (!quests.length) return;
  stopTimer();
  quest = pickQuest(quests, lastWord);
  lastWord = quest.word;
  const intro = $("#q-intro");
  $(".q-word", intro).textContent = `【${quest.word}】`;
  $(".q-reading", intro).textContent = quest.reading || "";
  $(".q-greek", intro).textContent = quest.greek || "";
  $(".q-rule", intro).textContent = `制限時間は ${limit} 秒。時間内なら何度でも撮り直せます。`;
  await renderRanking();
  show("q-intro");
}

function startHunt() {
  startMs = performance.now();
  $("#q-hunt .q-hunt-word").textContent = `【${quest.word}】`;
  tick();
  timer = setInterval(tick, 250);
  show("q-hunt");
}

function timeUp() {
  stopTimer();
  const t = $("#q-timeup");
  $(".q-timeup-word", t).textContent = `お題は【${quest.word}】でした。`;
  $(".q-examples ul", t).replaceChildren(...(quest.examples || []).slice(0, 3).map((e) => {
    const li = document.createElement("li");
    li.textContent = e;
    return li;
  }));
  show("q-timeup");
}

async function shoot() {
  let cur;
  try {
    $("#analyzing .analyzing-remain").hidden = false;
    cur = await analyze({ quest: quest.word });
  } catch (e) {
    if (left() === 0) return timeUp();
    if (e instanceof ApiError) return showIdeaFail(e.message, "q-hunt", e.photoUrl);
    return showError(e.message || "観測できませんでした。もう一度撮ってください。", "q-hunt");
  } finally {
    $("#analyzing .analyzing-remain").hidden = true;
  }
  if (!cur) return;
  const verdict = cur.result.quest || { match: false, reason: "" };
  if (verdict.match && shotCounts(startMs, cur.shotAt, limit)) return clear(cur, verdict);
  if (left() === 0) return timeUp();
  miss(cur, verdict);
}

function miss(cur, verdict) {
  const m = $("#q-miss");
  renderReading($(".reading-room", m), { idea: cur.result.idea, originalUrl: cur.originalUrl, ideaUrl: cur.ideaUrl });
  $(".q-verdict-text", m).textContent = `この物は【${quest.word}】を分有していません。`;
  $(".q-reason", m).textContent = verdict.reason;
  tick();
  show("q-miss");
}

async function clear(cur, verdict) {
  stopTimer();
  const seconds = elapsedAtShot(startMs, cur.shotAt);
  let rank = 0;
  try {
    const id = await db.addRecord({ word: quest.word, seconds, thumb: await shrink(cur.originalUrl, 240) });
    rank = await db.rankOf(quest.word, id);
  } catch { /* 記録できなくても達成は見せる */ }
  const c = $("#q-clear");
  $(".q-seconds", c).textContent = `${seconds.toFixed(1)}秒`;
  $(".q-rank", c).textContent = rank ? `『${quest.word}』の ${rank}位` : "";
  $(".q-reason", c).textContent = verdict.reason;
  renderReading($(".reading-room", c), { idea: cur.result.idea, originalUrl: cur.originalUrl, ideaUrl: cur.ideaUrl });
  c.dataset.seconds = seconds;
  show("q-clear");
}

// ---------------------------------------------------------------- 操作
actions.quest = () => openIntro();
actions["quest-start"] = () => startHunt();
actions["quest-shoot"] = () => shoot();
actions["quest-again"] = () => show("q-hunt");
actions["quest-save"] = async () => {
  try {
    const id = await saveCurrent({ questWord: quest.word, questSeconds: Number($("#q-clear").dataset.seconds) });
    stopQuest();
    openScroll(id);
  } catch {
    showError("図鑑に保存できませんでした。ブラウザの空き容量を確認してください。");
  }
};
actions["clear-records"] = async () => {
  if (!confirm("探究のランキングをすべて消します。よろしいですか？")) return;
  await db.clearRecords();
};

keymap["q-intro"] = { Space: () => startHunt(), Enter: () => startHunt(), Escape: () => show("title") };
keymap["q-hunt"] = { Space: () => shoot(), Enter: () => shoot(), Escape: () => show("title") };
keymap["q-miss"] = { Space: () => show("q-hunt"), Enter: () => show("q-hunt"), Escape: () => show("title") };
keymap["q-clear"] = { y: () => actions["quest-save"](), n: () => show("title") };
keymap["q-timeup"] = { "*": () => show("title") };

hooks["q-hunt"] = {
  enter: async () => {
    if (!quest) return show("title");
    if (left() === 0) return timeUp();
    await mountCamera("q-hunt");
  },
};
