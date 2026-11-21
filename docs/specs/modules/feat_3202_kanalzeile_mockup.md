---
entity_id: feat_3202_kanalzeile_mockup
type: feature
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: feat-3202-kanalzeile-mockup
tags: [zustellung, kanaele, mockup, epic-2913]
---

# Kanalzeile im Reiter Zustellung nach Mockup Fassung 4 (#3202)

## Approval

- [ ] Approved

## Purpose

Die Statuszeile der Kanaltabelle im Reiter Zustellung (Trip und Orts-Vergleich) zeigt heute Rohwerte (volle Adresse, Chat-ID, ungekürzte Nummer, Premium-Rückadresse). Sie soll dem Mockup Fassung 4 entsprechen: gekürzte Adresse und Nummer, kein Chat-ID-Anhang, Empfängerzahl wo es zusätzliche Empfänger gibt.

## Source

- **File:** `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts`
- **Identifier:** `kanalStatus()`, neu `adresseGekuerzt()`, `nummerGekuerzt()`

PO-Entscheidungen 20.11.2026 (verbindlich): Telegram nur „verbunden“ ohne Namen; „+N Empfänger“ nur im Orts-Vergleich; Kürzung E-Mail `lokalteil@…`, Telefon `+<Landesvorwahl> <3 Ziffern> …`; Premium im Normalzustand ohne Rückadresse. Frontend-only, kein neues Backend-Feld. Kontext: `docs/context/feat-3202-kanalzeile-mockup.md`.

## Scope

### Im Scope
- Reine Kürzungsfunktionen mit Unit-Tests; Anwendung nur in der Kanalzeile.
- Premium-Zeile ohne Rückadresse (Normal und „Rückadresse verfallen“); Telegram ohne Chat-ID.
- E-Mail-Zusatz „+N Empfänger“ im Orts-Vergleich (N = zusätzliche Empfänger), Katalog DE/EN.
- Elementliste: 23 Besitzer-Einträge `#3202` abräumen; Telegram-`@name`-Abweichung als begründete Ausnahme; Zählwächter anpassen.

### Nicht im Scope
- Telegram-Name speichern (Datenschutz, PO-Entscheidung), neues Empfängerfeld für Trips, Backend-/Profil-Änderungen.
- Kontosettings und `channelContactLabel.ts` (Volltext bleibt, Versand-Dialoge #1510).

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts` | MODIFY | Kürzungsfunktionen, `kanalStatus(profil, empfaengerZusatz)`, Premium/Telegram ohne Ziel |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | MODIFY | Empfängerzahl aus Kontext-Daten (Preset `empfaenger`) reichen |
| `frontend/src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte` | MODIFY | Anhang „+N Empfänger“ über Katalog |
| `frontend/src/lib/i18n/messages/de/zustellung.json`, `en/zustellung.json` | MODIFY | Schlüssel Empfängerzahl |
| `frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts` | MODIFY | Kürzung, Zustände, Empfänger |
| `frontend/e2e/s3b2795-zustellung-kanaele.spec.ts`, `-englisch.spec.ts`, `-mandanten.spec.ts` | MODIFY | Nutzersicht Trip/Vergleich, DE/EN, zwei Nutzer |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | 23 `#3202` entfernen, Ausnahme Telegram |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY | `"#3202": 0` |

## Estimated Scope

- **LoC:** ca. +90/-40 plus Tests
- **Files:** 10
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `zustellungModell.ts` (`kanalStatus`, `premiumStatus`) | module | Statuslogik, Ort der Kürzung |
| `ZustellungTab.svelte` / `KanalTabelle.svelte` | component | Ein Code für `context="route"\|"vergleich"` |
| `ComparePreset.empfaenger` | Datenfeld | Quelle für „+N Empfänger“ im Orts-Vergleich |
| Katalog `zustellung.json` DE/EN | i18n | Nutzertexte (ADR-0104) |
| `elementliste_besitzer.json`, `elementliste_abgleich_logik.ts` | Prüfdaten | Soll/Ist-Abgleich |
| `feat_2795_s3b_teil1_zustellung.md`, `feat_2913_abgleich_ganzseite.md` | Specs | Bestehende Kanalstatus-ACs, Zustände |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt ADR-0112 (Oberfläche gegen Mockup, Abweichung nur als begründete Ausnahme) um, hält ADR-0104 (Katalog, Adressen/Nummern unübersetzt) und ADR-0095 (alle vier Kanäle gleichrangig, Kürzung benachteiligt keinen) ein. Keine neue Grundsatzentscheidung; die Telegram-Abweichung ist PO-Entscheidung, keine Architekturänderung.

## Implementation Details

Trip und Orts-Vergleich teilen den Code (shared, `context`); keine Pendant-Komponente. Der Kontext liefert nur Daten: `empfaengerZusatz` = Anzahl zusätzlicher Empfänger (Vergleich: `preset.empfaenger` ohne Konto-Adresse; Trip: immer 0).

- `adresseGekuerzt(mail)`: Text vor erstem `@` + `@…`; Lokalteil nie weiter gekürzt (auch kurz, z.B. `a@…`); ohne `@` oder leer: leerer String.
- `nummerGekuerzt(nr)`: Leerzeichen/Trenner entfernen; mit `+`: Landesvorwahl 1 bis 3 Ziffern nach ITU-Tabelle (`+1`, `+7`, `+49`, `+353`), danach erste 3 Ziffern der Rufnummer, dann ` …` (`+49 171 …`); ohne `+`: erste 3 Ziffern + ` …`; leer: leerer String; kürzer als 3 Ziffern: Rest + ` …` ohne Fehler.
- `kanalStatus`: E-Mail `bestätigt · lokalteil@…` plus ` · +N Empfänger` nur bei N>0; SMS `bestätigt|unbestätigt · +49 171 …`; Telegram `verbunden` bzw. `nicht verbunden`, nie Chat-ID; Premium nur Statustext (`inReach · Rückadresse verfallen` im Lückenzustand), ohne Ziel.
- Elementliste: Telegram-Soll `verbunden · @henning` entfällt als Soll zugunsten Ist `verbunden`, eingetragen als `ausnahmen`-Eintrag mit Grund „PO-Entscheidung 20.11.2026: kein Telegram-Name speichern (Datenschutz)“ und `spec` auf diese Datei (Mechanik: `docs/reference/gates_und_ratschen.md`, Abschnitt Ganzseiten-Abgleich). Die übrigen 22 Einträge lösen sich durch den neuen Ist-Text auf und werden gelöscht; Zählwächter `"#3202": 0`.

## Expected Behavior

- **Input:** Profil (`mail_to`, `sms_to`, Verifizierungen, Telegram, Premium) und Kontext-Empfängerzahl.
- **Output:** Statuszeile je Kanal wie im Mockup, Trip und Orts-Vergleich identisch bis auf den Empfängerzusatz.
- **Side effects:** keine; nur Anzeige in der Tabelle, Daten unverändert.

## Test Plan

### Automated Tests (TDD RED)
- [ ] `adresseGekuerzt`: `henning@example.com` ergibt `henning@…`; `a@x.de` ergibt `a@…`; leer und ohne `@` ergibt leer.
- [ ] `nummerGekuerzt`: `+491711234567` ergibt `+49 171 …`; `+14155550123` ergibt `+1 415 …`; `+353871234567` ergibt `+353 871 …`; `0171 1234567` ergibt `017 …`; leer ergibt leer.
- [ ] `kanalStatus`: Premium Normal und stale ohne Rückadresse; Telegram ohne Chat-ID; E-Mail mit N=0 ohne Zusatz, mit N=2 mit Zusatz.
- [ ] E2E: Reiter Zustellung Trip und Orts-Vergleich, Normal und Lücken, DE und EN.
- [ ] Zählwächter `tests/test_2913_c2_besitzerliste.py` mit `"#3202": 0`.

## Acceptance Criteria

- **AC-1:** Given ein Konto mit bestätigter E-Mail `henning@…`, bestätigter Handynummer `+49 171 …` und verbundenem Telegram / When der Nutzer den Reiter Zustellung eines Trips öffnet / Then zeigt die Kanalzeile `bestätigt · henning@…`, `bestätigt · +49 171 …` und `verbunden`, ohne volle Adresse, volle Nummer oder Chat-ID.
  - Test: Nutzersicht im Browser (E2E), Texte der Kanaltabelle auslesen.
- **AC-2:** Given ein Orts-Vergleich mit einem zusätzlichen Empfänger / When der Nutzer den Reiter Zustellung öffnet / Then steht in der E-Mail-Zeile zusätzlich `· +1 Empfänger`, beim Trip erscheint dieser Zusatz nie.
  - Test: E2E Vergleich mit Empfänger gegen Trip ohne Empfängerliste.
- **AC-3:** Given die Kürzungsfunktionen / When sie kurze Lokalteile, Nummern ohne `+`, ausländische Vorwahlen mit 1 bis 3 Ziffern oder leere Werte erhalten / Then liefern sie die festgelegte Kürzung bzw. einen leeren Text, nie einen Fehler und nie den Volltext.
  - Test: Unit-Tests der reinen Funktionen (Grenzfälle).
- **AC-4:** Given der Zustand „Lücken“ (unbestätigte Nummer, verfallene Premium-Rückadresse, Telegram nicht verbunden) / When der Nutzer den Reiter öffnet / Then steht dort `unbestätigt · +49 171 …`, `inReach · Rückadresse verfallen` ohne Rückadresse und `nicht verbunden`.
  - Test: E2E mit umgeschriebener Profilantwort, Kanalzeilen auslesen.
- **AC-5:** Given Premium-SMS im Normalzustand / When der Nutzer den Reiter öffnet / Then zeigt die Premium-Zeile den Status ohne Rückadresse.
  - Test: E2E und Modelltest Premium fresh.
- **AC-6:** Given die Oberfläche in Deutsch bzw. Englisch / When der Nutzer den Reiter in Trip und Orts-Vergleich öffnet / Then erscheinen alle Statustexte und der Empfängerzusatz in der gewählten Sprache aus dem Katalog, Adressen und Nummern bleiben unübersetzt.
  - Test: E2E DE/EN (`s3b2795-zustellung-englisch.spec.ts`).
- **AC-7:** Given Staging mit dem Prüfkonto / When der Ganzseitenvergleich gegen die Elementliste läuft (DE und EN) / Then gibt es für die Kanalzeile keine neue Abweichung, die 23 Einträge `#3202` sind entfallen und allein `@name` bei Telegram steht als begründete Ausnahme.
  - Test: Abgleichslauf `elementliste-abgleich.staging.spec.ts` und Zählwächter mit `"#3202": 0`.
- **AC-8:** Given zwei verschiedene Nutzer mit unterschiedlichen Adressen und Nummern / When jeder den Reiter Zustellung öffnet / Then sieht jeder nur die gekürzten Werte seiner eigenen Daten.
  - Test: E2E `s3b2795-zustellung-mandanten.spec.ts` mit zwei Nutzern.

## Definition of Done

- [ ] Alle Unit- und E2E-Tests aus dem Test Plan grün, Kern-Schicht 100 %.
- [ ] Staging-Ganzseitenvergleich ohne neue Abweichung, Bildprüfung gegen Mockup (ADR-0112).
- [ ] Besitzerliste und Zählwächter im selben Schritt angepasst.
- [ ] Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe der Kürzung.
- [ ] Deploy mit Selftest Exit 0; Issue #3202 geschlossen.

## Known Limitations

- Kürzung nur in der Kanalzeile; Kontosettings zeigen weiterhin Volltext.
- Landesvorwahl-Erkennung ist eine feste Tabelle; unbekannte Vorwahlen fallen auf 3 Ziffern zurück.
- Der Telegram-Name fehlt bewusst (Datenschutz); Abweichung vom Mockup ist begründete Ausnahme.
- Trips haben keine Empfängerliste, daher dort nie „+N Empfänger“.

## Changelog

- 2026-11-21: Initial spec created
