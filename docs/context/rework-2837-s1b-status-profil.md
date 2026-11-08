# Context: rework-2837-s1b-status-profil

## Request Summary
Nachbesserung von #2837 S1 (Hub-Kopf ein Baustein, PR #2839 gemergt). Die Staging-Abnahme am 2026-11-07 (AC-15, Fresh-Eyes-Paar im selben Zustand) fand zwei Unterschiede außerhalb der Whitelist:
1. **Status-Schild:** Trip nutzt `TripStatusBadge` („PAUSIERT“, Großbuchstaben, gelb umrandet), Vergleich nutzt `CompareStatusPill` („pausiert“, Kleinbuchstaben, grau umrandet; aktiv: orange gefüllt). Zwei Bausteine für dasselbe Element.
2. **Profil in der Zeile unter dem Titel (AC-9):** Vergleich „— ✎ · Wandern · 2 Orte“, Trip nur „— ✎“.

Ziel: ein gemeinsames Status-Schild, Profil-Angabe bei beiden gleich, danach neue Staging-Abnahme (AC-15).

## Ursachen (belegt)
- **Profil:** `SubscriptionHeader.svelte:139` rendert `· {profileLabel}` nur, wenn `profileLabel` gesetzt ist. Der Vergleich übergibt es (`routes/compare/[id]/+page.svelte:174,381`, aus `presetProfileLabel(currentPreset.profil)`), `TripHeader.svelte:136-158` übergibt an `HubKopf` nur `profile={trip.activity}` und `profileOptions={aktivitaeten}`, **kein `profileLabel`**. `HubKopf.svelte:42,61,99` reicht es nur durch. Fix: TripHeader leitet das Label aus `aktivitaeten.find(o => o.value === trip.activity)?.label` ab und übergibt es.
- **Status:** Zwei Komponenten.
  - `trip-detail/TripStatusBadge.svelte` (41 Z.): `ui/pill/Pill` mit `tone` (draft/finished/archived=default, planned=info, active=accent, paused=warning), `data-outlined`, Testid `trip-detail-status-badge`, Labels `trip.status.*` (6 Zustände via `deriveTripStatus`).
  - `compare/CompareStatusPill.svelte` (64 Z.): eigenes Inline-Styling (Mono 11 px, Pill-Radius), active gefüllt `--g-accent`, sonst Outline `--g-ink-3`, `data-variant`/`data-status`, Labels aus `STATUS_MAP` (`listen.status.*`, 3 Zustände `active|paused|draft`).
  - Einbindung: Trip im `status`-Snippet von `HubKopf` (`TripHeader.svelte:165-168`), Vergleich im Snippet `statusBadge` (`routes/compare/[id]/+page.svelte:357-362`), dort auch `runtime-exceeded-hint`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | `profileLabel` fehlt; Status-Snippet |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | Trip-Status-Schild (Pill + Tone) |
| `frontend/src/lib/components/compare/CompareStatusPill.svelte` | Vergleich-Status-Schild (eigenes Styling) |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | `CompareStatus`, `STATUS_MAP` (auch Listen/Kacheln nutzen `STATUS_MAP`) |
| `frontend/src/routes/compare/[id]/+page.svelte` | Einbindung `CompareStatusPill`, `profileLabel` |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | gemeinsamer Kopf, Snippet `status`, Prop `profileLabel` |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | Titelblock, Zeile Region · Profil · meta |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Design-System-Atom mit `tone`/`data-tone` |
| `frontend/src/lib/components/molecules/index.ts` | exportiert `CompareStatusPill` |
| `docs/specs/modules/rework_2837_s1_hub_kopf.md` | S1-Spec (Entscheidung 5, 8; AC-6, AC-9, AC-15) |

## Tests, die Status-Selektoren/Varianten prüfen (müssen mitgezogen, nicht gelöscht werden)
- Unit: `compare/__tests__/f10Pruefstand.ts`, `compare/__tests__/issue_491_compare_detail.test.ts`, `compare/compare_detail.test.ts`, `lib/issue_577_atoms_design_fidelity.test.ts`, `shared/hub-kopf/__tests__/hub_kopf_baustein.test.ts`, `shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts`, `trip-detail/TripStatusBadge.atomic.test.ts`, `trip-detail/__tests__/tripStatusFinishedDraft.test.ts`, `trip-detail/__tests__/f9Pruefstand.ts`, `shared/hub-uebersicht/*`.
- E2E: `issue-336-status-dedup`, `trip-detail-actions`, `compare-hub-fidelity-s8c`, `design-system-lauf-b`, `accent-ctas`, `forms-dialogs-btn-migration`, `hub-versand-inline-bearbeiten`, Paritäts-Suite `hub-kopf-paritaet-compare-trip`.

## Existing Patterns
- Geteilte Bausteine liegen unter `shared/` mit `context="route"|"vergleich"` (ADR-0097, ADR-0110). Pendant-Sperre: keine Compare-Komponente mit Trip-Pendant.
- Status-Darstellung im Design-System: `ui/pill/Pill` mit `tone` ist das Atom; `CompareStatusPill` ist ein Sonderbau mit Inline-Styles (Altlast #488).
- Texte nur über den i18n-Katalog (ADR-0104), de + en.

## Dependencies
- Upstream: `ui/pill/Pill`, `deriveTripStatus`, `STATUS_MAP`, i18n `$t`.
- Downstream: Hub-Seiten Trip und Vergleich; `CompareStatusPill` nur von `routes/compare/[id]/+page.svelte` produktiv genutzt (plus Export in `molecules/index.ts` und Tests). Listen/Cockpit nutzen `STATUS_MAP`-Punkte, nicht die Pille (Cockpit-Kachel war in der Abnahme bereits gleich).

## Existing Specs
- `docs/specs/modules/rework_2837_s1_hub_kopf.md` (S1, ADR-0110), insbesondere Entscheidung 5 („Vergleich unverändert (`CompareStatusPill` + Laufzeit)“), die jetzt korrigiert wird.
- `docs/specs/modules/issue_488_compare_tile_atoms.md` (Ursprung `CompareStatusPill`).
- `docs/specs/modules/epic_135_step2_trip_detail_actions.md` (Ursprung `TripStatusBadge`).

## Risks & Considerations
- **Optik-Entscheidung:** Welche Darstellung gewinnt. Naheliegend: das Design-System-Atom `Pill` mit einer gemeinsamen Tone-Zuordnung (aktiv=accent, pausiert=warning, Entwurf=default), da Trip-Zustände eine Obermenge sind und `Pill` das Atom ist. Kontrast WCAG-AA muss in Hell und Dunkel halten (Design-Leitprinzip).
- **Sprache:** Trip-Labels `trip.status.*`, Vergleich `listen.status.*` — gleicher Zustand muss gleichen Text in gleicher Schreibung zeigen (Fresh-Eyes sah „PAUSIERT“ vs. „pausiert“).
- **Testids stabil** (S1 Entscheidung 10): `trip-detail-status-badge` bleibt; Vergleichs-Tests auf `data-variant`/`data-status` müssen umgedreht, nicht gelöscht werden.
- **Pendant-Sperre:** Ergebnis darf nicht zwei Komponenten bleiben; die alte Compare-Pille muss produktiv 0 Importeure haben oder entfallen.
- Spec-Freeze: S1-Spec ist ggf. eingefroren → Korrektur der Entscheidung 5 über eigene Nachbesserungs-Spec mit Verweis, nicht an der gesperrten Tabelle.
- Staging-Mailweg irrelevant (reines Frontend); Deploy-Scope frontend-only.

## Analysis

### Type
Feature (Nachbesserung #2837 S1 nach gescheiterter Staging-Abnahme AC-15; frontend-only)

Hinweis Vorgehen: Die drei Explore-Läufe aus Step 2a sind durch die Kontext-Sammlung oben (`/10-context`) abgedeckt; zusätzlich eigene Messungen (Kontrast, Importeure) und Plan/Sonnet-Gegencheck (2026-11-08).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/status-schild/StatusSchild.svelte` (Name vorläufig) | CREATE | EIN Status-Schild für beide Arten: Pill-Atom, `data-outlined`, Prop `status: TripStatus` (CompareStatus `active|paused|draft` ist Teilmenge), Prop `testid`, `data-status` bleibt, Labels `trip.status.*` (de+en vollständig), TONE_MAP/LABEL_MAP |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | DELETE | ersetzt durch StatusSchild |
| `frontend/src/lib/components/compare/CompareStatusPill.svelte` | DELETE | ersetzt durch StatusSchild (Inline-Styling-Altlast #488) |
| `frontend/src/lib/components/trip-detail/index.ts`, `molecules/index.ts` | MODIFY | Exporte entfernen |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | `deriveTripStatus` selbst aufrufen, StatusSchild mit Testid `trip-detail-status-badge`; `profileLabel` aus `aktivitaeten.find(o => o.value === trip.activity)?.label` an HubKopf übergeben |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | StatusSchild statt CompareStatusPill im Snippet `statusBadge` (Laufzeit-Hinweis bleibt) |
| `frontend/src/app.css:495` | MODIFY | `[data-slot=pill][data-outlined][data-tone=warning]` Text `--g-warning` → `--g-warn-deep` (AA-Fix, siehe Kontrast) |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | prüfen | `STATUS_MAP` verliert den Pillen-Verbraucher; bleibt, falls Listen/Punkte es nutzen |
| Tests (umhängen, nicht löschen) | MODIFY | `hub_uebersicht_modell.test.ts:469`, `hub_uebersicht_trip_ssr.test.ts:62,321` (Prop `trip`→`status`), `tripStatusFinishedDraft.test.ts:26` (Source-Inspection TONE_MAP/LABEL_MAP → neue Datei), `TripStatusBadge.atomic.test.ts` (umbenennen auf StatusSchild), `hub_kopf_seiten_paritaet.test.ts:71`, `f9Pruefstand.ts`, `f10Pruefstand.ts:136,241`, `compare_detail.test.ts:67`, `issue_491_compare_detail.test.ts:54-59` (verlangen String „CompareStatusPill“ → umdrehen), `issue_577_atoms_design_fidelity.test.ts`, `hub_kopf_baustein.test.ts` |
| E2E | MODIFY | `hub-versand-inline-bearbeiten.spec.ts:133,281-284` (Trip hat jetzt auch `data-status`; Kommentar + `.first()`-Locator prüfen), Kommentare `trip-detail-actions.spec.ts:74-77`; Paritäts-Suite `hub-kopf-paritaet-compare-trip` um Status-Schild und Profil-Zeile erweitern |
| `docs/specs/modules/rework_2837_s1b_status_profil.md` | CREATE | Nachbesserungs-Spec; korrigiert S1-Entscheidung 5 („Vergleich unverändert“) per Verweis, Hinweis in S1-Spec |

### Kontrast (gemessen, WCAG AA 4.5:1 für 11-px-Text; App hat keine Dunkel-Tokens)
| Zustand / Variante | Textfarbe | auf `--g-paper` #f6f4ee | auf Karte #fff | AA |
|---|---|---|---|---|
| Trip pausiert heute (outlined warning) | #c08a1a | 2.77 | 3.05 | **FAIL** |
| pausiert neu (warn-deep) | #8a6210 | 4.98 | 5.48 | ok |
| Entwurf/Fertig/Archiviert (outlined default, ink-muted) | #5c5a52 | 6.28 | 6.91 | ok |
| Geplant (outlined info) | #2c5a8c | 6.48 | 7.12 | ok |
| Aktiv (outlined accent-deep) | #8c3e1a | 6.77 | 7.45 | ok |
| Vergleich aktiv heute (weiß auf `--g-accent` #c45a2a) | #fff | 4.34 | – | **FAIL** |
| Vergleich pausiert/Entwurf heute (ink-3) | #6b675c | 5.13 | 5.65 | ok |

Folgerung: Weder die heutige Trip- noch die Vergleichs-Optik ist überall AA-fest. Gewählt: Pill-Atom umrandet (Trip-Bauart) mit warn-deep für Pausiert. Fix global in `app.css` (einzige produktive `data-outlined`-Nutzung ist das Status-Schild, sonst nur Demo `routes/_design`), damit das Design-System-Atom selbst AA-fest ist; im Commit als Token-Regel-Änderung benennen.

### Scope Assessment
- Files: ~6 Produktiv (1 neu, 2 gelöscht, 3–4 geändert) + ~12 Unit-Tests + 2–3 E2E + 1 Spec
- Estimated LoC: ~+200/-130 (Produktiv ~+50/-110, Rest Tests)
- Risk Level: LOW–MEDIUM (isolierter Kopf-Bereich; Risiko liegt in der Breite der Test-Umhängung und sichtbarer Optik-Änderung beim Vergleich)

### Technical Approach
1. Spec mit Entscheidungen: (a) EIN StatusSchild unter `shared/`, Pendant-Sperre erfüllt (beide Alt-Bausteine entfallen, 0 Importeure); (b) Optik = Pill umrandet; Vergleich-Aktiv wird umrandet statt gefüllt, Vergleich-Pausiert gelb (warn-deep) statt grau — sichtbare Änderungen, begründet mit Kontrast-Tabelle und Pill als Atom; (c) Texte `trip.status.*` für beide (Vergleich zeigt „Entwurf“ statt „draft“, Schreibung per CSS-Großschrift gleich); (d) Profil beim Trip in der Titel-Unterzeile („— ✎ · Trekking“), Leerfall ohne Aktivität = kein Zusatz, wie beim Vergleich ohne Profil; (e) Testid `trip-detail-status-badge` bleibt.
2. TDD RED: StatusSchild-Atomtest (alle 6 Zustände → Tone + Text), Paritätstest Trip/Vergleich gleicher Zustand ⇒ gleiches Markup, Profil-Zeile Trip.
3. Umsetzung, alte Dateien löschen, Tests umhängen, `app.css`.
4. Staging: Paritäts-E2E + neues Fresh-Eyes-Paar (AC-15, Desktop 1440 / Mobil 390) als Kommentar in Epic #2345.

### Dependencies
- Upstream: `ui/pill/Pill`, `deriveTripStatus`, i18n `trip.status.*`, `ACTIVITY_TYPE_OPTIONS`/`AKTIVITAET`.
- Downstream: Trip-Hub, Vergleich-Hub. Kacheln/Listen (`SubscriptionCard`, `ListNameCell`, `compare/+page.svelte` mit `compare-status-pill`-Testid eigener Bauart) nutzen CompareStatusPill nicht → unberührt. `hubUebersichtModell.ts:230` nutzt für Vergleich schon `trip.status.*` → passt.
- ADR-0110 Punkt 4 („Status als Badge in der Titelzeile bei beiden Arten“) deckt das; kein neues ADR, Verweis in der Spec genügt.

### Befunde gegen den Plan
- Test-Umhängung breiter als „data-variant umdrehen“ (Pfad-Importe, Source-Inspection auf TONE_MAP/LABEL_MAP, Signatur `trip`→`status`) — Inventar oben.
- Globale `app.css`-Änderung statt lokal: bewusst gewählt (Atom-Fix), Wirkung auf Demo-Seite begrenzt.
- Bestehende bewusste Abweichung: Übersichts-Kachel zeigt bei aktivem Vergleich „läuft automatisch“, der Kopf „Aktiv“ — nicht Teil dieser Nachbesserung, in der Spec erwähnen.

### Nebenbefund (für #1199)
- `listen.status.draft` lautet im deutschen Katalog „draft“ (englisch) — betrifft Listen-Punkte, nicht den Kopf.

### Open Questions
- keine (Optik-Entscheidung wird mit der Spec freigegeben)


## Übergabe an /50-implement (aus /40-tdd-red, 2026-11-08)

### RED-Tests (alle benannt ausführen, `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test <Dateien>`)
| Datei | AC | Stand |
|---|---|---|
| `src/lib/components/shared/status-schild/__tests__/status_schild.test.ts` (neu) | AC-2, AC-3, AC-4, AC-5, AC-8, AC-11 | rot (Baustein fehlt; Kaskade app.css: pausiert heute #c08a1a) |
| `src/lib/components/shared/status-schild/__tests__/status_schild_pendant_sperre.test.ts` (neu) | AC-9 | rot (Alt-Bausteine + 4 Importeure) |
| `src/lib/components/shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts` (erweitert, Block „#2837 S1b") | AC-1, AC-3, AC-6, AC-8, AC-11; Wächter AC-7, AC-10 | rot; AC-7/AC-10 **Wächter, heute grün (gewollt)** |
| `src/lib/components/shared/status-schild/StatusSchild.atomic.test.ts` (per `git mv` aus `trip-detail/TripStatusBadge.atomic.test.ts`) | #389-Zusicherungen | rot (Datei fehlt) |
| `trip-detail/__tests__/tripStatusFinishedDraft.test.ts`, `compare/compare_detail.test.ts`, `compare/__tests__/issue_491_compare_detail.test.ts`, `shared/hub-uebersicht/__tests__/hub_uebersicht_modell.test.ts` | umgehängt | rot |
| `frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts` (Block „HS S1b", HS-1 … HS-7) | AC-1 … AC-8, AC-11 | geschrieben, **nicht ausgeführt** (`--list` ok); Lauf in /e2e-verify |
| `src/lib/i18n/__tests__/paritaet_de_en.test.ts` (bestehend) | AC-11 Katalog: alle `trip.status.*` in de und en | Wächter, grün; muss grün bleiben |

### Vertrag, den RED festlegt
- `StatusSchild.svelte` Props: `status: TripStatus`, `testid?: string` (Standard nicht festgelegt; beide Seiten übergeben `trip-detail-status-badge`). Rendert genau ein `Pill` mit `data-outlined`, `data-status={status}`, `data-testid={testid}`, **kein `style`-Attribut**, Text `$t('trip.status.<status>')`. TONE_MAP/LABEL_MAP im Quelltext beibehalten (Source-Inspection-Tests `StatusSchild.atomic.test.ts`, `tripStatusFinishedDraft.test.ts`).
- Seiten-Parität: das Schild-Element hat bei Trip und Vergleich im selben Zustand **identische Attribute** (deepEqual) und identischen Text.
- Profil: in der Region-Zeile steht direkt hinter `trip-region-edit-toggle` ein `<span>` mit Text `· <Aktivitäts-Label>` (wie beim Vergleich).

### Erst in GREEN umbiegen (in RED bewusst nicht, sonst stürzen ganze Suiten ab)
- `trip-detail/__tests__/f9Pruefstand.ts:115,187-188` (`K.TripStatusBadge`, `kopfRendern`) und `compare/__tests__/f10Pruefstand.ts:136,241` (`K.CompareStatusPill`, `bausteineRendern`): top-level `await komp(...)` auf die Alt-Dateien → auf `shared/status-schild/StatusSchild.svelte` mit Prop `status` umstellen.
- `trip-detail/__tests__/hub_uebersicht_trip_ssr.test.ts:62,321`: top-level Import `TripStatusBadge` → StatusSchild, Props `{ trip }` → `{ status: deriveTripStatus(t, …) }`.
- Exporte `trip-detail/index.ts:3`, `molecules/index.ts:27` entfernen; Kommentar `hubUebersichtModell.ts:88` nachziehen.
- E2E-Kommentare `hub-versand-inline-bearbeiten.spec.ts:133,281-284` (Trip trägt jetzt auch `data-status`; `.first()`-Locator prüfen) und `trip-detail-actions.spec.ts:74-77`.

### Goldens ändern sich gewollt (keine Lockerung)
`tests/golden/f9_trip_flaechen` (kopf_status, hub_seite) und `tests/golden/f10_vergleich_flaechen` (bausteine, hub_seite) sind byte-gleiche Goldens. Sie ändern sich durch: Vergleich „Entwurf"/„Pausiert"/„Aktiv" statt „draft"/„pausiert"/„aktiv", Pill-Markup statt CompareStatusPill, `data-status` am Trip-Schild, „· Trekking" in der Trip-Unterzeile. Neu schreiben (`schreibeGolden`) und den Diff im Commit begründen — der Diff darf **nur** diese Stellen betreffen.

### Token-Regel
`frontend/src/app.css:495` `[data-slot="pill"][data-outlined][data-tone="warning"]` → `color: var(--g-warn-deep)` (Token existiert, `app.css:216`). Im Commit als Token-Regel-Änderung benennen.
