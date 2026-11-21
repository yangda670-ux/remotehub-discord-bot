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
