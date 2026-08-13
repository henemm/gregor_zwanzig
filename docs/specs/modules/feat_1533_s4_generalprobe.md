---
entity_id: feat_1533_s4_generalprobe
type: module
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [sms, premium, garmin, seven-io, verification]
---

<!-- Issue #1533 (Scheibe S4 des Epics #1676) -- Generalprobe Premium-SMS am
     echten Garmin-inReach-Geraet, letzte Scheibe vor der KHW-Tour ab 20.8.
     Vorgaenger: S1 (feat_1676_s1_premium_sms_rueckkanal.md, live),
     S2a (feat_1676_s2a_premium_sms_versand.md, live). ADR-0049 legt den
     Kanalnamen `premium_sms` fest. -->

# Generalprobe Premium-SMS am Garmin inReach — S4

## Approval

- [ ] Approved

## Purpose

Diese Scheibe liefert den finalen Nachweis, dass das Trip-Briefing als
Premium-SMS zuverlässig auf dem echten Garmin-inReach-Gerät ankommt — die
letzte offene Bedingung vor der KHW-Tour (ab 2026-08-20). Sie trennt zwei
Dinge, die im Issue-Text vermischt waren: (a) Prüfungen, die **kostenlos**
und **ohne PO-Aktivierung** automatisiert laufen (Zeichenbudget, Zeichensatz,
ein GSM-7-Wächter für zwei bisher unbewachte SMS-Pfade), und (b) einen
**Live-Nachweis-Ablauf**, der den kostenpflichtigen Kanal voraussetzt und
ausdrücklich der PO-Entscheidung vorbehalten bleibt.

## Abgrenzung (nicht in dieser Scheibe)

- **Kanal-Aktivierung selbst** ist keine Code-Änderung dieser Scheibe —
  laut CLAUDE.md eine PO-Entscheidung, keine Session schaltet `premium_sms`
  eigenmächtig ein. Der Live-Nachweis-Ablauf (unten) beschreibt, WANN und
  WIE aktiviert wird — er aktiviert nicht selbst.
- **#1702 (Kostenstelle)** — eigenes Feature ohne Vorbild, separates Issue.
- **#1717/S3 (Oberfläche)** — bereits geschlossen.
- **`journal/outbound`-Abrufer / persistente Latenz-Messinfrastruktur** —
  bewusst NICHT gebaut. Als „gut genug" gilt der Soll-Ist-Vergleich aus
  Anwendungslog (`seven_io_base.py:185-187`) und PO-Ablesung am Gerät (s.
  AC-7). Eine Session, die hier trotzdem einen `journal/outbound`-Poller
  baut, überdimensioniert die Scheibe.
- **Native Garmin-Integration (#18)** — bleibt deferred.
- **Fix des in dieser Spec dokumentierten GSM-7-Fundes** — die RED-Phase hat
  den Fund bestätigt (echter Bug, kein falscher Alarm, s. unten). PO-
  Entscheidung 2026-08-12: **eigenes Issue #1796**, nicht in dieser Scheibe
  fixen. AC-3 ist deshalb **aus dieser Scheibe entfernt** (s. „Fund während
  der Spec-Erstellung").

## Fund während der Spec-Erstellung (bitte bei der Freigabe lesen)

Zwei Annahmen aus dem Kontextdokument mussten beim Schreiben dieser Spec
korrigiert werden — beide am Code nachvollzogen, **keine davon per Testlauf
bestätigt** (das ist Aufgabe der RED-Phase):

1. **Das SMS-Token `C+`/`C~`/`C?` (Sicherheits-Symbol, `sms_format.md`
   §3.4b, seit v2.1) wird im Trip-Briefing-Pfad nicht erzeugt.**
   `sms_trip.py:428-430,466` berechnet `day_confidence` und legt es in
   `DailyForecast.confidence_pct_min` ab — `build_token_line()`
   (`output/tokens/builder.py`, komplett gelesen für diese Spec) liest
   dieses Feld an keiner Stelle. Kein `"C"`-Symbol wird je gebaut;
   `channel_layout.py:66` trägt eine Prioritätsgewichtung für ein Token, das
   nie entsteht. Punkt 3 des Original-Issues („Zeichensatz: SMS-Token
   unverstümmelt") kann sich für den Trip-Pfad deshalb **nicht** auf dieses
   Token beziehen — es gibt nichts zu verstümmeln, weil nichts entsteht.
   AC-1 unten prüft deshalb bewusst die Token, die tatsächlich gebaut
   werden, nicht `C+/C~/C?`. Diese Lücke zwischen Doku (`sms_format.md`)
   und Code ist ein eigenständiger Befund — ob dafür ein Issue entsteht,
   ist eine PO-Entscheidung, nicht Teil dieser Scheibe.
2. **`sms_prefix = trip.name.replace(" ", "")` (notification_service.py:873,
   892, 911) ist vor `render_official_alert_sms()` nicht vollständig
   GSM-7-sicher.** `_ascii()` (`alert/render.py:701-706`) ersetzt nur vier
   feste Zeichen (`–`, `−`, `°`, `↑`/`↓`) und faltet danach über
   `fold_ascii()` — das transliteriert ausschließlich **Buchstaben**
   (`unicodedata.category()` in Ll/Lu/Lt/Lo/Lm). Zeichen der GSM-7-
   Extension-Tabelle (`^{}[]~|\€`, s. `_GSM7_EXTENDED_TWO_SEPTET_CHARS` in
   `test_compare_sms_gsm7_charset.py`) sind bereits ASCII und keine
   „Buchstaben" — sie durchlaufen `_ascii()`/`fold_ascii()` unverändert. Ein
   Trip-Name wie `"KHW [Test]"` oder `"Tour~Nord"` würde das eckige-Klammer-
   bzw. Tilde-Zeichen unverändert in den amtlichen-Alarm-SMS-Text tragen —
   dieselbe Fehlerklasse wie der historische `°`-Fund im Compare-Pfad
   (Segment-Kosten-Verdopplung), nur über den Trip-Namen statt über einen
   Metrik-Wert eingeschleust. **Anders als bei Compare-Ortsnamen ist das
   hier keine bewusst akzeptierte Freitext-Ausnahme** — der Code versucht
   an dieser Stelle aktiv, den Namen budget-sicher zu machen (Umlaute werden
   gefaltet, s. Kommentar `official_alerts.py:1890-1892`), trifft dieses
   eigene Ziel bei Extension-Zeichen nur nicht vollständig.
   **BESTÄTIGT in der RED-Phase (2026-08-12):** der Test ging bei allen drei
   Parametrisierungen (`"KHW [Test]"`, `"Tour~Nord"`, `"Weg|Nord"`) rot —
   echter Fund, kein falscher Alarm. PO-Entscheidung 2026-08-12: **eigenes
   Issue #1796**, nicht in dieser Scheibe fixen. Der ursprüngliche AC-3-Test
   ist deshalb **aus dieser Scheibe entfernt** (Reproduktion + Messwerte
   sind vollständig in #1796 dokumentiert) — diese Spec liefert nur noch
   AC-1, AC-2, AC-4, AC-5.

## Source

- **File:** `tests/tdd/_gsm7_charset.py` (**NEU**, ~55 LoC) — geteilte
  GSM-7-Basisalphabet-Tabelle (GSM 03.38 / 3GPP TS 23.038, OHNE Extension-
  Tabelle) + `assert_gsm7_clean()`/`_first_non_gsm7_char()`, extrahiert aus
  `tests/tdd/test_compare_sms_gsm7_charset.py:82-141`. Naming-Konvention:
  führender Unterstrich = Test-Helfer, kein eigener pytest-Testfall (Vorbild
  `tests/tdd/_hiking_window_fixtures.py`).
- **File:** `tests/tdd/test_trip_sms_gsm7_charset.py` (**NEU**, ~100-120
  LoC) — Pendant zu `test_compare_sms_gsm7_charset.py` für die zwei bisher
  unbewachten SMS-Pfade: Trip-Briefing (`sms_trip.py`) und amtlicher Alarm
  (`official_alerts.py::render_official_alert_sms`). Importiert die
  Zeichensatz-Prüfung aus `_gsm7_charset.py` statt sie erneut zu definieren
  (vermeidet die „zwei grüne Testfamilien, verschiedene Definitionen"-Falle).
  Enthält NUR noch AC-1 (Trip-Briefing) und AC-2 (amtlicher Alarm,
  Regressionsschutz) — der ursprüngliche AC-3-Test (GSM-7-Extension-Zeichen
  im Trip-Namen) ist entfernt und nach #1796 verschoben (s. „Fund während
  der Spec-Erstellung").
- **File:** `scripts/premium_sms_preflight_check.py` (**NEU**, ~55-70 LoC)
  — Vorab-Check-Skript für den Live-Nachweis-Ablauf: ruft
  `PreviewService.render_sms_preview(trip_id, user_id=..., report_type=...)`
  (`src/services/preview_service.py:325-348`) für `"morning"` UND
  `"evening"` gegen die reale KHW-Trip-Konfiguration auf und meldet je
  Report-Typ Zeichenlänge (≤160) und GSM-7-Konformität — kein Realversand,
  kein SMS-Kosten-Risiko, nur der bestehende Preview-Pfad. Trennt die reine
  Prüflogik (`_check_sms_text(text) -> list[str]`) von der CLI-Verdrahtung,
  damit Erstere deterministisch testbar ist (s. AC-4).
- **File:** `tests/unit/test_premium_sms_preflight_check.py` (**NEU**, ~50
  LoC) — Kern-Schicht-Test für `scripts/premium_sms_preflight_check.py`:
  Prüflogik (AC-4) und Verdrahtung gegen `PreviewService` mit `demo=True`
  (AC-5), deterministisch, kein Netz.
- **File:** `docs/runbooks/premium_sms_generalprobe.md` (**NEU**, Doku,
  zählt nicht gegen das LoC-Limit) — der minutengenaue Live-Nachweis-Ablauf
  für die vier PO-Aktivierungs-Punkte (AC-6 bis AC-9). Format analog
  `docs/runbooks/telegram-webhook.md`.
- **Keine Änderung** an `src/output/renderers/sms_trip.py`,
  `src/output/renderers/alert/official_alerts.py` oder
  `src/output/renderers/comparison.py` — diese Scheibe fügt ausschließlich
  Test-/Skript-Dateien hinzu. `renderer_mail_gate.py` (#811) greift deshalb
  nicht (es blockt nur, wenn eine Renderer-Datei selbst gestaged wird);
  `briefing_mail_validator.py` ist für diese Scheibe nicht Voraussetzung.

## Estimated Scope

- **LoC (geschätzt):** ≈ 55 (`_gsm7_charset.py`) + 110 (Trip/Alarm-GSM7-
  Test) + 65 (Preflight-Skript) + 50 (Preflight-Test) ≈ **280 LoC**.
  **Korrektur der ursprünglichen Annahme „< 100 LoC":** die Schätzung im
  Auftrag ging von einem einzelnen kleinen Test aus; tatsächlich sind es
  vier neue Dateien (zwei Test-Pendants zum Compare-Guard, ein Skript samt
  eigenem deterministischen Test für dessen Verdrahtung). Wird bei der
  Freigabe voraussichtlich einen `loc_limit_override` brauchen. Der
  Runbook-Text (Doku) zählt nicht mit.
- **Files:** 5 CREATE (2 Test-Helfer/Test, 1 Skript, 1 Skript-Test, 1
  Runbook), 0 MODIFY an Produktivcode.
- **Effort:** low-medium (kein Produktivcode-Risiko, reine Test-/Skript-
  Ergänzung — aber der Fund oben kann die Effort-Einschätzung ändern, falls
  die Freigabe einen Fix in derselben Scheibe verlangt).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` | Vorgänger-Spec | D5: `report.sms_text` ist der einzige Versandtext (Grundlage für den Vorab-Check-Ansatz) |
| `tests/tdd/test_compare_sms_gsm7_charset.py` | Vorbild, Quelle der Extraktion | GSM-7-Basisalphabet + Extension-Tabellen-Ausschluss, `assert_gsm7_clean()` |
| `src/services/preview_service.py::render_sms_preview` | module | einziger geprüfter Vorschau-Pfad für `report.sms_text`, inkl. `demo=True` (FixtureProvider, kein Netz) |
| `src/output/renderers/sms_trip.py::SMSTripFormatter.format_sms` | module | Trip-Briefing-SMS-Renderer, bisher unbewachter Pfad |
| `src/output/renderers/alert/official_alerts.py::render_official_alert_sms` | module | amtlicher-Alarm-SMS-Renderer, bisher unbewachter Pfad |
| `src/output/tokens/builder.py::build_token_line` | module | vollständig gelesen für den Fund „C-Token nie emittiert" — Grundlage für AC-1s Scope |
| `internal/scheduler/scheduler.go` (`trip_reports_hourly`) | module | Job-`last_run` als ein Messpunkt für AC-6 |
| `src/output/channels/seven_io_base.py:185-187` | module | `logger.info`-Zeitstempel als Latenz-Messpunkt für AC-7 |
| `api/routers/debug.py::trigger_radar_alert` | Vorbild | Muster für einen möglichen Debug-Trigger (AC-8, Option i) |

## Implementation Details

### GSM-7-Wächter (AC-1 bis AC-3)

`_gsm7_charset.py` exportiert exakt dieselbe Definition wie der Compare-
Guard (Basisalphabet ohne Extension-Tabelle — Extension-Zeichen zählen als
Verstoß, obwohl technisch GSM-7-kodierbar, weil sie die 1-Septet-Budget-
Annahme verletzen). `test_trip_sms_gsm7_charset.py` deckt:

- **AC-1** (Trip-Briefing): ein Tages-Fixture mit möglichst vielen
  gleichzeitig aktiven Token (`N`,`K`,`D`,`R`,`PR`,`W`,`G`,`TH:`+Hagel-
  Suffix,`TH+:`,`W?`,Vigilance/Fire/Wintersport-Block wo zutreffend) über
  `SMSTripFormatter().format_sms(...)`, geprüft mit `assert_gsm7_clean`.
- **AC-2** (amtlicher Alarm, Regressionsschutz): `render_official_alert_sms`
  über alle neun `HAZARD_SMS_SYMBOLS`, uniforme UND gemischte Warnstufen,
  mit einem Trip-Namen, der Umlaute trägt (`"Höhenweg"` — bereits bekannt
  sicher, s. Kontextdokument) — Regressionsschutz, kein neuer Fund erwartet.
- **AC-3** (amtlicher Alarm, gezielter Fund-Test): derselbe Aufruf mit
  einem Trip-Namen, der ein GSM-7-Extension-Zeichen trägt (z. B.
  `"KHW [Test]"`), gegen `assert_gsm7_clean`. Erwartungsoffen — s. „Fund
  während der Spec-Erstellung".

Konstruktion der `OfficialAlertNotice`-Fixtures direkt als Dataclass-
Instanzen (`alert=`, `scope_label=`, `sms_scope=`), analog zum Aufbau in
`test_compare_sms_gsm7_charset.py` — kein Mock, echte Objekte.

### Preflight-Skript (AC-4, AC-5)

```
def _check_sms_text(text: str, *, max_chars: int = 160) -> list[str]:
    # liefert Verstoss-Beschreibungen: Laenge > max_chars, erster
    # GSM-7-fremder Fund (assert_gsm7_clean-Logik, non-raising Variante)
    ...

def run(trip_id: str, user_id: str, *, demo: bool = False) -> int:
    # ruft render_sms_preview() fuer "morning" und "evening", druckt
    # Laenge + Befund je Report-Typ, gibt 0 zurueck wenn beide sauber sind
```

`run()` ist die injizierbare Kernfunktion (kein `Mock()`/`patch()` nötig);
AC-5 ruft sie direkt mit `demo=True` gegen ein per `_isolate_data_root`
(Vorbild `tests/tdd/test_epic_140_preview_endpoints.py:19-49`) isoliertes,
geseedetes Trip-Fixture — deterministisch, kein Netz, kein SMS-Versand.

## Expected Behavior

- **Input (Kern-Schicht):** deterministische Fixtures (Tages-Aggregate,
  amtliche Warnungen, Trip-Namen) — kein Netz, kein Realversand.
- **Input (Live-Nachweis):** vom PO befristet aktivierter `premium_sms`-
  Kanal + reale KHW-Trip-Konfiguration + Garmin-Gerät.
- **Output:** grüne Kern-Schicht-Tests als automatisierter Nachweis für
  Zeichenbudget/Zeichensatz; ausgefüllte Checkliste im Runbook als Nachweis
  für die vier verbleibenden Live-Punkte.
- **Side effects:** keine — reine Test-/Skript-Ergänzung, keine
  Produktivpfad-Änderung, keine neue Persistenz.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Briefing-Tagesfixture mit möglichst vielen
  gleichzeitig aktiven SMS-Token (Temperatur, Niederschlag, Wind, Gewitter
  inkl. Hagel-Suffix, Folgetag-Gewitter, Nicht-abrufbar-Marker) / When
  `SMSTripFormatter().format_sms(...)` den Text rendert / Then ist der Text
  vollständig GSM-7-rein nach der strikten Basisalphabet-Definition
  (Extension-Tabelle zählt als Verstoß).
  - Prüfort: der von `format_sms()` tatsächlich zurückgegebene String,
    NICHT einzelne Token-Bausteine.
  - Test: `tests/tdd/test_trip_sms_gsm7_charset.py::test_trip_briefing_sms_stays_gsm7_clean_with_dense_token_line`

- **AC-2:** Given ein amtlicher Alarm mit jeder Katalog-Gefahr aus
  `HAZARD_SMS_SYMBOLS` (RED-Phase-Korrektur: **zehn** Einträge, nicht neun
  wie ursprünglich hier geschätzt — der Test iteriert programmatisch über
  den Katalog statt eine Zahl festzuschreiben, deckt damit auch künftige
  Erweiterungen automatisch ab), sowohl uniformer als auch gemischter
  Warnstufe, und einem Trip-Namen mit Umlauten (`"Höhenweg"`) / When
  `render_official_alert_sms(...)` den Text rendert / Then ist der Text
  für jede Gefahr und jede Stufen-Kombination GSM-7-rein.
  - Prüfort: der zurückgegebene String je Gefahr/Stufen-Kombination.
  - Test: `tests/tdd/test_trip_sms_gsm7_charset.py::test_official_alert_sms_stays_gsm7_clean_for_every_hazard_and_umlaut_trip_name`

- **AC-3:** ENTFERNT (RED-Phase 2026-08-12) — prüfte GSM-7-Extension-Zeichen
  im Trip-Namen, ging bei allen drei Parametrisierungen rot (echter Fund,
  s. „Fund während der Spec-Erstellung" Punkt 2). PO-Entscheidung: eigenes
  Issue **#1796**, Test + Fix wandern dorthin, nicht Teil dieser Scheibe.

- **AC-4:** Given die Prüflogik `_check_sms_text()` des Preflight-Skripts /
  When sie mit vier synthetischen Texten aufgerufen wird (sauber, > 160
  Zeichen, enthält `°`, enthält ein Extension-Zeichen) / Then meldet sie
  für die ersten Fall keine Verstöße und für die drei übrigen jeweils
  mindestens einen treffenden Verstoß (Länge bzw. Zeichensatz).
  - Prüfort: Rückgabewert von `_check_sms_text()` direkt, kein Skript-Lauf.
  - Test: `tests/unit/test_premium_sms_preflight_check.py::test_check_sms_text_flags_length_and_charset_violations`

- **AC-5:** Given ein per `_isolate_data_root` isoliertes, geseedetes
  Trip-Fixture / When `run(trip_id, user_id, demo=True)` aufgerufen wird /
  Then wird `PreviewService.render_sms_preview()` für **beide**
  Report-Typen (`"morning"` und `"evening"`) aufgerufen, und die Rückgabe
  enthält für jeden Report-Typ eine Länge- und Zeichensatz-Bewertung.
  - Prüfort: der Rückgabewert von `run()` bzw. eine injizierte
    Aufruf-Zählung, nicht nur „kein Fehler geworfen".
  - Test: `tests/unit/test_premium_sms_preflight_check.py::test_run_checks_both_morning_and_evening_via_preview_service`

- **AC-6:** (Live-Nachweis, PO-Aktivierung vorausgesetzt) Given der
  `premium_sms`-Kanal ist vom PO befristet aktiviert UND der reale KHW-Trip
  hat `send_premium_sms=true` / When der Go-Scheduler-Job
  `trip_reports_hourly` regulär läuft (nicht Handauslösung) / Then zeigt
  `last_run` im Status-Endpoint einen erfolgreichen Lauf UND der PO
  bestätigt am Gerät den Empfang der Nachricht — Status-Endpoint ALLEIN
  beweist nur „Job lief", nicht „SMS kam an".
  - Prüfort: `GET /api/scheduler/status` (`last_run` von
    `trip_reports_hourly`) kombiniert mit Geräte-Ablesung durch den PO.
  - Test: manuell, Runbook-Schritt (kein automatisierter Test möglich —
    setzt echten Kanal-Versand voraus).

- **AC-7:** (Live-Nachweis) Given ein Scheduler-getriebener Premium-SMS-
  Versand (AC-6) wurde ausgelöst / When der PO die Empfangszeit am Gerät
  abliest / Then liegt zwischen dem `logger.info`-Zeitstempel
  (`seven_io_base.py:185-187`) und der abgelesenen Empfangszeit eine
  plausible, im Runbook dokumentierte Zeitspanne — kein exakter
  Millisekunden-Vergleich, kein `journal/outbound`-Abruf nötig.
  - Prüfort: Anwendungslog-Zeitstempel vs. PO-Notiz im Runbook.
  - Test: manuell, Runbook-Schritt.

- **AC-8:** (Live-Nachweis, PO-Wahl zwischen zwei Optionen) Given es gibt
  aktuell keinen Debug-Trigger für Änderungs-/amtliche Alarme über
  Premium-SMS (nur `/api/debug/trigger-radar-alert`, und der sendet nur
  per Mail) / When der Alarm-Pfad am Gerät nachgewiesen werden soll / Then
  entscheidet der PO zwischen (i) einem kleinen, analog zu
  `trigger-radar-alert` gebauten Debug-Trigger für amtliche/Änderungs-
  Alarme über `premium_sms`, ODER (ii) manuellem Herabsetzen einer
  Alarmschwelle am echten KHW-Trip während des Testfensters, damit ein
  echter (kleiner) Alarm natürlich auslöst — und das Gerät zeigt danach
  den Alarmtext lesbar an.
  - Prüfort: Geräte-Ablesung durch den PO, Option im Runbook dokumentiert.
  - Test: manuell, Runbook-Schritt — Umsetzung von Option (i) wäre ein
    eigener kleiner Implementierungsschritt, kein automatisierter Test.

- **AC-9:** (Live-Nachweis) Given eine Premium-SMS ist auf dem Garmin-
  Gerät angekommen (AC-6 oder AC-8) / When der PO sie auf dem Display
  liest / Then sind Zeilenumbrüche und Reihenfolge nachvollziehbar lesbar
  — reine Beobachtung, per Foto/Beschreibung im Runbook festgehalten.
  - Prüfort: PO-Beobachtung am physischen Gerät.
  - Test: manuell, Runbook-Schritt, kein Code.

## Known Limitations

- **AC-3 (GSM-7-Extension-Zeichen im Trip-Namen) ist NICHT Teil dieser
  Scheibe** — die RED-Phase hat den Fund bestätigt (echter Bug, alle drei
  Parametrisierungen rot). PO-Entscheidung 2026-08-12: eigenes Issue
  **#1796** statt Fix in S4. Der Bug bleibt bis zur Bearbeitung von #1796
  bestehen — betrifft Trips, deren Name ein GSM-7-Extension-Zeichen
  (`^{}[]~|\€`) enthält.
- **Der C-Token-Befund (Fund 1 oben) wird von dieser Spec nicht behoben** —
  AC-1 prüft die Token, die tatsächlich existieren; ein SMS-seitiges
  Vertrauens-Symbol für niedrige Vorhersagesicherheit fehlt dem Nutzer
  damit weiterhin, unabhängig vom Ausgang dieser Scheibe.
- **Kein `journal/outbound`-Abruf** — Latenzmessung (AC-7) bleibt grob
  (Log-Zeitstempel vs. PO-Ablesung), keine maschinenlesbare Zustellbestätigung.
  Bewusste Entscheidung gegen Überdimensionierung dieser Scheibe.
- **AC-6/AC-7/AC-8/AC-9 sind nicht automatisierbar** — sie hängen an einer
  vom PO befristet aktivierten, kostenpflichtigen Infrastruktur (Garmin-
  Gerät, seven.io-Realversand). Das Runbook bündelt sie in möglichst wenige
  Aktivierungsfenster, ersetzt aber keinen automatisierten Test.
- **AC-8 Option (i)** (neuer Debug-Trigger) ist in dieser Spec nur als
  Option beschrieben, nicht spezifiziert — falls der PO sich dafür
  entscheidet, braucht das einen eigenen kleinen Implementierungsschritt
  vor dem Live-Fenster.
- **`friendly_label`-Token (konfigurierbare Metrik-Kurzform,
  `builder.py` „Friendly-format companion tokens") wurde nicht auf
  GSM-7-Sicherheit geprüft** — außerhalb des in dieser Spec untersuchten
  Bereichs (Kern-Token + amtlicher Alarm), analog zur bewussten Abgrenzung
  des Compare-Guards auf renderer-eigenen Text.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Diese Scheibe ändert keine Architektur- oder
  Kanal-Entscheidung — sie ergänzt Tests/ein Vorab-Check-Skript und
  beschreibt einen Live-Nachweis-Ablauf für eine bereits in ADR-0049
  getroffene Entscheidung (Premium-SMS als vierter Kanal). Kein neues ADR
  nötig.

## Changelog

- 2026-08-12: Initial spec erstellt — Issue #1533, Scheibe S4 des Epics
  #1676. Enthält zwei bei der Spec-Erstellung am Code nachvollzogene,
  noch nicht testlauf-bestätigte Funde (C-Token nie emittiert;
  GSM-7-Extension-Zeichen in Trip-Namen ungefiltert vor
  `render_official_alert_sms`).
- 2026-08-12 (nach RED-Phase): AC-3 bestätigt (echter Fund, 3/3 rot),
  Fix per PO-Entscheidung nach **#1796** ausgelagert. AC-3 aus dieser
  Scheibe entfernt — Scope jetzt AC-1, AC-2, AC-4, AC-5. AC-2-Zahl der
  Katalog-Gefahren korrigiert (zehn statt neun, `HAZARD_SMS_SYMBOLS`).
