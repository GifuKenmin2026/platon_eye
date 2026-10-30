// 図鑑：横に長い巻物と、詳しい表示
import { $, actions, keymap, show, showError } from "./ui.js";
import * as db from "./db.js";
import { matchIdea } from "./search.js";

const EMPTY = "まだ何も収められていません。観測して最初のイデアを収めましょう。";
let urls = [];
let shown = null;   // 詳しい表示中のイデア
let all = [];        // 図鑑のすべてのイデア（検索の元）
let highlight = null;

const track = () => $("#scroll .scroll-track");
const searchBox = () => $("#scroll-search");

function objectUrl(blob) {
  if (!(blob instanceof Blob)) return "";
  const u = URL.createObjectURL(blob);
  urls.push(u);
  return u;
}

const dateText = (ms) =>
  new Intl.DateTimeFormat("ja-JP", { dateStyle: "long", timeStyle: "short" }).format(new Date(ms));

function seal(idea) {
  return idea.questWord ? `探究達成　『${idea.questWord}』 ${Number(idea.questSeconds).toFixed(1)}秒` : "";
}

export function renderScroll(el, ideas, highlightId, { total = ideas.length, query = "" } = {}) {
  urls.forEach((u) => URL.revokeObjectURL(u));
  urls = [];
  const count = $(".scroll-count", el.closest(".screen"));
  count.textContent = query.trim() ? `${ideas.length} / ${total} 件` : (total ? `${total} のイデアを収蔵` : "");
  if (!ideas.length) {
    const p = document.createElement("p");
    p.className = "scroll-empty";
    p.textContent = query.trim() && total ? `『${query.trim()}』のイデアはまだ収められていません。` : EMPTY;
    el.replaceChildren(p);
    return;
  }
  el.replaceChildren(...ideas.map((idea) => {
    const card = document.createElement("button");
    card.className = "card" + (idea.id === highlightId ? " new" : "");
    card.dataset.action = "open-card";
    card.dataset.id = idea.id;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.decoding = "async";
    img.src = objectUrl(idea.thumb || idea.idea);
    img.alt = "";
    const word = document.createElement("span");
    word.className = "card-word";
    word.textContent = `【${idea.word}】`;
    const reading = document.createElement("span");
    reading.className = "card-reading";
    reading.textContent = idea.reading || "";
    card.append(img, word, reading);
    if (idea.questWord) {
      const mark = document.createElement("span");
      mark.className = "card-seal";
      mark.textContent = "探究達成";
      card.append(mark);
    }
    if (idea.id === highlightId) {
      const mark = document.createElement("span");
      mark.className = "card-new";
      mark.textContent = "いま収めた";
      card.append(mark);
    }
    return card;
  }));
}

function refresh() {
  const query = searchBox().value;
  renderScroll(track(), all.filter((i) => matchIdea(i, query)), highlight, { total: all.length, query });
  track().scrollLeft = 0;
}

export async function openScroll(highlightId) {
  try {
    all = await db.listIdeas();
  } catch {
    return showError("図鑑を読み込めませんでした。ブラウザを開き直してください。");
  }
  highlight = highlightId ?? null;
  searchBox().value = "";
  refresh();
  show("scroll");
}

export function openDetail(idea) {
  shown = idea;
  const d = $("#detail");
  $(".idea", d).src = objectUrl(idea.idea);
  $(".original", d).src = objectUrl(idea.original);
  $(".headword", d).textContent = `【${idea.word}】`;
  $(".reading", d).textContent = idea.reading || "";
  $(".greek", d).textContent = idea.greek || "";
  $(".greek-reading", d).textContent = idea.greekReading || "";
  $(".definition", d).textContent = idea.definition || "";
  $(".participation", d).textContent = idea.participation || "";
  $(".seal", d).textContent = seal(idea);
  $(".seal", d).hidden = !idea.questWord;
  $(".detail-original figcaption", d).textContent = `観測した物　${dateText(idea.createdAt)}`;
  show("detail");
}

export function closeDetail() {
  shown = null;
  show("scroll");
}

// ---------------------------------------------------------------- 操作
actions.scroll = () => openScroll();
actions["open-card"] = async (el) => {
  const idea = await db.getIdea(Number(el.dataset.id));
  if (idea) openDetail(idea);
};
actions["close-detail"] = () => closeDetail();
actions["delete-card"] = async () => {
  if (!shown || !confirm(`【${shown.word}】の記録を消します。よろしいですか？`)) return;
  await db.deleteIdea(shown.id);
  shown = null;
  await openScroll();
};
actions["clear-ideas"] = async () => {
  if (!confirm("図鑑のイデアをすべて消します。探究のランキングは残ります。よろしいですか？")) return;
  await db.clearIdeas();
  await openScroll();
};

const step = () => track().clientWidth * 0.6;
keymap.scroll = {
  // 1回目の Esc で検索を消し、検索が空ならタイトルへ
  Escape: () => {
    if (searchBox().value) {
      searchBox().value = "";
      refresh();
      searchBox().blur();
    } else {
      show("title");
    }
  },
  f: () => searchBox().focus(),
  ArrowRight: () => track().scrollBy({ left: step() }),
  ArrowLeft: () => track().scrollBy({ left: -step() }),
};
keymap.detail = { Escape: () => closeDetail() };

// 縦のホイールを横送りに
track().addEventListener("wheel", (e) => {
  if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
  e.preventDefault();
  track().scrollLeft += e.deltaY;
}, { passive: false });

searchBox().addEventListener("input", () => refresh());
