"""TDD RED — Epic #2133 ("jede Metrik, ab jetzt, auf jedem Kanal") durch den
echten Kanal-Eingang (#2417 AC-30, AC-31, AC-33).

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md
FUNDAMENT: tests/tdd/_befehl_e2e_fixtures.py

Epic #2133 gilt als geschlossen (S1 #2134, S2 #2185/#2186, S3 #2168/#2126,
S4 #2184, S5 #2207) — dieser Testfall prueft seine Zusagen ein zweites Mal,
diesmal durch den ECHTEN Eingang aller drei Kanaele statt durch einen
direkten Aufruf von ``TripCommandProcessor.process()`` (Vorbild fuer LETZTERES:
``tests/helpers/adhoc_metrik_fixtures.py``). Ein Prozessor-Test kann nicht
zeigen, ob ein Bug im READER (Zielaufloesung, Betreffparsing) die Zusage
unterwegs entwertet — genau das ist der Anlass von #2417.

===========================================================================
Lagen-Wahl je AC (Begruendung)
===========================================================================

AC-30 verlangt woertlich den PO-Lage-Nutzer (1 Trip + mehrere aktive
Vergleiche) — dort bleibt es. Das bedeutet aber: der READER-Fix aus #2417
selbst (U1, Reader routet metrikfoermige Woerter ohne Namen erst NACH dieser
Spec zuverlaessig an den einzigen aktiven Trip) ist eine VORAUSSETZUNG dafuer,
dass Telegram/Premium-SMS in der PO-Lage ueberhaupt etwas ueber Epic #2133
aussagen koennen. Vor diesem Fix antworten beide Kanaele auf JEDES Wort ohne
Namen mit der Mehrdeutigkeits-Rueckfrage (alte AC-4 aus #2282) — das ist ein
U1-Befund, kein #2133-Befund. Die E-Mail-Faelle sind davon nicht betroffen
(dort bestimmt der ``[Name]`` im Betreff das Ziel bereits eindeutig) und
liefern deshalb schon vor dem Reader-Fix eine echte #2133-Aussage.

AC-31/AC-33 verlangen keine PO-Lage — hier wird bewusst L2 (1 Trip, 0
Vergleiche) verwendet, um die #2133-Zusage unabhaengig vom U1-Befund messen
zu koennen.

===========================================================================
"Deutsches Katalogwort" vs. Kuerzel (AC-30)
===========================================================================

``metric_command_words()`` (app/metric_catalog.py) kennt genau zwei
Schreibweisen je Groesse: die Tabellenueberschrift ``col_label`` (die vom
Team-Lead-Briefing und von Spec #2134 "das Abrufwort" genannte Form — trotz
teils englischer Woerter wie "Temp"/"Wind") und das SMS-Kuerzel
``sms_code``. Eine dritte, tatsaechlich deutsche Form (``label_de``, z.B.
"Tiefe Wolken") ist im Abrufvokabular NICHT vorgesehen (Spec #2134, Abschnitt
"Metrik-Abrufwoerter werden abgeleitet") und wird hier deshalb NICHT
gesendet — nur als erwartetes Merkmal in der Antwort geprueft. Beide
gesendeten Formen kommen direkt aus ``get_all_metrics()``, keine Handliste.
"""
from __future__ import annotations

import email as email_lib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest
from freezegun import freeze_time

from app.loader import save_trip
from app.metric_catalog import get_all_metrics, get_metric
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from output.metric_format import format_value

from tests.tdd._befehl_e2e_fixtures import (
    FEHLERTEXTE,
    INNSBRUCK_LAT,
    INNSBRUCK_LON,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    lege_po_lage_nutzer_an,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden


# ---------------------------------------------------------------------------
# Kanal-Matrix (identisch fuer alle drei ACs dieser Datei)
# ---------------------------------------------------------------------------

CHANNEL_MATRIX = [
    ("telegram", None),
    ("premium_sms", None),
    ("email", "plain"),
    ("email", "alternative_beide"),
    ("email", "apple_html"),
]
CHANNEL_IDS = [
    "telegram", "premium_sms", "email_plain", "email_alternative_beide", "email_apple_html",
]


def _sende(kanal: str, mail_form: Optional[str], settings, recorder, nutzer, text: str) -> None:
    if kanal == "telegram":
        sende_telegram_text(settings, nutzer, text)
    elif kanal == "premium_sms":
        sende_premium_sms(settings, recorder, nutzer, text)
    elif kanal == "email":
        sende_email(settings, nutzer, text, form=mail_form)
    else:
        raise ValueError(kanal)


def _email_text(raw: str) -> str:
    msg = email_lib.message_from_string(raw)
    subject = msg.get("Subject", "")
    if msg.is_multipart():
        teile = [
            p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", errors="replace")
            for p in msg.walk() if p.get_content_type() == "text/plain"
        ]
    else:
        teile = [
            msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")
        ]
    return subject + "\n" + "\n".join(teile)


def _text(kanal: str, recorder, nutzer) -> str:
    """Der tatsaechlich gesendete Text, GEJOINT ueber ALLE an ``nutzer``
    gerichteten Sends dieses Kanals (nicht nur den letzten) -- ein Befehl kann
    MEHRERE Nachrichten ausloesen (z.B. "heute": eine Bestaetigung PLUS das
    eigentliche On-Demand-Briefing als zweite Telegram-Nachricht, Vorbild
    ``test_l2_heute_per_telegram_text_liefert_das_briefing`` im Geruest).
    Zusaetzlich nach Empfaenger gefiltert, damit zwei in einem Testfall
    verwendete Nutzer sich einen Recorder teilen koennen, ohne sich
    gegenseitig zu verfaelschen."""
    if kanal == "telegram":
        inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
        assert inhalte, f"Kein Telegram-Inhalt gesendet: {recorder.telegram!r}"
        return "\n".join(e["payload"].get("text", "") for e in inhalte)
    if kanal == "premium_sms":
        eintraege = [e for e in recorder.premium_sms_out if e["to"] == nutzer.premium_sms_reply_to]
        assert eintraege, f"Keine Premium-SMS an {nutzer.premium_sms_reply_to} gesendet."
        return "\n".join(e["text"] for e in eintraege)
    if kanal == "email":
        eintraege = [e for e in recorder.emails if nutzer.mail_to in e["to"]]
        assert eintraege, f"Keine Antwortmail an {nutzer.mail_to} gesendet."
        return "\n".join(_email_text(e["raw"]) for e in eintraege)
    raise ValueError(kanal)


# ---------------------------------------------------------------------------
# Snapshot-Aufbau — echter Stunden-Snapshot ueber WeatherSnapshotService,
# Vorbild tests/helpers/adhoc_metrik_fixtures.py._segmente
# ---------------------------------------------------------------------------

def _speichere_snapshot(trip_id: str, user_id: str, punkte: list[ForecastDataPoint]) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    ab, bis = punkte[0].ts, punkte[-1].ts
    segment = TripSegment(
        segment_id="seg-2417",
        start_point=GPXPoint(lat=INNSBRUCK_LAT, lon=INNSBRUCK_LON, elevation_m=600),
        end_point=GPXPoint(lat=INNSBRUCK_LAT + 0.02, lon=INNSBRUCK_LON + 0.02, elevation_m=900),
        start_time=ab, end_time=bis,
        duration_hours=max((bis - ab).total_seconds() / 3600.0, 1.0),
        distance_km=10.0, ascent_m=300.0, descent_m=300.0,
    )
    daten = [SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=0.0),
            data=punkte,
        ),
        aggregated=SegmentWeatherSummary(
            temp_min_c=-10.0, temp_max_c=35.0, thunder_level_max=ThunderLevel.MED,
            wind_max_kmh=40.0, precip_sum_mm=5.0, pop_max_pct=60,
        ),
        fetched_at=ab, provider=Provider.OPENMETEO.value,
    )]
    WeatherSnapshotService(user_id).save(trip_id, daten, ab.date())


#: Ein Wert je Stundenfeld, das mindestens eine waehlbare Groesse fuehrt.
#: Konstant ueber alle Stunden -- AC-30 prueft NUR, ob die richtige Groesse
#: mit der richtigen Einheit ankommt, nicht ihren zeitlichen Verlauf (das ist
#: Gegenstand von AC-31, s.u.).
STANDARD_STUNDENWERT: dict = dict(
    t2m_c=12.0, wind10m_kmh=18.0, wind_direction_deg=225, gust_kmh=30.0,
    precip_1h_mm=0.4, pop_pct=40, thunder_level=ThunderLevel.MED,
    pressure_msl_hpa=1013.0, humidity_pct=55, dewpoint_c=6.0, uv_index=4.0,
    snow_depth_cm=12.0, snow_new_24h_cm=2.0, snowfall_limit_m=1800,
    freezing_level_m=2200, wind_chill_c=9.0, visibility_m=8000,
    cloud_total_pct=60, cloud_low_pct=40, cloud_mid_pct=20, cloud_high_pct=10,
    dni_wm2=120.0,
)


def _standard_punkte(anzahl: int = 24) -> list[ForecastDataPoint]:
    ab = datetime.now(timezone.utc)
    return [
        ForecastDataPoint(ts=ab + timedelta(hours=i), **STANDARD_STUNDENWERT)
        for i in range(anzahl)
    ]


def _mit_eingeschraenkter_auswahl(nutzer) -> None:
    """Trip-Metrikauswahl auf EINE Groesse verengt (Spec-Klausel "unabhaengig
    von der Metrikauswahl des Trips", AC-30) -- der Ad-hoc-Abruf einer
    ANDEREN Groesse muss trotzdem den vollen Wert liefern."""
    trip = nutzer.trip
    trip.display_config = UnifiedWeatherDisplayConfig(
        trip_id=trip.id, metrics=[MetricConfig(metric_id="temperature", enabled=True)],
    )
    save_trip(trip, nutzer.user_id)


# ---------------------------------------------------------------------------
# AC-30 — jede waehlbare Groesse, beide Schreibweisen, alle drei Kanaele
# ---------------------------------------------------------------------------

def _metrik_wortformen() -> list[tuple]:
    """(metric, wort, formname) je Katalog-Groesse -- ``col_label`` immer,
    ``sms_code`` zusaetzlich wenn nicht leer. Quelle ausschliesslich
    ``get_all_metrics()``, keine Handliste (AC-30-Vollstaendigkeitspflicht)."""
    faelle = []
    for metric in get_all_metrics():
        faelle.append((metric, metric.col_label, "col_label"))
        if metric.sms_code:
            faelle.append((metric, metric.sms_code, "sms_code"))
    return faelle


def _id(fall) -> str:
    metric, _wort, form = fall
    return f"{metric.id}_{form}"


METRIK_FAELLE = _metrik_wortformen()

#: Der Nebelfall aus dem Epic ("ist es neblig?" beantwortet niemand direkt --
#: nur ueber Wolken bzw. Sichtweite) als benannter Einzelfall (AC-30, letzter
#: Satz). Beide Groessen stecken bereits in METRIK_FAELLE; diese Teilmenge
#: macht sie zusaetzlich EINZELN sichtbar und nachverfolgbar.
NEBELFALL_METRIK_IDS = {"cloud_total", "visibility"}
NEBELFALL_FAELLE = [f for f in METRIK_FAELLE if f[0].id in NEBELFALL_METRIK_IDS]

#: dp_fields, deren Formatierer KEINE Zahl+Einheit ausgibt (belegt in
#: ``trip_command_processor._metric_formatter``): Windrichtung wird als
#: Himmelsrichtungs-Kuerzel dargestellt, Niederschlagsart als Wortname.
_OHNE_EINHEITEN_PRUEFUNG = {"wind_direction_deg", "precip_type"}


def _erwartete_einheit(metric) -> Optional[str]:
    if metric.is_level or metric.dp_field in _OHNE_EINHEITEN_PRUEFUNG:
        return None
    return metric.display_unit or metric.unit or None


def _pruefe_metrik_antwort(kanal: str, text: str, metric) -> None:
    for fehler in FEHLERTEXTE:
        assert fehler not in text, (
            f"[{kanal}] Antwort auf {metric.id!r} traegt den Fehlertext "
            f"{fehler!r} statt eines Wertes: {text!r}"
        )
    assert "no data" not in text and "nicht verfügbar" not in text, (
        f"[{kanal}] Antwort auf {metric.id!r} meldet 'keine Daten', obwohl "
        f"der Snapshot dafuer einen Wert traegt: {text!r}"
    )
    if kanal == "premium_sms":
        kuerzel = metric.sms_code or metric.col_label
        assert kuerzel in text, (
            f"[premium_sms] Antwort auf {metric.id!r} nennt nicht ihr "
            f"Kuerzel {kuerzel!r}: {text!r}"
        )
        return
    assert metric.label_de in text, (
        f"[{kanal}] Antwort nennt nicht {metric.label_de!r} (Groesse "
        f"{metric.id!r}): {text!r}"
    )
    einheit = _erwartete_einheit(metric)
    if einheit:
        muster = re.compile(r"[-+]?\d[\d.,]*\s?" + re.escape(einheit))
        assert muster.search(text), (
            f"[{kanal}] Antwort enthaelt keinen Zahlenwert mit der "
            f"Katalog-Einheit {einheit!r} fuer {metric.id!r}: {text!r}"
        )


def _pruefe_einen_metrik_fall(monkeypatch, user_ids, kanal, mail_form, fall) -> None:
    metric, wort, _form = fall
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    _mit_eingeschraenkter_auswahl(nutzer)
    _speichere_snapshot(nutzer.trip.id, nutzer.user_id, _standard_punkte())
    settings = basis_settings()

    _sende(kanal, mail_form, settings, recorder, nutzer, wort)

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _text(kanal, recorder, nutzer)
    _pruefe_metrik_antwort(kanal, text, metric)


@pytest.mark.parametrize("kanal,mail_form", CHANNEL_MATRIX, ids=CHANNEL_IDS)
@pytest.mark.parametrize("fall", METRIK_FAELLE, ids=_id)
def test_jede_waehlbare_groesse_liefert_ihren_eigenen_verlauf(monkeypatch, user_ids, kanal, mail_form, fall):
    """AC-30: jede waehlbare Wetter-Groesse aus ``get_all_metrics()``, in
    beiden Schreibweisen, ueber alle drei Kanaele — unabhaengig von der
    Metrikauswahl des Trips."""
    _pruefe_einen_metrik_fall(monkeypatch, user_ids, kanal, mail_form, fall)


@pytest.mark.parametrize("kanal,mail_form", CHANNEL_MATRIX, ids=CHANNEL_IDS)
@pytest.mark.parametrize("fall", NEBELFALL_FAELLE, ids=_id)
def test_nebelfall_wolken_und_sicht_als_benannter_einzelfall(monkeypatch, user_ids, kanal, mail_form, fall):
    """AC-30, benannter Einzelfall: "ist es neblig?" wird nur ueber Wolken
    bzw. Sichtweite beantwortet, nicht ueber eine eigene Nebel-Groesse."""
    _pruefe_einen_metrik_fall(monkeypatch, user_ids, kanal, mail_form, fall)


# ---------------------------------------------------------------------------
# AC-31 — "ab jetzt": keine vergangenen Stunden, Premium-SMS in Wechselpunkten
# ---------------------------------------------------------------------------

#: 25.09.2026 13:00 UTC == 15:00 Europe/Vienna (CEST) -- Innsbruck-Fixture.
FROZEN_UHR = datetime(2026, 9, 25, 13, 0, tzinfo=timezone.utc)

TEMP_FRUEH_C = -8.0
TEMP_SPAET_C = 31.0
PRECIP_FRUEH_MM = 0.4
PRECIP_SPAET_MM = 3.3


def _ab_jetzt_punkte() -> list[ForecastDataPoint]:
    """Stundenpunkte ab deutlich VOR der eingefrorenen Uhr bis danach, mit
    klar unterscheidbaren Vormittags-/Nachmittagswerten (Vorbild
    ``test_adhoc_tageswert_ab_anfragezeit.py``: binaer eindeutig
    unterscheidbare Zahlen statt toleranzbehafteter Vergleiche)."""
    start = FROZEN_UHR - timedelta(hours=8)
    punkte = []
    for i in range(20):
        ts = start + timedelta(hours=i)
        vormittag = ts < FROZEN_UHR
        punkte.append(ForecastDataPoint(
            ts=ts,
            t2m_c=TEMP_FRUEH_C if vormittag else TEMP_SPAET_C,
            precip_1h_mm=PRECIP_FRUEH_MM if vormittag else PRECIP_SPAET_MM,
        ))
    return punkte


def test_ab_jetzt_telegram_zeigt_keine_vergangenen_stunden(monkeypatch, user_ids):
    """AC-31 (Telegram-Teil): ein Metrik-Abruf am Nachmittag beginnt bei der
    aktuellen Stunde -- der bereits vergangene Vormittag darf nicht mehr
    auftauchen (Zusage S2/#2186), gemessen durch den echten Telegram-Text-
    Eingang statt durch einen direkten Prozessor-Aufruf."""
    recorder = install_transport_fakes(monkeypatch)
    with freeze_time(FROZEN_UHR):
        nutzer = lege_lage_an(user_ids, "L2")
        _speichere_snapshot(nutzer.trip.id, nutzer.user_id, _ab_jetzt_punkte())
        settings = basis_settings()
        sende_telegram_text(settings, nutzer, "temp")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _text("telegram", recorder, nutzer)
    frueh_wert = format_value("temperature", TEMP_FRUEH_C)
    spaet_wert = format_value("temperature", TEMP_SPAET_C)
    assert spaet_wert in text, (
        f"Der Nachmittagswert {spaet_wert!r} fehlt im gesendeten Verlauf: {text!r}"
    )
    assert frueh_wert not in text, (
        f"Der bereits vergangene Vormittagswert {frueh_wert!r} taucht trotzdem "
        f"auf -- 'ab jetzt' (#2186) traegt nicht durch den echten Eingang: {text!r}"
    )


def test_ab_jetzt_premium_sms_zeigt_wechselpunkte_ohne_vergangenheit(monkeypatch, user_ids):
    """AC-31 (Premium-SMS-Teil): dieselbe 'ab jetzt'-Zusage PLUS die
    Kurzform-Zusage aus S5/#2207 -- Wechselpunkte mit Katalog-Kuerzel
    (``Kuerzel@Stunde``) statt einer Stundentabelle."""
    recorder = install_transport_fakes(monkeypatch)
    with freeze_time(FROZEN_UHR):
        nutzer = lege_lage_an(user_ids, "L2")
        _speichere_snapshot(nutzer.trip.id, nutzer.user_id, _ab_jetzt_punkte())
        settings = basis_settings()
        sende_premium_sms(settings, recorder, nutzer, "rain")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _text("premium_sms", recorder, nutzer)
    metric = get_metric("precipitation")
    kuerzel = metric.sms_code or metric.col_label
    frueh_wert = format_value("precipitation", PRECIP_FRUEH_MM, style="bare")
    spaet_wert = format_value("precipitation", PRECIP_SPAET_MM, style="bare")
    assert kuerzel in text, f"Kurzform nennt nicht ihr Kuerzel {kuerzel!r}: {text!r}"
    assert "@" in text, f"Kurzform traegt keinen Wechselpunkt-Zeitmarker '@...': {text!r}"
    assert spaet_wert in text, f"Nachmittagswert {spaet_wert!r} fehlt: {text!r}"
    assert frueh_wert not in text, (
        f"Bereits vergangener Vormittagswert {frueh_wert!r} taucht in der "
        f"Kurzform trotzdem auf: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-31 (Nachtrag) — "heute" (volles Briefing statt Metrik-Abruf)
# ---------------------------------------------------------------------------
#
# AC-31 nennt woertlich "eine Groesse ODER `heute`". Der volle "heute"-Pfad
# laeuft NICHT ueber den Snapshot-Cache (``WeatherSnapshotService``), den die
# obigen Metrik-Abruf-Tests fuellen: ``_trigger_on_demand`` ->
# ``TripReportSchedulerService.send_on_demand_report`` holt sein Wetter
# IMMER frisch ueber ``_fetch_weather`` -> den Provider (``FixtureProvider``,
# von ``tests/conftest.py`` erzwungen). Steuerbar ist das deshalb nur ueber
# die Fixture-DATEI selbst (``GZ_TEST_FIXTURE_DIR``), nicht ueber den
# Snapshot-Service -- ein eigener Weg gegenueber den Metrik-Abruf-Tests oben,
# aber derselbe Netzrand-Grundsatz (Datensubstitution an der bereits vom
# Projekt sanktionierten Stelle, kein Mock der Rendering-Logik).

_INNSBRUCK_FIXTURE_QUELLE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo" / "innsbruck.json"
)


def _fixture_dir_mit_ab_jetzt_werten(
    tmp_path: Path, *, frueh: dict, spaet: dict, grenz_index: int = 13,
) -> Path:
    """Kopie der Innsbruck-Fixture, deren Punkte VOR ``grenz_index`` (=
    Stunde 13 UTC == der eingefrorenen ``FROZEN_UHR``) das ``frueh``-Profil
    tragen, ab da das ``spaet``-Profil -- ``FixtureProvider`` stempelt Punkt
    ``i`` immer auf ``heutige_utc_mitternacht + i Stunden`` (Index-basiert,
    ``ts``-Feld der Quelldatei wird ignoriert)."""
    original = json.loads(_INNSBRUCK_FIXTURE_QUELLE.read_text())
    punkte = []
    for i, basis in enumerate(original["data"]):
        werte = dict(basis)
        werte.update(spaet if i >= grenz_index else frueh)
        punkte.append(werte)
    ziel_dir = tmp_path / "fixture_ab_jetzt"
    ziel_dir.mkdir()
    (ziel_dir / "innsbruck.json").write_text(json.dumps({"data": punkte}))
    return ziel_dir


#: Wind statt/zusaetzlich zu Temperatur als Signal fuer die Kurzform-Tests:
#: die Kurzuebersicht (``SMSTripFormatter``) laesst Temperatur unter meinen
#: Testwerten ganz weg (s. Testlauf-Befund), Wind (``W<Zahl>``) erscheint
#: dagegen zuverlaessig. Extreme, sich nicht ueberschneidende Ganzzahlen.
WIND_FRUEH_KMH = 3
WIND_SPAET_KMH = 97


def test_ac31_heute_telegram_normalstil_zeigt_keine_vergangenen_stunden(monkeypatch, user_ids, tmp_path):
    """AC-31, Telegram-Normalstil: das VOLLE 'heute'-Briefing (nicht nur ein
    Metrik-Abruf) soll bei der aktuellen Stunde beginnen -- der Vormittag
    darf im Stundenverlauf/Tageswert nicht mehr auftauchen.

    Format-Hinweis: dieser Pfad rendert NICHT ueber ``format_value()``
    (kein "31°C"), sondern ueber einen eigenen Tabellen-/Kurzuebersicht-
    Renderer mit rohen Dezimalzahlen ("31.0") -- deshalb roher Zahlen-
    vergleich statt Katalog-Formatierung."""
    recorder = install_transport_fakes(monkeypatch)
    fixture_dir = _fixture_dir_mit_ab_jetzt_werten(
        tmp_path, frueh={"t2m_c": TEMP_FRUEH_C}, spaet={"t2m_c": TEMP_SPAET_C},
    )
    with freeze_time(FROZEN_UHR):
        nutzer = lege_lage_an(user_ids, "L2")
        monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(fixture_dir))
        settings = basis_settings()
        sende_telegram_text(settings, nutzer, "heute")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _text("telegram", recorder, nutzer)
    assert str(TEMP_SPAET_C) in text, (
        f"Nachmittagswert {TEMP_SPAET_C!r} fehlt im vollen 'heute'-Briefing (Telegram): {text!r}"
    )
    assert str(TEMP_FRUEH_C) not in text, (
        f"Der bereits vergangene Vormittagswert {TEMP_FRUEH_C!r} taucht im vollen "
        f"'heute'-Briefing (Telegram Normalstil) trotzdem auf: {text!r}"
    )


def test_ac31_heute_telegram_kurzform_zeigt_keine_vergangenen_stunden(monkeypatch, user_ids, tmp_path):
    """AC-31, Telegram mit ``telegram_style=kurzform``: dieselbe 'ab jetzt'-
    Pruefung, PLUS Beleg, ob der tatsaechlich gesendete Text Wechselpunkte
    mit Katalog-Kuerzel traegt (S5/#2207) oder die aeltere, symbolbasierte
    Tages-SMS-Zusammenfassung (``SMSTripFormatter``) -- diese beiden
    Renderer sind im Code unterschiedliche Pfade, die Spec sagt nicht,
    welcher hier tatsaechlich greift. Temperatur erscheint in dieser
    Kurzuebersicht NICHT (Testlauf-Befund) -- Wind ist das verlaessliche
    Signal."""
    recorder = install_transport_fakes(monkeypatch)
    fixture_dir = _fixture_dir_mit_ab_jetzt_werten(
        tmp_path,
        frueh={"t2m_c": TEMP_FRUEH_C, "wind10m_kmh": WIND_FRUEH_KMH},
        spaet={"t2m_c": TEMP_SPAET_C, "wind10m_kmh": WIND_SPAET_KMH},
    )
    with freeze_time(FROZEN_UHR):
        nutzer = lege_lage_an(user_ids, "L2")
        nutzer.trip.report_config.telegram_style = "kurzform"
        save_trip(nutzer.trip, nutzer.user_id)
        monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(fixture_dir))
        settings = basis_settings()
        sende_telegram_text(settings, nutzer, "heute")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _text("telegram", recorder, nutzer)
    spaet_token = f"W{WIND_SPAET_KMH}"
    frueh_token = f"W{WIND_FRUEH_KMH}"
    assert spaet_token in text, (
        f"Nachmittags-Windwert {spaet_token!r} fehlt im 'heute'-Kurzform-Briefing (Telegram): {text!r}"
    )
    assert frueh_token not in text, (
        f"Der bereits vergangene Vormittags-Windwert {frueh_token!r} taucht im "
        f"'heute'-Kurzform-Briefing (Telegram) trotzdem auf: {text!r}"
    )


def _setze_premium_tier(nutzer) -> None:
    """Read-Modify-Write auf ``user.json``: ``premium_sms_allowed()``
    (ADR-0049) verlangt ``tier == "premium"`` fuer den VOLLEN On-Demand-
    Versand -- anders als bei einer blossen Befehls-ANTWORT (dort prueft
    ``send_command_reply_premium_sms`` diesen Tier NICHT). Das gemeinsame
    Fundament setzt kein ``tier``-Feld; ohne dieses Nachziehen scheitert
    JEDER volle Premium-SMS-Versand strukturell am Tier-Gate, unabhaengig
    von 'ab jetzt' (kein #2417/#2133-Befund, s. Testlauf)."""
    from app.loader import get_data_dir

    pfad = get_data_dir(nutzer.user_id) / "user.json"
    profil = json.loads(pfad.read_text())
    profil["tier"] = "premium"
    pfad.write_text(json.dumps(profil))


def test_ac31_heute_premium_sms_zeigt_keine_vergangenen_stunden(monkeypatch, user_ids, tmp_path):
    """AC-31, Premium-SMS: dieselbe Pruefung wie bei Telegram-Kurzform --
    ``notification_service.py`` sendet fuer BEIDE Kanaele denselben
    ``report.sms_text`` (identischer Renderer, zwei Transportwege)."""
    recorder = install_transport_fakes(monkeypatch)
    fixture_dir = _fixture_dir_mit_ab_jetzt_werten(
        tmp_path,
        frueh={"t2m_c": TEMP_FRUEH_C, "wind10m_kmh": WIND_FRUEH_KMH},
        spaet={"t2m_c": TEMP_SPAET_C, "wind10m_kmh": WIND_SPAET_KMH},
    )
    with freeze_time(FROZEN_UHR):
        nutzer = lege_lage_an(user_ids, "L2")
        _setze_premium_tier(nutzer)
        monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(fixture_dir))
        settings = basis_settings()
        sende_premium_sms(settings, recorder, nutzer, "heute")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _text("premium_sms", recorder, nutzer)
    spaet_token = f"W{WIND_SPAET_KMH}"
    frueh_token = f"W{WIND_FRUEH_KMH}"
    assert spaet_token in text, (
        f"Nachmittags-Windwert {spaet_token!r} fehlt im 'heute'-Briefing (Premium-SMS): {text!r}"
    )
    assert frueh_token not in text, (
        f"Der bereits vergangene Vormittags-Windwert {frueh_token!r} taucht im "
        f"'heute'-Briefing (Premium-SMS) trotzdem auf: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-33 — "gefuehrt heisst nicht gefuellt": fehlende Groesse wird BENANNT
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal,mail_form", CHANNEL_MATRIX, ids=CHANNEL_IDS)
def test_fehlende_groesse_wird_benannt(monkeypatch, user_ids, kanal, mail_form):
    """AC-33: eine im Gebiet nicht gefuehrte Groesse (hier UV-Index -- das
    Snapshot-Feld ``uv_index`` bleibt bei JEDEM Stundenpunkt ``None``) wird
    BENANNT statt zu schweigen, einen Fehler zu werfen oder als
    'Unbekannter Befehl' gemeldet zu werden."""
    metric = get_metric("uv_index")
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    ab = datetime.now(timezone.utc)
    punkte = [ForecastDataPoint(ts=ab + timedelta(hours=i), t2m_c=10.0) for i in range(12)]
    _speichere_snapshot(nutzer.trip.id, nutzer.user_id, punkte)
    settings = basis_settings()

    _sende(kanal, mail_form, settings, recorder, nutzer, metric.sms_code or metric.col_label)

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _text(kanal, recorder, nutzer)
    for unbekannt_marker in ("Unbekannter Befehl", "Befehlsformat: ### key: value"):
        assert unbekannt_marker not in text, (
            f"[{kanal}] Fehlende Groesse wird als unbekannter Befehl "
            f"behandelt statt benannt: {text!r}"
        )
    assert "Mehrdeutig" not in text
    if kanal == "premium_sms":
        assert "no data" in text, f"[premium_sms] Kein Keine-Daten-Hinweis: {text!r}"
        assert (metric.sms_code or metric.col_label) in text, (
            f"[premium_sms] Keine-Daten-Antwort nennt nicht die betroffene "
            f"Groesse: {text!r}"
        )
    else:
        assert metric.label_de in text, (
            f"[{kanal}] Antwort nennt nicht die fehlende Groesse "
            f"{metric.label_de!r}: {text!r}"
        )
        assert "nicht verfügbar" in text or "keine" in text.lower(), (
            f"[{kanal}] Antwort benennt die fehlende Groesse nicht "
            f"ausdruecklich als fehlend: {text!r}"
        )
