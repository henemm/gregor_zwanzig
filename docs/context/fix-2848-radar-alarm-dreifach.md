# Context: fix-2848-radar-alarm-dreifach

## Request Summary
Im Produktiv-Alarmlog (Trip `5f534011`, Nutzer `henning`) stehen am 24.08.2026 drei Radar-Alarme
für dasselbe Ereignis (Beginn 13:15 UTC, Ende 15:00 UTC, ARPAE-2I, jeweils HIGH), gesendet
12:22 / 12:37 / 13:07 UTC (Vorlauf 53/38/8 Min). Die Ereignis-Entdopplung (#1467 S4b-1,
seit 16.08. auf main) hätte Lauf 2 und 3 unterdrücken müssen. Klären: besteht der Fehler im
heutigen Code noch (Nachbau in der AlarmPruefstrecke), und wenn ja, warum.

## Messbefund Produktiv-Log (`/var/lib/gregor/users/henning/alert_log.json`, gelesen 2026-11-08)
| sent_at (UTC) | Vorlauf | event_at → event_end_at | measurement_point.segment_id | km | Messpunkte |
|---|---|---|---|---|---|
| 12:22:02 | 53 | 13:15 → 15:00 | `1` | 0–6.15 | 1/1 |
| 12:37:02 | 38 | 13:15 → 15:00 | `2` | 6.15–10.09 | 2/2 |
| 13:07:02 | 8 | 13:15 → 15:00 | `2` | 6.15–10.09 | 1/1 |

Zusätzlich: 10:31 Änderungsalarm (thunder 1→3, HIGH), 13:30 amtlich DPC (LOW), 16:22 weiterer
Nowcast (anderes Ereignis 17:15). Alle Kanäle email+telegram; kein `precip_mm` im Log-Eintrag.

**Auffällig:** Lauf 1 → Lauf 2 wechselt das Messsegment (1 → 2). Lauf 2 → Lauf 3 hat dasselbe
Segment (2) und dieselbe Ereigniszeit, trotzdem kein Duplikat erkannt. Zwei getrennte Fragen:
1. Lauf 2 vs. Lauf 1: disjunkte Segmentmengen (`{1}` vs. `{2}`)? Damaliger Code registrierte
   evtl. nur das aktive Segment; `radar_ereignis_segmente` ({aktiv} ∪ {Segment zur Ereigniszeit},
   #2261 A-1) kam später.
2. Lauf 3 vs. Lauf 2: gleiche Segmente, gleicher Beginn → nur erklärbar durch (a) fehlenden
   Registereintrag (Reset, z. B. Briefing-Reset des Registers, oder `record_event_identity` nicht
   erreicht), (b) Durchbruch über `quantitative_escalation` (`_mengen_ueberholt`, #2065 seit 22.08.),
   (c) `_covers_materially_more`, (d) damals anderer Code-Stand.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/alert_gate.py:436` | `radar_overtakes_cooldown()` — Mengen-Überholung (#2065) |
| `src/services/alert_gate.py:561` | `resolve_hazard_class()` — Nowcast immer Klasse `wet` |
| `src/services/alert_gate.py:~620-657` | `_times_overlap()` — Zeitüberlappung via `NOWCAST_HORIZON_MIN` um `point_at` |
| `src/services/alert_gate.py:660` | `_find_matching_entry()` — Kandidatensuche (Segmente nicht disjunkt + Zeitüberlappung) |
| `src/services/alert_gate.py:~760` | `_covers_materially_more()` — V1-Ausnahme |
| `src/services/alert_gate.py:~775` | `check_event_identity_gate()` — Eskalation → V1 → Unterdrückung |
| `src/services/alert_gate.py:~880` | `record_event_identity()` — Registrierung nach Zustellung |
| `src/services/trip_alert.py:2441-2474` | Sperrzeit + `_mengen_ueberholt` (Radar-Trip-Pfad) |
| `src/services/trip_alert.py:2818-2829` | Identitätsprüfung Radar: `radar_ereignis_segmente(trip, active, _onset_dt)`, `point_at=_onset_dt`, `quantitative_escalation=_mengen_ueberholt` |
| `src/services/trip_alert.py:2977-2983` | `record_event_identity` nach Zustellung |
| `src/services/compare_radar_alert.py:316` | Ortsvergleich-Pendant (ADR-0021 geteilt) |
| `docs/context/fix-2009-nowcast-8min-nachmessung.md` | Vorgänger-Analyse, Tabelle Z. 96-101 |

## Existing Patterns
- Entdopplung ist reiner Lesevorgang vor Versand, Registrierung nur nach Zustellung (F001-Symmetrie).
- AlarmPruefstrecke / Szenario-Wächter (`docs/specs/modules/alarm_pruefstrecke.md`,
  `alarm_szenarien_waechter_*.md`, `alarm_szenario_laufendes_ereignis.md`) sind das Werkzeug für
  den Nachbau mehrerer Läufe gegen echten Code.

## Dependencies
- Upstream: Radar-Nowcast (ARPAE-2I), Trip-Segmente/Position (`active`), `AlertStateService` (Register).
- Downstream: Alarmlog, alle vier Kanäle, Nachtragsmeldung (#2018), Ortsvergleich-Radarpfad.

## Existing Specs
- `docs/specs/modules/rework_1467_s3_nowcast.md`, `rework_1467_s1_alarm_kennung.md` (Ereignis-Identität)
- `docs/specs/modules/feat_2050_s4c_ein_ereignis_ein_alarm.md`
- `docs/specs/modules/feat_2261_a1_radar_vorlauf.md` (Segmentmenge A-1)
- `docs/specs/modules/fix_1714_compare_alert_briefing_reset.md` (Briefing-Reset)
- `docs/specs/modules/fix_2009_nowcast_vorlauf.md`

## Code-Historie (zwischen 16.08. und 24.08. auf main)
`99e65c7fa` 16.08. S4b-1 Entdopplung · `bf321eb8c` 21.08. #2018 Nachtrag · `e1836252a` 22.08.
#2065 Mengen-Überholung · `aadfcd554` 23.08. #2050 S4c · später #2261 A-1 (Segmentmenge).
Deploy-Stand am 24.08. muss in der Analyse bestimmt werden (nicht = main-Stand).

## Risks & Considerations
- Gefährlichste Fehlerrichtung ist "Alarm bleibt aus": jede Verschärfung der Entdopplung darf
  Eskalation/V1-Ausnahme nicht abschneiden.
- Wandernder Wanderer: Segmentwechsel zwischen Läufen ist der Normalfall, nicht die Ausnahme.
- Trip- und Ortsvergleich-Pfad müssen gleich behandelt werden (ADR-0021, Code-Teilung).
- Ist der Nachbau mit heutigem Code bereits entdoppelt: Ergebnis ist ein Wächter-Test + Schließen
  mit Begründung, kein Code-Fix.

## Analysis

### Type
Bug-Meldung, Befund: **kein Defekt der Entdopplung**. Lauf 2 und 3 sind gewollte
Mengen-Durchbrüche nach #2065. Offen ist eine Produktfrage (Kennzeichnung bzw. Häufigkeit).

### Beweis (Prod-Journal `journalctl -u gregor-python`, 24.08.2026, gelesen 2026-11-08)
| Lauf (UTC) | Journalzeile `Sperrzeit-Ueberholung … Trip 5f534011` | Ergebnis |
|---|---|---|
| 12:22 | (Sperrzeit frei) | Alarm 1, Basis wird 1,0 mm |
| 12:37 | Basis 1.0 mm, Menge 3.1 mm: **Durchbruch** | Alarm 2 (Faktor 3,1 ≥ 2, ≥ 2 mm) |
| 12:52 | Basis 3.1 mm, Menge 5.2 mm: Sperrzeit bleibt | still (Faktor 1,68) |
| 13:07 | Basis 3.1 mm, Menge 7.3 mm: **Durchbruch** | Alarm 3 (Faktor 2,35) |

Mechanik: `_mengen_ueberholt` (`src/services/trip_alert.py:~2448`) wird als
`quantitative_escalation` an `check_event_identity_gate()` übergeben
(`trip_alert.py:2828`); dort ist die Eskalation der erste Zweig mit `return _ALLOWED`
(`src/services/alert_gate.py:838`), vor V1 und Unterdrückung. Die Ereignis-Identität hätte
Lauf 3 gegen Lauf 2 gefunden (gleiche Segmente `{2}`, gleiche Ereigniszeit), wird aber
absichtlich überstimmt (Spec `fix_2065_verschaerfung_ueberholt_sperre.md`, Purpose: wirkt an
Sperrzeit UND Entdopplung). Der Segmentwechsel 1→2 ist deshalb nicht ursächlich.

Weitere Hypothesen geprüft und verworfen:
- Register-Reset dazwischen: Briefings am 24.08. nur 05:04 und 16:05 (`briefing_log.json`), kein Reset im Fenster.
- Dass heute keine `event_identity:`-Einträge im Register stehen, ist gewollt: `AlertStateService.reset()`
  (`src/services/alert_state.py:108`) behält nur `official_alert:` (Datei zuletzt 06.10. geschrieben).
- Code-Stand: Mengen-Überholung lief am 24.08. nachweislich (Journalzeile existiert erst seit #2065).
  Heutiger Code hat dieselbe Verdrahtung, das Verhalten wäre heute identisch.

### Das eigentliche Problem (Nutzersicht)
Alle drei Alarme sehen gleich aus („Regen in 53/38/8 Min“, gleiche Ereigniszeit). Ein
Verschärfungs-Alarm ist nicht als Verschärfung erkennbar (keine Angabe „jetzt 7 mm statt
3 mm“); für den Nutzer wirkt das wie ein dreifacher Doppel-Alarm. Zudem gibt es je Ereignis
keinen Deckel: jede erneute Verdopplung bricht wieder durch (Tagesdeckel
`_MAX_ESCALATION_BREAKTHROUGHS = 1` in `alert_daily_limit.py:131` greift nur am Tagesbudget).

### Affected Files (je nach PO-Entscheid)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_…_2848_*.py` | CREATE | Wächter: Nachbau 24.08. (1,0→3,1→5,2→7,3 mm) in der AlarmPruefstrecke, belegt Durchbruch-Verhalten |
| Radar-Alarm-Renderer (Mail/Telegram/SMS/Premium-SMS) | MODIFY (Option B) | Verschärfungs-Hinweis „stärker als gemeldet: X statt Y mm“, alle vier Kanäle |
| `src/services/trip_alert.py`, `compare_radar_alert.py` | MODIFY (Option B/C) | Durchbruch-Kennzeichen an Renderer durchreichen bzw. Deckel je Ereignis |

### Scope Assessment
- Option A (nur Wächter + Schließen): 1 Testdatei, ~+80 LoC, Risiko NIEDRIG.
- Option B (Verschärfung kennzeichnen): ~4–6 Dateien, ~+150 LoC, Risiko MITTEL (vier Kanäle, i18n, Mail-Validator).
- Option C (Deckel je Ereignis): ~2–3 Dateien, Risiko MITTEL–HOCH (Fehlerrichtung „Alarm bleibt aus“).

### Technical Approach
Empfehlung: **Option B** — Verhalten von #2065 bleibt (Verschärfung muss durch, A-3 aus
#2050), aber der Folge-Alarm sagt ausdrücklich, dass es dasselbe Ereignis ist und um wie viel
es stärker wurde. Behebt den Eindruck „dreifach dasselbe“, ohne einen Alarm zu verschlucken.
Ortsvergleich: #2065 wirkt dort bewusst nicht (PO-zurückgestellt), daher nur Trip-Pfad betroffen.

### Open Questions
- [x] PO-Entscheid 2026-11-08 (AskUserQuestion): **Option B — Verschärfung kennzeichnen.**
  Folge-Alarm nennt „dasselbe Regenereignis, jetzt stärker: X statt Y mm“ in allen vier
  Kanälen; Durchbruch-Verhalten aus #2065 bleibt unverändert. Wächter-Test des 24.08.-Ablaufs
  gehört in die Spec.

## RED-Übergabe an /50-implement (2026-11-08)

RED-Stand: 23 failed / 14 passed (`docs/artifacts/fix-2848-radar-alarm-dreifach/test-red-output.txt`).
Testdateien: `tests/tdd/test_radar_verschaerfung_kennzeichnung_mehrlauf.py` (11),
`tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py` (26). Wächter grün: AC-1, AC-3,
AC-8, AC-10-Altbestand, Katalog-Parität, Golden-Byte-Vergleiche ohne Kennzeichen.

- **Abgriff in der Prüfstrecke:** Mail = Klartext aus `mail_sink(subject, body)`; Telegram = Feld
  `text` im Loopback-Stub (Stil „rich“ = Langform); SMS und Premium-SMS über den seven.io-Stub,
  getrennt per `from == PREMIUM_SMS_SENDER`; Alarmlog aus `alert_log.json` → `entries`
  (`reason == "nowcast"`).
- **SMS-Grenzen:** `_dispatch_alert_message` rendert mit `limit=140`; Premium-SMS
  `CHANNEL_LIMITS["premium_sms"] = 153`; absolut 160. Token-Form im Test per Regex
  `": UP Y>X (R|TH)"`, also direkt hinter `"<Kopf>: "`; Platz reservieren wie `_ADDENDUM_SMS_PREFIX`.
- **Texte exakt:** DE „Dasselbe Ereignis, jetzt stärker: X statt Y mm“ (Komma, 1 Nachkommastelle),
  EN „Same event, now stronger: X instead of Y mm“; in Mail-Klartext, HTML und Telegram-Langform.
- **Feldnamen (von Tests verwendet):** `AlertMessage.verschaerfung = (basis_mm, menge_mm)`,
  `GateResult.ist_mengen_verschaerfung` (Default False), Alarmlog `escalation_from_mm` /
  `escalation_to_mm` (Toleranz 0,05).
- **AC-4b-Aufbau:** amtlicher Vorgänger 8 h gültig (kommt nur per V1 durch), dann jüngster
  gleichrangiger HIGH-Kandidat mit `match["source"] == "official"`.
- **AC-4a-Aufbau:** anderes Ereignis innerhalb der Sperrzeit nicht baubar (`NOWCAST_HORIZON_MIN`=180);
  Register wird über den produktiven Briefing-Reset geleert.
- **Lücken für Developer/Adversary:** Telegram-Kurzform (sendet `sms_body`) ist über die
  Prüfstrecke nicht abgedeckt; prüfen, ob `>` bei `parse_mode=HTML` als `&gt;` escaped wird. Kein
  eigener Aufrufer-Test „Ortsvergleich kennt das Feld nicht“ (abgedeckt über AC-8-Mehrlauf und
  Golden `regen_buendel`).

