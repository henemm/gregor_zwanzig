"""Ortsvergleich: eine Quelle fuer die Standard-Metrik-Reihenfolge (Issue #1356).

SPEC: docs/specs/modules/compare_metric_default_order_ssot.md
(Epic #2259, Scheibe S5 von Epic #1372)

Reine Renderer-/Dienst-Aufrufe mit fest gebauten Objekten: kein Netz, kein
Mock/patch. Test-Sinks sind echte Funktionen (deterministische Transport-Naht
des Produktivcodes), keine Mocks.

AC-Zuordnung (RED = schlaegt vor der Umsetzung fehl):
- AC-1: Klartext-Reihenfolge == HTML-Reihenfolge bei None        -> RED
- AC-2: Schluesselfolge _PLAIN_ROWS == CV2_METRICS (ohne warn)    -> RED
- AC-3: Format-Pruefung (#2991 _pruefe_plain_fmt) nennt Schluessel -> RED
- AC-7: Sink mit plain_body / **kw erhaelt den Klartext           -> RED
- AC-8: Positions-Sink bleibt unveraendert                        -> GRUEN (Regression)
- AC-9: Amtswarn-Sinks bleiben bei subject/body                   -> GRUEN (Regression)
"""
from __future__ import annotations
from tests.helpers.ampel_allgemein import PRESET_ALLGEMEIN


import pytest

from app.config import Settings
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import CV2_ZEILEN as CV2_METRICS, render_compare_html
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
    html = render_compare_html(ergebnis, enabled_metrics=None, preset=PRESET_ALLGEMEIN)
    text = render_comparison_text(ergebnis, enabled_metrics=None, preset=None)

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
    """GIVEN eine Klartext-Format-Zuordnung mit Schluessel, der nicht in
    CV2_METRICS steht WHEN die Import-Pruefung laeuft THEN klare Fehlermeldung
    mit Schluessel (#2991: ersetzt das fail-fast von ``_sort_by_cv2_order``)."""
    from output.renderers import comparison

    fmt = {**comparison._PLAIN_FMT, "erfundene_metrik_xyz": lambda v: str(v)}
    with pytest.raises(ValueError) as exc:
        comparison._pruefe_plain_fmt(fmt, CV2_METRICS)
    assert "erfundene_metrik_xyz" in str(exc.value)


def test_ac3_sortierung_nennt_fehlenden_schluessel():
    """GIVEN CV2_METRICS kennt einen Schluessel, den die Format-Zuordnung nicht
    hat THEN bricht die Pruefung ebenfalls mit dem Schluesselnamen ab."""
    from output.renderers import comparison

    fmt = {k: f for k, f in comparison._PLAIN_FMT.items() if k != "humidity_avg"}
    with pytest.raises(ValueError) as exc:
        comparison._pruefe_plain_fmt(fmt, CV2_METRICS)
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
    html = render_compare_html(ergebnis, enabled_metrics=None, preset=PRESET_ALLGEMEIN)
    text = render_comparison_text(ergebnis, enabled_metrics=None, preset=None)
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


@pytest.mark.parametrize("fehler", [ValueError, TypeError])
def test_ac8_signatur_nicht_ermittelbar_ruft_sink_wie_bisher(monkeypatch, fehler):
    """Spec Abschnitt 2: ist die Sink-Signatur nicht ermittelbar
    (``inspect.signature`` wirft ValueError/TypeError), wird konservativ wie
    bisher nur mit ``subject``/``body`` aufgerufen -- auch wenn der Sink
    ``**kw`` annaehme (Adversary-Finding F001)."""
    from services import notification_service

    def _wirft(_obj, *a, **k):
        raise fehler("Signatur nicht ermittelbar")

    monkeypatch.setattr(notification_service.inspect, "signature", _wirft)

    aufrufe: list[dict] = []
    ergebnis = _sende(lambda **kw: aufrufe.append(kw))

    assert "email" in ergebnis.sent_channels
    assert aufrufe == [{
        "subject": "Wetter-Vergleich: SSOT (03.11.2026)",
        "body": "<p>Innsbruck</p>",
    }]


# ---------------------------------------------------------------------------
# AC-4 (abgeloest durch #3047 Runde 7, B-L4): Telegram/SMS/Premium-SMS bei
# enabled_metrics=None folgen der Mail-Tabelle
# ---------------------------------------------------------------------------

# Bis Runde 7 war hier die SMS eingefroren, die bei None die feste Sechserliste
# (_CHANNEL_METRICS: D W SU CT SD NS) zeigte. Tech-Lead-Entscheidung im
# Nachtrag Runde 7 (Spec feat_3047_einstellung_gleich_mail_pruefkatalog.md,
# "Orte nie eingestellt = was die Mail zeigt", ADR-0095): die SMS zeigt
# dieselben Zeilen in derselben Folge wie die Mail (CV2-/Registerfolge) und
# kuerzt vom Listenende (AC-23). Die Kuerzel-Folge ist von Hand notiert.
_SMS_NONE_KUERZEL_FOLGE = ["D", "W", "R", "PR"]


def test_ac4_sms_bei_standard_folgt_mail_tabelle():
    import re

    from output.renderers.comparison import render_compare_sms

    sms = render_compare_sms(_result(), enabled_metrics=None)
    assert len(sms) <= 160, len(sms)
    # #3172 (ADR-0125): Token-Zeile ``O1 D10/20 W? R? ...`` -> Kuerzel.
    from tests.helpers.orte_sms import orte_teile, orte_token

    erster_ort = orte_teile(sms)[0]
    token = orte_token(erster_ort)
    kuerzel = [re.match(r"[A-Z]+", t).group(0) for t in token]
    assert kuerzel[:4] == _SMS_NONE_KUERZEL_FOLGE, sms
    assert "SU" not in kuerzel[:4], f"alte Sechserliste: {sms}"


# ---------------------------------------------------------------------------
# AC-5: nur die Klartext-Zeilenfolge aendert sich, nicht Zeilen/Werte
# ---------------------------------------------------------------------------


def test_ac5_plain_rows_sind_abgeleitete_sicht_der_format_zuordnung():
    """#2991: ``_PLAIN_ROWS`` ist eine abgeleitete Sicht -- Folge aus
    CV2_METRICS, Formatierer aus ``_PLAIN_FMT`` (keine eigene Klartext-Tabelle
    mit eigener Reihenfolge mehr)."""
    from output.renderers import comparison

    cv2 = [m["key"] for m in CV2_METRICS if m["key"] != "warn"]
    assert [r[0] for r in comparison._PLAIN_ROWS] == cv2
    assert all(r[2] is comparison._PLAIN_FMT[r[0]] for r in comparison._PLAIN_ROWS)


def test_ac5_klartext_zeilen_und_werte_mengengleich_bei_umgekehrter_folge():
    """Der Klartext in umgekehrter Auswahlfolge und der Standard-Klartext (None)
    enthalten dieselben Zeilen mit denselben Werten -- nur die Reihenfolge
    differiert."""
    from collections import Counter

    from output.renderers import comparison

    umgekehrt = [row[0] for row in comparison._PLAIN_ROWS][::-1]
    alt = render_comparison_text(_result(), enabled_metrics=umgekehrt, preset=None)
    neu = render_comparison_text(_result(), enabled_metrics=None, preset=None)

    alt_labels = klartext_uebersicht_labels(alt)
    assert len(alt_labels) >= 20, f"Vakuum-Schutz: nur {len(alt_labels)} Zeilen"
    assert Counter(alt.splitlines()) == Counter(neu.splitlines())
    assert alt_labels != klartext_uebersicht_labels(neu), (
        "Gegenprobe: die umgekehrte Folge muss sich von der Standardfolge unterscheiden"
    )
