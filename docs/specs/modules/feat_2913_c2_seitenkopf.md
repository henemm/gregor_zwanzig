---
entity_id: feat_2913_c2_seitenkopf
type: feature
created: 2026-11-13
updated: 2026-11-13
status: draft
version: "1.0"
workflow: feature-2913-c2-seitenkopf
tags: [einstellungen-neu, seitenkopf, hub, reiterleiste, vorlage-karte, abgleich, epic-2791, issue-2913]
---

# Scheibe c2: Seitenkopf des Editor-Hubs (Trip + Orts-Vergleich) nach Mockup

## Approval

- [ ] Approved

## Purpose

Der Hub-Kopf von Trip und Orts-Vergleich (Brotkrumen, Eyebrow, Titel mit Status-Pill, Meta-Zeile, Reiterleiste, Vorlage-Karte) weicht vom freigegebenen Mockup `mockup-hub-fassung3.html` ab; der Ganzseiten-Abgleich führt dafür 92 Besitzer-Einträge `#2913-c2`. Diese Scheibe bringt den geteilten Kopf auf Mockup-Stand (DE und EN), damit die c2-Einträge entfallen und `--abnahme` für den Kopf Exit 0 liefert.

## Source

- **File:** `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte`
- **Identifier:** `HubKopf` (mit `SubscriptionHeader`, `TripHeader`, `TripTabs`, `CompareTabs`, `VorlageKarte`, `routes/compare/[id]/+page.svelte`)
- **Schicht:** ausschließlich Frontend (`frontend/src/...`) plus Doku-Daten des Abgleichs (`docs/context/einstellungen_neu/`). Kein Go-API-, kein Python-Core-Code, keine Schema-Änderung.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung (ADR-0097):** Alle Änderungen liegen in den geteilten Bausteinen (`HubKopf`, `SubscriptionHeader`, `VorlageKarte`) oder in den bestehenden Paaren `TripTabs`/`CompareTabs` und `TripHeader`/Compare-Seite, jeweils mit gleicher Logik und `context="route"|"vergleich"`. Kein neuer Baustein mit einseitigem Pendant.
> - **Mandantentrennung:** Es werden keine Nutzerdaten bewegt und kein Endpoint geändert (nur Darstellung). Zwei-Nutzer-Test entfällt; die Isolation bleibt unberührt und wird im E2E-Lauf mit dem vorhandenen Staging-Konto lediglich nicht verletzt.
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt ändert sich; E-Mail, Telegram, SMS und Premium-SMS sind nicht betroffen (Mail-Kopf-Satz bleibt bei #2796).

## Scope

### In Scope

1. **Kopfleiste:** Brotkrumen „Trips / **Name**“ bzw. „Orte / **Name**“, Kebab „Weitere Aktionen“, Knopf mit Beschriftung „Test schicken ▾“ (nur Beschriftung, kein neues Menü; Menü bleibt #2797).
2. **Kopf:** Eyebrow „Trip · Region“ bzw. „Orte · Region“, h1 mit Status-Pill (fertig, aktiv, Entwurf mit „Aktivieren“, pausiert, archiviert), Meta-Zeile nach Mockup (Trip: „Datum · N Etappen · km · ↑m“; Orte: „N Orte · Vergleichstabelle · Briefing HH:MM“).
3. **Reiterleiste:** Zähler-Badge „Etappen (N)“ / „Orte (N)“, `aria-current` am aktiven Reiter.
4. **Vorlage-Karte:** Texte und Gruppen (Vorlagen / Eigene) nach Mockup, ohne den Satz „Name der Vorlage ersetzt das Profil und steht im Kopf der Mail“.
5. **Name/Region** bleiben inline bearbeitbar; im Ruhezustand nur Stift-Icon mit `aria-label`.
6. **Abgleich-Daten:** c2-Besitzer-Einträge entfernen; Einträge zu Profil-Wegfall, Tempo-Karte (`abschnitt=tempo`) und Mail-Kopf-Satz auf `#2796` umhängen (Grund „Scheibe S4, Datenmodell+Migration“); sichtbare Bearbeiten-Texte von Name/Region als Ausnahme mit Verweis auf diese Spec.
7. Neue Nutzertexte DE und EN im Katalog (ADR-0104); EN aus `elementliste.json`.

### Nicht-Ziele (ausdrücklich)

- Profil-Zeile/Profil-Chip bleiben bis #2796 (S4, ADR-0108); keine Entfernung, keine Migration.
- Tempo-Karte im Reiter Etappen (Fortbewegung, Tempo flach, Aufstieg, Gehzeit je Etappe): #2796.
- Mail-Kopf zeigt weiter das Profil; Vorlagenname im Mail-Kopf: #2796.
- „Test schicken“-Menü (Morgen-/Abend-Briefing): #2797; die 8 dortigen Besitzer-Einträge bleiben.
- Keine Datenmodell- oder Schema-Änderung (`activity`, `profil` unverändert, Read-Modify-Write unberührt).

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | Brotkrumen, Eyebrow, Titel+Pill, Meta, Kebab, Knopf „Test schicken ▾“ |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY | Ruhezustand nach Mockup, Stift als Icon mit aria-label; Profil-Teil unverändert |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | Eyebrow „Trip · Region“, Meta-Zeile, Pill-Zustände |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | Eyebrow „Orte · Region“, Meta „N Orte · Vergleichstabelle · Briefing HH:MM“ |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Zähler-Badge Etappen (N) über `MTabBar.badge` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Zähler-Badge Orte (N) über `MTabBar.badge` |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | Texte/Gruppen nach Mockup, ohne Mail-Kopf-Satz |
| `frontend/src/lib/i18n/messages/de/*.json`, `en/*.json` | MODIFY | neue Schlüssel DE+EN |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | c2-Einträge entfernen bzw. auf `#2796` umhängen |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` → Liste `ausnahmen` (gelesen von `leseAusnahmen`) | MODIFY | Name/Region-Bearbeiten-Texte mit Verweis auf diese Spec |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/*`, `shared/__tests__/subscription_header_*.test.ts`, `trip-detail/__tests__/trip_header_status_profil.test.ts`, `compare/__tests__/compare_hub_fidelity.test.ts`, `routes/compare/__tests__/bug_589_breadcrumb_links.test.ts` | MODIFY | an neue Texte/Struktur anpassen, nicht ersatzlos löschen |
| `frontend/e2e/hub-kopf-aufbau.spec.ts`, `hub-kopf-paritaet-compare-trip.spec.ts` (Knopf „Senden“ → „Test schicken“), `hub-kopf-bearbeiten.spec.ts`, `trip-hub-kopf-region-aktivitaet.spec.ts` | MODIFY | mitziehen |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts` | CREATE | neue Unit-Tests (node --test) |
| `frontend/e2e/hub-kopf-c2-mockup.staging.spec.ts` | CREATE | neue E2E-Prüfung gegen Staging (Playwright) |

## Estimated Scope

- **LoC:** ca. +350 / −150
- **Files:** ca. 10 Quelle + 10 Tests
- **Effort:** medium (Risiko niedrig bis mittel: geteilter Kopf, viele Tests binden an Kopf-Texte)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MTabBar` (`badge`), `StatusSchild`/`Pill`, `Eyebrow`, `Btn`, `SubscriptionKebab` | Design-System-Bausteine (ADR-0112) | einzige zulässige Bausteine; Wächter `bausteine_waechter*.test.ts` |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Soll | Z. 228–245, 310–326, 358–365, 454–465, 508–512 |
| `docs/context/einstellungen_neu/elementliste.json` | Soll-Texte | EN-Texte (Lücken: #2968) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | Daten | Besitzer-Einträge |
| `feat_2913_abgleich_ganzseite.md` | Spec | Besitzer-Mechanik, `--abnahme`, Marker `data-seite="hub"` |
| `rework_2837_s1_hub_kopf.md`, `rework_2845_hub_reiterleiste.md`, `feat_1273_s2_compare_hub_name_region_profil.md` | Specs | Vorgänger; Name/Region-Bearbeiten am Hub bleibt |
| Issue #2796 (S4, ADR-0108) | Abhängigkeit | übernimmt Profil, Tempo, Mail-Kopf-Satz |
| Issue #2797 | Abhängigkeit | übernimmt „Test schicken“-Menü |
| i18n-Katalog (ADR-0104) | Katalog | neue Nutzertexte nur dort |

## Implementation Details

Umbau der bestehenden geteilten Bausteine, keine Neubauten, Reihenfolge: Kopf, Reiterleiste, Vorlage-Karte, Besitzerliste/Ausnahmen, Abgleich-Abnahme.

1. **Kopf:** `HubKopf` rendert Brotkrumen (Elternlink „Trips“/„Orte“, Name als aktuelles Element), Knopf mit Beschriftung aus Prop `sendLabel` („Test schicken ▾“; testid `subscription-hub-send` bleibt), Kebab. `SubscriptionHeader` zeigt Eyebrow („Trip · Region“/„Orte · Region“), h1 mit Status-Pill und Meta-Zeile; der Stift ist im Ruhezustand ein Icon mit `aria-label`, Texte des Bearbeiten-Zustands (Speichern/Abbrechen/Feldnamen) bleiben und werden als Abgleich-Ausnahme geführt.
2. **Meta:** Trip aus Datum, Etappenzahl, km, ↑m; Orte aus Ortezahl, „Vergleichstabelle“, Briefing-Zeit. Zahlen locale-formatiert (DE „31,5 km“, EN „31.5 km“).
3. **Reiterleiste:** `badge` am Reiter Etappen/Orte mit Anzahl; Zähler ändert sich mit der Datenmenge; aktiver Reiter trägt `aria-current`.
4. **Vorlage-Karte:** Texte nach Mockup, Gruppen „Vorlagen“/„Eigene“; Mail-Kopf-Satz entfällt in c2.
5. **Abgleich-Daten:** Skript/Hand-Edit am Besitzer-JSON; `verweis` auf `#2796` mit Grund „Scheibe S4, Datenmodell+Migration“ für Profil-Wegfall, Tempo, Mail-Kopf-Satz. Ausnahmen-Eintrag für Name/Region-Bearbeiten-Texte mit Spec-Verweis.
6. **Tests:** bestehende Tests an neue Texte/Struktur anpassen (Knopf „Senden“ → „Test schicken“), nicht löschen.

## Expected Behavior

- **Input:** geöffneter Trip bzw. Orts-Vergleich (Hub), Sprache DE oder EN, Desktop oder Mobil.
- **Output:** Kopf, Reiterleiste und Vorlage-Karte entsprechen dem Mockup; Abgleich meldet für diese Bereiche keine Abweichung ohne Besitzer.
- **Side effects:** keine Datenänderung; nur Besitzer-/Ausnahmen-Daten des Abgleichs.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Unit (node --test) `hub_kopf_c2_mockup.test.ts`: GIVEN Trip-Daten mit Region/Datum WHEN Kopf gerendert THEN Eyebrow „Trip · Region“, Meta „Datum · N Etappen · km · ↑m“; analog Orte.
- [ ] Unit: GIVEN Status entwurf/aktiv/pausiert/archiviert/fertig WHEN Pill gerendert THEN passende Beschriftung, bei Entwurf „Aktivieren“ (DE und EN).
- [ ] Unit: GIVEN 4 Etappen bzw. 3 Orte WHEN Reiterleiste gerendert THEN Badge 4 bzw. 3 und `aria-current` am aktiven Reiter.
- [ ] Unit: GIVEN Vorlage-Karte WHEN gerendert THEN Gruppen Vorlagen/Eigene, kein Mail-Kopf-Satz.
- [ ] Unit: GIVEN Katalog WHEN neue Schlüssel geprüft THEN DE und EN vollständig (`keine_hartkodierten_nutzertexte`, Katalog-Parität).
- [ ] Unit: GIVEN Besitzerliste WHEN geladen THEN kein Eintrag mit Verweis `#2913-c2`; Umgehängte tragen `#2796`.
- [ ] E2E (Playwright, Staging) `hub-kopf-c2-mockup.staging.spec.ts`: Trip und Vergleich, DE und EN, Desktop und Mobil: Kopf, Badge, Vorlage-Karte sichtbar nach Mockup; Name inline ändern bleibt möglich.
- [ ] E2E/Abgleich: `npm run elementliste:abgleich -- --abnahme` gegen Staging, Exit 0 für DE und EN.
- [ ] Bestehende Tests (Liste unter Affected Files) angepasst und grün; Wächter `bausteine_waechter*` grün.

## Definition of Done

Fertig ist Scheibe c2, wenn Kopfleiste (Brotkrumen, Kebab, „Test schicken ▾“), Kopf (Eyebrow, Titel mit Status-Pill, Meta-Zeile), Reiterleiste mit Zähler und Vorlage-Karte von Trip-Hub und Orts-Vergleich-Hub ausschließlich aus Design-System-Bausteinen bestehen (Wächter grün), auf Staging in DE und EN der Elementliste des Mockups entsprechen, keine Besitzer-Einträge `#2913-c2` mehr existieren (Profil/Tempo/Mail-Kopf-Satz sichtbar auf #2796 umgehängt, Menü bei #2797), `npm run elementliste:abgleich -- --abnahme` für DE und EN mit Exit 0 endet, Name/Region für zwei verschiedene Nutzer nach Neuladen erhalten bleiben, der `mockup-bildpruefer` nach höchstens zwei Runden keine offene Abweichung meldet und Henning ein Soll/Ist-Bild des Kopfs bekommen hat (AC-1 bis AC-15).

## Acceptance Criteria

- **AC-1:** Given ein Trip ist im Hub geöffnet (Desktop, DE) / When die Kopfleiste betrachtet wird / Then zeigt sie die Brotkrumen „Trips / <Tripname>“, ein Kebab-Menü „Weitere Aktionen“ und den Knopf „Test schicken ▾“, und der Name in den Brotkrumen führt nicht zurück auf sich selbst, „Trips“ führt zur Trip-Liste.
  - Test: E2E am Trip-Hub: Brotkrumen-Link „Trips“ klicken, Liste erscheint; Knopfbeschriftung geprüft.

- **AC-2:** Given ein Orts-Vergleich ist im Hub geöffnet (Desktop, DE) / When die Kopfleiste betrachtet wird / Then zeigt sie „Orte / <Vergleichsname>“, das Kebab-Menü „Weitere Aktionen“ und den Knopf „Test schicken ▾“, und „Orte“ führt zur Vergleichs-Liste.
  - Test: E2E am Vergleichs-Hub, gleiche Prüfung wie AC-1; Gleichheit mit Trip über `hub-kopf-paritaet-compare-trip`.

- **AC-3:** Given ein Trip mit Region „Mallorca“, vier Etappen, Datum, Strecke und Aufstieg / When der Kopf betrachtet wird / Then steht über dem Titel „Trip · Mallorca“, der Titel trägt eine Status-Pill, und die Meta-Zeile lautet im Format „Datum · 4 Etappen · km · ↑m“.
  - Test: Unit (Kopf mit Fixture) plus E2E am Staging-Trip; Zahlenformat DE „31,5 km“.

- **AC-4:** Given ein Orts-Vergleich mit Region und drei Orten / When der Kopf betrachtet wird / Then steht über dem Titel „Orte · <Region>“ und die Meta-Zeile lautet „3 Orte · Vergleichstabelle · Briefing HH:MM“ (Zeit des konfigurierten Briefings).
  - Test: Unit mit Vergleichs-Fixture plus E2E am Staging-Vergleich.

- **AC-5:** Given ein Trip bzw. Vergleich im Zustand Entwurf, aktiv, pausiert, archiviert oder fertig / When der Titel betrachtet wird / Then zeigt die Status-Pill den passenden Zustand, und im Entwurf bietet der Kopf „Aktivieren“ an; Trip und Vergleich verhalten sich gleich.
  - Test: Unit über alle fünf Zustände für beide Kontexte; E2E: Entwurf aktivieren, Pill wechselt auf „aktiv“.

- **AC-6:** Given ein Trip mit vier Etappen bzw. ein Vergleich mit drei Orten / When die Reiterleiste betrachtet wird / Then lauten die Reiter „Übersicht · Etappen (4) · Wetter · Zustellung“ bzw. „Übersicht · Orte (3) · Wetter · Zustellung“, und der gerade aktive Reiter ist als aktuell markiert (`aria-current`).
  - Test: E2E liest Reiter-Beschriftungen und `aria-current` in beiden Kontexten; Unit für Badge-Zähler.

- **AC-7:** Given ein Trip, dem eine Etappe hinzugefügt wird / When die Reiterleiste neu angezeigt wird / Then steht im Reiter Etappen die neue Anzahl (Zähler folgt den Daten).
  - Test: E2E mit Seed-Trip: Etappe ergänzen, Badge wechselt von N auf N+1; analog Ort im Vergleich.

- **AC-8:** Given der Hub eines Trips oder Vergleichs mit Reiter Wetter / When die Vorlage-Karte betrachtet wird / Then zeigt sie die Überschrift „Vorlage“, den Namen der gewählten Vorlage mit Zustand „unverändert“ bzw. „N Abweichung(en)“, die Aktionen „Als eigene Vorlage speichern“ und „Auf „<Vorlage>“ zurücksetzen“, die Auswahl gliedert sich in „Vorlagen“ und „Eigene“, und der Satz „Name der Vorlage ersetzt das Profil und steht im Kopf der Mail“ erscheint nicht.
  - Test: E2E in Trip und Vergleich: Auswahl öffnen, Gruppen und Texte prüfen, Satz abwesend; Unit für Abweichungszähler.

- **AC-9:** Given ein Trip oder Vergleich im Hub / When Name oder Region geändert werden sollen / Then zeigt der Ruhezustand nur ein Stift-Symbol mit Beschriftung für Screenreader, ein Klick öffnet die Bearbeitung, und nach Speichern erscheinen neuer Name und Region in Brotkrumen, Titel und Eyebrow, ohne dass andere Felder (inkl. Profil) verloren gehen.
  - Test: E2E `hub-kopf-bearbeiten` (Trip und Vergleich): Name ändern, speichern, Seite neu laden, Wert und unverändertes Profil bleiben.

- **AC-10:** Given die Oberfläche ist auf Englisch gestellt / When Trip-Hub und Vergleichs-Hub geöffnet werden / Then erscheinen Brotkrumen, Eyebrow, Pill, Meta-Zeile, Reiter, Vorlage-Karte und Knopf „Send test ▾“ (EN-Wortlaut in `elementliste.json` als Lücke markiert, `text_en: null`; Übersetzung legt diese Scheibe fest und meldet sie an #2968) vollständig auf Englisch ohne deutsche Reste, Protokoll-Token bleiben unübersetzt.
  - Test: E2E in EN für beide Kontexte; Unit Katalog-Parität DE/EN.

- **AC-11:** Given ein Handy-Viewport (Mobil) / When Trip-Hub und Vergleichs-Hub geöffnet werden / Then bleiben Brotkrumen, Titel mit Pill, Reiterleiste mit Badge und „Test schicken ▾“ erreichbar und ohne horizontales Überlaufen bedienbar, auch mit langem Namen.
  - Test: E2E mit Mobil-Viewport (`mobile-ux-messung`), Trip und Vergleich, kein Seiten-Scrollen quer.

- **AC-12:** Given die c2-Besitzer-Einträge sind bearbeitet / When die Besitzerliste geprüft wird / Then enthält sie keinen Eintrag mit Verweis `#2913-c2` mehr; Einträge zu Profil, Tempo-Karte und Mail-Kopf-Satz verweisen auf `#2796` (Grund „Scheibe S4, Datenmodell+Migration“) und nichts davon ist gelöscht; die 8 Einträge für das „Test schicken“-Menü bleiben bei #2797.
  - Test: Unit liest die Besitzerliste als Daten, Anzahl und Verweise geprüft (Doku-Daten; Testdatei trägt Pflicht-Marker `# doc-compliance-test`).

- **AC-13:** Given Staging mit dem Stand dieser Scheibe / When `npm run elementliste:abgleich -- --abnahme` für DE und EN läuft / Then endet der Lauf jeweils mit Exit 0, und eine absichtlich verfälschte Kopf-Beschriftung (Gegenprobe) macht ihn rot.
  - Test: Abgleich-Lauf gegen Staging, Exit-Code DE und EN; Mutations-Gegenprobe per String-Ersetzung am Kopf-Text.

- **AC-14:** Given zwei verschiedene Nutzer mit eigenen Trips und Vergleichen / When beide ihren Hub öffnen / Then sieht jeder nur eigene Namen, Regionen und Zähler; diese Scheibe ändert keinen Endpoint und keine gespeicherten Daten.
  - Test: E2E mit zwei Staging-Nutzern: Brotkrumen und Zähler zeigen je nur die eigenen Daten; Datenstand vor/nach unverändert.

- **AC-15:** Given ein Nutzer im Hub / When der Ruhezustand geprüft wird / Then bleiben Profil-Zeile bzw. Profil-Chip unverändert sichtbar (Entfernung gehört zu #2796), und Tempo/Ankunftszeiten rechnen unverändert.
  - Test: E2E: Profil-Chip vorhanden und änderbar in Trip und Vergleich; Unit `trip_header_status_profil` unverändert grün.

## Known Limitations

- Mockup ist nur Deutsch; EN-Lücken in `elementliste.json` sind #2968 zugeordnet, fehlende EN-Texte werden im Katalog sinnvoll ergänzt und dort vermerkt.
- „Test schicken ▾“ ist in c2 nur Beschriftung; das Menü mit Morgen-/Abend-Briefing kommt mit #2797.
- Profil-Zeile, Tempo-Karte und Mail-Kopf-Satz weichen bis #2796 vom Mockup ab (sichtbar als umgehängte Besitzer-Einträge).
- Abnahme ist nur gegen Staging prüfbar (nicht lokal, nicht Prod).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; berührt ADR-0097 (Teilung Trip/Vergleich), ADR-0104 (Zweisprachigkeit), ADR-0108 (Profil → Vorlage, bleibt #2796), ADR-0112 (Design-System-Bausteine).
- **Rationale:** Reine Darstellungsanpassung innerhalb bestehender Entscheidungen. Der Zuschnitt (Profil/Tempo/Mail-Kopf bei #2796) folgt dem freigegebenen Scheibenplan `docs/context/einstellungen_neu.md` §10; eine „nur Oberfläche über `activity`“-Variante wurde verworfen, weil sie #2796 halb vorwegnähme und Bestandsdaten gefährdete.

## Changelog

- 2026-11-13: Initial spec created (Scheibe c2, Arbeitsplan #2913)
