"""Leser fuer den 3-Tages-Ausblick in zugestellten Ausgaben (Issue #3155, B4).

SPEC: docs/specs/modules/feat_3155_ein_name_ausblick.md (AC-1..AC-5, AC-10,
AC-11). Ober-Spec: docs/specs/modules/feat_3122_was_steht_wo.md AC-8/AC-34.

Das Soll steht von Hand hier (Name DE/EN, verbotene Altnamen), nie aus dem
Katalog gelesen: ein falscher Katalogwert soll den Test rot faerben, nicht
mitwandern. Die Leser erkennen den Ausblick-Block NAMENSUNABHAENGIG an seinen
Zeilen (HTML-Tabelle mit Tag-Spalte, Klartext-Tageszeilen, Telegram-Bubble mit
Tageszeilen) -- so trennen die Falllisten "Block da/nicht da" (AC-1..AC-4)
sauber von "Block heisst richtig" (AC-10/AC-11).
"""
from __future__ import annotations

import html as html_mod
import re
from typing import Optional

#: Der eine Name (Spec Entscheidung 6, Ober-Spec Nr. 15) -- von Hand.
NAME = {"de": "3-Tages-Ausblick", "en": "3-day outlook"}

#: Verbotene Namen des Ausblick-Blocks bzw. einer Oberflaechen-Beschriftung
#: (AC-11). Teilzeichenketten: kommen nirgends in der Ausgabe vor.
ALTE_NAMEN_TEIL = ("Mehrtages-Trend", "3-Tages-Vorschau", "Nächste Etappen",
                   "Naechste Etappen", "Next stages", "Multi-day trend",
                   "3-day preview")
#: "Ausblick"/"Outlook" ist verboten als ALLEINIGER Blocktitel (ganze Zeile
#: bzw. ganzer Textknoten) und als Kopf einer Variante ("Ausblick · …").
ALTE_TITEL = ("ausblick", "outlook")

#: Alle Namen, unter denen ein Ausblick-Kopf heute oder kuenftig steht --
#: nur zum ERKENNEN des Blocks (namensunabhaengig), nie als Soll.
_KOPF_ERKENNUNG = {"ausblick", "outlook", NAME["de"].casefold(), NAME["en"].casefold()}


def html_textknoten(html: str) -> list[str]:
    """Sichtbare Textknoten des HTML-Teils (getrimmt, entitaeten-dekodiert,
    ohne ``<style>``/``<head>``)."""
    rumpf = re.sub(r"(?is)<(style|head|script)\b.*?</\1>", " ", html)
    knoten = re.split(r"<[^>]+>", rumpf)
    return [html_mod.unescape(k).strip() for k in knoten if html_mod.unescape(k).strip()]


def textzeilen(text: str) -> list[str]:
    return [z.strip() for z in text.splitlines()]


def alte_namen_in(texte: list[str]) -> list[str]:
    """Fundstellen verbotener Namen (AC-11) in Zeilen/Textknoten."""
    funde = []
    for t in texte:
        for alt in ALTE_NAMEN_TEIL:
            if alt.casefold() in t.casefold():
                funde.append(f"{alt!r} in {t!r}")
        kopf = t.casefold().strip()
        if kopf in ALTE_TITEL or re.match(r"^(ausblick|outlook)\s*·", kopf):
            funde.append(f"Blocktitel {t!r}")
    return funde


def name_steht(texte: list[str], lang: str) -> bool:
    """Steht der eine Name als eigene Zeile/eigener Textknoten (Gross-/
    Kleinschreibung frei: die HTML-Eyebrow schreibt der Renderer gross)?"""
    soll = NAME[lang].casefold()
    return any(t.casefold().strip() == soll for t in texte)


# ---------------------------------------------------------------------------
# Trip-Telegram
# ---------------------------------------------------------------------------

def trip_telegram_ausblick(bubbles: list[str]) -> Optional[str]:
    """Die Ausblick-Bubble des Trip-Telegrams (erste Zeile ist ein Ausblick-
    Kopf, danach Tageszeilen) oder None -- namensunabhaengig."""
    for b in bubbles:
        zeilen = b.splitlines()
        if zeilen and zeilen[0].strip().casefold() in _KOPF_ERKENNUNG and len(zeilen) > 1:
            return b
    return None


def trip_telegram_kopf(bubbles: list[str]) -> Optional[str]:
    b = trip_telegram_ausblick(bubbles)
    return None if b is None else b.splitlines()[0].strip()


# ---------------------------------------------------------------------------
# Orte-Telegram
# ---------------------------------------------------------------------------

def orte_telegram_koepfe(text: Optional[str]) -> list[str]:
    """Ausblick-Koepfe im Orte-Telegram (eingerueckte Kopfzeile je Ort, danach
    Tageszeilen) -- namensunabhaengig; [] = kein Ausblick."""
    if not text:
        return []
    zeilen = text.splitlines()
    koepfe = []
    for i, z in enumerate(zeilen):
        if z.startswith("   ") and z.strip().casefold() in _KOPF_ERKENNUNG:
            folge = zeilen[i + 1] if i + 1 < len(zeilen) else ""
            if re.match(r"^\s+\S{2,3}\s", folge):
                koepfe.append(z.strip())
    return koepfe
