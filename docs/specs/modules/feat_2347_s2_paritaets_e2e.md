---
entity_id: feat_2347_s2_paritaets_e2e
type: feature
created: 2026-10-26
updated: 2026-10-26
status: draft
version: "1.0"
workflow: feat-2347-s2-s4-paritaets-e2e
tags: [epic-2345, etappe-p6, ratsche, e2e, playwright, trip-compare-teilung, mandantentrennung]
---

# Paritäts-E2E, Scheibe S2: Hub-Kopf, Navigation, Speicher-Chip, Liste (#2347)

## Approval

- [ ] Approved

## Purpose

Scheibe S1 (live, PR #2623) hat die kind-Helfer, den Wächter und zwei erste Paritäts-Specs geliefert. S2 räumt den ersten großen Block der Altlast: sieben Compare-only-Specs für **Reiterleiste, Hub-Kopf, Listen-Menü, Speicher-Chip, mobile Hub-/Listenbedienung und Sende-Dialog** werden mit ihren Trip-Pendants zu **fünf CI-Specs plus einer Staging-Spec** zusammengeführt, in denen **eine** Zusicherung per Schleife (`for (const kind of HUB_KINDS)`) für Trip UND Ortsvergleich geprüft wird. Danach gilt für diese Flächen: Was für den Ortsvergleich bewiesen ist, ist für den Trip bewiesen — und umgekehrt.

Ein zweiter Zweck ist Ehrlichkeit über den Altbestand: **keine** der sieben Alt-Compare-Dateien und keines der Trip-Pendants `mobile-tab-bar`, `trips-list-aktionen`, `issue-758`, `feat-880` steht in der CI-Ratsche (siehe Befund 1). Ihr „früher grün" ist nicht belegt; mindestens `mobile-tab-bar` ist nachweislich veraltet (Befund 2). Die neuen Specs kommen deshalb **in die Ratsche** und müssen dort Filter A, B und C bestehen — erst damit bewacht die CI diese Zusicherungen überhaupt.

Reine Testschicht. Produktcode wird **nicht** geplant. Wird ein Trip-Fall beim Zusammenführen rot, ist das eine Produktlücke, die **im selben Ticket** behoben wird (Regel „bekannte Abweichung im selben Ticket", AC-13); abgeschwächt wird nie.

## Source

- **File:** `frontend/e2e/helpers.ts` (Helfer-Erweiterung), neue Specs `frontend/e2e/hub-tab-bar.spec.ts`, `hub-kopf-bearbeiten.spec.ts`, `hub-kopf-aufbau.spec.ts`, `hub-list-menu.spec.ts`, `hub-save-chip.spec.ts`, `hub-send-dialog-target.staging.spec.ts`; Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`; Ratsche `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml`
- **Identifier:** `HUB_SEL[kind]` · `ALTLAST`, `ALTLAST_MAX` · `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`
- **Produktcode:** keiner (Regel für Trip-Rot-Fälle: AC-13).

**Schicht und Querschnitts-Prüfpunkte:**
- **Schicht:** ausschließlich Testschicht (Playwright gegen den CI-Stack bzw. Staging, Python-Unit-Wächter, CI-Ratsche, Gate-Doku). Kein Code in `frontend/src/`, `internal/`, `cmd/`, `api/`, `src/` — außer AC-13 (nur bei echter Produktlücke).
- **Trip/Ortsvergleich-Teilung:** Kern dieser Spec. Kopf, Chip, Reiterleiste, Aktionsmodell und Sende-Dialog sind im Produkt **bereits geteilte Bausteine** (`SubscriptionHeader.svelte`, `SaveIndicator.svelte`, `subscriptionTabs.ts`, `subscriptionActions.ts`, `SendConfirmDialog`); die Testschicht zieht jetzt nach. Compare-eigen bleiben nur Zusicherungen über Orte-Reiter, Orte-Anzahl, Eyebrow/Breadcrumb und die 4-Stat-Übersicht (siehe Zuordnung; im Test mit Begründung als `kind`-Zweig).
- **Mandantentrennung:** Alle Specs arbeiten mit Wegwerf-Daten des Admin-Testnutzers (Präfix `E2E-GZ-`, Aufräumen im `finally`); es wird **kein** neuer datenbewegender Endpunkt eingeführt und kein Zweitnutzer gebraucht. Die kind-übergreifende Cross-User-Sperre ist in S1 (`hub-cross-user-write-block`) bewiesen. Kein Zugriff auf Konfiguration oder Trips des PO.
- **Kanäle:** nicht betroffen — kein Briefing- oder Alarm-Inhalt wird geändert. Der Sende-Dialog-Test (AC-7) fängt den Sende-Abruf ab bzw. bestätigt nie; es geht nichts an echte Empfänger.

## Gesamtschnitt #2347 (S1–S4, alles in diesem Ticket)

Der Workflow-Automat kennt keinen zweiten Durchlauf von Phase 4 bis 8 im selben Workflow, und `deploy-gregor-prod.sh` synchronisiert hart auf `origin/main`; ein gemergter, nicht ausgelieferter Zwischen-PR würde von parallelen Sitzungen ungeprüft mit ausgeliefert. Darum wird der Rest wie S1 in **eigenen Workflows desselben Tickets** geführt (kein Abspalten: Ticket #2347 und Epic #2345 bleiben, das Issue bleibt offen bis S4). `.github/ci_e2e_specs.txt` ist Konfliktpunkt ⇒ die Scheiben werden strikt nacheinander gemergt.

| Scheibe | Inhalt | Status |
|---|---|---|
| S1 | Helfer; Versand-Autosave + Chip je kind; Cross-User-Sperre je kind; Wächter im Ratschenmodus (ALTLAST 48) | **live** (PR #2623, `9c7b41f94`) |
| **S2 (diese Spec)** | Reiterleiste, Hub-Kopf, Listen-Menü, Speicher-Chip, mobile Liste/Hub-Blatt, Sende-Dialog: 7 Compare-Altdateien + Trip-Pendants → 5 CI-Specs + 1 Staging-Spec; ALTLAST 48 → 41 | diese Spec |
| S3a | Alarme / Wertebereiche / Wetter-Metriken / Wertprops: `compare-alarme-speichert-selbst`, `-alarme-wertprops`, `-wertebereiche-speichert-selbst`, `-wertebereiche-wertprops`, `-wetter-metriken-speichert-selbst`, `-editor-autosave-user-isolation`, `compare-editor-slice3` AC-4..9, `compare-hub-inline-edit` (Wertebereich-Teil) | folgt |
| S3b | Versand-Trio (`compare-hub-versand-inline`, `-briefing-times`, Rest `compare-versand-speichert-selbst`), `versand-tab-vergleich`, Konflikt-412, Radar-Toggle, Stundenverlauf, `compare-editor-autosave`, `issue-682-compare-editor-mobile` ↔ `issue-661`, `.staging`-Specs, `feat-1461-s3b2b`, `fix-1350-*` | folgt |
| S4 | Gruppe ohne Trip-Pendant mit `gz-eigenstaendig:`-Kopf; #2243-Leichen; ALTLAST leer; Ratsche final | folgt |

Je Scheibe: `E2E_MIN_EXECUTED_HAUPT` neu **messen**, Filter A/B/C.

## Befund-Korrekturen gegenüber Ticket und Analyse (am Code gemessen, 2026-10-26)

1. **Die Alt-Specs laufen in der CI gar nicht.** `.github/ci_e2e_specs.txt` enthält von allen betroffenen Dateien nur `issue-724-trip-name-save-error` (Z. 379) und `trip-hub-kopf-region-aktivitaet` (Z. 389). `compare-tab-bar`, `compare-hub-name-region-profil`, `compare-hub-kopf-einmal`, `bug-626-compare-menu-actions`, `compare-hub-save-chip`, `compare-mobile-vervollstaendigung`, `compare-send-dialog-target.staging`, aber auch `mobile-tab-bar`, `trips-list-aktionen`, `issue-758-save-indicator`, `feat-880-autosave-overlay`, `issue-268-*`, `trips-list-send` stehen **nicht** in der Ratsche. Z. 126-127 der Ratsche nennt `compare-hub-save-chip:173` und `compare-hub-name-region-profil:240` nur als Filter-A-Ablehnungsgrund (Aufnahme 2026-09-18). **Folge:** (a) Die Analyse-Zeile „Ratschen-Zeilen umhängen" für `compare-hub-name-region-profil` trifft nicht zu — es gibt nichts umzuhängen; in der Ratsche wird **ein** Eintrag entfernt (`issue-724`) und **fünf** werden aufgenommen. (b) „Alt war grün" ist unbelegt; jeder Altfall wird im RED-Schritt gegen den CI-Stack neu gemessen, und ein roter Altfall ist ein Befund, keine Vorlage zum Abschwächen.
2. **`mobile-tab-bar.spec.ts` ist veraltet.** Sie erwartet **7** Reiter (`frontend/e2e/mobile-tab-bar.spec.ts:62`, `:81`, `:105`). Das Produkt hat seit #2287/#1743 genau **5** (`frontend/src/lib/components/shared/subscriptionTabs.ts`: `uebersicht` + Punkte-Reiter + 3 × `schwanz`; `TripTabs.svelte:78` leitet daraus ab). Drei der sechs Trip-Fälle sind vermutlich seit #1743 rot, unbemerkt, weil die Datei nicht in der Ratsche steht. Das Ziel `hub-tab-bar` prüft **5** für beide kinds.
3. **`bug-626-compare-menu-actions`:** Titel von AC-7 sagt „genau 5 Aktionen" (`:339`), die Prüfung verlangt `toHaveCount(6)` (`:366`) — der Titel ist veraltet, **6** gilt (`subscriptionActions.ts`: `pause|resume, send, alarms, weather, edit, delete`). Zwölf `waitForTimeout` (`:35,144,164,197,207,216,246,254,262,296,323,347`), UI-`login(page)` im `beforeEach` (`:123`; verbraucht Login-Kontingent 30/h — die neue Spec nutzt den `storageState` aus `global.setup.ts`), und AC-1/4/6/7 greifen auf `.first()` irgendeiner Kachel zu (Voraussetzung „ein aktiver Vergleich existiert im Konto") — datenabhängig, wird durch Eigen-Seed je kind ersetzt.
4. **Listen-Testids sind kind-spezifisch, das Menü selbst nicht:** Vergleich `compare-tile-<id>` + `compare-row-kebab` + `compare-status-pill` (`routes/compare/+page.svelte:70,271-272`), Trip `trip-row-<id>` + `trip-row-menu-btn` (`routes/trips/+page.svelte:247-248`). „Bearbeiten"/„Setup fortsetzen" führen beide auf den Hub (`/trips/<id>`: `routes/trips/+page.svelte:110-111`; `/compare/<id>`, `/edit` ist reiner Redirect). Mobil nutzen beide denselben Baustein (`subscription-card-<id>`, `subscription-card-menu-<id>`, `subscription-action-*`).
5. **Kopf-Testids tragen ein Präfix `p`:** `trip` bzw. `compare-hub` (`SubscriptionHeader.svelte:~104-165`: `${p}-name-edit-toggle`, `${p}-name-edit`, `${p}-name-save`, `${p}-region-edit(-toggle)`, `${p}-profil-option-<wert>`, `${p}-profil-knopf`, `${p}-profil-auswahl-option-<wert>`, `${p}-<feld>-save-error`). Überschrift: Trip `trip-detail-h1` (`TripHeader.svelte:117`), Vergleich ohne Testid (`getByRole('heading', { level: 1 })`). Das Feld hinter dem Profil heißt im Trip `activity` (8 Werte), im Vergleich `profil` (4 Werte); Region steht im Trip in `region`, im Vergleich in `display_config.region`.
6. **`compare-hub-kopf-einmal`:** 11 Quelltext-Fälle, aber **12** ausgeführte (AC-10-Schleife über zwei Viewports; AC-8-Schleife hat nur noch den Desktop-Eintrag, `:113-115`). Die Fallzahl-Prüfung (AC-10) zählt deshalb ausgeführte Fälle (`--list`), nicht `test(`-Vorkommen.
7. **`compare-send-dialog-target.staging`:** Es ist eine Validierungs-Spec, kein harter Test — Dialogtext und Button-Zustand gehen nur per `console.log` (`:38,41`), Screenshots nach `docs/artifacts/fix-1471-sende-dialog-ziel` (`:6,32`). Hart sind nur `not.toContain('0 Empfänger')`, `toBeVisible` und in Runde 2 `expect(isDisabled).toBe(true)` (`:109`) — das hängt am **ersten** Vergleich im Staging-Bestand (`.first()`), also an fremden Daten. Config `frontend/playwright.compare-send-dialog-target.staging.config.ts:22-24` trägt `dependencies` doppelt. Beides wird mit Eigen-Seed je kind bereinigt.
8. **`compare-mobile-vervollstaendigung` mischt drei Themen:** Liste mobil (AC-21 → Liste), Hub (AC-22/23/13 → Hub) und **Anlege-Editor** (AC-24, `/compare/new`). AC-24 (Lock-Toast + floating CTA) ist durch `issue-682-compare-editor-mobile` AC-2 (`:100`) und AC-4a (`:168`) abgedeckt, die in S3b mit `issue-661-trip-new-mobile` (`tn-lock-toast`) auf beide kinds gehoben werden. Er wird nicht verschoben, sondern dort belassen; die Deckung (Toast-Text „erst Vergleich benennen", CTA bleibt sichtbar, kein Tab-Wechsel) wird im RED gelesen — fehlt eine der drei Zusicherungen, wird sie in `issue-682` AC-2 ergänzt, bevor die Alt-Datei fällt.
9. **`issue-268-trips-mobile-card-stack`** (7 Fälle, Trip-Liste mobil) hat sechs datenabhängige `test.skip()` (`:77,109,136,159,197,220`) und steht nicht in der Ratsche. Sie bleibt in S2 unberührt (Trip-eigene Kartenstapel-Zusicherungen, Tippflächen); das Aufräumen ist ein Sammelposten für #1199 (LOW, kein Nutzerfehler).
10. **Konfig-Verweise:** Auf die sieben Alt-Dateien zeigen `frontend/playwright.1256-s8.staging.config.ts:26` (nur `compare-mobile-vervollstaendigung`), `frontend/e2e/playwright.1273-s1.red.config.ts:28,31`, `playwright.1273-s2.red.config.ts:28,31`, `playwright.2284-s1.red.config.ts:28,31` und `frontend/playwright.compare-send-dialog-target.staging.config.ts:20,23`; dazu je ein Staging-Setup (`feat-1256-s8.staging.setup.ts`, `compare-hub-save-chip.staging.setup.ts`, `compare-hub-name-region-profil.staging.setup.ts`, `compare-hub-kopf-einmal.staging.setup.ts`, `compare-send-dialog-target.staging.setup.ts`). Die RED-Configs und die vier ersten Setups sind nach dem Löschen verwaist (Befund per `grep -rl`: sonst nur Kommentar-Verweise). `playwright.758.staging.config.ts` und `playwright.880.staging.config.ts` zeigen auf Dateien, die **bleiben**.
11. **Quota:** Vergleiche sind pro Nutzer auf 2 aktive begrenzt (409; `compare-tab-bar.spec.ts:30-45` räumt dafür `E2E-GZ`-Altbestand). `seedHub('vergleich')` muss deshalb strikt im `finally` aufräumen, und Fälle, die zwei Vergleiche brauchen, dürfen nicht parallel laufen (`workers: 1` in CI, `playwright.config.ts`).

## Abgrenzung

Nicht in S2: alles aus den Scheiben S3a, S3b, S4 (siehe Gesamtschnitt) und die #2243-Leichen. Die Trip-Dateien `trip-hub-kopf-region-aktivitaet.spec.ts` (außer AC-11), `issue-758-save-indicator.spec.ts`, `feat-880-autosave-overlay.spec.ts`, `issue-268-*`, `trips-list-send.spec.ts` bleiben in S2 **unverändert** (Trip-eigene Auslöser, Staging-Setups, Etappen-Zusicherungen). Doppelte Trip-Zusicherungen, die durch die neuen Schleifen mit abgedeckt sind (z. B. Name ändern in `trip-hub-kopf` AC-1), werden **nicht** gelöscht — Bereinigen von Dopplungen ist kein Zusicherungsverlust-Risiko wert; Sammelposten für S4.

## Estimated Scope

- **LoC (Testcode, netto):** ca. +1.500 / −2.300 (6 neue Specs ~1.600, Helfer ~50, Wächter/Ratsche/Doku ~40; gelöscht: 7 Compare-Altdateien ≈ 1.800, `mobile-tab-bar` 116, `issue-724` ~130, `trips-list-aktionen` ~110, 3 RED-Configs, 4 Setups, 1 Config). Alles Testcode/Doku, zählt **nicht** als produktive Spec-Datei (`loc_limit_override` nicht nötig; sonst `workflow.py status` fragen).
- **Files:** ca. 38 (siehe „Berührte Dateien").
- **Effort:** high (Zusammenführung mit Neumessung des Altbestands, 3× Filter-B-Läufe).

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/e2e/helpers.ts` (`HubKind`, `HUB_KINDS`, `seedHub`, `openHub`, `hubApiPath`; S1) | module | Basis jeder neuen Spec |
| `frontend/e2e/hub-versand-autosave-chip.spec.ts`, `hub-cross-user-write-block.spec.ts` (S1) | module | Vorbilder (Schleife, `expect.poll`-Stabilität statt Schlaf) |
| `SubscriptionHeader.svelte`, `TripHeader.svelte`, `SaveIndicator.svelte`, `subscriptionTabs.ts`, `subscriptionActions.ts`, `SubscriptionCard.svelte`, `TripTabs.svelte`, `CompareTabs.svelte` | module | geprüfte, geteilte Bausteine (unverändert) |
| `frontend/e2e/global.setup.ts` | module | Admin-`storageState`, Seed-Orte `e2e-loc-innsbruck`/`-stubai`/`-zillertal` |
| `.github/ci_e2e_specs.txt`, `ci.yml` Job `e2e`, `.github/scripts/e2e_gate.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | CI | Positivliste, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT` |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | test | `ALTLAST`, `ALTLAST_MAX` |

## Implementation Details

### Helfer-Erweiterung `HUB_SEL[kind]` (dünn, keine Assertions)

In `frontend/e2e/helpers.ts` neben `HUB_KINDS` ein reines Konstanten-Objekt, **ohne** Assertions und ohne Wartelogik:

```ts
export const HUB_SEL: Record<HubKind, {
  kopf: 'trip' | 'compare-hub';          // Testid-Präfix des SubscriptionHeader
  reiter: string;                         // `${reiter}-<id>`, Panel: `${panel}-<id>`
  panel: string;
  reiterListe: string;                    // trip-detail-tab-list | compare-detail-tab-list
  punkteReiter: 'etappen' | 'orte';       // kind-eigener Punkte-Reiter
  profilFeld: 'activity' | 'profil';      // Feld im gespeicherten Stand
  profilWert: string;                     // gültiger, vom Seed verschiedener Wert (skitour | wandern)
  liste: { url: string; zeile: (id: string) => string; menue: string };
  hubUrl: (id: string) => RegExp;         // /trips/<id> bzw. /compare/<id>
}>;
```

Zusätzliche Seed-Optionen laufen über das bestehende `seedHub(request, kind, { extra })` (z. B. 3 Orte bzw. 3 Etappen für den Badge-Fall, `schedule: 'manual'` bzw. `PATCH /api/trips/<id>/state {paused:true}` für „pausiert", `location_ids: []` bzw. Etappen ohne Datum für „Entwurf"). Seed-Besonderheiten je kind stehen im jeweiligen Spec, nicht im Helfer. Wartebedingungen ausschließlich über `page.waitForResponse`, `expect.poll`, `toHaveAttribute('data-state', …)`, `toHaveCount`.

### Neue Specs und ihre Fälle (Zielbezeichner, auf die die Zuordnung verweist)

Jeder Fall läuft als `for (const kind of HUB_KINDS) test(\`<ID> (${kind}): …\`)`; Testtitel tragen `kind`. Kind-eigene Zweige (`if (kind === 'vergleich')`) tragen einen Kommentar mit Begründung.

**`hub-tab-bar.spec.ts` (HT)** — Reiterleiste, Desktop 1280 und Mobil 390
- HT-1 Deep-Link `?tab=alarme` positioniert den aktiven Reiter sichtbar (Mobil, `.mtabbar`, Box innerhalb 0..391 px)
- HT-2 Alt-Link `?tab=versand` landet aktiv auf Wetter-Metriken, URL endet auf `?tab=wetter-metriken#versand`
- HT-3 Letzter Reiter (`alarme`) per Wisch-Äquivalent (`scrollIntoViewIfNeeded`) + echtem Klick erreichbar, Panel wechselt, kein Reiter `vorschau`
- HT-4 A11y: `tablist`/`tab`, **genau 5** Reiter, `aria-selected`, roving `tabindex` (aktiv `0`, übrige `-1`), Pfeiltaste rechts aktiviert und fokussiert den Folge-Reiter
- HT-5 Alle Trigger ≥ 44 px hoch (Mobil)
- HT-6 Badge am Punkte-Reiter zeigt die Anzahl (3 Etappen bzw. 3 Orte)
- HT-7 Desktop: alle 5 Reiter liegen ohne Band-Scroll im Viewport (rechte Kante ≤ 1280)
- HT-8 Desktop-Optik je kind: Vergleich Badge-Hintergrund `rgb(236, 234, 217)` und 13 px Schrift; Trip aktiver Reiter transparent (`rgba(0, 0, 0, 0)`) — Werte bleiben je kind wie in den Alt-Specs (kind-Zweig, Begründung: Optik-Werte sind nicht Gegenstand der Teilung)
- HT-9 Echter Klick auf den Punkte-Reiter wechselt das Panel; das Übersicht-Panel ist danach nicht mehr im DOM
- HT-10 *(nur vergleich, compare-eigen)* Mobil: Übersicht zeigt genau 4 Stat-Karten im 2×2-Raster (Status / Nächster Versand / Zuletzt raus / Kanäle), kein „Briefings"-Stat, kein `compare-detail-stat-briefings` — Begründung: Inhalt der Übersicht ist kind-eigen (Trip-Cockpit)

**`hub-kopf-bearbeiten.spec.ts` (KB)** — Kopf inline bearbeiten
- KB-1 Name ändern ⇒ Überschrift sofort neu, nach Reload persistent (Server-Stand)
- KB-2 Region ändern ⇒ sichtbar, persistent (Feldpfad je kind laut `HUB_SEL`/Spec-Konstante)
- KB-3 Profil/Aktivität wählen ⇒ markiert (`data-selected`), persistent
- KB-4 Nur Name ändern ⇒ der PUT-Rumpf trägt **genau einen** geänderten Schlüssel; Orte/Etappen, Empfänger, Zeitplan, Profil bleiben unverändert (Fehlerklasse #2375/#2381)
- KB-5 Name ändern, dann im Reiter Wertebereiche eine Änderung committen ⇒ Name bleibt (Stabilitätsfenster per `expect.poll` auf den Server-Stand, kein Schlaf)
- KB-6 Mobil 375: Name, Region, Profil ändern ⇒ nach Reload persistent (Profil über Knopf + Auswahl)
- KB-7 PUT-500 beim Namen ⇒ Fehlermeldung `role=alert`, Eingabe bleibt offen mit dem Versuchswert, Server-Name und Überschrift unverändert
- KB-8 PUT-500 beim Profil/der Aktivität ⇒ Fehler unter den Kacheln, bisherige Kachel bleibt die einzige Auswahl
- KB-9 PUT 2xx ⇒ Feld schließt, Name aktuell, keine Fehlermeldung
- KB-10 Fehlermeldung verschwindet bei „Abbrechen" und erneutem Öffnen

**`hub-kopf-aufbau.spec.ts` (KA)** — Kopf-Markup und Kopf-Bedienung
- KA-1 Desktop: jede Kopf-Testid genau einmal im DOM (Zählung **ohne** `:visible`) und sichtbar
- KA-2 Mobil 375: dasselbe (Knopf + Auswahl statt Kacheln)
- KA-3 Region höchstens 60 Zeichen, Unterzeile während der Bearbeitung weg (Desktop **und** Mobil)
- KA-4 Bedienung Desktop: Vorbelegung der Felder, Kacheln während des Speicherns gesperrt, Fallback-Text „—" bei leerer Region, „Abbrechen" verwirft den Fehler
- KA-5 Mobil: Versand-Abschnitt ohne Test-Senden; Hub-Kopf-„Senden" im Viewport, öffnet `send-confirm-dialog`, „Senden" löst **genau einen** (abgefangenen) Sende-Abruf aus
- KA-6 *(nur vergleich)* Mobil: Eyebrow „Orts-Vergleich · Hub", Unterzeile „Wandern · 2 Orte", kein „· ·"
- KA-7 *(nur vergleich)* Desktop: keine Eyebrow, Breadcrumb „ORTS-VERGLEICHE / Hub", Unterzeile mit Profil
- KA-8 *(nur vergleich)* Orte-Anzahl: Desktop zählt gespeicherte IDs („· 2 Orte"), Mobil aufgelöste Orte („· 1 Ort", Singular), je genau ein Span im DOM
- KA-9 *(nur vergleich)* Desktop-Singular bei Vergleich mit einem Ort
  (KA-6..9 sind compare-eigen, weil Eyebrow/Breadcrumb/Orte-Anzahl Orte-Vergleichs-Rahmen sind; das Trip-Gegenstück „Eyebrow nur Datum" bleibt in `trip-hub-kopf-region-aktivitaet` AC-2.)

**`hub-list-menu.spec.ts` (LM)** — Listen-Menü und mobile Aktionen
- LM-1 „Bearbeiten" im Listen-Menü führt auf den Hub dieses Eintrags (URL `hubUrl(id)`, kein `/edit`)
- LM-2 Das Menü bietet keine Aktion „Vorschau"
- LM-3 „Pausieren" pausiert wirklich: UI-Status „pausiert" **und** Serverstand (Trip `paused_at` gesetzt bzw. Vergleich `schedule` ≠ `daily`); Etappen/Orte bleiben unverändert; danach steht dort „Fortsetzen"
- LM-4 „Fortsetzen" setzt fort: UI-Status „aktiv", danach „Pausieren"
- LM-5 Entwurf: „Setup fortsetzen" öffnet den Hub
- LM-6 Das Menü enthält „Senden"
- LM-7 Aktives Eintrags-Menü hat **genau 6** Einträge in fester Reihenfolge `Pausieren, Senden, Alarme, Wetter-Metriken, Bearbeiten, Löschen`, ohne „Archivieren" (ersetzt „Trip-Menü == Ortsvergleich-Menü": jetzt prüft jede Art die Soll-Liste selbst)
- LM-8 Ein archivierter Eintrag erscheint nicht in der Liste und ist unter `/archiv` auffindbar
- LM-9 Mobil: Karte mit Menü-Knopf; Menü-Knopf öffnet das Aktionsblatt; Tipp auf die Karte öffnet den Hub; fünf Status-Pillen
- LM-10 Mobil im Hub: ⋯ (`subscription-kebab`) öffnet das Blatt mit **genau** Fortsetzen / Archivieren / Löschen (pausierter Eintrag), ohne Senden / Vorschau / Bearbeiten; Schließen funktioniert

**`hub-save-chip.spec.ts` (SC)** — geteilter Speicher-Chip; **Auslöser ist kind-spezifisch, die Chip-Assertions sind gemeinsam**
- SC-1 Hub öffnen ⇒ Chip `idle`, Text „Gespeichert", genau ein `save-indicator` im DOM
- SC-2 Echte Änderung ⇒ `saving` → `idle` mit `.save-time` `HH:MM`, Änderung nach Reload persistent. Auslöser: Vergleich `?tab=orte` → `hub-orte-remove`; Trip `?tab=etappen` → Etappen-Datum ändern + blur (Vorbild `issue-758` AC-1)
- SC-3 Zahlenfeld im Reiter Wertebereiche fokussieren/verlassen ohne Änderung ⇒ Chip (Text samt Zeitstempel) unverändert, **null** PUTs — Stabilitätsfenster per `expect.poll` statt Schlaf
- SC-4 PUT-500 auf den Auslöser aus SC-2 ⇒ Chip `error`, Text „Fehler beim Speichern", Rollback sichtbar (Orte wieder zwei bzw. Datum zurück)
- SC-5 Region im Kopf speichern (PUT 800 ms verzögert) ⇒ Chip `saving` ⇒ `idle`, „Gespeichert", `.save-time` `HH:MM`
- SC-6 Profil/Aktivität im Kopf wählen (PUT verzögert) ⇒ Chip `saving` ⇒ `idle` am selben Controller, danach weiterhin genau ein `save-indicator`

**`hub-send-dialog-target.staging.spec.ts` (SD)** — bleibt **Staging-Spec**, nicht in der Ratsche
- SD-1 Liste rendert; der Lösch-Dialog behält seinen eigenen Text („… löschen?") und wird abgebrochen; der Sende-Dialog (`send-confirm-dialog`) nennt das tatsächliche Ziel (nie „0 Empfänger"); ist kein Ziel zustellbar, ist „Senden" gesperrt, ein erzwungener Klick löst **keinen** Sende-Abruf aus (Request-Liste bleibt leer, per `expect.poll`-Stabilität statt `waitForTimeout(1500)`)
- SD-2 Stress: zweimal Menü → Senden → Abbrechen, dann fünf schnelle erzwungene Klicks auf den gesperrten Button ⇒ kein Sende-Abruf, Dialog bleibt stabil
  Eigen-Seed je kind **ohne** zustellbares Ziel (Vergleich `empfaenger: []`; Trip: Kanäle aus bzw. leere Empfänger) statt `.first()` irgendeines Staging-Eintrags. Screenshots und `console.log` entfallen (keine Zusicherungen); Dateien werden zu `hub-send-dialog-target.staging.spec.ts`, `hub-send-dialog-target.staging.setup.ts`, `frontend/playwright.hub-send-dialog-target.staging.config.ts` (doppeltes `dependencies` bereinigt).

### Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`

Die sieben Einträge `bug-626-compare-menu-actions.spec.ts`, `compare-hub-kopf-einmal.spec.ts`, `compare-hub-name-region-profil.spec.ts`, `compare-hub-save-chip.spec.ts`, `compare-mobile-vervollstaendigung.spec.ts`, `compare-send-dialog-target.staging.spec.ts`, `compare-tab-bar.spec.ts` verschwinden aus `ALTLAST` (heute 48 Einträge, am Test selbst nachgezählt) ⇒ **41**; `ALTLAST_MAX` 48 → **41** (Literal, nicht `len(ALTLAST)`). Die neuen Dateinamen enthalten weder „compare" (Regel 1 greift nicht) noch verstoßen sie gegen Regel 2 (alle tragen `HUB_KINDS`). Aktualisieren: Docstring-Zeile „Am ENDSTAND von S1 gemessen (2026-10-26: 46 × Regel 1, 2 × Regel 2)" auf „… S2: 39 × Regel 1, 2 × Regel 2"; `docs/reference/gates_und_ratschen.md` (Abschnitt Wächter, „bei Einführung 48" um „S2: 41" ergänzen; Prüfdatum 2027-01-24 unverändert).

### CI-Kopplung

- `.github/ci_e2e_specs.txt`: Eintrag `e2e/issue-724-trip-name-save-error.spec.ts` (Z. 379) entfernen; neu `e2e/hub-kopf-aufbau.spec.ts`, `e2e/hub-kopf-bearbeiten.spec.ts`, `e2e/hub-list-menu.spec.ts`, `e2e/hub-save-chip.spec.ts`, `e2e/hub-tab-bar.spec.ts` (alphabetische Reihenfolge der Datei beachten); Kommentarblock „Aufnahme 2026-10-26 (#2347 S2)" mit Filter-A/B/C-Ergebnis; Z. 126-127 (Filter-A-Ablehnungsgrund für `compare-hub-save-chip`/`-name-region-profil`) um „(ersetzt durch hub-save-chip/hub-kopf-bearbeiten, #2347 S2)" ergänzen.
- `ci.yml` `E2E_MIN_SPECS`: 64 → **68** (64 − 1 `issue-724` + 5), exakt gleich `grep -c '^e2e/' .github/ci_e2e_specs.txt` (der Kern-Test erzwingt Gleichheit); Herleitung im Kommentar fortschreiben.
- `ci.yml` `E2E_MIN_EXECUTED_HAUPT`: **wird in `/50` gemessen, nicht geschätzt** — `npx playwright test --list` über die Hauptlauf-Auswahl (Positivliste ohne `bug-703`) am Endstand. **Richtung: steigt** (369 → Größenordnung 450: +HT 19, +KB 20, +KA 16, +LM 20, +SC 12 = +87, −3 `issue-724`, −2 AC-11 aus `trip-hub-kopf-region-aktivitaet`); weicht die Messung von der Größenordnung deutlich ab, wird die Abweichung im Kommentar begründet. Es gilt immer die Messung (Präzedenz S1, PR #2495).
- `tests/unit/test_e2e_positivliste_ratschen_bindung.py`: `MANDANTEN_SPECS` bleibt unverändert (S1-Namen); der Bindungstest bleibt grün durch Gleichheit der Zahlen.
- CI-Laufzeit: etwa 90 zusätzliche Fälle bei `workers: 1`; `ci.yml` setzt für den Job kein `timeout-minutes` (Standard des Runners). Gemessene Laufzeit wird im PR festgehalten.

### Config- und Verweis-Hygiene (`grep -rn <name> frontend .github tests` am Endstand: keine Treffer auf gelöschte Namen außer Historie in `docs/`)

- Löschen: `frontend/e2e/playwright.1273-s1.red.config.ts`, `playwright.1273-s2.red.config.ts`, `playwright.2284-s1.red.config.ts`; `frontend/playwright.1256-s8.staging.config.ts`; Setups `compare-hub-save-chip.staging.setup.ts`, `compare-hub-name-region-profil.staging.setup.ts`, `compare-hub-kopf-einmal.staging.setup.ts`, `feat-1256-s8.staging.setup.ts`.
- Umbenennen: `compare-send-dialog-target.staging.setup.ts` → `hub-send-dialog-target.staging.setup.ts`; `playwright.compare-send-dialog-target.staging.config.ts` → `playwright.hub-send-dialog-target.staging.config.ts` (`testMatch` und `storageState`-Pfad `staging-1471.json` unverändert nachziehen).
- Kommentar-Verweise nachziehen (nur Text): `frontend/e2e/issue-953.staging.setup.ts:4`, `metrik-grundauswahl-schneidet-kanal.staging.setup.ts:6`, `compare-edit-redirect.staging.setup.ts:6`, `compare-edit-redirect.spec.ts:15`, `compare-hub-fidelity-s8c.spec.ts:11`, `compare-editor-fidelity-s8d.spec.ts:19`, `hub-reiter-alt-kennungen-umleitung.spec.ts:66,374`, `trip-hub-kopf-region-aktivitaet.spec.ts:202`, `frontend/src/lib/components/shared/__tests__/subscription_header_{bedienlogik,einmal_gerendert,kontextneutral}.test.ts` (Verweis auf `compare-hub-kopf-einmal.spec.ts` → `hub-kopf-aufbau.spec.ts`).
- `frontend/playwright.758.staging.config.ts` und `playwright.880.staging.config.ts` bleiben (Ziel-Dateien bleiben). `frontend/src/routes/trips/__tests__/trip_list_pause.test.ts:11` verweist auf `trips-list-aktionen.spec.ts` ⇒ auf `hub-list-menu.spec.ts` ändern.

### Veränderungen an Trip-Dateien

- **gelöscht:** `mobile-tab-bar.spec.ts` (6 Fälle → HT), `issue-724-trip-name-save-error.spec.ts` (3 Fälle → KB; Ratschen-Zeile 379 geht), `trips-list-aktionen.spec.ts` (3 Fälle → LM).
- **geändert:** `trip-hub-kopf-region-aktivitaet.spec.ts` — AC-11 (Trip) und AC-11 (Vergleich) entfallen (→ SC-5, SC-6); Kopfkommentar aktualisieren; alles andere unverändert.
- **unverändert:** `issue-758`, `feat-880`, `issue-268`, `trips-list-send`.

## Expected Behavior

- **Input:** CI-Lauf `e2e` gegen den isolierten Stack; Unit-Lauf des Wächters; manueller Staging-Lauf für `hub-send-dialog-target.staging`.
- **Output:** Reiterleiste, Kopf, Listen-Menü, Speicher-Chip und Sende-Dialog werden für Trip und Ortsvergleich durch **dieselben** Specs mit denselben Zusicherungen geprüft; die CI bewacht sie (Ratsche). Eine neue Compare-only-Spec der S2-Gruppe wäre für den Wächter wieder ein Verstoß.
- **Side effects:** Wegwerf-Daten `E2E-GZ-…` (Aufräumen im `finally`, Sicherheitsnetz `global.teardown.ts`); keine Produktdaten, kein Zweitnutzer, kein echter Versand.

## Acceptance Criteria

- **AC-1:** Given ein Trip und ein Ortsvergleich mit je drei Etappen bzw. drei Orten / When der Nutzer die Reiterleiste auf dem Handy (390 px) und am Desktop (1280 px) bedient / Then gilt für Trip UND Ortsvergleich gleichermaßen: genau fünf Reiter, der per Deep-Link angesteuerte und der zuletzt gewählte Reiter liegt vollständig sichtbar, der Alt-Link `?tab=versand` landet auf Wetter-Metriken, Pfeiltasten wechseln den Reiter und setzen den Fokus mit, jede Tippfläche ist mindestens 44 px hoch, die Anzahl am Punkte-Reiter stimmt und am Desktop liegen alle Reiter ohne Scrollen im Fenster — in einer Spec, die per Schleife über beide kinds läuft. Nur die 4-Kennzahlen-Übersicht des Ortsvergleichs und die Optik-Werte je Art sind eigene Zweige.
  - Test: `hub-tab-bar.spec.ts` (HT-1..HT-10), Ratsche, CI-Stack.
  - Mutation (je kind getrennt, muss rot werden): Badge-Zähler am Punkte-Reiter in `CompareTabs.svelte` (`:156-159`) bzw. `TripTabs.svelte` (`:78-91`) entfernen → nur der Fall des betroffenen kind rot; Pfeiltasten-Handler im geteilten `MTabBar` entfernen → beide kinds rot; Reiteranzahl durch Einfügen eines sechsten Reiters in `REITER_DEFINITION` → beide rot.
- **AC-2:** Given ein Trip und ein Ortsvergleich im Hub / When der Nutzer Name, Region und Aktivitätsprofil im Kopf ändert (Desktop und Handy), den Namen mit einem Server-Fehler (500) speichert, das Profil mit 500 speichert oder die Eingabe abbricht / Then gilt für Trip UND Ortsvergleich: die neue Angabe steht sofort im Kopf und ist nach dem Neuladen gespeichert, der Speicher-Aufruf enthält genau das eine geänderte Feld und lässt alle übrigen Daten unberührt, ein Name aus einer früheren Änderung geht beim späteren Speichern in einem anderen Reiter nicht verloren, bei einem Server-Fehler bleibt die Eingabe offen mit dem Versuchswert und eine Fehlermeldung ist sichtbar, bei Erfolg schließt das Feld ohne Fehlermeldung, und eine alte Fehlermeldung verschwindet nach Abbrechen und erneutem Öffnen.
  - Test: `hub-kopf-bearbeiten.spec.ts` (KB-1..KB-10), Ratsche.
  - Mutation: in `SubscriptionHeader.svelte` `save()` den Rumpf um ein zweites Feld erweitern → KB-4 beider kinds rot; `fieldError`-Anzeige des Namens entfernen → KB-7 beider kinds rot; den Seitenhandler `onSaveField` nur im Trip (`TripHeader.svelte`) bzw. nur im Vergleichs-Hub das Profil verwerfen → nur der Fall dieses kind rot (beweist: kein Fall prüft nur „Code steht dort").
- **AC-3:** Given ein Trip und ein Ortsvergleich im Hub / When der Kopf gerendert und bedient wird / Then gilt für Trip UND Ortsvergleich: jedes Kopf-Bedienelement existiert genau einmal im DOM (nicht ein ausgeblendetes Zweitexemplar), die Region ist auf 60 Zeichen begrenzt und die Unterzeile verschwindet während der Bearbeitung, Vorbelegung, Sperre der Kacheln während des Speicherns und der Fallback „—" stimmen, und auf dem Handy ist „Senden" nur im Hub-Kopf erreichbar (kein Test-Senden im Versand-Abschnitt) und löst genau einen Versand-Aufruf aus. Compare-eigen bleiben Eyebrow „Orts-Vergleich · Hub", Breadcrumb und Orte-Anzahl samt Singular.
  - Test: `hub-kopf-aufbau.spec.ts` (KA-1..KA-9).
  - Mutation: zweites Kopf-Markup in einer Seite (Verdopplung einer Testid) → KA-1/KA-2 des betroffenen kind rot; `regionMaxLength` im Trip von 60 auf 200 → nur KA-3 (route) rot, beim Vergleich entsprechend nur KA-3 (vergleich); den Versand-Aufruf im Hub-Kopf doppelt auslösen → KA-5 beider kinds rot.
- **AC-4:** Given je ein aktiver, ein pausierter, ein Entwurfs- und ein archivierter Trip bzw. Ortsvergleich / When der Nutzer in der Liste (Desktop) das Zeilenmenü öffnet / Then gilt für Trip UND Ortsvergleich: „Bearbeiten" und „Setup fortsetzen" öffnen den Hub des Eintrags, „Vorschau" fehlt, „Senden" ist vorhanden, ein aktiver Eintrag zeigt genau sechs Einträge in der festen Reihenfolge Pausieren, Senden, Alarme, Wetter-Metriken, Bearbeiten, Löschen (kein Archivieren), „Pausieren" pausiert wirklich (Anzeige UND gespeicherter Stand) und danach steht dort „Fortsetzen", „Fortsetzen" macht den Eintrag wieder aktiv, und ein archivierter Eintrag steht nicht in der Liste, ist aber im Archiv auffindbar — ohne `waitForTimeout` (alle zwölf aus `bug-626` sind durch Ereignis-Warten ersetzt).
  - Test: `hub-list-menu.spec.ts` (LM-1..LM-8), Ratsche, Anmeldung über `storageState` (kein UI-Login).
  - Mutation: in `subscriptionActions.ts` den Eintrag `weather` streichen oder die Reihenfolge von `send`/`alarms` tauschen → LM-7 beider kinds rot; in `routes/trips/+page.svelte:110` das Ziel von „Bearbeiten" ändern → nur LM-1 (route) rot; das Pausieren im Vergleich nur in der Anzeige, nicht im Speicher durchführen → nur LM-3 (vergleich) rot.
- **AC-5:** Given ein Trip und ein Ortsvergleich auf einem Handy (390 px) / When der Nutzer die Liste öffnet, das Karten-Menü bedient und im Hub das ⋯-Menü öffnet / Then gilt für Trip UND Ortsvergleich: die Karte hat einen Menü-Knopf, der das Aktionsblatt öffnet, ein Tipp auf die Karte öffnet den Hub, fünf Status-Pillen stehen in der Liste, und das ⋯-Blatt im Hub zeigt bei einem pausierten Eintrag genau Fortsetzen, Archivieren, Löschen (ohne Senden, Vorschau, Bearbeiten) und lässt sich schließen.
  - Test: `hub-list-menu.spec.ts` (LM-9, LM-10).
  - Mutation: im geteilten `subscriptionActions` die Hub-Liste um „Senden" erweitern → LM-10 beider kinds rot; `SubscriptionCard`-Menü-Testid ändern → LM-9 beider rot.
- **AC-6:** Given ein Trip und ein Ortsvergleich im Hub / When der Nutzer eine echte Änderung auslöst (Ort entfernen bzw. Etappen-Datum ändern), Region oder Profil im Kopf speichert, ein Zahlenfeld nur anklickt und verlässt oder der Server mit 500 antwortet / Then gilt für Trip UND Ortsvergleich dieselbe Chip-Zusicherung: der geteilte Speicher-Chip steht beim Öffnen auf „Gespeichert" und ist genau einmal vorhanden, geht bei einer echten Änderung auf „Speichere…" und danach auf „Gespeichert HH:MM" und die Änderung überlebt das Neuladen, bleibt ohne Änderung samt Zeitstempel unverändert ohne einen einzigen Speicher-Aufruf, und zeigt bei einem Server-Fehler „Fehler beim Speichern" mit sichtbarem Zurücksetzen. Nur der Auslöser unterscheidet sich je Art.
  - Test: `hub-save-chip.spec.ts` (SC-1..SC-6); die beiden AC-11-Chip-Fälle sind aus `trip-hub-kopf-region-aktivitaet.spec.ts` hierher gewandert.
  - Mutation: Text „Gespeichert" in `SaveIndicator.svelte` ändern → SC-1/2/5/6 beider kinds rot; im Vergleichs-Hub `hub-orte-remove` nicht mehr speichern → nur SC-2/SC-4 (vergleich) rot; im Trip den Blur-Speichervorgang der Etappen-Daten abschalten → nur SC-2/SC-4 (route) rot; im Wertebereiche-Editor beim reinen Blur trotzdem speichern → SC-3 des betroffenen kind rot.
- **AC-7:** Given ein Trip und ein Ortsvergleich ohne zustellbares Ziel auf Staging / When der Nutzer in der Liste „Senden" wählt, den Dialog mehrfach öffnet und schließt und den gesperrten Senden-Knopf mehrfach erzwungen anklickt / Then nennt der Dialog für beide Arten das tatsächliche Ziel (nie „0 Empfänger"), der Lösch-Dialog behält seinen eigenen Text, der Senden-Knopf ist gesperrt und es geht kein Sende-Aufruf hinaus, der Dialog bleibt stabil — verifiziert mit eigener Staging-Config gegen Eigen-Seed statt gegen den ersten Eintrag im Staging-Bestand, ohne `waitForTimeout`.
  - Test: `hub-send-dialog-target.staging.spec.ts` (SD-1, SD-2), manuell gegen Staging (`playwright.hub-send-dialog-target.staging.config.ts`); bleibt außerhalb der Ratsche.
  - Mutation: das Sperren des Senden-Knopfs bei fehlendem Ziel im geteilten `SendConfirmDialog` entfernen → SD-1/SD-2 beider kinds rot.
- **AC-8:** Given der Paritäts-Wächter / When der Unit-Test läuft / Then enthält `ALTLAST` nur noch **41** Einträge (die sieben Dateien `bug-626-compare-menu-actions`, `compare-hub-kopf-einmal`, `compare-hub-name-region-profil`, `compare-hub-save-chip`, `compare-mobile-vervollstaendigung`, `compare-send-dialog-target.staging`, `compare-tab-bar` sind entfernt), `ALTLAST_MAX` ist **41**, keine Spec der S2-Gruppe steht mehr als Compare-only-Datei im Baum, und die Selbsttests der Wächter-Mutationen bleiben grün.
  - Test: `tests/unit/test_e2e_compare_paritaet_waechter.py` (benannte Datei).
  - Mutation: einen der sieben Namen in `ALTLAST` stehen lassen → rot („Eintrag entfernen", Datei existiert nicht mehr); `ALTLAST_MAX` auf 48 lassen → der Test mit dem Literal 41 schlägt an; eine neue `compare-neu.spec.ts` ohne Kopf anlegen → rot.
- **AC-9:** Given die CI-Ampel / When die Ratsche geprüft wird / Then enthält `.github/ci_e2e_specs.txt` `hub-tab-bar`, `hub-kopf-bearbeiten`, `hub-kopf-aufbau`, `hub-list-menu` und `hub-save-chip` und nicht mehr `issue-724-trip-name-save-error`, `E2E_MIN_SPECS` entspricht exakt der Listenlänge (erwartet 68), und `E2E_MIN_EXECUTED_HAUPT` ist der am Endstand per `npx playwright test --list` gemessene Wert (Richtung: steigt gegenüber 369) mit fortgeschriebener Begründung im Kommentar; die Existenzprüfung jeder Listenzeile ist grün.
  - Test: `tests/unit/test_e2e_positivliste_ratschen_bindung.py` sowie der CI-Job `e2e` (exakte Ausführungszahl über `e2e_gate.py`).
  - Mutation: Listenzeile auf einen nicht existierenden Dateinamen ändern → Existenzprüfung rot; `E2E_MIN_SPECS` um 1 verfälschen → Kern-Test rot; `E2E_MIN_EXECUTED_HAUPT` um 1 verändern → `e2e_gate.py` rot.
- **AC-10:** Given die Zuordnungstabelle dieser Spec / When jeder Testfall der sieben Alt-Compare-Dateien (43 Quelltext-Fälle) und der aufgelösten Trip-Dateien (`mobile-tab-bar` 6, `issue-724` 3, `trips-list-aktionen` 3, AC-11 aus `trip-hub-kopf-region-aktivitaet` 2) einer Zeile zugeordnet und gegen die neuen Specs abgeglichen wird / Then gibt es für jeden Altfall genau ein benanntes Ziel in einer neuen Spec (oder die ausdrückliche Feststellung „bleibt/Deckung in …" mit Verweis), und eine Fallzahl-Prüfung am Endstand bestätigt es: ausgeführte Fälle der Zielspecs je kind ≥ zugeordnete Altfälle, und jede gelöschte Datei ist in der Tabelle vollständig aufgeführt. Verlieren darf keine Zusicherung — nur der Altfall AC-24 (Lock-Toast) wird vorher auf Deckung in `issue-682` AC-2/AC-4a geprüft.
  - Test: Prüfung in `/60` und im Adversary-Dialog: `grep -c "^\s*test(" ` je Alt-Datei gegen die Tabelle (Zeilen 1-43 = Compare-Altfälle, 44-57 = aufgelöste Trip-Fälle, 58-74 = „bleibt"-Zeilen) und `npx playwright test --list` je Zieldatei gegen die Fallzahlen der Legende (HT 19, KB 20, KA 16, LM 20, SC 12, SD 4).
  - Mutation: beim Zusammenführen einen Fall (z. B. HT-3 „letzter Reiter per Wisch") weglassen → die Fallzahl-Prüfung (je kind erwartet 10 bzw. 9 HT-Fälle) meldet die Differenz; eine Alt-Zusicherung bewusst verfälschen (Reiteranzahl 5 → 6) → die Spec wird rot.
- **AC-11:** Given die neuen Ratschen-Specs / When sie im Zielverbund (Hauptlauf der Positivliste ohne `bug-703`) dreimal hintereinander laufen / Then sind alle drei Läufe grün (jeweils mit frischem Stack und frischer `admin.json`), und die neuen Specs enthalten **kein** `waitForTimeout` und **kein** `skip` (Filter A; Wartebedingungen über `waitForResponse`/`expect.poll`/Attribute), keinen `page.screenshot({path})`, keinen Hauptrepo-Pfad und kein `__dirname` (Filter C); `hub-send-dialog-target.staging.spec.ts` ist ebenfalls frei von `waitForTimeout`.
  - Test: Filter B (3 Zyklen) + `grep -c "waitForTimeout\|\.skip(\|test\.fixme\|__dirname" frontend/e2e/hub-*.spec.ts` = 0 (für die Staging-Spec nur `waitForTimeout`).
  - Mutation: `waitForTimeout` in eine der Dateien einfügen → Filter-A-Prüfung rot.
- **AC-12:** Given ein zusammengeführtes Verhalten aus AC-1 bis AC-6 / When die Implementierung gezielt verfälscht wird (Mutations-Gegenprobe, Sicherungskopie, nur String-Ersetzung — nie `git checkout/stash/reset`) / Then wird für **jedes** zusammengeführte Verhalten und für **beide** kinds der jeweils betroffene Test rot, und es wird protokolliert, **welcher** Test rot wurde; eine Verfälschung, die kein Test fängt, ist ein Finding. Zusätzlich zeigt die Gegenprobe, dass ein Fall nur dort rot wird, wo die Zusicherung wirkt (kind-spezifische Verfälschung ⇒ nur dieser kind-Fall rot).
  - Test: Adversary-Dialog in `/50` (Familien: Selektor/Testid, Zähler, Wartebedingung, Reihenfolge, PUT-Rumpf).
  - Mutation: siehe die Mutationszeilen in AC-1 bis AC-7 (je kind getrennt).
- **AC-13:** Given ein Fall der neuen Specs wird für den Trip rot, obwohl er für den Ortsvergleich grün ist (oder umgekehrt) / When die Ursache untersucht wird / Then wird die Produktlücke im **selben Ticket** (#2347) behoben und der Test bleibt unverändert streng; ein Abschwächen, ein `test.skip`, ein kind-Zweig, der den Fall nur für eine Art prüft, oder ein „bekannte Abweichung"-Vermerk ist unzulässig. Die berührten Produktdateien werden in diesem Fall in die Spec nachgetragen (`updated`/Changelog) und das LoC-Limit bei Bedarf per `loc_limit_override` angehoben.
  - Test: Prozess-AC; Beleg im Adversary-Protokoll (Liste „rot beim Zusammenführen: ja/nein, wenn ja: Fix-Commit").
  - Mutation: keine (Regel). Prüfpunkt im Adversary: jeder `if (kind === …)`-Zweig in den neuen Specs ist durch einen Kommentar mit Begründung gedeckt und steht in der Zuordnung als compare-eigen.
- **AC-14:** Given die umbenannten und gelöschten Dateien / When `grep -rn` auf deren Namen über `frontend`, `.github`, `tests` läuft / Then gibt es keinen Treffer auf eine nicht mehr vorhandene Datei (Configs, Setups, Kommentar-Verweise sind mitgezogen oder gelöscht), `playwright.758.staging.config.ts` und `playwright.880.staging.config.ts` zeigen weiter auf vorhandene Dateien, und der Staging-Lauf mit der umbenannten Config ist startfähig (`npx playwright test --list --config=playwright.hub-send-dialog-target.staging.config.ts` listet die vier Fälle).
  - Test: `grep`-Prüfung in `/60`, `--list` gegen die Staging-Config.
  - Mutation: einen Verweis auf eine gelöschte Datei stehen lassen → `grep` findet ihn.

## Zuordnung alt → neu (Regressionsnetz)

Legende: **HT/KB/KA/LM/SC/SD** siehe „Neue Specs und ihre Fälle". „je kind" = Fall läuft für `route` und `vergleich`. Zeilen mit „bleibt" ändern die Datei nicht.

| # | Alt (Datei · Fall) | Neu (Spec · Fall) | Anmerkung |
|---|---|---|---|
| 1 | `compare-tab-bar` · Mobile: Deep-Link `?tab=alarme` positioniert aktiven Tab sichtbar (`:82`) | `hub-tab-bar` · HT-1 je kind | |
| 2 | `compare-tab-bar` · Mobile: Alt-Link `?tab=versand` landet aktiv und sichtbar auf Wetter-Metriken (`:89`) | HT-2 je kind | Trip-Pendant lag nur in `hub-reiter-alt-kennungen-umleitung` (nicht Ratsche) |
| 3 | `compare-tab-bar` · Mobile: A11y — tablist/tab, aria-selected, roving tabindex, Pfeiltasten (`:96`) | HT-4 je kind | 5 Reiter |
| 4 | `compare-tab-bar` · Mobile: Trigger ≥ 44 px, Orte-Badge mit korrekter Zahl (`:114`) | HT-5 + HT-6 je kind | Fall wird geteilt, Zusicherungen bleiben beide |
| 5 | `compare-tab-bar` · Desktop: Leiste ohne Band-Scroll, neutraler Badge, Optik unverändert (`:134`) | HT-7 + HT-8 je kind | Badge-Farbe/13 px nur vergleich, Optik transparent nur route |
| 6 | `compare-hub-name-region-profil` · AC-1 Name ändern → sichtbar + Reload persistent (`:88`) | `hub-kopf-bearbeiten` · KB-1 je kind | |
| 7 | `compare-hub-name-region-profil` · AC-2 Region ändern → `display_config.region` persistent (`:118`) | KB-2 je kind | Feldpfad je kind |
| 8 | `compare-hub-name-region-profil` · AC-3 Aktivitätsprofil-Kachel → markiert + persistent (`:150`) | KB-3 je kind | Trip `activity`, Vergleich `profil` |
| 9 | `compare-hub-name-region-profil` · AC-4 nur Name ändern → übrige Felder unverändert (`:174`) | KB-4 je kind | mit kopf-einmal AC-3 zusammengelegt |
| 10 | `compare-hub-name-region-profil` · AC-5 Name ändern, dann Wertebereiche-Commit → Name bleibt (`:206`) | KB-5 je kind | `waitForTimeout(2_000)` (`:240`) → `expect.poll` |
| 11 | `compare-hub-name-region-profil` · AC-6 Mobile-Viewport — Name inline editierbar (`:250`) | KB-6 je kind | |
| 12 | `compare-hub-name-region-profil` · AC-7 PUT 500 → Fehlermeldung + Eingabe bleibt (`:284`) | KB-7 je kind | |
| 13 | `compare-hub-kopf-einmal` · AC-8 (Desktop) jede Kopf-Testid genau einmal (`:116`) | `hub-kopf-aufbau` · KA-1 je kind | |
| 14 | `compare-hub-kopf-einmal` · AC-8 (Mobil 375) (`:160`) | KA-2 je kind | |
| 15 | `compare-hub-kopf-einmal` · AC-2 (Mobil 375) Name, Region, Profil → Reload (`:205`) | KB-6 je kind | mit Zeile 11 zusammengelegt |
| 16 | `compare-hub-kopf-einmal` · AC-3 (Desktop) PUT trägt nur das geänderte Feld (`:252`) | KB-4 je kind | mit Zeile 9 zusammengelegt |
| 17 | `compare-hub-kopf-einmal` · AC-5 (Desktop) Profil-PUT scheitert (`:304`) | KB-8 je kind | |
| 18 | `compare-hub-kopf-einmal` · AC-9 (Mobil 375) Eyebrow, Unterzeile „Wandern · 2 Orte" (`:336`) | KA-6 nur vergleich | compare-eigen; Trip-Gegenstück bleibt `trip-hub-kopf` AC-2 |
| 19 | `compare-hub-kopf-einmal` · AC-9 (Desktop 1280) Breadcrumb „ORTS-VERGLEICHE / Hub" (`:349`) | KA-7 nur vergleich | compare-eigen |
| 20 | `compare-hub-kopf-einmal` · AC-10 (Desktop/Mobil) Region ≤ 60, Unterzeile weg (`:369`, 2 ausgeführte Fälle) | KA-3 je kind, je Viewport | |
| 21 | `compare-hub-kopf-einmal` · Bedienung (Desktop): Vorbelegung, Kacheln gesperrt, Fallback, Abbrechen verwirft Fehler (`:397`) | KA-4 je kind (+ KB-10 für „Abbrechen verwirft") | |
| 22 | `compare-hub-kopf-einmal` · F007 Orte-Anzahl Desktop zählt IDs, Mobil aufgelöste Orte (`:466`) | KA-8 nur vergleich | compare-eigen |
| 23 | `compare-hub-kopf-einmal` · F007 Singular „· 1 Ort" (`:492`) | KA-9 nur vergleich | compare-eigen |
| 24 | `bug-626-compare-menu-actions` · AC-1 „Bearbeiten" navigiert (`:131`) | `hub-list-menu` · LM-1 je kind | Ziel Hub; `.first()`-Kachel → Eigen-Seed |
| 25 | `bug-626-compare-menu-actions` · AC-4 (#1743) keine Aktion „Vorschau" (`:158`) | LM-2 je kind | |
| 26 | `bug-626-compare-menu-actions` · AC-2 „Pausieren" wechselt zu pausiert (`:174`) | LM-3 je kind | `waitForTimeout` `:197,207,216` ersetzt |
| 27 | `bug-626-compare-menu-actions` · AC-3 „Fortsetzen" wechselt zu aktiv (`:226`) | LM-4 je kind | `waitForTimeout` `:246,254,262` ersetzt |
| 28 | `bug-626-compare-menu-actions` · AC-5 „Setup fortsetzen" navigiert Draft (`:279`) | LM-5 je kind | `waitForTimeout` `:296` ersetzt; Trip-Entwurf = Etappen ohne Datum |
| 29 | `bug-626-compare-menu-actions` · AC-6 Menü enthält „Senden" (`:317`) | LM-6 je kind | `waitForTimeout` `:323` ersetzt |
| 30 | `bug-626-compare-menu-actions` · AC-7 Listen-Kebab zeigt Aktionen ohne Archivieren (`:339`, Titel „5", Prüfung 6) | LM-7 je kind | `waitForTimeout` `:347` ersetzt; Titel korrigiert; Sollliste fest |
| 31 | `compare-hub-save-chip` · AC-1 Hub öffnen → Chip idle (`:81`) | `hub-save-chip` · SC-1 je kind | |
| 32 | `compare-hub-save-chip` · AC-2 Ort entfernen → saving→idle + Zeitstempel (`:100`) | SC-2 je kind | Auslöser Orte bzw. Etappen |
| 33 | `compare-hub-save-chip` · AC-3 Zahlenfeld ohne Änderung → kein PUT (`:136`) | SC-3 je kind | `waitForTimeout(2_000)` (`:173`) → `expect.poll` |
| 34 | `compare-hub-save-chip` · AC-4 PUT 500 → „Fehler beim Speichern", Rollback (`:191`) | SC-4 je kind | |
| 35 | `compare-mobile-vervollstaendigung` · mobile Karte hat Menü-Knopf, Tipp navigiert, Aktionsblatt (`:100`) | LM-9 je kind | |
| 36 | `compare-mobile-vervollstaendigung` · AC-22 Übersicht 4 Stat-Karten 2×2, kein „Briefings" (`:129`) | HT-10 nur vergleich | compare-eigen (Cockpit-Übersicht im Trip) |
| 37 | `compare-mobile-vervollstaendigung` · AC-22 Tab-Leiste per echtem Klick (`:157`) | HT-9 je kind | |
| 38 | `compare-mobile-vervollstaendigung` · AC-22 Fix-Loop 1 letzter Tab per Wisch + Klick (`:190`) | HT-3 je kind | |
| 39 | `compare-mobile-vervollstaendigung` · AC-23 ⋯ öffnet Bottom-Sheet Fortsetzen/Archivieren/Löschen (`:225`) | LM-10 je kind | |
| 40 | `compare-mobile-vervollstaendigung` · AC-24 Lock-Toast + floating CTA im `/compare/new` (`:275`) | Deckung in `issue-682` AC-2 (`:100`) + AC-4a (`:168`); S3b hebt auf beide kinds mit `issue-661` | wird im RED gelesen; fehlt eine Zusicherung, ergänzt in `issue-682`, bevor Alt-Datei fällt |
| 41 | `compare-mobile-vervollstaendigung` · #2283 AC-13 Senden nur im Hub-Kopf (mobil) (`:321`) | KA-5 je kind | |
| 42 | `compare-send-dialog-target.staging` · Liste rendert, Löschdialog, Sende-Dialog Ziel + Sperre (`:9`) | `hub-send-dialog-target.staging` · SD-1 je kind | `waitForTimeout(1500)` (`:60`) ersetzt |
| 43 | `compare-send-dialog-target.staging` · Runde 2 Doppelklick/mehrfach öffnen (`:77`) | SD-2 je kind | `waitForTimeout(1500)` (`:114`) ersetzt; Eigen-Seed statt `.first()` |
| 44 | `mobile-tab-bar` · Deep-Link `?tab=alarme` (`:39`) | HT-1 je kind | |
| 45 | `mobile-tab-bar` · Tab-Wechsel auf letzten Tab positioniert ihn sichtbar (`:44`) | HT-3 je kind | |
| 46 | `mobile-tab-bar` · A11y (`:55`, erwartet 7 Reiter) | HT-4 je kind | auf **5** korrigiert (Befund 2) |
| 47 | `mobile-tab-bar` · Trigger ≥ 44 px (`:77`, erwartet 7) | HT-5 je kind | auf 5 korrigiert |
| 48 | `mobile-tab-bar` · Badges sichtbar (Etappen-Zähler) (`:89`) | HT-6 je kind | |
| 49 | `mobile-tab-bar` · Desktop: Leiste unverändert, alle Tabs ohne Band-Scroll (`:100`, erwartet 7) | HT-7 + HT-8 je kind | auf 5 korrigiert |
| 50 | `issue-724-trip-name-save-error` · AC-1 PUT scheitert → Feld offen + Fehlermeldung (`:41`) | KB-7 je kind | Ratschen-Zeile 379 entfällt |
| 51 | `issue-724-trip-name-save-error` · AC-2 PUT 2xx → Feld geschlossen, keine Fehlermeldung (`:71`) | KB-9 je kind | |
| 52 | `issue-724-trip-name-save-error` · AC-3 Fehlermeldung bei Abbrechen + Neu-Öffnen zurückgesetzt (`:101`) | KB-10 je kind | |
| 53 | `trips-list-aktionen` · erster Menüpunkt „Pausieren"; Wahl pausiert; danach „Fortsetzen" (`:48`) | LM-3 + LM-4 je kind | PATCH-Rumpf `{paused:true}` im Trip-Fall mitgeprüft |
| 54 | `trips-list-aktionen` · Reihenfolge und Beschriftung Trip-Menü == Ortsvergleich-Menü (`:71`) | LM-7 je kind | strenger: feste Sollliste je Art |
| 55 | `trips-list-aktionen` · AC-11 archivierter Trip erscheint nicht in der Liste (`:88`) | LM-8 je kind | Archiv-Auslöser Vergleich im RED ermitteln; weicht der Vergleich ab ⇒ AC-13 |
| 56 | `trip-hub-kopf-region-aktivitaet` · AC-11 (Trip) Region speichern → Chip saving ⇒ idle (`:974`) | SC-5 route (+ vergleich) | Fall wird aus der Ratschen-Datei entfernt |
| 57 | `trip-hub-kopf-region-aktivitaet` · AC-11 (Vergleich) Profil-Kachel → Chip (`:1000`) | SC-6 vergleich (+ route) | dito |
| 58 | `issue-758-save-indicator` · AC-1 Auto-Save bei Etappen-Änderung (`:88`) | bleibt; Auslöser auch in SC-2 route | Staging-Setup `issue-758.staging.setup.ts` |
| 59 | `issue-758-save-indicator` · AC-2 Ruhezustand „Gespeichert" (`:108`) | bleibt; ≙ SC-1 | |
| 60 | `issue-758-save-indicator` · AC-4 Save-Fehler (`:116`) | bleibt; ≙ SC-4 route | |
| 61 | `issue-758-save-indicator` · AC-5 ausstehender Auto-Save flusht vor Navigation (`:137`) | bleibt (Trip-eigener Auslöser) | |
| 62 | `issue-758-save-indicator` · AC-7 Briefing-Tab ohne Speichern-Button (`:173`) | bleibt | |
| 63 | `issue-758-save-indicator` · AC-3 Compare-Änderung speichert automatisch (`:213`) | bleibt; ≙ SC-2 vergleich | |
| 64 | `issue-758-save-indicator` · AC-6 Compare-Indikator unabhängig vom Trip-Editor (`:241`) | bleibt | |
| 65 | `feat-880-autosave-overlay` · AC-1 Overlay fixed, kein zweiter Indikator (`:86`) | bleibt; ≙ trip-hub-kopf AC-10 | |
| 66 | `feat-880-autosave-overlay` · AC-2 Uhrzeit HH:MM (`:95`) | bleibt; ≙ SC-2 | |
| 67 | `feat-880-autosave-overlay` · AC-3 idle dimmt nach 3 s (`:107`, `waitForTimeout` `:115`) | bleibt | Staging-Spec, nicht Ratsche ⇒ Filter A greift nicht |
| 68 | `feat-880-autosave-overlay` · AC-4 Fehler bleibt bei Deckkraft 1 (`:123`, `waitForTimeout` `:136`) | bleibt | dito |
| 69 | `feat-880-autosave-overlay` · AC-5 Mobile: Overlay über der BottomNav (`:143`) | bleibt | |
| 70 | `feat-880-autosave-overlay` · AC-7 Compare-Editor hat genau ein save-indicator (`:203`) | bleibt; ≙ SC-1 vergleich | |
| 71 | `feat-880-autosave-overlay` · AC-6 Trip- und Compare-Indikator unabhängig (`:214`) | bleibt | |
| 72 | `trip-hub-kopf-region-aktivitaet` · alle übrigen Fälle (AC-1..10, 12, 13, 18) | bleibt | Dopplung zu KB/KA wird nicht bereinigt (Abgrenzung) |
| 73 | `issue-268-trips-mobile-card-stack` · 7 Fälle (Trip-Liste mobil) | bleibt | Karten-Stapel Trip-eigen; LM-9 deckt die geteilte Karte ab; 6 `test.skip` ⇒ Sammelposten #1199 |
| 74 | `trips-list-send` · 3 Fälle (Berichtsart Morgen/Abend, 409) | bleibt | Trip-eigene Berichtsart; SD deckt den geteilten Dialog ab |

Es entfällt in S2 keine Zusicherung ersatzlos. Compare-eigen bleiben ausdrücklich: Eyebrow „Orts-Vergleich · Hub", Breadcrumb, Orte-Anzahl samt Singular (Zeilen 18, 19, 22, 23), die 4-Stat-Übersicht (Zeile 36) und die Optik-Werte des Orte-Reiters (Teil von Zeile 5); Trip-eigen: Optik-Wert des aktiven Etappen-Reiters.

## Berührte Dateien

| Datei | Änderung |
|---|---|
| `frontend/e2e/helpers.ts` | MODIFY — `HUB_SEL` |
| `frontend/e2e/hub-tab-bar.spec.ts`, `hub-kopf-bearbeiten.spec.ts`, `hub-kopf-aufbau.spec.ts`, `hub-list-menu.spec.ts`, `hub-save-chip.spec.ts` | CREATE |
| `frontend/e2e/hub-send-dialog-target.staging.spec.ts`, `hub-send-dialog-target.staging.setup.ts`, `frontend/playwright.hub-send-dialog-target.staging.config.ts` | CREATE (Umbenennung) |
| `frontend/e2e/compare-tab-bar.spec.ts`, `compare-hub-name-region-profil.spec.ts`, `compare-hub-kopf-einmal.spec.ts`, `bug-626-compare-menu-actions.spec.ts`, `compare-hub-save-chip.spec.ts`, `compare-mobile-vervollstaendigung.spec.ts`, `compare-send-dialog-target.staging.spec.ts` | DELETE |
| `frontend/e2e/mobile-tab-bar.spec.ts`, `issue-724-trip-name-save-error.spec.ts`, `trips-list-aktionen.spec.ts` | DELETE |
| `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts` | MODIFY — AC-11 (Trip, Vergleich) entfernen, Kommentar `:202` |
| `frontend/e2e/playwright.1273-s1.red.config.ts`, `playwright.1273-s2.red.config.ts`, `playwright.2284-s1.red.config.ts`; `frontend/playwright.1256-s8.staging.config.ts`; Setups `compare-hub-save-chip`, `compare-hub-name-region-profil`, `compare-hub-kopf-einmal`, `feat-1256-s8` (`.staging.setup.ts`); `compare-send-dialog-target.staging.setup.ts`, `frontend/playwright.compare-send-dialog-target.staging.config.ts` | DELETE (letztere zwei durch Umbenennung ersetzt) |
| Kommentar-Verweise: `issue-953.staging.setup.ts`, `metrik-grundauswahl-schneidet-kanal.staging.setup.ts`, `compare-edit-redirect.staging.setup.ts`, `compare-edit-redirect.spec.ts`, `compare-hub-fidelity-s8c.spec.ts`, `compare-editor-fidelity-s8d.spec.ts`, `hub-reiter-alt-kennungen-umleitung.spec.ts`, 3 × `subscription_header_*.test.ts`, `trip_list_pause.test.ts` | MODIFY (nur Text) |
| `frontend/e2e/issue-682-compare-editor-mobile.spec.ts` | MODIFY nur falls Deckungslücke zu Zeile 40 (siehe Befund 8) |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY — 7 Einträge raus, `ALTLAST_MAX` 41, Docstring |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` | MODIFY — Liste, `E2E_MIN_SPECS` 68, `E2E_MIN_EXECUTED_HAUPT` (gemessen) |
| `docs/reference/gates_und_ratschen.md` | MODIFY — ALTLAST-Stand 41 |

## Testplan

1. **RED (Messung des Altbestands):** Die 7 Compare-Altdateien und die vier Trip-Pendants (`mobile-tab-bar`, `trips-list-aktionen`, `issue-758`, `feat-880`) einmal gegen den CI-Stack (`frontend/e2e/ci-stack.sh`, frische `admin.json`) fahren und das Ergebnis je Fall in `docs/artifacts/feat-2347-s2-s4-paritaets-e2e/` festhalten (vorbestehend rot/grün). Rote Altfälle sind Befunde (Spec-Änderungslog), kein Grund zur Abschwächung.
2. **RED (neue Specs):** Die sechs neuen Specs schreiben und gegen den Stand **vor** einer Produktänderung laufen lassen; erwartet: alles grün, außer wo AC-13 greift (dann Produktfix).
3. **Mutationen** aus AC-1 bis AC-7 per String-Ersetzung mit externer Sicherungskopie, je kind getrennt; Protokoll „Verfälschung → welcher Test wurde rot".
4. `npx playwright test --list` über die Hauptlauf-Auswahl ⇒ `E2E_MIN_EXECUTED_HAUPT`; `grep -c '^e2e/' .github/ci_e2e_specs.txt` ⇒ `E2E_MIN_SPECS` (erwartet 68).
5. `uv run pytest tests/unit/test_e2e_compare_paritaet_waechter.py tests/unit/test_e2e_positivliste_ratschen_bindung.py` (benannte Dateien).
6. **Filter B:** 3 Zyklen im Zielverbund (Positivliste ohne `bug-703`, frischer Stack, frische `admin.json`), nicht Staging. **Filter A/C:** `grep` auf `waitForTimeout`, `.skip(`, `test.fixme`, `__dirname`, `screenshot({ path`.
7. **Staging:** `hub-send-dialog-target.staging` einmal mit eigener Config gegen Staging (nginx-Basic-Auth, Validator-Creds laut `reference_staging_*`).
8. `grep -rn` auf alle gelöschten/umbenannten Namen über `frontend .github tests` (AC-14).

## Risiken

- **Trip-Fälle rot:** Befund 2 zeigt, dass der Trip-Altbestand veraltet sein kann; Fälle ohne Trip-Pendant (Chip-Fehlerzustand bei Etappen-500, Entwurfs-Menü, Archiv-Auslöser des Vergleichs, Kopf-Senden-Abruf `kind=…` im Trip) können eine Produktlücke sichtbar machen. Regel AC-13: im selben Ticket fixen, nie abschwächen. Zeitaufwand und Produktdateien dann in der Spec nachtragen.
- **CI-Laufzeit/Quota:** +~87 Fälle bei `workers: 1`; Vergleiche je Nutzer auf 2 aktive begrenzt (Befund 11) — jeder Fall räumt im `finally`; der Login-Zähler steigt nicht (alle Fälle nutzen den `storageState`, `bug-626`-UI-Login entfällt).
- **Alt-Specs ungemessen:** siehe Befund 1; Schritt 1 des Testplans ist Pflicht, sonst ist „Zusicherungsverlust" nicht belegbar.
- **Datenabhängigkeit auf Staging:** SD-1/SD-2 ohne Eigen-Seed würden an fremdem Bestand hängen; Eigen-Seed ist Teil der Spec.
- **Parallele Sitzungen:** `.github/ci_e2e_specs.txt` und `ci.yml` nicht parallel mit anderer Sitzung/#2243 bearbeiten (Merge-Konflikt); vor Commit `git log HEAD..origin/main -- .github/ci_e2e_specs.txt`.
- **Zusicherungsverlust:** Zuordnung (74 Zeilen), Fallzahl-Prüfung (AC-10), Mutations-Gegenprobe (AC-12).
- **Rollback:** reine Testschicht — Revert des PR stellt Alt-Dateien, Configs, Ratsche und Wächter-Stand her; Produktverhalten unberührt (außer bei AC-13-Fixes, die als eigene Commits im PR stehen und einzeln revertierbar sind).

## Out of Scope (bleibt in #2347, folgt in S3a, S3b, S4)

Alle weiteren ALTLAST-Dateien (41 nach S2): Alarme/Wertebereiche/Wetter-Metriken/Wertprops (S3a); Versand-Trio, Konflikt-412, Radar, Stundenverlauf, `compare-editor-autosave`, `issue-682`↔`issue-661`, `.staging`-Specs (S3b); Gruppe ohne Trip-Pendant, #2243-Leichen, Leeren der Altlast, Ratsche final (S4). Bereinigung der Trip-Dopplungen und der `test.skip` in `issue-268`. Produktcode (außer AC-13).

## Known Limitations

- Der Wächter erkennt „kind-Schleife" nur an Textmustern (`HUB_KINDS`); er beweist nicht, dass die Schleife fachlich beide kinds prüft. Das bleibt Adversary-/Review-Punkt („hätte das ein geteilter Baustein sein müssen?") und wird durch AC-12/AC-13 abgedeckt.
- `hub-send-dialog-target.staging` ist nicht in der CI-Ratsche und braucht Staging mit Validator-Creds; sie ist ein manueller Staging-Nachweis.
- Die Kopf-Zusicherungen in `trip-hub-kopf-region-aktivitaet.spec.ts` und `hub-kopf-bearbeiten` überschneiden sich bewusst (Abgrenzung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Testschicht-Umbau und Ratsche, keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma) betroffen; setzt die bestehende Teilungs-Invariante (Trip/Ortsvergleich, CLAUDE.md) in der E2E-Schicht für Kopf, Reiter, Liste und Chip durch.

## Changelog

- 2026-10-26: Erstfassung S2 (Entwurf).
