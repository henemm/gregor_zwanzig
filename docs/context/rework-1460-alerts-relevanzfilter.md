# Context: rework-1460-alerts-relevanzfilter

**Issue:** #1460 (Scheibe 2 von 5 im Epic #1458) · **Erstellt:** 2026-08-02
**Vorgänger:** #1459 (Alarm-Protokoll, live `161db8bb`) · **Nachfolger:** #1461 (Schwelle je Kanal)

## Request Summary

Das PO-Zielmodell aus #1458 umsetzen: **drei Quellen (Vorhersage-Änderung, Nowcast, amtliche
Warnung), ein gemeinsamer Relevanz-Filter.** Diese Scheibe behandelt Bedingung (b) „Nutzer ist
zum Zeitpunkt auf dem Segment" und (c) „neu oder verschärft"; (a) „auf diesem Kanal gewünscht"
folgt in #1461. **Erweiterter Umfang (PO 2026-08-02):** die vier getrennten Ablaufsteuerungen
für Trip und Ortsvergleich werden zu einer zusammengeführt, und `trip_id`/`preset_id` im
Protokoll werden ein Kennungsfeld plus Typfeld.

## Related Files

| Datei | Zeilen | Relevanz |
|---|---|---|
| `src/services/trip_alert.py` | 1298 | Vier Einstiegspunkte, alle vier Melde-Gründe des Trip-Pfads |
| `src/services/compare_alert.py` | 323 | Ortsvergleich Änderungs-Alarm |
| `src/services/compare_radar_alert.py` | 222 | Ortsvergleich Nowcast, Docstring: „1:1 vom Trip-Radar-Pfad übernommen" |
| `src/services/compare_official_alert.py` | 235 | Ortsvergleich amtliche Warnung |
| `src/services/corridor_threshold.py` | 118 | `evaluate_corridor_thresholds()`, reine Funktion ohne Trip-Wissen |
| `src/services/deviation_alert_engine.py` | 262 | Geteilter, location-generischer Auswertungskern (ADR-0021) |
| `src/services/weather_change_detection.py` | ~800 | `detect_changes()` — die eigentliche Δ-Rechenstelle (`:540-628`) |
| `src/app/metric_catalog.py` | — | `default_change_threshold` je Metrik (`:772-794` Sammelfunktion) |
| `src/services/alert_state.py` | 75 | Melde-Gedächtnis, generisch auf `entity_id` (ADR-0021) |
| `src/services/trip_report_scheduler.py` | 1720 | `_reset_alert_state_after_briefing()` `:1036-1042`, Aufruf `:972` |
| `src/services/official_alerts/base.py` | 242 | Zeitfenster-Filter `:59-87`, Fenster-Parameter `:90-176`, `:179-241` |
| `src/services/alert_log.py` | ~200 | Protokoll-Schreibseite, `trip_id`+`preset_id` `:115-183` |
| `internal/store/log.go` | — | `AlertLogEntry` `:43`, `AlertCountByTrip()` `:94`, zählt `e.TripID` `:101` |
| `internal/handler/archive_stats.go` | 45 | `/api/archive/stats` |
| `internal/handler/cockpit.go` | — | `:36` liest `AlertLogEntry` für die Cockpit-Kachel |
| `internal/scheduler/scheduler.go` | — | Fünf Alarm-Jobs, alle `*/15 * * * *` (`:145-153`, `runForAllUsers()` `:299-333`) |
| `api/routers/scheduler.py` | — | Fünf 1:1-Wrapper-Endpunkte (`:45-107`) |
| `frontend/src/routes/+page.svelte` | `:109` | Filtert Cockpit-Alarme über `a.trip_id === hero?.id` |

## Ist-Stand: die vier Ablaufsteuerungen

Fünf Scheduler-Jobs, alle im 15-Minuten-Takt, laufen durch vier getrennte Ablaufpfade.
**Die Trennung ist nicht fachlich begründet — sie ist unterschiedlich weit abgeschrieben.**
Gemessen 2026-08-02:

| | Tages-Obergrenze | Zeit-Sperre nach Meldung | Kanäle | Ruhezeiten geprüft |
|---|---|---|---|---|
| Trip (alle vier Gründe) | ja | `ThrottleStore` Scope `trip`/`radar` | E-Mail/Telegram/SMS + Regel-Override | vor der Erkennung (+ nochmal in der Engine) |
| Compare Änderung | ja | `ThrottleStore` Scope `compare_preset` | **fest `{"email"}`** (`:38,244`) | nur implizit in der Engine |
| Compare Nowcast | **nein** (kein Import) | **eigene JSON-Datei** statt `ThrottleStore` | E-Mail/Telegram/SMS | **nach** der Erkennung |
| Compare amtlich | ja | **keine** (Docstring: State-Vergleich genügt) | E-Mail/Telegram/SMS | vor dem Abruf |

**Nutzersichtbare Folgen dieser Divergenz:**
- Ortsvergleich-Nowcast kennt **keine Tages-Obergrenze** — die Bremse gegen Meldungsfluten fehlt.
- Ortsvergleich-Änderungsalarme gehen **ausschließlich per E-Mail**, unabhängig von der Einstellung.
- Ortsvergleich-Amtlich hat **keinen Zeit-Cooldown**.

**Wortgleich dupliziert** (drei Compare-Dateien): `_load_presets()`, `_notification_service_for()`,
`entity_id`-Schema `f"{preset_id}:{location_id}"`, `alert_log.append_entry()`-Aufrufmuster.

**Echt verschieden (bleibt berechtigt):** Etappen vs. Orte; Compare bündelt immer alle
getriggerten Orte in EINE Nachricht (#1170); Empfänger sind beim Vergleich ein Preset-Attribut,
beim Trip ein Nutzer-Attribut; Compare-Mail-Template; Ortszeit-Bezug (#1383).

**Kopplung der vier Melde-Gründe im Trip-Pfad:** Änderung + Grenzwert sind am engsten gekoppelt
(eine Sperre, eine Nachricht, ein Gedächtnis-Dict). Amtlich koppelt opportunistisch an, hat aber
einen eigenständigen Fallback `_send_official_alert_only()` (`:1187-1230`) mit **reduzierten
Gates** — ohne `has_active_rules`-Prüfung. Nowcast ist **vollständig entkoppelt**: eigener
Durchlauf, eigene Sperre, wird nie mit anderem gebündelt.

## Die drei Befunde

### B1 — Melde-Gedächtnis wird zweimal täglich gelöscht

`alert_state` ist **eine flache Datei je Entität** (`data/users/<user_id>/alert_state/<entity_id>.json`)
mit drei parallelen Schlüsselräumen ohne strukturelles Konzept „Ereignis vs. Zustand":
`<metrik>:<segment>` (Änderung) · `corridor:<metrik>:<segment>` (Grenzwert) ·
`official_alert_state_key(a)` (amtlich).

`_reset_alert_state_after_briefing()` löscht **die ganze Datei**, also alle drei Räume, nach
jedem regulären Briefing (nicht bei Ad-hoc). Für die Änderung ist das richtig — das Briefing ist
der neue Vergleichsanker. Für Grenzwert und amtliche Warnung zerstört es die Entprellung.

**Wichtig:** Die Entprellung selbst **ist gebaut** (`trip_alert.py:411-426`: ordinal → nächste
Stufe, stetig → Abstand um mindestens die Katalog-Empfindlichkeit gewachsen; geheilte Treffer
werden sofort geräumt `:408`). Sie entspricht exakt ADR-0040 Punkt 2. Das Löschen entwertet sie.
⇒ **B1 ist die Reparatur eines Bruchs gegen eine bereits getroffene Entscheidung, keine Neuerung.**

### B4 — Erste Verschärfungsstufe fällt durch das Vergleichszeichen

`weather_change_detection.py:602` feuert bei `abs(delta) > threshold` — **strikt größer**.
Gewitter: Ordinal-Sprung 0→1 ergibt `delta = 1.0`, Katalog-Schwelle `default_change_threshold = 1.0`
(`metric_catalog.py:286`) ⇒ `1.0 > 1.0` = **False**. Erst 0→2 meldet.
Regen 25→40 mm: `delta = 15.0`, Schwelle 10.0 ⇒ meldet, Severity MODERATE.

Die Regel ist **generisch** — keine Sonderbehandlung ordinaler Größen, nur der Schwellenwert ist
metrikspezifisch. ⇒ **B4 ist unabhängig von der Grundsatzfrage behebbar.**

### B6 — Amtliche Warnungen ohne Zeitbezug

`trip_alert.py:1151` ruft `get_official_alerts_for_location(*coord)` — nur Koordinaten.
Die Funktion **nimmt bereits `window_start`/`window_end`/`now` entgegen** (`base.py:179-241`,
seit #1316/#1348); der Aufrufer übergibt sie nur nicht. Default `window_start=None` ⇒
`effective_start = now`, keine obere Grenze ⇒ eine Warnung, die in drei Tagen beginnt, meldet heute.

**Vorlage vorhanden:** Der Nowcast-Pfad (`trip_alert.py:814-829`) wählt exakt das aktive Segment
über `seg.start_time <= now <= seg.end_time` und überspringt, wenn alle Segmente vorbei sind.
Der Änderungs-/Grenzwert-Pfad arbeitet dagegen nur mit einer groben Tagesgrenze
(`corridor_threshold.py:86`).

## Protokoll und Go-Seite

`alert_log.append_entry()` schreibt beide Felder immer (`trip_id`, `preset_id`, `:172/178`),
Read-Modify-Write über die volle Datei, zwei Ziel-Listen `entries` / `not_delivered`.
Go liest nur `TripID` (`log.go:44`) und zählt `counts[e.TripID]++` (`:85`, `:101`) —
**Compare-Einträge landen dadurch heute unter dem leeren Schlüssel `""`.**
Leser: `/api/archive/stats`, Cockpit-Handler (`cockpit.go:36`), Frontend `+page.svelte:109`
(`a.trip_id === hero?.id`).

## Existing Specs / ADRs

| Dokument | Bedeutung für diese Scheibe |
|---|---|
| **ADR-0040** (2026-08-01) | Schwellen-Alarm ist **eigener, additiver** Melde-Grund. Punkt 2 fordert genau die Entprellung, die B1 bricht. **Teilaufgabe 1 des Issues widerspricht dieser ADR frontal.** |
| ADR-0009 | Alerts sind Abweichungs-Wächter; absolute Schwellen als *Standard* verworfen |
| ADR-0013 | `threshold` ist die Δ-Sensitivität, kein Absolutwert |
| ADR-0016 | Amtliche Warnungen als additiver Typ (Konstruktionsvorbild für ADR-0040) |
| ADR-0021 | Geteilte `DeviationAlertEngine`, `AlertStateService` bereits generisch auf `entity_id` — **die Grundlage für die Zusammenführung ist gelegt** |
| ADR-0041 | Zuständigkeit Warn-Quellen |
| `docs/context/konzept-1458-alerts-zweck.md` | Zielmodell, Entscheidungen E1–E7 |

## Risks & Considerations

1. **🔴 Richtungskonflikt mit ADR-0040.** Teilaufgabe 1 („Grenzwert wird Empfindlichkeit statt
   eigener Auslöser") nimmt eine Entscheidung von vorgestern zurück. ADR-0040 führte den
   Grenzwert ein, **weil** der Änderungs-Melder bei anhaltender Gefahr strukturell stumm bleibt
   (Belegfall KHW 403: sechs Wochen ohne Gewitter-Alarm). Erfordert PO-Entscheidung und, falls
   bestätigt, ein ablösendes ADR. **Nicht still umbauen.**
2. **Umfang sprengt das Zeilenbudget** (250/Durchgang) um ein Vielfaches — ~4.250 Zeilen in acht
   Modulen plus Go. Schnitt-Vorschlag ist Ergebnis der Analyse-Phase (PO hat ihn im Issue
   ausdrücklich angefordert).
3. **Bestandsdaten.** Protokoll-Umbau `trip_id`/`preset_id` → Kennung + Typ: Read-Modify-Write
   mit Merge, Altlesbarkeit zwingend (CLAUDE.md „Daten-Schema-Reworks"). Go-Zähler, Cockpit und
   Frontend-Vergleich müssen mitziehen.
4. **Zwei Namensräume in `corridor.metric`** (`AlertMetric` vs. Katalog-`key`) werden zwangsläufig
   berührt — #1455, Muster wie #1257. Mindestens nicht verschlimmern. `alert_metric_for()` bleibt
   für diese Richtung tabu.
5. **Vereinheitlichung ändert Verhalten.** Tages-Obergrenze für Compare-Nowcast und Telegram/SMS
   für Compare-Änderung sind aus Nutzersicht Verbesserungen, aber **Verhaltensänderungen** — sie
   gehören in die Abnahmekriterien, nicht als stiller Nebeneffekt.
6. **Mandantentrennung:** mit zwei verschiedenen Nutzern testen (CLAUDE.md).
7. **Datenpfad:** Python schreibt über `get_data_dir(user_id)` (#1265), Go liest fest
   `users/<user>/alert_log.json` (`log.go:57`) — bei Änderungen am Ablageort auf Divergenz achten.
8. **Rote Linien:** keine getrennten Wächter für Nowcast und Vorhersage (#818); keine
   Compare-eigene Zweitfassung (Trip/Compare-Teilungsregel); Datenbeschaffung wird **nicht**
   fusioniert, nur die Ablaufsteuerung.

---

## Analysis (Phase 2, 2026-08-02)

### Type
Feature/Rework (kein Bug-Fasttrack) — enthält aber drei echte Fehlerbehebungen (B1, B4, B6).

### Fünf Arbeitspakete

| | Paket | Abhängigkeit | Umfang (Py / Go / Tests) | Risikorichtung |
|---|---|---|---|---|
| **P1** | Grenzwert → Empfindlichkeit statt eigener Melde-Grund | ⚠️ PO-Entscheidung, Vorbedingung für P5 | 0 (behalten) bzw. 150–250 / — / 150 + ADR | **Alarme bleiben aus** |
| **P2** | Melde-Gedächtnis überlebt Briefing (B1) | keine | 20–40 / — / 40–60 | Alarm-Stau (harmlos) |
| **P3** | Erste Verschärfungsstufe meldet (B4) | keine | 10–20 / — / 30–50 | mehr Alarme (harmlos) |
| **P4** | Amtliche Warnung auf Segment-Zeitfenster (B6) | keine | 70–120 / — / 100–160 | **Alarme bleiben aus** |
| **P5** | Vier Ablaufsteuerungen → eine, Kennung+Typ, Go mitziehen | P1, P2, P4 | 650–950 / 90–160 / 550–900 | **strukturell höchstes** |

### Technische Empfehlung: Reihenfolge umdrehen

Die im Issue angekündigte Reihenfolge („erst zusammenführen, dann Filter darauf") ist die
riskantere. **Empfehlung: erst P2+P3+P4 reparieren, dann P5 zusammenführen.**

- Beim Zusammenführen muss ohnehin entschieden werden, **welches** der vier heutigen Verhalten
  künftig gilt. Steht das richtige Verhalten vorher fest, ist P5 ein reiner Umbau mit der
  Zielmarke „Verhalten unverändert" — genau das Muster, das ADR-0021 bereits erfolgreich
  vorexerziert hat.
- Merge-zuerst vermischt Verhaltensentscheidung und Strukturumbau in einem Schritt.
- **Doppelarbeit entsteht praktisch nicht:** P2 ist Trip-only (Compare kennt den Reset gar nicht),
  P3 sitzt in der bereits geteilten Δ-Vergleichsstelle, P4 betrifft zwei Aufrufstellen mit je
  wenigen Zeilen.
- Teil 1 ist reiner Python-Code: kein Go-Rebuild, kein Frontend, kein Schema-Umbau — klein,
  einzeln auf Staging verifizierbar, sofort auslieferbar.

### Auflösung des Widerspruchs zu ADR-0040 (Vorschlag)

Das Zielmodell sagt „der Grenzwert ist kein vierter Grund"; ADR-0040 sagt „der Grenzwert ist ein
eigener, additiver Melde-Grund". Beides ist vereinbar, wenn der Grenzwert als **zweite Auslöseart
innerhalb der Quelle 1 (Vorhersage-Wert)** verstanden wird:

> **Quelle 1 — der Vorhersage-Wert** löst aus, wenn er sich signifikant **geändert** hat
> *oder* eine vom Nutzer gesetzte **Grenze reißt**.
> Quelle 2 — Nowcast. Quelle 3 — amtliche Warnung.
> Darüber **ein** Relevanz-Filter: Kanal (a) · Segment+Zeit (b) · neu-oder-verschärft (c).

Damit bleiben es drei Quellen und ein Filter, ohne die Betriebserfahrung aus ADR-0040
(KHW 403 — sechs Wochen Stille bei Dauergefahr) zurückzunehmen. **P1 entfällt dann als
Umbauarbeit** (0 Zeilen); die tägliche Doppelmeldung wird vollständig von P2 behoben, der
übersehene Gewittersprung vollständig von P3.

### Korrekturen und Ergänzungen zum Issue-Text

1. **B6 besteht auch im Ortsvergleich** — `compare_official_alert.py:176` ruft
   `get_official_alerts_for_location(loc.lat, loc.lon)` ebenso ohne Zeitfenster. Im Issue nicht
   genannt. **Entscheidung: wird mitkorrigiert** (sonst bliebe eine Asymmetrie stehen).
2. **Das neue Protokollformat ist real noch leer.** Drei Protokolldateien, 220 Einträge, alle
   ausschließlich mit den vier Altfeldern — die #1459-Erweiterung ist im Code, aber noch in keinem
   realen Eintrag. Die Zusammenführung `trip_id`/`preset_id` → Kennung+Typ kostet daher jetzt
   **keine** Bestandsdaten-Migration im Zwischenformat; nur die 220 Alteinträge (alle Typ „Tour")
   müssen lesbar bleiben. Der günstigste Zeitpunkt ist jetzt.
3. **Archiv-Statistik zählt Vergleichs-Alarme unter dem leeren Schlüssel `""`** zusammen
   (`log.go:101`) — ununterscheidbar, kein Test deckt es ab. P5 behebt das nebenbei.
   `/api/archive/stats` wird derzeit von keinem Frontend-Code abgerufen.
4. **`AlertStateService` ist bereits generisch** auf `entity_id` (ADR-0021) — die Grundlage für
   die Kennung+Typ-Umstellung liegt.

### Bewusst NICHT einebnen (sonst Regression)

- **Amtliche Eskalation bleibt ohne Zeit-Cooldown** (`compare_official_alert.py:10-19`, aus
  #1233/F002): Ein Cooldown würde eine echte GELB→ORANGE-Verschärfung unterdrücken. Wird das beim
  Zusammenführen still an Trips Cooldown angeglichen, ist das „Alarm bleibt aus".
- **P3 darf nicht blind `>=` setzen** — die Stelle bedient alle Metriken. Eingrenzen auf ordinale
  Größen (Enum-Herkunft, `ThunderLevel`).
- **P4 muss das Segment-Muster aus `trip_alert.py:814-829` exakt übernehmen** (aktives Segment /
  erstes vor Start / alle vorbei → überspringen). Schlechtere Segmentwahl ⇒ heute sichtbare
  Warnungen verschwinden.

### Bewusste Verhaltensänderungen (gehören in die Abnahmekriterien, nicht als Nebeneffekt)

- Ortsvergleich-Nowcast bekommt die **Tages-Obergrenze** (heute keine).
- Ortsvergleich-Änderungsalarm bekommt **Telegram und SMS** (heute fest nur E-Mail).
- Ortsvergleich bekommt erstmals einen **Gedächtnis-Reset beim Briefing-Versand** (heute nie).

### Open Questions (dem PO vorgelegt)

- [ ] **Reihenfolge:** erst reparieren, dann zusammenführen — oder wie im Issue angekündigt umgekehrt?
- [ ] **Grenzwert-Alarm:** als zweite Auslöseart von Quelle 1 behalten (ADR-0040 bleibt) — oder zur
      reinen Empfindlichkeit zurückbauen (ADR-0040 wird abgelöst)?

---

## 🔴 PO-Entscheidung 2026-08-02 — ERSETZT die Empfehlung oben zu P1

Meine Empfehlung „ADR-0040 behalten" war auf einem Lesefehler gebaut und ist **zurückgezogen**.
PO wörtlich: *„Beispiel Gewitter: das steht doch im normalen Briefing, warum tust du so, als ob es
unterginge, weil es keinen Alarm dazu gibt? Und wenn der Nowcast konkret ein Gewitter auf der
Etappe/Segment entdeckt, meldet er das doch auch oder nicht?"*

### Gegenprobe am Belegfall von ADR-0040 (Trip „KHW 403", `henning/5f534011`, gemessen 2026-08-02)

| Prüfung | Ergebnis |
|---|---|
| Steht Gewitter im Briefing? | **Ja** — `thunder` ist eine der 24 Größen in `display_config.metrics` |
| Lief der Nowcast-Alarm? | **Ja** — `radar_alert_enabled` wird im **Trip**-Pfad gar nicht ausgewertet (nur `compare_radar_alert.py:88`); der Weg ist für Touren immer aktiv |
| „Sechs Wochen ohne Alarm"? | **Nicht haltbar** — 53 Einträge für diesen Trip im Protokoll (Juni 35, Juli 15, Aug 3), erster 2026-06-13 |
| Einschränkung | Das Altformat hält den **Grund** nicht fest (`reason` erst seit #1459) — ob darunter Gewitter-Alarme waren, ist nicht auflösbar. Die Aussage „es kam nichts" ist damit widerlegt, die Aussage „kein *Gewitter*-Alarm" weder belegt noch widerlegt |
| Korridore real gesetzt | `thunder_level [null,1]`, `wind_gust [null,20]`, `precipitation_sum [null,10]`, `temperature_max [null,5]`, `temperature_min [5,null]` — alle `notify:true` |
| Änderungs-Regel Gewitter | `{kind: delta, metric: thunder_level, threshold: 1}` ⇒ genau der B4-Fall: 0→1 rutscht durch |

### Die Auflösung: Auslöser ist der Grenzübertritt, nicht die Sprunggröße

**„Grenzwert wird Empfindlichkeit" heißt nicht Abschaffung, sondern Aufwertung.** Die vom Nutzer
gesetzte Grenze wird zum **Maßstab des einen Melders**: Ausgelöst wird, wenn ein Wert die Grenze
**übertritt** — nicht, wenn er einen großen Sprung macht.

| Lage | heute | mit Grenzübertritt als Auslöser |
|---|---|---|
| Gewitter 0→1, Grenze 1 | meldet **nicht** (`1.0 > 1.0` false) | meldet — Grenze übertreten |
| Regen 25→40 mm, Grenze 10 | meldet (Sprung 15 > 10) | meldet **nicht** — war schon drüber, keine neue Entscheidung |
| Gewitter Stufe 2 hält an | meldet 2×/Tag neu | meldet nicht — steht im Briefing |
| Gewitter zieht auf 0→2, Grenze 1 | meldet | meldet |

Damit ist der eigenständige Grenzwert-Melder ein **Notbehelf für einen Melder, der die falsche
Frage stellt**. Wird die richtige Frage gestellt, entfällt er — und der Betriebsbefund hinter
ADR-0040 (Stille bei Dauergefahr) wird korrekt bedient statt ignoriert.

**Folge für ADR-0040:** wird **abgelöst** (neues ADR in der Spec-Phase, Status „Abgelöst durch").
Der Kern von ADR-0040 überlebt: Die nutzergesetzte Grenze ist maßgeblich, es gibt keine
systemseitigen Absolutwerte. Nur ihre Rolle ändert sich — vom zweiten Melder zum Maßstab des
einen Melders. ADR-0009 (Abweichungs-Wächter) bleibt damit ebenfalls unangetastet.

### Korrigierte Paketstruktur

| | Paket | Änderung gegenüber oben |
|---|---|---|
| **P1+P3** | Auslöser = **Grenzübertritt** statt Sprunggröße (enthält B4) | zu EINEM Paket verschmolzen; P1 ist keine Rücknahme mehr, sondern der Kern der Reparatur |
| **P2** | Melde-Gedächtnis überlebt das Briefing (B1) | unverändert — auch der Grenzübertritt braucht Gedächtnis, sonst meldet jede 15-Min-Prüfung erneut |
| **P4** | Amtliche Warnung auf Segment-Zeitfenster (B6), **Trip + Ortsvergleich** | unverändert |
| **P5** | Vier Ablaufsteuerungen → eine, Kennung+Typ, Go mitziehen | unverändert, Teil 2 |

**Offen für die Spec:** Was gilt für Größen, für die der Nutzer **keine** Grenze gesetzt hat?
(Naheliegend: die Katalog-Empfindlichkeit als Rückfallmaß wie heute — muss aber ausdrücklich
entschieden und als AC festgehalten werden, nicht stillschweigend.)

### PO-Entscheidung Reihenfolge

**Erst reparieren (P1+P3, P2, P4), dann zusammenlegen (P5).** Bestätigt 2026-08-02.

---

## 🔴 KORREKTUR 2026-08-02 — ERSETZT den Abschnitt „Die Auflösung: Auslöser ist der Grenzübertritt"

Die Formulierung „Auslöser ist der Grenzübertritt" ist **zurückgezogen** — das wären absolute
Grenzen durch die Hintertür, verworfen durch **ADR-0009** und **ADR-0013**.
PO wörtlich: *„Sprichst du von absoluten Grenzen oder von Delta? Dazu gibt es schon endlose
Debatten und eine Entscheidung. Lies die Specs, hier soll das Rad nicht zum x-ten Mal neu erfunden
werden!"*

### Es bleibt bei Delta. Die Steuerung ist die vorhandene Empfindlichkeitsstufe je Metrik

Der Nutzer wählt je Metrik **aus · entspannt · standard · sensibel**; dahinter liegen
**Delta**-Schwellen. Fertig gebaut, seit #946 die **einzige** Alarm-Quelle:

| Baustein | Ort |
|---|---|
| Spec | `docs/specs/modules/feat_864_859_alert_presets.md` (#864 + #859) |
| Datenfeld | `display_config.metric_alert_levels` — `src/app/models.py:617` |
| Schwellentabelle | `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` → `METRIC_PRESETS` (14 Metriken × 3 Stufen) |
| Backend-Auflösung | `src/services/alert_preset.py:96` `expand_per_metric_levels()` |
| Prioritätskette | `trip_alert.py:172-183` — `metric_alert_levels` → `alert_preset` → `alert_rules` → Katalog |
| Bedienung | `frontend/src/lib/components/alerts-tab/AlertMetricLevelRow.svelte:16` |
| Weather-Tab-Kopplung | #961: `should_fire = weather_tab_enabled AND level != 'off'`, inkl. Backfill `standard` |

Beispielwerte (Delta): Böen 35/20/12 km/h · Regen 20/10/5 mm · Nullgradgrenze 400/200/100 m.

### Was P1 damit wirklich ist

Der **Wertebereich** (`corridors[].notify`, eingeführt in #1444 S1) ist die **absolute** Grenze.
Er widerspricht ADR-0009 und sitzt am falschen Bedienort — #1371 S6 hatte den Schalter dort schon
einmal entfernt (Nachfolge #1462). **Er fliegt als Alarm-Auslöser raus.** Gesteuert wird über
Metrik-Auswahl + Empfindlichkeitsstufe. Wertebereiche bleiben für die **Markierung** in der
Anzeige (`corridors[].mark`) erhalten. **ADR-0040 wird abgelöst.**

### B4 präzisiert: die Empfindlichkeit ist bei Gewitter wirkungslos — und heute latent

`thunder_level` steht in **allen drei** Stufen auf **1** (`alertMetricTable.ts`), und
`weather_change_detection.py:602` vergleicht **strikt** `abs(delta) > threshold` ⇒ ein Sprung um
genau eine Stufe meldet nie, egal was eingestellt ist.

**Die Skala ist praktisch zweiwertig:** `ThunderLevel` = NONE/MED/HIGH (`models.py:35-39`), aber
`openmeteo.py:621-638 _parse_thunder_level()` vergibt nur HIGH (WMO 95/96/99) oder NONE — die
**Mittelstufe hat keine Quelle** („Fehler 2" aus #1418, Nachfolge #1419 S3, Vorarbeit #1457).

⇒ **B4 ist heute latent, nicht akut.** Einzig möglicher Sprung: NONE→HIGH (Delta 2 > 1, meldet).
Scharf wird der Fehler, sobald die Mittelstufe eine Quelle bekommt. Hier trotzdem beheben, sonst
geht #1419 S3 mit einem stillen Fehler live.

### PO-go: Stufen-Semantik bei ordinalen Gefahrenstufen

Die Achse ist das **Niveau**, nicht die Sprunggröße:

| Stufe | meldet, wenn … |
|---|---|
| **sensibel** | die Gewitterneigung überhaupt steigt — auch auf die Mittelstufe |
| **standard** | sie die höchste Stufe erreicht |
| **entspannt** | sie von „kein Gewitter" direkt auf die höchste Stufe springt |

Solange die Mittelstufe keine Quelle hat, verhalten sich standard und entspannt gleich.

### Damit hinfällig

D1 (Übertritt-Definition), D2 (Grenze schon beim Briefing gerissen) und D4 (Größen ohne
Nutzergrenze) aus der vorigen Fassung. **D3 bleibt sinngemäß** als Entprellung des
Melde-Gedächtnisses (P2), **D5 bleibt** (Vergleichszeichen ordinal, nicht blind `>=`),
**D6–D8 bleiben** unverändert.

### Abhängigkeit zu laufender Arbeit

**#1457** (Gewitter-Signale je Gebiet aus der besten Quelle) ist offen und wird aktiv bearbeitet
(zuletzt 2026-08-02 18:04). Es ändert die **Datenbeschaffung** der Gewittersignale, nicht die
Alarm-Auswertung — Berührungspunkt ist allein die Skala. Die hier festgelegte Niveau-Semantik muss
mit der dortigen Einstufung zusammenpassen, sobald die Mittelstufe eine Quelle bekommt (#1419 S3).
