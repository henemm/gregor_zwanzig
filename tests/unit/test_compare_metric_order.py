"""Metrik-Reihenfolge im Ortsvergleich (Issue #1359, Scheibe 1).

Die im Editor eingestellte Metrik-Reihenfolge muss identisch in HTML-Mail,
Klartext-Teil derselben Mail und Telegram-Nachricht ankommen; "Amtliche
Warnungen" bleibt dabei immer erste Zeile.

SPEC: docs/specs/modules/compare_metric_order.md

Alle Tests sind reine Renderer-Aufrufe mit fest gebauten ComparisonResult-
Objekten: kein Netz, keine Mails, kein Mock/patch (CLAUDE.md Test-Politik,
Schicht "Kern (deterministisch)").

AC-Zuordnung:
- AC-4 (Kern-Anteil): Klartext folgt der uebergebenen Reihenfolge  -> RED
- AC-4 (HTML-Absicherung): HTML kippt bereits korrekt mit          -> GRUEN (Regression)
- AC-5: Telegram folgt derselben Reihenfolge                        -> RED
- AC-6: "Amtliche Warnungen" immer an erster Stelle in der Mail     -> GRUEN (Regression)
- AC-7: Altbestand ohne gespeicherte Auswahl rendert unveraendert   -> GRUEN (Charakterisierung)
- AC-8: bewusste Leerauswahl zeigt keine Uebersichtszeilen
        (auf RENDERER-Ebene, s. Klasse)                             -> GRUEN (Regression)
- AC-10: die SMS zeigt die zwei VORDERSTEN Metriken der Reihenfolge  -> RED
"""
from __future__ import annotations

import re
from datetime import date, datetime

import pytest

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import (
    render_comparison_text, render_compare_sms, render_compare_telegram,
)
from output.renderers.email.compare_html import render_compare_html
from services.official_alerts.models import OfficialAlert
from services.report_config_resolver import resolve_compare_render_options

# ---------------------------------------------------------------------------
# Fixtures (fest, ohne Netz) — Werte sind bewusst unspektakulaer; geprueft wird
# ausschliesslich die REIHENFOLGE der Zeilen, nicht ihr Inhalt.
# ---------------------------------------------------------------------------


def _loc(loc_id: str, name: str) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=47.0, lon=11.0, elevation_m=600)


def _loc_result(loc_id: str, name: str, alerts: list | None = None) -> LocationResult:
    """Ort mit allen 26 Uebersichts-Metriken befuellbar/ableitbar."""
    return LocationResult(
        location=_loc(loc_id, name),
        score=1,
        temp_max=20.0, temp_min=10.0,
        wind_max=15.0, gust_max=30.0,
        wind_direction_avg=180,
        wind_chill_min=8.0, wind_chill_max=18.0,
        cloud_avg=40, cloud_low_avg=10, cloud_mid_avg=20, cloud_high_avg=30,
        sunny_hours=5,
        snow_depth_cm=1.0, snow_new_cm=2.0,
        precip_sum_mm=1.0, pop_max_pct=50, uv_index_max=4.0,
        visibility_min_m=10000,
        official_alerts=alerts or [],
    )


def _result(alerts: list | None = None) -> ComparisonResult:
    """Drei Orte (AC-4 verlangt mindestens drei)."""
    return ComparisonResult(
        locations=[
            _loc_result("a", "Aachen", alerts),
            _loc_result("b", "Bremen"),
            _loc_result("c", "Chemnitz"),
        ],
        time_window=(0, 23),
        target_date=date(2026, 7, 24),
        created_at=datetime(2026, 7, 24, 4, 0),
    )


def _alert() -> list[OfficialAlert]:
    return [OfficialAlert(
        source="test-1359", hazard="thunderstorm", level=3,
        label="Gewitterwarnung Stufe Orange",
    )]


# ---------------------------------------------------------------------------
# Auslese-Helfer: Zeilen-/Zell-Reihenfolge aus dem jeweiligen Render-Ergebnis
# ---------------------------------------------------------------------------

_HTML_LABEL_RE = re.compile(
    r'font-weight:500;font-size:12px;border-right:1px solid #f0ece1;">([^<]*)</td>'
)


def _text_labels(text: str) -> list[str]:
    """Labels der Uebersichtszeilen des ERSTEN Ortsblocks, in Render-Reihenfolge."""
    labels: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped == "STUNDENVERLAUF":
            break
        if not raw.startswith("   ") or stripped.startswith("⚠️") or ":" not in stripped:
            continue
        label = stripped.split(":", 1)[0]
        if label in labels:  # zweiter Ortsblock -> fertig
            break
        labels.append(label)
    return labels


def _html_labels(html: str) -> list[str]:
    return _HTML_LABEL_RE.findall(html)


# Kurz-Labels der SMS-Zellen (= dieselben wie Telegram, gemeinsamer Helfer
# `_channel_metric_cells`). Die SMS ist flach ("Ort Label Wert Label Wert"),
# deshalb wird ueber Tokens statt ueber ein Trennzeichen ausgelesen.
_SMS_LABEL_TOKENS = {"Temp", "Wind", "Sonne", "Wolken", "Schnee", "Neuschnee"}


def _sms_labels(msg: str) -> list[str]:
    """Kurz-Labels des ERSTEN Ortsteils der SMS, in Render-Reihenfolge."""
    _, sep, body = msg.partition(": ")
    if not sep:
        return []
    first_location = body.split("; ")[0]
    return [t for t in first_location.split(" ") if t in _SMS_LABEL_TOKENS]


def _telegram_labels(msg: str) -> list[str]:
    """Kurz-Labels der Metrik-Zellen des ERSTEN Ortsblocks."""
    for raw in msg.splitlines():
        if " · " not in raw and "keine Werte" not in raw:
            continue
        cells = raw.strip().split(" · ")
        return [c.split(" ", 1)[0] for c in cells if c and c != "keine Werte"]
    return []


# Zwei Reihenfolgen derselben Metrik-MENGE — der Unterschied ist der ganze Test.
ORDER_A = ["cloud_avg", "temp_max", "sunny_hours", "wind_max"]
ORDER_B = ["wind_max", "sunny_hours", "temp_max", "cloud_avg"]

_TEXT_LABEL = {
    "temp_max": "Temp max", "wind_max": "Wind",
    "sunny_hours": "Sonne", "cloud_avg": "Wolken",
}
_TELEGRAM_LABEL = {
    "temp_max": "Temp", "wind_max": "Wind",
    "sunny_hours": "Sonne", "cloud_avg": "Wolken",
}
_HTML_LABEL = {
    "temp_max": "Temp max", "wind_max": "Wind",
    "sunny_hours": "Sonne", "cloud_avg": "Wolken",
}


class TestAC4PlainTextFollowsMetricOrder:
    """AC-4 (Kern-Anteil) — RED: der Klartext-Teil der Vergleichs-Mail rendert
    heute eine fest verdrahtete Quellcode-Reihenfolge; `_metric_visible`
    (comparison.py:126-127) prueft nur Mitgliedschaft, nicht Position."""

    def test_plaintext_order_follows_enabled_metrics_order_a(self):
        text = render_comparison_text(_result(), enabled_metrics=list(ORDER_A))
        assert _text_labels(text) == [_TEXT_LABEL[m] for m in ORDER_A], (
            "Klartext muss der uebergebenen Metrik-Reihenfolge folgen.\n"
            f"Text:\n{text}"
        )

    def test_plaintext_order_flips_with_reversed_selection(self):
        text_a = render_comparison_text(_result(), enabled_metrics=list(ORDER_A))
        text_b = render_comparison_text(_result(), enabled_metrics=list(ORDER_B))
        labels_a, labels_b = _text_labels(text_a), _text_labels(text_b)
        assert labels_a != labels_b, (
            "Dieselbe Metrik-MENGE in zwei Reihenfolgen muss zwei verschiedene "
            f"Zeilenfolgen ergeben, ergab aber beide Male {labels_a}."
        )
        assert labels_b == [_TEXT_LABEL[m] for m in ORDER_B], (
            f"Erwartet {[_TEXT_LABEL[m] for m in ORDER_B]}, war {labels_b}.\n"
            f"Text:\n{text_b}"
        )

    def test_plaintext_order_matches_html_order_in_same_mail(self):
        """HTML und Klartext derselben Mail duerfen sich nicht widersprechen."""
        result = _result()
        html_labels = [
            lbl for lbl in _html_labels(
                render_compare_html(result, enabled_metrics=list(ORDER_A))
            ) if lbl != "Amtliche Warnungen"
        ]
        text_labels = _text_labels(
            render_comparison_text(result, enabled_metrics=list(ORDER_A))
        )
        assert text_labels == html_labels, (
            f"Klartext {text_labels} weicht von HTML {html_labels} derselben Mail ab."
        )

    def test_end_to_end_preset_order_reaches_plaintext(self):
        """Vom gespeicherten Preset (Frontend-IDs) bis in den Klartext."""
        preset = {
            "id": "p-1359",
            "display_config": {
                "active_metrics": [
                    "cloud_avg_pct", "temp_max_c", "sunny_hours_h", "wind_max_kmh",
                ],
            },
        }
        opts = resolve_compare_render_options(preset)
        text = render_comparison_text(_result(), enabled_metrics=opts.enabled_metrics)
        assert _text_labels(text) == ["Wolken", "Temp max", "Sonne", "Wind"], (
            "Die im Vergleich gespeicherte Reihenfolge muss bis in den Klartext "
            f"durchschlagen.\nText:\n{text}"
        )


class TestAC4HtmlOrderRegression:
    """AC-4 (HTML-Anteil) — GRUEN, Regressionsschutz: der HTML-Pfad ordnet seit
    #1335 Scheibe 1 bereits korrekt und muss das bleiben."""

    def test_html_order_follows_enabled_metrics(self):
        for order in (ORDER_A, ORDER_B):
            labels = _html_labels(
                render_compare_html(_result(), enabled_metrics=list(order))
            )
            assert labels == ["Amtliche Warnungen"] + [_HTML_LABEL[m] for m in order], (
                f"HTML-Reihenfolge fuer {order} war {labels}."
            )


class TestAC5TelegramFollowsMetricOrder:
    """AC-5 — RED: `_channel_metric_cells` (comparison.py:349-367) iteriert ueber
    die feste Tupel-Konstante `_CHANNEL_METRICS` und prueft nur Mitgliedschaft."""

    def test_telegram_order_follows_enabled_metrics_order_a(self):
        msg = render_compare_telegram(_result(), enabled_metrics=list(ORDER_A))
        assert _telegram_labels(msg) == [_TELEGRAM_LABEL[m] for m in ORDER_A], (
            f"Telegram muss der uebergebenen Reihenfolge folgen.\nNachricht:\n{msg}"
        )

    def test_telegram_order_flips_with_reversed_selection(self):
        msg_a = render_compare_telegram(_result(), enabled_metrics=list(ORDER_A))
        msg_b = render_compare_telegram(_result(), enabled_metrics=list(ORDER_B))
        labels_a, labels_b = _telegram_labels(msg_a), _telegram_labels(msg_b)
        assert labels_a != labels_b, (
            "Dieselbe Metrik-MENGE in zwei Reihenfolgen muss zwei verschiedene "
            f"Telegram-Zellfolgen ergeben, ergab aber beide Male {labels_a}."
        )
        assert labels_b == [_TELEGRAM_LABEL[m] for m in ORDER_B], (
            f"Erwartet {[_TELEGRAM_LABEL[m] for m in ORDER_B]}, war {labels_b}.\n"
            f"Nachricht:\n{msg_b}"
        )

    def test_telegram_order_matches_plaintext_order(self):
        """AC-5 wortwoertlich: dieselbe Reihenfolge wie in der E-Mail."""
        result = _result()
        text_labels = _text_labels(
            render_comparison_text(result, enabled_metrics=list(ORDER_B))
        )
        tg_labels = _telegram_labels(
            render_compare_telegram(result, enabled_metrics=list(ORDER_B))
        )
        # Vergleich ueber die Metrik-IDs, weil Mail- und Telegram-Labels
        # unterschiedlich kurz sind ("Temp max" vs. "Temp").
        assert [_TEXT_LABEL[m] for m in ORDER_B] == text_labels
        assert [_TELEGRAM_LABEL[m] for m in ORDER_B] == tg_labels


class TestAC10SmsShowsTopTwoMetricsOfUserOrder:
    """AC-10 — RED: die SMS hat Platz fuer genau zwei Metriken je Ort
    (`_SMS_METRICS_PER_LOCATION`). Welche zwei das sind, entscheidet heute die
    feste Tupel-Konstante `_CHANNEL_METRICS` (comparison.py:314-321) statt der
    Nutzer-Reihenfolge — `_channel_metric_cells` bricht nach `limit` Zellen ab,
    nachdem es in Konstanten-Reihenfolge iteriert hat.

    PO-Entscheidung 2026-07-24: die Nutzer-Reihenfolge SOLL die SMS
    mitbestimmen (vormals als unbenannter Nebeneffekt in den Known
    Limitations gefuehrt). SMS-Kurz-Labels sind dieselben wie im Telegram-Pfad
    (gemeinsamer Helfer), deshalb `_TELEGRAM_LABEL`."""

    def test_sms_shows_first_two_metrics_of_order_a(self):
        msg = render_compare_sms(_result(), enabled_metrics=list(ORDER_A))
        assert _sms_labels(msg) == [_TELEGRAM_LABEL[m] for m in ORDER_A[:2]], (
            "Die SMS muss die zwei VORDERSTEN Metriken der Nutzer-Reihenfolge "
            f"zeigen.\nSMS:\n{msg}"
        )

    def test_sms_selection_flips_with_reversed_order(self):
        msg_a = render_compare_sms(_result(), enabled_metrics=list(ORDER_A))
        msg_b = render_compare_sms(_result(), enabled_metrics=list(ORDER_B))
        labels_a, labels_b = _sms_labels(msg_a), _sms_labels(msg_b)
        assert labels_a != labels_b, (
            "Dieselbe Metrik-MENGE in zwei Reihenfolgen muss zwei verschiedene "
            f"SMS-Metrikpaare ergeben, ergab aber beide Male {labels_a}."
        )
        assert labels_b == [_TELEGRAM_LABEL[m] for m in ORDER_B[:2]], (
            f"Erwartet {[_TELEGRAM_LABEL[m] for m in ORDER_B[:2]]}, war {labels_b}.\n"
            f"SMS:\n{msg_b}"
        )

    def test_sms_stays_within_budget(self):
        """Begleitschutz: die Reihenfolge-Aenderung darf das 140-Zeichen-Budget
        nicht sprengen (Endgarantie von `render_compare_sms`)."""
        for order in (ORDER_A, ORDER_B, None):
            msg = render_compare_sms(
                _result(), enabled_metrics=None if order is None else list(order)
            )
            assert len(msg) <= 140, f"SMS zu lang ({len(msg)}):\n{msg}"


class TestAC6OfficialAlertsStayFirst:
    """AC-6 (Mail-Anteil) — GRUEN, Regressionsschutz: "Amtliche Warnungen" steht
    unabhaengig von der uebrigen Reihenfolge immer an erster Stelle."""

    def test_html_warn_row_first_for_any_metric_order(self):
        for order in (ORDER_A, ORDER_B):
            labels = _html_labels(
                render_compare_html(_result(_alert()), enabled_metrics=list(order))
            )
            assert labels[0] == "Amtliche Warnungen", (
                f"Warn-Zeile muss erste Zeile sein, Reihenfolge war {labels}."
            )

    def test_html_warn_row_first_even_if_warn_listed_in_the_middle(self):
        order = ["cloud_avg", "warn", "temp_max"]
        labels = _html_labels(
            render_compare_html(_result(_alert()), enabled_metrics=order)
        )
        assert labels == ["Amtliche Warnungen", "Wolken", "Temp max"], (
            f"'warn' mitten in der Auswahl darf die Warn-Zeile nicht verschieben "
            f"oder verdoppeln, Reihenfolge war {labels}."
        )

    def test_plaintext_alert_line_survives_any_metric_order(self):
        for order in (ORDER_A, ORDER_B):
            text = render_comparison_text(_result(_alert()), enabled_metrics=list(order))
            assert "⚠️" in text and "Gewitterwarnung Stufe Orange" in text, (
                f"Warn-Zeile fehlt im Klartext bei Reihenfolge {order}.\nText:\n{text}"
            )
            assert "Amtliche Warnung" not in _text_labels(text), (
                "Die Warn-Zeile darf nicht als sortierbare Metrik-Zeile auftauchen."
            )


class TestAC7LegacyDefaultOrderUnchanged:
    """AC-7 — CHARAKTERISIERUNGSTEST (kein RED-Test!).

    Ein Vergleich OHNE je gespeicherte Metrik-Auswahl (`enabled_metrics=None`)
    muss NACH der Aenderung exakt dieselbe Zeilenfolge liefern wie heute. Die
    Erwartung unten wurde am 2026-07-24 empirisch vom unveraenderten Renderer
    abgenommen und ist bewusst eingefroren — schlaegt sie fehl, hat sich die
    Mail eines Altbestands ungefragt geaendert."""

    FROZEN_PLAIN_ORDER = [
        "Temp max", "Wind", "Temp min", "Böen", "Windrichtung",
        "Gefühlte Temp. min", "Gefühlte Temp. max",
        "Wolken tief", "Wolken mittel", "Wolken hoch",
        "Regen", "Regenwahrscheinlichkeit", "Gewitter", "UV max", "Sicht min",
        "CAPE", "Nullgradgrenze", "Luftfeuchtigkeit Ø", "Taupunkt Ø",
        "Luftdruck Ø", "Niederschlagsart", "Schneefallgrenze",
        "Sonne", "Wolken", "Schneehöhe", "Neuschnee",
    ]
    FROZEN_TELEGRAM_ORDER = ["Temp", "Wind", "Sonne", "Wolken", "Schnee", "Neuschnee"]
    FROZEN_HTML_ORDER = [
        "Amtliche Warnungen", "Temp max", "Wind", "Regen",
        "Regenwahrscheinlichkeit", "Gewitter", "Sonne", "Wolken", "UV max",
        "Sicht min", "Schneehöhe", "Neuschnee", "Temp min", "Böen", "CAPE",
        "Nullgradgrenze", "Windrichtung", "Gefühlte Temp. min",
        "Gefühlte Temp. max", "Wolken tief", "Wolken mittel", "Wolken hoch",
        "Luftfeuchtigkeit Ø", "Taupunkt Ø", "Luftdruck Ø", "Niederschlagsart",
        "Schneefallgrenze",
    ]

    def test_plaintext_default_order_frozen(self):
        text = render_comparison_text(_result(), enabled_metrics=None)
        assert _text_labels(text) == self.FROZEN_PLAIN_ORDER, (
            "Altbestand ohne gespeicherte Auswahl darf seine Zeilenfolge NICHT "
            f"aendern.\nText:\n{text}"
        )

    def test_telegram_default_order_frozen(self):
        msg = render_compare_telegram(_result(), enabled_metrics=None)
        assert _telegram_labels(msg) == self.FROZEN_TELEGRAM_ORDER, (
            f"Telegram-Default-Reihenfolge veraendert.\nNachricht:\n{msg}"
        )

    def test_html_default_order_frozen(self):
        labels = _html_labels(render_compare_html(_result(), enabled_metrics=None))
        assert labels == self.FROZEN_HTML_ORDER, (
            f"HTML-Default-Reihenfolge veraendert: {labels}"
        )

    def test_preset_without_active_metrics_uses_default_order(self):
        """Der Weg, den ein Altbestand tatsaechlich nimmt (kein display_config)."""
        opts = resolve_compare_render_options({"id": "legacy", "display_config": {}})
        assert opts.enabled_metrics is None
        text = render_comparison_text(_result(), enabled_metrics=opts.enabled_metrics)
        assert _text_labels(text) == self.FROZEN_PLAIN_ORDER


class TestAC8ExplicitEmptySelection:
    """AC-8 — bewusste Leerauswahl zeigt keine Uebersichtszeilen.

    Die Spec grenzt AC-8 auf die RENDERER-Ebene ein (PO-Entscheidung
    2026-07-24): `enabled_metrics=[]` darf nicht durch die Altbestands-Regel
    aus AC-7 (`None` = alle Metriken) ueberschrieben werden. Genau das ist der
    Regressionsschutz, den die AC-7-Aenderung braucht.

    Die Preset-Ebene (`display_config.active_metrics: []`) ist als eigener
    Fehler nach **Issue #1366** ausgelagert und NICHT Teil dieser Scheibe —
    s. `test_empty_active_metrics_preset_is_flattened_to_none_issue_1366`."""

    def test_renderer_empty_list_renders_no_overview_rows(self):
        """GRUEN (Regression): `enabled_metrics=[]` blendet alle Zeilen aus."""
        text = render_comparison_text(_result(), enabled_metrics=[])
        assert _text_labels(text) == [], (
            f"Leerauswahl darf keine Uebersichtszeile zeigen.\nText:\n{text}"
        )
        html_labels = _html_labels(render_compare_html(_result(), enabled_metrics=[]))
        assert html_labels == ["Amtliche Warnungen"], (
            f"HTML darf bei Leerauswahl nur die Warn-Zeile zeigen: {html_labels}"
        )
        msg = render_compare_telegram(_result(), enabled_metrics=[])
        assert _telegram_labels(msg) == [], f"Telegram-Zellen bei Leerauswahl:\n{msg}"

    @pytest.mark.xfail(
        strict=True,
        reason="Issue #1366: resolve_enabled_metrics([]) verflacht die bewusste "
               "Leerauswahl zu None (= alle Metriken). Ausserhalb dieser Scheibe.",
    )
    def test_empty_active_metrics_preset_is_flattened_to_none_issue_1366(self):
        """Dokumentierter Ist-Zustand der PRESET-Ebene, bewusst `xfail(strict)`.

        `resolve_enabled_metrics` (compare_metric_ids.py) gibt bei einem leeren
        `active_metrics` ``None`` zurueck — die bewusste Leerauswahl des Nutzers
        kippt damit in die Altbestands-Regel aus AC-7 und die Mail zeigt ALLE
        Metriken. Das ist ein eigenstaendiger Fehler (**Issue #1366**) und wird
        in dieser Scheibe NICHT repariert.

        Warum `xfail(strict=True)` und kein `skip`/keine Loeschung: der Fund
        bleibt als ausfuehrbarer Nachweis erhalten, und sobald #1366 behoben
        ist, schlaegt der Lauf mit XPASS fehl und erzwingt das Entfernen des
        Markers — ein `skip` waere still und der Nachweis ginge verloren."""
        opts = resolve_compare_render_options({
            "id": "p-empty", "display_config": {"active_metrics": []},
        })
        text = render_comparison_text(_result(), enabled_metrics=opts.enabled_metrics)
        assert _text_labels(text) == [], (
            "Bewusste Leerauswahl darf nicht durch die Altbestands-Regel (AC-7) "
            f"ueberschrieben werden.\nText:\n{text}"
        )
