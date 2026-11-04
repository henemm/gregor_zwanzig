"""#1786 — Zonen-Warnung aus first_resolvable_tz() entprellen (je Label und UTC-Tag).

SPEC: docs/specs/modules/fix_1786_zonen_warnung_entprellen.md
Echte Aufrufe mit caplog; Uhr ueber die Naht ``_utc_today`` (keine Mock-Logik).
"""
from __future__ import annotations

import logging
import threading
from datetime import date
from types import SimpleNamespace

import pytest

import src.utils.timezone as tzmod

WARN_TEXT = "Keine aufloesbare Zeitzone"


def _ohne_zone():
    return SimpleNamespace(timezone=None, lat=None, lon=None)


def _mit_zone():
    return SimpleNamespace(timezone="Europe/Berlin", lat=None, lon=None)


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    tzmod.reset_zonen_warnung()
    monkeypatch.setattr(tzmod, "_utc_today", lambda: date(2026, 11, 4))
    yield
    tzmod.reset_zonen_warnung()


def _warnungen(caplog):
    return [r for r in caplog.records if WARN_TEXT in r.getMessage()]


def test_ac1_312_aufrufe_eine_zeile(caplog):
    caplog.set_level(logging.WARNING, logger=tzmod.logger.name)
    for _ in range(312):
        assert tzmod.first_resolvable_tz([_ohne_zone()], "Preset A") == tzmod.UTC
    assert len(_warnungen(caplog)) == 1


def test_ac2_zwei_labels_je_eine_zeile(caplog):
    caplog.set_level(logging.WARNING, logger=tzmod.logger.name)
    for _ in range(5):
        tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")
        tzmod.first_resolvable_tz([_ohne_zone()], "Preset B")
    msgs = [r.getMessage() for r in _warnungen(caplog)]
    assert len(msgs) == 2
    assert any("Preset A" in m for m in msgs) and any("Preset B" in m for m in msgs)


def test_ac3_tageswechsel_warnt_erneut(caplog, monkeypatch):
    caplog.set_level(logging.WARNING, logger=tzmod.logger.name)
    tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")
    tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")
    assert len(_warnungen(caplog)) == 1
    monkeypatch.setattr(tzmod, "_utc_today", lambda: date(2026, 11, 5))
    tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")
    tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")
    assert len(_warnungen(caplog)) == 2


def test_ac4_leeres_label_nicht_entprellt(caplog):
    caplog.set_level(logging.WARNING, logger=tzmod.logger.name)
    for _ in range(4):
        assert tzmod.first_resolvable_tz([_ohne_zone()]) == tzmod.UTC
    assert len(_warnungen(caplog)) == 4


def test_ac5_aufloesbare_zone_unveraendert_ohne_warnung(caplog):
    caplog.set_level(logging.WARNING, logger=tzmod.logger.name)
    tz = tzmod.first_resolvable_tz([None, _ohne_zone(), _mit_zone()], "Preset A")
    assert str(tz) == "Europe/Berlin"
    assert _warnungen(caplog) == []


def test_ac6_parallele_aufrufe_eine_zeile(caplog):
    caplog.set_level(logging.WARNING, logger=tzmod.logger.name)
    barriere = threading.Barrier(16)

    def lauf():
        barriere.wait()
        for _ in range(20):
            tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")

    threads = [threading.Thread(target=lauf) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(_warnungen(caplog)) == 1


def test_ac7_reset_erlaubt_neue_warnung(caplog):
    caplog.set_level(logging.WARNING, logger=tzmod.logger.name)
    tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")
    tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")
    assert len(_warnungen(caplog)) == 1
    tzmod.reset_zonen_warnung()
    tzmod.first_resolvable_tz([_ohne_zone()], "Preset A")
    assert len(_warnungen(caplog)) == 2
