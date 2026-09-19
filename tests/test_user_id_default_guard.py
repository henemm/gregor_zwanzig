# doc-compliance-test
"""Struktur-Waechter: kein stiller ``user_id``-Rueckfall auf ``"default"``
(#2151 Scheibe A, ADR-0003).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_a.md (AC-8 bis AC-11)

Ein ``user_id``-Parameter mit Vorgabe ``"default"`` laesst einen Aufrufer, der
die Kennung vergisst, still auf dem Konto ``default`` arbeiten -- ADR-0003
nennt das ein Cross-User-Datenleck. Der Waechter parst die Module per ``ast``
(Struktur, keine Textsuche; Vorbild ``test_output_timezone_guard.py``):

* ``api/``: KEINE solche Vorgabe mehr (AC-8), auch nicht als ``Query("default")``.
* ``src/``: Ratsche. Die heute noch bestehenden Vorgaben stehen fest in
  ``_SRC_BESTAND`` (Scheibe C raeumt sie ab). Neue Stelle => rot; Listeneintrag
  ohne Fundstelle => rot (Liste nachziehen, nie still veralten) (AC-10).
* ``src/services/inbound_{email,telegram}_reader.py``: kein ``… or "default"``
  bei der Nutzerauflösung aus Absenderdaten (AC-11).

Die Suchfunktionen nehmen die Wurzel als Parameter -- so pruefen AC-9/AC-10 die
EMPFINDLICHKEIT des Waechters an einem gepflanzten Baum unter ``tmp_path``,
ohne Produktivcode anzufassen.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

# (Datei relativ zum Repo, qualifizierter Name) -- darf nur SCHRUMPFEN.
# Stand #2151 Scheibe A; Abbau in Scheibe C.
_SRC_BESTAND: frozenset[tuple[str, str]] = frozenset({
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

_INBOUND_READER = (
    "src/services/inbound_email_reader.py",
    "src/services/inbound_telegram_reader.py",
)


def _ist_default_literal(knoten: ast.AST | None) -> bool:
    return isinstance(knoten, ast.Constant) and knoten.value == "default"


def _ist_default_vorgabe(knoten: ast.AST | None) -> bool:
    """``"default"`` direkt oder als ``Query("default")``/``Query(default="default")``."""
    if _ist_default_literal(knoten):
        return True
    if isinstance(knoten, ast.Call):
        name = getattr(knoten.func, "id", None) or getattr(knoten.func, "attr", None)
        if name == "Query":
            if knoten.args and _ist_default_literal(knoten.args[0]):
                return True
            return any(
                k.arg == "default" and _ist_default_literal(k.value)
                for k in knoten.keywords
            )
    return False


class _VorgabenSammler(ast.NodeVisitor):
    def __init__(self) -> None:
        self.pfad: list[str] = []
        self.funde: set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.pfad.append(node.name)
        for st in node.body:
            if (
                isinstance(st, ast.AnnAssign)
                and isinstance(st.target, ast.Name)
                and st.target.id == "user_id"
                and _ist_default_vorgabe(st.value)
            ):
                self.funde.add(".".join(self.pfad + ["user_id"]))
        self.generic_visit(node)
        self.pfad.pop()

    def _funktion(self, node) -> None:
        a = node.args
        positional = a.posonlyargs + a.args
        paare = list(zip(positional[len(positional) - len(a.defaults):], a.defaults))
        paare += [(arg, d) for arg, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None]
        if any(arg.arg == "user_id" and _ist_default_vorgabe(d) for arg, d in paare):
            self.funde.add(".".join(self.pfad + [node.name]))
        self.pfad.append(node.name)
        self.generic_visit(node)
        self.pfad.pop()

    visit_FunctionDef = _funktion
    visit_AsyncFunctionDef = _funktion


def finde_default_vorgaben(wurzel: Path, unterordner: str) -> set[tuple[str, str]]:
    """Alle ``user_id``-Vorgaben ``"default"`` unter ``wurzel/unterordner``."""
    funde: set[tuple[str, str]] = set()
    for datei in sorted((wurzel / unterordner).rglob("*.py")):
        sammler = _VorgabenSammler()
        sammler.visit(ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei)))
        rel = datei.relative_to(wurzel).as_posix()
        funde |= {(rel, name) for name in sammler.funde}
    return funde


def finde_or_default(datei: Path) -> list[int]:
    """Zeilen mit ``<ausdruck> or "default"`` (``BoolOp``/``Or`` mit Literal)."""
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    return sorted(
        n.lineno for n in ast.walk(baum)
        if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)
        and any(_ist_default_literal(v) for v in n.values)
    )


def ratschen_abweichung(
    gefunden: set[tuple[str, str]], bestand: frozenset[tuple[str, str]],
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """(neue Stellen, veraltete Listeneintraege)."""
    return gefunden - bestand, set(bestand) - gefunden


# ═══════════════════════════ AC-8 ════════════════════════════════════════════


def test_ac8_api_hat_keine_user_id_vorgabe_default():
    """AC-8: unter ``api/`` gibt es keinen ``user_id``-Parameter mit Vorgabe
    ``"default"`` (auch nicht ``Query("default")``).

    RED heute: ``scheduler.send_test_trip_report``,
    ``scheduler.manual_send_compare_preset``, ``debug.trigger_radar_alert``.
    """
    funde = finde_default_vorgaben(_REPO, "api")
    assert funde == set(), (
        "AC-8: user_id faellt in api/ still auf 'default' zurueck (ADR-0003) -- "
        f"Pflichtparameter Query(...) verwenden: {sorted(funde)}"
    )


# ═══════════════════════════ AC-9 ════════════════════════════════════════════


def test_ac9_waechter_faengt_eine_neu_gepflanzte_router_vorgabe(tmp_path):
    """AC-9: eine neue Router-Funktion mit ``user_id: str = "default"`` (bzw.
    ``Query("default")``) wird gefunden und benannt -- der Waechter kennt
    nicht nur die bekannten Stellen."""
    router = tmp_path / "api" / "routers"
    router.mkdir(parents=True)
    (router / "neu.py").write_text(
        "from fastapi import Query\n"
        "def handler(user_id: str = \"default\"):\n    pass\n"
        "async def zweiter(x: int, *, user_id: str = Query(\"default\")):\n    pass\n"
        "def sauber(user_id: str = Query(...)):\n    pass\n"
        "def anderer_parameter(name: str = \"default\"):\n    pass\n",
        encoding="utf-8",
    )

    assert finde_default_vorgaben(tmp_path, "api") == {
        ("api/routers/neu.py", "handler"),
        ("api/routers/neu.py", "zweiter"),
    }


# ═══════════════════════════ AC-10 ═══════════════════════════════════════════


def test_ac10_src_bestand_stimmt_exakt_mit_dem_code_ueberein():
    """AC-10 (Ist-Stand): die ``src/``-Vorgaben entsprechen exakt der
    Bestandsliste -- keine neue Stelle, kein veralteter Eintrag."""
    neu, veraltet = ratschen_abweichung(finde_default_vorgaben(_REPO, "src"), _SRC_BESTAND)
    assert not neu, (
        "AC-10: neue user_id-Vorgabe 'default' in src/ -- Kennung als "
        f"Pflichtparameter fuehren statt die Liste zu erweitern: {sorted(neu)}"
    )
    assert not veraltet, (
        "AC-10: Listeneintrag ohne Fundstelle im Code -- aus _SRC_BESTAND "
        f"streichen (die Liste darf nur schrumpfen): {sorted(veraltet)}"
    )


def test_ac10_ratsche_schlaegt_in_beide_richtungen_an(tmp_path):
    """AC-10 (Empfindlichkeit): gepflanzter Baum mit einer bekannten und einer
    neuen Stelle gegen eine Liste mit einem bekannten und einem verschwundenen
    Eintrag -- beide Abweichungen werden benannt."""
    modul = tmp_path / "src" / "services"
    modul.mkdir(parents=True)
    (modul / "dienst.py").write_text(
        "class Dienst:\n"
        "    def __init__(self, user_id: str = \"default\"):\n        pass\n"
        "    def neu(self, user_id=\"default\"):\n        pass\n",
        encoding="utf-8",
    )
    bestand = frozenset({
        ("src/services/dienst.py", "Dienst.__init__"),
        ("src/services/dienst.py", "Dienst.entfernt"),
    })

    neu, veraltet = ratschen_abweichung(finde_default_vorgaben(tmp_path, "src"), bestand)

    assert neu == {("src/services/dienst.py", "Dienst.neu")}
    assert veraltet == {("src/services/dienst.py", "Dienst.entfernt")}


# ═══════════════════════════ AC-11 ═══════════════════════════════════════════


def test_ac11_inbound_reader_fallen_bei_unbekanntem_absender_nicht_auf_default():
    """AC-11: weder E-Mail- noch Telegram-Eingang loesen einen unbekannten
    Absender per ``… or "default"`` auf.

    RED heute: ``inbound_telegram_reader._resolve_user_for_chat``.
    """
    funde = {
        rel: zeilen for rel in _INBOUND_READER
        if (zeilen := finde_or_default(_REPO / rel))
    }
    assert funde == {}, (
        "AC-11: unbekannter Absender faellt still auf 'default' zurueck -- "
        f"None liefern (Vorbild inbound_email_reader, #2147): {funde}"
    )


def test_ac11_waechter_faengt_einen_gepflanzten_or_default(tmp_path):
    """AC-11 (Empfindlichkeit): ``lookup(x) or "default"`` wird gefunden,
    ``lookup(x) or None`` nicht."""
    datei = tmp_path / "reader.py"
    datei.write_text(
        "a = lookup(x) or \"default\"\n"
        "b = lookup(x) or None\n",
        encoding="utf-8",
    )
    assert finde_or_default(datei) == [1]
