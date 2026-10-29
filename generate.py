"""Konu seçer, Gemini ile karusel metni + caption + hashtag üretir -> out/post.json"""
import json, os, random, re, sys, time
import requests

def modelleri_bul():
    """Hesabın kullanabildiği Gemini modellerinden en yeni 'flash' ve 'flash-lite' modellerini seçer."""
    if os.environ.get("GEMINI_MODEL"):
        return [os.environ["GEMINI_MODEL"]]
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                     headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=30)
    r.raise_for_status()
    ad = [m["name"].split("/")[-1] for m in r.json()["models"] if "generateContent" in m.get("supportedGenerationMethods", [])]
    ad = [a for a in ad if a.startswith("gemini") and "flash" in a
          and not re.search(r"tts|image|embed|live|audio|robotics|computer|preview|exp|thinking|latest", a)]
    surum = lambda a: [int(x) for x in re.findall(r"\d+", a)]
    flash = sorted((a for a in ad if "lite" not in a), key=surum, reverse=True)
    lite = sorted((a for a in ad if "lite" in a), key=surum, reverse=True)
    secilen = flash[:2] + lite[:1]
    print("Modeller:", secilen)
    return secilen or sys.exit("Uygun Gemini modeli bulunamadı")


MODELLER = None
KATEGORILER = ["kardiyo", "kuvvet", "beslenme", "toparlanma", "motivasyon"]


def claude(prompt, system, max_tokens=4000):
    """Ad eski kaldı; Gemini'yi çağırır ve JSON döndürür."""
    global MODELLER
    MODELLER = MODELLER or modelleri_bul()
    for deneme in range(8):
        model = MODELLER[deneme % len(MODELLER)]  # hata olunca sıradaki modeli dene
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens,
                                           "temperature": 0.9}},
                timeout=90,
            )
            r.raise_for_status()
            metin = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(metin)
        except Exception as e:  # ağ, kota ya da bozuk JSON: tekrar dene
            print("Gemini hatası:", e, file=sys.stderr)
            time.sleep(min(5 * (deneme + 1), 25))
    sys.exit("Gemini 8 denemede cevap veremedi")


def haberler():
    """Google Haberler RSS'ten son 3 günün fitness/beslenme başlıkları (ücretsiz, anahtarsız)."""
    import urllib.parse, xml.etree.ElementTree as ET
    satir = []
    fenomenler = json.load(open("fenomenler.json", encoding="utf-8"))
    for q in [f'"{f}"' for f in fenomenler] + ["spor hocası açıkladı", "fitness fenomeni", "vücut geliştirme", "Türk sporcu antrenman", "spor bilimi yeni araştırma", "fitness", "antrenman programı", "protein kreatin", "koşu", "kas yapmak"]:
        try:
            u = "https://news.google.com/rss/search?hl=tr&gl=TR&ceid=TR:tr&q=" + urllib.parse.quote(q + " when:3d")
            kok = ET.fromstring(requests.get(u, timeout=30).content)
            satir += [i.findtext("title") for i in kok.iter("item")][:6]
        except Exception as e:
            print("Haber hatası:", e, file=sys.stderr)
    return "\n".join(f"- {t}" for t in dict.fromkeys(satir))


GENEL = {"antre", "spor", "fitne", "sağlı", "egzer", "gerçe", "yapma", "nasıl", "nedir", "olur", "faydal", "zararl", "hareke", "dayan", "kuvve", "dünya", "şampi", "hazır", "mücad", "etkil", "dinam", "üst", "düzey", "ulaşm", "milli", "olası"}


def benzer(konu, onceki):
    """Son konularla ortak anahtar kelime (ilk 5 harf, genel kelimeler hariç) varsa aynı konu sayılır."""
    kok = lambda t: {w[:5] for w in re.findall(r"\w{4,}", t.lower())} - GENEL
    return any(kok(konu) & kok(o) for o in onceki)


def gundem_konu(gecmis):
    """Güncel haber başlıklarından yeni bir konu çıkarır; olmazsa None (havuza düşülür)."""
    ham = haberler()
    print("Haber başlığı sayısı:", ham.count(chr(10)) + 1)
    if len(ham) < 200:
        return None
    onceki = [g["konu"] for g in gecmis[-40:]]
    for _ in range(3):
        sec = _sec(ham, onceki)
        if sec and not benzer(sec["konu"], onceki[-12:]):
            return sec
        print("Konu yakın zamanda işlendi, yenisi seçiliyor:", sec and sec["konu"], file=sys.stderr)
        onceki += [sec["konu"]] if sec else []


def _sec(ham, onceki):
    sec = claude("Aşağıda son günlerin fitness/spor/beslenme haber başlıkları var. Bunlardan Instagram karuseli için en merak uyandırıcı TEK konuyu seç. "
                 "Türkiye'deki fitness fenomenleri/sporcular (başlıklardaki isimler) ve yeni spor gelişmeleri hakkında haber varsa onları ÖNCELİKLİ seç, kişiyi konuda adıyla an. "
                 "Yalnızca antrenman, kas, beslenme, toparlanma ya da sağlıkla doğrudan bağ kurulabilen haberleri seç; futbol transferi, maç sonucu, kulüp ve dedikodu haberlerini seçme. Kanıtı zayıf ya da tehlikeli iddiaları da seçme. "
                 f"Şunlara benzer olmasın: {onceki}.\n\nBAŞLIKLAR:\n{ham[:5000]}\n\n"
                 'Sadece JSON ver: {"konu": "soru ya da iddia biçiminde başlık, haber başlığını kopyalama", "kategori": "'
                 + "|".join(KATEGORILER) + '", "bilgi": "bu konuda genel kabul görmüş bilimsel gerçekler; başlıktaki iddiayı doğrulanmadan tekrarlama, 600 karakteri geçmesin"}',
                 "Sadece geçerli JSON döndür. Emin olmadığın bilgiyi yazma.")
    return sec if sec.get("kategori") in KATEGORILER and sec.get("konu") else None


def konu_sec():
    konular = json.load(open("konular.json", encoding="utf-8"))
    gecmis = json.load(open("gecmis.json", encoding="utf-8"))
    kullanilan = {g["konu"] for g in gecmis}
    bos = [k for k in konular if k["konu"] not in kullanilan]
    if len(bos) < 8:  # havuz bitmeden yenisini doldur
        print("Konu havuzu azaldı, yeni konular üretiliyor")
        mevcut = [k["konu"] for k in konular]
        yeni = claude(
            f"Türkçe fitness/spor/sağlıklı beslenme Instagram hesabı için 30 yeni karusel konusu öner. "
            f"Kategoriler: {KATEGORILER}. Şu konulara benzer ya da aynı olmasın: {mevcut[-80:]}. "
            'Sadece JSON dizisi ver: [{"konu": "...", "kategori": "..."}]. Konular merak uyandıran soru ya da iddia olsun.',
            "Sadece geçerli JSON döndür.",
        )
        konular += [y for y in yeni if y.get("kategori") in KATEGORILER and y["konu"] not in mevcut]
        json.dump(konular, open("konular.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        bos = [k for k in konular if k["konu"] not in kullanilan]
    son = [g["kategori"] for g in gecmis[-2:]]  # aynı kategori üst üste gelmesin
    onceki = [g["konu"] for g in gecmis[-12:]]
    bos = [k for k in bos if not benzer(k["konu"], onceki)] or bos
    aday = [k for k in bos if k["kategori"] not in son] or bos
    return random.choice(aday)


SISTEM = """Sen Türkiye'deki "fitalgoritma" Instagram hesabının içerik editörüsün. Hesap: biyomekanik, kas gelişimi, veri odaklı antrenman, bilimsel beslenme.
Kurallar:
- Türkçe, sade, samimi, "sen" dili. Jargon çıkarsa tek cümleyle açıkla.
- Bilimsel olarak doğru ve temkinli ol. Uydurma sayı, sahte araştırma, kesin vaat ("7 günde 5 kilo") yazma. Emin olmadığın rakamı verme.
- Tıbbi tavsiye verme. Gerekiyorsa caption'da "sağlık sorunun varsa uzmana danış" de.
- Kapak merak uyandırsın ama yalan vaat etmesin. Her içerik slaytı TEK fikir anlatsın.
- Slayt metinlerinde emoji kullanma. Caption'da en fazla 3 emoji.
- Karusel akışı: 1) merak uyandıran kapak 2) yaygın yanlış inanış ya da sorunun özü 3) bilimin söylediği 4) bugün uygulayabileceğin somut adım (süre, tekrar, porsiyon gibi genel kabul gören aralıklar) 5) en sık yapılan hata ya da dikkat edilecek nokta. Genel geçer cümle yazma; her slayt okuyana yeni bir şey öğretsin.
- Haberdeki kişi ya da sporcu varsa kapakta ya da ilk slaytta adıyla an, ama kişi hakkında doğrulanmamış iddia yazma; kanıtı kişiden bağımsız anlat.
- Caption ilk satırı kapaktan farklı, güçlü bir kanca olsun; sonda net bir soru sor.
- Vurgulanacak 1-3 kelimeyi **çift yıldız** içine al (sadece kapak başlığı ve içerik başlıklarında).
Sadece geçerli JSON döndür."""

SEMA = """Şu JSON şemasıyla cevap ver:
{"kapak": {"etiket": "en fazla 22 karakter, büyük harf olmasın gerekmez (örn: Bilimsel Protokol)", "baslik": "en fazla 60 karakter, merak uyandıran, **vurgulu** kelimeli"},
 "icerik": [{"baslik": "en fazla 38 karakter", "metin": "en fazla 150 karakter, 1-2 kısa cümle"}, ... tam 5 adet],
 "kapanis": {"baslik": "en fazla 38 karakter, etkileşim sorusu", "metin": "en fazla 100 karakter, kaydet/paylaş/takip et çağrısı"},
 "caption": "en fazla 700 karakter. İlk satır dikkat çeken kanca. Kısa paragraflar. Sonda yorum sorusu ve takip çağrısı.",
 "hashtagler": ["10 adet, # işaretsiz, Türkçe ve İngilizce karışık, aşırı genel olmayan"]}"""

def gecerli(p):
    try:
        return (len(p["icerik"]) == 5 and len(p["kapak"]["baslik"]) <= 70 and len(p["kapanis"]["metin"]) <= 120
                and all(len(i["metin"]) <= 170 and len(i["baslik"]) <= 46 for i in p["icerik"])
                and len(p["caption"]) <= 900 and len(p["hashtagler"]) >= 5)
    except (KeyError, TypeError):
        return False


def main():
    gecmis = json.load(open("gecmis.json", encoding="utf-8"))
    # gönderilerin çoğu güncel gündemden, kalanı hazır havuzdan
    konu = (gundem_konu(gecmis) if random.random() < 0.85 else None) or konu_sec()
    print("Konu:", konu["konu"], "|", konu["kategori"])
    for _ in range(3):
        bilgi = f"Güncel bilgi (yalnızca bunlara dayan, üstüne ekleme yapma): {konu['bilgi']}\n" if konu.get("bilgi") else ""
        post = claude(f"Konu: {konu['konu']}\nKategori: {konu['kategori']}\n{bilgi}\n{SEMA}", SISTEM)
        if gecerli(post):
            break
        print("Metin sınırlara uymadı, yeniden üretiliyor", file=sys.stderr)
    else:
        sys.exit("Uygun metin üretilemedi")
    post["konu"], post["kategori"] = konu["konu"], konu["kategori"]
    os.makedirs("out", exist_ok=True)
    json.dump(post, open("out/post.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
