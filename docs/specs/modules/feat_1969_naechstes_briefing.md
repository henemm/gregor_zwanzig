---
entity_id: feat_1969_naechstes_briefing
type: module
created: 2026-10-23
updated: 2026-10-23
status: draft
version: "1.0"
tags: [briefing, scheduler, versand-tab, adr-0051, ortszone, epic-2507, trip, ortsvergleich]
---

# Nächstes Briefing — echter Versandzeitpunkt pro Trip und Ortsvergleich

## Approval

- [ ] Approved

## Purpose

Nutzer sehen pro Trip und pro Ortsvergleich, **wann ihr nächstes Briefing tatsächlich verschickt wird** (Wochentag, Uhrzeit HH:00, Zonenkürzel der Trip- bzw. Ortszone) — oder, wenn nichts ansteht, den Grund. Die Ableitung entsteht genau einmal im Python-Core und nutzt dieselben Prädikate wie der Scheduler; die drei heutigen, voneinander abweichenden Eigenrechnungen (Frontend `deriveNextSend`, Mail-Fuß `_compute_next_send`, fest verdrahtete Zeiten in der Trip-Karte) entfallen.

Issue: #1969 (letztes offenes Unter-Issue von Epic #2507). Kontext/Analyse: `docs/context/feat-1969-naechstes-briefing.md`.

## Abweichung vom Ticket

Das Ticket nennt die **Konto-Seite**. Dort steht heute „Trip-Checks / Nächste Prüfung" (`frontend/src/routes/account/+page.svelte`, Quelle `/api/scheduler/status/me`). Das ist der **stündliche Prüftakt des Go-Schedulers** (`trip_reports_hourly`) und kein Versandzeitpunkt: Der Versand hängt je Trip an Slot-Stunde, Ortszone, Pausen, Etappen am Zieltag und Idempotenz — alles Python-Wissen, das der Prüftakt nicht kennt. Eine Anzeige dort bliebe zwangsläufig falsch oder mehrdeutig, und ein Nutzer mit mehreren Trips hätte keine Zuordnung.

Festlegung (Tech-Lead-Entscheid, begründet):

1. **Ort der Anzeige:** pro Trip/Vergleich im **geteilten Versand-Reiter** (`VersandTab`, Parameter `context`), zusätzlich in der **HubOverview-Karte** des Trips (heute fest 06:00/18:00 — bereits sichtbar falsch). Dort entscheidet der Nutzer über Uhrzeiten und sieht sofort deren Wirkung.
2. **Ersatz der Alt-Rechnungen** (Epic-Regel: Reste nie abspalten): Startseite „Was geht raus", Vergleichsliste, Ortsvergleich-Detail und Compare-Mail-Fuß lesen denselben Backend-Wert (S3). Danach gibt es genau EINE Rechnung.
3. **Konto-Zeile „Nächste Prüfung" bleibt unverändert** (Wert, Berechnung, Beschriftung). Sie ist der Prüftakt des Systems und hat als solcher ihre Berechtigung (Observability, #2149). Sie wird bewusst **nicht** zum Versandzeitpunkt umgedeutet und **nicht** mit der neuen Ableitung vermischt — zwei Begriffe, zwei Orte. Kein Code in `account/+page.svelte` in diesem Ticket.

## Source

- **Python-Core (maßgeblich):**
  - `src/services/next_briefing.py` (NEU) — `next_trip_briefing(trip, now_utc, slot_store, strict_after=False)`, `next_compare_briefing(preset, locations, now_utc, strict_after=False)`
  - `src/services/trip_report_scheduler.py` — Prädikat aus `trip_briefing_due_at` / `_get_active_trips` in freie Funktion (verhaltensneutral)
  - `src/services/compare_slot_scheduler.py` — `presets_due_for_hour` wiederverwendet; Grund-Ermittlung als freie Funktion
  - `api/routers/internal.py` — `GET /api/_internal/next-briefings`
  - `src/output/renderers/email/compare_html.py` — `_compute_next_send` / `_render_abo_footer` (S3)
- **Go-API:** `internal/handler/proxy.go`, `internal/router/router.go` — `GET /api/next-briefings` (Muster `StagesWeatherProxyHandler`)
- **Frontend:** `frontend/src/lib/components/shared/VersandTab.svelte` + neuer geteilter Baustein unter `frontend/src/lib/components/shared/versand-tab/`; `frontend/src/lib/components/trip-detail/HubOverview.svelte`; `frontend/src/lib/utils/cockpitHelpers568.ts` (`deriveNextSend`, `resolvePresetSlots`, `primarySendSlot`); `frontend/src/lib/components/compare/CompareTabs.svelte`; `frontend/src/lib/components/molecules/CompareStatusRow.svelte`; `frontend/src/routes/+page.svelte`; `frontend/src/routes/_home/cockpitHelpers.ts`; `frontend/src/lib/components/compare/subscriptionHelpers.ts` (`formatNextSend`); `+page.server.ts` von Trip-Detail, Compare-Detail und Startseite

> Schicht-Hinweis: Die Fälligkeit wird ausschließlich in Python entschieden (Go tickt nur stündlich, `internal/scheduler/scheduler.go`). Go ist hier reiner authentifizierender Proxy, das Frontend reiner Konsument.

## Estimated Scope

- **LoC:** ~550–650 produktiv (Python ~250, Go ~50, Frontend ~250–350), ohne Tests. Das liegt über dem Standardlimit 250 und über dem Override 500. **`workflow.py set-field loc_limit_override 800` wird in `/40` bzw. `/50` gesetzt** (nicht schöngerechnet, nicht abgespalten — Epic-Regel).
- **Files:** ~20, davon ~8 Tests
- **Effort:** high
- **Risiko:** MEDIUM — neue Logik ist rein lesend; der Refactor berührt die Versand-Fälligkeit (gesichert durch Bestandstests, AC-12) und der Mail-Fuß löst Renderer-Commit-Gate und `email_spec_validator.py` aus.

## Scheiben (alle in dieser Spec, in dieser Reihenfolge)

| Scheibe | Inhalt |
|---|---|
| **S1** | Python-Refactor (Prädikat frei) → `next_briefing.py` → `_internal`-Endpoint → Go-Proxy; danach Ausgabeformat eingefroren (für #2346) |
| **S2** | Anzeige „Nächstes Briefing" im geteilten Versand-Reiter (Trip + Ortsvergleich), HubOverview-Karte mit echten Zeiten |
| **S3** | Ablösung `deriveNextSend` + Konsumenten + Fallbacks 06/07, toter Code, Compare-Mail-Fuß |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig` / `slot_aktiv` (`src/app/models.py`) | Datenmodell | Slots, Zeiten, `paused_until`, `skip_next` |
| `trip_day.anchor_tz` / `trip_local_now` (`src/services/trip_day.py`) | Zonenauflösung | Zone je Kandidatentag, Fallback UTC |
| `BriefingSlotStore` (`src/services/briefing_slots.py`) | Idempotenz (nur lesen) | bereits vermerkter heutiger Slot |
| `compare_slot_scheduler.presets_due_for_hour`, `resolve_preset_slots` | Ortsvergleich-Fälligkeit | exakte Stunde, Wochentag, `end_date` |
| `compare_alert_guard.is_silenced` | Sperre | `paused_at`, `schedule=="manual"`, `archived_at` |
| Loader `load_all_trips(user_id)`, `load_compare_presets(user_id)` | Persistenz | nutzerbezogene Objekte |
| ADR-0051, ADR-0044, ADR-0062 | Entscheidungen | Zone an den Daten; Kalendertage in Ortszeit; Core-Auth Go→Python |
| Epic #2345 (Teilung Trip/Ortsvergleich) | Invariante | geteilter Baustein statt Compare-only-Komponente |
| #2346 (Startseiten-Kachel) | Konsument | verdrahtet sich auf `GET /api/next-briefings` |

## Implementation Details

### Ausgabeformat (mit S1 eingefroren — Vertrag für #2346)

Pro Trip/Vergleich ein Objekt `NextBriefing`:

```
{
  at:          ISO-8601 mit Offset | null,   // z. B. "2026-10-24T07:00:00+02:00"
  local_date:  "2026-10-24",                  // Ortstag in der Zone von `tz`
  local_time:  "07:00",                       // immer HH:00
  tz:          "Europe/Paris",                // IANA; Fallback "UTC"
  tz_abbr:     "CEST",                        // Kürzel dieses Kandidatentags (DST-Offset!)
  slot:        "morning" | "evening",
  skipped?:    { local_date, local_time, slot },  // nur bei skip_next: der übersprungene Termin
  overdue?:    true,                          // heutiger Slot, Nachholfenster offen, noch nicht vermerkt
  reason?:     "manual" | "paused" | "disabled" | "ended" | "none",
  paused_until?: "2026-10-28"                 // nur bei reason "paused" mit Datum
}
```

- `at == null` ⇒ `reason` ist Pflicht; bei `at != null` entfällt `reason`.
- Sammelantwort `GET /api/next-briefings` → `{ "trips": { "<trip_id>": NextBriefing }, "compare": { "<preset_id>": NextBriefing } }`; optional `?trip_id=` bzw. `?preset_id=` schränkt auf ein Objekt ein.
- **Kein Feld am Trip-/Preset-JSON:** `GET /api/trips` und `GET /api/compare/presets` liefert Go allein aus dem Store — ein Feld dort hieße Go→Python pro Objekt (N+1) und berührt den ETag der Objekte; ADR-0051 Regel 1 verbietet zudem persistierte vorausberechnete Zeitpunkte. **Nichts wird persistiert.**

### Ableitung (keine neue Fälligkeitsregel)

1. **Prädikat teilen:** Die Ausschlüsse aus `trip_briefing_due_at` und `_get_active_trips` (Etappe am Zieltag: morning = Ortstag, evening = Ortstag+1; `paused_at`; `paused_until`; `slot_aktiv`; Nachholfenster `stunde <= ortsstunde < stunde+3`; `is_recorded_or_claimed`) werden in eine freie Funktion gezogen. Scheduler, Alarm-Sperre (`trip_alert.py`) und Anzeige rufen **dieselbe** Funktion. Verhaltensneutral.
2. **Kandidaten aufzählen:** Ortstag × Slot-Stunde (nur `.hour`, Default 7/18); die Zone wird **je Kandidatentag** über `anchor_tz` bestimmt (Etappe des Tages → erster Wegpunkt), UTC-Zeitpunkt über Ortsmoment mit DST-Offset dieses Tages. Das erste Kandidatenpaar, für das das geteilte Prädikat „fällig" sagt und das strikt nach `now` (bzw. im offenen Nachholfenster `>= now - Fenster`) liegt, ist das Ergebnis.
3. **Ortsvergleich:** eigene Ableitung (andere Regel: exakte Stunde, kein Nachholfenster, keine Idempotenz, Wochentag bei `weekly`, `end_date`), aber über `presets_due_for_hour([preset], locations, candidate_utc)` — gleicher Prädikat-Code wie der Scheduler. Suchfenster daily 2 / weekly 8 Tage; Obergrenze 14 Tage.
4. **Grund separat bestimmen** (nicht aus leerer Suche schließen, weil `is_silenced` im Prädikat steckt): Reihenfolge `manual` → `paused` (`paused_at` oder `paused_until`) → `disabled` (kein Slot aktiv bzw. Briefings abgeschaltet) → `ended` (Trip/`end_date` vorbei) → `none`.
5. **`skip_next`:** nur lesen (nie verbrauchen). `at` zeigt den **übernächsten, tatsächlich versendeten** Termin; `skipped` trägt den übersprungenen.
6. **Strikt-nach-jetzt-Option** (`strict_after=True`) für den Compare-Mail-Fuß: Der gerade laufende Versand (Mail wird in der fälligen Stunde gerendert) zählt nicht als „nächster".
7. **Trip-Suchfenster:** ab Ortstag heute bis letzte Etappe, inklusive Vorabend vor Etappe 1; Etappen-Lücken werden übersprungen; Trip in der Zukunft ⇒ erstes Briefing ist der Abend-Slot am Vortag der ersten Etappe.

### Anzeige-Wortlaut (Frontend)

- Normal: „Nächstes Briefing: Do 07:00 (CEST)"; geplant, keine Zusicherung (Ist-Versand = HH:00 + Laufzeit, bei ausgefallenem Tick bis +2 h).
- Überfällig: „läuft jetzt / wird nachgeholt".
- `skip_next`: „Do 18:00 (CEST) — Do 07:00 wird übersprungen".
- Kein Termin: „pausiert bis 28.10.", „Trip beendet", „nur manueller Versand", „Briefings abgeschaltet".
- Uhrzeit ohne Minuten, Wochentag/Datum aus `local_date`, Kürzel aus `tz_abbr` — nie Browser-Zone (ADR-0051 Regel 2/3).

## Expected Behavior

- **Input:** Auth-Kontext des Nutzers (Session), optional `trip_id` / `preset_id`; serverseitig `now_utc`.
- **Output:** `{trips:{…}, compare:{…}}` nach obigem Format; im UI die Zeile „Nächstes Briefing" bzw. der Grund.
- **Side effects:** keine — rein lesend. Kein Schreiben in `BriefingSlotStore`, kein Verbrauch von `skip_next`, keine Persistenz abgeleiteter Zeitpunkte.
- **Kanäle:** Der **Briefing-Inhalt wird nicht verändert** (E-Mail · Telegram · SMS · Premium-SMS bleiben inhaltlich wie bisher). Betroffen sind nur die Anzeige im Frontend und der Fußtext der Compare-**Mail** (Datum/Uhrzeit des nächsten Versands); der Zeitplan selbst ist kanalunabhängig und gilt für alle vier Kanäle gleich.

## Acceptance Criteria

### S1 — Python-Ableitung, Endpoint, Go-Proxy

- **AC-1:** Given ein Trip mit Morgen 07:00 / Abend 18:00 in Zone Europe/Paris, heutiger Ortstag mit Etappe, `now` = 05:00 Ortszeit / When die Ableitung läuft / Then ist das Ergebnis heute 07:00 mit `tz="Europe/Paris"`, `tz_abbr="CEST"`, `slot="morning"`, `at` mit Offset +02:00 und `local_time="07:00"`.
  - Test: `tests/tdd/test_next_briefing.py` mit echtem Trip-Objekt und eingefrorener Zeit; prüft alle Felder des Ausgabeformats.

- **AC-2:** Given derselbe Trip, `now` = 12:00 Ortszeit (Morgen-Slot vorbei und vermerkt) / When die Ableitung läuft / Then ist der nächste Termin heute 18:00 (`slot="evening"`); ist der Morgen-Slot im echten `BriefingSlotStore` (tmp-Verzeichnis) vermerkt, erscheint er auch bei `now` = 07:30 nicht als nächster.
  - Test: Fall „bereits versendet" mit echtem `BriefingSlotStore` im tmp-Verzeichnis: Slot vermerkt ⇒ nächster = Abend; derselbe Fall ohne Vermerk ⇒ `overdue=true` (siehe AC-3).

- **AC-3:** Given `now` = 08:30 Ortszeit, Morgen-Slot 07:00 nicht vermerkt, Nachholfenster (3 h) offen / When die Ableitung läuft / Then ist der heutige 07:00-Slot der nächste und trägt `overdue=true`; bei `now` = 10:00 (Fenster zu) ist es der Abend-Slot ohne `overdue`.
  - Test: Matrix 06:59 / 07:00 / 09:59 / 10:00 Ortszeit gegen die Fensterkante `stunde <= ortsstunde < stunde+3`.

- **AC-4:** Given ein Trip, dessen Etappen-Wegpunkte in Pacific/Auckland liegen, `now` so gewählt, dass UTC-Tag und Auckland-Ortstag auseinanderfallen / When die Ableitung läuft / Then entspricht `local_date` dem Ortstag in Auckland (nicht dem UTC-Tag), `tz="Pacific/Auckland"` und `at` trägt den Auckland-Offset.
  - Test: Datumsgrenzen-Fall mit Auckland-Trip; Gegenprobe Europe/Paris am selben UTC-Moment ergibt anderes `local_date`.

- **AC-5:** Given ein Trip über einen DST-Wechsel (z. B. Europe/Paris, Umstellung 25.10.2026) und `now` am Vortag / When die Ableitung für heute und den Folgetag läuft / Then trägt jeder Kandidat den Offset und das Kürzel **seines** Tages (CEST vor, CET nach der Umstellung) und `local_time` bleibt „07:00".
  - Test: zwei aufeinanderfolgende Ableitungen mit `skip_next`-freiem Trip; `at`-Offsets +02:00 bzw. +01:00, `tz_abbr` CEST bzw. CET.

- **AC-6:** Given ein Trip mit `skip_next=true`, `now` = 05:00 Ortszeit, Morgen 07:00 / Abend 18:00 / When die Ableitung läuft / Then zeigt `at` den **übernächsten, tatsächlich versendeten** Termin (heute 18:00) und `skipped` trägt den übersprungenen (`local_date` heute, `local_time` „07:00", `slot` „morning"); die Ableitung verändert `skip_next` nicht.
  - Test: nach dem Aufruf ist `skip_next` am Trip unverändert `true` (kein `save_trip`); UI-Wortlaut „Do 18:00 (CEST) — Do 07:00 wird übersprungen" in S2 (AC-21).

- **AC-7:** Given ein Trip mit `paused_at` oder `paused_until` in der Zukunft, bzw. ohne aktiven Slot, bzw. mit allen Etappen in der Vergangenheit / When die Ableitung läuft / Then ist `at=null` und `reason` ist `paused` (mit `paused_until`, falls gesetzt), `disabled` bzw. `ended` — jeweils genau einer, in der Reihenfolge manual → paused → disabled → ended → none.
  - Test: je ein Fall pro Grund mit echtem Trip-Objekt; Fall „paused_until in 3 Tagen" ⇒ `paused_until` im Ergebnis; Fall „pausiert UND Trip beendet" ⇒ `paused` (Reihenfolge).

- **AC-8:** Given ein Trip, dessen erste Etappe in drei Tagen liegt / When die Ableitung läuft / Then ist das erste Briefing der **Abend-Slot am Vortag der ersten Etappe**; liegt zwischen zwei Etappen ein Tag ohne Etappe, wird dieser Tag übersprungen und der nächste Slot eines Etappentags geliefert.
  - Test: Zukunfts-Trip (erwartet Vorabend 18:00) und Trip mit Etappenlücke (erwartet Überspringen) — jeweils mit Zone der Etappe.

- **AC-9:** Given ein Ortsvergleich (Preset) mit `schedule=daily`, `weekly`, mit `end_date`, `manual` bzw. archiviert / When die Ableitung läuft / Then liefert sie: `daily` die nächste exakte Slot-Stunde (kein Nachholfenster), `weekly` den nächsten passenden Wochentag, nach `end_date` `reason="ended"`, bei `manual` `reason="manual"`, bei pausiert (`paused_at`) `reason="paused"`, bei archiviert (`archived_at`) `reason="ended"` (ein archivierter Vergleich verschickt nie wieder — er gilt als beendet, nicht als vorübergehend pausiert); Vorrang bleibt manual → paused → disabled → ended → none — im selben Ausgabeformat wie beim Trip.
  - Test: `test_next_briefing.py` Compare-Fälle daily/weekly/end_date/manual/archived mit echten Preset-Objekten; Altdaten ohne Slots nutzen `resolve_preset_slots` (06/18).

- **AC-10:** Given die Zone ist nicht bestimmbar (Trip ohne Wegpunkte) / When die Ableitung läuft / Then fällt sie auf UTC zurück und zeigt dies ehrlich: `tz="UTC"`, `tz_abbr="UTC"`, `at` mit Offset +00:00 — keine erfundene Ortszone.
  - Test: Trip ohne Wegpunkte ⇒ Felder UTC; kein Fehler, kein Leerfeld.

- **AC-11:** Given für eine Matrix von Zeitpunkten (je Ortszone, vor/in/nach Slot, Fensterkante, Pause, bereits vermerkt) / When der Scheduler-Prädikat-Code „fällig zu Zeitpunkt X" meldet / Then gilt: die Anzeige nennt X als nächsten Termin ⇔ der Scheduler würde zu X versenden — Anzeige und Scheduler nutzen denselben Prädikat-Code, es existiert keine zweite Fälligkeitsregel.
  - Test: Äquivalenztest in `test_next_briefing.py`: für jeden Matrix-Zeitpunkt wird das freie Scheduler-Prädikat und die Anzeige-Ableitung am selben Objekt befragt; Abweichung ⇒ rot (Trip und Compare getrennt).

- **AC-12:** Given der Refactor des Prädikats aus `trip_briefing_due_at` / `_get_active_trips` in eine freie Funktion / When die Bestandstests laufen / Then bleiben `tests/tdd/test_briefing_faelligkeit_ortszone.py`, `test_briefing_slot_faelligkeit_und_alarmsperre.py`, `test_briefing_slot_idempotenz.py`, `test_report_config_slot_faelle.py`, `test_trip_alert_briefing_imminent.py`, `test_compare_preset_slot_dispatch.py` und `test_compare_alert_briefing_imminent.py` unverändert grün — das Versandverhalten ist byte-gleich.
  - Test: diese sieben Dateien (benannt) ohne Änderung an den Tests; kein Test wird angepasst, um den Refactor grün zu bekommen.

- **AC-13:** Given Nutzer A und Nutzer B besitzen je eigene Trips und Ortsvergleiche mit unterschiedlichen IDs / When Nutzer A `GET /api/next-briefings` aufruft — auch mit manipulierter Query `?user_id=<B>` / Then enthält die Antwort ausschließlich IDs von A (Go setzt `user_id` per `appendUserID` aus dem Auth-Kontext und überschreibt die Client-Query); ohne Auth-Kontext ist der Endpoint nicht erreichbar (401), und es fällt nie auf `"default"` zurück.
  - Test: Go-Handler-/Router-Test mit zwei Nutzern (A sieht keine ID von B, auch nicht bei `?user_id=B`), plus Test „ohne Session ⇒ 401".

- **AC-14:** Given zwei Nutzer mit getrennten Datenverzeichnissen / When der Python-Endpoint `GET /api/_internal/next-briefings?user_id=A` antwortet / Then tauchen keine Trip- oder Preset-IDs von B auf; der `_internal`-Endpoint verlangt `X-GZ-Core-Auth` (ADR-0062) und lehnt Aufrufe ohne gültigen Header ab.
  - Test: Python-Test mit zwei Nutzerverzeichnissen (tmp) und echten Trip-/Preset-Dateien; ohne Header ⇒ 401/403; mit `?trip_id=` eines fremden Nutzers ⇒ nicht enthalten.

- **AC-15:** Given das Ausgabeformat aus „Implementation Details" / When ein Ergebnis serialisiert wird / Then enthält es genau die dort genannten Felder, `at` ist ISO-8601 mit Offset oder `null`, `local_time` hat immer das Muster `HH:00`, und `at==null` ohne `reason` ist unmöglich (Schema-Test).
  - Test: Formattest über alle Fälle aus AC-1 bis AC-10: Muster `^\d{2}:00$`, `reason` Pflicht bei `at==null`, `reason` abwesend bei `at!=null`, `skipped` nur bei `skip_next`.

### S2 — Anzeige im geteilten Versand-Reiter und in der Trip-Karte

- **AC-16:** Given ein Trip ist im Editor geöffnet / When ich den Reiter „Briefings" (Versand) öffne / Then sehe ich dort eine Zeile „Nächstes Briefing" mit Wochentag, Uhrzeit HH:00 und Zonenkürzel der Trip-Zone (z. B. „Do 07:00 (CEST)"), ohne Browser-Zone-Umrechnung.
  - Test: `node --test`-Test des Bausteins mit Trip-Fixture (Paris) bei Browser-Zone ≠ Trip-Zone: angezeigt wird die Trip-Zone; Staging-Klick im Trip-Versand-Reiter.

- **AC-17:** Given ein Ortsvergleich ist geöffnet / When ich dessen Versand-Reiter öffne / Then sehe ich dieselbe Zeile „Nächstes Briefing" aus **demselben** geteilten Baustein (`context="vergleich"`), nicht aus einer Compare-eigenen Komponente.
  - Test: `node --test`: der Baustein wird mit `context="route"` und `context="vergleich"` mit gleichem Ausgabeformat gerendert; es existiert keine zweite Komponente für die Anzeige; Staging-Klick im Vergleichs-Versand-Reiter.

- **AC-18:** Given ich ändere im Versand-Reiter die Uhrzeit von Morgen- oder Abend-Briefing / When die Änderung gespeichert ist / Then lädt die Anzeige den Wert neu und zeigt die neue Uhrzeit (HH:00); ungespeicherte Änderungen werden nicht als Versandzeit dargestellt.
  - Test: Frontend-Test mit Speichern ⇒ erneuter Abruf von `/api/next-briefings?trip_id=`; Staging: Uhrzeit ändern, speichern, Zeile aktualisiert sich.

- **AC-19:** Given der Abruf schlägt fehl oder ist noch nicht geladen / When der Reiter gerendert wird / Then bleibt der Reiter voll bedienbar; die Zeile zeigt „—" bzw. einen neutralen Ladezustand, nie eine erfundene Zeit und keinen Absturz.
  - Test: `node --test` mit Fehlerantwort und Ladezustand.

- **AC-20:** Given der Trip-Cockpit-Hub / When ich die Karte „Briefings laufen" in `HubOverview` ansehe / Then zeigt sie die **echten** nächsten Zeiten (Slot-Stunden und Zone aus dem Backend-Wert) statt der fest verdrahteten 06:00/18:00; bei einem Trip mit Morgen 07:00 steht dort nie „06:00".
  - Test: `node --test` mit Trip, dessen Zeiten 08:00/20:00 sind ⇒ Karte zeigt 08:00/20:00; Screenshot-Prüfung der HubOverview bei Layoutänderung (feat_1435 AC-12).

- **AC-21:** Given `skip_next` ist aktiv bzw. es steht nichts an / When die Zeile gerendert wird / Then lautet der Text bei Überspringen „Do 18:00 (CEST) — Do 07:00 wird übersprungen", und bei `at==null` je nach `reason`: „pausiert bis 28.10." (mit `paused_until`, sonst „pausiert"), „Trip beendet", „nur manueller Versand", „Briefings abgeschaltet"; bei `overdue` der Hinweis „läuft jetzt / wird nachgeholt".
  - Test: `node --test`-Formatierungstest, eine Zeile je Fall (skip_next, paused mit/ohne Datum, ended, manual, disabled, overdue); Staging: Trip pausieren ⇒ Text „pausiert bis …".

- **AC-22:** Given die bestehenden Playwright-Selektoren des Versand-Reiters / When die neue Zeile hinzukommt / Then bleiben alle bisherigen `data-testid`s unverändert (versand_tab_route AC-7) und es entsteht kein neues Datenmodell (versand_tab_route AC-8: `ReportConfig`, `AlertRule` und bestehende Endpunkte unverändert); die neue Zeile erhält einen eigenen, stabilen `data-testid`.
  - Test: bestehende Versand-Tab-Tests laufen unverändert grün; neuer Test prüft die testid der neuen Zeile.

### S3 — Ablösung der Alt-Rechnungen, Mail-Fuß

- **AC-23:** Given die Konsumenten `CompareTabs.svelte`, `CompareStatusRow.svelte`, `routes/+page.svelte` und `_home/cockpitHelpers.ts` (`plannedBriefings`) / When sie den nächsten Versand anzeigen / Then lesen sie den Backend-Wert (`/api/next-briefings`) statt `deriveNextSend` bzw. der Fallbacks 06/07; Uhrzeit, Wochentag und Zonenkürzel stammen aus dem Backend-Objekt.
  - Test: `node --test` je Konsument mit Backend-Fixture; Browser-Zone ≠ Ortszone ⇒ Ortszone wird angezeigt; Staging: Vergleichsliste und Startseite zeigen dieselbe Zeit wie der Versand-Reiter.

- **AC-24:** Given `deriveNextSend` (`cockpitHelpers568.ts`) und die Fallback-Konstanten 06/07 / When S3 abgeschlossen ist / Then existiert in Frontend und Python genau EINE Rechnung des nächsten Versands: `deriveNextSend` samt nur dafür genutzter Helfer (`resolvePresetSlots`, `primarySendSlot`) ist entfernt, ebenso die Minuten-Fiktion (07:30).
  - Test: `node --test`-Verhaltenstest je Konsument: Ein Ortsvergleich mit `send_time` 07:30 und ein Backend-Objekt `local_time="07:00"` ⇒ jeder Konsument zeigt 07:00 (würde noch eine Frontend-Rechnung greifen, erschiene 07:30 bzw. die Browser-Zone — Test rot). `compare_send_time_minutes.test.ts` wird auf **HH:00** angepasst (pinnt jetzt „Minuten werden ignoriert, Anzeige HH:00"). Dass die Symbole entfernt sind, belegt `svelte-check` (Import eines entfernten Symbols bricht den Build) — kein Dateiinhalt-Check als Verhaltensnachweis.

- **AC-25:** Given die Dateien `frontend/src/lib/components/trip-detail/HubSchedule.svelte` und `frontend/src/lib/components/organisms/HomeHeroCompare.svelte` mit fest verdrahteten Zeiten / When S3 umgesetzt wird / Then zeigt keine erreichbare Seite mehr eine fest verdrahtete Versandzeit: Dateien ohne Importeur werden gelöscht, Dateien mit Importeur werden auf den Backend-Wert umgestellt.
  - Test: Ist eine Datei noch eingebunden, deckt der `node --test`-Konsumententest aus AC-23 sie mit ab (Backend-Wert 19:00 ⇒ Anzeige 19:00, nicht 06:00/18:00). Wird sie gelöscht, belegen `svelte-check` und `frontend-test` grün, dass nichts mehr auf sie verweist.

- **AC-26:** Given eine Compare-Mail wird in der fälligen Stunde gerendert / When der Abo-Fuß (`_render_abo_footer`) den nächsten Versand nennt / Then nutzt `_compute_next_send` die zentrale Ableitung mit `strict_after=True`: der gerade laufende Versand erscheint **nicht** als nächster, und Datum/Uhrzeit folgen Slots, Wochentag (`weekly`), `end_date` und Pause (kein pauschales „morgen" mehr).
  - Test: Kern-Test mit Preset daily, `now` = Slot-Stunde ⇒ Fuß nennt den Folgetermin; weekly ⇒ nächster Wochentag; `end_date` morgen vorbei ⇒ kein weiterer Termin im Fuß. Live: Renderer-Commit-Gate + `uv run python3 .claude/hooks/email_spec_validator.py` gegen echt zugestellte Staging-Mail aus dem Stalwart-Test-Postfach (Exit 0).

- **AC-27:** Given die Compare-Mail eines Ortsvergleichs in einer anderen Ortszone / When der Fuß den Termin nennt / Then steht er in der Ortszone mit Kürzel (fix_1727_s5c AC-5 bleibt erfüllt).
  - Test: Mail-Fuß-Test für Ortsvergleich mit Ortszone ≠ UTC; `test_vorschau_anzeige_folgen_ortszone.py` (Fußtest, Bereich ~657–708) wird auf das neue Fußformat angepasst, ohne die Zonen-Zusicherung zu lockern.

- **AC-28:** Given die Konto-Seite / When S3 abgeschlossen ist / Then zeigt „Trip-Checks / Nächste Prüfung" unverändert den Prüftakt (kein Versandzeitpunkt, keine Anbindung an `/api/next-briefings`), und alle ihre bestehenden Tests bleiben unverändert grün.
  - Test: Die bestehenden Tests der Konto-Seite laufen unverändert grün (Zeile „Nächste Prüfung“ zeigt weiterhin `next_run` von `/api/scheduler/status/me`). Staging: Die Konto-Seite zeigt die Prüfzeit, der Versand-Reiter den davon abweichenden Versandtermin.

## Bestehende ACs, die erhalten bleiben

| Quelle | Zusicherung |
|---|---|
| `issue_1268` AC-9/AC-10 | echte Versandzeit statt `hour_from` |
| `issue_571` AC-4 / AC-4b / AC-4c | Anzeige vor/nach Slot; `manual` = kein Versand |
| `issue_647` AC-4 | echter Wert statt „—" |
| `issue_1229` AC-4 | Zeile „Nächster Versand" im Versand-Tab bleibt (wird durch die neue Zeile erfüllt/ersetzt, nicht entfernt) |
| `fix_1727_s5c` AC-5 | Mail-Fuß in Ortszone |
| `feat_1435` AC-12 | Screenshots der HubOverview bei Layoutänderung |
| `versand_tab_route` AC-7 / AC-8 | `data-testid`s unverändert, kein Datenmodell-Umbau |

Diese Zusicherungen werden durch die jeweiligen Bestandstests weiter bewacht; Anpassungen an Frontend-Tests sind nur dort erlaubt, wo sie die Alt-Rechnung selbst pinnen (`compare_next_send_slots.test.ts`, `compare_send_time_minutes.test.ts`, `issue_571_home_cockpit_hero.test.ts`, `issue_647_home_fidelity.test.ts`, `cockpitHelpers.test.ts`, `issue_579_home_screen.test.ts`, `issue_578_molecules_organisms.test.ts`) — und dann so, dass die Zusicherung (nicht der Test) erhalten bleibt.

## Testplan

**Kern (deterministisch, ohne Netz, eingefrorene Zeit; keine Mocks, die nur Annahmen spiegeln — echte Trip-/Preset-Objekte, echter `BriefingSlotStore` im tmp-Verzeichnis):**

- `tests/tdd/test_next_briefing.py` — Fälle: Zonen, DST-Wechsel, Pacific/Auckland-Datumsgrenze, `skip_next`, Pause, `paused_until`, disabled, Nachholfenster, bereits vermerkt, Zukunfts-Trip, Etappenlücke, beendet, Compare daily/weekly/`end_date`/manual/archived, Äquivalenz Anzeige ⇔ Scheduler (AC-11), Formatschema (AC-15), Mandanten-Isolation (AC-14).
- Go: Handler-/Router-Test mit zwei Nutzern und ohne Auth (AC-13).
- Frontend per `node --test` (**kein Vitest**): geteilter Baustein (beide `context`-Werte), Formatierung/Texte (AC-21), Konsumenten (AC-23), angepasste Alt-Tests.
- Bestandstests aus AC-12 unverändert grün.

**Live-Schicht (nur `/e2e-verify` bzw. Deploy):** Staging-Klick im Versand-Reiter für Trip **und** Ortsvergleich (Uhrzeit ändern, Zeile aktualisiert sich; Trip pausieren ⇒ Grund); Mail-Fuß ⇒ Renderer-Commit-Gate und `uv run python3 .claude/hooks/email_spec_validator.py` gegen echte Staging-Mail (Marker `X-GZ-Mail-Type: compare`). Testdateien nach Verhalten benannt, nie nach Issue-Nummer.

**Adversary-Pflicht (Mutations-Gegenprobe):** Prädikat-Aufruf in der Anzeige durch eine eigene Bedingung ersetzen ⇒ AC-11 muss rot werden; `appendUserID` aus dem Handler entfernen ⇒ AC-13 muss rot werden; `strict_after` ignorieren ⇒ AC-26 muss rot werden; Zone je Kandidatentag durch Zone des Starttags ersetzen ⇒ AC-5 muss rot werden. Zusätzlich Review-Punkt: „hätte das ein geteilter Baustein sein müssen?" (erfüllt durch AC-17).

## Known Limitations

- Die Anzeige ist **geplant**, keine Zusicherung: Ist-Versand = HH:00 + Laufzeit, bei ausgefallenem Tick bis +2 h (Nachholfenster).
- Der Ortsvergleich hat bewusst eine andere Fälligkeitsregel als der Trip (exakte Stunde, kein Nachholfenster) — zwei Ableitungen hinter einem Ausgabeformat.
- `last_briefing` (zuletzt versendet) ist **nicht** Teil dieses Tickets; #2346 kann es nach Merge von S1 in denselben Endpoint ergänzen (eine Ableitung je Thema, kein zweiter Endpoint).
- Nur Anzeige: Das Ausgabeformat trägt keine Kanalinformation (Zeitplan gilt kanalunabhängig).
- Die Konto-Zeile „Nächste Prüfung" bleibt Prüftakt (siehe „Abweichung vom Ticket").

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; setzt ADR-0051 (Zone an den Daten, Regel 1 keine Persistenz abgeleiteter Zeitpunkte, Regel 2/3 Zone + Kürzel in der Anzeige), ADR-0044 (Kalendertage in Ortszeit) und ADR-0062 (Core-Auth Go→Python) um.
- **Rationale:** Es wird keine bestehende Entscheidung geändert; die Ableitung konsumiert vorhandene Prädikate. Die Ablösung dreier Eigenrechnungen ist eine Konsolidierung, keine Richtungsänderung.

## Changelog

- 2026-10-23: Initial spec created (PO-Entscheidungen 2026-10-23 eingearbeitet: `skip_next` ⇒ übernächster tatsächlich versendeter Termin + Hinweis auf den übersprungenen; nichts ansteht ⇒ Grund nennen).
