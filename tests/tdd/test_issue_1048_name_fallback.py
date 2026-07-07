"""TDD — Issue #1048 F005: absturzsicherer Name-Fallback in get_official_alerts_for_location().

SPEC: docs/specs/fast/fix-1048-name-fallback.md

Vor dem Fix nutzte der except-Zweig der Namens-Ermittlung
`repr(source.__class__.__name__)` als Fallback -- ein Attributzugriff, der bei
einer bewusst boesartig manipulierten Quelle (sabotiertes __getattribute__)
selbst werfen kann und damit die Docstring-Garantie "wirft selbst nie"
(AC-3 aus Issue #1034) verletzt. Der Fix ersetzt den Fallback durch einen
statischen String ohne jeden Attributzugriff.

KEINE Mocks (Projektkonvention CLAUDE.md): Die hostile Quelle ist ein echtes
Python-Objekt mit sabotiertem __getattribute__, kein Mock()/patch().
"""
from __future__ import annotations

import logging

import pytest

import services.official_alerts.base as oa_base
from services.official_alerts import (
    OfficialAlert,
    get_official_alerts_for_location,
    register_official_alert_source,
)


class _HostileOfficialAlertSource:
    """Boesartig manipuliertes Objekt (kein Mock): sowohl der Zugriff auf die
    ``name``-Property als auch auf ``__class__`` (fuer den alten Fallback
    ``repr(source.__class__.__name__)``) wirft eine Exception. ``covers()``
    liefert ``True`` und ``fetch()`` wirft ebenfalls, damit der Aufruf im
    fail-soft-Pfad landet und eine Warnung mit dem statischen Fallback-Namen
    geloggt wird."""

    def __getattribute__(self, item):
        if item in ("name", "__class__"):
            raise RuntimeError(f"hostile: Zugriff auf {item!r} sabotiert")
        return object.__getattribute__(self, item)

    @property
    def name(self) -> str:
        raise RuntimeError("hostile: name-Property wirft")

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        raise RuntimeError("hostile: fetch() wirft")


class _IntactOfficialAlertSource:
    """Echte, intakte Test-Quelle (kein Mock), liefert genau einen bekannten
    OfficialAlert."""

    @property
    def name(self) -> str:
        return "test-intact-source"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        return [
            OfficialAlert(
                source="test-intact-source",
                hazard="wind",
                level=2,
                label="Windwarnung Test",
            )
        ]


@pytest.fixture
def clean_registry():
    """Sichert den Zustand von _REGISTERED_SOURCES und stellt ihn nach dem
    Test wieder her (Registry-Isolation, analog Issue-1034-Tests)."""
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        yield
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


class TestIssue1048NameFallback:
    def test_hostile_source_faellt_still_aus_und_intakte_quelle_liefert(
        self, clean_registry, caplog
    ):
        """Given eine registrierte hostile Quelle (name-Property UND
        __class__-Zugriff werfen) NEBEN einer intakten Test-Quelle, When
        get_official_alerts_for_location() aufgerufen wird, Then wirft der
        Aufruf nicht, liefert den Alert der intakten Quelle und loggt eine
        Warnung mit dem statischen Fallback-Namen fuer die hostile Quelle."""
        register_official_alert_source(_HostileOfficialAlertSource())
        register_official_alert_source(_IntactOfficialAlertSource())

        with caplog.at_level(logging.WARNING, logger="services.official_alerts.base"):
            results = get_official_alerts_for_location(43.7102, 7.2620)

        assert len(results) == 1, f"Erwartet genau 1 Alert der intakten Quelle, war {results!r}"
        assert results[0].label == "Windwarnung Test"

        assert any("unbekannte Quelle" in record.getMessage() for record in caplog.records), (
            f"Fallback-Warnung muss den statischen Namen 'unbekannte Quelle' "
            f"enthalten, geloggt wurde: {[r.getMessage() for r in caplog.records]!r}"
        )

    def test_alter_fallback_haette_geworfen(self):
        """Beweis, dass der VOR dem Fix genutzte Fallback
        (repr(source.__class__.__name__)) bei dieser hostile Quelle selbst
        geworfen haette -- nur der statische String rettet."""
        hostile = _HostileOfficialAlertSource()

        with pytest.raises(Exception):
            str(hostile.name)

        with pytest.raises(Exception):
            repr(hostile.__class__.__name__)
