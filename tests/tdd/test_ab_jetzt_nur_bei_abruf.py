"""TDD — Regressionstest zu Adversary-Finding F001 (#2417, Runde 2, CRITICAL).

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md (AC-31)
Befund: docs/artifacts/feature-2417-interaktions-testabdeckung/adversary-dialog.md, F001

Der "ab jetzt"-Clamp aus AC-31 (``TripReportSchedulerService.
_send_trip_report_outcome``, Zweig ``elif on_demand and report_type ==
"morning":``) ist an ``on_demand=True`` gebunden. Dieses Flag setzt
AUSSCHLIESSLICH ``send_on_demand_report()`` -- jeder andere Aufrufer
(regulaerer Cron-Versand ``send_reports``/``send_due_reports``, Catchup-
Nachlieferung ``_process_pending_markers``, Test-Versand-Knopf
``send_test_report``) laesst ``on_demand`` auf seinem Default ``False``.

Dieser Test ruft ``_send_trip_report_outcome`` GENAUSO auf, wie es
``_dispatch_due_item``/der Scheduler/der Catchup-Pfad tun (``on_demand=False``,
Default) -- mit einer auf 15:00 Ortszeit eingefrorenen Uhr mitten am Tag.
Zusicherung: der volle Tag ab der geplanten Etappen-Startstunde bleibt im
TATSAECHLICH gesendeten Payload erhalten, inklusive der bereits vergangenen
Vormittagsstunden. Der Clamp darf NUR beim On-Demand-Abruf greifen (s.
``test_ac31_heute_telegram_normalstil_zeigt_keine_vergangenen_stunden`` in
``test_abruf_jede_metrik_e2e.py`` fuer den positiven Gegenfall).
"""
from __future__ import annotations

from freezegun import freeze_time

from services.trip_report_scheduler import TripReportSchedulerService
from tests.tdd._befehl_e2e_fixtures import (
    install_transport_fakes,
    lege_lage_an,
    user_ids,
)
from tests.tdd.test_abruf_jede_metrik_e2e import (
    FROZEN_UHR,
    TEMP_FRUEH_C,
    TEMP_SPAET_C,
    _email_text,
    _fixture_dir_mit_ab_jetzt_werten,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden


def test_geplanter_morgen_report_klemmt_nicht_auf_ab_jetzt(monkeypatch, user_ids, tmp_path):
    """F001: ``on_demand=False`` (regulaerer Scheduler-/Catchup-Pfad) darf den
    AC-31-Clamp NICHT anwenden -- der Vormittag muss im gesendeten Payload
    des geplanten Morgen-Reports erhalten bleiben, auch bei einer mitten am
    Tag eingefrorenen Uhr."""
    recorder = install_transport_fakes(monkeypatch)
    fixture_dir = _fixture_dir_mit_ab_jetzt_werten(
        tmp_path, frueh={"t2m_c": TEMP_FRUEH_C}, spaet={"t2m_c": TEMP_SPAET_C},
    )
    with freeze_time(FROZEN_UHR):
        nutzer = lege_lage_an(user_ids, "L2")
        monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(fixture_dir))
        # Kein explizites `settings=` -- wie jeder reale Aufrufer
        # (`_trigger_on_demand`, Scheduler-/Catchup-Dispatch) loest der
        # Konstruktor die Empfaenger-Adresse ueber `Settings().
        # with_user_profile(user_id)` auf `nutzer.mail_to` auf.
        service = TripReportSchedulerService(user_id=nutzer.user_id)
        outcome = service._send_trip_report_outcome(nutzer.trip, "morning", on_demand=False)

    assert outcome == "sent", f"Geplanter Morgen-Report wurde nicht gesendet: {outcome!r}"
    recorder.pruefe_keine_unbekannten_aufrufe()
    eintraege = [e for e in recorder.emails if nutzer.mail_to in e["to"]]
    assert eintraege, f"Keine Morgen-Report-Mail an {nutzer.mail_to} gesendet."
    text = "\n".join(_email_text(e["raw"]) for e in eintraege)
    assert str(TEMP_FRUEH_C) in text, (
        f"Der Vormittagswert {TEMP_FRUEH_C!r} fehlt im geplanten Morgen-Report -- "
        f"der On-Demand-Clamp (AC-31) greift faelschlich auch bei on_demand=False: {text!r}"
    )
    assert str(TEMP_SPAET_C) in text, (
        f"Der Nachmittagswert {TEMP_SPAET_C!r} fehlt im geplanten Morgen-Report: {text!r}"
    )
