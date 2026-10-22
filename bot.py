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

        # 2. Mencegah klik ganda tombol "MASUK KERJA"
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

        # 3. Belum dalam status izin tapi klik kembali kursi
        if aksi == "KEMBALI KURSI" and sedang_izin not in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
            await update.message.reply_text(
                f"⚠️ <b>GAGAL KEMBALI KURSI</b>\n"
                f"<i>(无法返回座位)</i>\n"
                f"────────────────\n"
                f"👤 <b>Nama / 姓名 :</b> {nama}\n"
                f"────────────────\n"
                f"❌ <b>Keterangan / 说明 :</b> Anda tidak sedang dalam status Izin Makan atau Izin Merokok/WC!\n"
                f"<i>(您当前不在吃饭或抽烟/WC状态，无需点击返回座位！)</i>",
                parse_mode="HTML"
            )
            return

        # 4. Sedang izin tertentu, tapi malah pilih izin lain (Harus KEMBALI KURSI dulu)
        if aksi in ["IZIN MAKAN", "IZIN MEROKOK/WC"] and sedang_izin in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
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
                f"⏳ <b>Detail Waktu Cekin / 详细请假用时 :</b> {info_durasi_total}\n"
                f"────────────────\n"
                f"🔢 <b>Total Cek In / 总打卡次数 :</b> Ke-{ke_berapa} / 第{ke_berapa}次\n"
                f"────────────────\n"
                f"⏱️ <b>Status / 状态 :</b> Berhasil Kembali ke Kursi\n"
                f"<i>(已返回座位继续工作)</i>"
            )
            pesan_penutup = "Terima kasih, sudah kembali tepat waktu.\n(谢谢您，按时返回。)"

        elif aksi == "MASUK KERJA":
            status_karyawan[user_id] = "MASUK"
            
            # Batas jam masuk kantor (09:30:00 WIB)
            jam_masuk_batas = waktu_sekarang.replace(hour=9, minute=30, second=0, microsecond=0)
            
            if waktu_sekarang > jam_masuk_batas:
                selisih_telat = int((waktu_sekarang - jam_masuk_batas).total_seconds())
                
                # Perhitungan Jam, Menit, dan Detik secara akurat
                jam_telat = selisih_telat // 3600
                sisa_detik = selisih_telat % 3600
                menit_telat = sisa_detik // 60
                detik_telat = sisa_detik % 60
                
                if jam_telat > 0:
                    info_telat = f"{jam_telat} jam {menit_telat} menit {detik_telat} detik / 迟到 {jam_telat}小时{menit_telat}分{detik_telat}秒"
                else:
                    info_telat = f"{menit_telat} menit {detik_telat} detik / 迟到 {menit_telat}分{detik_telat}秒"
                
                detail_isi = (
                    f"⚠️ <b>Status / 状态 :</b> TERLAMBAT / 迟到\n"
                    f"❌ <b>Keterangan :</b> Anda terlambat {info_telat} dari jam masuk (09:30 WIB)\n"
                    f"<i>(您迟到了，超过了规定上班时间 09:30)</i>"
                )
                pesan_penutup = "Harap datang lebih tepat waktu esok hari!\n(希望明天能按时到达！)"
            else:
                detail_isi = (
                    f"⏱️ <b>Status / 状态 :</b> Berhasil Check-in Tepat Waktu\n"
                    f"<i>(准时上班打卡成功)</i>"
                )
                pesan_penutup = "Selamat bekerja, jaga kedisiplinan!\n(祝您工作愉快，遵守纪律！)"

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

        elif aksi == "IZIN MEROKOK/WC":
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

        else: # PULANG KERJA
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
