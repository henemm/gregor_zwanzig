"""#2799 S7a1: Ampel-Listen der Kanaele aus ``AMPEL_LESER`` abgeleitet.

SPEC: docs/specs/modules/feat_2799_s7_ampel_weitere.md, Abschnitt
"Nachtrag Teil S7a1" (verbindlicher Entwurf), AC-18 und AC-22.

Drei Arten von Tests:

(a) Golden-Waechter (AC-22, schon heute gruen und muss es bleiben): die echten
    Renderer erzeugen Trip-Mail (HTML + Klartext), Telegram, SMS und
    Premium-SMS ueber den echten Versandweg (``NotificationService``, einzige
    Naht ist der Transport-Aufzeichner) sowie die Orte-Vergleichsmail (HTML +
    Klartext), Orte-Telegram und Orte-SMS aus einer festen Wetter-Fixture mit
    den S7-Metriken. Die Ausgaben liegen unter ``tests/fixtures/s7a1_ampel/``
    und wurden mit dem Stand VOR S7a1 erzeugt. Neu erzeugen nur bewusst und
    nur, wenn eine Spec die Ausgabe aendert::

        GOLDEN_S7A1_SCHREIBEN=1 uv run pytest tests/tdd/test_2799_s7a1_ampel_ableitung.py -k golden

(b) Nahtstellen-Tests (rot bis S7a1): eine Metrik der Spec wird zur Laufzeit
    in ``app.ampel.AMPEL_LESER`` aufgenommen (Simulation der Aktivierung in
    S7a2, einzige Naht ``monkeypatch.setattr`` auf diese Konstante). Dann
    muessen Pille, Stundentabelle, Orte-Uebersicht und SMS-Kuerzel die Stufe
    aus den echten Vorlagen (``app/ampel_templates.py``) tragen. Telegram liest
    schon heute ueber ``hat_ampel`` und ist die Paritaetsprobe.

(c) Ratsche (rot bis S7a1, ``faerbt_an`` fehlt): je Stelle ist die gefaerbte
    Menge ``AMPEL_LESER`` minus benannter Bestandsausnahme (AC-18).

Kein ``Mock()``/``patch()``/``MagicMock``. Feste Uhr (2026-07-20 04:00 UTC),
feste Zeitzone Europe/Paris.
"""
from __future__ import annotations

import copy
import html as html_mod
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

import app.ampel

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "s7a1_ampel"
GOLDEN_ENV = "GOLDEN_S7A1_SCHREIBEN"

TZ = ZoneInfo("Europe/Paris")
YEAR, MONTH, DAY = 2026, 7, 20
JETZT_UTC = "2026-07-20T04:00:00+00:00"

#: Die vier Metriken, die S7a2 aktiviert (Spec, Lieferplan S7a2).
S7A2_METRIKEN = frozenset({"cloud_total", "cloud_low", "dewpoint", "sunshine"})

#: Bestandsausnahmen je Stelle, von Hand aus dem Nachtrag S7a1 (Punkt 1).
SOLL_AUSNAHMEN = {
    "stundentabelle": frozenset({"wind_chill", "uv_index", "fresh_snow"}),
    "orte_uebersicht": frozenset({"wind_chill", "fresh_snow"}),
    "pille": frozenset(),
    "sms": frozenset(),
}

#: Heute in der Trip-Stundentabelle (Roh-Modus) getoente Metriken (Nachtrag S7a1).
HEUTE_GETOENT_STUNDENTABELLE = frozenset({
    "temperature", "wind", "gust", "precipitation", "rain_probability", "visibility",
})

#: Trip-Grundauswahl der Fixture: S7-Metriken plus die Bestands-Ampelmetriken.
FOLGE = [
    "temperature", "wind_chill", "wind", "gust", "precipitation", "rain_probability",
    "cloud_total", "cloud_low", "dewpoint", "sunshine", "uv_index", "visibility",
    "freezing_level", "snow_depth", "fresh_snow",
]

#: Orte-Uebersicht: Renderer-Kennungen der Zeilen (``CV2_ZEILEN``).
ORTE_ZEILEN = [
    "temp_max", "temp_min", "wind_max", "gust_max", "precip_sum", "pop_max",
    "sunny_hours", "cloud_avg", "cloud_low_avg", "dewpoint_avg", "uv_max",
    "visibility_min", "snow_depth_cm", "snow_new_cm", "freezing_level", "wind_chill_min",
]
ORTE_KANAL_ZEILEN = ["temp_max", "wind_max", "precip_sum", "cloud_avg", "cloud_low_avg",
                     "dewpoint_avg", "sunny_hours"]

# Pillen-Hintergruende je Ton (``helpers._PILL_TAG_PALETTE`` ueber ``_PILL_TONE_MAP``),
# von Hand: neutral -> info, gruen -> ok, gelb -> caution, orange -> warn.
PILLE_BG = {"neutral": "#dde8f3", "ampel_green": "#dcf2e1", "ampel_yellow": "#fdf2c4",
            "ampel_orange": "#fbe0c4", "ampel_red": "#fad3e1"}
# Zell-Toenung je Stufe (``design_tokens._TONE_CSS``), von Hand.
ZELLE_BG = {"yellow": "#fdf4cd", "orange": "#fbe3cc", "red": "#f7d3e2"}


def _aktiviert(monkeypatch, extra=S7A2_METRIKEN) -> None:
    """Simuliert die Aktivierung (S7a2): ``AMPEL_LESER`` zur Laufzeit erweitern."""
    monkeypatch.setattr(app.ampel, "AMPEL_LESER", app.ampel.AMPEL_LESER | frozenset(extra))


# ---------------------------------------------------------------------------
# Wetter-Fixture (deterministisch)
# ---------------------------------------------------------------------------

def _utc(day: int, hour: int) -> datetime:
    return datetime(YEAR, MONTH, day, hour, 0, tzinfo=TZ).astimezone(timezone.utc)


#: Bewoelkung je Ortsstunde: 50 %, nur 9/10/11 Uhr 65/70/65 % -- damit SMS
#: (erste Stunde gelb = 9 Uhr) und Spitze (10 Uhr) unterscheidbar sind.
_WOLKEN = {9: 65, 10: 70, 11: 65}


def _punkt(day: int, hour: int, **extra):
    from app.models import ForecastDataPoint, ThunderLevel

    wolken = _WOLKEN.get(hour, 50)
    werte = dict(
        ts=_utc(day, hour), t2m_c=15.0, wind_chill_c=(-3.0 if hour == 6 else 13.0),
        wind10m_kmh=35.0, gust_kmh=55.0, precip_1h_mm=2.0, pop_pct=60,
        cloud_total_pct=wolken, cloud_low_pct=wolken - 10, cloud_mid_pct=30,
        cloud_high_pct=20, thunder_level=ThunderLevel.NONE, humidity_pct=65,
        dewpoint_c=19.0, pressure_msl_hpa=1013.0, wind_dir_deg=250, visibility_m=8000,
        uv_index=7.0, snow_depth_cm=25, snow_new_24h_cm=6, precip_type="rain",
        freezing_level_m=2300, snowfall_limit_m=2000, wmo_code=61, is_day=1,
        # Sonnenstunden: nur 10 Uhr halbe Stunde (DNI 120 im Band 60..180) -> 0.5 h.
        dni_wm2=(120 if hour == 10 else 0),
    )
    werte.update(extra)
    return ForecastDataPoint(**werte)


def _meta():
    from app.models import ForecastMeta, Provider

    return ForecastMeta(provider=Provider.OPENMETEO, model="test",
                        run=datetime(YEAR, MONTH, DAY, 0, 0, tzinfo=timezone.utc),
                        grid_res_km=1.0, interp="point_grid")


def _segment(stunden=None, **extra):
    from app.models import (
        GPXPoint, NormalizedTimeseries, SegmentWeatherData, SegmentWeatherSummary,
        ThunderLevel, TripSegment,
    )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1400.0, distance_from_start_km=12.0),
        start_time=_utc(DAY, 8), end_time=_utc(DAY, 12),
        duration_hours=4.0, distance_km=12.0, ascent_m=900.0, descent_m=100.0,
    )
    stunden = stunden or {}
    daten = [_punkt(DAY, h, **{**extra, **stunden.get(h, {})}) for h in range(24)]
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=_meta(), data=daten),
        aggregated=SegmentWeatherSummary(
            temp_min_c=15.0, temp_max_c=15.0, temp_avg_c=15.0,
            wind_chill_min_c=-3.0, wind_chill_max_c=13.0, wind_max_kmh=35.0,
            gust_max_kmh=55.0, precip_sum_mm=8.0, pop_max_pct=60, cloud_avg_pct=57,
            thunder_level_max=ThunderLevel.NONE),
        fetched_at=datetime(YEAR, MONTH, DAY, 6, 0, tzinfo=timezone.utc), provider="openmeteo",
    )


def _nacht(stunden=None, **extra):
    from app.models import NormalizedTimeseries

    stunden = stunden or {}
    pts = [_punkt(DAY, h, **{**extra, **stunden.get(h, {})}) for h in range(12, 24)]
    pts += [_punkt(DAY + 1, h, **{**extra, **stunden.get(h, {})}) for h in range(0, 7)]
    return NormalizedTimeseries(meta=_meta(), data=pts)


# ---------------------------------------------------------------------------
# Trip: echter Versandweg
# ---------------------------------------------------------------------------

def _trip_daten(vorlage: str = "allgemein") -> dict:
    """Trip-JSON (Persistenzformat) mit Tabelle "Was steht wo": alle Metriken
    an allen Stellen, Roh-Form in Mail und Telegram; Ampel-Vorlage ``vorlage``."""
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import trip_json

    rows = [{"metric_id": m, "formats": {"email": "raw", "telegram": "raw"}} for m in FOLGE]
    return trip_json(
        FOLGE,
        display={"placements": {"version": 1, "rows": rows, "outlook_reports": []},
                 "ampel": {"template": vorlage}},
        report_config={"send_email": True, "send_sms": True, "send_telegram": True,
                       "send_premium_sms": True},
        trip_id="s7a1-ampel",
    )


def _trip_senden(monkeypatch, daten: dict, *, stunden=None, **wetter) -> dict[str, str]:
    """Ein Abend-Briefing ueber ``NotificationService``; je Kanal der Text.
    ``stunden``: {Ortsstunde: Werte} ueberschreibt ``wetter`` je Stunde."""
    from app.loader import load_trip
    from services.notification_service import NotificationService, TripReportRequest
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV, frisches_profil

    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mit = aufzeichner_installieren(monkeypatch)
    with freeze_time(JETZT_UTC):
        uid = frisches_profil()  # Premium-Rueckadresse relativ zur festen Uhr
        trip = load_trip(copy.deepcopy(daten), user_id=uid)
        assert trip is not None, "Vorbedingung: Trip-JSON laedt"
        rc = trip.report_config
        anfrage = TripReportRequest(
            trip=trip, report_type="evening", segment_weather=[_segment(stunden, **wetter)],
            trip_tz=TZ, night_weather=_nacht(stunden, **wetter), stage_name="E1",
            stage_stats={"distance_km": 12.0, "ascent_m": 900.0, "descent_m": 100.0,
                         "max_elevation_m": 1400},
            report_config=rc, display_config=trip.display_config,
            send_email=rc.send_email, send_sms=rc.send_sms,
            send_telegram=rc.send_telegram, send_premium_sms=rc.send_premium_sms,
        )
        ergebnis = NotificationService(user_id=uid).send_trip_report(anfrage)
    assert ergebnis.sent, f"Vorbedingung: Briefing versendet: {ergebnis}"
    mail = mit.sendungen("email")
    assert len(mail) == 1, f"Vorbedingung: genau eine Mail: {mit!r}"
    aus = {"html": mail[0]["body"], "plain": mail[0]["plain_text_body"]}
    for kanal in ("telegram", "sms", "premium_sms"):
        sendungen = mit.sendungen(kanal)
        assert sendungen, f"Vorbedingung: Kanal {kanal} versendet: {mit!r} / {ergebnis}"
        aus[kanal] = "\n=====\n".join(s["body"] for s in sendungen)
    return {k: v.replace(uid, "<UID>") for k, v in aus.items()}


# ---------------------------------------------------------------------------
# Orte: echte Renderer
# ---------------------------------------------------------------------------

def _orte_ergebnis(**ort_extra):
    from app.user import ComparisonResult, LocationResult, SavedLocation

    orte = []
    for i, name in enumerate(("Kronplatz", "Sulden")):
        ort = SavedLocation(id=f"s7a1-{i}", name=name, lat=46.7 - 0.2 * i, lon=11.9 - 1.3 * i,
                            elevation_m=1500 + 300 * i, timezone="Europe/Vienna")
        stunden = [_punkt(DAY, h) for h in range(8, 17)]
        orte.append(LocationResult(
            location=ort, temp_max=15.0, temp_min=15.0, wind_max=35.0, gust_max=55.0,
            wind_chill_min=-3.0, wind_chill_max=13.0, sunny_hours=0.5, cloud_avg=70,
            cloud_low_avg=60, snow_depth_cm=25, snow_new_cm=6, hourly_data=stunden,
            official_alerts=[], **ort_extra,
        ))
    return ComparisonResult(locations=orte, time_window=(9, 16), target_date=date(YEAR, MONTH, DAY),
                            created_at=datetime(YEAR, MONTH, DAY, 4, 0))


def _orte_preset() -> dict:
    return {"id": "s7a1-preset", "name": "S7a1-Vergleich", "weekday": None,
            "schedule": "daily", "location_ids": ["s7a1-0", "s7a1-1"],
            "profil": "allgemein"}


def _orte_ausgaben() -> dict[str, str]:
    from output.renderers.comparison import (
        render_compare_email, render_compare_sms, render_compare_telegram,
    )

    with freeze_time(JETZT_UTC):
        html, plain = render_compare_email(
            _orte_ergebnis(), enabled_metrics=ORTE_ZEILEN, hourly_metrics=None,
            hourly_enabled=True, preset_name="S7a1-Vergleich", preset=_orte_preset(),
        )
        telegram = render_compare_telegram(_orte_ergebnis(), enabled_metrics=ORTE_KANAL_ZEILEN,
                                           preset_name="S7a1-Vergleich", preset=_orte_preset())
        sms = render_compare_sms(_orte_ergebnis(), enabled_metrics=ORTE_KANAL_ZEILEN,
                                 preset=_orte_preset())
    return {"html": html, "plain": plain, "telegram": telegram, "sms": sms}


# ---------------------------------------------------------------------------
# HTML-Leser
# ---------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    return html_mod.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", fragment))).strip()


_PILLE = re.compile(
    r'<span style="display:inline-block;vertical-align:middle;padding:4px 10px;'
    r'[^"]*background:([^;]+);[^"]*">([^<]*)</span>')


def _pillen(html: str) -> dict[str, str]:
    """{Pillentext: Hintergrund} aller Metrik-Pillen der Trip-Mail."""
    return {html_mod.unescape(t): bg for bg, t in _PILLE.findall(html)}


def _pille(html: str, anfang: str) -> tuple[str, str]:
    treffer = [(t, bg) for t, bg in _pillen(html).items() if t.startswith(anfang)]
    assert len(treffer) == 1, f"Vorbedingung: genau eine Pille '{anfang}…': {_pillen(html)}"
    return treffer[0]


_TD = re.compile(r'<td\b([^>]*)data-label="([^"]+)"[^>]*>(.*?)</td>', re.DOTALL)


def _etappen_zellen(html: str) -> list[dict[str, tuple[str, str | None]]]:
    """Erste Stundentabelle der Etappe (Desktop): je Zeile {Spaltenkopf:
    (Text, Hintergrund oder None)}."""
    tab = re.search(r'<table data-table="resp".*?</table>', html, re.DOTALL)
    assert tab, "Vorbedingung: Etappen-Stundentabelle im HTML-Teil"
    zeilen = []
    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", tab.group(0), re.DOTALL):
        zellen = {}
        for attrs, label, inhalt in _TD.findall(tr):
            bg = re.search(r"background:(#[0-9a-fA-F]{6})", attrs)
            zellen[label] = (_text(inhalt), bg.group(1).lower() if bg else None)
        if "Time" in zellen:
            zeilen.append(zellen)
    assert zeilen, "Vorbedingung: Zeilen in der Etappentabelle"
    return zeilen


def _orte_uebersicht(html: str) -> dict[str, list[str | None]]:
    """Orte-Uebersicht: {Zeilenkopf: [Hintergrund je Ort oder None]}."""
    out: dict[str, list[str | None]] = {}
    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, re.DOTALL):
        tds = re.findall(r"<td\b([^>]*)>(.*?)</td>", tr, re.DOTALL)
        if len(tds) != 3 or "text-align:left" not in tds[0][0]:
            continue
        kopf = _text(tds[0][1])
        bgs = []
        for attrs, _inhalt in tds[1:]:
            bg = re.search(r"background:([^;]+);", attrs)
            wert = bg.group(1).strip().lower() if bg else "transparent"
            bgs.append(None if wert == "transparent" else wert)
        out.setdefault(kopf, bgs)
    return out


def _sms_token(sms: str, kuerzel: str) -> str:
    """Wertteil des Tokens ``kuerzel`` der ersten SMS-Zeile (``CT:SCT@10`` -> ``:SCT@10``)."""
    for tok in sms.split("\n")[0].split():
        m = re.match(rf"^{kuerzel}(?=[-:\d])(.*)$", tok)
        if m:
            return m.group(1)
    raise AssertionError(f"Vorbedingung: Token {kuerzel} in der SMS: {sms!r}")


# ---------------------------------------------------------------------------
# (a) Golden-Waechter AC-22 -- heute gruen, muss gruen bleiben
# ---------------------------------------------------------------------------

def _golden(name: str, ist: str) -> None:
    pfad = GOLDEN_DIR / name
    if os.environ.get(GOLDEN_ENV) == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        pfad.write_text(ist, encoding="utf-8")
    assert pfad.exists(), f"Golden fehlt: {pfad} (mit {GOLDEN_ENV}=1 aus dem Stand vor S7a1 erzeugen)"
    soll = pfad.read_text(encoding="utf-8")
    assert ist == soll, (
        f"AC-22: Ausgabe {name} weicht vom Stand vor S7a1 ab -- S7a1 darf nichts "
        f"Sichtbares aendern (Kanal byte-gleich)")


_TRIP_DATEIEN = {"html": "trip_mail.html", "plain": "trip_mail.txt",
                 "telegram": "trip_telegram.txt", "sms": "trip_sms.txt",
                 "premium_sms": "trip_premium_sms.txt"}
_ORTE_DATEIEN = {"html": "orte_mail.html", "plain": "orte_mail.txt",
                 "telegram": "orte_telegram.txt", "sms": "orte_sms.txt"}


@pytest.mark.parametrize("vorlage", ["allgemein", "alpen-trekking"])
def test_golden_ac22_trip_alle_kanaele_byte_gleich(monkeypatch, vorlage):
    """AC-22: Trip-Mail HTML/Klartext, Telegram, SMS, Premium-SMS unveraendert."""
    aus = _trip_senden(monkeypatch, _trip_daten(vorlage))
    for kanal, datei in _TRIP_DATEIEN.items():
        _golden(f"{vorlage}_{datei}", aus[kanal])


def test_golden_ac22_orte_alle_kanaele_byte_gleich():
    """AC-22: Orte-Vergleichsmail HTML/Klartext, Orte-Telegram, Orte-SMS unveraendert."""
    aus = _orte_ausgaben()
    for kanal, datei in _ORTE_DATEIEN.items():
        _golden(datei, aus[kanal])


def test_golden_fixture_traegt_die_s7_metriken(monkeypatch):
    """Vorbedingung der Golden: die Fixture zeigt die S7-Metriken wirklich
    (sonst waere "byte-gleich" fuer sie ohne Aussage)."""
    aus = _trip_senden(monkeypatch, _trip_daten())
    pillen = _pillen(aus["html"])
    for anfang in ("50–70% bewölkt", "Tiefe Wolken", "Taupunkt", "Sonne"):
        assert any(t.startswith(anfang) for t in pillen), f"Pille '{anfang}' fehlt: {pillen}"
    kopf = _etappen_zellen(aus["html"])[0]
    for label in ("Cloud", "CldLow", "Dew", "Sun", "0°Line", "SnowH", "Feels", "UV", "NewSn"):
        assert label in kopf, f"Spalte {label} fehlt in der Stundentabelle: {sorted(kopf)}"
    for kuerzel in ("CT", "CL", "DP", "W", "G"):
        _sms_token(aus["sms"], kuerzel)
    uebersicht = _orte_uebersicht(_orte_ausgaben()["html"])
    for kopf_ in ("Bewölkung", "Taupunkt", "Sonnenstunden", "Tiefe Wolken"):
        assert any(k.startswith(kopf_) for k in uebersicht), \
            f"Orte-Uebersicht ohne Zeile {kopf_}: {sorted(uebersicht)}"


# ---------------------------------------------------------------------------
# (b) Nahtstellen-Tests -- rot bis S7a1
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("anfang, soll_ton, grund", [
    # allgemein: Bewoelkung oben gelb 60 / orange 85 -> Spitze 70 % = gelb.
    ("50–70% bewölkt", "ampel_yellow", "Bewölkung max 70 % ≥ 60 (gelb, allgemein)"),
    # allgemein: tiefe Wolken oben gelb 50 / orange 80 -> Spitze 60 % = gelb.
    ("Tiefe Wolken", "ampel_yellow", "tiefe Wolken max 60 % ≥ 50 (gelb, allgemein)"),
    # alle Vorlagen: Taupunkt oben gelb 16 / orange 18 -> 19 °C = orange.
    ("Taupunkt", "ampel_orange", "Taupunkt 19 °C ≥ 18 (orange)"),
    # alle Vorlagen: Sonnenstunden unten orange < 1 -> 0.5 h = orange.
    ("Sonne", "ampel_orange", "Sonnenstunden 0.5 h < 1 (orange)"),
])
def test_naht_pille_traegt_ampelstufe_wenn_metrik_aktiviert(monkeypatch, anfang, soll_ton, grund):
    _aktiviert(monkeypatch)
    aus = _trip_senden(monkeypatch, _trip_daten("allgemein"))
    text, bg = _pille(aus["html"], anfang)
    assert bg == PILLE_BG[soll_ton], (
        f"Kanal E-Mail (Pille '{text}'): nach Aufnahme in AMPEL_LESER muss die Pille die "
        f"Ampelstufe {soll_ton} tragen ({grund}), ist aber Hintergrund {bg} "
        f"(neutral = {PILLE_BG['neutral']}) -- Pillen-Zweig fragt faerbt_an('pille', …) nicht")


def test_naht_pille_folgt_der_vorlage_nicht_einer_festen_farbe(monkeypatch):
    """Gegenprobe: Radtour hat Bewoelkung gelb erst ab 80 % -> 70 % ist gruen."""
    _aktiviert(monkeypatch)
    aus = _trip_senden(monkeypatch, _trip_daten("radtour"))
    text, bg = _pille(aus["html"], "50–70% bewölkt")
    assert bg == PILLE_BG["ampel_green"], (
        f"Kanal E-Mail (Pille '{text}', Vorlage radtour, gelb ab 80 %): erwartet gruen, "
        f"ist {bg} -- die Pillenfarbe muss aus der Vorlage kommen")


def test_naht_pille_ohne_aktivierung_neutral(monkeypatch):
    """Gegenprobe (heute gruen): ohne Aufnahme in AMPEL_LESER bleiben die vier
    Pillen neutral (keine sichtbare Aenderung in S7a1)."""
    aus = _trip_senden(monkeypatch, _trip_daten("allgemein"))
    for anfang in ("50–70% bewölkt", "Tiefe Wolken", "Taupunkt", "Sonne"):
        text, bg = _pille(aus["html"], anfang)
        assert bg == PILLE_BG["neutral"], f"Pille '{text}' ohne Aktivierung nicht neutral: {bg}"


def test_naht_stundentabelle_roh_toent_taupunkt_und_bewoelkung(monkeypatch):
    _aktiviert(monkeypatch)
    aus = _trip_senden(monkeypatch, _trip_daten("allgemein"))
    zeilen = _etappen_zellen(aus["html"])
    taupunkt = [(z["Time"][0], z["Dew"]) for z in zeilen]
    assert all(bg == ZELLE_BG["orange"] for _t, (_w, bg) in taupunkt), (
        f"Kanal E-Mail (Stundentabelle, Roh): Taupunkt 19 °C muss nach Aufnahme in "
        f"AMPEL_LESER orange getoent sein ({ZELLE_BG['orange']}), ist {taupunkt} -- "
        f"Rueckfall-Toenung nutzt noch die feste Liste statt faerbt_an('stundentabelle', …)")
    wolken = {z["Time"][0]: z["Cloud"] for z in zeilen}
    assert wolken["10"] == ("70", ZELLE_BG["yellow"]), (
        f"Kanal E-Mail (Stundentabelle, Roh): Bewölkung 70 % um 10 Uhr muss gelb getoent "
        f"sein (allgemein gelb ab 60), ist {wolken['10']}")
    assert wolken["08"] == ("50", None), (
        f"Kanal E-Mail (Stundentabelle): Bewölkung 50 % ist gruen und bleibt ungetoent, "
        f"ist {wolken['08']}")


def test_naht_orte_uebersicht_zeilen_ohne_sev_tragen_stufe(monkeypatch):
    _aktiviert(monkeypatch)
    uebersicht = _orte_uebersicht(_orte_ausgaben()["html"])

    def zeile(anfang):
        treffer = [v for k, v in uebersicht.items() if k.startswith(anfang)]
        assert len(treffer) == 1, f"Vorbedingung: Zeile {anfang}: {sorted(uebersicht)}"
        return treffer[0]

    fehler = []
    for anfang, stufe, grund in [
        ("Bewölkung", "yellow", "70 % ≥ 60"), ("Tiefe Wolken", "yellow", "60 % ≥ 50"),
        ("Taupunkt", "orange", "19 °C ≥ 18"), ("Sonnenstunden", "orange", "0.5 h < 1"),
    ]:
        ist = zeile(anfang)
        if ist != [ZELLE_BG[stufe]] * 2:
            fehler.append(f"{anfang} ({grund}): erwartet {stufe} {ZELLE_BG[stufe]}, ist {ist}")
    assert not fehler, (
        "Kanal E-Mail Orte-Übersicht: Zeilen ohne eigene sev erhalten nach Aufnahme in "
        "AMPEL_LESER keine generische Stufe (faerbt_an('orte_uebersicht', …)):\n"
        + "\n".join(fehler))


def test_naht_orte_uebersicht_bestandsausnahmen_bleiben_ungefaerbt(monkeypatch):
    """Gefuehlte Temperatur und Neuschnee bleiben in der Orte-Uebersicht ohne
    Stufe (Bestandsausnahme), auch wenn sie in ``AMPEL_LESER`` stehen."""
    _aktiviert(monkeypatch)
    uebersicht = _orte_uebersicht(_orte_ausgaben()["html"])
    for anfang in ("Gefühlte Temperatur", "Neuschnee"):
        treffer = [v for k, v in uebersicht.items() if k.startswith(anfang)]
        assert treffer, f"Vorbedingung: Zeile {anfang}: {sorted(uebersicht)}"
        assert treffer[0] == [None, None], f"Bestandsausnahme {anfang} gefaerbt: {treffer[0]}"


@pytest.mark.parametrize("kuerzel, grund", [
    ("CT", "Bewölkung 65 % um 9 Uhr ist die erste gelbe Stunde (allgemein gelb ab 60)"),
    ("CL", "tiefe Wolken 55 % um 9 Uhr ist die erste gelbe Stunde (allgemein gelb ab 50)"),
])
def test_naht_sms_kuerzel_hervorgehoben_wie_wind(monkeypatch, kuerzel, grund):
    _aktiviert(monkeypatch)
    aus = _trip_senden(monkeypatch, _trip_daten("allgemein"))
    for kanal in ("sms", "premium_sms"):
        wert = _sms_token(aus[kanal], kuerzel)
        assert re.search(r"@9(?!\d)", wert), (
            f"Kanal {kanal}: Token {kuerzel}{wert} -- nach Aufnahme in AMPEL_LESER muss die "
            f"Hervorhebung der Ampel folgen ({grund}) wie bei W/G; heute zeigt das Token nur "
            f"die Spitze (AMPEL_METRIK_JE_KUERZEL nicht aus faerbt_an('sms', …) abgeleitet)")


def test_naht_orte_sms_kuerzel_hervorgehoben_wie_wind(monkeypatch):
    """Orte-SMS nutzt dieselbe Token-Zeile (ADR-0125): CT/CL je Ort nach Ampel."""
    _aktiviert(monkeypatch)
    sms = _orte_ausgaben()["sms"]
    for kuerzel in ("CT", "CL"):
        wert = _sms_token(sms, kuerzel)
        assert re.search(r"@9(?!\d)", wert), (
            f"Kanal Orte-SMS: Token {kuerzel}{wert} -- nach Aufnahme in AMPEL_LESER muss die "
            f"erste gelbe Stunde (9 Uhr) hervorgehoben sein wie bei W/G: {sms!r}")


def test_naht_sms_ohne_aktivierung_unveraendert(monkeypatch):
    """Gegenprobe (heute gruen): ohne Aktivierung zeigt CT die Spitze (10 Uhr)."""
    aus = _trip_senden(monkeypatch, _trip_daten("allgemein"))
    assert not re.search(r"@9(?!\d)", _sms_token(aus["sms"], "CT")), aus["sms"]


def test_naht_telegram_paritaet_taupunkt_als_ampelmetrik(monkeypatch):
    """Paritaetsprobe: Telegram liest schon heute ueber ``hat_ampel``; nach
    Aufnahme traegt der Taupunkt (19 °C, orange) die Stunde wie W/G."""
    def dp_zeile(tg: str) -> str:
        z = [l for l in tg.splitlines() if l.startswith("DP ")]
        assert z, f"Vorbedingung: Telegram-Zeile DP: {tg!r}"
        return z[0]

    vorher = dp_zeile(_trip_senden(monkeypatch, _trip_daten("allgemein"))["telegram"])
    _aktiviert(monkeypatch)
    nachher = dp_zeile(_trip_senden(monkeypatch, _trip_daten("allgemein"))["telegram"])
    assert "@" not in vorher, f"Vorbedingung ohne Aktivierung: {vorher!r}"
    assert "@" in nachher, (
        f"Kanal Telegram: Taupunkt 19 °C ist orange, die Zeile muss die Stunde tragen "
        f"wie W/G, ist {nachher!r}")


# ---------------------------------------------------------------------------
# (c) Ratsche AC-18 -- rot bis S7a1 (``faerbt_an`` fehlt)
# ---------------------------------------------------------------------------

STELLEN = ("stundentabelle", "orte_uebersicht", "pille", "sms")


def _alle_metrik_ids() -> list[str]:
    from app.metric_catalog import get_all_metrics

    return [m.id for m in get_all_metrics()]


@pytest.mark.parametrize("stelle", STELLEN)
def test_ratsche_gefaerbt_je_stelle_gleich_leser_minus_ausnahme(stelle):
    from app.ampel import AMPEL_BESTANDSAUSNAHMEN, AMPEL_LESER, faerbt_an

    gefaerbt = {m for m in _alle_metrik_ids() if faerbt_an(stelle, m)}
    assert gefaerbt == set(AMPEL_LESER - AMPEL_BESTANDSAUSNAHMEN[stelle]), (
        f"Stelle {stelle}: gefaerbte Menge {sorted(gefaerbt)} != AMPEL_LESER minus "
        f"Bestandsausnahme {sorted(AMPEL_LESER - AMPEL_BESTANDSAUSNAHMEN[stelle])}")


def test_ratsche_ausnahmen_benannt_und_teilmenge_der_leser():
    from app.ampel import AMPEL_BESTANDSAUSNAHMEN, AMPEL_LESER

    assert set(AMPEL_BESTANDSAUSNAHMEN) == set(STELLEN), sorted(AMPEL_BESTANDSAUSNAHMEN)
    for stelle, ausnahme in AMPEL_BESTANDSAUSNAHMEN.items():
        assert ausnahme <= AMPEL_LESER, f"{stelle}: Ausnahme ausserhalb AMPEL_LESER: {ausnahme - AMPEL_LESER}"
        assert ausnahme == SOLL_AUSNAHMEN[stelle], (
            f"{stelle}: Bestandsausnahme {sorted(ausnahme)} != Nachtrag S7a1 "
            f"{sorted(SOLL_AUSNAHMEN[stelle])}")


def test_ratsche_faerbt_an_liest_leser_zur_laufzeit(monkeypatch):
    from app.ampel import faerbt_an

    assert not any(faerbt_an(s, "cloud_total") for s in STELLEN), "Vorbedingung: heute ungefaerbt"
    _aktiviert(monkeypatch, {"cloud_total"})
    assert all(faerbt_an(s, "cloud_total") for s in STELLEN), (
        "faerbt_an muss AMPEL_LESER beim Aufruf lesen (S7a2 aktiviert nur ueber die Konstante)")


def _getoente_stundenspalten(monkeypatch) -> set[str]:
    """Metriken, deren Spalte in der Trip-Stundentabelle (Roh) getoent ist,
    bei Werten, die in "allgemein" fuer JEDE Metrik gelb oder schlechter sind."""
    from app.metric_catalog import get_all_metrics

    extrem = dict(t2m_c=38.0, wind_chill_c=-25.0, wind10m_kmh=90.0, gust_kmh=110.0,
                  precip_1h_mm=20.0, pop_pct=95, visibility_m=50, uv_index=11.0,
                  snow_new_24h_cm=40, cloud_total_pct=100, cloud_low_pct=100,
                  dewpoint_c=25.0, dni_wm2=0)
    aus = _trip_senden(monkeypatch, _trip_daten("allgemein"), **extrem)
    label_zu_id = {m.col_label: m.id for m in get_all_metrics() if m.col_label}
    getoent = set()
    for zeile in _etappen_zellen(aus["html"]):
        for label, (_w, bg) in zeile.items():
            if bg and label in label_zu_id:
                getoent.add(label_zu_id[label])
    return getoent


def test_ratsche_stundentabelle_heute_getoente_menge(monkeypatch):
    """Waechter (heute gruen): heute getoent sind genau die sechs Bestandsmetriken."""
    assert _getoente_stundenspalten(monkeypatch) == HEUTE_GETOENT_STUNDENTABELLE


def test_ratsche_stundentabelle_toenung_folgt_faerbt_an(monkeypatch):
    """Die gerenderte Toenung der Stundentabelle ist genau ``faerbt_an``."""
    from app.ampel import faerbt_an

    getoent = _getoente_stundenspalten(monkeypatch)
    soll = {m for m in FOLGE if faerbt_an("stundentabelle", m)}
    assert getoent == soll == HEUTE_GETOENT_STUNDENTABELLE, (getoent, soll)


# ---------------------------------------------------------------------------
# (d) Fix-Loop 1 (Adversary F001-F004): Zusicherungen dort pruefen, wo sie wirken
# ---------------------------------------------------------------------------

def test_naht_pille_taupunkt_faerbt_nach_schaerfstem_wert_zeigt_minimum(monkeypatch):
    """F001: die Taupunkt-Pille ZEIGT das Tagesminimum, FAERBT aber nach dem
    schaerfsten Tageswert (Spec Nachtrag S7a1, ``ampel_schaerfe``). Fixture:
    5 °C in allen Stunden, nur 10 Uhr 19 °C -> allgemein oben 16/18/21 ->
    orange; das Minimum 5 °C allein waere gruen."""
    _aktiviert(monkeypatch)
    aus = _trip_senden(monkeypatch, _trip_daten("allgemein"), dewpoint_c=5.0,
                       stunden={10: {"dewpoint_c": 19.0}})
    text, bg = _pille(aus["html"], "Taupunkt")
    assert "5.0" in text and "19" not in text, (
        f"Vorbedingung: die Pille zeigt das Minimum 5.0 °C, ist '{text}'")
    assert bg == PILLE_BG["ampel_orange"], (
        f"Kanal E-Mail (Pille '{text}'): Taupunkt-Spitze 19 °C um 10 Uhr ist orange "
        f"(allgemein oben 18), die Pille muss nach dem schaerfsten Tageswert faerben, "
        f"nicht nach dem angezeigten Minimum 5 °C (gruen); ist {bg}")


def test_stundentabelle_altschluessel_vis_ist_sicht_und_getoent():
    """F002: der Alt-Spaltenschluessel ``"vis"`` (#1927) fuehrt in der
    Roh-Modus-Rueckfall-Toenung zur Sicht -- wie ``"visibility"`` -- und wird
    getoent (Sicht steht in ``AMPEL_LESER`` und ist keine Bestandsausnahme).
    ``"vis"`` kennt der Katalog nicht (``get_metric_by_col_key`` -> KeyError),
    die Zuordnung haengt allein am Alias."""
    from app.metric_catalog import get_metric_by_col_key
    from output.renderers.email.html import _stundentabelle_metrik

    with pytest.raises(KeyError):
        get_metric_by_col_key("vis")
    assert _stundentabelle_metrik("vis") == "visibility", (
        f"Alt-Schluessel 'vis' muss zur Sicht fuehren, ist {_stundentabelle_metrik('vis')!r}")
    assert _stundentabelle_metrik("vis") == _stundentabelle_metrik("visibility")
    assert _stundentabelle_metrik("gibtsnicht") is None


def test_ratsche_faerbt_an_unbekannte_stelle_keyerror():
    """F003: eine unbekannte Stelle ist ein Programmierfehler und scheitert
    laut (Docstring ``faerbt_an``), statt still "faerbt" zu melden. Gilt fuer
    eine Metrik mit Ampel-Leser (fuer Metriken ohne Leser entscheidet
    ``hat_ampel`` vorher: ``False``)."""
    from app.ampel import faerbt_an

    for metrik in ("wind", "visibility"):
        with pytest.raises(KeyError):
            faerbt_an("gibtsnicht", metrik)


def _orte_html_mit_gewitter() -> str:
    """Orte-Vergleichsmail (HTML) mit Gewitter-Zeile; Gewitter MITTEL je Ort."""
    from app.models import ThunderLevel
    from output.renderers.comparison import render_compare_email

    with freeze_time(JETZT_UTC):
        html, _plain = render_compare_email(
            _orte_ergebnis(thunder_level_max=ThunderLevel.MED),
            enabled_metrics=ORTE_ZEILEN + ["thunder_max", "wind_direction_avg"],
            hourly_metrics=None, hourly_enabled=True, preset_name="S7a1-Vergleich",
            preset=_orte_preset(),
        )
    return html


def test_naht_orte_uebersicht_eigene_sev_wird_nicht_ueberschrieben(monkeypatch):
    """F004: Zeilen mit eigener "sev"/"sev_loc" behalten sie auch, wenn ihre
    Metrik in ``AMPEL_LESER`` steht. Beobachtbar ist das an der Gewitter-Zeile:
    die eigene ``_sev_thunder`` faerbt "mittel" orange, die generische
    ``severity_for("thunder", …)`` liefert ``None`` (keine Toenung). Zusaetzlich
    muessen ALLE Zeilen mit eigener sev unter Aktivierung byte-gleich zum Stand
    ohne Aktivierung bleiben."""
    from output.renderers.email.compare_html import CV2_ZEILEN

    vorher = _orte_uebersicht(_orte_html_mit_gewitter())
    gewitter = [v for k, v in vorher.items() if k.startswith("Gewitter")]
    assert gewitter == [[ZELLE_BG["orange"]] * 2], (
        f"Vorbedingung: Gewitter mittel ist ohne Aktivierung orange: {gewitter} / {sorted(vorher)}")

    eigene = {z["metric_id"] for z in CV2_ZEILEN if "sev" in z or "sev_loc" in z}
    assert {"thunder", "wind_direction"} <= eigene, sorted(eigene)
    _aktiviert(monkeypatch, S7A2_METRIKEN | eigene)
    nachher = _orte_uebersicht(_orte_html_mit_gewitter())
    gewitter_n = [v for k, v in nachher.items() if k.startswith("Gewitter")]
    assert gewitter_n == gewitter, (
        f"Kanal E-Mail Orte-Übersicht: Gewitter-Zeile hat eigene sev und darf durch die "
        f"generische Stufe nicht ueberschrieben werden; vorher {gewitter}, nach "
        f"Aufnahme in AMPEL_LESER {gewitter_n}")
    s7_koepfe = ("Bewölkung", "Tiefe Wolken", "Taupunkt", "Sonnenstunden")
    unveraendert = {k: v for k, v in vorher.items() if not k.startswith(s7_koepfe)}
    assert {k: nachher.get(k) for k in unveraendert} == unveraendert, (
        "Kanal E-Mail Orte-Übersicht: Zeilen mit eigener sev aendern sich durch die "
        "Aktivierung (generische Stufe ueberschreibt eigene)")
