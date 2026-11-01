---
entity_id: fix_1777_compare_faelligkeit_und_idempotenz
type: bugfix
created: 2026-11-01
updated: 2026-11-01
status: draft
workflow: fix-1777-compare-faelligkeit
version: "1.0"
tags: [issue-1777, epic-1722, timezone, adr-0051, adr-0044, scheduler, ortsvergleich, idempotenz]
---

# Fix #1777 — Ortsvergleich-Briefing: Fälligkeitsfenster + Idempotenz-Vermerk

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich entscheidet die Fälligkeit seiner Briefing-Slots per exakter
Stundengleichheit (`slots.morning_time.hour == hour` / `slots.evening_time.hour == hour`,
`src/services/compare_slot_scheduler.py:211,213`). Dadurch entfällt ein auf 02:00 gestellter
Vergleich am Frühjahrs-Umstellungstag ersatzlos, geht am Herbsttag doppelt an die Empfänger und
fällt bei jedem ausgefallenen stündlichen Cron-Tick ohne Nachholung aus. Diese Spec überträgt
das Muster des Trip-Pfads (#1725: Fenster von 3 Stunden plus Idempotenz-Vermerk je Slot und
Ortstag) auf den Ortsvergleich, mit demselben Code (Teilungs-Gate) und ohne den Trip-Pfad zu
verändern. Issue #1777, Scheibe S4b aus Epic #1722.

## Source

- **File:** `src/services/compare_slot_scheduler.py`
- **Identifier:** `presets_due_for_hour`; Sammelphase `CompareDispatchStrategy.collect_due`
  (`src/services/dispatch_orchestrator.py`), Versand `_dispatch_due_preset`
  (`src/services/scheduler_dispatch_service.py:151`)
- Kontext: `docs/context/fix-1777-compare-faelligkeit.md`
- Vorbild (Trip): `docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md`
- ADR-0051 (drei Zeitbegriffe, Zone an den Daten), ADR-0044 (Kalendertag folgt der Ortszeit)

## Abgelöste Festlegungen

Diese Spec löst zwei frühere Festlegungen **ausdrücklich ab** (Begründung: ADR-0051 erklärt
Stundengleichheit für Fälligkeit für unzulässig, weil die Ortsstunde an Umstellungstagen nicht
genau einmal existiert):

1. **„Exakte Slot-Stunde, kein Nachholfenster" für die Compare-Anzeige** — Doku
   `src/services/next_briefing.py:195` und Test `tests/tdd/test_next_briefing.py:506-508`
   (AC-9 dort: „18:00 heute (kein Nachholfenster für 07:00)"). Neu gilt: Die Anzeige folgt dem
   Fenster und dem Vermerk wie beim Trip (AC-20).
2. **`due_at_8 == []` bei Slot 07:00** — `tests/tdd/test_compare_preset_slot_dispatch.py:84`
   (Stundengleichheit als Soll). Neu gilt: Ortsstunde 08 liegt im Fenster eines 07:00-Slots
   und ist fällig, solange kein Vermerk vorliegt.

Beide Tests werden bewusst auf das Zielverhalten umgeschrieben; ihr planmäßiges Rot ist Teil
des Vorhabens.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/briefing_slots.py` (`BriefingSlotStore`) | module | Vermerk-Speicher; wird parametriert (Datei, Entity-Typ, ID-Feld) und für den Vergleich wiederverwendet |
| `src/services/trip_report_scheduler.py` | module | Trip-Fensterprädikat `nachhol_fenster_offen` (Z. 355), `NACHHOL_FENSTER_STUNDEN` (Z. 130), `VERMERK_AUSGAENGE` (Z. 111); werden in das geteilte Prädikat bzw. die geteilte Menge gehoben, Verhalten unverändert |
| `src/services/dispatch_orchestrator.py` | module | `CompareDispatchStrategy` (`collect_due`, `pre_pass`, `dispatch_one`) |
| `src/services/scheduler_dispatch_service.py` | module | `_dispatch_due_preset`, `send_one_compare_preset`, Nachhol-Vermerke #2587 (`_mark_compare_undelivered`, `process_compare_pending_markers`, `_catchup_verdict`), Handversand `send_compare_preset` |
| `src/services/compare_alert.py`, `src/services/compare_official_alert.py` | module | Alarm-Sperre „Briefing steht bevor" (#1594) über `check_briefing_imminent` |
| `src/services/next_briefing.py`, `api/routers/internal.py` | module | Anzeige „Nächstes Briefing" |
| `src/services/briefing_log.py` | module | Quelle der Rollout-Ableitung (`entity_type="compare"`, `entity_id`, `kind`, `sent_at`, `on_demand`) |
| `utils.timezone` (`local_dt`, `first_resolvable_tz`), `services.file_lock` | module | Ortszone je Preset (#1726); Dateisperre |
| `internal/store/user.go`, `internal/handler/data_export_test.go` | Go | Liste der Nutzerdateien für Export/Löschung |
| `docs/specs/modules/compare_preset_zeitplan.md`, `fix_1726_ruhezeit_und_zaehler_ortszone.md` | spec | Slot-Modell des Vergleichs; Ortszone des Presets |

## Scope

Schicht: Python-Core (`src/services/`, `api/`) plus zwei Go-Zeilen (Dateiliste). Kein Frontend.

### Affected Files

| File | Change Type | Commit | Description |
|------|-------------|--------|-------------|
| `src/services/briefing_slots.py` | MODIFY | 1 | Klasse parametrieren (`filename`, `entity_type`, `id_key`; Defaults = Trip, byte-gleich); Compare-Ableitung aus `briefing_log.json` über `entity_type=="compare"` + `entity_id`; Lese-Methode für den Ausgang eines Vermerks; geteiltes reines Fensterprädikat + Konstante `NACHHOL_FENSTER_STUNDEN` |
| `src/services/trip_report_scheduler.py` | MODIFY | 1 | `nachhol_fenster_offen` nutzt das geteilte Prädikat; Konstante und `VERMERK_AUSGAENGE` re-exportiert (keine Verhaltensänderung) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | 1 | Ein Schlüssel-Helfer; `_dispatch_due_preset` liefert Ausgang statt bool; reserve/record/release um `send_one_compare_preset`; Cron-`no_weather` schreibt Nachhol-Vermerk; `_catchup_verdict` prüft den Store |
| `src/services/dispatch_orchestrator.py` | MODIFY | 1 | `collect_due`: Vermerk-Filter (`is_recorded_or_claimed`); `dispatch_one`: Zählung nach Ausgang, `no_channels` neutral |
| `internal/store/user.go` | MODIFY | 1 | `briefing_slots_compare.json` in die Nutzerdateien (Export/Löschung) |
| `internal/handler/data_export_test.go` | MODIFY | 1 | Erwartete Dateiliste um die neue Datei ergänzt |
| `src/services/compare_slot_scheduler.py` | MODIFY | 2 | Z. 211/213 `==` wird Fensterprädikat; optionaler read-only Store (Vermerk-Blick) |
| `src/services/compare_alert.py`, `src/services/compare_official_alert.py` | MODIFY | 2 | Alarm-Sperre mit Fenster + `is_recorded` |
| `src/services/next_briefing.py`, `api/routers/internal.py` | MODIFY | 2 | Anzeige „Nächstes Briefing" mit Store read-only, Fenster/überfällig wie beim Trip |
| `tests/tdd/test_compare_preset_slot_dispatch.py` | MODIFY | 2 | Z. 84 (`due_at_8 == []`) auf Fensterverhalten umgeschrieben |
| `tests/tdd/test_next_briefing.py` | MODIFY | 2 | Z. 506 (AC-9 „kein Nachholfenster") auf Fensterverhalten umgeschrieben |
| `tests/tdd/test_compare_preset_send.py` | MODIFY | 1 | Z. 186: Rückgabe ist Ausgang statt bool |
| `tests/tdd/test_compare_faelligkeit_fenster.py` | CREATE | 2 | Fenster, Umstellungstage, Zonen, Mandanten, Alarm, Anzeige |
| `tests/tdd/test_compare_briefing_vermerk.py` | CREATE | 1 | Vermerk, Ausgangs-Abbildung, Rollout, fail-closed, Nachholer, Handversand |

In RED zusätzlich zu prüfen (ungeprüft, Risiko): `test_compare_briefing_nachholen.py`,
`test_dispatch_orchestrator.py`, `test_compare_anchor_target_date.py`,
`test_compare_dispatch_failed_tally.py` und Tests mit `run_compare_presets_daily(hour=6)`.

## Estimated Scope

- **Files:** ~10 produktiv (davon 2 Go-Zeilen), ~6 Testdateien
- **LoC:** produktiv Commit 1 ca. +140/-20, Commit 2 ca. +60/-15 (zusammen unter dem Limit von 250); Tests ca. +300
- **Effort:** high
- **Risiko:** MEDIUM-HIGH (zentraler Versandpfad, berührt die geteilte Trip-Klasse; Fehler bedeutet Doppel- oder Ausfall-Versand)

## Expected Behavior

- **Input:** Cron-Lauf (Go → `POST /api/scheduler/*`) zur vollen Stunde; je Preset Slots (Morgen/Abend), Wochentage und Ortszone aus dem ersten auflösbaren Ort.
- **Output:** Ein Preset-Slot wird versendet, wenn die Ortsstunde im Fenster `stunde <= ortsstunde < stunde + 3` liegt und für `(preset_id, slot, ortstag)` noch kein Vermerk besteht — höchstens einmal je Ortstag.
- **Side effects:** Vermerk in `data/users/<user_id>/briefing_slots_compare.json` (reserve → record bzw. release); bei `no_weather` zusätzlich ein Nachhol-Vermerk; Handversand und Befehle schreiben keinen Vermerk.

### Zwei Commits in einem PR

Wie bei #1725 wird der gefährliche Zustand „offenes Fenster ohne wirksamen Vermerk"
unerreichbar gemacht:

- **Commit 1 (Vermerk bei unverändertem `==`):** Speicher, Ableitung, Filter, reserve/record/release,
  Nachholer-Prüfung, Go-Dateiliste. Die Fälligkeit bleibt Stundengleichheit; der Filter ist dabei
  ein No-op außer an der Herbst-Doppelstunde. Verhaltensneutral bis auf zwei bewusste Änderungen:
  `no_channels` zählt neutral, und `no_weather` im Cron schreibt einen Nachhol-Vermerk.
- **Commit 2 (Fenster + Alarm/Anzeige):** `==` wird `stunde <= ortsstunde < stunde + 3`;
  Alarm-Sperre und Anzeige ziehen nach.

Jeder Zwischenstand ist auslieferbar; ein Bisect landet nie im Zustand „Fenster ohne Schutz".

## Nicht-Scope

- **Trip-Pfad:** bleibt im Verhalten byte-gleich (AC-23); keine Änderung seiner Fälligkeit, seiner Datei `briefing_slots.json` oder seiner Rollout-Semantik.
- **Mitternachts-Überlauf:** kein Fenster über Ortsmitternacht (Slot 23:00 gilt nur 23:00-23:59), Parität zum Trip.
- **Go-Cron:** der ausfallende bzw. doppelte Tick an Umstellungstagen (`internal/scheduler/scheduler.go`, `robfig/cron`) wird nicht repariert, sondern durch Fenster + Vermerk aufgefangen.
- **Handversand/Befehle** (`send_compare_preset`, `on_demand=True`): unverändert.
- **Kein `seeded_at`-Sondermechanismus** für den Rollout: das wäre eine stille Abweichung von der PO-Entscheidung 2026-08-11 (enge Lesart, Docstring in `briefing_slots.py`) und müsste für beide Pfade gelten (eigenes Ticket, falls je gewünscht).
- **Retention/Prune** von `briefing_slots_compare.json` (Nachfolge-Arbeit, wie beim Trip).
- **Wetterabruf-Kontingent bei `channels_unreachable`** (#1329): bewusst in Kauf genommen, wie beim Trip.
- **Frontend/UI:** keine Änderung; die Anzeige „Nächstes Briefing" bekommt nur andere Daten vom internen Endpoint.

## Implementation Details

### Design

**Speicher: Variante B — dieselbe Klasse `BriefingSlotStore`, parametriert, eigene Datei
`briefing_slots_compare.json`.** Eintragsfeld `preset_id` statt `trip_id`; Konstruktor-Parameter
`filename`, `entity_type`, `id_key` mit Trip-Defaults.

Begründung:
- Teilungs-Gate (CLAUDE.md, Trip/Ortsvergleich ein Code) erfüllt: ein Code für reserve/record/release, fail-closed, Claim-TTL (900 s), Reparatur #2231, Rückwärts-Ableitung.
- Der Trip-Pfad bleibt über die Defaults byte-gleich.
- Eine Kollision gleicher IDs zwischen Trip und Preset ist konstruktionsbedingt ausgeschlossen (vgl. #2281 AC-5).
- Die Compare-Datei fehlt beim Rollout; damit greift die vorhandene Rückwärts-Ableitung („nur solange die eigene Datei fehlt") für den Vergleich unverändert.

Verworfene Varianten:
- **A — gleiche Datei mit Typfeld:** höchstes Regressionsrisiko für den Trip-Pfad; die Existenz-Bedingung der Ableitung greift für den Vergleich nie, weil `briefing_slots.json` durch Trips schon existiert (kein Rollout-Schutz).
- **C — eigene Klasse:** verletzt das Teilungs-Gate (zwei Codes für dieselbe Idempotenz).

**Rollout-Ableitung:** identische Semantik wie beim Trip (enge Lesart, PO-Entscheidung 2026-08-11).
Log-Einträge zählen nur bei `entity_type=="compare"`, passender `entity_id`, `kind`=Slot,
`on_demand` nicht gesetzt und `sent_at` im Ortstag der Preset-Zone.

**Ein Schlüssel-Helfer:** `(preset_id, slot, ortstag)` entsteht aus EINER
`_preset_ortszeit`-Auflösung (Ortstag und Ortsstunde aus derselben Zone, #1726). Derselbe
Helfer dient `collect_due`-Filter, `reserve`, `_catchup_verdict`-Prüfung und Log-Ableitung
(`zone` = Preset-Zone). Weicht eine Stelle ab, entsteht stiller Doppelversand.

**Fenster:** geteiltes reines Prädikat und Konstante (3 h) in `briefing_slots.py`, von Trip und
Compare genutzt. Das Weekly-Gate prüft den Ortstag des Laufs.

**Ein Prädikat für Sammellauf, Alarm-Sperre und Anzeige** (#1969-AC-11-Parität): der Sammellauf
nutzt `is_recorded_or_claimed`, Alarm-Sperre und Anzeige `is_recorded` (sonst schwiege der
Alarm bis 3 h nach einem zugestellten Briefing).

**Ausgangs-Abbildung (Compare liefert Ausnahmen statt Ausgangs-Strings):**

| Versandergebnis in `send_one_compare_preset` | Ausgang | Vermerk |
|---|---|---|
| Rückkehr ohne Ausnahme | `sent` | `record_outcome` |
| `SendOutcomeError` mit `code=="no_channels"` | `no_channels` | `record_outcome`; zählt neutral |
| `SendOutcomeError` mit `code=="no_weather"` | `no_weather` | `record_outcome` UND Nachhol-Vermerk |
| `SendOutcomeError` mit `code=="channels_unreachable"` | `channels_unreachable` | `release` (Retry im Fenster) |
| sonstige `ValueError`/Ausnahme | Fehler | `release`, als fehlgeschlagen gezählt |
| unbekannter Code | unbekannt | `record_outcome` (sperren, Trip-Parität) |

Vermerkt werden `sent`, `no_channels`, `no_weather` (geteilte `VERMERK_AUSGAENGE`; `no_stage`
existiert im Vergleich nicht). Beide Aufrufer der bisherigen bool-Funktion
(`dispatch_orchestrator.py:226` und `tests/tdd/test_compare_preset_send.py:186`) werden explizit
angepasst; kein truthy-Vergleich auf Strings.

**`no_weather` im Cron:** heute schreibt der Cron dafür keinen Nachhol-Vermerk (der Raise liegt
vor dem Versand-`try`), ein kurzer Wetterausfall lässt den Vergleich ersatzlos ausfallen. Neu:
vermerken UND Nachhol-Vermerk schreiben (Trip-Parität, dort deckt der Pending-Marker die
Nachlieferung). Das schließt diese Lücke nebenbei.

**Nachholer-Regel (#2587):** `_catchup_verdict` prüft zusätzlich den Store. Hat der Slot den
Ausgang `sent`, lautet das Verdict „drop". Bei `no_weather`/`no_channels` wird NICHT gedroppt
(dort ist der Marker der Retry). Hintergrund: Mit Fenster und Vermerk-Filter fehlt ein bereits
versendeter Slot in `due_keys`; bliebe ein Marker ungeräumt (`_clear_compare_dispatch_error`
ist fail-soft), ergäbe das Verdict „send" einen Doppelversand. Bei `channels_unreachable`
schreibt `send_one_compare_preset` bereits einen Nachhol-Vermerk, und der Slot wird per
`release` im Fenster wieder fällig; die Regel „wait, solange der reguläre Slot fällig ist"
verhindert das Doppel.

**Handversand/Befehle:** `send_compare_preset` (`on_demand=True`) schreibt keinen Vermerk und
wird nicht vom Vermerk blockiert; die Log-Ableitung überspringt `on_demand`. Die Trennung
entsteht über den Aufrufer: reserve/record/release liegen ausschließlich in `_dispatch_due_preset`.

**Manueller Auslöser `run_compare_presets_daily(?hour=)`:** läuft über denselben Sammelpfad
inklusive Vermerk, kein Sonderpfad.

**Teilungs-Gate-Hinweis (Trip/Vergleich ein Code):** erfüllt durch die parametrierte
`BriefingSlotStore` und das geteilte Fensterprädikat samt Konstante. Compare-eigen bleiben nur
Schlüssel-Helfer (Preset-Zone) und die Ausgangs-Abbildung, weil Compare Ausnahmen statt
Ausgangs-Strings liefert.

**Querschnitts-Prüfpunkte:**
- *Mandantentrennung:* Speicher je `user_id` unter `data/users/<user_id>/`; `user_id` aus dem Auslöser-Kontext, nie `"default"`; Test mit zwei Nutzern (AC-8).
- *Kanäle:* betrifft die Fälligkeit des Versands, nicht den Inhalt; gilt für alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) gleichermaßen, weil der Vermerk pro Briefing und nicht pro Kanal gesetzt wird. Ein Briefing, das auf keinem Kanal ankommt (`channels_unreachable`), wird im Fenster erneut versucht.

### Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Fenster ohne wirksamen Vermerk ⇒ stündlicher Serienversand an echte Empfänger (inkl. Premium-SMS) | zwei Commits; Vermerk zuerst scharf (AC-4 bis AC-12 laufen schon in Commit 1) |
| Schlüssel an einer Stelle abweichend (UTC- statt Ortstag, anderer Slot-Name) ⇒ stiller Doppelversand oder Ausfall | ein Schlüssel-Helfer; Mutation „Ortstag aus UTC" im Adversary |
| Rollout-Restfenster: existiert `briefing_slots_compare.json` schon, bevor der Log-Eintrag des Tages geprüft wurde, greift die Ableitung nicht | bewusst akzeptiert (PO 2026-08-11); durch Variante B für den Vergleich praktisch nur beim allerersten Lauf relevant |
| Doppel zwischen Nachholer (#2587) und regulärem Fensterversand | Nachholer-Regel, AC-14/AC-15 |
| Semantik-Wechsel für Mitnutzer von `presets_due_for_hour` (Alarm-Sperre, Anzeige) | Commit 2 zieht beide mit; AC-19/AC-20 |
| Berührung der geteilten Trip-Klasse | Defaults byte-gleich; AC-23 misst den Trip-Pfad |
| Fensterbreite nur an einem ausgefallenen Tick messbar (bei funktionierendem Vermerk liefert jede Breite am Normaltag genau einen Treffer) | AC-3 prüft H+1/H+2 fällig und H+3 nicht; Schwelle am Nachbarwert |
| `skip_next`/Aktiv-Filter ändert sich still, wenn der Filter vor die Aktivprüfung gezogen wird | Filter nach der Aktivprüfung, in der Sammelphase (Prüfort = Wirkort) |

### RED-Nachtrag: weitere abgelöste Bestandstests (2026-11-01)

In RED aufgedeckt; folgen ohne neue Entscheidung aus den freigegebenen ACs und ergänzen die
Liste „Abgelöste Festlegungen" (1, 2):

3. **„Ortsvergleich kennt keinen Vermerk"** — `tests/tdd/test_briefing_slot_idempotenz.py::test_t11`
   (Compare-Fall in der Trip-Testdatei). Neu: Fenster + Vermerk ergeben genau einen Versand
   (AC-2, AC-21). Die Trip-Tests dieser Datei bleiben unverändert (AC-23).
4. **„Keine Wetterdaten hinterlassen keinen Vermerk"** — `tests/tdd/test_compare_briefing_nachholen.py::test_ac2_…`
   (Fall `fehler_je_ort`). Neu gilt AC-12. Der Fall „Ausnahme überall" bleibt (release, AC-17).
5. **Stundengleichheit in der Einstellungs-Kette** — `tests/tdd/test_compare_einstellung_auslieferung_kette.py::test_slot_stunde_gilt_in_der_ortszeit_des_presets_je_nutzer`
   (08:00 Wien bei Slot 07:00 `== []`). Neu: fällig; erst H+3 nicht mehr (AC-3).
6. **bool-Rückgabe von `_dispatch_due_preset`** — real vier Aufrufer, zusätzlich
   `test_compare_briefing_nachholen.py` (`test_ac11_…`, `test_f004_…`): `is True` → `== "sent"`.

Schnittstelle: `now_utc: datetime | None = None` (Default = jetzt) für `_dispatch_due_preset` und
`dispatch_one`; bestehende Aufrufer ohne `now_utc` bleiben gültig. Der Compare-Speicher liegt wie
beim Trip unter `get_data_dir(user_id)`; `"default"` wird nicht fail-closed gesperrt (Tests
461/511 nutzen es mit eigenem `data_root`). Vorbestehend rot und nicht Teil von #1777:
`test_issue_511_weekly_scheduler.py` (zwei Tests, Logtext seit i18n-`InvalidPresetError`).

### Geplante Tests (Kern-Schicht, deterministisch, ohne Netz)

- Zeit wird als Parameter (`now_utc`) hereingereicht, keine Patches auf die Systemuhr; kein `Mock()`/`patch()`, das nur die eigene Annahme spiegelt. Echte `BriefingSlotStore`-Dateien in `tmp_path`.
- Testdateien nach Verhalten benannt (nicht nach Issue-Nummer, `test_naming_gate.py`): `tests/tdd/test_compare_faelligkeit_fenster.py`, `tests/tdd/test_compare_briefing_vermerk.py`. Prüfling relativ zur Testdatei aufgelöst.
- Fensterbreite am ausgefallenen Tick messen, nicht am Treffer-Zählen; Versandversuche zählen statt gesammelter Zeilen, wo der vermerk erst nach der Sammlung entsteht.
- `uv run pytest` nur mit benannten Testdateien.

**Mutationsziele für den Adversary** (String-Ersetzung mit externer Sicherungskopie, nie `git checkout/stash/reset`):
1. Fenster `3` auf `4` (und auf `2`, `1`, „bis Tagesende") — AC-3 muss rot werden.
2. `is_recorded_or_claimed` im Sammellauf entfernt — Herbst-Doppel (AC-2) muss rot werden.
3. `release` statt `record_outcome` bei `no_weather` — AC-12 muss rot werden.
4. `record_outcome` statt `release` bei `channels_unreachable` — AC-13 muss rot werden.
5. Schlüssel-Ortstag aus UTC statt Preset-Zone — AC-5, AC-6 und AC-9 müssen rot werden.
6. Schlüsselglieder einzeln entfernen (`slot`, `ortstag`, `preset_id`) — AC-4, AC-5, AC-8.
7. Rollout-Ableitung entfernt bzw. `on_demand`-Filter entfernt — AC-9, AC-10.
8. `_catchup_verdict` ohne Store-Prüfung — AC-14.
9. Alarm-Sperre mit `is_recorded_or_claimed` statt `is_recorded`, bzw. ohne Vermerk-Blick — AC-19.
10. Fail-open statt fail-closed bei Sperren-Timeout — AC-16.
11. Vermerk im Handversand gesetzt — AC-22.
12. Standardwerte der parametrierten Klasse verändert (Trip schreibt in die Compare-Datei) — AC-23.

Leitfrage je Mutation: ist die Zusicherung dort geprüft, wo sie WIRKT?

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit Morgen-Briefing 02:00 in einer Zone mit Frühjahrs-Umstellung (Europe/Paris, 29.03.2026, Ortsstunde 02 existiert nicht) / When der Versandlauf diesen Ortstag stündlich durchläuft / Then wird der Vergleich genau einmal fällig und versendet, nämlich bei Ortsstunde 03, statt ersatzlos auszufallen.
  - Test: Nutzer stellt Vergleich auf 02:00, an der Umstellung kommt das Briefing trotzdem einmal an.

- **AC-2:** Given derselbe Vergleich am Herbst-Umstellungstag (25.10.2026, Ortsstunde 02 kommt zweimal vor) / When beide Vorkommen der Ortsstunde 02 im Lauf durchschritten werden / Then geht das Briefing genau einmal an die Empfänger, das zweite Vorkommen wird durch den Vermerk gefiltert.
  - Test: Zwei Sammelläufe mit zwei UTC-Zeitpunkten derselben Ortsstunde, ein Versandversuch.

- **AC-3:** Given ein Vergleich mit Slot-Stunde H, dessen stündlicher Tick ausgefallen ist / When der nächste Lauf in Ortsstunde H+1 bzw. H+2 stattfindet / Then ist der Vergleich fällig und wird nachgeholt, und When der nächste Lauf erst in Ortsstunde H+3 stattfindet / Then ist er nicht mehr fällig (Fenster genau 3 Stunden, in beide Richtungen geprüft).
  - Test: Drei Läufe an den Nachbarwerten; Mutation Fenster 3 auf 4 wird rot.

- **AC-4:** Given ein Vergleich mit Morgen- und Abend-Slot, beide auf dieselbe Stunde gestellt / When diese Ortsstunde erreicht wird / Then werden beide Slots unabhängig voneinander versendet und vermerkt, und der Vermerk des einen blockiert den anderen nicht.
  - Test: Zwei Versandversuche in einem Lauf.

- **AC-5:** Given ein Nutzer mit zwei Vergleichen in verschiedenen Zonen (z. B. Europe/Paris und America/New_York) und gleicher Slot-Stunde / When der Versandlauf zu einem UTC-Zeitpunkt läuft / Then wird jeder Vergleich nach seiner eigenen Ortsstunde und seinem eigenen Ortstag beurteilt und höchstens einmal je Ortstag versendet.
  - Test: Ein UTC-Moment, in dem nur eine der beiden Ortsstunden im Fenster liegt; Mutation „Ortstag aus UTC" wird rot.

- **AC-6:** Given ein Vergleich, dessen Morgen-Slot an zwei aufeinanderfolgenden Ortstagen fällig wird / When der Lauf am zweiten Ortstag stattfindet / Then ist der Vergleich erneut fällig; der Vermerk des Vortags blockiert den neuen Tag nicht.
  - Test: Zwei Tage hintereinander, zwei Versandversuche.

- **AC-7:** Given zwei verschiedene Vergleiche mit gleicher Zone und gleicher Slot-Stunde / When die Ortsstunde erreicht wird / Then werden beide unabhängig versendet; der Vermerk des einen Vergleichs blockiert den anderen nicht.
  - Test: Zwei Versandversuche; Mutation „preset_id aus dem Schlüssel entfernen" wird rot.

- **AC-8:** Given zwei verschiedene Nutzer mit je einem Vergleich gleicher ID und Slot-Stunde / When der Versandlauf für beide läuft / Then führt jeder Nutzer seinen eigenen Vermerk unter `data/users/<user_id>/briefing_slots_compare.json`, und der Versand an den einen Nutzer blockiert den anderen nicht.
  - Test: Zwei Nutzer, zwei getrennte Dateien, zwei Versandversuche.

- **AC-9:** Given `briefing_slots_compare.json` existiert noch nicht (Rollout), aber `briefing_log.json` trägt für den Vergleich einen Eintrag mit `entity_type="compare"`, passender `entity_id` und Slot-Art, dessen Sendezeitpunkt im aktuellen Ortstag der Preset-Zone liegt / When die Fälligkeit geprüft wird / Then gilt der Slot als erledigt und wird nicht erneut versendet.
  - Test: Log-Eintrag vom Ortstag, kein zweiter Versand; ein Eintrag vom Vortag zählt nicht.

- **AC-10:** Given dieselbe Ausgangslage, aber der Log-Eintrag stammt von einem Handversand (`on_demand=true`) oder gehört zu einem Trip mit gleicher ID / When die Fälligkeit geprüft wird / Then blockiert er den regulären Slot nicht, und der Vergleich ist fällig.
  - Test: Fremder Typ und on_demand-Eintrag werden von der Ableitung übersprungen.

- **AC-11:** Given ein Versandversuch endet mit `sent`, `no_channels` oder `no_weather` / When der Versuch abgeschlossen ist / Then ist für diesen Slot an diesem Ortstag ein Vermerk gesetzt und er wird in den übrigen Stunden des Fensters nicht erneut verarbeitet; `no_channels` zählt dabei neutral und nicht als Fehler.
  - Test: Ausgangs-Matrix; die Fehlerzählung bleibt bei `no_channels` unverändert.

- **AC-12:** Given der Versand scheitert an fehlenden Wetterdaten (`no_weather`) / When der Cron-Lauf endet / Then ist der Slot vermerkt UND ein Nachhol-Vermerk (#2587) geschrieben, sodass die Nachlieferung über den Marker erfolgt und der Vergleich bei kurzem Wetterausfall nicht ersatzlos ausfällt.
  - Test: Nach `no_weather` existieren Vermerk und Nachhol-Marker; die folgende Stunde sendet nicht doppelt.

- **AC-13:** Given kein Kanal des Nutzers ist erreichbar (`channels_unreachable`) / When der Lauf endet / Then bleibt der Vermerk aus (release), der nächste Lauf innerhalb des Fensters versucht den Versand erneut, und zusammen mit dem Nachhol-Vermerk entsteht dabei kein doppeltes Briefing.
  - Test: Zweiter Lauf in H+1 sendet genau einmal; Mutation „record statt release" wird rot.

- **AC-14:** Given ein Nachhol-Marker ist ungeräumt geblieben, obwohl der Slot am Ortstag bereits mit `sent` vermerkt ist / When der Nachholer den Marker bewertet / Then verwirft er ihn ohne Versand (kein Nachhol-Doppel); bei Ausgang `no_weather` oder `no_channels` verwirft er den Marker dagegen nicht, weil dort der Marker der Retry ist.
  - Test: Marker + Slot `sent` ⇒ kein Versand; Marker + `no_weather` ⇒ Versand.

- **AC-15:** Given der reguläre Slot ist im Fenster aktuell fällig und es liegt ein Nachhol-Marker vor / When der Nachholer bewertet / Then wartet er („wait") und der reguläre Fensterversand sendet; es entsteht kein zweites Briefing für denselben Slot und Ortstag.
  - Test: Genau ein Versand über Nachholer und Fenster zusammen.

- **AC-16:** Given die Schreibsperre auf `briefing_slots_compare.json` ist innerhalb der Frist nicht zu bekommen / When ein Vergleich zum Versand ansteht / Then wird nicht gesendet (fail-closed), statt ohne wirksamen Vermerk zu senden.
  - Test: Gehaltene Sperre im selben Prozess (`flock`), `LOCK_TIMEOUT_SECONDS` zur Laufzeit gelesen; kein Versand.

- **AC-17:** Given ein Versand schlägt mit einer Ausnahme fehl (z. B. `ValueError` für Skip-Pfade) / When der Lauf endet / Then ist die Reservierung zurückgenommen, der Vergleich zählt als fehlgeschlagen, die übrigen Vergleiche des Laufs werden weiter versendet (Fehlerisolation #2217).
  - Test: Zwei Vergleiche, einer wirft; der andere kommt an, der erste ist im Fenster erneut fällig.

- **AC-18:** Given ein Vergleich, dessen Wochentag-Gate (Weekly) am Laufstag nicht zutrifft / When der Lauf in einer Stunde des Fensters stattfindet / Then ist er nicht fällig; das Fenster läuft nicht über Ortsmitternacht (Slot 23:00 gilt nur bis 23:59).
  - Test: Weekly an falschem Ortstag stumm; Slot 23 um 00:30 nicht fällig.

- **AC-19:** Given ein Vergleich, dessen Briefing um 07:00 bereits zugestellt wurde / When um 08:00 ein Wetter- oder amtlicher Alarm für diesen Vergleich ansteht / Then schweigt die Alarm-Sperre „Briefing steht bevor" (#1594) nicht weiter und der Alarm geht raus; ein noch nicht zugestelltes Briefing im Fenster hält den Alarm dagegen zurück.
  - Test: Mit Vermerk ⇒ Alarm erreicht die Kanäle; ohne Vermerk im Fenster ⇒ gesperrt.

- **AC-20:** Given ein Nutzer sieht die Anzeige „Nächstes Briefing" für einen Vergleich / When der Slot im Fenster liegt und noch nicht vermerkt ist / Then zeigt die Anzeige das Briefing als fällig bzw. überfällig an (wie beim Trip), und When der Slot bereits vermerkt ist / Then zeigt sie den nächsten Slot. Die frühere Festlegung „exakte Slot-Stunde, kein Nachholfenster" ist abgelöst.
  - Test: Anzeige 08:30 bei Slot 07:00 ohne Vermerk zeigt fällig/überfällig, mit Vermerk den Abend-Slot.

- **AC-21:** Given ein Vergleich wird über den manuellen Auslöser `run_compare_presets_daily(?hour=)` angestoßen / When für dieselbe Ortsstunde ein zweites Mal ausgelöst wird / Then läuft der Aufruf über denselben Sammelpfad inklusive Vermerk und sendet nicht doppelt.
  - Test: Zwei Aufrufe mit gleichem `hour`, ein Versand.

- **AC-22:** Given ein Nutzer löst einen Handversand (Befehl HEUTE/MORGEN oder „Senden" mit `on_demand=True`) aus / When der Versand läuft / Then schreibt er keinen Vermerk und wird auch von keinem Vermerk blockiert; der reguläre Slot bleibt fällig und ein Handversand nach dem regulären Versand funktioniert weiter.
  - Test: Handversand vor und nach dem Slot; Vermerk-Datei unverändert.

- **AC-23:** Given der Trip-Briefing-Pfad / When er nach dieser Änderung über 24 Stunden und die Umstellungstage läuft / Then ist sein Fälligkeitsergebnis, seine Datei (`briefing_slots.json`), sein Schlüssel `trip_id` und seine Rollout-Ableitung byte-gleich zum Stand davor.
  - Test: Bestehende Trip-Tests (`test_briefing_slot_fail_closed.py`, `test_briefing_slot_reparatur.py`, `test_briefing_slot_idempotenz.py` — dort nur der Compare-Fall T11 neu gefasst, siehe „Abgelöste Festlegungen" Nr. 3) bleiben unverändert grün; Mutation „Trip-Default auf Compare-Datei" wird rot.

- **AC-24:** Given ein Nutzer exportiert oder löscht seine Daten über die Go-API / When die Nutzerdateien aufgelistet werden / Then enthält die Liste `briefing_slots_compare.json`, sodass Export und Löschung die neue Datei erfassen.
  - Test: Go-Test `data_export_test.go` erwartet die Datei in Export und Löschung.

## Known Limitations

- Rollout-Restfenster (enge Lesart, PO-Entscheidung 2026-08-11): Hat ein anderer Eintrag die Compare-Datei schon angelegt, bevor der Log-Eintrag des Tages berücksichtigt wurde, greift die Ableitung nicht. Für den Vergleich praktisch nur beim ersten Lauf relevant.
- Kein Mitternachts-Überlauf des Fensters (Trip-Parität).
- `briefing_slots_compare.json` wächst unbegrenzt (Prune als Nachfolge-Arbeit); die Datei darf nie committet werden (`data/` bleibt untracked).
- Die Fangkraft der Tests ist bis zur Mutations-Gegenprobe in Phase 6b hergeleitet, nicht gemessen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0051, ADR-0044
- **Rationale:** ADR-0051 nennt den Idempotenz-Schlüssel `(entity_id, ortstag, slot)` und verbietet Stundengleichheit für Fälligkeit; ADR-0044 bindet den Kalendertag an die Ortszeit. Diese Spec wendet beide Regeln auf den Ortsvergleich an und führt keine neue Entscheidungsfläche ein; ein neues ADR ist nicht nötig. Die abgelösten Festlegungen (Abschnitt „Abgelöste Festlegungen") folgen aus ADR-0051, nicht aus einer neuen Entscheidung.

## Changelog

- 2026-11-01: RED-Nachtrag: abgelöste Festlegungen 3–6 (Bestandstests, die den freigegebenen ACs widersprechen); `now_utc` optional; keine AC-Änderung.
- 2026-11-01: Initial spec created (Issue #1777, S4b aus Epic #1722), aus `docs/context/fix-1777-compare-faelligkeit.md` auf Basis der Vorlage `fix_1725_faelligkeit_und_idempotenz.md`.
