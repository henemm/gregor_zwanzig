---
entity_id: fix_2220_telegram_kommando_befunde
type: module
created: 2026-09-09
updated: 2026-09-09
status: implemented
version: "1.0"
tags: [bug, telegram, premium-sms, gewitter-ampel, timeline, kanalaufloesung]
---

# Drei Befunde aus der #1199-Volltriage: Telegram-Ampelfarbe, Timeline-Mischfall, unbekannter Kanalname

## Approval

- [ ] Approved

## Purpose

Diese Spec bündelt drei unabhängige Befunde aus der #1199-Volltriage, die alle im Pfad der
Telegram-/Premium-SMS-Kommandos liegen:

- **C5-63:** Der Telegram-Drilldown zeigt für dieselbe Gewitterstufe eine andere Farbe als die
  E-Mail — `_BAND_EMOJI` (`src/services/trip_command_processor.py:209`) widerspricht seinem
  eigenen Bandnamen.
- **C5-38:** Ein einzelner Wegpunkt ohne Tageswerte erzeugt in der Timeline eine Zeile, die
  aktiv „0,0 mm Regen" und „kein Gewitter" behauptet, statt der ehrlichen Datenlücken-Meldung.
- **C5-58:** `_resolve_channel_flags` (`src/services/trip_report_scheduler.py:1719-1765`) löst
  einen unbekannten Kanalnamen unbemerkt auf `(False, False, False, False)` auf und behauptet
  dabei „kein Kanal konfiguriert", statt den unerkannten Namen zu protokollieren.

**Korrektur zum Issue-Titel:** Der Titel nennt „Telegram-/Premium-SMS-Kommandos" pauschal für
alle drei Befunde. Premium-SMS ist von **C5-63 nicht betroffen** — der Telegram-Drilldown ist
der einzige Kanal mit Emoji-Ausgabe (`with_emoji = channel == "telegram"`), Premium-SMS zeigt
nur das Wort. C5-38 und C5-58 wirken dagegen über alle drei Eingangskanäle (Telegram,
E-Mail-Freitext, Premium-SMS).

## Source

- **File:** `src/services/trip_command_processor.py` (C5-63, C5-38)
- **File:** `src/services/trip_report_scheduler.py` (C5-58)
- **Identifier:** `_BAND_EMOJI` / `_thunder_symbols` / `_thunder_fmt` (C5-63);
  `_mit_datiertem_rueckfall` / `_traegt_tageswerte` (C5-38); `_resolve_channel_flags` (C5-58)

Python-Core (`src/services/`) — keine Berührung mit Go (`internal/`) oder Frontend.

## Estimated Scope

- **LoC:** ~125–220
- **Files:** 6 (2 Produktivdateien, 1 geänderte + 3 neue Testdateien)
- **Effort:** medium

| Datei | Änderung |
|---|---|
| `src/services/trip_command_processor.py` | MODIFY — C5-63: `_BAND_EMOJI` (`:209`) bandtreu setzen · C5-38: `_mit_datiertem_rueckfall` (`:1390-1446`) von Tages- auf Punktgranularität |
| `src/services/trip_report_scheduler.py` | MODIFY — C5-58: Namens-Guard + `logger.warning` vor dem Return (`:1747-1753`) |
| `tests/tdd/test_thunder_stage_words_from_canonical_source.py` | MODIFY — `:75-96` zementiert den Ist-Stand, wird auf Zielskala A umgestellt |
| `tests/tdd/test_gewitter_ampel_bandtreu.py` | CREATE — AC-1/AC-2/AC-3 |
| `tests/tdd/test_timeline_punktgenauer_rueckfall.py` | CREATE — AC-4/AC-5/AC-6 |
| `tests/tdd/test_unbekannter_kanalname_warnung.py` | CREATE — AC-8/AC-9 |

**Warum neue Dateien statt Eingriff in `test_timeline_tagesgenaue_quellen.py` /
`test_kanaltreue_adhoc_antwort.py`:** beide Bestandsdateien sind Nichtregressions-Anker (siehe
„Zu wahrende Bestandstests" unten, u. a. #1818 AC-4/AC-7/F001/F005 und `feat_2126` AC-5) und
durften sich nicht bewegen; das Projekt benennt Testdateien nach Verhalten, nicht nach
Issue-Nummer — die drei neuen RED-Nachweise bekamen deshalb eigene, verhaltensbenannte Dateien.

**LoC-Hinweis:** C5-38 (~90–160 LoC, dreifach abgesicherter Bereich #1818/#2186) ist der Posten
mit Sprengpotenzial. Falls das Limit fällt: `workflow.py set-field loc_limit_override 500` —
nicht den Fix künstlich verengen.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `thunder_ampel_band()` / `_THUNDER_AMPEL_BAND` (`src/output/metric_format.py:307-326`) | function/dict | Kanonische Stufe→Band-Quelle für C5-63 — **nicht ändern** |
| `_AMPEL_DOT_COLORS` (`src/output/renderers/email/helpers.py:591-596`) | dict | Mail-seitige Band→Farbe-Referenz, mit der C5-63 Parität herstellt — **nicht ändern** |
| `THUNDER_LABEL_DE` (`src/app/thunder_scale.py`) | dict | Liefert die vier Stufennamen, aus denen `_thunder_symbols()` iteriert |
| `WeatherExtractor.timeline_dated` (`src/services/weather_extractor.py`) | method | Liefert den datierten Snapshot, gegen den C5-38 einzelne Punkte ersetzt — **nicht ändern** |
| `sms_allowed()` / `premium_sms_allowed()` (`src/services/user_tier.py`) | function | Tier-Gates, bleiben bei C5-58 unverändert wirksam — der Guard prüft nur den Namen |
| `official_alerts.py` (gesamter Pfad) | module | Amtliche Warnstufen-Emojis — von C5-63 nicht berührt, siehe Begründung unten — **nicht ändern** |

## Implementation Details

### C5-63 — `_BAND_EMOJI` bandtreu setzen

```python
# src/services/trip_command_processor.py:209
_BAND_EMOJI = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}
```

Ist-Stand: `{"green": "⚪", "yellow": "🟢", "orange": "🟡", "red": "🔴"}` — drei von vier
Einträgen widersprechen ihrem eigenen Schlüssel. Sichtbar nur über `_thunder_symbols()`
(`:219-224`) → `_thunder_fmt()` (`:301`), und dort nur bei `with_emoji = channel == "telegram"`
(Drilldown Gewitter, Drilldown Stundenspalte). Die Timeline (`_fmt_timeline:1666`) sowie
E-Mail/SMS/Premium-SMS zeigen ohnehin nur das Wort, nicht das Symbol — dort ändert sich nichts.

Das Dict bleibt **lokal**, kein Umzug nach `metric_format.py`: ADR-0025 Entscheidung 3 verbietet
lokale Dict-Literale, die auf `ThunderLevel`-Enum-Werten geschlüsselt sind (Muster `_TH_VAL`,
Zahlenskalen), nicht bandnamen-geschlüsselte Symboltabellen. `_BAND_EMOJI` ist strukturell
identisch zum bereits akzeptierten `_AMPEL_DOT_COLORS`
(`src/output/renderers/email/helpers.py:591`) — Band→Visual-Symbol lebt im konsumierenden
Renderer-Modul. Ein Umzug bräche dieses Muster.

**Warum Zielskala A und nicht die naheliegende Alternative (⚪ für NONE behalten):**
`trip_command_processor.py` importiert `official_alerts` nirgends — das amtliche Warnstufen-
Emoji wird ausschließlich in `render_official_alert_telegram` (`official_alerts.py:1839`)
emittiert, erreichbar nur über `narrow.py:416`, `comparison.py:813` und
`notification_service.py:1075`. Die beiden Emoji-Sätze erzeugen getrennte `CommandResult`-
Objekte, also getrennte Nachrichten — sie können einander in derselben Telegram-Nachricht nie
begegnen. Zusätzlich wird die amtliche Warnstufe 1 (🟢) strukturell nie gerendert: alle
Rendering-Pfade filtern vorher auf `level >= 2` (`narrow.py:406`, `comparison.py:801`,
`alert_urgency.py:80-89`, `hazard_symbols.py:34,37`). Die einzige Begründung für „⚪ behalten"
— Verwechslungsgefahr mit dem amtlichen 🟢 — entfällt damit vollständig. Der einzige sichtbare
Zusatzeffekt der Umstellung ist NONE ⚪ → 🟢, was bereits der PO-Entscheidung aus
`fix_1491_gewitter_ampelkreis.md:252-255` (grüner Kreis für NONE in der Trip-Stundentabelle)
folgt.

### C5-38 — Punktgranularität statt Tagesgranularität in `_mit_datiertem_rueckfall`

`src/services/trip_command_processor.py:1390-1446`. Ist-Stand: die Entscheidung „Anker behalten
oder datierten Snapshot nachziehen" fällt pro Tag als Alles-oder-nichts —

```python
if any(_traegt_tageswerte(timeline.points[i]) for i in tages_idx):
    continue                       # :1425 — sobald IRGENDEIN Punkt trägt, bleibt der GANZE Tag
verworfen.update(tages_idx)        # :1433 — sonst verwirft es ALLE Punkte des Tages
```

Ein Tag mit einem tragenden und einem leeren Punkt behält beide unverändert; der leere Punkt
rendert `?–? °C` und behauptet zusätzlich aktiv `0.0 mm` Regen (`else "0.0"`, nicht `"?"`,
`_fmt_timeline:1665`) und `"kein"` Gewitter (`_thunder_words().get(..., "NONE", …)`).

**Neue Logik:** pro Tag werden die tragenden Anker-Punkte behalten; jeder einzelne
**nicht-tragende** Anker-Punkt wird durch den zu ihm gehörenden Punkt des datierten Snapshots
ersetzt, sofern dieser trägt — trägt auch der nicht, entfällt der Punkt ganz. Die
Tag-für-Tag-Schleife (`for target_date, tz in tage`) und der Tagesfilter
(`local_dt(p.arrival_time, tz).date() == target_date`) bleiben unverändert; geändert wird nur,
**welche** Punkte innerhalb eines Tages ersetzt bzw. verworfen werden — nicht mehr der ganze
Tag auf einmal.

**Vollständige Fallunterscheidung je Tag** (`src/services/trip_command_processor.py:1430-1462`
— maßgeblich ist der Code, nicht diese Skizze):

- **Fall (a):** der Anker trägt JEDEN Punkt des Tages (`tages_idx and not fehlend`) → `continue`,
  kein Snapshot-Abruf. Unverändert AC-4/AC-7 (#1818): der Anker gewinnt, keine Nebenwirkung.
- **Fall (b), der #1818-KERNFALL:** der Anker kennt den Tag überhaupt nicht (`tages_idx == []`
  — der undatierte Anker trägt strukturell nur EINEN Tag). Der Tag wird **vollständig** aus dem
  datierten Snapshot übernommen, wie vor #2220.
  🔴 **Fall (b) darf NICHT mit Fall (c) zusammengelegt werden:** `fehlend` wäre für einen
  Tag ohne `tages_idx` immer leer (`fehlend = [i for i in tages_idx if ...]` — leere Eingabe,
  leeres Ergebnis), und ein auf `fehlend` bedingter Zweig würde diesen Fall fälschlich
  überspringen, sodass der Snapshot nie geholt wird und der Tag stumm leer bliebe. Genau hierauf
  ist die Implementierung beim ersten Anlauf hereingefallen; erst der Review hat es gefangen.
- **Fall (c), der Mischfall (neu, C5-38):** der Anker kennt den Tag, aber mindestens ein
  Anker-Punkt trägt nicht (`fehlend` nicht leer) — nur die einzelnen nicht-tragenden
  Anker-Punkte werden über `label` gegen den passenden Snapshot-Punkt ersetzt (bei Treffer)
  bzw. verworfen (sonst); tragende Anker-Punkte bleiben unangetastet.

```python
for target_date, tz in tage:
    tages_idx = [i for i, p in enumerate(timeline.points)
                 if local_dt(p.arrival_time, tz).date() == target_date]
    fehlend = [i for i in tages_idx if not _traegt_tageswerte(timeline.points[i])]

    if tages_idx and not fehlend:          # Fall (a)
        continue

    datiert = extractor.timeline_dated(trip_id, target_date, from_time)
    tages_snapshot = [p for p in datiert.points
                       if local_dt(p.arrival_time, tz).date() == target_date]

    if not tages_idx:                      # Fall (b) — #1818-Kernfall, NICHT mit (c) zusammenlegen
        ergaenzt.extend(p for p in tages_snapshot if _traegt_tageswerte(p))
        continue

    snapshot_by_label = {p.label: p for p in tages_snapshot}  # Fall (c) — Mischfall
    for i in fehlend:
        verworfen.add(i)
        ersatz = snapshot_by_label.get(timeline.points[i].label)
        if ersatz is not None and _traegt_tageswerte(ersatz):
            ergaenzt.append(ersatz)
```

**Zuordnung Anker-Punkt ↔ Snapshot-Punkt: über `label` (Segment-ID), nicht `arrival_time` und
nicht Index.** `TimelinePoint.label` wird bei der Erzeugung mit `str(seg.segment.segment_id)`
befüllt (`weather_extractor.py:125`) — eine vom Wetterlauf unabhängige Kennung derselben
Route-Etappe. `arrival_time` scheidet aus: `display_end_time(seg.segment)` kann sich zwischen
zwei Snapshot-Läufen geringfügig verschieben (Tempo-/Zeitfenster-Neuberechnung), ohne dass es
sich um einen anderen Wegpunkt handelt — eine Zeit-Gleichheit wäre damit zu strikt und ließe
echte Übereinstimmungen ins Leere laufen. Der Index scheidet aus derselben Begründung wie im
Kontext-Dokument aus: Anker und datierter Snapshot stammen aus verschiedenen Läufen, bei
zwischenzeitlich geänderter Routenstruktur (Etappe hinzugefügt/entfernt) ist Index-Gleichheit
nicht garantiert. `label` ist die einzige der drei Kandidaten, die die Identität der Etappe
trägt statt eines abgeleiteten Werts.

Die konkrete Zuordnung läuft im Fall-(c)-Zweig des vollständigen Codeblocks oben
(`snapshot_by_label = {p.label: p for p in tages_snapshot}`) — kein separater Codepfad.

Findet sich zu einem nicht-tragenden Anker-Punkt kein Snapshot-Punkt mit demselben `label`
(z. B. weil die Etappe im datierten Snapshot nicht mehr existiert), verhält es sich wie „auch
der Snapshot trägt nicht": der Punkt entfällt.

Die drei Ausgabestellen (`_fmt_timeline:1642-1653`, `_fmt_glance:1571-1586`,
`_fmt_gewitter:1599-1602`) werden **nicht** angefasst: sie prüfen bereits „Liste leer?" und
rufen dann `_tagesaussage_ohne_daten` — ein leergefegter Tag erzeugt die ehrliche Fehlanzeige
von selbst, weil `verworfen` jetzt auch den letzten verbliebenen Punkt eines Tages erfassen
kann.

### C5-58 — Namens-Guard vor `_resolve_channel_flags`

```python
# src/services/trip_report_scheduler.py:1747 ff.
_BEKANNTE_KANAELE = {"email", "sms", "premium_sms", "telegram"}

if restrict_to_channel is not None:
    if restrict_to_channel not in _BEKANNTE_KANAELE:
        logger.warning(
            "Unbekannter Kanalname in restrict_to_channel: %r", restrict_to_channel
        )
    return (
        restrict_to_channel == "email",
        restrict_to_channel == "sms" and sms_allowed(user_id),
        restrict_to_channel == "premium_sms" and premium_sms_allowed(user_id),
        restrict_to_channel == "telegram",
    )
```

**Der Rückgabewert bleibt unverändert** `(False, False, False, False)` — geändert wird
ausschließlich die Beobachtbarkeit über ein zusätzliches `logger.warning`. Kein `ValueError`,
kein Kanal-Enum: der Aufrufer müsste sonst einen bisher tolerierten Zustand hart behandeln, was
für einen latenten Defekt (siehe Known Limitations) unverhältnismäßig wäre; ein Kanal-Enum wäre
ein Cross-Cutting-Refactoring über sechs unabhängige Ad-hoc-Kanallisten im Repo, eine
Größenordnung über dem Nutzen dieses Tickets.

**Die Falle:** `restrict_to_channel="sms"` bei `sms_allowed(user_id) == False` ergibt exakt
`(False, False, False, False)` — ein legitimer, spezifizierter Zustand (`feat_2126` AC-5,
`tests/tdd/test_kanaltreue_adhoc_antwort.py:563`). Der Guard prüft deshalb ausschließlich, ob
`restrict_to_channel` selbst ein bekannter Name ist — **nicht**, ob das Ergebnis-Tupel vier
`False` enthält. Für `"sms"` (ein bekannter Name) feuert der Guard nie, unabhängig vom
Tier-Ergebnis.

## Expected Behavior

- **Input (C5-63):** Telegram-Drilldown-Anfrage (`dd_thunder_today|tomorrow`,
  `dd_hours_today|tomorrow`) für eine Etappe mit Gewitterstufe LOW oder MED.
  **Output:** Die Zeile trägt 🟡 (LOW) bzw. 🟠 (MED) — dieselbe Farbe wie die E-Mail für
  dieselbe Stufe. **Side effects:** keine — reine Darstellungskorrektur.

- **Input (C5-38):** `glance`/`heute_gewitter`/`timeline_heute`/`timeline_morgen` für einen Tag,
  dessen Anker-Punkte teils tragen, teils nicht. **Output:** kein gerendeter Punkt behauptet
  `0.0 mm`/`kein Gewitter` ohne zugrundeliegende Messung; ein Tag ohne jede tragende Quelle löst
  die ehrliche Datenlücken-Meldung aus. **Side effects:** keine — reine Leseoperation, kein
  Netzabruf, kein Schreibvorgang (unverändert AC-7 aus #1818).

- **Input (C5-58):** `restrict_to_channel` mit einem Namen außerhalb der vier bekannten Kanäle.
  **Output:** Rückgabewert unverändert `(False, False, False, False)`, zusätzlich eine
  Log-Warnung mit dem unbekannten Namen. **Side effects:** keine funktionale Änderung, nur
  Observability.

## Acceptance Criteria

- **AC-1:** Given eine Etappe mit Gewitterstufe LOW („leicht") / When der Telegram-Drilldown
  `dd_thunder_today` abgerufen wird / Then trägt die Zeile 🟡, nicht 🟢.
  - Test: `CommandResult` für `dd_thunder_today` mit einer LOW-Fixture erzeugen, den
    tatsächlich zurückgegebenen Text auf das Symbol vor „leicht" prüfen.

- **AC-2:** Given alle vier Ampelbänder (NONE/LOW/MED/HIGH) / When der Telegram-Drilldown für
  jedes Band gerendert wird / Then entspricht jedes Symbol der Farbe seines eigenen Bandnamens.
  Die erwarteten Symbole werden aus der kanonischen Quelle `thunder_ampel_band()`
  (`src/output/metric_format.py:307-326`) abgeleitet, nicht als Literale im Test gesetzt.
  - Test: für jede `ThunderLevel`-Stufe `thunder_ampel_band(level)` aufrufen, daraus das
    erwartete Symbol über eine im Test lokal definierte Band→Symbol-Referenz (grün→🟢,
    gelb→🟡, orange→🟠, rot→🔴) ableiten und gegen den tatsächlich gerenderten Drilldown-Text
    vergleichen — keine Kopie von `_BAND_EMOJI` selbst als Erwartungswert.

- **AC-3:** Given dieselbe Gewitterstufe / When sowohl die E-Mail (CSS-Ampelpunkt,
  `_AMPEL_DOT_COLORS`) als auch der Telegram-Drilldown gerendert werden / Then bezeichnen beide
  Ausgaben dieselbe Farbstufe — keine Verschiebung um ein Band.
  - Test: für dieselbe Fixture beide Renderpfade aufrufen (Mail-Helper `_ampel_dot_css` /
    Telegram `_thunder_fmt`), die jeweils erzeugte Farbbezeichnung (Mail: CSS-Farbname;
    Telegram: Symbol, gemappt auf denselben Farbnamen) auf Gleichheit prüfen.

- **AC-4:** Given ein Tag mit mehreren Zeitpunkten, von denen mindestens einer trägt und
  mindestens einer nicht trägt, und ein datierter Snapshot, der für den nicht-tragenden
  Zeitpunkt (gleiches `label`) Werte trägt / When `timeline_heute` abgerufen wird / Then
  enthält keine gerenderte Zeile `?–? °C`; der nicht-tragende Zeitpunkt zeigt die Werte aus dem
  datierten Snapshot.
  - Test: Zwei-Punkte-Tag mit einem vollständigen und einem leeren Anker-Punkt konstruieren
    (`_TAGESWERTE`-Felder alle `None` am zweiten Punkt), passenden datierten Snapshot mit
    demselben `label` und echten Werten bereitstellen, `timeline_heute` aufrufen, den
    zurückgegebenen Text auf Abwesenheit von `?–?` und Anwesenheit der Snapshot-Werte prüfen.

- **AC-5:** Given ein Zeitpunkt, der weder im Anker noch im datierten Snapshot trägt (gleiches
  `label` in beiden, beide ohne Tageswerte) / When die Timeline gerendert wird / Then fehlt
  dieser Zeitpunkt vollständig in der Ausgabe — insbesondere wird weder „0.0 mm" Regen noch
  „kein" Gewitter für ihn behauptet.
  - Test: Zwei-Punkte-Tag wie in AC-4, aber der datierte Snapshot trägt für das betroffene
    `label` ebenfalls keine Werte; geprüft wird, dass der zugehörige Zeitstempel in der
    gerenderten Zeilenliste nicht mehr vorkommt (nicht nur, dass `?–?` fehlt).

- **AC-6:** Given ein Tag, dessen sämtliche Anker-Punkte nicht tragen und für den auch der
  datierte Snapshot nichts trägt / When `glance`, `timeline_heute` oder `heute_gewitter`
  abgerufen wird / Then erscheint die ehrliche Datenlücken-Meldung (`_tagesaussage_ohne_daten`),
  nicht eine leere oder aus Fragezeichen bestehende Zeilenliste.
  - Test: einen Tag ohne jede tragende Quelle durch alle drei Formatierer laufen lassen, den
    zurückgegebenen Text auf die bekannte Datenlücken-Formulierung prüfen.

- **AC-7 (Regression):** Given ein Tag, dessen Anker-Punkte vollständig tragen, und ein
  ebenfalls tragender datierter Snapshot desselben Tages / When die Timeline gerendert wird /
  Then bleibt der undatierte Anker maßgeblich (#1818 AC-4: Anker schlägt Snapshot) und kein
  Rückfall-Wegpunkt rutscht in den Nachbartag (#1818 F001).
  - Test: bestehende Fixtures aus `test_timeline_tagesgenaue_quellen.py:406` (AC-4) und `:763`
    (F001) unverändert grün — kein neuer Testcode nötig, dieses AC bindet die Nichtregression.

- **AC-8:** Given `restrict_to_channel` trägt einen Namen außerhalb der vier bekannten Kanäle
  (z. B. `"whatsapp"`) / When die Kanal-Flags über `_resolve_channel_flags` aufgelöst werden /
  Then wird eine Log-Warnung protokolliert, die den unbekannten Namen wörtlich nennt; der
  Rückgabewert bleibt `(False, False, False, False)`.
  - Test: `_resolve_channel_flags(config, user_id, restrict_to_channel="whatsapp")` aufrufen,
    mit `caplog`/Log-Capture prüfen, dass genau eine Warnung mit `"whatsapp"` im Text erzeugt
    wurde.

- **AC-9 (Falle):** Given `restrict_to_channel="sms"` bei einem Nutzer ohne SMS-Tier-
  Berechtigung (`sms_allowed(user_id) == False`) / When die Kanal-Flags aufgelöst werden / Then
  wird **keine** Warnung protokolliert; das Ergebnis bleibt `(False, False, False, False)`, und
  `feat_2126` AC-5 (`tests/tdd/test_kanaltreue_adhoc_antwort.py:563`) bleibt unverändert grün.
  - Test: `_resolve_channel_flags(config, user_id, restrict_to_channel="sms")` mit einem echten
    Nutzerprofil ohne SMS-Tier aufrufen (kein Stub von `sms_allowed`, Muster wie `feat_2126`
    AC-5), Log-Capture prüft Abwesenheit jeder Warnung; zusätzlich Ausführung des bestehenden
    `test_kanaltreue_adhoc_antwort.py:563`-Tests als Nichtregressions-Beleg.

## Known Limitations

1. **C5-58 ist ein latenter Robustheitsdefekt ohne heute belegtes Nutzersymptom.** Alle drei
   `InboundMessage`-Erzeuger setzen ein hartkodiertes Literal (`inbound_email_reader.py:176` →
   `"email"`, `inbound_telegram_reader.py:232,328` → `"telegram"`, `inbound_sms_reader.py:264`
   → `"premium_sms"`); ein unbekannter Kanalname kann heute nur durch eine künftige
   Codeänderung an einem dieser Reader entstehen. Dieses Ticket kennzeichnet C5-58 deshalb
   ausdrücklich **nicht** als nutzersichtbaren Bug, sondern als vorbeugende Beobachtbarkeit für
   einen fünften Kanal. #2220 ist damit **keine Präzedenz** dafür, dass latente Befunde ohne
   belegtes Nutzersymptom künftig automatisch eigene Issues bekommen — die
   Nebenbefund-Triage-Regel (drei Ausnahmekriterien) bleibt unverändert in Kraft.

2. **C5-38 Punkt-Zuordnung: entschieden über `label` (Segment-ID), nicht `arrival_time` oder
   Index.** `TimelinePoint.label` wird bei der Punkterzeugung mit
   `str(seg.segment.segment_id)` befüllt (`weather_extractor.py:125`) — einer vom konkreten
   Wetterlauf unabhängigen Kennung derselben Route-Etappe. `arrival_time` scheidet als
   Zuordnungsschlüssel aus, weil `display_end_time(seg.segment)` sich zwischen zwei
   Snapshot-Läufen leicht verschieben kann, ohne dass ein anderer Wegpunkt gemeint ist — eine
   Zeitgleichheit wäre zu strikt. Der Index scheidet aus, weil Anker und datierter Snapshot aus
   verschiedenen Läufen stammen und bei zwischenzeitlich geänderter Routenstruktur (Etappe
   hinzugefügt/entfernt) keine Index-Gleichheit garantiert ist. Findet sich zu einem
   nicht-tragenden Anker-Punkt kein Snapshot-Punkt mit demselben `label`, entfällt der Punkt —
   dasselbe Verhalten wie wenn beide Quellen leer sind.

3. **Die `0.0 mm`/`kein`-Fallbacks werden nur dort repariert, wo der Mischfall sie erzeugt.**
   Dieses Ticket ändert `_fmt_timeline`/`_fmt_day_agg` selbst **nicht** — durch die
   Punkt-Entfernung in `_mit_datiertem_rueckfall` steht der leere Punkt gar nicht mehr in der
   Liste, die Formatierer bleiben unberührt (`_fmt_timeline:1665`, `_fmt_day_agg:1550`). Die
   breite Fläche — alle Stellen, an denen `precip`/`thunder` bei fehlender Messung außerhalb
   dieses Mischfalls eine Zahl bzw. „kein" behaupten — geht als Checkbox-Zeile nach **#1199**;
   kein eigenes Issue, weil über #2220 hinaus kein nutzersichtbares Fehlverhalten belegt ist.

4. **`test_thunder_stage_words_from_canonical_source.py:75-96` wird geändert, nicht nur
   gelesen.** Der Test zementiert aktuell den fehlerhaften Ist-Stand
   (`(LOW,"leicht","🟢")`, `(MED,"mittel","🟡")`). Er wird auf Zielskala A umgestellt
   (`(NONE,"kein","🟢")`, `(LOW,"leicht","🟡")`, `(MED,"mittel","🟠")`,
   `(HIGH,"hoch","🔴")`). Das ist eine legitime Anpassung — der Test prüfte veraltetes
   Verhalten —, aber ausdrücklich keine nachträgliche Test-Anpassung an unbeabsichtigten Code:
   sie ist Teil des Fix-Ziels dieser Spec.

## Zu wahrende Bestandstests

| Datei:Zeile | Zusicherung |
|---|---|
| `tests/tdd/test_timeline_tagesgenaue_quellen.py:406` | AC-4 (#1818): undatierter Anker schlägt den datierten Snapshot |
| dto. `:530` | AC-7 (#1818): Antwort schreibt nichts und ruft nichts ab |
| dto. `:676` | F005 (#1818): leerer Platzhalter verliert gegen echte Werte |
| dto. `:723` | F005-Grenzfall (#1818): beide Quellen leer → ehrliche Datenlücke |
| dto. `:763` | F001 CRITICAL (#1818): Rückfall-Wegpunkt rutscht nicht in den Nachbartag |
| `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py:558-620` | #2186: Rückfall ist genauso ab Anfragezeit gefenstert wie der Anker |
| `tests/tdd/test_kanaltreue_adhoc_antwort.py:563` | feat_2126 AC-5: SMS-Override ohne Tier-Berechtigung bleibt vier-mal `False` |
| dto. `:566-569` | feat_2126 AC-5: Tier-Gate wird durch das Override nicht umgangen |
| `tests/test_chip_ampel_farben.py` | Mail-seitige Ampelfarben (CSS-Punkte) — unverändert |
| `tests/tdd/test_outlook_metric_ampelfarben.py` | dto. |
| `tests/tdd/test_thunder_column_ampel.py` | dto. |
| `tests/tdd/test_issue_811_mode_matrix.py:29` | dto. |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** ADR-0025 wurde geprüft und trifft auf `_BAND_EMOJI` nicht zu — es verbietet
  lokale Dict-Literale, die auf dem `ThunderLevel`-Enum geschlüsselt sind (Zahlenskalen-Muster
  `_TH_VAL`), nicht bandnamen-geschlüsselte Symboltabellen. `_BAND_EMOJI` ist strukturell
  identisch zum bereits akzeptierten `_AMPEL_DOT_COLORS`
  (`src/output/renderers/email/helpers.py:591`); ein Umzug nach `metric_format.py` bräche
  dieses etablierte Muster (Band→Visual-Symbol lebt im konsumierenden Renderer-Modul), statt
  eine neue Entscheidungsfläche zu eröffnen. C5-38 und C5-58 sind additive Korrekturen
  innerhalb bereits bestehender Muster (Punktgranularität statt Tagesgranularität in einer
  bestehenden Funktion; ein zusätzlicher Guard vor einer bestehenden Rückgabe) und berühren
  keine Kanal-, Provider-, Datenmodell- oder Auth-Entscheidung.

## Changelog

- 2026-09-09: Initial spec created
- 2026-09-09: Umsetzung abgeschlossen; Dateitabelle, Fallunterscheidung (b) und Pfad der
  Mode-Matrix-Datei nach der Validierung richtiggestellt — ACs unverändert.
