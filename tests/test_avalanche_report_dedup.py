"""Zusammenfuehrung: zwei Skalen, zwei Gefahrenarten (AC-11).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-11 (und Abschnitt 8, Dublettenwahl)
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 5

Echter Pfad `get_official_alerts_with_status` mit zwei registrierten Quellen:
- die echte `AvalancheReportSource` auf aufgezeichneten Bytes,
- eine `RecordedSource`, die die MeteoAlarm-Lawinenwarnung (Typ 9, Awareness 3 von 4) aus der
  aufgezeichneten CAP-Datei `tests/fixtures/meteoalarm/cap_avalanche_plus_heat.xml` ueber die echte
  Eingangsfunktion `_extract_alerts_from_cap` liefert (nur der Gueltigkeitszeitraum wird auf das
  Bulletin-Fenster gelegt, sonst filtert der Zeitfenster-Filter sie weg).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from tests.helpers.avalanche_report_support import (
    P_TIROL_AT_07_25, FakeClock, FixtureTransport, RecordedSource, alerts_with_status, day_file,
    make_source, ok, only_source, parse_alert,
)

UTC = timezone.utc
NOW = datetime(2026, 2, 20, 8, 0, tzinfo=UTC)
_CAP = Path(__file__).resolve().parent / "fixtures" / "meteoalarm" / "cap_avalanche_plus_heat.xml"


def _meteoalarm_lawine(valid_from: datetime, valid_to: datetime):
    from services.official_alerts.meteoalarm import _extract_alerts_from_cap

    lawinen = [a for a in _extract_alerts_from_cap(_CAP.read_text(encoding="utf-8")) if a.hazard == "avalanche"]
    assert lawinen and lawinen[0].level == 3, "Voraussetzung: aufgezeichnete Typ-9-Warnung Awareness 3"
    return replace(lawinen[0], valid_from=valid_from, valid_to=valid_to)


def _quellen(datei_tag: str = "2026-02-20"):
    transport = FixtureTransport({"AT-07": ok(day_file(datei_tag))})
    lagebericht = make_source(transport, FakeClock(NOW))
    meteoalarm = RecordedSource("meteoalarm", [_meteoalarm_lawine(
        datetime(2026, 2, 19, 16, 0, tzinfo=UTC), datetime(2026, 2, 20, 16, 0, tzinfo=UTC))])
    return meteoalarm, lagebericht


def test_ac11_meteoalarm_lawine_und_lagebericht_bleiben_als_zwei_gefahrenarten_erhalten(monkeypatch):
    meteoalarm, lagebericht = _quellen()
    only_source(monkeypatch, meteoalarm, lagebericht)

    alerts, unavailable = alerts_with_status(*P_TIROL_AT_07_25, NOW)

    assert unavailable is False
    nach_gefahr = {a.hazard: a for a in alerts}
    assert sorted(nach_gefahr) == ["avalanche", "avalanche_bulletin"], alerts
    assert nach_gefahr["avalanche"].level == 3 and nach_gefahr["avalanche"].scale == "awareness"
    assert nach_gefahr["avalanche_bulletin"].native_level == 4
    assert nach_gefahr["avalanche_bulletin"].scale == "eaws"


def test_ac11_reihenfolge_der_registrierung_aendert_nichts(monkeypatch):
    meteoalarm, lagebericht = _quellen()
    only_source(monkeypatch, lagebericht, meteoalarm)

    alerts, _ = alerts_with_status(*P_TIROL_AT_07_25, NOW)

    assert sorted(a.hazard for a in alerts) == ["avalanche", "avalanche_bulletin"]


def test_ac11_schwaechere_lagebericht_stufe_verdraengt_die_meteoalarm_warnung_nicht(monkeypatch):
    """Stufe 1 (EAWS) neben Awareness 3: es gibt keinen skalenuebergreifenden Vergleich."""
    transport = FixtureTransport({"AT-02": ok(day_file("2026-03-01", "AT-02"))})
    now = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    lagebericht = make_source(transport, FakeClock(now))
    meteoalarm = RecordedSource("meteoalarm", [_meteoalarm_lawine(
        datetime(2026, 2, 28, 16, 0, tzinfo=UTC), datetime(2026, 3, 1, 16, 0, tzinfo=UTC))])
    only_source(monkeypatch, meteoalarm, lagebericht)

    alerts, _ = alerts_with_status(46.8947, 14.1901, now)       # AT-02-05-02, Stufe 1

    nach_gefahr = {a.hazard: a for a in alerts}
    assert sorted(nach_gefahr) == ["avalanche", "avalanche_bulletin"]
    assert nach_gefahr["avalanche_bulletin"].native_level == 1
    assert nach_gefahr["avalanche"].level == 3


def test_ac11_dublettenwahl_innerhalb_der_gefahrenart_vergleicht_die_originalstufe(monkeypatch):
    """Zwei Tabellenzeilen melden dieselbe Gefahrenart mit gleichem abgeleiteten level 4, aber
    Stufe 4 und Stufe 5. Mutation `native_level` -> `level` in `base.py` laesst die 4 gewinnen
    (Gleichstand, zuerst gesammelt) und macht diesen Test rot."""
    vier = parse_alert("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25", source="avalanche_report:AT-07")
    fuenf = parse_alert("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25",
                        source="avalanche_report:AT-02")
    assert vier.level == fuenf.level == 4 and (vier.native_level, fuenf.native_level) == (4, 5)
    only_source(monkeypatch, RecordedSource("a", [vier]), RecordedSource("b", [fuenf]))

    alerts, _ = alerts_with_status(*P_TIROL_AT_07_25, NOW)

    assert [(a.hazard, a.native_level) for a in alerts] == [("avalanche_bulletin", 5)]


def test_ac11_dublettenwahl_ist_unabhaengig_von_der_sammel_reihenfolge(monkeypatch):
    vier = parse_alert("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25", source="avalanche_report:AT-07")
    fuenf = parse_alert("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25",
                        source="avalanche_report:AT-02")
    only_source(monkeypatch, RecordedSource("b", [fuenf]), RecordedSource("a", [vier]))

    alerts, _ = alerts_with_status(*P_TIROL_AT_07_25, NOW)

    assert [(a.hazard, a.native_level) for a in alerts] == [("avalanche_bulletin", 5)]
