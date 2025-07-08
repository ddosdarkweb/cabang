from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from datetime import datetime, timedelta
import pytz
import json
from flask import Flask
import threading
import os

# === FLASK UNTUK KEEP ALIVE ===
app = Flask('')

@app.route('/')
def home():
    return "Bot aktif 24 jam!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.start()

# === KONFIGURASI BOT ===
TOKEN = "8019108696:AAHCA-1aWHkPlnypDDLjXL-Z6OW2kOxhU6I"
ADMIN_IDS = [5397964203, 1293577945]  # Ganti sesuai admin kamu
MAKS_IZIN = 5
TIMEZONE = pytz.timezone("Asia/Jakarta")
IZIN_FILE = "izin.json"

# === DURASI DEFAULT PER JENIS IZIN (MENIT) ===
DURASI = {
    "makan": 20,
    "merokok": 10,
    "toilet": 5,
    "bab": 15
}

izin_aktif = {}
last_kembali_uid = None

# === SIMPAN & LOAD DATA ===
def simpan_data():
    with open(IZIN_FILE, "w") as f:
        json.dump(izin_aktif, f, indent=2, default=str)

def load_data():
    global izin_aktif
    if os.path.exists(IZIN_FILE):
        with open(IZIN_FILE, "r") as f:
            raw = json.load(f)
            for uid, data in raw.items():
                izin_aktif[uid] = {
                    "nama": data["nama"],
                    "alasan": data["alasan"],
                    "keluar": datetime.fromisoformat(data["keluar"]),
                    "kembali": datetime.fromisoformat(data["kembali"])
                }

# === KIRIM PESAN KE ADMIN ===
async def kirim_ke_admins(context: ContextTypes.DEFAULT_TYPE, pesan: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=pesan)
        except Exception as e:
            print(f"Gagal kirim ke admin {admin_id}: {e}")

# === MENU IZIN ===
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🍽️ Makan", callback_data='izin_makan'),
         InlineKeyboardButton("🚬 Merokok", callback_data='izin_merokok')],
        [InlineKeyboardButton("🚽 Toilet", callback_data='izin_toilet'),
         InlineKeyboardButton("💩 BAB", callback_data='izin_bab')]
    ]
    await update.message.reply_text(
        "Silakan pilih jenis izin keluar:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === HANDLE IZIN ===
async def handle_izin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    alasan = query.data.replace("izin_", "")
    uid = str(user.id)

    if uid in izin_aktif:
        await query.message.reply_text("⚠️ Kamu masih dalam status izin.")
        return

    if len(izin_aktif) >= MAKS_IZIN:
        await query.message.reply_text("❌ Maksimal 5 orang boleh izin bersamaan.")
        return

    now = datetime.now(TIMEZONE)
    kembali = now + timedelta(minutes=DURASI[alasan])
    izin_aktif[uid] = {
        "nama": user.first_name,
        "alasan": alasan,
        "keluar": now,
        "kembali": kembali
    }
    simpan_data()

    tombol_kembali = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Saya Sudah Kembali", callback_data=f"in_{uid}")]
    ])

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"✅ {user.first_name} izin {alasan} pukul {now.strftime('%H:%M')} WIB.\n"
            f"⏳ Estimasi kembali: {kembali.strftime('%H:%M')}"
        ),
        reply_markup=tombol_kembali
    )

    await kirim_ke_admins(context,
        f"📤 {user.first_name} keluar untuk {alasan} pukul {now.strftime('%H:%M')} WIB."
    )

# === HANDLE KEMBALI ===
async def handle_kembali(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_kembali_uid

    query = update.callback_query
    await query.answer()
    user = query.from_user
    uid = str(user.id)
    now = datetime.now(TIMEZONE)

    print(f"✅ Tombol kembali diklik oleh {user.first_name} ({uid})")

    if uid == last_kembali_uid:
        print("⏹️ Duplikat klik tombol kembali - diabaikan")
        return
    last_kembali_uid = uid

    if uid not in izin_aktif:
        await query.message.reply_text("❌ Data izin tidak ditemukan.")
        return

    data = izin_aktif.pop(uid)
    simpan_data()

    keluar = data['keluar']
    kembali = data['kembali']
    durasi = now - keluar
    terlambat = now > kembali
    menit_telat = (now - kembali).seconds // 60 if terlambat else 0

    denda = 0
    if 1 <= menit_telat <= 9:
        denda = 50000 * menit_telat
    elif menit_telat >= 10:
        denda = 500000

    pesan = (
        f"👋 {user.first_name} kembali dari {data['alasan']}.\n"
        f"⏱️ Durasi: {str(durasi).split('.')[0]}"
    )
    if denda:
        pesan += f"\n⚠️ Terlambat {menit_telat} menit.\n💸 Denda: Rp{denda:,}"

    await context.bot.send_message(chat_id=query.message.chat_id, text=pesan)
    await kirim_ke_admins(context, pesan)

# === AUTO KEMBALI ===
async def auto_kembali(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE)
    auto_done = []

    for uid, data in izin_aktif.items():
        if now > data['kembali'] + timedelta(minutes=10):
            keluar = data['keluar']
            nama = data['nama']
            alasan = data['alasan']
            durasi = now - keluar
            denda = 500000

            pesan = (
                f"⚠️ {nama} belum kembali sesuai estimasi dan dianggap kembali otomatis.\n"
                f"⏱️ Durasi izin: {str(durasi).split('.')[0]}\n"
                f"💸 Denda: Rp{denda:,}"
            )

            await kirim_ke_admins(context, pesan)
            auto_done.append(uid)

    for uid in auto_done:
        izin_aktif.pop(uid, None)
    if auto_done:
        simpan_data()

# === OPSIONAL ===
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ID kamu: `{update.effective_user.id}`", parse_mode="Markdown")

async def tes_kirim_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await kirim_ke_admins(context, "📢 Tes kirim ke semua admin berhasil!")

# === MAIN ===
def main():
    load_data()
    app_bot = ApplicationBuilder().token(TOKEN).build()

    app_bot.add_handler(CommandHandler("start", show_menu))
    app_bot.add_handler(CommandHandler("id", get_id))
    app_bot.add_handler(CommandHandler("tesadmin", tes_kirim_admin))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, show_menu))
    app_bot.add_handler(CallbackQueryHandler(handle_izin, pattern="^izin_"))
    app_bot.add_handler(CallbackQueryHandler(handle_kembali, pattern="^in_.*$"))  # ← FIX

    app_bot.job_queue.run_repeating(auto_kembali, interval=60, first=10)

    print("✅ BOT AKTIF: dengan izin keluar, kembali, dan denda")
    keep_alive()
    app_bot.run_polling()

if __name__ == "__main__":
    main()
