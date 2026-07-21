---
entity_id: fix_1271_status_zeitformat
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [frontend, trip-status, i18n, bugfix]
---

<!-- Issue #1271 (Kosmetik-Sammel Prod-Audit) — Punkt 3 (Kacheln vs. Tabelle) ist als Issue #1274 ausgekoppelt, NICHT Teil dieser Spec. -->

# Fix #1271 — AM/PM-Zeitformat & Trip-Status-Widerspruch

## Approval

- [ ] Approved

## Purpose

Zwei unabhängige, in Issue #1271 gebündelte Bugs beheben: (1) native Zeit-/Datumsfelder im Frontend rendern AM/PM statt deutschem 24h-Format, weil die App kein `lang="de"` setzt; (2) derselbe Trip zeigt im Detail-Header ("Geplant") und in der Trips-Liste/Cockpit ("Fertig") widersprüchliche Status, weil zwei parallele Ableitungsfunktionen (`deriveTripStatus`, `tripStatus`) mit unterschiedlicher Logik existieren. Fix konsolidiert beide auf eine kanonische Quelle.

## Source

- **File:** `frontend/src/app.html:2` — `<html lang="en">` → `<html lang="de">`
- **File:** `frontend/src/lib/utils/tripStatus.ts` — `deriveTripStatus()` wird um `draft`/`finished` erweitert und zur kanonischen Quelle; `tripStatus()` wird Thin-Wrapper
- **File:** `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` — `TONE_MAP`/`LABEL_MAP` um `finished`, `draft` ergänzt
- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte:69` — `etappeValue`-Bedingung um `finished` erweitert
- **File:** `frontend/src/routes/trips/+page.svelte` — `statusTone()`, `primaryLabel()`, `handlePrimaryAction()`, mobile Filter-Pills (~Zeile 384-391)
- **File:** `frontend/src/routes/_home/cockpitHelpers.ts` — Konsumenten auf kanonische Funktion umgestellt (Verhalten von `activeOrNextTrip()` bleibt für nicht-pausierte Trips unverändert)

Betrifft **Frontend / User-UI** (SvelteKit, `frontend/src/...`). Kein Go-API-, kein Python-Core-Code betroffen — reine Client-seitige Ableitungslogik und ein HTML-Attribut.

## Estimated Scope

- **LoC:** ~+90/-40
- **Files:** 6
- **Effort:** low (Bug 1, `lang`-Attribut) / medium (Bug 2, Konsolidierung)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Trip.archived_at`, `Trip.paused_at`, `Trip.stages[].date` | Datenmodell (unverändert) | Eingaben der Status-Ableitung |
| `docs/specs/modules/epic_135_step2_trip_detail_actions.md` §4 | Spec | Bisherige `deriveTripStatus`-Reihenfolge, wird um `draft`/`finished` erweitert |
| `docs/specs/modules/screen_home_migration.md` | Spec | Bisherige `tripStatus`-Logik (Cockpit/Liste), wird Thin-Wrapper |
| `docs/specs/modules/versand_tab_route.md` (AC-3, AC-4, KL-1, KL-2) | Spec | `VTSchedulePlan.svelte` Zeitfelder, betroffen vom `lang`-Fix |
| `activeOrNextTrip()` (`tripStatus.ts`) | Intern | Cockpit-Hero-Auswahl — Regressionsschutz siehe Acceptance-Criteria-Abschnitt unten |

## Implementation Details

### Bug 1 — `lang="en"` → `lang="de"`

```html
<!-- frontend/src/app.html:2 -->
<html lang="de">
```

Einzeiliger Root-Cause-Fix. Wirkt global auf alle `<input type="time">`/`<input type="date">`-Vorkommen (u.a. `VTSchedulePlan.svelte:86,111`, `TripNewEditor.svelte`, `StageTimeField.svelte`, `StageDateField.svelte`, `EditReportConfigSection.svelte`, `EditRouteSection.svelte`, `AlertQuietHoursCard.svelte`, `VTLaufzeitVergleich.svelte`, `gpx-upload/+page.svelte`), da keine dieser Komponenten ein eigenes `lang`-Attribut setzt, das den globalen Wert überschreiben würde.

### Bug 2 — Konsolidierung auf eine kanonische Statusfunktion

Kanonischer Status (6 Zustände statt bisher zwei inkonsistenter 4-Zustands-Typen):

```ts
export type TripStatus = 'draft' | 'planned' | 'active' | 'paused' | 'finished' | 'archived';
```

Priorität (verbindliche Reihenfolge, ersetzt die bisherige `deriveTripStatus`-Reihenfolge aus Epic #135 §4):

1. `archived_at` gesetzt → `archived`
2. `paused_at` gesetzt → `paused`
3. keine datierten Etappen → `draft` (NEU — fehlte bisher in `deriveTripStatus`)
4. letztes Etappen-Datum < heute → `finished` (NEU — fehlte bisher in `deriveTripStatus`, war der Kern des gemeldeten Widerspruchs)
5. erstes Etappen-Datum ≤ heute ≤ letztes → `active`
6. sonst (alle Etappen in der Zukunft) → `planned`

`tripStatus()` (Liste/Cockpit, deutsche Kleinbuchstaben-Labels) wird Thin-Wrapper ohne eigene Ableitungslogik, Signatur bleibt erhalten:

```ts
const CANONICAL_TO_HOME: Record<TripStatus, HomeTripStatus> = {
  draft: 'draft',
  planned: 'geplant',
  active: 'aktiv',
  paused: 'pausiert',   // NEU
  finished: 'fertig',
  archived: 'fertig',
};
export type HomeTripStatus = 'aktiv' | 'geplant' | 'fertig' | 'draft' | 'pausiert';
export function tripStatus(trip: Trip, now: Date = new Date()): HomeTripStatus {
  return CANONICAL_TO_HOME[deriveTripStatus(trip, now)];
}
```

`deriveTripStatus()` bleibt die einzige Stelle mit Datums-/Feld-Vergleichslogik; alle Konsumenten (`TripStatusBadge`, `TripHeader.etappeValue`/`startLabel`/`startValue`, `trips/+page.svelte` `statusTone`/`primaryLabel`/`handlePrimaryAction`/Filter-Pills, `cockpitHelpers.ts`) lesen entweder direkt den kanonischen Status oder über den Thin-Wrapper.

`TripHeader.svelte:69` (`etappeValue`): Bedingung `s === 'archived'` → `s === 'archived' || s === 'finished'`.

`trips/+page.svelte` mobile Filter-Pills: fünfter Tab `{ label: 'Pausiert', value: 'pausiert' as const, count: ... }` neben Alle/Aktiv/Geplant/Fertig.

## Expected Behavior

- **Input:** Trip-Objekte mit `archived_at`, `paused_at`, `stages[].date`; Browser-Locale beim Rendern von Zeit-/Datumsfeldern
- **Output:** Konsistentes Status-Label über Detail-Header, Trips-Liste und Cockpit hinweg für denselben Trip; 24h-Zeitformat in allen nativen Zeit-Inputs unabhängig von Browser-/OS-Sprache
- **Side effects:** Trips, die bisher fälschlich als "Geplant" (Header) trotz vergangener Etappen liefen, zeigen neu "Fertig"; Trips, die bisher fälschlich draft-artig als "Geplant" liefen, zeigen "Entwurf"; pausierte Trips zeigen in Liste/Cockpit neu "Pausiert" statt (fälschlich) ihres datumsbasierten Status — s. AC-8/Known Limitations für die Konsequenz auf `activeOrNextTrip()`

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Browser-/OS-Locale Englisch öffnet den Versand-Tab (Trip oder Vergleich, geteilte `VTSchedulePlan.svelte`) / When er das Zeitfeld für Morgen- oder Abend-Briefing anzeigt oder bearbeitet / Then rendert der native Time-Picker im 24-Stunden-Format (z.B. "07:00"), nicht AM/PM, weil `<html lang="de">` die Format-Locale erzwingt statt der Browser-Locale zu folgen
  - Test: Playwright öffnet den Versand-Tab auf Staging, prüft `document.documentElement.lang === 'de'` und liest den sichtbaren/computed Wert des Zeit-Inputs

- **AC-2:** Given die übrigen Formulare mit `<input type="time">`/`<input type="date">` (u.a. `TripNewEditor`, `StageTimeField`, `StageDateField`, `EditReportConfigSection`, `EditRouteSection`, `AlertQuietHoursCard`, `VTLaufzeitVergleich`, `gpx-upload`) / When diese gerendert werden / Then übernehmen sie automatisch dieselbe `lang="de"`-Locale ohne Einzel-Fix pro Komponente
  - Test: Stichprobenartige Sichtprüfung auf Staging (mind. 2 der genannten Formulare, Datums- und Zeitfeld je einmal)

- **AC-3:** Given ein Trip mit `archived_at=null`, `paused_at=null`, letztes Etappen-Datum in der Vergangenheit / When Detail-Header (`TripStatusBadge`) UND Trips-Liste denselben Trip anzeigen / Then zeigen beide "Fertig" — nicht mehr uneinheitlich "Geplant" im Header vs. "Fertig" in der Liste
  - Test: Component-Test rendert `TripHeader`/`TripStatusBadge` und die Listenzeile aus `trips/+page.svelte` mit identischem Trip-Fixture (vergangene Etappen, nicht archiviert), vergleicht beide gerenderten Labels

- **AC-4:** Given ein Trip mit `paused_at` gesetzt und Etappen-Datumsbereich, der den heutigen Tag einschließt / When Detail-Header und Trips-Liste denselben Trip anzeigen / Then zeigen beide "Pausiert" — vorher kannte `tripStatus()` (Liste/Cockpit) keinen pausierten Zustand und zeigte stattdessen fälschlich "Aktiv"
  - Test: Component-Test mit `paused_at`-Fixture prüft Label in Header-Badge und Listenzeile

- **AC-5:** Given ein Trip ohne datierte Etappen (Entwurf) / When Detail-Header (`TripStatusBadge`, mobile Kennzahlen-Kachel) gerendert wird / Then zeigt er den Draft-Zustand statt fälschlich "Geplant" — vorher kannte `deriveTripStatus()` keinen `draft`-Zustand
  - Test: Component-Test mit Trip ohne `stages[].date` prüft Badge-Label und `etappeValue` in `TripHeader`

- **AC-6:** Given ein Trip mit letztem Etappen-Datum in der Vergangenheit und `archived_at=null` / When die mobile Kennzahlen-Kachel "ETAPPE" in `TripHeader.svelte` gerendert wird / Then zeigt sie `X/X` (alle Etappen abgeschlossen) statt `—/X`
  - Test: Component-Test prüft `etappeValue`-Ausgabe für einen `finished`-, nicht-archivierten Trip

- **AC-7:** Given die Trips-Liste (mobile Filter-Pills, ≤899px) / When ein Nutzer die Filter-Leiste ansieht / Then existiert neben Alle/Aktiv/Geplant/Fertig ein fünfter Tab "Pausiert" mit korrekter Trefferzahl; ein Klick darauf filtert `mobileFiltered` auf Trips mit kanonischem Status `paused`
  - Test: Playwright/Component-Test klickt den "Pausiert"-Tab mit gemischten Trip-Fixtures und prüft, dass nur pausierte Trips in der gefilterten Liste erscheinen

- **AC-8 (Regressionsschutz Hero-Auswahl):** Given eine Trip-Liste mit Trips in allen Zuständen (aktiv, geplant, fertig, draft, archiviert) aber OHNE pausierte Trips / When `activeOrNextTrip()` aufgerufen wird / Then liefert sie exakt denselben Trip wie vor der Konsolidierung — unveränderte "heute aktive Tour zuerst, sonst nächste anstehende Tour"-Logik
  - Test: Bestehende Tests für `activeOrNextTrip()`/`tripStatus()` bleiben ohne Anpassung der Erwartungswerte grün für alle nicht-pausierten Fixtures; zusätzlicher Test mit gemischten Fixtures bestätigt unveränderte Auswahl

## Known Limitations

- **Verhaltensänderung bei pausierten, datums-aktiven Trips:** `activeOrNextTrip()` prüft `tripStatus(t, now) === 'aktiv'`. Vor diesem Fix ignorierte `tripStatus()` `paused_at` komplett — ein pausierter Trip mit heute-aktivem Etappen-Datum wurde fälschlich als Hero gewählt. Nach der Konsolidierung liefert `tripStatus()` für solche Trips `'pausiert'`, wodurch sie NICHT mehr als Hero gewählt werden. Das ist eine bewusste Korrektur (pausierte Trips sollen nicht als "aktiv" gelten), aber eine Abweichung vom Vor-Fix-Verhalten für diesen einen Fall — bewusst dokumentiert, nicht Teil des AC-8-Regressionsschutzes, der sich nur auf nicht-pausierte Trips bezieht.
- Der Desktop-Zähler-Balken (Aktiv/Geplant/Abgeschlossen/Drafts) in `trips/+page.svelte` bekommt **keinen** eigenen "Pausiert"-Zähler — nur die mobilen Filter-Pills erhalten den neuen Tab (AC-7). Erweiterung des Desktop-Balkens ist nicht Teil dieser Spec.
- Punkt 3 aus Issue #1271 (Kacheln vs. Tabelle in der Trips-Liste) ist **nicht** Teil dieser Spec — ausgekoppelt nach Issue #1274, wird dort separat spezifiziert.
- `lang="de"` kann Browser-Autofill- oder Screenreader-Verhalten in bisher ungetesteten Randfällen beeinflussen; manuelle Staging-Stichprobe (AC-2) deckt nur die bekannten Formulare ab, keine vollständige Accessibility-Regression.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Konsolidierung zweier bestehender, gleichartiger Pure-Functions auf eine kanonische Quelle plus ein HTML-Attribut-Fix. Kein neues Architekturmuster, keine neue Abhängigkeit, kein Schichtwechsel — bestehendes Pure-Function-Muster (`(trip, now) => Status`) bleibt unverändert.

## Changelog

- 2026-07-16: Initial spec erstellt — Issue #1271
- 2026-07-16: Fakten-Korrektur (kein AC-Inhalt geändert): Dependencies-Tabelle Zeile "activeOrNextTrip()" umformuliert — der Querverweis "AC-8" kollidierte mit dem `edit_gate.py`-Regex `\bAC-\d+[:\s]+(.*)`, der nicht auf die `## Acceptance Criteria`-Sektion begrenzt ist und dadurch beiläufige AC-Nennungen in Prosa fälschlich als zu-kurze AC-Einträge blockierte. Gate-Bug separat gemeldet, nicht in diesem Workflow gefixt.
