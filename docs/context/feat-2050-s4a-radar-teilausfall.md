# Context: feat-2050-s4a-radar-teilausfall

**Issue:** #2050 Scheibe **S4a** — Szenario 6, Anforderung **B-4** („Teilausfall einer Quelle
gilt nie als Entwarnung"), mit D-2 („jede Unterdrückung hat einen benannten Grund samt der
Werte, die zur Entscheidung führten").
**Herkunft des Szenarios:** #1628 (Karnischer Höhenweg, 2026-08-08: 14 von 14 Radar-Prüfläufen
scheiterten mit HTTP 503, ohne dass irgendwo sichtbar wurde, dass die Datenlage fehlte).

## Request Summary

Ein echter Ausfall der Radar-Quelle endet im Alarmpfad heute als lautloses Nichts — im
Alarmprotokoll des Nutzers ununterscheidbar von „geprüft, alles ruhig". Die Scheibe führt den
bereits existierenden Ausfall-Marker in die **Auslöseentscheidung** und ins **Protokoll**.

## Der Befund in einem Satz

`NowcastResult.data_unavailable` existiert seit #1628 S1 — und wird außerhalb von
`radar_service.py` **in keiner einzigen Zeile Produktivcode gelesen** (repoweiter grep: null
Treffer).

## Was bereits gebaut ist (und deshalb NICHT Gegenstand dieser Scheibe ist)

| Was | Wo | Aus |
|---|---|---|
| Ausfall-Marker in den Daten, sauber getrennt von Kontingent-Drosselung | `src/services/radar_service.py:993-1003` | #1628 S1 |
| Ehrlicher Text im `/jetzt`-Kommando statt „Kein Niederschlag" | `src/services/radar_service.py:590-597` | #1628 S3 |
| Health-Journal für **anhaltende** Ausfälle (Betreiber-Sicht, `/api/scheduler/status`) | `radar_service.py:520-541` → `providers/enrichment_health.py` | #1581 |
| Ausweich-Zeitfenster der Radar-Prüfläufe (`7,22,37,52`) | `internal/scheduler/` | #1628 S0 |

**ADR-0018** („Modell-Fallback mit Ausweichen, aber ohne Kaschieren") führt den Radarpfad
deshalb als erfüllt. Die Invariante ist dort aber auf **Daten-Marker + Betreiber-Health-Signal**
formuliert. Die dritte Ebene — *der Nutzer, dessen Alarm ausbleibt* — ist von ADR-0018 nicht
abgedeckt und genau der Gegenstand von B-4.

## Die Lücke

`radar_alert_due()` (`src/services/trip_alert.py:147-158`) liest **nur** `onset_minutes` und
`already_running`. Ein Ausfall liefert `frames=[]` → `onset_minutes=None` → `False` → Ausstieg
`trip_alert.py:1681` mit nacktem `continue`.

Von den **15 Ausstiegen** des Radarblocks ist das der einzige völlig stumme — kein
Protokolleintrag, nicht einmal eine Logger-Zeile. Der Ausfall fällt zwangsläufig genau in ihn:

| Ausstieg | Zeile | Protokoll heute |
|---|---|---|
| Gate blockt | :1485 | ✅ `gate.reason` |
| Sperrzeit nicht überholt | :1628 | ✅ `cooldown` |
| Budget erschöpft | :1654 / :1671 | ✅ `daily_limit` |
| Briefing kündigte an | :1753 | ✅ `briefing_announced:…` |
| Doppel-Alarm-Guard | :1781 | ✅ `double_alert_guard` |
| Ereignis-Identität | :1946 | ✅ |
| **`radar_alert_due() == False`** | **:1681** | ❌ **nichts** |
| `get_nowcast()` wirft | :1560 | ❌ nur `logger.error`; Eintrag nur zufällig, wenn gerade die Sperrzeit lief |

Die zweite Zeile ist der Zwilling: die Ausnahme-Variante desselben Falls (Fehler statt
fail-soft-Leerergebnis).

## Was den Fall NICHT rettet (geprüft, damit es niemand erneut prüft)

- **Der Cache maskiert nichts.** Leere Frames werden nie gecacht (`radar_cache.py:106-107`) —
  jeder Lauf während eines Ausfalls trifft neu auf den echten Fehler. Maskiert wird höchstens
  ein transienter Ausfall innerhalb der 300-s-TTL nach einem *erfolgreichen* Abruf.
- **Die Vergleichsbasis wird nicht verfälscht.** `record_nowcast_sent()` (:2019) läuft erst
  nach zugestelltem Alarm; bei Ausfall wird **gar nichts** geschrieben, die letzte echte
  Messmenge bleibt stehen. Kein Datenschaden — aber eben auch kein Signal.
- **Das Health-Journal hilft dem Nutzer nicht.** Es ist eine Betreibergröße in
  `data/diagnostics/enrichment_calls.jsonl` und im Status-Endpunkt, nicht nutzerbezogen, und
  erscheint in keinem Kanal.

## Der zweite Fund: der eigentliche *Teil*ausfall

Szenario 6 spricht von einem **Teil**ausfall. Der Alarmpfad machte zum Zeitpunkt der Kartierung
nur einen einzigen Radarabruf — die Frage war deshalb, was ein Teilausfall hier überhaupt ist.
Drei Formen, kartiert und nachgeprüft:

> **Nachtrag 2026-08-23:** Mit **#2051 S2a** (räumliche Ausdehnung, fertig, merged vor dieser
> Scheibe) wird aus dem einen Abruf eine Schleife über bis zu sechs Messpunkte. Damit gibt es
> die „Teilstrecke" des Szenarios zum ersten Mal wirklich — und der Fall ist dort bereits
> versorgt: ein ausgefallener Folgepunkt gilt als **Lücke** (weder nass noch trocken) und trennt
> keine Zone, der Alarm geht trotzdem raus. Offen bleibt der Ausfall des **auslösenden** Punktes
> — dort liest die Auslöseregel den Marker weiterhin nicht, und das ist Form A unten.

| Form | Was passiert | Wirkung im Alarmpfad |
|---|---|---|
| **A · Totalausfall** | kein Frame, `data_unavailable=True` | lautloser Ausstieg :1681 (oben) |
| **B · Regionalquelle fällt aus, Ersatz greift** | echte Frames vom gröberen Modell; `_inca_unavailable_this_call` bleibt Instanzvariable, erreicht `NowcastResult` **nicht** | sieht aus wie voller Erfolg, nur gröber. `result.source` trägt die tatsächliche Quelle, aber nichts vergleicht sie gegen die erwartete |
| **C · Gewitter-Beiabruf scheitert bei echten Frames** | Niederschlag echt, **Gewitter-Information fehlt**; `convective_checked=False` (`radar_service.py:1129`) | **wirkt als geprüftes „kein Gewitter"** |

**Form C ist der schwerwiegende Fall.** `RadarFrame.is_convective` ist per Vorgabe `False` und
wird ohne Beiabruf nie gesetzt — aus „nicht geprüft" wird still „kein Gewitter". Das Feld
`convective_checked` existiert und hält den Unterschied fest, wird aber **nur** in
`format_now_text` (`radar_service.py:680`, der `/jetzt`-Pull-Pfad) gelesen. Im Alarmpfad:
**null Treffer** (nachgezählt in `trip_alert.py`).

Daran hängen drei Entscheidungen, alle in die abschwächende Richtung:

1. **`trip_alert.py:1735`** — `if _briefing_announced and not result.is_convective and not
   _overtaking: … continue`. Der Sicherheits-Override aus #883 („konvektive Gefahr durchbricht
   die Briefing-Unterdrückung") feuert nicht, weil die Prüfung ausfiel. **Ein Gewitteralarm
   wird auf Grundlage einer nie stattgefundenen Prüfung unterdrückt** — wörtlich ein Ausfall,
   der als Entwarnung wirkt.
2. **`trip_alert.py:1577`** — `urgency_from_radar(is_convective=…)`: `True` ergibt immer `HIGH`.
   Ohne Prüfung bleibt die Dringlichkeit niedriger, und damit entfällt auch das Recht auf den
   Eskalations-Durchbruch am Tagesbudget (S3b, berührt D-3).
3. **`trip_alert.py:1917/2042`** — `resolve_hazard_class()` bestimmt die Ereignis-Identität;
   eine falsche Klasse verschiebt Entdopplung und Ereigniszuordnung.

**Form B** bleibt bewusst außen vor: dort liegen echte Messwerte vor, die Aussage ist wahr, nur
gröber aufgelöst. Das ist der von ADR-0018 ausdrücklich gewollte Zustand („beste verfügbare
Daten statt Totalausfall"), sichtbar über `result.source`. Notiert als Nebenbefund.

**Räumliche Lücken** (No-Data-Pixel am Rand der Abdeckung) werden in
`providers/brightsky.py:90-120` als ganzer Zeitpunkt übersprungen, nicht als 0 mm gewertet —
die sichere Richtung. Fehlen dadurch *alle* Frames, mündet der Fall in Form A.

## Zielbild

`result.data_unavailable` **vor** dem `radar_alert_due()`-Aufruf abfragen; bei True ein eigener
Zweig mit `_protokolliere_radar_unterdrueckung(...)` und neuem, eigenständigem Grund-Code,
statt den stummen Ausstieg zu erben. Die Auslöseregeln für den echten Trockenfall bleiben
unangetastet.

**Kein neuer Alarm.** Das Issue schließt „neue Alarmarten" ausdrücklich aus, und ein Alarm
„konnte nicht prüfen" alle 15 Minuten wäre Lärm. Szenario 6 verlangt wörtlich *„als Ausfall
behandeln und protokollieren"* — Buchführung, nicht Meldung.

## Vorbild im Bestand: #2050 S3b (`d6af0666`, PR #2101, gestern live)

Dreiteiliges Muster, das S4a spiegelt:

1. neue `REASON_*`-Konstante in `alert_log.py` **mit Kommentar, warum eigenständig** statt einen
   bestehenden Grund mitzubenutzen;
2. Aufruf von `_protokolliere_radar_unterdrueckung(...)` unmittelbar vor dem `continue`;
3. `tests/tdd/test_alert_suppression_reason.py` fährt jeden Fall über die **echte**
   Auslöseentscheidung (kein Mock), prüft über `read_undelivered()` genau einen Vorfall mit
   genau diesem Grund — **plus Kontroll-Lauf ohne Ausfall, der tatsächlich versendet**
   (Positivkontrolle).

Zweites Vorbild, gleiche Frage, andere Quelle: **#1348** trennt für amtliche Warnungen
„keine Warnungen" von „nicht abrufbar" (`get_official_alerts_with_status()`), PO-Entscheid
2026-07-23 **streng**: eine ausgefallene abdeckende Quelle genügt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py:1343-2051` | Radar-Alarmblock; Eingriffsstellen :1554-1560 und :1680-1681 |
| `src/services/trip_alert.py:147-158` | `radar_alert_due()` — hier verschmelzen „trocken" und „keine Daten" |
| `src/services/trip_alert.py:1296-1319` | `_protokolliere_radar_unterdrueckung()` — fertiger Schreibweg |
| `src/services/radar_service.py:993-1003` | Bildung von `data_unavailable` |
| `src/services/alert_log.py:52-74` | Grund-Register; `REASON_DATA_UNAVAILABLE` fehlt |
| `src/services/alert_log.py:516` | `append_suppressed_entry` — `gate_reason` ist Pflicht (leer ⇒ `ValueError`) |
| `src/output/renderers/email/undelivered_hint.py:48-77` | Deutsche Beschriftung + failed/withheld-Einordnung — **für einen neuen Grund zwingend zu ergänzen**, sonst zeigt die Mail den rohen Code |
| `src/services/compare_radar_alert.py:447` | identische Stelle im Ortsvergleich (Paritätsfrage, s. u.) |
| `tests/helpers/alarm_pruefstrecke.py:136-166` | Prüfstrecke aus S1; `lauf(at=…, zweig="radar", radar_service=…)` — DI-Seam vorhanden |
| `tests/tdd/test_radar_cooldown_overtake.py`, `tests/tdd/test_nowcast_suppression_logging.py` | Vorlagen: gestubbter Radar-Service mit vorgegebenem `NowcastResult` durch den echten Pfad |

## Dependencies

- **Upstream:** `NowcastResult.data_unavailable` (bestehend, unverändert).
- **Downstream:** `alert_log.json` (`get_data_dir(user_id)`) → `read_undelivered()` →
  E-Mail-Briefing-Block „FEHLGESCHLAGEN / ZURÜCKGEHALTEN".
- **Go:** `internal/store/log.go:48-56` liest nur `entity_id, entity_type, sent_at,
  changes_count, severity` und ausschließlich die Liste `entries` — ein neuer Grund in
  `not_delivered` ist für Go **unsichtbar und damit additiv unkritisch**.

## Risks & Considerations

1. **Flut-Sorge ist unbegründet, aber der Renderer braucht Pflege.** Drei Bremsen greifen
   bereits (Zeitfilter `since=last_briefing_at`, 2-Min-Dedup, Gruppierung mit
   `MAX_LINES_PER_BLOCK = 5`) — 96 Ausfallläufe eines Tages werden **eine** Zeile `(96×)`.
   Aber: ein **neuer** Grund ohne Eintrag in `_REASON_LABELS` erscheint als roher Code.
   Einordnung gehört in den Block **„FEHLGESCHLAGEN"** — „ZURÜCKGEHALTEN — so hast du es
   eingestellt" wäre schlicht falsch, ein Quellenausfall ist keine Nutzereinstellung.
2. **Es gibt keinen stillen Protokollweg.** `read_undelivered()` liest beide Listen; einzig
   `REASON_CHANNEL_DISABLED` wird herausgefiltert. Wer nicht sichtbar buchen will, braucht eine
   eigene Diagnosespur — hier ist Sichtbarkeit aber gerade der Zweck.
3. **Nachweisfalle (gemessen beim S3b-Deploy):** Für den Mail-Nachweis muss die Reihenfolge
   *Briefing → Eintrag → zweites Briefing* sein; der Anker `last_briefing_at` macht den naiven
   Weg blind. Der Fehlversuch ist die Positivkontrolle.
4. **Doppelter Eingriffspunkt.** Fail-soft-Leerergebnis (:1681) und geworfene Ausnahme (:1560)
   sind fachlich derselbe Fall. Nur einen zu behandeln ließe die Hälfte still.
5. **Parität Trip ↔ Ortsvergleich.** Die identische Stelle existiert in
   `compare_radar_alert.py:447`. Das Schwester-Slice S3b hat beide Flächen zusammen bedient
   (`compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py` im selben
   Commit) — das ist der etablierte Zuschnitt für Unterdrückungsgründe und keine
   Ortsvergleich-Feature-Arbeit. Entscheidung: **mitnehmen**, spiegelbildlich, ohne eigene
   Compare-Mechanik.
6. **Revier.** Die Parallelsitzung liefert #2050 S3c in `trip_alert.py:306-570` +
   `alert_gate.py`; abgesprochen ist, dass ich `check_radar_alerts` (:1343 ff.) halte und sie
   dort nicht hineingreift. Ihr AC-11 ruft `check_radar_alerts` testweise auf und wurde
   ausdrücklich auf einen Pfad **ohne** Teilausfall gesetzt.

## Nebenbefunde (nicht in dieser Scheibe)

- **Amtlicher Zweig:** `check_official_alert_triggers` (:2263) ruft `get_official_alerts_for_location`
  — den Alt-Wrapper **ohne** Ausfall-Status — und verschluckt den Fehlschlag mit `logger.warning`
  (:2268). Die #1348-Unterscheidung nutzt heute nur das Briefing, nicht der Alarmpfad. Derselbe
  B-4-Verstoß, andere Quelle → Kandidat für S4b.
- **`has_error`-Segmente** werden im amtlichen Zweig still übersprungen (:2243).
- **Abweichungs-Zweig:** `suppressed_reason="alert_state_dedup"` (:456-471) läuft nur in
  `logger.debug`, während der Radarzweig denselben Fall protokolliert — verbliebene D-2-Lücke aus
  S3b, von der Parallelsitzung bewusst nicht mitgenommen, Triage → #1199.
