"""Der Lagebericht verdeckt nie den Ausfall einer anderen Quelle und meldet eigene
Auswertungsfehler sichtbar (#1441, Adversary-Fix-Loop 1: F001, F004).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-4, AC-5, AC-7 (Zustaende)
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 1

F001: "kein aktueller Bericht" (404, abgelaufenes Bulletin, Punkt in keiner Mikroregion) ist
fachlich "nicht zustaendig" -- der Lagebericht darf dann nicht als erfolgreich antwortende Quelle
den Ausfall der Bestandsquellen (GeoSphere, MeteoAlarm) kompensieren. Gemessen ueber den ECHTEN
Registry-Pfad `get_official_alerts_with_status` mit den ECHTEN Bestandsquellen: sie sind im Kern
per Egress-Waechter gesperrt (BLOCKED) und fallen dadurch von selbst aus -- kein Stub.
Nur die registrierte Lagebericht-Quelle wird gegen eine Instanz mit Fixture-Transport getauscht.

F004: Antwort ohne CAAML-Bulletinliste und Auswertungsfehler nach erfolgreichem Abruf sind
"nicht abrufbar"; ein im Schema erlaubtes `no_rating` ist KEIN Fehler.
Fixtures: tests/fixtures/avalanche_report/derived/ (README dort).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.helpers.avalanche_report_support import (
    P_TIROL_AT_07_05, P_ZELL_AM_SEE, FakeClock, FixtureTransport, Reply, alerts_with_status,
    make_source, ok, only_source, raw,
)

UTC = timezone.utc
HEUTE = datetime(2026, 10, 13, 10, 0, tzinfo=UTC)
WINTER = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)


def _echte_registry_mit(monkeypatch, lagebericht=None) -> None:
    """Echte Standard-Registry; die Lagebericht-Quelle wird (falls gegeben) gegen eine
    Instanz mit Fixture-Transport getauscht, sonst ganz entfernt."""
    import services.official_alerts  # noqa: F401  (Registrierung beim Import)
    from services.official_alerts import base

    bestand = [s for s in base._REGISTERED_SOURCES if s.name != "avalanche_report"]
    assert len(bestand) >= 2, "Voraussetzung: echte Bestandsquellen registriert"
    neu = bestand + ([lagebericht] if lagebericht is not None else [])
    monkeypatch.setattr(base, "_REGISTERED_SOURCES", neu)


def _quelle(reply: Reply, now: datetime):
    transport = FixtureTransport({"AT-07": reply})
    return transport, make_source(transport, FakeClock(now))


# ---------------------------------------------------------------- F001
@pytest.mark.parametrize("punkt", [P_TIROL_AT_07_05, P_ZELL_AM_SEE], ids=["tirol", "zell-am-see"])
def test_voraussetzung_bestandsquellen_fallen_im_kern_aus(monkeypatch, punkt):
    """Ohne Lagebericht: die echten Bestandsquellen sind gesperrt -> "nicht abrufbar"."""
    _echte_registry_mit(monkeypatch, None)

    _alerts, unavailable = alerts_with_status(*punkt, HEUTE)

    assert unavailable is True


@pytest.mark.parametrize("fall, reply_name, punkt", [
    ("404", "404", P_TIROL_AT_07_05),
    ("abgelaufen", "2026-05-02_AT-07_de_CAAMLv6.json", P_TIROL_AT_07_05),
    ("keine-mikroregion", "2026-05-02_AT-07_de_CAAMLv6.json", P_ZELL_AM_SEE),
], ids=["404", "abgelaufenes-bulletin", "bbox-ohne-mikroregion"])
def test_kein_aktueller_bericht_verdeckt_den_ausfall_der_bestandsquellen_nicht(
    monkeypatch, fall, reply_name, punkt,
):
    """Mutation M8 (`mark_not_covered()` entfernt) macht alle drei Faelle rot: der Lagebericht
    zaehlte dann als erfolgreich zustaendige Quelle und `unavailable` kippte auf False."""
    reply = Reply(404, b"") if reply_name == "404" else ok(reply_name)
    transport, quelle = _quelle(reply, HEUTE)
    _echte_registry_mit(monkeypatch, quelle)

    alerts, unavailable = alerts_with_status(*punkt, HEUTE)

    assert [a for a in alerts if a.hazard == "avalanche_bulletin"] == []
    assert unavailable is True, f"{fall}: der Ausfall der Bestandsquellen wird verdeckt"
    erwartete_abrufe = 0 if fall == "keine-mikroregion" else 1
    assert transport.served("AT-07") == erwartete_abrufe


def test_gueltiger_bericht_kompensiert_den_ausfall_weiterhin(monkeypatch):
    """Gegenprobe: ein gueltiges Bulletin ist eine echte, erfolgreiche Antwort."""
    transport, quelle = _quelle(ok("2026-03-01_AT-07_de_CAAMLv6.json"), WINTER)
    _echte_registry_mit(monkeypatch, quelle)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_05, WINTER)

    assert [a.native_level for a in alerts if a.hazard == "avalanche_bulletin"] == [3]
    assert unavailable is False


# ---------------------------------------------------------------- F004
def test_antwort_ohne_caaml_bulletinliste_ist_nicht_abrufbar(monkeypatch):
    """Mutation P1 (Parse-Fehler -> leeres Dokument) macht diesen Test rot."""
    transport, quelle = _quelle(Reply(200, raw("derived/defekt/kein_caaml.json")), WINTER)
    only_source(monkeypatch, quelle)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_05, WINTER)

    assert alerts == [] and unavailable is True
    assert transport.served("AT-07") == 1


def test_auswertungsfehler_nach_erfolgreichem_abruf_ist_nicht_abrufbar(monkeypatch):
    """Mutation N2 (`mark_fetch_incomplete()` im except entfernt) macht diesen Test rot."""
    datei = "derived/defekt/2026-03-01_AT-07_de_CAAMLv6_DERIVED_kaputte_endzeit.json"
    transport, quelle = _quelle(Reply(200, raw(datei)), WINTER)
    only_source(monkeypatch, quelle)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_05, WINTER)

    assert alerts == [] and unavailable is True


def test_no_rating_wird_verworfen_ohne_absturz_und_ohne_falsches_nicht_abrufbar(monkeypatch):
    """Mutation P5 (`no_rating` nicht mehr verworfen -> KeyError) macht diesen Test rot."""
    datei = "derived/2026-03-01_AT-07_de_CAAMLv6_DERIVED_no_rating.json"
    transport, quelle = _quelle(Reply(200, raw(datei)), WINTER)
    only_source(monkeypatch, quelle)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_05, WINTER)

    assert unavailable is False
    assert [(a.native_level, a.elevation_value, a.elevation_direction) for a in alerts] == [
        (3, "Waldgrenze", "above")
    ]
