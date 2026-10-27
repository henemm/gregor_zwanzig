# Altbestand-Messung — feat-2347-s2-s4-paritaets-e2e (Testplan Schritt 1)

Gemessen am 2026-10-26 im Worktree `2346-s2` (HEAD 801df2412), reine Messung, kein Code geändert.
Rohausgabe: `docs/artifacts/feat-2347-s2-s4-paritaets-e2e/altbestand-playwright-output.txt`.

## Stack-Parameter (CI-Nachbau nach `frontend/e2e/ci-stack.sh` + `ci.yml` Job `e2e`)

| Punkt | Wert |
|---|---|
| Go-Binary | `go build ./cmd/server` → Scratchpad `.../scratchpad/stack/gregor-server` (`GREGOR_SERVER_BIN`) |
| State-/Datenwurzel | `GZ_CI_STACK_STATE_DIR=.../scratchpad/stack/state` (leere Datenwurzel, frisch) |
| Ports | Go `8197` (`GZ_CI_STACK_GO_PORT`), Python-Core `8107` (`GZ_CI_STACK_PY_PORT`), Preview `4173` — vorher per `ss -ltn` frei |
| Handgriff 1 Proxy | `GZ_E2E_API_PROXY_TARGET=http://127.0.0.1:8197`, zusätzlich `GZ_API_BASE=http://localhost:8197` (SvelteKit-Server-Routen, `start-preview.sh`) |
| Handgriff 2 .env | `GZ_REPO_ENV_FILE=<leere Datei im Scratchpad>` |
| Handgriff 3 Ports | weder 8090/8000 noch 8091/8001 |
| Handgriff 4 Auth | `rm -f frontend/playwright/.auth/admin.json` vor dem Lauf |
| Handgriff 5 Fixture | `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo` (zusätzlich aus `.env.e2e`) |
| Aufruf | `CI=1 npx playwright test --workers=1 --reporter=list <12 Dateien>` aus `frontend/` |
| Stack-Ende | `ci-stack.sh stop` mit denselben Variablen; Ports 8197/8107/4173 danach frei, keine Restprozesse; die vom Lauf erzeugte `frontend/playwright/.auth/admin.json` (zeigte auf den gestoppten Stack) wieder entfernt |

**Kontrollmessung:** `e2e/hub-versand-autosave-chip.spec.ts` (Positivliste) **2/2 passed**, `global.setup` passed, keine 401 — Stack korrekt aufgesetzt.

`compare-send-dialog-target.staging.spec.ts`: **nicht gemessen** (Staging-Spec, nicht gegen den Stack gefahren).

Gesamt: 71 Fälle (inkl. setup + Kontrolle) — **58 passed, 13 failed, 0 skipped**.

## Ergebnis je Datei

| Datei | passed | failed | skipped |
|---|---|---|---|
| compare-tab-bar.spec.ts | 5 | 0 | 0 |
| compare-hub-name-region-profil.spec.ts | 7 | 0 | 0 |
| compare-hub-kopf-einmal.spec.ts | 11 | 1 | 0 |
| bug-626-compare-menu-actions.spec.ts | 3 | 4 | 0 |
| compare-hub-save-chip.spec.ts | 3 | 1 | 0 |
| compare-mobile-vervollstaendigung.spec.ts | 6 | 1 | 0 |
| mobile-tab-bar.spec.ts | 3 | 3 | 0 |
| trips-list-aktionen.spec.ts | 3 | 0 | 0 |
| issue-724-trip-name-save-error.spec.ts | 3 | 0 | 0 |
| issue-758-save-indicator.spec.ts | 5 | 2 | 0 |
| feat-880-autosave-overlay.spec.ts | 6 | 1 | 0 |

## Ergebnis je Fall

| Datei | Fall | Ergebnis | Fehlerursache |
|---|---|---|---|
| compare-tab-bar | :82 Mobile Deep-Link ?tab=alarme | passed | |
| compare-tab-bar | :89 Mobile Alt-Link ?tab=versand → Wetter-Metriken | passed | |
| compare-tab-bar | :96 Mobile A11y tablist/roving tabindex | passed | |
| compare-tab-bar | :114 Mobile Trigger ≥44px, Orte-Badge | passed | |
| compare-tab-bar | :134 Desktop Leiste ohne Band-Scroll | passed | |
| compare-hub-name-region-profil | :88 AC-1 Name ändern | passed | |
| compare-hub-name-region-profil | :118 AC-2 Region ändern | passed | |
| compare-hub-name-region-profil | :150 AC-3 Aktivitätsprofil | passed | |
| compare-hub-name-region-profil | :174 AC-4 nur Name → Rest unberührt | passed | |
| compare-hub-name-region-profil | :206 AC-5 Name dann Wertebereiche-Commit | passed | |
| compare-hub-name-region-profil | :250 AC-6 Mobile Name inline | passed | |
| compare-hub-name-region-profil | :284 AC-7 PUT 500 → Fehlermeldung | passed | |
| compare-hub-kopf-einmal | :116 AC-8 Desktop testid genau einmal | passed | |
| compare-hub-kopf-einmal | :160 AC-8 Mobil testid genau einmal | passed | |
| compare-hub-kopf-einmal | :205 AC-2 Mobil Name/Region/Profil | passed | |
| compare-hub-kopf-einmal | :252 AC-3 Kopf-PUT nur geändertes Feld | passed | |
| compare-hub-kopf-einmal | :304 AC-5 Profil-PUT scheitert | passed | |
| compare-hub-kopf-einmal | :336 AC-9 Mobil Eyebrow | passed | |
| compare-hub-kopf-einmal | :349 AC-9 Desktop Breadcrumb | passed | |
| compare-hub-kopf-einmal | :369 AC-10 Desktop Region ≤60 | passed | |
| compare-hub-kopf-einmal | :369 AC-10 Mobil Region ≤60 | passed | |
| compare-hub-kopf-einmal | :397 Bedienung Desktop | passed | |
| compare-hub-kopf-einmal | :466 F007 Orte-Anzahl Desktop vs. Mobil | **failed** | Messaufbau `DELETE /api/locations/{id}` → 409 `location_in_use` (Löschsperre für von Vergleichen referenzierte Orte, `internal/handler/location.go:294-305`); Test-Vorbedingung veraltet |
| compare-hub-kopf-einmal | :492 F007 Desktop-Singular | passed | |
| bug-626 | :131 AC-1 Bearbeiten → /compare/{id}/edit | **failed** | `compare-tile-*` nicht gefunden: Liste leer („Noch keine Vergleiche angelegt.") — Fall setzt Bestands-Vergleiche (Staging-Daten) voraus, legt selbst keinen an |
| bug-626 | :158 AC-4 Kebab ohne „Vorschau" | **failed** | dito (keine Kachel auf leerem Stack) |
| bug-626 | :174 AC-2 Pausieren | passed | |
| bug-626 | :226 AC-3 Fortsetzen | passed | |
| bug-626 | :279 AC-5 Setup fortsetzen (Draft) | passed | |
| bug-626 | :317 AC-6 Menü enthält „Senden" | **failed** | dito (keine Kachel auf leerem Stack) |
| bug-626 | :339 AC-7 Kebab 5 Aktionen ohne Archivieren | **failed** | dito (keine Kachel auf leerem Stack) |
| compare-hub-save-chip | :81 AC-1 Hub öffnen → idle | passed | |
| compare-hub-save-chip | :100 AC-2 Ort entfernen → saving→idle | **failed** | Chip bleibt `idle`, nie `saving` binnen 5 s nach `hub-orte-remove` — Trace: PUT 200 erfolgt, Phase `saving` zu kurz zum Beobachten (Timing-Zusicherung) |
| compare-hub-save-chip | :136 AC-3 Fokus ohne Änderung → kein PUT | passed | |
| compare-hub-save-chip | :191 AC-4 PUT 500 → Fehler, Rollback | passed | |
| compare-mobile-vervollstaendigung | :100 mobile Karte Menü-Knopf + Aktionsblatt | passed | |
| compare-mobile-vervollstaendigung | :129 AC-22 Übersicht-Tab geteilte CompareTabs | passed | |
| compare-mobile-vervollstaendigung | :157 AC-22 Tab-Leiste per Tastatur | passed | |
| compare-mobile-vervollstaendigung | :190 AC-22 FL1 letzter Tab sichtbar | passed | |
| compare-mobile-vervollstaendigung | :225 AC-23 ⋯ öffnet Bottom-Sheet | passed | |
| compare-mobile-vervollstaendigung | :275 AC-24 Lock-Toast + floating CTA | passed | |
| compare-mobile-vervollstaendigung | :321 #2283 AC-13 Senden nur im Hub-Kopf (mobil) | **failed** | `send-confirm-yes` disabled, Dialog meldet „Im Konto ist keine E-Mail-Adresse hinterlegt — es kann nichts gesendet werden." — Stack-Konto `admin` ohne Mail-Adresse, Test legt die Vorbedingung nicht an |
| mobile-tab-bar | :39 Mobile Deep-Link ?tab=alarme | passed | |
| mobile-tab-bar | :44 Mobile Tab-Wechsel letzter Tab | passed | |
| mobile-tab-bar | :55 Mobile A11y tablist/roving tabindex | **failed** | erwartet 7 Trip-Reiter, vorhanden 5 (Reiter Versand/Vorschau seit #1743 entfallen) — veraltete Zusicherung |
| mobile-tab-bar | :77 Mobile Trigger ≥44px | **failed** | dito, `expect(count).toBe(7)` erhält 5 |
| mobile-tab-bar | :89 Mobile Badges (Etappen-Zähler) | passed | |
| mobile-tab-bar | :100 Desktop Leiste ohne Band-Scroll | **failed** | dito, 7 erwartet / 5 vorhanden |
| trips-list-aktionen | :48 AC-1 Pausieren im Zeilenmenü | passed | |
| trips-list-aktionen | :71 Reihenfolge Trip-Menü == Vergleich-Menü | passed | |
| trips-list-aktionen | :88 AC-11 archivierter Trip nicht in Liste | passed | |
| issue-724 | :41 AC-1 PUT scheitert → Feld offen + Fehler | passed | |
| issue-724 | :71 AC-2 PUT 2xx → Feld zu | passed | |
| issue-724 | :101 AC-3 Fehler bei Abbrechen zurückgesetzt | passed | |
| issue-758 | :88 AC-1 Etappen-Datum Auto-Save → idle | **failed** | Indikator bleibt `dirty` nach `fill`+`blur` des Etappen-Datums — Trace: **kein** PUT, kein Speichern-Knopf, Kopf „Nicht gespeichert" → möglicher Produkt-Befund |
| issue-758 | :108 AC-2 Ruhezustand „Gespeichert" | passed | |
| issue-758 | :116 AC-4 Save-Fehler → error | **failed** | dito: bleibt `dirty`, PUT (abgefangen mit 500) wird offenbar nie ausgelöst |
| issue-758 | :137 AC-5 Flush vor Navigation | passed | |
| issue-758 | :173 AC-7 Briefing-Tab ohne Speichern-Button | passed | |
| issue-758 | :213 AC-3 Compare-Änderung → Gespeichert | passed | |
| issue-758 | :241 AC-6 Compare-Indikator unabhängig | passed | |
| feat-880 | :86 AC-1 Overlay fixed, kein zweiter Indikator | passed | |
| feat-880 | :95 AC-2 Uhrzeit HH:MM | passed | |
| feat-880 | :107 AC-3 idle dimmt nach 3 s | passed | |
| feat-880 | :123 AC-4 Fehler → opacity 1 | passed | |
| feat-880 | :143 AC-5 Mobile Overlay über BottomNav | passed | |
| feat-880 | :203 AC-7 Compare-Editor genau ein save-indicator | passed | |
| feat-880 | :214 AC-6 Trip-/Compare-Indikator unabhängig | **failed** | `ENOENT playwright/.auth/staging-880.json` — Fall braucht einen Staging-storageState, auf dem Stack strukturell nicht lauffähig |
| (Kontrolle) hub-versand-autosave-chip | :46 AC-1 route / vergleich | passed (2) | |

### Ursachen-Klassen der 13 Roten

- **Vorbedingung/Daten fehlt auf leerem Stack (6):** bug-626 AC-1/4/6/7 (Bestands-Vergleiche), compare-mobile AC-13 (Konto-Mail), feat-880 AC-6 (Staging-storageState).
- **Veraltete Zusicherung gegen geändertes Produkt (4):** mobile-tab-bar ×3 (7 → 5 Reiter, #1743), compare-hub-kopf-einmal F007 (Ort-Löschsperre 409).
- **Verhalten weicht ab (3), per Trace nachgeprüft:**
  - compare-hub-save-chip AC-2: Trace zeigt **genau einen** `PUT /api/compare/presets/{id}` → 200 (17:59:49.970Z). Gespeichert wurde also; die Phase `saving` ist so kurz, dass die Zusicherung „Chip zeigt `saving`" nicht beobachtbar ist (Timing-Zusicherung, kein Produktdefekt erkennbar).
  - issue-758 AC-1 (und gleichartig AC-4): Trace enthält **keinen** `PUT /api/trips/…` nach `fill`+`blur` des Etappen-Datums (nur Seed-POST und Aufräum-DELETE); im Snapshot kein Speichern-Knopf, Kopf zeigt „Nicht gespeichert". Die Datumsänderung im Etappen-Reiter löst binnen 5 s kein Auto-Save aus → **möglicher Produkt-Befund** (Spec „Risiken": Chip-Fehlerzustand bei Etappen-500 / AC-13), Ursache im Code nicht weiter eingegrenzt.

## Abgleich mit der Spec (`docs/specs/modules/feat_2347_s2_paritaets_e2e.md`)

- **Befund 1** (Alt-Specs laufen in der CI nicht, „früher grün" unbelegt): bestätigt — 13 von 69 Kandidaten-Fällen sind auf dem CI-Stack rot, unbemerkt.
- **Befund 2** (`mobile-tab-bar` veraltet, 7 → 5 Reiter): bestätigt, betrifft **drei** Fälle (`:55`, `:77`, `:100`), nicht nur A11y `:55` (Zuordnungszeile 46).
- **Befund 8** (Deckung AC-24 durch issue-682): **Deckungslücke bestätigt** — keine der drei Zusicherungen ist in issue-682 tatsächlich geprüft (Lesebefund a). Die AC-24-Altdatei selbst ist grün.
- **Neu, nicht in der Spec:** compare-hub-kopf-einmal F007 scheitert an der Ort-Löschsperre (409 `location_in_use`); bug-626 AC-1/4/6/7 und compare-mobile #2283 AC-13 brauchen Vorbedingungen, die der leere Stack nicht hat (Vergleich vorhanden, Konto-Mail); feat-880 AC-6 ist staging-gebunden; issue-758 AC-1/AC-4 kein Auto-Save beim Etappen-Datum.

## Lesebefund (a) — deckt `issue-682` AC-24 aus `compare-mobile-vervollstaendigung` ab?

Referenz AC-24: `frontend/e2e/compare-mobile-vervollstaendigung.spec.ts:275` — Toast-Text `:296`, kein Tab-Wechsel `:300-303`, CTA sichtbar nach dem Tipp `:304`.

| Zusicherung | von issue-682 gedeckt? | Beleg |
|---|---|---|
| Toast-Text „erst Vergleich benennen" | **nein** | `frontend/e2e/issue-682-compare-editor-mobile.spec.ts:118-119` prüft nur `getByRole('status')` sichtbar, keinen Text |
| CTA bleibt (nach dem Tipp auf gesperrten Tab) sichtbar | **nein** (nur teilweise) | `issue-682-compare-editor-mobile.spec.ts:173-174` (AC-4a) prüft `cm-mobile-cta` sichtbar **ohne** vorherigen Lock-Tipp; AC-2 (`:100-137`) prüft die CTA gar nicht |
| kein Tab-Wechsel | **nein** | `issue-682-compare-editor-mobile.spec.ts:123-124` liest `data-active` nur aus, ohne Assertion; `:130` `expect(toast).toBeTruthy()` ist auf einen Locator immer wahr (vakuum) |

`issue-682-compare-editor-mobile.spec.ts` **steht in der Ratsche**: `.github/ci_e2e_specs.txt:374`.

## Lesebefund (b) — Ortsvergleich archivieren und `/archiv`

- **Endpunkt:** `PATCH /api/compare/presets/{id}/state` — `internal/router/router.go:285` → `UpdateComparePresetStateHandler` (`internal/handler/compare_preset.go:504`).
- **Body/Feld:** `{"archived": true}` (`compare_preset.go:498`, `Archived *bool`). Setzt `ArchivedAt = now` (`compare_preset.go:550-553`), `false` setzt `nil` (`:555`); Wiederherstellen ist quotengeprüft (`:544`). Persistiertes Feld `archived_at` (`internal/model/compare_preset.go:44-45`). Ein normaler PUT übernimmt `archived_at` unverändert vom Original (`compare_preset.go:328`).
- **Frontend-Aufruf:** `setArchived(kind, id, archived)` → `patchState(... { archived })` → `PATCH ${basis}/state` (`frontend/src/lib/components/shared/subscriptionExec.ts:76-82`, `patchState` `:46-52`).
- **Erscheint unter `/archiv`: ja.** `frontend/src/routes/archiv/+page.server.ts:21-22` lädt `GET /api/compare/presets`, `:46` filtert `p.archived_at != null`, `:51` Typ `compare`, `:54` Datum aus `archived_at`. Anzeige mit Filter „Vergleiche" in `frontend/src/routes/archiv/+page.svelte:19,37,41`; Wiederherstellen dort per `PATCH /api/compare/presets/{id}/state` mit `{archived:false}` (`+page.svelte:52-57`).
