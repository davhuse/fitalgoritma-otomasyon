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
    for deneme in range(5):
        model = MODELLER[min(deneme // 2, len(MODELLER) - 1)]  # hata sürerse sıradaki modele geç
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens,
                                           "temperature": 0.9}},
                timeout=120,
            )
            r.raise_for_status()
            metin = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(metin)
        except Exception as e:  # ağ, kota ya da bozuk JSON: tekrar dene
            print("Gemini hatası:", e, file=sys.stderr)
            time.sleep(8 * (deneme + 1))
    sys.exit("Gemini 5 denemede cevap veremedi")


def ara(prompt):
    """Google aramasıyla güncel bilgi toplar (düz metin; arama aracı JSON moduyla birlikte kullanılamaz)."""
    global MODELLER
    MODELLER = MODELLER or modelleri_bul()
    for model in MODELLER:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]},
                timeout=120)
            r.raise_for_status()
            return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
        except Exception as e:
            print("Arama hatası:", e, file=sys.stderr)
    return None


def gundem_konu(gecmis):
    """Güncel gündemden yeni bir konu + doğrulanmış bilgi çıkarır; olmazsa None (havuza düşülür)."""
    bugun = time.strftime("%d.%m.%Y")
    ham = ara(f"Bugün {bugun}. Türkiye'de ve dünyada fitness, spor bilimi, antrenman, sağlıklı beslenme ve toparlanma alanında "
              "son günlerde gündemde olan 6 konuyu bul (yeni bilimsel çalışmalar, sosyal medyada tartışılan antrenman/beslenme akımları, "
              "sıkça sorulan sorular). Her biri için: konu başlığı ve güvenilir kaynaklara dayanan 2-3 somut bilgi yaz. "
              "Kişi ismi, marka, dedikodu ve kanıtı zayıf ya da tehlikeli iddiaları alma.")
    if not ham:
        return None
    onceki = [g["konu"] for g in gecmis[-40:]]
    sec = claude(f"Aşağıdaki gündem notlarından, Instagram karuseli için en merak uyandırıcı ve bilimsel olarak sağlam TEK konuyu seç. "
                 f"Şunlara benzer olmasın: {onceki}.\n\nNOTLAR:\n{ham[:6000]}\n\n"
                 f"Sadece JSON ver: " + '{"konu": "soru ya da iddia biçiminde başlık", "kategori": "' + "|".join(KATEGORILER) +
                 '", "bilgi": "bu konuyla ilgili notlardaki somut ve doğru bilgiler, 600 karakteri geçmesin"}',
                 "Sadece geçerli JSON döndür. Notlarda olmayan bilgi uydurma.")
    if sec.get("kategori") in KATEGORILER and sec.get("konu"):
        return sec
    return None


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
    aday = [k for k in bos if k["kategori"] not in son] or bos
    return random.choice(aday)


SISTEM = """Sen Türkiye'deki "fitalgoritma" Instagram hesabının içerik editörüsün. Hesap: biyomekanik, kas gelişimi, veri odaklı antrenman, bilimsel beslenme.
Kurallar:
- Türkçe, sade, samimi, "sen" dili. Jargon çıkarsa tek cümleyle açıkla.
- Bilimsel olarak doğru ve temkinli ol. Uydurma sayı, sahte araştırma, kesin vaat ("7 günde 5 kilo") yazma. Emin olmadığın rakamı verme.
- Tıbbi tavsiye verme. Gerekiyorsa caption'da "sağlık sorunun varsa uzmana danış" de.
- Kapak merak uyandırsın ama yalan vaat etmesin. Her içerik slaytı TEK fikir anlatsın.
- Slayt metinlerinde emoji kullanma. Caption'da en fazla 3 emoji.
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
    konu = (gundem_konu(gecmis) if random.random() < 0.7 else None) or konu_sec()
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
