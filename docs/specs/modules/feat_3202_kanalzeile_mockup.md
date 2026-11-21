---
entity_id: feat_3202_kanalzeile_mockup
type: feature
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.1"
workflow: feat-3202-kanalzeile-mockup
tags: [zustellung, kanaele, mockup, epic-2913]
---

# Kanalzeile im Reiter Zustellung nach Mockup Fassung 4 (#3202)

## Approval

- [ ] Approved

## Purpose

Die Statuszeile der Kanaltabelle im Reiter Zustellung (Trip und Orts-Vergleich) zeigt heute Rohwerte (volle Adresse, Chat-ID, ungekürzte Nummer, Premium-Rückadresse). Sie soll gekürzte Adresse und Nummer zeigen, keine Chat-ID und keine Premium-Rückadresse; Mockup und Produkt werden auf die PO-Entscheidungen abgeglichen.

## Source

- **File:** `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts`
- **Identifier:** `kanalStatus()`, neu `adresseGekuerzt()`, `nummerGekuerzt()`

PO-Entscheidungen (verbindlich): 20.11.2026 Telegram nur „verbunden“ ohne Namen; Kürzung E-Mail `lokalteil@…`, Telefon `+<Landesvorwahl> <3 Ziffern> …`; Premium im Normalzustand ohne Rückadresse. 21.11.2026: „+N Empfänger“ entfällt überall (auch Orts-Vergleich), weil `preset.empfaenger` seit #1452 wirkungslos ist. Frontend-only, kein neues Backend-Feld. Kontext: `docs/context/feat-3202-kanalzeile-mockup.md`.

## Scope

### Im Scope
- Reine Kürzungsfunktionen mit Unit-Tests; Anwendung nur in der Kanalzeile.
- Premium-Zeile ohne Rückadresse (Normal und „Rückadresse verfallen“); Telegram ohne Chat-ID; kein Empfängerzusatz in keinem Kontext.
- Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` angleichen: Telegram-Zeile „verbunden“ statt `@henning`, E-Mail-Zeile ohne „+1 Empfänger“. Danach Elementliste deterministisch neu erzeugen; sie ändert sich nur in diesen Zeilen.
- Elementliste/Besitzer: 23 `#3202`-Einträge abräumen, Zählwächter `tests/test_2913_c2_besitzerliste.py` auf `"#3202": 0` (`"#3194"` bleibt 8). Keine Telegram-Ausnahme, keine Umhängung von E-Mail-Zeilen nach #3194.

### Nicht im Scope
- Telegram-Name speichern (Datenschutz), Empfängerfeld für Trips, Auswertung von `preset.empfaenger`, Backend-/Profil-Änderungen.
- Kontosettings und `channelContactLabel.ts` (Volltext bleibt, Versand-Dialoge #1510).

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts` | MODIFY | Kürzungsfunktionen, `kanalStatus` mit gekürztem Ziel, Premium/Telegram ohne Ziel |
| `frontend/src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte` | MODIFY | nur falls Anzeige-Anpassung nötig |
| `frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts` | MODIFY | Kürzung, Zustände |
| `frontend/e2e/s3b2795-zustellung-kanaele.spec.ts`, `-englisch.spec.ts`, `-mandanten.spec.ts` | MODIFY | Nutzersicht Trip/Vergleich, DE/EN, zwei Nutzer |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | MODIFY | Telegram und E-Mail Sollzeile angleichen |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | deterministisch neu erzeugt |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | 23 `#3202` entfernen |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY | `"#3202": 0` |

## Estimated Scope

- **LoC:** ca. +60/-40 plus Tests (ohne generierte Elementliste)
- **Files:** 9
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `zustellungModell.ts` (`kanalStatus`, `premiumStatus`) | module | Statuslogik, Ort der Kürzung |
| `ZustellungTab.svelte` / `KanalTabelle.svelte` | component | Ein Code für `context="route"\|"vergleich"` |
| Katalog `zustellung.json` DE/EN | i18n | Nutzertexte (ADR-0104), keine neuen Schlüssel erwartet |
| Mockup Fassung 4, `elementliste.json`, `elementliste_besitzer.json`, `elementliste_abgleich_logik.ts` | Prüfdaten | Soll/Ist-Abgleich |
| `feat_2795_s3b_teil1_zustellung.md`, `feat_2913_abgleich_ganzseite.md` | Specs | Bestehende Kanalstatus-ACs, Zustände |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt ADR-0112 (Oberfläche gegen Mockup) um, indem das Mockup an PO-Entscheidungen angeglichen wird statt Ausnahmen zu führen; hält ADR-0104 (Katalog, Adressen/Nummern unübersetzt) und ADR-0095 (alle vier Kanäle gleichrangig, Kürzung benachteiligt keinen) ein. Keine neue Grundsatzentscheidung.

## Implementation Details

Trip und Orts-Vergleich teilen den Code (shared, `context`); keine Pendant-Komponente, keine Kontext-Verzweigung für die Kanalzeile.

- `adresseGekuerzt(mail)`: Text vor erstem `@` + `@…`; Lokalteil nie weiter gekürzt (auch kurz, z.B. `a@…`); ohne `@` oder leer: leerer String.
- `nummerGekuerzt(nr)`: Leerzeichen/Trenner entfernen; mit `+`: Landesvorwahl 1 bis 3 Ziffern (`+1`, `+7`, `+49`, `+353`), danach erste 3 Ziffern der Rufnummer, dann ` …` (`+49 171 …`); ohne `+`: erste 3 Ziffern + ` …`; leer: leerer String; unter 3 Ziffern: Rest + ` …` ohne Fehler.
- `kanalStatus`: E-Mail `bestätigt · lokalteil@…` (kein Empfängerzusatz, nirgends); SMS `bestätigt|unbestätigt · +49 171 …`; Telegram `verbunden` bzw. `nicht verbunden`, nie Chat-ID; Premium nur Statustext (`inReach · Rückadresse verfallen` im Lückenzustand), ohne Ziel.
- Mockup: Telegram-Zeile `verbunden`, E-Mail-Zeile `bestätigt · henning@…`; Elementliste per vorhandenem Erzeugungsskript neu (deterministisch, Diff nur in diesen Zeilen). Besitzer: `#3202`-Einträge löschen; die Zahl im Zählwächter im selben Schritt ändern.

## Expected Behavior

- **Input:** Profil (`mail_to`, `sms_to`, Verifizierungen, Telegram, Premium).
- **Output:** Statuszeile je Kanal gekürzt wie oben, Trip und Orts-Vergleich identisch; keine Empfängerzahl.
- **Side effects:** keine; nur Anzeige, Daten unverändert.

## Test Plan

### Automated Tests (TDD RED)
- [ ] `adresseGekuerzt`: `henning@example.com` ergibt `henning@…`; `a@x.de` ergibt `a@…`; leer und ohne `@` ergibt leer.
- [ ] `nummerGekuerzt`: `+491711234567` ergibt `+49 171 …`; `+14155550123` ergibt `+1 415 …`; `+353871234567` ergibt `+353 871 …`; `0171 1234567` ergibt `017 …`; leer ergibt leer.
- [ ] `kanalStatus`: Premium Normal und stale ohne Rückadresse; Telegram ohne Chat-ID; E-Mail ohne Empfängerzusatz.
- [ ] E2E: Reiter Zustellung Trip und Orts-Vergleich (auch mit gefülltem `preset.empfaenger`), Normal und Lücken, DE und EN.
- [ ] Zählwächter mit `"#3202": 0`, `"#3194": 8`; Elementliste-Neuerzeugung ändert nur die Telegram- und E-Mail-Sollzeilen.

## Acceptance Criteria

- **AC-1:** Given ein Konto mit bestätigter E-Mail `henning@…`, bestätigter Handynummer `+49 171 …` und verbundenem Telegram / When der Nutzer den Reiter Zustellung eines Trips öffnet / Then zeigt die Kanalzeile `bestätigt · henning@…`, `bestätigt · +49 171 …` und `verbunden`, ohne volle Adresse, volle Nummer oder Chat-ID.
  - Test: Nutzersicht im Browser (E2E), Texte der Kanaltabelle auslesen.
- **AC-2:** Given ein Trip und ein Orts-Vergleich, dessen `preset.empfaenger` mit weiteren Adressen gefüllt ist / When der Nutzer jeweils den Reiter Zustellung öffnet / Then zeigt weder der Trip noch der Orts-Vergleich eine Empfängerzahl in der E-Mail-Zeile.
  - Test: E2E Vergleich mit gefülltem Empfängerfeld gegen Trip, Zeilentext enthält kein „Empfänger“.
- **AC-3:** Given die Kürzungsfunktionen / When sie kurze Lokalteile, Nummern ohne `+`, ausländische Vorwahlen mit 1 bis 3 Ziffern oder leere Werte erhalten / Then liefern sie die festgelegte Kürzung bzw. einen leeren Text, nie einen Fehler und nie den Volltext.
  - Test: Unit-Tests der reinen Funktionen (Grenzfälle).
- **AC-4:** Given der Zustand „Lücken“ (unbestätigte Nummer, verfallene Premium-Rückadresse, Telegram nicht verbunden) / When der Nutzer den Reiter öffnet / Then steht dort `unbestätigt · +49 171 …`, `inReach · Rückadresse verfallen` ohne Rückadresse und `nicht verbunden`.
  - Test: E2E mit umgeschriebener Profilantwort, Kanalzeilen auslesen.
- **AC-5:** Given Premium-SMS im Normalzustand / When der Nutzer den Reiter öffnet / Then zeigt die Premium-Zeile den Status ohne Rückadresse.
  - Test: E2E und Modelltest Premium fresh.
- **AC-6:** Given die Oberfläche in Deutsch bzw. Englisch / When der Nutzer den Reiter in Trip und Orts-Vergleich öffnet / Then erscheinen alle Statustexte in der gewählten Sprache aus dem Katalog, Adressen und Nummern bleiben unübersetzt.
  - Test: E2E DE/EN (`s3b2795-zustellung-englisch.spec.ts`).
- **AC-7:** Given Staging mit dem Prüfkonto / When der Ganzseitenvergleich gegen die Elementliste läuft (DE und EN) / Then gibt es für die Kanalzeile keine neue Abweichung, die 23 Einträge `#3202` sind entfallen, es gibt keine Telegram-Ausnahme.
  - Test: Abgleichslauf `elementliste-abgleich.staging.spec.ts` und Zählwächter.
- **AC-8:** Given zwei verschiedene Nutzer mit unterschiedlichen Adressen und Nummern / When jeder den Reiter Zustellung öffnet / Then sieht jeder nur die gekürzten Werte seiner eigenen Daten.
  - Test: E2E `s3b2795-zustellung-mandanten.spec.ts` mit zwei Nutzern.
- **AC-9:** Given das angeglichene Mockup Fassung 4 / When die Elementliste neu erzeugt wird / Then entsprechen die Sollzeilen der Kanaltabelle den PO-Entscheidungen (Telegram `verbunden`, E-Mail ohne „+1 Empfänger“) und die Liste ändert sich nur in diesen Zeilen; keine Sollzeile bleibt ohne Besitzer.
  - Test: deterministische Neuerzeugung, Diff-Prüfung und Zählwächter (`#3194` bleibt 8, `#3202` 0).

## Definition of Done

- [ ] Alle Unit- und E2E-Tests aus dem Test Plan grün, Kern-Schicht 100 %.
- [ ] Staging-Ganzseitenvergleich ohne neue Abweichung, Bildprüfung gegen das angeglichene Mockup (ADR-0112).
- [ ] Mockup, Elementliste, Besitzerliste und Zählwächter im selben Schritt angepasst.
- [ ] Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe der Kürzung.
- [ ] Deploy mit Selftest Exit 0; Issue #3202 geschlossen.

## Known Limitations

- Kürzung nur in der Kanalzeile; Kontosettings zeigen weiterhin Volltext.
- Landesvorwahl-Erkennung ist eine feste Tabelle; unbekannte Vorwahlen fallen auf 3 Ziffern zurück.
- Der Telegram-Name fehlt bewusst (Datenschutz); das Mockup wird entsprechend angeglichen.
- Eine Empfängerzahl gibt es nirgends, solange `preset.empfaenger` wirkungslos ist (#1452).

## Changelog

- 2026-11-21: Initial spec created
- 2026-11-21: Überarbeitet nach PO-Entscheidung 21.11.: „+N Empfänger“ entfällt überall, Mockup und Elementliste angeglichen, Telegram-Ausnahme entfällt
