"""Issue #3197, AC-3 (ADR-0095): Kanal-Paritaet des Etappen-Tempos.

Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md, Test Plan
"Kanal-Paritaet": Trip mit Ueberschreibung auf Etappe 3; fuer E-Mail,
Telegram, SMS und Premium-SMS sind die bewerteten Stunden der Wegpunkte von
Etappe 3 gegenueber dem Lauf ohne Ueberschreibung geaendert, in allen vier
Kanaelen gleich; Wegpunkte der anderen Etappen identisch.

Gemessen wird der GERENDERTE Text aller vier Kanaele (``TripReportFormatter.
format_email`` liefert E-Mail HTML/Klartext, Telegram-Bubbles, SMS und
Premium-SMS aus EINEM Lauf), nicht ein Zwischenwert. Der Trip laeuft durch den
echten Schreibpfad (``save_trip`` -> Compute-on-Save -> ``arrival_calculated``)
und die echte Segmentbildung (``convert_trip_to_segments``).

Messaufbau: Etappe 3 hat drei Wegpunkte (0/4/8 km, 1000/1600/1000 m), Trip zu
Fuss 4 km/h. Ohne Ueberschreibung erreicht man den zweiten Wegpunkt um 10:30,
mit 3 km/h um 11:20 (Falltabelle). Nur das Wetter am ERSTEN Wegpunkt (Segment 1)
traegt einen Marker in der Stunde 11 (6 mm Regen, 25 C). Mit Ueberschreibung
gehoert Stunde 11 zu Segment 1 und wird bewertet, ohne Ueberschreibung liegt
sie in Segment 2 (anderer Ort, kein Regen). Jeder Kanal muss also mit
Ueberschreibung "Regen um 11" melden und ohne nicht.

Kern-Schicht: ohne Netz, ohne Mocks (Wetterreihen sind Eingabedaten).
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.loader import load_trip_from_dict, save_trip
from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
)
from output.renderers.trip_report import TripReportFormatter
from services.trip_segments import convert_trip_to_segments

_HERE = Path(__file__).resolve().parent
FALL = json.loads((_HERE / "fixtures" / "naismith_dav_paritaet.json").read_text(encoding="utf-8"))[
    "etappen_ueberschreibung"
]
ORT = ZoneInfo("Europe/Vienna")  # 47 N / 11 E, Juli = UTC+2
TAGE = {"S1": date(2026, 7, 1), "S2": date(2026, 7, 2), "S3": date(2026, 7, 3)}
MARKER_STUNDE_LOKAL = 11


def _trip_dict(s3_kmh: float | None) -> dict:
    """Drei gleich gebaute Etappen der Falltabelle; nur S3 traegt ggf. ein eigenes Tempo."""
    stages = copy.deepcopy(FALL["stages"])
    for st in stages:
        st.pop("grundtempo_kmh", None)
    s3 = copy.deepcopy(stages[0])
    s3.update(id="S3", name="Tag 3", date=TAGE["S3"].isoformat())
    for wp in s3["waypoints"]:
        wp["id"] = wp["name"] = wp["id"].replace("S1", "S3")
    if s3_kmh is not None:
        s3["grundtempo_kmh"] = s3_kmh
    stages.append(s3)
    return {"id": "t3197k", "name": "Kanal", "tempo": copy.deepcopy(FALL["tempo"]), "stages": stages}


def _reihe(tag: date, *, marker: bool) -> NormalizedTimeseries:
    """Stundenreihe (UTC); ``marker`` = Regen 6 mm / 25 C in der lokalen Stunde 11."""
    punkte = []
    for h in range(24):
        an = marker and h + 2 == MARKER_STUNDE_LOKAL
        punkte.append(ForecastDataPoint(
            ts=datetime(tag.year, tag.month, tag.day, h, tzinfo=timezone.utc),
            t2m_c=25.0 if an else 10.0, wind10m_kmh=5.0, gust_kmh=8.0,
            precip_1h_mm=6.0 if an else 0.0, cloud_total_pct=50, pop_pct=90 if an else 0,
        ))
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.2,
                        run=datetime(tag.year, tag.month, tag.day, tzinfo=timezone.utc))
    return NormalizedTimeseries(meta=meta, data=punkte)


def _gespeicherter_trip(tmp_path: Path, user: str, s3_kmh: float | None):
    pfad = save_trip(load_trip_from_dict(_trip_dict(s3_kmh)), user, data_dir=tmp_path)
    return load_trip_from_dict(json.loads(pfad.read_text(encoding="utf-8")))


def _briefing(trip, stage_id: str):
    tag = TAGE[stage_id]
    segmente = [
        SegmentWeatherData(segment=seg, timeseries=_reihe(tag, marker=(i == 0)),
                           aggregated=SegmentWeatherSummary(),
                           fetched_at=datetime(2026, 6, 30, tzinfo=timezone.utc), provider="openmeteo")
        for i, seg in enumerate(convert_trip_to_segments(trip, tag))
    ]
    return TripReportFormatter().format_email(
        segmente, "Kanal", "morning", display_config=build_default_display_config(),
        tz=ORT, trip=trip,
    )


def _ohne_wanduhr(text: str) -> str:
    """Fusszeile ``Generated: ...`` traegt die Wanduhr, keinen Wetterwert."""
    return "\n".join(z for z in text.splitlines() if not z.startswith("Generated: "))


def _kanaele(report) -> dict[str, str]:
    return {
        "email": _ohne_wanduhr(report.email_plain),
        "telegram": "\n".join(report.telegram_bubbles),
        "sms": report.sms_text or "",
        "premium_sms": report.premium_sms_text or report.sms_text or "",
    }


#: Woran jeder Kanal "Regen 6 mm in Stunde 11 bewertet" zeigt (Kanal-Format).
REGEN_11 = {
    "email": "Regen ab 11:00 · 6 mm",
    "telegram": "R 0.0-6.0@11",
    "sms": "R6.0@11",
    "premium_sms": "R6.0@11",
}


@pytest.fixture
def berichte(tmp_path):
    mit = _gespeicherter_trip(tmp_path, "u3197mit", 3)
    ohne = _gespeicherter_trip(tmp_path, "u3197ohne", None)
    return mit, ohne


def test_messaufbau_ankuenfte_etappe_3(berichte):
    """Positivkontrolle: S3 mit 3 km/h erreicht Wegpunkt 2 um 11:20, ohne um 10:30."""
    mit, ohne = berichte
    s3_mit = next(s for s in mit.stages if s.id == "S3")
    s3_ohne = next(s for s in ohne.stages if s.id == "S3")
    assert [wp.arrival_calculated for wp in s3_mit.waypoints] == FALL["erwartet"]["S2"]["ankuenfte"]
    assert [wp.arrival_calculated for wp in s3_ohne.waypoints] == FALL["erwartet"]["S1"]["ankuenfte"]


def test_etappe_3_alle_vier_kanaele_bewerten_die_geaenderte_stunde(berichte):
    """AC-3: mit Ueberschreibung bewerten E-Mail, Telegram, SMS und Premium-SMS
    die Stunde 11 am ersten Wegpunkt (Regen 6 mm um 11), ohne Ueberschreibung
    keiner der vier Kanaele. Alle vier aendern sich also gleich."""
    mit, ohne = berichte
    k_mit, k_ohne = _kanaele(_briefing(mit, "S3")), _kanaele(_briefing(ohne, "S3"))
    for kanal, marke in REGEN_11.items():
        assert marke in k_mit[kanal], f"{kanal}: mit Etappen-Tempo fehlt '{marke}':\n{k_mit[kanal]}"
        assert marke not in k_ohne[kanal], f"{kanal}: ohne Etappen-Tempo steht '{marke}':\n{k_ohne[kanal]}"
        assert k_mit[kanal] != k_ohne[kanal], f"{kanal}: Ausgabe unveraendert"


def test_etappe_3_mail_zeigt_die_neuen_wegpunkt_zeiten(berichte):
    """AC-3: Die Mail (Klartext und HTML) nennt die Segmentzeiten der
    Etappe-3-Wegpunkte mit Etappen-Tempo (08:00–11:20, 11:20–13:36)."""
    mit, ohne = berichte
    r_mit, r_ohne = _briefing(mit, "S3"), _briefing(ohne, "S3")
    for text in (r_mit.email_plain, r_mit.email_html):
        assert "08:00–11:20" in text and "11:20–13:36" in text
    for text in (r_ohne.email_plain, r_ohne.email_html):
        assert "08:00–10:30" in text and "10:30–12:12" in text
        assert "11:20" not in text


@pytest.mark.parametrize("stage_id", ["S1", "S2"])
def test_uebrige_etappen_in_allen_vier_kanaelen_identisch(berichte, stage_id):
    """AC-3: Die Wegpunkte der Etappen ohne Ueberschreibung liefern in allen
    vier Kanaelen exakt dieselbe Ausgabe wie im Trip ohne Etappen-Tempo."""
    mit, ohne = berichte
    k_mit, k_ohne = _kanaele(_briefing(mit, stage_id)), _kanaele(_briefing(ohne, stage_id))
    for kanal in REGEN_11:
        assert k_mit[kanal] == k_ohne[kanal], f"{stage_id}/{kanal} durch S3-Tempo veraendert"
