"""Wächter — ein Erfolgsstatus wird abgeleitet, nie behauptet.

Issue #1405 (Hälfte B, „Erfolg heißt Wirkung"): die zweitgrößte Fehlerart im
Projekt ist die *unverdiente Erfolgsmeldung* — ein ``ok``/``sent``/
``success`` wird gemeldet, obwohl niemand geprüft hat, ob überhaupt etwas
angekommen ist. Belegte Vorfälle: #1290 (Scheduler meldet ``ok``, während
133 von 133 Presets scheitern), #1346 (stiller Totalausfall meldet Erfolg),
#1348, #1403 (Sende-Endpunkt meldet ``sent: true`` ohne Zustellung). Für den
Betrieb ist das schlimmer als ein Fehler: eine Fehlermeldung löst Alarm aus,
eine falsche Erfolgsmeldung schaltet ihn ab.

Die Norm dagegen existiert bereits im eigenen Code — sie ist nur nicht
überall angewandt: ``run_briefing_dispatch()``
(``src/services/dispatch_orchestrator.py:157``) liefert ein
``(sent, failed)``-Tupel aus einer Schleife mit Fehler-Isolierung, und beide
Vorbild-Endpunkte (``api/routers/scheduler.py:42-44`` und ``:142-144``)
leiten ihren Status daraus ab statt ihn zu setzen::

    sent, failed = service.send_reports_for_hour(current_hour)
    status = "partial" if failed > 0 else "ok"

Dieser Wächter rollt dieses vorhandene Muster auf die restlichen
Erfolgsmeldungen aus, statt eine neue Regel zu erfinden.

Vier Signaturen (plus die Variante 1c) — fünf eigene Erkennungen, EIN
gemeinsames Ergebnis-Dict (Spec Version 1.2, 2026-07-28):

1. **Klasse 1 — konstanter Erfolgswert aus einem Aufruf**
   (``KIND_CONSTANT_SUCCESS``): die Funktion leitet eine Variable aus einem
   Aufruf ab (``V = <Call>(...)``) ODER tätigt einen Aufruf, dessen Rückgabe
   gar nicht zugewiesen wird — und liefert danach ein Rückgabe-Dict bzw.
   Response-Objekt, dessen Erfolgs-Schlüssel (``status``/``sent``/
   ``success``/``ok``) ein hartkodiertes Literal trägt, das diese Variable
   NICHT referenziert. Kernaussage: *„Du hast einen aussagekräftigen Wert
   geholt — und dein Erfolgsstatus hängt am Ende gar nicht von ihm ab."*
   Ausschluss „except divergiert": ein ``except``-Handler, der selbst ein
   ``return`` mit einem anderen Wert liefert, schließt den Fund aus (AC-5).
   **Dekoratoren zählen nicht** (S-7): ein ``ast.Call`` im
   ``decorator_list`` (``@router.get("/health")``) wird im umschließenden
   Raum ausgewertet und erfüllt Bedingung (a) NICHT — sonst wäre AC-16
   strukturell unerfüllbar. **Schlüsselwortargumente zählen wie
   Dict-Schlüssel** (S-8): ``CommandResult(success=True, ...)`` ist dieselbe
   Behauptung wie ``{"success": True}`` — ohne diese Gleichstellung wären
   B12, B15, B16 und das gesamte B18-Muster unerreichbar.
2. **Klasse 1c — Erfolgsmarker vor der Tat**
   (``KIND_PRE_TRY_SUCCESS_MARKER``): eine Sammlung wird per ``.append()``
   befüllt, BEVOR der zugehörige riskante Versandaufruf stattfindet
   (``sent_channels.append("email")`` als Geschwister-Anweisung VOR dem
   ``try`` — #684 AC-3, Anti-Pattern #656). Belegt verschont sind
   ``send_trip_report`` und ``send_compare_report``: dort steht der
   ``append`` NACH dem riskanten Aufruf und wird bei einem Fehlschlag nie
   erreicht (Gegenprobe in AC-6).
3. **Klasse 2 — teilerfolg-blind** (``KIND_PARTIAL_SUCCESS_BLIND``): die
   Funktion iteriert über eine Sammlung (``for``-Anweisung ODER
   ``sum(<genexp>)``/Comprehension), der gezählte Zustand stammt aus einem
   undurchsichtigen Aufruf, und es gibt keinen Namen, der ausschließlich im
   Fehlerfall erhöht wird und in die Rückgabe fließt. Die Fehlerbehandlung
   muss dafür NICHT in der scannenden Funktion sichtbar sein —
   ``try/except`` im Schleifenrumpf ist ein Symptom, kein notwendiges
   Merkmal (``B11c`` zählt per ``sum(genexp)`` ganz ohne ``try/except``).
   **Der Rückgabetyp spielt ausdrücklich KEINE Rolle** (S-1, Spec
   Version 1.2): die Bedingung „bloßer Skalar" aus Version 1.1 ist
   ersatzlos gestrichen — sie widersprach der eigenen Attrappen-Gegenprobe
   AC-8, deren Attrappe syntaktisch ``(sent, failed)`` liefert und an einer
   UND-Verknüpfung mit „bloßer Skalar" schon vor der entscheidenden vierten
   Bedingung gescheitert wäre. **Datenfluss-Prüfung, keine Typprüfung:**
   eine Attrappe, die ``(sent, failed)`` liefert und ``failed`` nie erhöht,
   MUSS ein Fund sein (AC-8). **Verschont-Ausschlussliste** (E6): ein
   Aufruf auf ein Python-Builtin aus ``_PURE_COMPUTATION_BUILTINS`` oder
   auf ``math.*`` gilt NICHT als undurchsichtig — sonst rissen die ≥15
   Aggregationsfunktionen in ``weather_metrics.py`` mit (AC-8b).
4. **Klasse 3 — Heartbeat ohne Wirkung** (``KIND_HEARTBEAT_UNWIRED``): eine
   Funktion mit ``heartbeat``/``betterstack`` im Namen, deren Name außerhalb
   ihrer eigenen Definition in der Scanfläche kein einziges Mal als Aufruf
   auftaucht. Ein Überwachungsmechanismus, der nie feuert, ist kein Schutz,
   sondern die Abwesenheit von Schutz mit Beleg-Anschein (Hausregel
   „Heartbeat-Pflicht: Readiness statt Liveness").
5. **Klasse 4 — Aufruf ohne Rückmeldung IM VERSANDKONTEXT**
   (``KIND_UNACKNOWLEDGED_DISPATCH``): eine Funktion, deren Körper im
   Wesentlichen ein ``try/except`` ist, dessen Handler nur protokolliert,
   die dem Aufrufer kein Erfolgssignal zurückgibt (kein ``return`` mit
   Wert), UND die im eigenen Rumpf selbst einen Kanal-Ausgabeaufruf
   enthält (``EmailOutput``/``TelegramOutput``/``SMSOutput``, bzw. deren
   ``.send(...)``, oder ein übergebener Sink-Parameter). Der Aufrufer kann
   strukturell nicht wissen, ob es geklappt hat.

   **Die Versandkontext-Bedingung ist NEU in Spec-Version 1.2 (E2)** und
   notwendig: die uneingeschränkte Form („try/except, Logger-only-Handler,
   kein Rückgabewert") traf 18 statt 3 Stellen, davon 15 Persistenz-Helfer
   (``alert_state.save``/``reset``, ``weather_snapshot.save`` …). Ein
   ``save()``, das jeden Fehler schluckt, ist ein verwandtes, aber ANDERES
   Problem — dieses Ticket heißt „Erfolg heißt Wirkung" und zielt auf
   Erfolgs*meldungen* (AC-13b grenzt das ab).

   **Die Einschränkung ergab SECHS statt drei Treffer:** neben den drei
   bekannten Compare-Versandhelfern (``notification_service.py:878/891/929``,
   B14b) erfüllen ``_send_telegram_incomplete_hint`` (Z. 385),
   ``send_command_reply_email`` (Z. 1115) und ``_send_service_error_email``
   (Z. 1293) dieselbe Signatur strukturell ununterscheidbar — sie sind als
   **B21** in die Restliste aufgenommen statt durch eine Verengung zur
   Zahlenkosmetik wegdefiniert zu werden. **Nacktes ``return`` ist kein
   Erfolgssignal** (S-9): ``ast.Return(value=None)`` liefert ``None`` wie
   das Funktionsende auch — sonst verlöre Klasse 4 ein Drittel der
   B14b-Erwartung.

Anders als in Hälfte A sind Klasse 2 und Klasse 3 ausdrücklich KEIN
gemeinsamer Mechanismus: die eine prüft den Datenfluss INNERHALB einer
Funktion, die andere die Abwesenheit eines Aufrufers über die GANZE
Scanfläche (Spec „Geklärte Punkte" 1).

**Mehrfachtreffer auf derselben Codestelle (S-6):** kollidieren zwei
Detektoren auf derselben Datei+Zeile, gewinnt KEINER still — GREEN führt
beide Arten im Wert (``"heartbeat_unwired+unacknowledged_dispatch"``)
statt eine zu überschreiben. Das gilt auch über mehrere Detektor-DURCHLÄUFE
hinweg (dateiweise Detektoren PLUS Klasse-3-Lauf), nicht nur innerhalb
eines Detektors. Ein Fund, der beim Zusammenführen verschwindet, wäre genau
der Fehler, gegen den dieser Wächter gebaut ist.

Ausnahmen sind eine geprüfte Datenstruktur, kein Kommentar:
``INTENTIONAL_CONSTANT_SUCCESS`` trägt je Eintrag eine fachliche Begründung;
ein Eintrag ohne Begründung macht rot (AC-14). Eine Kommentar-Konvention
(``# status-ok-intentional: <Grund>``) wurde bereits in Hälfte A verworfen —
ein Kommentar erreicht den Betrieb nicht, ein geprüfter Listen-Eintrag schon.

Bauform + Ratsche 1:1 nach ``tests/test_resolution_loss_guard.py`` (Hälfte A,
#1405): Scanfläche als Glob, ``ast.parse`` je Datei, Verstöße als
``{"pfad::funktion::ordinal": "art"}`` (Issue #1466 AP2 — vorher
``{"pfad:zeile": "art::funktion"}``, was bei jeder eingefügten Zeile wanderte
und zuletzt 13 unveränderte Stellen gleichzeitig als "behoben" und als "neuer
Verstoß" führte), zwei gekoppelte Ratschen-Tests (neuer Fund → rot; erledigter
Eintrag noch gelistet → rot), synthetische Wirkungsnachweise je Bugmuster UND
je Ausnahmeklasse.

Bekannte Grenzen (Scope, keine Ausnahme):
- **Vollständigkeit einer Werteprüfung ist nicht entscheidbar:** ob eine
  Funktion ALLE möglichen Rückgabewerte eines Aufrufs kennt (``"sent"`` /
  ``"no_stage"`` / ``"no_weather"`` UND ``"no_channels"``), steht im Rumpf
  der *aufgerufenen* Funktion — außerhalb der Ein-Funktions-Grenze. Klasse 1
  bewertet deshalb ausdrücklich NICHT die Vollständigkeit der Prüfung,
  sondern nur, ob der Erfolgsstatus überhaupt vom Aufrufergebnis abhängt.
- **Struktur, nicht Fachlichkeit:** der Wächter erzwingt, dass ein Status aus
  einem Zähler/einer Aufrufer-Prüfung ABGELEITET wird — nicht, dass die
  Ableitung fachlich richtig ist. ``failed > 5`` statt ``failed > 0`` bleibt
  unsichtbar.
- **Go-Code bleibt ungeprüft:** ``internal/`` ist für einen Python-``ast``-
  Scan strukturell unerreichbar — bewusste, dokumentierte Lücke (AC-15). Die
  Heartbeat-Aufrufe in ``internal/notify/mq.go`` und
  ``internal/config/config.go`` bleiben außen vor.
- **Heartbeat-Erkennung ist eine Aufrufer-Suche, keine Ausführungsanalyse:**
  ob der gefundene Aufruf zur Laufzeit erreicht wird oder hinter der
  RICHTIGEN Bedingung steht, prüft dieser Wächter nicht.
- **Die Attrappen-Gegenprobe deckt nur die naheliegendste Umgehung ab:** ein
  ``failed``, das zwar erhöht, aber nie gelesen wird, ist mit dieser
  Datenfluss-Prüfung ggf. nicht erkennbar.
- **Klasse 4 prüft nur die scannende Funktion selbst:** eine Funktion, die
  zwar ``return`` mit Wert liefert, dessen Wert der Aufrufer aber ignoriert,
  bleibt unsichtbar — das ist wieder eine Mehrfunktions-Frage. Genau deshalb
  sind B14b und B21 strukturell NICHT voneinander zu unterscheiden: die
  Versandkontext-Bedingung grenzt gegen Persistenz ab, nicht gegen weitere
  Versand-Fundstellen. Es kann jederzeit mehr als sechs geben, sobald neuer
  Code entsteht — AC-2 fängt das ab.
- **Klasse-1-Signatur ist rein syntaktisch, nicht risikobewusst:** Bedingung
  (a) unterscheidet nicht zwischen einem riskanten Aufruf (Versand,
  Netzwerkanfrage) und einem trivialen, deterministischen
  (``date.today()``). ``_show_status``/``_show_now`` (B18) matchen über
  ``date.today()``, obwohl der nie fehlschlagen kann — die Restliste nimmt
  sie trotzdem auf (Arbeitsvorrat, keine Vorab-Filterung). Das ist eine
  benannte Grenze der Signatur, kein Bug am Scanner (Spec „Offene Punkte" 3).
- **Keine Mehrfunktions-Datenflüsse:** ein Erfolgswert, der erst in einer
  aufrufenden Funktion verfälscht wird, ist mit einer Ein-Funktion-
  Strukturprüfung nicht erkennbar (wie in Hälfte A).

Regel-Budget (CLAUDE.md): neuer Pflicht-Test ohne Ersatz einer bestehenden
Regel → **Prüfdatum 2026-10-26** (+90 Tage, identisch mit Hälfte A, weil
beide Teile desselben Tickets #1405 sind). Kein nachweisbarer Fang bis dahin
→ Rückbau erwägen.

Spec: ``docs/specs/modules/waechter_1405_erfolg_wirkung.md`` (Version 1.2,
PO-freigegeben 2026-07-28, Änderungsbudget 2800).
"""
from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Scanfläche: der komplette Router-Baum (jede Erfolgsmeldung, die nach außen
# geht) + der komplette Service-Baum (inkl. official_alerts/). Deckt alle 19
# bekannten Fundstellen ab — auch B15–B17 liegen in `src/services/`, die
# Scanfläche musste dafür nicht erweitert werden. NICHT gescannt: `tests/`
# (kein Produktionspfad, und ein Unit-Test eines Heartbeats ist kein Beleg
# dafür, dass er im Betrieb gerufen wird — genau das ist B13) und `internal/`
# (Go — für einen Python-AST-Scan strukturell unerreichbar, s. AC-15).
_ROUTERS_DIR = REPO_ROOT / "api" / "routers"
_SERVICES_DIR = REPO_ROOT / "src" / "services"

# Art-Kennung. INTERN (in den einzelnen Detektoren) hat der Wert weiter die
# Form "<art>::<funktionsname>"; nach außen steht der Funktionsname seit
# Issue #1466 AP2 im SCHLÜSSEL ("pfad::funktion::ordinal", s.
# _number_findings) und im Wert nur noch die Art.
KIND_CONSTANT_SUCCESS = "constant_success"
KIND_PRE_TRY_SUCCESS_MARKER = "pre_try_success_marker"
KIND_PARTIAL_SUCCESS_BLIND = "partial_success_blind"
KIND_HEARTBEAT_UNWIRED = "heartbeat_unwired"
KIND_UNACKNOWLEDGED_DISPATCH = "unacknowledged_dispatch"

# --- Klasse 1: welche Dict-Schlüssel behaupten überhaupt einen Erfolg -------
# Bewusst eine feste Liste (Spec „Implementation Details", Klasse 1) statt
# einer „enthält ok"-Heuristik: `{"status": "skipped"}` ist keine
# Erfolgsbehauptung, `{"count": 0}` erst recht nicht.
_SUCCESS_KEYS = {"status", "sent", "success", "ok"}

# Literalwerte, die eine Erfolgsbehauptung darstellen. `"skipped"`/`"error"`/
# `"duplicate"` stehen bewusst NICHT hier: ein Endpunkt, der ehrlich
# „übersprungen" meldet, behauptet keinen Erfolg (so liegen
# `scheduler.py:107` und `:122` im Bestand).
_SUCCESS_LITERALS: set[object] = {"ok", "sent", "success", "processed", True}

# --- Klasse 3: woran ein Heartbeat als solcher erkennbar ist ----------------
_HEARTBEAT_NAME_MARKERS = ("heartbeat", "betterstack")

# Empfänger-Namen, die einen ``logger.*``-Aufruf ausmachen. Übernommen aus
# Hälfte A: bewusst eine feste Liste statt einer „enthält log"-Heuristik —
# ``catalog.get(...)`` enthält ebenfalls „log". Für Klasse 2 ist das der
# Nachweis, dass ein ``except``-Zweig NUR protokolliert, statt zu zählen; für
# Klasse 4 der Nachweis, dass der Handler NUR protokolliert, statt dem
# Aufrufer etwas zurückzugeben.
_LOGGER_RECEIVERS = {"logger", "_logger", "LOGGER", "log", "_log", "logging"}

# --- Klasse 2: was NICHT als „undurchsichtiger Aufruf" zählt (E6) ----------
# Verschont-Ausschlussliste aus Spec Version 1.2. Ein Aufruf auf eines dieser
# Builtins oder auf `math.*` ist reine Rechnung: was er im Fehlerfall tut, ist
# an der Aufrufstelle vollständig sichtbar (nämlich nichts — er hat keinen
# Fehlerfall). Ohne diese Liste würden mindestens 15 gleich gebaute
# Aggregationsfunktionen in `weather_metrics.py` als Klasse-2-Fund gemeldet
# (`_compute_wind_direction` z. B. zählt per
# `sum(math.sin(math.radians(d)) for d in dirs)`) — der Wächter wäre nie grün
# zu bekommen. Eine reine „Bindung an self."-Heuristik wurde geprüft und
# VERWORFEN: sie hätte zwei echte Treffer verloren
# (`notification_service.send_multi_location_deviation_alert(...)` und
# `radar_svc.get_nowcast(...)` sind Aufrufe auf FREMDE Objekte, nicht auf
# self) — Spec „Geklärte Punkte" 13.
_PURE_COMPUTATION_BUILTINS = {
    "len", "sum", "max", "min", "round", "abs", "getattr", "hasattr",
    "isinstance",
}
_PURE_COMPUTATION_MODULES = {"math"}

# --- Klasse 4: woran ein Versandkontext erkennbar ist (E2) -----------------
# Zusatzbedingung aus Spec Version 1.2: die Funktion muss im EIGENEN Rumpf
# einen Kanal-Ausgabeaufruf enthalten. Ohne sie traf Klasse 4 18 statt 6
# Stellen, davon 15 Persistenz-Helfer — ein `save()`, das jeden Fehler
# schluckt, ist ein verwandtes, aber anderes Problem (AC-13b).
_CHANNEL_OUTPUT_CLASSES = {"EmailOutput", "TelegramOutput", "SMSOutput"}

# Übergebene Sink-Parameter (`mail_sink(...)`, `telegram_sink(...)`,
# `sms_sink(...)`) sind die zweite zugelassene Form eines Ausgabeaufrufs.
# Bewusst ein Namens-SUFFIX statt einer festen Namensliste: die Sinks werden
# an mehreren Stellen unterschiedlich benannt, die Endung ist das stabile
# Merkmal.
_SINK_PARAMETER_SUFFIX = "_sink"

_MODULE_SCOPE = "<module>"

# Der einzige bekannte Ausnahme-Eintrag, wörtlich aus der Spec („Ausnahmeliste
# — Begründung als Datenstruktur"). Als Konstanten hier oben, damit AC-14
# gegen denselben Wortlaut prüft, den GREEN einträgt, statt gegen eine
# Abschrift.
_WEBHOOK_ACK_LOCATION = "api/routers/webhook.py::telegram_webhook::0"
_WEBHOOK_ACK_JUSTIFICATION = (
    "Protokoll-Empfangsbestätigung an Telegram, kein fachlicher Erfolgsstatus "
    "— verhindert Retry-Sturm (dokumentiert im Docstring, Z. 54f.)"
)


# ---------------------------------------------------------------------------
# Scanfläche
# ---------------------------------------------------------------------------


def _scan_files() -> list[Path]:
    """Alle zu scannenden Python-Dateien: ``api/routers/**`` + ``src/services/**``.

    GREEN muss liefern — eine sortierte, duplikatfreie Liste aller ``*.py``
    unter beiden Bäumen (rekursiv, inkl. ``src/services/official_alerts/``),
    OHNE ``tests/`` und OHNE ``internal/`` (Go). Die Liste ist zugleich

    * die Eingabe von ``_all_violations()``,
    * die Grundgesamtheit der Aufrufer-Suche für Klasse 3 (ein Heartbeat,
      der nur in ``tests/`` aufgerufen wird, gilt als unverdrahtet — genau so
      liegt B13 im Bestand) und
    * der Prüfgegenstand von ``test_scan_scope_excludes_go_internal_tree()``.
    """
    return sorted({*_ROUTERS_DIR.rglob("*.py"), *_SERVICES_DIR.rglob("*.py")})


# ---------------------------------------------------------------------------
# Strukturelle Bausteine des Scanners
# ---------------------------------------------------------------------------


def _walk_local(*nodes: ast.AST):
    """Wie ``ast.walk``, steigt aber NICHT in verschachtelte Funktionen ab.

    Übernommen aus Hälfte A (``tests/test_resolution_loss_guard.py``), weil
    hier dieselbe Grenze gilt: Klasse 1, 1c, 2 und 4 sind
    Ein-Funktion-Prüfungen. Ein ``sent_channels.append()`` in einer inneren
    Hilfsfunktion gehört zu DEREN Funktionsraum — sonst würden Erfolgsmarker
    und Zähler über Funktionsgrenzen hinweg vermischt und der
    Datenfluss-Nachweis wäre wertlos.

    Die Grenze gilt auch für die ÜBERGEBENEN Knoten selbst: eine Funktion, die
    direkt im Modul- oder Klassenrumpf steht, ist ihr eigener Raum und wird
    von ``_scopes()`` gesondert besucht.
    """
    boundaries = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    stack = [node for node in nodes if not isinstance(node, boundaries)]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, boundaries):
                continue
            stack.append(child)


def _scopes(tree: ast.Module):
    """Modulraum + jeder Funktionsraum (auch verschachtelte) mit seinem Namen."""
    yield tree, _MODULE_SCOPE
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node, node.name


def _is_logger_call(node: ast.AST) -> bool:
    """``logger.error(...)`` & Verwandte — übernommen aus Hälfte A.

    Für Klasse 2 ist das die Kernunterscheidung: ein ``except``-Zweig, der NUR
    protokolliert, isoliert den Fehler zwar, zählt ihn aber nicht. Für
    Klasse 4 dieselbe Unterscheidung eine Ebene höher: ein Handler, der nur
    protokolliert, verwandelt den Fehlschlag in gar nichts — der Aufrufer
    bekommt weder Ausnahme noch Rückgabewert.
    """
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    receiver = node.func.value
    if isinstance(receiver, ast.Name):
        return receiver.id in _LOGGER_RECEIVERS
    if isinstance(receiver, ast.Attribute):
        return receiver.attr in _LOGGER_RECEIVERS
    return False


def _relative_path(path: Path) -> str:
    """``pfad relativ zum Repo`` als POSIX-String, sonst der absolute Pfad.

    ``relative_to`` scheitert für Pfade außerhalb des Repos — die
    Wirkungsnachweise scannen synthetische Dateien in ``tmp_path``. Dann
    bleibt der absolute Pfad stehen; das Format ist nur für
    Menschenlesbarkeit relevant, die Tests prüfen auf das ``::funktion``-Ende.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _parse(path: Path) -> ast.Module:
    """Eine Scandatei als Syntaxbaum. Einziger Datei-Zugriff des Wächters."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _statement_blocks(scope: ast.AST):
    """Jede Anweisungs-LISTE des Funktions-/Modulraums, ohne fremde Funktionen.

    Klasse 1c fragt nicht „steht irgendwo ein ``append``", sondern „steht eins
    als GESCHWISTER vor einem ``try``" — dafür braucht es die Blöcke selbst.
    """
    yield list(scope.body)
    for node in _walk_local(*scope.body):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                yield list(block)
        for handler in getattr(node, "handlers", []) or []:
            yield list(handler.body)


def _merge_findings(target: dict[str, str], addition: dict[str, str]) -> dict[str, str]:
    """Zwei Fundmengen vereinen, OHNE dass ein Fund still verschwindet (S-6).

    Ein ``dict.update()`` würde bei gleicher ``pfad:zeile`` die vorhandene Art
    überschreiben — ein Fund, der beim Zusammenführen verschwindet, wäre genau
    der Fehler, gegen den dieser Wächter gebaut ist. Stattdessen werden die
    Arten zu ``"art_a+art_b::funktion"`` verschmolzen (sortiert, damit die
    Läufe-Reihenfolge den Wert nicht ändert); der Funktionsname bleibt der
    zuerst gemeldete — beide stehen im selben Funktionsraum.
    """
    for location, kind in addition.items():
        previous = target.get(location)
        if previous is None:
            target[location] = kind
            continue
        previous_kinds, _, previous_name = previous.partition("::")
        new_kinds, _, new_name = kind.partition("::")
        kinds = sorted(set(previous_kinds.split("+")) | set(new_kinds.split("+")))
        target[location] = f"{'+'.join(kinds)}::{previous_name or new_name}"
    return target


def _is_pure_computation_call(node: ast.Call) -> bool:
    """Reine Rechnung statt undurchsichtigem Aufruf — die Ausschlussliste (E6).

    ``sum(...)``/``max(...)``/``math.radians(...)`` haben keinen Fehlerfall,
    den ein Gegenzähler zählen könnte. Ohne sie meldete Klasse 2 allein in
    ``weather_metrics.py`` ≥15 Aggregationsfunktionen (AC-8b).
    """
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in _PURE_COMPUTATION_BUILTINS
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id in _PURE_COMPUTATION_MODULES
    return False


def _is_opaque_call(node: ast.AST) -> bool:
    """„Was tut dieser Aufruf im Fehlerfall?" — hier nicht sichtbar.

    Ein undurchsichtiger Aufruf ist ein Methoden-/Funktionsaufruf MIT
    Argumenten (``self.check_and_send_alerts(trip, cached)``), der weder eine
    reine Rechnung (``_is_pure_computation_call``) noch eine bloße Protokoll-
    zeile (``_is_logger_call``) ist. Ein Feldzugriff oder Vergleich zählt
    nicht — dort ist nichts verborgen. Der Argument-Zwang trennt den Abruf vom
    Aufräumen: ``imap.logout()`` liefert keinen gezählten Zustand.
    """
    if not isinstance(node, ast.Call):
        return False
    if not node.args and not node.keywords:
        return False
    if _is_logger_call(node) or _is_pure_computation_call(node):
        return False
    return isinstance(node.func, (ast.Name, ast.Attribute))


def _contains_opaque_call(*nodes: ast.AST) -> bool:
    """Steckt in einem der Ausdrücke ein undurchsichtiger Aufruf?

    Bewusst ``ast.walk`` statt ``_walk_local``: ``sum(math.sin(math.radians(d))
    for d in dirs)`` muss BIS INS INNERSTE geprüft werden, sonst gelten die
    verschachtelten ``math.*``-Aufrufe als undurchsichtig (AC-8b).
    """
    for node in nodes:
        for inner in ast.walk(node):
            if _is_opaque_call(inner):
                return True
    return False


def _returned_names(scope: ast.AST) -> set[str]:
    """Alle Namen, die in irgendeinem ``return`` dieses Raums vorkommen.

    Trägt beide Hälften der Klasse-2-Datenflussprüfung: der Erfolgszähler muss
    nach oben gemeldet werden, und ein echter Gegenzähler muss „ebenfalls in
    die Rückgabe fließen" (Spec, Klasse 2, dritte Bedingung).
    """
    names: set[str] = set()
    for node in _walk_local(*scope.body):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        for inner in ast.walk(node.value):
            if isinstance(inner, ast.Name):
                names.add(inner.id)
    return names


def _incremented_names(*nodes: ast.AST) -> set[str]:
    """Namen, die in ``nodes`` hochgezählt werden (``n += 1``/``n = n + 1``).

    Ein ``AugAssign`` auf ein ATTRIBUT (``self._sent += 1``, so in
    ``dispatch_orchestrator``) zählt bewusst nicht mit: das ist Objektzustand
    über mehrere Methoden hinweg und einfunktional nicht entscheidbar.
    """
    names: set[str] = set()
    for node in nodes:
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.AugAssign)
                and isinstance(inner.op, ast.Add)
                and isinstance(inner.target, ast.Name)
            ):
                names.add(inner.target.id)
            elif (
                isinstance(inner, ast.Assign)
                and len(inner.targets) == 1
                and isinstance(inner.targets[0], ast.Name)
                and isinstance(inner.value, ast.BinOp)
                and isinstance(inner.value.op, ast.Add)
                and isinstance(inner.value.left, ast.Name)
                and inner.value.left.id == inner.targets[0].id
            ):
                names.add(inner.targets[0].id)
    return names


def _integer_counter_names(scope: ast.AST) -> set[str]:
    """Namen, die als GANZZAHL-Zähler angelegt werden (``sent = 0``).

    Die Trennlinie zwischen Zählen und Aufsummieren, und sie ist nötig:
    ``total_hours = 0.0`` (``weather_metrics.calculate_sunny_hours``) und
    ``total_dist = 0.0`` (``trip_report_scheduler._compute_stage_stats``)
    wachsen ebenfalls in einer Schleife über einen Aufruf
    (``dni_to_sunny_fraction(...)``, ``haversine_km(...)``), zählen aber keine
    Vorgänge, sondern summieren gemessene Größen — ein Gegenzähler ergibt dort
    keinen Sinn, es gibt gar keinen Vorgang, der fehlschlagen könnte. Die
    Builtin-/``math.*``-Liste (E6) trägt das nicht: beide Aufrufe gehen auf
    eigene Klassen. Die Bedingung kostet keinen belegten Treffer — B9–B11c,
    B17, B19, B20 legen ihren Zähler mit ``= 0`` an; ``0.0`` zählt NICHT.
    """
    names: set[str] = set()
    for node in _walk_local(*scope.body):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if not isinstance(node.value, ast.Constant):
            continue
        if type(node.value.value) is not int:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _failure_counter_names(scope: ast.AST) -> set[str]:
    """Namen, die in einem ``except``-Zweig hochgezählt werden.

    Der strukturelle Nachweis eines ECHTEN Gegenzählers: ein Name, der im
    Fehlerfall wächst. Zusammen mit ``_returned_names()`` ergibt das die
    Hausnorm aus ``dispatch_orchestrator.py:65-77`` — ``failed += 1`` im
    ``except``, ``failed`` im ``return``. Die Attrappe aus AC-8 hat genau das
    nicht: ``failed = 0``, ins Tupel geschrieben, nie erhöht. Am Rückgabetyp
    ist sie von der Hausnorm nicht zu unterscheiden — an dieser Menge schon.
    """
    names: set[str] = set()
    for node in _walk_local(*scope.body):
        for handler in getattr(node, "handlers", []) or []:
            names |= _incremented_names(*handler.body)
    return names


# ---------------------------------------------------------------------------
# Die fünf Detektoren
# ---------------------------------------------------------------------------


def _find_constant_success_violations(path: Path) -> dict[str, str]:
    """Klasse 1 in EINER Datei als ``{"pfad:zeile": "constant_success::funktion"}``.

    GREEN muss liefern — je Funktionsraum der Datei:

    * **Aufruf-Bezug feststellen** (Bedingung a): die Funktion leitet VOR dem
      ``return`` eine Variable aus einem Aufruf ab (``V = <Call>(...)``, auch
      als Tupel-Ziel wie ``top_ort, actual_empfaenger = ...``) ODER tätigt
      einen Aufruf, dessen Rückgabewert gar keiner Variablen zugewiesen wird
      (nackte ``ast.Expr``-Anweisung — B12, B15, ``webhook.py:72``). Ohne
      jeden solchen Aufruf ist ein konstantes ``ok`` per Definition wahr —
      das ist die Lebendmeldung ``api/routers/health.py:9``, die deshalb OHNE
      Ausnahmeliste durchfällt (AC-16).
    * **Dekoratoren zählen NICHT als Aufruf im Rumpf** (S-7, Spec
      Version 1.2): ein ``ast.Call`` im ``decorator_list``
      (``@router.get("/health")``) wird im UMSCHLIESSENDEN Geltungsbereich
      ausgewertet, nicht im Funktionsraum der dekorierten Funktion, und ist
      syntaktisch kein Aufruf INNERHALB des Körpers. Der Scanner darf für
      Bedingung (a) ausschließlich ``node.body`` (plus dessen
      nicht-Funktions-Kinder) durchsuchen — NIE ``node.decorator_list``,
      ``node.args`` oder ``node.returns``. Ein naiver ``ast.walk()`` über den
      ganzen ``FunctionDef``-Knoten macht ``health()`` zum Klasse-1-Fund und
      AC-16 damit strukturell unerfüllbar.
    * **Behauptung feststellen** (Bedingung b): die Funktion liefert danach
      ein ``return`` mit einem Dict ODER einem Response-/Ergebnisobjekt,
      dessen Erfolgs-Schlüssel aus ``_SUCCESS_KEYS`` ein hartkodiertes
      Literal aus ``_SUCCESS_LITERALS`` trägt — einen Ausdruck also, der die
      abgeleitete Variable NICHT referenziert. **Schlüsselwortargumente eines
      Konstruktor-/Funktionsaufrufs zählen dabei wie Dict-Schlüssel** (S-8,
      Spec Version 1.2): ``CommandResult(success=True, ...)`` und
      ``NotificationResult(sent=True, ...)`` sind dieselbe Behauptung wie
      ``{"success": True}``. Ohne diese Gleichstellung wären B12, B15, B16
      und das GESAMTE B18-Muster in ``trip_command_processor.py`` (das
      ausschließlich über ``CommandResult(success=True, ...)`` läuft)
      unerreichbar — 13 der 45 erwarteten Treffer.
      Maßgeblich ist allein der Erfolgs-Schlüssel: dass ANDERE Schlüssel
      desselben Dicts die Variable sehr wohl benutzen (``{"status": "ok",
      "winner": top_ort, ...}`` — B12), rettet nichts. Ein Erfolgs-Schlüssel,
      dessen Wert selbst aus einer Variablen stammt (``{"status": status}``,
      ``scheduler.py:44``), ist per Definition abgeleitet → kein Fund.
    * **Ausschluss „except divergiert":** enthält ein ``except``-Handler der
      Funktion selbst ein ``return`` mit einem ANDEREN Wert, ist der Status
      doch an den Ausgang gekoppelt → kein Fund. Belegt korrekt
      ausgeschlossen: ``channel_test_service.py:42`` (Handler liefert
      ``{"error": ...}``), ``forecast_budget.py:102`` und
      ``official_alerts/meteoalarm_budget.py:143`` (Handler liefert
      ``"status": "unavailable"``) — AC-5.

    Ausdrücklich NICHT geprüft wird, ob eine vorhandene Werteprüfung
    VOLLSTÄNDIG ist (ob also alle möglichen Ausgänge des Aufrufs abgefangen
    sind). Das stünde im Rumpf der aufgerufenen Funktion und liegt jenseits
    der Ein-Funktions-Grenze — genau daran ist die Klasse-1-Fassung aus
    Spec-Version 1.0 gescheitert (s. Modul-Docstring, „Bekannte Grenzen").
    B1 bleibt trotzdem ein Fund, weil ``send_test_report_outcome()``
    aufgerufen wird, sein Ergebnis für ``"sent": True`` aber gar keine Rolle
    spielt.

    **Fundzeile ist die Zeile der jeweiligen ``return``-Anweisung, nicht die
    der ``def``-Anweisung.** Das ist nicht Kosmetik, sondern trägt die
    AC-1-Erwartung: ``_handle_query`` (B18) hat VIER unabhängige
    ``return CommandResult(success=True, ...)``-Zweige (Z. 470/479/487/496)
    und muss vier Treffer liefern. Ein Detektor, der die ``def``-Zeile als
    Schlüssel nimmt, ließe alle vier auf EINEN Dict-Eintrag zusammenfallen —
    AC-1/AC-17 wären damit strukturell unerfüllbar (dieselbe Falle wie bei
    Klasse 1c, wo drei Kanal-``append``-Stellen drei Treffer bleiben müssen).

    Schlüssel ist ``"<pfad relativ zum Repo>:<zeile>"``, Wert
    ``f"{KIND_CONSTANT_SUCCESS}::{name der umschließenden Funktion}"``.
    """
    tree = _parse(path)
    rel = _relative_path(path)
    found: dict[str, str] = {}

    for scope, scope_name in _scopes(tree):
        first_call_line = _first_meaningful_call_line(scope)
        if first_call_line is None:
            continue  # Bedingung (a) fehlt — die Lebendmeldung (AC-16).
        diverging = _except_return_values(scope)
        for node in _walk_local(*scope.body):
            if not isinstance(node, ast.Return) or node.value is None:
                continue
            if node.lineno <= first_call_line:
                continue  # „danach": ein return VOR jedem Aufruf behauptet nichts.
            if not _asserts_constant_success(node.value):
                continue
            if _handler_returns_other_value(diverging, node.value):
                continue  # Ausschluss „except divergiert" (AC-5).
            found[f"{rel}:{node.lineno}"] = f"{KIND_CONSTANT_SUCCESS}::{scope_name}"
    return found


def _first_meaningful_call_line(scope: ast.AST) -> int | None:
    """Zeile des ersten Aufrufs IM FUNKTIONSRUMPF — Bedingung (a) der Klasse 1.

    Zwei Formen zählen (Spec, Klasse 1):

    * eine Zuweisung, deren Wert einen Aufruf enthält (``outcome =
      service.send_test_report_outcome(...)``, auch als Tupel-Ziel wie
      ``top_ort, actual_empfaenger = ...``);
    * eine nackte ``ast.Expr``-Anweisung, die ein Aufruf ist
      (``service.send_test_report(trip, report_type)`` — B15, ``webhook.py:72``).

    **Ausgeschlossen sind ``logger.*``-Aufrufe:** eine Protokollzeile holt
    keinen Wert, dessen Ausgang der Status verschweigen könnte — sonst wäre
    der Wächter am Nebengeräusch gebaut.

    **Ausgeschlossen ist alles außerhalb von ``node.body``** (S-7): Dekoratoren
    (``@router.get("/health")``), Parameter-Vorbelegungen (``limit=int("10")``)
    und Rückgabe-Annotationen werden im UMSCHLIESSENDEN Raum ausgewertet.
    ``_walk_local(*scope.body)`` startet deshalb bei den Anweisungen des
    Rumpfes statt beim ``FunctionDef``-Knoten — ein ``ast.walk()`` über den
    ganzen Knoten machte ``health()`` zum Fund und AC-16 unerfüllbar. Zurück
    kommt die KLEINSTE Zeilennummer, damit die Reihenfolge-Prüfung nicht von
    der Knoten-Reihenfolge in ``_walk_local`` abhängt.
    """
    lines: list[int] = []
    for node in _walk_local(*scope.body):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            if any(
                isinstance(inner, ast.Call) and not _is_logger_call(inner)
                for inner in ast.walk(node.value)
            ):
                lines.append(node.lineno)
        elif (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and not _is_logger_call(node.value)
        ):
            lines.append(node.lineno)
    return min(lines) if lines else None


def _asserts_constant_success(value: ast.AST) -> bool:
    """Bedingung (b): ein Erfolgs-Schlüssel trägt ein hartkodiertes Literal.

    Zwei gleichwertige Schreibweisen (S-8):

    * ``{"status": "ok", ...}`` — Dict-Literal mit einem Schlüssel aus
      ``_SUCCESS_KEYS`` und einem Wert aus ``_SUCCESS_LITERALS``;
    * ``CommandResult(success=True, ...)`` — Schlüsselwortargument eines
      Konstruktor-/Funktionsaufrufs. Ohne diese Gleichstellung wären B12, B15,
      B16 und das ganze B18-Muster unerreichbar (13 der 45 Treffer).

    Maßgeblich ist ALLEIN der Erfolgs-Schlüssel: dass ANDERE Schlüssel die
    abgeleitete Variable benutzen (``{"status": "ok", "winner": top_ort}`` —
    B12) rettet nichts; umgekehrt ist ``{"status": status}`` abgeleitet und
    kein Fund (so die Vorbild-Endpunkte ``scheduler.py:44``/``:144``).
    """
    if isinstance(value, ast.Dict):
        for key, item in zip(value.keys, value.values):
            if (
                isinstance(key, ast.Constant)
                and key.value in _SUCCESS_KEYS
                and isinstance(item, ast.Constant)
                and item.value in _SUCCESS_LITERALS
            ):
                return True
    if isinstance(value, ast.Call):
        for keyword in value.keywords:
            if (
                keyword.arg in _SUCCESS_KEYS
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value in _SUCCESS_LITERALS
            ):
                return True
    return False


def _except_return_values(scope: ast.AST) -> list[ast.AST]:
    """Rückgabewerte, die in einem ``except``-Zweig dieses Raums stehen."""
    values: list[ast.AST] = []
    for node in _walk_local(*scope.body):
        for handler in getattr(node, "handlers", []) or []:
            for inner in _walk_local(*handler.body):
                if isinstance(inner, ast.Return) and inner.value is not None:
                    values.append(inner.value)
    return values


def _handler_returns_other_value(
    handler_values: list[ast.AST], returned: ast.AST
) -> bool:
    """Ausschluss „except divergiert" (AC-5): der Fehlerzweig meldet anders.

    Geprüft wird die ABWEICHUNG, nicht die bloße Anwesenheit eines ``return``:
    ``ForecastBudgetGate.snapshot`` liefert in beiden Zweigen denselben
    Schlüssel (``"status"``) mit unterschiedlichem Literal (``"ok"`` /
    ``"unavailable"``) — der Status hängt dort sehr wohl am Ausgang. Ein
    Detektor, der nur „Handler enthält irgendein return" prüft, könnte das
    nicht von einem Handler unterscheiden, der denselben Erfolgswert noch
    einmal behauptet. Verglichen wird über ``ast.dump`` OHNE Positionsangaben
    — zwei gleich geschriebene Dicts sind derselbe Wert.
    """
    target = ast.dump(returned, include_attributes=False)
    return any(
        ast.dump(value, include_attributes=False) != target for value in handler_values
    )


def _find_pre_try_success_marker_violations(path: Path) -> dict[str, str]:
    """Klasse 1c in EINER Datei als ``{"pfad:zeile": "pre_try_success_marker::funktion"}``.

    GREEN muss liefern — je Funktionsraum der Datei:

    * **Erfolgsmarker vor der Tat feststellen:** ein ``.append()``-Aufruf auf
      eine Sammlung steht als Geschwister-Anweisung VOR einem ``Try``-Knoten
      im selben Block (nicht darin), und der ``except``-Zweig nimmt den
      Eintrag nicht zurück (kein ``remove``/``pop``/``discard`` auf dieselbe
      Sammlung). Der Erfolg ist damit gebucht, bevor er stattgefunden hat.
    * **Jedes Kanal-Vorkommen ist ein eigener Treffer** mit eigener
      Zeilennummer: die Erwartung „3" in ``SPEC_LISTED_FINDINGS`` für
      ``send_official_alert`` (Z. 660/672/694) und ``_dispatch_alert_message``
      (Z. 1066/1082/1103) hängt daran. Zeigt sich in GREEN, dass strukturell
      nur 1 Treffer je Funktion erkennbar ist, wird die SPEC korrigiert
      (Spec „Offene Punkte" 2), NICHT der Test heimlich gelockert.
    * **Belegt verschont:** ``send_trip_report`` (Z. 308f.) und
      ``send_compare_report`` (Z. 765f.) — dort steht der ``append`` NACH dem
      riskanten Aufruf und wird bei einem Fehlschlag nie erreicht. Ebenso
      ``send_multi_location_official_alert`` (Z. 865/871/874): auch dort
      folgt der ``append`` erst auf den Helfer-Aufruf. Ein Detektor, der die
      Reihenfolge nicht auswertet, meldet alle drei mit und ist nie grün zu
      bekommen (Gegenprobe in AC-6).

    Eigener Detektor statt Unterfall von Klasse 1, weil die Signatur eine
    ANDERE ist: hier geht es nicht um einen Rückgabewert, sondern um die
    Reihenfolge zweier Anweisungen. Gemeinsames Themenfeld, eigenes
    Kind-Präfix (Spec „Geklärte Punkte" 5).
    """
    tree = _parse(path)
    rel = _relative_path(path)
    found: dict[str, str] = {}

    for scope, scope_name in _scopes(tree):
        for block in _statement_blocks(scope):
            for index, statement in enumerate(block):
                collection = _appended_collection(statement)
                if collection is None:
                    continue
                later_tries = [
                    node for node in block[index + 1 :] if isinstance(node, ast.Try)
                ]
                if not later_tries:
                    continue  # Der Marker steht NACH der Tat — er ist verdient.
                if not any(_try_risks_dispatch(node) for node in later_tries):
                    continue
                if any(_try_undoes_marker(node, collection) for node in later_tries):
                    continue  # Der Fehlerzweig nimmt den Eintrag zurück.
                found[f"{rel}:{statement.lineno}"] = (
                    f"{KIND_PRE_TRY_SUCCESS_MARKER}::{scope_name}"
                )
    return found


def _appended_collection(statement: ast.stmt) -> str | None:
    """Name der Sammlung, in die diese Anweisung einen Eintrag schreibt.

    Nur die nackte Anweisung ``sent_channels.append("email")`` zählt — ein
    ``append`` als Teil eines größeren Ausdrucks ist keine eigene Buchung,
    deren Reihenfolge man gegen ein ``try`` stellen könnte.
    """
    if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)):
        return None
    call = statement.value
    if not (isinstance(call.func, ast.Attribute) and call.func.attr == "append"):
        return None
    if not isinstance(call.func.value, ast.Name):
        return None
    return call.func.value.id


def _try_risks_dispatch(node: ast.Try) -> bool:
    """Ist das nachfolgende ``try`` überhaupt eine riskante Tat?

    Der Marker ist nur unverdient, wenn danach etwas passiert, das scheitern
    KANN und dessen Scheitern abgefangen wird: ein Handler, der protokolliert
    statt weiterzuwerfen, plus ein undurchsichtiger Aufruf im ``try``-Rumpf.
    Ein ``try``, das per ``raise`` weiterreicht, lässt den Marker nicht stehen.
    """
    if not node.handlers:
        return False
    for handler in node.handlers:
        if any(isinstance(inner, ast.Raise) for inner in _walk_local(*handler.body)):
            return False
    return _contains_opaque_call(*node.body)


def _try_undoes_marker(node: ast.Try, collection: str) -> bool:
    """Nimmt der Fehlerzweig den Eintrag zurück (``remove``/``pop``/``discard``)?

    Dann ist der Marker am Ende doch verdient — vorab gebucht, bei Fehlschlag
    storniert. Im Bestand kommt diese Form nicht vor; sie steht hier, damit
    die Reparatur (S4) auch diesen Weg gehen darf.
    """
    for handler in node.handlers:
        for inner in _walk_local(*handler.body):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr in {"remove", "pop", "discard"}
                and isinstance(inner.func.value, ast.Name)
                and inner.func.value.id == collection
            ):
                return True
    return False


def _find_partial_success_blind_violations(path: Path) -> dict[str, str]:
    """Klasse 2 in EINER Datei als ``{"pfad:zeile": "partial_success_blind::funktion"}``.

    GREEN muss liefern — je Funktionsraum der Datei, alle DREI Bedingungen
    zusammen (Version 1.1 hatte vier — die dritte ist gestrichen, s. u.):

    * **Iteration feststellen:** eine ``for``-Anweisung ODER ein
      ``sum(<genexp>)``/eine Comprehension. Die ``try/except``-Form im
      Schleifenrumpf ist ausdrücklich KEIN notwendiges Merkmal mehr — sie ist
      ein Symptom und trifft nur 2 von 5 belegten Stellen. ``B11c``
      (``compare_official_alert.py:72``) zählt per
      ``sum(1 for preset in presets if self._check_one_preset(...))`` ganz
      ohne ``try/except`` und MUSS trotzdem ein Fund sein.
    * **Undurchsichtigen Aufruf feststellen:** der gezählte Zustand stammt aus
      einem Methoden-/Funktionsaufruf mit Argumenten
      (``self.check_and_send_alerts(trip, cached)``), nicht aus einem
      einfachen Feldzugriff oder Vergleich. „Undurchsichtig" heißt: was der
      Aufruf im Fehlerfall tut, ist an dieser Stelle nicht sichtbar — die
      Fehlerbehandlung darf vollständig außerhalb der scannenden Funktion
      liegen. Genau das macht die Signatur überhaupt erreichbar.

      **Verschont-Ausschlussliste (E6, NEU Version 1.2):** ein Aufruf zählt
      NICHT als undurchsichtig, wenn sein Ziel ein Builtin aus
      ``_PURE_COMPUTATION_BUILTINS`` ist oder ein Attributzugriff auf ein
      Modul aus ``_PURE_COMPUTATION_MODULES`` (``math.sin``,
      ``math.radians``, …). Belegt notwendig: ALLE Zählschleifen und
      Comprehensions in ``weather_metrics.py`` (≥15 Aggregationsfunktionen)
      und ``aggregation.py::_circular_mean_deg`` rufen ausschließlich solche
      Ziele auf — ohne die Liste wäre der Wächter mit ≥15 Fehlalarmen nie
      grün zu bekommen (AC-8b). Belegt UNSCHÄDLICH: keiner der fünf echten
      Klasse-2-Treffer zählt über ein Builtin — sie zählen über
      ``self.check_and_send_alerts(...)``, ``self._check_one_preset(...)``,
      ``notification_service.send_multi_location_deviation_alert(...)`` und
      ``radar_svc.get_nowcast(...)``.
    * **Gegenzähler-Abwesenheit feststellen:** es gibt keinen Namen, der
      AUSSCHLIESSLICH im Fehlerfall erhöht wird (``except``-Handler oder
      Fehlausgangs-Zweig, vgl. ``dispatch_orchestrator.py:71-77``) UND
      ebenfalls in die Rückgabe fließt. Fehlt er → Fund.

    * **GESTRICHEN — „bloßer Skalar als Rückgabe" (S-1, Version 1.2):**
      Version 1.1 verlangte zusätzlich, dass die Funktion einen einzelnen
      Wert zurückgibt (kein Tupel/Objekt mit zwei Zählern). Diese Bedingung
      widersprach der eigenen Attrappen-Gegenprobe AC-8 DIREKT: die dortige
      Attrappe ``dispatch_all_presets`` gibt syntaktisch ``(sent, failed)``
      zurück und wäre an dieser Teilbedingung gescheitert, BEVOR die
      eigentlich entscheidende Gegenzähler-Prüfung überhaupt griffe — eine
      UND-Verknüpfung schlägt fehl, sobald eine Teilbedingung nicht zutrifft.
      **Der Rückgabetyp spielt ausdrücklich KEINE Rolle.** GREEN darf ihn
      nicht wieder einführen, auch nicht „als zusätzliches Indiz".
    * **Nicht am Rückgabetyp hängen (AC-8):** ``return sent, failed`` ist kein
      Freibrief. Maßgeblich ist allein, ob ``failed`` irgendwo im
      Fehlerzweig ERHÖHT wird. Eine Attrappe mit ``failed = 0`` und einem
      ``status = "partial" if failed > 0 else "ok"`` sieht der Hausnorm
      täuschend ähnlich und MUSS trotzdem ein Fund sein — sonst ist die ganze
      Klasse-2-Prüfung mit drei Zeilen Kosmetik auszuhebeln. Die
      Gegenzähler-Bedingung trägt diesen Fall allein und vollständig: das
      Tupel ist da, der Gegenzähler nicht.
    * **Gegenprobe Hausnorm (AC-9):** ``run_briefing_dispatch()``/
      ``TripDispatchStrategy.dispatch_one`` MÜSSEN strukturell durchfallen —
      ein Wächter, der die eigene Referenz-Implementierung anmeckert, ist nie
      grün zu bekommen. Ebenso die geprüft harmlosen Zählschleifen in
      ``comparison_scoring.py``, ``trip_segments.py``, ``warn_egress.py`` und
      ``massif_closure.py`` (dort zählt kein undurchsichtiger Aufruf,
      sondern ein Feldzugriff/Vergleich) sowie — NEU Version 1.2 — die
      Aggregationsfunktionen in ``weather_metrics.py`` und
      ``aggregation.py`` (dort greift die Verschont-Ausschlussliste).

    Trifft ``B9``–``B11``, ``B11b``, ``B11c``, ``B17`` sowie — NEU
    Version 1.2 (E4) — ``B19``/``B20``: ``inbound_email_reader.py:77`` und
    ``inbound_telegram_reader.py:107``. Beide waren in Version 1.1
    fälschlich als „kein Fund, bereits erfolgsbereinigt" geführt. Das
    Argument „``processed`` zählt nur tatsächlich Verarbeitetes" ist
    FACHLICH richtig, aber KEIN strukturelles Ausschlusskriterium — die
    Signatur fragt nicht „ist der Zähler fachlich korrekt", sondern „gibt es
    einen Gegenzähler für den Fehlerfall, der in dieselbe Rückgabe fließt".
    Beide haben keinen: der ``except``-Zweig im Schleifenrumpf ruft nur
    ``logger.error(...)`` (AC-18).

    Fundzeile ist die Zeile der Iteration (nicht die des ``return``), damit
    zwei blinde Schleifen derselben Funktion zwei Treffer bleiben.
    """
    tree = _parse(path)
    rel = _relative_path(path)
    found: dict[str, str] = {}

    for scope, scope_name in _scopes(tree):
        returned = _returned_names(scope)
        if _failure_counter_names(scope) & returned:
            continue  # Echter Gegenzähler vorhanden — die Hausnorm (AC-9).
        countable = _integer_counter_names(scope) & returned
        lines = _blind_counting_lines(scope, returned, countable)
        for lineno in lines:
            found[f"{rel}:{lineno}"] = f"{KIND_PARTIAL_SUCCESS_BLIND}::{scope_name}"
    return found


def _blind_counting_lines(
    scope: ast.AST, returned: set[str], countable: set[str]
) -> list[int]:
    """Zeilen teilerfolg-blinder Zählungen in EINEM Funktionsraum.

    Zwei Bauformen, weil der Bestand beide kennt (Spec, Klasse 2):

    1. **``for``-Schleife mit Ganzzahl-Zähler** — ``alerts_sent += 1`` im
       Rumpf, der Zähler fließt in die Rückgabe (``countable``), und im
       Schleifenrumpf steht ein undurchsichtiger Aufruf. So liegen B9, B10,
       B11, B11b, B17, B19 und B20 im Bestand. Ein ``try/except`` im Rumpf ist
       ausdrücklich KEIN Merkmal (es traf nur 2 von 5 Stellen).
    2. **``sum(<genexp>)``** — ``return sum(1 for preset in presets if
       self._check_one_preset(...))`` (B11c) zählt ohne Schleifenanweisung und
       ohne ``try/except``; der undurchsichtige Aufruf steht im Filter.

    Der Rückgabetyp spielt in BEIDEN Formen keine Rolle (S-1): die Attrappe
    aus AC-8 liefert ein ``(sent, failed)``-Tupel und bleibt Fund, weil
    ``failed`` nirgends im Fehlerfall wächst. Fundzeile ist die Zeile der
    Iteration, damit zwei blinde Schleifen zwei Treffer bleiben.
    """
    lines: list[int] = []
    for node in _walk_local(*scope.body):
        if isinstance(node, (ast.For, ast.AsyncFor)):
            counters = _incremented_names(*node.body) & countable
            if not counters:
                continue  # Keine gemeldete Zählung — nur eine gewöhnliche Schleife.
            if not _contains_opaque_call(*node.body):
                continue  # Nur Feldzugriffe/Vergleiche/Rechnung (AC-8b).
            lines.append(node.lineno)
        elif _is_blind_counting_sum(node, scope, returned):
            lines.append(node.lineno)
    return sorted(set(lines))


def _is_blind_counting_sum(
    node: ast.AST, scope: ast.AST, returned: set[str]
) -> bool:
    """``sum(<genexp>)`` als Zählung über einen undurchsichtigen Aufruf.

    Drei Bedingungen, alle nötig:

    * die Zählung ist ein ``sum(...)`` über eine Comprehension — ``sum(temps)``
      über eine fertige Liste zählt nichts, es rechnet (AC-8b);
    * das Ergebnis wird gemeldet (steht in einem ``return`` oder in einer
      Zuweisung an einen Namen, der zurückgegeben wird) — sonst ist es eine
      Zwischenrechnung, kein Erfolgsbericht;
    * im Element ODER im Filter der Comprehension steckt ein undurchsichtiger
      Aufruf. Die ITERATIONSQUELLE (``for preset in self._load_presets()``)
      zählt bewusst nicht: das ist die Menge, über die gezählt wird, nicht der
      gezählte Zustand — sonst wäre jede Comprehension über einen Lade-Aufruf
      ein Fund.
    """
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sum"
        and node.args
        and isinstance(node.args[0], (ast.GeneratorExp, ast.ListComp, ast.SetComp))
    ):
        return False
    if not _value_is_reported(node, scope, returned):
        return False
    comprehension = node.args[0]
    counted: list[ast.AST] = [comprehension.elt]
    for generator in comprehension.generators:
        counted.extend(generator.ifs)
    return _contains_opaque_call(*counted)


def _value_is_reported(node: ast.AST, scope: ast.AST, returned: set[str]) -> bool:
    """Fließt dieser Ausdruck in die Rückgabe der Funktion?

    Entweder direkt in einem ``return`` (``return sum(...)`` — so liegt B11c im
    Bestand) oder über einen zurückgegebenen Namen. Eine Zwischenrechnung, die
    niemand meldet, kann nichts unverdient behaupten.
    """
    for statement in _walk_local(*scope.body):
        if isinstance(statement, ast.Return) and statement.value is not None:
            if any(inner is node for inner in ast.walk(statement.value)):
                return True
        elif isinstance(statement, ast.Assign) and statement.value is not None:
            targets = {
                target.id
                for target in statement.targets
                if isinstance(target, ast.Name)
            }
            if targets & returned and any(
                inner is node for inner in ast.walk(statement.value)
            ):
                return True
    return False


def _find_unwired_heartbeat_violations(paths: Iterable[Path]) -> dict[str, str]:
    """Klasse 3 über die GANZE Scanfläche, geschlüsselt wie alle anderen
    Detektoren (``{"pfad::funktion::ordinal": "heartbeat_unwired"}``, #1466 AP2).

    Dünner Mantel um ``_unwired_heartbeat_raw()``; ``_all_violations()``
    braucht die ROHE, zeilenbezogene Fassung, weil das Ordinal erst NACH dem
    Zusammenführen mit den vier dateiweisen Detektoren vergeben werden darf —
    sonst bekämen zwei verschiedene Funde derselben Funktion beide die 0.
    """
    return _number_findings(_unwired_heartbeat_raw(paths))


def _unwired_heartbeat_raw(paths: Iterable[Path]) -> dict[str, str]:
    """Klasse 3 über die GANZE Scanfläche als ``{"pfad:zeile": "heartbeat_unwired::funktion"}``.

    Einziger Detektor, der nicht dateiweise arbeiten kann: „wird nirgends
    aufgerufen" ist eine Aussage über die gesamte Scanfläche, nicht über eine
    Datei. Deshalb nimmt er die Pfadliste statt eines einzelnen Pfads.

    GREEN muss liefern:

    * **Heartbeat-Funktionen sammeln:** jede ``FunctionDef``/
      ``AsyncFunctionDef``, deren Name (klein geschrieben) einen der
      ``_HEARTBEAT_NAME_MARKERS`` enthält — mit Datei und Zeile ihrer
      Definition.
    * **Aufrufe sammeln:** jeden ``ast.Call`` über alle Dateien der
      Scanfläche, dessen aufgerufener Name (``Name.id`` oder
      ``Attribute.attr``) einem dieser Funktionsnamen entspricht. Der Aufruf
      IN der eigenen Definition zählt nicht (Rekursion ist keine
      Verdrahtung), und ``tests/`` ist gar nicht Teil der Scanfläche — ein
      Unit-Test des No-Env-Verhaltens beweist nicht, dass der Heartbeat im
      Betrieb feuert (genau so liegt B13 im Bestand).
    * **Fund melden:** jede Heartbeat-Funktion mit null Aufrufern. Ein
      vorhandener Aufruf hinter einer Erfolgsbedingung (``if sent > 0:``)
      macht sie grün (AC-11) — dass der Aufruf hinter der RICHTIGEN Bedingung
      steht, prüft dieser Wächter ausdrücklich nicht (s. Modul-Docstring,
      „Bekannte Grenzen").

    Fundzeile ist die Zeile der ``def``-Anweisung.
    """
    # Eine LISTE, kein Dict nach Namen: zwei gleichnamige Heartbeat-Funktionen
    # in verschiedenen Dateien dürfen einander nicht still überschreiben.
    definitions: list[tuple[str, str, int]] = []
    trees: list[ast.Module] = []

    for path in paths:
        tree = _parse(path)
        trees.append(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            lowered = node.name.lower()
            if any(marker in lowered for marker in _HEARTBEAT_NAME_MARKERS):
                definitions.append((node.name, _relative_path(path), node.lineno))

    heartbeat_names = {name for name, _location, _lineno in definitions}
    if not heartbeat_names:
        return {}

    called: set[str] = set()
    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            if name not in heartbeat_names:
                continue
            # Rekursion ist keine Verdrahtung: ein Aufruf INNERHALB der eigenen
            # Definition beweist nur, dass die Funktion sich selbst kennt.
            if _is_inside_own_definition(tree, node, name):
                continue
            called.add(name)

    return {
        f"{location}:{lineno}": f"{KIND_HEARTBEAT_UNWIRED}::{name}"
        for name, location, lineno in definitions
        if name not in called
    }


def _is_inside_own_definition(tree: ast.Module, call: ast.Call, name: str) -> bool:
    """Steht dieser Aufruf im Rumpf der gleichnamigen Funktion selbst?"""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != name:
            continue
        if any(inner is call for inner in ast.walk(node)):
            return True
    return False


def _find_unacknowledged_dispatch_violations(path: Path) -> dict[str, str]:
    """Klasse 4 in EINER Datei als ``{"pfad:zeile": "unacknowledged_dispatch::funktion"}``.

    GREEN muss liefern — je Funktionsraum der Datei:

    * **Rumpf ist im Wesentlichen ein ``try/except``:** die tragende Arbeit
      der Funktion steht in einem ``Try``-Knoten (Vorspann wie lokale
      Importe, Präfix-Berechnungen o. Ä. davor ist unschädlich — so liegen
      ``_dispatch_compare_official_telegram`` und ``_sms`` im Bestand, die
      beide einen lokalen Import vor dem ``try`` haben).
    * **Handler protokolliert nur:** jeder ``except``-Zweig enthält
      ausschließlich ``logger.*``-Aufrufe (``_is_logger_call``) — kein
      ``raise``, kein ``return``, keine Zustandsänderung. Der Fehlschlag
      verwandelt sich in nichts.
    * **Kein Erfolgssignal an den Aufrufer:** die Funktion enthält kein
      einziges ``return`` mit einem Wert. Ein nacktes ``return`` (früher
      Ausstieg, so im Kurzform-Zweig von
      ``_dispatch_compare_official_telegram``, Z. 916, und im
      ``is_sms_only``-Vorspann von ``_send_service_error_email``, Z. 1297)
      ist KEIN Erfolgssignal und rettet den Fall nicht — es liefert ``None``
      wie das Funktionsende auch (S-9). Ohne diesen Ausschluss verlöre
      Klasse 4 ein Drittel der B14b-Erwartung. Eine Annotation ``-> None``
      ist ein zusätzliches Indiz, aber nicht erforderlich (nicht jede
      Fundstelle ist annotiert).
    * **Versandkontext feststellen** (E2, NEU Version 1.2 — die
      entscheidende Zusatzbedingung): der Rumpf enthält SELBST einen
      Ausgabe-/Versandaufruf, also einen Aufruf auf eine Klasse aus
      ``_CHANNEL_OUTPUT_CLASSES`` bzw. deren ``.send(...)``-Methode ODER auf
      einen übergebenen Sink-Parameter (Name endet auf
      ``_SINK_PARAMETER_SUFFIX``). Ohne diese Bedingung traf Klasse 4 in der
      RED-Phase gegen Version 1.1 **18 statt 3** Stellen, davon 15
      Persistenz-Helfer (``alert_state.save``/``reset``,
      ``weather_snapshot.save``, ``compare_weather_snapshot.save`` u. a.).
      Ein ``save()``, das jeden Fehler schluckt, ist ein verwandtes, aber
      ANDERES Problem — dieses Ticket zielt auf Erfolgs*meldungen*, nicht auf
      Persistenz (AC-13b prüft die Abgrenzung, Sammel-Eintrag #1199).

    Traf (nach der E2-Einschränkung, verifiziert gegen ``0627612d``) SECHS
    Funktionen, alle in ``notification_service.py``; seit #1459 sind es
    **DREI**:

    * **B14b — seit #1459 (``161db8bb``) BEHOBEN, kein Fund mehr:** die drei
      Compare-Versandhelfer ``_dispatch_compare_official_email``,
      ``_dispatch_compare_official_telegram`` und
      ``_dispatch_compare_official_sms`` liefern jetzt ``bool``, und
      ``send_compare_official_alert()`` verwertet es zu ``failed_channels``.
      Damit greift der Ausschluss ``_returns_a_value()`` (AC-13).
    * **B21** (NEU Version 1.2) — ``_send_telegram_incomplete_hint``
      (Z. 385, ruft ``TelegramOutput(...).send(...)``),
      ``send_command_reply_email`` (Z. 1115, ruft
      ``EmailOutput(...).send(...)``) und ``_send_service_error_email``
      (Z. 1293, ruft ``EmailOutput(...).send(...)`` nach einem
      ``is_sms_only``-Vorspann).

    B21 ist vom Detektor STRUKTURELL nicht von B14b zu unterscheiden — beide
    Gruppen sind Ein-Funktion-Prüfungen mit derselben Mechanik. Eine
    künstliche Verengung, die genau diese drei ausschließt, ohne die
    Grundmechanik zu ändern, wäre Signatur-Verengung zur Zahlenkosmetik
    (CLAUDE.md: „Neue Funde werden NICHT durch Verengung der Signatur
    wegdefiniert"). Sie stehen deshalb in der Restliste.

    Der Aufrufer ``send_multi_location_official_alert`` (Z. 798) ist selbst
    NICHT erkennbar — er enthält gar kein ``try``, und syntaktisch ist er vom
    korrekten E-Mail-Zweig in ``send_compare_report`` nicht zu unterscheiden.
    Eine Namens-Heuristik auf die äußere Funktion wurde ausdrücklich
    abgelehnt (träfe zufällig, bräche bei Umbenennung) — der Fund hängt
    stattdessen an den Helfern, die die Signatur einzeln verifizierbar
    erfüllen (Spec „Geklärte Punkte" 7).

    Fundzeile ist die Zeile der ``def``-Anweisung — die Funktion als Ganzes
    ist der Fund, nicht eine einzelne Anweisung darin.
    """
    tree = _parse(path)
    rel = _relative_path(path)
    found: dict[str, str] = {}

    for scope, scope_name in _scopes(tree):
        if scope_name == _MODULE_SCOPE:
            continue  # Ein Modulrumpf hat keinen Aufrufer, dem er etwas schuldet.
        if not any(isinstance(statement, ast.Try) for statement in scope.body):
            continue  # Der Rumpf ist nicht im Wesentlichen ein try/except.
        if not _every_handler_only_logs(scope):
            continue  # Ein Handler, der wirft oder zurückgibt, meldet sehr wohl.
        if _returns_a_value(scope):
            continue  # Es GIBT ein Erfolgssignal (AC-13).
        if not _dispatches_on_a_channel(scope):
            continue  # Kein Versandkontext — Persistenz gehört hier nicht her (AC-13b).
        found[f"{rel}:{scope.lineno}"] = (
            f"{KIND_UNACKNOWLEDGED_DISPATCH}::{scope_name}"
        )
    return found


def _every_handler_only_logs(scope: ast.AST) -> bool:
    """Protokolliert JEDER ``except``-Zweig dieses Raums nur — und tut sonst nichts?

    „Nur protokollieren" heißt wörtlich: jede Anweisung im Handler ist ein
    ``logger.*``-Aufruf. Ein ``raise`` reicht den Fehlschlag nach oben, ein
    ``return`` liefert ein Signal, eine Zuweisung ändert Zustand — überall
    wird der Fehlschlag zu etwas, und der Fall gehört nicht zu Klasse 4.
    """
    handlers = [
        handler
        for node in _walk_local(*scope.body)
        for handler in getattr(node, "handlers", []) or []
    ]
    if not handlers:
        return False
    for handler in handlers:
        if not handler.body:
            return False
        for statement in handler.body:
            if not (
                isinstance(statement, ast.Expr) and _is_logger_call(statement.value)
            ):
                return False
    return True


def _returns_a_value(scope: ast.AST) -> bool:
    """Gibt die Funktion dem Aufrufer irgendwo einen Wert zurück?

    Ein NACKTES ``return`` zählt nicht (S-9): ``ast.Return(value=None)``
    liefert ``None`` wie das Funktionsende auch — es ist ein früher Ausstieg,
    kein Erfolgssignal. Ohne diesen Ausschluss fielen
    ``_dispatch_compare_official_telegram`` (Kurzform-Zweig) und
    ``_send_service_error_email`` (``is_sms_only``-Vorspann) heraus, und
    Klasse 4 verlöre ein Drittel ihrer belegten Fundstellen.
    """
    return any(
        isinstance(node, ast.Return) and node.value is not None
        for node in _walk_local(*scope.body)
    )


def _dispatches_on_a_channel(scope: ast.AST) -> bool:
    """Versandkontext (E2): ruft der Rumpf SELBST einen Kanal-Ausgang auf?

    Zugelassen sind zwei Formen:

    * ein Aufruf auf eine Klasse aus ``_CHANNEL_OUTPUT_CLASSES``
      (``EmailOutput(self._settings).send(...)`` — erkennbar am Konstruktor);
    * ein Aufruf auf einen übergebenen Sink-Parameter (``mail_sink(...)``) —
      Endung statt fester Liste, weil die Sinks unterschiedlich heißen.

    Diese Bedingung trennt „Erfolg heißt Wirkung" von „Persistenz schluckt
    Fehler": ohne sie traf Klasse 4 18 statt 6 Stellen (AC-13b). Der
    Persistenz-Befund ist nicht wegdiskutiert, nur in eine andere Scheibe
    verwiesen (#1199).
    """
    for node in _walk_local(*scope.body):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id in _CHANNEL_OUTPUT_CLASSES:
            return True
        if node.func.id.endswith(_SINK_PARAMETER_SUFFIX):
            return True
    return False


def _number_findings(raw: dict[str, str]) -> dict[str, str]:
    """Rohfunde ``{"pfad:zeile": "art::funktion"}`` → ``{"pfad::funktion::ordinal": "art"}``.

    Issue #1466 AP2: der zeilenbasierte Schlüssel wanderte bei JEDER
    eingefügten Zeile. Zuletzt galten hier 13 Stellen gleichzeitig als behoben
    (alter Schlüssel) und als neuer Verstoß (neuer Schlüssel), mit
    UNTERSCHIEDLICHEM Versatz je Datei (+3 in notification_service.py,
    +119/+124 in trip_alert.py) — von Hand nicht mit einer Zahl nachzuziehen.

    Der neue Schlüssel nennt Datei, umschließende Funktion und die Position
    des Fundes INNERHALB dieser Funktion (0-basiert, nach Zeilennummer
    sortiert — dieselbe Zählweise in allen drei Wächtern). Der Funktionsname
    wandert damit vom WERT in den SCHLÜSSEL; im Wert bleibt allein die Art
    (bei einer Kollision zweier Detektoren auf derselben Zeile weiterhin
    ``"art_a+art_b"``, S-6).

    Das Ordinal ist Pflicht: ohne es fielen die Mehrfachfunde derselben
    Funktion zusammen (``_handle_query`` ×4, ``send_official_alert`` ×3,
    ``_dispatch_alert_message`` ×3, ``_trigger_on_demand`` ×2) und AC-1/AC-17
    wären strukturell unerfüllbar. Die Grenzen des Schlüssels stehen in der
    Spec zu #1466 unter „Bekannte Grenzen": eine Umbenennung/Aufteilung der
    Funktion bricht ihn weiterhin.
    """
    by_scope: dict[tuple[str, str], dict[int, str]] = {}
    for location, kind in raw.items():
        path, _, lineno = location.rpartition(":")
        kinds, _, scope_name = kind.partition("::")
        by_scope.setdefault((path, scope_name), {})[int(lineno)] = kinds
    numbered: dict[str, str] = {}
    for (path, scope_name), by_line in by_scope.items():
        for ordinal, lineno in enumerate(sorted(by_line)):
            numbered[f"{path}::{scope_name}::{ordinal}"] = by_line[lineno]
    return numbered


def _find_violations(path: Path) -> dict[str, str]:
    """Die vier dateiweisen Detektoren (Klasse 1, 1c, 2, 4) für EINE Datei.

    GREEN muss liefern — die Vereinigung von
    ``_find_constant_success_violations(path)``,
    ``_find_pre_try_success_marker_violations(path)``,
    ``_find_partial_success_blind_violations(path)`` und
    ``_find_unacknowledged_dispatch_violations(path)``. Klasse 3 fehlt hier
    bewusst: sie braucht die ganze Scanfläche (s. dort) und hat deshalb einen
    eigenen Einstieg.

    Kollidieren zwei Detektoren auf derselben ``pfad:zeile``, gewinnt keiner
    still: GREEN muss beide Arten im Wert führen (z. B.
    ``"heartbeat_unwired+unacknowledged_dispatch::_ping_heartbeat_compare"``)
    statt eine zu überschreiben — sonst verschwindet ein Fund im
    Zusammenführen, und das wäre genau der Fehler, gegen den dieser Wächter
    gebaut ist (S-6, Spec Version 1.2).

    **Das Beispiel ist nicht mehr aktuell:** ``scheduler.py:147`` kollidiert
    seit der E2-Einschränkung nicht mehr (``_ping_heartbeat_compare`` ruft
    ``httpx.get(...)``, keinen Kanal-Ausgang). Die Merge-Regel bleibt als
    Verteidigung in der Tiefe verbindlich.
    """
    found: dict[str, str] = {}
    _merge_findings(found, _find_constant_success_violations(path))
    _merge_findings(found, _find_pre_try_success_marker_violations(path))
    _merge_findings(found, _find_partial_success_blind_violations(path))
    _merge_findings(found, _find_unacknowledged_dispatch_violations(path))
    # Die Detektoren arbeiten intern weiter zeilenbezogen (S-6-Merge braucht
    # die Zeile als Kollisionsmerkmal); nach außen gilt seit #1466 AP2 der
    # verschiebungsfeste Schlüssel.
    return _number_findings(found)


def _all_violations() -> dict[str, str]:
    """Alle fünf Detektoren über die gesamte Scanfläche, zu EINEM Dict vereint.

    GREEN muss liefern:

    * ``_find_violations(path)`` für jede Datei aus ``_scan_files()``,
    * PLUS ``_find_unwired_heartbeat_violations(_scan_files())`` einmal über
      die ganze Liste,
    * zusammengeführt und ERST DANACH nummeriert (#1466 AP2) zu einem Dict
      ``{"pfad::funktion::ordinal": "art"}``.

    Die Mehrfachtreffer-Regel (S-6) gilt AUCH HIER, über die Detektor-
    DURCHLÄUFE hinweg: trifft der Klasse-3-Lauf dieselbe Datei+Zeile wie
    ein dateiweiser Detektor, führt ``_merge_findings`` beide Arten im Wert.

    Das Ergebnis ist ROH: Einträge aus ``INTENTIONAL_CONSTANT_SUCCESS`` sind
    hier noch enthalten. Gefiltert wird erst in der Ratsche (AC-2) — sonst
    könnte ein Ausnahme-Eintrag, den der Scanner in Wahrheit gar nicht mehr
    findet, unbemerkt als Dauereinrichtung stehenbleiben (AC-14 prüft genau
    das).
    """
    paths = _scan_files()
    found: dict[str, str] = {}
    for path in paths:
        _merge_findings(found, _find_constant_success_violations(path))
        _merge_findings(found, _find_pre_try_success_marker_violations(path))
        _merge_findings(found, _find_partial_success_blind_violations(path))
        _merge_findings(found, _find_unacknowledged_dispatch_violations(path))
    _merge_findings(found, _unwired_heartbeat_raw(paths))
    # Erst NACH dem Zusammenführen ALLER fünf Detektoren nummerieren (#1466
    # AP2): das Ordinal ist die Position innerhalb der Funktion über alle
    # Fundarten hinweg. Würde jeder Detektor für sich nummerieren, trügen zwei
    # verschiedene Funde derselben Funktion beide die 0 und einer verschwände.
    return _number_findings(found)


def _finding_locations(found: dict[str, str]) -> set[str]:
    """Scan-Ergebnis → Menge aus ``"pfad::funktion"`` (ohne Ordinal).

    Reine Umformung des Scanner-Ergebnisses (kein Stub, keine Erkennung),
    damit die synthetischen Nachweise gegen einen zeilen- UND ordinalstabilen
    Namen prüfen können.
    """
    return {location.rsplit("::", 1)[0] for location in found}


def _finding_location_counts(found: dict[str, str]) -> dict[str, int]:
    """Scan-Ergebnis → ``"pfad::funktion"`` mit der ZAHL der Treffer darin.

    Gezählt wird über das Ordinal, das seit #1466 im Schlüssel steckt — nur so
    bleiben drei Kanal-Vorkommen derselben Funktion drei Treffer.
    ``_finding_locations()`` wirft das Ordinal weg und lässt sie zu einem
    Eintrag zusammenfallen; AC-1 wäre damit blind dafür, ob der Scanner alle
    drei ``sent_channels.append()``-Stellen in ``_dispatch_alert_message``
    sieht oder nur eine.
    """
    counts: Counter[str] = Counter()
    for location in found:
        counts[location.rsplit("::", 1)[0]] += 1
    return dict(counts)


# ---------------------------------------------------------------------------
# Restliste aus der #1405-Bestandsaufnahme (B1–B21) — DARF NUR SCHRUMPFEN.
# Schlüssel = "pfad::funktion::ordinal" (wie vom Scanner geliefert, s.
# _number_findings), Wert = Begründung + Issue-Bezug.
#
# UMSCHLÜSSELUNG (#1466 AP2, 2026-08-02): früher "pfad:zeile". Dieser
# Schlüssel wanderte bei jeder eingefügten Zeile, zuletzt mit
# UNTERSCHIEDLICHEM Versatz je Datei (+3 in notification_service.py,
# +119/+124 in trip_alert.py) — 13 unveränderte Stellen galten gleichzeitig
# als behoben und als neuer Verstoß. Die Einträge selbst sind UNVERÄNDERT:
# dieselben 45 Codestellen, dieselben Begründungen, keine gestrichen. Die
# alte Zeilennummer steht nicht mehr im Schlüssel; die Funktion, die sie
# meinte, nennt jede Begründung ohnehin. Ein NEUER, hier nicht gelisteter Fund ist ein echter Rückfall
# (test_no_unlisted_success_status_findings schlägt fehl). Ein hier gelisteter
# Fund, den der Scanner nicht mehr findet, MUSS entfernt werden
# (test_known_violations_only_shrink schlägt sonst fehl, "veraltet").
#
# Alle Zeilennummern hier stammen aus dem ECHTEN Scan-Lauf, nicht aus der
# Spec-Tabelle — sonst prüfte die Ratsche eine Abschrift statt den Code. Die
# Spec-Tabelle B1–B21 ist die unabhängige Gegenprobe dazu und steht in
# SPEC_LISTED_FINDINGS (AC-1). Wo die Spec eine andere Zeile nennt, ist das
# kein Widerspruch, sondern die dort festgelegte Fundzeilen-Regel: Klasse 1
# meldet die Zeile des `return`, Klasse 2 die der Iteration, Klasse 3 und 4
# die der `def`-Anweisung (die Spec-Tabelle nennt teils die `def`-Zeile).
#
# 42 Einträge für 34 Funktionsschlüssel — gegenüber der Spec-Erwartung (33
# Schlüssel, 40 Treffer, plus Webhook-Ack in INTENTIONAL_CONSTANT_SUCCESS) zwei
# von Hand nachgelesene Zuwächse mit je derselben Mechanik wie eine belegte
# Fundstelle (Begründung steht beim jeweiligen Eintrag). Keine Verbreiterung
# der Signatur; die Bestandsaufnahme war unvollständig wie in Hälfte A.
# (B13 mit #1407, B2 mit #1447 und B14b — drei Schlüssel — mit #1459 aus der
# Restliste entfernt: alle Funde wurden repariert (B13 geloescht, B2 leitet
# den Status jetzt ab, B14b liefert und verwertet jetzt `bool`) — der
# Scanner findet dort nichts mehr, die Ratsche ist entsprechend kleiner.
# B14b mit #1459 aus SPEC_LISTED_FINDINGS entfernt (drei Schlüssel, Soll 36/43
# -> 33/40): _dispatch_compare_official_{email,telegram,sms} liefern jetzt
# `bool` statt gar keinen Rückgabewert, und send_compare_official_alert()
# WERTET ihn aus — er füllt `failed_channels`. Vorher wurde das `False`
# weggeworfen, ein gescheiterter Ortsvergleich-Versand galt als Erfolg; genau
# das war der Mangel. Der Scanner findet dort nichts mehr.)
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: dict[str, str] = {
    # --- B3–B8: sieben Trigger-Endpunkte, ein Muster. Fällt der Service für
    # ALLE Vorgänge durch, meldet der Endpunkt "ok" mit count=0 — von einem
    # ruhigen Tag ohne Alarme nicht zu unterscheiden (#1290).
    # Zeilennummern hier (und bei B1 unten) mit #1407 um den Löschbetrag von
    # _ping_heartbeat_compare (25 Zeilen, s. o.) verschoben — die Funde selbst
    # sind unverändert dieselben Stellen, nur weiter oben im File.
    # --- B2 entfernt (#1447 S1): trigger_alert_checks leitet den Status jetzt
    # aus AlertCheckRunResult.hit_deadline ab (status="partial" bei
    # Zeitobergrenze, sonst "ok") statt ihn fest zu setzen — der Scanner
    # findet an dieser Stelle nichts mehr, der Eintrag entfaellt mit ihr.
    "api/routers/scheduler.py::trigger_compare_alert_checks::0": (
        "B3 (#1405) — trigger_compare_alert_checks: dito (Deviation)."
    ),
    "api/routers/scheduler.py::trigger_radar_alert_checks::0": (
        "B4 (#1405) — trigger_radar_alert_checks: dito (Radar)."
    ),
    "api/routers/scheduler.py::trigger_compare_radar_alert_checks::0": (
        "B5 (#1405) — trigger_compare_radar_alert_checks: dito."
    ),
    "api/routers/scheduler.py::trigger_compare_official_alert_checks::0": (
        "B6 (#1405) — trigger_compare_official_alert_checks: dito."
    ),
    "api/routers/scheduler.py::trigger_inbound::0": (
        "B7 (#1405) — trigger_inbound: dito; der 'skipped'-Zweig ist korrekt."
    ),
    "api/routers/scheduler.py::trigger_inbound_telegram::0": (
        "B8 (#1405) — trigger_inbound_telegram: dito, Feld heißt 'processed'."
    ),
    # --- B13 entfernt (#1407): die Funktion war toter Code (Legacy-Pfad
    # #1131) und wurde ersatzlos geloescht statt angeschlossen — der Scanner
    # findet an dieser Stelle nichts mehr, der Eintrag entfaellt mit ihr.
    # --- B1: der #1403-Fall. Der Nutzer liest "Testmail verschickt", obwohl
    # nie etwas losgeschickt wurde ("no_channels" fällt bis zu sent=True durch).
    "api/routers/scheduler.py::send_test_trip_report::0": (
        "B1 (#1403/#1405) — send_test_trip_report: 'sent': True trotz outcome."
    ),
    # --- B11/B11b/B11c: die drei Compare-Alarmprüfer. Bei allen dreien heißt
    # eine 0 "nichts zu melden" ODER "alles kaputt" — kein Fehlerzähler.
    "src/services/compare_alert.py::check_all_compare_presets::0": (
        "B11 (#1405) — check_all_compare_presets: sent gezaehlt, kein Gegenzähler."
    ),
    "src/services/compare_official_alert.py::check_all_compare_presets::0": (
        "B11c (#1405) — check_all_compare_presets: sum(genexp) ohne try/except."
    ),
    "src/services/compare_radar_alert.py::check_all_compare_presets::0": (
        "B11b (#1405) — check_all_compare_presets: über _check_one_preset(...)."
    ),
    # --- B19/B20: die beiden Inbound-Reader. In Spec-Version 1.1 fälschlich
    # als "kein Fund" geführt (E4).
    "src/services/inbound_email_reader.py::poll_and_process::0": (
        "B19 (#1405) — poll_and_process: processed hoch, except nur logger.error."
    ),
    "src/services/inbound_telegram_reader.py::poll_and_process::0": (
        "B20 (#1405) — poll_and_process: dito über _process_update(...)."
    ),
    # --- B21: Klasse 4 im Versandkontext, bei der E2-Verifikation gefunden.
    # Strukturell nicht von B14b zu unterscheiden.
    "src/services/notification_service.py::_send_telegram_incomplete_hint::0": (
        "B21 (#1405) — _send_telegram_incomplete_hint: TelegramOutput, kein Signal."
    ),
    # --- B14a: Marker vor der Tat, drei Kanäle. NotificationResult.sent=True
    # heißt damit "konfiguriert", nicht "zugestellt" (#684 AC-3, #656).
    "src/services/notification_service.py::send_official_alert::0": (
        "B14a (#1405/#684) — send_official_alert: append('email') vor dem try."
    ),
    "src/services/notification_service.py::send_official_alert::1": (
        "B14a (#1405/#684) — send_official_alert: dito, Telegram."
    ),
    "src/services/notification_service.py::send_official_alert::2": (
        "B14a (#1405/#684) — send_official_alert: dito, SMS."
    ),
    # Issue #1701 (S2b, D7): vierter Kanal Premium-SMS (Garmin inReach) --
    # bewusste Ratschen-Anhebung 3->4, NICHT die Buchung hinter den `try`
    # verschoben (s. Spec D7). `sent_channels`="versucht" bleibt getrennt von
    # `reachable_channels`="erreichbar" -- dieselbe Marker-vor-der-Tat-Semantik
    # wie die drei Bestandskanaele.
    "src/services/notification_service.py::send_official_alert::3": (
        "B14a (#1405/#684, #1701 D7) — send_official_alert: dito, Premium-SMS."
    ),
    # --- B14b ENTFERNT (#1459, 2026-08-02): die drei Compare-Versandhelfer
    # _dispatch_compare_official_{email,telegram,sms} hatten keine Rückmeldung —
    # der Aufrufer buchte den Erfolg auf den bloßen Umstand, dass er sie
    # GERUFEN hatte. Seit `161db8bb` liefern alle drei `bool`, und
    # send_compare_official_alert() WERTET den Rückgabewert aus: aus einem
    # `False` wird ein Eintrag in `failed_channels`, der in
    # NotificationResult.failed_channels beim Aufrufer ankommt
    # (notification_service.py:882-906). Damit trifft die Klasse-4-Signatur
    # ("kein Erfolgssignal an den Aufrufer") strukturell nicht mehr zu; der
    # Scanner findet dort nichts mehr.
    #
    # Dritter Fall derselben Mechanik wie B13 (#1407) und B2 (#1447): eine
    # Fundstelle verschwindet, WEIL sie repariert wurde. Geprüft wurde beides
    # — die drei Funktionen existieren unverändert unter denselben Namen
    # (keine Umbenennung/Auflösung, die den Verstoß nur verschoben hätte), und
    # die "unlisted"-Hälfte des Wächters ist leer (kein Fund unter einem
    # anderen Namen wieder aufgetaucht). Die Spec-Gegenprobe
    # SPEC_LISTED_FINDINGS war mit #1459 bereits nachgezogen; NUR diese
    # Restliste blieb stehen, weil ihr zeilenbasierter Schlüssel damals
    # ohnehin schon 13-fach rot war und der echte Fortschritt darin unterging.
    # Genau dagegen ist #1466 gebaut.
    # --- B14c: dasselbe Marker-vor-der-Tat-Muster im gemeinsamen
    # Alarm-Versandweg (Änderungs-, Radar- und amtliche Alarme).
    "src/services/notification_service.py::_dispatch_alert_message::0": (
        "B14c (#1405/#684) — _dispatch_alert_message: append('email') vor dem try."
    ),
    "src/services/notification_service.py::_dispatch_alert_message::1": (
        "B14c (#1405/#684) — _dispatch_alert_message: dito, Telegram."
    ),
    "src/services/notification_service.py::_dispatch_alert_message::2": (
        "B14c (#1405/#684) — _dispatch_alert_message: dito, SMS."
    ),
    # Issue #1701 (S2b, D7): vierter Kanal Premium-SMS, dieselbe Begruendung
    # wie bei send_official_alert::3 oben.
    "src/services/notification_service.py::_dispatch_alert_message::3": (
        "B14c (#1405/#684, #1701 D7) — _dispatch_alert_message: dito, Premium-SMS."
    ),
    "src/services/notification_service.py::send_command_reply_email::0": (
        "B21 (#1405) — send_command_reply_email: EmailOutput, keine Rückmeldung."
    ),
    "src/services/notification_service.py::_send_service_error_email::0": (
        "B21 (#1405) — _send_service_error_email: EmailOutput, nacktes return (S-9)."
    ),
    # --- B12: top_ort/actual_empfaenger sind abgeleitet und stehen im selben
    # Dict — der Erfolgs-Schlüssel daneben ist trotzdem hartkodiert.
    "src/services/scheduler_dispatch_service.py::send_compare_preset::0": (
        "B12 (#1405) — send_compare_preset: 'status': 'ok' fest."
    ),
    # --- B9/B10: die beiden Trip-Alarmprüfer.
    "src/services/trip_alert.py::check_all_trips::0": (
        "B9 (#1405) — check_all_trips: alerts_sent ohne Gegenzähler, return int."
    ),
    "src/services/trip_alert.py::check_radar_alerts::0": (
        "B10 (#1405) — check_radar_alerts: sent ohne Gegenzähler."
    ),
    # --- B18: dateiweites Muster, zehn Funktionen, 13 Treffer. Reparatur (S4)
    # am Stück: EINE Entscheidung darüber, was CommandResult.success bedeutet
    # (Antwort verfasst vs. zugrundeliegende Aktion erfolgreich).
    "src/services/trip_command_processor.py::_handle_query::0": (
        "B18 (#1405) — _handle_query (glance): nach self._fmt_glance(...)."
    ),
    "src/services/trip_command_processor.py::_handle_query::1": (
        "B18 (#1405) — _handle_query (heute_gewitter): nach _fmt_gewitter(...)."
    ),
    "src/services/trip_command_processor.py::_handle_query::2": (
        "B18 (#1405) — _handle_query (timeline_heute): nach _fmt_timeline(...)."
    ),
    "src/services/trip_command_processor.py::_handle_query::3": (
        "B18 (#1405) — _handle_query (timeline_morgen): dito."
    ),
    # --- B16: outcome wird geprüft, der Text variiert korrekt — nur `success`
    # bleibt in BEIDEN Ausgängen True (zweiter Treffer: s. Kopfkommentar).
    "src/services/trip_command_processor.py::_trigger_on_demand::0": (
        "B16 (#1405) — _trigger_on_demand: success=True trotz outcome != 'sent'."
    ),
    "src/services/trip_command_processor.py::_trigger_on_demand::1": (
        "B16 (#1405) — _trigger_on_demand: Erfolgsausgang, ohne Bezug auf outcome."
    ),
    "src/services/trip_command_processor.py::_handle_drilldown::0": (
        "B18 (#1405) — _handle_drilldown: nach WeatherExtractor(...).drilldown()."
    ),
    "src/services/trip_command_processor.py::_handle_hours_drilldown::0": (
        "B18 (#1405) — _handle_hours_drilldown: nach vier drilldown(...)-Abrufen."
    ),
    "src/services/trip_command_processor.py::_apply_ruhetag::0": (
        "B18 (#1405) — _apply_ruhetag: nach unzugewiesenem save_trip(...)."
    ),
    # --- B15: das Ergebnis wird nicht einmal entgegengenommen.
    "src/services/trip_command_processor.py::_trigger_report::0": (
        "B15 (#1405) — _trigger_report: send_test_report(...) unzugewiesen."
    ),
    "src/services/trip_command_processor.py::_show_status::0": (
        "B18 (#1405) — _show_status: matcht über das triviale date.today(). "
        "Bewusst aufgenommen (Arbeitsvorrat, keine Vorab-Filterung) — die "
        "Signatur ist syntaktisch, nicht risikobewusst (Spec 'Offene Punkte' 3)."
    ),
    "src/services/trip_command_processor.py::_apply_pause::0": (
        "B18 (#1405) — _apply_pause: nach unzugewiesenem save_trip(...)."
    ),
    "src/services/trip_command_processor.py::_apply_skip::0": (
        "B18 (#1405) — _apply_skip: dito."
    ),
    "src/services/trip_command_processor.py::_show_now::0": (
        "B18 (#1405) — _show_now: nach svc.get_nowcast(...)/format_now_text(...)."
    ),
    "src/services/trip_command_processor.py::_cancel_trip::0": (
        "B18 (#1405) — _cancel_trip: nach bedingtem, unzugewiesenem save_trip(...)."
    ),
    "src/services/trip_command_processor.py::_resume_trip::0": (
        "B18 (#1405) — _resume_trip: dito."
    ),
    # --- Issue #2051 S4 (/strecke-Kommando, Adversary-Runde 3): dieselbe
    # B18-Signatur wie _show_now/_show_status/_handle_query oben -- nach
    # einem Aufruf (get_nowcast(...)/derive_rain_zones(...)/den beiden
    # Renderern) folgt ein unbedingtes `success=True`, das nicht auf den
    # Aufruf Bezug nimmt. Fachlich geprueft (team-lead-Auftrag): `success`
    # wird von KEINEM Aufrufer gelesen (inbound_telegram_reader.py,
    # inbound_email_reader.py senden confirmation_subject/-body IMMER
    # gleich zurueck, unabhaengig vom Wert) -- die Unterscheidung hat heute
    # keine Verhaltensauswirkung. Fachlich ist `success=True` in allen drei
    # Zweigen zudem korrekt: das Kommando hat eine gueltige, ehrliche
    # Antwort verfasst (auch der Ausfall-Zweig AC-7 ist per Spec E1 eine
    # normale, keine fehlgeschlagene Antwort -- Analogie zu AC-6). Dieselbe
    # Bestandsentscheidung wie bei den bereits gelisteten Query-Kommandos:
    # Reparatur-Vorrat (B18), keine Ausnahme in INTENTIONAL_CONSTANT_SUCCESS
    # (die bleibt strukturell auf den einen Webhook-Fall beschraenkt, AC-14).
    "src/services/trip_command_processor.py::_show_strecke::0": (
        "B18 (#1405, Analogie) — _show_strecke: alle Folgepunkte ausgefallen "
        "(AC-7), nach der Fail-soft-Nowcast-Schleife."
    ),
    "src/services/trip_command_processor.py::_show_strecke::1": (
        "B18 (#1405, Analogie) — _show_strecke: kein Regen erkannt (AC-19), "
        "nach derive_rain_zones(...)."
    ),
    "src/services/trip_command_processor.py::_show_strecke::2": (
        "B18 (#1405, Analogie) — _show_strecke: Zonen gebildet (Normalfall), "
        "nach _fmt_strecke_email(...)/_fmt_strecke_telegram(...)."
    ),
    # --- B17 + der eine neue Fundort: beide zählen ohne Gegenzähler.
    "src/services/trip_report_scheduler.py::send_reports::0": (
        "B17 (#1405) — send_reports: sent_count ohne Gegenzähler, return int."
    ),
    "src/services/trip_report_scheduler.py::_process_pending_markers::0": (
        "NEU (#1405, beim Bau des Wächters nachgelesen) — "
        "_process_pending_markers: delivered += 1 nur bei outcome == 'sent', "
        "kein Gegenzähler, return delivered. Der Wert fließt in "
        "dispatch_orchestrator.pre_pass direkt in den sent-Tally — eine "
        "gescheiterte Nachlieferung ist dort von einer nicht fälligen nicht "
        "zu unterscheiden. Gleiche Mechanik wie B17."
    ),
}


# ---------------------------------------------------------------------------
# Ausnahmeliste: bewusst erlaubte konstante Erfolgswerte.
# Semantisch umgekehrt zu KNOWN_VIOLATIONS — ein Eintrag hier bedeutet
# "bewusst erlaubt", nicht "Reparatur ausstehend". Ein Fund auf dieser Liste
# macht die Ratsche NICHT rot; ein Eintrag ohne nichtleere Begründung dagegen
# schon (AC-14).
#
# Genau EIN Eintrag, und der Scanner meldet die Stelle tatsächlich (AC-14
# prüft beides): `telegram_webhook` ist strukturell ein Klasse-1-Fund —
# `_reader._process_update(update, settings)` steht als unzugewiesener Aufruf
# im try, der Handler protokolliert nur, danach folgt ein festes
# {"status": "ok"}. Fachlich ist das trotzdem richtig: die 200-Antwort ist
# eine Protokoll-Empfangsbestätigung an Telegram, kein Erfolgsbericht über die
# Verarbeitung — ohne sie liefe Telegram in einen Retry-Sturm.
#
# `api/routers/health.py` braucht KEINEN Eintrag — dort trifft die
# Klasse-1-Signatur strukturell gar nicht zu (keine vorgelagerte riskante
# Operation, s. AC-16). Eine Lebendmeldung auf eine Ausnahmeliste zu setzen
# wäre die Umkehrung des Wächters: er soll erklären können, warum er NICHT
# anschlägt, statt Ausnahmen zu sammeln.
# ---------------------------------------------------------------------------
INTENTIONAL_CONSTANT_SUCCESS: dict[str, str] = {
    _WEBHOOK_ACK_LOCATION: _WEBHOOK_ACK_JUSTIFICATION,
}


# ---------------------------------------------------------------------------
# AC-1: die 22 in der Spec namentlich gelisteten Fundstellen B1–B21 (B13 mit
# #1407, B2 mit #1447 entfernt — s. u.), als "pfad::funktion" →
# MINDEST-TREFFERZAHL — bewusst OHNE Zeilennummern, damit spätere
# Codeverschiebungen sie nicht brechen.
#
# 36 Funktionsschlüssel für 22 Ticket-Fundstellen, Summe der Mindest-Treffer
# = 43 (33×1 + 2×3 + 1×4). Die Zahlen weichen auseinander, weil ein
# Ticket-Punkt mehrere Funktionen und eine Funktion mehrere Treffer haben
# kann:
#
#   * B14a/B14b/B14c sind ticket-seitig EIN Punkt (der aus Hälfte A
#     übernommene #684-Fall), fallen beim Scan aber auf FÜNF Funktionen —
#     B14a und B14c als Klasse 1c mit je drei Kanal-Vorkommen
#     (`send_official_alert` Z. 660/672/694, `_dispatch_alert_message`
#     Z. 1066/1082/1103), B14b auf die drei Klasse-4-Helfer mit je einem.
#   * B18 ist EIN Ticket-Punkt (dateiweites Muster in
#     `trip_command_processor.py`), aber ZEHN Funktionsschlüssel mit 13
#     Treffern — `_handle_query` allein trägt vier davon (vier unabhängige
#     `return CommandResult(success=True, ...)`-Zweige, Z. 470/479/487/496).
#   * B21 ist EIN gebündelter Ticket-Punkt mit drei Funktionsschlüsseln.
#
# Gezählt wird, nicht bloß auf Anwesenheit geprüft. Ohne Zählung bliebe ein
# Scanner grün, der in `_dispatch_alert_message` nur den E-Mail-Kanal sieht
# und Telegram und SMS verliert — oder der in `_handle_query` nur den ersten
# von vier Zweigen meldet.
#
# Rechnung gegenüber Version 1.1 (23 Schlüssel, Summe 27):
#   +10 Schlüssel / +13 Treffer (B18, dateiweites Muster)
#   + 2 Schlüssel / + 2 Treffer (B19/B20, die beiden Inbound-Reader)
#   + 3 Schlüssel / + 3 Treffer (B21, Klasse 4 im Versandkontext)
#   = +15 Schlüssel / +18 Treffer  ->  38 Schlüssel, Summe 45.
#
# #1407: B13 (toter Compare-Heartbeat) repariert durch Löschen statt
# Anschließen — ein hier zulässiger Fall, in dem eine Fundstelle ohne neue
# Spec-Version verschwindet (s. u., "Einzige zugelassene Änderung").
#   - 1 Schlüssel / - 1 Treffer (B13)  ->  37 Schlüssel, Summe 44.
#
# #1447 (S1): B2 (trigger_alert_checks) repariert — der Status wird jetzt aus
# AlertCheckRunResult.hit_deadline abgeleitet statt fest auf "ok" gesetzt.
# Zweiter zulässiger Fall derselben Mechanik wie B13.
#   - 1 Schlüssel / - 1 Treffer (B2)  ->  36 Schlüssel, Summe 43.
#
# ACHTUNG: Diese Liste stammt wörtlich aus der Spec
# (docs/specs/modules/waechter_1405_erfolg_wirkung.md Version 1.2, Tabelle
# "Mindest-Trefferzahlen für AC-1") und ist die UNABHÄNGIGE Erwartung an die
# Trefferkraft des Scanners. Sie darf NICHT aus KNOWN_VIOLATIONS abgeleitet
# werden — sonst prüfte der Wächter sich selbst. Schlägt AC-1 fehl, ist der
# Scanner zu eng gebaut: die Liste wird zur Behebung NIEMALS gekürzt und keine
# Mindestzahl herabgesetzt (Test-Politik: Schwellen nie anpassen, damit etwas
# grün wird). Nur eine reparierte Fundstelle darf hier verschwinden — dann
# zusammen mit ihrem KNOWN_VIOLATIONS-Eintrag. Einzige zugelassene Änderung an
# den Zahlen: die in der Spec unter "Offene Punkte" 2 vorgesehene Korrektur
# der 3er-Erwartung für notification_service.py — und die wird IN DER SPEC
# beschlossen und dort nachgezogen, nicht still hier.
# ---------------------------------------------------------------------------
SPEC_LISTED_FINDINGS: dict[str, int] = {
    # B1 — der #1403-Fall: "no_channels" fällt durch bis "sent": True
    "api/routers/scheduler.py::send_test_trip_report": 1,
    # B2 entfernt (#1447 S1) — trigger_alert_checks leitet den Status jetzt
    # aus AlertCheckRunResult.hit_deadline ab, der Scanner findet dort nichts
    # mehr.
    # B3 — dito (Compare-Deviation)
    "api/routers/scheduler.py::trigger_compare_alert_checks": 1,
    # B4 — dito (Radar)
    "api/routers/scheduler.py::trigger_radar_alert_checks": 1,
    # B5 — dito (Compare-Radar)
    "api/routers/scheduler.py::trigger_compare_radar_alert_checks": 1,
    # B6 — dito (Compare-Amtlich)
    "api/routers/scheduler.py::trigger_compare_official_alert_checks": 1,
    # B7 — dito (Inbound E-Mail)
    "api/routers/scheduler.py::trigger_inbound": 1,
    # B8 — dito, Feld heißt "processed" (Inbound Telegram)
    "api/routers/scheduler.py::trigger_inbound_telegram": 1,
    # B9 — try/except je Trip, nur alerts_sent hoch, return int
    "src/services/trip_alert.py::check_all_trips": 1,
    # B10 — analoges Muster im Radar-Pfad, return sent (int)
    "src/services/trip_alert.py::check_radar_alerts": 1,
    # B11 — try/except je Ort, nur sent gezählt
    "src/services/compare_alert.py::check_all_compare_presets": 1,
    # B11b — gleiches Muster, Nowcast-Fehler je Ort nur im logger.error
    "src/services/compare_radar_alert.py::check_all_compare_presets": 1,
    # B11c — sum(1 for ... if ...) ohne jeden Fehlerzähler und ohne try/except
    "src/services/compare_official_alert.py::check_all_compare_presets": 1,
    # B12 — top_ort/actual_empfaenger zugewiesen, "status" trotzdem festes "ok"
    "src/services/scheduler_dispatch_service.py::send_compare_preset": 1,
    # B13 entfernt (#1407) — toter Compare-Heartbeat wurde geloescht statt
    # angeschlossen, der Scanner findet dort nichts mehr.
    # B14a — sent_channels.append() vor dem try, jetzt VIER Kanäle
    # (email/telegram/sms/premium_sms). Issue #1701 (S2b, D7): von 3 auf 4
    # angehoben, NICHT die Buchung hinter den `try` verschoben — die Spec
    # trifft diese Entscheidung ausdrücklich (Nachzugpflicht dieses
    # Kommentars).
    "src/services/notification_service.py::send_official_alert": 4,
    # B14c — dito, jetzt VIER Kanäle; genutzt von Änderungs-, Radar- und
    # amtlichen Alarmen. Issue #1701 (S2b, D7).
    "src/services/notification_service.py::_dispatch_alert_message": 4,
    # B14b entfernt (#1459, 2026-08-02) — die drei Helfer
    # _dispatch_compare_official_{email,telegram,sms} liefern jetzt `bool`, und
    # send_compare_official_alert() WERTET den Rueckgabewert aus (fuellt daraus
    # `failed_channels` fuer das Alarm-Protokoll). Vorher wurde das `False`
    # weggeworfen: ein gescheiterter Ortsvergleich-Versand galt als Erfolg —
    # genau der Mangel, den diese drei Eintraege gefuehrt haben. Der Scanner
    # findet dort nichts mehr, die Ratsche ist entsprechend kleiner.
    # B15 — send_test_report() unzugewiesen, danach bedingungslos success=True
    "src/services/trip_command_processor.py::_trigger_report": 1,
    # B16 — outcome geprüft, Text variiert korrekt, success=True aber nicht
    "src/services/trip_command_processor.py::_trigger_on_demand": 1,
    # B17 — toter Code, sent_count ohne Gegenzähler, return int
    "src/services/trip_report_scheduler.py::send_reports": 1,
    # --- B18 (NEU Version 1.2, E3): dateiweites Muster in ----------------
    # trip_command_processor.py. Zehn Funktionsschlüssel, 13 Treffer,
    # dieselbe Mechanik wie B15/B16 — ein abgeleiteter oder unzugewiesener
    # Aufruf, danach ein hartkodiertes success=True im
    # CommandResult-Konstruktor, das den abgeleiteten Wert nicht
    # referenziert. Reparatur (S4) sinnvollerweise am Stück: EINE
    # Entscheidung darüber, was CommandResult.success bedeuten soll
    # (Antwort erfolgreich verfasst vs. zugrundeliegende Aktion erfolgreich).
    # B18 — vier unabhängige Zweige (glance / heute_gewitter /
    # timeline_heute / timeline_morgen), je nach einem Renderer-Aufruf
    # (self._fmt_glance/_fmt_gewitter/_fmt_timeline). VIER Treffer: ein
    # Scanner, der die def-Zeile als Schlüssel nimmt, ließe alle vier auf
    # einen Eintrag zusammenfallen und käme hier nie über 1.
    "src/services/trip_command_processor.py::_handle_query": 4,
    # B18 — res = WeatherExtractor(user_id).drilldown(...)
    "src/services/trip_command_processor.py::_handle_drilldown": 1,
    # B18 — r_temp = ex.drilldown(...) (plus drei weitere Ableitungen)
    "src/services/trip_command_processor.py::_handle_hours_drilldown": 1,
    # B18 — save_trip(new_trip, user_id) unzugewiesen
    "src/services/trip_command_processor.py::_apply_ruhetag": 1,
    # B18 — today = date.today(): trivialer Aufruf, matcht trotzdem
    # (Signatur ist syntaktisch, nicht risikobewusst — Spec "Offene
    # Punkte" 3; Arbeitsvorrat statt Vorab-Filterung)
    "src/services/trip_command_processor.py::_show_status": 1,
    # B18 — save_trip(new_trip, user_id) unzugewiesen
    "src/services/trip_command_processor.py::_apply_pause": 1,
    # B18 — dito
    "src/services/trip_command_processor.py::_apply_skip": 1,
    # B18 — result = svc.get_nowcast(...), body = svc.format_now_text(...)
    "src/services/trip_command_processor.py::_show_now": 1,
    # B18 — save_trip(new_trip, user_id), bedingt und unzugewiesen
    "src/services/trip_command_processor.py::_cancel_trip": 1,
    # B18 — dito
    "src/services/trip_command_processor.py::_resume_trip": 1,
    # --- B19/B20 (NEU Version 1.2, E4): die beiden Inbound-Reader --------
    # In Version 1.1 fälschlich als "kein Fund, bereits erfolgsbereinigt"
    # geführt. "processed zählt nur tatsächlich Verarbeitetes" ist fachlich
    # richtig, aber KEIN strukturelles Ausschlusskriterium für Klasse 2 —
    # beiden fehlt der Gegenzähler für den Fehlerfall (AC-18).
    # B19 — for uid in uids: processed += self._process_single(...),
    # except Exception: logger.error(...), return processed
    "src/services/inbound_email_reader.py::poll_and_process": 1,
    # B20 — identisches Muster über self._process_update(...)
    "src/services/inbound_telegram_reader.py::poll_and_process": 1,
    # --- B21 (NEU Version 1.2): Klasse 4 im Versandkontext ---------------
    # Bei der Verifikation der E2-Einschränkung gefunden: strukturell nicht
    # von B14b zu unterscheiden (try/except, Logger-only-Handler, kein
    # return mit Wert, Kanal-Ausgabeaufruf im eigenen Rumpf). SECHS statt
    # der erwarteten drei Klasse-4-Treffer — aufgenommen statt durch eine
    # Verengung zur Zahlenkosmetik wegdefiniert.
    # B21 — ruft TelegramOutput(...).send(...), keine Rückmeldung an
    # send_trip_report
    "src/services/notification_service.py::_send_telegram_incomplete_hint": 1,
    # B21 — ruft EmailOutput(...).send(...), keine Rückmeldung an den
    # Inbound-Reader
    "src/services/notification_service.py::send_command_reply_email": 1,
    # B21 — ruft EmailOutput(...).send(...) nach einem is_sms_only-Vorspann
    # mit nacktem return (zählt nach S-9 NICHT als Rückmeldung)
    "src/services/notification_service.py::_send_service_error_email": 1,
}


# ---------------------------------------------------------------------------
# AC-1 bis AC-3: Bestandsaufnahme und Ratschen
# ---------------------------------------------------------------------------


def test_scanner_finds_every_spec_listed_finding():
    """AC-1 (+ AC-17 und AC-18): GIVEN die 22 in der Spec gelisteten
    Fundstellen B1–B21 (B13 mit #1407, B2 mit #1447 entfernt)
    WHEN der Wächter über die Scanfläche läuft
    THEN schlägt er in JEDER der 33 zugehörigen Funktionen mindestens so oft
    an wie in der Mindestzahl-Tabelle festgelegt (30 Funktionen mit 1, 2
    Funktionen mit 4, 1 Funktion mit 4), Summe 42.

    Issue #1701 (S2b, D7): der vierte Versandkanal Premium-SMS hebt die
    beiden Kanal-Vorkommen in ``send_official_alert`` und
    ``_dispatch_alert_message`` von je drei auf je vier Treffer an (die
    Spec-Nachzugpflicht aus Version 1.2 dieses Dokuments) — Summe damit 42
    statt 40, Funktionsschlüssel-Zahl unverändert 33.

    Gemessen an SPEC_LISTED_FINDINGS — einer fest verdrahteten Erwartung aus
    der Spec (``pfad::funktion`` → Mindest-Trefferzahl), NICHT aus
    KNOWN_VIOLATIONS abgeleitet (AC-1 und AC-3 dürfen nicht dieselbe Quelle
    benutzen, sonst prüft der Wächter sich selbst). Gezählt wird im ROHEN
    Scan-Ergebnis, wo der Zeilenbezug noch vorhanden ist: die vier
    Kanal-Vorkommen in ``send_official_alert`` und ``_dispatch_alert_message``
    sind je vier Treffer, die vier Zweige in ``_handle_query`` je vier — eine
    reine Mengenprüfung bliebe grün, wenn der Scanner davon welche verlöre.

    **AC-17 (B18, dateiweites Muster) und AC-18 (B19/B20, Inbound-Reader)
    sind laut Spec Teil dieser Prüfung**, bekommen hier aber je einen eigenen
    Nachweisblock mit eigener Fehlermeldung. Grund: beide sind Zuwächse aus
    Spec-Version 1.2 und würden in der Gesamtsumme untergehen — fiele B18
    komplett aus, meldete die Sammel-Zusicherung nur „13 von 45 fehlen" und
    nicht, dass ein ganzes Muster nicht erkannt wird.

    Fehlt ein Treffer, ist der Scanner zu eng gebaut — die Erwartung wird zur
    Behebung NICHT gekürzt.
    """
    # Zuerst die Erwartung selbst prüfen — bewusst VOR dem Scan-Lauf: eine
    # gekürzte Tabelle würde sonst hinter einem grünen Scan verschwinden,
    # und genau das ist der Weg, auf dem Wächter still ihre Schärfe
    # verlieren (Test-Politik: Schwellen nie anpassen, damit etwas grün wird).
    assert len(SPEC_LISTED_FINDINGS) == 33 and sum(SPEC_LISTED_FINDINGS.values()) == 42, (
        "SPEC_LISTED_FINDINGS weicht von der Spec-Tabelle ab (erwartet 33 "
        "Funktionsschlüssel, Summe 42 — Version 1.2 minus B13, #1407, minus "
        "B2, #1447, minus B14b (drei Schlüssel), #1459, plus zweimal +1 fuer "
        "den vierten Kanal Premium-SMS, #1701 D7). Ist: "
        f"{len(SPEC_LISTED_FINDINGS)} Schlüssel, Summe "
        f"{sum(SPEC_LISTED_FINDINGS.values())}"
    )

    found = _all_violations()
    hit_counts = _finding_location_counts(found)

    missing = sorted(
        f"{location} (erwartet >={expected}, gefunden {hit_counts.get(location, 0)})"
        for location, expected in SPEC_LISTED_FINDINGS.items()
        if hit_counts.get(location, 0) < expected
    )
    assert not missing, (
        "Der Wächter erkennt diese in der Spec belegten Fundstellen NICHT "
        "(oder nicht oft genug) — die Signatur ist zu eng gebaut (Issue "
        "#1405, Tabelle B1–B21). Die Erwartung NICHT kürzen, sondern den "
        f"Scanner erweitern. Code reference: {missing}"
    )

    # --- AC-17: B18, das dateiweite Muster in trip_command_processor.py ---
    b18_prefix = "src/services/trip_command_processor.py::"
    b18_expected = {
        location: expected
        for location, expected in SPEC_LISTED_FINDINGS.items()
        if location.startswith(b18_prefix)
        and not location.endswith(("::_trigger_report", "::_trigger_on_demand"))
    }
    b18_missing = sorted(
        f"{location} (erwartet >={expected}, gefunden {hit_counts.get(location, 0)})"
        for location, expected in b18_expected.items()
        if hit_counts.get(location, 0) < expected
    )
    assert not b18_missing, (
        "AC-17: das dateiweite B18-Muster in trip_command_processor.py wird "
        "nicht vollständig erkannt — zehn Funktionen mit zusammen 13 "
        "Treffern, davon vier allein in _handle_query. Häufigste Ursache: "
        "der Detektor nimmt die def-Zeile als Fund-Schlüssel, dann fallen "
        "die vier _handle_query-Zweige auf einen Eintrag zusammen. Zweite "
        "Ursache: Schlüsselwortargumente eines Konstruktors "
        "(CommandResult(success=True, ...)) werden nicht wie Dict-Schlüssel "
        f"behandelt (S-8). Code reference: {b18_missing}"
    )

    # --- AC-18: B19/B20, die beiden Inbound-Reader als Klasse-2-Fund ------
    inbound_expected = [
        "src/services/inbound_email_reader.py::poll_and_process",
        "src/services/inbound_telegram_reader.py::poll_and_process",
    ]
    inbound_missing = sorted(
        location for location in inbound_expected if hit_counts.get(location, 0) < 1
    )
    assert not inbound_missing, (
        "AC-18: die beiden Inbound-Reader werden nicht als Klasse-2-Fund "
        "erkannt. Sie waren in Spec-Version 1.1 fälschlich als 'kein Fund' "
        "geführt — 'processed zählt nur tatsächlich Verarbeitetes' ist "
        "fachlich richtig, aber kein strukturelles Ausschlusskriterium: "
        "beiden fehlt der Gegenzähler für den Fehlerfall, der except-Zweig "
        f"ruft nur logger.error(...). Code reference: {inbound_missing}"
    )


def test_no_unlisted_success_status_findings():
    """AC-2: GIVEN ein neuer Fund mit einer der vier Signaturen (konstanter
    Erfolgswert aus einem Aufruf, Erfolgsmarker vor dem Versand,
    teilerfolg-blinde Zählung, unverdrahteter Heartbeat, Aufruf ohne
    Rückmeldung) irgendwo in der Scanfläche
    WHEN der Wächter läuft
    THEN schlägt er fehl und benennt Datei:Zeile — die Restliste kann nicht
    stillschweigend wachsen.

    Einträge aus INTENTIONAL_CONSTANT_SUCCESS zählen hier ausdrücklich nicht
    als Fund (AC-14): sie sind bewusst erlaubt und tragen eine geprüfte
    Begründung.

    Der Nachweis, dass der Scanner die Muster wirklich strukturell erkennt
    (statt zufällig zur Restliste zu passen), sind die synthetischen
    Wirkungsnachweise AC-4 bis AC-13.
    """
    found = _all_violations()
    unlisted = {
        location: kind
        for location, kind in found.items()
        if location not in KNOWN_VIOLATIONS
        and location not in INTENTIONAL_CONSTANT_SUCCESS
    }
    assert not unlisted, (
        "Neue unverdiente Erfolgsmeldungen entdeckt (Issue #1405): ein "
        "ok/sent/success wird gemeldet, ohne aus dem tatsächlichen Ergebnis "
        "abgeleitet zu sein. Beheben nach dem Referenzmuster "
        "run_briefing_dispatch() ((sent, failed)-Tupel aus einer "
        "fehler-isolierten Schleife, Status rein aus failed > 0) — oder, "
        "falls fachlich berechtigt, mit Begründung in "
        "INTENTIONAL_CONSTANT_SUCCESS eintragen. Code reference: "
        f"{sorted(unlisted.items())}"
    )


def test_known_violations_only_shrink():
    """AC-3: Die Restliste ist Übergangs-Buchhaltung für die Reparatur-Scheibe
    S4 und darf nur kleiner werden. Sobald eine gelistete Stelle behoben ist
    (der Scanner sie nicht mehr findet), MUSS der Eintrag entfernt werden —
    sonst bliebe die Liste eine Dauereinrichtung statt eines
    Fortschrittsnachweises."""
    found = _all_violations()
    stale = sorted(location for location in KNOWN_VIOLATIONS if location not in found)
    assert not stale, (
        "Diese Stellen sind inzwischen behoben (Scanner findet sie nicht "
        "mehr) — aus KNOWN_VIOLATIONS entfernen, die Liste darf nur "
        f"schrumpfen. Code reference: {stale}"
    )


# ---------------------------------------------------------------------------
# AC-4 bis AC-6: Wirkungsnachweise Klasse 1 und 1c
# ---------------------------------------------------------------------------


def test_scanner_detects_constant_success_from_call_in_synthetic_file(tmp_path):
    """AC-4: Wirkungsnachweis für das Bugmuster selbst — eine Variable wird aus
    einem Aufruf abgeleitet (bzw. ein Aufruf bleibt ganz unzugewiesen), und
    das Rückgabe-Dict trägt trotzdem ein festes ``"status": "ok"`` /
    ``"sent": True``, das diese Variable nicht referenziert.

    **Erste Form — abgeleitete Variable, die im Status nicht vorkommt.**
    Nachbau von ``api/routers/scheduler.py:217`` (``send_test_trip_report``,
    der #1403-Fall): ``send_test_report_outcome()`` liefert ein
    aussagekräftiges Outcome, der Router prüft zwei Werte davon und meldet
    für alles Übrige ``sent: True``. Der Nutzer sieht „Testmail verschickt",
    obwohl kein Kanal konfiguriert war und nie etwas losgeschickt wurde.
    Ausdrücklich NICHT geprüft wird, ob die Werteliste vollständig ist — das
    stünde im Rumpf der aufgerufenen Funktion (s. Modul-Docstring, „Bekannte
    Grenzen"). Geprüft wird nur: der Status hängt am Ende nicht an ``outcome``.

    **Zweite Form — Aufruf ohne jede Zuweisung.** Nachbau von
    ``src/services/trip_command_processor.py:888`` (``_trigger_report``, B15)
    und ``scheduler_dispatch_service.py:443`` (B12): das Ergebnis wird nicht
    einmal entgegengenommen, der Erfolg ist trotzdem gebucht. Die zweite Form
    zeigt zugleich, dass das Rückgabe-Objekt kein Dict sein muss — ein
    Ergebnisobjekt mit ``success=True`` als Schlüsselwortargument ist
    dieselbe Behauptung (S-8, Spec Version 1.2). Ohne diese Gleichstellung
    wären B12, B15, B16 und das gesamte B18-Muster unerreichbar.

    **Dritte Form (NEU Version 1.2) — mehrere Zweige, mehrere Treffer.**
    Nachbau von ``trip_command_processor.py::_handle_query`` (B18): VIER
    unabhängige ``return CommandResult(success=True, ...)``-Zweige nach je
    einer Ableitung aus einem Renderer-Aufruf. Erwartet werden VIER Treffer
    in dieser einen Funktion. Das ist der Wirkungsnachweis für die
    Fundzeilen-Regel: Schlüssel ist die Zeile des jeweiligen ``return``,
    nicht die der ``def``-Anweisung. Ein Detektor, der die ``def``-Zeile
    nimmt, ließe alle vier auf EINEN Dict-Eintrag zusammenfallen — AC-1 und
    AC-17 wären damit strukturell unerfüllbar, und niemand sähe es, weil die
    Funktion ja „gefunden" wäre.

    Unterscheidungspunkt zu AC-5: die ``except``-Handler hier liefern KEINEN
    abweichenden Rückgabewert (der erste wirft weiter, die übrigen
    existieren nicht). Bei ``channel_test_service`` liefert der Handler
    dagegen ``{"error": ...}`` und macht die Meldung damit ehrlich.

    Wird das nicht erkannt, ist der Wächter ein zahnloses Bestandsprotokoll.
    """
    derived_file = tmp_path / "synthetic_constant_success_derived.py"
    derived_file.write_text(
        "from fastapi import HTTPException\n"
        "\n"
        "from services.trip_report_scheduler import TripReportSchedulerService\n"
        "\n"
        "\n"
        "def send_test_trip_report(trip_id, user_id='default', report_type='evening'):\n"
        "    service = TripReportSchedulerService(user_id=user_id)\n"
        "    try:\n"
        "        outcome = service.send_test_report_outcome(trip_id, report_type)\n"
        "    except ValueError as e:\n"
        "        raise HTTPException(status_code=422, detail=str(e))\n"
        "    if outcome == 'no_stage':\n"
        "        raise HTTPException(status_code=422, detail='Keine Etappendaten')\n"
        "    if outcome == 'no_weather':\n"
        "        raise HTTPException(status_code=422, detail='Keine Wetterdaten')\n"
        "    return {'status': 'ok', 'trip_id': trip_id, 'sent': True}\n",
        encoding="utf-8",
    )
    found = _find_violations(derived_file)
    locations = _finding_locations(found)
    assert any(loc.endswith("::send_test_trip_report") for loc in locations), (
        "Scanner hat die konstante Erfolgsmeldung neben einer abgeleiteten "
        f"Variablen nicht erkannt (Klasse 1, Nachbau des #1403-Falls): {found}"
    )
    assert all(
        kind.startswith(KIND_CONSTANT_SUCCESS) for kind in found.values()
    ), f"Unerwartete Fund-Art gemeldet: {found}"

    unassigned_file = tmp_path / "synthetic_constant_success_unassigned.py"
    unassigned_file.write_text(
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CommandResult:\n"
        "    success: bool\n"
        "    command: str\n"
        "    confirmation_body: str\n"
        "\n"
        "\n"
        "def _trigger_report(trip, report_type, user_id):\n"
        "    from services.trip_report_scheduler import TripReportSchedulerService\n"
        "\n"
        "    service = TripReportSchedulerService(user_id=user_id)\n"
        "    service.send_test_report(trip, report_type)\n"
        "    return CommandResult(\n"
        "        success=True,\n"
        "        command='report',\n"
        "        confirmation_body=f'{report_type} Report wird jetzt gesendet.',\n"
        "    )\n",
        encoding="utf-8",
    )
    unassigned_found = _find_violations(unassigned_file)
    unassigned_locations = _finding_locations(unassigned_found)
    assert any(loc.endswith("::_trigger_report") for loc in unassigned_locations), (
        "Scanner hat den unzugewiesenen Aufruf mit festem success=True nicht "
        "erkannt (Klasse 1, Nachbau von B15/trip_command_processor.py:888) — "
        "ohne diese Form fielen B12, B15 und der Webhook-Ack durch das Raster: "
        f"{unassigned_found}"
    )
    assert all(
        kind.startswith(KIND_CONSTANT_SUCCESS) for kind in unassigned_found.values()
    ), f"Unerwartete Fund-Art gemeldet: {unassigned_found}"

    multi_branch_file = tmp_path / "synthetic_constant_success_multi_branch.py"
    multi_branch_file.write_text(
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CommandResult:\n"
        "    success: bool\n"
        "    command: str\n"
        "    confirmation_subject: str\n"
        "    confirmation_body: str\n"
        "\n"
        "\n"
        "class TripCommandProcessor:\n"
        "    def _handle_query(self, trip, query_key, received_at, user_id):\n"
        "        '''Dispatch read-only query. Never mutates trip state.'''\n"
        "        from services.weather_extractor import WeatherExtractor\n"
        "\n"
        "        today = received_at.date()\n"
        "        extractor = WeatherExtractor(user_id=user_id)\n"
        "        timeline = extractor.timeline(trip.id)\n"
        "\n"
        "        if query_key == 'glance':\n"
        "            body = self._fmt_glance(timeline, today)\n"
        "            return CommandResult(\n"
        "                success=True, command='glance',\n"
        "                confirmation_subject=f'[{trip.name}] Glance',\n"
        "                confirmation_body=body,\n"
        "            )\n"
        "        elif query_key == 'heute_gewitter':\n"
        "            body = self._fmt_gewitter(timeline, today)\n"
        "            return CommandResult(\n"
        "                success=True, command='heute_gewitter',\n"
        "                confirmation_subject=f'[{trip.name}] Gewitter heute',\n"
        "                confirmation_body=body,\n"
        "            )\n"
        "        elif query_key == 'timeline_heute':\n"
        "            body = self._fmt_timeline(timeline, today, 'Heute')\n"
        "            return CommandResult(\n"
        "                success=True, command='timeline_heute',\n"
        "                confirmation_subject=f'[{trip.name}] Timeline heute',\n"
        "                confirmation_body=body,\n"
        "            )\n"
        "        elif query_key == 'timeline_morgen':\n"
        "            body = self._fmt_timeline(timeline, today, 'Morgen')\n"
        "            return CommandResult(\n"
        "                success=True, command='timeline_morgen',\n"
        "                confirmation_subject=f'[{trip.name}] Timeline morgen',\n"
        "                confirmation_body=body,\n"
        "            )\n"
        "        return CommandResult(\n"
        "            success=False, command=query_key,\n"
        "            confirmation_subject='Unbekannt',\n"
        "            confirmation_body='Unbekannte Abfrage.',\n"
        "        )\n",
        encoding="utf-8",
    )
    multi_found = _find_violations(multi_branch_file)
    multi_counts = _finding_location_counts(multi_found)
    multi_hits = sum(
        count
        for location, count in multi_counts.items()
        if location.endswith("::_handle_query")
    )
    assert multi_hits >= 4, (
        "Scanner meldet für die vier unabhängigen success=True-Zweige nur "
        f"{multi_hits} Treffer (erwartet >=4). Nachbau von B18/"
        "_handle_query: der Fund-Schlüssel MUSS die Zeile des jeweiligen "
        "return tragen, nicht die der def-Anweisung — sonst fallen alle vier "
        "auf einen Dict-Eintrag zusammen und AC-1/AC-17 sind strukturell "
        f"unerfüllbar. Fundliste: {multi_found}"
    )
    assert all(
        kind.startswith(KIND_CONSTANT_SUCCESS) for kind in multi_found.values()
    ), f"Unerwartete Fund-Art gemeldet: {multi_found}"


def test_scanner_ignores_diverging_except_return_in_synthetic_file(tmp_path):
    """AC-5: Gegenprobe „except divergiert" — ein ``except``-Handler, der
    selbst ein ``return`` mit einem ANDEREN Wert liefert, koppelt den Status
    doch an den Ausgang. Kein Fund.

    Zwei belegte Bauformen aus dem eigenen Bestand:

    1. ``channel_test_service.send_test_message`` (Z. 12-45): ``{"status":
       "ok"}`` (Z. 42) wird nur erreicht, wenn ``output.send()`` ohne
       Ausnahme durchgelaufen ist; der Handler liefert ``{"error": str(exc)}``
       (Z. 43f.).
    2. ``ForecastBudgetGate.snapshot`` (Z. 87-113): ``"status": "ok"``
       (Z. 102) im ``try``, ``"status": "unavailable"`` (Z. 112) im
       ``except``. Identisch gebaut ist
       ``official_alerts/meteoalarm_budget.py`` (Z. 143/152).

    Das ist die härteste Anforderung an Klasse 1: das bloße Vorkommen eines
    Erfolgs-Literals neben einem Aufruf genügt nicht. Ein Scanner, der hier
    anschlägt, meldet drei korrekt gebaute Positivbeispiele des eigenen
    Bestands als Verstoß und ist nie grün zu bekommen — dieselbe Falle wie
    die Referenz-Auflöser in Hälfte A (dortiges AC-5).

    Die zweite Bauform ist die schärfere Probe: dort steht das Erfolgs-Dict
    INNERHALB des ``try``, und beide Zweige liefern denselben Schlüssel mit
    unterschiedlichem Literal. Ein Detektor, der nur „Handler enthält
    irgendein return" prüft statt „Handler liefert einen anderen Wert",
    bestünde die erste Probe und fiele bei der zweiten durch.
    """
    channel_test_file = tmp_path / "synthetic_diverging_except_channel_test.py"
    channel_test_file.write_text(
        "from app.config import Settings\n"
        "\n"
        "\n"
        "def send_test_message(channel, user_id):\n"
        "    settings = Settings().with_user_profile(user_id).for_testing()\n"
        "    subject = 'Gregor 20 — Testmeldung'\n"
        "    body = 'Dein Kanal funktioniert!'\n"
        "    try:\n"
        "        if channel == 'email':\n"
        "            from output.channels.email import EmailOutput\n"
        "\n"
        "            output = EmailOutput(settings)\n"
        "            output.send(subject, body, html=False)\n"
        "        elif channel == 'telegram':\n"
        "            from output.channels.telegram import TelegramOutput\n"
        "\n"
        "            output = TelegramOutput(settings)\n"
        "            output.send(subject, body)\n"
        "        else:\n"
        "            return {'error': f'Unbekannter Kanal: {channel}'}\n"
        "        return {'status': 'ok'}\n"
        "    except Exception as exc:\n"
        "        return {'error': str(exc)}\n",
        encoding="utf-8",
    )
    found = _find_violations(channel_test_file)
    assert not found, (
        "Das Referenzmuster 'Handler liefert einen Fehlerwert zurück' wurde "
        f"fälschlich als konstante Erfolgsmeldung gezählt: {found}"
    )

    budget_gate_file = tmp_path / "synthetic_diverging_except_budget_gate.py"
    budget_gate_file.write_text(
        "PROVIDER = 'open-meteo'\n"
        "\n"
        "\n"
        "class ForecastBudgetGate:\n"
        "    DAILY_BUDGET = 8000\n"
        "\n"
        "    def snapshot(self) -> dict:\n"
        "        '''Fail-open: liefert Nullen mit status \"unavailable\" statt zu werfen.'''\n"
        "        try:\n"
        "            data = self._load_for_today()\n"
        "            calls = data['calls'].get(PROVIDER, 0)\n"
        "            ratio = calls / self.DAILY_BUDGET if self.DAILY_BUDGET else 0.0\n"
        "            return {\n"
        "                'date': data['date'],\n"
        "                'calls_today': calls,\n"
        "                'daily_budget': self.DAILY_BUDGET,\n"
        "                'usage_ratio': ratio,\n"
        "                'status': 'ok',\n"
        "            }\n"
        "        except Exception:\n"
        "            return {\n"
        "                'date': None,\n"
        "                'calls_today': 0,\n"
        "                'daily_budget': self.DAILY_BUDGET,\n"
        "                'usage_ratio': 0.0,\n"
        "                'status': 'unavailable',\n"
        "            }\n"
        "\n"
        "    def _load_for_today(self) -> dict:\n"
        "        return {'date': None, 'calls': {}}\n",
        encoding="utf-8",
    )
    budget_found = _find_violations(budget_gate_file)
    assert not budget_found, (
        "Das Fail-open-Referenzmuster (status 'ok' im try, 'unavailable' im "
        "except) wurde fälschlich als konstante Erfolgsmeldung gezählt — der "
        "Detektor prüft offenbar nur die Anwesenheit eines return im Handler, "
        f"nicht die Abweichung des Werts: {budget_found}"
    )


def test_scanner_detects_pre_try_success_marker_in_synthetic_file(tmp_path):
    """AC-6: Wirkungsnachweis für Klasse 1c — der Erfolgsmarker steht VOR der
    Tat. ``sent_channels.append("email")`` wird ausgeführt, bevor der Versand
    überhaupt versucht wurde, und der ``except``-Zweig nimmt den Eintrag nicht
    zurück; er protokolliert nur.

    Nachbau von ``src/services/notification_service.py:1066ff``
    (``_dispatch_alert_message``, Issue #684 AC-3, Anti-Pattern #656). Folge im
    Betrieb: ``NotificationResult.sent=True`` heißt „konfiguriert", nicht
    „zugestellt" — und die Doppelalarm-Sperre greift auch dann, wenn nichts
    angekommen ist. Der Nutzer bekommt keinen Alarm und keine zweite Chance.

    Erwartet werden DREI Treffer in dieser Funktion, einer je Kanal-Vorkommen:
    ein Scanner, der nur das erste ``append`` sieht, verlöre Telegram und SMS,
    und die 3er-Erwartung in SPEC_LISTED_FINDINGS wäre wertlos. Zeigt sich in
    GREEN, dass strukturell nur ein Treffer je Funktion erkennbar ist, wird
    die SPEC korrigiert (Spec „Offene Punkte" 2), NICHT diese Zahl.

    **Zweiter Teil — die Gegenprobe auf die Reihenfolge.** Dieselbe Bauform
    mit umgekehrter Reihenfolge (``append`` NACH dem riskanten Aufruf, im
    ``try``) darf KEIN Fund sein: bei einem Fehlschlag wird die Zeile nie
    erreicht, der Marker ist also verdient. So liegen ``send_trip_report``
    (Z. 308f.) und ``send_compare_report`` (Z. 765f.) im Bestand — die Spec
    nennt beide ausdrücklich als „belegt verschont". Ohne diese Gegenprobe
    wäre der Detektor ein reiner „gibt es hier append und try?"-Test und
    würde zwei korrekte Versandpfade anmeckern; er wäre dann nie grün zu
    bekommen, und die Unterscheidung, um die es fachlich geht, wäre gar nicht
    geprüft.
    """
    bad_file = tmp_path / "synthetic_pre_try_marker.py"
    bad_file.write_text(
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
        encoding="utf-8",
    )
    found = _find_violations(bad_file)
    counts = _finding_location_counts(found)
    hits = sum(
        count
        for location, count in counts.items()
        if location.endswith("::_dispatch_alert_message")
    )
    assert hits >= 3, (
        "Scanner hat die Erfolgsmarker-vor-der-Tat nicht (oder nicht "
        "vollständig) erkannt: erwartet sind drei Treffer (email/telegram/"
        f"sms), gefunden {hits}. Fundliste: {found}"
    )
    assert all(
        kind.startswith(KIND_PRE_TRY_SUCCESS_MARKER) for kind in found.values()
    ), f"Unerwartete Fund-Art gemeldet: {found}"

    good_file = tmp_path / "synthetic_post_send_marker.py"
    good_file.write_text(
        "import logging\n"
        "\n"
        "from output.channels.email import EmailOutput\n"
        "from output.channels.sms import SMSOutput\n"
        "from output.channels.telegram import TelegramOutput\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "def send_compare_report(settings, subject, html_body, sms_text, channels):\n"
        "    sent_channels = []\n"
        "\n"
        "    if 'email' in channels:\n"
        "        EmailOutput(settings).send(subject, html_body, mail_type='compare')\n"
        "        sent_channels.append('email')\n"
        "\n"
        "    if 'telegram' in channels and settings.can_send_telegram():\n"
        "        try:\n"
        "            TelegramOutput(settings).send(subject=subject, body=sms_text)\n"
        "            sent_channels.append('telegram')\n"
        "        except Exception as e:\n"
        "            logger.error('Compare telegram failed: %s', e)\n"
        "\n"
        "    if 'sms' in channels and settings.can_send_sms():\n"
        "        try:\n"
        "            SMSOutput(settings).send(subject='', body=sms_text)\n"
        "            sent_channels.append('sms')\n"
        "        except Exception as e:\n"
        "            logger.error('Compare SMS failed: %s', e)\n"
        "\n"
        "    return {'sent': bool(sent_channels), 'sent_channels': sent_channels}\n",
        encoding="utf-8",
    )
    good_found = _find_violations(good_file)
    assert not good_found, (
        "Der verdiente Erfolgsmarker (append NACH dem riskanten Aufruf, so in "
        "send_trip_report und send_compare_report) wurde als Fund gemeldet — "
        "der Detektor wertet die Reihenfolge nicht aus und wäre damit nie "
        f"grün zu bekommen. Fundliste: {good_found}"
    )


# ---------------------------------------------------------------------------
# AC-7 bis AC-9: Wirkungsnachweise Klasse 2 (teilerfolg-blind)
# ---------------------------------------------------------------------------


def test_scanner_detects_partial_success_blind_loop_in_synthetic_file(tmp_path):
    """AC-7: Wirkungsnachweis für Klasse 2 — eine Funktion zählt Erfolge aus
    einem undurchsichtigen Aufruf und führt keinen Gegenzähler. Fällt jeder
    einzelne Vorgang durch, meldet sie ``0`` — und ``0`` ist von einem
    ruhigen Tag ohne Alarme nicht zu unterscheiden.

    Dass beide Nachbauten hier einen bloßen Skalar zurückgeben, ist Zufall
    der Vorlage und ausdrücklich KEIN Erkennungsmerkmal: die Bedingung
    „bloßer Skalar" ist in Spec-Version 1.2 ersatzlos gestrichen (S-1), der
    Rückgabetyp spielt keine Rolle. Den Gegenbeweis führt AC-8 mit einer
    Tupel-Rückgabe.

    Zwei Bauformen, und die zweite ist der eigentliche Nachweis:

    1. **``for``-Schleife mit Fehler-Isolierung** — Nachbau von
       ``src/services/trip_alert.py:275`` (``check_all_trips``): die
       Isolierung ist da (die Schleife bricht nicht ab, richtig so), aber die
       zweite Hälfte der Hausnorm fehlt — der Fehler wird nur ins Log
       geschrieben, nie gezählt und nie nach oben gereicht.
    2. **``sum(genexp)`` ganz OHNE ``try/except``** — Nachbau von
       ``src/services/compare_official_alert.py:72`` (``B11c``). Das ist der
       Beleg für die Verallgemeinerung aus Spec-Version 1.1: die alte Fassung
       verlangte ``try/except`` im Schleifenrumpf und hätte diese Stelle
       verfehlt — 3 von 5 belegten Fundstellen wären durchgerutscht. Die
       Fehlerbehandlung liegt hier vollständig in ``_check_one_preset()``,
       außerhalb der scannenden Funktion; sichtbar ist nur, dass ein Erfolg
       gezählt und ein Fehlschlag nicht gezählt wird.

    Ein Detektor, der die zweite Form nicht erkennt, ist am Symptom gebaut
    (``try/except``) statt am Schaden (kein Gegenzähler).
    """
    loop_file = tmp_path / "synthetic_partial_blind_loop.py"
    loop_file.write_text(
        "import logging\n"
        "\n"
        "from app.loader import load_all_trips\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "class TripAlertService:\n"
        "    def __init__(self, user_id):\n"
        "        self._user_id = user_id\n"
        "\n"
        "    def check_all_trips(self):\n"
        "        alerts_sent = 0\n"
        "        for trip in load_all_trips(user_id=self._user_id):\n"
        "            cached = self._get_cached_weather(trip)\n"
        "            if not cached:\n"
        "                continue\n"
        "            try:\n"
        "                if self.check_and_send_alerts(trip, cached):\n"
        "                    alerts_sent += 1\n"
        "            except Exception as e:\n"
        "                logger.error(f'Alert check failed for trip {trip.id}: {e}')\n"
        "        return alerts_sent\n",
        encoding="utf-8",
    )
    found = _find_violations(loop_file)
    locations = _finding_locations(found)
    assert any(loc.endswith("::check_all_trips") for loc in locations), (
        "Scanner hat die teilerfolg-blinde Schleife nicht erkannt (Klasse 2, "
        f"Nachbau von trip_alert.check_all_trips): {found}"
    )
    assert all(
        kind.startswith(KIND_PARTIAL_SUCCESS_BLIND) for kind in found.values()
    ), f"Unerwartete Fund-Art gemeldet: {found}"

    genexp_file = tmp_path / "synthetic_partial_blind_genexp.py"
    genexp_file.write_text(
        "from app.loader import load_all_locations\n"
        "\n"
        "\n"
        "class CompareOfficialAlertService:\n"
        "    def __init__(self, user_id):\n"
        "        self._user_id = user_id\n"
        "\n"
        "    def check_all_compare_presets(self) -> int:\n"
        "        presets = self._load_presets()\n"
        "        if not presets:\n"
        "            return 0\n"
        "        all_locations = {loc.id: loc for loc in load_all_locations(user_id=self._user_id)}\n"
        "        return sum(1 for preset in presets if self._check_one_preset(preset, all_locations))\n",
        encoding="utf-8",
    )
    genexp_found = _find_violations(genexp_file)
    genexp_locations = _finding_locations(genexp_found)
    assert any(
        loc.endswith("::check_all_compare_presets") for loc in genexp_locations
    ), (
        "Scanner hat die teilerfolg-blinde sum(genexp)-Zählung OHNE try/except "
        "nicht erkannt (Klasse 2, Nachbau von B11c/compare_official_alert.py:"
        "72). Genau daran ist die alte 'try/except im Schleifenrumpf'-Fassung "
        f"gescheitert — sie traf nur 2 von 5 Stellen: {genexp_found}"
    )
    assert all(
        kind.startswith(KIND_PARTIAL_SUCCESS_BLIND) for kind in genexp_found.values()
    ), f"Unerwartete Fund-Art gemeldet: {genexp_found}"


def test_scanner_detects_tuple_shaped_decoy_without_real_failure_counter(tmp_path):
    """AC-8: die Attrappen-Gegenprobe — der wichtigste Test dieses Wächters.

    Diese Funktion trägt jedes äußere Merkmal der Hausnorm: sie initialisiert
    ``failed = 0``, sie leitet einen ``status`` aus ``failed > 0`` ab, sie
    protokolliert das Ergebnis, sie liefert ``(sent, failed)``. Sie erhöht
    ``failed`` nur nie. Jeder Lauf meldet ``failed=0`` und ``status="ok"`` —
    auch der, in dem alle 133 Presets scheitern (Prod-Journal 2026-07-16,
    Issue #1290).

    Eine Prüfung am Rückgabetyp (``tuple`` statt ``int``) wäre hier fälschlich
    grün — und damit wäre die ganze Klasse-2-Prüfung mit drei Zeilen Kosmetik
    auszuhebeln: ``failed = 0`` deklarieren, ins Tupel schreiben, fertig. Der
    Wächter MUSS auf den Datenfluss schauen: wird ``failed`` irgendwo in einem
    FEHLERZWEIG erhöht? Das Tupel ist da, der Gegenzähler nicht.

    **Spec-Version 1.2 (S-1) hat dafür eine Bedingung gestrichen.**
    Version 1.1 verlangte zusätzlich „gibt einen bloßen Skalar zurück" — und
    war damit mit sich selbst im Widerspruch: diese Attrappe gibt syntaktisch
    ``(sent, failed)`` zurück und wäre an der UND-Verknüpfung gescheitert,
    BEVOR die Gegenzähler-Prüfung überhaupt griffe. Der Test hier wäre in
    keiner Implementierung grün zu bekommen gewesen, die sich an die Spec
    hält. Seit Version 1.2 trägt die Gegenzähler-Bedingung den Fall allein —
    GREEN darf den Rückgabetyp nicht wieder einführen, auch nicht „als
    zusätzliches Indiz".

    Scheitert dieser Test in GREEN, ist der Detektor am Symptom gebaut und
    muss auf Datenfluss umgestellt werden — die Erwartung wird nicht
    aufgeweicht.
    """
    decoy_file = tmp_path / "synthetic_tuple_decoy.py"
    decoy_file.write_text(
        "import logging\n"
        "import time\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "class CompareDispatchService:\n"
        "    def __init__(self, user_id):\n"
        "        self._user_id = user_id\n"
        "\n"
        "    def dispatch_all_presets(self, presets):\n"
        "        '''Versendet alle faelligen Presets. Returns (sent, failed).'''\n"
        "        sent = 0\n"
        "        failed = 0\n"
        "        for preset in presets:\n"
        "            try:\n"
        "                if self._dispatch_one(preset):\n"
        "                    sent += 1\n"
        "                else:\n"
        "                    sent += 1\n"
        "            except Exception as e:\n"
        "                logger.error('dispatch failed for %s: %s', preset.get('id'), e)\n"
        "            time.sleep(2.0)\n"
        "        status = 'partial' if failed > 0 else 'ok'\n"
        "        logger.info('dispatch done: %s (sent=%s, failed=%s)', status, sent, failed)\n"
        "        return sent, failed\n",
        encoding="utf-8",
    )
    found = _find_violations(decoy_file)
    locations = _finding_locations(found)
    assert any(loc.endswith("::dispatch_all_presets") for loc in locations), (
        "Die Attrappe ist durchgerutscht: eine Funktion, die (sent, failed) "
        "liefert, aber 'failed' nie erhöht, MUSS ein Klasse-2-Fund bleiben — "
        "sonst prüft der Wächter den Rückgabetyp statt den Datenfluss und ist "
        f"mit drei Zeilen Kosmetik auszuhebeln. Fundliste: {found}"
    )
    assert all(
        kind.startswith(KIND_PARTIAL_SUCCESS_BLIND) for kind in found.values()
    ), f"Unerwartete Fund-Art gemeldet: {found}"


def test_scanner_ignores_pure_computation_calls_in_synthetic_file(tmp_path):
    """AC-8b (NEU, E6): Verschont-Probe für die Ausschlussliste — fünf
    Nachbauten der ``weather_metrics.py``-Aggregationsfunktionen. Sie zählen
    und aggregieren über Comprehensions und ``sum(<genexp>)``, aber jeder
    Aufruf darin ist entweder ein Python-Builtin aus
    ``_PURE_COMPUTATION_BUILTINS`` oder eine ``math.*``-Funktion. KEIN Fund.

    Warum das kein Detail ist: die Klasse-2-Signatur fragt nach einem
    „undurchsichtigen Aufruf" — einem Aufruf, dessen Verhalten im Fehlerfall
    an der Aufrufstelle nicht sichtbar ist. ``sum(...)``, ``max(...)`` und
    ``math.radians(...)`` sind das Gegenteil: sie haben gar keinen
    Fehlerfall, den ein Gegenzähler zählen könnte. Ohne die Ausschlussliste
    hätte der Scanner ≥15 gleich gebaute Aggregationsfunktionen in
    ``weather_metrics.py`` plus ``aggregation.py::_circular_mean_deg``
    gemeldet — der Wächter wäre nie grün zu bekommen gewesen, und die
    naheliegende „Reparatur" (Signatur verengen, bis es passt) hätte echte
    Treffer mitgerissen.

    Die geprüfte Alternative war eine reine „Bindung an ``self.``"-Heuristik
    („nur Aufrufe auf self sind undurchsichtig"). Sie wurde VERWORFEN, weil
    sie zwei echte Treffer verloren hätte: ``compare_alert.py`` zählt über
    ``notification_service.send_multi_location_deviation_alert(...)`` und
    ``trip_alert.py::check_radar_alerts`` über ``radar_svc.get_nowcast(...)``
    — beides Aufrufe auf FREMDE Objekte. Die Ausschlussliste unterscheidet
    dagegen nach dem, worauf es fachlich ankommt: rechnet der Aufruf nur,
    oder kann er scheitern?

    Die fünfte Bauform (``_compute_wind_direction``) ist die schärfste
    Probe: ``sum(math.sin(math.radians(d)) for d in dirs)`` ist ein
    ``sum(<genexp>)`` mit VERSCHACHTELTEN Aufrufen — ein Detektor, der nur
    das äußerste Ziel prüft und die inneren ``math.*``-Aufrufe als
    undurchsichtig wertet, fällt hier durch.
    """
    metrics_file = tmp_path / "synthetic_pure_computation.py"
    metrics_file.write_text(
        "import math\n"
        "\n"
        "\n"
        "class WeatherMetricsService:\n"
        "    def _compute_temperature(self, timeseries):\n"
        "        temps = [dp.t2m_c for dp in timeseries.data if dp.t2m_c is not None]\n"
        "        if not temps:\n"
        "            return None, None, None\n"
        "        return min(temps), max(temps), sum(temps) / len(temps)\n"
        "\n"
        "    def _compute_wind(self, timeseries):\n"
        "        winds = [dp.wind10m_kmh for dp in timeseries.data if dp.wind10m_kmh is not None]\n"
        "        return max(winds) if winds else None\n"
        "\n"
        "    def _compute_precipitation(self, timeseries):\n"
        "        precip_vals = [\n"
        "            dp.precip_1h_mm for dp in timeseries.data if dp.precip_1h_mm is not None\n"
        "        ]\n"
        "        return sum(precip_vals) if precip_vals else None\n"
        "\n"
        "    def _compute_cloud_cover(self, timeseries):\n"
        "        clouds = [\n"
        "            dp.cloud_total_pct for dp in timeseries.data if dp.cloud_total_pct is not None\n"
        "        ]\n"
        "        if not clouds:\n"
        "            return None\n"
        "        return round(sum(clouds) / len(clouds))\n"
        "\n"
        "    def _compute_wind_direction(self, timeseries):\n"
        "        dirs = [\n"
        "            dp.wind_direction_deg\n"
        "            for dp in timeseries.data\n"
        "            if dp.wind_direction_deg is not None\n"
        "        ]\n"
        "        if not dirs:\n"
        "            return None\n"
        "        sin_sum = sum(math.sin(math.radians(d)) for d in dirs)\n"
        "        cos_sum = sum(math.cos(math.radians(d)) for d in dirs)\n"
        "        avg_rad = math.atan2(sin_sum / len(dirs), cos_sum / len(dirs))\n"
        "        avg_deg = math.degrees(avg_rad) % 360\n"
        "        return round(avg_deg)\n",
        encoding="utf-8",
    )
    found = _find_violations(metrics_file)
    assert not found, (
        "Reine Rechen-Aggregationen (Builtins und math.*) wurden als "
        "teilerfolg-blind gemeldet — die Verschont-Ausschlussliste (E6, "
        "_PURE_COMPUTATION_BUILTINS/_PURE_COMPUTATION_MODULES) greift nicht. "
        "Mit diesem Verhalten meldete der Wächter allein in "
        "weather_metrics.py mindestens 15 Fehlalarme und wäre nie grün zu "
        f"bekommen. Fundliste: {found}"
    )


def test_scanner_ignores_house_norm_sent_failed_tuple_in_synthetic_file(tmp_path):
    """AC-9: Gegenprobe zur Hausnorm — ``failed`` wird im Fehlerzweig erhöht
    (sowohl im ``except`` als auch beim genuinen Fehlausgang ``no_weather``),
    ``sent`` im Erfolgszweig, beide fließen in die Rückgabe. Kein Fund.

    Nachbau von ``src/services/dispatch_orchestrator.py:65-77`` und ``:157``
    (``TripDispatchStrategy.dispatch_one`` / ``run_briefing_dispatch``). Das
    ist die Norm, die dieser Wächter ausrollt — schlägt er hier an, meldet er
    sein eigenes Vorbild als Verstoß und ist strukturell nie grün zu
    bekommen. Ebenso wichtig: die Fehler-Isolierung bleibt (die Schleife
    bricht bei einem Einzelfehler nicht ab) — nicht die Isolierung ist das
    Problem, sondern der fehlende Zähler.
    """
    good_file = tmp_path / "synthetic_house_norm.py"
    good_file.write_text(
        "import logging\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "def run_briefing_dispatch(service, due_items):\n"
        "    sent = 0\n"
        "    failed = 0\n"
        "    for trip, report_type in due_items:\n"
        "        try:\n"
        "            outcome = service.send_trip_report_outcome(trip, report_type)\n"
        "            if outcome == 'no_weather':\n"
        "                failed += 1\n"
        "            else:\n"
        "                sent += 1\n"
        "        except Exception as e:\n"
        "            failed += 1\n"
        "            logger.error('Failed %s report for %s: %s', report_type, trip.id, e)\n"
        "    return sent, failed\n",
        encoding="utf-8",
    )
    found = _find_violations(good_file)
    assert not found, (
        "Die Hausnorm ((sent, failed) mit echtem Fehlerzähler) wurde "
        f"fälschlich als teilerfolg-blind gezählt: {found}"
    )


# ---------------------------------------------------------------------------
# AC-10 und AC-11: Wirkungsnachweise Klasse 3 (Heartbeat ohne Wirkung)
# ---------------------------------------------------------------------------


def _write_unwired_heartbeat_surface(tmp_path) -> list[Path]:
    """Mini-Scanfläche aus zwei Dateien: Heartbeat definiert, aber nirgends gerufen.

    Nachbau von ``api/routers/scheduler.py:147`` (``_ping_heartbeat_compare``)
    zusammen mit dem Endpunkt, der ihn aufrufen SOLLTE
    (``trigger_compare_presets_daily``) und es nicht tut — die zweite Datei
    steht für „irgendwo sonst in der Scanfläche wird er auch nicht gerufen".
    """
    router_file = tmp_path / "synthetic_router.py"
    router_file.write_text(
        "import logging\n"
        "import os\n"
        "\n"
        "from services.scheduler_dispatch_service import run_compare_presets_daily\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "def _ping_heartbeat_compare():\n"
        "    '''Fail-soft: Heartbeat-Ping wenn GZ_HEARTBEAT_COMPARE gesetzt.'''\n"
        "    url = os.getenv('GZ_HEARTBEAT_COMPARE', '')\n"
        "    if not url:\n"
        "        logger.debug('GZ_HEARTBEAT_COMPARE nicht gesetzt — kein Ping')\n"
        "        return\n"
        "    try:\n"
        "        import httpx\n"
        "\n"
        "        httpx.get(url, timeout=5)\n"
        "        logger.info('Heartbeat-Ping Compare OK')\n"
        "    except Exception as e:\n"
        "        logger.warning('Heartbeat-Ping Compare fehlgeschlagen: %s', e)\n"
        "\n"
        "\n"
        "def trigger_compare_presets_daily(user_id, hour=None):\n"
        "    sent, failed = run_compare_presets_daily(user_id, hour=hour)\n"
        "    status = 'partial' if failed > 0 else 'ok'\n"
        "    return {'status': status, 'count': sent, 'failed': failed}\n",
        encoding="utf-8",
    )
    other_file = tmp_path / "synthetic_service.py"
    other_file.write_text(
        "def run_compare_presets_daily(user_id, hour=None):\n"
        "    return 0, 0\n",
        encoding="utf-8",
    )
    return [router_file, other_file]


def test_scanner_detects_unwired_heartbeat_function_in_synthetic_file(tmp_path):
    """AC-10: Wirkungsnachweis für Klasse 3 — eine Funktion mit ``heartbeat``
    im Namen, die in der gesamten Scanfläche (außer in ihrer eigenen
    Definition) nirgends aufgerufen wird.

    Nachbau von ``api/routers/scheduler.py:147`` (``_ping_heartbeat_compare``,
    B13): der Compare-Heartbeat ist verdrahtet GEDACHT, aber nie
    angeschlossen. Bleibt der Compare-Versand komplett aus, schlägt niemand
    Alarm — der Gegenpol zum „bedingungslosen Ping" aus der Hausregel
    „Readiness statt Liveness". Ein Unit-Test, der nur das
    No-Env-Verhalten prüft, ist kein Aufrufer: ``tests/`` ist deshalb nicht
    Teil der Scanfläche.

    Der Wächter MELDET den Fund; die REPARATUR (den Compare-Heartbeat
    tatsächlich anschließen) läuft ausschließlich in Issue #1407, nicht in S4
    dieser Ticket-Familie (Spec „Aus dem Scope ausgeschlossen").
    """
    surface = _write_unwired_heartbeat_surface(tmp_path)
    found = _find_unwired_heartbeat_violations(surface)
    locations = _finding_locations(found)
    assert any(loc.endswith("::_ping_heartbeat_compare") for loc in locations), (
        "Scanner hat den unverdrahteten Heartbeat nicht erkannt (Klasse 3, "
        f"Nachbau von B13): {found}"
    )
    assert all(
        kind.startswith(KIND_HEARTBEAT_UNWIRED) for kind in found.values()
    ), f"Unerwartete Fund-Art gemeldet: {found}"


def test_scanner_ignores_wired_heartbeat_call_in_synthetic_file(tmp_path):
    """AC-11: Gegenprobe — dieselbe Heartbeat-Funktion, diesmal mit einem
    echten Aufruf hinter einer Erfolgsbedingung (``if sent > 0:``). Kein Fund.

    Referenzmuster ist das Pendant im Trip-Pfad, das korrekt nur bei
    erfolgreichem Versand pingt. Dass der Aufruf hinter der RICHTIGEN
    Bedingung steht, prüft dieser Wächter ausdrücklich nicht (s.
    Modul-Docstring, „Bekannte Grenzen") — geprüft wird nur, dass er
    überhaupt existiert.
    """
    router_file = tmp_path / "synthetic_router.py"
    router_file.write_text(
        "import logging\n"
        "import os\n"
        "\n"
        "from services.scheduler_dispatch_service import run_compare_presets_daily\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "def _ping_heartbeat_compare():\n"
        "    '''Fail-soft: Heartbeat-Ping wenn GZ_HEARTBEAT_COMPARE gesetzt.'''\n"
        "    url = os.getenv('GZ_HEARTBEAT_COMPARE', '')\n"
        "    if not url:\n"
        "        logger.debug('GZ_HEARTBEAT_COMPARE nicht gesetzt — kein Ping')\n"
        "        return\n"
        "    try:\n"
        "        import httpx\n"
        "\n"
        "        httpx.get(url, timeout=5)\n"
        "        logger.info('Heartbeat-Ping Compare OK')\n"
        "    except Exception as e:\n"
        "        logger.warning('Heartbeat-Ping Compare fehlgeschlagen: %s', e)\n"
        "\n"
        "\n"
        "def trigger_compare_presets_daily(user_id, hour=None):\n"
        "    sent, failed = run_compare_presets_daily(user_id, hour=hour)\n"
        "    if sent > 0:\n"
        "        _ping_heartbeat_compare()\n"
        "    status = 'partial' if failed > 0 else 'ok'\n"
        "    return {'status': status, 'count': sent, 'failed': failed}\n",
        encoding="utf-8",
    )
    other_file = tmp_path / "synthetic_service.py"
    other_file.write_text(
        "def run_compare_presets_daily(user_id, hour=None):\n"
        "    return 0, 0\n",
        encoding="utf-8",
    )
    found = _find_unwired_heartbeat_violations([router_file, other_file])
    assert not found, (
        "Ein verdrahteter Heartbeat (Aufruf hinter der Erfolgsbedingung) "
        f"wurde fälschlich als unverdrahtet gemeldet: {found}"
    )


# ---------------------------------------------------------------------------
# AC-12 und AC-13: Wirkungsnachweise Klasse 4 (Aufruf ohne Rückmeldung)
# ---------------------------------------------------------------------------


def test_scanner_detects_unacknowledged_dispatch_in_synthetic_file(tmp_path):
    """AC-12: Wirkungsnachweis für Klasse 4 — eine Versandfunktion besteht im
    Wesentlichen aus ``try: <Versandaufruf>; except Exception as e:
    logger.error(...)`` und gibt dem Aufrufer nichts zurück.

    Nachbau der drei Compare-Versandhelfer
    ``src/services/notification_service.py:878/891/929``
    (``_dispatch_compare_official_email``/``_telegram``/``_sms``, B14b). Der
    Aufrufer ``send_multi_location_official_alert`` hängt sein
    ``sent_channels.append(...)`` an den bloßen Umstand, dass er den Helfer
    GERUFEN hat — er kann strukturell gar nicht erfahren, ob der Versand
    geklappt hat. Der Fehlschlag verwandelt sich in eine Logzeile, die
    Erfolgsmeldung geht trotzdem raus.

    **Alle drei Nachbauten hier rufen einen Kanal-Ausgang im eigenen Rumpf**
    (``EmailOutput``/``TelegramOutput``) und erfüllen damit die
    Versandkontext-Zusatzbedingung aus Spec-Version 1.2 (E2). Die
    Gegenprobe dazu — dieselbe Struktur OHNE Kanal-Ausgang — steht in
    AC-13b.

    Drei Formen im Nachbau, alle MÜSSEN Fund sein:

    1. der schlichte Fall (E-Mail-Helfer, B14b): nur ``try``/``except``, kein
       ``return``, Annotation ``-> None``;
    2. der Fall mit lokalem Import vor dem ``try`` UND einem nackten
       ``return`` im Erfolgspfad (Telegram-Helfer, Z. 916 im Bestand). Ein
       nacktes ``return`` liefert ``None`` und ist KEIN Erfolgssignal (S-9)
       — ein Detektor, der jedes ``return`` als Rückmeldung wertet, verlöre
       genau diesen Fall und damit ein Drittel der B14b-Erwartung;
    3. der Fall mit Vorspann-Guard und nacktem ``return`` GANZ VORN
       (Nachbau von ``_send_service_error_email``, Z. 1293/1297, B21). Er
       zeigt zweierlei: dass ein mehrzeiliger Vorspann vor dem ``try``
       unschädlich ist, und dass ein nacktes ``return`` auch dann keine
       Rückmeldung ist, wenn es vor dem ``try`` steht. Diese Form belegt
       zugleich B21 — die drei bei der E2-Verifikation zusätzlich
       gefundenen Helfer sind vom Detektor strukturell nicht von B14b zu
       unterscheiden, weshalb die Spec sie in die Restliste aufgenommen
       statt sie durch eine Verengung wegdefiniert hat.
    """
    bad_file = tmp_path / "synthetic_unacknowledged_dispatch.py"
    bad_file.write_text(
        "import logging\n"
        "\n"
        "from output.channels.email import EmailOutput\n"
        "from output.channels.telegram import TelegramOutput\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "class NotificationService:\n"
        "    def __init__(self, settings):\n"
        "        self._settings = settings\n"
        "\n"
        "    def _dispatch_compare_official_email(self, preset_name, subject, html) -> None:\n"
        "        try:\n"
        "            EmailOutput(self._settings).send(\n"
        "                subject=subject, body=html, html=True, mail_type='official-alert',\n"
        "            )\n"
        "        except Exception as e:\n"
        "            logger.error(f'Compare official alert email failed for {preset_name}: {e}')\n"
        "\n"
        "    def _dispatch_compare_official_telegram(\n"
        "        self, preset_name, subject, notices, telegram_style='rich',\n"
        "    ) -> None:\n"
        "        from output.renderers.alert.official_alerts import render_official_alert_sms\n"
        "\n"
        "        try:\n"
        "            if telegram_style == 'kurzform':\n"
        "                kurz_body = render_official_alert_sms(notices, sms_prefix=preset_name)\n"
        "                TelegramOutput(self._settings).send(subject=subject, body=kurz_body)\n"
        "                return\n"
        "            TelegramOutput(self._settings).send(subject=subject, body=str(notices))\n"
        "        except Exception as e:\n"
        "            logger.error(f'Compare official alert telegram failed for {preset_name}: {e}')\n"
        "\n"
        "    def _send_service_error_email(self, request) -> None:\n"
        "        config = request.report_config\n"
        "        is_sms_only = config and config.send_sms and not config.send_email\n"
        "        if not is_sms_only:\n"
        "            return\n"
        "        error_lines = '\\n'.join(\n"
        "            f'  - Segment {e.segment.segment_id}: {e.error_message}'\n"
        "            for e in request.failed_segments\n"
        "            if e.segment is not None\n"
        "        )\n"
        "        subject = f'[{request.trip.name}] Wetterdaten nicht verfuegbar'\n"
        "        try:\n"
        "            EmailOutput(self._settings).send(subject=subject, body=error_lines, html=True)\n"
        "            logger.info(f'Service error email sent for {request.trip.name}')\n"
        "        except Exception as e:\n"
        "            logger.error(f'Failed to send service error email: {e}')\n",
        encoding="utf-8",
    )
    found = _find_violations(bad_file)
    locations = _finding_locations(found)
    assert any(
        loc.endswith("::_dispatch_compare_official_email") for loc in locations
    ), (
        "Scanner hat den Versandhelfer ohne Rückmeldung nicht erkannt "
        "(Klasse 4, Nachbau von notification_service.py:878): der Aufrufer "
        "kann strukturell nicht wissen, ob der Versand geklappt hat. "
        f"Fundliste: {found}"
    )
    assert any(
        loc.endswith("::_dispatch_compare_official_telegram") for loc in locations
    ), (
        "Scanner hat den Telegram-Helfer nicht erkannt (Klasse 4, Nachbau von "
        "notification_service.py:891) — vermutlich weil der lokale Import vor "
        "dem try oder das nackte 'return' im Kurzform-Zweig als Rückmeldung "
        f"gewertet wurde. Ein nacktes return liefert None. Fundliste: {found}"
    )
    assert any(
        loc.endswith("::_send_service_error_email") for loc in locations
    ), (
        "Scanner hat den B21-Helfer nicht erkannt (Klasse 4, Nachbau von "
        "notification_service.py:1293) — vermutlich weil der mehrzeilige "
        "Vorspann vor dem try als 'Rumpf ist nicht im Wesentlichen ein "
        "try/except' gewertet wurde oder weil das nackte return im "
        "is_sms_only-Guard als Rückmeldung durchging. B21 ist von B14b "
        "strukturell nicht zu unterscheiden und steht deshalb in der "
        f"Restliste. Fundliste: {found}"
    )
    assert all(
        kind.startswith(KIND_UNACKNOWLEDGED_DISPATCH) for kind in found.values()
    ), f"Unerwartete Fund-Art gemeldet: {found}"


def test_scanner_ignores_acknowledged_dispatch_in_synthetic_file(tmp_path):
    """AC-13: Gegenprobe zu Klasse 4 — dieselbe ``try/except``-mit-Logger-
    Struktur, aber die Funktion liefert dem Aufrufer ein echtes Erfolgssignal
    zurück. Kein Fund.

    Das ist die Reparaturform, auf die S4 den Bestand bringen soll: der
    Fehlschlag bleibt fail-soft (die anderen Kanäle reißen nicht mit), aber
    er ist für den Aufrufer sichtbar und kann in ``sent_channels`` einfließen.
    Schlüge der Wächter auch hier an, hätte er keine Aussage mehr — er würde
    schlicht jedes fail-soft ``try/except`` anmeckern, und die Reparatur
    könnte ihn nicht grün machen.

    Geprüft werden beide Rückmeldungsformen: ein Bool aus dem Erfolgspfad
    (``return True`` / ``return False`` im Handler) und ein weitergereichtes
    Aufruf-Ergebnis (``return result``).
    """
    good_file = tmp_path / "synthetic_acknowledged_dispatch.py"
    good_file.write_text(
        "import logging\n"
        "\n"
        "from output.channels.email import EmailOutput\n"
        "from output.channels.sms import SMSOutput\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "class NotificationService:\n"
        "    def __init__(self, settings):\n"
        "        self._settings = settings\n"
        "\n"
        "    def _dispatch_compare_official_email(self, preset_name, subject, html) -> bool:\n"
        "        try:\n"
        "            EmailOutput(self._settings).send(\n"
        "                subject=subject, body=html, html=True, mail_type='official-alert',\n"
        "            )\n"
        "        except Exception as e:\n"
        "            logger.error(f'Compare official alert email failed for {preset_name}: {e}')\n"
        "            return False\n"
        "        return True\n"
        "\n"
        "    def _dispatch_compare_official_sms(self, preset_name, sms_text):\n"
        "        try:\n"
        "            result = SMSOutput(self._settings).send(subject='', body=sms_text)\n"
        "        except Exception as e:\n"
        "            logger.error(f'Compare official alert sms failed for {preset_name}: {e}')\n"
        "            return None\n"
        "        return result\n",
        encoding="utf-8",
    )
    found = _find_violations(good_file)
    assert not found, (
        "Ein Versandhelfer MIT Rückmeldung (return True/False bzw. return "
        "result) wurde als Klasse-4-Fund gemeldet — damit wäre jedes "
        "fail-soft try/except ein Verstoß und die Reparatur aus S4 könnte den "
        f"Wächter nie grün machen. Fundliste: {found}"
    )


def test_scanner_ignores_persistence_only_swallow_in_synthetic_file(tmp_path):
    """AC-13b (NEU, E2): Abgrenzung gegen Persistenz — dieselbe
    ``try/except``-mit-Logger-Struktur und ebenfalls ohne Rückgabewert, aber
    OHNE Aufruf auf einen Kanal-Ausgang. KEIN Klasse-4-Fund.

    Nachbau von ``src/services/alert_state.py::save`` (Z. 60) und ``::reset``
    (Z. 68); dieselbe Bauform haben ``weather_snapshot.py::save`` (Z. 61) und
    ``compare_weather_snapshot.py::save`` (Z. 52).

    Der Grund für diese Gegenprobe ist ein gemessener Befund aus der
    RED-Phase gegen Spec-Version 1.1: die uneingeschränkte Klasse-4-Form
    (nur „try/except, Logger-only-Handler, kein Rückgabewert") traf **18
    statt 3 Stellen**, davon 15 Persistenz-Helfer. Ein ``save()``, das jeden
    Fehler schluckt, IST ein echtes Problem — aber ein anderes: dieses
    Ticket heißt „Erfolg heißt Wirkung" und zielt auf Erfolgs*meldungen*,
    nicht auf Persistenz. Der Befund ist als Sammel-Eintrag in #1199
    festgehalten und ausdrücklich nicht wegdiskutiert; er wird nur in einer
    anderen Scheibe bearbeitet (Spec „Aus dem Scope ausgeschlossen").

    Wichtig für die Beurteilung: das ist KEINE Verengung zur Zahlenkosmetik.
    Dieselbe Verifikation, die 15 Persistenz-Helfer ausgeschlossen hat, hat
    drei WEITERE echte Versandkontext-Treffer offengelegt (B21) — und die
    sind in die Restliste gewandert statt weg. Der Test hier prüft die eine
    Richtung, AC-12 (dritte Form) die andere.
    """
    persistence_file = tmp_path / "synthetic_persistence_swallow.py"
    persistence_file.write_text(
        "import json\n"
        "import logging\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "class AlertStateStore:\n"
        "    def __init__(self, state_dir):\n"
        "        self._state_dir = state_dir\n"
        "\n"
        "    def save(self, entity_id: str, state: dict) -> None:\n"
        "        '''Persist the alert-state dict for an entity.'''\n"
        "        try:\n"
        "            self._state_dir.mkdir(parents=True, exist_ok=True)\n"
        "            self._path(entity_id).write_text(json.dumps(state, indent=2))\n"
        "        except OSError as e:\n"
        "            logger.error(f'Failed to save alert_state for {entity_id}: {e}')\n"
        "\n"
        "    def reset(self, entity_id: str) -> None:\n"
        "        '''Clear the alert-state for an entity (remove file). Idempotent.'''\n"
        "        path = self._path(entity_id)\n"
        "        try:\n"
        "            if path.exists():\n"
        "                path.unlink()\n"
        "        except OSError as e:\n"
        "            logger.warning(f'Failed to reset alert_state for {entity_id}: {e}')\n"
        "\n"
        "    def _path(self, entity_id: str):\n"
        "        return self._state_dir / f'{entity_id}.json'\n",
        encoding="utf-8",
    )
    found = _find_violations(persistence_file)
    assert not found, (
        "Persistenz-Helfer ohne Kanal-Ausgang wurden als Klasse-4-Fund "
        "gemeldet — die Versandkontext-Zusatzbedingung (E2, "
        "_CHANNEL_OUTPUT_CLASSES/_SINK_PARAMETER_SUFFIX) greift nicht. Mit "
        "diesem Verhalten trifft Klasse 4 18 statt 6 Stellen und vermischt "
        "'Erfolg heißt Wirkung' mit 'Persistenz schluckt Fehler' — zwei "
        f"verschiedene Probleme. Fundliste: {found}"
    )


# ---------------------------------------------------------------------------
# AC-14: Ausnahmeliste mit Begründungspflicht
# ---------------------------------------------------------------------------


def test_webhook_ack_is_documented_exception_not_silent_pass():
    """AC-14 (erste Hälfte): ``api/routers/webhook.py:72``
    (``telegram_webhook``) meldet bewusst immer ``{"status": "ok"}`` — das ist
    eine Protokoll-Empfangsbestätigung an Telegram, kein fachlicher
    Erfolgsstatus, und verhindert einen Retry-Sturm.

    Strukturell IST die Stelle ein Klasse-1-Fund: ``_reader._process_update(
    update, settings)`` steht als unzugewiesener Aufruf im ``try``, der
    Handler protokolliert nur, und danach folgt ein festes ``{"status":
    "ok"}``. Sie wird deshalb NICHT blind grün durchgewunken (sonst taucht sie
    bei jeder künftigen Prüfung als vermeintlicher Fehlalarm wieder auf),
    sondern steht mit wörtlicher Begründung in INTENTIONAL_CONSTANT_SUCCESS.
    Drei Dinge müssen gelten:

    1. der Eintrag existiert und trägt genau den in der Spec festgelegten
       Begründungstext,
    2. er steht NICHT zusätzlich in KNOWN_VIOLATIONS (er ist keine ausstehende
       Reparatur),
    3. der Scanner findet die Stelle tatsächlich — eine Ausnahme für etwas,
       das gar nicht erkannt wird, wäre Dekoration.
    """
    found = _all_violations()
    assert _WEBHOOK_ACK_LOCATION in INTENTIONAL_CONSTANT_SUCCESS, (
        "Der Telegram-Webhook-Ack fehlt in INTENTIONAL_CONSTANT_SUCCESS — "
        "ohne Eintrag taucht er bei jeder Prüfung erneut als vermeintlicher "
        f"Fehlalarm auf. Code reference: {_WEBHOOK_ACK_LOCATION}"
    )
    assert INTENTIONAL_CONSTANT_SUCCESS[_WEBHOOK_ACK_LOCATION] == (
        _WEBHOOK_ACK_JUSTIFICATION
    ), (
        "Die Begründung weicht vom in der Spec festgelegten Wortlaut ab — die "
        "Unterscheidung 'Protokoll-Ack, kein Erfolgsstatus' MUSS wörtlich "
        f"dastehen. Code reference: {_WEBHOOK_ACK_LOCATION}"
    )
    assert _WEBHOOK_ACK_LOCATION not in KNOWN_VIOLATIONS, (
        "Der Webhook-Ack steht zugleich in KNOWN_VIOLATIONS — 'bewusst "
        "erlaubt' und 'Reparatur ausstehend' schließen sich aus. Code "
        f"reference: {_WEBHOOK_ACK_LOCATION}"
    )
    assert _WEBHOOK_ACK_LOCATION in found, (
        "Der Scanner findet die Webhook-Stelle gar nicht — dann ist die "
        "Ausnahme Dekoration statt geprüfter Entscheidung (und die "
        "Klasse-1-Signatur greift dort nicht). Code reference: "
        f"{_WEBHOOK_ACK_LOCATION}"
    )


def test_intentional_exceptions_carry_nonempty_justification():
    """AC-14 (zweite Hälfte): jeder Eintrag in INTENTIONAL_CONSTANT_SUCCESS
    trägt eine nichtleere fachliche Begründung, und jeder Eintrag ist noch
    aktuell.

    Das ist der Grund, warum die Ausnahmen eine geprüfte Datenstruktur sind
    und keine Kommentar-Konvention (``# status-ok-intentional: <Grund>``):
    ein Kommentar im Code erreicht den Betrieb nicht, ein geprüfter
    Listen-Eintrag schon. Ohne diesen Test wäre die Liste ein Schlupfloch —
    jeder künftige Fund ließe sich mit einer leeren Zeile stillstellen.

    Zusätzlich wird die Liste gegen den echten Scan geprüft: eine Ausnahme
    für eine Stelle, die der Scanner nicht (mehr) meldet, ist veraltet und
    muss raus — dieselbe Ratschen-Logik wie AC-3, nur in die andere Richtung.
    """
    found = _all_violations()
    unjustified = sorted(
        location
        for location, justification in INTENTIONAL_CONSTANT_SUCCESS.items()
        if not isinstance(justification, str) or not justification.strip()
    )
    assert not unjustified, (
        "Diese Ausnahmen tragen keine Begründung — eine Ausnahme ohne "
        "fachliche Begründung ist ein Schlupfloch, kein Beschluss. Code "
        f"reference: {unjustified}"
    )
    stale = sorted(
        location for location in INTENTIONAL_CONSTANT_SUCCESS if location not in found
    )
    assert not stale, (
        "Diese Ausnahmen sind veraltet (der Scanner meldet die Stelle nicht "
        "mehr) — aus INTENTIONAL_CONSTANT_SUCCESS entfernen. Code reference: "
        f"{stale}"
    )


# Genehmigte Ausnahmen, fest verdrahtet — Zuwachs ist eine Spec-Entscheidung.
_APPROVED_EXCEPTIONS = {_WEBHOOK_ACK_LOCATION}


def test_intentional_exception_list_cannot_grow():
    """AC-14 (dritter Teil): GIVEN ein echter, unreparierter Fund / WHEN er
    aus KNOWN_VIOLATIONS genommen und mit irgendeinem Text hier eingetragen
    wird / THEN wird der Wächter rot — die Ausnahmeliste kann nicht wachsen.

    Ohne sie ist die Ausnahmeliste die Hintertür des Wächters: AC-2 zählt
    Einträge daraus NICHT als Fund, der Begründungs-Test prüft nur, DASS Text
    dasteht — ein Füllsatz ließ `scheduler.py:54` (B2) spurlos verschwinden
    (#1405: „Keine Ausnahme ohne Schrumpf-Nachweis"). SCHRUMPFEN bleibt
    erlaubt: fällt ein Eintrag weg, ist die Stelle wieder ungelistet und AC-2
    schlägt an, außer sie ist repariert oder steht in KNOWN_VIOLATIONS.
    """
    added = sorted(set(INTENTIONAL_CONSTANT_SUCCESS) - _APPROVED_EXCEPTIONS)
    assert not added, (
        "Neuer Eintrag in INTENTIONAL_CONSTANT_SUCCESS: eine Ausnahme entsteht "
        "durch eine Spec-Entscheidung, nicht durch einen Listeneintrag — sonst "
        f"ist jeder offene Fund mit zwei Zeilen stillzustellen. Hier: {added}"
    )


# ---------------------------------------------------------------------------
# AC-15 und AC-16: Abgrenzung der Scanfläche und strukturelle Nicht-Treffer
# ---------------------------------------------------------------------------


def test_scan_scope_excludes_go_internal_tree():
    """AC-15: Der Go-Baum ``internal/`` ist NICHT Teil der Scanfläche — ein
    Python-``ast``-Scan erreicht ihn strukturell nicht (andere Sprache, keine
    ``.py``-Dateien). Das ist eine bewusste, dokumentierte Lücke, kein
    Versehen: die Heartbeat-Aufrufe in ``internal/notify/mq.go`` und
    ``internal/config/config.go`` bleiben ungeprüft. Vorbild für eine
    Python↔Go-Abdeckung über ein Inventar statt über AST ist
    ``tests/test_egress_inventory_drift.py``.

    Der Test hält die Lücke fest, damit sie nicht später stillschweigend als
    „geprüft" gilt — und prüft zugleich, dass die Scanfläche überhaupt gefüllt
    ist (ein leerer Scan wäre ein grüner Wächter ohne Wirkung).
    """
    scanned = _scan_files()
    assert scanned, "Scanfläche ist leer — der Wächter liefe wirkungslos grün."
    internal_dir = REPO_ROOT / "internal"
    inside_go_tree = [p for p in scanned if internal_dir in p.parents]
    assert not inside_go_tree, (
        "Der Go-Baum internal/ liegt in der Scanfläche — ein Python-AST-Scan "
        "kann ihn nicht auswerten. Abgrenzung ist bewusst (Issue #1405, 'Aus "
        f"dem Scope ausgeschlossen'). Code reference: {inside_go_tree}"
    )
    assert all(
        _ROUTERS_DIR in p.parents or _SERVICES_DIR in p.parents for p in scanned
    ), (
        "Scanfläche enthält Dateien außerhalb von api/routers/** und "
        "src/services/** — die Spec zieht die Grenze dort."
    )
    tests_dir = REPO_ROOT / "tests"
    assert not [p for p in scanned if tests_dir in p.parents], (
        "tests/ liegt in der Scanfläche — ein Unit-Test eines Heartbeats "
        "wäre damit ein 'Aufrufer' und B13 verschwände (Klasse 3)."
    )


def test_scanner_ignores_pure_liveness_endpoint(tmp_path):
    """AC-16: ``api/routers/health.py`` meldet konstant ``{"status": "ok"}`` —
    und das ist richtig so: „ok" heißt hier „der Prozess antwortet", was per
    Definition wahr ist, sobald der Handler läuft. Es gibt keine vorgelagerte
    Tat, deren Ausgang verschwiegen werden könnte — die Funktion tätigt gar
    keinen Aufruf, dessen Ergebnis der Status ignorieren könnte, also greift
    Bedingung (a) der Klasse-1-Signatur nicht.

    Entscheidend ist das WIE: die Stelle darf NICHT über die Ausnahmeliste
    grün werden, sondern muss strukturell durchfallen. Sonst wäre die
    Ausnahmeliste der bequeme Weg für jeden künftigen Fund, und der Wächter
    verlöre seine Aussagekraft.

    **AC-16b (S-7) ist Teil dieses Tests:** der synthetische Zwilling trägt
    einen Dekorator, der SELBST ein ``ast.Call`` ist
    (``@router.get("/health")``) — und genau daran scheitert ein naiver
    Detektor. ``ast.walk()`` über den kompletten ``FunctionDef``-Knoten sieht
    ``decorator_list`` als Kind-Feld und findet dort einen unzugewiesenen
    Aufruf; Bedingung (a) wäre erfüllt, Bedingung (b) durch das feste
    ``{"status": "ok"}`` ebenfalls, und die Lebendmeldung wäre ein Fund. Der
    Scanner darf für Bedingung (a) ausschließlich ``node.body`` durchsuchen.
    Ein Dekorator wird im UMSCHLIESSENDEN Raum ausgewertet, nicht im
    Funktionsraum der dekorierten Funktion — er ist syntaktisch kein Aufruf
    innerhalb des Körpers. Die zweite synthetische Form schärft das nach:
    zwei gestapelte Dekoratoren mit Argumenten, ein leerer Funktionsrumpf
    außer dem ``return``, und zusätzlich ein Aufruf in der DEFAULT-Belegung
    eines Parameters (``limit=int("10")``) sowie in der Rückgabe-Annotation —
    auch diese Stellen liegen außerhalb von ``node.body``.

    Geprüft wird beides: die echte Datei im Bestand UND zwei synthetische
    Zwillinge — ersteres bindet den Wächter an den Ist-Stand, letzteres hält
    die Aussage auch dann fest, wenn ``health.py`` eines Tages umzieht.
    """
    health_file = REPO_ROOT / "api" / "routers" / "health.py"
    assert health_file.exists(), (
        f"Erwartete Lebendmeldung fehlt: {health_file} — AC-16 prüft ins Leere."
    )
    real_found = _find_violations(health_file)
    assert not real_found, (
        "Die reine Lebendmeldung api/routers/health.py wurde als Fund "
        "gemeldet. Sie MUSS strukturell durchfallen (kein vorgelagerter "
        "Aufruf) — nicht über INTENTIONAL_CONSTANT_SUCCESS grün gemacht "
        f"werden. Code reference: {real_found}"
    )
    assert str(_relative_path(health_file)) not in {
        location.split("::", 1)[0] for location in INTENTIONAL_CONSTANT_SUCCESS
    }, (
        "health.py steht auf der Ausnahmeliste — damit wäre der bequeme Weg "
        "eröffnet, jeden künftigen Fund per Listeneintrag stillzustellen."
    )

    synthetic_file = tmp_path / "synthetic_health.py"
    synthetic_file.write_text(
        "from fastapi import APIRouter\n"
        "\n"
        "router = APIRouter()\n"
        "\n"
        "\n"
        "@router.get('/health')\n"
        "def health():\n"
        "    return {'status': 'ok', 'version': '0.1.0'}\n",
        encoding="utf-8",
    )
    synthetic_found = _find_violations(synthetic_file)
    assert not synthetic_found, (
        "Der synthetische Lebendmeldungs-Zwilling wurde als konstante "
        "Erfolgsmeldung gezählt — vermutlich hat ein ast.walk() über den "
        "ganzen FunctionDef-Knoten den Dekorator @router.get('/health') als "
        "unzugewiesenen Aufruf im Rumpf gewertet (S-7). Für Bedingung (a) "
        f"zählt ausschließlich node.body: {synthetic_found}"
    )

    decorated_file = tmp_path / "synthetic_decorated_only.py"
    decorated_file.write_text(
        "from fastapi import APIRouter, Depends\n"
        "\n"
        "router = APIRouter()\n"
        "\n"
        "\n"
        "def _require_auth():\n"
        "    return None\n"
        "\n"
        "\n"
        "@router.get('/ready', response_model=dict)\n"
        "@router.head('/ready')\n"
        "def readiness(limit=int('10'), _auth=Depends(_require_auth)) -> dict:\n"
        "    return {'status': 'ok', 'ready': True}\n",
        encoding="utf-8",
    )
    decorated_found = _find_violations(decorated_file)
    assert not decorated_found, (
        "Eine Funktion, deren einzige Aufrufe in decorator_list, args-"
        "Defaults und der Rückgabe-Annotation stehen, wurde als Klasse-1-"
        "Fund gemeldet (S-7). Alle drei Stellen werden AUSSERHALB des "
        "Funktionsraums ausgewertet und erfüllen Bedingung (a) nicht — der "
        "Scanner darf ausschließlich node.body durchsuchen, nie "
        "node.decorator_list/node.args/node.returns. Ohne diesen Ausschluss "
        f"ist AC-16 strukturell unerfüllbar: {decorated_found}"
    )
