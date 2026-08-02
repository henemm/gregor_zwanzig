"""Die drei Waechter erkennen ihre Funde nach einer Zeilenverschiebung wieder.

Issue #1466 Arbeitspaket 2 (Dach #1196), Spec:
``docs/specs/modules/fix_1466_kern_suite_gruen.md`` AC-3/AC-4/AC-5.

Die drei Waechter (Erfolg/Aufloesung/Zeitzone) schluesseln ihre Restlisten
heute ueber ``"pfad:zeile"``. Jede eingefuegte Zeile verschiebt alles darunter:
dieselbe Stelle gilt gleichzeitig als "behoben" (alter Schluessel) und als
"neuer Verstoss" (neuer Schluessel) -- beim Erfolgs-Waechter 13x, mit
UNTERSCHIEDLICHEM Versatz, also nicht mit einer Zahl nachzuziehen. Wer eine
rote Suite gewohnt ist, liest sie nicht mehr; genau darin gingen zwei ECHTE
neue Verstoesse unter (Arbeitspaket 1).

Geprueft wird der neue Schluessel ``"pfad::funktion::ordinal"``:
AC-3 (eine echt eingefuegte Zeile aendert die Fundmenge nicht -- eingefuegt
wird wirklich, gescannt wirklich zweimal), AC-4 (mehrere Funde derselben
Funktion bleiben unterscheidbar; ohne Ordinal fielen im Bestand 14 Funde auf
5 Eintraege zusammen) und AC-5 (auch der Zeitzonen-Waechter kennt danach den
umschliessenden Funktionsnamen, verschachtelt und auf Modulebene).

Dazu (Issue #1466 F001, Pruefer-Befund): zwei Funde in DERSELBEN Quellzeile
bleiben ZWEI Eintraege. Eine Comprehension mit zwei unabhaengigen
Lookup-Filtern meldet beide unter der Zeile des Comprehension-Knotens; eine
Deduplizierung der Zeilen liesse einen davon still verschwinden -- genau der
Fehler, gegen den diese Waechter gebaut sind (Hausregel S-6). Der Nachweis
traegt seine eigene Mutations-Gegenprobe: mit wieder eingebauter
Deduplizierung meldet derselbe Scan nur noch einen Eintrag.

NICHT behauptet: Umbenennungs- oder Struktursicherheit -- der Schluessel
schuetzt gegen Zeilenverschiebung (Spec "Bekannte Grenzen").

Test-Politik: Kernschicht, keine Mocks, kein Dateiinhalt-Check als
Verhaltensnachweis -- gemessen wird nur, was die Scanner zurueckgeben.
Pfadregel #1409: Prueflinge relativ zu DIESER Testdatei aufgeloest.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pytest

# Pfadregel #1409: Prueflinge relativ zur eigenen Testdatei.
_TESTS_DIR = Path(__file__).resolve().parent

# Der neue Schluessel: <pfad>::<funktion>::<ordinal>. Der Pfad enthaelt nie
# "::", der Funktionsname nie ":" -- ``<module>`` eingeschlossen.
FINDING_RE = re.compile(r"^(?P<path>.+)::(?P<function>[^:]+)::(?P<ordinal>\d+)$")

# Kurzname -> Waechter-Datei. Welche Bestandsdatei als Prueftraeger fuer AC-3
# dient, steht hier bewusst NICHT: sie wird zur Laufzeit aus der Scanflaeche
# des jeweiligen Waechters bestimmt (s. _richest_scanned_file). So kann der
# Nachweis nicht veralten, wenn eine Fundstelle repariert oder eine Datei
# umbenannt wird -- und der Test haengt an keiner abgeschriebenen Pfadliste.
GUARD_FILES: dict[str, str] = {
    "erfolg": "test_success_status_guard.py",
    "aufloesung": "test_resolution_loss_guard.py",
    "zeitzone": "test_output_timezone_guard.py",
}


@lru_cache(maxsize=None)
def _guard(name: str):
    """Den Waechter als Modul laden -- ueber seinen Dateipfad, nicht ueber den
    Paketnamen: so misst ein Worktree-Lauf zwingend die Worktree-Fassung."""
    path = _TESTS_DIR / GUARD_FILES[name]
    assert path.exists(), f"Waechter-Datei fehlt: {path}"
    spec = importlib.util.spec_from_file_location(f"gz_guard_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def _richest_scanned_file(name: str) -> Path:
    """Die Datei aus der Scanflaeche des Waechters mit den MEISTEN Funden.

    Prueftraeger fuer den Einfuege-Nachweis: je mehr Funde, desto aussagekraeftiger
    der Vergleich. Ausgewaehlt wird aus ``_scan_files()`` des Waechters selbst --
    kein hier abgeschriebener Pfad, der stillschweigend veralten koennte.
    """
    guard = _guard(name)
    best: Path | None = None
    best_count = 0
    for path in guard._scan_files():
        count = len(guard._find_violations(path))
        if count > best_count:
            best, best_count = path, count
    assert best is not None, (
        f"Waechter '{name}' findet in seiner gesamten Scanflaeche nichts -- "
        "der Einfuege-Nachweis haette keinen Prueftraeger."
    )
    return best


def _parsed(keys) -> list[re.Match]:
    return [FINDING_RE.match(str(k)) for k in keys]


def _malformed(keys) -> list[str]:
    return sorted(str(k) for k in keys if not FINDING_RE.match(str(k)))


def _function_of(key: str) -> str:
    """``pfad::funktion`` eines Fundschluessels -- ohne das Ordinal."""
    match = FINDING_RE.match(key)
    assert match is not None, key
    return f"{match.group('path')}::{match.group('function')}"


# ---------------------------------------------------------------------------
# AC-3 / AC-5 (Form): der Schluessel nennt Datei, Funktion und Ordinal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("guard_name", sorted(GUARD_FILES))
def test_every_finding_is_named_by_file_function_and_ordinal(guard_name):
    """GIVEN einen der drei Waechter / WHEN er ueber seine Scanflaeche laeuft /
    THEN traegt JEDER Fundschluessel die Form ``pfad::funktion::ordinal`` --
    keine Zeilennummer mehr, dafuer der umschliessende Funktionsraum. Fuer den
    Zeitzonen-Waechter ist das zugleich die Formhaelfte von AC-5 (er hat heute
    gar keine Bereichsverfolgung, ``ast.walk`` blank)."""
    guard = _guard(guard_name)
    found = guard._all_violations()

    assert found, (
        f"Waechter '{guard_name}' meldet gar nichts -- dann prueft dieser "
        "Nachweis ins Leere (leerer Scan = gruener Waechter ohne Wirkung)."
    )
    malformed = _malformed(found)
    assert not malformed, (
        f"Waechter '{guard_name}' schluesselt Funde nicht als "
        "'pfad::funktion::ordinal'. Genau dieser Schluessel ist der "
        "Verschiebungsschutz (Issue #1466 AC-3). Code reference: "
        f"{malformed[:10]}"
    )


def test_all_three_guards_number_their_findings_the_same_way():
    """Das Ordinal darf 0- oder 1-basiert sein, aber ueber alle drei Waechter
    GLEICH (Spec AC-3) -- sonst trifft daneben, wer eine Restliste von Hand
    nachzieht."""
    bases: dict[str, int] = {}
    for guard_name in sorted(GUARD_FILES):
        found = _guard(guard_name)._all_violations()
        malformed = _malformed(found)
        assert not malformed, (
            f"Waechter '{guard_name}' liefert unlesbare Schluessel, die "
            f"Zaehlweise ist damit nicht feststellbar: {malformed[:5]}"
        )
        ordinals = [int(m.group("ordinal")) for m in _parsed(found)]
        assert ordinals, f"Waechter '{guard_name}' meldet nichts."
        bases[guard_name] = min(ordinals)

    assert len(set(bases.values())) == 1, (
        "Die drei Waechter zaehlen ihre Funde unterschiedlich (kleinstes "
        f"vergebenes Ordinal je Waechter): {bases}"
    )
    assert set(bases.values()) <= {0, 1}, (
        f"Das Ordinal startet weder bei 0 noch bei 1: {bases}"
    )


# ---------------------------------------------------------------------------
# AC-3: der Einfuege-Nachweis -- echt eingefuegt, echt neu gescannt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("guard_name", sorted(GUARD_FILES))
def test_findings_survive_a_line_inserted_above_them(guard_name, tmp_path):
    """
    GIVEN eine vom Waechter gescannte Bestandsdatei mit mehreren Funden
    WHEN oberhalb dieser Funde tatsaechlich eine Zeile eingefuegt wird (Kopie
      ausserhalb des Repos, identischer Dateipfad fuer beide Laeufe)
    THEN meldet der Waechter exakt DIESELBEN Fundschluessel wie vorher.

    Kern von AC-3, bewusst kein Gedankenexperiment: eingefuegt wird wirklich,
    gescannt zweimal, verglichen werden die Rueckgaben. Dass die Einfuegung
    wirklich verschoben hat, wird unabhaengig nachgewiesen (Syntaxbaum
    vorher/nachher) -- sonst waere der Test auch ohne Einfuegung gruen.
    """
    guard = _guard(guard_name)
    source = _richest_scanned_file(guard_name)
    original = source.read_text(encoding="utf-8")

    # Beide Laeufe schreiben auf DENSELBEN Pfad -- der Pfadanteil des
    # Schluessels ist damit garantiert identisch, verglichen wird allein die
    # Wirkung der Verschiebung.
    target = tmp_path / source.name
    target.write_text(original, encoding="utf-8")
    before = set(guard._find_violations(target))

    target.write_text(
        "# Issue #1466 AC-3: eingefuegte Zeile (Verschiebungs-Nachweis)\n"
        + original,
        encoding="utf-8",
    )
    after = set(guard._find_violations(target))

    assert before, (
        f"Die Bestandsdatei {source} liefert dem Waechter '{guard_name}' gar "
        "keinen Fund -- der Einfuege-Nachweis liefe ins Leere. Andere "
        "Prueftraeger-Datei waehlen."
    )

    # Gegenprobe: die Einfuegung hat den Code wirklich verschoben.
    first_def_before = min(
        node.lineno
        for node in ast.walk(ast.parse(original))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    first_def_after = min(
        node.lineno
        for node in ast.walk(ast.parse(target.read_text(encoding="utf-8")))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    assert first_def_after == first_def_before + 1, (
        "Die eingefuegte Zeile hat den Code nicht verschoben -- dann beweist "
        f"der Vergleich nichts. Vorher {first_def_before}, nachher "
        f"{first_def_after}."
    )

    assert after == before, (
        f"Waechter '{guard_name}': eine einzige eingefuegte Zeile in "
        f"{source.name} aendert die Fundmenge. Genau daran zerbricht die "
        "Restliste bei jeder Codeverschiebung -- dieselbe Stelle gilt "
        "gleichzeitig als behoben (alter Schluessel) und als neuer Verstoss "
        "(neuer Schluessel). Code reference: nur vorher "
        f"{sorted(before - after)[:5]} / nur nachher {sorted(after - before)[:5]}"
    )


# ---------------------------------------------------------------------------
# AC-4: mehrere Funde in derselben Funktion bleiben unterscheidbar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("guard_name", sorted(GUARD_FILES))
def test_repeated_findings_in_one_function_stay_separate(guard_name):
    """
    GIVEN eine Funktion mit mehreren unabhaengigen Fundstellen (im Bestand
      z. B. ``trip_command_processor.py::_handle_query`` mit vier Zweigen)
    WHEN der Waechter ueber die Scanflaeche laeuft
    THEN traegt jede Fundstelle einen EIGENEN Schluessel -- sie fallen nicht
      auf einen Eintrag je Funktion zusammen.

    Die Erwartung kommt aus dem Scanner selbst, nicht aus einer Abschrift:
    verglichen werden Schluesselzahl und Funktionszahl. Sind beide gleich,
    traegt keine Funktion mehr als einen Fund -- genau die Wirkung eines
    Schluessels ohne Ordinal. Dass es Mehrfachfaelle ueberhaupt gibt, wird
    mitverlangt (sonst waere die Aussage leer wahr).
    """
    guard = _guard(guard_name)
    found = guard._all_violations()
    malformed = _malformed(found)
    assert not malformed, (
        f"Waechter '{guard_name}' liefert Schluessel ohne Funktions-/"
        f"Ordinal-Anteil, AC-4 ist daran nicht messbar: {malformed[:5]}"
    )

    per_function = Counter(_function_of(str(k)) for k in found)
    multi = {name: count for name, count in per_function.items() if count > 1}

    assert multi, (
        f"Waechter '{guard_name}': keine einzige Funktion traegt mehr als "
        "einen Fund. Im Bestand gibt es diese Faelle nachweislich (14 Funde in "
        "5 Funktionen ueber Erfolgs- und Aufloesungs-Waechter, 22 Funde in 14 "
        "Funktionen im Zeitzonen-Waechter) -- fallen sie zusammen, sieht die "
        "Ratsche einen Teil der Verstoesse nicht mehr. Ursache ist fast immer "
        "ein Schluessel auf def-Ebene ohne Ordinal."
    )
    assert len(per_function) < len(found), (
        f"Waechter '{guard_name}': Funktionszahl und Fundzahl sind gleich "
        f"({len(per_function)} zu {len(found)}) -- Mehrfachfunde sind "
        "verschwunden."
    )

    for name, count in sorted(multi.items()):
        ordinals = sorted(
            int(FINDING_RE.match(str(k)).group("ordinal"))
            for k in found
            if _function_of(str(k)) == name
        )
        assert len(set(ordinals)) == count, (
            f"Waechter '{guard_name}': {name} traegt {count} Funde, aber nur "
            f"{len(set(ordinals))} verschiedene Ordinale: {ordinals}"
        )


# --- synthetische Wirkungsnachweise zu AC-4 (unabhaengig vom Bestand) -------

_SYNTHETIC_MULTI: dict[str, tuple[str, str, int]] = {
    # Zwei unabhaengige Katalog-Fehltreffer in EINER Funktion (Mechanik von
    # geosphere_warn.py::_extract_alerts).
    "aufloesung": (
        "synthetic_two_silent_drops.py",
        "from app.metric_catalog import get_metric\n"
        "\n"
        "\n"
        "def build_columns(dc, extra_ids):\n"
        "    columns = []\n"
        "    for mc in dc.metrics:\n"
        "        try:\n"
        "            metric_def = get_metric(mc.metric_id)\n"
        "        except KeyError:\n"
        "            continue\n"
        "        columns.append(metric_def.col_key)\n"
        "    for raw in extra_ids:\n"
        "        try:\n"
        "            other_def = get_metric(raw)\n"
        "        except KeyError:\n"
        "            continue\n"
        "        columns.append(other_def.col_key)\n"
        "    return columns\n",
        2,
    ),
    # Drei Kanal-Vorkommen desselben Erfolgsmarkers-vor-der-Tat in EINER
    # Funktion (Nachbau von notification_service.py::_dispatch_alert_message,
    # Bauform woertlich aus dem vorhandenen Wirkungsnachweis des Waechters).
    "erfolg": (
        "synthetic_three_pre_try_markers.py",
        "import logging\n"
        "\n"
        "from output.channels.email import EmailOutput\n"
        "from output.channels.sms import SMSOutput\n"
        "from output.channels.telegram import TelegramOutput\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "def _dispatch_alert_message(settings, subject, plain, html, sms_body, channels):\n"
        "    sent_channels = []\n"
        "\n"
        "    if 'email' in channels and settings.can_send_email():\n"
        "        sent_channels.append('email')\n"
        "        try:\n"
        "            EmailOutput(settings).send(subject=subject, body=html, plain_text_body=plain)\n"
        "        except Exception as e:\n"
        "            logger.error('Email alert failed: %s', e)\n"
        "\n"
        "    if 'telegram' in channels and settings.can_send_telegram():\n"
        "        sent_channels.append('telegram')\n"
        "        try:\n"
        "            TelegramOutput(settings).send(subject=subject, body=plain)\n"
        "        except Exception as e:\n"
        "            logger.error('Telegram alert failed: %s', e)\n"
        "\n"
        "    if 'sms' in channels and settings.can_send_sms():\n"
        "        sent_channels.append('sms')\n"
        "        try:\n"
        "            SMSOutput(settings).send(subject='', body=sms_body)\n"
        "        except Exception as e:\n"
        "            logger.error('SMS alert failed: %s', e)\n"
        "\n"
        "    return {'sent': bool(sent_channels), 'sent_channels': sent_channels}\n",
        3,
    ),
    # Zwei rohe .astimezone()-Aufrufe in EINER Funktion.
    "zeitzone": (
        "synthetic_two_raw_astimezone.py",
        "def render(start_ts, end_ts, tz):\n"
        "    start = start_ts.astimezone(tz).strftime('%H:%M')\n"
        "    end = end_ts.astimezone(tz).strftime('%H:%M')\n"
        "    return f'{start}-{end}'\n",
        2,
    ),
}


@pytest.mark.parametrize("guard_name", sorted(_SYNTHETIC_MULTI))
def test_synthetic_repeated_findings_yield_one_entry_each(guard_name, tmp_path):
    """AC-4, bestandsunabhaengig: eine synthetische Datei mit einer BEKANNTEN
    Zahl unabhaengiger Fundstellen in EINER Funktion muss genau so viele
    Schluessel erzeugen. Der Bestands-Nachweis oben zeigt nur, DASS
    Mehrfachfunde existieren -- hier ist die Sollzahl unabhaengig bekannt."""
    guard = _guard(guard_name)
    filename, source, expected = _SYNTHETIC_MULTI[guard_name]
    synthetic = tmp_path / filename
    synthetic.write_text(source, encoding="utf-8")

    found = guard._find_violations(synthetic)
    malformed = _malformed(found)
    assert not malformed, (
        f"Waechter '{guard_name}' schluesselt nicht als "
        f"'pfad::funktion::ordinal': {malformed}"
    )

    per_function = Counter(_function_of(str(k)) for k in found)
    assert len(per_function) == 1, (
        f"Erwartet wurde EINE betroffene Funktion, gemeldet: {dict(per_function)}"
    )
    name, count = next(iter(per_function.items()))
    assert count == expected, (
        f"Waechter '{guard_name}': {expected} unabhaengige Fundstellen in "
        f"{name}, gemeldet wurden {count}. Fallen sie zusammen, verliert die "
        f"Ratsche {expected - count} Verstoesse. Code reference: {sorted(found)}"
    )


# ---------------------------------------------------------------------------
# F001: zwei Funde in DERSELBEN Quellzeile bleiben zwei Eintraege
# ---------------------------------------------------------------------------

# Eine Comprehension meldet ihre Funde unter der Zeile des Comprehension-
# KNOTENS, nicht unter der des einzelnen Filters. Zwei unabhaengige
# Lookup-Filter an derselben Comprehension liefern deshalb zweimal dieselbe
# Zeilennummer -- der Fall, in dem eine Deduplizierung einen Fund schluckt.
_TWO_DROPS_ONE_LINE = (
    "def build_columns(dc):\n"
    "    return {\n"
    "        key: (FIRST_MAP[key], SECOND_MAP[key])\n"
    "        for key in dc.keys\n"
    "        if key in FIRST_MAP\n"
    "        if key in SECOND_MAP\n"
    "    }\n"
)


def _write_two_drops_one_line(tmp_path) -> Path:
    """Die synthetische Datei ablegen UND unabhaengig nachweisen, dass beide
    Funde wirklich auf EINER Zeile liegen.

    Ohne diesen Nachweis koennte die Konstruktion still zerfallen (z. B. weil
    jemand die Filter auf zwei Comprehensions aufteilt) -- der Test waere dann
    gruen, ohne den Fall noch zu pruefen.
    """
    target = tmp_path / "synthetic_two_drops_one_line.py"
    target.write_text(_TWO_DROPS_ONE_LINE, encoding="utf-8")

    comprehensions = [
        node
        for node in ast.walk(ast.parse(_TWO_DROPS_ONE_LINE))
        if isinstance(node, ast.DictComp)
    ]
    assert len(comprehensions) == 1, (
        "Vorbedingung: GENAU eine Comprehension -- sonst tragen die Funde "
        f"verschiedene Zeilen und der Fall ist nicht mehr gestellt: {comprehensions}"
    )
    assert len(comprehensions[0].generators[0].ifs) == 2, (
        "Vorbedingung: ZWEI unabhaengige Lookup-Filter an derselben "
        "Comprehension -- beide melden die Zeile des Comprehension-Knotens."
    )
    return target


def test_two_findings_in_one_source_line_stay_two_entries(tmp_path):
    """
    GIVEN eine Comprehension mit ZWEI unabhaengigen Katalog-Fehltreffern, die
      beide unter derselben Quellzeile gemeldet werden
    WHEN der Aufloesungs-Waechter sie schluesselt
    THEN bleiben es ZWEI Eintraege mit verschiedenen Ordinalen.

    Hausregel S-6 (test_success_status_guard.py): beim Zusammenfuehren darf
    kein Fund still verschwinden. Der ``"+"``-Merge des Erfolgs-Waechters
    trennt ueber die ARTEN und traegt hier nicht -- dieser Waechter kennt nur
    eine Art. Das Ordinal trennt unabhaengig von der Art.

    Die Gegenprobe zu diesem Test (Deduplizierung wieder eingebaut ->
    nur noch EIN Eintrag) steht direkt darunter; ohne sie waere hier nicht
    gezeigt, dass die Aussage ueberhaupt an der Zaehlweise haengt.
    """
    guard = _guard("aufloesung")
    synthetic = _write_two_drops_one_line(tmp_path)

    found = guard._find_violations(synthetic)

    malformed = _malformed(found)
    assert not malformed, (
        f"Aufloesungs-Waechter schluesselt nicht als 'pfad::funktion::ordinal': "
        f"{malformed}"
    )
    assert len(found) == 2, (
        "Zwei unabhaengige stille Verluste in EINER Quellzeile muessen zwei "
        "unterscheidbare Eintraege ergeben -- sonst faellt einer aus der "
        "Ratsche und ist danach unsichtbar (Issue #1466 F001). Code "
        f"reference: {sorted(found)}"
    )
    ordinals = {int(FINDING_RE.match(str(k)).group("ordinal")) for k in found}
    assert ordinals == {0, 1}, (
        f"Erwartet wurden die Ordinale 0 und 1, gemeldet: {sorted(ordinals)}"
    )
    per_function = Counter(_function_of(str(k)) for k in found)
    assert list(per_function) == [
        f"{synthetic}::build_columns"
    ], f"Beide Funde gehoeren in build_columns: {dict(per_function)}"


def test_reintroducing_line_dedup_loses_one_of_the_two_findings(tmp_path):
    """MUTATIONS-GEGENPROBE zum Test darueber.

    Baut man die Zeilen-Deduplizierung (``sorted(set(lines))``) wieder in
    ``_number_findings()`` ein, meldet derselbe Scan nur noch EINEN Eintrag.
    Damit ist gezeigt, dass der Test oben tatsaechlich an dieser Zeile haengt
    und nicht ohnehin gruen waere.

    Mutiert wird eine KOPIE des Waechters in ``tmp_path`` -- die echte Datei
    im Repo wird nicht angefasst. Dass die Mutation ueberhaupt gegriffen hat,
    wird selbst behauptet (Trefferzahl), sonst waere die Gegenprobe eine
    Attrappe, die immer gruen ist.
    """
    original = (_TESTS_DIR / GUARD_FILES["aufloesung"]).read_text(encoding="utf-8")
    ungedeckt = "for ordinal, lineno in enumerate(sorted(lines)):"
    dedupliziert = "for ordinal, lineno in enumerate(sorted(set(lines))):"
    assert original.count(ungedeckt) == 1, (
        "Die Zaehlzeile von _number_findings() sieht anders aus als erwartet "
        "-- die Gegenprobe wuerde nichts mutieren und waere wertlos. "
        f"Gesucht: {ungedeckt!r}"
    )

    mutiert_pfad = tmp_path / "mutierter_aufloesungs_waechter.py"
    mutiert_pfad.write_text(
        original.replace(ungedeckt, dedupliziert), encoding="utf-8"
    )
    spec = importlib.util.spec_from_file_location(
        f"gz_guard_mutiert_{tmp_path.name}", mutiert_pfad
    )
    mutiert = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mutiert
    spec.loader.exec_module(mutiert)

    synthetic = _write_two_drops_one_line(tmp_path)

    assert len(_guard("aufloesung")._find_violations(synthetic)) == 2, (
        "Vorbedingung der Gegenprobe: der ECHTE Waechter meldet hier zwei "
        "Funde."
    )
    assert len(mutiert._find_violations(synthetic)) == 1, (
        "Die wieder eingebaute Deduplizierung muesste einen der beiden Funde "
        "schlucken. Tut sie es nicht, misst der Test darueber etwas anderes "
        "als die Zaehlweise -- dann ist der Nachweis wertlos. Code reference: "
        f"{sorted(mutiert._find_violations(synthetic))}"
    )


# ---------------------------------------------------------------------------
# AC-5: der Zeitzonen-Waechter kennt den umschliessenden Funktionsraum
# ---------------------------------------------------------------------------


def test_timezone_guard_finding_names_the_enclosing_function(tmp_path):
    """
    GIVEN eine synthetische Ausgabedatei mit drei Verstoessen in drei Raeumen:
      Modulebene, verschachtelte innere Funktion, Geschwisterfunktion
    WHEN der Zeitzonen-Waechter sie scannt
    THEN nennt jeder Schluessel den RICHTIGEN Raum -- ``<module>``, ``inner``
      (NICHT ``outer``, dessen Raum er nicht ist) und ``sibling``.

    Der Waechter weiss heute nichts ueber Funktionen (Spec AC-5); Vorbild sind
    die ``_scopes()`` der beiden anderen Waechter. Deren Modulraum-Platzhalter
    wird hier aus dem Waechter GELESEN, nicht abgetippt.
    """
    guard = _guard("zeitzone")
    module_scope = getattr(guard, "_MODULE_SCOPE", None)
    assert module_scope, (
        "Der Zeitzonen-Waechter kennt keinen Modulraum-Platzhalter "
        "(_MODULE_SCOPE) -- er hat heute gar keine Bereichsverfolgung. "
        "Nachruesten wie in test_success_status_guard.py / "
        "test_resolution_loss_guard.py (_scopes(), _MODULE_SCOPE = "
        "'<module>')."
    )

    synthetic = tmp_path / "synthetic_scoped_timezone.py"
    synthetic.write_text(
        "from zoneinfo import ZoneInfo\n"
        "\n"
        "BOOT_STAMP = RAW_START.astimezone(ZoneInfo('UTC'))\n"
        "\n"
        "\n"
        "def outer(ts, tz):\n"
        "    def inner(value):\n"
        "        return value.astimezone(tz).strftime('%H:%M')\n"
        "\n"
        "    return inner(ts)\n"
        "\n"
        "\n"
        "def sibling(ts, tz):\n"
        "    return ts.astimezone(tz).strftime('%H:%M')\n",
        encoding="utf-8",
    )

    found = guard._find_violations(synthetic)
    malformed = _malformed(found)
    assert not malformed, (
        "Der Zeitzonen-Waechter schluesselt weiterhin ohne Funktionsanteil "
        f"(heute 'pfad:zeile'): {malformed}"
    )

    functions = {
        FINDING_RE.match(str(k)).group("function") for k in found
    }
    assert {module_scope, "inner", "sibling"} <= functions, (
        "Der Zeitzonen-Waechter ordnet die drei Funde nicht den richtigen "
        f"Raeumen zu. Erwartet: {module_scope}, inner, sibling. Gemeldet: "
        f"{sorted(functions)} (Fundliste {sorted(found)})"
    )
    assert "outer" not in functions, (
        "Der Fund aus der inneren Funktion wurde 'outer' zugeschrieben -- die "
        "Bereichsverfolgung steigt in verschachtelte Funktionen ab, statt sie "
        "als eigenen Raum zu behandeln (Semantik der beiden anderen "
        f"Waechter). Gemeldet: {sorted(found)}"
    )
