// 分析中の画面：イデア論のひとことを約4秒ごとに入れ替える
// （プラトンの言葉そのままではなく、考えを短く言い直したもの）
import { $, hooks } from "./ui.js";

export const SAYINGS = [
  "目に見える物は、イデアの影にすぎない。",
  "洞窟の囚人は、壁に映る影を本物だと思っている。",
  "美しい物はみな、「美そのもの」を分有している。",
  "大工は「寝台のイデア」を見て、寝台をつくる。",
  "学ぶとは、魂がかつて見たイデアを思い出すこと。",
  "物は移ろう。イデアは移ろわない。",
];

let timer = null;
let index = Math.floor(Math.random() * SAYINGS.length);

function next() {
  index = (index + 1) % SAYINGS.length;
  $("#analyzing .analyzing-saying").textContent = SAYINGS[index];
}

// プラトンの胸像は web/img/plato.jpg があるときだけ出す
{
  const fig = $("#analyzing .analyzing-bust");
  const img = $("img", fig);
  const reveal = () => { fig.hidden = false; };
  if (img.complete && img.naturalWidth) reveal();
  else img.addEventListener("load", reveal, { once: true });
}

hooks.analyzing = {
  enter() {
    next();
    clearInterval(timer);
    timer = setInterval(next, 4000);
  },
  leave() {
    clearInterval(timer);
    timer = null;
  },
};
