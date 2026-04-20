import os, zipfile
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from reportlab.platypus import SimpleDocTemplate, Image

TOKEN = os.environ.get("BOT_TOKEN")

user_data = {}
customers = {}

DOC_TYPES = ["cccd","vneid","vssid","luong","sf","other"]

# ================= TLS =================
def tinh_lai(luong, kv, ct):
    if luong <= 8:
        base = [42,46,47,49]
    elif luong <= 10:
        base = [40.5,44.5,45.5,49]
    else:
        base = [38.5,42.5,43.5,47]

    if kv == "tp" and ct == "ps":
        return base[0]
    elif kv == "tp":
        return base[1]
    elif ct == "ps":
        return base[2]
    else:
        return base[3]

def build_tls(uid):
    d = user_data.get(uid, {})
    text = f"""📊 TLS

💰 Lương: {d.get("luong","❓")}
📍 KV: {d.get("kv","❓")}
🏢 CT: {d.get("ct","❓")}
"""

    kb = [
        [InlineKeyboardButton("🏙 TP","kv_tp"),
         InlineKeyboardButton("🌆 Tỉnh","kv_tinh")],
        [InlineKeyboardButton("🏢 PS","ct_ps"),
         InlineKeyboardButton("🏭 NON","ct_non")],
        [InlineKeyboardButton("✅ TÍNH","calc")]
    ]
    return text, InlineKeyboardMarkup(kb)

# ================= DBR =================
def tinh_dbr(luong, ct, no):
    if ct == "ps":
        max_dbr = 0.5 if luong >= 6 else 0.4
    else:
        max_dbr = 0.5 if luong >= 12 else 0.4

    dbr = no / luong
    con = luong * max_dbr - no
    vay = int(con * 15)

    return round(dbr*100), int(max_dbr*100), vay

# ================= PDF =================
def img_to_pdf(img, pdf):
    doc = SimpleDocTemplate(pdf)
    doc.build([Image(img, width=400, height=500)])

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📊 TLS","tls")],
        [InlineKeyboardButton("📂 HỒ SƠ","hoso")]
    ]
    await update.message.reply_text("Chọn:", reply_markup=InlineKeyboardMarkup(kb))

# ================= BUTTON =================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data

    user_data.setdefault(uid, {})
    await q.answer()

    # TLS
    if data=="tls":
        user_data[uid]={}
        user_data[uid]["step"]="luong"
        await q.message.reply_text("Nhập lương:")
        return

    if data.startswith("kv_"):
        user_data[uid]["kv"]=data.split("_")[1]

    if data.startswith("ct_"):
        user_data[uid]["ct"]=data.split("_")[1]

    if data=="calc":
        d=user_data[uid]
        lai=tinh_lai(d["luong"],d["kv"],d["ct"])
        await q.message.reply_text(f"📊 Lãi suất: {lai}%")

        kb=[
            [InlineKeyboardButton("📊 DBR","dbr")],
            [InlineKeyboardButton("🔁 TLS lại","tls")],
            [InlineKeyboardButton("❌ Bỏ qua","skip")]
        ]
        await q.message.reply_text("Tiếp:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data=="dbr":
        user_data[uid]["step"]="no"
        await q.message.reply_text("Nhập nợ hàng tháng:")
        return

    # HỒ SƠ
    if data=="hoso":
        kb=[
            [InlineKeyboardButton("➕ NEW","new")],
            [InlineKeyboardButton("🔍 CHECK","check")]
        ]
        await q.message.reply_text("Hồ sơ:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data=="new":
        user_data[uid]["step"]="new"
        await q.message.reply_text("Tên:\nCCCD:\nSDT:\nĐịa chỉ:\nLương:")
        return

    if data=="check":
        user_data[uid]["step"]="search"
        await q.message.reply_text("Nhập tên/cccd/sdt:")
        return

    if data.startswith("doc_"):
        user_data[uid]["doc_type"]=data.split("_")[1]
        user_data[uid]["step"]="upload"
        user_data[uid]["last_photos"]=[]
        await q.message.reply_text("Gửi ảnh xong bấm lại loại giấy tờ")
        return

    if data=="done_upload":
        await q.message.reply_text("Đã xong upload")
        return

    if data=="export_zip":
        kh=customers[user_data[uid]["current"]]
        files=[]
        for k,arr in kh["docs"].items():
            for i,fid in enumerate(arr):
                file=context.bot.get_file(fid)
                img=f"{uid}_{k}_{i}.jpg"
                file.download(img)

                pdf=f"{uid}_{k}_{i}.pdf"
                img_to_pdf(img,pdf)
                files.append(pdf)
                os.remove(img)

        zipname=f"{uid}.zip"
        with zipfile.ZipFile(zipname,'w') as z:
            for f in files:
                z.write(f)

        await q.message.reply_document(open(zipname,"rb"))

        for f in files+[zipname]:
            os.remove(f)
        return

# ================= HANDLE =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.message.from_user.id
    txt=update.message.text
    step=user_data.get(uid,{}).get("step")

    if step=="luong":
        user_data[uid]["luong"]=float(txt)
        text,markup=build_tls(uid)
        await update.message.reply_text(text, reply_markup=markup)
        return

    if step=="no":
        d=user_data[uid]
        dbr,maxd,vay=tinh_dbr(d["luong"],d["ct"],float(txt))
        await update.message.reply_text(f"DBR:{dbr}% | Max:{maxd}% | Vay thêm:{vay}tr")

        kb=[
            [InlineKeyboardButton("💾 Lưu khách","save")],
            [InlineKeyboardButton("📂 Hồ sơ","hoso")],
            [InlineKeyboardButton("🔁 TLS","tls")]
        ]
        await update.message.reply_text("Tiếp:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if step=="new":
        lines=txt.split("\n")
        data={
            "ten":lines[0],
            "cccd":lines[1],
            "sdt":lines[2],
            "diachi":lines[3],
            "luong":lines[4],
            "docs":{k:[] for k in DOC_TYPES}
        }
        customers[data["cccd"]]=data
        user_data[uid]["current"]=data["cccd"]

        kb=[[InlineKeyboardButton("📎 Upload giấy tờ","upload")]]
        await update.message.reply_text("Đã lưu khách", reply_markup=InlineKeyboardMarkup(kb))
        return

    if step=="search":
        for k,v in customers.items():
            if txt in k or txt in v["ten"] or txt in v["sdt"]:
                user_data[uid]["current"]=k
                kb=[
                    [InlineKeyboardButton("👁 Xem","view")],
                    [InlineKeyboardButton("📤 ZIP","export_zip")]
                ]
                await update.message.reply_text(v["ten"], reply_markup=InlineKeyboardMarkup(kb))
                return
        await update.message.reply_text("Không thấy")

# ================= PHOTO =================
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.message.from_user.id

    if "last_photos" in user_data.get(uid,{}):
        user_data[uid]["last_photos"].append(update.message.photo[-1].file_id)

# ================= RUN =================
app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.PHOTO, photo))

print("BOT RUNNING")
app.run_polling()
