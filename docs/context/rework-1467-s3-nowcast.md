# Context: rework-1467-s3-nowcast

**Issue:** #1467 Scheibe **S3** von vier (Epic #1458, Teil 2 von #1460)
**Vorgänger:** S1 live (`49cf1c22`, `entity_id`+`entity_type`), S2 vollständig live (AG1–AG6, zuletzt `b55bcc49`)
**Track:** Full Process (Intake 5/6, PO-bestätigt 2026-08-08)
**Nachfolger:** S4 (amtlich + `_day_window_end()`-Mitternachtsfenster); danach #1594

## Request Summary

Der **Nowcast-Pfad** (Regen-/Gewitter-Onset) des Ortsvergleichs wird an die gemeinsame
Ablaufsteuerung angeschlossen. Nutzersichtbarer Gewinn: Der Ortsvergleich-Nowcast bekommt die
**Tages-Obergrenze** (hat heute keine — die Bremse gegen Meldungsfluten fehlt), benutzt die
**gemeinsame Sperrzeit** statt einer eigenen JSON-Datei, und die **Ruhezeiten-Prüfung wandert
vor die Datenbeschaffung** (spart Abruf-Kontingent, gleiches Meldeverhalten).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/compare_radar_alert.py` (262 Z.) | **Der zu ändernde Pfad.** Ablauf `_check_one_preset()` `:85-178`. Eigene Sperrzeit-Datei `:67`, eigener Cooldown-Check `:104-110`, Ruhezeit **nach** der Erkennung `:117-124`, **kein** `alert_daily_limit` |
| `src/services/trip_alert.py` (1292 Z.) | **Die Vorlage.** Radar-Zweig `check_radar_alerts()` `:701-938`. Reihenfolge Ruhezeit `:748` → Sperrzeit `:752` → Tageslimit `:761` → Abruf `:767` → Erkennung `:780`. `ThrottleStore.record("radar", …)` `:935`, `increment()` `:930` — beide **erst nach** erfolgreicher Zustellung |
| `src/services/throttle_store.py` (Scopes `trip`/`radar`/`compare_preset`) | Zielspeicher der Sperrzeit. Ein File `throttle_state.json` je Nutzer, `fcntl`-Lock, atomarer Write. Legacy-Migration `_migrate_flat_file()` `:184` — **genau das Format** der abzulösenden Datei. ⚠️ Fallstrick s. Risiken R1 |
| `src/services/alert_daily_limit.py` | Tages-Obergrenze. `is_allowed(user_id, now, reason=None)` `:61`, `increment()` `:77`. Zähler `alert_daily_count.json`, Tageswechsel nach **Europe/Vienna**. `_FORECAST_CHANGE_RESERVE = {2:1, 4:2}` `:58` — NowCast-Reserve aus #1555 |
| `src/services/deviation_alert_engine.py` | `is_quiet_hours(now, quiet_from, quiet_to, context_label)` `:78` — die kanonische Fassung, von allen vier Pfaden gerufen. `is_cooldown_active()` `:140` (heute die Cooldown-Prüfung des Compare-Nowcast) |
| `src/services/compare_alert_guard.py` | `is_silenced(preset)` `:39` — sitzt bereits an `compare_radar_alert.py:95`, **vor** allem anderen (AG6) |
| `src/services/compare_alert_channels.py` | `effective_compare_channels()` `:28` — sitzt bereits an `compare_radar_alert.py:133` |
| `src/services/alert_log.py` | `append_entry()` `:135`. Gründe `REASON_NOWCAST` `:56`; **ungenutzt bisher:** `REASON_QUIET_HOURS` `:47`, `REASON_DAILY_LIMIT` `:48`, `REASON_COOLDOWN` `:49` |
| `api/routers/scheduler.py` | `POST /api/scheduler/compare-radar-alert-checks` `:90-97` (Auslöser für die Staging-Verifikation), `radar-alert-checks` `:80-87` |
| `internal/scheduler/scheduler.go` | Cron `*/15` Job `compare_radar_alert_checks` `:320-324` und `radar_alert_checks` `:305-309` |
| `tests/tdd/test_compare_radar_alert.py` (754 Z., 10 Tests) | Bestandsschutz des Compare-Nowcast |
| `tests/tdd/test_data_root_migration_services.py:81` | Verankert den Pfad `compare_radar_alert_throttle.json` — zieht bei einer Ablösung mit |

## Ist-Stand: Trip-Nowcast vs. Ortsvergleich-Nowcast (gemessen 2026-08-08)

| | Trip (`trip_alert.py:701-938`) | Ortsvergleich (`compare_radar_alert.py:85-178`) |
|---|---|---|
| **Reihenfolge** | Ruhezeit → Sperrzeit → **Tageslimit** → Abruf → Erkennung | Riegel → Sperrzeit → **Abruf + Erkennung** → Ruhezeit |
| **Sperrzeit** | `ThrottleStore`, Scope `"radar"`, Key `trip.id`, `fcntl`-Lock, atomar | **eigene Datei** `compare_radar_alert_throttle.json` `:67`, flaches `{preset_id: iso}`, **kein Lock, kein atomarer Write** (`write_text` `:259`) |
| **Tages-Obergrenze** | `is_allowed(…, reason="nowcast")` `:763`, `increment()` `:930` nach Zustellung | **fehlt vollständig** — Modul nicht importiert |
| **Sperrdauer** | `trip.alert_cooldown_minutes`, sonst 120 Min | `preset["alert_cooldown_minutes"]`, sonst 120 Min (`_DEFAULT_COOLDOWN_MINUTES` `:36`) |
| **Onset-Schwelle** | `radar_alert_due(result, threshold_min=20)` `:780` | dieselbe Funktion, importiert aus `trip_alert` `:27`, `_RADAR_ONSET_THRESHOLD_MIN=20` `:31` |

**Bereits geteilt und in dieser Scheibe nicht anzufassen:** `is_silenced` (AG6), `effective_compare_channels` (AG1/AG4), `radar_alert_due`, `DeviationAlertEngine.is_quiet_hours`, `AlertStateService`, `alert_log.append_entry` (seit S1 mit `entity_id`/`entity_type`), `NotificationService.send_multi_location_radar_alert`, Dringlichkeit + Kanal-Schwelle (#1461 S3a/S3b).

**Noch wortgleich dupliziert** über die drei Compare-Dateien: `_load_presets()`
(`compare_radar_alert.py:241`, `compare_alert.py:536`, `compare_official_alert.py:297`),
`_notification_service_for()` (`:221`/`:520`/`:283`), Kennungsschema `f"{preset_id}:{loc.id}"`.

## Existing Patterns

- **Es gibt bis heute KEINEN gemeinsamen Melder-Durchlauf.** Fünf `*/15`-Cronjobs → fünf
  HTTP-Endpunkte → vier Service-Klassen. S1 und S2 haben *Bausteine* geteilt, nicht den Ablauf
  zusammengelegt. Das Issue-Ziel „ein Melder-Durchlauf, parametriert über den Kontext" ist noch
  offen — S3 entscheidet, ob es ein geteilter **Freigabe-Baustein** (Ruhezeit → Sperrzeit →
  Tageslimit) wird oder wieder nur Einzelaufrufe.
- **Riegel früh in der Schleife, vor der Datenbeschaffung** — Vorbild AG2
  (`docs/context/fix-1467-ag2-ruhezeit-vor-abruf.md`) und `compare_official_alert.py:105-113`.
  Wirkung damals: „gleiches Meldeverhalten, weniger Abrufe".
- **Zähler und Sperrzeit erst nach erfolgreicher Zustellung schreiben** — Trip macht es so
  (`:930`/`:935`), Compare-Nowcast auch (`:175-177`). Diese Invariante darf nicht kippen.
- **Legacy-Migration statt Umschreiben der Historie** — `ThrottleStore._migrate_flat_file()`,
  Präzedenz aus S1 („Lese-Regel statt Migration", BUG-DATALOSS-GR221).
- **Ein Baustein, mehrere Aufrufer** statt Zweitfassung (ADR-0021, Trip/Compare-Teilungsregel).

## Dependencies

**Upstream:** `ThrottleStore`, `alert_daily_limit`, `user_tier.daily_alert_limit`,
`DeviationAlertEngine`, `AlertStateService`, `alert_log`, `NotificationService`,
`compare_alert_guard`, `compare_alert_channels`, `alert_urgency`, `alert_channel_threshold`,
`RadarService.get_nowcast`, `utils/timezone.resolve_location_tz`.

**Downstream:** `api/routers/scheduler.py:90-97`, `internal/scheduler/scheduler.go:320-324`,
Alarm-Protokoll → Cockpit/Archiv-Statistik (Go), `/api/scheduler/status`.

## Existing Specs

- `docs/specs/modules/rework_1467_s1_alarm_kennung.md` — Kennung (live)
- `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` v1.2 — S2, AC-1…AC-28 (live)
- `docs/specs/modules/throttle_store.md` — Zielspeicher der Sperrzeit
- `docs/specs/modules/alert_daily_limit.md` + `docs/specs/modules/fix_1555_nowcast_alert_priority.md` — Tagesbudget und NowCast-Reserve
- `docs/specs/modules/fix_1479_ruhezeit_wurzel.md` — Ruhezeit-Aufrufstelle 3 ist `compare_radar_alert.py`
- `docs/specs/_archive/modules/issue_1041b_compare_radar_alert_service.md` — **archiviert**; von dort stammt die heutige Zusicherung „Ruhezeit erst nach der Erkennung" (Codekommentar `:116`). Archivablage sagt nichts über Gültigkeit — die Umkehrung ist eine bewusste Entscheidung und braucht ein eigenes AC
- ADR-0021 — geteilter Auswertungskern

## Risks & Considerations

1. **🔴 R1 — Die Legacy-Migration des `ThrottleStore` läuft für Bestandsnutzer NICHT mehr.**
   `_migrate_if_needed()` `:162-164` bricht sofort ab, wenn `throttle_state.json` bereits
   existiert. Für alle drei realen Nutzer existiert sie (gemessen). Ein einfach ergänztes
   `_LEGACY_COMPARE_RADAR_FILE` würde also **nie** greifen und die Sperrzeit stillschweigend
   verlieren. Bestandsdaten sind real: `henning` trägt `{"cp-eb6ba0b239d90e37":
   "2026-07-25T19:45:03…"}`. Der Verlust wäre hier folgenlos (Eintrag ist Wochen alt), das
   Muster aber falsch — die Übernahme braucht einen eigenen, idempotenten Weg.
2. **🔴 R2 — Die Tages-Obergrenze kann NowCast-Meldungen unterdrücken.** Genau das war #1555:
   ein einziger geteilter Tageszähler über alle Trips und alle Alarm-Gründe, `free`-Stufe = 2/Tag,
   Abweichungs-Alarme haben ihn regelmäßig aufgebraucht → system-weit **null** zugestellte
   NowCast-Alarme. Behoben durch die Reserve `_FORECAST_CHANGE_RESERVE` `:58`. S3 hängt einen
   **weiteren** Verbraucher an denselben Zähler. **Ausbleibende Alarme sind der gefährlichste
   Fehler** — das gehört als ausdrückliche Entscheidung in die Spec, nicht als Nebeneffekt.
3. **R3 — Ruhezeit vor die Erkennung ziehen ändert eine zugesicherte Zusage.** Der Kommentar
   `:116` („Onset ist bereits erkannt — Ruhezeit unterdrückt erst hier den Versand") stammt aus
   #1041b. Das Meldeverhalten bleibt gleich (in beiden Fällen geht nichts raus), Abrufe sinken.
   Zu prüfen ist der Seiteneffekt auf den Dedup-Zustand `_finalize_triggered_state()` `:175`.
4. **R4 — Schlüsselraum der Sperrzeit.** Scope `"radar"` ist heute mit `trip.id` belegt.
   Preset-IDs (`cp-…`) kollidieren praktisch nicht, aber „praktisch nicht" ist keine Zusicherung.
   Entweder eigener Scope oder Kennung nach S1-Muster (`compare:<preset_id>`) — Entscheidung
   gehört in die Spec.
5. **R5 — Alle fünf realen Ortsvergleiche des PO sind stillgelegt** (`schedule="manual"`, AG6).
   Der Compare-Nowcast feuert in Produktion derzeit ohnehin nicht. Für die Staging-Verifikation
   heißt das: ein Prüf-Preset braucht einen echten Zeitplan, sonst misst man den AG6-Riegel.
6. **R6 — Nowcast ist live schwer provozierbar** (echter Regen-/Gewitter-Onset ≤ 20 Min). Der
   Nachweis muss über den ausgelieferten Staging-Code + Zustandsdateien geführt werden
   (Rezept aus AG5/AG6), nicht über „wir warten auf Regen".
7. **R7 — #1594 hängt hinter dieser Umbaukette.** Die zusammengelegte Steuerung soll den
   **nächsten geplanten Versandzeitpunkt** kennen. Gemessen: eine solche Funktion existiert
   nirgends. Es gibt nur Ad-hoc-Stundenabgleiche (`trip_report_scheduler.py:464-474`,
   `compare_slot_scheduler.py:109-111`) — beide werfen die **Minuten weg** und rechnen in
   Wien-Zeit, nicht in Ortszeit. #1594 ist **nicht** Teil von S3; S3 darf sich den Weg dorthin
   aber nicht verbauen.
8. **R8 — Struktur-Wächter.** `tests/test_success_status_guard.py` und
   `tests/test_resolution_loss_guard.py` verankern `compare_radar_alert.py` per
   `datei::funktion::ordinal` samt `try/except`-Zahl. Ein zusätzlicher Riegel verschiebt die
   Zählung ⇒ Schlüssel nachziehen, **Wächter nicht aufweichen**.
9. **R9 — Mandantentrennung.** Zähler und Sperrzeit liegen unter `data/users/<user_id>/`.
   Pflichttest mit **zwei** verschiedenen Nutzern.

---

# Analysis (Phase 2, 2026-08-08)

## Type

**Feature/Rework** — Umbau mit Zielmarke „Verhalten unverändert" plus drei ausdrücklich
gewollten Verhaltensänderungen (Tages-Obergrenze, gemeinsame Sperrzeit, Reihenfolge).

## Was die Analyse gegenüber der Issue-Beschreibung korrigiert

| Behauptung im Issue (Stand 2026-08-02) | Gemessener Stand 2026-08-08 |
|---|---|
| Compare-Nowcast hat feste Kanäle / keine Stilllegung | **überholt** — `effective_compare_channels` `:133` und `is_silenced` `:95` sitzen bereits drin (AG1/AG4/AG6) |
| „Bremse gegen Meldungsfluten fehlt" | **stimmt, wirkt aber nur bei getakteten Konten.** `daily_alert_limit()` liefert für `tier: premium` `None`. Von drei realen Konten ist eines premium (`henning`), zwei ohne `tier`-Feld (= `free`, 2/Tag) |
| „spart Abruf-Kontingent" | **nur bedingt.** `get_nowcast` trifft oft den geteilten Cache (TTL 300 s) — ein Treffer kostet nichts. Nur ein echter Fehltreffer im open-meteo-Zweig verbraucht Kontingent; RADOLAN/INCA/DPC sind ungegatet |

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/alert_gate.py` | **CREATE** | Geteilter Freigabe-Baustein: Ruhezeit → Sperrzeit → Tages-Obergrenze in fester Reihenfolge |
| `src/services/compare_radar_alert.py` | MODIFY | Ruft den Baustein; eigene Sperrzeit-Datei + `_load/_save_throttle_times` entfallen |
| `src/services/trip_alert.py` | MODIFY | Radar-Zweig `:748-765` ruft denselben Baustein (Ersetzung, keine Verhaltensänderung) |
| `src/services/throttle_store.py` | MODIFY | Scope-Liste im Docstring um `compare_radar` ergänzen |
| `tests/tdd/test_compare_radar_alert.py` | MODIFY | AC-7 misst die Mandantentrennung an der alten Datei → Messpunkt wandert auf `throttle_state.json` |
| `tests/tdd/test_data_root_migration_services.py` | MODIFY | `:74-82` prüft `_throttle_file` namentlich → wird ohne Anpassung rot |
| `tests/tdd/test_throttle_store.py` | MODIFY | neuer Scope braucht Abdeckung |
| `tests/test_success_status_guard.py` | MODIFY (nur falls Zählung kippt) | Anker `compare_radar_alert.py::check_all_compare_presets::0` und `…: 1` |
| `docs/adr/0021-shared-deviation-alert-engine.md` | MODIFY | Nachtrag: „Tageslimit bleibt Trip-spezifisch, kein Compare-Bedarf bekannt" wird durch S3 sachlich falsch |
| Go-Seite, Frontend | **keine** | belegt: kein Treffer für `compare_radar_alert`/`radar_alert_throttle` |

## Scope Assessment

- Dateien: 4 Produktiv (1 neu), ~5 Test, 1 ADR-Nachtrag
- Produktiv-LoC: **~150–190** (Baustein ~70–90, Compare netto ~+20–40, Trip netto ~−10, Docstring ~2)
- Test-LoC: ~300–400
- **Passt in EINEN Arbeitsgang** unter dem 250-Zeilen-Budget. Keine Unterteilung nötig
- Risiko: **HOCH** — jeder Fehler im Baustein unterdrückt *alle* Nowcast-Alarme beider Pfade

## Technical Approach

**Ein geteilter Freigabe-Baustein, von Anfang an mit BEIDEN Verbrauchern verdrahtet.**

```python
# src/services/alert_gate.py
class GateResult(NamedTuple):
    allowed: bool
    reason: Optional[str]   # REASON_QUIET_HOURS | REASON_COOLDOWN | REASON_DAILY_LIMIT

def check_nowcast_gate(*, user_id, throttle_scope, throttle_key, cooldown_minutes,
                       quiet_from, quiet_to, context_label, now,
                       daily_limit_reason="nowcast", throttle_store=None) -> GateResult
def record_nowcast_sent(*, user_id, throttle_scope, throttle_key, now,
                        throttle_store=None) -> None
```

Der Baustein reicht `is_quiet_hours` **unverändert** durch (kein eigenes `try/except` —
`fix_1479` AC-11 wird von einem AST-Wächter geprüft). `record_nowcast_sent` bündelt
`increment()` + `record()` und wird **ausschließlich nach erfolgreicher Zustellung** gerufen,
genau wie heute an beiden Stellen.

**Abweichung von der Empfehlung des Strategie-Agenten:** Er wollte den Baustein zunächst nur
vom Ortsvergleich rufen lassen und den Trip-Pfad später nachziehen. Dagegen spricht das
Hausmuster aus S2 AG1: dort wurde der Kanal-Resolver extrahiert und **beide** Bestandsstellen
wurden sofort zu dünnen Wrappern — Produktivcode schrumpfte netto. Ein „geteilter" Baustein
mit genau einem Verbraucher ist keine Entdopplung, sondern eine **dritte** Fassung derselben
Reihenfolge; und das Issue-Ziel lautet ausdrücklich Zusammenlegen, nicht Danebenlegen. Der
Mehraufwand ist gering (der Trip-Zweig verliert ~18 Zeilen), das Risiko liegt allein bei den
Struktur-Wächtern und ist messbar.

**Sperrzeit:** neuer Scope `"compare_radar"`, Schlüssel = `preset_id`.
- `"radar"` ist ausschließlich mit **Trip**-IDs belegt. Seit dem #1250-Cutover liegen Trips und
  Ortsvergleiche im selben Verzeichnis `briefings/<id>.json`, unterschieden nur durch `kind`;
  IDs sind frei gewählte Slugs, keine UUIDs ⇒ Kollision ist real möglich.
- `"compare_preset"` ist durch den Änderungsalarm auf **demselben** `preset_id`-Schlüssel
  belegt. Wiederverwendung würde `test_alert_log_compare_and_tenancy.py::test_ac12…` rot
  machen — dort löst ein Preset im selben Lauf Δ-, Nowcast- und amtlichen Alarm aus und
  erwartet `(1,1,1)`.

**Altdaten:** bewusster Verzicht auf Migration, mit Begründung in der Spec.
`_migrate_if_needed()` `:162-164` bricht ab, sobald `throttle_state.json` existiert — bei allen
realen Nutzern der Fall. Eine vierte Legacy-Konstante wäre totes Gerüst; der wirksame Weg wäre
ein ungegateter `_update()`-Aufruf mit `setdefault`-Semantik. Real existiert **ein** Alteintrag
(`henning`, `cp-eb6ba0b239d90e37`, 25.07.), längst außerhalb jedes Cooldowns. Die Altdatei wird
nicht mehr geschrieben und bleibt unangetastet liegen (kein Löschen).

## Risiken, geordnet nach Schwere

1. **Fehler im Baustein unterdrückt alle Nowcast-Alarme beider Pfade.** Genau die Bugklasse,
   gegen die der `ThrottleStore` einst gebaut wurde („stiller Totalausfall"). Gegenmittel: jede
   Gate-Stufe einzeln bewachen, Reihenfolge 1:1 gegen die Trip-Vorlage messen.
2. **Geteilter Tageszähler** (#1555): ein weiterer Verbraucher am selben Topf. Entschärft durch
   `reason="nowcast"` — die Reserve kappt nur `forecast_change`. Ein eigener Compare-Reason
   würde diesen Schutz **verlieren**; das ist der Fehler, der hier lauert.
3. **Zähler-Reihenfolge:** `increment`/`record` vor statt nach der Zustellung würde
   fehlgeschlagene Versuche als verbraucht buchen.
4. **Scope-Kollision** bei falscher Schlüsselwahl (s. o.).
5. **Ruhezeit vor Erkennung** kippt zwei archivierte ACs (#1041/#1041b) — Meldeverhalten
   bleibt gleich, die Ablösung gehört ausdrücklich in die Spec.
6. **Struktur-Wächter** (`test_success_status_guard.py`) — Deploy-Blocker, kein Nutzerrisiko.

## Nebenbefund (nicht in dieser Scheibe)

`trip_report_scheduler.py:1159` prüft `is_allowed(reason="nowcast")` für den
Starkregen-Kurzhinweis, ruft aber nirgends `increment()` — geprüft, aber nie verbucht.
Einzige asymmetrische Stelle im Repo. → Sammel-Issue #1199.

## Entscheidungen (getroffen 2026-08-08)

- **E1 — geteilter Freigabe-Baustein, beide Nowcast-Pfade sofort verdrahtet.** Entschieden vom
  Tech-Lead gegen die Empfehlung des Strategie-Agenten (der wollte zunächst nur den
  Compare-Verbraucher). Begründung: ein Baustein mit genau einem Verbraucher ist keine
  Entdopplung, sondern eine dritte Fassung derselben Reihenfolge. Hausmuster ist S2 AG1 —
  dort wurden beide Bestandsstellen sofort zu dünnen Wrappern und der Produktivcode schrumpfte.
- **E2 — Tages-Obergrenze exakt wie beim Trip-Nowcast, `reason="nowcast"`.** Damit erbt der
  Ortsvergleich den Vorrang-Schutz aus #1555 (die Reserve kappt nur `forecast_change`). Ein
  Compare-eigener Grund würde diesen Schutz still verlieren — das ist die Falle an dieser Stelle.
- **E3 — neuer Scope `"compare_radar"`, Schlüssel `preset_id`; keine Migration der Altdaten,**
  mit Begründung in der Spec (ein realer Alteintrag vom 25.07., längst außerhalb jedes
  Cooldowns; der vorhandene Migrationsmechanismus greift bei Bestandsnutzern ohnehin nicht).
- **E4 — JA, Unterdrückungen werden protokolliert (PO-Entscheidung 2026-08-08).**
  `REASON_QUIET_HOURS`, `REASON_COOLDOWN`, `REASON_DAILY_LIMIT` (`alert_log.py:47-49`) werden
  erstmals scharf geschaltet. Der Freigabe-Baustein kennt die sperrende Stufe ohnehin und gibt
  sie über `GateResult.reason` zurück. **Geltungsbereich: die beiden Nowcast-Pfade** — Änderungs-
  und amtliche Alarme bleiben unberührt (eigene Scheiben S4 bzw. Folgearbeit).
  ⚠️ **LoC-Wirkung:** schätzungsweise +30–50 Zeilen ⇒ Gesamtschätzung rückt auf **~180–240**
  Produktiv-Zeilen und damit nah an die 250er-Grenze. Wird es eng, ist die
  Unterdrückungs-Protokollierung der Teil, der als eigener Arbeitsgang nachgezogen wird —
  nicht der Kern (a)/(b)/(c).
