# Context: feature-2980-c2-bildabgleich-r1

## Request Summary
Fix-Loop der Scheibe c2 (Seitenkopf, Teil von #2913) nach `mockup-bildpruefer` Runde 1: die acht c2-eigenen Abweichungen aus #2980 beheben, danach Bildprüfer Runde 2 auf denselben acht Zuständen (Trip/Orte × DE/EN × 1280×900/390×844, Reiter Wetter) und Soll/Ist-Bild an den PO. Spec bleibt `docs/specs/modules/feat_2913_c2_seitenkopf.md` (wird um ACs für Runde 1 ergänzt), Briefing `docs/briefings/feature-2913-c2-seitenkopf.md`.

## PO-Entscheidungen (13.11.2026, AskUserQuestion, Kommentar in #2980)
1. **Handy-Reiterleiste wie Mockup:** Text-Reiter mit 2-px-Unterstrich `--g-accent` auf allen Breiten (seitlich wischbar). Löst ADR-0111 Punkt 1 letzter Satz + Punkt 3 („Handy Pillen“) und ADR-0109 Punkt 7 Satz „Mobil bleibt die freigegebene Pill-Leiste“ ab ⇒ **neues ADR 0118** nötig (ADR-Index + `tests/test_adr_index_drift.py`), in 0109/0111 „Abgelöst durch 0118 (Teil Handy)“ vermerken.
2. **Kennzahlenzeile Handy entfällt** („Etappe · Briefing · Start in“, Herkunft #416, Soll-Bild Mai = historisch nach ADR-0111 Punkt 5).

## Soll aus dem Mockup (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`)
| Element | Mockup-CSS (Zeile) |
|---|---|
| Kopfband `.crumbs` | Z. 34: Mono 11 px, letter-spacing .06em, **uppercase**, `--g-ink-3`, padding 14 px, Linie `--g-rule-soft` unten; Name `b` = `--g-ink` 500 (Z. 35). Kein Zurück-Pfeil, Name nicht gekürzt (Z. 229–240) |
| Kebab | `btn sm ghost` (Z. 49: transparenter Grund, Rahmen `--g-rule`) |
| „Test schicken ▾“ | `btn sm accent` (Z. 47: Grund `--g-accent` #c45a2a, Text weiß) — **heute `Btn variant="primary"` (Ink/schwarz)**. Achtung ADR-0111 Punkt 6 „Hauptaktion Ink“ und #2879 „Accent als Fläche unter Text nur `--g-accent-deep`“ (Kontrast weiß auf #c45a2a ≈ 4,2:1 < 4,5 bei 12 px). Prüfen, welcher Btn-Variant-Baustein „accent“ abbildet und welche Fläche zulässig ist (vermutlich `--g-accent-deep` oder Ausnahme dokumentieren) |
| Kopf `.head` | Z. 36: padding 26/18, gap 6; Eyebrow Mono 11 px .12em uppercase `--g-ink-3` (Z. 38) |
| Meta `.meta` | Z. 40: **Mono 13 px `--g-ink-3`** — heute `HubKopf.svelte` `.hub-kopf-meta` Sans `--g-text-sm` `--g-ink-2` |
| Status-Pill `.pill` | Z. 41–43: Mono 11 px 500 uppercase .04em, padding 3/9, radius 999, **gefüllt ohne Rahmen**: neutral `--g-paper-deep`/`--g-ink-3`, good `rgba(61,107,58,.1)`/`--g-good`; Zuordnung PILL Z. 326 (fertig/Entwurf/pausiert/archiviert neutral, aktiv good) — heute `StatusSchild` umrandet/farbig |
| Reiter `.tabs/.tab` | Z. 62–66: Linie `--g-rule`, padding 12/16, 13 px 500 `--g-ink-3`, aktiv `--g-ink` 600 + Unterstrich `--g-accent`, overflow-x auto; **keine Handy-Media-Query** ⇒ gleiche Optik bei 390 |
| Abschnittskopf `.sectionh` | Z. 69–71: Linie `--g-rule-soft` unten, padding-bottom 12, h2 22 px 600, p 13 px `--g-ink-3` **max-width 68ch** (Wetter-Text Z. 442) |
| Vorlage-Karte | Z. 90–92, 507–512: Karte `.vorlage` flex, Eyebrow „Vorlage“, `.picker` inline-flex (Rahmen `--g-rule`, Grund `--g-paper`, padding 8/12, 15 px 600) mit `<small>` Mono 11 px `--g-ink-3` „▾ unverändert“; rechts „Als eigene Vorlage speichern“ `btn sm ghost` **mittig ausgerichtet** (align-items:center) |

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | Leiste (Brotkrumen, BackLink mobil Z. ~88, Kebab, Knopf `variant="primary"`), Meta-Stil, Kopf-Polster |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | Titelzeile, `badges`-Snippet (Pill), Region-/Profil-Zeile (Profil bleibt, #2796) |
| `frontend/src/lib/components/shared/status-schild/StatusSchild.svelte` | Pill-Optik (gefüllt gedämpft statt umrandet) — prüfen, wo sonst benutzt (Listen!) ⇒ ggf. Variante/Prop statt globaler Änderung |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | `unten`-Snippet `mobile-metrics` (entfällt), Crumb = `trip.shortcode ?? trip.name` (Mockup: Name) |
| `frontend/src/routes/compare/[id]/+page.svelte` | Compare-Pendant des Kopfs |
| `frontend/src/lib/components/mobile/MTabBar.svelte` | Handy-Media-Query (<900 px) Pillen ⇒ Unterstrich wie Desktop, Band wischbar, 44-px-Tippfläche halten (#2284 AC-13) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte` | Konsumenten MTabBar |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | Vorlage-Wähler (Kasten, Höhe, Text-Ausrichtung, „▾ unverändert“ Mono, Knopf-Höhe) — **noch nicht gelesen** |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Abschnittskopf Wetter (max-width 68ch, Linie) — **noch nicht gelesen** |
| `.claude/agents/mockup-bildpruefer.md` | Prüfer: nur 3 Eingaben (Mockup-Bild, Staging-Bild, Elementlisten-Auszug), max. 2 Runden |
| `frontend/e2e/fix2913-metrikliste-mockup.staging.spec.ts` | Vorbild für Ganzseiten-Aufnahmen gegen Staging |

## Existing Patterns
- Nur Design-System-Bausteine (ADR-0112, Wächter `bausteine_waechter*.test.ts`); Tokens statt Rohwerte.
- Trip/Orte teilen `HubKopf`/`SubscriptionHeader`/`MTabBar` (ADR-0097) — Änderung einmal im geteilten Baustein.
- Frontend-Tests laufen über `node --test` (kein Vitest), E2E Playwright gegen Staging.

## Dependencies
- Upstream: Tokens `app.css` (`--g-accent`, `--g-accent-deep`, `--g-paper-deep`, `--g-font-mono`), Atome `Btn`, `Eyebrow`, `BackLink`.
- Downstream: `StatusSchild` evtl. auch in Listen (Trip-/Vergleichsliste) — Pill-Änderung darf dort nur bewusst wirken; `MTabBar` nur im Hub (Anlegen nutzt `AnlegeReiter`).

## Existing Specs
- `docs/specs/modules/feat_2913_c2_seitenkopf.md` (AC-1…15; c2), `mobile_tab_leisten_mtabbar.md`, `issue_416_mobile_trip_kennzahlen.md` (wird abgelöst), `rework_2845_hub_reiterleiste.md`.

## Risks & Considerations
- **Kontrast „Test schicken“:** Mockup-Orange als Fläche mit weißem 12-px-Text verfehlt WCAG-AA (Design-Leitprinzip „hoher Kontrast gewinnt“, #2879). Lösung im Rahmen bestehender Entscheidungen: `--g-accent-deep`-Fläche (6,77:1) oder `Btn variant="accent"` falls vorhanden; Entscheidung in der Analyse begründen.
- **ADR-0110/0111 „Hauptaktion Ink“** widerspricht Mockup-Akzent-Knopf ⇒ im neuen ADR 0118 mitregeln (Knopf „Test schicken ▾“ Akzent wie Mockup).
- Bestandstests binden an Pillen-Optik (MTabBar), `trip-header-mobile-metrics`, Brotkrumen-Kürzel, BackLink mobil: mitziehen, nicht löschen (Kennzahlen-Tests aus #416 ersatzlos entfernen ist durch PO-Entscheidung gedeckt).
- 44-px-Tippflächen am Handy (#2284 AC-13) bei Text-Reitern und Kebab erhalten.
- Brotkrumen am Handy ohne Zurück-Pfeil und ohne Kürzung: langer Name darf nicht horizontal überlaufen (AC-11) ⇒ Umbruch statt Ellipsis.
- Bildaufnahmen Runde 1 liegen nicht im Repo; Runde 2 neu aufnehmen (Mockup lokal gerendert + Staging, gleicher Viewport).

## Analysis

### Type
Feature (Fix-Loop Optik nach Bildprüfer Runde 1, Teil von #2913)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `docs/adr/0118-…-handy-reiter-unterstrich-und-akzent-aktion.md` | CREATE | Handy-Reiter = Unterstrich (löst ADR-0109 P7 Satz „Mobil bleibt Pill-Leiste“, ADR-0111 P1 letzter Satz + P3 „Handy Pillen“ ab); „Test schicken ▾“ = `Btn accent` (löst ADR-0110 P2 / ADR-0111 P6 „Hauptaktion Ink“ für diesen Knopf ab, Fläche bewusst `--g-accent-deep`); #416-Kennzahlen entfallen |
| `docs/adr/0109-…md`, `0110-…md`, `0111-…md`, `docs/adr/README.md` | MODIFY | Status „Teilweise abgelöst durch ADR-0118 (…)“ in Datei + Index (Statusklasse muss gleich sein, `tests/test_adr_index_drift.py`) |
| `docs/specs/modules/feat_2913_c2_seitenkopf.md` | MODIFY | neue ACs Runde 1 (AC-16 ff.), Changelog |
| `docs/specs/modules/mobile_tab_leisten_mtabbar.md` | MODIFY | Handy-Optik Unterstrich, AC-4 44 px bleibt, AC-6 als überholt markieren |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | Z.103/106 `variant="primary"`→`"accent"`; Kopfband Mono 11 px uppercase `--g-ink-3`, Name `--g-ink` 500; `.back-mobil`/BackLink weg (Z.92, CSS 219-235); Ellipsis/nowrap (150-164) → Umbruch (`overflow-wrap:anywhere`, `min-width:0`); Kebab ghost mit Rahmen `--g-rule`, 44 px mobil; `.hub-kopf-meta` (204-209) Mono 13 px `--g-ink-3` |
| `frontend/src/lib/components/shared/status-schild/StatusSchild.svelte` | MODIFY | gefüllt ohne Rahmen (`data-outlined` weg); TONE_MAP active→good, Rest neutral; neutral lokal `--g-paper-deep`/`--g-ink-3` (Dunkelmodus-Kontrast messen, sonst `--g-ink-2` + Vermerk). Einzige Konsumenten: TripHeader + Compare-Seite ⇒ globale Änderung zulässig |
| `frontend/src/lib/components/mobile/MTabBar.svelte` | MODIFY | Handy-@media (158-216): Pillen raus, Unterstrich wie Desktop/AnlegeReiter (123-161): 13 px 500 `--g-ink-3`, aktiv `--g-ink` 600 + 2 px `--g-accent`, Grundlinie `--g-rule`; Band/Scroll-Snap/Fade + 44 px bleiben; Zähler neutral bleibt |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | `mobile-metrics`-Snippet (186-199) + CSS (210-218) entfernen; Crumb auf `trip.name` (Mockup zeigt Namen, nicht Kürzel) |
| `frontend/src/routes/compare/[id]/+page.svelte` | CHECK | Pendant: Crumb/Status/Knopf laufen über HubKopf/StatusSchild, nur prüfen |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | `.wt-karte` align-items center; Picker Rahmen `--g-rule`, Grund `--g-paper`, 15 px 600; „▾ unverändert“ Mono 11 px `--g-ink-3` |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | lokaler `.wt-kopf` (Z.219-222, CSS ab ~300): Linie `--g-rule-soft` unten, padding-bottom 12, h2 22/600, p 13 px `--g-ink-3` max-width 68ch (kein SectionH ⇒ keine Seiteneffekte) |
| Tests: `mobile/__tests__/s3a2794_mtabbar_leiste_soll.test.ts`, `e2e/issue-269-mobile-trip-tabs.spec.ts`, `status_schild*.test.ts`, `StatusSchild.atomic.test.ts`, `hub_kopf_baustein.test.ts`, `hub_kopf_c2_mockup.test.ts`, `hub_kopf_seiten_paritaet.test.ts`, `subscription_header_einmal_gerendert.test.ts`, `tripStatusFinishedDraft.test.ts`, `e2e/hub-kopf-aufbau.spec.ts`, `e2e/hub-kopf-c2-mockup.staging.spec.ts` | MODIFY | bewusst auf neues Soll ziehen (nicht löschen) |
| `frontend/src/lib/components/trip-detail/TripHeader.mobile-metrics.test.ts` | DELETE | #416 entfällt (PO-Entscheidung 2) |
| neue Bildaufnahme-Spec nach Vorbild `e2e/fix2913-metrikliste-mockup.staging.spec.ts` (file://-Mockup, 1280×900 + 390×844, Trip/Orte, DE/EN) | CREATE | Aufnahmen für Bildprüfer Runde 2 |

### Scope Assessment
- Files: ~6 Komponenten + ADR/Specs + ~10 Tests
- Estimated LoC: +250/-120 (rund 300-350 Diff)
- Risk Level: MEDIUM (geteilte Bausteine für Trip und Orte; viele Bestandstests binden an alte Optik; rein Frontend/CSS, keine Daten)

### Technical Approach
Alles im geteilten Baustein (ADR-0097), nur Tokens (Wächter `bausteine_waechter*.test.ts`; `68ch` relativ, beim Wächterlauf bestätigen).
- **Knopf-Farbe:** `Btn variant="accent"` (`--g-accent-deep` #8c3e1a, 7,45:1). Mockup-#c45a2a mit Weiß 4,34:1 verfehlt AA; Design-Leitprinzip „hoher Kontrast gewinnt“ ist PO-bestätigt (2026-05-25, #2879) ⇒ keine neue PO-Frage. Dem Bildprüfer als Elementlisten-Zusatz „bewusste Abweichung: Fläche --g-accent-deep statt --g-accent (AA)“ mitgeben, im Soll/Ist-Bild für den PO offen nennen.
- **Uppercase nur per CSS:** DOM-Text bleibt; Tests mit `innerText`/`useInnerText` auf Brotkrumen/Pill vorher greppen (Falle CSS-uppercase).
- **Brotkrumen Handy:** kein Zurück-Pfeil, Elternlabel bleibt Link, Umbruch statt Ellipsis (AC-11 kein horizontaler Überlauf).
- **Status-Pill:** global gefüllt, Zuordnung nach Mockup Z.326 (aktiv good, sonst neutral); `data-status` bleibt.
- Reihenfolge: ADR 0118 + Spec-ACs → Tests rot → CSS/Markup → Staging → Bildaufnahmen → Bildprüfer Runde 2 (Elementlisten-Auszug je Zustand, max. 2 Runden insgesamt ⇒ dies ist die letzte) → Soll/Ist-Bild an PO.

### Dependencies
- Tokens `app.css`: `--g-accent` #c45a2a, `--g-accent-deep` #8c3e1a, `--g-paper-deep`, `--g-ink-3`, `--g-rule`, `--g-rule-soft`, `--g-good`, `--g-font-mono`; Pill-Tones `good`/`neutral` (app.css ~663-704).
- Konsumenten: HubKopf ← TripHeader, Compare-Seite; MTabBar ← TripTabs, CompareTabs; VorlageKarte ← WetterTabInhalt; StatusSchild ← TripHeader, Compare-Seite.
- Bildprüfer `.claude/agents/mockup-bildpruefer.md`: nur Mockup-Bild, Staging-Bild, Elementlisten-Auszug (`docs/context/einstellungen_neu/elementliste.json`).

### Open Questions
- [x] Knopf-Farbe accent vs. accent-deep → accent-deep (bestehende PO-Linie Kontrast)
- [x] Crumb Kürzel vs. Name → Name (Mockup)
- [ ] Dunkelmodus-Kontrast Pill neutral (`--g-ink-3` auf `--g-paper-deep`) in der Umsetzung messen; bei <4,5:1 `--g-ink-2` + Vermerk
- [ ] Vorlage-Karte: Zentrierung Knopf gegen Spalte mit Eyebrow im Bildvergleich bestätigen
