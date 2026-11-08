import os
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

# Konfigurasi Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8929417098:AAEUOjUMNT2A0O5Px8eHoOKp5zNMc398O7M"
RENDER_URL = "https://bot-absen-z5bs.onrender.com"  # Ganti dengan URL Render kamu tanpa garis miring di akhir

# Inisialisasi Aplikasi Telegram
application = Application.builder().token(TOKEN).build()

# Inisialisasi Flask
app = Flask(__name__)

status_karyawan = {}
waktu_mulai_izin = {}
hitung_izin = {}
waktu_masuk_kerja = {}
tanggal_terakhir_reset = None

WIB = ZoneInfo("Asia/Jakarta")

def cek_dan_reset_harian():
    global tanggal_terakhir_reset
    waktu_sekarang = datetime.now(WIB)
    tanggal_hari_ini = waktu_sekarang.date()
    
    if tanggal_terakhir_reset != tanggal_hari_ini and waktu_sekarang.time() >= time(1, 0, 0):
        status_karyawan.clear()
        waktu_mulai_izin.clear()
        hitung_izin.clear()
        waktu_masuk_kerja.clear()
        tanggal_terakhir_reset = tanggal_hari_ini

async def cek_durasi_izin_berkala(context: ContextTypes.DEFAULT_TYPE):
    waktu_sekarang = datetime.now(WIB)
    for user_id, status in list(status_karyawan.items()):
        if status in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
            waktu_mulai = waktu_mulai_izin.get(user_id)
            if not waktu_mulai:
                continue
            selisih_detik = int((waktu_sekarang - waktu_mulai).total_seconds())
            max_detik = 30 * 60 if status == "IZIN MAKAN" else 10 * 60
            
            if selisih_detik >= max_detik:
                await context.bot.send_message(
                    chat_id=context.job.chat_id,
                    text=f"⚠️ Peringatan: <b>{status}</b> untuk ID {user_id} telah melewati batas waktu!",
                    parse_mode="HTML"
                )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cek_dan_reset_harian()
    chat_id = update.effective_chat.id
    
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if not current_jobs:
        context.job_queue.run_repeating(cek_durasi_izin_berkala, interval=30, first=5, chat_id=chat_id, name=str(chat_id))

    keyboard = [
        [InlineKeyboardButton("MASUK KERJA", callback_data="MASUK KERJA"), InlineKeyboardButton("PULANG KERJA", callback_data="PULANG KERJA")],
        [InlineKeyboardButton("IZIN MAKAN", callback_data="IZIN MAKAN"), InlineKeyboardButton("IZIN MEROKOK/WC", callback_data="IZIN MEROKOK/WC")],
        [InlineKeyboardButton("KEMBALI KURSI", callback_data="KEMBALI KURSI")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Silakan pilih tombol absensi di bawah ini:\n<i>请在下方选择考勤按钮：</i>", 
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cek_dan_reset_harian()
    
    user = query.from_user
    nama = user.full_name
    user_id = user.id
    aksi = query.data
    waktu_sekarang = datetime.now(WIB)
    waktu_str = waktu_sekarang.strftime("%d %B %Y, %H:%M:%S WIB")
    
    sedang_izin = status_karyawan.get(user_id)
    
    if aksi != "MASUK KERJA" and not sedang_izin:
        await query.message.reply_text(f"⚠️ {nama}, Anda belum MASUK KERJA / 尚未上班打卡")
        return

    if aksi == "MASUK KERJA":
        status_karyawan[user_id] = "MASUK"
        waktu_masuk_kerja[user_id] = waktu_sekarang
        pesan = f"✅ <b>{nama}</b> Berhasil Check-in Tepat Waktu pada {waktu_str}"
    elif aksi == "PULANG KERJA":
        status_karyawan[user_id] = None
        pesan = f"👋 <b>{nama}</b> Telah Pulang Kerja pada {waktu_str}"
    elif aksi in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
        status_karyawan[user_id] = aksi
        waktu_mulai_izin[user_id] = waktu_sekarang
        pesan = f"⏳ <b>{nama}</b> Sedang mengambil <b>{aksi}</b> pada {waktu_str}"
    elif aksi == "KEMBALI KURSI":
        status_karyawan[user_id] = "MASUK"
        pesan = f"🎯 <b>{nama}</b> Telah Kembali ke Kursi pada {waktu_str}"
    else:
        pesan = f"📋 {nama} - {aksi}"

    await query.message.reply_text(pesan, parse_mode="HTML")

# Daftarkan handler
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_callback))

@app.route('/')
def home():
    return "Bot Absen Telegram Aktif via Webhook!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    """Endpoint Flask untuk menerima update dari Telegram"""
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return 'OK', 200

if __name__ == "__main__":
    import asyncio
    
    # Inisialisasi dan set webhook otomatis saat bot dinyalakan di Render
    async def setup_webhook():
        await application.initialize()
        await application.bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}")
        await application.start()

    asyncio.run(setup_webhook())

    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
