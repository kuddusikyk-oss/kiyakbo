import os
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CommandHandler, filters
from google import genai

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Render port isteği için mini web sunucusu
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

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

# Google GenAI İstemcisi
client = genai.Client(api_key=GEMINI_API_KEY)

# WooCommerce'den ürün arama fonksiyonu
def woocommerce_urun_ara(arama_terimi):
    try:
        url = f"{WC_URL}/wp-json/wc/v3/products"
        params = {"search": arama_terimi, "per_page": 3}
        response = requests.get(url, params=params, auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET), timeout=10)
        
        if response.status_code == 200:
            urunler = response.json()
            if not urunler:
                return None
            
            bilgi_metni = "SİTEDE BULUNAN GERÇEK ÜRÜN VERİLERİ (Fiyat, Cinsiyet, Nitelikler ve Doğrudan Link):\n\n"
            for u in urunler:
                ad = u.get("name")
                fiyat = u.get("price")
                stok_durumu = "Stokta Var ✅" if u.get("stock_status") == "instock" else "Tükendi ❌"
                link = u.get("permalink")
                
                nitelikler = u.get("attributes", [])
                nitelik_metni = ""
                for nit in nitelikler:
                    isim = nit.get("name")
                    secenekler = ", ".join(nit.get("options", []))
                    nitelik_metni += f"- {isim}: {secenekler}\n"

                kisa_aciklama = u.get("short_description", "").replace("<p>", "").replace("</p>", "").replace("<br />", "\n").replace("<strong>", "").replace("</strong>", "")
                
                bilgi_metni += f"* Ürün Adı: {ad}\n"
                bilgi_metni += f"* Fiyat: {fiyat} TL\n"
                bilgi_metni += f"* Stok Durumu: {stok_durumu}\n"
                if nitelik_metni:
                    bilgi_metni += f"* Nitelikler (Cinsiyet/Nota vb.):\n{nitelik_metni}"
                bilgi_metni += f"* Açıklama: {kisa_aciklama}\n"
                bilgi_metni += f"* DOĞRUDAN LİNK: {link}\n\n"
            return bilgi_metni
        else:
            return None
    except Exception as e:
        print(f"WooCommerce API Hatası: {e}")
        return None

# Sistem Talimatı
parfum_talimati = """
Sen Kuandy Parfüm (kuandyparfum.com.tr) e-ticaret sitesinin resmi ve profesyonel yapay zeka parfüm danışmanısın. 

KURALLAR:
1. Kullanıcı "merhaba", "selam" gibi selamlama yazdığında kibarca kendini tanıt ("Ben Kuandy Parfüm yapay zeka danışmanıyım 🌸") ve nasıl yardımcı olabileceğini sor.
2. Kullanıcı kışlık parfüm, 4 mevsim parfüm veya belirli bir nota sorduğunda, sağlanan ürün verilerini kullanarak yönlendirme yap.
3. Önerdiğin her ürünün **Erkek, Kadın veya Unisex** olduğunu mutlaka belirt.
4. Parfümün koku notalarını (varsa niteliklerden) müşteriye aktar.
5. Ürün önerirken fiyatı belirt ve linki şu formatta ver: [Ürünü İncele ve Satın Al (Fiyat TL)](ÜRÜN_LİNKİ). Asla ana sayfa linkini ürün için verme.
6. Alışverişlerde kazanılan Kuandy Coin avantajından bahset.
7. Telegram Markdown formatına uygun temiz metinler yaz, ham HTML etiketleri kullanma.
"""

async def start_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    karsilama = (
        "Merhaba! Ben Kuandy Parfüm'ün (kuandyparfum.com.tr) yapay zeka danışmanıyım. 🌸\n\n"
        "İster kışlık, ister 4 mevsimlik, ister özel koku notalarına sahip parfümler arayın; aradığınız tüm kokuları, cinsiyet seçimlerini ve Kuandy Coin avantajlarını anında bulabilirim. Hangi parfümü arıyorsunuz?"
    )
    await update.message.reply_text(karsilama)

async def ai_yanitla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_mesaji = update.message.text
    print(f"Gelen mesaj: {kullanici_mesaji}")
    
    wc_veri = woocommerce_urun_ara(kullanici_mesaji)
    
    if wc_veri:
        baglam_mesaji = f"Kullanıcı mesajı: {kullanici_mesaji}\n\n{wc_veri}"
    else:
        baglam_mesaji = f"Kullanıcı mesajı: {kullanici_mesaji}\n\nNot: Sitede bu aramaya birebir uyan ürün bulunamadı. Kullanıcıya kışlık, yazlık veya 4 mevsimlik genel koleksiyonlar için https://kuandyparfum.com.tr adresini göster."
    
    try:
        # Hata ekranında belirtilen güncel model adı
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=baglam_mesaji,
            config={
                'system_instruction': parfum_talimati,
            }
        )
        await update.message.reply_text(response.text, disable_web_page_preview=False)
    except Exception as e:
        print(f"Hata detayı: {e}")
        await update.message.reply_text(f"Hata oluştu: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_komutu))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_yanitla))
    
    print("Kıyakbot 3.6-flash Model ile çalışıyor...")
    app.run_polling(drop_pending_updates=True)
