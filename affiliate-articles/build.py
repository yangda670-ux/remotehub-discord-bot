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

src = (ROOT / "x-posts.md").read_text(encoding="utf-8")
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
(DIST / "x-posts.txt").write_text("\n".join(lines), encoding="utf-8")
