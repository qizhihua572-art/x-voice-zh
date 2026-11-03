# x-voice-zh · X 爆款转化（中文版）

> **English in short:** `x-voice-zh` is an open-source (MIT) agent skill for Claude Code / Codex. It learns your Chinese writing voice from your own posts, picks viral posts from accounts in your niche, extracts their skeleton (hook type, structure, format), and rewrites them in your voice using **only facts you confirmed** — anything unknown is left as a blank `__`. It also ships a deterministic, no-LLM scorer for common Chinese "AI-tone" patterns. Pure Python stdlib. It never posts, replies or contacts anyone. See [README.en.md](README.en.md).

一句话：**学你的语气 → 找同赛道爆款 → 拆骨架 → 换成你自己的事 → 去 AI 味打分。**

做 X（推特）的人都知道，爆款帖有套路，但直接照抄既没意思，也不是你。这个 skill 只留爆款的**骨架**（钩子、结构、形式），内容全部换成**你自己的经历和数字**。你没说过的事，它留空位让你填，不替你编。

## 它做什么
| 步骤 | 谁来做 | 脚本 |
|---|---|---|
| 导入你的帖子（粘贴 / X 数据导出 / csv / json） | 脚本 | `import_posts.py` |
| 统计语气：长度、行数、表情、常见开头、数据最好 vs 最差 | 脚本 + AI 对照原帖润色 | `voice_profile.py` |
| 筛同赛道爆款（排除回复、转发、推广；收藏或回复过阈值） | 脚本 | `rank_viral.py`（可选 `fetch_x.py` 用你自己的 X API 拉） |
| 拆骨架：钩子类型、结构、形式、可收藏线索 | 脚本初判 + AI 复核 | `extract_skeleton.py` |
| 用你的事实改写成你的帖子，不知道的留空位 | AI（按 `SKILL.md`） | `brief.py` 生成任务单 |
| 中文去 AI 味打分（12 条硬禁 + 12 条软提示） | 脚本，不调模型，同一段文字永远同一个分 | `score_draft.py` |

## 它不做什么
- **不自动发帖、不自动回复、不自动关注、不联系任何人。** 只出草稿，发不发你定。
- **不编事实。** 经历、数字、成品只来自你确认的「事实清单」，别人的数字只能写「作者说」。
- 不保证涨粉，不保证爆。分数只说明「像不像模板腔」，不说明内容好不好。
- 不抄原帖措辞；不存你的 token；数据都在你本地。

## 安装

要求：Python 3.8+（只用标准库，不需要 `pip install`）。

**Claude Code**
```bash
git clone https://github.com/qizhihua572-art/x-voice-zh x-voice-zh && cd x-voice-zh
./install.sh claude            # 全局：~/.claude/skills/x-voice-zh
# 或只给当前项目用：在项目目录里运行  /path/to/x-voice-zh/install.sh claude-project
```
手动安装也行：把 `skills/x-voice-zh/` 整个目录复制到 `~/.claude/skills/`（或项目里的 `.claude/skills/`）。

**Codex**
```bash
./install.sh codex             # 复制到 ${CODEX_HOME:-~/.codex}/skills/x-voice-zh
```
Codex 的 skills 目录位置随版本可能不同，如果不在这里，请按你的版本文档把 `skills/x-voice-zh/` 放进对应目录（也可以 `./install.sh /你的/skills/目录`）。

装完新开一个会话，直接说：「用 x-voice-zh 学我的语气」。

## 5 分钟上手
1. **学语气**：把你最近 20–30 条原创帖粘到 `xvoice-work/my_posts.txt`（每条之间用单独一行 `---`，带上浏览/收藏更好，格式见 `references/voice-profile.md`），对 AI 说「用 x-voice-zh 学我的语气」。它会生成画像，并让你**逐条确认事实清单**。
2. **找爆款**：把同赛道大佬近 48 小时的帖子贴进来（或用 `fetch_x.py`），说「筛爆款」。
3. **转写**：说「把前 5 条转成我的版本」。你会拿到最多 5 条草稿，首推排最前，每条都有原帖数据、为什么火、草稿、怎么发、要补的空，以及打分。
4. **优化**：已有草稿，说「给这条去 AI 味」，它会逐条按命中的规则改，改前改后都打分。

没有 X API 也能全程使用。有 API 的话（价格、权限、额度以 X 官网为准，请自己核对）：
```bash
export X_BEARER_TOKEN=你自己的token       # 只读环境变量，脚本不保存也不打印
python skills/x-voice-zh/scripts/fetch_x.py --user 账号1 --user 账号2 --hours 48 --max 100 -o bigshots.jsonl
```

## 命令行单独用（不经过 AI 也行）
```bash
S=skills/x-voice-zh/scripts
python $S/voice_profile.py examples/sample_posts.jsonl --md profile.md --json profile.json
python $S/rank_viral.py examples/sample_bigshots.jsonl --top 5 -o viral.jsonl
python $S/extract_skeleton.py viral.jsonl --format md
python $S/score_draft.py draft.txt --profile profile.json --facts examples/sample_facts.md
```
`score_draft.py` 示例：
```
$ echo "说白了，这不是工具的问题，而是你没想清楚。你怎么看？" | python $S/score_draft.py -
得分 40/100 — 重写：有硬禁项
  [硬] H01 翻案腔（不是…而是…）：不是工具的问题，而是 → 只在前后两半都有信息时才留；否则直接说结论
  [硬] H03 硬凑互动的结尾提问：你怎么看 → 只留一个你真想知道答案的具体问题，或者不收尾
  [硬] H06 口头禅起手（说白了/先说结论/一句话总结）：说白了 → 直接说内容
```

## 去 AI 味规则
硬禁（命中就重写）：翻案腔「不是…而是」、金句/升维收尾、硬凑互动的结尾提问、标题党钩子、三连排比、口头禅起手、提示语冒号、铺垫客服腔、emoji 当项目符号、感叹号连发、虚构人物故事、你自己的禁用词。
软提示（只提示）：路标词、顿号过密、概括词盖住数字、破折号、太长、链接在正文、数字不在事实清单里等。
**别误改清单**：问句本身、句长参差、「首先/其次」、单个漂亮词、emoji 本身，这些人写的文章里一样常见，不要当成 AI 味去改。
完整说明见 [`references/de-ai-rules.md`](skills/x-voice-zh/references/de-ai-rules.md)，评分口径见 [`score-rubric.md`](skills/x-voice-zh/references/score-rubric.md)。

## 目录
```
skills/x-voice-zh/
  SKILL.md                  # 5 个模式：学语气 / 找爆款 / 拆骨架并转写 / 优化草稿 / 选题包
  references/               # 钩子类型库、画像模板、事实清单模板、去 AI 味规则、评分口径、输出格式
  scripts/                  # 纯标准库 Python
examples/                   # 全部是虚构示例数据（已标注 example）
tests/                      # python -m unittest discover -s tests
```
`examples/` 里的账号、帖子和数字**都是虚构的**，只用于演示和测试。

## 常见问题
- **会不会被封号？** 这个 skill 不做任何自动化操作，只出文字。但 X 的规则会变，发帖和互动请自己把握，我们不保证任何结果。
- **我的数据去哪了？** 都在你本地的文件里。skill 本身不上传任何东西；你用的 AI 助手会读到你让它读的文件，按它自己的隐私政策处理。
- **为什么不直接让 AI 全自动写？** 因为帖子里最值钱的是你真实的经历。AI 不知道的事就该留空。

## 测试
```bash
python -m unittest discover -s tests -v
```

## 路线图
- 支持更多输入格式；多账号对比
- 钩子类型库扩充（欢迎提 PR，附真实场景，不要附真实用户数据）
- 更多去 AI 味规则（要求：每条规则带正反例测试）

## 贡献 / 许可
欢迎 issue 和 PR。MIT 许可，见 [LICENSE](LICENSE)；参考与致谢见 [NOTICE.md](NOTICE.md)。
