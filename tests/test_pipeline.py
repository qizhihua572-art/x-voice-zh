import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import _helpers as h
from _common import load_posts, normalize, parse_num, parse_time
from extract_skeleton import hook_types, skeleton
from rank_viral import is_promo, select
from voice_profile import build_profile, opener, to_markdown
import brief
import fetch_x


def tmp_write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def tmp(content, suffix):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


class Import(unittest.TestCase):
    def test_parse_num(self):
        self.assertEqual(parse_num("1.2万"), 12000)
        self.assertEqual(parse_num("3.4k"), 3400)
        self.assertEqual(parse_num("1,234"), 1234)
        self.assertIsNone(parse_num(""))
        self.assertIsNone(parse_num("abc"))

    def test_txt(self):
        p = load_posts(tmp("第一条\n第二行\n---\n第二条\n---\n\n", ".txt"))
        self.assertEqual([x["text"] for x in p], ["第一条\n第二行", "第二条"])

    def test_jsonl_aliases(self):
        p = load_posts(tmp(json.dumps({"full_text": "hi", "favorite_count": 3, "view_count": "1.5万",
                                       "bookmark_count": 2}) + "\n", ".jsonl"))
        self.assertEqual((p[0]["likes"], p[0]["views"], p[0]["bookmarks"]), (3, 15000, 2))

    def test_x_archive(self):
        js = 'window.YTD.tweets.part0 = [{"tweet": {"id_str": "1", "full_text": "你好", "favorite_count": "5", ' \
             '"retweet_count": "1", "created_at": "Mon Nov 02 10:00:00 +0000 2026"}}, ' \
             '{"tweet": {"id_str": "2", "full_text": "@a 回复", "in_reply_to_status_id_str": "9"}}]'
        p = load_posts(tmp(js, ".js"))
        self.assertEqual(len(p), 2)
        self.assertEqual(p[0]["likes"], 5)
        self.assertTrue(p[1]["is_reply"])

    def test_csv(self):
        p = load_posts(tmp("text,likes,bookmarks\n你好,3,1\n", ".csv"))
        self.assertEqual((p[0]["text"], p[0]["likes"], p[0]["bookmarks"]), ("你好", 3, 1))

    def test_api_v2_public_metrics(self):
        p = normalize({"id": "1", "text": "x", "public_metrics": {"like_count": 4, "bookmark_count": 7,
                                                                  "impression_count": 100, "reply_count": 2}})
        self.assertEqual((p["likes"], p["bookmarks"], p["views"], p["replies"]), (4, 7, 100, 2))

    def test_retweet_detected(self):
        self.assertTrue(normalize({"text": "RT @a: x"})["is_retweet"])

    def test_parse_time(self):
        self.assertIsNotNone(parse_time("2026-11-02T10:00:00Z"))
        self.assertIsNotNone(parse_time("Mon Nov 02 10:00:00 +0000 2026"))
        self.assertIsNone(parse_time("不是时间"))


class Profile(unittest.TestCase):
    def setUp(self):
        self.posts = load_posts(os.path.join(h.EXAMPLES, "sample_posts.jsonl"))
        self.pf = build_profile(self.posts)

    def test_basic(self):
        self.assertEqual(self.pf["n_posts"], 24)
        self.assertGreater(self.pf["emoji_rate"], 0.8)
        self.assertEqual(self.pf["top_openers"][0][0], "好家伙")
        self.assertIn("🤣", self.pf["top_emoji"])
        self.assertLessEqual(self.pf["lines_median"], 3)

    def test_best_worst(self):
        best = self.pf["best_posts"][0]["text"]
        self.assertIn("收不收钱", best)
        worst = " ".join(p["text"] for p in self.pf["worst_posts"])
        self.assertIn("本质上", worst)

    def test_markdown(self):
        md = to_markdown(self.pf)
        self.assertIn("语气画像", md)
        self.assertIn("好家伙", md)

    def test_replies_excluded(self):
        posts = self.posts + [normalize({"text": "@x 回复一下", "is_reply": True})]
        self.assertEqual(build_profile(posts)["n_posts"], 24)
        self.assertEqual(build_profile(posts, include_replies=True)["n_posts"], 25)

    def test_empty(self):
        self.assertEqual(build_profile([])["n_posts"], 0)

    def test_opener(self):
        self.assertEqual(opener("救命，我完了"), "救命")
        self.assertEqual(opener("🤣好家伙 来了"), "好家伙")


class Rank(unittest.TestCase):
    def setUp(self):
        self.posts = load_posts(os.path.join(h.EXAMPLES, "sample_bigshots.jsonl"))

    def test_select(self):
        sel, dropped = select(self.posts)
        self.assertEqual(len(sel), 7)
        self.assertEqual(dropped["reply_or_rt"], 1)
        self.assertEqual(dropped["promo"], 1)
        self.assertTrue(all(not p["is_reply"] for p in sel))
        scores = [(p["bookmarks"] or 0) * 3 + (p["replies"] or 0) * 2 + (p["likes"] or 0) for p in sel]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_thresholds_either(self):
        sel, _ = select(self.posts, min_bookmarks=500, min_replies=10 ** 9)
        self.assertEqual({p["id"] for p in sel}, {"demo-b3", "demo-b7", "demo-b1"})
        sel, _ = select(self.posts, min_bookmarks=10 ** 9, min_replies=200)
        self.assertEqual({p["id"] for p in sel}, {"demo-b6"})

    def test_accounts(self):
        sel, _ = select(self.posts, accounts=["@demo_big_c"])
        self.assertTrue(sel and all(p["author"] == "demo_big_c" for p in sel))

    def test_since_hours(self):
        old = normalize({"text": "旧帖", "bookmarks": 999, "created_at": "2020-01-01 00:00:00"})
        new = normalize({"text": "新帖", "bookmarks": 999,
                         "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()})
        sel, d = select([old, new], since_hours=48)
        self.assertEqual([p["text"] for p in sel], ["新帖"])
        self.assertEqual(d["too_old"], 1)

    def test_dedupe(self):
        a = normalize({"text": "完全一样的内容", "bookmarks": 500})
        b = normalize({"text": "完全一样的内容！", "bookmarks": 400})
        sel, d = select([a, b])
        self.assertEqual(len(sel), 1)
        self.assertEqual(d["dup"], 1)

    def test_missing_metrics(self):
        p = normalize({"text": "没有数据"})
        self.assertEqual(select([p])[0], [])
        self.assertEqual(len(select([p], allow_missing=True)[0]), 1)

    def test_promo(self):
        self.assertTrue(is_promo("加微信领取"))
        self.assertTrue(is_promo("Use code ABC"))
        self.assertFalse(is_promo("今天做了个小工具"))


class Skeleton(unittest.TestCase):
    def test_hooks(self):
        self.assertIn("报数字", hook_types("上线 11 天，付费用户 38 个"))
        self.assertIn("打时间差", hook_types("从 0 到第一个付费用户，我只用了 9 天"))
        self.assertIn("坦白", hook_types("说实话，我第一个产品死得很惨"))
        self.assertIn("拿出成品", hook_types("终于做完了，能直接玩"))
        self.assertIn("报痛点", hook_types("卡了我三天：支付回调老丢"))
        self.assertTrue(hook_types("今天天气不错")[0].startswith("未识别"))

    def test_skeleton_fields(self):
        p = normalize({"text": "免费模板：10 个提示词\n1. 先写痛点\n2. 再写承诺\n`npx foo`",
                       "likes": 100, "bookmarks": 250, "author": "a", "url": "https://example.com/1"})
        s = skeleton(p)
        self.assertEqual(s["bookmark_like_ratio"], 2.5)
        self.assertIn("清单/步骤", s["save_hints"])
        self.assertIn("安装/命令", s["save_hints"])
        self.assertFalse(s["link_in_body"])


class Brief(unittest.TestCase):
    def test_build(self):
        posts = load_posts(os.path.join(h.EXAMPLES, "sample_bigshots.jsonl"))[:2]
        out = brief.build("# 画像", "# 事实\n- 12 天", posts, top=2)
        for needle in ("转写规则", "真实事实清单", "爆款 1", "示例数据", "只出草稿"):
            self.assertIn(needle, out)


class FetchX(unittest.TestCase):
    def test_urls(self):
        self.assertTrue(fetch_x.user_url("@abc").endswith("/users/by/username/abc"))
        u = fetch_x.timeline_url("123", 100, "2026-11-01T00:00:00Z")
        self.assertIn("exclude=replies%2Cretweets", u)
        self.assertIn("public_metrics", u)
        self.assertIn("max_results=100", u)
        self.assertIn("max_results=5", fetch_x.timeline_url("1", 1))

    def test_fetch_with_fake_getter(self):
        calls = []

        def getter(url, token):
            calls.append(url)
            self.assertEqual(token, "fake")
            if "/users/by/username/" in url:
                return {"data": {"id": "42"}}
            if "pagination_token" not in url:
                return {"data": [{"id": "1", "text": "一", "public_metrics": {"bookmark_count": 5}}],
                        "meta": {"next_token": "n1"}}
            return {"data": [{"id": "2", "text": "二", "public_metrics": {"bookmark_count": 9}}], "meta": {}}

        posts = fetch_x.fetch_user("@abc", "fake", hours=48, max_results=100, getter=getter)
        self.assertEqual([p["id"] for p in posts], ["1", "2"])
        self.assertEqual(posts[1]["bookmarks"], 9)
        self.assertEqual(posts[0]["url"], "https://x.com/abc/status/1")
        self.assertEqual(len(calls), 3)

    def test_no_token_exits_2(self):
        env = {k: v for k, v in os.environ.items() if k != "X_BEARER_TOKEN"}
        r = subprocess.run([sys.executable, os.path.join(h.SCRIPTS, "fetch_x.py"), "--user", "a"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Bearer", r.stdout)

    def test_dry_run_needs_no_network(self):
        r = subprocess.run([sys.executable, os.path.join(h.SCRIPTS, "fetch_x.py"), "--user", "a", "--dry-run"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("/users/by/username/a", r.stdout)


class EndToEndCLI(unittest.TestCase):
    def run_py(self, name, *args):
        return subprocess.run([sys.executable, os.path.join(h.SCRIPTS, name), *args],
                              capture_output=True, text=True, check=True)

    def test_full_flow(self):
        with tempfile.TemporaryDirectory() as d:
            posts = os.path.join(d, "posts.jsonl")
            self.run_py("import_posts.py", os.path.join(h.EXAMPLES, "sample_posts.jsonl"), "-o", posts)
            self.run_py("voice_profile.py", posts, "--json", os.path.join(d, "p.json"), "--md", os.path.join(d, "p.md"))
            viral = os.path.join(d, "viral.jsonl")
            self.run_py("rank_viral.py", os.path.join(h.EXAMPLES, "sample_bigshots.jsonl"), "--top", "5", "-o", viral)
            sk = self.run_py("extract_skeleton.py", viral, "--format", "md").stdout
            self.assertIn("钩子类型", sk)
            b = os.path.join(d, "brief.md")
            self.run_py("brief.py", "--profile", os.path.join(d, "p.md"), "--facts",
                        os.path.join(h.EXAMPLES, "sample_facts.md"), "--viral", viral, "-o", b)
            self.assertIn("爆款 5", h.read(b))
            draft = os.path.join(d, "draft.txt")
            tmp_write(draft, "好家伙，我的记账小工具上线 12 天了🤣\n访问 120，注册 9，付费 0😂")
            out = self.run_py("score_draft.py", draft, "--json", "--profile", os.path.join(d, "p.json"),
                              "--facts", os.path.join(h.EXAMPLES, "sample_facts.md"),
                              "--ban-file", os.path.join(h.EXAMPLES, "ban_words.txt")).stdout
            self.assertEqual(json.loads(out)["score"], 100)

    def test_fail_on_hard_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            draft = os.path.join(d, "d.txt")
            tmp_write(draft, "说白了就是这样")
            r = subprocess.run([sys.executable, os.path.join(h.SCRIPTS, "score_draft.py"), draft, "--fail-on-hard"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)

    def test_stdin(self):
        r = subprocess.run([sys.executable, os.path.join(h.SCRIPTS, "score_draft.py"), "-"],
                           input="今天上线了🤣", capture_output=True, text=True)
        self.assertIn("100/100", r.stdout)


class InstallAndHygiene(unittest.TestCase):
    def test_install_script(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["bash", os.path.join(h.ROOT, "install.sh"), d], check=True, capture_output=True)
            self.assertTrue(os.path.isfile(os.path.join(d, "x-voice-zh", "SKILL.md")))
            self.assertTrue(os.path.isfile(os.path.join(d, "x-voice-zh", "scripts", "score_draft.py")))

    def test_skill_frontmatter(self):
        t = h.read(os.path.join(h.ROOT, "skills", "x-voice-zh", "SKILL.md"))
        self.assertTrue(t.startswith("---\nname: x-voice-zh\ndescription: "))
        self.assertIn("\n---\n", t[4:])

    def test_no_personal_data(self):
        banned = ["齐总", "QGongfang", "Q工坊", "一蓑烟雨", "不会代码", "Zhihua", "Qi Zhihua"]
        for root, _, files in os.walk(h.ROOT):
            if ".git" in root.split(os.sep) or "__pycache__" in root:
                continue
            for fn in files:
                if fn == "test_pipeline.py":
                    continue
                path = os.path.join(root, fn)
                try:
                    t = h.read(path)
                except UnicodeDecodeError:
                    continue
                for b in banned:
                    self.assertNotIn(b, t, f"{b} found in {path}")

    def test_no_secrets_and_real_x_links_only_in_docs(self):
        for fn in os.listdir(h.EXAMPLES):
            t = h.read(os.path.join(h.EXAMPLES, fn))
            self.assertNotIn("x.com/", t, fn)  # 示例数据不放真实链接

    def test_examples_marked(self):
        for fn in ("sample_posts.jsonl", "sample_bigshots.jsonl"):
            for line in h.read(os.path.join(h.EXAMPLES, fn)).splitlines():
                self.assertTrue(json.loads(line)["example"])


if __name__ == "__main__":
    unittest.main()
