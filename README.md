<div align="center">

```text
██████╗ ██╗████████╗    ████████╗██╗  ██╗███████╗    ██╗    ██╗██████╗ ██╗████████╗███████╗██╗   ██╗██████╗
██╔══██╗██║╚══██╔══╝    ╚══██╔══╝██║  ██║██╔════╝    ██║    ██║██╔══██╗██║╚══██╔══╝██╔════╝██║   ██║██╔══██╗
██████╔╝██║   ██║          ██║   ███████║█████╗      ██║ █╗ ██║██████╔╝██║   ██║   █████╗  ██║   ██║██████╔╝
██╔══██╗██║   ██║          ██║   ██╔══██║██╔══╝      ██║███╗██║██╔══██╗██║   ██║   ██╔══╝  ██║   ██║██╔═══╝
██████╔╝██║   ██║          ██║   ██║  ██║███████╗    ╚███╔███╔╝██║  ██║██║   ██║   ███████╗╚██████╔╝██║
╚═════╝ ╚═╝   ╚═╝          ╚═╝   ╚═╝  ╚═╝╚══════╝     ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝ ╚═════╝ ╚═╝
─────────────────────────────────────────────────────────────────────────────────────
```

# BitTheWriteup

**Automated Bug Bounty Writeup Digest for Discord**

![Python](https://img.shields.io/badge/python-3.9+-red?style=flat-square&logo=python)
![Dependencies](https://img.shields.io/badge/dependencies-stdlib%20only-darkred?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![Author](https://img.shields.io/badge/author-0xdragon-gold?style=flat-square)

</div>

---

## Overview

BitTheWriteup is a lightweight Python script that automatically collects high-quality Bug Bounty writeups from multiple trusted sources and delivers them directly to a Discord channel using a webhook.

The project uses only Python's standard library and requires no third-party dependencies.

---

## Features

- Automatic Discord delivery
- Configurable scheduling
- Duplicate prevention
- Queue prioritization
- Multiple trusted sources
- Daily summary mode
- Zero external dependencies

---

## Installation

```bash
git clone https://github.com/0xdragon10/BitTheWriteup.git
cd bitthewriteup
cp config.example.json config.json
```

Python 3.9 or newer is required.

---

## Configuration

Edit `config.json` and set your Discord webhook:

```json
{
  "discord_webhook": "https://discord.com/api/webhooks/YOUR/WEBHOOK"
}
```

---

## Usage

```bash
python3 bitthewriteup.py --dry-run
python3 bitthewriteup.py
python3 bitthewriteup.py --once
python3 bitthewriteup.py --refresh
python3 bitthewriteup.py --summary
python3 bitthewriteup.py --status
python3 bitthewriteup.py --list
```

---

## Project Structure

| File | Description |
|------|-------------|
| `bitthewriteup.py` | Main application |
| `config.json` | User configuration |
| `queue.json` | Cached queue |
| `sent.log` | Sent history |
| `run.log` | Execution log |

---

## License

MIT

---

<div align="center">

Made by **0xdragon**

</div>
