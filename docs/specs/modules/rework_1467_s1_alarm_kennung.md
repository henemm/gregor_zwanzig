---
entity_id: rework_1467_s1_alarm_kennung
type: refactor
created: 2026-08-03
updated: 2026-08-03
status: draft
version: "1.0"
tags: [alerts, trip, compare, epic-1458, issue-1467, schema]
---

# Alarm-Protokoll: eine Kennung statt zwei Feldern (Issue #1467 Scheibe S1, Epic #1458 Teil 2)

## Approval

- [x] Approved — PO-„go" 2026-08-03 (12 ACs freigegeben, inkl. Anhebung des LoC-Limits auf 500
      für diesen Durchgang)

## Purpose

Das Alarm-Protokoll (`alert_log.json`) trägt seit #1459 **zwei** Kennungsfelder: `trip_id` für
Touren und `preset_id` für Ortsvergleiche. Diese Trennung hat keinen fachlichen Grund — sie
existiert allein, weil die Go-Zählung `AlertCountByTrip()` (`internal/store/log.go:94`) am Feld
`trip_id` hängt und beim Einführen des Vergleichs-Protokolls nicht angefasst werden sollte.

Die Folge ist ein nutzersichtbarer Fehler: Vergleichs-Einträge haben `trip_id == ""`, und die
Zählung wirft damit **alle** Ortsvergleiche aller Presets in einen gemeinsamen Topf unter dem
leeren Schlüssel. Kein Test deckt das heute ab.

Diese Scheibe ersetzt beide Felder durch **eine Kennung (`entity_id`) plus ein Typfeld
(`entity_type`)** und zieht Go-Speicher, Go-Handler und Frontend-Typen mit. Sie ist reiner Umbau
mit der Zielmarke „Verhalten unverändert" — mit genau einer bewussten Ausnahme: die getrennte
Zählung. Sie ist die **erste** von vier Scheiben in #1467 und muss vor den anderen laufen, weil
jede folgende Scheibe Protokoll-Einträge schreibt und damit Mischbestand erzeugt.

## Source

- **File:** `src/services/alert_log.py`
- **Identifier:** `append_entry()`

Betroffene Schichten — **alle drei** (Python-Kern, Go-API, Frontend):

| Datei | Änderung | Zweck |
|---|---|---|
| `src/services/alert_log.py` | MODIFY | `append_entry()` (`:117-201`): Parameter `trip_id`/`preset_id` → `entity_id`/`entity_type`; Serialisierung (`:173`, `:178`) entsprechend |
| `src/services/trip_alert.py` | MODIFY | 3 Aufrufstellen: `:277` (Vorhersage-Änderung), `:868` (Nowcast), `:1136` (amtliche Warnung) |
| `src/services/compare_alert.py` | MODIFY | 1 Aufrufstelle `:145` |
| `src/services/compare_radar_alert.py` | MODIFY | 1 Aufrufstelle `:124` |
| `src/services/compare_official_alert.py` | MODIFY | 1 Aufrufstelle `:140`; der Kommentar `:138` („Vergleichs-Eintrag mit leerem `trip_id` + `preset_id`") wird gegenstandslos und fällt |
| `internal/store/log.go` | MODIFY | `AlertLogEntry` (`:42-49`) bekommt `EntityID`/`EntityType`; neue Lese-Regel für Altformat; `AlertCountByTrip()` (`:90-104`) → `AlertCountByEntity()` |
| `internal/handler/archive_stats.go` | MODIFY | `:21` ruft die umbenannte Funktion |
| `internal/handler/cockpit.go` | MODIFY | keine Logik-Änderung; die Antwort trägt durch den erweiterten Typ die neuen Felder |
| `frontend/src/lib/types.ts` | MODIFY | `AlertLogEntry` (`:558-563`) |
| `frontend/src/routes/+page.svelte` | MODIFY | Filter `:109` prüft Kennung **und** Typ |
| `docs/specs/modules/feat_1459_alert_protokoll.md` | MODIFY | Design-Entscheidung D2 fortschreiben |

## Estimated Scope

- **LoC:** ~100 Produktivcode (Python ~35, Go ~55, Frontend ~10), ~260 Tests ⇒ **~360 gesamt,
  über dem 250er-Budget**. `loc_limit_override 500` braucht PO-Freigabe vor Implementierungsbeginn.
- **Files:** 10 geändert, 0 neu, 0 gelöscht; 3–4 Testdateien neu bzw. erweitert
- **Effort:** medium
- **Risiko:** MITTEL — nicht der Schreibpfad ist gefährlich, sondern die Go-Lese-Regel. Greift sie
  nicht, zeigt das Cockpit stumm null Alarme, und eine leere Kachel sieht aus wie „keine Alarme".

## Dependencies

- **Upstream:** #1459 (Protokoll-Format, live seit 2026-08-02, `161db8bb`), #1460 T1 (live seit
  2026-08-03, `8f2053f9`) — beide abgeschlossen.
- **Downstream:** #1467 S2/S3/S4 bauen auf dem hier festgelegten Feldnamen und Typ-Vokabular auf.
  Ein späterer Rename wäre ein zweiter Formatwechsel.
- **Berührt nicht:** `AlertStateService`, `ThrottleStore`, `NotificationService`,
  `DeviationAlertEngine` — deren Kennungen bleiben unverändert.

## Gemessener Ist-Stand der Bestandsdaten (2026-08-03)

| Nutzer | Einträge | Altformat (4 Felder) | Neuformat (#1459) |
|---|---|---|---|
| `default` | 79 | 79 | 0 |
| `henning` | 112 | 110 | 2 |
| `steffi` | 31 | 31 | 0 |
| **Summe** | **222** | **220** | **2** |

`preset_id` ist in **0 von 222** Einträgen gesetzt, `trip_id` in **allen 222**. Es gibt bis heute
keinen einzigen Vergleichs-Eintrag im Protokoll. Der Schlüssel `not_delivered` existiert in keiner
Datei.

⚠️ Die Issue-Beschreibung sagt „220 Einträge, alle ausschließlich mit den vier Altfeldern" — das
war am 2026-08-02 richtig, seither hat der Produktivbetrieb 2 Neuformat-Einträge erzeugt. Der
Kern der Begründung bleibt gültig und wird durch die Messung sogar schärfer: zu migrieren ist
ausschließlich „`trip_id` → Kennung, Typ = Tour".

## Implementation Details

### Namenswahl

`entity_id` (string) + `entity_type` (string). Zulässige Werte des Typfelds in dieser Scheibe:
`"trip"` und `"compare"`.

`entity_id` ist im Alarm-Bereich bereits das etablierte Wort: `AlertStateService`
(`alert_state.py:50-100`) und beide Compare-Pfade (`compare_alert.py:10`,
`compare_radar_alert.py:174-182`) nennen ihre Kennung so. Ein drittes Vokabular würde einen
vierten Namen für dieselbe Sache einführen.

`entity_type` bleibt bewusst ein **freier String**, kein geschlossenes Enum — dieselbe Begründung
wie bei den Nicht-Zustellungs-Gründen (`alert_log.py:33-37`): künftige Typen docken additiv an,
ohne Schema-Migration.

### Altlesbarkeit — Lese-Regel, keine Datei-Migration

Bestandsdateien werden **nicht** umgeschrieben. Beim Lesen (Go) gilt:

```
entity_id   := entry.entity_id   wenn nicht leer, sonst entry.trip_id
entity_type := entry.entity_type wenn nicht leer, sonst "trip"
```

Warum nicht migrieren: Ein Umschreiben der Protokolldateien ist der einzige Weg, bei dem ein
Fehler die Historie unwiederbringlich beschädigt — das Muster von BUG-DATALOSS-GR221. Die
Lese-Regel kostet ~8 Zeilen und ist rückwirkend folgenlos. Präzedenzfall im Haus:
`ThrottleStore._migrate_flat_file()` (`throttle_store.py:185-201`) migriert ebenfalls beim Lesen.

Die zwei Neuformat-Einträge werden von derselben Regel getragen (`trip_id` gefüllt,
`entity_id` fehlt).

### Kein Doppelschreiben

Neue Einträge tragen **nur** `entity_id` + `entity_type`, nicht zusätzlich `trip_id`/`preset_id`.
Ein Übergangs-Doppelschreiben würde genau den Zustand verlängern, den diese Scheibe beseitigt,
und S2–S4 würden ihn erben. Das Zeitfenster, in dem neuer Python-Code auf altem Go-Code träfe,
liegt bei Sekunden (`deploy-gregor-prod.sh` startet alle drei Dienste in einem Lauf); im
schlimmsten Fall fehlt ein einzelner Eintrag vorübergehend in der 24-h-Kachel. Die Datei selbst
bleibt in jedem Fall vollständig.

### Zählung im Archiv

`AlertCountByTrip()` → `AlertCountByEntity()`, Schlüssel `"<typ>:<kennung>"`, z. B.
`"trip:5f534011"` oder `"compare:abc123"`. Damit verschwindet der Sammel-Schlüssel `""`, und
Touren und Presets sind unterscheidbar, ohne sich auf die Kollisionsfreiheit zweier unabhängiger
Kennungsräume zu verlassen.

`/api/archive/stats` hat **keinen Frontend-Konsumenten** (gemessen: kein Treffer in
`frontend/src`), und `docs/reference/api_contract.md:27` nennt nur Pfad und Methode, kein
Antwortschema. Der Vertrag ist damit frei änderbar.

`BriefingCountByTrip()` bleibt unangetastet — Vergleichs-Briefings protokollieren dort nicht.

### Frontend-Filter

`+page.svelte:109` filtert heute `a.trip_id === hero?.id`. Künftig:
`a.entity_type === 'trip' && a.entity_id === hero?.id`. Der Typ-Vergleich ist kein Beiwerk: Nach
der Vereinheitlichung liegen Tour- und Preset-Kennungen im selben Feld, eine Gleichheit allein
wäre nicht mehr eindeutig.

## Nicht-Ziele / bewusst unverändert

- **Die Ablaufsteuerungen werden nicht zusammengelegt** — das ist S2–S4. Diese Scheibe fasst
  ausschließlich das Protokoll-Format an.
- **`BriefingLogEntry` bleibt unverändert** (`log.go:9-14`), obwohl es dasselbe Muster zeigt.
  Vergleichs-Briefings schreiben dort gar nicht; eigener Gegenstand, nicht Teil von #1467.
- **`not_delivered` bleibt für Go unsichtbar** (D4 aus #1459) — Cockpit-Kachel und
  Archiv-Statistik ändern sich für Bestandstouren um keine Zahl.
- **D1 bleibt gültig** (#1459): EIN Eintrag je Meldung, Kanäle als Listen innerhalb des Eintrags.
- Keine Änderung an Auslöse-Logik, Schwellen, Kanälen, Ruhezeiten oder Tages-Obergrenzen.

## Regressionsgefahr

| Gefahr | Absicherung |
|---|---|
| Go liest die neuen Felder nicht ⇒ Cockpit-Kachel stumm leer | AC-5, AC-6 prüfen den vollen Weg Datei → Go → JSON |
| Altbestand wird nicht mehr zugeordnet ⇒ 220 Einträge verschwinden aus dem Cockpit | AC-4 mit echtem Altformat-Bestand |
| Neue Schlüsselform bricht die Archiv-Zählung | AC-7, AC-8 |
| Frontend filtert gegen ein nicht mehr existierendes Feld | AC-9 |
| Cross-User-Vermischung durch Anfassen von `log.go` | AC-10 (zwei Nutzer) |
| Bestandsdatei wird beim Schreiben beschädigt | AC-3 (Zuwachs-Vergleich) |

## Prüfung mit zwei Nutzern

`AlertCountByEntity()` und der Cockpit-Handler sind `WithUser`-gebunden. AC-10 verlangt einen
Durchlauf mit zwei Nutzern, die je eigene Protokolldateien mit **gleichlautenden Kennungen**
haben — kein Eintrag darf über die Nutzergrenze sichtbar werden. Vorbild:
`internal/handler/archive_stats_test.go:125-146`.

## Acceptance Criteria

**Schreibpfad (Python)**

- **AC-1:** Given ein Tour-Alarm wird ausgelöst, When `append_entry()` den Eintrag schreibt,
  Then trägt der Eintrag `entity_id` = Tour-Kennung und `entity_type` = `"trip"` und **weder**
  `trip_id` **noch** `preset_id`.
  - Test: `append_entry(user, entity_id="t1", entity_type="trip", …)` aufrufen, geschriebene JSON
    laden, Feldbestand exakt prüfen (beide Altfelder abwesend).

- **AC-2:** Given ein Ortsvergleichs-Alarm wird ausgelöst, When `append_entry()` den Eintrag
  schreibt, Then trägt der Eintrag `entity_id` = Preset-Kennung und `entity_type` = `"compare"`.
  - Test: Aufruf aus `compare_alert.py`-Pfad, JSON prüfen.

- **AC-3:** Given eine Bestands-Protokolldatei mit 220 Alt-Einträgen, When ein neuer Eintrag
  angehängt wird, Then sind die 220 Alt-Einträge danach **feldweise unverändert** und die Datei
  enthält genau einen Eintrag mehr — kein Alt-Eintrag wird um `entity_id`/`entity_type` ergänzt
  oder umgeschrieben.
  - Test: echte Bestandsdatei-Kopie als Fixture, vorher/nachher-Vergleich der ersten 220 Einträge
    Element für Element.

**Lesepfad Altbestand (Go)**

- **AC-4:** Given eine Protokolldatei mit ausschließlich Alt-Einträgen (`trip_id` gefüllt, kein
  `entity_id`), When `LoadAlertLog()` sie liest, Then liefert jeder Eintrag `EntityID` = der alte
  `trip_id`-Wert und `EntityType` = `"trip"`.
  - Test: `seedAlertLog` mit vier Altformat-Einträgen, geladene Struktur prüfen.

- **AC-5:** Given dieselbe Alt-Datei, When `GET /api/cockpit/status` aufgerufen wird, Then
  enthält die Antwort für jeden Eintrag der letzten 24 h die Felder `entity_id` und `entity_type`
  mit den abgeleiteten Werten — die Kachel zeigt dieselbe Anzahl Alarme wie vor dem Umbau.
  - Test: Handler via `httptest`, JSON dekodieren, Anzahl und Feldwerte prüfen.

- **AC-6:** Given eine Protokolldatei mit **gemischtem** Bestand (Alt-Einträge und neue Einträge
  mit `entity_type: "compare"`), When `GET /api/cockpit/status` aufgerufen wird, Then trägt jeder
  Eintrag den korrekten Typ — Alt-Einträge `"trip"`, neue Einträge ihren geschriebenen Wert.
  - Test: gemischte Seed-Datei, typweise Zählung prüfen.

**Zählung im Archiv (Go)**

- **AC-7:** Given eine Protokolldatei mit drei Alarmen für Tour `A`, einem für Tour `B` und zwei
  für Preset `P`, When `GET /api/archive/stats` aufgerufen wird, Then enthält die Antwort
  `{"trip:A": 3, "trip:B": 1, "compare:P": 2}` — insbesondere **kein** Schlüssel `""`.
  - Test: `seedAlertLog` mit sechs Einträgen, Antwort-Map exakt vergleichen.

- **AC-8:** Given eine Tour und ein Preset mit **derselben Kennung** `"x1"`, When
  `GET /api/archive/stats` aufgerufen wird, Then werden beide getrennt gezählt
  (`"trip:x1"` und `"compare:x1"`), nicht addiert.
  - Test: zwei Einträge mit gleicher Kennung, unterschiedlichem Typ.

**Frontend**

- **AC-9:** Given die Startseite mit einer aktiven Tour `hero` und einem Protokoll, das sowohl
  einen Alarm dieser Tour als auch einen Vergleichs-Alarm mit derselben Kennung enthält, When die
  Alarm-Liste der Tour gerendert wird, Then erscheint **nur** der Tour-Alarm.
  - Test: Frontend-Unit-Test gegen die Filter-Ableitung mit beiden Einträgen.

**Mandantentrennung**

- **AC-10:** Given zwei Nutzer `userA` und `userB` mit je eigener Protokolldatei, die
  gleichlautende Kennungen enthalten, When beide nacheinander `GET /api/archive/stats` und
  `GET /api/cockpit/status` aufrufen, Then sieht jeder ausschließlich die eigenen Einträge und
  die eigenen Zahlen.
  - Test: zwei Store-Kontexte, vier Handler-Aufrufe, kreuzweise Prüfung.

**Fail-soft (unverändertes Verhalten)**

- **AC-11:** Given die Protokolldatei fehlt oder ist unlesbares JSON, When
  `GET /api/cockpit/status` und `GET /api/archive/stats` aufgerufen werden, Then antworten beide
  mit `200` und leeren Strukturen — kein `500`.
  - Test: kein File / kaputtes File, beide Handler.

- **AC-12:** Given ein Eintrag ohne jede Kennung (`entity_id` und `trip_id` beide leer), When
  `LoadAlertLog()` ihn liest, Then wird er nicht verworfen und landet unter dem Schlüssel
  `"trip:"` — die Zählung bleibt vollständig, statt Einträge stumm zu schlucken.
  - Test: Seed mit einem kennungslosen Eintrag, Gesamtzahl prüfen.

## Known Limitations

- `/api/archive/stats` hat weiterhin keinen Frontend-Konsumenten. Diese Scheibe repariert die
  Zählung, macht sie aber nicht sichtbar — das wäre ein eigener Gegenstand.
- Die Alt-Einträge behalten dauerhaft ihr Vier-Feld-Format. Die Lese-Regel bleibt damit
  dauerhaft nötig; sie ist als bewusster, dokumentierter Bestandteil des Formats zu verstehen,
  nicht als vorübergehende Krücke.
- `entity_type` ist ein freier String. Ein Tippfehler in einer künftigen Aufrufstelle erzeugt
  einen neuen Typ statt eines Fehlers — bewusst in Kauf genommen (additive Erweiterbarkeit), aber
  ein Kandidat für einen Wächter, sobald ein dritter Typ entsteht.

## Changelog

- 2026-08-03: Initiale Spec. Zuschnitt S1 von #1467 PO-bestätigt
  (`#issuecomment-5163592914`). Bestandsdaten am 2026-08-03 nachgemessen (222 Einträge, davon 2
  im Neuformat) — korrigiert die Angabe der Issue-Beschreibung.
