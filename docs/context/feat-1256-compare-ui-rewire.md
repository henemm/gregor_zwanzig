# Context: feat-1256-compare-ui-rewire

Issue #1256 (PO-Auftrag 2026-07-13) — Orts-Vergleich-UI 1:1 auf Design-Handoff-4
bringen. Kanonische Quelle: JSX in Handoff-4-Zip (`claude-code-handoff/current/jsx/`
+ `gregor-zwanzig-mobile/project/`); alte Soll-PNGs (Ranking/Signal) ÜBERHOLT.
Entpackter Arbeitsstand: Session-Scratchpad `handoff4/` (bei Bedarf neu entpacken
aus `/home/hem/gregor_zwanzig/claude-code-handoff/Gregor-Zwanzig-handoff-4.zip`).

## Request Summary

Drei Design-Screens (Liste `ScreenCompareList`, Hub `ScreenCompareDetail` mit 6
Tabs, Editor `ScreenCompareEditor` create/edit) + Mobile-Varianten 1:1 in die
App bringen und verdrahten. Kernbefund der Context-Phase: **Die Struktur
existiert bereits weitgehend** (Routen, 6 Tabs, Progressive-Editor, klickbare
Kacheln) — die Arbeit ist ein präziser 1:1-Angleich je Screen plus das Schließen
konkreter Struktur-Lücken, KEIN Neubau.

## Soll (JSX, kondensiert)

- **Liste:** CompareTile (Status-Dot, Name, Status+Region, `N Orte · Profil`,
  Kanal-Pills, Fuß `schedule + zuletzt`), Kebab per Status (draft→[Setup
  fortsetzen, Löschen]; sonst [Pausieren/Aktivieren, Briefing jetzt senden,
  Vorschau, Bearbeiten, Löschen]), Intro-Copy „ohne Ranking", 3 Stats, Suche,
  Leerzustand, Fußzähler.
- **Hub (6 Tabs):** Header-Kebab NUR Lifecycle; Übersicht = Monitoring-Streifen
  (5 Stats: Status/Nächster Versand/Briefings/Zuletzt raus/Kanäle) + 4
  SummaryCards mit „Bearbeiten →"-Tab-Sprung + Verifikations-Hinweis; Orte-Tab
  mit Drag (Reihenfolge=Spalten); Idealwerte (CompareIdealRow, „kein Score");
  Layout (Limit-Pills Email·alle/Telegram·max 8/SMS·flach + CompareLayoutRow je
  Kanal); Versand (Briefing-Zeiten, Kanal-Toggles mit verifiziert-Status,
  Aktivierungs-Karte, „kein Enddatum"-Copy); Vorschau (CompareChannelSwitch,
  Email: Desktop-Inbox/iPhone-Umschalter, CompareBriefingPreview).
- **Editor (5 Abschnitte):** vergleich→orte→idealwerte→layout→versand;
  Freischalt-Kette name→≥2 Orte→Vis-Flags; Fortschritt „N/5"; Tab3 =
  `CorridorEditor context="vergleich"`; **Tab4 = geteilter `LayoutTab` mit
  `LT_ComparePreview`** (Orte=Spalten-Live-Vorschau, grün=Idealbereich, „Kein
  Ranking", Telegram-Rechnung `Label + N Orte = X Spalten (max 8)`, SMS ≤140);
  Tab5 = `VersandTab context="vergleich"` mit Aktivierungs-Banner; create:
  „Briefing aktivieren" erst bei isReady; edit: alle frei, dirty-Pill.
- **Mobile:** Editor CEM_ (TabBar scrollbar, Lock-Toast, floating CTA, Sheet-
  Bibliothek); Liste dense+Chevron ohne Kebab; Detail 2×2-Monitoring (4 Stats),
  SummaryRows, Lifecycle-Bottom-Sheet, Vorschau fest mobile.
- **WIDERSPRUCHS-WARNUNG:** `screen-compare-email.jsx` (mobile-Projekt) trägt
  Score/Rang/Empfehlung — im Header selbst als `⚠ DEPRECATED (PO 2026-07-11)`
  markiert, wird von den Auftrags-Screens nicht importiert. NICHT übernehmen.

## Ist (Frontend, kondensiert)

- Routen: `/compare` (CompareGrid/CompareTile, Suche, 3 Stats, Fußzähler,
  Kachel→`/compare/{id}`, CTA→`/compare/new`), `/compare/[id]` (Header mit
  StatusPill/Primäraktion/CompareKebab; CompareTabs mit EXAKT den 6 Tabs,
  „Wertebereiche"-Label, URL-Sync `?tab=`), `/compare/new` (CompareEditor
  mode=create mit Lock-Engine; Edit-Route mit Deep-Link).
- Wiederverwendbar (live): `shared/corridor-editor/*` (#1231),
  `shared/VersandTab.svelte` + `versand-tab/*` mit `context="vergleich"`
  (#1232), CompareTile (#582 „1:1 nach JSX" — gegen ALTEN JSX-Stand).
- **Struktur-Lücken:** Editor-Tab4 nutzt noch `steps/Step4Layout` (#442, alt)
  statt geteiltem LayoutTab+LT_ComparePreview; Editor hat 6. Tab „Alarme" im
  Edit-Modus (#1170) — Soll-Editor kennt nur 5 (PO-Memory: Alerts eigene
  Config-Seite → Klärung, ob Alarme-Tab bleibt); `steps/Step3Idealwerte` toter
  Code; `steps/Step2Orte` alt vs. Soll-Smart-Import.
- **Neutralitäts-Grauzonen:** `CompareMatrix` mit `compare-matrix-best`
  (Best-Value-Hervorhebung #251), `HourlyMatrix` „Top-3 Locations" — Soll-
  Vorschau nutzt neutrale CompareBriefingPreview. Prüfen, wo Matrix/Hourly
  gerendert werden (Vorschau-Tab?) und ob „best" gegen Neutralität verstößt.
- Playwright: 17 Compare-Specs + 20 Unit-Suiten; testid-Verträge (C6) siehe
  Ist-Bericht — `compare-detail-tab-*`, `compare-editor-*`, `cm-mobile-*`,
  `corridor-*`, `versand-tab` u.v.m. MÜSSEN stabil bleiben.
- Unklar (in Analyse klären): ob LocationsRail/AutoReports*-Komponenten noch
  auf `/compare` gerendert werden (Spec issue-287 klickt `compare-rail`) oder
  Alt-Reste sind; Kebab-Aktionsumfang Liste vs. Soll.

## Datenlage (Backend, kondensiert)

- CRUD komplett: GET/POST/PUT/DELETE `/api/compare/presets*`, PATCH
  `.../state` (nur archived), POST `.../send` (Proxy→Python Einzelversand).
- Live-Daten: GET `/api/compare?location_ids=…` (Tabellen-Rows); Mail-Preview
  `POST /api/_validator/compare-email-preview` (Body-Parameter, nicht
  preset_id).
- Status: KEIN persistenter draft/paused — `deriveStatusFromPreset`
  (name/location_ids→draft; `schedule=="manual"`→paused). Chassis-Scheibe 2
  (#1250) bringt `paused_at`.
- Locations: CRUD + `POST /api/locations/resolve` (URL/Koordinaten — deckt
  Soll-Smart-Import; Freitext-Geocoding ist im Soll NICHT gefordert).
- Ohne Backend-Gegenstück: `region` nur untypisiert in DisplayConfig;
  Profil nur 4er-Enum-String (reicht für Soll-Labels); kein numerisches
  weight an Idealwerten (Soll braucht keins — nur Prio-Reihenfolge).

## Risks & Considerations

1. **Regression-Historie:** #438/#485 bauten gegen alten Design-Stand — darum
   Drift. Fidelity-Gate je Scheibe: Playwright-Screenshot + fresh-eyes gegen
   JSX-Struktur (echte Zeilennummern, kein Prosa-Abgleich).
2. **testid-Stabilität (C6)** über alle Scheiben — 17 Specs dürfen nicht brechen.
3. **Alarme-Tab im Editor** widerspricht formal dem 5er-Soll → PO-Klärung in
   der Spec (Empfehlung: bleibt, da PO-bestätigtes Muster „Alerts eigener Tab").
4. **Layout-Tab-Ersatz** (Step4Layout → geteilter LayoutTab) ist die größte
   Einzellücke und berührt Editor UND Hub-Layout-Tab.
5. Abhängigkeit Chassis: Pause-Toggle heute über schedule-Mechanik — UI-Arbeit
   nutzt die bestehende computePauseToggle-Logik, wechselt in S2 (#1250) auf
   `paused_at` (kein Blocker, aber Doppel-Touch vermeiden → Reihenfolge klären).
6. Ist-Soll-Abgleich als PO-lesbarer Kommentar in #1256 (PO-Wunsch 2026-07-13)
   — Spec-Scheiben müssen auf diesen Abgleich referenzieren.
