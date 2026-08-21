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

from api.routers.compare import get_compare_metrics
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

    #1848 A2: der Ausblick speichert reine KENNUNGEN, die Auswertungen leitet
    der Katalog ab -- eine Probe je Auswertung gibt es nicht mehr, weil sich
    eine einzelne Auswertung gar nicht mehr auswaehlen laesst. Die Zusicherung
    ist unveraendert und wird dadurch sogar direkter: was hier auftaucht, ist
    genau das, was ein Nutzer im Ausblick speichern koennte. Der Rueckgabewert
    behaelt die Form ``"kennung/auswertung"``, damit die Positivkontrolle und
    die Gegenprobe unveraendert lesbar bleiben."""
    register = {m.id: m for m in get_all_metrics()}
    treffer: list[str] = []
    for metric_id in metric_ids:
        if not resolver([metric_id]):
            continue
        aggregationen = getattr(register.get(metric_id), "default_aggregations", ("min", "max"))
        treffer.extend(f"{metric_id}/{a}" for a in (aggregationen or ("min", "max")))
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


# ---------------------------------------------------------------------------
# F002 -- die bewachte Menge selbst ist bewacht
#
# Adversary-Befund: `GEHZEIT_METRIC_IDS` auf zwei Kennungen zu kuerzen liess
# ALLE Tests gruen -- `temperature_day_high` und `wind_chill_day_low` haetten
# danach ausser dem Literal keinen Anker mehr gehabt. Genau die Fehlerklasse,
# gegen die diese Scheibe gebaut ist: eine Liste, deren Zusicherung still zur
# Luege wird. Die erwartete Menge wird deshalb aus dem ZENTRALREGISTER
# abgeleitet und gegen das Literal gestellt.
# ---------------------------------------------------------------------------
def _register_gehzeit_ids(
    definitionen: list[MetricDefinition] | None = None,
) -> list[str]:
    """Welche Registereintraege tragen den Zusatz '(Gehzeit)' im `label_de`?
    Das ist die im Register erkennbare Menge der Gehzeit-Groessen -- unabhaengig
    davon, was dieser Waechter oben als Literal fuehrt."""
    if definitionen is None:
        definitionen = get_all_metrics()
    return sorted(
        m.id for m in definitionen
        if GEHZEIT_LABEL_ZUSATZ in (getattr(m, "label_de", "") or "")
    )


def _mengen_abweichung(
    bewacht: tuple[str, ...] | list[str], abgeleitet: list[str]
) -> tuple[list[str], list[str]]:
    """Differenz in BEIDE Richtungen: (fehlt im Waechter, fehlt im Register).
    EIN Aufbau fuer Zusicherung und Gegenprobe."""
    return (
        sorted(set(abgeleitet) - set(bewacht)),
        sorted(set(bewacht) - set(abgeleitet)),
    )


def test_f002_bewachte_menge_deckt_sich_mit_den_gehzeit_eintraegen_des_registers():
    """Die vier Kennungen stehen nicht mehr allein als Literal da: die erwartete
    Menge kommt aus dem Register (`label_de` traegt '(Gehzeit)'). Schrumpft das
    Literal, wird das rot -- kommt ueber #1468 eine neue Gehzeit-Groesse dazu,
    die hier nicht mitbewacht wird, ebenfalls."""
    abgeleitet = _register_gehzeit_ids()
    assert abgeleitet, (
        "Positivkontrolle: das Register liefert keinen einzigen Eintrag mit dem "
        f"Zusatz '{GEHZEIT_LABEL_ZUSATZ}' -- die Ableitung traegt dann nichts und "
        "eine Uebereinstimmung waere ueber die leere Menge trivial wahr."
    )
    fehlt_im_waechter, fehlt_im_register = _mengen_abweichung(GEHZEIT_METRIC_IDS, abgeleitet)
    assert (fehlt_im_waechter, fehlt_im_register) == ([], []), (
        "Die bewachte Menge deckt sich nicht mit den Gehzeit-Eintraegen des "
        f"Zentralregisters. Im Waechter (GEHZEIT_METRIC_IDS) fehlen: {fehlt_im_waechter} "
        f"-- im Register fehlt der '{GEHZEIT_LABEL_ZUSATZ}'-Eintrag zu: {fehlt_im_register}. "
        "Beides ist ein Befund: eine hier stillschweigend entfernte Kennung waere "
        "unbewacht, eine neue Gehzeit-Groesse im Register muss mitbewacht werden."
    )


def test_f002_gegenprobe_geschrumpfte_und_gewachsene_menge_werden_benannt():
    """F002 Wirkungsnachweis an KOPIEN, in beide Richtungen -- ohne ihn waere
    nicht bewiesen, dass die Abweichung ueberhaupt auffaellt."""
    abgeleitet = _register_gehzeit_ids()

    # (a) Waechter geschrumpft: zwei Kennungen ohne Anker.
    geschrumpft = ("temperature_day_low", "wind_chill_day_high")
    fehlt_im_waechter, fehlt_im_register = _mengen_abweichung(geschrumpft, abgeleitet)
    assert fehlt_im_waechter == ["temperature_day_high", "wind_chill_day_low"], (
        f"Eine geschrumpfte Waechter-Menge faellt nicht auf: {fehlt_im_waechter}"
    )
    assert fehlt_im_register == [], f"Falschmeldung in der Gegenrichtung: {fehlt_im_register}"

    # (b) Register um eine neue Gehzeit-Groesse gewachsen, Waechter unveraendert.
    vorbild = next(m for m in get_all_metrics() if m.id == "temperature_day_low")
    register_kopie = list(get_all_metrics()) + [
        replace(vorbild, id="humidity_day_high", label_de="Tages-Höchstfeuchte (Gehzeit)")
    ]
    fehlt_im_waechter, fehlt_im_register = _mengen_abweichung(
        GEHZEIT_METRIC_IDS, _register_gehzeit_ids(register_kopie)
    )
    assert fehlt_im_waechter == ["humidity_day_high"], (
        f"Eine neue Gehzeit-Groesse im Register faellt nicht auf: {fehlt_im_waechter}"
    )
    assert _register_gehzeit_ids() == abgeleitet, (
        "Die Gegenprobe hat das ECHTE Register veraendert."
    )


# ---------------------------------------------------------------------------
# F001 -- geprueft wird die LEITUNG, nicht nur die Funktion
#
# Adversary-Befund: haengt `GET /api/compare/metrics` eine Gehzeit-Groesse an
# die ANTWORT, blieb alles gruen -- der Waechter prueft nur
# `get_compare_metric_catalog()`. Die Spec begruendet den Verzicht auf einen
# Frontend-Waechter aber damit, dass die Bedienflaeche den ENDPOINT liest
# (compareMetricCatalogLoader.ts:101). Zwischen Funktion und Antwort passt eine
# Aenderung. Reiner Funktionsaufruf: kein Netz, kein HTTP-Client, kein
# TestClient-Server, kein Mock.
# ---------------------------------------------------------------------------
# Herkunft einer Fundstelle -- die Meldung muss unterscheidbar sagen, ueber
# WELCHES Feld der Verstoss aufgefallen ist, sonst raetselt der naechste Leser.
_FUND_UEBER_METRIC_ID = "ueber metric_id"
_FUND_UEBER_LABEL = "ueber Beschriftung"


def _verbotene_ids_in_endpoint_antwort(
    verboten: tuple[str, ...] = GEHZEIT_METRIC_IDS, payload: dict | None = None
) -> list[str]:
    """Welche Eintraege der Nutzlast von `GET /api/compare/metrics`
    (`{"metrics": [...]}`) tragen eine Gehzeit-Groesse an die Bedienflaeche?
    Leer = in Ordnung.

    ZWEI Wege, weil die Bedienflaeche zwei Felder liest (F-ADV2-1):
    `compareMetricCatalogLoader.ts:57-58` baut Auswahl und Wertebereichs-Zeile
    aus `key`/`label`, `metric_id` ist dort optional und nur Filterfeld (:136).
    Ein Antwort-Eintrag OHNE `metric_id`, aber mit dem Zusatz '(Gehzeit)' in
    der Beschriftung, erreicht den Wertebereichs-Editor und den Trip-Reiter
    genauso -- ueber `metric_id` allein waere er unsichtbar.
    """
    if payload is None:
        payload = get_compare_metrics()
    eintraege = payload.get("metrics") or []
    fundstellen = {
        f"{e['metric_id']} ({_FUND_UEBER_METRIC_ID})"
        for e in eintraege
        if e.get("metric_id") in set(verboten)
    }
    # Beschriftungs-Weg: unabhaengig von `verboten`, denn '(Gehzeit)' IST das
    # Merkmal der Gehzeit-Fensterung im Register (vgl. _register_gehzeit_ids).
    fundstellen |= {
        f"{e.get('key') or e.get('metric_id') or '<ohne key>'} "
        f"({_FUND_UEBER_LABEL}: {e.get('label')!r})"
        for e in eintraege
        if GEHZEIT_LABEL_ZUSATZ in (e.get("label") or "")
    }
    return sorted(fundstellen)


def test_f001_endpoint_antwort_bietet_keine_gehzeit_kennung_an():
    """Die Antwort selbst -- nicht die dahinterliegende Funktion -- fuehrt keine
    der vier Kennungen. Das ist die Leitung, die die Bedienflaeche liest."""
    gefunden = _verbotene_ids_in_endpoint_antwort()
    assert gefunden == [], (
        "GET /api/compare/metrics liefert Gehzeit-Kennungen an die "
        f"Bedienflaeche aus: {gefunden} -- " + _verstoss_meldung(gefunden)
    )


def test_f001_positivkontrolle_derselbe_suchweg_findet_temperature_in_der_antwort():
    """Ohne sie waere die Zusicherung oben wieder nur 'gruen, weil am falschen
    Ort gesucht': derselbe Suchweg muss finden, was in der Antwort stehen MUSS
    (`temperature`, getragen vom Eintrag `temp_min_c`)."""
    erwartet = f"temperature ({_FUND_UEBER_METRIC_ID})"
    assert _verbotene_ids_in_endpoint_antwort(verboten=("temperature",)) == [erwartet], (
        "Der Suchweg findet 'temperature' nicht in der Endpoint-Antwort -- das "
        "Gruen stammt dann nicht aus Abwesenheit, sondern aus dem falschen Ort."
    )
    keys = {e.get("key") for e in get_compare_metrics().get("metrics") or []}
    assert "temp_min_c" in keys, (
        f"Erwarteter Traeger-Eintrag temp_min_c fehlt in der Antwort: {sorted(keys)[:5]}"
    )


def test_f001_gegenprobe_an_die_antwort_gehaengte_kennung_wird_gemeldet():
    """F001 Wirkungsnachweis an KOPIEN der Nutzlast, auf BEIDEN Wegen -- (a) mit
    `metric_id` (die Mutation des ersten Adversary), (b) OHNE `metric_id`, nur
    mit '(Gehzeit)' in der Beschriftung (F-ADV2-1: dieser Eintrag erreichte den
    Wertebereichs-Editor, ohne dass ein Test rot wurde)."""
    echt = get_compare_metrics()

    # (a) Weg ueber das Filterfeld `metric_id`.
    kopie_a = {"metrics": list(echt.get("metrics") or []) + [
        {"key": "kunst_wind_chill_day_high", "unit": "°C", "decimals": 0, "kind": "range",
         "metric_id": "wind_chill_day_high", "aggregation": "max"}
    ]}
    assert _verbotene_ids_in_endpoint_antwort(payload=kopie_a) == [
        f"wind_chill_day_high ({_FUND_UEBER_METRIC_ID})"
    ], "Der Waechter bemerkt eine an die Endpoint-Antwort gehaengte Kennung nicht."

    # (b) Weg ueber die Beschriftung -- Eintrag OHNE `metric_id`.
    label = "Gefuehlte Tages-Hoechsttemperatur (Gehzeit)"
    kopie_b = {"metrics": list(echt.get("metrics") or []) + [
        {"key": "wind_chill_day_high_c", "unit": "°C", "decimals": 0, "kind": "range",
         "label": label, "aggregation": "max"}
    ]}
    assert _verbotene_ids_in_endpoint_antwort(payload=kopie_b) == [
        f"wind_chill_day_high_c ({_FUND_UEBER_LABEL}: {label!r})"
    ], (
        "Ein Antwort-Eintrag OHNE `metric_id`, aber mit '(Gehzeit)' in der "
        "Beschriftung faellt nicht auf -- er erreicht die Bedienflaeche ueber "
        "`key`/`label` trotzdem (compareMetricCatalogLoader.ts:57-58)."
    )

    assert _verbotene_ids_in_endpoint_antwort() == [], (
        "Die Gegenprobe hat die ECHTE Antwort veraendert."
    )


def test_f001_regulaerer_eintrag_ohne_gehzeit_zusatz_gilt_nicht_als_verstoss():
    """Falsch-Positiv-Probe zum Beschriftungs-Weg: ein normaler Antwort-Eintrag
    ohne '(Gehzeit)' im Label darf NICHT anschlagen -- sonst waere die Roete
    des Waechters wertlos, weil jeder neue Ortsvergleich-Eintrag sie ausloest."""
    echt = get_compare_metrics()
    kopie = {"metrics": list(echt.get("metrics") or []) + [
        {"key": "kunst_humidity", "unit": "%", "decimals": 0, "kind": "range",
         "label": "Relative Luftfeuchte (Tagesfenster)", "aggregation": "max"}
    ]}
    assert _verbotene_ids_in_endpoint_antwort(payload=kopie) == [], (
        "Der Waechter meldet einen regulaeren Eintrag ohne '(Gehzeit)'-Zusatz "
        "als Verstoss -- Falsch-Positiv."
    )
