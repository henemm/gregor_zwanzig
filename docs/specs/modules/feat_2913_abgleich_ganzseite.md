---
entity_id: feat_2913_abgleich_ganzseite
type: module
created: 2026-11-12
updated: 2026-11-12
status: draft
version: "1.0"
tags: [einstellungen-neu, elementliste, abgleich, ganzseite, besitzer, abnahme, epic-2791, issue-2913]
---

# Elementlisten-Abgleich über die ganze Seite (Besitzer, Gegenrichtung, Abnahmeregel)

## Approval

- [ ] Approved

## Purpose

Der Staging-Abgleich prüft heute nur Abschnitte, die in der Elementliste stehen und per `data-abschnitt` markiert sind; was die Seite zusätzlich zeigt, bleibt unsichtbar, und Abweichungen haben keinen Verantwortlichen. Diese Spec (Plan A–C aus Issue #2913) macht den Abgleich seitenweit: Texte, die live sichtbar sind und in keinem Eintrag stehen, werden als `zusaetzlich` gemeldet, jede Abweichung braucht einen Besitzer (Scheibe, Issue oder Freigabe), und ein neuer Modus `--abnahme` wird rot, solange eine Abweichung herrenlos ist.

## Source

- **File:** `frontend/e2e/elementliste_abgleich_logik.ts`, `frontend/e2e/elementliste-abgleich.staging.spec.ts`, `scripts/elementliste_abgleich.ts`, `docs/context/einstellungen_neu/elementliste_besitzer.json` (neu), `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte`, `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `frontend/src/lib/components/compare/CompareTabs.svelte`, `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte`, `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte`
- **Identifier:** Status `zusaetzlich`; `findeZusaetzliche`, `leseBesitzer`, `wendeBesitzerAn`, `exitCode(…, { abnahme })`; Marker `data-seite="hub"`, `data-abschnitt` = `kopf | reiterleiste | vorlage | laden | warnung`
- **Schicht:** ausschließlich Frontend-Prüfwerkzeug (`frontend/e2e`, `scripts/`, Doku-JSON) plus unsichtbare Marker-Attribute an Svelte-Komponenten. Kein Go-API-, kein Python-Core-Code.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung:** Der Abgleich läuft für beide Kontexte (`ctx` trip und orte) mit derselben Logik; Marker werden in den geteilten Komponenten (`HubKopf`, `TripTabs`/`CompareTabs`, `VorlageKarte`, `WetterTabInhalt`) gesetzt, kein neuer Baustein mit einseitigem Pendant.
> - **Mandantentrennung:** Keine Nutzerdaten werden bewegt; das Prüfwerkzeug liest nur über das vorhandene Staging-Konto. Zwei-Nutzer-Test entfällt (kein datenbewegender Endpoint).
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt wird geändert; die Kanäle (E-Mail, Telegram, SMS, Premium-SMS) kommen nur als bestehende Segmente der Elementliste vor.

## Scope

### In Scope

1. Status `zusaetzlich` (Gegenrichtung) mit Zähler, eigener Liste und stabiler ID im Bericht.
2. Besitzer-Datei mit Parser und Anwendung; Besitzer-Spalte im Markdown-Bericht.
3. Modus `--abnahme` (keine Abweichung ohne Besitzer); `--strict` unverändert.
4. Unsichtbare Marker `data-seite="hub"` sowie `kopf`, `reiterleiste`, `vorlage`, `laden`, `warnung`.
5. Rot-Probe an der Profil-Zeile (Fixture und Staging) und Triage des Ganzseitenberichts DE/EN mit Tabelle in #2913.

### Nicht-Ziele (ausdrücklich)

- Die gefundenen Abweichungen werden **nicht** behoben; sie gehen mit Besitzer an die Scheiben `#2913-c2`, `#2913-d`, `#2913-e` bzw. an Issues.
- Kein Handy-Viewport in der Gegenrichtung (Folge-Issue); die Gegenrichtung läuft nur auf Desktop.
- Keine Zustände außer `normal` (kein `laedt`, `fehler`, `luecken`) und keine Kanal-Segmente in der Gegenrichtung.
- Kein Umbau von `mockup-bildpruefer` (Plan D ist in `fix-2913-metrikliste-mockup` erledigt).
- Keine Änderung an Zustellungs-Komponenten (Reiter Zustellung gehört #2795); sie werden nur gelesen.
- Kein sichtbarer Aussehenswechsel der Seiten.

## Estimated Scope

- **LoC:** ca. +600 / −20
- **Files:** ca. 15
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md` | Spec | Vorgänger: Elementliste, Abgleich, `--strict`; hier nur erweitert |
| `docs/context/einstellungen_neu/elementliste.json` | Daten | Soll-Einträge (kein `uebersicht`-Reiter) |
| `docs/context/einstellungen_neu/elementliste_freigaben.json` | Daten | Freigaben; zählen künftig als Besitzer |
| `frontend/src/lib/__tests__/bausteine_waechter*.ts` | Gate | Marker/Wrapper dürfen ihn nicht verletzen (TripTabs/CompareTabs im Bestand) |
| Staging-Konto (Staging-`.env`) | Betrieb | Live-Lauf; `assertNotProdBaseURL` bleibt |
| Sitzung #2795 (Zustellung) | Abstimmung | CompareTabs/TripTabs liegen nahe; vor Änderung abstimmen |

## Implementation Details

**1. Status und Bericht.** `Status` erhält `zusaetzlich`. Zusätzliche Einträge liegen in einer **eigenen Liste** im Bericht (nicht in `plan.elemente`), damit `abschluss` (`eintraege.length === elemente.length`) unverändert gilt. `zaehler` erhält `zusaetzlich`. ID: `zus:<ctx>/<reiter>/<hash>`, Hash über den normalisierten Text, Zahlen werden vorher zu `{zahl}`.

**2. Gegenrichtung.** Je Kombination ctx × Reiter (Zustand `normal`, ohne Segment, Desktop) werden die sichtbaren Texte **aller** `[data-seite="hub"]` gelesen (nicht `body`: SaveIndicator, BottomNav und Seitenleiste liegen außerhalb). `findeZusaetzliche(befund, liste, ausnahmen, kontoTexte, sprache)` erklärt einen Text, wenn er (a) zu einem Eintrag des Reiters oder zu `kopf`/`reiterleiste` desselben ctx passt (`erwartung`, DE/EN), (b) zu einem Konto-Text aus der API gehört (Trip-/Preset-Name, Etappen-, Ortsnamen) oder (c) zu einer Ausnahme mit Grund und Spec gehört. Reihenfolge und Mehrfachvorkommen sind egal. Reiter Übersicht fehlt in der Elementliste: Ausnahme mit Grund, Besitzer ist ein neues Issue „Elementliste: Reiter Übersicht aus dem Mockup erzeugen“.

**3. Besitzer.** Datei `elementliste_besitzer.json` (getrennt von den Freigaben). Ein Eintrag nennt Ziel-Art (`element` per ID, `abschnitt` per ctx/reiter/abschnitt, `zusaetzlich` per Text oder Muster), `grund` und Verweis (Scheibe `#2913-c2|d|e` oder Issue `#NNNN`). `leseBesitzer` wirft bei fehlendem Grund oder fehlendem/ungültigem Verweis (wie `leseFreigaben`). Eine Freigabe (Status `freigegeben`) zählt als Besitzer. Der Markdown-Bericht erhält eine Besitzer-Spalte und eine Zusätzlich-Tabelle.

**4. Abnahme.** `--abnahme` (in `leseOptionen` und `flagsAlsUmgebung`): Exit ≠ 0 genau dann, wenn ein Eintrag `abweichend`, `nicht_pruefbar` oder `zusaetzlich` keinen Besitzer hat. `--strict` bleibt unverändert.

**5. Marker.** `data-seite="hub"` an `HubKopf` und an der Wurzel von `TripTabs`/`CompareTabs`; `data-abschnitt="kopf"` am Wurzel-div von `HubKopf`; `data-abschnitt="reiterleiste"` an einem Wrapper um `MTabBar` ohne Klasse und Style; `vorlage` an `VorlageKarte`; `laden` und `warnung` an `wt-laden`/`wt-fehler` in `WetterTabInhalt`. Nur Attribute bzw. ein styleloser Wrapper.

**6. Triage (A).** Neuer Ganzseitenbericht DE und EN auf Staging; jede Abweichung erhält einen Besitzer (Werkzeuglücken sind durch Marker behoben, echte Abweichungen gehen an c2/d/e oder ein Issue); Tabelle als Kommentar in Issue #2913. Das Rauschen der Gegenrichtung (Schätzung 20–60 Treffer) wird iterativ mit Ausnahmen oder Besitzern triagiert, nie pauschal gefiltert.

## Expected Behavior

- **Input:** Elementliste, Besitzer-Datei, Freigaben, Live-Seite auf Staging, Konto-Daten per API; Flag `--abnahme`.
- **Output:** Bericht (JSON + Markdown) mit Zähler und Liste `zusaetzlich`, Besitzer je Eintrag; Exit-Code nach `--strict` bzw. `--abnahme`.
- **Side effects:** Keine; Prüfwerkzeug liest nur. Marker sind unsichtbare Attribute.

## Acceptance Criteria

- **AC-1:** Given ein Befund enthält einen Live-Text, der weder zu einem Listeneintrag, einem Konto-Text noch einer Ausnahme passt / When `findeZusaetzliche` und `baueBericht` laufen / Then erscheint er mit Status `zusaetzlich` in einer eigenen Liste des Berichts, der Zähler `zusaetzlich` in JSON und Markdown ist um 1 höher, und `plan.elemente` bleibt unverändert, sodass `abschluss` weiterhin nur die Listenelemente vergleicht.
  - Test: `node --test`, `elementliste_abgleich.test.ts`, Fixture-Befund mit und ohne Fremdtext; Prüfung von Zähler, Liste und `abschluss`.

- **AC-2:** Given zwei Läufe mit demselben Fremdtext, der sich nur in Zahlen unterscheidet (z. B. „3 Etappen“ und „7 Etappen“) / When die IDs gebildet werden / Then lautet die ID beide Male `zus:<ctx>/<reiter>/<hash>` mit identischem Hash (Zahlen zu `{zahl}` normalisiert); ein anderer Text ergibt einen anderen Hash.
  - Test: `elementliste_abgleich.test.ts`, Gleichheit und Ungleichheit der IDs.

- **AC-3:** Given ein Live-Text passt auf einen Eintrag des Reiters oder auf `kopf`/`reiterleiste` desselben ctx, in DE oder EN, in beliebiger Reihenfolge und auch mehrfach vorkommend / When die Gegenrichtung läuft / Then ist er erklärt und wird nicht als `zusaetzlich` gemeldet; derselbe Text unter einem anderen ctx, der dort keinen Eintrag hat, wird `zusaetzlich`.
  - Test: `elementliste_abgleich.test.ts`, Fixture mit DE-/EN-Texten, vertauschter Reihenfolge, Duplikat und ctx-Wechsel.

- **AC-4:** Given ein Live-Text ist ein Konto-Text (Trip-/Preset-Name, Etappenname, Ortsname aus der API) oder steht in den Ausnahmen mit Grund und Spec / When die Gegenrichtung läuft / Then ist er erklärt; eine Ausnahme ohne Grund oder ohne Spec-Verweis lässt den Parser mit Fehler abbrechen.
  - Test: `elementliste_abgleich.test.ts`, Konto-Text-Fixture, Ausnahme gültig und ungültig.

- **AC-5:** Given der Staging-Lauf liest die Texte einer Seite / When die Wurzel der Gegenrichtung bestimmt wird / Then werden nur die Texte unter `[data-seite="hub"]` gelesen und die Gegenrichtung gilt nur für Zustand `normal`, ohne Segment, im Desktop-Viewport; Texte von SaveIndicator, BottomNav und Seitenleiste erscheinen nie als `zusaetzlich`.
  - Test: Staging-Lauf mit Berichtsprüfung (keine dieser Texte in der Zusätzlich-Liste); `elementliste_abgleich_verdrahtung.test.ts` für Wurzel-Selektor und Kombi-Filter.

- **AC-6:** Given `elementliste_besitzer.json` mit Ziel-Arten `element`, `abschnitt` und `zusaetzlich` (Text oder Muster) / When `leseBesitzer` sie liest und `wendeBesitzerAn` sie auf den Bericht anwendet / Then trägt jeder gedeckte Eintrag Besitzer und Verweis im Bericht und in der Besitzer-Spalte des Markdown; ein Abschnitts-Besitzer deckt alle Abweichungen dieses Abschnitts; Status und Zähler der Einträge ändern sich dadurch nicht.
  - Test: `elementliste_abgleich.test.ts`, drei Zielarten, Markdown-Spalte.

- **AC-7:** Given ein Besitzer-Eintrag ohne `grund`, ohne Verweis oder mit einem Verweis, der weder `#2913-c2|d|e` noch `#NNNN` ist / When `leseBesitzer` läuft / Then wirft der Parser einen Fehler, der den Eintrag nennt; gültige Einträge werden angenommen.
  - Test: `elementliste_abgleich.test.ts`, je ein Fehlerfall (Grund fehlt, Verweis fehlt, Verweis ungültig) und ein gültiger Fall.

- **AC-8:** Given ein Eintrag ist per Freigabe (`freigegeben`, mit Grund und Spec) gedeckt / When `--abnahme` bewertet wird / Then zählt die Freigabe als Besitzer und verursacht keinen Exit ≠ 0.
  - Test: `elementliste_abgleich.test.ts`, Fixture mit Freigabe aus `elementliste_freigaben.json`.

- **AC-9:** Given ein Bericht mit je einem Eintrag `abweichend`, `nicht_pruefbar` und `zusaetzlich` / When `exitCode` mit `abnahme` läuft / Then ist der Exit ≠ 0, solange mindestens einer davon keinen Besitzer hat, und 0, wenn jeder einen Besitzer hat; ein herrenloser Eintrag jeder der drei Arten genügt einzeln für Exit ≠ 0.
  - Test: `elementliste_abgleich.test.ts`, Kreuzprobe über die drei Status mit und ohne Besitzer.

- **AC-10:** Given `--strict` wird ohne `--abnahme` aufgerufen / When `exitCode` läuft / Then gilt unverändert: Exit ≠ 0 bei `abweichend + nicht_pruefbar > 0`, `freigegeben` zählt nicht; `zusaetzlich` allein löst ohne `--abnahme` keinen Exit ≠ 0 aus. Ohne beide Flags bleibt Exit 0. `--abnahme` wird aus Argumenten und Umgebung (`flagsAlsUmgebung`, `leseOptionen`) gelesen.
  - Test: `elementliste_abgleich.test.ts` und `elementliste_abgleich_verdrahtung.test.ts`, bestehende Strict-Fälle bleiben grün.

- **AC-11:** Given ein Befund-Fixture enthält die Profil-Zeile des Seitenkopfs (Profil-Optionen stehen nicht in der Elementliste) / When Bericht und `exitCode` mit `--abnahme` laufen / Then ist die Profil-Zeile `zusaetzlich` und der Exit ist 1; nach Anlage eines passenden Besitzer-Eintrags im Fixture ist der Exit 0.
  - Test: `elementliste_abgleich.test.ts`, Fixture vor und nach dem Besitzer-Eintrag.

- **AC-12:** Given der Staging-Lauf mit `--abnahme` und in `elementliste_besitzer.json` ist für die Profil-Zeile noch kein Besitzer eingetragen / When der Lauf endet / Then ist er rot und der Bericht nennt die Profil-Zeile unter `zusaetzlich`; nach Eintrag des Besitzers entfällt sie aus den herrenlosen Treffern.
  - Test: Lauf `npm run elementliste:abgleich -- --abnahme` gegen Staging (nur Staging, nicht im PR-CI), Exit und Bericht.

- **AC-13:** Given die Seiten Trip und Orte-Vergleich auf Staging / When der Abgleich die Abschnitte liest / Then tragen `HubKopf` `data-seite="hub"` und `data-abschnitt="kopf"`, `TripTabs`/`CompareTabs` `data-seite="hub"` und einen styleless Wrapper um `MTabBar` mit `data-abschnitt="reiterleiste"`, `VorlageKarte` `vorlage`, `WetterTabInhalt` `laden` und `warnung`; das sichtbare Aussehen ist unverändert, der Bausteine-Wächter bleibt grün, und es gibt keine Änderung an Zustellungs-Komponenten.
  - Test: Staging-Lauf (Abschnitte werden gefunden, die Werkzeuglücke „Haken fehlt“ entfällt für diese Abschnitte); `node --test bausteine_waechter.test.ts bausteine_waechter_wirkort.test.ts`; Diff-Prüfung (keine Zustellungs-Dateien).

- **AC-14:** Given der neue Ganzseitenbericht für DE und EN auf Staging / When `npm run elementliste:abgleich -- --abnahme` läuft / Then ist der Exit 0, jede verbleibende Abweichung, jedes `nicht_pruefbar` und jedes `zusaetzlich` hat einen Besitzer (Scheibe, Issue oder Freigabe), der Reiter Übersicht ist als Ausnahme mit Grund und neuem Issue geführt, und die Triage-Tabelle steht als Kommentar in Issue #2913.
  - Test: Lauf je Sprache gegen Staging; Prüfung von Exit, Berichtsdateien und Issue-Kommentar.

## Test Plan

- Kern-Tests mit `node --test` (kein Vitest): `frontend/src/lib/__tests__/elementliste_abgleich.test.ts` (AC-1 bis AC-4, AC-6 bis AC-11), `elementliste_abgleich_verdrahtung.test.ts` (AC-5, AC-10), `bausteine_waechter*.test.ts` (AC-13).
- Staging-Lauf außerhalb der PR-CI mit `playwright.elementliste.staging.config.ts` (AC-5, AC-12, AC-13, AC-14).
- **Testpolitik:** Kein Mock-Theater; Logik gegen echte Fixture-Befunde, Gegenrichtung gegen echtes Staging. Mutations-Gegenprobe (Pflicht): per String-Ersetzung z. B. Besitzer-Prüfung, Hash-Normalisierung oder `abnahme`-Zweig ausschalten; je ein Test muss rot werden. `uv run pytest` nie ohne benannte Dateien.

## Definition of Done

- AC-1 bis AC-14 erfüllt und durch die genannten Tests belegt; Mutations-Gegenprobe ohne unbewachte Verfälschung.
- Kern-Tests und Bausteine-Wächter grün; alle sechs CI-Checks grün.
- Staging-Lauf DE und EN mit `--abnahme` Exit 0; Triage-Tabelle in Issue #2913; Issue für Reiter Übersicht angelegt.
- Auslieferung in einem PR; keine Produktfunktion verändert.

## Known Limitations

- Gegenrichtung nur Desktop und nur Zustand `normal`; Handy-Zusätze und Zustände sind Folge-Issues.
- Die Besitzer-Datei kann zum Verschiebebahnhof werden; Gegenmittel: Grund und Verweis sind Pflicht, Abschluss von #2913 verlangt weiterhin `--strict` grün.
- Erkannt wird Text, keine Optik; Optik deckt `mockup-bildpruefer` ab.
- Rauschen der Gegenrichtung wird iterativ triagiert; Konto-Texte ohne Muster brauchen gezielte Ausnahmen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Erweiterung des Prüfwerkzeugs aus ADR-0112, keine neue Entscheidungsfläche)
- **Rationale:** Es ändert sich nur ein Prüfwerkzeug; kein Kanal, Provider, Datenmodell oder Auth betroffen.

## Changelog

- 2026-11-12: Initial spec created (Issue #2913, Plan A–C, Workflow feature-2913-abgleich-ganzseite)
- 2026-11-13: Fix-Loop 4 (Staging-Befund `zusaetzlich = 0`): In der Gegenrichtung erklärt `{zahl}` nur noch Zahl-Text (`erwartungGegenrichtung`); ein Eintrag `muster: "{zahl}"` wurde vorher zu `^.+?$` und erklärte jeden Live-Text. Hinrichtung (`erwartung`) und ID-Bildung (AC-2) unverändert. Bekannte Grenze: andere Platzhalter (`{metrik}`, `{zeit}` …) bleiben in der Gegenrichtung beliebig; Zahlen mit Leerzeichen-Tausendertrenner gelten nicht als Zahl-Text.
