---
entity_id: fix_3283_was_steht_wo_optik
type: bugfix
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
workflow: fix-3283-wsw-optik
tags: [wetter-tab, was-steht-wo, bildpruefung, epic-3122]
---

# Karte „Was steht wo": Optik-Befunde der Bildprüfung (#3283)

## Approval

- [ ] Approved

## Purpose

Die Karte „Was steht wo" (Reiter Wetter) weicht in sieben Punkten vom freigegebenen Soll-Bild Fassung 4 ab (abgeschnittene Beispielwerte, überflüssige Beispiele in Zusatzspalten, fehlende E-Mail-Kürzel, zu frühes „nur Tageswert" bei Telegram, überragendes „Gespeichert", kleine Symbole, klebende Legende). Diese Spec gleicht Karte und Telegram-Ausgabe an Soll-Bild, ADR-0124 Nr. 3 und AC-28 aus feat_3122 an.

## Source

- **File:** `frontend/src/lib/components/molecules/EinstellTabelle.svelte`, `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte`, `src/services/placements_view_service.py`, `src/output/renderers/email/helpers.py`
- **Identifier:** `EinstellTabelle` (Spalten/Zellen), `WasStehtWoKarte` (Legende), `_trip_muster` / `_trip_nur_tageswert` / `_html_stundentabelle` (Placements-Service), `telegram_metric_configs` (Telegram-Auswahl)

> **Schicht-Hinweis:** Frontend (`frontend/src/...`) und Python-Core (`src/services/`, `src/output/renderers/`). Keine Go-API-Änderung.
>
> **Trip/Ortsvergleich-Teilung:** `EinstellTabelle` und `WasStehtWoKarte` sind bereits geteilt (`context="route"|"vergleich"`); Änderungen gelten für beide Kontexte, das ist gewollt. Es entsteht keine neue Komponente mit Pendant.
>
> **Mandantentrennung:** Es werden keine Nutzerdaten bewegt oder geschrieben; der Placements-Endpoint wird nur gelesen (`user_id` aus dem Auth-Kontext). Die Endpoint-Tests laufen dennoch mit zwei verschiedenen Nutzern.
>
> **Kanäle:** Betroffen sind E-Mail (Beispiel mit Kürzel), Telegram (Zählregel, echte Ausgabe), SMS (Fensterwerte in der Karte). Premium-SMS-Inhalt bleibt unverändert.

## Estimated Scope

- **LoC:** ca. +150/-20
- **Files:** ca. 9
- **Effort:** medium (Risiko mittel: echte Telegram-Ausgabe ändert sich bei Trips mit `secondary`-Metriken)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/molecules/EinstellTabelle.svelte` | MODIFY | Spaltenbreiten (B1), kein Beispiel in `schmal`-Spalten (B2), Symbol-Darstellung (B6) |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts` | MODIFY | Kennzeichen „nur Symbol" je Zelle (B6) |
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | MODIFY | Legende als Grid (B7) |
| Token-Datei `--g-size-*` | MODIFY | 150px/118px, falls fehlend (B1) |
| `src/services/placements_view_service.py` | MODIFY | E-Mail-Kürzel (B3), SMS-Beispielfilter (B2) |
| `src/output/renderers/email/helpers.py` | MODIFY | `telegram_metric_configs` setzt `bucket="primary"` (B4) |
| `tests/tdd/test_placements_tabelle_endpoint.py` + neuer Test B4 | MODIFY/CREATE | Endpoint- und Telegram-Nachweise |
| `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts`, EinstellTabelle-Test | MODIFY | Karten-Nachweise B1/B2/B6/B7 |
| `frontend/e2e/was-steht-wo-bildabgleich.staging.spec.ts` | CREATE | Screenshots 3 Kontexte × DE/EN, SaveIndicator ausgeblendet (B5) |

**Nicht im Scope**
- Doppeltes Kürzel „L" in der Legende (#3284).
- Globales Verhalten des SaveIndicator.
- Weitere Mockup-Abweichungen außerhalb der sieben Befunde.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_3122_was_steht_wo.md` | spec | Teil B Nr. 11, AC-21, AC-28, AC-33 (Soll) |
| `docs/adr/0124-was-steht-wo-eine-tabelle.md` | ADR | Nr. 3: Telegram-Zählregel „ab der achten Metrik" |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` + `bilder-fassung4/` | Soll-Bild | Maße, Zellaufbau, Legende |
| `src/services/placements_beispiel.py` | module | `VERSION` der Beispielwerte |
| `src/output/renderers/channel_layout.py` | module | Telegram-Spaltenwahl (`bucket=="primary"`) |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts` | module | `zelleAus`: Kennzeichen „nur Symbol" |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | component | globales Etikett, im Prüfaufbau ausgeblendet |
| `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts` | test-vorlage | Vorlage für Screenshot-Spec |
| `.claude/agents/mockup-bildpruefer.md` | agent | Bildvergleich Soll/Ist |
| Token-Datei (`--g-size-*`) | design-tokens | Spaltenbreiten 150px / 118px |

## Implementation Details

Entscheidungen B1 bis B7 sind vom Tech Lead getroffen (Kontext: `docs/context/fix-3283-wsw-optik.md`).

- **B1 Spaltenbreiten:** Kanalspalten `minmax(150px,1fr)`, Zusatzspalten 118px, nur über Tokens (`--g-size-*`, bei Bedarf neu anlegen). Kein Beispielwert wird mehr mit „…" abgeschnitten.
- **B2 Zusatzspalten und SMS-Fenster:** Spalten mit `schmal` (Stundenverlauf, Ausblick) zeigen nur Haken und Roh/Einfach, kein Beispiel (Frontend unterdrückt `et-beispiel`; der Endpoint liefert `example` weiter, Datenwahrheit bleibt). In der SMS-Spalte erhalten nur Metriken mit eigenem SMS-Token ein Beispiel; abgeleitete Fenster-Kinder (`temperature_day_low/high`, `wind_chill_*`) bleiben ohne Beispiel, Ausnahme `temperature_night` (`N10`). Der Filter wirkt nur im Beispiel-Dict (`_trip_muster` „sms"), nicht in `sms_werte`, damit `_trip_sms_fehlt` intakt bleibt.
- **B3 E-Mail-Kürzel:** Trip-E-Mail-Beispiel trägt das Spaltenkürzel davor (`Temp 14.4`), nur wenn der Wert Buchstaben oder Ziffern enthält; reine Symbole ohne Präfix. Kürzel = `col_label` (sprachunabhängig). Orte-Kontext unverändert.
- **B4 Telegram-Zählregel:** Ursache ist der Altwert `bucket`; `telegram_metric_configs` erbt ihn aus der alten Grundauswahl, der Renderer nimmt nur `bucket=="primary"`. Gewitter und Gefühlte Temperatur mit `secondary` bekamen daher keine Spalte. Fix: `telegram_metric_configs` setzt `bucket="primary"`. Danach folgen Telegram-Nachricht und Karte beide der Zählregel „ab der achten Metrik" (eine Reihenfolge für alle Stellen, ADR-0124 Nr. 3). Telegram-Renderer- und Golden-Tests werden mitgeprüft.
- **B5 SaveIndicator:** Komponente bleibt unverändert (global, `position:fixed`). Der Prüfaufbau (Screenshot-Spec) blendet ihn aus; kein Befund an der Karte selbst.
- **B6 Symbol-Beispiele:** Reine Symbole (kein Buchstabe/Ziffer) in `--g-text-sm` und Farbe `ink` statt `ink-2` (Kontrast AA); Kennzeichen kommt aus `wasStehtWoAnsicht.ts`.
- **B7 Legende:** Grid `auto 1fr`, Abstand 4px/14px, `dt` Mono, Gewicht normal, ohne `min-width`.
- **Prüfaufbau:** neue Spec `frontend/e2e/was-steht-wo-bildabgleich.staging.spec.ts` (Trip, drei Orte, ein Ort, je DE und EN), danach `mockup-bildpruefer` gegen die Mockup-PNG.

Geplante Tests (kein Mock-Theater, echte Berechnung, echter Endpoint, gerenderte Karte):

- Backend `tests/tdd/test_placements_tabelle_endpoint.py` (Anpassung AC-16: Ausnahme Fenster-Kinder; neu: B3, B4), `tests/tdd/` Telegram-Ausgabe für B4.
- Frontend `organisms/__tests__/was_steht_wo_karte.test.ts` und EinstellTabelle-Test (`node:test`).

## Expected Behavior

- **Input:** Reiter Wetter eines Trips, eines Abos mit drei Orten, eines mit einem Ort (DE/EN); Telegram-Versand eines Trips.
- **Output:** Karte ohne Abschneidungen, ohne Beispiele in Zusatzspalten, E-Mail-Beispiele mit Kürzel, Telegram-Spalten und Karte nach gleicher Zählregel, lesbare Symbole, saubere Legende.
- **Side effects:** Echte Telegram-Ausgabe zeigt künftig Metriken mit altem `secondary`-Wert an Position unter 8; `VERSION` der Beispielwerte wird erhöht, falls sich Beispiele ändern.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Endpoint (zwei Nutzer): Trip-E-Mail-Beispiel `temperature` beginnt mit `Temp `, reines Symbol ohne Präfix; Orte-E-Mail unverändert (AC-4).
- [ ] Endpoint: SMS-Beispiel fehlt für `temperature_day_low/high`, `wind_chill_*`; `temperature_night` zeigt `N…`; „passt nicht mehr“ unverändert (AC-3).
- [ ] Endpoint: Ausblick/Stundenverlauf liefern weiter `example` (AC-2, Datenwahrheit).
- [ ] Echte Telegram-Ausgabe: Trip mit Gewitter/Gefühlter Temperatur (Altwert `secondary`) an Position < 8 hat die Spalte; Karte meldet für sie kein „nur Tageswert“; Grenze ab der achten Metrik (AC-5, AC-6).
- [ ] Karte gerendert (node --test): Zusatzspalten ohne Beispieltext, Rasterbreiten 150/118 über Tokens, Symbol-Klasse, Legende Grid ohne Fett (AC-1, AC-2, AC-8, AC-9).
- [ ] Staging: Screenshot-Spec 3 Kontexte × DE/EN + `mockup-bildpruefer`; `elementliste:abgleich --scope wetter --strict` DE und EN (AC-7, AC-10, AC-11).

## Acceptance Criteria

- **AC-1:** Given der Reiter Wetter eines Trips mit Beispielwerten wie „61 %", „Wolken 40 %" und „freundlich" / When die Karte „Was steht wo" in Deutsch und Englisch gerendert wird / Then steht jeder Beispielwert in den Kanalspalten vollständig da, ohne „…" am Ende, die Kanalspalten sind mindestens 150 Pixel und die Zusatzspalten 118 Pixel breit. (Befund 1, Abschneidung)
  - Test: Frontend-Test an der gerenderten Karte (Spaltenbreite per Token, kein abgeschnittener Text) und Screenshot der Bildprüfung.

- **AC-2:** Given ein Trip mit Stundenverlauf und Ausblick / When die Karte angezeigt wird / Then zeigen diese Zusatzspalten nur Haken und Roh/Einfach, aber keinen Beispielwert; die Placements-Antwort liefert `example` weiterhin. (Befund 2, Zusatzspalten)
  - Test: Frontend-Test an der gerenderten Karte; Endpoint-Test mit zwei verschiedenen Nutzern, dass `example` in der Antwort bleibt.

- **AC-3:** Given ein Trip mit Tagestemperatur-Fenster (`D14/18`) und Windchill-Fenster (`FN12`) / When die SMS-Spalte der Karte angezeigt wird / Then steht dort bei diesen abgeleiteten Fenster-Metriken kein Beispiel, bei der Nachttemperatur aber `N10`, und der Hinweis „fehlt in der SMS" bleibt korrekt. (Befund 2, SMS-Fenster)
  - Test: Endpoint-Test gegen die echte Berechnung mit zwei Nutzern, prüft Beispiel-Dict und unveränderte `sms_werte`.

- **AC-4:** Given ein Trip mit Temperatur- und Böen-Spalte in der E-Mail / When die E-Mail-Beispielzelle in der Karte angezeigt wird / Then lautet sie `Temp 14.4` bzw. `Gust …` (Kürzel vor dem Wert), bei reinen Symbolen ohne Kürzel, und im Orte-Kontext bleibt die Zelle unverändert. (Befund 3, E-Mail-Kürzel)
  - Test: Endpoint-Test mit echter Beispielberechnung für Trip und Vergleich, zwei Nutzer; Kürzel in DE und EN gleich.

- **AC-5:** Given ein Trip, in dem Gewitter und Gefühlte Temperatur an Position kleiner 8 stehen und früher im alten Feld `bucket` als `secondary` geführt wurden / When die echte Telegram-Nachricht für diesen Trip gebaut wird / Then hat sie für Gewitter und Gefühlte Temperatur eine Spalte, und die Karte markiert genau die Metriken ab der achten Position mit „nur Tageswert", Nachricht und Karte stimmen überein. (Befund 4, Telegram-Zählregel)
  - Test: Test der echten Telegram-Ausgabe (Renderer mit realen Konfigurationen) plus Endpoint-Test derselben Konfiguration; die bestehenden Telegram-Renderer- und Golden-Tests bleiben grün.

- **AC-6:** Given ein Trip mit mehr als sieben Telegram-Metriken / When Karte und Telegram-Nachricht verglichen werden / Then fehlt die achte und jede weitere Metrik in der Nachricht, und die Karte zeigt für genau diese „nur Tageswert". (Befund 4, Grenze)
  - Test: Test der echten Telegram-Ausgabe gegen den Endpoint mit acht und neun Metriken.

- **AC-7:** Given der Prüfaufbau für die Bildprüfung / When die Karte als Element fotografiert wird / Then ragt kein „Gespeichert"-Etikett über den Kartenrand, weil der Prüfaufbau den SaveIndicator ausblendet; im normalen Betrieb bleibt das Etikett unverändert sichtbar. (Befund 5, Gespeichert-Etikett)
  - Test: Screenshot der Bildprüfung ohne Etikett; Browser-Test, dass der SaveIndicator außerhalb des Prüfaufbaus weiterhin erscheint.

- **AC-8:** Given ein Einfach-Symbol als E-Mail-Beispiel (kein Buchstabe, keine Ziffer) / When die Karte gerendert wird / Then ist das Symbol in der Textgröße `sm` und in der Farbe `ink` dargestellt und erfüllt den Kontrast nach WCAG AA. (Befund 6, Symbole)
  - Test: Frontend-Test an der gerenderten Karte (Klasse, berechnete Größe/Farbe) und Kontrastprüfung.

- **AC-9:** Given die Legende der Karte mit langen Kürzeln / When sie in Deutsch und Englisch angezeigt wird / Then stehen Kürzel und Erklärung in zwei Spalten mit 14 Pixel Abstand, die Kürzel in Monoschrift ohne Fettdruck, und kein Kürzel klebt an seinem Text. (Befund 7, Legende)
  - Test: Frontend-Test an der gerenderten Legende (Grid, Gewicht, Abstand) und Bildprüfung.

- **AC-10:** Given Staging mit einem Trip, einem Abo mit drei Orten und einem mit einem Ort / When die Karte in allen drei Kontexten, je Deutsch und Englisch (sechs Aufnahmen, SaveIndicator im Prüfaufbau ausgeblendet), vom `mockup-bildpruefer` gegen das Soll-Bild Fassung 4 verglichen wird / Then meldet er keinen offenen Befund zu den sieben Punkten (Abschlussbedingung laut PO 23.11.2026; bleibt nach zwei Runden ein Befund, ist das Issue nicht fertig). (Bildprüfung)
  - Test: `frontend/e2e/was-steht-wo-bildabgleich.staging.spec.ts` erzeugt die sechs Aufnahmen; Prüfer-Agent mit Mockup- und Staging-Bild.

- **AC-11:** Given die geänderte Karte auf Staging / When `npm run elementliste:abgleich -- --scope wetter --strict` in Deutsch und mit `--sprache en` läuft / Then enden beide Läufe grün (Exit 0), ohne neue Abweichung im Abschnitt `was-steht-wo`. (Text-Abgleich)
  - Test: beide Abgleich-Läufe mit Prüfkonto-Login und Seed-IDs.

## Definition of Done

- [ ] Spec freigegeben, Tests rot vor Umsetzung, dann grün
- [ ] Alle sieben Befunde umgesetzt (B1–B7)
- [ ] Mutationsprobe: je Befund rötet eine Verfälschung mindestens einen Test
- [ ] Telegram-Renderer- und Golden-Tests grün
- [ ] Bildprüfung Trip/drei Orte/ein Ort × DE/EN ohne offenen Befund, Text-Abgleich `--strict` DE und EN grün, Ergebnisse als Artefakt
- [ ] PR mit allen 6 CI-Checks grün, Deploy, Selftest

## Known Limitations

- Der alte `bucket`-Wert bleibt im Datenmodell; er wird nur für Telegram nicht mehr ausgewertet (Altbegriff, im neuen Editor nicht bedienbar).
- Der SaveIndicator wird nicht umgebaut; er ist global und kein Karteninhalt. **PO-Entscheidung 23.11.2026:** „So lassen“ — kurze Bestätigung am Fensterrand darf kurz über dem Inhalt liegen; nur der Prüfaufbau blendet sie aus.
- Der Befund „Kürzel L doppelt" gehört zu #3284.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (setzt ADR-0124 Nr. 3 um)
- **Rationale:** Die Zählregel „ab der achten Metrik" ist bereits entschieden; diese Spec gleicht Telegram-Ausgabe und Karte an, ohne eine Entscheidung zu ändern.

## Changelog

- 2026-11-23: Initial spec created
