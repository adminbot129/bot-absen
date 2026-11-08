import os
import logging
import html
import threading

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import Flask

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==================================================
# KONFIGURASI
# ==================================================

TOKEN = "8929417098:AAEUOjUMNT2A0O5Px8eHoOKp5zNMc398O7M"

WIB = ZoneInfo("Asia/Jakarta")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# ==================================================
# FLASK UNTUK RENDER
# ==================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Absen Telegram Aktif!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


# ==================================================
# PENYIMPANAN DATA
# ==================================================

status_karyawan = {}
waktu_mulai_izin = {}
hitung_izin = {}
waktu_masuk_kerja = {}

tanggal_terakhir_reset = None


# ==================================================
# RESET DATA HARIAN
# ==================================================

def cek_dan_reset_harian():
    global tanggal_terakhir_reset

    waktu_sekarang = datetime.now(WIB)
    tanggal_hari_ini = waktu_sekarang.date()

    if (
        tanggal_terakhir_reset != tanggal_hari_ini
        and waktu_sekarang.time() >= time(1, 0, 0)
    ):
        status_karyawan.clear()
        waktu_mulai_izin.clear()
        hitung_izin.clear()
        waktu_masuk_kerja.clear()

        tanggal_terakhir_reset = tanggal_hari_ini

        print(
            f"[AUTO-RESET] Data absensi berhasil di-reset "
            f"pada {waktu_sekarang.strftime('%Y-%m-%d %H:%M:%S')}"
        )


# ==================================================
# PENGINGAT OTOMATIS IZIN
# ==================================================

async def cek_durasi_izin_berkala(
    context: ContextTypes.DEFAULT_TYPE
):
    waktu_sekarang = datetime.now(WIB)

    for user_id, status in list(status_karyawan.items()):

        if status not in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:
            continue

        waktu_mulai = waktu_mulai_izin.get(user_id)

        if not waktu_mulai:
            continue

        selisih_detik = int(
            (waktu_sekarang - waktu_mulai).total_seconds()
        )

        if status == "IZIN MAKAN":
            durasi_max = timedelta(minutes=30)
            max_detik = 30 * 60
            warning_1_detik = 29 * 60
        else:
            durasi_max = timedelta(minutes=10)
            max_detik = 10 * 60
            warning_1_detik = 9 * 60

        warning_3_detik = max_detik + (5 * 60)
        warning_4_mulai = max_detik + (6 * 60)

        waktu_target_kembali = waktu_mulai + durasi_max

        if selisih_detik > max_detik:
            lebih_detik = selisih_detik - max_detik

            jam_lebih = lebih_detik // 3600
            sisa_det_lebih = lebih_detik % 3600
            menit_lebih = sisa_det_lebih // 60
            detik_lebih = sisa_det_lebih % 60

            info_kelebihan = (
                f"{jam_lebih} jam {menit_lebih} menit "
                f"{detik_lebih} detik WIB / 超时 "
                f"{jam_lebih}小时{menit_lebih}分{detik_lebih}秒"
            )
        else:
            info_kelebihan = "Belum lewat batas / 尚未超时"

        job_data = context.job.data

        if job_data is None:
            context.job.data = {}
            job_data = context.job.data

        user_key_warn1 = f"{user_id}_warn1"
        user_key_warn2 = f"{user_id}_warn2"
        user_key_warn3 = f"{user_id}_warn3"
        user_key_spam_terakhir = f"{user_id}_spam_terakhir"

        pesan_notif = None

        # PERINGATAN 1 MENIT SEBELUM BATAS

        if (
            warning_1_detik <= selisih_detik < max_detik
            and not job_data.get(user_key_warn1)
        ):
            job_data[user_key_warn1] = True

            pesan_notif = (
                f"<pre>"
                f"┌──────────────────────────────────────┐\n"
                f"│        ⚠️ PERINGATAN WAKTU IZIN        \n"
                f"│            (请假时间警告)            \n"
                f"├──────────────────────────────────────┤\n"
                f"│ 👤 Nama / 姓名 :\n"
                f"    Karyawan / 员工 (ID: {user_id})\n"
                f"│ 📱 ID : {user_id}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 📝 Detail / 详情 :\n"
                f"    {status}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⏰ Waktu Mulai / 开始时间 :\n"
                f"    {waktu_mulai.strftime('%d %B %Y, %H:%M:%S WIB')}\n"
                f"│ ⏰ Target Kembali / 应回时间 :\n"
                f"    {waktu_target_kembali.strftime('%d %B %Y, %H:%M:%S WIB')}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⚠️ Keterangan / 说明 :\n"
                f"    Waktu izin tersisa 1 menit lagi!\n"
                f"    请注意：请假时间只剩1分钟！\n"
                f"└──────────────────────────────────────┘"
                f"</pre>"
            )

        # PERINGATAN WAKTU IZIN HABIS

        elif (
            max_detik <= selisih_detik < warning_3_detik
            and not job_data.get(user_key_warn2)
        ):
            job_data[user_key_warn2] = True

            pesan_notif = (
                f"<pre>"
                f"┌──────────────────────────────────────┐\n"
                f"│        🚨 WAKTU IZIN TELAH HABIS       \n"
                f"│             (请假时间已到)           \n"
                f"├──────────────────────────────────────┤\n"
                f"│ 👤 Nama / 姓名 :\n"
                f"    Karyawan / 员工 (ID: {user_id})\n"
                f"│ 📱 ID : {user_id}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 📝 Detail / 详情 :\n"
                f"    {status}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⏰ Waktu Mulai / 开始时间 :\n"
                f"    {waktu_mulai.strftime('%d %B %Y, %H:%M:%S WIB')}\n"
                f"│ ⏰ Seharusnya Kembali / 应回时间 :\n"
                f"    {waktu_target_kembali.strftime('%d %B %Y, %H:%M:%S WIB')}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⚠️ Keterangan / 说明 :\n"
                f"    Batas waktu izin sudah habis!\n"
                f"    Segera tekan KEMBALI KURSI!\n"
                f"    时间已到，请立刻返回座位打卡！\n"
                f"└──────────────────────────────────────┘"
                f"</pre>"
            )

        # PERINGATAN TERLAMBAT 5 MENIT

        elif (
            warning_3_detik <= selisih_detik < warning_4_mulai
            and not job_data.get(user_key_warn3)
        ):
            job_data[user_key_warn3] = True

            pesan_notif = (
                f"<pre>"
                f"┌──────────────────────────────────────┐\n"
                f"│        🔥 PERINGATAN KERAS           \n"
                f"│            (严重超时警告)            \n"
                f"├──────────────────────────────────────┤\n"
                f"│ 👤 Nama / 姓名 :\n"
                f"    Karyawan / 员工 (ID: {user_id})\n"
                f"│ 📱 ID : {user_id}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ 📝 Detail / 详情 :\n"
                f"    {status}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⏰ Waktu Mulai / 开始时间 :\n"
                f"    {waktu_mulai.strftime('%d %B %Y, %H:%M:%S WIB')}\n"
                f"│ ⏰ Seharusnya Kembali / 应回时间 :\n"
                f"    {waktu_target_kembali.strftime('%d %B %Y, %H:%M:%S WIB')}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⏳ Kelebihan Waktu / 超时时长 :\n"
                f"    {info_kelebihan}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⚠️ Keterangan / 说明 :\n"
                f"    Terlambat lebih dari 5 menit!\n"
                f"    超时超过5分钟未返回岗位！\n"
                f"└──────────────────────────────────────┘"
                f"</pre>"
            )

        # PERINGATAN DIULANG SETIAP MENIT

        elif selisih_detik >= warning_4_mulai:

            waktu_terakhir_spam = job_data.get(
                user_key_spam_terakhir,
                0
            )

            if selisih_detik - waktu_terakhir_spam >= 60:

                job_data[user_key_spam_terakhir] = selisih_detik

                pesan_notif = (
                    f"<pre>"
                    f"┌──────────────────────────────────────┐\n"
                    f"│        📢 PANGGILAN DARURAT (SPAM)     \n"
                    f"│            (紧急呼叫与催促)          \n"
                    f"├──────────────────────────────────────┤\n"
                    f"│ 👤 Nama / 姓名 :\n"
                    f"    Karyawan / 员工 (ID: {user_id})\n"
                    f"│ 📱 ID : {user_id}\n"
                    f"├──────────────────────────────────────┤\n"
                    f"│ 📝 Detail / 详情 :\n"
                    f"    {status}\n"
                    f"├──────────────────────────────────────┤\n"
                    f"│ ⏰ Waktu Mulai / 开始时间 :\n"
                    f"    {waktu_mulai.strftime('%d %B %Y, %H:%M:%S WIB')}\n"
                    f"│ ⏰ Seharusnya Kembali / 应回时间 :\n"
                    f"    {waktu_target_kembali.strftime('%d %B %Y, %H:%M:%S WIB')}\n"
                    f"├──────────────────────────────────────┤\n"
                    f"│ ⏳ Kelebihan Waktu / 超时时长 :\n"
                    f"    {info_kelebihan}\n"
                    f"├──────────────────────────────────────┤\n"
                    f"│ ⚠️ Keterangan / 说明 :\n"
                    f"    Belum kembali! Peringatan diulang!\n"
                    f"    超时未归！每分钟持续催促中！\n"
                    f"└──────────────────────────────────────┘"
                    f"</pre>"
                )

        if pesan_notif:
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=pesan_notif,
                parse_mode="HTML"
            )


# ==================================================
# PAPAN KETIK TELEGRAM
# ==================================================

def buat_keyboard():

    keyboard = [
        ["MASUK KERJA", "PULANG KERJA"],
        ["IZIN MAKAN", "IZIN MEROKOK/WC"],
        ["KEMBALI KURSI"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True
    )


# ==================================================
# PERINTAH START
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    cek_dan_reset_harian()

    chat_id = update.effective_chat.id

    if context.job_queue is not None:

        current_jobs = context.job_queue.get_jobs_by_name(
            str(chat_id)
        )

        if not current_jobs:

            context.job_queue.run_repeating(
                cek_durasi_izin_berkala,
                interval=30,
                first=5,
                chat_id=chat_id,
                name=str(chat_id)
            )

    else:
        logger.error(
            "JobQueue tidak tersedia. Pasang dependency "
            "'python-telegram-bot[job-queue]' agar pengingat otomatis aktif."
        )

    await update.message.reply_text(
        "Silakan pilih tombol absensi di bawah ini:\n"
        "<i>请在下方选择考勤按钮：</i>",
        reply_markup=buat_keyboard(),
        parse_mode="HTML"
    )


# ==================================================
# PROSES PILIHAN TOMBOL ABSENSI
# ==================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    cek_dan_reset_harian()

    if not update.message or not update.effective_user:
        return

    user = update.effective_user

    nama = html.escape(user.full_name)
    user_id = user.id

    aksi = update.message.text.strip()

    waktu_sekarang = datetime.now(WIB)

    waktu_str = waktu_sekarang.strftime(
        "%d %B %Y, %H:%M:%S WIB"
    )

    sedang_izin = status_karyawan.get(user_id)

    pilihan_valid = [
        "MASUK KERJA",
        "PULANG KERJA",
        "IZIN MAKAN",
        "IZIN MEROKOK/WC",
        "KEMBALI KURSI"
    ]

    if aksi not in pilihan_valid:
        return

    # ----------------------------------------------
    # VALIDASI BELUM MASUK KERJA
    # ----------------------------------------------

    if aksi != "MASUK KERJA" and not sedang_izin:

        await update.message.reply_text(
            f"<pre>"
            f"┌──────────────────────────────────────┐\n"
            f"│        ⚠️ GAGAL MELAKUKAN AKSI        \n"
            f"│            (操作失败)                \n"
            f"├──────────────────────────────────────┤\n"
            f"│ 👤 Nama / 姓名 :\n"
            f"    {nama}\n"
            f"│ 📱 ID : {user_id}\n"
            f"├──────────────────────────────────────┤\n"
            f"│ ⚠️ Keterangan / 说明 :\n"
            f"    Belum MASUK KERJA / 尚未上班打卡\n"
            f"└──────────────────────────────────────┘"
            f"</pre>",
            parse_mode="HTML"
        )

        return

    # ----------------------------------------------
    # VALIDASI SUDAH MASUK KERJA
    # ----------------------------------------------

    if aksi == "MASUK KERJA" and sedang_izin == "MASUK":

        await update.message.reply_text(
            f"<pre>"
            f"┌──────────────────────────────────────┐\n"
            f"│        ⚠️ SUDAH MASUK KERJA          \n"
            f"│            (已经上班打卡)            \n"
            f"├──────────────────────────────────────┤\n"
            f"│ 👤 Nama / 姓名 :\n"
            f"    {nama}\n"
            f"│ 📱 ID : {user_id}\n"
            f"├──────────────────────────────────────┤\n"
            f"│ ⚠️ Keterangan / 说明 :\n"
            f"    Sudah check-in sebelumnya!\n"
            f"└──────────────────────────────────────┘"
            f"</pre>",
            parse_mode="HTML"
        )

        return

    # ----------------------------------------------
    # VALIDASI KEMBALI KURSI
    # ----------------------------------------------

    if aksi == "KEMBALI KURSI" and sedang_izin not in [
        "IZIN MAKAN",
        "IZIN MEROKOK/WC"
    ]:

        await update.message.reply_text(
            f"<pre>"
            f"┌──────────────────────────────────────┐\n"
            f"│        ⚠️ GAGAL KEMBALI KURSI        \n"
            f"│            (无法返回座位)            \n"
            f"├──────────────────────────────────────┤\n"
            f"│ 👤 Nama / 姓名 :\n"
            f"    {nama}\n"
            f"│ 📱 ID : {user_id}\n"
            f"├──────────────────────────────────────┤\n"
            f"│ ⚠️ Keterangan / 说明 :\n"
            f"    Tidak sedang dalam status izin!\n"
            f"└──────────────────────────────────────┘"
            f"</pre>",
            parse_mode="HTML"
        )

        return

    # ----------------------------------------------
    # VALIDASI SEDANG IZIN
    # ----------------------------------------------

    if aksi in ["IZIN MAKAN", "IZIN MEROKOK/WC"] and sedang_izin in [
        "IZIN MAKAN",
        "IZIN MEROKOK/WC"
    ]:

        await update.message.reply_text(
            f"<pre>"
            f"┌──────────────────────────────────────┐\n"
            f"│        ⚠️ GAGAL MEMILIH IZIN         \n"
            f"│            (无法选择请假)            \n"
            f"├──────────────────────────────────────┤\n"
            f"│ 👤 Nama / 姓名 :\n"
            f"    {nama}\n"
            f"│ 📱 ID : {user_id}\n"
            f"├──────────────────────────────────────┤\n"
            f"│ ⚠️ Status Aktif / 当前状态 :\n"
            f"    {sedang_izin}\n"
            f"└──────────────────────────────────────┘"
            f"</pre>",
            parse_mode="HTML"
        )

        return

    # ----------------------------------------------
    # BATAS MAKSIMAL 3 ORANG IZIN
    # ----------------------------------------------

    if aksi in ["IZIN MAKAN", "IZIN MEROKOK/WC"]:

        jumlah_orang_izin = sum(
            1
            for status in status_karyawan.values()
            if status in ["IZIN MAKAN", "IZIN MEROKOK/WC"]
        )

        if (
            sedang_izin not in ["IZIN MAKAN", "IZIN MEROKOK/WC"]
            and jumlah_orang_izin >= 3
        ):

            await update.message.reply_text(
                f"<pre>"
                f"┌──────────────────────────────────────┐\n"
                f"│        ⚠️ KUOTA IZIN PENUH           \n"
                f"│            (请假名额已满)            \n"
                f"├──────────────────────────────────────┤\n"
                f"│ 👤 Nama / 姓名 :\n"
                f"    {nama}\n"
                f"│ 📱 ID : {user_id}\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⚠️ Keterangan / 说明 :\n"
                f"    Sedang Izin: 3/3 Orang (Penuh)\n"
                f"    当前请假人数已满 (3/3)\n"
                f"└──────────────────────────────────────┘"
                f"</pre>",
                parse_mode="HTML"
            )

            return

    # ----------------------------------------------
    # KEMBALI KURSI
    # ----------------------------------------------

    if aksi == "KEMBALI KURSI":

        jenis_izin_terakhir = sedang_izin

        waktu_mulai = waktu_mulai_izin.get(user_id)

        if waktu_mulai:

            selisih_detik = int(
                (waktu_sekarang - waktu_mulai).total_seconds()
            )

            menit_aktual = selisih_detik // 60
            detik_aktual = selisih_detik % 60

            info_durasi_total = (
                f"{menit_aktual} menit {detik_aktual} detik / "
                f"{menit_aktual}分钟{detik_aktual}秒"
            )

        else:
            info_durasi_total = "Tidak tercatat / 未记录"

        ke_berapa = hitung_izin.get(
            (user_id, jenis_izin_terakhir),
            1
        )

        status_karyawan[user_id] = "MASUK"

        waktu_mulai_izin.pop(user_id, None)

        detail_isi = (
            f"├──────────────────────────────────────┤\n"
            f"│ ⏱️ Status / 状态 :\n"
            f"    Berhasil Kembali ke Kursi\n"
            f"    (已返回座位继续工作)\n"
            f"├──────────────────────────────────────┤\n"
            f"│ ⏳ Detail Waktu Izin / 假用时 :\n"
            f"    {info_durasi_total}\n"
            f"├──────────────────────────────────────┤\n"
            f"│ 🔢 Total Cek In / 总打卡次数 :\n"
            f"    Ke-{ke_berapa} / 第{ke_berapa}次"
        )

        pesan_penutup = (
            "Terima kasih, sudah kembali tepat waktu.\n"
            "(谢谢您，按时返回。)"
        )

    # ----------------------------------------------
    # MASUK KERJA
    # ----------------------------------------------

    elif aksi == "MASUK KERJA":

        status_karyawan[user_id] = "MASUK"

        waktu_masuk_kerja[user_id] = waktu_sekarang

        jam_masuk_batas = waktu_sekarang.replace(
            hour=9,
            minute=30,
            second=0,
            microsecond=0
        )

        if waktu_sekarang > jam_masuk_batas:

            selisih_telat = int(
                (waktu_sekarang - jam_masuk_batas).total_seconds()
            )

            jam_telat = selisih_telat // 3600
            sisa_detik = selisih_telat % 3600
            menit_telat = sisa_detik // 60
            detik_telat = sisa_detik % 60

            if jam_telat > 0:

                info_telat = (
                    f"{jam_telat} jam {menit_telat} menit "
                    f"{detik_telat} detik / 迟到 "
                    f"{jam_telat}小时{menit_telat}分{detik_telat}秒"
                )

            else:

                info_telat = (
                    f"{menit_telat} menit {detik_telat} detik / 迟到 "
                    f"{menit_telat}分{detik_telat}秒"
                )

            detail_isi = (
                f"├──────────────────────────────────────┤\n"
                f"│ ⏱️ Status / 状态 :\n"
                f"    TERLAMBAT / 迟到\n"
                f"├──────────────────────────────────────┤\n"
                f"│ ⚠️ Keterangan / 说明 :\n"
                f"    Terlambat {info_telat}\n"
                f"    (超过规定上班时间 09:30)"
            )

            pesan_penutup = (
                "Harap datang lebih tepat waktu esok hari!\n"
                "(希望明天能按时到达！)"
            )

        else:

            detail_isi = (
                f"├──────────────────────────────────────┤\n"
                f"│ ⏱️ Status / 状态 :\n"
                f"    Berhasil Check-in Tepat Waktu\n"
                f"    (准时上班打卡成功)"
            )

            pesan_penutup = (
                "Selamat bekerja, jaga kedisiplinan!\n"
                "(祝您工作愉快，遵守纪律！)"
            )

    # ----------------------------------------------
    # IZIN MAKAN
    # ----------------------------------------------

    elif aksi == "IZIN MAKAN":

        status_karyawan[user_id] = aksi

        waktu_mulai_izin[user_id] = waktu_sekarang

        kunci_hitung = (user_id, aksi)

        hitung_izin[kunci_hitung] = (
            hitung_izin.get(kunci_hitung, 0) + 1
        )

        ke_berapa = hitung_izin[kunci_hitung]

        jumlah_orang_izin = sum(
            1
            for status in status_karyawan.values()
            if status in ["IZIN MAKAN", "IZIN MEROKOK/WC"]
        )

        detail_isi = (
            f"├──────────────────────────────────────┤\n"
            f"│ ⏱️ Alokasi Izin / 规定时长 :\n"
            f"    30 Menit / 分钟\n"
            f"├──────────────────────────────────────┤\n"
            f"│ 👥 Status Izin / 当前请假人数 :\n"
            f"    Sedang Izin: {jumlah_orang_izin}/3 Orang (Maks 3)\n"
            f"    当前请假: {jumlah_orang_izin}/3人\n"
            f"├──────────────────────────────────────┤\n"
            f"│ 🔢 Total Cek In / 总打卡次数 :\n"
            f"    Ke-{ke_berapa} / 第{ke_berapa}次"
        )

        pesan_penutup = (
            "Silakan kembali ke kursi tepat waktu.\n"
            "(请按时返回座位。)"
        )

    # ----------------------------------------------
    # IZIN MEROKOK / WC
    # ----------------------------------------------

    elif aksi == "IZIN MEROKOK/WC":

        status_karyawan[user_id] = aksi

        waktu_mulai_izin[user_id] = waktu_sekarang

        kunci_hitung = (user_id, aksi)

        hitung_izin[kunci_hitung] = (
            hitung_izin.get(kunci_hitung, 0) + 1
        )

        ke_berapa = hitung_izin[kunci_hitung]

        jumlah_orang_izin = sum(
            1
            for status in status_karyawan.values()
            if status in ["IZIN MAKAN", "IZIN MEROKOK/WC"]
        )

        detail_isi = (
            f"├──────────────────────────────────────┤\n"
            f"│ ⏱️ Alokasi Izin / 规定时长 :\n"
            f"    10 Menit / 分钟\n"
            f"├──────────────────────────────────────┤\n"
            f"│ 👥 Status Izin / 当前请假人数 :\n"
            f"    Sedang Izin: {jumlah_orang_izin}/3 Orang (Maks 3)\n"
            f"    当前请假: {jumlah_orang_izin}/3人\n"
            f"├──────────────────────────────────────┤\n"
            f"│ 🔢 Total Cek In / 总打卡次数 :\n"
            f"    Ke-{ke_berapa} / 第{ke_berapa}次"
        )

        pesan_penutup = (
            "Silakan kembali ke kursi tepat waktu.\n"
            "(请按时返回座位。)"
        )

    # ----------------------------------------------
    # PULANG KERJA
    # ----------------------------------------------

    else:

        waktu_masuk = waktu_masuk_kerja.get(user_id)

        if waktu_masuk:

            selisih_kerja = int(
                (waktu_sekarang - waktu_masuk).total_seconds()
            )

            jam_kerja = selisih_kerja // 3600
            sisa_detik_kerja = selisih_kerja % 3600
            menit_kerja = sisa_detik_kerja // 60
            detik_kerja = sisa_detik_kerja % 60

            info_durasi_kerja = (
                f"{jam_kerja} jam {menit_kerja} menit "
                f"{detik_kerja} detik\n"
                f"    ({jam_kerja}小时{menit_kerja}分{detik_kerja}秒)"
            )

        else:
            info_durasi_kerja = "Tidak tercatat / 未记录"

        jam_pulang_resmi = waktu_sekarang.replace(
            hour=20,
            minute=30,
            second=0,
            microsecond=0
        )

        if waktu_sekarang < jam_pulang_resmi:

            info_pulang = (
                "Pulang Sebelum Jam Kerja Berakhir / 提前下班"
            )

        else:

            info_pulang = (
                "Selesai Shift / Pulang Tepat Waktu / 准时下班"
            )

        status_karyawan[user_id] = None

        waktu_masuk_kerja[user_id] = None

        waktu_mulai_izin.pop(user_id, None)

        detail_isi = (
            f"├──────────────────────────────────────┤\n"
            f"│ ⏱️ Status / 状态 :\n"
            f"    {info_pulang}\n"
            f"    (规定下班时间 20:30)\n"
            f"├──────────────────────────────────────┤\n"
            f"│ ⏳ Total Waktu Kerja / 总工作时长 :\n"
            f"    {info_durasi_kerja}"
        )

        pesan_penutup = (
            "Terima kasih atas kerja keras hari ini.\n"
            "Hati-hati di jalan.\n"
            "(感谢今天的辛勤工作，一路平安。)"
        )

    # ----------------------------------------------
    # LAPORAN ABSENSI
    # ----------------------------------------------

    pesan = (
        f"<pre>"
        f"┌──────────────────────────────────────┐\n"
        f"│        📋 LAPORAN ABSEN ANGGOTA      \n"
        f"│             (员工考勤报告)           \n"
        f"├──────────────────────────────────────┤\n"
        f"│ 👤 Nama / 姓名 :\n"
        f"    {nama}\n"
        f"│ 📱 ID : {user_id}\n"
        f"├──────────────────────────────────────┤\n"
        f"│ 📝 Detail / 详情 :\n"
        f"    {aksi}\n"
        f"├──────────────────────────────────────┤\n"
        f"│ ⏰ Waktu / 时间 :\n"
        f"    {waktu_str}\n"
        f"{detail_isi}\n"
        f"└──────────────────────────────────────┘\n"
        f"{pesan_penutup}"
        f"</pre>"
    )

    await update.message.reply_text(
        pesan,
        parse_mode="HTML",
        reply_markup=buat_keyboard()
    )


# ==================================================
# ERROR HANDLER
# ==================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    logger.exception(
        "Terjadi error saat memproses update Telegram:",
        exc_info=context.error
    )


# ==================================================
# MENJALANKAN BOT
# ==================================================

if __name__ == "__main__":

    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    application.add_error_handler(error_handler)

    print("Bot Telegram mulai berjalan dengan stabil...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )
