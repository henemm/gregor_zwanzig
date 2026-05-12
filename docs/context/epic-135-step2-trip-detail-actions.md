# Context: Issue #153 — Trip-Übersicht: Breadcrumb + Status-Badge + Aktionen

## Request Summary

Zweites Sub-Issue von Epic #135 (Trip-Übersicht). Über der Tab-Navigation (aus Issue #155) soll die Trip-Detail-Seite drei Header-Bausteine bekommen:

1. **Breadcrumb** — `Trips / KHW 403` (Trip-Name + ggf. Shortcode), Link zurück auf `/trips`
2. **Status-Badge** — visualisiert vier Status: `Geplant`, `Aktiv`, `Pausiert`, `Archiviert`
3. **Aktions-Buttons** — `Pausieren` und `Archivieren` (am Trip-Header rechts)

Daraus ergibt sich der echte Knackpunkt: **Das Trip-Modell hat heute keinen `status`-Begriff**. Status muss eingeführt werden — entweder als persistiertes Feld oder als abgeleitete Größe (siehe `Risks & Considerations` §1).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/[id]/+page.svelte` | **EDIT.** Aktuell nur `<h1>{trip.name}</h1>` + `<TripTabs>`. Hier docken Breadcrumb + StatusBadge + Aktionen oberhalb der Tabs an. |
| `frontend/src/routes/trips/[id]/+page.server.ts` | **ggf. EDIT.** Wenn Status aus Backend kommt, muss der Loader das Feld mit ausliefern. Sonst unverändert. |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | **NICHT BERÜHRT** — Tab-Skelett bleibt unverändert. |
| `frontend/src/lib/components/trip-detail/index.ts` | **EDIT.** Barrel-Export ergänzen um neue Komponenten. |
| `frontend/src/lib/components/trip-detail/Breadcrumb.svelte` | **NEU.** Breadcrumb-Komponente (Trips → Trip-Name/Shortcode). |
| `frontend/src/lib/components/trip-detail/StatusBadge.svelte` | **NEU.** Badge mit 4 Status-Varianten (Geplant/Aktiv/Pausiert/Archiviert). |
| `frontend/src/lib/components/trip-detail/TripActions.svelte` | **NEU.** Buttons `Pausieren` + `Archivieren` mit Confirm-Dialog. |
| `frontend/src/lib/components/trip-detail/tripStatus.ts` | **NEU.** Pure-Function `deriveStatus(trip, now)` (Logik einmal an einer Stelle, getestbar ohne DOM). |
| `frontend/src/lib/types.ts` (Z. 41-52) | **EDIT.** `Trip` um `status?`, `archived_at?`, `paused_at?` (oder vergleichbar) erweitern. |
| `internal/model/trip.go` (Z. 20-31) | **ggf. EDIT.** Wenn Status persistiert wird → Felder `Status string`, `ArchivedAt *time.Time`, `PausedAt *time.Time` ergänzen. |
| `internal/handler/trip.go` (Z. 112-196) | **ggf. EDIT.** `tripUpdateRequest` und `UpdateTripHandler` um die neuen Felder erweitern (Merge-Pattern). |
| `frontend/src/lib/components/ui/badge/badge.svelte` | **REFERENZ.** Bestehende Badge-Komponente (Tailwind-Variants). Eigene StatusBadge baut darauf oder kopiert das Pattern. |
| `frontend/src/lib/components/ui/dialog/` | **REFERENZ.** Confirm-Dialog für „Archivieren"-Aktion. Pattern wie in `/routes/trips/+page.svelte` (Delete-Confirm). |
| `frontend/e2e/trip-detail-tabs.spec.ts` | **REFERENZ.** Pattern für Playwright-Test auf `/trips/[id]`-Route. |

## Existing Patterns

- **Server-Loader-Pattern:** `+page.server.ts` lädt Daten via Backend-API mit Session-Cookie, wirft `error(404)` bei Not-Found. Bereits etabliert in `[id]/+page.server.ts`.
- **Komponenten unter `trip-detail/`:** Epic #135 hat das Verzeichnis `frontend/src/lib/components/trip-detail/` etabliert (`TripTabs.svelte`, `index.ts`). Alle neuen Header-Bausteine landen dort.
- **Svelte-5-Runen:** `$props()`, `$state`, `$derived`. Vorbild: `TripTabs.svelte` und `EmailPreviewHeader.svelte`.
- **Tailwind-Variants für Badges:** `frontend/src/lib/components/ui/badge/badge.svelte` nutzt `tailwind-variants` für Varianten (default/secondary/destructive/outline/ghost). Status-Badge ergänzt oder kopiert dieses Pattern.
- **Confirm-Dialog für destruktive Aktionen:** `routes/trips/+page.svelte` (Z. 277-293) zeigt das Pattern für „Löschen"-Bestätigung — analog für „Archivieren".
- **Merge-Pattern beim Trip-Update:** Backend nutzt `tripUpdateRequest` mit Pointer-Feldern (`*string`, `*[]model.Stage`) — siehe `internal/handler/trip.go:112-124` und `bug-99-update-trip-merge.md`. Neue Status-Felder folgen demselben Pointer-Schema.
- **Test-Pattern:** Playwright-E2E gegen Dev-Server `localhost:4173`, Auth via `playwright/.auth/admin.json`. Testdaten-Trip `e2e-cockpit-test` aus `global.setup.ts`.

## Dependencies

- **Upstream:**
  - Backend `/api/trips/{id}` (GET) — liefert Trip-JSON. Wenn Status persistiert wird, muss der Endpoint das Feld zurückliefern.
  - Backend `/api/trips/{id}` (PUT) — bereits vorhanden, Merge-Pattern. Wenn neue Felder hinzukommen, müssen sie in `tripUpdateRequest` ergänzt werden.
  - `Trip`-Type in `frontend/src/lib/types.ts`
  - `--g-accent`-Token + Status-spezifische Farb-Tokens (siehe Risk §3)
  - bits-ui Tabs (bereits in #155 eingeführt)
- **Downstream (was später hier andocken wird):**
  - Sub-Issue #154 (Hero) — wird die Stats-Zeile (Aktive Etappe / Nächstes Briefing / Tage bis Start) unterhalb des Status-Badges rendern. Hero könnte den Status auch beeinflussen (z.B. „Aktive Etappe = Stage X, Tag 2/5").
  - Trip-Wizard `wizardState.svelte.ts` — beim Anlegen eines neuen Trips muss der Status implizit `Geplant` sein (Default oder abgeleitet).
  - Scheduler — pausierte Trips sollen keine Briefings auslösen (separates Issue, **nicht in #153**!).
- **Schema-Rework:** `CLAUDE.md` schreibt vor: Pre-Snapshot via `data_schema_backup.py`-Hook, Migration mit Roundtrip-Test, Post-Verifikation. Status-Felder sind additiv (Default = "Geplant" wenn nicht gesetzt) → Roundtrip ist einfach: alte Trips ohne `status` werden automatisch als „Geplant"/„Aktiv" (je nach Datum) angezeigt.

## Existing Specs

- `docs/specs/modules/epic_135_step1_tab_navigation.md` — direkt vorausgehende Sub-Spec; Verzeichnisstruktur + bits-ui-Pattern wiederverwenden.
- `docs/specs/bugfix/bug-99-update-trip-merge.md` — beschreibt das Pointer-Merge-Pattern im UpdateTripHandler (Schema-Rework-Falle vermeiden).
- **Master-Spec für Epic #135 existiert NICHT** (analog zu #155). Sub-Spec für #153 reicht — Konsistenz mit #155.
- **Status-Begriff existiert NICHT in den Specs** — er wird mit dieser Spec frisch eingeführt.

## Risks & Considerations

### 1. Status-Modell: Persistiert vs. abgeleitet — Tech-Lead-Empfehlung

Zwei Wege:

- **A) Vollständig abgeleitet aus Datum:** Status = pure Funktion `(trip.stages, now)` →
  - Heute < frühestes Stage-Datum → `Geplant`
  - Heute zwischen erstem und letztem Stage → `Aktiv`
  - Heute > letztes Stage-Datum → `Archiviert`
  - „Pausiert" → **nicht möglich** ohne Persistenz (keine Datumslogik dafür)
  
- **B) Persistierte Flags + Datumsableitung:** zwei explizite Flags `paused_at`, `archived_at` + Datumsableitung für Geplant/Aktiv.
  - Status =
    - `paused_at` gesetzt → `Pausiert`
    - `archived_at` gesetzt → `Archiviert`
    - sonst: abgeleitet wie A (Geplant/Aktiv)

**Tech-Lead-Empfehlung: B.** Begründung: Issue #153 fordert explizit Buttons „Pausieren" und „Archivieren" — diese Aktionen ergeben nur Sinn, wenn der Status persistiert wird. Vollständig abgeleitete Status würden den Knopf zur Geste ohne Wirkung machen. Migration ist trivial: alte Trips haben kein `paused_at`/`archived_at` → laufen weiter unter „Geplant"/„Aktiv" wie bisher. Status selbst wird **nicht persistiert**, sondern in einer Pure-Function `deriveStatus(trip, now)` aus den Flags + Datumsbereich berechnet. Damit gibt es nur **eine** Source of Truth (die Flags), keine Inkonsistenz zwischen Status-String und Flags.

### 2. Soll der Status im Backend persistiert werden, oder nur im Frontend ableitet?

Folgekonsequenz aus #1: Wenn „Pausieren"/„Archivieren" persistent sein soll (sonst nutzlos), **muss** das Backend die Flags speichern. Reine Frontend-Persistenz (z.B. localStorage) wäre user-gebunden, ginge bei Tab-Wechsel verloren — Anti-Pattern. → **Backend-Felder `paused_at`, `archived_at` als `*time.Time`** in `model.Trip`, dazu Endpoint-Erweiterung im `tripUpdateRequest`. Daten-Schema-Rework: trivial additiv (keine Migration alter Daten nötig — `nil` ist Default).

### 3. Farben für Status-Varianten — Design-Token-Disziplin

Status-Badges brauchen verschiedene Farben. Vier semantische Klassen:
- `Geplant` — neutral/grau (kommt noch)
- `Aktiv` — Akzent (`var(--g-accent)`, läuft jetzt)
- `Pausiert` — warnend (gelb/amber)
- `Archiviert` — gedämpft (mid-gray, abgeschlossen)

Aktuell existieren `--g-accent`, `--g-ink`, `--g-ink-faint`, `--g-border`. Es gibt **keine** semantischen Status-Tokens. Empfehlung: in `app.css` vier neue Tokens ergänzen (`--g-status-planned`, `--g-status-active`, `--g-status-paused`, `--g-status-archived`), nicht inline Hex-Werte.

### 4. „Archivieren" — destruktiv oder reversibel?

Issue-Body unklar. Pragmatisch: **reversibel**. Archivierte Trips bleiben in der Datenbank, werden in der Trip-Liste aber ggf. ausgeblendet (separates Issue!). Wiederherstellung später möglich. → Confirm-Dialog mit Hinweis „Trip wird ins Archiv verschoben — kann später reaktiviert werden." statt „Wirklich löschen?". „Löschen" bleibt eine getrennte Aktion (existiert bereits in der Trip-Liste).

### 5. „Pausieren" — wirkt sofort?

Konsequenz von Pausieren: Briefings sollen nicht mehr versendet werden. **Aber:** Der Scheduler ist in #153 nicht in Scope. Pragmatisch:
- In #153 nur den Flag setzen + UI anzeigen.
- Scheduler-Integration (paused Trips überspringen) → **eigenes Folge-Issue** anlegen (Hinweis in Known Limitations).

### 6. Breadcrumb-Inhalt: Name oder Shortcode?

Issue sagt „`Trips / KHW 403`". Im Beispiel ist `KHW 403` ein Shortcode. Aber nicht alle Trips haben einen Shortcode (Feld ist optional, `shortcode?: string`). Pragmatisch: Breadcrumb zeigt `Trips / <shortcode>` wenn vorhanden, sonst `Trips / <name>`. Konsistenz mit `EmailPreviewHeader.svelte:20`: `trip.shortcode ? \`${trip.name} · ${trip.shortcode}\` : trip.name`.

### 7. Action-Buttons: Wann disabled?

- `Archivieren` bei bereits archivierten Trips → disabled oder Label-Wechsel auf „Wiederherstellen"? Empfehlung: Label-Wechsel (`Reaktivieren` bzw. analog `Fortsetzen` für Pausiert), kein disabled. Klarer User-Mental-Model: Button toggelt den Status.
- `Pausieren` bei archiviertem Trip → nicht sinnvoll → ausblenden (nicht disabled, sonst wird's unübersichtlich).

### 8. Trip-Detail vs. Trip-Liste — Status-Sichtbarkeit

Aktuell zeigt die Trip-Liste (`routes/trips/+page.svelte`) den Status **nicht**. Sub-Issue #153 fügt den Status nur in der Detail-Seite hinzu. In der Liste später nachziehen (Konsistenz) → **explicit out of scope** für #153, in „Known Limitations" notieren.

### 9. LoC-Budget

Workflow-Tools v3 enforced 250 LoC pro Workflow (mit Override-Möglichkeit). Geschätzt:
- Backend Schema-Erweiterung: ~10 LoC (`trip.go`) + ~15 LoC (`handler/trip.go` Merge-Logik)
- `tripStatus.ts` Pure-Function: ~25 LoC
- `Breadcrumb.svelte`: ~25 LoC
- `StatusBadge.svelte`: ~35 LoC
- `TripActions.svelte`: ~80 LoC (Buttons + Confirm-Dialog + API-Calls)
- `index.ts` Barrel-Update: ~3 LoC
- `+page.svelte` Edit: +20 LoC
- `types.ts` Edit: +5 LoC
- E2E-Tests: ~70 LoC
- Status-Token in `app.css`: ~4 LoC
- **Total: ~290 LoC** → wahrscheinlich knappes Override nötig (350?). Phase 3 verfeinert die Schätzung.

### 10. Backend-Tests bei Schema-Erweiterung

CLAUDE.md verlangt Roundtrip-Test bei Schema-Reworks. Für additive Felder: `internal/handler/trip_test.go` ergänzen um „Trip ohne `paused_at` → unverändert nach PUT" und „Trip mit `paused_at` → bleibt erhalten".

---

## Phase 2 — Analyse-Ergebnisse (2026-05-12)

### Finale Architektur-Entscheidungen

| Bereich | Entscheidung | Begründung |
|---------|-------------|------------|
| **Backend-Schema** | `paused_at *time.Time` + `archived_at *time.Time` (Timestamps statt Booleans), `omitempty` | Audit-Trail (wann pausiert?) + saubere additive Erweiterung. Python-Loader robust gegen unbekannte Felder. |
| **API-Endpoint** | NEU: `PATCH /api/trips/{id}/state` mit Body `{paused?: bool, archived?: bool}` | Boolean-Aktion (Frontend-Mental-Model) → Backend mappt zu Timestamp set/clear. Vermeidet Go-Tristate-Problem (absent vs. explicit null). Bestehender `PUT /api/trips/{id}` bleibt unverändert. |
| **Reversibilität** | Beide Aktionen sind reversibel (Toggle-Verhalten) | User-Entscheidung 2026-05-12. Buttons wechseln Label je nach Status. |
| **Frontend-Status-Funktion** | Neu: `deriveTripStatus(trip, now)` in `lib/utils/tripStatus.ts` mit 4 Werten (`planned/active/paused/archived`) | Zentraler Util, getestbar ohne DOM. |
| **Cockpit-Konsolidierung** | Cockpit-Funktion (`routes/+page.svelte:17-23`) bleibt vorerst stehen, eigenes Tech-Debt-Ticket | Scope-Schutz; Memory-Regel „Duplikate konsolidieren" wird durch separates Issue erfüllt. |
| **Confirm-Dialog** | Nur für „Archivieren". Pausieren/Fortsetzen/Reaktivieren ohne Confirm. | Archivieren fühlt sich „großer" an. Pause ist alltäglich. |
| **Status-Badge-Styling** | Bestehende `Pill`-Komponente wiederverwenden (`tone: success/warning/default/info`) | Keine neuen CSS-Tokens nötig. |
| **Wizard-Save-Schutz** | `toTripPayload()` schickt `paused_at`/`archived_at` nicht mit → Pointer-Pattern lässt sie unverändert. Bei `TripEditView.svelte` Spread wird das Feld 1:1 durchgereicht (vom GET). | Verifiziert (kein zusätzlicher Code nötig). |
| **Scheduler-Pause** | OUT OF SCOPE für #153, separates Folge-Issue. In Known Limitations notieren. | Bewusste Scope-Begrenzung. |
| **Status-Mapping** | `archived_at != nil` → `archived` (Vorrang). Sonst `paused_at != nil` → `paused`. Sonst Datums-Ableitung: heute innerhalb Stage-Bereich → `active`, sonst `planned`. | Vier-Status-Hierarchie ohne Inkonsistenz. |

### Datei-Inventar (8 Dateien, ~220 LoC)

| Datei | Art | LoC |
|-------|-----|-----|
| `internal/model/trip.go` | EDIT | +2 |
| `internal/handler/trip.go` | EDIT (UpdateTripHandler bleibt; **neuer Handler `UpdateTripStateHandler`**) | +50 |
| `cmd/server/main.go` | EDIT (1 neue Route) | +1 |
| `internal/handler/trip_state_test.go` | NEU (Toggle-Tests) | +60 |
| `frontend/src/lib/types.ts` | EDIT (Trip-Interface +2 Felder) | +2 |
| `frontend/src/lib/utils/tripStatus.ts` | NEU (Pure-Function) | +25 |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | NEU (Pill-Wrapper) | +30 |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | NEU (Breadcrumb + Badge + Actions + Confirm-Dialog) | +90 |
| `frontend/src/lib/components/trip-detail/index.ts` | EDIT (Barrel) | +2 |
| `frontend/src/routes/trips/[id]/+page.svelte` | EDIT (TripHeader einbinden, `<h1>` ersetzen) | +5 / -1 |
| `frontend/e2e/trip-detail-actions.spec.ts` | NEU (E2E AC-Tests) | +80 |
| **Summe** | | **~350 LoC** |

Schätzung 350 LoC → **Override notwendig**: `workflow.py set-field loc_limit_override 400` mit Begründung „Backend-Endpoint NEU + 2 neue Frontend-Komponenten + E2E-Test-Suite". E2E-Tests + 1 zusätzlicher Backend-Handler treiben die Zahl.

### Open Items für Spec-Phase

- Genaue AC-N-Formulierung (mindestens 8 Kriterien: Breadcrumb-Rendering, Status-Berechnung × 4 Stati, Pause-Toggle, Archive-Toggle mit Confirm, Reversibilität, Persistenz nach Reload).
- TestID-Inventar für Playwright-Selektoren.
- Pseudo-Code für `deriveTripStatus`.
- Sicherstellen, dass die alte Cockpit-Status-Funktion **nicht** beeinflusst wird (kein Import-Konflikt).
