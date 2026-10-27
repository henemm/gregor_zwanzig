"""TDD RED -- Rueckbau der kontingentierten MeteoAlarm-EDR-Klasse (Issue #2266, Epic #2258).

SPEC: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md (AC-1, AC-4)

Verhaltensnachweise fuer die Loeschung -- kein Dateiinhalt-Check am Quelltext:

- AC-1: ``MeteoAlarmSource``, ``meteoalarm_budget`` und ``RateLimitRetryPolicy``
  sind nicht mehr importierbar (``pytest.raises(ImportError)``). Positivkontrolle
  je Test: das umgebende Modul bzw. der geteilte CAP-Mapper bleibt importierbar --
  sonst bestuende der Test auch, wenn versehentlich ALLES geloescht wuerde.
- AC-4: das Python-Egress-Inventar (das importierte ``INVENTORY``-Objekt) kennt
  ``api.meteoalarm.org`` nicht mehr, ``feeds.meteoalarm.org`` bleibt gesperrt
  deklariert. Das Go-Gegenstueck liegt in
  ``internal/egress/inventory_meteoalarm_test.go``.

RED heute: alle drei Importe gelingen noch (``Failed: DID NOT RAISE``), und der
EDR-Host steht noch im Inventar (AssertionError).

Kern-Schicht: ohne Marker, ohne Netz.
"""
from __future__ import annotations

import importlib

import pytest


def test_ac1_edr_klasse_meteoalarmsource_ist_nicht_mehr_importierbar():
    """AC-1: GIVEN der Rueckbau ist abgeschlossen, WHEN ``MeteoAlarmSource``
    importiert werden soll, THEN schlaegt der Import mit ImportError fehl --
    waehrend der geteilte CAP-Mapper im selben Modul erreichbar bleibt."""
    from services.official_alerts.meteoalarm import _group_and_map_info_entries

    assert callable(_group_and_map_info_entries), (
        "Positivkontrolle: der CAP-Mapper traegt den Feed-Weg AT/IT/DE und darf "
        "beim Rueckbau NICHT mitgeloescht werden"
    )
    with pytest.raises(ImportError):
        from services.official_alerts.meteoalarm import MeteoAlarmSource  # noqa: F401


def test_ac1_budget_modul_meteoalarm_budget_ist_nicht_mehr_importierbar():
    """AC-1: GIVEN der Rueckbau ist abgeschlossen, WHEN das Budget-Modul
    importiert werden soll, THEN schlaegt der Import mit ImportError fehl."""
    importlib.import_module("services.official_alerts")  # Positivkontrolle: Paket bleibt
    with pytest.raises(ImportError):
        importlib.import_module("services.official_alerts.meteoalarm_budget")


def test_ac1_retry_policy_ist_aus_warn_egress_nicht_mehr_importierbar():
    """AC-1: GIVEN der Rueckbau ist abgeschlossen, WHEN ``RateLimitRetryPolicy``
    aus ``warn_egress`` importiert werden soll, THEN schlaegt der Import mit
    ImportError fehl -- der Abrufweg ``cached_fetch`` selbst bleibt."""
    from services.official_alerts.warn_egress import cached_fetch

    assert callable(cached_fetch), "Positivkontrolle: cached_fetch traegt den Feed-Abruf"
    with pytest.raises(ImportError):
        from services.official_alerts.warn_egress import RateLimitRetryPolicy  # noqa: F401


def test_ac4_python_egress_inventar_kennt_nur_noch_den_feed_host():
    """AC-4: GIVEN das Python-Egress-Inventar, WHEN es nach MeteoAlarm-Hosts
    befragt wird, THEN ist ``feeds.meteoalarm.org`` weiter als gesperrter Host
    deklariert und ``api.meteoalarm.org`` weder erlaubt noch deklariert."""
    from app.egress_guard import INVENTORY, IsolationKind

    assert INVENTORY.get("feeds.meteoalarm.org") is IsolationKind.BLOCKED, (
        "der kontingentfreie Feed-Host muss fuer Test/Staging gesperrt deklariert "
        f"bleiben, erhalten: {INVENTORY.get('feeds.meteoalarm.org')!r}"
    )
    meteoalarm_hosts = sorted(h for h in INVENTORY if "meteoalarm" in h)
    assert "api.meteoalarm.org" not in INVENTORY, (
        f"der EDR-Host ist zurueckgebaut und darf nicht mehr im Inventar stehen; "
        f"MeteoAlarm-Hosts im Inventar: {meteoalarm_hosts}"
    )
    assert meteoalarm_hosts == ["feeds.meteoalarm.org"], (
        f"einziger MeteoAlarm-Host muss der Feed sein, erhalten: {meteoalarm_hosts}"
    )
