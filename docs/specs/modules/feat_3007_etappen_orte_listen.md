---
entity_id: feat_3007_etappen_orte_listen
type: feature
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: 3007-etappen-orte-listen
issue: 3007
tags: [einstellungen-neu, listenzeile, etappen, orte, abgleich, epic-2913, issue-3007]
---

# Einstellungen neu: Listen der Reiter Etappen und Orte nach Mockup

## Approval

- [ ] Approved

## Purpose

Die Reiter Etappen (Trip) und Orte (Orts-Briefing) zeigen ihre Listen künftig wie im freigegebenen Mockup `mockup-hub-fassung3.html`: eine ruhige Zeile je Etappe bzw. Ort aus einem gemeinsamen Design-System-Baustein, in DE und EN aus dem Katalog. Heute ist Etappen ein voller Editor ohne Listenansicht und Orte eine Liste mit Rang-Badge, Hinweis und ✕. Der Elementlisten-Abgleich soll für beide Reiter keine Abweichung und keine Fremdtexte mehr melden (Teil von Epic #2913).

## Source

- **File:** `frontend/src/lib/components/molecules/Listenzeile.svelte` (neu, Ablage unter `molecules/`, siehe Implementation Details)
- **Identifier:** `Listenzeile` (auf Basis `Einstellungszeile`), eingesetzt in `CompareTabs` (Orte) und `EditStagesPanelNew` (Etappen)
- **Schicht:** ausschließlich Frontend (`frontend/src/...`) plus Doku-Daten des Abgleichs (`docs/context/einstellungen_neu/`). Kein Go-API-, kein Python-Core-Code, keine Schema-Änderung.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung (ADR-0097):** Ein Zeilen-Baustein für beide Listen; kein Orte-eigenes Pendant. Eigen je Kontext sind nur die Zeileninhalte (Etappen: Titel, Kennzahlen, Gehzeit; Orte: Name, Gruppe, Höhe) und der Aufklapp-Inhalt (Editor bzw. Orte-Panel), wie im Mockup.
> - **Mandantentrennung:** Reine Darstellung; „entfernen“ und Sortieren nutzen unveränderte Handler und Endpunkte. Kein neuer Endpunkt, daher kein neuer Zwei-Nutzer-Test; die bestehenden Speicherwege bleiben unberührt.
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt ändert sich; E-Mail, Telegram, SMS und Premium-SMS nicht betroffen.

## Estimated Scope

- **LoC:** ca. +600 / −250 (inkl. Tests) in zwei Teilschritten
- **Files:** ca. 10 Quell-/Daten-Dateien plus ca. 10 bis 12 E2E-Specs
- **Effort:** high (Etappen-Editor ist zentraler Arbeitsbereich, viele Bestands-E2E)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Soll | `viewEtappen` Z. 577-587, `viewOrte` Z. 588-591, CSS `.lrow` Z. 140-143, `.meta` Z. 40, `.btn.sm` Z. 46, `.btn.quiet` Z. 50, `.card` Z. 72 |
| `molecules/Einstellungszeile.svelte` | Molekül (ADR-0112) | vorhandene `.lrow`-Zeile (Titel, Hinweis, Snippet rechts); Basis des Bausteins |
| `atoms/Btn.svelte`, `atoms/Card.svelte` | Atome | Textknopf „entfernen“ (`sm`, `quiet`), Karte um die Liste |
| `SortableList` / `DragHandle` | Bausteine | Reihenfolge der Orte (bleibt) |
| `molecules/Bereichskopf.svelte` | Molekül (#3006) | Köpfe beider Reiter, unverändert |
| `computeArrivalTimes`, `activityToSpeed` (`EditStagesPanelNew`) | vorhandene Gehzeit-Rechnung | Gehzeit je Etappe; nicht das veraltete `naismithHours` |
| `Stage.distanceKm`, `Stage.ascentM` (`utils/tripStats.ts`) | Daten | Kennzahlen „x km · ↑y m“ |
| `loc.group`, `loc.elevation_m` | Daten | Orte-Zeile „Gruppe · Höhe m“ |
| i18n-Katalog (ADR-0104) | Katalog | Nutzertexte DE+EN; vorhanden u. a. `layout.ausgabe.entfernen`, `vergleich.hub.ziehen_sortieren`, `trip.hub.kopf.etappen_*` |
| `elementliste.json`, `elementliste_besitzer.json` | Soll-/Besitzerdaten | 76 `luecke:true`-Einträge; Besitzer-Einträge 337/338/346/347/746/747 |
| `frontend/e2e/elementliste_abgleich_logik.ts`, `elementliste-abgleich.staging.spec.ts` | Abgleich | liest `data-abschnitt` in `[data-seite="hub"]`; zählt sichtbare Fremdtexte |
| `tests/test_2913_c2_besitzerliste.py` | Konsistenztest | Besitzerliste |
| `docs/specs/modules/feat_3006_bereichskoepfe.md`, `docs/specs/_archive/modules/issue_503_wegpunkt_editor_fix.md`, `docs/specs/modules/mobile_stages_tab_listen_only.md` | Specs | Vorgänger und Bestandsverhalten |
| Issues #2796, #2798, #3006 | Abgrenzung | #2796 Tempo/Fortbewegung (offen); #2798 1..n Orte, Ein-Ort-Briefing (offen); #3006 Köpfe (geliefert) |

## Scope

### Nicht-Ziele

- Tempo-Karte (Fortbewegung, Tempo flach, Aufstieg) und Knopf „Tempo ändern“: #2796. Die Elementlisten-Einträge „Tempo ändern“ bekommen Besitzer-Einträge `art:element` mit Verweis #2796; der Besitzer-Eintrag `tempo` (Index 339) bleibt.
- Mehrere Orte vs. Ein-Ort-Briefing: #2798.
- Bereichsköpfe: #3006.
- Der Anlegen-Editor (`TripNewEditor`) und der Mobil-Zweig der Etappen (`mobile-stages-list`, `StageCardM`, PO-Entscheid F5) bleiben unverändert.
- Keine Funktion entfällt still: Editor-Funktionen der Etappen (Karte, Profil, Wegpunkte, Datum, Startzeit, Pausentag, Kaskade, Löschen) und Orte-Funktionen (Sortieren, Aufklapp-Panel, Hinzufügen) bleiben.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/molecules/Einstellungszeile.svelte` | MODIFY | optional klickbar: `role="button"`, `tabindex`, `aria-expanded`, Enter/Leertaste; ohne Option unverändert |
| `frontend/src/lib/components/molecules/Listenzeile.svelte` | CREATE | gemeinsamer Zeilen-Baustein Trip/Orte: Titel, Zweitzeile, Meta rechts, Aktions-Snippet, optional klickbar, optional Ziehgriff-Slot |
| `frontend/src/lib/components/molecules/index.ts` | MODIFY | Export |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Orte-Liste nach Mockup, `data-abschnitt="liste"`; Hinweis, Rang-Badge, Wechselfarbe, ✕ raus; Textknopf „entfernen“; Ziehgriff und Panel bleiben |
| `frontend/src/lib/components/molecules/CompareLocationRow.svelte` | DELETE | nach `grep -rn CompareLocationRow` nur wenn kein weiterer Nutzer |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY | Prop `listeZuerst` (Standard `false`): Liste `data-abschnitt="liste"` und Aufklapp-Editor je Etappe; Desktop-Strip im Hub-Modus ersetzt |
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | MODIFY | Prop durchreichen |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Hub-Modus einschalten |
| `frontend/src/lib/i18n/messages/de/*.json`, `en/*.json` | MODIFY | neue Schlüssel (Gehzeit, Kennzahl-Muster, Etappen-Titel, „entfernen“ falls nicht vorhanden) |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | 76 `luecke:true`-Einträge auf `i18n_key`/`text_en`/`luecke:false`, IDs unverändert |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | Einträge 337/338/346/347/746/747 raus (337/346 nur, wenn der Abgleich den Kopf findet); „Tempo ändern“-Elemente neu als `art:element` → #2796 |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY | Konsistenz nachziehen |
| `frontend/src/lib/components/molecules/__tests__/listenzeile*.test.ts` u. a. | CREATE | SSR-Tests Baustein, Orte-Liste, Etappen-Liste |
| Bestands-E2E: `etappen-strip-*`, `waypoints-editor`, `issue-407`, `issue-498`, `hub-editor-autosave-*`, `hub-save-chip`, `fix-2954`, `trip-hub-etappenliste-titel`, `compare-hub-inline-edit` u. a. | MODIFY | Zeilenklick vor Editor; Erwartungen an Rang/✕/Hinweis angleichen; nicht löschen |

## Implementation Details

**Baustein.** `Listenzeile` setzt auf `Einstellungszeile` auf (kein zweites `.lrow`): linke Spalte Titel (fett) und Zweitzeile (klein, `--g-ink-3`), rechts Meta (Mono, `--g-ink-3`) und Aktions-Snippet. Optional klickbar: dann `role="button"`, `tabindex="0"`, `aria-expanded`, Enter und Leertaste lösen den Klick aus. Maße nur über Design-Tokens (Wächter `bausteine_waechter*`). Beide Reiter verwenden ihn, es gibt kein Orte-eigenes Pendant.

**Orte (Teilschritt 1).** Zeile: Name als Titel, Zweitzeile „Gruppe · Höhe m“. Fehlt Gruppe oder Höhe, steht nur der vorhandene Teil ohne verwaistes „·“; fehlen beide, entfällt die Zweitzeile. Rechts Textknopf „entfernen“ (`Btn` sm quiet) mit unverändertem Handler und Testid `hub-orte-remove`. Entfallen: Rang-Badge, `hub-section-hint`, Wechselfarbe, ✕. Der Ziehgriff bleibt textlos mit `aria-label`, die Reihenfolge der Vergleichstabelle bleibt sortierbar. Aufklapp-Panel (`hub-orte-panel`) und Hinzufügen (`hub-orte-add`, im Kopf seit #3006) bleiben. Container der Liste trägt `data-abschnitt="liste"`.

**Etappen (Teilschritt 2).** Im Hub (Prop `listeZuerst`) zeigt der Reiter nur die Liste in einer Karte, eine Zeile je Etappe: „E{n} · Start → Ziel“, Zweitzeile „x km · ↑y m“, rechts Meta „Gehzeit h:mm“. Die Gehzeit kommt aus der vorhandenen Rechnung (`computeArrivalTimes`, `activityToSpeed`). Ein Pausentag hat Titel, aber keine Kennzahlen und keine Gehzeit. Fehlen Distanz oder Aufstieg, entfällt nur der fehlende Teil. Klick oder Enter klappt den unveränderten bestehenden Editor für diese Etappe unter der Zeile auf (Karte, Profil, Wegpunkte, Datum, Startzeit, Pausentag), erneuter Klick schließt ihn; es ist höchstens ein Editor gleichzeitig offen. Begründung: Der Abgleich zählt jeden sichtbaren Text als Fremdtext, und die Grundentscheidung verlangt „Etappen und Wegpunkte unverändert“; das Aufklapp-Muster existiert bereits im Orte-Reiter. Ohne `listeZuerst` (Anlegen-Editor) und im Mobil-Zweig bleibt alles wie bisher. Kein Knopf „Tempo ändern“ in dieser Scheibe.

**Katalog und Daten.** Nutzertexte nur über den Katalog, DE und EN. Protokoll-Token und Zahlen werden nicht übersetzt. `elementliste.json`: die 76 Einträge (10 + 9 je vier Zustände) per Skript auf Schlüssel, EN-Text und `luecke:false`, IDs unverändert. Offene Punkte, die in Phase 3/4 geklärt werden: Mehrfachtreffer bei Gehzeit in allen Zeilen (Elementliste führt nur E1) und ob der Abgleich den Kopf findet (Besitzer 337/346).

**Prüf-Datensatz.** Der Staging-Prüf-Trip braucht Etappen mit Distanz und Aufstieg, der Prüf-Vergleich Orte mit Gruppe und Höhe; sonst wird der Prüf-Datensatz ergänzt.

**Zwei Teilschritte.** 1: Baustein, Einstellungszeile klickbar, Orte, zugehörige Katalog- und Elementlisten-Einträge. 2: Etappen, restliche Einträge, Besitzerliste, Staging-Abgleich `--abnahme`. Jeder Teilschritt bleibt im LoC-Rahmen und ist für sich auslieferbar.

**Mutation/Adversary.** Der Validator verfälscht gezielt per String-Ersetzung (Sicherungskopie extern, kein `git checkout/stash/reset`), u. a.: „entfernen“-Handler vertauschen, „·“-Trennung immer setzen, Gehzeit auf falsche Etappe, `aria-expanded` konstant, Aufklapp-Editor für falsche Etappe, `data-abschnitt` entfernen. Jede Verfälschung muss einen Test rot machen, dort, wo die Zusicherung wirkt (Render bzw. Browser).

## Expected Behavior

- **Input:** geöffneter Trip mit Etappen bzw. Orts-Briefing mit Orten, Reiter Etappen bzw. Orte, Sprache DE oder EN.
- **Output:** Liste wie im Mockup; Etappenzeile klappt den bestehenden Editor auf; Ort lässt sich per Textknopf entfernen und per Ziehgriff sortieren.
- **Side effects:** keine neuen; Speichern, Entfernen und Sortieren laufen über die bisherigen Wege.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `listenzeile*.test.ts` (node --test, SSR): GIVEN Titel, Zweitzeile, Meta, Aktion WHEN gerendert THEN Elemente in Mockup-Reihenfolge; ohne Zweitzeile/Meta kein leerer Platzhalter; klickbare Variante trägt `role="button"`, `tabindex`, `aria-expanded`.
- [ ] Orte SSR (DE/EN): GIVEN Orte mit/ohne Gruppe bzw. Höhe WHEN gerendert THEN „Gruppe · Höhe m“, ohne verwaistes „·“; Textknopf „entfernen“ (kein ✕), kein Rang-Badge, kein `hub-section-hint`, Ziehgriff mit `aria-label`, `data-abschnitt="liste"`.
- [ ] Etappen SSR (DE/EN): GIVEN Trip mit Etappen und einem Pausentag WHEN Hub-Modus gerendert THEN „E{n} · Start → Ziel“, „x km · ↑y m“, „Gehzeit h:mm“, Pausentag ohne Kennzahlen, kein „Tempo ändern“, `data-abschnitt="liste"`, Editor zunächst nicht sichtbar; Anlegen-Editor unverändert.
- [ ] Katalog-Parität und Wächter `keine_hartkodierten_nutzertexte`, `bausteine_waechter*` grün.
- [ ] Datentest (`# doc-compliance-test`): 76 Einträge ohne `luecke:true`, IDs unverändert; Besitzerliste-Konsistenz (`tests/test_2913_c2_besitzerliste.py`) grün.
- [ ] E2E (Playwright, Staging): Etappenzeile anklicken, Editor sichtbar, Datum/Startzeit/Pausentag änderbar und gespeichert; Orte: „entfernen“, Sortieren, Panel, Hinzufügen; Bestands-Specs angepasst und grün.
- [ ] Abgleich `elementliste:abgleich --abnahme` gegen Staging, DE und EN: keine Abweichung und kein Fremdtext für `trip/etappen` und `orte/orte`; Mutations-Gegenprobe (Textänderung in der Zeile) macht ihn rot.
- [ ] Keine Mock-Theater: SSR-Render echter Komponenten, E2E gegen echtes Staging.

## Definition of Done

Fertig ist #3007, wenn beide Listen den gemeinsamen Baustein nutzen, Texte DE und EN aus dem Katalog kommen, alle Editor- und Orte-Funktionen erhalten sind, der Abgleich auf Staging für `trip/etappen` und `orte/orte` weder Abweichung noch Fremdtext meldet, die Sammel-Einträge `{text}` dieser Reiter aus der Besitzerliste entfernt sind und Henning ein Soll/Ist-Bild beider Reiter bekommen hat.

## Acceptance Criteria

- **AC-1:** Given der Baustein Listenzeile wird mit Titel, Zweitzeile, Meta und Aktion gerendert / When die Struktur betrachtet wird / Then stehen Titel (fett) und Zweitzeile links und Meta sowie Aktion rechts, aufgebaut auf der Einstellungszeile, und ohne Zweitzeile oder Meta entsteht kein leerer Platzhalter.
  - Test: SSR-Render mit node --test, Struktur und Reihenfolge, beide Varianten.

- **AC-2:** Given die Zeile ist als klickbar konfiguriert / When sie mit der Tastatur bedient wird / Then ist sie fokussierbar, trägt `role="button"` und `aria-expanded`, und Enter sowie Leertaste lösen dieselbe Aktion aus wie ein Klick; ohne Konfiguration verhält sich die Einstellungszeile unverändert.
  - Test: SSR-Render beider Varianten; Browser-Test Tastaturbedienung im Staging-E2E.

- **AC-3:** Given Trip und Orts-Briefing / When die Listen beider Reiter betrachtet werden / Then nutzen beide denselben Baustein Listenzeile, und es gibt kein Orte-eigenes Zeilen-Pendant mehr (`CompareLocationRow` ist entfernt oder ungenutzt).
  - Test: SSR-Render beider Reiter mit gemeinsamem Marker; Struktur-Test (`# doc-compliance-test`) auf Nichtvorhandensein.

- **AC-4:** Given ein Orts-Briefing mit Orten, die Gruppe und Höhe haben / When der Reiter Orte geöffnet wird / Then zeigt jede Zeile den Ortsnamen und darunter „Gruppe · Höhe m“, in der Reihenfolge des Mockups, in DE und EN.
  - Test: SSR-Render in DE und EN; Staging-E2E mit Prüf-Vergleich.

- **AC-5:** Given ein Ort ohne Gruppe oder ohne Höhe / When der Reiter Orte geöffnet wird / Then zeigt die Zeile nur den vorhandenen Teil ohne verwaistes „·“, und fehlen beide, entfällt die Zweitzeile.
  - Test: SSR-Render mit den drei Randfällen.

- **AC-6:** Given der Reiter Orte / When die Zeilen betrachtet werden / Then gibt es keinen Rang-Badge, keinen Reihenfolge-Hinweis, keine Wechselfarbe und kein ✕; stattdessen steht rechts der Textknopf „entfernen“ (EN-Entsprechung aus dem Katalog) als kleiner, ruhiger Knopf.
  - Test: SSR-Render in DE und EN.

- **AC-7:** Given der Reiter Orte mit mindestens zwei Orten / When „entfernen“ bei einem Ort angeklickt wird / Then wird genau dieser Ort entfernt wie bisher mit dem unveränderten Handler, und der Knopf trägt weiter die Testid `hub-orte-remove`.
  - Test: Staging-E2E (Ort entfernen, Liste kürzer, andere Orte unverändert); bestehendes `compare-hub-inline-edit.spec.ts` grün.

- **AC-8:** Given der Reiter Orte / When die Reihenfolge per Ziehgriff geändert wird / Then bleibt Sortieren möglich und gespeichert, der Ziehgriff hat keinen sichtbaren Text, aber ein `aria-label` aus dem Katalog.
  - Test: SSR-Render (aria-label, kein Text); Staging-E2E Sortieren.

- **AC-9:** Given der Reiter Orte / When eine Ortszeile angeklickt bzw. „+ Ort hinzufügen“ betätigt wird / Then öffnen sich Aufklapp-Panel (`hub-orte-panel`) und Hinzufügen (`hub-orte-add`) unverändert.
  - Test: Staging-E2E mit Testids `hub-orte-row`, `hub-orte-panel`, `hub-orte-add`.

- **AC-10:** Given ein Trip mit Etappen / When der Reiter Etappen im Hub geöffnet wird / Then zeigt jede Etappe eine Zeile „E{n} · Start → Ziel“ mit „x km · ↑y m“ darunter und rechts „Gehzeit h:mm“, in DE und EN aus dem Katalog.
  - Test: SSR-Render in DE und EN; Staging-E2E mit Prüf-Trip.

- **AC-11:** Given eine Etappe mit Distanz und Aufstieg / When die Gehzeit angezeigt wird / Then stammt sie aus der vorhandenen Gehzeit-Rechnung (`computeArrivalTimes`/`activityToSpeed`) und stimmt mit der Ankunftszeit-Berechnung des Editors überein.
  - Test: SSR-Render mit festem Tempo, Erwartungswert aus derselben Rechnung unabhängig berechnet.

- **AC-12:** Given ein Trip mit einem Pausentag / When der Reiter Etappen geöffnet wird / Then zeigt die Pausentag-Zeile Titel, aber weder Kennzahlen noch Gehzeit; fehlen bei einer Etappe Distanz oder Aufstieg, entfällt nur der fehlende Teil.
  - Test: SSR-Render mit Pausentag und unvollständiger Etappe.

- **AC-13:** Given der Reiter Etappen im Hub / When die Seite geöffnet wird / Then ist zunächst nur die Liste sichtbar (kein Editor, keine Karte), und Klick oder Enter auf eine Etappenzeile klappt den unveränderten Editor (Karte, Profil, Wegpunkte, Datum, Startzeit, Pausentag) für genau diese Etappe unter der Zeile auf; erneuter Klick schließt ihn, höchstens ein Editor ist gleichzeitig offen.
  - Test: Staging-E2E (Klick, Enter, Schließen, Wechsel zwischen Etappen); SSR-Render des Grundzustands.

- **AC-14:** Given die aufgeklappte Etappe / When Datum, Startzeit oder Pausentag geändert werden / Then wird gespeichert wie bisher (Autosave, Kaskade der Folgeetappen), keine Editor-Funktion ist entfallen.
  - Test: angepasste Bestands-E2E (`hub-editor-autosave-*`, `hub-save-chip`, `waypoints-editor`, `etappen-strip-*`) grün.

- **AC-15:** Given der Anlegen-Editor eines neuen Trips und die mobile Ansicht / When die Etappen bearbeitet werden / Then verhalten sie sich unverändert (kein Listenmodus im Anlegen-Editor, Mobil-Zweig `mobile-stages-list` wie bisher).
  - Test: SSR-Render ohne `listeZuerst`; Bestands-E2E `mobile-stages-listen-only.spec.ts`, `mobile-etappen-sortieren-speichert.spec.ts` grün.

- **AC-16:** Given der Reiter Etappen / When er geöffnet wird / Then gibt es keinen Knopf „Tempo ändern“ und keine Tempo-Karte; diese gehören zu #2796 und sind in der Besitzerliste dorthin verwiesen.
  - Test: SSR-Render; Datentest der Besitzerliste (Einträge `art:element` mit Verweis #2796).

- **AC-17:** Given beide Listen / When der Abschnitts-Marker geprüft wird / Then trägt der Listen-Container jedes Reiters genau einmal `data-abschnitt="liste"`, in jedem Zustand (normal, Laden, Fehler, Lücken).
  - Test: SSR-Render beider Reiter in allen Zuständen, Markeranzahl gleich eins.

- **AC-18:** Given die Oberfläche steht auf Deutsch bzw. Englisch / When Etappen- oder Orte-Reiter geöffnet werden / Then stammen alle Zeilentexte, Beschriftungen und `aria-label` aus dem Katalog in der gewählten Sprache ohne Rest der anderen; Protokoll-Token und Zahlen bleiben unübersetzt; jeder neue Schlüssel existiert in DE und EN.
  - Test: Katalog-Paritätstest, SSR-Render beider Sprachen, Wächter `keine_hartkodierten_nutzertexte`.

- **AC-19:** Given `elementliste.json` mit den 76 Lücken-Einträgen beider Reiter / When die Datei nach dem Nachziehen geladen wird / Then tragen sie `i18n_key`, `text_de` und `text_en`, sind nicht mehr `luecke:true`, und alle Eintrags-IDs sind unverändert.
  - Test: Datentest (`# doc-compliance-test`) über die Einträge von `trip/etappen/liste` und `orte/orte/liste`.

- **AC-20:** Given `elementliste_besitzer.json` / When die Datei nach dem Nachziehen geprüft wird / Then enthält sie keine Sammel-Einträge `{text}` für Etappen und Orte (746/747) und keinen Listen-Eintrag mehr für beide (338/347); die Kopf-Einträge 337/346 sind nur entfernt, wenn der Abgleich den Kopf findet; Eintrag 339 (`tempo`) bleibt.
  - Test: `tests/test_2913_c2_besitzerliste.py` angepasst und grün.

- **AC-21:** Given Staging mit dem Stand dieser Scheibe und einem Prüf-Datensatz mit Etappen (Distanz, Aufstieg) und Orten (Gruppe, Höhe) / When `elementliste:abgleich --abnahme` für DE und EN läuft / Then meldet er für `trip/etappen` und `orte/orte` keine Abweichung und keine Fremdtexte, und eine absichtlich verfälschte Zeilenbeschriftung (Gegenprobe) macht ihn rot.
  - Test: Abgleich-Lauf gegen Staging DE und EN; Mutations-Gegenprobe per String-Ersetzung.

- **AC-22:** Given die Umsetzung ist abgeschlossen / When Bestandstests und Wächter laufen / Then sind die bestehenden Testids (`hub-orte-row`, `hub-orte-remove`, `hub-orte-add`, `hub-orte-panel`, `mobile-stages-list`, `stage-cardm-row`) weiter vorhanden und alle angepassten Bestands-E2E grün; keine Bestandsfunktion wurde still entfernt.
  - Test: bestehende Specs und `bausteine_waechter*` laufen grün; Staging-E2E.

## Known Limitations

- Die Listenzeile der Etappen zeigt „Gehzeit“ für jede Etappe; die Elementliste führt es nur für E1. Mehrfachtreffer im Abgleich werden in Phase 3/4 geprüft und notfalls in der Elementliste ergänzt.
- „Tempo ändern“ und Tempo-Karte folgen mit #2796; bis dahin ist das Tempo nur über den bestehenden Editor änderbar.
- Reihenfolge-Sortieren der Orte bleibt trotz Mockup-Satz „ohne Rangfolge“ erhalten (Inventar E2 „Reihenfolge unverändert“); Zuordnung zu #2798 wird dort neu bewertet.
- Der Abgleich läuft im Desktop-Viewport; der Mobil-Zweig ist nicht Teil des Nachweises.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; folgt ADR-0097 (Trip/Orte geteilt), ADR-0104 (Katalog DE/EN), ADR-0112 (Design-System-Bausteine)
- **Rationale:** Setzt bestehende Entscheidungen um. Das Aufklapp-Muster für den Etappen-Editor folgt der Grundentscheidung „Etappen und Wegpunkte unverändert“ und dem schon vorhandenen Orte-Panel.

## Changelog

- 2026-11-17: Initial spec created
