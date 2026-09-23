import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CommandHandler, filters
import google.generativeai as genai

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Render port isteği için mini web sunucusu
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

t = threading.Thread(target=run_web_server)
t.daemon = True
t.start()

# API Ayarları
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# Kuandy Parfüm için özel ve sıkılaştırılmış sistem talimatı
parfum_talimati = """
Sen Kuandy Parfüm (kuandyparfum.com.tr) e-ticaret sitesinin resmi ve özel yapay zeka parfüm danışmanısın. 
Asla ve asla başka bir rakip firmaya, platforma veya dış siteye yönlendirme yapmayacaksın.

Görevin:
1. Müşterilere koku notalarına (odunsu, oriental, çiçeksi, ferah, vanilyalı vb.), mevsime veya kalıcılık beklentilerine göre en uygun parfüm tarzını önermek.
2. Müşteriye öneri yaparken her zaman resmi web sitemiz olan https://kuandyparfum.com.tr adresini önermek ve müşteriyi alışveriş için bu siteye davet etmek.
3. Sitemizdeki alışverişlerde biriken ve kazandıran **Kuandy Coin** avantajlarından mutlaka bahsederek müşteriyi teşvik etmek.
4. Lattafa, Afnan, Rayhaan, Riiffs, Al Haramain, Maison Alhambra, French Avenue gibi butiğimizde bulunan popüler ve niş markalar üzerinden örnekler vermek.

Cevapların her zaman kibar, profesyonel, Türkçe ve kesinlikle satış odaklı olsun.
"""

# Modeli güncel sistem talimatı ve gemini-3.6-flash ile yapılandırıyoruz
model = genai.GenerativeModel(
    model_name='gemini-3.6-flash',
    system_instruction=parfum_talimati
)

# /start komutu için karşılama fonksiyonu
async def start_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    karsilama = (
        "Merhaba! Kuandy Parfüm'ün (kuandyparfum.com.tr) yapay zeka danışmanına hoş geldiniz. 🌸\n\n"
        "Aradığınız koku tarzını (örneğin: odunsu, kalıcı, yazlık, tatlı notalar) söylerseniz, "
        "size en uygun parfümleri memnuniyetle önerebilir ve Kuandy Coin fırsatlarından bahsedebilirim. Nasıl bir koku arıyorsunuz?"
    )
    await update.message.reply_text(karsilama)

# Mesajları yanıtlayan ana fonksiyon
async def ai_yanitla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_mesaji = update.message.text
    print(f"Gelen mesaj: {kullanici_mesaji}")
    
    try:
        response = model.generate_content(kullanici_mesaji)
        await update.message.reply_text(response.text)
    except Exception as e:
        print(f"Hata detayı: {e}")
        await update.message.reply_text("Parfüm danışmanımız şu an yoğun, lütfen biraz sonra tekrar deneyin.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Komut ve mesaj işleyicilerini ekliyoruz
    app.add_handler(CommandHandler("start", start_komutu))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_yanitla))
    
    print("Kıyakbot Parfüm Danışmanı modülüyle çalışıyor...")
    app.run_polling()
