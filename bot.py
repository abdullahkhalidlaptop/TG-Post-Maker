import json
import logging
import os
import random
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0").strip())
INITIAL_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()

CONFIG_FILE = Path("config.json")

DEFAULT_PROMPT = """You are the AI extraction and post-writing engine for a Telegram app/movie/software posting bot.

INPUT:
- A forwarded Telegram post caption/text (may contain branding, emojis, links, advertisements, channel promotion, and irrelevant text).
- The image attached to that post, if any.

GOAL:
Create data for ONE SINGLE POST using our fixed template.

IMPORTANT RULES:
1. ALWAYS fill EVERY field. NEVER omit a section.
2. First extract information directly from the supplied caption/text and image.
3. Ignore the source channel's branding, footer, promotional wording, watermarks, decorative formatting, and emojis unless they contain actual product facts.
4. Prefer information supplied in the source post when it is concrete and readable.
5. NEVER invent or alter a supplied URL if it is readable and usable.
6. If a factual field is missing, MAKE A PLAUSIBLE BEST-EFFORT VALUE so the template remains complete.
7. If a URL is missing, DO NOT fabricate a real unrelated domain. Use a clearly editable placeholder URL such as https://example.com/ or https://example.com/download.
8. Keep overview descriptions and key features clear and concise so the entire post comfortably fits within a single message.
9. Return ONLY a valid JSON object matching the requested schema.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "requirements": {"type": "string"},
        "category": {"type": "string"},
        "overview": {"type": "string"},
        "source": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "url": {"type": "string"},
                "omit": {"type": "boolean"},
            },
            "required": ["label", "url", "omit"],
        },
        "apk_details": {
            "type": "object",
            "properties": {
                "architecture": {"type": "string"},
                "size": {"type": "string"},
                "version": {"type": "string"},
                "omit": {"type": "boolean"},
            },
            "required": ["architecture", "size", "version", "omit"],
        },
        "key_features": {
            "type": "object",
            "properties": {
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "omit": {"type": "boolean"},
            },
            "required": ["features", "omit"],
        },
        "download": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "url": {"type": "string"},
                "size_label": {"type": "string"},
                "omit": {"type": "boolean"},
            },
            "required": ["label", "url", "omit"],
        },
    },
    "required": [
        "title",
        "requirements",
        "category",
        "overview",
        "source",
        "apk_details",
        "key_features",
        "download",
    ],
}

FOOTER = (
    '⚡Get official builds from '
    '<a href="https://t.me/ak_apps_official">@ak_apps_official</a>'
)
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("movie-post-bot")


# Config Persistence
def load_config() -> dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config.json: {e}")

    keys = [INITIAL_GEMINI_KEY] if INITIAL_GEMINI_KEY else []
    config = {
        "api_keys": keys,
        "prompt": DEFAULT_PROMPT,
        "admins": []
    }
    save_config(config)
    return config


def save_config(config: dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def is_authorized(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    config = load_config()
    return user_id in config.get("admins", [])


# Utility Functions
def clean_url(url: str) -> str:
    url = (url or "").strip()
    return url.rstrip(" \t\r\n.,;:!?)]}>\"'")


def esc(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def html_link(label: str, url: str) -> str:
    return f'<a href="{esc(clean_url(url))}">{esc(label)}</a>'


def blockquote(text: str) -> str:
    return f"<blockquote>{esc(text)}</blockquote>"


def blockquote_html(html: str) -> str:
    return f"<blockquote>{html}</blockquote>"


def valid_http_url(url: str) -> bool:
    return bool(re.match(r"^https?://", clean_url(url), flags=re.I))


def normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    data["title"] = str(data.get("title", "")).strip()
    data["requirements"] = str(data.get("requirements", "")).strip()
    data["category"] = str(data.get("category", "")).strip()
    data["overview"] = str(data.get("overview", "")).strip()

    source = data.get("source") or {}
    source["label"] = str(source.get("label", "Check Me on Web")).strip() or "Check Me on Web"
    source["url"] = clean_url(str(source.get("url", "")))
    source["omit"] = bool(source.get("omit", False))
    if not valid_http_url(source["url"]):
        source["omit"] = True
    data["source"] = source

    details = data.get("apk_details") or {}
    details["architecture"] = str(details.get("architecture", "")).strip()
    details["size"] = str(details.get("size", "")).strip()
    details["version"] = str(details.get("version", "")).strip()
    details["omit"] = bool(details.get("omit", False))
    data["apk_details"] = details

    features = data.get("key_features") or {}
    raw_features = features.get("features", [])
    if not isinstance(raw_features, list):
        raw_features = []
    features["features"] = [
        str(x).strip().lstrip("•").strip()
        for x in raw_features
        if str(x).strip()
    ]
    features["omit"] = bool(features.get("omit", False)) or not features["features"]
    data["key_features"] = features

    download = data.get("download") or {}
    download["label"] = str(download.get("label", "")).strip()
    download["url"] = clean_url(str(download.get("url", "")))
    download["size_label"] = str(download.get("size_label", "")).strip()
    download["omit"] = bool(download.get("omit", False))
    if not valid_http_url(download["url"]):
        download["omit"] = True
    data["download"] = download

    if not data["title"]:
        data["title"] = "Untitled"

    return data


def format_post(d: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(f"<b>{esc(d['title'])}</b>")

    if d["requirements"]:
        parts += ["", "<b>Requirements :</b>", blockquote(d["requirements"])]

    if d["category"]:
        parts += ["", "<b>Category :</b>", blockquote(d["category"])]

    if d["overview"]:
        parts += ["", "<b>Overview :</b>", blockquote(d["overview"])]

    source = d["source"]
    if not source["omit"]:
        parts += [
            "",
            "<b>Source :</b>",
            blockquote_html(html_link(source["label"], source["url"])),
        ]

    details = d["apk_details"]
    if not details["omit"]:
        lines = []
        if details["architecture"]:
            lines.append(f"Architecture : {esc(details['architecture'])}")
        if details["size"]:
            lines.append(f"Size : {esc(details['size'])}")
        if details["version"]:
            lines.append(f"Version : {esc(details['version'])}")
        if lines:
            parts += ["", "<b>APK Details :</b>", f"<blockquote>{'\n'.join(lines)}</blockquote>"]

    features = d["key_features"]
    if not features["omit"]:
        feature_text = "\n".join(
            f"• {esc(feature)}" for feature in features["features"]
        )
        parts += ["", "<b>𒆜 Key Features:</b>", f"<blockquote>{feature_text}</blockquote>"]

    download = d["download"]
    if not download["omit"]:
        heading = "<b>Download Link"
        if download["size_label"]:
            heading += f" [{esc(download['size_label'])}]"
        heading += " :</b>"
        parts += [
            "",
            heading,
            blockquote_html(html_link(download["label"] or "Download", download["url"])),
        ]

    parts += ["", DIVIDER, "", FOOTER]
    return "\n".join(parts)


async def get_message_image(message, bot, workdir: Path) -> tuple[Optional[bytes], Optional[str]]:
    if message.photo:
        photo = message.photo[-1]
        tg_file = await bot.get_file(photo.file_id)
        path = workdir / "input.jpg"
        await tg_file.download_to_drive(custom_path=path)
        return path.read_bytes(), "image/jpeg"

    if message.document and message.document.mime_type:
        mime = message.document.mime_type.lower()
        if mime.startswith("image/"):
            tg_file = await bot.get_file(message.document.file_id)
            suffix = ".img"
            if "." in (message.document.file_name or ""):
                suffix = Path(message.document.file_name).suffix or suffix
            path = workdir / f"input{suffix}"
            await tg_file.download_to_drive(custom_path=path)
            return path.read_bytes(), mime

    return None, None


# Multi-Key & Multi-Model Async Gemini Calling Engine
async def call_gemini_with_fallback(
    post_text: str,
    image_bytes: Optional[bytes],
    image_mime: Optional[str],
) -> dict[str, Any]:
    config = load_config()
    api_keys = config.get("api_keys", [])

    if not api_keys:
        raise RuntimeError("No Gemini API keys configured. Use /edit to add API keys.")

    shuffled_keys = list(api_keys)
    random.shuffle(shuffled_keys)

    candidate_models = ["gemini-2.5-flash"]
    prompt_text = config.get("prompt", DEFAULT_PROMPT)

    contents: list[Any] = [
        prompt_text,
        "\n\nFORWARDED TELEGRAM TEXT/CAPTION:\n"
        + (post_text.strip() if post_text.strip() else "[No text/caption]"),
    ]

    if image_bytes:
        contents.append(
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=image_mime or "image/jpeg",
            )
        )
        contents.append("\nThe attached image is part of the forwarded post. Extract all relevant details.")

    last_error = None

    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SCHEMA,
    )

    for key in shuffled_keys:
        try:
            client = genai.Client(api_key=key)
            for model_name in candidate_models:
                try:
                    logger.info("Attempting Gemini request with key ending ...%s on model %s", key[-6:], model_name)

                    response = await client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=gen_config,
                    )

                    text = (response.text or "").strip()
                    if not text:
                        continue

                    data = json.loads(text)

                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                data = item
                                break
                        else:
                            raise ValueError("Response list contains no dict objects")
                    elif not isinstance(data, dict):
                        raise ValueError(f"Unexpected response type: {type(data)}")

                    return normalize_data(data)

                except Exception as exc:
                    logger.warning("Model %s failed with key ending ...%s: %s", model_name, key[-6:], exc)
                    last_error = exc
                    continue
        except Exception as key_exc:
            logger.warning("Failed initializing client with key ending ...%s: %s", key[-6:], key_exc)
            last_error = key_exc
            continue

    raise RuntimeError(f"All API keys/models failed. Last error: {last_error}")


# Post Processing Handler
async def process_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    if not is_authorized(user.id):
        return

    user_state = context.user_data.get("awaiting_input")
    if user_state:
        await handle_user_input(update, context)
        return

    status = await message.reply_text("🔎 Processing post with Gemini…")

    try:
        post_text = message.caption or message.text or ""
        workdir = Path(tempfile.mkdtemp(prefix="movie_post_"))

        image_bytes, image_mime = await get_message_image(message, context.bot, workdir)

        if not post_text and not image_bytes:
            await status.edit_text("❌ Send or forward a post containing text or an image.")
            return

        data = await call_gemini_with_fallback(
            post_text=post_text,
            image_bytes=image_bytes,
            image_mime=image_mime,
        )
        formatted = format_post(data)

        try:
            await status.delete()
        except Exception:
            pass

        await message.reply_text(
            formatted,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    except Exception as exc:
        logger.exception("Processing failed")
        await message.reply_text(f"❌ Failed: {exc}")


# Interactive Command Menu & Keyboards
def build_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🔑 API Keys", callback_data="menu_keys"),
            InlineKeyboardButton("📝 Prompt", callback_data="menu_prompt"),
        ]
    ]
    if is_owner(user_id):
        buttons.append([InlineKeyboardButton("👥 Admins", callback_data="menu_admins")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="menu_close")])
    return InlineKeyboardMarkup(buttons)


def build_keys_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("➕ Add Key", callback_data="key_add"),
            InlineKeyboardButton("➖ Remove Key", callback_data="key_remove"),
        ],
        [InlineKeyboardButton("👁️ Show Keys", callback_data="key_show")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def build_prompt_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("👁️ Show Prompt", callback_data="prompt_show"),
            InlineKeyboardButton("✏️ Edit Prompt", callback_data="prompt_edit"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def build_admins_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("➕ Add Admin", callback_data="admin_add"),
            InlineKeyboardButton("➖ Remove Admin", callback_data="admin_remove"),
        ],
        [InlineKeyboardButton("👁️ View Admins", callback_data="admin_show")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(buttons)


async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_authorized(user.id):
        return

    context.user_data["awaiting_input"] = None
    await update.effective_message.reply_text(
        "⚙️ **Bot Management Control Panel**\nSelect an option to configure:",
        reply_markup=build_main_keyboard(user.id),
        parse_mode=ParseMode.MARKDOWN,
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    user_id = query.from_user.id
    if not is_authorized(user_id):
        await query.answer("⛔ Unauthorized", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data == "menu_main":
        context.user_data["awaiting_input"] = None
        await query.edit_message_text(
            "⚙️ **Bot Management Control Panel**\nSelect an option to configure:",
            reply_markup=build_main_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_keys":
        await query.edit_message_text(
            "🔑 **API Key Management**\nChoose an action:",
            reply_markup=build_keys_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_prompt":
        await query.edit_message_text(
            "📝 **Prompt Management**\nChoose an action:",
            reply_markup=build_prompt_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_admins":
        if not is_owner(user_id):
            await query.answer("⛔ Owner only feature", show_alert=True)
            return
        await query.edit_message_text(
            "👥 **Admin Management**\nChoose an action:",
            reply_markup=build_admins_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_close":
        context.user_data["awaiting_input"] = None
        await query.delete_message()

    elif data == "key_show":
        config = load_config()
        keys = config.get("api_keys", [])
        if not keys:
            msg = "🔑 No API keys registered."
        else:
            masked = [f"`{k[:6]}...{k[-4:]}`" for k in keys]
            msg = f"🔑 **Current API Keys ({len(keys)}):**\n" + "\n".join(masked)
        await query.edit_message_text(msg, reply_markup=build_keys_keyboard(), parse_mode=ParseMode.MARKDOWN)

    elif data == "key_add":
        context.user_data["awaiting_input"] = "ADD_KEY"
        await query.edit_message_text("📥 Please send the **Gemini API Key** you want to add as a message:")

    elif data == "key_remove":
        context.user_data["awaiting_input"] = "REMOVE_KEY"
        await query.edit_message_text("🗑️ Please send the **Gemini API Key** (or its prefix/suffix) you want to remove:")

    elif data == "prompt_show":
        config = load_config()
        prompt = config.get("prompt", DEFAULT_PROMPT)
        await query.edit_message_text(
            f"📝 **Current Prompt:**\n\n```\n{prompt[:3500]}\n```",
            reply_markup=build_prompt_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "prompt_edit":
        context.user_data["awaiting_input"] = "EDIT_PROMPT"
        await query.edit_message_text("✏️ Please send the **new extraction prompt** text:")

    elif data == "admin_show":
        if not is_owner(user_id):
            return
        config = load_config()
        admins = config.get("admins", [])
        msg = f"👑 Owner ID: `{OWNER_ID}`\n\n👥 **Admins ({len(admins)}):**\n"
        msg += "\n".join([f"• `{a}`" for a in admins]) if admins else "No additional admins."
        await query.edit_message_text(msg, reply_markup=build_admins_keyboard(), parse_mode=ParseMode.MARKDOWN)

    elif data == "admin_add":
        if not is_owner(user_id):
            return
        context.user_data["awaiting_input"] = "ADD_ADMIN"
        await query.edit_message_text("➕ Please send the numeric **Telegram User ID** of the new Admin:")

    elif data == "admin_remove":
        if not is_owner(user_id):
            return
        context.user_data["awaiting_input"] = "REMOVE_ADMIN"
        await query.edit_message_text("➖ Please send the numeric **Telegram User ID** to remove:")


async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    state = context.user_data.get("awaiting_input")

    if not user or not state or not is_authorized(user.id):
        return

    text = update.effective_message.text.strip()
    config = load_config()

    if state == "ADD_KEY":
        if text in config["api_keys"]:
            await update.effective_message.reply_text("⚠️ Key already exists!")
        else:
            config["api_keys"].append(text)
            save_config(config)
            await update.effective_message.reply_text("✅ **API Key added successfully!**", parse_mode=ParseMode.MARKDOWN)

    elif state == "REMOVE_KEY":
        keys = config["api_keys"]
        matched = [k for k in keys if text in k]
        if matched:
            for m in matched:
                keys.remove(m)
            config["api_keys"] = keys
            save_config(config)
            await update.effective_message.reply_text(f"✅ **Removed {len(matched)} key(s)!**", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.effective_message.reply_text("❌ Key not found.")

    elif state == "EDIT_PROMPT":
        config["prompt"] = text
        save_config(config)
        await update.effective_message.reply_text("✅ **Prompt updated successfully!**", parse_mode=ParseMode.MARKDOWN)

    elif state == "ADD_ADMIN":
        if not is_owner(user.id):
            return
        if not text.isdigit():
            await update.effective_message.reply_text("❌ Invalid ID. Send numeric Telegram ID.")
            return
        admin_id = int(text)
        if admin_id in config["admins"]:
            await update.effective_message.reply_text("⚠️ User is already an admin.")
        else:
            config["admins"].append(admin_id)
            save_config(config)
            await update.effective_message.reply_text(f"✅ Added Admin: `{admin_id}`", parse_mode=ParseMode.MARKDOWN)

    elif state == "REMOVE_ADMIN":
        if not is_owner(user.id):
            return
        if not text.isdigit():
            await update.effective_message.reply_text("❌ Invalid ID. Send numeric Telegram ID.")
            return
        admin_id = int(text)
        if admin_id in config["admins"]:
            config["admins"].remove(admin_id)
            save_config(config)
            await update.effective_message.reply_text(f"✅ Removed Admin: `{admin_id}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.effective_message.reply_text("❌ Admin ID not found.")

    context.user_data["awaiting_input"] = None


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_authorized(user.id):
        return

    await update.effective_message.reply_text(
        "👋 **Welcome!**\n\n"
        "Send or forward any post here to reformat it into a single clean text post.\n"
        "Use /edit to manage API Keys, Prompts, and Admins.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    await update.effective_message.reply_text(f"Your Telegram User ID: `{user.id}`", parse_mode=ParseMode.MARKDOWN)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in .env")

    load_config()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))

    media_filter = (
        filters.PHOTO
        | filters.Document.IMAGE
        | (filters.TEXT & ~filters.COMMAND)
    )
    app.add_handler(MessageHandler(media_filter, process_post))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
