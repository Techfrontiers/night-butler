# Night Butler (บัตเลอร์กะดึก) 🦥🌙

> You sleep. Your second brain works the night shift.

**Hacktoberfest 2026 — DEV Challenge Week 3: "Slow and Steady"** submission.

A tiny nightly agent that reads what your AI assistant learned yesterday and
writes you a Thai morning brief — so you never have to scroll through chat
history again.

## The lazy payoff

- **~15 minutes saved every morning.** Instead of re-reading yesterday's
  3,500+ memory chunks and long chat threads, you wake up to one phone-sized
  screen: what happened, what's pending, what to do today.
- **Zero cloud AI bills.** Memory search runs on local open-weight embeddings
  ([BGE-M2 multilingual](https://huggingface.co/BAAI/bge-m3)) via Ollama on a
  $1/month VPS. The whole thing costs less than a cup of coffee per year.
- **Zero new accounts.** It reuses the Telegram bot you already have and the
  API gateway you already run.

## How it works

```
23:59 ── cron fires ──▶ butler.py
                            │
                            ├─ 1. read last 24h of agent memory
                            │     (SQLite FTS + bge-m3 vector index, local)
                            ├─ 2. ask LLM for a Thai morning brief
                            │     (via self-hosted OpenAI-compatible gateway)
                            ├─ 3. save brief-YYYY-MM-DD.md
                            └─ 4. send to Telegram
06:30 ── ☀️ brief on your phone ──▶ you, still half asleep
```

If the LLM is unreachable (no tokens tonight), it degrades gracefully: it
still writes a brief noting the outage and the raw memory count instead of
crashing.

## Why open innovation matters for this build

This project only makes sense *because* the AI pieces are open:

1. **Your memory is personal data.** A cloud embeddings API would see
   everything your assistant ever learned about you. Local bge-m3 means none
   of it ever leaves your $1 box — there is no trust decision to make.
2. **Free forever.** A nightly summarizer is exactly the kind of tiny
   automation a per-token API would make silly to pay for. Open weights make
   the lazy option the free option: set it up once, nap forever.
3. **Swappable, not load-bearing.** Don't like the brief style? Change the
   prompt. Want a different embedding model? One line. No vendor to
   renegotiate with.

## Setup

```bash
# 1. put files on your box
sudo mkdir -p /opt/night-butler/briefs
sudo cp butler.py /opt/night-butler/

# 2. configure via env (no secrets in the repo)
export NIGHT_BUTLER_API_KEY_FILE=/path/to/your-gateway-key
export NIGHT_BUTLER_OPENCLAW_JSON=/root/.openclaw/openclaw.json   # telegram bot token lives here
export NIGHT_BUTLER_AGENT_DB=/root/.openclaw/agents/main/agent/openclaw-agent.sqlite
# optional: NIGHT_BUTLER_GW_URL, NIGHT_BUTLER_MODEL, NIGHT_BUTLER_CHAT_ID, NIGHT_BUTLER_BRIEF_DIR

# 3. nightly cron (06:30 Asia/Bangkok)
(crontab -l; echo "30 6 * * * /usr/bin/python3 /opt/night-butler/butler.py >> /var/log/night-butler.log 2>&1") | crontab -
```

Needs: Python 3 (stdlib only — `sqlite3`, `urllib`), an OpenAI-compatible
`POST /v1/chat/completions` endpoint, and an OpenClaw-style agent DB
(optional — without it, the brief just says memory is quiet).

## What the brief looks like

```
☀️ บรีฟเช้า 21 Oct

🌙 เมื่อคืนมีอะไรเกิดขึ้น
- ...
📌 อะไรค้างอยู่
- ...
☀️ วันนี้แนะนำให้ทำอะไร
- ...
🗑️ น่าลืมได้
- ... (suggestions only — it never deletes anything by itself)
```

## License

MIT — steal it, your mornings will thank you.
