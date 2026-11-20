---
entity_id: fix_3192_wetter_dialog_abgleich
type: refactor
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: fix-3192-wetter-dialog-abgleich
tags: [elementliste, abgleich, wetter, epic-2913, pruefwerkzeug]
---

# Elementlisten-Abgleich: Wetter-Dialoge auf Mockup-Datenlage (Issue #3192, Epic #2913)

## Approval

- [ ] Approved

## Purpose

Der Staging-Abgleich misst die Wetter-Dialoge (Grenzen ändern, Vorlage wählen, bestätigen, speichern) auf einem eigenen Prüf-Datensatz statt auf der Mockup-Datenlage; deshalb bleiben 56 der 156 Besitzer-Einträge `#3111` „nicht gefunden“. Diese Spec richtet Prüf-Datensatz und Bedienplan an der Mockup-Lage aus, räumt die `#3111`-Einträge ab und weist zusätzlich nach (F004), dass eine frisch gespeicherte eigene Vorlage sofort im Menü erscheint. Kein Produktcode wird geändert.

## Source

- **File:** `frontend/e2e/elementliste-abgleich.staging.spec.ts`, `frontend/e2e/elementliste_abgleich_logik.ts`
- **Identifier:** `sichtbareTexte`, `wetterPruefDaten`, `bedienPlan`, `ordneAbschnitte`
- **Soll-Quelle:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (Z. 460-488)

> **Schicht:** nur Prüfwerkzeug und Testdaten (Playwright/Node), kein Go-, Python- oder Svelte-Produktcode.
>
> **Mandantentrennung:** Prüf-Datensätze nur im Prüfkonto, mit eigenen IDs und Namen; kein Zugriff auf Daten anderer Nutzer. Der GR221-Seed des Prüfkontos (#2967) bleibt unberührt.
>
> **Trip/Ortsvergleich-Teilung:** Geteilter Code bleibt unverändert; beide Kontexte (`route`, `vergleich`) werden gemessen.
>
> **Kanäle:** nicht betroffen (nur Editor-Oberfläche).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| feat_3111_wetter_dialoge_mockup | spec | Soll der Dialoge, Auslöser dieses Nachfolgers |
| feat_2967_pruefkonto_mockupdaten | spec | Seed des Prüfkontos (bleibt unberührt) |
| feat_2968_elementliste_en_zuordnung | spec | EN-Zuordnung der Elementliste |
| `scripts/elementliste_aus_mockup.ts` | script | Erzeugt `elementliste.json` inkl. `text_en` |
| `/api/trips`, `/api/compare/presets`, `/api/locations`, `/api/metric-presets`, `/api/templates` | API | Anlegen und Aufräumen der Prüf-Datensätze, Vorlagenliste |
| Issues #3151, #3189, #3190 | issue | Ziel für begründet umgehängte Restabweichungen |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/e2e/elementliste-abgleich.staging.spec.ts | MODIFY | Prüf-Datensätze je Kontext zweifach, Mockup-Lage, eigene Vorlage je Art, Seiten-ID je Abschnitt, Platzhalter aus `<textarea>` |
| frontend/e2e/elementliste_abgleich_logik.ts | MODIFY | Wechselziel je Kontext, Datensatzwahl je Abschnitt (reine Funktion), Override-Bau |
| frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts | MODIFY | Unit-Tests für die neuen reinen Funktionen |
| docs/context/einstellungen_neu/elementliste.json | MODIFY | Neu erzeugt, `text_en` der #3111-Texte |
| frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts | MODIFY | `ALT_SHA` mit Begründung nachgezogen |
| docs/context/einstellungen_neu/elementliste_besitzer.json | MODIFY | `#3111`-Einträge abräumen bzw. begründet umhängen |
| tests/test_2913_c2_besitzerliste.py | MODIFY | Zählwächter an Reststand angepasst |
| frontend/e2e/s3a2794-teil3-vorlage.spec.ts | MODIFY | F004: Browser-Test mit echtem Speichern (schreibend, eigener Datensatz, Aufräumen) |

## Estimated Scope
- **LoC:** +200/-60 (ohne generierte JSON-Dateien)
- **Files:** 8
- **Effort:** medium (nur Prüfwerkzeug und Testdaten, aber Staging-Lauf DE/EN und Besitzer-Neuordnung)

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Prüfwerkzeug ohne Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor, Test-/Deploy-Strategie unberührt); das Mockup als Soll folgt Epic #2913.

## Implementation Details

1. **Zwei Datensätze je Kontext.** Das Mockup ist in sich widersprüchlich: der Abweichend-Satz steht im Grenzen-Dialog statisch immer, die Bestätigung zeigt keinen Verlust-Satz (Ausgangslage ohne Abweichungen). Das Produkt koppelt beides an echte Abweichungen (#3111 AC-2/AC-6). Daher: Datensatz „mit Abweichung“ (je Briefing-Metrik ein gültiger Override `lower`/`upper` aufsteigend, Seite gemäß `allowed_sides`; Gewitter über `ampel.thunder`) misst die `grenzen-*`-Abschnitte; Datensatz „ohne Abweichung“ (nur Vorlage und Metrik-Auswahl) misst `vorlage-*`. Die Seiten-ID je Abschnitt liefert eine reine, unit-getestete Funktion; jeder Bedien-Abschnitt lädt ohnehin eine frische Seite.
2. **Mockup-Lage.** Trip: aktiv `alpen-trekking`, Wechselziel `wandern`. Orte: aktiv `allgemein`, Wechselziel `alpen-trekking`, Vergleich mit 3 Orten (Bestätigung „für diese Orte“). Fehlt das Mockup-Ziel in `/api/templates`, meldet der Plan `nicht_herstellbar` mit Grund; der Fallback „erste andere Vorlage“ greift nur, wenn es für den Kontext kein Mockup-Ziel gibt.
3. **Eigene Vorlage je Art** (`route`, `vergleich`) mit Beschreibung „aus GR221 gespeichert“ im Prüf-Datensatz, damit „eigene · aus GR221 gespeichert“ in beiden Listen steht. Eindeutiger Prüf-Name, Reste eines abgebrochenen Laufs vorher löschen, im `finally` aufräumen.
4. **Messinstrument:** `sichtbareTexte` liest Platzhalter zusätzlich aus `<textarea>`.
5. **EN:** Elementliste neu erzeugen; `ALT_SHA` ändert sich bewusst (nur `text_en` befüllt), Begründung im Test; Anzahl 2646 und Mockup-Hash bleiben.
6. **Abschluss:** Staging-Abgleich DE und EN; gefundene `#3111`-Einträge entfernen, Rest je Eintrag begründet umhängen (Beispielzahlen der Vorlagen-Unterzeilen an #3151, Herkunftszeile an #3189, Speichern-Dialog an #3190); kein Eintrag bleibt an #3111; Zählwächter anpassen.
7. **F004** als eigener schreibender Browser-Test, nicht im lesenden Abgleich (dort gilt Schreibanfrage = Fehlschlag, #2966 AC-7).

## Expected Behavior

- **Input:** Staging-Abgleich `--scope wetter` (DE, EN) mit dem Prüfkonto; Browser-Test für F004.
- **Output:** Wetter-Dialog-Einträge werden auf Mockup-Datenlage gemessen; Besitzerliste ohne `#3111`.
- **Side effects:** Prüf-Datensätze werden angelegt und im selben Lauf gelöscht; Produktdaten und GR221-Seed unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Unit: GIVEN Abschnitt-ID WHEN die Seiten-ID bestimmt wird THEN liefert `grenzen-*` den Datensatz „mit Abweichung“ und `vorlage-*` den Datensatz „ohne Abweichung“.
- [ ] Unit: GIVEN Briefing-Metrik mit `allowed_sides` WHEN der Override gebaut wird THEN ist er gültig (lower/upper aufsteigend, nur erlaubte Seite), Gewitter als `thunder`.
- [ ] Unit: GIVEN Kontext trip/orte und Vorlagenliste WHEN das Wechselziel bestimmt wird THEN `wandern` bzw. `alpen-trekking`; fehlt es, `nicht_herstellbar` mit Grund; Fallback nur ohne Mockup-Ziel.
- [ ] Browser/Staging: Abgleich `--scope wetter` DE und EN, Bericht ohne `#3111`-Treffer außer begründet umgehängten.
- [ ] Browser: F004 speichern und Menü lesen, Testdaten aufgeräumt.
- [ ] `tests/test_2913_c2_besitzerliste.py`, `elementliste_uebersicht_2969.test.ts`, `elementliste_en_zuordnung_2968` grün.

## Acceptance Criteria

- **AC-1:** Given der Abgleich legt für Trip und Orte je zwei Prüf-Datensätze an / When die Grenzen-Abschnitte und die Vorlage-Abschnitte gemessen werden / Then misst „mit Abweichung“ (gültiger Grenzen-Override je Briefing-Metrik gemäß erlaubter Seite, Gewitter über `thunder`) die `grenzen-*`-Einträge und „ohne Abweichung“ die `vorlage-*`-Einträge, und die Wahl der Seite je Abschnitt ist eine reine, unit-getestete Funktion.
  - Test: Unit-Test der Seitenwahl und des Override-Baus; Staging-Lauf zeigt Abweichend-Satz im Grenzen-Dialog und keinen Verlust-Satz in der Bestätigung.

- **AC-2:** Given die Mockup-Datenlage / When der Abgleich die Vorlagen-Bestätigung herstellt / Then ist beim Trip „Alpen-Trekking“ aktiv und „Wandern“ das Wechselziel, bei Orten „Allgemein“ aktiv und „Alpen-Trekking“ das Wechselziel mit drei Orten („für diese Orte“); fehlt das Ziel in der Vorlagenliste, meldet der Abgleich „nicht herstellbar“ mit Grund und nie still, und die erste andere Vorlage dient nur als Ersatz, wenn es kein Mockup-Ziel gibt.
  - Test: Unit-Tests der Wechselziel-Wahl (Ziel vorhanden, Ziel fehlt, kein Mockup-Ziel); Staging-Lauf belegt die Bestätigungstexte.

- **AC-3:** Given der Abgleich läuft gegen das Prüfkonto / When er startet und endet / Then liegt je Art (Trip, Vergleich) eine eigene Vorlage mit Beschreibung „aus GR221 gespeichert“ im Prüf-Datensatz, Reste eines früheren Abbruchs sind vorher gelöscht, alles ist im `finally` aufgeräumt, und der GR221-Seed des Prüfkontos ist danach unverändert.
  - Test: Staging-Lauf mit absichtlich vorhandenem Rest; danach Liste der Vorlagen und Trips des Prüfkontos gleich wie vor dem Lauf.

- **AC-4:** Given ein Dialog mit Platzhaltertext in einem mehrzeiligen Textfeld / When der Abgleich die sichtbaren Texte sammelt / Then erscheint der Platzhalter des Textfelds in der Liste wie der eines einzeiligen Felds.
  - Test: Unit-/Browser-Test mit einer Seite, die einen Platzhalter nur in einem Textfeld trägt.

- **AC-5:** Given die #3111-Texte tragen noch kein Englisch in der Elementliste / When die Elementliste neu erzeugt wird / Then enthalten sie `text_en`, der Pin `ALT_SHA` ist mit Begründung nachgezogen, und Anzahl 2646 sowie Mockup-Hash sind unverändert.
  - Test: `elementliste_uebersicht_2969.test.ts` grün mit neuem Pin und dokumentierter Begründung.

- **AC-6:** Given der Staging-Abgleich ist in Deutsch und Englisch gelaufen / When die Besitzerliste ausgewertet wird / Then sind alle als gefunden belegten `#3111`-Einträge entfernt, jeder verbleibende Eintrag ist begründet umgehängt (#3151 Beispielzahlen der Vorlagen-Unterzeilen, #3189 Herkunftszeile, #3190 Speichern-Dialog), kein Eintrag bleibt an #3111, der Zählwächter stimmt, und der EN-Zuordnungstest ist grün.
  - Test: `tests/test_2913_c2_besitzerliste.py` und `elementliste_en_zuordnung_2968` grün; Abgleichsbericht DE/EN ohne offene `#3111`-Treffer.

- **AC-7:** Given der Abgleich bedient die Wetter-Dialoge auf den neuen Datensätzen / When während der Bedienung eine Schreibanfrage ausgelöst wird / Then gilt das weiterhin als Fehlschlag des Abgleichs (lesend, #2966 AC-7); das Anlegen und Aufräumen der Prüf-Datensätze liegt außerhalb der Bedienung.
  - Test: Bestehender Schreibschutz-Test der Verdrahtung bleibt grün; Abgleichslauf meldet keine Schreibanfrage während der Bedienung.

- **AC-8:** Given Trip oder Orte mit geöffnetem Wetter-Reiter / When der Nutzer eine eigene Vorlage mit Beschreibung speichert / Then erscheint sie ohne Neuladen im Vorlagen-Menü als „eigene · <Beschreibung>“, und die Testdaten sind danach gelöscht.
  - Test: Browser-Test (Trip und Orte) speichert wirklich, liest das Menü, räumt in `finally` auf.

## Definition of Done

- AC-1 bis AC-8 durch Tests belegt, Kern-Tests grün, alle 6 CI-Checks grün
- Elementlisten-Abgleich `--scope wetter` auf Staging in DE und EN ohne „nicht gefunden“ für die Wetter-Dialog-Einträge, die die Mockup-Lage abbildet
- Kein Besitzer-Eintrag mehr an `#3111`; jeder Rest mit Grund an #3151, #3189 oder #3190; Zählwächter und EN-Zuordnungstest grün
- Änderung in `main`, Ergebnis (Abgleich-Zahlen DE/EN) im Issue dokumentiert

## Changelog

- 2026-11-20: Initial spec created
