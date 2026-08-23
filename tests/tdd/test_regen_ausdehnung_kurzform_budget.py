"""TDD RED — Issue #2051 Scheibe S2b: das Zonen-Kuerzel der Kurzform ist
budget-bewusst — es entfaellt ganz, statt angeschnitten zu werden.

SPEC: docs/specs/modules/feat_2051_s2b_ausdehnung_kanaele.md — AC-8, AC-9.

Fachlicher Kern: das Kuerzel ist das ZULETZT angefuegte Element der Kurzform.
Passt es nicht vollstaendig ins Zeichenbudget, entfaellt es — niemals eine
halbe Spanne, niemals ein haengendes Komma. Bei mehreren Zonen werden von
vorn so viele genannt, wie vollstaendig passen.

Warum das zaehlt: `km8-1` (angeschnitten) waere im Satellitenkanal eine
FALSCHE Angabe, keine fehlende — und auf der Huette am Karnischen Hoehenweg
gibt es keinen zweiten Kanal, der sie richtigstellt.

RED-Ursache: die Kurzform (`render.py:927-996`) kennt kein Zonen-Token und
damit auch keine Budget-Regel dafuer.

Mock-frei: echte `OnsetEvent`/`RainZone`/`AlertMessage`-Objekte durch den
echten Renderer mit seinem oeffentlichen `limit`-Parameter.
"""
from __future__ import annotations

import pytest

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_sms
from services.rain_extent import RainZone

SMS_LIMIT = 140
# Deutlich ueber dem Limit: rendert derselbe Aufruf mit grosszuegigem Limit
# denselben Text, hat der harte Schnitt `body[:limit]` NICHT gegriffen.
UNGEDECKELT = 4000

_ZONE_A = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)
_ZONE_B = RainZone(km_from=19.0, km_to=21.0, onset_minutes=50, event_end_minutes=70)


def _extremfall_msg(*zonen: RainZone, km_measured: bool = True) -> AlertMessage:
    """Der kombinierte Extremfall (Spec AC-8/AC-9): 30-Zeichen-Ortsname (auf
    24 gekappt), `onset_precip_mm=99.9`, Untergrenzen-Ende ` >@23:59` und
    Guete-Marker `?` — die teuerste Zeitgruppe, die die Kurzform bauen kann.
    """
    ortsname = "Obertilliacher Bergwiesenalm".ljust(30, "x")
    assert len(ortsname) == 30, "Voraussetzung: 30-Zeichen-Ortsname"
    event = OnsetEvent(
        onset_minutes=40, onset_time="18:00", km_from=0.0, km_to=0.0,
        is_convective=True, intensity_label="Starker Regen",
        source_label="Radar (DWD)", location_label=ortsname,
        onset_precip_mm=99.9, event_end_time="23:59",
        event_ongoing_beyond_horizon=True,
        location_sharpness_limit_time="20:00",
        km_measured=km_measured, rain_zones=tuple(zonen),
    )
    return AlertMessage(
        trip_short="Alpen", stand_at="17:20", events=(event,),
        source="Radar (DWD)",
    )


def _kuerzel(*zonen: RainZone) -> str:
    """Das Zonen-Kuerzel, ABGELEITET aus den Zonenwerten der Fixture."""
    return " km" + ",".join(
        f"{int(round(z.km_from))}-{int(round(z.km_to))}" for z in zonen
    )


def _basistext() -> str:
    """Der zonenlose Extremfall-Text, vom Renderer selbst gebildet.

    Bewusst NICHT als Literal: die Spec-Rechnung (49 Zeichen) wird hier
    nachgemessen statt abgeschrieben — aendert eine andere Scheibe die
    Zeitgruppe, faellt das hier auf und nicht erst in einer Budget-Zusage,
    die dann eine andere Grenze meint als gemeint war."""
    return render_sms(_extremfall_msg(), limit=UNGEDECKELT)


def test_vorbedingung_die_budget_rechnung_der_spec_stimmt():
    """Vorbedingung (kein AC): die drei `limit`-Werte aus AC-8 haengen an
    zwei gemessenen Groessen — Basistext 49 Zeichen, erstes Kuerzel 7,
    volles Kuerzel 13 Zeichen. Stimmt eine davon nicht, pruefen die
    AC-8-Faelle unten andere Grenzen als die Spec meint."""
    basis = _basistext()

    assert basis == "Obertilliacher Bergwiese: TH@18:00 >@23:59? R99.9", (
        f"Der zonenlose Extremfall-Text hat sich veraendert: {basis!r}"
    )
    assert len(basis) == 49, f"Basistext: {len(basis)} statt 49 Zeichen: {basis!r}"
    assert len(_kuerzel(_ZONE_A)) == 7, (
        f"Erstes Kuerzel: {_kuerzel(_ZONE_A)!r} ist nicht 7 Zeichen lang"
    )
    assert len(_kuerzel(_ZONE_A, _ZONE_B)) == 13, (
        f"Volles Kuerzel: {_kuerzel(_ZONE_A, _ZONE_B)!r} ist nicht 13 Zeichen lang"
    )


# --------------------------------------------------------------------------
# AC-8 — drei Budget-Faelle: erste Zone passt / nichts passt / beide passen.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fall, limit, zonen_im_text",
    [
        ("a", 56, (_ZONE_A,)),           # 49 + 7 -> exakt Platz fuer Zone 1
        ("b", 55, ()),                   # 49 + 6 -> ein Zeichen zu wenig
        ("c", 62, (_ZONE_A, _ZONE_B)),   # 49 + 13 -> Platz fuer beide
    ],
)
def test_ac8_zonen_kuerzel_entfaellt_statt_angeschnitten_zu_werden(
    fall, limit, zonen_im_text,
):
    """AC-8 GIVEN den zonenlosen Basistext (49 Zeichen) und zwei Zonen
    km 8-12 / km 19-21 (Kuerzel-Kandidat ` km8-12,19-21`, 13 Zeichen; erste
    Zone allein ` km8-12`, 7 Zeichen)
    WHEN `render_sms` mit `limit=56` / `limit=55` / `limit=62` rendert
    THEN zeigt (a) NUR die erste Zone (exakt 56 Zeichen), (b) GAR KEIN
    Kuerzel (49 Zeichen, byte-identisch zum zonenlosen Stand) und (c) BEIDE
    Zonen (exakt 62 Zeichen) — nie eine angeschnittene Spanne, nie ein
    haengendes Komma.

    Fall (b) ist die Abwesenheits-Zusicherung, (a) und (c) sind ihre
    Positivkontrolle: derselbe Aufbau, ein verschobener `limit`-Wert,
    gegensaetzliches Ergebnis.

    Der Sollwert wird aus Basistext und Zonenwerten ZUSAMMENGESETZT, nicht
    getippt — ein hart verdrahteter Text im Produktivcode faellt dadurch auf.

    RED heute: die Kurzform kennt kein Zonen-Token, Fall (a) und (c)
    schlagen fehl."""
    erwartet = _basistext() + (_kuerzel(*zonen_im_text) if zonen_im_text else "")

    sms = render_sms(_extremfall_msg(_ZONE_A, _ZONE_B), limit=limit)

    assert sms == erwartet, (
        f"AC-8 Fall ({fall}, limit={limit}): erwartet {erwartet!r}, "
        f"erhalten {sms!r}"
    )
    assert len(sms) == len(erwartet) <= limit, (
        f"AC-8 Fall ({fall}): {len(sms)} Zeichen, erwartet {len(erwartet)} "
        f"und hoechstens {limit}: {sms!r}"
    )
    # Kein angeschnittenes Kuerzel, kein haengendes Komma — auch dann nicht,
    # wenn die Laenge zufaellig stimmte.
    assert not sms.endswith(","), f"AC-8 Fall ({fall}): haengendes Komma: {sms!r}"
    assert not sms.endswith("-"), (
        f"AC-8 Fall ({fall}): angeschnittene Spanne: {sms!r}"
    )
    if not zonen_im_text:
        assert " km" not in sms, (
            f"AC-8 Fall ({fall}): das Kuerzel passt nicht und muss deshalb "
            f"VOLLSTAENDIG entfallen: {sms!r}"
        )


# --------------------------------------------------------------------------
# AC-9 — der harte Schnitt `body[:limit]` greift auch mit Zonen nicht.
# --------------------------------------------------------------------------

def test_ac9_der_harte_schnitt_greift_im_extremfall_mit_zonen_nicht():
    """AC-9 GIVEN denselben kombinierten Extremfall mit zwei realistischen
    Zonen (max. erreichbar bei `RADAR_ZONE_MAX_POINTS=6`)
    WHEN derselbe Aufruf einmal mit `limit=140` und einmal ungedeckelt
    (`limit=4000`) rendert
    THEN sind beide Texte IDENTISCH und 62 Zeichen lang — der harte Schnitt
    `body[:limit]` (`render.py:996`) greift im Extremfall MIT Zonen genauso
    wenig wie ohne (Bestandsinvariante aus S1-AC-16).

    Ohne diese Pruefung waere jede Laengenzusage trivial erfuellbar: ein
    abgeschnittener Text ist immer kurz genug.

    RED heute: beide Texte sind 49 Zeichen lang (kein Zonen-Token)."""
    gedeckelt = render_sms(_extremfall_msg(_ZONE_A, _ZONE_B), limit=SMS_LIMIT)
    ungedeckelt = render_sms(_extremfall_msg(_ZONE_A, _ZONE_B), limit=UNGEDECKELT)

    assert gedeckelt == ungedeckelt, (
        "AC-9: der harte Schnitt greift im Extremfall mit Zonen.\n"
        f"  gedeckelt   ({len(gedeckelt)}) = {gedeckelt!r}\n"
        f"  ungedeckelt ({len(ungedeckelt)}) = {ungedeckelt!r}"
    )
    assert len(gedeckelt) == 62, (
        f"AC-9: erwartet 62 Zeichen (49 Basistext + 13 Kuerzel), erhalten "
        f"{len(gedeckelt)}: {gedeckelt!r}"
    )
