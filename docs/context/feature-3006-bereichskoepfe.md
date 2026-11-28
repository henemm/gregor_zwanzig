# Context: feature-3006-bereichskoepfe

## Request Summary
Issue #3006 (Teil von Epic #2913): Jeder Reiter der Einstellungen (Trip und Orte) zeigt oben den Bereichskopf aus Mockup Fassung 3 (`.sectionh`: h2 + Erklärsatz, optional Aktion rechts), DE/EN aus dem Katalog (ADR-0104), aus einem Design-System-Baustein (ADR-0112), geteilt für Trip und Orte (ADR-0097). Elementlisten-Abgleich meldet `abschnittskopf` aller Reiter als gefunden.

## Soll (Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`)
- CSS Z. 69-71: `.sectionh{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;border-bottom:1px solid var(--g-rule-soft);padding-bottom:12px}`, `h2 22px/600/letter-spacing -.01em/margin 0`, `p margin 2px 0 0; color ink-3; 13px; max-width 68ch`.
- Wetter Z. 442: „Wetter“ / „Was im Briefing steht, was für dich zu viel oder zu wenig ist und ab wann du einen Alarm bekommst.“ (Kopf auch in Zuständen laedt/fehler)
- Zustellung Z. 556: „Zustellung“ / „Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.“
- Etappen Z. 579 (nur Trip): „Etappen & Wegpunkte“ / „Das Tempo bestimmt die Gehzeiten und damit, welche Stunden je Wegpunkt bewertet werden.“
- Orte Z. 590 (nur Orte): „Orte“ / „Ein Ort ergibt ein Orts-Briefing. Ab zwei Orten kommt die Vergleichstabelle dazu, ohne Rangfolge.“ + Knopf rechts „+ Ort hinzufügen“ (ghost, sm)
- Übersicht Z. 594: „Übersicht“ / „Unverändert: Stand, letzte Briefings, nächster Versand.“ (Mockup-Satz ist Platzhalter-Charakter; Übersicht ist in der Elementliste noch nicht erfasst, #2969)

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/subscriptionTabs.ts` (~42-60) | `REITER_DEFINITION`, Reiterliste; Kommentar „Bereichsköpfe kommen mit #2913“ |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:200-224` | Trip-Reiter: uebersicht (HubReiterflaeche > HubUebersicht), etappen (EditStagesSection/EditStagesPanelNew), wetter (shared/WetterTab), zustellung (ZustellungTab) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` 713/731/805/822 | Orte-Reiter: uebersicht, orte (inline Card+SortableList), wetter, zustellung; „Ort hinzufügen“-Knopf Z. 781-783 unten in der Card, ohne „+“ |
| `frontend/src/lib/components/organisms/zustellung-tab/ZustellungKopf.svelte:7-10` | bestehender Kopf Zustellung (eigene Kopie, `data-abschnitt="abschnittskopf"`, Testids `zustellung-titel`/`-erklaer`) |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:225-228, 312-329` | bestehender Kopf Wetter (eigene Kopie, Testids `wetter-tab-titel`/`-erklaer`) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Etappen-Reiter-Inhalt, kein Kopf |
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | Übersicht, kein Kopf |
| `frontend/src/lib/components/molecules/` + `index.ts` | Ablage für neuen Baustein (Molekül „Bereichskopf“) |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | Katalog; vorhanden: `wetter.kopf.titel/erklaerung`, `zustellung.kopf.titel/erklaer`, `listen.orte.hinzufuegen`; fehlt: Etappen, Orte, Übersicht |
| `docs/context/einstellungen_neu/elementliste.json` | `abschnittskopf`-Einträge für trip/wetter, trip/zustellung, trip/etappen, orte/orte (mit Knopf), orte/wetter, orte/zustellung; Übersicht fehlt; Titel auf `aktionen.reiter.*` gemappt; Etappen-Einträge `luecke:true` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | keine #3006-Einträge; #2968 (EN-Lücken Zustellung-Text), #3022 (orte.zustellung.laedt; Stand 2026-11-28 durch #3022 entfernt) |
| `frontend/e2e/elementliste_abgleich_logik.ts:602-603, 931, 946` | Abschnitt über `data-abschnitt` in `[data-seite="hub"]`, Reihenfolge-Prüfung |

## Existing Patterns
- Abschnitt-Haken: statisches `data-abschnitt="abschnittskopf"` am Kopf-Container.
- Zwei Kopien weichen bereits ab (Erklärsatz ink-2/13px vs ink-3/text-sm/68ch) → Vereinheitlichung auf Mockup-Werte.
- Tests: `node --test` mit SSR-Render (`wetter_tab_abschnitt_marker_2966.test.ts` Z. 86 prüft Kopftext) und statischer Strukturtest (`s3b2795_zustellung_struktur.test.ts`).

## Dependencies
- Upstream: Design-Tokens (`--g-size-22px`, `--g-size-13px`, `--g-ink-3`, `--g-rule-soft`, `--g-s-*`), i18n `$t`, Btn-Atom.
- Downstream: Elementlisten-Abgleich, bestehende Tests mit Testids `wetter-tab-titel`, `zustellung-titel` u. a., E2E-Specs der Reiter.

## Existing Specs
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md`, `feat_2795_s3b_teil1_zustellung.md`, `feat_2913_c2_seitenkopf.md`, `i18n_zt_kopf_sprache_3014.md`, `rework_2845_hub_reiterleiste.md`, `feat_2682_hub_uebersicht_geteilt.md`.

## Risks & Considerations
- Testids der bestehenden Köpfe erhalten (Bestandstests, E2E).
- Orte-Knopf wandert in den Kopf: `hub-orte-add` und Aufklapp-Panel müssen weiter funktionieren; Mockup-Text „+ Ort hinzufügen“ vs. Katalog „Ort hinzufügen“.
- Elementliste mappt Kopftitel auf `aktionen.reiter.*`; Zustellungs-Erklärsatz dort `i18n_key:null` → Elementliste ggf. nachziehen.
- Übersicht: keine Elementlisten-Einträge (#2969 Besitzer) — Kopf trotzdem bauen, Abgleich-Nachweis dort nicht möglich.
- Neuer Katalogschlüssel für „Etappen & Wegpunkte“ (mit #2794 entfallen) DE+EN.
- Keine parallele Arbeit an denselben Dateien: #3007 (Listen Etappen/Orte) berührt dieselben Reiter — offen, nicht belegt.

## Analysis

### Type
Feature (Teil von Epic #2913, Einstellungen neu)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/molecules/Bereichskopf.svelte` | CREATE | Design-System-Baustein: Props `titel`, `erklaerung`, `testid` (Präfix), `aktion?: Snippet`; Root `<div data-abschnitt="abschnittskopf">` mit h2, p, Aktions-Wrapper als **direkte Kinder** (CSS-Grid `1fr auto`, Aktion `grid-row:1/span 2; align-self:end`, mobil einspaltig). Mockup-Werte: h2 22px/600/-.01em/margin 0, p margin 2px 0 0, ink-3, 13px, 68ch, Linie rule-soft + padding-bottom 12px am Root |
| `frontend/src/lib/components/molecules/index.ts` | MODIFY | Export |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | `<header class="wt-kopf">` + CSS 312-329 → Baustein (testid `wetter-tab`) |
| `frontend/src/lib/components/organisms/zustellung-tab/ZustellungKopf.svelte` | DELETE | durch Baustein ersetzt (vorher `grep -rn ZustellungKopf`) |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | MODIFY | Z. ~109 Baustein (testid `zustellung`) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Etappen-Zweig: Kopf vor `{#if trip}` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Orte: SectionH „Verglichene Orte“ → Bereichskopf, Knopf `hub-orte-add` (gleicher Handler `toggleAddPanel`, Btn sm ghost) wandert in den Kopf, Footer-Div in der Card entfällt; Wetter/Zustellung: Kopf darf während Hydrations-Sperre (Z. 805-835) nicht fehlen |
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | MODIFY | Kopf oben, geteilt Trip/Orte |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | MODIFY | neue Schlüssel: Etappen-Titel/-Satz, Orte-Satz, Orte-Knopf „+ Ort hinzufügen“, Übersicht-Titel/-Satz (Namensraum nach Konvention) |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | ~22 `luecke:true`-Einträge (Zustellungs-Satz, Etappen, Orte-Satz/-Knopf, je Zustand) per Skript auf `i18n_key`/`text_en`/`luecke:false`, IDs unverändert; vorher prüfen, ob Generator/Konsistenztest existiert |
| `frontend/src/lib/components/molecules/__tests__/bereichskopf*.test.ts` | CREATE | SSR-Render DE/EN, Struktur (direkte Kinder, Reihenfolge), Aktion-Snippet |

### Scope Assessment
- Files: ~12-14
- Estimated LoC: +250/-60 (inkl. Test, ohne elementliste.json)
- Risk Level: MEDIUM (viele Reiter berührt, Bestandstests mit Testids und Struktur-Prüfung AC-28)

### Technical Approach
Ein Molekül `Bereichskopf` ersetzt beide vorhandenen Kopien und wird in allen acht Reitern (Trip/Orte × Übersicht, Etappen|Orte, Wetter, Zustellung) eingesetzt. `atoms/SectionH.svelte` wird NICHT umgebaut (anderes Muster, vielfach genutzt; Begründung im Molekül-Kommentar). Testid-Präfixe erhalten `wetter-tab-titel/-erklaer` und `zustellung-titel/-erklaer`. Grid statt verschachteltem Flex, damit `hub_kopf_c2_bildabgleich.test.ts` AC-28 (`titel.eltern` trägt Linie/Padding, erklaer Geschwister) und die Abgleich-Reihenfolge (`ordnung` 1 Titel, 2 Satz, 3 Knopf) halten. Zustellungs-Satz wechselt von ink-2 auf Mockup-ink-3. Der Abgleich bewertet Textgleichheit über `text_de`/`text_en` (luecke → `nicht_pruefbar`), daher elementliste.json nachziehen.

Reihenfolge: Katalog → Baustein+Test → Wetter → Zustellung (Kopie löschen) → Etappen, Orte (Knopf) → Übersicht → elementliste.json → Abgleich DE/EN alle Zustände.

### Tech-Lead-Entscheidungen (aus Mockup abgeleitet, keine PO-Frage)
- Orte: Mockup `viewOrte()` zeigt nur Kopf + Liste → SectionH „Verglichene Orte“ entfällt (ersetzt). Reihenfolge-Hinweis „hub-section-hint“ gehört zur Liste → bleibt unverändert, Zuordnung #3007 (Listen Etappen/Orte).
- Übersicht: Mockup-Satz „Unverändert: Stand, letzte Briefings, nächster Versand.“ wird übernommen (Mockup ist Soll); Elementlisten-Nachweis dort nicht möglich (#2969).
- Orte-Knopf: eigener Schlüssel mit „+“ (Mockup-Text); `listen.orte.hinzufuegen` auf weitere Nutzung prüfen.
- Hydrations-Sperre Orte (Wetter/Zustellung): Kopf muss auch während des Ladens stehen (Elementliste kennt `laedt` mit Kopf) → Kopf vor die Sperre; genau ein Marker je Reiter.

### Dependencies
Design-Tokens (`--g-size-22px`, `--g-size-13px`, `--g-ink-3`, `--g-rule-soft`), `$t`, Atom `Btn`. Downstream: Elementlisten-Abgleich, `hub_kopf_c2_bildabgleich.test.ts`, `wetter_tab_abschnitt_marker_2966.test.ts`, `s3b2795_zustellung_struktur.test.ts`, E2E `compare-hub-inline-edit.spec.ts` (Z. 131), `mobile-ux-messung.spec.ts` (Z. 470, AC-14 36px).

### Open Questions
- keine Produktfragen. Parallelität: #3007 berührt TripTabs/CompareTabs — vor Phase 6 auf Überschneidung prüfen.
