"""Issue #1397 (Tageskontingent-Fund, S1c-Nachbesserung): MeteoAlarmBudgetGate.

SPEC: docs/specs/modules/warn_service_consumption.md
Ausfuehrung:
    uv run pytest tests/unit/test_meteoalarm_budget_gate.py -v

Kern-Schicht, netzfrei. Muster ``tests/unit/test_forecast_budget_gate.py``
(gleiche Reload-Merge-Write-/Fail-open-Eigenschaften wie ``ForecastBudgetGate``,
hier ohne Prioritaetsstufen -- ein einfaches An/Aus). Zaehlerdatei wird
direkt vorbereitet (kein Mock der Klasse).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from app.loader import get_data_root
from services.official_alerts.meteoalarm_budget import MeteoAlarmBudgetGate


def _budget_path():
    return get_data_root() / "diagnostics" / "meteoalarm_budget.json"


def _write_budget(calls: int) -> None:
    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": date.today().isoformat(), "calls": calls}))


def _write_corrupt_budget() -> None:
    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-valid-json,,,")


# ---------------------------------------------------------------------------
# Grundverhalten: unter/ueber Budget, fehlende/kaputte Datei (fail-open)
# ---------------------------------------------------------------------------

def test_below_budget_allows_calls():
    _write_budget(calls=50)
    gate = MeteoAlarmBudgetGate()
    assert gate.allow() is True


def test_at_or_above_budget_blocks_calls():
    _write_budget(calls=MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET)
    gate = MeteoAlarmBudgetGate()
    assert gate.allow() is False, (
        "genau am Budget (nicht erst darueber) muss bereits blockiert werden"
    )


def test_one_below_budget_still_allows():
    _write_budget(calls=MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET - 1)
    gate = MeteoAlarmBudgetGate()
    assert gate.allow() is True


def test_missing_counter_file_never_blocks():
    assert not _budget_path().exists()
    gate = MeteoAlarmBudgetGate()
    assert gate.allow() is True, "fehlende Zaehlerdatei (erster Zugriff) darf nie blockieren"


def test_corrupted_counter_file_never_blocks():
    _write_corrupt_budget()
    gate = MeteoAlarmBudgetGate()
    assert gate.allow() is True, "kaputte Zaehlerdatei darf NIE blockieren (fail-open)"


# ---------------------------------------------------------------------------
# record_call() zaehlt tatsaechlich hoch, ueber alle Laender gemeinsam
# ---------------------------------------------------------------------------

def test_record_call_increments_shared_counter_across_countries():
    """Ein Tagesbudget UEBER ALLE Laender (kein pro-Land-Zaehler) --
    AT- und IT-Abrufe zehren vom selben Konto."""
    gate = MeteoAlarmBudgetGate()
    assert gate.allow() is True
    for _ in range(MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET):
        gate.record_call()
    assert gate.allow() is False, (
        f"nach {MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET} Aufrufen muss das "
        f"gemeinsame Budget erschoepft sein"
    )


# ---------------------------------------------------------------------------
# GZ_METEOALARM_DAILY_BUDGET: ENV-Override ohne Deploy
# ---------------------------------------------------------------------------

def test_env_override_raises_budget(monkeypatch):
    monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "5000")
    _write_budget(calls=1000)
    gate = MeteoAlarmBudgetGate()
    assert gate.daily_budget == 5000
    assert gate.allow() is True, "1000 < 5000 (ENV-Override) muss durchlassen"


def test_env_override_invalid_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "nicht-lesbar")
    gate = MeteoAlarmBudgetGate()
    assert gate.daily_budget == MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET, (
        "unlesbarer ENV-Wert darf den Default nicht kippen (fail-open)"
    )


def test_env_override_non_positive_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "0")
    gate = MeteoAlarmBudgetGate()
    assert gate.daily_budget == MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET


# ---------------------------------------------------------------------------
# UTC-Tageswechsel (Muster ForecastBudgetGate Adversary-Fund F002)
# ---------------------------------------------------------------------------

def test_counter_from_yesterday_utc_is_ignored_at_todays_utc_boundary():
    now_utc = datetime.now(timezone.utc)
    yesterday_utc = (now_utc - timedelta(days=1)).date().isoformat()

    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "date": yesterday_utc,
        "calls": MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET,  # gestern ausgeschoepft
    }))

    gate = MeteoAlarmBudgetGate()

    assert gate.allow(now=now_utc) is True, (
        "ein 'gestern' (UTC) ausgeschoepfter Zaehlerstand darf am heutigen "
        "UTC-Tag NICHT mehr wirken"
    )


def test_counter_from_today_utc_still_applies_with_injected_now():
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.date().isoformat()

    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "date": today_utc,
        "calls": MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET,
    }))

    gate = MeteoAlarmBudgetGate()

    assert gate.allow(now=now_utc) is False, (
        "ein heutiger (UTC), ausgeschoepfter Zaehlerstand muss weiterhin "
        "ganz normal blockieren"
    )


def test_snapshot_reports_usage_ratio():
    _write_budget(calls=50)
    gate = MeteoAlarmBudgetGate()
    snap = gate.snapshot()
    assert snap["status"] == "ok"
    assert snap["calls_today"] == 50
    assert snap["daily_budget"] == MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET
    assert snap["usage_ratio"] == 50 / MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET


def test_snapshot_fail_open_on_corrupted_file():
    _write_corrupt_budget()
    gate = MeteoAlarmBudgetGate()
    snap = gate.snapshot()
    assert snap["status"] == "unavailable"
    assert snap["calls_today"] == 0


# ---------------------------------------------------------------------------
# Adversary-Fund (Runde 2, 2026-07-27): rollierendes 24h-Fenster statt
# UTC-Kalendertagsgrenze. Belegte Messung: 429 um 10:37 UTC, x-ratelimit-
# reset 86.399s spaeter (~10:37 des Folgetags) -- NICHT ~48.180s bis UTC-
# Mitternacht. record_observed_reset() haelt den ECHTEN Reset-Zeitpunkt
# fest; allow() bleibt bis dahin HART gesperrt, unabhaengig vom Zaehler.
# ---------------------------------------------------------------------------

def test_observed_daily_reset_locks_until_real_reset_not_utc_midnight():
    """Belegte Messung: Sperre tritt um 10:37 UTC ein, ``x-ratelimit-reset``
    meldet 86.399s spaeter (10:37 des Folgetags). GIVEN dieser Reset-
    Zeitpunkt wurde festgehalten, WHEN ``allow()`` um 00:30 des Folgetags
    geprueft wird (UTC-Mitternacht laengst vorbei), THEN bleibt es
    gesperrt. WHEN um 10:38 des Folgetags (nach dem ECHTEN Reset) geprueft
    wird, THEN oeffnet es wieder."""
    observed_at = datetime(2026, 7, 27, 10, 37, 0, tzinfo=timezone.utc)
    reset_at = observed_at + timedelta(seconds=86399)  # belegte Messung

    gate = MeteoAlarmBudgetGate()
    gate.record_observed_reset(reset_at.timestamp(), now=observed_at)

    midnight_next_day_plus_30 = datetime(2026, 7, 28, 0, 30, 0, tzinfo=timezone.utc)
    assert gate.allow(now=midnight_next_day_plus_30) is False, (
        "um 00:30 des Folgetags (UTC-Mitternacht laengst vorbei, aber VOR dem "
        "echten Reset) muss das Budget weiterhin gesperrt sein"
    )

    just_after_reset = datetime(2026, 7, 28, 10, 38, 0, tzinfo=timezone.utc)
    assert gate.allow(now=just_after_reset) is True, (
        "nach dem ECHTEN Reset-Zeitpunkt (10:37 UTC des Folgetags) muss das "
        "Budget wieder oeffnen"
    )


def test_observed_reset_locks_even_far_below_own_call_counter():
    """Kern des Funds: der beobachtete Reset sperrt UNABHAENGIG vom eigenen
    Zaehlerstand -- selbst wenn dieser weit unter dem Budget liegt (unser
    Zaehler ist nur eine Selbstbeschraenkung, der Reset die einzige echte
    Information ueber die Gegenseite)."""
    observed_at = datetime(2026, 7, 27, 10, 37, 0, tzinfo=timezone.utc)
    reset_at = observed_at + timedelta(seconds=86399)

    _write_budget(calls=1)  # weit unter dem Budget (200)
    gate = MeteoAlarmBudgetGate()
    gate.record_observed_reset(reset_at.timestamp(), now=observed_at)

    assert gate.allow(now=observed_at + timedelta(minutes=5)) is False, (
        "ein niedriger Zaehlerstand darf die Reset-Sperre NICHT aufheben"
    )


def test_observed_reset_is_capped_against_absurd_values():
    """GIVEN ein absurd weit in der Zukunft liegender Reset-Zeitpunkt
    (z.B. manipulierter/kaputter Header), WHEN ``record_observed_reset()``
    ihn persistiert, THEN wird er auf ``MAX_RESET_HORIZON_SECONDS``
    gedeckelt -- ein einzelner falscher Wert darf den Dienst nicht
    monatelang lahmlegen."""
    now = datetime(2026, 7, 27, 10, 37, 0, tzinfo=timezone.utc)
    absurd_reset = (now + timedelta(days=365)).timestamp()

    gate = MeteoAlarmBudgetGate()
    gate.record_observed_reset(absurd_reset, now=now)

    just_before_cap = now + timedelta(seconds=MeteoAlarmBudgetGate.MAX_RESET_HORIZON_SECONDS - 60)
    just_after_cap = now + timedelta(seconds=MeteoAlarmBudgetGate.MAX_RESET_HORIZON_SECONDS + 60)

    assert gate.allow(now=just_before_cap) is False, "kurz vor dem Deckel muss noch gesperrt sein"
    assert gate.allow(now=just_after_cap) is True, (
        "kurz NACH dem Deckel (MAX_RESET_HORIZON_SECONDS) muss wieder offen sein, "
        "obwohl der gemeldete Reset noch viel spaeter gelegen haette"
    )


def test_counter_resets_after_observed_reset_passes():
    """GIVEN ein beobachteter Reset ist bereits VORUEBER, WHEN
    ``allow()``/``record_call()`` danach aufgerufen werden, THEN startet
    der Zaehler wieder bei 0 -- kein Uebertrag aus dem vorherigen Fenster."""
    observed_at = datetime(2026, 7, 27, 10, 37, 0, tzinfo=timezone.utc)
    reset_at = observed_at + timedelta(seconds=86399)

    _write_budget(calls=199)  # fast ausgeschoepft VOR dem Reset
    gate = MeteoAlarmBudgetGate()
    gate.record_observed_reset(reset_at.timestamp(), now=observed_at)

    after_reset = reset_at + timedelta(minutes=1)
    assert gate.allow(now=after_reset) is True, (
        "nach dem Reset muss der Zaehler wieder Luft haben, nicht den alten Stand fortfuehren"
    )
    snap = gate.snapshot()
    # snapshot() nutzt now=None (echte Uhr) -- daher hier nur ueber allow()
    # mit injiziertem now geprueft; ein direkter Zaehler-Check erfolgt ueber
    # eine frische Zustandsabfrage mit derselben injizierten Zeit:
    assert gate._load_state(now=after_reset)["calls"] == 0, (
        f"Zaehler muss nach dem Reset auf 0 stehen, war {gate._load_state(now=after_reset)['calls']}"
    )


def test_fallback_to_utc_boundary_when_no_reset_ever_observed():
    """Gegenprobe: OHNE je einen Reset beobachtet zu haben, bleibt das
    Verhalten die alte UTC-Kalendertagsgrenze (Bestandsverhalten,
    Rueckwaertskompatibilitaet mit Zaehlerdateien ohne
    ``observed_reset_ts``-Feld)."""
    now_utc = datetime.now(timezone.utc)
    yesterday_utc = (now_utc - timedelta(days=1)).date().isoformat()

    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "date": yesterday_utc,
        "calls": MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET,
    }))  # KEIN observed_reset_ts-Feld -- altes Dateiformat

    gate = MeteoAlarmBudgetGate()

    assert gate.allow(now=now_utc) is True, (
        "ohne je beobachteten Reset bleibt die UTC-Tagesgrenze der Fallback"
    )
