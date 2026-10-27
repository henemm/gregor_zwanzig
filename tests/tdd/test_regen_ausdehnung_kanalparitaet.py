"""TDD RED — Issue #2051 Scheibe S2b: Langform und Kurzform nennen DIESELBEN
km-Grenzen in derselben Reihenfolge.

SPEC: docs/specs/modules/feat_2051_s2b_ausdehnung_kanaele.md — AC-10.

Fachlicher Kern: die beiden Textformen unterscheiden sich in der WORTFORM
(`Nass km 8-12, km 19-21` gegen `km8-12,19-21`), niemals im ZAHLENINHALT.
Auf dem Pass liest der Nutzer E-Mail/Telegram, auf der Huette nur die
Premium-SMS — zwei verschiedene Zahlenaussagen ueber dieselbe Strecke waeren
ein Widerspruch, den niemand aufloesen kann.

Muster: `test_onset_menge_kanalparitaet.py` (#2046), hier auf der
Renderer-Ebene, weil beide Formen aus demselben `OnsetEvent` entstehen.

RED-Ursache: die Kurzform traegt heute ueberhaupt keine Zonenangabe.

Mock-frei: echte `OnsetEvent`/`RainZone`/`AlertMessage`-Objekte durch die
echten Renderer.
"""
from __future__ import annotations

import re

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_email, render_sms
from services.rain_extent import RainZone

_ZONE_A = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)
_ZONE_B = RainZone(km_from=19.0, km_to=21.0, onset_minutes=50, event_end_minutes=70)

_PAAR_RE = re.compile(r"(\d+)-(\d+)")


def _msg() -> AlertMessage:
    event = OnsetEvent(
        onset_minutes=25, onset_time="15:00", km_from=0.0, km_to=6.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", location_label="Sillian",
        onset_precip_mm=2.5, event_end_time="16:30",
        km_measured=True, rain_zones=(_ZONE_A, _ZONE_B),
    )
    return AlertMessage(
        trip_short="KHW 403", stand_at="14:35", events=(event,),
        source="Radar (DWD)",
    )


def _paare_langform(plain: str) -> list[tuple[int, int]]:
    """Die Zahlenpaare der LANGFORM-Ausdehnung (`· Nass km 8-12, km 19-21`).

    Bewusst erst ab dem `Nass`-Abschnitt gelesen: die uebrige Zeile traegt
    ihre eigene km-Spanne (Segment-Lage), die hier nichts zu suchen hat."""
    treffer = re.search(r"· Nass (km [^·\n]*)", plain)
    if not treffer:
        return []
    return [(int(a), int(b)) for a, b in _PAAR_RE.findall(treffer.group(1))]


def _paare_kurzform(sms: str) -> list[tuple[int, int]]:
    """Die Zahlenpaare der KURZFORM-Ausdehnung (` km8-12,19-21`)."""
    treffer = re.search(r" km([\d,-]+)", sms)
    if not treffer:
        return []
    return [(int(a), int(b)) for a, b in _PAAR_RE.findall(treffer.group(1))]


def test_ac10_langform_und_kurzform_nennen_dieselben_km_grenzen():
    """AC-10 GIVEN ein `OnsetEvent` mit zwei Zonen km 8-12 und km 19-21,
    einmal ueber die E-Mail-Langform und einmal ueber die Kurzform gerendert
    (DIESELBEN Rohdaten)
    WHEN beide Texte auf ihre Zonenwerte geprueft werden
    THEN tragen beide dieselben km-Grenzen in derselben Reihenfolge —
    unterschiedliche Wortform, identischer Zahleninhalt.

    Der Sollwert wird aus den Zonen der Fixture abgeleitet, nicht getippt;
    zusaetzlich werden die beiden EXTRAHIERTEN Listen direkt gegeneinander
    geprueft — eine Verschiebung nur in einem der beiden Renderer faellt so
    auf, auch wenn beide dieselbe Form behalten.

    RED heute: die Kurzform traegt keine Zonenangabe, ihre Paarliste ist
    leer."""
    erwartet = [
        (int(round(z.km_from)), int(round(z.km_to))) for z in (_ZONE_A, _ZONE_B)
    ]
    msg = _msg()

    _html, plain = render_email(msg)
    sms = render_sms(msg)

    lang = _paare_langform(plain)
    kurz = _paare_kurzform(sms)

    assert lang == erwartet, (
        f"AC-10: die Langform muss {erwartet} nennen, extrahiert {lang}:\n{plain}"
    )
    assert kurz == erwartet, (
        f"AC-10: die Kurzform muss {erwartet} nennen, extrahiert {kurz}: {sms!r}"
    )
    assert lang == kurz, (
        f"AC-10: Langform {lang} und Kurzform {kurz} nennen verschiedene "
        f"km-Grenzen.\nLangform:\n{plain}\nKurzform: {sms!r}"
    )
