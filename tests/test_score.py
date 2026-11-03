import json
import os
import re
import unittest

import _helpers as h
from score_draft import score, split_drafts


def ids(r, kind="hard"):
    return {x["id"] for x in r[kind]}


class HardRules(unittest.TestCase):
    def test_flip(self):
        self.assertIn("H01", ids(score("这不是工具的问题，而是你没想清楚。")))
        self.assertIn("H01", ids(score("与其说是运气，不如说是积累。")))
        self.assertIn("H01", ids(score("你以为是价格问题，其实是没人知道你。")))

    def test_flip_negative(self):
        self.assertNotIn("H01", ids(score("我不是不想发，我是不知道发什么😂")))
        self.assertNotIn("H01", ids(score("这个按钮不是蓝色的。而是我改成了绿色。")))  # 跨句不算

    def test_closer(self):
        self.assertIn("H02", ids(score("做了三个功能。\n本质上，工具人人都有。")))
        self.assertIn("H02", ids(score("做了三个功能。\n未来属于会用 AI 的人。")))
        self.assertNotIn("H02", ids(score("做了三个功能🤣\n晚点再改")))

    def test_forced_question(self):
        self.assertIn("H03", ids(score("今天上线了。\n你怎么看？")))
        self.assertIn("H03", ids(score("今天上线了。\n欢迎留言讨论")))
        self.assertNotIn("H03", ids(score("定价少打了小数点🥲\n你们上线前都会检查什么？")))

    def test_clickbait(self):
        self.assertIn("H04", ids(score("90%的人都不知道这个技巧")))
        self.assertIn("H04", ids(score("震惊！这个工具太强了")))

    def test_parallel(self):
        r = score("他会写代码\n他会做设计\n他会写文案")
        self.assertIn("H05", ids(r))
        self.assertNotIn("H05", ids(score("他会写代码\n我会写文案\n你会做设计")))

    def test_catchphrase_label_filler(self):
        self.assertIn("H06", ids(score("说白了就是要先收钱")))
        self.assertIn("H07", ids(score("核心是：先收钱")))
        self.assertIn("H08", ids(score("让我们拭目以待")))
        self.assertIn("H08", ids(score("好问题，我来回答")))

    def test_emoji_bullets(self):
        self.assertIn("H09", ids(score("✅ 省钱\n✅ 省时间")))
        self.assertNotIn("H09", ids(score("省钱✅\n省时间✅")))

    def test_exclaim_and_fake_friend(self):
        self.assertIn("H10", ids(score("太强了！！！")))
        self.assertNotIn("H10", ids(score("太强了！")))
        self.assertIn("H11", ids(score("我有个朋友靠这个月入过万")))

    def test_ban_words(self):
        r = score("这个办法保证涨粉", ban_words=["保证涨粉"])
        self.assertIn("H12", ids(r))
        self.assertNotIn("H12", ids(score("这个办法有用", ban_words=["保证涨粉"])))


class SoftAndScore(unittest.TestCase):
    def test_soft(self):
        self.assertIn("S01", ids(score("然而我还是做完了"), "soft"))
        self.assertIn("S02", ids(score("我用了 A、B、C 三个工具"), "soft"))
        self.assertIn("S03", ids(score("成本降低了，大幅提升 30%"), "soft"))
        self.assertIn("S04", ids(score("答案很简单——先收钱"), "soft"))
        self.assertIn("S06", ids(score("代码在 https://example.com/x"), "soft"))
        self.assertIn("S09", ids(score("今天上线 #a #b #c"), "soft"))
        self.assertIn("S10", ids(score("建议收藏，以后用得上"), "soft"))
        self.assertIn("S11", ids(score("1. 先做\n2. 再测\n3. 后发"), "soft"))
        self.assertIn("S08", ids(score("不是我不想，是真没时间"), "soft"))

    def test_too_long(self):
        long = "\n".join(["第%d行内容在这里" % i for i in range(8)])
        self.assertIn("S05", ids(score(long), "soft"))

    def test_facts_numbers(self):
        facts = "访问 120，注册 9，付费 0。价格 5 刀。"
        ok = score("访问 120，注册 9，付费 0🤣", facts_text=facts)
        self.assertNotIn("S07", ids(ok, "soft"))
        bad = score("访问 120，付费用户 38 个🤣", facts_text=facts)
        self.assertIn("S07", ids(bad, "soft"))
        self.assertIn("38", [x for x in bad["soft"] if x["id"] == "S07"][0]["match"])

    def test_numbered_list_not_counted_as_fact(self):
        r = score("1. 访问 120\n2. 注册 9", facts_text="访问 120 注册 9")
        self.assertNotIn("S07", ids(r, "soft"))

    def test_profile_mismatch(self):
        pf = {"n_posts": 20, "emoji_rate": 0.9, "lines_p90": 3, "chars_p90": 40}
        self.assertIn("S12", ids(score("今天上线了", profile=pf), "soft"))
        self.assertNotIn("S12", ids(score("今天上线了🤣", profile=pf), "soft"))

    def test_blanks(self):
        r = score("我的小游戏做了 __ 天🤣")
        self.assertEqual(r["blanks"], 1)
        self.assertFalse(r["ready_to_post"])
        self.assertIn("空位", r["verdict"])
        r2 = score("我的小游戏做了 12 天🤣")
        self.assertTrue(r2["ready_to_post"])
        self.assertEqual(r2["score"], 100)

    def test_blank_content_not_checked(self):
        r = score("今天上线了 【待补：本质上的原因】🤣")
        self.assertNotIn("H02", ids(r))

    def test_penalties(self):
        r = score("说白了，这不是工具的问题，而是你没想清楚")
        self.assertEqual(r["score"], 100 - 20 * len(r["hard"]) - 6 * len(r["soft"]))
        self.assertTrue(r["verdict"].startswith("重写"))

    def test_deterministic(self):
        t = "说白了，这不是工具的问题，而是你没想清楚。\n你怎么看？"
        self.assertEqual(score(t), score(t))

    def test_same_rule_counted_once(self):
        r = score("不是A而是B。不是C而是D。")
        self.assertEqual(len([x for x in r["hard"] if x["id"] == "H01"]), 1)

    def test_split_drafts(self):
        self.assertEqual(len(split_drafts("a\n---\nb\n---\nc")), 3)


class ExampleDrafts(unittest.TestCase):
    def test_sample_output_drafts_pass(self):
        text = h.read(os.path.join(h.EXAMPLES, "sample_output.md"))
        facts = h.read(os.path.join(h.EXAMPLES, "sample_facts.md"))
        drafts = re.findall(r"```draft\n(.*?)```", text, re.S)
        self.assertEqual(len(drafts), 3)
        for d in drafts:
            r = score(d, facts_text=facts)
            self.assertEqual(r["hard"], [], d)
            self.assertEqual(r["soft"], [], d)


if __name__ == "__main__":
    unittest.main()
