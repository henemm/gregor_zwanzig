# Context: feat-2050-sz12-fehlende-vergleichsbasis

## Request Summary
Epic #2050, Szenario 12 (Anforderungen D-2, E-1): Ein laufender Trip ohne gültige Vergleichsbasis
(Alarm-/Briefing-Anker) darf nie „stilles Nichts" erzeugen — entweder kommt ein Alarm, oder ein
**sichtbarer, benannter Grund** steht im Alarmprotokoll. Heute landet der Fehl-Anker nur in einer
Diagnosedatei (`alert_anchor_rejected.jsonl`), die ausschließlich der Go-Health-Endpoint als Streak auswertet.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py` :854 `check_all_trips`, :946 `_get_cached_weather(..., tagesgleicher_anker_noetig=True)`, :965-972 leeres `cached` ⇒ nur amtlich, dann `continue` | Stelle des stillen Nichts im Abweichungs-Zweig |
| `src/services/trip_alert.py` :1013-1175 `_get_cached_weather` | Anker-Reihenfolge: `load_dated` (1081) → rollierend je Kanal (1107, 1219-1254) → undatiert `load()` (1112). Ablehnungen `not_briefing_backed` (1140), `too_old` (1155), `wrong_day` (1162) |
| `src/services/trip_alert.py` :1256-1285 `_report_missing_anchor` | `missing` nur bei laufendem Trip (sonst DEBUG, #1199-Muster) |
| `src/services/trip_alert.py` :381-408 `_protokolliere_unterdrueckung` | fail-soft Trip-Wrapper um `append_suppressed_entry` (Beispiel :478-481) |
| `src/services/trip_alert.py` :2578/2618/2621 `check_official_alert_triggers` | amtlicher Zweig braucht den Anker nur für die Routengeometrie; ohne Anker ebenfalls still ⇒ `_report_missing_anchor` feuert ZWEIMAL pro Lauf |
| `src/services/trip_alert.py` :1612 `check_radar_alerts` | Radar ist anker-unabhängig (Segment über `_resolve_alert_segment`) |
| `src/services/alert_briefing_anchor.py` :55-71 `record_alert_anchor_rejected` | Diagnosedatei, vier Gründe dokumentiert (:66-71); :238-256 `undelivered_since_last_briefing` |
| `src/services/alert_log.py` :47-83 REASON_*, :331-388 `_E1_FIELD_TYPES`/`_apply_e1_fields`, :391-518 `append_entry` (O3/D4 :425-440), :536-640 `append_suppressed_entry`, :651 `DEDUP_WINDOW=2min`, :703 `read_undelivered` | Zielort des Grundes; Gründe sind freie Strings, additiv ohne Migration |
| `src/output/renderers/email/undelivered_hint.py` :48-67 `_REASON_LABELS`, :73-96 `_REASON_BLOCK` | Neuer Grund MUSS hier ein deutsches Label + Block-Zuordnung bekommen, sonst roher Code in der Mail |
| `tests/tdd/test_alert_undelivered_hint.py` :2246-2260 `_REASON_EXPECTATION` (AC-18) | handgepflegter Katalog-Wächter |
| `internal/scheduler/briefing_health.go` :312-335 | Einziger Leser der Diagnosedatei (nur `ts`, Streak 60 Min) — darf nicht brechen |
| `internal/store/log.go` :51-98 | Go liest nur `entries`, kein `reason` — neuer Grund braucht dort nichts |
| `src/services/compare_alert.py` :489-580 | Ortsvergleich-Pendant: `_anchor_too_old` nur Warning; leerer Anker = Bootstrap → vermutlich ebenfalls still |
| `tests/helpers/alarm_pruefstrecke.py` :111, :163, :196-200 | Harness; `zweig="deviation"` ruft `check_and_send_alerts` DIREKT — der Fehl-Anker-Pfad ist so NICHT erreichbar ⇒ neuer Zweig über `check_all_trips` nötig |
| `tests/tdd/test_alert_anchor_day_guard.py` :170, :474, :515, :551, :700, :756, :1363, :1498 | Bestehende Anker-Wächter (Diagnosezeile, `missing`, nicht gestartet bleibt still, amtlich nicht stummgeschaltet) |

## Existing Patterns
- **S3b / S4a:** benannter Unterdrückungsgrund als neue `REASON_*`-Konstante, geschrieben über `append_suppressed_entry` → `not_delivered`, Label in `undelivered_hint.py`.
- **S4b / S6:** additive Zusatzfelder über `_E1_FIELD_TYPES`/`_apply_e1_fields` (None wird weggelassen, falscher Typ verworfen, nie Exception).
- **#1661 C2:** nicht gestarteter Trip ⇒ kein Diagnoseeintrag (Dauerrauschen vermeiden).
- Szenario-Wächter: `tests/tdd/test_alarm_szenario_*.py` mit `AlarmPruefstrecke`.

## Dependencies
- Upstream: `SnapshotService` (`load_dated`/`load`), rollierende Kanal-Marker, `_effective_alert_channels`, `get_data_dir(user_id)`.
- Downstream: Briefing-Hinweis „nicht zugestellt" (`notification_service.py:520`, `scheduler_dispatch_service.py:565`), Go-Health-Streak, Cockpit (`internal/handler/cockpit.go:22`, liest nur `entries`).

## Existing Specs
- `docs/specs/modules/alarm_pruefstrecke.md`, `feat_2050_s3b_budget_und_unterdrueckungsgrund.md`, `feat_2050_s4a_radar_teilausfall.md`, `alarm_protokoll_vorwarnzeit.md` (S6/E-1)
- Anker-Historie: `fix_1661_anker_vom_falschen_tag.md`, `fix_1699_anker_ohne_briefing.md`, `fix_1987_kanal_anker.md`, `fix_1629_briefing_anker_versandfehler.md`
- ADRs: 0056 (rollierender Alarm-Anker), 0009 (Alarme als Abweichungs-Wächter — ohne Briefing keine Vergleichsbasis), 0018, 0021

## Risks & Considerations
- **Rauschen:** `record_alert_anchor_rejected` schreibt bei jedem Lauf (15/30 Min — Kommentare widersprechen sich). Direkt ins Protokoll übernommen wären das 48–96 Einträge/Tag/Trip; `DEDUP_WINDOW` (2 Min) fasst nichts zusammen ⇒ Entdopplung je Trip/Tag/Grund oder Zustandswechsel-Regel nötig.
- **Doppelschreibung:** ohne Anker ruft der Lauf `_report_missing_anchor` zweimal (Abweichung + amtlich).
- **Kein Briefing ⇒ kein Hinweis:** `undelivered_since_last_briefing` liefert `[]` ohne Briefing-Zeitstempel — der Grund wäre im Protokoll, aber im Briefing-Hinweis unsichtbar. Klären, wo „sichtbar" gemessen wird.
- **„Eindeutige Alarmlage" ist ohne Anker gar nicht gemessen:** ohne Anker wird kein frisches Wetter geholt. Möglich sind nur Grund + Werte (Ankerdatum vs. heute, Alter in h), keine Wettergrößen. Variante „trotzdem frisch holen und gegen Schwellen prüfen" wäre eine Verhaltensänderung (ADR-0009!) und damit eine Entscheidungsfläche.
- **Stille Kanal-Marker-Verwerfungen** (nur DEBUG, :1200-1216) können `missing` melden, obwohl Marker existieren.
- **Ortsvergleich-Parität:** Compare-Seite hat dasselbe stille Nichts (zu alter/fehlender Anker) und keinerlei Diagnose — Teilungs-Invariante beachten.
- **Go-Diagnose-Streak** darf durch Umbau nicht verschwinden (Health-Endpoint, `alert_anchor_health_test.go`).
- Leser des neuen Grundes außerhalb Python: keine (Go/Frontend lesen `reason` nicht).

## Analysis

### Type
Feature (Epic #2050 Szenario 12, D-2/E-1; Checkbox in #2261 Teil A)

### Verifizierte Befunde
- `check_all_trips` läuft alle **15 Min** (`internal/scheduler/scheduler.go:260`; Docstring trip_alert.py:858 „30 Min" ist veraltet).
- Leerer Anker ⇒ `trip_alert.py:965-972`: nur amtlicher Versand, dann `continue` — **kein** alert_log-Eintrag. Gründe `missing`/`not_briefing_backed`/`too_old`/`wrong_day` landen nur in `diagnostics/alert_anchor_rejected.jsonl`.
- Doppel-Diagnose bestätigt: amtlicher Zweig ruft `_get_cached_weather(tagesgleicher_anker_noetig=False)` (trip_alert.py:2618) ⇒ `missing` bis zu 2× je Lauf.
- `append_suppressed_entry` (alert_log.py:536) hat **keine** Schreib-Entdopplung; `DEDUP_WINDOW` wirkt nur beim Lesen. `gate_reason` ist Pflicht (ValueError bei leer) und ist der sichtbare Grund-Code (`not_delivered[].reason`).
- Sichtbarkeit: Gründe erscheinen nur im **E-Mail**-Briefing-Hinweis (`undelivered_hint.py`); Go/Cockpit lesen `reason` nicht, kein Frontend-Leser. `undelivered_since_last_briefing` (alert_briefing_anchor.py:238-256) liefert ohne bisherigen Briefing-Zeitstempel `[]` (bewusst, AC-7 aus #1461: sonst kippt Historie in die erste Mail) ⇒ der Fall `missing` (nie ein Briefing) wäre heute nirgends sichtbar.
- ADR-0009/0056: Alarme sind Abweichungs-Wächter; ohne Anker KEIN frisches Holen gegen absolute Schwellen. Szenario 12 wird über den Zweig „protokollierter sichtbarer Grund" erfüllt — keine ADR-Änderung.
- **Ortsvergleich hat dasselbe stille Nichts** (`compare_alert.py:489-580`): leerer Anker (`cached=[]`, „Bootstrap") und `_anchor_too_old` (>26 h, nur `logger.warning`) ⇒ kein Alarm, kein Eintrag. Beides heilt erst mit dem nächsten Briefing-Versand, nicht im nächsten Lauf ⇒ echtes stilles Nichts. Ein fail-soft Protokoll-Wrapper existiert bereits (`compare_alert.py:97` `_protokolliere_unterdrueckung`, entity_type="compare").

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_log.py` | MODIFY | `REASON_NO_REFERENCE_BASIS = "no_reference_basis"`; additives typgeprüftes Feld für den Untergrund (`_E1_FIELD_TYPES`-Muster) + Ankerdatum/`reference_at`; Lese-Helfer „schon heute protokolliert?" (Nutzer, Entity, Tag, Untergrund) auf dem bestehenden alert_log.json des Nutzers |
| `src/services/trip_alert.py` | MODIFY | in `_get_cached_weather` an den Ablehnungsstellen (:1125/:1172 bzw. `_report_missing_anchor`) zusätzlich Protokolleintrag — nur bei `tagesgleicher_anker_noetig=True`, nur laufender Trip, entdoppelt; fail-soft über bestehenden `_protokolliere_unterdrueckung`-Weg |
| `src/services/compare_alert.py` | MODIFY | leerer Anker + `_anchor_too_old` ⇒ derselbe Grund über den vorhandenen Wrapper, je Preset/Tag/Untergrund entdoppelt |
| `src/services/alert_briefing_anchor.py` | MODIFY | Ersatz-Fenster ohne Briefing-Zeitstempel: NUR `no_reference_basis`-Einträge (nicht die Gesamthistorie ⇒ AC-7 aus #1461 bleibt gewahrt) |
| `src/output/renderers/email/undelivered_hint.py` | MODIFY | deutsches Label + Block-Zuordnung für `no_reference_basis` |
| `tests/tdd/test_alert_undelivered_hint.py` | MODIFY | Katalog-Wächter `_REASON_EXPECTATION` ergänzen |
| `tests/tdd/test_alarm_szenario_fehlende_vergleichsbasis.py` | CREATE | Szenario-Test über `check_all_trips` / `check_all_compare_presets` (Fehl-Anker vom Produkt erzeugt, nie per Fixture eingelegt) |
| `docs/specs/modules/feat_2050_sz12_fehlende_vergleichsbasis.md` | CREATE | Spec |

Unverändert und als Regressionswächter: `diagnostics/alert_anchor_rejected.jsonl` + Go-Health-Streak (`briefing_health.go:312-335`, `alert_anchor_health_test.go`), `tests/tdd/test_alert_anchor_day_guard.py`.

### Scope Assessment
- Files: 5 produktiv + 2 Tests + Spec
- Estimated LoC: +120–160 / -0 (unter 250)
- Risk Level: MEDIUM — zentraler Alarmlauf, aber rein additiv (Protokoll + Hinweis), kein Auslöseverhalten ändert sich

### Technical Approach
1. **Ein** Grund `no_reference_basis` statt vier; Untergrund (`missing`/`not_briefing_backed`/`too_old`/`wrong_day`; Compare: `missing`/`too_old`) als eigenes typgeprüftes Feld, dazu Ankerdatum bzw. `reference_at` und Bezugstag (D-2 „Werte, die zur Entscheidung führten"; E-1 „Vergleichsbasis"). `gate_reason` = `no_reference_basis` (kein zusammengesetzter String).
2. Schreiben dort, wo der Grund entsteht (`_get_cached_weather`), nur im Δ-Aufruf (`tagesgleicher_anker_noetig=True`) ⇒ amtlicher Zweitaufruf schreibt nie, Doppel entfällt ohne Zusatzlogik.
3. Nur laufender Trip (Muster #1661 C2) — kein Rauschen vor dem Aufbruch.
4. Entdopplung: höchstens ein Eintrag je Nutzer + Entity + Tag + Untergrund. Tag = dasselbe `today`, das der Lauf bereits verwendet. Nur das alert_log des jeweiligen Nutzers (Szenario 11: kein geteilter Zähler) ⇒ Zwei-Nutzer-AC.
5. Sichtbarkeit: Briefing-Hinweis bekommt ein Ersatz-Fenster ohne Briefing-Zeitstempel, das ausschließlich `no_reference_basis` zeigt ⇒ das erste zugestellte Briefing nennt den Grund.
6. Ortsvergleich im selben Ticket über dieselben Bausteine (Teilungs-Invariante, Parität #1533).
7. Diagnosedatei bleibt unverändert beschrieben.

### Dependencies
- `SnapshotService` (`load_dated`/`load`), rollierende Kanal-Marker, `_effective_alert_channels`/`effective_alert_channels`, `get_data_dir(user_id)`, `last_briefing_at`.
- Leser: `notification_service.py:520`, `scheduler_dispatch_service.py:565` (beide via `undelivered_since_last_briefing`).

### Bewusst nicht im Scope (Bestand, kein neuer Befund dieses Tickets)
- Nicht-zugestellt-Hinweis existiert für **keinen** Grund in Telegram/SMS/Premium-SMS — betrifft alle bestehenden Gründe gleich; Kanalparität des Hinweises ist eigenes Thema.
- Kanal-Marker-Verwerfungen nur auf DEBUG (trip_alert.py:1200-1216) können `missing` melden, obwohl Marker existieren.

### Open Questions
- [ ] Keine Produktfrage offen. Label-Wortlaut („Kein Alarm möglich: noch keine Vergleichsbasis / Vergleichsbasis vom TT.MM. zu alt") wird in der Spec mit den ACs freigegeben.
