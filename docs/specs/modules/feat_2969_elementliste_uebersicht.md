---
entity_id: feat_2969_elementliste_uebersicht
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-2969-elementliste-uebersicht
tags: [einstellungen-neu, elementliste, abgleich, uebersicht, besitzer, epic-2913, issue-2969]
---

# Elementliste: Reiter Übersicht (Trip und Orte)

## Approval

- [ ] Approved

## Purpose

Der Reiter Übersicht fehlt in der Elementliste, deshalb besucht der Ganzseiten-Abgleich ihn nie und eine Pauschal-Ausnahme (`{text}`) verdeckt alles, was dort steht. Diese Spec nimmt den einzigen Soll-Teil des Mockups (Bereichskopf mit Titel und Erklärsatz) in die Liste auf und ersetzt die Pauschal-Ausnahme durch einzelne, begründete Ausnahmen für den im Mockup ausdrücklich „unveränderten“ Inhalt. Neue oder geänderte Texte der Übersicht fallen dadurch künftig als `zusaetzlich` auf.

## Source

- **File:** `scripts/elementliste_aus_mockup.ts`, `docs/context/einstellungen_neu/elementliste.json`, `docs/context/einstellungen_neu/elementliste_besitzer.json`
- **Identifier:** Generator-Schleife `KONTEXTE × ZUSTAENDE` (neuer Reiter `uebersicht`, Abschnitt `abschnittskopf`); Besitzerliste `ausnahmen`; Live-Marker `data-abschnitt="abschnittskopf"` in `HubUebersicht.svelte`
- **Schicht:** ausschließlich Frontend-Prüfwerkzeug und Prüfdaten (`scripts/`, `docs/context/`, `frontend/src/lib/__tests__/`). Keine Produktoberfläche, kein Go-API-, kein Python-Core-Code.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung:** Beide Kontexte (`trip`, `orte`) laufen mit derselben Generator- und Abgleichslogik; die Live-Übersicht ist ein gemeinsamer Baustein (`HubUebersicht`, ADR-0097). Kein neuer Baustein.
> - **Mandantentrennung:** Es werden keine Nutzerdaten bewegt; gelesen wird nur über das vorhandene Staging-Prüfkonto. Zwei-Nutzer-Test entfällt.
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt betroffen (E-Mail, Telegram, SMS, Premium-SMS unverändert).

## Scope

### In Scope

1. Generator liest den Reiter Übersicht (Trip, Orte; vier Zustände), nur den Bereichskopf.
2. Regenerierte Elementliste mit 16 neuen Übersicht-Einträgen, bestehende Einträge unverändert.
3. Besitzerliste: Pauschal-Ausnahme für die Übersicht entfällt, Einzel-Ausnahmen für den im Mockup als „unverändert“ markierten Inhalt (DE und EN).
4. Staging-Abnahme DE und EN mit `--abnahme`.

### Nicht-Ziele (ausdrücklich)

- Keine Änderung der Produktoberfläche; der Inhalt der Übersicht bleibt, wie er ist (Mockup: „Unverändert“).
- Keine Änderung am Mockup (Hash bleibt).
- Keine neue Ausnahmeart und keine Änderung der Abgleich-Logik, solange kein Test sie verlangt.
- Der Live-Erklärsatz „Unverändert: …“ wird hier nicht umformuliert (Nebenbefund für #1199).

## Estimated Scope

- **LoC:** ca. +10 Generator, ca. +120 Test, Daten (JSON) je nach Staging-Lesen
- **Files:** 6
- **Effort:** low bis medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | Mockup | Soll-Bild (`viewUebersicht`, Bereichskopf) |
| `frontend/src/lib/i18n/messages/{de,en}` | Katalog | EN-Texte `aktionen.reiter.uebersicht`, `bausteine.hub_uebersicht.kopf_erklaer` |
| `frontend/e2e/elementliste_abgleich_logik.ts` | Modul | Abgleich (`planeLauf`, `findeZusaetzliche`); bleibt unverändert |
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | Komponente | Live-Übersicht mit Bereichskopf-Marker |
| `docs/specs/modules/feat_2913_abgleich_ganzseite.md` | Spec | Vorbild; Übersicht-Ausnahme wird durch diese Spec ersetzt |
| Staging-Prüfkonto (Trip und Orts-Vergleich) | Umgebung | Live-Lesen für Einzel-Ausnahmen und Abnahme |

## Implementation Details

1. **Generator:** Je ctx (trip, orte) × Zustand (normal, laedt, fehler, luecken) zusätzlich Reiter `uebersicht` lesen (Klick `#tabs [data-tab="uebersicht"]`), nur Abschnitt `abschnittskopf` (Titel „Übersicht“, Satz „Unverändert: Stand, letzte Briefings, nächster Versand.“). Die Karte „Im Mockup nicht ausgearbeitet.“ ist Mockup-Notiz und kommt nicht in die Liste. EN aus dem Katalog („Overview“, „Unchanged: status, latest briefings, next delivery.“), `luecke` false. Kopfkommentar im Generator ergänzen.
2. **Liste regenerieren:** Alle 2646 bisherigen Einträge bleiben mit gleichen IDs und Feldern; nur neue Einträge mit Reiter `uebersicht` kommen hinzu (16 = 2 ctx × 4 Zustände × Titel/Satz); Mockup-Hash unverändert.
3. **Besitzerliste:** Die zwei Pauschal-Ausnahmen (ctx trip/orte, Reiter `uebersicht`, Muster `{text}`, Verweis #2969) entfallen. Stattdessen Einzel-Ausnahmen (ctx + Reiter `uebersicht` + `text` oder `muster`) für den unveränderten Live-Inhalt der Übersicht, DE und EN, gewonnen aus einem echten Staging-Lesen. Grund: „Mockup Fassung 4: Inhalt der Übersicht unverändert (viewUebersicht)“, `spec` = diese Spec. Kein Muster, das nur aus einem Platzhalter besteht.
4. **Abgleich:** Hinrichtung prüft den Bereichskopf live (`data-abschnitt="abschnittskopf"`); Gegenrichtung liest den ganzen Hub. Kopf und Reiterleiste werden über die Wetter-Einträge erklärt, der unveränderte Inhalt über die Einzel-Ausnahmen, ein unbekannter Text wird `zusaetzlich`. Die Abgleich-Logik bleibt unverändert, außer ein Test zeigt Bedarf.
5. **Abnahme:** `npm run elementliste:abgleich -- --abnahme` auf Staging für DE und EN mit Exit 0; neue `nicht_pruefbar`/`abweichend` in den Zuständen laedt/fehler/luecken der Übersicht bekommen einen Besitzer mit Grund.
6. **Doku:** In `feat_2913_abgleich_ganzseite.md` Hinweis, dass die Übersicht-Ausnahme durch #2969 ersetzt ist.

## Test Plan

### Automated Tests (TDD RED)

Neue Datei `frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts` (Kern-Schicht, `node --test`, ohne Mocks):

- [ ] GIVEN die regenerierte Elementliste WHEN Einträge mit Reiter `uebersicht` gezählt werden THEN sind es 16, je ctx × Zustand ein Titel und ein Satz mit richtigem DE/EN und Abschnitt `abschnittskopf`
- [ ] GIVEN die Elementliste WHEN nach „Im Mockup nicht ausgearbeitet“ gesucht wird THEN gibt es keinen Eintrag
- [ ] GIVEN die Besitzerliste WHEN Ausnahmen für `uebersicht` geprüft werden THEN gibt es keine Pauschal-Ausnahme (Muster nur aus Platzhalter)
- [ ] GIVEN `findeZusaetzliche` für ctx/Reiter `uebersicht` WHEN Kopf-Text und bekannte Inhaltstexte vorliegen THEN gelten sie als erklärt
- [ ] GIVEN `findeZusaetzliche` für `uebersicht` WHEN ein unbekannter Text vorliegt THEN wird er als `zusaetzlich` gemeldet
- [ ] Bestehende Wächter (`elementliste_aktuell`, `elementliste_bereichskoepfe_3006`, `elementliste_abgleich_ganzseite`, `elementliste_besitzer_kern`, `tests/test_2913_c2_besitzerliste.py`, `tests/test_3007_besitzerliste.py`) bleiben grün

## Acceptance Criteria

- **AC-1:** Given das Mockup Fassung 4 / When der Generator läuft / Then enthält die Elementliste für Trip und Orte in allen vier Zuständen je einen Eintrag für Titel und Erklärsatz des Reiters Übersicht (16 Einträge, Abschnitt `abschnittskopf`) mit EN „Overview“ und „Unchanged: status, latest briefings, next delivery.“
  - Test: Der Listen-Test zählt 16 Übersicht-Einträge mit richtigem DE/EN und Abschnitt.

- **AC-2:** Given die Mockup-Karte „Im Mockup nicht ausgearbeitet.“ / When die Liste erzeugt wird / Then kommt dieser Text nicht als Soll-Eintrag vor, weil er eine Mockup-Notiz und kein Produkttext ist
  - Test: Der Listen-Test findet keinen Eintrag mit diesem Text.

- **AC-3:** Given die bisherige Elementliste mit 2646 Einträgen / When sie neu erzeugt wird / Then bleiben alle bisherigen Einträge mit gleichen IDs und Feldern unverändert, nur Einträge mit Reiter Übersicht kommen hinzu, und der Mockup-Hash-Test bleibt grün
  - Test: Der Aktualitäts-/Hash-Test und ein Vergleich der alten gegen die neue Liste bestehen.

- **AC-4:** Given die Besitzerliste / When sie geladen wird / Then gibt es keine Pauschal-Ausnahme mehr für den Reiter Übersicht, sondern Einzel-Ausnahmen für den unveränderten Live-Inhalt (DE und EN) mit Grund „Mockup Fassung 4: Inhalt der Übersicht unverändert (viewUebersicht)“ und Verweis auf diese Spec
  - Test: Der Besitzer-Test findet keine Ausnahme, deren Muster nur aus einem Platzhalter besteht, und jede Übersicht-Ausnahme trägt Grund und Spec.

- **AC-5:** Given eine Live-Übersicht mit Kopf, Reiterleiste und bekanntem Inhalt / When `findeZusaetzliche` die Texte prüft / Then gelten Kopf-Text und bekannte Inhaltstexte als erklärt und ein neuer, unbekannter Text wird als `zusaetzlich` gemeldet
  - Test: Der Logik-Test übergibt bekannte und einen unbekannten Text und erwartet genau diesen als zusätzlich.

- **AC-6:** Given der Staging-Lauf für Trip und Orte / When der Abgleich den Reiter Übersicht besucht / Then wird der Bereichskopf live gegen die Liste geprüft (Hinrichtung) und der ganze Hub gelesen (Gegenrichtung)
  - Test: Der Staging-Bericht enthält für `uebersicht` geprüfte Elemente mit Status `ok` im Bereichskopf.

- **AC-7:** Given Staging und die neue Besitzerliste / When `npm run elementliste:abgleich -- --abnahme` für DE und EN läuft / Then ist der Exit 0, und jedes neue `nicht_pruefbar` oder `abweichend` der Übersicht in laedt/fehler/luecken hat einen Besitzer mit Grund
  - Test: Beide Abnahme-Läufe enden mit Exit 0, der Bericht zeigt keine herrenlose Übersicht-Abweichung.

- **AC-8:** Given die Spec des Vorgängers / When #2969 ausgeliefert ist / Then vermerkt `feat_2913_abgleich_ganzseite.md`, dass die Übersicht-Ausnahme durch #2969 ersetzt ist
  - Test: Doku-Pflege (`# doc-compliance-test`-Ausnahme); Nutzerverhalten wird durch AC-6 und AC-7 bewiesen.

## Definition of Done

- AC-1 bis AC-8 erfüllt und durch die genannten Tests belegt; Mutations-Gegenprobe ohne unbewachte Verfälschung.
- Kern-Tests und bestehende Elementlisten-Wächter grün; alle sechs CI-Checks grün.
- Staging-Lauf DE und EN mit `--abnahme` Exit 0.
- Keine Produktfunktion verändert.

## Known Limitations

- Der Inhalt unter dem Bereichskopf ist im Mockup nicht gestaltet; die Einzel-Ausnahmen halten den heutigen Live-Stand als Soll („unverändert“) fest. Ändert sich der Inhalt bewusst, müssen die Ausnahmen mit angepasst werden.
- Gegenrichtung weiterhin nur Desktop und Zustand `normal` (siehe Vorgänger-Spec).
- Nebenbefund, nicht im Scope: Der Live-Erklärsatz „Unverändert: …“ gibt eine Mockup-Notiz wieder; das geht in Sammel-Issue #1199.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es ändern sich nur Prüfwerkzeug und Prüfdaten (Erweiterung aus ADR-0112); kein Kanal, Provider, Datenmodell oder Auth betroffen.

## Changelog

- 2026-11-19: Initial spec created (Issue #2969, Epic #2913, Workflow feat-2969-elementliste-uebersicht)
