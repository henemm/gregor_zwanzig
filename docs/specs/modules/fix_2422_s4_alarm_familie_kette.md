---
entity_id: fix_2422_s4_alarm_familie_kette
type: bugfix
created: 2026-09-29
updated: 2026-09-29
status: draft
version: "1.0"
tags: [testing, alarm, radar, amtliche-warnungen, versand, kanaele, schwelle, fix]
workflow: fix-2422-s4-alarm-familie-kette
---

# Fix #2422 (Scheibe S4): Kette Alarm-Familie — Schwellen · Radar · Abweichung · Amtliche Warnungen — Tests + Fix

## Approval

- [ ] Approved

## Purpose

Issue #2422 lautet „Konfiguration und Auslieferung nicht getestet!". S1–S3 haben diese Kette für
**Trip-Briefings** geprüft (Metrik-Auswahl, Editor-Anzeige, Kanal an/aus, Slot-Schalter,
`email_format`, `sms_threshold`-Pillen). **Scheibe S4 prüft dieselbe Frage für die Alarm-Familie:**
Kanal-Auflösung + Schwellen (`alert_channels`, `alert_channel_thresholds`), Radar-Alarme,
Abweichungsalarme (Wetter-Delta-Regeln) und amtliche Warnungen — vom gespeicherten Trip-JSON bis
zur tatsächlichen Auslieferung über alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS).

**Zwei bestätigte Produktivfehler, nicht nur eine Testlücke:**

1. **Amtliche Warnungen werden trotz `official_warnings.enabled=true` nie ausgelöst, wenn das
   veraltete Feld `official_alert_triggers_enabled` zufällig auf `false` steht und keine aktive
   Wetter-Delta-Regel existiert.** Ein Vorab-Filter im Sammellauf (`trip_alert.py:895-911`) prüft
   nur das Legacy-Feld und überspringt den Trip komplett, **bevor** die korrekte Vorrangprüfung in
   `check_official_alert_triggers()` (`trip_alert.py:2554`, konkret `:2577-2587`) überhaupt erreicht
   wird. Das Frontend schreibt seit Issue #1258 nur noch `official_warnings.enabled`, nie mehr das
   Legacy-Feld — Altbestand bleibt auf seinem letzten historischen Wert stehen. Der Nutzer sieht im
   Editor „amtliche Warnungen: an", bekommt aber nie eine amtliche Alarm-Nachricht — exakt das
   Fehlerbild aus #2422 (Editor zeigt X, Auslieferung macht Y).
2. **SMS-Nichtparität bei gebündelten Abweichungsalarmen (#1088):** Der eingebettete amtliche
   Zusatzblock einer gebündelten Abweichungs-Alarm-Mail fehlt bewusst in der SMS
   (`notification_service.py:1706-1708`). Für diese Abweichung existiert **keine ADR** — eine
   unbelegte Code-Kommentar-Entscheidung ist keine ratifizierte Architekturentscheidung. Nach der
   aus S2 gewonnenen Regel „bekannte Abweichung wird im selben Ticket gefixt, nicht befristet ins
   Ausnahme-Register geschoben" und der PO-Korrektur vom 2026-09-05 („jeder Kanal muss jede Frage
   beantworten können", Epic #2133) ist das ein **Fixkandidat**: die SMS bekommt mindestens einen
   kurzen Hinweistext auf die amtliche Warnung, kein sang- und klangloses Weglassen.

**Scope-Entscheidung: nur Trip-Alarm-Pfad.** `ComparePreset.alert_channels` hat laut #2293 aktuell
kein stabiles Go-Feld/keine Migration (nur Roh-Dict-Zugriff) — eine Golden-Fixture-Kette für die
Schwellen-Auflösung am Compare-Datenmodell würde auf einem Datenmodell aufsetzen, das #2293 gerade
erst herstellt. Die Compare-Alarm-Kette (Radar + amtliche Warnungen am `ComparePreset`) wird als
**expliziter Folgepunkt im Sammel-Issue #1199** vermerkt, nicht stillschweigend fallen gelassen
(siehe „Known Limitations").

**Alle vier Kanäle sind gleichrangig.** Keine der drei Alarm-Arten behandelt einen Kanal als
nachrangig — die Kanal-Matrix wird für Abweichung, Radar und amtliche Warnungen mit demselben
Maßstab geprüft.

## Source

- **File (Python-Core, produktiv):**
  - `src/services/trip_alert.py:895-911` — Fix des Vorab-Filters im Sammellauf (muss
    `official_warnings.enabled` genauso berücksichtigen wie `:2577-2587` es tut)
  - `src/services/notification_service.py:1672-1946` (`_dispatch_alert_message`) bzw. der SMS-Renderer
    für Abweichungsalarme — Fix der SMS-Paritätslücke (#1088): mindestens ein Kurz-Hinweistext auf die
    amtliche Warnung bei gebündelten Abweichungsalarmen
- **File (Python-Core, nur gelesen, nicht geändert):** `src/app/trip.py:209-231` (Datenmodell),
  `src/app/loader.py:273-299,366,636-727,808-830,1702-1731` (Lesen/Migration), `src/app/models.py:1275`
  (`AlertRule.channels`), `src/services/alert_channels.py:29-213` (`resolve_alert_channels`,
  `effective_alert_channels`), `src/services/alert_channel_threshold.py:20-35` (`split_by_threshold`),
  `src/services/trip_alert.py:1588-1628,2261,2528,2554,2577-2587,2714,2799,2882-2914`,
  `src/services/notification_service.py:1058` (`send_official_alert`),
  `src/output/renderers/alert/{render,project,model,official_alerts}.py`
- **File (Test-Infrastruktur, erweitert):**
  - `tests/helpers/alarm_pruefstrecke.py` (#2050) — Loader-Adapter (Trip aus echter JSON-Datei über
    `app.loader.load_trip(...)` statt `Trip(...)` im Speicher) + der `official`-Zweig ruft künftig
    den öffentlichen Einstiegspunkt `check_official_alert_triggers()` statt der privaten
    `svc._send_official_alert_only(...)` auf
  - `tests/helpers/transport_mitschrift.py:47-108` (S1–S3-Muster, unverändert wiederverwendet)
  - `tests/helpers/einstellung_auslieferung_orakel.py` — Erweiterung um Alarm-Kanal-Erwartung
- **File (Test-Daten, neu):** `tests/fixtures/alarm_kette/golden_abweichung.json`,
  `tests/fixtures/alarm_kette/golden_radar.json`, `tests/fixtures/alarm_kette/golden_amtlich_fall1.json`,
  `tests/fixtures/alarm_kette/golden_amtlich_fall2_altdaten.json`,
  `tests/fixtures/alarm_kette/golden_amtlich_fall3_bug.json`
- **File (Test, neu):** `tests/tdd/test_alarm_abweichung_kette.py`, `tests/tdd/test_alarm_radar_kette.py`,
  `tests/tdd/test_alarm_amtliche_warnungen_kette.py`,
  `tests/tdd/test_alarm_sms_paritaet_amtlicher_zusatz.py`
- **Identifier:** `check_official_alert_triggers`, `_dispatch_alert_message`, `send_official_alert`,
  `resolve_alert_channels`, `effective_alert_channels`, `split_by_threshold`

> **Schicht-Hinweis:** S4 ist **ausschließlich Python-Core** (`src/services/`, Tests unter `tests/`).
> Kein Go-, kein Frontend-Code wird geändert — beide Editor-/Speicherwege für die betroffenen Felder
> sind laut Analyse bereits korrekt (`AlarmeTab.svelte`, `alarmeDeliveryPayload.ts`) und bereits an
> anderer Stelle getestet (`internal/handler/trip_alert_channel_thresholds_test.go`,
> `frontend/.../alertChannelThresholds.test.ts`). S4 schließt die Lücke **dahinter**: geladenes
> Trip-Objekt → Alarm-Trigger-Logik → Versand.
>
> **Keine Schema-Änderung:** Alle betroffenen Felder (`alert_channels`, `alert_channel_thresholds`,
> `official_warnings`, `official_alert_triggers_enabled`) existieren bereits unverändert im
> Datenmodell. Der Pre-Snapshot-Hook `data_schema_backup.py` wird durch S4 nicht ausgelöst.
>
> **Mail-Renderer-Berührung:** Der SMS-Paritäts-Fix berührt ggf. `src/output/renderers/alert/*.py`
> bzw. den SMS-Textbau für Abweichungsalarme — das ist Alarm-, nicht Trip-Briefing-Inhalt. Die
> Pflicht-Validatoren `briefing_mail_validator.py`/`email_spec_validator.py` sind auf Trip-Briefing-
> bzw. Ortsvergleich-Mails zugeschnitten und decken Alarm-Mails nicht ab; ob der
> Renderer-Commit-Gate hier trotzdem greift, klärt `/50` am konkreten Diff. Der eigentliche Nachweis
> für S4 läuft über die Golden-Fixture-Ketten (AC-7), nicht über die Mail-Validatoren.

## Estimated Scope

- **LoC produktiv:** ~60–100 (Fix `trip_alert.py:895-911` ~15–20; SMS-Paritäts-Fix
  `notification_service.py`/Renderer ~30–60; kleinere Anpassungen an Aufrufstellen)
- **LoC Test:** ~650–800 (`alarm_pruefstrecke.py`-Erweiterung ~80–120; drei neue Testdateien für
  Abweichung/Radar/amtlich je ~120–180; SMS-Paritätstest ~60; fünf neue Golden-Fixture-JSONs;
  Orakel-Erweiterung ~60–80)
- **Gesamt:** ~700–900 LoC — deutlich über dem Test-Default (500) und im Grenzbereich des
  Produktiv-Defaults (250). Vor `/40`/`/50` `workflow.py status` prüfen und bei Bedarf
  `workflow.py set-field loc_limit_override 900` setzen (keine PO-Rückfrage nötig, bereits mit dem
  PO abgeklärt — nicht eigenmächtig auf eine Teilscheibe verengen).
- **Files:** ~10–12 neu/geändert
- **Effort:** high — zwei echte Produktivcode-Fixes in der Alarm-Trigger-Logik (nicht nur Tests),
  drei parallele Golden-Fixture-Ketten, Migrations-Pflicht über `app.loader`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader` (`load_trip`, Migrationslogik `_migrate_legacy_alert_rules`, `_migrate_rule_channels_to_metric_channels`) | Modul | Upstream — Golden-Fixtures MÜSSEN hierüber laufen, nicht `Trip(...)` im Speicher |
| `resolve_alert_channels()` / `effective_alert_channels()` (`alert_channels.py`) | Modul | Die eine geteilte Kanal-Auflösung für Trip **und** Vergleich — S4 prüft sie nur im Trip-Kontext |
| `split_by_threshold()` (`alert_channel_threshold.py`) | Modul | Reine Funktion, wird an drei Aufrufstellen separat geprüft (Abweichung, Radar, je eigener Kontext) |
| `check_official_alert_triggers()` (`trip_alert.py:2554`) | Modul | Öffentlicher Einstiegspunkt für amtliche Warnungen — MUSS über diesen Weg getestet werden, nicht über die private `_send_official_alert_only` |
| `_dispatch_alert_message` (`notification_service.py`) | Modul | Downstream-Versand für Radar **und** Abweichung (gemeinsamer Pfad) |
| `send_official_alert` (`notification_service.py:1058`) | Modul | Downstream-Versand für amtliche Warnungen im Trip-Scope |
| `tests/helpers/transport_mitschrift.py` (S1–S3) | Testhilfe | Wiederverwendete Mitschrift-Naht an `EmailOutput`/`SMSOutput`/`PremiumSmsOutput`/`TelegramOutput` |
| `tests/helpers/alarm_pruefstrecke.py` (#2050) | Testhilfe | Basis, wird um Loader-Adapter + öffentlichen Official-Einstiegspunkt erweitert |
| ADR-0021 (geteilte `DeviationAlertEngine`) | ADR | Begründet den gemeinsamen Auflösungskern für Trip und Vergleich |
| ADR-0046 (Kanal-Schwelle regelt WIE, nicht OB) | ADR | Grundlage für AC-1/AC-2 (Schwelle filtert Inhalt, nicht Kanal-Zugehörigkeit) |
| ADR-0049 (Premium-SMS als vierter Kanal) | ADR | Premium-SMS wird in allen drei Alarm-Arten gleichrangig geprüft |
| ADR-0077 (`alert_metric_channels`) | ADR | Grundlage für AC-1 (Kanal je Metrik, nur beim Abweichungsalarm) |
| Sammel-Issue #1199 | Issue | Aufnahme des Compare-Alarm-Folgepunkts (Known Limitations) |
| Issue #1088 | Issue | SMS-Paritätslücke amtlicher Zusatzblock — wird in S4 gefixt, nicht registriert |

## Implementation Details

### Fix 1 — Vorab-Filter im Sammellauf (`trip_alert.py:895-911`)

Vorher (Bug):

```python
official_trigger_possible = trip.official_alert_triggers_enabled is not False
if (not has_active_rules and (not trip.report_config or not trip.report_config.alert_on_changes)
        and not official_trigger_possible):
    continue
```

Der Filter prüft nur das veraltete Feld. Nachher muss er spiegelbildlich zur Vorrangregel in
`:2577-2587` auch `official_warnings.enabled` berücksichtigen:

```python
official_warnings_enabled = getattr(trip.official_warnings, "enabled", None)
official_trigger_possible = (
    official_warnings_enabled
    if official_warnings_enabled is not None
    else trip.official_alert_triggers_enabled is not False
)
if (not has_active_rules and (not trip.report_config or not trip.report_config.alert_on_changes)
        and not official_trigger_possible):
    continue
```

`official_warnings.enabled` hat Vorrang, wenn gesetzt; fehlt es (Altdaten), zählt weiter das
Legacy-Feld. Das deckt exakt die drei Enable-Zustände aus AC-3/AC-4/AC-5 ab.

### Fix 2 — SMS-Paritäts-Hinweistext (#1088)

Bei einer gebündelten Abweichungs-Alarm-SMS, deren zugehörige Mail einen eingebetteten amtlichen
Zusatzblock trägt, erhält die SMS mindestens einen kurzen Hinweistext (z. B. `"+ amtl. Warnung s.
E-Mail/Telegram"` oder gleichwertig knapp) statt des Zusatzblocks komplett wegzulassen. Umfang ist
bewusst minimal gehalten (Zeichen-Budget SMS), erfüllt aber „jeder Kanal beantwortet jede Frage"
(Epic #2133): der Nutzer erfährt aus der SMS selbst, dass eine amtliche Warnung vorliegt, auch ohne
Zugriff auf E-Mail/Telegram.

### Testinfrastruktur-Erweiterung

- `alarm_pruefstrecke.lauf()` bekommt einen Loader-Adapter: Trip wird aus einer echten JSON-Fixture
  über `app.loader.load_trip(...)` geladen, nicht `Trip(...)` im Speicher konstruiert — sonst
  wiederholt S4 die Migrations-Lücke, die #2050 selbst hatte.
- Der `official`-Zweig ruft künftig `check_official_alert_triggers()` auf (öffentlicher
  Einstiegspunkt, enthält die Drei-Zustand-Vorrangprüfung), nicht mehr die private
  `svc._send_official_alert_only(...)` — sonst wird genau die Prüfung umgangen, die S4 testen soll.
- Testnaht einheitlich über `transport_mitschrift.py` (S1–S3-Muster), nicht der bisherige
  `mail_sink`/HTTP-Stub-Ansatz aus `alarm_pruefstrecke.py` — vermeidet zwei parallele
  Testphilosophien.
- Fünf neue Golden-Fixtures, alle als reale Trip-JSON-Dateien, die durch `app.loader` laufen:
  Abweichung, Radar, amtlich (drei Enable-Fälle).

### Reihenfolge (PFLICHT für `/40`/`/50`)

1. Rote Tests für den Bug-Fall (AC-5) und die SMS-Parität (AC-7) zuerst.
2. Abweichungsalarm-Kette (reichhaltigster Pfad: Migration, `alert_metric_channels`, Schwelle).
3. Radar-Alarm-Kette (teilt sich `_dispatch_alert_message` mit Abweichung).
4. Amtliche-Warnungen-Kette (eigener Pfad, Drei-Zustand-Vorrang, enthält Fix 1).
5. Produktivfixes (Fix 1, Fix 2).
6. Cooldown/Quiet-Hours-AC (AC-6) und Negativ-Test (AC-8).

## Expected Behavior

- **Input:** gespeichertes Trip-JSON (Persistenzformat des Editors) mit beliebiger Kombination aus
  `alert_channels`, `alert_channel_thresholds`, `alert_metric_channels`, `official_warnings`,
  `official_alert_triggers_enabled` (Alt-Daten), `alert_cooldown_minutes`, `alert_quiet_from/to`,
  `alert_rules`.
- **Output:** Für jede der drei Alarm-Arten (Abweichung, Radar, amtlich) geht genau das hinaus, was
  das JSON aussagt: die aufgelösten Kanäle (Override → Regel/Metrik-Union → Tarif-Gate), gefiltert
  durch die eingestellte Schwelle, unterdrückt während Cooldown/Quiet-Hours, in derselben Menge über
  alle vier Kanäle. Amtliche Warnungen lösen aus, wenn `official_warnings.enabled` **oder**
  (Altdaten-Fall) das Legacy-Feld es erlaubt — nie stillschweigend gar nicht, obwohl der Editor „an"
  zeigt.
- **Side effects:** Zwei gezielte Produktivcode-Fixes (`trip_alert.py`, `notification_service.py`/
  Renderer); erweiterte Testinfrastruktur (`alarm_pruefstrecke.py`, Orakel); fünf neue
  Golden-Fixtures; keine Datenmodell-Änderung.

## Acceptance Criteria

- **AC-1 (Abweichungsalarm: Kanal-Auflösung + Schwelle konsistent bis zu allen vier Kanälen):**
  Given ein über `app.loader` geladener Trip mit aktiven Wetter-Delta-Regeln, `alert_channels` mit
  genau zwei eingeschalteten Kanälen, `alert_metric_channels` mit einer abweichenden Kanal-Auswahl
  für eine einzelne Metrik, und einer `alert_channel_thresholds`-Schwelle, die den Auslöser für
  genau einen Kanal unterdrückt / When ein Abweichungsalarm über `alarm_pruefstrecke.lauf()`
  ausgelöst wird / Then bedient der Aufzeichner exakt die durch Auflösung **und** Schwelle
  bestimmte Kanalmenge — inklusive der metrikspezifischen Kanal-Abweichung — bei allen vier
  Kanälen (E-Mail, Telegram, SMS, Premium-SMS) gleich streng geprüft.
  - Test: `test_alarm_abweichung_kette.py::test_kanalmatrix_und_schwelle_konsistent_bis_zum_versand`
    — Erwartung aus `resolve_alert_channels()`/`split_by_threshold()` unabhängig nachgebildet im
    Orakel, nicht aus der Produktfunktion übernommen.

- **AC-2 (Radar-Alarm: Kanal-Auflösung + Schwelle über alle vier Kanäle):** Given ein geladener Trip
  mit `alert_channels` (drei von vier Kanälen an) und einer Radar-Schwelle, die den Auslöser knapp
  unterschreitet, sowie eine Gegenprobe knapp überschreitet / When der Radar-Alarm über dieselbe
  Prüfstrecke ausgelöst wird / Then bleibt die Auslieferung im ersten Fall aus, im zweiten Fall
  bedient der Aufzeichner exakt die drei eingeschalteten Kanäle — kein Kanal wird bei Radar
  anders behandelt als bei Abweichung.
  - Test: `test_alarm_radar_kette.py::test_radar_kanalmatrix_und_schwelle_konsistent`.

- **AC-3 (Amtliche Warnungen, Fall 1 — aktueller Schalter):** Given ein geladener Trip mit
  `official_warnings.enabled=true` und einem beliebigen, auch widersprüchlichen Stand des
  Legacy-Felds `official_alert_triggers_enabled` (z. B. `false`), sowie **keine** aktive
  Wetter-Delta-Regel / When `check_official_alert_triggers()` über die Prüfstrecke für eine echte
  amtliche Warnmeldung ausgeführt wird / Then wird die amtliche Alarm-Nachricht über die
  eingeschalteten Kanäle ausgeliefert — der aktuelle Schalter hat Vorrang vor dem veralteten Feld.
  - Test: `test_alarm_amtliche_warnungen_kette.py::test_official_warnings_enabled_hat_vorrang`.

- **AC-4 (Amtliche Warnungen, Fall 2 — Alt-Daten mit nur Legacy-Feld):** Given ein geladener Trip
  ohne `official_warnings`-Block (Alt-Daten-Fall) und `official_alert_triggers_enabled=true` /
  When derselbe Auslöser läuft / Then wird die amtliche Alarm-Nachricht wie beim aktuellen Schalter
  ausgeliefert — Altbestand ohne den neuen Block funktioniert unverändert weiter.
  - Test: `test_alarm_amtliche_warnungen_kette.py::test_legacy_feld_traegt_bei_fehlendem_official_warnings_block`.

- **AC-5 (Bug-Fix: der beschriebene Bug-Fall löst nach dem Fix eine amtliche Alarm-Nachricht aus):**
  Given ein geladener Trip mit `official_warnings.enabled=true`, `official_alert_triggers_enabled=false`
  (historisch vor #1258 ausgeschaltet) und **keiner** aktiven Wetter-Delta-Regel / When der reguläre
  Sammellauf (nicht nur `check_official_alert_triggers()` direkt, sondern der Vorab-Filter in
  `trip_alert.py:895-911` davor) für eine echte amtliche Warnmeldung läuft / Then wird der Trip
  **nicht** übersprungen und die amtliche Alarm-Nachricht wird ausgeliefert — vor dem Fix wird der
  Trip in Zeile 906–911 komplett übersprungen und keine Nachricht geht hinaus.
  - Test: `test_alarm_amtliche_warnungen_kette.py::test_bugfall_vorab_filter_blockiert_nicht_mehr_trotz_veraltetem_legacy_feld`
    — rot vor dem Fix (Aufzeichner leer), grün danach (Aufzeichner enthält die Nachricht). Bug-Nachweis
    aus Nutzersicht: der Sammellauf-Einstieg wird verwendet, nicht der öffentliche Einstiegspunkt
    isoliert, sonst fängt der Test den Bug nicht.

- **AC-6 (Cooldown/Quiet-Hours im Alarm-Pfad):** Given ein geladener Trip mit
  `alert_cooldown_minutes` und `alert_quiet_from`/`alert_quiet_to`, ein Abweichungsalarm, der
  innerhalb der Quiet-Hours ausgelöst wird, und ein zweiter Alarm-Auslöser innerhalb des
  Cooldown-Fensters nach einem bereits versendeten Alarm / When beide Fälle über die Prüfstrecke
  laufen / Then bleibt die Auslieferung in beiden Fällen aus; außerhalb der Quiet-Hours und nach
  Ablauf des Cooldowns liefert derselbe Auslöser normal aus.
  - Test: `test_alarm_abweichung_kette.py::test_cooldown_und_quiet_hours_unterdruecken_den_alarm`,
    parametrisiert über beide Sperren; Gegenprobe außerhalb der Sperren im selben Test.

- **AC-7 (SMS-Paritäts-Korrektur #1088):** Given ein Abweichungsalarm, dessen gebündelte Mail einen
  eingebetteten amtlichen Zusatzblock trägt / When die zugehörige SMS gerendert und versendet wird /
  Then enthält die SMS mindestens einen kurzen Hinweistext auf die amtliche Warnung — vor dem Fix
  fehlt der Zusatzblock in der SMS vollständig und ohne jeden Hinweis.
  - Test: `test_alarm_sms_paritaet_amtlicher_zusatz.py::test_sms_enthaelt_hinweis_auf_amtliche_warnung_bei_gebuendeltem_alarm`
    — rot vor dem Fix, grün danach; prüft den gerenderten SMS-Text, kein Dateiinhalt-Check.

- **AC-8 (Negativ-Test: bewusste Nicht-Parität `metrics` nur bei Abweichungsalarm):** Given ein
  geladener Trip mit `alert_metric_channels` gesetzt / When ein Radar-Alarm **und** eine amtliche
  Warnung ausgelöst werden / Then wird `alert_metric_channels` bei beiden **nicht** ausgewertet —
  die Kanalauflösung für Radar und amtlich hängt strukturell nicht von der Metrik ab. Der Test
  schützt gegen den Fehlschluss, dass fehlende Metrik-Kanal-Trennung bei Radar/amtlich ein Defekt
  wäre.
  - Test: `test_alarm_radar_kette.py::test_alert_metric_channels_wirkt_nicht_bei_radar_und_amtlich`
    — Gegenprobe mit identischem `alert_metric_channels`-Wert, aber unverändertem Ergebnis
    gegenüber einem Lauf ohne dieses Feld.

## Known Limitations

- **Compare-Alarm-Kette bleibt außerhalb von S4** (Radar + amtliche Warnungen am `ComparePreset`).
  `ComparePreset.alert_channels` hat laut #2293 aktuell kein stabiles Go-Feld/keine Migration — eine
  Golden-Fixture-Kette dafür würde auf einem Datenmodell aufsetzen, das #2293 erst herstellt.
  **Folgepunkt: Sammel-Issue #1199** — Compare-Alarm-Kette nach Abschluss von #2293 nachziehen, nicht
  stillschweigend fallen lassen.
- **`radar_alert_enabled` existiert nur am `ComparePreset`, kein Trip-Pendant.** Am Trip läuft das
  Radar-Gate implizit über Segmentwahl/Nowcast/Throttle. Dokumentationswürdige Asymmetrie, **kein
  Bug** — AC-2 prüft den Trip-Pfad so, wie er tatsächlich funktioniert.
- **`official_alerts_enabled` liegt außerhalb von S4.** Es steuert den Fetch der amtlichen
  Warn-**Inhalte** fürs Trip-Briefing (anderer Konsument, S1-Territorium: `trip_report_scheduler.py`,
  `comparison_engine.py`), nicht den Alarm-**Trigger**. Nicht mit `official_warnings.enabled`
  verwechseln.
- **`metrics`/`metric_channel_sets` gilt strukturell nur beim Abweichungsalarm** — dokumentiert und
  durch AC-8 als Negativ-Test aktiv abgesichert, damit die Vier-Kanal-Matrix keine falsche rote
  Zelle für Radar/amtlich erzeugt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue
- **Rationale:** S4 ändert keine Architekturentscheidung — es schließt Testabdeckungslücken
  innerhalb bereits getroffener Entscheidungen (ADR-0021 geteilte `DeviationAlertEngine`, ADR-0046
  Kanal-Schwelle regelt WIE nicht OB, ADR-0049 Premium-SMS als vierter Kanal, ADR-0077
  `alert_metric_channels`) und behebt zwei lokale Bugs (Vorrangprüfung amtlicher Warnungen,
  SMS-Paritätslücke #1088), ohne eine bestehende Entscheidung zu revidieren.

## Changelog

- 2026-09-29: Initial spec created
