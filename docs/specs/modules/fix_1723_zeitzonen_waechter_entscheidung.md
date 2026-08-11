---
entity_id: fix_1723_zeitzonen_waechter_entscheidung
type: bugfix
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [tests, guard, ratchet, zeitzone, epic-1722, issue-1723]
---

<!-- Issue #1723 — Epic #1722, Scheibe S1: Zeitzonen-Wächter (#1402) auf die
     Entscheidungs-Schicht (src/services/** + api/**) ausdehnen. -->

# Fix #1723 (Epic #1722 S1) — Zeitzonen-Wächter auf die Entscheidungs-Schicht ausdehnen

## Approval

- [ ] Approved

## Purpose

Der bestehende Zeitzonen-Wächter `tests/test_output_timezone_guard.py` (Issue #1402) bewacht
heute nur die **Darstellung** einer Uhrzeit (`src/output/**` + sieben einzeln gelistete
Messaging-Dateien). Die elf wiederkehrenden Zeitzonen-Bugs des Projekts sitzen aber in der
**Entscheidung** — welcher Kalendertag gemeint ist, ob ein Versand fällig ist, ob Ruhezeit gilt,
wann ein Zähler kippt. Diese Lieferung dehnt den Geltungsbereich des bestehenden Wächters auf
`src/services/**` + `api/**` aus, trägt den heutigen Bestand als `KNOWN_VIOLATIONS` ein und
blockt damit ausschließlich **Neuzugänge**. Es bewegt keine Zeile Produktivcode.

## Source

- **File:** `tests/test_output_timezone_guard.py` (MODIFY)
- **Identifier:** `_scan_files()` (Scanfläche erweitern), zwei neue Detektor-Zweige innerhalb der
  bestehenden `ast.walk(tree)`-Schleife von `_find_violations()` (Muster A „Umgebungsuhr", Muster
  B „festes Nicht-UTC-Zonen-Literal"), `KNOWN_VIOLATIONS` (neue Einträge), ein neuer Test analog
  `test_scan_scope_excludes_go_internal_tree` aus `tests/test_success_status_guard.py`.

> **Schicht-Hinweis:** reines Test-Infrastruktur-Artefakt (`tests/`). Die Scanfläche liest
> Produktivcode unter `src/services/**` und `api/**` (Python-Core/Domain-Backend), verändert ihn
> aber nicht. Kein Frontend-, Go-API- oder Go-internal-Code betroffen.

## Estimated Scope

- **LoC:** ~350–450 (Budget vom PO auf 500 freigegeben, weil die `KNOWN_VIOLATIONS`-Bestandsliste
  inline in der `.py`-Testdatei steht und mitzählt: erweiterte Scanfläche + zwei Detektor-Zweige +
  ~30–40 Restlisten-Einträge + sechs neue Tests)
- **Files:** 1 MODIFY (`tests/test_output_timezone_guard.py`). Keine weitere Datei.
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/test_success_status_guard.py::_scan_files()` / `test_scan_scope_excludes_go_internal_tree()` | Bauform-Vorbild | Scanfläche `api/routers/**` + `src/services/**` ist im Repo bereits erprobt; Vorbild für die „Scanfläche nicht leer + Positiv-Prüfung je Baum"-Zusicherung |
| `tests/test_guard_findings_survive_line_shifts.py` | Meta-Wächter, Downstream | Lädt den Prüfling über `_scan_files()`/`_find_violations()` zur Laufzeit, wählt den Prüfträger für den Einfüge-Nachweis automatisch aus „Datei mit den meisten Funden" — kann nach dieser Erweiterung wechseln, muss danach weiterhin grün sein (AC-10) |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | inhaltliche Grundlage (Status: Akzeptiert) | „Heute"/„morgen" folgen der Ortszeit — trägt die Bugklasse dieses Wächters bereits |
| `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` | Grundsatzentscheidung Epic #1722 (Status: Vorgeschlagen) | ordnet ADR-0044 als Spezialfall ein; S1 ändert kein Verhalten und ist von ihrem Status unabhängig lieferbar, S2 (#1724, bereits live) macht sie erstmals verhaltenswirksam |
| Issue #1466 AP2 | Schlüsselformat | `"pfad::funktion::ordinal"` statt `"pfad:zeile"` — bereits im Prüfling implementiert (`_number_findings()`, `_MODULE_SCOPE`), gilt unverändert für neue Funde |
| Issue #1465 | Falle (bereits im Prüfling behoben) | `rglob` auf ein fehlendes Verzeichnis liefert wortlosen Leerlauf — Vorbild für `test_scan_list_paths_all_exist()`; dieselbe Zusicherungsart wird für die neue Scanfläche gebraucht (AC-1) |
| Issue #1719 (`selectable=False`-Gate) | Präzedenzfall | ein zu weit gefasstes Muster trifft Kollateralschaden — Begründung für E1/E2 unten |
| Issue #1724 (Epic #1722 S2, LIVE `e21f4f48`) | Bestandsänderung | hat zwei `Europe/Vienna`-Stellen entfernt (`src/services/scheduler_dispatch_service.py`, `api/routers/scheduler.py`) — der heutige Bestand ist NIEDRIGER als die Zahlen im Kontextdokument (Stand `e230977d`); verifiziert per grep am 2026-08-11: nur noch `alert_daily_limit.py` + `deviation_alert_engine.py` |
| Issue #1726 (Epic #1722 S4) | Folge-Scheibe | übernimmt die verbleibenden `Europe/Vienna`-Stellen zur Behebung, getragen von ADR-0051 |

## Implementation Details

### Scanfläche erweitern

`_scan_files()` liefert zusätzlich zur bisherigen Fläche (`src/output/**` +
`_MESSAGING_SERVICE_FILES`) alle `*.py` unter `src/services/**` und `api/**` (rekursiv, analog
`_production_files()` im selben Modul bzw. `_scan_files()` in `test_success_status_guard.py`).
Die Kombination MUSS über eine Menge geführt werden (`sorted({*...})`, nicht `+=`): sechs der
sieben bisherigen `_MESSAGING_SERVICE_FILES`-Einträge liegen bereits unter `src/services/` und
würden sonst doppelt gescannt (harmlos für das Ergebnis, aber unnötige Redundanz). Der siebte
Eintrag (`src/app/cli.py`) bleibt der einzige, den die neue Fläche nicht mitbringt, und muss in
`_MESSAGING_SERVICE_FILES` stehen bleiben. Der Modul-Docstring-Kommentar über `_OUTPUT_DIR`
(„das komplette src/output/-Baumwerk … NICHT gescannt wird …") ist entsprechend zu aktualisieren
— er beschreibt sonst eine Fläche, die es nicht mehr gibt (dieselbe Fehlerart wie in
`[[reference_aussagen_ueber_eigenen_code_veralten_still]]`).

### Zwei neue Detektor-Zweige (in derselben `for node in ast.walk(tree):`-Schleife wie die
bestehenden fünf)

**Muster A — Umgebungsuhr.** `date.today()` (immer ein Fund — `date` kennt keine Zone) sowie
`datetime.now()` **ohne** ein `tz`-Argument (weder positional noch als Keyword). Erkannt wird
strukturell über den Attributnamen (`.today`/`.now`), nicht über den Empfängertyp — dieselbe
Grenze wie bei den übrigen Detektoren dieses Wächters und bei `test_success_status_guard.py`
(„Struktur, nicht Fachlichkeit"). `.utcnow()` matcht diesen Zweig NICHT (E2 unten) — es genügt,
`.utcnow()` nicht in die Attributnamen-Menge aufzunehmen, kein Ausschluss-Sonderfall nötig.

**Muster B — festes Nicht-UTC-Zonen-Literal.** `ZoneInfo("<beliebiger String außer "UTC">")` als
eigenständiger Fund, unabhängig davon, in welcher Ausdrucksform er auftritt (Modulebene-Zuweisung
wie `VIENNA = ZoneInfo("Europe/Vienna")`, Funktionsargument, Rückfallausdruck). Die vorhandenen
Helfer `_is_hardcoded_zoneinfo_call()` (matcht jedes Zonen-Literal) und `_is_zoneinfo_utc_call()`
(matcht nur `"UTC"`) decken die Bedingung bereits ab: Muster B ist `_is_hardcoded_zoneinfo_call(node)
and not _is_zoneinfo_utc_call(node)` als eigener, neuer Fundzweig — nicht nur innerhalb der
bestehenden Mid-Body-Rückfallformen (BoolOp/getattr/If/IfExp), die bislang ausschließlich
`src/output/**` erreichten.

Beide neuen Zweige nutzen dieselbe `record()`-Hilfsfunktion und damit automatisch das bestehende
Schlüsselformat (`"pfad::funktion::ordinal"`) und die bestehende Bereichsverfolgung (`_scopes()`,
`_MODULE_SCOPE`) — Modulebene-Funde wie das obige `VIENNA = ...`-Beispiel lösen ohne weitere
Änderung korrekt zu `<module>` auf.

### E1 — `ZoneInfo("UTC")` wird NICHT gefangen

Fünf der neun gemessenen Zonen-Literal-Funde (Stand `e230977d`) sind `"UTC"`, davon vier
dokumentierte Notnagel-Rückfälle in `notification_service.py` bei nicht auflösbarem Ort. Nach
Hausnorm #1345 („naive Zeitstempel sind UTC") ist das die *richtige* Schreibweise — der bekämpfte
Fehler ist die **geratene** Ortszone, nicht UTC. Muster B fängt deshalb ausschließlich
Nicht-UTC-Literale (s. o.).

### E2 — `.utcnow()` wird NICHT gefangen

`datetime.utcnow()` liefert *explizit* UTC, während `.now()`/`.today()` *implizit*
Prozess-Lokalzeit liefern — eine andere Fehlerklasse. Dass `.utcnow()` seit Python 3.12 veraltet
ist, ist Modernisierungsarbeit und nicht Gegenstand dieses Wächters.

### `KNOWN_VIOLATIONS` frisch messen

Die Restliste für die neue Fläche darf NICHT aus dem Kontextdokument `docs/context/fix-1723-
zeitzonen-waechter-entscheidung.md` abgeschrieben werden — dessen Zahlen stammen vom Stand
`e230977d`, seither ist #1724 live und hat zwei `Europe/Vienna`-Stellen entfernt
(`scheduler_dispatch_service.py`, `api/routers/scheduler.py`; per grep am 2026-08-11 verifiziert:
nur noch `alert_daily_limit.py` + `deviation_alert_engine.py` tragen `Europe/Vienna`). Maßgeblich
ist ausschließlich der AST-Scan der fertigen `_find_violations()`-Implementierung, unmittelbar vor
dem Commit gegen den dann aktuellen Stand von `main` ausgeführt — nicht die grep-Zählungen aus dem
Issue („40 + 10"/„12"), die Kommentare und Docstrings mitzählen (in `scheduler_dispatch_service.py`
sind 7 von 12 grep-Treffern reine Prosa aus #1724).

### Interaktion mit dem Meta-Wächter

`tests/test_guard_findings_survive_line_shifts.py` bestimmt den Prüfträger für den
Einfüge-Nachweis zur Laufzeit aus `_scan_files()` des Wächters selbst („Datei mit den meisten
Funden"). Wächst die Fundmenge in der neuen Fläche über die bisher reichste Datei
(`src/output/renderers/alert/official_alerts.py`) hinaus, wechselt der Prüfträger automatisch —
dieser Test braucht dafür keine Änderung, muss aber nach der Erweiterung nachweislich grün bleiben
(AC-10).

## Expected Behavior

- **Input:** der aktuelle Stand von `src/output/**`, `_MESSAGING_SERVICE_FILES`, `src/services/**`
  und `api/**` beim Testlauf.
- **Output:** `pytest`-Grün, solange kein Fund von Muster A oder Muster B in der erweiterten
  Fläche unlistet ist. Rot mit `Code reference: <Datei>::<Funktion>::<Ordinal>` bei jedem neuen,
  unlisteten Fund; ebenso rot, wenn ein `KNOWN_VIOLATIONS`-Eintrag auf eine inzwischen behobene
  Stelle zeigt (Schrumpf-Ratsche).
- **Side effects:** keine — reiner Lesezugriff auf den Quellbaum, kein Netzwerk, keine
  Produktivcode-Änderung.

## Acceptance Criteria

- **AC-1:** Given der Wächter läuft gegen den aktuellen Stand von `src/services/**` und `api/**` / When `_scan_files()` aufgerufen wird / Then enthält die zurückgegebene Liste mindestens eine Datei aus jedem der beiden neu hinzugekommenen Bäume, und kein Eintrag liegt außerhalb der (alten + neuen) Scanfläche
  - Test: `test_scan_scope_includes_services_and_api_and_is_not_empty()` — analog `test_scan_scope_excludes_go_internal_tree` aus `test_success_status_guard.py`; prüft Nicht-Leere der Gesamtfläche UND je-Baum-Zugehörigkeit.

- **AC-2:** Given ein neu eingefügtes `date.today()` oder `datetime.now()` ohne `tz`-Argument in einer synthetischen Datei unter einem `src/services/`-artigen Pfad / When der Wächter läuft / Then wird die Stelle als Fund gemeldet und der Wächtertest schlägt fehl, sofern der Fund nicht in `KNOWN_VIOLATIONS` steht
  - Test: synthetischer Wirkungsnachweis (Mutations-Pflicht 1) analog `test_scanner_detects_raw_astimezone_in_synthetic_output_file`, aber für Muster A und explizit außerhalb `src/output/`.

- **AC-3:** Given ein neu eingefügtes `ZoneInfo("<Nicht-UTC-Zone>")`-Literal in einer synthetischen Datei unter einem `api/`-artigen Pfad / When der Wächter läuft / Then wird die Stelle als Fund gemeldet und der Wächtertest schlägt fehl, sofern der Fund nicht in `KNOWN_VIOLATIONS` steht
  - Test: synthetischer Wirkungsnachweis (Mutations-Pflicht 2) für Muster B, außerhalb `src/output/`.

- **AC-4:** Given ein neu eingefügtes `ZoneInfo("UTC")` in derselben synthetischen Datei / When der Wächter läuft / Then bleibt der Test grün — E1 ist damit nicht nur behauptet, sondern gegengeprobt
  - Test: synthetischer Gegenprobe-Wirkungsnachweis (Mutations-Pflicht 5, erste Hälfte).

- **AC-5:** Given ein neu eingefügtes `datetime.utcnow()` in derselben synthetischen Datei / When der Wächter läuft / Then bleibt der Test grün — E2 ist damit nicht nur behauptet, sondern gegengeprobt
  - Test: synthetischer Gegenprobe-Wirkungsnachweis (Mutations-Pflicht 5, zweite Hälfte).

- **AC-6:** Given ein `KNOWN_VIOLATIONS`-Eintrag der neuen Fläche, dessen Fundstelle im Code noch existiert, wird aus der Liste entfernt / When der bestehende Shrink-Test (`test_known_violations_only_shrink`) läuft / Then schlägt er fehl, weil der Scanner die Stelle weiterhin findet, die Liste sie aber nicht mehr trägt
  - Test: Mutations-Pflicht 3, ausgeführt als String-Ersetzung mit externer Sicherungskopie (Repo-Konvention) gegen einen frisch aus der neuen Fläche gemessenen Eintrag, NICHT `git checkout/stash/reset`.

- **AC-7:** Given je ein eigener synthetischer Wirkungsnachweis für Muster A und für Muster B / When einer der beiden Detektoren durch ein invertiertes Prädikat (z. B. `and has_tz_kw` statt `and not has_tz_kw`) lautlos leerläuft, während der jeweils andere weiter Funde liefert / Then wird genau dieser Ausfall sichtbar — eine reine Summenprüfung über beide Muster hinweg würde ihn verdecken
  - Test: Mutations-Pflicht 4 — die AC-2- und AC-3-Nachweise müssen JE FÜR SICH auf den eigenen Fundtyp prüfen (`assert kind == "..."`, nicht nur `assert found`), sonst bleibt diese AC unerfüllt.

- **AC-8:** Given der Commit-Zeitpunkt der Implementierung / When `KNOWN_VIOLATIONS` für die neue Fläche befüllt wird / Then stammt jede Zahl aus einem frischen AST-Scan gegen den dann aktuellen Stand von `main` (inkl. der bereits durch #1724 entfernten zwei `Europe/Vienna`-Stellen), NICHT aus den grep-Zählungen des Issues oder den Zahlen im Kontextdokument (Stand `e230977d`)
  - Test: `test_no_unlisted_output_timezone_violations()` und `test_known_violations_only_shrink()` (bereits vorhanden, unverändert in ihrer Logik) laufen beide grün gegen den finalen Commit-Stand — das ist der einzige Nachweis, dass die Liste weder unter- noch überzählt.

- **AC-9:** Given ein Fund auf Modulebene außerhalb jeder Funktion (z. B. `VIENNA = ZoneInfo("Europe/Vienna")`) in der neuen Fläche / When der Wächter läuft / Then trägt der Fundschlüssel `_MODULE_SCOPE` (`"<module>"`) als Funktionsanteil, im selben Format `"pfad::funktion::ordinal"` wie alle übrigen Funde
  - Test: Wirkungsnachweis mit einer synthetischen Modulebene-Zuweisung unter einem `src/services/`-artigen Pfad, analog `test_timezone_guard_finding_names_the_enclosing_function` aus dem Meta-Wächter.

- **AC-10:** Given die erweiterte Scanfläche und die ggf. gewachsene Fundmenge / When `tests/test_guard_findings_survive_line_shifts.py` läuft / Then bleibt er vollständig grün — auch wenn `_richest_scanned_file("zeitzone")` dadurch auf eine andere Datei als bisher (`official_alerts.py`) wechselt
  - Test: `uv run pytest tests/test_guard_findings_survive_line_shifts.py -v` nach Fertigstellung der Erweiterung, vor dem Commit.

- **AC-11:** Given der unveränderte Bestand von `src/output/**` und `_MESSAGING_SERVICE_FILES` / When der erweiterte Wächter läuft / Then bleiben alle bisher bekannten 22 Funde (Restliste vor dieser Lieferung) unverändert erkannt und gelistet — die Erweiterung darf den bestehenden Scope nicht verschmälern
  - Test: `uv run pytest tests/test_output_timezone_guard.py -v` gegen den unveränderten `src/output/**`-Teilbestand; Regressionsschutz, kein neuer Testcode nötig, da `_all_violations()` beide Flächen gemeinsam prüft.

- **AC-12:** Given die Ausnahme aus #1723 („`src/providers/geosphere.py:372` ist API-Parameter, keine Entscheidung") / When der Wächter läuft / Then ist diese Ausnahme strukturell wirkungslos, weil `src/providers/` außerhalb der Scanfläche (`src/output/**`, `_MESSAGING_SERVICE_FILES`, `src/services/**`, `api/**`) liegt — sie wird dokumentiert, nicht implementiert
  - Test: keiner nötig (negative Feststellung); in „Known Limitations" festgehalten, damit sie nicht als offene Aufgabe missverstanden wird.

## Test Plan

Alle Läufe erfolgen über `uv run pytest tests/test_output_timezone_guard.py -v` sowie
(nach jeder Änderung an der Scanfläche/den Detektoren) `uv run pytest
tests/test_guard_findings_survive_line_shifts.py -v` im Sitzungs-Worktree — beide Dateien sind
namentlich benannt und damit vom Verbot des breiten Testlaufs (`CLAUDE.md` „Breiter Testlauf
gesperrt") nicht betroffen.

**Reihenfolge (wichtig für AC-8):** zuerst Scanfläche + beide Detektoren implementieren und alle
synthetischen Wirkungsnachweise (AC-2 bis AC-7, AC-9) grün bekommen — dabei ist `KNOWN_VIOLATIONS`
für die neue Fläche noch leer, der Wächter also absichtlich rot gegen den echten Bestand. Erst
unmittelbar vor dem Commit `_all_violations()` gegen den dann aktuellen `main`-Stand ausführen
(z. B. per `python3 -c "..."` oder einem Wegwerf-Testlauf) und das Ergebnis 1:1 in
`KNOWN_VIOLATIONS` übertragen — nicht früher, sonst veraltet die Liste durch parallele Arbeit
anderer Sessions (`main` ändert sich durch andere PRs).

- **AC-1:** `_scan_files()` direkt aufrufen, prüfen dass `_SERVICES_DIR`/`_API_DIR` (bzw. deren
  Pfad-Objekte) mindestens einmal als `parent` in der Ergebnisliste vorkommen und dass die
  Ergebnisliste nicht leer ist.
- **AC-2/AC-3/AC-7:** je eine synthetische Datei in `tmp_path` unter einem `src/services/`- bzw.
  `api/`-artigen Unterpfad mit genau einem Muster-A- bzw. Muster-B-Fund; `_find_violations()`
  direkt aufrufen, `kind`-Wert des Funds prüfen (nicht nur Nicht-Leere).
- **AC-4/AC-5:** dieselbe synthetische Datei zusätzlich um ein `ZoneInfo("UTC")` bzw.
  `datetime.utcnow()` ergänzen, erneut scannen, Fundzahl unverändert.
- **AC-6:** String-Ersetzung mit externer Sicherungskopie: einen frisch gemessenen
  `KNOWN_VIOLATIONS`-Eintrag der neuen Fläche temporär entfernen, `test_known_violations_only_shrink`
  laufen lassen, roten Fehlertext gegen den erwarteten Schlüssel prüfen, Sicherungskopie
  zurückspielen.
- **AC-8/AC-11:** vollständiger Lauf von `tests/test_output_timezone_guard.py -v` gegen den
  finalen Commit-Stand — Exit 0 ist der Nachweis, kein separater Test.
- **AC-9:** synthetische Datei mit `VIENNA = ZoneInfo('Europe/Vienna')` auf Modulebene unter einem
  `src/services/`-artigen Pfad; Fundschlüssel muss `::<module>::` enthalten.
- **AC-10:** vollständiger Lauf von `tests/test_guard_findings_survive_line_shifts.py -v`.
- **AC-12:** keine Testausführung — Dokumentationsnachweis in „Known Limitations".

## Known Limitations

1. **Muster 3 ist explizit außerhalb dieser Scheibe.** `.hour`/`.date()` auf einem Zeitstempel
   ohne nachweisliche Zonen-Auflösung (der eigentliche Fehler von #1470/#1697) braucht eine
   Datenfluss-Prüfung über Funktionsgrenzen hinweg und wird hier nicht versucht — eigene Scheibe.
2. **Go-Seite bleibt ungeprüft.** `time.Now()` (~225 Fundstellen) ist für einen Python-`ast`-Scan
   strukturell unerreichbar; Go führt die Zone im Typ mit, andere Fehlerklasse (analog AC-15 in
   `test_success_status_guard.py`).
3. **Die im Issue #1723 genannte Ausnahme geht ins Leere.** `src/providers/geosphere.py:372` liegt
   in `src/providers/` — außerhalb von `src/output/**`, `_MESSAGING_SERVICE_FILES`,
   `src/services/**` und `api/**`. Die Ausnahme wird nie gebraucht (AC-12). Nebenbefund, nicht Teil
   dieser Lieferung: `geosphere.py:405` deutet die Antwort mit
   `replace(tzinfo=ZoneInfo("Europe/Vienna"))`, was keine reine Parameterübergabe ist — relevant
   erst, wenn eine spätere Scheibe (S5) die Fläche auf `src/providers/` weitet.
4. **`ZoneInfo("UTC")` und `.utcnow()` sind bewusst KEINE Fehlerklasse dieses Wächters (E1/E2).**
   Fünf Fundstellen (`notification_service.py:773/821/1061/1063`,
   `trip_report_scheduler.py:1820`) bleiben deshalb unsichtbar — sie sind nach Hausnorm #1345
   vermutlich richtig, keine offene Schuld.
5. **Die verbleibenden `Europe/Vienna`-Stellen sind namentlich #1726 (S4) zugeordnet**
   (`src/services/alert_daily_limit.py`, `src/services/deviation_alert_engine.py`), getragen von
   ADR-0051. Diese Lieferung trägt sie nur als `KNOWN_VIOLATIONS`-Eintrag, behebt sie nicht.
6. **`.now()`/`.today()` werden strukturell erkannt, nicht typgeprüft.** Ein Objekt mit einer
   `.now()`-Methode, die keine Zeitzone betrifft, wäre theoretisch ein Fehlalarm — dieselbe Grenze
   wie bei den übrigen Wächtern dieses Repos („Struktur, nicht Fachlichkeit",
   `test_success_status_guard.py`). Am gemessenen Bestand tritt dieser Fall nicht auf.
7. **Doppelte Scan-Abdeckung von sechs `_MESSAGING_SERVICE_FILES`-Einträgen wird beseitigt, nicht
   nur toleriert.** Sechs der sieben Einträge liegen unter `src/services/` und wären ohne
   Mengenbildung (`sorted({*...})`) redundant gescannt — funktional folgenlos, aber unnötig; die
   Kombination MUSS deshalb über eine Menge geführt werden (s. Implementation Details).
8. **Der Meta-Wächter kann den Prüfträger wechseln (AC-10), ohne dass das ein Fehler ist** — er
   wählt zur Laufzeit die fundreichste Datei der (jetzt größeren) Scanfläche neu aus.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Testinfrastruktur-Erweiterung ohne Verhaltensänderung an Produktivcode —
  keine neue Entscheidungsfläche im Sinne der ADR-Kriterien. Inhaltlich getragen von ADR-0044
  (akzeptiert, „Kalendertage folgen der Ortszeit") und im Vorgriff auf ADR-0051 (vorgeschlagen,
  „Drei Zeitbegriffe") ausgerichtet, ohne von deren Status abzuhängen: S1 blockt Neuzugänge in der
  Entscheidungs-Schicht unabhängig davon, ob ADR-0051 bereits akzeptiert ist.

## Changelog

- 2026-08-11: Initial spec erstellt — Issue #1723, Epic #1722 Scheibe S1.
