---
entity_id: feat_2051_s2b_ausdehnung_kanaele
type: feature
created: 2026-08-23
updated: 2026-08-23
status: draft
version: "1.0"
tags: [alarm, nowcast, radar, ausdehnung, zone, sms, kanal-kaskade]
---

# Ausdehnung auf die übrigen Kanäle — #2051 Scheibe S2b

## Approval

- [ ] Approved

## Purpose

S2a hat die räumliche Ausdehnung eines Regenereignisses als km-Zonen
eingeführt (`rain_extent.derive_rain_zones()`, `OnsetEvent.rain_zones`) und
**eine** von sieben Textstellen bespielt (E-Mail-Trip-Langform). Der
Baustein `_onset_extent_suffix()` existiert bereits — S2b hängt ihn an die
übrigen Langform-Stellen und bringt die Ausdehnung zusätzlich in die
Kurzform (SMS/Premium-SMS/Telegram-Kurzstil), wo sie bisher komplett fehlt.
Ohne S2b bleibt die Ausdehnung auf einer einzigen Textstelle stehen — genau
die Lücke, die die Hütte am Karnischen Höhenweg trifft: dort kommt nur die
Premium-SMS an, und die trägt heute keine Ausdehnungsangabe.

Grundprinzip aus dem Ticket (unverändert bindend): **nur Daten über das
Wetter, keine Rechnung über den Nutzer.**

## Source

- **File:** `src/output/renderers/alert/render.py` (Textstellen-Verkettung,
  neuer Kurzform-Helfer), `src/services/validator_render_service.py`
  (Prüffläche), `api/routers/validator.py` (`OnsetPayload`)
- **Identifier:** `_onset_extent_suffix()` (bereits vorhanden,
  `render.py:614-639`), `_render_sms_onset()` (`render.py:927-996`), neuer
  Helfer `_sms_onset_extent_suffix()` (neu, `render.py`), `RainZone`
  (`src/services/rain_extent.py:26-43`, unverändert), `render_alert_preview()`
  (`validator_render_service.py:93`)

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Core
> (`src/output/renderers/alert/`, `src/services/`, `api/routers/`) — kein
> Go-API-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~70-100 produktiv (drei Ein-Zeilen-Anhängungen, ein neuer
  Kurzform-Helfer, Prüffläche + Payload-Erweiterung), ~180-220 Tests — in
  Summe **über dem 250-LoC-Workflow-Limit**,
  `workflow.py set-field loc_limit_override 500` ist vor `/40-tdd-red`
  einzuplanen (Muster wie S2a/S3).
- **Files:** `render.py`, `validator_render_service.py`,
  `api/routers/validator.py` + 4-5 neue Testdateien.
- **Effort:** medium — kein neuer Rechenkern, ausschließlich additive
  Verkettung eines bestehenden Bausteins plus ein neuer, budget-bewusster
  Kurzform-Helfer.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_onset_extent_suffix()` | function (`render.py:614-639`, S2a) | Bereits fertiger Baustein für die drei zusätzlichen Langform-Stellen — nur zusätzlich verkettet, keine Änderung an der Funktion selbst. |
| `_onset_end_suffix` / `_onset_reach_suffix` / `_onset_sharpness_suffix` | functions (`render.py:546,585,599`) | Bestimmen die Verkettungs-Reihenfolge — `_onset_extent_suffix` hängt sich unverändert ans Ende an (Muster S1/S3). |
| `_sms_onset_sharpness_marker` / `_sms_onset_ende` | functions (`render.py:869,907`) | Musterfassung für den neuen Kurzform-Helfer — anhängbares Zeichen/Token oder leer, Aufrufer bindet es an die bereits gebildete Zeitgruppe. |
| `RainZone` | dataclass (`src/services/rain_extent.py:26-43`) | Datenquelle der Kurzform-Zonenwerte (`km_from`, `km_to`) — unverändert, keine neuen Felder nötig. |
| `OnsetEvent.rain_zones` / `.km_measured` | fields (`model.py:120,178`, S2a) | Beide Felder existieren bereits auf `OnsetEvent` — S2b befüllt sie zusätzlich in der Prüffläche, ändert das Modell selbst nicht. |
| `render_sms(msg, limit=140)` | function (`render.py:1482-1501`) | Öffentliche Kurzform-Fassade mit explizitem `limit`-Parameter — Testwerkzeug für die budget-genaue Drop-Prüfung (AC-8), keine Signaturänderung. |
| `render_alert_preview()` | function (`validator_render_service.py:93-172`) | Prüffläche — muss `rain_zones`/`km_measured` aus `OnsetPayload` lesen und ins `OnsetEvent` durchreichen (R4). |
| `OnsetPayload` | Pydantic-Model (`api/routers/validator.py:226-268`) | Vorschau-Payload-Schema — bekommt die neuen Felder gespiegelt (Vorwarnung analog #2046 F002 / S1/S3-Vorlage). |
| `_ASCII_EXTENSION_REPLACEMENTS` / `tests/tdd/_gsm7_charset.py` | mechanism/fixture | Der ASCII-Bindestrich (`-`) im Zonen-Kürzel ist GSM-7-Basiszeichensatz und wird von der Faltung nicht angefasst — dieselbe Prüfung wie beim `?`-Zeichen (S3 E6). |

## Getroffene Entscheidungen (aus dem PO-Briefing, nicht erneut vorlegen)

**Kurzform-Format:** `km8-12`, angehängt hinter der gesamten Zeitgruppe
inklusive des S3-Güte-Markers `?` — Beispiel: `R2.5@15:00@16:30 km8-12`.
Ganzzahlig gerundet wie die Langform (`int(round(...))`), ASCII-Bindestrich.

**Mehrere Zonen:** komma-getrennt ohne Leerzeichen, `km8-12,19-21` — EIN
`km`-Präfix vor der ersten Spanne, danach nur noch `X-Y`-Paare. Getrennt
aufgezählt, nie zu einer Hülle zusammengefasst (dieselbe Begründung wie S2a
E2: die trockene Strecke dazwischen darf nicht als nass erscheinen).

**Sichtbarkeit:** identisch zur Langform-Regel aus S2a — nur bei vermessener
Etappe (`km_measured`) und nur bei nicht-leeren `rain_zones`. Sonst entfällt
das Kürzel vollständig, die Zeile bleibt byte-identisch zum heutigen Stand.

**Budget-Regel:** Das Zonen-Kürzel ist das **zuletzt** angefügte Element der
Kurzform. Passt es nicht vollständig ins Zeichenbudget, entfällt es —
**niemals abgeschnitten, niemals eine halbe Spanne**. Bei mehreren Zonen
werden so viele genannt, wie vollständig passen, von vorn; passt nicht
einmal die erste, entfällt die Angabe ganz. Der harte Schnitt `body[:limit]`
(`render.py:996`) bleibt eine Reißleine, die auch mit Zonen nie greifen darf
(Bestandsinvariante `tests/tdd/test_onset_ende_sms_budget.py:107-137`).

**Sprache:** Die Kurzform ist ENGLISCH kodiert (`R`=Rain, `TH`=Thunder,
`now`). `km` ist international und bleibt unverändert.

**Mehr-Orte-Zweig:** `_onset_extent_suffix` wird auch dort angehängt — als
**dokumentierter No-op**. Dieser Zweig läuft ausschließlich über den
Ortsvergleich-Bündelpfad (`project.py:621`,
`to_multi_location_onset_alert_message`), der `rain_zones` bewusst nie
setzt (S2a AC-15, kein Streckenkonzept im Ortsvergleich). Zweck der
Anhängung: die sieben Aufrufstellen laufen nicht schweigend auseinander —
wer den Code liest, sieht an jeder Stelle denselben Baustein, nicht sechs
von sieben. Es ist **kein** neues Verhalten für den Ortsvergleich.

**Wegpunktnamen für unvermessene Etappen — entfällt ersatzlos** (Revision
gegenüber der S2a-Spec, die diesen Punkt noch als S2b-Scope benannte). Die
Analyse hat nachgemessen: `backfill_stage_distances()`
(`src/services/track_resolution.py:264-344`) rüstet die Kilometrierung aus
dem GPX-Bestand nach, und der Alarmpfad ruft sie **selbst auf**, für die
Etappe von `today`, **vor** der Segmentauflösung (`trip_alert.py:1385`).
Zur Alarmzeit ist die aktive Etappe damit vermessen, unabhängig vom
persistierten Stand — die Aussage „9 von 13 KHW-Etappen zeigen keine
Ausdehnung" aus der S2a-Spec beschreibt den gespeicherten Bestand, nicht die
Laufzeit. Eine Ersatzdarstellung für unvermessene Etappen wird deshalb nicht
gebraucht.

## Implementation Details

**Drei zusätzliche Langform-Aufrufstellen** (additive Verkettung des
bestehenden Bausteins, keine Änderung an `_onset_extent_suffix` selbst,
Reihenfolge wie bei S1/S3: Ende → Reichweite → Güte → Ausdehnung):

```python
# render.py:486 (_render_subject_onset)
f"{_onset_end_suffix(e)}{_onset_reach_suffix(e)}{_onset_sharpness_suffix(e)}"
f"{_onset_extent_suffix(e)}"

# render.py:813 (_render_telegram_onset, Variable `second`)
f"{_onset_wann_zeile(e)}{_onset_end_suffix(e)}"
f"{_onset_reach_suffix(e)}{_onset_sharpness_suffix(e)}{_onset_extent_suffix(e)} · "
f"{e.intensity_label} · {e.source_label}"

# render.py:658-660 (_render_email_onset_multi, dokumentierter No-op)
f"{_onset_wann_zeile(e, praefix='ab ')}{_onset_end_suffix(e)}"
f"{_onset_reach_suffix(e)}{_onset_sharpness_suffix(e)}{_onset_extent_suffix(e)} · "
f"{e.intensity_label}"
```

**Neuer Kurzform-Helfer** (`render.py`, Muster
`_sms_onset_sharpness_marker`/`_sms_onset_ende`, aber mit einem zweiten
Parameter für das verbleibende Budget — die einzige Kurzform-Anhängung
dieser Scheiben-Familie, die budget-abhängig ganz entfällt statt
unbedingt angehängt zu werden):

```python
def _sms_onset_extent_suffix(zonen: tuple[RainZone, ...], budget: int) -> str:
    """Issue #2051 S2b: Zonen-Kuerzel der Kurzform (` km8-12,19-21`) oder
    leer. `budget` ist die Anzahl noch verfuegbarer Zeichen NACH dem Rest
    des Textes (limit - len(bisheriger_body)) -- das Kuerzel haengt sich nur
    an, wenn es VOLLSTAENDIG hineinpasst; passt nicht einmal die erste Zone,
    entfaellt die Angabe komplett. Bei mehreren Zonen werden von vorn so
    viele genommen, wie vollstaendig passen -- nie eine angeschnittene
    Spanne, nie ein haengendes Komma."""
    if not zonen:
        return ""
    teile = [f"{int(round(z.km_from))}-{int(round(z.km_to))}" for z in zonen]
    genommen: list[str] = []
    for teil in teile:
        kandidat = " km" + ",".join(genommen + [teil]) if not genommen else (
            " km" + ",".join(genommen) + "," + teil
        )
        if len(kandidat) > budget:
            break
        genommen.append(teil)
    if not genommen:
        return ""
    return " km" + ",".join(genommen)
```

**Aufruf in `_render_sms_onset`** (`render.py:927-996`): NACH dem Bau von
`body = f"{head}: {token}"` (Zeile ~995), vor dem harten Schnitt:

```python
if getattr(e, "km_measured", False) and getattr(e, "rain_zones", ()):
    body += _sms_onset_extent_suffix(e.rain_zones, limit - len(body))
return body if len(body) <= limit else body[:limit]
```

Die `km_measured`/`rain_zones`-Prüfung steht bewusst VOR dem Helfer-Aufruf
(dieselbe Sichtbarkeitsregel wie `_onset_extent_suffix` in der Langform) —
der Helfer selbst kennt diese Regel nicht, er kennt nur das Budget.

**Prüffläche** (`validator_render_service.py:93-172`,
`render_alert_preview` → `OnsetEvent(...)`-Konstruktion): neue Felder
zusätzlich zu den bestehenden `getattr(...)`-Zeilen (Muster
`source_reach_time` o.), plus Import `from services.rain_extent import
RainZone`:

```python
km_measured=getattr(body.onset, "km_measured", False),
rain_zones=tuple(
    RainZone(
        km_from=z.km_from, km_to=z.km_to,
        onset_minutes=z.onset_minutes, event_end_minutes=z.event_end_minutes,
    )
    for z in getattr(body.onset, "rain_zones", [])
),
```

**`OnsetPayload`-Erweiterung** (`api/routers/validator.py:226-268`, additiv,
Muster `event_end_time` o.):

```python
class RainZonePayload(BaseModel):
    km_from: float
    km_to: float
    onset_minutes: int
    event_end_minutes: int | None = None

# in OnsetPayload:
km_measured: bool = False
rain_zones: list[RainZonePayload] = Field(default_factory=list)
```

## Expected Behavior

- **Input:** `OnsetEvent` mit optional gesetzten `rain_zones` (aus S2a) und
  `km_measured`; Kurzform-Renderer mit dem bestehenden `limit`-Parameter.
- **Output:**
  - Betreff, Telegram rich, E-Mail-Trip-Langform (unverändert seit S2a) und
    der Mehr-Orte-Zweig (No-op) rufen `_onset_extent_suffix` einheitlich als
    letztes Element auf.
  - SMS, Premium-SMS und Telegram-Kurzstil tragen zusätzlich das
    Zonen-Kürzel, wenn `km_measured` gesetzt UND `rain_zones` nicht leer
    ist — als letztes Element der Kurzform, budget-bewusst gekürzt bis hin
    zum vollständigen Entfallen, nie mitten in einer Spanne abgeschnitten.
  - `POST /api/trips/{id}/alert-preview` zeigt die Ausdehnung in allen
    betroffenen Kanälen, wenn der Payload `rain_zones`/`km_measured` trägt.
  - Ohne Zonen oder auf unvermessener Etappe bleibt jeder betroffene Text
    byte-identisch zum Stand vor dieser Spec.
- **Side effects:** keine — additive Feld-Nutzung und Textverkettung. Keine
  Persistenz betroffen, keine Änderung an der Auslöseregel.

## Acceptance Criteria

- **AC-1:** Given ZWEI `OnsetEvent` mit `km_measured=True`, die sich
  ausschliesslich in ihrer Zone unterscheiden (Fall A: km 8-12, Fall B:
  km 3-5) / When der E-Mail-Betreff (`_render_subject_onset`) fuer beide
  gerendert wird / Then traegt Fall A `Nass km 8-12` und **nicht**
  `Nass km 3-5`, Fall B `Nass km 3-5` und **nicht** `Nass km 8-12` — der
  Betreff bildet die Angabe also aus den Zonendaten des jeweiligen Events
  und traegt keinen konstanten Text.
  - Test: EIN Unit-Test mit beiden Faellen. Die Sollstrings werden im Test
    aus den Zonenwerten der jeweiligen Fixture **abgeleitet**
    (`f"Nass km {int(round(z.km_from))}-{int(round(z.km_to))}"`), nicht als
    Literal getippt — ein hart verdrahtetes Ergebnis im Produktivcode faellt
    dadurch auf. Je Fall zusaetzlich die Negativpruefung gegen den Sollstring
    des anderen Falls.

- **AC-2:** Given denselben Zwei-Faelle-Aufbau wie AC-1 / When Telegram rich
  (`_render_telegram_onset`) fuer beide gerendert wird / Then traegt die
  zweite Zeile in Fall A `Nass km 8-12` und **nicht** `Nass km 3-5`, in
  Fall B umgekehrt.
  - Test: EIN Unit-Test mit beiden Faellen, Sollstrings wie in AC-1 aus den
    Zonenwerten abgeleitet, je Fall die Negativpruefung gegen den anderen
    Sollstring.

- **AC-3:** Given ein Bündel-`AlertMessage` mit zwei Events aus dem
  Ortsvergleich-Pfad (Muster `_render_email_onset_multi`, `rain_zones`
  jeweils leer `()` — die einzige Konstellation, die dieser Pfad in
  Produktion je erhält) / When der Mehr-Orte-Zweig gerendert wird / Then
  bleibt der Text byte-identisch zum Stand vor dieser Spec, obwohl
  `_onset_extent_suffix` jetzt auch dort aufgerufen wird — die Anhängung ist
  ein dokumentierter No-op, kein neues Verhalten für den Ortsvergleich.
  - Test: Regressionslauf des bestehenden Mehr-Orte-Tests mit unverändertem
    Fixture (`rain_zones` nicht gesetzt), Volltextvergleich gegen den Stand
    vor dieser Spec.

- **AC-4:** Given ein `OnsetEvent` mit `km_measured=True`, einer Zone
  km 8-12 und Beginn/Ende, die die Zeitgruppe `R2.5@15:00@16:30` erzeugen /
  When `_render_sms_onset` (Standardlimit 140) rendert / Then lautet der
  Token-Teil exakt `R2.5@15:00@16:30 km8-12` — das Zonen-Kürzel hängt
  unmittelbar hinter der vollständigen Zeitgruppe, mit genau einem
  Leerzeichen als Fuge.
  - Test: Unit-Test gegen `_render_sms_onset`/`render_sms`, exakter
    Substring-Vergleich auf `R2.5@15:00@16:30 km8-12`.

- **AC-5:** Given denselben Aufbau wie AC-4, aber mit zwei Zonen km 8-12
  und km 19-21 / When die Kurzform gerendert wird / Then lautet das Kürzel
  exakt `km8-12,19-21` — komma-getrennt, ohne Leerzeichen, ohne
  wiederholtes `km`-Präfix, und NIEMALS als zusammengefasste Spanne
  `km8-21`.
  - Test: Unit-Test mit zwei Zonen, Substring-Prüfung auf `km8-12,19-21`
    UND Negativ-Prüfung, dass `km8-21` nicht vorkommt.

- **AC-6:** Given zweimal denselben Aufbau wie AC-4, einmal mit
  `km_measured=False` (unvermessene Etappe) und einmal — bei sonst
  identischer Konstruktion — mit `km_measured=True` / When beide Texte
  gerendert werden / Then fehlt das Zonen-Kürzel im ersten Fall vollständig
  (Text byte-identisch zum Stand vor dieser Spec) UND erscheint im zweiten
  Fall (Positivkontrolle — derselbe Aufbau, ein verschobener Wert,
  gegensätzliches Ergebnis, Muster S3-AC-6).
  - Test: Ein Testpaar mit identischem Aufbau bis auf `km_measured`, beide
    Ausgänge (Abwesenheit und Anwesenheit des Kürzels) im selben Test
    geprüft.

- **AC-7:** Given eine Zone mit `km_from=7.6`, `km_to=11.4` / When das
  Zonen-Kürzel gebildet wird / Then lautet es exakt `km8-11` — ganzzahlig
  gerundet (`int(round(...))`) wie die Langform-Rundung in
  `_onset_extent_suffix`, nicht abgeschnitten (`km7-11` wäre falsch).
  - Test: Unit-Test mit den exakten Nachkommawerten 7.6/11.4, Substring-
    Prüfung auf `km8-11` UND Negativ-Prüfung, dass `km7-11` nicht vorkommt.

- **AC-8:** Given den Basistext ohne Zonen aus AC-4
  (`"Obertilliacher Bergwiese: TH@18:00 >@23:59? R99.9"`, 49 Zeichen — 24
  Zeichen Ortsname-Kopf gekappt + `": "` + Gewitter-Token mit
  Untergrenzen-Ende und Güte-Marker) und zwei Zonen km 8-12/km 19-21
  (Kürzel-Kandidat ` km8-12,19-21`, 13 Zeichen; erste Zone allein
  ` km8-12`, 7 Zeichen) / When `render_sms` mit drei verschiedenen `limit`-
  Werten rendert: (a) `limit=56` (49+7, exakt Platz für die erste Zone),
  (b) `limit=55` (49+6, ein Zeichen zu wenig für die erste Zone),
  (c) `limit=62` (49+13, Platz für beide Zonen) / Then zeigt (a) NUR die
  erste Zone (`...R99.9 km8-12`, exakt 56 Zeichen), (b) GAR KEIN Kürzel
  (Text bleibt bei 49 Zeichen, byte-identisch zum zonenlosen Stand), und
  (c) BEIDE Zonen (`...R99.9 km8-12,19-21`, exakt 62 Zeichen) — nie eine
  angeschnittene Spanne, nie ein hängendes Komma.
  - Test: Drei Unit-Tests (oder ein parametrisierter Test) mit denselben
    Event-Daten und den drei `limit`-Werten, je eine exakte
    Zeichenlängen-Prüfung und ein exakter Substring-Vergleich.

- **AC-9:** Given denselben kombinierten Extremfall wie AC-8 (30-Zeichen-
  Ortsname → 24-Zeichen-Kopf, `onset_precip_mm=99.9`, Untergrenzen-Ende,
  Güte-Marker) mit zwei realistischen Zonen (max. erreichbar bei
  `RADAR_ZONE_MAX_POINTS=6`) UND dem Standardlimit `limit=140` / When
  derselbe Aufruf einmal mit `limit=140` und einmal ungedeckelt
  (`limit=4000`) rendert / Then sind beide Texte IDENTISCH (62 Zeichen,
  Muster S1-AC-16) — der harte Schnitt `body[:limit]` greift im
  Extremfall mit Zonen genauso wenig wie ohne.
  - Test: Testpaar mit `limit=140` und `limit=4000`, Gleichheitsprüfung
    beider Ergebnisse plus exakte Längenprüfung `== 62`.

- **AC-10:** Given ein `OnsetEvent` mit zwei Zonen km 8-12 und km 19-21,
  einmal über die E-Mail-Langform (`_render_email_onset`) und einmal über
  die Kurzform (`_render_sms_onset`) gerendert (dieselben Rohdaten,
  Kanalparität-Muster `test_onset_menge_kanalparitaet.py`) / When beide
  Texte auf ihre Zonenwerte geprüft werden / Then tragen beide dieselben
  km-Grenzen (8, 12, 19, 21) in derselben Reihenfolge — die Langform als
  `Nass km 8-12, km 19-21`, die Kurzform als `km8-12,19-21` — unterschied-
  liche Wortform, identischer Zahleninhalt.
  - Test: Paritätstest, extrahiert die Zahlenpaare aus beiden gerenderten
    Texten (Regex) und vergleicht sie auf Gleichheit.

- **AC-11:** Given den Extremfall aus AC-9 mit gesetztem Zonen-Kürzel /
  When der resultierende Text auf seinen Zeichenvorrat geprüft wird / Then
  ist er vollständig ASCII-rein (`text.isascii()`) — der Bindestrich im
  Zonen-Kürzel ist GSM-7-Basiszeichensatz und ändert daran nichts, anders
  als `~` (S3 E6).
  - Test: Unit-Test mit demselben Extremfall wie AC-9, `sms.isascii()`
    geprüft.

- **AC-12:** Given einen `OnsetPayload` mit gesetzten `rain_zones`
  (mindestens einer Zone) und `km_measured=True` / When
  `render_alert_preview(trip_obj, body)` läuft / Then trägt JEDER der vier
  betroffenen Preview-Texte (`subject`, `email_plain`, `telegram`, `sms`)
  die Ausdehnungsangabe — die Prüffläche muss die Lücke schließen, die die
  S2a-Lieferung als „nicht gemessen" gebucht hat (R4), sonst ist kein AC
  dieser Scheibe über HTTP nachweisbar.
  - Test: Unit-Test gegen `render_alert_preview` mit einem `OnsetPayload`
    (echtes Pydantic-Objekt, kein Mock), Substring-Prüfung auf die
    Zonenangabe in allen vier zurückgegebenen Textfeldern.

- **AC-13:** Given einen `OnsetPayload` OHNE die neuen Felder (Alt-Client,
  Muster #2046 F002) / When `render_alert_preview` läuft / Then bleibt
  jeder der vier Preview-Texte byte-identisch zum Stand vor dieser Spec —
  die neuen Felder sind additiv und defaulten auf „keine Ausdehnung",
  pydantic verwirft sie nicht still (Regressions-Absicherung des
  Rückwärtskompatibilitäts-Vertrags).
  - Test: Unit-Test mit einem `OnsetPayload`, der die neuen Felder
    weglässt, Volltextvergleich der vier Preview-Texte gegen den
    Stand vor dieser Spec.

- **AC-14:** Given einen beliebigen der vier neu betroffenen Texte
  (Betreff, Telegram rich, Mehr-Orte-Zweig, Kurzform) mit gesetzter
  Ausdehnungsangabe / When der Text auf Formulierungen geprüft wird, die
  eine Handlungsempfehlung oder eine Ankunftszeit-Rechnung über den Nutzer
  enthalten (Muster S2a-AC-16/S3-AC-15) / Then enthält KEINER der vier
  Texte eine solche Formulierung — ausschließlich km-Spannen und Zeiten.
  - Test: Unit-Test über alle vier Renderer-Ausgaben mit gesetzten Zonen,
    Negativ-Prüfung auf dieselbe Liste verbotener Muster wie S2a-AC-16.

## Known Limitations

- **Der Mehr-Orte-Zweig bleibt strukturell stumm.** Der No-op aus AC-3 ist
  keine Verbesserung für den Ortsvergleich — er bleibt ohne
  Streckenkonzept, `rain_zones` wird dort nie gesetzt. Eine echte
  Ausdehnungsangabe im Ortsvergleich bräuchte ein eigenes Streckenkonzept,
  das außerhalb dieser Scheiben-Familie liegt.
- **Briefing-Kurzfristhinweis und `/jetzt`-Kommando bleiben ohne
  Ausdehnung** — beide brauchen eine eigene Mehrpunkt-Verdrahtung
  (Ein-Punkt-Abfrage bzw. kein Reststreckenbezug), außerhalb dieses
  Zuschnitts.
- **Die Budget-Drop-Regel wird im realistischen Betrieb kaum sichtbar.**
  Bei `RADAR_ZONE_MAX_POINTS=6` und 2-km-Abstand entstehen höchstens drei
  Zonen mit ein- bis zweistelligen km-Werten — die AC-9-Rechnung zeigt 62
  von 140 möglichen Zeichen, deutlicher Puffer. AC-8 erzwingt die
  Drop-Situation deshalb über den expliziten `limit`-Parameter statt über
  eine im Betrieb erreichbare Zonenzahl — die Mechanik ist eine Reißleine
  für lange Ortsnamen und künftig größere Zonendeckel, kein heute aktiv
  durchlaufener Pfad.
- **Messlücken bleiben unmarkiert** (S2a Known Limitation, unverändert) —
  ein Punkt ohne Daten fällt still aus der Zonenbildung, ohne Kennzeichen
  im Text. Betrifft S2b nicht zusätzlich, S2b bespielt nur weitere
  Kanäle mit demselben, bereits bekannten Verhalten.

## Nicht-Ziele

- **Briefing-Kurzfristhinweis** (`starkregen_hint.py`) — braucht eine
  eigene Mehrpunkt-Abfrage im Hinweis-Pfad, eigene Scheibe.
- **`/jetzt`-Kommando** — Sofortabfrage ohne Reststreckenbezug,
  `NowcastResult` trägt kein Zonenfeld.
- **Wegpunktnamen für unvermessene Etappen — entfällt ersatzlos** (siehe
  Entscheidungs-Abschnitt oben; die S2a-Spec-Aussage war eine
  Momentaufnahme des Datenbestands, nicht der Laufzeit).
- **Änderungen an der Zonenbildung** (`src/services/rain_extent.py`,
  `derive_rain_zones`, `RainZone`) — S2b **konsumiert** die Zonen
  ausschließlich. Wie eine **Messlücke** behandelt wird (heute: der Punkt
  fällt still heraus, `rain_extent.py:77-78`, und zwei nasse Abschnitte
  verschmelzen zu EINER Zone), gehört **#2050 S4b/S4b-2** (abgestimmt
  2026-08-23 mit der dortigen Sitzung).

  **Stand nach der Abstimmung:** Die Zonenbildung bleibt **byte-gleich**.
  S4b hatte zunächst geplant, eine Lücke die Zone abschließen zu lassen,
  und hat das zurückgezogen — zwei S2a-Wächter sichern das Nicht-Trennen
  ausdrücklich zu (`test_regen_ausdehnung_zonenbildung.py:148`,
  `test_regen_ausdehnung_textstellen.py:503`, beide mit Positivkontrolle),
  und die dortige Begründung trägt: Ein als trennend gewerteter Ausfall
  erfindet eine trockene Strecke, die niemand gemessen hat. Beide
  Darstellungen behaupten Ungemessenes; ehrlich ist allein eine
  **Kennzeichnung**, und die ist Wortarbeit (S4b-2). S4b liefert deshalb
  nur die Nachvollziehbarkeit (additives `RainZone`-Feld mit Default,
  Abgriff ins Alarmprotokoll).

  **Kein AC dieser Spec schreibt das heutige Lückenverhalten fest.** Alle
  AC-Fixtures verwenden **lückenfreie** Punktreihen (jeder Abfragepunkt
  trägt ein Ergebnis). Die Zusicherung „mehrere Zonen bleiben getrennt
  aufgezählt" (AC-5, AC-10) wird deshalb mit zwei **bereits getrennten**
  Zonen in der Fixture geprüft, nie über eine Lücke hinweg — sonst wäre der
  Test ein Wächter, der die Korrektur aus #2050 S4b fälschlich rot färbt.

  Die Zonenzahl bewegt sich durch S4b also **nicht**. Sollte eine spätere
  Scheibe sie doch verändern (etwa indem eine gekennzeichnete Lücke zu zwei
  Zonen führt), wird das Kurzform-Kürzel länger und kann nach der
  Budget-Regel (AC-8) entfallen — das wäre **gewolltes Verhalten, keine
  Regression**.

- **Änderungen am Ortsvergleich** (`compare_radar_alert.py`,
  `project.py:621`) — kein Streckenkonzept, `rain_zones` bleibt dort leer.
- **Signaturänderung an `get_nowcast()`** — bleibt Ein-Punkt-API.
- **Keine neue Zentral-Kaskaden-Mechanik** — jede Aufrufstelle verkettet
  ihre Suffixe weiterhin einzeln (Bestandsmuster, unverändert seit S1).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Verkettung eines in S2a bereits fertigen
  Bausteins an drei weitere Aufrufstellen plus ein neuer, budget-bewusster
  Kurzform-Helfer nach demselben Suffix-Muster. Berührt keine der vier
  Entscheidungsflächen, die ein neues ADR verlangen würden: ADR-0011 (ein
  Backend-Renderer) bleibt gültig; ADR-0021 (geteilter Code Trip/Compare)
  wird angewendet, nicht verändert (Mehr-Orte-Zweig bleibt dokumentierter
  No-op, AC-3); kein neuer Kanal, kein neuer Provider, keine
  Persistenz-Änderung, keine Änderung an der Auslöseregel.

## Changelog

- 2026-08-23: Initial spec created (#2051 Scheibe S2b, Ausdehnung auf die
  übrigen Kanäle — drei zusätzliche Langform-Stellen, Kurzform-Zonenkürzel
  mit Budget-Drop-Mechanik, Prüffläche `validator_render_service.py`).
