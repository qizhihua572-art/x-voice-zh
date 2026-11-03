# x-voice-zh — viral-post adaptation for Chinese X (Twitter) creators

An open-source (MIT) agent skill for **Claude Code** and **Codex**. Pure Python standard library (3.8+).

**What it does**
1. Learns your voice from your own posts (length, lines, emoji, openers, best vs. worst posts) — `voice_profile.py`.
2. Picks viral posts from accounts in your niche from a file you paste/export, or optionally via **your own** X API token — `rank_viral.py`, `fetch_x.py`.
3. Extracts each post's skeleton (hook type, structure, format, save-worthy content) — `extract_skeleton.py`.
4. The agent rewrites each one in your voice using **only the facts you confirmed**. Anything unknown stays a blank `__`. — `SKILL.md`, `brief.py`.
5. Scores drafts with a **deterministic, no-LLM** rule set for common Chinese "AI-tone" patterns (12 hard rules, 12 soft hints, plus a "don't over-fix" list) — `score_draft.py`.

**What it never does:** post, reply, follow, DM, or contact anyone; invent facts; guarantee growth. It only produces drafts. Your token is read from `X_BEARER_TOKEN` and never stored or printed.

**Install**
```bash
git clone <repo-url> x-voice-zh && cd x-voice-zh
./install.sh claude     # ~/.claude/skills/x-voice-zh
./install.sh codex      # ${CODEX_HOME:-~/.codex}/skills/x-voice-zh  (check your Codex version's skills path)
```
Then start a new session and say: "use x-voice-zh to learn my voice". Run tests with `python -m unittest discover -s tests -v`.

The tool and its rules target **Chinese** text. All accounts, posts and numbers under `examples/` are fictional. The detailed documentation is in Chinese: [README.md](README.md).

License: MIT. See [NOTICE.md](NOTICE.md) for references and credits.
