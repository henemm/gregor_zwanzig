# Context: feature-2601-mobile-audit

## Request Summary
#2601 (Epic #2729, Strang B, go-live-pflicht): Mobile-UX-Audit über alle Routen in drei
Smartphone-Profilen, Befunde beheben, Befundliste ins Issue.

## Ausgangslage (wichtigster Befund)
Die erste Runde ist **bereits geliefert**: PR #2602 (Commit 52cfeaad5), gemergt 2026-10-23,
Spec `docs/specs/modules/mobile_ux_audit_2601.md` (approved, PO 2026-10-22). Das Issue blieb
trotzdem offen — ohne Kommentar, ohne Befundliste (Lieferpunkt „Befundliste im Issue“ fehlt),
am 2026-11-01 in Epic #2729 als offen eingeordnet.

Seitdem: **180 Frontend-Commits auf main**, davon ~59 aus der Englisch-Migration (Epic #2730,
F1–F12) und dem Editor-/Vergleichs-Umbau (#2345, #2837). Englische Texte sind oft länger →
neue Überlauf-/Umbruchrisiken, die die Oktober-Runde nicht sehen konnte (sie lief nur DE).

Damit ist der verbleibende Umfang: **zweite Audit-Runde auf aktuellem Stand, in DE und EN**,
Lücken der Routenliste schließen, neue Befunde beheben, Befundliste ins Issue, schließen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/mobile-ux-audit.spec.ts` (396 Z.) | Audit-Logik (`LAYOUT_CHECK`, `auditRoute`, `OVERLAYS`), Report nach `test-results/mobile-ux/` |
| `frontend/playwright.mobile-ux.local.config.ts` | 3 Profile: iphone13 390×844, iphone18pro 402×874, landscape 844×390; Chromium-Emulation |
| `frontend/e2e/ci-stack.sh`, `global.setup.ts` | Offline-Stack (Port 8091) + Login/Seed `playwright/.auth/admin.json` |
| `frontend/src/app.css` | Touch-Regeln aus Runde 1 (16px-Inputs, `.g-link-tap`, Häkchen 20px, Hinweis-Freihaltung) |
| `frontend/src/lib/i18n/resolveLang.ts` | Sprache: Cookie `gz_lang` > Accept-Language > de; **für Angemeldete überschreibt die Profilsprache** |
| `frontend/src/routes/**/+page.svelte` | 25 Seiten; Audit-Liste (Z. 374–391) deckt **nicht** ab: `/trips/[id]/edit`, `/compare/[id]/edit` (im Issue verlangt), `/reset-password`, `/magic-link`, `/verify-email` |
| `frontend/e2e/mobile-usability-audit.spec.ts` + `playwright.mobile-usability.local.config.ts` | älterer, separater Usability-Audit (Staging/WebKit) — nicht doppeln |

## Existing Patterns
- Audit = Report-Modus (Ist-Aufnahme) + `GZ_AUDIT_STRICT=1` (harte Kriterien a, c, d, Tap < 24px).
- Fixes bevorzugt zentral in `app.css` unter `@media (max-width: 899px), (pointer: coarse)`, nicht pro Komponente.
- Trip/Vergleich teilen Editor-Code (`shared/`, `context="route"|"vergleich"`) — Fix an einer Stelle wirkt in beiden (Gate!).
- Englisch-Lauf für angemeldete Routen braucht Profilsprache `en` (Cookie allein reicht nicht).

## Dependencies
- Upstream: lokaler Offline-Stack, Preview-Build, Seed-Daten (Trip mit Etappen, Vergleich).
- Downstream: CI-`e2e`-Job führt diese Config **nicht** aus (lokaler Audit, wiederholbar); Mobile-Tests `mobile-*.spec.ts`, `issue-*-mobile*.spec.ts` sichern Einzelaspekte.

## Existing Specs
- `docs/specs/modules/mobile_ux_audit_2601.md` (Runde 1, AC-1…AC-6) — wird fortgeschrieben (v1.1), keine neue Spec.
- `mobile_tab_leisten_mtabbar.md`, `mobile_stages_tab_listen_only.md`, `fix_2277_s2b_mobile_rahmen_angleichung.md`, `feat_1256_s8d_mobile_editor_fidelity.md`.

## Risks & Considerations
- Umfang erst nach dem Lauf bekannt → Analyse-Phase muss den Audit selbst ausführen (Befundliste ist Analyse-Ergebnis).
- EN-Lauf ändert die Profilsprache des Seed-Admins → nach dem Lauf zurücksetzen (nur lokaler Stack, kein Staging/Prod).
- Breite CSS-Regeln in `app.css` wirken auf Desktop-Touch-Geräte mit (`pointer: coarse`) — Desktop-Regressionen prüfen.
- Code-Teilung Trip/Vergleich: keine compare-eigenen Sonderfixes.
- Nur Chromium; Safari-Eigenheiten bleiben unbeobachtbar (bekannte Grenze aus Runde 1).

## Audit Runde 2 — Messergebnis (2026-11-10, HEAD 76ca6e4d9, DE+EN × 3 Profile, Chromium)

Rohdaten (flüchtig): Scratchpad `audit-de/`, `audit-en/` (Reports + Screenshots). Alle 12 Läufe grün (Report-Modus).

**Hart (a/c/d überall 0; nur Tap < 24px):**
| Route/View | Element | Maß | Profile |
|---|---|---|---|
| /trips/[id] Etappen | `stage-date-field` Segmente Tag/Monat | 22×26 (×8 Etappen) | alle, DE+EN |
| /trips/[id] Etappen | `stage-start-time-field` Stunde/Minute | 22×26 (×8) | alle, DE+EN |
| /trips/new | `trip-new-date-input` Segmente tt/mm | 22×26 | alle, DE+EN |
| /trips/[id] Übersicht | `trip-full-profile-stage-*` „Etappe T01 auswählen" | 23–24×164 | Hochformat |

**Weich:** Text 10px (Tab-Badges `trip-detail-tab-badge-*`/`compare-detail-tab-orte`, ✉ in hub-overview, „AKTIONEN" Karten-Menü); Tap 24–40px bei 48 Selektoren (u. a. „+ Neuer Trip" 87×28, `compare-list-new-mobile` 28, „Im Editor öffnen →" 28, `hub-orte-add` 28, `briefings-laufzeit` 28, `wm2-grundauswahl` 36, Archiv-Filter 35, channel-tab 37); Clipping `hub-kopf-breadcrumb` (scrollH 30/clientH 17) Trip+Vergleich-Hub; /compare: ein `<main>` 16px waagerecht scrollbar (374/358), von Check (a) nicht erfasst; **nur EN:** `cm-mobile-tabbar` /compare/new scrollt waagerecht (378/358). Input<16px: 0.

**EN-Übersetzungslücken (kein Mobile-Befund):** Filterchips ALLE/AKTIV/GEPLANT/PAUSIERT/FERTIG (/trips, /compare), Status „AKTIV" auf Trip-Karten, „AKTIONEN", „WETTER-BRIEFING" (/login).

**Audit-Mängel:** Trefferkappung 15/20/12 je View + Verzweigung in `LAYOUT_CHECK` lässt <24px-Treffer in die 24–40-Liste rutschen (Zahlen = Untergrenzen); Redirect-Erkennung `route.startsWith(landed)` verdeckt, dass `/trips/[id]/edit`, `/compare/[id]/edit` per 307 auf die Detailseite leiten; nicht abgedeckt: öffentliche Startseite (ausgeloggt), `/reset-password`, `/verify-email`, `/magic-link(/verify)`, Wizard-Schritte > 1 von /trips/new, /compare/new; `/gpx-upload` → 301 /trips/new (Skip korrekt). Spec-AC-3/AC-6 nennen Tabs alarme/wetter-metriken/vorschau, die es nicht mehr gibt (jetzt übersicht/etappen/wetter/zustellung).

**Laufanleitung — Sicherheitsfalle:** Vorschau-Proxy `/api` zeigt per Default auf `localhost:8091` = STAGING (`vite.config.ts`, `API_PROXY_TARGET`). Lokal zwingend `GZ_E2E_API_PROXY_TARGET=http://localhost:<go-port>` + `GZ_API_BASE` + `GZ_REPO_ENV_FILE=/nonexistent`; Stack auf freien Ports (`GZ_CI_STACK_GO_PORT=8191`, `GZ_CI_STACK_PY_PORT=8102`). Erster Versuch traf Staging mit 401 (nichts geschrieben). Sprache: Config ohne `locale` → Chromium zeigt öffentliche Seiten EN; EN angemeldet via `PUT /api/auth/profile {"language":"en"}`. Seed legt keinen Vergleich an (manuell nötig).

## Analysis

### Type
Feature (Audit Runde 2 + Fixes; Fortschreibung Spec `mobile_ux_audit_2601.md` v1.0 → v1.1)

### Ursachen (im Code bestätigt)
- Segmente 22px: `molecules/DatumFeld.svelte:214` und `molecules/UhrzeitFeld.svelte:~133` — `[data-segment]{padding:1px 1px}`. `edit/StageDateField`/`StageTimeField` sind nur Hüllen, trip-new nutzt `DatumFeld groesse="gross"` → ein Fix in zwei Bausteinen deckt alle Fundstellen, Trip und Vergleich.
- Breadcrumb-Clipping: `shared/hub-kopf/HubKopf.svelte:76` Link mit `.g-link-tap` (±13px Padding/Margin) in `.breadcrumb-path` mit `overflow:hidden` (Z. 135) → Trefferfläche wird mitgeklippt.
- Höhenprofil: `trip-detail/FullProfile.svelte:160-178` transparentes `<rect>` je Etappe mit Breite des Streckenanteils → kurze Etappen 23px.
- Audit: `mobile-ux-audit.spec.ts:162` `if (min<24 && tiny.length<15) … else if (min<40)` → Überlauf der Kappung rutscht in weich; `:334` `route.startsWith(landed)` verdeckt 307-Redirects.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/molecules/DatumFeld.svelte | MODIFY | Segment min 24×24 (Touch/≤899px), Jahr unverändert |
| frontend/src/lib/components/molecules/UhrzeitFeld.svelte | MODIFY | dito |
| frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte | MODIFY | Clipping nur horizontal (overflow-x:clip / padding-block), Trip+Vergleich |
| frontend/src/lib/components/trip-detail/FullProfile.svelte | MODIFY (minimal) | `data-tap-equivalent` am rect (WCAG 2.5.8 „equivalent": Etappenwahl im Etappen-Tab) |
| frontend/src/app.css | MODIFY | 28px-Knöpfe auf bestehenden 36px-Boden, 10px-Texte → 11px |
| /compare-Seite, `cm-mobile-tabbar` (AnlegeReiter) | MODIFY (nach Messung) | main-Überlauf 16px; EN-Tabbar: gewollter Scroll oder Fix |
| frontend/e2e/mobile-ux-audit.spec.ts | MODIFY | Zähler ungekappt, Redirect-Status, main-Überlauf allgemein, Routen (ausgeloggte `/`, reset-password, verify-email, magic-link(/verify), Wizard-Schritte), Höhenprofil-Ausnahme |
| frontend/playwright.mobile-ux.local.config.ts | MODIFY | `GZ_AUDIT_LOCALE=de|en` (locale + Profilsprache), Abbruch ohne `GZ_E2E_API_PROXY_TARGET` (Staging-Schutz) |
| frontend/e2e/issue-2601-*.spec.ts | CREATE | Messtests (berechnete Größen) Segmente ≥24px, Breadcrumb ungeclippt, Desktop 1280×800 unverändert |
| docs/specs/modules/mobile_ux_audit_2601.md | MODIFY | v1.1, AC-3/AC-6 auf Tabs übersicht/etappen/wetter/zustellung, neue ACs, Laufanleitung |

### Scope Assessment
- Files: 9–11
- Estimated LoC: +250…350 / −30 (ca. die Hälfte Audit/Spec) → LoC-Override 500 laut Issue zulässig
- Risk Level: LOW–MEDIUM (zentrale Bausteine DatumFeld/UhrzeitFeld, aber nur Touch/≤899px-Medienblock; Desktop-Messung als Gegenprobe)

### Technical Approach
Reihenfolge: (1) Audit härten (Zähler, Redirect, main-Überlauf, Proxy-Schutz) und neu messen — wahre Zahlen vor dem Fix; (2) Segmentfelder zentral (Padding statt `::after`, sonst Überlappung; natives `type=date` verworfen — macht Segmentbausteine #2881 rückgängig); (3) Breadcrumb in HubKopf; (4) Höhenprofil als dokumentierte Ausnahme WCAG 2.5.8 „equivalent" (Verbreiterung erzwingt bei 8+ Etappen Überlappung = Fehlklicks); (5) main-Überlauf /compare und EN-Tabbar messen, dann gezielt beheben; (6) weiche Befunde nur über vorhandene app.css-Böden, keine Einzelhacks; (7) Routen/Locale/Spec v1.1. Befundliste (Vorher/Nachher) als Kommentar in #2601.

### Dependencies
DatumFeld/UhrzeitFeld werden in Trip-Editor, Vergleichs-Editor und trip-new genutzt (shared). HubKopf wirkt in Trip- und Vergleichs-Hub. Audit-Lauf braucht lokalen Stack auf freien Ports (siehe „Laufanleitung — Sicherheitsfalle").

### Ausgegliedert
- EN-Übersetzungslücken → #2919 (Epic #2730), kein Mobile-Befund.

### Gegen den Plan / Risiken
- Ursache main-Überlauf /compare noch offen; zeigt sich ein Fehler in einem geteilten Baustein mit großem Umfang → abtrennen.
- Harte Zahl ist Untergrenze; nach Audit-Härtung können weitere harte Treffer auftauchen.
- Breitere Segmente können in EN auf 390px die Etappenkarten-Zeile umbrechen → im Etappen-Tab messen.
- `pointer:coarse` greift auch auf Touch-Laptops >899px (bei Segmenten harmlos).

### Open Questions
- keine Produktfrage offen (Höhenprofil-Ausnahme ist WCAG-konform, gleichwertige Bedienung vorhanden).

## RED-Stand (Phase 5, 2026-11-10, Commit 3b18e9211, Basis d322e2a9e)

Testdateien (Namens-Gate verbietet `issue-<N>`-Präfix, daher sprechende Namen; Spec-Testplan in /50 nachziehen):
- `frontend/e2e/mobile-ux-messung.spec.ts` — AC-7…AC-14 (9 Fälle)
- `frontend/e2e/mobile-ux-audit-selbsttest.spec.ts` — AC-15 (3 Fälle), importiert künftiges Modul
- `frontend/e2e/mobile-ux-audit-staging-schutz.test.ts` — AC-16 (`node --test`, läuft automatisch im `frontend-test`-Job via `npm test`; NICHT auf Listen setzen)

RED-Ist: AC-7/8 Segmente 22×26; AC-9 grün (Regressionsschutz, Desktop-Sollwerte als Konstanten); AC-10 Brotkrumen 30/17, elementFromPoint trifft `div.hub-kopf-leiste`; AC-11 kein `data-tap-equivalent` (Etappenwahl-Teil schon grün); AC-12a inneres `<main>` ohne Klasse +16 px in allen Profilen; AC-12b grün (EN-Tabbar bewusst scrollbar: overflow-x:auto + Fade-Maske, letzter Reiter erreichbar) → kein Fix an der Tabbar nötig; AC-13 10 px; AC-14 28,39 px; AC-15 Modul fehlt; AC-16 Liste ohne Variable Exit 0, keine Locale.

Vertrag Audit-Modul `frontend/e2e/mobile-ux-audit-check.ts`: Named Exports `LAYOUT_CHECK`, `type LayoutResult`; `mobile-ux-audit.spec.ts` importiert daraus. `tinyTargets` alle < 24 ungekappt, `smallTargets` nur 24–39, `pageOverflowPx` = Max über Fenster UND jedes `<main>`, `[data-tap-equivalent]` nie hart.

Für /50-implement:
- `.github/ci_e2e_specs.txt`: `e2e/mobile-ux-messung.spec.ts` + `e2e/mobile-ux-audit-selbsttest.spec.ts` aufnehmen; `E2E_MIN_SPECS` 78→80, `E2E_MIN_EXECUTED_HAUPT` 697→709 (per `npx playwright test --list` über die Positivliste nachmessen, Kommentar-Kette in ci.yml fortschreiben).
- Selbsttest-Datei allein laufen lassen, solange das Modul fehlt (Ladefehler beendet Sammellauf mit „No tests found").
- Config AC-16: `GZ_AUDIT_LOCALE` → `use.locale` (de/en) in allen 3 Projekten; fehlt `GZ_E2E_API_PROXY_TARGET` → throw mit Variablennamen.
- AC-13: „AKTIONEN" (`Sheet.svelte`, inline `style:font-size="10px"`) und ✉ (`ChannelDot.svelte`, inline style) sind Inline-Styles → Fix in diesen geteilten Bausteinen (Token `--g-text-xs`), nicht `!important` in app.css. „AKTIONEN" hart deutsch → gehört zu #2919.
- AC-8: Vergleichs-Editor hat kein UhrzeitFeld; gemessen wird `compare-versand-enddate-input` (Zustellung → „Bis Datum").
- Lokaler Stack: Ports 8191/8102, Vorschau 4173 nur mit `GZ_E2E_API_PROXY_TARGET`; alte Worktree-`playwright/.auth/admin.json` gesichert im Scratchpad (ignoriert, nie committen).
