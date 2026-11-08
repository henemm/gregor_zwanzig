"""TDD RED — Issue #1695: Ortsvergleich-Anker darf nicht auf zwei Kalendertage
zerfallen, wenn die Ortsmitternacht zwischen den Abruf von Ort 1 und Ort 2 faellt.

SPEC: docs/specs/modules/fix_1695_anker_ortsmitternacht.md (AC-1 bis AC-8)

Der Defekt in einem Satz: ``_write_compare_alert_snapshots`` ruft
``CompareLocationWeatherSource.fetch()`` je Ort auf, und ``fetch()`` loest
"jetzt" bei JEDEM Aufruf selbst auf (``datetime.now(timezone.utc)``). Springt
die Uhr zwischen Ort 1 und Ort 2 ueber die Ortsmitternacht, tragen die Anker
desselben Vergleichs verschiedene ``target_date``; der 15-Minuten-Alarm meldet
dann eine "Aenderung", obwohl sich die Vorhersage nicht geaendert hat.

Abgenommen wird die GESPEICHERTE WIRKUNG: der echte Schreibpfad
``_write_compare_alert_snapshots`` mit der echten
``CompareLocationWeatherSource``; gelesen wird ueber
``CompareWeatherSnapshotService.load()``. Gestellt sind nur der Provider-Rand
(echter Fake, Muster ``SkriptierterOpenMeteo`` aus
``test_compare_alert_day_window.py``) und die Uhr. Kein ``Mock``/``patch``.

Welche Tests HEUTE rot sind (und warum):
  * AC-1, AC-3, AC-4, AC-8: rot — der Schreibpfad uebergibt kein ``now``,
    ``fetch()`` kennt den Parameter nicht.
  * AC-2, AC-5, AC-6: Regressionswaechter fuer unveraendertes Verhalten; sie
    sind absichtlich schon heute gruen und duerfen es nach dem Fix bleiben.

Ausfuehrung:
    uv run pytest tests/tdd/test_compare_anker_ortsmitternacht.py -v \
        --disable-socket --allow-hosts=127.0.0.1
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.user import SavedLocation
from services.weather_cache import reset_shared_weather_cache_for_tests
from utils.timezone import tz_for_coords

from tests.tdd.test_compare_alert_day_window import (
    SkriptierterOpenMeteo,
    Wetterlage,
    ortszeit,
)

# Mitteleuropa (Europe/Vienna, im November UTC+1).
ALPEN_LAT, ALPEN_LON = 47.0500, 11.5500
ALPEN2_LAT, ALPEN2_LON = 47.2000, 11.2000
# Kamtschatka (UTC+12) und Kalifornien (UTC-8 im November).
KAMTSCHATKA_LAT, KAMTSCHATKA_LON = 53.0, 158.65
SIERRA_LAT, SIERRA_LON = 39.1900, -120.2400

TAG = date(2026, 11, 5)


# ───────────────────────── Aufbau (kein Mock) ────────────────────────────────

class Aufbau:
    """Registriert den Provider-Fake und liefert Orte/Nutzer."""

    def __init__(self, monkeypatch, tmp_path, lage: Wetterlage,
                 provider_klasse=SkriptierterOpenMeteo) -> None:
        import providers.base as provider_registry

        self.monkeypatch = monkeypatch
        monkeypatch.chdir(tmp_path)
        # tests/conftest.py setzt diese Variable pro Test; sie haette in
        # ``get_provider()`` Vorrang vor der Registry und hebelte den Fake aus.
        monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
        if not provider_registry._PROVIDER_FACTORIES:
            provider_registry._load_providers()
        reset_shared_weather_cache_for_tests()
        monkeypatch.setitem(
            provider_registry._PROVIDER_FACTORIES,
            "openmeteo",
            lambda: provider_klasse(lage),
        )

    def uhr_quelle(self, momente: list[datetime]) -> None:
        """Uhr der lesenden Quelle: liefert nacheinander ``momente``, danach
        immer den letzten. Gestellt wird das modul-lokale ``datetime``."""
        import services.compare_location_weather_source as quelle_mod

        folge = list(momente)

        class _Folge(datetime):
            @classmethod
            def now(cls, tz=None):
                moment = folge.pop(0) if len(folge) > 1 else folge[0]
                return moment.replace(tzinfo=None) if tz is None else moment.astimezone(tz)

        self.monkeypatch.setattr(quelle_mod, "datetime", _Folge)

    def uhr_dispatch(self, moment: datetime,
                     schritt: timedelta | None = None) -> None:
        """Uhr des Schreibpfads (``_datetime`` in ``scheduler_dispatch_service``).

        Ohne ``schritt`` steht die Uhr fest auf ``moment``. Mit ``schritt``
        laeuft sie fort: der erste ``now()``-Aufruf liefert ``moment``, jeder
        weitere den vorigen Moment + ``schritt`` (#2847, F001) -- sonst faellt
        nicht auf, wenn der Schreibpfad die Uhr je Ort neu abfragt."""
        import services.scheduler_dispatch_service as dispatch_mod

        stand = [moment]

        class _Fest(datetime):
            @classmethod
            def now(cls, tz=None):
                aktuell = stand[0]
                if schritt is not None:
                    stand[0] = aktuell + schritt
                return aktuell.replace(tzinfo=None) if tz is None else aktuell.astimezone(tz)

        self.monkeypatch.setattr(dispatch_mod, "_datetime", _Fest)


def neuer_nutzer() -> str:
    return f"tdd-1695-{uuid.uuid4().hex[:8]}"


def ort(loc_id: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=f"Ort {loc_id}", lat=lat, lon=lon,
                         elevation_m=1000)


def schreibe(preset_id: str, orte: list, user_id: str) -> None:
    """Der ECHTE Schreibpfad des Report-Versands (Morgen-Slot: Versatz 0)."""
    from services.scheduler_dispatch_service import _write_compare_alert_snapshots

    _write_compare_alert_snapshots(preset_id, orte, user_id, {}, 0)


def anker(user_id: str, preset_id: str, loc_id: str):
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    return CompareWeatherSnapshotService(user_id=user_id).load(preset_id, loc_id)


def wien_lage() -> Wetterlage:
    return Wetterlage(tz=tz_for_coords(ALPEN_LAT, ALPEN_LON), basis_tag=TAG,
                      tagesgang=False)


def utc_lage() -> Wetterlage:
    """Zeitreihe in UTC ueber 4.-7.11. — deckt die Fenster aller drei Zeitzonen."""
    return Wetterlage(tz=timezone.utc, basis_tag=TAG, tagesgang=False)  # type: ignore[arg-type]


# ═════════════════════════════════ AC-1 ══════════════════════════════════════

def test_ac1_ortsmitternacht_zwischen_zwei_orten_zerlegt_den_anker_nicht(
    monkeypatch, tmp_path
):
    """AC-1: Given Preset mit zwei Orten und eine Uhr, die zwischen dem Abruf
    von Ort 1 und Ort 2 ueber die Ortsmitternacht springt / When der
    Anker-Schreiber beide Orte speichert / Then tragen beide Anker dasselbe
    ``target_date``.

    HEUTE ROT: Ort 1 holt um 23:59 Ortszeit (Tag 5.11.), Ort 2 um 00:01
    (Tag 6.11.) — die Anker tragen verschiedene Tage.
    """
    b = Aufbau(monkeypatch, tmp_path, wien_lage())
    tz = tz_for_coords(ALPEN_LAT, ALPEN_LON)
    # Uhr der Quelle: erst 23:59, dann 00:01 Ortszeit (springt ueber Mitternacht).
    b.uhr_quelle([ortszeit(tz, TAG, 23) .replace(minute=59),
                  ortszeit(tz, date(2026, 11, 6), 0).replace(minute=1)])
    # Uhr des Schreibpfads: fest VOR der Mitternacht.
    b.uhr_dispatch(ortszeit(tz, TAG, 23).replace(minute=58))

    user_id, preset_id = neuer_nutzer(), f"cp-1695-{uuid.uuid4().hex[:6]}"
    schreibe(preset_id, [ort("a", ALPEN_LAT, ALPEN_LON),
                         ort("b", ALPEN2_LAT, ALPEN2_LON)], user_id)

    a, bb = anker(user_id, preset_id, "a"), anker(user_id, preset_id, "b")
    assert a and bb, "Fixture-Schutz: beide Orte muessen einen Anker haben."
    assert a[0].target_date == bb[0].target_date, (
        "AC-1: Die Anker desselben Vergleichs zerfallen auf zwei Kalendertage "
        f"(Ort a: {a[0].target_date}, Ort b: {bb[0].target_date}). Der Schreibpfad "
        "muss EINEN Zeitpunkt festhalten und an alle Orte durchreichen."
    )
    assert a[0].target_date == TAG


# ═════════════════════════════════ AC-2 ══════════════════════════════════════

def test_ac2_fetch_ohne_now_nutzt_weiter_die_systemuhr(monkeypatch, tmp_path):
    """AC-2 (Regressionswaechter, heute gruen): ``fetch()`` ohne ``now``
    verhaelt sich wie vor dem Fix — der Ortstag stammt aus der Systemuhr."""
    from services.compare_location_weather_source import CompareLocationWeatherSource

    b = Aufbau(monkeypatch, tmp_path, utc_lage())
    b.uhr_quelle([datetime(2026, 11, 5, 14, 0, tzinfo=timezone.utc)])

    punkt = CompareLocationWeatherSource().fetch(
        "k", KAMTSCHATKA_LAT, KAMTSCHATKA_LON, 4, 19,
        tage_ab_ortstag=0, user_id=neuer_nutzer(),
    )
    # 14:00 UTC = 02:00 Ortszeit am 6.11. in Kamtschatka (UTC+12).
    assert punkt.target_date == date(2026, 11, 6)


# ═════════════════════════════════ AC-3 ══════════════════════════════════════

def test_ac3_uebergebenes_now_gilt_je_ort_in_der_ortszeit(monkeypatch, tmp_path):
    """AC-3: Given ``fetch()`` mit tz-aware ``now`` und davon abweichender
    Systemuhr, Orte in UTC+12 und UTC-8 / Then stammt der Ortstag je Ort aus
    ``now`` (nicht aus der Systemuhr) und die Orte duerfen um einen Tag
    differieren.

    HEUTE ROT: ``fetch()`` kennt den Parameter ``now`` nicht (TypeError).
    """
    from services.compare_location_weather_source import CompareLocationWeatherSource

    b = Aufbau(monkeypatch, tmp_path, utc_lage())
    # Systemuhr bewusst auf einem ganz anderen Tag.
    b.uhr_quelle([datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)])
    now = datetime(2026, 11, 5, 14, 0, tzinfo=timezone.utc)
    user_id = neuer_nutzer()
    quelle = CompareLocationWeatherSource()

    kamtschatka = quelle.fetch("k", KAMTSCHATKA_LAT, KAMTSCHATKA_LON, 4, 19,
                               tage_ab_ortstag=0, now=now, user_id=user_id)
    sierra = quelle.fetch("s", SIERRA_LAT, SIERRA_LON, 4, 19,
                          tage_ab_ortstag=0, now=now, user_id=user_id)

    # 14:00 UTC: Kamtschatka 02:00 am 6.11., Sierra 06:00 am 5.11.
    assert kamtschatka.target_date == date(2026, 11, 6)
    assert sierra.target_date == date(2026, 11, 5)


# ═════════════════════════════════ AC-4 ══════════════════════════════════════

def test_ac4_naives_now_wirft_value_error_vor_dem_providerzugriff(
    monkeypatch, tmp_path
):
    """AC-4: Naives ``now`` -> ``ValueError`` statt stillem Rueckfall auf die
    Systemuhr, und zwar VOR dem Provider-Zugriff.

    HEUTE ROT: ``TypeError`` (unbekannter Parameter) statt ``ValueError``.
    """
    from services.compare_location_weather_source import CompareLocationWeatherSource

    aufrufe: list[object] = []

    class ZaehlenderProvider(SkriptierterOpenMeteo):
        def fetch_forecast(self, *a, **k):
            aufrufe.append(a)
            return super().fetch_forecast(*a, **k)

    Aufbau(monkeypatch, tmp_path, utc_lage(), provider_klasse=ZaehlenderProvider)

    with pytest.raises(ValueError):
        CompareLocationWeatherSource().fetch(
            "k", ALPEN_LAT, ALPEN_LON, 4, 19, tage_ab_ortstag=0,
            now=datetime(2026, 11, 5, 12, 0), user_id=neuer_nutzer(),
        )
    assert not aufrufe, "AC-4: Die Pruefung muss vor dem Provider-Zugriff laufen."


# ═════════════════════════════════ AC-5 ══════════════════════════════════════

def test_ac5_ein_fehlschlagender_ort_verhindert_die_anderen_anker_nicht(
    monkeypatch, tmp_path
):
    """AC-5 (Regressionswaechter, heute gruen): der mittlere von drei Orten
    wirft am Provider-Rand; Anker 1 und 3 liegen vor, 2 nicht, der Lauf bricht
    nicht ab (fail-soft je Ort)."""
    gift_lat = 45.0

    class Giftprovider(SkriptierterOpenMeteo):
        def fetch_forecast(self, location, *a, **k):
            if getattr(location, "latitude", None) == gift_lat:
                raise RuntimeError("Provider-Ausfall fuer genau diesen Ort")
            return super().fetch_forecast(location, *a, **k)

    b = Aufbau(monkeypatch, tmp_path, wien_lage(), provider_klasse=Giftprovider)
    # Beide Uhren fest auf Mittag Ortszeit am Testtag (#2847): sonst rechnet
    # der Test mit der echten Uhr und liegt ausserhalb der Wetter-Testdaten.
    mittag = ortszeit(tz_for_coords(ALPEN_LAT, ALPEN_LON), TAG, 12)
    b.uhr_quelle([mittag])
    b.uhr_dispatch(mittag)
    user_id, preset_id = neuer_nutzer(), f"cp-1695-{uuid.uuid4().hex[:6]}"

    schreibe(preset_id, [ort("a", ALPEN_LAT, ALPEN_LON),
                         ort("b", gift_lat, ALPEN_LON),
                         ort("c", ALPEN2_LAT, ALPEN2_LON)], user_id)

    assert anker(user_id, preset_id, "a")
    assert not anker(user_id, preset_id, "b")
    assert anker(user_id, preset_id, "c")


# ═════════════════════════════════ AC-6 ══════════════════════════════════════

def test_ac6_anker_liegen_nur_im_bereich_des_eigenen_nutzers(monkeypatch, tmp_path):
    """AC-6 (Regressionswaechter, heute gruen): zwei Nutzer mit GLEICHEM Preset-
    und Ort-Schluessel, aber verschiedenen Koordinaten. Jeder sieht nur den
    eigenen Anker; ein dritter, unbeteiligter Nutzer sieht keinen."""
    b = Aufbau(monkeypatch, tmp_path, wien_lage())
    # Beide Uhren fest auf Mittag Ortszeit am Testtag (#2847): sonst rechnet
    # der Test mit der echten Uhr und liegt ausserhalb der Wetter-Testdaten.
    mittag = ortszeit(tz_for_coords(ALPEN_LAT, ALPEN_LON), TAG, 12)
    b.uhr_quelle([mittag])
    b.uhr_dispatch(mittag)
    nutzer_a, nutzer_b, fremder = neuer_nutzer(), neuer_nutzer(), neuer_nutzer()
    preset_id = f"cp-1695-{uuid.uuid4().hex[:6]}"

    schreibe(preset_id, [ort("x", ALPEN_LAT, ALPEN_LON)], nutzer_a)
    schreibe(preset_id, [ort("x", ALPEN2_LAT, ALPEN2_LON)], nutzer_b)

    a, b_ = anker(nutzer_a, preset_id, "x"), anker(nutzer_b, preset_id, "x")
    assert a and b_
    assert a[0].lat == ALPEN_LAT and b_[0].lat == ALPEN2_LAT
    assert not anker(fremder, preset_id, "x")
    assert not anker("default", preset_id, "x")


# ═════════════════════════════════ AC-8 ══════════════════════════════════════

def test_ac8_schreibpfad_reicht_ein_und_dasselbe_now_an_alle_orte(
    monkeypatch, tmp_path
):
    """AC-8: Der Schreibpfad uebergibt BEDINGUNGSLOS ``now`` an ``fetch()``,
    an jeden Ort denselben Wert, und fuer jeden Ort liegt ein Anker vor (kein
    vom fail-soft-Schleifenrumpf verschluckter ``TypeError``).

    Die Attrappe ist eine echte Unterklasse des Prueflings mit ``now=None`` in
    der Signatur, die den Wert aufzeichnet und an den echten Abrufweg
    delegiert (Muster ``SpionierendeQuelle``).

    HEUTE ROT: der Schreibpfad reicht kein ``now`` durch (aufgezeichnet: None).
    """
    import services.compare_location_weather_source as quelle_mod

    b = Aufbau(monkeypatch, tmp_path, wien_lage())
    # Beide Uhren fest auf Mittag Ortszeit am Testtag (#2847): sonst rechnet
    # der Test mit der echten Uhr und liegt ausserhalb der Wetter-Testdaten.
    mittag = ortszeit(tz_for_coords(ALPEN_LAT, ALPEN_LON), TAG, 12)
    b.uhr_quelle([mittag])
    # Dispatch-Uhr laeuft fort (je Abfrage +1 Minute, bleibt am Testtag):
    # fragte der Schreibpfad die Uhr je Ort neu ab, erhielten die Orte
    # verschiedene Zeitpunkte und die Gleichheits-Zusicherung wuerde rot.
    b.uhr_dispatch(mittag, schritt=timedelta(minutes=1))
    aufgezeichnet: list[object] = []
    echte_quelle = quelle_mod.CompareLocationWeatherSource

    class SpionierendeQuelle(echte_quelle):
        def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
                  target_date=None, tage_ab_ortstag=None, elevation_m=None,
                  now=None, user_id=None):
            aufgezeichnet.append(now)
            zusatz = {} if now is None else {"now": now}
            return super().fetch(point_id, lat, lon, start_hour, end_hour,
                                 target_date=target_date,
                                 tage_ab_ortstag=tage_ab_ortstag,
                                 elevation_m=elevation_m, user_id=user_id,
                                 **zusatz)

    monkeypatch.setattr(quelle_mod, "CompareLocationWeatherSource", SpionierendeQuelle)

    user_id, preset_id = neuer_nutzer(), f"cp-1695-{uuid.uuid4().hex[:6]}"
    schreibe(preset_id, [ort("a", ALPEN_LAT, ALPEN_LON),
                         ort("b", ALPEN2_LAT, ALPEN2_LON)], user_id)

    assert len(aufgezeichnet) == 2, "Der Schreibpfad muss beide Orte abrufen."
    assert all(n is not None for n in aufgezeichnet), (
        f"AC-8: `now` wurde nicht (bedingungslos) durchgereicht: {aufgezeichnet}"
    )
    assert aufgezeichnet[0] == aufgezeichnet[1], (
        "AC-8: Alle Orte eines Vergleichs muessen DENSELBEN Zeitpunkt erhalten."
    )
    assert aufgezeichnet[0].tzinfo is not None
    assert anker(user_id, preset_id, "a") and anker(user_id, preset_id, "b")
