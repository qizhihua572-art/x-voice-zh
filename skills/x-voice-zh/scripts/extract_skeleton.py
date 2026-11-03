#!/usr/bin/env python3
"""给爆款帖拆骨架（规则判断，不调模型）：钩子类型、结构、形式、可收藏线索。
「为什么火」这一栏留给 AI 对照原帖补，脚本只给证据。

用法:
  python extract_skeleton.py viral.jsonl --format md
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import EMOJI_RE, URL_RE, features, lines_of, load_posts  # noqa: E402

# 钩子类型（顺序 = 优先级）。每条是 (类型, 判断的正则, 保留字段)；只看首行。
HOOKS = [
    ("打时间差", re.compile(r"(\d+|[一二三四五六七八九十])\s*(天|小时|周|个月|分钟).{0,12}(就|才|只|便|竟|已经)|从.{1,12}到.{1,12}|以前.{1,12}现在|before.{0,20}after", re.I), False),
    ("报数字", re.compile(r"\d[\d,.]*\s*(万|k|K|w|%|刀|美元|美金|\$|元|块|star|Star|收藏|粉|人|个|倍)|[$¥￥]\s*\d"), True),
    ("拿出成品", re.compile(r"做(好|完|了个|出)|上线|开源|发布|终于|成品|demo|Demo|DEMO|搞定|放出|交付|试玩|能玩|已经能"), True),
    ("坦白", re.compile(r"说实话|坦白|承认|翻车|踩坑|我错|惭愧|不瞒|老实说|其实我|没想到我|失败|被骂"), True),
    ("报痛点", re.compile(r"太(贵|慢|难|烦|卡)|烦死|卡住|卡了|没人|怎么办|为什么.{0,10}[？?]|一直(报错|失败)|救命|头疼|崩溃|踩|浪费"), True),
    ("下判断", re.compile(r"^.{0,30}(才是|就是|不会|永远|没有.{0,6}可言|越.{1,8}越|都是)"), True),
]
SAVE_HINTS = [
    ("安装/命令", re.compile(r"`[^`]+`|npx |pip |npm |git clone|brew |curl |安装")),
    ("清单/步骤", re.compile(r"(?m)^\s*([1-9][.、)）]|[①②③④⑤]|[-•·])")),
    ("省钱/赚钱数字", re.compile(r"省\s*\d|\d+\s*(刀|美元|美金|元|块).{0,6}(月|天|年)?|MRR|月入|收入|成本")),
    ("可直接复用的模板/提示词", re.compile(r"提示词|模板|prompt|Prompt|清单|checklist|SOP")),
]
MEDIA_RE = re.compile(r"截图|视频|录屏|图[：:]|📷|🎥|\[图|pic\.|video|https://t\.co/\S+")


def hook_types(text):
    first = (lines_of(text) or [""])[0]
    hits = []
    for name, rx, first_only in HOOKS:
        target = first
        if rx.search(target):
            hits.append(name)
    return hits or ["未识别（请 AI 判断）"]


def skeleton(p):
    text = p["text"]
    f = features(text)
    ls = lines_of(URL_RE.sub("", text))
    saves = [n for n, rx in SAVE_HINTS if rx.search(text)]
    ratio = None
    if p.get("likes") and p.get("bookmarks") is not None:
        ratio = round(p["bookmarks"] / p["likes"], 2)
    return {
        "author": p.get("author"), "url": p.get("url"),
        "views": p.get("views"), "likes": p.get("likes"), "replies": p.get("replies"),
        "bookmarks": p.get("bookmarks"), "bookmark_like_ratio": ratio,
        "hook_types": hook_types(text),
        "first_line": ls[0] if ls else "",
        "first_line_len": len(ls[0]) if ls else 0,
        "lines": f["lines"], "chars": f["chars"],
        "emoji": f["emoji"], "ends_question": f["ends_question"],
        "link_in_body": f["has_url"],
        "media_hint": bool(MEDIA_RE.search(text)),
        "save_hints": saves,
        "example": bool(p.get("example")),
    }


def to_markdown(items):
    L = []
    for i, s in enumerate(items, 1):
        tag = "（示例数据）" if s["example"] else ""
        L.append(f"### {i}. {s['author'] or '未知账号'} {tag}")
        L.append(f"- 原帖：{s['url'] or '无链接'}；浏览 {s['views']} / 回复 {s['replies']} / 收藏 {s['bookmarks']}"
                 + (f"（收藏/点赞 {s['bookmark_like_ratio']}）" if s['bookmark_like_ratio'] is not None else ""))
        L.append(f"- 钩子类型（规则判断，请复核）：{'、'.join(s['hook_types'])}")
        L.append(f"- 结构：{s['lines']} 行 / {s['chars']} 字；首行 {s['first_line_len']} 字：{s['first_line']}")
        L.append(f"- 形式：{'有图/视频线索' if s['media_hint'] else '纯文字或未知'}；"
                 f"{'正文带链接（转写时挪到评论区）' if s['link_in_body'] else '正文无链接'}；"
                 f"{'问句收尾' if s['ends_question'] else '非问句收尾'}")
        L.append(f"- 可收藏线索：{'、'.join(s['save_hints']) or '没看到明显的可存内容'}")
        L.append("- 为什么火：（AI 对照原帖补，必须有依据）")
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--format", choices=["json", "md"], default="json")
    ap.add_argument("-o", "--out", default="-")
    a = ap.parse_args(argv)
    items = [skeleton(p) for p in load_posts(a.input)]
    out = to_markdown(items) if a.format == "md" else json.dumps(items, ensure_ascii=False, indent=2)
    if a.out == "-":
        print(out)
    else:
        open(a.out, "w", encoding="utf-8").write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
