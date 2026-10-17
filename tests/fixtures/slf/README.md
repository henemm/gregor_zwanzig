# SLF-Fixtures (Issue #1441 Scheibe S3)

Spec: `docs/specs/modules/feat_1441_s3_slf.md` · Helper: `tests/helpers/slf_support.py`

## Herkunft

| Datei | Quelle | Aufgezeichnet |
|---|---|---|
| `at_<ISO>.json` (8 Dateien) | `GET https://aws.slf.ch/api/bulletin/caaml/de/json?activeAt=<ISO>` (CAAML6-JSON, ganze Schweiz) | 17.10.2026 |
| `leer.json` | `GET https://aws.slf.ch/api/bulletin/caaml/de/json` ohne `activeAt`, ausser Saison; Inhalt wörtlich `{"bulletins":[]}` (HTTP 200) | 16.10.2026 |
| `CH_micro-regions.geojson.json` | EAWS-Mikroregionen der Schweiz (149 Umrisse, MultiPolygon, CRS84 `[lon, lat]`), Lizenz CC0 | 17.10.2026 |

Die acht Bulletin-Dateien und die GeoJSON-Datei sind unverändert aus
`docs/artifacts/feat-1441-s3-slf/raw/` übernommen (Dateinamen gleich). Die Bulletins enthalten
höchstens Stufe 3; Stufe 4/5 und Absenkungen leiten Tests per `derive()` ab (nur
`mainValue`/`dangerRatingValue` geändert) und nennen das im Testnamen („abgeleitet").

Gültigkeiten: `03-01T08` 07:00Z–16:00Z (Morgen) · `03-01T17:30` und `03-02T06` dieselbe
Abend-Ausgabe 03-01 16:00Z–03-02 16:00Z · `03-02T08` 07:00Z–16:00Z (Morgen-Update) ·
`2025-12-20` 12-19 16:00Z–12-20 16:00Z · `04-10` 06:00Z–15:00Z.

## Punkte, die der Helper bereitstellt

Innere Punkte bestimmt `interior_point(region_id)` deterministisch aus dem Umriss (Raster, größter
Randabstand, in keiner anderen CH-Mikroregion); gegengeprüft mit `RegionMapper.regions_at`.

| Region | Punkt (lat, lon) | Verwendung |
|---|---|---|
| CH-7231 Münstertal | 46.6026, 10.3487 | AC-1/2/6/18 ff. (3-, oberhalb 2000) |
| CH-1311 | 46.3435, 6.8491 | AC-2 (Jan, zwei Probleme ab 2000), AC-5b (Apr, nachmittags) |
| CH-1246 | 46.7297, 8.3576 | AC-3 (Apr, unterhalb 2400), AC-6 (03-01, 2 neutral) |
| CH-5112 | 46.9240, 9.6385 | AC-4 (Abend 03-01, mehrdeutig), AC-6 (Jan, 3+) |
| CH-8112 | 46.6441, 6.3271 | AC-5a/AC-6 (Stufe 1, `lowerBound 0`) |
| CH-9211 Mittelland | 47.2560, 8.2577 | AC-13/14 (nie bewertet) |
| CH-5123 (Davos, Graubünden) | 46.7697, 9.8818 | AC-11 |
| CH-4222 (Zermatt, Wallis) | 46.0492, 7.7792 | AC-11 |
| CH-1243 (Grindelwald, Berner Oberland) | 46.5961, 8.0871 | AC-11 |
| CH-1122 | 46.6289, 7.0590 | AC-13 (bewertet 2026-02-10, nicht 2025-12-20) |

Feste Punkte außerhalb der Schweiz (in keiner CH-Mikroregion, geprüft): Innsbruck 47.27/11.39,
Bregenz 47.50/9.75, Aosta 45.74/7.32, Feldberg 47.87/8.00, dazu aus dem S1-Helper München,
Zell am See und die Tirol-Punkte. `P_ZUERICH` 47.37/8.54 liegt in **CH-9311** (nicht CH-9211);
der S1-Punkt 47.3769/8.5417 liegt in CH-9211. Beide Regionen sind in keiner Stichprobe bewertet.
