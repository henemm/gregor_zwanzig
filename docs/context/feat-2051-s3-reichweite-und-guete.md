# Context: feat-2051-s3-reichweite-und-guete

**Issue:** #2051, Scheibe S3 — „Reichweite der Quelle als Datum" + Güte-Kennzeichnung
**Track:** Standard · **Basis:** `origin/main` @ `2939965b`

## Request Summary

Der Radar-Nowcast soll sichtbar machen, **wie weit seine Aussage reicht** („Radar
reicht bis HH:MM") und **wie belastbar sie ist** („ab HH:MM extrapoliert —
Ortsangabe unscharf"). Beides als Datum über das Wetter, nicht als Bewertung und
nicht als Handlungsempfehlung.

Vorgänger: S1 (Dauer/Ende) ist seit 2026-08-22 08:46 UTC live (`c684d053`).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/radar_service.py:69-72` | `_NOWCAST_HORIZON_MIN = 180` / öffentlicher Alias `NOWCAST_HORIZON_MIN` — der Prüfhorizont |
| `src/services/radar_service.py:110-121` | `RADAR_ONSET_THRESHOLD_MIN = 55`; **Kommentar belegt die Güte-Schwelle**: „jenseits ~60 Min sinkt die Ortsschärfe des INCA-Extrapolationsprodukts deutlich" |
| `src/services/radar_service.py:95` | `_MAX_FRAME_COVERAGE = timedelta(minutes=15)` — Deckung eines Frames, gröbstes Produktivraster |
| `src/services/radar_service.py:136-224` | `NowcastResult` — Rückgabestruktur; `source` ist **ein** String pro Abruf, keine Pro-Frame-Herkunft |
| `src/services/radar_service.py:203-224` | S1-Felder `event_end_minutes`, `event_ongoing_beyond_horizon` |
| `src/services/radar_service.py:625/627` | Textstelle: Nowcast-Satz |
| `src/output/renderers/alert/render.py:298` | Textstelle: laufendes Ereignis (#2050 S2b) |
| `src/output/renderers/alert/render.py:554-582` | Textstelle: Langform-Ende-Suffix (E-Mail/Telegram rich) |
| `src/output/renderers/alert/render.py:800-870` | Textstelle: SMS-Kurzform, `_sms_onset_ende()`, `_render_sms_onset(limit=140)` |
| `src/output/renderers/email/starkregen_hint.py:25-60` | Textstelle: E-Mail-Kurzfristhinweis |
| `src/output/renderers/alert/model.py:128-129` | Ende-Felder am Event-Modell |
| `src/services/trip_report_scheduler.py:1826-1838` | **Der ungedeckelte Pfad** — „kennt keinen Onset-Grenzwert und akzeptiert jeden Treffer im vollen 180-Minuten-Fenster" |
| `src/services/trip_alert.py:1387`, `src/services/compare_radar_alert.py:358` | Alarm-Pfade, gedeckelt über `radar_alert_due(result, RADAR_ONSET_THRESHOLD_MIN)` |

## Existing Specs

- `docs/specs/modules/feat_2051_s1_dauer_und_ende.md` — Vorgänger-Scheibe, v1.1
- `docs/specs/modules/fix_1945_nowcast_horizon.md` — Anhebung 60 → 180
- `docs/specs/modules/fix_2009_nowcast_vorlauf.md` — Herkunft der 55-Min-Schwelle
- `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` — SMS-Token-Format

## Existing Patterns

- **Additive Feld-Durchreichung:** S1 hat `event_end_minutes` +
  `event_ongoing_beyond_horizon` an `NowcastResult` ergänzt und durch alle sieben
  Textstellen gereicht. S3 folgt derselben Bahn.
- **Zwei Formen, entschieden an einem Wächter-Boolean** (S1: Normalform vs.
  Untergrenzen-Form) — vorhandenes Muster für „Aussage mit Vorbehalt".
- **Kanal-Kaskade:** Grundauswahl ist das Maximum, der Kanal darf nur abwählen.
  SMS/Premium-SMS haben ein hartes Budget (`limit=140`, GSM-7), die Kurzform ist
  englisch (`R` = Rain, `TH` = Thunder).
- **Eine Zahl, ein Name:** wiederkehrendes Muster im Radar-Service — jede Schwelle
  bekommt einen eigenen benannten Wert mit Begründung, warum sie *nicht* mit einem
  Nachbarn geteilt wird.

## Dependencies

- **Upstream:** `RadarNowcastService.get_nowcast()` (`radar_service.py:441`),
  Provider GeoSphere-INCA / AROME-FR / ICON-D2 / ARPAE / `minutely_15`
- **Downstream:** 6 Aufrufstellen von `get_nowcast()` — `trip_alert.py:1373`,
  `compare_radar_alert.py:348`, `trip_report_scheduler.py:1876`,
  `trip_command_processor.py:1559`, `thunder_enrichment.py:255`

## Analyse-Befunde (Phase 2, kombiniert)

### B1 — Der PO-Entscheid vom 21.08. ist bereits gefallen: Option (b)

Der Ticket-Kommentar stellte drei Optionen zur Wahl (a Horizont auf 60 kappen /
b voller Horizont mit Güte-Kennzeichnung / c Kappung je Alarmart). Die S1-Spec
hat ihn als **E3** entschieden und der PO hat sie freigegeben:
`_NOWCAST_HORIZON_MIN` bleibt 180, keine Kappung, Kennzeichnung statt Schnitt.
**Nicht erneut vorlegen.**

### B2 — Was E3 offenlässt

E3 setzt gleich: „Die vom PO erwogene Güte-Kennzeichnung **ist** der
`event_ongoing_beyond_horizon`-Wächter." Das trägt nur einen Teilfall. Der
Wächter feuert ausschließlich, wenn es **bis zum Horizont durchregnet**. Er sagt
nichts über:

- die Reichweite als solche, wenn es *nicht* bis zum Ende regnet (Normalfall)
- die Unschärfe bei **großem Vorlauf** — genau der Fall aus dem PO-Kommentar
  („bei 90 Minuten Vorlauf liegt das Ereignis am Rand der Radar-Reichweite")

Beides ist der Gegenstand von S3.

### B3 — Der Realfall entsteht im Briefing-Pfad, nicht im Alarm-Pfad

`RADAR_ONSET_THRESHOLD_MIN = 55` deckelt Trip- und Ortsvergleichs-Alarme hart:
eine Alarm-Aussage „in 90 Minuten" kann dort gar nicht entstehen. Der
90-Min-Fall des PO stammt aus `trip_report_scheduler.py:1829-1831` (Briefing-
Kurzfristhinweis) bzw. der Inbound-Kommando-Antwort — die beiden Pfade **ohne**
Vorlauf-Deckel. Das ist die Fläche, auf der die Güte-Kennzeichnung überhaupt
Wirkung entfaltet; im Alarm-Pfad wäre sie fast immer stumm.

### B4 — Güte hat keine Datengrundlage aus der Quelle

`NowcastResult.source` ist **ein** String für den ganzen Abruf
(`"radar" | "INCA" | "AROME-FR" | "minutely_15"`). Es gibt **keine** Angabe je
Frame, ob er Analyse (gemessen) oder Extrapolation (gerechnet) ist. INCA liefert
im abgerufenen Fenster durchgehend Extrapolation. Eine Kennzeichnung „ab HH:MM
extrapoliert" kann also **nicht** aus einem Quellen-Merkmal abgeleitet werden.

Verfügbar ist stattdessen der **Vorlauf** — und dafür trägt der Code bereits eine
belegte Schwelle: `radar_service.py:110-111` nennt ~60 Min als Punkt, ab dem die
Ortsschärfe deutlich sinkt. Das ist dieselbe Zahl, die `RADAR_ONSET_THRESHOLD_MIN
= 55` begründet. **Konsequenz für die Spec:** Die Güte-Grenze ist eine
Zeitschwelle, kein Quellen-Datum — und das muss der Wortlaut ehrlich abbilden
(„ab HH:MM unscharf" statt „ab HH:MM extrapoliert", denn extrapoliert ist alles).

### B5 — Reichweite ist ein echtes, immer verfügbares Datum

Der letzte verfügbare Frame-Zeitpunkt steht in `frames` und ist unabhängig davon
verfügbar, ob es regnet. Er ist heute nur indirekt und nur im Regenfall sichtbar
(`event_ongoing_beyond_horizon`). Als eigenes Feld nach außen gegeben, deckt er
S3 Punkt 1 ohne zusätzlichen Quellenabruf.

**Achtung Bezugspunkte:** „Reichweite der Quelle" (letzter Frame + dessen
Deckung) und „Prüfhorizont" (`now + 180 Min`) sind **zwei verschiedene Größen**.
Die Quelle kann früher enden als der Horizont (Datenlücke, kürzeres Produkt) —
dann ist die Reichweite die kleinere Zahl. Ein Feld, das beides vermischt, wäre
ein blinder Wächter.

## Risks & Considerations

- **R1 — Kollision mit #2075.** Die Parallelsitzung `khw-milestone-check` fixt
  `radar_service.py:325` (`coverage_end` ohne `next_ts`) — dieselbe
  Deckungsrechnung, aus der die Reichweite abzuleiten ist. Vor dem Liefern
  rebasen; `git diff origin/main --diff-filter=D` nach dem Rebase prüfen.
- **R2 — SMS-Budget.** Die Kurzform trägt bereits `R2.5@18:00 >@20:00`. Ein
  drittes Zeit-Token sprengt bei ungünstiger Ortslänge die 140 GSM-7-Zeichen.
  Die Kanal-Kaskade erlaubt Abwahl — S3 muss begründen, was SMS/Premium-SMS
  bekommt und was nicht. Auf der Hütte ist Premium-SMS der einzige Kanal.
- **R3 — Doppelung zur S1-Untergrenzenform.** `Regen mindestens bis 16:00` sagt
  bereits implizit „die Quelle endet um 16:00". Ein zusätzliches
  „Radar reicht bis 16:00" daneben wäre Dopplung. Die Spec muss regeln, wann
  welche Form erscheint — nicht beide gleichzeitig.
- **R4 — Bevormundungs-Grenze.** „Ortsangabe unscharf" ist ein Datum über die
  Aussage. „Verlass dich nicht darauf" wäre eine Bewertung. Der Wortlaut
  entscheidet, auf welcher Seite die Zeile landet (Ticket-Grundprinzip, PO
  zweifach geschärft).
- **R5 — Zwei ACs an den Rändern lassen die Mitte ungeprüft** (Lehre aus S1 →
  #2075). Der Test-Plan braucht explizit den Fall *zwischen* den Rändern.

## Test-Landkarte

Bewachende Testdateien sind über die S1-Formulierungen auffindbar
(`grep -rn "letzter Regen\|mindestens bis" tests/`) — in Phase 4 zu erheben.
