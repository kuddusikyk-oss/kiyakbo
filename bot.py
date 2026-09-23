import os
import logging
import requests
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
WC_URL = os.getenv("WC_URL", "https://kuandyparfum.com.tr")
WC_CONSUMER_KEY = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")

genai.configure(api_key=GEMINI_API_KEY)

# WooCommerce'den ürün arama fonksiyonu
def woocommerce_urun_ara(arama_terimi):
    try:
        url = f"{WC_URL}/wp-json/wc/v3/products"
        params = {"search": arama_terimi, "per_page": 5}
        response = requests.get(url, params=params, auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET), timeout=10)
        
        if response.status_code == 200:
            urunler = response.json()
            if not urunler:
                return None
            
            bilgi_metni = "Sitemizde bulduğum güncel ürünler:\n\n"
            for u in urunler:
                ad = u.get("name")
                fiyat = u.get("price")
                stok_durumu = "Stokta Var ✅" if u.get("stock_status") == "instock" else "Tükendi ❌"
                link = u.get("permalink")
                
                bilgi_metni += f"🔹 **{ad}**\n"
                bilgi_metni += f"   💰 Fiyat: {fiyat} TL\n"
                bilgi_metni += f"   📦 Durum: {stok_durumu}\n"
                bilgi_metni += f"   🔗 İncele/Satın Al: {link}\n\n"
            return bilgi_metni
        else:
            return None
    except Exception as e:
        print(f"WooCommerce API Hatası: {e}")
        return None

# Kuandy Parfüm için özel ve sıkılaştırılmış sistem talimatı
parfum_talimati = """
Sen Kuandy Parfüm (kuandyparfum.com.tr) e-ticaret sitesinin resmi ve özel yapay zeka parfüm danışmanısın. 
Asla ve asla başka bir rakip firmaya, platforma veya dış siteye yönlendirme yapmayacaksın.

Görevin:
1. Müşterilere koku notalarına (odunsu, oriental, çiçeksi, ferah, vanilyalı vb.), mevsime veya kalıcılık beklentilerine göre en uygun parfüm tarzını önermek.
2. Müşteriye öneri yaparken her zaman resmi web sitemiz olan https://kuandyparfum.com.tr adresini önermek ve müşteriyi alışveriş için bu siteye davet etmek.
3. Sitemizden sağlanan anlık stok, fiyat ve ürün bağlantılarını (link) müşteriye net bir şekilde sunmak.
4. Sitemizdeki alışverişlerde biriken ve kazandıran **Kuandy Coin** avantajlarından mutlaka bahsederek müşteriyi teşvik etmek.
5. Lattafa, Afnan, Rayhaan, Riiffs, Al Haramain, Maison Alhambra, French Avenue gibi butiğimizde bulunan popüler ve niş markalar üzerinden örnekler vermek.

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
        "Aradığınız parfümü, markayı yazabilir ya da koku tarzınızı (odunsu, kalıcı, yazlık vb.) söyleyebilirsiniz. "
        "Size anlık stok, fiyat bilgilerini ve doğrudan ürün linklerini sunabilir, Kuandy Coin fırsatlarından bahsedebilirim!"
    )
    await update.message.reply_text(karsilama)

# Mesajları yanıtlayan ana fonksiyon
async def ai_yanitla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_mesaji = update.message.text
    print(f"Gelen mesaj: {kullanici_mesaji}")
    
    # WooCommerce'den ürün aratıyoruz
    wc_veri = woocommerce_urun_ara(kullanici_mesaji)
    
    baglam_mesaji = kullanici_mesaji
    if wc_veri:
        baglam_mesaji = f"Kullanıcı mesajı: {kullanici_mesaji}\n\nWooCommerce Sitemizden Alınan Gerçek Ürün ve Stok Verileri:\n{wc_veri}"
    
    try:
        response = model.generate_content(baglam_mesaji)
        await update.message.reply_text(response.text, parse_mode='Markdown', disable_web_page_preview=False)
    except Exception as e:
        print(f"Hata detayı: {e}")
        try:
            await update.message.reply_text(response.text)
        except:
            await update.message.reply_text("Parfüm danışmanımız şu an yoğun, lütfen biraz sonra tekrar deneyin.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Komut ve mesaj işleyicilerini ekliyoruz
    app.add_handler(CommandHandler("start", start_komutu))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_yanitla))
    
    print("Kıyakbot WooCommerce Entegrasyonlu Parfüm Danışmanı ile çalışıyor...")
    app.run_polling()
