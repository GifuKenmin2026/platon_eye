// ブラウザで開くだけの小さなテスト。結果は #out に「PASS n / FAIL n」
const cases = [];
export const test = (name, fn) => cases.push([name, fn]);
export function eq(actual, expected, msg = "") {
  if (actual !== expected) throw new Error(`${msg} 期待 ${JSON.stringify(expected)} / 実際 ${JSON.stringify(actual)}`);
}
export function near(actual, expected, eps = 1e-6) {
  if (Math.abs(actual - expected) > eps) throw new Error(`期待 ${expected} / 実際 ${actual}`);
}

// ---------------------------------------------------------------- compose.js
const compose = await import("../compose.js");

test("wordFontSize: 2字はいちばん狭い制約（物の幅）で決まる", () => {
  near(compose.wordFontSize(1280, 720, { w: 0.14, h: 0.58 }, 2), 80.64, 1e-3);
});
test("wordFontSize: 細い物で8字なら下限（短辺×0.06）", () => {
  near(compose.wordFontSize(1280, 720, { w: 0.05, h: 0.58 }, 8), 43.2, 1e-3);
});
test("wordFontSize: 大きな物は短辺×0.22 が上限", () => {
  near(compose.wordFontSize(1280, 720, { w: 0.9, h: 0.9 }, 1), 158.4, 1e-3);
});

// ---------------------------------------------------------------- db.js
const db = await import("../db.js");
db.useDbName("platon-eye-test");
const blob = () => new Blob(["x"], { type: "image/jpeg" });

async function fresh() {
  await db.clearIdeas();
  await db.clearRecords();
}

test("db: 図鑑は新しい順に並ぶ", async () => {
  await fresh();
  const a = await db.addIdea({ word: "時間", createdAt: 1, idea: blob(), original: blob() });
  const b = await db.addIdea({ word: "庇護", createdAt: 2, idea: blob(), original: blob() });
  const list = await db.listIdeas();
  eq(list.length, 2);
  eq(list[0].id, b);
  eq(list[1].id, a);
  eq((await db.getIdea(a)).word, "時間");
});
test("db: 1件消せる", async () => {
  await fresh();
  const a = await db.addIdea({ word: "時間", createdAt: 1 });
  await db.addIdea({ word: "美", createdAt: 2 });
  await db.deleteIdea(a);
  eq((await db.listIdeas()).map((i) => i.word).join(), "美");
});
test("db: 図鑑を全部消してもランキングは残る", async () => {
  await fresh();
  await db.addIdea({ word: "美", createdAt: 1 });
  await db.addRecord({ word: "美", seconds: 10, thumb: blob() });
  await db.clearIdeas();
  eq((await db.listIdeas()).length, 0);
  eq((await db.topRecords("美")).length, 1);
});
test("db: ランキングは秒の小さい順、同じなら先の記録が上、5件まで", async () => {
  await fresh();
  const ids = [];
  for (const s of [30, 12.5, 40, 12.5, 8, 50, 60]) ids.push(await db.addRecord({ word: "庇護", seconds: s }));
  await db.addRecord({ word: "時間", seconds: 1 });
  const top = await db.topRecords("庇護");
  eq(top.map((r) => r.seconds).join(), "8,12.5,12.5,30,40");
  eq(top[1].id, ids[1]);
  eq(top[2].id, ids[3]);
  eq(await db.rankOf("庇護", ids[4]), 1);
  eq(await db.rankOf("庇護", ids[3]), 3);
  eq(await db.rankOf("庇護", ids[6]), 7);
});
test("db: ランキングを消せる", async () => {
  await fresh();
  await db.addRecord({ word: "美", seconds: 3 });
  await db.clearRecords();
  eq((await db.topRecords("美")).length, 0);
});

// ---------------------------------------------------------------- quest.js（純粋関数）
const q = await import("../quest-core.js");

test("remaining: 残り0.9秒は1と表示", () => eq(q.remaining(0, 89100, 90), 1));
test("remaining: 時間を過ぎたら0", () => eq(q.remaining(0, 95000, 90), 0));
test("remaining: 始めた瞬間は制限時間そのもの", () => eq(q.remaining(0, 0, 90), 90));
test("shotCounts: 0.001秒前のシャッターは有効", () => eq(q.shotCounts(0, 89999, 90), true));
test("shotCounts: ちょうど制限時間は無効", () => eq(q.shotCounts(0, 90000, 90), false));
test("elapsedAtShot: 小数1桁", () => eq(q.elapsedAtShot(1000, 13460), 12.5));
test("pickQuest: 前回の語を避ける", () => {
  const list = [{ word: "庇護" }, { word: "時間" }];
  eq(q.pickQuest(list, "庇護", () => 0).word, "時間");
  eq(q.pickQuest(list, "時間", () => 0).word, "庇護");
});
test("pickQuest: 1語しかなければそれ", () => eq(q.pickQuest([{ word: "美" }], "美", () => 0).word, "美"));
test("limitFromUrl: 指定があればそれ", () => eq(q.limitFromUrl("?limit=5"), 5));
test("limitFromUrl: 0 や不正は90", () => {
  eq(q.limitFromUrl("?limit=0"), 90);
  eq(q.limitFromUrl("?limit=abc"), 90);
  eq(q.limitFromUrl("?limit=601"), 90);
  eq(q.limitFromUrl(""), 90);
});

// ---------------------------------------------------------------- api.js（時間切れ）
const api = await import("../api.js");

test("api: 返事が来なければ時間切れのエラー", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = (url, opt) => new Promise((_, reject) =>
    opt.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));
  try {
    await api.transmute(new Blob(["x"]), null, { timeoutMs: 30 });
    throw new Error("エラーにならなかった");
  } catch (e) {
    eq(e instanceof api.ApiError, true, "ApiError");
    eq(e.message.includes("時間がかかりすぎ"), true, e.message);
  } finally {
    globalThis.fetch = realFetch;
  }
});

// ---------------------------------------------------------------- camera.js（エラーの文）
const camera = await import("../camera.js");

test("camera: 他のアプリが使用中なら、そう伝える", () => {
  eq(camera.cameraMessage("NotReadableError").includes("他のアプリ"), true);
});
test("camera: 許可がなければ許可の直し方", () => {
  eq(camera.cameraMessage("NotAllowedError").includes("許可"), true);
});
test("camera: 見つからなければ USB の確認", () => {
  eq(camera.cameraMessage("NotFoundError").includes("USB"), true);
});

// ---------------------------------------------------------------- search.js
const search = await import("../search.js");
const koushin = { word: "交信", reading: "こうしん", label: "スマートフォン", definition: "隔たった存在同士が…" };

test("search: 空の検索はすべて一致", () => eq(search.matchIdea(koushin, "  "), true));
test("search: 語で一致", () => eq(search.matchIdea(koushin, "交"), true));
test("search: 読み（ひらがな）で一致", () => eq(search.matchIdea(koushin, "こうし"), true));
test("search: カタカナでも読みに一致", () => eq(search.matchIdea(koushin, "コウシン"), true));
test("search: 括弧つきでも一致", () => eq(search.matchIdea(koushin, "【交信】"), true));
test("search: 物の名前や定義では一致しない", () => {
  eq(search.matchIdea(koushin, "スマート"), false);
  eq(search.matchIdea(koushin, "隔たった"), false);
});
test("search: 読みが無い札でも落ちない", () => eq(search.matchIdea({ word: "美" }, "び"), false));

// ---------------------------------------------------------------- 実行
const out = document.getElementById("out");
let pass = 0;
const fails = [];
for (const [name, fn] of cases) {
  try { await fn(); pass++; } catch (e) { fails.push(`✗ ${name}: ${e.message}`); }
}
out.textContent = `PASS ${pass} / FAIL ${fails.length}\n` + fails.join("\n");
