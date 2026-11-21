#!/usr/bin/env python3
"""貼り付け用ファイルを dist/ に出力するスクリプト。

- ameba-01.md / note-01.md:冒頭の `[seminar]: URL` を読み取り、
  `[テキスト][seminar]` を「テキスト URL」形式に展開します(管理用コメントは削除)。
- x-posts.md:冒頭の `SEMINAR_URL: URL` を読み取り、各投稿の {SEMINAR_URL} を置き換えます。
  あわせて、各投稿の文字数(URLは23字として計算)をチェックします。

リンクを変えるときは、各ファイル冒頭の1行だけを書き換えて、このスクリプトを再実行してください。
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)


def body_chars(text: str) -> int:
    """見出し記号・画像指示・空白を除いた、おおよその本文文字数。"""
    t = re.sub(r"【画像:[^】]+】", "", text)
    t = re.sub(r"[#>*\-\s`]", "", t)
    return len(t)


for name in ["ameba-01.md", "note-01.md"]:
    src = (ROOT / name).read_text(encoding="utf-8")
    m = re.search(r"^\[seminar\]:\s*(\S+)\s*$", src, re.M)
    url = m.group(1)
    out = re.sub(r"<!--.*?-->\n*", "", src, flags=re.S)
    out = re.sub(r"^\[seminar\]:.*\n+", "", out, flags=re.M)
    out = re.sub(r"\[([^\]]+)\]\[seminar\]", rf"\1\n{url}", out)
    (DIST / name).write_text(out, encoding="utf-8")
    print(f"{name}: 本文 約{body_chars(out)}字 / リンク {url}")

for xname in ["x-posts", "x-threads"]:
    src = (ROOT / f"{xname}.md").read_text(encoding="utf-8")
    url = re.search(r"^SEMINAR_URL:\s*(\S+)\s*$", src, re.M).group(1)
    posts = re.findall(r"^## (.+?)\n.*?```\n(.*?)```", src, re.S | re.M)
    lines = []
    for title, body in posts:
        body = body.strip()
        count = len(body.replace("{SEMINAR_URL}", "x" * 23))
        expanded = body.replace("{SEMINAR_URL}", url)
        status = "OK" if count <= 140 else "超過"
        print(f"X {title}: {count}字 {status}")
        lines.append(f"===== {title}({count}字) =====\n{expanded}\n")
    (DIST / f"{xname}.txt").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- Ameba用HTML
# Amebaブログの「HTML表示」に貼り付けるHTMLを、ameba-01.md から生成します。
# Amebaでは <style> タグが使えないため、装飾はすべてインラインstyleで指定しています。
import html as _html

S = {
    "h2": "font-size:1.3em;font-weight:bold;color:#17365A;background:#EDF4FB;border-left:6px solid #2C6AA0;padding:0.5em 0.8em;margin:2.2em 0 1em;",
    "h3": "font-size:1.1em;font-weight:bold;color:#17365A;border-bottom:2px solid #B9CFE4;padding-bottom:0.3em;margin:1.8em 0 0.8em;",
    "p": "line-height:1.9;margin:0 0 1.2em;",
    "list": "line-height:1.9;margin:0 0 1.2em;padding-left:1.5em;",
    "box": "background:#EDF4FB;border:1px solid #B9CFE4;border-radius:8px;padding:1em 1.2em;margin:0 0 1.4em;",
    "pr": "display:inline-block;font-size:0.85em;color:#4A5B6E;border:1px solid #B9CFE4;border-radius:4px;padding:0.2em 0.7em;margin:0 0 1.2em;",
    "img": "width:100%;max-width:100%;height:auto;",
    "fig": "text-align:center;margin:0 0 1.4em;",
    "link": "color:#2C6AA0;font-weight:bold;",
}


def _inline(t, url):
    t = _html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\[seminar\]", rf'<a href="{url}" target="_blank" rel="noopener sponsored" style="{S["link"]}">\1</a>', t)
    t = re.sub(r"(?<![\"=])(https://willaugh\.com)", r'<a href="\1" target="_blank" rel="noopener">\1</a>', t)
    return t


def _blocks(text, url, img_prefix):
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        first = lines[0]
        if first.startswith("### "):
            out.append(f'<h3 style="{S["h3"]}">{_inline(first[4:], url)}</h3>')
        elif first.startswith("## "):
            out.append(f'<h2 style="{S["h2"]}">{_inline(first[3:], url)}</h2>')
        elif all(l.startswith(">") for l in lines):
            inner = "\n".join(re.sub(r"^>\s?", "", l) for l in lines)
            inner = re.sub(r"^(\*\*[^*]+\*\*)\n(?![-\d])", r"\1\n\n", inner)  # 見出し行と本文を分ける
            rendered = _blocks(inner, url, img_prefix)
            i = rendered.rfind("margin:0 0 1.2em;")  # 囲みの最後の要素は下余白なし
            if i >= 0:
                rendered = rendered[:i] + "margin:0;" + rendered[i + len("margin:0 0 1.2em;"):]
            out.append(f'<div style="{S["box"]}">{rendered}</div>')
        elif all(re.match(r"- ", l) for l in lines):
            items = "".join(f"<li>{_inline(l[2:], url)}</li>" for l in lines)
            out.append(f'<ul style="{S["list"]}">{items}</ul>')
        elif all(re.match(r"\d+\. ", l) for l in lines):
            items = "".join(f"<li>{_inline(re.sub(r'^\d+\. ', '', l), url)}</li>" for l in lines)
            out.append(f'<ol style="{S["list"]}">{items}</ol>')
        elif m := re.fullmatch(r"【画像:(.+?)】", first.strip()):
            name = m.group(1)
            img = f'<img src="{img_prefix}{name}" alt="" style="{S["img"]}">'
            if name.startswith("button"):
                img = f'<a href="{url}" target="_blank" rel="noopener sponsored">{img}</a>'
            out.append(f"<!-- ▼画像:{name}(Amebaに画像をアップロードしたら、src をそのURLに差し替えてください) -->\n"
                       f'<div style="{S["fig"]}">{img}</div>')
        elif first.startswith("▶ ") and "[seminar]" in first:
            label = re.search(r"\[([^\]]+)\]\[seminar\]", first).group(1)
            out.append(
                f'<p style="text-align:center;margin:0 0 1.4em;">'
                f'<a href="{url}" target="_blank" rel="noopener sponsored" style="display:inline-block;background:#2A6DB5;color:#fff;'
                f'font-weight:bold;font-size:1.05em;text-decoration:none;padding:0.85em 1.8em;border-radius:999px;'
                f'box-shadow:0 4px 0 #123A66;line-height:1.5;">'
                f'<span style="display:inline-block;background:#FFD45C;color:#17365A;font-size:0.8em;border-radius:4px;padding:0.1em 0.5em;margin-right:0.6em;">無料・約30分</span>'
                f'{_html.escape(label)} ›</a></p>')
        elif first.startswith("PR(") or first == "**PR(アフィリエイトリンクを含みます)**":
            out.append(f'<p><span style="{S["pr"]}">PR(アフィリエイトリンクを含みます)</span></p>')
        else:
            out.append(f'<p style="{S["p"]}">' + "<br>".join(_inline(l, url) for l in lines) + "</p>")
    return "\n".join(out)


src = (ROOT / "ameba-01.md").read_text(encoding="utf-8")
url = re.search(r"^\[seminar\]:\s*(\S+)\s*$", src, re.M).group(1)
body = re.sub(r"<!--.*?-->\n*", "", src, flags=re.S)
body = re.sub(r"^\[seminar\]:.*\n+", "", body, flags=re.M)
title = re.search(r"^# (.+)$", body, re.M).group(1)
body = re.sub(r"^# .+\n+", "", body, count=1, flags=re.M)  # タイトルはAmebaのタイトル欄に入れる

fragment = _blocks(body, url, "images/")
(DIST / "ameba-01.html").write_text(
    f"<!-- Amebaのタイトル欄:{title} -->\n<!-- 以下を、Amebaブログのエディタの「HTML表示」に貼り付けてください -->\n{fragment}\n",
    encoding="utf-8")
preview = _blocks(body, url, "../images/")
(DIST / "ameba-01-preview.html").write_text(
    f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    f"<title>Ameba記事プレビュー</title></head><body style=\"background:#fff;color:#1D2B3A;font-family:'Hiragino Sans','Noto Sans JP',sans-serif;"
    f'max-width:720px;margin:0 auto;padding:24px 16px;font-size:16px\"><h1 style="font-size:1.5em;color:#17365A;line-height:1.5">{_html.escape(title)}</h1>\n{preview}\n</body></html>',
    encoding="utf-8")
print("ameba-01.html / ameba-01-preview.html を出力しました")


# ---------------------------------------------------------------- まとめページ(dist/index.html)
# 記事・X投稿・画像を1ページで確認し、ボタンでコピーできるHTMLです(画像も埋め込み済み。単体で開けます)。
import base64
import json


def _data_uri(name):
    f = ROOT / "images" / name
    return "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode() if f.exists() else ""


def _embed_imgs(fragment):
    return re.sub(r'src="(?:\.\./)?images/([^"]+)"', lambda m: f'data-img="{m.group(1)}"', fragment)


def _article(name):
    src = (ROOT / name).read_text(encoding="utf-8")
    url = re.search(r"^\[seminar\]:\s*(\S+)\s*$", src, re.M).group(1)
    body = re.sub(r"<!--.*?-->\n*", "", src, flags=re.S)
    body = re.sub(r"^\[seminar\]:.*\n+", "", body, flags=re.M)
    title = re.search(r"^# (.+)$", body, re.M).group(1)
    body = re.sub(r"^# .+\n+", "", body, count=1, flags=re.M)
    return title, body, url


def _x_items(name):
    src = (ROOT / name).read_text(encoding="utf-8")
    url = re.search(r"^SEMINAR_URL:\s*(\S+)\s*$", src, re.M).group(1)
    items = []
    for sec in re.split(r"^## ", src, flags=re.M)[1:]:
        title = sec.split("\n", 1)[0].strip()
        m = re.search(r"```\n(.*?)```", sec, re.S)
        if not m:
            continue
        body = m.group(1).strip()
        img = re.search(r"【画像:(.+?)】", sec)
        items.append({
            "title": title,
            "text": body.replace("{SEMINAR_URL}", url),
            "count": len(body.replace("{SEMINAR_URL}", "x" * 23)),
            "img": img.group(1) if img else None,
        })
    return items


def _esc(t):
    return _html.escape(t)


def _copy_btn(text, label="コピー"):
    return f'<button class="copy" data-copy="{_esc(text)}">{label}</button>'


def _x_cards(items):
    out = []
    for it in items:
        img = f'<img data-img="{_esc(it["img"])}" alt="{_esc(it["img"])}">' if it["img"] else ""
        cls = "ok" if it["count"] <= 140 else "ng"
        out.append(f'''<article class="xcard">
  <header><h3>{_esc(it["title"])}</h3><span class="count {cls}">{it["count"]}字</span></header>
  <pre>{_esc(it["text"])}</pre>{img}
  <footer>{_copy_btn(it["text"])}{f'<span class="imgname">画像:{_esc(it["img"])}</span>' if it["img"] else ""}</footer>
</article>''')
    return "\n".join(out)


a_title, a_body, a_url = _article("ameba-01.md")
a_fragment = _blocks(a_body, a_url, "images/")
a_html_paste = (DIST / "ameba-01.html").read_text(encoding="utf-8")
a_preview = _embed_imgs(a_fragment)

n_title, n_body, n_url = _article("note-01.md")
n_md = (DIST / "note-01.md").read_text(encoding="utf-8")
n_md = re.sub(r"^# .+\n+", "", n_md, count=1, flags=re.M)
n_preview = _embed_imgs(_blocks(n_body, n_url, "images/"))

x_posts = _x_items("x-posts.md")
x_threads = _x_items("x-threads.md")
img_names = sorted(p.name for p in (ROOT / "images").glob("*.png"))
img_grid = "\n".join(
    f'<figure><img data-img="{n}" alt="{n}"><figcaption>{n}'
    f' <a class="dl" data-img-href="{n}" download="{n}">保存</a></figcaption></figure>' for n in img_names)
img_json = json.dumps({n: _data_uri(n) for n in img_names})

page = f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>記事と投稿のまとめ</title>
<style>
:root{{--bg:#F3F7FB;--card:#fff;--text:#1D2B3A;--sub:#4A5B6E;--navy:#17365A;--blue:#2C6AA0;--line:#D3E1EE;--pale:#EDF4FB;--ok:#2E7D4F;--ng:#B3261E}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0F1720;--card:#17212C;--text:#E4ECF4;--sub:#9DB0C3;--navy:#BFD8F0;--blue:#7FB2E5;--line:#2A3A4B;--pale:#1C2A38;--ok:#7BCB98;--ng:#F2938C}}}}
:root[data-theme="dark"]{{--bg:#0F1720;--card:#17212C;--text:#E4ECF4;--sub:#9DB0C3;--navy:#BFD8F0;--blue:#7FB2E5;--line:#2A3A4B;--pale:#1C2A38;--ok:#7BCB98;--ng:#F2938C}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:"Hiragino Sans","Noto Sans JP","Yu Gothic",sans-serif;line-height:1.7}}
.wrap{{max-width:960px;margin:0 auto;padding:20px 16px 80px}}
h1{{font-size:1.35rem;color:var(--navy);margin:8px 0 4px}}
.lead{{color:var(--sub);font-size:.9rem;margin:0 0 16px}}
nav{{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;gap:6px;overflow-x:auto;padding:10px 0;border-bottom:1px solid var(--line)}}
nav button{{flex:none;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;padding:7px 16px;font:inherit;font-size:.9rem;cursor:pointer}}
nav button[aria-selected="true"]{{background:var(--blue);border-color:var(--blue);color:#fff}}
section{{display:none;padding-top:16px}} section.on{{display:block}}
.bar{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 14px}}
.copy{{border:0;background:var(--blue);color:#fff;border-radius:8px;padding:7px 14px;font:inherit;font-size:.85rem;cursor:pointer}}
.copy.done{{background:var(--ok)}}
.note{{background:var(--pale);border:1px solid var(--line);border-radius:10px;padding:10px 14px;font-size:.88rem;color:var(--sub);margin:0 0 14px}}
.paper{{background:#fff;color:#1D2B3A;border-radius:12px;border:1px solid var(--line);padding:20px 18px;overflow-wrap:anywhere}}
.paper img{{max-width:100%;height:auto}}
.paper h1t{{display:block}}
.xgrid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}}
.xcard{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:10px;min-width:0}}
.xcard header{{display:flex;justify-content:space-between;gap:8px;align-items:baseline}}
.xcard h3{{font-size:.9rem;margin:0;color:var(--navy)}}
.count{{font-size:.8rem;font-weight:700;white-space:nowrap}} .count.ok{{color:var(--ok)}} .count.ng{{color:var(--ng)}}
.xcard pre{{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;font-size:.92rem;background:var(--pale);border-radius:8px;padding:10px 12px;flex:1}}
.xcard img{{width:100%;border-radius:8px;border:1px solid var(--line)}}
.xcard footer{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.imgname{{font-size:.78rem;color:var(--sub)}}
.imgs{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}}
.imgs figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px}}
.imgs img{{width:100%;border-radius:6px;display:block}}
.imgs figcaption{{font-size:.82rem;color:var(--sub);margin-top:6px;display:flex;justify-content:space-between;gap:8px}}
.dl{{color:var(--blue);font-weight:700}}
h2.sub{{font-size:1rem;color:var(--navy);margin:22px 0 10px}}
</style></head>
<body><div class="wrap">
<h1>記事と投稿のまとめ</h1>
<p class="lead">記事の確認とコピー用です。元の記事を書き換えたら <code>python3 build.py</code> で、このページも作り直されます。</p>
<nav role="tablist">
  <button role="tab" data-tab="ameba" aria-selected="true">Ameba</button>
  <button role="tab" data-tab="note">note</button>
  <button role="tab" data-tab="xposts">X投稿({len(x_posts)})</button>
  <button role="tab" data-tab="xthreads">Xスレッド</button>
  <button role="tab" data-tab="images">画像({len(img_names)})</button>
</nav>

<section id="ameba" class="on">
  <div class="bar">{_copy_btn(a_title, "タイトルをコピー")}{_copy_btn(a_html_paste, "HTMLをコピー(HTML表示に貼り付け)")}</div>
  <p class="note">コピーしたHTMLの画像は <code>src="images/…"</code> になっています。Amebaに画像をアップロードしたら、そのURLに差し替えてください(目印:<code>&lt;!-- ▼画像:… --&gt;</code>)。</p>
  <div class="paper"><h2 style="font-size:1.3em;color:#17365A;margin:0 0 1em">{_esc(a_title)}</h2>{a_preview}</div>
</section>

<section id="note">
  <div class="bar">{_copy_btn(n_title, "タイトルをコピー")}{_copy_btn(n_md, "本文をコピー(Markdown)")}</div>
  <p class="note">noteはHTMLを貼り付けられないため、本文はMarkdownでコピーします。「【画像:…】」の位置に、画像を挿入してください。下のプレビューは確認用で、実際の見出しや囲みはnoteの標準デザインになります。</p>
  <div class="paper"><h2 style="font-size:1.3em;color:#17365A;margin:0 0 1em">{_esc(n_title)}</h2>{n_preview}</div>
</section>

<section id="xposts">
  <p class="note">リンクは本文に入れず、反応の良い投稿に「リンク用リプライ」を付けます。字数は、改行を1字、URLを23字として数えています。</p>
  <div class="xgrid">{_x_cards(x_posts)}</div>
</section>

<section id="xthreads">
  <p class="note">1/ を投稿したあと、2/ 以降を、1つ前の投稿へのリプライとして、順番につなげます。リンクは最後のリプライだけです。</p>
  <h2 class="sub">スレッドA:アフィリエイトの基本</h2>
  <div class="xgrid">{_x_cards([i for i in x_threads if i["title"].startswith("A-")])}</div>
  <h2 class="sub">スレッドB:学び始める前に知っておきたい5つのこと</h2>
  <div class="xgrid">{_x_cards([i for i in x_threads if i["title"].startswith("B-")])}</div>
</section>

<section id="images">
  <div class="imgs">{img_grid}</div>
</section>
</div>
<script>
const IMGS = {img_json};
document.querySelectorAll('[data-img]').forEach(el => {{ el.src = IMGS[el.dataset.img] || ''; }});
document.querySelectorAll('[data-img-href]').forEach(el => {{ el.href = IMGS[el.dataset.imgHref] || '#'; }});
document.querySelectorAll('nav button').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('nav button').forEach(x => x.setAttribute('aria-selected', x === b));
  document.querySelectorAll('section').forEach(s => s.classList.toggle('on', s.id === b.dataset.tab));
  window.scrollTo({{top: 0}});
}}));
async function copyText(t) {{
  try {{ await navigator.clipboard.writeText(t); return true; }} catch (e) {{
    const ta = document.createElement('textarea'); ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); let ok = false; try {{ ok = document.execCommand('copy'); }} catch (e2) {{}}
    ta.remove(); return ok;
  }}
}}
document.addEventListener('click', async e => {{
  const b = e.target.closest('.copy'); if (!b) return;
  const label = b.textContent; const ok = await copyText(b.dataset.copy);
  b.textContent = ok ? 'コピーしました' : 'コピーできませんでした'; b.classList.toggle('done', ok);
  setTimeout(() => {{ b.textContent = label; b.classList.remove('done'); }}, 1600);
}});
</script>
</body></html>'''
(DIST / "index.html").write_text(page, encoding="utf-8")
print(f"index.html を出力しました({len(page)//1024}KB)")


# ---------------------------------------------------------------- Amebaだけの一式(dist/ameba-kit と ameba-kit.zip)
import shutil
import zipfile

KIT = DIST / "ameba-kit"
shutil.rmtree(KIT, ignore_errors=True)
(KIT / "images").mkdir(parents=True)
for n in sorted(set(re.findall(r"【画像:(.+?)】", (ROOT / "ameba-01.md").read_text(encoding="utf-8")))):
    shutil.copy(ROOT / "images" / n, KIT / "images" / n)
shutil.copy(DIST / "ameba-01.html", KIT / "ameba-01.html")
(KIT / "title.txt").write_text(a_title + "\n", encoding="utf-8")
shutil.copy(ROOT / "image-src" / "ameba-kit-手順.txt", KIT / "手順.txt")
with zipfile.ZipFile(DIST / "ameba-kit.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(KIT.rglob("*")):
        if f.is_file():
            z.write(f, f.relative_to(DIST))
print("ameba-kit.zip を出力しました")
