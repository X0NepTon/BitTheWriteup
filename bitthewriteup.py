#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bitthewriteup — bug bounty writeup digest for discord
author : 0xdragon  |  version: 2.1.0
"""

import os, re, json, time, hashlib, logging, argparse
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass

# ─── Banner ───────────────────────────────────────────────────────────────────

RED   = "\033[38;5;196m"   # bright red
DRED  = "\033[38;5;124m"   # dark red
GOLD  = "\033[38;5;220m"   # gold
WHITE = "\033[38;5;255m"   # bright white
GRAY  = "\033[38;5;240m"   # dark gray
RESET = "\033[0m"

BANNER = f"""
{RED}██████╗ ██╗████████╗{RESET}    {DRED}████████╗██╗  ██╗███████╗{RESET}    {WHITE}██╗    ██╗██████╗ ██╗████████╗███████╗██╗   ██╗██████╗{RESET}
{RED}██╔══██╗██║╚══██╔══╝{RESET}    {DRED}╚══██╔══╝██║  ██║██╔════╝{RESET}    {WHITE}██║    ██║██╔══██╗██║╚══██╔══╝██╔════╝██║   ██║██╔══██╗{RESET}
{DRED}██████╔╝██║   ██║   {RESET}       {RED}██║   ███████║█████╗  {RESET}    {RED}██║ █╗ ██║██████╔╝██║   ██║   █████╗  ██║   ██║██████╔╝{RESET}
{DRED}██╔══██╗██║   ██║   {RESET}       {RED}██║   ██╔══██║██╔══╝  {RESET}    {DRED}██║███╗██║██╔══██╗██║   ██║   ██╔══╝  ██║   ██║██╔═══╝{RESET}
{WHITE}██████╔╝██║   ██║   {RESET}       {WHITE}██║   ██║  ██║███████╗{RESET}    {WHITE}╚███╔███╔╝██║  ██║██║   ██║   ███████╗╚██████╔╝██║{RESET}
{GRAY} ╚═════╝ ╚═╝   ╚═╝          ╚═╝   ╚═╝  ╚═╝╚══════╝     ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝ ╚═════╝ ╚═╝{RESET}
{GRAY}  ───────────────────────────────────────────────────────────────────────────────────────{RESET}
{GOLD}  [*]{RESET} {WHITE}bug bounty writeup digest → discord{RESET}                        {RED}author: 0xdragon{RESET}
{GOLD}  [*]{RESET} {GRAY}portswigger · intigriti · medium · dev.to · github medium-writeups  {RESET}
{GRAY}  ───────────────────────────────────────────────────────────────────────────────────────{RESET}
"""

# ─── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
SENT_LOG    = BASE_DIR / "sent.log"
RUN_LOG     = BASE_DIR / "run.log"
QUEUE_FILE  = BASE_DIR / "queue.json"

# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"{RED}[!]{RESET} config.json not found — copy config.example.json")
        raise SystemExit(1)
    cfg = json.loads(CONFIG_FILE.read_text("utf-8"))
    wh  = cfg.get("discord_webhook", "")
    if not wh or "YOUR_WEBHOOK" in wh:
        print(f"{RED}[!]{RESET} set discord_webhook in config.json")
        raise SystemExit(1)
    return cfg

CFG           = load_config()
WEBHOOK_URL   = CFG["discord_webhook"]
LOOP          = CFG.get("schedule", {}).get("loop", True)
INTERVAL_MIN  = CFG.get("schedule", {}).get("interval_minutes", 60)
ITEMS_PER_RUN = CFG.get("schedule", {}).get("items_per_run", 1)
MIN_SCORE     = CFG.get("limits",   {}).get("min_score", 3)
MAX_QUEUE     = CFG.get("limits",   {}).get("max_queue", 200)
REQUIRE_ANY   = [k.lower() for k in CFG.get("filters", {}).get("require_any", [])]
EXCLUDE_ANY   = [k.lower() for k in CFG.get("filters", {}).get("exclude_any", [])]
HTTP_TIMEOUT  = 25

def _is_enabled(val) -> bool:
    """Handles: false / "false" / "False" / 0 — all correctly disabled."""
    if isinstance(val, bool): return val
    if isinstance(val, str):  return val.strip().lower() not in ("false","0","no","off")
    return bool(val)

_SRC_CFG = {s["id"]: s for s in CFG.get("sources", [])}

# ─── Discord embed colors ─────────────────────────────────────────────────────

COLORS = {
    "portswigger": 0xFF4444,   # red
    "intigriti":   0xCC0000,   # dark red
    "yeswehack":   0xFF8C00,   # dark orange/gold
    "medium_wu":   0xFFD700,   # gold
    "medium_bb":   0xFFA500,   # orange
    "devto":       0x8B0000,   # very dark red
    "github_wu":   0xFF6347,   # tomato red
    "default":     0xB22222,   # firebrick
}

# ─── Sources ──────────────────────────────────────────────────────────────────

_ALL_SOURCES = [
    {
        "name":   "PortSwigger Research",
        "id":     "portswigger",
        "type":   "rss",
        "weight": 5,
        "url":    "https://portswigger.net/research/rss",
    },
    {
        "name":   "Intigriti Blog",
        "id":     "intigriti",
        "type":   "rss",
        "weight": 4,
        "url":    "https://blog.intigriti.com/feed",
    },
    {
        "name":   "Medium — Bug Bounty Writeup",
        "id":     "medium_wu",
        "type":   "rss",
        "weight": 4,
        "url":    "https://medium.com/feed/tag/bug-bounty-writeup",
    },
    {
        "name":   "Medium — Bug Bounty",
        "id":     "medium_bb",
        "type":   "rss",
        "weight": 3,
        "url":    "https://medium.com/feed/tag/bug-bounty",
    },
    {
        "name":   "dev.to — Bug Bounty",
        "id":     "devto",
        "type":   "rss",
        "weight": 2,
        "url":    "https://dev.to/feed/tag/bugbounty",
    },
    {
        "name":   "GitHub medium-writeups",
        "id":     "github_wu",
        "type":   "rss",
        "weight": 3,
        "url":    "https://github.com/rix4uni/medium-writeups/commits/main.atom",
    },
    # ── Add custom sources below ──────────────────────────────────────────
    # {
    #     "name":   "NahamSec Blog",
    #     "id":     "nahamsec",
    #     "type":   "rss",
    #     "weight": 3,
    #     "url":    "https://nahamsec.com/feed",
    # },
]

def get_sources() -> list:
    out = []
    for s in _ALL_SOURCES:
        ov = _SRC_CFG.get(s["id"], {})
        out.append({
            **s,
            "enabled": _is_enabled(ov.get("enabled", True)),
            "weight":  ov.get("weight", s["weight"]),
        })
    return out

SOURCES = get_sources()

# Trusted sources — always pass keyword filter
WHITELIST_EXEMPT = {"portswigger", "intigriti", "yeswehack", "github_wu"}

# ─── Data class ───────────────────────────────────────────────────────────────

@dataclass
class Item:
    title:       str
    url:         str
    summary:     str
    source_id:   str
    source_name: str
    published:   str
    score:       int = 0
    uid:         str = ""

    def __post_init__(self):
        if not self.uid:
            self.uid = hashlib.sha256(
                f"{self.source_id}:{self.url}".encode()
            ).hexdigest()[:16]

    def to_dict(self): return self.__dict__

    @classmethod
    def from_dict(cls, d):
        keys = {"title","url","summary","source_id","source_name",
                "published","score","uid"}
        return cls(**{k: v for k, v in d.items() if k in keys})

# ─── Logging ──────────────────────────────────────────────────────────────────

def setup_logging():
    handlers = [logging.StreamHandler()]
    try: handlers.append(logging.FileHandler(RUN_LOG, encoding="utf-8"))
    except: pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )

log = logging.getLogger(__name__)

# ─── Sent log ─────────────────────────────────────────────────────────────────

def load_sent() -> set:
    if not SENT_LOG.exists(): return set()
    return set(l.strip() for l in SENT_LOG.read_text("utf-8").splitlines() if l.strip())

def mark_sent(uid: str):
    with SENT_LOG.open("a", encoding="utf-8") as f: f.write(uid + "\n")

def prune_sent(keep: int = 8000):
    if not SENT_LOG.exists(): return
    lines = SENT_LOG.read_text("utf-8").splitlines()
    if len(lines) > keep:
        SENT_LOG.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")

# ─── Queue ────────────────────────────────────────────────────────────────────

def load_queue() -> list:
    if not QUEUE_FILE.exists(): return []
    try: return [Item.from_dict(d) for d in json.loads(QUEUE_FILE.read_text("utf-8"))]
    except: return []

def save_queue(items: list):
    top = sorted(items, key=lambda x: -x.score)[:MAX_QUEUE]
    QUEUE_FILE.write_text(
        json.dumps([i.to_dict() for i in top], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def queue_stats() -> str:
    q = load_queue()
    if not q: return "empty"
    by_src = defaultdict(int)
    for i in q: by_src[i.source_id] += 1
    parts = " | ".join(f"{k}:{v}" for k, v in sorted(by_src.items()))
    return f"{len(q)} items  [{parts}]"

# ─── HTTP ─────────────────────────────────────────────────────────────────────

RSS_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Accept":          "application/rss+xml,application/atom+xml,text/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}

def fetch_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers=RSS_HEADERS)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return r.read()

# ─── XML parser ───────────────────────────────────────────────────────────────

ATOM = "http://www.w3.org/2005/Atom"

def _strip(text: str) -> str:
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text or "", flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    for e, c in [("&nbsp;"," "),("&amp;","&"),("&lt;","<"),
                 ("&gt;",">"),("&#39;","'"),("&quot;",'"')]:
        text = text.replace(e, c)
    return re.sub(r"\s+", " ", text).strip()

def _find(el, *tags):
    for t in tags:
        f = el.find(t)
        if f is not None: return f
    return None

def _txt(el) -> str:
    return (el.text or "").strip() if el is not None else ""

def _try_parse(raw: bytes):
    """Three attempts to parse potentially malformed XML."""
    for fn in [
        lambda: ET.fromstring(raw),
        lambda: ET.fromstring(
            re.sub(r'encoding=["\'][^"\']+["\']', 'encoding="utf-8"',
                   raw.decode("latin-1", errors="replace")
            ).encode("utf-8", errors="replace")),
        lambda: ET.fromstring(
            re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '',
                   raw.decode("utf-8", errors="replace")
            ).encode("utf-8")),
    ]:
        try: return fn()
        except ET.ParseError: continue
    raise ET.ParseError("all parse attempts failed")

MEDIUM_URL_RE = re.compile(
    r'https?://(?:medium\.com|infosecwriteups\.com|systemweakness\.com|'
    r'betterprogramming\.pub|readmedium\.com|freedium\.cfd|hackernoon\.com)[^\s"<>]{10,300}'
)

def parse_rss(raw: bytes, source: dict) -> list:
    items = []
    try: root = _try_parse(raw)
    except ET.ParseError as e:
        log.warning(f"[{source['name']}] xml error: {e}"); return items

    bare = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if bare == "rss":
        ch = root.find("channel")
        entries = (ch if ch is not None else root).findall("item")
    else:
        entries = root.findall(f"{{{ATOM}}}entry") or root.findall("entry")

    for entry in entries[:60]:
        title_el = _find(entry, "title", f"{{{ATOM}}}title")
        title    = _strip(_txt(title_el))
        if not title: continue

        link_el = _find(entry, "link", f"{{{ATOM}}}link")
        url = ""
        if link_el is not None:
            url = link_el.get("href") or _strip(_txt(link_el))

        # github_wu: commit Atom feed — extract Medium URLs from commit body
        if source["id"] == "github_wu":
            content_el  = _find(entry, "content", f"{{{ATOM}}}content")
            content_txt = _strip(_txt(content_el)) if content_el is not None else ""
            found = MEDIUM_URL_RE.findall(content_txt)
            if found:
                for wu_url in found[:3]:
                    items.append(Item(
                        title=title, url=wu_url,
                        summary="bug bounty writeup",
                        source_id=source["id"], source_name=source["name"],
                        published="",
                    ))
                continue
            if not url: continue
            items.append(Item(title=title, url=url, summary="bug bounty writeup",
                              source_id=source["id"], source_name=source["name"],
                              published=""))
            continue

        if not url: continue
        summ_el   = _find(entry, "description","summary","content",
                          f"{{{ATOM}}}summary", f"{{{ATOM}}}content")
        summary   = _strip(_txt(summ_el))[:600]
        date_el   = _find(entry, "pubDate","published","updated",
                          f"{{{ATOM}}}published", f"{{{ATOM}}}updated")
        published = _txt(date_el)[:25]
        items.append(Item(
            title=title, url=url, summary=summary,
            source_id=source["id"], source_name=source["name"],
            published=published,
        ))
    return items

# ─── Filter ───────────────────────────────────────────────────────────────────

def is_bug_bounty(item: Item) -> bool:
    c = (item.title + " " + item.summary).lower()
    if any(kw in c for kw in EXCLUDE_ANY): return False     # hard exclude
    if item.source_id in WHITELIST_EXEMPT: return True      # trusted source
    if REQUIRE_ANY: return any(kw in c for kw in REQUIRE_ANY)
    return True

# ─── Scoring ──────────────────────────────────────────────────────────────────

VULN_SCORES = {
    "rce": 10, "remote code execution": 10,
    "account takeover": 9, "ato": 9,
    "ssrf": 8, "zero day": 8, "0day": 8,
    "sql injection": 7, "sqli": 7,
    "authentication bypass": 7, "auth bypass": 7, "privilege escalation": 7,
    "subdomain takeover": 6, "xss stored": 6, "blind xss": 6,
    "prototype pollution": 6,
    "idor": 5, "cve-": 5,
    "csrf": 4, "open redirect": 3,
}
ENGAGEMENT = {
    "$": 2, "bounty": 2, "critical": 3, "high": 2,
    "chain": 3, "poc": 3, "bypass": 2,
    "writeup": 1, "write-up": 1, "disclosed": 1,
}
SOURCE_TRUST = {
    "portswigger": 1.5,
    "intigriti":   1.3,
    "yeswehack":   1.2,
    "medium_wu":   1.1,
    "medium_bb":   1.0,
    "github_wu":   1.0,
    "devto":       0.9,
}

def compute_score(item: Item) -> int:
    c = (item.title + " " + item.summary).lower()
    s = sum(pts for kw, pts in VULN_SCORES.items() if kw in c)
    s += sum(pts for kw, pts in ENGAGEMENT.items() if kw in c)
    if item.source_id == "github_wu" and s == 0: s = 5
    return max(int(s * SOURCE_TRUST.get(item.source_id, 1.0)), 1)

# ─── Fetch ────────────────────────────────────────────────────────────────────

REFRESH_EVERY = 10
_run_n = {"n": 0}

def fetch_all() -> list:
    all_items = []
    active = [s for s in SOURCES if s["enabled"]]
    log.info(f"  active sources: {len(active)}/{len(SOURCES)}")
    for src in active:
        log.info(f"  {GOLD}>{RESET} {src['name']}")
        try:
            raw   = fetch_url(src["url"])
            items = parse_rss(raw, src)
            rel   = [i for i in items if is_bug_bounty(i)]
            for i in rel: i.score = compute_score(i)
            pool  = src.get("weight", 2) * 8
            top   = sorted(rel, key=lambda x: -x.score)[:pool]
            all_items.extend(top)
            log.info(f"    {GOLD}✓{RESET} {len(rel)}/{len(items)} passed | top {len(top)} kept")
        except urllib.error.URLError as e:
            log.warning(f"    {RED}✗{RESET} network: {e}")
        except Exception as e:
            log.warning(f"    {RED}✗{RESET} error: {e}")
    return all_items

def dedupe(items: list) -> list:
    seen, out = set(), []
    for i in items:
        if i.uid not in seen: seen.add(i.uid); out.append(i)
    return out

def refresh_queue(sent_ids: set) -> list:
    log.info(f"{GOLD}── refreshing queue ──────────────────────────────────{RESET}")
    fresh    = fetch_all()
    existing = load_queue()
    combined = dedupe(existing + fresh)
    unsent   = [i for i in combined if i.uid not in sent_ids]
    quality  = [i for i in unsent if i.score >= MIN_SCORE]
    dropped  = len(unsent) - len(quality)
    if dropped: log.info(f"  dropped {dropped} low-quality (score < {MIN_SCORE})")
    save_queue(quality)
    log.info(f"  queue → {queue_stats()}")
    return quality

# ─── Diversity pick ───────────────────────────────────────────────────────────

def pick_diverse(queue: list, n: int) -> list:
    """
    n=1  → best score overall
    n=5  → one from each source
    n=10 → proportional, capped per source at ceil(n/sources)
    """
    if not queue or n <= 0: return queue[:n] if queue else []
    by_src = defaultdict(list)
    for item in sorted(queue, key=lambda x: -x.score):
        by_src[item.source_id].append(item)
    cap = max(1, -(-n // len(by_src)))
    candidates = []
    for k in sorted(by_src.keys()):
        take = min(cap, len(by_src[k]))
        candidates.extend(by_src[k][:take])
        by_src[k] = by_src[k][take:]
    candidates.sort(key=lambda x: -x.score)
    if len(candidates) > n:
        candidates = candidates[:n]
    elif len(candidates) < n:
        overflow = sorted(
            [i for lst in by_src.values() for i in lst],
            key=lambda x: -x.score,
        )
        candidates.extend(overflow[:n - len(candidates)])
    return sorted(candidates, key=lambda x: -x.score)

# ─── Discord ──────────────────────────────────────────────────────────────────

def _trunc(s: str, n: int) -> str:
    return s[:n] + "…" if len(s) > n else s

def discord_post(payload: dict) -> int:
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(WEBHOOK_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent",   "DiscordBot (bitthewriteup, 2.1.0)")
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return r.status
    except urllib.error.HTTPError as e:
        try: body = e.read().decode()[:200]
        except: body = ""
        log.warning(f"discord http {e.code}: {body}"); return e.code
    except Exception as e:
        log.warning(f"discord error: {e}"); return 0

def send_item(item: Item) -> bool:
    color = COLORS.get(item.source_id, COLORS["default"])
    desc  = _trunc(item.summary, 350) if item.summary else "_no preview_"
    stars = "🔴" * min(item.score // 4, 5) or "🟡"
    payload = {"embeds": [{
        "title":       _trunc(item.title, 256),
        "url":         item.url,
        "description": desc,
        "color":       color,
        "fields": [
            {"name": "quality", "value": f"{stars} `{item.score}pts`", "inline": True},
            {"name": "source",  "value": item.source_name,              "inline": True},
        ],
        "footer":    {"text": f"bitthewriteup by 0xdragon  •  {item.published[:16] or '?'}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }]}
    status = discord_post(payload)
    if status in (200, 204): return True
    if status == 429:
        log.warning("rate limited — waiting 6s..."); time.sleep(6)
        return discord_post(payload) in (200, 204)
    if status in (401, 403):
        log.error(f"webhook rejected (http {status}) — update discord_webhook in config.json")
        raise SystemExit(1)
    return False

def send_daily_summary(top_items: list, total_sent: int):
    """End-of-day summary embed: best 5 writeups sent today."""
    if not top_items: return
    lines = "\n".join(
        f"**{i}.** [{_trunc(item.title, 65)}]({item.url})  `{item.score}pts`"
        for i, item in enumerate(top_items[:5], 1)
    )
    payload = {"embeds": [{
        "title":       "📋 Daily Best — bitthewriteup",
        "description": lines,
        "color":       0xFFD700,  # gold
        "fields": [
            {"name": "Sent today", "value": str(total_sent), "inline": True},
            {"name": "UTC",
             "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
             "inline": True},
        ],
        "footer": {"text": "bitthewriteup by 0xdragon"},
    }]}
    discord_post(payload)

# ─── Core run ─────────────────────────────────────────────────────────────────

_today_sent: list = []

def run_once(dry_run: bool = False, force_refresh: bool = False):
    _run_n["n"] += 1
    n = _run_n["n"]
    log.info(f"{RED}═{RESET}" * 60)
    log.info(
        f"{RED}[bitthewriteup]{RESET}  run #{n}  "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    sent_ids = load_sent()
    queue    = [i for i in load_queue() if i.uid not in sent_ids]
    do_refresh = (
        force_refresh or n == 1
        or n % REFRESH_EVERY == 0
        or len(queue) < ITEMS_PER_RUN * 3
    )
    if do_refresh:
        queue = refresh_queue(sent_ids)
    else:
        log.info(f"  queue: {queue_stats()}")
    if not queue:
        log.info("  queue empty — nothing to send."); return
    to_send = pick_diverse(queue, ITEMS_PER_RUN)
    if dry_run:
        log.info(f"  {GOLD}[dry-run]{RESET} would send {len(to_send)}:")
        for i in to_send:
            log.info(f"    score={i.score:3d} [{i.source_id:12}] {i.title[:65]}")
        return
    sent_uids = set()
    for item in to_send:
        log.info(f"  {GOLD}→{RESET} [{item.source_id}] score={item.score}  {item.title[:60]}")
        try: ok = send_item(item)
        except SystemExit: raise
        except Exception as e: log.error(f"  send error: {e}"); ok = False
        if ok:
            mark_sent(item.uid); sent_uids.add(item.uid); _today_sent.append(item)
            log.info(f"  {GOLD}✅ sent{RESET}")
        else:
            log.warning(f"  {RED}❌ failed{RESET}")
        time.sleep(1.5)
    remaining = [i for i in queue if i.uid not in sent_uids]
    save_queue(remaining)
    log.info(f"  done. sent {len(sent_uids)}/{len(to_send)} | queue: {len(remaining)}")

# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    print(BANNER)
    p = argparse.ArgumentParser(
        description="bitthewriteup — bug bounty digest for discord",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{GOLD}commands:{RESET}
  python3 bitthewriteup.py              # loop (reads config.json)
  python3 bitthewriteup.py --once       # one run then exit
  python3 bitthewriteup.py --dry-run    # preview without sending
  python3 bitthewriteup.py --refresh    # force queue refresh now
  python3 bitthewriteup.py --summary    # send best-of-day to Discord
  python3 bitthewriteup.py --status     # show queue stats
  python3 bitthewriteup.py --list       # list sources
        """,
    )
    p.add_argument("--once",    action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--summary", action="store_true")
    p.add_argument("--status",  action="store_true")
    p.add_argument("--list",    action="store_true")
    args = p.parse_args()
    setup_logging()

    if args.status:
        prune_sent()
        sent   = load_sent()
        active = [s for s in SOURCES if s["enabled"]]
        print(f"{GOLD}{'─'*55}{RESET}")
        print(f"  {RED}bitthewriteup{RESET} v2.1.0")
        print(f"{GOLD}{'─'*55}{RESET}")
        print(f"  webhook  : {WEBHOOK_URL[:52]}...")
        print(f"  schedule : every {INTERVAL_MIN} min | {ITEMS_PER_RUN}/run")
        print(f"  sources  : {len(active)}/{len(SOURCES)} enabled")
        print(f"  sent     : {len(sent)} lifetime")
        print(f"  queue    : {queue_stats()}")
        print(f"{GOLD}{'─'*55}{RESET}")
        return

    if args.list:
        print(f"  {'id':15} {'w':3}  status  name")
        print(f"  {'─'*15} {'─'*3}  ──────  ────")
        for s in SOURCES:
            st = f"{GOLD}on {RESET}" if s["enabled"] else f"{RED}off{RESET}"
            print(f"  {s['id']:15} {s['weight']:<3}  {st}  {s['name']}")
        return

    if args.summary:
        send_daily_summary(_today_sent or load_queue()[:5], len(_today_sent))
        log.info("summary sent."); return

    prune_sent()
    log.info(f"schedule : every {INTERVAL_MIN} min | {ITEMS_PER_RUN}/run")
    log.info(f"score    : min {MIN_SCORE} | cap {MAX_QUEUE}")
    loop = LOOP and not args.once
    if loop:
        log.info(f"mode     : {GOLD}loop{RESET} — ctrl+c to stop\n")
        try:
            while True:
                try: run_once(dry_run=args.dry_run, force_refresh=args.refresh)
                except SystemExit: raise
                except Exception as e: log.error(f"run error: {e}")
                log.info(f"sleeping {INTERVAL_MIN} min...\n")
                time.sleep(INTERVAL_MIN * 60)
        except KeyboardInterrupt:
            print(f"\n{RED}[bitthewriteup]{RESET} stopped. bye!\n")
    else:
        run_once(dry_run=args.dry_run, force_refresh=args.refresh)

if __name__ == "__main__":
    main()
