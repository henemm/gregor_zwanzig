---
entity_id: fix_2422_s3_kanal_an_aus_kette
type: bugfix
created: 2026-09-28
updated: 2026-09-28
status: draft
version: "1.0"
tags: [testing, invariante, versand, kanaele, schedule, orakel, fix]
workflow: fix-2422-s3-kanal-an-aus-kette
---

# Fix #2422 (Scheibe S3): Kette Kanal an/aus · Versandzeiten · Einzel-Slot-Schalter · email_format · sms_threshold — Tests + Fix

## Approval

- [ ] Approved

## Purpose

Issue #2422 lautet „Konfiguration und Auslieferung nicht getestet!". Scheibe S1 hat geprüft, dass
das **gespeicherte** Trip-JSON so ausgeliefert wird, wie es dort steht (Kaskade Metrik × Kanal).
Scheibe S2a hat geprüft, dass der Editor genau diesen Stand anzeigt und speichert. **Scheibe S3
schließt die Strecke davor und daneben:** die Schalter, die entscheiden, **OB, WANN und in welcher
FORM** überhaupt eine Nachricht hinausgeht — vom gespeicherten Trip-JSON bis zur tatsächlich
ausgelieferten Nachricht. Konkret: Kanal an/aus (E-Mail, Telegram, SMS, Premium-SMS), Versandzeiten,
Gesamtschalter/Pause, die beiden Einzel-Schalter „Morgen aktiv"/„Abend aktiv", `email_format`
(voll/kompakt), `sms_threshold`, und der Vorrang `channel_layouts_per_report` vor `channel_layouts`.

Der Bestand prüfte davon fast nichts bis zur Auslieferung: die S1/S2a-Matrix baut ihren Sendeauftrag
direkt aus den `send_*`-Feldern und **umgeht damit** die Kanal-Auflösung, die Render-Optionen und den
Scheduler. Geprüft war nur „alle vier Kanäle an" (`test_kanaltreue_adhoc_antwort.py`).

**Hauptbefund (am Code bestätigt, produktiver Fix in dieser Scheibe):** Die Checkboxen „Aktiv" bei
Morgen-Briefing und Abend-Briefing im Versand-Reiter schreiben `report_config.morning_enabled` und
`report_config.evening_enabled`. Python kennt diese beiden Felder nicht; der Scheduler prüft nur den
Gesamtschalter `enabled` — für beide Slots gleich. Wer „Abend aktiv" abhakt, sieht in Editor und
Trip-Übersicht „Abend aus", bekommt aber weiterhin das Abend-Briefing. Der Ortsvergleich macht es
richtig (`compare_slot_scheduler.py:168-170`), der Trip nicht. Das ist nutzersichtbares Fehlverhalten
(Triage-Kriterium a) und genau die Beschwerde, um die es in #2422 geht.

**Entscheid „Tests + Fix in einem Schnitt" (PO-Linie aus S2a):** Der PO hat in S2a ausdrücklich
verweigert, bekannte Abweichungen befristet zu tolerieren („Warum soll ich eine befristete Abweichung
OK heißen?"). Deshalb legt diese Spec **keinen** Ausnahme-Register-Eintrag an. Jede Verdachtsstelle
wurde per Code-Lektüre zu einem definitiven Befund gebracht (Abschnitt „Verdachtsstellen — Verdikte"):
bestätigte Abweichungen sind Fix-ACs, als korrekt erwiesene Stellen werden reine Test-ACs (Zusicherung
bewachen), eine nicht erreichbare Stelle wird als Nebenbefund benannt.

**Ausdrücklich gewollte Verhaltensänderungen (kein Regressions-Befund):**
1. Trips, bei denen im Editor „Morgen aktiv" oder „Abend aktiv" abgehakt wurde, bekommen dieses
   Briefing ab dem Deploy **nicht mehr** — genau so, wie es Editor und Trip-Übersicht schon zeigen.
   Wie viele Prod-Trips das betrifft, ist nicht messbar (Prod-Bestand unter `/var/lib/gregor` ist für
   den Entwicklungsbenutzer nicht lesbar). Trips ohne diese Schalter liefern unverändert aus.
2. In der E-Mail-Metriken-Übersicht (Pillen) gilt die im Editor eingestellte SMS-Erwähnungsschwelle
   künftig auch dann, wenn die E-Mail ein eigenes Kanal-Layout hat (bisher fiel sie dort auf den
   Standardwert zurück, während die SMS die eingestellte Schwelle nutzte).
3. Trips **ohne** Per-Slot-Schlüssel und **ohne** Zeitfelder in `report_config` liefern unverändert
   mit den Standardzeiten 07:00/18:00 aus; Editor und Trip-Übersicht zeigen sie künftig als „aktiv"
   (bisher „aus", obwohl geliefert wurde).

**Alle vier Kanäle sind gleichrangig.** Kein Testbein behandelt einen Kanal als nachrangig: die
Kanal-Matrix (AC-8) prüft E-Mail, Telegram, SMS und Premium-SMS gleich streng, und der Alarm-Vorlauf
(AC-5) hängt nicht vom Kanal ab. Nur Daten, keine Handlungsempfehlungen.

## Verdachtsstellen — Verdikte (Code-Lektüre 2026-09-28, Fundstellen gegen `origin/main`-Stand des Worktrees)

| # | Verdachtsstelle | Verdikt | Fundstelle / Begründung | Behandlung |
|---|---|---|---|---|
| H | Einzel-Slot-Schalter wirken nicht | **bestätigt, Defekt** | Editor schreibt sie (`VersandTab.svelte:209-211`, `EditReportConfigSection.svelte:277-279`); Python: `TripReportConfig` (`models.py:1105ff`) und Loader (`loader.py:583-617`) ohne Feld; Scheduler prüft nur `rc.enabled` (`trip_report_scheduler.py:179` und `:933`); Ableitung flach aus `enabled` (`loader.py:648-649`, `internal/store/trip.go:92-95`) | **Fix** (AC-1 bis AC-7, AC-20, AC-21) |
| 1 | `channel_layouts_per_report` gewinnt in der Kaskade, Editor schreibt/zeigt es nie | **bestätigt als Mechanismus, kein Nutzer-Defekt der Kaskade** | Vorrang `per_report > per_channel > global` ist bewusst (`models.py:_cascade_source_for_channel`, #434); im Frontend liest nur `types.ts:295` und `cockpitHelpers568.ts:58` das Feld, **kein** Schreibweg (`git log -S` findet nur Typ + Lesestelle); Go lässt den Schlüssel beim flachen Merge von `display_config` stehen (`handler/trip.go:342-344`, `config_merge.go`). Das Orakel `erwartete_kaskade` kennt den Vorrang **nicht** (`einstellung_auslieferung_orakel.py:324ff`) — eine Orakel-Lücke, kein Produktfehler | **Test** (AC-17, AC-19) + Orakel-Erweiterung. Die Editor-Sichtbarkeit ist bereits als **B7 → Scheibe S6+** gebucht (`fix_2422_einstellung_gleich_auslieferung.md` Zeilen 44 und 64) — hier kein neues Issue. Bestand mit gesetztem Schlüssel: nicht messbar |
| 2a | `sms_threshold` wirkt in SMS/Kurzform/Premium nicht, wenn im Kanal-Layout gesetzt | **nicht bestätigt (korrekt nach Design)** | Die Schwelle ist bewusst eine **globale** Größe je Metrik (KL-4, `trip_report.py:325-331`, gelesen aus `_dc_uncollapsed.metrics` `:349-355`); der Editor schreibt sie nur in `display_config.metrics` (`weatherMetricsSavePayload.ts:59-69`), nie in ein Kanal-Layout; der Loader-Lesezugriff auf Layout-Einträge (`loader.py:985/1020`) ist ein toter Lesepfad | **Test** (AC-15) |
| 2b | `sms_threshold` wirkt in den **E-Mail-Pillen** nicht bei eigenem E-Mail-Layout | **bestätigt, Defekt** | `trip_report.py:133-139` kollabiert `dc` auf die E-Mail-Kanal-Liste (Layout-Einträge tragen `sms_threshold=None`), danach lesen `email/html.py:1465-1468`, `plain.py:203-206`, `compact.py:197-200` die Schwelle aus **diesem** `dc`. Ergebnis: Pillen nutzen `DEFAULTS` (`builder.py:129`: Regen 0,2 mm, Regenwahrscheinlichkeit 20 %) statt der eingestellten Werte (Golden A/B/C: 0,1 mm und 10 %) — SMS und Mail widersprechen sich | **Fix** (AC-16) |
| 3 | `syncSendFlags` schreibt still `send_*=false`, kennt `send_premium_sms` nicht | **nicht bestätigt (nicht erreichbar)** | Die Funktion wirkt nur, wenn `weatherChannels` übergeben wird (`EditReportConfigSection.svelte:298`); **kein** Aufrufer übergibt es (vier Einbindungen: `TripEditView.svelte:203`, `TripNewEditor.svelte:893/1160`, `BriefingsTab.svelte:40`, `WeatherMetricsTab.svelte:2013`; Grep `weatherChannels` außerhalb der Komponente ohne Treffer). Im Produkt ein reiner Durchlauf; die Premium-Lücke ist toter Code | Kein AC. **Nebenbefund**, Checkbox-Zeile in #1199 (Kriterium: kein nutzersichtbares Verhalten). Der Nutzerweg „gesetzter Kanal bleibt gesetzt" ist über AC-22 mitbewacht |
| 4 | Go kappt Minuten auf volle Stunde; zeigt der Editor die gekappte Zeit? | **nicht bestätigt** | Editor bietet nur volle Stunden an (`VTSchedulePlan.svelte:105-113`, `HOUR_OPTIONS`); Go kappt beim Schreiben (`handler/trip.go:354-356`, `slot_hour_normalization.go:71-80`) und heilt beim Lesen (`healTripSlotTimes`); Python nimmt `zeit.hour` (`trip_report_scheduler.py:131-140`) | **Test** (AC-13, AC-14, AC-19) |
| 5 | Default `send_email=True` bei fehlendem Feld vs. Editor | **nicht bestätigt (konsistent)** | Loader `loader.py:587` Default an; `_resolve_channel_flags` ohne `report_config` ⇒ nur E-Mail (`trip_report_scheduler.py:1793`); Editor `reportConfig?.send_email !== false` (`VersandTab.svelte:143`, `EditReportConfigSection.svelte:78`) — alle drei „an" | **Test** (AC-10, AC-25) |
| 6 | Go-PUT ersetzt statt zu mergen | **nicht bestätigt für `report_config`** | Einziger Schreibort des Blocks ist `handler/trip.go:352` mit `mergeConfigMap` (Grep `ReportConfig = ` in `internal/`: ein Treffer); `report_config` besteht aus Skalaren und zwei Listen (`multi_day_trend_reports`, `daily_summary_metrics`), die der Editor vollständig mitsendet; Python `save_trip` mergt tief (`loader.py:129-141`) | **Test** (AC-19) |
| N1 | Orakel `erreichbare_kanaele` kennt keine `send_*=false`-Schalter | **bestätigt (Test-Infrastruktur-Lücke)** | `einstellung_auslieferung_orakel.py:244-256` fügt E-Mail und eine Telegram-Variante **immer** hinzu, ohne `send_email`/`send_telegram`/Tier zu lesen — eine Kanal-Matrix wäre gegen ein Orakel geprüft, das E-Mail immer erwartet | Orakel-Erweiterung (Abschnitt „Orakel", AC-8, AC-10, AC-11) |
| N2 | Anzeige-Rückfall bei Trips ohne Per-Slot-Schlüssel | **bestätigt, Defekt (Anzeige ≠ Versand, Altdaten)** | Drei verschiedene Regeln: Trip-Übersicht liest strikt `rc.morning_enabled === true` (`rightColumn.ts:70-71`, `cockpitHelpers568.ts:61-62`, `:113`, `cockpitHelpers.ts:151`, `TripKachel.svelte:39`, `+page.svelte:127`); Editor `enabled && typeof morning_time === 'string'` (`VersandTab.svelte:163-170`, `EditReportConfigSection.svelte:165-173`); Python nach dem Fix `enabled`. Ein Altdaten-Trip mit `enabled=true` ohne Per-Slot-Schlüssel wird geliefert, aber als „aus" angezeigt | **Fix** (AC-23, AC-24) mit einer geteilten Fallzeilen-Tabelle gegen Auseinanderdriften |

## Deckungstabelle: Umfang S3 vs. Abgrenzung

| # | Thema | Ort | Begründung |
|---|---|---|---|
| D1 | Kanal an/aus je Kanal (`send_email/telegram/sms/premium_sms`), „alle aus", Defaults, Tier-Gate — bis zur ausgelieferten Nachricht | **S3**, Python-Bein (AC-8 bis AC-11) | Bisher nur „alle vier an" geprüft |
| D2 | Gesamtschalter `enabled`, `paused_until`, `paused_at`, `skip_next` | **S3**, Python-Bein (AC-3, AC-6, AC-7) | Steuerstelle `_get_active_trips`, ungeprüft |
| D3 | Einzel-Slot-Schalter Morgen/Abend (Hauptbefund) | **S3, produktiver Fix** (AC-1 bis AC-7, AC-20, AC-21) | Triage-Kriterium a |
| D4 | Alarm-Vorlauf-Sperre `trip_briefing_due_at` (zweiter Wirkort der Slot-Schalter) | **S3, Fix + Test** (AC-5) | Ohne Nachzug schwiege ein Alarm für ein Briefing, das nie kommt (Fehlerklasse #1555/#1584) |
| D5 | `email_format` full/compact bis zur Mail | **S3**, Python-Bein (AC-12) | Ungeprüft |
| D6 | Versandzeiten: Editor-Format, Go-Kappung, Python-Fenster | **S3**, Python/Go (AC-13, AC-14, AC-19) | Kette nirgends durchgehend |
| D7 | `sms_threshold` in SMS/Kurzform/Premium | **S3**, Test (AC-15) | Bisher `golden_c.json:93,101` nicht ausgewertet |
| D8 | `sms_threshold` in den E-Mail-Pillen | **S3, produktiver Fix** (AC-16) | Verdikt 2b |
| D9 | `channel_layouts_per_report`-Vorrang bis zum Text; Erhalt beim Editor-Speichern | **S3**, Python/Go (AC-17, AC-19) | Ungeprüft; Orakel-Lücke |
| D10 | Go-PUT-Roundtrip der vollständigen `report_config`, zwei Nutzer | **S3**, Go-Bein (AC-19, AC-20) | Multi-User-Pflicht |
| D11 | TS-Serialisierung von `report_config` gegen eingefrorenes Golden; Editor-Defaults; Anzeige-Regel | **S3**, TS-Bein (AC-22 bis AC-25) | Muster `merge_report_config_read_modify_write.test.ts` |
| D12 | Staging: Trip mit Abend=aus liefert kein Abend-Briefing | **S3**, E2E (AC-26) | SSR-Bausteintest beweist die Verdrahtung nicht |
| D13 | Bestandstests, die die alte Ableitung festschreiben; Kommentare „EINZIGER Schalter" | **S3** (AC-27) | Ablösung wird dokumentiert, nicht still vollzogen |
| D14 | Editor-Hinweis Kanal-Layout „nur abwählen" (B6) | **#2438 (S2b)** — außerhalb | UI-Änderung am geteilten Editor, eigene Abnahme |
| D15 | Editor zeigt/verwaltet `channel_layouts_per_report` (B7-Rest) | **Scheibe S6+** — außerhalb (bereits gebucht) | siehe Verdikt 1 |
| D16 | Alarm-Familie (Schwellen `alert_channel_thresholds`, Radar/Regen, amtliche Warnungen) | **S4** — außerhalb | Nicht mit `sms_threshold` (Erwähnungsschwelle) verwechseln |
| D17 | Ortsvergleich (`compare_slot_scheduler.py`, `channel_active_metrics`, eigener Speicherweg) | **S5** — außerhalb | Hat die Slot-Semantik bereits korrekt; eigener Datenpfad |
| D18 | B1/B2/B3/B5-Fixes aus S1 | unverändert **S6+** | Nicht Teil dieser Kette |

## Source

- **File (Python-Core, produktiv):** `src/app/models.py` (`TripReportConfig`: zwei neue Felder;
  neue Modulfunktion `slot_aktiv`), `src/app/loader.py` (Report-Config lesen `:583-617`, schreiben
  `:1822-1853`, flache Ableitung `:640-649`), `src/services/trip_report_scheduler.py`
  (`_get_active_trips` `:894-951`, `trip_briefing_due_at` `:143-206`), `src/output/renderers/trip_report.py`
  (Übertragung der globalen Erwähnungsschwelle auf die kollabierte E-Mail-Liste, `:133-139`)
- **File (Go-API, produktiv):** `internal/store/trip.go` (`deriveFlatFields` `:52-100`); Kommentare
  „EINZIGER Schalter" in `internal/store/trip.go` und `src/app/loader.py:640-647` werden bereinigt
- **File (Frontend, produktiv):** neu `frontend/src/lib/utils/reportSlotAktiv.ts` (eine Regel, ein
  Ort); Leser `frontend/src/lib/utils/rightColumn.ts:70-71`, `cockpitHelpers568.ts:61-62/113`,
  `frontend/src/routes/_home/cockpitHelpers.ts:151`, `frontend/src/routes/_home/TripKachel.svelte:39`,
  `frontend/src/routes/+page.svelte:127`; Editor-Startzustand `frontend/src/lib/components/shared/VersandTab.svelte:163-170`
  und `frontend/src/lib/components/edit/EditReportConfigSection.svelte:165-173`; Payload-Bau der beiden
  Editoren (verhaltensgleich in eine reine Funktion herausgezogen, falls er nur im `$effect` steht —
  Vorbild `weatherMetricsSavePayload.ts`)
- **File (Test-Infrastruktur):** `tests/helpers/einstellung_auslieferung_orakel.py`
  (`erreichbare_kanaele`, `erwartete_kaskade` erweitert), `tests/helpers/transport_mitschrift.py`
  (E-Mail-Aufzeichner merkt zusätzlich `mail_type`/`mail_format`),
  `tests/tdd/_einstellung_auslieferung_fixtures.py`
- **File (Test-Daten, neu):** `tests/fixtures/einstellung_auslieferung/golden_d.json`,
  `tests/fixtures/einstellung_auslieferung/report_config_nach_speichern_golden_d.json`,
  `tests/fixtures/report_config_slot_faelle.json` (geteilte Fallzeilen-Tabelle für Python, Go und TS)
- **File (Test, neu):** `tests/tdd/test_kanal_an_aus_kette.py`,
  `tests/tdd/test_report_config_slot_faelle.py`,
  `tests/tdd/test_mail_pillen_schwelle_bei_eigenem_layout.py`,
  `internal/store/trip_slot_flat_fields_test.go`, `internal/handler/report_config_roundtrip_test.go`,
  `frontend/src/lib/components/shared/versand-tab/__tests__/report_config_serialisierung_golden.test.ts`,
  `frontend/src/lib/utils/__tests__/report_slot_aktiv.test.ts`,
  `frontend/src/lib/components/shared/versand-tab/__tests__/versand_tab_defaults_gleich_auslieferung.test.ts`,
  `frontend/e2e/kanal-an-aus-kette.staging.spec.ts`
- **File (Test, angepasst — bewusste Ablösung, AC-27):** `internal/store/trip_flat_fields_test.go:71-75`,
  `tests/test_trip_flat_fields_dual_read.py`
- **Identifier:** `slot_aktiv(rc, report_type)`, `TripReportSchedulerService._get_active_trips`,
  `trip_briefing_due_at`, `_resolve_channel_flags`, `deriveFlatFields`, `mergeReportConfig`,
  `reportSlotAktiv`, `erwartete_kaskade`, `erreichbare_kanaele`

> **Schicht-Hinweis:** S3 berührt **alle drei** Schichten. Produktivcode ändert sich in Python-Core
> (Slot-Prüfung, Loader, Mail-Pillen-Schwelle), Go-API (flache Ableitung) und Frontend (eine Regel für
> die Anzeige). **Schema-relevante Dateien** (`src/app/models.py`, `src/app/loader.py`,
> `internal/store/trip.go`) lösen den Pre-Snapshot-Hook `data_schema_backup.py` aus (tar.gz nach
> `.backups/`). Alle Änderungen an Bestandsdaten sind **Read-Modify-Write mit Merge** — die beiden
> neuen Felder sind additiv, fehlende Schlüssel bleiben fehlend (kein Aufblähen, kein Replace).
>
> **Mail-Änderung:** Der Fix aus AC-16 berührt Mail-Inhalts-Dateien (`trip_report.py`) — der
> Renderer-Commit-Gate (Modus-Matrix-Test + Validator) greift, und der Trip-Briefing-Validator
> `briefing_mail_validator.py` (**nicht** `email_spec_validator.py`) ist Pflicht vor „E2E bestanden".

## Estimated Scope

- **LoC produktiv:** ~150–260 (Python: `slot_aktiv` + Felder + Loader lesen/schreiben + Scheduler-Aufrufe
  ~45; Mail-Pillen-Schwelle ~12; Go: `deriveFlatFields` + Kommentare ~25; Frontend: Helfer ~15, sechs
  Leser ~25, zwei Editor-Startzustände ~20, herausgezogene Payload-Funktion ~40).
  **Liegt im Grenzbereich zum 250-LoC-Limit** — vor `/50` `workflow.py status` fragen und bei Bedarf
  `workflow.py set-field loc_limit_override 500` setzen (das Limit zählt nur produktive Spec-Dateien).
- **LoC Test:** ~450–700 (Python-Kette, Fallzeilen-Tabelle, Go zwei Dateien, TS drei Dateien, E2E, Golden D)
- **Files:** ~30 neu/geändert
- **Effort:** high — Produktivänderung in drei Schichten, vier Testbeine, Abstimmung mit einer
  Parallelsitzung an denselben Dateien

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fix_2422_einstellung_gleich_auslieferung` (S1) | Spec | Orakel-Mechanik, `erwartete_kaskade`, Aufzeichner, Golden A/B/C; Zeilen 44/64 buchen B7 nach S6+ |
| `fix_2422_s2a_editor_gleich_gespeichert` (S2a) | Spec | Formvorlage; Deckungstabelle verweist die Kaskade und „mehrere Kanäle in einem Speicherzyklus" nach S3; `test_ac18` sperrt die Kennungen B4, B6–B9, K8, K9 — **hier werden keine Register-Einträge angelegt** |
| `tests/tdd/test_kanaltreue_adhoc_antwort.py:290-352` | Testvorlage | Scheduler-Einstieg `send_due_reports(now_utc)` mit Aufzeichner; Bezugsstunde fest statt Systemuhr |
| `tests/helpers/transport_mitschrift.py` | Testhilfe | Naht ausschließlich am Transport; wird um `mail_type`/`mail_format` erweitert |
| `src/services/trip_report_scheduler.py` | Modul | Wirkort der Slot-Prüfung; **Parallelsitzung #2417 hat hier uncommittete Änderungen** |
| `src/services/notification_service.py` | Modul | Versand je Flag (`:594/620/643/665`), `no_channel_configured` (`:575-581`); **ebenfalls Parallelsitzung #2417** |
| `src/services/alert_gate.py` / `src/services/trip_alert.py:1329-1334` | Modul | Aufrufer von `trip_briefing_due_at` (Alarm-Vorlauf-Sperre) |
| `src/services/report_config_resolver.py:114-150` | Modul | Ableitungsweg `email_format` |
| `src/services/user_tier.py` | Modul | `sms_allowed`/`premium_sms_allowed` (Berechtigung ≠ Einstellung) |
| ADR-0050 (Metrik-Kaskade) | ADR | Vorrang per_report > per_channel > global, globales Maximum |
| ADR-0049 (Premium-SMS teilt SMS) | ADR | Premium-SMS/Kurzform/SMS teilen den SMS-Text |
| ADR-0051 (Drei Zeitbegriffe) / ADR-0044 | ADR | Ortszeit je Trip, Fenster `NACHHOL_FENSTER_STUNDEN` |
| ADR-0032 (geteilte Tab-Editoren) | ADR | Begründet, warum `VersandTab` (route-Zweig) und `EditReportConfigSection` beide die eine Regel nutzen |
| `docs/reference/api_contract.md` (Trip-`report_config`, flache Felder) | Referenz | Beschreibung der beiden Per-Slot-Felder wird ergänzt (Doku-Update in `/50`) |
| Issue #2438 (S2b), #1199 (Sammel-Issue) | Issue | #2438 unberührt; Verdikt 3 wird dort als Checkbox-Zeile gebucht |

**Risiko Parallelsitzung #2417:** Diese Sitzung hat uncommittet Änderungen an `notification_service.py`
und `trip_report_scheduler.py` in Arbeit. Vor `/50` stimmt der Orchestrator per `ListAgents` +
`SendMessage` ab (nie MQ `gregor`→`gregor`), in welcher Reihenfolge gemergt wird. Die Slot-Prüfung
berührt in `trip_report_scheduler.py` nur zwei kleine Stellen (`_get_active_trips`,
`trip_briefing_due_at`) — Konflikte sind lokal lösbar, aber nicht auszuschließen.

## Implementation Details

> **Reihenfolge (PFLICHT für `/40`/`/50`):** (1) Rote Tests am Nutzerbild („Abend aus ⇒ nur Morgen-Mail",
> AC-1) und an der Mail-Pillen-Schwelle (AC-16) schreiben, (2) Produktivfixes, (3) **erst danach**
> Golden D und die eingefrorenen `report_config_nach_speichern_*`-Dateien aus der echten Helferkette
> erzeugen, damit sie den korrigierten Stand zeigen.

### Semantik der Slot-Prüfung (eine Regel, ein Ort)

Neue Modulfunktion in `src/app/models.py`:

```
slot_aktiv(rc: Optional[TripReportConfig], report_type: str) -> bool
  rc ist None                      -> True            (Trip ohne report_config: Bestandsverhalten)
  rc.enabled is False              -> False           (Gesamtschalter bleibt Master, schaltet BEIDE Slots ab)
  per_slot = rc.morning_enabled bzw. rc.evening_enabled  (je report_type)
  per_slot ist True / False        -> per_slot        (False schaltet NUR diesen Slot ab)
  per_slot ist None                -> True            (Rückfall auf enabled, das hier True ist: Altdaten unverändert)
```

- `TripReportConfig` bekommt `morning_enabled: Optional[bool] = None` und
  `evening_enabled: Optional[bool] = None`. Der Loader übernimmt nur echte `bool`-Werte
  (`isinstance(x, bool)`), alles andere (JSON-`null`, Zeichenkette, Zahl) wird zu `None` — fail-safe
  auf den Bestandsfall.
- Der Schreibweg (`loader.py` `report_config`-Block) schreibt die Schlüssel **nur, wenn sie nicht
  `None` sind** (additiv, Muster `sms_threshold` #624). Grund: `save_trip` mergt gegen die Datei
  (`_deep_merge_preserve_unknown`); ein geladenes `None` bedeutet „Schlüssel war nicht da" — es wird
  nicht als `null` auf die Platte geschrieben, ein gesetzter Wert bleibt garantiert erhalten.
- **Randfall `enabled=True, morning=False, evening=False`:** beide Slots aus (jeder Slot folgt seinem
  eigenen `False`). Das entspricht der Editor-Anzeige; der Editor selbst schreibt in diesem Fall
  `enabled=false` (`enabled = morning_enabled || evening_enabled`) — beide Schreibweisen liefern
  dasselbe Ergebnis (AC-4).
- `_get_active_trips` und `trip_briefing_due_at` rufen **dieselbe** Funktion auf (Prüfort = Wirkort,
  keine zweite Fassung). In `_get_active_trips` steht die Slot-Prüfung **neben** der `enabled`-Prüfung
  und **vor** dem Verbrauch von `skip_next` — ein abgeschalteter Slot darf den Überspringen-Wunsch des
  Nutzers nicht aufbrauchen (AC-6). In `trip_briefing_due_at` steht sie **innerhalb** der Slot-Schleife
  (`for report_type, zieltag in ...`), nicht davor: dort ist der Gesamtschalter-Test bisher vor der
  Schleife, ein Slot-genauer Test kann nur in der Schleife stehen. Der Master-Test `enabled is False`
  entfällt dort zugunsten von `slot_aktiv` in der Schleife (gleiches Ergebnis für beide Slots).
- Weitere Aufrufer von `_get_active_trips`: `trip_report_scheduler.py:456` (direkter Sammelversand),
  `:577` (`_collect_due_trips`, speist `run_briefing_dispatch`). Beide erben die Prüfung ohne eigenen
  Code.
- **Flache Ableitung (Python):** `loader.py:648-649` setzt `morning_enabled`/`evening_enabled` des
  `Trip` künftig aus `slot_aktiv(report_config, "morning"/"evening")` statt beide aus `enabled`; ohne
  `report_config` weiter `None`.
- **Flache Ableitung (Go):** `deriveFlatFields` (`internal/store/trip.go`) leitet dieselbe Regel ab:
  Gesamtschalter `enabled` (fehlend ⇒ an, wie Python), dann Per-Slot-`bool` (`rc["morning_enabled"]`),
  sonst Rückfall; ohne `report_config` bleiben die Felder `nil` (Stale-Reset aus F001 bleibt). Dieselbe
  Fallzeilen-Tabelle (`tests/fixtures/report_config_slot_faelle.json`) treibt den Go-, den Python- und
  den TS-Test — so können die drei Fassungen nicht unbemerkt auseinanderlaufen.
- **Frontend:** eine Funktion `reportSlotAktiv(rc, slot)` in `frontend/src/lib/utils/reportSlotAktiv.ts`
  mit derselben Regel. Alle sechs Leser der Trip-Übersicht und beide Editor-Startzustände rufen sie auf.
  Die Zeitbedingung `typeof morning_time === 'string'` im Editor-Startzustand entfällt (Verhalten
  siehe „Gewollte Verhaltensänderung 3"). Der Ortsvergleich-Zweig von `VersandTab` (Preset-Props,
  Standardwerte `true`/`false`) bleibt unberührt.

### Mail-Pillen-Schwelle (Fix AC-16)

In `trip_report.py` wird beim Bau der kollabierten E-Mail-Liste (`active_metrics`, `:136-138`) für jeden
Eintrag ohne eigenes `sms_threshold` der Wert des gleichnamigen Eintrags der **unkollabierten globalen**
Liste (`_dc_uncollapsed.metrics`) übernommen. Ein am Layout-Eintrag selbst gesetzter Wert gewinnt weiter
(er kommt aus Bestandsdaten und wäre spezifischer). Damit lesen `html.py`, `plain.py` und `compact.py`
unverändert und die Pillen folgen derselben Schwelle wie die SMS. Der Weg für Telegram-Kurzform und
Premium-SMS ist unverändert (sie teilen den SMS-Text und lesen bereits die globale Schwelle).

### Orakel-Erweiterung (Test-Infrastruktur)

- `erreichbare_kanaele(report_config, *, tier)` liest aus dem **rohen JSON**, mit denselben
  Standardwerten wie der Editor: `send_email` fehlend ⇒ an; `send_telegram`, `send_sms`,
  `send_premium_sms` fehlend ⇒ aus; kein `report_config` ⇒ nur E-Mail. Berechtigung: SMS nur bei
  Tier `standard`/`premium`, Premium-SMS nur bei Tier `premium`. E-Mail-HTML und -Klartext sind **eine**
  Nachricht (zwei Teile), Telegram-Form (`rich`/`kurzform`) folgt `telegram_style`.
- `erwartete_kaskade` bekommt den Vorrang `channel_layouts_per_report[report_type][kanal]` vor
  `channel_layouts[kanal]` vor `display_config.metrics` (weiterhin **eigenständig** aus dem rohen
  JSON, kein Import der Produktkaskade; Schnitt gegen das globale Maximum wie bei `per_channel`).
  Die S1-Drift-Tests der Erwartungsdateien bleiben grün, weil A/B/C kein `per_report` tragen.
- Der E-Mail-Aufzeichner in `transport_mitschrift.py` speichert zusätzlich `mail_type` und
  `mail_format` (bisher nimmt er sie an und verwirft sie), damit `email_format=compact` an der Naht
  beobachtbar wird.

### Golden D (neu: `tests/fixtures/einstellung_auslieferung/golden_d.json`)

Pflicht-Eigenschaften (Implementierungs-Constraint für `/40`):

- **D-1:** `report_config` mit `enabled=true`, `morning_enabled=true`, `evening_enabled=false`,
  Zeiten im Editor-Format (`"06:00:00"`/`"20:00:00"`), `send_email=true`, `send_telegram=true`,
  `send_sms=true`, `send_premium_sms=true`, `email_format="compact"`, `telegram_style="kurzform"`, dazu ein dem
  Frontend unbekannter Schlüssel (`change_threshold_wind_kmh`) für den Erhalt-Nachweis.
- **D-2:** `display_config.metrics` mit gesetzter globaler `sms_threshold` für Regen (0,1) und
  Regenwahrscheinlichkeit (10) — **abweichend** von `DEFAULTS` (0,2/20), damit AC-15/AC-16 unterscheiden
  können.
- **D-3:** ein E-Mail-Kanal-Layout **ohne** `sms_threshold`-Einträge (löst Verdikt 2b aus) und
  `channel_layouts_per_report.evening.email` mit einer **anderen** Auswahl/Reihenfolge als
  `channel_layouts.email` (löst den Vorrang aus), zusätzlich `channel_layouts_per_report.evening.sms`.
  Für den Morgen gibt es **kein** `per_report`-Layout (Gegenprobe: Morgen folgt `per_channel`).
- **D-4:** Etappen für heute **und** morgen (Ortstag), damit Morgen- und Abend-Slot fällig sein können.

Aus Golden D wird per echter Editor-Helferkette die eingefrorene Datei
`report_config_nach_speichern_golden_d.json` erzeugt (der `report_config`-Blob, den `VersandTab`/
`EditReportConfigSection` ohne Änderung zurückschreiben); sie ist ein roher, geprüfter Zustand, kein
Orakel-Ergebnis.

### Vier Testbeine

**(a) Python-Scheduler-Einstieg** (`tests/tdd/test_kanal_an_aus_kette.py`, Vorlage
`test_kanaltreue_adhoc_antwort.py:290-352`): Nutzer mit echtem `user.json` (Tier, Empfänger,
`sms_verified_number`; Kennung ohne „test"/„tdd", Herkunftssperre #2406), Trip als **Persistenzformat des
Editors** über den echten `load_trip`, echter `TripReportSchedulerService.send_due_reports(now_utc)`,
Naht **nur** am Transport (Aufzeichner). Bezugszeit fest (Ortstag, feste Stunde), nie die Systemuhr.
Kein Mock-Theater: der Aufzeichner ersetzt die Netz-Naht, nicht die Entscheidung, wer bedient wird.

**(b) Go** (`internal/store/`, `internal/handler/`): Persistenz-Roundtrip der vollständigen
`report_config` über `PUT /api/trips/{id}`, Zwei-Nutzer-Aufbau über `s.WithUser` mit echter `user_id`
(nie `"default"`), Vorbild `fix_go_rmw_merge_1082_1103_test.go` und `newTestStore`/`seedTrip`.

**(c) TS** (`node --test`, kein Vitest): Serialisierung des `report_config`-Blobs gegen die eingefrorene
Datei, Anzeige-Regel gegen die geteilte Fallzeilen-Tabelle, Editor-Defaults per SSR-Render (die
`send_*`-Startwerte entstehen beim Erzeugen, nicht in `onMount` — deshalb unter `svelte/server`
messbar).

**(d) Staging-E2E** (Playwright): echte Bedienung im Editor, ein ausgelöster Sammellauf, IMAP-Prüfung.

## Expected Behavior

- **Input:** gespeichertes Trip-JSON (Persistenzformat des Editors) mit beliebiger Kombination aus
  Gesamtschalter, Einzel-Slot-Schaltern, Kanal-Schaltern, Zeiten, `email_format`, `sms_threshold`,
  `channel_layouts(_per_report)`.
- **Output:** Es geht genau das hinaus, was das JSON aussagt: pro fälligem, aktivem Slot genau ein
  Briefing an genau die eingeschalteten und berechtigten Kanäle, in der eingestellten Form
  (`compact`/`full`), mit der eingestellten Metrik-Auswahl/Reihenfolge (inkl. `per_report`-Vorrang) und
  den eingestellten Erwähnungsschwellen in SMS, Kurzform, Premium-SMS **und** E-Mail-Pillen. Ein
  abgeschalteter Slot liefert nichts, verbraucht kein `skip_next` und hält keinen Alarm zurück.
- **Side effects:** Produktivänderung in drei Schichten (siehe Source); neue additive Felder
  `report_config.morning_enabled/evening_enabled` im Python-Modell; neue Testdateien, Golden D,
  Fallzeilen-Tabelle; bewusste Anpassung zweier Bestandstests; **keine** Register-Erweiterung.

## Acceptance Criteria

### Bein (a) — Python-Scheduler-Einstieg

- **AC-1 (Abend aus ⇒ nur das Morgen-Briefing kommt an):** Given ein Trip, dessen Editor-Stand
  „Morgen aktiv" an und „Abend aktiv" aus ist (`enabled=true`, `morning_enabled=true`,
  `evening_enabled=false`), beide Zeiten in derselben Stunde, Etappen heute und morgen / When der
  reguläre Sammellauf `send_due_reports` zu dieser Stunde läuft / Then geht genau **ein** Briefing
  hinaus (das Morgen-Briefing) und kein Abend-Briefing — beim Nutzer kommt an, was der Editor zeigt.
  - Test: `test_kanal_an_aus_kette.py::test_abend_aus_liefert_nur_morgen` — Aufzeichner zeigt genau eine
    Sendung; der Betreff/Berichtstyp ist Morgen; das Ergebnis ist `(1, 0)`. Rot vor dem Fix.

- **AC-2 (Morgen aus ⇒ nur das Abend-Briefing kommt an):** Given derselbe Trip mit „Morgen aktiv" aus
  und „Abend aktiv" an / When derselbe Lauf läuft / Then geht genau ein Briefing hinaus (Abend), kein
  Morgen-Briefing.
  - Test: `test_morgen_aus_liefert_nur_abend` (Umkehrung zu AC-1, damit eine einseitige Prüfung nicht
    besteht).

- **AC-3 (Altdaten und Gesamtschalter):** Given (a) ein Trip mit `enabled=true` und **ohne**
  Per-Slot-Schlüssel, (b) ein Trip mit `enabled=false` und ohne Per-Slot-Schlüssel, (c) ein Trip mit
  `enabled=false` aber `morning_enabled=true` und `evening_enabled=true` / When der Lauf zur
  Fälligkeit beider Slots läuft / Then liefert (a) beide Slots wie bisher, (b) keinen Slot, (c) keinen
  Slot — der Gesamtschalter ist Master und schaltet beide ab, ein Einzel-Schalter „aus" schaltet nur
  seinen Slot ab.
  - Test: `test_kanal_an_aus_kette.py::test_altdaten_und_gesamtschalter_folgen_der_regel`, parametrisiert
    über die Zeilen der geteilten Tabelle `tests/fixtures/report_config_slot_faelle.json` (Python-Bein).

- **AC-4 (Randfall alle Slots aus trotz `enabled=true`):** Given ein Trip mit `enabled=true`,
  `morning_enabled=false`, `evening_enabled=false` (so speichert der Editor `enabled=false`; von Hand
  kann auch `enabled=true` stehen bleiben) / When der Lauf zu beiden Fälligkeiten läuft / Then geht
  **nichts** hinaus, in beiden Schreibweisen (`enabled=true` und `enabled=false`).
  - Test: `test_kanal_an_aus_kette.py::test_beide_slots_aus_liefert_nichts_in_beiden_schreibweisen`.

- **AC-5 (Alarm-Vorlauf hält für ein abgeschaltetes Briefing nichts zurück):** Given ein Trip mit
  „Abend aktiv" aus und „Morgen aktiv" an / When das Fälligkeits-Prädikat des Alarm-Vorlaufs
  (`trip_briefing_due_at`) für einen Zeitpunkt im Abend-Fenster bzw. im Morgen-Fenster gefragt wird /
  Then ist es im Abend-Fenster **nicht** fällig (der Alarm schweigt nicht für ein Briefing, das nie
  kommt) und im Morgen-Fenster fällig; bei `enabled=false` ist es in keinem Fenster fällig.
  - Test: `test_report_config_slot_faelle.py::test_alarm_vorlauf_folgt_derselben_slot_regel`,
    parametrisiert über die geteilte Fallzeilen-Tabelle; ruft das Prädikat direkt mit echter
    `user_id`. Fängt die Entfernung der Prüfung dort, die `test_abend_aus_liefert_nur_morgen` **nicht**
    fangen kann (eigene Mutation M5).

- **AC-6 (`skip_next` wird nicht von einem abgeschalteten Slot verbraucht):** Given ein Trip mit
  `skip_next=true` und „Abend aktiv" aus / When der Sammellauf zur Abend-Fälligkeit läuft und danach
  zur Morgen-Fälligkeit des nächsten Tages / Then ist `skip_next` nach dem Abend-Lauf **weiterhin
  gesetzt** (der abgeschaltete Slot hat den Wunsch nicht aufgebraucht), und das nächste aktive
  Briefing wird übersprungen und verbraucht ihn. Dabei bleiben alle übrigen Schlüssel der Datei
  (Per-Slot-Schalter, Kanäle, Zeiten, unbekannte Felder) unverändert erhalten — geprüft an der Datei
  nach dem echten Schreiber (`save_trip` aus dem `skip_next`-Read-Modify-Write).
  - Test: `test_kanal_an_aus_kette.py::test_skip_next_bleibt_bei_abgeschaltetem_slot_und_datei_bleibt_vollstaendig`.

- **AC-7 (Pause und Trip-Pause):** Given ein Trip mit `paused_until` in der Zukunft, ein zweiter mit
  abgelaufenem `paused_until`, ein dritter mit gesetztem `paused_at` / When der Lauf zur Fälligkeit
  läuft / Then liefert der erste und der dritte nichts, der zweite normal.
  - Test: `test_kanal_an_aus_kette.py::test_pause_und_trip_pause_unterdruecken_den_versand`.

- **AC-8 (Kanal-Matrix: genau die eingeschalteten Kanäle werden bedient):** Given ein Nutzer mit
  Tier `premium` und ein Trip, bei dem jeweils **nur ein** Kanal (E-Mail, Telegram, SMS,
  Premium-SMS) eingeschaltet ist, sowie jeweils **alle bis auf einen** / When der reguläre Slot-Lauf
  läuft / Then bedient der Aufzeichner **exakt** die eingeschaltete Menge — jeder der vier Kanäle mit
  demselben Maßstab, keiner nachrangig. Erwartete Menge kommt aus dem erweiterten Orakel
  `erreichbare_kanaele` (rohes JSON), nie aus einer Produktfunktion.
  - Test: `test_kanal_an_aus_kette.py::test_kanalmatrix_bedient_genau_die_eingeschalteten_kanaele`,
    parametrisiert über acht Kombinationen; Fehlermeldung nennt die Menge der bedienten Kanäle.

- **AC-9 (alle vier aus ⇒ nichts geht hinaus, ehrlich verbucht):** Given ein Trip mit allen vier
  Kanälen aus / When der Slot-Lauf läuft / Then geht keine Nachricht hinaus, der Slot wird mit dem
  Ausgang „no_channels" vermerkt (kein Fehler, kein erneuter Versuch im Nachhol-Fenster) und der Lauf
  meldet keinen Versandfehler.
  - Test: `test_kanal_an_aus_kette.py::test_alle_kanaele_aus_liefert_nichts_und_vermerkt_no_channels` —
    Aufzeichner leer; Rückgabe des Einzel-Slot-Versands ist `no_channels`; ein zweiter Lauf in
    derselben Stunde sendet ebenfalls nichts.

- **AC-10 (fehlende Schlüssel: dieselben Standardwerte wie der Editor):** Given (a) ein Trip, dem
  `send_email` in `report_config` fehlt, (b) einer, dem `send_telegram`, `send_sms`, `send_premium_sms`
  fehlen, (c) einer ganz ohne `report_config` / When der Slot-Lauf läuft / Then wird E-Mail bedient
  (Standard „an"), Telegram/SMS/Premium-SMS **nicht** (Standard „aus"), und (c) bekommt nur E-Mail —
  genau wie der Editor die Kanäle anzeigt (AC-25).
  - Test: `test_kanal_an_aus_kette.py::test_fehlende_kanal_schluessel_folgen_den_editor_defaults`.

- **AC-11 (Berechtigung ≠ Einstellung):** Given ein Trip mit `send_sms=true` und `send_premium_sms=true`
  bei einem Nutzer mit Tier `free`, sowie bei Tier `standard` / When der Slot-Lauf läuft / Then wird bei
  `free` weder SMS noch Premium-SMS ausgeliefert; bei `standard` SMS, aber **nicht** Premium-SMS
  (eigenes Tier-Gate, ADR-0049). E-Mail und Telegram sind davon unberührt.
  - Test: `test_kanal_an_aus_kette.py::test_tier_gate_begrenzt_sms_und_premium_sms`, Erwartung aus
    `erreichbare_kanaele(..., tier=...)`.

- **AC-12 (`email_format=compact` kommt als kompakte Mail an):** Given Golden D mit
  `email_format="compact"` und (Gegenprobe) dieselbe Fassung mit `"full"` / When der Slot-Lauf läuft /
  Then trägt die aufgezeichnete E-Mail bei `compact` den Marker `mail_format="compact"` und den
  kompakten Klartext-Aufbau (kein HTML-Stundentabellen-Körper), bei `full` `mail_format="full"` mit
  Stundentabellen; beide tragen `mail_type` für Trip-Briefing.
  - Test: `test_kanal_an_aus_kette.py::test_email_format_compact_und_full_kommen_wie_eingestellt_an`.

- **AC-13 (Versandzeiten und Nachhol-Fenster im Editor-Format):** Given ein Trip mit Morgen 06:00:00 und
  Abend 20:00:00 (Editor-Format) in einer Ortszeit, die nicht UTC ist / When der Lauf um 05:59, 06:00,
  08:59, 09:00 Ortszeit (Morgen) bzw. 19:59, 20:00, 22:59 Ortszeit (Abend) läuft, und danach ein zweites
  Mal im selben Fenster / Then liefert nur die Ortszeit im Fenster `[Stunde, Stunde+3)` und **nie
  doppelt** (der Vermerk des ersten Versands beendet das Fenster).
  - Test: `test_kanal_an_aus_kette.py::test_versandzeit_fenster_und_kein_doppelversand`, parametrisiert
    über die Ortsstunden; feste Bezugszeiten, nicht die Systemuhr.

- **AC-14 (Zeitfeld mit Minuten aus Altdaten löst zur Stunde aus):** Given ein Trip, dessen
  `morning_time` mit Minuten gespeichert ist (`"07:30:00"`, Altbestand oder direkter API-Weg) /
  When der Lauf um 07:00 Ortszeit läuft / Then wird das Morgen-Briefing zur Stunde 7 ausgeliefert, nicht
  erst „um halb acht" und nicht gar nicht (Python nimmt die Stunde).
  - Test: `test_kanal_an_aus_kette.py::test_zeitfeld_mit_minuten_loest_zur_stunde_aus`.

- **AC-15 (globale `sms_threshold` wirkt in SMS, Kurzform und Premium-SMS):** Given Golden D mit
  globaler Regen-Schwelle 0,1 mm (Standardwert wäre 0,2) und einem Stundenwert von 0,15 mm / When der
  Slot-Lauf läuft / Then enthalten SMS, Telegram-Kurzform und Premium-SMS den Regen-Token; mit
  entfernter Schwelle (Standard 0,2) enthalten sie ihn **nicht**. Eine im Kanal-Layout stehende
  `sms_threshold` ändert an der SMS nichts (Schwelle ist bewusst global, KL-4).
  - Test: `test_kanal_an_aus_kette.py::test_globale_sms_schwelle_wirkt_in_allen_drei_sms_texten`,
    Erwartung aus dem gespeicherten JSON; Gegenprobe ohne Schwelle im selben Test.

- **AC-16 (Fix: Mail-Pillen folgen der eingestellten Schwelle auch bei eigenem E-Mail-Layout):**
  Given Golden D (E-Mail hat ein eigenes Layout ohne `sms_threshold`, global 0,1 mm) und ein Stundenwert
  von 0,15 mm / When die E-Mail (HTML, Klartext und Kompaktform) gerendert und versendet wird / Then
  erscheint die Regen-Pille in **allen drei** Formen — wie in der SMS aus AC-15; ein Layout-Eintrag mit
  **eigener** Schwelle behält Vorrang vor der globalen; ohne globale Schwelle bleibt der Standardwert.
  - Test: `test_mail_pillen_schwelle_bei_eigenem_layout.py` (drei Renderer-Einstiege `render_html`,
    `render_plain`, `render_compact` **und** der Weg durch `send_due_reports`; echte Stundenreihe, kein
    Mock). Rot vor dem Fix. Die Staging-Mail geht durch `briefing_mail_validator.py` (AC-26).

- **AC-17 (`channel_layouts_per_report` gewinnt bis in den Text):** Given Golden D mit einem
  Abend-`per_report`-Layout für E-Mail und SMS, das sich von `channel_layouts` unterscheidet, und ohne
  Morgen-`per_report`-Layout / When Abend- und Morgen-Briefing ausgeliefert werden / Then zeigt das
  Abend-Briefing in E-Mail, SMS, Premium-SMS und Kurzform die `per_report`-Auswahl und -Reihenfolge, das
  Morgen-Briefing die `per_channel`-Auswahl; ein `per_report`-Eintrag darf das globale Maximum nicht
  erweitern (Schnitt).
  - Test: `test_kanal_an_aus_kette.py::test_per_report_layout_gewinnt_am_abend_morgen_folgt_per_channel`,
    Erwartung aus dem erweiterten `erwartete_kaskade` (rohes JSON).

### Bein (b) — Go

- **AC-18 (Go-PUT-Roundtrip der vollständigen `report_config`, zwei Nutzer):** Given zwei verschiedene
  Nutzer A und B mit je einem Trip **gleicher Kennung** / When A per `PUT /api/trips/{id}` die
  vollständige `report_config` aus `report_config_nach_speichern_golden_d.json` (Kanäle, Zeiten,
  `email_format`, `enabled`, Per-Slot-Schalter, unbekannter Schlüssel) sendet und B eine andere
  Konfiguration speichert / Then liest jeder Nutzer per `GET` und direkt aus seiner Datei exakt seinen
  Stand zurück, der unbekannte Schlüssel bleibt erhalten, B sieht und verändert A's Stand nicht; ein
  Trip, den nur A besitzt, ist für B per `GET` und `PUT` nicht auffindbar (404) und bleibt danach
  unverändert.
  - Test: `internal/handler/report_config_roundtrip_test.go::TestReportConfigRoundtrip_ZweiNutzer`
    (echte `user_id` über `s.WithUser`, nie `"default"`).

- **AC-19 (Go: Minuten-Kappung, Teil-PUT, `per_report` bleibt erhalten):** Given ein Trip mit
  gespeichertem `channel_layouts_per_report` und einer `report_config` / When ein PUT nur
  `morning_time: "07:30:00"` in `report_config` sendet, danach ein zweiter PUT nur `display_config`
  mit `channel_layouts` (ohne `per_report`) / Then steht `morning_time` gekappt als `"07:00:00"` in
  Antwort und Datei, alle übrigen `report_config`-Schlüssel sind unverändert, und
  `channel_layouts_per_report` ist nach dem zweiten PUT **unverändert vorhanden** (der Editor-Speicherweg
  löscht ihn nicht; Verdikt 1).
  - Test: `internal/handler/report_config_roundtrip_test.go::TestReportConfigRoundtrip_KappungTeilPutUndPerReport`.

- **AC-20 (Go: flache Trip-Felder folgen der einen Regel):** Given die Zeilen der geteilten Tabelle
  `tests/fixtures/report_config_slot_faelle.json` (Datei per relativem Pfad gelesen) / When ein Trip mit
  der jeweiligen `report_config` geladen und gespeichert wird / Then stehen die abgeleiteten flachen
  Felder `morning_enabled`/`evening_enabled` des Trips exakt auf dem Tabellenwert; ohne `report_config`
  bleiben sie `nil`, und ein zuvor gespeicherter, veralteter Wert wird beim erneuten Ableiten überschrieben
  (kein Stale).
  - Test: `internal/store/trip_slot_flat_fields_test.go::TestDeriveFlatFields_SlotFaelle`.

### Loader (Python-Persistenz)

- **AC-21 (Loader liest und schreibt die Per-Slot-Schalter verlustfrei):** Given ein Trip-JSON mit
  `report_config.morning_enabled=true` und `evening_enabled=false` sowie eines ohne diese Schlüssel /
  When beide über den echten `load_trip` geladen und über `save_trip` zurückgeschrieben werden / Then
  bleiben gesetzte Werte in der Datei genau erhalten, fehlende Schlüssel bleiben fehlend (kein
  `null`-Eintrag), unbekannte Schlüssel bleiben erhalten, und die flachen Felder des geladenen Trips
  entsprechen der Fallzeilen-Tabelle; ein Nicht-`bool`-Wert (z. B. `"ja"`) wird als „nicht gesetzt"
  gelesen.
  - Test: `test_report_config_slot_faelle.py::test_loader_roundtrip_und_flache_felder_folgen_der_tabelle`.

### Bein (c) — TypeScript

- **AC-22 (TS: `report_config` wird ohne Änderung unverändert zurückgeschrieben, Änderungen kommen
  wie gemeint):** Given die `report_config` aus Golden D geladen / When der Payload-Baustein der
  Editoren (`mergeReportConfig` mit den Feldern, die `VersandTab` bzw. `EditReportConfigSection`
  besitzen) ohne Änderung läuft / Then entspricht das Ergebnis strukturell der eingefrorenen
  `report_config_nach_speichern_golden_d.json` **einschließlich** des unbekannten Schlüssels und aller
  vier Kanal-Schalter; schaltet der Nutzer „Abend" aus, steht `enabled=true`, `evening_enabled=false`,
  `morning_enabled=true`; schaltet er beide aus, steht `enabled=false`; jede Abweichung macht den Test rot.
  - Test: `report_config_serialisierung_golden.test.ts` (`node --test`), Payload-Funktion ist die
    **von den Komponenten tatsächlich benutzte** reine Funktion (kein Nachbau im Test).

- **AC-23 (Fix: Trip-Übersicht zeigt den Slot-Zustand nach derselben Regel wie der Versand):**
  Given die Zeilen der geteilten Tabelle (Datei per relativem Pfad gelesen) / When die Trip-Übersicht
  (`getReportSchedule`, Cockpit-Helfer, Trip-Kachel, Startseite, `deriveNextSend`) einen Trip mit der
  jeweiligen `report_config` anzeigt / Then steht „Morgen"/„Abend" genau auf dem Tabellenwert — auch
  für Altdaten ohne Per-Slot-Schlüssel („aktiv", wenn der Gesamtschalter an ist) und bei
  `enabled=false` („aus", auch wenn ein Per-Slot-Schlüssel `true` trägt).
  - Test: `report_slot_aktiv.test.ts` — Helfer `reportSlotAktiv` **und** ein Leser-Test je Leser
    (`rightColumn.getReportSchedule`, `cockpitHelpers568`, `cockpitHelpers.deriveNextSend`).

- **AC-24 (Fix: Editor-Startzustand folgt derselben Regel):** Given ein Trip mit `enabled=true`, ohne
  Per-Slot-Schlüssel und **ohne** Zeitfelder in `report_config` / When der Versand-Reiter geöffnet wird /
  Then zeigt er „Morgen aktiv" und „Abend aktiv" als angehakt (bisher „aus", obwohl das Briefing
  mit den Standardzeiten geliefert wurde); bei `enabled=false` zeigt er beide aus; mit Per-Slot-Schlüsseln
  zeigt er diese.
  - Test: `report_slot_aktiv.test.ts::editor_startzustand_folgt_der_regel` — der Startzustand wird aus
    derselben reinen Funktion abgeleitet, die `VersandTab.svelte` und `EditReportConfigSection.svelte`
    aufrufen; die Verdrahtung beweist AC-26.

- **AC-25 (Editor-Kanal-Defaults gleich Auslieferung):** Given `report_config` (a) ohne `send_email`,
  (b) ohne `send_telegram`/`send_sms`/`send_premium_sms`, (c) ganz ohne `report_config` / When der
  Versand-Reiter serverseitig gerendert wird / Then ist E-Mail angehakt und die anderen drei nicht — das
  ist dieselbe Aussage wie AC-10 für die Auslieferung.
  - Test: `versand_tab_defaults_gleich_auslieferung.test.ts` (SSR-Render, Startwerte entstehen beim
    Erzeugen der Komponente).

### Bein (d) — Staging-E2E und Gesamtnachweis

- **AC-26 (E2E: „Abend aus" im Editor ⇒ auf Staging kommt kein Abend-Briefing an):** Given ein Staging-
  Testnutzer mit genau einem Trip (Etappen heute und morgen, Morgen- und Abend-Zeit in derselben
  Stunde, E-Mail-Kanal an) / When der Nutzer im echten Browser im Versand-Reiter „Abend aktiv"
  abhakt und speichert, `GET /api/trips/{id}` den Stand bestätigt (`evening_enabled=false`,
  `morning_enabled=true`, `enabled=true`) und danach **ein** Sammellauf für diesen Nutzer ausgelöst wird /
  Then liegt im Test-Postfach (IMAP) **genau eine** Trip-Briefing-Mail — die des Morgens (sie ist die
  Positivkontrolle, dass der Lauf überhaupt lief) — und keine Abend-Mail; die Mail besteht
  `briefing_mail_validator.py` mit Exit 0.
  - Test: `frontend/e2e/kanal-an-aus-kette.staging.spec.ts` (nur Staging, nicht in der CI-Ampel; Ratsche
    laut `docs/reference/gates_und_ratschen.md`), plus Lauf von
    `uv run python3 .claude/hooks/briefing_mail_validator.py` gegen die zugestellte Staging-Mail. Ein
    einzelnes „keine Abend-Mail" ohne Morgen-Mail zählt **nicht** als Bestehen.

- **AC-27 (Bewusste Ablösung der alten Ableitung, Kommentare bereinigt):** Given
  `internal/store/trip_flat_fields_test.go:71-75` und `tests/test_trip_flat_fields_dual_read.py`
  schreiben die alte Regel „flache Felder = `enabled`" fest / When der Fix umgesetzt ist / Then werden
  diese Tests bewusst auf die neue Regel angepasst (nicht gelöscht, nicht unangepasst grün), und die
  Kommentare „`enabled` ist der EINZIGE Schalter" in `loader.py:640-647` und `internal/store/trip.go`
  sind durch die neue Regel ersetzt. Der Bestandsschutz für Trips ohne Per-Slot-Schlüssel bleibt in
  beiden Tests als Fall erhalten.
  - Test: die angepassten Bestandstests selbst; zusätzlich Diff-Nachweis in der Commit-Historie.

- **AC-28 (Keine neuen Register-Einträge):** Given diese Scheibe / When in `/40`/`/50` eine weitere,
  bisher unbekannte Abweichung in dieser Kette auftritt / Then wird sie, wenn im Rahmen dieser Kette
  lösbar, produktiv gefixt; liegt sie außerhalb, stoppt der Entwickler und legt sie dem PO vor —
  **kein** befristeter Register-Eintrag. Nach S3 enthält das Ausnahme-Register weiterhin nur die
  S1-Einträge.
  - Test: Erweiterung der bestehenden Register-Prüfung `test_ac18_keine_neuen_register_eintraege`
    (zählt die Einträge und prüft, dass keine Kennung dieser Spec — `S3-…` — und keine der gesperrten
    Kennungen darin steht).

## Mutations-Pflichtfänge (für `/50`, Adversary Step 3b)

**Regel:** Mutation nur per String-Ersetzung mit **externer Sicherungskopie** — nie `git checkout/
stash/reset`. Ein grüner Lauf beweist nur, dass die Tests durchlaufen. Leitfrage je Mutation: **Ist die
Zusicherung dort geprüft, wo sie WIRKT — oder nur dort, wo der Code steht?** Zählt WELCHER Test rot
wird, nicht dass irgendeiner rot wird.

| Nr | Mutation | Erwartet rot (Name des fangenden Tests) |
|---|---|---|
| M1 | Slot-Prüfung in `_get_active_trips` entfernen (`slot_aktiv`-Aufruf raus, nur `enabled` bleibt) | `test_abend_aus_liefert_nur_morgen`, `test_morgen_aus_liefert_nur_abend`, `test_beide_slots_aus_liefert_nichts_in_beiden_schreibweisen` |
| M2 | `None`-Rückfall kippen (`None` ⇒ `False`) | `test_altdaten_und_gesamtschalter_folgen_der_regel` (Fall a); Gegenmutation `enabled=false` überstimmt Per-Slot `true` nicht mehr ⇒ derselbe Test (Fall c) |
| M3 | Per-Slot-Lesen im Loader entfernen (`rc_data.get("morning_enabled")` weg) | `test_abend_aus_liefert_nur_morgen` (Einstieg über Datei/`load_trip`), `test_loader_roundtrip_und_flache_felder_folgen_der_tabelle` |
| M4 | Go-`deriveFlatFields` zurück auf nur `enabled` | `TestDeriveFlatFields_SlotFaelle` |
| M5 | Slot-Prüfung in `trip_briefing_due_at` entfernen (Master-Test davor bleibt) | `test_alarm_vorlauf_folgt_derselben_slot_regel` — und **`test_abend_aus_liefert_nur_morgen` bleibt dabei grün** (Beleg, dass der Wirkort einen eigenen Test braucht) |
| M6 | Slot-Prüfung **hinter** den `skip_next`-Verbrauch verschieben | `test_skip_next_bleibt_bei_abgeschaltetem_slot_und_datei_bleibt_vollstaendig` |
| M7 | Testbein (a) Kanäle: `send_telegram` in `_resolve_channel_flags` ignorieren; `premium_sms_allowed` durch `sms_allowed` ersetzen; `send_email`-Default kippen | `test_kanalmatrix_bedient_genau_die_eingeschalteten_kanaele`; `test_tier_gate_begrenzt_sms_und_premium_sms`; `test_fehlende_kanal_schluessel_folgen_den_editor_defaults` |
| M8 | Testbein (a) Form: `email_format` im Resolver hart auf `"full"` | `test_email_format_compact_und_full_kommen_wie_eingestellt_an` |
| M9 | Testbein (a) Zeiten: `NACHHOL_FENSTER_STUNDEN` 3→4 bzw. `stunde+1`; Vermerk-Filter in `_collect_due_trips` entfernen | `test_versandzeit_fenster_und_kein_doppelversand` |
| M10 | Testbein (a) Schwelle: globale Schwelle in `trip_report.py` nicht auf die kollabierte E-Mail-Liste übertragen; Gegenmutation: globale überschreibt Layout-eigene | `test_mail_pillen_schwelle_bei_eigenem_layout.py` (Vorrang-Fall); SMS-Schwelle aus `_dc_uncollapsed` auf kollabierte Liste umstellen ⇒ `test_globale_sms_schwelle_wirkt_in_allen_drei_sms_texten` |
| M11 | Testbein (a) Kaskade: `per_report`-Zweig in `get_metrics_for_channel` auf `per_channel` umleiten | `test_per_report_layout_gewinnt_am_abend_morgen_folgt_per_channel` |
| M12 | Testbein (b) Go: `NormalizeReportConfigSlotTimes`-Aufruf im PUT-Handler entfernen; `mergeConfigMap` durch Replace ersetzen; `s.WithUser` durch festen Nutzer `"default"` ersetzen | `TestReportConfigRoundtrip_KappungTeilPutUndPerReport`; unbekannter Schlüssel in `TestReportConfigRoundtrip_ZweiNutzer`; ebenda die Zwei-Nutzer-Zusicherung |
| M13 | Testbein (c) TS: `rightColumn.ts` zurück auf `=== true`; Editor-Startzustand mit Zeitbedingung zurück; Payload `enabled = morning_enabled && evening_enabled` | `report_slot_aktiv.test.ts` (Leser-Test bzw. Startzustand); `report_config_serialisierung_golden.test.ts` |
| M14 | Testbein (c)/(d) Verdrahtung: in `VersandTab.svelte` die herausgezogene Payload-Funktion nicht mehr aufrufen (`evening_enabled` aus `own` streichen) | **Nur** `kanal-an-aus-kette.staging.spec.ts` (AC-26) — der Bausteintest AC-22 bleibt grün, weil er die reine Funktion prüft, nicht die Verdrahtung. Der Adversary benennt das ausdrücklich; der E2E ist deshalb Pflicht-AC |
| M15 | Orakel-Gegenprobe: `erreichbare_kanaele` wieder E-Mail immer erwarten | `test_kanalmatrix_...` mit „E-Mail aus" rot (beweist, dass das Orakel nicht mehr E-Mail voraussetzt) |

## Test-Plan (AC → Testbein → Datei)

| AC | Bein | Datei / Test |
|---|---|---|
| AC-1, AC-2, AC-3, AC-4 | (a) Python-Scheduler | `tests/tdd/test_kanal_an_aus_kette.py` |
| AC-5, AC-21 | (a) Python Prädikat + Loader | `tests/tdd/test_report_config_slot_faelle.py` |
| AC-6, AC-7, AC-9, AC-10 | (a) Python-Scheduler | `tests/tdd/test_kanal_an_aus_kette.py` |
| AC-8, AC-11 | (a) Python-Scheduler + Orakel | `tests/tdd/test_kanal_an_aus_kette.py`, `einstellung_auslieferung_orakel.py` |
| AC-12, AC-13, AC-14 | (a) Python-Scheduler | `tests/tdd/test_kanal_an_aus_kette.py` |
| AC-15, AC-17 | (a) Python-Scheduler + Golden D | `tests/tdd/test_kanal_an_aus_kette.py`, `golden_d.json` |
| AC-16 | (a) Python-Renderer + Scheduler | `tests/tdd/test_mail_pillen_schwelle_bei_eigenem_layout.py` |
| AC-18, AC-19 | (b) Go-Handler, zwei Nutzer | `internal/handler/report_config_roundtrip_test.go` |
| AC-20 | (b) Go-Store | `internal/store/trip_slot_flat_fields_test.go` |
| AC-22 | (c) TS Serialisierung | `report_config_serialisierung_golden.test.ts` |
| AC-23, AC-24 | (c) TS Anzeige-Regel | `report_slot_aktiv.test.ts` |
| AC-25 | (c) TS SSR-Render | `versand_tab_defaults_gleich_auslieferung.test.ts` |
| AC-26 | (d) Staging-E2E + Validator | `frontend/e2e/kanal-an-aus-kette.staging.spec.ts`, `briefing_mail_validator.py` |
| AC-27 | Bestandstests angepasst | `trip_flat_fields_test.go`, `test_trip_flat_fields_dual_read.py` |
| AC-28 | Register-Prüfung | bestehende `test_ac18…`-Erweiterung |

**Testpolitik:** Testdateien nach Verhalten benannt, nicht nach Issue-Nummer. Kein `uv run pytest` ohne
benannte Testdateien. Kein Mock-Theater; Aufzeichner nur an der Transport-Naht; Prüfling relativ zur
Testdatei auflösen (nicht über den festen Hauptrepo-Pfad, sonst falsches Grün im Worktree). Kein echter
Versand an Produktiv-Empfänger. Das Sammel-Trip-Verbot („nur Test-Trip") gilt für den E2E: der Lauf
betrifft nur den Testnutzer dieser Spec.

## Known Limitations

- **Bestand nicht messbar:** Wie viele Prod-Trips ein gesetztes „Morgen/Abend aktiv = aus" tragen und
  ab dem Deploy weniger Briefings bekommen, ist nicht messbar (kein Lesezugriff auf `/var/lib/gregor`).
  Das Verhalten ist für genau diese Trips die gewollte Angleichung an ihre Anzeige; Trips ohne die
  Schalter bleiben unverändert (AC-3).
- **`channel_layouts_per_report`:** In der Auslieferung bewacht (AC-17) und beim Editor-Speichern
  erhalten (AC-19); der Editor zeigt es weiterhin nicht (B7 → S6+, bereits gebucht). Ob Prod-Trips das
  Feld tragen, ist nicht messbar.
- **`syncSendFlags`:** toter Pfad (kein Aufrufer übergibt `weatherChannels`), Premium-SMS-Lücke darin
  latent und ohne Wirkung; als Nebenbefund in #1199, nicht in dieser Scheibe angefasst.
- **Alarme, Ortsvergleich, B6:** siehe Deckungstabelle D14–D17 — nicht Teil von S3.
- Der Ortsvergleich-Zweig von `VersandTab` (Preset-Props) bleibt unverändert; die Trip-Regel wird nur im
  `route`-Zweig angewandt. Sie ändert die Compare-Semantik nicht, die bereits korrekt ist.
- Der E2E prüft eine Slot-Kombination (Abend aus); die Umkehrung und alle Kanal-Kombinationen liegen im
  schnellen, deterministischen Python-Kern (AC-2, AC-8).
- Zeitfelder werden im Editor nur als volle Stunden angeboten; Minuten in Altdaten werden von Go beim
  Schreiben/Lesen gekappt und von Python als Stunde gelesen (AC-14, AC-19) — es gibt keinen Weg zu
  halbstündigem Versand.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Anwendung von ADR-0050/0049/0051/0032, keine neue Entscheidung)
- **Rationale:** Die Slot-Semantik (Gesamtschalter Master, Einzel-Schalter je Slot, `None` ⇒ Rückfall)
  ist keine Kaskaden- oder Datenmodell-Entscheidung, sondern die Wiederherstellung der Semantik, die der
  Editor seit jeher zeigt und der Ortsvergleich (`compare_slot_scheduler.py`) bereits umsetzt; die frühere
  Behauptung „`enabled` ist der EINZIGE Schalter" (Loader-Kommentar aus #1250 S4) war eine Annahme ohne
  ADR (Grep über `docs/adr`: kein Treffer). Sie wird hier ersetzt und im Changelog festgehalten. Die
  beiden neuen Felder sind additiv und durch Read-Modify-Write geschützt (CLAUDE.md, BUG-DATALOSS-GR221).

## Changelog

- 2026-09-28: Initial spec created (Scheibe S3 von #2422). Aufbau nach `fix_2422_s2a_editor_gleich_gespeichert`.
  Verdikte zu allen sechs Verdachtsstellen per Code-Lektüre; zusätzlich zwei neue Befunde (N1 Orakel-Lücke
  bei `send_*`, N2 Anzeige-Rückfall bei Altdaten) und der Alarm-Vorlauf als zweiter Wirkort der Slot-Schalter.
  Fixes im selben Schnitt (kein Register-Eintrag): Einzel-Slot-Schalter (Python, Go, Frontend-Anzeige) und
  Mail-Pillen-Schwelle bei eigenem E-Mail-Layout. Vier Testbeine (Python-Scheduler, Go zwei Nutzer, TS,
  Staging-E2E), geteilte Fallzeilen-Tabelle gegen Auseinanderdriften der drei Fassungen. 28 ACs.
