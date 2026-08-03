# Context: rework-1467-s1-alarm-kennung

**Issue:** #1467 Scheibe S1 (Epic #1458, Teil 2 von #1460)
**Erstellt:** 2026-08-03
**Track:** Full Process (Intake 6/6)

## Request Summary

Das Alarm-Protokoll trägt seit #1459 **zwei** Kennungsfelder — `trip_id` und `preset_id` — ohne
fachlichen Grund; die Trennung existiert nur, weil die Go-Zählung `AlertCountByTrip()` am Feld
`trip_id` hängt. S1 ersetzt beide durch **eine Kennung plus ein Typfeld** und zieht Go-Speicher,
Go-Handler und Frontend-Typen mit. Nutzersichtbarer Gewinn: Vergleichs-Alarme werden im Cockpit
und in der Archiv-Statistik wieder getrennt gezählt statt alle zusammen unter dem leeren
Schlüssel `""`.

## Related Files

### Python — Schreibpfad

| Datei | Relevanz |
|---|---|
| `src/services/alert_log.py:117-201` | **Kernstück.** `append_entry()` serialisiert `trip_id` und `preset_id` als zwei getrennte Felder (`:173`, `:178`). Enthält die Read-Modify-Write-Mechanik über die volle Datei und die Zwei-Schlüssel-Ablage `entries` / `not_delivered` |
| `src/services/trip_alert.py:277`, `:868`, `:1136` | Drei Aufrufstellen mit `trip_id=trip.id` (Vorhersage-Änderung, Nowcast, amtliche Warnung) |
| `src/services/compare_alert.py:145` | Aufrufstelle Vergleich/Vorhersage-Änderung, `preset_id=` |
| `src/services/compare_radar_alert.py:124` | Aufrufstelle Vergleich/Nowcast |
| `src/services/compare_official_alert.py:140` | Aufrufstelle Vergleich/amtlich; Kommentar `:138` benennt das Doppelfeld ausdrücklich als Zwischenlösung |

### Go — Lesepfad

| Datei | Relevanz |
|---|---|
| `internal/store/log.go:42-49` | `AlertLogEntry` kennt **nur vier Felder** (`trip_id`, `sent_at`, `changes_count`, `severity`) — die #1459-Zusätze werden beim Unmarshal stillschweigend verworfen |
| `internal/store/log.go:90-104` | `AlertCountByTrip()` zählt nach `e.TripID`. Vergleichs-Einträge haben dort `""` ⇒ alle Presets landen in einem gemeinsamen Topf |
| `internal/handler/cockpit.go:22,36-41` | Liest das volle Log, filtert auf 24 h, gibt `AlertLogEntry`-Objekte 1:1 als JSON zurück |
| `internal/handler/archive_stats.go:21` | Gibt die Zähl-Map als `{"alerts": {tripID: n}}` zurück |
| `internal/router/router.go:193,195` | Routen `/api/cockpit/status` und `/api/archive/stats` |

### Frontend

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/types.ts:558-563` | `AlertLogEntry` spiegelt exakt die vier Go-Felder |
| `frontend/src/routes/+page.svelte:109` | `heroAlerts` filtert `a.trip_id === hero?.id` — **einzige** inhaltliche Verwendung der Kennung |
| `frontend/src/routes/+page.server.ts:18,26` | SSR-Fetch von `/api/cockpit/status`, fail-soft |

## Gemessener Ist-Stand der Bestandsdaten (2026-08-03)

⚠️ **Korrektur zur Issue-Beschreibung.** Das Issue sagt (Stand 2026-08-02): *„220 Einträge, alle
ausschließlich mit den vier Altfeldern"*. Das gilt so **nicht mehr** — seit #1459 live ist,
schreibt der Produktiv-Code das neue Format:

| Nutzer | Einträge | Altformat | Neuformat |
|---|---|---|---|
| `default` | 79 | 79 | 0 |
| `henning` | 112 | 110 | **2** (`forecast_change`, `official_alert`) |
| `steffi` | 31 | 31 | 0 |
| **Summe** | **222** | **220** | **2** |

**Der Kernpunkt bleibt aber gültig, und zwar schärfer formuliert:** `preset_id` ist in **keinem
einzigen** realen Eintrag gesetzt (0 von 222), `trip_id` ist in **jedem** Eintrag gefüllt. Es gibt
also bis heute **keinen einzigen Vergleichs-Eintrag im Protokoll** — das Doppelfeld war noch nie
in seiner eigentlichen Funktion befüllt. Genau deshalb ist die Zusammenlegung jetzt billig: zu
migrieren ist nur „`trip_id` → Kennung, Typ = Tour", nicht ein Mischbestand aus zwei Typen.

Der Schlüssel `not_delivered` existiert in **keiner** Datei — bisher war jeder Alarm auf
mindestens einem Kanal erreichbar.

## Existing Patterns

- **Read-Modify-Write mit Merge** (`alert_log.py:189-201`): volle Datei laden, anhängen, ganz
  zurückschreiben. Kaputte Datei ⇒ Warnung + Neuanlage, nie Absturz. Muster für die Migration.
- **Fail-soft auf der Go-Seite** (`log.go:56-72`): fehlende oder kaputte Datei ⇒ leere Liste,
  nie 500. Muss auch für unbekannte/fehlende Kennungsfelder gelten.
- **Additive Feld-Erweiterung ohne Schema-Migration** (`alert_log.py:33-37`): freie Strings statt
  geschlossener Enums, damit #1461 additiv andocken kann. Für das Typfeld übernehmen.
- **Generisches `entity_id`** — `AlertStateService` (`alert_state.py:7`) und `ThrottleStore`
  arbeiten bereits mit einer generischen Kennung; `compare_official_alert.py:243` bildet
  `f"{preset_id}:{loc_id}"`. Die Namenswahl für S1 sollte dazu passen, damit S2–S4 andocken.
- **Zwei-Nutzer-Test** als feste Form: `internal/handler/archive_stats_test.go:125-146`
  (`userA`/`userB`), `tests/tdd/test_alert_tenancy_two_users.py`.

## Dependencies

**Upstream (was der Schreibpfad braucht):** `app.loader.get_data_dir()`,
`app.metric_catalog.metric_and_aggregation_for_field()`, die fünf Aufrufstellen in den vier
Alarm-Diensten.

**Downstream (was vom Format abhängt):** `internal/store/log.go` → `cockpit.go` /
`archive_stats.go` → `/api/cockpit/status`, `/api/archive/stats` → `+page.server.ts` →
`+page.svelte:109`. **`/api/archive/stats` hat aktuell keinen Frontend-Konsumenten** (kein
Treffer in `frontend/src`) — der Endpunkt wird bereitgestellt, aber nicht angezeigt.

## Existing Specs & ADRs

- `docs/specs/modules/feat_1459_alert_protokoll.md` (v1.5, 16 ACs) — legt D1 (EIN Eintrag je
  Meldung, Kanäle als Listen darin), D2 (vier Altfelder unverändert) und D4 (`not_delivered` für
  Go unsichtbar) fest. **Diese Scheibe ändert D2 bewusst** und muss die Spec fortschreiben.
- `docs/specs/modules/rework_1460_t1_relevanzfilter.md` (v1.2, 34 ACs) — Zielverhalten, auf das
  S2–S4 aufbauen.
- `docs/context/rework-1460-alerts-relevanzfilter.md` — Analyse der vier Ablaufsteuerungen mit
  Zeilenbelegen.
- ADR-0043 (löst ADR-0040 ab), ADR-0021 (geteilte Engine).

## Bestehende Tests im Wirkbereich

Python: `tests/tdd/test_alert_log.py`, `test_alert_log_channels.py`, `test_alert_log_metrics.py`,
`test_alert_tenancy_two_users.py`, dazu 16 weitere Dateien mit `alert_log`-Bezug.
Go: `internal/handler/archive_stats_test.go`, `internal/handler/cockpit_test.go` (Helfer
`seedAlertLog`, `withUserCtx`, `newTestStore`).

## Risks & Considerations

1. **Stiller Datenverlust beim Format-Wechsel.** Go verwirft heute schon alle Felder, die es nicht
   kennt. Fällt `trip_id` weg, ohne dass Go die neue Kennung liest, zeigt das Cockpit **null
   Alarme** — und niemandem fällt es auf, weil die Kachel dann einfach leer ist. Beide Seiten
   müssen im selben Commit fallen, und ein Test muss die 220 Altbestands-Einträge über den
   vollen Weg (Datei → Go → JSON → Frontend-Filter) nachweisen.
2. **Altlesbarkeit ist Pflicht** (CLAUDE.md, BUG-DATALOSS-GR221): Die 220 Alteinträge tragen kein
   Typfeld. Sie müssen ohne Umschreiben der Datei als Typ „Tour" gelesen werden — eine
   Einmal-Migration der Datei wäre riskanter als eine Lese-Regel.
3. **`+page.svelte:109` vergleicht gegen `hero?.id`**, also eine Tour-Kennung. Nach dem Umbau
   muss der Filter zusätzlich den Typ prüfen, sonst zeigt eine Tour Alarme eines gleichnamigen
   Presets — heute unmöglich, nach der Vereinheitlichung denkbar.
4. **Mandantentrennung**: Zähl- und Cockpit-Pfad sind `WithUser`-gebunden; der Nachweis mit zwei
   Nutzern ist bei jeder Änderung an `log.go` fällig.
5. **Namenswahl bindet S2–S4.** Der Feldname der Kennung und das Vokabular des Typfelds werden in
   den folgenden drei Scheiben von allen Ablaufpfaden verwendet. Ein späterer Rename wäre ein
   zweiter Formatwechsel — die Entscheidung gehört ausdrücklich in die Spec, nicht in den Code.
6. **Zeilenbudget**: Python + Go + Frontend + Tests. Ohne Migrations-Skript realistisch am
   250-Zeilen-Limit; Override rechtzeitig mit dem PO klären statt am Commit-Gate.
7. **Parallel-Sitzungen**: `prod_selftest.py` misst `HEAD~1..HEAD` und ist bei paralleler Arbeit
   blind (bekannt, #1199). Beim Deploy dieser Scheibe Ersatznachweis von Hand einplanen.

## Analysis

### Type

Rework (Feature-Track) — kein Fehlerbericht, sondern ein bewusster Formatwechsel mit einem
mitgenommenen Nebeneffekt (getrennte Zählung statt Sammel-Schlüssel `""`).

### Namenswahl — Empfehlung

**`entity_id` (string) + `entity_type` (string, Werte `trip` | `compare`).**

Begründung: `entity_id` ist im Alarm-Bereich bereits das etablierte Wort — `AlertStateService`
(`alert_state.py:50-100`) und beide Compare-Pfade (`compare_alert.py:10`,
`compare_radar_alert.py:174-182`) benennen ihre Kennung genau so. Ein drittes Vokabular
(`subject_id`, `owner_id`) würde einen vierten Namen für dieselbe Sache einführen. `entity_type`
bleibt ein **freier String**, kein geschlossenes Enum — dieselbe Begründung wie bei
`alert_log.py:33-37`: künftige Typen (z. B. ein Wächter ohne Tour) docken additiv an, ohne
Schema-Migration.

### Altlesbarkeit — Empfehlung: Lese-Regel statt Datei-Migration

Die 222 Bestands-Einträge werden **nicht umgeschrieben**. Beim Lesen gilt: fehlt `entity_id`, wird
`trip_id` als Kennung und `trip` als Typ eingesetzt. Das trägt auch die zwei Neuformat-Einträge
(sie haben `trip_id` gefüllt, `preset_id` leer).

Warum nicht migrieren: Ein Umschreiben der Protokolldateien ist der einzige Weg, bei dem ein
Fehler die Historie **unwiederbringlich** beschädigt — genau das Muster von BUG-DATALOSS-GR221.
Eine Lese-Regel kostet ~8 Zeilen Go und ist rückwirkend folgenlos. Präzedenzfall im Haus:
`ThrottleStore._migrate_flat_file()` (`throttle_store.py:185-201`) migriert ebenfalls beim Lesen.

### Doppelschreiben — Empfehlung: nein

Neue Einträge tragen **nur** `entity_id` + `entity_type`, nicht zusätzlich `trip_id`. Ein
Übergangs-Doppelschreiben würde genau den Zustand verlängern, den diese Scheibe beseitigt, und
S2–S4 erben ihn. Das Deploy-Fenster, in dem neuer Python-Code und alter Go-Code zusammenträfen,
liegt bei Sekunden (`deploy-gregor-prod.sh` startet alle drei Dienste in einem Lauf) und würde
höchstens einen einzelnen Eintrag in der 24-h-Kachel verzögern — kein Datenverlust, da die Datei
selbst vollständig bleibt.

### Zählung im Archiv — Empfehlung

`AlertCountByTrip()` wird zu **`AlertCountByEntity()`**, Schlüssel `"<typ>:<kennung>"`
(z. B. `"trip:5f534011"`, `"compare:abc123"`). Damit ist der heutige Sammel-Schlüssel `""` weg
und Touren und Presets sind unterscheidbar, ohne sich auf die Kollisionsfreiheit zweier
unabhängiger Kennungsräume zu verlassen. `/api/archive/stats` hat **keinen Frontend-Konsumenten**
(gemessen), der Vertrag ist also frei änderbar; `docs/reference/api_contract.md` nennt nur Pfad
und Methode, kein Antwortschema.

Die Briefing-Zählung `BriefingCountByTrip()` bleibt unangetastet — Vergleichs-Briefings
protokollieren dort ohnehin nicht.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/alert_log.py` | MODIFY | `append_entry()`: `trip_id`/`preset_id` → `entity_id`/`entity_type` |
| `src/services/trip_alert.py` | MODIFY | 3 Aufrufstellen (`:277`, `:868`, `:1136`) |
| `src/services/compare_alert.py` | MODIFY | 1 Aufrufstelle (`:145`) |
| `src/services/compare_radar_alert.py` | MODIFY | 1 Aufrufstelle (`:124`) |
| `src/services/compare_official_alert.py` | MODIFY | 1 Aufrufstelle (`:140`) + Kommentar `:138` |
| `internal/store/log.go` | MODIFY | `AlertLogEntry` um `entity_id`/`entity_type`; Lese-Regel für Altformat; `AlertCountByTrip` → `AlertCountByEntity` |
| `internal/handler/archive_stats.go` | MODIFY | Aufruf der umbenannten Funktion |
| `internal/handler/cockpit.go` | MODIFY | keine Logik-Änderung, aber Ausgabe trägt die neuen Felder |
| `frontend/src/lib/types.ts` | MODIFY | `AlertLogEntry`-Typ |
| `frontend/src/routes/+page.svelte` | MODIFY | Filter `:109` prüft zusätzlich den Typ |
| `docs/specs/modules/rework_1467_s1_alarm_kennung.md` | CREATE | Spec dieser Scheibe |
| `docs/specs/modules/feat_1459_alert_protokoll.md` | MODIFY | D2 fortschreiben (vier Altfelder gelten nicht mehr unverändert) |
| Tests Python / Go / Frontend | CREATE/MODIFY | s. u. |

### Scope Assessment

- Dateien: 12 Produktiv + Tests
- Geschätzt: ~100 Zeilen Produktivcode (Python ~35, Go ~55, Frontend ~10), ~260 Testzeilen
- **Summe ~360 Zeilen ⇒ über dem 250er-Budget.** Ein Override auf 500 wird nötig und braucht
  ausdrückliche PO-Zustimmung.
- Risiko: **MITTEL.** Der gefährliche Pfad ist nicht der Schreiber, sondern die Go-Lese-Regel:
  Greift sie nicht, zeigt das Cockpit stumm null Alarme.

### Nachweis-Anforderungen (in die ACs)

1. Eine echte Bestands-Protokolldatei im **Altformat** (vier Felder) fließt über den vollen Weg
   Datei → `LoadAlertLog` → `/api/cockpit/status` → Frontend-Filter und wird der richtigen Tour
   zugeordnet.
2. Ein Vergleichs-Eintrag und ein Tour-Eintrag mit **derselben Kennung** werden getrennt gezählt.
3. Zwei verschiedene Nutzer sehen ausschließlich die eigenen Einträge (Mandantentrennung).
4. Der Bestand bleibt nach einem neuen Eintrag byte-identisch bis auf den Zuwachs.

### Open Questions

- [ ] LoC-Override auf 500 — PO-Zustimmung nötig (wird bei der Spec-Freigabe mitgestellt).

## Angrenzend, aber NICHT in dieser Scheibe

- `BriefingLogEntry` (`log.go:9-14`) trägt ebenfalls `trip_id`. Vergleichs-Briefings schreiben
  aktuell **gar nicht** ins Briefing-Protokoll (`trip_report_scheduler.py:1044` ist der einzige
  Schreiber). Gleiches Muster, eigener Gegenstand — gehört nicht in #1467.
- Die eigentliche Zusammenlegung der Ablaufsteuerungen (S2–S4).
- `_day_window_end()`-Mitternachtsfenster (S4).
