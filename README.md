<div align="center">

```
██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗    ██████╗  ██████╗ ████████╗
██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝    ██╔══██╗██╔═══██╗╚══██╔══╝
██║   ██║███████║██║   ██║██║     ██║       ██████╔╝██║   ██║   ██║   
╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║       ██╔══██╗██║   ██║   ██║   
 ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║       ██████╔╝╚██████╔╝   ██║   
  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝       ╚═════╝  ╚═════╝    ╚═╝   
```

**Production-Grade Telegram File Storage & Management System**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0+-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot_API_7.0+-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

*Your private Telegram Drive · Search Engine · Encrypted Vault · CDN · SaaS — all in one bot.*

---

</div>

## ✦ Overview

**Vault Bot** is an enterprise-level, fully async Telegram file storage system built with `python-telegram-bot v21+` and MongoDB. It combines the power of Google Drive, a search engine, an encrypted personal vault, a CDN-style file sharing service, and a SaaS admin dashboard — all inside Telegram.

Every interaction is keyboard-driven, every UI element uses **small-caps Unicode**, and every feature is production-ready with proper error handling, logging, and modular architecture.

---

## ✦ Feature Matrix

| Category | Feature | Free | Premium |
|---|---|:---:|:---:|
| **Storage** | File upload & management | ✓ 20MB | ✓ 2GB |
| | Folder tree navigation | ✓ | ✓ |
| | File rename / move / copy | ✓ | ✓ |
| | Duplicate detection | ✓ | ✓ |
| | Storage quota | 500MB | 10GB |
| **Search** | Full-text search | ✓ | ✓ |
| | Category filters | ✓ | ✓ |
| | Advanced filters (size/date/tags) | ✗ | ✓ |
| | Sort by latest / size / popularity | ✓ | ✓ |
| **Vault** | PIN-protected encrypted vault | 5 files | ✓ Unlimited |
| | Auto-lock after inactivity | ✓ | ✓ |
| | Session management | ✓ | ✓ |
| **Sharing** | Token-based share links | 3 links | ✓ Unlimited |
| | Expiry control | ✓ | ✓ |
| | One-time download links | ✗ | ✓ |
| | Password-protected links | ✗ | ✓ |
| **Premium** | Subscription plans | — | ₹99/mo · ₹799/yr |
| | GPay / UPI payment | ✓ | — |
| | Admin approval workflow | — | ✓ |
| **Admin** | Broadcast messages | — | ✓ |
| | User management (ban/unban) | — | ✓ |
| | Force grant premium | — | ✓ |
| | Real-time system stats | — | ✓ |
| | Log viewer | — | ✓ |
| | Backup & restore | — | ✓ |
| | Maintenance mode toggle | — | ✓ |

---

## ✦ Architecture

```
telegram-vault-bot/
│
├── main.py                    # application entry, handler registration, lifecycle
├── config.py                  # centralised env config (dataclass, frozen)
│
├── database/
│   ├── connection.py          # motor async client, collection accessors, indexes
│   ├── models.py              # document factory functions, enums
│   └── __init__.py
│
├── handlers/                  # telegram update handlers (thin layer)
│   ├── start.py               # /start, deep-link resolver, main menu
│   ├── upload.py              # file upload, size/quota checks
│   ├── search.py              # full-text search, filters, pagination
│   ├── file_ops.py            # send, rename, delete, copy, move, info, favorite
│   ├── folder.py              # folder create, navigate, rename, delete
│   ├── vault.py               # pin setup, unlock, session, vault file listing
│   ├── share.py               # share link create, view, revoke
│   ├── premium.py             # plan selection, payment screenshot, approval
│   └── admin.py               # admin panel, broadcast, ban, stats, backup
│
├── services/                  # business logic layer (pure async)
│   ├── file_service.py        # file crud, versioning, duplicate detection
│   ├── folder_service.py      # folder tree, breadcrumb, recursive delete
│   ├── search_service.py      # mongodb text search, tag suggestions
│   ├── vault_service.py       # pin hashing, session management, vault ops
│   ├── share_service.py       # token generation, link lifecycle, access tracking
│   ├── user_service.py        # user crud, favorites, recent, storage tracking
│   ├── subscription_service.py# plan management, payment workflow, auto-expiry
│   └── backup_service.py      # json export/import, scheduled backup
│
├── middlewares/
│   ├── auth.py                # user registration, ban check, last_seen update
│   ├── rate_limiter.py        # token bucket per user
│   └── channel_check.py       # required channel membership enforcement
│
├── utils/
│   ├── keyboards.py           # all inline keyboard builders (small caps ui)
│   ├── helpers.py             # formatting, hashing, upi links, tokens
│   ├── encryption.py          # fernet symmetric encryption for vault
│   ├── logger.py              # dual logger: console + telegram log channel
│   └── scheduler.py           # apscheduler: expiry, cleanup, auto-backup
│
├── .env.example
├── requirements.txt
├── Procfile
└── README.md
```

**Design Principles:**
- **Separation of Concerns** — handlers never touch the DB directly; all logic lives in services
- **Async everywhere** — `motor`, `asyncio`, `python-telegram-bot` v21 concurrent updates
- **Typed** — dataclasses, type hints, and enums throughout
- **Zero external file storage** — all files stored as Telegram `file_id` in a private channel

---

## ✦ Quick Setup

### 1 · Prerequisites

```bash
Python 3.11+
MongoDB Atlas (free tier works) or self-hosted MongoDB 7+
A Telegram Bot Token from @BotFather
A private Telegram channel for storage
A private Telegram channel for logs
```

### 2 · Installation

```bash
git clone https://github.com/youruser/telegram-vault-bot
cd telegram-vault-bot

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3 · Environment

```bash
cp .env.example .env
nano .env                      # fill in all values
```

Key variables:

| Variable | Description |
|---|---|
| `BOT_TOKEN` | From @BotFather |
| `OWNER_ID` | Your Telegram user ID |
| `ADMIN_IDS` | Comma-separated admin IDs |
| `MONGO_URI` | MongoDB connection string |
| `STORAGE_CHANNEL_ID` | Private channel ID (with `-100` prefix) |
| `LOG_CHANNEL_ID` | Private log channel ID |
| `REQUIRED_CHANNELS` | e.g. `secretsbotz` (no @) |
| `UPI_ID` | Your GPay/UPI ID e.g. `yourname@gpay` |

### 4 · Storage Channel Setup

1. Create a private Telegram channel
2. Add your bot as **admin** with post permissions
3. Copy the channel ID (format: `-100XXXXXXXXXX`)
4. Set it as `STORAGE_CHANNEL_ID` in `.env`

### 5 · Run

```bash
python main.py
```

---

## ✦ Deployment

### Railway (Recommended)

```bash
# install railway cli
npm install -g @railway/cli

railway login
railway init
railway up
```

Set all env vars in Railway dashboard → Variables.  
The `Procfile` handles the process type automatically.

### Render

1. Connect your GitHub repo
2. Set **Build Command**: `pip install -r requirements.txt`
3. Set **Start Command**: `python main.py`
4. Add all environment variables
5. Set instance type to **Background Worker**

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t vault-bot .
docker run --env-file .env vault-bot
```

---

## ✦ GPay / UPI Payment Integration

The bot generates **UPI deep links** for one-tap payment. Here's how it works:

### How It Works

```
User taps "💳 Pay ₹99 via UPI/GPay"
    ↓
UPI deep link opens GPay/PhonePe/Paytm
    ↓
User pays & takes a screenshot
    ↓
User sends screenshot to bot
    ↓
Bot forwards to admin with [✅ Approve] [❌ Reject] buttons
    ↓
Admin approves → user instantly gets premium
```

### UPI Link Format

```python
upi://pay?pa=yourname@gpay&pn=Vault+Bot&am=99&tn=vault+monthly&cu=INR
```

Set your UPI ID in `.env`:
```
UPI_ID=yourname@gpay
UPI_NAME=Vault Bot Premium
```

### Adding Razorpay (Optional Advanced)

If you want automated payment verification, integrate Razorpay:

```bash
pip install razorpay
```

```python
import razorpay

client = razorpay.Client(auth=("YOUR_KEY_ID", "YOUR_KEY_SECRET"))
order = client.order.create({
    "amount": 9900,        # paise (₹99 = 9900)
    "currency": "INR",
    "receipt": f"vault_{user_id}_{timestamp}",
})
# share order id with user, verify webhook on payment
```

> For the current screenshot-based flow, no Razorpay account is needed.

---

## ✦ Admin Commands

| Command | Description |
|---|---|
| `/admin` | Open admin panel |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/grant <user_id> <plan>` | Force-grant premium |

Admin panel buttons:
- **👥 Users** — browse, view stats, ban/unban, toggle premium
- **📊 Stats** — system-wide stats: users, files, storage, payments
- **📢 Broadcast** — send any message to all users
- **💳 Payments** — review pending payment screenshots
- **📋 Logs** — recent activity log
- **🛠 Maintenance** — toggle maintenance mode
- **💾 Backup** — create instant JSON backup

---

## ✦ Database Collections

| Collection | Purpose |
|---|---|
| `users` | User profiles, roles, storage quota, favorites, recent |
| `files` | File metadata, `file_id`, tags, category, hash, vault flag |
| `folders` | Folder tree with parent_id references |
| `sessions` | Vault unlock sessions (auto-expire) |
| `links` | Share link tokens with expiry and access tracking |
| `payments` | Payment records with screenshot references |
| `subscriptions` | Active premium subscriptions with expiry |
| `logs` | Action audit log |

All collections have proper indexes for query performance.

---

## ✦ Logging System

Every user action generates a structured log entry sent to the private log channel:

```
📤 UPLOAD
├ ᴜsᴇʀ: 123456789 (@username)
├ ᴛɪᴍᴇ: 2024-01-15 14:32:01 UTC
├ file: document.pdf
├ size: 4.2 MB
└ vault: False
```

Actions logged: `upload`, `download`, `delete`, `search`, `vault`, `share`, `payment`, `auth`, `admin`, `ban`, `unban`, `system`, `backup`

---

## ✦ Security

- **PIN hashing** — vault PINs are hashed with SHA-256 + secret salt
- **Fernet encryption** — vault metadata is symmetrically encrypted
- **Rate limiting** — token bucket (10 messages/60s default, configurable)
- **Role-based access** — owner > admin > premium > user > banned
- **Input sanitisation** — all user inputs sanitised before DB operations
- **Session timeout** — vault auto-locks after 30 minutes of inactivity
- **Owner bypass** — owner ID bypasses all restrictions
- **Channel enforcement** — bot unusable until required channels are joined

---

## ✦ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Bot Framework | python-telegram-bot 21.6 |
| Database | MongoDB 7 via Motor (async) |
| Scheduling | APScheduler 3.10 |
| Encryption | cryptography (Fernet) |
| Event Loop | uvloop (optional, 2× faster) |
| Hosting | Railway / Render / Docker |

---

## ✦ Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'add my feature'`
4. Push and open a Pull Request

---

<div align="center">

**Built with precision. Designed for scale.**

ᴅᴇᴠ: [@its_me_secret](https://t.me/its_me_secret) &nbsp;|&nbsp; sᴜᴘᴘᴏʀᴛ: [@song_assistant](https://t.me/song_assistant)

</div>
