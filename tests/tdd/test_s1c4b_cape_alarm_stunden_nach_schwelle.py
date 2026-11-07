"""Issue #2792 S1c-4b Fix-Loop 2 (Adversary F001) — CAPE-Alarm wählt Stunden über die Schwelle.

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md, AC-6 („CAPE trägt
keine eigene Farbe/Stufe").

Seit CAPE keine Ampel-Stufe mehr hat, darf die Stundenauswahl des
Abweichungsalarms (``alert.hours.affected_hours``) CAPE nicht mehr als
Stufen-Metrik behandeln: ``_stage("cape", …)`` ist für jeden Wert ``None``.
Stünde CAPE weiter in ``_LEVEL_METRICS``, gäbe es
  * ohne Anker KEINE einzige Stundenzeile (keine Stunde „ab Gelb"),
  * mit Anker den Rückfall „jede abweichende Stunde" — also auch Stunden
    UNTER der Schwelle (400, 300 J/kg).
Soll: CAPE zählt über die Schwelle, wie jede Metrik ohne Stufe.

Reihe (UTC 08–13 Uhr): 100 / 400 / 900 / 1600 / 1700 / 300, Schwelle 500,
Ausgangswert bzw. Anker 100 → betroffen genau 10, 11, 12 Uhr UTC.

Geprüft wird dort, wo die Auswahl wirkt:
  1. ``affected_hours`` direkt, in allen Profil-Vorlagen, mit und ohne Anker.
  2. Echter Trip-Alarm-Weg: ``WeatherChange`` (CAPE) + Segment mit
     Stundenreihe → ``to_alert_message`` → ``render_email`` → Stundenzeilen
     der Mail.

Kern-Schicht: echte Domänenobjekte, keine Mocks, kein Netz.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from bs4 import BeautifulSoup

from app.ampel import AMPEL_TEMPLATES, resolve_ampel

UTC = timezone.utc
VORLAGEN = sorted(AMPEL_TEMPLATES)

_T0 = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
_CAPE = [100.0, 400.0, 900.0, 1600.0, 1700.0, 300.0]   # 08..13 Uhr UTC
_ANKER = [100.0] * len(_CAPE)
_SCHWELLE = 500.0
_UNTER_SCHWELLE = {"400", "300", "100"}


def _ampel(vorlage: str) -> dict:
    return resolve_ampel({"display_config": {"preset_name": vorlage}})


def _reihe(werte):
    from services.weather_snapshot import _deserialize_timeseries
    rows = [{"ts": (_T0 + timedelta(hours=i)).isoformat(), "t2m_c": 15.0, "cape_jkg": v}
            for i, v in enumerate(werte)]
    ts = _deserialize_timeseries({"hourly": rows}, "openmeteo")
    assert ts is not None and [p.cape_jkg for p in ts.data] == list(werte)
    return ts


# ---------------------------------------------------------------------------
# 1. affected_hours direkt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vorlage", VORLAGEN)
@pytest.mark.parametrize("mit_anker", [False, True], ids=["ohne_anker", "mit_anker"])
def test_cape_alarm_stunden_genau_ueber_der_schwelle(vorlage, mit_anker):
    from output.renderers.alert.hours import affected_hours
    out = affected_hours(
        "cape", _reihe(_CAPE), _reihe(_ANKER) if mit_anker else None,
        threshold=_SCHWELLE, value_from=100.0, tz=UTC, ampel=_ampel(vorlage),
    )
    assert out, (
        f"CAPE-Alarm ohne eine einzige Stundenzeile (Vorlage {vorlage}, "
        f"Anker={mit_anker}) — CAPE wird als Stufen-Metrik behandelt"
    )
    zeiten = [r.time for r in out["hours"]]
    werte = [r.value_to for r in out["hours"]]
    assert zeiten == ["10:00", "11:00", "12:00"], (
        f"Falsche CAPE-Stunden (Vorlage {vorlage}, Anker={mit_anker}): "
        f"{list(zip(zeiten, werte))!r}"
    )
    assert werte == [900.0, 1600.0, 1700.0]
    assert all(w - 100.0 >= _SCHWELLE for w in werte), werte
    if mit_anker:
        assert [r.value_from for r in out["hours"]] == [100.0, 100.0, 100.0]
    else:
        assert all(r.value_from is None for r in out["hours"])
    assert out["hours_range"] == ("10:00", "12:00")
    assert out["hours_capped"] is False


# ---------------------------------------------------------------------------
# 2. Echter Trip-Alarm-Weg bis in die Mail
# ---------------------------------------------------------------------------

def _segment(werte):
    from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment
    seg = TripSegment(
        segment_id="1",
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.05, lon=11.05, elevation_m=1500, distance_from_start_km=6.0),
        start_time=_T0,
        end_time=_T0 + timedelta(hours=len(werte) - 1),
        duration_hours=float(len(werte) - 1), distance_km=6.0, ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=_reihe(werte), aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(2026, 5, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


def _cape_aenderung():
    from app.models import ChangeSeverity, WeatherChange
    return WeatherChange(
        metric="cape_max_jkg", old_value=100.0, new_value=1700.0, delta=1600.0,
        threshold=_SCHWELLE, severity=ChangeSeverity.MAJOR, direction="increase",
        segment_id="1", occurred_at=_T0 + timedelta(hours=4),
    )


def _stundenzeilen(html: str) -> dict:
    """{HH:MM: [Zellentexte]} aller Tabellenzeilen, deren erste Zelle eine Uhrzeit ist."""
    import re
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if tds and re.fullmatch(r"\d{2}:\d{2}", tds[0].get_text(strip=True)):
            out[tds[0].get_text(strip=True)] = [td.get_text(strip=True) for td in tds[1:]]
    return out


# Koordinaten 47/11 = Europe/Vienna (Mai: UTC+2) → 10/11/12 Uhr UTC = 12/13/14 Uhr.
_ERWARTET = {"12:00": "900", "13:00": "1600", "14:00": "1700"}


@pytest.mark.parametrize("vorlage", VORLAGEN)
@pytest.mark.parametrize("mit_anker", [False, True], ids=["ohne_anker", "mit_anker"])
def test_cape_alarm_mail_zeigt_genau_die_stunden_ueber_der_schwelle(vorlage, mit_anker):
    from output.renderers.alert.project import to_alert_message
    from output.renderers.alert.render import render_email
    msg = to_alert_message(
        [_cape_aenderung()], [_segment(_CAPE)], "Cape", tz=UTC, stand_at="06:00",
        anchor_segments=[_segment(_ANKER)] if mit_anker else None,
        ampel=_ampel(vorlage),
    )
    assert [e.metric_id for e in msg.events] == ["cape"], "Vorbedingung: CAPE-Ereignis"
    html, _plain = render_email(msg)
    zeilen = _stundenzeilen(html)
    assert set(zeilen) == set(_ERWARTET), (
        f"Stundenzeilen der CAPE-Alarm-Mail falsch (Vorlage {vorlage}, "
        f"Anker={mit_anker}): {zeilen!r}"
    )
    for zeit, zahl in _ERWARTET.items():
        assert any(zahl in t for t in zeilen[zeit]), (
            f"{zeit}: Zahl {zahl} fehlt (Vorlage {vorlage}): {zeilen[zeit]!r}"
        )
    # Zelle ohne Anker „900", mit Anker „100 → 900": gezählt wird der neue Wert.
    alle_neu = [z[-1].split("→")[-1].strip() for z in zeilen.values()]
    assert alle_neu == [_ERWARTET[k] for k in zeilen], zeilen
    assert not any(t in _UNTER_SCHWELLE for t in alle_neu), (
        f"Stunden unter der Schwelle in der Mail (Vorlage {vorlage}): {zeilen!r}"
    )
