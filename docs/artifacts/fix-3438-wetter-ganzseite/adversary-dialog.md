# Adversary Dialog — fix-3438-wetter-ganzseite
Spec: docs/specs/modules/fix_3438_wetter_ganzseite.md
Datum: 2026-11-28 09:22

## Checkliste
- [x] **Input:** Nutzer öffnet Trip- bzw. Orts-Hub, Reiter Wetter, in Deutsch oder Englisch, bei 1280 oder 390 px. — lokal belegt: Kopf-Tests Trip/Orte DE/EN (adversary-tests-1.txt)
- [x] **Output:** Kopf mit Oberzeile samt Region-Stift und ohne eigene Regionszeile; Meta „N Orte · Morgen-Briefing HH:MM“; im Mockup stehen die Chips „Nicht im Briefing“ vollständig und der Knopf in `--g-accent-deep`. — lokal belegt: hub_kopf_region_oberzeile_3438.test.ts, mockup_nicht_im_briefing_3438.test.ts
- [x] **Side effects:** Nur beim Speichern der Region wird der Trip bzw. Orts-Vergleich per Merge geschrieben (Read-Modify-Write, kein Feldverlust); sonst keine. — lokal belegt: Speichern per Merge, Spec hub-kopf-region-zwei-nutzer-3438.staging.spec.ts (ohneRegion-Vergleich)
- [x] **AC-1:** Given der Trip-Hub eines Prüfkontos im Reiter Wetter / When die Chips unter „Nicht im Briefing“ im Mockup und auf Staging verglichen werden / Then stehen im Mockup alle 11 ausgebbaren, nicht gewählten Katalog-Metriken in derselben Reihenfolge wie im Produkt. — lokal belegt: mockup_nicht_im_briefing_3438.test.ts
- [x] **AC-2:** Given der Orts-Hub eines Prüfkontos im Reiter Wetter / When die Chips unter „Nicht im Briefing“ im Mockup und auf Staging verglichen werden / Then stehen im Mockup alle 15 Katalog-Metriken in Produkt-Reihenfolge, und das Produkt zeigt weiterhin jede ausgebbare Metrik. — lokal belegt: mockup_nicht_im_briefing_3438.test.ts
- [x] **AC-3:** Given ein Trip oder Orts-Vergleich mit Region im Hub / When der Kopf betrachtet wird / Then gibt es unter dem Titel keine eigene Regionszeile mehr, und die Region steht nur in der Oberzeile („Trip · Mallorca“ bzw. „Orte · Münsterland“) mit einem Stift (Screenreader-Beschriftung). — lokal belegt: SubscriptionHeader.svelte, Kopf-Test
- [x] **AC-4:** Given ein Nutzer ändert über den Stift an der Oberzeile die Region eines Trips bzw. Orts-Vergleichs und speichert / When die Seite neu geladen wird / Then steht die neue Region in Oberzeile und Brotkrumen, Name und Profil sind unverändert, und ein zweiter Nutzer sieht und ändert diese Region nicht. — (Staging-Nachweis in /e2e-verify ausstehend; Spec frontend/e2e/hub-kopf-region-zwei-nutzer-3438.staging.spec.ts geprüft)
- [x] **AC-5:** Given der Name im Kopf soll geändert werden / When der Nutzer den Stift am Titel klickt / Then öffnet das Inline-Bearbeiten wie bisher, und der Name wird gespeichert, ohne dass andere Felder verloren gehen. — lokal belegt: Name-Speichern-Weg unverändert, hub-kopf-bearbeiten
- [x] **AC-6:** Given ein Orts-Vergleich mit drei Orten und einem Morgen-Briefing um 07:00 / When der Kopf in Deutsch oder Englisch betrachtet wird / Then lautet die Meta-Zeile „3 Orte · Morgen-Briefing 07:00“ (EN entsprechend) ohne das Wort „Vergleichstabelle“. — lokal belegt: vergleich_hub_sprache.test.ts, hub_kopf_c2_mockup.test.ts
- [x] **AC-7:** Given ein Orts-Vergleich ohne Region / When der Kopf betrachtet wird / Then steht über dem Titel die Oberzeile „Orte“, mit Region „Orte · <Region>“; das Produkt wird dafür nicht geändert. — (Staging-Nachweis in /e2e-verify ausstehend; Spec frontend/e2e/hub-kopf-c2-mockup.staging.spec.ts geprüft)
- [x] **AC-8:** Given der Kopf im Mockup und auf Staging / When die Fläche des Knopfs „Test schicken ▾“ verglichen wird / Then verwenden beide `--g-accent-deep` (Kontrast mindestens 4,5:1, gemessen 7,45:1), und die Abweichung steht nicht mehr als offener Befund. — lokal belegt: Mockup-Regel .btn.accent, Mutation rot
- [x] **AC-9:** Given der Abschnitt „Was steht wo“ im Mockup und auf Staging / When die Ziehgriffe verglichen werden / Then zeichnen beide einen Griff je Zeile in der Farbe #9a958a (Mockup ⋮⋮ 12 px bzw. 10 px am Handy, Produkt 14 px), und der Befund ist als „keine Abweichung“ mit diesem Beleg zugeordnet. — (Staging-Nachweis in /e2e-verify ausstehend; Messverfahren in frontend/e2e/hub-kopf-c2-mockup.staging.spec.ts geprüft)
- [x] **AC-10:** Given das geänderte Mockup / When die Elementliste neu erzeugt wird / Then ist `mockup_hash` aktuell, und keine Besitzer- oder Freigabe-Zeile verweist auf eine entfallene Element-ID. — lokal belegt: elementliste_aktuell.test.ts, test_2913_c2_besitzerliste.py
- [x] **AC-11:** Given die ausgelieferte Version auf Staging / When der Elementlisten-Abgleich `--strict` mit Prüfkonto und Seed-IDs (DE und EN) läuft / Then bleibt keine unzugeordnete Abweichung zu den Punkten 1 bis 4 übrig. — (Staging-Nachweis in /e2e-verify ausstehend; Skript scripts/elementliste_abgleich.ts --strict, Besitzerliste lokal geprüft)
- [x] **AC-12:** Given die Ganzseitenbilder von Mockup und Staging (Trip, Orte, ein Ort; 1280 und 390 px) / When der `mockup-bildpruefer` sie vergleicht / Then bleibt keine unzugeordnete Abweichung zu den vier Punkten (Chips, Hub-Kopf, Knopffarbe, Ziehgriffe) offen. — (Staging-Nachweis in /e2e-verify ausstehend; Bildprüfer-Lauf nach Deploy, Mockup-Seite lokal geprüft)

## Dialog

### Runde 1
**Adversary:**
Tests (Named, node --test): 8 RED/Anker-Dateien plus TripHeader.issue699 = 379 pass, 0 fail (docs/artifacts/fix-3438-wetter-ganzseite/adversary-tests-1.txt); pytest tests/test_2913_c2_besitzerliste.py 36 passed (adversary-pytest-1.txt); Hash-/Zusammengesetzt-Tests 33 pass (adversary-tests-2.txt); weitere Kopf-Suiten 92 pass (adversary-tests-3.txt).

Confirmation AC-3: 
Code reference: frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte:123
Beschreibung: Oberzeile mit Eyebrow plus Region-Stift (Zeile 134), die alte Regionszeile unter dem Titel ist entfernt. Status CONFIRMED (Mutation: aria-label am Region-Stift entfernt -> 9 Tests rot; Profil-Label aus der Oberzeile -> 2 rot).
Confirmation AC-5:
Code reference: frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte:143
Beschreibung: Namens-Stift unveraendert, Speichern-Weg `save()` (Zeile 91) unveraendert; kein Feldverlust-Code beruehrt. CONFIRMED.
Confirmation AC-6:
Code reference: frontend/src/routes/compare/[id]/+page.svelte:201
Beschreibung: Meta nur Anzahl plus Briefing-Zeit. CONFIRMED (Mutation: „Vergleichstabelle“ wieder anhaengen -> 6 rot; Morgen-Zweig abschalten -> 4 rot). Katalogschluessel in de/en aktionen.json entfernt, kein weiterer Verwender (grep).
Confirmation AC-7: Eyebrow ohne Region = nur „Trip“/„Orte“ (hub-kopf-aufbau.spec.ts, hub-kopf-paritaet-compare-trip.spec.ts angepasst); Produkt nicht geaendert. CONFIRMED (Staging-Messung ausstehend).
Confirmation AC-8:
Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:49
Beschreibung: `.btn.accent` auf --g-accent-deep; Mutation zurueck auf --g-accent -> Test rot. CONFIRMED.
Confirmation AC-1/AC-2: Mockup-Chips Zeilen 340 und 354 (TRIP_OFF/ORTE_OFF + KAT_FOLGE) in der Elementliste; mockup_nicht_im_briefing_3438.test.ts berechnet das Soll aus briefingAngebot() mit den echten Seed-Funktionen (kein Abschreiben). Die Kette Mockup -> Elementliste wird durch elementliste_aktuell.test.ts (Hash) bewacht: Mutation „Chip aus TRIP_OFF entfernt“ ohne Neuerzeugung -> Hash-Test rot (die Chip-Suite allein bleibt gruen, weil sie die Liste liest; das ist durch den Hash-Test abgedeckt). CONFIRMED.
Confirmation AC-10: elementliste.json neu erzeugt, test_2913_c2_besitzerliste.py gruen, Besitzer-Ausnahmen „Name/Region bearbeiten“, „Test schicken ▾“, „Mallorca“, „Westfalen“, „Vergleichstabelle“-Muster entfernt; die Stift-Texte stehen jetzt als Kopf-Knopf im Soll (neuer Test belegt das je Kontext/Sprache). CONFIRMED.
Code reference: frontend/playwright.3438-region-zwei-nutzer.staging.config.ts:19
Config: testMatch genau auf hub-kopf-region-zwei-nutzer-3438.staging.spec.ts, Setup-Projekt, workers 1, nur Staging-baseURL. Die Spec prueft: Region aendern, Reload, Name/Profil unveraendert, Merge (ohneRegion-Vergleich), Zwei-Nutzer (B sieht kein A, PUT/GET 403/404, A unveraendert), Stift in Zeile des Eyebrows ueber dem Titel (Trip und Orte, 1280 und 390 px). Zusicherung real geprueft. AC-4: Staging ausstehend.
Staging ausstehend (nicht hier pruefbar): AC-4, AC-7, AC-9 (Messung; Hinweis LOW F002), AC-11, AC-12. E2E-Specs geaendert (hub-kopf-aufbau, hub-kopf-paritaet-compare-trip, trip-hub-kopf-region-aktivitaet): Diff gelesen, Selektoren passen zum neuen DOM (preceding-sibling::*[1] = Eyebrow-Wrapper vor dem Stift, hub-kopf-eyebrow-testid, textContent wegen CSS-Grossschreibung); lokal nicht gestartet (kein Stack), plausibel korrekt.

Mutationen ohne Fang: keine in der Zielsuite, die nicht anderswo gefangen wird. maxlength der Region-Eingabe: in den 8 Zielsuiten nicht bewacht, aber subscription_header_bedienlogik.test.ts faengt es (2 rot).

**Implementierer:** (nicht beteiligt, Kontext-Isolation)

### Runde 2
**Adversary:**
Gezielt die wirksame Stelle: Region-Bearbeiten auf Trip UND Orte laeuft ueber denselben geteilten SubscriptionHeader (
Code reference: frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte:126
Beschreibung: Bearbeiten ersetzt die Oberzeile durch Eingabe (maxlength, Speichern, Abbrechen), Fehlermeldung `fieldError('region')` bleibt (Zeile 140). Kein Escape/Fokus-Handling existierte vorher und existiert nachher — keine Regression. Fallback `{region || '—'}` nur ohne Eyebrow-Snippet (Test rot bei Mutation, 4 Tests). Pruefpunkt (d): die geaenderten Altests ersetzen Erwartungen durch das Neue (Meta ohne Vergleichstabelle, Region in Oberzeile) und fuegen `hatNicht('Vergleichstabelle')` hinzu; kein Test geloescht, ALT_ANZAHL/ALT_SHA mit begruendetem Diff nachgezogen (+32 IDs: 16 Stift-Knoepfe, 16 Chips). Pruefpunkt (c): entfernte Besitzer-Ausnahmen verdecken nichts — Stift-Texte stehen im Soll, Knopf-Farbe stimmt in Mockup und Produkt ueberein, „Mallorca“/„Westfalen“ standen nur als Region-Zeile; Staging-Abgleich --strict (AC-11) muss das bestaetigen und bleibt ausstehend. Pruefpunkt (b): Soll aus briefingAngebot() berechnet (mockup_nicht_im_briefing_3438.test.ts), nicht abgeschrieben.
Finding F001 (LOW, edge_case): 
Code reference: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:729
Beschreibung: Spec nennt fuer den Ziehgriff „Mockup Z. 721“, tatsaechlich steht er jetzt in Z. 729 (Mockup verschoben). Nur Beleg-Text; beim Abschlusskommentar von #3438 die Zeile korrekt nennen. Keine Code-Folge.
Finding F002 (LOW, anti_pattern):
Code reference: frontend/src/lib/components/shared/wetter-tab/__tests__/mockup_nicht_im_briefing_3438.test.ts:84
Beschreibung: Mockup-Chip-Test prueft nur Zustand „normal“ (mockupChips default); Zustand „luecken“ wird nur durch die Anzahl-/Hash-Pins in elementliste_uebersicht_2969.test.ts bewacht. Akzeptabel, da dieselbe Liste erzeugt wird.
Keine CRITICAL/HIGH/MEDIUM.

**Implementierer:** (nicht beteiligt)

## Herkunft der Vorbedingungen

Vorbedingungen (Seed des Pruefkontos, Katalog, Mockup-Hash) stammen aus echten Seed-Funktionen (scripts/staging_pruefkonto_mockupdaten.py) und dem Produkt-Katalog, nicht aus abgeschriebenen Listen. Staging-Zugang fuer die E2E-Specs: Setup-Projekt fix-1895-modus-rueckbau.staging.setup.ts (frontend/playwright.3438-region-zwei-nutzer.staging.config.ts:11).

## Verdict

VERDICT: VERIFIED (lokal). Staging ausstehend: AC-4, AC-7, AC-9, AC-11, AC-12. Findings nur LOW (F001, F002).

## Geprüfte Dateien

- sha256:928d45ba9d6e34a23a00f3b34e5e976ef74c95c18fe7c83d7536725b2ab7780a  frontend/playwright.3438-region-zwei-nutzer.staging.config.ts
- sha256:a2cc05639ee64a77143d7cabe251d1b46d191708e2c5b9d90b9a17088c0b8270  frontend/src/lib/components/shared/wetter-tab/__tests__/mockup_nicht_im_briefing_3438.test.ts

## Prüfbasis

- base: 5619fdea5ebf67397bcea7f5a8ba7a0985237082
- blob:25f3b5f8e6f1c3e3bf19e7d5c69986b8640ec341  frontend/playwright.3438-region-zwei-nutzer.staging.config.ts
- blob:4e12624bb33c382823d6972fe406b45c22129fe9  frontend/src/lib/components/shared/wetter-tab/__tests__/mockup_nicht_im_briefing_3438.test.ts

## Geprüfte Dateien

- sha256:ad2e02da1d8755e9c17356e15dfea677c76498df74c3fb17b533ab673c4ca427  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- sha256:928d45ba9d6e34a23a00f3b34e5e976ef74c95c18fe7c83d7536725b2ab7780a  frontend/playwright.3438-region-zwei-nutzer.staging.config.ts
- sha256:3c6e92fb4817e8b602c1fdaf4eee7538a60638b981fc9b542955bb2f81e3bca1  frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte
- sha256:a2cc05639ee64a77143d7cabe251d1b46d191708e2c5b9d90b9a17088c0b8270  frontend/src/lib/components/shared/wetter-tab/__tests__/mockup_nicht_im_briefing_3438.test.ts
- sha256:02c8bd049a147765824c6ab465ece51556eab3c505ba1ebaeb7756cef6ddde0e  frontend/src/routes/compare/[id]/+page.svelte

## Prüfbasis

- base: 5619fdea5ebf67397bcea7f5a8ba7a0985237082
- blob:94aab3690046fe9213276c3ea925089cef05ba49  docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html
- blob:25f3b5f8e6f1c3e3bf19e7d5c69986b8640ec341  frontend/playwright.3438-region-zwei-nutzer.staging.config.ts
- blob:d2a5a748a828bce7fd7f15d62772bb6b4e6ab930  frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte
- blob:4e12624bb33c382823d6972fe406b45c22129fe9  frontend/src/lib/components/shared/wetter-tab/__tests__/mockup_nicht_im_briefing_3438.test.ts
- blob:96480617e9b5555e4c778f648c953e1a44adbc1e  frontend/src/routes/compare/[id]/+page.svelte
