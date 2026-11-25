# doc-compliance-test
"""AST-Import-Waechter: der Altpfad der Kanal-Listen kehrt nicht zurueck (#3237).

SPEC: docs/specs/modules/feat_3237_altpfad_entfernen.md, AC-9, AC-11;
docs/specs/modules/feat_3277_altfelder_entfernen.md, AC-8.

Werkzeug-Klasse (CLAUDE.md-Ausnahme ``# doc-compliance-test``): der Waechter
liest Produktions-Quelltext als DATEN (``ast.walk``) und meldet jeden Import,
jede Definition und jeden Aufruf/Attributzugriff eines geloeschten
Altpfad-Namens. Ausnahmen stehen als Daten mit Begruendung und ``EXPIRY`` in
``ERLAUBT``; eine abgelaufene Ausnahme macht den Test rot.

Selbstnachweis: synthetischer Quelltext mit verbotenem Import wird erkannt,
ein erlaubter Eintrag besteht, ein abgelaufener faellt (Muster
``tests/test_mail_recipient_parity.py``).
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
PRODUKTION = (WURZEL / "src", WURZEL / "api", WURZEL / ".claude" / "hooks", WURZEL / "scripts")

#: Geloeschte Altpfad-Namen (Spec Abschnitt Source/Scope).
VERBOTEN = frozenset({
    # channel_list_resolver
    "legacy_view", "legacy_lists", "trip_channel_metrics", "_trip_view", "_compare_view",
    "vm_lists", "ALTBESTAND_UEBER_UMRECHNUNG",
    # placements
    "placements_from_legacy", "legacy_placements", "_legacy_rows", "_output_changes",
    "_legacy_outlook_reports", "LegacyConversion",
    # placements_view_service
    "erstanlage_begleitfelder",
    # models.UnifiedWeatherDisplayConfig
    "get_metrics_for_channel", "cascade_source_for_channel", "_cascade_source_for_channel",
    # compare_outlook_metric_ids / compare_metric_ids
    "resolve_trip_outlook_metrics", "resolve_compare_outlook_metrics",
    "resolve_trip_outlook_formats", "resolve_compare_outlook_formats",
    "resolve_channel_enabled_metrics", "resolve_channel_layout_rows",
    # report_config_resolver
    "_options_bisher",
    # Migrationsskript (AC-11)
    "migrate_3157_placements",
    # #3277 AC-8: toter Code ohne Produktionsaufrufer (compare_outlook_metric_ids)
    "resolve_hourly_metric_formats",
})

#: (Datei relativ zur Wurzel, Name) -> (Begruendung, EXPIRY). Leer: keine Ausnahme.
ERLAUBT: dict[tuple[str, str], tuple[str, date]] = {}


def _namen(baum: ast.AST) -> list[tuple[int, str]]:
    """(Zeile, Name) jeder Stelle, die einen Namen importiert, definiert,
    aufruft oder als Attribut liest."""
    treffer: list[tuple[int, str]] = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom):
            if knoten.module:
                treffer += [(knoten.lineno, teil) for teil in knoten.module.split(".")]
            treffer += [(knoten.lineno, a.name) for a in knoten.names]
        elif isinstance(knoten, ast.Import):
            for a in knoten.names:
                treffer += [(knoten.lineno, teil) for teil in a.name.split(".")]
        elif isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            treffer.append((knoten.lineno, knoten.name))
        elif isinstance(knoten, ast.Name):
            treffer.append((knoten.lineno, knoten.id))
        elif isinstance(knoten, ast.Attribute):
            treffer.append((knoten.lineno, knoten.attr))
    return treffer


def verstoesse(quelltext: str, datei: str, erlaubt=None, heute: date | None = None) -> list[str]:
    erlaubt = ERLAUBT if erlaubt is None else erlaubt
    heute = heute or date.today()
    out = []
    for zeile, name in _namen(ast.parse(quelltext)):
        if name not in VERBOTEN:
            continue
        ausnahme = erlaubt.get((datei, name))
        if ausnahme is not None and ausnahme[1] >= heute:
            continue
        out.append(f"{datei}:{zeile}: {name}")
    return out


def _produktionsdateien():
    for ordner in PRODUKTION:
        yield from sorted(ordner.rglob("*.py"))


def test_ac9_kein_produktionscode_nutzt_den_altpfad():
    funde = []
    for pfad in _produktionsdateien():
        rel = str(pfad.relative_to(WURZEL))
        funde += verstoesse(pfad.read_text(encoding="utf-8"), rel)
    assert not funde, "Altpfad-Namen im Produktionscode:\n" + "\n".join(funde)


def test_ac11_migrationsskript_ist_entfernt():
    assert not (WURZEL / "scripts" / "migrate_3157_placements.py").exists()


def test_ac9_erlaubnisliste_traegt_begruendung_und_ist_nicht_abgelaufen():
    for (datei, name), (grund, ablauf) in ERLAUBT.items():
        assert name in VERBOTEN, (datei, name)
        assert len(grund) >= 20, (datei, name, grund)
        assert ablauf >= date.today(), f"Ausnahme abgelaufen: {datei} {name} ({ablauf})"


# ---------------------------------------------------------------------------
# Selbstnachweis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quelle", [
    "from services.placements import placements_from_legacy\n",
    "from services import channel_list_resolver as c\nc.legacy_lists(dc, 'trip', 'evening')\n",
    "dc.get_metrics_for_channel('email', 'evening')\n",
    "import scripts.migrate_3157_placements\n",
    "def erstanlage_begleitfelder():\n    pass\n",
    # #3277 AC-8
    "from output.renderers.compare_outlook_metric_ids import resolve_hourly_metric_formats\n",
    "from output.renderers import compare_outlook_metric_ids as c\nc.resolve_hourly_metric_formats({})\n",
])
def test_selbstnachweis_verbotener_name_wird_erkannt(quelle):
    assert verstoesse(quelle, "src/beispiel.py", erlaubt={}), quelle


def test_selbstnachweis_erlaubter_eintrag_besteht():
    quelle = "from services.placements import placements_from_legacy\n"
    erlaubt = {("src/beispiel.py", "placements_from_legacy"):
               ("Selbstnachweis: befristete Ausnahme", date(2099, 1, 1))}
    assert verstoesse(quelle, "src/beispiel.py", erlaubt=erlaubt) == []


def test_selbstnachweis_abgelaufener_eintrag_faellt():
    quelle = "from services.placements import placements_from_legacy\n"
    erlaubt = {("src/beispiel.py", "placements_from_legacy"):
               ("Selbstnachweis: abgelaufene Ausnahme", date(2000, 1, 1))}
    assert verstoesse(quelle, "src/beispiel.py", erlaubt=erlaubt)


def test_selbstnachweis_bleibende_namen_sind_frei():
    quelle = ("from services.placements import resolve_outlook_reports, read_placements\n"
              "from services.channel_list_resolver import resolve_channel_lists, grundauswahl\n")
    assert verstoesse(quelle, "src/beispiel.py", erlaubt={}) == []
