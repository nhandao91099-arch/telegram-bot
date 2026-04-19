import os
import sqlite3
import zipfile
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from reportlab.platypus import SimpleDocTemplate, Image
from docx import Document

# ===== TOKEN =====
TOKEN = os.getenv("TOKEN")

# ===== DB =====
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS customers (
    phone TEXT PRIMARY KEY,
    name TEXT,
    cccd TEXT,
    salary REAL
)""")

c.execute("""CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    type TEXT,
    file_id TEXT
)""")

conn.commit()

user_data = {}

# ================= TLS =================

def tinh_lai(luong, kv, ct):
    if luong <= 8: base = [42,46,47,49]
    elif luong <= 10: base = [40.5,44.5,45.5,49]
    elif luong <= 13: base = [38.5,42.5,43.5,47]
    elif luong <= 17: base = [36.5,40.5,41.5,45]
    elif luong <= 22: base = [34,38.5,39.5,43]
    elif luong <= 27: base = [30,34,35,39]
    elif luong <= 33: base = [26.5,30.5,31.5,35]
    else: base = [19,25.5,26.5,30]

    if kv == "tp" and ct == "ps": return base[0]
    elif kv == "tp": return base[1]
    elif ct == "ps": return base[2]
    else: return base[3]

def tinh_mue(luong, kv, ct):
    if kv == "tp":
        hs = 6 if luong < 6 else 10 if luong < 12 else 12
    else:
        hs = 6 if luong < 9 else 8
    return round(luong * hs, 0)

def tinh_gop(vay, lai, thang):
    r = lai / 100 / 12
    return int(vay * r / (1 - (1 + r) ** -thang))

# ================= MENU =================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 TLS", callback_data="tls")],
        [InlineKeyboardButton("👤 KHÁCH HÀNG", callback_data="cus")],
        [InlineKeyboardButton("📄 THƯ XÁC NHẬN", callback_data="txn")]
    ])

def doc_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("CCCD", callback_data="doc_CCCD")],
        [InlineKeyboardButton("VNEID", callback_data="doc_VNEID")],
        [InlineKeyboardButton("LƯƠNG", callback_data="doc_LUONG")],
        [InlineKeyboardButton("VSSID", callback_data="doc_VSSID")],
        [InlineKeyboardButton("SF", callback_data="doc_SF")],
        [InlineKeyboardButton("OTHER", callback_data="doc_OTHER")],
        [InlineKeyboardButton("📄 Xuất PDF", callback_data="export")]
    ])

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("MENU:", reply_markup=main_menu())

# ================= BUTTON =================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data

    user_data.setdefault(uid, {})
    await query.answer()

    # TLS
    if data == "tls":
        user_data[uid]["step"] = "tls_luong"
        await query.message.reply_text("Nhập lương (18.5 hoặc 18500000 đều được):")
        return

    if data.startswith("kv_"):
        user_data[uid]["kv"] = data.split("_")[1]

    elif data.startswith("ct_"):
        user_data[uid]["ct"] = data.split("_")[1]

    elif data == "calc":
        d = user_data[uid]

        lai = tinh_lai(d["luong"], d["kv"], d["ct"])
        mue = tinh_mue(d["luong"], d["kv"], d["ct"])

        vay = int(mue * 0.8) * 1000000

        msg = f"""📊 KẾT QUẢ
Lãi: {lai}%
Hạn mức: {mue}tr

12T: {tinh_gop(vay,lai,12):,}
24T: {tinh_gop(vay,lai,24):,}
36T: {tinh_gop(vay,lai,36):,}
48T: {tinh_gop(vay,lai,48):,}
"""
        await query.message.reply_text(msg)
        return

    # KHÁCH
    if data == "cus":
        user_data[uid]["step"] = "input_cus"
        await query.message.reply_text("Nhập:\nTên\nSĐT\nCCCD\nLương")
        return

    if data.startswith("doc_"):
        user_data[uid]["doc_type"] = data.split("_")[1]
        user_data[uid]["step"] = "upload"
        await query.message.reply_text("Gửi ảnh")
        return

    if data == "export":
        phone = user_data[uid]["phone"]

        c.execute("SELECT type,file_id FROM documents WHERE phone=?", (phone,))
        rows = c.fetchall()

        files = []

        for t,fid in rows:
            file = await context.bot.get_file(fid)
            path = f"{fid}.jpg"
            await file.download_to_drive(path)

            pdf = f"{t}.pdf"
            doc = SimpleDocTemplate(pdf)
            doc.build([Image(path)])

            files.append(pdf)
            await query.message.reply_document(open(pdf,"rb"))

        zip_name = f"{phone}.zip"
        with zipfile.ZipFile(zip_name,"w") as z:
            for f in files:
                z.write(f)

        await query.message.reply_document(open(zip_name,"rb"))
        return

    # TXN
    if data == "txn":
        user_data[uid]["step"] = "txn_input"
        await query.message.reply_text("Nhập:\nTên\nCCCD\nNgày cấp\nNơi cấp\nĐịa chỉ")
        return

# ================= TEXT =================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    txt = update.message.text

    # TLS
    if user_data.get(uid, {}).get("step") == "tls_luong":
        try:
            luong = float(txt.replace(",", "."))
            if luong > 1000:
                luong /= 1000000

            user_data[uid]["luong"] = luong

            keyboard = [
                [InlineKeyboardButton("TP", callback_data="kv_tp"),
                 InlineKeyboardButton("Tỉnh", callback_data="kv_tinh")],
                [InlineKeyboardButton("PS", callback_data="ct_ps"),
                 InlineKeyboardButton("NON", callback_data="ct_non")],
                [InlineKeyboardButton("TÍNH", callback_data="calc")]
            ]

            await update.message.reply_text("Chọn:", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await update.message.reply_text("Nhập số")
        return

    # KHÁCH
    if user_data.get(uid, {}).get("step") == "input_cus":
        lines = txt.split("\n")

        if len(lines) < 4:
            await update.message.reply_text("Nhập đủ 4 dòng")
            return

        name = lines[0]
        phone = lines[1]
        cccd = lines[2]
        salary = float(lines[3])

        c.execute("INSERT OR REPLACE INTO customers VALUES (?,?,?,?)",
                  (phone,name,cccd,salary))
        conn.commit()

        user_data[uid]["phone"] = phone

        await update.message.reply_text("Đã lưu\nGửi hồ sơ:", reply_markup=doc_menu())
        return

    # TXN
    if user_data.get(uid, {}).get("step") == "txn_input":
        lines = txt.split("\n")

        if len(lines) < 5:
            await update.message.reply_text("Nhập đủ 5 dòng")
            return

        ten, cccd, ngaycap, noicap, diachi = lines

        doc = Document()
        now = datetime.now()

        doc.add_paragraph(f"Tôi là: {ten}")
        doc.add_paragraph(f"CCCD: {cccd}")
        doc.add_paragraph(f"Ngày cấp: {ngaycap} tại {noicap}")
        doc.add_paragraph(f"Địa chỉ: {diachi}")
        doc.add_paragraph(f"Ngày {now.day}/{now.month}/{now.year}")
        doc.add_paragraph(ten)

        file = f"{ten}.docx"
        doc.save(file)

        await update.message.reply_document(open(file,"rb"))
        return

# ================= PHOTO =================

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id

    if user_data.get(uid, {}).get("step") != "upload":
        return

    phone = user_data[uid]["phone"]
    doc_type = user_data[uid]["doc_type"]
    file_id = update.message.photo[-1].file_id

    c.execute("INSERT INTO documents(phone,type,file_id) VALUES (?,?,?)",
              (phone,doc_type,file_id))
    conn.commit()

    await update.message.reply_text("Đã lưu")

# ================= RUN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    print("RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
