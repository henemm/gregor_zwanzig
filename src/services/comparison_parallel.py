"""
Service: run_comparison_parallel -- die Orte eines Vergleichs GLEICHZEITIG rechnen.

Scheibe B1 von Issue #1765. Die Vergleichs-Vorschau verarbeitete die Orte eines
Presets nacheinander (~25 s je Ort) und riss ab drei Orten die 60-Sekunden-Grenze
zwischen Go-API und nginx. Dieser Baustein legt die Parallelitaet AUSSERHALB der
Engine an: ``ComparisonEngine.run()`` bleibt unveraendert und wird je Ort einmal
mit genau diesem einen Ort aufgerufen.

Bewusst ein eigenes, neutrales Modul (weder in ``comparison_engine.py`` noch in
``compare_preview_service.py``): so ist "die Engine bleibt unangetastet"
mechanisch nachpruefbar, und die uebrigen Aufrufwege (Versand, Sofortvergleich)
koennen in der Folgescheibe andocken, ohne etwas umzubauen.

Vorbild im Repo: ``services/stage_weather.py:170-183`` (Executor-Aufbau,
indexierte Vorbelegung statt Anhaengen, duenner Fehler-Wrapper je Einheit).

Spec: docs/specs/modules/fix_1765_b1_compare_vorschau_parallel.md
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, cast

from app.user import ComparisonResult, LocationResult
from services.comparison_engine import COMPARE_FORECAST_HOURS

if TYPE_CHECKING:
    from datetime import date

    from app.profile import ActivityProfile
    from app.user import SavedLocation

logger = logging.getLogger(__name__)

# Bewusst niedriger als das Vorbild (``min(len, 8)`` in stage_weather.py): das
# Meteo-France-Konto wird von allen Nutzern GEMEINSAM genutzt und ist nicht
# aktiv gedrosselt -- siehe docs/reference/decision_matrix.md:231-254.
MAX_PARALLEL_LOCATIONS = 4


def _run_one_location(
    loc: "SavedLocation",
    *,
    time_window: tuple[int, int],
    target_date: "date",
    forecast_hours: int,
    profile: Optional["ActivityProfile"],
    official_alerts_enabled: bool,
    call_source: Optional[str],
) -> LocationResult:
    """Ein Ort, ein Engine-Lauf.

    Faengt bewusst NICHTS ab: ``ComparisonEngine.run()`` fasst einen echten
    Ortsfehler bereits selbst in ein ``LocationResult(error=...)`` und wirft
    dafuer NICHT (comparison_engine.py:128-147 und :369-381). Was hier dennoch
    als Ausnahme herauskommt, ist per Definition kein Ortsfehler, sondern
    systemisch (z.B. die ``Settings()``-Konstruktion VOR der Ortsschleife,
    comparison_engine.py:121). Ob daraus ein Ortsfehler wird (AC-3) oder der
    ganze Lauf abbricht (AC-8), entscheidet erst der Einsammler in
    ``run_comparison_parallel`` -- nur dort ist bekannt, ob ALLE Orte
    betroffen sind.

    Die Diagnose-Quelle wird hier gesetzt, nicht beim Aufrufer: ein
    ``ThreadPoolExecutor`` reicht den Kontext NICHT an seine Arbeiter weiter.
    """
    import services.comparison_engine as ce_mod
    from providers.call_log import override_call_source

    quelle = override_call_source(call_source) if call_source else nullcontext()
    with quelle:
        result = ce_mod.ComparisonEngine.run(
            locations=[loc],
            time_window=time_window,
            target_date=target_date,
            forecast_hours=forecast_hours,
            profile=profile,
            official_alerts_enabled=official_alerts_enabled,
        )
    return result.locations[0]


def run_comparison_parallel(
    locations: List["SavedLocation"],
    time_window: tuple[int, int],
    target_date: "date",
    forecast_hours: int = COMPARE_FORECAST_HOURS,
    profile: Optional["ActivityProfile"] = None,
    official_alerts_enabled: bool = True,
    *,
    call_source: Optional[str] = None,
) -> ComparisonResult:
    """Wie ``ComparisonEngine.run()``, nur werden die Orte gleichzeitig statt
    nacheinander berechnet. Signatur, Parameter und Ergebnisform sind identisch.

    Die Ortsreihenfolge des Ergebnisses ist die KONFIGURIERTE, nicht die
    Fertigstellungsreihenfolge: jedes Teilergebnis landet ueber seinen Index.

    Raises:
        Exception: die erste aufgefangene Ausnahme, wenn JEDER Ort mit einer
            Ausnahme scheitert -- das ist eine systemische Stoerung und behaelt
            damit die Fehlerform von vor der Parallelisierung (AC-8).
    """
    locations = list(locations)
    # EIN Zeitstempel fuer den gesamten Lauf, vor dem Start -- nicht je Ort und
    # nicht aus einem Teilergebnis (das haenge sonst an der Fertigstellung).
    # Naive UTC statt nackter Prozessuhr (Hausnorm #1345): genau so lesen die
    # Renderer das Feld (``local_stamp`` -> ``utils.timezone._as_utc``), und
    # ``tests/test_output_timezone_guard.py`` verbietet ``datetime.now()`` ohne
    # Zeitzone im Entscheidungs-/Ausgabepfad.
    created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    fetched: List[Optional[LocationResult]] = [None] * len(locations)
    fehler: List[tuple[int, Exception]] = []
    if locations:  # ``min(0, 4)`` waere ein ungueltiges ``max_workers``
        with ThreadPoolExecutor(
            max_workers=min(len(locations), MAX_PARALLEL_LOCATIONS)
        ) as executor:
            future_to_idx = {
                executor.submit(
                    _run_one_location,
                    loc,
                    time_window=time_window,
                    target_date=target_date,
                    forecast_hours=forecast_hours,
                    profile=profile,
                    official_alerts_enabled=official_alerts_enabled,
                    call_source=call_source,
                ): idx
                for idx, loc in enumerate(locations)
            }
            for future, idx in future_to_idx.items():
                try:
                    fetched[idx] = future.result()
                except Exception as exc:  # noqa: BLE001 -- Einordnung folgt unten
                    logger.warning(
                        "run_comparison_parallel: Ort %r fehlgeschlagen",
                        getattr(locations[idx], "id", idx), exc_info=True,
                    )
                    fehler.append((idx, exc))

    # AC-8 (Fehlerformen unveraendert): scheitert JEDER Ort mit einer Ausnahme,
    # ist die Stoerung systemisch -- vor der Parallelisierung lief die Engine
    # EINMAL fuer alle Orte, eine solche Ausnahme schlug bis zum Router durch
    # und wurde dort zu HTTP 503 (api/routers/preview.py:99-110). N
    # gleichlautende Ortsfehler in einer 200er-Antwort waeren eine ANDERE
    # Fehlerform. Bei genau EINEM Ort gilt dasselbe: einen echten Ortsfehler
    # haette ``run()`` selbst abgefangen (s. ``_run_one_location``).
    if fehler and len(fehler) == len(locations):
        raise fehler[0][1]
    # Teilausfall bleibt Ortsfehler (AC-3): der betroffene Ort erscheint MIT
    # Fehlermeldung an SEINER Position, die uebrigen behalten ihre Daten.
    for idx, exc in fehler:
        fetched[idx] = LocationResult(
            location=locations[idx], error=str(exc) or type(exc).__name__,
        )

    # ``fetched`` ist danach luecklos besetzt: jeder Index traegt entweder das
    # Engine-Ergebnis oder ein LocationResult mit gesetztem ``error``.
    return ComparisonResult(
        locations=cast(List[LocationResult], fetched),
        time_window=time_window,
        target_date=target_date,
        created_at=created_at,
    )
