"""TDD RED — Issue #1584 Scheibe C: Der Abweichungs-Alarm des Ortsvergleichs
vergleicht zwei verschiedene TAGESZEITEN statt desselben Tagesfensters.

SPEC: docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md
(AC-1, AC-2, AC-3a, AC-3b, AC-4, AC-5, AC-6a, AC-6b, AC-7, AC-8a, AC-8b)

Der Defekt in einem Satz: ``CompareLocationWeatherSource.fetch()`` baut bei
JEDEM Aufruf ein Ein-Stunden-Segment bei ``datetime.now()``
(``compare_location_weather_source.py:38-50``). Anker (beim Report-Versand)
und Frisch-Abruf (beim 15-Minuten-Check) decken deshalb verschiedene
Tagesstunden ab — der blosse Tagesgang loest Alarme aus, und Aenderungen
ausserhalb der laufenden Stunde werden nie gesehen.

Abgenommen wird ausschliesslich die ZUGESTELLTE WIRKUNG: geht ueber den
echten ``CompareAlertService``-Sendepfad eine Mail raus (``mail_sink``
gefuellt) oder nicht. Kein Assert auf ``aggregated``, ``segment.end_time``
oder ``duration_hours``.

Warum jeder Test HEUTE rot ist — die beiden Haelften des Fehlerbilds:

  * Tests, die einen Alarm ERWARTEN (AC-2, AC-3a, AC-4, AC-6a, AC-7, AC-8a),
    laufen auf einer FLACHEN Temperaturkurve. Die echte Vorhersage-Aenderung
    liegt ausserhalb der gerade laufenden Stunde -> heute Delta 0, kein
    Versand, Test rot. Das ist die Blindheits-Haelfte.
  * Tests, die KEINEN Alarm erwarten (AC-1, AC-3b, AC-5, AC-6b, AC-8b),
    laufen auf einer Zeitreihe mit linear steigender Temperatur (Tagesgang,
    die Fixture aus dem Spec-Beleg). Anker 07:00 gegen Frisch 15:00 ergibt
    heute Delta 12,0 K gegen die gemessene Schwelle von 10,0 K -> es geht
    faelschlich eine Mail raus, Test rot. Das ist die Fehlalarm-Haelfte.

Beide Fixtures sind bewusst asymmetrisch: mit Tagesgang waeren die
"Alarm"-Tests heute schon gruen (der Tagesgang allein loest aus und der Test
bewiese nichts), mit flacher Kurve waeren die "kein Alarm"-Tests heute schon
gruen (heute sieht der Alarm die Aenderung ohnehin nicht).

Netz- und versandfrei, mock-frei:
  * Der Provider ist ein echter Fake (kein ``Mock``/``patch``/``MagicMock``),
    registriert ueber die vorhandene Provider-Registry
    (``providers.base._PROVIDER_FACTORIES``) — damit laeuft der ECHTE
    ``CompareLocationWeatherSource`` inklusive ``SegmentWeatherService``-
    Fensterfilterung durch. Genau dort sitzt der Defekt; ein injizierter
    ``weather_source`` wuerde ihn ueberspringen und nichts beweisen.
  * E-Mail laeuft ueber die vorhandene ``mail_sink``-Naht, Telegram/SMS sind
    in den Settings leer und im Preset nicht eingeschaltet.
  * Uhrzeit-Seam: das modul-lokale ``datetime`` in
    ``services.compare_location_weather_source`` (Muster
    ``_freeze_compare_official_alert_now`` aus
    ``tests/tdd/test_compare_official_alert.py:584``). ``freezegun`` ist im
    Projekt nicht installiert.
  * Persistenz: Presets ueber ``monkeypatch.chdir(tmp_path)`` (der
    Compare-Loader liest ``data/users/...`` cwd-relativ), alles Uebrige ueber
    die pytest-isolierte ``app.loader.get_data_dir()``-Basis (#1133).

Ausfuehrung:
    uv run pytest tests/tdd/test_compare_alert_day_window.py -v \
        --disable-socket --allow-hosts=127.0.0.1
"""
from __future__ import annotations

import inspect
import logging
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from app.user import SavedLocation
from services.weather_cache import reset_shared_weather_cache_for_tests
from utils.timezone import tz_for_coords

from tests.helpers.alert_log_fixtures import settings_email_only
from tests.helpers.compare_briefings import write_compare_briefings

# Mitteleuropa (Europe/Vienna) — AC-1, AC-2, AC-3a/3b, AC-5, AC-6a/6b, AC-7,
# AC-8a/8b. Kein sichtbarer UTC-Versatz zu Wien: diese Orte sehen die
# Zeitzonen-Mutation bewusst NICHT.
ALPEN_LAT, ALPEN_LON = 47.0500, 11.5500
# Deutlicher UTC-Versatz WESTLICH von Wien (America/Los_Angeles, UTC-7/-8) —
# nur AC-4. Westlich ist Pflicht: bei fest verdrahtetem Europe/Vienna faellt
# das dort berechnete Fenster auf einen ganz anderen Ortszeit-Abschnitt.
SIERRA_LAT, SIERRA_LON = 39.1900, -120.2400

# Niederschlags-Delta weit ueber der Standard-Schwelle von 10,0 mm.
REGEN_MM = 30.0
FLACHE_TEMPERATUR_C = 12.0
# Steigung des Tagesgangs in K je Ortsstunde.
#
# GEMESSEN, nicht aus der Spec uebernommen: auf diesem Pfad
# (``_STANDARD_METRIC_LEVELS``, ``display_config=None``) liegt die wirksame
# Temperatur-Schwelle bei 10,0 K, nicht bei den in der Spec genannten 7,0 K —
# die Regel ``temperature_change`` (Schwelle 10,0, Felder ``temp_min_c`` +
# ``temp_max_c``) ueberschreibt in der Schwellen-Tabelle die engere Regel
# ``temperature_max`` (6,0). Der Spec-Beleg "Delta 8,0 gegen Schwelle 7,0"
# loest deshalb NICHT aus — nachgemessen. Mit 1,5 K je Stunde ergibt der
# Tagesgang zwischen Anker (07:00 -> 10,5 °C) und Frisch-Abruf (15:00 ->
# 22,5 °C) ein Delta von 12,0 K und ueberschreitet die echte Schwelle.
TAGESGANG_K_PRO_STUNDE = 1.5


# ───────────────────────── Fixture-Wetterlage (kein Mock) ───────────────────

@dataclass(frozen=True)
class Wetterlage:
    """Deterministische 96-Stunden-Zeitreihe ab ``basis_tag`` minus ein Tag.

    ``tagesgang=True``  -> ``t2m_c`` steigt linear mit der ORTSSTUNDE (die
    Fixture des Spec-Belegs, s. ``TAGESGANG_K_PRO_STUNDE``): eine voellig
    unveraenderte Vorhersage, deren Tagesgang beim heutigen
    Ein-Stunden-Fenster als "Aenderung" durchschlaegt.
    ``tagesgang=False`` -> ``t2m_c`` konstant; dann kann NUR die unten
    eingetragene Aenderung einen Alarm ausloesen.

    ``regen`` traegt ``(tagesversatz, ortsstunde, mm)``: Niederschlag genau in
    dieser einen Ortsstunde des Tages ``basis_tag + tagesversatz``.
    """

    tz: ZoneInfo
    basis_tag: date
    tagesgang: bool = True
    regen: tuple[tuple[int, int, float], ...] = ()

    def zeitreihe(self) -> NormalizedTimeseries:
        start = ortszeit(self.tz, self.basis_tag - timedelta(days=1), 0)
        regen_index = {
            (self.basis_tag + timedelta(days=versatz), stunde): mm
            for versatz, stunde, mm in self.regen
        }
        punkte = []
        for h in range(96):
            ts = start + timedelta(hours=h)
            lokal = ts.astimezone(self.tz)
            punkte.append(
                ForecastDataPoint(
                    ts=ts,
                    t2m_c=(
                        TAGESGANG_K_PRO_STUNDE * lokal.hour
                        if self.tagesgang
                        else FLACHE_TEMPERATUR_C
                    ),
                    wind10m_kmh=5.0,
                    gust_kmh=8.0,
                    precip_1h_mm=regen_index.get((lokal.date(), lokal.hour), 0.0),
                )
            )
        return NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.2,
                run=start,
            ),
            data=punkte,
        )


class SkriptierterOpenMeteo:
    """Echter Provider-Fake (KEIN Mock): liefert wie Open-Meteo eine volle
    Tages-Zeitreihe unabhaengig vom angefragten Fenster. Gefiltert und
    aggregiert wird danach vom echten ``SegmentWeatherService`` — dessen
    Fensterfilterung ist genau der Pruefling."""

    def __init__(self, lage: Wetterlage) -> None:
        self._lage = lage

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        return self._lage.zeitreihe()


def ortszeit(tz: ZoneInfo, tag: date, stunde: int) -> datetime:
    """Ortszeit -> UTC, exakt nach dem Muster aus ``trip_segments.py:263-273``."""
    return datetime.combine(tag, time(stunde)).replace(tzinfo=tz).astimezone(timezone.utc)


# ───────────────────────── Szenario (echter Sendepfad) ──────────────────────

class Szenario:
    """Ein Ortsvergleich mit genau einem Ort, echtem Anker-Store und echtem
    ``CompareAlertService``. Anker und Frisch-Abruf laufen BEIDE ueber den
    echten ``CompareLocationWeatherSource`` — nur die Uhrzeit wird gestellt."""

    def __init__(self, monkeypatch, tmp_path, lat: float, lon: float,
                 fenster: tuple[int, int] | None = None) -> None:
        import providers.base as provider_registry
        from app.loader import save_location

        self._monkeypatch = monkeypatch
        self.lat, self.lon = lat, lon
        self.tz = tz_for_coords(lat, lon)
        self.basis_tag = datetime.now(timezone.utc).astimezone(self.tz).date()
        self.user_id = f"tdd-1584c-{uuid.uuid4().hex[:8]}"
        self.preset_id = f"cp-1584c-{uuid.uuid4().hex[:6]}"
        self.location_id = "loc-1"

        # Issue #1595: der Compare-Preset-Loader liest NICHT mehr cwd-relativ,
        # sondern ueber ``get_data_root()``. Die Fixture wird deshalb unter der
        # aufgeloesten Wurzel abgelegt (s.u.); das chdir bleibt als zweite
        # Sicherung gegen versehentlich relative Schreibzugriffe, die sonst im
        # echten Repo-Baum landen und den #1265-Waechter aus tests/conftest.py
        # ausloesen wuerden.
        monkeypatch.chdir(tmp_path)
        # tests/conftest.py::_use_fixture_provider setzt diese Variable fuer
        # jeden Test; sie haette in ``get_provider()`` Vorrang vor der
        # Registry und wuerde den Fake unten aushebeln.
        monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
        if not provider_registry._PROVIDER_FACTORIES:
            provider_registry._load_providers()
        self._registry = provider_registry._PROVIDER_FACTORIES

        save_location(
            SavedLocation(id=self.location_id, name="Vergleichsort",
                          lat=lat, lon=lon, elevation_m=1000),
            user_id=self.user_id,
        )
        preset = {
            "id": self.preset_id,
            "name": "Zeitfenster-Vergleich",
            "user_id": self.user_id,
            "location_ids": [self.location_id],
            # #1467 S2 AG6: ohne aktiven Zeitplan gilt der Vergleich als
            # stillgelegt und schweigt in JEDEM Alarm-Pfad.
            "schedule": "daily",
            "weekday": 4,
            "profil": "ALLGEMEIN",
            "empfaenger": ["gregor-test@henemm.com"],
            "alert_cooldown_minutes": 0,
            "letzter_versand": None,
            "created_at": "2026-08-08T00:00:00Z",
        }
        if fenster is not None:
            preset["day_window_start_hour"] = fenster[0]
            preset["day_window_end_hour"] = fenster[1]
        from app.loader import get_data_root

        write_compare_briefings(get_data_root() / "users" / self.user_id, [preset])
        # Fuer den Versandpfad-Test (F001): dasselbe Preset-Dict, das auch auf
        # der Platte liegt — `send_one_compare_preset()` bekommt es direkt.
        self.preset = preset

    # -- Seams -------------------------------------------------------------

    def _stelle_uhr(self, stunde: int) -> None:
        import services.compare_location_weather_source as quelle_mod

        moment = ortszeit(self.tz, self.basis_tag, stunde)

        class _Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return moment.replace(tzinfo=None) if tz is None else moment.astimezone(tz)

        self._monkeypatch.setattr(quelle_mod, "datetime", _Frozen)

    def _stelle_wetter(self, lage: Wetterlage) -> None:
        # Der geteilte Wetter-Cache matcht ueber "Fenster deckt ab" — ohne
        # Reset lieferte der Frisch-Abruf die Anker-Zeitreihe zurueck und
        # jede echte Aenderung waere unsichtbar.
        reset_shared_weather_cache_for_tests()
        self._monkeypatch.setitem(
            self._registry, "openmeteo", lambda: SkriptierterOpenMeteo(lage)
        )

    def _fetch(self, stunde: int):
        """Ruft den ECHTEN Produktions-Abrufweg. Die Spec gibt ``fetch()`` die
        Fenstergrenzen als zusaetzliche Parameter — der Aufruf bindet sich
        deshalb an die Signatur, damit derselbe Test vor und nach dem Fix
        denselben Produktionscode trifft."""
        from services.compare_location_weather_source import CompareLocationWeatherSource
        from services.report_config_resolver import resolve_compare_time_window
        from app.loader import compare_preset_to_dict, load_compare_presets

        self._stelle_uhr(stunde)
        quelle = CompareLocationWeatherSource()
        parameter = inspect.signature(quelle.fetch).parameters
        if "start_hour" in parameter and "end_hour" in parameter:
            preset = compare_preset_to_dict(
                load_compare_presets(user_id=self.user_id)[0]
            )
            start_hour, end_hour = resolve_compare_time_window(preset)
            return quelle.fetch(self.location_id, self.lat, self.lon, start_hour, end_hour)
        return quelle.fetch(self.location_id, self.lat, self.lon)

    # -- Schritte ----------------------------------------------------------

    def anker(self, lage: Wetterlage, stunde: int, alter: timedelta | None = None):
        """Schreibt den Delta-Anker so, wie ihn der Report-Versand schreibt:
        ueber denselben ``CompareLocationWeatherSource``. ``alter`` datiert
        ``fetched_at`` zurueck (AC-6a/6b/7) — der Anker selbst bleibt echt."""
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        self._stelle_wetter(lage)
        punkt = self._fetch(stunde)
        if alter is not None:
            punkt = replace(punkt, fetched_at=datetime.now(timezone.utc) - alter)
        CompareWeatherSnapshotService(user_id=self.user_id).save(
            self.preset_id, self.location_id, punkt
        )
        return punkt

    def anker_direkt(self, punkt, alter: timedelta | None = None) -> None:
        """Schreibt einen bereits geholten Anker erneut, mit neuem
        ``fetched_at`` (AC-7: "es wird ein NEUER Anker geschrieben")."""
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        if alter is not None:
            punkt = replace(punkt, fetched_at=datetime.now(timezone.utc) - alter)
        else:
            punkt = replace(punkt, fetched_at=datetime.now(timezone.utc))
        CompareWeatherSnapshotService(user_id=self.user_id).save(
            self.preset_id, self.location_id, punkt
        )

    def lauf(self, lage: Wetterlage, stunde: int) -> list[tuple[str, str]]:
        """Ein vollstaendiger Alarm-Check zur Ortszeit ``stunde``. Gibt die
        tatsaechlich zugestellten Mails zurueck."""
        from services.compare_alert import CompareAlertService

        self._stelle_wetter(lage)
        self._stelle_uhr(stunde)
        mails: list[tuple[str, str]] = []
        CompareAlertService(
            settings=settings_email_only(),
            user_id=self.user_id,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()
        return mails


    def versand(self, lage: Wetterlage, preset_ueberschreibung: dict | None = None):
        """Ein vollstaendiger Report-Versand ueber den ECHTEN Produktionspfad
        `send_one_compare_preset()` — derselbe Weg, auf dem in Produktion der
        Δ-Anker entsteht. Transport laeuft ueber die vorhandenen
        `*_sink`-Naehte, es geht nichts raus."""
        from services.scheduler_dispatch_service import send_one_compare_preset

        self._stelle_wetter(lage)
        preset = {**self.preset, **(preset_ueberschreibung or {})}
        send_one_compare_preset(
            preset,
            settings_email_only(),
            self.user_id,
            "data",
            mail_sink=lambda *a, **k: None,
            sms_sink=lambda *a, **k: None,
            telegram_sink=lambda *a, **k: None,
        )


def tagesgang(sz: Szenario, regen: tuple[tuple[int, int, float], ...] = ()) -> Wetterlage:
    return Wetterlage(tz=sz.tz, basis_tag=sz.basis_tag, tagesgang=True, regen=regen)


def flach(sz: Szenario, regen: tuple[tuple[int, int, float], ...] = ()) -> Wetterlage:
    return Wetterlage(tz=sz.tz, basis_tag=sz.basis_tag, tagesgang=False, regen=regen)


# ═══════════════════ Adversary-Finding F001 (Anker-Schreibpfad) ═════════════

def test_f001_versandpfad_reicht_das_preset_fenster_an_den_anker_durch(
    monkeypatch, tmp_path
):
    """Bewacht Adversary-Finding F001 (HIGH).

    GIVEN einen Ortsvergleich mit einem Tagesfenster, das VOM DEFAULT 4/19
    ABWEICHT (6-21)
    WHEN der echte Report-Versand `send_one_compare_preset()` laeuft und dabei
    den Δ-Anker schreibt
    THEN holt die Wetterquelle genau das Fenster des Presets — identisch zu
    `resolve_compare_time_window(preset)`.

    Warum dieser Test existiert: alle uebrigen Tests dieser Datei schreiben den
    Anker ueber einen direkten `fetch()`-Aufruf, und die 14 mitgeaenderten
    Bestandstests benutzen Attrappen, deren `fetch()` `start_hour`/`end_hour`
    entgegennimmt und ignoriert. Entfernte man in
    `scheduler_dispatch_service.py` NUR das `preset`-Argument an der
    Aufrufstelle von `_write_compare_alert_snapshots`, blieben sie alle gruen —
    der Anker landete wieder im falschen Fenster, waehrend der Frisch-Abruf
    korrekt bliebe. Genau das Fehlerbild, das diese Scheibe behebt.

    Der Fenster-Wert 6-21 ist Absicht: mit dem Default 4/19 waere der Test auch
    dann gruen, wenn gar kein Preset durchgereicht wuerde.
    """
    from services.report_config_resolver import resolve_compare_time_window
    import services.compare_location_weather_source as quelle_mod

    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON, fenster=(6, 21))

    # Spionage-Wetterquelle: KEIN Mock — eine echte Unterklasse des
    # Prueflings, die die Fenstergrenzen mitschreibt und danach an den echten
    # Abrufweg (Fake-Provider aus der Registry) delegiert.
    aufgezeichnete_fenster: list[tuple] = []
    echte_quelle = quelle_mod.CompareLocationWeatherSource

    class SpionierendeQuelle(echte_quelle):
        # `target_date`/`tage_ab_ortstag` (Issue #1661 Teil B): der
        # Versandpfad reicht den Tag, ueber den gebrieft wird, bis zum Δ-Anker
        # durch — als VERSATZ gegen den Ortstag (Schreibseite), der Δ-Check
        # spaeter als absoluten Tag (Leseseite). Die Attrappe nimmt beides
        # entgegen und gibt es weiter, statt hier an einem TypeError zu
        # scheitern — geprueft wird in DIESEM Test weiterhin nur das Fenster.
        def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
                  target_date=None, tage_ab_ortstag=None):
            aufgezeichnete_fenster.append((start_hour, end_hour))
            return super().fetch(point_id, lat, lon, start_hour, end_hour,
                                 target_date=target_date,
                                 tage_ab_ortstag=tage_ab_ortstag)

    # `_write_compare_alert_snapshots` importiert die Klasse erst zur Laufzeit
    # aus ihrem Heimatmodul — dort ist die Naht.
    monkeypatch.setattr(quelle_mod, "CompareLocationWeatherSource", SpionierendeQuelle)

    erwartet = resolve_compare_time_window(sz.preset)
    assert erwartet != (4, 19), (
        "Fixture-Schutz: das Preset-Fenster muss vom Default 4/19 abweichen, "
        "sonst kann der Test ein verlorenes Preset-Argument nicht sehen."
    )

    # `official_alerts_enabled=False`: der Versandpfad soll offline bleiben —
    # geprueft wird der Anker, nicht die Warnlagen-Anreicherung.
    sz.versand(flach(sz), {"official_alerts_enabled": False})

    assert aufgezeichnete_fenster, (
        "F001: Der Report-Versand hat gar keinen Δ-Anker geschrieben — der "
        "Anker-Schreibpfad wurde nicht durchlaufen, der Test bewacht nichts."
    )
    assert aufgezeichnete_fenster == [erwartet] * len(aufgezeichnete_fenster), (
        f"F001: Der Δ-Anker wurde mit dem Fenster {aufgezeichnete_fenster} "
        f"geholt statt mit dem Preset-Fenster {erwartet}. Anker und "
        "Frisch-Abruf decken damit wieder verschiedene Tageszeiten ab — "
        "vermutlich wird `preset` an `_write_compare_alert_snapshots()` nicht "
        "(oder als leeres Dict) uebergeben."
    )


# ═════════════════════════════════ AC-1 ══════════════════════════════════════

def test_ac1_unveraenderte_vorhersage_loest_keinen_alarm_aus(monkeypatch, tmp_path):
    """AC-1: Given Ort in Mitteleuropa, Tagesfenster-Default 4-19, Anker um
    07:00 Ortszeit, UNVERAENDERTE Vorhersage / When der Check um 15:00
    Ortszeit laeuft / Then bleibt der Alarm aus.

    HEUTE ROT, weil der heutige Code faelschlich ZUSTELLT: Anker- und
    Frisch-Fenster sind je eine Stunde bei ``now``; ``t2m_c = Ortsstunde``
    ergibt 7,0 gegen 15,0 = Delta 8,0 K ueber der Schwelle 5,0 K. Der reine
    Tagesgang genuegt, obwohl sich die Vorhersage nicht geaendert hat.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    lage = tagesgang(sz)
    sz.anker(lage, 7)
    mails = sz.lauf(lage, 15)
    assert not mails, (
        "AC-1: Eine unveraenderte Vorhersage darf keinen Alarm ausloesen. "
        f"Tatsaechlich zugestellt: {[s for s, _ in mails]}. Anker (07:00) und "
        "Frisch-Abruf (15:00) decken verschiedene Tagesstunden ab — verglichen "
        "wird der Tagesgang, nicht die Vorhersage."
    )


# ═════════════════════════════════ AC-2 ══════════════════════════════════════

def test_ac2_echte_aenderung_ausserhalb_der_pruefstunde_wird_gemeldet(monkeypatch, tmp_path):
    """AC-2: Given denselben Aufbau, und eine echte Aenderung, die die
    Schwelle nur um 14:00 Ortszeit ueberschreitet / When der Check um 15:00
    Ortszeit laeuft / Then wird der Alarm zugestellt.

    HEUTE ROT, weil der heutige Code faelschlich SCHWEIGT: das
    Ein-Stunden-Fenster deckt nur 15:00-16:00 ab, der geaenderte 14-Uhr-Wert
    liegt ausserhalb und wird nie aggregiert. Die Temperatur ist hier flach —
    ohne das waere der Tagesgang allein schon ein Ausloeser und der Test
    bewiese nichts.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    sz.anker(flach(sz), 7)
    mails = sz.lauf(flach(sz, ((0, 14, REGEN_MM),)), 15)
    assert mails, (
        "AC-2: Eine echte Vorhersage-Aenderung um 14:00 Ortszeit (30 mm gegen "
        "Schwelle 10 mm) muss einen Alarm ausloesen, auch wenn der Check erst "
        "um 15:00 laeuft. Es kam keine Mail an — bewertet wird nur die gerade "
        "laufende Stunde, der Alarm ist fuer den Rest des Tages blind."
    )


# ═════════════════════════════════ AC-3a ═════════════════════════════════════

def test_ac3a_aenderung_in_stunde_18_liegt_innerhalb_des_fensters(monkeypatch, tmp_path):
    """AC-3a: Given ausdruecklich gesetztes Tagesfenster 4-19, echte Aenderung
    genau in Stunde 18 (letzte volle Stunde innerhalb ``[4,19)``) / When der
    Check laeuft / Then wird der Alarm zugestellt.

    HEUTE ROT (heutiger Code schweigt faelschlich): Stunde 18 liegt ausserhalb
    des Ein-Stunden-Fensters bei 15:00. Flache Temperatur, damit nur die
    Aenderung selbst ausloesen kann.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON, fenster=(4, 19))
    sz.anker(flach(sz), 7)
    mails = sz.lauf(flach(sz, ((0, 18, REGEN_MM),)), 15)
    assert mails, (
        "AC-3a: Stunde 18 liegt innerhalb des Tagesfensters 4-19 — eine echte "
        "Aenderung dort muss zugestellt werden. Es kam keine Mail an: das "
        "bewertete Fenster reicht nicht bis an die Obergrenze."
    )


# ═════════════════════════════════ AC-3b ═════════════════════════════════════

def test_1599_ac3_aenderung_in_stunde_19_liegt_innerhalb_des_fensters(monkeypatch, tmp_path):
    """#1599 AC-3 — UMGEDREHT, abgeloest durch #1599: hier stand
    ``test_ac3b_…stunde_19_liegt_ausserhalb…`` aus #1584 C.

    Die Obergrenze ist seit #1599 INKLUSIV: bei Fenster 4-19 zaehlt die Stunde
    19 mit (Fensterende zeitlich 20:00 Ortszeit), eine echte Aenderung um 19:40
    muss zugestellt werden. Flache Temperatur ist Pflicht — mit Tagesgang loeste
    schon der Tagesgang zwischen Anker (07:00) und Frisch-Abruf (15:00) aus und
    der Test bewiese nichts. Die Aussen-Haelfte des Paars ist
    ``test_1599_ac4_…stunde_20_liegt_ausserhalb…`` direkt darunter — derselbe
    Ortsvergleich mit demselben ausdruecklich gesetzten Fenster.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON, fenster=(4, 19))
    sz.anker(flach(sz), 7)
    mails = sz.lauf(flach(sz, ((0, 19, REGEN_MM),)), 15)
    assert mails, (
        "#1599 AC-3: Stunde 19 liegt INNERHALB des inklusiven Tagesfensters "
        "4-19 (Fensterende 20:00 Ortszeit) — eine echte Aenderung dort (30 mm "
        "gegen Schwelle 10 mm) muss zugestellt werden. Es kam keine Mail an: "
        "die obere Fenstergrenze wird weiterhin exklusiv bei 19:00 gebildet "
        "(compare_location_weather_source.py::_window_bound)."
    )


# ════════════════════════════ #1599 AC-4 ═════════════════════════════════════

def test_1599_ac4_aenderung_in_stunde_20_liegt_ausserhalb_des_fensters(
    monkeypatch, tmp_path,
):
    """#1599 AC-4: Given DENSELBEN Ortsvergleich wie #1599 AC-3 (ausdruecklich
    gesetztes Tagesfenster 4-19) und dieselbe Wetteraenderung, nur um 20:10
    Ortszeit / When der Compare-Alert-Check laeuft / Then bleibt der Alarm aus.

    Die Innen-Haelfte des Grenzwert-Paars steht direkt darueber. Beide Haelften
    muessen am SELBEN, ausdruecklich konfigurierten Fenster haengen: das
    inklusive Ende verschiebt die Kante von 19:00 auf 20:00, und eine
    Zusicherung „bis genau hierhin und keinen Schritt weiter" ist nur bewiesen,
    wenn beide Seiten derselben Kante an derselben Konfiguration gemessen
    werden. ``test_ac8b_…ist_stunde_20_ausserhalb`` prueft dieselbe Stunde am
    DEFAULT-Fenster (Preset ohne die Felder) — wertgleich, aber ein anderer
    Aufloesungspfad; er bleibt als eigener Fall bestehen.

    Tagesgang statt flacher Kurve, nach der Konvention dieses Moduls fuer
    „kein Alarm"-Tests (s. Modul-Docstring): so faellt der Test zusaetzlich auf,
    wenn Anker (07:00) und Frisch-Abruf (15:00) wieder verschiedene Tagesstunden
    abdecken. Mit gleichem Fenster auf beiden Seiten hebt sich der Tagesgang
    exakt auf; ausloesen kann nur der Regen in Stunde 20.
    Rot bei ``window_end_utc_exclusive()`` mit ``+ 2 h`` statt ``+ 1 h``: das
    Fenster reichte dann bis 21:00 Ortszeit, Stunde 20 laege faelschlich
    innerhalb und die Aenderung ginge raus.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON, fenster=(4, 19))
    sz.anker(tagesgang(sz), 7)
    mails = sz.lauf(tagesgang(sz, ((0, 20, REGEN_MM),)), 15)
    assert not mails, (
        "#1599 AC-4: Stunde 20 liegt AUSSERHALB des inklusiven Tagesfensters "
        "4-19 (Fensterende 20:00 Ortszeit) — eine Aenderung dort darf keinen "
        f"Alarm ausloesen. Zugestellt: {[s for s, _ in mails]}. Entweder "
        "reicht die obere Fenstergrenze eine Stunde zu weit, oder Anker und "
        "Frisch-Abruf decken verschiedene Tagesstunden ab."
    )


# ═════════════════════════════════ AC-4 ══════════════════════════════════════

def test_ac4_fenster_wird_in_der_ortszeit_am_ort_aufgeloest(monkeypatch, tmp_path):
    """AC-4: Given einen Ort mit klarem UTC-Versatz zu Wien
    (America/Los_Angeles), Tagesfenster-Default 4-19 ORTSZEIT AM ORT, eine
    echte Aenderung um 17:00 Ortszeit / When der Check um 09:00 Ortszeit
    laeuft / Then wird der Alarm zugestellt.

    ABWEICHUNG VON DER SPEC (bewusst, gemeldet): die Spec nennt als Pruefzeit
    17:05 Ortszeit. Zu dieser Zeit umfasst das heutige Ein-Stunden-Fenster
    aber bereits die Stunde 17 — der Alarm ginge schon HEUTE raus und der Test
    waere von Anfang an gruen, also wertlos. Mit der Pruefzeit 09:00 bleibt
    die Zeitzonen-Aussage unveraendert und der Test ist heute rot.

    HEUTE ROT (heutiger Code schweigt faelschlich): Fenster 09:00-10:00,
    Aenderung um 17:00.
    Rot bei der Mutation ``tz_for_coords`` -> ``Europe/Vienna``: das Fenster
    4-19 Wiener Zeit entspricht am Ort 19:00 des Vortages bis 10:00 — Stunde
    17 Ortszeit liegt dann ausserhalb, der Alarm bliebe aus. Anker (07:00
    Ortszeit = 16:00 Wien) und Frisch (09:00 Ortszeit = 18:00 Wien) fallen
    dabei auf denselben Wiener Kalendertag, das Fenster ist also fuer beide
    Seiten dasselbe — der Test scheitert dann an der Zeitzone, nicht am
    Fenstervergleich.
    """
    sz = Szenario(monkeypatch, tmp_path, SIERRA_LAT, SIERRA_LON)
    sz.anker(flach(sz), 7)
    mails = sz.lauf(flach(sz, ((0, 17, REGEN_MM),)), 9)
    assert mails, (
        "AC-4: Das Tagesfenster muss in der Ortszeit AM ORT aufgeloest werden "
        "(tz_for_coords(lat, lon)). Es kam keine Mail an — entweder gilt "
        "weiterhin das Ein-Stunden-Fenster bei now, oder das Fenster wurde in "
        "Europe/Vienna bzw. UTC statt in America/Los_Angeles gebildet."
    )


# ═════════════════════════════════ AC-5 ══════════════════════════════════════

def test_ac5_check_um_22_uhr_bleibt_beim_fenster_des_laufenden_tages(monkeypatch, tmp_path):
    """AC-5 (Randfall 22:00): Given Tagesfenster 4-19, Anker um 07:00 Ortszeit
    an Tag D, Vorhersage fuer Tag D unveraendert, Vorhersage fuer Tag D+1
    bewusst ANDERS (30 mm Regen um 12:00 an D+1) / When der Check um 22:00
    Ortszeit noch an Tag D laeuft / Then bleibt der Alarm aus.

    Neu gefasst mit Issue #1661 (PO-Entscheidung E3): die Zusicherung lautet
    nicht mehr „Anker und Frisch-Abruf bleiben beim Fenster des laufenden
    Tages", sondern „Anker und Frisch-Abruf beschreiben DENSELBEN Tag —
    naemlich den, ueber den zuletzt gebrieft wurde". Fuer diesen Test ist das
    derselbe Tag und derselbe Assert: das Preset hier hat keinen aktivierten
    Abend-Slot, der Anker traegt also keinen bzw. den laufenden Tagesbezug.
    Nur die Formulierung war zu eng — die Wirkung ist unveraendert.

    Anker und Frisch-Abruf sehen exakt dieselbe Zeitreihe — es hat sich nichts
    geaendert; unterschiedlich sind nur die beiden KALENDERTAGE darin.

    HEUTE ROT, weil der heutige Code faelschlich ZUSTELLT: Tagesgang 7,0 gegen
    22,0 = Delta 15,0 K.
    Rot bei der Mutation "nach Fensterende auf den Folgetag umschalten": der
    Frisch-Abruf berechnete dann Tag D+1 (4-19) mit den 30 mm, der Anker
    bliebe auf Tag D — ein Delta ohne jede Vorhersage-Aenderung.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    lage = tagesgang(sz, ((1, 12, REGEN_MM),))
    sz.anker(lage, 7)
    mails = sz.lauf(lage, 22)
    assert not mails, (
        "AC-5: Ein Check um 22:00 Ortszeit muss weiterhin das Tagesfenster des "
        "LAUFENDEN lokalen Tages bewerten — dort hat sich nichts geaendert. "
        f"Zugestellt: {[s for s, _ in mails]}. Entweder wurde auf den Folgetag "
        "umgeschaltet, oder Anker und Frisch-Abruf decken weiterhin "
        "verschiedene Tagesstunden ab."
    )


# ═════════════════════════════════ AC-6a ═════════════════════════════════════

def test_ac6a_anker_knapp_unter_26_stunden_alarmiert_weiterhin(monkeypatch, tmp_path):
    """AC-6a: Given einen Delta-Anker mit ``fetched_at`` = jetzt minus 25 h
    50 min und eine echte Aenderung innerhalb des Fensters / When der Check
    laeuft / Then wird der Alarm zugestellt.

    HEUTE ROT (heutiger Code schweigt faelschlich): die Aenderung um 14:00
    liegt ausserhalb des Ein-Stunden-Fensters bei 15:00.
    Rot bei einer zu aggressiven Alters-Schwelle (z.B. 24 h statt 26 h): ein
    noch gueltiger Anker wuerde dann bereits unterdrueckt.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    sz.anker(flach(sz), 7, alter=timedelta(hours=25, minutes=50))
    mails = sz.lauf(flach(sz, ((0, 14, REGEN_MM),)), 15)
    assert mails, (
        "AC-6a: Ein Anker mit 25 h 50 min Alter liegt unter der 26-h-Grenze — "
        "eine echte Aenderung im Tagesfenster muss weiterhin zugestellt "
        "werden. Es kam keine Mail an: entweder greift die Alters-Sperre zu "
        "frueh, oder die Aenderung liegt ausserhalb des bewerteten Fensters."
    )


# ═════════════════════════════════ AC-6b ═════════════════════════════════════

def test_ac6b_anker_ueber_26_stunden_schweigt_mit_warnung(monkeypatch, tmp_path, caplog):
    """AC-6b: Given denselben Aufbau wie AC-6a, aber ``fetched_at`` = jetzt
    minus 26 h 10 min / When der Check laeuft / Then bleibt der Alarm aus UND
    es erscheint eine WARNING-Protokollzeile mit Preset- und Ortskennung
    (Spec, Abschnitt "Anker-Hoechstalter-Guard").

    HEUTE ROT, weil der heutige Code faelschlich ZUSTELLT — gegen einen
    ADR-0009-widrigen, ueber 26 Stunden alten Anker. Der Tagesgang ist dafuer
    noetig: mit flacher Kurve bliebe der Alarm heute schon aus (Blindheit) und
    der Test bewiese nichts. Die echte Aenderung um 14:00 ist trotzdem
    eingebaut, damit der Test nach dem Fix am GUARD scheitert, wenn dieser
    entfernt wird — und nicht mangels Ausloeser gruen bleibt.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    sz.anker(tagesgang(sz), 7, alter=timedelta(hours=26, minutes=10))
    with caplog.at_level(logging.WARNING):
        mails = sz.lauf(tagesgang(sz, ((0, 14, REGEN_MM),)), 15)

    assert not mails, (
        "AC-6b: Ein ueber 26 Stunden alter Delta-Anker darf keinen Alarm mehr "
        f"tragen (ADR-0009). Zugestellt: {[s for s, _ in mails]}."
    )
    warnungen = [
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    ]
    assert any(
        sz.preset_id in m and sz.location_id in m for m in warnungen
    ), (
        "AC-6b: Der unterdrueckte Lauf muss eine WARNING-Protokollzeile mit "
        f"Preset-Kennung ({sz.preset_id}) und Ortskennung ({sz.location_id}) "
        f"schreiben. Gefundene Warnungen: {warnungen}"
    )


# ═════════════════════════════════ AC-7 ══════════════════════════════════════

def test_ac7_nach_neuem_anker_wird_dieselbe_aenderung_wieder_gemeldet(monkeypatch, tmp_path):
    """AC-7: Given den unterdrueckten Zustand aus AC-6b (Anker 26 h 10 min
    alt), dann wird ein NEUER Anker mit ``fetched_at`` = jetzt geschrieben /
    When derselbe Aenderungswert erneut geprueft wird / Then wird der Alarm
    jetzt zugestellt.

    HEUTE ROT (heutiger Code schweigt faelschlich): die Aenderung um 14:00
    liegt ausserhalb des Ein-Stunden-Fensters bei 15:00 — auch im zweiten
    Lauf.
    Rot, wenn die Alters-Sperre beim Unterdruecken faelschlich
    ``alert_state``/Cooldown fortschreibt: die Aenderung gaelte dann als
    bereits gemeldet und der Alarm bliebe auch nach dem frischen Anker aus —
    aus der temporaeren Unterdrueckung wuerde Dauerstille.

    Flache Temperatur: der Tagesgang wuerde den zweiten Lauf schon heute
    ausloesen und die Aussage zunichtemachen.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    anker_punkt = sz.anker(flach(sz), 7, alter=timedelta(hours=26, minutes=10))
    geaendert = flach(sz, ((0, 14, REGEN_MM),))

    erster_lauf = sz.lauf(geaendert, 15)
    assert not erster_lauf, (
        "AC-7 (Vorbedingung): der Lauf gegen den 26 h 10 min alten Anker muss "
        f"stumm bleiben. Zugestellt: {[s for s, _ in erster_lauf]}."
    )

    sz.anker_direkt(anker_punkt)  # neuer Anker, fetched_at = jetzt
    zweiter_lauf = sz.lauf(geaendert, 15)
    assert zweiter_lauf, (
        "AC-7: Nach einem frischen Delta-Anker muss dieselbe echte Aenderung "
        "wieder gemeldet werden. Es kam keine Mail an — entweder ist die "
        "Aenderung weiterhin ausserhalb des bewerteten Fensters, oder die "
        "Alters-Sperre hat alert_state/Cooldown fortgeschrieben und die "
        "Aenderung gilt faelschlich als bereits gemeldet."
    )


# ═════════════════════════════════ AC-8a ═════════════════════════════════════

def test_ac8a_ohne_gesetztes_tagesfenster_gilt_der_default_4_19(monkeypatch, tmp_path):
    """AC-8a: Given ein Preset OHNE ``day_window_start_hour``/``_end_hour``
    (Produktiv-Regelfall: kein einziger Vergleich hat das Feld gesetzt), eine
    echte Aenderung in Stunde 18 / When der Check laeuft / Then wird der Alarm
    zugestellt.

    HEUTE ROT (heutiger Code schweigt faelschlich): Stunde 18 liegt ausserhalb
    des Ein-Stunden-Fensters bei 15:00.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    sz.anker(flach(sz), 7)
    mails = sz.lauf(flach(sz, ((0, 18, REGEN_MM),)), 15)
    assert mails, (
        "AC-8a: Ohne gesetzte Tagesfenster-Felder muss der Default 4-19 "
        "greifen — Stunde 18 liegt darin. Es kam keine Mail an: entweder "
        "faellt ein fehlendes Feld nicht auf den Default zurueck, oder das "
        "bewertete Fenster ist weiterhin eine Stunde breit."
    )


# ═════════════════════════════════ AC-8b ═════════════════════════════════════

def test_ac8b_ohne_gesetztes_tagesfenster_ist_stunde_20_ausserhalb(monkeypatch, tmp_path):
    """AC-8b (Regressions-Waechter gegen "Bewertung = ganzer Tag"): Given
    denselben Aufbau wie AC-8a, aber die Aenderung liegt in Stunde 20
    (ausserhalb des Defaults 4-19) / When der Check laeuft / Then bleibt der
    Alarm aus.

    HEUTE ROT, weil der heutige Code faelschlich ZUSTELLT: Tagesgang 7,0 gegen
    15,0. Der Tagesgang ist auch hier Absicht — mit flacher Kurve waere der
    Test heute schon gruen und bewachte nichts.
    Rot bei einem hartcodierten ``(0, 24)`` bzw. dem von ADR-0035 abgeloesten
    "#1268: Bewertung = ganzer Tag": Stunde 20 laege dann faelschlich innerhalb.
    """
    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON)
    sz.anker(tagesgang(sz), 7)
    mails = sz.lauf(tagesgang(sz, ((0, 20, REGEN_MM),)), 15)
    assert not mails, (
        "AC-8b: Stunde 20 liegt ausserhalb des Default-Tagesfensters 4-19 — es "
        f"darf kein Alarm rausgehen. Zugestellt: {[s for s, _ in mails]}. "
        "Entweder wird der ganze Tag bewertet, oder Anker und Frisch-Abruf "
        "decken weiterhin verschiedene Tagesstunden ab."
    )


# ═══════ #1599 Gruppe C — amtliche Warnungen (Umrechnungsstelle 3) ══════════
#
# Der Sichtbarkeits-Horizont fuer amtliche Warnungen im Ortsvergleich
# (`compare_official_alert.py::_day_window_end`) ist die dritte Stelle, die
# die Endstunde in eine Zeitgrenze umrechnet. Die Fixtures dafuer wohnen in
# `tests/tdd/test_compare_official_alert.py` (echte Fake-Quelle ueber die
# Quellen-Registry, echte Presets/Orte auf Platte, `mail_sink`-Naht) und
# werden hier wiederverwendet statt kopiert.

def _amtliche_warnung_mails(monkeypatch, gueltig_ab_utc, gueltig_bis_utc) -> list:
    """Ein vollstaendiger Lauf des echten `CompareOfficialAlertService`-
    Sendepfads; gibt die zugestellten Mails zurueck. Uhr eingefroren auf
    2026-07-12 10:00 UTC = 12:00 Ortszeit Hermagor (Europe/Vienna, UTC+2);
    `morning_time` 16:00 liegt ausserhalb des Vorlauf-Fensters aus #1594."""
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    from tests.tdd.test_compare_official_alert import (
        LAT_A, LON_A, _alert, _clean_user, _FakeOfficialAlertSource, _location,
        _preset, _settings_all_channels, _sources_backup, _uid, _write_presets,
    )
    from tests.tdd.test_compare_official_alert import (
        _freeze_compare_official_alert_now as _friere_uhr,
    )
    from app.loader import save_location

    uid = _uid("1599c")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p-1599", ["loc-a"], ["e@x.invalid"], morning_time="16:00:00",
        )])
        _friere_uhr(monkeypatch, datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc))
        register_official_alert_source(_FakeOfficialAlertSource(
            LAT_A, LON_A, [_alert(vf=gueltig_ab_utc, vt=gueltig_bis_utc)],
        ))
        mails: list = []
        CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()
        return mails
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


def test_1599_ac5_amtliche_warnung_ab_1945_liegt_im_sichtbarkeits_horizont(monkeypatch):
    """#1599 AC-5: Eine amtliche Warnung, deren Gueltigkeit um 19:45 Ortszeit
    beginnt, liegt bei Tagesfenster 4-19 INNERHALB des Sichtbarkeits-Horizonts
    — der reicht mit der inklusiven Obergrenze bis 20:00 Ortszeit, nicht bis
    19:00. Sie muss zugestellt werden."""
    mails = _amtliche_warnung_mails(
        monkeypatch,
        datetime(2026, 7, 12, 17, 45, tzinfo=timezone.utc),   # 19:45 Ortszeit
        datetime(2026, 7, 12, 19, 0, tzinfo=timezone.utc),    # 21:00 Ortszeit
    )
    assert mails, (
        "#1599 AC-5: Eine amtliche Warnung ab 19:45 Ortszeit liegt im "
        "Sichtbarkeits-Horizont des Tagesfensters 4-19 (bis 20:00 Ortszeit) "
        "und muss zugestellt werden. Es kam keine Mail an — der Horizont "
        "endet weiterhin exklusiv um 19:00 "
        "(compare_official_alert.py::_day_window_end)."
    )


def test_1599_ac6_amtliche_warnung_ab_2015_bleibt_ausserhalb(monkeypatch):
    """#1599 AC-6 (Waechter): dieselbe Warnung, Gueltigkeitsbeginn 20:15
    Ortszeit — knapp jenseits der neuen Grenze 20:00. Sie bleibt ausserhalb
    des Sichtbarkeits-Horizonts und darf NICHT zugestellt werden.
    Diskriminierende Aussen-Haelfte zu AC-5."""
    mails = _amtliche_warnung_mails(
        monkeypatch,
        datetime(2026, 7, 12, 18, 15, tzinfo=timezone.utc),   # 20:15 Ortszeit
        datetime(2026, 7, 12, 19, 30, tzinfo=timezone.utc),   # 21:30 Ortszeit
    )
    assert not mails, (
        "#1599 AC-6: Eine amtliche Warnung ab 20:15 Ortszeit liegt jenseits "
        "des Sichtbarkeits-Horizonts (bis 20:00 Ortszeit) und darf nicht "
        f"zugestellt werden. Tatsaechlich zugestellt: {[s for s, _ in mails]} "
        "— der Horizont wurde um mehr als eine Stunde verschoben oder ganz "
        "aufgehoben."
    )


def test_day_window_end_folgt_dem_ortstag_nicht_dem_utc_tag():
    """#1727 S5g AC-7: `_day_window_end` bestimmt das Tagesfenster-Ende auf dem
    ORTSTAG des Vergleichsorts, nicht auf dem UTC-Tag.

    Warum dieser Test noetig ist: `test_1599_ac5`/`test_1599_ac6` (:842/:861)
    pruefen `_day_window_end` ausschliesslich in Wiener Zone (17:45 UTC als
    "19:45 Ortszeit"). Dort fallen Ortstag und UTC-Tag auf DENSELBEN
    Kalendertag — und weil die Funktion genau `local_now.date()` auswertet,
    bliebe eine Verwechslung der Ortszone mit UTC dort gruen. Sie bewachen die
    Fenster-Formel, nicht die Zone.

    Aufbau: Auckland (Pacific/Auckland, im Juli NZST = UTC+12) bei fest
    gesetztem `now` = 2026-07-12 13:00 UTC -> Ortszeit 2026-07-13 01:00. Ortstag
    ist der 13., UTC-Tag der 12. — sie fallen auseinander. Kein
    `datetime.now()`, keine Laufzeit-Ortswahl (die bestehende
    `_daytime_location()` in `test_official_alert_time_window.py:497-508` waehlt
    den Ort wanduhrabhaengig und hat Wien an erster Stelle — als Nachweis
    untauglich).

    MUTATIONS-ERWARTUNG: Wird `now.astimezone(tz)` in
    `compare_official_alert.py::_day_window_end` durch `to_utc(now)` ersetzt
    oder die Zone fest verdrahtet, faellt der ausgewertete Kalendertag auf den
    12. zurueck; das Fensterende springt damit um einen ganzen Tag (bzw. wird
    auf `now` geklemmt) und dieser Test wird rot.
    """
    from app.day_window import window_end_utc_exclusive
    from services.compare_official_alert import CompareOfficialAlertService
    from tests.tdd.test_compare_official_alert import (
        _clean_user, _location, _settings_all_channels, _uid,
    )

    lat, lon = -36.85, 174.76          # Auckland
    tz = tz_for_coords(lat, lon)
    assert tz is not None, "Ortszone von Auckland nicht aufloesbar"
    now = datetime(2026, 7, 12, 13, 0, tzinfo=timezone.utc)
    assert now.astimezone(tz).date() == date(2026, 7, 13), (
        "Vorbedingung verletzt: Ortstag und UTC-Tag muessen auseinanderfallen, "
        f"Ortszeit ist {now.astimezone(tz)}"
    )

    # Beide Kandidaten explizit, mit derselben Fenster-Formel wie im Prueflings-
    # Code (Default-Fenster 4-19, weil das Preset nicht existiert).
    ende_ortstag = window_end_utc_exclusive(date(2026, 7, 13), 19, tz)
    ende_utc_tag = window_end_utc_exclusive(date(2026, 7, 12), 19, tz)
    assert ende_ortstag != ende_utc_tag, (
        "Probe ohne Varianz: beide Kandidaten liefern denselben Zeitpunkt "
        f"({ende_ortstag}) — dann beweist der Vergleich unten nichts."
    )

    uid = _uid("1727s5g")
    _clean_user(uid)
    try:
        ende = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
        )._day_window_end("gibt-es-nicht", _location("loc-nz", "Auckland", lat, lon), now)
    finally:
        _clean_user(uid)

    assert ende == ende_ortstag, (
        "#1727 S5g AC-7: Das Tagesfenster-Ende muss dem ORTSTAG des "
        f"Vergleichsorts folgen ({ende_ortstag}), tatsaechlich: {ende}."
    )
    assert ende != ende_utc_tag, (
        "#1727 S5g AC-7: Das Fensterende folgt dem UTC-Tag "
        f"({ende_utc_tag}) statt dem Ortstag des Vergleichsorts."
    )
