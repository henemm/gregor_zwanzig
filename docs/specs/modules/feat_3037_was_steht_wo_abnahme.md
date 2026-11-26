---
entity_id: feat_3037_was_steht_wo_abnahme
type: feature
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: abnahme-3037-was-steht-wo
tags: [was-steht-wo, abnahme, soll-ist-bild, mockup, handy, "#3037", "#3122", "#2795"]
---

# Abnahme der Tabelle „Was steht wo“ mit Soll/Ist-Bild (#3037)

## Approval

- [ ] Approved

## Purpose

Schließt die Abschlussabnahme der Tabelle „Was steht wo“ im Reiter Wetter (Bau #3122, Baustein B7): Das Soll-Bild (Mockup Fassung 4) wird für Trip und Orte, am Computer (1280 px) und am Handy (390 px), gegen Staging gelegt, jede Abweichung bekommt einen Besitzer, und Henning erhält ein Soll/Ist-Bild (links Mockup, rechts Staging). Zusätzlich wird nachgewiesen, dass ein Vergleich mit genau einem Ort „Orte“ heißt, dass auf dem Handy fünf Haken-Spalten ohne seitliches Scrollen nebeneinander stehen und dass „Einstellung = Ausgabe“ (Elementliste, Mail-Validatoren, Katalog #3047) gilt.

## Source

- **File:** `frontend/e2e/wsw-abnahme-3037.staging.spec.ts`, `frontend/playwright.3037-wsw-abnahme.staging.config.ts`, `scripts/soll_ist_bild.py`, `docs/reference/mail_validators.md`
- **Identifier:** Playwright-Test-Datei der Abnahme, Bildfunktion `soll_ist_bild` (reine Funktion, ohne Netz), Abschnitt „Soll aus der gespeicherten Konfiguration — `--konfig`“

Schicht: Test-/Werkzeug-Schicht (Staging-E2E, Python-Skript, Referenzdoku). Kein Frontend-Produktcode, kein Go, kein Python-Core. Produktcode ändert sich nur, wenn eine Abweichung **in der Karte** im selben Workflow als kleiner Fix behoben wird; Abweichungen außerhalb der Karte bekommen ein eigenes Issue mit Verweis. Keine Änderung an Gate-Konfiguration, kein Schritt, der eine menschliche Sperre braucht.

Querschnitt:

- **Trip/Ortsvergleich-Teilung:** unberührt, keine neue Komponente; der Test prüft beide Kontexte (`route`, `vergleich`) an derselben geteilten Karte.
- **Mandantentrennung:** Das Prüfkonto sieht nur eigene Daten (Login per `/api/auth/login`, `user_id` aus dem Login, kein `"default"`). Das Wegwerf-Abo entsteht nur im Prüfkonto und wird dort wieder entfernt; Test AC-9 prüft, dass ein zweites Konto es nicht sieht.
- **Kanäle:** Die Abnahme betrifft die Einstellung für alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS); die Karte zeigt sie gleichrangig, der Mail-Nachweis deckt E-Mail ab, der Katalog #3047 die übrigen Ausgaben.

## Estimated Scope

- **LoC:** ~285 (Spec-Test ~150, Config ~30, Bildskript ~60, Doku ~5 Zeilen, dazu Test ~40)
- **Files:** 5
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_3122_was_steht_wo.md` | Spec | AC-21, AC-27, AC-33, AC-35–37, Handy am Gerät (Z. 354), Validatoren `--konfig` (Z. 318/324) |
| `docs/adr/0124-was-steht-wo-eine-tabelle.md` | ADR | Nr. 10 (Bereich „Orte“), Konsequenzen (Handy), Folgepflichten |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | Mockup | Soll-Bild, Kontexte `[data-ctx="trip|orte|ort1"]` |
| `frontend/e2e/ganzseitenaufnahme.ts` | Hilfe | `ganzseite(page, datei)` für Ganzseitenbild |
| `frontend/e2e/was-steht-wo.helpers.ts` | Hilfe | `seedAbo(..., {orte:1})` für das Wegwerf-Abo |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | Vorbild | Prüfkonto-Login per `/api/auth/login` |
| `frontend/playwright.3283-wsw-bildabgleich.staging.config.ts` | Vorbild | Basic-Auth-Konfiguration für Staging |
| `scripts/elementliste_abgleich.ts` | Skript | `npm run elementliste:abgleich -- --abnahme --scope wetter/normal` |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py` | Validatoren | Mail-Nachweis mit `--konfig` |
| `POST /api/briefings/{id}/send?kind=route\|vergleich` | Go-API | Staging-Mail mit bekannter Konfiguration auslösen (nur genutzt) |
| Prüfkatalog #3047 (`tests/fixtures/einstellung_gleich_mail/`) | Test | Kern-Schicht „Einstellung = Ausgabe“ |
| `mockup-bildpruefer` | Agent | Soll/Ist-Bild-Prüfung, höchstens zwei Runden |
| #3364 (andere Sitzung) | Issue | Trip-Karte („nur morgens/abends“), macht drei `todo`/`xfail`-Fälle grün |
| Staging, Prüfkonto-Seed, Stalwart-Test-Postfach | Umgebung | Messläufe |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/wsw-abnahme-3037.staging.spec.ts` | CREATE | Prüfkonto-Login, Ganzseitenbilder, Mockup-Gegenbilder, Handy- und Ein-Ort-Prüfungen |
| `frontend/playwright.3037-wsw-abnahme.staging.config.ts` | CREATE | Staging-Konfiguration mit Basic-Auth, `workers: 1`, kein 1895-Setup, kein storageState |
| `scripts/soll_ist_bild.py` | CREATE | Mockup links, Staging rechts, beschriftet, je Kontext, Breite und Sprache ein PNG |
| `tests/tdd/test_soll_ist_bild.py` | CREATE | Test der reinen Bildfunktion ohne Netz |
| `docs/reference/mail_validators.md` | MODIFY | Veralteten Hinweis (Z. 139, „Soll ab #3122 … noch nicht gebaut“) auf den gebauten Stand bereinigen |

Nicht im Scope: Karten-Produktcode (außer kleinem Fix nach Definition of Done), Backend, Gate-Konfiguration, Trip-Anzeige aus #3364.

## Implementation Details

1. **Playwright-Konfiguration:** wie `playwright.3283-wsw-bildabgleich.staging.config.ts` (nginx-Basic-Auth, Staging-Adresse), `workers: 1`. Kein Setup-Projekt aus #1895 und kein storageState.
2. **Login und IDs:** Der Test meldet das Prüfkonto per `/api/auth/login` mit `GZ_AUTH_USER`/`GZ_AUTH_PASS` an (Muster `elementliste-abgleich.staging.spec.ts`). Trip = `ELEMENTLISTE_TRIP_ID`, Orte (drei Orte) = `ELEMENTLISTE_ORTE_ID`. Ist eine ID oder das Konto nicht erreichbar, bricht der Test mit klarer Meldung ab.
3. **Ein-Ort-Fall:** Wegwerf-Abo über `seedAbo(..., {orte:1})` mit eindeutigem Namenspräfix. Aufräumen im `finally` und zusätzlich in `afterAll` (alle Abos mit dem Präfix). Vor dem Anlegen wird die Quota des Prüfkontos geprüft; bei erschöpfter Quota klarer Abbruch statt Fehlschlag mitten im Lauf.
4. **Ganzseitenbild:** `ganzseite()` für Reiter Wetter, Kontexte trip, orte, ort1, Sprache DE und EN, Breite 1280 und 390. Die Sprache wird am Prüfkonto umgeschaltet und am Ende immer auf DE zurückgesetzt (auch bei Fehlern). Mockup-Gegenbilder nur DE, je Kontext (`trip`, `orte`, `ort1`) und Breite, über `[data-ctx=…]`.
5. **Handy-Prüfung:** Bei 390 px, EN, Kontext Orte stehen fünf Haken-Spalten mit Umschaltern nebeneinander; das Karten-Rollfeld läuft nicht über (`scrollWidth <= clientWidth`). Kontrast-Mindestwert WCAG AA ist bereits Teil von AC-33 der Spec #3122 und wird dort nicht neu geprüft.
6. **Ein-Ort-Texte:** Im Kontext ort1 heißt der Bereich „Orte“ (DE) bzw. „Locations“ (EN); kein sichtbarer Text enthält „alle Orte“/„1 Orte“ oder englisches Pendant im Plural, das mehrere Orte voraussetzt.
7. **`scripts/soll_ist_bild.py`:** reine Funktion `(mockup_png, staging_png, titel) -> Bild` mit PIL: Mockup links, Staging rechts, Beschriftung „Soll (Mockup)“ / „Ist (Staging)“ mit Kontext, Breite, Sprache; Ausgabe je Kombination ein PNG. Kleinere Höhe wird mit Hintergrund aufgefüllt, nicht verzerrt. Kommandozeile dünn über der Funktion.
8. **Dokumentation:** In `docs/reference/mail_validators.md` wird der Hinweis zu #3122 auf Ist-Stand umgeschrieben (gebaut; Abnahme „Einstellung = Ausgabe“ gegen Katalog #3047, nachgewiesen in #3037).
9. **Messläufe (Definition of Done, keine Code-Dateien):**
   - Elementliste `npm run elementliste:abgleich -- --abnahme --scope wetter/normal`, einmal DE, einmal mit `--sprache en`, jeweils mit Prüfkonto und Seed-IDs: Abschnitt „was-steht-wo“ ohne Abweichung; jede andere Abweichung der Seite erhält einen Besitzer (Issue).
   - Staging-Mails Trip, drei Orte, ein Ort: Konfig per GET holen, Versand per `POST /api/briefings/{id}/send?kind=route|vergleich`, Validatoren mit `--konfig`, Exit 0.
   - Katalog #3047 Kern-Schicht grün: Ausgangsstand 26.11. EXIT 0 mit drei `xfail` (Fälle aus #3364); nach Auslieferung #3364 ohne `todo`/`xfail` dieser Fälle.
   - `mockup-bildpruefer` je Kontext und Breite höchstens zwei Runden ohne offenen Befund, oder jeder Befund ist zugeordnet (behoben oder eigenes Issue mit Verweis).
10. **Reihenfolge:** Orte und Ein-Ort jetzt. Trip-Bild, Trip-Mail und Katalog-Vollständigkeit erst nach Auslieferung von #3364 (andere Sitzung).
11. **Abweichungen:** In der Karte im selben Workflow als kleiner Fix beheben; außerhalb der Karte eigenes Issue mit Besitzer, nie „kommt später“.

## Definition of Done

- [ ] Spec freigegeben, Test `test_soll_ist_bild.py` rot vor Umsetzung, dann grün
- [ ] Staging-Lauf Orte und Ein-Ort (DE/EN × 1280/390) grün, Wegwerf-Abo entfernt, Sprache DE
- [ ] Elementliste `--abnahme` DE und EN: Abschnitt der Tabelle ohne Abweichung, übrige Abweichungen zugeordnet
- [ ] Mail-Nachweis Orte (3 Orte, 1 Ort) mit `--konfig`, Exit 0
- [ ] Soll/Ist-Bilder an Henning, Bildprüfer-Befunde zugeordnet
- [ ] Nach #3364: Trip-Bild, Trip-Mail, Katalog ohne `todo`/`xfail`
- [ ] PR mit allen 6 CI-Checks grün, Deploy und Selftest, Issue #3037 erst nach vollständiger Abnahme schließen

## Expected Behavior

- **Input:** Prüfkonto auf Staging mit Seed (Trip, Orte mit drei Orten) und ein Wegwerf-Abo mit einem Ort.
- **Output:** Ganzseitenbilder je Kontext, Sprache und Breite; Mockup-Gegenbilder; zusammengesetzte Soll/Ist-PNGs; Messprotokolle (Elementliste, Mail-Validatoren, Katalog).
- **Side effects:** Wegwerf-Abo und ein Ort im Prüfkonto während des Laufs (danach entfernt); Prüfkonto-Sprache wird zwischenzeitlich umgeschaltet und am Ende auf DE gesetzt.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Bildfunktion (pytest, ohne Netz, `tests/tdd/test_soll_ist_bild.py`): GIVEN Mockup- und Staging-Bild gleicher Breite, unterschiedlicher Höhe WHEN zusammengesetzt THEN Mockup links, Staging rechts, beide unverzerrt, Beschriftung „Soll (Mockup)“/„Ist (Staging)“ mit Kontext, Breite, Sprache (AC-5)
- [ ] Bildfunktion (pytest): GIVEN Bilder unterschiedlicher Breite WHEN zusammengesetzt THEN klarer Abbruch statt stiller Skalierung (AC-5)
- [ ] Staging-Lauf (`frontend/e2e/wsw-abnahme-3037.staging.spec.ts`, nur `/e2e-verify`): Ganzseitenbilder je Kontext × DE/EN × 1280/390 mit Bildbreite = Fensterbreite (AC-1), Mockup-Gegenbilder (AC-4), Ein-Ort-Texte (AC-2), 390 px EN Orte fünf Spalten ohne Überlauf (AC-3), Aufräumen + Sprache DE + zweites Konto sieht Wegwerf-Abo nicht (AC-9)

### Messläufe (Abnahme, kein Code)

- [ ] Elementliste `--abnahme --scope wetter/normal` DE und EN mit Prüfkonto (AC-6)
- [ ] Staging-Mails Trip, drei Orte, ein Ort + Validatoren `--konfig` Exit 0 (AC-7)
- [ ] Katalog #3047 Kern-Schicht Exit 0 (AC-8)
- [ ] `mockup-bildpruefer` je Kontext/Breite, Soll/Ist-Bild an Henning (AC-10)

## Acceptance Criteria

- **AC-1:** Given das Prüfkonto ist auf Staging angemeldet und der Trip, der Orte-Vergleich mit drei Orten bzw. das Abo mit einem Ort ist geöffnet (Trip erst nach Auslieferung #3364) / When die Ganzseitenbilder im Reiter Wetter bei 1280 px und 390 px, je Deutsch und Englisch, aufgenommen werden / Then entstehen je Kontext vier Bilder, deren Breite dem jeweiligen Fenster entspricht, und die Tabelle „Was steht wo“ ist darauf sichtbar.
  - Test: Staging-Playwright-Lauf als Prüfkonto, Bildbreite je Aufnahme gleich Fensterbreite, Tabelle sichtbar.

- **AC-2:** Given ein Wegwerf-Abo mit genau einem Ort existiert im Prüfkonto / When der Reiter Wetter dieses Orte-Vergleichs geöffnet wird / Then heißt der Bereich „Orte“ (Englisch „Locations“) und kein sichtbarer Text enthält Mehrzahl-Formulierungen wie „alle Orte“ oder „1 Orte“.
  - Test: Nutzer öffnet den Ein-Ort-Vergleich in DE und EN, Seitentext enthält die Bereichsüberschrift und keine der verbotenen Formulierungen.

- **AC-3:** Given das Handy-Fenster ist 390 px breit, die Sprache ist Englisch und der Orte-Vergleich mit drei Orten ist geöffnet / When die Tabelle „Was steht wo“ betrachtet wird / Then stehen die fünf Haken-Spalten mit ihren Umschaltern nebeneinander, und die Tabelle läuft nicht seitlich über (Inhaltsbreite höchstens so groß wie die sichtbare Breite).
  - Test: Staging-Playwright bei 390 px EN, fünf Spalten sichtbar im Fenster, `scrollWidth <= clientWidth` am Karten-Rollfeld.

- **AC-4:** Given das Mockup Fassung 4 für die Kontexte trip, orte und ort1 / When es bei 1280 px und 390 px in Deutsch aufgenommen wird / Then liegt je Kontext und Breite ein Mockup-Gegenbild vor, das als Soll für den Vergleich dient (sechs Bilder).
  - Test: Staging-Spec nimmt das Mockup über die Kontextmarke auf, sechs Dateien mit Fensterbreite als Bildbreite.

- **AC-5:** Given ein Mockup-Bild und ein Staging-Bild gleicher Breite / When die Bildfunktion sie zusammensetzt / Then zeigt das Ergebnis das Mockup links und das Staging-Bild rechts, beide beschriftet mit „Soll (Mockup)“ und „Ist (Staging)“ samt Kontext, Breite und Sprache, ohne Verzerrung bei unterschiedlicher Höhe.
  - Test: `tests/tdd/test_soll_ist_bild.py` mit zwei Testbildern unterschiedlicher Höhe, Breite des Ergebnisses gleich Summe beider, Farbpunkte links und rechts stimmen, Höhe gleich der größeren; kein Netz.

- **AC-6:** Given das Prüfkonto mit Seed-IDs für Trip und Orte / When der Elementlisten-Abgleich mit `--abnahme --scope wetter/normal` auf Deutsch und mit `--sprache en` läuft / Then meldet der Abschnitt „was-steht-wo“ keine Abweichung, und jede andere Abweichung der Seite ist einem Besitzer (Issue) zugeordnet.
  - Test: Abgleichlauf DE und EN gegen Staging, Bericht je Sprache ohne Abweichung im Abschnitt, Besitzerliste vollständig.

- **AC-7:** Given Staging-Mails für Trip, drei Orte und einen Ort wurden über die Versand-Schnittstelle ausgelöst / When der jeweilige Mail-Validator mit der gespeicherten Konfiguration (`--konfig`) die zugestellte Mail prüft / Then beendet er sich mit Exit 0, das heißt die Mail zeigt genau, was in der Tabelle eingestellt ist.
  - Test: Versand per API als Prüfkonto, Validator gegen die Mail im Stalwart-Test-Postfach, Exit-Code 0 je Fall (Trip erst nach #3364).

- **AC-8:** Given der Prüfkatalog #3047 für das neue Datenmodell / When die Kern-Schicht ausgeführt wird / Then endet sie mit Exit 0; vor Auslieferung #3364 bleiben genau die drei bekannten Fälle als `xfail`, danach ist kein Fall dieser Gruppe mehr `todo` oder `xfail`.
  - Test: Kern-Schicht-Lauf der Katalog-Testdateien, Ausgabe zählt grün, Ausnahme und offen.

- **AC-9:** Given ein zweites Konto neben dem Prüfkonto und ein Wegwerf-Abo im Prüfkonto / When der Test endet, auch nach einem Fehler, und das zweite Konto seine Abos abruft / Then ist das Wegwerf-Abo entfernt, die Prüfkonto-Sprache ist wieder Deutsch, und das zweite Konto hat das Abo nie gesehen.
  - Test: Abruf der Abos mit beiden Konten vor, während und nach dem Lauf (inkl. absichtlich abgebrochenem Lauf), Namenspräfix nicht mehr vorhanden, Sprache gleich DE.

- **AC-10:** Given die Soll/Ist-Bilder je Kontext und Breite liegen vor / When der Bildprüfer sie in höchstens zwei Runden prüft / Then ist jede Abweichung entweder in der Karte behoben oder einem eigenen Issue mit Verweis zugeordnet, und Henning erhält die Soll/Ist-Bilder mit Mockup links und Staging rechts.
  - Test: Bildprüfer-Bericht je Kontext/Breite ohne offenen Befund; jeder Befund trägt Issue-Nummer oder Verweis auf den Fix; Bilder an den PO übergeben.

## Known Limitations

- Handy „am Gerät“: Der Agent prüft nur das 390-px-Fenster; das echte Gerät sieht Henning über das Soll/Ist-Bild.
- Trip-Bild, Trip-Mail und vollständiger Katalog warten auf #3364 (andere Sitzung).
- Quota des Prüfkontos kann das Wegwerf-Abo verhindern; der Test bricht dann klar ab.
- `staging_mail_pruefen.py` legt immer drei Orte an und kennt kein `--konfig`; die Mails kommen deshalb über die Versand-Schnittstelle.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (setzt ADR-0124 um und prüft es)
- **Rationale:** Reines Prüfwerkzeug und Abnahme ohne neue Entscheidung; Wegwerf-Abo statt Seed-Erweiterung, weil der Elementlisten-Abgleich nur Trip- und Orte-IDs kennt und kein dauerhafter Ein-Ort-Bestand nötig ist.

## Changelog

- 2026-11-26: Initial spec created
