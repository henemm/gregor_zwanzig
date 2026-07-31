# Context: fix-1425-s2b-gewitter-skala

**Issue:** #1425 Schritt 2 Teil 2, **Scheibe B** — die letzte offene Scheibe des Tickets.
Scheibe A (Markier-Wirkung, `b3995b17`) und C (Banner-Text, `f6286910`) sind live.

## Request Summary

Der Trip führt Gewitter als **Prozent 0–100** (`ROUTE_METRIC_DEFS`, Vorgabe „bis 40"), der
zentrale Katalog als **dreistufig ordinal** (`kein/mittel/hoch`). Die Skalen sollen vereinheitlicht
werden; danach kann die Übergangs-Zuordnung `TRIP_CORRIDOR_METRIC_TO_COL_KEY` entfallen.

## Der Fehler ist invertiert, nicht nur unwirksam

Der Ticket-Text sagt „markiert dadurch *jede* Stunde. Kein Absturz, aber fachlich unsinnig".
Die Messung präzisiert das:

- Der Stundenwert ist ein `ThunderLevel`-Enum (`src/app/models.py:35-39, 107`), der Renderer
  übersetzt ihn per `thunder_ordinal()` in **0/1/2** (`src/output/metric_format.py:218-229`).
- Der gespeicherte Trip-Korridor trägt **Prozent**: `[null, 40]`.
- `corridor_inside(0|1|2, None, 40)` (`src/services/corridor_match.py:17-40`) ist deshalb
  **immer wahr** — auch bei `HIGH`.

Wirkung für den Nutzer: Die Markierung sagt „im Wunschbereich" **gerade dann, wenn Gewitter
herrscht**. Das ist schlimmer als wirkungslos. Über die Zahlenfelder ist der Korridor auch nicht
reparierbar: Nur `max = 0` würde stufenrichtig wirken, der Schieberegler bietet aber 0–100 in
5er-Schritten.

## Datenbestand: keine betroffenen Einstellungen

Alle Datenwurzeln durchsucht (`/home/hem/gregor_zwanzig/data`, `gregor_zwanzig_staging/data`):

| Fund | Datei | Inhalt | Bewertung |
|---|---|---|---|
| Vergleichs-Preset | `data/users/henning/compare_presets.json` | `thunder_level_max`, `range: [null, 0]` | bereits **ordinal**, korrekt, keine Migration |
| Trip (tot) | `data/users/henning/trips/5f534011.json` | `thunder_level`, `range: [null, 1]` | `trips/` ist **toter Altbestand seit #1250**, der Kern liest ausschließlich `briefings/` |
| Trip (tot) | `data/users/henning/trips/74de939c.json` | `thunder_level`, `range: [null, 1]` | dito |
| **lebender Pfad `briefings/`** | — | **kein einziger Gewitter-Korridor** | — |

**Konsequenz:** Die Migration betrifft real **null** Datensätze. Sie wird trotzdem gebaut (ein
Nutzer kann jederzeit vor dem Fix einen Korridor mit der Vorgabe „bis 40" anlegen), aber sie ist
nicht mehr der Risikotreiber, als der sie im Ticket geführt wurde.

## Der Ordinal-Zweig existiert bereits — er wird nur nicht erreicht

Das ist der zweite Grund, warum diese Scheibe kleiner ist als befürchtet:

| Baustein | Beleg | Zustand |
|---|---|---|
| Ordinal-Darstellung Desktop | `CorridorEditor.svelte:366-392` — drei Beschriftungs-Buttons statt Schieberegler | **fertig** |
| Ordinal-Darstellung Mobil | `CorridorEditorMobile.svelte:244-245, 359-363` | **fertig** |
| Ordinal-Skala aus Katalog ableiten | `compareMetricCatalogLoader.ts:51-53` — `kind==='ordinal'` → `scale=[0, labels.length-1]` | **fertig**, aber nur im Compare-Zweig |
| Compare-Zeilenzustand trägt `kind` | `corridorEditorState.ts:513-518, 555-557` | **fertig** |
| **Route-Zeilenzustand trägt `kind` NICHT** | `corridorEditorState.ts:155-162` (`buildRoutePool`), `:192-197` (`addRow`) | **Lücke** |
| **Route-Katalog-Ableitung verwirft `kind`** | `compareMetricCatalogLoader.ts:150-152` — mappt nur `rangeMin/rangeMax/step` | **Lücke** |
| **Gewitter ist aus dem Route-Pool ausgeschlossen** | `compareMetricCatalogLoader.ts:110-117` + `ROUTE_CORRIDOR_CATALOG_IDS` (`corridorEditorState.ts:98-105`, Schlüssel `thunder`) | **bewusst, für diese Scheibe** |

Der Ordinal-Zweig in `CorridorEditor.svelte:366` kann im `context="route"` heute **strukturell nicht
greifen** — nicht weil er fehlt, sondern weil `kind` nie im Zeilenzustand ankommt.

## Der Schlüsselwechsel ist die eigentliche Migration

Zieht Gewitter auf den Katalog um, heißt die Metrik `thunder_level_max` statt `thunder_level`
(`compare_metric_catalog.py:92-95`). Gespeicherte Korridore tragen den alten Schlüssel — sie müssen
umgeschlüsselt **und** umgerechnet werden, sonst verschwinden sie stillschweigend aus dem Editor
(`buildRoutePool` kennt sie dann nicht mehr) und aus der Markierung.

## Weitere Leser derselben Größe (Regressionsflächen)

Drei Skalen koexistieren im System — die Umstellung darf keine davon anfassen:

| Skala | Wo | Bleibt |
|---|---|---|
| `thunder_ordinal` **0/1/2** | Alarme (`weather_change_detection.py:591-596, 658-668`), Marken (`corridor_mark.py:49-57`), Telegram (`narrow.py:168-171`), Tagesvergleich, Tagesfenster | unverändert |
| `thunder_label_value` **0/2/3** | **nur** SMS-Token (`sms_trip.py:351-363`, ausdrücklich „NICHT `thunder_ordinal`") | unverändert |
| Enum | Risk Engine (`risk_engine.py:121-130`), Ausblick (`outlook.py:165-166`), Formatierer | unverändert |
| Alarm-Schwellen 1.0/2.0 | Go-Defaults (`internal/model/trip.go:184-211`), FE-Beschriftung (`alertMetricLabels.ts:52-59`) | unverändert |

**Prozent-Reste außerhalb des Korridors** (gefunden, nicht Teil dieser Scheibe):
`html.py:173-178` (Zahlen-Fallback `>20 → risk`) und `html.py:275, 294-299, 345` (Mobil-Stundenliste
gibt `{thunder_val:.0f}%` aus, liefert bei Enum-Werten 0). Beide sind Altlasten der
Prozent-Interpretation — als Sammel-Einträge notieren.

## Risks & Considerations

1. **Schlüsselwechsel ohne Umschlüsselung = stiller Verlust** eines gespeicherten Wertebereichs.
   Die Umschlüsselung muss beim Laden greifen (`buildRoutePool`), damit auch Daten erfasst werden,
   die nie durch eine Migration liefen.
2. **`unknownCorridors`-Pass-Through** (aus Teil 1) darf den alten Schlüssel nicht als „unbekannt"
   durchreichen und dadurch doppelt speichern.
3. **Geteilter Editor:** Der Ordinal-Zweig wird ab jetzt in beiden Kontexten benutzt — keine
   Route-eigene Kopie bauen (Teilungs-Invariante).
4. **Mail-Gate #811** greift, sobald `html.py` angefasst wird.
5. **Rückbau `TRIP_CORRIDOR_METRIC_TO_COL_KEY`:** Nach dem Umzug trägt kein lebender Datensatz mehr
   einen der 5 Route-Schlüssel — außer den 4 übrigen (`wind_gust`, `temperature_min/max`,
   `snow_line`). Der vollständige Rückbau ist deshalb **auch nach dieser Scheibe nicht** möglich;
   nur der `thunder_level`-Eintrag kann fallen. Das im Ticket versprochene „fällt, sobald der Pool
   auf Katalog-IDs umzieht" gilt also nur für Gewitter.

## Existing Specs

- `docs/specs/modules/fix_1425_s2b_markier_wirkung.md` — Scheibe A, enthält `build_trip_corridor_id_map()`
- `docs/specs/fast/fix-1425-s2c-banner-text.md` — Scheibe C
- `docs/specs/modules/fix_1425_s2_corridor_pool.md` — Teil 1, Pool-Erweiterung
