---
name: x-voice-zh
description: 中文 X（推特）爆款转化。学用户自己的语气，从同赛道账号里筛爆款帖、拆骨架，用用户的真实经历改写成他自己的帖子（不知道的事实留空位，不编造），再用不调模型的规则给草稿做中文去 AI 味打分。用户说「学我的语气」「把这条爆款转成我的」「帮我出选题」「给这条草稿去 AI 味/打分」时使用。只出草稿，不替用户发帖、回复或联系任何人。
---

# x-voice-zh：中文 X 爆款转化

一句话：**学你的语气 → 找同赛道爆款 → 拆骨架 → 换成你自己的事 → 去 AI 味打分。**

脚本都在本文件旁边的 `scripts/` 里（纯 Python 标准库，Python 3.8+）。下文的 `SCRIPTS` 指这个目录。
先确认路径：本 SKILL.md 所在目录下的 `scripts/`。工作文件放在用户项目里的 `xvoice-work/`，别放进 skill 目录。

## 底线（任何模式都不能破）
1. 只出草稿。**不替用户发帖、回复、点赞、关注，也不联系任何人。**
2. **不编事实。** 经历、数字、成品、结果，只能来自用户的「真实事实清单」。清单里没有的，在草稿里留空位 `__`，让用户自己补。
3. 别人帖子里的数字只能写成「作者说」，不当成用户的数据。
4. 不抄原帖措辞，只留骨架（钩子类型、结构、形式）。
5. 正文不放链接，链接放评论区，写在「怎么发」里。
6. 用户自己定的禁用词（比如不写粉丝数）要遵守，用 `--ban-words` 或 `--ban-file` 交给打分器。
7. 不碰政治、割韭菜、拉人头、灰产。
8. 不保证涨粉或收益；没有数据支持的话不说。

## 模式 1：学语气
1. 让用户给 20–30 条自己的原创帖（越多越准），连浏览、回复、收藏。来源任选：
   - 复制粘贴到 `xvoice-work/my_posts.txt`，每条之间用单独一行 `---`；
   - X 官方数据导出里的 `tweets.js`；
   - csv / json / jsonl（字段名见 `references/voice-profile.md`）；
   - 有 X API 的，用 `fetch_x.py`（见模式 2）。
2. 导入并统计：
   ```bash
   python SCRIPTS/import_posts.py xvoice-work/my_posts.txt -o xvoice-work/posts.jsonl
   python SCRIPTS/voice_profile.py xvoice-work/posts.jsonl --json xvoice-work/profile.json --md xvoice-work/profile.md
   ```
3. 读 `profile.md`，**对照用户最好和最差的帖子原文**，补完底部「待 AI 补充」的 6 项，写成 5–8 条语气规则（开头、行数、表情、口头禅、收尾、哪类帖数据差）。每条规则要在用户真实帖子里见过，没见过的不写。
4. 帮用户建「真实事实清单」`xvoice-work/facts.md`（模板见 `references/facts-template.md`）：他在做什么、用什么工具、花了多少钱、有什么结果、踩过什么坑。**逐条问用户确认，别替他写。**
5. 样本不到 20 条就告诉用户画像只能参考。

## 模式 2：找爆款
1. 和用户列同赛道账号：中文为主，英文 1–2 个。
2. 拿帖子，二选一：
   - **没有 API（默认）**：让用户把大佬近 48 小时的帖子复制进文本文件，连互动数字；用 `import_posts.py` 导入。
   - **有 API（可选）**：用户自己设置环境变量 `X_BEARER_TOKEN`（别让用户把 token 发给你，也别回显），然后：
     ```bash
     python SCRIPTS/fetch_x.py --user 账号1 --user 账号2 --hours 48 --max 100 -o xvoice-work/bigshots.jsonl
     ```
     X API 的价格、权限和额度以官网为准，让用户自己核对。接口不能按点赞筛选，所以先拉再排。
3. 筛爆款（只留原创，排除回复、转发、推广；收藏或回复过阈值）：
   ```bash
   python SCRIPTS/rank_viral.py xvoice-work/bigshots.jsonl --min-bookmarks 100 --min-replies 100 --top 10 -o xvoice-work/viral.jsonl
   ```
   阈值按账号大小调；如果入选太少，降低阈值并告诉用户。
4. 剔除纯新闻转述、站队吵架、和用户赛道无关的帖子。

## 模式 3：拆骨架并转写（核心）
1. 拆骨架：
   ```bash
   python SCRIPTS/extract_skeleton.py xvoice-work/viral.jsonl --format md
   ```
   脚本的钩子类型是规则判断，**你要对照原帖复核**，并补上「为什么火」。钩子类型库见 `references/hooks.md`。
2. 生成任务单（可选，把画像、事实、爆款拼到一起）：
   ```bash
   python SCRIPTS/brief.py --profile xvoice-work/profile.md --facts xvoice-work/facts.md --viral xvoice-work/viral.jsonl --top 5 -o xvoice-work/brief.md
   ```
3. 对每条爆款：
   - 在事实清单里找落点。**用户确实有对应的经历才转；没有就标「不转」并说明原因，别硬凑。**
   - 保留钩子类型和结构，用用户的开头、口语、表情习惯，写 2–4 行（以画像为准）。
   - 用户不知道的事实留空位 `__`。
   - 标明：引用原帖还是单独发；配什么图/视频；哪些空要补；哪些事要先做完（比如先有成品）。
4. **每条草稿写完必须打分**，有硬禁项就重写：
   ```bash
   python SCRIPTS/score_draft.py xvoice-work/drafts.txt --profile xvoice-work/profile.json --facts xvoice-work/facts.md
   ```
   （多条草稿放一个文件，用单独一行 `---` 隔开。）空位没补完 = 不能发。`S07`（数字不在事实清单里）要么核实，要么换成空位。
5. 输出格式见 `references/output-format.md`：一次最多 5 条，首推排最前，每条含「原帖链接和真实数字 / 一句话为什么火 / 草稿 / 怎么发 / 要补的空」。

## 模式 4：优化草稿
用户给一段稿子：先 `score_draft.py` 打分，按命中的规则逐条改，输出「改前 / 改后 / 改了什么」，改后再打一次分。改的时候**不增加用户没说过的事实**。规则含义见 `references/de-ai-rules.md`（含「别误改」清单）。

## 模式 5：选题包
按「事 / 料 / 3 点 / 怎么发」给选题：事=是什么；料=真实链接和数字（没核到就写没核到）；3 点=和用户自己的事的关联；怎么发=配图、链接位置、发完做什么。

## 自检（交给用户前，一行写出来）
- 遮住最后一句，意思还在吗？在就删。
- 每个数字、经历能指出出处吗？指不出就删或留空位。
- 读出声：用户会这么说话吗？对照画像。
- `score_draft.py` 硬禁项 = 0 吗？
- 有没有替用户做了决定（发不发、什么时候发）？这些留给用户。
