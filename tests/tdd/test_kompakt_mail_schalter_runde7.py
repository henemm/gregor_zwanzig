"""Kompakt-Mail (Trip): Warnungen zuerst, Schalter passend zur Editor-Sperre.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(Nachtrag Runde 7, AC-25). Befund B-TM1 (amtliche Warnungen zuerst, WV6).
B-P1/B-P2 (Kompakt ignoriert ``show_stage_stats``/``show_outlook``) sind
KEIN Fehler: PO-Entscheidung #722 (docs/specs/modules/
issue_722_email_compact_format.md); hier wird gesichert, dass Mail und
Editor-Sperre zusammenpassen.

Echter Weg: rohes Trip-JSON -> ``load_trip`` -> ``NotificationService.
send_trip_report`` -> Transport-Mitschrift (``render_trip_mit_ausblick``).
Einzige Naht ist der Transport. Das Soll steht hier als feste Zeichenkette
(Nutzersicht), nicht aus einem Produkt-Resolver. Grundauswahl in einer Folge
ungleich der Katalogfolge. Zwei Nutzer in EINER Mitschrift pruefen, dass das
Format beim richtigen Nutzer wirkt.

Kein ``Mock()``/``patch()``/``MagicMock``.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
    mail_teile, render_trip_mit_ausblick, trip_json,
)
from tests.helpers.transport_mitschrift import aufzeichner_installieren

#: Grundauswahl in einer Folge ungleich der Katalogfolge.
FOLGE = ["gust", "precipitation", "temperature", "wind"]

#: Erwartete Nutzertexte je Sprache (ASCII-gefaltet wie im Kompaktformat).
TEXT = {
    "de": {"warn": "== Warnungen ==", "ueberblick": "== Metriken-Ueberblick ==",
           "ausblick": "3-Tages-Ausblick"},
    "en": {"warn": "== Warnings ==", "ueberblick": "== Metrics overview ==",
           "ausblick": "3-day outlook"},
}

def _warnung():
    from services.official_alerts.models import OfficialAlert
    return OfficialAlert(
        source="meteofrance_vigilance", hazard="thunderstorm", level=3,
        label="Gewitter", region_label="Pruefregion Runde7",
        valid_from=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 7, 20, 20, 0, tzinfo=timezone.utc),
    )


def _kompakt(monkeypatch, rc: dict | None = None, **kw) -> str:
    data = trip_json(FOLGE, report_config={"email_format": "compact", **(rc or {})})
    m, _trip, _uid = render_trip_mit_ausblick(monkeypatch, data, **kw)
    html, text = mail_teile(m)
    assert html is None, "Vorbedingung: Kompaktformat (nur Text)"
    return text


# ---------------------------------------------------------------------------
# B-TM1 / WV6: amtliche Warnungen stehen an erster Stelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_kompakt_amtliche_warnung_vor_jedem_inhaltsblock(monkeypatch, report_type, lang):
    text = _kompakt(monkeypatch, report_type=report_type, language=lang,
                    official_alerts=[_warnung()])
    zeilen = text.splitlines()
    t = TEXT[lang]
    assert t["warn"] in zeilen, f"Warnblock fehlt im Kompaktformat:\n{text}"
    assert t["ueberblick"] in zeilen, f"Vorbedingung: Ueberblick vorhanden:\n{text}"
    w = zeilen.index(t["warn"])
    bloecke = [i for i, z in enumerate(zeilen) if z.startswith("== ")]
    assert bloecke[0] == w, (
        f"{report_type}/{lang}: erster Block ist {zeilen[bloecke[0]]!r} (Zeile "
        f"{bloecke[0]}), die Warnung steht erst in Zeile {w}; WV6: immer zuerst")
    assert w < zeilen.index(t["ueberblick"])
    assert zeilen[w + 1].startswith("  ! "), zeilen[w:w + 3]


# ---------------------------------------------------------------------------
# PO-Entscheidung #722: Kompakt ignoriert die Baustein-Schalter
# ---------------------------------------------------------------------------
# Der Editor sperrt im Kompakt-Modus die drei Schalter ``show_outlook``,
# ``show_stage_stats``, ``show_yesterday_comparison`` und sagt „fix
# Metriken-Ueberblick + Ausblick" (``layout.mail_inhalt.kompakt_hinweis``;
# Sperre geprueft in frontend/.../shared/__tests__/mail_inhalt_card.test.ts
# AC-1). Die Mail muss dazu passen: gleiche Ausgabe, egal wie die gesperrten
# Schalter gespeichert sind, und Ueberblick + Ausblick immer enthalten.

SCHALTER = ("show_outlook", "show_stage_stats", "show_yesterday_comparison")


def _ohne_zeitstempel(text: str) -> str:
    return "\n".join(z for z in text.splitlines() if not z.startswith("Generated:"))


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_kompakt_gesperrte_schalter_aendern_die_mail_nicht(monkeypatch, report_type, lang):
    an = _kompakt(monkeypatch, {k: True for k in SCHALTER},
                  report_type=report_type, language=lang)
    aus = _kompakt(monkeypatch, {k: False for k in SCHALTER},
                   report_type=report_type, language=lang)
    assert _ohne_zeitstempel(an) == _ohne_zeitstempel(aus), (
        "Kompakt: gesperrte Schalter veraendern die Mail (Editor-Sperre luegt)")
    t = TEXT[lang]
    assert t["ueberblick"] in aus and t["ausblick"] in aus, (
        f"Kompakt-Hinweis verspricht Ueberblick + Ausblick:\n{aus}")


def test_zwei_nutzer_kompakt_und_ausfuehrlich(monkeypatch):
    """Gleiche Schalter (Ausblick aus), Nutzer A Kompakt, Nutzer B
    Ausfuehrlich: nur in der ausfuehrlichen Mail wirkt der Schalter."""
    mitschrift = aufzeichner_installieren(monkeypatch)
    kompakt = trip_json(FOLGE, report_config={"email_format": "compact",
                                              "show_outlook": False})
    voll = trip_json(FOLGE, report_config={"email_format": "full", "show_outlook": False})
    _m, _t, uid_a = render_trip_mit_ausblick(monkeypatch, kompakt, mitschrift=mitschrift)
    _m, _t, uid_b = render_trip_mit_ausblick(monkeypatch, voll, mitschrift=mitschrift)
    assert uid_a != uid_b and "default" not in (uid_a, uid_b)
    sa, sb = mitschrift.sendungen("email")
    assert sa["empfaenger"] != sb["empfaenger"]
    assert sa["mail_format"] == "compact" and "3-Tages-Ausblick" in sa["body"]
    assert sb["mail_format"] != "compact"
    assert "3-Tages-Ausblick" not in sb["plain_text_body"]
