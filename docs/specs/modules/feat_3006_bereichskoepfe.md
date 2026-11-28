---
entity_id: feat_3006_bereichskoepfe
type: feature
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: feature-3006-bereichskoepfe
issue: 3006
tags: [einstellungen-neu, bereichskopf, reiter, abgleich, epic-2913, issue-3006]
---

# Bereichsköpfe je Reiter der Einstellungen (Trip + Orts-Vergleich)

## Approval

- [ ] Approved

## Purpose

Jeder Reiter der Einstellungen von Trip und Orts-Vergleich bekommt oben den Bereichskopf aus dem freigegebenen Mockup `mockup-hub-fassung3.html` (Überschrift, Erklärsatz, optional eine Aktion rechts). Bisher gibt es zwei voneinander abweichende Einzelkopien (Wetter, Zustellung) und für die übrigen Reiter gar keinen Kopf. Ein gemeinsamer Design-System-Baustein ersetzt sie, in DE und EN aus dem Katalog, damit der Elementlisten-Abgleich den Abschnitt `abschnittskopf` aller Reiter als gefunden meldet (Teil von Epic #2913).

## Source

- **File:** `frontend/src/lib/components/molecules/Bereichskopf.svelte` (neu)
- **Identifier:** `Bereichskopf` (eingesetzt in `TripTabs`, `CompareTabs`, `WetterTabInhalt`, `ZustellungTab`, `HubUebersicht`)
- **Schicht:** ausschließlich Frontend (`frontend/src/...`) plus Doku-Daten des Abgleichs (`docs/context/einstellungen_neu/elementliste.json`). Kein Go-API-, kein Python-Core-Code, keine Schema-Änderung.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung (ADR-0097):** Der Baustein liegt einmal unter `molecules/` und wird in beiden Kontexten verwendet; Wetter, Zustellung und Übersicht nutzen bereits geteilte Reiter-Inhalte. Eigen je Kontext sind nur Etappen (Trip) und Orte (Orte) mit ihren Köpfen, wie im Mockup.
> - **Mandantentrennung:** Reine Darstellung, keine Nutzerdaten bewegt, kein Endpoint geändert. Zwei-Nutzer-Test entfällt.
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt ändert sich; E-Mail, Telegram, SMS und Premium-SMS nicht betroffen.

## Estimated Scope

- **LoC:** ca. +250 / −60 (inkl. Tests, ohne `elementliste.json`)
- **Files:** ca. 12 bis 14
- **Effort:** medium (viele Reiter berührt, Bestandstests mit Testids und Struktur-Wächter)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Soll | CSS Z. 69-71 (`.sectionh`), Köpfe Z. 442 (Wetter), 556 (Zustellung), 579 (Etappen), 590 (Orte), 594 (Übersicht) |
| `Btn` (Atom) | Design-System-Baustein (ADR-0112) | Aktionsknopf „+ Ort hinzufügen“ (ghost, sm), Atom unverändert |
| `atoms/SectionH.svelte` | Atom | bleibt unverändert (anderes Muster, vielfach genutzt) |
| Design-Tokens `--g-size-22px`, `--g-size-13px`, `--g-ink-3`, `--g-rule-soft`, `--g-s-*` | Tokens | nur Tokens statt Rohwerte (Wächter `bausteine_waechter*.test.ts`) |
| i18n-Katalog (ADR-0104) | Katalog | Nutzertexte DE+EN; vorhanden `wetter.kopf.*`, `zustellung.kopf.*`; neu Etappen, Orte, Übersicht, Knopf |
| `docs/context/einstellungen_neu/elementliste.json` | Soll-Daten | `abschnittskopf`-Einträge je Reiter; Abgleich bewertet Text über `text_de`/`text_en` |
| `frontend/e2e/elementliste_abgleich_logik.ts` | Abgleich | liest `data-abschnitt` in `[data-seite="hub"]`, prüft Reihenfolge Titel, Satz, Knopf |
| `hub_kopf_c2_bildabgleich.test.ts` (AC-28 aus #2980) | Bestandstest | Struktur: Titel-Eltern trägt Linie/Padding, Erklärsatz ist Geschwister |
| `wetter_tab_abschnitt_marker_2966.test.ts`, `s3b2795_zustellung_struktur.test.ts` | Bestandstests | Testids und Kopftexte |
| `feat_2913_c2_seitenkopf.md`, `feat_2795_s3b_teil1_zustellung.md`, `feat_2794_s3a_reiter_wetter.md` | Specs | Vorgänger |
| Issues #2969, #3007, #2968, #3022 | Abgrenzung | #2969 Übersicht in Elementliste; #3007 Listen Etappen/Orte; #2968/#3022 EN-Lücken |

## Scope

### Nicht-Ziele

- `SectionH`-Atom wird nicht umgebaut.
- Listen-Inhalte der Reiter Etappen und Orte (inkl. Reihenfolge-Hinweis `hub-section-hint`): #3007.
- Kein neuer Elementlisten-Eintrag für Übersicht (#2969, Besitzer).

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/molecules/Bereichskopf.svelte` | CREATE | Baustein: Props `titel`, `erklaerung`, `testid` (Präfix), optional `aktion` (Snippet); Root `<div data-abschnitt="abschnittskopf">` mit h2, p, Aktions-Wrapper als direkte Kinder (CSS-Grid `1fr auto`, Aktion rechts unten ausgerichtet, mobil einspaltig) |
| `frontend/src/lib/components/molecules/index.ts` | MODIFY | Export |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | `<header class="wt-kopf">` und zugehöriges CSS durch Baustein ersetzen (Testid-Präfix `wetter-tab`) |
| `frontend/src/lib/components/organisms/zustellung-tab/ZustellungKopf.svelte` | DELETE | durch Baustein ersetzt (vorher `grep -rn ZustellungKopf`) |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | MODIFY | Baustein statt ZustellungKopf (Testid-Präfix `zustellung`) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Etappen-Zweig: Kopf vor dem Inhalt (auch bei noch nicht geladenem Trip) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Orte: SectionH „Verglichene Orte“ durch Bereichskopf ersetzen, Knopf `hub-orte-add` (gleicher Handler `toggleAddPanel`, `Btn` sm ghost) in den Kopf, Footer-Zeile des Knopfs in der Card entfällt; Wetter/Zustellung: Kopf steht auch während der Hydrations-Sperre |
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | MODIFY | Kopf oben, geteilt für Trip und Orte |
| `frontend/src/lib/i18n/messages/de/*.json`, `en/*.json` | MODIFY | neue Schlüssel: Etappen-Titel/-Satz, Orte-Satz, Orte-Knopf „+ Ort hinzufügen“, Übersicht-Titel/-Satz (Namensraum nach Konvention) |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | `luecke:true`-Einträge der Köpfe per Skript auf `i18n_key`/`text_en`/`luecke:false`, IDs unverändert; vorher Generator/Konsistenztest prüfen |
| `frontend/src/lib/components/molecules/__tests__/bereichskopf*.test.ts` | CREATE | SSR-Render DE/EN, Struktur, Aktion-Snippet |
| Bestandstests und E2E mit Kopf-Bezug (u. a. `wetter_tab_abschnitt_marker_2966.test.ts`, `s3b2795_zustellung_struktur.test.ts`, `hub_kopf_c2_bildabgleich.test.ts`, `compare-hub-inline-edit.spec.ts`, `mobile-ux-messung.spec.ts`) | MODIFY | nur wo nötig an neue Struktur anpassen, nicht löschen |

## Implementation Details

Ein Molekül `Bereichskopf` ersetzt beide vorhandenen Kopien und wird in allen acht Reitern eingesetzt (Trip und Orte je Übersicht, Etappen bzw. Orte, Wetter, Zustellung). Der Kommentar im Molekül begründet, warum `SectionH` nicht umgebaut wird.

Mockup-Maße (CSS Z. 69-71): Root mit Linie `1px solid var(--g-rule-soft)` unten und `padding-bottom` 12 px, Lücke 12 px; h2 22 px, Gewicht 600, Laufweite -.01em, Rand 0; Erklärsatz Rand `2px 0 0`, Farbe `--g-ink-3`, 13 px, `max-width: 68ch`. Die Aktion steht rechts, am unteren Rand ausgerichtet; bei wenig Platz bricht sie um.

Grid statt verschachteltem Flex: h2, p und Aktion sind direkte Kinder des Roots, damit der Struktur-Test aus #2980 (Titel-Eltern trägt Linie, Satz ist Geschwister) und die Abgleich-Reihenfolge (1 Titel, 2 Satz, 3 Knopf) halten. Der Zustellungs-Satz wechselt von ink-2 auf Mockup-ink-3.

Testids: aus dem Präfix `testid` werden `<präfix>-titel` und `<präfix>-erklaer`; `wetter-tab` und `zustellung` erhalten die bestehenden Ids. Etappen, Orte und Übersicht bekommen analog eigene Präfixe.

Orte: Das Mockup zeigt nur Kopf und Liste; SectionH „Verglichene Orte“ entfällt, der Knopf „+ Ort hinzufügen“ wandert in den Kopf und ruft denselben Handler (`toggleAddPanel`) auf wie zuvor, Testid `hub-orte-add` bleibt. Der Aufklapp-Bereich zum Hinzufügen bleibt funktional unverändert.

Zustände: Der Kopf steht vor jeder Lade-/Fehler-/Sperr-Weiche des Reiters, nicht darin. Dadurch gibt es genau einen Marker je Reiter in jedem Zustand.

Reihenfolge der Umsetzung: Katalog, Baustein und Test, Wetter, Zustellung (Kopie löschen), Etappen und Orte (Knopf), Übersicht, `elementliste.json`, Abgleich DE/EN in allen Zuständen.

## Expected Behavior

- **Input:** geöffneter Trip bzw. Orts-Vergleich, beliebiger Reiter, Sprache DE oder EN.
- **Output:** Oben im Reiter steht der Bereichskopf mit Titel und Erklärsatz (Orte zusätzlich mit Knopf), Maße wie Mockup.
- **Side effects:** keine Datenänderung; nur Doku-Daten des Abgleichs.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `bereichskopf*.test.ts` (node --test, SSR-Render): GIVEN Titel, Satz, Testid-Präfix WHEN gerendert THEN h2, p und genau ein `data-abschnitt="abschnittskopf"`-Root mit Testids `<präfix>-titel`/`-erklaer`; mit Aktions-Snippet steht die Aktion als drittes direktes Kind, ohne Snippet kein leerer Aktions-Wrapper.
- [ ] Gleiche Datei: GIVEN Baustein WHEN Stilregeln aufgelöst THEN Maße und Tokens wie Mockup (22 px/600, 13 px, `--g-ink-3`, 68ch, Linie `--g-rule-soft`, Padding 12 px).
- [ ] SSR je Reiter (Trip: Übersicht, Etappen, Wetter, Zustellung; Orte: Übersicht, Orte, Wetter, Zustellung) in DE und EN: GIVEN Reiter gerendert WHEN Kopftexte gelesen THEN Titel und Satz aus dem Katalog, genau ein Marker; bei Orte-Reiter Knopf „+ Ort hinzufügen“ / EN-Entsprechung mit Testid `hub-orte-add`.
- [ ] SSR Zustände: GIVEN Reiter im Zustand Laden, Fehler bzw. Hydrations-Sperre WHEN gerendert THEN Kopf vorhanden, genau einmal.
- [ ] Katalog-Parität: GIVEN neue Schlüssel WHEN DE und EN verglichen THEN vollständig (`keine_hartkodierten_nutzertexte`).
- [ ] Wächter: `bausteine_waechter*.test.ts`, `hub_kopf_c2_bildabgleich.test.ts`, `wetter_tab_abschnitt_marker_2966.test.ts`, `s3b2795_zustellung_struktur.test.ts` bleiben grün; Dateien `ZustellungKopf.svelte` und Klasse `wt-kopf` kommen nirgends mehr vor.
- [ ] Elementliste: GIVEN `elementliste.json` WHEN geladen THEN Kopf-Einträge der erfassten Reiter ohne `luecke:true`, IDs unverändert (Testdatei mit `# doc-compliance-test`).
- [ ] Abgleich (`npm run elementliste:abgleich` gegen Staging, DE und EN): `abschnittskopf` aller erfassten Reiter gefunden; Mutations-Gegenprobe per String-Ersetzung am Kopf-Text macht den Abgleich rot.
- [ ] E2E (Playwright, Staging): Orte-Reiter, „+ Ort hinzufügen“ klicken, Aufklapp-Bereich öffnet; bestehende Specs `compare-hub-inline-edit.spec.ts` und `mobile-ux-messung.spec.ts` grün.

## Definition of Done

Fertig ist #3006, wenn alle acht Reiter (Trip und Orte je Übersicht, Etappen bzw. Orte, Wetter, Zustellung) ihren Bereichskopf ausschließlich aus dem einen Design-System-Baustein beziehen, die alten Kopf-Kopien entfernt sind, alle Kopftexte in DE und EN aus dem Katalog kommen, der Elementlisten-Abgleich auf Staging für DE und EN den Abschnitt `abschnittskopf` aller erfassten Reiter als gefunden meldet (Übersicht per SSR-Test, siehe Known Limitations), die bestehenden Testids und der Aufklapp-Knopf „Ort hinzufügen“ weiter funktionieren und Henning ein Soll/Ist-Bild der Köpfe bekommen hat (AC-1 bis AC-21).

## Acceptance Criteria

- **AC-1:** Given der Baustein Bereichskopf wird mit Titel und Erklärsatz gerendert / When die Struktur betrachtet wird / Then besteht er aus einem Container mit dem Abschnitts-Marker `abschnittskopf`, darin als direkte Kinder Überschrift und Erklärsatz (in dieser Reihenfolge), und die Erklär-Testids tragen das übergebene Präfix.
  - Test: SSR-Render mit node --test, Struktur und Reihenfolge der Kinder.

- **AC-2:** Given der Baustein Bereichskopf / When seine Stile betrachtet werden / Then entsprechen sie dem Mockup: Überschrift 22 px, Gewicht 600, Erklärsatz 13 px in `--g-ink-3` mit höchstens 68 Zeichen Breite, darunter eine dünne Trennlinie in `--g-rule-soft` mit 12 px Abstand, alles über Design-Tokens.
  - Test: SSR-Render und aufgelöste Stilregeln; Wächter `bausteine_waechter*` bleibt grün.

- **AC-3:** Given der Baustein wird mit und ohne Aktion verwendet / When gerendert / Then steht die Aktion rechts am Kopf als drittes direktes Kind, ohne Aktion entsteht kein leerer Platzhalter, und bei wenig Breite bricht die Aktion unter den Text um.
  - Test: SSR-Render beider Varianten; Browser-Messung bei 390 px Breite, kein Überlauf.

- **AC-4:** Given ein Trip ist im Hub geöffnet / When der Reiter Übersicht geöffnet wird / Then steht oben der Bereichskopf „Übersicht“ mit dem Mockup-Satz „Unverändert: Stand, letzte Briefings, nächster Versand.“ (DE) bzw. der englischen Entsprechung aus dem Katalog.
  - Test: SSR-Render des Trip-Reiters in DE und EN.

- **AC-5:** Given ein Trip ist im Hub geöffnet / When der Reiter Etappen geöffnet wird / Then steht oben der Bereichskopf „Etappen & Wegpunkte“ mit dem Satz „Das Tempo bestimmt die Gehzeiten und damit, welche Stunden je Wegpunkt bewertet werden.“ (DE) bzw. der englischen Entsprechung aus dem Katalog, auch solange der Trip noch lädt.
  - Test: SSR-Render in DE und EN, einmal mit geladenem und einmal mit noch nicht geladenem Trip.

- **AC-6:** Given ein Trip ist im Hub geöffnet / When der Reiter Wetter geöffnet wird / Then steht oben der Bereichskopf „Wetter“ mit dem Satz „Was im Briefing steht, was für dich zu viel oder zu wenig ist und ab wann du einen Alarm bekommst.“ (DE) bzw. der englischen Entsprechung aus dem Katalog.
  - Test: SSR-Render in DE und EN; bestehende Prüfung in `wetter_tab_abschnitt_marker_2966.test.ts`.

- **AC-7:** Given ein Trip ist im Hub geöffnet / When der Reiter Zustellung geöffnet wird / Then steht oben der Bereichskopf „Zustellung“ mit dem Satz „Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.“ (DE) bzw. der englischen Entsprechung aus dem Katalog, in der Mockup-Farbe `--g-ink-3`.
  - Test: SSR-Render in DE und EN; Struktur-Test `s3b2795_zustellung_struktur.test.ts`.

- **AC-8:** Given ein Orts-Briefing ist im Hub geöffnet / When der Reiter Übersicht geöffnet wird / Then steht oben derselbe Bereichskopf „Übersicht“ mit demselben Satz wie beim Trip, aus demselben geteilten Baustein.
  - Test: SSR-Render des Orte-Reiters in DE und EN; Gleichheit mit der Trip-Ausgabe.

- **AC-9:** Given ein Orts-Briefing ist im Hub geöffnet / When der Reiter Orte geöffnet wird / Then steht oben der Bereichskopf „Orte“ mit dem Satz „Ein Ort ergibt ein Orts-Briefing. Ab zwei Orten kommt die Vergleichstabelle dazu, ohne Rangfolge.“ (DE) bzw. der englischen Entsprechung, rechts im Kopf der Knopf „+ Ort hinzufügen“ (EN-Entsprechung aus dem Katalog), und die frühere Überschrift „Verglichene Orte“ sowie der Knopf unten in der Card entfallen. *(Erklärsatz abgelöst durch `docs/specs/modules/fix_3437_orte_erklaer_gesperrt.md` (#3437): „Schon ein einzelner Ort ergibt ein vollständiges Briefing. Ab zwei Orten stehen die Orte in der Übersicht nebeneinander, ohne Rangfolge.“)*
  - Test: SSR-Render in DE und EN; Reihenfolge Titel, Satz, Knopf im Kopf.

- **AC-10:** Given der Reiter Orte mit dem Knopf im Kopf / When „+ Ort hinzufügen“ angeklickt wird / Then öffnet sich derselbe Aufklapp-Bereich zum Hinzufügen wie bisher (gleicher Handler), der Knopf trägt weiter die Testid `hub-orte-add`, und ein erneuter Klick schließt ihn wieder.
  - Test: E2E gegen Staging (Klick, Bereich sichtbar, erneuter Klick, Bereich weg); bestehendes `compare-hub-inline-edit.spec.ts` bleibt grün.

- **AC-11:** Given ein Orts-Briefing ist im Hub geöffnet / When der Reiter Wetter geöffnet wird / Then steht oben derselbe Bereichskopf „Wetter“ wie beim Trip, aus demselben Baustein, in DE und EN.
  - Test: SSR-Render des Orte-Reiters in DE und EN; Gleichheit mit der Trip-Ausgabe.

- **AC-12:** Given ein Orts-Briefing ist im Hub geöffnet / When der Reiter Zustellung geöffnet wird / Then steht oben derselbe Bereichskopf „Zustellung“ wie beim Trip, aus demselben Baustein, in DE und EN.
  - Test: SSR-Render des Orte-Reiters in DE und EN; Gleichheit mit der Trip-Ausgabe.

- **AC-13:** Given die Oberfläche steht auf Deutsch bzw. auf Englisch / When irgendein Reiter von Trip oder Orten geöffnet wird / Then stammen Titel, Erklärsatz und Knopftext aus dem Katalog, in der gewählten Sprache vollständig ohne Rest der anderen Sprache, und jeder neue Schlüssel existiert in DE und EN.
  - Test: Katalog-Paritätstest und SSR-Render beider Sprachen; Wächter `keine_hartkodierten_nutzertexte`.

- **AC-14:** Given ein Reiter befindet sich im Zustand Laden oder Fehler / When er angezeigt wird / Then steht der Bereichskopf trotzdem oben, mit demselben Text wie im Normalzustand.
  - Test: SSR-Render der Reiter Wetter und Zustellung (Trip und Orte) in den Zuständen Laden und Fehler.

- **AC-15:** Given im Reiter Wetter oder Zustellung der Orte läuft die Hydrations-Sperre (Daten werden noch geladen) / When der Reiter angezeigt wird / Then steht der Bereichskopf bereits oben und erscheint nach dem Laden nicht ein zweites Mal.
  - Test: SSR-Render im gesperrten und im entsperrten Zustand, jeweils genau ein Marker.

- **AC-16:** Given ein beliebiger Reiter von Trip oder Orten in beliebigem Zustand / When der Abschnitts-Marker gezählt wird / Then gibt es auf der Seite genau einen Marker `abschnittskopf` je Reiter.
  - Test: SSR-Render aller acht Reiter in allen Zuständen, Markeranzahl gleich eins.

- **AC-17:** Given die bestehenden Kopf-Elemente von Wetter, Zustellung und Orte-Hinzufügen / When die Seite nach dem Umbau gerendert wird / Then sind die Testids `wetter-tab-titel`, `wetter-tab-erklaer`, `zustellung-titel`, `zustellung-erklaer` und `hub-orte-add` weiterhin vorhanden und tragen denselben Text wie bisher bzw. laut Mockup.
  - Test: SSR-Render und bestehende Tests `wetter_tab_abschnitt_marker_2966.test.ts` und `s3b2795_zustellung_struktur.test.ts` grün.

- **AC-18:** Given der Umbau ist abgeschlossen / When der Quellbaum und die gerenderten Reiter geprüft werden / Then gibt es die Komponente ZustellungKopf und den Wetter-Eigenkopf `wt-kopf` nicht mehr, und beide Reiter zeigen ihren Kopf über den gemeinsamen Baustein.
  - Test: Struktur-Test (`# doc-compliance-test`) auf Nichtvorhandensein der alten Komponente; SSR-Render beider Reiter mit Baustein-Marker.

- **AC-19:** Given `elementliste.json` mit den Kopf-Einträgen der erfassten Reiter / When die Datei nach dem Nachziehen geladen wird / Then tragen Titel, Erklärsatz und Knopf (Orte) je `i18n_key`, `text_de` und `text_en` und sind nicht mehr als Lücke markiert; die Eintrags-IDs sind unverändert.
  - Test: Datentest (`# doc-compliance-test`) über die Kopf-Einträge; Generator/Konsistenztest, falls vorhanden, grün.

- **AC-20:** Given Staging mit dem Stand dieser Scheibe / When der Elementlisten-Abgleich für DE und EN läuft / Then meldet er den Abschnitt `abschnittskopf` aller erfassten Reiter von Trip und Orten (Etappen bzw. Orte, Wetter, Zustellung, je Zustand) als gefunden, und eine absichtlich verfälschte Kopf-Beschriftung (Gegenprobe) macht ihn rot. Bekannte Grenze: Der Reiter Übersicht ist in der Elementliste noch nicht erfasst (#2969), sein Kopf wird daher nur per SSR-Test (AC-4, AC-8) nachgewiesen, nicht im Abgleich.
  - Test: Abgleich-Lauf gegen Staging DE und EN; Mutations-Gegenprobe per String-Ersetzung am Kopf-Text.

- **AC-21:** Given das Atom `SectionH` wird in anderen Bereichen verwendet / When diese Scheibe umgesetzt ist / Then ist `SectionH` unverändert, und dessen Bestandstests bleiben ohne Anpassung grün.
  - Test: bestehende SectionH-Tests und Wächter laufen unverändert grün.

## Known Limitations

- Reiter Übersicht ist im Abgleich nicht nachweisbar, solange #2969 die Elementliste nicht erweitert; der Mockup-Satz für Übersicht ist Platzhalter-Charakter und wird als Soll übernommen.
- #3007 (Listen Etappen/Orte) berührt dieselben Reiterdateien; vor Phase 6 auf Überschneidung prüfen.
- EN-Lücken anderer Texte bleiben bei #2968 und #3022.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; folgt ADR-0097 (Trip/Orte geteilt), ADR-0104 (Katalog DE/EN), ADR-0112 (Design-System-Bausteine)
- **Rationale:** Setzt bestehende Entscheidungen um und ändert keine; `SectionH` bleibt wegen anderen Musters und vieler Nutzungen unberührt.

## Changelog

- 2026-11-17: Initial spec created
- 2026-11-28: AC-9 Erklärsatz Reiter Orte abgelöst durch #3437 (Mockup Fassung 4), siehe `docs/specs/modules/fix_3437_orte_erklaer_gesperrt.md`
