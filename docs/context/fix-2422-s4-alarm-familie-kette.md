# Context: Fix #2422 (Scheibe S4) — Kette Alarm-Familie

## Request Summary

Issue #2422 verlangt, alle Testlücken zwischen Konfiguration und Auslieferung zu finden. S1–S3
haben das für Trip-Briefings geprüft (Metrik-Auswahl, Editor-Anzeige, Kanal an/aus, Slot-Schalter,
`email_format`, `sms_threshold`-Pillen). Scheibe S4 prüft dieselbe Frage für die **Alarm-Familie**:
Schwellen (`alert_channel_thresholds`), Radar-/Regen-Alarme und amtliche Warnungen — vom
gespeicherten JSON bis zur Auslieferung über alle vier Kanäle (E-Mail, Telegram, SMS,
Premium-SMS).

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/trip.py:209-231` | Datenmodell: `alert_channels`, `alert_channel_thresholds`, `alert_metric_channels`, `official_warnings`, `official_alert_triggers_enabled`, `official_alerts_enabled` |
| `src/app/models.py:1275` | `AlertRule.channels` — Regel-Override |
| `src/app/models.py:1347` | `ComparePreset.radar_alert_enabled` — Asymmetrie zum Trip (kein eigenes Feld dort) |
| `internal/model/trip.go:145-232` | Go-Pendants (`AlertChannelThresholdsConfig`, `AlertChannelsConfig`, `OfficialWarnings`) |
| `src/app/loader.py:273-299,366,636-727,808-830,1702-1731` | Lesen/Schreiben + Migrationslogik (`_migrate_legacy_alert_rules`, `_migrate_rule_channels_to_metric_channels`) — geladener Trip ≠ rohes JSON |
| `frontend/.../AlarmeTab.svelte:112-343` | Editor: Schwellen-Pillen, amtliche Warnungen, Radar-Toggle |
| `frontend/.../alarme-tab/{alertChannelState,alarmeDeliveryPayload,tripChannelReconstruction}.ts` | Speicher-/Hydrations-Pfad Trip |
| `frontend/.../compare/alarmePropsAus.ts`, `shared/alarmeVergleichSpeicherung.ts` | Speicherpfad Vergleich (Kollisionsrisiko mit #2293) |
| `src/services/alert_channels.py:29-213` | **Die eine geteilte Kanal-Auflösung** für Trip und Vergleich (`resolve_alert_channels`, `effective_alert_channels`) |
| `src/services/alert_channel_threshold.py:20-35` | `split_by_threshold()` — reine Funktion, wendet die Schwelle an |
| `src/services/trip_alert.py:1588-1628,2261,2528,2577-2587,2799,2882-2914` | Radar-/Abweichungs-/amtlicher Trigger-Einstieg, Schwellen-Anwendung, Enable-Schalter-Vorrang |
| `src/services/compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py` | Compare-Pendants — nutzen denselben `alert_channels.py`-Kern |
| `src/output/renderers/alert/{render,project,model,official_alerts}.py` | Eigene Alarm-Renderer, getrennt von Trip-Briefing-Renderern |
| `src/services/notification_service.py:1058,1364,1672-1946` | **Drei getrennte** Vier-Kanal-Versandpfade: `send_official_alert`, `send_multi_location_official_alert`, `_dispatch_alert_message` (Radar+Abweichung) |
| `src/services/official_alerts/*.py` | Quellen-Registry, Fetch/Verarbeitung amtlicher Warnungen |
| `tests/helpers/transport_mitschrift.py:47-108` | Wiederverwendbare Mitschrift-Infrastruktur aus S1–S3 — patcht exakt an der Stelle, an der auch Alarme versenden |
| `tests/helpers/einstellung_auslieferung_orakel.py`, `erwartungsdateien_erzeugen.py` | Ausnahme-Register- und Golden-Muster aus S1–S3 |
| `tests/helpers/alarm_pruefstrecke.py` (#2050) | Baut Trip **im Speicher**, nicht aus JSON — schließt die S4-Lücke nicht |
| `internal/handler/trip_alert_channel_thresholds_test.go`, `compare_preset_alert_channel_thresholds_test.go` | Go-Seite Editor→gespeichert bereits gut getestet |
| `frontend/.../alarme-tab/alertChannelThresholds.test.ts` | Frontend-Seite bereits getestet (AC-10) |

## Existing Patterns

- **Geteilte Kanal-Auflösung, aber getrennte Dispatch-Pfade:** `resolve_alert_channels()` ist der
  eine Auflösungskern (Override → Regel/Metrik-Union → Tarif-Gate). Danach laufen drei
  unterschiedliche Versandpfade (`_dispatch_alert_message` für Radar+Abweichung, zwei eigene
  Methoden für amtliche Warnungen Trip/Compare) — keine einheitliche vierte Funktion.
- **Schwelle wirkt NACH der Kanalauflösung, VOR dem Versand:** `split_by_threshold()` wird an
  jeder der drei Aufrufstellen separat aufgerufen (`trip_alert.py:2261/2528/2799`). Eine
  Ketten-Prüfung muss alle drei Stellen einzeln abdecken.
- **`metrics`/`metric_channel_sets` gilt strukturell NUR beim Abweichungsalarm** — Radar und
  amtliche Warnungen übergeben nie Metrik-Kanäle. Eine S4-Erwartung „Kanal je Metrik" für Radar/
  amtlich wäre ein Fehlschluss, kein Defekt.
- **Bewusste Nicht-Parität dokumentiert im Code:** der eingebettete amtliche Zusatzblock einer
  gebündelten Abweichungs-Alarm-Mail fehlt in der SMS bewusst (`notification_service.py:1706-1708`).
  Muss ins Ausnahme-Register, sonst erzeugt die Vier-Kanal-Matrix eine falsche rote Zelle.
- **S1–S3-Testmuster wiederverwendbar:** Mitschrift-Helper, Ausnahme-Register, Golden-Fixture-
  Erzeugung sind kanalunabhängig und für Alarme ohne Änderung nutzbar.

## Dependencies

- **Upstream:** `app.loader` (Lesepfad + Migrationslogik), `resolve_alert_channels()` als
  gemeinsamer Kern für Trip und Vergleich (ADR-0021, ADR-0023).
- **Downstream:** Drei getrennte Notification-Dispatch-Pfade, eigene Alarm-Renderer (kanal- und
  typspezifisch), Transport-Layer (`output/channels/*.py`, geteilt mit Trip-Briefings).

## Existing Specs

- `docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md` — S1, definiert S4 als
  „Kette Alarm-Familie (Schwellen, Radar/Regen, amtliche Warnungen) JSON → alle vier Kanäle" (L1).
- `docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md` — S2a, nennt S4 als „Kette
  Alarm-Familie … außerhalb".
- `docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md` — S3, D16: „Nicht mit `sms_threshold`
  (Erwähnungsschwelle) verwechseln".
- `docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md` (Draft, andere Sitzung, Worktree
  `ticket-empfehlung-2345`) — reine Kanal-an/aus-Parität für den Vergleich, **nicht** Schwellen.
  Nutzt denselben `alert_channels.py`-Kern lesend, ändert ihn nicht. Datei-Überschneidungsrisiko
  bei `AlarmeTab.svelte`, `compare/alarmePropsAus.ts`, `shared/alarmeVergleichSpeicherung.ts`,
  `compare/compareEditorSave.ts`, falls S4 den Compare-Alarmpfad mitprüft.
- `docs/specs/modules/alarm_pruefstrecke.md` (#2050) — baut Trips im Speicher; ergänzt S4, ersetzt
  es nicht.
- `docs/specs/modules/feat_1701_alarm_premium_sms.md` — Premium-SMS als vierter Alarm-Kanal,
  `blocked_channels`/`blocked_reason_codes`.
- ADRs: 0009, 0010, 0011, 0013, 0016, 0019, **0021** (geteilte `DeviationAlertEngine`), **0023**
  (`BriefingSubscription`-`kind`-Diskriminator), 0033, 0039, 0040, 0041, 0043, **0046** (Kanal-
  Schwelle regelt WIE, nicht OB), 0047, 0048, **0049** (Premium-SMS als vierter Kanal), 0052,
  0056, 0057, 0064, 0074, **0077** (`alert_metric_channels`).

## Risks & Considerations

- **Scope-Frage Compare-Alarme:** ungeklärt, ob `compare_alert.py`/`compare_official_alert.py`/
  `compare_radar_alert.py` in S4 mitgeprüft werden (Kollisionsrisiko mit der laufenden #2293-
  Sitzung) oder komplett außerhalb bleiben (dann evtl. Teil von S5 oder eigene Scheibe). Wird in
  `/20-analyse` geklärt, keine eigenmächtige Entscheidung.
- **Drei getrennte Dispatch-Pfade statt einem** bedeutet: eine einzige Vier-Kanal-Matrix reicht
  nicht — mindestens drei separate Ketten (Radar, Abweichung, amtlich) mit je vier Kanälen.
- **Bekannte Code-Fehlreferenz im S1-Kontext-Dokument** (`fix-2422-konfig-auslieferung-testluecken.md:159`
  nennt `trip_report_scheduler.py`/`notification_service.py:619/642/664` — das ist der
  Briefing-, nicht der Alarm-Pfad). Für S4 gelten stattdessen `notification_service.py:1058`,
  `:1364`, `:1672`.
- **Migrationslogik beim Laden** (`_migrate_legacy_alert_rules`,
  `_migrate_rule_channels_to_metric_channels`) bedeutet: ein im Speicher gebauter Trip
  unterscheidet sich strukturell von einem geladenen. Die S4-Golden-Fixtures müssen echte
  JSON-Dateien durch `app.loader` laufen lassen (wie S1–S3), nicht `Trip(...)` direkt
  konstruieren — sonst bleibt die eigentliche Lücke (wie bei `alarm_pruefstrecke.py`) unentdeckt.
- **Asymmetrie Trip vs. Compare bei Radar:** `ComparePreset.radar_alert_enabled` existiert, ein
  Trip-Pendant nicht (Radar-Gate dort nur implizit über Segmentwahl/Nowcast/Throttle) —
  dokumentationswürdig, kein Bug per se.
- **Drei überlappende Enable-Schalter für amtliche Warnungen** (`official_alerts_enabled`,
  `official_alert_triggers_enabled` [veraltet], `official_warnings.enabled` [aktuell, hat
  Vorrang]) — Golden-Fixtures müssen den aktuellen Schalter nutzen, Altbestand-Fall mit nur dem
  Legacy-Feld separat prüfen.
- **Bereits erledigt, nicht wieder aufmachen:** Alarm-Vorlauf-Sperre `trip_briefing_due_at` (D4,
  S3, AC-5).

## Analysis

### Type
Feature (Testabdeckungs-Ticket, analog S1–S3) — mit mindestens einem echten Produktbug-Kandidaten
(siehe unten), kein reines Test-Hinzufügen.

### Scope-Entscheidung: NUR Trip-Alarm-Pfad, Compare-Alarme als benannter Folgepunkt

Geprüft gegen den Ur-Spec `docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md`: L1
(„Alarm-Familie … Scheibe S4") und L4 („Ortsvergleich `channel_active_metrics` + Kanalwahl …
Scheibe S5") sind **beide** ohne explizite Trip/Compare-Zuordnung formuliert — L4/S5 behandelt
Ortsvergleichs-**Metrikauswahl**, nicht Alarme. Compare-Alarme (`compare_alert.py`,
`compare_official_alert.py`, `compare_radar_alert.py`) sind damit im Ur-Schnitt **keiner** Scheibe
fest zugeordnet — die Kollisionsargumentation mit #2293 allein trägt die Ausklammerung nicht (kein
Draft-Spec in `origin/main`, keine aktive Session dafür).

Trotzdem: S4 bleibt bewusst auf den **Trip-Pfad** beschränkt, aus einem **inhaltlichen** Grund —
`ComparePreset.alert_channels` hat laut #2293 aktuell kein Go-Feld/keine Migration (nur
Roh-Dict-Zugriff); eine Golden-Fixture-Kette für die Schwellen-Auflösung am Compare-Datenmodell
würde auf einem Datenmodell aufsetzen, das #2293 gerade erst herstellt. `radar_alert_enabled` und
`official_warnings` existieren am `ComparePreset` dagegen schon stabil — dafür fehlt also
tatsächlich unabhängig von #2293 eine Testkette.

**Empfehlung:** Compare-Alarm-Kette (Radar + amtliche Warnungen, ohne die Schwellen-Override-Frage)
als eigenen, benannten Folgepunkt vermerken (Sammel-Issue #1199 oder eigenes Ticket nach #2293),
nicht stillschweigend fallen lassen.

### Korrekturen gegenüber dem ursprünglichen Kontext-Dokument

- **Nur 2 Dispatch-Funktionen im Trip-Pfad, nicht 3:** `_dispatch_alert_message` bedient sowohl
  Radar- als auch Abweichungsalarm gemeinsam (`trip_alert.py:2261` bzw. `:2528` rufen
  `split_by_threshold()` auf, münden aber in denselben Dispatch); `send_official_alert`
  (`notification_service.py:1058`) ist der zweite, eigenständige Pfad.
  `send_multi_location_official_alert` (`:1364`) wird ausschließlich von
  `compare_official_alert.py:282` aufgerufen — außerhalb des S4-Scope. Die Matrix-Achse ist
  **Trigger × Kanal** (3 Trigger: Radar/Abweichung/amtlich), nicht „3 Dispatch-Pfade".
- **`tests/helpers/alarm_pruefstrecke.py` (#2050) ist nutzbarer als zunächst angenommen:**
  `lauf()` nimmt ein beliebiges `Trip`-Objekt entgegen (Zeile 164) — wird ein per
  `app.loader.load_trip(...)` geladener Trip übergeben, schließt das die Migrations-Lücke für
  Radar und Abweichung. **Echte verbleibende Lücke:** der `official`-Zweig ruft dort die private
  `svc._send_official_alert_only(...)` auf (Zeile 202) und **umgeht** damit den öffentlichen
  Einstiegspunkt `check_official_alert_triggers()` (`trip_alert.py:2554`) — genau die Stelle mit
  der Drei-Schalter-Vorrangprüfung, die S4 testen soll. S4 muss diesen Pfad über den echten
  Einstiegspunkt führen, sonst bleibt die Lücke bestehen wie bei #2050 selbst.
- **Testnaht:** `transport_mitschrift.py` (S1–S3-Pattern, patcht direkt an
  `EmailOutput`/`SMSOutput`/`PremiumSmsOutput`/`TelegramOutput`) statt `alarm_pruefstrecke`s
  eigenem `mail_sink`/HTTP-Stub-Ansatz verwenden — sonst laufen zwei Testphilosophien dauerhaft
  parallel.
- **Kein Ausnahme-Register für die SMS-Nichtparität amtlicher Zusatzblock:** Für die dokumentierte
  Lücke (`notification_service.py:1706-1708`, Issue #1088) existiert **keine ADR** (geprüft:
  `docs/adr/` hat keinen Treffer außer einem unrelated Zeilenverweis). Eine unbelegte
  Code-Kommentar-Entscheidung ist keine ratifizierte Architekturentscheidung — nach der aus S2
  gewonnenen Regel „bekannte Abweichung wird im selben Ticket gefixt, nicht befristet ins
  Ausnahme-Register geschoben" (vgl. #2422 S2) ist das ein **Fixkandidat**, kein Registereintrag.
  Ebenso stützt die PO-Korrektur vom 2026-09-05 („jeder Kanal muss jede Frage beantworten können",
  Epic #2133) die Fix-Richtung.
- **LoC-Politik korrigiert:** Tests zählen sehr wohl gegen ein Budget (Test-Default 500 LoC,
  getrennt vom Produktiv-Default 250 — `docs/reference/gates_und_ratschen.md`). Bei Überschreiten
  gilt laut CLAUDE.md `workflow.py set-field loc_limit_override <N>` — **keine** Rückfrage beim PO
  nötig, und **kein** Grund, den Scope eigenmächtig zu verengen (`feedback_red_umfang_nie_
  eigenmaechtig_auf_eine_scheibe_verengen`). S4 bleibt daher **ein** Workflow/eine Spec, analog
  S1–S3, nicht in S4a/b/c aufgeteilt — spart dem PO zusätzliche Freigaberunden.

### Gefundener Bug-Kandidat (bereits in der Analyse, nicht erst im Test)

**`trip_alert.py:895-911`** (Vorab-Filter im Sammellauf, VOR `check_official_alert_triggers()`):

```python
official_trigger_possible = trip.official_alert_triggers_enabled is not False
if (not has_active_rules and (not trip.report_config or not trip.report_config.alert_on_changes)
        and not official_trigger_possible):
    continue
```

Dieser Vorab-Filter prüft **nur** das veraltete Feld `official_alert_triggers_enabled` — **nicht**
`official_warnings.enabled`, obwohl Letzteres laut `trip_alert.py:2577-2587` eigentlich Vorrang
hat („Issue #1258 löst das Legacy-Feld ab"). Das Frontend (`AlarmeTab.svelte`,
`alarmeDeliveryPayload.ts:107`) schreibt beim Speichern **nur noch** `official_warnings.enabled`,
nie mehr `official_alert_triggers_enabled` — das Legacy-Feld bleibt in gespeicherten Trips auf
seinem letzten historischen Wert stehen (kein Migrationsschritt setzt es zurück, geprüft in
`loader.py:279/669/714/1706-1707`).

**Konkretes Szenario:** Ein Trip, dessen Legacy-Feld irgendwann auf `false` stand (z. B. vor
#1258 im Editor ausgeschaltet), bei dem der Nutzer amtliche Warnungen über die **aktuelle**
Alarme-Tab-Oberfläche wieder **einschaltet** (`official_warnings.enabled: true`) — und sonst
keine aktive Wetter-Delta-Regel hat: `official_trigger_possible` wird `False`, der Trip wird
bereits in Zeile 906–911 komplett übersprungen, **bevor** `check_official_alert_triggers()` und
damit die korrekte Vorrangregel überhaupt erreicht wird. Der Nutzer sieht im Editor „amtliche
Warnungen: an", bekommt aber nie eine amtliche Alarm-Nachricht — exakt das Fehlerbild aus der
Original-Meldung von #2422 (Editor zeigt X, Auslieferung macht Y).

→ **Muss in der Spec als AC formuliert werden** (Zeile 905 auch auf `official_warnings.enabled`
prüfen, spiegelbildlich zu 2577–2587), nicht nur als Testfall.

### Einstellungs-Inventar Trip-Alarme-Tab (Grundlage für Golden-Fixtures)

Aus `AlarmeTab.svelte` + `alarmeDeliveryPayload.ts` extrahiert — Spalte „Scope" legt fest, was S4
abdeckt:

| JSON-Feld | Schreiber (Frontend) | Konsument (Backend) | Scope S4 |
|---|---|---|---|
| `alert_channels` (email/telegram/sms/premium_sms) | `alarmeDeliveryPayload.ts:111-116`, immer alle 4 explizit | `resolve_alert_channels()` (`alert_channels.py`) | ✅ in Scope |
| `alert_channel_thresholds` (je Kanal) | `alarmeDeliveryPayload.ts:122-129`, nur wenn bekannt | `split_by_threshold()` (3 Aufrufstellen `trip_alert.py:2261/2528/2799`) | ✅ in Scope |
| `official_warnings.enabled` | `alarmeDeliveryPayload.ts:107` | `trip_alert.py:2577-2587` (Vorrang) + `:895-911` (Vorab-Filter, s. Bug-Kandidat oben) | ✅ in Scope |
| `official_alert_triggers_enabled` (Legacy) | nicht mehr geschrieben, nur Alt-Daten | `trip_alert.py:905`, `:2585` (Fallback) | ✅ in Scope (als Alt-Daten-Fall + Bug-Kandidat) |
| `alert_cooldown_minutes` | `AlarmeTab.svelte:350`, `alarmeDeliveryPayload.ts:108` | `trip_alert.py` Cooldown-Gate (Issue #181, ca. 545-547/1296-1381/1677-1692/2714) | ✅ in Scope — bisher im Kontextdoc nicht erwähnt, gehört strukturell dazu |
| `alert_quiet_from` / `alert_quiet_to` | `AlarmeTab.svelte:351-352`, `alarmeDeliveryPayload.ts:109-110` | dieselbe Cooldown/Quiet-Gate-Stelle | ✅ in Scope, aus demselben Grund |
| `alert_rules` (Wetter-Delta-Regeln) | `WeatherMetricsTab`/`AlertPreviewCard`, nicht Alarme-Tab selbst | `trip_alert.py:2528` (Schwelle), Regel-Auswertung vorgelagert | ✅ in Scope (Abweichungsalarm-Auslöser) |
| `official_alerts_enabled` | `WeatherMetricsTab.svelte` (Inhalt-Bereich, NICHT Alarme-Tab, D2/#1301) | `trip_report_scheduler.py:1416`, `comparison_engine.py:320` — steuert Fetch der amtlichen Warn-**Inhalte** für Trip-Briefings | ❌ außerhalb — anderer Konsument (Briefing-Inhalt, nicht Alarm-Trigger), gehört fachlich zu S1-Territorium |
| `radar_alert_enabled` | nur `ComparePreset` (Compare-Editor), kein Trip-Gegenstück in der UI | Radar-Gate implizit über Segmentwahl/Nowcast/Throttle | ❌ außerhalb Trip — dokumentationswürdige Asymmetrie, kein Bug |

### Risiken

- Golden-Fixtures **müssen** durch `app.loader` laufen (nicht `Trip(...)` im Speicher), sonst
  wiederholt S4 den #2050-Fehler.
- Drei sich überlagernde Enable-Zustände (`official_warnings.enabled` > `official_alert_triggers_
  enabled` [Legacy] > Vorab-Filter-Bug) brauchen mindestens 3 gezielte Golden-Fälle, nicht nur
  „ein" amtlicher Warnungs-Fall.
- Cooldown/Quiet-Hours (`alert_cooldown_minutes`, `alert_quiet_from/to`) waren im ursprünglichen
  Kontext-Dokument nicht erwähnt — ohne explizite Aufnahme wäre das eine vierte, stille Lücke
  entstanden.
- SMS-Nichtparität amtlicher Zusatzblock: Fix statt Registereintrag ändert den Scope leicht
  Richtung Produktivcode (`notification_service.py`, ggf. `render_alert_sms`) — kleine, aber
  echte Codeänderung, nicht nur Testarbeit.

### Scope Assessment
- Betroffene Dateien (Test + ggf. kleine Produktiv-Fixes): geschätzt 8–12
  (`trip_alert.py` [Fix Zeile 905], `notification_service.py`/Renderer [SMS-Parität-Fix], 3 neue
  Testdateien Radar/Abweichung/amtlich, 1-2 neue Golden-Fixture-JSONs, Erweiterung
  `einstellung_auslieferung_orakel.py`/Fixture-Helfer, ggf. Erweiterung `alarm_pruefstrecke.py`
  um Loader-Adapter + öffentlichen Official-Einstiegspunkt).
- Geschätzte LoC: deutlich über dem Test-Default 500 → `loc_limit_override` einplanen (siehe oben,
  keine Rückfrage nötig).
- Risiko: **Mittel** — enthält echten Produktivcode-Fix (Alarm-Trigger-Logik), nicht nur Tests.

### Technical Approach
1. `alarm_pruefstrecke.py` um einen Loader-Adapter (Trip aus echter JSON-Datei) und einen vierten
   Lauf-Modus erweitern, der `check_official_alert_triggers()` (öffentlich) statt
   `_send_official_alert_only()` (privat) aufruft.
2. Testnaht auf `transport_mitschrift.py` vereinheitlichen.
3. Reihenfolge: Abweichungsalarm zuerst (reichhaltigster Pfad, Migrationslogik,
   `alert_metric_channels`, Schwelle) → Radar (teilt sich `_dispatch_alert_message`) → amtliche
   Warnungen (eigener Pfad, Drei-Zustand-Vorrang, enthält den Bug-Fix).
4. Fix `trip_alert.py:895-911`: Vorab-Filter muss `official_warnings.enabled` genauso
   berücksichtigen wie `check_official_alert_triggers()` es tut.
5. SMS-Parität amtlicher Zusatzblock (#1088): kleiner Fix statt Ausnahme-Registereintrag —
   Umfang (kurzer Hinweistext vs. vollständiger Block) ist Spec-Entscheidung in `/30-write-spec`.

### Dependencies
Upstream: `app.loader` (Migration), `resolve_alert_channels()`. Downstream: 2 Dispatch-Funktionen
(`_dispatch_alert_message`, `send_official_alert`), Alarm-Renderer, Transport-Layer (geteilt mit
Trip-Briefings, S1-S3-Infrastruktur wiederverwendbar).

### Open Questions
- [ ] SMS-Parität amtlicher Zusatzblock (#1088): vollständiger Block oder Kurz-Hinweis? →
  Spec-Entscheidung, keine PO-Rückfrage nötig (Produktentscheidung „jeder Kanal beantwortet jede
  Frage" ist bereits gesetzt, nur die Form ist offen).
- [ ] Compare-Alarm-Kette (Radar + amtliche Warnungen) als Folge-Backlog-Eintrag in #1199
  vermerken — Aufgabe für `/30-write-spec` oder direkt danach.
