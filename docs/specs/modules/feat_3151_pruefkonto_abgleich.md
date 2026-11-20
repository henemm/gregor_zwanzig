---
entity_id: feat_3151_pruefkonto_abgleich
type: feature
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
tags: [einstellungen-neu, elementliste, abgleich, staging, seed, kanalauswahl, epic-2913, issue-3151]
workflow: feat-3151-pruefkonto-abgleich
---

# Prüfkonto-Seed Kanalauswahl und Abgleich: 247 `#2967`-Einträge auflösen

## Approval

- [ ] Approved

## Purpose

Der Staging-Seed des Prüfkontos (#2967) kennt die Kanalauswahl des Mockups nicht: Trip und Vergleich haben live nur E-Mail als Briefing- und Alarmkanal. Diese Spec erweitert den Seed um Briefing-Kanäle, Alarm-Kanäle und Alarm-Schwellen laut Mockup, lässt danach den Abgleich DE+EN neu laufen und löst die 247 Besitzer-Einträge mit Verweis `#2967` auf (entfernen oder auf Kind-Issues von Epic #2913 umhängen).

## Source

- **File:** `scripts/staging_pruefkonto_mockupdaten.py` (Soll-Funktionen `soll_trip`, `soll_vergleich`, Sicherung `sichere_datensatz`, `sichere_vergleich`)
- **Identifier:** neue reine Funktionen `soll_kanalauswahl_trip()`, `soll_kanalauswahl_vergleich()` und Konstanten für Schwellen
- **Schicht:** Prüfwerkzeug (`scripts/`, `tests/`), Daten (`docs/context/einstellungen_neu/elementliste_besitzer.json`), Runbook. Kein Go-, Python-Core- oder Frontend-Produktcode; die Go-API kann Felder und Merge bereits.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orts-Vergleich-Teilung:** n/a, kein UI-Baustein; der Seed füllt beide Kontexte mit Daten.
> - **Mandantentrennung:** Schreibzugriffe nur mit der Anmeldung des Prüfkontos `u-89f9fe2f` (`GZ_PRUEFKONTO_*`), nur auf die eigenen festen Datensätze; nie `"default"`, nie `GZ_AUTH_*`. Test mit zwei Nutzern (AC-4).
> - **Kanäle:** Alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) werden gesetzt, ausschließlich mit Testzielen (AC-5).

## Estimated Scope

- **LoC:** ca. +230 (Seed ~40, Tests ~120, Zählwächter ~15, Runbook ~15, Besitzerliste per Skript mechanisch)
- **Files:** 5
- **Effort:** medium (Aufwand im Staging-Lauf und in der Neuklassifizierung, Risiko niedrig bis mittel: nur Staging-Testkonto)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| scripts/staging_pruefkonto_mockupdaten.py | MODIFY | Reine Soll-Funktionen Kanalauswahl Trip/Vergleich, Schwellen-Konstanten; nur Soll-Teilobjekte senden, feldweiser Merge für `report_config`, `alert_channels`, `alert_channel_thresholds` |
| tests/tdd/test_staging_pruefkonto_mockupdaten.py | MODIFY | Fake-Server bildet Go-Merge je Kanal und `alert_channels`-Ableitung des Vergleichs nach; Tests AC-1 bis AC-4 |
| docs/context/einstellungen_neu/elementliste_besitzer.json | MODIFY | 247 `#2967`-Einträge nach Neuklassifizierung entfernen bzw. umhängen (per Skript) |
| tests/test_2913_c2_besitzerliste.py | MODIFY | Zählwächter `soll`: `#2967` auf 0, Zähler der neuen Verweise, Historie-Kommentar |
| docs/runbooks/staging_pruefkonto_seed.md | MODIFY | Kanalauswahl-Soll, Abgleich DE+EN, Hinweis auf Klassifizierungs-Nachweis |

### Nicht-Ziele

- Keine Änderung an Go-API, Python-Core, Frontend oder Katalog-Vorlagen; echte Abweichungen werden nicht im Seed kaschiert.
- Kein Verbiegen des Trip-Datums. Der Abgleich selbst schreibt weiterhin nicht (außer dem bekannten, zurückgestellten Testdatensatz „E2E-GZ #2966“).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md` | Spec | Seed-Grundlage; AC-8/AC-9 dort an #3151 abgetreten |
| `mockup-hub-fassung4.html` Z.373-374 | Quelle | Soll `st[ctx].sw.ch` (b = Briefing, a = Alarm, s = Dringlichkeit) |
| `internal/handler/trip.go:437-535` | Betrieb | Go-Merge `report_config` je Schlüssel, `alert_channels`/`alert_channel_thresholds` je Kanal; keine Schwellen-Wertprüfung |
| `internal/store/trip.go:108-121`, `internal/store/compare_preset.go:55-71` | Betrieb | Ableitung Flachfelder (Trip) bzw. `alert_channels` aus Flags (Vergleich) |
| `src/services/alert_urgency.py` | Quelle | Schwellenwerte `LOW`/`MODERATE`/`HIGH` |
| Staging-`.env` (`GZ_PRUEFKONTO_*`, Core-Secret, `GZ_SEVEN_SANDBOX_KEY`), Loopback 8091 | Betrieb | Seed- und Abgleich-Lauf auf dem Staging-Host |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts`, `scripts/elementliste_abgleich.ts` | Werkzeug | Abgleich DE+EN, Berichte unter `ELEMENTLISTE_BERICHT_DIR` |
| Issues #2799, #2867, #3122, #3194, #3086, #2955 | Ziel/Prüfung | Umhängen und Dublettenprüfung; #2967, #3145 geschlossen |
| Epic #2913 | Epic | Neue Kind-Issues als Sub-Issues; Epic bleibt offen |

## Implementation Details

1. **Soll Trip** (nur diese Schlüssel senden): `report_config {send_email: true, send_telegram: true, send_sms: false, send_premium_sms: false}`, `alert_channels` alle vier `true`, `alert_channel_thresholds {email: LOW, telegram: LOW, sms: MODERATE, premium_sms: HIGH}`. Mockup „gering/mittel/hoch“ entspricht `LOW/MODERATE/HIGH`. Flachfelder am Trip leitet der Store ab; der Seed schreibt sie nicht.
2. **Soll Vergleich:** top-level `send_email/send_telegram: true`, `send_sms/send_premium_sms: false`, `alert_channels` EXPLIZIT alle `true` (sonst materialisiert der Store es aus den Flags), `alert_channel_thresholds` wie beim Trip. `sichere_vergleich` merkt die Unterobjekte feldweise (Ist laden, nur Soll-Kanäle überschreiben), wie bei `display_config`.
3. **Merge:** Statt `{**ist, **soll}` auf oberster Ebene wird bei den drei Unterobjekten jeder Kanalschlüssel einzeln verglichen und nur bei Abweichung geschrieben; Fremdfelder und fremde Kanalschlüssel bleiben (CLAUDE.md Daten-Schema-Regel).
4. **Idempotenz:** `_enthaelt` vergleicht die Unterobjekte in der Form, wie Go sie zurückgibt; der Fake bildet Ableitung und Normalisierung nach (Muster `test_ac4_f001_…`). Zweiter Lauf: kein Daten-Schreibzugriff, nur der bekannte `staging-seed`-Aufruf (Tarif/Zähler).
5. **Kein echter Versand:** Staging nutzt SMS-Sandbox (`src/app/config.py:222-224`) und Telegram-Test-Bot (`config.py:255-258`); Ziele sind fiktiv (SMS-Nummer, Chat-ID, inReach-Absender, Zweitempfänger `.invalid`), E-Mail nur an das Test-Postfach. Der Trip liegt in der Vergangenheit. Wird der Staging-Weg für den Vergleich (`schedule: daily`) in der Prüfung nicht belegt, setzt der Seed den Vergleich auf `schedule: manual` (Soll-Funktion + Test).
6. **Staging-Lauf (nach Merge/Deploy):** Seed zweimal (stellt fehlenden GR221-Trip, Münsterland und Orte wieder her), dann Abgleich DE und EN (je ca. 8 Min.), nicht parallel zu anderen Läufen mit demselben Konto.
7. **Neuklassifizierung:** Aus den frischen Berichten wird jeder der 247 `#2967`-Einträge neu eingeordnet (aufgelöst / echte Abweichung / Umhängen); die Zahlen vom 19.11. (119/53/62/15) sind nur Orientierung. Aufgelöste entfernt ein Skript (Vorher-Datei als Nachweis). Umhängen: B5 auf #2799/#2867, „gesperrt: {grund}“ auf #3122, EN-Reste auf #3194, übrige bestätigte Abweichungen auf neue Kind-Issues von Epic #2913 nach Dublettenprüfung (Kanalzeile, Grünbereich, Gewitter-Stufen mit Prüfung #2955, Anzeige-Metriken Trip, alpen-trekking Skala/Zurücksetzen, Kleinkram); das Mockup ist Soll. Abschnitts-Einträge `wetter/metriken` werden aufgeteilt. Die Klassifizierung je Klasse (Anzahl, Ziel) steht als Kommentar in #3151.
8. **Zählwächter:** `soll` in `tests/test_2913_c2_besitzerliste.py`: `#2967` auf 0, neue und erhöhte Verweise ergänzt, Summe konsistent.
9. **GitHub-Texte:** Telegram- und Mockup-Namen immer in Backticks, nie als bares At-Handle.

## Expected Behavior

- **Input:** Aufruf des Seeds auf dem Staging-Host mit Prüfkonto-Zugang; danach Abgleich DE+EN.
- **Output:** Trip und Vergleich zeigen Briefing E-Mail+Telegram, Alarme alle vier Kanäle mit Schwellen LOW/LOW/MODERATE/HIGH; `elementliste_besitzer.json` enthält keinen `#2967`-Eintrag mehr.
- **Side effects:** Schreibzugriffe nur auf eigene Seed-Datensätze des Prüfkontos; kein Versand an echte Geräte oder Adressen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] GIVEN leerer Fake-Server WHEN Seed läuft THEN Trip und Vergleich tragen Kanalauswahl, Alarm-Kanäle und Schwellen laut Mockup (AC-1).
- [ ] GIVEN Soll-Funktionen WHEN aufgerufen THEN exakte Werte und Schwellen-Konstanten, ohne Netz (AC-1).
- [ ] GIVEN Trip/Vergleich mit Fremdfeldern und fremdem Kanalschlüssel WHEN Seed läuft THEN Fremdes bleibt, nur Soll-Teilobjekte geändert (AC-2).
- [ ] GIVEN Seed lief WHEN zweiter Lauf (Fake mit Go-Normalisierung und Ableitung `alert_channels`) THEN keine Daten-Schreibaufrufe, Zustand identisch (AC-3).
- [ ] GIVEN zwei Nutzer im Fake WHEN Seed als Prüfkonto läuft THEN zweiter Nutzer byte-gleich, nichts unter `default` (AC-4).
- [ ] GIVEN Seed-Soll WHEN Kanalziele geprüft THEN nur fiktive Ziele, Vergleich je Beleg `manual` bzw. Sandbox (AC-5).
- [ ] GIVEN Besitzerliste und Zählwächter WHEN Wächter läuft THEN `#2967` = 0, Summe konsistent, kein Eintrag an `#2967`/`#3145` (AC-7).

### Live-Lauf (E2E-Phase, nur Staging)

- [ ] Seed zweimal Exit 0, Lauf 2 schreibfrei; Abgleich DE und EN Exit 0, Schreib-Tripwire 0 (AC-6).

## Acceptance Criteria

- **AC-1:** Given der Seed-Code / When die Soll-Funktionen für Trip und Vergleich ausgewertet werden und der Seed gegen den Fake-Server läuft / Then stehen am Trip `report_config` mit `send_email`/`send_telegram` true und `send_sms`/`send_premium_sms` false, `alert_channels` alle vier true und Schwellen email/telegram `LOW`, sms `MODERATE`, premium_sms `HIGH`, und am Vergleich dieselben Werte als `send_*`, explizites `alert_channels` und `alert_channel_thresholds` (Mockup Z.373-374).
  - Test: Unit-Test der reinen Soll-Funktionen auf exakte Werte und Schwellen-Konstanten plus Kern-Test, der den Fake-Zustand nach dem Lauf liest.

- **AC-2:** Given Trip und Vergleich haben im Konto Fremdfelder und einen weiteren Kanalschlüssel mit eigenem Wert / When der Seed läuft / Then werden nur die Soll-Teilobjekte der Kanalauswahl gesendet und gemerged, alle Fremdfelder bleiben erhalten (Read-Modify-Write, nie Replace).
  - Test: Kern-Test legt Fremdfelder vorab im Fake ab und vergleicht Zustand und gesendete Bodies nach dem Lauf.

- **AC-3:** Given der Seed ist einmal gelaufen und Go normalisiert bzw. leitet `alert_channels` ab (im Fake nachgebildet) / When er ein zweites Mal läuft / Then erfolgt kein Daten-Schreibzugriff auf Trip und Vergleich, der Zustand ist byte-gleich und der Exit-Code 0.
  - Test: Kern-Test zählt Schreibaufrufe im zweiten Lauf (0 außer `staging-seed`) und vergleicht den Fake-Zustand.

- **AC-4:** Given zwei Nutzer mit eigenen Trips und Vergleichen im Fake-Server / When der Seed als Prüfkonto läuft / Then ändert er nur dessen Datensätze, der zweite Nutzer bleibt mit allen neuen Feldern unverändert.
  - Test: Kern-Test vergleicht den Bestand des zweiten Nutzers vorher/nachher.

- **AC-5:** Given der Seed setzt Alarm-Kanäle auf alle vier und der Vergleich läuft täglich / When der Staging-Scheduler läuft / Then geht nichts an echte Geräte oder Adressen: SMS über die Sandbox, Telegram über den Test-Bot, Ziele fiktiv oder im Test-Postfach; ist das nicht belegbar, steht der Vergleich auf `schedule: manual`.
  - Test: Kern-Test prüft, dass alle Seed-Ziele fiktiv sind und der Vergleich bei fehlendem Beleg auf `manual` steht; Belegquellen (`config.py`) stehen im Runbook.

- **AC-6:** Given der Seed ist auf Staging deployt / When er zweimal läuft und danach der Abgleich DE und EN / Then enden alle Läufe mit Exit 0, Lauf 2 des Seeds schreibt nichts, fehlender GR221-Trip, Münsterland und Orte sind wiederhergestellt und der Schreib-Tripwire des Abgleichs meldet 0.
  - Test: Live-Lauf gegen Staging (E2E-Phase), Exit-Codes und Tripwire im Bericht.

- **AC-7:** Given die frischen Abgleich-Berichte / When die 247 `#2967`-Einträge neu klassifiziert werden / Then sind aufgelöste Einträge entfernt, bestätigte Abweichungen auf #2799/#2867, #3122, #3194 oder neue Kind-Issues von Epic #2913 umgehängt, es bleibt kein Eintrag an `#2967` oder `#3145`, die Klassifizierung je Klasse steht als Kommentar in #3151 und der Zählwächter stimmt inklusive der neuen Verweise.
  - Test: `tests/test_2913_c2_besitzerliste.py` (benannte Datei) prüft Zählung je Verweis und Gesamtsumme; Kommentar-Inhalt per Sichtprüfung im Issue.

- **AC-8:** Given Issue-Kommentare und Issue-Texte dieser Arbeit / When sie veröffentlicht werden / Then enthalten sie kein bares At-Handle; Telegram- und Mockup-Namen stehen in Backticks.
  - Test: Prüfung der erzeugten Texte vor dem Absenden per Muster auf `@`-Namen außerhalb von Backticks.

## Definition of Done

- Alle Kern-Tests (AC-1 bis AC-5, AC-7, AC-8) grün; Seed-Tests und Besitzerlisten-Wächter mit benannten Dateien.
- Seed zweimal auf Staging Exit 0 (Lauf 2 schreibfrei), Abgleich DE+EN Exit 0, Tripwire 0.
- `#2967`-Einträge in der Besitzerliste: 0; Kind-Issues angelegt; Klassifizierung als Kommentar in #3151; Runbook aktualisiert.
- Epic #2913 bleibt offen; PR-Text „Refs #3151“.

## Known Limitations

- Die Zahlen der Klassifizierung vom 19.11. sind veraltet (vor #2968/#3192); verbindlich ist der Neulauf.
- Ob B3/B7 (alpen-trekking weicht vom Mockup ab) als Kind-Issue oder Ausnahme geführt werden, entscheidet der Tech Lead nach der Known-Limitation-Regel der Spec #2967: Kind-Issue.
- Die Reihenfolge der Metrik-Gruppen und Katalog-Vorlagen werden nicht im Seed geändert.
- Das Skript läuft nur auf dem Staging-Host; Rohdaten der Klassifizierung vom 19.11. liegen nur gitignored in einem fremden Worktree.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Prüfwerkzeug und Datenpflege für Staging; keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor) wird verändert, bestehende Felder und der Go-Merge werden unverändert genutzt.

## Changelog

- 2026-11-20: Initial spec created
