---
entity_id: feat_2050_sz12_fehlende_vergleichsbasis
type: feature
created: 2026-10-01
updated: 2026-10-01
status: draft
workflow: feat-2050-sz12-fehlende-vergleichsbasis
version: "1.0"
tags: [alarm, anker, vergleichsbasis, protokoll, ortsvergleich]
---

# Fehlende Vergleichsbasis wird protokolliert statt lautlos zu verschwinden (Issue #2050, Szenario 12)

## Approval

- [ ] Approved

## Purpose

Der Abweichungs-Alarm ist ein Wächter, der eine Änderung gegen einen Anker (die Vergleichsbasis
aus dem letzten Briefing) misst (ADR-0009, ADR-0056). Fehlt dieser Anker oder wird er verworfen,
endet der Lauf heute ohne jede Spur im Alarmprotokoll des Nutzers: Der Grund steht nur in der
Diagnosedatei `alert_anchor_rejected.jsonl`, die allein der Go-Health-Endpoint als Streak liest.
Diese Scheibe erfüllt **Szenario 12** (Anforderungen **D-2**: jede Unterdrückung hat einen
benannten Grund samt der Werte, die zur Entscheidung führten, und **E-1**: die Vergleichsbasis
gehört ins Protokoll): Ein laufender Trip bzw. ein aktiver Ortsvergleich ohne gültige
Vergleichsbasis erzeugt nie „stilles Nichts", sondern genau einen benannten Eintrag
`no_reference_basis` im Alarmprotokoll des betroffenen Nutzers, der im nächsten zugestellten
Briefing als „nicht zugestellt" sichtbar wird. Das Auslöseverhalten bleibt unverändert; es wird
nichts frisch gegen absolute Schwellen geprüft (ADR-0009/0056 bleiben gewahrt).

## Source

- **File:** `src/services/trip_alert.py` — `_get_cached_weather` (Ablehnungsstellen `missing`,
  `not_briefing_backed`, `too_old`, `wrong_day`), `_report_missing_anchor`, `check_all_trips`
  (leeres `cached` ⇒ nur amtlich, dann `continue`), Trip-Wrapper `_protokolliere_unterdrueckung`
- **File:** `src/services/compare_alert.py` — `_evaluate_one_location` (leerer Anker
  „Bootstrap", `_anchor_too_old`), Wrapper `_protokolliere_unterdrueckung` (`entity_type="compare"`)
- **File:** `src/services/alert_log.py` — neue Konstante, additive E-1-Felder
  (`_E1_FIELD_TYPES`/`_apply_e1_fields`), Lese-Helfer für die Entdopplung
- **File:** `src/services/alert_briefing_anchor.py` — `undelivered_since_last_briefing`
- **File:** `src/output/renderers/email/undelivered_hint.py` — `_REASON_LABELS`/`_REASON_BLOCK`
- **Identifier:** `no_reference_basis`, `append_suppressed_entry`

Schicht: ausschließlich Python-Core (`src/services/`, `src/output/renderers/`). Kein Go-, kein
Frontend-Anteil: `internal/store/log.go` und `internal/handler/cockpit.go` lesen nur `entries`,
nie `not_delivered[].reason`; `internal/scheduler/briefing_health.go` liest allein das Feld `ts`
der Diagnosedatei. Beides bleibt unberührt.

## Estimated Scope

- **LoC:** ~120–160 Produktivcode (ohne Tests/Doku), unter dem 250-LoC-Limit
- **Files:** 5 produktiv + 2 Tests + Spec
- **Effort:** medium
- **Risiko:** MEDIUM — zentraler Alarmlauf, aber rein additiv (Protokoll + Hinweis); kein
  Auslöseverhalten ändert sich

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alert_log.append_suppressed_entry` | function | Schreibweg nach `not_delivered`; `gate_reason` Pflicht; Signatur bekommt zwei additive optionale Felder |
| `alert_log._E1_FIELD_TYPES` / `_apply_e1_fields` | module data / function | Typgeprüfte, additiv-defensive Zusatzfelder (None ⇒ Absenz, falscher Typ ⇒ verworfen, nie Exception) |
| `trip_alert._get_cached_weather(..., tagesgleicher_anker_noetig)` | method | Entstehungsort des Grundes; nur der Abweichungs-Aufruf (`True`) schreibt |
| `trip_alert._report_missing_anchor` | method | Laufender-Trip-Prüfung (#1661 C2) für `missing` |
| `compare_alert._protokolliere_unterdrueckung` | method | Vorhandener fail-soft Wrapper des Ortsvergleichs |
| `alert_briefing_anchor.undelivered_since_last_briefing` | function | Gemeinsame Naht beider Briefing-Pfade (`notification_service.py`, `scheduler_dispatch_service.py`) |
| `tests/helpers/alarm_pruefstrecke.py` | test helper | Harness; `zweig="deviation"` ruft `check_and_send_alerts` direkt und erreicht den Fehl-Anker-Pfad NICHT — der Szenario-Test fährt deshalb `check_all_trips` / `check_all_compare_presets` |

## Implementation Details

**1. Ein Grund, typgeprüfter Untergrund (D-2/E-1).** `alert_log.REASON_NO_REFERENCE_BASIS =
"no_reference_basis"`. `gate_reason` ist genau dieser Code (kein zusammengesetzter String). Der
Untergrund steht in einem eigenen additiven Feld `reference_gap` (str): Trip `missing` /
`not_briefing_backed` / `too_old` / `wrong_day`, Ortsvergleich `missing` / `too_old`. Dazu der
Bezugstag `reference_day` (str, ISO-Datum, das `today` des Laufs) und — sofern ein Anker
existiert — das vorhandene Feld `reference_at` (Ankerdatum bzw. Schreibzeitpunkt des
verworfenen Ankers). Beide neuen Schlüssel kommen in `_E1_FIELD_TYPES` (Typ `str`) und in die
Schleife von `_apply_e1_fields` sowie als optionale Parameter in `append_suppressed_entry`.

**2. Schreibort und -bedingung (Trip).** An den Ablehnungsstellen in `_get_cached_weather`
(und im `missing`-Zweig über `_report_missing_anchor`) wird zusätzlich zum unveränderten
`record_alert_anchor_rejected` ein Protokolleintrag geschrieben — **nur** wenn
`tagesgleicher_anker_noetig=True` (Abweichungs-Aufruf). Der amtliche Zweitaufruf
(`check_official_alert_triggers`, `tagesgleicher_anker_noetig=False`) schreibt nie; die
bisherige Doppel-Diagnose pro Lauf erzeugt so keinen Doppel-Eintrag, ohne Zusatzlogik.
**Nur laufender Trip** (`start_date <= today <= end_date`, Muster #1661 C2): ein noch nicht
gestarteter Trip bleibt wie bisher still (DEBUG).

**3. Entdopplung.** Höchstens **ein** Eintrag je Nutzer + Entity + Tag + Untergrund. Vor dem
Schreiben fragt ein neuer Lese-Helfer in `alert_log.py` das `not_delivered` des
`alert_log.json` **desselben Nutzers** ab, ob für `(entity_id, entity_type,
gate_reason=no_reference_basis, reference_gap, reference_day)` bereits ein Eintrag existiert.
Der Tag ist dasselbe `today`, das der Lauf bereits verwendet. Wechselt der Untergrund am selben
Tag (z. B. `missing` → `wrong_day`), entsteht ein zweiter Eintrag — ein neuer Befund. Ohne diese
Regel erzeugte der 15-Min-Lauf (`internal/scheduler/scheduler.go`, Docstring in
`check_all_trips` nennt veraltet 30 Min) bis zu 96 Einträge je Trip und Tag; `DEDUP_WINDOW`
(2 Min) wirkt nur beim Lesen und fasst das nicht zusammen.

**4. Fail-soft.** Ein scheiternder Protokoll-Eintrag oder Entdopplungs-Lesefehler darf nie
den Lauf der übrigen Trips/Ortsvergleiche des Nutzers mitreißen (Muster `fix_1479`): Aufruf
über die bestehenden Wrapper `_protokolliere_unterdrueckung` (Trip und Compare), die
`append_suppressed_entry` in `try/except` mit `logger.error` fassen. Das Leer-`cached`-Ergebnis
und der Rückgabewert `None` von `_get_cached_weather` bleiben bitgleich.

**5. Ortsvergleich (Parität, selbes Ticket).** In `compare_alert._evaluate_one_location`:
(a) leerer Anker (`cached == []`, bisher „Bootstrap") ⇒ `reference_gap="missing"`;
(b) `_anchor_too_old(...)` ⇒ `reference_gap="too_old"`, `reference_at` = `fetched_at` des
Ankers. Beides über den vorhandenen Wrapper (`entity_type="compare"`, `entity_id=preset_id`),
je **Preset** + Tag + Untergrund entdoppelt (nicht je Ort — ein Preset mit sechs Orten schreibt
einmal). Der Wrapper bekommt dafür die neuen Parameter durchgereicht; sein bisheriger
`reason=REASON_FORECAST_CHANGE` bleibt. Der Cooldown und der `alert_state` werden weiterhin
nicht angefasst (Spec AC-7 aus #1584 C).

**6. Sichtbarkeit.** `undelivered_hint.py`: `_REASON_LABELS["no_reference_basis"] = "Kein Alarm
möglich: keine gültige Vergleichsbasis"`, `_REASON_BLOCK["no_reference_basis"] = "failed"`
(es ist kein vom Nutzer eingestellter Rückhalt; der Wächter war blind). Das Label ist
bewusst statisch (das Register `_REASON_LABELS` kennt keine Vorfalls-Werte); Untergrund,
Ankerdatum und Bezugstag stehen im Protokolleintrag selbst. Zusätzlich
`undelivered_since_last_briefing`: Ohne gespeicherten Briefing-Zeitstempel (`since is None`)
liefert die Funktion künftig **ausschließlich** die `no_reference_basis`-Einträge der Entity
(Ersatz-Fenster), nicht mehr `[]`. Die Gesamthistorie kippt weiterhin nicht in die erste Mail
(AC-7 aus #1461 bleibt gewahrt) — nötig, weil der Untergrund `missing` per Definition ohne
Briefing auftritt und sonst nirgends sichtbar wäre. Mit Briefing-Zeitstempel bleibt das
Verhalten unverändert (Fenster `since=last_briefing_at`).

**7. Unverändert (Regressionswächter).** `record_alert_anchor_rejected` und
`alert_anchor_rejected.jsonl` (Format, Schreibfrequenz) sowie der Go-Health-Streak
(`briefing_health.go`, `alert_anchor_health_test.go`) bleiben wie sie sind; die
Diagnosedatei schreibt weiterhin bei jedem Lauf.

## Expected Behavior

- **Input:** Ein Lauf von `check_all_trips` bzw. `check_all_compare_presets`, in dem der
  Abweichungs-Zweig keine gültige Vergleichsbasis findet (Trip: `missing`,
  `not_briefing_backed`, `too_old`, `wrong_day`; Ortsvergleich: `missing`, `too_old`).
- **Output:** Genau ein `not_delivered`-Eintrag im `alert_log` des betroffenen Nutzers mit
  `gate_reason == "no_reference_basis"`, `reference_gap`, `reference_day` (und `reference_at`,
  sofern ein Anker existiert); kein Alarm, kein Versand, keine Änderung am Auslöseverhalten.
- **Side effects:** Der Grund erscheint im „nicht zugestellt"-Block der nächsten
  E-Mail-Briefing des Nutzers unter „FEHLGESCHLAGEN" mit deutschem Label; die
  Diagnosedatei wird wie bisher geschrieben.

## Acceptance Criteria

- **AC-1:** Given ein laufender Trip, dessen Abweichungs-Zweig keinen Anker findet (es gab nie
  ein Briefing), When `check_all_trips` läuft, Then steht im Alarmprotokoll des Nutzers genau
  ein `not_delivered`-Eintrag mit `gate_reason == "no_reference_basis"` und
  `reference_gap == "missing"` samt `reference_day` (heute) — statt wie bisher ohne jede Spur
  im Alarmprotokoll zu enden — und es geht kein Abweichungs-Alarm raus.

- **AC-2:** Given ein laufender Trip, dessen vorhandener Anker abgelehnt wird (nicht aus einem
  Briefing stammend, zu alt, oder vom falschen Tag), When `check_all_trips` läuft, Then
  entsteht je Fall genau ein Eintrag `no_reference_basis` mit dem passenden `reference_gap`
  (`not_briefing_backed` / `too_old` / `wrong_day`) und dem Ankerdatum in `reference_at`, sodass
  nachträglich belegbar ist, welche Vergleichsbasis verworfen wurde (D-2/E-1). Der Fehl-Anker
  entsteht dabei vom Produkt selbst (Briefing-Schreibweg bzw. Abfrage-Snapshot), nicht durch
  einen hand eingelegten Datensatz.

- **AC-3:** Given ein Trip ohne Anker, When `check_all_trips` an einem Tag mehrfach läuft
  (15-Minuten-Takt, mindestens drei Läufe), Then steht je Nutzer + Trip + Tag + Untergrund
  genau **ein** Eintrag im Alarmprotokoll, nicht einer je Lauf; wechselt der Untergrund am
  selben Tag (z. B. `missing` zu `wrong_day`), kommt für den neuen Untergrund ein weiterer
  Eintrag hinzu, und am Folgetag entsteht wieder ein neuer Eintrag.

- **AC-4:** Given ein laufender Trip ohne Anker und eine amtliche Warnung im selben Lauf, When
  `check_all_trips` den amtlichen Zweig (zweiter Aufruf mit `tagesgleicher_anker_noetig=False`)
  und den Abweichungs-Zweig durchläuft, Then entsteht genau ein Eintrag `no_reference_basis`
  (nur der Abweichungs-Aufruf schreibt), die amtliche Warnung wird unverändert versendet, und
  die Diagnosedatei erhält weiterhin ihre bisherigen Zeilen.

- **AC-5:** Given ein Trip, dessen Laufzeitraum noch nicht begonnen hat und der keinen Anker
  hat, When `check_all_trips` läuft, Then entsteht **kein** Eintrag im Alarmprotokoll (Normalfall
  vor dem ersten Briefing, Muster #1661 C2) — Abgrenzung, muss rot werden, wenn man sie
  verletzt.

- **AC-6:** Given ein laufender Trip mit gültigem, tagesgleichem, briefing-gestütztem Anker,
  When `check_all_trips` läuft, Then entsteht **kein** `no_reference_basis`-Eintrag und der
  Abweichungs-Zweig löst bei einer Wetteränderung über der Schwelle weiterhin aus und versendet
  tatsächlich (Positivkontrolle: ohne sie bewiese kein anderer Test dieser Scheibe, dass die
  Prüfung etwas misst).

- **AC-7:** Given ein aktiver Ortsvergleich (Preset) ohne Anker (leerer Snapshot, bisher
  „Bootstrap"), When `check_all_compare_presets` läuft, Then steht im Alarmprotokoll des
  Nutzers genau ein Eintrag mit `entity_type == "compare"`, `entity_id == <preset_id>`,
  `gate_reason == "no_reference_basis"` und `reference_gap == "missing"` — auch bei mehreren
  Orten im Preset und mehreren Läufen am selben Tag nur einer.

- **AC-8:** Given ein aktiver Ortsvergleich, dessen Anker älter als die 26-Stunden-Grenze ist
  (`_anchor_too_old`), When `check_all_compare_presets` läuft, Then entsteht genau ein Eintrag
  `no_reference_basis` mit `reference_gap == "too_old"` und dem Ankerzeitpunkt in
  `reference_at`; der `alert_state` und der Cooldown bleiben unberührt (kein Alarm gilt als
  gemeldet, Dauerstille entsteht nicht).

- **AC-9:** Given zwei verschiedene Nutzer mit je einem laufenden Trip bzw. aktiven
  Ortsvergleich ohne Anker im selben Prüfzyklus, When beide Läufe stattfinden, Then liegt der
  Eintrag jedes Nutzers ausschließlich in dessen eigenem `alert_log` (`data/users/<user_id>/`);
  die Entdopplung des einen Nutzers unterdrückt den Eintrag des anderen nicht, und keine
  Entity-ID des einen erscheint im Protokoll des anderen (Mandantentrennung).

- **AC-10:** Given ein Eintrag `no_reference_basis` liegt im Alarmprotokoll eines Nutzers, der
  bereits ein Briefing erhalten hat (Reihenfolge: Briefing senden, Eintrag schreiben, zweites
  Briefing senden), When das nächste E-Mail-Briefing gerendert wird, Then erscheint der Grund
  im Block „FEHLGESCHLAGEN" mit dem deutschen Label „Kein Alarm möglich: keine gültige
  Vergleichsbasis" und nicht als roher Code und nicht im Block „ZURÜCKGEHALTEN".

- **AC-11:** Given ein Nutzer ohne gespeicherten Briefing-Zeitstempel, für dessen Trip sowohl
  ein `no_reference_basis`-Eintrag als auch ältere Einträge anderer Gründe (z. B. `cooldown`,
  `delivery_failed`) im Protokoll stehen, When `undelivered_since_last_briefing` aufgerufen
  wird, Then liefert sie ausschließlich die `no_reference_basis`-Einträge dieser Entity; die
  älteren Einträge anderer Gründe erscheinen weiterhin **nicht** (AC-7 aus #1461 bleibt
  gewahrt). Hat der Nutzer dagegen einen Briefing-Zeitstempel, bleibt das Fenster
  `since=last_briefing_at` bitgleich zum bisherigen Verhalten.

- **AC-12:** Given der handgepflegte Katalog-Wächter `_REASON_EXPECTATION` (AC-18 in
  `test_alert_undelivered_hint.py`), When er über alle SSoT-Gründe parametrisiert läuft, Then
  enthält er `REASON_NO_REFERENCE_BASIS` mit Label und Block `failed` und wird rot, sobald
  Label oder Block-Zuordnung des neuen Grundes fehlen oder abweichen.

- **AC-13:** Given ein `append_suppressed_entry`-Aufruf mit einem falsch typisierten
  `reference_gap` oder `reference_day` (z. B. `int`), When der Eintrag geschrieben wird, Then
  entsteht der Eintrag ohne dieses Feld, ohne Exception, mit `logger.warning` (additiv-defensiv
  wie die übrigen E-1-Felder); ein Aufruf ohne die Felder (alle anderen Gründe) erzeugt
  unverändert Einträge ohne diese Schlüssel.

- **AC-14:** Given der Protokoll-Schreibweg selbst schlägt fehl (z. B. nicht beschreibbares
  `alert_log.json` des einen Trips), When `check_all_trips` läuft, Then laufen die übrigen
  Trips desselben Nutzers weiter durch und versenden ihre Alarme (fail-soft, `fix_1479`); der
  Fehler steht als `logger.error` im Log.

- **AC-15:** Given die Diagnosedatei `alert_anchor_rejected.jsonl` und der Go-Health-Streak,
  When ein Lauf ohne Anker stattfindet, Then wird die Diagnosezeile weiterhin bei jedem Lauf
  mit unverändertem Format geschrieben und die bestehenden Anker-Wächter
  (`tests/tdd/test_alert_anchor_day_guard.py`, `internal/scheduler/alert_anchor_health_test.go`)
  bleiben grün (Regressions-AC: Streak darf durch die Entdopplung des Protokolls nicht
  verschwinden).

- **AC-16:** Given ein laufender Trip ohne Anker, dessen aktuelle Wetterlage über den
  Alarmschwellen läge, When `check_all_trips` läuft, Then wird dafür **kein** frischer
  Wetterabruf gegen absolute Schwellen gestartet und kein Alarm ausgelöst — das Auslöseverhalten
  bleibt bitgleich (ADR-0009/0056); die Zusicherung wird an den ausbleibenden Abruf des
  Wetter-Providers und den fehlenden Versand gemessen, nicht am Code.

## Geplante Tests

Szenario-Test `tests/tdd/test_alarm_szenario_fehlende_vergleichsbasis.py` (neu) fährt über die
echten Einstiege `check_all_trips` / `check_all_compare_presets`; der Fehl-Anker entsteht vom
Produkt (Briefing-Schreibweg, Abfrage-Snapshot über `glance`-Pfad, Zeitsprung des Laufs), nie
durch einen Fixture-Datensatz. Vorbild: `test_alert_suppression_reason.py` (S3b),
`tests/helpers/alarm_pruefstrecke.py` für Zeit-/Kanal-Aufbau.

| AC | Test | Beweis |
|----|------|--------|
| AC-1 | `test_trip_ohne_anker_schreibt_no_reference_basis_missing` | `read_undelivered(user)` hat einen Eintrag, `gate_reason`, `reference_gap`, `reference_day`; Versandzähler 0 |
| AC-2 | `test_trip_abgelehnter_anker_je_untergrund` (parametrisiert: 3 Fälle) | Eintrag + `reference_at` je Untergrund |
| AC-3 | `test_trip_entdoppelt_je_tag_und_untergrund` | drei Läufe ⇒ 1 Eintrag; Untergrundwechsel ⇒ 2; Folgetag ⇒ neuer |
| AC-4 | `test_amtlicher_zweitaufruf_schreibt_nie` | genau 1 Eintrag; amtliche Mail versendet; Diagnosezeilen unverändert |
| AC-5 | `test_nicht_gestarteter_trip_bleibt_still` | Protokoll leer |
| AC-6 | `test_gueltiger_anker_loest_weiter_aus_positivkontrolle` | echter Versand, kein `no_reference_basis` |
| AC-7 | `test_compare_ohne_anker_schreibt_grund_je_preset` | `entity_type="compare"`, ein Eintrag bei mehreren Orten/Läufen |
| AC-8 | `test_compare_anker_zu_alt` | Eintrag `too_old` + `reference_at`; `alert_state`/Cooldown unverändert |
| AC-9 | `test_zwei_nutzer_eintrag_nur_im_eigenen_protokoll` | Trip und Compare, `read_undelivered` je Nutzer |
| AC-10 | `test_briefing_hinweis_zeigt_deutsches_label_im_failed_block` (Briefing → Eintrag → zweites Briefing, echter Renderer) | Label im Block „FEHLGESCHLAGEN"; Nachweis zusätzlich über `briefing_mail_validator.py` gegen die zugestellte Staging-Mail |
| AC-11 | `test_ersatzfenster_ohne_zeitstempel_nur_no_reference_basis` + `test_fenster_mit_zeitstempel_unveraendert` | gemischte Historie ⇒ nur der neue Grund; AC-7 aus #1461 (`test_alert_undelivered_hint.py`) bleibt grün |
| AC-12 | Ergänzung `_REASON_EXPECTATION` in `test_alert_undelivered_hint.py` | Katalog-Wächter AC-18 |
| AC-13 | `test_reference_felder_typpruefung_und_absenz` | Feld fehlt bei falschem Typ, keine Exception; Altgründe ohne Schlüssel |
| AC-14 | `test_protokollfehler_reisst_lauf_nicht_mit` | zweiter Trip versendet |
| AC-15 | bestehende Wächter `test_alert_anchor_day_guard.py`, `alert_anchor_health_test.go` + eine neue Zeile im Szenario-Test, die die Diagnosedatei pro Lauf zählt | Streak/Format unverändert |
| AC-16 | `test_ohne_anker_kein_frischer_abruf_kein_alarm` | Provider-Zähler 0, kein Versand |

**Mutations-Gegenproben (Pflicht für den Adversary, Wirkstelle statt Codestelle):**
(a) Schreibbedingung `tagesgleicher_anker_noetig` entfernen ⇒ AC-4 muss rot werden;
(b) „laufender Trip"-Prüfung entfernen ⇒ AC-5 rot; (c) Entdopplung entfernen ⇒ AC-3 rot;
(d) `user_id` im Entdopplungs-Lesehelfer auf Standard ändern ⇒ AC-9 rot;
(e) Ersatz-Fenster auf „alles" erweitern ⇒ AC-11 rot; (f) Label aus `_REASON_LABELS` entfernen ⇒
AC-10 und AC-12 rot; (g) Compare-Wrapper-Aufruf in `_anchor_too_old`-Zweig entfernen ⇒ AC-8 rot.

## Bewusst nicht im Scope

- **Kanalparität des Nicht-zugestellt-Hinweises.** Der Hinweis existiert für **keinen**
  bestehenden Grund in Telegram, SMS oder Premium-SMS, sondern nur im E-Mail-Briefing. Das
  betrifft alle Gründe gleich und ist ein eigenes Thema (Epic #2133, jeder Kanal beantwortet
  jede Frage); es gehört nicht in eine Scheibe, die einen einzelnen Grund ergänzt. Die
  Protokolleinträge selbst sind kanalunabhängig und bleiben vollständig.
- **Stille Kanal-Marker-Verwerfungen auf DEBUG** (`trip_alert.py` rollierende Kanal-Marker):
  Sie können `missing` melden, obwohl Marker existieren. Das ist Bestand der
  Anker-Suche (#1987) und kein neuer Befund; diese Scheibe protokolliert, was die Suche
  ergibt, und ändert die Suche nicht. Die Wahrheit der Suche wäre eine eigene Messung.
- **Frisch holen und gegen absolute Schwellen prüfen**, wenn kein Anker existiert: eine
  Verhaltensänderung und damit Entscheidungsfläche (ADR-0009: Alarme sind Abweichungs-Wächter,
  ohne Briefing keine Vergleichsbasis; ADR-0056). Diese Scheibe liefert Grund und Werte
  (Untergrund, Ankerdatum, Bezugstag), keine Wettergrößen.
- **Radar- und amtlicher Zweig:** anker-unabhängig (Radar über `_resolve_alert_segment`,
  amtlich braucht den Anker nur für die Routengeometrie); sie schweigen nicht wegen fehlender
  Vergleichsbasis.
- **Dynamisches Label mit Ankerdatum** („Vergleichsbasis vom TT.MM. zu alt"): erforderte, dass
  das Register `_REASON_LABELS` Vorfalls-Werte trägt. Das Datum ist im Protokolleintrag
  festgehalten (`reference_at`); eine datierte Beschriftung kann als Folgeverbesserung kommen.

## Known Limitations

- Der Nutzer erfährt den Grund erst im nächsten zugestellten E-Mail-Briefing, nicht
  sofort — Buchführung, kein neuer Alarm (ein „Wache blind"-Alarm alle 15 Minuten wäre Lärm;
  #2050 schließt neue Alarmarten aus).
- Ortsvergleich: Ein frisch angelegtes, aktives Preset schreibt vor seinem ersten Briefing
  einmal je Tag `missing`; das ist gewollt (der Wächter ist in dieser Zeit tatsächlich blind),
  und die Entdopplung hält es bei einem Eintrag je Tag.
- Der Tag ist der Kalendertag des Laufs; ein Lauf über Mitternacht ergibt am neuen Tag einen
  neuen Eintrag.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (bestehend: ADR-0009, ADR-0056 gewahrt)
- **Rationale:** Der Grund `no_reference_basis` ist ein additiver Protokoll-Code ohne
  Migration (Gründe sind freie Strings; Felder additiv-defensiv). Die Scheibe verändert weder
  den Auslöser noch die Anker-Politik, sondern macht das Ergebnis der Anker-Prüfung im
  nutzerbezogenen Protokoll sichtbar. Die Entscheidung „kein frisches Holen ohne Anker" aus
  ADR-0009/0056 wird ausdrücklich bestätigt, nicht revidiert.

## Changelog

- 2026-10-01: Initial spec created (aus `docs/context/feat-2050-sz12-fehlende-vergleichsbasis.md`).
