"""out/post.json -> out/<damga>_1..7.jpg (1080x1350). Şablon A/B sırayla, fotoğraf kategoriye göre."""
import html, json, random, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright

KOK = Path(__file__).parent.resolve()
AC, BG = "#22e6ff", "#050f17"
FD = (KOK / "fontlar").as_uri()
LOGO = (KOK / "logo.jpg").as_uri()


def fontface():
    f = ""
    rng = {"latin": "U+0000-00FF,U+0131,U+0152-0153,U+2000-206F,U+20AC,U+2122",
           "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20CF,U+2113"}
    for fam, pre, ws in (("Barlow Condensed", "bc", (700, 800)), ("Inter", "inter", (400, 600))):
        for w in ws:
            for sub, r in rng.items():
                f += f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('{FD}/{pre}-{sub}-{w}.woff2');unicode-range:{r}}}"
    return f


CSS = fontface() + f"""*{{box-sizing:border-box;margin:0}}body{{width:1080px;height:1350px;background:{BG};color:#fff;font-family:'Inter',sans-serif;position:relative;overflow:hidden}}
.bg{{position:absolute;inset:0;background-size:cover;background-position:center}}.ov{{position:absolute;inset:0}}
.mono{{position:absolute;top:70px;left:80px;display:flex;align-items:center;gap:20px;z-index:3}}
.lg{{width:84px;height:84px;border-radius:50%;box-shadow:0 0 0 3px {AC},0 0 30px {AC}88}}
.nm{{font-family:'Barlow Condensed';font-weight:700;font-size:44px;letter-spacing:3px;text-transform:uppercase}}
.main{{position:absolute;left:80px;right:80px;z-index:3}}
.chip{{display:inline-block;background:{AC};color:{BG};font-family:'Barlow Condensed';font-weight:800;font-size:38px;padding:8px 26px;border-radius:8px;margin-bottom:30px;letter-spacing:4px;text-transform:uppercase}}
h1{{font-family:'Barlow Condensed';text-transform:uppercase;font-size:140px;line-height:.98;font-weight:800;letter-spacing:1px;text-shadow:0 6px 40px #000}}
em{{font-style:normal;color:{AC}}}
h2{{font-family:'Barlow Condensed';text-transform:uppercase;font-size:96px;line-height:1.02;font-weight:800;letter-spacing:1px;margin-bottom:30px}}
p{{font-size:44px;line-height:1.45;font-weight:400;color:#e3f6fb}}
.card{{background:#07202ccc;border:2px solid {AC}66;border-radius:36px;padding:50px}}
.num{{font-family:'Barlow Condensed';font-size:220px;font-weight:800;color:{AC};line-height:1;text-shadow:0 0 50px {AC}66;margin-bottom:10px}}
.foot{{position:absolute;left:80px;right:80px;bottom:70px;display:flex;justify-content:space-between;font-size:32px;color:#a9cdd7;font-weight:600;letter-spacing:1px;z-index:3}}.foot b{{color:{AC}}}"""


def vurgu(s):
    return re.sub(r"\*\*(.+?)\*\*", r"<em>\1</em>", html.escape(s))


def sayfa(sablon, foto, kapak, govde, son=False):
    img = f"url('{foto.as_uri()}')"
    if kapak and sablon == "A":
        bg = (f"<div class=bg style=\"background-image:{img}\"></div><div class=ov style='background:linear-gradient(180deg,#050f1766 0%,#050f1700 25%,#050f17ee 70%,#050f17 100%)'></div>")
        pos = "bottom:190px"
    elif kapak:
        bg = (f"<div class=bg style=\"background-image:{img};height:720px\"></div><div class=ov style='background:linear-gradient(180deg,transparent 40%,{BG} 53%)'></div><div style='position:absolute;left:0;right:0;bottom:0;height:5px;background:{AC}'></div>")
        pos = "top:560px"
    else:
        bg = (f"<div class=bg style=\"background-image:{img};filter:blur(10px) brightness(.8)\"></div><div class=ov style='background:#050f17dd'></div>")
        pos = "top:230px;bottom:190px;display:flex;flex-direction:column;justify-content:center"
    ok = ("KAYDIR <svg width=40 height=22 viewBox='0 0 40 22' style='vertical-align:-2px'><path d='M0 11h36M27 2l9 9-9 9' stroke='%s' stroke-width='4' fill='none'/></svg>" % AC) if not son else "KAYDET"
    return (f"<!doctype html><html lang=tr><meta charset=utf-8><style>{CSS}</style>{bg}"
            f"<div class=mono><img class=lg src='{LOGO}'><span class=nm>fitalgoritma</span></div>"
            f"<div class=main style='{pos}'>{govde}</div>"
            f"<div class=foot><span>@fitalgoritma</span><b>{ok}</b></div>")


# taşma koruması: yazı sığmazsa küçült
SIGDIR = """(k)=>{const m=document.querySelector('.main');const hs=[...m.querySelectorAll('h1,h2')];
 const ok=()=>{const r=m.getBoundingClientRect();return r.top>=215&&r.bottom<=1165};
 let n=0;while(!ok()&&n++<30){hs.forEach(h=>h.style.fontSize=(parseFloat(getComputedStyle(h).fontSize)-4)+'px');
 m.querySelectorAll('p').forEach(p=>p.style.fontSize=(parseFloat(getComputedStyle(p).fontSize)-1)+'px')}return ok()}"""


def main():
    post = json.load(open(KOK / "out/post.json", encoding="utf-8"))
    gecmis = json.load(open(KOK / "gecmis.json", encoding="utf-8"))
    sablon = "AB"[len(gecmis) % 2]
    foto_dir = KOK / "foto" / post["kategori"]
    fotolar = sorted(foto_dir.glob("*.jpg"))
    foto = KOK / "foto" / str(post.get("foto") or "")  # Gemini'nin konuya göre seçtiği
    if not foto.is_file():  # seçim yoksa/geçersizse: kategoride en uzun süredir kullanılmayan
        kullanim = {g.get("foto"): i for i, g in enumerate(gecmis)}
        en_eski = min(kullanim.get(f.name, -1) for f in fotolar)
        foto = random.choice([f for f in fotolar if kullanim.get(f.name, -1) == en_eski])
    damga = time.strftime("%y%m%d%H%M")

    sl = [sayfa(sablon, foto, True, f"<span class=chip>{html.escape(post['kapak']['etiket'])}</span><br><h1>{vurgu(post['kapak']['baslik'])}</h1>")]
    for i, x in enumerate(post["icerik"], 1):
        sl.append(sayfa(sablon, foto, False,
                        f"<div class=num>{i:02d}</div><div class=card><h2>{vurgu(x['baslik'])}</h2><p>{html.escape(x['metin'])}</p></div>"))
    k = post["kapanis"]
    sl.append(sayfa(sablon, foto, False, f"<h1 style='font-size:128px'>{vurgu(k['baslik'])}</h1><p style='margin-top:40px'>{html.escape(k['metin'])}</p>", son=True))

    adlar = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for n, h in enumerate(sl, 1):
            f = KOK / f"out/_{n}.html"
            f.write_text(h, encoding="utf-8")
            pg.goto(f.as_uri())
            pg.evaluate("document.fonts.ready")
            if not pg.evaluate(SIGDIR, None):
                raise SystemExit(f"Slayt {n} yazısı sığmadı")
            ad = f"{damga}_{n}.jpg"
            pg.screenshot(path=str(KOK / "out" / ad), type="jpeg", quality=90)
            adlar.append(ad)
            f.unlink()
        b.close()
    post.update(gorseller=adlar, foto=foto.name, sablon=sablon)
    json.dump(post, open(KOK / "out/post.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Üretildi:", adlar, "| şablon", sablon, "| foto", foto.name)


if __name__ == "__main__":
    main()
