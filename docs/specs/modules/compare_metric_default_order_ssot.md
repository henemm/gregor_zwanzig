---
entity_id: compare_metric_default_order_ssot
type: module
created: 2026-11-03
updated: 2026-11-03
status: draft
version: "1.0"
tags: [compare, ortsvergleich, metriken, reihenfolge, renderer, mail, epic-2259, epic-1372, issue-1356]
---

# Ortsvergleich: eine Quelle fuer die Standard-Metrik-Reihenfolge (+ Klartext am Mail-Sink)

## Approval

- [ ] Approved

## Purpose

Fuer Ortsvergleiche ohne gespeicherte Metrik-Auswahl (`enabled_metrics=None`,
Altbestand) zeigen HTML- und Klartext-Teil der Compare-Mail dieselben
Metrik-Zeilen in verschiedener Reihenfolge, weil zwei von Hand gepflegte Listen
(`CV2_METRICS`, `_PLAIN_ROWS`) existieren. Diese Spec legt `CV2_METRICS` als
einzige Quelle der Standardreihenfolge fest, leitet `_PLAIN_ROWS` daraus ab,
sichert das mit Waechtern und reicht (C3-75) den Klartext der Compare-Mail an
den `mail_sink` durch, damit die Klartext-Reihenfolge ueberhaupt testbar ist.

Issue #1356 (Epic #2259, Scheibe S5 von Epic #1372 "Kanal-Treue: gleiche
Auswahl, gleiche Reihenfolge in allen Ausgaben"). Analyse:
`docs/context/fix-1356-compare-metrik-reihenfolge.md`.

Ausgangslage: Seit #1359/#1335 folgen HTML **und** Klartext einer gespeicherten
Nutzer-Reihenfolge. Es bleibt allein der Standardfall `None`.

## Source

- **File:** `src/output/renderers/comparison.py`
- **Identifier:** `_PLAIN_ROWS`, `_DAILY_PLAIN_ROWS`, `_ordered_rows`, `_PLAIN_ROWS_BY_ID`
- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `CV2_METRICS` (kanonische Reihenfolge, unveraendert)
- **File:** `src/services/notification_service.py`
- **Identifier:** `NotificationService.send_compare_report` (`mail_sink`-Aufruf)

Schicht: Python-Core (Renderer in `src/output/renderers/`, Dienst in
`src/services/`). Kein Go-API-, kein Frontend-Eingriff.

> **Querschnitts-Pruefpunkte (CLAUDE.md):**
> - **Trip/Ortsvergleich-Teilung:** Die Reihenfolge-Quelle ist EIN Modul
>   (`CV2_METRICS`); `_PLAIN_ROWS` wird daraus abgeleitet, es entsteht keine
>   zweite Kopie und keine neue Compare-Komponente mit Trip-Pendant. Das
>   Frontend ist nicht betroffen: `COMPARE_METRIC_KEYS`
>   (`corridorEditorState.ts`) deckt sich bereits mit der `CV2_METRICS`-
>   Reihenfolge (Paritaets-Waechter `compareMetricKeysParity.test.ts`
>   vergleicht sortiert und bleibt gruen). Der Trip-Pfad wird nicht beruehrt.
> - **Mandantentrennung:** Reine Renderer-Aenderung (Zeilenreihenfolge einer
>   modulweiten Konstante) und ein zusaetzlicher Keyword im Test-Sink-Aufruf.
>   Es werden keine Nutzerdaten gelesen, geschrieben oder bewegt; `user_id`-
>   Weg und Empfaengeraufloesung bleiben unveraendert. Daher kein
>   Zwei-Nutzer-Test; die Konstante ist nutzerunabhaengig.
> - **Kanaele:** siehe naechster Abschnitt, alle vier benannt.

### Betroffene Kanaele (am Code gemessen, 2026-11-03)

Bei `enabled_metrics=None` gilt:

| Kanal | Quelle der Standard-Zeilen | Wirkung dieser Spec |
|---|---|---|
| E-Mail **HTML** | `CV2_METRICS` (`compare_html._visible_metrics`) | unveraendert (ist die kanonische Reihenfolge) |
| E-Mail **Klartext** | `_ordered_rows(_PLAIN_ROWS, None)` (`comparison.py:257`) | **einzige Aenderung**: Zeilenfolge wird die HTML-Folge |
| **Telegram** | `_CHANNEL_METRICS` (`comparison.py:549`, Zugriff Z.768): temp_max, wind_max, sunny_hours, cloud_avg, snow_depth_cm, snow_new_cm | unveraendert (Kurz-Auswahl, bereits in HTML-Reihenfolge) |
| **SMS** | `_CHANNEL_METRICS` (Zugriff Z.996) | unveraendert |
| **Premium-SMS** | verwendet denselben SMS-Text (`sms_text`, `render_compare_sms`) | unveraendert |

`_PLAIN_ROWS_BY_ID` (Dict-Nachschlag nach ID) ist reihenfolgeunabhaengig; die
Telegram-/SMS-Zeilen werden bei `None` nach `_CHANNEL_METRICS` geordnet, nicht
nach `_PLAIN_ROWS`. Die Annahme der Analyse "Telegram/SMS folgen Plain" trifft
fuer den Standardfall **nicht** zu (sie gilt nur bei gespeicherter Auswahl,
dort bestimmt aber ohnehin die Nutzerliste die Reihenfolge). Die Aenderung der
Analyse-Tabelle ist hiermit festgehalten; `FROZEN_TELEGRAM_ORDER` bleibt
daher **unveraendert** (Abweichung von der Analyse-Tabelle "Affected Files").

> **PFLICHT-Hinweis Renderer-Gate:** `comparison.py` und `compare_html.py`
> (letztere nur bei Waechter-Zugriff, ggf. unveraendert) loesen das
> Renderer-Commit-Gate aus: Modus-Matrix-Test und
> `email_spec_validator.py` gegen eine **echt zugestellte** Staging-Mail
> (`X-GZ-Mail-Type: compare`), Staging-Mailweg-Werkzeug aus #2774.

## Estimated Scope

- **LoC:** ca. +60 / -40
- **Files:** ca. 4 (`comparison.py`, `notification_service.py`,
  `tests/unit/test_compare_metric_order.py`,
  `docs/specs/modules/compare_metric_order.md`) plus ggf. neue Testdatei
- **Effort:** low-medium (Risiko: Renderer-Gate, Sink-Kompatibilitaet)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compare_html.CV2_METRICS` | Konstante | Quelle der Standardreihenfolge (Schluessel `key`) |
| `comparison._PLAIN_ROWS` / `_DAILY_PLAIN_ROWS` | Konstante | Klartext-Zeilen; werden nach `CV2_METRICS` sortiert |
| `compare_metric_ids.FRONTEND_TO_RENDERER_METRIC_ID` | Mapping | Frontend-Schluessel -> Renderer-ID (Auswahlweg, nicht Standardreihenfolge) |
| `NotificationService.send_compare_report` | Funktion | Mail-Sink-Naht (C3-75) |
| `tests/unit/test_compare_metric_order.py` | Test | AC-7-Charakterisierung wird bewusst angepasst |
| `docs/specs/modules/compare_metric_order.md` | Spec | AC-7 + Known Limitation bekommen Nachtrag |

## Implementation Details

### 1. Eine Quelle, abgeleitete Klartext-Liste

**Schluessel-Abbildung (gemessen):** Die Zeilen-Schluessel von `CV2_METRICS`
(`key`) und die Renderer-Metrik-IDs der Plain-Zeilen (`_PLAIN_ROWS[i][0]`)
sind **identisch** (26 Schluessel, z.B. `temp_max`, `wind_max`,
`snow_depth_cm`, `snow_new_cm`, `wind_direction_avg`, `humidity_avg`).
Abweichend benannt sind nur (a) das Feld `metric_id` in `CV2_METRICS`, das auf
das zentrale Register zeigt (`temperature`, `wind`, `snow_depth`,
`fresh_snow`, `wind_direction` ...), und (b) die Frontend-IDs
(`FRONTEND_TO_RENDERER_METRIC_ID`, z.B. `temp_max_c` -> `temp_max`,
`snow_new_sum_cm` -> `snow_new_cm`, `wind_direction_deg` ->
`wind_direction_avg`). Fuer die Reihenfolge zaehlt ausschliesslich `key`
(CV2) gegen `row[0]` (Plain); `metric_id` des Registers und die Frontend-IDs
sind nicht beteiligt, eine Uebersetzung ist nicht noetig.

`_PLAIN_ROWS` bleibt die Tabelle (Renderer-ID, Katalog-Label-Schluessel,
Formatter). Sie wird beim Modulimport ueber ein kleines Hilfsstueck
(z.B. `_sort_by_cv2_order(rows)`) in `CV2_METRICS`-Reihenfolge gebracht
(`warn` ist nur HTML und wird uebersprungen; `_DAILY_PLAIN_ROWS` wird dabei
mit eingemischt). Kommentare in `comparison.py`, die Deckungsgleichheit
behaupten bzw. "die Reihenfolge DIESER Konstante ist AC-7" sagen, werden
korrigiert.

**Fail-fast statt stilles Ans-Ende-Haengen:** Enthaelt `_PLAIN_ROWS` einen
Schluessel, der nicht in `CV2_METRICS` (ohne `warn`) steht, oder fehlt einer,
schlaegt der Import mit einem klaren Fehler fehl (`ValueError`/`KeyError` mit
Schluesselnamen). Kein `sorted(..., key=default=len)`-Fallback.

### 2. C3-75: Klartext am `mail_sink`

`send_compare_report` ruft heute `mail_sink(subject=subject, body=html_body)`;
`text_body` (Klartext) erreicht den Sink nicht, daher ist der Klartext der
Compare-Mail ueber den Sink nicht testbar. Neu: der Klartext wird als
Keyword `plain_body=text_body` mitgegeben -- **nur wenn der Sink es
annimmt**.

Entscheidung: Annahme-Pruefung per `inspect.signature` auf dem Sink
(`_sink_accepts_plain_body(sink)`):
- Sink hat Parameter `plain_body` oder `**kwargs` (VAR_KEYWORD) -> mit
  `plain_body` aufrufen.
- sonst (z.B. `lambda subject, body:`, `lambda *a`) -> wie bisher
  `mail_sink(subject=..., body=...)`.
- Signatur nicht ermittelbar (`ValueError`/`TypeError`) -> wie bisher
  (konservativ).

Begruendung: Die Aenderung muss die Mehrzahl bestehender Test-Sinks
(Signatur `lambda subject, body:` bzw. `lambda **kw`) unveraendert lassen;
ein unbedingtes neues Keyword wuerde `TypeError` bei den Positionssinks
ausloesen. Eine Aenderung an allen bestehenden Sinks waere ein Eingriff in
viele fremde Tests ohne fachlichen Gewinn.

**Risikostellen (am Code gemessen):**
- Sinks mit `**kw`, die den Inhalt von `kw` auswerten (z.B.
  `tests/tdd/test_compare_alert_parallel_mandanten.py:78` mit `str(kw)`, ggf.
  weitere `lambda **kw`: `test_compare_preset_send.py:538` speichert `kw`
  vollstaendig, `test_compare_premium_sms_versand.py:423`,
  `test_selection_conservation_rendered.py:672` liest `kw.get("body")`,
  `test_telegram_test_mode_guard.py:341` liest `kw.get("subject")`). Diese
  bekommen den Klartext zusaetzlich im Dict; Asserts, die auf exakte
  Gleichheit des Dicts bzw. `str(kw)` pruefen, koennen kippen und sind bei
  `/50` gezielt gegenzupruefen (Treffer fuer `send_compare_report`-Pfad, nicht
  die Alarm-Pfade).
- Positionssinks `lambda subject, body:` (z.B.
  `test_alert_undelivered_hint.py:1030/1546`) bleiben unveraendert, weil sie
  `plain_body` nicht annehmen. Dieser Test (Z.~1132) dokumentiert, dass der
  Klartext bisher nur ueber das Echt-Pfad-Muster geprueft wird; mit dem neuen
  Keyword kann er kuenftig ueber den Sink pruefen.
- `inspect.signature` auf `functools.partial`/Mock-Objekten: Mocks akzeptieren
  `**kwargs` und zaehlen damit als annehmend, das ist gewollt.

**Nicht im Scope von C3-75:** die Amtswarn-Sinks `notification_service.py`
Z.1405 (Trip-Amtswarnung) und Z.1745 (`_dispatch_compare_official_email`) und
alle Alarm-Pfade (Z.2101 usw.): andere Mailtypen, getrennter Kontrakt.

### 3. Aenderung an AC-7 der Spec `compare_metric_order.md` (Umfang der Umsetzung)

Bei `/50` wird `docs/specs/modules/compare_metric_order.md` ergaenzt (diese
Spec schreibt die Datei nicht selbst):
- Hinweis-Block bei **AC-7**: Die Plain-Standardreihenfolge wird in v1.1
  bewusst auf die HTML-Reihenfolge umgestellt (Ticket #1356, PO-bestaetigt
  2026-07-24). Die Zusicherung "nichts aendert sich ungefragt" gilt weiter
  fuer HTML, Telegram, SMS, Premium-SMS sowie Zeileninhalt/Werte des
  Klartexts; nur die Plain-**Zeilenfolge** aendert sich, bewusst und einmalig.
- Absatz **"HTML und Klartext haben unterschiedliche Standard-Reihenfolgen"**
  (Known Limitations): umformulieren zu "bis #1356 unterschiedlich; seit
  #1356 eine Quelle (`CV2_METRICS`)".
- Version/Changelog nachziehen.

Im Test: `FROZEN_PLAIN_ORDER` in `TestAC7LegacyDefaultOrderUnchanged` wird auf
die `FROZEN_HTML_ORDER`-Folge (ohne "Amtliche Warnungen") umgestellt;
`FROZEN_TELEGRAM_ORDER` und `FROZEN_HTML_ORDER` bleiben.

## Expected Behavior

- **Input:** Compare-Mail-Rendering mit `enabled_metrics=None`.
- **Output:** Klartext-Zeilen je Ort in `CV2_METRICS`-Reihenfolge:
  temp_max, wind_max, precip_sum, pop_max, thunder_max, sunny_hours,
  cloud_avg, uv_max, visibility_min, snow_depth_cm, snow_new_cm, temp_min,
  gust_max, freezing_level, wind_direction_avg, wind_chill_min/max,
  cloud_low/mid/high_avg, humidity_avg, dewpoint_avg, pressure_avg,
  precip_type, snowfall_limit; "Amtliche Warnungen" bleibt HTML-Zeile 1.
  Zeileninhalt/Werte/Labels unveraendert. Telegram/SMS/Premium-SMS
  unveraendert.
- **Side effects:** `mail_sink`-Aufrufer, die `plain_body` oder `**kw`
  annehmen, erhalten zusaetzlich den Klartext (nur `send_compare_report`).
  Fuer Nutzer mit gespeicherter Auswahl (`enabled_metrics` gesetzt) aendert
  sich nichts.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich ohne gespeicherte Metrik-Auswahl
  (`enabled_metrics=None`) und drei Orte mit Werten fuer alle 26 Metriken /
  When die Compare-Mail gerendert wird (HTML und Klartext) / Then stehen die
  Metrik-Zeilen im Klartext in exakt derselben Reihenfolge wie im HTML (ohne
  die HTML-Zeile "Amtliche Warnungen"), nach Anzeige-Label verglichen, je
  Ort.
  - Test (Kern, deterministisch): rendert `render_comparison_text` und
    `render_compare_html` mit `None`, liest die Label-Reihenfolge je Kanal
    mit den Helfern aus `tests/helpers/compare_order.py` und vergleicht auf
    Gleichheit (Ende-zu-Ende-Vergleich, nicht nur Listenvergleich).

- **AC-2:** Given die Konstanten `_PLAIN_ROWS` (Renderer-IDs, Klartext) und
  `CV2_METRICS` (HTML) / When der Waechter-Test die Schluesselfolgen
  vergleicht / Then ist die Folge der IDs in `_PLAIN_ROWS` gleich der Folge
  der `key`-Werte in `CV2_METRICS` ohne `warn`, und der Test wird rot, sobald
  eine Metrik nur in einer der beiden Listen steht oder die Reihenfolge
  abweicht.
  - Test (Kern, deterministisch): Waechter vergleicht die zwei
    Schluesselfolgen; Gegenprobe per String-Mutation einer Liste in einer
    Kopie (kein `git checkout/stash`) zeigt rot.

- **AC-3:** Given ein Schluessel kommt in `_PLAIN_ROWS`, aber nicht in
  `CV2_METRICS` vor (oder umgekehrt) / When das Modul importiert bzw. die
  Sortierung ausgefuehrt wird / Then bricht der Import mit einer klaren
  Fehlermeldung, die den Schluessel nennt; die Zeile wird nicht still ans
  Ende gehaengt.
  - Test (Kern, deterministisch): Hilfsfunktion der Sortierung mit
    kuenstlich ergaenzter Zeile aufrufen und auf die Fehlermeldung mit dem
    Schluesselnamen pruefen.

- **AC-4:** Given ein Altbestands-Ortsvergleich (`enabled_metrics=None`) /
  When Telegram-Kurz-/Lang-Nachricht, SMS und Premium-SMS (derselbe SMS-
  Text) erzeugt werden / Then entsprechen ihre Metrik-Folge und Inhalt
  exakt dem Stand vor dieser Aenderung (temp, wind, sonne, wolken,
  schneehoehe, neuschnee aus `_CHANNEL_METRICS`) -- die Angleichung der
  Plain-Reihenfolge verschiebt dort nichts.
  - Test (Kern, deterministisch): `FROZEN_TELEGRAM_ORDER` bleibt
    unveraendert gruen; zusaetzlich SMS-Ausgabe mit `None` auf
    zeichengleiche Ausgabe gegen eingefrorene Erwartung (alle vier Kanaele
    benannt; die SMS-Charakterisierung ergaenzt, falls noch nicht vorhanden).

- **AC-5:** Given ein Altbestands-Ortsvergleich (`enabled_metrics=None`) /
  When HTML und Klartext vor und nach der Aenderung verglichen werden /
  Then sind HTML-Zeilenfolge, alle Zeilen-Labels, Werte und Einheiten in
  Klartext und HTML unveraendert -- ausschliesslich die Reihenfolge der
  Klartext-Zeilen hat sich geaendert (bewusste, PO-bestaetigte Ausnahme von
  AC-7 der Spec `compare_metric_order`).
  - Test (Kern, deterministisch): `TestAC7LegacyDefaultOrderUnchanged`
    mit auf die HTML-Folge umgestelltem `FROZEN_PLAIN_ORDER`; Test
    `FROZEN_HTML_ORDER` unveraendert; Vergleich der Label-/Wert-Mengen
    des Klartexts vor und nach (mengengleich).

- **AC-6:** Given ein Ortsvergleich mit gespeicherter, vom Standard
  abweichender Metrik-Auswahl (`enabled_metrics` gesetzt, oder `[]`) /
  When die Mail in HTML und Klartext gerendert wird / Then folgen beide
  weiterhin ausschliesslich der gespeicherten Liste (`[]` bleibt leer); die
  neue Standardreihenfolge hat darauf keinen Einfluss.
  - Test (Kern, deterministisch): bestehende Tests aus #1359 (AC-1 bis
    AC-3, AC-8 der Spec `compare_metric_order`) bleiben unveraendert gruen.

- **AC-7:** Given ein Test-Sink, der `plain_body` oder `**kw` annimmt /
  When `send_compare_report` mit `mail_sink` und `effective_channels`
  `{"email"}` laeuft / Then erhaelt der Sink neben `subject` und `body`
  (HTML) das Keyword `plain_body` mit dem Klartext der Compare-Mail
  (identisch zum uebergebenen `text_body`).
  - Test (Kern, deterministisch): Aufruf mit `lambda **kw: ...` und mit
    explizitem `plain_body`-Parameter; Klartext-Inhalt gegen den
    uebergebenen `text_body` pruefen und die Zeilenfolge (AC-1) am Sink-
    Klartext statt am Echt-Pfad nachweisen.

- **AC-8:** Given ein bestehender Test-Sink mit Signatur
  `lambda subject, body:` (ohne `plain_body`/`**kw`) / When
  `send_compare_report` laeuft / Then wird der Sink unveraendert nur mit
  `subject` und `body` aufgerufen (kein `TypeError`), die E-Mail gilt als
  zugestellt (`sent_channels` enthaelt `email`).
  - Test (Kern, deterministisch): Aufruf mit Positions-Sink; kein
    Fehler, Sink-Argumente unveraendert.

- **AC-9:** Given Amtswarn-Mails (Trip-Amtswarnung, `_dispatch_compare_official_email`)
  und Alarm-Pfade / When sie ueber `mail_sink` laufen / Then ruft der Code
  ihren Sink weiterhin exakt wie bisher auf (nur `subject`, `body`) -- C3-75
  gilt allein fuer `send_compare_report`.
  - Test (Kern, deterministisch): bestehende Amtswarn-/Alarm-Tests bleiben
    unveraendert gruen (u.a. `test_compare_official_alert_*`).

- **AC-10:** Given eine nach Merge auf Staging ausgeloeste
  Compare-Mail an einen Altbestands-Ortsvergleich ohne gespeicherte
  Auswahl / When die echt zugestellte Mail im Stalwart-Test-Postfach per
  Prueflauf (#2774) abgeholt und mit `email_spec_validator.py`
  validiert wird / Then ist der Validator-Exit 0, und der Klartext-Teil der
  Mail (`text/plain`) enthaelt die Metrik-Zeilen in der Reihenfolge des
  HTML-Teils.
  - Test (E2E, Staging, Live-Schicht in `/e2e-verify`): Mail zustellen, beide
    MIME-Teile auslesen, Label-Reihenfolge vergleichen.

## Known Limitations

- **Katalog-Reihenfolge (Beobachtung, nicht geaendert):**
  `get_compare_metric_catalog()` fuehrt eine dritte Reihenfolge
  (snow_depth, snow_new, sunny, wind, ...). Sie dient Anzeige/Auslieferung
  und ist nicht der Mail-Standard. Eine Angleichung ist ausdruecklich nicht
  Teil dieser Spec.
- Nicht im Scope: Orts-Reihenfolge (#1359 Scheibe 2), Alarm-Pfade,
  Frontend, Editor-Marken, Amtswarn-Sinks.
- Die Telegram-/SMS-Kurz-Auswahl (`_CHANNEL_METRICS`) bleibt eine eigene,
  kleine Liste; sie ist nicht aus `CV2_METRICS` abgeleitet (nur zufaellig
  HTML-konform). Eine Ableitung waere eine separate Entscheidung.
- Der Klartext-Teil wird von `email_spec_validator` nicht geprueft (liest nur
  HTML); die Reihenfolge-Sicherung des Klartexts laeuft ueber AC-1/AC-2/AC-7
  und den E2E-Test AC-10.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue Entscheidungsflaeche; die kanonische Reihenfolge
  war schon die des Frontend-Editors und der HTML-Mail. Die bewusste
  Abloesung der eingefrorenen Plain-Reihenfolge (AC-7 in
  `compare_metric_order`) ist ueber Ticket #1356 / PO-Bestaetigung
  2026-07-24 und den Nachtrag in der Spec nachvollziehbar dokumentiert.

## Changelog

- 2026-11-03: Initial spec created (Issue #1356, Epic #2259 / #1372 S5).
