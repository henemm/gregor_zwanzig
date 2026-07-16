"""Ueberlauf-Ehrlichkeit der Compare-Kanal-Renderer (Issue #1270, Nachbesserung).

SPEC: docs/specs/modules/compare_channel_preview_dispatch.md (AC-3)

Fehlerklasse "luegende Ausgabe" (vgl. #1269): ein Vergleich, der Orte
stillschweigend weglaesst, behauptet Vollstaendigkeit, die er nicht hat.
Hauskonvention dagegen ist das SMS-Laengen-Budget mit ` +k`-Ueberlauf-Marker
(`src/output/renderers/alert/render.py:507-535`, ADR-0011:42): Kopf immer,
Inhalte solange, wie das Ergebnis INKL. des evtl. noetigen Markers ins Budget
passt, Rest sichtbar als ` +k`.

RED-Grund (vor dem Fix):
  * `render_compare_sms` bricht die Ortsschleife wortlos ab (comparison.py:350)
    -> kein ` +k`, Orte verschwinden unsichtbar.
  * `render_compare_telegram` schneidet hart auf 4096 (`text[:max_chars]`,
    comparison.py:317) -> Rest mitten im Wort, kein Hinweis auf den Verlust.

KEINE Mocks: echte, synthetische `ComparisonResult`-Objekte gehen direkt in die
echten Renderer (Muster: tests/tdd/test_compare_channel_render_neutrality.py).
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.channel_layout import CHANNEL_LIMITS

TARGET_DATE = date(2026, 7, 8)
SMS_LIMIT = CHANNEL_LIMITS["sms"]["max_chars"]            # 140
TELEGRAM_LIMIT = CHANNEL_LIMITS["telegram"]["max_chars"]  # 4096

# ` +k` am Textende, k = Anzahl weggelassener Orte.
_OVERFLOW_MARKER = re.compile(r" \+(\d+)$")


def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.27, lon=11.39, elevation_m=1000)


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=13.5,
        wind_chill_c=12.5,
        wind10m_kmh=8.0,
        gust_kmh=15.0,
        precip_1h_mm=0.0,
        cloud_total_pct=30,
        uv_index=4.0,
        thunder_level=ThunderLevel.NONE,
        pop_pct=10,
        visibility_m=9000,
    )


def _result(names: list[str], errors: set[str] | None = None) -> ComparisonResult:
    """`errors` = Namen der Orte, deren Abruf fehlgeschlagen ist (`error` gesetzt,
    keine Messwerte) — der reale Zustand nach einem Provider-Ausfall."""
    errors = errors or set()
    locations = [
        LocationResult(
            location=_loc(f"loc-{i}", name),
            score=50 + i,
            temp_max=None if name in errors else 12.5 + i,
            temp_min=None if name in errors else 5.5,
            wind_max=None if name in errors else 8.0,
            gust_max=None if name in errors else 15.0,
            cloud_avg=None if name in errors else 30,
            sunny_hours=None if name in errors else 5,
            official_alerts=[],
            hourly_data=[] if name in errors else [_dp(9), _dp(12), _dp(15)],
            error="API-Fehler" if name in errors else None,
        )
        for i, name in enumerate(names)
    ]
    return ComparisonResult(
        locations=locations,
        time_window=(9, 16),
        target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 0),
    )


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------


def test_sms_overflow_marks_omitted_locations_with_plus_k():
    """GIVEN so viele Orte, dass das 140-Zeichen-Budget ueberlaeuft
    WHEN render_compare_sms rendert
    THEN endet der Text mit ' +k', k == Anzahl NICHT dargestellter Orte,
    und len(text) <= 140.

    RED: der Renderer bricht die Schleife wortlos ab (kein Marker)."""
    from output.renderers.comparison import render_compare_sms

    names = [f"Ortsname{i:02d}" for i in range(12)]
    text = render_compare_sms(_result(names))

    assert len(text) <= SMS_LIMIT, f"SMS-Budget verletzt: {len(text)} > {SMS_LIMIT}: {text!r}"
    match = _OVERFLOW_MARKER.search(text)
    assert match is not None, (
        "AC-3/#1269: Orte entfallen still — es fehlt der ' +k'-Ueberlauf-Marker "
        f"(Hauskonvention alert/render.py:507-535). Text: {text!r}"
    )
    shown = [name for name in names if name in text]
    assert int(match.group(1)) == len(names) - len(shown), (
        f"' +k' muss die weggelassenen Orte EXAKT zaehlen: k={match.group(1)}, "
        f"dargestellt={len(shown)}/{len(names)}. Text: {text!r}"
    )
    assert shown, "Mindestens ein Ort muss dargestellt sein"


def test_sms_without_overflow_has_no_marker():
    """GIVEN ein Ergebnis, bei dem alle Orte ins Budget passen
    WHEN render_compare_sms rendert
    THEN erscheint KEIN '+k'-Marker (kein Verlust => kein Hinweis)."""
    from output.renderers.comparison import render_compare_sms

    text = render_compare_sms(_result(["Ax", "Bx"]))

    assert len(text) <= SMS_LIMIT
    assert "Ax" in text and "Bx" in text
    assert _OVERFLOW_MARKER.search(text) is None, (
        f"Kein Ort entfaellt — der '+k'-Marker darf nicht erscheinen: {text!r}"
    )


def test_sms_degenerate_single_long_name_still_shows_content():
    """GIVEN der Degenerationsfall: ein Ort mit extrem langem Namen
    WHEN render_compare_sms rendert
    THEN ist das Ergebnis nicht nur die Ueberschrift und len <= 140.

    Vorbild: alert/render.py:534 — Garantie len<=limit auch im
    Degenerationsfall, aber NIE 'Ueberschrift + nichts'."""
    from output.renderers.comparison import render_compare_sms

    long_name = "Sankt" + "Wolfgangimsalzkammergut" * 20
    text = render_compare_sms(_result([long_name]))

    assert len(text) <= SMS_LIMIT, f"SMS-Budget verletzt: {len(text)}"
    head = text.split(":")[0] + ":"
    rest = text[len(head):].strip()
    assert rest, (
        "Degenerationsfall liefert nur die Ueberschrift ohne jeden Ort — "
        f"verboten (luegende Ausgabe). Text: {text!r}"
    )
    assert long_name[:20] in text, (
        f"Der einzige Ort muss erkennbar bleiben (ggf. gekuerzt). Text: {text!r}"
    )
    assert text.endswith("..."), (
        "Der Ortsname wurde beschnitten, sieht aber vollstaendig aus — die "
        f"Kuerzung muss erkennbar sein. Text: {text!r}"
    )


def test_sms_degenerate_long_names_marks_remaining_locations():
    """GIVEN mehrere Orte, von denen schon der erste das Budget sprengt
    WHEN render_compare_sms rendert
    THEN bleibt der erste Ort erkennbar UND die restlichen sind als ' +k'
    ausgewiesen (kein stiller Totalverlust)."""
    from output.renderers.comparison import render_compare_sms

    names = ["A" + "berglandschaft" * 12, "Bozen", "Chur"]
    text = render_compare_sms(_result(names))

    assert len(text) <= SMS_LIMIT, f"SMS-Budget verletzt: {len(text)}"
    match = _OVERFLOW_MARKER.search(text)
    assert match is not None and int(match.group(1)) == 2, (
        f"Zwei Orte entfallen — erwartet ' +2' am Ende. Text: {text!r}"
    )


def test_sms_error_locations_are_not_silently_dropped():
    """GIVEN 4 Orte, davon 2 mit `error` (alles passt ins Budget)
    WHEN render_compare_sms rendert
    THEN ist erkennbar, dass der Vergleich 4 Orte umfasst — die Fehler-Orte sind
    dargestellt ODER im ' +k'-Marker mitgezaehlt.

    RED-Grund: der Renderer filtert Fehler-Orte VOR der Ueberlauf-Zaehlung raus
    (comparison.py:389-396). Die SMS sieht dann aus wie ein 2-Orte-Vergleich —
    exakt die luegende Ausgabe aus #1269, die der eigene Docstring
    (comparison.py:373-378) ausschliesst. `render_compare_telegram` haelt
    Fehler-Orte sichtbar (comparison.py:308-311)."""
    from output.renderers.comparison import render_compare_sms

    names = [f"Ort{i:02d}" for i in range(4)]
    text = render_compare_sms(_result(names, errors={"Ort01", "Ort03"}))

    assert len(text) <= SMS_LIMIT, f"SMS-Budget verletzt: {len(text)}: {text!r}"
    match = _OVERFLOW_MARKER.search(text)
    omitted = int(match.group(1)) if match else 0
    shown = [name for name in names if name in text]
    assert len(shown) + omitted == len(names), (
        f"Die SMS behauptet einen Vergleich ueber {len(shown) + omitted} Orte, "
        f"tatsaechlich sind es {len(names)} — {len(names) - len(shown) - omitted} "
        f"Fehler-Ort(e) verschwinden spurlos (#1269). Text: {text!r}"
    )


def test_sms_error_locations_count_toward_overflow_marker():
    """GIVEN 15 Orte (10 mit Werten, 5 mit `error`), Budget laeuft ueber
    WHEN render_compare_sms rendert
    THEN gilt: dargestellte Orte + k == 15 (nicht 10) — der Marker darf die
    Fehler-Orte nicht unterschlagen."""
    from output.renderers.comparison import render_compare_sms

    names = [f"Ort{i:02d}" for i in range(15)]
    errors = {f"Ort{i:02d}" for i in range(10, 15)}
    text = render_compare_sms(_result(names, errors=errors))

    assert len(text) <= SMS_LIMIT, f"SMS-Budget verletzt: {len(text)}: {text!r}"
    match = _OVERFLOW_MARKER.search(text)
    assert match is not None, f"Ueberlauf ohne ' +k'-Marker: {text!r}"
    shown = [name for name in names if name in text]
    assert len(shown) + int(match.group(1)) == len(names), (
        f"' +k' muss ALLE nicht dargestellten Orte zaehlen (auch Fehler-Orte): "
        f"dargestellt={len(shown)}, k={match.group(1)}, gesamt={len(names)}. "
        f"Text: {text!r}"
    )


def test_sms_all_locations_failed_is_honest():
    """GIVEN alle Orte haben `error`
    WHEN render_compare_sms rendert
    THEN entsteht eine ehrliche Nachricht: die Orte sind erkennbar (oder als
    ' +k' ausgewiesen), nicht bloss die Ueberschrift und kein Eindruck eines
    leeren Vergleichs."""
    from output.renderers.comparison import render_compare_sms

    names = [f"Ort{i:02d}" for i in range(3)]
    text = render_compare_sms(_result(names, errors=set(names)))

    assert len(text) <= SMS_LIMIT, f"SMS-Budget verletzt: {len(text)}: {text!r}"
    head = text.split(":")[0] + ":"
    rest = text[len(head):].strip()
    assert rest, f"Nur die Ueberschrift, kein Inhalt: {text!r}"
    match = _OVERFLOW_MARKER.search(text)
    omitted = int(match.group(1)) if match else 0
    shown = [name for name in names if name in text]
    assert len(shown) + omitted == len(names), (
        f"Alle 3 Orte sind fehlerhaft — die SMS muss das ausweisen, statt einen "
        f"leeren Vergleich zu suggerieren. Text: {text!r}"
    )
    assert shown, (
        f"Kein einziger Ort erkennbar — die Nachricht sagt nicht, worum es geht. "
        f"Text: {text!r}"
    )


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def _telegram_over_limit_names() -> list[str]:
    """So viele Orte, dass der Telegram-Text sicher ueber 4096 Zeichen geht."""
    return [f"Telegramort{i:03d}" for i in range(150)]


def test_telegram_overflow_cuts_on_line_boundary_and_is_visible():
    """GIVEN Inhalt ueber 4096 Zeichen
    WHEN render_compare_telegram rendert
    THEN wird an einer Zeilen-/Wortgrenze geschnitten (kein mitten-im-Wort-Rest)
    und der Verlust ist im Text erkennbar.

    RED: aktuell harter Schnitt `text[:4096]` ohne jeden Hinweis."""
    from output.renderers.comparison import render_compare_telegram

    names = _telegram_over_limit_names()
    full = render_compare_telegram(_result(names))

    assert len(full) <= TELEGRAM_LIMIT, f"Telegram-Budget verletzt: {len(full)}"

    shown = [name for name in names if name in full]
    assert 0 < len(shown) < len(names), (
        "Fixture trifft den Ueberlauf nicht — Test waere aussagelos"
    )

    # Verlust erkennbar: die Zahl der weggelassenen Orte steht im Text.
    omitted = len(names) - len(shown)
    assert str(omitted) in full, (
        f"{omitted} Orte entfallen, ohne dass der Text das ausweist "
        f"(#1269, luegende Ausgabe). Ende: {full[-200:]!r}"
    )

    # Kein mitten-im-Wort-Rest: die letzte Zeile VOR dem Hinweis ist eine
    # vollstaendige Zeile des ungekuerzten Renders. (Ein Praefix-Vergleich auf
    # die Ortsnamen taugt hier nicht — die Namen teilen sich Praefixe.)
    body = full.split("…")[0].rstrip("\n")
    complete_lines = set(render_compare_telegram(_result(shown)).splitlines())
    assert body.splitlines()[-1] in complete_lines, (
        f"Letzte Zeile ist angeschnitten: {body.splitlines()[-1]!r}"
    )


def test_telegram_kept_lines_are_complete_lines():
    """GIVEN ein Ueberlauf-Ergebnis
    WHEN render_compare_telegram rendert
    THEN ist jede Zeile bis auf den Kuerzungs-Hinweis eine VOLLSTAENDIGE Zeile
    des ungekuerzten Renders (Zeilengrenze, keine halbe Datenzeile)."""
    from output.renderers.comparison import render_compare_telegram

    names = _telegram_over_limit_names()
    shown_names = [n for n in names if n in render_compare_telegram(_result(names))]
    reference = render_compare_telegram(_result(shown_names))
    complete_lines = set(reference.splitlines())

    text = render_compare_telegram(_result(names))
    lines = text.splitlines()
    unknown = [ln for ln in lines if ln and ln not in complete_lines]
    assert len(unknown) <= 1, (
        f"Mehr als der Kuerzungs-Hinweis ist keine vollstaendige Zeile: {unknown!r}"
    )


def test_telegram_without_overflow_has_no_truncation_notice():
    """GIVEN ein Ergebnis weit unter dem Budget
    WHEN render_compare_telegram rendert
    THEN erscheint kein Kuerzungs-Hinweis."""
    from output.renderers.comparison import render_compare_telegram

    text = render_compare_telegram(_result(["Innsbruck", "Bozen"]))

    assert "Innsbruck" in text and "Bozen" in text
    assert "gekürzt" not in text and "…" not in text, (
        f"Nichts entfaellt — kein Kuerzungs-Hinweis erlaubt: {text!r}"
    )
