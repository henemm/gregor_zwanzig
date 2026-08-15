# Context: fix-1727-s5a-befehlspfade

**Issue:** [#1727](https://github.com/henemm/gregor_zwanzig/issues/1727) Scheibe **S5a** (Zuschnitt aus
`issuecomment-5272415017`) · Teil von Epic [#1722](https://github.com/henemm/gregor_zwanzig/issues/1722)
**Workflow:** `fix-1727-s5a-befehlspfade` (Full Process, Intake-Score 4)
**Erstellt:** 2026-08-12 · Basis-HEAD `77229550`
**Vorgänger:** #1470 (Drilldown), #1697 (Alarm-Pfad), #1724/#1725 (Briefing-Fälligkeit), #1726 (Ruhezeit/Zähler)

## Request Summary

Die **Befehlspfade** — `/heute`, `/morgen`, `/status`, `/jetzt`, `### ruhetag`, `glance`,
`heute_gewitter`, `timeline_heute`, `timeline_morgen` und die Auswahl der aktiven Tour — bestimmen
„welcher Kalendertag ist gemeint" über die **Serveruhr** bzw. den **UTC-Tag der eingehenden
Nachricht**. ADR-0044 verlangt seit 2026-08-03 den **Ortstag der Tour**. Diese Stellen sind dort
ausdrücklich als „bewusst ausgegrenzt, nicht vergessen" gelistet; S5a holt sie nach.

## Type

**Bug.** Verstoß gegen eine bereits getroffene, akzeptierte Grundsatzentscheidung (ADR-0044),
nicht gegen eine offene Frage. Die Entwurfsfrage ist entschieden — **nicht neu aufmachen.**

## Die fünf Fundstellen — gemessen, nicht aus dem Ticket übernommen

| # | Stelle | Ist-Zeitbasis | Wirkung |
|---|---|---|---|
| 1 | `trip_command_processor.py:499` `_handle_query` | `received_at.date()` (UTC) | 6 Befehle, s. u. |
| 2 | `trip_command_processor.py:429` `command_date` | `msg.received_at.date()` (UTC) | `### ruhetag` — **verschiebt Etappendaten**, Idempotenz-Schlüssel |
| 3 | `trip_command_processor.py:1076` `_show_status` | `date.today()` (Serveruhr) | `/status`-Filter |
| 4 | `trip_command_processor.py:1227` `_show_now` | `date.today()` (Serveruhr) | `/jetzt` — Etappenwahl für Radar |
| 5 | `inbound_telegram_reader.py:358` `_find_active_trip` | `date.today()` (Serveruhr) | **auf welche Tour jeder Befehl wirkt** |

Der Serverprozess läuft in `Etc/UTC` — `date.today()` ist praktisch der UTC-Kalendertag.
`received_at` ist garantiert zeitzonenbehaftet (`datetime.now(tz=timezone.utc)`, gesetzt in
`inbound_email_reader.py:149` und `inbound_telegram_reader.py:227/321`) und trägt den
**Verarbeitungs**zeitpunkt des Cron-Polls, nicht den Sendezeitpunkt des Nutzers.

## 🔴 Korrektur am Ticket: `/heute` und `/morgen` versenden NICHT für den falschen Tag

Das Issue und ADR-0044 heben hervor, `_handle_query` „**löst einen Versand aus**, nicht nur eine
Anzeige". Nachgemessen ist das so nicht mehr richtig:

`_trigger_on_demand` (`:562-592`) reicht `target_date` **nicht** weiter — `send_on_demand_report(trip,
report_type)` (`trip_report_scheduler.py:922`) nimmt kein Datum. Der Scheduler bestimmt den Zieltag
selbst über `_get_target_date` (`:781-805`), und das rechnet seit #1724 mit
`trip_local_today(trip, now_utc)` (`:801`) bereits **in der Ortszone**.

`target_date` landet einzig im **Fehlertext**: `_on_demand_failure_body(outcome, label, target_date)`
(`:581`, Formatierung `:246`). Der Erfolgszweig (`:585-591`) benutzt es gar nicht.

**Der Fehler ist damit ein anderer, aber real:** bei `outcome != "sent"` nennt die Antwort einen
anderen Tag als den, gegen den der Scheduler tatsächlich geprüft hat. Neuseeland, Nachricht 14:00 UTC
(= 02:00 Ortszeit des Folgetags): Scheduler prüft Ortstag D+1, die Antwort meldet
„Heute (D): Keine Etappe geplant". **Zwei Bestimmungen desselben Begriffs mit zwei Antworten.**

## 🔴 Der Zuschnitt-Entscheid: die Timeline-Familie hängt an einer zweiten, ungelösten Baustelle

`glance`, `heute_gewitter`, `timeline_heute`, `timeline_morgen` filtern über
`p.arrival_time.date() == target_date` (`_aggregate_day:808`, `_fmt_timeline:891`).

`arrival_time` ist ein **UTC-Zeitpunkt**: `trip_segments.py:182-192` stempelt die Ortszone auf die
Wanduhr-Ankunftszeit und rechnet nach UTC (`TripSegment.start_time/end_time` sind in
`app/models.py:402-403` als „UTC!" annotiert, und die Erzeugung deckt sich damit).

**Neuer, unberichteter Befund:** `_fmt_timeline` gibt diesen Zeitpunkt **roh** aus —
`f"🕐 {p.arrival_time:%H:%M}"` (`:900`/`:902`). Keine Ortszeit-Formatierung. Der Drilldown daneben
macht es richtig (`local_fmt(pt.ts, tz)`, `:796`). **Auf Korsika steht bei einer 08:00-Ankunft
`06:00`.** Kein Test hält das fest (keine Assertion auf `🕐`/`Timeline ·` in `tests/`), kein Issue
kennt es. Der Zeitzonen-Wächter greift nicht: er prüft rohes `.astimezone()` und stille
Zonen-Rückfälle, nicht eine unlokalisierte f-String-Ausgabe.

Filter **und** Anzeige sind heute gemeinsam UTC — in sich stimmig. Wird nur der Tag auf Ortszeit
umgestellt, entsteht genau der Bruch, vor dem #1697 warnt:

> Heute ist die Kette in sich konsistent falsch: Schreiber und Leser irren gleich, deshalb passt es
> zusammen. Wird nur die Etappenauswahl umgestellt, entsteht ein **neuer** Bruch.
> Eine Einzelzeile zu ändern ist hier nicht der kleine, sondern der gefährliche Schnitt.

**Daraus folgt eine Entscheidung, die die Spec treffen muss** (Optionen in „Offene Entscheidungen").

## Existing Patterns — das Muster ist da, erprobt und gehärtet

`src/services/trip_day.py` hält alle Bausteine; eine eigene Kopie der Auflösung ist laut ADR-0044
ein **Regelverstoß**:

| Funktion | Aufgabe | Zeile |
|---|---|---|
| `trip_tz(trip)` | Rückfall 2 — erste Etappe mit Wegpunkten, sonst importierte `UTC`-Konstante | `:29-42` |
| `display_tz(trip, day)` | Zone der Etappe dieses Tages | `:45-52` |
| `anchor_tz(trip, now_utc)` | löst die Henne-Ei-Falle: Zone der Etappe des **Weltzeit**-Tages | `:55-71` |
| `trip_local_now(trip, now_utc)` | Ortstag UND Ortsstunde aus EINER Auflösung | `:74-87` |
| `trip_local_today(trip, now_utc)` | **das, was `date.today()` ersetzt** | `:90-96` |

**Vorbild 1 — Drilldown im selben Modul** (`_day_window:736-775`): holt `anchor_tz`/`display_tz` aus
`services.trip_day` (Modul-Import `:23`), keine lokale Kopie, und **reicht `tz` durch**, damit
Fenstergrenze und Uhrzeitspalte konstruktiv nicht auseinanderlaufen können (`:759-762`).

**Vorbild 2 — `_get_active_trips`** (`trip_report_scheduler.py:722-779`): hatte **exakt** das Problem
von Fundstelle 5 und wurde in #1724 gefixt. Der Docstring benennt beides:

> Der Zieltag wird deshalb IN der Schleife je Trip bestimmt — vorher stand er davor und galt für alle
> gleich. In Auckland lag er dadurch bis zu zwölf Stunden am Tag daneben. (`:729-734`)
> Ein Default auf die Systemuhr würde genau die Umgebungsuhr wieder einführen, die ADR-0051 Regel 3
> verbietet. (`:738-740`)

## Wirkung je Fundstelle — gemessen

**`/status` (3):** Filter `stage.date >= today`.
- UTC−8: zwischen 00:00–08:00 UTC ist der Ortstag noch D−1 ⇒ die aktuelle Etappe wird
  **herausgefiltert** — bis zu 8 h/Tag fehlt die heutige Etappe.
- UTC+12: zwischen 12:00–24:00 UTC ist der Ortstag schon D+1 ⇒ eine lokal bereits abgeschlossene
  Etappe bleibt **sichtbar** — bis zu 12 h/Tag.
- Mitteleuropa: 2 h/Tag (22:00–00:00 UTC). **Auch Korsika ist jede Nacht betroffen** — die Annahme
  „in Europa ändert sich nichts" wurde schon in #1697 nachgemessen und widerlegt.

**`/jetzt` (4):** `date.today()` → `trip.get_stage_for_date(today)` → Radar-Nowcast. #1402 hat hier
nur die **Uhrzeit** des Onset-Texts ortsrichtig gemacht (`tz_for_coords(wp.lat, wp.lon)`, `:1248-1250`)
— die vorgelagerte Frage „welcher Tag/welche Etappe" bleibt Servertag. Uhrzeit richtig, Tag falsch.

**`### ruhetag` (2):** `_apply_ruhetag` (`:946-995`) verschiebt jede Etappe mit
`stage.date > command_date` um `+N`. Der Ortstag-Fix ändert **nur**, ob die *heutige* Etappe
mitwandert; weiter entfernte Etappen sind vom Offset unabhängig.

Korsika (UTC+2), Nachricht 00:30 Ortszeit = 22:30 UTC am Vortag, heutige Etappe auf D:
- heute: `command_date = D−1` ⇒ `D > D−1` ⇒ **wahr** ⇒ die heutige Etappe wird mitverschoben
- nach dem Fix: `command_date = D` ⇒ `D > D` ⇒ **falsch** ⇒ sie bleibt liegen

Der Punkt ist nicht „eine Etappe weniger", sondern **Gleichheit innerhalb des Ortstages**: derselbe
Befehl verhält sich um 00:30 Ortszeit heute anders als um 14:00 Ortszeit desselben Tages. Nach dem
Fix nicht mehr. Mismatch-Fenster = `|UTC-Offset|` Stunden ab Ortsmitternacht (Korsika 2 h,
Neuseeland **12 von 24 h**).

**Randfall, der eine AC braucht:** Hat die Tour nur noch die heutige Etappe, ist `shifts` nach dem
Fix leer ⇒ die Antwort kippt von „Ruhetag eingetragen" auf „Keine zukuenftigen Etappen zum
Verschieben" (`:973-979`). Verhaltenswechsel, kein Absturz.

**`_find_active_trip` (5):** ein einziges `today` **vor** der Schleife (`:358`) gilt für **alle**
Touren (`:367`). Übertragung des #1724-Musters: `trip_local_today(trip, now_utc)` **in** der Schleife,
je Tour deren eigene Zone.

## Dependencies

- **Upstream:** `services/trip_day.py` (alle Bausteine vorhanden, keine Neuentwicklung),
  `utils/timezone.py` (`tz_for_coords`, `local_dt`, `local_fmt`, importierte `UTC`-Konstante).
- **Downstream:** `TripCommandProcessor.process()` ist der einzige Eintritt für Mail- **und**
  Telegram-Befehle. Kette: Go-Cron `internal/scheduler/scheduler.go:385` → Proxy
  `internal/router/router.go:212` → `api/routers/scheduler.py:127/172` → Inbound-Reader →
  `processor.process(inbound)`.
- **Kein Konsument außerhalb:** `command_log.json` wird ausschließlich von `_load_command_log`/
  `_append_command_log`/`_is_already_applied` in `trip_command_processor.py:1301-1345` berührt (Grep
  über `src/`, `api/`, `internal/`, `frontend/src`).

## Persistenz-Folgen (Fundstelle 2)

`_append_command_log` schreibt nach `get_data_dir(user_id)/command_log.json` (`:1301-1303`), eine
JSON-Liste, Felder `trip_id`, `command`, `date` (`command_date.isoformat()`), `applied_at`. **Keine
Retention** — wächst unbegrenzt. `_is_already_applied` vergleicht `date` als **String** (`:1342`),
kennt also keine Semantik.

Bestand gemessen: im Worktree-`data/` **und** im Hauptrepo-`data/` (die beiden Verzeichnisse aus
#1633) existiert **kein** `command_log.json`. **Nicht gemessen:** `/var/lib/gregor` (Prod) und
`/var/lib/gregor-staging` — `claude-gregor:claude-gregor`, Modus `2750`, kein Lesezugriff als `hem`,
kein sudo verwendet.

**Bedeutungsbruch:** Ein Altbestandseintrag trägt ein UTC-Datum, ein neuer den Ortstag. Betroffen
sind nur Einträge, die **am Umstellungstag im Mismatch-Fenster** geschrieben wurden; dort griffe die
Doppelausführungs-Sperre einmalig nicht. Kein Datenverlust, keine Migration nötig — aber die Spec
muss es benennen statt es zu übersehen.

## Bestehende Wächter

**`tests/test_output_timezone_guard.py`** — AST-Ratsche, `KNOWN_VIOLATIONS` darf nur **schrumpfen**.

- Drei Einträge betreffen S5a: `:619` `_find_active_trip`, `:627` `_show_now`, `:628` `_show_status`.
- Schlüsselform ist `pfad::funktion::ordinal`, das Ordinal zählt **innerhalb der Funktion**
  (`_number_findings:266-281`, Fix für #1466 AP2 — das alte `pfad:zeile` driftete bei jeder
  eingefügten Zeile). Nachgemessen: alle drei sind der **einzige** Eintrag ihrer Funktion, ein
  Entfernen verschiebt also keine fremden Ordinale.
- Muster A prüft rein syntaktisch `node.func.attr in {"now","today"}` (`:145`, `:386-394`). Nach der
  Umstellung auf `trip_local_today(trip, now_utc)` — ein `ast.Call` auf `ast.Name`, kein
  `ast.Attribute` — matcht der Scanner nicht mehr. **Alle drei Einträge müssen im selben Commit
  raus**, sonst wird `test_known_violations_only_shrink` (`:704-716`) rot.
- 🔴 **Die Fundstellen 1 und 2 sind völlig unbewacht.** `received_at.date()` ist ein `.date()`-Aufruf
  auf einem Parameter — Muster A sieht das strukturell nicht. Genau diese Lücke schließt erst
  **Muster 3** aus Scheibe S5c.

**`tests/test_success_status_guard.py`** — kein Handlungsbedarf, empirisch gemessen (Scanner gegen
synthetische Nachbauten der Funktionskörper laufen gelassen, nicht dem Kommentartext geglaubt):

- `_show_status` (`:1655`) begründet sich selbst mit dem „**trivialen** `date.today()`" — das ist
  aber nicht der einzige Auslöser: `lines.append(...)` (`trip_command_processor.py:1080`) erfüllt
  dieselbe Bedingung. Probe mit entferntem `date.today()`: matcht unverändert.
- `_show_now` (`:1666`) ankert an `get_nowcast(...)`/`format_now_text(...)` und
  `trip.get_stage_for_date(today)`.
- Die vier `_handle_query`-Einträge (`:1622-1632`) ankern an `WeatherExtractor(...)` und
  `extractor.timeline(...)` (`:511-513`) — beide vor allen Rückgabezweigen und unabhängig von der
  `today`-Zeile.
- **Nicht bewacht:** die Ortszeit-Ausgabe der Timeline (s. o.) und die Tagesbestimmung aller sechs
  Query-Zweige.

## Existing Specs & ADRs

- `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` — **Akzeptiert.** Die vier Stellen dieser
  Scheibe stehen dort namentlich unter „Noch nicht umgesetzt".
- `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` — Regel 3: `date.today()` und
  `datetime.now()` ohne `tz` sind im Produktivcode verboten; „jetzt" wird als Parameter hereingereicht.
- `docs/specs/modules/fix_1470_drilldown_ortszeit.md` — Henne-Ei-Auflösung, AC-Vorbild.
- `docs/specs/modules/trip_command_processor.md` — Modul-Spec; hält fest: **kein Undo-Mechanismus**
  (`:416`), also kein zweiter datumsabhängiger Pfad.
- `docs/context/fix-1697-ortstag-statt-servertag.md` — die Fundstellen-Karte; S5a ist dort „Kette B".

## Analysis

### Type
**Bug** — Verstoß gegen ADR-0044 (Akzeptiert). Keine offene Produktfrage.

### Kopplung innerhalb der Scheibe — die #1697-Falle greift hier NICHT

Nachgemessen: **der Wetter-Schnappschuss ist nicht datiert.** `_delete_snapshot` (`:1291-1299`) und
`_fetch_and_save_snapshot` (`:285`) adressieren `get_snapshots_dir(user_id)/{trip_id}.json` — eine
Datei je Tour, kein Datum im Schlüssel. `save_dated`/`load_dated` kommen im ganzen Modul **nicht**
vor. Es gibt in S5a also **kein Schreiber/Leser-Paar**, das gemeinsam umgestellt werden müsste; die
vier Stellen sind voneinander unabhängig. Das ist der entscheidende Unterschied zu #1697, wo genau
diese Kopplung den Zuschnitt bestimmt hat.

Einzige verbleibende Datums-Persistenz ist `command_log.json` (nur `ruhetag`, s. o.) — Schreiber und
Leser sitzen beide in `_is_already_applied`/`_append_command_log` und werden zwangsläufig gemeinsam
umgestellt.

### Der größte Blast Radius: `_find_active_trip` sitzt vor JEDEM Telegram-Befehl

Beide Aufrufer sind Torwächter: `:187` für alle Text-Befehle, `:314` für alle Callback-Buttons.
Liefert die Funktion eine andere Tour, trifft **jeder** Befehl eine andere Tour.

Wann ändert sich die Auswahl? Wenn zwei Touren aneinandergrenzen und der Tageswechsel dazwischen
liegt. Tour A endet an D, Tour B beginnt an D+1; Nachricht um 22:30 UTC (= 00:30 Ortszeit an D+1 in
Mitteleuropa): heute wählt `today = D` noch **A**, nach dem Fix wählt `today = D+1` **B**. Lokal ist
tatsächlich schon D+1 — die neue Antwort ist die richtige. Braucht eine eigene AC.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | `command_date` (`:429`), `_show_status` (`:1076`), `_show_now` (`:1227`); die beiden `_show_*` bekommen `now_utc`. **`_handle_query` bleibt unberührt.** |
| `src/services/inbound_telegram_reader.py` | MODIFY | `_find_active_trip` — `now_utc` als Pflichtparameter, Auflösung je Tour **in** der Schleife |
| `tests/test_output_timezone_guard.py` | MODIFY | drei `KNOWN_VIOLATIONS`-Einträge entfernen (`:619`, `:627`, `:628`) |
| `tests/tdd/test_inbound_telegram_reader.py`, `test_bug_824_archived_trip_filter.py`, `_telegram_live_fixture.py` | MODIFY | vier Aufrufstellen der geänderten Signatur |
| `tests/…/<neue Datei>` | CREATE | Verhaltenstests, nach Verhalten benannt (nicht nach Issue-Nummer) |
| `tests/tdd/conftest.py` *(offen)* | MODIFY | Zwei-Zonen-Fixtur teilbar machen — s. Entscheidung 4 |

### Scope Assessment
- Produktivcode: 2 Dateien, geschätzt **+45/−15**
- Tests: geschätzt **+110/−10** (Zwei-Zonen-Fixtur, Vorbedingungs-Anker, ein Umstellungstag)
- **Risiko: MEDIUM-HIGH** — nicht wegen der Rechnung, sondern wegen `_find_active_trip` vor allen
  Befehlen und weil `ruhetag` Etappendaten schreibt.
- LoC gegen das Limit 250: **passt mit Puffer**, seit `_handle_query` ganz draußen ist.

### 🔴 Die Nachweis-Lücke, die benannt bleiben muss

Die wertvollste Mutation für `_find_active_trip` ist **„die Tagesberechnung wieder vor die Schleife
ziehen"** — exakt die Regression, die #1724 in `_get_active_trips` behoben hat. Sie wird **nur** von
einem Test gefangen, der **zwei Touren in verschiedenen Zonen** hat, die bei demselben `now_utc`
verschiedene Ortstage tragen. Keiner der fünf bestehenden Aufrufer-Tests baut das. Ohne diesen neuen
Test bleibt die Mutation ungefangen — das ist eine Pflicht-AC, keine Kür.

Zweite bewusst offene Grenze: Im Mismatch-Fenster nennen `/status` (Ortstag) und `/glance` (UTC-Tag)
verschiedene Tage. Das ist **Anzeige-Divergenz ohne gemeinsamen Datenträger** — kein Datenverlust,
keine still fehlschlagende Zusicherung, anders als die Persistenz-Kopplung aus #1697. Gehört als
bekannte Grenze in die Spec, sonst wertet der Adversary sie als Regression.

### Nachweisform
Vollständig offline belegbar (Kern-Schicht): `freeze_time` (freezegun, vorgemacht in
`tests/unit/test_trip_local_today.py:24/52`) plus In-Memory-`Trip`/`Stage`/`Waypoint`. **Keine
Staging-Mail nötig** — der Versand selbst ist unberührt. Ein exemplarischer Umstellungstag statt
einer vollen Sommerzeit-Matrix (reine Datumsbestimmung, kein Fenster) — ADR-0044 verlangt beide
Wechseltage für *Fensterlängen*; hier ist die Schärfe geringer und das LoC-Budget der bessere Wächter.

## Offene Entscheidungen für die Spec

0. ~~Fehlertext von `/heute`/`/morgen` in S5a mitnehmen?~~ **Entschieden: nein — `_handle_query`
   bleibt komplett draußen.** `today`/`tomorrow` werden **einmal** berechnet (`:499-500`) und speisen
   **alle sechs** Zweige. Den Fehlertext allein zu korrigieren hieße, eine **zweite**
   `today`-Definition in dieselbe Funktion zu setzen — genau das Muster, vor dem ADR-0044 warnt
   („eine eigene Kopie der Zonen-Auflösung ist ein Regelverstoß"), und man tauschte einen falschen
   Tag gegen zwei konkurrierende Tagesbegriffe an einer Stelle. Der saubere Fix ist ohnehin ein
   anderer: `send_on_demand_report` soll den Tag **zurückgeben**, den es benutzt hat, statt dass der
   Aufrufer ihn rät. Das gehört zu #1795, das `_handle_query` bereits besitzt.
1. ~~Timeline-Familie: mit oder ohne?~~ **Entschieden: ohne.** `glance`, `heute_gewitter`,
   `timeline_heute`, `timeline_morgen` bleiben in S5a unverändert und konsistent UTC; sie brauchen
   Tag **und** Uhrzeit gemeinsam und damit eine eigene Nachweisführung → **#1795**. Rückverweis in
   #1727 gebucht (`issuecomment-5272587776`). Der verbleibende Zwischenzustand ist keine *neue*
   Inkonsistenz: `/glance` und der Drilldown-Button derselben Nachricht nennen schon heute
   verschiedene Tage, weil der Drilldown seit #1470 ortszonenrichtig rechnet und `_handle_query`
   nicht.
2. **`_find_active_trip`-Signatur:** `now_utc` als **Pflichtparameter** — ADR-0051 Regel 3 verbietet
   den Systemuhr-Default, und `_get_active_trips` benennt das im Docstring wörtlich
   (`trip_report_scheduler.py:738-740`). Trifft zwei Produktiv-Aufrufer (`:187`, `:314`) und vier
   Test-Aufrufstellen.
3. **Kosten der Pro-Tour-Auflösung:** `tz_for_coords` (`utils/timezone.py:32-40`) hat **kein**
   Ergebnis-Caching; nur der `TimezoneFinder` selbst ist ein Lazy-Singleton (`:23-29`). Ein
   `.timezone_at()` pro Tour und Aufruf, linear und billig. **Vorschlag: ausdrücklich keinen Cache
   bauen** — S5a ist eine Korrekturscheibe, nicht der Ort für eine Optimierung ohne gemessenen
   Engpass. Die Spec soll das als bewusste Nicht-Entscheidung festhalten.
4. **Woher kommt die Zwei-Zonen-Fixtur?** Es gibt zwei, beide unteilbar in Testmodulen
   (`_trip_two_zones` in `test_drilldown_day_window_local_date.py:415`, `trip_zwei_zonen` in
   `test_ruhezeit_und_zaehler_folgen_der_ortszone.py:1553`). **Vorschlag:** `_trip_two_zones` nach
   `tests/tdd/conftest.py` heben und beide Altnutzer darauf ziehen — eine dritte Kopie wäre genau
   der Fehler, den ADR-0044 für die Zonen-Auflösung selbst verbietet.

## Risks & Considerations

- **Sommerzeit ist Pflicht, nicht Kür** (ADR-0044): beide Wechseltage testen. Für eine reine
  *Datums*bestimmung weniger scharf als für Fensterlängen, aber zu belegen statt anzunehmen.
- **Fixturen-Falle (#1726 F002):** Trip-Fixturen mit **einer** Etappe lassen `anchor_tz` und
  `trip_tz` zusammenfallen — die Zusicherung kann strukturell nie fehlschlagen. Ebenso Fixturen
  ausschließlich in Mitteleuropa. Jeder neue Test braucht einen **Vorbedingungs-Anker**, der misst,
  dass Ortstag und Servertag bei dieser Fixtur wirklich auseinanderfallen.
- **LoC-Limit 250:** #1726 brauchte für 18 Stellen +239. Fünf Stellen plus drei Signaturänderungen
  plus Tests — mit Option B machbar, mit Option A nicht ohne Override.
- **`data/` muss untracked bleiben.**

## Testfläche — ausgezählt

**26 Testdateien** fahren `TripCommandProcessor`; **keine** davon steht in
`.github/ci_tdd_excludes.txt` — alle einschlägigen Tests laufen also in der CI.

**Direkte Aufrufer der zu ändernden Signaturen** (brechen beim Umbau) — nur `_find_active_trip`:

| Datei:Zeile | Aufruf |
|---|---|
| `tests/tdd/_telegram_live_fixture.py:344` | `reader._find_active_trip(user_id)` |
| `tests/tdd/test_bug_824_archived_trip_filter.py:198` | `reader._find_active_trip(two_trip_env)` |
| `tests/tdd/test_inbound_telegram_reader.py:78`, `:108`, `:130` | `reader._find_active_trip()` |

`_show_status` und `_show_now` werden von **keinem** Test direkt gerufen, nur über `process()` —
ihre Signaturerweiterung schlägt also nicht in die Testfläche durch.

### 🔴 Die Fixturen-Falle ist hier real, nicht theoretisch

Alle Trip-Fixturen der Befehlspfad-Tests liegen in **Mitteleuropa**:

| Datei | Koordinaten | Zone | Offset-Fenster |
|---|---|---|---|
| `test_trip_command_processor.py:57-58` | `lat=39.71/39.75` (Mallorca) | `Europe/Madrid` | 2 h/Tag |
| `test_inbound_telegram_reader.py:24-25` | `lat=39.71/39.75` | `Europe/Madrid` | 2 h/Tag |
| `test_issue_651_telegram_query_glance.py:45,69-70` | `lat=39.76/39.80` | `Europe/Madrid` | 2 h/Tag |
| `test_issue_1007_heute_voll_briefing.py:110-144` | `lat=47.28-47.31` | `Europe/Vienna` | 2 h/Tag |

Ortstag und Servertag fallen dort nur zwischen 22:00 und 00:00 UTC auseinander. Ein Test, der
seinen `received_at` nicht **absichtlich** in dieses Fenster legt, bleibt grün, egal welche
Tagesbasis der Prüfling benutzt — die Zusicherung kann strukturell nie fehlschlagen. Genau die
Klasse, die in #1726 als F002 gefunden wurde.

Breiter nachgezählt über **24** Dateien: **23 davon liegen ausschließlich in Mitteleuropa**
(Mallorca 39.7/2.6, Korsika 42.x/9.x, Österreich/Deutschland 47–48/9–11.5, DE/NL-Grenze 52.2/7.7).
10–11 Dateien bauen wenigstens eine Fixtur mit mehr als einer Etappe, `anchor_tz` und `trip_tz`
fallen dort also nicht automatisch zusammen — die *zweite* Hälfte der #1726-F002-Falle ist damit
schwächer als die erste.

**Die einzige Ausnahme ist zugleich die brauchbare Vorlage:** `_trip_two_zones`
(`tests/tdd/test_drilldown_day_window_local_date.py:415-431`) baut Etappe 0 in **Wellington**
(`-41.3/174.8`) und die folgenden auf **Korsika** — „zwölf Stunden auseinander, genau die Spanne,
die den Anker sichtbar macht" (`:410-412`). Sie wird heute nur über den Drilldown-Zweig benutzt,
der **vor** dem `command_date`-Block zurückkehrt, berührt die fünf Ziel-Stellen also nicht.

**Zonen-Fixturen sind nirgends geteilt:** `trip_zwei_zonen()` liegt in
`tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py:1553` — in einem **Testmodul**, nicht in
einer `conftest.py`. `tests/conftest.py` und `tests/tdd/conftest.py` bieten keine Zonen-Hilfe;
`tests/unit/conftest.py` existiert nicht. Es gibt damit **zwei** Zwei-Zonen-Fixturen an zwei Orten,
beide unteilbar. Ob S5a eine davon in eine `conftest.py` hebt oder eine dritte baut, **gehört in die
Spec, nicht in die Implementierung.**

**Vorhandenes Vorbild für die Testform:** `tests/unit/test_trip_local_today.py` prüft den Baustein
bereits isoliert.
