"""Ortsvergleich: eine Quelle fuer die Standard-Metrik-Reihenfolge (Issue #1356).

SPEC: docs/specs/modules/compare_metric_default_order_ssot.md
(Epic #2259, Scheibe S5 von Epic #1372)

Reine Renderer-/Dienst-Aufrufe mit fest gebauten Objekten: kein Netz, kein
Mock/patch. Test-Sinks sind echte Funktionen (deterministische Transport-Naht
des Produktivcodes), keine Mocks.

AC-Zuordnung (RED = schlaegt vor der Umsetzung fehl):
- AC-1: Klartext-Reihenfolge == HTML-Reihenfolge bei None        -> RED
- AC-2: Schluesselfolge _PLAIN_ROWS == CV2_METRICS (ohne warn)    -> RED
- AC-3: Sortier-Hilfe wirft mit Schluesselnamen                   -> RED
- AC-7: Sink mit plain_body / **kw erhaelt den Klartext           -> RED
- AC-8: Positions-Sink bleibt unveraendert                        -> GRUEN (Regression)
- AC-9: Amtswarn-Sinks bleiben bei subject/body                   -> GRUEN (Regression)
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.config import Settings
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import CV2_METRICS, render_compare_html
from services.notification_service import NotificationService
from tests.helpers.compare_order import (
    html_uebersicht_labels, klartext_uebersicht_labels,
)
from tests.unit.test_compare_metric_order import _result


# ---------------------------------------------------------------------------
# AC-1: Ende-zu-Ende — Klartext folgt der HTML-Reihenfolge bei enabled_metrics=None
# ---------------------------------------------------------------------------


def test_ac1_klartext_folgt_html_reihenfolge_bei_standard():
    """GIVEN Ortsvergleich ohne gespeicherte Auswahl, 3 Orte, alle Metriken
    WHEN HTML und Klartext gerendert werden
    THEN stehen die Uebersichts-Labels im Klartext in derselben Reihenfolge."""
    ergebnis = _result()
    html = render_compare_html(ergebnis, enabled_metrics=None)
    text = render_comparison_text(ergebnis, enabled_metrics=None)

    html_labels = html_uebersicht_labels(html)
    text_labels = klartext_uebersicht_labels(text)

    assert len(html_labels) >= 20, f"Vakuum-Schutz: nur {len(html_labels)} HTML-Zeilen"
    assert text_labels == html_labels, (
        "Klartext-Standardreihenfolge weicht von HTML ab.\n"
        f"HTML:     {html_labels}\nKlartext: {text_labels}"
    )


# ---------------------------------------------------------------------------
# AC-2: Waechter ueber die Schluesselfolgen beider Konstanten
# ---------------------------------------------------------------------------


def test_ac2_plain_rows_schluesselfolge_gleich_cv2_ohne_warn():
    from output.renderers.comparison import _PLAIN_ROWS

    plain = [row[0] for row in _PLAIN_ROWS]
    cv2 = [m["key"] for m in CV2_METRICS if m["key"] != "warn"]

    assert len(cv2) >= 20, f"Vakuum-Schutz: nur {len(cv2)} CV2-Schluessel"
    assert plain == cv2, (
        "_PLAIN_ROWS und CV2_METRICS fuehren verschiedene Folgen.\n"
        f"nur in Plain: {[k for k in plain if k not in cv2]}\n"
        f"nur in CV2:   {[k for k in cv2 if k not in plain]}\n"
        f"Plain: {plain}\nCV2:   {cv2}"
    )


# ---------------------------------------------------------------------------
# AC-3: fail-fast bei Schluessel ausserhalb von CV2_METRICS
# ---------------------------------------------------------------------------


def test_ac3_sortierung_nennt_unbekannten_schluessel():
    """GIVEN eine Plain-Zeile mit Schluessel, der nicht in CV2_METRICS steht
    WHEN die Sortier-Hilfe laeuft THEN klare Fehlermeldung mit Schluessel."""
    from output.renderers import comparison

    rows = tuple(comparison._PLAIN_ROWS) + (
        ("erfundene_metrik_xyz", "vergleich.zeile.erfunden", lambda v: str(v)),
    )
    with pytest.raises((ValueError, KeyError)) as exc:
        comparison._sort_by_cv2_order(rows)
    assert "erfundene_metrik_xyz" in str(exc.value)


def test_ac3_sortierung_nennt_fehlenden_schluessel():
    """GIVEN CV2_METRICS kennt einen Schluessel, den die Plain-Zeilen nicht haben
    THEN bricht die Sortierung ebenfalls mit dem Schluesselnamen ab."""
    from output.renderers import comparison

    rows = tuple(r for r in comparison._PLAIN_ROWS if r[0] != "humidity_avg")
    with pytest.raises((ValueError, KeyError)) as exc:
        comparison._sort_by_cv2_order(rows)
    assert "humidity_avg" in str(exc.value)


# ---------------------------------------------------------------------------
# AC-7 / AC-8 / AC-9: Klartext am mail_sink (C3-75)
# ---------------------------------------------------------------------------

_KLARTEXT = "Innsbruck\nTemperatur Maximum: 20 °C\nWind: 15 km/h"


def _dienst() -> NotificationService:
    return NotificationService(Settings(_env_file=None), "ssot-1356-nutzer")


def _sende(mail_sink):
    return _dienst().send_compare_report(
        subject="Wetter-Vergleich: SSOT (03.11.2026)",
        html_body="<p>Innsbruck</p>",
        text_body=_KLARTEXT,
        telegram_text="Innsbruck",
        sms_text="Innsbruck",
        recipients=["gregor-test@henemm.com"],
        effective_channels={"email"},
        mail_sink=mail_sink,
    )


def test_ac7_sink_mit_kwargs_erhaelt_plain_body():
    aufrufe: list[dict] = []
    ergebnis = _sende(lambda **kw: aufrufe.append(kw))

    assert "email" in ergebnis.sent_channels
    assert len(aufrufe) == 1
    assert aufrufe[0].get("subject") == "Wetter-Vergleich: SSOT (03.11.2026)"
    assert aufrufe[0].get("body") == "<p>Innsbruck</p>"
    assert aufrufe[0].get("plain_body") == _KLARTEXT


def test_ac7_sink_mit_explizitem_plain_body_parameter():
    aufrufe: list[tuple] = []

    def sink(subject, body, plain_body):
        aufrufe.append((subject, body, plain_body))

    _sende(sink)
    assert aufrufe == [
        ("Wetter-Vergleich: SSOT (03.11.2026)", "<p>Innsbruck</p>", _KLARTEXT)
    ]


def test_ac7_klartext_reihenfolge_am_sink_gleich_html_reihenfolge():
    """AC-1 am Sink statt am Echt-Pfad: der Klartext, der den Sink erreicht,
    folgt der HTML-Reihenfolge."""
    ergebnis = _result()
    html = render_compare_html(ergebnis, enabled_metrics=None)
    text = render_comparison_text(ergebnis, enabled_metrics=None)
    erhalten: dict = {}
    _dienst().send_compare_report(
        subject="s", html_body=html, text_body=text, telegram_text="t",
        sms_text="s", recipients=["gregor-test@henemm.com"],
        effective_channels={"email"},
        mail_sink=lambda **kw: erhalten.update(kw),
    )
    assert erhalten.get("plain_body") is not None, "Klartext erreicht den Sink nicht"
    assert klartext_uebersicht_labels(erhalten["plain_body"]) == \
        html_uebersicht_labels(erhalten["body"])


def test_ac8_positions_sink_ohne_plain_body_bleibt_unveraendert():
    aufrufe: list[tuple] = []
    ergebnis = _sende(lambda subject, body: aufrufe.append((subject, body)))

    assert "email" in ergebnis.sent_channels
    assert aufrufe == [("Wetter-Vergleich: SSOT (03.11.2026)", "<p>Innsbruck</p>")]


def test_ac8_sink_mit_nur_subject_und_body_keywords():
    """Auch ein Sink mit exakt den Parametern subject/body (Keyword-Aufruf)
    darf kein TypeError ausloesen."""
    aufrufe: list[dict] = []

    def sink(*, subject, body):
        aufrufe.append({"subject": subject, "body": body})

    ergebnis = _sende(sink)
    assert "email" in ergebnis.sent_channels
    assert list(aufrufe[0]) == ["subject", "body"]
