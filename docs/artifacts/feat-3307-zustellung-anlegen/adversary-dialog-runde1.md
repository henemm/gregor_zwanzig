# Adversary Dialog — feat-3307-zustellung-anlegen
Spec: docs/specs/modules/feat_3332_zustellung_anlegen_trip.md
Datum: 2026-11-24 13:20

## Checkliste
- [x] **Input:** Nutzer legt einen Trip an, stellt im Schritt Zustellung Zeiten (z. B. Morgen 06:45), Kanäle, Dringlichkeit Telegram HIGH und Stille Stunden ein und legt an.
- [x] **Output:** Genau ein `POST` auf die Trip-Anlage mit diesen Werten in `report_config` und den Alarm-Feldern; der Hub-Reiter Zustellung des neuen Trips zeigt denselben Stand.
- [x] **Side effects:** Nur der lesende Profil-Abruf; kein PUT, kein Speichern vor dem Anlegen.
- [x] **AC-1:** Given ein angemeldeter Nutzer legt einen Trip an / When er den Schritt Zustellung öffnet, in der Mobil- und in der Desktop-Ansicht / Then sieht er den Reiter Zustellung mit Briefing-Zeiten, Kanal-Tabelle und Stille Stunden wie im Hub, und das Alt-Panel mit Versand-Abschnitt und die Mail-Inhalt-Karte erscheinen dort nicht mehr.
- [x] **AC-2:** Given der Nutzer stellt im Anlegen Briefing-Zeiten, Kanäle und Stille Stunden ein / When er den Trip anlegt / Then enthält der eine POST `report_config.morning_time`/`evening_time` (HH:MM:SS), `morning_enabled`/`evening_enabled`, `send_email/telegram/sms/premium_sms` und `alert_quiet_from/_to` mit genau den eingestellten Werten.
- [x] **AC-3:** Given der Nutzer wählt Alarm-Kanäle, die Dringlichkeit HIGH für Telegram und einen Cooldown / When er den Trip anlegt / Then stehen `alert_channels`, `alert_channel_thresholds.telegram == "HIGH"` und `alert_cooldown_minutes` im POST.
- [x] **AC-4:** Given der Nutzer öffnet den Schritt Zustellung, bedient den Reiter aber nicht / When er den Trip anlegt / Then ist der POST-Körper in `report_config`, den Alarm-Feldern und `display_config.channels` bitgleich zu dem heutigen Körper (keine stille Änderung der Startwerte, `multi_day_trend_reports` und die Standardwerte aus `ergaenzeVersandStandard` weiter vorhanden).
- [x] **AC-5:** Given der Nutzer ändert Werte im Reiter / When er bis zum Anlegen weitermacht / Then gibt es weder einen PUT noch einen Autosave noch einen Schreibaufruf vor dem Anlegen, und beim Anlegen genau einen POST.
- [ ] **AC-6:** Given der Nutzer hat im Reiter Zustellung Werte gesetzt / When er zwischen Mobil und Desktop wechselt oder Schritte vor und zurück geht / Then bleibt der Stand erhalten und die Werte stehen unverändert im POST.
- [x] **AC-7:** Given der Nutzer gibt eine rasterfremde Uhrzeit ein (z. B. 06:50) / When er den Trip anlegt / Then sendet der POST die letzte gültige Viertelstunden-Zeit und es gibt keinen Server-Fehler 400.
- [x] **AC-8:** Given ein Trip wird im Anlegen mit gesetzter Zustellung angelegt / When der Nutzer danach den Hub-Reiter Zustellung dieses Trips öffnet / Then zeigt er dieselben Zeiten, Kanäle, Dringlichkeiten, Stille Stunden und denselben Cooldown wie beim Anlegen eingestellt.
- [x] **AC-9:** Given der Nutzer ist im Schritt Alarme des Trip-Anlegens / When er den Reiter öffnet / Then fehlen dort die Abschnitte Alarm-Kanäle, Cooldown und Stille Stunden (sie stehen im Reiter Zustellung), während amtliche Warnungen und Metrik-Alarmstufen dort bleiben; jedes Feld hat genau eine Bedienstelle, und im Hub und im Ortsvergleich-Anlegen bleibt der Reiter Alarme unverändert.
- [x] **AC-10:** Given ein Nutzer legt einen Trip an / When er im Schritt Zustellung die Mail-Inhalt-Felder sucht / Then sind E-Mail-Format, Etappen-Statistik, Vortagesvergleich und Nacht-Block weiter über die Karte „Was steht wo“ bedienbar, ihre Werte stehen wie bisher im POST, und `show_stability` sowie Bestandsfelder behalten ihren Standardwert.
- [x] **AC-11:** Given der Reiter Zustellung im Trip-Anlegen / When der Nutzer ihn öffnet / Then erscheint dort keine Infobox mehr, während sie im Alt-Panel des Ortsvergleich-Anlegens und im Reiter Alarme des Trip-Anlegens wie bisher nur beim Anlegen erscheint.
- [x] **AC-12:** Given zwei verschiedene Nutzer A und B mit verschiedenem Kanalstatus (A hat Telegram verbunden, B nicht) / When beide je einen Trip anlegen / Then zeigt der Reiter bei A die Dringlichkeit für Telegram und bei B nicht, jeder Trip erscheint nur beim jeweiligen Nutzer, und B sieht den Trip von A nicht.
- [x] **AC-13:** Given der Ortsvergleich wird angelegt / When der Nutzer den Schritt Zustellung öffnet / Then verhält er sich unverändert wie vor dieser Änderung (Alt-Panel, ein POST), D1 ändert dort nichts.

## Dialog

### Runde 1
**Adversary:**
Testlauf (benannte Dateien: zustellung-tab/__tests__, alarme_tab_ohne_zustellung_3332, trip_anlegen_zustellung_*_3332, infobox_nur_beim_anlegen, anlegen_ohne_autosave, dazu alle trip-new/__tests__ und shared/__tests__): 2051 pass, 0 fail (docs/artifacts/feat-3307-zustellung-anlegen/adversary-test-output.txt).
Mutations-Gegenprobe, 30 Verfaelschungen per String-Ersetzung mit externer Sicherung (md5 aller sechs Produktionsdateien danach identisch). 26 gefangen. UEBERLEBT: M11 (ZustellungTab ignoriert zustellungStart), M12/M12b (Editor reicht zustellungStart weder Desktop noch Mobil durch), M20 (Inhaltsgleichheits-Guard in handleZustellungAnlegeStand entfernt), M24 (Eintrittstrip ohne Cooldown, gleichwertig, da standAusTrip auf 120 faellt), M28 (rc.enabled = nur morgenAn statt morgenAn||abendAn).
Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:75
Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts:99
Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:361
Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:539
Code reference: frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts:25
Code reference: frontend/src/lib/components/shared/AlarmeTab.svelte:217

Finding F001: Severity HIGH, Category: edge_case, Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:75. AC-6 (Stand ueberlebt Wechsel Mobil/Desktop und Schrittwechsel) ist in der Kern-Schicht ungeprueft: die Mutationen M11/M12/M12b (zustellungStart ignorieren bzw. in beiden Editor-Mounts weglassen) lassen alle Tests gruen; `zustellungStart` kommt in den 3332-Tests nur in einem Kommentar vor. Spec verlangt Unit-Test „Neuaufbau mit zustellungStart ergibt denselben Stand“. Wirkstelle: ohne die Durchreichung wuerde nach Ansichtswechsel der Reiter auf den Eintrittsstand zurueckspringen, waehrend der Editor `zustellungStand` behaelt und beim Anlegen sendet (Anzeige und POST laufen auseinander, stiller Datenverlust-Eindruck). Nur die E2E TZ-3 (hier nicht lauffaehig) bewacht es. Remediation: SSR-Test, der ZustellungTab mit zustellungStart (z. B. Morgen 06:45, Stille an) rendert und die Anzeige prueft, plus AST-Test, dass beide ZustellungTab-Mounts im Editor `zustellungStart={zustellungStand}` tragen.
Finding F002: Severity MEDIUM, Category: edge_case, Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:370. M28 (`rc.enabled = stand.morgenAn`) bleibt gruen: es gibt keinen Test „nur Abend an“ => enabled true. Folge der Mutation waere Gesamtschalter aus (reportSlotAktiv: enabled=false schaltet beide Slots ab), also ein Abend-Briefing, das nie kommt. Remediation: Fall Morgen aus/Abend an in den Payload-Test aufnehmen.
Finding F003: Severity LOW, Category: anti_pattern, Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:540. Guard gegen Update-Schleifen (M20) ohne Test; im SSR nicht beobachtbar. Remediation: reiner Helfer „standGleich“ mit Unit-Test oder ausdrueckliche Aufnahme in die E2E.
Bewertung der bekannten Abweichung (mitZustellung bei jeder Meldung): vertretbar. Nach der ersten Aenderung steht alert_cooldown_minutes=120 statt null im POST; der Server faellt bei null auf throttle_hours*60 = 120 (src/services/trip_alert.py:1737, Default 2) und der Hub zeigt ohnehin 120 (zustellungModell.ts cooldownVon); keine Verhaltensaenderung. Ohne Bedienung bleibt der Koerper bitgleich (M27 gefangen). Kein Finding.
Weitere Pruefungen: AC-9 (M07/M08/M25/M26 gefangen: Hub und Ortsvergleich unveraendert, Trip-Anlegen ohne channels/cooldown/quiet-hours), AC-13 (M07 gefangen), AC-4 (M06 mit 57 roten Tests gefangen, Fixture-Vergleich wirkt), AC-5 (M13/M14/M14b gefangen; E2E zaehlt PUT/POST), AC-7 (M09/M10 gefangen). Alt-Test-Umstellungen gesichtet: keine Zusicherung still entfernt, jeweils ersetzt (Mail-Karte 0 Instanzen + Standardfelder im Speicherweg; Premium-SMS ueber KanalTabelle; Infobox-Test mit expliziter Gegenprobe); Infobox „wetter-metriken“ im Trip-Anlegen entfaellt laut Entscheidung RED Nr. 2. AC-12 (zwei Nutzer) nur per E2E-Spec gelesen, nicht ausgefuehrt (Staging noetig).
**Implementierer:**
(nicht befragt; Adversary-Lauf ohne Implementierer-Kontext)

### Runde 2
**Adversary:**
Zweite Runde: Gegenprobe auf die Wirkstelle. Fuer F001 wurde geprueft, ob ein anderer Test die Durchreichung mittelbar deckt (grep zustellungStart in allen Tests: nur Kommentar in trip_anlegen_zustellung_verdrahtung_3332.test.ts) und ob M11 nur ein gleichwertiger Mutant ist (nein: der Editor-Stand wird sonst beim Neuaufbau nicht angezeigt). M24 ist gleichwertig (kein Finding). Verbotene Wege nicht benutzt (kein checkout/stash/reset); alle sechs Produktionsdateien per cmp gegen die Sicherung identisch.
**Implementierer:**
(nicht befragt)

## Herkunft der Vorbedingungen

Hinweis: kein Sprachprofil konfiguriert (`precondition_origins.default_lang`). Vorbedingungen stammen aus den Spec-ACs, dem Kontextdokument docs/context/feat-3307-zustellung-anlegen.md und den benannten Testdateien.

## Verdict

VERDICT: BROKEN
