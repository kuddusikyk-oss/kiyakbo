import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import google.generativeai as genai

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token ve API anahtarını güvenli bir şekilde bulut ortamından alıyoruz
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

async def ai_yanitla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_mesaji = update.message.text
    print(f"Gelen mesaj: {kullanici_mesaji}")
    
    try:
        yanit = model.generate_content(kullanici_mesaji)
        await update.message.reply_text(yanit.text)
    except Exception as e:
        print(f"Hata: {e}")
        await update.message.reply_text("Yapay zeka yanıt üretirken bir sorun oluştu.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_yanitla))
    
    print("Kıyakbot yapay zeka modülüyle çalışıyor...")
    app.run_polling()
