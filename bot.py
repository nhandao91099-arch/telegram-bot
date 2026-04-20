# ================= IMPORT =================
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from datetime import datetime
from docx import Document
from reportlab.platypus import SimpleDocTemplate, Image
from PIL import Image as PILImage

import os, json, zipfile, re

# ================= TOKEN =================
TOKEN = os.environ.get("BOT_TOKEN")

# ================= DATA =================
user_data = {}
customers = {}

REQUIRED_DOCS = ["cccd", "vneid", "vssid", "luong", "sf", "other"]

# ================= TLS (GIỮ NGUYÊN) =================
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

# ================= DBR =================
def tinh_dbr(luong, ct, no):
    if ct == "ps":
        max_dbr = 0.5 if luong >= 6 else 0.4
    else:
        max_dbr = 0.5 if luong >= 12 else 0.4

    dbr = no / luong
    con = luong * max_dbr - no
    vay = int(con * 15)

    return round(dbr * 100), vay, int(max_dbr * 100)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📊 TLS", callback_data="tls")],
        [InlineKeyboardButton("📂 HỒ SƠ", callback_data="hoso")],
        [InlineKeyboardButton("📄 TXN", callback_data="txn")]
    ]
    await update.message.reply_text("Chọn chức năng:", reply_markup=InlineKeyboardMarkup(kb))

# ================= BUTTON =================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data

    user_data.setdefault(uid, {})
    await query.answer()

    # ===== TLS =====
    if data == "tls":
        user_data[uid]["step"] = "tls_luong"
        await query.message.reply_text("Nhập lương:")
        return

    if data == "dbr":
        user_data[uid]["step"] = "dbr_no"
        await query.message.reply_text("Nhập nợ hàng tháng:")
        return

    if data == "hoso":
        kb = [
            [InlineKeyboardButton("➕ NEW", callback_data="new_kh")],
            [InlineKeyboardButton("🔍 CHECK", callback_data="check_kh")]
        ]
        await query.message.reply_text("Hồ sơ:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "new_kh":
        user_data[uid]["step"] = "new_kh"
        await query.message.reply_text("Nhập:\nTên:\nCCCD:\nSDT:\nĐịa chỉ:\nLương:")
        return

    if data == "check_kh":
        user_data[uid]["step"] = "search_kh"
        await query.message.reply_text("Nhập tên / sdt / cccd:")
        return

    if data == "export":
        kb = [
            [InlineKeyboardButton("📦 ZIP", callback_data="zip")],
            [InlineKeyboardButton("📄 OCR FORM", callback_data="ocr_form")]
        ]
        await query.message.reply_text("Xuất:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "txn":
        user_data[uid]["step"] = "txn_search"
        await query.message.reply_text("Nhập tên / sdt / cccd:")
        return

# ================= HANDLE TEXT =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    txt = update.message.text

    step = user_data.get(uid, {}).get("step")

    # ===== TLS =====
    if step == "tls_luong":
        user_data[uid]["luong"] = float(txt)
        user_data[uid]["step"] = "tls_kv"
        await update.message.reply_text("KV (tp/tinh):")
        return

    if step == "tls_kv":
        user_data[uid]["kv"] = txt
        user_data[uid]["step"] = "tls_ct"
        await update.message.reply_text("CT (ps/non):")
        return

    if step == "tls_ct":
        user_data[uid]["ct"] = txt

        d = user_data[uid]
        lai = tinh_lai(d["luong"], d["kv"], d["ct"])

        await update.message.reply_text(f"Lãi: {lai}%")

        kb = [[InlineKeyboardButton("📊 DBR", callback_data="dbr")]]
        await update.message.reply_text("Tiếp:", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ===== DBR =====
    if step == "dbr_no":
        d = user_data[uid]
        no = float(txt)

        dbr, vay, maxd = tinh_dbr(d["luong"], d["ct"], no)

        await update.message.reply_text(f"DBR: {dbr}%\nMax: {maxd}%\nVay thêm: {vay}tr")
        return

    # ===== NEW KH =====
    if step == "new_kh":
        lines = txt.split("\n")
        data = {
            "ten": lines[0].split(":")[1].strip(),
            "cccd": lines[1].split(":")[1].strip(),
            "sdt": lines[2].split(":")[1].strip(),
            "diachi": lines[3].split(":")[1].strip(),
            "luong": lines[4].split(":")[1].strip(),
            "docs": {}
        }
        customers[data["cccd"]] = data

        await update.message.reply_text("Đã lưu khách")
        return

    # ===== SEARCH =====
    if step == "search_kh":
        for k,v in customers.items():
            if txt in v["ten"] or txt in v["cccd"] or txt in v["sdt"]:
                user_data[uid]["current"] = k

                kb = [[InlineKeyboardButton("📤 Xuất", callback_data="export")]]
                await update.message.reply_text(f"Tên: {v['ten']}", reply_markup=InlineKeyboardMarkup(kb))
                return

        await update.message.reply_text("Không tìm thấy")
        return

# ================= RUN =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("BOT RUNNING")
app.run_polling()
