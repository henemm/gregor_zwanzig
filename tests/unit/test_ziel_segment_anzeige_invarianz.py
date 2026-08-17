"""TDD RED — Issue #1599: Das Alarmfenster gewinnt die Randstunde, die ANZEIGE
bleibt unveraendert. SPEC: fix_1599_tagesfenster_randstunde.md (AC-10..AC-15,
AC-18).

In der RED-Phase bereits GRUEN (so von der Spec verlangt): diese Tests bewachen
den Kollateralschaden, den erst die Implementierung ausloesen kann — das
Ziel-Segment endet danach eine Stunde spaeter, und jeder Anzeige-Konsument, der
``segment.end_time`` direkt liest, wuerde diese Stunde ungefragt mitzeigen.

Gemessen wird gerenderter Text, nicht ein Zwischenwert. Die 20-Uhr-Stunde traegt
einen unverwechselbaren Marker (47 °C), die 19-Uhr-Stunde einen zweiten (33 °C):
taucht ``47`` auf, hat die Ausgabe die neue Alarmgrenze uebernommen; fehlt
``33``, ist die Fixture kaputt (Positivkontrolle). Ort ist Reykjavik
(``Atlantic/Reykjavik``, ganzjaehrig UTC+0) — Ortszeit == UTC, keine
Offset-Rechnung.

Ausfuehrung:
    uv run pytest tests/unit/test_ziel_segment_anzeige_invarianz.py -v \
        --disable-socket --allow-hosts=127.0.0.1
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
)
from app.trip import Stage, Trip, Waypoint
from output.renderers.trip_report import TripReportFormatter
from services.trip_segments import convert_trip_to_segments

ISLAND_LAT, ISLAND_LON = 64.1466, -21.9426
TZ = ZoneInfo("Atlantic/Reykjavik")
TAG = date(2026, 7, 12)

MARKE_19 = 33.0      # letzte Stunde, die sichtbar bleiben MUSS
MARKE_20 = 47.0      # erste Stunde, die die Anzeige NIE erreichen darf
MARKE_NACHT = -21.0  # Nacht-Minimum, liegt NUR in der Ankunftsstunde 19
GRUND = 10.0


def _ts(hour: int, tag: date = TAG) -> datetime:
    return datetime(tag.year, tag.month, tag.day, hour, 0, tzinfo=timezone.utc)


def _meta() -> ForecastMeta:
    return ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                        grid_res_km=2.2, run=_ts(0))


def _tagesreihe() -> NormalizedTimeseries:
    temp = {19: MARKE_19, 20: MARKE_20}
    return NormalizedTimeseries(meta=_meta(), data=[
        ForecastDataPoint(ts=_ts(h), t2m_c=temp.get(h, GRUND), wind10m_kmh=5.0,
                          gust_kmh=8.0, precip_1h_mm=0.0, cloud_total_pct=50)
        for h in range(24)
    ])


def _nachtreihe() -> NormalizedTimeseries:
    """Ankunft 19:00 -> 06:00 des Folgetags. Der Nacht-Block zeigt je 2 h das
    MINIMUM — das Kaeltezeichen erscheint also nur, wenn der Block bei Stunde 19
    beginnt (AC-12)."""
    punkte = [
        ForecastDataPoint(ts=_ts(h), t2m_c=MARKE_NACHT if h == 19 else 5.0,
                          wind10m_kmh=5.0, gust_kmh=8.0, precip_1h_mm=0.0)
        for h in range(19, 24)
    ] + [
        ForecastDataPoint(ts=_ts(h, date(2026, 7, 13)), t2m_c=5.0,
                          wind10m_kmh=5.0, gust_kmh=8.0, precip_1h_mm=0.0)
        for h in range(0, 7)
    ]
    return NormalizedTimeseries(meta=_meta(), data=punkte)


def _segmente() -> list[SegmentWeatherData]:
    """Start 08:00 -> Sattel 15:00 (GLATTE Etappengrenze, AC-18) -> Tagesziel
    17:00; das Ziel-Segment baut die Produktion selbst."""
    stage = Stage(id="T1", name="Tag 1", date=TAG, waypoints=[
        Waypoint(id="W1", name="Start", lat=ISLAND_LAT - 0.1, lon=ISLAND_LON - 0.1,
                 elevation_m=100, arrival_calculated="08:00"),
        Waypoint(id="W2", name="Sattel", lat=ISLAND_LAT - 0.05, lon=ISLAND_LON - 0.05,
                 elevation_m=200, arrival_calculated="15:00"),
        Waypoint(id="W3", name="Tagesziel", lat=ISLAND_LAT, lon=ISLAND_LON,
                 elevation_m=300, arrival_calculated="17:00"),
    ])
    trip = Trip(id="anzeige-1599", name="Anzeige-Invarianz", stages=[stage])
    trip.report_config = TripReportConfig(trip_id=trip.id, send_email=True)
    reihe = _tagesreihe()
    return [
        SegmentWeatherData(
            segment=seg, timeseries=reihe,
            aggregated=SegmentWeatherSummary(temp_min_c=GRUND, temp_max_c=GRUND),
            fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        )
        for seg in convert_trip_to_segments(trip, TAG)
    ]


def _mail(night: bool = False):
    return TripReportFormatter().format_email(
        _segmente(), "Anzeige-Invarianz", "evening",
        display_config=build_default_display_config(),
        night_weather=_nachtreihe() if night else None, tz=TZ,
    )


def _ziel_abschnitt(plain: str) -> str:
    """Aufbau: "━━ 🏁 Wetter am Ziel: 17:00–19:00 | 300m ━━\\n<Tabelle>\\n━━ …".
    Teil 0 ist der Rest der Ueberschrift, Teil 1 die Stundentabelle."""
    assert "Wetter am Ziel" in plain, f"Fixture kaputt: kein Ziel-Abschnitt.\n{plain}"
    return plain.split("Wetter am Ziel", 1)[1].split("━━")[1]


def test_ac10_ziel_stundentabelle_zeigt_keine_20_uhr_zeile():
    """AC-10: Die Ziel-Stundentabelle bleibt bei Stunde 19 stehen, obwohl der
    Alarmpfad ab #1599 bis 20:00 auswertet."""
    abschnitt = _ziel_abschnitt(_mail().email_plain)
    assert "33" in abschnitt, f"Positivkontrolle 19-Uhr-Wert fehlt:\n{abschnitt}"
    assert "47" not in abschnitt, (
        "AC-10: Die Ziel-Stundentabelle zeigt den 20-Uhr-Datenpunkt (47 °C) — "
        f"die neue Alarm-Obergrenze ist in die Anzeige durchgeschlagen.\n{abschnitt}"
    )


def test_ac11_kopfzeile_wetter_am_ziel_endet_weiterhin_um_19_uhr():
    """AC-11: Die Kopfzeile 'Wetter am Ziel' zeigt weiterhin 17:00–19:00."""
    report = _mail()
    for name, text in (("Plain", report.email_plain), ("HTML", report.email_html)):
        assert "17:00–19:00" in text, (
            f"AC-11 ({name}): Kopfzeile muss 17:00–19:00 zeigen — vermutlich "
            "steht dort 17:00–20:00, also die neue Alarm-Obergrenze."
        )


def test_ac12_nachtblock_beginnt_weiterhin_zur_ankunftsstunde():
    """AC-12: Der Nacht-Block beginnt zur bisherigen Ankunftsstunde 19. Beweis
    ueber den Kaelte-Marker, der ausschliesslich dort liegt: beginnt der Block
    erst um 20:00, verschwindet er."""
    plain = _mail(night=True).email_plain
    assert "Nacht am Ziel" in plain, f"Fixture kaputt: kein Nacht-Block.\n{plain}"
    nacht = plain.split("Nacht am Ziel", 1)[1]
    assert "-21" in nacht, (
        "AC-12: Der Nacht-Block enthaelt die Ankunftsstunde 19 nicht mehr "
        f"(Kaelte-Marker -21 °C fehlt) — er beginnt eine Stunde spaeter.\n{nacht}"
    )


def test_ac13_ankunftszeile_in_mail_bleibt_unveraendert():
    """AC-13: Die 'Ankunft'-Zeile in HTML und Plain zeigt denselben Wert."""
    report = _mail(night=True)
    for name, text in (("Plain", report.email_plain), ("HTML", report.email_html)):
        assert "Ankunft 19:00 → Morgen 06:00" in text, (
            f"AC-13 ({name}): Die Ankunft-Zeile folgt dem Ziel-Segment-Ende und "
            "ist mit der neuen Alarm-Obergrenze auf 20:00 gewandert."
        )


class _NachtfensterProvider:
    """Echter (Nicht-Mock) Provider-Stellvertreter: liefert stundenweise Punkte
    fuer GENAU das angefragte Fenster — so verhaelt sich auch open-meteo, das
    nur die erfragte Zeitspanne zurueckgibt. Kein Netz, kein ``Mock``/``patch``.

    Der Kaelte-Marker liegt ausschliesslich in der Ankunftsstunde 19: wird das
    Nachtfenster eine Stunde spaeter angefragt, ist er in den Daten schlicht
    nicht enthalten. Eigener ``name``, damit der prozessweite Wetter-Cache
    (Schluessel enthaelt die Modellkennung, die hier auf den Providernamen
    zurueckfaellt) diesen Abruf nicht mit dem eines anderen Tests verwechselt.
    """

    name = "nachtfenster-1599"

    def __init__(self) -> None:
        self.angefragt: list[datetime] = []

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble=True, enrich_snow=True):
        self.angefragt.append(start)
        punkte = []
        lauf = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        while lauf < end:
            punkte.append(ForecastDataPoint(
                ts=lauf, t2m_c=MARKE_NACHT if lauf.hour == 19 else 5.0,
                wind10m_kmh=5.0, gust_kmh=8.0, precip_1h_mm=0.0))
            lauf += timedelta(hours=1)
        return NormalizedTimeseries(meta=_meta(), data=punkte)


def test_ac12b_nachtabruf_holt_die_ankunftsstunde_wirklich_ab():
    """AC-12 an der WIRKSTELLE (Adversary-Fund F002): ``fetch_night_weather()``
    ist die Stelle, die im Versand- und Vorschau-Pfad die Nacht-Reihe
    tatsaechlich beschafft. Sie muss am ANZEIGE-Ende des Ziel-Segments
    ansetzen (19:00), nicht an dessen seit #1599 eine Stunde spaeterer
    Alarm-Obergrenze (20:00) — sonst fehlt der ersten Zeile der Tabelle
    „Nacht am Ziel" die Datengrundlage.

    ``test_ac12_...`` oben injiziert die Nacht-Reihe als Parameter und ruft
    diese Funktion nie auf; er kann den Abruf-Grenzwert deshalb nicht bewachen.
    Hier laeuft der echte Abruf ueber einen fensterehrlichen Provider, und das
    Ergebnis geht anschliessend durch denselben echten Renderer.
    """
    from services.segment_weather import fetch_night_weather

    segmente = _segmente()
    assert str(segmente[-1].segment.segment_id) == "Ziel", (
        "Fixture kaputt: das letzte Segment ist nicht das Ziel-Segment."
    )
    provider = _NachtfensterProvider()

    reihe = fetch_night_weather(segmente[-1], provider=provider)

    assert provider.angefragt, (
        "Der Provider wurde nicht gefragt — der Abruf-Grenzwert waere ungeprueft."
    )
    assert provider.angefragt[0].astimezone(timezone.utc).hour == 19, (
        "AC-12b: Der Nachtabruf beginnt um "
        f"{provider.angefragt[0]} statt zur Ankunftsstunde 19:00 — der Fetch "
        "folgt der neuen Alarm-Obergrenze statt dem Anzeige-Ende."
    )
    assert reihe is not None and reihe.data, "Kein Nachtabruf zustande gekommen"
    assert reihe.data[0].ts.hour == 19, (
        f"AC-12b: Die Nacht-Reihe beginnt um {reihe.data[0].ts} statt um 19:00."
    )

    plain = TripReportFormatter().format_email(
        segmente, "Anzeige-Invarianz", "evening",
        display_config=build_default_display_config(),
        night_weather=reihe, tz=TZ,
    ).email_plain
    assert "Nacht am Ziel" in plain, f"Fixture kaputt: kein Nacht-Block.\n{plain}"
    nacht = plain.split("Nacht am Ziel", 1)[1]
    assert "-21" in nacht, (
        "AC-12b: Der aus dem ECHTEN Abruf gespeiste Nacht-Block enthaelt die "
        f"Ankunftsstunde 19 nicht (Kaelte-Marker -21 °C fehlt).\n{nacht}"
    )


def test_ac14_telegram_timeline_zeigt_dieselbe_ankunft():
    """AC-14: Die Telegram-``/timeline``-Antwort weist das Tagesziel weiterhin
    mit 19:00 aus, nicht mit der neuen Alarmgrenze."""
    from services.trip_command_processor import TripCommandProcessor
    from services.weather_extractor import WeatherExtractor
    from services.weather_snapshot import WeatherSnapshotService

    user_id = "tdd-1599-timeline"
    WeatherSnapshotService(user_id).save("anzeige-1599", _segmente(), TAG)
    timeline = WeatherExtractor(user_id).timeline("anzeige-1599", TAG)
    text = TripCommandProcessor()._fmt_timeline(
        timeline, TAG, "Anzeige-Invarianz", "heute", TZ)
    assert "🕐 19:00" in text, f"AC-14: 19:00 fehlt in der Timeline:\n{text}"
    assert "🕐 20:00" not in text, (
        f"AC-14: Die Timeline zeigt 20:00 — neue Alarm-Obergrenze sichtbar.\n{text}"
    )


def test_ac15_kachelzeile_sms_und_kurzuebersicht_ohne_20_uhr_wert():
    """AC-15: Mail-Kachelzeile (Teil der gerenderten Mail), SMS-Text und
    Telegram-Kurzuebersicht beziehen keinen 20-Uhr-Wert des Ziel-Segments ein.
    Positivkontrolle: der 19-Uhr-Wert MUSS enthalten sein (Bug #1146,
    ``is_last``) — sonst pruefte der Test nur eine leere Menge."""
    from output.renderers.compact_summary import CompactSummaryFormatter
    from output.renderers.sms_trip import SMSTripFormatter

    segmente = _segmente()
    ausgaben = {
        "Mail (inkl. Kachelzeile)": _mail().email_plain,
        "SMS": SMSTripFormatter().format_sms(segmente, tz=TZ),
        "Telegram-Kurzuebersicht": CompactSummaryFormatter().format_stage_summary(
            segmente, "Tag 1", build_default_display_config(), tz=TZ),
    }
    for name, text in ausgaben.items():
        assert "47" not in text, (
            f"AC-15 ({name}): Der 20-Uhr-Wert des Ziel-Segments (47 °C) "
            f"erscheint in der Ausgabe.\n{text}"
        )
    for name in ("SMS", "Telegram-Kurzuebersicht"):
        assert "33" in ausgaben[name], (
            f"Positivkontrolle ({name}): 19-Uhr-Wert fehlt.\n{ausgaben[name]}"
        )


def test_ac18_glatte_etappengrenze_zaehlt_die_stunde_15_genau_einmal():
    """AC-18: Eine regulaere Etappe, die glatt um 15:00 endet, gibt die Stunde 15
    an das FOLGE-Segment ab (Bug #806/#1146). Wird die Anzeige-Kompensation aus
    #1599 pauschal auf alle Segmente statt nur auf das Ziel-Segment angewandt,
    wird eine Stunde doppelt gezaehlt oder geht verloren.

    ABWEICHUNG (bewusst, gemeldet): gemessen an der geteilten Punktequelle
    ``collect_hiking_window_points()`` statt am gerenderten Text. Kein Kanal gibt
    die ANZAHL preis — Kachelzeile, SMS und Kurzuebersicht zeigen Minimum/Maximum
    und sind gegen eine doppelt gezaehlte Stunde strukturell unempfindlich.

    Gemessen wird die GANZE Gehzeit-Stundenmenge, nicht nur die Grenzstunde 15
    (Adversary-Fund F001): die pauschale Kompensation nimmt jedem NICHT-letzten
    Segment die Stunde VOR seinem Ende (hier 14 und 16) — die Etappengrenze
    selbst bleibt in beiden Welten genau einmal gezaehlt, weil ``h < e_h`` sie
    ohnehin an das Folgesegment abgibt und ``display_end_time()`` die Stunde bei
    einem dann nur noch einstuendigen Fenster gar nicht erst zuruecknimmt. Ein
    Test, der nur die Grenzstunde zaehlt, kann diese Mutation strukturell nicht
    sehen — unabhaengig davon, wie nah die Grenze an der Fenstergrenze liegt.
    """
    from collections import Counter

    from output.renderers.day_window import collect_hiking_window_points

    zaehler = Counter(p.ts.hour for p in collect_hiking_window_points(_segmente()))
    assert zaehler[15] == 1, (
        "AC-18: Die Stunde 15 (glattes Etappenende) muss genau einmal in der "
        f"Gehzeit-Punktemenge stehen, gefunden: {zaehler[15]} (2 = doppelt "
        "gezaehlt, 0 = verloren)."
    )
    # Start 08:00 -> Sattel 15:00 -> Tagesziel 17:00, Ziel-Anzeigeende 19:00
    # (inklusiv, Bug #1146): das Gehzeitfenster ist die luecken- und
    # ueberschneidungsfreie Kette 08..19.
    assert sorted(zaehler.items()) == [(h, 1) for h in range(8, 20)], (
        "AC-18: Das Gehzeitfenster muss die Stunden 08..19 genau einmal "
        f"enthalten, gefunden: {sorted(zaehler.items())}. Fehlende Stunden vor "
        "einer Segmentgrenze bedeuten, dass die Anzeige-Kompensation nicht nur "
        "auf das Ziel-Segment wirkt; eine Stunde 20 bedeutet, dass sie gar "
        "nicht wirkt."
    )
