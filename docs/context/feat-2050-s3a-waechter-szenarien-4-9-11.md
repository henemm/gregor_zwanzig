# Context: #2050 Scheibe S3a — Wächter für Szenarien 4, 9, 11

## Request Summary

Issue #2050 fordert für drei der zwölf Szenarien einen echten Wächter auf der
`AlarmPruefstrecke`: Sz 4 (Verschärfung überholt Sperrzeit, A-3), Sz 9 (Tagesbezug
über Zeitzonen, B-2), Sz 11 (Mandantentrennung, D-1/D-2). Laut Vorrecherche vom
22.08. reine Testarbeit, kein Produktivcode. Explore-Recherche (dieser Workflow)
bestätigt das für Sz 9 und Sz 11 — für Sz 4 ergibt sich eine wichtige Korrektur.

## 🔴 Korrektur zu Sz 4: bereits durch #2065 bewacht

`tests/tdd/test_radar_cooldown_overtake.py` (950 Zeilen, frisch gemergt mit
`34a0af8f`) prüft **exakt** das Sz-4-Verhalten bereits über die echte
`AlarmPruefstrecke`, kein Mock:
- `test_ac1_verschaerfung_ueberholt_die_laufende_sperrzeit_auf_allen_kanaelen`
- `test_ac5_der_durchbruch_wirkt_auch_an_der_entdopplung`
- AC-2 bis AC-14 decken Ruhezeit-Unbrechbarkeit, Tagesbudget, fehlende
  Vergleichsbasis, Protokollzeile ab.

Die S2a-Spec (`docs/specs/modules/alarm_szenarien_waechter_2_3.md`) dokumentiert
zusätzlich, dass ihr AC-3 (identisch zu Sz 4) dort gebaut, ROT gemessen und "nach
#2065 ausgelagert" wurde — jetzt durch #2065 geschlossen.

**Folge für den Zuschnitt:** Ein neuer Wächter, der den Radar-Zweig von Sz 4 erneut
komplett prüft, wäre Duplikation. Sinnvoll bleibt ein **schlanker Kontrast-Test**:
derselbe Eskalationsversuch im **deviation-Zweig** zeigt, dass dort — anders als im
Radar-Zweig — **keine** Überholung stattfindet (`triggered_count == 0`, Grund bleibt
`REASON_COOLDOWN`). Das ist die bisher unbewachte Grenze, die die Vorrecherche als
⚠️ markiert hatte ("gilt NUR für den Radar-Zweig").

## Related Files

| File | Relevance |
|------|-----------|
| `tests/helpers/alarm_pruefstrecke.py` | Prüfstrecke — `AlarmPruefstrecke.lauf()`, API siehe unten |
| `tests/tdd/test_alarm_szenario_gewitter_vorverlegung.py` | Direktes Vorbild für Sz 11 (zwei `user_id`s, Kontroll-/Testnutzer) |
| `tests/tdd/test_alarm_szenario_briefing_ueberholung_zeitreihe.py` | Vorbild für Zeitreihen (Sz 4 wäre analog) |
| `tests/tdd/test_radar_cooldown_overtake.py` | #2065 — bewacht Sz 4 im Radar-Zweig bereits vollständig |
| `src/services/alert_gate.py:421-446` | `radar_overtakes_cooldown()` — Faktor 2.0 + ≥2.0mm absolut |
| `src/services/trip_alert.py:1438-1462` | Wirkort Radar-Zweig (`_ueberholt_sperrzeit`) |
| `src/services/trip_alert.py:306-308` | Deviation-Zweig: harter `return False`, KEINE Überholung |
| `src/services/trip_alert.py:991-1013` | `_is_throttled_with_cooldown` — reine Boolean-Prüfung im Deviation-Zweig |
| `src/utils/timezone.py:138-143` | `day_offset()` |
| `src/output/renderers/alert/render.py:214-242` | `_time_with_day` — Wortbildung Tagesbezug |
| `src/output/renderers/alert/render.py:758-771` | `_sms_onset_time` — SMS-Kurzform |
| `src/output/renderers/alert/model.py` | 6× `*_day_offset`-Felder (nicht 5 wie Vorrecherche — `event_end_day_offset` kam über #2051 S1 dazu) |
| `src/services/alert_daily_limit.py:34-36` | Tageszähler, `get_data_dir(user_id)` |
| `src/services/throttle_store.py:57-63` | Sperrzeit, Instanz pro `user_id` |
| `src/services/alert_state.py:50-56` | Melde-/Identitätsgedächtnis, `get_data_dir(user_id)` |
| `src/services/alert_log.py:389,557` | Protokoll — `append_entry`, `read_undelivered` |
| `src/app/loader.py:1153-1167` | `get_data_dir()` — Regex-validiert, kein globaler Cache |
| `src/services/radar_cache.py:73-84` | ⚠️ prozessweiter Cache, geschlüsselt NUR über lat/lon/region/elevation — OHNE user_id |

## Existing Patterns

- **Prüfstrecke-API** (`tests/helpers/alarm_pruefstrecke.py`, 189 Zeilen):
  ```python
  class AlarmPruefstrecke:
      def __init__(self, *, user_id: str, settings: Optional[Settings] = None,
                   throttle_hours: int = 2) -> None: ...
      def lauf(self, *, at: datetime, zweig: Literal["deviation","official","radar"],
                trip: "Trip", cached_weather=None, fresh_weather=None,
                official_notices=None, radar_service=None) -> AlarmPruefstreckeLauf: ...

  @dataclass
  class AlarmPruefstreckeLauf:
      triggered_count: int
      mail: list       # (subject, body)
      telegram: list
      sms: list
      premium_sms: list
  ```
  - `zweig="deviation"` → `check_and_send_alerts(...)`
  - `zweig="radar"` → `check_radar_alerts()`
  - Zeitsteuerung nur über `at=` (`freeze_time(at)` intern), kein separater Reset-Parameter.
  - Jeder `.lauf()` resettet vier **prozessweite** Singleton-Caches (Radar/Wetter/
    Thunder-Window/Telegram-Rate-Limit) — die vier fachlichen Zustandsspeicher
    (Tageszähler, Sperrzeit, Identitätsgedächtnis, Protokoll) bleiben über Läufe
    hinweg absichtlich erhalten (Kontinuität via `get_data_dir(user_id)`, wie in Produktion).
  - **Zwei Nutzer parallel ist kein Feature der Prüfstrecke** — Muster: zwei
    `AlarmPruefstrecke`-Instanzen (je `user_id`), Läufe **sequenziell**
    aufgerufen (nicht Threads) wegen der user_id-losen Radar-Caches. Vorbild:
    `test_alarm_szenario_gewitter_vorverlegung.py::test_ac7_...`.
- **Hilfsfunktionen** (aus `test_alarm_pruefstrecke_selbstschutz.py`):
  `_AT` (fixer Zeitpunkt), `_settings_all_channels()`, `_write_premium_profile(uid, at)`,
  `_write_tier(uid, tier)`, `_radar_trip(uid, trip_id, **flags)`; `_clean_user(uid)`
  aus `test_952_onset_alert_fidelity.py:180`.
- **alert_log-Struktur:** `append_entry()` schreibt `channels_not_sent: [{channel, reason}]`
  (kein Top-Level `gate_reason`). `append_suppressed_entry()` erzwingt `gate_reason`
  als Pflichtparameter, Ziel-Liste `not_delivered`. Lesen über
  `read_undelivered(user_id, entity_id=..., entity_type=..., since=...) -> list[UndeliveredIncident]`,
  `.reasons: tuple[str, ...]`. Konstanten: `REASON_COOLDOWN`, `REASON_QUIET_HOURS`,
  `REASON_DAILY_LIMIT`, `REASON_EVENT_DUPLICATE`, `REASON_NOWCAST`, `REASON_OFFICIAL_ALERT`.
- **Spec-Format** (S1/S2a): Given/When/Then + eingerückte `- Test:`-Zeile,
  `## Nicht Ziel`, `## Known Limitations`, `## Changelog` mit datierten Nachträgen.

## Dependencies

- Upstream: `AlarmPruefstrecke` (S1), `_clean_user`, Settings-/Trip-Fabriken aus
  bestehenden S2a-Tests.
- Downstream: keine — reine Testdateien, nichts hängt von ihnen ab.

## Existing Specs

- `docs/specs/modules/alarm_pruefstrecke.md` (S1)
- `docs/specs/modules/alarm_szenarien_waechter_2_3.md` (S2a — dokumentiert die
  Sz-4-Auslagerung nach #2065)
- `docs/specs/modules/fix_2065_verschaerfung_ueberholt_sperre.md` (#2065 — bewacht
  den Radar-Zweig von Sz 4 bereits vollständig)

## Risks & Considerations

- **Duplikation bei Sz 4:** voller Wächter würde #2065 wiederholen. Spec muss den
  Sz-4-Umfang auf den Kontrast (deviation-Zweig überholt NICHT) reduzieren und
  explizit auf `test_radar_cooldown_overtake.py` als bereits bestehenden Nachweis
  für den Radar-Zweig verweisen.
- **Sz 11 Nebenläufigkeit:** echte Parallelität (Threads) ist wegen der user_id-losen
  Radar-Caches nicht vorgesehen — Test muss sequenziell zwei Instanzen fahren und
  darf keine Thread-Parallelität suggerieren.
- **Sz 9 Feldzahl:** sechs `*_day_offset`-Felder, nicht fünf — `event_end_day_offset`
  kam über #2051 S1 neu dazu. Spec sollte offenlassen, welche Felder der konkrete
  Testfall (Radar-Onset über Mitternacht) tatsächlich durchläuft, statt alle sechs
  vorab zu behaupten.
- Keine Kollision mit laufenden Sessions (S6, #2073, #2054, #2051) — reine Testdateien,
  keine Produktivcode-Berührung.

## Analysis

### Type
Feature (Test-Wächter, kein Bug)

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `tests/tdd/test_alarm_szenario_sperrzeit_verschaerfung.py` | CREATE | Sz 4 — schlanker Kontrast: deviation-Zweig überholt die Sperrzeit NICHT (Radar-Zweig bereits durch #2065 bewacht) |
| `tests/tdd/test_alarm_szenario_tagesbezug_zeitzone.py` | CREATE | Sz 9 — Prüflauf 23:50, Ereignis 00:23, korrekter Tagesbezug/Etappentag im Alarmtext |
| `tests/tdd/test_alarm_szenario_mandantentrennung.py` | CREATE | Sz 11 — zwei `user_id`s, sequenzielle Läufe, kein geteilter Zustand über die vier Speicher |
| `docs/specs/modules/alarm_szenarien_waechter_4_9_11.md` | CREATE | Spec mit ACs |
| `docs/context/feat-2050-s3a-waechter-szenarien-4-9-11.md` | MODIFY | dieses Dokument |

Kein Produktivcode wird geändert.

### Scope Assessment
- Files: 3 Testdateien + 1 Spec (neu)
- Estimated LoC: +350/−0 (deutlich kleiner als S2a, da Sz 4 auf Kontrast reduziert)
- Risk Level: **LOW** — keine Produktivcode-Berührung, keine Dateikollision mit laufenden Sessions

### Technical Approach

Alle drei Wächter laufen über die echte `AlarmPruefstrecke` (S1), nach dem Muster aus
`test_alarm_szenario_gewitter_vorverlegung.py`:

- **Sz 4:** ein Lauf im `zweig="deviation"`, der bei aktiver Sperrzeit (`ThrottleStore`
  vorbelegt) eine deutliche Verschärfung anbietet → `triggered_count == 0` erwartet,
  `read_undelivered(...)` zeigt `REASON_COOLDOWN`. Ergänzend ein Kommentar/Verweis auf
  `test_radar_cooldown_overtake.py` als Nachweis für den Radar-Zweig, damit die Spec
  nicht behauptet, hier würde der Radar-Fall neu bewiesen.
- **Sz 9:** ein `zweig="radar"`-Lauf um 23:50 (Prüfzeitpunkt-Zeitzone des Trips) mit
  einem Frame, dessen abgeleitete Ereigniszeit auf 00:23 des Folgetags fällt.
  Assertion auf den gerenderten Text (Mail/Telegram/SMS) — Tagesbezug muss sichtbar
  sein (z.B. "morgen" / Wochentagskürzel je nach dem, was `_time_with_day` tatsächlich
  produziert — vor Spec-Schreiben kurz den Renderer-Output an einem Beispiel prüfen,
  keine der sechs `*_day_offset`-Felder vorab annehmen).
- **Sz 11:** zwei `AlarmPruefstrecke`-Instanzen (`user_id` A, B), gleiche Region/Trip-
  Parameter, sequenzielle Läufe (A dann B dann A), Assertion, dass Nutzer A's
  Sperrzeit/Tageszähler/Protokoll unverändert bleiben, nachdem Nutzer B ausgelöst hat
  (und umgekehrt) — je Speicher eine eigene Prüfung, nicht nur "zwei Mails kamen an".

### Dependencies
- Upstream: `AlarmPruefstrecke`, `_clean_user`, bestehende Settings-/Trip-Fabriken.
- Downstream: keine.

### Open Questions
- [ ] Sz 9: exakter erwarteter Textbaustein für "Ereignis morgen" — wird beim Testbau
  am echten Renderer-Output verifiziert, keine Blockfrage an den PO nötig.
