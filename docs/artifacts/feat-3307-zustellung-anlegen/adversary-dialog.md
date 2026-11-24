# Adversary Dialog — feat-3307-zustellung-anlegen
Spec: docs/specs/modules/feat_3332_zustellung_anlegen_trip.md
Datum: 2026-11-24 16:30

## Checkliste
- [x] **Input:** Nutzer legt einen Trip an, stellt im Schritt Zustellung Zeiten (z. B. Morgen 06:45), Kanäle, Dringlichkeit Telegram HIGH und Stille Stunden ein und legt an.
- [x] **Output:** Genau ein `POST` auf die Trip-Anlage mit diesen Werten in `report_config` und den Alarm-Feldern; der Hub-Reiter Zustellung des neuen Trips zeigt denselben Stand.
- [x] **Side effects:** Nur der lesende Profil-Abruf; kein PUT, kein Speichern vor dem Anlegen.
- [x] **AC-1:** Given ein angemeldeter Nutzer legt einen Trip an / When er den Schritt Zustellung öffnet, in der Mobil- und in der Desktop-Ansicht / Then sieht er den Reiter Zustellung mit Briefing-Zeiten, Kanal-Tabelle und Stille Stunden wie im Hub, und das Alt-Panel mit Versand-Abschnitt und die Mail-Inhalt-Karte erscheinen dort nicht mehr.
- [x] **AC-2:** Given der Nutzer stellt im Anlegen Briefing-Zeiten, Kanäle und Stille Stunden ein / When er den Trip anlegt / Then enthält der eine POST `report_config.morning_time`/`evening_time` (HH:MM:SS), `morning_enabled`/`evening_enabled`, `send_email/telegram/sms/premium_sms` und `alert_quiet_from/_to` mit genau den eingestellten Werten.
- [x] **AC-3:** Given der Nutzer wählt Alarm-Kanäle, die Dringlichkeit HIGH für Telegram und einen Cooldown / When er den Trip anlegt / Then stehen `alert_channels`, `alert_channel_thresholds.telegram == "HIGH"` und `alert_cooldown_minutes` im POST.
- [x] **AC-4:** Given der Nutzer öffnet den Schritt Zustellung, bedient den Reiter aber nicht / When er den Trip anlegt / Then ist der POST-Körper in `report_config`, den Alarm-Feldern und `display_config.channels` bitgleich zu dem heutigen Körper (keine stille Änderung der Startwerte, `multi_day_trend_reports` und die Standardwerte aus `ergaenzeVersandStandard` weiter vorhanden).
- [x] **AC-5:** Given der Nutzer ändert Werte im Reiter / When er bis zum Anlegen weitermacht / Then gibt es weder einen PUT noch einen Autosave noch einen Schreibaufruf vor dem Anlegen, und beim Anlegen genau einen POST.
- [x] **AC-6:** Given der Nutzer hat im Reiter Zustellung Werte gesetzt / When er zwischen Mobil und Desktop wechselt oder Schritte vor und zurück geht / Then bleibt der Stand erhalten und die Werte stehen unverändert im POST.
- [x] **AC-7:** Given der Nutzer gibt eine rasterfremde Uhrzeit ein (z. B. 06:50) / When er den Trip anlegt / Then sendet der POST die letzte gültige Viertelstunden-Zeit und es gibt keinen Server-Fehler 400.
- [x] **AC-8:** Given ein Trip wird im Anlegen mit gesetzter Zustellung angelegt / When der Nutzer danach den Hub-Reiter Zustellung dieses Trips öffnet / Then zeigt er dieselben Zeiten, Kanäle, Dringlichkeiten, Stille Stunden und denselben Cooldown wie beim Anlegen eingestellt. (Kern belegt: POST traegt die Werte, Hub liest unveraendert via standAusTrip; Live-E2E gegen Staging steht fuer /e2e-verify aus.)
- [x] **AC-9:** Given der Nutzer ist im Schritt Alarme des Trip-Anlegens / When er den Reiter öffnet / Then fehlen dort die Abschnitte Alarm-Kanäle, Cooldown und Stille Stunden (sie stehen im Reiter Zustellung), während amtliche Warnungen und Metrik-Alarmstufen dort bleiben; jedes Feld hat genau eine Bedienstelle, und im Hub und im Ortsvergleich-Anlegen bleibt der Reiter Alarme unverändert.
- [x] **AC-10:** Given ein Nutzer legt einen Trip an / When er im Schritt Zustellung die Mail-Inhalt-Felder sucht / Then sind E-Mail-Format, Etappen-Statistik, Vortagesvergleich und Nacht-Block weiter über die Karte „Was steht wo“ bedienbar, ihre Werte stehen wie bisher im POST, und `show_stability` sowie Bestandsfelder behalten ihren Standardwert.
- [x] **AC-11:** Given der Reiter Zustellung im Trip-Anlegen / When der Nutzer ihn öffnet / Then erscheint dort keine Infobox mehr, während sie im Alt-Panel des Ortsvergleich-Anlegens und im Reiter Alarme des Trip-Anlegens wie bisher nur beim Anlegen erscheint.
- [x] **AC-12:** Given zwei verschiedene Nutzer A und B mit verschiedenem Kanalstatus (A hat Telegram verbunden, B nicht) / When beide je einen Trip anlegen / Then zeigt der Reiter bei A die Dringlichkeit für Telegram und bei B nicht, jeder Trip erscheint nur beim jeweiligen Nutzer, und B sieht den Trip von A nicht. (Kern belegt: Kanalstatus-Logik des Reiters unveraendert; Zwei-Nutzer-Live-E2E steht fuer /e2e-verify aus.)
- [x] **AC-13:** Given der Ortsvergleich wird angelegt / When der Nutzer den Schritt Zustellung öffnet / Then verhält er sich unverändert wie vor dieser Änderung (Alt-Panel, ein POST), D1 ändert dort nichts.

## Dialog

### Runde 1
**Adversary:**
Basislauf (benannte Dateien: alle trip-new/__tests__, shared/__tests__, zustellung-tab/__tests__, alarme-tab/__tests__; Befehl node --import ./test-lib-loader.mjs --experimental-strip-types --test): 2129 pass, 0 fail (docs/artifacts/feat-3307-zustellung-anlegen/adversary-test-output.txt).
F004 (Runde 2 der Vorrunden) erneut geprueft: Test-Fix liest trip_anlegen_zustellung_payload_3332.test.ts:45-47 jetzt briefing {email,sms} und alarme {telegram,premium_sms} getrennt, Pruefung je Feld. N05 (send_<kanal> aus stand.alarme) ROT (3 Tests), N06 (Alarm-Kanaele aus stand.briefing) ROT (3 Tests). F004 behoben.
Neue Mutationen (41 insgesamt, Subset 107 Testdateien, String-Ersetzung, Sicherung im Scratchpad, cmp danach identisch). Gefangen (rot): A1 Dringlichkeit nicht uebernommen (6), A2 quietTo=Von (7), A3 Cooldown nicht uebernommen (8), A4 Stille-Schalter ignoriert (2), A5 Abend-Raster-Guard weg (1), A5b Morgen-Raster-Guard weg (7), A6 enabled=UND (4), A7 ohne Stand -> reportConfig undefined (1), A8 Rumpf ersetzt statt gemischt (9), A9 ...alarm weg (17), A10 evening_enabled aus Morgen (4), B1 Meldung ohne Kopie (1), B3 Delta gegen sich selbst (4), B4 Meldung unterdrueckt (19), C1 Anlege-Zweig im Reiter aus (12), C2 onAnlegeStand nicht gerufen (12), C3/C3b/C3c je ein Abschnitt (channels/cooldown/quiet-hours) nicht ausgeblendet (2/4/2), C4 Ortsvergleich ausgeblendet (1), C5 Trip nicht ausgeblendet (3), C6 createMode-Abfrage weg (10, Hub waere betroffen), C7 Filter weg (4), D1 Gleichheitswaechter weg (1), D2/D2b Rueckschreiben reportConfig bzw. alarm weg (11/10), D3b Anlegeweg ergaenzeVersandStandard statt ...Standardwerte (44), D5d alert_channels im Eintrittstrip weg (1), D6 createMode am Desktop-Mount aus (13), D7 onAnlegeStand am Desktop-Mount weg (105), D8 Stand nicht gemerkt (5), D9 stubTrip-Spread weg (1).
UEBERLEBT, gleichwertig bzw. ohne beobachtbare Wirkung: B2 (Basiskopie im Speicherer entfernt: der Reiter ersetzt `stand` stets (ZustellungTab.svelte:99, kein In-place-Schreiben), die Basis wird nie veraendert); C2b (context hart 'route': Anlegen-Speicherer wird nur vom Trip-Anlegen mit context route gebaut, Ortsvergleich nutzt Alt-Panel); D5/D5b/D5c (cooldown/quiet_from/channel_thresholds im Eintrittstrip auf undefined: initialCreateTripAlarmState liefert exakt diese Leerwerte bzw. Standard-Dringlichkeiten, standAusTrip faellt auf dieselben Standardwerte; spaetere Remounts nutzen zustellungStart); D3 war versehentlich eine No-op-Ersetzung (nicht gefunden, kein Lauf).
Gegenprobe Wirkstelle: Nutzer erreicht den POST ueber TripNewEditor -> mitZustellung -> buildCreateTripPayload; D2/D2b/D6/D7/D8 mutieren genau diese Strecke und sind rot.
**Implementierer:**
(nicht befragt; Adversary-Lauf ohne Implementierer-Kontext)

### Runde 2
**Adversary:**
Zweite Pruefung der Spec-ACs gegen Code und Tests statt gegen Mutationsergebnisse: AC-1 (SSR-Test, Desktop/Mobil, Alt-Panel und Mail-Inhalt-Karte fehlen) PROVEN; AC-2/AC-3 (Payload-Test mit getrennten Kanaelen, je Feld) PROVEN; AC-4 (bitgleich bei nie bedientem Reiter, D3b rot) PROVEN; AC-5 (kein PUT, B4/C1 rot) PROVEN; AC-6 (zustellungStart, D8/D7 rot) PROVEN; AC-7 (A5/A5b rot) PROVEN; AC-9 (C3-C7 rot, Ortsvergleich C4 rot) PROVEN; AC-10 (Standardwerte-Weg D3b rot) PROVEN; AC-11/AC-13 durch SSR- und Infobox-Tests in der Suite (2129 gruen) PROVEN; AC-8/AC-12 nur auf Kernebene (Live-E2E gegen Staging nicht ausgefuehrt, Aufgabe von /e2e-verify). Frueh-Konvergenz-Skepsis: die einzigen Ueberlebenden wurden einzeln auf Gleichwertigkeit hin am Quelltext geprueft (siehe Runde 1), keine echte Luecke. Vorrunden-Findings F001-F004 behoben. Keine Aenderung an Produktionsdateien hinterlassen: alle sechs per cmp identisch zur Sicherung; kein checkout/stash/reset benutzt.
**Implementierer:**
(nicht befragt)

## Herkunft der Vorbedingungen

Hinweis: kein Sprachprofil konfiguriert (`precondition_origins.default_lang`). Vorbedingungen stammen aus den Spec-ACs, den benannten Testdateien und dem Quelltext.

Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts:99
Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:80
Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:361
Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:539
Code reference: frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts:45
Code reference: frontend/src/lib/components/shared/AlarmeTab.svelte:217

## Verdict

VERDICT: VERIFIED

Tests: 2129 passed, 0 failed. Mutationen: 41 eingebaut, 36 rot, 5 ueberlebt (alle gleichwertig, begruendet; D3 No-op). Offen nur Live-E2E (AC-8, AC-12) fuer /e2e-verify.

## Geprüfte Dateien

- sha256:94a000978df0f78c6f73abaee0b07f26ddf1c5aa708d49e1ee8a962464407287  frontend/src/lib/components/shared/AlarmeTab.svelte
- sha256:35e21af4e0ae5391d7b5864561e70d5bec90f194c01007fe80f587517a5b27cd  frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts
- sha256:1691680cbc38c18258cd7cc24bf88cd2d7d6b40e4d7a7cffdbd5cca3b4cf3f94  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- sha256:8f4c0b9c711d297cdf05feeb28fa89b7c76e66c21edb1f0f75b95d4ec9f5302c  frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts
- sha256:c4f3361082123b7d6bfbf96498d9a415bfa3dadbc6951df7b7982729c5b1e599  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- sha256:73a2cd3b04b4512d3a55821d9ff1572b65ef929cc9086e1ee68fb8c3f0520535  frontend/src/lib/components/trip-new/tripNewLogic.ts

## Prüfbasis

- base: 3ea65a10d223ce8227255201fe15c800af302b81
- blob:2ffdd0bf1982b7232dd41c170ee4fdaff87909bc  frontend/src/lib/components/shared/AlarmeTab.svelte
- blob:8a5eefe95ee74cb9cc9578558bdef32c5a44854a  frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts
- blob:9701299aa05a2a2ee304c3bcd6723c47562837b7  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- blob:d8599c9f1befd78366738488221338ceece9ef65  frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts
- blob:942374bd4c08aab401ddd19a4d7d92087fc7983e  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- blob:9a08d8b4c8472f75974bbb8a671d4a8b7490f153  frontend/src/lib/components/trip-new/tripNewLogic.ts
