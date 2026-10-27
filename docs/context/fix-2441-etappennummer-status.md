# Context: fix-2441-etappennummer-status

## Request Summary
STATUS zeigt für dieselbe Etappe den rohen Namen („02: Obstansersee-Hütte nach Porzehütte"),
die Kurzform (`heute`) „E4:". Beide Wege sollen auf allen Kanälen dieselbe Etappennummer nennen
(Epic #2506 Kanal-Parität, Refs #2417 AC-27). Tech-Lead-Entscheid (PO „weiter" 07.10.): es gilt
die **gezählte, chronologische Nummer** (Spec #760), nicht die vom Autor im Namen vergebene.

## Ursache (belegt, Zeilen heute)
- STATUS: `src/services/trip_command_processor.py:2562` (`_show_status`) gibt `stage.name` roh aus
  (Ticket nannte :2259, veraltet).
- Weitere Roh-Ausgaben von `stage.name` in Befehlsantworten: `:2402`, `:2519` → `StageShift`, Ausgabe
  `:2450`, `:2533` (STARTDATUM-Verschiebung, Bestätigung).
- Kurzform: `Trip.numbered_stage_label()` (`src/app/trip.py:294-309`) berechnet Position nach Datum;
  `_STAGE_PREFIX_RE` (`trip.py:33-36`) erkennt nur „Etappe N"/„Tag N". Ein Präfix „02:" bleibt im Rest
  → „Etappe 4: 02: Obstansersee…". `_sms_stage_prefix()` (`src/output/renderers/sms_trip.py:50-55`,
  `_ETAPPE_RE` nur „Etappe N") macht daraus `E4`.

## Related Files
| File | Relevanz |
|------|----------|
| `src/app/trip.py` | `numbered_stage_label`, `_STAGE_PREFIX_RE` — Präfix-Erkennung um „02:"/„02 –" erweitern |
| `src/services/trip_command_processor.py` | `_show_status` (:2562) + StageShift-Ausgaben (:2450/:2533) auf geteilte Bezeichnung umstellen |
| `src/output/renderers/sms_trip.py` | `_sms_stage_prefix` (E{N}); prüfen, dass es aus dem erweiterten Label dieselbe Zahl liest |
| `src/services/trip_report_scheduler.py:1547`, `preview_service.py:203` | rufen `numbered_stage_label` (Briefing/Vorschau) — Regressionsfläche |
| `src/services/notification_service.py:404` | Alarm-Etappennummer, gleiche Zählung („S5", Spec fix_2122) |

## Existing Patterns
- Spec `docs/specs/modules/issue_760_stage_number.md`: Nummer = 1-basierte chronologische Position, „zwingend".
- Spec `fix_2122_etappen_praefix_kurzform.md`: Alarm-Kurzform `S{N}`, gleiche Zählung (Position in
  `sorted(stages, key=date)+1`). Es existieren also drei Schreibweisen (`Etappe N`, `E{N}`, `S{N}`),
  aber **eine** Zählung — der Fix darf diese Zählung nicht verändern.
- Bestehende Tests: `tests/tdd/test_issue_760_stage_number.py`, `test_issue_762_stage_suffix.py`,
  `test_ascii_folding.py`, `test_trip_sms_gsm7_charset.py`, `test_preview_render_options_parity.py`,
  `tests/tdd/_befehl_e2e_fixtures.py` (Befehle durch den echten Eingang, Memory #2417).

## Dependencies
- Upstream: `Trip.stages` (Datum, Name), `trip_local_today`.
- Downstream: Briefing-Mail (full/compact), Vorschau, Alarm-Renderer, SMS/Telegram-Kurzform, STATUS-Antwort
  auf allen Kanälen (E-Mail, Telegram, SMS, Premium-SMS). GSM-7-Zeichensatz auf Kurzform-Kanälen beachten
  (`strich`-Logik in `_show_status`).

## Existing Specs
- `docs/specs/modules/issue_760_stage_number.md`, `fix_2122_etappen_praefix_kurzform.md`,
  `feat_2417_kurzform_englisch.md` (EN-Ausgabe von STATUS: `self._en`).

## Risks & Considerations
- Blast Radius: geteilte Funktion → jede Änderung der Präfix-Erkennung wirkt auf Briefing-Mail und
  Alarme; Regression über die bestehenden Tests + Gegenprobe „Name ohne Präfix bleibt unverändert".
- Namen mit führender Zahl, die KEINE Etappennummer ist (z. B. „2 Seen Runde", „1. Pass") dürfen nicht
  fälschlich abgeschnitten werden → Muster eng fassen (nur `\d+` direkt gefolgt von `:`/`.`/`–`/`-`
  + Leerraum; Randfälle in der Spec benennen).
- Etappenlose/ohne Namen Fälle: leerer Rest → nur „Etappe N".
- Keine Persistenzänderung: Namen in den Daten bleiben unverändert (nur Anzeige).
- Pflicht-Test aus Nutzersicht: dieselbe Etappe über `status` und `heute` durch den echten Befehlseingang
  → dieselbe Zahl; zwei verschiedene Nutzer (Multi-User-Regel) bei datenbewegenden Endpunkten nicht
  einschlägig (nur lesend), trotzdem user_id durchreichen wie im Bestand.
- Offen für die Analyse: STATUS auf Kurzform-Kanälen (SMS) in welcher Schreibweise (`E4` vs. `Etappe 4`)?
  Vorschlag: Kanal-Schreibweise wie bei `heute` auf demselben Kanal.

## Analysis

### Type
Bug (nutzersichtbar, Kanal-Parität, Epic #2506)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/app/trip.py | MODIFY | `_STAGE_PREFIX_RE` um eng gefasstes Zahlenpräfix („02:", „02 –", „2.") erweitern |
| src/services/trip_command_processor.py | MODIFY | `_show_status` (:2562) und StageShift-Ausgaben (:2402/:2450, :2519/:2533) nutzen `trip.numbered_stage_label(stage)` statt `stage.name` |
| tests/tdd/test_issue_2441_etappennummer_status.py | CREATE | status vs. heute durch echten Befehlseingang, Randfälle des Musters |
| docs/specs/modules/ (neue Spec) | CREATE | ACs auf Deutsch, PO-Freigabe |

`sms_trip.py::_sms_stage_prefix` bleibt unverändert: liest aus dem bereits normalisierten Label „Etappe N: …" dieselbe Zahl.

### Scope Assessment
- Files: 2 Produktiv + 1 Test + 1 Spec
- Estimated LoC: +35/-6 produktiv
- Risk Level: MEDIUM (geteilte Funktion wirkt auf Briefing, Vorschau, Alarme)

### Technical Approach
Eine Wahrheit: gezählte chronologische Position (Spec #760). Zahlenpräfix im Namen wird wie „Etappe N" ersetzt, nicht addiert. STATUS/Verschiebe-Antworten rufen dieselbe Funktion. Schreibweise in STATUS: „Etappe N: Rest" auf allen Kanälen (Listenzeilen, keine 160-Zeichen-Zeile pro Etappe); GSM-7-Strich-Logik bleibt. Muster eng: nur `^\d{1,2}` direkt gefolgt von `:`/`.`/`–`/`-` und Leerraum; „2 Seen Runde" bleibt unverändert. Keine Persistenzänderung.

### Dependencies
`Trip.stages`, `trip_local_today`; Downstream: Briefing-Mail, Vorschau (`preview_service.py:203`), Scheduler (`trip_report_scheduler.py:1547`), Alarm-Zählung (`notification_service.py:404`, S{N}, gleiche Zählung).

### Open Questions
- [ ] Keine für den PO. Tech-Lead-Entscheid: STATUS-Schreibweise „Etappe N:" statt „E{N}".
