import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== TOKEN (CHO RENDER) =====
TOKEN = os.getenv("TOKEN")

user_data = {}

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📊 TLS", callback_data="tls")]]
    await update.message.reply_text("Bấm TLS:", reply_markup=InlineKeyboardMarkup(keyboard))

# ===== TÍNH LÃI =====
def tinh_lai(luong, kv, ct):
    if luong <= 8:
        base = [42,46,47,49]
    elif luong <= 10:
        base = [40.5,44.5,45.5,49]
    elif luong <= 13:
        base = [38.5,42.5,43.5,47]
    elif luong <= 17:
        base = [36.5,40.5,41.5,45]
    elif luong <= 22:
        base = [34,38.5,39.5,43]
    elif luong <= 27:
        base = [30,34,35,39]
    elif luong <= 33:
        base = [26.5,30.5,31.5,35]
    else:
        base = [19,25.5,26.5,30]

    if kv == "tp" and ct == "ps":
        return base[0]
    elif kv == "tp":
        return base[1]
    elif ct == "ps":
        return base[2]
    else:
        return base[3]

# ===== MỨC VAY =====
def tinh_mue(luong, kv, ct):
    if kv == "tp":
        if ct == "ps":
            hs = 6 if luong < 6 else 10 if luong < 12 else 12
        else:
            hs = 6 if luong < 6 else 8 if luong < 12 else 10
    else:
        if ct == "ps":
            hs = 6 if luong < 6 else 10
        else:
            hs = 6 if luong < 9 else 8

    return round(luong * hs, 0)

# ===== GÓP EMI =====
def tinh_gop(vay, lai, thang):
    r = lai / 100 / 12
    return int(vay * r / (1 - (1 + r) ** -thang))

# ===== TÍNH TỔNG =====
def tinh_all(luong, kv, ct, dc=None):
    lai = tinh_lai(luong, kv, ct)

    if dc == "han":
        lai -= 1

    mue = tinh_mue(luong, kv, ct)

    thap = int(mue * 0.7)
    cao = int(mue * 0.9)
    vay_tr = int((thap + cao) / 2)
    vay = vay_tr * 1000000

    return f"""📊 KẾT QUẢ

👉 Lãi suất: {lai}%
💰 Hạn mức: {int(mue)} triệu

📌 Gợi ý vay:
{thap} – {cao} triệu

💸 Ước tính (vay {vay_tr}tr):

12T: ~ {tinh_gop(vay,lai,12):,}
24T: ~ {tinh_gop(vay,lai,24):,}
36T: ~ {tinh_gop(vay,lai,36):,}
48T: ~ {tinh_gop(vay,lai,48):,}
"""

# ===== MENU =====
def build_menu(uid):
    d = user_data.get(uid, {})

    text = f"""📊 TÍNH LÃI

💰 Lương: {d.get("luong","❓")}
📍 KV: {d.get("kv","❓")}
🏢 CT: {d.get("ct","❓")}
⚙️ DC: {d.get("dc","❓")}
"""

    keyboard = [
        [InlineKeyboardButton("🏙 TP", callback_data="kv_tp"),
         InlineKeyboardButton("🌆 Tỉnh", callback_data="kv_tinh")],

        [InlineKeyboardButton("🏢 PS", callback_data="ct_ps"),
         InlineKeyboardButton("🏭 NON", callback_data="ct_non")],

        [InlineKeyboardButton("🇰🇷 Hàn", callback_data="dc_han"),
         InlineKeyboardButton("❌ None", callback_data="dc_none")],

        [InlineKeyboardButton("✅ TÍNH", callback_data="calc")]
    ]

    return text, InlineKeyboardMarkup(keyboard)

# ===== BUTTON =====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data

    user_data.setdefault(uid, {})

    await query.answer()

    if data == "tls":
        user_data[uid] = {}
        text, markup = build_menu(uid)
        await query.message.edit_text(text, reply_markup=markup)
        return

    if data.startswith("kv_"):
        user_data[uid]["kv"] = data.split("_")[1]

    elif data.startswith("ct_"):
        user_data[uid]["ct"] = data.split("_")[1]

    elif data.startswith("dc_"):
        user_data[uid]["dc"] = data.split("_")[1]

    elif data == "calc":
        d = user_data[uid]

        if "luong" not in d or "kv" not in d or "ct" not in d:
            await query.answer("Nhập đủ thông tin!", show_alert=True)
            return

        msg = tinh_all(d["luong"], d["kv"], d["ct"], d.get("dc"))
        await query.message.reply_text(msg)
        return

    text, markup = build_menu(uid)
    await query.message.edit_text(text, reply_markup=markup)

# ===== NHẬP LƯƠNG =====
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    txt = update.message.text.replace(",", ".")

    try:
        luong = float(txt)
        if luong > 1000:
            luong /= 1000000

        user_data.setdefault(uid, {})
        user_data[uid]["luong"] = round(luong, 2)

        text, markup = build_menu(uid)
        await update.message.reply_text(text, reply_markup=markup)

    except:
        await update.message.reply_text("Nhập số: 18 / 18.5 / 18000000")

# ===== RUN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("BOT ĐANG CHẠY...")
    app.run_polling()

if __name__ == "__main__":
    main()
