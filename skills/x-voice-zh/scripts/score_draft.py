#!/usr/bin/env python3
"""中文「去 AI 味」规则打分器：纯规则，不调模型，同一段文字永远同一个分。

用法:
  python score_draft.py draft.txt
  python score_draft.py drafts.txt --json          # 多条草稿用单独一行 --- 隔开
  echo "草稿" | python score_draft.py -
  python score_draft.py draft.txt --profile profile.json --facts facts.md --ban-words 词1,词2

硬禁项命中 = 重写；软项只提示，别硬改。空位（__）没补完 = 不能发。
规则说明见 references/de-ai-rules.md，评分口径见 references/score-rubric.md。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import EMOJI_RE, URL_RE, features, lines_of  # noqa: E402

HARD_PENALTY = 20
SOFT_PENALTY = 6

BLANK_RE = re.compile(r"_{2,}|＿{2,}|【待补[^】]*】|\[待补[^\]]*\]")
SENT_SPLIT = re.compile(r"[。！？!?；;\n]")
CLOSER_RE = re.compile(r"本质上|归根结底|归根到底|说到底|终究|才是真正的|未来属于|赢家永远")
CLOSER_ANY_RE = re.compile(r"本质上|归根结底|归根到底")
FORCED_Q_RE = re.compile(r"你怎么看|你觉得呢|你同意吗|你敢吗|你站[哪谁]|评论区(聊聊|见|告诉我|说说)|欢迎(留言|评论|讨论)|说说你的(看法|想法)|你会选|你选哪个")
CLICKBAIT_RE = re.compile(r"(9\d|九成|绝大多数|大部分)\s*%?的人(都)?(不知道|不会|不懂|想不到)|^停止|震惊|重磅|炸裂|颠覆")
CATCHPHRASE_RE = re.compile(r"说白了|说穿了|先说结论|一句话总结|简单来说|总的来说")
LABEL_COLON_RE = re.compile(r"(核心是|关键在于|关键是|原因如下|总结|重点是|结论|答案)[:：]")
FILLER_RE = re.compile(r"让我们|深入(看看|探讨|了解)|不要误会|别误会|好问题|希望(这|对你)?.{0,4}帮助|拭目以待|值得一提的是|综上所述|需要注意的是|不难发现")
FAKE_FRIEND_RE = re.compile(r"我有个朋友|我一个朋友|有个粉丝跟我说|有位读者告诉我")
FLIP_PATTERNS = [
    re.compile(r"不是.{1,30}?而是"), re.compile(r"并非.{1,30}?而是"),
    re.compile(r"与其说.{1,30}?不如说"), re.compile(r"(表面|看似|看起来).{1,30}?(实际|实则)"),
    re.compile(r"你以为.{1,30}?其实"),
]
SOFT_FLIP_RE = re.compile(r"不是.{1,20}?[，,]\s*是")
CONNECTOR_RE = re.compile(r"^(然而|因此|此外|总之|综上)")
VAGUE_RE = re.compile(r"(大幅|显著|极大|大大|明显)(提升|提高|降低|增强|优化)")
BEG_SAVE_RE = re.compile(r"建议收藏|一定要收藏|收藏起来|先收藏|点赞收藏|转发收藏")
LIST_ITEM_RE = re.compile(r"^\s*([1-9][.、)）]|[①②③④⑤]|[-•·])")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

RULES = {
    "H01": ("翻案腔（不是…而是…）", "只在前后两半都有信息时才留；否则直接说结论"),
    "H02": ("金句/升维收尾", "删掉最后一句，用前一句收尾"),
    "H03": ("硬凑互动的结尾提问", "只留一个你真想知道答案的具体问题，或者不收尾"),
    "H04": ("标题党钩子（90%的人不知道/停止…/震惊）", "换成你自己的事或具体数字开头"),
    "H05": ("三连排比（连续三行同一个开头）", "留最有信息的一行，其余合并或删"),
    "H06": ("口头禅起手（说白了/先说结论/一句话总结）", "直接说内容"),
    "H07": ("提示语冒号（核心是：/总结：）", "去掉标签，直接写内容"),
    "H08": ("铺垫或客服腔（让我们/好问题/拭目以待）", "删掉，只保留后面的内容"),
    "H09": ("emoji 当项目符号（每行开头一个表情）", "表情放句末，别放行首"),
    "H10": ("感叹号连发", "最多一个"),
    "H11": ("虚构人物故事（我有个朋友…）", "换成你自己真实的经历，没有就删"),
    "H12": ("命中你设定的禁用词", "改掉或删掉"),
    "S01": ("句首路标词（然而/因此/此外）", "口语里直接接下一句"),
    "S02": ("顿号罗列过密（一个分句 3 项以上）", "挑最重要的两项"),
    "S03": ("概括词盖住数字（大幅提升）", "直接写数字"),
    "S04": ("破折号当悬念", "改成逗号或句号"),
    "S05": ("太长（超过行数/字数上限）", "删到你平时的长度"),
    "S06": ("链接在正文里", "挪到评论区，正文里降权"),
    "S07": ("数字没出现在事实清单/原帖里", "核实后再用，核实不了就换成空位 __ 或删"),
    "S08": ("不是 A，是 B 句式", "两半都有信息才留"),
    "S09": ("话题标签超过 2 个", "留 0–2 个"),
    "S10": ("求收藏/求转发", "让内容本身值得收藏，别开口要"),
    "S11": ("三点清单式", "口语帖少用「1/2/3」，挑一点说透"),
    "S12": ("和你的语气画像不一致", "对照画像里的长度和表情习惯改"),
}


def _hit(rid, match, line=None):
    name, fix = RULES[rid]
    return {"id": rid, "name": name, "match": match, "line": line, "fix": fix}


def _strip_emoji(s):
    return EMOJI_RE.sub("", s).strip()


def _numbers(text):
    out = set()
    for m in NUM_RE.findall(text):
        out.add(m.replace(",", "").rstrip("0").rstrip(".") if "." in m else m.replace(",", ""))
    return out


def score(text, profile=None, facts_text=None, ban_words=None, max_lines=None, max_chars=None):
    body = text.strip()
    ls = lines_of(body)
    hard, soft = [], []
    blanks = BLANK_RE.findall(body)
    probe = BLANK_RE.sub("", body)  # 规则只检查已写的部分
    plines = lines_of(probe)
    last_line = _strip_emoji(plines[-1]) if plines else ""

    for sent in SENT_SPLIT.split(probe):
        for rx in FLIP_PATTERNS:
            m = rx.search(sent)
            if m:
                hard.append(_hit("H01", m.group(0)))
                break
    m = CLOSER_ANY_RE.search(probe) or CLOSER_RE.search(last_line)
    if m:
        hard.append(_hit("H02", m.group(0)))
    if last_line and (m := FORCED_Q_RE.search(last_line)):
        hard.append(_hit("H03", m.group(0)))
    for l in plines:
        if m := CLICKBAIT_RE.search(_strip_emoji(l)):
            hard.append(_hit("H04", m.group(0)))
            break
    # H05：连续三行同一个开头（前 2 个汉字/字符相同）
    heads = [re.sub(r"^[\s\d.、)）①②③④⑤\-•·]+", "", _strip_emoji(l))[:2] for l in plines]
    for i in range(len(heads) - 2):
        if len(heads[i]) == 2 and heads[i] == heads[i + 1] == heads[i + 2]:
            hard.append(_hit("H05", "「" + heads[i] + "…」连续三行", i + 1))
            break
    if m := CATCHPHRASE_RE.search(probe):
        hard.append(_hit("H06", m.group(0)))
    if m := LABEL_COLON_RE.search(probe):
        hard.append(_hit("H07", m.group(0)))
    if m := FILLER_RE.search(probe):
        hard.append(_hit("H08", m.group(0)))
    emoji_heads = [l for l in plines if EMOJI_RE.match(l)]
    if len(emoji_heads) >= 2:
        hard.append(_hit("H09", f"{len(emoji_heads)} 行以表情开头"))
    if re.search(r"[！!]{3,}", probe) or len(re.findall(r"[！!]", probe)) >= 5:
        hard.append(_hit("H10", "感叹号过多"))
    if m := FAKE_FRIEND_RE.search(probe):
        hard.append(_hit("H11", m.group(0)))
    for w in ban_words or []:
        if w and w in probe:
            hard.append(_hit("H12", w))

    # ---- 软项 ----
    for i, l in enumerate(plines, 1):
        if m := CONNECTOR_RE.match(_strip_emoji(l)):
            soft.append(_hit("S01", m.group(0), i))
            break
    for clause in re.split(r"[，,。！？!?；;\n]", probe):
        if clause.count("、") >= 2:
            soft.append(_hit("S02", clause.strip()[:20]))
            break
    if re.search(r"\d", probe) and (m := VAGUE_RE.search(probe)):
        soft.append(_hit("S03", m.group(0)))
    if "——" in probe or re.search(r"(?<!-)—(?!-)", probe):
        soft.append(_hit("S04", "破折号"))
    f = features(probe)
    ml = max_lines or (int(profile["lines_p90"]) + 1 if profile and profile.get("lines_p90") else 5)
    mc = max_chars or (int(profile["chars_p90"] * 1.3) if profile and profile.get("chars_p90") else 160)
    if f["lines"] > ml or f["chars"] > mc:
        soft.append(_hit("S05", f"{f['lines']} 行 / {f['chars']} 字，上限 {ml} 行 / {mc} 字"))
    if URL_RE.search(probe):
        soft.append(_hit("S06", URL_RE.search(probe).group(0)[:30]))
    if facts_text is not None:
        known = _numbers(facts_text)
        nums = _numbers("\n".join(LIST_ITEM_RE.sub("", l) for l in plines))
        bad = sorted(n for n in nums if n not in known)
        if bad:
            soft.append(_hit("S07", "、".join(bad[:6])))
    if SOFT_FLIP_RE.search(probe) and not any(h["id"] == "H01" for h in hard):
        soft.append(_hit("S08", SOFT_FLIP_RE.search(probe).group(0)))
    if len(re.findall(r"#\S+", probe)) > 2:
        soft.append(_hit("S09", "标签过多"))
    if m := BEG_SAVE_RE.search(probe):
        soft.append(_hit("S10", m.group(0)))
    if sum(1 for l in plines if LIST_ITEM_RE.match(l)) >= 3:
        soft.append(_hit("S11", "三条以上编号/符号清单"))
    if profile and profile.get("n_posts"):
        if profile.get("emoji_rate", 0) >= 0.4 and f["emoji"] == 0:
            soft.append(_hit("S12", "你的帖子常用表情，这条一个都没有"))

    def _dedupe(hits):
        seen, out = set(), []
        for h in hits:
            key = (h["id"], h["match"]) if h["id"] == "H12" else h["id"]
            if key not in seen:
                seen.add(key)
                out.append(h)
        return out

    hard, soft = _dedupe(hard), _dedupe(soft)
    penalty = HARD_PENALTY * len(hard) + SOFT_PENALTY * len(soft)
    sc = max(0, 100 - penalty)
    if hard:
        verdict = "重写：有硬禁项"
    elif blanks:
        verdict = f"还有 {len(blanks)} 个空位没补，补完再发"
    elif soft:
        verdict = "基本可发，软提示看一眼"
    else:
        verdict = "可发"
    return {
        "score": sc, "verdict": verdict, "hard": hard, "soft": soft,
        "blanks": len(blanks),
        "ready_to_post": not hard and not blanks,
        "stats": {"lines": f["lines"], "chars": f["chars"], "emoji": f["emoji"]},
    }


def to_text(r, idx=None):
    L = [f"{'#' + str(idx) + ' ' if idx else ''}得分 {r['score']}/100 — {r['verdict']}"]
    for h in r["hard"]:
        L.append(f"  [硬] {h['id']} {h['name']}：{h['match']} → {h['fix']}")
    for h in r["soft"]:
        L.append(f"  [软] {h['id']} {h['name']}：{h['match']} → {h['fix']}")
    if r["blanks"]:
        L.append(f"  [空] {r['blanks']} 个空位（__）需要你自己补")
    L.append(f"  统计：{r['stats']['lines']} 行 / {r['stats']['chars']} 字 / {r['stats']['emoji']} 个表情")
    return "\n".join(L)


def split_drafts(raw):
    parts = re.split(r"(?m)^\s*---+\s*$", raw)
    return [p.strip() for p in parts if p.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="草稿文件，- 表示从标准输入读")
    ap.add_argument("--json", action="store_true", help="输出 json")
    ap.add_argument("--profile", help="voice_profile.py 生成的 profile.json")
    ap.add_argument("--facts", help="你的真实事实清单（文本/markdown），用来核对数字")
    ap.add_argument("--ban-words", default="", help="你自己的禁用词，逗号分隔")
    ap.add_argument("--ban-file", help="禁用词文件，一行一个，# 开头是注释")
    ap.add_argument("--fail-on-hard", action="store_true", help="有硬禁项时退出码为 1")
    a = ap.parse_args(argv)
    raw = sys.stdin.read() if a.input == "-" else open(a.input, encoding="utf-8").read()
    profile = json.load(open(a.profile, encoding="utf-8")) if a.profile else None
    facts = open(a.facts, encoding="utf-8").read() if a.facts else None
    bans = [w.strip() for w in a.ban_words.split(",") if w.strip()]
    if a.ban_file:
        bans += [l.strip() for l in open(a.ban_file, encoding="utf-8")
                 if l.strip() and not l.lstrip().startswith("#")]
    drafts = split_drafts(raw) or [""]
    results = [score(d, profile, facts, bans) for d in drafts]
    if a.json:
        print(json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2))
    else:
        for i, r in enumerate(results, 1):
            print(to_text(r, i if len(results) > 1 else None))
    return 1 if a.fail_on_hard and any(r["hard"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
