"""Geteilter Baustein: "welche Tour meint eine Nachricht ohne Trip-Namen?"

Verschoben aus ``services.inbound_telegram_reader._find_active_trip``
(Issue #2184, Epic #2133 Scheibe S4) — bit-identisches Verhalten, nur ohne
``self.`` und ohne das Laden der Touren. Vorbild und Praezedenz:
``services.trip_day`` (#1470).

Der Schnitt liegt bewusst NACH dem Laden: ``load_all_trips(user_id)`` bleibt im
jeweiligen Reader, weil vier bestehende Testdateien
``services.inbound_telegram_reader.load_all_trips`` auf dem Modulpfad patchen —
wanderte der Aufruf mit hierher, griffen alle vier Patches ins Leere und liefen
still gegen echte Daten statt gegen Fixtures.

Issue #2282 Scheibe S1: ``resolve_active_target`` erweitert dieselbe Frage auf
Ortsvergleiche — EINE Funktion fuer Auswahl UND alle drei Ergebnistexte
(SPEC: docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md,
Abschnitt 1). Sie laedt selbst nichts, aus demselben Grund wie oben.

SPEC: docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from services.trip_day import trip_local_today
from utils.ascii_fold import fold_ascii

if TYPE_CHECKING:
    from app.trip import Trip

KEIN_KANDIDAT_TEXT = "Kein aktiver Trip oder Ortsvergleich gefunden."

_LABEL = {"route": "Trip", "vergleich": "Vergleich"}


def pick_active_trip(trips: list["Trip"], now_utc: datetime) -> "Trip | None":
    """Aktive Tour = erste Tour mit Datum-Overlap, sonst frueheste zukuenftige.

    Issue #1727 S5a: "heute" ist der ORTStag DIESER Tour (ADR-0044), nicht das
    Datum der Serveruhr. Der Vergleichstag wird deshalb IN der Schleife je Tour
    bestimmt — ein einziger, aus nur einer Tour abgeleiteter Tag waehlt an der
    Tourgrenze die bereits abgelaufene Tour. Auch der Zukunfts-Rueckfall
    rechnet je Tour.

    Args:
        trips: Touren des Mandanten, bereits geladen.
        now_utc: Zeitpunkt der eingehenden Nachricht. Pflichtparameter — ein
            Default auf die Systemuhr wuerde genau die Umgebungsuhr wieder
            einfuehren, die ADR-0051 Regel 3 verbietet.
    """
    if not trips:
        return None

    # 1. Overlap: stage[0].date <= Ortstag DIESER Tour <= stage[-1].date
    for trip in trips:
        if not trip.stages:
            continue
        today = trip_local_today(trip, now_utc)
        if trip.stages[0].date <= today <= trip.stages[-1].date:
            return trip

    # 2. Fallback: fruehester zukuenftiger Trip — "zukuenftig" ebenfalls am
    #    Ortstag DIESER Tour gemessen, nicht an einem gemeinsamen Wert.
    future = [
        t for t in trips
        if t.stages and t.stages[0].date > trip_local_today(t, now_utc)
    ]
    if future:
        return min(future, key=lambda t: t.stages[0].date)

    return None


@dataclass
class ZielErgebnis:
    """Ergebnis von ``resolve_active_target``. ``text`` ist nur bei
    mehrdeutiger/keiner Auswahl gesetzt, ``kind``/``target`` nur bei
    eindeutiger."""
    kind: str | None
    target: object | None
    text: str | None


def _vergleich_ist_aktiv(preset: dict, heute) -> bool:
    """Adressierbarkeits-Pruefung eines Ortsvergleichs (Issue #2282 Abschnitt
    1) — bewusst NICHT ``is_silenced()`` (Pause zaehlt hier als aktiv, sonst
    waere 'weiter' nie erreichbar). Nur ``archived_at``/``end_date`` machen
    inaktiv, Referenztag ist der UTC-Kalendertag von ``now_utc``."""
    if preset.get("archived_at"):
        return False
    end_date = preset.get("end_date")
    if end_date:
        try:
            from datetime import date as _date
            if _date.fromisoformat(str(end_date)) < heute:
                return False
        except ValueError:
            pass
    return True


# Adversary F003 (#2282 Fix-Loop 1): GSM-7 kennt fuer diese ASCII-Zeichen nur
# die 2-Septet-Erweiterungstabelle (Form-Feed, ^ { } \ [ ~ ] | €) -- eine
# Laengenrechnung, die 1 Zeichen = 1 Septet voraussetzt, darf sie im Ergebnis
# nie haben. Backtick hat ueberhaupt keine GSM-7-Entsprechung. Dieselbe
# Kurzliste ist bereits an einer Produktivstelle dupliziert (Issue #1796,
# output/renderers/alert/render.py::_ASCII_EXTENSION_REPLACEMENTS, Quelle
# der Wahrheit fuer die Zeichen selbst: tests/tdd/_gsm7_charset.py::
# GSM7_EXTENDED_TWO_SEPTET_CHARS) -- dieselbe akzeptierte Duplizierung statt
# eines Imports quer durch die Renderer-Schicht (Layering: trip_selection
# ist ein leichtgewichtiger Auswahl-Baustein, kein Renderer-Konsument).
_GSM7_UNSAFE_ASCII_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("[", "("), ("]", ")"), ("{", "("), ("}", ")"),
    ("\\", "/"), ("|", "-"), ("~", "-"), ("^", ""),
    ("€", "EUR"), ("\x0c", ""), ("`", "'"),
)


def _gsm7_sicher(text: str) -> str:
    """Faltet ``text`` auf ein GSM-7-EINSEPTET-sicheres Alphabet (AC-15,
    Adversary F003). ``fold_ascii`` (einzige Transliterations-Quelle im
    Projekt, Issue #1253) deckt jede Schrift -- inkl. Kyrillisch, Griechisch,
    CJK und die meisten Piktogramme -- auf reines ASCII ab; das ist mehr als
    das reine GSM-7-Alphabet, deshalb zusaetzlich die o.g. Erweiterungs-
    Zeichen ersetzen. Danach gilt 1 Zeichen = 1 GSM-7-Septet, ``len()`` misst
    also korrekt -- kein separates Gewichtungssystem mehr noetig."""
    folded = fold_ascii(text)
    for bad, good in _GSM7_UNSAFE_ASCII_REPLACEMENTS:
        folded = folded.replace(bad, good)
    return folded


def _rueckfrage_text(kandidaten: list[tuple[str, str]], channel: str) -> str:
    """Rueckfrage-Text bei Mehrdeutigkeit (Issue #2282 Abschnitt 1). Fuer
    ``channel == "premium_sms"`` werden die NAMEN zuerst GSM-7-sicher
    gefaltet (F003) und dann gekuerzt (Boden 4 Zeichen), nie die Anzahl der
    Kandidaten oder die Woerter Trip/Vergleich (AC-15). Telegram bleibt
    unveraendert (kein 160-Zeichen-Limit, volle Namen)."""
    if channel != "premium_sms":
        return _rueckfrage_mit_laenge(kandidaten, None)

    sicher = [(k, _gsm7_sicher(n)) for k, n in kandidaten]
    laengen = [len(n) for _, n in sicher if n]
    max_laenge = max(laengen, default=4)
    for laenge in range(max_laenge, 3, -1):
        text = _rueckfrage_mit_laenge(sicher, laenge)
        if len(text) <= 160:
            return text
    return _rueckfrage_mit_laenge(sicher, 4)


def _rueckfrage_mit_laenge(kandidaten: list[tuple[str, str]], laenge: int | None) -> str:
    def _kuerzen(n: str) -> str:
        return n if laenge is None else n[:laenge]

    liste = ", ".join(f"{_kuerzen(n)} ({_LABEL[k]})" for k, n in kandidaten)
    beispiel = _kuerzen(kandidaten[0][1]) if kandidaten else ""
    return f"Mehrdeutig: {liste}. Mit Namen antworten, z.B. '{beispiel} pause'."


def resolve_active_target(
    trips: "list[Trip]", presets: list[dict], now_utc: datetime, *, channel: str,
) -> ZielErgebnis:
    """Kind-neutrale Auswahl UND alle drei Ergebnistexte in einer Funktion
    (Issue #2282 Abschnitt 1). Laedt selbst nichts — ``trips``/``presets``
    kommen vom aufrufenden Reader.

    Entscheidungstabelle:
      1 Trip, 0 Vergleiche        -> eindeutig Trip
      0 Trip, genau 1 Vergleich   -> eindeutig Vergleich
      1 Trip, >=1 Vergleich       -> mehrdeutig
      0 Trip, >=2 Vergleiche      -> mehrdeutig
      0 Trip, 0 Vergleiche        -> keiner
    """
    trip = pick_active_trip(trips, now_utc)
    heute = now_utc.date()
    vergleiche = [p for p in presets if _vergleich_ist_aktiv(p, heute)]

    if trip and not vergleiche:
        return ZielErgebnis(kind="route", target=trip, text=None)
    if not trip and len(vergleiche) == 1:
        return ZielErgebnis(kind="vergleich", target=vergleiche[0], text=None)
    if not trip and not vergleiche:
        return ZielErgebnis(kind=None, target=None, text=KEIN_KANDIDAT_TEXT)

    kandidaten: list[tuple[str, str]] = []
    if trip:
        kandidaten.append(("route", trip.name))
    kandidaten += [("vergleich", p.get("name", "")) for p in vergleiche]
    return ZielErgebnis(kind=None, target=None, text=_rueckfrage_text(kandidaten, channel))
