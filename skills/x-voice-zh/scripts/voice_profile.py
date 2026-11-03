#!/usr/bin/env python3
"""从你自己的帖子里算语气画像（纯统计，不调模型）。

用法:
  python voice_profile.py posts.jsonl --json profile.json --md profile.md
默认只统计原创帖（排除回复和转发），加 --include-replies 可一起算。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (EMOJI_RE, HAN_RE, URL_RE, engagement, features, lines_of,  # noqa: E402
                     load_posts, median, percentile)

STOP_CHARS = set("的了是我你他她它们在有和就也都不这那个与及把被让给对从向为以而但并或")
PARTICLES = list("吧呀啊嘛哈啦呢哦诶哎")
OPENER_SPLIT = re.compile(r"[，,。！!？?、\s~～…:：]")


def opener(text):
    first = lines_of(URL_RE.sub("", text))
    if not first:
        return ""
    head = OPENER_SPLIT.split(first[0].strip(), 1)[0]
    head = EMOJI_RE.sub("", head)
    return head[:6]


def phrases(texts, top=10):
    """2-3 字中文短语，按「出现在多少条帖子里」排序。"""
    df = Counter()
    for t in texts:
        seen = set()
        for seg in re.findall(r"[\u4e00-\u9fff]+", URL_RE.sub("", t)):
            for n in (2, 3):
                for i in range(len(seg) - n + 1):
                    g = seg[i:i + n]
                    if g[0] in STOP_CHARS or g[-1] in STOP_CHARS:
                        continue
                    seen.add(g)
        df.update(seen)
    items = [(g, c) for g, c in df.items() if c >= 2]
    kept = []
    for g, c in sorted(items, key=lambda x: (-x[1], -len(x[0]), x[0])):
        if any(g in k and c <= kc for k, kc in kept):  # 被更长短语包含且不更常见
            continue
        kept.append((g, c))
        if len(kept) >= top:
            break
    return kept


def build_profile(posts, include_replies=False):
    pool = [p for p in posts if include_replies or not (p["is_reply"] or p["is_retweet"])]
    if not pool:
        return {"n_posts": 0, "note": "没有可统计的原创帖"}
    feats = [features(p["text"]) for p in pool]
    n = len(pool)
    chars = [f["chars"] for f in feats]
    lines = [f["lines"] for f in feats]
    per_line = []
    for p in pool:
        per_line += [len(l) for l in lines_of(URL_RE.sub("", p["text"]))]
    emo = Counter()
    for p in pool:
        emo.update(EMOJI_RE.findall(p["text"]))
    openers = Counter(o for o in (opener(p["text"]) for p in pool) if o)
    particle = Counter()
    for p in pool:
        for ch in PARTICLES:
            if ch in p["text"]:
                particle[ch] += 1
    profile = {
        "n_posts": n,
        "chars_median": median(chars),
        "chars_p90": percentile(chars, 0.9),
        "lines_median": median(lines),
        "lines_p90": percentile(lines, 0.9),
        "line_len_median": median(per_line),
        "emoji_rate": round(sum(1 for f in feats if f["emoji"]) / n, 2),
        "top_emoji": [e for e, _ in emo.most_common(5)],
        "emoji_stack_rate": round(sum(1 for p in pool if re.search(
            EMOJI_RE.pattern + "{2,}", p["text"])) / n, 2),
        "exclaim_avg": round(sum(f["exclaim"] for f in feats) / n, 2),
        "question_end_rate": round(sum(1 for f in feats if f["ends_question"]) / n, 2),
        "url_in_body_rate": round(sum(1 for f in feats if f["has_url"]) / n, 2),
        "top_openers": [[o, c] for o, c in openers.most_common(8) if c >= 2],
        "particles": [[k, c] for k, c in particle.most_common(5)],
        "top_phrases": [[g, c] for g, c in phrases([p["text"] for p in pool])],
    }
    with_metrics = [p for p in pool if any(p.get(k) is not None for k in ("bookmarks", "replies", "likes"))]
    if len(with_metrics) >= 4:
        ranked = sorted(with_metrics, key=engagement, reverse=True)
        q = max(1, len(ranked) // 4)

        def avg(group, key):
            vals = [features(p["text"])[key] for p in group]
            return round(sum(vals) / len(vals), 2)

        top, bottom = ranked[:q], ranked[-q:]
        profile["top_vs_bottom"] = {
            "group_size": q,
            "top_chars": avg(top, "chars"), "bottom_chars": avg(bottom, "chars"),
            "top_lines": avg(top, "lines"), "bottom_lines": avg(bottom, "lines"),
            "top_emoji": avg(top, "emoji"), "bottom_emoji": avg(bottom, "emoji"),
            "top_question_end": avg(top, "ends_question"), "bottom_question_end": avg(bottom, "ends_question"),
        }
        profile["best_posts"] = [
            {"text": p["text"][:80], "url": p.get("url"), "views": p.get("views"),
             "replies": p.get("replies"), "bookmarks": p.get("bookmarks")}
            for p in ranked[:3]
        ]
        profile["worst_posts"] = [
            {"text": p["text"][:80], "url": p.get("url"), "views": p.get("views"),
             "replies": p.get("replies"), "bookmarks": p.get("bookmarks")}
            for p in ranked[-3:]
        ]
    return profile


def to_markdown(pf):
    if not pf.get("n_posts"):
        return "# 语气画像\n\n没有可统计的原创帖。\n"
    L = ["# 语气画像（脚本统计，下面的规则请让 AI 对照原帖再润色）", "",
         f"样本：{pf['n_posts']} 条原创帖", "", "## 统计出来的事实"]
    L.append(f"- 长度：中位数 {pf['chars_median']:g} 字，90 分位 {pf['chars_p90']:g} 字；"
             f"中位 {pf['lines_median']:g} 行，90 分位 {pf['lines_p90']:g} 行；一行中位 {pf['line_len_median']:g} 字")
    emo = "".join(pf["top_emoji"]) or "无"
    L.append(f"- 表情：{int(pf['emoji_rate'] * 100)}% 的帖子有表情，常用 {emo}；"
             f"{int(pf['emoji_stack_rate'] * 100)}% 的帖子会连着叠放")
    L.append(f"- 感叹号：平均每条 {pf['exclaim_avg']} 个")
    L.append(f"- 结尾：{int(pf['question_end_rate'] * 100)}% 以问句收尾；{int(pf['url_in_body_rate'] * 100)}% 正文里带链接")
    if pf["top_openers"]:
        L.append("- 常见开头：" + "、".join(f"「{o}」×{c}" for o, c in pf["top_openers"]))
    if pf["particles"]:
        L.append("- 语气词：" + "、".join(f"{k}×{c}" for k, c in pf["particles"]))
    if pf["top_phrases"]:
        L.append("- 常用短语（出现在多少条里）：" + "、".join(f"{g}×{c}" for g, c in pf["top_phrases"]))
    tb = pf.get("top_vs_bottom")
    if tb:
        L += ["", "## 数据最好的 vs 最差的（各取前后 1/4，互动分 = 收藏×3 + 回复×2 + 点赞）",
              f"- 字数：{tb['top_chars']} vs {tb['bottom_chars']}",
              f"- 行数：{tb['top_lines']} vs {tb['bottom_lines']}",
              f"- 表情数：{tb['top_emoji']} vs {tb['bottom_emoji']}",
              f"- 问句收尾占比：{tb['top_question_end']} vs {tb['bottom_question_end']}"]
        L += ["", "### 最好的 3 条"] + [
            f"- 「{p['text'].replace(chr(10), ' ⏎ ')}」 浏览 {p['views']} / 回复 {p['replies']} / 收藏 {p['bookmarks']} {p.get('url') or ''}"
            for p in pf["best_posts"]]
        L += ["", "### 最差的 3 条"] + [
            f"- 「{p['text'].replace(chr(10), ' ⏎ ')}」 浏览 {p['views']} / 回复 {p['replies']} / 收藏 {p['bookmarks']} {p.get('url') or ''}"
            for p in pf["worst_posts"]]
    L += ["", "## 待 AI 补充（对照原帖写，别凭空写）",
          "1. 开头怎么写：", "2. 一条几行、一行多长：", "3. 表情怎么放：",
          "4. 常用词和口头禅：", "5. 怎么收尾：", "6. 哪类帖数据差、以后别发："]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="posts.jsonl 或其他 import_posts 支持的格式")
    ap.add_argument("--json", help="画像 json 输出路径")
    ap.add_argument("--md", help="画像 markdown 输出路径")
    ap.add_argument("--include-replies", action="store_true")
    a = ap.parse_args(argv)
    posts = load_posts(a.input)
    pf = build_profile(posts, a.include_replies)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(pf, f, ensure_ascii=False, indent=2)
    md = to_markdown(pf)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(md)
    if not a.json and not a.md:
        print(md)
    if pf.get("n_posts", 0) < 20:
        print("提示：样本不到 20 条，画像只能参考。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
