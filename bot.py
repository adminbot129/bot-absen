import os
from datetime import datetime
from zoneinfo import ZoneInfo
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
waktu_masuk_kerja = {}  # Variabel untuk mencatat waktu masuk kerja

# Zona Waktu Indonesia Barat (WIB / Jakarta)
WIB = ZoneInfo("Asia/Jakarta")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("MASUK KERJA"), KeyboardButton("PULANG KERJA")],
        [KeyboardButton("IZIN MAKAN"), KeyboardButton("IZIN MEROKOK/WC")],
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
    
    # Waktu real-time akurat sesuai zona waktu WIB (Jakarta)
    waktu_sekarang = datetime.now(WIB)
    waktu_str = waktu_sekarang.strftime("%d %B %Y, %H:%M:%S WIB")
    
    menu_valid = ["MASUK KERJA", "PULANG KERJA", "IZIN MAKAN", "IZIN MEROKOK/WC", "KEMBALI KURSI"]
    
    if aksi in menu_valid:
        sedang_izin = status_karyawan.get(user_id)
        
        # 1. Cek jika belum check-in (atau sudah pulang / None) tapi mencoba aksi selain MASUK KERJA
        if aksi != "MASUK KERJA" and not sedang_izin:
            await update.message.reply_text(
                f"<pre>"
                f"┌──────────────────────────────────────┐\n"
                f"│        ⚠️ GAGAL MELAKUKAN AKSI       │\n"
                f"│            (操作失败)                │\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 👤 Nama / 姓名 :                     │\n"
                f"│    {nama:<33} │\n"
                f"│ 📱 ID : {user_id:<28} │\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ❌ Keterangan / 说明 :               │\n"
                f"│    Belum MASUK KERJA / 尚未上班打卡  │\n"
                f"└──────────────────────────────────────┘"
                f"</pre>",
                parse_mode="HTML"
            )
            return

        # 2. Mencegah klik ganda tombol "MASUK KERJA"
        if aksi == "MASUK KERJA" and sedang_izin == "MASUK":
            await update.message.reply_text(
                f"<pre>"
                f"┌──────────────────────────────────────┐\n"
                f"│        ⚠️ SUDAH MASUK KERJA          │\n"
                f"│            (已经上班打卡)            │\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 👤 Nama / 姓名 :                     │\n"
                f"│    {nama:<33} │\n"
                f"│ 📱 ID : {user_id:<28} │\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ❌ Keterangan / 说明 :               │\n"
                f"│    Sudah check-in sebelumnya!        │\n"
                f"└──────────────────────────────────────┘"
                f"</pre>",
                parse_mode="HTML"
            )
            return

        # 3. Belum dalam status izin tapi klik kembali kursi
        if aksi == "KEMBALI KURSI" and sedang_izin not in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
            await update.message.reply_text(
                f"<pre>"
                f"┌──────────────────────────────────────┐\n"
                f"│        ⚠️ GAGAL KEMBALI KURSI        │\n"
                f"│            (无法返回座位)            │\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 👤 Nama / 姓名 :                     │\n"
                f"│    {nama:<33} │\n"
                f"│ 📱 ID : {user_id:<28} │\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ❌ Keterangan / 说明 :               │\n"
                f"│    Tidak sedang dalam status izin!   │\n"
                f"└──────────────────────────────────────┘"
                f"</pre>",
                parse_mode="HTML"
            )
            return

        # 4. Sedang izin tertentu, tapi malah pilih izin lain (Harus KEMBALI KURSI dulu)
        if aksi in ["IZIN MAKAN", "IZIN MEROKOK/WC"] and sedang_izin in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
            await update.message.reply_text(
                f"<pre>"
                f"┌──────────────────────────────────────┐\n"
                f"│        ⚠️ GAGAL MEMILIH IZIN         │\n"
                f"│            (无法选择请假)            │\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 👤 Nama / 姓名 :                     │\n"
                f"│    {nama:<33} │\n"
                f"│ 📱 ID : {user_id:<28} │\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ❌ Status Aktif / 当前状态 :         │\n"
                f"│    {sedang_izin:<33} │\n"
                f"└──────────────────────────────────────┘"
                f"</pre>",
                parse_mode="HTML"
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
                info_durasi_total = f"{menit_aktual} menit {detik_aktual} detik / {menit_aktual}分钟{detik_aktual}秒"
            else:
                info_durasi_total = "Tidak tercatat / 未记录"

            ke_berapa = hitung_izin.get((user_id, jenis_izin_terakhir), 1)
            status_karyawan[user_id] = "MASUK"
            
            detail_isi = (
                f"├──────────────────────────────────────┤\n"
                f"│ ⏱️ Status / 状态 :\n"
                f"│    Berhasil Kembali ke Kursi\n"
                f"│    (已返回座位继续工作)\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⏳ Detail Waktu Izin / 假用时 :\n"
                f"│    {info_durasi_total}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 🔢 Total Cek In / 总打卡次数 :\n"
                f"│    Ke-{ke_berapa} / 第{ke_berapa}次"
            )
            pesan_penutup = "Terima kasih, sudah kembali tepat waktu.\n(谢谢您，按时返回。)"

        elif aksi == "MASUK KERJA":
            status_karyawan[user_id] = "MASUK"
            waktu_masuk_kerja[user_id] = waktu_sekarang  # Catat waktu mulai kerja
            
            # Batas jam masuk kantor (09:30:00 WIB)
            jam_masuk_batas = waktu_sekarang.replace(hour=9, minute=30, second=0, microsecond=0)
            
            if waktu_sekarang > jam_masuk_batas:
                selisih_telat = int((waktu_sekarang - jam_masuk_batas).total_seconds())
                
                jam_telat = selisih_telat // 3600
                sisa_detik = selisih_telat % 3600
                menit_telat = sisa_detik // 60
                detik_telat = sisa_detik % 60
                
                if jam_telat > 0:
                    info_telat = f"{jam_telat} jam {menit_telat} menit {detik_telat} detik / 迟到 {jam_telat}小时{menit_telat}分{detik_telat}秒"
                else:
                    info_telat = f"{menit_telat} menit {detik_telat} detik / 迟到 {menit_telat}分{detik_telat}秒"
                
                detail_isi = (
                    f"├──────────────────────────────────────┤\n"
                    f"│ ⏱️ Status / 状态 :\n"
                    f"│    TERLAMBAT / 迟到\n"
                    f"├──────────────────────────────────────┤\n"
                    f"│ ❌ Keterangan / 说明 :\n"
                    f"│    Terlambat {info_telat}\n"
                    f"│    (超过规定上班时间 09:30)"
                )
                pesan_penutup = "Harap datang lebih tepat waktu esok hari!\n(希望明天能按时到达！)"
            else:
                detail_isi = (
                    f"├──────────────────────────────────────┤\n"
                    f"│ ⏱️ Status / 状态 :\n"
                    f"│    Berhasil Check-in Tepat Waktu\n"
                    f"│    (准时上班打卡成功)"
                )
                pesan_penutup = "Selamat bekerja, jaga kedisiplinan!\n(祝您工作愉快，遵守纪律！)"

        elif aksi == "IZIN MAKAN":
            status_karyawan[user_id] = aksi
            waktu_mulai_izin[user_id] = waktu_sekarang
            kunci_hitung = (user_id, aksi)
            hitung_izin[kunci_hitung] = hitung_izin.get(kunci_hitung, 0) + 1
            ke_berapa = hitung_izin[kunci_hitung]

            detail_isi = (
                f"├──────────────────────────────────────┤\n"
                f"│ ⏱️ Alokasi Izin / 规定时长 :\n"
                f"│    30 Menit / 分钟\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 🔢 Total Cek In / 总打卡次数 :\n"
                f"│    Ke-{ke_berapa} / 第{ke_berapa}次"
            )
            pesan_penutup = "Silakan kembali ke kursi tepat waktu.\n(请按时返回座位。)"

        elif aksi == "IZIN MEROKOK/WC":
            status_karyawan[user_id] = aksi
            waktu_mulai_izin[user_id] = waktu_sekarang
            kunci_hitung = (user_id, aksi)
            hitung_izin[kunci_hitung] = hitung_izin.get(kunci_hitung, 0) + 1
            ke_berapa = hitung_izin[kunci_hitung]

            detail_isi = (
                f"├──────────────────────────────────────┤\n"
                f"│ ⏱️ Alokasi Izin / 规定时长 :\n"
                f"│    15 Menit / 分钟\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 🔢 Total Cek In / 总打卡次数 :\n"
                f"│    Ke-{ke_berapa} / 第{ke_berapa}次"
            )
            pesan_penutup = "Silakan kembali ke kursi tepat waktu.\n(请按时返回座位。)"

        else: # PULANG KERJA
            waktu_masuk = waktu_masuk_kerja.get(user_id)
            if waktu_masuk:
                selisih_kerja = int((waktu_sekarang - waktu_masuk).total_seconds())
                jam_kerja = selisih_kerja // 3600
                sisa_detik_kerja = selisih_kerja % 3600
                menit_kerja = sisa_detik_kerja // 60
                detik_kerja = sisa_detik_kerja % 60
                info_durasi_kerja = f"{jam_kerja} jam {menit_kerja} menit {detik_kerja} detik\n│    ({jam_kerja}小时{menit_kerja}分{detik_kerja}秒)"
            else:
                info_durasi_kerja = "Tidak tercatat / 未记录"

            status_karyawan[user_id] = None
            waktu_masuk_kerja[user_id] = None  # Reset data masuk kerja

            detail_isi = (
                f"├──────────────────────────────────────┤\n"
                f"│ ⏱️ Status / 状态 :\n"
                f"│    Selesai Shift / Pulang\n"
                f"│    (下班 / 班次结束)\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⏳ Total Waktu Kerja / 总工作时长 :\n"
                f"│    {info_durasi_kerja}"
            )
            pesan_penutup = "Terima kasih atas kerja keras hari ini.\nHati-hati di jalan.\n(感谢今天的辛勤工作，一路平安。)"

        pesan = (
            f"<pre>"
            f"┌──────────────────────────────────────┐\n"
            f"│        📋 LAPORAN ABSEN ANGGOTA      │\n"
            f"│             (员工考勤报告)           │\n"
            f"├──────────────────────────────────────┤\n"
            f"│ 👤 Nama / 姓名 :                     │\n"
            f"│    {nama:<33} │\n"
            f"│ 📱 ID : {str(user_id):<28} │\n"
            f"├──────────────────────────────────────┤\n"
            f"│ 📝 Detail / 详情 :                   │\n"
            f"│    {aksi:<33} │\n"
            f"├──────────────────────────────────────┤\n"
            f"│ ⏰ Waktu / 时间 :                    │\n"
            f"│    {waktu_str:<33} │\n"
            f"{detail_isi}\n"
            f"└──────────────────────────────────────┘\n"
            f"{pesan_penutup}"
            f"</pre>"
        )
        
        await update.message.reply_text(pesan, parse_mode="HTML")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    import threading
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    TOKEN = "8929417098:AAHqjy5pdj1vjNkRNUHSmRPzoALTutlsfwA"
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot Telegram mulai berjalan...")
    application.run_polling()
