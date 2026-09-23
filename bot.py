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

# WooCommerce'den ürün ve kısa açıklamalarını arama fonksiyonu
def woocommerce_urun_ara(arama_terimi):
    try:
        url = f"{WC_URL}/wp-json/wc/v3/products"
        params = {"search": arama_terimi, "per_page": 3}
        response = requests.get(url, params=params, auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET), timeout=10)
        
        if response.status_code == 200:
            urunler = response.json()
            if not urunler:
                return None
            
            bilgi_metni = "Sitemizdeki Gerçek Ürün Verileri:\n\n"
            for u in urunler:
                ad = u.get("name")
                fiyat = u.get("price")
                stok_durumu = "Stokta Var ✅" if u.get("stock_status") == "instock" else "Tükendi ❌"
                link = u.get("permalink")
                # Sitenize girdiğiniz kısa açıklamayı (HTML etiketlerinden arındırarak) çekiyoruz
                kisa_aciklama = u.get("short_description", "").replace("<p>", "").replace("</p>", "").replace("<br />", "\n")
                
                bilgi_metni += f"🔹 Ürün: {ad}\n"
                bilgi_metni += f"   💰 Fiyat: {fiyat} TL\n"
                bilgi_metni += f"   📦 Durum: {stok_durumu}\n"
                bilgi_metni += f"   📝 Detay/Açıklama: {kisa_aciklama}\n"
                bilgi_metni += f"   🔗 Link: {link}\n\n"
            return bilgi_metni
        else:
            print(f"WooCommerce API Yanıt Kodu: {response.status_code}")
            return None
    except Exception as e:
        print(f"WooCommerce API Hatası: {e}")
        return None

# Kuandy Parfüm sistem talimatı
parfum_talimati = """
Sen Kuandy Parfüm (kuandyparfum.com.tr) e-ticaret sitesinin resmi ve akıllı yapay zeka parfüm danışmanısın. 
Asla başka bir rakip firmaya veya dış siteye yönlendirme yapmayacaksın.

Görevin:
1. Müşteri bir ürün sorduğunda, eğer aşağıda "WooCommerce Sitemizden Alınan Gerçek Ürün Verileri" başlığı altında bir bilgi varsa, o bilgileri (fiyat, stok, kısa açıklama ve verilen linki) birebir kullanarak müşteriye sun.
2. Müşteriye ürünün doğrudan satın alma linkini Markdown formatında şık bir şekilde ver (Örn: [Ürünü İncele ve Satın Al](LİNK)).
3. Sitemizdeki alışverişlerde kazandıran **Kuandy Coin** avantajından mutlaka bahset.
4. Cevapların kibar, profesyonel ve satış odaklı olsun.
"""

model = genai.GenerativeModel(
    model_name='gemini-3.6-flash',
    system_instruction=parfum_talimati
)

async def start_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    karsilama = (
        "Merhaba! Kuandy Parfüm'ün (kuandyparfum.com.tr) yapay zeka danışmanına hoş geldiniz. 🌸\n\n"
        "Aradığınız parfümü yazın; anlık fiyatını, stok durumunu, siteye girdiğiniz özel açıklamalarını ve doğrudan ürün linkini hemen size sunayım!"
    )
    await update.message.reply_text(karsilama)

async def ai_yanitla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_mesaji = update.message.text
    print(f"Gelen mesaj: {kullanici_mesaji}")
    
    # WooCommerce'den ürün aratıyoruz
    wc_veri = woocommerce_urun_ara(kullanici_mesaji)
    
    baglam_mesaji = kullanici_mesaji
    if wc_veri:
        baglam_mesaji = f"Kullanıcı mesajı: {kullanici_mesaji}\n\nWooCommerce Sitemizden Alınan Gerçek Ürün Verileri:\n{wc_veri}"
    
    try:
        response = model.generate_content(baglam_mesaji)
        # Markdown çakışmalarını önlemek için düz metin veya güvenli gönderim yapıyoruz
        await update.message.reply_text(response.text, disable_web_page_preview=False)
    except Exception as e:
        print(f"Hata detayı: {e}")
        await update.message.reply_text("Parfüm danışmanımız yanıt üretirken bir sorunla karşılaştı.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_komutu))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_yanitla))
    
    print("Kıyakbot WooCommerce Kısa Açıklama Entegrasyonu ile çalışıyor...")
    app.run_polling()
