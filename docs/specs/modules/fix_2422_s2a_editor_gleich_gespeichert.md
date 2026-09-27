---
entity_id: fix_2422_s2a_editor_gleich_gespeichert
type: bugfix
created: 2026-09-27
updated: 2026-09-27
status: draft
version: "1.0"
tags: [testing, invariante, editor, roundtrip, kanaele, orakel, fix]
workflow: fix-2422-s2-editor-gleich-gespeichert
---

# Fix #2422 (Scheibe S2a): Editor-Anzeige = gespeicherter Stand — Tests + Fix

## Approval

- [ ] Approved

## Purpose

Scheibe S1 von Issue #2422 hat geprüft, ob das im Trip **gespeicherte** JSON tatsächlich so
ausgeliefert wird, wie es dort steht. Scheibe S2a schließt die Strecke **davor**: Editor-Anzeige
→ Speichern → Auslieferung — für den No-Op-Fall („nichts geändert, nichts verschoben sich") UND
für echte Änderungen (vier Pflicht-Änderungsfälle), denn die eigentliche Beschwerde aus #2422
lautet „ich stelle X ein, Y kommt an", kein bloßes No-Op-Speichern.

**PO-Entscheid 2026-09-27:** Die erste Fassung dieser Spec wollte zwei bekannte Abweichungen —
**B9** (SMS-Reihenfolge wirkt nur bei Kaskadenquelle `per_channel`/`per_report`, nicht bei
`global`) und **K8** (per-Metrik-Felder wie `morning_enabled`/`evening_enabled` gehen beim
Editor-Speichern verloren) — nur sichtbar machen und befristet im Ausnahme-Register tolerieren.
Henning hat die Freigabe verweigert: „Warum soll ich eine befristete Abweichung OK heißen?" Diese
Scheibe ist deshalb von „nur Tests" zu **„Tests + Fix"** umgebaut: **B9 und K8 werden hier
produktiv behoben**, nicht mehr registriert. Golden C (dritter Beispiel-Trip: SMS/Telegram ohne
eigenes Kanal-Layout) bleibt der Auslöser dieser Fälle, zeigt nach dem Fix aber **korrektes**
Verhalten statt einer tolerierten Abweichung.

S2a prüft deshalb beides: „Speichern ohne Änderung" (die Kette bleibt stabil) UND „Speichern nach
einer echten Änderung" (die Änderung kommt tatsächlich an) — über vier definierte Änderungsfälle
(Metrik abwählen, Reihenfolge tauschen, Roh/Einfach umschalten, erstmalige SMS-Bearbeitung).

**Betroffene Kanäle des B9-Fixes, in einfacher Sprache:** Die SMS-Reihenfolge aus dem Editor wirkt
nicht nur für SMS selbst, sondern ebenso für **Premium-SMS** (Garmin inReach) und die
**Telegram-Kurzform** — diese drei Versandwege benutzen laut ADR-0049 denselben SMS-Text-Aufbau,
also wirkt eine Korrektur an einer Stelle automatisch für alle drei.

Außerhalb der beiden Fixes (B9, K8) ändert S2a **kein** weiteres sichtbares Verhalten der
Anwendung. Ein sichtbarer Editor-Hinweis zu B6 („Kanal-Layout kann nur abwählen, globales Maximum
nach ADR-0050") ist weiterhin **nicht** Teil von S2a, sondern des eigenständigen Folge-Tickets
#2438 — das jetzt **nur noch** B6 enthält, seit B9 hier produktiv gefixt wird.

## Deckungstabelle: Umfang S2a vs. Abgrenzung

| # | Thema | Ort | Begründung |
|---|---|---|---|
| K1 | Drittes Golden-Trip-JSON („Golden C"): SMS/Telegram ohne eigenes Kanal-Layout → Kaskadenquelle `global` | **S2a**, neues Golden + Aufnahme in die S1-Python-Matrix | Bisher hat kein Golden diesen Fall ausgelöst (S1-Kontext, Befund A) |
| K2 | Invariante „TS-Helferkette lädt Golden → Anzeige je Kanal = Erwartung" | **S2a**, TS-Kern | Zugesagte Invariante aus dem S1-Schnittplan (`:47/:60`) |
| K3 | Invariante „TS-Helferkette speichert ohne Änderung → Stand bleibt gleich (gegen eingefrorene `nach_speichern`-Datei; Python prüft zusätzlich die Auslieferungs-Gleichheit)" | **S2a**, TS-Kern + Python-Kern | Kern des S2-Auftrags |
| K4 | Invariante „Go-PUT-Roundtrip (beide Pfade) erhält `channel_layouts`/`display_config.metrics`" | **S2a**, Go-Kern | Kein Go-Test prüft das heute (S1-Kontext `:31`) |
| K5 | Invariante „Editor-Anzeige = gespeicherter Stand" end-to-end im echten Browser | **S2a**, E2E (Staging) | SSR-Helferkette beweist die echte Svelte-Verdrahtung nicht (Memory „Bausteintest beweist die Verdrahtung nicht") |
| K6 | B9 (SMS-Nutzerreihenfolge im Editor sichtbar bei Quelle `global`, ausgeliefert wurde bisher die feste Standardreihenfolge) | **S2a, produktiver Fix** (Python-Core `trip_report.py`, löst DEC-2 aus `fix_1677_sms_reihenfolge.md` ab — PO-Entscheid 2026-09-27) | Anzeige und Auslieferung sind nach dem Fix identisch — kein Editor-Hinweis mehr nötig für diesen Teil, kein Register-Eintrag |
| K7 | B6 (Kanal-Layout kann nur abwählen, globales Maximum nach ADR-0050) im Editor sichtbar machen | **S2b = #2438** (jetzt einziger Inhalt von #2438, seit B9 in S2a gefixt ist) | UI-Änderung am geteilten Editor braucht eigene Wortlaut-Abnahme, Fresh-Eyes-Blick, Pendant-Prüfung — nicht Teil dieser Scheibe |
| K8 | Verlust von per-Metrik `morning_enabled`/`evening_enabled` (und weiterer, dem Frontend unbekannter Felder) beim Editor-Speichern | **S2a, produktiver Fix** (Frontend, Read-Modify-Write statt Replace, CLAUDE.md-Regel #102) | PO-Entscheid 2026-09-27: wird hier gefixt, unabhängig vom fehlenden konkreten Bestandsnachweis (siehe Datenlage-Abschnitt) — kein Register-Eintrag |
| K9 | Verlust von `format_mode` beim Editor-Speichern | **Kein Register-Eintrag, kein eigener Fix nötig** — automatisch mitgeprüft durch die Python-Äquivalenz-Zusicherung (AC-5) | Funktional folgenlos (jede Katalog-Metrik hat höchstens einen Nicht-Roh-Modus, `use_friendly_format` legt ihn fest) |
| K10 | Ortsvergleich (`compareEditorSave.ts`, `channel_active_metrics`, `telegram_style` in `display_config`) | **S5** | Eigener Speicherweg, eigenes Datenmodell — siehe Begründung unten |
| K11 | Änderungspfad „ich stelle X ein, Y kommt an": vier Pflicht-Änderungsfälle (Metrik abwählen, Reihenfolge tauschen, Roh/Einfach umschalten, SMS-Reiter bei Kaskadenquelle `global`) durch TS-, Python- und E2E-Kern | **S2a**, alle drei Kerne + E2E | Das ist die eigentliche Nutzerbeschwerde aus #2422 (Änderung, kein No-Op) — gehört strukturell in dieselbe Kette wie K2–K5 und darf nicht nach S3 verschoben werden |
| K12 | Ablösung DEC-2 aus `fix_1677_sms_reihenfolge.md` (Byte-Identität der SMS-/Kurzform-Ausgabe bei Kaskadenquelle `global`) inkl. Anpassung der abhängigen Tests | **S2a** | Direkte Folge des B9-Fixes — eine dokumentierte Entscheidung wird nicht still rückgängig gemacht, sondern hier als Ablösung festgehalten und die abhängigen Tests bewusst angepasst |

## Außerhalb des Umfangs → Unter-Issue

| Ziel | Inhalt |
|---|---|
| **#2438 (S2b)** | NUR NOCH B6-Sichtbarkeit im Editor: Hinweistext für „Kanal-Layout kann nur abwählen, globales Maximum nach ADR-0050". B9 ist mit dieser Scheibe (S2a) produktiv erledigt und entfällt aus #2438s Scope — Issue-Beschreibung bei Bedarf anpassen. UI-Änderung am geteilten Trip-/Vergleichs-Editor mit eigenem Produktentscheid, eigenem Wortlaut, Fresh-Eyes-Inspektion und Pendant-Prüfung (`context="route"|"vergleich"`). |
| **S3** | Kette Kanal an/aus, Versandzeiten, `email_format`, `sms_threshold`, `bucket`/`channel_layouts_per_report` (K8 ist bereits in S2a produktiv gefixt und entfällt hier). |
| **S4** | Kette Alarm-Familie (Schwellen, Radar/Regen, amtliche Warnungen) JSON → alle vier Kanäle. |
| **S5** | Kette Ortsvergleich `channel_active_metrics` + Kanalwahl, eigener Speicherweg `compareEditorSave.ts`. |
| **S6+** | B1/B2/B3/B5-Fixes aus S1 (unverändert). |

Diese Spec enthält bewusst **keine offene PO-Frage**. Der PO hat die B9-/K8-Fixes am 2026-09-27
ausdrücklich freigegeben (siehe Purpose); der Schnitt S2a/S2b (jetzt nur noch B6 in #2438) und die
Behandlung von K9 sind Entscheidungen dieser Spec, keine Rückfragen.

## Source

- **File (Python-Kern, Test):** `tests/tdd/test_einstellung_gleich_auslieferung.py` (erweitert um
  Golden C), `tests/helpers/einstellung_auslieferung_orakel.py` (Erwartungsdatei-Export; **keine**
  Register-Erweiterung für B9/K8/K9, siehe „Register bleibt unverändert" unten)
- **File (Python-Core, produktiv — B9-Fix):** `src/output/renderers/trip_report.py:337–346`
  (Aktivierungs-Gate `_sms_cascade_source in ("per_report", "per_channel")` entfällt)
- **File (Frontend, produktiv — K8-Fix):** `frontend/src/lib/components/trip-detail/metricsEditor.ts:336`
  (`buildWeatherConfigMetrics`), ggf. `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
  und `frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts` (Read-Modify-Write
  statt Replace)
- **File (TS-Kern, Test):** `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/`
  (neue Testdatei(en), Vorbild `channelMetricLayouts.test.ts`)
- **File (Go-Kern, Test):** `internal/handler/` (neue `_test.go`, Vorbild `bug_601_roundtrip_test.go`,
  `config_merge_structure_test.go`) — **kein** Go-Produktivcode betroffen
- **File (E2E):** `frontend/e2e/weather-metrics-tab-autosave.spec.ts` (erweitert) oder neue
  `*.staging.spec.ts`, in `ci_e2e_specs.txt` aufgenommen
- **File (#1677-Testanpassung):** `tests/golden/sms/*.txt` und der zugehörige #1677-Byte-Identitäts-
  Test (Name aus `/40`/`/50`) — angepasst, siehe K12/AC-13
- **Identifier:** Helferkette `bucketsToColumns` → `channelOverrideFromMetrics` →
  `splitChannelMetricsForDisplay` → `buildWeatherConfigMetrics` → `mergeAllChannelLayoutsForSave`
  (Anzeige/Speichern); `erwartete_kaskade` (Python-Orakel, unverändert Wahrheit);
  `cascade_source_for_channel` (Python, `src/app/models.py`, bestehend aus #1677)

> **Schicht-Hinweis:** Diese Spec berührt **alle drei** Schichten (Frontend/TS, Go-API,
> Python-Core). Anders als in der ursprünglichen „nur Tests"-Fassung ändert S2a jetzt **bewusst**
> Produktivcode in **zwei** Schichten:
> - **Python-Core** (`trip_report.py:337–346`): B9-Fix — das Aktivierungs-Gate aus DEC-2
>   (`fix_1677_sms_reihenfolge.md`) entfällt, `position` wird immer aus der SMS-Kaskade abgeleitet,
>   unabhängig von der Kaskadenquelle.
> - **Frontend** (`metricsEditor.ts`, ggf. `WeatherMetricsTab.svelte`/`channelMetricLayouts.ts`):
>   K8-Fix — Read-Modify-Write statt Replace beim Bau der Speichern-Payload.
> Go-Produktivcode bleibt unverändert. Zusätzlich weiterhin möglich: ein verhaltensgleiches
> Herauslösen von Lade-/Speicherlogik in eine reine Funktion, falls für die TS-Tests nötig.

## Estimated Scope

- **LoC:** produktiv ~150–290 (B9-Fix in `trip_report.py` ~10–25 LoC: Gate entfernen,
  Kommentare/Docstring nachziehen; K8-Fix Read-Modify-Write in `metricsEditor.ts`/
  `WeatherMetricsTab.svelte`/`channelMetricLayouts.ts` ~140–260 LoC, weil für jede Metrik und jeden
  Kanal-Layout-Eintrag der Original-Bestand als Basis übernommen und nur die dem Frontend bekannten
  Felder überschrieben werden müssen, statt den Eintrag komplett neu zu bauen). **Liegt
  voraussichtlich über dem 250-LoC-Workflow-Limit** — vor `/50` `workflow.py set-field
  loc_limit_override 500` setzen (CLAUDE.md-Regel „LoC-Limit 250/Workflow"). Test ~850–1150
  (Golden C + Erwartungs-/Nach-Speichern-/Nach-Änderung-Dateien + TS-Kern + Go-Kern +
  Python-Matrix-Erweiterung + Drift-Test + Änderungspfad-Tests + E2E + #1677-Testanpassung).
- **Files:** ~18–21 neu/geändert (Golden C, 3 Anzeige-Erwartungsdateien, 3 Nach-Speichern-Dateien,
  8 Nach-Änderung-Dateien, Drift-Test, Python-Äquivalenz-/Änderungspfad-Tests, TS-Testdatei(en),
  Go-Testdatei, E2E-Erweiterung, `trip_report.py` (produktiv), `metricsEditor.ts` +
  `WeatherMetricsTab.svelte`/`channelMetricLayouts.ts` (produktiv), `tests/golden/sms/*.txt` +
  zugehöriger #1677-Test (angepasst), ggf. eine herausgelöste reine TS-Funktion)
- **Effort:** high — echte Produktivcode-Änderung in zwei Schichten (nicht mehr nur Tests), Kette
  über drei Schichten plus E2E für No-Op- UND Änderungspfad, plus Anpassung einer abhängigen,
  bereits abgeschlossenen Scheibe (#1677 DEC-2)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fix_2422_einstellung_gleich_auslieferung` (S1) | Spec | Liefert Golden A/B, Orakel-Register-Mechanik, `erwartete_kaskade` als wiederverwendete Wahrheit |
| `fix_1677_sms_reihenfolge` | Spec | DEC-2 (Aktivierungs-Gate, Byte-Identität bei `global`) wird durch den B9-Fix dieser Scheibe abgelöst — siehe „B9-Fix" unten |
| `tests/golden/sms/*.txt` + zugehöriger #1677-Test | Testvorlage | Byte-Identitäts-Zusicherung bei `global`, wird angepasst (AC-13) |
| ADR-0050 (Metrik-Kaskade) | ADR | Begründet B6 (globales Maximum) und die Kaskadenquellen (`per_channel`/`per_report`/`global`); **nicht** durch den B9-Fix betroffen — Regel 5 „Reihenfolge je Kanal einstellbar" wird eher gestärkt |
| ADR-0049 (Premium-SMS teilt SMS) | ADR | SMS-Kanal-Reiter deckt Premium-SMS mit ab, kein eigener E2E-Reiter nötig; B9-Fix gilt für SMS, Premium-SMS und Telegram-Kurzform gleichermaßen |
| ADR-0032 (geteilte Tab-Editoren) | ADR | Begründet, warum die getestete Helferkette Trip UND Vergleich bedient, S2a aber keinen Compare-Baustein hinzufügt |
| ADR-0053 (kanal-eigene Auswahl im Vergleich) | ADR | Begründet die Abgrenzung K10 (Ortsvergleich = eigener Datenpfad, S5) |
| `src/output/renderers/trip_report.py` | Modul | B9-Fix-Ort: `_sms_position_by_metric`-Gate entfällt |
| `frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts` | Modul | `channelOverrideFromMetrics`, `splitChannelMetricsForDisplay`, `mergeAllChannelLayoutsForSave` — echte Helfer, ggf. K8-Fix-Ort für Kanal-Layout-Einträge |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Modul | `buildWeatherConfigMetrics` — K8-Fix-Ort für `display_config.metrics` |
| `internal/handler/weather_config.go`, `internal/handler/trip.go`, `internal/handler/config_merge.go` | Modul | PUT-Pfade und flacher Merge, den das Go-Bein prüft (unverändert) |
| `tests/helpers/einstellung_auslieferung_orakel.py` (`erwartete_kaskade`, `AusnahmeEintrag`, `KANAELE`) | Modul | Bleibt die einzige Wahrheit; wird **nicht** nach TS/Go portiert |
| `tests/tdd/_einstellung_auslieferung_fixtures.py` (`golden_dict`, `frisches_profil`) | Modul | Golden-Loader, wird um Golden C erweitert |
| `internal/store` Testhelfer `newTestStore`/`seedTrip` (`trip_write_test.go`) | Testvorlage | Zwei-Nutzer-Aufbau für das Go-Bein |
| `frontend/e2e/weather-metrics-tab-autosave.spec.ts` | Testvorlage | Basis für das E2E-Bein (createTrip/fetchTrip/GET) |
| Issue #2438 (S2b) | Issue | Nimmt K7 (B6-Editor-Sichtbarkeit) aus dieser Spec heraus |

## Implementation Details

> **Implementierungsreihenfolge (PFLICHT für `/40`/`/50`):** Die B9-/K8-Fixes werden **vor** dem
> Einfrieren der Erwartungs-/Nach-Speichern-/Nach-Änderung-Dateien umgesetzt, damit diese Dateien
> den **korrigierten**, nicht den alten fehlerhaften Stand zeigen. Reihenfolge: (1) B9-Fix in
> `trip_report.py`, (2) K8-Fix im Frontend, (3) #1677-Testanpassung, (4) erst danach Golden C +
> alle eingefrorenen Dateien erzeugen.

### B9-Fix: SMS-Reihenfolge gilt auch bei Kaskadenquelle `global` (PO-Entscheid 2026-09-27, löst DEC-2 aus `fix_1677_sms_reihenfolge.md` ab)

Der PO hat entschieden: Die SMS-Nutzerposition aus dem Editor gilt **immer** — auch wenn kein
eigenes `channel_layouts.sms`/`channel_layouts_per_report[...].sms` gespeichert ist
(Kaskadenquelle `global`). Anzeige und Auslieferung sind dann identisch, wie bei jeder anderen
Kaskadenquelle auch.

- **Fundstelle:** `src/output/renderers/trip_report.py:337–346`. Das bestehende Aktivierungs-Gate
  ```
  _sms_position_by_metric = (
      {m.metric_id: i for i, m in enumerate(_sms_metrics_ordered)}
      if _sms_cascade_source in ("per_report", "per_channel")
      else {}
  )
  ```
  entfällt — `_sms_position_by_metric` wird **immer** aus `_sms_metrics_ordered` abgeleitet, auch
  wenn `_sms_cascade_source == "global"`.
- **Betroffene Kanäle:** SMS, Premium-SMS und Telegram-Kurzform (teilen laut ADR-0049 denselben
  `sms_text`/dieselbe `channel_layouts.sms`-Quelle, `notification_service.py:566,596,653,672`).
- **Ablösung DEC-2 (`fix_1677_sms_reihenfolge.md`):** Jene Spec hatte das Gate bewusst so gesetzt,
  dass bei `global` **keine** `position` gesetzt wird, um Byte-Identität zur alten
  `POSITIONAL`-Reihenfolge zu garantieren (dortige AC-2). Diese Spec dokumentiert die Ablösung:
  `fix_1677_sms_reihenfolge.md` bleibt als historisches Dokument bestehen (kein Rückbau der Datei
  nötig), DEC-2 gilt dort ab dieser Scheibe als **abgelöst durch fix_2422_s2a** — der Verweis in
  dieser Spec plus Changelog-Eintrag genügt, **kein neues ADR** nötig (ADR-0050 ist nicht
  betroffen; es handelt sich nicht um eine Kaskaden-/Datenmodell-Entscheidung, sondern um die
  Aktivierungsbedingung einer bereits bestehenden Kaskaden-Ableitung).
- **ADR-0050 unberührt, Regel 5 gestärkt:** Regel 5 „Reihenfolge je Kanal einstellbar" wird durch
  den Fix eher gestärkt — die Nutzer-Reihenfolge wirkt jetzt **ausnahmslos**, unabhängig von der
  Kaskadenebene, statt nur bei zwei von drei Ebenen.
- **Ausdrücklich gewollte Verhaltensänderung:** Bei Trips, deren SMS-Reiter noch nie bearbeitet
  wurde (kein eigenes Layout gespeichert, Kaskadenquelle `global`), ändert sich die ausgelieferte
  SMS-/Kurzform-/Premium-Reihenfolge **einmalig** von der bisherigen festen Standardreihenfolge
  (`POSITIONAL`) auf die im Editor sichtbare (globale) Reihenfolge. Das ist eine gewollte,
  PO-freigegebene Verhaltensänderung — kein Bug, kein Regressions-Befund.
- **Auswirkung auf #1677:** Die dortige AC-2 sichert exakt das Gegenteil zu (Byte-Identität bei
  `global`) — diese Zusicherung entfällt bewusst. Die zugehörigen Tests
  (`tests/golden/sms/*.txt`, Byte-für-Byte-Vergleich für den `global`-Fall) werden angepasst:
  entweder werden die Goldens für den `global`-Fall auf die neue, positionsbasierte Reihenfolge
  aktualisiert, oder der betroffene Testfall wird umgewidmet und ein neuer Test sichert zu, dass
  `position` bei `global` **genauso** wirkt wie bei `per_channel`/`per_report`. Das ist Teil dieser
  Scheibe (siehe AC-13), keine unangekündigte Nebenfolge.

### K8-Fix: Read-Modify-Write statt Replace beim Editor-Speichern

CLAUDE.md-Pflicht „Read-Modify-Write mit Merge, niemals Replace" (BUG-DATALOSS-GR221, #102) gilt
für `display_config.metrics`-Einträge und `channel_layouts`-Einträge genauso wie für andere
Schema-Bereiche.

- **Bisheriger Zustand:** `buildWeatherConfigMetrics` (`metricsEditor.ts:336`) baute jeden
  Metrik-Eintrag komplett neu aus den dem Frontend bekannten Feldern (`metric_id`, `enabled`,
  `use_friendly_format`, `horizons`, `bucket`, `order`). Jedes andere, dem Frontend unbekannte Feld
  eines Bestands-Eintrags (`morning_enabled`, `evening_enabled`, `format_mode`, künftige Felder)
  ging beim Speichern verloren (Replace statt Merge).
- **Fix:** Beim Bau der Speichern-Payload wird für jede Metrik der **Original-Eintrag** aus dem
  geladenen Trip als Basis genommen; nur die vom Editor tatsächlich veränderten, dem Frontend
  bekannten Felder werden überschrieben (sinngemäß `{...originalEntry, metric_id, enabled,
  use_friendly_format, horizons, bucket, order}`), alle anderen Felder wandern unverändert mit.
  Derselbe Grundsatz gilt für Kanal-Layout-Einträge in `channel_layouts`, soweit sie zusätzliche,
  dem Frontend unbekannte Felder tragen.
- **Zusicherung:** Golden C trägt nach „Speichern ohne Änderung" exakt dieselben
  `morning_enabled`/`evening_enabled`/`format_mode`-Werte wie vorher — **ohne Ausnahme, ohne
  Register-Eintrag** (siehe AC-4/AC-7).

### Register bleibt unverändert für S1-Befunde — keine neuen Einträge in S2a

Golden C löste historisch die Befunde B9 und K8 aus — beide werden in dieser Scheibe **produktiv
gefixt** (siehe oben), nicht mehr über einen befristeten Register-Eintrag toleriert. K9
(`format_mode`) war nie ein Register-Fall und bleibt es — er wird automatisch von der
Python-Äquivalenz-Zusicherung (AC-5) mitgeprüft, weil der Verlust von `format_mode` die
Auslieferungs-Projektion nachweislich nicht verschiebt (`use_friendly_format` legt den Modus
eindeutig fest).

Die Register-Mechanik selbst — aus S1 für B1/B2/B3/B5 — bleibt **unverändert** bestehen und wird
von dieser Scheibe **nicht** angefasst.

**Neue Regel für diese Scheibe:** Die Umsetzung darf **keine neuen** Register-Einträge anlegen.
Findet der Entwickler in `/40`/`/50` eine weitere, bisher unbekannte Abweichung innerhalb dieser
Kette (Editor-Anzeige/Speichern/Auslieferung für die drei Kern-Beine + E2E + Änderungspfad), wird
sie — sofern im Rahmen dieser Kette lösbar — **sofort produktiv mitgefixt**. Liegt sie außerhalb
des Rahmens dieser Kette (z. B. Alarm-Familie, Ortsvergleich, `bucket`/`channel_layouts_per_report`),
**stoppt der Entwickler und legt den Befund dem PO vor**, statt ihn befristet ins Register zu
schreiben oder stillschweigend zu übergehen.

### Golden C (neu: `tests/fixtures/einstellung_auslieferung/golden_c.json`)

Pflicht-Eigenschaften (Implementierungs-Constraint für `/40`, analog zu S1s P1–P8):

- **G1 (Kaskadenquelle `global` auslösen):** SMS **und** Telegram haben in
  `display_config.channel_layouts` **kein** eigenes Layout (Schlüssel fehlt oder ist `null`) —
  einzig E-Mail behält ein eigenes Layout, damit die Golden weiterhin ein `per_channel`-Beispiel
  im selben Fixture zeigt. Löst die Kaskadenquelle `global` aus — nach dem B9-Fix liefert SMS/
  Kurzform/Premium in diesem Fall dieselbe Reihenfolge, die der Editor zeigt (statt vorher der
  festen Standardreihenfolge).
- **G2 (Umnummerierungs-sensitive globale Reihenfolge):** Die globalen `bucket:secondary`-Metriken
  in `display_config.metrics` stehen in einer Reihenfolge, die bei der `secondary→primary`-Migration
  (#587, ausgelöst beim Laden in `WeatherMetricsTab.svelte:460–520`) eine andere `order`-Nummer
  bekäme, wenn die Migration die Reihenfolge nicht erhält — Fang für eine Regression an genau
  dieser Stelle.
- **G3 (`format_mode` vorhanden):** Mindestens eine Metrik mit `has_friendly_format=True` trägt
  `format_mode` im globalen `display_config.metrics`-Eintrag — deckt K9 ab (funktional folgenlos,
  siehe oben).
- **G4 (per-Metrik `morning_enabled`/`evening_enabled` gesetzt, nicht `null`):** Mindestens eine
  Metrik in `display_config.metrics` trägt `morning_enabled=false` oder `evening_enabled=false`
  (ein echter, von `null` verschiedener Wert) — deckt den K8-Fix ab. Golden C ist damit die einzige
  der drei Goldens, die diesen Fall überhaupt zeigt (A/B tragen laut S1-Kontext keine
  per-Metrik-Werte).

Golden C wird in die S1-Python-Matrix (`tests/tdd/test_einstellung_gleich_auslieferung.py`,
`_einstellung_auslieferung_fixtures.py::golden_dict`) als drittes Golden aufgenommen — die
Matrix-Iteration läuft für A, B **und** C.

### Datenlage morning_enabled/evening_enabled (gemessen 2026-09-27)

Prod-Trips unter `/var/lib/gregor` sind für den Nutzer `hem` nicht lesbar
(Memory „Staging-Datenbestand ist für hem NICHT lesbar" gilt analog für Prod) →
**NOT_MEASURABLE**. Der lokal verfügbare Bestand
(`data/users/default/trips/gr221-mallorca.json`) trägt das Feld nur mit `null` (= „erben von
global") — der Verlust von `null` wäre folgenlos gewesen, weil es beim erneuten Laden wieder als
`null` (erben) ankäme. Es gibt **keinen Beleg** für einen Bestandstrip mit einem echten
Nicht-`null`-Wert in diesem Feld. **Trotzdem wird der Feldverlust in dieser Scheibe gefixt
(PO-Entscheid 2026-09-27):** Die CLAUDE.md-Pflicht „Read-Modify-Write, niemals Replace" gilt
unabhängig davon, ob ein konkreter Bestandsschaden aktuell nachweisbar ist — das Fehlen eines
Nachweises ist kein Grund, eine bekannte Replace-statt-Merge-Lücke offen zu lassen.

### Wahrheit bleibt das Python-Orakel

`erwartete_kaskade` (`tests/helpers/einstellung_auslieferung_orakel.py`) wird **nicht** nach
TypeScript oder Go portiert — jede Portierung wäre eine zweite, potenziell abweichende
Implementierung derselben Kaskadenregel und würde die Unabhängigkeitsgarantie aus S1 (AC-3)
unterlaufen. Stattdessen erzeugt ein kleines, in `/50` geschriebenes Skript aus dem Python-Orakel
für Golden A, B und C je eine **eingefrorene Erwartungsdatei**
(`tests/fixtures/einstellung_auslieferung/erwartung_golden_a.json`,
`erwartung_golden_b.json`, `erwartung_golden_c.json` — je Kanal Auswahl, Reihenfolge,
Roh/Einfach-Modus). Diese Dateien sind die Wahrheit für das TS- und das E2E-Bein und werden **nach**
den B9-/K8-Fixes erzeugt (siehe Implementierungsreihenfolge oben) — `erwartung_golden_c.json` zeigt
für SMS also bereits die korrigierte, positionsbasierte Reihenfolge.

Ein **Drift-Test im Python-Kern** (pytest, Commit-Gate,
`tests/test_erwartungsdatei_drift_einstellung_gleich_auslieferung.py`) prüft bei jedem Lauf, dass
jede eingefrorene Erwartungsdatei exakt dem **aktuellen** Ergebnis von `erwartete_kaskade` für das
jeweilige Golden entspricht. Ändert sich die Orakel-Logik (z. B. durch einen S1-Folgefix), ohne
dass die Erwartungsdatei neu erzeugt wird, wird dieser Drift-Test rot — die Erwartungsdateien
können nie unbemerkt veralten.

### Zweigliedrige, an beiden Enden bewachte Kette für „Speichern ohne Änderung"

TypeScript kann `erwartete_kaskade` nicht selbst berechnen (das Orakel wird bewusst nicht nach TS
portiert, siehe oben) — ein TS-Test kann also nicht direkt gegen „die Orakel-Projektion" prüfen,
ob Speichern die Auslieferung verändert. Diese Zusicherung wird deshalb in zwei Hälften geteilt,
die über eine gemeinsame, in `/50` einmalig erzeugte und eingefrorene Datei verbunden sind:

- **`tests/fixtures/einstellung_auslieferung/nach_speichern_golden_a.json`** (analog `_b`, `_c`):
  der vollständige Trip-Zustand, den die TS-Helferkette erzeugt, wenn ein Golden geladen und ohne
  Änderung gespeichert wird (Payload aus `buildWeatherConfigMetrics`/`mergeAllChannelLayoutsForSave`
  flach in den Golden-Ausgangszustand gemergt, analog `config_merge.go`). Diese Datei wird einmal
  aus der TS-Helferkette selbst erzeugt und dann eingefroren — sie ist kein Orakel-Ergebnis,
  sondern ein roher, geprüfter Trip-Zustand.
- **(a) TS-Kern:** Der TS-Test baut denselben Stand erneut (deterministisch, dieselbe Helferkette)
  und vergleicht ihn strukturell gegen die eingefrorene `nach_speichern_<golden>.json`. Weicht der
  TS-Output ab, wird der Test rot — das fängt jede Regression in der TS-Helferkette selbst
  (Struktur-Vergleich, keine Orakel-Logik nötig).
- **(b) Python-Kern:** `erwartete_kaskade(nach_speichern_<golden>) == erwartete_kaskade(golden)`
  — **ohne Ausnahme**. Das ist die eigentliche fachliche Zusicherung „Speichern ohne Änderung
  verändert die Auslieferung nicht" — sie läuft dort, wo das Orakel tatsächlich zu Hause ist, und
  vergleicht die eingefrorene `nach_speichern`-Datei gegen das Original-Golden.
- **(c) E2E:** `GET /api/trips/{id}` nach echtem Speichern im Browser wird auf den relevanten
  Feldern (`display_config.metrics`, `channel_layouts`, ggf. `channel_layouts_per_report`) gegen
  `nach_speichern_golden_c.json` verglichen — das schließt die echte Verdrahtung (Svelte-Komponente,
  Go-Endpunkt) an die bewachte Kette (a)+(b) an.

Die Anzeige-Erwartungsdateien (`erwartung_golden_*.json`, s. o.) bleiben davon unberührt: Sie
enthalten die Orakel-Projektion (Auswahl/Reihenfolge/Roh-Einfach-Modus je Kanal) direkt als reine
Daten (Listen/Strings), die TS ohne jede Orakel-Logik lesen und mit der eigenen, unabhängig
berechneten Anzeige vergleichen kann (AC-3) — TS berechnet dabei keine Kaskade nach, es vergleicht
nur zwei Datenstrukturen.

### Drei Beine + E2E

**TS-Kern** (`node --test`, **kein** Vitest — Memory „Kein Vitest, es läuft node --test"; Ablage
`frontend/src/lib/components/shared/weather-metrics-tab/__tests__/`):

1. Golden A, B, C laden (echte Helfer `bucketsToColumns`,
   `channelOverrideFromMetrics`, `splitChannelMetricsForDisplay` — kein Mock).
2. Angezeigte Auswahl/Reihenfolge je Kanal (email, telegram, sms — inkl. B6-Clip nach ADR-0050)
   gegen die passende Erwartungsdatei vergleichen — **ohne Ausnahme**, da B9 gefixt ist.
3. Speichern ohne Änderung simulieren (`buildWeatherConfigMetrics`,
   `mergeAllChannelLayoutsForSave`), Ergebnis flach mergen (wie `config_merge.go:7–19`), den
   resultierenden Stand strukturell gegen die eingefrorene `nach_speichern_<golden>.json`
   vergleichen (kein Orakel-Aufruf in TS, siehe Abschnitt „Zweigliedrige ... Kette" oben) —
   **einschließlich** aller dem Frontend unbekannten Felder (K8-Fix).
4. Payload-Vollständigkeit: Der beim Speichern gebaute `channel_layouts`-Block enthält **alle**
   drei Kanäle (email/telegram/sms), auch wenn nur einer bearbeitet wurde — das ist die
   Zusicherung, die die Go-seitige Merge-Lücke (flacher Merge, K10-Nachbarbefund) kompensiert.
5. Feld-Erhalt (K8-Fix): Für jede Metrik in Golden C mit `morning_enabled`/`evening_enabled`/
   `format_mode` prüft ein Test, dass diese Werte nach Speichern-ohne-Änderung **unverändert und
   ohne Ausnahme** im gebauten Payload stehen (siehe AC-7).

Dieses Bein prüft ausdrücklich **nur** die Helferkette. Es beweist **nicht**, dass
`WeatherMetricsTab.svelte` (`initFromTrip`/`buildWeatherPayload`) diese Helfer tatsächlich in
dieser Reihenfolge mit diesen Daten aufruft — dafür ist das E2E-Bein Pflicht (Memory
„Bausteintest beweist die Verdrahtung nicht").

**Go-Kern** (`internal/handler/…_test.go`, Vorbild `bug_601_roundtrip_test.go`,
`config_merge_structure_test.go`):

6. Roundtrip **beider** PUT-Pfade — `PUT /api/trips/{id}/weather-config` und
   `PUT /api/trips/{id}` — mit den Golden-Bodys (Golden per `os.ReadFile` relativ zur Testdatei):
   PUT senden, GET danach lesen, `channel_layouts` und `display_config.metrics` sind exakt der
   gesendete Stand.
7. **Zwei verschiedene Nutzer** über `s.WithUser`: Nutzer B sieht und ändert Nutzer As Trip
   **nicht** (Cross-User-Isolation, CLAUDE.md-Pflicht bei jedem nutzerbezogenen Endpoint-Test).
8. Kein Test schreibt „ein Teil-PUT von `channel_layouts` löscht die übrigen Kanäle" als
   **gewollt** fest — diese Vollständigkeits-Zusicherung liegt beim Frontend (Punkt 4 oben). Der
   Go-Test beschreibt den flachen Merge nur als **Ist-Verhalten** des geprüften Pfads, nicht als
   Anforderung an einen Teil-PUT.

**Python-Kern:** Golden C in der S1-Matrix (siehe oben) + Drift-Test der Erwartungsdateien.

**E2E** (Playwright, Staging-Spec; Basis `frontend/e2e/weather-metrics-tab-autosave.spec.ts`;
Aufnahme in `ci_e2e_specs.txt` bzw. eigene `*.staging.spec.ts`):

9. Golden-Trip (aus Golden C abgeleitet) über die Test-API anlegen → im echten Editor je
   Kanal-Reiter (email/telegram/sms — Premium-SMS teilt den SMS-Reiter, ADR-0049) die angezeigte
   Auswahl/Reihenfolge gegen die Erwartungsdatei prüfen — **ohne Ausnahme**: die SMS-Zelle zeigt
   die Nutzerreihenfolge, und genau diese wird nach dem B9-Fix auch ausgeliefert.
10. Speichern ohne Änderung auslösen (Autosave oder expliziter Speichern-Klick, je nach
    bestehendem Editor-Verhalten) → `GET /api/trips/{id}` danach = eingefrorene
    `nach_speichern_golden_c.json` auf den relevanten Feldern (`display_config.metrics`,
    `channel_layouts`, ggf. `channel_layouts_per_report`), **einschließlich**
    `morning_enabled`/`evening_enabled` je Metrik (K8-Fix).

Dieses Bein bewacht die tatsächliche Verdrahtung und ist Pflicht-AC, nicht optional.

### Vierter Baustein: Änderungspfad „Ich stelle X ein, Y kommt an" (Fälle 1–4)

Die bisherigen Beine testen ausschließlich „Speichern **ohne** Änderung" (No-Op). Die eigentliche
Beschwerde aus Issue #2422 lautet aber „ich stelle X ein, Y kommt an" — eine **Änderung**, kein
No-Op. Diese Lücke gehört strukturell in dieselbe Kette wie „Speichern ohne Änderung" und wird
**nicht** nach S3 verschoben.

Vier Pflicht-Änderungsfälle (Implementierungs-Constraint für `/40`, analog zu den
Golden-Pflichteigenschaften G1–G4 und S1s P1–P8 — die konkrete Metrik-/Positionswahl je Fall ist
Implementierungsdetail von `/40`, keine Spec-Vorgabe):

- **Fall 1 (Metrik abwählen):** Ausgangspunkt Golden A. In einem Kanal-Reiter mit eigenem Layout
  (email oder telegram) wird eine aktiv gewählte Metrik über die echte Anzeige-/Speicher-Helferkette
  abgewählt.
- **Fall 2 (Reihenfolge tauschen):** Ausgangspunkt Golden A. In einem Kanal-Reiter mit eigenem
  Layout tauschen zwei aktive Metriken ihre Position.
- **Fall 3 (Roh/Einfach umschalten):** Ausgangspunkt Golden A. Eine Metrik mit
  `has_friendly_format=True` wechselt in einem Kanal-Reiter den Roh/Einfach-Modus.
- **Fall 4 (SMS-Reiter: erstmalige Bearbeitung, Kaskadenquelle wechselt `global` → `per_channel`):**
  Ausgangspunkt Golden C (SMS-Reiter bislang nie bearbeitet, `channelBuckets.sms === null`). Der
  Nutzer wählt im SMS-Reiter eine Metrik ab **UND** tauscht zwei Metriken (dieselbe Bedienung wie
  im E2E-Bein). Festgelegtes Verhalten (Code gelesen, nicht mehr Implementierungs-Ermessen):
  `startChannelOverride` erzeugt dabei ein eigenes Override; `mergeAllChannelLayoutsForSave`
  (`channelMetricLayouts.ts:117`) schreibt es als `channel_layouts.sms`. Die globale Liste
  `display_config.metrics` bleibt unverändert, Telegram bleibt bei Kaskadenquelle `global`. Nach
  dem Speichern steht die Kaskadenquelle für SMS auf `per_channel`, die geänderte
  Reihenfolge/Auswahl wird ausgeliefert wie eingestellt — E-Mail und Telegram bleiben gegenüber
  Golden C unverändert (passt zu AC-16).

Für jeden Fall werden zwei eingefrorene Dateien erzeugt (einmalig aus der echten Helferkette,
danach eingefroren, analog `nach_speichern_<golden>.json`):

- **`tests/fixtures/einstellung_auslieferung/nach_aenderung_<fall>.json`** — der vollständige,
  gespeicherte Trip-Zustand nach der Änderung (Ausgangs-Golden + simulierte Nutzeränderung, über
  `buildWeatherConfigMetrics`/`mergeAllChannelLayoutsForSave` gebaut und flach gemergt).
- **`tests/fixtures/einstellung_auslieferung/nach_aenderung_<fall>_anzeige.json`** — die vom Editor
  nach der Änderung berechnete Anzeige je Kanal (Auswahl/Reihenfolge/Roh-Einfach-Modus), gleiche
  Form wie `erwartung_golden_*.json`.

`<fall>` steht für einen sprechenden Bezeichner je Fall (z. B. `fall1_metrik_abwaehlen`,
`fall2_reihenfolge_tauschen`, `fall3_roh_einfach_umschalten`, `fall4_sms_erstbearbeitung`),
festgelegt in `/40`.

**TS-Kern:** Ein Test simuliert jeden der vier Fälle über dieselben echten Helfer wie die
No-Op-Tests (Anzeige-Neuberechnung + Speichern-Payload-Bau + flacher Merge) und vergleicht sowohl
die resultierende Anzeige gegen `nach_aenderung_<fall>_anzeige.json` als auch den gespeicherten
Stand gegen `nach_aenderung_<fall>.json` — strukturell, ohne Orakel-Logik in TS (derselbe
Mechanismus wie bei „Speichern ohne Änderung"). Jede Abweichung macht den Test rot.

**Python-Kern:** Zwei Zusicherungen je Fall:
1. Die eigentliche „Einstellung = Auslieferung"-Zusicherung für Änderungen:
   `erwartete_kaskade(nach_aenderung_<fall>.json)` stimmt mit der Projektion aus
   `nach_aenderung_<fall>_anzeige.json` überein (Auswahl, Reihenfolge, Roh/Einfach je Kanal) —
   **ohne Ausnahme**, auch für Fall 4.
2. Eine Plausibilitätsprüfung, dass die Änderung tatsächlich ankam (kein zufällig grüner
   No-Op-Fehlschluss): Die in Fall 1 abgewählte Metrik fehlt in der Projektion aus
   `nach_aenderung_fall1.json` GENAU im betroffenen Kanal (andere Kanäle bleiben unverändert wie im
   Original-Golden); die in Fall 2 getauschten Metriken stehen in der Projektion aus
   `nach_aenderung_fall2.json` nachweislich in vertauschter Reihenfolge gegenüber der
   Original-Golden-Projektion; analog für Fall 3 (Roh/Einfach) und Fall 4 (die abgewählte Metrik
   fehlt nur in SMS, die getauschten Metriken stehen nur in SMS vertauscht — E-Mail und Telegram
   bleiben gegenüber Golden C unverändert).

**E2E:** Mindestens eine echte Änderung im Browser (Staging): im SMS-Reiter (Fall 4, Golden C,
erstmalige Bearbeitung) eine Metrik abwählen UND zwei Metriken tauschen, danach speichern und per
`GET` zurücklesen — das Ergebnis stimmt auf den relevanten Feldern mit
`nach_aenderung_fall4_sms_erstbearbeitung.json` überein: Kaskadenquelle SMS wechselt auf
`per_channel`, E-Mail und Telegram bleiben gegenüber Golden C unverändert. Das ist der
End-to-End-Beleg für die Nutzerbeschwerde „ich stelle X ein, Y kommt an" im Fall der erstmaligen
SMS-Bearbeitung. Der separate E2E-Nachweis für B9 bei **unveränderter** Kaskadenquelle `global`
(SMS-Reiter bleibt unbearbeitet) steht im No-Op-Bein (AC-11).

### Ortsvergleich bleibt außerhalb (K10, Begründung gegen Teilungsverstoß)

Der Ortsvergleich hat einen eigenen Speicherweg (`compareEditorSave.ts`), ein eigenes Datenmodell
für die Kanalauswahl (`channel_active_metrics` statt `channel_layouts`) und legt `telegram_style`
in `display_config` statt in `report_config` ab (ADR-0053). S2a testet die **geteilten** Helfer
(`bucketsToColumns`, `channelOverrideFromMetrics`, `splitChannelMetricsForDisplay`), die auch der
Vergleichs-Editor nutzt (`CompareTabs.svelte`, `context="vergleich"`) — S2a fügt aber **keinen**
neuen Compare- oder Trip-Pendant-Baustein hinzu, weil kein neuer Baustein entsteht, nur
bestehende Helfer getestet werden. Der eigenständige Speicherweg-Vergleich (`channel_active_metrics`,
`compareEditorSave.ts`) ist strukturell eine andere Kette und gehört zu S5. Der B9-Fix
(`trip_report.py`) betrifft nur das Trip-Briefing — der Ortsvergleich hat keine
SMS-Positions-Kaskade (nutzt `channel_active_metrics`), ist also von B9 nicht berührt.

## Expected Behavior

- **Input:** Golden A, B (aus S1, unverändert), Golden C (neu, siehe oben); daraus abgeleitete,
  eingefrorene Anzeige-Erwartungsdateien (`erwartung_golden_*.json`), eingefrorene
  Nach-Speichern-Dateien (`nach_speichern_*.json`, No-Op) und eingefrorene Nach-Änderung-Dateien
  (`nach_aenderung_<fall>.json`/`_anzeige.json` für die vier Änderungsfälle 1–4) — alle erzeugt
  **nach** den B9-/K8-Fixes.
- **Output:** Für jede der drei Golden-Trips stimmt (a) die im TS-Kern simulierte Editor-Anzeige
  je Kanal mit der Anzeige-Erwartungsdatei überein, (b) der im TS-Kern simulierte Stand nach
  Speichern-ohne-Änderung mit der eingefrorenen `nach_speichern_*.json` überein (einschließlich
  aller per-Metrik-Felder), (c) `erwartete_kaskade(nach_speichern_*) == erwartete_kaskade(golden)`
  im Python-Kern — **ohne Ausnahme**, (d) der über beide Go-PUT-Pfade zurückgelesene Stand mit dem
  gesendeten Golden, und (e) die im echten Browser (E2E) angezeigte und gespeicherte
  Kanal-Konfiguration mit den jeweiligen eingefrorenen Dateien überein. Zusätzlich stimmt für jeden
  der vier Änderungsfälle (f) die TS-simulierte Anzeige/der TS-simulierte Speicherstand mit
  `nach_aenderung_<fall>*.json` überein, (g)
  `erwartete_kaskade(nach_aenderung_<fall>) == Projektion aus nach_aenderung_<fall>_anzeige` im
  Python-Kern — ohne Ausnahme, und (h) mindestens ein echter Änderungsfall im Browser (E2E) kommt
  so an, wie eingestellt. Produktiv liefert `trip_report.py` bei Kaskadenquelle `global` jetzt die
  Editor-Reihenfolge (B9-Fix), und das Frontend erhält beim Speichern alle dem Frontend unbekannten
  per-Metrik-Felder (K8-Fix).
- **Side effects:** Produktivcode-Änderung in Python-Core (`trip_report.py`, B9-Fix) und Frontend
  (`metricsEditor.ts`/`WeatherMetricsTab.svelte`/`channelMetricLayouts.ts`, K8-Fix), zusätzlich
  optional ein verhaltensgleiches Herauslösen von Lade-/Speicherfunktionen. Anpassung der
  #1677-Byte-Identitäts-Tests. Neue Testdateien, Golden C, eingefrorene Erwartungs-,
  Nach-Speichern- und Nach-Änderung-Dateien, ein Drift-Test. **Keine** Register-Erweiterung.

## Acceptance Criteria

- **AC-1 (Golden C in der Python-Matrix):** Given Golden C mit den Eigenschaften G1–G4 (kein
  eigenes SMS-/Telegram-Layout, umnummerierungs-sensitive globale Reihenfolge, `format_mode`
  gesetzt, per-Metrik `morning_enabled`/`evening_enabled` nicht-`null`) / When die S1-Invarianten-
  Matrix (`test_einstellung_gleich_auslieferung.py`) um Golden C erweitert läuft / Then wird Golden
  C von derselben Matrixfunktion wie A/B durchlaufen und erzeugt mindestens eine Zelle mit
  Kaskadenquelle `global`.
  - Test: `test_golden_c_kaskadenquelle_global_wird_ausgeloest` (Python-Kern) lädt Golden C über
    `load_trip`, prüft für SMS, dass die Kaskadenquelle `global` ist (nicht `per_channel`), für
    E-Mail bleibt sie `per_channel`.

- **AC-2 (Drift-Test der Erwartungsdateien):** Given eine eingefrorene Erwartungsdatei je Golden
  (A, B, C) / When der Drift-Test läuft / Then stimmt jede Erwartungsdatei exakt mit dem
  aktuellen Ergebnis von `erwartete_kaskade` für das jeweilige Golden überein — jede unbemerkte
  Abweichung (z. B. durch eine spätere Orakel-Änderung) macht den Test rot.
  - Test: `tests/test_erwartungsdatei_drift_einstellung_gleich_auslieferung.py::
    test_erwartungsdateien_entsprechen_dem_aktuellen_orakel` vergleicht für A/B/C `json.load` der
    Erwartungsdatei mit einer frisch aufgerufenen `erwartete_kaskade`-Projektion, Mengengleichheit.

- **AC-3 (TS-Anzeige = Erwartung je Kanal, alle drei Goldens, ohne Ausnahme):** Given die drei
  Erwartungsdateien und die echten Helfer `channelOverrideFromMetrics`/
  `splitChannelMetricsForDisplay` / When die TS-Helferkette auf Golden A, B und C angewendet wird
  / Then stimmt für email, telegram und sms je Golden die berechnete Anzeige-Reihenfolge und
  -Auswahl mit der Erwartungsdatei überein — **ohne Ausnahme**, auch für den SMS-Kanal von Golden C
  (Kaskadenquelle `global`).
  - Test: `weather-metrics-tab/__tests__/editor_anzeige_gleich_erwartung.test.ts`, `node --test`,
    parametrisiert über die drei Goldens × drei Kanäle.

- **AC-4 (TS-Speichern ohne Änderung = eingefrorener Stand, inkl. aller Felder):** Given ein Golden
  wird geladen, ohne dass der Nutzer etwas ändert / When `buildWeatherConfigMetrics` +
  `mergeAllChannelLayoutsForSave` die Speichern-Payload bauen und diese flach in den Ausgangsstand
  gemergt wird / Then stimmt der resultierende Stand strukturell mit der eingefrorenen
  `nach_speichern_<golden>.json` überein — ein reiner Datenvergleich, TS berechnet dabei keine
  Orakel-Projektion, und **inklusive** aller dem Frontend unbekannten Felder
  (`morning_enabled`, `evening_enabled`, `format_mode`) — kein Feld geht verloren.
  - Test: `weather-metrics-tab/__tests__/editor_speichern_ohne_aenderung.test.ts` baut den Stand
    nach Speichern für A, B, C und vergleicht ihn strukturell gegen `nach_speichern_golden_a.json`/
    `_b.json`/`_c.json`.

- **AC-5 (Python: Speichern ohne Änderung verändert die Auslieferung nicht, ohne Ausnahme — inkl.
  B9-Nachweis bei Kaskadenquelle `global`):** Given die eingefrorene `nach_speichern_<golden>.json`
  (aus AC-4) und das jeweilige Original-Golden / When `erwartete_kaskade` auf beide Zustände
  angewendet wird / Then ist `erwartete_kaskade(nach_speichern_<golden>) ==
  erwartete_kaskade(golden)` für A, B und C — **ohne Ausnahme** (weder für B9 noch für K8, beide
  sind gefixt). Für Golden C ist das ausdrücklich der **Python-Nachweis von B9 bei Kaskadenquelle
  `global`, ohne dass der SMS-Reiter bearbeitet wurde**: Die ausgelieferte SMS-Reihenfolge stimmt
  mit der im Editor angezeigten (globalen) Reihenfolge überein, statt der bisherigen festen
  Standardreihenfolge zu folgen. Das ist die eigentliche fachliche Zusicherung, dass Speichern ohne
  Änderung die Auslieferung nicht verändert; dieser Test deckt zugleich K9 ab, weil der Verlust von
  `format_mode` die Projektion nachweislich nicht verschiebt.
  - Test: `test_einstellung_gleich_auslieferung.py::
    test_ac5_speichern_ohne_aenderung_veraendert_die_auslieferung_nicht` (Python-Kern) lädt Golden
    und `nach_speichern_<golden>.json`, ruft `erwartete_kaskade` auf beiden auf und vergleicht die
    Ergebnismenge je Kanal auf exakte Gleichheit; für Golden C prüft ein eigener Fall explizit die
    SMS-Reihenfolge bei Kaskadenquelle `global` gegen `erwartung_golden_c.json`.

- **AC-6 (TS: alle Kanäle im Speichern-Payload):** Given nur ein Kanal-Reiter (z. B. email) wurde
  im Editor geöffnet oder bearbeitet / When die Speichern-Payload gebaut wird
  (`mergeAllChannelLayoutsForSave`) / Then enthält `channel_layouts` weiterhin **alle** drei
  Kanäle (email/telegram/sms) mit ihrem jeweils zuletzt bekannten Stand — kein Kanal fehlt im
  gesendeten Body.
  - Test: `weather-metrics-tab/__tests__/speichern_sendet_alle_kanaele.test.ts` baut die Payload
    nach simuliertem Bearbeiten nur eines Kanals und prüft `Object.keys(channel_layouts)` enthält
    email, telegram, sms.

- **AC-7 (TS: Feld-Erhalt ohne Ausnahme — K8-Fix):** Given ein per-Metrik-Eintrag in Golden C
  trägt `morning_enabled=false`/`evening_enabled=false`/`format_mode` / When der Editor lädt und
  ohne Änderung speichert / Then bleiben diese Werte im gebauten Payload für **jede** betroffene
  Metrik unverändert erhalten — ohne Ausnahme, ohne Register-Eintrag; ein Test, der das Gate
  wieder einführt (nur bekannte Felder übernehmen), macht diesen Test rot.
  - Test: `weather-metrics-tab/__tests__/feld_erhalt_ohne_ausnahme.test.ts` (bzw. Erweiterung von
    `editor_speichern_ohne_aenderung.test.ts`) prüft Metrik für Metrik, dass `morning_enabled`,
    `evening_enabled` und `format_mode` nach dem simulierten Speichern identisch zum
    Golden-C-Ausgangswert sind.

- **AC-8 (Go: Roundtrip beider PUT-Pfade):** Given ein Golden-Body (A, B oder C) wird per PUT
  gesendet / When abwechselnd `PUT /api/trips/{id}/weather-config` und `PUT /api/trips/{id}`
  verwendet werden, gefolgt von einem `GET` / Then ist der zurückgelesene Stand von
  `channel_layouts` und `display_config.metrics` exakt der gesendete, für **beide** Pfade
  unabhängig voneinander.
  - Test: `internal/handler/weather_config_editor_roundtrip_test.go`, zwei Unterfälle je Pfad,
    Golden per `os.ReadFile` relativ zur Testdatei.

- **AC-9 (Go: Cross-User-Isolation, Trip bleibt unverändert):** Given zwei verschiedene Nutzer A
  und B mit je eigenem Trip / When Nutzer B versucht, über denselben Endpoint den Trip von Nutzer
  A zu lesen oder zu ändern / Then schlägt der Zugriff fehl (kein Cross-User-Datenleck) UND ein
  anschließendes `GET` durch Nutzer A zeigt, dass dessen Trip nach dem abgewiesenen Versuch
  unverändert ist — unabhängig davon, welcher der beiden PUT-Pfade getestet wird.
  - Test: derselbe Testfile, `test_zwei_nutzer_sehen_sich_nicht` (Name sinngemäß), nutzt
    `s.WithUser` für beide Nutzer, prüft den Fehlerfall explizit und liest Nutzer As Trip danach
    erneut, um die Unverändertheit zu belegen.

- **AC-10 (E2E: Anzeige = Erwartung im echten Browser, ohne Ausnahme):** Given ein aus Golden C
  abgeleiteter Trip wurde über die Test-API angelegt / When der Editor im Browser (Staging)
  geöffnet und jeder Kanal-Reiter (email/telegram/sms) besucht wird / Then zeigt jeder Reiter die
  Auswahl/Reihenfolge aus der Anzeige-Erwartungsdatei — **ohne Ausnahme**, auch der SMS-Reiter bei
  Kaskadenquelle `global`.
  - Test: `frontend/e2e/editor-gleich-gespeichert.staging.spec.ts` (oder Erweiterung von
    `weather-metrics-tab-autosave.spec.ts`), Playwright gegen Staging, in `ci_e2e_specs.txt`.

- **AC-11 (E2E: Speichern → GET = eingefrorener Stand, inkl. Feld-Erhalt UND B9-Nachweis bei
  Kaskadenquelle `global`):** Given derselbe Golden-C-Trip im Editor geöffnet, ohne dass der Nutzer
  eine Einstellung ändert (SMS-Reiter bleibt unbearbeitet, Kaskadenquelle bleibt `global`) / When
  das Speichern ausgelöst wird (Autosave oder Klick) / Then liefert ein anschließendes
  `GET /api/trips/{id}` auf den relevanten Feldern (`display_config.metrics`, `channel_layouts`,
  ggf. `channel_layouts_per_report`) denselben Stand wie die eingefrorene
  `nach_speichern_golden_c.json` — insbesondere trägt die SMS-Ausgabe dieselbe Reihenfolge wie die
  Editor-Anzeige (das ist der **E2E-Nachweis von B9 bei Kaskadenquelle `global`**, ohne dass der
  Nutzer die SMS-Reihenfolge bearbeitet hat; der Nachweis für die erstmalige Bearbeitung steht in
  AC-17) — UND `morning_enabled`/`evening_enabled` je Metrik sind nach dem `GET` identisch mit dem
  Stand vor dem Speichern — die Kette Editor → Speichern (Go) → gespeichertes JSON ist end-to-end
  belegt und an die Python-Zusicherung (AC-5) angeschlossen.
  - Test: derselbe E2E-Spec, Folgeschritt nach AC-10, liest per API zurück und vergleicht die
    genannten Felder gegen `nach_speichern_golden_c.json`, inklusive der SMS-Reihenfolge.

- **AC-12 (Umfang der Verhaltensänderung ist auf B9 und K8 begrenzt):** Given der gesamte
  S2a-Umfang nach dem Umbau zu „Tests + Fix" / When alle neuen und bestehenden Tests laufen /
  Then ist die einzige von Nutzern beobachtbare Verhaltensänderung (a) die SMS-/Kurzform-/
  Premium-Reihenfolge bei Kaskadenquelle `global` folgt jetzt der Editor-Anzeige statt der festen
  Standardreihenfolge (B9-Fix), und (b) per-Metrik-Felder (`morning_enabled`, `evening_enabled`,
  `format_mode` u. a.) gehen beim Editor-Speichern nicht mehr verloren (K8-Fix) — alle anderen
  bestehenden Tests bleiben unverändert grün, mit der einzigen benannten Ausnahme der
  #1677-Byte-Identitäts-Tests bei `global` (siehe AC-13).
  - Test: Bestehende Editor-/Speichern-Tests (`channelPayloadAllChannels.test.ts`,
    `weatherConfigMetricsPayloadShape.test.ts`, `wetter_metriken_nutzlast_verliert_keine_daten.test.ts`)
    und bestehende SMS-Renderer-Tests außerhalb `global` (`tests/golden/sms/*.txt` für
    `per_channel`/`per_report`-Fälle) bleiben unverändert grün; ein vollständiger Testlauf zeigt
    keine weiteren, hier nicht benannten Regressionen.

- **AC-13 (#1677-Byte-Identität bei `global` wird bewusst abgelöst):** Given
  `fix_1677_sms_reihenfolge.md` AC-2 sichert bislang Byte-Identität der SMS-/Kurzform-Ausgabe bei
  Kaskadenquelle `global` zu (DEC-2-Aktivierungsgate) / When der B9-Fix (Entfernen des
  Aktivierungsgates in `trip_report.py:337–346`) umgesetzt ist / Then wird der zugehörige
  #1677-Test bewusst angepasst: entweder werden die `tests/golden/sms/*.txt`-Goldens für den
  `global`-Fall auf die neue, positionsbasierte Reihenfolge aktualisiert, oder der Testfall wird
  umgewidmet und ein neuer Test sichert „`position` gilt bei `global` genauso wie bei
  `per_channel`/`per_report`" zu — in keinem Fall bleibt die alte Byte-Identitäts-Zusicherung
  unverändert grün UND unangepasst gleichzeitig bestehen.
  - Test: `tests/tdd/test_sms_reihenfolge_gilt_auch_bei_globaler_kaskade.py` (neuer bzw.
    umbenannter Nachfolgetest der bisherigen #1677-AC-2-Byte-Identitätsprüfung), plus
    Diff-Nachweis, dass die betroffenen Golden-Dateien bewusst geändert wurden (Commit-Historie).

- **AC-14 (TS: Änderungsfälle 1–4, Anzeige UND Speichern = eingefrorener Stand):** Given die vier
  Änderungsfälle (Fall 1 Metrik abwählen, Fall 2 Reihenfolge tauschen, Fall 3 Roh/Einfach
  umschalten — alle auf Golden A; Fall 4 SMS-Reiter: erstmalige Bearbeitung, Metrik abwählen UND
  zwei Metriken tauschen — auf Golden C) mit ihren
  eingefrorenen `nach_aenderung_<fall>.json`/`_anzeige.json`-Dateien / When die echte
  Anzeige-Helferkette und die echte Speicher-Helferkette (`buildWeatherConfigMetrics`,
  `mergeAllChannelLayoutsForSave`, flacher Merge) je Fall erneut ausgeführt werden / Then stimmen
  sowohl die berechnete Anzeige mit `nach_aenderung_<fall>_anzeige.json` als auch der gespeicherte
  Stand mit `nach_aenderung_<fall>.json` strukturell überein — jede Abweichung macht den Test rot.
  - Test: `weather-metrics-tab/__tests__/editor_aenderung_gleich_erwartung.test.ts`, `node --test`,
    parametrisiert über die vier Fälle.

- **AC-15 (Python: Änderung kommt an, wie eingestellt, ohne Ausnahme):** Given
  `nach_aenderung_<fall>.json` (gespeicherter Stand nach der Änderung) und
  `nach_aenderung_<fall>_anzeige.json` (Editor-Anzeige nach derselben Änderung) je Fall / When
  `erwartete_kaskade` auf den gespeicherten Stand angewendet und mit der Anzeige-Projektion
  verglichen wird / Then stimmen Auswahl, Reihenfolge und Roh/Einfach je Kanal für alle vier Fälle
  überein — **ohne Ausnahme**, auch für Fall 4 (SMS-Reiter: erstmalige Bearbeitung, Kaskadenquelle
  wechselt von `global` zu `per_channel`) — das ist die eigentliche Zusicherung „ich stelle X ein,
  Y kommt an" aus #2422, nicht nur der No-Op-Fall aus AC-5.
  - Test: `test_einstellung_gleich_auslieferung.py::
    test_ac15_aenderung_kommt_wie_eingestellt_an` (Python-Kern), parametrisiert über Fall 1–4.

- **AC-16 (Python: Plausibilität — die Änderung hat tatsächlich gewirkt, alle vier Fälle):** Given
  die vier Änderungsfälle / When die Projektion aus `nach_aenderung_<fall>.json` gegen die
  Projektion aus dem jeweiligen Original-Golden verglichen wird / Then unterscheiden sie sich
  GENAU um die eingestellte Änderung und sonst nirgends: Fall 1 — die abgewählte Metrik fehlt nur
  im betroffenen Kanal; Fall 2 — die beiden getauschten Metriken stehen im betroffenen Kanal in
  vertauschter Reihenfolge; Fall 3 — die umgeschaltete Metrik wechselt im betroffenen Kanal
  zwischen Roh und Einfach; Fall 4 — die abgewählte Metrik fehlt **nur** in SMS, die beiden
  getauschten Metriken stehen **nur** in SMS vertauscht. Alle übrigen Kanäle und Metriken (E-Mail,
  Telegram) bleiben gegenüber dem Original-Golden unverändert. Das schließt aus, dass ein Fall grün
  bleibt, obwohl die Änderung nicht gewirkt hat (No-Op).
  - Test: `test_ac16_aenderung_hat_tatsaechlich_gewirkt`, parametrisiert über Fall 1–4, prüft
    je Fall die erwartete Differenz explizit (nicht bloß „ungleich").

- **AC-17 (E2E: erstmalige SMS-Bearbeitung kommt an, wie eingestellt):** Given Golden C ist im
  Browser (Staging) im SMS-Reiter geöffnet, der SMS-Reiter wurde bislang nie bearbeitet
  (Kaskadenquelle `global`, Fall 4) / When der Nutzer im SMS-Reiter eine Metrik abwählt UND zwei
  Metriken tauscht und danach speichert / Then liefert `GET /api/trips/{id}` auf den relevanten
  Feldern (`display_config.metrics`, `channel_layouts`, ggf. `channel_layouts_per_report`)
  denselben Stand wie die eingefrorene `nach_aenderung_fall4_sms_erstbearbeitung.json` — die
  Kaskadenquelle für SMS steht danach auf `per_channel`, E-Mail und Telegram bleiben gegenüber
  Golden C unverändert. Die Nutzerbeschwerde „ich stelle X ein, Y kommt an" ist damit für den Fall
  der erstmaligen SMS-Bearbeitung end-to-end belegt, nicht nur der No-Op-Fall (der separate
  B9-Nachweis bei unveränderter Kaskadenquelle `global` steht in AC-11).
  - Test: derselbe E2E-Spec wie AC-10/AC-11, weiterer Testfall mit echter Bedienung statt reinem
    Auslesen, liest per API zurück und vergleicht die genannten Felder gegen
    `nach_aenderung_fall4_sms_erstbearbeitung.json`.

- **AC-18 (Keine neuen Register-Einträge):** Given die Umsetzung dieser Scheibe (B9-Fix, K8-Fix,
  Änderungspfad) / When in `/40`/`/50` eine weitere, bisher unbekannte Abweichung innerhalb dieser
  Kette auftritt / Then wird sie, sofern im Rahmen dieser Kette lösbar, produktiv gefixt statt
  registriert — es wird **kein** neuer befristeter Register-Eintrag angelegt; liegt sie außerhalb
  des Rahmens dieser Kette, stoppt der Entwickler und legt den Befund dem PO vor, statt ihn
  befristet zu tolerieren oder stillschweigend zu übergehen. Nach Abschluss von S2a enthält das
  Register ausschließlich die unveränderten S1-Einträge (B1/B2/B3/B5).
  - Test: `test_ac18_keine_neuen_register_eintraege` (Python-Kern, Erweiterung der S1-Register-
    Prüfung) zählt die Register-Einträge nach Abschluss von S2a und prüft, dass kein Eintrag mit
    `befund` in `{"B9", "K8", "K9"}` oder einem in dieser Spec nicht benannten neuen Kürzel
    existiert.

## Known Limitations

- Außerhalb der beiden Fixes (B9, K8) ändert S2a **kein** weiteres Produktverhalten, mit Ausnahme
  eines optionalen, verhaltensgleichen Herauslösens von Editor-Lade-/Speicherlogik in eine reine
  Funktion.
- B9 und K8 sind mit dieser Scheibe **produktiv gefixt** — kein Register-Eintrag, kein Folge-Fix
  in einer weiteren Scheibe nötig. Der produktive Fix für B6 (Editor-Sichtbarkeit) folgt weiterhin
  in #2438.
- `format_mode` (K9) geht nach dieser Scheibe **nicht mehr** verloren: Es wandert durch den
  K8-Fix (Read-Modify-Write statt Replace) als dem Editor unbekanntes Feld mit und ist durch AC-7
  ausdrücklich zugesichert. Kein Register-Eintrag.
- Ortsvergleich (`compareEditorSave.ts`, `channel_active_metrics`) ist strukturell außerhalb —
  eigene Kette, eigene Scheibe S5; vom B9-Fix nicht berührt (keine SMS-Positions-Kaskade dort).
- Die Datenlage zu `morning_enabled`/`evening_enabled` in Bestandstrips ist für Prod nicht messbar
  (`hem` hat keinen Zugriff auf `/var/lib/gregor`); der Fix wird unabhängig davon umgesetzt (siehe
  Datenlage-Abschnitt).
- Kein Staging-Zugriff für die TS-/Go-/Python-Kern-Tests nötig — nur das E2E-Bein läuft gegen
  Staging (wie in der Deploy-Kette ohnehin vorgesehen).
- Der Änderungspfad deckt genau vier definierte Fälle ab (Metrik abwählen, Reihenfolge tauschen,
  Roh/Einfach umschalten, SMS-Reiter bei Kaskadenquelle `global`) — nicht jede denkbare Kombination
  von Änderungen (z. B. gleichzeitiges Ändern mehrerer Kanäle in einem Speicherzyklus, Änderungen
  an `bucket`/`channel_layouts_per_report`). Letztere gehören laut Deckungstabelle zu S3.
- Die einmalige Verhaltensänderung der SMS-/Kurzform-/Premium-Reihenfolge bei Kaskadenquelle
  `global` (B9-Fix) betrifft ausschließlich Trips, deren SMS-Reiter noch nie bearbeitet wurde —
  bei allen anderen bleibt die Reihenfolge unverändert (sie folgte schon vorher der
  Nutzer-Position).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Anwendung von ADR-0050/0049/0032/0053, keine neue Entscheidung)
- **Rationale:** S2a führt keine neue Architekturentscheidung ein. ADR-0050 ist durch den B9-Fix
  nicht betroffen — Regel 5 „Reihenfolge je Kanal einstellbar" wird eher gestärkt, weil die
  Nutzer-Reihenfolge jetzt ausnahmslos wirkt, statt nur bei zwei von drei Kaskadenebenen. Die
  Ablösung von DEC-2 aus `fix_1677_sms_reihenfolge.md` ist keine ADR-pflichtige
  Architekturentscheidung (Kaskade/Datenmodell unverändert), sondern eine Änderung der
  Aktivierungsbedingung einer bestehenden Ableitung — sie wird deshalb hier als dokumentierte
  Ablösung festgehalten (PO-Entscheid 2026-09-27, Verweis + Changelog), statt ein neues ADR
  anzulegen. Die K8-Fix-Code-Änderung (Read-Modify-Write statt Replace) wendet lediglich die
  bestehende CLAUDE.md-Regel #102 an und braucht ebenfalls kein neues ADR.

## Changelog

- 2026-09-27: Initial spec created (Scheibe S2a von #2422, Schnitt S2a/S2b gegenüber der S1-Spec
  bestätigt und begründet — B6/B9-Editor-Sichtbarkeit wandert nach S2b/#2438).
- 2026-09-27: Nach Koordinator-Korrektur überarbeitet — Widerspruch aufgelöst, dass TS eine
  „Orakel-Projektion" berechnen müsste (Orakel bleibt Python-exklusiv): neue zweigliedrige Kette
  über eingefrorene `nach_speichern_<golden>.json`-Dateien (TS vergleicht strukturell, Python prüft
  mit `erwartete_kaskade` die eigentliche Auslieferungs-Gleichheit, E2E schließt die Verdrahtung
  an); AC-4/AC-10(alt) entsprechend umgeschrieben, neues AC-5 (Python-Äquivalenz) ergänzt; K9
  (`format_mode`) von „Register-Eintrag" auf „kein Register-Eintrag, abgedeckt durch AC-5"
  korrigiert (ein Eintrag für eine nie rot werdende Zelle wäre sofort veraltet); AC-7 (Register-
  Mechanik) präzisiert: ein veralteter Eintrag macht den Testlauf rot, nicht nur eine Meldung;
  AC-9 (Go Cross-User) um die Zusicherung ergänzt, dass Nutzer As Trip nach dem abgewiesenen
  Zugriff unverändert bleibt. ACs neu durchnummeriert (jetzt 13 statt 12).
- 2026-09-27: Nach unabhängigem PO-Briefing erweitert — bislang wurde nur „Speichern ohne
  Änderung" (No-Op) geprüft; die eigentliche Beschwerde aus #2422 („ich stelle X ein, Y kommt an")
  ist aber ein Änderungsfall. Neuer Baustein „Änderungspfad" mit vier Pflicht-Änderungsfällen
  (Metrik abwählen, Reihenfolge tauschen, Roh/Einfach umschalten, SMS-Reiter bei Kaskadenquelle
  `global`), je zwei eingefrorenen Dateien (`nach_aenderung_<fall>.json`/`_anzeige.json`), neuen
  ACs AC-14 bis AC-18 (TS-Beide-Vergleiche, Python-Kernzusicherung, Python-Plausibilität, E2E mit
  echter Bedienung, Register-Mechanik für Fall 4/B9). Deckungstabelle (K11), Expected Behavior,
  Estimated Scope und Known Limitations entsprechend ergänzt. ACs jetzt 18 statt 13.
- 2026-09-27: **PO-Entscheid — von „nur Tests" zu „Tests + Fix" umgebaut.** Henning hat die
  Freigabe der Register-Fassung verweigert („Warum soll ich eine befristete Abweichung OK
  heißen?"). B9 und K8 werden jetzt **in dieser Scheibe produktiv gefixt**, nicht mehr registriert:
  B9-Fix in `src/output/renderers/trip_report.py:337–346` (Aktivierungs-Gate entfällt, löst DEC-2
  aus `fix_1677_sms_reihenfolge.md` ab, dortige AC-2-Byte-Identitätstests werden angepasst — neues
  AC-13); K8-Fix im Frontend (Read-Modify-Write statt Replace beim Editor-Speichern, CLAUDE.md
  #102 — neues AC-7). Alte Register-bezogene ACs (Register-Mechanik B9, Register-Startbefüllung
  K8/B9, Register-Mechanik Änderungsfall) entfernt bzw. ersetzt durch AC-12 („Umfang der
  Verhaltensänderung ist auf B9 und K8 begrenzt", ersetzt die alte „Verhaltensneutralität") und
  AC-18 („Keine neuen Register-Einträge" — neue Pflichtregel für Folgefunde in `/40`/`/50`).
  Deckungstabelle (K6, K8, neue K12), Source (Produktivcode-Dateien in zwei Schichten), Estimated
  Scope (produktiv jetzt ~150–290 LoC, voraussichtlich über dem 250-LoC-Limit →
  `loc_limit_override` nötig), Dependencies, Änderungspfad (Fall 4 ohne Register-Bezug) und Known
  Limitations entsprechend überarbeitet. ACs neu durchnummeriert, weiterhin 18 (AC-1 bis AC-18),
  aber mit anderem Inhalt an mehreren Stellen (siehe oben).
- 2026-09-27: Fall 4 anhand des gelesenen Codes festgelegt (kein Implementierungsermessen mehr):
  bearbeitet der Nutzer den nie angefassten SMS-Reiter (`channelBuckets.sms === null`), erzeugt
  `startChannelOverride` ein eigenes Override, `mergeAllChannelLayoutsForSave`
  (`channelMetricLayouts.ts:117`) schreibt es als `channel_layouts.sms`; die globale Liste bleibt
  unverändert, Telegram bleibt `global`. Satz „der Implementierer stellt in `/40` empirisch fest"
  gestrichen. Fall 4 umbenannt in „SMS-Reiter: erstmalige Bearbeitung" (Metrik abwählen UND zwei
  Metriken tauschen, wie im E2E-Bein), Datei `nach_aenderung_fall4_sms_global_reihenfolge.json` in
  `nach_aenderung_fall4_sms_erstbearbeitung.json` umbenannt; AC-14/AC-15/AC-16/AC-17 entsprechend
  angepasst, AC-16 Fall 4 um „abgewählte Metrik fehlt nur in SMS" ergänzt. Der **B9-Nachweis bei
  Kaskadenquelle `global` (ohne Änderung)** ausdrücklich als solcher benannt: AC-5 (Python-Kern)
  und AC-11 (E2E) tragen jetzt explizit den Zusatz „B9-Nachweis bei Kaskadenquelle `global`" — Fall
  4/AC-17 heißt nicht mehr B9-Beweis, sondern „erstmalige SMS-Bearbeitung kommt an wie eingestellt".
  Purpose-Absatz um eine einfache Erklärung ergänzt, dass der B9-Fix ebenso Premium-SMS und
  Telegram-Kurzform betrifft (ADR-0049, gleicher SMS-Text-Aufbau). AC-Anzahl unverändert bei 18.
