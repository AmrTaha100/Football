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

# تحميل بيانات النقاط
if os.path.exists(SCORES_FILE):
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            scores = json.load(f)
    except Exception:
        scores = {}
else:
    scores = {}


def save_scores():
    """حفظ دائم للنقاط والإحصائيات."""
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)


# ألعاب الجلسات الحالية: chat_id -> game_state
games = {}


def normalize_arabic(text):
    """تنظيف وتوحيد الأحرف العربية والهمزات."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def get_rank(points):
    """تحديد الرتبة الكروية حسب النقاط."""
    if points >= 100:
        return "أسطورة كرة القدم 👑"
    if points >= 60:
        return "نجم عالمي 🌟"
    if points >= 30:
        return "لاعب محترف ⚽"
    if points >= 10:
        return "موهبة صاعدة ⚡"
    return "لاعب هاوٍ 🥉"


def get_game_markup():
    """لوحة أزرار التفاعل أثناء الجولة."""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💡 تلميح إضافي", callback_data="next_hint"),
        InlineKeyboardButton("🔤 أول حرف", callback_data="reveal_letter"),
    )
    markup.row(
        InlineKeyboardButton("🏳️ استسلام", callback_data="give_up"),
        InlineKeyboardButton("🔄 لاعب جديد", callback_data="new_game"),
    )
    return markup


def get_next_game_markup():
    """زر سريع لبدء جولة جديدة فوراً."""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("⚽ لاعب جديد", callback_data="new_game")
    )
    return markup


def pick_player_for_user(user_id):
    """اختيار لاعب لم يظهر للمستخدم مؤخراً لمنع التكرار."""
    played = scores.get(user_id, {}).get("played_players", [])
    available = [p for p in PLAYERS if p["name"] not in played]

    # إذا أنهى اللاعب جميع الأسئلة، نعيد تصفير السجل
    if not available:
        available = PLAYERS
        if user_id in scores:
            scores[user_id]["played_players"] = []
            save_scores()

    return random.choice(available)


@bot.message_handler(commands=["start", "play"])
def start_game(message):
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)

    # تهيئة بيانات اللاعب في الإحصائيات
    if user_id not in scores:
        scores[user_id] = {
            "name": message.from_user.first_name or "لاعب",
            "points": 0,
            "wins": 0,
            "streak": 0,
            "best_streak": 0,
            "played_players": [],
        }
        save_scores()

    player = pick_player_for_user(user_id)

    # تسجيل حالة الجولة
    games[chat_id] = {
        "player": player,
        "hint_index": 0,
        "attempts_left": 3,
        "letter_revealed": False,
    }

    text = (
        f"⚽ <b>لعبة خمّن اللاعب!</b>\n"
        f"❤️ <b>المحاولات:</b> 3 فرَص\n\n"
        f"🎯 <b>التحدي الأول (3 نقاط ⭐):</b>\n"
        f"{player['hints'][0]}\n\n"
        f"اكتب اسم اللاعب في رسالة أو اطلب تلميحاً من الأزرار 👇"
    )
    bot.send_message(
        message.chat.id, text, parse_mode="HTML", reply_markup=get_game_markup()
    )


@bot.message_handler(commands=["stats"])
def show_stats(message):
    user_id = str(message.from_user.id)
    if user_id not in scores:
        bot.reply_to(message, "لم تلعب أي جولة بعد! اكتب /play للبدء.")
        return

    data = scores[user_id]
    rank = get_rank(data.get("points", 0))
    text = (
        f"📊 <b>إحصائيات الكابتن {data.get('name', 'بطل')}:</b>\n\n"
        f"🎖️ <b>الرتبة:</b> {rank}\n"
        f"⭐ <b>مجموع النقاط:</b> {data.get('points', 0)}\n"
        f"🏆 <b>عدد مرات الفوز:</b> {data.get('wins', 0)}\n"
        f"🔥 <b>السلسلة الحالية (Streak):</b> {data.get('streak', 0)}\n"
        f"⚡ <b>أعلى سلسلة حققتها:</b> {data.get('best_streak', 0)}"
    )
    bot.reply_to(message, text, parse_mode="HTML")


@bot.message_handler(commands=["top"])
def show_leaderboard(message):
    if not scores:
        bot.reply_to(message, "لا توجد نتائج مسجلة بعد!")
        return

    sorted_players = sorted(
        scores.values(), key=lambda x: x.get("points", 0), reverse=True
    )[:5]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    text = "🏆 <b>لوحة أساطير اللعبة:</b>\n\n"

    for i, p in enumerate(sorted_players):
        medal = medals[i] if i < len(medals) else "▫️"
        rank = get_rank(p.get("points", 0))
        text += (
            f"{medal} <b>{p.get('name', 'لاعب')}</b>: {p.get('points', 0)} نقطة\n"
            f"   └ <i>{rank}</i> ({p.get('wins', 0)} فوز)\n"
        )

    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = str(call.message.chat.id)
    user_id = str(call.from_user.id)

    if call.data == "new_game":
        bot.answer_callback_query(call.id)
        start_game(call.message)
        return

    if chat_id not in games:
        bot.answer_callback_query(
            call.id, "الجولة انتهت، اضغط لاعب جديد بالأسفل.", show_alert=True
        )
        return

    game = games[chat_id]
    player = game["player"]

    if call.data == "next_hint":
        game["hint_index"] += 1
        points_map = {1: "نقطتان ⭐⭐", 2: "نقطة واحدة ⭐"}

        if game["hint_index"] < len(player["hints"]):
            hint = player["hints"][game["hint_index"]]
            pts_label = points_map.get(game["hint_index"], "")
            bot.send_message(
                call.message.chat.id,
                f"💡 <b>تلميح إضافي ({pts_label}):</b>\n{hint}",
                parse_mode="HTML",
            )
        else:
            bot.send_message(
                call.message.chat.id, "⚠️ استنفدت جميع التلميحات! حاول التخمين الآن."
            )
        bot.answer_callback_query(call.id)

    elif call.data == "reveal_letter":
        if game.get("letter_revealed"):
            bot.answer_callback_query(
                call.id, "تم كشف الحرف الأول بالفعل!", show_alert=True
            )
            return

        game["letter_revealed"] = True
        first_letter = player["name"].strip()[0]
        bot.send_message(
            call.message.chat.id,
            f"🔤 <b>مساعدة سريعة:</b> يبدأ اسم اللاعب بحرف: ( <b>{first_letter}</b> )",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    elif call.data == "give_up":
        if user_id in scores:
            scores[user_id]["streak"] = 0
            save_scores()

        bot.send_message(
            call.message.chat.id,
            f"اللاعب كان: <b>{player['name']}</b> 😅\nانقطعت سلسلة الانتصارات!\nاضغط بالأسفل لجولة جديدة 👇",
            parse_mode="HTML",
            reply_markup=get_next_game_markup(),
        )
        del games[chat_id]
        bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda msg: True)
def check_guess(message):
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)

    if chat_id not in games:
        bot.reply_to(
            message,
            "لا توجد جولة نشطة حالياً! اضغط بالأسفل للبدء 👇",
            reply_markup=get_next_game_markup(),
        )
        return

    game = games[chat_id]
    player = game["player"]

    user_guess = normalize_arabic(message.text)
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
        hints_used = game["hint_index"] + 1
        earned_points = 4 - hints_used

        # خصم نقطة إذا استعان بكشف الحرف الأول
        if game.get("letter_revealed"):
            earned_points -= 1

        if earned_points < 1:
            earned_points = 1

        # تسجيل وتحديث ملف اللاعب
        if user_id not in scores:
            scores[user_id] = {
                "name": message.from_user.first_name or "لاعب",
                "points": 0,
                "wins": 0,
                "streak": 0,
                "best_streak": 0,
                "played_players": [],
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

        if "played_players" not in user_data:
            user_data["played_players"] = []
        user_data["played_players"].append(player["name"])

        save_scores()

        current_rank = get_rank(user_data["points"])
        streak_text = (
            f"\n🔥 <b>السلسلة الحالية:</b> {user_data['streak']} فوز متتالي!"
            if user_data["streak"] > 1
            else ""
        )

        response_text = (
            f"🎉 <b>إجابة صحيحة يا {message.from_user.first_name}!</b>\n"
            f"اللاعب هو بالفعل <b>{player['name']}</b> 👏\n\n"
            f"⭐ <b>النقاط المكتسبة:</b> +{earned_points}\n"
            f"📊 <b>رصيدك:</b> {user_data['points']} نقطة | <i>{current_rank}</i>"
            f"{streak_text}\n\n"
            f"اضغط بالأسفل لجولة جديدة مباشرة 👇"
        )
        bot.reply_to(
            message,
            response_text,
            parse_mode="HTML",
            reply_markup=get_next_game_markup(),
        )
        del games[chat_id]

    else:
        # تقليل عدد المحاولات المتبقية
        game["attempts_left"] -= 1

        if game["attempts_left"] > 0:
            hearts = "❤️" * game["attempts_left"]
            bot.reply_to(
                message,
                f"❌ <b>إجابة خاطئة!</b>\nالمحاولات المتبقية: {hearts} ({game['attempts_left']})\nحاول مجدداً أو اطلب تلميحاً.",
                parse_mode="HTML",
            )
        else:
            if user_id in scores:
                scores[user_id]["streak"] = 0
                save_scores()

            bot.reply_to(
                message,
                f"💀 <b>انتهت جميع محاولاتك!</b>\n"
                f"اللاعب كان: <b>{player['name']}</b> 💔\n\n"
                f"اضغط على الزر بالأسفل لتحدي جديد 👇",
                parse_mode="HTML",
                reply_markup=get_next_game_markup(),
            )
            del games[chat_id]


if __name__ == "__main__":
    print("Bot is fully upgraded and running...")
    bot.infinity_polling()
