# doc-compliance-test
"""Issue #1986 AC-3: Jede als "begruendet getrennt" gefuehrte Paritaets-Testdatei
traegt in der Kopfzeile den Marker ``PARITAET-BEGRUENDUNG: <Begruendung>``.

Dateiinhalt-Check ist hier erlaubt: das geforderte Verhalten (Begruendung
vorhanden) ist selbst Dokumentation. Neue begruendet getrennte Paritaetstests
muessen in BEGRUENDET_GETRENNT eingetragen werden.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
KOPF_ZEILEN = 25
MARKER = re.compile(r"PARITAET-BEGRUENDUNG:[ \t]*(\S.*)")

BEGRUENDET_GETRENNT = [
    # Kanal gegen Kanal
    "tests/tdd/test_briefing_parity_night_thunder.py",
    "tests/tdd/test_channel_origin_guard_parity.py",
    "tests/tdd/test_regen_ausdehnung_kanalparitaet.py",
    "tests/tdd/test_vorlauf_kanalparitaet.py",
    "tests/tdd/test_alarm_sms_paritaet_amtlicher_zusatz.py",
    "tests/tdd/test_hiking_window_parity.py",
    "tests/tdd/test_etappennummer_status_paritaet.py",
    # Python gegen Go (zwei Prozesse, Fixture ist der Zwang)
    "tests/test_mail_recipient_parity.py",
    "internal/mail/recipient_parity_test.go",
    "tests/unit/test_user_id_pattern_parity.py",
    "tests/unit/test_entity_id_pattern_parity.py",
    "internal/handler/briefing_route_get_lock_etag_test.go",
    # Deutsch gegen Englisch (Kataloge)
    "tests/test_i18n_api_katalog_paritaet.py",
    "tests/test_i18n_inbound_katalog_paritaet.py",
    "tests/unit/test_i18n_katalog_paritaet.py",
    "internal/i18n/katalog_paritaet_test.go",
    "frontend/src/lib/i18n/__tests__/paritaet_de_en.test.ts",
    # Regressionswaechter, Rahmen bereits geteilt
    "frontend/e2e/hub-anlegen-paritaet-flaechen.spec.ts",
    # Go-Waechter, begruendet getrennt
    "internal/store/entity_id_test.go",
    "internal/store/entity_id_upstream_zeichen_test.go",
    "internal/scheduler/forecast_budget_health_test.go",
    "internal/model/trip_schema_drift_test.go",
]


def begruendung(text: str):
    """Liefert die Begruendung aus der Kopfzeile oder None."""
    kopf = "\n".join(text.splitlines()[:KOPF_ZEILEN])
    m = MARKER.search(kopf)
    return m.group(1).strip() if m else None


@pytest.mark.parametrize("rel", BEGRUENDET_GETRENNT)
def test_datei_traegt_marker_mit_begruendung(rel):
    pfad = REPO / rel
    assert pfad.is_file(), f"{rel} fehlt"
    b = begruendung(pfad.read_text(encoding="utf-8"))
    assert b, f"{rel}: Kopfzeile ohne 'PARITAET-BEGRUENDUNG: <Begruendung>'"
    assert len(b) >= 10, f"{rel}: Begruendung zu kurz"


def test_gegenprobe_ohne_marker_wird_erkannt():
    assert begruendung("# nur ein Test\nimport os\n") is None
    assert begruendung("# PARITAET-BEGRUENDUNG:   \nx\n") is None
    assert begruendung("# PARITAET-BEGRUENDUNG: zwei Prozesse\n") == "zwei Prozesse"
