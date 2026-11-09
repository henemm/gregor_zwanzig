---
entity_id: rework_2845_hub_reiterleiste
type: feature
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
workflow: rework-2845-hub-reiterleiste
tags: [epic-2345, trip-compare-teilung, frontend-only, hub-reiterleiste, shared, paritaet]
---

# Hub-Reiterleiste: eine Optik für Trip und Ortsvergleich (Issue #2845, Teil A, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Die Reiterleiste der Detailseite (Übersicht, Orte bzw. Etappen, Wetter-Metriken, Zustellung, Alarme) sieht auf dem Computer bei Trip und Ortsvergleich verschieden aus. Beim Trip sind die nicht gewählten Reiter dunkel, etwas größer und mit einer dünnen Linie darunter. Beim Ortsvergleich sind sie grau, 13 Pixel klein, enger gesetzt, ohne Linie und rund 6 Pixel höher. Beide benutzen schon denselben Baustein (`MTabBar`). Die Abweichung ist ein bewusst eingebauter Schalter `size` (`md` für den Trip, `sm` für den Ortsvergleich), den die Ursprungsspec `mobile_tab_leisten_mtabbar.md` (Iteration 2) eingeführt hat, um die damalige Compare-Optik zu halten.

Das widerspricht der PO-Vorgabe „Trip und Ortsvergleich teilen ihren Code" (ADR-0097, Pendant-Sperre #1170): Ein Schalter, der nur dazu dient, zwei Optiken zu erhalten, ist ein eingebautes Pendant. Zusätzlich verliert die graue Variante gegen das Leitprinzip „Hoher Kontrast = Lesbarkeit" (WCAG-AA): inaktive Reiter in `--g-ink-3` sind schwächer lesbar als in `--g-ink`.

**Entscheidung (Tech Lead, am Code gemessen):** Der `size`-Prop von `MTabBar` wird **vollständig entfernt**, samt der `.mtabbar.sm`-Regeln und der Kommentare dazu. Es gibt **keinen Ersatz-Prop**, damit sich die Leiste nie wieder je Seite umbiegen lässt. Die bisherige Trip-Optik (`md`) wird die Einheitsoptik: inaktive Reiter in `--g-ink`, Schrift `0.875rem`, 1 Pixel Linie unter der Leiste in `--g-ink-faint`, aktiver Reiter mit Accent-Unterstrich. Der Zähler-Badge bleibt neutral (AC-10 aus #2837 S1, ADR-0110). Mobil (unter 900 Pixel Breite) ändert sich nichts, dort sind beide Seiten schon gleich.

Sichtbare Folge für den Nutzer: Am Computer wird die Leiste des Ortsvergleichs etwa 6 Pixel höher, die inaktiven Reiter sind dunkler und eine Linie läuft unter der ganzen Leiste. Beim Trip ändert sich nichts.

**Außerhalb (Non-Goal):** Der Nebenbefund aus dem Issue (Trip zeigt „So 06:00 (CEST)", Ortsvergleich „So 06:00 (CET)" für denselben Sonntag 8.11.2026) ist kein Leisten-Thema, berührt den Python-Core und wird als **eigenes Bug-Issue** geführt. Diese Spec enthält dazu keine ACs. Siehe Known Limitations.

## Source

- **Geändert (Pfade relativ zum Repo-Wurzelverzeichnis):**
  - `frontend/src/lib/components/mobile/MTabBar.svelte`: Prop `size` samt Typ in `Props` und Destrukturierung entfernen, `class:sm={size === 'sm'}` am Wurzelelement entfernen, die Regeln `.mtabbar.sm …` (Block „size="sm" (Compare) …") entfernen, Kommentar im Props-Block (`/** Desktop-Optik: 'md' … 'sm' … */`) entfernen, Kommentar im Kopf („in jeder Breite und Größe") und Badge-Kommentar („nicht über `size` gesteuert") auf die neue Lage anpassen.
  - `frontend/src/lib/components/compare/CompareTabs.svelte`: Aufruf `<MTabBar … size="sm" />` ohne `size`; Kommentar vor dem Aufruf („size="sm" haelt die Compare-Optik (13px, 12/16px) …") streichen.
  - `frontend/src/lib/components/mobile/__tests__/mtabbar_zaehler_neutral.test.ts`: Die Kaskadenrechnung `badgeStil(size, mobil)` und die Fälle je `size` ('md'/'sm') entfallen; die Zusicherungen (Badge neutral, Accent bleibt der Unterstrich des aktiven Reiters) bleiben, jetzt ohne Variantenachse. Neu in dieser Datei: kein Selektor mit Varianten-Klasse am `.mtabbar`-Kopf mehr (Wächter gegen einen Rückfall).
  - `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts`: Der Fall „die Reiterleisten unterscheiden sich höchstens in der Größe `sm`" (Filter `c !== 'sm'`) wird zu „die Reiterleisten tragen bei Trip und Vergleich dieselben Klassen".
  - `frontend/e2e/hub-tab-bar.spec.ts`: Im Zweig `if (kind === 'vergleich') { … toBe('13px') }` (HT-8, Altfall „13-px-Trigger") entfällt der Kind-Zweig; stattdessen neuer Paritätsfall HT-14 (siehe AC-1, AC-2, AC-7). Der Kopfkommentar „HT-8 (Größe je Art …)" wird angepasst.
  - `docs/specs/modules/mobile_tab_leisten_mtabbar.md`: Changelog-Vermerk „Iteration 2 (`size="sm"`) zurückgenommen durch #2845"; im Abschnitt „Architektur-Entscheidung" der Satz „mit Varianten-Prop (`underline` / `buttons`)" bleibt unberührt (dort ist ein anderer, nie gebauter Prop gemeint) und bekommt nur den Verweis auf diese Spec.
- **Geprüft, keine Änderung nötig:** `frontend/src/lib/components/trip-detail/TripTabs.svelte` (ruft `MTabBar` ohne `size`), `frontend/src/lib/components/compare/__tests__/compare_mobile_shared_hub.test.ts` und `frontend/src/routes/compare/__tests__/issue_582_compare_design_fidelity.test.ts` (prüfen nur, dass `<MTabBar` gerendert wird, die Media-Query und `border-bottom: 2px solid var(--g-accent)`; keine `size`-/13px-Kopplung gefunden), `frontend/src/routes/compare/__tests__/compare_list_mobile_chrome.test.ts` (`size="sm"` dort gehört zur Komponente `Stat`, nicht zu `MTabBar`).
- **Unverändert:** Reiter-Daten in `shared/subscriptionTabs.ts`, Test-IDs, `data-slot`-Vertrag, Mobil-CSS (`@media (max-width: 899px)`).

> **Schicht-Hinweis:** ausschließlich **Frontend** (SvelteKit). Kein Go-, kein Python-Code, kein Datenmodell, kein Endpunkt.

> **Trip/Ortsvergleich-Teilung:** erfüllt und gestärkt. Beide Seiten rufen denselben Baustein ohne jede Variante; es entsteht keine neue Komponente, die Pendant-Sperre löst nicht aus.
> **Mandantentrennung:** nicht betroffen (reine Darstellung, kein datenbewegender Endpunkt, kein `user_id`-Bezug).
> **Kanäle:** nicht betroffen (kein Briefing- oder Alarm-Inhalt, kein Kanal-Pfad).

## Scope

Nur die Desktop-Optik der Hub-Reiterleiste (Frontend). Der Zeitzonen-Nebenbefund (CEST/CET) liegt in Issue #2869 und ist nicht Teil dieser Spec.

## Estimated Scope

- **LoC:** ca. +30 / -50 (netto kleiner, vor allem entfernte CSS-Regeln und Testvarianten)
- **Files:** 6 bis 7 (MTabBar, CompareTabs, zwei Unit-Tests, ein E2E, Ursprungsspec)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `mobile/MTabBar.svelte` | Baustein | gemeinsame Reiterleiste, hier wird `size` entfernt |
| `trip-detail/TripTabs.svelte` | Konsument | Referenz-Optik, bleibt unverändert |
| `compare/CompareTabs.svelte` | Konsument | ruft künftig ohne `size` |
| `shared/subscriptionTabs.ts` | Reiter-Daten | unverändert |
| CSS-Variablen `--g-ink`, `--g-ink-3`, `--g-ink-faint`, `--g-accent`, `--g-paper-deep` | Design-Tokens | Einheitsoptik und neutraler Zähler |
| `docs/specs/modules/rework_2837_s1_hub_kopf.md` (AC-10) | Vorgänger-Spec | Zähler neutral bleibt |

## Implementation Details

1. `MTabBar.svelte`: `size` aus `Props`, aus `$props()`-Destrukturierung und aus dem Markup (`class:sm`) entfernen. Der Block `.mtabbar.sm …` (drei Regeln) fällt komplett. Die Basisregeln (`.mtabbar`, `[data-slot='segmented-item']`, aktiv) bleiben unverändert und sind damit die Einheitsoptik. Die Mobil-Media-Query bleibt unangetastet.
2. `CompareTabs.svelte`: `size="sm"` und den zugehörigen Kommentarsatz entfernen.
3. Tests mitziehen (siehe Source). Der Unit-Test `mtabbar_zaehler_neutral.test.ts` liest weiter mit dem echten Svelte-Compiler die komponenten-eigenen Regeln; dort wird nur die Variantenachse gestrichen.
4. E2E: Neuer Fall HT-14 in `hub-tab-bar.spec.ts` für beide Arten bei 1440 × 900 und bei 390 × 844. Er vergleicht die zwei Seiten gegeneinander (Trip gegen Vergleich) statt gegen Festwerte, damit eine künftige gemeinsame Änderung der Einheitsoptik ihn nicht bricht; nur Kontrast und Accent-Farbe sind gegen feste Schwellen bzw. Werte geprüft.
5. Pflicht-Mutationen für die Gegenprobe (String-Ersetzung mit externer Sicherungskopie): (a) in `MTabBar.svelte` eine Varianten-Regel für einen Konsumenten wieder einführen (z. B. `.mtabbar.compact`-Regel plus Klasse), (b) inaktive Reiter wieder auf `var(--g-ink-3)`, (c) Linie `border-bottom` am Container entfernen. Jede muss mindestens einen der ACs rot machen.

## Expected Behavior

- **Input:** Hub-Seite von Trip oder Ortsvergleich (Computer ab 900 Pixel Breite oder Handy).
- **Output:** Computer: identische Reiterleiste (Schrift, Farbe der inaktiven Reiter, Linie unter der Leiste, Höhe, Accent-Unterstrich am aktiven Reiter, neutraler Zähler). Handy: unverändert (Pill-Band mit Fade).
- **Side effects:** keine; Reiter-Wechsel, Deep-Link, Tastatur und URL-Sync bleiben bei den Konsumenten.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Hub und ein Ortsvergleichs-Hub, jeweils mit fünf Reitern, geöffnet bei 1440 × 900 Pixel / When beide Seiten nacheinander geladen und die Reiter vermessen werden / Then haben ein nicht gewählter Reiter beider Seiten dieselbe Schriftgröße (0.875rem = 14 px), dieselbe Schriftfarbe (`--g-ink`, rgb(26, 26, 24)) und dieselbe Polsterung, und die Leiste beider Seiten trägt dieselbe 1-Pixel-Linie in `--g-ink-faint` am unteren Rand.
  - Test: Playwright `frontend/e2e/hub-tab-bar.spec.ts` HT-14, je Art `getComputedStyle` auf `[data-slot="segmented-item"][data-state="inactive"]` (fontSize, color, paddingTop/-Left) und auf `[data-slot="segmented"]` (borderBottomWidth, borderBottomColor); Gleichheit Trip gegen Vergleich.

- **AC-2:** Given dieselben zwei Hubs bei 1440 × 900 Pixel / When die Höhe der Reiterleiste (Container) und eines Reiters per Layoutmessung ermittelt wird / Then ist die Höhendifferenz zwischen Trip-Leiste und Vergleichs-Leiste **0 Pixel** (vorher rund 6 Pixel), und ebenso die Höhendifferenz der einzelnen Reiter.
  - Test: Playwright HT-14, `boundingBox().height` von `[data-testid="trip-detail-tab-list"] bzw. [data-testid="compare-detail-tab-list"] .mtabbar` und des ersten Reiters je Art; `expect(hoeheVergleich).toBe(hoeheTrip)` (Toleranz 0).

- **AC-3:** Given ein Hub (Trip oder Ortsvergleich) bei 390 × 844 Pixel / When die Seite geladen wird / Then ist die Leiste unverändert zum bisherigen Stand: Pill-Reiter mit mindestens 44 Pixel Tippfläche, horizontales Band, aktiver Reiter vollständig sichtbar, Pfeiltasten wechseln den Reiter, und Trip und Vergleich sehen gleich aus (Schriftgröße, Reiterhöhe).
  - Test: bestehende Playwright-Fälle HT-1 bis HT-6 und HT-9 in `hub-tab-bar.spec.ts` laufen unverändert grün; HT-14 ergänzt bei 390 px den Vergleich Trip gegen Vergleich (fontSize, Reiterhöhe gleich).

- **AC-4:** Given ein Hub mit drei Punkten bzw. Orten (Zähler am Reiter „Orte"/„Etappen" sichtbar) / When die Seite bei 1440 und bei 390 Pixel Breite betrachtet wird / Then ist der Zähler in beiden Arten neutral (Grund `--g-paper-deep` = rgb(236, 234, 217), Schrift `--g-ink-3` = rgb(107, 103, 92)), nie Accent-gefüllt, und das Kontrastverhältnis Schrift zu Grund beträgt mindestens 4,5:1.
  - Test: bestehendes Playwright HT-8 (`hub-tab-bar.spec.ts`, ohne den entfernten 13-px-Kind-Zweig); Unit `mtabbar_zaehler_neutral.test.ts` rechnet dieselbe Zusicherung mit dem echten Svelte-Compiler an der Kaskade nach (Desktop und `max-width: 899px`).

- **AC-5:** Given Trip-Hub und Ortsvergleichs-Hub bei 1440 Pixel Breite / When der aktive Reiter betrachtet wird / Then trägt er in beiden Arten einen Unterstrich in Accent-Farbe (`--g-accent`, rgb(196, 90, 42)), einen transparenten Hintergrund und die gleiche Schriftstärke wie der aktive Reiter der jeweils anderen Seite; inaktive Reiter haben keinen Accent-Unterstrich.
  - Test: Playwright HT-8/HT-14, `getComputedStyle(aktiverReiter).borderBottomColor` gleich rgb(196, 90, 42), `backgroundColor` gleich rgba(0, 0, 0, 0), `fontWeight` Trip gegen Vergleich gleich; inaktiver Reiter: `borderBottomColor` ungleich Accent.

- **AC-6:** Given beide Hubs bei 1440 Pixel Breite / When ein Nutzer einen anderen Reiter mit der Maus anklickt und danach mit der Pfeiltaste (rechts/links) weiterschaltet / Then wechselt der Inhalt wie bisher, die Seite lädt nicht neu, der gewählte Reiter ist `aria-selected="true"` mit `tabindex=0`, die übrigen `tabindex=-1`, und die Reiter sind weiter über `data-slot="segmented"`, `data-slot="segmented-item"` und die bisherigen `data-testid` erreichbar.
  - Test: bestehende Playwright-Fälle HT-4, HT-11 und HT-12 in `hub-tab-bar.spec.ts` (Rollen, Pfeiltaste, Reiter A → B → A) laufen unverändert grün; kein bestehender Selektor wird geändert.

- **AC-7:** Given beide Hubs bei 1440 Pixel Breite / When die Leiste nach der Umstellung gerendert wird / Then tragen Trip- und Vergleichs-Leiste dieselbe Klassenliste am Leisten-Element (`class` von `[data-slot="segmented"]`, also dieselbe Komponente ohne Variante), und kein Reiter hat eine abweichende Optik gegenüber der Referenz aus AC-1. Es gibt keinen Schalter, über den ein Konsument die Desktop-Optik verändern kann.
  - Test: Playwright HT-14 vergleicht `className` von `.mtabbar` Trip gegen Vergleich (gleich) und AC-1/AC-2 beweisen die gleiche Wirkung; Unit `hub_kopf_seiten_paritaet.test.ts` (SSR-Markup beider Seiten, Klassenliste der Leiste ohne Filter gleich). Zusätzlich Unit `mtabbar_zaehler_neutral.test.ts` über den Svelte-Compiler-AST (kein Dateiinhalt-Text-Match): kein Selektor der `<style>`-Regeln trägt eine Klasse am `.mtabbar`-Kopf (Varianten-Klasse), und `parse(...).instance` deklariert in `Props` kein Feld `size` (AST-Prüfung der Typdeklaration, Verhaltensnachweis ist AC-1/2/7 im Browser).

- **AC-8:** Given der Trip-Hub und der Ortsvergleichs-Hub bei 1440 Pixel Breite / When die Farbe der inaktiven Reiter gegen den Seitengrund gemessen wird / Then beträgt das Kontrastverhältnis in beiden Arten mindestens 4,5:1 (WCAG-AA; `--g-ink` auf Papier rund 15:1; der bisherige graue Vergleichs-Reiter `--g-ink-3` wird nicht mehr verwendet).
  - Test: Playwright HT-14, `kontrastVerhaeltnis(color, backgroundColor des Seitenhintergrunds)` aus `frontend/e2e/helpers` je Art; `toBeGreaterThanOrEqual(4.5)`.

## Test Plan

- **Unit (Compiler-AST):** `mtabbar_zaehler_neutral.test.ts` ohne Größenachse; Zähler bleibt neutral (AC-4).
- **Unit:** `hub_kopf_seiten_paritaet.test.ts` — Trip und Vergleich tragen dieselben Klassen an der Leiste (AC-7).
- **E2E (Playwright):** `hub-tab-bar.spec.ts` HT-14 vergleicht Trip gegen Vergleich bei 1440 px und 390 px (Schrift, Farbe inaktiv, Linie, Höhe 0 px Differenz, Kontrast ≥ 4,5:1); HT-1 bis HT-9, HT-11, HT-12 laufen unverändert (AC-1 bis AC-8).
- **Pflicht-Mutation:** `size="sm"` bzw. `.mtabbar.sm`-Regeln wieder einführen ⇒ mindestens HT-14 rot.

## Definition of Done

- AC-1 bis AC-8 erfüllt, jedes mit grünem Test aus dem Test Plan; angepasste Tests umgedreht, keiner gelöscht.
- Adversary-Verdict VERIFIED (Mutation aus dem Test Plan wird gefangen).
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0.
- Issue #2845 erst schließen, wenn auch der Nebenbefund (#2869) geklärt ist.

## Known Limitations

- **Zeitzonen-Nebenbefund CEST/CET (ausdrücklich nicht Teil dieser Spec):** Im Hub „Nächster Versand" zeigt der Trip `So 06:00 (CEST)`, der Ortsvergleich `So 06:00 (CET)` für denselben Sonntag 8.11.2026 (Winterzeit). Das Kürzel kommt aus dem Backend (`src/services/next_briefing.py`, `_termin`/`vor_ort.tzname()`), nicht aus der Leiste; die Ursache ist aus dem Code nicht erkennbar (Hypothese unbestätigt: Etappe ohne Wegpunkte mit Rückfallzone oder ein Termin über die Zeitumstellung hinweg). Wird als **eigenes Bug-Issue** mit Reproduktion aus Nutzersicht geführt (erst rot nachweisen); keine ACs hier. Das Issue #2845 wird erst geschlossen, wenn auch dieses Folge-Issue geklärt ist oder der Nebenbefund dort nachweislich übernommen wurde.
- Der Ortsvergleich wird am Computer bewusst etwa 6 Pixel höher und die Reiter dunkler; das ist die gewollte Folge der Einheitsoptik, kein Fehler.
- Die E2E-Messung bei 1440 Pixel ist neu; die bestehenden Desktop-Fälle (HT-7, HT-8) laufen bei 1280 Pixel weiter.
- Für künftige Änderungen: Soll die Leiste je Seite wieder verschieden aussehen, braucht das ein neues ADR (Ablösung von ADR-0097), nicht einen neuen Prop.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (nicht nötig). Die Änderung wendet **ADR-0097** (Trip und Ortsvergleich teilen ihren Code) und **ADR-0110** (Hub-Kopf und Anlege-Rahmen ein Baustein; Zähler neutral, Leitprinzip hoher Kontrast) auf die Reiterleiste an und nimmt eine lokale Spec-Iteration (`size="sm"`, `mobile_tab_leisten_mtabbar.md` Iteration 2) zurück. Es entsteht keine neue Architektur-Ebene.
- **Rationale:** ein Baustein ohne Varianten statt zwei Optiken; Kontrast gewinnt gegen weiche Optik (PO-bestätigt 2026-05-25).

## Changelog

- 2026-11-09: Initial spec created (Issue #2845, Teil A; Teil B Zeitzone ausgegliedert).
- 2026-11-09: **Desktop-Werte abgelöst durch ADR-0111** (Issue #2881, Punkt 1): am Computer gilt ADR-0109 Punkt 7 — kein Kasten, Grundlinie 1 px `--g-rule` (statt `--g-ink-faint`), Reiter 13 px (statt 14 px)/500, aktiv 600 (statt 500), Zähler Mono 10 px neutral, Radius 3 px. Inaktiv `--g-ink` und die Gleichheit Trip/Vergleich aus dieser Spec bleiben; `hub-tab-bar.spec.ts` HT-14 ist umgestellt.
