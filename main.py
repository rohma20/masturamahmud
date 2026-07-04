import asyncio
import sqlite3
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, ChatMemberUpdatedFilter
from aiogram.filters.chat_member_updated import JOIN_TRANSITION
from aiogram.utils.deep_linking import create_start_link, decode_payload
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated

# Токен берется из переменных ocean_environment
API_TOKEN = os.getenv("BOT_TOKEN")

# API_TOKEN = "8602948149:AAFfDfqPqCQR4c7JX6uVqxHqepiudWUa8Do"

CHANNEL_ID = -1002973042972
MAIN_CHANNEL_LINK = "https://t.me/+yKejphFq__MwOGUy"
MARAFON_GROUP_LINK = "https://t.me/+gVFz9nv8h1NlNjIy"

REQUIRED_INVITES = 5

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
def init_db():
    conn = sqlite3.connect("referrals.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        referrer_id INTEGER,
        invited_count INTEGER DEFAULT 0,
        is_counted INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

# ОБРАБОТЧИК КОМАНДЫ /START
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    referrer_id = None

    # Парсим реферальный токен из ссылки
    if len(args) > 1:
        try:
            payload = decode_payload(args[1])
            if payload.isdigit():
                referrer_id = int(payload)
        except:
            if args[1].isdigit():
                referrer_id = int(args[1])

    conn = sqlite3.connect("referrals.db")
    cur = conn.cursor()

    # Проверяем, есть ли уже юзер в базе
    cur.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
    user = cur.fetchone()

    if not user:
        # Защита от самореферальной ссылки
        if referrer_id == user_id:
            referrer_id = None
        cur.execute(
            "INSERT INTO users (user_id, referrer_id) VALUES (?,?)",
            (user_id, referrer_id)
        )
    else:
        old_ref = user[0]
        # Если юзер зашел раньше сам, но теперь перешел по ссылке и у него нет реферера — обновляем
        if old_ref is None and referrer_id and referrer_id != user_id:
            cur.execute(
                "UPDATE users SET referrer_id=? WHERE user_id=?",
                (referrer_id, user_id)
            )

    conn.commit()
    conn.close()

    # Генерируем уникальную ссылку для пользователя
    link = await create_start_link(bot, str(user_id), encode=True)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=MAIN_CHANNEL_LINK)],
            [InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=f"https://t.me/share/url?url={link}&text=Kitob marafoniga qo'shiling!")],
            [InlineKeyboardButton(text="✅ Natijani tekshirish", callback_data="check")]
        ]
    )

    # Заменили ** на * для стандартного Markdown Телеграма
    text = f"""
✨ *Kitobxon qizlar jamoasi* bilan birgalikda kunlik mutolaa qilib, kitobxonlik ko‘nikmasini shakllantirish-chi?

📖 Unda sizni birgalikda ko‘plab kitoblarni o‘qib, oxirida o‘sha kitoblar bo‘yicha *testlar*, *sertifikatlar* va *sovg‘alarni* qo‘lga kiritadigan *Kitobxon qizlar jamoasiga taklif qilamiz!* 🎀

🚀 *Jamoaga qo‘shilishga tayyormisiz?*

Unda quyidagi havolani do‘stlaringizga yuboring va *5 ta do‘stingizni taklif qiling* 👇

🔗 `{link}`

🎁 5 ta do‘stingiz kanalga qo‘shilgach sizга *maxsus guruh havolasi* beriladi!

📚 Aytgancha, bu kanalda *bepul arab tili darslari ham bor.*
"""

    # Добавлен параметр parse_mode="Markdown" чтобы работал жирный текст и код
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# ОТСЛЕЖИВАНИЕ ВХОДА В КАНАЛ
@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def user_join(event: ChatMemberUpdated):
    if event.chat.id != CHANNEL_ID:
        return

    user_id = event.new_chat_member.user.id

    conn = sqlite3.connect("referrals.db")
    cur = conn.cursor()

    cur.execute("SELECT referrer_id, is_counted FROM users WHERE user_id=?", (user_id,))
    data = cur.fetchone()

    if data:
        referrer_id, counted = data

        # Засчитываем инвайт, только если этот пользователь еще не был посчитан
        if referrer_id and counted == 0:
            cur.execute(
                "UPDATE users SET invited_count = invited_count + 1 WHERE user_id=?",
                (referrer_id,)
            )
            cur.execute(
                "UPDATE users SET is_counted = 1 WHERE user_id=?",
                (user_id,)
            )
            conn.commit()

            try:
                # Отправляем уведомление пригласителю
                await bot.send_message(
                    referrer_id,
                    "🎉 Sizning havolangiz orqali yangi a'zo kanalga qo'shildi! +1"
                )
            except Exception:
                pass

    conn.close()

# ОБРАБОТКА КНОПКИ ПРОВЕРКИ
@dp.callback_query(F.data == "check")
async def check(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    conn = sqlite3.connect("referrals.db")
    cur = conn.cursor()
    cur.execute("SELECT invited_count FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    count = row[0] if row else 0
    conn.close()

    if count >= REQUIRED_INVITES:
        await callback.message.answer(
            f"🎉 Tabriklayman! Vazifa bajarildi.\n\nMana guruh havolasi:\n{MARAFON_GROUP_LINK}"
        )
    else:
        # Всплывающее окошко-уведомление в Telegram
        await callback.answer(
            f"Siz hali etarlicha odam taklif qilmadingiz. Takliflar: {count}/{REQUIRED_INVITES}",
            show_alert=True
        )

# КОМАНДА /STATS
@dp.message(Command("stats"))
async def stats(message: types.Message):
    user_id = message.from_user.id

    conn = sqlite3.connect("referrals.db")
    cur = conn.cursor()
    cur.execute("SELECT invited_count FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    count = row[0] if row else 0
    conn.close()

    await message.answer(f"📊 Siz jami {count} ta odam taklif qildingiz.")

async def main():
    init_db()
    print("Бот успешно запущен...")
    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query", "chat_member"]
    )

if __name__ == "__main__":
    asyncio.run(main())