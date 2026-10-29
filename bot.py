import os
from datetime import datetime, time
from zoneinfo import ZoneInfo
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

# Inisialisasi Flask untuk port Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Absen Telegram Aktif!"

# Status penyimpanan data sementara
status_karyawan = {}
waktu_mulai_izin = {}
hitung_izin = {}
waktu_masuk_kerja = {}
tanggal_terakhir_reset = None

# Zona Waktu Indonesia Barat (WIB / Jakarta)
WIB = ZoneInfo("Asia/Jakarta")

# Fungsi untuk mereset seluruh data absensi dan hitungan harian tepat jam 01:00 WIB
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
        print(f"[AUTO-RESET] Data absensi berhasil di-reset pada {waktu_sekarang.strftime('%Y-%m-%d %H:%M:%S')}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cek_dan_reset_harian()
    
    keyboard = [
        [InlineKeyboardButton("MASUK KERJA", callback_data="MASUK KERJA"), InlineKeyboardButton("PULANG KERJA", callback_data="PULANG KERJA")],
        [InlineKeyboardButton("IZIN MAKAN", callback_data="IZIN MAKAN"), InlineKeyboardButton("IZIN MEROKOK/WC", callback_data="IZIN MEROKOK/WC")],
        [InlineKeyboardButton("KEMBALI KURSI", callback_data="KEMBALI KURSI")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Silakan pilih tombol absensi di bawah ini:\n"
        "<i>请在下方选择考勤按钮：</i>", 
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cek_dan_reset_harian()
    
    user = query.from_user
    nama = user.full_name
    user_id = user.id
    aksi = query.data
    
    waktu_sekarang = datetime.now(WIB)
    waktu_str = waktu_sekarang.strftime("%m/%d %H:%M:%S")
    
    sedang_izin = status_karyawan.get(user_id)
    
    # Validasi Dasar (Menggunakan tanda ⚠️)
    if aksi != "MASUK KERJA" and not sedang_izin:
        await query.message.reply_text(
            f"Pengguna: {nama}\n"
            f"ID Pengguna: {user_id}\n"
            f"----------------------------------------\n"
            f"⚠️ Gagal: Belum MASUK KERJA / 尚未上班打卡",
            reply_to_message_id=query.message.message_id
        )
        return

    if aksi == "MASUK KERJA" and sedang_izin == "MASUK":
        await query.message.reply_text(
            f"Pengguna: {nama}\n"
            f"ID Pengguna: {user_id}\n"
            f"----------------------------------------\n"
            f"⚠️ Gagal: Sudah check-in sebelumnya / 已经上班打卡",
            reply_to_message_id=query.message.message_id
        )
        return

    if aksi == "KEMBALI KURSI" and sedang_izin not in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
        await query.message.reply_text(
            f"Pengguna: {nama}\n"
            f"ID Pengguna: {user_id}\n"
            f"----------------------------------------\n"
            f"⚠️ Gagal: Tidak sedang dalam status izin / 无法返回座位",
            reply_to_message_id=query.message.message_id
        )
        return

    if aksi in ["IZIN MAKAN", "IZIN MEROKOK/WC"] and sedang_izin in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
        await query.message.reply_text(
            f"Pengguna: {nama}\n"
            f"ID Pengguna: {user_id}\n"
            f"----------------------------------------\n"
            f"⚠️ Gagal: Sedang dalam status izin lain / 当前状态: {sedang_izin}",
            reply_to_message_id=query.message.message_id
        )
        return

    # --- FITUR BATASAN MAKSIMAL 3 ORANG IZIN BERBARENGAN ---
    if aksi in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
        jumlah_orang_izin = sum(1 for status in status_karyawan.values() if status in ["IZIN MAKAN", "IZIN MEROKOK/WC"])
        
        if sedang_izin not in ["IZIN MAKAN", "IZIN MEROKOK/WC"] and jumlah_orang_izin >= 3:
            await query.message.reply_text(
                f"Pengguna: {nama}\n"
                f"ID Pengguna: {user_id}\n"
                f"----------------------------------------\n"
                f"⚠️ Gagal: Kuota izin penuh (Maksimal 3 orang)\n"
                f"当前请假人数已满（最多3人），请稍候再试。",
                reply_to_message_id=query.message.message_id
            )
            return

    # --- Eksekusi Logika Aksi ---
    if aksi == "KEMBALI KURSI":
        jenis_izin_terakhir = sedang_izin
        waktu_mulai = waktu_mulai_izin.get(user_id)
        if waktu_mulai:
            selisih_detik = int((waktu_sekarang - waktu_mulai).total_seconds())
            menit_aktual = selisih_detik // 60
            detik_aktual = selisih_detik % 60
            info_durasi = f"{menit_aktual} menit {detik_aktual} detik ({menit_aktual}分钟{detik_aktual}秒)"
        else:
            info_durasi = "Tidak tercatat / 未记录"

        ke_berapa = hitung_izin.get((user_id, jenis_izin_terakhir), 1)
        status_karyawan[user_id] = "MASUK"
        
        teks_laporan = (
            f"Pengguna: {nama}\n"
            f"ID Pengguna: {user_id}\n"
            f"----------------------------------------\n"
            f"✅ Berhasil Kembali ke Kursi: {waktu_str}\n"
            f"Perhatian: Durasi izin {info_durasi} (Ke-{ke_berapa})"
        )

    elif aksi == "MASUK KERJA":
        status_karyawan[user_id] = "MASUK"
        waktu_masuk_kerja[user_id] = waktu_sekarang  
        jam_masuk_batas = waktu_sekarang.replace(hour=9, minute=30, second=0, microsecond=0)
        
        if waktu_sekarang > jam_masuk_batas:
            selisih_telat = int((waktu_sekarang - jam_masuk_batas).total_seconds())
            menit_telat = selisih_telat // 60
            teks_laporan = (
                f"Pengguna: {nama}\n"
                f"ID Pengguna: {user_id}\n"
                f"----------------------------------------\n"
                f"⚠️ Terlambat Check-in: {waktu_str}\n"
                f"Perhatian: Anda terlambat {menit_telat} menit (超过规定上班时间 09:30)"
            )
        else:
            teks_laporan = (
                f"Pengguna: {nama}\n"
                f"ID Pengguna: {user_id}\n"
                f"----------------------------------------\n"
                f"✅ Check-in Berhasil: Tepat Waktu - {waktu_str}\n"
                f"Perhatian: Selamat bekerja dengan disiplin!"
            )

    elif aksi == "IZIN MAKAN":
        status_karyawan[user_id] = aksi
        waktu_mulai_izin[user_id] = waktu_sekarang
        kunci_hitung = (user_id, aksi)
        hitung_izin[kunci_hitung] = hitung_izin.get(kunci_hitung, 0) + 1
        ke_berapa = hitung_izin[kunci_hitung]

        teks_laporan = (
            f"Pengguna: {nama}\n"
            f"ID Pengguna: {user_id}\n"
            f"----------------------------------------\n"
            f"✅ Check-in Berhasil: Izin Makan - {waktu_str}\n"
            f"Perhatian: Ini adalah check-in ke-{ke_berapa} Izin Makan Anda"
        )

    elif aksi == "IZIN MEROKOK/WC":
        status_karyawan[user_id] = aksi
        waktu_mulai_izin[user_id] = waktu_sekarang
        kunci_hitung = (user_id, aksi)
        hitung_izin[kunci_hitung] = hitung_izin.get(kunci_hitung, 0) + 1
        ke_berapa = hitung_izin[kunci_hitung]

        teks_laporan = (
            f"Pengguna: {nama}\n"
            f"ID Pengguna: {user_id}\n"
            f"----------------------------------------\n"
            f"✅ Check-in Berhasil: Ke Kamar Mandi / Merokok - {waktu_str}\n"
            f"Perhatian: Ini adalah check-in ke-{ke_berapa} Ke Kamar Mandi Anda"
        )

    else: # PULANG KERJA
        waktu_masuk = waktu_masuk_kerja.get(user_id)
        if waktu_masuk:
            selisih_kerja = int((waktu_sekarang - waktu_masuk).total_seconds())
            jam_kerja = selisih_kerja // 3600
            menit_kerja = (selisih_kerja % 3600) // 60
            info_durasi_kerja = f"{jam_kerja} jam {menit_kerja} menit"
        else:
            info_durasi_kerja = "Tidak tercatat"

        status_karyawan[user_id] = None
        waktu_masuk_kerja[user_id] = None  

        teks_laporan = (
            f"Pengguna: {nama}\n"
            f"ID Pengguna: {user_id}\n"
            f"----------------------------------------\n"
            f"✅ Selesai Shift / Pulang: {waktu_str}\n"
            f"Perhatian: Total waktu kerja Anda {info_durasi_kerja}. Hati-hati di jalan!"
        )

    await query.message.reply_text(
        teks_laporan, 
        reply_to_message_id=query.message.message_id
    )

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    import threading
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    TOKEN = os.environ.get("TOKEN", "8929417098:AAHRiyhPpxEI1uHZb3Df3Yb5-P8V29Q6ZNg")

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot Telegram mulai berjalan dengan pemberitahuan peringatan ⚠️...")
    application.run_polling()
