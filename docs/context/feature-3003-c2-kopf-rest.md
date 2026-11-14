# Context: feature-3003-c2-kopf-rest

## Request Summary
Issue #3003 (Teil von #2913, Scheibe c2 Seitenkopf): drei Rest-Abweichungen aus mockup-bildpruefer Runde 2
nach #2980 beheben — (1) Vorlage-Wähler zu hoch / Inhalt klebt oben, (2) Abstand Eyebrow „Vorlage" ↔ Wähler
am Handy zu klein, (3) Reiterleiste am Handy enger/linksbündig statt über volle Breite verteilt.
Abnahme: Staging-Aufnahme der acht Zustände (Reiter Wetter, Trip + Orte, DE + EN, 1280×900 + 390×844), Soll/Ist-Bild an den PO.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | Wähler: `<Btn size="tap">` (min 44 px) + `.wt-picker :global([data-slot='btn']) { align-items: baseline }` → Inhalt oben (Ursache Punkt 1). `.wt-picker-wrap` gap 6 px (= Mockup), `.wt-eyebrow`. |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Atom, Größe `tap` = Mindesthöhe `--g-tap-min` (44 px). Nicht ändern (global). |
| `frontend/src/lib/components/mobile/MTabBar.svelte` | Reiterleiste Trip UND Vergleich (TripTabs, CompareTabs). Mobile (<900 px): `flex-shrink:0`, padding `--g-s-2 --g-size-10px`, font `--g-text-sm` (13 px), Overflow-Band mit Fade-Maske, Scroll-Snap. Ursache Punkt 3. |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte` | Nutzer der MTabBar (geteilt, Trip/Vergleich-Teilung bleibt gewahrt). |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Soll: `.picker` inline-flex, align-items:center, padding 8px 12px, 15 px/600 (~37 px hoch); `.tab` padding 12px 16px, 13 px/500; `.tabs-in` width 100 %; Eyebrow-Wrap gap 6 px. Mobile-Media (760 px) ohne Tab-/Picker-Regeln. |
| `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts` | Staging-Abnahme (37 Tests); AC-26 prüft nur Rahmen/Grund/Schrift, nicht Höhe/vertikale Lage → neue Zusicherung hier. |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_bildabgleich.test.ts` | Kern-Test (node --test) zu #2980-Stilregeln, Vorbild für Kern-Zusicherungen. |
| `frontend/src/lib/components/mobile/__tests__/s3a2794_mtabbar_leiste_soll.test.ts` | Bestehende MTabBar-Soll-Tests (u. a. #2794 B2: vier DE-Reiter passen bei 360 px). |
| `docs/specs/modules/feat_2913_c2_seitenkopf.md` | c2-Spec (#2980-ACs, AC-17/18/26/27). |
| `docs/specs/modules/mobile_tab_leisten_mtabbar.md` | MTabBar-Spec (44-px-Tippfläche #2284, Band #1231). |

## Existing Patterns
- Stil-Overrides am Atom per `:global([data-slot='btn'])` im Komponenten-Scope (VorlageKarte), Atom bleibt unverändert.
- Mobile-Regeln in MTabBar unter `@media (max-width: 899px)`; Kommentare mit Issue/AC-Bezug.
- Bildabgleich-Abnahme (ADR-0112): Staging-Spec nimmt die acht Zustände auf, mockup-bildpruefer vergleicht; nach Runde 2 keine dritte Runde, Rest → Folge-Issue.

## Dependencies
- Upstream: Btn-Atom (Größe `tap`), Design-Token (`--g-text-*`, `--g-s-*`, `--g-tap-min`).
- Downstream: MTabBar in Trip- und Vergleich-Hub (beide Reiterleisten ändern sich gleich — gewollt, Code-Teilung). VorlageKarte nur im Wetter-Reiter (beide Kontexte).

## Existing Specs
- `docs/specs/modules/feat_2913_c2_seitenkopf.md`
- `docs/specs/modules/mobile_tab_leisten_mtabbar.md`

## Risks & Considerations
- Handy: 44-px-Tippfläche bleibt Pflicht (#2284, K-5) — Wähler am Handy 44 px, aber Inhalt mittig; Desktop ~37 px wie Mockup (Btn `tap` erzwingt 44 px auch am Desktop → Override nur am Desktop oder andere Btn-Größe).
- Reiter über volle Breite: EN-Reiternamen länger; bei 360 px dürfen vier Reiter nicht überlaufen (bestehender Test #2794 B2), Band/Scroll-Verhalten als Rückfall bei Überbreite erhalten (flex:1 mit min-content statt fixer Verteilung).
- Punkt 2 (Eyebrow-Abstand): Gap ist bereits 6 px wie Mockup — Ursache in Analyse am Staging-Bild messen (evtl. Folge der Baseline-Ausrichtung / Kartenumbruch am Handy).
- „Größere Schrift" am Handy im Mockup: Token sind gleich (13 px) — in der Analyse gegen Aufnahme prüfen, ob nur Breite/Padding wirkt; keine Schrift unter 11 px (#2601).
- Nebenbefunde aus Runde 2 mit anderen Besitzern (#2796, #2981, #2954, App-Rahmen) bleiben außen vor.

## Analysis

### Type
Feature (Bildabgleich-Rest, reine Darstellung, Frontend-only)

### Befunde (gemessen am Code, 2026-11-14)
1. **Wähler (Punkt 1):** `Btn size="tap"` = `padding: 0 14px; min-height: 44px` (app.css:516). VorlageKarte überschreibt
   `align-items: baseline` → in einem 44-px-Flex-Knopf ohne Polster oben sitzt der Text direkt unter dem Rahmen.
   Mockup `.picker`: `align-items:center; padding:8px 12px` → ~38 px hoch, Text mittig.
2. **Eyebrow-Abstand (Punkt 2):** Kein eigener Fehler. Gap ist 6 px wie im Mockup; sichtbar ist aber
   6 px + Rahmen + Polster bis zur Schrift. Mockup: 6 + 1 + 8 = 15 px bis zum Text; Staging: 6 + 1 + 0 = 7 px,
   weil der Text oben klebt. **Mittig-Ausrichtung behebt Punkt 2 mit** (44 px, Text ~20 px → ~12 px Luft oben).
3. **Reiterleiste Handy (Punkt 3):** Mockup `.tab` 13 px / `padding:12px 16px`, vier Reiter füllen bei 390 px
   die Breite (~380 px Inhalt). Staging Handy: 13 px (`--g-text-sm` = 13 px, gleiche Schriftgröße; der Eindruck
   „größer" entsteht nur aus mehr Luft), `padding: 8px 10px`, `flex-shrink:0` → ~330 px, linksbündig, Lücke rechts.
   16 px Polster würde bei 360 px überlaufen (#2794 B2 verlangt: vier DE-Reiter passen bei 360 px).

### Technical Approach (Empfehlung)
- **Wähler:** `.wt-picker :global([data-slot='btn'])` → `align-items: center` statt `baseline`; Polster seitlich
  12 px wie Mockup. **Höhe bleibt 44 px auf allen Breiten:** Die bestehende Design-Prüfung AC-40 (#2794,
  `s3a2794-teil3-design.spec.ts`) verlangt Touch-Ziele ≥ 44 px im Wetter-Reiter auch am Desktop (K-5).
  Ein 38-px-Wähler am Desktop bräche diese freigegebene Regel; Tech-Lead-Entscheid: Tippfläche geht vor
  den 6 px Höhe, analog zur bewussten Abweichung „Test schicken" (Kontrast). Rest-Abweichung (44 statt ~38 px)
  wird im Soll/Ist-Bild als bewusste Abweichung genannt, nicht als offener Punkt.
- **Reiter Handy:** in MTabBar mobil `flex-shrink:0` → `flex: 1 0 auto` + `justify-content: center`;
  Polster 10 px bleibt Mindestmaß. Reiter wachsen bei Platz auf volle Breite (wie Mockup), bei Überbreite (EN,
  360 px, viele Reiter) bleibt das Band mit Scroll/Fade unverändert. Gilt für Trip UND Vergleich (geteilte
  Komponente, gewollt). Desktop unverändert (nicht beanstandet). Schriftgröße bleibt 13 px (= Mockup).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | Wähler: center statt baseline, Polster 12 px |
| `frontend/src/lib/components/mobile/MTabBar.svelte` | MODIFY | mobil: Reiter `flex: 1 0 auto`, zentrierter Inhalt |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_bildabgleich.test.ts` | MODIFY | Kern-Zusicherungen (Regeln vorhanden) |
| `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts` | MODIFY | gemessen: Inhalt mittig (oben≈unten ±2 px), Wähler ≥44 px; Reiter Handy füllen Leistenbreite (rechte Kante letzter Reiter ≈ Leistenende ±2 px) bei 390 px, DE+EN, Trip+Orte; kein Überlauf bei 360 px DE |
| `docs/specs/modules/feat_2913_c2_seitenkopf.md` | MODIFY | neue ACs (Nachtrag #3003) |

### Scope Assessment
- Files: 5 · Estimated LoC: +60/-5 (davon ~50 Tests) · Risk Level: LOW
- Risiko: Reiter-Verteilung ändert beide Hubs (gewollt); bestehende Tests #2794 B2 (360 px) und AC-40 (44 px) bleiben Wächter.

### Dependencies
Btn-Atom unverändert; Token `--g-text-sm`, `--g-size-10px`, `--g-tap-min`. Abnahme: acht Staging-Zustände + mockup-bildpruefer, Soll/Ist-Bild an den PO.

### Open Questions
- keine (44-px-Höhe am Desktop per Tech-Lead-Entscheid nach K-5/AC-40; in der Spec sichtbar zur Freigabe)
