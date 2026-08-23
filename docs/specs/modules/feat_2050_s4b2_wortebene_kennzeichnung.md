---
entity_id: feat_2050_s4b2_wortebene_kennzeichnung
type: feature
created: 2026-08-23
updated: 2026-08-23
status: draft
workflow: feat-2050-s4b2-wortebene-kennzeichnung
version: "1.0"
tags: [alarm, nowcast, radar, renderer, wortebene, kennzeichnung]
---

# Ausgefallene Gewitterprüfung und Messlücke werden im Alarmtext kenntlich gemacht (Issue #2050, Scheibe S4b-2)

## Approval

- [x] Approved — PO-Freigabe 2026-08-23 („go")

## Purpose

Zwei Sachverhalte, die das System bereits **kennt** und korrekt in Auslöseentscheidung und
Protokoll führt, erreichen den Alarmtext nicht und werden dort dadurch **falsch** dargestellt:

1. **Ausgefallene Gewitterprüfung** (`convective_checked=False`) — der Text beschriftet das
   Ereignis trotzdem als „Regen" bzw. `R`, obwohl niemand geprüft hat, ob es ein Gewitter war.
2. **Messlücke in der Radar-Ausdehnung** (`measurement_gaps`, seit #2050 S4b im
   Alarmprotokoll) — die genannte Ausdehnung ist bei einer Lücke tendenziell zu klein, der Text
   verschweigt, dass ein Teil der Strecke gar nicht gemessen wurde.

Diese Scheibe schließt beide Lücken auf der reinen **Wortebene**: ein zusätzlicher Hinweis im
Alarmtext, sonst keine Verhaltensänderung. Auslöse-Entscheidung, Zonenbildung und Protokoll
sind mit #2050 S4a/S4b fertig und bleiben unangetastet.

## Source

- **File:** `src/output/renderers/alert/render.py` — Betreff/E-Mail/Telegram/SMS-Kurzform des
  Radar-Onset-Alarms
  (Vorbild-Suffix `_onset_sharpness_suffix` `:609-621`, Vorbild-Marker
  `_sms_onset_sharpness_marker` `:925-942`, Kurzform-Konstruktion `_render_sms_onset`
  `:979-1054`, Zonen-Suffix `_onset_extent_suffix` `:624-649`,
  `_sms_onset_extent_suffix` `:945-976`)
- **File:** `src/output/renderers/alert/model.py` — `OnsetEvent` (`:77` ff., `@dataclass(frozen=True)`)
- **File:** `src/services/notification_service.py` — `RadarAlertRequest` (`:177` ff.),
  Umsetzung Request → `OnsetEvent` (`:1426`)
- **File:** `src/services/trip_alert.py` — Bauaufruf des `RadarAlertRequest` (`:2186`),
  `_messluecken_felder()` (`:211-241`)
- **File:** `src/output/renderers/alert/project.py` — Ortsvergleich-Pfad (`:621-656`), baut
  `OnsetEvent` direkt
- **File:** `src/services/validator_render_service.py` — Payload-Replay und Live-Preview
  (`:123, 297, 335`)
- **Identifier:** `OnsetEvent`, `RadarAlertRequest`, `_render_sms_onset`,
  `_onset_sharpness_suffix` (Vorbild), `_sms_onset_sharpness_marker` (Vorbild)

Schicht: ausschließlich Python-Core (`src/services/`, `src/output/renderers/`). Kein Go-, kein
Frontend-Anteil.

## Estimated Scope

- **LoC:** ~60–80 Produktivcode, ~90–150 Tests → Gesamtsumme voraussichtlich 150–230 Zeilen,
  ohne Puffer knapp am 250er-Standardlimit — `loc_limit_override 500` vorsorglich setzen.
- **Files:** 6 MODIFY (Produktivcode) + neue Testdatei(en)
- **Effort:** medium
- **Risiko:** MEDIUM–HIGH — Alarmtext auf allen vier Kanälen, laufende Tour (Karnischer
  Höhenweg, Start 2026-08-23); additiv, keine Signaturänderung an bestehenden Pflichtfeldern

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/radar_service.py::NowcastResult.convective_checked` | dataclass field | Bestehender Marker, Default `True`, `False` bei INCA-Sidecar-Fehler — Quelle für Punkt 1 |
| `src/services/trip_alert.py::_messluecken_felder()` (`:211-241`) | function | Bestehende Bildung von `measurement_gaps` (`points_total`/`points_measured`/`gap_km`), seit #2050 S4b im Protokoll — Quelle für Punkt 2 |
| `src/services/rain_extent.py::derive_rain_zones()` (`:46`) | function | Zonenbildung, bleibt unverändert — nur ihr Ergebnis (`rain_zones`) wird beim Rendern zusätzlich mit `gap_km` kombiniert |
| `src/output/renderers/alert/render.py::_onset_sharpness_suffix`/`_sms_onset_sharpness_marker` | function | Direktes Vorbild-Muster (#2051 S3) für Langform-Suffix und Kurzform-Marker |
| `src/services/notification_service.py::RadarAlertRequest` (`:177`) | dataclass | Nicht `frozen` — trägt die beiden neuen Felder bis `send_radar_alert()` |
| `src/output/renderers/alert/model.py::OnsetEvent` (`:77`) | dataclass | `frozen=True` — kein dict-Feld, `gap_km` als `tuple[float, ...]` |
| `src/output/renderers/alert/project.py` (`:621-656`) | module | Ortsvergleich-Pfad, baut `OnsetEvent` ohne den Umweg über `RadarAlertRequest` — Punkt 1 dort separat verdrahten |
| `src/services/validator_render_service.py` (`:123, 297, 335`) | module | Zwei Unterpfade (Payload-Replay, Live-Preview), beide müssen dieselbe Kennzeichnung zeigen wie der echte Versand |
| `api/routers/validator.py` (`OnsetPayload`) | module | **Nachgetragen 2026-08-23 nach der RED-Phase:** ohne ein Feld `convective_checked: bool = True` verwirft pydantic den Schlüssel **still**, und der Live-Preview-Unterpfad von AC-7 ist nicht messbar. Jede Vorgängerscheibe (#2046, #2051 S1/S2b/S3) hat diese Datei aus demselben Grund mitgezogen (Muster #2046 F002). Betrifft nur Punkt 1; der Replay-Unterpfad braucht sie nicht |

## Implementation Details

**Grundmuster (identisch zum Vorbild Einsetzschärfe, #2051 S3):** ein DTO-Feld trägt die
Information bis zum Renderer; eine Langform-Suffix-Funktion hängt ein deutsches Textstück an
(oder liefert `""`); eine Kurzform-Marker-Funktion liefert ein einzelnes GSM-7-Basiszeichen
(oder `""`), das der Aufrufer an das bereits vollständig gebildete Token anhängt.

**Vier Konstruktionsstellen** müssen beide Felder tragen — die vergessene Stelle ist das
größte Einzelrisiko, weil dann Vorschau oder Ortsvergleich denselben Sachverhalt leiser
darstellen als der echte Versand:

1. Trip: `trip_alert.py:2186` → `RadarAlertRequest`
2. Ortsvergleich: `project.py:621-656` (baut `OnsetEvent` direkt) — **nur Punkt 1**, da Punkt 2
   dort gegenstandslos ist (siehe Nicht-Ziel)
3. Validator, Payload-Replay
4. Validator, Live-Preview

**Neue Felder:**

- `RadarAlertRequest` (nicht frozen, `notification_service.py:177`): zwei zusätzliche
  Optionalfelder analog dem bestehenden Muster (`briefing_context`, `segment_id`) —
  `convective_checked: bool = True` und `gap_km: tuple[float, ...] = ()`.
  `send_radar_alert()` (`:1426`) reicht beide unverändert an `OnsetEvent` weiter.
- `OnsetEvent` (`frozen=True`, `model.py:77`): dieselben zwei Felder, gleiche Defaults.
  **Kein dict** — `RadarAlertRequest` darf einen dict tragen (z. B. wenn `_messluecken_felder()`
  ein Dict zurückgibt), `OnsetEvent` ausschließlich die verdichtete `tuple[float, ...]`, sonst
  bricht das Hashing des frozen dataclass.
- `convective_checked` defaultet auf `True` (Muster wie bei `km_measured=False` als sicherer
  Default für Punkt 2, aber umgekehrte Richtung): ein `False`-Default würde jede
  Bestands-Fixture, die das Feld nicht setzt, plötzlich „ungeprüft" behaupten — eine
  Regression auf breiter Front.

**Langform (Deutsch), zwei neue Suffix-Funktionen nach Vorbild `_onset_sharpness_suffix`
(`render.py:609-621`):**

- Punkt 1: `getattr(e, "convective_checked", True)` ist `False` → `" · Gewitter ungeprüft"`,
  sonst `""`.
- Punkt 2: nur wenn zusätzlich eine Ausdehnung gezeigt wird (`rain_zones` nicht leer **und**
  `km_measured`, dieselbe Sichtbarkeitsregel wie `_onset_extent_suffix`) **und** `gap_km` nicht
  leer → `" · Ausdehnung unvollständig gemessen"`, sonst `""`.
- Beide Suffixe an denselben vier Aufrufstellen anhängen, an denen `_onset_sharpness_suffix`
  bereits hängt (Betreff, E-Mail-Tabelle, Telegram, SMS-Langform).

**Kurzform (Englisch), zwei neue Marker nach Vorbild `_sms_onset_sharpness_marker`
(`render.py:925-942`):**

- Punkt 1: `#` unmittelbar hinter dem Kürzel (`kuerzel = "TH" if e.is_convective else "R"`,
  `render.py:998`) — Beispiel `R#2.5@18:00`. Anders als der Güte-Marker (der an das *letzte*
  Zeit-Token hängt) hängt dieser Marker an das *erste* Token der Zeile, weil er den Sachverhalt
  selbst (Gewitter vs. Regen) qualifiziert, nicht die Zeitangabe.
- Punkt 2: `>` unmittelbar hinter der bereits gebildeten Zonen-Liste (`_sms_onset_extent_suffix`,
  `render.py:945-976`) — Beispiel `km2-4,9-11>`.

  🔴 **Der Platz für den Marker wird VOR der Zonenauswahl reserviert** (Präzisierung aus der
  RED-Phase, 2026-08-23 — die ursprüngliche Fassung „Fit-Check *nach* der Liste" ist
  **nicht bewachbar** und wurde ersetzt):

  Der Marker ist **ein** Zeichen und steht am Textende. Hängt man ihn unbedingt an, wird der
  Text 141 Zeichen lang, und der harte Sicherungsschnitt `body[:limit]` (`render.py:1054`)
  entfernt genau dieses eine Zeichen wieder. Das Ergebnis ist **byte-identisch** zu dem der
  korrekten Fassung — die Pflicht-Mutation „Fit-Check entfernen" wäre am Draht nicht
  beobachtbar, und jede Assertion auf ein „abgeschnittenes Fragment" liefe ins Leere, weil ein
  einzelnes Zeichen kein Fragment hinterlässt. (Die Fragment-Formulierung stammt aus einem
  verworfenen Vorschlag mit einem vierzeichigen Marker.)

  Beobachtbar wird die Zusicherung nur, wenn das Zeichen im Budget mitgezählt wird, **bevor**
  die abwählbaren Zonen genommen werden. Im Randfall entfällt dann die letzte Zone und der
  Marker steht da; die naive Fassung zeigt alle Zonen und verliert den Marker still. Fachlich
  ist das zugleich die richtige Rangfolge: der Hinweis „unvollständig gemessen" wiegt schwerer
  als die letzte von vielen Streckenangaben — eine Zone weniger ist eine kleinere Aussage als
  eine Ausdehnung, die vollständig gemessen zu sein vorgibt.

  Der harte Sicherungsschnitt darf in keinem Fall die Absicherung sein: er kappt nur die
  Gesamtlänge, ohne auf Zeichengrenzen oder Wichtigkeit zu achten.

**Zeichenwahl (entschieden, nicht Gegenstand der Freigabe):** `?` ist durch die Einsetzschärfe
(#2051 S3) belegt und scheidet aus. `#` statt `*` für Punkt 1 (`*` wäre vor einer Zahl als
Multiplikation lesbar). `>` für Punkt 2 trägt im bestehenden Alarm-Vokabular bereits die
Bedeutung „Untergrenze" (`>@20:00`, Ende-Grammatik aus #2051 S1) — dieselbe Bedeutung
„reicht mindestens so weit", hier auf die Strecke statt auf die Zeit angewandt. Beide sind
GSM-7-Basiszeichen, kein Extension-Faltungsrisiko.

**Reihenfolge innerhalb der Implementierung:** erst Punkt 1 (Verdrahtung durch alle vier
Konstruktionsstellen, einfache Logik), dann Punkt 2 (Budget-Logik) — Verdrahtungsfehler und
Grenzfall-Fehler werden so nicht vermischt debuggt.

## Expected Behavior

- **Input (Punkt 1):** ein `OnsetEvent` mit `convective_checked=False`.
- **Output (Punkt 1):** Langform trägt ` · Gewitter ungeprüft`, Kurzform trägt `#` unmittelbar
  hinter dem Kürzel — in allen vier Kanälen, in beiden Flächen (Trip und Ortsvergleich).
- **Input (Punkt 2):** ein `OnsetEvent` mit `gap_km` nicht leer und einer gezeigten Ausdehnung
  (`rain_zones` nicht leer, `km_measured=True`).
- **Output (Punkt 2):** Langform trägt ` · Ausdehnung unvollständig gemessen`, Kurzform trägt
  `>` unmittelbar hinter der Zonen-Liste — in allen vier Kanälen des Trip-Pfads. Im
  Ortsvergleich entsteht nie eine Ausdehnung, der Hinweis erscheint dort folgerichtig nie.
- **Side effects:** keine Änderung an Auslöseentscheidung, Zonenbildung oder Protokoll; keine
  Handlungsempfehlung — die Kennzeichnung nennt nur den Sachverhalt.

## Acceptance Criteria

**Punkt 1 — ausgefallene Gewitterprüfung**

- **AC-1:** Given ein Radar-Onset-Alarm mit ausgefallener Gewitterprüfung
  (`convective_checked=False`) wird per E-Mail versendet, When der Trip-Nutzer das Briefing
  liest, Then steht in der Langform-Darstellung des Ereignisses der Zusatz
  „ · Gewitter ungeprüft" — der Leser kann „geprüft, kein Gewitter" nicht mehr mit „nicht
  geprüft" verwechseln.
  - Test: gestubbter Radar-Lauf mit `convective_checked=False` über die echte
    Alarm-Prüfstrecke bis zum gerenderten E-Mail-Text; Textstelle im Fließtext nachweisen.

- **AC-2:** Given derselbe Alarm wird per Telegram versendet, When der Trip-Nutzer die
  Telegram-Nachricht liest, Then trägt auch die Telegram-Langform denselben Zusatz
  „ · Gewitter ungeprüft" — kein Kanal ist gegenüber der E-Mail nachrangig.
  - Test: derselbe gestubbte Lauf, Telegram-Renderpfad geprüft.

- **AC-3:** Given derselbe Alarm wird per SMS versendet, When der Trip-Nutzer die SMS liest,
  Then steht unmittelbar hinter dem Kürzel (`R` oder `TH`) das Zeichen `#`, z. B. `R#2.5@18:00`
  — im knappsten Kanal ist der Sachverhalt trotzdem lesbar.
  - Test: derselbe gestubbte Lauf, SMS-Kurzform-Text auf das Zeichen an exakt dieser Position
    geprüft.

- **AC-4:** Given derselbe Alarm wird per Premium-SMS (Garmin inReach) versendet, When der
  Trip-Nutzer die Premium-SMS liest, Then trägt sie denselben `#`-Marker wie die reguläre
  SMS — auf der Hütte am Karnischen Höhenweg kommt nur dieser Kanal an, er darf den
  Sachverhalt nicht verschweigen.
  - Test: derselbe gestubbte Lauf, Premium-SMS-Renderpfad geprüft.

- **AC-5:** Given die Gewitterprüfung wurde durchgeführt und ergab kein Gewitter
  (`convective_checked=True, is_convective=False`), When derselbe Alarm über alle vier Kanäle
  gerendert wird, Then erscheint **weder** der Langform-Zusatz **noch** der `#`-Marker — die
  reguläre, geprüfte „kein Gewitter"-Aussage bleibt unverändert (Gegenprobe, sichert AC-1
  bis AC-4 gegen Übersteuerung).
  - Test: derselbe Prüfaufbau mit `convective_checked=True`, alle vier Renderpfade auf
    Abwesenheit des Zusatzes bzw. des Zeichens geprüft.

- **AC-6:** Given derselbe Sachverhalt (`convective_checked=False`) tritt an einem
  Ortsvergleichs-Preset auf statt an einem Trip, When der Ortsvergleich-Alarm gerendert wird,
  Then trägt er dieselbe Kennzeichnung (Langform-Zusatz bzw. `#`-Marker je nach Kanal) wie der
  Trip-Alarm — der Ortsvergleich ist sonst leiser als der Trip und meldet einen Sachverhalt
  nicht, den das System bereits kennt.
  - Test: derselbe gestubbte Lauf über den Ortsvergleich-Radarpfad (`project.py`), Kennzeichnung
    in mindestens einem Kanal nachgewiesen.

- **AC-7:** Given ein Alarm mit ausgefallener Gewitterprüfung wird in der Vorschau-/
  Validator-Fläche dargestellt (Payload-Replay oder Live-Preview), When der Nutzer die
  Vorschau ansieht, Then zeigt sie dieselbe Kennzeichnung wie der tatsächlich versendete
  Alarm — sonst wäre die Vorschau eine Zusage, die der echte Versand nicht einhält.
  - Test: derselbe gestubbte Lauf über `validator_render_service.py` (beide Unterpfade),
    Kennzeichnung im gerenderten Vorschautext nachgewiesen.

- **AC-8:** Given ein `OnsetEvent`, bei dem das Feld `convective_checked` gar nicht explizit
  gesetzt wurde (Bestandscode, Altdaten), When es gerendert wird, Then gilt es als **geprüft**
  und trägt **keinen** Hinweis — ein `False`-Default würde jede Bestandslage fälschlich als
  „ungeprüft" beschriften und wäre eine Regression auf breiter Front.
  - Test: `OnsetEvent` ohne explizites `convective_checked` konstruiert (Default greift),
    gerenderter Text ohne Zusatz/Zeichen in mindestens zwei Kanälen nachgewiesen.

**Punkt 2 — Messlücke in der Radar-Ausdehnung**

- **AC-9:** Given ein Radar-Onset-Alarm mit einer gezeigten Ausdehnung, bei deren Ermittlung
  Messpunkte fehlten (`gap_km` nicht leer), wird per E-Mail versendet, When der Trip-Nutzer das
  Briefing liest, Then steht hinter der Ausdehnungsangabe der Zusatz
  „ · Ausdehnung unvollständig gemessen" — der Leser weiß, dass die genannte Strecke nicht die
  vollständig gemessene ist.
  - Test: gestubbter Radar-Lauf mit gesetztem `gap_km` und gezeigter Ausdehnung über die echte
    Alarm-Prüfstrecke bis zum gerenderten E-Mail-Text; Textstelle nachgewiesen.

- **AC-10:** Given derselbe Alarm wird per Telegram versendet, When der Trip-Nutzer die
  Telegram-Nachricht liest, Then trägt auch die Telegram-Langform denselben Zusatz.
  - Test: derselbe gestubbte Lauf, Telegram-Renderpfad geprüft.

- **AC-11:** Given derselbe Alarm wird per SMS versendet, When der Trip-Nutzer die SMS liest,
  Then steht unmittelbar hinter der Zonen-Liste das Zeichen `>`, z. B. `km2-4,9-11>`.
  - Test: derselbe gestubbte Lauf, SMS-Kurzform-Text auf das Zeichen an exakt dieser Position
    geprüft.

- **AC-12:** Given derselbe Alarm wird per Premium-SMS versendet, When der Trip-Nutzer die
  Premium-SMS liest, Then trägt sie denselben `>`-Marker wie die reguläre SMS.
  - Test: derselbe gestubbte Lauf, Premium-SMS-Renderpfad geprüft.

- **AC-13:** Given die Mehrpunkt-Abfrage lief vollständig durch und alle Punkte wurden
  gemessen (`gap_km == []`), When derselbe Alarm über alle vier Kanäle gerendert wird, Then
  erscheint **kein** Hinweis auf Punkt 2 — wichtig, weil `gap_km` laut `trip_alert.py:222-229`
  **immer** entsteht, sobald die Mehrpunkt-Abfrage lief, auch wenn sie leer bleibt; eine leere
  Liste ist kein Signal für „es fehlt etwas".
  - Test: derselbe Prüfaufbau mit `gap_km=[]` bei sonst identischer, gezeigter Ausdehnung, alle
    vier Renderpfade auf Abwesenheit des Zusatzes bzw. des Zeichens geprüft.

- **AC-14:** Given das Feld für die Messlücken ist an einem `OnsetEvent` gar nicht vorhanden
  (Altdaten, oder die Mehrpunkt-Abfrage lief gar nicht erst), When es gerendert wird, Then
  erscheint ebenfalls **kein** Hinweis — Abwesenheit des Feldes bedeutet ausdrücklich **nicht**
  „alles wurde gemessen", sondern nur, dass über Lücken nichts bekannt ist.
  - Test: `OnsetEvent` ohne das Feld konstruiert (Default `()` greift), gerenderter Text ohne
    Zusatz/Zeichen nachgewiesen — bewusst dieselbe Beobachtung wie AC-13, andere Ursache.

- **AC-15:** Given ein Alarm zeigt gar keine Ausdehnung (keine Zonen, oder die Etappe ist nicht
  vermessen — dieselbe Sichtbarkeitsregel wie die Ausdehnungsangabe selbst), aber `gap_km` ist
  gesetzt, When er gerendert wird, Then erscheint **kein** Hinweis auf Punkt 2 — ein Hinweis auf
  eine unvollständig gemessene Ausdehnung ohne gezeigte Ausdehnung hinge ohne Bezugsgröße in der
  Luft und wäre für den Leser unverständlich.
  - Test: `OnsetEvent` mit `rain_zones=()` bzw. `km_measured=False`, aber gesetztem `gap_km`,
    gerenderter Text ohne Zusatz/Zeichen nachgewiesen.

- **AC-16:** 🔴 Given eine SMS-Kurzform mit einem 24-Zeichen-Ortsnamen, Untergrenzen-Ende-Form
  mit Wochentagskürzel und einer Zonen-Liste, die das 140-Zeichen-Budget vollständig ausschöpft,
  und zusätzlich sind Messlücken gesetzt, When der Text gerendert wird, Then steht der
  `>`-Marker im Text und die **letzte Zone entfällt** dafür — der Hinweis auf die unvollständige
  Messung darf niemals still verlorengehen, während die Streckenliste vollzählig bleibt.
  **Positivkontrolle** (b): derselbe Aufbau mit größerem Budget zeigt **beides** — die
  vollständige Zonen-Liste *und* den Marker; das belegt, dass die in (a) weggelassene Zone echt
  existiert und der Marker überhaupt gebaut wird.
  - Test: zwei SMS-Konstruktionen mit identischem Aufbau, einmal am Limit (Marker vorhanden,
    letzte Zone **ganz** entfallen, keine Reste einer angeschnittenen Spanne, kein hängendes
    `,` oder `-`), einmal mit Platz (volle Liste **und** Marker). Die Assertion darf **nicht**
    `len(sms) <= 140` sein: der harte Sicherungsschnitt hält die Länge unabhängig ein, deshalb
    bliebe eine reine Längenprüfung auch bei fehlerhafter Implementierung grün.
  - Ergänzender Test für die Lage „Budget reicht nicht einmal für die erste Zone": dann steht
    `>` **genau einmal** im Text (nämlich in seiner Bedeutung als Ende-Untergrenze aus #2051 S1)
    und nicht ein zweites Mal direkt hinter der Uhrzeit, wo es etwas Falsches aussagen würde.
  - **Präzisiert am 2026-08-23 nach der RED-Phase** (Kern unverändert, Nachweisform korrigiert):
    Die ursprüngliche Fassung verlangte, ein „abgeschnittenes Fragment" des Markers zu fangen.
    Das ist bei einem **einzeichigen** Marker am Textende unmöglich — unbedingtes Anhängen
    ergibt 141 Zeichen, der harte Schnitt entfernt genau dieses Zeichen, das Ergebnis ist
    byte-identisch zur korrekten Fassung. Die Zusicherung wird erst beobachtbar, wenn der Platz
    für den Marker **vor** der Zonenauswahl reserviert wird (siehe Implementation Details).

## Nicht Ziel

- **Zonenbildung (`src/services/rain_extent.py`) wird nicht angefasst.** Zwei Wächter aus
  #2051 S2a (`tests/tdd/test_regen_ausdehnung_zonenbildung.py`,
  `tests/tdd/test_regen_ausdehnung_textstellen.py`) sichern bereits zu, dass eine Lücke Zonen
  weder zusammenwachsen noch trennen lässt. Bei einer Messlücke behaupten **beide**
  Darstellungen Ungemessenes — Zusammenwachsen behauptet durchgehende Nässe über die Lücke,
  Trennen behauptet Trockenheit an der Lücke. Deshalb ist die Antwort dieser Scheibe
  **Kennzeichnung**, nicht eine andere Zonen-Darstellung.
- **Auslöse-Entscheidung und Protokoll bleiben unverändert.** #2050 S4a (`convective_checked`
  in der Briefing-Unterdrückung) und #2050 S4b (`measurement_gaps` im Alarmprotokoll) sind
  fertig; diese Scheibe liest ihre Ergebnisse nur zusätzlich für die Textausgabe.
- **`official_alerts.py` (amtliche DWD-Warnungen) ist nicht betroffen** — eigener Pfad, andere
  Semantik, keine der beiden Größen (`convective_checked`, `gap_km`) existiert dort.
- **Punkt 2 ist im Ortsvergleich gegenstandslos.** `project.py:625` setzt
  `km_from=km_to=0.0` und nie `rain_zones` — es gibt dort keine Ausdehnung, die als
  unvollständig gemessen gekennzeichnet werden könnte. Ausdrücklich festgehalten, damit dies
  später nicht als vergessene Stelle gilt (Abgrenzung zu AC-6, die ausschließlich Punkt 1
  betrifft).
- **Kein Rat, nur Daten.** Die Kennzeichnung benennt einen Sachverhalt (ungeprüft/unvollständig
  gemessen) und leitet daraus keine Handlungsempfehlung ab.
- **Dringlichkeit und Ereignis-Identität** bei ausgefallener Gewitterprüfung (Priorisierung
  statt Beschriftung) sind nicht Gegenstand dieser Scheibe — anderer Entscheidungstyp, eigene
  Messung nötig, an anderer Stelle im Code (`trip_alert.py:1577, 1917, 2042`).

## Known Limitations

- Die Kennzeichnung ist rein additiv am Text — sie ändert nichts an Menge, Zeit oder Ort des
  Alarms selbst.
- Bei mehreren gleichzeitig gebündelten Onset-Ereignissen (Mehr-Orte-Alarm) trägt jedes Ereignis
  seine eigene Kennzeichnung unabhängig — kein gemeinsamer Marker für das Bündel.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine additive Wortebenen-Änderung nach bereits etabliertem Muster
  (#2051 S3, Einsetzschärfe-Kennzeichnung) — keine neue Architektur-Entscheidung, sondern
  Anwendung einer bestehenden.

## Changelog

- 2026-08-23: Initial spec created (aus `docs/context/feat-2050-s4b2-wortebene-kennzeichnung.md`).
