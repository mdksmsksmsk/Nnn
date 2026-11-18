
import asyncio
import logging
import os
import sqlite3

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

# ==============================
# AYARLAR
# ==============================

TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

CHANNELS = [
    "@swarovskiyeniden",
    "@swarovskihile",
    "@hilemfk",
]

FILE_CHANNEL = "@hilemfk"
DB_NAME = os.getenv("DB_PATH", "swarovski.db")

router = Router()


# ==============================
# VERİTABANI
# ==============================

def db():
    return sqlite3.connect(DB_NAME, timeout=30)


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                referrer_id INTEGER,
                referrals INTEGER DEFAULT 0,
                referral_counted INTEGER DEFAULT 0
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                name TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)

        con.execute("""
            INSERT OR IGNORE INTO stats(name, value)
            VALUES('commands', 0)
        """)


def register_user(user_id, username, referrer=None):
    if referrer == user_id:
        referrer = None

    with db() as con:
        con.execute("""
            INSERT OR IGNORE INTO users
            (user_id, username, referrer_id)
            VALUES (?, ?, ?)
        """, (user_id, username, referrer))


def add_command():
    with db() as con:
        con.execute("""
            UPDATE stats
            SET value = value + 1
            WHERE name = 'commands'
        """)


def get_referrals(user_id):
    with db() as con:
        row = con.execute(
            "SELECT referrals FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

    return row[0] if row else 0


def credit_referral(user_id):
    with db() as con:
        row = con.execute("""
            SELECT referrer_id, referral_counted
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if not row:
            return False

        referrer_id, counted = row

        if not referrer_id or counted:
            return False

        if referrer_id == user_id:
            return False

        cursor = con.execute("""
            UPDATE users
            SET referral_counted = 1
            WHERE user_id = ?
            AND referral_counted = 0
            AND referrer_id IS NOT NULL
        """, (user_id,))

        if cursor.rowcount != 1:
            return False

        con.execute("""
            UPDATE users
            SET referrals = referrals + 1
            WHERE user_id = ?
        """, (referrer_id,))

        return True


# ==============================
# ÜYELİK KONTROLÜ
# ==============================

async def check_subscriptions(bot, user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(
                chat_id=channel,
                user_id=user_id
            )

            if member.status in ("left", "kicked"):
                return False

            if member.status == "restricted" and not member.is_member:
                return False

        except Exception:
            logging.exception(
                "Üyelik kontrolü başarısız: %s", channel
            )
            return False

    return True


def subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 1. Kanal",
            url="https://t.me/swarovskiyeniden"
        )],
        [InlineKeyboardButton(
            text="📢 2. Kanal",
            url="https://t.me/swarovskihile"
        )],
        [InlineKeyboardButton(
            text="📢 3. Kanal",
            url="https://t.me/hilemfk"
        )],
        [InlineKeyboardButton(
            text="✅ Katıldım, Kontrol Et",
            callback_data="check_sub"
        )],
    ])


# ==============================
# MENÜLER
# ==============================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚡ Standoff 2 Rootlu Sürüm",
            callback_data="file_3"
        )],
        [
            InlineKeyboardButton(
                text="📂 Ekstra Dosya 1",
                callback_data="file_5"
            ),
            InlineKeyboardButton(
                text="📂 Ekstra Dosya 2",
                callback_data="file_6"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📂 Ekstra Dosya 3",
                callback_data="file_7"
            ),
            InlineKeyboardButton(
                text="📂 Ekstra Dosya 4",
                callback_data="file_8"
            ),
        ],
        [InlineKeyboardButton(
            text="🛠️ Root Uygulamaları",
            callback_data="root_apps"
        )],
        [InlineKeyboardButton(
            text="🔥 Neptunium",
            callback_data="file_116"
        )],
        [InlineKeyboardButton(
            text="⭐ Brawl Stars",
            callback_data="file_117"
        )],
        [InlineKeyboardButton(
            text="💎 Exodium",
            callback_data="file_118"
        )],
        [InlineKeyboardButton(
            text="🎯 LEGIT Oyun Taktikleri",
            callback_data="legit"
        )],
        [InlineKeyboardButton(
            text="🎮 Eğlence Menüsü",
            callback_data="fun_menu"
        )],
        [InlineKeyboardButton(
            text="👥 Davet Et & Kazan",
            callback_data="ref_menu"
        )],
        [InlineKeyboardButton(
            text="🔐 Admin Paneli",
            callback_data="admin_panel"
        )],
    ])


def back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Ana Menü",
            callback_data="back_to_menu"
        )]
    ])


def referral_gate_keyboard(link):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👥 Arkadaşını Davet Et",
            url=link
        )],
        [InlineKeyboardButton(
            text="🔄 Davetimi Kontrol Et",
            callback_data="refresh_ref"
        )],
        [InlineKeyboardButton(
            text="📢 Kanalları Kontrol Et",
            callback_data="check_sub"
        )],
    ])


# ==============================
# ERİŞİM KONTROLÜ
# ==============================

async def show_subscription(message):
    await message.answer(
        "⚠️ **KANALLARA KATILMAN GEREKİYOR!**\n\n"
        "Botu kullanabilmek için üç kanalımıza da katılmalısın.",
        reply_markup=subscribe_keyboard(),
        parse_mode="Markdown"
    )


async def show_referral_gate(message, bot, user_id):
    info = await bot.get_me()
    link = f"https://t.me/{info.username}?start=ref_{user_id}"

    await message.answer(
        "👥 **DAVET ŞARTI**\n\n"
        "Kanallarımıza katıldın! Şimdi botun diğer özelliklerini "
        "açmak için 1 arkadaşını davet etmelisin.\n\n"
        f"Başarılı davetlerin: {get_referrals(user_id)}/1\n\n"
        "Arkadaşın davet bağlantından gelip üç kanalımıza katılmalı.",
        reply_markup=referral_gate_keyboard(link),
        parse_mode="Markdown"
    )


async def has_access(bot, user_id):
    if not await check_subscriptions(bot, user_id):
        return False

    return get_referrals(user_id) >= 1


async def require_access(callback, bot):
    user_id = callback.from_user.id

    if not await check_subscriptions(bot, user_id):
        await callback.answer(
            "❌ Kanallardan ayrılmışsın! Tekrar katıl.",
            show_alert=True
        )
        await callback.message.answer(
            "⚠️ **Üyeliğin eksik!**",
            reply_markup=subscribe_keyboard(),
            parse_mode="Markdown"
        )
        return False

    if get_referrals(user_id) < 1:
        await callback.answer(
            "❌ Önce 1 arkadaşını davet etmelisin.",
            show_alert=True
        )
        await show_referral_gate(callback.message, bot, user_id)
        return False

    return True


# ==============================
# START
# ==============================

@router.message(Command("start", "menu"))
async def start(message: Message, bot: Bot):
    user = message.from_user

    if not user:
        return

    args = (message.text or "").split()
    referrer = None

    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer = int(args[1][4:])
        except ValueError:
            referrer = None

    register_user(user.id, user.username, referrer)
    add_command()

    if not await check_subscriptions(bot, user.id):
        await show_subscription(message)
        return

    credit_referral(user.id)

    if get_referrals(user.id) < 1:
        await show_referral_gate(message, bot, user.id)
        return

    await message.answer(
        "🔥 **SWAROVSKI VIP ARŞİVİNE HOŞ GELDİN!**\n\n"
        "İstediğin kategoriyi aşağıdan seçebilirsin.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


# ==============================
# ÜYELİK KONTROL BUTONU
# ==============================

@router.callback_query(F.data == "check_sub")
async def check_sub_button(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    if not await check_subscriptions(bot, user_id):
        await callback.answer(
            "❌ Üç kanalın tamamına katılmalısın!",
            show_alert=True
        )
        return

    credit_referral(user_id)
    await callback.answer("✅ Kanal üyeliğin onaylandı!")

    if get_referrals(user_id) < 1:
        await show_referral_gate(callback.message, bot, user_id)
    else:
        await callback.message.answer(
            "🎉 **Tüm şartlar tamamlandı!**",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )


@router.callback_query(F.data == "refresh_ref")
async def refresh_ref(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    if not await check_subscriptions(bot, user_id):
        await callback.answer(
            "Önce üç kanala katılmalısın.",
            show_alert=True
        )
        return

    credit_referral(user_id)

    if get_referrals(user_id) >= 1:
        await callback.answer(
            "🎉 Davet şartın tamamlandı!",
            show_alert=True
        )
        await callback.message.answer(
            "🔥 **VIP MENÜ AÇILDI!**",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
    else:
        await callback.answer(
            "Henüz başarılı bir davetin yok.",
            show_alert=True
        )


# ==============================
# REFERANS MENÜSÜ
# ==============================

@router.callback_query(F.data == "ref_menu")
async def ref_menu(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    if not await check_subscriptions(bot, user_id):
        await callback.answer(
            "Önce kanallara katılmalısın.",
            show_alert=True
        )
        return

    info = await bot.get_me()
    link = f"https://t.me/{info.username}?start=ref_{user_id}"

    await callback.message.answer(
        "👥 **DAVET ET & KAZAN**\n\n"
        f"🔗 Davet bağlantın:\n`{link}`\n\n"
        f"🎯 Başarılı davet: {get_referrals(user_id)}\n\n"
        "Arkadaşın bağlantından gelip üç kanalımıza katılınca "
        "davetin sayılır.",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )

    await callback.answer()


# ==============================
# DOSYA GÖNDERME
# ==============================

FILES = {
    "file_3": 3,
    "file_5": 5,
    "file_6": 6,
    "file_7": 7,
    "file_8": 8,
    "file_116": 116,
    "file_117": 117,
    "file_118": 118,
}


@router.callback_query(F.data.in_(list(FILES.keys())))
async def send_file(callback: CallbackQuery, bot: Bot):
    if not await require_access(callback, bot):
        return

    message_id = FILES[callback.data]
    await callback.answer("📦 Dosya hazırlanıyor...")

    try:
        await bot.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=FILE_CHANNEL,
            message_id=message_id
        )
    except Exception:
        logging.exception("Dosya gönderilemedi")
        await callback.message.answer(
            "❌ Dosya gönderilemedi. Depo kanalındaki mesajı kontrol et."
        )


# ==============================
# LEGIT TAKTİKLER
# ==============================

@router.callback_query(F.data == "legit")
async def legit_menu(callback: CallbackQuery, bot: Bot):
    if not await require_access(callback, bot):
        return

    text = (
        "🎯 **STANDOFF 2 LEGIT TAKTİKLER**\n\n"
        "1️⃣ **Nişan:** Nişangâhını rakibin çıkabileceği kafa "
        "hizasında tut.\n\n"
        "2️⃣ **Hareket:** Gereksiz yere açık alanda koşma. "
        "Siperleri kullan.\n\n"
        "3️⃣ **Ses:** Rakibin ayak seslerini dinle ve acele karar verme.\n\n"
        "4️⃣ **Recoil:** Silahların geri tepmesini antrenman "
        "alanında öğren.\n\n"
        "5️⃣ **Harita:** Köşeleri ve geçiş noktalarını ezberle.\n\n"
        "6️⃣ **Takım:** Takım arkadaşlarınla aynı anda hareket et.\n\n"
        "7️⃣ **Ekonomi:** Oyun içi paranı takımın durumuna göre kullan.\n\n"
        "8️⃣ **Güvenlik:** Bilinmeyen APK ve dosyalara hesap "
        "bilgilerini verme.\n\n"
        "🏆 En iyi gelişim düzenli ve adil antrenmandır."
    )

    await callback.message.answer(
        text,
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==============================
# ROOT UYGULAMALARI
# ==============================

@router.callback_query(F.data == "root_apps")
async def root_apps(callback: CallbackQuery, bot: Bot):
    if not await require_access(callback, bot):
        return

    await callback.answer(
        "🛠️ Root uygulamaları yakında eklenecek!",
        show_alert=True
    )


# ==============================
# EĞLENCE
# ==============================

def fun_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎲 Zar At",
                callback_data="fun_dice"
            ),
            InlineKeyboardButton(
                text="🍀 Şans",
                callback_data="fun_luck"
            )
        ],
        [
            InlineKeyboardButton(
                text="🤖 Botun Sırrı",
                callback_data="fun_secret"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Ana Menü",
                callback_data="back_to_menu"
            )
        ]
    ])


@router.callback_query(F.data == "fun_menu")
async def fun_menu(callback: CallbackQuery, bot: Bot):
    if not await require_access(callback, bot):
        return

    await callback.message.answer(
        "🎮 **EĞLENCE MENÜSÜ**",
        reply_markup=fun_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "fun_dice")
async def fun_dice(callback: CallbackQuery, bot: Bot):
    if not await require_access(callback, bot):
        return

    await callback.answer("🎲 Zar atılıyor...")
    await bot.send_dice(callback.message.chat.id)


@router.callback_query(F.data == "fun_luck")
async def fun_luck(callback: CallbackQuery, bot: Bot):
    if not await require_access(callback, bot):
        return

    await callback.answer(
        "🍀 Bugün şans seninle olsun!",
        show_alert=True
    )


@router.callback_query(F.data == "fun_secret")
async def fun_secret(callback: CallbackQuery, bot: Bot):
    if not await require_access(callback, bot):
        return

    await callback.answer(
        "🤖 Swarovski ekibi tarafından geliştirildi!",
        show_alert=True
    )


# ==============================
# GERİ DÖNÜŞ
# ==============================

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    if not await has_access(bot, user_id):
        await callback.answer(
            "Erişim şartların eksik.",
            show_alert=True
        )

        if not await check_subscriptions(bot, user_id):
            await callback.message.answer(
                "⚠️ Kanallara tekrar katılmalısın.",
                reply_markup=subscribe_keyboard()
            )
        else:
            await show_referral_gate(
                callback.message, bot, user_id
            )
        return

    await callback.answer()
    await callback.message.answer(
        "🔥 **SWAROVSKI VIP ARŞİVİ**",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


# ==============================
# ADMIN PANELİ
# ==============================

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            "⛔ Bu alan yalnızca yöneticilere açık.",
            show_alert=True
        )
        return

    with db() as con:
        users = con.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        commands = con.execute(
            "SELECT value FROM stats WHERE name='commands'"
        ).fetchone()[0]

        referrals_total = con.execute(
            "SELECT SUM(referrals) FROM users"
        ).fetchone()[0] or 0

    await callback.message.answer(
        "👑 **SWAROVSKI ADMIN PANELİ**\n\n"
        f"👥 Toplam kullanıcı: `{users}`\n"
        f"💬 Toplam komut: `{commands}`\n"
        f"🔗 Başarılı davet: `{referrals_total}`\n"
        "🟢 Sistem: Çalışıyor",
        reply_markup=back_keyboard(),
        parse_mode="Markdown"
    )

    await callback.answer()


# ==============================
# ÜYELİK DEĞİŞİKLİĞİ BİLDİRİMİ
# ==============================

@router.chat_member()
async def membership_changed(
    event: ChatMemberUpdated,
    bot: Bot
):
    channel_username = event.chat.username

    if not channel_username:
        return

    channel = "@" + channel_username

    if channel not in CHANNELS:
        return

    new_status = event.new_chat_member.status

    if new_status not in ("left", "kicked"):
        return

    affected_user_id = event.new_chat_member.user.id

    try:
        await bot.send_message(
            affected_user_id,
            "⚠️ Zorunlu kanallarımızdan ayrıldığını gördük.\n\n"
            "Botu kullanmak için tekrar katılmalısın.",
            reply_markup=subscribe_keyboard()
        )
    except Exception:
        logging.info(
            "Üyelik bildirimi gönderilemedi: %s",
            affected_user_id
        )


# ==============================
# BAŞLAT
# ==============================

async def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN Render ortam değişkeninde eksik!"
        )

    init_db()

    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    logging.info("Swarovski VIP Bot başlatılıyor...")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
            
