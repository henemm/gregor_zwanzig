# Kontext: #1481 Scheibe A — Commit-Gate „Tests der berührten Dateien"

> **Hinweis zum Workflow-Namen:** Der Workflow heißt `feat-1481a-leser-vorlage`, weil die
> Scheibe ursprünglich eine *Leser-Vorlage* bauen sollte. Diese Idee ist in der Analyse an
> einer Messung gescheitert (s. u.) und wurde vom PO durch den hier beschriebenen Zuschnitt
> ersetzt. Der Name bleibt, damit die Workflow-Buchführung stabil bleibt.

## Auslöser

PO-Grundsatzentscheid 2026-08-03: *„nur ein Hook, der dich zwingt, bringt irgendetwas. Alles
andere ist komplett vergebener Aufwand."* Vorausgegangen war die Diagnose, dass die
wiederholten Fehler nicht an fehlenden Regeln liegen, sondern daran, dass vorhandene Regeln im
Moment der Arbeit nicht abgerufen werden.

## Verworfen: die Leser-Vorlage (mit Messung belegt)

Geplant war: Der Hook ermittelt aus dem Diff die geänderten Symbole, sucht alle Stellen, die
sie lesen, und legt die Liste beim Commit vor. **An fünf echten Commits durchgerechnet:**

| Commit | Folge-Fehler | Vorlage hätte enthalten |
|---|---|---|
| `d7c2ea8f` (#1314) | #1451 | 408 Fundstellen (406 davon zum Symbol `SPEC`) |
| `386bbdba` (#1401 A2b) | #1453 | 462 Fundstellen |
| `28cefe7f` (#1452) | #1471 | **1526** Fundstellen (`name` allein 983×) |
| `eedeeed9` (#1406 B) | — | 561 Fundstellen |
| `bea33854` (#1470) | — | 65 Fundstellen |

**Zwei Gründe für das Verwerfen:**

1. **Unbrauchbare Signalqualität.** 400–1500 Treffer je Commit, beherrscht von
   Allerweltsnamen (`SPEC`, `name`, `fetch`, `__init__`, Testhelfer wie `_result`,
   `TARGET_DATE`). Ein solches Gate wird umgangen, nicht gelesen.
2. **Es hätte die Fehler gar nicht gefangen.** #1451 war eine *neu gebaute* Funktion neben
   einer vorhandenen (keine Leser-Frage). #1453 war das Lesen eines Feldes mit unbekanntem
   Inhalt (keine Leser-Frage). Nur #1471 lag im Muster — aber `empfaenger` ist ein Datenfeld,
   keine Definition, und taucht in der Messung nicht auf.

**Die Erkenntnis, die den neuen Zuschnitt trägt:** In zwei der drei Fälle hat das System den
Fehler bereits gemeldet — bei #1453 stand der passende Wächter zwei Tage rot, bei #1471 hatte
der Adversary von #1452 den Befund selbst gefunden (als „kosmetisch" abgelegt, s. #1471). Es
fehlte nie an Information, sondern daran, dass vorhandene Information nichts blockiert hat.

## Neuer Zuschnitt (PO-Entscheid)

**`git commit` blockiert, wenn die Kern-Tests der geänderten Dateien rot sind.**

Kein neuer Erkenntnisapparat — das vorhandene Signal wird scharf gestellt. Das Muster
existiert bereits im Repo: `renderer_mail_gate.py` (#811) verlangt für Mail-Inhalts-Dateien
einen grünen Testlauf, bevor es einen Commit durchlässt. Diese Scheibe verallgemeinert es,
statt etwas Neues danebenzustellen (DRY auf der Gate-Ebene, Invariante 3 von #1374).

## Analyse

### Typ
Feature (Werkzeug/Gate), projektspezifisch → `.claude/hooks/`, nicht ins Plugin.

### Zuordnung Datei → Tests (gemessen)

Namensnennung des Moduls in Testdateien (`git grep -l "<modulname>" tests/`), ergänzt um die
Import-Beziehung. Messung an `src/output/renderers/email/compare_html.py`:
**20 Testdateien, 236 Tests, 9 Sekunden.** Hooktauglich.

Gegenprobe an `bea33854` (2 geänderte Quelldateien): 24 zugehörige Testdateien über die
direkte Import-Beziehung.

### Bestandsschutz — Ratsche statt Härte

Die Kern-Suite trägt heute **18 rote Tests** (#1196 Scheibe 1: 39 → 18; davon 12 echte
Produktfehler, 3 Design-Fidelity, 2 Reihenfolge-Verschmutzung, 1 Live-Schicht-Fehlplatzierung).

Ein hartes „rot = kein Commit" würde sofort Arbeit an Dateien blockieren, deren Tests aus
fremden Gründen rot sind. Deshalb **Ratsche**: Der Hook vergleicht gegen einen gespeicherten
Rot-Bestand je Testdatei und blockiert nur **neue** Fehlschläge. Der Bestand darf nie wachsen
und sinkt über #1196.

### Betroffene Dateien

| Datei | Art | Zweck |
|---|---|---|
| `.claude/hooks/touched_tests_gate.py` | CREATE | der Hook |
| `.claude/settings.json` | MODIFY | Verdrahtung als PreToolUse/Bash |
| `tests/tdd/test_touched_tests_gate.py` | CREATE | Verhaltensnachweis (Wegwerf-Repo, kein Netz) |
| `.claude/hooks/<rot-bestand>.json` | generiert | Ratschen-Stand, nicht handgepflegt |

### Umfang
~4 Dateien, geschätzt +200/-0 LoC. Risiko: MITTEL (ein Gate, das jeden Commit betrifft —
fail-open bei eigenen Fehlern ist Pflicht).

### Abgrenzung
- Nur **Python-Kern**. Go- und Frontend-Tests bleiben außen vor (eigene Laufzeitprofile).
- Nur die **Kern-Schicht**; Live-Marker (`live`/`email`/`staging`) werden ausgeschlossen —
  sonst löst ein Commit echten Versand aus (#1477).
- Kein Ersatz für `renderer_mail_gate.py`; die Mail-Regel bleibt strenger.

### Offene Punkte
- [ ] `pytest-socket` ist **nicht installiert**, obwohl CLAUDE.md es als sicheren Weg nennt
      (`--disable-socket` → `unrecognized arguments`). Für dieses Gate nicht blockierend
      (Marker-Ausschluss genügt), aber die Regel zeigt auf ein Werkzeug, das es nicht gibt →
      Sammel-Eintrag.
