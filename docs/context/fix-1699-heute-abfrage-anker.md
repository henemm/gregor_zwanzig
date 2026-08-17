# Context: fix-1699-heute-abfrage-anker

Issue: [#1699](https://github.com/henemm/gregor_zwanzig/issues/1699) — „Abfrage /heute setzt den
Alarm-Vergleichspunkt neu — und hebelt damit den Datumsschutz aus #1661 teilweise aus"

## Request Summary

Eine reine Abfrage über den Inbound-Kanal schreibt einen Wetter-Snapshot direkt in die
Ankerdatei und umgeht dabei den geteilten Baustein `write_anchor_and_reset_memory()`, der bei
On-Demand-Abrufen bewusst aussteigt (#1007-Invariante). Seit #1661 besteht dieser
selbstgeschriebene Anker die Datumsprüfung anstandslos, obwohl ihm kein Briefing zugrunde liegt.

## 🔴 Abweichung vom Issue-Wortlaut (am Code belegt)

Das Issue benennt `/heute` als Auslöser. Das trifft **nicht** zu — der Auslöser ist eine
andere Gruppe von Abfragen. Belege:

| Behauptung im Issue | Befund am Stand `d40b61a0` |
|---|---|
| `/heute` schreibt den Snapshot direkt | **Nein.** `trip_command_processor.py:526-529` fängt `heute`/`morgen` mit einem `return self._trigger_on_demand(...)` ab — **vor** dem Timeline-Setup. Der Fallback in Zeile 536 wird für diese beiden Kommandos nie erreicht. |
| Der On-Demand-Pfad umgeht `write_anchor_and_reset_memory()` | **Nein, für `/heute` nicht.** `send_on_demand_report()` setzt `on_demand=True` (`trip_report_scheduler.py:1124`), der Baustein steigt bei `on_demand=True` aus (`alert_briefing_anchor.py:291-292`), und `_write_briefing_anchor()` ist ausschließlich dessen Callback (`trip_report_scheduler.py:1505-1525`). Dieser Pfad ist read-only. |
| Zeilenangabe `:294-303` | Verschoben auf `:278-310` (Funktion `_fetch_and_save_snapshot`). |

**Tatsächlich betroffen** sind die übrigen Abfrage-Kommandos, die den Fallback in Zeile 536
erreichen: `glance`, `heute_gewitter`, `timeline_heute` und die weiteren `_QUERY_KEYS`
(`trip_command_processor.py:101-102`).

**Zusätzliche Vorbedingung:** Der Fallback greift nur bei `not timeline.available`, und das ist
laut `weather_extractor.py:84-92` genau dann der Fall, wenn **gar kein** undatierter Snapshot
existiert. Der Bug tritt also nicht bei jeder Abfrage auf, sondern nur, wenn kein Anker da ist.

**Die Wirkung ist dadurch nicht kleiner, sondern anders:** Ohne Snapshot hätte der Alarm den
Grund `missing` protokolliert und geschwiegen (`trip_alert.py:627-629`, `:693-695`). Nach einer
solchen Abfrage existiert ein Anker mit `target_date = heute`, der die #1661-Prüfung besteht
(`trip_alert.py:633-634`). Der Vergleichspunkt wird also nicht *verschoben* — er wird
**erfunden**, ohne dass je ein Briefing lief. Ab dann gilt der Zustand zum Abfragezeitpunkt als
Normalzustand, und der Nutzer kann dem Alarm nicht ansehen, dass ihm kein Briefing zugrunde liegt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py:278-310` | `_fetch_and_save_snapshot` — schreibt `WeatherSnapshotService.save()` direkt (Zeile 308). Der Fehlerherd. |
| `src/services/trip_command_processor.py:503-537` | `_handle_query` — Verzweigung; Zeile 526-529 (sauberer Pfad) vs. Zeile 536 (Fallback). |
| `src/services/trip_command_processor.py:101-102` | `_QUERY_KEYS` — die Menge der Abfragen, die den Fallback erreichen können. |
| `src/services/alert_briefing_anchor.py:254-292` | `write_anchor_and_reset_memory()` mit `on_demand`-Aussteig (Zeile 291-292); Aufrufer nur `trip_report_scheduler.py:1515` und `scheduler_dispatch_service.py:524`. |
| `src/services/alert_briefing_anchor.py:56-96` | `record_alert_anchor_rejected()` — Diagnose nach `diagnostics/alert_anchor_rejected.jsonl`. |
| `src/services/trip_alert.py:616-663` | Datumsprüfung aus #1661; Ablehnungsgründe `wrong_day`, `too_old`. |
| `src/services/trip_alert.py:666-695` | `_report_missing_anchor()` — Grund `missing`, nur bei laufender Tour. |
| `src/services/weather_snapshot.py:54-116` | `save()` / `save_dated()` — schreibt `trip_id`, `target_date`, `snapshot_at`, `provider`, `segments`. **Kein Herkunftsfeld vorhanden.** |
| `src/services/weather_extractor.py:79-92` | `timeline()` — `available=False` genau bei fehlendem undatiertem Snapshot. |
| `src/app/loader.py:1165-1167` | `get_snapshots_dir()` → `{data_dir}/users/{user_id}/weather_snapshots/`. |

## Existing Patterns

- **Ein geteilter Baustein für Anker + Melde-Gedächtnis.** `write_anchor_and_reset_memory()`
  wird von Trip- und Ortsvergleich-Seite gemeinsam benutzt; der Kommentar bei
  `trip_report_scheduler.py:1490-1494` sagt ausdrücklich, dass zwei Fassungen auseinanderlaufen
  würden. Eine Lösung, die am Prüfling vorbei einen zweiten Schreibweg baut, verstößt gegen dieses Muster.
- **Ablehnungsgründe als Strings mit Diagnose-Zeile.** `wrong_day`, `too_old`, `missing` — ein
  vierter Grund fügt sich in ein bestehendes Muster ein (Lösungsweg (b) aus dem Issue).
- **Snapshot-Schema ist additiv erweiterbar.** `target_date` kam mit #1661 additiv dazu;
  `load_target_date()` (`weather_snapshot.py:168-194`) liest gezielt ein einzelnes Feld, ohne den
  Rest zu deserialisieren. Ein Herkunftsfeld ließe sich analog nachziehen.
- **Altbestand ohne neues Feld muss weiterlaufen** — Muster aus AC-10 von #1661.

## Dependencies

- **Upstream:** `WeatherSnapshotService`, `TripReportSchedulerService._convert_trip_to_segments`
  / `._fetch_weather`, `WeatherExtractor.timeline`.
- **Downstream:** `TripAlertService` (Anker-Auswahl und Datumsprüfung), alle Anzeigepfade der
  Abfrage-Kommandos (`_fmt_glance`, `_fmt_gewitter`, `_fmt_timeline`), die Diagnose-Auswertung.

## Existing Specs

- `docs/specs/modules/fix_1661_anker_vom_falschen_tag.md` — AC-1 bis AC-16. Der Abschnitt
  „Nicht in dieser Scheibe" benennt genau diesen Punkt wörtlich als bewusst nicht behandelt:
  „**#1007-Abweichung in `trip_command_processor.py:294-303`** — On-Demand-Pfad schreibt Snapshot
  direkt und umgeht `write_anchor_and_reset_memory()`, überschreibt undatierten Trip-Anker."
- `docs/adr/0009-alerts-als-abweichungs-waechter.md:18-20` — „Alerts sind **Abweichungs-Wächter**:
  Sie melden, wenn der aktuelle Nowcast **deutlich vom zuletzt versendeten Briefing abweicht**".
  Ein Anker ohne Briefing hat unter dieser Entscheidung keine Grundlage.
- #1007-Invariante im Wortlaut: `trip_report_scheduler.py:1495-1501` — „On-Demand-Abruf
  (heute/morgen-Kommando) ist read-only gegenüber Snapshot-/Alert-Zustand — Baseline bleibt das
  letzte reguläre Briefing."

## Testbestand

| Datei | Was sie bewacht |
|---|---|
| `tests/tdd/test_alert_anchor_day_guard.py` | AC-1 bis AC-15 aus #1661: Verwerfen bei falschem Tag, 26-h-Altersnetz, Diagnose-Einträge, laufende vs. zukünftige Tour. |
| `tests/tdd/test_trip_briefing_anchor_unchanged.py` | `test_ac27_ad_hoc_abruf_laesst_anker_und_gedaechtnis_unberuehrt` — bewacht **den sauberen `/heute`-Pfad**, nicht den Fallback. Erklärt, warum der Bug bisher unentdeckt blieb. |
| `tests/tdd/test_compare_anchor_target_date.py` | AC-7 bis AC-10 (Compare-Seite). |
| `tests/tdd/test_compare_alert_day_window.py:180-350` | Szenario-Klasse mit `versand()` / `lauf()` / `anker()` — spielt „Briefing → Vorhersage ändert sich → Alarm prüft" netzfrei über den echten Code durch. Wird bereits von `test_compare_anchor_target_date.py` wiederverwendet. Kandidat für den RED-Test, sofern sie sich auf die Trip-Seite übertragen lässt. |
| `tests/integration/test_weather_snapshot.py`, `tests/integration/test_alert_snapshot_pipeline.py` | Snapshot-Persistenz und -Pipeline. |

## Risks & Considerations

- **Gegenrichtung des Fehlers.** Ein zu strenges Verwerfen macht aus „Alarm gegen falsche Basis"
  ein „gar kein Alarm". Auf der Tour sind beide Zustände von außen nicht unterscheidbar — die
  Lösung muss den Unterschied in der Diagnose sichtbar machen, nicht nur im Verhalten.
- **Anzeige darf nicht kaputtgehen.** AC-6 aus #1661 verlangt, dass die Abfragepfade ihre Daten
  weiterhin zeigen. Nimmt man den Fetch ersatzlos heraus, antworten `glance` & Co. ohne Briefing
  gar nicht mehr. Der Lösungsweg muss Anzeige und Ankerwirkung trennen.
- **Zweiter Ablageort vs. Herkunftsfeld.** Weg (a) aus dem Issue braucht ein neues Verzeichnis
  (Datenschema-Änderung, Backup-Hook, Migration); Weg (b) braucht ein additives Feld im
  bestehenden Schema plus einen vierten Ablehnungsgrund. Weg (b) fügt sich sichtbar besser in die
  vorhandenen Muster — **die Entscheidung gehört aber in die Analyse-Phase, nicht hierher.**
- **Altbestand.** Bereits geschriebene Snapshots tragen kein Herkunftsfeld. Ob ein fehlendes Feld
  als „briefing-gestützt" (rückwärtskompatibel, aber lässt den Bug für Altdateien bestehen) oder
  als „unbekannt" (strenger, riskiert stille Alarm-Unterdrückung nach dem Deploy) gilt, ist eine
  Produktentscheidung.
- **Nebenaspekt aus dem Issue:** `_fetch_and_save_snapshot` legt Etappen von heute **und** morgen
  unter `target_date = today` ab (`trip_command_processor.py:301-303`). Für den Alarmvergleich
  heute folgenlos, aber das Feld beschreibt den Dateiinhalt nicht vollständig.
- **Häufigkeit — geklärt, siehe Analyse unten.** Der Zustand „kein undatierter Snapshot" ist ein
  regelmäßiger Betriebszustand, kein Randfall.

---

## Analysis

### Type

**Bug.** Nutzersichtbares Fehlverhalten am Alarm-Pfad; kein neues Verhalten gewünscht, sondern
eine dokumentierte Invariante (#1007) wiederherzustellen.

### Wie oft tritt der Fehlerzustand ein?

Der fehlerhafte Zweig greift nur bei `not timeline.available`, also bei fehlendem **oder leerem**
undatiertem Snapshot. Das ist **regelmäßiger Betriebszustand**, nicht Randfall — drei belegte Wege:

1. **Neu angelegter Trip.** Das Anlegen schreibt keinen Snapshot (`loader.py` `save_trip` speichert
   nur Metadaten); er entsteht erst beim ersten regulären Briefing. Jede Abfrage davor trifft den Zweig.
2. **Nach `ruhetag` oder `startdatum`.** Beide Kommandos löschen den undatierten Anker gezielt
   (`trip_command_processor.py:1086`, `:1162` → `_delete_snapshot`, `:1416-1424`). Das Löschen ist
   Absicht — der alte Anker passt nach der Verschiebung nicht mehr. Jede Abfrage bis zum nächsten
   Briefing erzeugt danach einen Pseudo-Anker.
3. **Leerer Snapshot nach fehlgeschlagenem Wetterabruf.** Liefert `_fetch_weather()` eine leere
   Liste, wird `segments: []` gespeichert; `load()` gibt `[]` zurück und `available` ist ebenfalls `False`.

### 🔴 Der Fix muss zwischen zwei Alarm-Pfaden unterscheiden

`trip_alert.py:606-664` (`_get_cached_weather`) bedient **zwei** Aufrufer über den Schalter
`tagesgleicher_anker_noetig`:

| Zeile | Pfad | Bedeutung des Snapshots |
|---|---|---|
| `:630-632` | `if not tagesgleicher_anker_noetig: return undated` | **Amtliche Warnungen** — der Snapshot liefert nur die **Geometrie** (wo ist die Tour). Die Datumsprüfung aus #1661 wird hier bewusst übersprungen. |
| `:633-664` | Datums- und Altersprüfung, Ablehnungsgründe | **Abweichungs-Alarm** — der Snapshot ist die **Vergleichsbasis** (ADR-0009). |

**Daraus folgt zwingend:** Die neue Herkunftsprüfung darf **ausschließlich** in den zweiten Pfad,
also **nach** Zeile 632. Ein nicht briefing-gestützter Snapshot hat dieselbe Geometrie wie ein
echter — für amtliche Warnungen ist er einwandfrei. Läge die Prüfung vor Zeile 630, würde der Fix
**amtliche Warnungen unterdrücken** und damit in genau die Gegenrichtung kippen, die dieses
Ticket verhindern soll (#1701: Alarme müssen alle Kanäle erreichen).

Zweite Vorrangregel, die den Wirkbereich einschränkt: `:611-613` liest zuerst `load_dated(trip.id,
today)`. Existiert ein **datierter** Snapshot von heute, wird der undatierte nie angesehen. Der
Abfrage-Pfad schreibt nur `save()` (undatiert), nie `save_dated()` — der Bug kann also nur wirken,
wenn auch kein datierter Snapshot für heute existiert. Das deckt sich mit den drei Szenarien oben.

### Affected Files (with changes)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/weather_snapshot.py` | MODIFY | `save()` bekommt additiven Parameter `briefing_backed: bool = True`, schreibt das Feld ins JSON; neue schlanke Lesemethode analog `load_target_date()` (`:168-194`), die nur dieses eine Feld liest und bei fehlendem Feld `True` liefert. |
| `src/services/trip_command_processor.py` | MODIFY | Zeile 308: einziger Aufrufer, der `briefing_backed=False` setzt. |
| `src/services/trip_alert.py` | MODIFY | Neue Prüfung **nach** Zeile 632, vor der Datumsprüfung; neuer Ablehnungsgrund plus `record_alert_anchor_rejected(...)`. |
| `src/services/alert_briefing_anchor.py` | MODIFY (Doku) | Vierter Ablehnungsgrund im Docstring `:64-66`; die Diagnose-Funktion selbst nimmt jeden String entgegen, kein Code-Eingriff. |
| `tests/tdd/test_alert_anchor_day_guard.py` | MODIFY | Additive Testfälle im bestehenden Wächter. |
| `tests/integration/test_weather_snapshot.py` | MODIFY | Roundtrip + Altbestand-Default. |

### Scope Assessment

- Dateien: 4 Quellcode + 2 Testdateien
- Geschätzte LoC: Quellcode ~35–40, Tests ~120–160
- **Vorbehalt:** Projekterfahrung sagt, der Nachweis kostet mehr als der Mechanismus. Bei der
  oberen Schätzung plus dem Test für die Pfadtrennung (amtliche Warnungen bleiben unberührt) kann
  das 250-LoC-Limit knapp werden. Nicht vorab überschreiben — erst messen.
- Risk Level: **MEDIUM.** Der Eingriff selbst ist klein, aber er sitzt im Alarm-Pfad, und die
  Fehlerrichtung „zu streng" unterdrückt Alarme still.

### Technical Approach

**Empfohlen: Weg (b) aus dem Issue** — Herkunftsmerkmal am Snapshot plus vierter Ablehnungsgrund.

Begründung gegen Weg (a) (getrennter Anzeige-Cache): Ein zweiter Ablageort baut genau den zweiten
Schreibweg, vor dem `alert_briefing_anchor.py:1-23` und `trip_report_scheduler.py:1490-1494`
ausdrücklich warnen („zwei Fassungen dürften auseinanderlaufen"). Er bräuchte zusätzlich eine
eigene Alterungsregel und eine Quellenauswahl in `WeatherExtractor.timeline()`, die jeder künftige
Schreiber erneut richtig treffen muss. Vor allem aber erzeugt Weg (a) **keine Diagnose-Spur**: der
Alarm sieht den Cache nie und meldet weiterhin nur `missing` — der Unterschied zwischen „es gab nie
einen Anker" und „ein Anker wurde als nicht vertrauenswürdig verworfen" bliebe unsichtbar.

Weg (b) folgt dagegen dem `target_date`-Präzedenzfall aus #1661: additives Feld, schlanke eigene
Lesemethode, bestehende Ablehnungsmechanik mitbenutzt. Schätzung ~35–40 LoC Quellcode.

**Datenschema:** `save()` (`weather_snapshot.py:61-86`) baut das Dict vollständig neu und ersetzt
die Datei — es gibt keinen Lese-Änderungs-Zyklus, in dem fremde Felder verloren gehen könnten. Die
Read-Modify-Write-Pflicht des Projekts greift hier nicht. Ein Roundtrip- und ein
Altbestands-Test sind trotzdem angezeigt (Muster wie bei `target_date`).

### Open Questions

- [ ] **Altbestand-Auslegung (Produktentscheidung, gehört in die Spec-Freigabe).** Empfehlung:
      fehlendes Feld = „briefing-gestützt". Die Gegenoption („unbekannt ⇒ verwerfen") würde beim
      ersten Alarmlauf nach dem Deploy **jeden** vor dem Deploy legitim geschriebenen Anker
      verwerfen — also flächendeckend Alarme unterdrücken, bis das nächste reguläre Briefing läuft.
      Preis der Empfehlung: durch den Bug bereits entstandene Pseudo-Anker bleiben gültig, bis das
      nächste Briefing sie überschreibt (bei laufenden Touren binnen Stunden; bei noch nicht
      gestarteten Touren möglicherweise bis zum Tourstart).
- [ ] **Nebenaspekt `target_date` für heute+morgen** (`trip_command_processor.py:301-303`):
      Empfehlung, ihn **nicht** in diese Scheibe zu nehmen — eigenständiges Korrektheitsproblem,
      für den Alarm nach diesem Fix ohnehin gegenstandslos (der Anker wird verworfen, bevor sein
      `target_date` zählt), und er würde das LoC-Budget zusätzlich belasten. → eigenes Issue.
