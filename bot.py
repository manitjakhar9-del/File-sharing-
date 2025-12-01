import json
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ========== CONFIG ==========
API_ID = int(os.getenv("API_ID", "123456"))       # from env vars
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456"))   # your telegram user id

DATA_FILE = "files.json"

# ========== LOAD / SAVE STORAGE ==========

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"counter": 0, "files": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

db = load_data()
# db = { "counter": int, "files": { "id": { "type": "..", "file_id": "..", "caption": "..." } } }

# ========== BOT CLIENT ==========
app = Client(
    "file_share_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

waiting_for_file = set()

# ========== HELPER: SEND FILE BY KEY ==========
async def send_file_by_id(client: Client, message: Message, key: str):
    if key not in db["files"]:
        await message.reply_text("❌ File not found. Wrong ID?")
        return

    file_data = db["files"][key]
    ftype = file_data["type"]
    fid = file_data["file_id"]
    cap = file_data.get("caption") or f"File #{key}"

    if ftype == "document":
        await message.reply_document(fid, caption=cap)
    elif ftype == "video":
        await message.reply_video(fid, caption=cap)
    elif ftype == "photo":
        await message.reply_photo(fid, caption=cap)
    else:
        await message.reply_text("⚠️ Unknown file type stored.")

# ========== /start COMMAND ==========
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    args = message.text.split(maxsplit=1)

    if len(args) == 1:
        btns = [
            [InlineKeyboardButton("📂 Get by ID", callback_data="open_get")],
        ]
        if message.from_user.id == ADMIN_ID:
            btns.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")])

        await message.reply_text(
            "👋 Welcome to File Share Bot!\n\n"
            "• Admin: /admin se files add karo\n"
            "• Users: /get <id> se file lo\n\n"
            "Agar tumhare paas direct link hai:\n"
            "`https://t.me/YourBot?start=1`\n"
            "to bas Start dabao, file aa jayegi.",
            reply_markup=InlineKeyboardMarkup(btns),
            quote=True
        )
        return

    key = args[1].strip()
    await send_file_by_id(client, message, key)

# ========== /get COMMAND ==========
@app.on_message(filters.command("get") & filters.private)
async def get_handler(client: Client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) == 1:
        await message.reply_text("Usage: `/get <id>`", parse_mode="markdown")
        return

    key = args[1].strip()
    await send_file_by_id(client, message, key)

# ========== ADMIN PANEL ==========
def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add new file", callback_data="admin_add")],
            [InlineKeyboardButton("📋 List all files", callback_data="admin_list")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel")],
        ]
    )

@app.on_message(filters.command("admin") & filters.private)
async def admin_cmd_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("⛔ You are not allowed to access admin panel.")
        return

    await message.reply_text(
        "🛠 Admin Panel:\n\n"
        "Choose an option:",
        reply_markup=admin_keyboard()
    )

# ========== CALLBACKS ==========
@app.on_callback_query()
async def callback_handler(client, cq):
    user_id = cq.from_user.id
    data = cq.data

    if data == "open_get":
        await cq.message.reply_text("Send `/get <id>` to receive a file.\nExample: `/get 1`", parse_mode="markdown")
        await cq.answer()
        return

    if user_id != ADMIN_ID and data.startswith("admin_"):
        await cq.answer("Not allowed.", show_alert=True)
        return

    if data == "admin_panel":
        await cq.message.reply_text(
            "🛠 Admin Panel:\n\nChoose an option:",
            reply_markup=admin_keyboard()
        )
        await cq.answer()

    elif data == "admin_add":
        waiting_for_file.add(user_id)
        await cq.message.reply_text(
            "📤 Send me the file now (document / video / photo).\n\n"
            "Caption = will be saved as file caption."
        )
        await cq.answer("Send file now.", show_alert=False)

    elif data == "admin_list":
        if not db["files"]:
            await cq.message.reply_text("ℹ️ No files saved yet.")
            await cq.answer()
            return

        text_lines = ["📋 *Saved Files:*"]
        for key, info in db["files"].items():
            cap = info.get("caption") or "No caption"
            text_lines.append(f"`{key}` → {cap[:40]}")
        txt = "\n".join(text_lines)

        await cq.message.reply_text(txt, parse_mode="markdown")
        await cq.answer()

    elif data == "admin_cancel":
        if user_id in waiting_for_file:
            waiting_for_file.discard(user_id)
        await cq.message.reply_text("✅ Admin operation cancelled.")
        await cq.answer()

# ========== ADMIN FILE UPLOAD ==========
@app.on_message(
    filters.private
    & filters.user(ADMIN_ID)
    & (filters.document | filters.video | filters.photo)
)
async def admin_file_save_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in waiting_for_file:
        await message.reply_text("ℹ️ Use /admin → 'Add new file' first.")
        return

    if message.document:
        ftype = "document"
        file_id = message.document.file_id
    elif message.video:
        ftype = "video"
        file_id = message.video.file_id
    elif message.photo:
        ftype = "photo"
        file_id = message.photo.file_id
    else:
        await message.reply_text("⚠️ Unsupported file type.")
        return

    caption = message.caption or ""

    db["counter"] += 1
    key = str(db["counter"])
    db["files"][key] = {
        "type": ftype,
        "file_id": file_id,
        "caption": caption
    }
    save_data()

    waiting_for_file.discard(user_id)

    bot = await client.get_me()
    deep_link = f"https://t.me/{bot.username}?start={key}"

    await message.reply_text(
        f"✅ File saved!\n\n"
        f"ID: `{key}`\n"
        f"Deep Link:\n{deep_link}\n\n"
        f"Users can:\n"
        f"• Click this link\n"
        f"• Or type `/get {key}` in bot chat.",
        parse_mode="markdown",
        disable_web_page_preview=True
    )

# ========== RUN ==========
print("Bot is running with admin panel on Render...")
app.run()
