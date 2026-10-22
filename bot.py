import os
from datetime import datetime
from flask import Flask
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Inisialisasi Flask untuk port Render
app = Flask('')

@app.route('/')
def home():
    return "Bot Absen Telegram Aktif!"

# Status penyimpanan data sementara
status_karyawan = {}
waktu_mulai_izin = {}
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
    
    waktu_sekarang = datetime.now()
    waktu_str = waktu_sekarang.strftime("%d %B %Y, %H:%M:%S WIB")
    
    menu_valid = ["MASUK KERJA", "PULANG KERJA", "IZIN MAKAN", "IZIN MEROKOK", "KEMBALI KURSI"]
    
    if aksi in menu_valid:
        sedang_izin = status_karyawan.get(user_id)
        
        if aksi in ["IZIN MAKAN", "IZIN MEROKOK", "KEMBALI KURSI"] and not sedang_izin:
            await update.message.reply_text(
                f"⚠️ <b>GAGAL MELAKUKAN AKSI</b>\n"
                f"<i>(操作失败)</i>\n"
                f"────────────────\n"
                f"👤 <b>Nama / 姓名 :</b> {nama}\n"
                f"────────────────\n"
                f"❌ <b>Keterangan / 说明 :</b> Anda belum melakukan <b>MASUK KERJA</b> atau sudah pulang!\n"
                f"<i>(您还没有上班打卡或已经下班，无法进行此操作！)</i>",
                parse_mode="HTML"
            )
            return

        if aksi == "MASUK KERJA" and sedang_izin == "MASUK":
            await update.message.reply_text(
                f"⚠️ <b>SUDAH MASUK KERJA</b>\n"
                f"<i>(已经上班打卡)</i>\n"
                f"❌ Anda sudah melakukan check-in / masuk kerja sebelumnya!",
                parse_mode="HTML"
            )
            return

        if aksi == "KEMBALI KURSI" and sedang_izin not in ["IZIN MAKAN", "IZIN MEROKOK"]:
            await update.message.reply_text(
                f"⚠️ <b>GAGAL KEMBALI KURSI</b>\n"
                f"❌ Anda tidak sedang dalam status Izin Makan atau Izin Merokok!",
                parse_mode="HTML"
            )
            return

        if aksi == "KEMBALI KURSI":
            jenis_izin_terakhir = sedang_izin
            waktu_mulai = waktu_mulai_izin.get(user_id)
            if waktu_mulai:
                selisih_detik = int((waktu_sekarang - waktu_mulai).total_seconds())
                menit_aktual = selisih_detik // 60
                detik_aktual = selisih_detik % 60
                info_durasi_total = f"{menit_aktual} menit {detik_aktual} detik"
            else:
                info_durasi_total = "Tidak tercatat"

            ke_berapa = hitung_izin.get((user_id, jenis_izin_terakhir), 1)
            status_karyawan[user_id] = "MASUK"
            detail_isi = f"⏳ <b>Durasi:</b> {info_durasi_total}\n🔢 <b>Total:</b> Ke-{ke_berapa}"
            pesan_penutup = "Terima kasih, sudah kembali tepat waktu."

        elif aksi == "MASUK KERJA":
            status_karyawan[user_id] = "MASUK"
            detail_isi = "⏱️ <b>Status:</b> Berhasil Check-in / Masuk Kerja"
            pesan_penutup = "Selamat bekerja, jaga kedisiplinan!"

        elif aksi in ["IZIN MAKAN", "IZIN MEROKOK"]:
            status_karyawan[user_id] = aksi
            waktu_mulai_izin[user_id] = waktu_sekarang
            kunci_hitung = (user_id, aksi)
            hitung_izin[kunci_hitung] = hitung_izin.get(kunci_hitung, 0) + 1
            ke_berapa = hitung_izin[kunci_hitung]
            durasi_teks = "30 Menit" if aksi == "IZIN MAKAN" else "15 Menit"
            detail_isi = f"⏱️ <b>Alokasi:</b> {durasi_teks}\n🔢 <b>Total:</b> Ke-{ke_berapa}"
            pesan_penutup = "Silakan kembali ke kursi tepat waktu."

        else:
            status_karyawan[user_id] = None
            detail_isi = "⏱️ <b>Status:</b> Selesai Shift / Pulang"
            pesan_penutup = "Terima kasih atas kerja keras hari ini."

        pesan = (
            f"📋 <b>LAPORAN ABSEN ANGGOTA</b>\n"
            f"👤 <b>Nama:</b> {nama}\n"
            f"📝 <b>Detail:</b> {aksi}\n"
            f"⏰ <b>Waktu:</b> {waktu_str}\n"
            f"────────────────\n"
            f"{detail_isi}\n"
            f"────────────────\n"
            f"{pesan_penutup}"
        )
        await update.message.reply_text(pesan, parse_mode="HTML")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    import threading
    # Jalankan Flask di background thread agar tidak memblokir bot Telegram
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    TOKEN = "8929417098:AAHqjy5pdj1vjNkRNUHSmRPzoALTutlsfwA"
    
    # Jalankan bot Telegram menggunakan run_polling() bawaan yang stabil
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot Telegram mulai berjalan...")
    application.run_polling()
