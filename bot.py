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
        self.wfile.write(b"Kuandy Parfum AI Bot is active and running!")

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

# API ve Mağaza Ayarları
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WC_URL = os.getenv("WC_URL", "https://kuandyparfum.com.tr")
WC_CONSUMER_KEY = os.getenv("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.getenv("WC_CONSUMER_SECRET")

# Google GenAI İstemcisi
client = genai.Client(api_key=GEMINI_API_KEY)

# WooCommerce Ürünlerini Bellekte Tutma ve Akıllı Önbellek (Cache)
urunler_cache = []
son_guncelleme_zamani = 0

def woocommerce_envanterini_guncelle():
    global urunler_cache, son_guncelleme_zamani
    simdi = time.time()
    if urunler_cache and (simdi - son_guncelleme_zamani < 900):
        return urunler_cache

    try:
        url = f"{WC_URL}/wp-json/wc/v3/products"
        params = {"per_page": 50, "status": "publish", "orderby": "date", "order": "desc"}
        response = requests.get(url, params=params, auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET), timeout=15)
        
        if response.status_code == 200:
            urunler_cache = response.json()
            son_guncelleme_zamani = simdi
            print(f"Başarıyla {len(urunler_cache)} adet ürün envantere yüklendi.")
    except Exception as e:
        print(f"WooCommerce Envanter Çekme Hatası: {e}")
    
    return urunler_cache

def akilli_urun_filtrele(kullanici_sorgusu):
    tum_urunler = woocommerce_envanterini_guncelle()
    if not tum_urunler:
        return "Şu anda site envanterine ulaşılamadı."

    envanter_metni = "KUANDY PARFÜM GÜNCEL ÜRÜN ENVANTERİ VE DETAYLARI:\n\n"
    
    for u in tum_urunler:
        ad = u.get("name", "")
        fiyat = u.get("price", "0")
        stok = "Stokta Var ✅" if u.get("stock_status") == "instock" else "Tükendi ❌"
        link = u.get("permalink", WC_URL)
        
        kategoriler = ", ".join([cat.get("name", "") for cat in u.get("categories", [])])
        
        nitelik_metni = ""
        for nit in u.get("attributes", []):
            isim = nit.get("name", "")
            secenekler = ", ".join(nit.get("options", []))
            nitelik_metni += f"  - {isim}: {secenekler}\n"

        aciklama = u.get("short_description", "")
        for tag in ["<p>", "</p>", "<br>", "<br />", "<strong>", "</strong>", "<em>", "</em>"]:
            aciklama = aciklama.replace(tag, "")
        
        envanter_metni += f"🔹 Ürün Adı: {ad}\n"
        envanter_metni += f"   - Fiyat: {fiyat} TL\n"
        envanter_metni += f"   - Durum: {stok}\n"
        envanter_metni += f"   - Kategoriler: {kategoriler}\n"
        if nitelik_metni:
            envanter_metni += f"   - Nitelikler:\n{nitelik_metni}"
        if aciklama.strip():
            envanter_metni += f"   - Açıklama/Notlar: {aciklama.strip()}\n"
        envanter_metni += f"   - DOĞRUDAN LİNK: {link}\n\n"

    return envanter_metni

# Profesyonel Parfüm Uzmanı ve Satış Danışmanı Sistem Talimatı
parfum_talimati = """
Sen kuandyparfum.com.tr adresinin resmi, üst düzey kıdemli parfüm uzmanı ve baş satış danışmanısın. Amacın müşterilere mağazadaki en uygun parfümleri nokta atışı önermek, koku zevklerine rehberlik etmek ve satışa yönlendirmektir.

ÇALIŞMA PRENSİPLERİN VE KURALLAR:
1. **Samimi ve Profesyonel Karşılama:** Müşteri "merhaba", "selam" gibi bir giriş yaptığında kibarca kendini tanıt ("Ben Kuandy Parfüm'ün kıdemli parfüm uzmanı ve danışmanıyım 🌸") ve aradığı koku karakterini (odunsu, baharatlı, vanilya, yazlık, kışlık vb.) sor.
2. **Nokta Atışı Eşleştirme:** Aşağıda sana sunulan güncel ürün envanterini dikkatle incele. Müşterinin talebine en uygun olan gerçek ürünleri envanterden seç ve kesinlikle bu listeden öner. Asla uydurma ürün yazma.
3. **Detaylı Sunum:** Önerdiğin her parfüm için şunları mutlaka belirt:
   - Ürünün tam adı ve **Erkek, Kadın veya Unisex** olduğu.
   - Koku notaları (üst, orta, dip nota veya varsa içerik özellikleri).
   - Fiyatı ve **[Ürünü İncele ve Satın Al (Fiyat TL)](DOĞRUDAN_LİNK)** formatındaki nokta atışı ürün linki. (Asla ana sayfa linkini ürün için kullanma, her ürünün kendi DOĞRUDAN LİNK'ini ver).
4. **Kuandy Coin Avantajı:** Alışverişlerde müşterilerin **Kuandy Coin** kazanarak sonraki siparişlerinde indirim elde edebileceğini vurgula.
5. **Yönlendirme:** Eğer müşteri kararsız kalırsa, ona notalar (Vanilya, Amber, Oud, Deri, Çiçeksi, Ferah vb.) hakkında sorular sorarak en doğru kokuya ulaşmasını sağla.
6. **Biçimlendirme:** Telegram Markdown formatına tam uygun, göz yormayan, şık ve emoji destekli metinler üret.
"""

async def start_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    karsilama = (
        "Merhaba! Ben Kuandy Parfüm'ün (kuandyparfum.com.tr) kıdemli parfüm uzmanı ve satış danışmanıyım. 🌸\n\n"
        "Konya merkezli mağazamızdan Türkiye'nin dört bir yanına ulaştırdığımız; Lattafa, Afnan, Al Haramain, Rayhaan ve daha pek çok seçkin markanın orijinal parfümleri arasından size en uygun imzayı bulabilirim.\n\n"
        "Bugün size nasıl bir koku arıyoruz? (Örn: Kışlık kalıcı erkek parfümü, vanilyalı kadın kokusu vb.)"
    )
    await update.message.reply_text(karsilama)

async def ai_yanitla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_mesaji = update.message.text
    print(f"Gelen müşteri mesajı: {kullanici_mesaji}")
    
    envanter_verisi = akilli_urun_filtrele(kullanici_mesaji)
    baglam_mesaji = f"Müşterinin Talebi/Mesajı: {kullanici_mesaji}\n\n{envanter_verisi}"
    
    yanit = None
    # 3'lü deneme döngüsü ve bekleme süreleri artırıldı (Yoğunluk aşımı için)
    for deneme in range(1, 4):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=baglam_mesaji,
                config={
                    'system_instruction': parfum_talimati,
                    'temperature': 0.4,
                }
            )
            yanit = response.text
            if yanit:
                break
        except Exception as e:
            print(f"Gemini API Deneme {deneme} hatası: {e}")
            time.sleep(deneme * 1.5) # Her denemede biraz daha fazla bekle (1.5s, 3s)
            
    if yanit:
        await update.message.reply_text(yanit, disable_web_page_preview=False)
    else:
        await update.message.reply_text("Şu an yoğunluk nedeniyle yanıt oluşturulamadı, lütfen tekrar deneyin.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_komutu))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_yanitla))
    
    print("Kuandy Parfüm Uzmanı (Gemini 3.6 Flash) aktif ve çalışmaya hazır...")
    app.run_polling(drop_pending_updates=True)
