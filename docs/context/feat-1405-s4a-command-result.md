# Context: feat-1405-s4a-command-result

## Request Summary
#1405 S4, erstes Bündel (S4a): die 21 B18-Funde des Wächters `tests/test_success_status_guard.py`
in `src/services/trip_command_processor.py` reparieren — „Erfolg heißt Wirkung" für die Antwort auf
Nutzer-Befehle (Mail/SMS/Telegram). Restliste gesamt vorher: 31 (Erfolg) + 22 (Auflösung) = 53.

## Kernbefunde (gemessen 2026-10-14)

1. **`CommandResult.success` hat in Produktion KEINEN Leser.** `grep '\.success\b'` über `src/`, `api/`
   leer; kein `asdict`/`vars` auf `CommandResult`; kein JSON-Feld `success` in `internal/scheduler`,
   `internal/handler/inbound_webhooks.go`. Gelesen wird es nur in Tests (36 Testzeilen).
   **Folge:** Ein bloßes Umsetzen des Booleans ändert für den Nutzer nichts. ACs müssen an der
   **Antwort je Kanal** hängen (kommt sie an, was steht drin) — sonst fängt beim Zurückdrehen auf
   `True` kein Test die Wirkung.
2. **`process()` (`trip_command_processor.py:978`) fängt Handler-Exceptions NICHT ab.** Was dann passiert:
   | Kanal | Stelle | Verhalten bei Exception aus einem Handler |
   |---|---|---|
   | Mail | `inbound_email_reader.py:250-257` | `logger.exception`, **keine Antwort** an den Nutzer |
   | SMS | `inbound_sms_reader.py:280-283` (um `_verarbeite_befehl`) | `logger.warning`, **keine Antwort** |
   | Telegram | `api/routers/webhook.py:89-92` (um `_process_update`) | `logger.error`, `{"status":"ok"}`, **keine Antwort** |
   → Das ist die eigentliche Unterart-B-Wirkung: der Nutzer schickt `pause`, das Speichern wirft,
   er bekommt nichts (oder glaubt bei anderer Verdrahtung an Erfolg). Ein zentraler Fang in
   `process()` würde alle drei Kanäle ohne Reader-Änderung abdecken (Lösungsentscheid → /20).
3. **`save_trip` (`src/app/loader.py:1954`) meldet Fehler per Exception** (`TripFileCorrupt`, OSError),
   nicht per Rückgabewert. `p = save_trip(...); success = p is not None` befriedigt nur den Scanner
   → Umgehung, wird vom Adversary zu Recht als BROKEN gewertet.

## Die 21 Funde in drei Klassen

| Klasse | Funktionen (Schlüssel-Suffix) | Anzahl |
|---|---|---|
| **A — nach Speichern** | `_apply_pause`, `_apply_skip`, `_apply_ruhetag`, `_cancel_trip`, `_resume_trip`, `_apply_compare_pause` (`save_compare_preset_pause`), `_resume_compare` (`resume_compare_preset`, Status-Rückgabe nur teilweise geprüft) | 7 |
| **B — nach Wetter-Abruf** | `_handle_query` ::0–::3 (glance, heute_gewitter, timeline_heute/morgen), `_handle_drilldown`, `_handle_hours_drilldown`, `_handle_metric_drilldown`, `_show_now`, `_show_strecke` ::0–::2 | 11 |
| **C — reiner Text** | `_show_help`, `_show_help_for_kind`, `_show_status` (matcht nur über `date.today()`, Spec „Offene Punkte" 3) | 3 |

Vorbilder für Klasse B **in derselben Datei:** `success=ergebnis.outcome == "sent"` (:1555, :1564),
`success=bool(werte)` (:1716), `success=outcome == "sent"` (:2491); Ausfall-Zweig in
`_handle_metric_drilldown` prüft bereits `_traegt_werte(res)`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | 21 Fundstellen; `CommandResult` (:177), `process()` (:978) |
| `tests/test_success_status_guard.py` | `KNOWN_VIOLATIONS` (:1506, B18 ab :1587), `SPEC_LISTED_FINDINGS` (Längenanker `len == 19 and sum == 22` bei :1946), `INTENTIONAL_CONSTANT_SUCCESS` + `_APPROVED_EXCEPTIONS` (:3411) |
| `docs/specs/modules/waechter_1405_erfolg_wirkung.md` | Spec des Wächters; „Offene Punkte" 3 (:743ff.) zur risiko-blinden Klasse-1-Signatur |
| `src/services/inbound_email_reader.py`, `inbound_sms_reader.py`, `inbound_telegram_reader.py`, `api/routers/webhook.py` | Aufrufer von `process()` und Fehlerbehandlung |
| `src/app/loader.py` (`save_trip`), `src/services/scheduler_dispatch_service.py` (`save_compare_preset_pause` :310, `resume_compare_preset` :348) | Speicherpfade Klasse A |
| `docs/specs/modules/fix_1405_s1_alarm_zustellung.md` | Vorgänger-Scheibe (Muster „Erfolg heißt Zustellung") |

## Existing Patterns
- **Hausnorm** `run_briefing_dispatch()` → `(sent, failed)`; Status aus dem Ergebnis, nicht konstant.
- **Genehmigte Text-Ausnahmen existieren bereits:** `_show_columns_info`, `_show_config` stehen in
  `_APPROVED_EXCEPTIONS` — Präzedenz für Klasse C. Zuwachs der Ausnahmeliste ist laut Test
  ausdrücklich „eine Spec-Entscheidung" (F001-Sperre `test_intentional_exception_list_cannot_grow`).
- Akzeptierte Reparaturformen definiert der Scanner über seine Ignore-Tests
  (`test_scanner_ignores_diverging_except_return…`, `…_pure_computation_calls…`,
  `…_house_norm_sent_failed_tuple…`) — daran ausrichten, nicht neu erfinden.

## Ratschen-Mechanik (bei jeder reparierten Funktion zusammen ändern)
1. Eintrag aus `KNOWN_VIOLATIONS` entfernen (sonst `test_known_violations_only_shrink` rot).
2. Ort aus `SPEC_LISTED_FINDINGS` entfernen bzw. Mindestzahl senken + Längenanker (`len == 19 / sum == 22`)
   nachziehen (sonst `test_scanner_finds_every_spec_listed_finding` rot).
3. Schlüssel `::0..::3` sind je Funktion durchnummeriert → **Funktionen immer ganz reparieren**,
   sonst verrutschen die Indizes.
4. Klasse C über `INTENTIONAL_CONSTANT_SUCCESS` + `_APPROVED_EXCEPTIONS` nur mit Spec-Begründung.

## Dependencies
- Upstream: `save_trip`, `save_compare_preset_pause`/`resume_compare_preset`, `WeatherExtractor.drilldown`,
  Nowcast-Service, `_fmt_*`-Formatierer.
- Downstream: die drei Reader + Telegram-Webhook (verschicken jede Antwort unabhängig von `success`).

## Existing Specs
- `docs/specs/modules/waechter_1405_erfolg_wirkung.md`, `waechter_1405_stille_aufloesung.md`,
  `fix_1405_s1_alarm_zustellung.md`.

## Risks & Considerations
- **Scanner-Gaming:** Ableitungen, die nur syntaktisch „aus einem Ergebnis" kommen (`p is not None`),
  sind keine Reparatur. Mutations-Gegenprobe muss an der **Antwort** messen.
- **Klasse C:** Ausnahme-Zuwachs vs. Erweiterung `_is_pure_computation_call` (Gate-Code, hohes Risiko,
  synthetischer Test nötig) — **offene Frage für /20**.
- **Zentraler Fang in `process()`:** muss die Antwort kanalgerecht formulieren (SMS ≤160 Zeichen) und
  darf keine echten Programmfehler verschleiern (Protokoll bleibt Pflicht).
- **Parallelsitzung #2439** (cached-baking-peacock) ändert `inbound_sms_reader.py` (Feld `processed`)
  und `api/routers/scheduler.py`, NICHT den Prozessor (Abstimmung 2026-10-14). Falls S4a Reader
  anfassen muss → vorher per `SendMessage` Bescheid geben.
- Uhrzeitabhängige Kommando-Tests (Briefing-Sperre #1594, s. S1-Kommentar) → außerhalb des Fensters messen.
- Kommando-Pfad ist live-relevant: Staging-Gate verlangt Telegram-Live-Test + echten Mail-Eingang.

## Analysis

### Type
Feature (Reparatur-Scheibe S4a des Wächters #1405, Unterart B „Erfolg heißt Wirkung")

### Scanner-Regel (gemessen, `tests/test_success_status_guard.py:576-664`)
Geflaggt wird ein `return` mit konstantem Erfolgsliteral (`success=True` u. a., `_SUCCESS_LITERALS` :220),
wenn davor im selben Funktions-Scope irgendein Nicht-`logger`-Aufruf steht (:650-657). **Einzige Ausnahme:**
ein `except`-Handler IN DERSELBEN Funktion gibt einen anderen Wert zurück (:661, `ast.dump`-Vergleich) —
dann sind ALLE Returns dieser Funktion frei. Hilfsfunktionen, die `False` liefern, sieht der Scanner nicht.
`_is_pure_computation_call` gilt nur für Klasse 2, nicht hier. Reparaturen, die der Regel NICHT genügen
(bleiben geflaggt): Early-Return + konstantes `True` am Ende; Guard, der nur loggt und weiterläuft.

**Ehrlich zulässige Formen (nur diese zwei):**
- **F1 — Ein-Return mit Prädikat:** EIN `return CommandResult(success=<prädikat>, ...)`, bei dem DASSELBE
  Prädikat auch Betreff/Text wählt (Ohne-Daten-Text ↔ Daten-Text). Zur Laufzeit nicht konstant.
- **F2 — Divergierender `except`:** echter Fehlerpfad im selben Scope, der die Fehlerantwort zurückgibt.

**Verboten (Scanner-Gaming):** `success = x is not None`/`fehler is None` hinter einem Early-Return
(zur Laufzeit konstant); Verlagerung in Helfer, nur damit der Scanner nichts mehr sieht.

### Entscheidungen (technisch, kein PO-Halt)
1. **KEIN Aufteilen** in Unterscheiben: alle 21 Funde in diesem Workflow (Memory: Epics themenweise
   abschließen, `/40` deckt alle ACs). Quellcode-Anteil ~130–180 LoC; reicht 250 nicht →
   `workflow.py set-field loc_limit_override 500`.
2. **Zentraler Fang in `process()` (:978)** — die eigentliche Nutzerwirkung: heute bekommt der Nutzer bei
   JEDER Handler-Exception auf allen vier Kanälen GAR KEINE Antwort (Mail `inbound_email_reader.py:256`,
   SMS/Premium-SMS `inbound_sms_reader.py:282`, Telegram `webhook.py:91`). Neu: `except Exception` →
   `logger.exception` (Programmfehler bleiben sichtbar) + `CommandResult(success=False, ...)` mit kurzer,
   kanaltauglicher Antwort (≤160 Zeichen, DE/EN über `self._t`), `suppress_email_reply=False`.
   **Idempotenz-Falle (verbindlich für den AC-Text):** der Text darf NICHT pauschal „bitte erneut senden"
   sagen — `skip`, `ruhetag` (nach dem Speichern) und `heute`/`morgen` (Briefing evtl. schon verschickt)
   sind nicht wiederholungsfest. Sinngemäß: „Befehl konnte nicht sicher ausgeführt werden. Bitte mit
   STATUS prüfen, bevor du ihn erneut sendest." (EN analog). Keine Reader-Änderung → keine Kollision mit #2439.
3. **Klasse A über F2, NICHT über die Ausnahmeliste.** `_speichere` (:3108) wirft künftig eine eigene
   Exception (z. B. `_SpeicherFehler`), die die bisherige Fehler-`CommandResult` trägt; jeder Handler:
   `try: self._speichere(...) except _SpeicherFehler as e: return e.result`. LoC-neutral gegenüber
   `fehler = ...; if fehler: return fehler`. Compare-Pause analog (Wrapper um `save_compare_preset_pause`,
   wirft bei `False`). `_resume_compare` über F1 (`fortgesetzt = status == "resumed"` wählt Text UND
   success; `lock_timeout` bleibt eigener Zweig).
4. **Klasse B über F1/F2.** Prädikat = genau das, was heute schon den Ohne-Daten-Text wählt
   (`timeline.available` in `_fmt_glance/_fmt_gewitter/_fmt_timeline` :2211/:2236/:2283; „Keine
   stündlichen Daten" in den Drilldowns). Folge: „Kein Wetter-Snapshot verfügbar" → `success=False`
   (Antworttext unverändert).
5. **Klasse C (`_show_help`, `_show_help_for_kind`, `_show_status`) → `INTENTIONAL_CONSTANT_SUCCESS` +
   `_APPROVED_EXCEPTIONS`** (3 → 6), Präzedenz `_show_columns_info`/`_show_config`. Reiner Text aus der
   Trip-Konfiguration, kein Abruf, kein Schreiben → kein Fehlerausgang, den `success` abbilden könnte.
   `_is_pure_computation_call` wird NICHT erweitert (Gate-Code, lockert den Wächter repo-weit).
6. `success` bleibt ohne Produktions-Leser. Ehrliche Spec-Rahmung: „Status konsistent zur Antwort" +
   zentrale Fehlerantwort als Nutzerwert. Kein neuer Konsument in dieser Scheibe.

### Die 21 Funde — Reparaturform je Schlüssel
| # | Schlüssel (`trip_command_processor.py`) | Form | Warum der Scanner ihn freigibt | Welcher Test wird rot beim Zurückdrehen |
|---|---|---|---|---|
| 1 | `_apply_pause::0` (:2731) | F2 `_SpeicherFehler` | divergierender except im Scope | gesperrter Trip (`LockTimeout`) → Antwort „Bitte erneut senden", nicht „pausiert" |
| 2 | `_apply_skip::0` (:2761) | F2 | dto. | dto. für `skip`; `LoaderError` → „Nicht gespeichert" |
| 3 | `_apply_ruhetag::0` (:2456) | F2 | dto. | dto.; zusätzlich: `_append_command_log`/`_delete_snapshot` NACH dem Speichern werfen → Antwort meldet Ruhetag gesetzt (kein Fehler), Warn-Log |
| 4 | `_cancel_trip::0` (:3066) | F2 | dto. | `LoaderError` → „Nicht gespeichert" |
| 5 | `_resume_trip::0` (:3085) | F2 | dto. | dto. |
| 6 | `_apply_compare_pause::0` (:1340) | F2 (Wrapper wirft bei `False`) | dto. | Vergleich gesperrt → „Bitte erneut senden" |
| 7 | `_resume_compare::0` (:1383) | F1 `fortgesetzt` | success nicht-literal | nicht pausierter Vergleich → „ist nicht pausiert" + `success=False` |
| 8–11 | `_handle_query::0–::3` (:1479/1489/1499/1509) | F1, Prädikat `timeline.available` (bzw. Tagespunkte vorhanden) | success nicht-literal | kein Snapshot + Abruf scheitert → Text „Kein Wetter-Snapshot" UND `success=False`, je Kanal |
| 12 | `_handle_drilldown::0` (:1643) | F1 (Ohne-Daten-Zweig :1619 + Daten-Zweig in EIN Return) | dto. | kein Stundenwert → „Keine stündlichen Daten", `success=False` |
| 13 | `_handle_hours_drilldown::0` (:1836) | F1 (mit :1802 zusammenlegen) | dto. | alle vier Spalten fehlen → `success=False` |
| 14 | `_handle_metric_drilldown::0` (:1734) | F1 (`werte`/`_traegt_werte` als Prädikat, :1698/:1715) | dto. | keine Werte → `success=False` |
| 15 | `_show_now::0` (:2878) | F2 um `get_nowcast` (:2866, heute unbewacht) | divergierender except | `get_nowcast` wirft → Antwort „Nowcast nicht verfügbar" statt KEINER Antwort |
| 16–18 | `_show_strecke::0–::2` (:3022/:3035/:3049) | F2 um `backfill_stage_distances(persist=True)` (:2910, unbewacht) + F1 für „keine Daten" | divergierender except | **Verdacht stiller Ersatz:** liefern ALLE Punkte `None` (inkl. Startpunkt / nur 1 Punkt), behauptet :3031 „Kein Regen erkannt" → in `/40` per Test reproduzieren; Soll: „Nowcast nicht verfügbar", `success=False` |
| 19 | `_show_help::0` (:2640) | Ausnahmeliste | Spec-Begründung | entfällt (kein Fehlerausgang) |
| 20 | `_show_help_for_kind::0` (:1270) | Ausnahmeliste | dto. | entfällt |
| 21 | `_show_status::0` (:2597) | Ausnahmeliste | dto. (nur `trip_local_today` + Etappenliste) | entfällt |

### Ratschen-Nachzug (im selben Commit wie die Reparatur, Funktionen immer GANZ)
- `KNOWN_VIOLATIONS` (:1587-1699): alle 21 Trip-Schlüssel raus.
- `SPEC_LISTED_FINDINGS` (:1851-1871): 10 Trip-Funktionen / 13 Treffer raus → Längenanker :1946 von
  `len == 19 and sum == 22` auf voraussichtlich **`len == 9 and sum == 9`** (in `/40` nachrechnen, ob
  `_show_status` als Ausnahme dort bleiben muss → dann 10/10).
- `INTENTIONAL_CONSTANT_SUCCESS` (:1736) + `_APPROVED_EXCEPTIONS` (:3411): +3 (Klasse C) mit Begründung.
- Veraltete Docstrings beim Vorbeigehen korrigieren: :1908-1916 („33 Funktionen / sum 42"),
  :1717-1734 („Genau EIN Eintrag").

### Tests
- **Neue Verhaltenstests über den ECHTEN Eingang aller vier Kanäle** (Memory: Befehle erst durch den
  echten Kanal-Eingang fertig): Mail-Reader, SMS-Reader (`sms` UND `premium_sms`), Telegram
  `_process_update`. Kern-Assertion: eine Antwort GEHT RAUS und trägt den richtigen Inhalt. Mutation
  „Fang in `process()` entfernen" muss rot werden; Mutation je Funktion „`success=True` konstant" muss
  einen Test rot machen.
- **Bestehende Tests mit `success is True` auf Ohne-Daten-Pfaden** (Kandidaten u. a.
  `test_issue_651_telegram_query_glance.py`, `test_issue_704_telegram_interactive_navigation.py`,
  `test_timeline_tagesgenaue_quellen.py`, `test_feature_656_radar_nowcast.py`,
  `test_stundenabruf_teilluecken.py`): in `/40` gezielt ermitteln; die Erwartung in der Spec AUSDRÜCKLICH
  ändern (keine stille Anpassung).
- `pytest.raises` gegen `process(` prüfen — der zentrale Fang ändert dieses Verhalten bewusst.
- Uhrzeitabhängige Tests (Briefing-Sperre #1594) außerhalb des Fensters messen.

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_command_processor.py` | MODIFY | zentraler Fang `process()`, `_SpeicherFehler`, F1/F2 je Funktion |
| `tests/test_success_status_guard.py` | MODIFY | Ratsche, Längenanker, Ausnahmeliste +3, Docstrings |
| `tests/tdd/test_befehlsantwort_erfolg_heisst_wirkung.py` | CREATE | Verhaltenstests über die vier echten Eingänge |
| bestehende `tests/tdd/test_*` mit `success is True` auf Ohne-Daten-Pfaden | MODIFY | Erwartung ausdrücklich auf `False` |
| `docs/specs/modules/waechter_1405_erfolg_wirkung.md` | MODIFY | Begründung Ausnahmen Klasse C, Stand Restliste |

### Scope Assessment
- Dateien: 3–4 produktiv/Test + ~5 Bestandstests
- Geschätzte LoC: Quelle +130…180 / −40; Tests +200
- Risiko: **MITTEL** — zentraler Befehlspfad aller vier Kanäle; Wortlaut der Fehlerantwort; viele Bestandstests

### Dependencies
- Upstream: `update_trip`/`save_trip` (`LockTimeout`, `LoaderError`), `save_compare_preset_pause`,
  `resume_compare_preset` (`scheduler_dispatch_service.py:310/:348`), `WeatherExtractor`,
  `RadarNowcastService.get_nowcast`, `backfill_stage_distances`.
- Downstream: Mail-/SMS-/Telegram-Reader + Webhook — UNVERÄNDERT (lesen `success` nicht).
- Parallel: #2439 (`inbound_sms_reader.py`) — kein Überlapp, solange die Reader unverändert bleiben.

### Open Questions
- Keine PO-Fragen (alles technische Entscheidungen). In `/40` zu messen: (a) Verdacht stiller Ersatz in
  `_show_strecke` bei komplettem Nowcast-Ausfall; (b) ob `_show_status` in `SPEC_LISTED_FINDINGS` bleibt
  (Anker 9/9 vs. 10/10).
