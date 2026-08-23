# Context: feat-2050-s4b2-wortebene-kennzeichnung

Issue #2050, Scheibe **S4b-2**. Erstellt 2026-08-23 (Phase 1).

## Request Summary

Zwei Sachverhalte, die das System bereits KENNT, erreichen den Alarmtext nicht und werden
dadurch im Text falsch dargestellt:

1. **Ausgefallene Gewitterprüfung** — `convective_checked=False` ist bekannt, protokolliert und
   wirkt korrekt auf die Auslöse-Entscheidung. Der Text beschriftet den Alarm trotzdem als
   „Regen" / `R`, obwohl niemand weiß, ob es ein Gewitter war.
2. **Messlücke in der Radar-Ausdehnung** — `measurement_gaps` ist seit S4b im Alarmprotokoll,
   erreicht den Renderer aber nicht. Die genannte Ausdehnung ist bei einer Lücke tendenziell
   **zu klein** (Reihenfolge entlang der Route: nass, nass, LÜCKE, trocken → der Text behauptet
   implizit Trockenheit hinter der Lücke, wo nichts gemessen wurde).

Beides ist reine **Wortebene**: keine Änderung an der Auslöse-Entscheidung, an der Zonenbildung
oder am Protokoll.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/notification_service.py:177` | `RadarAlertRequest` — das Renderer-Eingangs-DTO. **Beide** Felder fehlen hier; das ist die Bruchstelle |
| `src/services/notification_service.py:1426` | Umsetzung Request → `OnsetEvent` (`rain_zones=tuple(request.rain_zones)`) — hier müssen die neuen Felder mitreisen |
| `src/services/trip_alert.py:2186` | Bauaufruf des `RadarAlertRequest`; `is_convective` wird mitgenommen, `convective_checked` nicht |
| `src/services/trip_alert.py:224–241` | `_messluecken_felder()` — Entstehung von `measurement_gaps` (`points_total`/`points_measured`/`gap_km`) |
| `src/services/trip_alert.py:302` | `_radar_e1_fields()` ruft die Lückenbildung auf |
| `src/services/radar_service.py:154, 764, 1129` | Herkunft von `convective_checked` (Default `True`, `False` bei INCA-Fehlschlag, Durchreichung) |
| `src/output/renderers/alert/render.py:486, 663, 742, 820` | Langform-Beschriftung „Gewitter"/„Regen" (Betreff, E-Mail-Body, SMS-Langform, Premium-SMS) |
| `src/output/renderers/alert/render.py:998` | Kurzform-Kürzel `TH`/`R` |
| `src/output/renderers/alert/render.py:624` | `_onset_extent_suffix()` — Ausdehnungstext Langform (`· Nass km 2-4, km 9-11`) |
| `src/output/renderers/alert/render.py:945` | `_sms_onset_extent_suffix()` — Ausdehnungstext Kurzform (` km2-4,9-11`) |
| `src/output/renderers/alert/render.py:609–621` | **Vorbild Langform:** `_onset_sharpness_suffix()` |
| `src/output/renderers/alert/render.py:925–942` | **Vorbild Kurzform:** `_sms_onset_sharpness_marker()` |
| `src/output/renderers/alert/render.py:979–1054` | `_render_sms_onset(msg, limit=140)` — Budget-Konstruktion **und** harter Sicherungsschnitt |
| `src/output/renderers/alert/render.py:1653–1679` | GSM-7-Extension-Faltung (`_ASCII_EXTENSION_REPLACEMENTS`, `_ascii()`) |
| `src/services/validator_render_service.py:123, 297, 335` | Weiterer DTO-Verbraucher |
| `src/output/renderers/alert/project.py:625` | Ortsvergleich-Pfad, baut ebenfalls über das DTO |

## Existing Patterns

**Das Kennzeichnungs-Muster (Vorbild Einsetzschärfe, #2051 S3) — exakt nachbauen:**

1. Ein **DTO-Feld** trägt die Information bis zum Renderer.
2. **Langform:** deutsches Text-Suffix, angehängt an jede Aufrufstelle
   (`_onset_sharpness_suffix` → `" · Ortsangabe ab {HH:MM} unscharf"`), aufgerufen an
   `render.py:495` (Betreff), `673` (E-Mail-Tabelle), `756` (Telegram), `829` (SMS-Langform).
3. **Kurzform:** **ein** GSM-7-Basiszeichen, einmalig berechnet, ans Ende des **vollständig
   gebildeten** Zeit-Tokens gehängt (`render.py:1009, 1015`). Die Marker-Funktion kennt die
   innere Form des Tokens bewusst nicht.

**Kurzform-Zeichen-Inventar (ENGLISCH), mit dem nichts kollidieren darf:**
`R` · `TH` · `now` · `@` · `>` · `?` · `km{X-Y,X-Y}` · `,` · `Rest{mm}` · `!{code}` ·
Metrik-Kürzel `[A-Z]{2}` · Wochentagskürzel (#2054) · Leerzeichen. App-weit reserviert: `X`.

**GSM-7:** Extension-Zeichen (`~ [ ] { } \ | ^ €`) kosten zwei Septets und werden hart auf
ASCII gefaltet (`render.py:1658–1669`). Deshalb wurde `?` statt `~` gewählt. Ein neues Zeichen
**muss** aus dem GSM-7-Basiszeichensatz stammen.

## Dependencies

- **Upstream:** `radar_service.NowcastResult.convective_checked`; `_messluecken_felder()` in
  `trip_alert.py`; `rain_extent.derive_rain_zones()` (`src/services/rain_extent.py:46`)
- **Downstream:** alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) in **beiden** Flächen
  (Trip **und** Ortsvergleich, über `project.py:625`); `validator_render_service.py`

## Existing Specs

- Spec zu #2050 S4a (enthält AC-7/8/9 sowie die in S4b gebauten AC-12/13)
- `docs/reference/api_contract.md` — DTO-Formate
- Vorbild-Spec #2051 S3 (Einsetzschärfe / Güte-Zeichen `?`) und #2051 S2b (Zonen-Kürzel)

## Was bereits gebaut ist (NICHT erneut bauen)

Nachgemessen, nicht angenommen: `tests/tdd/test_radar_convective_check_failure.py` läuft
**grün** (3 Tests) und sichert bereits ab:

- **AC-7** — eine ausgefallene Gewitterprüfung trägt die Briefing-Unterdrückung **nicht**
  (der Alarm geht also raus, er wird *nicht* unterdrückt)
- **AC-8** — eine durchgeführte Prüfung ohne Gewitter unterdrückt unverändert
- **AC-9** — der Ausfall steht im Protokolleintrag

Die verbleibende Lücke ist ausschließlich die **Beschriftung im Text**.

Ebenfalls fertig (S4b, live `e65bb8ea`): `measurement_gaps` im Alarmprotokoll, in beiden
Schreibpfaden (`trip_alert.py:2088` unterdrückt, `2355` versendet).

## Risks & Considerations

1. **🔴 Harter Sicherungsschnitt in der Kurzform.** `render.py:1054` endet mit
   `return body if len(body) <= limit else body[:limit]`. Das Budget wird davor durch
   **Konstruktion** gehalten (Zonen werden ganz abgewählt, wenn sie nicht vollständig passen,
   `render.py:971–976, 1052–1053`) — der Schnitt ist die letzte Sicherung. Folge für diese
   Arbeit: Ein neu angehängtes Zeichen kann im Randfall (langer Ortsname, viele Zonen) **still
   abgeschnitten** werden, ohne dass ein Test rot wird, denn die Bestandstests prüfen nur
   `len(sms) <= 140`. **Ein Test, der nur die Länge prüft, bewacht hier nichts.** Das neue
   Zeichen muss im Budget mitgezählt und vor den abwählbaren Zonen platziert werden, und der
   Nachweis muss seine **Anwesenheit** im Randfall prüfen.
2. **Zwei Sachverhalte, eine Datei.** Beide Punkte landen in `render.py`; deshalb eine Scheibe.
   Sie sind aber unabhängig und brauchen getrennte ACs.
3. **Renderer-Mail-Gate (#811).** `renderer_mail_gate.py:56` matcht
   `src/output/renderers/alert/(?!official_alerts\.py$)[^/]+\.py$` — `render.py` fällt darunter.
   Vor dem ersten Commit sind zwei **frische** Nachweise nötig: Modus-Matrix-Test und
   Mail-Validator mit Exit 0 gegen eine **echt zugestellte** Staging-Mail (kein Mock).
   Nachgemessen, nicht aus zweiter Hand übernommen.
4. **DTO-Erweiterung berührt mehrere Verbraucher.** `RadarAlertRequest` wird auch von
   `validator_render_service.py` und dem Ortsvergleich-Pfad (`project.py:625`) gebaut —
   Signaturänderung braucht den Referenzfeger über `tests/`.
5. **Zonenbildung bleibt unangetastet.** Zwei Wächter aus #2051 S2a sichern zu, dass eine Lücke
   Zonen weder zusammenwachsen noch trennen lässt
   (`tests/tdd/test_regen_ausdehnung_zonenbildung.py`,
   `tests/tdd/test_regen_ausdehnung_textstellen.py`). Der Fix ist **Kennzeichnung**, nicht die
   andere Darstellung — beide Darstellungen behaupten bei einer Lücke Ungemessenes.
6. **`official_alerts.py` ist NICHT betroffen** — eigener SMS-Pfad, amtliche DWD-Warnungen,
   andere Semantik.
7. **Kein Rat, nur Daten.** Die Kennzeichnung sagt, dass etwas ungemessen/ungeprüft ist — sie
   leitet daraus keine Handlungsempfehlung ab.

## Analysis

### Type

**Feature** (Änderung an bestehendem Verhalten). Kein Bug: die Auslöse-Entscheidung ist korrekt,
es fehlt Ausgabe.

### Affected Files (with changes)

| File | Change | Description |
|---|---|---|
| `src/services/notification_service.py` | MODIFY | `RadarAlertRequest`: zwei Optionalfelder; `send_radar_alert()` reicht sie an `OnsetEvent` weiter |
| `src/output/renderers/alert/model.py` | MODIFY | `OnsetEvent`: `convective_checked: bool = True`, `gap_km: tuple[float, ...] = ()` |
| `src/services/trip_alert.py` | MODIFY | Trip-Pfad: beide Werte an den Request; `_messluecken_felder()` ein zweites Mal an der Request-Baustelle nutzen |
| `src/output/renderers/alert/project.py` | MODIFY | Ortsvergleich-Pfad: `convective_checked` mitgeben (nur Punkt 1) |
| `src/services/validator_render_service.py` | MODIFY | Beide Unterpfade (Payload-Replay, Live-Preview) |
| `src/output/renderers/alert/render.py` | MODIFY | Zwei Suffix-Funktionen (Langform) + zwei Kurzform-Marker, verdrahtet an allen Kanal-Stellen |
| `tests/tdd/…` | CREATE | Neue Wächter (siehe Mutations-Vorgabe unten) |

### Scope Assessment

- Dateien: 6 MODIFY (Produktivcode) + neue Testdatei(en)
- Geschätzt: Produktivcode ~60–80 LoC, Tests ~90–150 LoC → **~150–230 LoC**
- Das 250er-Limit reicht rechnerisch, aber ohne Puffer → `loc_limit_override 500` vorsorglich
- Risk Level: **MEDIUM–HIGH** (Alarmtext auf allen vier Kanälen, laufende Tour)

### Technical Approach

Rein additiver Durchstich, kein neuer Datenweg. Es gibt **vier** Konstruktionsstellen, die alle
bedient werden müssen — die vergessene Stelle ist das größte Einzelrisiko, weil dann Vorschau
oder Ortsvergleich denselben Sachverhalt leiser darstellen als der echte Versand:

1. Trip: `trip_alert.py:2186` → `RadarAlertRequest`
2. Ortsvergleich: `project.py:621–656` (baut `OnsetEvent` direkt)
3. Validator, Payload-Replay
4. Validator, Live-Preview

**🔴 Default-Richtung ist pro Feld herzuleiten, nicht mechanisch:** `convective_checked` muss
`True` defaulten. Ein `False`-Default ließe jede Bestands-Fixture, die das Feld nicht setzt,
plötzlich „ungeprüft" behaupten — eine Regression auf breiter Front. Bei `km_measured` ist
umgekehrt `False` der sichere Default.

**🔴 `OnsetEvent` ist `@dataclass(frozen=True)`** (`model.py:76`, nachgeprüft) — dort darf kein
dict landen (Hashing bricht). Auf dem Event nur `gap_km: tuple[float, ...] = ()`;
`RadarAlertRequest` ist nicht frozen und darf den dict tragen. Das Alert-Log-Schema aus S4b
bleibt unverändert — es wird nur an einer zweiten Stelle gelesen.

**Ortsvergleich und Punkt 2:** gegenstandslos. `project.py:625` setzt `km_from=km_to=0.0` und
nie `rain_zones` — es gibt dort keine Ausdehnung, die zu klein sein könnte.

### Wortwahl (entschieden)

| | Langform (Deutsch, E-Mail/Telegram) | Kurzform (Englisch, SMS/Premium-SMS) |
|---|---|---|
| **Punkt 1** — Gewitterprüfung ausgefallen | ` · Gewitter ungeprüft` | `#` unmittelbar hinter dem Kürzel: `R#2.5@18:00` |
| **Punkt 2** — Ausdehnung zu klein | ` · Ausdehnung unvollständig gemessen` | `>` unmittelbar hinter der Zonen-Liste: `km2-4,9-11>` |

Begründung der Kurzform-Zeichen:
- `?` scheidet aus — belegt durch die Einsetzschärfe (#2051 S3).
- `#` statt `*` für Punkt 1: `*` wäre vor einer Zahl als Multiplikation lesbar (`R*2.5`).
- `>` für Punkt 2 statt eines neuen Wort-Suffixes: `>` trägt im Alarm-Vokabular bereits die
  Bedeutung **„Untergrenze"** (`>@20:00`). „Reicht mindestens so weit" ist dieselbe Bedeutung,
  auf die Strecke statt auf die Zeit angewandt — das Vokabular wächst nicht, und im knappsten
  Kanal kostet es ein Zeichen statt vier. Abgrenzung zu `?`: dort wäre eine *zweite, andere*
  Bedeutung entstanden, hier ist es die gleiche.
- Beide sind GSM-7-**Basis**zeichen (`tests/tdd/_gsm7_charset.py:19–26`), kein Extension-Risiko.
- Kollisionsprüfung: kein Bestandstest zählt `>`/`#`/`*`; `#` kommt im Alarm-Renderer nicht vor.
- Die Kennzeichnung nennt nur den Sachverhalt und leitet keine Handlung ab (Produktregel).

### 🔴 Die Budget-Falle und der Test, der sie bewacht

`render.py:1054` schneidet hart: `return body if len(body) <= limit else body[:limit]`.
Punkt 1s Marker sitzt im Kern-Token und ist dadurch strukturell geschützt. Punkt 2s Marker wird
**nach** dem Zonen-Suffix angehängt und ist damit genau der Risikofall: ohne eigenen Fit-Check
kann ein Fragment im Text landen, während ein reiner Längentest grün bleibt — der harte Schnitt
hält die Länge ja ein.

Konstruktion: derselbe Fit-Check wie bei der Zonen-Liste — passt der Marker nicht vollständig,
entfällt er **ganz**, nie angeschnitten.

**Pflicht-Mutation für den Adversary:** Fit-Check entfernen, Marker unbedingt anhängen.
**Dieser Test MUSS dabei rot werden:** Szenario nahe der 140-Zeichen-Kante (24-Zeichen-Ort,
Untergrenzen-Ende-Form mit Wochentag, volle Zonen-Liste) mit gesetzten Lücken. Die Assertion
darf **nicht** `len(sms) <= 140` sein (bleibt bei der Mutation grün), sondern muss das
abgeschnittene Fragment fangen — plus Positivkontrolle in einem zweiten Fall mit Platz, die
belegt, dass der Marker sonst tatsächlich erschiene.

### Scheiben-Schnitt: EINE Scheibe (entschieden)

Der Strategie-Agent empfahl einen Split in zwei Scheiben. Dagegen entschieden: `render.py` steht
unter dem Renderer-Mail-Gate, das pro Commit-Runde eine **echt zugestellte** Staging-Mail plus
Validator-Lauf verlangt. Ein Split zahlt den teuersten Posten doppelt — für zwei Änderungen, die
sich Datei und Verdrahtung teilen. Interne Reihenfolge wie empfohlen: erst Punkt 1 (Verdrahtung
durch alle vier Stellen, einfache Logik), dann Punkt 2 (Budget-Logik), damit Verdrahtungsfehler
nicht mit Grenzfall-Fehlern vermischt debuggt werden.

### Dependencies

Upstream: `NowcastResult.convective_checked`; `_messluecken_felder()` (`trip_alert.py:211–241`).
Downstream: vier Kanäle × zwei Flächen; `validator_render_service.py`.
Unberührt: `rain_extent.py` (Zonenbildung), `official_alerts.py` (eigener Pfad).

### Open Questions

Keine offenen Fragen an den PO. Die Wortwahl der Langform geht über die Akzeptanzkriterien in
Phase 3 zur Freigabe.

## Herkunft der Angaben

Drei parallele Explore-Agenten haben kartiert; die entscheidenden Behauptungen habe ich an der
Fundstelle selbst gegengeprüft. Dabei fielen zwei Agentenfehler auf: die Behauptung, ein
Bestandstest sei rot (er ist grün), und die daraus abgeleitete Fehlerbeschreibung „Alarm wird
unterdrückt" (tatsächlich geht er raus — AC-7 sichert genau das zu).
