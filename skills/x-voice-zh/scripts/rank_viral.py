#!/usr/bin/env python3
"""从同赛道账号的帖子里筛出爆款（不调模型）。

规则：只留原创（排除回复、转发）；收藏、回复、浏览任意一项过阈值；
排除推广和抽奖；按正文去重；按互动分排序（收藏×3 + 回复×2 + 点赞）。

用法:
  python rank_viral.py bigshots.jsonl --min-bookmarks 100 --min-replies 100 --top 10 -o viral.jsonl
  python rank_viral.py bigshots.jsonl --accounts alice,bob --since-hours 48 --format md
"""
import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import engagement, load_posts, parse_time, write_jsonl  # noqa: E402

PROMO_RE = re.compile(
    r"限时|优惠码|折扣|点击链接|加微信|加V|私信我|私信领|领取|抽奖|转发抽|带货|邀请码|返佣|返现|"
    r"联盟|课程报名|扫码|vx[:：]|VX[:：]|giveaway|use code|dm me|link in bio", re.I)


def is_promo(text):
    return bool(PROMO_RE.search(text))


def norm_key(text):
    return re.sub(r"\W+", "", text)[:40].lower()


def select(posts, min_bookmarks=100, min_replies=100, min_views=None, accounts=None,
           since_hours=None, now=None, allow_missing=False, keep_promo=False):
    acc = {a.lower().lstrip("@") for a in (accounts or [])}
    now = now or datetime.now(timezone.utc)
    seen, out, dropped = set(), [], {"reply_or_rt": 0, "promo": 0, "below_threshold": 0,
                                     "account": 0, "too_old": 0, "dup": 0}
    for p in posts:
        if p["is_reply"] or p["is_retweet"]:
            dropped["reply_or_rt"] += 1
            continue
        if acc and (p.get("author") or "").lower().lstrip("@") not in acc:
            dropped["account"] += 1
            continue
        if since_hours is not None:
            t = parse_time(p.get("created_at"))
            if t is None or now - t > timedelta(hours=since_hours):
                dropped["too_old"] += 1
                continue
        if not keep_promo and is_promo(p["text"]):
            dropped["promo"] += 1
            continue
        has_metrics = any(p.get(k) is not None for k in ("bookmarks", "replies", "views"))
        ok = (p.get("bookmarks") or 0) >= min_bookmarks if min_bookmarks is not None else False
        ok = ok or ((p.get("replies") or 0) >= min_replies if min_replies is not None else False)
        ok = ok or (min_views is not None and (p.get("views") or 0) >= min_views)
        if not ok and not (allow_missing and not has_metrics):
            dropped["below_threshold"] += 1
            continue
        k = norm_key(p["text"])
        if k in seen:
            dropped["dup"] += 1
            continue
        seen.add(k)
        out.append(p)
    out.sort(key=engagement, reverse=True)
    return out, dropped


def to_markdown(posts):
    L = ["| # | 作者 | 浏览 | 回复 | 收藏 | 开头 | 链接 |", "|---|---|---|---|---|---|---|"]
    for i, p in enumerate(posts, 1):
        head = p["text"].split("\n")[0][:24].replace("|", "｜")
        L.append(f"| {i} | {p.get('author') or '-'} | {p.get('views') or '-'} | {p.get('replies') or '-'} | "
                 f"{p.get('bookmarks') or '-'} | {head} | {p.get('url') or '-'} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--min-bookmarks", type=int, default=100)
    ap.add_argument("--min-replies", type=int, default=100)
    ap.add_argument("--min-views", type=int, default=None)
    ap.add_argument("--accounts", help="只看这些账号，逗号分隔")
    ap.add_argument("--since-hours", type=float, default=None, help="只看最近多少小时（需要 created_at）")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--allow-missing-metrics", action="store_true", help="没有互动数据的帖子也保留")
    ap.add_argument("--keep-promo", action="store_true")
    ap.add_argument("--format", choices=["jsonl", "md"], default="jsonl")
    ap.add_argument("-o", "--out", default="-")
    a = ap.parse_args(argv)
    posts = load_posts(a.input)
    sel, dropped = select(posts, a.min_bookmarks, a.min_replies, a.min_views,
                          a.accounts.split(",") if a.accounts else None, a.since_hours,
                          allow_missing=a.allow_missing_metrics, keep_promo=a.keep_promo)
    sel = sel[:a.top]
    if a.format == "md":
        txt = to_markdown(sel)
        if a.out == "-":
            print(txt)
        else:
            open(a.out, "w", encoding="utf-8").write(txt)
    else:
        write_jsonl(sel, a.out)
    print(f"输入 {len(posts)} 条，入选 {len(sel)} 条；剔除：{dropped}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
