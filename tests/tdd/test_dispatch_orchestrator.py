"""TDD RED — Issue #1207: EIN Versand-Orchestrator fuer Trip + Compare.

SPEC: docs/specs/modules/dispatch_orchestrator.md (AC-1..AC-5)
CONTEXT: docs/context/rework-1207-versand-orchestrator.md

RED-Phase: `src/services/dispatch_orchestrator.py` existiert noch nicht.
`run_briefing_dispatch(kind, user_id, hour)` + Strategy-Adapter
`TripDispatchStrategy`/`CompareDispatchStrategy` sowie die Registry
`_STRATEGY` fehlen komplett -> jeder Import schlaegt mit ImportError fehl.

KEINE Mocks — echte tmp-User unter dem isolierten Test-Datenroot
(`app.loader.get_data_dir`, autouse-Fixture `tests/conftest.py::_isolate_data_root`),
keine gemockten Loader/Services. Die beiden Struktur-Guards (AC-1/AC-2) sind
per `# doc-compliance-test` markiert (CLAUDE.md-Ausnahme fuer Quelltext-
Introspektion statt Verhaltensnachweis) und pruefen Delegation bzw.
Config-Zugriffspfad per `inspect`/AST.
"""
from __future__ import annotations

import ast
import inspect
import json
import uuid
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# --- Test-Fixtures (kein Mock — echter isolierter tmp-User) ---------------


def _fresh_user_id(suffix: str) -> str:
    return f"tdd-1207-{suffix}-{uuid.uuid4().hex[:8]}"


def _make_isolated_user(user_id: str) -> None:
    """Legt einen echten (isolierten) Test-User ohne faellige Trips/Presets an.

    Nutzt `app.loader.get_data_dir`, respektiert also die autouse-Fixture
    `_isolate_data_root` (tests/conftest.py) — kein Schreibzugriff auf das
    echte `data/users/`.
    """
    from app.loader import get_data_dir

    udir = get_data_dir(user_id)
    udir.mkdir(parents=True, exist_ok=True)
    (udir / "user.json").write_text(
        json.dumps({"id": user_id, "mail_to": "gregor-test@henemm.com"}),
        encoding="utf-8",
    )


def _strategy_delay(strategy_obj) -> float:
    """Normalisiert Klasse vs. Instanz — Spec legt nicht fest, ob `_STRATEGY`
    Klassen oder Instanzen registriert."""
    try:
        instance = strategy_obj() if isinstance(strategy_obj, type) else strategy_obj
        return instance.inter_mail_delay
    except TypeError:
        # Konstruktor verlangt Pflichtargumente -> Klassenattribut pruefen.
        return strategy_obj.inter_mail_delay


# --- AC-1: gemeinsamer Einstieg existiert ---------------------------------


def test_orchestrator_module_and_entry_exist():
    """AC-1: `run_briefing_dispatch` + beide Strategy-Adapter sind importierbar
    und der Einstieg ist aufrufbar (Modul-Existenz + Signatur-Kontrakt)."""
    from src.services.dispatch_orchestrator import (
        CompareDispatchStrategy,
        TripDispatchStrategy,
        run_briefing_dispatch,
    )

    assert callable(run_briefing_dispatch)
    assert TripDispatchStrategy is not None
    assert CompareDispatchStrategy is not None


def test_strategy_registry_covers_both_kinds():
    """AC-1: `_STRATEGY` deckt beide `kind`-Werte ab (`route`/`vergleich`) —
    kein dritter Versandweg, keine fehlende Zuordnung."""
    from src.services.dispatch_orchestrator import _STRATEGY

    assert "route" in _STRATEGY
    assert "vergleich" in _STRATEGY
    assert _STRATEGY["route"] is not None
    assert _STRATEGY["vergleich"] is not None


# --- HIGH-Risiko 1: Inter-Mail-Delay bleibt pro kind erhalten -------------


def test_trip_inter_mail_delay_is_two_seconds():
    """HIGH-Risiko-Punkt 1: Trip behaelt das 2s-Rate-Limit-Delay
    (Catch-up-Sends ausgenommen, s. Spec) — darf durch die Konsolidierung
    NICHT auf 0 absinken."""
    from src.services.dispatch_orchestrator import TripDispatchStrategy

    assert _strategy_delay(TripDispatchStrategy) == 2.0


def test_compare_inter_mail_delay_is_two_seconds():
    """PO-Entscheidung 2026-07-16: Compare bekommt dieselbe 2s-Sendepause wie
    Trip. Ersetzt das fruehere Non-Goal ("Compare gewinnt KEIN 2s-Delay dazu")
    aus `3ca3be14` — das war im Kontext eines verhaltensneutralen Refactors
    richtig und ist jetzt bewusst revidiert.

    Begruendung: seit #1270 verschickt Compare pro faelligem Preset DREI
    Kanaele (E-Mail + Telegram + SMS) ohne jede Pause -> Rate-Limit-Risiko bei
    Resend/Telegram. Der Rate-Limit-Schutz (#766), der Trip seine 2.0s gab,
    gilt fuer Compare genauso."""
    from src.services.dispatch_orchestrator import CompareDispatchStrategy

    assert _strategy_delay(CompareDispatchStrategy) == 2.0


def test_compare_pauses_between_presets_but_not_after_the_last():
    """Verhaltensnachweis zur PO-Entscheidung 2026-07-16: die echte
    Orchestrator-Schleife pausiert zwischen zwei faelligen Compare-Presets
    tatsaechlich ~2s — und NICHT nach dem letzten.

    Kein Mock/Patch und kein gemocktes `time.sleep`: gemessen wird echte
    Wanduhr-Zeit gegen den echten `run_briefing_dispatch`-Loop. Genutzt wird
    die im Modul bereits vorhandene Naht `_STRATEGY` (Registry, s.
    `test_strategy_registry_covers_both_kinds`): registriert wird eine echte
    Unterklasse der echten `CompareDispatchStrategy`, die `inter_mail_delay`
    ERBT — sinkt der Wert zurueck auf 0, wird dieser Test rot. Ueberschrieben
    sind nur `collect_due` (zwei Dummy-Items statt echter Preset-Datei) und
    `dispatch_one` (Zeitstempel statt echtem Versand) — damit der Test keine
    echten Mails verschickt. Die zu pruefende Logik (Schleife, Delay-Position,
    `i < len(due) - 1`) bleibt der echte Produktivcode.
    """
    import time

    from src.services import dispatch_orchestrator as mod

    class _RecordingCompareStrategy(mod.CompareDispatchStrategy):
        # inter_mail_delay bewusst NICHT ueberschrieben -> geerbter Echtwert.
        def __init__(self, settings, user_id, data_root=None):
            super().__init__(settings, user_id, data_root)
            self.dispatch_times: list[float] = []

        def collect_due(self, hour):
            return ["preset-a", "preset-b"]

        def pre_pass(self, hour, due):
            return None

        def dispatch_one(self, item):
            self.dispatch_times.append(time.monotonic())

    user_id = _fresh_user_id("delay")
    _make_isolated_user(user_id)

    instances: list[_RecordingCompareStrategy] = []

    class _Capturing(_RecordingCompareStrategy):
        def __init__(self, settings, user_id, data_root=None):
            super().__init__(settings, user_id, data_root)
            instances.append(self)

    original = mod._STRATEGY["vergleich"]
    mod._STRATEGY["vergleich"] = _Capturing
    try:
        mod.run_briefing_dispatch("vergleich", user_id, 7)
        returned = time.monotonic()
    finally:
        mod._STRATEGY["vergleich"] = original

    assert len(instances) == 1
    times = instances[0].dispatch_times
    assert len(times) == 2, "beide faelligen Presets muessen versendet werden"

    gap = times[1] - times[0]
    assert gap >= 1.9, (
        f"Zwischen zwei faelligen Compare-Presets wurde nicht ~2s pausiert "
        f"(gemessen: {gap:.3f}s)"
    )

    trailing = returned - times[1]
    assert trailing < 1.0, (
        f"Nach dem LETZTEN Compare-Preset darf nicht pausiert werden "
        f"(gemessen: {trailing:.3f}s nach dem letzten Versand)"
    )


# --- HIGH-Risiko 3: Rueckgabe-Taxonomie bleibt getrennt -------------------


def test_route_dispatch_returns_trip_tally_format():
    """AC-1 + HIGH-Risiko-Punkt 3: `kind="route"` liefert das Trip-Tally-
    Format `(sent, failed)` — hier `(0, 0)`, da der frische Test-User weder
    faellige Trips noch SMTP-Konfiguration hat. Echter tmp-User, kein Mock."""
    from src.services.dispatch_orchestrator import run_briefing_dispatch

    user_id = _fresh_user_id("route")
    _make_isolated_user(user_id)

    result = run_briefing_dispatch("route", user_id, 7)

    assert result == (0, 0)
    assert isinstance(result, tuple)


def test_vergleich_dispatch_returns_compare_count_format():
    """AC-1 + HIGH-Risiko-Punkt 3: `kind="vergleich"` liefert seit Issue #1290
    (E1, Epic #1301 Scheibe E, PO-freigegebene Spec 2026-07-18) DASSELBE
    Tupel-Format wie `kind="route"` — Revision der vormaligen #1207-Aussage
    "KEINE Vereinheitlichung": der Prod-Journal-Befund 2026-07-16 (133/133
    stille Fehlschlaege) zeigte, dass ein reiner `int`-Erfolgszaehler einen
    100%-Ausfall nicht von einem leeren Lauf unterscheiden kann. Echter
    tmp-User, kein Mock. Analog zur 2s-Delay-Revision in dieser Datei
    (PO-Entscheidung 2026-07-16, ebenfalls dort dokumentiert)."""
    from src.services.dispatch_orchestrator import run_briefing_dispatch

    user_id = _fresh_user_id("vergleich")
    _make_isolated_user(user_id)

    result = run_briefing_dispatch("vergleich", user_id, 7)

    assert result == (0, 0)
    assert isinstance(result, tuple)


# --- AC-1: Entry-Points delegieren statt zu duplizieren -------------------


def test_entry_points_delegate_to_orchestrator():  # doc-compliance-test
    """AC-1: `send_reports_for_hour` (Trip) UND `run_compare_presets_daily`
    (Compare) referenzieren im Quelltext `run_briefing_dispatch` — Delegation
    an den gemeinsamen Orchestrator statt zweier unabhaengiger Codepfade.
    Jetzt rot: keine der beiden Funktionen kennt den Namen."""
    from services import scheduler_dispatch_service, trip_report_scheduler

    trip_src = inspect.getsource(
        trip_report_scheduler.TripReportSchedulerService.send_reports_for_hour
    )
    compare_src = inspect.getsource(scheduler_dispatch_service.run_compare_presets_daily)

    assert "run_briefing_dispatch" in trip_src, (
        "send_reports_for_hour delegiert noch nicht an run_briefing_dispatch"
    )
    assert "run_briefing_dispatch" in compare_src, (
        "run_compare_presets_daily delegiert noch nicht an run_briefing_dispatch"
    )


# --- AC-2: Render-Config ausschliesslich ueber die zwei Resolver ----------


def test_orchestrator_config_only_via_resolver():  # doc-compliance-test
    """AC-2: `dispatch_orchestrator.py` liest Render-Config NUR ueber
    `resolve_report_render_options`/`resolve_compare_render_options` — kein
    Direktzugriff auf `.report_config`/`.display_config`-Attribute (Struktur-
    Verbot #1209 gilt weiter). Jetzt rot, weil die Datei komplett fehlt."""
    source_path = _PROJECT_ROOT / "src" / "services" / "dispatch_orchestrator.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_attrs = {"report_config", "display_config"}
    violations = [
        f"{source_path.name}:{node.lineno} — .{node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in forbidden_attrs
    ]
    assert not violations, (
        "AC-2: Direktzugriff auf Render-Config-Attribute im Orchestrator "
        "gefunden (muss ueber die zwei Resolver-Funktionen laufen):\n  "
        + "\n  ".join(violations)
    )

    uses_resolver = (
        "resolve_report_render_options" in source
        and "resolve_compare_render_options" in source
    )
    assert uses_resolver, (
        "AC-2: dispatch_orchestrator.py muss beide Resolver-Funktionen "
        "(resolve_report_render_options fuer route, resolve_compare_render_options "
        "fuer vergleich) nutzen"
    )


# --- Adversary Fix-Loop F002: injiziertes Settings bleibt erhalten --------


def test_send_reports_for_hour_uses_injected_settings_not_fresh_reload(caplog):
    """F002: `TripReportSchedulerService.send_reports_for_hour` muss das per
    Konstruktor injizierte `self._settings` an `run_briefing_dispatch`
    weiterreichen -- NICHT still ein frisches `Settings().with_user_profile()`
    laden (das den Konstruktor-Override verwirft).

    Beobachtbares Signal (kein Mock): der SMTP-Fruehausstieg in
    `run_briefing_dispatch` ("Trip"-Strategie hat `smtp_guard=True`) ruft bei
    `can_send_email() is False` `strategy.collect_due()` NIE auf -- also
    entsteht auch NIE der echte, unconditional DEBUG-Log-Eintrag
    "Active trips for ..." aus `_get_active_trips()`. Eine frisch geladene
    Settings-Instanz fuer einen "tdd"-Test-User hat in dieser Umgebung
    (Stalwart-Test-Creds in .env, siehe `Settings.for_testing()`)
    `can_send_email() == True` -- OHNE den Fix wuerde also der Guard NICHT
    greifen und der Log-Eintrag erscheinen, obwohl das injizierte Settings
    explizit `can_send_email() == False` erzwingt. Kein Mock/Patch: echter
    Logger, echte Settings-Instanz, echter isolierter tmp-User.
    """
    import logging as logging_module

    from app.config import Settings
    from services.trip_report_scheduler import TripReportSchedulerService

    user_id = _fresh_user_id("f002")
    _make_isolated_user(user_id)

    # Praemisse dokumentieren: eine frisch geladene Settings-Instanz fuer
    # diesen User haette can_send_email() == True (Stalwart-Test-Creds).
    fresh_reload = Settings().with_user_profile(user_id)
    assert fresh_reload.can_send_email() is True, (
        "Praemisse verletzt: Stalwart-Test-SMTP-Creds fehlen in .env -- "
        "Test kann Bug/Fix so nicht unterscheiden."
    )

    # Injiziertes Settings mit erzwungenem can_send_email() == False.
    injected = fresh_reload.model_copy(update={
        "mail_to": None, "smtp_host": None, "smtp_user": None, "smtp_pass": None,
    })
    assert injected.can_send_email() is False

    service = TripReportSchedulerService(settings=injected, user_id=user_id)

    caplog.set_level(logging_module.DEBUG, logger="trip_report_scheduler")
    result = service.send_reports_for_hour(7)

    assert result == (0, 0)
    assert not any("Active trips for" in rec.message for rec in caplog.records), (
        "Guard griff nicht -- injiziertes Settings wurde verworfen "
        "(send_reports_for_hour laedt still ein frisches Settings statt "
        "self._settings durchzureichen)"
    )
