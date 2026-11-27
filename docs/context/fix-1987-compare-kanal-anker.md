# Context: #1987 Scheibe S2 — Ortsvergleich: kanalscharfer, rollierender Alarm-Anker

Workflow: `fix-1987-compare-kanal-anker` · Branch `fix/1987-compare-kanal-anker` · Stand HEAD `003f19cde`

## Request Summary

PO-Entscheid 2026-08-19 (Issue #1987): Vergleichsbasis eines Abweichungsalarms ist der Stand, den dieser
Empfänger **auf diesem Kanal zuletzt tatsächlich zugestellt** bekommen hat — Briefing **oder** Alarm.
Scheibe S1 (Trip) ist seit 2026-08-20 live (PR #2008, ADR-0056-Amendment). S2 überträgt das auf den
Ortsvergleich. Dort fehlt zusätzlich der rollierende Anker ganz: heute schiebt nur das Briefing den Merker.
Issue trägt jetzt `go-live-pflicht` / Meilenstein „Going Live: externe Nutzer“ — S2 ist nicht mehr zurückgestellt.

Zu bauen (aus Issue, S2):
1. Ein zugestellter Ortsvergleich-Alarm schiebt den Merker (rollierend).
2. Merker je Kanal (email, telegram, sms, premium_sms), geschrieben nur für `delivered_channels`.
3. Alterungs-Obergrenze je Kanal: veralteter Merker → Vergleich gegen frischesten verfügbaren Stand.
4. Bestandsdaten (kanallose Dateien) bleiben lesbar und dienen allen Kanälen als Ausgangsbasis.

## Related Files

| Datei | Rolle |
|---|---|
| `src/services/compare_weather_snapshot.py` | Δ-Anker-Service: `{preset}__{loc}.json` in `compare_weather_snapshots/`; `save` :52-80, `load` :91-, `delete` :77-107 (kein src-Aufrufer) |
| `src/services/compare_alert.py` | Laden :695 (`_vorbereite_ort` :689), `_anchor_too_old` :769-798 mit `_MAX_ANCHOR_AGE = 26h` (:63) → Ort wird übersprungen; Auswertung je Ort `DeviationAlertEngine.evaluate` :745; Kanäle `_kanaele_fuer_ort` :835; Versand `send_multi_location_deviation_alert` ~:480-498, `delivered_all |= delivered_channels` :497; danach alert_log, `_finalize_triggered_state` :565/:822, Throttle, Daily-Limit. **Schreibt keinen Anker.** |
| `src/services/scheduler_dispatch_service.py` | `_write_compare_alert_snapshots` :1178-1254 über `_anchor_and_reset` :972-986 → `write_anchor_and_reset_memory` (alert_briefing_anchor.py:266). Aufgerufen im Exception-Pfad :1031 und Erfolgspfad :1094, nicht bei `channels_unreachable`. Schreibt alle Orte, kanallos. Briefing-Kanäle `_effective_compare_briefing_channels` :717 |
| `src/services/alert_preview_hours.py:101` | zweiter Leser des Compare-Ankers (Vorschau) |
| `src/services/notification_service.py:169,209-213` | `NotificationResult.delivered_channels` = sent − failed |
| `src/services/weather_snapshot.py` :231-323 | S1-Vorbild: `_alarm_anchor_path` mit Legacy-Fallback, `save_alarm_anchor(channel)`, `alarm_anchor_target_date` |
| `src/services/trip_alert.py` | S1-Vorbild: `_ALARM_ANCHOR_CEILING = 4h` :111, `_kanal_anker_kandidat` :1534, `_rollierender_anker_kandidat` :1576-1646 (ältester gültiger Kandidat, `None` falls ein Kanal ungültig), `_write_rolling_alarm_anchor` :1648-1667 (nur delivered_channels, Aufruf :1094) |
| `internal/store/compare_preset.go:331-357` | Go löscht beim Preset-Löschen `compare_weather_snapshots/<id>__*.json` → neuer Dateiname MUSS mit `{preset}__` beginnen |
| `internal/store/user.go:612`, `internal/handler/data_export_test.go` | Konto-Löschung / Export des Nutzerbaums |

Nicht betroffen: `compare_radar_alert.py`, `compare_official_alert.py` (nutzen nur `alert_state`, keinen Δ-Anker).

## Existing Patterns

- S1-Muster (Trip): eine Datei je Kanal, Legacy-Fallback im Lesepfad statt Migrationsskript; Schreiben nur für
  `delivered_channels`; ein gemeinsamer Auswertungslauf gegen den **ältesten** gültigen Kanal-Kandidaten;
  ungültiger Kanal-Kandidat → Rückfall auf den Briefing-Anker (Tier 1). Ceiling 4 h für den rollierenden Anker.
- Trip/Ortsvergleich-Code-Teilung (CLAUDE.md, #1170): wo möglich S1-Hilfslogik teilen statt Compare-Pendant
  neu bauen; Pendant-Gate `tests/tdd/test_pendant_gate_bekannte_paare.py:43` kennt das Paar.
- Daten-Schema-Rework: Read-Modify-Write, kein Replace; Bestandsdatei bleibt.
- `atomic_write_json` für alle Snapshot-Writes.

## Dependencies / Dependents

- Leser: `compare_alert._vorbereite_ort`, `alert_preview_hours` (Vorschau muss dieselbe Basis zeigen — Kanal-Frage!).
- Schreiber: Briefing-Dispatch; neu: Compare-Alarm nach Versand.
- Go-Cleanup per Präfix `{preset}__`.

## Existing Specs / ADRs

- `docs/specs/modules/fix_1987_kanal_anker.md` (S1, 11 ACs; sagt S2 bleibt unangetastet)
- `docs/adr/0056-rollierender-alarm-anker-statt-briefing-only-snapshot.md:112` — „Ortsvergleichs-Δ-Anker bleibt kanalagnostisch (S2, zurückgestellt)“ → Amendment nötig
- `docs/adr/0021` (DeviationAlertEngine), `docs/specs/_archive/modules/issue_1169_compare_alert_consumer.md`
- #1661 (target_date im Compare-Anker), #1629 (Briefing-Anker als Absicherung), #1199 F002 (Kandidaten-Verwerfung bei ≥2 Kanälen)

## Tests (betroffen / Vorbild)

Compare: `tests/tdd/test_issue_1169_compare_alert_consumer.py`, `test_compare_anchor_target_date.py`,
`test_compare_alert_anchor_unaffected.py` (:142 fest auf `{preset}__{loc}.json`), `test_compare_alert_channel_delivery.py`,
`test_compare_anker_ortsmitternacht.py`, `test_compare_briefing_anchor_and_memory_reset.py`,
`test_compare_briefing_anchor_survives_dispatch_failure.py`, `test_alert_preview_reihen_quelle.py`,
`tests/unit/test_compare_weather_snapshot_delete.py`, `tests/test_test_suite_passes_user_id_explicitly.py:90`.
S1-Vorbild: `tests/tdd/test_alert_channel_anchor_{delivery,retention,ceiling_fallback,shared_comparison}.py`.

## Risks / Offene Punkte für die Analyse

1. **Ceiling-Zielkonflikt:** Compare überspringt heute einen Ort bei Anker > 26 h. S1 nutzt 4 h für den
   rollierenden Anker und fällt sonst auf den Briefing-Anker zurück. Für Compare braucht es dasselbe Zwei-Stufen-Modell
   (Briefing-Anker als Tier 1 bleibt, rollierender Kanal-Anker als Tier 2) — die bestehende Datei bleibt Tier 1.
2. **Briefing-Anker schreibt auch im Exception-Pfad** (#1629-artige Absicherung, `test_compare_briefing_anchor_survives_dispatch_failure.py`).
   Analog S1-E1: Tier 1 bleibt kanalagnostisch und unbedingt; Zustellungsbindung gilt nur für den rollierenden Tier-2-Anker.
3. **Gruppenversand:** Ein Alarm-Versand umfasst mehrere Orte; der rollierende Anker muss für jeden **im Versand enthaltenen Ort**
   und je zugestelltem Kanal geschrieben werden — mit dem Frischwert, gegen den ausgewertet wurde.
4. **Kanäle je Ort sind metrikabhängig** (`_kanaele_fuer_ort`) — Kandidatenmenge je Ort muss dieselbe Kanalmenge nutzen.
5. **Vorschau** (`alert_preview_hours`) liest den Anker ebenfalls — muss dieselbe Auflösung nehmen oder bewusst bei Tier 1 bleiben.
6. Go-Cleanup-Präfix, Export, Konto-Löschung: Dateiname `{preset}__{loc}__alarm_{channel}.json` o. ä. hält den Präfix.
7. Quiet Hours / Daily-Limit / Throttle: unterdrückter Versand = keine Zustellung = kein Merker.

## Analysis

**Type:** Feature-Änderung mit Fehlverhaltens-Anteil (PO-Entscheid #1987, Scheibe S2 Ortsvergleich).

### Affected Files

| Datei | Change | Inhalt |
|---|---|---|
| `src/services/compare_weather_snapshot.py` | MODIFY | `save_alarm_anchor(preset, loc, point, channel)` / `load_alarm_anchor(preset, loc, channel)`; Datei `{preset}__{loc}__alarm_{channel}.json` (Präfix `{preset}__` hält Go-Cleanup + `delete()`), ~50 LoC |
| `src/services/compare_alert.py` | MODIFY | gemeinsame Basis-Auflösung (`_vorbereite_ort` :689) ~60 LoC; Schreibpunkt je Gruppe nach `send_multi_location_deviation_alert` (~:497) ~30 LoC |
| `src/services/alert_preview_hours.py` | MODIFY | `compare_preview_point` (:88-120) nutzt dieselbe Auflösung, rein lesend, ~15 LoC |
| `src/services/alarm_anchor_basis.py` | CREATE (optional) | neutrale Hilfsfunktion „ältester gültiger Kandidat“ ~40 LoC; Trip bleibt unangetastet |
| `docs/adr/0056-…md` | MODIFY | Amendment: :112 „bleibt kanalagnostisch, zurückgestellt“ ersetzen |
| `docs/specs/modules/fix_1987_s2_compare_kanal_anker.md` | CREATE | Spec S2 |
| Tests `tests/tdd/test_compare_channel_anchor_*.py` | CREATE | s. u. |

Summe Quellcode: 3–4 Dateien, ~200 LoC → innerhalb ±250, kein Split.

### Scope / Risk

Mittel. Alarmpfad Ortsvergleich + Vorschau; Bestandsdaten bleiben (keine Umbenennung, neue Dateien zusätzlich). Kein Go-, kein Frontend-Change.

### Technical Approach (Variante B′, empfohlen)

| Variante | Basis je Kanal | Ceiling | Wirkt an Briefing-Tagen | LoC |
|---|---|---|---|---|
| A: S1 strikt spiegeln (Briefing gewinnt immer) | Tier-Kette | 4 h | nein (S1-Defekt, s. #3481) | ~180 |
| B: neuester gültiger, 4 h | max | 4 h | ja, verwirft aber 4–26 h alte Alarm-Anker → Rückfall auf ÄLTEREN Briefing-Stand | ~200 |
| **B′: neuester gültiger, 26 h, target_date-Guard** | max | 26 h | ja | ~200 |
| C: kanallosen Anker schieben | — | 26 h | ja, aber nicht kanalscharf | ~60 |

1. **Basis je Kanal** c ∈ `config.channels` (rohe preset-weite Menge, vor Schwellen-/Metrikfilter, analog S1):
   basis_c = **neuester** gültiger Stand aus {Briefing-Anker (bestehende Datei), Alarm-Anker c}.
   Gültig: Alter ≤ `_MAX_ANCHOR_AGE` (26 h, unverändert, EINE Grenze); Alarm-Anker nur, wenn sein `target_date` dem des Briefing-Ankers entspricht (Tagesbezug #1661; neues Abend-Briefing für morgen entwertet heutige Alarm-Anker).
   Fehlt die kanalscharfe Datei → nur Briefing-Anker (Bestandsdaten = Ausgangsbasis für alle Kanäle, AC-4 des Issues). Kein Kontaminationsweg: nie der Alarm-Anker eines ANDEREN Kanals.
2. **Gemeinsamer Lauf** (E2/ADR-0021 unverändert): verglichen wird gegen die **älteste** basis_c; `target_date` und `fetched_at` dieser Basis speisen Frisch-Abruf, `reference_at`, `anchor_point`.
3. **Kein gültiger Stand** → bestehendes `too_old`/`missing`-Verhalten (Ort übersprungen, Diagnose).
4. **Schreiben**: je versendeter Gruppe, für jeden Ort der Gruppe × jeden Kanal in **dieser Gruppe** `notif_result.delivered_channels` → `save_alarm_anchor(fresh_point mit target_date)`. Nicht `delivered_all`, nicht `sent_channels`, nicht `effective_channels`. Kein `write_anchor_and_reset_memory` (Melde-Gedächtnis bleibt). Fail-soft, nach dem Versand, ändert Backoff/Finalize/Protokoll nicht. `BLOCKED_ONLY`/Quiet-Hours/Daily-Limit/Backoff → nichts zugestellt → nichts geschrieben.
5. **Vorschau** löst die Basis identisch auf (rein lesend), sonst zeigt sie andere Stundenzeilen als der Alarm.
6. **Briefing-Anker** bleibt unbedingt und kanalagnostisch (E1-Analogie, #1629-Absicherung inkl. Exception-Pfad).

**Abweichung von S1 begründet:** S1 lässt den datierten Briefing-Anker immer gewinnen (rollierender Merker greift nur ohne Tagesbriefing) — erfüllt den PO-Entscheid an Briefing-Tagen nicht → eigenes Ticket #3481. Die 4 h aus S1 würden im Compare-Modell einen jüngeren, zugestellten Stand zugunsten eines älteren verwerfen (= erfundener Sprung), widerspricht dem PO-Entscheid zur Alterungsgrenze.

### Dependencies

Leser: `compare_alert._vorbereite_ort`, `alert_preview_hours.compare_preview_point`. Schreiber neu: `compare_alert._check_one_preset` Versandschleife. Go-Cleanup per Präfix (`internal/store/compare_preset.go:331-357`), Konto-Löschung/Export per Verzeichnis — unverändert gültig.

### Tests (neu, Kern-Schicht, ohne Mock-Theater; echte Dateien im tmp-Datenverzeichnis)

Zustellung je Kanal/Gruppe/Teilzustellung; nichts zugestellt → kein Merker; Basis = neuester je Kanal / ältester über Kanäle; neues Briefing schlägt älteren Alarm-Anker; Alarm-Anker mit anderem target_date verworfen; > 26 h verworfen; Altbestand ohne Kanaldatei; Melde-Gedächtnis unberührt; Vorschau = Alarm-Basis; Preset-Löschung entfernt Kanaldateien.

### Open Questions / Nicht-Ziele

- Keine PO-Frage offen: PO-Entscheide 2026-08-19 decken Kanal-Basis, Zustellungsbindung und Alterungsgrenze.
- Nicht-Ziel: Melde-Gedächtnis (`alert_state`) bleibt kanallos (wie Trip); `reference_at` bleibt EIN Wert (kanalweise Ausweisung = #1948 S6); Trip-Korrektur = #3481.
- Spec prüfen: `fresh_point.target_date` auf dem Schreibpfad belegt? Sonst aus der Basis ergänzen.
- Bekannte Grenze: Briefing-Anker aus Exception-Pfad kann als „neuester“ gewählt werden, obwohl nicht zugestellt (bewusste #1629-Absicherung).
