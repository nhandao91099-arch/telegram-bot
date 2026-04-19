import os
import sqlite3
import zipfile
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from reportlab.platypus import SimpleDocTemplate, Image
from docx import Document
import pytesseract
from PIL import Image as PILImage

# ===== TOKEN =====
TOKEN = os.getenv("TOKEN")

# ===== DB =====
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS customers (
    phone TEXT PRIMARY KEY,
    name TEXT,
    cccd TEXT,
    salary REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    type TEXT,
    file_id TEXT
)
""")

conn.commit()

user_data = {}

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

def tinh_gop(vay, lai, thang):
    r = lai / 100 / 12
    return int(vay * r / (1 - (1 + r) ** -thang))

# ================= MENU =================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 TLS", callback_data="tls")],
        [InlineKeyboardButton("👤 KHÁCH HÀNG", callback_data="customer")],
        [InlineKeyboardButton("📄 THƯ XÁC NHẬN", callback_data="txn")]
    ])

def customer_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 GIẤY TỜ", callback_data="doc")],
        [InlineKeyboardButton("❗ CHECK THIẾU", callback_data="check_doc")],
        [InlineKeyboardButton("📄 XUẤT PDF", callback_data="export_pdf")],
        [InlineKeyboardButton("🤖 SCAN DOCX", callback_data="scan_docx")]
    ])

def doc_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("CCCD", callback_data="doc_CCCD")],
        [InlineKeyboardButton("VNEID", callback_data="doc_VNEID")],
        [InlineKeyboardButton("LUONG", callback_data="doc_LUONG")],
        [InlineKeyboardButton("VSSID", callback_data="doc_VSSID")],
        [InlineKeyboardButton("SF", callback_data="doc_SF")],
        [InlineKeyboardButton("OTHER", callback_data="doc_OTHER")]
    ])

def txn_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("LNL", callback_data="txn_LNL")],
        [InlineKeyboardButton("SALPIL", callback_data="txn_SALPIL")]
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
        await query.message.reply_text("Nhập lương:")
        user_data[uid]["step"] = "tls_salary"
        return

    # CUSTOMER
    if data == "customer":
        await query.message.reply_text("Nhập: Tên | SĐT | CCCD | Lương")
        user_data[uid]["step"] = "new_customer"
        return

    # DOC
    if data == "doc":
        await query.message.reply_text("Chọn loại:", reply_markup=doc_menu())
        return

    if data.startswith("doc_"):
        user_data[uid]["doc_type"] = data.split("_")[1]
        user_data[uid]["step"] = "upload_doc"
        await query.message.reply_text("Gửi ảnh")
        return

    # CHECK
    if data == "check_doc":
        phone = user_data[uid]["current_phone"]
        REQUIRED = ["CCCD","VNEID","LUONG","VSSID","SF"]

        c.execute("SELECT DISTINCT type FROM documents WHERE phone=?", (phone,))
        have = [x[0] for x in c.fetchall()]

        missing = [x for x in REQUIRED if x not in have]

        if missing:
            await query.message.reply_text("\n".join([f"❌ {x}" for x in missing]))
        else:
            await query.message.reply_text("✅ Đủ")
        return

    # EXPORT PDF
    if data == "export_pdf":
        phone = user_data[uid]["current_phone"]

        c.execute("SELECT DISTINCT type FROM documents WHERE phone=?", (phone,))
        types = [x[0] for x in c.fetchall()]

        pdfs = []

        for t in types:
            c.execute("SELECT file_id FROM documents WHERE phone=? AND type=?", (phone,t))
            files = c.fetchall()

            elements = []
            for f in files:
                file = await context.bot.get_file(f[0])
                path = f"{f[0]}.jpg"
                await file.download_to_drive(path)
                elements.append(Image(path))

            pdf = f"{t}.pdf"
            doc = SimpleDocTemplate(pdf)
            doc.build(elements)

            pdfs.append(pdf)
            await query.message.reply_document(open(pdf,"rb"))

        zip_name = f"hoso_{phone}.zip"
        with zipfile.ZipFile(zip_name,'w') as z:
            for f in pdfs:
                z.write(f)

        await query.message.reply_document(open(zip_name,"rb"))
        return

    # SCAN DOCX
    if data == "scan_docx":
        user_data[uid]["step"] = "input_extra"
        await query.message.reply_text("Địa chỉ | Nơi làm | Công ty | Chức vụ")
        return

    # TXN
    if data == "txn":
        await query.message.reply_text("Chọn loại:", reply_markup=txn_menu())
        return

    if data.startswith("txn_"):
        user_data[uid]["txn_type"] = data.split("_")[1]
        user_data[uid]["step"] = "txn_input"
        await query.message.reply_text("Tên | CCCD | Ngày cấp | Nơi cấp | Địa chỉ")
        return

# ================= HANDLE TEXT =================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    txt = update.message.text

    # NEW CUSTOMER
    if user_data.get(uid, {}).get("step") == "new_customer":
        name, phone, cccd, salary = [x.strip() for x in txt.split("|")]

        c.execute("INSERT OR REPLACE INTO customers VALUES (?,?,?,?)",
                  (phone, name, cccd, float(salary)))
        conn.commit()

        user_data[uid]["current_phone"] = phone

        await update.message.reply_text("Đã lưu", reply_markup=customer_menu())
        return

    # SCAN EXTRA
    if user_data.get(uid, {}).get("step") == "input_extra":
        parts = txt.split("|")

        extra = {
            "address": parts[0].strip(),
            "work": parts[1].strip(),
            "company": parts[2].strip(),
            "job": parts[3].strip()
        }

        phone = user_data[uid]["current_phone"]

        doc = Document()
        doc.add_heading("THÔNG TIN KHÁCH",0)

        c.execute("SELECT * FROM customers WHERE phone=?", (phone,))
        cus = c.fetchone()

        doc.add_paragraph(f"Tên: {cus[1]}")
        doc.add_paragraph(f"SĐT: {cus[0]}")
        doc.add_paragraph(f"CCCD: {cus[2]}")

        doc.add_paragraph(f"Địa chỉ: {extra['address']}")
        doc.add_paragraph(f"Công ty: {extra['company']}")

        c.execute("SELECT type, file_id FROM documents WHERE phone=?", (phone,))
        rows = c.fetchall()

        for t,fid in rows:
            file = await context.bot.get_file(fid)
            path = f"{fid}.jpg"
            await file.download_to_drive(path)

            text = pytesseract.image_to_string(PILImage.open(path))
            doc.add_paragraph(f"{t}: {text}")

        name = f"scan_{phone}.docx"
        doc.save(name)

        await update.message.reply_document(open(name,"rb"))
        return

    # TXN
    if user_data.get(uid, {}).get("step") == "txn_input":
        ten, cccd, ngaycap, noicap, diachi = [x.strip() for x in txt.split("|")]

        now = datetime.now()

        doc = Document()
        doc.add_heading("THƯ XÁC NHẬN",0)

        doc.add_paragraph(f"Tôi là: {ten}")
        doc.add_paragraph(f"Số CCCD: {cccd}. Cấp ngày: {ngaycap}. Cấp tại: {noicap}")
        doc.add_paragraph(f"Địa chỉ: {diachi}")

        if user_data[uid]["txn_type"] == "LNL":
            doc.add_paragraph("MUA ĐỒ DÙNG GIA ĐÌNH - BỘ BÀN GHẾ GỖ")

        doc.add_paragraph(f"Ngày {now.day} tháng {now.month} năm {now.year}")
        doc.add_paragraph(ten)

        file = f"txn_{ten}.docx"
        doc.save(file)

        await update.message.reply_document(open(file,"rb"))
        return

# ================= PHOTO =================

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id

    if user_data.get(uid, {}).get("step") != "upload_doc":
        return

    phone = user_data[uid]["current_phone"]
    doc_type = user_data[uid]["doc_type"]
    file_id = update.message.photo[-1].file_id

    c.execute("INSERT INTO documents(phone,type,file_id) VALUES (?,?,?)",
              (phone, doc_type, file_id))
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
