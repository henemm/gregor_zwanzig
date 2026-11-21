---
entity_id: feat_3203_metrikzeilen_mockup
type: feature
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: feat-3203-metrikzeilen-mockup
tags: [einstellungen-neu, reiter-wetter, elementlisten-abgleich, mockup, "#3203", "#2913"]
---

# Reiter Wetter: Metrik-Zeilen nach Mockup Fassung 4 (Abgleich korrigieren)

## Approval

- [ ] Approved

## Purpose

Die 19 Besitzer-Einträge `#3203` (Epic #2913) sind überwiegend ein Messartefakt: Der Elementlisten-Abgleich überspringt alles unter `aria-hidden="true"`, obwohl Skala-Zahlen, Gewitter-Stufenwörter und der Trennpunkt „·“ im Reiter Wetter sichtbar sind. Die Spec korrigiert den Abgleich (Sichtbarkeit statt A11y-Attribut), gleicht den Vorboten-Satz im Mockup an den Live-Stand an und räumt die Besitzer-Einträge ab.

## Source

- **File:** `frontend/e2e/elementliste-abgleich.staging.spec.ts` (Z. 124-140 `sichtbareTexte`) und `frontend/e2e/elementliste_abgleich_logik.ts`
- **Identifier:** `sichtbareTexte` (Filter auf `[aria-hidden]`) und die neue reine Funktion zur Sichtbarkeitsprüfung

> Schicht: ausschließlich Frontend-Testwerkzeug, Mockup und Besitzerliste; kein Go-API-/Python-Core-Code, keine Produktkomponente.
> Trip/Orts-Vergleich: `MetrikZeile` und `AmpelLeiste` sind bereits geteilt, der Abgleich-Fix gilt für beide Kontexte ohne Kontext-Zweig. Keine Nutzerdaten, keine Kanalinhalte betroffen.

## Scope

**Im Scope**
- Abgleich: sichtbarer Text unter `aria-hidden` zählt; `display:none`/`visibility:hidden` und reine SVG/Icons zählen nicht.
- Mockup `mockup-hub-fassung4.html` (Z. 428): Vorboten-Satz nur für Metriken mit `m[2].includes('Vorbote')`; `elementliste.json` deterministisch neu erzeugen (`scripts/elementliste_aus_mockup.ts`).
- Besitzerliste: 19 Einträge `#3203` abräumen, „:00“ als begründete Ausnahme; Zählwächter `tests/test_2913_c2_besitzerliste.py` (`"#3203": 0`).
- Messung vorher/nachher im Staging-Abgleich aller Reiter.

**Nicht im Scope**
- `aria-hidden` im Produkt (`MetrikZeile.svelte`, `AmpelLeiste.svelte`) bleibt unverändert (Screenreader-Ausgabe).
- Keine neuen Farben/Token, keine Katalog-Änderung (DE/EN vollständig), kein Backend.
- Vorbote-Satz im Produkt (`ampelModell.ts`) bleibt wie live.

## Estimated Scope

- **LoC:** ca. +120/-60 (ohne generierte Elementliste)
- **Files:** 7 (Abgleich-Spec, Abgleich-Logik, neuer Logik-Test, Mockup, Besitzer-JSON, Zählwächter, generierte `elementliste.json`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/elementliste_abgleich_logik.ts` | module | Reine Abgleich-Logik, hier um Sichtbarkeitsregel erweitert |
| `scripts/elementliste_aus_mockup.ts` | script | Erzeugt `elementliste.json` deterministisch aus dem Mockup |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | data | Besitzer-Einträge und `ausnahmen` mit `spec` |
| `tests/test_2913_c2_besitzerliste.py` | test | Zählwächter je Besitzer |
| Staging + Prüfkonto-Seed (`scripts/staging_pruefkonto_mockupdaten.py`) | system | Abgleich-Lauf vorher/nachher |
| `feat_2913_scheibe_c_wetter_rest.md` (Punkt 3/AC-5) | spec | Begründung der Ausnahme „:00“ (Stundenraster) |
| `feat_3151_pruefkonto_abgleich.md`, `feat_2913_abgleich_ganzseite.md` | spec | Abgleich-Vorgänger |

## Implementation Details

1. **Sichtbarkeitsregel (reine Funktion, node --test):** Ein Textknoten zählt, wenn kein Vorfahr `display:none`, `visibility:hidden` oder `hidden` trägt, nicht in `svg`/Icon-Elementen liegt und echten Text hat. `aria-hidden` wird nicht mehr ausgewertet. `sichtbareTexte` (Spec Z. 134) ruft diese Funktion statt des `[aria-hidden]`-Filters auf.
2. **Mockup:** Z. 428 auf `m[2].includes('Vorbote')`; Tiefe Wolken (Trip) und Sonnenstunden (Orte) zeigen dann „Kein Alarm. Die Farbe erscheint nur im Briefing.“. `elementliste.json` per Skript neu erzeugen, keine Handpflege.
3. **Besitzerliste:** 2 Abschnitt-Einträge `metriken` und 14 Grün-Einträge sowie die 2 „Kein Alarm“-Einträge (Orte DE/EN) abräumen, „:00“ (Index 147) als `ausnahmen` mit `spec: feat_2913_scheibe_c_wetter_rest`. Zählwächter auf `"#3203": 0` mit Kommentar wie bei #3202.
4. **Wirkung messen:** Abgleich aller Reiter (DE+EN) vor der Änderung sichern, danach erneut laufen lassen und vergleichen.

## Expected Behavior

- **Input:** Staging-Seite Reiter Wetter (Trip und Orts-Vergleich), Prüfkonto-Seed.
- **Output:** Abgleich meldet für Skala-Zahlen (-10/-15), Gewitter-Stufen keins/mittel/hoch, „· grün: …“ und die Alarm-Satz-Reihenfolge keine Abweichung mehr; keine herrenlosen Besitzer-Einträge.
- **Side effects:** Wechsel abweichend→gefunden in anderen Reitern ist erlaubt; neue Abweichungen außerhalb `#3203` sind es nicht. Screenreader-Ausgabe unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `frontend/e2e/elementliste_abgleich_logik.test.ts` (node --test), DOM-Fixture: Text unter `aria-hidden="true"` wird gezählt (rot vor der Änderung).
- [ ] Gleiches Fixture: Text unter `display:none` und `visibility:hidden` wird nicht gezählt.
- [ ] Gleiches Fixture: reines SVG/Icon unter `aria-hidden` liefert keinen Text.
- [ ] Gleiches Fixture: „·“ neben „grün: 2 bis 27 °C“ ergibt den zusammenhängenden Text „· grün: 2 bis 27 °C“.
- [ ] Produkt-Test (bestehende Svelte-Tests): `aria-hidden` bleibt an `wt-marken` und am „·“ (Screenreader-Ausgabe unverändert).
- [ ] `tests/test_2913_c2_besitzerliste.py`: `"#3203": 0`, keine herrenlosen Einträge, `ausnahmen` enthält „:00“ mit `spec`.
- [ ] Staging-Abgleich aller Reiter vorher/nachher: Diff enthält nur Einträge `#3203` (abweichend→gefunden).

## Acceptance Criteria

- **AC-1:** Given Reiter Wetter im Trip mit Skala unter einer Metrik (Marken mit `aria-hidden`) / When der Elementlisten-Abgleich die Seite liest / Then zählen Skala-Zahlen (z. B. -10, -15) und die Gewitter-Stufen keins/mittel/hoch als sichtbarer Text und werden gefunden.
  - Test: Abgleich gegen Staging DE meldet für diese Elemente „gefunden“; Logik-Test mit Fixture belegt die Regel.

- **AC-2:** Given Reiter Wetter im Orts-Vergleich mit derselben Metrik-Zeile / When der Abgleich läuft / Then wird der Trennpunkt mit „grün: 2 bis 27 °C“ als ein Text erkannt, und die Alarm-Satz-Reihenfolge meldet keine Abweichung.
  - Test: Staging-Abgleich Orte DE zeigt für Grünbereich und Reihenfolge keinen `#3203`-Eintrag mehr.

- **AC-3:** Given ein Element mit `display:none`, `visibility:hidden` oder ein reines Icon/SVG unter `aria-hidden` / When die Abgleich-Logik Texte sammelt / Then wird es nicht gezählt und erzeugt kein Rauschen.
  - Test: node --test mit DOM-Fixture, drei Fälle (versteckt, unsichtbar, Icon).

- **AC-4:** Given Reiter Wetter in Deutsch und Englisch, Trip und Orts-Vergleich / When der Abgleich beider Sprachen läuft / Then meldet er keinen Eintrag mit Besitzer `#3203`, und der Zählwächter steht auf 0.
  - Test: Staging-Abgleich DE+EN je Kontext; `tests/test_2913_c2_besitzerliste.py` grün.

- **AC-5:** Given Tiefe Wolken (Trip) und Sonnenstunden (Orte), die keine Vorboten sind / When der Nutzer die Zeile liest / Then steht dort „Kein Alarm. Die Farbe erscheint nur im Briefing.“ (DE) bzw. der englische Katalogtext, und das Mockup Fassung 4 zeigt dasselbe.
  - Test: Staging-Abgleich; Elementliste ist per Skript neu erzeugt und stimmt mit dem Mockup überein.

- **AC-6:** Given ein Screenreader-Nutzer im Reiter Wetter (Trip und Orte) / When die Zeile vorgelesen wird / Then bleiben Skala-Marken und Trennpunkt für Hilfstechnik verborgen wie bisher.
  - Test: Komponenten-Test prüft `aria-hidden` an Marken und „·“ unverändert.

- **AC-7:** Given alle Reiter der Einstellungen im Staging-Abgleich / When vorher und nachher verglichen wird / Then gibt es keine neue Abweichung außerhalb der `#3203`-Einträge.
  - Test: Differenzlauf beider Berichte; erlaubt ist nur der Wechsel abweichend→gefunden.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`), Tests rot vor Umsetzung, dann grün
- [ ] Abgleich-Bericht vorher/nachher aller Reiter DE+EN als Artefakt abgelegt
- [ ] Mutationsprobe: Sichtbarkeitsregel auf alten `aria-hidden`-Filter zurückgesetzt röntet den Logik-Test
- [ ] Besitzerliste und Zählwächter angepasst, PR mit allen 6 CI-Checks grün, Deploy, Selftest
- [ ] Bildprüfung Reiter Wetter (ADR-0112); #2867 gegen Code prüfen und bei Erledigung schließen

## Known Limitations

- „:00“ im Tagesfenster (Stundenraster mit fester Minute 00) weicht bewusst vom Mockup „06:00“ ab (Ausnahme mit Spec-Verweis).
- Die Sichtbarkeitsregel gilt für alle Reiter; sie kann zuvor verdeckte, echte Abweichungen anderer Besitzer sichtbar machen (nur Verbesserung abweichend→gefunden ist erlaubt, sonst Nachbesserung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Ausführung bestehender Entscheidungen (ADR-0112 Mockup-getriebene Scheiben mit Bildprüfung, ADR-0104 Texte nur über Katalog, kein neuer Text); die Messregel des Abgleichs ist Testwerkzeug und ändert keine Produktentscheidung.

## Changelog

- 2026-11-21: Initial spec created (Entscheidungen: Vorboten-Satz bleibt live und Mockup wird angeglichen; Abgleich statt Produkt korrigieren; „:00“ als Ausnahme)
