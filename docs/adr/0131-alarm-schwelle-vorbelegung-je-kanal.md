# ADR-0131: Alarm-Schwelle mit Vorbelegung je Kanal; Premium-SMS bekommt endgültig den SMS-Inhalt

- **Status:** Akzeptiert (PO-Entscheidungen 2026-11-28, Issue #2801)
- **Datum:** 2026-11-28
- **Bezug:** Issue #2801 (Epic #2791 S9), Spec `docs/specs/modules/feat_2801_alarm_schwelle_vorbelegung_je_kanal.md`, Kontext `docs/context/s9-2801-premium-sms-eigene-liste.md`. **Löst teilweise ab:** [ADR-0046](0046-alarm-kanal-schwelle.md) (Startwert `LOW` für alle Kanäle), [ADR-0095](0095-kanal-paritaet-jeder-kanal-jede-frage.md) Nr. 4 („Ohne gesetzten Wert gilt der Startwert `LOW`“), [ADR-0124](0124-was-steht-wo-eine-tabelle.md) Nr. 8 („Premium-SMS folgt **vorerst** der SMS, eigene Auswahl mit S9“), Konzept `docs/context/einstellungen_neu.md` N2 („eigene Liste“), PO-Entscheidung 2026-08-05 / `feat_1461_s3b2a` AC-13. **Bewahrt:** rote Linie #638 (rohes Opt-in im Protokoll), [ADR-0101](0101-read-modify-write-mit-merge.md) (kein Datenumbau), ADR-0095 (Kanal-Parität), ADR-0097 (ein Code für Trip und Orte), ADR-0104 (Texte DE/EN über den Katalog).

## Kontext

Bisher galt für jeden Alarm-Kanal ohne gesetzten Wert die Schwelle „gering“ (`LOW`). Damit gingen auch geringe Alarme per SMS und per Premium-SMS hinaus. Die Premium-SMS läuft über Satellit (Garmin inReach) und kostet je Nachricht; die SMS kostet weniger, aber auch etwas. E-Mail und Telegram kosten nichts. Konzept N2 sah für die Premium-SMS zusätzlich eine eigene Metrik-Auswahl im Briefing vor; ADR-0124 Nr. 8 hielt „folgt vorerst der SMS“ als Zwischenstand fest.

## Entscheidung

1. **Vorbelegung je Kanal.** Ohne gesetzten Wert gilt: E-Mail `LOW`, Telegram `LOW`, SMS `MODERATE`, Premium-SMS `HIGH`. Gilt für alle Trips und Orte, neu wie Bestand, für Wetter-, amtliche und Radar-Alarme.
2. **Gesetzte Werte bleiben.** Ein gespeicherter Wert gilt unverändert, auch ein ausdrücklich gesetztes `LOW`. Leere oder unbekannte Werte gelten als nicht gesetzt. Gesetzt wird je Kanal einzeln.
3. **Eine Quelle je Sprache.** Python: `services.alert_channel_threshold.default_threshold()` / `resolve_threshold()`; alle Alarm-Pfade (über `split_by_threshold`) und die Briefing-Schwellen in `trip_report.py` (SMS) und `narrow.py` (Telegram) nutzen sie. Frontend: `DEFAULT_CHANNEL_THRESHOLDS` / `resolveChannelThreshold` in `alertChannelState.ts`; Alarme-Reiter, Zustellung, Neuanlage Trip und Orte nutzen sie. Gleichheit beider Seiten sichert `tests/fixtures/alarm_schwelle_vorbelegung_2801.json`. Go setzt keinen Default (nil bleibt nil).
4. **Kein Datenumbau.** Die Wirkung entsteht nur zur Laufzeit; Bestandsdaten werden nicht geschrieben (ADR-0101).
5. **Premium-SMS bekommt endgültig den SMS-Inhalt.** Keine eigene Auswahl, keine eigene Spalte in „Was steht wo“. Der Premium-Text ist der SMS-Text, von hinten auf 153 Zeichen gekürzt, amtliche Warnungen zuletzt. Der Unterschied zwischen SMS und Premium-SMS bei Alarmen kommt allein über die Schwelle.
6. **Rote Linie #638 bleibt.** Unterdrückte Kanäle stehen im Protokoll als rohes Opt-in mit Grund `below_channel_threshold`.

## Verworfene Alternativen

- **Startwert `LOW` für alle beibehalten:** Satellit-Nachrichten für jeden geringen Alarm, ohne dass der Nutzer das gewählt hat.
- **Vorbelegung nur für neue Trips/Orte (Bestand bleibt `LOW`):** zwei Regeln für dieselbe Frage; der PO wollte eine Regel für alle.
- **Vorbelegung beim Anlegen in die Daten schreiben:** Datenumbau, spätere Änderungen der Vorbelegung würden niemanden mehr erreichen.
- **Eigene Premium-Auswahl (N2):** zusätzliche Auswahl ohne erkennbaren Nutzen gegenüber „derselbe Inhalt, gekürzt“.

## Konsequenzen

- **Bestand ohne gesetzten Wert:** SMS meldet ab sofort erst ab „mittel“, Premium-SMS erst bei „hoch“ (sofern eingeschaltet). E-Mail und Telegram bleiben vollständig, ein geringer Alarm geht nie verloren (ADR-0095).
- **Amtliche Warnungen im SMS-Briefing:** Die SMS-Schwelle steuert die niedrigste amtliche Stufe im Kurznachrichten-Bericht (ADR-0046). Ohne gesetzten Wert fehlen Warnungen der Stufe gering im Trip-SMS- und damit im Premium-SMS-Briefing. Telegram (Vorbelegung `LOW`) und E-Mail sind nicht betroffen.
- **Festschreiben beim Speichern:** Wer in der Zustellung eine Dringlichkeit ändert, schreibt die angezeigten (aufgelösten) Werte aller vier Kanäle fest; spätere Änderungen der Vorbelegung erreichen diese Nutzer nicht mehr.
- **Texte:** Hinweis unter „Was steht wo“ („Die Premium-SMS bekommt denselben Inhalt wie die SMS.“) und Fußzeile der Kanal-Tabelle in DE und EN über den Katalog.
