"""公共函数：读帖子、统一字段、算文本特征。只用标准库。"""
import csv
import io
import json
import os
import re
from datetime import datetime, timezone

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF\u2600-\u27BF\u2B50\u2B55\u2764\u2705\u274C]"
)
URL_RE = re.compile(r"https?://\S+")
HAN_RE = re.compile(r"[\u4e00-\u9fff]")

ALIASES = {
    "text": ["text", "full_text", "content", "body"],
    "views": ["views", "view_count", "impressions", "impression_count"],
    "likes": ["likes", "like_count", "favorite_count", "favorites"],
    "replies": ["replies", "reply_count"],
    "bookmarks": ["bookmarks", "bookmark_count"],
    "reposts": ["reposts", "retweets", "retweet_count", "repost_count"],
    "created_at": ["created_at", "date", "time", "timestamp"],
    "url": ["url", "link"],
    "author": ["author", "username", "screen_name", "user"],
    "id": ["id", "id_str", "tweet_id"],
}
METRICS = ["views", "likes", "replies", "bookmarks", "reposts"]


def parse_num(v):
    """'1.2万' '3.4k' '1,234' 12 -> 数字；空/无法解析 -> None。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace(",", "").replace("，", "")
    if not s:
        return None
    mult = 1
    if s[-1] in "万wW":
        mult, s = 10000, s[:-1]
    elif s[-1] in "kK千":
        mult, s = 1000, s[:-1]
    elif s[-1] in "mM":
        mult, s = 1000000, s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def parse_time(v):
    """尽量解析时间；返回带时区的 datetime 或 None。"""
    if not v:
        return None
    s = str(v).strip()
    if s.isdigit() and len(s) >= 10:
        n = int(s)
        if n > 10**11:
            n //= 1000
        return datetime.fromtimestamp(n, tz=timezone.utc)
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _pick(raw, names):
    for n in names:
        if n in raw and raw[n] not in (None, ""):
            return raw[n]
    return None


def normalize(raw):
    """把各种来源的一条帖子统一成固定字段。"""
    if "tweet" in raw and isinstance(raw["tweet"], dict):  # X 数据导出
        raw = raw["tweet"]
    pm = raw.get("public_metrics") or {}
    flat = dict(raw)
    for k, v in pm.items():
        flat.setdefault(k, v)
    text = _pick(flat, ALIASES["text"]) or ""
    post = {"text": str(text).replace("\r\n", "\n").strip()}
    for k in METRICS:
        post[k] = parse_num(_pick(flat, ALIASES[k]))
    for k in ("created_at", "url", "author", "id"):
        v = _pick(flat, ALIASES[k])
        post[k] = str(v) if v is not None else None
    reply = bool(flat.get("is_reply")) or bool(flat.get("in_reply_to_status_id")) \
        or bool(flat.get("in_reply_to_status_id_str")) or bool(flat.get("in_reply_to_user_id")) \
        or post["text"].startswith("@")
    rt = bool(flat.get("is_retweet")) or post["text"].startswith("RT @")
    post["is_reply"] = reply
    post["is_retweet"] = rt
    post["example"] = bool(flat.get("example") or flat.get("_example"))
    return post


def _split_plain(text):
    parts = re.split(r"(?m)^\s*(?:---+|===+)\s*$", text)
    if len(parts) == 1:
        parts = re.split(r"\n\s*\n\s*\n+", text)
    return [p.strip() for p in parts if p.strip()]


def load_posts(path, keep_empty=False):
    """读 jsonl / json / X 数据导出 tweets.js / csv / txt(md)，返回统一字段列表。"""
    with open(path, encoding="utf-8-sig") as f:
        raw_text = f.read()
    ext = os.path.splitext(path)[1].lower()
    items = []
    if ext in (".jsonl", ".ndjson"):
        for line in raw_text.splitlines():
            line = line.strip()
            if line:
                items.append(json.loads(line))
    elif ext in (".json", ".js"):
        body = raw_text.strip()
        if ext == ".js" or not body.startswith(("[", "{")):
            body = body[body.index("["):]  # window.YTD.tweets.part0 = [...]
        data = json.loads(body)
        if isinstance(data, dict):
            for key in ("posts", "tweets", "data"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
            else:
                data = [data]
        items = data
    elif ext == ".csv":
        items = list(csv.DictReader(io.StringIO(raw_text)))
    else:
        items = [{"text": t} for t in _split_plain(raw_text)]
    posts = [normalize(i) for i in items if isinstance(i, dict)]
    if not keep_empty:
        posts = [p for p in posts if p["text"]]
    return posts


def write_jsonl(posts, path):
    f = open(path, "w", encoding="utf-8") if path and path != "-" else None
    try:
        for p in posts:
            line = json.dumps(p, ensure_ascii=False)
            if f:
                f.write(line + "\n")
            else:
                print(line)
    finally:
        if f:
            f.close()


def lines_of(text):
    return [l.strip() for l in text.split("\n") if l.strip()]


def features(text):
    ls = lines_of(text)
    body = URL_RE.sub("", text)
    return {
        "chars": len(re.sub(r"\s", "", body)),
        "lines": len(ls),
        "emoji": len(EMOJI_RE.findall(text)),
        "exclaim": len(re.findall(r"[！!]", text)),
        "ends_question": bool(ls) and ls[-1].rstrip("😂🤣😳😱🙏 ").endswith(("？", "?")),
        "has_url": bool(URL_RE.search(text)),
        "has_digit": bool(re.search(r"\d", text)),
    }


def engagement(p):
    """排序用的互动分：收藏最重，其次回复、点赞。缺失当 0。"""
    return (p.get("bookmarks") or 0) * 3 + (p.get("replies") or 0) * 2 + (p.get("likes") or 0)


def median(xs):
    xs = sorted(xs)
    if not xs:
        return 0
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]
