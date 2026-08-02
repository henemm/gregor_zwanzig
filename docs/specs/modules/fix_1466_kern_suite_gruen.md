---
entity_id: fix_1466_kern_suite_gruen
type: bugfix
created: 2026-08-02
updated: 2026-08-02
status: draft
version: "1.0"
tags: [kern-suite, resolution-loss-guard, success-status-guard, output-timezone-guard, roundtrip, issue-1466, issue-1196]
workflow: fix-1466-kern-suite-gruen
---

<!-- Issue #1466 (Wächter-Drift) unter dem Dach-Issue #1196 (deterministischer Kern 100 % grün) -->

# Kern-Suite grün: zwei echte Verstöße beheben, Wächter-Schlüssel verschiebungsfest machen, Roundtrip-Invariante auf die haltbare Aussage umstellen (Issue #1466)

## Approval

- [x] Approved — 2026-08-02, auf ausdrückliche Delegation des PO („Ich bin PO. Ich kenne
  mich damit nicht aus. Handle als mein Tech Lead der nach Best-Practice-Regeln
  entscheidet", zweimal bekräftigt). Der PO hat den Dreier-Zuschnitt (AP1/AP2/AP3) und die
  Reihenfolge zuvor mit „Ja" bestätigt; die fachlichen Einzelentscheidungen — insbesondere
  AP3 (Test statt Produktivcode ändern) — sind hier begründet und nicht einzeln vorgelegt
  worden. **Der Abschnitt „Warum AP3 den Test ändert und nicht den Code" ist die
  Rechenschaft dafür.**

## Purpose

Der deterministische Kern läuft aktuell mit rotem Rauschen, sodass ein
tatsächlicher Regressions-Fund im allgemeinen Rot untergeht — genau das ist
bei dieser Erhebung bereits passiert: zwei **echte** stille
Auflösungsverluste blieben unbemerkt, weil niemand die rote Suite mehr
liest. Diese Lieferung bringt den Kern zurück auf grün, ohne die Prüftiefe
zu senken: zwei echte Codefehler werden behoben (nicht in eine
Ausnahmeliste eingetragen), drei Wächter bekommen einen Schlüssel, der
Zeileneinfügungen übersteht, statt bei jeder Verschiebung neu rot zu
werden, und eine strukturell unerreichbare Roundtrip-Invariante wird durch
die Aussage ersetzt, die tatsächlich zählt: kein Informationsverlust, keine
Information, die etwas anderes bedeutet als ihre Abwesenheit.

## Source

> **Schicht-Hinweis:** Diese Lieferung ist ausschließlich **Python-Core**
> (Renderer, Test-Infrastruktur). Kein Go-Anteil wird geändert — der
> referenzierte Go-Test (AC-7) ist bereits vorhandenes, unverändertes
> Regressionsmaterial und wird nur als Nachweis herangezogen.

- **File:** `src/output/renderers/compare_hourly_metric_ids.py` —
  **Identifier:** `normalize_hourly_metrics()` (`:95-118`, stiller
  Verlust `:112-115`)
- **File:** `src/output/renderers/email/html.py` — **Identifier:**
  `build_trip_corridor_id_map()` (`:602-621`, stiller Verlust `:615-618`)
- **File:** `tests/test_success_status_guard.py` — **Identifier:**
  `KNOWN_VIOLATIONS` (`:1410`), `INTENTIONAL_CONSTANT_SUCCESS`/
  `_WEBHOOK_ACK_LOCATION` (`:268`, `:1614`), `_scopes()` (`:326`,
  bereits vorhanden)
- **File:** `tests/test_resolution_loss_guard.py` — **Identifier:**
  `KNOWN_VIOLATIONS` (`:616`), `_finding_locations()` (`:565`),
  `_finding_location_counts()` (`:579`), `_scopes()` (`:157`, bereits
  vorhanden)
- **File:** `tests/test_output_timezone_guard.py` — **Identifier:**
  `KNOWN_VIOLATIONS` (`:381`), `_find_violations()` (`:175-265`, scannt
  heute flach mit `ast.walk(tree)`, **keine** `_scopes()`-Funktion)
- **File:** `tests/test_trip_flat_fields_dual_read.py` — **Identifier:**
  `test_ac13_report_config_byte_identical_after_roundtrip` (`:112-126`)
- **File:** `src/app/loader.py` — **Identifier:** `_clamped_day_window()`
  (`:98-121`), `_trip_to_dict()` (`:1521-1553`), `save_trip()` /
  `_deep_merge_preserve_unknown()` (`:1629-1644`, `:124-136`) — **READ
  ONLY**, unverändert
- **Referenz (unverändert, Nachweis für AC-7):**
  `internal/handler/trip_day_window_write_seam_test.go:48-80`
  (`TestUpdateTripHandler_ClampsInvalidDayWindowPairOnWrite`)

## Estimated Scope

- **LoC:** ~40–60 Produktivcode (zwei Logging-Ergänzungen in AP1,
  ggf. `import logging` in `html.py`) + ~180–260 Testcode (drei
  Schlüssel-Migrationen mit Scope-Nachrüstung im dritten Wächter,
  Insert-Nachweistests, zwei neue Fixture-basierte Log-Assertions,
  Umbau des Roundtrip-Tests) + ~40–60 Doku-Zeilen (diese Spec,
  Changelog-Einträge in den drei Wächter-Kommentarblöcken). **Gesamt
  ~260–380 Zeilen**; auf den 250er-Rahmen zählen Produktivcode und
  Tests, `docs/`/`*.md` nicht — ein Override ist wahrscheinlich nötig.
- **Files:** 2 Produktivdateien (AP1), 3 Wächter-Testdateien (AP2), 1
  Testdatei (AP3) — 6 Dateien insgesamt.
- **Effort:** medium — AP1 ist lokal klein, AP2 ist die eigentliche
  Arbeit (Scope-Verfolgung im dritten Wächter neu bauen, alle
  Zeilen-Schlüssel migrieren, Insert-Nachweis führen), AP3 ist eine
  gezielte Testumformulierung ohne Produktivcode-Eingriff.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py::get_metric()` | READ (unverändert) | Wirft `KeyError` bei unbekannter `metric_id` — genau der Fehltreffer, der in AP1 sichtbar gemeldet werden muss |
| `src/output/renderers/compare_metric_ids.py::resolve_enabled_metrics()` | READ (Vorbild) | Referenzmuster „Sammeln-und-melden": `unmapped`-Liste + `logger.warning(...)` NACH der Schleife, Issue-Bezug im Text (`:154-166`) |
| `tests/test_resolution_loss_guard.py::_branch_is_safeguarded()` / `_scopes()` | READ | Der Wächter erkennt genau dieses Muster als „gemeldet" — AP1 muss so implementiert werden, dass der Wächter selbst grün bleibt, nicht nur die Fachlogik |
| `tests/test_success_status_guard.py::_scopes()` (`:326`) | READ (Vorbild) | Bereits vorhandene AST-Scope-Verfolgung — Vorlage für die Nachrüstung im dritten Wächter |
| `src/services/official_alerts/dpc.py::_extract_alerts()` | READ (Vorbild Sichtbarkeit) | `logger.warning("dpc: unbekannter Zonencode %r ...")` (`:117`) — Muster für eine verständliche, kontextreiche Logzeile |
| `internal/handler/trip_day_window_write_seam_test.go` | READ (Regressionsnachweis, unverändert) | Belegt den realen Reset-Pfad, den AC-7 nicht brechen darf |

## Implementation Details

### AP1 — zwei echte stille Auflösungsverluste beheben

Beide Stellen folgen exakt der A1–A9-Mechanik aus #1405
(`get_metric(...)` → `except KeyError: continue`, unbekannte Größe fällt
kommentarlos aus der Ausgabe):

- `normalize_hourly_metrics()` (`compare_hourly_metric_ids.py:112-115`):
  im `try`/`except KeyError`-Zweig eine `dropped`-Liste befüllen und nach
  der Schleife per `logger.warning(...)` mit Issue-Bezug (`#1466`, analog
  `#1406`) melden — Vorbild `resolve_enabled_metrics()`. Modul hat bereits
  einen `logger` (`:23`).
- `build_trip_corridor_id_map()` (`email/html.py:615-618`): dieselbe
  Technik im `except (KeyError, TypeError)`-Zweig; das Modul hat noch
  **keinen** `logger` — `import logging` + `logger =
  logging.getLogger(__name__)` sind Teil dieser Änderung. Der bestehende
  Docstring-Absatz (`:602-604`, „Nicht auflösbare Einträge … werden still
  übersprungen") muss auf den neuen, sichtbaren Zustand nachgezogen
  werden — er beschreibt sonst ein Verhalten, das nicht mehr stimmt.

Beide Änderungen müssen den `resolution_loss_guard`-Wächter selbst
zufriedenstellen: das „Sammeln-und-melden"-Muster (Liste befüllen, NACH
der Schleife/am Funktionsende meldenden `logger.warning`-Aufruf mit der
Liste als Argument) ist genau das, was `_branch_is_safeguarded()` als
„nicht still" erkennt. Eine Meldung direkt im `except`-Zweig wäre
ebenfalls zulässig, wählt aber nicht das im Projekt etablierte Muster.

### AP2 — Wächter-Schlüssel auf `datei::funktion::ordinal` umstellen

Betroffen: `test_success_status_guard.py`, `test_resolution_loss_guard.py`,
`test_output_timezone_guard.py`. Der neue Schlüssel ersetzt den heutigen
zeilenbasierten Schlüssel (`"pfad:zeile"`) durch
`"pfad::funktion::ordinal"`, wobei `ordinal` die Position des Fundes
**innerhalb dieser Funktion in Scan-Reihenfolge** ist (0-basiert oder
1-basiert, konsistent über alle drei Wächter).

- **`test_success_status_guard.py`** und **`test_resolution_loss_guard.py`**
  führen bereits eine funktionsbewusste `_scopes()`-Funktion (`:326` bzw.
  `:157`) und tragen den Funktionsnamen schon **im Wert**
  (`f"{KIND}::{scope_name}"`). Der Umbau verschiebt diese Information vom
  Wert in den Schlüssel und ergänzt das Ordinal — keine neue
  Scanner-Fähigkeit nötig.
- **`test_output_timezone_guard.py`** hat **keine** Scope-Verfolgung
  (`_find_violations()` läuft mit blankem `ast.walk(tree)`, `:191`). Hier
  muss `_scopes()` (Vorbild: die beiden anderen Wächter, identische
  Semantik: Modulraum + jeder Funktionsraum, verschachtelte Funktionen
  eingeschlossen, `_MODULE_SCOPE = "<module>"` für Modulebene-Funde) neu
  gebaut und in `_find_violations()` eingehängt werden, ohne die
  bestehende Fund-Logik (`raw_astimezone`, `hardcoded_zone_abbrev`,
  `silent_tz_default`, `silent_tz_or_fallback`,
  `silent_tz_getattr_fallback`, `silent_tz_none_guard`,
  `silent_tz_ternary`) zu verändern.
- **Mitzuziehen:** `INTENTIONAL_CONSTANT_SUCCESS`/`_WEBHOOK_ACK_LOCATION`
  (`test_success_status_guard.py:268`, `:1614-1615`, an drei Stellen als
  Schlüssel benutzt — u.a. `test_scanner_flags_and_documents_the_
  intentional_constant_success`, `:3093-3114`) ist ebenfalls zeilenbasiert
  und muss auf denselben Schlüsseltyp migriert werden, sonst bleibt genau
  dieselbe Bombe mit längerer Lunte im selben Wächter liegen.

**Ordinal ist zwingend** (nicht optional): ohne es kollabieren die 9
Mehrfachfunde in 5 Funktionen (`trip_command_processor.py::_handle_query`
×4, `notification_service.py::send_official_alert` ×3,
`notification_service.py::_dispatch_alert_message` ×3,
`trip_command_processor.py::_trigger_on_demand` ×2,
`geosphere_warn.py::_extract_alerts` ×2) auf 5 Einträge — die
Ratschen-Tests (`test_no_unlisted_resolution_drops`/
`test_known_violations_only_shrink`-Äquivalente in allen drei Wächtern)
würden dann einen Teil der real gefundenen Verstöße gar nicht mehr sehen
können, weil zwei verschiedene Funde denselben Schlüssel teilen.

### AP3 — Roundtrip-Invariante umstellen (Test, nicht Code)

`test_ac13_report_config_byte_identical_after_roundtrip`
(`test_trip_flat_fields_dual_read.py:112-126`) wird von einer
Byte-Identitäts-Prüfung (`rt["report_config"] == d["report_config"]`) auf
eine Prüfung umgestellt, die genau das festnagelt, was tatsächlich gilt:

1. Kein Schlüssel, der im Original vorhanden war, verschwindet nach dem
   Roundtrip (Mengenvergleich der Schlüssel: `original.keys() <=
   roundtripped.keys()`).
2. Für jeden Schlüssel außer `updated_at` (strukturell nicht
   byte-identisch reproduzierbar, `loader.py:604`) gilt: entweder ist der
   Wert unverändert, oder er wechselt von „Schlüssel fehlte im Original"
   zu `None` — niemals von einem gesetzten Wert zu etwas anderem als
   diesem Wert.
3. Ein **gesetztes** Tagesfenster (`day_window_start_hour`/`_end_hour`
   mit echten Stunden, nicht `None`) übersteht den Roundtrip
   unverändert — das ist die im aktuellen Test unter der
   Byte-Identität versteckte, eigentlich relevante Aussage (AC-6).

Produktivcode (`loader.py`) bleibt in AP3 vollständig unangetastet — s.
„Warum AP3 den Test ändert und nicht den Code".

## Acceptance Criteria

- **AC-1:** Given `normalize_hourly_metrics()` erhält eine gespeicherte
  Stundenauswahl mit einer `metric_id`, die im Register nicht existiert
  / When die Funktion diese Auswahl auflöst / Then wird die unbekannte
  Kennung nicht mehr kommentarlos verworfen, sondern über
  `logger.warning` mit der konkreten Kennung und Issue-Bezug protokolliert,
  während die restliche Liste unverändert korrekt aufgelöst wird.
  - Test: Log-Capture-Test ruft `normalize_hourly_metrics()` mit einer
    Mischung aus gültigen und einer unbekannten `metric_id` auf und
    prüft, dass die unbekannte Kennung im Log-Text auftaucht — kein
    Dateiinhalt-Check, sondern echtes Funktionsverhalten.

- **AC-2:** Given `build_trip_corridor_id_map()` verarbeitet den
  Compare-Metrik-Katalog und trifft auf einen Eintrag, dessen `metric_id`
  im Register nicht auflösbar ist (`KeyError`/`TypeError`) / When die
  Funktion die Korridor-ID-Abbildung baut / Then wird der Verlust über
  `logger.warning` mit der konkreten Kennung sichtbar gemeldet, statt
  wortlos zu verschwinden.
  - Test: Log-Capture-Test mit präpariertem Katalog-Eintrag, dessen
    `metric_id` nicht im Register steht; Log-Text enthält die Kennung.

- **AC-3:** Given eine neue Zeile wird oberhalb einer bereits in
  `KNOWN_VIOLATIONS` gelisteten Fundstelle in eine gescannte Datei
  eingefügt (z. B. eine Kommentarzeile) / When einer der drei Wächter
  (`test_success_status_guard.py`, `test_resolution_loss_guard.py`,
  `test_output_timezone_guard.py`) danach läuft / Then erkennt er den
  Fund weiterhin unter demselben Schlüssel — der Wächter wird NICHT rot,
  obwohl sich die Zeilennummer verschoben hat.
  - Test: Für jeden der drei Wächter wird in einer temporären Kopie der
    gescannten Datei tatsächlich eine Zeile eingefügt (kein
    Gedankenexperiment) und der Scan erneut ausgeführt; die
    Fundmenge (Schlüssel) bleibt identisch zum Lauf ohne Einfügung.

- **AC-4:** Given eine Funktion enthält mehrere unabhängige stille
  Auflösungsverluste (z. B. `trip_command_processor.py::_handle_query`
  mit vier Fundstellen) / When der Wächter über diese Funktion läuft /
  Then bleiben alle Funde als einzeln unterscheidbare Einträge erhalten
  — sie fallen nicht auf einen einzigen Eintrag pro Funktion zusammen.
  - Test: Für alle fünf bekannten Mehrfachfund-Funktionen (insgesamt 9
    Funde) wird geprüft, dass die Anzahl der Schlüssel mit diesem
    `datei::funktion`-Präfix der Anzahl der tatsächlichen Funde
    entspricht, nicht 1.

- **AC-5:** Given `test_output_timezone_guard.py` hat heute keine
  funktionsbewusste Scope-Verfolgung / When der Wächter nach dieser
  Lieferung läuft / Then schlüsselt er seine `KNOWN_VIOLATIONS` nach
  demselben `datei::funktion::ordinal`-Schema wie die beiden anderen
  Wächter — inklusive korrekter Funktionszuordnung für verschachtelte
  Funktionen und Modulebene-Funde.
  - Test: Synthetischer Wirkungsnachweis (analog den bestehenden
    Wirkungsnachweisen der anderen beiden Wächter) mit zwei Funden in
    zwei verschiedenen Funktionen derselben Datei — beide erscheinen mit
    unterschiedlichem Funktionsanteil im Schlüssel.

- **AC-6:** Given ein Trip mit einem **gesetzten** Tagesfenster
  (`day_window_start_hour`/`_end_hour` mit gültigen, unterschiedlichen
  Stunden) / When er geladen und wieder serialisiert wird
  (`_trip_to_dict(load_trip_from_dict(d))`) / Then sind beide Werte nach
  dem Roundtrip identisch zu den Ausgangswerten — das ist die Aussage,
  die tatsächlich geprüft werden muss, nicht Byte-Identität des gesamten
  `report_config`-Blocks.
  - Test: `test_ac13_...` (umbenannt/umformuliert) mit einem Tagesfenster
    ungleich der Default-Werte im Input; Assertion vergleicht exakt diese
    zwei Felder vor/nach Roundtrip.

- **AC-7:** Given ein bereits gesetztes Tagesfenster soll zurückgesetzt
  werden (ungültiges oder leeres Paar wird geschrieben) / When der
  Schreibpfad läuft / Then verschwindet das Fenster tatsächlich von der
  Platte — der Persistenzpfad (`_deep_merge_preserve_unknown`, RMW-Merge)
  bleibt durch die Testumstellung dieser Lieferung unangetastet
  funktionsfähig.
  - Test: Regressionslauf des bestehenden, unveränderten
    `TestUpdateTripHandler_ClampsInvalidDayWindowPairOnWrite`
    (`internal/handler/trip_day_window_write_seam_test.go:31-82`) bleibt
    grün — kein neuer Test nötig, dieser AC ist ein Nicht-Regressions-Beleg
    dafür, dass AP3 den Schreibpfad nicht berührt.

- **AC-8:** Given alle drei Arbeitspakete sind umgesetzt / When die
  betroffenen Kern-Testdateien
  (`tests/test_success_status_guard.py`,
  `tests/test_resolution_loss_guard.py`,
  `tests/test_output_timezone_guard.py`,
  `tests/test_trip_flat_fields_dual_read.py`) sowie die beiden
  betroffenen Produktivdateien-Tests laufen / Then sind alle grün, ohne
  dass eine Erwartung (Schwellenwert, Fundliste, Assertion) nur
  „passend gemacht" statt tatsächlich erfüllt wurde.
  - Test: voller Lauf der vier genannten Testdateien, Exit 0; stichprobenhafte
    Prüfung, dass keine `KNOWN_VIOLATIONS`/`SPEC_LISTED_FINDINGS`-Zahl
    gesenkt wurde, um Rot zu vermeiden (Test-Politik: Schwellen nie
    manipulieren).

## Bekannte Grenzen des neuen Schlüssels

Der neue Schlüssel `datei::funktion::ordinal` beseitigt das
Verschiebungsproblem nicht — er verschiebt es von „jede Einfügung" auf
„jede Umbenennung". Vier Grenzen bleiben ausdrücklich bestehen:

| Grenze | Beleg |
|---|---|
| **Funktion umbenannt/aufgeteilt bricht ihn ebenso.** | Genau das reißt heute `test_scanner_finds_every_spec_listed_finding` — und diese Liste ist bereits zeilenfrei. Der neue Schlüssel verschiebt das Problem von „jede Einfügung" auf „jede Umbenennung", nicht auf null. |
| **Kein Klassenkontext.** | `_scopes()` liefert flaches `node.name`. Zwei gleichnamige Methoden in verschiedenen Klassen derselben Datei sind über den Schlüssel nicht unterscheidbar — 11 mehrdeutige Namen in der Erfolgs-, 14 in der Auflösungs-Scanfläche (`dispatch_orchestrator.py` 6×). Heute ist kein bekannter Fund davon betroffen, aber ein künftiger könnte es sein. |
| **Ordinal verschiebt sich beim Reparieren.** | Wird einer von mehreren Funden in derselben Funktion behoben, wandern die Ordinale der übrigen. Trifft nur die Kollisionsfunktionen mit mehr als einem Fund, und genau in dem Moment, in dem man die Liste ohnehin anfasst — kein Überraschungseffekt, aber kein automatischer Selbstheilungs-Mechanismus. |
| **Modulebene bündelt unter einem Pseudo-Funktionsnamen.** | Funde außerhalb jeder Funktion tragen den Platzhalter `<module>` (`_MODULE_SCOPE`). Mehrere solcher Funde in derselben Datei sind nur noch über das Ordinal, nicht mehr über einen aussagekräftigen Funktionsnamen unterscheidbar — der Schlüssel bleibt korrekt, verliert an dieser Stelle aber an Lesbarkeit. |

Der Schlüssel ist damit ein **Verschiebungsschutz gegen Zeileneinfügung**,
keine allgemeine Umbenennungs- oder Struktursicherheit. Diese Ehrlichkeit
ist bewusst — ein Wächter, der seine Grenzen nicht kennt, täuscht
Sicherheit vor, die er nicht liefert.

## Warum AP3 den Test ändert und nicht den Code

`_trip_to_dict()` (`loader.py:1521-1553`) emittiert alle 29
`report_config`-Schlüssel **unbedingt**, auch wenn sie leer/`None` sind.
Der naheliegende Fix für Byte-Identität wäre, leere Schlüssel
wegzulassen — das ist aber die falsche Lösung: `save_trip()`
(`:1629-1644`) mergt den Python-Output per
`_deep_merge_preserve_unknown()` (`:124-136`) gegen die vorhandene
Datei auf der Platte, und dieser Merge **rekursiert in
`report_config` hinein**. Ein fehlender Schlüssel im Overlay lässt den
alten Plattenwert stehen statt ihn zu löschen. Würde `day_window_start_
hour`/`_end_hour` bei `None` weggelassen, wäre ein einmal gesetztes
Tagesfenster **nie wieder löschbar** — genau die Falle, die bereits
einmal aufgeschlagen ist und als Warnung im Code steht
(`loader.py:1554-1562`, Issue #1250 Scheibe 4 F002). Der reale Pfad, der
das verlangt (Zurücksetzen eines gesetzten Tagesfensters über die API),
ist in `internal/handler/trip_day_window_write_seam_test.go:48-80`
bereits als Testfall vorhanden (AC-7).

Die geprüfte Invariante selbst ist außerdem strukturell unerreichbar:
`updated_at` wird bei **jedem** Laden auf `datetime.now()` gesetzt
(`loader.py:604`), sofern kein `updated_at` im Input steht — Byte-
Identität ist für dieses Feld per Definition ausgeschlossen, unabhängig
von jeder Codeänderung. Gemessen wurde außerdem: ein bereits **gesetztes**
Tagesfenster übersteht den heutigen Roundtrip bereits unverändert; es
kommen nur die beiden Felder als `None` **hinzu**, wenn sie im Original
komplett fehlten — nichts verschwindet, es entsteht kein Datenverlust.
`wind_exposition_min_elevation_m` und `paused_until` zeigen denselben
Effekt und stehen nur zufällig in der Testvorlage.

**Entscheidung (Tech Lead, 2026-08-02):** Der Test wird auf die
tragfähige Aussage umgestellt — es geht keine Information verloren, und
es kommt keine hinzu, die etwas anderes bedeutet als ihre Abwesenheit.
`day_window_* = None` bedeutet exakt dasselbe wie „Schlüssel fehlt"
(`_clamped_day_window()`, `loader.py:98-121`, kennt keinen dritten
Zustand). Der Produktivcode bleibt unangetastet — einen Test, der eine
unhaltbare Invariante fordert, verbiegt man nicht mit Produktivcode, man
korrigiert die Erwartung des Tests.

## AP4 — vier Registrierungen am Hygiene-Gate

**Nachtrag 2026-08-02, nach der Freigabe hinzugekommen (Adversary-Befund F002).** Diese
Spec wurde mit einem Dreier-Zuschnitt freigegeben. AP4 kam erst im GREEN-Auftrag dazu,
nachdem der RED-Lauf vier weitere rote Kern-Tests zutage gefördert hatte, die in der
Ausgangsmessung nicht standen. Der Prüfer hat zu Recht bemängelt, dass die Buchführung
fehlte — hier ist sie nachgeholt. Inhaltlich ist AP4 unabhängig bestätigt.

`tests/tdd/test_765_backend_hygiene_compliance.py::test_765_no_product_source_read` schlägt
für vier Dateien an. Sie lesen Produktquelltext als **Daten** für eine Strukturregel — die
Werkzeugklasse, für die das Projekt bereits eine Registrierung kennt (`# doc-compliance-test`
plus Eintrag in `_SELF_EXEMPT`; Vorbilder `test_report_config_scheduler_structure.py`,
`test_dispatch_orchestrator.py`).

| Datei | Einordnung |
|---|---|
| `tests/test_api_contract_drift.py` | Route-/JSON-Tag-Inventar gegen die Doku — Werkzeugklasse, Marker war bereits vorhanden |
| `tests/test_egress_inventory_drift.py` | Go-Hostliste als Text gegen die per Import geladene Python-Liste (Go ist aus Python nur als Text erreichbar) — Werkzeugklasse |
| `tests/test_mail_recipient_parity.py` | Go-Konstantenmengen + AST-Verzweigungsratsche; der Verhaltensteil ruft den echten Guard mit Sentinel — Werkzeugklasse |
| `tests/tdd/test_validator_log_unique_filenames.py` | **weder Werkzeugklasse noch Verstoß — Fehlalarm des Gates**, s.u. |

**Der vierte Fall ist ein Gate-Fehler, kein Testfehler.** Die Datei liest gar keinen
Produktquelltext: ihre `read_text()`-Ziele sind YAML-Protokolle unter `tmp_path`, und die
vier Produktpfade in `_GATE_CASES` sind reine Namensdaten (der Test legt gleichnamige
Attrappen an). Weil ein `read_text()`-Ziel eine Comprehension-Variable ist, erntet
`_collect_listed_product_paths()` **jedes** Listen-/Tupel-Literal der Datei — auch solche,
die keine Dateiliste sind.

**Die Gate-Logik wurde bewusst nicht angefasst** (das wäre Aufweichen eines Gates für den
eigenen Blocker). Die Datei steht mit ausdrücklichem Vermerk „Fehlalarm, nicht
Werkzeugklasse" in `_SELF_EXEMPT`. Das ist ein Kompromiss mit einem benannten Preis: ein
späterer **echter** Quelltext-Zugriff in genau dieser Datei würde nicht mehr gefangen.
Die saubere Lösung — `_collect_listed_product_paths()` auf homogene Pfadlisten beschränken
— gehört in ein eigenes Ticket (Kategorie „fälschlich blockierendes Gate").

## Nachweisführung

Kein Mailversand nötig — diese Lieferung fasst keine Mail-Renderer im
Sinne des Renderer-Commit-Gates (#811) an (weder `compare_html.py` noch
`trip_report.py`/`sms_trip.py`/`compact_summary.py`/`alert/*.py` sind
betroffen).

1. **AP1:** Log-Capture-Tests für `normalize_hourly_metrics()` und
   `build_trip_corridor_id_map()` grün; danach der
   `resolution_loss_guard`-Wächter selbst grün (die beiden reparierten
   Stellen verschwinden aus `KNOWN_VIOLATIONS`, `test_known_violations_
   only_shrink` erzwingt das Entfernen).
2. **AP2 — Einfüge-Nachweis (Pflicht, kein Gedankenexperiment):** für
   jeden der drei Wächter wird in einer temporären Kopie einer gescannten
   Datei tatsächlich eine Zeile oberhalb einer bekannten Fundstelle
   eingefügt, der Scan erneut ausgeführt und die Fundmenge (Schlüssel)
   mit dem Lauf ohne Einfügung verglichen — identisch trotz
   verschobener Zeilennummer. Zusätzlich: die drei vollen Wächter-Läufe
   sind grün.
3. **AP3:** `tests/test_trip_flat_fields_dual_read.py` voll grün,
   insbesondere der umgestellte Test; als Regressionsbeleg für den
   unangetasteten Schreibpfad läuft
   `TestUpdateTripHandler_ClampsInvalidDayWindowPairOnWrite`
   (Go) unverändert grün.
4. **Gesamt:** `uv run pytest tests/test_success_status_guard.py
   tests/test_resolution_loss_guard.py tests/test_output_timezone_guard.py
   tests/test_trip_flat_fields_dual_read.py` — alle grün, keine
   gesenkten Schwellen/gekürzten Erwartungsmengen (Test-Politik).

## Known Limitations

- Die zwei bereits erfolgten **Funktions-Aufteilungen**
  (`_extract_alerts_from_cap` → `_collect_cap_info_entries` +
  `_group_and_map_info_entries`, Issue #1445) bleiben auch mit dem
  neuen Schlüssel **Handarbeit** — eine Aufteilung ändert den
  Funktionsnamen-Teil des Schlüssels, der Wächter kann das nicht
  automatisch nachziehen. Wer eine gelistete Funktion aufteilt, muss die
  betroffenen `KNOWN_VIOLATIONS`-Einträge von Hand auf die neuen
  Funktionsnamen umschlüsseln.
- Die vier „Bekannten Grenzen des neuen Schlüssels" oben gelten
  unverändert fort — der Schlüssel ist ein Verschiebungsschutz, keine
  Umbenennungssicherheit.
- Diese Lieferung repariert nur die **beiden in AP1 genannten**
  Fundstellen. Die übrigen ~20 bereits bekannten stillen
  Auflösungsverluste aus #1405 (A1–A13 + 9 neu gefundene) bleiben in
  `KNOWN_VIOLATIONS` stehen — ihre Reparatur ist eine eigene Scheibe
  (S4), nicht Teil dieser Lieferung.
- `internal/` (Go) bleibt für den `resolution_loss_guard`- und den
  `output_timezone_guard`-Wächter strukturell unerreichbar (Python-AST-
  Scan) — bewusste, bereits dokumentierte Lücke, durch diese Lieferung
  nicht verändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Lieferung trifft keine neue Grundsatzentscheidung
  auf einer der in `docs/adr/README.md` genannten Entscheidungsflächen
  (Kanäle, Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie). Die Tech-Lead-Entscheidung zu AP3 (Test statt
  Code anpassen) ist eine lokale, im Abschnitt „Warum AP3 den Test
  ändert und nicht den Code" begründete Einzelfallentscheidung, keine
  wiederverwendbare Architekturregel.

## Changelog

- 2026-08-02: Initial spec created — Issue #1466 unter Dach-Issue #1196.
  Basiert auf `docs/context/fix-1466-kern-suite-gruen.md` (Stand
  `fda6e10d`).
