# Context: fix-1727-s5g-alarmkandidaten

Erhoben 2026-08-19 gegen `origin/main` `9300e634`, per drei parallelen Recherche-Agenten.
Alle Zeilennummern in diesem Dokument sind **nachgemessen**, nicht aus dem Register übernommen.

## Request Summary

Issue #1727 (Epic #1722, ADR-0049/ADR-0051) räumt `KNOWN_VIOLATIONS` in
`tests/test_output_timezone_guard.py` auf. Nach S5f steht die Liste bei **34** Einträgen. Der
PO-Entscheid vom 2026-08-19 hat das Abschlusskriterium von „auf null" auf „nur noch die
dokumentierten dauerhaften Ausnahmen (#1402/#1345)" präzisiert. S5g ist die dafür fehlende Scheibe:
die verbleibenden echten `raw_astimezone`-Kandidaten.

## Basislinie: die 34 Einträge, ausgezählt

| Rubrik | Einträge | Bleibt in der Liste? |
|---|---|---|
| DAUERHAFT (`tz=None` ist legitimer Domänenzustand) | 2 | ja, dauerhaft |
| Aufrufseite abgesichert (PO-Entscheidung #1402) | 20 | ja, dauerhaft |
| bewusst UTC nach Hausnorm #1345 (Kontingent-Zähler) | 4 | ja, dauerhaft |
| **echte Kandidaten → Scope dieser Scheibe** | **8** | **nein** |
| **Summe** | **34** | |

Die 4 bewusst-UTC-Einträge sind `forecast_budget.py::_today_utc`,
`meteoalarm_budget.py::_now_ts`, `meteoalarm_budget.py::_today_utc`,
`weather_extractor.py::_to_naive_utc`.

**Korrektur zum PO-Kommentar:** dort steht „~9 echte Kandidaten"; die dort selbst aufgezählten
Dateien ergeben summiert 8 (1+2+1+1+1+2). Die Rechnung 2+20+4+8 = 34 geht exakt auf.

## Kernbefund: alle 8 Kandidaten sind Formbereinigung

Kein einziger der acht Fundstellen ist ein laufender Zeitzonen-Bug. Alle rechnen bereits korrekt;
sie gehen nur nicht über einen zentralen, benannten Helfer. **S5g ist damit dieselbe Sorte Scheibe
wie S5f, nicht die Bugfix-Scheibe, die der Intake angenommen hatte.**

| # | Kandidat | Ist-Zeile | Register sagt | Zone korrekt? | Testschutz |
|---|---|---|---|---|---|
| 1 | `alert_briefing_anchor.py::record_briefing_sent` | :205 | :195 | ja (UTC richtig, Regel 1) | **kein Werte-Netz** |
| 2 | `compare_location_weather_source.py::_window_bound` | :43 | :39 | ja (pro Ort) | stark, deterministisch |
| 3 | `compare_location_weather_source.py::fetch` | :118 | :116 | ja (pro Ort) | stark, deterministisch |
| 4 | `compare_official_alert.py::_day_window_end` | :397 | :271 | ja (pro Ort) | Grenze ja, **Zone nicht deterministisch** |
| 5 | `scheduler_dispatch_service.py::run_compare_presets_daily` | :210 | :179 | ja (feste Debug-Zone) | indirekt |
| 6 | `stage_weather.py::_to_utc_date` | :62 | :62 | ja (toter Zweig) | **kein Werte-Netz** |
| 7 | `trip_alert.py::_briefing_precip_for_onset` | :1028 | :872 | ja (interner Index) | **echt** (#818 AC-1/AC-2) |
| 8 | `trip_alert.py::check_radar_alerts` | :1274 | :1092 | ja (pro Startpunkt) | **echt**, ohne Mock |

### Zeilendrift ist durchgehend und massiv

Sieben von acht Registereinträgen nennen eine falsche Zeile, teils um mehrere hundert Zeilen
(:872→:1028, :1092→:1274, :271→:397, :179→:210). **Einträge sind ausschließlich über den
funktionsbezogenen Schlüssel zu identifizieren.** Wer nach Zeilennummer greift, trifft fremden Code.
Dieselbe Warnung stand schon in der S5f-Spec (Known Limitations) — sie gilt hier verschärft.

### Begründungen je Kandidat

**1 · `record_briefing_sent`** — `moment` ist ein reiner Speicher-/Vergleichszeitstempel, wird als
`isoformat()` ins Anker-JSON geschrieben und nur von `last_briefing_at()` gelesen; einziger
Konsument ist ein Zeitvergleich in `alert_gate.py:344`. Die Lokalisierung passiert schon korrekt an
der Anzeigegrenze (`alert_gate.py:351`, `local_fmt`). UTC ist hier nach ADR-0051 Regel 1
(„Vergangenes ist ein Zeitpunkt") die richtige Antwort. 1 Aufrufer in `src/`, 0 in `api/`.

**2+3 · `_window_bound` / `fetch`** — beide lösen die Zone über `tz_for_coords(lat, lon)` mit den
Koordinaten des jeweils übergebenen Vergleichsorts auf, bevor gerechnet wird. `fetch()` wird in
allen drei Aufrufern in einer Schleife je Ort mit dessen eigenen Koordinaten gerufen
(`scheduler_dispatch_service.py:682`, `compare_alert.py:430-433`, `:435-437`). Ein Fehlschlag der
Zonenauflösung isoliert auf genau diesen einen Ort. Der vermutete Multi-Zonen-Fehler existiert
nicht.

**4 · `_day_window_end`** — dito, `tz_for_coords(loc.lat, loc.lon)` je Iteration aus `_detect()`.
Nebenbefund: `tz_for_coords(...) or timezone.utc` (`:396`) ist toter Code — `tz_for_coords` liefert
bei Fehler bereits selbst `ZoneInfo("UTC")`, nie einen falsy-Wert.

**5 · `run_compare_presets_daily`** — **die Registerbeschreibung ist falsch.** Dort steht
„Fälligkeit in der Ortszone des Presets (#1724)". Tatsächlich sitzt die Preset-Ortszonen-Logik seit
#1726 in `compare_slot_scheduler.py::presets_due_for_hour:138` und geht dort bereits über
`local_dt`. Der verbliebene rohe Aufruf gehört zum manuellen `?hour=`-Debug-Trigger mit fester
Referenzzone `Europe/Vienna`; der stündliche Produktiv-Cron ruft ohne `hour` auf und **erreicht die
Zeile nie** (`api/routers/scheduler.py:199`, einziger Aufrufer).

**6 · `_to_utc_date`** — der `astimezone`-Zweig ist toter Code: `ForecastDataPoint.__post_init__`
(`app/models.py:221-233`, Hausnorm #1345) konvertiert jeden aware Zeitstempel schon bei Konstruktion
nach UTC und strippt auf naiv. Der reale Pfad ist immer `ts.date()`.

**7 · `_briefing_precip_for_onset`** — reiner Lookup-Schlüssel gegen die normalisierte Zeitreihe.
Die dem Nutzer **angezeigte** Onset-Uhrzeit läuft über einen getrennten, bereits korrekt
lokalisierten Pfad (`trip_alert.py:1274`, Kandidat 8).

**8 · `check_radar_alerts`** — `tz_for_coords(active.start_point.lat, .lon)`, echte
Koordinaten-Auflösung. Der String läuft unverändert bis in den Renderer (`ab {e.onset_time}`), keine
zweite Umrechnung unterwegs. Bei Gewitter 15:30 Ortszeit liest der Nutzer „ab 15:30" — korrekt.

## Der Helfer: `to_utc()` ist da und getestet

`src/utils/timezone.py:107-120` (aus S5f):

```python
def _as_utc(dt): return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
def to_utc(dt):  return _as_utc(dt).astimezone(timezone.utc)
```

`tests/unit/test_utils_timezone.py` deckt naiv (kein Wertsprung beim Labeln) und aware Nicht-UTC
(echte Konvertierung, Regressionsschutz Adversary-Fund F001) ab. **8 Aufrufer** heute in `src/`,
alle aus S5f.

Für Kandidat 8 ist `local_fmt(dt, tz)`/`local_dt` der passende Helfer, nicht `to_utc()` — dort wird
in die **Ortszone** gerechnet, nicht nach UTC.

## Testlage — wo die Scheibe eigenen Schutz mitbringen muss

**Echter Schutz vorhanden (kein neuer RED-Test nötig):**
- Kandidat 7: `test_issue_818_radar_briefing_integration.py::test_ac1_...` / `::test_ac2_...` prüfen
  den Stunden-Match mit konkreten Werten (48 naive UTC-Stempel gegen berechnete `onset_hour`).
- Kandidat 8: `test_bundle_791_847_844_alerts.py::test_ac1_radar_alert_onset_in_local_time` — Trip
  auf Korsika, echter `mail_sink` statt Mock, prüft die lokale Zeit im Body **und** dass die
  UTC-Zeit dort *nicht* steht.
- Kandidaten 2+3: `test_compare_alert_day_window.py::test_ac4_fenster_wird_in_der_ortszeit_am_ort_
  aufgeloest` (Sierra, America/Los_Angeles, mit ausformulierter Mutations-Erwartung im Docstring)
  plus zwei Grenzwert-Tests an der 19/20-Uhr-Kante.

**Kein Werte-Netz (Lücke):**
- Kandidat 1: alle Tests übergeben bereits UTC-aware Werte — `.astimezone(timezone.utc)` ist in
  *jedem* Testpfad ein No-Op. Geprüft wird die Throttle-Logik, nie die Konvertierung.
- Kandidat 6: die zwei Kern-Tests prüfen nur `set(ws.keys()) == {...}`, kein Wert-Assert. Suche nach
  einem geprüften `is_day`-Wert im ganzen `tests/`-Baum: **0 Treffer**. Der Fake-Provider liefert
  zudem 24 Stunden konstant `is_day=1` — kein Tag/Nacht-Übergang, kein Mismatch-Szenario.

**Schwächer, als er aussieht:**
- Kandidat 4: die Fenstergrenze ist sauber bewacht, die **Zone pro Ort nicht deterministisch**.
  `_daytime_location()` (`test_official_alert_time_window.py:497-508`) wählt zur Laufzeit den ersten
  von 11 Orten mit Ortsstunde 6–16 — **Wien steht an erster Stelle**. Läuft die Suite zur passenden
  Tageszeit, testet sie Wien gegen Wien, und eine Mutation „fest auf Wien verdrahtet" bliebe
  unentdeckt. Die drei Grenzwert-Tests daneben laufen ohnehin alle in Wiener Zone.
  → **Pflicht-Prüfpunkt für die Mutations-Gegenprobe.**

## Nachweisform „Register schrumpft um genau N"

Es gibt **keinen** literalen Count-Assert (`len(KNOWN_VIOLATIONS) == N`) — auch S5f hatte keinen.
Mechanisch abgesichert ist nur die bidirektionale Mengengleichheit aus zwei Tests:
`test_no_unlisted_output_timezone_violations` (kein Fund ohne Eintrag) und
`test_known_violations_only_shrink` (kein Eintrag ohne Fund). Der „exakt N"-Teil war bei S5f eine
Behauptung im AC-Text, belegt durch Diff-Augenschein. Kein Präzedens zum Übernehmen.

## Offene Entscheidungsfrage für die Spec (PO)

Das Issue fordert wörtlich: *„Der Unterschied zwischen ‚noch nicht behoben' und ‚bewusst so' muss am
Ende zitierbar sein — das ist der eigentliche Zweck des Epics."* **Heute ist er es nicht.** Beide
Gate-Tests vergleichen ausschließlich Schlüssel; keine Zeile im Wächter liest je den
Beschreibungstext. „DAUERHAFT" und „Aufrufseite abgesichert" sind reine Prosa für menschliche Leser.

Im Repo existieren drei erprobte Mechaniken als Vorbild:

| Mechanik | Wo | Was sie erzwingt |
|---|---|---|
| Freitext ohne Prüfung | `KNOWN_VIOLATIONS` heute | nichts |
| Inline-Marker + Mindestbegründung | `gz-main-path` (#1409), `test_repo_path_hardcoding_ratchet.py:346` | Marker am Fundort, Begründung ≥15 Zeichen nach Unwort-Bereinigung; „x"/Emoji zählen nicht |
| Payload-Pinning gegen die Quelle | `PINNED_EXEMPT_AGGREGATIONS`, `test_compare_catalog_derives_from_central_catalog.py:347` | Vollständigkeit der Pin-Liste + Wert-Validierung gegen den lebenden Katalog |

Zu entscheiden: leert S5g nur die Liste (Abschlusskriterium des PO-Entscheids erfüllt), oder trennt
sie zusätzlich strukturell „echte Schuld" von „dokumentierter Dauerausnahme" (Ticket-Kern erfüllt)?

## Nebenbefunde (nicht Scope, gehen in die Triage)

1. **`_derive_is_day` vergleicht UTC-Tag gegen Ortstag** (`stage_weather.py:74`). Die
   Formbereinigung löst das *nicht*. Wirkung geprüft und belegt: OR-Semantik über alle Punkte, ein
   korrekt zugeordneter Tagpunkt erzwingt `1` — der Ausschluss nächtlicher Randstunden kann `1↔0`
   **nie** kippen. Einzig erreichbar ist `0 → None`, und nur wenn *alle* Punkte der Etappe in
   00:00–02:00 Ortszeit fallen. Einziger Leser im ganzen Repo (Python/Go/Frontend) ist die
   Icon-Auswahl `StageDetailRow.svelte:123`, wo der WMO-Code ohnehin Vorrang hat. → kosmetisch,
   praktisch unerreichbar, Known Limitation.
2. **Detektor-Schwäche Muster B:** `_is_hardcoded_zoneinfo_call` verlangt `ast.Constant` als
   Argument. `ZONE = "Europe/Vienna"` + `ZoneInfo(ZONE)` wird **nicht** erkannt (Argument ist
   `ast.Name`/`ast.Attribute`). Empirisch belegt: Scanner gegen `dispatch_orchestrator.py` gelaufen →
   `{}`, obwohl Literal und Verwendung beide im Scope liegen. Der Kopfkommentar-Anspruch „Muster B
   vollständig abgeräumt" gilt nur für die eine sichtbare Schreibweise.
3. **Scope-Lücke:** `src/providers/` wird gar nicht gescannt. Dort steht
   `ZoneInfo("Europe/Vienna")` (`geosphere.py:545`) — exakt das Zielmuster des Detektors, für ihn
   unsichtbar. Selbstkonsistent (der Request fragt dieselbe Zone an), aber unbewacht.
4. **Die Wien-Konstante lebt in Go weiter:** `internal/config/config.go:20`
   (`SCHEDULER_TIMEZONE`, Default `Europe/Vienna`), verwendet in `scheduler.go:146`. #1726 meldete
   „beide `VIENNA`-Konstanten sind weg" — das stimmt für Python. Die Go-Seite grenzt #1727
   ausdrücklich aus. Nach ADR-0051 ist der Cron nur noch Takt, nicht Tagesentscheidung — das ist
   plausibel, aber **ungeprüft**.
5. **Toter Code:** `compare_official_alert.py:396` `or timezone.utc`.
6. **Falsche Registerbeschreibung** bei `run_compare_presets_daily` (s.o.) — beim Entfernen des
   Eintrags erledigt sich das, aber es zeigt, dass die Freitext-Begründungen altern, ohne dass es
   jemand merkt.
7. **Nicht-deterministischer Zonen-Test** `_daytime_location()` (s.o.).

## Related Files

| File | Relevanz |
|---|---|
| `tests/test_output_timezone_guard.py` | der Wächter; `KNOWN_VIOLATIONS:526-645`, Gate-Tests `:669`/`:685` |
| `src/utils/timezone.py` | Helfer-Inventar, `to_utc`/`_as_utc` `:107-120` |
| die 6 Kandidaten-Dateien | s. Tabelle oben |
| `docs/specs/modules/fix_1727_s5f_raw_astimezone_formbereinigung.md` | direkte Vorlage für Spec-Form und Beweisstandard |
| `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` | Regel 1/2/3, normative Grundlage der Klassifikation |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | Spezialfall von Regel 2 |

## Risks & Considerations

- **Parallele Session auf `trip_alert.py`:** #1987 (kanalscharfer Alarm-Anker) ist in Phase 6 GREEN
  und ändert `_write_rolling_alarm_anchor` (~:796-806), `_get_cached_weather` (~:671-763);
  `_effective_anchor_age` und ein Ceiling-Block entfallen. Beide S5g-Kandidaten (:1028, :1274) liegen
  **semantisch außerhalb** — keine der geänderten Funktionen wird von ihnen aufgerufen. Aber gleiche
  Datei ⇒ Zeilendrift. Abgestimmt: #1987 mergt zuerst, S5g rebased danach.
- **Formbereinigung kann Verhalten ändern, wenn der falsche Helfer gewählt wird.** S5f hat das an
  einer Stelle (Ankunftstag am Ziel) bewusst vermieden: `to_utc()` hätte dort einen
  Westziel-Tagesverschiebungsbug eingeführt, `local_dt()` war richtig. Dieselbe Sorgfalt gilt hier,
  insbesondere bei Kandidat 8 (Ortszone, nicht UTC).
- **Zwei Kandidaten ohne Werte-Netz** (1 und 6) — der Umbau ist dort nur durch die Tests von
  `to_utc()` selbst gedeckt.
- **Kandidat 4** ist die einzige Stelle, deren Zonen-Zusicherung nicht deterministisch bewacht ist.
- Der Ortsvergleich ist als Produktthema zurückgestellt; drei Kandidaten liegen in Compare-Dateien.
  Das ist reine Zeitzonen-Hygiene am Bestand, kein Feature-Ausbau — die Spec muss das ausdrücklich
  abgrenzen.
