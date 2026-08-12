"""Der Radar-Mail-Waechter muss ALLE drei Ortsformen kennen — und nur die.

Hintergrund (Issue #1744 A1): P-1 des `radar_alert_mail_validator` fragt, ob
die Alarm-Mail ueberhaupt sagt WO. Seine Formen-Aufzaehlung kannte "Etappe N",
"km X-Y" und "Segment", aber NICHT die Ziel-Form "🏁 Ziel" — die einzige
Ortsform, die `format_segment_reference` fuer die letzte Etappe erzeugt. Am
2026-08-12 an der echt zugestellten Mail gemessen: der Waechter beanstandete
eine korrekte, PO-freigegebene Ausgabe (Exit 1, P-1) und haette damit jede
Ziel-Segment-Warnung blockiert — ein faelschlich blockierendes Gate.

Die Erweiterung ist additiv. Damit stellt sich sofort die Gegenfrage, die
dieser Test dauerhaft beantwortet: **behaelt die Pruefung ihre Zaehne?** Eine
Formen-Aufzaehlung, die man bei jedem neuen Format nachzieht, verkommt sonst
zur Attrappe, die alles durchwinkt. Der vierte Fall unten ist deshalb der
wichtigste: eine Mail OHNE jeden Ortsbezug muss weiterhin beanstandet werden.

Die drei Positiv-Faelle laufen ueber den ECHTEN Renderer (`render_email` auf
einer echten `AlertMessage`) und die ECHTE Versand-Pipeline
(`build_mime_message`) — nicht ueber handgeschriebene Wunsch-Strings. Sonst
prueft der Test seine eigene Annahme darueber, wie die Mail aussieht, statt
der Mail. Nur der Negativ-Fall ist konstruiert: eine Ausgabe ohne Ortsbezug
kann der Renderer gar nicht erzeugen, genau deshalb ist sie die Gegenprobe.

Vorbild fuer Aufbau und Modul-Laden: tests/tdd/test_official_alert_mail_validator.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "radar_alert_mail_validator.py"

SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_validator_module():
    if not VALIDATOR_PATH.exists():
        pytest.fail(f"Validator-Datei nicht gefunden: {VALIDATOR_PATH}")
    spec = importlib.util.spec_from_file_location(
        "radar_alert_mail_validator_probe", VALIDATOR_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rendered_radar_mail_plain(segment_id) -> str:
    """Der Plaintext einer echten Radar-Alarm-Mail — dieselbe Fixture-Bauform
    wie `scripts/send_gate_test_mails.py::build_radar_alert_message`, damit die
    Nachweis-Mail des Commit-Gates und dieser Test dasselbe Objekt pruefen."""
    from output.renderers.alert.model import AlertMessage, OnsetEvent
    from output.renderers.alert.render import render_email

    onset = OnsetEvent(
        onset_minutes=25, onset_time="14:30", km_from=0.0, km_to=8.0,
        is_convective=False, intensity_label="Leichter Regen",
        source_label="Radar (DWD)", briefing_context=None,
        segment_id=segment_id,
    )
    msg = AlertMessage(
        trip_short="GATE1241 probe", stand_at="13:05", events=(onset,),
        source="Radar (DWD)", cooldown_display="2 Stunden",
    )
    return render_email(msg)[1]


def _as_radar_mail(plain: str):
    """Verpackt den Text ueber die echte Versand-Pipeline zu der Mail, die der
    Waechter im Postfach vorfindet (Marker-Header `X-GZ-Mail-Type`)."""
    from output.channels.email import build_mime_message

    return build_mime_message(
        subject="[GATE1241 probe] Regen in 25 Min",
        body=plain,
        from_addr="gregor_zwanzig@henemm.com",
        to_header="gregor-test@henemm.com",
        reply_to=None,
        html=False,
        plain_text_body=None,
        mail_type="radar-alert",
    )


@pytest.mark.parametrize("segment_id,erwartete_ortsangabe", [
    ("Ziel", "🏁 Ziel"),   # letzte Etappe — die Form, die P-1 bis #1744 nicht kannte
    ("1", "Segment 1"),    # numerische Etappe
    (None, "km 0–8"),      # Altdaten ohne Kennung -> km-Rueckfall (#1744 AC-7)
])
def test_waechter_akzeptiert_jede_echte_ortsform(segment_id, erwartete_ortsangabe):
    """Alle drei Ortsformen, die der Renderer ueberhaupt erzeugen kann, muessen
    den Waechter passieren — sonst blockiert er korrekte Auslieferungen."""
    plain = _rendered_radar_mail_plain(segment_id)
    assert f"Wo & wann: {erwartete_ortsangabe} · ab 14:30" in plain, (
        f"Renderer erzeugt nicht die erwartete Ortsangabe: {plain[:200]!r}"
    )

    ok, errors = _load_validator_module().validate_message(_as_radar_mail(plain))

    assert ok is True, (
        f"Waechter beanstandet die korrekte Ortsform {erwartete_ortsangabe!r}: {errors}"
    )


def test_waechter_beanstandet_mail_ohne_jeden_ortsbezug():
    """Die Gegenprobe: dieselbe Mail, nur ohne Ortsangabe in der Zeile
    'Wo & wann'. Faellt sie NICHT durch, ist P-1 eine Attrappe und die
    Erweiterung um die Ziel-Form waere eine Aufweichung gewesen."""
    plain = _rendered_radar_mail_plain("Ziel").replace(
        "Wo & wann: 🏁 Ziel · ab 14:30", "Wo & wann: ab 14:30",
    )
    assert "Ziel" not in plain and "Segment" not in plain, (
        "Testaufbau kaputt: der Ortsbezug steckt noch irgendwo im Text"
    )

    ok, errors = _load_validator_module().validate_message(_as_radar_mail(plain))

    assert ok is False, "Mail ohne jeden Ortsbezug wurde durchgewunken — P-1 hat keine Zaehne mehr"
    assert any(e.startswith("P-1:") for e in errors), (
        f"Erwartet eine P-1-Beanstandung, bekommen: {errors}"
    )
