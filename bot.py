from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

# 1. Menu utama saat /start diketik
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("MASUK KERJA", callback_data="Masuk Kerja")],
        [InlineKeyboardButton("IZIN MAKAN", callback_data="Izin Makan")],
        [InlineKeyboardButton("IZIN MEROKOK", callback_data="Izin Merokok")],
        [InlineKeyboardButton("KEMBALI KURSI", callback_data="Kembali Kursi")]
    ]
    await update.message.reply_text("Pilih menu absensi:", reply_markup=InlineKeyboardMarkup(keyboard))

# 2. Respon saat tombol diklik (muncul pesan baru)
async def tombol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    nama = query.from_user.full_name
    aksi = query.data
    
    pesan = f"<b>{nama}</b> melakukan: <b>{aksi}</b>"
    await context.bot.send_message(chat_id=query.message.chat_id, text=pesan, parse_mode="HTML")

def main():
    # Masukkan token bot Anda di sini
    TOKEN = "8929417098:AAHqjy5pdj1vjNkRNUHSmRPzoALTutlsfwA"
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(tombol))
    
    print("Bot siap...")
    app.run_polling()

if __name__ == "__main__":
    main()