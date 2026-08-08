#!/usr/bin/env python3
"""Ausgabe-Waechter „Secret-Output-Sperre" — Issue #1537 Scheibe 2, Stufe B.

`PostToolUse`-Waechter: durchsucht das ERGEBNIS jedes Werkzeugaufrufs nach dem
ausgeschriebenen Wert eines Geheimnisses aus der lokalen `.env` und ersetzt jeden
Treffer durch `***<SCHLUESSELNAME>***`, bevor Claude das Ergebnis sieht.

Warum ueberhaupt: Scheibe 1 (`secret_in_repo_gate.py`) schuetzt nur einen Austrittsweg
(vorgemerkte Dateien beim `git commit`). Der Egress-Waechter des Plugins
(`secret_egress_guard.py`, #1380) prueft nur ausgehende EINGABEN. Ein Wert, der in der
AUSGABE eines Werkzeugs zurueckkommt, obwohl er im Aufruf nie stand, lief bisher an
beiden vorbei — genau so trat in #1535 ein gueltiger Bot-Zugang ueber die Testausgabe
eines `Bash`-Aufrufs aus.

Vier Bauvorgaben, alle nicht verhandelbar:

  1. STUMM IM NORMALFALL. VOLLSTAENDIG geprueft und nichts gefunden heisst: keinerlei
     stdout, keinerlei stderr, Exit 0, Ergebnis unangetastet. Nur dann. „Konnte nicht
     pruefen" ist kein Normalfall und wird gemeldet (Bauvorgabe 2).
  2. DURCHGEHEND FAIL-OPEN — die Umkehrung von Scheibe 1. Dieser Waechter laeuft nach
     JEDEM Werkzeugaufruf in JEDER Sitzung; eine eigene Stoerung (Plugin fehlt, .env
     unlesbar, kaputtes JSON, unerwartete Gestalt, beliebige Ausnahme) darf niemals ein
     Werkzeug-Ergebnis zerstoeren oder eine Sitzung blockieren. Jede Stoerung endet mit
     Exit 0 und unveraendertem Ergebnis — aber NICHT lautlos: sie hinterlaesst eine
     stderr-Zeile mit dem Ausnahme-TYP (nie deren Text, der Nutzlast-Bruchstuecke tragen
     kann). Ein stiller Abbruch ist von „nichts gefunden" nicht unterscheidbar, waehrend
     der Wert weiterhin im Klartext bei Claude ankommt (Befund F005).
     GEMELDET WIRD, WER UNERWARTET MITTEN IN DER ARBEIT SCHEITERT — nicht, wer von
     vornherein weiss, dass er nicht arbeiten kann. Deshalb bleibt der Fall „Plugin fehlt"
     bewusst still: das ist ein Dauerzustand, und eine Zeile nach JEDEM Werkzeugaufruf waere
     Laerm, bis jemand das Plugin installiert — Laerm hat hier schon einmal einen Befund
     erzeugt (F003). Diese Unterscheidung ist die Regel fuer kuenftige Aenderungen.
  3. ERKENNUNG WIRD GELIEHEN, NICHT NEU GEBAUT. `collect_secrets`, `_is_secret_key`,
     `_is_secret_value` kommen per importlib aus `core/hooks/secret_egress_guard.py` des
     Plugins agent-os-openspec (Ladeweg wie `.claude/hooks/hook_utils.py`). Ein dritter
     eigener Geheimnis-Begriff waere der Fehler. Zwei getrennte try-Bloecke (Vorbild
     `secret_in_repo_gate.py:96-123`): fehlt das Modul ODER fehlt eine der Funktionen in
     einer aelteren Plugin-Fassung, wird der Waechter fail-open statt kaputt.
  4. STRUKTURERHALTENDER ERSATZ. Gemessen am 2026-08-07 (neun Laeufe einer eigenstaendigen
     Sitzung, Claude Code 2.1.224, Zufallsmarker): die Plattform uebernimmt
     `updatedToolOutput` nur, wenn es ALLE Schluessel des urspruenglichen Ergebnisses
     traegt. Ein String oder ein unvollstaendiges Objekt wird STILLSCHWEIGEND VERWORFEN —
     kein Fehler, kein Hinweis, Exit 0, auch unter `--debug hooks` keine Diagnosezeile.
     Ein falsch geformter Ersatz ist damit von einem funktionierenden Waechter nicht
     unterscheidbar. Deshalb: das empfangene `tool_response` wird KOPIERT und darin werden
     nur Werte ersetzt — nie ein frisches Objekt gebaut.

GEMESSENE GRENZE (2026-08-07, Nachmessung zur offenen Luecke bei AC-3): bei einem
FEHLGESCHLAGENEN Bash-Aufruf (Exit-Code != 0) laeuft dieser Hook UEBERHAUPT NICHT — die
Plattform ruft `PostToolUse` dort nicht auf. Zwei Laeufe mit Zufallsmarker ergaben null
Hook-Aufrufe, waehrend derselbe Befehl mit Exit-Code 0 den Hook normal ausloeste. Die
String-Behandlung unten bleibt trotzdem drin (andere Werkzeuge koennen String-Ergebnisse
liefern), ist fuer den Bash-Fehlschlag aber wirkungslos — nicht weil der Ersatz abgelehnt
wuerde, sondern weil es gar nicht erst dazu kommt.

KEINE REKURSION, NIRGENDS (Adversary-Befund F005, gemessen 2026-08-08, Python 3.12,
recursionlimit 1000). Traversierung UND Tiefenkopie laufen iterativ ueber einen Stapel. Die
frueheren Grenzen waren beide unsichtbar: eine feste Grenze von 25 Ebenen (bis F003) und
danach `copy.deepcopy`, das ab Tiefe 498 einen `RecursionError` warf — GEFANGEN vom Notfall-
Handler unten, und zwar bevor `main()` irgendetwas ausgegeben hatte. Das sah von aussen aus
wie „geprueft, nichts gefunden", waehrend die Plattform das Ergebnis MIT dem Wert im Klartext
weiterreichte: der schwerste Fehler, den dieser Waechter haben kann. Gemessen liegt die
verbleibende Grenze jetzt bei `json.loads` bzw. `json.dumps`: Tiefe 9997 geht, ab 9998 kommt
ein `RecursionError` — also rund das Zwanzigfache. Jenseits davon bleibt es fail-open, aber
NICHT MEHR STUMM (siehe `_melde_abbruch`). Zyklen sind ausgeschlossen, weil das Ergebnis
ausschliesslich aus `json.loads` stammt.

Kein `.env`-Cache (sonst greift der Waechter nach einer Rotation ins Leere) und kein
Werkzeugname-Filter: fuer AUSGABEN ist `Read` gerade der wahrscheinlichste Austrittsweg,
waehrend der Egress-Waechter ihn (fuer Eingaben zu Recht) ueberspringt.

Meldungen nennen ausschliesslich Werkzeug- und Schluesselnamen — nie den Wert.

Regel-Budget: schliesst einen Weg, ueber den in #1535 nachweislich ein aktiver Zugang
ausgetreten ist. Schaltet sich deshalb nicht automatisch ab;
Wirksamkeits-Pruefung: 2026-11-05.

Exit-Code immer 0 — `PostToolUse` kann laut Hook-Vertrag ohnehin nicht blockieren.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

# ------------------------------------------------------- Plugin-Erkennung leihen
# Block 1: Modul ueberhaupt laden. Derselbe Ladeweg wie `.claude/hooks/hook_utils.py`
# (Registry -> installPath -> importlib von der Datei), nur mit anderem Zieldateipfad.


def _plugin_modul():
    registry = os.path.expanduser("~/.claude/plugins/installed_plugins.json")
    with open(registry) as fh:
        daten = json.load(fh)
    install_pfad = ""
    for schluessel, eintraege in daten.get("plugins", {}).items():
        if not schluessel.startswith("agent-os-openspec@"):
            continue
        eintrag = next((e for e in eintraege if e.get("scope") == "user"), eintraege[0])
        install_pfad = eintrag.get("installPath", "")
        break
    if not install_pfad:
        raise ImportError("agent-os-openspec nicht in der Plugin-Registry")
    modul_pfad = os.path.join(install_pfad, "core", "hooks", "secret_egress_guard.py")
    if not os.path.isfile(modul_pfad):
        raise ImportError(f"secret_egress_guard.py nicht gefunden ({modul_pfad})")
    spec = importlib.util.spec_from_file_location("_gz_secret_egress_guard", modul_pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


try:
    _EGRESS = _plugin_modul()
    MODUL_FEHLT: str | None = None
except Exception as _fehler:  # noqa: BLE001 — fehlendes Plugin macht fail-open, nicht kaputt
    _EGRESS = None
    MODUL_FEHLT = f"{type(_fehler).__name__}: {_fehler}"

# Block 2: die drei Funktionen einzeln greifen. Bewusst getrennt vom Modul-Import: eine
# aeltere Plugin-Fassung koennte das Modul haben, aber nicht (alle) diese Namen — dann
# soll der Waechter ebenfalls nur fail-open werden, nicht abstuerzen.
try:
    if _EGRESS is None:
        raise ImportError(MODUL_FEHLT or "Modul nicht geladen")
    collect_secrets = _EGRESS.collect_secrets
    _is_secret_key = _EGRESS._is_secret_key
    _is_secret_value = _EGRESS._is_secret_value
    FUNKTION_FEHLT: str | None = None
except Exception as _fehler2:  # noqa: BLE001
    collect_secrets = None  # type: ignore[assignment]
    _is_secret_key = None  # type: ignore[assignment]
    _is_secret_value = None  # type: ignore[assignment]
    FUNKTION_FEHLT = f"{type(_fehler2).__name__}: {_fehler2}"


def _konfiguration() -> dict:
    """Erkennungs-Konfiguration des Plugins (ehrt `openspec.yaml`, z.B. `ignore_keys`).

    Faellt auf die dokumentierten Vorgabewerte zurueck, falls die (hausinterne)
    Hilfsfunktion in einer aelteren Plugin-Fassung fehlt oder die Konfiguration nicht
    lesbar ist — wieder fail-open statt kaputt.
    """
    try:
        return _EGRESS._get_config()
    except Exception:  # noqa: BLE001
        return {
            "enabled": True, "min_length": 8, "ignore_keys": set(),
            "extra_key_patterns": [], "scan_all_keys": False,
        }


def _geheimnisse() -> list[tuple[str, str]]:
    """(Schluessel, Wert)-Paare aus der lokalen `.env`, frisch von Platte (kein Cache).

    Doppelte Werte werden zusammengefasst; steht derselbe Wert unter mehreren Schluesseln,
    gewinnt der, den das Plugin als echten Geheimnis-Schluessel einstuft (`_is_secret_key`)
    — sonst traegt der Ersatz z.B. `***DATABASE_URL***` statt `***DB_PASS***`, wenn das
    Passwort zusaetzlich in einer Verbindungs-URL steckt.

    Sortiert nach absteigender Wertlaenge: sonst koennte ein kurzes Geheimnis, das
    Teilstring eines langen ist, den langen Treffer zerschneiden.
    """
    cfg = _konfiguration()
    if not cfg.get("enabled", True):
        return []
    wurzel = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    nach_wert: dict[str, str] = {}
    for schluessel, wert in collect_secrets(cfg, wurzel):
        if not wert or not _is_secret_value(wert, cfg):
            continue
        bisher = nach_wert.get(wert)
        if bisher is None or (
            not _is_secret_key(bisher, cfg) and _is_secret_key(schluessel, cfg)
        ):
            nach_wert[wert] = schluessel
    return sorted(
        ((s, w) for w, s in nach_wert.items()), key=lambda p: len(p[1]), reverse=True
    )


# ------------------------------------------------------------------- Maskierung


def _ersetze(text: str, paare: list[tuple[str, str]], gefunden: set[str]) -> str:
    for schluessel, wert in paare:
        if wert in text:
            text = text.replace(wert, f"***{schluessel}***")
            gefunden.add(schluessel)
    return text


def _tiefe_kopie(knoten):
    """Tiefenkopie OHNE Rekursion — Ersatz fuer `copy.deepcopy` (Befund F005).

    `copy.deepcopy` steigt je Ebene einen Stack-Rahmen tief und warf ab Tiefe 498 einen
    `RecursionError`, noch bevor die Maskierung ueberhaupt begann. Hier laeuft dieselbe
    Arbeit ueber einen Arbeitsstapel: Quelle und zugehoeriges Ziel wandern paarweise durch.

    Nur JSON-Typen — mehr kann in einem `tool_response` nicht stehen, er kommt aus
    `json.loads`. Strings, Zahlen, `bool` und `None` sind unveraenderlich und werden direkt
    uebernommen; alles Unbekannte ebenso (kann hier nicht auftreten, waere sonst geteilt).
    Die SCHLUESSELREIHENFOLGE bleibt erhalten — sie einzusammeln und neu zu setzen wuerde
    die Gestalt aendern, an der die Plattform den Ersatz annimmt oder verwirft (AC-13).
    """
    if not isinstance(knoten, (dict, list)):
        return knoten
    wurzel: dict | list = {} if isinstance(knoten, dict) else []
    stapel: list[tuple[dict | list, dict | list]] = [(knoten, wurzel)]
    while stapel:
        quelle, ziel = stapel.pop()
        paare = quelle.items() if isinstance(quelle, dict) else enumerate(quelle)
        for schluessel, wert in paare:
            if isinstance(wert, dict):
                neu: object = {}
            elif isinstance(wert, list):
                neu = []
            else:
                neu = wert
            if isinstance(ziel, list):
                ziel.append(neu)
            else:
                ziel[schluessel] = neu
            if isinstance(wert, (dict, list)):
                stapel.append((wert, neu))   # type: ignore[arg-type]
    return wurzel


def _neue_notizen() -> dict:
    """Was ausser der reinen Maskierung noch gemeldet werden muss (Regel: NIE LAUTLOS)."""
    return {"oberste_schluessel": set()}


def _maskiere_schluessel(knoten: dict, paare: list[tuple[str, str]], gefunden: set[str],
                         notizen: dict, oberste_ebene: bool) -> None:
    """Ein Geheimnis kann auch als SCHLUESSELNAME auftreten (Adversary-Befund F001).

    Unterhalb der obersten Ebene wird umbenannt — die Plattform prueft dort die
    Schluesselmenge nicht. AUF der obersten Ebene wird bewusst NICHT umbenannt: gemessen
    verwirft die Plattform den GESAMTEN Ersatz, sobald ein Schluessel des Originals fehlt
    (Bauvorgabe 4) — aus einer Teilluecke wuerde ein Totalausfall, auch fuer alle Werte.
    Stattdessen wird laut gemeldet (in `main`), nie stillschweigend uebergangen.
    """
    umbenennungen: dict[str, str] = {}
    for schluessel in list(knoten):
        if not isinstance(schluessel, str):
            continue
        treffer: set[str] = set()
        neuer = _ersetze(schluessel, paare, treffer)
        if not treffer:
            continue
        if oberste_ebene:
            notizen["oberste_schluessel"].add(neuer)   # maskierte Form, nie der Rohwert
        else:
            gefunden.update(treffer)
            umbenennungen[schluessel] = neuer
    if umbenennungen:
        neu = [(umbenennungen.get(s, s), w) for s, w in knoten.items()]  # Reihenfolge bleibt
        knoten.clear()
        knoten.update(neu)


def _maskiere_inplace(knoten, paare: list[tuple[str, str]], gefunden: set[str],
                      notizen: dict, oberste_ebene: bool = False) -> None:
    """Ersetzt Werte IN der uebergebenen Kopie — Reihenfolge und alle uebrigen Felder
    bleiben unangetastet (Bauvorgabe 4). Laeuft ITERATIV ueber einen Stapel durch dicts und
    Listen (keine Tiefengrenze, siehe Kopf), damit auch verschachtelte Formen
    (`Read` -> `file.content`) und unbekannte Werkzeuge lueckenlos erfasst sind.
    Schluesselnamen: siehe `_maskiere_schluessel` — `oberste_ebene` gilt nur fuer den
    Wurzelknoten, alles darunter wird umbenannt."""
    stapel: list[tuple[object, bool]] = [(knoten, oberste_ebene)]
    while stapel:
        aktuell, ist_oberste = stapel.pop()
        if isinstance(aktuell, dict):
            for schluessel, wert in list(aktuell.items()):
                if isinstance(wert, str):
                    neu = _ersetze(wert, paare, gefunden)
                    if neu != wert:
                        aktuell[schluessel] = neu
                elif isinstance(wert, (dict, list)):
                    stapel.append((wert, False))
            # Erst nach den Werten: das Umbenennen laesst die Kindobjekte unberuehrt.
            _maskiere_schluessel(aktuell, paare, gefunden, notizen, ist_oberste)
        elif isinstance(aktuell, list):
            for i, wert in enumerate(aktuell):
                if isinstance(wert, str):
                    neu = _ersetze(wert, paare, gefunden)
                    if neu != wert:
                        aktuell[i] = neu
                elif isinstance(wert, (dict, list)):
                    stapel.append((wert, False))


# ------------------------------------------------------------------- Hauptlauf

# Letztes bekanntes Werkzeug, damit die Notfallmeldung sagen kann, WELCHES Ergebnis
# ungeprueft durchging. Steht auf "?" bis die Nutzlast gelesen ist.
_WERKZEUG = "?"


def _melde_abbruch(fehler: BaseException) -> None:
    """Fail-open bleibt — lautlos bleibt es nicht (Befund F005).

    Wird dieser Weg genommen, ist das Ergebnis UNGEPRUEFT bei Claude angekommen und kann
    Zugangsdaten im Klartext enthalten. Genannt wird ausschliesslich der Ausnahme-TYP: der
    TEXT einer Ausnahme kann Bruchstuecke der Nutzlast tragen, und ein Waechter, der beim
    Scheitern das Geheimnis in seine Fehlermeldung schreibt, waere die Luecke in Reinform.
    """
    print(f"[secret_output_gate] Pruefung des Ergebnisses von {_WERKZEUG} NICHT abgeschlossen "
          f"({type(fehler).__name__}) — das Ergebnis ging UNVERAENDERT durch und kann "
          f"Zugangsdaten im Klartext enthalten.", file=sys.stderr)


def main() -> int:
    # Kein eigener try-Block: jede Stoerung faellt in den Notfall-Handler unten, der sie
    # meldet. Frueher endete sie hier lautlos — ununterscheidbar von „nichts gefunden".
    global _WERKZEUG
    eingabe = json.loads(sys.stdin.read() or "{}")
    if not isinstance(eingabe, dict):
        return 0
    _WERKZEUG = eingabe.get("tool_name") or "?"

    if collect_secrets is None:
        # Plugin fehlt oder ist zu alt: Ergebnis unveraendert, lautlos. Eine Meldung nach
        # JEDEM Werkzeugaufruf waere unbrauchbarer Laerm.
        return 0

    ergebnis = eingabe.get("tool_response")
    if not isinstance(ergebnis, (str, dict, list)):
        return 0  # null/Zahl/bool: nichts zu maskieren

    paare = _geheimnisse()
    if not paare:
        return 0

    gefunden: set[str] = set()
    notizen = _neue_notizen()
    if isinstance(ergebnis, str):
        # String-Form eines Ergebnisses. Fuer den Bash-Fehlschlag nachweislich
        # unerreichbar (siehe „GEMESSENE GRENZE" im Kopf) — andere Werkzeuge koennen
        # String-Ergebnisse aber sehr wohl liefern, deshalb bleibt der Zweig.
        ersatz = _ersetze(ergebnis, paare, gefunden)
    else:
        ersatz = _tiefe_kopie(ergebnis)
        _maskiere_inplace(ersatz, paare, gefunden, notizen,
                          oberste_ebene=isinstance(ergebnis, dict))

    werkzeug = _WERKZEUG
    if gefunden:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedToolOutput": ersatz,
        }}, ensure_ascii=False))
        print(f"[secret_output_gate] Zugangsdaten im Ergebnis von {werkzeug} maskiert: "
              f"{', '.join(sorted(gefunden))} (Wert bewusst nicht angezeigt).",
              file=sys.stderr)
    # Kein Fund UND nichts zu melden -> keinerlei Ausgabe, Ergebnis unangetastet (AC-1).
    if notizen["oberste_schluessel"]:
        print(f"[secret_output_gate] Zugangsdaten im SCHLUESSELNAMEN auf oberster Ebene des "
              f"Ergebnisses von {werkzeug}: "
              f"{', '.join(sorted(notizen['oberste_schluessel']))} (maskiert dargestellt, "
              f"Wert bewusst nicht angezeigt). Dort NICHT umbenannt — die Plattform verwirft "
              f"sonst den gesamten Ersatz und es bliebe auch jeder Wert unmaskiert. Der "
              f"Schluesselname erreicht Claude daher im Klartext.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as _abbruch:  # noqa: BLE001 — Stoerung veraendert NIE ein Ergebnis ...
        _melde_abbruch(_abbruch)   # ... bleibt aber nicht unerwaehnt (Befund F005)
        sys.exit(0)
