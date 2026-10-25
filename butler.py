#!/usr/bin/env python3
"""
Night Butler (บัตเลอร์กะดึก) — Hacktoberfest 2026 DEV Challenge Week 3: Slow and Steady.

กะดึก: อ่านความจำของเอเจนต์ (local open-weight embeddings ผ่าน OpenClaw memory)
แล้วสรุปเป็นบรีฟเช้าภาษาไทย — ตื่นมาไม่ต้องไล่อ่านแชทยาว

No secrets in this file: API key / bot token / chat id come from env or local
config files at runtime. Safe to publish.
"""
import json
import os
import re
import sqlite3
import time
import urllib.request
from datetime import datetime, timedelta, timezone

# ---------- config (env-overridable, no secrets here) ----------
GW_URL = os.environ.get("NIGHT_BUTLER_GW_URL", "http://127.0.0.1:28080")
GW_MODEL = os.environ.get("NIGHT_BUTLER_MODEL", "sydear-photon")
API_KEY_FILE = os.environ.get("NIGHT_BUTLER_API_KEY_FILE",
                              "/opt/sydear-router-gateway/.keys/night-butler.key")
OPENCLAW_JSON = os.environ.get("NIGHT_BUTLER_OPENCLAW_JSON",
                               "/root/.openclaw/openclaw.json")
AGENT_DB = os.environ.get("NIGHT_BUTLER_AGENT_DB",
                          "/root/.openclaw/agents/main/agent/openclaw-agent.sqlite")
BRIEF_DIR = os.environ.get("NIGHT_BUTLER_BRIEF_DIR", "/opt/night-butler/briefs")
TZ = timezone(timedelta(hours=7))  # Asia/Bangkok


def read_key():
    with open(API_KEY_FILE) as f:
        return f.read().strip()


def telegram_cfg():
    """Read bot token + owner chat id from local OpenClaw config (runtime only)."""
    try:
        d = json.load(open(OPENCLAW_JSON))
    except Exception:
        return None, None
    tg = (d.get("channels") or {}).get("telegram") or {}
    if not tg.get("enabled") or not tg.get("botToken"):
        return None, None
    token = tg["botToken"]
    chat_id = os.environ.get("NIGHT_BUTLER_CHAT_ID")
    if not chat_id:
        allow = ((d.get("commands") or {}).get("ownerAllowFrom") or [])
        m = re.search(r"telegram:(\d+)", " ".join(allow))
        chat_id = m.group(1) if m else None
    return token, chat_id


def recent_memory(hours=24, limit=60):
    """Chunks the agent learned/updated in the last `hours` (local bge-m3 index)."""
    con = sqlite3.connect(f"file:{AGENT_DB}?mode=ro", uri=True, timeout=10)
    since = int(time.time()) - hours * 3600
    rows = con.execute(
        "SELECT path, text, updated_at FROM memory_index_chunks "
        "WHERE updated_at > ? ORDER BY updated_at DESC LIMIT ?",
        (since, limit)).fetchall()
    con.close()
    return rows


def ask_gateway(prompt, api_key):
    body = json.dumps({
        "model": GW_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2500,
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        GW_URL + "/v1/chat/completions", data=body,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode())
    return d["choices"][0]["message"]["content"]


BRIEF_PROMPT = """นายคือ "บัตเลอร์กะดึก" ผู้ช่วยที่ทำงานตอนเจ้านายนอน
จากบันทึกความจำของเอเจนต์ในช่วง 24 ชั่วโมงที่ผ่านมา (รูปแบบ: [ไฟล์] ข้อความ)
เขียน "บรีฟเช้า" เป็นภาษาไทย สำเนียงกันเองแบบเพื่อน (ใช้ มึง/กู ได้) สั้น กระชับ
โครง (ใช้อิโมจินำหัวข้อ):
🌙 เมื่อคืนมีอะไรเกิดขึ้น — สรุป 3-6 ข้อ เฉพาะเรื่องสำคัญ
📌 อะไรค้างอยู่ — งาน/การตัดสินใจที่ยังไม่จบ
☀️ วันนี้แนะนำให้ทำอะไร — 2-4 ข้อ เรียงตามความสำคัญ
🗑️ น่าลืมได้ — เสนอเฉยๆ ว่าอะไรในความจำดูเป็นขยะ ห้ามลบเอง แค่เสนอ

กฎ: อย่าแต่งเรื่องที่ไม่มีในบันทึก ถ้าบันทึกน้อยก็บอกตรงๆ ว่าน้อย อย่าเดา
ความยาวไม่เกิน 1 หน้าจอมือถือ

บันทึก:
{chunks}
"""


def send_telegram(token, chat_id, text):
    body = json.dumps({"chat_id": chat_id,
                       "text": text[:4000]}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get("ok", False)


def main():
    now = datetime.now(TZ)
    os.makedirs(BRIEF_DIR, exist_ok=True)
    rows = recent_memory()
    if rows:
        chunks = "\n".join(
            f"[{p}] {t[:600]}" for p, t, _ in rows)
    else:
        chunks = "(ไม่มีความจำใหม่ใน 24 ชม. — เจ้านายน่าจะพักผ่อนจริง)"
    prompt = BRIEF_PROMPT.format(chunks=chunks[:12000])
    api_key = read_key()
    try:
        brief = ask_gateway(prompt, api_key)
    except Exception as e:
        # graceful degradation: no live tokens tonight — still leave a trace
        brief = ("⚠️ คืนนี้เรียกสมองผ่าน gateway ไม่ติด "
                 f"({str(e)[:100]}) เลยสรุปให้ไม่ได้\n\n"
                 f"แต่มีความจำใหม่ {len(rows)} ชิ้นใน 24 ชม. "
                 "ไว้โทเค็นกลับมาแล้วจะสรุปให้")

    header = f"# ☀️ บรีฟเช้า {now:%d %b %Y}\n\n_บัตเลอร์กะดึกสรุปให้ตอน {now:%H:%M} — จากความจำ {len(rows)} ชิ้นใน 24 ชม._\n\n"
    full = header + brief
    path = os.path.join(BRIEF_DIR, f"brief-{now:%Y-%m-%d}.md")
    with open(path, "w") as f:
        f.write(full)
    print("wrote", path, f"({len(rows)} chunks)")

    token, chat_id = telegram_cfg()
    if token and chat_id:
        try:
            ok = send_telegram(token, chat_id,
                              f"☀️ บรีฟเช้า {now:%d %b}\n\n{brief}")
            print("telegram:", "sent" if ok else "failed")
        except Exception as e:
            print("telegram error:", str(e)[:120])
    else:
        print("telegram: not configured, skipped")


if __name__ == "__main__":
    main()
