import os
import logging
import time
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

# WooCommerce'den esnek ürün arama fonksiyonu
def woocommerce_urun_ara(arama_terimi):
    try:
        url = f"{WC_URL}/wp-json/wc/v3/products"
        # Önce tam terimle arat
        params = {"search": arama_terimi, "per_page": 5}
        response = requests.get(url, params=params, auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET), timeout=10)
        
        urunler = []
        if response.status_code == 200:
            urunler = response.json()
            
        # Eğer tam eşleşme bulunamazsa kelimelere bölüp esnek arama yap (Örn: "kışlık erkek" -> "erkek" veya "kış")
        if not urunler and len(arama_terimi.split()) > 1:
            kelimeler = arama_terimi.split()
            for kelime in kelimeler:
                if len(kelime) > 3: # Kısa takıları ele
                    params = {"search": kelime, "per_page": 5}
                    resp = requests.get(url, params=params, auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET), timeout=10)
                    if resp.status_code == 200 and resp.json():
                        urunler.extend(resp.json())
        
        if not urunler:
            return None
        
        # Benzersiz ürünleri seç
        benzersiz_urunler = {u['id']: u for u in urunler}.values()
        
        bilgi_metni = "SİTEDE BULUNAN İLGİLİ ÜRÜN VERİLERİ (Fiyat, Cinsiyet, Nitelikler ve Doğrudan Link):\n\n"
        for u in list(benzersiz_urunler)[:4]:
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
    except Exception as e:
        print(f"WooCommerce API Hatası: {e}")
        return None

# Sistem Talimatı
parfum_talimati = """
Sen Kuandy Parfüm (kuandyparfum.com.tr) e-ticaret sitesinin resmi ve profesyonel yapay zeka parfüm danışmanısın. 

GÖREVLERİN VE KURALLAR:
1. Kullanıcı "merhaba", "selam" gibi bir giriş yaptığında kibarca kendini tanıt ("Ben Kuandy Parfüm yapay zeka danışmanıyım 🌸") ve nasıl yardımcı olabileceğini sor.
2. Kullanıcı kışlık, yazlık, 4 mevsim veya erkek/kadın/unisex parfüm istediğinde, sana sağlanan gerçek ürün verilerinden uygun olanları seçerek doğrudan müşteriye öner.
3. Önerdiğin her ürünün **Erkek, Kadın veya Unisex** olduğunu niteliklere bakarak kesinlikle belirt.
4. Parfümün koku notalarını (üst, orta, dip nota vb.) ve açıklamalarını müşteriye aktar.
5. Ürün önerirken fiyatını mutlaka belirt ve linki şu formatta ver: [Ürünü İncele ve Satın Al (Fiyat TL)](ÜRÜN_LİNKİ). Asla ana sayfa linkini ürün için verme; her ürünün kendi DOĞRUDAN LİNK'ini kullan.
6. Alışverişlerde kazanılan **Kuandy Coin** avantajından bahset.
7. Telegram Markdown formatına uygun temiz metinler yaz, ham HTML etiketleri kullanma.
"""

async def start_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    karsilama = (
        "Merhaba! Ben Kuandy Parfüm'ün (kuandyparfum.com.tr) yapay zeka danışmanıyım. 🌸\n\n"
        "İster kışlık, ister yazlık, ister 4 mevsimlik, ister özel koku notalarına sahip parfümler arayın; aradığınız tüm kokuları, cinsiyet seçimlerini ve Kuandy Coin avantajlarını anında bulabilirim. Hangi parfümü arıyorsunuz?"
    )
    await update.message.reply_text(karsilama)

async def ai_yanitla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_mesaji = update.message.text
    print(f"Gelen mesaj: {kullanici_mesaji}")
    
    wc_veri = woocommerce_urun_ara(kullanici_mesaji)
    
    if wc_veri:
        baglam_mesaji = f"Kullanıcı mesajı: {kullanici_mesaji}\n\n{wc_veri}"
    else:
        baglam_mesaji = f"Kullanıcı mesajı: {kullanici_mesaji}\n\nNot: Sitede bu aramaya birebir uyan ürün bulunamadı. Kullanıcıya genel koleksiyonlar için https://kuandyparfum.com.tr adresini öner ve alternatif notalar sor."
    
    # 503 Yoğunluk hatalarına karşı 3 kez otomatik tekrar deneme mekanizması (Retry)
    yanit = None
    for deneme in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=baglam_mesaji,
                config={
                    'system_instruction': parfum_talimati,
                }
            )
            yanit = response.text
            break
        except Exception as e:
            print(f"Deneme {deneme+1} başarısız: {e}")
            time.sleep(2) # 2 saniye bekleyip tekrar dene
            
    if yanit:
        await update.message.reply_text(yanit, disable_web_page_preview=False)
    else:
        await update.message.reply_text("Şu an yoğunluk nedeniyle yanıt üretilemedi, lütfen tekrar deneyin.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_komutu))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_yanitla))
    
    print("Kıyakbot Gelişmiş Esnek Arama Sürümü ile çalışıyor...")
    app.run_polling(drop_pending_updates=True)
