# Context: #1948 Scheibe S4 — Zweig-c-Zielbild (Nowcast/Onset-SMS)

**Workflow:** `fix-1948-s4-nowcast-sms` · **Issue:** #1948 · **Track:** Full Process (Score 4)
**Erstellt:** 2026-08-19

## Request Summary

Die Nowcast-/Onset-Kurznachricht (Zweig c) soll auf das einheitliche Alarm-Format nachziehen:
Kopf über die gemeinsame Ortsauflösung statt selbstgebautem `km{a}-{b}:`, und Token von
`TH!{onset_minutes}` (Countdown) auf `TH@{onset_time}` (konkrete Uhrzeit). PO-Zielbild aus
Konzept v3 Abschnitt 1: **`Ziel: TH@15:40`** — heute lautet dieselbe Nachricht `km8-8: TH!8`.

## Ist-Zustand (belegt)

`src/output/renderers/alert/render.py:422-438` (`_render_sms_onset`) nutzt **weder** `_km_str`
**noch** `_km_str_onset` **noch** `format_alert_location` — der Kopf ist hand-verdrahtet:

```python
token = f"TH!{e.onset_minutes}" if e.is_convective else f"R!{e.onset_minutes}"
a, b = int(round(e.km_from)), int(round(e.km_to))
if getattr(e, "location_label", None):
    body = f"{trip} km{a}-{b}: {token}"     # Compare, >1 Ort
else:
    body = f"km{a}-{b}: {token}"            # Trip UND Compare mit genau 1 Ort
```

Schreibweise weicht vom gemeinsamen Kopf ab: `km8-8` (kein Leerzeichen, ASCII-Bindestrich) vs.
`km 8–8` (Leerzeichen, En-Dash) aus `format_alert_location` (`segments.py:101`).

Vorbild für den Zielzustand ist der Trip-Δ-Kopf in `render_sms` (`render.py:910-916`):
`head = f"{_ascii_alert_location(_km_str(msg))}: "`.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py:422` | `_render_sms_onset` — **die** zu ändernde Funktion |
| `src/output/renderers/alert/render.py:129-170` | `_location_of`, `_km_str`, `_km_str_onset` — die Kopf-Bausteine |
| `src/output/renderers/alert/segments.py:91` | `format_alert_location` — Auflösungsreihenfolge label → Segment → km |
| `src/output/renderers/alert/model.py:36-51` | `OnsetEvent` — `onset_time` (`str`, nie `None`), `onset_minutes`, `segment_id`, `location_label` |
| `src/output/renderers/alert/project.py:319-398` | `to_multi_location_onset_alert_message` — setzt `location_label` nur bei >1 Ort |
| `src/services/notification_service.py:1373` | einziger Produktiv-Aufruf `render_sms`, Ergebnis geht an SMS **und** Premium-SMS |
| `src/services/validator_render_service.py:217-259` | `_render_nowcast_replay` — S2-Einspeiseweg, nutzt echtes `_derive_result` |

## Dependencies

- **Upstream:** `OnsetEvent.onset_time` wird lokal-ortszeitlich als `"HH:MM"` befüllt
  (`trip_alert.py:1274`, `project.py:382`), Typ `str`, kein `None`-Fall im Produktivcode.
- **Downstream:** ein einziges Rendering bedient **beide** Kurzkanäle — `limit=140` gilt für
  SMS und Premium-SMS gemeinsam (`notification_service.py:1543/1558`), kein eigener Grenzwert
  für Premium-SMS. Kürzung ist ein harter Endschnitt `body[:limit]`, keine Token-Priorisierung.

## Existing Specs

- `docs/specs/modules/fix_1948_s3_sms_sofortfix.md` — direkte Vorlage (Zweig a). Dessen **AC-7**
  sichert ausdrücklich zu, dass `_render_sms_onset` byte-identisch bleibt; genau diese Zusicherung
  läuft mit S4 planmäßig aus.
- `docs/specs/modules/alarm_testeinspeisung.md` — S2-Einspeiseweg (`nowcast_frames`-Payload)
- `docs/specs/modules/alarm_eingangsprotokoll.md` — S1-Mitschnitt

## 🔴 Zielkonflikt — muss die Spec entscheiden

`tests/tdd/test_alert_location_vocabulary.py:573-585`
(`test_kurznachricht_des_nowcasts_nennt_keinen_ort`) fordert heute wörtlich das **Gegenteil** des
Zielbilds: `"Segment" not in sms`, `"Ziel" not in sms`, `"🏁" not in sms`, und `re.search(r"km\d", sms)`
**muss** matchen. Docstring: *„der Betreff wechselt auf '🏁 Ziel', die Kurznachricht bleibt bei 'km8-8'."*

Das PO-Zielbild `Ziel: TH@15:40` ist genau die Segment-Sprache, die dieser Test verbietet. Sobald
`_render_sms_onset` über `format_alert_location` geht und das Event eine `segment_id` trägt, löst
der Kopf zu `🏁 Ziel` auf statt zu `km 8–8`. Entweder wird der Test bewusst abgelöst (Präzedenz:
S3 hat #1744 AC-5 für Zweig a genauso abgelöst) — oder das Zielbild ist so nicht umsetzbar.

## Offene Entscheidungsfragen für die Spec

> **Stand Phase 2: alle beantwortet** — siehe PO-Entscheide-Tabelle im Analysis-Teil unten.
> Der Zielkonflikt oben ist entschieden: der Test wird dokumentiert abgelöst.

1. **Zieht der Regen-Zweig mit?** Konzept nennt nur `TH@15:40`. Ob `R!{min}` ebenfalls auf
   `R@{onset_time}` wechselt, ist nirgends entschieden. Bestimmt, wie viele Tests rot werden.
2. **Compare-Onset mit genau EINEM Ort nennt den Ort heute gar nicht.** `location_label` bleibt
   per Invariante `None` (`project.py:378`), `km_from=km_to=0.0` → SMS lautet `km0-0: R!25`; der
   Ortsname steht ungenutzt in `msg.trip_short`. Heilt S4 das mit (`format_alert_location` Stufe 1),
   oder bleibt der Ortsvergleich byte-identisch?
3. **Doppelpunkt-Form:** Leitsatz sagt „ein Gewitter heißt in allen drei Zweigen `TH:`", das
   Zielbild für Zweig c schreibt `TH@15:40` ohne Doppelpunkt. Bei c folgt kein Stufenwert.

## Risks & Considerations

- **7 bestehende Tests werden rot** und müssen fortgeschrieben werden (nicht gelöscht):
  `test_multi_location_onset_alert.py:262` (Goldstring `km5-18: R!12`) ·
  `test_issue_919_radar_alert_canonical.py:143-165` (`R!12`/`TH!8`) ·
  `test_952_onset_alert_fidelity.py:336` (Regex `km(\d+)-(\d+)` bricht am Leerzeichen) ·
  `test_alert_sms_segment_head.py:194-227` (AC-12, **zugleich Pendant-Wächter**) ·
  `test_alert_sms_location_positions.py:934/960` (2× Versandpfad, Marker `live`) ·
  `test_alert_preview_nowcast_replay.py:105` (Regex `R!(\d+)` + Minuten-Semantik) ·
  `test_alert_location_vocabulary.py:573` (der Zielkonflikt oben).
- **Pendant-Wächter erhalten:** `test_ac12_...` vergleicht Trip- und Compare-Ergebnis
  gegeneinander. Er darf auf das neue Format umgestellt werden, aber die Differenzlogik
  (Compare behält den Namen, Trip nicht) muss als Vergleich bestehen bleiben.
- **Leitplanke #1599 ist präventiv, nicht scharf** (Korrektur zur Intake-Annahme): Der
  Alarm-Renderer importiert `app.day_window` **nicht**; `display_end_time()` liegt außerhalb der
  Aufrufkette, und `onset_time` entsteht als reine Uhrzeit-Arithmetik in `radar_service.py:274`.
  Die Regel bleibt trotzdem als Nicht-Berührungs-Nachweis in der Spec stehen.
- **AC-4-Bedenken entschärft** (Korrektur zur Intake-Annahme): Der Kommentar an `_km_str_onset`
  nennt nur „AC-4", nicht #1170/#1467, und betrifft den **Telegram**-Pfad. `_km_str_onset` nimmt
  `location_label` gar nicht entgegen — eine Wiederverwendung im SMS-Kopf bricht die Zusicherung
  nicht. Das reale Risiko liegt bei `segment_id` (Zielkonflikt oben).
- **AC-10 (#1935/#1779) hat keinen eigenen Test** — nur indirekt über die Regressionstests
  mitgeprüft. Lückenbefund, gehört nach #1196/#1199, nicht in diese Scheibe.

## Verifikation nach Konzept-Leitprinzip — Grenze belegt

Echte S1-Zweig-c-Mitschnitte existieren auf dem Server (nicht im Repo, `data/` ist ungetrackt):

| Ablage | Aufzeichnungen | mit Regen ≥0,1 mm/h | mit konvektivem Frame | Maximum |
|---|---|---|---|---|
| Prod `/var/lib/gregor/debug/alert_input/nowcast/` | 50 (INCA, 46.5641/13.4792 = KHW) | 14 | **0** | 2,8 mm/h |
| Staging `/var/lib/gregor-staging/…` | 6 (AROME-FR, INCA, radar) | 3 | **0** | 9,2 mm/h |

**Folge:** Der Regen-Pfad ist mit echten Meldungen verifizierbar. Der Gewitter-Pfad — also genau
das Zielbild `TH@15:40` — ist es **nicht**, weil in keiner der 56 Aufzeichnungen ein konvektiver
Frame steckt. Für Gewitter bleibt eine abgeleitete Variante (echte Frames, `is_convective` gesetzt)
plus Unit-Test. Das gehört als Grenze in die Spec, statt später als „mit echten Daten verifiziert"
verbucht zu werden.

Einspeiseweg (S2), erprobt und deterministisch im Kern-Testlauf:
`POST /api/trips/{trip_id}/alert-preview?user_id=…` mit `{"nowcast_frames": {source, frames[], km_from, km_to}}`
→ Antwort trägt `onset_detected` und das gerenderte `sms`. Der Replay nutzt dasselbe
`_derive_result` wie der Live-Pfad, keinen Test-Sonderweg.

---

# Analysis (Phase 2)

### Type
Feature (Format-Konsolidierung innerhalb Epic #1948)

### PO-Entscheide — verbindlich

| # | Frage | Entscheid |
|---|---|---|
| 1 | Zieht der Regen-Zweig mit? | **Ja** — `R!{min}` → `R@{onset_time}`, gleiches Muster wie Gewitter |
| 2 | Segment-Sprache im Kopf? | **Ja** — Zielbild `Ziel: TH@15:40`; `test_kurznachricht_des_nowcasts_nennt_keinen_ort` wird dokumentiert abgelöst |
| 3 | Ortsvergleich mitheilen? | **Ja**, beide Fälle |
| 3a | Ein-Ort-Compare (Sonderfall nötig) | **Ja, in S4 mitbauen** — trotz Empfehlung „eigenes Ticket"; PO wählte bewusst |
| 3b | `+N`-Zähler bei mehreren Orten | **Nein** — die Nachricht wertet nur den führenden Ort aus; ein Zähler verspräche Vollständigkeit, die sie nicht einlöst |

### Technical Approach

Neuer Funktionskörper (`render.py:422`), Muster übernommen vom Trip-Δ-Kopf (`render.py:916`):

```python
token = f"TH@{e.onset_time}" if e.is_convective else f"R@{e.onset_time}"
head = _ascii_alert_location(_location_of((e,), _onset_label(msg, e)))
body = f"{head}: {token}"
```

Begründung der Bausteinwahl:
- **Nicht** `_km_str_onset(e)` — die unterdrückt `location_label` absichtlich und wird von
  Telegram/Betreff mitbenutzt (`render.py:416`, `render.py:284`); eine Änderung dort würde
  ungefragt zwei weitere Kanäle verändern.
- **Nicht** `_km_str(msg)` — liest `msg.location_label`, das für Onset-Nachrichten von **keinem**
  Konstruktor je gesetzt wird und damit strukturell immer `None` ist.
- Ein **lokaler** `_location_of((e,), <label>)`-Aufruf lässt die geteilten Bausteine unangetastet.

### 🔴 Der Ein-Ort-Compare-Sonderfall (PO-Entscheid 3a)

Belegte Ursache: `to_multi_location_onset_alert_message` setzt `location_label` nur bei mehr als
einem Ort (`project.py:387`, `location_label=location_name if multi else None`); die Invariante ist
explizit getestet (`test_multi_location_onset_alert.py:351`). Bei genau einem Ort steht der
Ortsname ausschließlich in `msg.trip_short` (`project.py:392-393`), und `km_from=km_to=0.0`.

Die nötige Fallunterscheidung hängt am Marker `msg.source == "compare-radar"` (`project.py:397`) —
heute ein Freitext ohne Vertrag. **Härtung statt Hinnahme:** Der Marker wird zu einer benannten
Konstante (z.B. `COMPARE_RADAR_SOURCE`) angehoben und an Setz- wie Lesestelle darüber referenziert.
Damit bricht ein Umbenennen sichtbar, statt die Ortsanzeige still auf `km 0–0` zurückfallen zu
lassen. Ein Wächter-Test muss genau diese stille Rückfall-Situation abdecken.

### Gemessen, nicht vermutet

**Zeichensatz — kein UCS-2-Risiko.** `_ascii_alert_location` (`render.py:989-992`) ruft
`_strip_pictographs` (entfernt Unicode-Kategorie `So`) **vor** `fold_ascii`:

```
format_alert_location(None, ['Ziel'], 8, 8)  →  '🏁 Ziel'
_ascii(...)                                  →  ':checkered_flag: Ziel'   ← falsch, nicht nutzen
_ascii_alert_location(...)                   →  'Ziel'                    ← richtig
```

Der Unterschied ist der Grund, warum `_ascii_alert_location` als eigene Funktion existiert. Ein
Charset-Problem entstünde nur durch Verwechslung der beiden — das gehört als Mutations-Kandidat
in die Adversary-Runde.

**Längen-Budget — unkritisch** (Limit 140, harter Endschnitt `body[:limit]`):

| Szenario | alt | neu | Δ |
|---|---|---|---|
| Trip mit Segmentnamen | `km8-8: TH!8` (11) | `Ziel: TH@15:40` (14) | +3 |
| Trip, km-Rückfall | `km5-18: R!12` (12) | `km 5-18: R@14:35` (16) | +4 |
| Compare, kurzer Ortsname | `Vergleich km5-18: R!12` (22) | `Vergleich: R@14:08` (18) | **−4** |
| Compare, 35-Zeichen-Ortsname | (Name auf 16 gekappt, 27) | **ungekappt** (45) | +18 |

Geerbtes Restrisiko: `format_alert_location` Stufe 1 kappt den Ortsnamen **nicht** — der Trip-Δ-Pfad
hat dieselbe Lücke (`render.py:916`). Wird nicht in S4 gelöst, aber in der Spec benannt.

### Scope Assessment

- Dateien: 1 Produktivdatei (+1 für die Marker-Konstante) + 8 Testdateien
- Geschätzte LoC: ~30–40 Produktiv, ~90–130 Test → **~120–170**, unter dem Limit 250
- Risk Level: **MEDIUM** — Kernlogik eines kritischen Nutzerpfads, aber eng umgrenzte Funktion

Zwei Posten mit echter Schätzunsicherheit: `test_alert_sms_location_positions.py` und
`test_alert_preview_nowcast_replay.py` prüfen künftig einen **wanduhr-abhängigen** Wert
(`onset_time` statt Countdown-Minuten) und brauchen Zeitfenster-Toleranz statt Goldstring.

### Reihenfolge

1. TDD-RED gebündelt in **einem** neuen Testmodul (neue Zusicherung: `TH@`/`R@`-Form,
   Segment-Kopf, GSM-7-Reinheit, Ein-Ort-Compare nennt den Ort)
2. `_render_sms_onset` + Marker-Konstante implementieren
3. Bestandstests fortschreiben, aufsteigend nach Komplexität: statische Goldstrings zuerst
   (`test_issue_919…`, `test_multi_location_onset_alert`, `test_952…`), dann der Pendant-Wächter
   `test_alert_sms_segment_head.py` AC-12 (**Differenzlogik erhalten, nicht nur Strings tauschen**),
   dann die beiden zeitabhängigen, zuletzt die bewusste Ablösung in
   `test_alert_location_vocabulary.py:573` mit Begründung im Docstring.

### Open Questions
- keine offen — alle fünf Entscheidungsfragen sind PO-beantwortet (Tabelle oben).
