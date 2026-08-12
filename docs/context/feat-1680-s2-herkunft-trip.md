<!-- Issue #1680, Scheibe 2 (Trip-Seite). Vorgänger: Scheibe 1 (Ortsvergleich),
     live seit 2026-08-12, Spec docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md.
     Bezug: Epic #1419 Rang 4, Entscheidung E1. -->

# Kontext: Herkunft der Gewitterstufe auf der Trip-Seite (#1680 Scheibe 2)

## Zusammenfassung der Anforderung

Die fusionierte Gewitterstufe soll auch im Trip-Briefing sichtbar tragen, **welches
Signal** sie erreicht hat — so wie es der Ortsvergleich seit Scheibe 1 tut
(`leicht · CAPE`). PO-Entscheid zum Umfang dieser Scheibe (2026-08-12): **zwei
Ausgabeorte** — die **Kurzzusammenfassung** in der Trip-Mail und die Antwort auf das
**GEWITTER-Kommando** — plus der **geteilte Aggregations-Helfer**, der die Regel
„Vereinigung der Träger der Maximal-Segmente" einmal definiert.

Fortbestehende PO-Entscheidungen aus Scheibe 1 (2026-08-11), unverändert gültig:

| Frage | Entscheidung |
|---|---|
| Auslegung | **(ii) alle tragenden Signale** — jede Zutat, die die gezeigte Stufe erreicht. Kein Gewinner wird gekürt, die interne `if`-Reihenfolge der Fusion wird damit **keine** Produktaussage |
| Kanäle | **E-Mail und Telegram ja · SMS und Premium-SMS ausdrücklich OHNE Herkunft** — aktiv abzuwählen, nicht stillschweigend auszulassen |

## Ausgangslage: was Scheibe 1 bereitgestellt hat

Alle Bausteine existieren und sind produktiv im Einsatz:

| Baustein | Ort | Rolle |
|---|---|---|
| `thunder_signal_carriers()` | `src/output/metric_format.py` | ermittelt je Stunde die tragenden Signale |
| `THUNDER_SIGNAL_LABEL_DE` | `src/output/metric_format.py` | deutscher Wortkatalog (`CAPE`, `Blitzpotenzial`, …) |
| `_signal_levels()` | `src/output/metric_format.py` | aus der Fusion herausgelöst, zeichengleich |
| `ForecastDataPoint.thunder_level_signals` | `src/app/models.py:204` | `list[str]`, providerseitig befüllt (`src/providers/thunder_enrichment.py:151`) |
| `SegmentWeatherSummary.thunder_level_max_signals` | `src/app/models.py:430` | `list[str]`, befüllt in `src/services/weather_metrics.py:462` |
| `_compute_thunder_level_signals()` | `src/services/weather_metrics.py:616-642` | bildet die Vereinigung je Level-1-Segment |

Die Fusion hat **vier** Zutaten: Wettercode, Blitzdichte (nur Frankreich), CAPE
(CIN-gedämpft), Blitzpotenzial LPI (nicht Frankreich). `sdi_2` (Superzellen) ist
**keine** Zutat — das Issue-Beispiel „hoch, Blitzpotenzial+Superzelle" ist am Code
nicht baubar.

**Kein Trip-Lesepunkt existiert heute.** Einzige Lesestelle von
`thunder_level_max_signals` ist `src/output/renderers/email/compare_html.py:694`
(`loc_thunder_signals()`), also Ortsvergleich.

## Der zentrale Befund dieser Scheibe

Die S1-Spec beschrieb als Vorbedingung **einen** ungelösten Aggregationsweg
(Known Limitation 7: `aggregate_stage()` kennt `union_of_max_carriers` nicht und
fällt auf `values[0]` zurück). Die Messung zeigt: es sind **drei** Wege, und alle
drei rechnen die Tages-/Etappenstufe selbst.

| # | Weg | Ort | Kennt Träger? |
|---|---|---|---|
| 1 | `aggregate_stage()` | `src/services/weather_metrics.py:1164-1267` | nein — kein Dispatch-Zweig für `union_of_max_carriers`, generischer `else` (Z. 1261-1262) liefert `values[0]`, also die Trägerliste des **ersten** Segments |
| 2 | `_aggregate_day()` | `src/services/trip_command_processor.py:804-830` | nein — eigene MAX-Schleife `max(thunder_vals, key=thunder_ordinal)` über `p.metrics.thunder_level_max`, Träger kommen dort gar nicht vor |
| 3 | `_format_thunder()` | `src/output/renderers/compact_summary.py:567-601` | arbeitet direkt auf den Stundenwerten (`dp.thunder_level`), bildet **gar kein** Aggregat |

Die Regel `union_of_max_carriers` ist an `src/services/weather_metrics.py:478`
**deklariert**, aber an keiner Stelle **ausgewertet**.

⇒ Wer die Herkunft auf die Trip-Seite bringt, muss die Regel **einmal** als
geteilten Helfer bauen und an den betroffenen Wegen anschließen. Drei
Eigenimplementierungen wären genau die Fehlerklasse, gegen die #1480 läuft
(lokale Kopien der Gewitter-Stufenskala, neun Fundstellen).

Warum `aggregate_stage()` trotzdem mitzulösen ist, obwohl die beiden gewählten
Ausgabeorte ihn umgehen: er hat **drei** Verbraucher —
`compact_summary.py:263` (`_aggregate()`), `src/services/stage_weather.py:112`
(Go-Cockpit-Spiegel) und `src/services/trip_report_scheduler.py:2020`
(Mehrtages-Ausblick). Sobald einer davon die Trägerliste liest, wird der
`values[0]`-Rückfall zu einem echten Fehler: die Stufe entstünde per MAX über
alle Segmente, die Herkunft käme aus dem ersten. Präzedenz derselben Fehlerklasse
im selben `else`-Zweig: #1592 F003 (`cape_model_id`).

## Andockplatz an den beiden Ausgabeorten

An beiden liegt das Suffix-Muster aus dem Hagel-Kennzeichen (#1475) bereits frei —
derselbe Renderweg wie in Scheibe 1 (`f"{label} · {note}"`):

| Ausgabeort | Datei:Zeile | heutige Ausgabe | vorhandener Platz |
|---|---|---|---|
| Kurzzusammenfassung | `src/output/renderers/compact_summary.py:596-601` | `Gewitter möglich 14:00–17:00` | `f"{text} · {note}"` mit `format_hail_note(hail_priority(...))` |
| GEWITTER-Kommando | `src/services/trip_command_processor.py:874-881` | `⛈ Gewitter heute (13.08.): leicht` | `suffix = f" · {hail_note}" if hail_note else ""` |

Bemerkenswert: die **Kurzzusammenfassung nennt gar keine Stufe**, nur das
Zeitfenster. Die Herkunft beantwortet dort „worauf beruht diese Gewittermeldung",
nicht „worauf beruht diese Stufe". Das GEWITTER-Kommando nennt die Stufe als Wort
(`_THUNDER_LABEL`).

## Vollständige Landkarte der Trip-Ausgabeorte (Abgrenzung)

Gemessen, damit die Abgrenzung dieser Scheibe belegt ist statt geschätzt:

| Ausgabeort | Datei:Zeile | Stufe als Wort? | in dieser Scheibe |
|---|---|---|---|
| Kurzzusammenfassung | `compact_summary.py:567-601` | nein (nur Zeitfenster) | **ja** |
| GEWITTER-Kommando | `trip_command_processor.py:863-881` | ja | **ja** |
| Kommando-Timeline je Wegpunkt | `trip_command_processor.py:903-913` | ja | nein — kompakte Zeile ohne Suffix-Platz |
| Tages-Aggregatzeile (`_fmt_day_agg`) | `trip_command_processor.py:832-843` | ja | nein |
| Mehrtages-Ausblick, Spalte „Gew" | `email/outlook.py:174-298`, `353-403`, `453-537` | ja | nein — Token-Pfad mit getrenntem Tag-/Nachtanteil (#1653), **geteilt mit Compare** |
| Gewitter-Vorschau (Ersatz für Ausblick) | `email/html.py:1307-1329`, `email/plain.py:307-332` | ja | nein |
| Pill „Metriken-Überblick" | `email/helpers.py:1713-1757` | ja | nein — **geteilt mit Compare** |
| Stundentabelle (Zellwert + Ampelfarbe) | `trip_report.py:597-601`, `email/html.py:814-825` | nein | nein |
| Risiko-Badges der RiskEngine | `trip_report.py:902-908` | ja, aber **eigene Skala** (`RiskLevel`, nicht `ThunderLevel`) | nein |
| SMS-Token `TH:` / `TH+:` | `sms_trip.py:412-417`, `670-702` | nein (Zahlenwert) | **ausgeschlossen** (PO: kein SMS) |
| Alarm-Renderer | `alert/render.py:39-53`, `324-390` | nein — gibt die rohe Ordinalzahl 0–3 aus | nein |

Hinweis zur Dateizuordnung: `email/html.py`, `email/plain.py` und `email/compact.py`
sind faktisch Trip-only (nur über `render_email()` ← `trip_report.py:49/200`
erreichbar). `email/helpers.py` und `email/outlook.py` sind dagegen **mit dem
Ortsvergleich geteilt** — eine Änderung dort erschiene sofort in beiden Flächen.

## Verwandte Spezifikationen und Entscheidungen

| Dokument | Bezug |
|---|---|
| `docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md` | Vorgänger-Scheibe, 12 ACs, Known Limitations 3 und 7 |
| `docs/context/feat-1680-thunder-herkunft.md` | Analyse vor Scheibe 1 (Auslegungsfrage, zwei gemessen widerlegte Irrtümer) |
| `docs/features/gewitter-gesamtkonzept.md` | Epic #1419, Rang 4 („Herkunft mitführen"), Abschnitt 4.5 Option c |
| `docs/reference/metric_output_matrix.md` | Zeile 94 führt den Herkunfts-Zusatz als Compare-only; diese Scheibe ergänzt die Trip-Zeilen |
| ADR-0025 | Eine Gewitter-Quelle für alle Briefing-Kanäle — diese Scheibe ergänzt die gemeinsame Fusion additiv, baut keine zweite |
| ADR-0007 | Daten statt Empfehlungen — die Herkunft nennt die Zutat, gibt keine Handlungsanweisung |
| ADR-0048 | Modellabhängige Schwellen; das Label sagt nichts über die Güte der Eichung aus |

## Risiken und Fallstricke

1. 🔴 **Die Voraussetzung des Musters gilt nicht automatisch** — die Lehre aus
   AC-12 in Scheibe 1. Dort hätte die Zeile beinahe eine Stufe aus dem Engine-Lauf
   mit einer Herkunft aus einer zweiten, unabhängigen Rechnung gepaart. Für jeden
   Ausgabeort dieser Scheibe ist einzeln zu prüfen, ob gezeigte Stufe und
   Trägerliste **aus derselben Rechnung** stammen. Wo nicht: lieber keine
   Herkunft als eine, die zu einer anderen Zahl gehört.
2. 🔴 **Persistenz-Kante.** Das GEWITTER-Kommando antwortet aus einem
   gespeicherten Wetter-Snapshot („Kein Wetter-Snapshot verfügbar" als
   Fehlerfall). Ob `thunder_level_max_signals` dort überhaupt ankommt, ist die
   Vorabfrage dieser Scheibe — wird gerade gemessen. Zusätzlich gilt aus
   Scheibe 1: ein neues Feld MUSS `str` oder `list[str]` sein,
   `weather_snapshot.py:239,291` behandelt nur skalare Enums, und ein
   Serialisierungsfehler wird **still geschluckt** (`:85`, `:113`) — der gesamte
   Schnappschuss wäre weg (gebucht als #1405).
3. **Regelkopien.** Drei Aggregationswege, eine Regel — ohne geteilten Helfer
   entstehen Kopien (Fehlerklasse #1480).
4. **`aggregate_stage()` hat drei Verbraucher**, einer davon der Go-Cockpit-Spiegel
   (`stage_weather.py:112`). Ein neuer Dispatch-Zweig ändert dort das Verhalten mit.
5. **Kein Leck in die SMS.** In Scheibe 1 war die Annahme „Compare-SMS zeigt
   Gewitter gar nicht" **falsch** — `comparison.py:629` rendert es sehr wohl, und
   ein Suffix wäre automatisch in die SMS gelaufen, per GSM-7 zu `-` entstellt.
   Für die Trip-SMS ist derselbe Nachweis zu führen: der Ausschluss muss **aktiv**
   sein und geprüft werden.
6. **Commit-Gates.** `compact_summary.py` steht auf der Liste des
   `renderer_mail_gate.py` — der Commit blockiert ohne frischen
   `briefing_mail_validator.py`-Lauf und grüne `test_issue_811_mode_matrix.py`.

## Ergebnis der Vorabmessungen

### Beide Ausgabeorte sind bedienbar — die Zutat kommt an

**GEWITTER-Kommando (Snapshot-Pfad).** Der Weg trägt, weil beide Richtungen
generisch arbeiten statt mit gepflegten Feldlisten:

| Schritt | Ort | Befund |
|---|---|---|
| Laden | `src/services/weather_extractor.py:84,93` | `timeline()` lädt **ausschließlich** einen gespeicherten Snapshot; `TimelinePoint.metrics = seg.aggregated` reicht das ganze Objekt durch |
| Serialisieren | `src/services/weather_snapshot.py:229-243` | iteriert über `vars(summary)` — **keine Allowlist**; `list[str]` fällt in den generischen Zweig |
| Deserialisieren | `src/services/weather_snapshot.py:246-261` | `known_fields` kommt aus `dataclasses.fields()` — **dynamisch**, nicht hartcodiert |
| Stundenpunkte | `weather_snapshot.py:265-291`, `301-321` | dieselbe generische Mechanik für `thunder_level_signals` |

⇒ Es fehlt **nur die Konsumption**, kein Transport. `_aggregate_day()` liest das
Feld schlicht nicht und hat im Rückgabe-Dict keinen Schlüssel dafür.

**Kurzzusammenfassung (Frischdaten-Pfad).** Die Objekte stammen direkt aus dem
Provider-Abruf (`trip_report_scheduler.py:564,1096`), nicht aus dem Snapshot; der
Snapshot wird erst danach geschrieben (`:1300`). `enrich_thunder()` setzt das Feld
bereits im Provider (`src/providers/openmeteo.py:1204,1216-1218`), und
`build_day_window_points()` sammelt die Punkte **per Referenz** ohne Kopie
(`day_window.py:113-144`). ⇒ Feld kommt an.

### 🔴 Neuer Befund 1: `_merge_hour()` wählt die Herkunft willkürlich

`src/output/renderers/day_window.py:56-71`:

```python
base = max(dps, key=lambda dp: (thunder_ordinal(dp.thunder_level),
                                dp.precip_1h_mm or 0.0, dp.gust_kmh or 0.0))
return dataclasses.replace(
    base,
    thunder_level=max_thunder(dp.thunder_level for dp in dps),
    ...)
```

Die **Stufe** wird über alle Punkte der Stunde neu gebildet und ist kohärent
(`base` wird nach derselben Ordnung gewählt, die `max_thunder()` anwendet).
Die **Trägerliste** steht dagegen nicht in der Override-Liste und kommt
unverändert von `base` — also von *einem* der Punkte mit Höchststufe, nicht
aus der Vereinigung aller. Erreichen zwei Punkte derselben Stunde dieselbe
Stufe über **verschiedene** Zutaten, entscheidet der Tie-Break nach
Niederschlag und Böen, welche Herkunft überlebt — ein für die Herkunft
sachfremdes Kriterium.

Das verletzt die freigegebene Auslegung (ii) („alle tragenden Signale, kein
Gewinner"). Erreichbar an der **Ankunftsstunde**, wo sich Segment- und
Nachtfenster überschneiden (Docstring `day_window.py:39-41`). ⇒ Gehört in
diese Scheibe, sonst zeigt die Kurzzusammenfassung dort eine unvollständige
Herkunft.

### ⚠️ Neuer Befund 2: Restweg der Kurzzusammenfassung in die SMS

`src/services/notification_service.py:417` (SMS) und `:433` (Premium-SMS)
senden `report.sms_text or report.email_plain`. Die Kurzzusammenfassung steht
in `email_plain` — bei leerem SMS-Text ginge sie samt Herkunft an beide
Kurznachrichtenkanäle, entgegen der PO-Entscheidung.

Entschärft, aber nicht ausgeschlossen: `sms_text` wird laut #868 **immer**
erzeugt (`trip_report.py:441`), der Rückfall ist damit praktisch tot. Als
Restrisiko zu benennen und durch einen Test am **erzeugten SMS-Text** zu
bewachen — nicht durch die Annahme, der Zweig sei unerreichbar. In Scheibe 1
war genau eine solche Annahme („Compare-SMS zeigt Gewitter gar nicht")
gemessen falsch.

### Der geteilte Helfer: eine Signatur, drei Andockstellen

Die Regel existiert bereits — aber als **private Methode** an der Engine
(`weather_metrics.py:616-642`, `_compute_thunder_level_signals`), fest an
`NormalizedTimeseries` gebunden und damit für Segmente und Wegpunkte nicht
nutzbar. Sie bildet die Vereinigung über alle Stunden, die das Maximum
erreichen, dedupliziert unter Erhalt der Erstauftrittsreihenfolge, und liefert
`None` statt einer leeren Liste.

Vorbild für das Herauslösen ist `hail_priority()`
(`src/output/metric_format.py:568-583`): eine freie Funktion mit **neun**
Aufrufstellen, aufgerufen sowohl aus `aggregate_stage()` (`:1210`) als auch aus
`_aggregate_day()` (`:825`) als auch aus der Kurzzusammenfassung (`:600`) —
genau die drei Wege, um die es hier geht.

Die drei Andockstellen unterscheiden sich nur in dem, worüber vereinigt wird:

| Andockstelle | Vereinigung über | Paare aus |
|---|---|---|
| `aggregate_stage()` | Segmente | `s.thunder_level_max` / `s.thunder_level_max_signals` |
| `_aggregate_day()` | Wegpunkte | `p.metrics.thunder_level_max` / `p.metrics.thunder_level_max_signals` |
| `_format_thunder()` | gefensterte Stunden | `dp.thunder_level` / `dp.thunder_level_signals` |

Der Aufruf von `_compute_thunder_level_signals` liegt **nicht** in einem
`try/except` (`weather_metrics.py:438-440`) — das Herauslösen ist semantisch
sauber. (Prüfung wegen #1752: dort war der Aufrufkontext Teil der Semantik und
im `grep` unsichtbar.)

### Nebenbefunde

- **Doku-Drift:** Der Kommentar `compact_summary.py:91-93` behauptet,
  `_aggregate()` sei auch Quelle für Gewitter. Der Code widerspricht:
  `_format_thunder()` hat gar keinen `summary`-Parameter und liest
  ausschließlich die Stundenwerte (bewusst so, ADR-0025 Entscheidung 1, #1275).
- **Totes Gerüst:** `format_location_summary()` (`compact_summary.py:625-668`)
  hat keinen produktiven Aufrufer im gesamten Repo — nur Tests und Kommentare.
- **Go-Seite:** `internal/model/segment.go:4-27` kennt kein Signal-Feld; es ließ
  sich aber keine einzige Konstruktionsstelle von `model.SegmentWeatherSummary{}`
  in `internal/` finden. Ob das Struct überhaupt auf diesem Datenweg liegt, ist
  offen — für diese Scheibe ohne Belang, da sie die Go-Seite nicht berührt.
