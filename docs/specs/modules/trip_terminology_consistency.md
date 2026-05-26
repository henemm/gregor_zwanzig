# Spec: Trip-Terminologie-Konsistenz (Issue #394)

**Status:** Draft — wartet auf PO-Approval
**Created:** 2026-05-26
**Issue:** #394
**PO-Direktive:** „Verwende immer den Begriff **Trip**" — „Tour/Touren" als Synonym für Trip ist verboten.

## Zweck

Alle **user-sichtbaren** UI-Texte im Frontend verwenden durchgängig „Trip"/„Trips". Das uneinheitliche „Tour"/„Touren" (aus Claude-Design-Vorlagen + Bestand) wird entfernt. Ein Source-Inspection-Guard-Test (analog `contrast-audit.test.ts`, läuft über `node --test`) verhindert Rückfall.

## Scope

**Betroffen (user-sichtbare Strings in `.svelte`, ~35 Vorkommen / ~11 Dateien):**
`routes/+page.svelte` (Home-Cockpit, inkl. der in #386 eingeführten „Weitere Touren"/„Nächste Tour"/„Neue Tour"), `routes/trips/+page.svelte`, `routes/archiv/+page.svelte`, `routes/_design-system/+page.svelte`, `lib/components/trip-wizard/steps/Step3Weather.svelte`, `lib/components/edit/WeatherSummaryCard.svelte`, `lib/components/trip-detail/SavePresetDialog.svelte`, `lib/components/ui/sidebar/Sidebar.svelte`, `lib/components/ui/sidebar/BottomNav.svelte`, `lib/brand/BrandSidebar.svelte`, `routes/_home/EmptyKachel.svelte`.

**Ersetzungsregeln (mit Grammatik):**
- „Tour" → „Trip", „Touren" → „Trips".
- Artikel/Adjektiv: *die* Tour → *der* Trip. Konkret: „Neue Tour" → „Neuer Trip"; „Meine Touren" → „Meine Trips"; „Weitere Touren" → „Weitere Trips"; „Nächste Tour" → „Nächster Trip"; „Frühere Trips" bleibt.
- Komposita: „Mehrtagestour(en)" → „Mehrtages-Trip(s)"; „Touren-…" → „Trip-…".

**NICHT anfassen:**
- `Etappe`/`Wegpunkt` (bleiben deutsch).
- `Vergleich`/`Orts-Vergleich` (= Subscription, KEIN Trip).
- Code-Identifier, Pfade, `data-testid`, Imports, Kommentare (`TripKachel`, `/trips`, `tripStatus` etc.).
- Backend/Go, E-Mail-Templates (separat, falls dort „Tour" — diese Spec ist Frontend-UI).

## Acceptance Criteria

**AC-1:** Given das Frontend, When man die user-sichtbaren Texte aller `.svelte`-Dateien prüft, Then enthält **kein** sichtbarer String „Tour" oder „Touren" als Synonym für Trip — überall steht „Trip"/„Trips".

**AC-2:** Given die grammatische Ersetzung, When „Neue Tour"/„Meine Touren"/„Weitere Touren"/„Nächste Tour" ersetzt werden, Then sind Artikel/Adjektiv korrekt angepasst („Neuer Trip", „Meine Trips", „Weitere Trips", „Nächster Trip") — keine falschen Genus-Formen.

**AC-3 (Abgrenzung):** Given `Etappe`, `Wegpunkt`, `Vergleich`/`Orts-Vergleich`, When der Sweep läuft, Then bleiben diese unverändert (kein „Trip" wo Subscription/Stage gemeint ist).

**AC-4 (Guard-Test):** Given ein neuer Test `src/lib/trip-terminology.test.ts` (Source-Inspection, `node --test`), When er über alle `.svelte`-Dateien scannt, Then schlägt er fehl, sobald ein user-sichtbarer „Tour/Touren"-String existiert (Code-Identifier/Pfade/`data-testid`/Kommentare ausgenommen), und ist nach dem Sweep grün. Vor dem Sweep ist er rot (RED-Beweis).

**AC-5 (keine Regression):** Given die geänderten Seiten, When `svelte-check` + `contrast-audit.test.ts` laufen, Then bleiben sie grün; keine funktionale/visuelle Änderung außer dem Wort-Tausch. Routen laden weiterhin (200/302).

## Tests (mock-frei)

- `trip-terminology.test.ts` (Guard, Source-Inspection) — RED vor Sweep, GREEN danach.
- Stichprobe Staging (Post-Push): `/`, `/trips`, `/archiv` authentifiziert laden → „Trip(s)" sichtbar, kein „Tour".

## Risiken

- Falsch-Positiv im Guard (z.B. „Tour" in einem Nicht-Trip-Wort) → Guard auf Wortgrenzen + user-sichtbare Kontexte beschränken; ggf. `audit:exempt`-Konvention für Einzelfälle.
- Genus-Fehler bei mechanischem Replace → bewusst grammatisch ersetzen, nicht blind `sed`.
- LoC: reiner Text-Tausch + 1 Testdatei, klar unter 250.
