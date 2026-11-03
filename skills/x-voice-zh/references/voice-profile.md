# 语气画像模板

## 输入格式
`import_posts.py` 能读：
- `.txt` / `.md`：每条帖子之间用单独一行 `---`
- `.jsonl` / `.json`：每条一个对象
- X 数据导出的 `tweets.js`（`window.YTD.tweets.part0 = [...]`）
- `.csv`：带表头

字段名（任选一个）：
| 含义 | 可识别的字段名 |
|---|---|
| 正文 | text / full_text / content |
| 浏览 | views / view_count / impressions / impression_count |
| 点赞 | likes / like_count / favorite_count |
| 回复 | replies / reply_count |
| 收藏 | bookmarks / bookmark_count |
| 转发 | reposts / retweets / retweet_count |
| 时间 | created_at / date |
| 链接 / 作者 / id | url / author(username) / id |

回复和转发默认不进画像（`is_reply`、`is_retweet`，或以 `@` / `RT @` 开头）。

## 画像文件结构
```
# <名字> 语气画像
样本：N 条原创帖，日期范围
## 语气规则（5–8 条，每条都要在真实帖子里见过）
1. 开头：
2. 长度和行数：
3. 表情：
4. 口头禅和常用词：
5. 收尾：
6. 数据差的写法（以后别发）：
## 数据最好的 3 条
（链接 + 数据 + 为什么好）
## 数据最差的 3 条
（链接 + 数据 + 为什么差）
```
统计部分由 `voice_profile.py` 给，规则部分由 AI 对照原帖写。
