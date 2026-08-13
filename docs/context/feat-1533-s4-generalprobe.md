# Context: S4 Generalprobe Premium-SMS am Garmin inReach (#1533)

## Request Summary

#1533 ist Scheibe **S4** des Epics #1676 (Premium-SMS als vierter Kanal) — der
finale Nachweis am echten Garmin-inReach-Gerät vor der KHW-Tour (ab 20.8.).
Am 2026-08-11 hat der PO 2 von 9 Checklisten-Punkten am Gerät bestätigt
(Erstkontakt, Absender-als-Rufnummer erreicht das Gerät) und den Kanal danach
wieder abgeschaltet. **Sechs Punkte offen:**

1. Scheduler-getriebener Versand (morning + evening), nicht Handauslösung
2. Zeichenbudget: vollständig, ≤160 Zeichen, keine Kürzung/Aufteilung
3. Zeichensatz: SMS-Token (`C+`/`C~`/`C?`, Sonderzeichen) unverstümmelt
4. Latenz gemessen (Versandzeit → Empfang)
5. Alarm-Pfad am Gerät (seit #1701 live, am Gerät unbelegt)
6. Lesbarkeit auf dem Display (Zeilenumbrüche, Reihenfolge)

Aus dem Issue-Text: **„Alle sechs brauchen den Kanal wieder eingeschaltet und
kosten Geld. Das ist eine PO-Entscheidung, kein technischer Schritt — keine
Sitzung schaltet ihn eigenmächtig ein."** Diese Scheibe darf den Kanal daher
nicht selbst aktivieren.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:1154-1158, 1500-1504` | `send_premium_sms` bereits korrekt ins Scheduler-DTO verdrahtet (Tier-Gate `premium_sms_allowed()`, nicht `sms_allowed()`) — Punkt 1 ist Code-seitig fertig, nur am Gerät unbewiesen |
| `src/services/notification_service.py:429-438, 587-593, 908-920` | Alle drei Versandpfade (Briefing, No-Data-Hint, amtlicher Alarm) rufen `PremiumSmsOutput(...).send()` symmetrisch zu `SMSOutput` |
| `src/output/channels/seven_io_base.py:155-187` | Gemeinsamer Transport beider seven.io-Kanäle. **Kein** persistiertes Sende-Log mit Zeitstempel — nur `logger.info(...)`. Für Latenzmessung (Punkt 4) fehlt Instrumentierung |
| `src/services/inbound_sms_reader.py:56,215-231` | Pollt bereits `gateway.seven.io/api/journal/inbound` für die Rückadresse. Für Latenz bräuchte man das Pendant `journal/outbound` (liefert je Nachricht echten Sendezeitpunkt + Zustellstatus) — existiert im Code noch nicht |
| `src/services/preview_service.py:346-348` | `report.sms_text` ist der **einzige** Text, der sowohl an SMS als auch Premium-SMS geht (S2a-Entscheidung: kein eigener Render-Pfad). Die Vorschau kann also Punkt 2+3 **ohne jeden Realversand** am echten Trip-Text prüfen |
| `src/output/renderers/sms_trip.py` (`format_sms`, TokenLine-Pipeline) | Erzeugt reine ASCII-Token (Ziffern/Buchstaben, kein literales `°`) — strukturell GSM-7-sicher; `_sms_stage_prefix` faltet den Etappennamen über `fold_ascii` |
| `src/output/renderers/alert/official_alerts.py:1811-1896` (`render_official_alert_sms`) | Amtlicher-Alarm-SMS-Text (auch für Premium-SMS, notification_service.py:912-915): `sms_prefix` (Trip-Name) wird **erst in `head` eingebettet, dann komplett per `_ascii()` gefaltet** (Zeile 1892) — Trip-Namen mit Umlauten (z.B. „Höhenweg") sind damit bereits abgesichert. Limit hier `140`, nicht 160 (dritte SMS-Grenze aus #1719 S4) |
| `src/output/renderers/comparison.py:583-621` (`_sms_gsm7_safe`) | Bereits gelöstes Beispiel derselben Bugklasse im Compare-Pfad: `°` erzwang früher **stille UCS-2-Umschaltung → Segment-Verdopplung/Kosten**. Kein Pendant-Test existiert für den Trip-Briefing-Pfad (`test_compare_sms_gsm7_charset.py` ist compare-only) |
| `internal/scheduler/scheduler.go` (+`scheduler_test.go`) | `last_run`-Tracking existiert **pro Job** (`trip_reports_hourly`), nicht pro Kanal — beweist „Job lief", nicht „Premium-SMS kam an" |
| ADR-0049, `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` | Bindende Design-Entscheidungen: kein eigener Render-Pfad (D8), 30-Tage-Verfallsfrist Rückadresse (D6), fail-closed in der Kanalklasse |

## Existing Patterns

- **Preview-vor-Realversand** ist das etablierte Muster im Projekt (Preview-Endpoints Epic #140) — dieselbe Route, die die UI für die Vorschau nutzt, kann hier ohne Kosten die Punkte 2+3 gegen den echten KHW-Trip prüfen.
- **GSM-7-Sanitisierung existiert bereits einmal** (`comparison.py`), aber lokal im Compare-Renderer — kein geteilter Wächter/Test, der auch den Trip-Pfad abdeckt. Bisherige Prüfung ergab: der Trip-Pfad ist beim Briefing strukturell sicher (reine ASCII-Token), beim Alarm-Pfad sicher durch `_ascii()`-Nachbehandlung. Kein bekannter Bug — aber auch kein automatisierter Wächter, der einen künftigen Regress fände (Analogie zu `test_compare_sms_gsm7_charset.py`, das es für den Trip-Pfad nicht gibt).
- **`format_alert_sms()` in `sms_trip.py`** hat keine Aufrufstelle mehr (toter Legacy-Pfad, „§A4 unchanged") — nicht Teil des echten Alarmversands, daher hier ignoriert.
- **journal/inbound-Polling** (`inbound_sms_reader.py`) ist die Vorlage für einen analogen `journal/outbound`-Abruf zur Latenzmessung — gleiches Gateway, andere Route.

## Dependencies

- **Upstream:** seven.io-Gateway (Versand + `journal/inbound`/`journal/outbound`), Garmin inReach (physisches Gerät, Empfängerlogik außerhalb unserer Kontrolle), Go-Scheduler (`trip_reports_hourly`-Cron) für Punkt 1.
- **Downstream:** keine — S4 ist die letzte Scheibe des Epics, nichts hängt fachlich von ihr ab außer der PO-Entscheidung, ob der Kanal für die Tour vertrauenswürdig ist.

## Existing Specs

- `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` (S1, live)
- `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` (S2a, live)
- ADR-0049 (`docs/adr/0049-premium-sms-vierter-kanal.md`)
- Kein Spec-Dokument für S3 (#1717) explizit referenziert hier gefunden — S3 ist reine Oberfläche, für S4 nicht code-relevant.

## Risks & Considerations

- **Money-Blast-Radius:** jede Aktivierung des Kanals kostet echtes Geld (Premium-SMS-Tarif) und darf laut CLAUDE.md nur der PO auslösen. Die Spec muss die **Reihenfolge** so bauen, dass alles automatisierbar (Punkte 2+3 per Vorschau) VOR dem ersten kostenpflichtigen Versand geprüft ist, und die kostenpflichtigen Schritte (1, 4, 5, 6) in möglichst wenigen, gebündelten Aktivierungsfenstern zusammenfallen.
- **Latenzmessung fehlt strukturell:** ohne `journal/outbound`-Abruf gibt es keine maschinenlesbare Bestätigung „gesendet um X, zugestellt um Y" — nur PO-Beobachtung am Gerät + unser `logger.info`-Zeitstempel im Anwendungslog. Zu klären in der Spec: reicht ein grober Soll-Ist-Vergleich (Scheduler-Log-Zeit vs. PO-Ablesezeit am Gerät), oder lohnt sich ein kleiner `journal/outbound`-Abrufer?
- **Alarm-Pfad am Gerät (Punkt 5) braucht einen echten oder manuell ausgelösten Test-Alarm** — ein reales Gewitter ist nicht planbar; ein manuell triggerbarer Testalarm für den Alarm-Pfad wäre zu klären (existiert vermutlich bereits ein Test-/Debug-Hebel, sonst PO-Entscheidung nötig).
- **Lesbarkeit (Punkt 6)** ist reine Beobachtung am physischen Gerät (Foto/Beschreibung durch den PO) — kein Code, keine Automatisierung möglich.
- **GSM-7-Wächter-Lücke:** kein automatisierter Test verhindert einen künftigen Regress im Trip-/Alarm-SMS-Pfad (nur der Compare-Pfad ist bewacht). Ob das in dieser Scheibe geschlossen wird (kleiner Pendant-Test) oder als Nebenbefund nach #1199 geht, ist eine Spec-Entscheidung — aktuell **kein** bekannter Bug, nur eine Bewachungslücke.
- **Scope-Frage für die Spec:** wie viel „Code" gehört überhaupt in diese Scheibe? Denkbare Bausteine: (a) ein Vorschau-Check-Skript/Test, das Zeichenbudget+Charset am echten KHW-Trip vor jedem Realversand verifiziert (Punkte 2+3, kostenlos), (b) optional ein `journal/outbound`-Abrufer für Latenz (Punkt 4), (c) ein GSM-7-Pendant-Test für den Trip-/Alarm-Pfad (Wächter-Lücke, kein akuter Bug). Punkte 1, 5, 6 bleiben genuine Live-Beobachtung mit PO-Mitwirkung, kein Code.
