# Adversary Dialog — feat-3307-zustellung-anlegen
Spec: docs/specs/modules/feat_3332_zustellung_anlegen_trip.md
Datum: 2026-11-24 14:10

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
- [x] **AC-8:** Given ein Trip wird im Anlegen mit gesetzter Zustellung angelegt / When der Nutzer danach den Hub-Reiter Zustellung dieses Trips öffnet / Then zeigt er dieselben Zeiten, Kanäle, Dringlichkeiten, Stille Stunden und denselben Cooldown wie beim Anlegen eingestellt.
- [x] **AC-9:** Given der Nutzer ist im Schritt Alarme des Trip-Anlegens / When er den Reiter öffnet / Then fehlen dort die Abschnitte Alarm-Kanäle, Cooldown und Stille Stunden (sie stehen im Reiter Zustellung), während amtliche Warnungen und Metrik-Alarmstufen dort bleiben; jedes Feld hat genau eine Bedienstelle, und im Hub und im Ortsvergleich-Anlegen bleibt der Reiter Alarme unverändert.
- [x] **AC-10:** Given ein Nutzer legt einen Trip an / When er im Schritt Zustellung die Mail-Inhalt-Felder sucht / Then sind E-Mail-Format, Etappen-Statistik, Vortagesvergleich und Nacht-Block weiter über die Karte „Was steht wo“ bedienbar, ihre Werte stehen wie bisher im POST, und `show_stability` sowie Bestandsfelder behalten ihren Standardwert.
- [x] **AC-11:** Given der Reiter Zustellung im Trip-Anlegen / When der Nutzer ihn öffnet / Then erscheint dort keine Infobox mehr, während sie im Alt-Panel des Ortsvergleich-Anlegens und im Reiter Alarme des Trip-Anlegens wie bisher nur beim Anlegen erscheint.
- [x] **AC-12:** Given zwei verschiedene Nutzer A und B mit verschiedenem Kanalstatus (A hat Telegram verbunden, B nicht) / When beide je einen Trip anlegen / Then zeigt der Reiter bei A die Dringlichkeit für Telegram und bei B nicht, jeder Trip erscheint nur beim jeweiligen Nutzer, und B sieht den Trip von A nicht.
- [x] **AC-13:** Given der Ortsvergleich wird angelegt / When der Nutzer den Schritt Zustellung öffnet / Then verhält er sich unverändert wie vor dieser Änderung (Alt-Panel, ein POST), D1 ändert dort nichts.

## Dialog

### Runde 1
**Adversary:**
Testlauf (benannte Dateien: alle trip-new/__tests__, shared/__tests__, zustellung-tab/__tests__, alarme-tab/__tests__): 2129 pass, 0 fail (docs/artifacts/feat-3307-zustellung-anlegen/adversary-test-output.txt).
Die fuenf ueberlebenden Mutationen der Vorrunde erneut eingebaut (String-Ersetzung, externe Sicherung, cmp danach identisch): M11 (ZustellungTab ignoriert zustellungStart) ROT (5 Tests, u. a. SSR Test 2, Verdrahtung Test 7); M12 und M12b (Desktop- bzw. Mobil-Mount ohne zustellungStart) ROT; M20 (Inhaltsgleichheits-Guard entfernt) ROT (F003-Test); M28 (enabled = nur morgenAn) ROT (Test "nur Abend an"); zusaetzlich M28b und M28c ROT. F001, F002, F003 der Vorrunde sind behoben.
Neue eigene Mutationen (35, alle sechs Produktionsdateien): 28 gefangen (vertauschte Morgen/Abend-Felder und -Zeiten, Raster-Guard entfernt, Stille Stunden/Cooldown/Dringlichkeit nicht uebernommen, Kopie der Meldung entfernt, Anlege-Zweig im Reiter abgeschaltet, Abschnittslisten des Alarme-Reiters in Trip-Anlegen/Hub/Ortsvergleich, createMode-Abfrage entfernt, Eintrittstrip, Standardwerte-Weg, Stand-Merken, Rueckschreiben von reportConfig/alarm, mitZustellung ohne Stand).
UEBERLEBT mit Wirkung: N05 (`send_<kanal>` aus stand.alarme statt stand.briefing) und N06 (Alarm-Kanaele aus stand.briefing statt stand.alarme), beide auch gegen die volle Suite (2129 Tests) gruen. Ursache: im Payload-Test (trip_anlegen_zustellung_payload_3332.test.ts:48-49) sind `briefing` und `alarme` identisch belegt, eine Verwechslung ist unbeobachtbar. Folge fuer den Nutzer: Briefing-Kanalwahl und Alarm-Kanalwahl landen vertauscht im POST. Gleichwertig bzw. ohne Wirkung: N11, N14, N19, N20, N28, N29, N35 (Begruendung: Ergaenzer fuellt auf, Zustand wird nie in-place veraendert, Editor nutzt nur `stand` nicht `nutzlast`, Eintrittsstand ist leer, Ergaenzer setzt multi_day_trend_reports wieder).

Finding F004: Severity MEDIUM, Category: edge_case, Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:373. mitZustellung bildet `send_<kanal>` aus stand.briefing (Zeile 373) und Alarm-Kanaele aus stand.alarme (Zeile 377); die Tests belegen beide mit identischen Werten, ein Vertauschen bleibt gruen. Spec AC-2/AC-3 verlangt genau die eingestellten Werte je Feld. Remediation: im Payload-Test briefing und alarme unterschiedlich belegen (z. B. briefing email+sms, alarme telegram+premium_sms) und je Feld einzeln pruefen.
**Implementierer:**
(nicht befragt; Adversary-Lauf ohne Implementierer-Kontext)

### Runde 2
**Adversary:**
Gegenprobe auf die Wirkstelle: F001 ist dort bewacht, wo er wirkt (SSR-Reiter mit zustellungStart sowie beide Editor-Mounts einzeln, M11/M12/M12b rot). F003 durch Verhaltenstest mit Objektidentitaet gefangen. AC-6 auf Kern-Ebene PROVEN; E2E (AC-8, AC-12 mit zwei Nutzern, TZ-3) hier nicht ausgefuehrt, nur Spec gelesen (Staging noetig). N05/N06 zweite Pruefung gegen die volle Suite: weiter gruen, Finding bleibt. Ein Mutationslauf wurde durch Zeitlimit abgebrochen; die betroffene Datei wurde per cmp als abweichend erkannt und aus der Sicherung wiederhergestellt; abschliessend alle sechs Produktionsdateien identisch zur Sicherung (cmp). Kein checkout/stash/reset benutzt.
**Implementierer:**
(nicht befragt)

## Herkunft der Vorbedingungen

Hinweis: kein Sprachprofil konfiguriert (`precondition_origins.default_lang`). Vorbedingungen stammen aus den Spec-ACs, den benannten Testdateien und dem Quelltext.

Code reference: frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts:99
Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:75
Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:373
Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:539
Code reference: frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts:25
Code reference: frontend/src/lib/components/shared/AlarmeTab.svelte:217

## Verdict

VERDICT: BROKEN
