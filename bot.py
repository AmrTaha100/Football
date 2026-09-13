import json
import os
import random
import re
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# تحميل قائمة اللاعبين
with open("players.json", "r", encoding="utf-8") as f:
    PLAYERS = json.load(f)

SCORES_FILE = "scores.json"

# تحميل بيانات النقاط أو إنشاء ملف جديد
if os.path.exists(SCORES_FILE):
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            scores = json.load(f)
    except Exception:
        scores = {}
else:
    scores = {}


def save_scores():
    """حفظ النتائج في ملف محلي لضمان بقائها."""
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)


# ألعاب الجلسة الحالية
games = {}


def normalize_arabic(text):
    """تنظيف وتوحيد الحروف العربية والمسافات لتفادي أخطاء الإملاء."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def get_game_markup():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💡 تلميح إضافي", callback_data="next_hint"),
        InlineKeyboardButton("🏳️ استسلام", callback_data="give_up"),
    )
    markup.row(InlineKeyboardButton("🔄 لاعب جديد", callback_data="new_game"))
    return markup


def get_next_game_markup():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("⚽ لاعب جديد", callback_data="new_game")
    )
    return markup


@bot.message_handler(commands=["start", "play"])
def start_game(message):
    user_id = str(message.chat.id)
    player = random.choice(PLAYERS)
    games[user_id] = {"player": player, "hint_index": 0}

    # تهيئة بيانات المستخدم إن لم تكن موجودة
    if user_id not in scores:
        user_name = message.from_user.first_name or "لاعب"
        scores[user_id] = {
            "name": user_name,
            "points": 0,
            "wins": 0,
            "streak": 0,
            "best_streak": 0,
        }
        save_scores()

    text = (
        f"⚽ <b>لعبة خمّن اللاعب!</b>\n\n"
        f"🎯 <b>التحدي الأول (3 نقاط ⭐):</b>\n"
        f"{player['hints'][0]}\n\n"
        f"خمن اسمه في رسالة أو اطلب تلميحاً إضافياً بالأسفل 👇"
    )
    bot.send_message(
        message.chat.id, text, parse_mode="HTML", reply_markup=get_game_markup()
    )


@bot.message_handler(commands=["stats"])
def show_stats(message):
    user_id = str(message.chat.id)
    if user_id not in scores:
        bot.reply_to(message, "لم تلعب أي جولة بعد! اكتب /play للبدء.")
        return

    data = scores[user_id]
    text = (
        f"📊 <b>إحصائياتك يا {data.get('name', 'بطل')}:</b>\n\n"
        f"⭐ <b>مجموع النقاط:</b> {data.get('points', 0)}\n"
        f"🏆 <b>عدد مرات الفوز:</b> {data.get('wins', 0)}\n"
        f"🔥 <b>السلسلة الحالية (Streak):</b> {data.get('streak', 0)}\n"
        f"⚡ <b>أعلى سلسلة حققتها:</b> {data.get('best_streak', 0)}"
    )
    bot.reply_to(message, text, parse_mode="HTML")


@bot.message_handler(commands=["top"])
def show_leaderboard(message):
    if not scores:
        bot.reply_to(message, "لا توجد نتائج مسجلة حتى الآن!")
        return

    sorted_players = sorted(
        scores.values(), key=lambda x: x.get("points", 0), reverse=True
    )[:5]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    text = "🏆 <b>لوحة المتصدرين:</b>\n\n"

    for i, p in enumerate(sorted_players):
        medal = medals[i] if i < len(medals) else "▫️"
        text += f"{medal} <b>{p.get('name', 'لاعب')}</b>: {p.get('points', 0)} نقطة ({p.get('wins', 0)} فوز)\n"

    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = str(call.message.chat.id)

    if call.data == "new_game":
        bot.answer_callback_query(call.id)
        start_game(call.message)
        return

    if user_id not in games:
        bot.answer_callback_query(
            call.id, "الجولة انتهت، اضغط لاعب جديد بالأسفل.", show_alert=True
        )
        return

    game = games[user_id]
    player = game["player"]

    if call.data == "next_hint":
        game["hint_index"] += 1
        points_map = {1: "نقطتان ⭐⭐", 2: "نقطة واحدة ⭐"}

        if game["hint_index"] < len(player["hints"]):
            hint = player["hints"][game["hint_index"]]
            pts_label = points_map.get(game["hint_index"], "")
            bot.send_message(
                int(user_id),
                f"💡 <b>تلميح إضافي ({pts_label}):</b>\n{hint}",
                parse_mode="HTML",
            )
        else:
            bot.send_message(
                int(user_id), "⚠️ استنفدت جميع التلميحات! خمن الآن."
            )
        bot.answer_callback_query(call.id)

    elif call.data == "give_up":
        if user_id in scores:
            scores[user_id]["streak"] = 0
            save_scores()

        bot.send_message(
            int(user_id),
            f"اللاعب كان: <b>{player['name']}</b> 😅\nانقطعت سلسلة الانتصارات!\nاضغط بالأسفل لجولة جديدة 👇",
            parse_mode="HTML",
            reply_markup=get_next_game_markup(),
        )
        del games[user_id]
        bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda msg: True)
def check_guess(message):
    user_id = str(message.chat.id)
    if user_id not in games:
        bot.reply_to(
            message,
            "لا توجد جولة نشطة حالياً! اضغط بالأسفل للبدء 👇",
            reply_markup=get_next_game_markup(),
        )
        return

    raw_guess = message.text
    user_guess = normalize_arabic(raw_guess)
    player = games[user_id]["player"]

    full_name = normalize_arabic(player["name"])
    name_parts = full_name.split()
    aliases = [normalize_arabic(a) for a in player.get("aliases", [])]
    valid_names = set([full_name] + aliases + name_parts)

    is_correct = False
    if len(user_guess) >= 3:
        for valid in valid_names:
            if user_guess in valid or valid in user_guess:
                is_correct = True
                break

    if is_correct:
        hints_used = games[user_id]["hint_index"] + 1
        earned_points = 4 - hints_used
        if earned_points < 1:
            earned_points = 1

        if user_id not in scores:
            scores[user_id] = {
                "name": message.from_user.first_name or "لاعب",
                "points": 0,
                "wins": 0,
                "streak": 0,
                "best_streak": 0,
            }

        user_data = scores[user_id]
        user_data["name"] = message.from_user.first_name or user_data.get(
            "name", "لاعب"
        )
        user_data["points"] += earned_points
        user_data["wins"] += 1
        user_data["streak"] += 1
        if user_data["streak"] > user_data.get("best_streak", 0):
            user_data["best_streak"] = user_data["streak"]

        save_scores()

        streak_text = (
            f"\n🔥 <b>السلسلة الحالية:</b> {user_data['streak']} فوز متتالي!"
            if user_data["streak"] > 1
            else ""
        )
        response_text = (
            f"🎉 <b>إجابة صحيحة وممتازة!</b>\n"
            f"اللاعب هو بالفعل <b>{player['name']}</b>\n\n"
            f"⭐ <b>النقاط المكتسبة:</b> +{earned_points}\n"
            f"📊 <b>إجمالي نقاطك:</b> {user_data['points']}{streak_text}\n\n"
            f"اضغط على الزر بالأسفل لجولة جديدة مباشرة 👇"
        )
        bot.reply_to(
            message,
            response_text,
            parse_mode="HTML",
            reply_markup=get_next_game_markup(),
        )
        del games[user_id]
    else:
        bot.reply_to(message, "❌ إجابة خاطئة! حاول مجدداً أو اطلب تلميحاً.")


if __name__ == "__main__":
    print("Bot is running with enhanced hints...")
    bot.infinity_polling()
