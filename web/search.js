// 図鑑の検索：語と読みで探す（ひらがな・カタカナは同じ扱い）

export function normalize(text) {
  return String(text ?? "")
    .normalize("NFKC")
    .replace(/[【】「」『』\s]/g, "")
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))  // カタカナ → ひらがな
    .toLowerCase();
}

export function matchIdea(idea, query) {
  const q = normalize(query);
  if (!q) return true;
  return normalize(idea.word).includes(q) || normalize(idea.reading).includes(q);
}
