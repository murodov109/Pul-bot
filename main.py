import time
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import desc
from sqlalchemy.orm import Session
from config import BOT_TOKEN, ADMIN_IDS, PROOF_CHANNEL_ID, MANDATORY_CHANNEL_IDS, DATABASE_URL, MIN_WITHDRAW, DAILY_WITHDRAW_LIMIT, BROADCAST_BATCH
from models import make_engine_session, User, WithdrawRequest, Referral, MandatoryChannel, BroadcastLog

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
engine, SessionLocal = make_engine_session(DATABASE_URL)

def get_session() -> Session:
    return SessionLocal()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def mask_target(value: str) -> str:
    s = value.strip()
    if len(s) <= 6:
        return "***"
    return f"{s[:4]}{'*'*(max(len(s)-6, 2))}{s[-2:]}"

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Hisobim"), KeyboardButton("Pul ishlash"))
    kb.add(KeyboardButton("Pul yechish"), KeyboardButton("Pul yechish so'rovlari"))
    kb.add(KeyboardButton("Admin bilan aloqa"), KeyboardButton("Isbotlar"))
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Statistika"), KeyboardButton("Majburiy obuna"))
    kb.add(KeyboardButton("Pul yechish so'rovlari (ADMIN)"))
    kb.add(KeyboardButton("Reklama tarqatish"), KeyboardButton("Balans boshqarish"))
    return kb

def ensure_user(user_id: int, username: str, first_name: str, last_name: str = None, ref_by: int = None):
    with get_session() as s:
        u = s.get(User, user_id)
        if not u:
            u = User(id=user_id, username=username, first_name=first_name, last_name=last_name, referred_by=ref_by)
            s.add(u)
            s.commit()
        else:
            u.username = username
            u.first_name = first_name
            u.last_name = last_name
            s.commit()
        return u

def check_mandatory_subs(user_id: int) -> bool:
    if not MANDATORY_CHANNEL_IDS:
        return True
    try:
        for ch_id in MANDATORY_CHANNEL_IDS:
            member = bot.get_chat_member(ch_id, user_id)
            if member.status in ["left", "kicked"]:
                return False
        return True
    except Exception:
        return False

def referral_bonus_amount() -> int:
    return 1000

def today_date_range():
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end

@bot.message_handler(commands=["start"])
def cmd_start(m):
    user = ensure_user(m.from_user.id, m.from_user.username, m.from_user.first_name, m.from_user.last_name)
    ref_by = None
    if m.text and " " in m.text:
        param = m.text.split(" ", 1)[1]
        if param.startswith("ref_"):
            try:
                ref_by = int(param.replace("ref_", "").strip())
            except ValueError:
                ref_by = None
    if ref_by and ref_by != m.from_user.id:
        with get_session() as s:
            u = s.get(User, m.from_user.id)
            if u and not u.referred_by:
                if check_mandatory_subs(m.from_user.id):
                    u.referred_by = ref_by
                    s.commit()
                    ref_user = s.get(User, ref_by)
                    if ref_user:
                        ref_user.balance += referral_bonus_amount()
                        s.add(Referral(referrer_id=ref_by, referred_id=m.from_user.id))
                        s.commit()
    if not check_mandatory_subs(m.from_user.id):
        kb = InlineKeyboardMarkup()
        for ch_id in MANDATORY_CHANNEL_IDS:
            chat = bot.get_chat(ch_id)
            kb.add(InlineKeyboardButton(text=f"Obuna: {chat.title}", url=f"https://t.me/{chat.username}" if chat.username else None))
        bot.send_message(m.chat.id, "Iltimos, kanallarga obuna bo‘ling va keyin /start buyrug‘ini qayta yuboring.", reply_markup=kb)
        return
    bot.send_message(m.chat.id, "Xush kelibsiz! Quyidagi menyudan foydalaning.", reply_markup=main_menu())
    if is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "Admin paneliga xush kelibsiz.", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "Hisobim")
def account(m):
    with get_session() as s:
        u = s.get(User, m.from_user.id)
        if not u:
            bot.reply_to(m, "Profil topilmadi. /start yuboring.")
            return
        ref_count = s.query(Referral).filter(Referral.referrer_id == u.id).count()
        bot.send_message(m.chat.id, f"Balans: <b>{u.balance}</b> so'm\nReferallar: {ref_count}", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "Pul ishlash")
def earn(m):
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{m.from_user.id}"
    bot.send_message(m.chat.id, f"Sizning referal havolangiz:\n<code>{ref_link}</code>")

@bot.message_handler(func=lambda m: m.text == "Isbotlar")
def proofs(m):
    if PROOF_CHANNEL_ID == 0:
        bot.send_message(m.chat.id, "Isbotlar kanali sozlanmagan.")
    else:
        chat = bot.get_chat(PROOF_CHANNEL_ID)
        if chat.username:
            bot.send_message(m.chat.id, f"Isbotlar kanali: https://t.me/{chat.username}")
        else:
            bot.send_message(m.chat.id, "Isbotlar kanali mavjud, lekin public havola yo‘q.")

user_states = {}

@bot.message_handler(func=lambda m: m.text == "Pul yechish")
def withdraw_start(m):
    with get_session() as s:
        u = s.get(User, m.from_user.id)
        if not u:
            bot.reply_to(m, "Profil topilmadi. /start yuboring.")
            return
        bot.send_message(m.chat.id, f"Balansingiz: {u.balance} so'm.\nMinimal yechish: {MIN_WITHDRAW} so'm.\nYechmoqchi bo‘lgan summani kiriting:")
        user_states[m.from_user.id] = {"stage": "amount"}

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("stage") == "amount")
def withdraw_amount(m):
    try:
        amount = int(m.text.strip())
    except ValueError:
        bot.reply_to(m, "Iltimos, summani butun son ko‘rinishida kiriting.")
        return
    if amount < MIN_WITHDRAW:
        bot.reply_to(m, f"Minimal yechish {MIN_WITHDRAW} so'm.")
        return
    with get_session() as s:
        u = s.get(User, m.from_user.id)
        if u.balance < amount:
            bot.reply_to(m, "Balans yetarli emas.")
            return
        if DAILY_WITHDRAW_LIMIT > 0:
            start, end = today_date_range()
            cnt = s.query(WithdrawRequest).filter(WithdrawRequest.user_id == u.id, WithdrawRequest.created_at >= start, WithdrawRequest.created_at < end).count()
            if cnt >= DAILY_WITHDRAW_LIMIT:
                bot.reply_to(m, "Bugungi yechish limitiga yetdingiz.")
                return
    user_states[m.from_user.id] = {"stage": "target", "amount": amount}
    bot.send_message(m.chat.id, "Karta yoki telefon raqamini yuboring (faqat raqam):")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("stage") == "target")
def withdraw_target(m):
    target = m.text.strip().replace(" ", "")
    if not target.isdigit() or len(target) < 9:
        bot.reply_to(m, "Raqam noto‘g‘ri. Iltimos, faqat raqam kiriting (karta yoki telefon).")
        return
    state = user_states[m.from_user.id]
    amount = state["amount"]
    with get_session() as s:
        u = s.get(User, m.from_user.id)
        if u.balance < amount:
            bot.reply_to(m, "Balans yetarli emas.")
            user_states.pop(m.from_user.id, None)
            return
        u.balance -= amount
        wr = WithdrawRequest(user_id=u.id, amount=amount, pay_target=target, status="pending")
        s.add(wr)
        s.commit()
        bot.send_message(m.chat.id, f"So‘rov yaratildi.\nMiqdor: {amount} so'm\nRekvizit: {mask_target(target)}\nHolat: kutilmoqda")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Tasdiqlash", callback_data=f"wd_ok_{wr.id}"), InlineKeyboardButton("Bekor qilish", callback_data=f"wd_no_{wr.id}"))
        for admin_id in ADMIN_IDS:
            bot.send_message(admin_id, f"Yangi pul yechish so‘rovi #{wr.id}\nUser: @{u.username or 'no_username'} ({u.id})\nMiqdor: {amount} so'm\nRekvizit: {target}", reply_markup=kb)
    user_states.pop(m.from_user.id, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith("wd_"))
def handle_withdraw_admin(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "Adminlar uchun.")
        return
    action, req_id = c.data.split("_")[1], int(c.data.split("_")[2])
    with get_session() as s:
        wr = s.get(WithdrawRequest, req_id)
        if not wr or wr.status != "pending":
            bot.answer_callback_query(c.id, "So‘rov topilmadi yoki allaqachon ko‘rib chiqilgan.")
            return
        user = s.get(User, wr.user_id)
        if action == "ok":
            wr.status = "approved"
            wr.processed_at = datetime.now()
            s.commit()
            bot.send_message(user.id, f"Pul yechish so‘rovi #{wr.id} tasdiqlandi.\nMiqdor: {wr.amount} so'm")
            if PROOF_CHANNEL_ID != 0:
                bot.send_message(PROOF_CHANNEL_ID, f"Yangi pul yechish so‘rovi tasdiqlandi!\nUser: @{user.username or 'no_username'}\nMiqdor: {wr.amount} so'm\nRekvizit: {mask_target(wr.pay_target)}\nHolat: <b>tasdiqlandi</b>")
            bot.answer_callback_query(c.id, "Tasdiqlandi.")
        elif action == "no":
            wr.status = "rejected"
            wr.processed_at = datetime.now()
            user.balance += wr.amount
            s.commit()
            bot.send_message(user.id, f"Pul yechish so‘rovi #{wr.id} bekor qilindi. {wr.amount} so'm balansingizga qaytarildi.")
            bot.answer_callback_query(c.id, "Bekor qilindi.")

@bot.message_handler(func=lambda m: m.text == "Pul yechish so'rovlari")
def my_withdraws(m):
    with get_session() as s:
        q = s.query(WithdrawRequest).filter(WithdrawRequest.user_id == m.from_user.id).order_by(desc(WithdrawRequest.id)).limit(10).all()
        if not q:
            bot.send_message(m.chat.id, "Sizda yechish so‘rovlari yo‘q.")
            return
        lines = []
        for r in q:
            lines.append(f"#{r.id} — {r.amount} so'm — {r.status} — {r.created_at.strftime('%Y-%m-%d %H:%M')}")
        bot.send_message(m.chat.id, "\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "Admin bilan aloqa")
def contact_admin(m):
    bot.send_message(m.chat.id, "Xabar matnini yuboring (to‘g‘ridan-to‘g‘ri adminlarga boradi).")
    user_states[m.from_user.id] = {"stage": "contact_admin"}

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("stage") == "contact_admin")
def forward_to_admin(m):
    txt = m.text.strip()
    user_states.pop(m.from_user.id, None)
    for admin_id in ADMIN_IDS:
        bot.send_message(admin_id, f"Foydalanuvchidan xabar:\nUser: @{m.from_user.username or 'no_username'} ({m.from_user.id})\nMatn:\n{txt}")
    bot.send_message(m.chat.id, "Xabar yuborildi.")

@bot.message_handler(func=lambda m: m.text == "Statistika")
def stats(m):
    if not is_admin(m.from_user.id):
        return
    with get_session() as s:
        total_users = s.query(User).count()
        start, end = today_date_range()
        daily_new = s.query(User).filter(User.created_at >= start, User.created_at < end).count()
        total_refs = s.query(Referral).count()
        today_refs = s.query(Referral).filter(Referral.created_at >= start, Referral.created_at < end).count()
        active_users = s.query(User).filter(User.last_active_at >= datetime.now() - timedelta(days=7)).count()
        bot.send_message(m.chat.id, f"Umumiy foydalanuvchilar: {total_users}\nAktiv (7 kun): {active_users}\nBugungi takliflar: {today_refs}\nUmumiy takliflar: {total_refs}\nKunlik yangi foydalanuvchilar: {daily_new}")

@bot.message_handler(func=lambda m: m.text == "Majburiy obuna")
def mandatory_menu(m):
    if not is_admin(m.from_user.id):
        return
    with get_session() as s:
        current = s.query(MandatoryChannel).all()
        lines = ["Majburiy obuna kanallari:"]
        for c in current:
            lines.append(f"- {c.channel_id} ({c.title or ''})")
        lines.append("\nQo‘shish: /add_sub <channel_id>\nO‘chirish: /del_sub <channel_id>")
        bot.send_message(m.chat.id, "\n".join(lines))

@bot.message_handler(commands=["add_sub"])
def add_sub(m):
    if not is_admin(m.from_user.id):
        return
    try:
        ch_id = int(m.text.split(" ", 1)[1].strip())
    except Exception:
        bot.reply_to(m, "Format: /add_sub <channel_id>")
        return
    with get_session() as s:
        if s.query(MandatoryChannel).filter(MandatoryChannel.channel_id == ch_id).first():
            bot.reply_to(m, "Allaqachon qo‘shilgan.")
            return
        title = None
        try:
            chat = bot.get_chat(ch_id)
            title = chat.title
        except Exception:
            pass
        s.add(MandatoryChannel(channel_id=ch_id, title=title))
        s.commit()
    bot.reply_to(m, "Qo‘shildi.")

@bot.message_handler(commands=["del_sub"])
def del_sub(m):
    if not is_admin(m.from_user.id):
        return
    try:
        ch_id = int(m.text.split(" ", 1)[1].strip())
    except Exception:
        bot.reply_to(m, "Format: /del_sub <channel_id>")
        return
    with get_session() as s:
        c = s.query(MandatoryChannel).filter(MandatoryChannel.channel_id == ch_id).first()
        if not c:
            bot.reply_to(m, "Topilmadi.")
            return
        s.delete(c)
        s.commit()
    bot.reply_to(m, "O‘chirildi.")

@bot.message_handler(func=lambda m: m.text == "Pul yechish so'rovlari (ADMIN)")
def admin_withdraws(m):
    if not is_admin(m.from_user.id):
        return
    with get_session() as s:
        q = s.query(WithdrawRequest).order_by(desc(WithdrawRequest.id)).limit(20).all()
        if not q:
            bot.send_message(m.chat.id, "So‘rovlar yo‘q.")
            return
        lines = []
        for r in q:
            lines.append(f"#{r.id} — {r.amount} so'm — {r.status} — {r.created_at.strftime('%Y-%m-%d %H:%M')} — User {r.user_id} — Rekv: {r.pay_target}")
        bot.send_message(m.chat.id, "\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "Reklama tarqatish")
def broadcast_prompt(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "Tarqatiladigan matnni yuboring.")
    user_states[m.from_user.id] = {"stage": "broadcast_text"}

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("stage") == "broadcast_text")
def broadcast_send(m):
    if not is_admin(m.from_user.id):
        user_states.pop(m.from_user.id, None)
        return
    text = m.text
    user_states.pop(m.from_user.id, None)
    with get_session() as s:
        total = s.query(User).count()
        s.add(BroadcastLog(message_type="text", content=text))
        s.commit()
        offset = 0
        sent = 0
        while True:
            users = s.query(User).order_by(User.id).offset(offset).limit(BROADCAST_BATCH).all()
            if not users:
                break
            for u in users:
                try:
                    bot.send_message(u.id, text)
                    sent += 1
                    time.sleep(0.02)
                except Exception:
                    pass
            offset += BROADCAST_BATCH
    bot.send_message(m.chat.id, f"Tarqatildi: {sent}/{total} foydalanuvchi.")

@bot.message_handler(func=lambda m: m.text == "Balans boshqarish")
def balance_manage(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "Format:\n/add_balance <user_id> <amount>\n/sub_balance <user_id> <amount>")

@bot.message_handler(commands=["add_balance"])
def add_balance(m):
    if not is_admin(m.from_user.id):
        return
    try:
        _, uid, amt = m.text.split()
        uid = int(uid)
        amt = int(amt)
    except Exception:
        bot.reply_to(m, "Format: /add_balance <user_id> <amount>")
        return
    with get_session() as s:
        u = s.get(User, uid)
        if not u:
            bot.reply_to(m, "User topilmadi.")
            return
        u.balance += amt
        s.commit()
    bot.reply_to(m, f"{uid} balansiga {amt} qo‘shildi.")

@bot.message_handler(commands=["sub_balance"])
def sub_balance(m):
    if not is_admin(m.from_user.id):
        return
    try:
        _, uid, amt = m.text.split()
        uid = int(uid)
        amt = int(amt)
    except Exception:
        bot.reply_to(m, "Format: /sub_balance <user_id> <amount>")
        return
    with get_session() as s:
        u = s.get(User, uid)
        if not u:
            bot.reply_to(m, "User topilmadi.")
            return
        if u.balance < amt:
            bot.reply_to(m, "Balans yetarli emas.")
            return
        u.balance -= amt
        s.commit()
    bot.reply_to(m, f"{uid} balansidan {amt} ayirildi.")

@bot.message_handler(func=lambda m: True)
def track_activity(m):
    with get_session() as s:
        u = s.get(User, m.from_user.id)
        if u:
            u.last_active_at = datetime.now()
            s.commit()
    txt = (m.text or "").strip().lower()
    if txt not in ["hisobim", "pul ishlash", "pul yechish", "pul yechish so'rovlari", "admin bilan aloqa", "isbotlar", "statistika", "majburiy obuna", "pul yechish so'rovlari (admin)", "reklama tarqatish", "balans boshqarish"]:
        bot.send_message(m.chat.id, "Menyu:", reply_markup=main_menu())
        if is_admin(m.from_user.id):
            bot.send_message(m.chat.id, "Admin menyu:", reply_markup=admin_menu())

if __name__ == "__main__":
    bot.infinity_polling(skip_pending=True, timeout=20)
