"""Wirksame Bewölkung aus Nutzersicht, in allen vier Kanälen (Issue #3106, ADR-0122).

SPEC: docs/specs/modules/feat_3106_wirksame_bewoelkung.md (AC-1, AC-3, AC-4,
AC-5, AC-7, AC-8, AC-9)

Kern-Schicht, netzfrei, ohne Mock-Theater. Die Wetterdaten laufen durch den
ECHTEN Abrufweg (Normalisierung am Provider-Ausgang), danach durch die echten
Renderer bzw. den echten Versand:

* **Trip:** ``OpenMeteoProvider`` mit Open-Meteo-Antwort aus einem
  ``httpx.MockTransport`` (``_wirksame_bewoelkung_fixtures``) -> Segment ->
  ``NotificationService.send_trip_report`` mit dem Golden-Trip ``golden_b``
  (E-Mail, SMS, Premium-SMS, Telegram); einzige Naht ist der geteilte
  Transport-Aufzeichner (``tests/helpers/transport_mitschrift.py``).
* **Ortsvergleich:** ``ComparisonEngine.run`` über den Offline-Spiegel
  ``FixtureProvider`` (Fixture mit Wolkenschichten im tmp-Ordner) -> die
  Produktiv-Renderer für E-Mail, Telegram und SMS. Die Premium-SMS des
  Ortsvergleichs trägt denselben SMS-Text (``send_compare_report`` schickt
  ``sms_text`` an beide SMS-Kanäle).

Stunden im Tal wechseln zwischen Schleierwolken (Modell 100 %, wirksam 50 %)
und der gemischten AC-3-Stunde (Modell 84 %, wirksam 52 %).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.helpers.ampel_allgemein import AMPEL_ALLGEMEIN, PRESET_ALLGEMEIN
from tests.tdd._wirksame_bewoelkung_fixtures import (
    GEMISCHT, NUR_TIEF, SCHLEIER, open_meteo_antwort, provider_mit_antwort,
)

pytestmark = pytest.mark.filterwarnings("ignore")

WIEN = ZoneInfo("Europe/Vienna")
_DICHT_MITTEL = {"cloud_cover": 100, "cloud_cover_low": 0, "cloud_cover_mid": 100,
                 "cloud_cover_high": 0}
_GELB_AB = 70  # Ampel-Grundeinstellung Bewölkung (gelb ab 70 %)


def _wechselnd(h: int) -> dict:
    return SCHLEIER if h % 2 == 0 else GEMISCHT


# ═══════════════════════════════ Trip ═══════════════════════════════════════


def _trip_senden(monkeypatch, tmp_path, *, wolken_je_stunde, hoehe_m: float):
    """Open-Meteo-Abruf -> Segment -> echter Versand von ``golden_b``.
    Liefert die Kanalmitschrift."""
    from app.config import Location
    from app.loader import load_trip
    from app.models import GPXPoint, SegmentWeatherData, TripSegment
    from services.notification_service import NotificationService, TripReportRequest
    from services.weather_metrics import summarize_points
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd._einstellung_auslieferung_fixtures import (
        TRANSPORT_ENV, TZ, frisches_profil,
    )
    from tests.tdd._sms_einfach_fixtures import variante

    stunden = [f"2026-07-20T{h:02d}:00" for h in range(24)]
    antwort = open_meteo_antwort(
        stunden, [wolken_je_stunde(h) for h in range(24)], temperature_2m=15.0,
        wind_speed_10m=10.0, wind_gusts_10m=20.0, precipitation=0.0,
        direct_normal_irradiance=300.0, is_day=1, weather_code=3,
    )
    ort = Location(latitude=42.0, longitude=9.0, name="Etappe", elevation_m=int(hoehe_m))
    reihe = provider_mit_antwort(monkeypatch, tmp_path, antwort).fetch_forecast(
        ort, enrich_ensemble=False, enrich_snow=False,
    )
    start = datetime(2026, 7, 20, 8, tzinfo=TZ).astimezone(timezone.utc)
    ende = datetime(2026, 7, 20, 12, tzinfo=TZ).astimezone(timezone.utc)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=hoehe_m, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=hoehe_m, distance_from_start_km=12.0),
        start_time=start, end_time=ende, duration_hours=4.0, distance_km=12.0,
        ascent_m=100.0, descent_m=100.0,
    )
    fenster = [dp for dp in reihe.data
               if start <= dp.ts.replace(tzinfo=timezone.utc) <= ende]
    wetter = SegmentWeatherData(
        segment=seg, timeseries=reihe, aggregated=summarize_points(fenster),
        fetched_at=datetime(2026, 7, 20, 6, tzinfo=timezone.utc), provider="openmeteo",
    )
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mitschrift = aufzeichner_installieren(monkeypatch)
    trip = load_trip(variante("golden_b"), user_id="default")
    rc = trip.report_config
    ergebnis = NotificationService(user_id=frisches_profil()).send_trip_report(TripReportRequest(
        trip=trip, report_type="evening", segment_weather=[wetter], trip_tz=TZ,
        night_weather=reihe, stage_name="E1", report_config=rc,
        display_config=trip.display_config, send_email=rc.send_email, send_sms=rc.send_sms,
        send_telegram=rc.send_telegram, send_premium_sms=rc.send_premium_sms,
    ))
    assert ergebnis.sent, f"Vorbedingung: Briefing muss versendet werden: {ergebnis}"
    assert set(mitschrift.kanaele) == {"email", "sms", "premium_sms", "telegram"}, mitschrift
    return mitschrift


def _segment_wolken_spalte(mail_text: str) -> list[int]:
    """Werte der Spalte ``Cloud`` in der Segment-Stundentabelle der Klartext-Mail."""
    teil = mail_text.split("━━ Segment 1", 1)[1].split("━━ Nacht", 1)[0]
    zeilen = teil.strip().splitlines()
    spalte = zeilen[1].split().index("Cloud")
    return [int(z.split()[spalte]) for z in zeilen[3:] if re.match(r"^\s*\d\d\s", z)]


def _ct_wert(sms: str) -> int | None:
    treffer = re.search(r"(?:^|\s)CT(\d+)", sms)
    return int(treffer.group(1)) if treffer else None


def test_trip_schleierwolken_in_allen_vier_kanaelen(monkeypatch, tmp_path):
    """AC-1/AC-3/AC-7/AC-8 Trip: Tal (500 m), wechselnd Schleier/gemischt."""
    mit = _trip_senden(monkeypatch, tmp_path, wolken_je_stunde=_wechselnd, hoehe_m=500.0)

    mail = mit.sendungen("email")[0]["plain_text_body"]
    stunden = _segment_wolken_spalte(mail)
    assert stunden == [50, 52, 50, 52, 50], f"Stundentabelle E-Mail (Roh): {stunden}"
    # AC-7: Tagesmittel = Mittel der angezeigten Stundenwerte, Pille = Spanne.
    mittel = round(sum(stunden) / len(stunden))
    assert f"Wolken {mittel}%" in mail, mail[:600]
    assert "50–52% bewölkt" in mail, mail[:900]

    for kanal in ("sms", "premium_sms"):
        text = mit.sendungen(kanal)[0]["body"]
        assert _ct_wert(text) == 52, f"{kanal}: Spitze der wirksamen Bewölkung: {text}"

    telegram = "\n".join(s["body"] for s in mit.sendungen("telegram"))
    tabelle = telegram.split("<pre>", 1)[1].split("</pre>", 1)[0]
    assert tabelle.count("⛅") == 5, f"AC-1: Einfach-Modus ⛅ je Stunde: {tabelle}"
    assert "☁️" not in telegram and "🌥️" not in telegram, telegram
    # AC-8: keine Stunde erreicht auch nur die gelbe Grenze der Grundeinstellung.
    assert max(stunden) < _GELB_AB


def test_trip_hochlage_ueber_den_tiefen_wolken(monkeypatch, tmp_path):
    """AC-4 Trip: ab 2500 m zählen tiefe Wolken unter dem Standort nicht."""
    mit = _trip_senden(monkeypatch, tmp_path, wolken_je_stunde=lambda h: NUR_TIEF,
                       hoehe_m=3000.0)
    mail = mit.sendungen("email")[0]["plain_text_body"]
    assert _segment_wolken_spalte(mail) == [0, 0, 0, 0, 0]
    assert _ct_wert(mit.sendungen("sms")[0]["body"]) in (None, 0)


# ═══════════════════════════ Ortsvergleich ══════════════════════════════════


def _vergleich(monkeypatch, tmp_path, *, wolken_je_stunde, hoehe_m: int):
    """Ortsvergleich über den Offline-Spiegel ``FixtureProvider``."""
    from app.user import SavedLocation
    from services.comparison_engine import ComparisonEngine

    ordner = tmp_path / "fixture"
    ordner.mkdir()
    daten = []
    for i in range(72):
        w = wolken_je_stunde(i)
        daten.append({
            "cloud_total_pct": w["cloud_cover"], "cloud_low_pct": w["cloud_cover_low"],
            "cloud_mid_pct": w["cloud_cover_mid"], "cloud_high_pct": w["cloud_cover_high"],
            "t2m_c": 5.0, "wind10m_kmh": 10, "gust_kmh": 20, "precip_1h_mm": 0.0,
            "dni_wm2": 300, "is_day": 1, "wmo_code": 3,
        })
    (ordner / "innsbruck.json").write_text(json.dumps({"data": daten}))
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(ordner))
    # eindeutige Koordinate je Lauf -> kein vorbelegter Cache-Eintrag
    off = (uuid.uuid4().int % 9000) / 100000.0
    ort = SavedLocation(id=f"loc-{uuid.uuid4().hex[:6]}", name="Igls", lat=47.23 + off,
                        lon=11.41 + off, elevation_m=hoehe_m, timezone="Europe/Vienna")
    ergebnis = ComparisonEngine.run(
        locations=[ort], time_window=(9, 16),
        target_date=datetime.now(WIEN).date() + timedelta(days=1),
        official_alerts_enabled=False, user_id=f"wolken-{uuid.uuid4().hex[:6]}",
    )
    assert ergebnis.locations[0].error is None, ergebnis.locations[0].error
    return ergebnis


def _kanaele(ergebnis) -> dict:
    from output.renderers.comparison import (
        render_compare_email, render_compare_sms, render_compare_telegram,
    )

    html, klartext = render_compare_email(
        ergebnis, enabled_metrics=["cloud_avg"], hourly_metrics=["cloud_total_pct"],
        hourly_enabled=True, preset=PRESET_ALLGEMEIN,
    )
    return {
        "html": html, "klartext": klartext,
        "telegram": render_compare_telegram(
            ergebnis, enabled_metrics=["cloud_avg"], preset=PRESET_ALLGEMEIN),
        "sms": render_compare_sms(ergebnis, enabled_metrics=["cloud_avg"]),
    }


def _stundenwerte_klartext(klartext: str) -> list[int]:
    return [int(v) for v in re.findall(r"^\s+\d\d:00\s+Cloud (\d+)", klartext, re.M)]


def test_vergleich_schleierwolken_in_allen_kanaelen(monkeypatch, tmp_path):
    """AC-1/AC-3/AC-7/AC-8 Ortsvergleich: Übersicht und Stundenwerte stimmen
    überein, in E-Mail (HTML + Klartext), Telegram und SMS/Premium-SMS."""
    ergebnis = _vergleich(monkeypatch, tmp_path, wolken_je_stunde=_wechselnd, hoehe_m=870)
    ort = ergebnis.locations[0]
    stunden = [dp.cloud_total_pct for dp in ort.hourly_data]
    assert sorted(set(stunden)) == [50, 52], stunden
    # AC-7: das Tagesmittel ist das Mittel der angezeigten Stundenwerte.
    assert ort.cloud_avg == round(sum(stunden) / len(stunden)) == 51

    k = _kanaele(ergebnis)
    assert _stundenwerte_klartext(k["klartext"]) == stunden
    assert "Bewölkung: 51%" in k["klartext"], k["klartext"][:400]
    assert re.search(r">51%</td>", k["html"]), "Übersicht HTML"
    assert re.findall(r">(50|52)</td>", k["html"]), "Stundentabelle HTML"
    assert not re.search(r">(84|92|100)%?</td>", k["html"]), "kein Modellwert in der Mail"
    assert "Wolken 51%" in k["telegram"], k["telegram"]
    # #3172 (ADR-0125): Token-Zeile der Trip-SMS -- Spitze der WIRKSAMEN
    # Stundenwerte (52 %), nie ein Modellwert.
    assert re.search(r"CT52@\d+", k["sms"]), k["sms"]
    assert not re.search(r"CT(84|92|100)", k["sms"]), k["sms"]
    # AC-8: unterhalb der gelben Grenze -> keine Ampel-Stundenmarke (``@h``).
    from app.ampel import gelb_oder_schlechter

    assert max(stunden) < _GELB_AB
    assert not gelb_oder_schlechter(AMPEL_ALLGEMEIN, "cloud_total", float(max(stunden)))
    assert "@" not in k["telegram"].split("Wolken", 1)[1].splitlines()[0]


def test_vergleich_sonnenstunden_bleiben_bei_einstrahlung(monkeypatch, tmp_path):
    """AC-9: mit DNI beruhen die Sonnenstunden auf der Einstrahlung -- dieselben
    Stunden mit Modell-Gesamtbewölkung ergeben dieselben Sonnenstunden."""
    from dataclasses import replace

    from services.weather_metrics import WeatherMetricsService

    ergebnis = _vergleich(monkeypatch, tmp_path, wolken_je_stunde=_wechselnd, hoehe_m=870)
    ort = ergebnis.locations[0]
    roh = [replace(dp, cloud_total_pct=dp.cloud_total_model_pct) for dp in ort.hourly_data]
    assert [dp.cloud_total_pct for dp in roh] != [dp.cloud_total_pct for dp in ort.hourly_data]
    assert ort.sunny_hours == WeatherMetricsService.calculate_sunny_hours(roh) == 8.0


def test_vergleich_hochlage_uebersicht_und_stunden_gleich(monkeypatch, tmp_path):
    """AC-4: ab 2500 m nur tiefe Wolken -> 0 % in Übersicht UND Stundenwerten,
    Stern-Markierung „über den tiefen Wolken" bleibt."""
    ergebnis = _vergleich(monkeypatch, tmp_path, wolken_je_stunde=lambda i: NUR_TIEF,
                          hoehe_m=2800)
    ort = ergebnis.locations[0]
    assert {dp.cloud_total_pct for dp in ort.hourly_data} == {0}
    assert ort.cloud_avg == 0
    assert ort.above_low_clouds is True
    k = _kanaele(ergebnis)
    assert set(_stundenwerte_klartext(k["klartext"])) == {0}
    assert "Bewölkung: 0%" in k["klartext"]
    # #3172: 0 % in jeder Stunde = Leerwert der Token-Zeile.
    assert k["sms"] == "O1 CT-", k["sms"]


def test_vergleich_hochlage_dichte_mittelschicht_voll(monkeypatch, tmp_path):
    """AC-5: ab 2500 m dichte mittelhohe Schicht -> 100 % (bisher 50 %)."""
    ergebnis = _vergleich(monkeypatch, tmp_path, wolken_je_stunde=lambda i: _DICHT_MITTEL,
                          hoehe_m=2800)
    ort = ergebnis.locations[0]
    assert ort.cloud_avg == 100
    assert re.search(r"CT100@\d+", _kanaele(ergebnis)["sms"])  # #3172 Token-Zeile
