import sqlite3, requests, hashlib, time, asyncio, json, os
DB_PATH = "/tmp/DB_PATH"
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN") # Ambil dari Environment Variable Render

DUITKU_MERCHANT_CODE = "DS34319"
DUITKU_API_KEY = "98653b5d9f908e767a7f321c017c5269"
DUITKU_URL = "https://sandbox.duitku.com"

PRODUK = {
    "jam5": "5 Jam", "minggu1": "1 Minggu", "bulan1": "1 Bulan 1 HP",
    "bulan2": "1 Bulan 2 HP", "bulan3": "1 Bulan 3 HP", "bulan4": "1 Bulan 4 HP"
}
HARGA = {
    "jam5": 2000, "minggu1": 15000, "bulan1": 50000,
    "bulan2": 95000, "bulan3": 125000, "bulan4": 150000
}

def init_db():
    conn = sqlite3.connect("dDB_PATH")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS transaksi (order_id TEXT PRIMARY KEY, user_id INTEGER, paket TEXT, jumlah INTEGER, total INTEGER, status TEXT, created_at INTEGER)")
    conn.commit()
    conn.close()

def buat_qris_duitku(user_id, nama, total, order_id, produk_nama):
    try:
        signature = hashlib.md5(f"{DUITKU_MERCHANT_CODE}{order_id}{total}{DUITKU_API_KEY}".encode()).hexdigest()
        url = f"{DUITKU_URL}/api/merchant/v2/inquiry"
        data = {
            "merchantCode": DUITKU_MERCHANT_CODE, "amount": total, "merchantOrderId": order_id,
            "productDetails": f"Voucher {produk_nama}", "customerVaName": nama,
            "email": f"{user_id}@ef.media", "phoneNumber": "0812", "paymentMethod": "SP",
            "returnUrl": "https://duitku.com", "callbackUrl": "https://duitku.com", "signature": signature
        }
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, data=json.dumps(data), headers=headers, timeout=20)
        print("RESPONSE DUITKU:", response.text)
        result = response.json()
        return result
    except Exception as e:
        return {"error": str(e), "message": str(e)}

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, new_message=False):
    keyboard = [[InlineKeyboardButton("🛒 Beli Voucher", callback_data="menu_beli")]]
    text = f"🔥 Selamat datang di E-FLASH MEDIA 🔥\n\nSilakan pilih menu:"
    if new_message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context, new_message=True)

async def cmd_beli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await menu_beli(update, context, new_message=True)

async def menu_beli(update: Update, context: ContextTypes.DEFAULT_TYPE, new_message=False):
    keyboard = [[InlineKeyboardButton(f"{nama} = Rp {HARGA[kode]:,}".replace(",", "."), callback_data=f"pilih_paket_{kode}")] for kode, nama in PRODUK.items()]
    keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data="back_menu")])
    text = "Silakan pilih jenis voucher:"
    if new_message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        query = update.callback_query; await query.answer()
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def pilih_paket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    paket = query.data.split("_")[2]
    context.user_data['paket'] = paket
    keyboard = []
    row = []

    # KHUSUS JAM5: TAMPILKAN 5 SAMPAI 10
    if paket == "jam5":
        jumlah_list = range(5, 11) # 5,6,7,8,9,10
    else:
        jumlah_list = range(1, 6) # 1,2,3,4,5

    for i in jumlah_list:
        row.append(InlineKeyboardButton(str(i), callback_data=f"pilih_jumlah_{i}"))
        if len(row) == 3: keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data="menu_beli")])

    await query.edit_message_text(text=f"Anda memilih: *{PRODUK[paket]}* - Rp{HARGA[paket]:,}\n\nPilih Jumlah:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def pilih_jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    jumlah = int(query.data.split("_")[2])
    paket = context.user_data['paket']
    context.user_data['jumlah'] = jumlah
    harga_satuan = HARGA[paket]
    total = harga_satuan * jumlah
    user = query.from_user
    keyboard = [[InlineKeyboardButton("✅ Lanjutkan Bayar via QRIS", callback_data="bayar_qris")], [InlineKeyboardButton("❌ Batal", callback_data="menu_beli")]]

    text = (
        f"📝 *KONFIRMASI PESAN*\n\n"
        f"Nama: {user.first_name}\n"
        f"Paket: {PRODUK[paket]}\n"
        f"Jumlah: {jumlah}\n"
        f"Harga Satuan: Rp{harga_satuan:,}\n"
        f"-----------------------\n"
        f"*Total Bayar: Rp{total:,}*\n\n"
        f"ℹ️ Kode Voucher akan keluar Otomatis setelah berhasil bayar"
    )
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def bayar_qris(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    paket = context.user_data['paket']
    jumlah = context.user_data['jumlah']
    user_id, nama = query.from_user.id, query.from_user.first_name
    harga_satuan = HARGA[paket]
    total = harga_satuan * jumlah

    if total < 50000:
        await query.edit_message_text(f"❌ GAGAL\nMinimal SANDBOX Rp50.000\nTotal kamu: Rp{total:,}\n\nContoh: 1 Minggu x4 = 60.000")
        return

    order_id = f"EF{int(time.time())}"
    produk_nama = f"{PRODUK[paket]} x{jumlah}"
    await query.edit_message_text(text=f"⏳ Sedang membuat QRIS...")

    result = await asyncio.to_thread(buat_qris_duitku, user_id, nama, total, order_id, produk_nama)

    if 'qrUrl' in result and result['qrUrl']:
        caption = f"✅ *SILAHKAN SCAN QRIS DI BAWAH*\n\nPaket: {PRODUK[paket]}\nJumlah: {jumlah}\nTotal Bayar: *Rp{total:,}*\nOrder ID: `{order_id}`\n\n⚠️ Mode SANDBOX"
        await query.message.reply_photo(photo=result['qrUrl'], caption=caption, parse_mode="Markdown")
        conn = sqlite3.connect("DB_PATH"); c = conn.cursor()
        c.execute("INSERT INTO transaksi VALUES (?,?,?,?,?,?,?)", (order_id, user_id, paket, jumlah, total, "PENDING", int(time.time())))
        conn.commit(); conn.close()
    else:
        pesan_error = result.get('message', result.get('error', 'Unknown Error'))
        await query.message.reply_text(f"❌ GAGAL BUAT QRIS\n\nAlasan: `{pesan_error}`\nCode: `{result.get('responseCode')}`", parse_mode="Markdown")

    await query.message.reply_text("Ketik /start untuk kembali")

async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context, new_message=False)

async def set_commands(app):
    commands = [
        BotCommand("start", "Buka Menu Utama"),
        BotCommand("beli", "Beli Voucher"),
    ]
    await app.bot.set_my_commands(commands)

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("beli", cmd_beli))
    app.add_handler(CallbackQueryHandler(menu_beli, pattern="^menu_beli$"))
    app.add_handler(CallbackQueryHandler(pilih_paket, pattern="^pilih_paket_"))
    app.add_handler(CallbackQueryHandler(pilih_jumlah, pattern="^pilih_jumlah_"))
    app.add_handler(CallbackQueryHandler(bayar_qris, pattern="^bayar_qris$"))
    app.add_handler(CallbackQueryHandler(back_menu, pattern="^back_menu$"))
    app.post_init = set_commands
    print("Bot E-FLASH MEDIA is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
