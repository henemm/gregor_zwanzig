# Context: fix-1271-status-zeitformat

## Request Summary
Issue #1271 (Kosmetik-Sammel Prod-Audit) — zwei Bugs beheben: (1) Zeitfelder im Versand-Tab zeigen AM/PM statt deutschem 24h-Format; (2) Trip-Status widerspricht sich zwischen Listen-Ansicht ("Fertig") und Detail-Header ("Geplant") für denselben Trip. Punkt 3 des Issues (Kacheln vs. Tabelle) ist nach Folge-Issue #1274 ausgekoppelt, nicht Teil dieses Workflows.

## Related Files

### Bug 1 — AM/PM-Zeitformat
| File | Relevance |
|------|-----------|
| `frontend/src/app.html:2` | `<html lang="en">` — Root Cause. SvelteKit-Scaffold-Default, nie auf `de` geändert. Steuert die Locale, nach der Browser native `<input type="time">`/`<input type="date">`-Picker rendern (AM/PM vs. 24h, Datumsformat). |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte:86,111` | `<input type="time">` für Morgen-/Abend-Briefing-Uhrzeit (geteilter VersandTab, context="route"\|"vergleich") — betroffener Input im gemeldeten Bug. |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:43-47` (`formatNextSend`) | Bereits korrekt: manuelles 24h-Format (`pad(d.getHours())`), keine `toLocaleTimeString`-Abhängigkeit. Kein Fix nötig, nur zur Abgrenzung geprüft. |

**Weitere Fundstellen mit `type="time"`/`type="date"`**, die vom selben `lang`-Fix mit-repariert werden (kein Einzel-Fix pro Datei nötig):
`TripNewEditor.svelte`, `StageTimeField.svelte`, `StageDateField.svelte`, `EditReportConfigSection.svelte`, `EditRouteSection.svelte`, `AlertQuietHoursCard.svelte`, `VTLaufzeitVergleich.svelte`, `gpx-upload/+page.svelte`.

### Bug 2 — Statuswiderspruch FERTIG/GEPLANT
| File | Relevance |
|------|-----------|
| `frontend/src/lib/utils/tripStatus.ts:12-33` (`deriveTripStatus`) | Liefert `'planned'\|'active'\|'paused'\|'archived'`. **Prüft nicht**, ob alle Etappen in der Vergangenheit liegen — fällt dann fälschlich auf `'planned'` zurück. Spec-Referenz im Code: `docs/specs/modules/epic_135_step2_trip_detail_actions.md` §4. |
| `frontend/src/lib/utils/tripStatus.ts:42-77` (`tripStatus`) | Liefert `'aktiv'\|'geplant'\|'fertig'\|'draft'`. Prüft explizit `letztes Etappen-Datum < heute → 'fertig'`. Spec-Referenz: `docs/specs/modules/screen_home_migration.md`. |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte:69,87,94` | Nutzt `deriveTripStatus` → zeigt im Detail-Header ggf. fälschlich "Geplant". |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte:23,29` | Label-Rendering für `deriveTripStatus`-Ergebnis. |
| `frontend/src/routes/trips/+page.svelte:42,146,154,351-354,389-391,417,450,452` | Trips-Listenansicht — nutzt `tripStatus` → zeigt korrekt "Fertig". |
| `frontend/src/routes/_home/cockpitHelpers.ts:19,251` | Cockpit — nutzt ebenfalls `tripStatus`. |

**Befund:** Zwei parallele, konzeptionell unterschiedliche Ableitungsfunktionen in derselben Datei, entstanden aus zwei getrennten Features (Epic #135 Trip-Detail-Actions vs. Issue #386 Cockpit). `tripStatus()` hat die korrekte "vergangene Etappen → fertig"-Regel, `deriveTripStatus()` fehlt sie.

## Existing Patterns
- Beide Statusfunktionen sind reine Funktionen (`(trip, now) => Status`), gut testbar, keine Seiteneffekte.
- `docs/specs/modules/epic_135_step2_trip_detail_actions.md` §4 dokumentiert die verbindliche Reihenfolge für `deriveTripStatus`: `archived_at → paused_at → aktiv-im-Zeitraum → sonst planned`. Diese Reihenfolge müsste um eine Vergangenheits-Regel ergänzt werden, ohne `archived`/`paused` zu verdrängen.
- `tripStatus()` kennt keine `paused`-Variante — das Cockpit/die Liste zeigen pausierte Trips also anders (oder gar nicht als solche) als der Detail-Header.

## Dependencies
- Upstream: `Trip.archived_at`, `Trip.paused_at`, `Trip.stages[].date` (Datenmodell, unverändert).
- Downstream: Cockpit-Hero-Auswahl (`activeOrNextTrip` in `tripStatus.ts:82+`) nutzt `tripStatus()` — Änderungen an der Vergangenheits-Regel dürfen die Hero-Selektion nicht brechen.

## Existing Specs
- `docs/specs/modules/epic_135_step2_trip_detail_actions.md` — Statuslogik Detail-Header (`deriveTripStatus`)
- `docs/specs/modules/screen_home_migration.md` — Statuslogik Cockpit/Liste (`tripStatus`)
- `docs/specs/modules/versand_tab_route.md` — VTSchedulePlan (AC-3, AC-4, KL-1, KL-2)

## Risks & Considerations
- **`lang="en"→"de"` ist eine globale Änderung** (ganze App, nicht nur Versand-Tab) — betrifft alle 9 Fundstellen mit `type="time"`/`type="date"` gleichzeitig. Erwünscht (Produkt ist rein deutschsprachig), aber Screenreader/Browser-Autofill-Verhalten kann sich ändern — bei manueller Staging-Prüfung alle Editoren mit Datums-/Zeit-Feldern stichprobenartig ansehen, nicht nur Versand-Tab.
- **Status-Vereinheitlichung:** `paused` existiert nur in `deriveTripStatus`, nicht in `tripStatus`. Vor Merge der Logik klären: soll `tripStatus()` künftig auch `paused` kennen, oder bleibt Cockpit/Liste bewusst gröber? Muss in der Spec-Phase (AC) explizit entschieden werden, sonst regressiert die Pausier-Anzeige in Liste/Cockpit.
- Zwei Funktionsnamen (`deriveTripStatus` vs. `tripStatus`) für praktisch denselben Zweck ist der strukturelle Fehler — Fix sollte auf **eine** Quelle konsolidieren (CLAUDE.md: „Code-Duplikate konsolidieren — eine Quelle, Rest Thin-Wrapper"), nicht nur die Vergangenheits-Regel in beide Funktionen duplizieren.
- **`trips/+page.svelte` nutzt bereits BEIDE Funktionen für unterschiedliche Zwecke in derselben Datei** (`statusTone()` via `deriveTripStatus`, `primaryLabel()`/`handlePrimaryAction()` via `tripStatus()`) — zusätzlicher Beleg, dass die Trennung strukturell falsch ist, nicht nur ein Anzeige-Detail.
- `deriveTripStatus()` kennt außerdem kein `draft` (Trip ohne datierte Etappen) — nur `tripStatus()` unterscheidet das. Eine Konsolidierung muss auch diesen Zustand mitnehmen, sonst bricht `primaryLabel()`/`handlePrimaryAction()` in `trips/+page.svelte` (Wizard-Fortsetzen-Aktion für Draft-Trips).
- `TripHeader.svelte:69` (`etappeValue`) prüft `s === 'archived'` für die "X/X abgeschlossen"-Kennzahl — bei einem neuen `finished`-Zustand (vergangen, aber nicht archiviert) muss diese Bedingung mit erweitert werden, sonst zeigt die mobile Kennzahlen-Kachel weiterhin `—/X` statt `X/X`.

## Analysis

### Type
Bug (2 unabhängige Befunde, gebündelt in #1271; Punkt 3 als #1274 ausgekoppelt).

### Affected Files (with changes)

**Bug 1 — AM/PM:**
| File | Change | Description |
|------|--------|-------------|
| `frontend/src/app.html` | MODIFY | `<html lang="en">` → `<html lang="de">` (1 Zeile). Root-Cause-Fix, wirkt auf alle 9 Fundstellen mit `type="time"`/`type="date"` gleichzeitig. |

**Bug 2 — Statuswiderspruch:**
| File | Change | Description |
|------|--------|-------------|
| `frontend/src/lib/utils/tripStatus.ts` | MODIFY | Eine kanonische Funktion (Basis: `deriveTripStatus`) liefert 6 Zustände: `draft \| planned \| active \| paused \| finished \| archived` (NEU: `draft`, `finished`). `tripStatus()` wird Thin-Wrapper (deutsche Kleinschreibungs-Labels für Liste/Cockpit), keine eigene Ableitungslogik mehr. |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | MODIFY | `TONE_MAP`/`LABEL_MAP` um `finished` ("Fertig") und `draft` ergänzen. |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | `etappeValue` (Zeile 69): Bedingung `s === 'archived'` → `s === 'archived' \|\| s === 'finished'`, sonst zeigt die mobile Kennzahlen-Kachel bei vergangenen-aber-nicht-archivierten Trips weiter `—/X`. |
| `frontend/src/routes/trips/+page.svelte` | MODIFY | `statusTone()` auf kanonische Funktion + neue Zustände umstellen; `primaryLabel`/`handlePrimaryAction` auf denselben Aufruf statt zweier Funktionen. |
| `frontend/src/routes/_home/cockpitHelpers.ts` | MODIFY | Auf kanonische Funktion umstellen (`activeOrNextTrip` darf sich nicht ändern — Regressionsgefahr, s. u.). |

### Scope Assessment
- Files: 6 (1 für Bug 1, 5 für Bug 2)
- Estimated LoC: ~+90/-40 (grob; App-weit größter Batzen in `tripStatus.ts` + `trips/+page.svelte`)
- Risk Level: LOW (Bug 1, reiner HTML-Attribut-Fix) / MEDIUM (Bug 2, Konsolidierung mit UI-Sichtbarkeitsänderung: Header zeigt neu "Fertig", Liste/Cockpit neu "Pausiert")

### Technical Approach
**Bug 1:** `lang="en"` → `lang="de"` in `app.html`. Kein Framework-Code betroffen, kein Test-Risiko außer visueller Stichprobe auf Staging (alle Datums-/Zeit-Felder).

**Bug 2:** Single-Source-of-Truth-Konsolidierung, PO-bestätigt (5-States-Modell + `draft`):
1. `deriveTripStatus()` erweitern um `draft` (keine datierten Etappen) und `finished` (letztes Etappen-Datum < heute, `archived_at` nicht gesetzt) — Priorität: `archived` > `paused` > `draft` > `active` > `finished` > `planned`.
2. `tripStatus()` wird Thin-Wrapper: mappt kanonischen Status auf die bisherigen deutschen Kleinbuchstaben-Labels (`archived`→`fertig`, `finished`→`fertig`, `paused`→`pausiert` [NEU], Rest unverändert) — behält die bestehende String-Signatur bei, damit Filter-Vergleiche (`mobileFilter === 'pausiert'` etc.) weiter funktionieren.
3. Konsumenten (`TripStatusBadge`, `TripHeader`, `trips/+page.svelte`, `cockpitHelpers.ts`) auf den neuen kanonischen Zustand abstimmen (s. Affected Files).
4. **Offene Frage für Spec-Phase:** Bekommt "Pausiert" in der Trips-Liste einen eigenen Filter-Tab (UI-Erweiterung) oder bleibt es nur eine korrekte interne Ableitung/Badge-Farbe ohne neuen Tab? Nicht in Analyse vorentschieden, da UI-Scope-Frage — wird als AC in `/30-write-spec` explizit gestellt.

### Dependencies
- `activeOrNextTrip()` (Cockpit-Hero-Auswahl, `tripStatus.ts:82+`) nutzt `tripStatus() === 'aktiv'` — muss nach Umbau exakt gleiches Verhalten behalten (Regressionstest: aktive Trips weiterhin als Hero wählbar).
- Keine Backend-/API-Änderung nötig — reine Frontend-Ableitungslogik.

### Open Questions
- [ ] Eigener "Pausiert"-Filter-Tab in `trips/+page.svelte` (Liste) — ja/nein? → wird als AC in Spec-Phase gestellt.

