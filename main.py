# ... [potongan atas tidak diubah, tetap sama dengan yang kamu kirim] ...
# Hanya bagian `handle_kembali` dan `auto_kembali` yang diubah sesuai permintaan kamu

# === HANDLE KEMBALI MANUAL ===
async def handle_kembali(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_kembali_uid

    query = update.callback_query
    await query.answer()
    user = query.from_user
    uid = str(user.id)
    now = datetime.now(TIMEZONE)

    if uid == last_kembali_uid:
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

# === AUTO KEMBALI JIKA LEBIH 10 MENIT ===
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
