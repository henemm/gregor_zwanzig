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
