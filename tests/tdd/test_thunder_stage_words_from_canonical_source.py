"""TDD RED — Issue #2010 (Telegram) / #2011 (Briefing-Mail-Ampelfarbe):
Gewitter-Stufenwörter/-Ampelfarbe folgen der kanonischen Quelle
(``src/output/metric_format.py::THUNDER_LABEL_DE`` / ``thunder_ampel_band()``)
statt lokal kopierter Wort-/Zahlenketten.

AC-1 bis AC-3 (#2010, Telegram-Klartext/-Emoji/-Stundendrilldown) und AC-4
(Ableitungsnachweis) messen ``_thunder_fmt``/``_handle_hours_drilldown`` in
``src/services/trip_command_processor.py``. AC-5 bis AC-7 (#2011) messen
``_thunder_risk_level``/``_row_risk`` in
``src/output/renderers/email/html.py``. AC-8/AC-9 (Wächter-Basislinie/
Marker-Positivkontrolle) liegen in
``tests/tdd/test_thunder_scale_local_copy_guard.py``.

Spec: docs/specs/modules/fix_2010_2011_gewitter_stufenwoerter.md
Kontext: docs/context/fix-2010-2011-gewitter-stufenwoerter.md

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.loader import save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from output.metric_format import THUNDER_LABEL_DE, _THUNDER_AMPEL_BAND
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
    _thunder_fmt,
    _thunder_symbols,
    _thunder_words,
)
from src.output.renderers.email.html import _render_html_table, _row_risk, _thunder_risk_level

# ---------------------------------------------------------------------------
# AC-1 / AC-2: _thunder_fmt() -- Klartext- und Emoji-Pfad, alle vier Stufen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "level,expected_word",
    [
        (ThunderLevel.NONE, "kein"),
        (ThunderLevel.LOW, "leicht"),
        (ThunderLevel.MED, "mittel"),
        (ThunderLevel.HIGH, "hoch"),
    ],
)
def test_ac1_thunder_fmt_plain_zeigt_die_vier_korrekten_woerter(level, expected_word):
    """AC-1: Klartext-Pfad (``with_emoji=False``) zeigt fuer jede Stufe genau
    das kanonische Wort -- insbesondere 'mittel' statt 'mäßig' und 'kein'
    statt 'keins'."""
    text = _thunder_fmt(level, with_emoji=False)
    assert text == expected_word, f"{level}: erwartet {expected_word!r}, erhalten {text!r}"
    assert "mäßig" not in text and "keins" not in text


@pytest.mark.parametrize(
    "level,expected_word,expected_emoji",
    [
        (ThunderLevel.NONE, "kein", "⚪"),
        (ThunderLevel.LOW, "leicht", "🟢"),
        (ThunderLevel.MED, "mittel", "🟡"),
        (ThunderLevel.HIGH, "hoch", "🔴"),
    ],
)
def test_ac2_thunder_fmt_emoji_behaelt_symbol_und_korrigiert_wort(level, expected_word, expected_emoji):
    """AC-2: Emoji-Pfad (``with_emoji=True``) behaelt das Kreis-Emoji UND
    zeigt das korrigierte Wort, beide gemeinsam in derselben Zeile.

    Exakter Split statt Teilstring-Suche: 'kein' ist Teilstring von 'keins'
    -- eine reine ``in``-Pruefung wuerde den Bug nicht fangen.
    """
    text = _thunder_fmt(level, with_emoji=True)
    parts = text.split(" ", 1)
    assert len(parts) == 2, f"{level}: erwartet 'EMOJI WORT', erhalten {text!r}"
    assert parts[0] == expected_emoji, f"{level}: Emoji {parts[0]!r}, erwartet {expected_emoji!r}"
    assert parts[1] == expected_word, f"{level}: Wort {parts[1]!r}, erwartet {expected_word!r}"


# ---------------------------------------------------------------------------
# AC-3: Stundendrilldown ist ein unabhaengiger zweiter Pfad
# ---------------------------------------------------------------------------

TODAY = date(2026, 9, 10)
RECEIVED_AT = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
_TRIP_ID = "test-2010-2011-hours-drilldown"
_TRIP_NAME = "Stufenwoerter-Test-Tour"
_USER_ID = "default"


def _make_trip() -> Trip:
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[
            Stage(
                id="S1",
                name="Heute-Etappe",
                date=TODAY,
                waypoints=[Waypoint(id="W1", name="Start", lat=42.1, lon=9.0, elevation_m=800)],
            ),
        ],
    )


def _make_snapshot_segments() -> list[SegmentWeatherData]:
    """6 Stundenpunkte mit einer MED-Stunde -- unabhaengiger Nachweis von
    AC-1/AC-2, da ``_handle_hours_drilldown`` bislang eine eigene
    if/elif-Verzweigung mit eigenem 'mäßig'-Literal besass."""
    provider = Provider.OPENMETEO
    meta = ForecastMeta(provider=provider, model="test", grid_res_km=0.0)
    thunder_seq = [ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH]
    hourly_points = [
        ForecastDataPoint(
            ts=RECEIVED_AT + timedelta(hours=i),
            thunder_level=thunder_seq[i % len(thunder_seq)],
            wind10m_kmh=20.0,
            precip_1h_mm=0.0,
        )
        for i in range(6)
    ]
    timeseries = NormalizedTimeseries(meta=meta, data=hourly_points)
    segment = TripSegment(
        segment_id="seg-2010",
        start_point=GPXPoint(lat=42.1, lon=9.0, elevation_m=800),
        end_point=GPXPoint(lat=42.2, lon=9.1, elevation_m=600),
        start_time=RECEIVED_AT,
        end_time=RECEIVED_AT + timedelta(hours=5),
        duration_hours=5.0,
        distance_km=8.0,
        ascent_m=100.0,
        descent_m=100.0,
    )
    summary = SegmentWeatherSummary(
        thunder_level_max=ThunderLevel.HIGH, wind_max_kmh=20.0, precip_sum_mm=0.0
    )
    return [
        SegmentWeatherData(
            segment=segment,
            timeseries=timeseries,
            aggregated=summary,
            fetched_at=RECEIVED_AT,
            provider=provider.value,
        )
    ]


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> Path:
    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)
    save_trip(_make_trip(), _USER_ID)
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(_USER_ID).save(_TRIP_ID, _make_snapshot_segments(), TODAY)
    return tmp_path


def _process(body: str, channel: str) -> CommandResult:
    msg = InboundMessage(
        channel=channel,
        trip_name=_TRIP_NAME,
        body=body,
        sender="test",
        received_at=RECEIVED_AT,
        user_id=_USER_ID,
    )
    return TripCommandProcessor().process(msg)


def test_ac3_hours_drilldown_med_stunde_zeigt_mittel_nicht_maessig(env):
    """AC-3, Klartext (E-Mail-Kanal): die MED-Stunde zeigt 'mittel' am
    Zeilenende, 'mäßig' erscheint nirgends im Body."""
    result = _process("### query: dd_hours_today", channel="email")
    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    body = result.confirmation_body

    zeilen_mit_mittel = [ln for ln in body.splitlines() if ln.rstrip().endswith("mittel")]
    assert zeilen_mit_mittel, f"Keine Zeile mit 'mittel' (Klartext, MED) gefunden:\n{body}"
    assert "mäßig" not in body, f"'mäßig' noch im Stundendrilldown-Body:\n{body}"


def test_ac3_hours_drilldown_med_stunde_zeigt_gelbes_emoji_telegram(env):
    """AC-3, Emoji (Telegram-Kanal): die MED-Stunde zeigt das gelbe
    Kreis-Emoji 🟡 am Zeilenende, 'mäßig' erscheint nirgends im Body."""
    result = _process("### query: dd_hours_today", channel="telegram")
    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    body = result.confirmation_body

    zeilen_mit_gelb = [ln for ln in body.splitlines() if ln.rstrip().endswith("🟡")]
    assert zeilen_mit_gelb, f"Keine Zeile mit 🟡 (Emoji, MED) gefunden:\n{body}"
    assert "mäßig" not in body, f"'mäßig' noch im Stundendrilldown-Body:\n{body}"


_STUNDENZEILE = re.compile(r"^(\d{2})\s")
# NONE-Stunden der Fixture in Ortszeit: `thunder_seq[i % 3] == NONE` fuer i=0/3,
# Startpunkt 08:00 UTC, Korsika im September UTC+2.
_NONE_STUNDEN = ("10", "13")


@pytest.mark.parametrize(
    "channel,karte",
    [("email", _thunder_words), ("telegram", _thunder_symbols)],
)
def test_ac3_hours_drilldown_none_stunde_zeigt_strich_statt_stufenwort(env, channel, karte):
    """AC-3 / Implementation Details #2010: der NONE-Sonderfall bleibt ein
    eigener Zweig -- eine Stunde ohne Gewitter zeigt '—', NICHT den Eintrag,
    den ``thunder_karte`` fuer NONE traegt ('kein' bzw. ⚪). Ohne den
    Sonderfall stuende dort dieser Eintrag."""
    none_eintrag = karte()["NONE"]
    assert none_eintrag and none_eintrag != "—", (
        "Positivkontrolle: die Stufenkarte muss fuer NONE einen eigenen, vom "
        f"Strich verschiedenen Eintrag tragen, gefunden {none_eintrag!r}"
    )

    result = _process("### query: dd_hours_today", channel=channel)
    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    body = result.confirmation_body
    stunden = {
        m.group(1): ln.rstrip()
        for ln in body.splitlines()
        if (m := _STUNDENZEILE.match(ln))
    }

    for h in _NONE_STUNDEN:
        assert h in stunden, f"Stunde {h} fehlt im Drilldown:\n{body}"
        assert stunden[h].endswith("—"), (
            f"NONE-Stunde {h} endet nicht auf '—': {stunden[h]!r}"
        )
    fehlgriffe = [ln for ln in stunden.values() if ln.endswith(none_eintrag)]
    assert not fehlgriffe, (
        f"Stundenzeile zeigt den NONE-Eintrag {none_eintrag!r} statt '—': {fehlgriffe}"
    )


# ---------------------------------------------------------------------------
# AC-4: Ableitung statt Wert-Kopie (Regressionsschutz)
# ---------------------------------------------------------------------------


def test_ac4_thunder_fmt_plain_folgt_veraendertem_quellwort(monkeypatch):
    """AC-4: ein testlokal veraendertes ``THUNDER_LABEL_DE[MED]`` muss im
    ueber ``_thunder_fmt()`` gerenderten Wort erscheinen -- Beleg fuer
    Ableitung statt einmaliger Wert-Kopie."""
    monkeypatch.setitem(THUNDER_LABEL_DE, ThunderLevel.MED, "XTESTWORT")
    text = _thunder_fmt(ThunderLevel.MED, with_emoji=False)
    assert text == "XTESTWORT", (
        f"Erwartet den veraenderten Quellwert 'XTESTWORT', erhalten {text!r} -- "
        "_thunder_fmt() liest THUNDER_LABEL_DE offenbar nicht bei jedem Aufruf."
    )


@pytest.mark.parametrize(
    "body,konsument",
    [
        ("gewitter", "_fmt_gewitter"),
        ("glance", "_fmt_day_agg"),
        ("### query: timeline_heute", "_fmt_timeline"),
    ],
)
def test_ac4_zusammenfassung_glance_timeline_folgen_veraendertem_quellwort(
    env, monkeypatch, body, konsument
):
    """AC-4 fuer die drei uebrigen Stufenwort-Konsumenten: auch
    ``_fmt_gewitter``/``_fmt_day_agg``/``_fmt_timeline`` muessen bei JEDEM
    Aufruf aus ``THUNDER_LABEL_DE`` ableiten. Ein einmaliger Modul-Snapshot
    (frueher ``_THUNDER_LABEL``) bliebe hier auf dem alten Wort stehen.

    Veraendert wird HIGH, weil der Fixture-Schnappschuss als Tages-/Wegpunkt-
    Stufe HIGH traegt -- MED erreicht diese drei Ausgaben nicht."""
    monkeypatch.setitem(THUNDER_LABEL_DE, ThunderLevel.HIGH, "XTESTWORT")
    result = _process(body, channel="email")
    assert result.success is True, f"Erwartet success=True: {result.confirmation_body!r}"
    text = result.confirmation_body
    assert "XTESTWORT" in text, (
        f"{konsument} zeigt den veraenderten Quellwert nicht:\n{text}"
    )
    assert "hoch" not in text, (
        f"{konsument} zeigt weiterhin das eingefrorene Wort 'hoch':\n{text}"
    )


# ---------------------------------------------------------------------------
# AC-5: Ampeluebersetzung aller vier Stufen -- abgeleitet statt kopiert
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "level,expected",
    [
        (ThunderLevel.NONE, "ok"),
        (ThunderLevel.LOW, "yellow"),
        (ThunderLevel.MED, "watch"),
        (ThunderLevel.HIGH, "risk"),
    ],
)
def test_ac5_thunder_risk_level_uebersetzt_alle_vier_stufen_enum(level, expected):
    assert _thunder_risk_level(level) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("NONE", "ok"), ("LOW", "yellow"), ("MED", "watch"), ("HIGH", "risk")],
)
def test_ac5_thunder_risk_level_uebersetzt_alle_vier_stufen_string(raw, expected):
    assert _thunder_risk_level(raw) == expected


def test_ac5_thunder_risk_level_folgt_veraendertem_ampel_band_fuer_med(monkeypatch):
    """AC-5: Ableitungsnachweis -- ein testlokal veraenderter Eintrag in
    ``_THUNDER_AMPEL_BAND[MED]`` aendert das Ergebnis fuer MED entsprechend,
    weil die Uebersetzung jetzt tatsaechlich ueber ``thunder_ampel_band()``
    laeuft statt ueber eine eigene Wort-Kette."""
    monkeypatch.setitem(_THUNDER_AMPEL_BAND, ThunderLevel.MED, "red")
    ergebnis = _thunder_risk_level(ThunderLevel.MED)
    assert ergebnis == "risk", (
        f"Veraendertes Ampelband fuer MED ('red') liefert {ergebnis!r}, erwartet "
        "'risk' -- _thunder_risk_level() scheint eine eigene Wort-Kette statt "
        "thunder_ampel_band() zu nutzen."
    )


# ---------------------------------------------------------------------------
# AC-6: NONE liefert jetzt "ok" statt None
# ---------------------------------------------------------------------------


def test_ac6_thunder_risk_level_none_liefert_ok_statt_none():
    """AC-6: NONE liefert jetzt 'ok' (nicht mehr None) -- Vokabular-
    Erweiterung, verhaltensneutral abgesichert (Regressionsschutz-Nachweis
    fuer die Downstream-Wirkung: siehe
    test_thunder_risk_dot_and_tint.py::test_ac4_..., unveraendert gruen)."""
    assert _thunder_risk_level(ThunderLevel.NONE) == "ok"
    assert _thunder_risk_level("NONE") == "ok"


def test_ac6_row_risk_bleibt_fuer_none_gewitter_unveraendert_ok():
    """AC-6 zweiter Teil: ``_row_risk()`` liefert fuer eine ansonsten
    unauffaellige Zeile mit NONE-Gewitter unveraendert 'ok' -- der Wechsel
    von None auf 'ok' bei ``_thunder_risk_level()`` bleibt an dieser
    Pruefstelle wirkungslos."""
    row = {
        "time": "14:00", "temp": 18.0, "wind": 10.0, "gust": 15.0,
        "precip": 0.0, "pop": 5.0, "thunder": ThunderLevel.NONE,
    }
    assert _row_risk(row) == "ok"


# ---------------------------------------------------------------------------
# AC-7: Zahlen-Fallback bleibt funktionsfaehig (Regressionsschutz)
# ---------------------------------------------------------------------------

_BG_HEX = re.compile(r"background:\s*(#[0-9a-fA-F]{6})")
_THUNDER_COL_LABEL = "Thdr"
CELL_RED = "#f7d3e2"
CELL_ORANGE = "#fbe3cc"


def _render_one(row: dict) -> str:
    return _render_html_table([row], friendly_keys=set(), indicator_keys=set())


def _thunder_cell_bg(html: str):
    soup = BeautifulSoup(html, "html.parser")
    tr = soup.find("tbody").find_all("tr")[0]
    td = tr.find("td", attrs={"data-label": _THUNDER_COL_LABEL})
    if td is None:
        return None
    match = _BG_HEX.search(td.get("style", ""))
    return match.group(1).lower() if match else None


def test_ac7_zahlen_fallback_bleibt_funktionsfaehig_fuer_numerische_rohwerte():
    """AC-7 (Regressionsschutz gegen versehentliches Entfernen): eine
    Tabellenzeile mit rohem numerischem 'thunder'-Wert (aelterer Legacy-
    Datenpfad, #1425) bekommt weiterhin einen Warnhintergrund ueber den
    Zahlen-Fallback-Zweig in ``_thunder_risk_level()``."""
    row_base = {"time": "14:00", "temp": 18.0, "wind": 10.0, "gust": 15.0,
                "precip": 0.0, "pop": 5.0}

    assert _thunder_cell_bg(_render_one({**row_base, "thunder": 25.0})) == CELL_RED
    assert _thunder_cell_bg(_render_one({**row_base, "thunder": 5.0})) == CELL_ORANGE
    assert _thunder_cell_bg(_render_one({**row_base, "thunder": 0.0})) is None
