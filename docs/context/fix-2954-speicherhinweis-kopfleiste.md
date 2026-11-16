# Context: fix-2954-speicherhinweis-kopfleiste

## Request Summary
Der Speicherhinweis („Gespeichert", „Speichere …", Fehler/Konflikt) schwebt heute als `position: fixed`-Chip unten rechts über dem Inhalt aller Hub-Reiter (Trip und Orte) und verdeckt/fängt Klicks der Metrik-Liste ab (Messung #2913: @1024 16/15, @1280 11/10, @390 9/6 verdeckte Scroll-Positionen). Soll nach Mockup Fassung 3: Text in der Kopfleiste (`.crumbs`) links vom ⋮-Menü und „Test schicken", Farbe `--g-good`, 12,5 px, verschwindet nach 5 s. Kein Overlay.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | Atom; heute `position:fixed; bottom/right 16px; z-index 62`, mobil über BottomNav (`--g-nav-clearance`). Zustände idle/dirty/saving/conflict(+Retry-Knopf)/error; idle zeigt Dot + „Gespeichert" + HH:MM, blendet nach 3 s auf neutrale Farbe ab (nie unsichtbar, #880/#2400). |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` Z. 183–186 | einzige Mount-Stelle (`{#if saveController}<SaveIndicator …/>`), unter dem Titelblock, außerhalb der Leiste. |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | geteilter Kopf Trip/Orte; Leiste `.hub-kopf-leiste` mit `.breadcrumb-path` + `.hub-actions` (Kebab, Senden/Setup, `meldungen`-Snippet). Ziel-Ort des Hinweises: in `.hub-actions` vor dem Kebab (Mockup-Reihenfolge Toast → ⋮ → Test schicken). Reicht `saveController` an SubscriptionHeader durch. |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte`, `frontend/src/routes/compare/[id]/+page.svelte` | Aufrufer von HubKopf, übergeben `saveController`. Keine Änderung nötig, wenn HubKopf den Mount übernimmt. |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | SaveStatus-Controller (state, error, savedAt); kein Ausblende-Timer für die Anzeige. |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` Z. 34 (`.crumbs` flex-wrap), 59 (`.toast`), 211 (`.toast.bad` → `--g-bad`), 229–237 (Markup, `aria-live="polite"`), 679 (`flash()` leert nach 5000 ms) | Soll. |

## Existing Patterns
- Geteilter Kopf: EIN Markup für Trip/Vergleich, Unterschiede nur per Props/Snippets (ADR-0110, `context_herkunft_zweige_eingefroren.test.ts`).
- Leiste mobil: 44-px-Tippflächen per negativem Block-Rand; `.hub-actions` ist `flex-wrap`, schrumpfbar (Meldung bricht in den Aktionen um, #2837 AC-8).
- Mockup-Toast: Text, `aria-live="polite"`, Fehlerfarbe per Klasse `.bad`.

## Dependencies
- Upstream: `SaveStatus`, `Dot`, i18n-Katalog `nav.*` (gespeichert, speichere, nicht_gespeichert, konflikt, nochmal_speichern, speicherfehler[_mit]).
- Downstream: ~35 E2E-Specs greifen über `data-testid="save-indicator"` + `data-state` auf den Zustand zu (bleiben gültig, wenn testid/data-state erhalten bleiben). Positions-Zusicherungen, die geändert werden müssen: `frontend/e2e/feat-880-autosave-overlay.spec.ts:84–91, :207–213` (AC-1/AC-7 `position: fixed`), `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts:915–960` (AC-10 „fixed, unten rechts"). Unit-Wächter: `speicheranzeige_ruhe_kontrast.test.ts` (rechnet mit den CSS-Werten der Komponente), `subscription_header_einmal_gerendert.test.ts`, `subscription_header_kontextneutral.test.ts`, `navigation_und_speicheranzeige_sprache.test.ts`, `saveIndicatorConflictBranch.test.ts`, `harte_farben_waechter`, `bausteine_waechter_regeln.ts` (Listen-Eintrag), i18n-Wächter.

## Existing Specs / ADRs
- `docs/specs/modules/feat_880_autosave_overlay.md` — Entscheidung „fixes Overlay unten rechts", Idle-Zurücktreten, nie display:none (Barrierefreiheit), Fehler dauerhaft sichtbar (AC-4).
- `docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md`, `feat_2284_s1_subscription_header.md` (S2: Chip kommt vom Baustein), `rework_2837_s1_hub_kopf.md`, `feat_2913_c2_seitenkopf.md`.
- ADR-0110 (geteilter Hub-Kopf), ADR-0111 (Mockup Fassung 3 ist Maßstab), ADR-0118 (Kopfleiste ohne Zurück-Pfeil, Akzent-Aktion). Neues ADR nötig, das #880 „fixed overlay" für den Hub ablöst (Issue verlangt das).

## Risks & Considerations
- **Verlorene Zusicherung:** Die im Issue genannten Artefakte (`docs/artifacts/fix-2913-metrikliste-mockup/zusicherung-speicherhinweis-fuer-seitenkopf.ts.txt`, Messung, Rot-Ausgabe) existieren in keinem Zweig/Worktree mehr — die Zusicherung „kein Bedienelement wird vom Hinweis verdeckt (elementFromPoint)" muss in TDD-RED neu geschrieben werden.
- **Produktfrage 5 s:** Mockup leert den Text nach 5 s; heute bleibt „Gespeichert HH:MM" dauerhaft (Barrierefreiheits-Entscheidung #880). Fehler/Konflikt müssen dauerhaft bleiben (sonst geht ein Speicherfehler unbemerkt verloren). Klären in Analyse/Spec.
- **390 px:** Leiste hat Brotkrumen + Kebab + „Test schicken"; zusätzlicher Text kann umbrechen/Leiste erhöhen. Konflikt-Zustand mit „Nochmal speichern"-Knopf ist breit. Mockup `.crumbs` ist `flex-wrap`.
- **Layout-Sprung:** Erscheinen/Verschwinden des Textes darf die Aktionen nicht verschieben (Klick auf „Test schicken" während Statuswechsel). Ggf. reservierter Platz oder Text links vom Kebab mit `margin-inline-start:auto`.
- **Vergleich-Entwurf:** dort steht „Setup abschließen" auf dem Platz von Senden — Hinweis muss genauso erscheinen.
- **Barrierefreiheit:** `aria-live="polite"` (Mockup) — heute fehlt aria-live.
- Kontrast `--g-good` hell #3d6b3a / dunkel #6fbf6a auf Kopfgrund prüfen (WCAG-AA, Leitprinzip).

## Analysis

### Type
Feature (Rework Seitenkopf, Epic #2794 Seitenkopf-Scheibe; löst #880-Overlay für den Hub ab)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | MODIFY | Inline-Text statt `position:fixed`-Chip: kein Hintergrund, 12,5 px, Erfolg `--g-good`, Fehler/Konflikt `--g-danger-fg` (kein Hartwert, `--g-bad` gibt es nur im Mockup). `aria-live="polite"`. Erfolgstext per JS-Timer (`$effect` auf `savedAt`+`state`, Cleanup räumt Timer) nach 5 s geleert; `gz-save-fade`-Animation entfällt. `white-space:nowrap` weg (Umbruch 390 px). Element bleibt immer im DOM, `data-testid`/`data-state` unverändert an `controller.state`. |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | Mount in `.hub-actions` als erstes Kind (vor Kebab; Mockup-Reihenfolge Hinweis → ⋮ → Test schicken), in beiden Sendemodi (Senden / Setup abschließen). |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY | Mount entfernen (genau eine Instanz bleibt, hub-save-chip SC-1). `saveController`-Prop bleibt für den Speicherweg. |
| `docs/adr/0120-speicherhinweis-in-der-kopfleiste.md` + `docs/adr/README.md` | CREATE/MODIFY | Löst #880 „fixes Overlay, nie unsichtbar" und #2284 AC-10 für den Hub ab. |
| `docs/specs/modules/fix_2954_speicherhinweis_kopfleiste.md` | CREATE | Spec mit ACs. |
| `frontend/e2e/feat-880-autosave-overlay.spec.ts` (:84–91, :207–213), `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts` (:915–960) | MODIFY | Positions-Zusicherungen „fixed unten rechts" → „in der Kopfleiste vor dem Kebab". |
| `frontend/e2e/issue-758-save-indicator.spec.ts` (AC-2 :111), `frontend/e2e/hub-save-chip.spec.ts` (SC-1 :118), `epic-138-metriken-editor.spec.ts:114`, `design-system-trip-vergleich.spec.ts:1129` | MODIFY | Prüfen „Gespeichert"/sichtbar beim Öffnen ohne Speichern → auf `data-state="idle"` / attached umstellen (Text erscheint nur nach echtem Speichern). Text-Prüfungen direkt nach Speichern (AC-1, AC-3, SC-2, SC-5) bleiben, da < 5 s. |
| neue E2E `frontend/e2e/fix-2954-speicherhinweis-kopfleiste.spec.ts` | CREATE | Zusicherung „kein Bedienelement im Inhalt vom Hinweis verdeckt" (`elementFromPoint` über Scroll-Positionen, Trip + Orte, 390/1024/1280) — Original-Artefakt aus #2913 verloren, neu schreiben; Hinweis liegt in der Leiste; Text weg nach 5 s; Fehler bleibt. |
| `speicheranzeige_ruhe_kontrast.test.ts` | MODIFY | Kontrast neu: `--g-good` und `--g-danger-fg` gegen Kopfgrund (hell/dunkel, ≥ 4,5:1). |
| `subscription_header_einmal_gerendert.test.ts`, `subscription_header_kontextneutral.test.ts`, `saveIndicatorConflictBranch.test.ts`, `navigation_und_speicheranzeige_sprache.test.ts`, `bausteine_waechter_regeln.ts`, `harte_farben_waechter` | CHECK/MODIFY | Mount-Ort-Wechsel nachziehen. |

### Scope Assessment
- Files: ~3 Produktiv + ~10 Tests + ADR/Spec
- Estimated LoC: Produktiv ~+60/-60, Tests/Doku ~+250
- Risk Level: MEDIUM (zentrales Element auf allen Hub-Reitern, viele Specs hängen am Testid; Logik klein)

### Technical Approach (Tech-Lead-Entscheidungen)
1. **Ort:** HubKopf `.hub-actions`, erstes Kind. `.hub-actions` ist rechtsbündig (`justify-content:flex-end`) → erscheinender/verschwindender Text wächst nach links, Kebab und Senden bleiben stehen (kein Layout-Sprung der Knöpfe). Keine reservierte Mindestbreite (kostet am Handy Platz); fehlender Platz → Umbruch in den Aktionen (bestehendes Verhalten #2837 AC-8).
2. **5 s nur für Erfolg** (Mockup Z. 679, ADR-0111). `dirty`/`saving` sichtbar solange Zustand; **Fehler und Konflikt (mit „Nochmal speichern") dauerhaft** — bewusste Abweichung vom Mockup (dort leert auch `.bad` nach 5 s), weil ein Speicherfehler sonst unbemerkt bliebe (#880 AC-4 bleibt).
3. **Beim Öffnen kein Text** (Mockup-Toast startet leer; „Gespeichert" ohne Speichern wäre eine Behauptung). Text erscheint nur nach echtem Speichern (`savedAt` gesetzt), dann 5 s.
4. **Barrierefreiheit:** Element bleibt als stabile `aria-live="polite"`-Region im DOM; nur der Inhalt wechselt. Ersetzt die #880-Regel „nie unsichtbar" (Ansage statt Dauer-Anzeige) → ADR.
5. **JS-Timer statt CSS-Animation:** CSS-Animation startet bei idle→idle nicht neu; Timer an `savedAt` startet jeden Speichervorgang neu.
6. Kein neues Pendant-Bauteil: dasselbe Atom, geteilt Trip/Orte (ADR-0110, #1170).

### Dependencies
`SaveStatus` (`saveStatusStore.svelte.ts`, unverändert), `Dot`, i18n `nav.*` (keine neuen Texte nötig). Aufrufer TripHeader / compare `+page.svelte` unverändert.

### Open Questions
- keine offenen Produktfragen; Abweichung „Fehler bleibt stehen" und „beim Öffnen leer" werden in der Spec zur Freigabe sichtbar gemacht.
