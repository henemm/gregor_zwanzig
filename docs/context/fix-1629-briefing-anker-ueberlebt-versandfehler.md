# Context: fix-1629-briefing-anker-ueberlebt-versandfehler

Issue: [#1629](https://github.com/henemm/gregor_zwanzig/issues/1629) · Track: **Full Process** · Phase 1 (Context)
Erstellt: 2026-08-09

## Request Summary

Der Abweichungs-Alarm (`reason=forecast_change`) eines live laufenden Trips fiel am 2026-08-08 **einen
ganzen Tag** aus, weil der datierte Wetter-Snapshot dieses Tages fehlte. Sichtbar war ausschließlich
eine WARNING-Logzeile alle 15 Minuten. Zu klären ist, warum der Snapshot fehlte, warum der Ausfall
unsichtbar blieb, und was daran struktureller Natur ist.

## Gemessener Befund (Prod, nicht hergeleitet)

Die im Issue offen gelassene Frage („Warum der Morgen-Snapshot heute fehlt, ist NICHT geklärt") ist
beantwortet. Das Morgen-Briefing des 08.08. ist nicht ausgefallen, sondern **mitten im Lauf
abgebrochen**:

```
Aug 08 05:00:46 gregor-python: ERROR dispatch_orchestrator:
  Failed morning report for 5f534011: [email] 1 Empfänger nicht in der
  Resend-Allowlist bei Host 'smtp.resend.com' — Versand blockiert (Issue #1147/#1219)
Aug 08 05:00:46 gregor-api: [scheduler] trip_reports_hourly: user henning failed:
  ... reported 1 failed (status=partial, count=0)
Aug 08 05:00:46 gregor-api: [notify] CLAUDE_MQ_SECRET unset, skipping MQ send
  (subject="Trip-Briefing-Totalausfall (#1346)")
```

Dateilage in Prod (`/var/lib/gregor/users/henning/weather_snapshots/`, Stand 2026-08-09):
`…_2026-08-03` … `…_2026-08-07` vorhanden, **`…_2026-08-08` fehlt**, `…_2026-08-09` (heute 05:00)
und `…_2026-08-10` (gestern 16:00) vorhanden. Genau ein Tag Lücke, deckungsgleich mit dem
abgebrochenen Briefing.

### Häufigkeit der Warnzeile (gesamte Journal-Aufbewahrung, `gregor-python.service`)

| Zeitraum | „No fresh weather data" |
|---|---|
| 2026-06-21 – 2026-07-10 | 46–203 Treffer **täglich, lückenlos** |
| 2026-07-22 / 07-26 | 2 / 1 |
| 2026-08-07 / 08-08 | 25 / 53 (beide `5f534011`) |

Rund 1 350 Treffer. Die Zeile ist damit kein Ausnahmesignal, sondern Dauerrauschen — sie kann
strukturell niemandem auffallen.

## Ursachenkette (an jeder Station belegt)

1. `trip_report_scheduler.py:958` `send_trip_report(request)` — **kein try/except**.
2. Der Resend-Allowlist-Guard wirft dort `OutputConfigError` (`src/output/channels/email.py:678-731`).
3. Die Ausnahme fliegt bis `dispatch_orchestrator.py:66-79` hoch. Alles dazwischen entfällt.
4. Damit entfällt insbesondere `trip_report_scheduler.py:1046` `write_anchor_and_reset_memory(...)`
   → **kein datierter Snapshot** (`save_dated`), kein undatierter (`save`), kein Melde-Reset.
5. Am Folgetag lädt `trip_alert.py:505` `load_dated(trip.id, today)` → `None`, fällt auf
   `svc.load(trip.id)` zurück (Zeile 509). Diese Datei trug bis 16:28 den Stand vom 07.08.,
   danach den vom 09.08.
6. `_fetch_fresh_weather` (`trip_alert.py:1007-1010`) filtert: `end_time < now_utc` → weg;
   `start_time.date() > today_utc` → weg. In **beiden** Fällen fällt alles weg → `[]`.
7. `trip_alert.py:237` `logger.warning("No fresh weather data for trip …")`, `return False`.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_report_scheduler.py:958` | ungeschützter Versandaufruf — Bruchstelle |
| `src/services/trip_report_scheduler.py:1030-1056` | `_write_briefing_anchor` + Aufruf, wird übersprungen |
| `src/services/trip_report_scheduler.py:986-996` | `_append_briefing_log` nur im `else`-Zweig (`result.sent`) |
| `src/services/alert_briefing_anchor.py:114-170` | `write_anchor_and_reset_memory` — geteilter Baustein, Reihenfolge: Zeitstempel → Anker → Gedächtnis-Reset |
| `src/services/scheduler_dispatch_service.py:401 / 423-435` | **Ortsvergleich hat dieselbe Bruchstelle** (Versand ungeschützt vor Anker) |
| `src/services/weather_snapshot.py:61-198` | `save`/`save_dated`/`load`/`load_dated`, alle fail-soft |
| `src/services/trip_alert.py:484-512` | `_get_cached_weather` — Rückfall auf undatiert **ohne Datumsprüfung** |
| `src/services/trip_alert.py:1004-1036` | Zeitfilter, Rückgabe `[]` ununterscheidbar von Erfolg |
| `src/services/trip_alert.py:233-238` | Warnstelle, kein Unterschied „Snapshot fehlt" ↔ „Segmente zeitlich raus" |
| `src/services/compare_alert.py:359` | Compare lädt **nur** `load()`, kein `load_dated` — der #823-Schutz fehlt hier ganz |
| `src/output/channels/email.py:678-731` | wirft `OutputConfigError` (Allowlist-Guard #1147/#1219) |
| `src/services/notification_service.py:275 / 798-873` | `send_trip_report` / `send_compare_report` propagieren E-Mail-Ausnahmen; Telegram/SMS fail-soft, aber `OutputConfigError` wird re-raised |
| `internal/scheduler/scheduler.go:285-300` | #1346-Benachrichtigung, **edge-triggered** (nur `ok`→`error`) |
| `internal/notify/mq.go:35-39` | ohne `CLAUDE_MQ_SECRET` → `return nil`, schweigend |
| `internal/scheduler/briefing_health.go:139-148` | vorhandene Health-Felder am Status-Endpunkt |
| `internal/scheduler/warn_service_health.go:262-309` | zweites Aggregat-Muster, generisch nach Dienstnamen |

## Existing Patterns

- **ADR-0018 Punkt 3** (`docs/adr/0018-provider-fallback-ohne-kaschieren.md:17`): ein persistenter
  Ausfall muss ein **mit der Ausfalldauer wachsendes** Signal erzeugen — Vorbildfelder
  `provider_error_streak_since`, `provider_errors_recent_count`, `last_provider_error_at`.
- **Aggregat statt Einzelmeldung:** `briefing_health.go` und `warn_service_health.go` lesen
  Journal-Dateien unter der Datenwurzel und hängen generisch am Status-Endpunkt. Ein neues Signal
  in dieser Bauart kostet null bis wenige Go-Zeilen.
- **#1628 als Blaupause und als Warnung:** `NowcastResult.data_unavailable`
  (`radar_service.py:79-98, 586-590`) unterscheidet „Ausfall" von „nichts zu melden" — und hat genau
  **einen** Leser im Produktivcode (`format_now_text()`, `:254`). Vorgänger `throttled` hatte null
  Leser. Ein Signal ohne Leser versandet.
- **Fail-soft-Konvention der Persistenz:** `WeatherSnapshotService` und
  `CompareWeatherSnapshotService` schlucken Schreib-/Lesefehler und loggen nur. Der Anker-Aufruf
  selbst ist dagegen **nicht** gegen eine vorgelagerte Ausnahme geschützt.
- **Geteilter Baustein (#1467 S2 AG5):** Anker + Melde-Reset laufen für Trip **und** Ortsvergleich
  durch dieselbe Funktion. Jede Änderung dort wirkt beidseitig — das ist gewollt und zugleich der
  Grund für den hohen Blast Radius.

## Dependencies

- **Upstream:** `NotificationService` → Kanal-Ausgaben (`email.py` Allowlist-Guard), `WeatherSnapshotService`,
  `AlertStateService`, `get_data_dir()` (Datenwurzel aus systemd-Env, #1595/#1633).
- **Downstream:** Abweichungs-Alarm (`trip_alert.check_and_send_alerts`), Compare-Alarm
  (`compare_alert.py`), Cockpit-Kachel #393 und Briefing-Historie (lesen `briefing_log.json` über
  `internal/store/log.go:23-27`), NowCast-Vergleich gegen Briefing (`trip_alert.py:828-829`).

## Existing Specs

| Pfad | Inhalt |
|---|---|
| `docs/specs/modules/weather_snapshot.md` | Zweck des Snapshots, `target_date`-Feld |
| `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` | Anker + Gedächtnis an **einer** Bedingung, geteilt mit Compare |
| `docs/specs/modules/fix_1628_nowcast_datenluecke.md` | „Ausfall ≠ nichts zu melden" — nächstverwandte Spec |
| `docs/specs/modules/feat_1461_s3b1_briefing_sichtbarkeit.md` | Briefing zeigt nicht erreichte Alarme |
| `docs/adr/0018-provider-fallback-ohne-kaschieren.md` | Nicht-Kaschieren-Invariante |

## Risks & Considerations

- **Offene Produktfrage (PO, Phase 3):** Der Anker ist laut Vision „das letzte Briefing, das der
  Nutzer im Kopf hat". Kam die Mail nie an, hat er nichts im Kopf — ein Anker wäre eine Fiktion.
  Der Preis für „kein Anker" war hier aber ein kompletter Tag ohne Abweichungs-Alarme. Beide
  Antworten sind vertretbar; die Entscheidung gehört in die ACs, nicht in die Analyse.
- **Nebenwirkung Melde-Gedächtnis:** `write_anchor_and_reset_memory` setzt auch den Melde-Reset. Den
  Anker nach einem Versandfehler zu schreiben, würde ohne Trennung auch das Gedächtnis
  zurücksetzen — mit Spam-Risiko. Anker und Reset hängen bewusst an **einer** Bedingung (#1467 S2 AG5).
- **Beidseitige Wirkung:** Jede Änderung an dieser Funktion oder an ihrer Aufrufstelle betrifft Trip
  **und** Ortsvergleich. Der Compare-Pfad hat dieselbe Bruchstelle und zusätzlich gar keinen
  Datums-Schutz beim Laden.
- **Doppelte Sichtbarkeitslücke:** Der Totalausfall hatte einen gebauten Melder (#1346), der wegen
  fehlendem `CLAUDE_MQ_SECRET` schweigend aussteigt — und er ist edge-triggered, meldet also nur den
  Übergang, nicht die Dauer. Das ist eine Konfigurations-/Infra-Frage, kein Python-Defekt; ob sie in
  diesen Workflow gehört, ist zu entscheiden.
- **Signal ohne Leser:** Wird ein neues „Snapshot fehlt"-Merkmal eingeführt, muss im selben Zug ein
  Leser existieren, sonst wiederholt sich das `throttled`-Muster.
- **Rauschen statt Signal:** ~1 350 identische WARNING-Zeilen über die Aufbewahrungsdauer. Eine
  weitere Logzeile ist keine Abhilfe.
- **Nicht in diesem Kontext geklärt:** ob die Warnzeile im Juni/Juli denselben Ursprung hatte
  (anderer Trip, evtl. legitimes „Trip vorbei") — für die Ursachenkette des 08.08. irrelevant,
  für die Bewertung der Signalgüte aber offen.

---

# Analysis (Phase 2)

## Type

**Bug.** Kein Feature-Anteil. Ursachenkette am Code bestätigt, eine Gegenthese durch Messung
ausgeschlossen.

## Gegenprüfung (analysis-challenger) — Ergebnis

| Prüfpunkt | Verdikt | Beleg |
|---|---|---|
| Kein `try/except` zwischen Versand (`:958`) und Anker (`:1046`) | **BESTÄTIGT** | `trip_report_scheduler.py:698-1066` eine Einrückungsebene; Docstring `:724` sagt ausdrücklich „Raises: … if email send fails" |
| `OutputConfigError` wird unterwegs nicht gefangen | **BESTÄTIGT** | `notification_service.py:354-356` ohne `try` — im Gegensatz zu SMS `:361-368` und Telegram `:378-390`, die beide fangen |
| Zweiter Weg hätte den Snapshot schreiben können | **WIDERLEGT** | On-Demand steigt aus (`alert_briefing_anchor.py:151`), Abend-Briefing schreibt `target_date=morgen` (`trip_report_scheduler.py:536-540`), Nachhol-Marker liegt hinter der Bruchstelle (`:1001-1005`) |
| Gegenthese „Open-Meteo war den Tag über tot" | **WIDERLEGT (gemessen)** | `Failed to fetch fresh weather for segment` (`trip_alert.py:1031`) am 08.08. **0-mal** im Journal bei 53 Warnungen ⇒ die Abrufschleife wurde nie betreten ⇒ Zeitfilter, nicht Provider |
| Kette ist der einzige mögliche Verlauf | **PRÄZISIERT** | Zweites, früheres Tor `trip_alert.py:434-437` (`if not cached: continue`) — wäre auch die undatierte Datei weg gewesen, wäre der Trip **völlig lautlos** übersprungen worden |

## Der entscheidende Befund

**Ein nicht zugestelltes Briefing schreibt den Anker heute bereits.** Bei
`result.sent == False` (Kanal konfiguriert, aber unerreichbar — kein Ausnahmefall, nur ein
Ergebnisobjekt) steuert der Block `trip_report_scheduler.py:986-996` **ausschließlich** Logzeile und
`briefing_log`-Eintrag; `write_anchor_and_reset_memory` bei `:1046` läuft danach **bedingungslos**.
Der einzige Zweig, der ihn überspringt, ist eine **durchgereichte Ausnahme**.

Damit ist die im Intake aufgeworfene Produktfrage („darf ein nie zugestelltes Briefing einen Anker
setzen?") vom Bestand bereits beantwortet: **ja, tut es** — bewusst und getestet. Die Ausnahme-Lücke
ist keine Designentscheidung, sondern eine **Asymmetrie zwischen den Kanälen**: E-Mail wirft,
SMS/Telegram sind fail-soft.

Einziger ausdrücklich anders behandelter Fall: `record_official_alerts_reported` ist mit
`if result.sent and not on_demand` gesondert geschützt (`:1036`), bewacht von
`tests/tdd/test_alert_state_briefing_reset.py:846`. Dieser Test bleibt von der Kernänderung
unberührt.

## Affected Files (with changes)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_report_scheduler.py:958` | MODIFY | Versandaufruf in `try/except`; im `except` denselben Anker-Aufruf wie `:1046` ausführen, danach `raise` (Zählung/Logging in `dispatch_orchestrator.py:76-78` bleibt unverändert) |
| `src/services/scheduler_dispatch_service.py:401` | MODIFY | symmetrisch für den Ortsvergleich (Anker-Aufruf bei `:423`) |
| Diagnose-Schreiber (neu oder bestehendes Modul) | CREATE/MODIFY | fail-soft Eintrag `users/<uid>/diagnostics/briefing_dispatch_failures.json`, Muster `record_corrupt_trip_observability` |
| `internal/scheduler/briefing_health.go:139-148` | MODIFY | Feldpaar `briefing_dispatch_error_streak_since` + `briefing_dispatch_errors_recent_count`, Namensanalogie zu `provider_error_streak_since`/`provider_errors_recent_count` |
| Tests | CREATE | Ausnahmefall in `tests/tdd/test_trip_briefing_anchor_unchanged.py` + Compare-Pendant + Go-Test |

## Scope Assessment

- Dateien: 4 Produktivdateien + 3 Testdateien
- Geschätzte LoC: **~90 Produktivcode** (Limit 250)
- Risk Level: **MEDIUM** — geteilter Baustein, beidseitige Wirkung; aber die Änderung stellt eine
  bereits bestehende Semantik wieder her, statt eine neue einzuführen

## Technical Approach (Empfehlung)

**Ausnahme am Aufrufer fangen, Anker + Melde-Reset gebündelt lassen, danach `raise`.** In beiden
Pfaden (Trip und Ortsvergleich) symmetrisch.

Verworfene Alternativen:

- **Anker schreiben, Reset auslassen.** Erzeugt genau die Kombination, die der Docstring von
  `write_anchor_and_reset_memory` (`alert_briefing_anchor.py:7-14`) als gefährlichste bezeichnet:
  frischer Anker gegen altes Melde-Gedächtnis ⇒ eine reale Abweichung kann **dauerhaft** verschluckt
  werden, ohne Logzeile. Widerspricht zudem #1467 S2 AG5 („an EINER Bedingung"). Tauscht einen
  sichtbaren Ein-Tages-Ausfall gegen einen unsichtbaren Dauerausfall — schlechter Handel.
- **Nur die Leseseite härten** (Altersschutz auf den undatierten Rückfall). Löst den Kern-Defekt
  nicht: der Alarm bliebe an diesem Tag trotzdem stumm, nur mit ehrlicherer Begründung.

**Verbleibendes Risiko, ausdrücklich benannt:** Bei einer Fehlerserie wird das Melde-Gedächtnis je
Versuch neu geleert, was Wiederholungsmeldungen begünstigt. Dieses Muster existiert im heutigen
`result.sent == False`-Pfad bereits; die Änderung führt es nicht ein.

## Sichtbarkeit (ADR-0018)

Kein neues Journal, kein neuer Endpunkt. Der `except`-Zweig schreibt fail-soft einen
Diagnose-Eintrag; `BriefingHealth()` aggregiert ihn zu einem **mit der Ausfalldauer wachsenden**
Feldpaar am bestehenden `/api/scheduler/status`. Leser ist die BetterStack-Eskalationsleiter, die
für `provider_error_streak_since` bereits dieselbe Formel `now - streak_since` anwendet. Damit hat
das Signal von Anfang an einen Leser — anders als `NowcastResult.throttled` (null Leser) und
`data_unavailable` (ein Leser).

Der Blocker #1633 (gespaltene Datenwurzel) ist gemerged; Diagnose-Dateien liegen wieder unter der
überwachten Wurzel.

## Nicht in diesem Workflow (Folge-Issues)

1. **[#1661] Leseseite härten:** 26-h-Altersschutz für den undatierten Trip-Rückfall (`trip_alert.py:509`),
   analog zum bereits vorhandenen `compare_alert.py:49/388` `_MAX_ANCHOR_AGE`; dazu `load_dated` auf
   der Compare-Seite (`compare_alert.py:359`), die den #823-Schutz gar nicht kennt. Unabhängig
   testbar, eigene ACs.
2. **[#1662] Versandfehler nachliefern:** Der Nachhol-Mechanismus #1012 (`pending_briefings.json`,
   stündlicher Vorlauf `_process_pending_markers`, `trip_report_scheduler.py:337-409`) erfasst nur
   **Wetterdaten**-Fehler. Ein Versandfehler wird nie vorgemerkt ⇒ der Nutzer bekam am 08.08. gar
   kein Briefing und niemand hat es bemerkt. Eigenes, nutzersichtbares Problem.
3. **Rauschen der Warnzeile** (~1 350 Treffer): „Snapshot fehlt" ↔ „Segmente zeitlich raus"
   unterscheidbar machen (`trip_alert.py:233-238`), plus das stille Tor `:434-437`.
4. **#1346-Melder:** schweigt ohne `CLAUDE_MQ_SECRET` (`internal/notify/mq.go:39`) und ist
   edge-triggered. Infrastruktur-/Konfigurationsfrage, kein Python-Defekt.

## Open Questions

- [ ] Bestätigung in Phase 3, dass der Anker auch bei gescheitertem Versand geschrieben wird —
      der Bestand tut es bereits, die Änderung stellt nur Gleichbehandlung her.
- [ ] Gehört das Go-Health-Feldpaar in diesen Workflow (Empfehlung: ja, sonst Signal ohne Leser)?
