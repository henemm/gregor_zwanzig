---
entity_id: feat_3111_wetter_dialoge_mockup
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-3111-wetter-dialoge-mockup
tags: [wetter, dialoge, mockup, epic-2913, i18n]
---

# Wetter-Dialoge nach Mockup (Issue #3111, Epic #2913)

## Approval

- [ ] Approved

## Purpose

Die Dialoge im Hub-Reiter Wetter (Grenzen ändern, Vorlage wählen, Vorlage bestätigen, Vorlage speichern) werden in Text, Reihenfolge und Aufbau an das angenommene Mockup angeglichen, für Trip und Orte und in Deutsch und Englisch. Das Mockup ist laut Epic #2913 das Soll; danach entfallen die 156 Besitzer-Einträge `#3111` der Elementliste.

## Source

- **File:** `frontend/src/lib/components/organisms/wetter-tab/GrenzenEditor.svelte`, `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte`, `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte`
- **Identifier:** Svelte-Komponenten `GrenzenEditor`, `VorlageKarte`, `SavePresetDialog`; Funktion für Vorlagen-Kurzbeschreibung in `frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts`
- **Soll-Quelle:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (Z. 340-360, 455-505)

> **Schicht:** reines Frontend (SvelteKit), kein Go-API-, kein Python-Core-, kein Datenmodell-Eingriff.

> **Trip/Ortsvergleich-Teilung:** Alle Bausteine liegen bereits geteilt (`WetterTab` mit `context="route"|"vergleich"`; `GrenzenEditor`, `VorlageKarte`, `SavePresetDialog` kontextfrei bzw. kontextgesteuert). Es entsteht keine einseitige Komponente. Anlegeseiten (`TripNewEditor`/`CompareNewEditor`) nutzen denselben Reiter und ziehen automatisch mit.
>
> **Mandantentrennung:** Keine Nutzerdaten werden neu bewegt; bestehende Preset-Endpunkte bleiben unverändert (Preset-Beschreibung wird nur angezeigt/erfasst wie bisher).
>
> **Kanäle:** Keine Briefing- oder Alarm-Inhalte betroffen (nur Editor-Oberfläche).

## Löst ab (Abgrenzung zu feat_2794_s3a)

Diese Spec löst folgende Stellen der freigegebenen Spec `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` in diesen Punkten ausdrücklich ab (die alte Spec wird nicht bearbeitet):

- **Z. 123** (Kurzbeschreibung der Systemvorlage aus den ersten aktiven Metriken abgeleitet) wird abgelöst durch kuratierte Stichworte je Systemvorlage (AC-4).
- **Z. 124** (Live-Form der Vorlagen-Karten, Kennzeichnung der aktiven Vorlage und eigene Vorlagen ohne Unterzeile) wird abgelöst durch „· aktiv" als Text (AC-3) und die Unterzeile eigener Vorlagen (AC-5).
- **Z. 139** (Speichern-Dialog mit Beschreibungs-Label und Knopf-Reihenfolge der Live-Form) wird abgelöst durch AC-7.
- **AC-10** (Ableitung der Kurzbeschreibung aus den Metriken) wird abgelöst durch AC-4.

## Scope

**Im Scope:** Texte und Aufbau der Dialoge Grenzen ändern, Vorlage-Auswahl, Vorlage-Bestätigung und Vorlage speichern im Reiter Wetter, für Trip und Orte (geteilter Code), Deutsch und Englisch; Besitzer-Einträge `#3111` abräumen.

**Außerhalb des Scopes:** Herkunftszeile „aus GR221 gespeichert“ (#3189, neues Datenfeld), Steuerelement-Aufbau des Speichern-Dialogs (Checkbox, Inline-Karte, einzeiliges Feld, #3190), Mockup-Beispieldaten (#3151).

## Estimated Scope

- **LoC:** ca. 120-180 Code plus ca. 40 Katalogzeilen (DE/EN)
- **Files:** 6 Produktdateien (ggf. `WetterTabInhalt.svelte` als 7.), dazu Tests und Elementliste
- **Effort:** medium (Risiko MEDIUM: geteilter Code Trip/Orte, viele Tests pinnen die Live-Form)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| feat_2794_s3a_reiter_wetter | spec | Vorgänger-Spec, wird in genannten Punkten abgelöst |
| mockup-hub-fassung4.html | design | Soll-Vorlage (Epic #2913) |
| ADR-0104 | adr | Zweisprachigkeit: neue Nutzertexte nur über Katalog, Protokoll-Token nie übersetzen |
| ADR-0112 | adr | Bausteine (Steuerelement-Fragen bleiben ausgelagert, #3190) |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | i18n-Katalog | neue und geänderte Texte |
| `/api/templates` (`api/routers/config.py`) | API | liefert Systemvorlagen unverändert (keine Beschreibung) |
| `frontend/e2e/elementliste_abgleich_logik.ts` | test tool | Elementlisten-Abgleich (`--scope wetter`) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | datei | Besitzer-Einträge `#3111` |
| `tests/test_2913_c2_besitzerliste.py` | test | Zählwächter der Besitzer-Einträge |
| Issue #3189 | issue | Herkunft „aus GR221 gespeichert" (Backend-Feld), erbt Rest-Einträge |
| Issue #3190 | issue | Steuerelement-Abweichungen (Checkbox, Inline-Karte, einzeiliges Feld) |
| Issue #3151 | issue | Mockup-Beispieldaten (z.B. „Wandern 10 Metriken") |

## Implementation Details

Entscheidungen des Tech Leads (aus `docs/context/feat-3111-wetter-dialoge-mockup.md`, unverändert):

1. Mockup Fassung 4 ist Soll; diese Spec löst die abweichenden Stellen von feat_2794_s3a ab.
2. **Grenzen-Titel:** zwei Katalogschlüssel je Seite (`wetter.grenzen.unten_1/_2`, `oben_1/_2`), im Markup mit `<br>` verbunden, kein Zeilenumbruch im JSON.
3. **Kuratierte Stichworte** je Systemvorlage im Katalog (DE/EN, `wetter.vorlage.stichworte.*`); die Zahl der Metriken bleibt aus den Daten, `WEATHER_TEMPLATES` bleibt unverändert. Für unbekannte Vorlagen-IDs bleibt die bisherige Ableitung aus den ersten aktiven Metriken als Fallback.
4. **Bestätigung zweiteilig:** fetter Titel `„{name}“ übernehmen?` plus Rumpf. Rumpf nach Mockup: „Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Trips." (Trip) bzw. „… für diesen Ort." / „… für diese Orte." (Orte), danach „Zustellung, Etappen und Orte bleiben unverändert." `frage_vergleich` wird an diesen Wortlaut angeglichen.
5. **Unterzeile eigener Vorlagen:** „eigene" plus vorhandene `description`. Die Herkunft „aus GR221 gespeichert" braucht ein neues Datenfeld im Backend und wandert in #3189 (Besitzer-Einträge dorthin).
6. **Nicht in dieser Scheibe:** Checkbox statt Schalter, Inline-Karte statt modalem Dialog, einzeiliges Feld statt Textbereich (#3190).
7. **Abschluss:** Staging-Abgleich `--scope wetter` DE und EN, Einträge `#3111` entfernen, Zählwächter nachziehen.

Weitere Festlegungen:

- Anführungszeichen in allen betroffenen Texten „…" (statt ‚…'); EN sinnvoll übersetzt, Anführungszeichen dort laut Katalogkonvention; Protokoll-Token nie übersetzt.
- Der Abweichend-Satz steht als Textknoten direkt im Hinweis-Absatz hinter dem Hinweis (kein Kind-Element: der Abgleich-Sammler `sichtbareTexte()`, elementliste-abgleich.staging.spec.ts:110-132, liest nur eigene Textknoten je Element; siehe docs/artifacts/feat-3111-wetter-dialoge-mockup/klaerung-textlesung.md) und wird nur bei Abweichung gerendert. Der testid `wetter-grenzen-abweichend-{id}` entfällt; E2E s3a2794-teil3-grenzen.spec.ts:56 wird angepasst. Gleiches Prinzip für Bestätigungs-Rumpf und „Name · aktiv“ (je ein Element, nur Text); Grenzen-Titel `{x_1}<br>{x_2}` ohne Leerraum.
- Knopf-Reihenfolge im Speichern-Dialog: Speichern vor Abbrechen (Bestätigungs-Dialog hat sie bereits: Übernehmen, Abbrechen).
- Betroffene Bestandstests (Unit: `s3a2794_teil3_wetter_katalog`, `deutsch_unveraendert`, `wetter_tab_abschnitt_marker_2966`, `elementliste_abgleich_bedienplan`; E2E: `s3a2794-teil3-vorlage`, `-grenzen`, `-dialog`, `-englisch`) werden auf die neue Form angepasst.

## Expected Behavior

- **Input:** Nutzer öffnet im Hub-Reiter Wetter von Trip oder Orten „Grenzen ändern", das Vorlagen-Menü, eine Vorlagen-Bestätigung bzw. „Als eigene Vorlage speichern".
- **Output:** Die Dialoge zeigen Wortlaut, Aufbau und Reihenfolge des Mockups Fassung 4 in der Sprache des Nutzers.
- **Side effects:** Keine Datenänderung; die Anzahl offener Abweichungen in der Elementliste sinkt um die `#3111`-Einträge.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Unit: GIVEN Katalog DE/EN WHEN Schlüssel für Grenzen-Titel, Stichworte, Bestätigung, Platzhalter geladen werden THEN sind alle vorhanden, EN ungleich DE, Quotes „…" ohne ‚…'.
- [ ] Unit: GIVEN unbekannte Vorlagen-ID WHEN Kurzbeschreibung gebildet wird THEN greift die Ableitung aus den aktiven Metriken (Fallback).
- [ ] Unit: GIVEN Systemvorlage mit bekannter ID WHEN Kurzbeschreibung gebildet wird THEN steht die Zahl aus den Daten vor den kuratierten Stichworten.
- [ ] E2E (Browser, Trip und Orte, DE und EN): GIVEN geöffneter Grenzen-Editor / Vorlagen-Menü / Bestätigung / Speichern-Dialog WHEN der sichtbare Text gelesen wird THEN entspricht er dem Mockup (ACs unten).
- [ ] Klärung per RED-Test im echten Browser: Liest der Abgleich-Sammler `textContent` oder `innerText`? Davon hängt ab, ob die `<br>`-Lösung ohne Leerzeichen zwischen den Titelzeilen passt oder zusätzlicher Leerraum nötig ist (Technikfrage, keine PO-Frage).
- [ ] Staging: `elementliste_abgleich` mit `--scope wetter` in DE und EN ohne Befund für diese Dialog-Elemente.
- [ ] `tests/test_2913_c2_besitzerliste.py`: Zählwächter für `#3111` ist auf den Reststand nachgezogen (Einträge entfernt bzw. auf #3189).

## Acceptance Criteria

- **AC-1:** Given der Hub-Reiter Wetter von Trip oder Orten in Deutsch oder Englisch / When der Nutzer bei einer Metrik „Grenzen ändern" öffnet / Then stehen die Gruppentitel zweizeilig („unten" über „zu wenig", „oben" über „zu viel"; englisch sinngemäß übersetzt) und nicht mehr einzeilig mit Schrägstrich.
  - Test: Im echten Browser Grenzen-Editor öffnen, Titel der beiden Gruppen lesen und prüfen, dass zwei getrennte Zeilen angezeigt werden, in DE und EN, in Trip und Orten.

- **AC-2:** Given der geöffnete Grenzen-Editor einer Metrik / When der Hinweistext angezeigt wird / Then stehen Hinweis (z.B. Grün zwischen „gelb unten" und „gelb oben") und der Satz „Abweichend von der Vorlage „{Name}"." im selben Absatz mit „…"-Anführungszeichen, und der Abweichend-Satz erscheint nur, wenn die Metrik von der Vorlage abweicht.
  - Test: Nutzer ändert eine Grenze (Abweichung vorhanden) und prüft den Absatz mit beiden Sätzen; bei unveränderter Vorlage fehlt der Abweichend-Satz; Quotes sind „…", DE und EN, Trip und Orte.

- **AC-3:** Given das geöffnete Vorlagen-Menü eines Trips oder Orte-Briefings / When die aktive Vorlage in der Liste steht / Then trägt ihr Name den sichtbaren Zusatz „· aktiv", und keine andere Vorlage trägt ihn.
  - Test: Menü im Browser öffnen, Text der aktiven Vorlage lesen („Name · aktiv"), die übrigen Einträge ohne Zusatz; nach Wechsel der Vorlage wandert der Zusatz mit (DE und EN, Trip und Orte).

- **AC-4:** Given das Vorlagen-Menü / When die Systemvorlagen aufgelistet werden / Then zeigt jede bekannte Systemvorlage die Metrik-Zahl aus den Daten plus die kuratierten Stichworte aus dem Katalog (z.B. „14 Metriken · Gewitter, Böen, Nullgradgrenze"), und eine unbekannte Vorlagen-ID fällt auf die Ableitung aus den aktiven Metriken zurück.
  - Test: Im Browser die Unterzeile jeder Systemvorlage lesen: Zahl entspricht den aktiven Metriken der Vorlage, Stichworte entsprechen dem Katalog (DE und EN); Unit-Test mit unbekannter ID prüft den Fallback.

- **AC-5:** Given der Nutzer besitzt eine selbst gespeicherte Vorlage / When das Vorlagen-Menü den Bereich „Eigene" zeigt / Then steht unter dem Namen die Unterzeile „eigene" (englisch „own"), ergänzt um die Beschreibung der Vorlage, falls eine vorhanden ist.
  - Test: Eigene Vorlage mit und ohne Beschreibung anlegen, Menü öffnen und die Unterzeile lesen („eigene" bzw. „eigene · {Beschreibung}"), DE und EN, Trip und Orte.

- **AC-6:** Given das Vorlagen-Menü / When der Nutzer eine andere Vorlage auswählt / Then erscheint die Bestätigung zweiteilig mit fettem Titel „„{Name}" übernehmen?" und einem Rumpf, der für Trip „… Alarmstufen dieses Trips", für einen einzelnen Ort „… für diesen Ort" und für mehrere Orte „… für diese Orte" nennt, bei vorhandenen Abweichungen den Satz „Deine N Abweichung(en) von „{alte Vorlage}" geht/gehen verloren." (Anführungszeichen „…") enthält und mit „Zustellung, Etappen und Orte bleiben unverändert." endet; Übernehmen steht vor Abbrechen.
  - Test: Im Browser eine Vorlage anklicken, Titel und Rumpf getrennt lesen, Wortlaut je Kontext (Trip, ein Ort, mehrere Orte) in DE und EN prüfen und Knopf-Reihenfolge kontrollieren.

- **AC-7:** Given der Dialog „Als eigene Vorlage speichern" / When er geöffnet wird / Then heißt das Feld „Beschreibung (optional)" mit Platzhalter „wofür die Vorlage gedacht ist", das Namensfeld hat den Platzhalter „z.B. Mallorca Frühling", und der Knopf Speichern steht vor Abbrechen.
  - Test: Dialog im Browser öffnen, Label, beide Platzhalter und die Reihenfolge der Knöpfe lesen, in DE und EN (englische Texte sinnvoll übersetzt), in Trip und Orten.

- **AC-8:** Given Trip und Orte-Briefing sowie Deutsch und Englisch / When AC-1 bis AC-7 geprüft werden / Then gelten sie in allen vier Kombinationen aus demselben geteilten Code, Protokoll-Token (z.B. SMS-Kürzel, `compact_label`) bleiben dabei unübersetzt, und alle neuen Texte stammen aus dem Katalog.
  - Test: E2E-Läufe für Trip und Orte je in DE und EN; Katalog-Test prüft, dass DE und EN dieselben Schlüssel tragen und keine Texte fest im Code stehen.

- **AC-9:** Given der Staging-Server mit der neuen Version / When der Elementlisten-Abgleich mit `--scope wetter` in DE und EN läuft / Then meldet er für die Dialog-Elemente dieser Scheibe keinen Befund, die Besitzer-Einträge `#3111` sind aus der Besitzerliste entfernt (Rest für die Herkunfts-Unterzeile auf #3189), und der Zählwächter ist auf den Reststand nachgezogen.
  - Test: Abgleich gegen Staging in beiden Sprachen starten und Befundliste lesen; Besitzer-Test (`tests/test_2913_c2_besitzerliste.py`) läuft grün mit angepasster Zahl.

## Definition of Done

- AC-1 bis AC-9 durch Tests belegt, Kern-Tests grün, alle 6 CI-Checks grün
- Elementlisten-Abgleich `--scope wetter` auf Staging in DE und EN ohne Befund für die Dialog-Elemente dieser Scheibe
- Besitzer-Einträge `#3111` entfernt, Rest für die Herkunftszeile auf #3189, Zählwächter nachgezogen
- Änderung in `main`, auf Produktion ausgeliefert, Ergebnis im Issue dokumentiert

## Known Limitations

- Herkunft „aus GR221 gespeichert" in der Unterzeile eigener Vorlagen fehlt bis #3189 (neues Backend-Datenfeld).
- Checkbox „Als Standard", Inline-Karte statt modalem Dialog und einzeiliges Beschreibungsfeld (Mockup) bleiben bis #3190 abweichend.
- Mockup-Beispielzahlen (z.B. „Wandern 10 Metriken", Ampel hat 11 aktiv) bleiben bewusst aus Daten abgeleitet (#3151).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue
- **Rationale:** Epic #2913 legt das Mockup als Soll fest; die Scheibe ändert nur Texte und Aufbau innerhalb bestehender Bausteine. Bezug: ADR-0104 (Zweisprachigkeit, Katalog), ADR-0112 (Bausteine).

## Changelog

- 2026-11-19: Initial spec created (löst feat_2794_s3a Z. 123, 124, 139 und AC-10 in diesen Punkten ab)
