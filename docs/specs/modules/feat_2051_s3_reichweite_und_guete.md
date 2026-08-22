---
entity_id: feat_2051_s3_reichweite_und_guete
type: feature
created: 2026-08-22
updated: 2026-08-22
status: approved
version: "1.0"
tags: [alarm, briefing, nowcast, radar, reichweite, guete]
---

# Reichweite der Quelle und Güte-Kennzeichnung — #2051 Scheibe S3

## Approval

- [x] Approved — PO-Freigabe der Acceptance Criteria am 2026-08-22 (v1.0)

## Purpose

Der Radar-Nowcast-Pfad sagt heute, seit Scheibe S1 (#2051), wann ein
Niederschlagsereignis beginnt und endet — aber nicht, **wie weit die Quelle
selbst reicht** und **wie belastbar** ihre Ortsangabe über die Zeit ist. Zwei
Fragen, zwei Antworten:

1. **Reichweite:** Bis zu welchem Zeitpunkt hat die Quelle tatsächlich
   Frames geliefert? Das ist heute nur indirekt und nur im Regenfall
   sichtbar (`event_ongoing_beyond_horizon`) — ein Nutzer, bei dem es
   trocken bleibt oder dessen Ereignis vor dem Horizont endet, erfährt nie,
   wie weit die Beobachtung selbst reicht.
2. **Güte:** Ab wann sinkt die Verlässlichkeit der Ortsangabe? Die
   GeoSphere-INCA-Quelle extrapoliert das gesamte abgerufene Fenster (keine
   Analyse-Teilstrecke); jenseits von ~60 Minuten Vorlauf sinkt ihre
   Ortsschärfe deutlich (belegter Code-Kommentar, `radar_service.py:110f`).
   Bei einem Vorlauf von 90 Minuten liegt ein gemeldetes Ereignis am Rand der
   Radar-Reichweite — das ist der konkrete Fall aus dem PO-Ticket-Kommentar
   vom 2026-08-21.

Beide Angaben werden aus den bereits abgerufenen `frames` bzw. aus den in S1
bestimmten `onset_minutes`/`event_end_minutes` abgeleitet — **kein**
zusätzlicher Quellenabruf. Beide werden als **Datum über die Aussage**
ausgeliefert, nicht als Bewertung und nicht als Handlungsempfehlung
(Ticket-Grundprinzip).

Vorgänger: S1 (Dauer/Ende) ist seit 2026-08-22 08:46 UTC live (`c684d053`).
S2 (räumliche Ausdehnung) und S4 (`/strecke`-Kommando) aus Issue #2051
bleiben außerhalb dieses Zuschnitts; das Ticket bleibt als Scheiben-Ticket
offen.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `_derive_result()` (Z. 877ff.), `NowcastResult` (Z.
  136-224), neue Konstante `LOCATION_SHARPNESS_LIMIT_MIN`

Begleitend: `src/output/renderers/alert/model.py` (`OnsetEvent`),
`src/output/renderers/alert/project.py` (geteilte Anzeigefassungen, analog
`event_end_display`, Z. 60-67), `src/output/renderers/alert/render.py`
(sieben Textstellen, analog `_onset_end_suffix`/`_sms_onset_ende`),
`src/output/renderers/email/starkregen_hint.py` (Briefing-Kurzfristhinweis),
`src/services/notification_service.py` (`starkregen_nowcast`-Tupel, Z. 116),
`src/services/trip_report_scheduler.py` (Tupel-Aufbau, Z. 1893-1904,
Auspacken Z. 406-412), `api/routers/validator.py` (`OnsetPayload`,
Vorschau-/Replay-Weg).

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Core
> (`src/services/`, `src/output/`, `api/routers/`) — kein Go-API-, kein
> Frontend-Anteil.

## Estimated Scope

- **LoC:** ~160-200 produktiv, ~150-190 Tests — **über dem 250-LoC-
  Workflow-Limit** in Summe, `workflow.py set-field loc_limit_override 500`
  ist vor `/40-tdd-red` einzuplanen (Muster wie S1).
- **Files:** ~9-10 Produktivdateien (`radar_service.py`, `model.py`,
  `project.py`, `render.py`, `starkregen_hint.py`, `notification_service.py`,
  `trip_report_scheduler.py`, `api/routers/validator.py`,
  `validator_render_service.py`) + ~8-10 Testdateien.
- **Effort:** medium-high — kleiner als S1 (keine neue Grenzfindungs-
  Rekursion, kein Tagesversatz-Sonderfall), aber sieben Textstellen plus
  zwei neue Anzeigefassungen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_derive_wet_block_end` / `_derive_result` | function (`radar_service.py:278,877`) | Liefert bereits `window`, `all_ts_sorted`, `horizon`, `now` — dieselben Bausteine tragen die Reichweiten-Ableitung, kein zweiter Rechenkern. |
| `_MAX_FRAME_COVERAGE` | constant (`radar_service.py:95`, 15 Min) | Deckungsgrenze eines einzelnen Frames — dieselbe Mechanik wie bei `_accumulate_precip_mm`/`_derive_wet_block_end` trägt auch die Reichweite. |
| `_NOWCAST_HORIZON_MIN` | constant (`radar_service.py:69`, 180) | Deckel der Reichweite — Reichweite ist NIE größer als der Horizont, kann aber kleiner sein. |
| `RADAR_ONSET_THRESHOLD_MIN` | constant (`radar_service.py:121`, 55) | Nachbar-Schwelle, von der `LOCATION_SHARPNESS_LIMIT_MIN` bewusst getrennt bleibt (E2) — von dieser Spec unberührt. |
| `NowcastResult.onset_minutes` / `.event_end_minutes` | fields (`radar_service.py:139`, S1) | Eingabe der Güte-Prüfung — die Güte hat keine eigene Quellen-Herkunft, sie vergleicht diese beiden bereits vorhandenen Zeiten gegen die Grenze (E2). |
| `event_end_display` | function (`project.py:60-67`, S1) | Musterfassung für die neuen Anzeigefunktionen `source_reach_display`/`location_sharpness_display` — dieselbe Struktur (`now_utc`, `nowcast`/Werte, `tz` → `(str \| None, int)`). |
| `_onset_end_suffix` / `_sms_onset_ende` | functions (`render.py:546,806`, S1) | Musterfassung für `_onset_reach_suffix`/`_onset_sharpness_suffix`/`_sms_onset_sharpness_marker` — additiv anhängbares Textstück oder leer. |
| `starkregen_nowcast: tuple[...]` | field (`notification_service.py:116`) | Bereits fünfgliedriges Tupel (S1/#2050) — wächst additiv um Reichweite und Güte-Grenzzeit, Muster identisch. |
| `OnsetPayload` | Pydantic-Model (`api/routers/validator.py:~240`) | Vorschau-Payload-Schema — muss die neuen Felder kennen, sonst Adversary-Fund wie #2046 F002 / S1-Vorwarnung. |

## Getroffene Entscheidungen (E1–E7, aus Phase 2 — nicht erneut vorlegen)

**E1 — Zwei getrennte Felder, nicht eines.** `NowcastResult` bekommt die
Reichweite der Quelle als eigenes Feld (Arbeitsname
`source_reach_minutes`, Minuten ab jetzt bis zum Ende der Deckung des
LETZTEN gelieferten Frames, gedeckelt am Prüfhorizont). Diese Größe ist
NICHT `_NOWCAST_HORIZON_MIN`: der Horizont ist, wie weit geprüft wird; die
Reichweite ist, wie weit die Quelle tatsächlich geliefert hat. Die Quelle
kann früher enden (Datenlücke, kürzeres Produkt). Ein Feld, das beides
vermischt, wäre ein blinder Wächter — es gäbe dann nur EINE
Abweichungsstelle für ZWEI Bezugspunkte.

**E2 — Güte ist eine Zeitschwelle, kein Quellen-Merkmal.**
`NowcastResult.source` ist ein einziger String für den ganzen Abruf; es
gibt keine Angabe je Frame, ob er Analyse oder Extrapolation ist. Bei INCA
ist das gesamte abgerufene Fenster Extrapolation — es gibt keinen
gemessenen Teil, von dem sich ein „ab hier" abgrenzen ließe. Die
Güte-Grenze wird deshalb aus dem VORLAUF abgeleitet. Neue Konstante
`LOCATION_SHARPNESS_LIMIT_MIN = 60`, belegt durch den vorhandenen
Code-Kommentar `radar_service.py:110-111` („jenseits ~60 Min sinkt die
Ortsschärfe des INCA-Extrapolationsprodukts deutlich"). **Bewusst ein
EIGENER Name** neben `RADAR_ONSET_THRESHOLD_MIN = 55`: die 55 ist eine
Auslöseschwelle (feuert der Alarm?), die 60 eine Güte-Grenze (wie belastbar
ist die Ortsangabe?) — verschiedene Bezugspunkte, verschiedene Zwecke. Ein
geteilter Name ließe die nächste Änderung des einen still auf das andere
durchschlagen. Folgt exakt dem Begründungsmuster von
`_ONSET_PRECIP_WINDOW_MIN` vs. `_OVERTAKE_COMPARE_WINDOW_MIN`
(`radar_service.py:98-106`).

**E3 — Wortlaut: „unscharf", nicht „extrapoliert".** Der PO-Vorschlag
lautete „davon ab 14:40 extrapoliert - Ortsangabe unscharf". Das Wort
„extrapoliert" wäre falsch, weil ALLES extrapoliert ist — es suggeriert
eine Grenze in den Daten, die es nicht gibt. Gelieferte Langform:
`Ortsangabe ab HH:MM unscharf`. Das ist ein Datum über die Aussage, keine
Bewertung und keine Handlungsempfehlung (Ticket-Grundprinzip).

**E4 — Auslösebedingung der Güte-Zeile.** Sie erscheint, wenn MINDESTENS
EINE der im Text genannten Ereigniszeiten (Beginn ODER Ende) jenseits von
`now + LOCATION_SHARPNESS_LIMIT_MIN` liegt. Genannt wird die GRENZZEIT
selbst (`now + 60 Min`, in Ortszeit), nicht welcher Wert betroffen ist — die
Zuordnung macht der Nutzer, das ist sein Schritt. Wichtig für den Zuschnitt:
Die Zeile ist NICHT stumm im Alarm-Pfad, obwohl Alarme bei 55 Min Vorlauf
gedeckelt sind (`RADAR_ONSET_THRESHOLD_MIN`) — denn das seit S1
mitgelieferte ENDE kann weit jenseits der Grenze liegen (Beginn in 20 Min,
Ende in 150 Min).

**E5 — Keine Dopplung mit der S1-Untergrenzenform.** Ist
`event_ongoing_beyond_horizon` gesetzt, sagt der Text bereits `Regen
mindestens bis HH:MM` und nennt damit implizit dieselbe Zeit, die die
Reichweite trüge. Die Reichweiten-Angabe entfällt in diesem Fall. Sie
erscheint nur, wenn das Ereignis-Ende bekannt ist (oder es trocken bleibt)
— und liefert dort echten Gewinn: `letzter Regen gegen 14:30, Radar reicht
bis 16:00` sagt dem Nutzer, dass zwischen 14:30 und 16:00 beobachtet
trocken ist und nach 16:00 nichts bekannt.

**E6 — Kanal-Kaskade: Güte überall, Reichweite nicht in der Kurzform.**
Grundauswahl ist das Maximum, der Kanal darf nur abwählen (PO-Vorgabe).
- E-Mail (Betreff, Trip-Onset-Zeile, Mehr-Orte-Bündel/Ortsvergleich),
  Telegram rich, Briefing-Kurzfristhinweis, Kommando-Antwort: **beides** —
  `Radar reicht bis HH:MM` und `Ortsangabe ab HH:MM unscharf`.
- SMS / Premium-SMS / Telegram-Kurzstil: **nur die Güte**, als EIN Zeichen
  `?` unmittelbar hinter dem betroffenen Zeit-Token (`R2.5@15:00?`). Die
  Reichweite wird hier abgewählt.
- Begründung der Abwahl: Die Kurzform trägt bereits `R2.5@18:00 >@20:00`
  und hat ein hartes Budget von 140 GSM-7-Zeichen (`_render_sms_onset(limit
  =140)`); ein drittes Zeit-Token sprengt es bei langem Ortsnamen.
  Abgewählt wird die Angabe mit dem geringeren Gewicht: Die Güte ändert,
  WIE die ganze Aussage zu lesen ist, die Reichweite ist eine
  Zusatzinformation — und im Untergrenzen-Fall transportiert `>@` die
  Reichweite ohnehin schon (E5). Auf der Hütte am Karnischen Höhenweg ist
  Premium-SMS der einzige ankommende Kanal; deshalb darf dort gerade die
  Güte NICHT fehlen.
- **Warum `?` und ausdrücklich NICHT `~`:** `~` gehört zur
  GSM-7-Extension-Tabelle und kostet ZWEI Septets je Zeichen. Der Renderer
  faltet es deshalb vor dem Versand hart auf `-`
  (`_ASCII_EXTENSION_REPLACEMENTS`, `render.py:1497`, Issue #1796) — aus
  `R2.5@15:00~` würde auf dem Gerät `R2.5@15:00-`, und ein Bindestrich hinter
  einer Uhrzeit liest sich wie ein abgeschnittener Zeitbereich. Das wäre
  schlechter als gar keine Kennzeichnung. `?` steht dagegen im
  GSM-7-BASISzeichensatz (ein Septet, verifiziert gegen
  `tests/tdd/_gsm7_charset.py::_GSM7_BASIC`), überlebt die ASCII-Faltung
  unverändert und trägt seine Bedeutung ohne Legende. Es ist englisch-neutral
  wie die ganze Kurzform (`R` = Rain, `TH` = Thunder).
- **Kollisionsprüfung:** `?` kommt heute in keinem Token der Onset-Kurzform
  vor. Das in CLAUDE.md erwähnte Konfidenzband-Vokabular (`C+`/`C~`/`C?`) ist
  im Code **nicht** implementiert (kein Treffer in `src/`) — es taugt weder
  als Beleg noch als Kollisionsrisiko und wird hier bewusst nicht als
  Begründung herangezogen.

**E7 — Der 60-Minuten-Entscheid aus dem Ticket-Kommentar vom 2026-08-21 ist
bereits gefallen und wird nicht erneut vorgelegt.** Die S1-Spec hat ihn als
E3 entschieden und der PO hat sie freigegeben: `_NOWCAST_HORIZON_MIN` bleibt
180, keine Kappung, Kennzeichnung statt Schnitt. S3 setzt diese Wahl um.
Die S1-Spec hat dabei in E3 zu viel behauptet: Sie setzt die
Güte-Kennzeichnung mit dem Wächter `event_ongoing_beyond_horizon` gleich —
der feuert aber nur, wenn es bis zum Horizont durchregnet, und deckt den
eigentlichen PO-Fall (großer Vorlauf bei einem Ereignis, das VOR dem
Horizont endet) gerade nicht ab. Genau diese Lücke schließt S3.

## Implementation Details

**Neues Feld auf `NowcastResult`** (`radar_service.py:136-224`, additiv,
optional, Muster `event_end_minutes` aus S1):

```python
source_reach_minutes: Optional[int] = None
# Issue #2051 S3: Minuten ab jetzt bis zum Ende der Deckung des LETZTEN
# gelieferten Frames, gedeckelt am 180-Min-Horizont. NICHT dasselbe wie der
# Horizont selbst -- die Quelle kann frueher enden (Datenluecke, kuerzeres
# Produkt). `None` nur, wenn im Nowcast-Fenster ueberhaupt keine Frames
# vorliegen (throttled/data_unavailable/echte Providerluecke) -- ein
# durchgehend TROCKENES Fenster hat trotzdem eine Reichweite (bis zu 180).
```

**Ableitung in `_derive_result()`** (`radar_service.py:877ff.`): Dieselbe
`window`-Liste (Frames im `[now, horizon]`-Fenster) und dasselbe
`all_ts_sorted`, die S1 bereits für Onset/Ende nutzt. Letzter Frame in
`window` (maximaler Zeitstempel) liefert seine eigene Deckung nach exakt der
Mechanik aus `_accumulate_precip_mm`/`_derive_wet_block_end`: nächster
Nachbar aus der VOLLSTÄNDIGEN Frame-Liste (oder Horizont, wenn keiner
folgt), gedeckelt auf `_MAX_FRAME_COVERAGE`, nie über den Horizont hinaus.
`window` leer ⇒ `source_reach_minutes = None` (keine Beobachtung, nicht
„Reichweite null"). Kein neuer Helfer nötig — die Formel ist eine
Zeile analog `frame_end = min(next_ts_full, ts + _MAX_FRAME_COVERAGE,
horizon)`.

**Neue Konstante** (neben `RADAR_ONSET_THRESHOLD_MIN`,
`radar_service.py:~121`):

```python
LOCATION_SHARPNESS_LIMIT_MIN = 60
# Issue #2051 S3: eigener Name neben RADAR_ONSET_THRESHOLD_MIN (55) -- die
# 55 ist eine AUSLOESESCHWELLE (feuert der Alarm?), diese 60 eine
# GUETE-GRENZE (wie belastbar ist die Ortsangabe?). Belegt durch den
# Kommentar oben ("jenseits ~60 Min sinkt die Ortsschaerfe des
# INCA-Extrapolationsprodukts deutlich"). Downstream-Leser (render.py,
# starkregen_hint.py, project.py) referenzieren die MODUL-Variable
# (`radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN`), nie ein Import zur
# Bindezeit -- Laufzeit-Drift-Schutz wie bei RADAR_ONSET_THRESHOLD_MIN.
```

**Zwei neue geteilte Anzeigefassungen in `project.py`** (Muster
`event_end_display`, Z. 60-67, EINE Fassung für Trip- UND
Ortsvergleich-Pfad, ADR-0021):

```python
def source_reach_display(now_utc, nowcast, tz) -> tuple[str | None, int]:
    """(HH:MM, Tagesversatz) der Reichweite oder (None, 0), wenn keine
    Reichweite bekannt ist ODER `event_ongoing_beyond_horizon` gesetzt ist
    (E5 -- die Untergrenzen-Form nennt die Zeit bereits selbst)."""

def location_sharpness_display(now_utc, onset_minutes, event_end_minutes, tz) \
        -> tuple[str | None, int]:
    """(HH:MM, Tagesversatz) der Guete-Grenzzeit (now + LIMIT) oder (None, 0),
    wenn WEDER onset_minutes NOCH event_end_minutes jenseits der Grenze
    liegen (oder beide None sind). Liest die Grenze bei JEDEM Aufruf ueber
    die Modulreferenz, bindet sie NICHT beim Import."""
```

**Vier neue Felder auf `OnsetEvent`** (`model.py`, additiv, optional,
Muster `event_end_time`/`event_end_day_offset` aus S1):

```python
source_reach_time: str | None = None
source_reach_day_offset: int = 0
location_sharpness_limit_time: str | None = None
location_sharpness_limit_day_offset: int = 0
```

`location_sharpness_limit_time` ist `None`, wenn die Güte-Zeile nicht
erscheinen soll (Entscheidung ist bereits in `location_sharpness_display`
getroffen — der Renderer prüft nur noch auf `None`, keine zweite
Schwellprüfung im Renderer selbst, sonst zwei Wahrheiten wie AC-20 in S1
warnt).

**Sieben Textstellen** (Muster `_onset_end_suffix`/`_sms_onset_ende`,
`render.py:546,806`):

- Vier Langform-Stellen, die bereits `_onset_end_suffix(e)` aufrufen
  (`render.py:486` Betreff, `:601` E-Mail Trip, `:679` E-Mail
  Mehr-Orte-Bündel, `:748` Telegram rich): hängen zusätzlich
  `_onset_reach_suffix(e)` (` · Radar reicht bis HH:MM` oder leer) und
  `_onset_sharpness_suffix(e)` (` · Ortsangabe ab HH:MM unscharf" oder
  leer) an, in dieser Reihenfolge — Ende, dann Reichweite, dann Güte.
- `format_starkregen_hint()` (`starkregen_hint.py`): Signatur wächst additiv
  um `source_reach_minutes: int | None = None`,
  `location_sharpness_limit_minutes: int | None = None` (bzw. bereits
  vorformatierte HH:MM/Versatz-Paare, Muster wie die bestehenden
  `event_end_*`-Parameter) — ein Aufrufer ohne die neuen Argumente bekommt
  byte-identisch den bisherigen Text.
- `format_now_text()` (`radar_service.py:625ff.`): dieselbe additive
  Erweiterung, unmittelbar neben der S1-Ende-Weiche.
- `_render_sms_onset()`/`_sms_onset_ende()` (`render.py:806-880`): NUR die
  Güte, als neuer Helfer `_sms_onset_sharpness_marker(e) -> str`
  (`"?"` oder `""`), an `zeit = _sms_onset_time(...) + _sms_onset_ende(...)`
  angehängt — `zeit += _sms_onset_sharpness_marker(e)`. Keine
  Reichweiten-Angabe in der Kurzform (E6).

**Datenweg außerhalb der Renderer** (Muster identisch zu S1):
`to_multi_location_onset_alert_message`/Trip-Pfad in `project.py` rufen
`source_reach_display`/`location_sharpness_display` neben
`event_end_display` auf und befüllen die vier neuen `OnsetEvent`-Felder in
DERSELBEN Ortszone wie Beginn/Ende (`loc_tz`). Das
`starkregen_nowcast`-Tupel (`notification_service.py:116`,
`trip_report_scheduler.py:1893-1904`) wächst additiv um
`source_reach_minutes` und die Güte-Rohwerte (`onset_minutes`,
`event_end_minutes` reichen bereits, KEIN zusätzlicher Rohwert nötig — die
Grenzprüfung passiert im Formatierer, s. Architekturgrenze
„Scheduler liefert nur Rohdaten"). `OnsetPayload`
(`api/routers/validator.py`) bekommt die neuen `OnsetEvent`-Felder
gespiegelt (Vorwarnung analog #2046 F002/S1).

## Expected Behavior

- **Input:** `NowcastResult` mit Frames, die das Nowcast-Fenster ganz,
  teilweise oder gar nicht abdecken; optional gesetztem
  `onset_minutes`/`event_end_minutes` aus S1.
- **Output:**
  - `source_reach_minutes` ist IMMER gesetzt, wenn mindestens ein Frame im
    Fenster liegt — unabhängig davon, ob es regnet.
  - Die sechs Langform-/Briefing-/Kommando-Textstellen tragen zusätzlich
    `Radar reicht bis HH:MM`, außer bei `event_ongoing_beyond_horizon=True`
    (E5) oder wenn keine Reichweite bekannt ist.
  - Dieselben sechs Textstellen UND die Kurzform tragen zusätzlich
    `Ortsangabe ab HH:MM unscharf` bzw. das Zeichen `?`, wenn Beginn oder
    Ende jenseits der Güte-Grenze liegen.
  - Ohne Frames im Fenster (throttled/data_unavailable/echte Providerlücke)
    bleibt der Text byte-identisch zum heutigen Stand (keine der beiden
    neuen Angaben erscheint).
- **Side effects:** keine — additive Feld-Durchreichung plus
  Renderer-/Formatierungserweiterung. Keine Persistenz betroffen, keine
  Änderung an der Auslöseregel (`radar_alert_due`) oder der
  #2020-Überholungsprüfung.

## Acceptance Criteria

- **AC-1:** Given eine Frame-Zeitreihe, die das gesamte 180-Minuten-Fenster
  durchgehend abdeckt (Raster 15 Min, kein Trockenübergang, keine Lücke) /
  When `_derive_result` `source_reach_minutes` ableitet / Then entspricht
  `source_reach_minutes` dem vollen Horizont (180), gedeckelt und nicht
  darüber hinaus.
  - Test: Unit-Test gegen `_derive_result` mit konstruierten Frames im
    15-Minuten-Raster über das volle Fenster, `source_reach_minutes == 180`
    geprüft.

- **AC-2:** Given eine Frame-Zeitreihe, die nach Minute 40 abbricht (keine
  weiteren Frames bis zum Horizont), während zugleich KEIN nasser Block
  vorliegt (`onset_minutes=None`, `event_end_minutes=None`, komplett
  trocken) / When `_derive_result` beide Größen ableitet / Then ist
  `source_reach_minutes` deutlich kleiner als der Horizont (nahe Minute
  40 + `_MAX_FRAME_COVERAGE`), während `onset_minutes`/`event_end_minutes`
  unverändert `None` bleiben — die Reichweite bewegt sich unabhängig vom
  Regen-Zustand, kein gemeinsamer Wächter verschiebt beide zugleich.
  - Test: Unit-Test mit einer nach Minute 40 abbrechenden, komplett
    trockenen Frame-Zeitreihe; `source_reach_minutes` und
    `onset_minutes`/`event_end_minutes` einzeln geprüft.

- **AC-3:** Given ein `OnsetEvent` mit gesetztem `source_reach_time` und
  `event_ongoing_beyond_horizon=False` / When eine der sechs
  Langform-/Briefing-/Kommando-Textstellen gerendert wird / Then enthält
  der Text zusätzlich zur bestehenden Beginn-/Ende-Angabe
  `Radar reicht bis HH:MM`.
  - Test: Je ein Unit-Test für `_render_email_onset`,
    `format_starkregen_hint` und `format_now_text` mit konstruiertem
    Event/Ergebnis, Substring-Prüfung auf `Radar reicht bis`.

- **AC-4:** Given einen Onset-Alarm mit Beginn 75 Minuten in der Zukunft
  (`onset_minutes=75`, jenseits der 60-Minuten-Güte-Grenze) und einem Ende
  innerhalb der Grenze / When die Texte gerendert werden / Then erscheint
  in jeder der sechs Langform-/Briefing-/Kommando-Stellen zusätzlich
  `Ortsangabe ab HH:MM unscharf`, mit `HH:MM` = `now + 60 Min`.
  - Test: Unit-Test mit `onset_minutes=75`, `event_end_minutes` innerhalb
    der Grenze, gerenderter Text auf `Ortsangabe ab` und die erwartete
    Grenzzeit geprüft.

- **AC-5:** Given einen Onset-Alarm mit Beginn 20 Minuten in der Zukunft
  (diesseits der Grenze, alarmfähig unter `RADAR_ONSET_THRESHOLD_MIN`) und
  einem Ende 150 Minuten in der Zukunft (jenseits der Grenze) / When die
  Texte gerendert werden / Then erscheint die Güte-Zeile TROTZDEM, obwohl
  der Alarm-Pfad den Beginn selbst nie über 55 Minuten Vorlauf hinaus
  auslöst — genau der Fall aus B3/E4, den der Alarm-Pfad sonst stumm
  ließe.
  - Test: Unit-Test mit `onset_minutes=20`, `event_end_minutes=150`, Text
    enthält `Ortsangabe ab` mit der Grenzzeit `now + 60 Min`, nicht mit dem
    Beginn.

- **AC-6:** Given zwei Onset-Alarme, deren jeweils spätere Ereigniszeit
  (Beginn oder Ende) exakt 50 Minuten bzw. exakt 90 Minuten in der Zukunft
  liegt (beide diesseits bzw. jenseits der 60-Minuten-Grenze) / When die
  Texte gerendert werden / Then fehlt die Güte-Zeile beim
  50-Minuten-Fall vollständig UND derselbe Testaufbau erzeugt die
  Güte-Zeile, sobald ausschließlich die betroffene Zeit auf 90 Minuten
  verschoben wird (Positivkontrolle — dieselbe Konstruktion, ein
  verschobener Wert, gegensätzliches Ergebnis).
  - Test: Ein Unit-Test-Paar mit identischem Aufbau bis auf die verschobene
    Ereigniszeit; beide Ausgänge (Abwesenheit und Anwesenheit der
    Güte-Zeile) in demselben Test geprüft, nicht in getrennten Tests ohne
    gemeinsamen Bezug.

- **AC-7:** Given vier Fälle mit der betroffenen Ereigniszeit bei genau 45,
  59, 61 und 75 Minuten (zwei knapp diesseits, zwei knapp jenseits der
  60-Minuten-Grenze — die Zone ZWISCHEN den Rändern aus S1 → #2075) / When
  die Güte-Zeile für jeden Fall geprüft wird / Then fehlt sie bei 45 und 59
  Minuten und erscheint bei 61 und 75 Minuten — kein Fall an den bloßen
  Rändern (0/180 oder exakt 60) lässt die Zone dazwischen ungeprüft.
  - Test: Ein parametrisierter Unit-Test über die vier Minutenwerte, je ein
    Assert auf Anwesenheit/Abwesenheit der Güte-Zeile.

- **AC-8:** Given einen Fall mit gesetzter Güte-Zeile (Aufbau wie AC-4) /
  When der gerenderte Text auf sein Vokabular geprüft wird / Then enthält
  er das Wort „unscharf", NIEMALS das Wort „extrapoliert" — letzteres
  suggeriert fälschlich einen gemessenen Teil, den die INCA-Quelle nicht
  liefert (E2/E3).
  - Test: Unit-Test mit Substring-Prüfung `"unscharf" in text` UND
    `"extrapoliert" not in text` am selben gerenderten Text.

- **AC-9:** Given einen Onset-Alarm mit `event_ongoing_beyond_horizon=True`
  (S1-Untergrenzenform, `Regen mindestens bis HH:MM`) und einer im übrigen
  gesetzten Reichweite / When die sechs betroffenen Textstellen gerendert
  werden / Then erscheint KEINE zusätzliche `Radar reicht bis`-Angabe — die
  Untergrenzenform trägt die Reichweiten-Aussage bereits implizit (E5).
  - Test: Unit-Test mit `event_ongoing_beyond_horizon=True`, gerenderter
    Text enthält `Regen mindestens bis`, aber NICHT `Radar reicht bis`.

- **AC-10:** Given denselben Aufbau wie AC-9 (`event_ongoing_beyond_horizon
  =True`) mit zusätzlich einem Beginn jenseits der Güte-Grenze / When die
  Texte gerendert werden / Then erscheint die Güte-Zeile `Ortsangabe ab
  HH:MM unscharf` UNVERÄNDERT — die E5-Unterdrückung betrifft
  ausschließlich die Reichweiten-Angabe, nicht die Güte-Zeile; beide
  Entscheidungen bleiben unabhängig voneinander.
  - Test: Unit-Test mit beiden Wächtern kombiniert gesetzt, Text enthält
    sowohl `Regen mindestens bis` als auch `Ortsangabe ab ... unscharf`,
    aber nicht `Radar reicht bis`.

- **AC-11:** Given einen Onset-Alarm mit Güte-Fall (Beginn oder Ende
  jenseits der Grenze) / When `_render_sms_onset` (SMS, Premium-SMS,
  Telegram-Kurzstil) gerendert wird / Then trägt der Text genau EIN
  Zeichen `?` unmittelbar hinter dem Zeit-Token (z. B. `R2.5@15:00?`), und
  der resultierende Text bleibt unter 140 GSM-7-Zeichen auch im
  Extremfall (langer Ortsname, `onset_precip_mm=99.9`, kombiniertes
  Untergrenzen- und Güte-Token).
  - Test: Unit-Test gegen `_render_sms_onset` mit Güte-Fall, Regex-Prüfung
    auf genau ein `?` an der erwarteten Position; ergänzender
    Längentest mit dem Extremfall-Aufbau (Muster S1-AC-16), `len(sms) <=
    140` geprüft.

- **AC-12:** Given denselben Güte-Fall wie AC-11 / When die Kurzform
  gerendert wird / Then enthält sie KEINE Reichweiten-Angabe (kein
  zusätzliches Zeit-Token für `source_reach_time`) — die Kanal-Kaskade
  wählt in der Kurzform ausschließlich die Güte, die Reichweite bleibt
  abgewählt (E6).
  - Test: Unit-Test mit gesetztem `source_reach_time` UND Güte-Fall, die
    Anzahl der Zeit-Token in der Kurzform bleibt bei maximal zwei (Beginn,
    Ende) plus dem `?`-Zeichen — kein drittes Zeit-Token.

- **AC-13:** Given einen Onset-Alarm ohne Güte-Fall UND ohne
  Reichweiten-relevante Besonderheit (Reichweite = voller Horizont,
  beide Ereigniszeiten diesseits der Grenze) / When `_render_sms_onset`
  gerendert wird / Then ist der resultierende Text BYTE-IDENTISCH zum
  Stand vor dieser Spec (kein hängendes `?`, keine leere Anhängsel-Stelle).
  - Test: Regressionslauf der bestehenden SMS-Onset-Goldstring-Tests ohne
    inhaltliche Anpassung — keiner darf allein wegen der neuen Felder rot
    werden.

- **AC-14:** Given denselben Onset-Alarm einmal über den Trip-Pfad
  (`trip_alert.check_radar_alerts`) und einmal über den
  Ortsvergleich-Pfad (`compare_radar_alert`) gerendert (ADR-0021, geteilter
  Code) / When beide Pfade dieselben Frames erhalten / Then tragen
  Reichweiten- UND Güte-Angabe in beiden Flächen denselben Wortlaut und
  denselben Wert — keine Fläche zeigt eine der beiden Angaben, ohne dass
  die andere es auch täte.
  - Test: Paritätstest, gespiegelt zu
    `tests/tdd/test_onset_menge_kanalparitaet.py`, prüft Trip- und
    Ortsvergleich-Ausgabe auf identische Reichweiten- und Güte-Angaben.

- **AC-15:** Given einen beliebigen der sieben gerenderten Texte mit
  gesetzter Reichweite oder Güte-Zeile / When der Text auf Formulierungen
  geprüft wird, die eine Handlungsempfehlung oder eine
  Positions-/Uhrzeit-Rechnung über den Nutzer enthalten (z. B. „verlass
  dich nicht darauf", „bis dahin solltest du …") / Then enthält KEINER der
  sieben Texte eine solche Formulierung — ausschließlich ein Datum über
  die Aussage (Zeitpunkt, Wort „unscharf"/„reicht bis").
  - Test: Unit-Test über alle sieben Renderer-Ausgaben mit gesetzter
    Reichweite/Güte, Negativ-Prüfung auf eine Liste verbotener Muster.

- **AC-16:** Given ein Testfall, der `LOCATION_SHARPNESS_LIMIT_MIN` zur
  Laufzeit auf einen von 60 abweichenden Wert setzt (z. B. per Monkeypatch
  auf `radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN`) / When die
  Güte-Prüfung für eine Ereigniszeit knapp über dem NEUEN, nicht dem alten
  Wert läuft / Then greift die Güte-Zeile nach dem NEUEN Wert — die
  Erwartung im Test wird aus DERSELBEN Modulreferenz gelesen, nicht als
  fest getippte Zahl im Test dupliziert, damit ein hart getippter
  Erwartungswert im Produktivcode auffliegen würde, sobald der Test die
  Referenz statt einer eigenen Kopie prüft.
  - Test: Unit-Test, der `radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN`
    monkeypatcht, die Erwartung aus derselben Modulvariable ableitet
    (`limit = radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN`, nicht
    `limit = 60`) und prüft, dass die Güte-Zeile exakt an dieser Grenze
    kippt.

## Known Limitations

- **Die Güte-Grenze ist eine gesetzte Zahl, kein gemessenes
  Quellen-Merkmal** (E2). 60 Minuten ist der im Code dokumentierte,
  fachlich begründete Schätzwert für den Punkt, an dem die
  INCA-Ortsschärfe „deutlich" sinkt — keine kalibrierte, laufend
  nachgeführte Messgröße. Eine künftige Quelle mit Pro-Frame-Herkunft
  (Analyse vs. Extrapolation) könnte diese Schwelle ablösen; bis dahin
  bleibt sie eine Heuristik.
- **Reichweiten-Präzision hängt am Quellenraster.** Wie bei
  `event_end_minutes` (S1) bestimmt die Kadenz der jeweiligen Quelle
  (5-15 Min) die Präzision der Reichweiten-Angabe; bei gröberem Raster
  kann die tatsächliche Reichweite um bis zu `_MAX_FRAME_COVERAGE`
  (15 Min) von der Anzeige abweichen.
- **S2 (räumliche Ausdehnung), S4 (`/strecke`-Kommando)** aus Issue #2051
  bleiben offen — diese Spec deckt ausschließlich S3.
- **Die Güte-Zeile nennt keine betroffene Größe.** Sie sagt „ab HH:MM
  unscharf", nicht ob Beginn, Ende oder beide betroffen sind (E4,
  bewusste Entscheidung — Bevormundungs-Grenze). Ein Nutzer mit zwei
  Ereigniszeiten muss selbst vergleichen, welche jenseits der genannten
  Grenzzeit liegt.

## Nicht-Ziele

- **Keine räumliche Ausdehnung** (S2) und **kein `/strecke`-Kommando** (S4)
  — beide bleiben eigenständige Scheiben von #2051.
- **Keine Kappung von `_NOWCAST_HORIZON_MIN`** auf 60 — nähme #1945 und
  S1/E3 zurück.
- **Keine Änderung an `RADAR_ONSET_THRESHOLD_MIN = 55`** oder der
  #2020-Überholungsprüfung.
- **Kein neuer Quellenabruf** — Reichweite und Güte werden ausschließlich
  aus den bereits abgerufenen `frames` bzw. aus den in S1 abgeleiteten
  `onset_minutes`/`event_end_minutes` gebildet.
- **Keine Handlungsempfehlung, keine Rechnung über den Nutzer**
  (Ankunftszeiten, Begegnungspunkte, „verlass dich nicht darauf").
- **Keine Änderung an der Trip-Konfiguration des PO.**
- **Keine Berührung von `radar_service.py` Zeile ~325 (`coverage_end` in
  `_derive_wet_block_end`)** — dort arbeitet parallel Issue #2075 an
  einem eigenen Fund. Die Reichweiten-Ableitung dieser Spec liegt in
  `_derive_result` und liest dieselbe Mechanik, ohne die dortige Zeile
  selbst zu ändern.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Feld-Durchreichung entlang derselben, bereits in
  S1 etablierten Wirkkette (`NowcastResult` → `OnsetEvent` → sieben
  Textstellen) plus zwei reine Anzeigefassungs-Helfer, die dem Muster
  `event_end_display` folgen. Berührt keine der vier Entscheidungsflächen,
  die ein neues ADR verlangen würden: ADR-0011 (ein Backend-Renderer)
  bleibt gültig — alle Textstellen liegen weiter in `render.py`;
  ADR-0021 (geteilter Code Trip/Compare) wird angewendet, nicht verändert
  (AC-14); ADR-0052 (Mail-Bauform) bleibt unangetastet, Reichweite und
  Güte fügen sich als weitere Datenzeilen-Anhängsel ein. Kein neuer Kanal,
  kein neuer Provider, keine Persistenz-Änderung, keine Änderung an der
  Auslöseregel.

## Test-Plan

**Bestehende Tests, die den heutigen Text ohne Reichweite/Güte
festnageln — laufen unverändert grün oder werden additiv fortgeschrieben
(AC-13):**

- Alle in S1s Test-Plan gelisteten Bestandstests
  (`tests/tdd/test_alert_sms_onset_zeitpunkt.py`,
  `test_952_onset_alert_fidelity.py`,
  `test_multi_location_onset_alert.py`,
  `test_onset_menge_kanalparitaet.py` u. a.) — Regressionslauf ohne
  inhaltliche Anpassung an den Fixtures.
- Die S1-eigenen Testdateien
  (`tests/tdd/test_nowcast_blockende_*.py`,
  `tests/tdd/test_onset_ende_*.py`) — dürfen durch die neuen additiven
  Felder nicht rot werden.

**Neue Testdateien, benannt nach Verhalten (nicht nach Issue-Nummer):**

- `tests/tdd/test_nowcast_source_reach_ableitung.py` — AC-1/AC-2
  (Reichweite bei vollständiger Deckung, Reichweite bei Datenlücke
  unabhängig vom Regen-Zustand).
- `tests/tdd/test_nowcast_source_reach_textstellen.py` — AC-3/AC-9/AC-10
  (Reichweiten-Text in den sechs Stellen, E5-Unterdrückung, Unabhängigkeit
  von der Güte-Zeile).
- `tests/tdd/test_nowcast_ortsschaerfe_schwelle.py` — AC-4/AC-5/AC-6/AC-7
  (Auslösebedingung, Alarm-Pfad-Fall, Positivkontrolle, Randzone
  61-75/45-59).
- `tests/tdd/test_nowcast_ortsschaerfe_wortlaut.py` — AC-8 (Wortlaut
  „unscharf", nicht „extrapoliert").
- `tests/tdd/test_onset_reichweite_guete_sms.py` — AC-11/AC-12/AC-13
  (SMS-Marker, Abwahl der Reichweite, Byte-Identität ohne Güte-Fall).
- `tests/tdd/test_onset_reichweite_guete_kanalparitaet.py` — AC-14
  (Trip ↔ Ortsvergleich).
- `tests/tdd/test_onset_reichweite_guete_keine_bevormundung.py` — AC-15.
- `tests/tdd/test_ortsschaerfe_grenze_laufzeitbindung.py` — AC-16
  (Modulreferenz statt Import-Bindung).

## Changelog

- 2026-08-22: Initial spec created (#2051 Scheibe S3, Reichweite der Quelle
  und Güte-Kennzeichnung).
