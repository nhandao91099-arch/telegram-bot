from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from reportlab.platypus import SimpleDocTemplate, Image
from google.cloud import vision
from google.oauth2 import service_account

import os, json, zipfile, re

# ===== TOKEN =====
TOKEN = os.environ.get("TOKEN")

# ===== GOOGLE OCR (CÁCH B - ENV) =====
info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
credentials = service_account.Credentials.from_service_account_info(info)
client = vision.ImageAnnotatorClient(credentials=credentials)

user_data = {}
REQUIRED_DOCS = ["cccd","vneid","luong","vssid","sf","other"]

# ================= OCR =================
def ocr_google(path):
    with open(path, "rb") as f:
        content = f.read()

    image = vision.Image(content=content)
    res = client.text_detection(image=image)

    texts = res.text_annotations
    return texts[0].description if texts else ""

# ================= LÃI =================
def tinh_lai(luong, kv, ct):
    if luong <= 10:
        base = [42,46,47,49]
    elif luong <= 20:
        base = [36,40,41,45]
    else:
        base = [30,35,36,40]

    if kv=="tp" and ct=="ps": return base[0]
    if kv=="tp": return base[1]
    if ct=="ps": return base[2]
    return base[3]

# ================= DBR =================
def tinh_dbr(luong, kv, no):
    max_dbr = 0.5 if kv=="tp" else 0.6
    con = luong*max_dbr - no
    vay = int(con*15)
    return round(no/luong*100), vay

# ================= PDF =================
def tao_pdf(docs, context, uid):
    files=[]

    for loai, fid in docs.items():
        file = context.bot.get_file(fid)
        img = f"{uid}_{loai}.jpg"
        file.download(img)

        pdf = f"{uid}_{loai}.pdf"
        doc = SimpleDocTemplate(pdf)
        doc.build([Image(img,400,500)])

        files.append(pdf)

        try: os.remove(img)
        except: pass

    return files

def zip_files(files, uid):
    z = f"{uid}_hoso.zip"
    with zipfile.ZipFile(z,'w') as zipf:
        for f in files:
            zipf.write(f)
    return z

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📊 TÍNH LÃI", callback_data="lai")],
        [InlineKeyboardButton("📊 DBR", callback_data="dbr")],
        [InlineKeyboardButton("📂 GIẤY TỜ", callback_data="docs")]
    ]
    await update.message.reply_text("Menu:", reply_markup=InlineKeyboardMarkup(kb))

# ================= BUTTON =================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data

    user_data.setdefault(uid,{})
    await q.answer()

    # ===== LÃI =====
    if data=="lai":
        user_data[uid]["step"]="luong_lai"
        await q.message.reply_text("Nhập lương:")
        return

    # ===== DBR =====
    if data=="dbr":
        user_data[uid]["step"]="luong_dbr"
        await q.message.reply_text("Nhập lương:")
        return

    # ===== DOCS =====
    if data=="docs":
        kb=[[InlineKeyboardButton(x.upper(),callback_data=f"doc_{x}")] for x in REQUIRED_DOCS]
        kb.append([InlineKeyboardButton("CHECK",callback_data="check")])
        kb.append([InlineKeyboardButton("PDF",callback_data="pdf")])
        kb.append([InlineKeyboardButton("SCAN",callback_data="scan")])
        await q.message.reply_text("Chọn:",reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("doc_"):
        user_data[uid]["doc_type"]=data.split("_")[1]
        user_data[uid]["step"]="upload"
        await q.message.reply_text("Gửi ảnh:")
        return

    if data=="check":
        docs=user_data.get(uid,{}).get("docs",{})
        msg="\n".join([f"{'✅' if d in docs else '❌'} {d}" for d in REQUIRED_DOCS])
        await q.message.reply_text(msg)
        return

    if data=="pdf":
        docs=user_data.get(uid,{}).get("docs",{})
        if not docs:
            await q.message.reply_text("❌ Chưa có giấy tờ")
            return

        files=tao_pdf(docs,context,uid)
        z=zip_files(files,uid)

        with open(z,"rb") as f:
            await q.message.reply_document(f)

        try:
            os.remove(z)
            for f in files: os.remove(f)
        except: pass

        return

    # ===== OCR =====
    if data=="scan":
        docs=user_data.get(uid,{}).get("docs",{})
        if not docs:
            await q.message.reply_text("❌ Chưa có giấy tờ")
            return

        text=""

        for loai,fid in docs.items():
            file=context.bot.get_file(fid)
            path=f"{uid}_{loai}.jpg"
            file.download(path)

            text+=ocr_google(path)

            try: os.remove(path)
            except: pass

        cccd=re.search(r"\d{9,12}",text)
        await q.message.reply_text(f"📋 CCCD: {cccd.group() if cccd else 'Không rõ'}")
        return

# ================= TEXT =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.message.from_user.id
    txt=update.message.text
    step=user_data.get(uid,{}).get("step")

    # ===== LÃI =====
    if step=="luong_lai":
        user_data[uid]["luong"]=float(txt)
        user_data[uid]["step"]="kv"
        await update.message.reply_text("tp / tinh")
        return

    if step=="kv":
        user_data[uid]["kv"]=txt
        user_data[uid]["step"]="ct"
        await update.message.reply_text("ps / non")
        return

    if step=="ct":
        d=user_data[uid]
        lai=tinh_lai(d["luong"],d["kv"],txt)
        await update.message.reply_text(f"📊 Lãi suất: {lai}%")
        return

    # ===== DBR =====
    if step=="luong_dbr":
        user_data[uid]["luong"]=float(txt)
        user_data[uid]["step"]="no"
        await update.message.reply_text("Nhập nợ:")
        return

    if step=="no":
        d=user_data[uid]
        dbr,vay=tinh_dbr(d["luong"],"tp",float(txt))
        await update.message.reply_text(f"📊 DBR: {dbr}%\n💰 Vay thêm: {vay}tr")
        return

# ================= PHOTO =================
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.message.from_user.id

    if user_data.get(uid,{}).get("step")=="upload":
        fid=update.message.photo[-1].file_id
        loai=user_data[uid]["doc_type"]

        user_data[uid].setdefault("docs",{})
        user_data[uid]["docs"][loai]=fid

        await update.message.reply_text(f"✅ Đã lưu {loai}")

# ================= RUN =================
app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle))
app.add_handler(MessageHandler(filters.PHOTO,photo))

print("BOT OK")
app.run_polling()
