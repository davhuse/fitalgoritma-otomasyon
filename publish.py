"""out/ içindeki karuseli Instagram Graph API ile paylaşır, başarılıysa gecmis.json'a yazar."""
import json, os, sys, time
import requests

HOST = os.environ.get("IG_HOST", "https://graph.instagram.com") + "/v21.0"
TOKEN, UID = os.environ["IG_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
BASE = os.environ["IMG_BASE"]  # örn. https://raw.githubusercontent.com/kullanici/repo/gecici


def api(yol, **p):
    r = requests.post(f"{HOST}/{yol}", data={**p, "access_token": TOKEN}, timeout=60)
    if not r.ok:
        sys.exit(f"Instagram hatası ({yol}): {r.text}")
    return r.json()


def hazir_bekle(kimlik):
    for _ in range(40):
        d = requests.get(f"{HOST}/{kimlik}", params={"fields": "status_code", "access_token": TOKEN}, timeout=60).json()
        if d.get("status_code") == "FINISHED":
            return
        if d.get("status_code") in ("ERROR", "EXPIRED"):
            sys.exit(f"Konteyner hatası: {d}")
        time.sleep(3)
    sys.exit("Konteyner zamanında hazır olmadı")


def url_bekle(url):
    for _ in range(20):
        if requests.head(url, timeout=30).status_code == 200:
            return
        time.sleep(3)
    sys.exit(f"Görsel herkese açık değil: {url}")


post = json.load(open("out/post.json", encoding="utf-8"))
cocuklar = []
for ad in post["gorseller"]:
    url = f"{BASE}/{ad}"
    url_bekle(url)
    cocuklar.append(api(f"{UID}/media", image_url=url, is_carousel_item="true")["id"])
for c in cocuklar:
    hazir_bekle(c)

caption = post["caption"].strip() + "\n\n" + " ".join("#" + h.lstrip("#") for h in post["hashtagler"])
kap = api(f"{UID}/media", media_type="CAROUSEL", children=",".join(cocuklar), caption=caption)["id"]
hazir_bekle(kap)
medya = api(f"{UID}/media_publish", creation_id=kap)["id"]
print("Paylaşıldı, medya id:", medya)

gecmis = json.load(open("gecmis.json", encoding="utf-8"))
gecmis.append({"tarih": time.strftime("%Y-%m-%d %H:%M"), "konu": post["konu"], "kategori": post["kategori"],
               "foto": post["foto"], "baslik": post["kapak"]["baslik"], "medya": medya})
json.dump(gecmis, open("gecmis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
