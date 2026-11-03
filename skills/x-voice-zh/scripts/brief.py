#!/usr/bin/env python3
"""把「语气画像 + 事实清单 + 爆款骨架 + 原帖」拼成一份给 AI 读的转写任务单。

AI（Claude Code / Codex）读完这份任务单，按 SKILL.md 第 4 步写草稿，
写完再用 score_draft.py 打分。

用法:
  python brief.py --profile profile.md --facts facts.md --viral viral.jsonl --top 5 -o brief.md
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_posts  # noqa: E402
from extract_skeleton import skeleton  # noqa: E402

RULES = """## 转写规则（必须遵守）
1. 只留原帖的骨架（钩子类型、结构、形式），不照抄原帖措辞。
2. 事实只能来自上面的「真实事实清单」。清单里没有的经历、数字，一律留空位 `__`，不许编。
3. 别人帖子里的数字，只能写「作者说」，不当成我的事实。
4. 对不上事实清单的爆款，直接标「不转」并说明原因，不硬凑。
5. 正文不放链接；链接放评论区，在「怎么发」里说明。
6. 写完用 `score_draft.py` 打分，有硬禁项就重写。
7. 只出草稿，不替用户发帖、回复或联系任何人。
"""


def build(profile_md, facts_md, posts, top=5):
    L = ["# 转写任务单", "", "## 我的语气画像", profile_md.strip() or "（未提供，先跑 voice_profile.py）", "",
         "## 我的真实事实清单（只准用这里面的事实）", facts_md.strip() or "（未提供：所有个人经历都必须留空位）", "",
         RULES, "## 候选爆款（已按互动排序）"]
    for i, p in enumerate(posts[:top], 1):
        s = skeleton(p)
        tag = "（示例数据）" if s["example"] else ""
        L += [f"### 爆款 {i}{tag}：{s['author'] or '未知'}",
              f"- 原帖链接：{s['url'] or '无'}",
              f"- 数据：浏览 {s['views']} / 回复 {s['replies']} / 收藏 {s['bookmarks']}",
              f"- 规则判断的钩子类型：{'、'.join(s['hook_types'])}（请复核）",
              f"- 结构：{s['lines']} 行 / {s['chars']} 字；形式：{'有图/视频线索' if s['media_hint'] else '纯文字或未知'}",
              f"- 可收藏线索：{'、'.join(s['save_hints']) or '无明显线索'}",
              "- 原文（只用来拆骨架，别抄）：", "```", p["text"], "```", ""]
    L += ["## 请按这个格式输出（首推排最前，最多 5 条）",
          "每条：原帖链接和真实数字 / 一句话说为什么火（要有依据）/ 转写草稿 / 怎么发 / 要补的空 / 要先做完的事"]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", help="画像 markdown（voice_profile.py --md 生成并润色后的）")
    ap.add_argument("--facts", help="真实事实清单文件")
    ap.add_argument("--viral", required=True, help="爆款 jsonl（rank_viral.py 输出）")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("-o", "--out", default="-")
    a = ap.parse_args(argv)
    rd = lambda p: open(p, encoding="utf-8").read() if p else ""
    out = build(rd(a.profile), rd(a.facts), load_posts(a.viral), a.top)
    if a.out == "-":
        print(out)
    else:
        open(a.out, "w", encoding="utf-8").write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
