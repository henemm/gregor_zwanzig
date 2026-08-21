"""Issue #2030 — Vorhersage-Mitschnitt am Verbrauchspunkt (AC-1..AC-12).

SPEC: docs/specs/modules/feat_2030_vorhersage_mitschnitt.md
Ausfuehrung:
    uv run pytest tests/unit/test_forecast_capture.py -v

Kern-Schicht, netzfrei. KEINE Mocks/patch/MagicMock als Verhaltensnachweis: der
Fake-Provider unten erfuellt das `WeatherProvider`-Protokoll echt, jede Zusicherung
wird an ECHT geschriebenen Dateien unter der isolierten Datenwurzel geprueft
(autouse `_isolate_data_root`, tests/conftest.py:121) und strukturiert als JSONL
geparst — nie per `"xyz" in datei.read_text()`.

Zwei Fallen, gegen die hier bewusst gebaut wird: (1) "es entsteht keine Zeile"
(Kill-Switch, Fail-soft) ist heute trivial wahr, weil es noch gar keinen Mitschnitt
gibt — beide Tests tragen deshalb eine Positivkontrolle im selben Testkoerper;
(2) #1987-Falle: der Prune darf nur datierte `forecast_capture_*`-Tagesdateien
treffen, Nachbardateien und undatierte Namensvettern muessen ueberleben.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from services.segment_weather import SegmentWeatherService
from services.weather_cache import WeatherCacheService

WORKTREE = Path(__file__).resolve().parents[2]

# Fester Uhr-Anker: heutiges Datum, sichere Tagesstunde (weit weg vom Tageswechsel),
# damit Fenster von wenigen Stunden nie ueber Mitternacht laufen und der
# Tagesdatei-Name deterministisch bleibt.
ANKER = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)

# Vertrag der JSONL-Zeile (AC-11): genau diese Schluessel, nicht mehr.
ERWARTETE_SCHLUESSEL = {
    "written_at", "fetched_at", "cache_hit", "grund", "lat", "lon", "segment_id",
    "fenster_start", "fenster_ende", "day_window_start_hour", "day_window_end_hour",
    "provider", "model", "source", "werte",
}
ERWARTETE_WERTE = {
    "precip_sum_mm", "wind_max_kmh", "gust_max_kmh", "thunder_level_max",
    "temp_min_c", "temp_max_c", "pop_max_pct", "cape_max_jkg",
    "snow_new_sum_cm", "snowfall_limit_m",
}


# --- Pruefling, Uhr, Testdaten --------------------------------------------
def _modul():
    """Der Pruefling — aufgeloest RELATIV zu dieser Testdatei (Pfadregel #1409):
    aus einem Worktree darf nie die Hauptrepo-Kopie geprueft werden."""
    from services import forecast_capture

    assert Path(forecast_capture.__file__).resolve().is_relative_to(WORKTREE), \
        f"Pruefling stammt aus einem fremden Checkout: {forecast_capture.__file__}"
    return forecast_capture


def _uhr(monkeypatch, zeitpunkt: datetime):
    """`_utcnow` ist die EINZIGE Uhr-Quelle des Moduls — die Produktion laeuft
    denselben Pfad wie der Test, es gibt keinen `now`-Parameter."""
    modul = _modul()
    monkeypatch.setattr(modul, "_utcnow", lambda: zeitpunkt)
    return modul


class FakeProvider:
    """Zaehlender Fake-Provider (KEIN Mock): liefert wie der reale
    OpenMeteo-Provider einen vollen UTC-Tag mit deterministischen Stundenwerten und
    zaehlt seine Aufrufe — daran wird ein echter Cache-Treffer belegt."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        self.calls += 1
        tagesanfang = (start or ANKER).replace(hour=0, minute=0, second=0, microsecond=0)
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                            grid_res_km=2.2, run=ANKER, interp="grid_point")
        data = [
            ForecastDataPoint(ts=tagesanfang + timedelta(hours=h), t2m_c=float(h),
                              wind10m_kmh=10.0 + h, gust_kmh=20.0 + h,
                              precip_1h_mm=0.5 * h, pop_pct=10 + h, cape_jkg=100.0 * h)
            for h in range(24)
        ]
        return NormalizedTimeseries(meta=meta, data=data)


def _segment(lat: float = 46.6, lon: float = 12.9, start: Optional[datetime] = None,
             stunden: int = 3, segment_id=1) -> TripSegment:
    beginn = start if start is not None else ANKER
    return TripSegment(
        segment_id=segment_id, start_point=GPXPoint(lat, lon, 2000.0),
        end_point=GPXPoint(lat + 0.01, lon + 0.01, 2100.0),
        start_time=beginn, end_time=beginn + timedelta(hours=stunden),
        duration_hours=float(stunden), distance_km=6.0, ascent_m=300.0,
        descent_m=100.0, day_window_start_hour=6, day_window_end_hour=18,
    )


def _aggregat(precip: float = 7.4, **abweichend) -> SegmentWeatherSummary:
    werte = dict(
        precip_sum_mm=precip, wind_max_kmh=30.0, gust_max_kmh=55.0,
        thunder_level_max=ThunderLevel.MED, temp_min_c=4.0, temp_max_c=17.0,
        pop_max_pct=80, cape_max_jkg=900.0, snow_new_sum_cm=0.0, snowfall_limit_m=2900,
    )
    werte.update(abweichend)
    return SegmentWeatherSummary(**werte)


def _mitschnitt(modul, segment=None, aggregat=None, fetched_at=None,
                cache_hit: bool = False, provider: str = "openmeteo",
                model: str = "icon_d2") -> bool:
    return modul.capture_segment_forecast(
        segment=segment if segment is not None else _segment(),
        aggregated=aggregat if aggregat is not None else _aggregat(),
        fetched_at=fetched_at if fetched_at is not None else ANKER - timedelta(minutes=5),
        cache_hit=cache_hit, provider=provider, model=model,
    )


# --- Geschriebene Dateien lesen -------------------------------------------
def _diagnose_ordner(wurzel: Optional[Path] = None) -> Path:
    from app.loader import get_data_root

    return (wurzel if wurzel is not None else get_data_root()) / "diagnostics"


def _datei(zeitpunkt: datetime, wurzel: Optional[Path] = None) -> Path:
    name = f"forecast_capture_{zeitpunkt.date().isoformat()}.jsonl"
    return _diagnose_ordner(wurzel) / name


def _jsonl(pfad: Path) -> list[dict]:
    if not pfad.is_file():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


def _zeilen(zeitpunkt: datetime, wurzel: Optional[Path] = None) -> list[dict]:
    return _jsonl(_datei(zeitpunkt, wurzel))


def _health_meldungen(pfad_wert: str) -> list[dict]:
    """Die TATSAECHLICH geschriebenen `enrichment_calls.jsonl`-Zeilen dieses Pfads
    — echtes Verhalten von `log_enrichment_call`, kein gepatchter Zaehler."""
    zeilen = _jsonl(_diagnose_ordner() / "enrichment_calls.jsonl")
    return [z for z in zeilen if z.get("path") == pfad_wert]


def _ziel_unbeschreibbar_machen(zeitpunkt: datetime) -> Path:
    """Die Zieldatei durch ein VERZEICHNIS ersetzen — `open(..., "a")` scheitert
    dann zuverlaessig, auch als root (anders als `chmod`), waehrend der
    `diagnostics`-Ordner beschreibbar bleibt: die Health-Meldung muss im
    Fehlschlagfall ja noch geschrieben werden koennen."""
    pfad = _datei(zeitpunkt)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if pfad.is_file():
        pfad.unlink()
    pfad.mkdir(exist_ok=True)
    return pfad


@pytest.fixture(autouse=True)
def _sauberer_prozesszustand():
    """Der Mitschnitt haelt prozessweiten Zustand (Dedup-dict, zuletzt gepruntes
    Datum, Health-Drossel) — ohne Raeumung leckt er zwischen Tests. Bewusst
    tolerant gegen einen fehlenden Pruefling, damit im RED-Zustand jeder Test an
    SEINER eigenen Zusicherung scheitert und nicht pauschal am Fixture-Import."""
    try:
        from services import forecast_capture
    except Exception:
        yield
        return
    forecast_capture.reset_capture_state()
    yield
    forecast_capture.reset_capture_state()


@pytest.fixture(params=["GZ_DATA_DIR", "_DATA_ROOT"])
def datenwurzel(request, tmp_path, monkeypatch):
    """Datenwurzel NACH dem Import umstellen, Arbeitsverzeichnis daneben legen
    (Muster `tests/unit/test_diagnostics_path_resolution.py`). Beide Wege, weil
    `get_data_root()` sie unterschiedlich gewichtet (`_DATA_ROOT` > `GZ_DATA_DIR`):
    ein Writer, der nur die Umgebungsvariable liest, faellt sonst nicht auf."""
    from app import loader

    wurzel, arbeitsordner = tmp_path / "datenwurzel", tmp_path / "arbeitsordner"
    wurzel.mkdir()
    arbeitsordner.mkdir()
    if request.param == "GZ_DATA_DIR":
        monkeypatch.setattr(loader, "_DATA_ROOT", None, raising=False)
        monkeypatch.setenv("GZ_DATA_DIR", str(wurzel))
    else:
        monkeypatch.delenv("GZ_DATA_DIR", raising=False)
        monkeypatch.setattr(loader, "_DATA_ROOT", str(wurzel), raising=False)
    monkeypatch.chdir(arbeitsordner)
    return wurzel, arbeitsordner


# --- AC-1..AC-3: Aenderungs- plus Takt-Regel ------------------------------
def test_change_writes_one_line_with_reason_aenderung(monkeypatch):
    """AC-1. GIVEN ein zuvor geschriebener Stand fuer einen Schluessel WHEN ein
    neuer Verbrauch mit abweichendem alarmrelevantem Wert eintrifft THEN entsteht
    genau EINE weitere Zeile mit `grund: "aenderung"`."""
    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is True, "Grundlinie fehlt"

    _uhr(monkeypatch, ANKER + timedelta(minutes=20))  # deutlich INNERHALB des Takts
    assert _mitschnitt(modul, aggregat=_aggregat(precip=29.4)) is True

    zeilen = _zeilen(ANKER)
    assert len(zeilen) == 2, f"erwartet Grundlinie + eine Aenderungszeile, ist {zeilen}"
    assert zeilen[-1]["grund"] == "aenderung"
    assert zeilen[-1]["werte"]["precip_sum_mm"] == 29.4
    assert zeilen[0]["werte"]["precip_sum_mm"] == 7.4, "Grundlinie wurde ueberschrieben"


def test_stale_entry_older_than_60min_writes_despite_unchanged_values(monkeypatch):
    """AC-2. GIVEN identische Werte, aber der letzte Eintrag desselben Schluessels
    ist aelter als 60 Minuten WHEN erneut verbraucht wird THEN entsteht genau eine
    Zeile mit `grund: "takt"` — der erzwungene Takt macht eine FEHLENDE Zeile
    eindeutig als Fehler erkennbar."""
    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is True

    _uhr(monkeypatch, ANKER + timedelta(minutes=61))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is True

    zeilen = _zeilen(ANKER)
    assert len(zeilen) == 2
    assert zeilen[-1]["grund"] == "takt"
    assert zeilen[-1]["werte"] == zeilen[0]["werte"], "Takt-Zeile traegt andere Werte"
    assert zeilen[-1]["written_at"] == (ANKER + timedelta(minutes=61)).isoformat()


def test_unchanged_and_fresh_writes_nothing(monkeypatch):
    """AC-3. GIVEN identische Werte und ein Eintrag juenger als 60 Minuten WHEN
    derselbe Schluessel erneut verbraucht wird THEN entsteht keine Zeile.
    Positivkontrolle im selben Test: eine Wertaenderung zur GLEICHEN Uhrzeit
    schreibt sehr wohl — ohne sie waere "keine Zeile" auch bei totem Writer wahr."""
    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is True

    _uhr(monkeypatch, ANKER + timedelta(minutes=59))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is False
    assert len(_zeilen(ANKER)) == 1, "unveraendert+frisch haette nichts schreiben duerfen"

    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.5)) is True
    assert len(_zeilen(ANKER)) == 2, "Positivkontrolle: Aenderung muss schreiben"


# --- AC-4: Wert-Frische am ECHTEN Dienst ----------------------------------
def test_cache_hit_preserves_original_fetched_at(monkeypatch):
    """AC-4a. GIVEN ein Cache-Treffer mit `cached_at` messbar in der Vergangenheit
    WHEN eine Zeile geschrieben wird THEN traegt `fetched_at` den URSPRUENGLICHEN
    Abrufzeitpunkt (nicht die aktuelle Uhrzeit) und `cache_hit` ist wahr.
    `cached_at` und die gestellte Uhr liegen bewusst 45 bzw. 90 Minuten
    auseinander — waeren sie gleich, bewiese die Gleichheit nichts."""
    provider = FakeProvider()
    cache = WeatherCacheService(ttl_seconds=3600)
    dienst = SegmentWeatherService(provider, cache=cache)
    segment = _segment()

    _uhr(monkeypatch, ANKER)
    dienst.fetch_segment_weather(segment)  # Cache-Miss: fuellt Cache + Grundlinie

    abgerufen_um = (datetime.now(timezone.utc) - timedelta(minutes=45)).replace(microsecond=0)
    for eintrag in cache._cache.values():
        eintrag.cached_at = abgerufen_um  # echter Eintrag, nur aelter gestellt

    verbraucht_um = ANKER + timedelta(minutes=90)  # > 60 min => Takt erzwingt Schreiben
    _uhr(monkeypatch, verbraucht_um)
    dienst.fetch_segment_weather(segment)

    assert provider.calls == 1, "zweiter Lauf war kein echter Cache-Treffer"
    zeilen = _zeilen(ANKER)
    assert len(zeilen) == 2, f"Cache-Treffer hat nichts mitgeschnitten: {zeilen}"
    letzte = zeilen[-1]
    assert letzte["cache_hit"] is True
    assert letzte["fetched_at"] == abgerufen_um.isoformat()
    assert letzte["written_at"] == verbraucht_um.isoformat()
    assert letzte["fetched_at"] != letzte["written_at"], "Wert-Frische ging verloren"


def test_cache_miss_records_fresh_fetch_and_cache_hit_false(monkeypatch):
    """AC-4b. GIVEN ein frischer Provider-Abruf WHEN eine Zeile geschrieben wird
    THEN traegt `fetched_at` den echten Abrufzeitpunkt (zwischen zwei
    Realzeit-Marken um den Aufruf herum) und `cache_hit` ist falsch."""
    dienst = SegmentWeatherService(FakeProvider(), cache=WeatherCacheService())
    _uhr(monkeypatch, ANKER)

    vorher = datetime.now(timezone.utc)
    dienst.fetch_segment_weather(_segment())
    nachher = datetime.now(timezone.utc)

    zeilen = _zeilen(ANKER)
    assert len(zeilen) == 1, f"frischer Abruf hat nichts mitgeschnitten: {zeilen}"
    assert zeilen[0]["cache_hit"] is False
    abgerufen = datetime.fromisoformat(zeilen[0]["fetched_at"])
    assert vorher <= abgerufen <= nachher, "fetched_at ist nicht der echte Abrufzeitpunkt"
    assert zeilen[0]["written_at"] == ANKER.isoformat()


# --- AC-5/AC-6: Ablage und Aufbewahrung -----------------------------------
def test_line_is_appended_to_todays_daily_file(monkeypatch):
    """AC-5. GIVEN ein Schreibvorgang am aktuellen Datum WHEN die Zeile geschrieben
    wird THEN landet sie ANGEHAENGT in der Tagesdatei des heutigen Tages; eine
    bestehende Zeile bleibt unveraendert erhalten."""
    modul = _uhr(monkeypatch, ANKER)
    ziel = _datei(ANKER)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps({"marker": "vorher"}) + "\n", encoding="utf-8")

    assert _mitschnitt(modul, aggregat=_aggregat(precip=3.3)) is True

    zeilen = _zeilen(ANKER)
    assert len(zeilen) == 2, "die bestehende Zeile wurde ueberschrieben statt angehaengt"
    assert zeilen[0] == {"marker": "vorher"}
    assert zeilen[1]["werte"]["precip_sum_mm"] == 3.3
    assert ziel.name == f"forecast_capture_{ANKER.date().isoformat()}.jsonl"


def test_prune_removes_only_forecast_capture_files_older_than_30_days(monkeypatch):
    """AC-6a. GIVEN alte und junge Tagesdateien sowie Nachbardateien im
    `diagnostics`-Ordner WHEN ein Datumswechsel den Prune ausloest THEN
    verschwinden ausschliesslich zu alte, DATIERTE `forecast_capture_*`-Dateien —
    Nachbardateien und undatierte Namensvettern ueberleben (#1987-Falle).

    Die Nachbar-Marker stehen VOR dem ersten Mitschnitt: `enrichment_calls.jsonl`
    waechst durch die von AC-10 geforderte Health-Meldung legitim mit. Nur so
    weist die Zeile-1-Pruefung weiter Ueberschreiben/Abschneiden nach, statt
    blosses Wachstum zu verbieten. Die `alt`/`jung`-Tagesdateien bleiben bewusst
    NACH dem ersten Mitschnitt — laegen sie schon davor, koennte der Prune sie
    bereits bei t=0 raeumen und ihr Verschwinden waere nicht mehr dem
    Datumswechsel zuzuordnen."""
    modul = _uhr(monkeypatch, ANKER)
    ordner = _diagnose_ordner()
    ordner.mkdir(parents=True, exist_ok=True)
    nachbarn = [
        ordner / "openmeteo_calls.jsonl",
        ordner / "enrichment_calls.jsonl",
        ordner / "forecast_capture_ohne_datum.jsonl",  # kein Datum => kein Prune-Ziel
    ]
    for pfad in nachbarn:
        with pfad.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"marker": pfad.name}) + "\n")

    assert _mitschnitt(modul, aggregat=_aggregat(precip=1.0)) is True

    def _tagesdatei(tage: int) -> Path:
        return ordner / f"forecast_capture_{(ANKER - timedelta(days=tage)).date()}.jsonl"

    alt = [_tagesdatei(40), _tagesdatei(35)]
    jung = [_tagesdatei(5), _tagesdatei(1)]
    for pfad in alt + jung:
        with pfad.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"marker": pfad.name}) + "\n")

    _uhr(monkeypatch, ANKER + timedelta(days=1))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=2.0)) is True

    for pfad in alt:
        assert not pfad.exists(), f"{pfad.name} ist aelter als 30 Tage, haette weg gemusst"
    for pfad in jung:
        assert pfad.is_file(), f"{pfad.name} ist juenger als 30 Tage, faelschlich entfernt"
    for pfad in nachbarn:
        assert pfad.is_file(), f"Nachbardatei {pfad.name} wurde angetastet (#1987)"
        erste = pfad.read_text(encoding="utf-8").splitlines()[0]
        assert json.loads(erste) == {"marker": pfad.name}, f"{pfad.name} ueberschrieben"


def test_prune_runs_only_on_date_change_not_every_write(monkeypatch):
    """AC-6b. GIVEN mehrere Schreibvorgaenge am selben Tag WHEN sie nacheinander
    erfolgen THEN laeuft der Prune NICHT bei jedem Schreiben, sondern erst beim
    tatsaechlichen Datumswechsel — belegt an einer alten Datei, die den zweiten
    Schreibvorgang desselben Tages ueberlebt und erst am Folgetag verschwindet."""
    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=1.0)) is True

    uralt = _diagnose_ordner() / f"forecast_capture_{(ANKER - timedelta(days=40)).date()}.jsonl"
    uralt.write_text(json.dumps({"marker": "uralt"}) + "\n", encoding="utf-8")

    _uhr(monkeypatch, ANKER + timedelta(minutes=90))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=2.0)) is True
    assert uralt.is_file(), "Prune lief bei einem Schreibvorgang OHNE Datumswechsel"

    _uhr(monkeypatch, ANKER + timedelta(days=1))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=3.0)) is True
    assert not uralt.exists(), "Prune lief beim Datumswechsel nicht"


def test_path_resolves_via_get_data_root_at_runtime(datenwurzel, monkeypatch):
    """AC-7. GIVEN `GZ_DATA_DIR` bzw. `loader._DATA_ROOT` zeigen auf
    unterschiedliche temporaere Verzeichnisse WHEN der Writer aufgerufen wird THEN
    folgt der Schreibpfad in BEIDEN Faellen der zur Laufzeit aufgeloesten
    Datenwurzel — und neben dem Arbeitsverzeichnis entsteht nichts (Falle #1633:
    eine beim Import gebundene Modulkonstante)."""
    wurzel, arbeitsordner = datenwurzel
    modul = _uhr(monkeypatch, ANKER)

    assert _mitschnitt(modul, aggregat=_aggregat(precip=4.2)) is True

    daneben = sorted(str(p.relative_to(arbeitsordner)) for p in arbeitsordner.rglob("*"))
    assert not daneben, (f"Neben {arbeitsordner} ist etwas entstanden: {daneben} — "
                         f"die Datenwurzel {wurzel} wurde nicht beachtet.")
    zeilen = _zeilen(ANKER, wurzel=wurzel)
    assert len(zeilen) == 1, f"keine Zeile unter der Datenwurzel {wurzel}"
    assert zeilen[0]["werte"]["precip_sum_mm"] == 4.2


# --- AC-8/AC-9: Wirkung am Einbaupunkt ------------------------------------
def test_capture_failure_does_not_raise_and_forecast_result_unchanged():
    """AC-8. GIVEN das Schreibziel ist nicht beschreibbar WHEN
    `_aggregate_for_segment` ueber `fetch_segment_weather` laeuft THEN kommt das
    REGULAERE, vollstaendige Ergebnis zurueck, ohne Ausnahme nach aussen.
    Positivkontrolle im selben Test: mit heilem Ziel MUSS eine Zeile entstehen —
    sonst bewiese der erste Teil nur, dass es gar keinen Mitschnitt gibt."""
    dienst = SegmentWeatherService(FakeProvider(), cache=WeatherCacheService())
    heute = datetime.now(timezone.utc)

    _ziel_unbeschreibbar_machen(heute)
    kaputt = dienst.fetch_segment_weather(_segment(lat=46.60))

    assert kaputt.has_error is False, f"Mitschnitt-Fehler schlug durch: {kaputt.error_message}"
    assert kaputt.aggregated.precip_sum_mm is not None
    assert kaputt.timeseries is not None

    _datei(heute).rmdir()
    gut = dienst.fetch_segment_weather(_segment(lat=46.70))  # anderer Dedup-Schluessel

    assert len(_zeilen(heute)) == 1, "Positivkontrolle: mit heilem Ziel muss geschrieben werden"
    assert kaputt.aggregated == gut.aggregated, "Ergebnis haengt vom Mitschnitt-Erfolg ab"


def test_kill_switch_disables_capture_completely(monkeypatch):
    """AC-9. GIVEN `GZ_FORECAST_CAPTURE=0` WHEN ein Segment-Aggregat verbraucht
    wird THEN entsteht keine Datei und kein Health-Eintrag, das Wetterergebnis
    bleibt unveraendert. Positivkontrolle: ohne die Variable (Default AN) entsteht
    unter sonst gleichen Bedingungen eine Zeile."""
    dienst = SegmentWeatherService(FakeProvider(), cache=WeatherCacheService())
    heute = datetime.now(timezone.utc)

    monkeypatch.setenv("GZ_FORECAST_CAPTURE", "0")
    aus = dienst.fetch_segment_weather(_segment(lat=46.60))

    assert _zeilen(heute) == [], "Kill-Switch hat den Dateizugriff nicht verhindert"
    assert _health_meldungen("forecast_capture") == [], "Kill-Switch liess Health-Eintrag zu"
    assert aus.has_error is False

    monkeypatch.delenv("GZ_FORECAST_CAPTURE")
    an = dienst.fetch_segment_weather(_segment(lat=46.70))  # anderer Dedup-Schluessel

    assert len(_zeilen(heute)) == 1, "Positivkontrolle: Default ist AN"
    assert aus.aggregated == an.aggregated, "das Wetterergebnis haengt am Kill-Switch"


# --- AC-10..AC-12: Ausfall-Sichtbarkeit, Zeilenvertrag, Reihenfolge -------
def test_success_and_failure_report_to_enrichment_health_throttled(monkeypatch):
    """AC-10. GIVEN aufeinanderfolgende Mitschnitt-Versuche innerhalb von 15
    Minuten WHEN der erste erfolgreich ist und ein spaeterer fehlschlaegt THEN
    erscheint je 15-Minuten-Fenster HOECHSTENS eine Meldung mit Pfad
    `forecast_capture` und passendem Ausgang in der echten
    `diagnostics/enrichment_calls.jsonl`."""
    from providers.enrichment_health import (
        OUTCOME_OK, OUTCOME_UNAVAILABLE, PATH_FORECAST_CAPTURE,
    )

    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=1.0)) is True
    for versatz, precip in ((5, 2.0), (10, 3.0)):
        _uhr(monkeypatch, ANKER + timedelta(minutes=versatz))
        assert _mitschnitt(modul, aggregat=_aggregat(precip=precip)) is True

    meldungen = _health_meldungen(PATH_FORECAST_CAPTURE)
    assert len(meldungen) == 1, f"gedrosselt heisst EINE Meldung je 15 Minuten: {meldungen}"
    assert meldungen[0]["outcome"] == OUTCOME_OK

    _ziel_unbeschreibbar_machen(ANKER)
    _uhr(monkeypatch, ANKER + timedelta(minutes=16))  # Drosselfenster abgelaufen
    assert _mitschnitt(modul, aggregat=_aggregat(precip=4.0)) is False

    meldungen = _health_meldungen(PATH_FORECAST_CAPTURE)
    assert len(meldungen) == 2, f"der Ausfall blieb stumm (ADR-0018): {meldungen}"
    assert meldungen[-1]["outcome"] == OUTCOME_UNAVAILABLE


def test_line_contains_required_fields_no_timeseries_no_trip_id_under_4kib(monkeypatch):
    """AC-11. GIVEN eine schreibwuerdige Zeile WHEN sie aufgebaut wird THEN traegt
    sie Identitaet, Herkunft und die alarmrelevanten Aggregatwerte — aber keine
    Zeitreihe, keine Stundenwerte, keine Trip-Kennung — und bleibt unter 4 KiB
    (mehrere Threads haengen gleichzeitig an, `comparison_parallel.py:118`)."""
    modul = _uhr(monkeypatch, ANKER)
    segment = _segment(lat=46.6123, lon=12.9456, segment_id="Ziel")

    assert _mitschnitt(
        modul, segment=segment, aggregat=_aggregat(precip=29.4),
        fetched_at=ANKER - timedelta(minutes=12), cache_hit=True,
        provider="openmeteo", model="icon_d2",
    ) is True

    roh = _datei(ANKER).read_text(encoding="utf-8").splitlines()[-1]
    zeile = json.loads(roh)

    assert set(zeile) == ERWARTETE_SCHLUESSEL, (
        f"Zeilenvertrag verletzt: zu viel {set(zeile) - ERWARTETE_SCHLUESSEL}, "
        f"fehlt {ERWARTETE_SCHLUESSEL - set(zeile)}")
    assert set(zeile["werte"]) == ERWARTETE_WERTE
    assert zeile["lat"] == pytest.approx(46.6123)
    assert zeile["lon"] == pytest.approx(12.9456)
    assert zeile["segment_id"] == "Ziel"
    assert zeile["fenster_start"] == segment.start_time.isoformat()
    assert zeile["fenster_ende"] == segment.end_time.isoformat()
    assert zeile["day_window_start_hour"] == 6
    assert zeile["day_window_end_hour"] == 18
    assert zeile["provider"] == "openmeteo"
    assert zeile["model"] == "icon_d2"
    assert isinstance(zeile["source"], str) and zeile["source"]
    assert zeile["werte"]["thunder_level_max"] == "MED", "Enum nicht als String serialisiert"
    assert zeile["werte"]["precip_sum_mm"] == 29.4
    assert not any(isinstance(w, (list, dict)) for w in zeile["werte"].values()), \
        "Aggregatwerte enthalten eine Zeitreihe/Stundenwerte"
    assert not any(isinstance(w, list) for w in zeile.values()), "Zeitreihe in der Zeile"
    assert len(roh.encode("utf-8")) < 4096, f"Zeile ist {len(roh.encode('utf-8'))} Bytes gross"


def test_resolve_call_source_called_only_after_write_decision(monkeypatch):
    """AC-12. GIVEN ein Verbrauch, der wegen unveraendert-und-frisch keine Zeile
    ausloest WHEN die Pruefung abgeschlossen ist THEN wurde das teure
    `resolve_call_source()` (nutzt `inspect.stack()`) NICHT aufgerufen; erst der
    schreibwuerdige Fall ruft es — genau einmal. Der Zaehler umhuellt die ECHTE
    Funktion, es wird nichts vorgetaeuscht."""
    from providers import call_log

    zaehler = {"n": 0}
    echt = call_log.resolve_call_source

    def zaehlend() -> str:
        zaehler["n"] += 1
        return echt()

    monkeypatch.setattr(call_log, "resolve_call_source", zaehlend)

    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=5.0)) is True  # Grundlinie
    zaehler["n"] = 0

    _uhr(monkeypatch, ANKER + timedelta(minutes=30))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=5.0)) is False
    assert zaehler["n"] == 0, "resolve_call_source lief vor der Schreib-Entscheidung"

    assert _mitschnitt(modul, aggregat=_aggregat(precip=9.0)) is True
    assert zaehler["n"] == 1, "im schreibwuerdigen Fall muss genau einmal aufgeloest werden"


# --- Adversary-Befunde: Nebenlaeufigkeit, Schluesselschnitt, Grenzfaelle ---
# Die Grenzwerte 60/15/30 stehen hier BEWUSST als Literale und nicht als
# `modul.TAKT_MINUTEN` o.ae.: eine Verschiebung der Konstante ist genau die
# Regression, die diese Tests fangen sollen.
def test_gleichzeitige_erstverbraucher_schreiben_genau_eine_zeile(monkeypatch):
    """F008. GIVEN ein Schluessel ohne Grundlinie (kalter Zustand nach
    Prozessstart) WHEN 50 Threads ihn gleichzeitig mit IDENTISCHEN Werten
    verbrauchen THEN entsteht genau EINE Zeile. Lagen Pruefung und
    Zustands-Update in getrennten kritischen Sektionen, sah jeder Thread "noch
    keine Grundlinie" und schrieb — 50 Zeilen statt einer. Echte Threads,
    `threading.Barrier` erzwingt den gleichzeitigen Start."""
    modul = _uhr(monkeypatch, ANKER)
    anzahl = 50
    barriere = threading.Barrier(anzahl)
    ergebnisse: list[bool] = []
    sammel_sperre = threading.Lock()

    def verbrauchen() -> None:
        barriere.wait()
        geschrieben = _mitschnitt(modul, aggregat=_aggregat(precip=7.4))
        with sammel_sperre:
            ergebnisse.append(geschrieben)

    threads = [threading.Thread(target=verbrauchen) for _ in range(anzahl)]
    for faden in threads:
        faden.start()
    for faden in threads:
        faden.join(timeout=20)

    assert sum(ergebnisse) == 1, f"{sum(ergebnisse)} Threads schrieben, erwartet genau 1"
    assert len(_zeilen(ANKER)) == 1, f"mehr als eine Zeile: {_zeilen(ANKER)}"


def test_dedup_schluessel_trennt_tag_und_beide_koordinaten(monkeypatch):
    """F005. GIVEN drei Verbrauche mit IDENTISCHEN Werten innerhalb des Takts,
    die sich NUR im Tag, nur in `lon` bzw. nur in `lat` unterscheiden WHEN sie
    nacheinander eintreffen THEN traegt jeder seinen eigenen Schluessel und
    erzeugt eine eigene Zeile. Die identischen Werte sind der Kern der Probe:
    bei abweichenden Werten schriebe auch ein kollidierender Schluessel, die
    Zusicherung waere trivial wahr. Der Tages-Fall ist Henningss Alltag — die
    Tour ist mehrtaegig, dieselbe Uhrzeit kommt an jedem Tag vor."""
    modul = _uhr(monkeypatch, ANKER)
    grundlinie = _segment(lat=46.6, lon=12.9, start=ANKER)
    varianten = [
        _segment(lat=46.6, lon=12.9, start=ANKER + timedelta(days=1)),
        _segment(lat=46.6, lon=13.9, start=ANKER),
        _segment(lat=47.6, lon=12.9, start=ANKER),
    ]

    assert _mitschnitt(modul, segment=grundlinie, aggregat=_aggregat(precip=7.4)) is True
    for segment in varianten:
        assert _mitschnitt(modul, segment=segment, aggregat=_aggregat(precip=7.4)) is True

    zeilen = _zeilen(ANKER)
    assert len(zeilen) == 4, f"Schluessel kollidieren, nur {len(zeilen)} von 4 Zeilen"
    assert {z["grund"] for z in zeilen} == {"aenderung"}


def test_importfehler_des_mitschnitts_erreicht_die_wetterabfrage_nicht(monkeypatch):
    """F006. GIVEN `services.forecast_capture` ist nicht importierbar WHEN
    `fetch_segment_weather()` laeuft THEN kommt das regulaere Ergebnis zurueck.
    Das AEUSSERE try/except an der Aufrufstelle ist die einzige Schicht, die
    einen Importfehler ueberhaupt abfangen KANN — das innere im Writer wird
    dabei nie erreicht (AC-8 verlangt beide). Positivkontrolle: mit heilem
    Import entsteht unter sonst gleichen Bedingungen eine Zeile."""
    import services.forecast_capture as echtes_modul

    dienst = SegmentWeatherService(FakeProvider(), cache=WeatherCacheService())
    heute = datetime.now(timezone.utc)

    monkeypatch.setitem(sys.modules, "services.forecast_capture", None)
    kaputt = dienst.fetch_segment_weather(_segment(lat=46.60))

    assert kaputt.has_error is False, f"Importfehler schlug durch: {kaputt.error_message}"
    assert kaputt.aggregated.precip_sum_mm is not None
    assert kaputt.timeseries is not None
    assert _zeilen(heute) == [], "ohne importierbares Modul kann nichts geschrieben werden"

    monkeypatch.setitem(sys.modules, "services.forecast_capture", echtes_modul)
    gut = dienst.fetch_segment_weather(_segment(lat=46.70))  # anderer Dedup-Schluessel

    assert len(_zeilen(heute)) == 1, "Positivkontrolle: mit heilem Import muss es schreiben"
    assert kaputt.aggregated == gut.aggregated, "Ergebnis haengt am Mitschnitt-Import"


def test_fehlgeschlagenes_schreiben_vergiftet_die_grundlinie_nicht(monkeypatch):
    """F007. GIVEN der Schreibvorgang fuer einen Schluessel schlaegt fehl WHEN
    derselbe Schluessel kurz darauf mit UNVERAENDERTEN Werten erneut verbraucht
    wird THEN wird geschrieben — ein Stand, der nie in der Datei landete, darf
    nicht als "zuletzt geschrieben" gelten. Der Nachlauf liegt bewusst INNERHALB
    des Takts: bei abgelaufenem Takt schriebe auch die vergiftete Variante, die
    Probe haette keine Varianz."""
    modul = _uhr(monkeypatch, ANKER)
    _ziel_unbeschreibbar_machen(ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is False
    _datei(ANKER).rmdir()

    _uhr(monkeypatch, ANKER + timedelta(minutes=5))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is True

    zeilen = _zeilen(ANKER)
    assert len(zeilen) == 1, f"der gescheiterte Versuch verschluckte die Zeile: {zeilen}"
    assert zeilen[0]["grund"] == "aenderung", "der gescheiterte Stand galt als Grundlinie"


def test_takt_grenze_bei_exakt_60_minuten_schreibt_nicht(monkeypatch):
    """F001. GIVEN identische Werte und ein Eintrag GENAU 60 Minuten alt WHEN
    erneut verbraucht wird THEN entsteht keine Zeile: "aelter als 60 Minuten"
    ist strikt, die Grenzminute gehoert noch zum ruhigen Fenster."""
    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is True

    _uhr(monkeypatch, ANKER + timedelta(minutes=60))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=7.4)) is False
    assert len(_zeilen(ANKER)) == 1, "die Takt-Grenze loeste eine Zeile zu frueh aus"


def test_health_drossel_meldet_bei_exakt_15_minuten_nicht_erneut(monkeypatch):
    """F002. GIVEN eine Health-Meldung liegt GENAU 15 Minuten zurueck WHEN ein
    weiterer Mitschnitt gelingt THEN bleibt es bei einer Meldung — "hoechstens
    eine je 15 Minuten" schliesst die Grenzminute ein."""
    from providers.enrichment_health import PATH_FORECAST_CAPTURE

    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=1.0)) is True

    _uhr(monkeypatch, ANKER + timedelta(minutes=15))
    assert _mitschnitt(modul, aggregat=_aggregat(precip=2.0)) is True

    meldungen = _health_meldungen(PATH_FORECAST_CAPTURE)
    assert len(meldungen) == 1, f"die Drossel oeffnete eine Minute zu frueh: {meldungen}"


def test_prune_grenze_genau_30_tage_bleibt_31_tage_geht(monkeypatch):
    """F003. GIVEN eine Tagesdatei ist am Prune-Tag GENAU 30 Tage alt, eine
    zweite 31 Tage WHEN der Datumswechsel den Prune ausloest THEN ueberlebt die
    erste und die zweite verschwindet. Beide werden relativ zum PRUNE-Tag
    datiert, nicht zum Anker — der Prune laeuft einen Tag spaeter."""
    modul = _uhr(monkeypatch, ANKER)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=1.0)) is True
    prune_tag = ANKER + timedelta(days=1)
    ordner = _diagnose_ordner()

    def _tagesdatei(tage: int) -> Path:
        name = f"forecast_capture_{(prune_tag - timedelta(days=tage)).date()}.jsonl"
        pfad = ordner / name
        pfad.write_text(json.dumps({"marker": name}) + "\n", encoding="utf-8")
        return pfad

    genau_30, tag_31 = _tagesdatei(30), _tagesdatei(31)

    _uhr(monkeypatch, prune_tag)
    assert _mitschnitt(modul, aggregat=_aggregat(precip=2.0)) is True

    assert genau_30.is_file(), "genau 30 Tage alt ist nicht 'aelter als 30 Tage'"
    assert not tag_31.exists(), "31 Tage alt haette entfernt werden muessen"
