"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — AI assistant handler
Grok-powered human-like assistant for direct messages and group @mentions.

Per-user toggle:  /ai  — enable or disable AI replies for your account.
AI will NOT respond until the user has run  /ai  at least once to turn it ON.
"""

from __future__ import annotations
import logging
import re
from typing import Optional

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters

from config import cfg
from database.connection import users as users_col

log = logging.getLogger(__name__)

_GROK_URL   = "https://api.x.ai/v1/chat/completions"
_GROK_MODEL = "grok-3-mini"


# ══════════════════════════════════════════════════════════════════════════════
# PER-USER AI TOGGLE  (stored in MongoDB users collection)
# ══════════════════════════════════════════════════════════════════════════════

async def _is_ai_enabled(user_id: int, user_data: dict) -> bool:
    """Return True if AI is enabled for this user (cached in user_data)."""
    if "ai_enabled" in user_data:
        return bool(user_data["ai_enabled"])
    doc = await users_col().find_one({"user_id": user_id}, {"ai_enabled": 1})
    enabled = bool(doc.get("ai_enabled", False)) if doc else False
    user_data["ai_enabled"] = enabled
    return enabled


async def _set_ai_enabled(user_id: int, enabled: bool, user_data: dict) -> None:
    """Persist AI toggle to MongoDB and update local cache."""
    await users_col().update_one(
        {"user_id": user_id},
        {"$set": {"ai_enabled": enabled}},
        upsert=True,
    )
    user_data["ai_enabled"] = enabled


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT  —  exhaustive bot knowledge
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """\
You are the official AI assistant of "Secret File Storage Bot" — a premium \
Telegram-based cloud storage bot.  Your job is to help EVERY user, answer \
EVERY question, and guide them through EVERY feature of the bot.

━━━━━━━━━━━━━━━━━━  PERSONALITY  ━━━━━━━━━━━━━━━━━━
• You are warm, smart, concise, and human.
• Never give robotic or templated replies.
• Keep answers short unless a detailed explanation is needed.
• Always match the user's language (Hindi, English, Hinglish, etc.).
• Never say "I don't know" — if unsure, guide the user to /start or support.
• Use emojis naturally to make responses feel premium and friendly.
• Upsell premium gently when it is genuinely relevant.

━━━━━━━━━━━━━━━━  BOT OVERVIEW  ━━━━━━━━━━━━━━━━━━
Secret File Storage Bot lets users store, organise, encrypt, and share files \
privately on Telegram.  Key pillars:
  📁 File Storage   — upload any file, photo, video, audio, voice, document
  🔍 Smart Search   — full-text search with filters, tags, categories, sorting
  🔐 Encrypted Vault — PIN-locked private space for sensitive files
  🔗 Secure Sharing  — password-protected, one-time, or expiry links
  📂 Folders        — organise files into nested folders
  ⭐ Favourites     — bookmark important files
  💎 Premium Plan   — unlimited storage, 2 GB uploads, all features unlocked
  🤖 AI Assistant   — this bot (you), enabled with /ai command

━━━━━━━━━━━━━━━━  ALL COMMANDS  ━━━━━━━━━━━━━━━━━━

/start
  Opens the main menu with all options.
  First-time users see a welcome screen.
  Deep links (?start=dl_TOKEN) auto-deliver shared files.

/upload
  Tells the bot you want to upload a file.
  Actually, you can just SEND any file directly — the bot saves it automatically!
  Supported: documents, videos, audios, photos, voice messages, video notes.
  Free plan: up to 500 MB per file.  Premium: up to 2 GB.
  Add #tags in the file caption to auto-tag it.  Example: "Invoice #finance #2024"

/search  [query]
  Search across all your stored files.
  You can also type the query directly: /search invoice
  Or just go to Search from the main menu and type your keyword.
  Filters available: All / Documents / Videos / Audios / Photos / Archives
  Sort by: Newest, Oldest, Largest, Most Downloaded
  Results are paginated — use the arrows to browse more pages.
  Tip: search by #tag — e.g., type  #finance  to find all tagged files.

/vault
  Opens your encrypted private vault.
  First time: you set a 4–8 digit PIN.
  Each session: enter your PIN to unlock.
  Files inside the vault are stored encrypted and hidden from your normal file list.
  To lock the vault again: use the 🔒 Lock button inside the vault.
  Lost your PIN? Contact support — vault resets require admin action.

/premium
  Shows your current plan and upgrade options.
  Free plan:  500 MB storage, 500 MB upload limit, 10 share links.
  Premium:    ∞ unlimited storage, 2 GB uploads, unlimited links, all features.
  Price:      ₹9/month or ₹99/year (Yearly plan — best value!)
  Payment:    Pay via UPI/GPay, then send the screenshot inside the bot.
  Approval:   Admin reviews and activates within a few hours.

/stats
  Shows your personal storage stats:
  — Plan (Free / Premium / Admin)
  — Total files stored
  — Storage used vs limit
  — Account join date

/admin   (admin only)
  Opens the admin panel.
  Features: user management, broadcast, payment approvals, system logs,
  maintenance mode toggle, database backup.

/maintenance   (admin only)
  Toggles maintenance mode ON/OFF.
  When ON, regular users see a maintenance message and cannot use the bot.
  Admins can still operate normally.

/ai
  Toggles your personal AI assistant ON or OFF.
  When ON:  bot replies intelligently to your messages.
  When OFF: bot ignores plain text messages (only commands work).
  Default: OFF — you must run /ai once to enable it.

━━━━━━━━━━━━━━━━  FILE OPERATIONS  ━━━━━━━━━━━━━━━━

Uploading a file:
  Just send any file to the bot chat.  That's it!  The bot saves it instantly.
  You can add a caption and #tags.  Example caption: "My Resume #job #2024"
  After upload, you see the file card with actions: Rename, Move, Share, Delete, Vault.

Renaming a file:
  Open your file list, tap the file → tap ✏️ Rename → type the new name.

Moving a file to a folder:
  Open your file list, tap the file → tap 📁 Move → choose the destination folder.

Deleting a file:
  Open your file list, tap the file → tap 🗑 Delete → confirm.
  Deleted files are removed permanently.  Storage is freed immediately.

Downloading / viewing a file:
  Open your file list, tap the file → tap 📥 Download.
  The bot sends the file directly to your chat.

Adding to favourites:
  Tap the file → tap ⭐ Favourite.  View all favourites from the main menu.

Sharing a file:
  Tap the file → tap 🔗 Share.
  Options: set an expiry time, make it one-time-use, add a password.
  The bot generates a t.me deep link you can share with anyone.

━━━━━━━━━━━━━━━━  FOLDER MANAGEMENT  ━━━━━━━━━━━━━━━

Creating a folder:
  Go to main menu → 📁 Files → ➕ New Folder → type a folder name.

Navigating folders:
  Tap a folder to open it.  Use the back arrow to go up a level.

Deleting a folder:
  Open the folder → tap ⚙ Options → 🗑 Delete Folder.
  Warning: deletes all files inside too!

Nested folders:
  You can create folders inside folders (sub-folders) for deep organisation.

━━━━━━━━━━━━━━━━  VAULT GUIDE  ━━━━━━━━━━━━━━━━━━━

What is the Vault?
  A PIN-protected encrypted section of your storage.
  Files inside are hidden from normal search and file list.
  Great for private documents, sensitive photos, confidential data.

Setting up Vault:
  Type /vault → bot asks you to set a PIN (4–8 digits) → enter it twice to confirm.

Unlocking Vault:
  Type /vault → enter your PIN → vault opens for 30 minutes.
  After 30 min the session expires and you need to re-enter your PIN.

Adding files to Vault:
  Upload a file normally → tap 🔐 Add to Vault on the file card.
  Or: unlock the vault first, then send files while vault is open.

Removing files from Vault:
  Open vault → tap the file → tap 📤 Remove from Vault.

Forgot PIN:
  Contact admin/support.  PIN can only be reset by admin action.

━━━━━━━━━━━━━━━━  SHARE LINKS  ━━━━━━━━━━━━━━━━━━━

Creating a share link:
  Open the file → tap 🔗 Share.
  The bot creates a t.me/botusername?start=dl_TOKEN link.

Link options:
  ⏳ Expiry    — link auto-expires after chosen time (1h / 24h / 7d / never)
  🔂 One-time  — link works only once, then self-destructs
  🔒 Password  — recipient must enter a password to download

Managing your links:
  Main menu → 🔗 Links — see all active links, view stats, deactivate.

━━━━━━━━━━━━━━━━  SEARCH & TAGS  ━━━━━━━━━━━━━━━━━━

Full-text search:
  /search  or tap 🔍 Search from the menu.
  Type any keyword — bot searches filenames, captions, and tags.

Tag search:
  Add #tags to captions when uploading.  Search by #tagname.
  Example: upload "photo.jpg" with caption "Holiday #goa #2024"
  Later: /search #goa  →  finds all Goa photos instantly.

Category filter:
  Filter by: All · Documents · Videos · Audios · Photos · Archives

Sort options:
  Newest first / Oldest first / Largest first / Most downloaded

━━━━━━━━━━━━━━━━  PREMIUM GUIDE  ━━━━━━━━━━━━━━━━━━

Free vs Premium comparison:

  Feature              Free          Premium 💎
  ─────────────────────────────────────────────
  Storage              500 MB        ∞ Unlimited
  Upload limit         500 MB        2 GB per file
  Share links          10 max        ∞ Unlimited
  Vault files          Limited       ∞ Unlimited
  Search filters       Basic         Advanced
  Bulk operations      ❌            ✅
  Priority support     ❌            ✅

Price:  ₹9/month or ₹99/year (Yearly plan — best value!)

How to buy Premium:
  1. Type /premium → tap 💎 Buy Premium
  2. Bot shows UPI/GPay payment details
  3. Pay the amount, take a screenshot
  4. Send the screenshot to the bot
  5. Admin verifies and activates within a few hours
  6. You'll get a confirmation message when activated

━━━━━━━━━━━━━━━━  TROUBLESHOOTING  ━━━━━━━━━━━━━━━

Bot not responding?
  Make sure you're not in maintenance mode.
  Try /start to reset your session.

File upload failed?
  Check your file size — free users max 500 MB, premium max 2 GB.
  Make sure you're a member of the required channels (/start again to check).

Can't find a file?
  Use /search with a keyword.  Files are stored by name, tag, and caption.

Share link not working?
  The link may have expired, been used (if one-time), or been deactivated.
  Create a new link from the file card.

Vault PIN forgotten?
  Contact support @its_Xyron — admin can reset your vault.

Payment not activated?
  Wait a few hours after sending the screenshot.
  If still not activated after 24 hours, contact @its_Xyron.

Premium expired?
  Use /premium to renew.  Your files stay safe — only premium features lock.

Rate limit hit?
  Slow down!  Free plan allows 10 messages per 60 seconds.

━━━━━━━━━━━━━━━━  ADMIN FEATURES  ━━━━━━━━━━━━━━━━

(Only visible to admins)
• View all users, search users, ban/unban users
• View and approve/reject pending premium payments
• Broadcast message to all users
• View system activity logs
• Toggle maintenance mode
• Trigger database backup
• Grant/revoke premium manually

━━━━━━━━━━━━━━━━  COMMON Q&A  ━━━━━━━━━━━━━━━━━━

Q: Is my data safe?
A: Yes.  Files are stored in a private Telegram channel.  Vault files are encrypted.

Q: Can others see my files?
A: No.  Each user can only see their own files.

Q: What file types are supported?
A: Everything Telegram supports — documents, videos, audio, photos, voice, video notes.

Q: How many files can I store?
A: Unlimited number of files.  Total storage is 500 MB (free) or unlimited (premium).

Q: Can I use the bot in groups?
A: Yes!  Mention the bot (@botname question) in a group to get AI answers.

Q: How to contact support?
A: Message @its_Xyron on Telegram.

━━━━━━━━━━━━━━━━  RESPONSE RULES  ━━━━━━━━━━━━━━━

1. ALWAYS answer the user's question completely and correctly.
2. NEVER give the same generic reply twice in a conversation.
3. If the user's question is about a bot feature, explain it fully.
4. If the user writes in Hindi or Hinglish, reply in Hinglish.
5. If the user just says "hi/hello/hey", greet them and ask what they need.
6. Guide users to the right command for their need.
7. If something requires admin action, tell them to contact @its_Xyron.
8. Always end with a helpful follow-up or next step.
"""


# ══════════════════════════════════════════════════════════════════════════════
# KEYWORD-BASED SMART FALLBACK  (works even without Grok API)
# ══════════════════════════════════════════════════════════════════════════════

# Each entry: (list_of_keywords_or_patterns, response_text)
# Keywords are matched case-insensitively as whole words / substrings.
_KEYWORD_MAP: list[tuple[list[str], str]] = [
    # ── greetings ─────────────────────────────────────────────────────────────
    (
        ["hi", "hello", "hey", "hii", "helo", "hlo", "helllo", "heyy", "namaste",
         "namaskar", "salaam", "salam", "sat sri akal", "kem cho", "vanakkam",
         "good morning", "good evening", "good afternoon", "good night", "gm", "gn",
         "sup", "wassup", "yo"],
        "Hey! 👋 Welcome to *Secret File Storage Bot*!\n\n"
        "Main yahan hoon aapki help ke liye 😊\n\n"
        "Kya chahiye aapko? File upload karna hai? Search karna hai? Ya kuch aur?\n"
        "Type karo ya /start se main menu open karo! 🚀",
    ),

    # ── start / main menu ─────────────────────────────────────────────────────
    (
        ["start", "main menu", "menu", "home", "begin", "open bot", "bot start",
         "bot kaise use", "use karna", "kaise use"],
        "🚀 *Bot Start Karna:*\n\n"
        "👉 /start type karo — main menu khul jayega!\n\n"
        "Wahan se aap kar sakte ho:\n"
        "📁 File upload/manage\n"
        "🔍 Files search karna\n"
        "🔐 Encrypted vault\n"
        "🔗 Secure share links\n"
        "💎 Premium upgrade\n\n"
        "Simply /start dalo aur sab options milenge! ✅",
    ),

    # ── upload ────────────────────────────────────────────────────────────────
    (
        ["upload", "file bhejo", "file send", "file save", "store file", "file store",
         "kaise upload", "how to upload", "file upload karna", "document upload",
         "photo upload", "video upload", "audio upload", "file kaise store",
         "apload", "uplod"],
        "📤 *File Upload Karna — Super Easy!*\n\n"
        "Bas file directly bot ko bhejo — automatically save ho jati hai! ✅\n\n"
        "✅ Supported types:\n"
        "• 📄 Documents (PDF, Word, ZIP, etc.)\n"
        "• 🎬 Videos\n"
        "• 🎵 Audio / Music\n"
        "• 📷 Photos\n"
        "• 🎤 Voice messages\n"
        "• 📹 Video notes\n\n"
        "💡 Pro Tip: Caption mein #tags add karo!\n"
        "Example: 'My Resume #job #2024'\n\n"
        "📦 Size limit:\n"
        "• Free users: 500 MB per file\n"
        "• Premium users: 2 GB per file 💎\n\n"
        "Upload ke baad file card milega — rename, share, vault sab options honge!",
    ),

    # ── search ────────────────────────────────────────────────────────────────
    (
        ["search", "find", "dhundo", "file dhundna", "file search", "kaise search",
         "how to search", "search karna", "file find", "files kahan hain",
         "meri files", "my files", "serch", "searh"],
        "🔍 *Files Search Karna:*\n\n"
        "1️⃣ /search type karo ya main menu se Search open karo\n"
        "2️⃣ File ka naam, tag ya keyword type karo\n"
        "3️⃣ Results aa jayenge — paginated (arrows se aage/peeche)\n\n"
        "🏷 *Tag se search:*\n"
        "Upload karte waqt #tag lagao:\n"
        "Caption: 'Invoice.pdf #finance #2024'\n"
        "Search: #finance  →  saari finance files mil jayengi!\n\n"
        "🎛 *Filters available:*\n"
        "All · Documents · Videos · Audios · Photos · Archives\n\n"
        "📊 *Sort by:*\n"
        "Newest / Oldest / Largest / Most Downloaded",
    ),

    # ── vault ─────────────────────────────────────────────────────────────────
    (
        ["vault", "encrypted", "private vault", "vault kya", "vault kaise",
         "vault open", "vault unlock", "pin", "vault password", "secret vault",
         "private storage", "locked files", "secure files", "vault use",
         "how to use vault", "bault"],
        "🔐 *Encrypted Vault — Your Secret Space!*\n\n"
        "*Vault kya hai?*\n"
        "PIN-protected private section — files yahan hidden + encrypted rehti hain!\n\n"
        "*Setup (First time):*\n"
        "👉 /vault type karo\n"
        "👉 Bot PIN set karne ko bolega (4–8 digits)\n"
        "👉 PIN enter karo → confirm karo → vault ready! ✅\n\n"
        "*Unlock karna:*\n"
        "👉 /vault → apna PIN enter karo → 30 min ke liye unlock\n\n"
        "*Files vault mein add karna:*\n"
        "File card mein 🔐 Add to Vault button tap karo\n\n"
        "*PIN bhool gaye?*\n"
        "Support se contact karo: @its_Xyron\n\n"
        "💡 Sensitive documents, private photos ke liye perfect!",
    ),

    # ── premium ───────────────────────────────────────────────────────────────
    (
        ["premium", "upgrade", "plan", "pricing", "price", "cost", "kitna",
         "kitne rupaye", "rupees", "rs ", "₹", "inr", "buy premium", "premium kaise",
         "premium lena", "paid plan", "yearly", "subscription", "membership",
         "unlimited storage", "premium features", "premeum", "premuim"],
        "💎 *Premium Plan — Worth Every Rupee!*\n\n"
        "```\n"
        "Feature          Free      Premium 💎\n"
        "─────────────────────────────────────\n"
        "Storage          500 MB    ∞ Unlimited\n"
        "Upload limit     500 MB    2 GB/file\n"
        "Share links      10 max    ∞ Unlimited\n"
        "Vault files      Limited   ∞ Unlimited\n"
        "Priority support  ❌       ✅\n"
        "```\n\n"
        "💰 *Price: ₹9/month or ₹99/year only!*\n\n"
        "*Premium kaise buy karo:*\n"
        "1️⃣ /premium type karo\n"
        "2️⃣ 💎 Buy Premium tap karo\n"
        "3️⃣ UPI/GPay se payment karo\n"
        "4️⃣ Screenshot bot ko bhejo\n"
        "5️⃣ Admin verify karega — kuch ghanton mein activate ho jayega! ✅",
    ),

    # ── payment / UPI ─────────────────────────────────────────────────────────
    (
        ["payment", "pay", "upi", "gpay", "paytm", "phonepe", "bhim", "screenshot",
         "paid", "kaise pay", "payment karna", "how to pay", "paise", "money",
         "transaction", "proof", "receipt"],
        "💳 *Payment Process:*\n\n"
        "1️⃣ /premium type karo → 💎 Buy Premium tap karo\n"
        "2️⃣ Bot UPI ID aur amount dikhayega\n"
        "3️⃣ GPay / Paytm / PhonePe / BHIM se payment karo\n"
        "4️⃣ Payment ka screenshot lo\n"
        "5️⃣ Screenshot directly bot ko bhejo (same chat mein)\n"
        "6️⃣ Admin review karega — kuch ghanton mein activate hoga ✅\n\n"
        "⚠️ 24 ghante baad bhi activate na ho toh:\n"
        "Contact: @its_Xyron",
    ),

    # ── share links ───────────────────────────────────────────────────────────
    (
        ["share", "link", "sharing", "share link", "share file", "file share",
         "kaise share", "how to share", "send to friend", "share karna",
         "shareable link", "download link", "public link", "sher"],
        "🔗 *File Share Karna:*\n\n"
        "1️⃣ File open karo apni list mein\n"
        "2️⃣ 🔗 Share button tap karo\n"
        "3️⃣ Link options choose karo:\n"
        "   ⏳ Expiry time (1h / 24h / 7d / never)\n"
        "   🔂 One-time (sirf ek baar kaam karega)\n"
        "   🔒 Password protect (recipient ko password chahiye hoga)\n"
        "4️⃣ t.me/... link milegi — share karo kisi ko bhi! ✅\n\n"
        "*Links manage karna:*\n"
        "Main menu → 🔗 Links — sab active links, stats, deactivate\n\n"
        "💎 Free plan: max 10 links | Premium: unlimited!",
    ),

    # ── folder ────────────────────────────────────────────────────────────────
    (
        ["folder", "create folder", "new folder", "organise", "organize",
         "folder banana", "folder kaise", "directory", "category files",
         "file arrange", "foldar"],
        "📂 *Folder Management:*\n\n"
        "*New folder banana:*\n"
        "Main menu → 📁 Files → ➕ New Folder → naam type karo ✅\n\n"
        "*Folder navigate karna:*\n"
        "Folder tap karo → andar ke files/sub-folders dikhenge\n"
        "Back arrow se upar jao\n\n"
        "*File folder mein move karna:*\n"
        "File tap karo → 📁 Move → folder choose karo ✅\n\n"
        "*Folder delete karna:*\n"
        "Folder open karo → ⚙ Options → 🗑 Delete\n"
        "⚠️ Warning: andar ki saari files bhi delete ho jayengi!\n\n"
        "*Nested folders bhi supported hain!* (Folders ke andar folders)",
    ),

    # ── delete ────────────────────────────────────────────────────────────────
    (
        ["delete", "remove", "file delete", "delete karna", "file hatana",
         "remove file", "delete file", "hata do", "del", "delet"],
        "🗑 *File Delete Karna:*\n\n"
        "1️⃣ /search ya Files se apni file open karo\n"
        "2️⃣ File card mein 🗑 Delete button tap karo\n"
        "3️⃣ Confirm karo → file permanently delete! ✅\n\n"
        "⚠️ *Dhyan raho:* Delete permanent hai — undo nahi hota!\n"
        "Storage immediately free ho jati hai.\n\n"
        "💡 Agar galti se delete ho jaye toh koi recovery nahi hai.\n"
        "Pehle soch lo! 😊",
    ),

    # ── rename ────────────────────────────────────────────────────────────────
    (
        ["rename", "name change", "file rename", "naam badalna", "rename file",
         "file ka naam", "new name", "renam"],
        "✏️ *File Rename Karna:*\n\n"
        "1️⃣ File open karo apni list se\n"
        "2️⃣ ✏️ Rename button tap karo\n"
        "3️⃣ Naya naam type karo → Enter karo ✅\n\n"
        "💡 Good practice: descriptive names rakho!\n"
        "Example: 'Aadhar_Card_2024.pdf' instead of 'scan1.pdf'",
    ),

    # ── stats / storage ───────────────────────────────────────────────────────
    (
        ["stats", "storage", "space", "kitna space", "how much space",
         "storage left", "storage used", "storage info", "my storage",
         "kitna baki", "limit", "quota", "disk"],
        "📊 *Storage Stats Dekhna:*\n\n"
        "/stats type karo ya menu → 📊 Stats\n\n"
        "Dikhega:\n"
        "• Plan (Free / Premium)\n"
        "• Total files stored\n"
        "• Storage used vs limit\n"
        "• Visual progress bar\n"
        "• Account join date\n\n"
        "📦 *Limits:*\n"
        "• 🆓 Free: 500 MB total\n"
        "• 💎 Premium: ∞ Unlimited\n\n"
        "Storage full ho rahi hai? 💎 /premium se upgrade karo!",
    ),

    # ── favourites ────────────────────────────────────────────────────────────
    (
        ["favourite", "favorite", "star", "bookmark", "saved files",
         "favourites", "favorites", "starred", "fav", "favrit"],
        "⭐ *Favourites Feature:*\n\n"
        "*File favourite mark karna:*\n"
        "File open karo → ⭐ Favourite tap karo ✅\n\n"
        "*Favourites dekhna:*\n"
        "Main menu → ⭐ Favourites\n\n"
        "*Favourite se hatana:*\n"
        "Favourite file open karo → ⭐ tap karo (toggle off)\n\n"
        "💡 Important files ko favourite karo — jaldi access karo kisi bhi waqt!",
    ),

    # ── tags ──────────────────────────────────────────────────────────────────
    (
        ["tag", "tags", "hashtag", "label", "tagging", "tag karna",
         "tag kaise", "how to tag", "#tag"],
        "🏷 *Tags — Smart File Organisation:*\n\n"
        "*Tag lagana:*\n"
        "File upload karte waqt caption mein #tag add karo\n"
        "Example: 'Project Report #work #2024 #report'\n\n"
        "*Tag se search:*\n"
        "/search #work  →  saari work-tagged files milegi!\n\n"
        "💡 *Best practices:*\n"
        "• Short, consistent tags use karo\n"
        "• Category tags: #work #personal #finance #study\n"
        "• Year tags: #2024 #2025\n"
        "• Project tags: #projectname\n\n"
        "Tags = Instant File Finding! 🚀",
    ),

    # ── download ─────────────────────────────────────────────────────────────
    (
        ["download", "file pao", "get file", "file lena", "receive file",
         "file download", "kaise download", "how to download", "downlod"],
        "📥 *File Download Karna:*\n\n"
        "1️⃣ /search se ya Files list se file open karo\n"
        "2️⃣ 📥 Download tap karo\n"
        "3️⃣ Bot directly file send kar dega! ✅\n\n"
        "💡 Shared link se download:\n"
        "t.me/botname?start=dl_TOKEN link open karo\n"
        "Bot automatically file deliver kar dega!\n\n"
        "⚠️ Password-protected link ke liye password chahiye hoga.",
    ),

    # ── AI toggle ─────────────────────────────────────────────────────────────
    (
        ["ai", "ai on", "ai off", "enable ai", "disable ai", "ai assistant",
         "ai kaise", "ai help", "chatbot", "ai enable", "ai disable",
         "ai toggle", "ai command", "ai kya hai", "ai band", "ai chalu"],
        "🤖 *AI Assistant — Aapka Smart Helper!*\n\n"
        "*Enable/Disable karna:*\n"
        "/ai — command chalao, AI ON/OFF ho jayega!\n\n"
        "*AI ON hone ke baad:*\n"
        "• Bot ko directly message karo — AI reply karega\n"
        "• Group mein @mention karo — AI wahan bhi help karega\n"
        "• Koi bhi sawaal pucho — poori guide milegi!\n\n"
        "*AI OFF karna:*\n"
        "Phir se /ai chalao — AI responses band ho jayengi.\n\n"
        "💡 Default: OFF — /ai se ON karna hoga.",
    ),

    # ── support / contact ────────────────────────────────────────────────────
    (
        ["support", "help", "contact", "admin", "owner", "problem", "issue",
         "error", "nahi ho raha", "kaam nahi", "not working", "bug", "complaint",
         "helpline", "assist", "samajh nahi"],
        "🆘 *Support & Help:*\n\n"
        "📬 *Direct Support:* @its_Xyron\n"
        "👨‍💻 *Developer:* @its_Xyron\n\n"
        "*Common solutions:*\n"
        "• Bot respond nahi kar raha → /start type karo\n"
        "• File upload fail → size check karo (free: 500MB)\n"
        "• Vault PIN bhool gaya → @its_Xyron contact karo\n"
        "• Payment activate nahi hui → 24 hr wait karo, fir contact karo\n"
        "• Share link kaam nahi kar raha → naya link banao\n\n"
        "Koi specific problem? Seedha batao — help karunga! 😊",
    ),

    # ── maintenance mode ─────────────────────────────────────────────────────
    (
        ["maintenance", "maintenance mode", "bot down", "maintenance kya",
         "bot off", "maintenance on", "service unavailable"],
        "🔧 *Maintenance Mode:*\n\n"
        "Jab maintenance mode ON hota hai:\n"
        "• Regular users ko 'maintenance' message aata hai\n"
        "• Bot ke features temporarily unavailable hote hain\n"
        "• Admins normally kaam kar sakte hain\n\n"
        "*Admin ke liye:*\n"
        "/maintenance — toggle ON/OFF\n\n"
        "Maintenance complete hone ke baad bot automatically normal ho jata hai!",
    ),

    # ── bot features / what can it do ────────────────────────────────────────
    (
        ["features", "kya kar sakta", "bot kya karta", "capabilities",
         "what can you do", "what does bot do", "bot features", "all features",
         "poori list", "sab features", "feature list"],
        "🔒 *Secret File Storage Bot — Complete Features:*\n\n"
        "📁 *Storage:* Any file — docs, videos, audio, photos, voice\n"
        "🔍 *Smart Search:* Full-text + tag + category + filters\n"
        "🔐 *Encrypted Vault:* PIN-locked private space\n"
        "🔗 *Secure Sharing:* Password, expiry, one-time links\n"
        "📂 *Folders:* Nested organisation\n"
        "⭐ *Favourites:* Quick access bookmarks\n"
        "🏷 *Tags:* #hashtag auto-categorisation\n"
        "💎 *Premium:* Unlimited storage + 2GB uploads @ ₹9/mo or ₹99/yr\n"
        "🤖 *AI Assistant:* 24/7 smart help (enable with /ai)\n"
        "📊 *Stats:* Real-time storage usage\n\n"
        "Kisi bhi feature ke baare mein pucho! 😊",
    ),

    # ── security / privacy ───────────────────────────────────────────────────
    (
        ["safe", "secure", "privacy", "data safe", "data secure",
         "kya data safe", "is it safe", "security", "private", "hack",
         "hacking", "leak", "password safe"],
        "🛡 *Security & Privacy:*\n\n"
        "✅ *Files:* Private Telegram channel mein stored — sirf aap dekh sakte ho\n"
        "✅ *Vault:* AES encryption — PIN ke bina access impossible\n"
        "✅ *Share links:* Optional password + expiry + one-time protection\n"
        "✅ *No public access:* Koi bhi aapki files nahi dekh sakta\n"
        "✅ *Telegram security:* Telegram ka end-to-end secure infrastructure\n\n"
        "💡 Extra security ke liye Vault use karo sensitive files ke liye!",
    ),

    # ── file types / formats ─────────────────────────────────────────────────
    (
        ["file type", "format", "kaunsa file", "which file", "supported files",
         "pdf", "word", "excel", "zip", "mp4", "mp3", "jpg", "png",
         "what files", "kaunse format"],
        "📄 *Supported File Types:*\n\n"
        "📁 *Documents:* PDF, Word, Excel, PPT, TXT, ZIP, RAR, etc.\n"
        "🎬 *Videos:* MP4, MKV, AVI, MOV, etc.\n"
        "🎵 *Audio:* MP3, FLAC, WAV, OGG, etc.\n"
        "📷 *Photos:* JPG, PNG, GIF, WEBP, etc.\n"
        "🎤 *Voice:* Telegram voice messages\n"
        "📹 *Video notes:* Telegram circular video notes\n\n"
        "Basically — *Telegram jo support karta hai, hum bhi karte hain!* ✅\n\n"
        "Size limit: Free 500MB | Premium 2GB per file 💎",
    ),

    # ── how many files ───────────────────────────────────────────────────────
    (
        ["kitni files", "how many files", "file limit", "max files",
         "unlimited files", "files kitni store", "ek din mein"],
        "📦 *File Limits:*\n\n"
        "• Files ki *count* pe koi limit nahi! ∞\n"
        "• Sirf total *storage size* ka limit hai:\n"
        "  🆓 Free: 500 MB total\n"
        "  💎 Premium: Unlimited ∞\n\n"
        "Matlab 1000 choti files bhi rakho, koi problem nahi!\n"
        "Bas total size 500 MB ke andar rehni chahiye (free mein).\n\n"
        "More storage chahiye? /premium se upgrade karo! 💎",
    ),
]


def _keyword_reply(text: str) -> Optional[str]:
    """Return a canned reply if the message matches any keyword pattern."""
    normalized = text.lower().strip()
    for keywords, reply in _KEYWORD_MAP:
        for kw in keywords:
            # whole-word or substring match
            if re.search(r'\b' + re.escape(kw) + r'\b', normalized) or kw in normalized:
                return reply
    return None


# ══════════════════════════════════════════════════════════════════════════════
# GROK API  CALL
# ══════════════════════════════════════════════════════════════════════════════

async def _ask_grok(user_message: str, history: list) -> Optional[str]:
    """Call Grok API and return assistant reply, or None on failure."""
    if not cfg.GROK_API_KEY:
        return None

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for turn in history[-8:]:          # last 8 turns for richer context
        messages.append(turn)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": _GROK_MODEL,
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 400,             # longer, more helpful replies
    }
    headers = {
        "Authorization": f"Bearer {cfg.GROK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _GROK_URL, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                log.warning("grok api error %d", resp.status)
                return None
    except Exception as e:
        log.error("grok request failed: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_ai_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle AI assistant ON/OFF for the calling user."""
    user = update.effective_user
    currently_on = await _is_ai_enabled(user.id, context.user_data)
    new_state = not currently_on
    await _set_ai_enabled(user.id, new_state, context.user_data)

    if new_state:
        await update.message.reply_text(
            "🤖  *AI Assistant — ENABLED* ✅\n\n"
            "Ab aap directly message karo — main samjhunga aur help karunga!\n\n"
            "💡 Tips:\n"
            "• Koi bhi sawaal pucho — commands, features, problems\n"
            "• Hindi, English, Hinglish — sab chalega!\n"
            "• Group mein @mention karo for AI help\n\n"
            "AI band karna ho toh /ai dobara type karo.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "🤖  *AI Assistant — DISABLED* ❌\n\n"
            "Ab bot plain messages ka jawab nahi dega.\n"
            "Commands normally kaam karte rahenge (/start, /search, etc.)\n\n"
            "Wapas enable karna ho toh /ai type karo.",
            parse_mode="Markdown",
        )


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def handle_ai_dm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle direct messages to the bot with AI reply."""
    if update.effective_chat.type != "private":
        return

    # don't intercept messages that other handlers are already waiting for
    if context.user_data and (
        context.user_data.get("awaiting_search")
        or context.user_data.get("awaiting_screenshot")
        or context.user_data.get("vault_state")
        or context.user_data.get("awaiting_broadcast")
        or context.user_data.get("awaiting_rename")
        or context.user_data.get("awaiting_folder_name")
        or context.user_data.get("awaiting_admin_search")
        or context.user_data.get("pending_link_token")
    ):
        return

    text = (update.message.text or "").strip()
    if not text:
        return
    if len(text) > 1000:
        await update.message.reply_text(
            "✂️ ᴍᴇssᴀɢᴇ ᴛᴏᴏ ʟᴏɴɢ. ᴘʟᴇᴀsᴇ ᴋᴇᴇᴘ ɪᴛ ᴜɴᴅᴇʀ 1000 ᴄʜᴀʀs."
        )
        return

    # ── check per-user toggle ─────────────────────────────────────────────────
    if not await _is_ai_enabled(update.effective_user.id, context.user_data):
        return  # AI is OFF for this user — silently ignore

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    # ── try keyword fallback first (fast, no API call) ────────────────────────
    quick_reply = _keyword_reply(text)

    # ── then try Grok (if API key set) ───────────────────────────────────────
    history: list = context.user_data.setdefault("ai_history", [])
    grok_reply: Optional[str] = None

    if cfg.GROK_API_KEY:
        grok_reply = await _ask_grok(text, history)

    reply = grok_reply or quick_reply
    if not reply:
        # generic but informative fallback
        reply = (
            "🤖 Hmm, I didn't quite get that!\n\n"
            "Aap in topics mein se kuch pooch sakte ho:\n"
            "📤 File upload karna\n"
            "🔍 Files search karna\n"
            "🔐 Vault use karna\n"
            "🔗 File share karna\n"
            "💎 Premium plan\n"
            "📂 Folders banana\n\n"
            "Ya /start se main menu open karo!"
        )

    if grok_reply:
        # store this turn in history only for Grok-answered replies
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": grok_reply})
        if len(history) > 20:
            history[:] = history[-20:]

    await update.message.reply_text(reply, parse_mode="Markdown")


async def handle_ai_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle @bot mentions in group chats with AI reply."""
    if update.effective_chat.type == "private":
        return

    message = update.message
    if not message or not message.text:
        return

    bot_username = context.bot.username
    if not bot_username:
        return

    mention = f"@{bot_username}"
    if mention.lower() not in message.text.lower():
        return

    # strip mention from the text
    user_text = message.text.replace(mention, "").strip()
    # also handle case-insensitive mention
    user_text = re.sub(re.escape(mention), "", message.text, flags=re.IGNORECASE).strip()
    if not user_text:
        await message.reply_text(
            "👋 Kya poochna tha? Mention ke baad apna sawaal likho!\n"
            "Example: @botname how do I upload a file?"
        )
        return

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    # try keyword match first, then Grok
    quick_reply = _keyword_reply(user_text)
    grok_reply: Optional[str] = None

    if cfg.GROK_API_KEY:
        grok_reply = await _ask_grok(user_text, [])   # stateless in groups

    reply = grok_reply or quick_reply
    if not reply:
        reply = (
            "🤖 Sawaal samajh nahi aaya!\n\n"
            "File upload, search, vault, sharing, ya premium ke baare mein pucho.\n"
            "Privately baat karni ho toh bot ko DM karo! 😊"
        )

    await message.reply_text(reply, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

def get_handlers():
    return [
        # /ai toggle command
        CommandHandler("ai", cmd_ai_toggle),
        # group @mention handler
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            handle_ai_group_mention,
        ),
        # DM handler — catches unhandled text in private chats
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            handle_ai_dm,
        ),
    ]
