#!/usr/bin/env python3
"""Bilder der echten Oberflaeche fuer die oeffentlichen Funktionsseiten (Issue #3319).

SPEC: docs/specs/modules/oeffentliche_doku_3319.md (AC-8, AC-9)
RUNBOOK: docs/runbooks/funktionen_screenshots.md

Meldet sich per Playwright mit dem Staging-Pruefkonto an (Zugang
``GZ_PRUEFKONTO_USER``/``GZ_PRUEFKONTO_PASS`` aus der Staging-``.env``; das Konto
traegt den Mockup-Seed aus ``scripts/staging_pruefkonto_mockupdaten.py``: Trip
GR221 Mallorca, Ortsvergleich Muensterland, vier Kanaele mit Fiktivwerten) und
nimmt je Sprache (Cookie ``gz_lang`` und Kontosprache) die UI-Bilder auf:
Cockpit, Trip anlegen, Trip-Uebersicht, Reiter Wetter und Zustellung, Archiv,
Ortsvergleich, Kanaele im Konto und Konto (Level/Mengen).
Ausgabe als WebP unter ``frontend/static/funktionen/`` (de) bzw.
``frontend/static/funktionen/en/`` (en); die Masse landen per Merge in
``frontend/src/lib/components/organisms/funktionen/bildmasse.json``.

Personendaten (AC-9): vor JEDER Aufnahme maskiert das Skript Mail-Adressen und
Telefonnummern (auch gekuerzt angezeigte wie „name@…“ oder „+49 171 …“) im
sichtbaren Seitentext und in Eingabefeldern und prueft danach
mit ``pruefe_vor_aufnahme`` den gesamten sichtbaren Text: steht dort noch eine
Mail-Adresse oder Telefonnummer, die nicht in ``FIKTIV_ERLAUBT`` steht, bricht
das Skript ab (``PersonendatenGefunden``), es entsteht kein Bild.

Nur Staging (``https://staging.gregor20.henemm.com``), nie Produktion. Laeuft
auf dem Host (Staging-``.env`` lesbar).

Usage:
    uv run python scripts/funktionen_screenshots.py [--sprache de|en] [--nur NAME ...]
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "frontend" / "static" / "funktionen"
BILDMASSE = PROJECT_ROOT / "frontend" / "src" / "lib" / "components" / "organisms" / "funktionen" / "bildmasse.json"
STAGING_ENV = Path("/home/hem/gregor_zwanzig_staging/.env")
BASIS_URL = "https://staging.gregor20.henemm.com"
SPRACHEN = ("de", "en")

# Seed-Kennungen (scripts/staging_pruefkonto_mockupdaten.py)
TRIP_ID = "gz2967-gr221-mallorca"
VERGLEICH_NAME = "Münsterland"

# Masken: so erscheinen Mail-Adressen und Telefonnummern auf den Bildern.
MASKE_MAIL = "wanderer@beispiel.invalid"
MASKE_TELEFON = "+49 ••• •••••••"

#: Einzige erlaubte Kontaktdaten im sichtbaren Text: die Masken und die
#: Fiktivwerte des Seeds (``.invalid``-Zweitempfaenger). Alles andere ist ein Befund.
FIKTIV_ERLAUBT: frozenset[str] = frozenset({
    MASKE_MAIL,
    MASKE_TELEFON,
    "pruefkonto-2967@gregor-test.invalid",
})

# Mail-Adressen, auch gekuerzt angezeigte („name@…“, „name@...“). Kuerzel wie
# „BKN@9“ (SMS-Token) fallen nicht darunter: nach dem @ folgt dort eine Ziffer.
_MAIL_MUSTER = (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
                r"|[A-Za-z0-9._%+-]{2,}@\s?(?:\.\.\.|…)")
# Telefonnummern: international (+49 …, 0049 …) oder national mit Vorwahl (0171 …),
# auch gekuerzt angezeigt („+49 171 …“). Uhrzeiten, Datumsangaben, Hoehen und
# Bruchzahlen fallen bewusst nicht darunter.
_TELEFON_MUSTER = (r"(?<![\w.:/\-])(?:\+|00)\d{1,3}(?:[ \-/]?\d){6,14}(?!\w)"
                   r"|(?<![\w.:/\-])0\d{2,4}[ \-/]?\d{5,10}(?!\w)"
                   r"|(?<![\w.:/\-])(?:\+|00)\d{1,3}[ \-/]?\d{2,}[\d \-/]*\s?(?:\.\.\.|…)")
_MAIL_RE = re.compile(_MAIL_MUSTER)
_TELEFON_RE = re.compile(_TELEFON_MUSTER)


class PersonendatenGefunden(RuntimeError):
    """Sichtbarer Text enthaelt eine Mail-Adresse oder Telefonnummer ausserhalb der Fiktiv-Liste."""


def _ziffern(s: str) -> str:
    return re.sub(r"\D", "", s)


def personendaten_befunde(text: str, erlaubt: frozenset[str] | set[str]) -> list[str]:
    """Alle Mail-Adressen und Telefonnummern in ``text``, die nicht erlaubt sind."""
    erlaubt_mail = {e.lower() for e in erlaubt if "@" in e}
    erlaubt_tel = {_ziffern(e) for e in erlaubt if "@" not in e and _ziffern(e)}
    befunde: list[str] = []
    for m in _MAIL_RE.finditer(text):
        if m.group(0).lower() not in erlaubt_mail:
            befunde.append(m.group(0))
    for m in _TELEFON_RE.finditer(text):
        if _ziffern(m.group(0)) not in erlaubt_tel:
            befunde.append(m.group(0).strip())
    return befunde


def pruefe_vor_aufnahme(text: str, erlaubt: frozenset[str] | set[str]) -> None:
    """Bricht mit ``PersonendatenGefunden`` ab, wenn der Text Kontaktdaten enthaelt."""
    befunde = personendaten_befunde(text, erlaubt)
    if befunde:
        # Die Befunde selbst nicht ausgeben (koennten echte Daten sein): nur die Anzahl.
        raise PersonendatenGefunden(
            f"{len(befunde)} Mail-Adresse(n)/Telefonnummer(n) ausserhalb der Fiktiv-Liste "
            "im sichtbaren Text - keine Aufnahme")


# ─── Bilddateien ────────────────────────────────────────────────────────────
MAX_BYTES = 195 * 1024


def ziel_datei(name: str, lang: str) -> Path:
    """``static/funktionen/<name>.webp`` (de) bzw. ``static/funktionen/en/<name>.webp``."""
    if lang not in SPRACHEN or not re.fullmatch(r"[a-z0-9-]+", name):
        raise ValueError(f"ungueltiges Bildziel {name!r}/{lang!r}")
    ordner = STATIC_DIR / "en" if lang == "en" else STATIC_DIR
    return ordner / f"{name}.webp"


def speichere_webp(png: bytes, ziel: Path, *, max_breite: int = 1200) -> tuple[int, int]:
    """PNG -> WebP (Qualitaet 80, bei Bedarf weniger bzw. kleiner, immer < 200 KB)."""
    from PIL import Image

    bild = Image.open(io.BytesIO(png)).convert("RGB")
    if bild.width > max_breite:
        bild = bild.resize((max_breite, round(bild.height * max_breite / bild.width)), Image.LANCZOS)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    qualitaet = 80
    while True:
        puffer = io.BytesIO()
        bild.save(puffer, "WEBP", quality=qualitaet, method=6)
        if puffer.tell() < MAX_BYTES:
            break
        if qualitaet > 55:
            qualitaet -= 5
        else:
            bild = bild.resize((round(bild.width * 0.85), round(bild.height * 0.85)), Image.LANCZOS)
    ziel.write_bytes(puffer.getvalue())
    anzeige = ziel.relative_to(PROJECT_ROOT) if ziel.is_relative_to(PROJECT_ROOT) else ziel
    print(f"{anzeige}  {bild.width}x{bild.height}  {puffer.tell() // 1024} KB")
    return bild.width, bild.height


def masse_eintragen(neu: dict[str, dict[str, tuple[int, int]]]) -> None:
    """Masse je Bild und Sprache in bildmasse.json mergen (andere Eintraege bleiben)."""
    alt = json.loads(BILDMASSE.read_text(encoding="utf-8")) if BILDMASSE.exists() else {}
    for name, je_sprache in neu.items():
        eintrag = alt.setdefault(name, {})
        for lang, (w, h) in je_sprache.items():
            eintrag[lang] = {"width": w, "height": h}
    BILDMASSE.write_text(json.dumps(dict(sorted(alt.items())), indent="\t", ensure_ascii=False) + "\n",
                         encoding="utf-8")


# ─── Aufnahme der Oberflaeche ───────────────────────────────────────────────
# Maskiert Mail-Adressen und Telefonnummern in Textknoten, Eingabefeldern und
# Platzhaltern; liefert danach den gesamten sichtbaren Text (inkl. Feldwerte).
_MASKIEREN_JS = r"""
([mailMuster, telMuster, maskeMail, maskeTel]) => {
  const mail = new RegExp(mailMuster, 'g');
  const tel = new RegExp(telMuster, 'g');
  const ersetze = (s) => s.replace(mail, maskeMail).replace(tel, maskeTel);
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const neu = ersetze(n.nodeValue);
    if (neu !== n.nodeValue) n.nodeValue = neu;
  }
  for (const el of document.querySelectorAll('input, textarea')) {
    if (typeof el.value === 'string') {
      const neu = ersetze(el.value);
      if (neu !== el.value) el.value = neu;
    }
    if (el.placeholder) el.placeholder = ersetze(el.placeholder);
  }
  const felder = [...document.querySelectorAll('input, textarea')]
    .filter((el) => el.type !== 'hidden' && el.type !== 'password')
    .map((el) => `${el.value} ${el.placeholder || ''}`);
  return `${document.body.innerText}\n${felder.join('\n')}`;
}
"""

def maskieren_und_pruefen(page) -> None:
    # Dieselben Muster maskieren (JS-Regex, gleiche Syntax) und pruefen danach (Python).
    text = page.evaluate(_MASKIEREN_JS, [_MAIL_MUSTER, _TELEFON_MUSTER, MASKE_MAIL, MASKE_TELEFON])
    pruefe_vor_aufnahme(text, FIKTIV_ERLAUBT)


def _ruhig(page) -> None:
    page.wait_for_load_state("networkidle")
    # Animationen/Uebergaenge aus, Systemhinweise (Passkey-Angebot, Update) weg.
    page.add_style_tag(content=(
        "*,*::before,*::after{transition:none!important;animation:none!important;"
        "caret-color:transparent!important}"
        "[data-testid='passkey-angebot'],[data-testid='sw-update-hinweis']{display:none!important}"
    ))
    page.wait_for_timeout(400)


def aufnahme(page, lang: str, name: str, *, selektor: str | None = None,
             max_hoehe: int = 900) -> tuple[int, int]:
    """Bild ``name`` in Sprache ``lang`` aufnehmen (Ziel: ``ziel_datei``)."""
    return aufnehmen(page, ziel_datei(name, lang), selektor=selektor, max_hoehe=max_hoehe)


def aufnehmen(page, datei: Path, *, selektor: str | None = None,
              max_hoehe: int = 900) -> tuple[int, int]:
    """Maskieren, pruefen, erst DANN Element (oder Hauptbereich) aufnehmen und speichern.

    Einziger Aufnahmeweg des Skripts. Findet der Waechter nach dem Maskieren noch
    Kontaktdaten, bricht er mit ``PersonendatenGefunden`` ab, bevor ein Bildschirmfoto
    entsteht; ``datei`` wird dann nicht angelegt (Test:
    tests/test_funktionen_screenshots_waechter.py, echter Browser, Seiteninhalt lokal).
    """
    _ruhig(page)
    maskieren_und_pruefen(page)
    name = datei.stem
    ziel = page.locator(selektor).first if selektor else page.locator("main").first
    ziel.scroll_into_view_if_needed()
    box = ziel.bounding_box()
    if box is None:
        raise RuntimeError(f"{name}: Element {selektor or 'main'} nicht sichtbar")
    page.evaluate("window.scrollTo(0, 0)")
    box = ziel.bounding_box()
    # Genau der Elementrahmen (kein Rand: links laege sonst die Seitenleiste im Bild).
    clip = {"x": box["x"], "y": box["y"], "width": box["width"],
            "height": min(box["height"], max_hoehe)}
    png = page.screenshot(clip=clip, full_page=True)
    return speichere_webp(png, datei)


def anmelden(page, nutzer: str, passwort: str) -> None:
    page.goto(f"{BASIS_URL}/login")
    page.fill("input[name=username]", nutzer)
    page.fill("input[name=password]", passwort)
    page.locator("form button[type=submit]").last.click()
    page.wait_for_url(lambda u: "/login" not in u, timeout=20000)


def sprache_setzen(page, lang: str) -> None:
    """Kontosprache (Profil) und Besucher-Cookie auf ``lang``."""
    page.context.add_cookies([{"name": "gz_lang", "value": lang, "url": BASIS_URL}])
    antwort = page.request.put(f"{BASIS_URL}/api/auth/profile", data={"language": lang})
    if not antwort.ok:
        raise RuntimeError(f"Sprache {lang} nicht gesetzt (HTTP {antwort.status})")


def vergleich_pfad(page) -> str:
    """Pfad des Seed-Ortsvergleichs (Kennung ueber die Liste der eigenen Vergleiche)."""
    antwort = page.request.get(f"{BASIS_URL}/api/compare/presets")
    daten = antwort.json() if antwort.ok else []
    liste = daten if isinstance(daten, list) else daten.get("presets", [])
    for p in liste:
        if p.get("name") == VERGLEICH_NAME and p.get("id"):
            return f"/compare/{p['id']}"
    raise RuntimeError("Ortsvergleich Münsterland nicht gefunden - Seed gelaufen?")


def aufnahmen(page, lang: str, nur: set[str] | None) -> dict[str, tuple[int, int]]:
    masse: dict[str, tuple[int, int]] = {}

    def soll(name: str) -> bool:
        return not nur or name in nur

    def seite(pfad: str) -> None:
        page.goto(f"{BASIS_URL}{pfad}")

    if soll("cockpit"):
        seite("/")
        masse["cockpit"] = aufnahme(page, lang, "cockpit")
    if soll("trip-anlegen"):
        seite("/trips/new")
        masse["trip-anlegen"] = aufnahme(page, lang, "trip-anlegen", max_hoehe=760)
    for name, tab in (("trip-hub", "uebersicht"), ("trip-wetter", "wetter"), ("trip-zustellung", "zustellung")):
        if soll(name):
            seite(f"/trips/{TRIP_ID}?tab={tab}")
            masse[name] = aufnahme(page, lang, name)
    if soll("archiv"):
        seite("/archiv")
        masse["archiv"] = aufnahme(page, lang, "archiv", max_hoehe=440)
    if soll("ortsvergleich"):
        seite(vergleich_pfad(page))
        masse["ortsvergleich"] = aufnahme(page, lang, "ortsvergleich")
    if soll("konto-kanaele"):
        seite("/account")
        masse["konto-kanaele"] = aufnahme(page, lang, "konto-kanaele", selektor="#kanaele")
    if soll("konto-level"):
        seite("/account")
        masse["konto-level"] = aufnahme(page, lang, "konto-level", selektor="[data-testid='account-section']")
    return masse


def lade_zugang() -> tuple[str, str]:
    from scripts.staging_pruefkonto_mockupdaten import lade_env

    env = lade_env(STAGING_ENV)
    nutzer, passwort = env.get("GZ_PRUEFKONTO_USER"), env.get("GZ_PRUEFKONTO_PASS")
    if not nutzer or not passwort:
        raise SystemExit("GZ_PRUEFKONTO_USER/GZ_PRUEFKONTO_PASS fehlen in der Staging-.env")
    return nutzer, passwort


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--sprache", choices=SPRACHEN, action="append",
                        help="nur diese Sprache(n); Standard: de und en")
    parser.add_argument("--nur", nargs="*", default=None, help="nur diese Bildnamen")
    args = parser.parse_args(argv)
    sprachen = tuple(args.sprache or SPRACHEN)
    nur = set(args.nur) if args.nur else None

    nutzer, passwort = lade_zugang()
    from playwright.sync_api import sync_playwright

    alle: dict[str, dict[str, tuple[int, int]]] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1,
                                      locale="de-DE", timezone_id="Europe/Berlin")
        page = context.new_page()
        try:
            anmelden(page, nutzer, passwort)
            for lang in sprachen:
                sprache_setzen(page, lang)
                for name, mass in aufnahmen(page, lang, nur).items():
                    alle.setdefault(name, {})[lang] = mass
        finally:
            # Kontosprache des Pruefkontos zuruecksetzen (Seed-Stand: Deutsch).
            try:
                sprache_setzen(page, "de")
            except Exception:  # noqa: BLE001 - Aufraeumen darf den Befund nicht verdecken
                pass
            browser.close()
    masse_eintragen(alle)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT_ROOT))
    raise SystemExit(main())
