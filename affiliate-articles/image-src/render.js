// 記事用画像を HTML/CSS + SVG でデザインし、Playwright で PNG に書き出すスクリプト。
// 使い方:  node image-src/render.js   (affiliate-articles フォルダで実行)
// フォント: image-src/fonts/ に Noto Sans JP(woff2)を置くと使用します。
//           無い場合は `npm pack @fontsource/noto-sans-jp@5.0.19` で取得し、
//           files/noto-sans-jp-{japanese,latin}-{400,700,900}-normal.woff2 をコピーしてください。
//           見つからない場合は、システムの日本語フォント(IPAゴシック等)で描画します。
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const FONT_DIR = path.join(__dirname, 'fonts');
const OUT_DIR = path.join(__dirname, '..', 'images');

function fontFaces() {
  let css = '';
  for (const w of [400, 700, 900]) {
    for (const sub of ['latin', 'japanese']) {
      const f = path.join(FONT_DIR, `noto-sans-jp-${sub}-${w}-normal.woff2`);
      if (fs.existsSync(f)) {
        const b64 = fs.readFileSync(f).toString('base64');
        css += `@font-face{font-family:'NotoJP';font-weight:${w};src:url(data:font/woff2;base64,${b64}) format('woff2');}\n`;
      }
    }
  }
  return css;
}

// 落ち着いた青系のパレット
const C = {
  bg: '#F3F7FB', navy: '#17365A', blue: '#2C6AA0', mid: '#5E8FBF',
  light: '#DCE9F5', pale: '#EDF4FB', text: '#1D2B3A', sub: '#4A5B6E', line: '#B9CFE4',
};

const BASE_CSS = `
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%}
body{font-family:'NotoJP','IPAGothic','WenQuanYi Zen Hei',sans-serif;color:${C.text};background:${C.bg};
  -webkit-font-smoothing:antialiased;overflow:hidden}
.pr{position:absolute;right:28px;bottom:18px;font-size:18px;color:${C.sub};letter-spacing:.1em;
  border:1.5px solid ${C.line};border-radius:4px;padding:1px 8px;background:#fff}
.frame{position:absolute;inset:0;padding:56px 64px}
.title{font-weight:900;color:${C.navy};letter-spacing:.02em}
.note{position:absolute;left:64px;bottom:22px;font-size:18px;color:${C.sub}}
`;

// シンプルなアイコン(SVG)
const ICON = {
  company: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><rect x="12" y="14" width="40" height="40" rx="3" fill="none" stroke="${c}" stroke-width="4"/><path d="M20 24h6M30 24h6M40 24h4M20 33h6M30 33h6M40 33h4" stroke="${c}" stroke-width="4" stroke-linecap="round"/><rect x="27" y="42" width="10" height="12" fill="${c}"/></svg>`,
  hub: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><circle cx="32" cy="32" r="9" fill="${c}"/><circle cx="12" cy="16" r="6" fill="none" stroke="${c}" stroke-width="4"/><circle cx="52" cy="16" r="6" fill="none" stroke="${c}" stroke-width="4"/><circle cx="12" cy="48" r="6" fill="none" stroke="${c}" stroke-width="4"/><circle cx="52" cy="48" r="6" fill="none" stroke="${c}" stroke-width="4"/><path d="M17 20l9 7M47 20l-9 7M17 44l9-7M47 44l-9-7" stroke="${c}" stroke-width="4"/></svg>`,
  writer: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><rect x="10" y="12" width="44" height="32" rx="3" fill="none" stroke="${c}" stroke-width="4"/><path d="M18 22h28M18 30h20" stroke="${c}" stroke-width="4" stroke-linecap="round"/><path d="M24 52h16M32 44v8" stroke="${c}" stroke-width="4" stroke-linecap="round"/></svg>`,
  reader: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><circle cx="32" cy="22" r="10" fill="none" stroke="${c}" stroke-width="4"/><path d="M14 54c2-11 9-17 18-17s16 6 18 17" fill="none" stroke="${c}" stroke-width="4" stroke-linecap="round"/></svg>`,
  book: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><path d="M32 16c-6-4-14-5-22-4v36c8-1 16 0 22 4 6-4 14-5 22-4V12c-8-1-16 0-22 4z" fill="none" stroke="${c}" stroke-width="4" stroke-linejoin="round"/><path d="M32 16v36" stroke="${c}" stroke-width="4"/></svg>`,
  video: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><rect x="8" y="14" width="48" height="34" rx="4" fill="none" stroke="${c}" stroke-width="4"/><path d="M27 23v16l13-8z" fill="${c}"/><path d="M22 54h20" stroke="${c}" stroke-width="4" stroke-linecap="round"/></svg>`,
  seminar: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><rect x="16" y="8" width="40" height="26" rx="3" fill="none" stroke="${c}" stroke-width="4"/><circle cx="14" cy="38" r="6" fill="none" stroke="${c}" stroke-width="4"/><path d="M4 58c1-7 5-11 10-11s9 4 10 11" fill="none" stroke="${c}" stroke-width="4" stroke-linecap="round"/><path d="M22 40l10-10" stroke="${c}" stroke-width="4" stroke-linecap="round"/></svg>`,
  clock: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><circle cx="32" cy="32" r="22" fill="none" stroke="${c}" stroke-width="4"/><path d="M32 18v14l9 6" fill="none" stroke="${c}" stroke-width="4" stroke-linecap="round"/></svg>`,
  check: (c = C.blue) => `<svg viewBox="0 0 64 64" width="100%" height="100%"><circle cx="32" cy="32" r="24" fill="${c}"/><path d="M21 33l8 8 15-17" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
};

const arrowR = (w = 60, c = C.mid) => `<svg width="${w}" height="28" viewBox="0 0 ${w} 28"><path d="M2 14H${w - 14}" stroke="${c}" stroke-width="4"/><path d="M${w - 18} 4l14 10-14 10z" fill="${c}"/></svg>`;

// ---------------------------------------------------------------- 画像定義
const images = [];

// 1. Ameba 見出し画像
images.push({
  file: 'ameba-01-header.png', w: 1200, h: 630, html: `
<div class="frame" style="background:linear-gradient(135deg,#FFFFFF 0%,${C.pale} 55%,${C.light} 100%)">
  <div style="position:absolute;right:-90px;top:-90px;width:420px;height:420px;border-radius:50%;background:${C.light};opacity:.7"></div>
  <div style="position:absolute;right:60px;bottom:-140px;width:300px;height:300px;border-radius:50%;background:${C.light};opacity:.5"></div>
  <div style="position:relative;display:inline-block;background:${C.navy};color:#fff;font-size:26px;font-weight:700;padding:8px 22px;border-radius:6px;letter-spacing:.08em">はじめての方向け 解説</div>
  <div class="title" style="position:relative;font-size:76px;line-height:1.2;margin-top:40px">アフィリエイトとは?</div>
  <div style="position:relative;font-size:38px;font-weight:700;color:${C.blue};line-height:1.55;margin-top:22px">仕組み・広告アフィの基本・<br>学び方の選択肢を、やさしく整理</div>
  <div style="position:absolute;right:70px;top:250px;display:grid;grid-template-columns:110px 110px;gap:22px">
    ${['company', 'hub', 'writer', 'reader'].map(k => `<div style="width:110px;height:110px;background:#fff;border-radius:22px;padding:20px;box-shadow:0 6px 18px rgba(23,54,90,.10)">${ICON[k]()}</div>`).join('')}
  </div>
  <div style="position:absolute;left:64px;bottom:48px;width:120px;height:6px;background:${C.blue};border-radius:3px"></div>
</div>
<div class="pr">PR</div>`,
});

// 2. note 見出し画像
images.push({
  file: 'note-01-header.png', w: 1280, h: 670, html: `
<div class="frame" style="background:${C.navy};padding:96px 72px">
  <div style="position:absolute;inset:0;background:radial-gradient(circle at 85% 20%, rgba(94,143,191,.45), transparent 45%),radial-gradient(circle at 10% 110%, rgba(44,106,160,.6), transparent 50%)"></div>
  <div style="position:relative;color:${C.light};font-size:30px;font-weight:700;letter-spacing:.06em">本業の合間に学び始める前に</div>
  <div style="position:relative;color:#fff;font-size:76px;font-weight:900;line-height:1.3;margin-top:22px">知っておきたい<br><span style="color:#BFD8F0">5つ</span>のこと</div>
  <div style="position:relative;display:flex;gap:18px;margin-top:60px">
    ${['期待値', 'お金の上限', '用語', 'スキマ時間', '見極め'].map((t, i) => `
      <div style="display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.10);border:1.5px solid rgba(255,255,255,.28);border-radius:40px;padding:10px 22px 10px 10px">
        <span style="width:40px;height:40px;border-radius:50%;background:#fff;color:${C.navy};font-weight:900;font-size:22px;display:flex;align-items:center;justify-content:center">${i + 1}</span>
        <span style="color:#fff;font-size:26px;font-weight:700">${t}</span></div>`).join('')}
  </div>
  <div style="position:absolute;right:80px;top:70px;width:170px;height:170px;opacity:.9">${ICON.clock('#BFD8F0')}</div>
</div>
<div class="pr" style="background:transparent;color:#BFD8F0;border-color:rgba(191,216,240,.5)">PR</div>`,
});

// 3. 図解:アフィリエイトの仕組み(4者の流れ)
const node = (icon, name, desc) => `
  <div style="width:210px;text-align:center">
    <div style="width:130px;height:130px;margin:0 auto;background:#fff;border:3px solid ${C.line};border-radius:26px;padding:24px">${ICON[icon]()}</div>
    <div style="font-size:32px;font-weight:900;color:${C.navy};margin-top:14px">${name}</div>
    <div style="font-size:20px;color:${C.sub};margin-top:4px;line-height:1.4">${desc}</div>
  </div>`;
const stepLabel = (n, t) => `<div style="font-size:20px;font-weight:700;color:${C.blue};text-align:center;line-height:1.35;width:120px"><span style="display:inline-block;width:30px;height:30px;line-height:30px;border-radius:50%;background:${C.blue};color:#fff;font-size:17px;margin-bottom:4px">${n}</span><br>${t}</div>`;
images.push({
  file: 'diagram-01.png', w: 1200, h: 675, html: `
<div class="frame" style="background:#fff">
  <div class="title" style="font-size:46px">アフィリエイトの仕組み</div>
  <div style="font-size:24px;color:${C.sub};margin-top:8px">広告主・ASP・発信者・読者の4者で成り立つ、成果報酬型の広告です</div>
  <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-top:46px">
    ${node('company', '広告主', '商品を<br>売りたい企業')}
    <div style="margin-top:28px">${stepLabel('1', '広告を<br>登録')}${arrowR(110)}</div>
    ${node('hub', 'ASP', '広告主と発信者を<br>つなぐ仲介会社')}
    <div style="margin-top:28px">${stepLabel('2', 'リンクを<br>受け取り紹介')}${arrowR(110)}</div>
    ${node('writer', '発信者', '商品を<br>紹介する人')}
    <div style="margin-top:28px">${stepLabel('3', 'リンクから<br>購入・申込み')}<svg width="110" height="28" viewBox="0 0 110 28"><path d="M108 14H16" stroke="${C.mid}" stroke-width="4"/><path d="M18 4L4 14l14 10z" fill="${C.mid}"/></svg></div>
    ${node('reader', '読者', '紹介を見て<br>行動する人')}
  </div>
  <div style="margin:30px auto 0;width:960px;background:${C.pale};border:2px dashed ${C.mid};border-radius:14px;padding:14px 22px;display:flex;align-items:center;gap:16px;font-size:24px;color:${C.navy};font-weight:700">
    <span style="flex:none;width:34px;height:34px;line-height:34px;text-align:center;border-radius:50%;background:${C.blue};color:#fff;font-size:19px">4</span>
    成果が確認されると、ASPを通じて、広告主から発信者へ報酬が支払われます
  </div>
</div>
<div class="pr">PR</div>`,
});

// 4. 図解:学び方の選択肢の比較
const col = (icon, name, rows, accent) => `
  <div style="flex:1;background:#fff;border-radius:18px;border-top:10px solid ${accent};box-shadow:0 4px 16px rgba(23,54,90,.08);padding:20px 26px 20px">
    <div style="display:flex;align-items:center;gap:14px"><div style="width:62px;height:62px">${ICON[icon](accent)}</div>
      <div style="font-size:38px;font-weight:900;color:${C.navy}">${name}</div></div>
    ${rows.map(([h, t]) => `<div style="margin-top:14px"><div style="font-size:19px;font-weight:700;color:${accent};letter-spacing:.05em">${h}</div>
      <div style="font-size:23px;line-height:1.5;margin-top:4px">${t}</div></div>`).join('')}
  </div>`;
images.push({
  file: 'diagram-02.png', w: 1200, h: 675, html: `
<div class="frame" style="background:${C.bg};padding:36px 56px">
  <div class="title" style="font-size:42px">学び方の選択肢をくらべる</div>
  <div style="font-size:23px;color:${C.sub};margin-top:6px">正解は一つではありません。時間や学びやすさに合わせて組み合わせましょう</div>
  <div style="display:flex;gap:26px;margin-top:24px">
    ${col('book', '本', [['特徴', '基礎から体系的に学べる'], ['向いている人', '自分のペースで<br>読み返したい人'], ['気をつけたい点', '情報が出版時点の<br>ものになる場合がある']], C.navy)}
    ${col('video', '動画', [['特徴', '操作などを目で見て<br>理解しやすい'], ['向いている人', '通勤などのスキマ時間に<br>学びたい人'], ['気をつけたい点', '発信者によって<br>内容の質がさまざま']], C.blue)}
    ${col('seminar', 'セミナー', [['特徴', '講師の説明を<br>まとまった形で聞ける'], ['向いている人', '質問や相談の機会が<br>ほしい人'], ['気をつけたい点', '有料の講座などの案内が<br>ある場合がある']], C.mid)}
  </div>
</div>
<div class="pr">PR</div>`,
});

// 5. 図解(note):学び始める前に知っておきたい5つのこと
const five = [
  ['期待値を整える', '結果には個人差があり、収益は保証されないと理解する'],
  ['お金の上限を決める', '学習費・広告費など、使ってよい金額を先に決める'],
  ['用語はよく出るものから', 'ASP・LP・CPC・CVRなどを少しずつ覚える'],
  ['スキマ時間で学ぶ', '通勤・昼休み・夜の15分を使い分ける'],
  ['情報を見極める', '出どころと表現を確かめ、その場で決めない'],
];
images.push({
  file: 'diagram-03.png', w: 1280, h: 670, html: `
<div class="frame" style="background:#fff;padding:48px 64px">
  <div class="title" style="font-size:44px">学び始める前に知っておきたい5つのこと</div>
  <div style="margin-top:26px;display:flex;flex-direction:column;gap:14px">
    ${five.map(([h, t], i) => `
    <div style="display:flex;align-items:center;gap:22px;background:${i % 2 ? '#fff' : C.pale};border:2px solid ${C.light};border-radius:14px;padding:13px 24px">
      <div style="flex:none;width:54px;height:54px;border-radius:50%;background:${C.navy};color:#fff;font-size:28px;font-weight:900;display:flex;align-items:center;justify-content:center">${i + 1}</div>
      <div style="flex:none;width:370px;font-size:30px;font-weight:900;color:${C.navy}">${h}</div>
      <div style="font-size:24px;color:${C.text}">${t}</div>
    </div>`).join('')}
  </div>
</div>
<div class="pr">PR</div>`,
});

// 6. 図解(note):スキマ時間の学び方
const slot = (time, verb, desc, icon) => `
  <div style="flex:1;background:#fff;border-radius:18px;box-shadow:0 4px 16px rgba(23,54,90,.08);padding:26px 20px;text-align:center">
    <div style="width:70px;height:70px;margin:0 auto">${ICON[icon]()}</div>
    <div style="font-size:24px;color:${C.sub};font-weight:700;margin-top:10px">${time}</div>
    <div style="font-size:44px;font-weight:900;color:${C.navy};margin-top:2px">${verb}</div>
    <div style="font-size:22px;line-height:1.5;margin-top:10px">${desc}</div>
  </div>`;
images.push({
  file: 'diagram-04.png', w: 1280, h: 670, html: `
<div class="frame" style="background:${C.bg};padding:48px 60px">
  <div class="title" style="font-size:44px">スキマ時間で学ぶ、1日の使い分け</div>
  <div style="font-size:24px;color:${C.sub};margin-top:6px">1回の目標は小さく。「用語を2つ覚える」「動画を1本見る」くらいから</div>
  <div style="display:flex;align-items:center;gap:14px;margin-top:34px">
    ${slot('通勤中', '見る', '動画や音声で<br>インプット', 'video')}
    ${arrowR(46)}
    ${slot('昼休み', '書く', '気になった用語や<br>疑問をメモ', 'writer')}
    ${arrowR(46)}
    ${slot('夜の15分', '振り返る', 'メモを読み返し<br>分からない点を調べる', 'clock')}
  </div>
  <div style="margin-top:26px;background:${C.navy};color:#fff;border-radius:14px;padding:16px 26px;font-size:25px;font-weight:700;display:flex;align-items:center;gap:16px">
    <span style="background:#fff;color:${C.navy};border-radius:6px;padding:2px 12px;font-size:21px">週に1回</span>
    1週間のメモを見返し、「分かったこと」と「まだ分からないこと」を分ける
  </div>
</div>
<div class="pr">PR</div>`,
});

// 7. X用:アフィリエイトの仕組み(要点)
images.push({
  file: 'x-01.png', w: 1200, h: 675, html: `
<div class="frame" style="background:linear-gradient(160deg,#fff 0%,${C.pale} 100%);padding:56px 64px">
  <div style="display:inline-block;background:${C.blue};color:#fff;font-size:24px;font-weight:700;padding:6px 18px;border-radius:6px">基本のキ</div>
  <div class="title" style="font-size:56px;margin-top:18px">アフィリエイトは「成果報酬型」の広告</div>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-top:52px;padding:0 10px">
    ${[['company', '広告主'], ['hub', 'ASP'], ['writer', '発信者'], ['reader', '読者']].map(([k, n], i, a) => `
      <div style="text-align:center"><div style="width:140px;height:140px;background:#fff;border:3px solid ${C.line};border-radius:28px;padding:26px">${ICON[k]()}</div>
      <div style="font-size:34px;font-weight:900;color:${C.navy};margin-top:12px">${n}</div></div>
      ${i < a.length - 1 ? arrowR(90) : ''}`).join('')}
  </div>
  <div style="margin-top:40px;font-size:30px;font-weight:700;color:${C.blue};text-align:center">紹介をきっかけに成果が出たとき、報酬が支払われる仕組みです</div>
</div>
<div class="pr">PR</div>`,
});

// 8. X用:広告アフィを始める前に確認したい3つ
images.push({
  file: 'x-02.png', w: 1200, h: 675, html: `
<div class="frame" style="background:${C.navy};padding:76px 70px">
  <div style="color:#BFD8F0;font-size:28px;font-weight:700">広告アフィリエイト(広告アフィ)とは</div>
  <div style="color:#fff;font-size:34px;font-weight:700;margin-top:10px;line-height:1.5">ネット広告を使って、紹介ページへ人を集める方法のこと</div>
  <div style="color:#fff;font-size:52px;font-weight:900;margin-top:44px">始める前に、確認したい3つ</div>
  <div style="display:flex;gap:22px;margin-top:28px">
    ${[['広告費がかかる', '場合があり、赤字になる<br>可能性もあります'], ['上限額を決める', '使ってよい金額を<br>先に決めておきましょう'], ['規約を確認する', '広告媒体やASPの<br>ルールを守りましょう']].map(([h, t]) => `
    <div style="flex:1;background:#fff;border-radius:16px;padding:30px 24px 34px">
      <div style="display:flex;align-items:center;gap:10px"><div style="width:40px;height:40px">${ICON.check()}</div><div style="font-size:30px;font-weight:900;color:${C.navy}">${h}</div></div>
      <div style="font-size:25px;line-height:1.6;margin-top:14px;color:${C.text}">${t}</div>
    </div>`).join('')}
  </div>
  <div style="position:absolute;left:70px;bottom:22px;color:#BFD8F0;font-size:20px">※結果には個人差があります。</div>
</div>
<div class="pr" style="background:transparent;color:#BFD8F0;border-color:rgba(191,216,240,.5)">PR</div>`,
});

// 9. X用:学び方は大きく3つ
images.push({
  file: 'x-03.png', w: 1200, h: 675, html: `
<div class="frame" style="background:#fff;padding:56px 70px">
  <div class="title" style="font-size:56px">アフィリエイトの学び方は、大きく3つ</div>
  <div style="display:flex;flex-direction:column;gap:20px;margin-top:40px">
    ${[['book', '本', '基礎から、体系的に学べる', C.navy], ['video', '動画', 'スキマ時間に、目で見て学べる', C.blue], ['seminar', 'セミナー', 'まとまった説明を聞ける', C.mid]].map(([k, n, t, a]) => `
    <div style="display:flex;align-items:center;gap:26px;background:${C.pale};border-left:12px solid ${a};border-radius:12px;padding:16px 28px">
      <div style="width:66px;height:66px">${ICON[k](a)}</div>
      <div style="width:190px;font-size:42px;font-weight:900;color:${C.navy}">${n}</div>
      <div style="font-size:32px;font-weight:700">${t}</div>
    </div>`).join('')}
  </div>
  <div style="margin-top:28px;font-size:27px;color:${C.blue};font-weight:700">通勤や昼休みの15分から、あなたに合う方法を試してみましょう</div>
</div>
<div class="pr">PR</div>`,
});

// 10. 案内ボタン風画像
images.push({
  file: 'button-01.png', w: 800, h: 200, html: `
<div style="position:absolute;inset:0;background:#fff;display:flex;align-items:center;justify-content:center">
  <div style="width:700px;height:110px;border-radius:55px;background:linear-gradient(180deg,${C.blue} 0%,${C.navy} 100%);box-shadow:0 6px 0 #0F2740, 0 10px 20px rgba(23,54,90,.18);
    display:flex;align-items:center;justify-content:center;gap:18px;color:#fff">
    <div style="width:46px;height:46px;border-radius:50%;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center">
      <svg width="20" height="22" viewBox="0 0 20 22"><path d="M3 2l15 9-15 9z" fill="#fff"/></svg></div>
    <div style="font-size:36px;font-weight:700;letter-spacing:.04em">無料動画セミナーの概要を見る</div>
    <svg width="18" height="28" viewBox="0 0 18 28"><path d="M3 3l11 11L3 25" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </div>
</div>
<div class="pr" style="right:20px;bottom:12px;font-size:15px">PR</div>`,
});

// ---------------------------------------------------------------- 書き出し
(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const css = fontFaces() + BASE_CSS;
  const browser = await chromium.launch();
  for (const img of images) {
    const page = await browser.newPage({ viewport: { width: img.w, height: img.h }, deviceScaleFactor: 1 });
    await page.setContent(`<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>${css}</style></head><body>${img.html}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(OUT_DIR, img.file) });
    await page.close();
    console.log('wrote', img.file, `${img.w}x${img.h}`);
  }
  await browser.close();
})();
