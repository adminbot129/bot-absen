import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Membuat server web kecil agar Render mendeteksi port terbuka
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot Absen Telegram Aktif!"

def run_flask():
    # Render menggunakan port dari environment variable PORT atau 10000 secara default
    import os
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# 记录员工当前状态
status_karyawan = {}

# 记录请假开始时间 (key: user_id, value: datetime)
waktu_mulai_izin = {}

# 记录请假总次数 (key: (user_id, jenis_izin), value: int)
hitung_izin = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("MASUK KERJA"), KeyboardButton("PULANG KERJA")],
        [KeyboardButton("IZIN MAKAN"), KeyboardButton("IZIN MEROKOK")],
        [KeyboardButton("KEMBALI KURSI")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Silakan pilih tombol absensi di bawah ini:\n"
        "<i>请在下方选择考勤按钮：</i>", 
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    nama = user.full_name
    user_id = user.id
    aksi = update.message.text.strip()
    
    print(f"[DEBUG] Pesan diterima dari {nama} ({user_id}): {aksi}")

    waktu_sekarang = datetime.now()
    waktu_str = waktu_sekarang.strftime("%d %B %Y, %H:%M:%S WIB")
    
    menu_valid = ["MASUK KERJA", "PULANG KERJA", "IZIN MAKAN", "IZIN MEROKOK", "KEMBALI KURSI"]
    
    if aksi in menu_valid:
        sedang_izin = status_karyawan.get(user_id)
        
        # Cek jika belum check-in / belum masuk / sudah pulang
        if aksi in ["IZIN MAKAN", "IZIN MEROKOK", "KEMBALI KURSI"] and not sedang_izin:
            await update.message.reply_text(
                f"⚠️ <b>GAGAL MELAKUKAN AKSI</b>\n"
                f"<i>(操作失败)</i>\n"
                f"────────────────\n"
                f"👤 <b>Nama / 姓名 :</b> {nama}\n"
                f"────────────────\n"
                f"❌ <b>Keterangan / 说明 :</b> Anda belum melakukan <b>MASUK KERJA</b> atau sudah pulang!\n"
                f"<i>(您还没有上班打卡或已经下班，无法进行此操作！)</i>\n"
                f"────────────────\n"
                f"💡 <i>Silakan klik tombol <b>MASUK KERJA</b> terlebih dahulu.\n(请先点击上班打卡按钮。)</i>",
                parse_mode="HTML"
            )
            return

        # Mencegah klik ganda tombol "MASUK KERJA"
        if aksi == "MASUK KERJA" and sedang_izin == "MASUK":
            await update.message.reply_text(
                f"⚠️ <b>SUDAH MASUK KERJA</b>\n"
                f"<i>(已经上班打卡)</i>\n"
                f"────────────────\n"
                f"👤 <b>Nama / 姓名 :</b> {nama}\n"
                f"────────────────\n"
                f"❌ <b>Keterangan / 说明 :</b> Anda sudah melakukan check-in / masuk kerja sebelumnya!\n"
                f"<i>(您之前已经打过上班卡了，请勿重复点击！)</i>",
                parse_mode="HTML"
            )
            return

        # Belum dalam status izin tapi klik kembali kursi
        if aksi == "KEMBALI KURSI" and sedang_izin not in ["IZIN MAKAN", "IZIN MEROKOK"]:
            await update.message.reply_text(
                f"⚠️ <b>GAGAL KEMBALI KURSI</b>\n"
                f"<i>(无法返回座位)</i>\n"
                f"────────────────\n"
                f"👤 <b>Nama / 姓名 :</b> {nama}\n"
                f"────────────────\n"
                f"❌ <b>Keterangan / 说明 :</b> Anda tidak sedang dalam status Izin Makan atau Izin Merokok!\n"
                f"<i>(您当前不在吃饭或抽烟状态，无需点击返回座位！)</i>\n"
                f"────────────────\n"
                f"💡 <i>Tombol ini hanya khusus untuk mengakhiri waktu izin.\n(此按钮专门用于结束请假时间。)</i>",
                parse_mode="HTML"
            )
            return

        # Sedang izin tapi pilih izin lain
        if aksi in ["IZIN MAKAN", "IZIN MEROKOK"] and sedang_izin in ["IZIN MAKAN", "IZIN MEROKOK"]:
            await update.message.reply_text(
                f"⚠️ <b>GAGAL MEMILIH IZIN</b>\n"
                f"<i>(无法选择请假)</i>\n"
                f"────────────────\n"
                f"👤 <b>Nama / 姓名 :</b> {nama}\n"
                f"────────────────\n"
                f"❌ <b>Keterangan / 说明 :</b> Anda saat ini masih tercatat sedang <b>{sedang_izin}</b>.\n"
                f"<i>(您当前记录为：{sedang_izin}。)</i>\n"
                f"────────────────\n"
                f"💡 <i>Silakan klik tombol <b>KEMBALI KURSI</b> terlebih dahulu!\n(请先点击返回座位按钮！)</i>",
                parse_mode="HTML"
            )
            return

        # --- 1. 返回座位 (KEMBALI KURSI) ---
        if aksi == "KEMBALI KURSI":
            jenis_izin_terakhir = sedang_izin
            
            waktu_mulai = waktu_mulai_izin.get(user_id)
            if waktu_mulai:
                selisih_detik = int((waktu_sekarang - waktu_mulai).total_seconds())
                menit_aktual = selisih_detik // 60
                detik_aktual = selisih_detik % 60
                info_durasi_total = f"{menit_aktual} menit {detik_aktual} detik / {menit_aktual}分钟{detik_aktual}秒"
            else:
                info_durasi_total = "Tidak tercatat / 未记录"

            ke_berapa = hitung_izin.get((user_id, jenis_izin_terakhir), 1)
            status_karyawan[user_id] = "MASUK"
            
            detail_isi = (
                f"⏳ <b>Detail Waktu Cekin / 详细请假用时 :</b> {info_durasi_total}\n"
                f"────────────────\n"
                f"🔢 <b>Total Cek In / 总打卡次数 :</b> Ke-{ke_berapa} / 第{ke_berapa}次\n"
                f"────────────────\n"
                f"⏱️ <b>Status / 状态 :</b> Berhasil Kembali ke Kursi\n"
                f"<i>(已返回座位继续工作)</i>"
            )
            pesan_penutup = "Terima kasih, sudah kembali tepat waktu.\n(谢谢您，按时返回。)"

        # --- 2. 上班打卡 (MASUK KERJA) ---
        elif aksi == "MASUK KERJA":
            status_karyawan[user_id] = "MASUK"
            detail_isi = (
                f"⏱️ <b>Status / 状态 :</b> Berhasil Check-in / Masuk Kerja\n"
                f"<i>(上班打卡成功)</i>"
            )
            pesan_penutup = "Selamat bekerja, jaga kedisiplinan!\n(祝您工作愉快，遵守纪律！)"

        # --- 3. 吃饭请假 (IZIN MAKAN - 30分钟) ---
        elif aksi == "IZIN MAKAN":
            status_karyawan[user_id] = aksi
            waktu_mulai_izin[user_id] = waktu_sekarang
            
            kunci_hitung = (user_id, aksi)
            hitung_izin[kunci_hitung] = hitung_izin.get(kunci_hitung, 0) + 1
            ke_berapa = hitung_izin[kunci_hitung]

            detail_isi = (
                f"⏱️ <b>Alokasi Izin / 规定时长 :</b> 30 Menit / 分钟\n"
                f"────────────────\n"
                f"🔢 <b>Total Cek In / 总打卡次数 :</b> Ke-{ke_berapa} / 第{ke_berapa}次"
            )
            pesan_penutup = "Silakan kembali ke kursi tepat waktu.\n(请按时返回座位。)"

        # --- 4. 抽烟请假 (IZIN MEROKOK - 15分钟) ---
        elif aksi == "IZIN MEROKOK":
            status_karyawan[user_id] = aksi
            waktu_mulai_izin[user_id] = waktu_sekarang
            
            kunci_hitung = (user_id, aksi)
            hitung_izin[kunci_hitung] = hitung_izin.get(kunci_hitung, 0) + 1
            ke_berapa = hitung_izin[kunci_hitung]

            detail_isi = (
                f"⏱️ <b>Alokasi Izin / 规定时长 :</b> 15 Menit / 分钟\n"
                f"────────────────\n"
                f"🔢 <b>Total Cek In / 总打卡次数 :</b> Ke-{ke_berapa} / 第{ke_berapa}次"
            )
            pesan_penutup = "Silakan kembali ke kursi tepat waktu.\n(请按时返回座位。)"

        # --- 5. 下班打卡 (PULANG KERJA) ---
        else:
            status_karyawan[user_id] = None
            detail_isi = (
                f"⏱️ <b>Status / 状态 :</b> Selesai Shift / Pulang\n"
                f"<i>(下班 / 班次结束)</i>"
            )
            pesan_penutup = "Terima kasih atas kerja keras hari ini. Hati-hati di jalan.\n(感谢今天的辛勤工作，一路平安。)"

        pesan = (
            f"📋 <b>LAPORAN ABSEN ANGGOTA</b>\n"
            f"<i>(员工考勤报告)</i>\n"
            f"──────────────────────\n"
            f"👤 <b>Nama / 姓名 :</b> {nama}\n"
            f"────────────────\n"
            f"📝 <b>Detail Izin / 详情 :</b> {aksi}\n"
            f"────────────────\n"
            f"⏰ <b>Waktu / 时间 :</b> {waktu_str}\n"
            f"────────────────\n"
            f"{detail_isi}\n"
            f"─────────────────────────\n"
            f"{pesan_penutup}"
        )
        
        await update.message.reply_text(pesan, parse_mode="HTML")

async def main():
    # Menyalakan server web kecil di latar belakang untuk Render
    keep_alive()

    TOKEN = "8929417098:AAHqjy5pdj1vjNkRNUHSmRPzoALTutlsfwA"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot siap dan berjalan stabil...")
    
    # Menjalankan polling dengan aman menggunakan asyncio
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    stop_signal = asyncio.Event()
    try:
        await stop_signal.wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot berhasil dihentikan dengan aman.")
