---
entity_id: fix_3438_wetter_ganzseite
type: module
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
tags: [einstellungen, mockup-fassung-4, ganzseite, wetter, hub-kopf, i18n]
issue: 3438
epic: 2913
workflow: fix-3438-wetter-ganzseite
---

# Ganzseite Reiter Wetter: Zuordnung der Bildprüfer-Befunde (Chips, Hub-Kopf, Knopffarbe, Ziehgriffe)

## Approval

- [ ] Approved

## Purpose

Vier Befunde des Bildprüfers zur Ganzseite des Reiters Wetter (Trip, Orte, ein Ort; 1280 und 390 px; Kommentar #3009, Cluster 7) bekommen je eine begründete Zuordnung, damit keine Abweichung still geduldet wird. Je Punkt wird entweder das Produkt ans Mockup (Fassung 4) angeglichen oder das Mockup samt Elementliste an eine belegte Produktentscheidung. Danach darf die Abnahme #3009 diese vier Punkte nicht mehr als offen führen.

## Source

- **File:** `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte`, `frontend/src/routes/compare/[id]/+page.svelte`, `frontend/src/lib/i18n/messages/{de,en}/aktionen.json`, `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`
- **Identifier:** Region-Bearbeiten im Seitenkopf, Meta-Zeile Orte (`aktionen.kopf.vergleichstabelle`), Mockup-Listen `TRIP_OFF` / `ORTE_OFF`, Mockup-Regel `.btn.accent`

> **Schicht:** Frontend (`frontend/src/...`, SvelteKit) plus Mockup und Elementliste unter `docs/context/einstellungen_neu/`. Kein Go- und kein Python-Code, kein Versand- oder Speicherpfad. Die Region wird über den bestehenden Speicherweg von Trip bzw. Orts-Vergleich geschrieben (unverändert).
>
> **Trip/Ortsvergleich-Teilung:** Der Seitenkopf (`SubscriptionHeader`, `HubKopf`) ist geteilt; Punkt 2a gilt für Trip und Orte gleich, keine neue Komponente. Nur die Meta-Zeile (2b) liegt im Compare-eigenen Teil der Seite.
>
> **Mandantentrennung:** Das Speichern der Region bewegt Nutzerdaten; `user_id` kommt wie bisher aus dem Auth-Kontext. Test mit zwei verschiedenen Nutzern (AC-4).
>
> **Kanäle:** Briefing- und Alarm-Inhalt aller vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) bleibt unverändert; es ändert sich nur die Anzeige im Editor.

## Scope

**Drin:** Mockup Fassung 4 (Chip-Listen „Nicht im Briefing“ Trip/Orte, Knopffarbe „Test schicken ▾“, Stift an Titel und Oberzeile) samt neu erzeugter Elementliste und nachgezogener Besitzer-/Freigabe-Einträge; Seitenkopf Trip und Orte (Regionszeile entfällt, Region-Stift an der Oberzeile); Meta-Zeile Orte ohne „Vergleichstabelle“ (DE/EN); Spec c2 (AC-4, AC-9) und Glossar nachgezogen; Belege für 2c und 4.

**Nicht drin:** Auswahlregel der Chips im Produkt, Knopffarbe im Produkt, Ziehgriffe im Produkt, Speicherweg der Region, Briefing- und Alarm-Inhalte aller Kanäle, übrige Cluster der Messung #3009.

## Estimated Scope

- **LoC:** Produktcode ca. +40/-45, dazu Tests, Mockup und neu erzeugte Elementliste
- **Files:** ca. 14 (siehe Tabelle)
- **Effort:** medium

## Zuordnung der vier Befunde

| # | Befund | Zuordnung | Änderung |
|---|--------|-----------|----------|
| 1 | Chips „Nicht im Briefing“ (Trip 8 statt 11, Orte 10 statt 15) | Produktregel belegt: jede ausgebbare Katalog-Metrik ist hinzufügbar, in Gruppen-Reihenfolge (Spec #2794 AC-19, #3047) | Mockup angleichen |
| 2a | Stift am Titel und eigene Regionszeile mit Stift | Inline-Bearbeiten belegt (Spec c2 Nr. 5, AC-9); die doppelte Regionszeile (Region steht schon im Eyebrow) ist nicht belegt | Produkt angleichen, Funktion bleibt |
| 2b | Meta-Zeile Orte „· Vergleichstabelle ·“ | Mockup Fassung 4 „3 Orte · Morgen-Briefing 07:00“, ADR-0124 Nr. 10; Rückbau war für #3122 vermerkt und blieb aus | Produkt angleichen |
| 2c | Ein Ort ohne Oberzeile „Orte · Name“ | Regel „Orte · Region, ohne Region nur Orte“ (Spec c2) belegt; das Prüf-Abo hatte keine Region | Keine Produktänderung, nur Beleg |
| 3 | Farbe „Test schicken ▾“ | Bewusste Abweichung `--g-accent-deep` (Spec c2 AC-16, #2980, ADR-0118, WCAG-AA 7,45:1 statt 4,34:1) | Mockup angleichen |
| 4 | Ziehgriffe in „Was steht wo“ | Mockup Z. 721 zeichnet ⋮⋮ in gleicher Farbe #9a958a; Griff existiert in beiden | Keine Abweichung, nur Beleg |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `briefingAngebot()` (`shared/wetter-tab/ampelModell.ts`) | Funktion | Quelle der Produkt-Reihenfolge der Chips; bleibt unverändert |
| `SubscriptionHeader.svelte`, `HubKopf.svelte` | Komponenten (geteilt) | Eyebrow und Titel; Region-Stift wandert an die Oberzeile |
| `routes/compare/[id]/+page.svelte` | Seite | Meta-Zeile Orte, Eyebrow-Regel |
| `tr()` / Katalog `messages/{de,en}/aktionen.json` | i18n (ADR-0104) | Meta-Text nur über den Katalog |
| `scripts/elementliste_aus_mockup.ts`, `scripts/elementliste_abgleich.ts` | Skripte | Elementliste neu erzeugen (`mockup_hash`), Abgleich `--strict` |
| `elementliste_besitzer.json`, `elementliste_freigaben.json` | Soll-Daten | Freigaben zu „Vergleichstabelle“ und Region-Stift nachziehen |
| `docs/reference/i18n_glossar.md` | Glossar | Eintrag „Vergleichstabelle“ in der Meta-Zeile entfällt |
| `feat_2913_c2_seitenkopf.md`, `feat_2794_s3a_reiter_wetter.md`, `feat_2913_abgleich_ganzseite.md` | Specs | Bezugsstellen AC-4, AC-9, AC-16, AC-19 |
| ADR-0118, ADR-0124 Nr. 10, ADR-0104 | ADR | Knopf-Kontrast, Bereichsname Orte, Katalog-Pflicht |

## Implementation Details

**Punkt 1 (Mockup).** In `mockup-hub-fassung4.html` werden `TRIP_OFF` (Z. 337) und `ORTE_OFF` (Z. 349) samt der `removed`-Logik (Z. 526) so umgebaut, dass die Chips „Nicht im Briefing“ die Metriken des Staging-Prüfkontos vollständig und in Produkt-Reihenfolge zeigen. Trip (11): Luftfeuchte, Taupunkt, Windrichtung, Niederschlagsart, Bewölkung gesamt, Bewölkung mittel, Bewölkung hoch, Sonnenstunden, Luftdruck, Neuschnee, Schneehöhe. Orte (15): gefühlte Temperatur Wind, Luftfeuchte, Taupunkt, Windrichtung, Niederschlagsart, Sichtweite, Bewölkung tief, mittel, hoch, UV-Index, Luftdruck, Nullgradgrenze, Schneefallgrenze, Neuschnee, Schneehöhe. Die Metrik-Schlüssel in Produkt-Reihenfolge stehen im Kontext (`docs/context/fix-3438-wetter-ganzseite.md`, Abschnitt „Messung Staging/Mockup“); die Beschriftungen DE/EN kommen aus dem Produkt-Katalog (`frontend/src/lib/i18n/messages/`) und werden nicht neu erfunden. Abgewählte Vorlagen-Metriken reihen sich an ihrer Katalog-Position ein, nicht am Ende. Danach `elementliste.json` mit `scripts/elementliste_aus_mockup.ts` neu erzeugen (`mockup_hash` aktuell); verwaiste Besitzer- und Freigabe-Einträge werden geprüft und nachgezogen.

**Punkt 2a (Produkt, geteilter Kopf).** Die eigene Regionszeile unter dem Titel in `SubscriptionHeader.svelte` entfällt. Der Stift zum Bearbeiten der Region (Ruhezustand: nur Symbol mit `aria-label`) sitzt an der Oberzeile („Trip · Mallorca ✎“, „Orte · Münsterland ✎“); der Stift am Titel für den Namen bleibt. Das Inline-Bearbeiten von Name und Region bleibt vollständig erhalten (Spec c2 AC-9), nur der Platz ändert sich. Das Mockup zeichnet den Stift am Titel und blass an der Oberzeile. Die Test-IDs der Bearbeiten-Schalter bleiben, soweit sie nicht an einer entfallenden Zeile hängen.

**Punkt 2b (Produkt).** Die Meta-Zeile im Compare-Hub lautet „N Orte · Morgen-Briefing HH:MM“ (EN entsprechend), ohne „Vergleichstabelle“. Der Katalogschlüssel `aktionen.kopf.vergleichstabelle` wird in DE und EN entfernt, sofern ein Suchlauf keine weitere Nutzung findet (sonst bleibt er mit Begründung). Nachziehen: `hub_kopf_c2_mockup.test.ts`, `f9KatalogAnker.ts`, `e2e/hub-kopf-c2-mockup.staging.spec.ts`, Spec c2 AC-4 (Meta ohne „Vergleichstabelle“), Glossar, Besitzer-Einträge zu „Vergleichstabelle“ in `elementliste_besitzer.json` (Vermerk „Rückbau mit #3122“ entfällt samt Eintrag).

**Punkt 2c (kein Code).** Beleg per Staging-Messung: Bei einem Orts-Vergleich ohne Region steht die Oberzeile „Orte“ allein, mit Region „Orte · <Region>“.

**Punkt 3 (Mockup).** `.btn.accent` im Kopf des Mockups (Z. 49, Knopf „Test schicken ▾“) wird auf `--g-accent-deep` gestellt. Das Produkt bleibt unverändert. Die Ausnahme „Knopf-Farbe“ im Abgleich entfällt, weil Mockup und Produkt dann übereinstimmen.

**Punkt 4 (nur Beleg).** Keine Änderung. Belegt wird: Mockup Z. 721 `⋮⋮` (12 px, Handy 10 px, #9a958a); Produkt SVG mit sechs Punkten in #9a958a, 14 px. Die Zuordnung steht im Abschlusskommentar von #3438.

**Betroffene Dateien**

| Datei | Änderung |
|-------|----------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | MODIFY Chip-Listen, Stift an Oberzeile, Knopf `--g-accent-deep` |
| `docs/context/einstellungen_neu/elementliste.json` | REGENERATE |
| `docs/context/einstellungen_neu/elementliste_besitzer.json`, `elementliste_freigaben.json` | MODIFY Einträge Vergleichstabelle, Region-Stift, Knopf-Farbe |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY Regionszeile entfällt, Region-Stift an Oberzeile |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY nur falls der Eyebrow dort gerendert wird |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY Meta-Zeile ohne Vergleichstabelle |
| `frontend/src/lib/i18n/messages/de/aktionen.json`, `en/aktionen.json` | MODIFY Schlüssel `aktionen.kopf.vergleichstabelle` entfernen |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts` | MODIFY Erwartungen Meta, Stift |
| `frontend/src/lib/components/compare/__tests__/f9KatalogAnker.ts` | MODIFY Anker |
| `frontend/e2e/hub-kopf-c2-mockup.staging.spec.ts` | MODIFY Meta, Region-Stift, Oberzeile |
| `frontend/e2e/` Region-Bearbeiten-Spec (neu, Zwei-Nutzer) | CREATE |
| `docs/specs/modules/feat_2913_c2_seitenkopf.md` | MODIFY AC-4 und AC-9 mit Verweis auf diese Spec |
| `docs/reference/i18n_glossar.md` | MODIFY |

## Expected Behavior

- **Input:** Nutzer öffnet Trip- bzw. Orts-Hub, Reiter Wetter, in Deutsch oder Englisch, bei 1280 oder 390 px.
- **Output:** Kopf mit Oberzeile samt Region-Stift und ohne eigene Regionszeile; Meta „N Orte · Morgen-Briefing HH:MM“; im Mockup stehen die Chips „Nicht im Briefing“ vollständig und der Knopf in `--g-accent-deep`.
- **Side effects:** Nur beim Speichern der Region wird der Trip bzw. Orts-Vergleich per Merge geschrieben (Read-Modify-Write, kein Feldverlust); sonst keine.

## Test Plan

### Kern-Schicht (`node --test`, deterministisch, kein Mock-Theater)

- Kopf-Test: Der gerenderte Kopf hat keine eigene Regionszeile, der Region-Stift (`aria-label`) sitzt in der Oberzeile, der Stift am Titel bleibt; für Kontext Trip und Orte.
- Meta-Test: Orte-Meta lautet DE „3 Orte · Morgen-Briefing 07:00“ und EN entsprechend, ohne „Vergleichstabelle“; der Katalogschlüssel existiert nicht mehr.
- Mockup-Test: Die Chips des Mockups für Trip (11) und Orte (15) stimmen in Anzahl und Reihenfolge mit `briefingAngebot()` für das Seed-Profil überein (Soll aus dem Produkt-Modell berechnet, nicht aus einer abgeschriebenen Liste); Knopf-Fläche im Mockup ist `--g-accent-deep`.
- Elementlisten-Tests: `mockup_hash` aktuell (`pruefeHashAktuell`), keine verwaisten Besitzer-/Freigabe-IDs.

### Live-E2E-Schicht (nur in `/e2e-verify` gegen Staging)

- Region-Bearbeiten Trip und Orte: Region ändern, speichern, Seite neu laden; Name, Profil und übrige Felder bleiben. Zwei verschiedene Nutzer: Nutzer B sieht die Region von Nutzer A nie und kann sie nicht ändern.
- Messung: Oberzeile eines Orts-Vergleichs ohne Region zeigt „Orte“; mit Region „Orte · <Region>“.
- Staging-Abgleich `scripts/elementliste_abgleich.ts --strict` mit Prüfkonto und Seed-IDs (DE und EN).
- `mockup-bildpruefer` über die Ganzseitenbilder (Trip, Orte, ein Ort; 1280 und 390 px).

## Acceptance Criteria

- **AC-1:** Given der Trip-Hub eines Prüfkontos im Reiter Wetter / When die Chips unter „Nicht im Briefing“ im Mockup und auf Staging verglichen werden / Then stehen im Mockup alle 11 ausgebbaren, nicht gewählten Katalog-Metriken in derselben Reihenfolge wie im Produkt.
  - Test: Kern-Test vergleicht Mockup-Chips mit der Ausgabe von `briefingAngebot()`; Staging-Abgleich ohne Abweichung bei den Chips.

- **AC-2:** Given der Orts-Hub eines Prüfkontos im Reiter Wetter / When die Chips unter „Nicht im Briefing“ im Mockup und auf Staging verglichen werden / Then stehen im Mockup alle 15 Katalog-Metriken in Produkt-Reihenfolge, und das Produkt zeigt weiterhin jede ausgebbare Metrik.
  - Test: Kern-Test wie AC-1 für Orte; bestehender Kontextkatalog-Test `nicht_im_briefing_kontextkatalog.test.ts` bleibt grün.

- **AC-3:** Given ein Trip oder Orts-Vergleich mit Region im Hub / When der Kopf betrachtet wird / Then gibt es unter dem Titel keine eigene Regionszeile mehr, und die Region steht nur in der Oberzeile („Trip · Mallorca“ bzw. „Orte · Münsterland“) mit einem Stift (Screenreader-Beschriftung).
  - Test: Kopf-Test (Trip und Orte) und Staging-Messung der Elemente bei 1280 und 390 px.

- **AC-4:** Given ein Nutzer ändert über den Stift an der Oberzeile die Region eines Trips bzw. Orts-Vergleichs und speichert / When die Seite neu geladen wird / Then steht die neue Region in Oberzeile und Brotkrumen, Name und Profil sind unverändert, und ein zweiter Nutzer sieht und ändert diese Region nicht.
  - Test: E2E mit zwei verschiedenen Nutzern, Trip und Orte; Spec c2 AC-9 gilt weiter und wird entsprechend verwiesen.

- **AC-5:** Given der Name im Kopf soll geändert werden / When der Nutzer den Stift am Titel klickt / Then öffnet das Inline-Bearbeiten wie bisher, und der Name wird gespeichert, ohne dass andere Felder verloren gehen.
  - Test: bestehender E2E `hub-kopf-bearbeiten` bleibt grün.

- **AC-6:** Given ein Orts-Vergleich mit drei Orten und einem Morgen-Briefing um 07:00 / When der Kopf in Deutsch oder Englisch betrachtet wird / Then lautet die Meta-Zeile „3 Orte · Morgen-Briefing 07:00“ (EN entsprechend) ohne das Wort „Vergleichstabelle“.
  - Test: Meta-Test in beiden Sprachen; Staging-E2E am Orts-Hub; Katalogschlüssel `aktionen.kopf.vergleichstabelle` ist entfernt oder mit dokumentierter Restnutzung belegt.

- **AC-7:** Given ein Orts-Vergleich ohne Region / When der Kopf betrachtet wird / Then steht über dem Titel die Oberzeile „Orte“, mit Region „Orte · <Region>“; das Produkt wird dafür nicht geändert.
  - Test: Staging-Messung mit einem Abo ohne und einem mit Region, Ergebnis im Abschlusskommentar von #3438.

- **AC-8:** Given der Kopf im Mockup und auf Staging / When die Fläche des Knopfs „Test schicken ▾“ verglichen wird / Then verwenden beide `--g-accent-deep` (Kontrast mindestens 4,5:1, gemessen 7,45:1), und die Abweichung steht nicht mehr als offener Befund.
  - Test: Kern-Test liest die Mockup-Regel; E2E liest die berechnete Hintergrundfarbe auf Staging; Spec c2 AC-16 bleibt gültig.

- **AC-9:** Given der Abschnitt „Was steht wo“ im Mockup und auf Staging / When die Ziehgriffe verglichen werden / Then zeichnen beide einen Griff je Zeile in der Farbe #9a958a (Mockup ⋮⋮ 12 px bzw. 10 px am Handy, Produkt 14 px), und der Befund ist als „keine Abweichung“ mit diesem Beleg zugeordnet.
  - Test: Staging-Messung der Griff-Elemente und -Farbe, Beleg im Abschlusskommentar; keine Codeänderung.

- **AC-10:** Given das geänderte Mockup / When die Elementliste neu erzeugt wird / Then ist `mockup_hash` aktuell, und keine Besitzer- oder Freigabe-Zeile verweist auf eine entfallene Element-ID.
  - Test: Elementlisten-Tests (`pruefeHashAktuell`, Besitzer-/Freigabe-Konsistenz) im Kern-Lauf grün.

- **AC-11:** Given die ausgelieferte Version auf Staging / When der Elementlisten-Abgleich `--strict` mit Prüfkonto und Seed-IDs (DE und EN) läuft / Then bleibt keine unzugeordnete Abweichung zu den Punkten 1 bis 4 übrig.
  - Test: `scripts/elementliste_abgleich.ts --strict` mit Prüfkonto-Login.

- **AC-12:** Given die Ganzseitenbilder von Mockup und Staging (Trip, Orte, ein Ort; 1280 und 390 px) / When der `mockup-bildpruefer` sie vergleicht / Then bleibt keine unzugeordnete Abweichung zu den vier Punkten (Chips, Hub-Kopf, Knopffarbe, Ziehgriffe) offen.
  - Test: Bildprüfer-Lauf nach dem Staging-Deploy, Ergebnis im Abschlusskommentar.

## Definition of Done

- AC-1 bis AC-12 erfüllt, Kern-Tests (node --test) grün, alle CI-Checks grün.
- Staging-E2E (Region-Bearbeiten Zwei-Nutzer, Kopf, Abgleich `--strict`, Bildprüfer) grün.
- Ausgeliefert nach Produktion, Selftest grün, Issue #3438 mit Zuordnungs-Kommentar geschlossen.

## Risks

- Der geteilte Kopf betrifft Trip und Orte; Region-Bearbeiten darf nicht verloren gehen (AC-4, AC-5) und schreibt per Merge, nicht per Replace.
- Eine Mockup-Änderung kann `ordnung`-Werte und IDs der Elementliste verschieben; Besitzer- und Freigabe-Einträge können verwaisen (AC-10).
- Das Prüfkonto hat feste Region, Wegwerf-Abos keine; die Oberzeilen-Messung (AC-7) muss beide Fälle abdecken.
- Der Katalogschlüssel darf nur entfernt werden, wenn kein weiterer Verwender existiert (Suchlauf vor dem Entfernen).

## Known Limitations

- Die Chip-Listen im Mockup bilden den Stand des Prüfkontos ab; ändert sich der Katalog, muss das Mockup nachgezogen werden (der Kern-Test macht das sichtbar).
- Der Auftrag braucht keine menschliche Sperre (override) und keine Änderung der Gate-Konfiguration.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Angleichung an das freigegebene Mockup und an bestehende Entscheidungen (ADR-0118, ADR-0124 Nr. 10, Spec #2794 AC-19, c2 AC-9/AC-16). Die Verlegung des Region-Stifts ändert nur den Platz, nicht die Funktion; keine neue Entscheidungsfläche.

## Changelog

- 2026-11-28: Initial spec created (Issue #3438, Epic #2913)
