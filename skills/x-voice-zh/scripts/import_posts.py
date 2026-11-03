#!/usr/bin/env python3
"""把你的帖子（jsonl / json / X 数据导出 tweets.js / csv / txt）转成统一 jsonl。

用法:
  python import_posts.py my_posts.txt -o posts.jsonl
  python import_posts.py tweets.js -o posts.jsonl      # X 官方数据导出
txt/md 里每条帖子之间用单独一行 --- 隔开。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_posts, write_jsonl  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--out", default="-", help="输出 jsonl，默认打印到屏幕")
    a = ap.parse_args(argv)
    posts = load_posts(a.input)
    write_jsonl(posts, a.out)
    print(f"读到 {len(posts)} 条帖子", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
