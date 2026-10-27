# Context: Kanalzuordnung je Metrik (#1895 Frage 2, letzter Baustein Epic #1230)

> Workflow `feat-1895-kanalzuordnung-je-metrik` · Issue #1895 · Epic #1230
> Erhoben 2026-09-21. Stand `origin/main` = `fab1c74a`.

## Request Summary

Die Alarm-Kanalzuordnung („dieser Alarm geht nur per SMS") haengt heute an der
Regel-Entitaet `trip.alert_rules`, die seit #946/ADR-0043 fuer das Ausloesen
wirkungslos ist. Sie soll ein eigenes Feld **je Metrik** werden, direkt neben
der Empfindlichkeitsstufe. Damit faellt der letzte Zweck der Regel-Entitaet
als Kanal-Traeger weg.

### 🔴 Die Praemisse „fuer den Nutzer nichts sichtbar" traegt nur zum Teil

Der PO hat das Ticket geparkt, weil von Frage 2 „nichts sichtbar" sei. Die
**Datenaufraeumung** ist tatsaechlich unsichtbar — drei Punkte sind es nicht,
und die Spec muss sie benennen statt sie unter der Praemisse mitlaufen zu lassen:

1. **Die Editor-Spalte ist sichtbar.** Eine Kanalzuordnung je Metrik braucht
   eine Bedienflaeche. ADR-0043 verbietet ausdruecklich eine
   Konfigurationsflaeche ohne sichtbare Wirkung — verstecken ist also keine
   Option (Designfrage 5 haengt daran).
2. **`has_active_rules` faellt moeglicherweise weg** (Designfrage 6). Das Gate
   entscheidet heute, ob ein Trip ueberhaupt geprueft wird und ueberstimmt
   `alert_on_changes=False`. Ein Wegfall aendert Trip-Verhalten.
3. **Bestandstrips mit unsichtbaren Regel-Kanaelen** (Kernbefund C, R8). Deren
   aufgeloeste Kanalmenge aendert sich, wenn die Migration die Union nicht exakt
   reproduziert.

Verhaltensneutral ist der Umbau also nur unter Auflagen, nicht von selbst.

Letzte offene Substanz von Epic #1230 (Phasen 1–4 geliefert: #1231, #1229,
#1250, #1232). PO-Entscheid 2026-09-21: nicht einzeln bauen, sondern im Zug
von #1230.

---

## 🔴 Kernbefund A: der Kanal-Satz wird heute EINMAL JE ABO berechnet

**Das ist die eigentliche Schwierigkeit — nicht das neue Feld, sondern die
Granularitaet.** Heute entsteht genau ein `set[str]` pro Trip bzw. pro Preset
(`trip_alert.py:1652-1662`, `compare_alert.py:271-275`) und wandert als
`AlertEvaluationConfig.channels` durch die gesamte Auswertung
(`trip_alert.py:552`, `compare_alert.py:601`).

Ein Feld „je Metrik" verlangt, dass die Aufloesung **pro Alarm/Metrik** laeuft.
Das beruehrt jede der sechs Trip-Aufrufstellen:

| Stelle | Zweck |
|---|---|
| `trip_alert.py:400` | Unterdrueckungs-Protokoll |
| `trip_alert.py:552` | `AlertEvaluationConfig.channels` (Deviation-Engine) |
| `trip_alert.py:1072` | Anker-Auswahl je Kanal |
| `trip_alert.py:1671` | Radar-Alarm |
| `trip_alert.py:2509` | Versand Aenderungsalarm (`_send_alert`) |
| `trip_alert.py:2726` | amtlicher Alarm |

Vergleich-Seite: `compare_alert.py:110,601`, `compare_official_alert.py:472`,
`compare_radar_alert.py:168`.

**Nicht jede dieser Stellen hat ueberhaupt eine Metrik im Kontext** (Radar,
amtlicher Alarm, Anker-Auswahl). Die Analyse muss festlegen, was dort gilt —
Rueckfall auf den Abo-weiten Satz ist die naheliegende Antwort, muss aber
spezifiziert und getestet werden, sonst entsteht genau die Luecke aus
ADR-0021 (siehe Kernbefund F).

---

## 🔴 Kernbefund B: die Kanal-Logik ist heute vierschichtig

| # | Schicht | Granularitaet | Feld | Trip | Vergleich |
|---|---|---|---|---|---|
| 1 | Briefing-Kanaele (geerbt) | je Abo | `report_config.send_*` bzw. flache `send_*` | ja | ja, **ohne `send_email`** |
| 2 | Alarm-Kanal-Override | je Abo | `alert_channels` | `trip.go:151,204-209` | **fehlt im Go-Struct** (→ #2293) |
| 3 | Kanaele je Regel (UNION) | je Alarmregel | `alert_rules[].channels` | `models.py:1254`, `trip.go:66` | existiert nicht |
| 4 | Dringlichkeits-Schwelle je Kanal | je Abo | `alert_channel_thresholds` | `trip.go:157,218-224` | `compare_preset.go:105` |

**Schicht 3 soll verschwinden**, ersetzt durch „Kanaele je Metrik".

**Asymmetrie:** Der Vergleich hat das Geschwisterfeld (Schicht 4, #1461 S3b-2b),
aber nicht das Hauptfeld (Schicht 2). Genau diese Luecke will #2293 schliessen.

### Aufloesung heute — `src/services/alert_channels.py`

`resolve_alert_channels(override, inherited, rule_channel_sets, user_id)` (`:28-66`),
die EINE Auflaesung fuer beide `kind`-Werte (#2279 S1):

1. `override` gesetzt ⇒ ersetzt `inherited` vollstaendig (auch wenn leer)
2. keine aktiven Regeln ⇒ Ergebnis = `inherited` (`:52-53`)
3. aktive Regeln ⇒ **Union je Regel** (`:55-60`); leeres `rule_channels` faellt
   auf `inherited` zurueck
4. Tier-Gates einmal am Ende (`:62-65`)

| Adapter | Zeilen | `rule_channel_sets` |
|---|---|---|
| `_trip_channel_inputs` | `:86-93` | `[rule.channels for rule in active_rules]` (`:92`) |
| `_compare_channel_inputs` | `:96-110` | **immer `[]`** (`:110`) |

Der dritte Parameter ist die Schnittstelle, die der Umbau veraendert.
**`_trip_channel_inputs:92` ist die einzige Stelle in `src/`, die `rule.channels`
ueberhaupt liest.**

Die Kanal-Schwelle (Schicht 4) laeuft **nach** der Aufloesung:
`alert_channel_threshold.split_by_threshold` an 6 Stellen
(`trip_alert.py:2261,2522,2793`; `compare_alert.py:288`,
`compare_official_alert.py:279`, `compare_radar_alert.py:335`).

Der Versand nimmt ein fertiges Set entgegen und verzweigt hartkodiert je Kanal
(`notification_service.py`, 4 Versandfunktionen, z.B. `_dispatch_alert_message:1553`
mit email `:1683` · telegram `:1699` · sms `:1780` · premium_sms `:1794`).
**`notification_service.py` bleibt unberuehrt, solange weiterhin ein `set[str]`
ankommt.**

---

## 🔴 Kernbefund C: Schicht 3 ist im Trip-Detail schon heute unerreichbar

- `AlertRulesEditor` (einziger Ort mit Kanal-Chips je Regel) ist live **nur im
  Anlege-Wizard** montiert: `trip-new/TripNewEditor.svelte:862,1102`.
- Der Alarme-Tab im Trip-Detail (`trip-detail/AlarmeScheduleTab.svelte` →
  `shared/AlarmeTab.svelte`) schreibt **nur** `alert_channels` und rekonstruiert
  **nur** daraus bzw. aus `report_config`
  (`alarme-tab/tripChannelReconstruction.ts:18-43`). Er liest und schreibt
  `alert_rules` nicht.
- `TripEditView.svelte:205` (zweiter Mount) hat unter `frontend/src` keinen
  Importeur ausserhalb von Tests — Status „tot" ist zu verifizieren.

**Folge:** Ein Trip kann Regel-Kanaele tragen, die der Nutzer im Detail weder
sieht noch aendern kann. Wer im Alarme-Tab die Kanaele umstellt, aendert
Schicht 2 — waehrend Schicht 3 unveraendert in die Union eingeht. Ein
bestehender, stiller Widerspruch, den dieser Umbau aufloest.

- **`AlertRulesEditor` kennt nur `email/telegram/sms`** (`TripNewEditor.svelte:144`,
  `TripEditView.svelte:52-56`) — **kein `premium_sms`**, Verstoss gegen die
  Gleichrangigkeit der vier Kanaele (#1701, ADR-0049).

---

## 🔴 Kernbefund D: der Compare-Override laeuft ins Leere

`alert_channels.py:103` liest `preset.get("alert_channels")` — aber das
Go-`ComparePreset` kennt das Feld nicht (`compare_preset.go:95-96` sagt es
ausdruecklich) und verwirft es beim Decode (`handler/compare_preset.go:298`
via `mergeBriefingPatch`, `handler/briefing_subscription.go:174-198`).
In Produktion ist der Compare-Override praktisch immer `None`.

Frontend-Nahtstelle bereits markiert: `shared/alarmeVergleichSpeicherung.ts:69`
— „Nahtstelle fuer #2293 `alert_channels`".

---

## 🔴 Kernbefund E: `display_config` hat KEINEN Feld-Level-Merge

Der Go-Merge fuer `display_config` ist genau eine Ebene tief
(`handler/config_merge.go:11-22`, `dst[k] = v` je Key; aus `handler/trip.go:335-336`
und `briefing_subscription.go:174-198`). **`metric_alert_levels` wird beim
Senden komplett ersetzt, nie feldweise gemergt** — das Frontend kommentiert es
ausdruecklich (`alarme-tab/tripAlertMetricsFromCatalog.ts:44-46`,
`AlarmeScheduleTab.svelte:40-45`).

Das widerspricht dem Pointer-Merge-Muster, das `alert_channels` und
`alert_channel_thresholds` genau deshalb als **Top-Level-Felder** fuehrt
(#1701-Begruendung, `trip.go:196-224`; Go-Merge `handler/trip.go:401-414`).
Ein Kanalfeld in `display_config` erbt die Voll-Ersetzung und damit das
GR221-Risiko; ein Top-Level-Geschwisterfeld erbt den sicheren Feld-Level-Merge.

**Python laedt unbekannte Top-Level-Keys nicht ins Trip-Dataclass**
(`_trip_to_dict` schreibt nur bekannte Keys, `loader.py:1643-1660`) — ein neues
Trip-Feld braucht typisierte Entsprechungen in Python UND Go. Beim Vergleich
genuegt das Roh-Dict (`preset.raw`). Unbekannte Keys ueberleben `save_trip`
nur dank `_deep_merge_preserve_unknown` (`loader.py:128-140`).

---

## 🔴 Kernbefund F: harte ADR-Grenzen

- **ADR-0043** (Empfindlichkeitsstufe = einziger Alarm-Regler): Die
  Kanalzuordnung darf **nicht** entscheiden, OB eine Metrik alarmiert — das
  waere der verbotene zweite Regler. Sie darf nur den **Weg** bestimmen.
  Ebenso verboten: eine Konfigurationsflaeche ohne sichtbare Wirkung (genau
  der Fehler, den #1895 aufraeumt) und ein leeres Kanal-Set, das eine Meldung
  spurlos verschwinden laesst.
- **ADR-0046** (Alarm-Kanal-Schwelle) ist die zustaendige ADR-Ebene:
  „Empfindlichkeit beantwortet OB, die Kanal-Schwelle beantwortet AUF WELCHEM
  WEG" (`:37-51`). Das neue Feld gehoert auf diese Ebene. Folgepflicht `:101-105`:
  jede Stelle, die ein Kanal-Set fuer den Versand aufloest, muss die Schwelle
  anwenden. **Ein neues ADR ist faellig** (Fortschreibung von 0046).
- **ADR-0049** (Premium-SMS): vier Kanaele, Tier-Gates genau einmal im
  gemeinsamen Kern. Harte Dreier-Listen sind ab #1701 unvollstaendig.
- **ADR-0021 — die Praezedenzfalle:** `_radar_effective_channels()` las
  `trip.alert_channels` nie; ein Feld, das an einer Nahtstelle nicht gelesen
  wird, ist dort wirkungslos (`:120-130`). **Das neue Feld muss an EINER Stelle
  wirken**, nie in einer Sonderfassung. Mit Kernbefund A ist das die
  Hauptgefahr dieses Umbaus.
- **ADR-0023**: additiv, `omitempty`, beide `kind`-Werte, Roundtrip-Test,
  Migration im 1250-Muster, `kind` nie raten.
- **Kein ADR zur Kanal-Aufloesung selbst** — Spec #2279 sagt ausdruecklich
  „keine neue, ADR-0021 und ADR-0023 gelten" (`:285-294`).

---

## Schluesselmenge — zwei verschiedene Vokabulare, nicht verwechseln

| Menge | Umfang | Wo | Wofuer |
|---|---|---|---|
| Go `AlertableMetrics` (`trip.go:227-236`) | 6 | `wind_gust`, `precipitation_sum`, `temperature_min`, `temperature_max`, `snow_line`, `thunder_level` | Vokabular der **Regel-Entitaet** (Schicht 3) |
| Python-Enum `AlertMetric` (`models.py:1212-1237`) | 16 | zusaetzlich `*_change`, `fresh_snow`, `cape`, `visibility`, `freezing_level`, `thunder_onset`, `precipitation_heavy_onset`, `humidity` (tot) | Schluessel von `metric_alert_levels` |
| Frontend `ALERTABLE_METRICS` (`alerts-tab/alertMetricTable.ts:188-205`) | 15 | `AlertMetric` ohne `snow_line` | Anzeigereihenfolge der Stufen-Tabelle |

**Die Stufen-Tabelle nutzt das volle `AlertMetric`-Enum, nicht die Go-Sechs.**
Soll die Kanalzuordnung „neben der Stufe" stehen, ist ihre Schluesselmenge die
der Stufe (15 angezeigte), nicht die der abgeloesten Regel (6).
Legacy-Migration `snow_line` → `freezing_level` beachten (`loader.py:730-744`,
`store/trip.go:314-330`). Go validiert weder Metrik-Keys noch Stufenwerte.

**Editor-Ort:** geteiltes `AlarmeTab.svelte` (Prop `context`, Default `route`) →
`alerts-tab/AlertMetricLevelTable.svelte` (Kopf heute „Metrik / Empfindlichkeit
/ Schwellwert", `:63-66`) → `AlertMetricLevelRow.svelte` (Stufen
`['off','entspannt','standard','sensibel']`, `:19`). **Das ist die Zeile, an die
eine Kanalspalte andockt.** Mounts: Trip `AlarmeScheduleTab.svelte:60`;
Vergleich `CompareTabs.svelte:1046`, `CompareNewEditor.svelte:398,489`.

---

## 🔴 Konflikt mit #2293 (offen, priority:high, Epic #2345)

#2293 will `ComparePreset.AlertChannels *AlertChannelsConfig` nachbauen (Schicht 2
am Vergleich spiegeln) **plus** Migration `scripts/migrate_2279_alert_channels.py`.
Dieser Umbau definiert dieselbe Flaeche neu. Beides nacheinander hiesse, dasselbe
Feld zweimal zu migrieren — genau die Verschwendung, wegen der der PO #1895 an
#1230 gekoppelt hat.

**Tech-Lead-Entscheidung (Intake 2026-09-21):** #1895-F2 zuerst, legt die Zielform
fest; #2293 wird danach gegen die neue Form neu geschnitten. Notiz an #2293 geht
raus, sobald die Spec steht. Ebenfalls beruehrt: **#2212** (E-Mail am Vergleich
nicht abwaehlbar, `send_email` fehlt).

Die Spec #2279 nennt beides bereits als Scheibe S2 (`:263-283`) und warnt: eine
Migration flach → `alert_channels` friert die Kanaele ein, solange der Tab flache
Felder schreibt (Override gewinnt).

---

## Nicht verwechseln: die andere Metrik×Kanal-Matrix

`channelBuckets` / `layout: {channel: metrics[]}` (Output-Layout #14, #1575 S3,
#1719 S3, ADR-0050) regelt, **welche Wettergroesse im Briefing welchen Kanal
erreicht** — nicht Alarme. Spec: `docs/specs/modules/fix_1575_channel_metric_selection.md`.

Die neue Alarm-Kanalzuordnung ist eine **zweite, unabhaengige** Matrix mit
derselben Achsenbeschriftung. Spec und Benennung muessen das trennscharf halten.

---

## Was von `alert_rules` uebrig bleibt

Nach dem Umbau hat die Regel-Entitaet noch **einen** Zweck:

- **Pruef-Gate `has_active_rules`** (`trip_alert.py:459-462` im `send`-Pfad mit
  Gate `:465-468`; `trip_alert.py:895-898` in `check_all_trips` mit Gate `:906-908`).
  Eine aktive Regel ueberstimmt `report_config.alert_on_changes=False` bzw.
  entscheidet, ob der Trip ueberhaupt geprueft wird.
- **Diagnose** `api/routers/validator.py:116-119,137-139` (`config_source`),
  haengt nicht am Versand.

**Am Vergleich gibt es kein `has_active_rules`-Aequivalent** und keine
Regel-Entitaet (`alert_channels.py:102`: „Der Vergleich kennt keine
Alarm-Regeln"). Dessen Gates sind `is_silenced`, Cooldown, Tageslimit, Ruhezeit,
`check_briefing_imminent` (`compare_alert.py:150ff`). Die Analyse muss
entscheiden, ob das Gate bleibt, wandert oder faellt — **ein Wegfall wuerde das
Trip-Verhalten aendern und ist damit nicht verhaltensneutral.**

**Nebenbefund (Sammel-Issue #1199-Kandidat):** `trip_alert.py:438,442` behauptet
im Kommentar noch, `alert_rules` sei Source-of-Truth fuer den Detektor — seit
#946 falsch. `_select_change_detector` (`:817`) speist sich aus
`metric_alert_levels`/`display_config`.

---

## Blast Radius (gemessen)

| Bereich | Dateien |
|---|---|
| **Routing-Kern** | `alert_channels.py`, `trip_alert.py`, `compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py` (die vier letzten nur bei Signaturaenderung) |
| **Python-Persistenz** | `models.py`, `loader.py`, `trip.py` (Doku), `api/routers/validator.py` |
| **Go** | `model/trip.go`, `model/compare_preset.go`, `store/trip.go`, `handler/trip.go`, `handler/weather_config.go`, `handler/compare_preset.go`, `handler/briefing_subscription.go` |
| **Frontend** | `alert-rules-editor/` (`alertChannels.ts`, `AlertRulesEditor.svelte`, `AlertRuleRow.svelte`), `alerts-tab/AlertCard.svelte`, `alerts-tab/AlertMetricLevelTable.svelte`/`-Row.svelte`, `shared/AlarmeTab.svelte`, `alarme-tab/alarmeDeliveryPayload.ts`, `alarme-tab/tripChannelReconstruction.ts`, `shared/alarmeVergleichSpeicherung.ts`, `compare/compareEditorSave.ts`, `compare/alarmePropsAus.ts`, `types.ts:345`, `trip-new/TripNewEditor.svelte`, `edit/TripEditView.svelte` |
| **Skripte** | neues Migrationsskript; beruehrt `migrate_1244_null_lists.py`, `migrate_1231_corridors.py`, `seed_validator_archive.py` |
| **`notification_service.py`** | **unberuehrt**, solange ein `set[str]` ankommt |

**Das ist deutlich mehr als eine Scheibe.** Der Schnitt gehoert in die Analyse;
eine naheliegende Teilung ist: (S1) Feld + Persistenz + Migration
verhaltensneutral · (S2) Aufloesung auf Metrik-Granularitaet · (S3) Editor-Spalte
· (S4) Rueckbau `alert_rules[].channels`.

### Tests, die der Umbau rot faerbt

**An `rule.channels` (ca. 15 Tests in 6 Dateien):**
`tests/tdd/test_alert_channel_resolution_parity.py:202` ·
`tests/tdd/test_issue_638_alerts_redesign.py:335,363,387,409,424,452,474,609` ·
`tests/tdd/test_trip_alert_channel_precedence.py:107,183` ·
`tests/tdd/test_issue_1069_tier_channel_gating.py:406,424` ·
`tests/tdd/test_issue_816_alert_deviation.py:745` ·
`tests/unit/test_radar_alert_channel_resolution.py:567,620`

**An der Override-Aufloesung (ca. 25 Tests in ~10 Dateien), rot nur bei
Signatur-/Symbolwechsel:** `test_alert_channel_resolution_parity.py` (AC-1/3/4/5) ·
`test_compare_alert_channels.py:188,229,258,288` (die vier
`test_ac6_*delegates*` haengen am **Symbolnamen** `effective_alert_channels` im
Verbrauchermodul) · `test_radar_alert_channel_resolution.py` ·
`test_914_slice4_alert_sms_dispatch.py` · `test_issue_684_alert_email_guard.py` ·
`test_alert_channel_threshold.py` · `test_alert_channel_premium_sms.py`

**Korrektur einer naheliegenden Annahme:** `tests/tdd/test_alert_tenancy_two_users.py`
nagelt die Union-Semantik **nicht** fest (enthaelt keine `AlertRule`-Konstruktion);
es ist Mandantentrennungs-Schutz zu #1460.

**Go:** keine Assertions zu `rule.channels` ausser Roundtrip
`internal/store/store_trip_briefings_test.go:221` und `SyncAlertRules`
(`model/trip.go:362` bewahrt `channels`).

---

## Migrations- und Testvorlagen

| Zweck | Vorlage |
|---|---|
| Feld additiv ergaenzen (schlank) | `scripts/migrate_1231_corridors.py` — Dry-Run-Default (`:237`), `--root` required (`:235`), `_make_backup` (`:206-212`), Zwei-Phasen `_collect_plan` (`:157-203`) + `MigrationAbort` vor jedem Schreiben (`:63`), `_apply` (`:215-230`), Report (`:251-255`) |
| Vollstaendig (Kollision, kind-genau) | `scripts/migrate_1250_briefings.py` — `_target_state` (`:82-109`), `claimed`-Dict (`:147-155`), korrupte Quelle als SKIP (`:193,210`) |
| RMW additiv | `migrate_1231_corridors.py:215-230` (`trip["corridors"]=…`, ganzes Dict zurueckschreiben); Python-Store `loader.py:128` `_deep_merge_preserve_unknown`, Additiv-Kommentar `:1606-1628` |
| Migrationstest | `tests/tdd/test_corridor_migration.py` — lossless `:144,189`, Dry-Run schreibt nichts `:326`, Idempotenz `:374`, Legacy-Felder ueberleben `:407`, Abbruch ohne Teil-Schreiben `:273`, Backup-PermissionError `:561` |
| Roundtrip neues Feld | `tests/test_briefing_route_cutover.py:275` (`test_roundtrip_nested_maps_no_field_loss_via_briefings_path`) — prueft `report_config`, `display_config.metric_alert_levels`, `corridors`, `alert_rules`, `some_unknown_field` |

**Datenlage:** `data/users/<user_id>/briefings/<id>.json`, eine Datei je Entitaet,
mit `kind`-Diskriminator (ADR-0023, `api_contract.md:806-807,2059`).
Alt-Stores `trips/`, `compare_presets.json` sind seit #1250 S7a/S7b tot (#1708).
Trip-ID kann gleich Preset-ID sein (F001) — `kind` explizit tragen, nie raten.

**Achtung:** Edits an `models.py`, `trip.py`, `loader.py`, `internal/model/*.go`,
`internal/store/store.go` loesen automatisch den Pre-Snapshot-Hook
`data_schema_backup.py` aus.

---

## Offene Designfragen fuer /20-analyse

1. **Granularitaet (Kernbefund A).** Laeuft die Aufloesung kuenftig pro Metrik?
   Was gilt an den Aufrufstellen ohne Metrik-Kontext (Radar, amtlich,
   Anker-Auswahl)? Rueckfall auf den Abo-weiten Satz muss spezifiziert und
   getestet sein.
2. **Ablageort — das Praezedenz-Argument traegt NUR zur Haelfte.**
   `AlertChannelThresholdsConfig` stand vor derselben Wahl und wurde Top-Level.
   Die Begruendung (`trip.go:211-217`) lautet aber woertlich: Pointer je Kanal,
   damit „Kanal fehlt im Body" von „Kanal explizit gesetzt" unterscheidbar
   bleibt. **Das ist ein Argument ueber vier feste, benannte Struct-Felder — es
   uebertraegt sich nicht ungeprueft auf eine Map mit 15 offenen
   Metrik-Schluesseln.** Zu klaeren ist konkret:
   - Ein Top-Level-Map-Feld wuerde von `mergeBriefingPatch`
     (`briefing_subscription.go:174-198`) **eine Ebene tief** gemergt: je
     Metrik-Key gemergt, der Kanal-Wert je Metrik aber komplett ersetzt. Das ist
     metrik-genau, nicht kanal-genau — reicht das?
   - Der Trip-PUT laeuft ueber ein explizites DTO (`handler/trip.go:230ff`);
     ein neues Feld muss dort ergaenzt werden, sonst faellt es still raus.
   - In `display_config` waere es dagegen Voll-Ersetzung (Kernbefund E).

   Tendenz weiterhin Top-Level, aber **als begruendete Entscheidung der Analyse,
   nicht als Praezedenz-Uebernahme.**
3. **Verhaeltnis zu Schicht 2.** Bleibt `alert_channels` globaler Override
   (Metrik ohne eigene Zuordnung erbt ihn) oder wird er abgeloest? Ersteres ist
   vertraeglicher und haelt Spec-#2279-AC-1/AC-3 am Leben.
4. **Wirkreihenfolge zu Schicht 4.** Metrik-Zuordnung vor oder nach
   `split_by_threshold`? ADR-0046-Folgepflicht: die Schwelle darf nicht umgangen
   werden.
5. **Leeres Kanal-Set.** ADR-0043 verbietet spurloses Verschwinden. Was passiert
   bei einer Metrik, der der Nutzer alle Kanaele nimmt — gesperrt in der UI, oder
   Rueckfall auf den Abo-Satz?
6. **`has_active_rules`.** Bleibt, wandert oder faellt? Ein Wegfall aendert
   Trip-Verhalten und waere nicht verhaltensneutral.
7. **Vergleich.** Bekommt er die Metrik-Zuordnung (Paritaet), obwohl es dort
   Schicht 3 nie gab? Was migriert dort?
8. **Premium-SMS.** Alle vier Kanaele — der abgeloeste `AlertRulesEditor` kannte drei.
9. **Scheibenschnitt.** Der Blast Radius traegt keine Ein-Schuss-Lieferung.

---

## Risks & Considerations

- **R1 Datenverlust.** Schema-Rework auf `data/users/`. RMW mit Merge, nie
  Replace (#102). Dry-Run-Default, tar.gz-Backup, Idempotenz, Pro-Nutzer-Scoping,
  Report.
- **R2 Stille Kanal-Abschaltung.** Ein Alarm, der einen Kanal verliert, ist
  unsichtbar bis zum Ernstfall. Die Migration muss je Abo belegen: aufgeloeste
  Kanalmenge vorher == nachher.
- **R3 Nahtstelle ohne Leser** (ADR-0021-Praezedenz). Mit Kernbefund A die
  Hauptgefahr: sechs Trip-Aufrufstellen, von denen nicht alle eine Metrik kennen.
  Mutations-Gegenprobe muss jede einzeln treffen.
- **R4 Vier gleichrangige Kanaele** (#1701, ADR-0049, Paritaets-Audit #1533).
- **R5 Doppelmigration mit #2293** — durch Reihenfolge entschaerft.
- **R6 Mandantentrennung.** Jeder datenbewegende Endpoint mit ZWEI Nutzern testen.
- **R7 Parallelsitzung.** #2276 (Compare-Speicherweg, Epic #2345) laeuft
  zeitgleich in einer anderen Sitzung und fasst `AlarmeTab`/`CompareTabs` an.
  Kollisionsflaeche im Frontend beobachten.
- **R8 Bestandsdaten mit unerreichbaren Regel-Kanaelen** (Kernbefund C). Trips
  koennen Regel-Kanaele tragen, die nie im Detail sichtbar waren. Die Migration
  muss sie uebernehmen — R2 verlangt es.
- **R9 `display_config` wird voll ersetzt** (Kernbefund E). Bei Ablage dort
  muesste der Client das Feld immer vollstaendig senden.

---

## Related Files (Kern)

| Datei | Relevanz |
|---|---|
| `src/services/alert_channels.py:28-126` | die EINE Auflaesung, beide Adapter, Dispatcher |
| `src/services/trip_alert.py:400,459-468,552,817,895-908,1072,1671,2509,2726,2889` | Aufrufstellen, `has_active_rules`, Detektor-Wahl |
| `src/services/compare_alert.py:110,271-275,573-620` | Vergleich-Builder, Kanal-Satz |
| `src/services/alert_channel_threshold.py:20` | Schicht 4, `split_by_threshold` |
| `src/services/notification_service.py:1553,1683-1806` | Versand je Kanal |
| `internal/model/trip.go:151-236` | `AlertChannels`, Thresholds, Pointer-Merge-Begruendung, `AlertableMetrics` |
| `internal/model/compare_preset.go:48,75,91-105` | `DisplayConfig`-Bucket, fehlendes `alert_channels` |
| `internal/handler/config_merge.go:11-22` | flacher `display_config`-Merge |
| `internal/handler/trip.go:335-336,401-414` | beide Merge-Arten im Vergleich |
| `src/app/models.py:859,1212-1237,1254,1324` | Stufe, `AlertMetric`-Enum, `AlertRule.channels` |
| `src/app/loader.py:128-140,195-197,730-744,1643-1660,1704-1715` | Merge, Defaults, Legacy-Migration, Serialisierung |
| `frontend/.../alerts-tab/AlertMetricLevelTable.svelte`, `-Row.svelte` | Zielzeile der Kanalspalte |

## Existing Specs

- `docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md` — Spec der heutigen Auflaesung (wird geaendert; AC-1..AC-7, Mutations-Gegenproben, Known Limitations `:263-283`)
- `docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md`, `..._s3b2b_compare_kanal_schwelle.md` — Schicht 4
- `docs/specs/modules/fix_1895_alarm_modus_rueckbau.md`, `fix_1895_s2_alarmkarte_rueckbau.md` — Schritt 1 dieses Tickets
- `docs/specs/modules/fix_1575_channel_metric_selection.md` — die ANDERE Metrik×Kanal-Matrix

## ADRs

`docs/adr/0043-*` (einziger Alarm-Regler) · `0046-alarm-kanal-schwelle.md`
(zustaendige Ebene, Fortschreibung faellig) · `0049-premium-sms-vierter-kanal.md`
· `0021-shared-deviation-alert-engine.md:120-130` (Praezedenzfalle) ·
`0023-briefing-subscription-shared-model.md`

---

# Analysis

> Erstellt 2026-09-22 in Phase 2 (`/20-analyse #1895`). Stand `origin/main` = `fab1c74a`.
> Diese Sektion ist die Entscheidungsgrundlage fuer `/30-write-spec` und nach `/clear`
> allein lesbar — sie wiederholt bewusst, was oben schon steht, wenn es fuer eine
> Entscheidung noetig ist.

## Type

**Feature** (Datenmodell-Rework mit Folge-Verhaltensaenderung). Das Ticket traegt zwar
das Label `bug`, aber der nutzersichtbare Fehlerteil ist mit Schritt 1 (`a928dbce`) und
Schritt 2 (`fab1c74a`) geliefert. Offen ist allein Frage 2 — ein additives Feld plus
Umhaengen der Kanal-Aufloesung.

## 🔴 Entscheidung 0: Dieser Workflow liefert genau EINE Scheibe (S1)

Der oben gemessene Blast Radius (5 Python-Module im Routing-Kern, 7 Go-Dateien, 15+
Frontend-Dateien, Migrationsskript) traegt keine Ein-Schuss-Lieferung. Das LoC-Limit
des Workflows liegt bei 250 produktiven Zeilen. Entscheidender noch: `/40-tdd-red` deckt
**alle** ACs der Spec ab und darf nicht nachtraeglich auf eine Teilscheibe verengt werden.
**Die Verengung muss also jetzt passieren, an der Spec-Grenze** — nicht spaeter im RED.

Die Spec aus `/30-write-spec` beschreibt daher **ausschliesslich S1**. S2–S4 werden beim
Abschluss dieses Workflows als eigene Issues angelegt und in #1230 sowie #1895 verlinkt.

| Scheibe | Inhalt | Liefert dieser Workflow? |
|---|---|---|
| **S1** | Feld `alert_metric_channels` top-level auf beiden `kind`-Werten, typisiert in Go UND Python, additiv, `omitempty`. **Kein Leser im Alarm-Pfad, keine Migration, kein Frontend.** Plus ADR-0077 und `api_contract.md`. | **JA** |
| S2 | Aufloesung auf Metrik-Granularitaet (`alert_channels.py` + 6 Trip-Aufrufstellen + Vergleich-Stellen) · Migration `alert_rules[].channels` → neues Feld | nein — eigenes Issue |
| S3 | Editor-Spalte in `AlertMetricLevelTable.svelte`/`-Row.svelte` (Trip + Vergleich) | nein — eigenes Issue |
| S4 | Rueckbau `alert_rules[].channels`, `AlertRulesEditor`, toter `TripEditView` | nein — eigenes Issue |

**Warum S1 den Schnitt traegt:** Ohne Leser kann das Feld nichts abschalten — Risiko R2
(stille Kanal-Abschaltung) kann in S1 strukturell nicht feuern. Die Migration gehoert
deshalb nach S2, direkt neben den Code, der das Feld erst massgeblich macht; sie in S1 zu
ziehen wuerde das LoC-Limit sprengen und ein Feld migrieren, das niemand liest.
S1 fasst ausserdem **keine einzige `.svelte`-Datei** an und hat damit null
Kollisionsflaeche mit der Parallelsitzung an #2276 (R7) — das ist durch den Schnitt
erzwungen, nicht zufaellig.

**Reihenfolge-Zwang: S2 MUSS vor S3.** `docs/adr/0043-*.md:79-80` verwirft woertlich
„eine Konfigurationsflaeche ohne sichtbare Wirkung". Eine Editor-Spalte, die auf ein
Feld schreibt, das keine Aufrufstelle liest, ist genau dieser verworfene Fall — und
genau der Fehler, den #1895 aufraeumt. S1 ist davon nicht betroffen: S1 hat gar keine
Bedienflaeche.

## Entscheidungen zu den neun Designfragen

Alle neun sind Tech-Lead-Entscheidungen und hier beantwortet. Freigabepflichtig sind
allein die ACs der Spec, nicht diese Entscheidungen.

| # | Frage | Entscheidung | Tragender Grund |
|---|---|---|---|
| 1 | Granularitaet | Aufloesung laeuft kuenftig **pro Metrik**; Aufrufstellen ohne Metrik-Kontext (Radar, amtlicher Alarm, Anker-Auswahl) fallen auf den **Abo-weiten Satz** zurueck. Gilt ab **S2**. | ADR-0021-Praezedenz (`0021-*.md:120-130`): ein Feld, das an einer Nahtstelle nicht gelesen wird, ist dort wirkungslos. Die Mutations-Gegenprobe in S2 muss jede der sechs Trip-Aufrufstellen **einzeln** treffen. |
| 2 | Ablageort | **Top-Level**, Go-Typ **`map[string]interface{}`**, JSON-Tag `alert_metric_channels`, im Trip-PUT ueber `mergeConfigMap` gemergt (Muster `DisplayConfig`, `internal/handler/trip.go:334-336`). | **Datensicherheit, nicht Praezedenz.** In `display_config` waere es Voll-Ersetzung (Kernbefund E) = GR221-Klasse (#102). Siehe Entscheidung 2 unten. |
| 3 | Verhaeltnis zu Schicht 2 | `alert_channels` **bleibt** globaler Override. Eine Metrik ohne eigenen Eintrag **erbt** ihn. | Vertraeglicher; haelt Spec-#2279 AC-1/AC-3 am Leben. „Kein Eintrag" ist damit kein Sonderfall, sondern der Normalfall — genau das macht S1 verhaltensneutral. |
| 4 | Wirkreihenfolge zu Schicht 4 | Metrik-Zuordnung **zuerst** (bestimmt die Kanalmenge), danach `split_by_threshold`. | ADR-0046-Folgepflicht (`:101-105`): jede Stelle, die ein Kanal-Set aufloest, muss die Schwelle anwenden. Umgekehrte Reihenfolge wuerde sie umgehen. |
| 5 | Leeres Kanal-Set | **Rueckfall auf den Abo-Satz**, kein spurloses Verschwinden. Die UI (S3) sperrt nicht, sondern zeigt „erbt". | ADR-0043 verbietet, dass eine Meldung spurlos verschwindet. |
| 6 | `has_active_rules` | **Bleibt unangetastet.** Ausdrueckliches **Nicht-Ziel** dieses Reworks — weder S1 noch S2–S4 fassen es an. | Ein Wegfall aendert Trip-Verhalten (ueberstimmt `alert_on_changes=False`) und waere nicht verhaltensneutral. Gehoert in ein eigenes Ticket mit eigener Begruendung. |
| 7 | Vergleich | **Ja, Paritaet ab S1.** `ComparePreset` bekommt das Feld gleich mit. | Fast gratis: Der Vergleich-PUT laeuft generisch ueber `mergeBriefingPatch` und braucht **keine** Handler-Aenderung. Gleichrangigkeit Trip/Vergleich ist PO-Vorgabe. |
| 8 | Premium-SMS | **Alle vier Kanaele** von Anfang an — `email`, `telegram`, `sms`, `premium_sms`. | #1701, ADR-0049, Paritaets-Audit #1533. Der abgeloeste `AlertRulesEditor` kannte nur drei; das wird hier nicht fortgeschrieben. |
| 9 | Scheibenschnitt | S1–S4 wie oben; dieser Workflow liefert S1. | Siehe Entscheidung 0. |

## 🔴 Entscheidung 2 im Detail: warum der Go-Typ die eigentliche Entscheidung ist

Nicht der Ablageort allein entscheidet ueber Datensicherheit, sondern der **Go-Typ**:

- **Vergleich (`ComparePreset`):** Der PUT laeuft durchgehend generisch ueber
  `applyComparePresetPatch` → `mergeBriefingPatch` (`internal/handler/briefing_subscription.go:188-196`).
  Dieser Pfad arbeitet auf rohem JSON **vor** dem Unmarshal und mergt **jeden**
  Top-Level-Key mit Objekt-Wert automatisch eine Ebene tief. Metrik-genauer Merge
  **gratis, ohne eine Zeile Handler-Code**.

  ⚠️ **Das allein genuegt nicht** (nachgemessen 2026-09-22 an
  `internal/handler/compare_preset.go:292-300`): direkt nach dem Merge steht
  `json.Unmarshal(merged, &p)` in das **typisierte** `model.ComparePreset`. Ein Key
  ohne Struct-Feld ueberlebt den Merge, wird aber beim Unmarshal **verworfen** — genau
  der Mechanismus, an dem heute der Compare-`alert_channels`-Override scheitert
  (Kernbefund D). **Das Go-Struct-Feld am `ComparePreset` ist damit Pflicht, nicht
  Kuer.** Gratis ist nur der Handler-Code, nicht das Feld.
- **Trip:** Der PUT laeuft **nicht** ueber diesen Pfad, sondern ueber das explizite
  DTO `tripUpdateRequest` (`internal/handler/trip.go:216-260`) mit Feld-fuer-Feld
  codiertem Merge. Ob das neue Feld denselben Merge bekommt, haengt **einzig am Typ**:
  - `map[string]interface{}` → eine Zeile `existing.X = mergeConfigMap(existing.X, *req.X)`
    (verifiziert am Vorbild `DisplayConfig`/`WeatherConfig`/`Aggregation`/`ReportConfig`,
    `internal/handler/trip.go:328-340`) ⇒ metrik-genauer Merge, **symmetrisch zum Vergleich**.
  - eigener Slice-/Struct-Typ ohne `mergeConfigMap`-Kompatibilitaet (Muster `AlertRules`,
    `Corridors`) → `existing.X = *req.X` ⇒ **atomarer Ersatz des ganzen Feldes**.

Im zweiten Fall wuerde ein Editor, der in S3 nur die Kanaele **einer** Metrik speichert,
alle anderen Metriken der Map still loeschen — exakt die GR221-Klasse. **Der Typ muss
deshalb in S1 festgelegt werden, nicht in S2/S3 nachgeruestet.** Das kostet in S1 nichts
extra; es ist eine reine Typentscheidung.

**Granularitaetsgrenze, bewusst akzeptiert:** Der Merge ist **metrik-genau, nicht
kanal-genau** — die Kanalliste **einer** Metrik wird komplett ersetzt. Das ist richtig
so: Die Kanalliste einer Metrik ist ein Wert, kein Container. Ein Client, der die Kanaele
einer Metrik aendert, sendet immer die ganze neue Liste dieser Metrik.

## 🔴 Korrektur am Kontext oben: Python verliert unbekannte Top-Level-Keys NICHT

Kernbefund E behauptet, Python lade unbekannte Top-Level-Keys nicht. Das stimmt nur
halb und ist fuer die Risikobewertung wichtig:

`loader.py:645-667` fuehrt eine `KNOWN_TOP_LEVEL`-Menge; alles ausserhalb landet in
`Trip.extra` (`:667,699`, Issue #991) und wird beim Serialisieren per `setdefault`
wieder eingespeist (`:1788-1790`) — **verlustfrei, ohne jede Codeaenderung**.

**Folge fuer S1:** Selbst ein Teil-Deploy (Go schreibt das Feld, Python kennt es noch
nicht) verliert keine Daten. Das typisierte Python-Feld ist trotzdem Teil von S1 — nicht
fuer die Persistenz, sondern weil S2 einen benannten Leser braucht und `extra` eine
Auffangnetz-Mechanik ist, keine Schnittstelle.

⚠️ Eine Falle steht direkt daneben (`loader.py:657-658`): Steht ein Key in
`KNOWN_TOP_LEVEL`, aber ohne modelliertes Feld, wird ein zuvor persistierter Alt-Wert
**nicht** ueber `extra` konserviert. Das neue Feld muss deshalb **alle drei** Stellen
zugleich bekommen — `KNOWN_TOP_LEVEL`-Eintrag **und** Dataclass-Feld **und**
Rueckschreiben in `_trip_to_dict`. Nie nur eine oder zwei davon.

## Schluesselmenge des neuen Feldes

**Die 15 angezeigten Metriken** — das `AlertMetric`-Enum ohne `snow_line`
(`frontend/.../alerts-tab/alertMetricTable.ts:187-203`; `snow_line` ist per
Legacy-Migration durch `freezing_level` abgeloest, `loader.py:730-744`,
`internal/store/trip.go:314-330`).

Begruendung: Das Feld steht **neben der Empfindlichkeitsstufe**, also ist seine
Schluesselmenge die der Stufe — nicht die sechs der abgeloesten Regel-Entitaet
(Go `AlertableMetrics`, `internal/model/trip.go:227-236`).

**S1 validiert die Schluessel nicht.** Go validiert heute weder Metrik-Keys noch
Stufenwerte (nachgeprueft: weder `validateTrip` noch `validateComparePreset` fassen sie
an). Eine neue Validierung waere Scope-Creep und wuerde Bestandsdaten mit `snow_line`
brechen. Die Schluesselmenge ist damit eine **Analyse-Entscheidung fuer S3**, nicht
S1-Code.

## Affected Files (S1)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `internal/model/trip.go` | MODIFY | Feld `AlertMetricChannels map[string]interface{}` mit `json:"alert_metric_channels,omitempty"` + Docstring (Muster `AlertChannels`, `:151-163`) |
| `internal/model/compare_preset.go` | MODIFY | dito (Muster `AlertChannelThresholds`, `:91-98`) |
| `internal/handler/trip.go` | MODIFY | DTO-Feld in `tripUpdateRequest` + `mergeConfigMap`-Zeile im RMW-Block, analog `:334-336` |
| `internal/handler/compare_preset.go` | — | **unberuehrt**, laeuft generisch ueber `mergeBriefingPatch` — aber das Struct-Feld ist trotzdem Pflicht (typisierter Unmarshal verwirft sonst den Key, s.o.) |
| `internal/store/trip.go` | — | **unberuehrt, nachgemessen 2026-09-22:** `SaveTrip` marshalt das Struct transparent (`:272`), `LoadTrip`/`LoadTrips` unmarshalen transparent (`:197`/`:141`). Ein neues Struct-Feld fliesst ohne Registrierung mit; die `snow_line`→`freezing_level`-Legacy-Migration (`:314-330`) ist feldspezifisch und beruehrt es nicht. |
| `src/app/trip.py` | MODIFY | Dataclass-Feld `alert_metric_channels: Optional[dict] = None` (Muster `alert_channels`, `:221`) |
| `src/app/loader.py` | MODIFY | `KNOWN_TOP_LEVEL`-Eintrag + Konstruktor-`data.get(...)` + bedingtes Schreiben in `_trip_to_dict` (Muster `:652,695,1625-1626`) |
| `src/app/models.py` | MODIFY | optionales typisiertes `ComparePreset`-Feld (Paritaet). **Fuer die Persistenz nicht noetig, nachgemessen:** `compare_preset_to_dict` liefert `preset.raw` unveraendert zurueck (`src/app/loader.py:345-352`) — jeder Key uebersteht den Python-Roundtrip ohne Codeaenderung. Das Feld dient S2 als benannter Leser. |
| `docs/reference/api_contract.md` | MODIFY | **Pflicht, sonst CI rot** — siehe Risiken |
| `docs/adr/0077-*.md` + `docs/adr/README.md` | CREATE/MODIFY | ADR-0077 (Fortschreibung ADR-0046), Index-Eintrag (`tests/test_adr_index_drift.py`) |
| `tests/…` Roundtrip + `internal/store/…_test.go` | CREATE/MODIFY | Roundtrip-Nachweis beide `kind`-Werte, zwei Nutzer |

## Scope Assessment (S1)

- **Dateien:** 7 produktiv + 2 Doku + Tests
- **Geschaetzte LoC:** **+40 bis +90** produktiv (Doku/`*.md`/Tests zaehlen nicht) —
  Baseline: die strukturell gleiche Scheibe #1461 S3b-2a brauchte fuer den reinen
  Persistenz-Teil 58 Zeilen. Marge zum 250er-Limit >150 Zeilen.
- **Risk Level:** **NIEDRIG** — additiv, `omitempty`, kein Leser, keine Migration,
  keine UI, kein Netz. Die zwei Risiken mit Zaehnen sind der Go-Typ und die Doku-Pflicht,
  beide unten mit Gegenmassnahme.

## Technical Approach (S1)

1. Go-Struct-Feld auf **beiden** Entitaeten, Typ `map[string]interface{}`, `omitempty`.
2. Trip-PUT-DTO ergaenzen **und** die `mergeConfigMap`-Zeile setzen — beides zusammen,
   sonst faellt das Feld beim Trip-PUT still raus oder ersetzt blind.
3. Python: `KNOWN_TOP_LEVEL` + Dataclass-Feld + `_trip_to_dict`-Rueckschreiben (alle drei).
4. `api_contract.md` um das JSON-Tag ergaenzen (CI-Pflicht).
5. ADR-0077 als Fortschreibung von ADR-0046: Ablageort, Typ, Schluesselmenge,
   „kein Eintrag = erbt den Abo-Satz", Reihenfolge S2-vor-S3.
6. Roundtrip-Tests: Feld ueberlebt Speichern/Laden auf beiden `kind`-Werten, mit **zwei
   verschiedenen Nutzern**; ein Teil-PUT ohne das Feld loescht es nicht; ein Teil-PUT mit
   **einer** Metrik loescht die anderen Metriken nicht.

   🔴 **Die Teil-PUT-Tests MUESSEN auf der HTTP-Schicht laufen** (`UpdateTripHandler`),
   **nicht** gegen `store.SaveTrip`. `mergeConfigMap` sitzt in `internal/handler` — der
   Store marshalt das Struct transparent durch (`internal/store/trip.go:272`
   `json.MarshalIndent(trip, …)`, `:197`/`:141` `json.Unmarshal`) und sieht den Merge
   nie. Ein Store-Roundtrip-Test bliebe unter der Mutation „Blind-Replace statt
   `mergeConfigMap`" **gruen** — die Gegenmassnahme zu Risiko A waere dann Theater.
   Fehlerklasse: „Mutation im falschen Kontext ist strukturell unbeobachtbar" (#2276 S6b).

   **Vergleichsseite ehrlich buchen:** Dort gibt es keinen eigenen Handler-Code zu
   mutieren — der Merge ist vorbestehendes generisches Verhalten. Der
   Compare-Teil-PUT-Test charakterisiert Bestand und bewacht das **Struct-Feld** (ohne
   Feld verwirft der Unmarshal den Key), nicht einen Merge von uns. In der Spec als
   solcher kennzeichnen, damit der Adversary ihn nicht als unbewachte AC bucht.

**Mutations-Gegenprobe (Pflicht in `/50-implement`):** Mindestens — `omitempty` entfernen ·
`mergeConfigMap` durch Blind-Replace ersetzen (muss rot werden, sonst ist der
Teil-PUT-Test wertlos) · `KNOWN_TOP_LEVEL`-Eintrag entfernen · `_trip_to_dict`-Zeile
entfernen · Feld aus dem Trip-DTO entfernen.

## Dependencies & Reihenfolge

- **#2293** (`ComparePreset.AlertChannels` nachbauen, Schicht 2 am Vergleich) definiert
  dieselbe Flaeche. **Tech-Lead-Entscheidung: #1895-F2 legt die Zielform fest, #2293
  wird danach dagegen neu geschnitten.** Beide Felder koennen nebeneinander existieren —
  #2293 ist Schicht 2 (je Abo), dieses Feld ist die neue Schicht (je Metrik).
  **Notiz an #2293 und #2212 geht raus, sobald die Spec steht.**
- **#1230** ist der Epic-Rahmen; #1895-F2 ist dessen letzte offene Substanz.
- **R7 Parallelsitzung #2276** (`AlarmeTab`/`CompareTabs`): fuer S1 gegenstandslos —
  S1 fasst keine `.svelte`-Datei an. Wird erst ab S3 relevant.

## Tests, die S1 rot faerbt

Nachgemessen — das Kontextdokument oben ueberzeichnet diesen Punkt:

- **`tests/test_api_contract_drift.py:55`** (`test_every_model_json_tag_is_documented`):
  scannt **jedes** `json:"…"`-Tag in `internal/model/trip.go` und `compare_preset.go`
  und verlangt eine Erwaehnung in `docs/reference/api_contract.md`. **Wird rot, wenn die
  Doku-Zeile fehlt.** Das ist der einzige sicher rote Bestandstest.
- **Nicht rot:** `tests/test_briefing_route_cutover.py:275` und
  `internal/store/store_trip_briefings_test.go:221` pruefen nur, dass **benannte** Felder
  ueberleben — keine Assertion auf eine geschlossene Feldmenge. Ein additives Feld bricht
  sie nicht.
- Die im Kontext oben gelisteten ~15 Tests an `rule.channels` und ~25 an der
  Override-Aufloesung betreffen **S2/S4**, nicht S1 — S1 aendert keine Signatur.

## Risks & Considerations (S1)

| # | Risiko | Gegenmassnahme |
|---|---|---|
| **A** | **Falscher Go-Typ** ⇒ atomarer Ersatz statt Metrik-Merge. Bricht erst in S3 sichtbar, dann als Datenverlust. | Typ `map[string]interface{}` in der Spec als AC festschreiben; Mutations-Gegenprobe „Blind-Replace" muss rot werden. |
| **B** | **Doku-Pflicht vergessen** ⇒ CI rot. | `api_contract.md` als fixer Bestandteil desselben PRs, nicht als Nacharbeit. |
| **C** | **Python halb verdrahtet** (`KNOWN_TOP_LEVEL` ohne Dataclass-Feld) ⇒ Alt-Werte gehen verloren (`loader.py:657-658`). | Alle drei Stellen zusammen; Roundtrip-Test mit vorbefuelltem Bestandswert. |
| **D** | **Scope-Creep** — Schluessel-Validierung in Go, Frontend-Typen, vorgezogene Migration. | Definition of Done: „Feld + Persistenz + Roundtrip + Doku + ADR. Kein Frontend, keine Validierung, keine Migration." |
| **E** | **Mandantentrennung** (#1460, Multi-User-Pflicht). | Roundtrip-Test mit **zwei verschiedenen Nutzern**. |
| **F** | Hook `data_schema_backup.py` feuert bei Edits an `models.py`/`trip.py`/`loader.py`/`internal/model/*.go` | erwartet, kein Handlungsbedarf — Snapshot nach `.backups/` |

## Open Questions

Keine. Alle neun Designfragen sind oben entschieden; sie waren Tech-Lead-Entscheidungen,
keine PO-Fragen. Freigabepflichtig sind allein die ACs der Spec (Phase 3).

## Rahmung fuer das PO-Briefing (Phase 3)

**S1 aendert fuer den Nutzer nichts — und das ist der Punkt, nicht ein Makel.** Der PO
hat #1895 geparkt, weil von Frage 2 „nichts sichtbar" ist; S1 ist noch unsichtbarer als
Frage 2 im Ganzen, naemlich reine Verrohrung. Das Briefing darf keine nutzersichtbare
Aenderung suggerieren.

Was S1 leistet, in einem Satz: **Es legt die Zielform des Feldes fest — Ablageort, Typ
und Merge-Verhalten —, damit S2 und S3 darauf bauen koennen, ohne beim Speichern Kanaele
zu verlieren.** Wirksam wird die Sache erst mit S2, sichtbar erst mit S3 (Kanalspalte
neben der Empfindlichkeitsstufe).

⚠️ Das PO-Briefing-Gate ist SHA256-gebunden an den Spec-INHALT — erst den Spec-Text
festzurren, dann das Briefing anfordern. Jede spaetere Spec-Aenderung entwertet es.

## Folge-Issues (anzulegen beim Abschluss dieses Workflows)

- **S2** — Aufloesung auf Metrik-Granularitaet + Migration `alert_rules[].channels`
- **S3** — Editor-Spalte (haengt an S2, darf nie davor)
- **S4** — Rueckbau `alert_rules[].channels`, `AlertRulesEditor`, toter `TripEditView`
  (verifiziert 2026-09-22: `TripEditView.svelte` hat **keinen** Laufzeit-Importeur unter
  `frontend/src`, nur Dateiinhalt-Tests — der im Kontext offene Punkt ist damit geklaert)
- **Nebenbefund → #1199:** `trip_alert.py:438,442` behauptet im Kommentar noch,
  `alert_rules` sei Source-of-Truth fuer den Detektor — seit #946 falsch.
