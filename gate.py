"""Zamanlayıcı geç/eksik çalışsa da günde 4 paylaşımı garanti eder.
Her yarım saatte çalışır; son geçen paylaşım saatinin penceresinde henüz paylaşım yoksa 'devam=true' der."""
import json, os, sys
from datetime import datetime, timedelta, timezone

SAATLER = [(9, 0), (13, 0), (18, 0), (21, 30)]  # Türkiye saati
TR = timezone(timedelta(hours=3))

if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
    devam = True
else:
    simdi = datetime.now(TR)
    slotlar = [simdi.replace(hour=h, minute=m, second=0, microsecond=0) for h, m in SAATLER]
    gecen = [s for s in slotlar if s <= simdi]
    if not gecen:
        devam = False  # gece yarısı - 09:00 arası paylaşım yok
    else:
        pencere = gecen[-1]
        # geçmişteki saatler UTC yazılıyor (runner saati)
        paylasimlar = [datetime.strptime(g["tarih"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                       for g in json.load(open("gecmis.json", encoding="utf-8"))]
        devam = not any(p >= pencere for p in paylasimlar)
        try:  # Instagram engeli sonrası bekleme
            if datetime.now(timezone.utc) < datetime.strptime(json.load(open("bekle.json"))["until"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc):
                devam = False
        except (OSError, KeyError, ValueError):
            pass
    print("Şimdi (TR):", simdi.strftime("%H:%M"), "| pencere:", gecen[-1].strftime("%H:%M") if gecen else "-")

print("Karar: paylaş" if devam else "Karar: bu pencerede zaten paylaşıldı / zamanı değil")
with open(os.environ["GITHUB_OUTPUT"], "a") as f:
    f.write(f"devam={'true' if devam else 'false'}\n")
