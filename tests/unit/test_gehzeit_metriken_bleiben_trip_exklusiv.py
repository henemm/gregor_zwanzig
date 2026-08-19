"""Die vier Gehzeit-Groessen bleiben trip-exklusiv (#1848 Scheibe C).

SPEC: docs/specs/modules/feat_1848_c_waechter_gehzeit_trip_exklusiv.md

PO-Entscheid 2026-08-19: `temperature_day_low`, `temperature_day_high`,
`wind_chill_day_low`, `wind_chill_day_high` sind dem Trip vorbehalten und
werden im Ortsvergleich NIE angeboten. Bisher haelt das nur, weil es niemand
verletzt hat: der bestehende Drift-Waechter
(`test_compare_catalog_derives_from_central_catalog.py`) ZIEHT die vier ueber
`CENTRAL_METRICS_COVERED_ELSEWHERE` von seiner Pruefmenge AB -- fuer sie ist
"hat keinen Compare-Eintrag" trivial wahr.

🔴 EHRLICHKEITSVERMERK ZUR ROETE: Die Invariante haelt am Bestand. AC-1 bis
AC-4 und AC-7 sind deshalb sofort gruen -- sie nageln Bestandsverhalten fest,
und ihre Aussagekraft kommt NICHT aus ihrer Roete, sondern aus den
Gegenproben (jede Zusicherung laeuft ueber eine benannte Hilfsfunktion, die
im selben Lauf gegen eine kuenstlich gebrochene KOPIE gefuehrt wird) und aus
den Positivkontrollen (derselbe Suchweg findet, was dort stehen MUSS). Echt
rot am Bestand sind AC-5 (toter Funktionsname `_collect_hiking_window_dps()`)
und AC-6 (ueberholte Rueckbau-Zusagen).

Test-Politik: Kern-Schicht -- kein Netz, kein Mock, kein `patch()`. Die echten
Katalog-/Registerlisten werden NIE veraendert, nur Kopien. Pfadregel #1409:
Prueflinge relativ zu DIESER Testdatei aufgeloest.
"""
from __future__ import annotations

import ast
import builtins
import importlib.util
import io
import re
import tokenize
from dataclasses import replace
from pathlib import Path

from app.metric_catalog import MetricDefinition, get_all_metrics
from output.renderers.compare_hourly_metric_ids import HOURLY_EXCLUDED_METRIC_IDS
from output.renderers.compare_metric_catalog import get_compare_metric_catalog
from output.renderers.compare_outlook_metric_ids import resolve_outlook_metrics

# Pfadregel #1409: Prueflinge relativ zur eigenen Testdatei, nie ueber einen
# festen Hauptrepo-Pfad -- sonst kaeme falsches Gruen aus dem Worktree.
_UNIT_DIR = Path(__file__).resolve().parent
_REPO = _UNIT_DIR.parents[1]
_METRIC_CATALOG_PY = _REPO / "src" / "app" / "metric_catalog.py"
_DRIFT_GUARD_PY = _UNIT_DIR / "test_compare_catalog_derives_from_central_catalog.py"

# AC-7: VIER NAMENTLICH GENANNTE Kennungen -- ausdruecklich kein Namensmuster
# ("alles mit _day_"). #1468 fuegt dem Register additiv Eintraege hinzu; ein
# Musterwaechter wuerde davon rot, ein Namenswaechter nicht.
GEHZEIT_METRIC_IDS: tuple[str, ...] = (
    "temperature_day_low", "temperature_day_high",
    "wind_chill_day_low", "wind_chill_day_high",
)
GEHZEIT_LABEL_ZUSATZ = "(Gehzeit)"


# ---------------------------------------------------------------------------
# Hilfsfunktionen -- jede nimmt ihre Eingabe als Parameter (Default = echte
# Daten), damit Produktions-Zusicherung und Gegenprobe DIESELBE Logik fahren.
# ---------------------------------------------------------------------------
def _verbotene_ids_im_compare_katalog(
    verboten: tuple[str, ...] = GEHZEIT_METRIC_IDS, entries: list[dict] | None = None
) -> list[str]:
    """Tuer 1: welche der genannten Kennungen traegt ein Ortsvergleich-Katalog-
    Eintrag als `metric_id`? Leer = in Ordnung."""
    if entries is None:
        entries = get_compare_metric_catalog()
    vorhanden = {e.get("metric_id") for e in entries if e.get("metric_id")}
    return sorted(set(verboten) & vorhanden)


def _verstoss_meldung(gefunden: list[str]) -> str:
    """EIN Meldungsaufbau fuer Zusicherung und Gegenprobe -- AC-1 verlangt,
    dass der Fehlertext die betroffene Kennung BENENNT."""
    return (
        "Gehzeit-Kennungen im Ortsvergleich angeboten (trip-exklusiv laut "
        f"PO-Entscheid 2026-08-19, #1848): {gefunden}"
    )


def _gehzeit_ids_ohne_stundenausschluss(
    excluded: frozenset[str] | set[str] = HOURLY_EXCLUDED_METRIC_IDS,
) -> list[str]:
    """Tuer 2: welche der vier fehlen in `HOURLY_EXCLUDED_METRIC_IDS`? Hier ist
    ENTHALTENSEIN das Soll -- der Ausschluss ist die Zusicherung."""
    return sorted(set(GEHZEIT_METRIC_IDS) - set(excluded))


def _im_ausblick_waehlbar(
    metric_ids: tuple[str, ...] = GEHZEIT_METRIC_IDS, resolver=resolve_outlook_metrics
) -> list[str]:
    """Tuer 3: welche der genannten Kennungen loest der 3-Tages-Ausblick auf?
    Probiert je Kennung alle im Register vorgesehenen Auswertungen durch."""
    register = {m.id: m for m in get_all_metrics()}
    treffer: list[str] = []
    for metric_id in metric_ids:
        aggregationen = getattr(register.get(metric_id), "default_aggregations", ("min", "max"))
        for aggregation in aggregationen or ("min", "max"):
            if resolver([{"metric_id": metric_id, "aggregation": aggregation}]):
                treffer.append(f"{metric_id}/{aggregation}")
    return sorted(treffer)


def _gehzeit_labels_ohne_zusatz(
    definitionen: list[MetricDefinition] | None = None,
) -> list[str]:
    """AC-4 gegen DATEN (`MetricDefinition.label_de`), nicht gegen Fliesstext:
    welche der vier haben keinen Registereintrag oder keinen '(Gehzeit)'?"""
    if definitionen is None:
        definitionen = get_all_metrics()
    register = {m.id: m for m in definitionen}
    return sorted(
        metric_id for metric_id in GEHZEIT_METRIC_IDS
        if GEHZEIT_LABEL_ZUSATZ not in (getattr(register.get(metric_id), "label_de", "") or "")
    )


def _kommentartext(quelltext: str) -> str:
    """Alle Kommentare einer Python-Quelle als EIN normalisierter Text.
    Zeilenumbrueche und Einrueckung fallen weg -- so haengt keine Zusicherung
    an einer Zeilennummer (Muster #1466)."""
    kommentare = [
        tok.string.lstrip("#").strip()
        for tok in tokenize.generate_tokens(io.StringIO(quelltext).readline)
        if tok.type == tokenize.COMMENT
    ]
    return re.sub(r"\s+", " ", " ".join(kommentare))


def _definierte_funktionsnamen(wurzeln: tuple[Path, ...]) -> set[str]:
    """Alle im Baum per `def`/`async def` definierten Namen (AST, zur Laufzeit
    aufgeloest) plus die Builtins."""
    namen = set(dir(builtins))
    for wurzel in wurzeln:
        for datei in wurzel.rglob("*.py"):
            baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
            namen.update(
                knoten.name for knoten in ast.walk(baum)
                if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return namen


def _tote_kommentar_namen(quelltext: str, definiert: set[str]) -> list[str]:
    """AC-5: in Kommentaren als `name()` genannte Funktionsnamen, die der Code
    nicht kennt. Schluessel ist der NAME, nicht die Zeile."""
    genannt = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\(\)", _kommentartext(quelltext)))
    return sorted(genannt - definiert)


def _drift_guard_modul():
    """Den Nachbar-Waechter als Modul laden (relativ zur eigenen Testdatei),
    damit AC-6 (b) gegen DATEN statt gegen Dateitext prueft."""
    spec = importlib.util.spec_from_file_location("_drift_guard_1848c", _DRIFT_GUARD_PY)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# ---------------------------------------------------------------------------
# AC-1 / AC-2 -- Tuer 1 (Katalog) samt Positivkontrolle
# ---------------------------------------------------------------------------
def test_ac1_kein_ortsvergleich_eintrag_traegt_eine_gehzeit_kennung():
    """AC-1. Gruen am Bestand (Invariante haelt, s. Modul-Docstring); die
    Aussagekraft liefert die Gegenprobe unten."""
    gefunden = _verbotene_ids_im_compare_katalog()
    assert gefunden == [], _verstoss_meldung(gefunden)


def test_ac1_gegenprobe_kuenstlicher_katalogeintrag_wird_namentlich_gemeldet():
    """AC-1 Wirkungsnachweis: dieselbe Pruef-Funktion gegen eine KOPIE des
    Katalogs mit kuenstlichem `temperature_day_low`-Eintrag. Ohne diesen
    Nachweis waere nicht bewiesen, dass der Waechter ueberhaupt etwas prueft."""
    kopie = list(get_compare_metric_catalog()) + [
        {"key": "kunst_temp_day_low", "unit": "°C", "decimals": 0, "kind": "range",
         "metric_id": "temperature_day_low", "aggregation": "min"}
    ]
    gefunden = _verbotene_ids_im_compare_katalog(entries=kopie)
    assert gefunden == ["temperature_day_low"], (
        f"Waechter erkennt den kuenstlich hinzugefuegten Eintrag nicht: {gefunden}"
    )
    assert "temperature_day_low" in _verstoss_meldung(gefunden), (
        f"Fehlertext nennt die Kennung nicht: {_verstoss_meldung(gefunden)}"
    )
    assert _verbotene_ids_im_compare_katalog() == [], (
        "Die Gegenprobe hat den ECHTEN Katalog veraendert -- es darf nur eine "
        "Kopie manipuliert werden."
    )


def test_ac2_positivkontrolle_derselbe_suchweg_findet_temperature():
    """AC-2, der wichtigste Test dieser Datei: derselbe Suchweg, der oben die
    Abwesenheit feststellt, angewendet auf eine Kennung, die im Ortsvergleich
    vorkommen MUSS (`temperature` ueber den Eintrag `temp_min_c`). Ohne ihn
    waere AC-1 auch gruen, wenn am falschen Ort gesucht wird."""
    assert _verbotene_ids_im_compare_katalog(verboten=("temperature",)) == ["temperature"], (
        "Der Suchweg findet 'temperature' nicht im Ortsvergleich-Katalog -- "
        "das Gruen von AC-1 stammt dann nicht aus Abwesenheit, sondern daraus, "
        "dass am falschen Ort gesucht wird."
    )
    keys = {e.get("key") for e in get_compare_metric_catalog()}
    assert "temp_min_c" in keys, f"Erwarteter Traeger-Eintrag temp_min_c fehlt: {sorted(keys)[:5]}"


# ---------------------------------------------------------------------------
# AC-3 -- Tuer 2 (Stundenverlauf) und Tuer 3 (3-Tages-Ausblick)
# ---------------------------------------------------------------------------
def test_ac3_tuer2_alle_vier_stehen_im_stundenverlaufs_ausschluss():
    """AC-3, Tuer 2: ENTHALTENSEIN in `HOURLY_EXCLUDED_METRIC_IDS` ist das
    Soll. Gruen am Bestand (#1728 hat den Ausschluss gesetzt)."""
    fehlend = _gehzeit_ids_ohne_stundenausschluss()
    assert fehlend == [], (
        f"Gehzeit-Kennungen ohne Stundenverlaufs-Ausschluss: {fehlend}"
    )


def test_ac3_tuer2_gegenprobe_entfernter_ausschluss_wird_gemeldet():
    """AC-3 Wirkungsnachweis Tuer 2 an einer KOPIE der Ausschlussmenge."""
    kopie = set(HOURLY_EXCLUDED_METRIC_IDS) - {"wind_chill_day_high"}
    assert _gehzeit_ids_ohne_stundenausschluss(kopie) == ["wind_chill_day_high"], (
        "Waechter bemerkt eine aus der Ausschlussmenge entfernte Kennung nicht."
    )
    assert _gehzeit_ids_ohne_stundenausschluss() == [], (
        "Die Gegenprobe hat die ECHTE Ausschlussmenge veraendert."
    )


def test_ac3_tuer3_keine_gehzeit_kennung_ist_im_ausblick_aufloesbar():
    """AC-3, Tuer 3: der 3-Tages-Ausblick verwirft alle vier."""
    waehlbar = _im_ausblick_waehlbar()
    assert waehlbar == [], f"Gehzeit-Kennungen im 3-Tages-Ausblick waehlbar: {waehlbar}"


def test_ac3_tuer3_positivkontrolle_temperature_ist_aufloesbar():
    """AC-3/AC-2 fuer Tuer 3: derselbe Suchweg loest `temperature` auf --
    sonst waere die Abwesenheit oben nur die Abwesenheit des Suchwegs."""
    assert _im_ausblick_waehlbar(metric_ids=("temperature",)), (
        "Der Ausblick-Resolver loest nicht einmal 'temperature' auf -- der "
        "Suchweg traegt nicht."
    )


def test_ac3_tuer3_gegenprobe_durchlassender_resolver_wird_gemeldet():
    """AC-3 Wirkungsnachweis Tuer 3: ein kuenstlicher Resolver, der alles
    annimmt (kein Mock -- eine im Test definierte Funktion), muss alle vier
    Kennungen als waehlbar melden."""
    alles_durchlassend = lambda eintraege: list(eintraege)  # noqa: E731
    gemeldet = _im_ausblick_waehlbar(resolver=alles_durchlassend)
    assert {t.split("/")[0] for t in gemeldet} == set(GEHZEIT_METRIC_IDS), (
        f"Waechter meldet bei durchlassendem Resolver nicht alle vier: {gemeldet}"
    )


# ---------------------------------------------------------------------------
# AC-4 -- "(Gehzeit)" ist tragend, an den Daten festgenagelt
# ---------------------------------------------------------------------------
def test_ac4_alle_vier_label_de_tragen_den_gehzeit_zusatz():
    """AC-4. Gruen am Bestand (metric_catalog.py:173,190,260,271)."""
    ohne = _gehzeit_labels_ohne_zusatz()
    assert ohne == [], (
        f"Registereintraege ohne tragenden Zusatz '{GEHZEIT_LABEL_ZUSATZ}': {ohne} -- "
        "der Zusatz unterscheidet Gehzeit-Fensterung vom konfigurierten Tagesfenster."
    )


def test_ac4_gegenprobe_kopie_ohne_zusatz_wird_gemeldet():
    """AC-4 Wirkungsnachweis an einer KOPIE des Registers (dataclasses.replace,
    kein Mock): der entfernte Zusatz muss auffallen."""
    kopie = [
        replace(m, label_de="Tages-Tiefsttemperatur") if m.id == "temperature_day_low" else m
        for m in get_all_metrics()
    ]
    assert _gehzeit_labels_ohne_zusatz(kopie) == ["temperature_day_low"], (
        "Waechter bemerkt den entfernten '(Gehzeit)'-Zusatz nicht."
    )
    assert _gehzeit_labels_ohne_zusatz() == [], "Die Gegenprobe hat das ECHTE Register veraendert."


# ---------------------------------------------------------------------------
# AC-5 -- in Kommentaren genannte Funktionsnamen sind auflösbar
# doc-compliance-test
# ---------------------------------------------------------------------------
def test_ac5_kommentar_funktionsnamen_sind_im_code_aufloesbar():  # doc-compliance-test
    """AC-5, ROT AM BESTAND: die vier Blockkommentare zu den Gehzeit-Groessen
    nennen `_collect_hiking_window_dps()` -- diese Funktion existiert nicht,
    sie heisst `collect_hiking_window_points()` (renderers/day_window.py).
    Geprueft wird laufzeitaufgeloest ueber `ast` (Muster #1466), NICHT ueber
    Zeilennummern. Doku-Konformitaetstest, kein Verhaltensnachweis."""
    definiert = _definierte_funktionsnamen((_REPO / "src", _REPO / "api"))
    tot = _tote_kommentar_namen(_METRIC_CATALOG_PY.read_text(encoding="utf-8"), definiert)
    assert tot == [], (
        f"Kommentare in {_METRIC_CATALOG_PY.relative_to(_REPO)} nennen Funktionsnamen, "
        f"die im Code nicht auflösbar sind: {tot} -- Name korrigieren oder Kommentar "
        "streichen; ein Kommentar, der auf einen nicht existierenden Namen zeigt, "
        "führt jeden Leser in die Irre."
    )


def test_ac5_aufloeser_findet_echte_namen_und_meldet_erfundene():  # doc-compliance-test
    """AC-5 Positivkontrolle + Gegenprobe: der Aufloeser darf nach der
    Korrektur nicht trivial gruen sein. Gegen einen KUENSTLICHEN Quelltext
    (kein Dateizugriff): ein existierender Name schweigt, ein erfundener wird
    gemeldet."""
    definiert = _definierte_funktionsnamen((_REPO / "src",))
    assert "collect_hiking_window_points" in definiert, (
        "Der AST-Scan findet nicht einmal collect_hiking_window_points() -- "
        "die Scanflaeche stimmt nicht."
    )
    kunst = "# richtig: collect_hiking_window_points()\n# falsch: _gibt_es_nicht_1848c()\nX = 1\n"
    assert _tote_kommentar_namen(kunst, definiert) == ["_gibt_es_nicht_1848c"], (
        "Aufloeser meldet den erfundenen Namen nicht oder meldet den echten mit."
    )


# ---------------------------------------------------------------------------
# AC-6 -- die ueberholten Rueckbau-Zusagen
# doc-compliance-test
# ---------------------------------------------------------------------------
def test_ac6a_rueckbaupfad_kommentar_gibt_den_po_entscheid_wieder():  # doc-compliance-test
    """AC-6 (a), ROT AM BESTAND: der Blockkommentar behauptet, die vier Zeilen
    fielen mit #1848 'ersatzlos weg'. Der PO-Entscheid vom 2026-08-19 sagt das
    Gegenteil. Geprueft wird der ueber alle Kommentarzeilen normalisierte Text
    (kein Zeilenanker). Doku-Konformitaetstest."""
    text = _kommentartext(_DRIFT_GUARD_PY.read_text(encoding="utf-8"))
    assert "Deckungs-Ausnahme" in text, (
        "Positivkontrolle: die Kommentar-Extraktion liefert nicht einmal die "
        "Ueberschrift des Ausnahme-Blocks -- der Suchweg traegt nicht. "
        "(Docstrings sind KEINE Kommentare; hier wird bewusst nur `#` gelesen.)"
    )
    assert "ersatzlos weg" not in text.lower(), (
        "Der Rueckbaupfad-Kommentar behauptet weiterhin, die vier Zeilen fielen "
        "mit #1848 ersatzlos weg. Ueberholt durch den PO-Entscheid 2026-08-19: "
        "die vier Gehzeit-Groessen bleiben trip-exklusiv."
    )
    assert "trip-exklusiv" in text.lower(), (
        "Der Kommentar sagt nicht, dass die vier Kennungen trip-exklusiv bleiben."
    )


def test_ac6b_die_vier_einzelvermerke_sind_ebenfalls_aktualisiert():  # doc-compliance-test
    """AC-6 (b), ROT AM BESTAND: jeder der vier Ausnahme-Eintraege traegt den
    Text 'Rueckbau mit #1848'. Geprueft gegen die importierten DATEN, nicht
    gegen Dateitext. Der Blockkommentar allein genuegt nicht."""
    ausnahmen = _drift_guard_modul().CENTRAL_METRICS_COVERED_ELSEWHERE
    fehlend = sorted(set(GEHZEIT_METRIC_IDS) - set(ausnahmen))
    assert fehlend == [], (
        f"Die vier Gehzeit-Kennungen fehlen in CENTRAL_METRICS_COVERED_ELSEWHERE: "
        f"{fehlend} -- ohne sie waere diese Zusicherung ueber die leere Menge "
        "trivial wahr. Sie bleiben trip-exklusiv und damit ausgenommen."
    )
    ueberholt = sorted(m for m in GEHZEIT_METRIC_IDS if "rueckbau" in ausnahmen[m].lower())
    assert ueberholt == [], (
        f"Einzelvermerke kuendigen weiterhin einen Rueckbau mit #1848 an: {ueberholt} -- "
        "ueberholt durch den PO-Entscheid 2026-08-19 (trip-exklusiv)."
    )
    ohne_entscheid = sorted(
        m for m in GEHZEIT_METRIC_IDS if "trip-exklusiv" not in ausnahmen[m].lower()
    )
    assert ohne_entscheid == [], (
        f"Einzelvermerke nennen den Stand vom 2026-08-19 nicht: {ohne_entscheid}"
    )


# ---------------------------------------------------------------------------
# AC-7 -- namentlich, nie ueber ein Namensmuster
# ---------------------------------------------------------------------------
def test_ac7_neuer_register_eintrag_mit_day_im_namen_macht_nicht_rot():
    """AC-7: #1468 fuegt dem Register additiv Eintraege hinzu. Ein Waechter,
    der 'alles mit _day_' verboete, wuerde davon rot. Nachweis an KOPIEN:
    weder ein Compare-Eintrag noch ein Registereintrag mit `_day_` im Namen
    (aber nicht unter den vier) loest einen Befund aus."""
    fremd = "thunder_onset_day_shift_h"
    katalog_kopie = list(get_compare_metric_catalog()) + [
        {"key": "kunst_onset", "unit": "h", "decimals": 0, "kind": "range",
         "metric_id": fremd, "aggregation": "min"}
    ]
    assert _verbotene_ids_im_compare_katalog(entries=katalog_kopie) == [], (
        f"Waechter schlaegt auf die fremde Kennung '{fremd}' an -- er leitet aus "
        "einem Namensmuster ab statt aus den vier benannten Kennungen (AC-7)."
    )

    vorbild = next(m for m in get_all_metrics() if m.id == "temperature_day_low")
    register_kopie = list(get_all_metrics()) + [
        replace(vorbild, id=fremd, label_de="Vorverlagerung des Gewitterbeginns")
    ]
    assert _gehzeit_labels_ohne_zusatz(register_kopie) == [], (
        f"Die '(Gehzeit)'-Zusicherung verlangt den Zusatz auch von '{fremd}' -- "
        "sie zielt auf ein Namensmuster statt auf die vier benannten Kennungen."
    )
