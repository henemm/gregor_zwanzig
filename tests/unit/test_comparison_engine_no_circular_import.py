"""Adversary-Fund F001 (#1391/#1392): kein Circular Import beim ersten Touch
von `output.metric_format` ueber den neuen `summarize_points()`-Aufrufpfad.

Ursache (verifiziert): `output/metric_format.py` importiert auf Modulebene
(fuer den `tone_css`-Re-Export) `output.renderers.email.design_tokens`. Wird
`output.metric_format` als ALLERERSTES beruehrt (bevor irgendetwas
`output.renderers`/`output.renderers.email` initialisiert hat), muss Python
zuerst deren `__init__.py`-Kette ausfuehren -- die importiert
`output.renderers.day_window`, das wiederum (Modulkopf) `max_thunder`/
`thunder_ordinal` aus `output.metric_format` braucht: ein Selbstbezug
innerhalb des `output`-Pakets, der IMMER schon strukturell moeglich war.

Vor #1391/#1392 hat kein Aufrufer von `_compute_thunder_level()`
(`weather_metrics.py`, lazyer Import von `max_thunder`) `output.metric_format`
als ERSTEN Touch in einem Prozess ausgeloest, der nicht vorher schon
`output.renderers` geladen hatte. Der neue `summarize_points()`-Aufruf in
`comparison_engine.fetch_forecast_for_location()`/`ComparisonEngine.run()`
kann das jetzt -- z.B. in einem frischen Interpreter, der NUR
`services.comparison_engine` importiert (kein vorheriger `api.main`-/
`output.renderers`-Import). Der bestehende Regressionstest
`tests/tdd/test_a2_compare_openmeteo_metrics.py` deckt genau diesen Fall aus
Nutzersicht ab (ein Ort faellt im Vergleich mit `result["error"]` komplett
aus). Dieser Test hier prueft zusaetzlich BEIDE Aufrufpfade explizit in einem
echten Subprozess (kein Mock, kein Attribut-Rebind von
`fetch_forecast_for_location`) -- der Adversary hat zu Recht bemerkt, dass
`test_comparison_engine_matches_canonical_daily_cloud_layer_values`
(`test_compare_daily_cloud_layers.py`) genau diese Funktion per Rebind
ersetzt und den Bug deshalb nie ausfuehrt.

Netzfrei: `GZ_TEST_FIXTURE_DIR` zeigt den Subprozess auf
`fixtures/openmeteo/` (dieselbe Fixture wie `test_a2_...`), keine
`@pytest.mark.live`-Markierung noetig.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
FIXTURE_DIR = PROJECT_ROOT / "fixtures" / "openmeteo"

_SCRIPT = """
import sys
from datetime import date

from app.user import SavedLocation
from services.comparison_engine import ComparisonEngine, fetch_forecast_for_location

loc = SavedLocation(
    id="fresh-interp-1391-1392", name="Innsbruck",
    lat=47.2692, lon=11.4041, elevation_m=574,
)

# Weg 1: fetch_forecast_for_location() -- die Stelle, die der Adversary-Fund
# betraf (comparison_engine.py, zweite Duplikat-Stelle, :453). Bisher nur
# result["error"] geprueft (Adversary-Fund Runde 2): jetzt zusaetzlich der
# tatsaechlich gerechnete Tageswert, nicht nur "kein Fehler".
result = fetch_forecast_for_location(loc, hours=48)
if result["error"] is not None:
    print(f"FAIL fetch_forecast_for_location: {result['error']}")
    sys.exit(1)
fetch_cloud_low = result.get("cloud_low_avg")

# Weg 2: ComparisonEngine.run() -- die erste Duplikat-Stelle (:203-211),
# echter Aufrufpfad ohne Attribut-Rebind von fetch_forecast_for_location.
cmp_result = ComparisonEngine.run(
    locations=[loc],
    time_window=(0, 23),
    target_date=date.today(),
    forecast_hours=48,
    official_alerts_enabled=False,
)
loc_result = cmp_result.locations[0]
if loc_result.error is not None:
    print(f"FAIL ComparisonEngine.run: {loc_result.error}")
    sys.exit(1)
engine_cloud_low = loc_result.cloud_low_avg

print(f"CLOUD_LOW_AVG fetch={fetch_cloud_low} engine={engine_cloud_low}")
print("FRESH_INTERPRETER_OK")
"""


def _run_in_fresh_interpreter() -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GZ_TEST_FIXTURE_DIR"] = str(FIXTURE_DIR)
    return subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=str(SRC_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_both_comparison_engine_paths_survive_fresh_interpreter_import():
    """F001-Nachweis: ein frischer Interpreter, der NUR
    `services.comparison_engine` importiert (kein vorheriger
    `output.renderers`-Import, wie er in der laufenden pytest-Session oder im
    Server durch andere Module laengst passiert waere), darf beim ersten
    `summarize_points()`-Aufruf ueber KEINEN der beiden Aufrufpfade an einem
    Circular Import scheitern.
    """
    proc = _run_in_fresh_interpreter()

    assert proc.returncode == 0, (
        f"Frischer Interpreter ist abgestuerzt (returncode={proc.returncode}).\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "FRESH_INTERPRETER_OK" in proc.stdout, (
        f"Erwartetes Erfolgs-Sentinel fehlt in stdout.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "circular import" not in proc.stdout.lower(), (
        f"Circular-Import-Fehler im Subprozess:\n{proc.stdout}"
    )

    # Adversary-Fund Runde 2: "kein Fehler" allein beweist nicht, dass
    # fetch_forecast_for_location() -- der Pfad, in dem der Bug steckte --
    # auch das RICHTIGE rechnet. Werte-Zusicherung statt Momentaufnahme:
    # beide Wege muessen fuer dieselbe Fixture einen plausiblen, GLEICHEN
    # Tageswert liefern (cloud_low_pct ist in der Innsbruck-Fixture konstant
    # 30 ueber alle 72 Stunden -- die einzige der drei Bewoelkungsstufen, die
    # der FixtureProvider ueberhaupt befuellt).
    line = next(
        (l for l in proc.stdout.splitlines() if l.startswith("CLOUD_LOW_AVG")), None
    )
    assert line is not None, f"Wert-Zeile fehlt in stdout:\n{proc.stdout}"
    values = dict(part.split("=") for part in line.split()[1:])
    fetch_val, engine_val = values["fetch"], values["engine"]
    assert fetch_val != "None", (
        f"fetch_forecast_for_location() liefert kein cloud_low_avg: {line}"
    )
    assert 0 <= int(fetch_val) <= 100, f"cloud_low_avg unplausibel: {line}"
    assert fetch_val == engine_val, (
        f"fetch_forecast_for_location() und ComparisonEngine.run() liefern "
        f"fuer dieselbe Fixture unterschiedliche Tageswerte: {line}"
    )
