# Fix #1425 — Trip: „Markieren" wirkt im Briefing (Schritt 1: Wirkung)

- **Issue:** #1425 (Etappe S6 von #1372, Dach #1374) · Nachfolger des geschlossenen #1384
- **created:** 2026-07-30
- **Scope:** Python-Renderer + Durchreichweg. Kein Frontend, kein Go, kein Datenmodell.

## Vorgeschichte — was bereits entschieden ist

**Nicht erneut vorlegen.** Zwei Festlegungen liegen vor und gelten:

1. **PO 2026-07-26** (`docs/context/feat-1373-s2-ein-katalog.md:128`): *„erst Wirkung, dann Auswahl"* — der Trip-Pool wird nicht erweitert, solange Wertebereiche im Trip nichts bewirken. Reihenfolge bindend.
2. **Tab-Konzept #1360** (`docs/context/fix-1360-compare-tab-konzept.md:97`): Der Reiter *Wertebereiche* hat genau eine Zuständigkeit — *„Wie Werte gelesen werden: **markieren**"*. Der Reiter ist geteilt, die Zuständigkeit gilt für Trip und Vergleich gleich.
3. **PO 2026-07-30:** Richtung bestätigt — „Markieren" hebt den Wert im Trip-Briefing hervor; die Alternative (Reiter im Trip entfernen) ist verworfen.

**Daraus folgt ohne weitere Entscheidung:** markiert wird **überall dort, wo der Wert im Trip-Briefing erscheint** — genau wie im Ortsvergleich, der sowohl seine Übersichts- als auch seine Stundentabelle markiert (`compare_html.py:587`, `:763`).

## Ausgangslage (gemessen 2026-07-30, Stand `f9910112`)

`Trip.corridors` existiert im Modell (`src/app/trip.py:193`, seit #1231) und wird persistiert (`loader.py:213-231`, `:1509-1518`; Go `internal/model/trip.go:71-78`). **Gelesen wird es von keinem Trip-Ausgabeweg** — `src/output/renderers/email/__init__.py::render_email` hat keinen `corridors`-Parameter, und `email/html.py` enthält keinen Treffer auf `corridor`. Der Reiter *Wertebereiche* im Trip ist damit vollständig wirkungslos (Verstoß gegen Invariante 1 aus #1372).

Der Ortsvergleich hat die Mechanik fertig:

| Baustein | Ort | Aufgabe |
|---|---|---|
| `_mark_lookup(corridors, id_map)` | `compare_html.py:349` | nur `mark=True`, über `id_map` auf Renderer-Zeilen-Keys aufgelöst |
| `_is_marked(corridor, value)` | `compare_html.py:358` | delegiert an `corridor_inside()` (`src/services/corridor_match.py`) — **die einzige Match-Quelle**; Gewitter-Enum wird vorab per `thunder_ordinal()` übersetzt |
| `class="corridor-mark"` | `compare_html.py:538`, `:674` | additiv zur Ampel-Färbung |
| CSS-Injektion | `compare_html.py:1351` | `border-left:3px solid <success>`, nur wenn `corridors` nicht leer — sonst HTML byte-identisch |

Der Trip-Renderpfad hat genau **einen** Adapter: `src/output/renderers/trip_report.py:181` ruft `render_email(...)`. Die Stundentabelle entsteht in `email/html.py::_render_html_table` (`:552`), die Zellen bei `:708-712`.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einem Wertebereich, bei dem „Markieren" gesetzt ist / When das Briefing als E-Mail erzeugt wird / Then ist in der Stundentabelle jede Zelle dieser Wettergröße hervorgehoben, deren Wert innerhalb des eingestellten Bereichs liegt — und keine, deren Wert außerhalb liegt.
  - Test: Trip mit Korridor + Stundenwerten teils innerhalb, teils außerhalb; gerendertes HTML prüfen. Echte Objekte, kein Mock.

- **AC-2:** Given ein Trip mit einem Wertebereich, bei dem „Markieren" **nicht** gesetzt ist (nur gespeichert) / When das Briefing erzeugt wird / Then ist nichts hervorgehoben — ein reiner „nicht markieren"-Eintrag verändert die Ausgabe nicht.

- **AC-3:** Given ein Trip **ohne** Wertebereiche / When das Briefing erzeugt wird / Then ist das erzeugte HTML unverändert gegenüber dem Stand vor dieser Änderung — kein zusätzliches CSS, keine zusätzlichen Klassen. (Vorbild: dieselbe Zusicherung im Vergleich, `compare_html.py:1349-1351`.)

- **AC-4:** Given derselbe Wertebereich einmal an einem Trip und einmal an einem Ortsvergleich / When beide Briefings erzeugt werden / Then entscheidet **dieselbe** Abgleich-Funktion über „innerhalb" — es gibt keine zweite Match-Logik. Prüfbar: der Trip-Pfad benutzt `corridor_inside()`, und die Hervorhebungs-Bausteine liegen an **einer** Stelle, die beide Renderer nutzen.

- **AC-5:** Given eine Wettergröße, für die im Trip ein Wertebereich gesetzt ist, die aber in der Stundentabelle gar nicht angezeigt wird / When das Briefing erzeugt wird / Then wird der Eintrag still ignoriert und nichts bricht — aber er bleibt gespeichert (kein stilles Verwerfen der Daten).

- **AC-6:** Given die Gewitter-Größe / When ihr Wert gegen einen Wertebereich geprüft wird / Then wird die Stufe korrekt als Ordinalwert verglichen (nicht als Enum-Instanz und nicht als Prozentzahl) — dieselbe Übersetzung wie im Vergleich.

## Was NICHT Teil von Schritt 1 ist

- **Der Pool** (Inhalt des geschlossenen #1384): erst nach der Wirkung, so bindend entschieden. Dann auch die **zwei Gewitter-Skalen** — der Trip führt Gewitter heute als Prozent 0–100 mit Vorgabe 40 (`corridorEditorState.ts:33`), der Katalog dreistufig. Eine Umstellung reinterpretiert Bestandswerte und braucht eine Migration.
- **Der Klartext-Teil der Mail** (`email/plain.py`): dort gibt es keine Tabellenzellen und keine Auszeichnung — eine Hervorhebung ist strukturell nicht darstellbar. Bleibt dokumentiert außen vor, damit niemand es später als Lücke missversteht.
- **Telegram und SMS:** keine Auszeichnung möglich bzw. kein Platz. Unberührt.
- Frontend, Go, Datenmodell, Persistenz: keine Änderung.

## Umsetzungshinweise

- **Geteilt bauen, nicht kopieren.** `_mark_lookup`/`_is_marked` und die CSS-/Klassen-Regel gehören an eine Stelle, die Trip- und Vergleichs-Renderer gemeinsam nutzen. Ein Nachbau im Trip-Renderer wäre ein Verstoß gegen die Trip/Compare-Teilungs-Invariante (CLAUDE.md) — und genau das Anti-Pattern, das #1170 dokumentiert.
- **Durchreichweg:** `trip_report.py:181` gibt `trip.corridors` an `render_email` weiter; von dort bis `_render_html_table`. Kein neuer Ladeweg — das Feld liegt bereits am Trip.
- **Namensraum-Falle:** Trip-Korridore tragen Route-Keys (`wind_gust`, `precipitation_sum`, `temperature_min`, `temperature_max`, `thunder_level`, `snow_line`), die Stundentabelle eigene Spalten-Keys. Es braucht also eine Zuordnung analog `FRONTEND_TO_RENDERER_METRIC_ID`/`CORRIDOR_METRIC_TO_HOUR_KEY` im Vergleich. **Das ist ausdrücklich eine Übergangs-Zuordnung** und fällt, sobald der Pool auf Katalog-IDs umzieht (Schritt 2). Als solche kommentieren, mit Verweis auf #1372 — sonst entsteht das sechste Metrik-Vokabular.

## Pflicht-Gate vor dem Commit

Diese Änderung fasst Mail-Inhalts-Dateien an (`src/output/renderers/email/*.py`) → **Renderer-Mail-Gate #811** greift. Vor dem Commit nötig: `tests/tdd/test_issue_811_mode_matrix.py` frisch grün **und** ein erfolgreicher `briefing_mail_validator.py`-Lauf gegen eine **echt zugestellte** Staging-Test-Mail. Reihenfolge: stagen → Matrix → Mail senden → validieren → committen (nie Validator und Commit im selben Aufruf).

## Budget

Geschätzt **200–280 Zeilen** (Code + Tests): geteilte Extraktion der drei Bausteine, Durchreichweg über zwei Ebenen, Übergangs-Zuordnung, sechs AC-Tests. Das Standardlimit 250 ist knapp. **Kein Override im Vorgriff** — erst messen, dann bei Bedarf mit Zahlen vorlegen.

## Changelog

- 2026-07-31: Markier-Wirkung jetzt für 20 von 23 Metriken implementiert (Spec `fix_1425_s2b_markier_wirkung.md`, S2 Teil 2 Scheibe A); ausgenommen bleiben die 3 Tages-Summen, da Trip-Briefing keine Übersichtszeile für Tages-Aggregate hat
