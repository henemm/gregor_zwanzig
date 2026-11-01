"""TDD RED — Issue #2286 AC-11: der Trip-Guard ohne SMTP warnt, statt still `(0, 0)` zu liefern.

SPEC: docs/specs/modules/fix_2286_compare_betrieb_health.md (Implementierungsdetail 8, AC-11)

Bewusst eigene Kern-Datei statt Ergaenzung von `test_dispatch_orchestrator.py`:
jene Datei traegt modulweit `pytestmark = pytest.mark.live`, und
`pyproject.toml` waehlt `live` per `addopts` ab -- ein dort ergaenzter Test
liefe in CI nie und koennte AC-11 nicht bewachen. Die hier geprueften Pfade
brauchen weder Netz noch Live-Dienste.

Soll:
  * Trip (`smtp_guard=True`): ohne vollstaendige SMTP-Konfiguration weiterhin
    `(0, 0)` (kein Fehler-Zaehler -- fehlendes SMTP ist ein Deploy-Fehler, den
    `/api/health` und `prod_selftest` fangen), ABER ein WARNING-Log, das SMTP
    nennt.
  * Compare (`smtp_guard=False`): unveraendert ohne globalen Guard -- ein
    faelliger, scheiternder Vergleich zaehlt als `failed`.

Kein Mock: echte Settings-Instanz (per `model_copy` SMTP-los, wie der
F002-Test in test_dispatch_orchestrator.py), echter Logger, echter isolierter
Daten-Root (autouse `_isolate_data_root`).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.config import Settings
from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.compare_slot_time import utc_moment


def _settings_ohne_smtp(user_id: str) -> Settings:
    settings = Settings().with_user_profile(user_id).model_copy(update={
        "mail_to": None, "smtp_host": None, "smtp_user": None, "smtp_pass": None,
    })
    assert settings.can_send_email() is False, "Praemisse: SMTP muss fehlen"
    return settings


def test_trip_guard_without_smtp_returns_zero_and_warns(caplog):
    """Given der Trip-Versand laeuft ohne SMTP-Konfiguration / When der
    Trip-Guard in `run_briefing_dispatch("route", ...)` greift / Then bleibt
    das Ergebnis `(0, 0)` UND es steht ein WARNING im Log, das SMTP nennt.

    RED: heute liefert der Guard still `(0, 0)` ohne jedes Log."""
    from services.dispatch_orchestrator import run_briefing_dispatch

    user_id = f"tdd-2286-ac11-{uuid.uuid4().hex[:8]}"
    caplog.set_level(logging.WARNING)

    result = run_briefing_dispatch(
        "route", user_id, datetime.now(timezone.utc), settings=_settings_ohne_smtp(user_id),
    )

    assert result == (0, 0), f"AC-11: der Guard liefert weiterhin (0, 0), kam {result!r}"
    smtp_warnungen = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "smtp" in r.getMessage().lower()
    ]
    assert smtp_warnungen, (
        "AC-11: der Trip-Guard muss bei fehlendem SMTP ein WARNING-Log "
        f"schreiben, das SMTP nennt; Log war: {[r.getMessage() for r in caplog.records]!r}"
    )


def test_compare_has_no_global_guard_and_counts_failed():
    """AC-11 Gegenrichtung (gruener Waechter): der Vergleichs-Versand bleibt
    OHNE globalen SMTP-Guard -- ein faelliger Vergleich wird auch ohne SMTP
    versucht, sein Scheitern zaehlt pro Vergleich als `failed` (`(0, 1)`).
    Ein (versehentlich) eingebauter Guard lieferte `(0, 0)`.

    Issue #1777 (AC-11): ohne JEDEN wirksamen Kanal endet der Versuch als
    neutrales ``no_channels``. Der Vergleich bekommt deshalb Telegram als
    wirksamen Kanal (Preset-Opt-in + Dummy-Bot-Konfiguration), waehrend SMTP
    weiter fehlt -- so scheitert er an der gemeinten Ursache, dem nicht
    aufloesbaren Ort, und das vor jedem Netzkontakt."""
    from app.loader import get_data_dir, get_data_root
    from services.dispatch_orchestrator import run_briefing_dispatch

    user_id = f"tdd-2286-ac11c-{uuid.uuid4().hex[:8]}"
    user_dir = get_data_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    # Kein aufloesbarer Ort -> Zone UTC (Rueckfall), Versand scheitert vor
    # jedem Netzkontakt an `order_locations_by_ids` (ValueError -> failed).
    write_compare_briefings(user_dir, [{
        "id": "cp-ohne-ort", "name": "Ohne Ort", "location_ids": ["loc-fehlt"],
        "schedule": "daily", "profil": "ALLGEMEIN", "morning_time": "07:00:00",
        "created_at": "2026-01-01T00:00:00Z", "send_telegram": True,
    }])
    now_utc = utc_moment(datetime.now(timezone.utc).date(), 7)
    settings = _settings_ohne_smtp(user_id).model_copy(update={
        "telegram_bot_token": "dummy-token", "telegram_chat_id": "1",
    })
    assert settings.can_send_email() is False, "Praemisse: SMTP muss fehlen"
    assert settings.can_send_telegram() is True, "Praemisse: Telegram wirksam"

    result = run_briefing_dispatch(
        "vergleich", user_id, now_utc, data_root=str(get_data_root()),
        settings=settings,
    )

    assert result == (0, 1), (
        "AC-11: Compare zaehlt den gescheiterten Vergleich auch ohne SMTP als "
        f"failed (kein globaler Guard), kam {result!r}"
    )
