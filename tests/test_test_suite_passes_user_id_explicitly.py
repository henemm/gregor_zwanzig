# doc-compliance-test
"""AST-Inventar: ALLE Testaufrufe der 40 betroffenen Funktionen/Konstruktoren/
``InboundMessage`` reichen ``user_id`` explizit durch -- kein Testaufruf darf
sich mehr auf den (in Scheibe C entfernten) Signatur-Default verlassen
(#2151 Scheibe C, Migration Item 5).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_c.md (Test 13,
AC-10)

Quelle der 40 Ziele: ``_MIGRATIONSZIELE`` unten -- eine EIGENE, eingefrorene
Kopie der urspruenglichen ``_SRC_BESTAND``-Liste aus
``tests/test_user_id_default_guard.py`` (Stand vor der Scheibe-C-Leerung,
``git show HEAD:tests/test_user_id_default_guard.py``). Bewusst KEIN Import
von dort: ``_SRC_BESTAND`` wird im Zuge dieser Scheibe auf ``frozenset()``
geleert (das ist ihr Ziel-Endzustand), waehrend dieser Migrations-Nachweis
weiterhin gegen die vollen 40 urspruenglichen Ziele pruefen muss -- sonst waere
dieser Test vakuum-gruen (leeres Register, 0 Funde IMMER, unabhaengig vom
Testbestand). Fuer jedes Ziel wird die POSITION des
``user_id``-Parameters aus der ECHTEN Signatur bestimmt (``inspect``, kein
geratener Index): ein Konstruktor-Eintrag (``Klasse.__init__`` bzw. das
Dataclass-Feld ``InboundMessage.user_id``) wird an einem Aufruf ``Klasse(...)``
gesucht (``inspect.signature(Klasse)`` laesst ``self`` bereits weg), ein
Methoden-Eintrag (``Klasse.methode``) an einem Attribut-Aufruf ``*.methode(...)``
(Klassen-Aufloesung ist wie bei den Sammlern in ``test_user_id_default_guard.py``
bewusst NICHT generisch -- reine Namens-Uebereinstimmung, keine Typ-Inferenz).
Ist ``user_id`` in der Signatur ``KEYWORD_ONLY`` (z. B. die drei
``PreviewService.render_*_preview``-Methoden), zaehlt ausschliesslich das
Keyword-Argument als Beleg.

Ein Aufruf gilt als GEDECKT, wenn er ``user_id=...`` als Keyword traegt ODER
(nur bei einem ``POSITIONAL_OR_KEYWORD``/``POSITIONAL_ONLY``-Parameter)
genug positionelle Argumente bis zu dessen Position hat. ``*args``/``**kwargs``-
Entpackung an einer Aufrufstelle macht den Fund nicht entscheidbar -- solche
Aufrufe werden NICHT gemeldet (bewusste Scope-Grenze, analog den bestehenden
Sammlern in ``test_user_id_default_guard.py``).

Ausnahme (explizite, auditierbare Markierung): Aufrufe in DIESEM Scheibe-C-
Testbestand, die ``user_id`` ABSICHTLICH weglassen, um genau das
fail-closed-Verhalten (AC-3/AC-5/AC-7) bzw. den unveraenderten Legacy-Pfad
(AC-4) zu belegen, tragen ``# type: ignore[call-arg]`` auf derselben Zeile --
ein grep-barer, im Repo etablierter Marker (mypy-Konvention fuer bewusst
fehlende Argumente), keine stille Ausnahme. Ohne diese Ausnahme koennte
AC-10 nie erfuellt sein, weil die permanenten Regressionstests aus Test 4-8/11
denselben Aufruf dauerhaft OHNE ``user_id`` brauchen, um die Pflicht ueberhaupt
zu pruefen.

Heute (RED): ~270+ Testaufrufe in ~80 Bestandsdateien lassen ``user_id`` noch
weg (Migration Item 5 steht aus) -- die Fundliste steht im Fehlertext.
"""
from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_TESTS_DIR = _REPO / "tests"
_SELBST = Path(__file__).resolve()
_MARKER = "type: ignore[call-arg]"

# Eingefrorene Kopie von ``_SRC_BESTAND`` (Stand vor der Scheibe-C-Leerung in
# tests/test_user_id_default_guard.py, ``git show HEAD:...``) -- 40 Eintraege.
# Darf sich NICHT mit der schrumpfenden Ratsche dort mitbewegen (siehe
# Modul-Docstring); dieser Migrations-Nachweis braucht die urspruengliche,
# vollstaendige Zielmenge dauerhaft.
_MIGRATIONSZIELE: frozenset[tuple[str, str]] = frozenset({
    ("src/app/loader.py", "load_trip"),
    ("src/app/loader.py", "get_data_dir"),
    ("src/app/loader.py", "get_locations_dir"),
    ("src/app/loader.py", "get_briefings_dir"),
    ("src/app/loader.py", "get_snapshots_dir"),
    ("src/app/loader.py", "load_all_locations"),
    ("src/app/loader.py", "save_location"),
    ("src/app/loader.py", "delete_location"),
    ("src/app/loader.py", "load_all_trips"),
    ("src/app/loader.py", "save_trip"),
    ("src/app/loader.py", "delete_trip"),
    ("src/services/alert_state.py", "AlertStateService.__init__"),
    ("src/services/compare_alert.py", "CompareAlertService.__init__"),
    ("src/services/compare_official_alert.py", "CompareOfficialAlertService.__init__"),
    ("src/services/compare_radar_alert.py", "CompareRadarAlertService.__init__"),
    ("src/services/compare_weather_snapshot.py", "CompareWeatherSnapshotService.__init__"),
    ("src/services/inbound_email_reader.py", "InboundEmailReader._find_trip_id"),
    ("src/services/inbound_telegram_reader.py", "InboundTelegramReader._find_active_trip"),
    ("src/services/notification_service.py", "NotificationService.__init__"),
    ("src/services/preview_service.py", "PreviewService._load_trip"),
    ("src/services/preview_service.py", "PreviewService.render_email_preview"),
    ("src/services/preview_service.py", "PreviewService.render_sms_preview"),
    ("src/services/preview_service.py", "PreviewService.render_telegram_preview"),
    ("src/services/scheduler_dispatch_service.py", "run_compare_presets_daily"),
    ("src/services/trip_alert.py", "TripAlertService.__init__"),
    ("src/services/trip_command_processor.py", "InboundMessage.user_id"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._find_trip"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._apply_ruhetag"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._trigger_report"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._shift_start"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._cancel_trip"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._resume_trip"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._delete_snapshot"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._get_command_log_path"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._load_command_log"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._append_command_log"),
    ("src/services/trip_command_processor.py", "TripCommandProcessor._is_already_applied"),
    ("src/services/trip_report_scheduler.py", "TripReportSchedulerService.__init__"),
    ("src/services/weather_extractor.py", "WeatherExtractor.__init__"),
    ("src/services/weather_snapshot.py", "WeatherSnapshotService.__init__"),
})


def _ziel_aufloesen(datei_rel: str, qualname: str) -> tuple[str, int | None, bool]:
    """Liefert (Aufruf-Suchname, Positions-Index von user_id oder None bei
    KEYWORD_ONLY, ist_attribut_aufruf) fuer einen ``_MIGRATIONSZIELE``-Eintrag
    -- Positions-Index aus der ECHTEN Signatur via ``inspect``."""
    modul_name = datei_rel.removeprefix("src/").removesuffix(".py").replace("/", ".")
    modul = importlib.import_module(modul_name)
    teile = qualname.split(".")
    if len(teile) == 1:
        ziel = getattr(modul, teile[0])
        such_name = teile[0]
        params = list(inspect.signature(ziel).parameters.values())
        ist_attribut = False
    else:
        klasse = getattr(modul, teile[0])
        attrname = teile[1]
        if attrname in ("__init__", "user_id"):
            # Konstruktor bzw. Dataclass-Feld -- Aufrufstelle ist Klasse(...);
            # inspect.signature(Klasse) laesst self bereits weg.
            such_name = teile[0]
            params = list(inspect.signature(klasse).parameters.values())
            ist_attribut = False
        else:
            methode = getattr(klasse, attrname)
            such_name = attrname
            params = list(inspect.signature(methode).parameters.values())
            if params and params[0].name == "self":
                params = params[1:]
            ist_attribut = True
    positional = [
        p.name for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    index = positional.index("user_id") if "user_id" in positional else None
    return such_name, index, ist_attribut


def _baue_ziel_register() -> tuple[dict[str, int | None], dict[str, int | None]]:
    """(Name-Ziele fuer ``Name(...)``-Aufrufe, Attribut-Ziele fuer
    ``*.attr(...)``-Aufrufe) -- je Suchname der Positions-Index von
    ``user_id`` (``None`` bei ``KEYWORD_ONLY``)."""
    name_ziele: dict[str, int | None] = {}
    attribut_ziele: dict[str, int | None] = {}
    for datei_rel, qualname in sorted(_MIGRATIONSZIELE):
        such_name, index, ist_attribut = _ziel_aufloesen(datei_rel, qualname)
        (attribut_ziele if ist_attribut else name_ziele)[such_name] = index
    return name_ziele, attribut_ziele


class _AufrufSammler(ast.NodeVisitor):
    def __init__(
        self, quellzeilen: list[str],
        name_ziele: dict[str, int | None], attribut_ziele: dict[str, int | None],
    ) -> None:
        self._zeilen = quellzeilen
        self._name_ziele = name_ziele
        self._attribut_ziele = attribut_ziele
        self.funde: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        such_name: str | None = None
        index: int | None = None
        if isinstance(node.func, ast.Name) and node.func.id in self._name_ziele:
            such_name = node.func.id
            index = self._name_ziele[such_name]
        elif isinstance(node.func, ast.Attribute) and node.func.attr in self._attribut_ziele:
            such_name = node.func.attr
            index = self._attribut_ziele[such_name]

        if such_name is not None and not self._ist_markiert(node.lineno):
            hat_keyword = any(kw.arg == "user_id" for kw in node.keywords)
            hat_kwargs_entpackung = any(kw.arg is None for kw in node.keywords)
            hat_args_entpackung = any(isinstance(a, ast.Starred) for a in node.args)
            hat_positional = index is not None and len(node.args) > index
            entscheidbar = not hat_kwargs_entpackung and not hat_args_entpackung
            if entscheidbar and not hat_keyword and not hat_positional:
                self.funde.append((node.lineno, such_name))
        self.generic_visit(node)

    def _ist_markiert(self, lineno: int) -> bool:
        if not (0 < lineno <= len(self._zeilen)):
            return False
        return _MARKER in self._zeilen[lineno - 1]


def _sammle_verstoesse() -> list[str]:
    name_ziele, attribut_ziele = _baue_ziel_register()
    fundliste: list[str] = []
    for datei in sorted(_TESTS_DIR.rglob("*.py")):
        if datei.resolve() == _SELBST:
            continue
        quelltext = datei.read_text(encoding="utf-8")
        baum = ast.parse(quelltext, filename=str(datei))
        sammler = _AufrufSammler(quelltext.splitlines(), name_ziele, attribut_ziele)
        sammler.visit(baum)
        rel = datei.relative_to(_REPO).as_posix()
        for zeile, name in sammler.funde:
            fundliste.append(f"{rel}:{zeile} {name}(...)")
    return fundliste


def test_ac10_alle_testaufrufe_reichen_user_id_explizit_durch():
    """AC-10 / Test 13: kein Aufruf einer der 40 betroffenen Funktionen/
    Konstruktoren/``InboundMessage`` unter ``tests/**/*.py`` (auch
    ``live``-/``email``-markierte Dateien) laesst ``user_id`` weg.

    RED heute: die Migration (Item 5, ~277 Aufrufe in ~81 Dateien) steht noch
    aus -- die vollstaendige Fundliste steht unten im Fehlertext.
    """
    verstoesse = _sammle_verstoesse()
    assert verstoesse == [], (
        f"AC-10: {len(verstoesse)} Testaufrufe ohne explizites user_id "
        "gefunden -- mechanisch auf explizite Kennung umstellen (Konto "
        f"'default' bleibt gueltig, siehe AC-9): {verstoesse}"
    )
