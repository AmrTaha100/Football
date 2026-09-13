import json
import os
import random
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# تحميل بيانات اللاعبين
with open("players.json", "r", encoding="utf-8") as f:
    PLAYERS = json.load(f)

# حفظ حالة كل مستخدم: {user_id: {"player": {...}, "hint_index": 0}}
games = {}


def get_game_markup():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💡 تلميح إضافي", callback_data="next_hint"),
        InlineKeyboardButton("🏳️ استسلام", callback_data="give_up"),
    )
    markup.row(InlineKeyboardButton("🔄 لاعب جديد", callback_data="new_game"))
    return markup


@bot.message_handler(commands=["start", "play"])
def start_game(message):
    user_id = message.chat.id
    player = random.choice(PLAYERS)
    games[user_id] = {"player": player, "hint_index": 0}

    text = (
        f"⚽ <b>لعبة خمّن اللاعب!</b>\n\n"
        f"<b>التلميح الأول:</b>\n{player['hints'][0]}\n\n"
        f"اكتب اسم اللاعب في رسالة أو اطلب تلميحاً إضافياً 👇"
    )
    bot.send_message(
        user_id, text, parse_mode="HTML", reply_markup=get_game_markup()
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.message.chat.id
    if user_id not in games:
        bot.answer_callback_query(
            call.id, "ابدأ لعبة جديدة بكتابة /play", show_alert=True
        )
        return

    game = games[user_id]
    player = game["player"]

    if call.data == "next_hint":
        game["hint_index"] += 1
        if game["hint_index"] < len(player["hints"]):
            hint = player["hints"][game["hint_index"]]
            bot.send_message(user_id, f"💡 <b>تلميح:</b>\n{hint}", parse_mode="HTML")
        else:
            bot.send_message(
                user_id, "⚠️ لا توجد تلميحات أخرى! حاول التخمين الآن."
            )
        bot.answer_callback_query(call.id)

    elif call.data == "give_up":
        bot.send_message(
            user_id,
            f"اللاعب كان: <b>{player['name']}</b> 😅\nأرسل /play للعب مجدداً.",
            parse_mode="HTML",
        )
        del games[user_id]
        bot.answer_callback_query(call.id)

    elif call.data == "new_game":
        bot.answer_callback_query(call.id)
        start_game(call.message)


@bot.message_handler(func=lambda msg: True)
def check_guess(message):
    user_id = message.chat.id
    if user_id not in games:
        bot.reply_to(message, "اكتب /play لبدء اللعبة!")
        return

    user_guess = message.text.strip().lower()
    player = games[user_id]["player"]

    # فحص الاسم الرسمي والأسماء البديلة
    valid_names = [player["name"].lower()] + [
        a.lower() for a in player.get("aliases", [])
    ]

    if any(alias in user_guess for alias in valid_names):
        hints_used = games[user_id]["hint_index"] + 1
        response_text = (
            f"🎉 <b>إجابة صحيحة!</b> هو بالفعل <b>{player['name']}</b>!\n"
            f"عرفته بعد <b>{hints_used}</b> تلميح.\n\n"
            f"اكتب /play للعب جولة جديدة ⚽"
        )
        bot.reply_to(message, response_text, parse_mode="HTML")
        del games[user_id]
    else:
        bot.reply_to(message, "❌ إجابة خاطئة! حاول مرة أخرى أو اطلب تلميحاً.")


if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
