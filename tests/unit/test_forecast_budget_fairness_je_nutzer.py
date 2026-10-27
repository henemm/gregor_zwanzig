"""Issue #2387 (Scheibe S1 von #2150, Epic #2138): Kontingent je Nutzer.

SPEC: docs/specs/modules/forecast_budget_je_nutzer.md (AC-1 bis AC-5, AC-7 bis AC-10)
Ausfuehrung:
    uv run pytest tests/unit/test_forecast_budget_fairness_je_nutzer.py -v

Kern-Schicht, netzfrei. Beobachtet wird ausschliesslich ueber das Verhalten
der oeffentlichen API (`allow()` / `snapshot()`), NIE ueber den Inhalt der
Zaehlerdateien -- die Dateien sind hier nur das Arrangement (Muster
`test_forecast_budget_gate.py::_write_budget`), die Zusicherung wird am
Rueckgabewert geprueft.

Arrangement per Direktschreiben statt per `record_call()`-Schleife: die
Schwellenbaender liegen bei 7200/8550 Aufrufen, jeder echte `record_call()`
ist ein fcntl-Lock + Lesen + Schreiben + `os.replace`. Wo der SCHREIBWEG
selbst der Pruefling ist (AC-2, AC-9), wird `record_call()` echt aufgerufen.

Die Nutzerkennungen sind bewusst zwei verschiedene (`nutzer_a`/`nutzer_b`,
ADR-0003: Zwei-Nutzer-Test mit Gegenlesung ist Pflicht).

AC-6 (Go-Status-Endpunkt darf keine Nutzerkennung ausgeben) liegt Go-seitig:
`internal/scheduler/forecast_budget_user_privacy_test.go`.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

import pytest

from app.loader import get_data_dir, get_data_root
from services.forecast_budget import PROVIDER, ForecastBudgetGate
from tests.helpers.ortstag import utc_tag

NUTZER_A = "nutzer_a"
NUTZER_B = "nutzer_b"

# DAILY_BUDGET = 9000, POLLING_THRESHOLD = 0.80, BRIEFING_ONLY_THRESHOLD = 0.95.
# Fairer Anteil bei N=2 aktiven Nutzern: 9000 / 2 = 4500.
FAIRER_ANTEIL_BEI_ZWEI = ForecastBudgetGate.DAILY_BUDGET // 2
UEBER_ANTEIL = FAIRER_ANTEIL_BEI_ZWEI + 500      # 5000 -- klar darueber
UNTER_ANTEIL = FAIRER_ANTEIL_BEI_ZWEI - 2200     # 2300 -- klar darunter

# Global im Stufe-1-Band: ueber 80% (polling-Schwelle), unter 95%.
GLOBAL_UEBER_POLLING = 7300      # 7300 / 9000 = 0.811
# Global im oberen Stufe-1-Band: ueber 95% (alert_check-Schwelle), unter 100%.
GLOBAL_UEBER_ALERT = 8600        # 8600 / 9000 = 0.956
# Global am harten Kontoschutz: 100%.
GLOBAL_VOLL = ForecastBudgetGate.DAILY_BUDGET


# --- Arrangement-Helfer ----------------------------------------------------

def _globaler_pfad():
    return get_data_root() / "diagnostics" / "forecast_budget.json"


def _nutzer_pfad(user_id: str):
    return get_data_dir(user_id) / "diagnostics" / "forecast_budget.json"


def _schreibe_global(calls: int, active_users, tag=None) -> None:
    """Globale Zaehlerdatei vorbereiten.

    `active_users` ist NICHT optional: aus der Groesse dieser Menge leitet
    das Gate den fairen Anteil (DAILY_BUDGET / N) ab. Fehlt das Feld, ist
    N=1 und der faire Anteil das ganze Tagesbudget -- dann liegt NIEMAND
    darueber und AC-1/AC-10 waeren gruen, ohne etwas zu bewachen.
    """
    pfad = _globaler_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": (tag or utc_tag()).isoformat(),
        "calls": {PROVIDER: calls},
        "cache_hits": 0,
        "cache_misses": 0,
        "active_users": list(active_users),
    }))


def _schreibe_nutzer_topf(user_id: str, calls: int, tag=None) -> None:
    pfad = _nutzer_pfad(user_id)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": (tag or utc_tag()).isoformat(),
        "calls": {PROVIDER: calls},
    }))


# ---------------------------------------------------------------------------
# AC-1: Polling-Schwelle gerissen -> nur der Vielverbraucher wird gedrosselt
# ---------------------------------------------------------------------------

def test_ueber_polling_schwelle_drosselt_nur_den_nutzer_ueber_seinem_anteil():
    _schreibe_global(GLOBAL_UEBER_POLLING, active_users=[NUTZER_A, NUTZER_B])
    _schreibe_nutzer_topf(NUTZER_A, UEBER_ANTEIL)
    _schreibe_nutzer_topf(NUTZER_B, UNTER_ANTEIL)

    gate_a = ForecastBudgetGate(user_id=NUTZER_A)
    gate_b = ForecastBudgetGate(user_id=NUTZER_B)

    assert gate_a.allow("polling") is False, (
        "AC-1: Nutzer A liegt mit seinem eigenen Tagesverbrauch ueber dem "
        "fairen Anteil (DAILY_BUDGET/N) -- er muss gedrosselt werden"
    )
    assert gate_b.allow("polling") is True, (
        "AC-1 (Kern des Tickets): Nutzer B liegt klar UNTER seinem fairen "
        "Anteil -- der Vielverbrauch von A darf ihn nicht mitdrosseln"
    )


# ---------------------------------------------------------------------------
# AC-10: dasselbe im 95-99%-Band fuer die Alarm-Pruefung
# ---------------------------------------------------------------------------

def test_im_oberen_band_laeuft_die_alarmpruefung_des_unbeteiligten_weiter():
    _schreibe_global(GLOBAL_UEBER_ALERT, active_users=[NUTZER_A, NUTZER_B])
    _schreibe_nutzer_topf(NUTZER_A, UEBER_ANTEIL)
    _schreibe_nutzer_topf(NUTZER_B, 3600)  # unter 4500, Summe passt zu 8600

    gate_a = ForecastBudgetGate(user_id=NUTZER_A)
    gate_b = ForecastBudgetGate(user_id=NUTZER_B)

    assert gate_a.allow("alert_check") is False, (
        "AC-10: A liegt ueber seinem fairen Anteil -- Alarm-Pruefung gedrosselt"
    )
    assert gate_b.allow("alert_check") is True, (
        "AC-10 (Kernzusicherung #2387): die Alarm-Pruefung des unbeteiligten "
        "Nutzers B laeuft im 95-99%-Band weiter"
    )


# ---------------------------------------------------------------------------
# AC-2: Nutzer-Toepfe sind getrennt -- Gegenlesung UND Positivkontrolle
# ---------------------------------------------------------------------------

def test_nutzer_topf_eines_fremden_nutzers_ist_im_eigenen_snapshot_unsichtbar():
    gate_a = ForecastBudgetGate(user_id=NUTZER_A)
    gate_b = ForecastBudgetGate(user_id=NUTZER_B)

    gate_b.record_call()

    assert gate_a.snapshot()["user_calls_today"] == 0, (
        "AC-2 (Gegenlesung, ADR-0003): der Aufruf von Nutzer B darf im "
        "Nutzer-Topf von A NICHT auftauchen"
    )
    assert gate_b.snapshot()["user_calls_today"] == 1, (
        "AC-2 (Positivkontrolle): unter der echten Kennung von B muss der "
        "gebuchte Aufruf sichtbar sein -- sonst misst die Gegenlesung nur, "
        "dass ueberhaupt nichts gezaehlt wird"
    )


# ---------------------------------------------------------------------------
# AC-3: user_briefing bleibt auch bei 100% und vollem eigenem Topf frei
# ---------------------------------------------------------------------------

def test_user_briefing_bleibt_bei_vollem_budget_und_vollem_eigenem_topf_frei():
    _schreibe_global(GLOBAL_VOLL, active_users=[NUTZER_A, NUTZER_B])
    _schreibe_nutzer_topf(NUTZER_A, GLOBAL_VOLL)

    gate_a = ForecastBudgetGate(user_id=NUTZER_A)

    assert gate_a.allow("user_briefing") is True, (
        "AC-3: user_briefing wird in KEINER Stufe gedrosselt (Produktgrundsatz)"
    )


# ---------------------------------------------------------------------------
# AC-4: unlesbarer Nutzer-Topf -> fail-open, nie ein Drosselungsgrund
# ---------------------------------------------------------------------------

def test_kaputter_nutzer_topf_drosselt_nicht_und_wirft_nicht(caplog):
    _schreibe_global(GLOBAL_UEBER_POLLING, active_users=[NUTZER_A, NUTZER_B])
    pfad = _nutzer_pfad(NUTZER_A)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("{kein-gueltiges-json,,,")

    gate_a = ForecastBudgetGate(user_id=NUTZER_A)

    with caplog.at_level(logging.WARNING, logger="forecast_budget"):
        ergebnis = gate_a.allow("polling")

    assert ergebnis is True, (
        "AC-4 (E3): ein unlesbarer Nutzer-Topf gilt als 'nicht ueberschritten' "
        "-- ein Lesefehler darf nie zur Drosselung fuehren"
    )
    # Auf den Logger des Prueflings eingegrenzt: ein blosses `caplog.records`
    # waere schon von einer beliebigen fremden WARNING erfuellt und wuerde
    # Abdeckung vortaeuschen (Muster des Fehlschlusses aus #2152).
    warnungen = [r for r in caplog.records if r.name == "forecast_budget"]
    assert warnungen, (
        "AC-4: der verschluckte Lesefehler muss als WARNING des Gate-Loggers "
        "sichtbar werden, sonst ist der Fail-open-Weg im Betrieb unbeobachtbar"
    )


def test_gegenprobe_lesbarer_topf_ueber_anteil_drosselt_sehr_wohl():
    """Gegenprobe zu AC-4: ohne sie waere der Fail-open-Test auch dann gruen,
    wenn das Gate den Nutzer-Topf gar nicht auswertet."""
    _schreibe_global(GLOBAL_UEBER_POLLING, active_users=[NUTZER_A, NUTZER_B])
    _schreibe_nutzer_topf(NUTZER_A, UEBER_ANTEIL)

    assert ForecastBudgetGate(user_id=NUTZER_A).allow("polling") is False, (
        "Gegenprobe: derselbe Aufbau mit LESBAREM Topf ueber dem fairen "
        "Anteil muss drosseln -- nur dann beweist der Fail-open-Test etwas"
    )


# ---------------------------------------------------------------------------
# AC-5: UTC-Tageswechsel setzt Nutzer-Topf UND die Menge aktiver Nutzer zurueck
# ---------------------------------------------------------------------------

def test_tageswechsel_setzt_nutzer_topf_und_aktive_nutzer_zurueck():
    gestern = utc_tag() - timedelta(days=1)
    _schreibe_global(GLOBAL_UEBER_ALERT, active_users=[NUTZER_A, NUTZER_B], tag=gestern)
    _schreibe_nutzer_topf(NUTZER_A, UEBER_ANTEIL, tag=gestern)

    gate_a = ForecastBudgetGate(user_id=NUTZER_A)
    stand = gate_a.snapshot()

    assert stand["user_calls_today"] == 0, (
        "AC-5: der Nutzer-Topf des Vortags darf am neuen UTC-Tag nicht mehr zaehlen"
    )
    assert stand["active_users_count"] == 0, (
        "AC-5: auch die Menge der aktiven Nutzer unterliegt dem Tagesreset -- "
        "sonst traegt N die Nutzer von gestern in den fairen Anteil von heute"
    )


def test_record_call_traegt_den_nutzer_in_die_menge_aktiver_nutzer_ein():
    """Positivkontrolle zum Tagesreset oben.

    Ohne diesen Test waere `active_users_count == 0` dort auch dann gruen,
    wenn der SCHREIBWEG gar nicht existiert -- und alle uebrigen Tests lesen
    `active_users` nur aus einer von Hand gelegten Datei. Faellt der
    Schreibweg aus, bleibt N in Produktion dauerhaft 0, der faire Anteil
    damit das ganze Tagesbudget, und Stufe 1 feuert nie: bei 81% globaler
    Auslastung liefe `polling` dann fuer JEDEN durch, wo es heute fuer
    jeden blockiert -- eine Rueckentwicklung des Kontoschutzes.
    """
    gate_a = ForecastBudgetGate(user_id=NUTZER_A)
    gate_b = ForecastBudgetGate(user_id=NUTZER_B)

    gate_a.record_call()
    gate_b.record_call()

    stand = gate_a.snapshot()
    assert stand["active_users_count"] == 2, (
        "record_call() muss den Nutzer in die Menge der heute aktiven Nutzer "
        "eintragen -- diese Menge liefert N fuer den fairen Anteil"
    )
    assert stand["fair_share"] == ForecastBudgetGate.DAILY_BUDGET / 2, (
        "Der faire Anteil wird zur Laufzeit aus N abgeleitet "
        "(DAILY_BUDGET / max(N,1)) und lebt NEBEN den Bestandskonstanten, "
        "nie an ihrer Stelle (E6)"
    )


def test_injizierte_uhr_eines_neuen_tages_hebt_die_drosselung_auf():
    """Dieselbe Zusicherung ueber den injizierbaren `now`-Parameter von
    `allow()` -- ohne `date.today()`, ohne Abhaengigkeit von der Wanduhr."""
    from datetime import datetime, time, timezone

    heute = utc_tag()
    _schreibe_global(GLOBAL_UEBER_POLLING, active_users=[NUTZER_A, NUTZER_B], tag=heute)
    _schreibe_nutzer_topf(NUTZER_A, UEBER_ANTEIL, tag=heute)

    gate_a = ForecastBudgetGate(user_id=NUTZER_A)

    jetzt_heute = datetime.combine(heute, time(12, 0), tzinfo=timezone.utc)
    morgen = jetzt_heute + timedelta(days=1)

    assert gate_a.allow("polling", now=jetzt_heute) is False, (
        "Kontrollmessung: am selben UTC-Tag greift die Drosselung"
    )
    assert gate_a.allow("polling", now=morgen) is True, (
        "AC-5: am naechsten UTC-Tag sind globaler Zaehler und Nutzer-Topf "
        "zurueckgesetzt -- keine Drosselung mehr"
    )


# ---------------------------------------------------------------------------
# AC-7: Aufrufpfade ohne echte Kennung brechen laut, statt still auf einen
#       Ersatzwert zurueckzufallen (ADR-0003)
# ---------------------------------------------------------------------------

def test_gate_ohne_nutzerkennung_bricht_laut():
    with pytest.raises(TypeError):
        ForecastBudgetGate()  # type: ignore[call-arg]


def test_ortsvergleich_abrufpfad_fuehrt_user_id_als_pflichtparameter():
    """AC-7 fuer `compare_location_weather_source.py`.

    Geprueft wird die gebundene Signatur zur Laufzeit, nicht der Dateitext:
    ein Parameter OHNE Default ist genau der Mechanismus, der den stillen
    Rueckfall auf `"default"` unmoeglich macht. Der Aufruf selbst wird
    bewusst NICHT ausgefuehrt -- er wuerde im roten Lauf in einen echten
    Wetterabruf laufen statt in den erwarteten TypeError.
    """
    import inspect

    from services.compare_location_weather_source import CompareLocationWeatherSource

    parameter = inspect.signature(CompareLocationWeatherSource.fetch).parameters
    assert "user_id" in parameter, (
        "AC-7: der Ortsvergleichs-Abrufpfad muss die echte Nutzerkennung "
        "entgegennehmen -- die Aufrufer (compare_alert.py, "
        "scheduler_dispatch_service.py) fuehren sie bereits"
    )
    assert parameter["user_id"].default is inspect.Parameter.empty, (
        "AC-7 (ADR-0003): `user_id` darf KEINEN Default haben -- ein Default "
        "waere genau der stille Rueckfall, den diese Zusicherung verbietet"
    )


# ---------------------------------------------------------------------------
# AC-8: bei 100% uebersteuert der harte Kontoschutz den fairen Anteil
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prioritaet", ["polling", "alert_check"])
def test_bei_vollem_budget_wird_auch_der_sparsame_nutzer_gedrosselt(prioritaet):
    _schreibe_global(GLOBAL_VOLL, active_users=[NUTZER_A, NUTZER_B])
    _schreibe_nutzer_topf(NUTZER_B, 0)

    gate_b = ForecastBudgetGate(user_id=NUTZER_B)

    assert gate_b.allow(prioritaet) is False, (
        f"AC-8: bei 100% Tagesbudget muss '{prioritaet}' auch fuer einen "
        "Nutzer mit leerem eigenem Topf gedrosselt werden -- Stufe 2 "
        "(Kontoschutz gegenueber Open-Meteo) uebersteuert den fairen Anteil"
    )


def test_kaputter_nutzer_topf_hebelt_den_harten_kontoschutz_nicht_aus():
    """AC-8 x AC-4: die beiden Zusicherungen treffen sich hier.

    AC-8 prueft Stufe 2 mit LESBAREM Topf, AC-4 den Fail-open mit globalem
    Anteil im Stufe-1-Band. Die Kombination "unlesbarer Topf UND 100 %
    Tagesbudget" faellt zwischen beide -- und genau dort entscheidet die
    REIHENFOLGE der Stufen: wird der Nutzer-Topf vor der 100-%-Pruefung
    gelesen, liefert sein fail-open-True den Aufruf frei und der harte
    Kontoschutz gegenueber open-meteo hat ein Loch.
    """
    _schreibe_global(GLOBAL_VOLL, active_users=[NUTZER_A, NUTZER_B])
    pfad = _nutzer_pfad(NUTZER_A)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("{kein-gueltiges-json,,,")

    assert ForecastBudgetGate(user_id=NUTZER_A).allow("polling") is False, (
        "Bei 100 % Tagesbudget drosselt Stufe 2 UNABHAENGIG vom fairen "
        "Anteil -- auch dann, wenn der Nutzer-Topf unlesbar ist und der "
        "Verbrauch deshalb als 0 gilt (AC-8 uebersteuert AC-4)"
    )


# ---------------------------------------------------------------------------
# AC-9: Bestandsdaten bleiben erhalten, der Nutzer-Topf beginnt frisch bei 0
# ---------------------------------------------------------------------------

def test_globaler_bestandszaehler_bleibt_erhalten_nutzer_topf_beginnt_bei_null():
    pfad = _globaler_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    # Bestandsformat VOR dieser Aenderung: ohne das Feld "active_users".
    pfad.write_text(json.dumps({
        "date": utc_tag().isoformat(),
        "calls": {PROVIDER: 1234},
        "cache_hits": 7,
        "cache_misses": 3,
    }))

    gate_a = ForecastBudgetGate(user_id=NUTZER_A)
    gate_a.record_call()

    stand = gate_a.snapshot()
    assert stand["calls_today"] == 1235, (
        "AC-9: der globale Bestandszaehler muss erhalten bleiben und nur um "
        "den neuen Aufruf steigen (Read-Modify-Write mit Merge, nie Replace)"
    )
    assert stand["cache_hits"] == 7 and stand["cache_misses"] == 3, (
        "AC-9: Client-unbekannte Bestandsfelder duerfen beim Schreiben nicht "
        "verloren gehen"
    )
    assert stand["user_calls_today"] == 1, (
        "AC-9: der neue Nutzer-Topf beginnt unabhaengig bei 0 und zaehlt nur "
        "den eigenen Aufruf -- kein rueckwirkender Split des globalen Stands"
    )


# ---------------------------------------------------------------------------
# Wertpruefung am Alarm-Pfad (AC-7 an der WIRKSTELLE)
#
# AC-7 prueft die gebundene SIGNATUR (`user_id` ohne Default). Sie sagt nichts
# ueber den WERT, der dort ankommt: ein Aufrufer, der still `None` einsetzt,
# erfuellt die Signatur und liefert die Fairness trotzdem als Nulloperation
# aus -- der Verbrauch landet nur im globalen Topf, Stufe 1 findet keinen
# Verursacher, und bei 81 % globaler Auslastung drosselt es wieder JEDEN.
#
# Geprueft wird deshalb die WIRKUNG, nicht die Weitergabe eines Arguments:
# das Produkt laeuft echt durch `TripAlertService._fetch_fresh_weather()`
# (kein Nachbau der Schleife), und danach wird der Nutzer-Topf ausgelesen.
# Nichts an dem, was hier geprueft wird, legt die Fixture selbst an -- den
# Zaehlerstand schreibt `ForecastBudgetGate.record_call()` aus dem
# Produktivpfad (`segment_weather.py`, VOR dem Provider-Aufruf).
# ---------------------------------------------------------------------------

class _ZaehlenderFakeProvider:
    """Netzfreier Fake-Provider (KEIN Mock/patch/MagicMock) -- gleiche
    Konstruktion wie `test_forecast_budget_gate.CountingFakeProvider`."""

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        from datetime import datetime, timezone

        from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider

        self.call_count += 1
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.2,
            run=datetime.now(timezone.utc), interp="grid_point",
        )
        basis = start or datetime.now(timezone.utc)
        return NormalizedTimeseries(
            meta=meta,
            data=[ForecastDataPoint(ts=basis + timedelta(hours=i), t2m_c=10.0 + i)
                  for i in range(3)],
        )


def _platzhalter_segment():
    """Ein Segment, das die Vorfilter von `_fetch_fresh_weather` passiert:
    beginnt heute (UTC), endet in der Zukunft."""
    from datetime import datetime, timezone

    from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment

    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    punkt = GPXPoint(lat=47.2692, lon=11.4041, elevation_m=1200.0)
    segment = TripSegment(
        segment_id="alarm-wertpruefung",
        start_point=punkt, end_point=punkt,
        start_time=jetzt, end_time=jetzt + timedelta(hours=3),
        duration_hours=3.0, distance_km=0.0, ascent_m=0, descent_m=0,
    )
    return SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def test_alarmpfad_bucht_den_abruf_im_topf_des_pruefenden_nutzers(monkeypatch):
    """Der `alert_check`-Abruf von `TripAlertService` muss die ECHTE Kennung
    bis in den Budget-Topf tragen.

    Mutations-Anker: wird in `trip_alert.py` an der `fetch_segment_weather`-
    Aufrufstelle `user_id=self._user_id` durch `user_id=None` ersetzt, bleibt
    der Nutzer-Topf leer und dieser Test wird rot -- waehrend AC-7 (reine
    Signaturpruefung) gruen bliebe.
    """
    import providers.base as provider_basis
    from services.trip_alert import TripAlertService
    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_weather_cache_for_tests()
    provider = _ZaehlenderFakeProvider()
    monkeypatch.setattr(provider_basis, "get_provider", lambda *a, **k: provider)

    dienst = TripAlertService(user_id=NUTZER_A)
    ergebnis = dienst._fetch_fresh_weather([_platzhalter_segment()])

    # Kontrollmessung gegen Vakuum-Gruen: ohne echten Upstream-Versuch haette
    # `record_call()` gar nicht laufen koennen, und die Zusicherung unten
    # waere nur die Abwesenheit von allem.
    assert provider.call_count == 1, (
        "Testvoraussetzung: der Alarm-Pfad muss genau EINEN echten "
        f"Upstream-Versuch ausloesen, tatsaechlich {provider.call_count}"
    )
    assert len(ergebnis) == 1, "Testvoraussetzung: ein Segment, ein Ergebnis"

    assert ForecastBudgetGate(user_id=NUTZER_A).snapshot()["user_calls_today"] == 1, (
        "Der alert_check-Abruf muss im Budget-Topf DES pruefenden Nutzers "
        "ankommen -- sonst kennt Stufe 1 den Verursacher nicht und drosselt "
        "bei Budget-Druck wieder alle (genau der Defekt aus #2387)"
    )
    assert ForecastBudgetGate(user_id=NUTZER_B).snapshot()["user_calls_today"] == 0, (
        "Gegenlesung (ADR-0003): der Abruf von Nutzer A darf im Topf von B "
        "NICHT auftauchen"
    )


def test_ortsvergleich_abrufpfad_bucht_im_topf_der_uebergebenen_kennung(monkeypatch):
    """Dieselbe Wertpruefung fuer den Ortsvergleichs-Abrufpfad.

    `test_ortsvergleich_abrufpfad_fuehrt_user_id_als_pflichtparameter`
    (AC-7) prueft die gebundene Signatur -- dass der Parameter existiert und
    keinen Default hat. Diese Zusicherung hier prueft, dass die uebergebene
    Kennung auch WIRKT: `CompareLocationWeatherSource.fetch()` muss sie bis
    zum Gate tragen. Wird sie an
    `compare_location_weather_source.py` auf dem Weg zu
    `fetch_segment_weather()` fallengelassen, bleibt AC-7 gruen und dieser
    Test wird rot.

    Trip- und Ortsvergleich-Pfad sind gleichrangig (PO-Vorgabe, Epic #1230):
    eine Wertpruefung nur am Trip-Pfad liesse den Vergleich unbewacht.
    """
    import providers.base as provider_basis
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_weather_cache_for_tests()
    provider = _ZaehlenderFakeProvider()
    monkeypatch.setattr(provider_basis, "get_provider", lambda *a, **k: provider)

    CompareLocationWeatherSource().fetch(
        "ort-wertpruefung", 47.2692, 11.4041, user_id=NUTZER_A,
    )

    assert provider.call_count == 1, (
        "Testvoraussetzung: der Ortsvergleichs-Abruf muss genau EINEN echten "
        f"Upstream-Versuch ausloesen, tatsaechlich {provider.call_count}"
    )
    assert ForecastBudgetGate(user_id=NUTZER_A).snapshot()["user_calls_today"] == 1, (
        "Die an fetch() uebergebene Kennung muss bis in den Budget-Topf "
        "durchschlagen -- ein auf dem Weg fallengelassenes user_id erfuellt "
        "die Signaturpruefung aus AC-7 und bucht den Verbrauch trotzdem "
        "unattributiert"
    )
    assert ForecastBudgetGate(user_id=NUTZER_B).snapshot()["user_calls_today"] == 0, (
        "Gegenlesung (ADR-0003): der Abruf fuer Nutzer A darf im Topf von B "
        "NICHT auftauchen"
    )


# ---------------------------------------------------------------------------
# Adversary Fix-Loop 1 (F001-F003): drei weitere Wertpruefungen.
#
# Gemessen war: eine Mutation auf `user_id=None` an diesen drei Stellen macht
# KEINEN Test rot -- 55 / 40 / 108 Tests blieben gruen. Die schwerste ist
# F003: das ist der produktive Scheduler-Versandpfad des taeglichen
# Briefings, dort hatte AC-1/AC-10 im echten Versand keine Absicherung.
# ---------------------------------------------------------------------------

def _stage_trip(trip_id: str):
    """Ein-Etappen-Trip mit zwei vermessenen Wegpunkten (Muster
    `tests/tdd/test_stage_weather_parity.py`)."""
    from app.trip import Stage, Trip, Waypoint

    from tests.helpers.ortstag import utc_tag as _utc_tag

    wp1 = Waypoint(id="g1", name="Start", lat=47.2692, lon=11.4041,
                   elevation_m=600, arrival_calculated="08:35")
    wp2 = Waypoint(id="g2", name="Ziel", lat=47.3010, lon=11.4500,
                   elevation_m=1200, arrival_calculated="14:35")
    stage = Stage(id="s1", name="Etappe 1", date=_utc_tag(), waypoints=[wp1, wp2])
    return Trip(id=trip_id, name=trip_id, stages=[stage])


def test_stage_weather_endpunkt_bucht_im_topf_der_uebergebenen_kennung():
    """F002: `compute_stage_weather()` traegt die Kennung des anfragenden
    Nutzers bis in den Budget-Topf.

    Der Aufrufer (`api/routers/internal.py`, Endpunkt
    `/api/_internal/trips/{trip_id}/stages-weather`) fuehrt `user_id` als
    Pflicht-Query-Parameter; `_fetch_one()` reicht sie an
    `fetch_segment_weather()` weiter. Wird sie dort fallengelassen, laeuft
    der Cockpit-Abruf jedes Nutzers unattributiert -- Stufe 1 kennt den
    Verursacher nicht.
    """
    from services.stage_weather import compute_stage_weather

    provider = _ZaehlenderFakeProvider()
    ergebnis = compute_stage_weather(
        _stage_trip("trip-stage-wertpruefung"), provider, user_id=NUTZER_A,
    )

    assert provider.call_count >= 1, (
        "Testvoraussetzung: der Etappen-Abruf muss mindestens EINEN echten "
        f"Upstream-Versuch ausloesen, tatsaechlich {provider.call_count}"
    )
    assert "s1" in ergebnis, "Testvoraussetzung: die Etappe muss ausgewertet werden"

    assert ForecastBudgetGate(user_id=NUTZER_A).snapshot()["user_calls_today"] >= 1, (
        "F002: der Etappen-Wetterabruf muss im Budget-Topf DES anfragenden "
        "Nutzers ankommen -- sonst bleibt der Cockpit-Verbrauch "
        "unattributiert und Stufe 1 findet keinen Verursacher"
    )
    assert ForecastBudgetGate(user_id=NUTZER_B).snapshot()["user_calls_today"] == 0, (
        "Gegenlesung (ADR-0003): der Abruf fuer Nutzer A darf im Topf von B "
        "NICHT auftauchen"
    )


def test_scheduler_nachtabruf_bucht_im_topf_des_versendenden_nutzers(monkeypatch):
    """F003 (schwerster der drei): der PRODUKTIVE Versandpfad.

    `TripReportSchedulerService._fetch_night_weather()` beschafft die
    Nachtreihe fuer das taegliche Briefing. Faellt die Kennung hier weg,
    hat die Kernzusicherung des Tickets (AC-1/AC-10: nur der
    Vielverbraucher wird gedrosselt) im echten Versand keine Grundlage --
    der gesamte Nachtabruf aller Nutzer landet unattributiert im globalen
    Topf.
    """
    import providers.base as provider_basis
    from services.trip_report_scheduler import TripReportSchedulerService
    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_weather_cache_for_tests()
    provider = _ZaehlenderFakeProvider()
    monkeypatch.setattr(provider_basis, "get_provider", lambda *a, **k: provider)

    dienst = TripReportSchedulerService(user_id=NUTZER_A)
    reihe = dienst._fetch_night_weather(_platzhalter_segment())

    assert provider.call_count == 1, (
        "Testvoraussetzung: der Nachtabruf muss genau EINEN echten "
        f"Upstream-Versuch ausloesen, tatsaechlich {provider.call_count} "
        "(`fetch_night_weather` faengt Fehler intern ab -- ohne diese "
        "Kontrollmessung waere der Test auch bei einem stillen Fehlschlag "
        "gruen)"
    )
    assert reihe is not None, "Testvoraussetzung: die Nachtreihe muss ankommen"

    assert ForecastBudgetGate(user_id=NUTZER_A).snapshot()["user_calls_today"] == 1, (
        "F003: der Nachtabruf des taeglichen Briefings muss im Budget-Topf "
        "DES versendenden Nutzers ankommen -- ohne ihn hat AC-1/AC-10 im "
        "produktiven Versandpfad keine Grundlage"
    )
    assert ForecastBudgetGate(user_id=NUTZER_B).snapshot()["user_calls_today"] == 0, (
        "Gegenlesung (ADR-0003): der Versand fuer Nutzer A darf im Topf von "
        "B NICHT auftauchen"
    )


def test_vorschau_reicht_die_kennung_bis_in_den_nachtabruf(monkeypatch):
    """F001: die Vorschau (`PreviewService._build_report`) traegt die
    Kennung des anfragenden Nutzers in den Nachtabruf.

    Anders als F002/F003 ist hier die Topf-Messung allein NICHT
    trennscharf: derselbe Lauf bucht auch die Etappen-Abrufe, die ihre
    Kennung ueber einen anderen Weg bekommen -- eine Mutation nur am
    Nacht-Aufruf bliebe im Topf unsichtbar. Deshalb wird die ECHTE
    `fetch_night_weather` zusaetzlich mit einem reinen Aufruf-Rekorder
    umwickelt (kein Mock-Rueckgabewert, der echte Weg laeuft weiter --
    Muster `tests/unit/test_preview_night_block.py`), der die tatsaechlich
    angekommene Kennung festhaelt.
    """
    import dataclasses

    import services.segment_weather as sw
    from app.trip import Stage, Trip, Waypoint
    from services.preview_service import PreviewService
    from app.metric_catalog import build_default_display_config

    from tests.helpers.ortstag import utc_tag as _utc_tag

    empfangen: list = []
    echte_funktion = sw.fetch_night_weather

    def _rekorder(seg, provider=None, *, user_id=None):
        empfangen.append(user_id)
        return echte_funktion(seg, provider=provider, user_id=user_id)

    monkeypatch.setattr(sw, "fetch_night_weather", _rekorder)

    ziel = _utc_tag()
    wp1 = Waypoint(id="G1", name="Start", lat=47.2692, lon=11.4041, elevation_m=600)
    wp2 = Waypoint(id="G2", name="Ziel", lat=47.3010, lon=11.4500, elevation_m=1200)
    dc = build_default_display_config(trip_id="vorschau-nacht-trip")
    dc = dataclasses.replace(dc, show_night_block=True)
    trip = Trip(
        id="vorschau-nacht-trip", name="Vorschau-Nacht-Trip",
        stages=[Stage(id="T1", name="Etappe 1", date=ziel, waypoints=[wp1, wp2])],
        display_config=dc,
    )

    from datetime import datetime, timezone

    PreviewService()._build_report(
        trip, ziel, "evening", now_utc=datetime.now(timezone.utc), demo=True,
        user_id=NUTZER_A,
    )

    assert empfangen, (
        "Testvoraussetzung: die Vorschau muss Nachtdaten beschaffen -- ohne "
        "Aufruf koennte diese Zusicherung nichts bewachen"
    )
    assert empfangen[0] == NUTZER_A, (
        "F001: die Vorschau muss die Kennung des anfragenden Nutzers in den "
        f"Nachtabruf durchreichen, angekommen ist {empfangen[0]!r} -- ein "
        "stilles None bucht den Verbrauch unattributiert"
    )
    assert ForecastBudgetGate(user_id=NUTZER_B).snapshot()["user_calls_today"] == 0, (
        "Gegenlesung (ADR-0003): die Vorschau fuer Nutzer A darf im Topf von "
        "B NICHT auftauchen"
    )
