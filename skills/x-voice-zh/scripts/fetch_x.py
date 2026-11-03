#!/usr/bin/env python3
"""可选：用你自己的 X API token 拉某个账号的原创帖（排除回复和转发）。

token 只从环境变量 X_BEARER_TOKEN 读，脚本不保存、不打印。
X API 的价格、权限和读取额度以官网为准，用之前自己查；没有 API 也能用，
把帖子复制进文本文件，用 import_posts.py 导入即可。

用法:
  export X_BEARER_TOKEN=你自己的token
  python fetch_x.py --user someone --hours 48 --max 100 -o bigshots.jsonl
  python fetch_x.py --user someone --dry-run         # 只打印会请求的地址
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import normalize, write_jsonl  # noqa: E402

BASE = "https://api.x.com/2"


def user_url(username):
    return f"{BASE}/users/by/username/{urllib.parse.quote(username.lstrip('@'))}"


def timeline_url(user_id, max_results=100, start_time=None, pagination_token=None):
    q = {
        "max_results": max(5, min(100, max_results)),
        "exclude": "replies,retweets",
        "tweet.fields": "created_at,public_metrics,lang",
    }
    if start_time:
        q["start_time"] = start_time
    if pagination_token:
        q["pagination_token"] = pagination_token
    return f"{BASE}/users/{user_id}/tweets?" + urllib.parse.urlencode(q)


def parse_timeline(payload, username):
    """把 API 返回转成统一字段。"""
    posts = []
    for t in payload.get("data", []) or []:
        t = dict(t)
        t["author"] = username.lstrip("@")
        t["url"] = f"https://x.com/{t['author']}/status/{t['id']}"
        posts.append(normalize(t))
    return posts


def http_get_json(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "User-Agent": "x-voice-zh/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"X API 返回 {e.code}：{e.reason}。多半是 token 无效、套餐没有读取权限或额度用完，请去 X 开发者后台核对。")
    except urllib.error.URLError as e:
        raise SystemExit(f"网络错误：{e.reason}")


def fetch_user(username, token, hours=48, max_results=100, getter=http_get_json):
    uid = getter(user_url(username), token)["data"]["id"]
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ") if hours else None
    posts, nxt = [], None
    while len(posts) < max_results:
        payload = getter(timeline_url(uid, max_results - len(posts), start, nxt), token)
        posts += parse_timeline(payload, username)
        nxt = (payload.get("meta") or {}).get("next_token")
        if not nxt:
            break
    return posts[:max_results]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", action="append", required=True, help="账号，可重复")
    ap.add_argument("--hours", type=float, default=48)
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-o", "--out", default="-")
    a = ap.parse_args(argv)
    if a.dry_run:
        for u in a.user:
            print(user_url(u))
            print(timeline_url("<user_id>", a.max, "<start_time>"))
        return 0
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        print("没有找到环境变量 X_BEARER_TOKEN。没有 API 的话，请改用 import_posts.py 导入你复制的帖子。", file=sys.stderr)
        return 2
    allp = []
    for u in a.user:
        allp += fetch_user(u, token, a.hours, a.max)
    write_jsonl(allp, a.out)
    print(f"拉到 {len(allp)} 条", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
