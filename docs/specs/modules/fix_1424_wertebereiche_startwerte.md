# Fix #1424 — Ortsvergleich-Wertebereiche: Startwerte vollständig, ungeeignete Größen nicht mehr im Angebot

- **Issue:** #1424 (Etappe S6 von #1372, Dach #1374)
- **created:** 2026-07-30
- **Kontext:** Nachfolger des als überholt geschlossenen #1384
- **Scope:** Frontend (Ortsvergleich). Python/Go unverändert.

## Problem

Im Reiter *Wertebereiche* eines Ortsvergleichs sind alle 26 Katalog-Einträge als Wertebereich hinzufügbar (`buildCompareMetricDefs`, `compareMetricCatalogLoader.ts:31-56`; `buildComparePool`, `corridorEditorState.ts:378-400` — beide ohne Filter). Zwei Mängel:

**M1 — 12 Größen starten ohne Von/Bis-Vorgabe.** Die Startwert-Tabelle `_COMPARE_DEFAULTS` (`corridorEditorState.ts:259-274`) hat nur **14** Einträge. Fehlt der Eintrag, entsteht die Zeile mit `defaultMin: null, defaultMax: null` (`compareMetricCatalogLoader.ts:37`). Eine Zeile mit **beiden** Grenzen offen ist ungültig (`validateCorridorRows`, `corridorEditorState.ts:173-176`), und `saveGateDecision` (`:626-628`) liefert dann `dirty` statt `schedule` — das Speichern des **gesamten** Reiters bleibt aus, bis der Nutzer selbst eine Grenze setzt. Die 14 anderen verhalten sich anders, ohne dass das erkennbar ist.

**M2 — zwei Größen taugen nicht als Von/Bis-Bereich, werden aber angeboten.**
- *Niederschlagsart* (`precip_type_dominant`): `kind: "enum"` (RAIN/SNOW/MIXED/FREEZING_RAIN), ohne `rangeMin`/`rangeMax`. Das Frontend drückt sie auf einen Zahlen-Schieber 0–100 platt und sagt das selbst (`compareMetricCatalogLoader.ts:25-29`).
- *Windrichtung* (`wind_direction_deg`): zyklisch 0–360°. „von 350° bis 10°" ist mit einem Von/Bis-Paar nicht ausdrückbar; eine Sonderbehandlung existiert nicht.

**PO-Entscheidung 2026-07-30:** beide nicht mehr als Wertebereich anbieten. Sie bleiben normale Wettergrößen im Reiter *Wetter-Metriken*.

Damit sinkt M1 von 12 auf **10** zu ergänzende Startwerte — die zwei anderen fallen mit M2 weg.

## Die zehn Startwerte

Quelle: `IDEAL_DEFAULTS` deckt diese Größen **nicht** ab (nur 4 Profile × 3–4 Größen, `corridorEditorState.ts:339-362`). Also Sinnwerte — dasselbe Vorgehen wie bei `sunny_hours_h` im Bestand. Jeder Wert liegt **innerhalb der Katalog-Skala** und **auf der Schrittweite** der Größe.

| Größe | Einheit | Skala / Schritt | Vorgabe | Warum |
|---|---|---|---|---|
| Regenwahrscheinlichkeit | % | 0–100 / 5 | bis **30** | darüber plant man Regen ein |
| Luftfeuchtigkeit | % | 0–100 / 5 | **30–70** | Komfortband; darunter trocken, darüber drückend |
| Taupunkt | °C | −20–30 / 1 | bis **16** | ab ~16 °C wird es schwül |
| Luftdruck | hPa | 950–1050 / 5 | ab **1010** | Hochdruck-Seite, stabiles Wetter |
| Tiefe Wolken | % | 0–100 / 5 | bis **50** | tiefe Wolken nehmen die Sicht |
| Mittelhohe Wolken | % | 0–100 / 5 | bis **50** | dito, abgeschwächt |
| Hohe Wolken | % | 0–100 / 5 | bis **70** | hohe Wolken stören kaum, daher großzügiger |
| Gefühlte Temperatur (min) | °C | −30–30 / 1 | ab **−5** | analog Temperatur-Min im Bestand |
| Gefühlte Temperatur (max) | °C | −20–45 / 1 | bis **30** | strenger als Temperatur-Max (35), weil „gefühlt" |
| Schneefallgrenze | m | 0–5000 / 100 | ab **1500** | analog Nullgradgrenze im Bestand |

Einseitig offene Bereiche sind ausdrücklich erlaubt und im Bestand üblich (`temp_min_c`, `gust_max_kmh`, `freezing_level_m`) — Pflicht ist nur **mindestens eine** Grenze.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich im Reiter *Wertebereiche* / When der Nutzer eine der zehn oben genannten Größen über „+ Metrik hinzufügen" ergänzt / Then trägt die neue Zeile sofort die dort festgelegte Von/Bis-Vorgabe, und das Speichern des Reiters läuft an wie bei den bestehenden Größen — es bleibt nicht aus.
  - Test: `addCompareRow` mit den echten Defs je Größe aufrufen, `min`/`max` gegen die Tabelle prüfen; `saveGateDecision` der resultierenden Zeilen ergibt `schedule`, nicht `dirty`.

- **AC-2:** Given das gesamte Angebot des Reiters / When irgendeine angebotene Größe hinzugefügt wird / Then hat **jede** angebotene Größe eine Vorgabe mit mindestens einer Grenze — es gibt keinen Eintrag im Angebot, der eine sofort ungültige Zeile erzeugt.
  - Test: Vollständigkeitsprüfung über alle Einträge, die `buildCompareMetricDefs` aus der echten Katalog-Antwort erzeugt. Dieser Test ist der eigentliche Wert des Tickets: er verhindert, dass der Mangel zurückkommt, sobald eine neue Wettergröße in den Katalog aufgenommen wird.

- **AC-3:** Given der Reiter *Wertebereiche* / When der Nutzer das Angebot „+ Metrik hinzufügen" öffnet / Then erscheinen *Niederschlagsart* und *Windrichtung* dort nicht mehr, alle übrigen Größen weiterhin.

- **AC-4:** Given ein Ortsvergleich, für den früher ein Wertebereich zu *Niederschlagsart* oder *Windrichtung* gespeichert wurde / When der Nutzer im Reiter *Wertebereiche* etwas anderes ändert und speichert / Then ist der alte Eintrag danach unverändert weiterhin gespeichert — er wird nicht verworfen (Read-Modify-Write mit Merge, BUG-DATALOSS-GR221 / #102).
  - Test: gespeicherten Korridor mit einer nicht mehr angebotenen Metrik durch `buildComparePool` → `buildCompareCorridorSavePayload` führen, Eintrag muss im Ergebnis unverändert enthalten sein.

- **AC-5:** Given *Gewitter* / When es als Wertebereich hinzugefügt wird / Then bleibt es unverändert ein Stufenband (kein/mittel/hoch) — die Entfernung aus AC-3 trifft ausschließlich die beiden dort genannten Größen, nicht den Ordinal-Fall.

- **AC-6:** Given eine der zehn neuen Vorgaben / When sie im Editor erscheint / Then liegt jeder Wert innerhalb der Skala seiner Größe und auf deren Schrittweite — kein Wert, den der Schieber nicht darstellen kann.

## Was NICHT angefasst wird

- Der **Trip**-Zweig (`ROUTE_METRIC_DEFS`, `ROUTE_CORRIDOR_CATALOG_IDS`) — dort wirken Wertebereiche gar nicht, das ist **#1425**.
- Die zwei verschiedenen Gewitter-Skalen (Trip Prozent vs. Katalog dreistufig) — ebenfalls **#1425**, weil eine Umstellung Bestandswerte reinterpretiert und eine Migration braucht.
- Der `mark`-Pfad und die Vergleichs-Mail (`compare_html.py:355` `_mark_lookup`).
- Python und Go: keine Änderung. Die Persistenz nimmt beliebige Metrik-Schlüssel (`Corridor.metric` ist auf beiden Seiten ein freier String ohne Enum).

## Umsetzungshinweise

- Die Entfernung aus dem Angebot (AC-3) gehört an **eine** Stelle, damit sie nicht kontextabhängig auseinanderläuft. `buildCompareMetricDefs` ist der einzige Ort, an dem Katalog-Einträge zu Editor-Definitionen werden.
- Datenerhalt (AC-4) trägt der bestehende `unknownCorridors`-Weg: `buildComparePool` sammelt Korridore, deren Metrik nicht in `defs` steht, und `buildCompareCorridorSavePayload` hängt sie unverändert wieder an. Fällt eine Größe aus `defs`, greift dieser Weg von selbst — das ist zu **belegen**, nicht zu vermuten.
- Folgewirkung von AC-3 auf `COMPARE_METRIC_KEYS` (`corridorEditorState.ts:390-397`) prüfen: diese Liste dient der Metrik-**Auswahl** (Reiter *Wetter-Metriken*), nicht den Wertebereichen. Die zwei Größen bleiben dort, sie sind weiter auswählbare Wettergrößen.

## Betroffene Bestandstests

- `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.test.ts` — Prefill-/Pool-Tests, `_COMPARE_DEFAULTS`-Erwartungen.
- `frontend/src/lib/components/shared/corridor-editor/__tests__/compareMetricCatalogParity.test.ts` — eingefrorene 26er-Fixture; prüfen, ob die Parität die Angebotsliste oder den Katalog meint (der **Katalog** bleibt bei 26, nur das Wertebereichs-Angebot schrumpft auf 24).
- `tests/tdd/test_compare_metric_catalog_endpoint.py` — Endpoint-Vollständigkeit; darf unverändert bleiben, der Endpoint ändert sich nicht.

## Budget

Geschätzt ~120–160 Zeilen (Code + Tests): zehn Tabellenzeilen, eine Filterstelle, die Vollständigkeitsprüfung aus AC-2 plus vier AC-Tests. Standardlimit 250 reicht.
