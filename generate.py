"""Konu seçer, Claude ile karusel metni + caption + hashtag üretir -> out/post.json"""
import json, os, random, re, sys, time
import requests

MODEL = "claude-sonnet-5-5"
KATEGORILER = ["kardiyo", "kuvvet", "beslenme", "toparlanma", "motivasyon"]


def claude(prompt, system, max_tokens=3500):
    for deneme in range(4):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                json={"model": MODEL, "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            r.raise_for_status()
            metin = r.json()["content"][0]["text"]
            return json.loads(re.search(r"[\[{].*[\]}]", metin, re.S).group(0))
        except Exception as e:  # ağ, kota ya da bozuk JSON: tekrar dene
            print("Claude hatası:", e, file=sys.stderr)
            time.sleep(5 * (deneme + 1))
    sys.exit("Claude 4 denemede cevap veremedi")


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
    konu = konu_sec()
    print("Konu:", konu["konu"], "|", konu["kategori"])
    for _ in range(3):
        post = claude(f"Konu: {konu['konu']}\nKategori: {konu['kategori']}\n\n{SEMA}", SISTEM)
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
