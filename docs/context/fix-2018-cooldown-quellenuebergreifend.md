# Context: #2018 — Cooldown greift nicht über Quellen hinweg

## Request Summary

Ein Nutzer erhielt am selben Trip („KHW 403", Segment „Ziel") binnen 22 Minuten zwei
Gewitter-Alarme aus unterschiedlichen Quellen: 16:15 eine amtliche ORANGE-Warnung
(Gültigkeit 16:00–17:00), 16:37 einen Radar-Nowcast („Gewitter in 8 Min; Ziel ab 16:45").
Die zweite Mail verspricht im Text „Cooldown: Du erhältst diese Warnung höchstens einmal
in 30 Minuten". Der PO meldet: Cooldown wirkt bei Meldungen aus unterschiedlichen Quellen
nicht.

## Gemessene Ursachenkette

Der Cooldown ist **nicht** die wirkende Stufe. Die einzige quellenübergreifende Bremse ist
`check_event_identity_gate()` (#1467 S4b). Sie hat den Fall **erkannt** und dann über die
V2-Eskalations-Ausnahme **bewusst durchgelassen**:

| Schritt | Wert | Fundstelle |
|---|---|---|
| 1. amtlich zugestellt, Register geschrieben | `hazard_class="wet"`, `segment_ids=["Ziel"]`, `severity="MODERATE"`, Fenster 16:00–17:00 | `trip_alert.py:1838-1849`, `:1923-1932` |
| 2. Nowcast fragt Gate | `hazard_class="wet"`, `segment_ids=["Ziel"]`, `severity="HIGH"`, `point_at=16:45` | `trip_alert.py:1437-1445` |
| 3. Match gefunden | Präfix `event_identity:wet:` ✅ · Segment-Schnittmenge ✅ · Zeitüberlappung ✅ | `alert_gate.py:492-541` |
| 4. **Durchbruch** | `alert_urgency.exceeds("HIGH","MODERATE")` → `2 > 1` → `_ALLOWED` | `alert_gate.py:605-606` |
| 5. V1 hätte nicht gegriffen | `covered_until 19:45` vs. Schwelle `20:00` → `False` | `alert_gate.py:544-557` |

**Der Befund ist systematisch, kein Einzelfall:** `urgency_from_radar()` gibt bei
`is_convective=True` **immer** `"HIGH"` zurück (`alert_urgency.py:32-44`), während jede
amtliche Warnung unterhalb ROT höchstens `"MODERATE"` ist (Level 3 = ORANGE →
`hazard_symbols.LEVEL_LETTERS[3]=="M"`, `alert_urgency.py:24-29`). Ein Gewitter-Nowcast
kann eine vorausgegangene GELB-/ORANGE-Gewitterwarnung desselben Segments deshalb **nie**
als Dublette erkennen. Die Gegenrichtung (Nowcast zuerst, amtlich danach) greift dagegen.

## Zweiter, unabhängiger Befund: der Mailtext

Der Satz „Cooldown … höchstens einmal in 30 Minuten" (`render.py:389-391`, Bündelzweig
`:334-336`) ist reine Anzeige von `trip.alert_cooldown_minutes` und beschreibt
ausschließlich den Nowcast-Throttle (Scope `radar`, Key `trip.id`). Die vorige Mail war
eine **amtliche** Warnung — die füllt den Topf `"trip"`, nicht `"radar"`. Technisch hat
der Cooldown also korrekt nicht gegriffen; der Text erweckt beim Leser trotzdem die
Erwartung einer quellenübergreifenden Zusage, die das System nicht gibt. Der Satz
erscheint nur im Radar-E-Mail-Zweig, nicht bei amtlichen Warnungen und nicht in
Telegram/SMS.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_gate.py:560-660` | `check_event_identity_gate()` + `record_event_identity()` — die quellenübergreifende Stufe. Kern der Änderung |
| `src/services/alert_gate.py:401-419` | `resolve_hazard_class()` — Kanon `wet`; alles außerhalb → `None` → nie entdoppelt |
| `src/services/alert_gate.py:447-557` | `_find_matching_entry`, `_times_overlap`, `_covers_materially_more` (V1) |
| `src/services/alert_urgency.py:21-70` | `_RANK`, `exceeds()`, `urgency_from_official_level()`, `urgency_from_radar()` — **die Ursache** |
| `src/services/trip_alert.py:1437-1445`, `:1526-1533` | Nowcast-Zweig: Gate-Aufruf + Registrierung |
| `src/services/trip_alert.py:1838-1849`, `:1923-1932` | Amtlicher Zweig: Gate-Aufruf + Registrierung |
| `src/services/trip_alert.py:962-983`, `:1213-1217`, `:1366-1371` | `_is_throttled_with_cooldown()`, `cooldown_min`, `cooldown_display` |
| `src/services/throttle_store.py:39-82` | Vier getrennte Scopes (`trip`/`radar`/`compare_preset`/`compare_radar`) |
| `src/output/renderers/alert/render.py:334-336`, `:389-391` | Der irreführende Cooldown-Satz |
| `src/services/compare_official_alert.py:200-208` | Gleiche Konstellation im Ortsvergleich |
| `src/services/compare_radar_alert.py:63-79`, `:224-231` | Gleiche Konstellation im Ortsvergleich |

## Existing Patterns

- **Gate-Kette je Alarmart, eine gemeinsame Schlussstufe.** `check_nowcast_gate()`
  (Ruhezeit → Sperrzeit → Tageslimit), `check_official_alert_gate()` (Ruhezeit → Tageslimit,
  **ohne** Sperrzeit), danach für beide `check_event_identity_gate()`.
- **Sperrzeit ist bewusst quellen- und entitätsgetrennt** — vier Scopes, Begründung in
  `throttle_store.py:39-51`: Wiederverwendung würde Alarmarten einander unterdrücken lassen.
- **Fail-open als Leitlinie.** Register-Einträge, die sich nicht parsen lassen, werden
  übersprungen; fehlende Zeit- oder Segmentangabe führt zu „senden", nie zu „unterdrücken".
- **Registrierung erst nach erfolgreicher Zustellung**, nicht beim Auslösen.

## Dependencies

- **Upstream:** `AlertStateService` (`data/users/<user>/alert_state/<entity>.json`),
  `alert_urgency`, `radar_service.NOWCAST_HORIZON_MIN=180`, `OfficialAlert.valid_from/valid_to`,
  `normalize_segment_id()`.
- **Downstream:** alle vier Kanäle über `notification_service.py` (sechs getrennte
  `send_*`-Methoden für Alarme — kein gemeinsamer Versand-Engpass), `alert_log`
  (`REASON_EVENT_DUPLICATE`), Ortsvergleich-Pfade.

## Existing Specs & ADRs

- `docs/adr/0021-shared-deviation-alert-engine.md` — Träger aller Alarm-Ablauf-Entscheide;
  Nachträge `:104` (#1467 S3), `:166` (S4a, amtlich ohne Cooldown), `:189` (S4b-1,
  Ereignis-Identität), `:207` (#1917 S4b-2, Compare)
- `docs/specs/modules/rework_1467_s4b_entdopplung.md` — AC-4 (nicht-`wet` nie entdoppelt),
  AC-5 (leere Segment-ID ⇒ nie Match), AC-7, AC-13, AC-17; Leitsatz `:44-47`
- `docs/specs/modules/rework_1467_s4a_amtlich.md` — AC-3: „ein amtlicher Alarm scheitert
  nie an einer Sperrzeit" als Eigenschaft des Funktionstyps
- `docs/specs/modules/rework_1917_s4b2_compare_entdopplung.md`, `throttle_store.md` (#1213),
  `alert_daily_limit.md` (#1070), `alert_quiet_hours_localtime.md`
- `docs/adr/0016-amtliche-warnungen-additiver-typ.md` — Wurzel der Quellentrennung
- `docs/adr/0046-alarm-kanal-schwelle.md` — Kanal-Schwelle regelt WIE, nie OB

## Risks & Considerations

1. **🔴 Fehlerrichtung.** Der dokumentierte Leitsatz lautet: „Der gefährlichste Fehler ist
   der ausbleibende Alarm" (`rework_1467_s4b_entdopplung.md:44-47`). Die V2-Ausnahme ist
   genau dafür gebaut. Sie ersatzlos zu streichen hieße: eine amtliche GELB-Warnung um
   16:00 verschluckt den Radar-Nowcast „Gewitter in 8 Minuten" um 16:37 — die
   handlungsrelevantere der beiden Meldungen.
2. **Regression-Gefahr S4a/E1.** Der amtliche Pfad wurde bewusst vom `"trip"`-Cooldown
   entkoppelt, weil ein Änderungsalarm bis zu 120 Minuten lang jede amtliche Eskalation
   verschluckte. Bewacht von `tests/tdd/test_official_alert_cooldown_entkopplung.py`.
3. **Severity-Skala ist grob.** Drei Stufen (`LOW/MODERATE/HIGH`), Nowcast konvektiv ist
   konstant `HIGH` ohne Bezug zu Intensität oder Onset-Nähe. Jede Feinsteuerung über
   Severity trifft auf diese Auflösungsgrenze.
4. **Weitere Gefahrenarten ungeschützt.** Wind, Schnee, Glatteis, Hitze, Wegsperrung
   fallen in **keine** Klasse und werden quellenübergreifend nie entdoppelt (AC-4, bewusst).
   Nicht Teil des gemeldeten Falls — aber dieselbe Fläche.
5. **Änderungsalarm nicht angeschlossen.** Als offener Punkt S4b-3 in der Spec vermerkt;
   der Doppel-Alert-Guard (`trip_alert.py:1081-1099`) ist die einzige Absicherung Nowcast↔Δ.
6. **Ortsvergleich ist PO-zurückgestellt**, trägt aber dieselbe Konstellation. Änderungen
   am geteilten Baustein wirken dort automatisch mit — Regressionsrisiko ohne Zielabsicht.
7. **Parallelsitzung #2017 Scheibe B** schreibt in derselben Funktion `check_radar_alerts()`,
   im Block **nach** dem Gate (Nowcast-Abrufstelle, Segment-Ende-Guard-Rückbau). Abgrenzung
   abgesprochen; wer zuerst auf `main` ist, meldet sich, der andere rebased.
8. **Nebenbefunde** (nicht ursächlich, im Adversary zu prüfen): `_find_matching_entry`
   liefert den erstbesten statt den stärksten Registereintrag (`alert_gate.py:513-541`);
   der Nowcast übergibt `cooldown_minutes` nicht (`trip_alert.py:1443`); amtliche Warnungen
   ohne `valid_from`/`valid_to` erzeugen nie matchbare Einträge (`alert_gate.py:482`);
   `record()` fällt bei Lock-Timeout still aus (`throttle_store.py:139-150`).

## Abgrenzung

- **Nicht** Teil dieser Arbeit: `get_nowcast`-Abrufstelle, Segment-Ende-Guard-Rückbau,
  `trip_report_scheduler.py:1809-1815` (gehört #2017 B); Alarm-Uhrzeiten/Projektion
  (gehört #2020); Alarm-Textformat (gehört #1948 S6).
- Die Nowcast-Hälfte des gemeldeten Belegpaars ist durch #2009 überholt (Onset-Schwelle
  20→55 Min). Das Original-Zeitstempelpaar taugt nicht mehr als Messgrundlage — die
  Reproduktion muss künstlich mit Werten erfolgen, die die heutigen Schwellen passieren.

---

## Analysis

### Type
**Bug** — mit einer eingebetteten Produktentscheidung. Die Ursache ist ein
Konstruktionsfehler, kein Implementierungsfehler: die durchbrechende Stufe ist bewusst
gebaut, mutations-getestet und PO-freigegeben (#1467 S4b AC-10). Was fehlt, ist die
Unterscheidung zweier Skalen, die dieselben Etiketten tragen.

### Gegenprüfung der Ursachenkette (analysis-challenger)

Alle sieben Schritte am Code **BESTÄTIGT**, keine widerlegte Einzelbehauptung.
Verdict: **NEEDS REVIEW** — wegen genau eines ungeprüften Alternativpfads:

- **🔴 Offener Punkt A1:** `AlertStateService.reset()` löscht `event_identity:`-Einträge bei
  jedem regulären Briefing-Versand (bewacht von
  `tests/tdd/test_alert_state_briefing_reset.py:1132-1167`, AC-14). Lief zwischen 16:15 und
  16:37 ein Briefing, war der Registereintrag weg — **gleiches Symptom, anderer Defekt,
  anderer Fix** (Reset-Filter statt Eskalationslogik). Indiz dagegen: im Screenshot liegen
  beide Mails unmittelbar nebeneinander, ohne Briefing-Mail dazwischen. Nicht abschließend
  belegt.
- Widerlegt wurden: Segment-ID-Normalisierungsasymmetrie (beide Seiten literal `"Ziel"`),
  Zeitzonenfehler (GeoSphere liefert tz-aware, `geosphere_warn.py:64`), ein vierter
  Unterdrückungsmechanismus (Doppel-Alert-Guard prüft nur Δ-Keys, `trip_alert.py:415-420`).
- Level-Mapping für GeoSphere (AT) und DPC (IT) verifiziert; MeteoAlarm/Vigilance nicht
  geprüft — die gemeinsame `OfficialAlert.level`-Struktur (2–4) erzwingt es architektonisch.

### Drei einschnürende Befunde (Plan)

1. **V1 ist faktisch tot.** `NOWCAST_HORIZON_MIN` steht seit #1945 auf **180** statt 60
   (`radar_service.py:68-71`). Die V1-Ausnahme verlangt damit eine Abdeckung von 6 Stunden
   über das registrierte Ende hinaus — V2 ist im Gewitterfall die einzige Stufe, die
   überhaupt noch etwas tut, und sie öffnet.
2. **Die Quelle ist im Register bereits ablesbar** — ohne Signaturänderung. An allen vier
   Aufrufstellen gilt strikt: Nowcast setzt nur `point_at`, amtlich nur
   `window_start`/`window_end`.
3. **Signatur-Wächter.** `tests/tdd/test_compare_radar_alert_event_identity.py:842-882`
   friert die Parameterlisten von `check_event_identity_gate`, `record_event_identity` und
   `resolve_hazard_class` exakt ein. Jeder neue Parameter macht ihn rot.

### Optionen

| | Option | Trifft den Befund? | Risiko „Alarm bleibt aus" | Scope (prod LoC) |
|---|---|---|---|---|
| O-A | Nur den Cooldown-Satz wahrheitsgemäß machen | nein | keins | +8/-4 |
| **O-B** | **V2 quellenbewusst: Eskalation zählt nur innerhalb derselben Skala, amtlich ROT bricht absolut durch** | **ja, an der Wurzel** | mittel, benennbar | **+65/-10** |
| O-C | `urgency_from_radar()` differenzieren | teilweise | **hoch und unsichtbar** | +30/-5, Folgeänderungen offen |
| O-D | Ergänzungsmeldung statt Voll-Alarm | nein (zwei Meldungen bleiben) | am geringsten | +180…260, sprengt Limit |
| O-E | Karenz statt Ausnahme (Durchbruch erst nach X Minuten) | ja | **niedrig** — Unterdrückung wird Verzögerung | +45/-8 |
| **O-F** | `_find_matching_entry` liefert den **stärksten** statt erstbesten Eintrag | Härtung | senkt Risiko | **+15/-5** |

**O-C verworfen und als eigenes Ticket vorzumerken:** dieselbe Zahl speist
`alert_channel_threshold.split_by_threshold()` (`trip_alert.py:1428-1430`). Eine Abstufung
auf `MODERATE` nähme jedem, der für SMS die Schwelle `HIGH` gesetzt hat, still den
Gewitter-Alarm auf genau dem Kanal, den er im Gelände empfängt — und höhlt ADR-0046 („die
Schwelle regelt WIE, nie OB") der Sache nach aus. Verletzt zusätzlich
`feat_1461_s3a_alarm_dringlichkeit.md` AC-5 wörtlich.
**O-D verworfen und als eigenes Ticket vorzumerken:** löst die Beschwerde nicht (es bleiben
zwei Nachrichten in 22 Minuten), kostet 180–260 Zeilen über Gate, Modell, Renderer und vier
Kanäle, und kollidiert frontal mit #1948 S6.

### Technical Approach (Empfehlung)

**O-B + O-F liefern, O-A danach, O-E nur bei PO-Antwort (b).**

Die technische Unterscheidung, auf der alles ruht: `HIGH` aus
`urgency_from_radar(is_convective=True)` und `MODERATE` aus `urgency_from_official_level(3)`
sind **keine zwei Punkte einer Skala, sondern zwei Skalen mit gleichen Etiketten**.
`LEVEL_LETTERS = {2:"L", 3:"M", 4:"H"}` (`hazard_symbols.py:34`) macht ORANGE strukturell zu
`MODERATE`, während der Radar-Zweig ohne jeden Intensitätsbezug `HIGH` liefert. Der Vergleich
in `alert_gate.py:605` vergleicht also Äpfel mit Birnen.

Umsetzung ohne Signaturbruch: `record_event_identity()` schreibt einen Quellenvermerk in die
**Nutzlast** (nicht in die Signatur), abgeleitet aus der Fallunterscheidung, die die Funktion
ohnehin trifft (`alert_gate.py:643-651`); die Leseseite fällt bei Alt-Einträgen ohne das Feld
auf dieselbe Ableitung zurück. V2 bricht dann durch, wenn **(a)** beide Meldungen aus
derselben Quelle stammen (unverändertes Verhalten) **oder (b)** die neue Meldung amtlich ist
und `severity == "HIGH"` erreicht (Stufe ROT bzw. unbekannter Level als Fallback).

Damit bleibt die gefährlichste Konstellation offen — amtlich ROT nach Nowcast kommt **immer**
durch — und die gemeldete schließt sich.

**Ehrlich zu benennender Preis:** die konkretere Meldung fällt weg. Der Nutzer weiß dann
„Gewitter zwischen 16:00 und 17:00 auf der Etappe", aber nicht „ab 16:45, in 8 Minuten".

### Scheiben-Schnitt

- **S1 „Quellenbewusste Eskalation"** (~80 prod LoC, nur `alert_gate.py`): Quellenvermerk,
  quellenbewusste V2-Bedingung mit absolutem ROT-Durchbruch, stärkster-Treffer-Härtung (O-F).
  Plus ADR-0021-Nachtrag und Modul-Spec. Tests ~250–320 Zeilen ⇒ **`loc_limit_override`
  nötig**, Präzedenz S4a/S4b-1. Mutations-Gegenprobe zum ROT-Durchbruch ist Pflicht.
- **S2 „Karenz"** (O-E, ~20 LoC) — nur bei PO-Antwort (b), baut auf S1 auf.
- **S3 „Ehrlicher Cooldown-Satz"** (O-A, ~10 LoC) — erst **nach** dem Landen von #1948 S6,
  additive Formulierung, damit nur das bit-eingefrorene Golden
  (`test_multi_location_onset_alert.py:39-48`) angefasst werden muss.

### Scope Assessment (S1)
- Dateien: 1 produktiv (`src/services/alert_gate.py`), 1–2 Testdateien, 1 Spec, 1 ADR-Nachtrag
- LoC: ~+80/-10 produktiv, ~+250–320 Test
- Risk Level: **HIGH** (Alarm-Pfad, alle vier Kanäle, Ortsvergleich wirkt automatisch mit)

### Open Questions
- [ ] **PO-Entscheid:** Was soll passieren, wenn dasselbe Gewitter erst amtlich und Minuten
      später vom Radar gemeldet wird? (a) nur die erste · (b) zweite nach Mindestpause ·
      (c) zweite als Nachtrag · (d) alles bleibt, nur der Text wird ehrlich
- [ ] **A1 offen:** Lief zwischen den beiden Mails ein reguläres Briefing? Wenn ja,
      verschiebt sich die Ursache auf den Reset-Filter.
- [ ] Entschieden von mir (Tech Lead, kein PO-Halt): amtliche **ROT**-Warnung bricht immer
      durch — deckt sich mit dem Leitsatz „der gefährlichste Fehler ist der ausbleibende
      Alarm" und ist in allen Varianten so gebaut.

---

## PO-Entscheid 2026-08-21 (Henning)

**Gewählt: Variante (c) — Ergänzungsmeldung statt Voll-Alarm (O-D).**
Die zweite Meldung wird **nicht unterdrückt**. Sie wird sofort zugestellt, aber als kurzer
Nachtrag mit Bezug auf die bereits gemeldete Lage („Ergänzung zur amtlichen Warnung von
16:15: Radar zeigt Beginn ab 16:45").

Die Nachteile waren bei der Vorlage benannt (zwei Nachrichten bleiben, teuerste Variante,
Kollision mit #1948 S6) und sind vom PO in Kenntnis dieser Folgen gewählt worden. **Nicht
erneut aufrollen.**

**Zweite Auskunft:** Für „KHW 403" läuft nachmittags **kein** reguläres Briefing (nur
morgens/abends). Damit ist **offener Punkt A1 geschlossen** — der Registereintrag war zum
Abfragezeitpunkt vorhanden, das Gate hat ihn gefunden und über die V2-Eskalation
durchgelassen. Die Ursachenkette ist vollständig belegt.

**Tech-Lead-Entscheid (kein PO-Halt):** amtliche **ROT**-Warnung bricht immer als
Voll-Alarm durch, nie als Nachtrag.

### Folgen für den Zuschnitt

1. **O-B wird nicht verworfen, sondern zur Voraussetzung.** Die quellenbewusste
   Unterscheidung muss den Fall erkennen — nur das Ergebnis wechselt von „unterdrücken" zu
   „als Nachtrag zustellen". Der Gate-Ausgang wird dreiwertig statt zweiwertig.
2. **O-A wird Pflicht, nicht Kür.** Kommen weiterhin zwei Nachrichten, widerspricht der Satz
   „Cooldown: höchstens einmal in 30 Minuten" der gelieferten Wirklichkeit. Er gehört in
   dieselbe Lieferung wie der Nachtrags-Renderer.
3. **O-E (Karenz) entfällt** — der PO hat gegen die Mindestpause entschieden.
4. **O-F bleibt** und gewinnt an Bedeutung: der Nachtrag verweist auf einen konkreten
   Registereintrag, also muss der **stärkste** Treffer gewählt werden, nicht der erstbeste
   (`alert_gate.py:513-541`).

### Revidierter Scheiben-Schnitt

- **S1 „Dreiwertiges Gate"** (~90 prod LoC, nur `src/services/alert_gate.py`): Quellenvermerk
  in der Register-Nutzlast (ohne Signaturbruch, `alert_gate.py:643-651`), quellenbewusste
  Unterscheidung, dritter Ausgang „Nachtrag" samt Treffer-Kontext (`reported_at`, Quelle,
  gemeldeter Zeitbezug), absoluter ROT-Durchbruch, stärkster-Treffer-Härtung (O-F).
  **Verhaltensneutral**: solange kein Aufrufer den dritten Ausgang auswertet, bleibt die
  Zustellung unverändert. Präzedenz für eine verhaltensneutrale erste Scheibe: #2017 A.
- **S2 „Nachtragsmeldung"**: `AlertMessage`-Bezugsfeld (`model.py:112`), Nachtragsform je
  Kanal in `render.py`, Auswertung des dritten Ausgangs an den vier Aufrufstellen, neuer
  `alert_log`-Grund. **Erst nach dem Landen von #1948 S6** (dort +132 Zeilen in `render.py`,
  noch nicht auf `main`) — sonst zwei Sitzungen im selben Renderer-Zweig.
- **S3 „Ehrlicher Cooldown-Satz"** (O-A, ~10 LoC): additive Präzisierung, gehört zu S2 in
  dieselbe Datei; nur das bit-eingefrorene Golden
  (`test_multi_location_onset_alert.py:39-48`) wird angefasst.
- **Eigene Tickets, nicht hier:** O-C „Radar-Dringlichkeit differenzieren" (Kollateralschaden
  an der Kanal-Schwelle, ADR-0046), O-D-Ausweitung auf weitere Gefahrenarten jenseits `wet`,
  Änderungsalarm als dritte Prüfrichtung (S4b-3, in der Spec bereits als offen vermerkt).
