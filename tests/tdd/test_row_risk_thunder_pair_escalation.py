"""TDD RED — Issue #1927 Wiedereroeffnung, Spec fix_1927_risk_dot_kombi_regel
Revision v1.1, AC-4 (Paar 2 — Gewitter+Wind/Boeen), Verdrahtungs-Nachweis.

Der Adversary-Dialog gegen v1.0 (`docs/artifacts/fix-1927-risk-dot-kombi-regel/
adversary-dialog.md`) fand: der `severities`-Dict, den `_row_risk()`
(`src/output/renderers/email/html.py`) an `escalate_pair_watch()` uebergibt,
enthaelt gar keinen `"thunder"`-Key -- das Gewitter-Paar war deshalb ueber den
echten Aufrufpfad strukturell nie erreichbar, unabhaengig von der zweiten
Luecke (kein eigenstaendiges 'yellow' fuer `ThunderLevel.LOW`, s.
`_thunder_risk_level`, aktuell mappt LOW zusammen mit MED auf 'watch').

Diese zwei Tests beweisen NUR ZUSAMMEN, dass die Eskalation ueber die
Paar-Regel laeuft, nicht ueber einen pauschalen LOW-Hardcode (s. Kommentare
je Test).

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz. Echter
Renderer-Aufruf (`_row_risk`) mit echten Zeilen-Dicts. Kein Dateiinhalt-Check.

SPEC: docs/specs/modules/fix_1927_risk_dot_kombi_regel.md (v1.1) AC-4
KONTEXT: docs/context/fix-1927-risk-dot-kombi-regel.md
"""
from __future__ import annotations

from app.models import ThunderLevel
from src.output.renderers.email.html import _row_risk


def test_thunder_low_alone_no_yellow_partner_becomes_yellow_not_watch():
    """Test A: `ThunderLevel.LOW` und sonst harmlose Werte, KEIN Partner
    (wind/gust) gelb / When `_row_risk()` ausgewertet wird / Then liefert die
    Funktion 'yellow' -- NICHT 'watch'.

    RED-Beweis: `_thunder_risk_level()` mappt `LOW` heute (vor dieser
    Aenderung) zusammen mit `MED` auf 'watch' -- dieser Test zeigt, dass ein
    ALLEINSTEHENDES LOW (kein gelber Partner in der Zeile) heute faelschlich
    'watch' statt der neuen eigenstaendigen Gelb-Stufe liefert. Erst
    zusammen mit `test_thunder_low_with_yellow_gust_partner_becomes_watch`
    (Test B) beweisen beide Tests, dass die Eskalation ueber die Paar-Regel
    laeuft und nicht ueber einen pauschalen LOW->watch-Hardcode: Test A zeigt
    LOW alleine ist NICHT mehr automatisch watch, Test B zeigt LOW+gelber
    Partner IST watch."""
    row = {
        "thunder": ThunderLevel.LOW,
        "wind": 5, "gust": 10, "precip": 0, "pop": 5, "vis": 20000,
    }
    result = _row_risk(row)
    assert result == "yellow", (
        f"_row_risk mit ThunderLevel.LOW und harmlosen Partnern liefert "
        f"{result!r}, erwartet 'yellow' -- alleinstehendes LOW-Gewitter ohne "
        f"gelben Partner eskaliert NICHT auf 'watch' (Spec v1.1 AC-4, "
        f"Regressions-AC)."
    )


def test_thunder_low_with_yellow_gust_partner_becomes_watch():
    """Test B: `ThunderLevel.LOW` UND `gust` auf Katalog-Gelbschwelle (30
    km/h), sonst harmlose Werte / When `_row_risk()` ausgewertet wird / Then
    liefert die Funktion 'watch' (Paar-Eskalation Blitzschlag +
    Boeenfront-Sturzgefahr).

    HINWEIS: dieser Test ALLEIN ist mehrdeutig -- er liefert 'watch' auch mit
    dem heutigen (kaputten) Code, weil `_thunder_risk_level()` `LOW` aktuell
    IMMER auf 'watch' zwingt, unabhaengig vom Partner. Erst in Kombination
    mit Test A (der zeigt, dass LOW alleine NICHT mehr automatisch 'watch'
    ist) beweisen beide Tests zusammen, dass hier tatsaechlich die Paar-Regel
    greift und nicht ein pauschaler LOW-Hardcode. Dieser Test bleibt VOR der
    Implementierung bereits gruen -- das ist beabsichtigt und kein
    RED-Nachweis fuer sich allein."""
    row = {
        "thunder": ThunderLevel.LOW,
        "gust": 30, "wind": 5, "precip": 0, "pop": 5, "vis": 20000,
    }
    result = _row_risk(row)
    assert result == "watch", (
        f"_row_risk mit ThunderLevel.LOW und gust=30 (Katalog-Gelbschwelle) "
        f"liefert {result!r}, erwartet 'watch' (Spec v1.1 AC-4)."
    )
