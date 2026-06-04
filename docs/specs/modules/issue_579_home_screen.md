# Spec: #579 Home-Screen 1:1 nach JSX

**Issue:** #579  
**Workflow:** issue-579-home-screen  
**Status:** Draft  
**Quelle der Wahrheit:** `claude-code-handoff/current/jsx/screen-home.jsx` + `screen-home-planning.jsx`

---

## Ziel

`frontend/src/routes/+page.svelte` wird 1:1 nach den kanonischen JSX-Quellen reimplementiert. Alle 13 visuellen Pass/Fail-Kriterien (V1–V13) müssen bestehen. Daten-Verdrahtung bleibt stabil.

---

## Scope

| Was | Dateien |
|-----|---------|
| Neuimplementierung Home | `frontend/src/routes/+page.svelte` |
| Daten-Bug Fix | `frontend/src/routes/_home/cockpitHelpers.ts` |
| Daten-Bug Fix | `frontend/src/routes/+page.svelte` (`otherTrips`-Filter) |

---

## Acceptance Criteria

**AC-1:** Given die Home-Seite im Trip-Modus (aktiver liveTrip), When sie bei 1440 px gerendert wird, Then steht die Hero-Karte (`HomeHeroTrip`) links und die Outbox + Alerts rechts — `align-items: start` auf dem Grid, kein Loch unter dem Hero (V1-Pass).

**AC-2:** Given die Hero-Karte im Trip-Modus, When sie gerendert wird, Then ist die Elementreihenfolge: Pills-Zeile → Titel (34 px, fontWeight 600) → Region-Untertitel → Fortschrittsbalken mit Label „Tag x / y" + Datumsrange → Footer-Leiste (card-alt, borderTop) mit Eyebrow „Kanäle" + Dot-Reihe links + „Trip öffnen →" rechts (V2+V3-Pass).

**AC-3:** Given die Schnellaktionen im Trip-Modus, When die linke Hero-Spalte gerendert wird, Then stehen 5 QuickAction-Zeilen (pause/metrics/clock/eye/send) **vertikal gestapelt** direkt unter der Hero-Karte innerhalb der linken Spalte — kein Horizontal-Grid, keine separate volle Breitenzeile (V13-Pass). Letzte Aktion: `glyph="send"`, label „Test-Briefing schicken", sub „→ An deine eigenen Kanäle".

**AC-4:** Given der Compare-Modus (kein liveTrip, aber aktive Vergleiche), When die Schnellaktionen gerendert werden, Then stehen 5 QuickActions vertikal in der linken Spalte: route/metrics/clock/eye/send — letzte: „Test-Vergleich schicken", sub „→ An deine eigenen Kanäle" (V13-Compare-Pass).

**AC-5:** Given aktive Vergleiche neben dem Trip-Hero (alsoWatched.length > 0), When die Seite gerendert wird, Then sind alle CompareStatusRow-Zeilen in einer **einzelnen Card** eingebettet mit Eyebrow „Außerdem beobachtet", Titel „N Orts-Vergleich(e) läuft/laufen nebenher" und Link „Alle Vergleiche →" (V5-Pass).

**AC-6:** Given die Archiv-Sektion (archive.length > 0), When sie gerendert wird, Then gibt es **keinen Card-Wrapper** um die gesamte Sektion — stattdessen `SectionH` (eyebrow „Archiv", title „Frühere Trips", kicker mit Anzahl, right = „Alle anzeigen"-Button) direkt über dem 4-Spalten-Grid (V7-Pass).

**AC-7:** Given der PageHeader, When er gerendert wird, Then hat er **keinen** `sub`-Text, der Titel lautet kompakt (max. 18 px), beide Buttons (Neuer Trip + Neuer Vergleich) haben `variant="ghost"` mit `+`-Icon — kein Primary-Button, kein langer Beschreibungsabsatz (V9+V10-Pass).

**AC-8:** Given `report_config.morning_time` oder `evening_time` mit dem Wert `HH:MM:SS` (DB-Format), When `plannedBriefings()` in `cockpitHelpers.ts` aufgerufen wird, Then wird nur `HH:MM` (erste 5 Zeichen) zurückgegeben — keine Sekunden in der Anzeige.

**AC-9:** Given Trips mit `status === 'fertig'`, When `otherTrips` abgeleitet wird, Then erscheinen abgeschlossene Trips **nicht** in der laufenden Kachel-Liste (kein Doppelauftritt im Archiv-Grid + Kachel-Reihe).

**AC-10:** Given der Planning-Modus (kein liveTrip, keine aktiven Vergleiche), When die Seite gerendert wird, Then enthält sie: ehrlichen Hinweis-Banner (Dot neutral + Text), `SectionH "Weiter einrichten"` mit 2er-Grid aus SetupResumeCards, `SectionH "Schnell anlegen"` mit 3er-Grid aus QuickActions, Sektion „Laufende Orts-Vergleiche" mit CompareTiles (falls vorhanden), Archiv-Sektion — alles entsprechend `screen-home-planning.jsx`.

**AC-11:** Given ein Playwright-Screenshot bei 1440 px für alle drei Modi (trip, compare, planning), When der `fresh-eyes-inspector` Agent ihn gegen die SOLL-PNGs (`D-home-trip.png`, `D-home-compare.png`, `D-home-planning.png`) prüft, Then lautet das Verdict **PASS** für alle drei Modi (kein offener Blocker V1–V13).

---

## Nicht im Scope

- Neue API-Endpunkte oder Backend-Änderungen
- Mobile-Layout-Änderungen (bestehende Media-Queries bleiben)
- Änderungen an Atom/Molecule-Komponenten (außer `cockpitHelpers.ts`)
- `TripKachel.svelte`, `CompareKachel.svelte`, `EmptyKachel.svelte` bleiben unverändert

---

## Hinweise für Implementierung

- LoC-Limit: Override auf 500 vorab setzen (`workflow.py set-field loc_limit_override 500`)
- `cockpitHelpers.ts` Z. 134 + 142: `(rc.morning_time || '07:00').slice(0, 5)`
- `otherTrips`: `trips.filter(t => t.id !== hero?.id && tripStatus(t, now) !== 'fertig')`
- Schnellaktionen-Container: `display:flex, flexDirection:column, gap:10` in linker Spalte
- Hero-Footer: `borderTop: 1px solid var(--g-rule-soft)`, `background: var(--g-card-alt)`, `padding: 14px 26px`, `display:flex, justifyContent:space-between`
- Archiv ohne Card: `SectionH` + `<div class="archive-grid">` direkt (kein `<Card>`)
