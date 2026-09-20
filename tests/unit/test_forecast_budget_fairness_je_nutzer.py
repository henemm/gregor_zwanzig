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

    with caplog.at_level("WARNING"):
        ergebnis = gate_a.allow("polling")

    assert ergebnis is True, (
        "AC-4 (E3): ein unlesbarer Nutzer-Topf gilt als 'nicht ueberschritten' "
        "-- ein Lesefehler darf nie zur Drosselung fuehren"
    )
    assert caplog.records, (
        "AC-4: der verschluckte Lesefehler muss als WARNING sichtbar werden, "
        "sonst ist der Fail-open-Weg im Betrieb unbeobachtbar"
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
