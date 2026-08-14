# ADR-0055: Die 3-Tages-Vorschau des Trip-Briefings bekommt wählbare Spalten (löst ADR-0037 Punkt 2 ab)

- **Status:** Akzeptiert
- **Datum:** 2026-08-14
- **Bezug:** Issue #1720 Scheibe 1, Spec
  `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md` (AC-1 bis AC-17),
  Kontext-Dokument `docs/context/feat-1720-vorschau-metriken.md`.
  PO-Auftrag 2026-08-11, PO-Entscheidungen 2026-08-14.
  **Löst ADR-0037 Punkt 2 ab** (Trip-Mail bleibt byte-identisch);
  **schreibt ADR-0050** (Metrik-Kaskade) auf die Ausgabefläche „Vorschau" fort;
  grenzt sich bewusst gegen ADR-0053 Punkt 1 ab (s. „Divergenz zum
  Ortsvergleich").

## Kontext

ADR-0037 (2026-07-27) machte den 3-Tages-Ausblick des **Ortsvergleichs**
datengetrieben aus dem Metrik-Katalog. Punkt 2 jenes ADR sicherte ausdrücklich
zu:

> **`build_outlook_row(..., metrics=None)` bleibt byte-identisch.** Der neue
> `metrics`-Parameter ist rein additiv: `None` (Trip-Aufruf, unverändert)
> liefert exakt das bisherige feste Dict. Der Trip ruft weiterhin ohne
> `metrics` auf — die Trip-Mail ändert sich in keinem Byte.

Diese Zusicherung war für ihre Lieferung richtig: sie hielt den Trip aus einer
Compare-Scheibe heraus. Sie ist aber keine Aussage darüber, dass der Trip
dauerhaft keine Auswahl haben soll. Genau so wurde sie jedoch gelesen — an
zwei Stellen, die diese Lieferung mit korrigiert:

| Stelle | Wortlaut | Was tatsächlich gemeint war |
|---|---|---|
| `weatherMetricsTabSections.ts:54-55` | „Ebenfalls NUR im Vergleich: der Trip bekommt **bewusst keine** Ausblick-Auswahlfläche (Spec § Out of Scope)" | `issue_1361_1368_ausblick_konfigurierbar.md:535-536`: „Der Trip bekommt keine Bedienfläche — **das Epic betrifft ausschließlich den Ortsvergleich**" — Zuschnitt jener Lieferung |
| `docs/reference/metric_output_matrix.md:89` | „Der Trip-Ausblick hat keine wählbaren Spalten und **braucht keine**" | Feststellung des Ist-Standes plus Begründung, warum Scheibe 2 von #1703 Compare-only blieb |

**Die Fehlerklasse, die dieses ADR ausdrücklich benennt:** Eine Zuschnittgrenze
(„nicht in dieser Lieferung") wird beim Weiterreichen zu einer Festlegung
(„grundsätzlich nicht"). Im Verlauf dieses Workflows trat sie **dreimal** auf —
beim Code-Kommentar oben, bei einem verkürzten ADR-0053-Zitat in der
strategischen Bewertung (dort fielen die Worte „in dieser Scheibe" und
„Scheiben-Schnitt" weg), und in der Ursprungs-Begründung der Blockade selbst.
Vgl. dieselbe Klasse in #1680 S5a, wo eine Blockade-Begründung vier Scheiben
lang weitergereicht wurde, ohne je gemessen worden zu sein.

Der Ist-Stand vor dieser Lieferung, gemessen: Die Vorschau erscheint an **vier**
Trip-Ausgabeorten mit **drei unabhängigen** Implementierungen — HTML-Mail
(`email/html.py:1357`), Klartext-Mail (`email/plain.py:338`), Kompakt-Mail
(`email/compact.py:227-238`, eigener Loop) und Telegram-rich
(`narrow.py:571-609`). SMS und Premium-SMS erreichen sie baulich nicht
(`sms_trip.py` kennt `multi_day_trend` nicht). Alle vier zeigen fest verdrahtete
Spalten.

## Entscheidung

**1. Der Trip-Ausblick wird katalog-getrieben — dieselbe Bauform wie der
Ortsvergleich.** Auswahl liegt als `display_config.outlook_metrics` im
Neuformat `[{"metric_id": …, "aggregation": …}]`, aufgelöst über die
bestehenden, generischen Funktionen aus `compare_outlook_metric_ids.py`. Die
Drei-Werte-Semantik aus ADR-0037 Punkt 3 gilt unverändert: Feld fehlt → die
bisherigen festen Spalten; `[]` → der ganze Block entfällt; gefüllt → die
gewählten Spalten in Auswahl-Reihenfolge.

**Damit ist ADR-0037 Punkt 2 abgelöst.** Die Trip-Mail ändert sich, sobald ein
Nutzer die neue Fläche bedient. Ohne Bedienung bleibt sie byte-identisch — das
ist keine Nebenwirkung, sondern zugesichert und mit AC-1 am **echten
Versandpfad** geprüft, nicht am isolierten Renderer.

**2. Die Auswahl ist global — keine Kanal-Ebene.** Ein Abschnitt
„3-Tages-Vorschau" im Wetter-Reiter, eine Liste, keine Kanal-Reiter.

Begründung (PO-Entscheid 2026-08-14) — ausdrücklich **nicht** aus ADR-0053
Punkt 1 abgeleitet, dessen Formulierung nur einen Scheiben-Schnitt
rechtfertigt: SMS und Premium-SMS erreichen den Ausblick baulich nicht;
wirksam wären genau zwei Kanäle (E-Mail in drei Formen, Telegram). Eine
Kanal-Ebene für zwei Kanäle verdoppelt Bedienfläche, Speicherweg und Auflösung
für einen Nutzen, den niemand angefragt hat.

**3. Die Vorschau-Auswahl ist an die Grundauswahl gebunden.** Sie darf nur
abwählen, nie hinzufügen; eine Abwahl in der Grundauswahl wirkt sofort in der
Vorschau. Damit gilt ADR-0050 (Grundauswahl = Maximum) nicht nur für Kanäle,
sondern auch für diese Ausgabefläche — der Auftragstext zu #1720 verlangt das
ausdrücklich.

Zwei Regeln aus `_clip_to_global_maximum()` (`src/app/models.py:893-916`)
werden dabei übernommen, nicht neu erfunden: der Schnitt zieht seine
Schnittmenge aus `get_metrics_for_report_type(report_type)` (damit Morgen-/
Abend-Overrides und das `selectable`-Gate aus #1585 wirken), und bei **leerer**
Grundauswahl wird **nicht** geschnitten — „kein Maximum definiert" ist nicht
dasselbe wie „nichts erlaubt" (Regel D4).

**4. Die Auswahl wird an EINER Stelle aufgelöst und durchgereicht.** Diese
Entscheidung entstand aus einem Adversary-Finding (F001, HIGH) und ist der
eigentliche Architektur-Gehalt dieses ADR.

Der Trip-Renderer kollabiert `dc.metrics` vor dem Rendern auf den E-Mail-Kanal
(`trip_report.py:133-138`). Solange Spaltenbau (Renderer) und Zeilenbau
(Aggregation) **je selbst** auflösen, sehen sie verschiedene Stände. Die erste
Implementierung umging das, indem beide gegen den *kollabierten* Stand
schnitten — technisch stimmig, aber damit erbte die Vorschau die E-Mail-Kanal-
Ebene durch die Hintertür und widersprach Punkt 2 dieses ADR. Die Alternative
(beide gegen den ungekollabierten Stand, aber weiter getrennt) hätte
**Spaltenüberschriften und Zahlen auseinanderlaufen** lassen — richtige
Überschrift, falsche Zahl darunter, die schwerere Fehlerklasse.

Aufgelöst wird der Zielkonflikt nicht durch Abwägen, sondern durch Beseitigen
seiner Ursache: **eine** Auflösung aus dem ungekollabierten Stand
(`_dc_uncollapsed`, für dasselbe Problem bereits 2026 bei der SMS eingeführt,
#1575 Scheibe 3), explizit durchgereicht als
`render_email(outlook_metrics=…)` → `render_html`/`render_plain`. Die Renderer
lösen nicht mehr selbst auf. Ein Versatz ist damit strukturell ausgeschlossen,
nicht bloß unwahrscheinlich.

Die verbleibende zweite Auflösung in `build_outlook_row()` ist benannt und
begründet: die Zellwerte entstehen zur Aggregationszeit aus
`SegmentWeatherSummary`, das nicht zum Renderer reist. Sie liest dieselbe
Funktion und denselben ungekollabierten Stand und liegt in derselben Schicht
wie der Spaltenbau.

**5. Die falsche Legende wird richtiggestellt.** Die HTML-Legende bezeichnete
die Spalte `N` als „Nacht-Tief". Gemessen ist der Wert das **Tages**-Minimum
innerhalb des Wanderfensters: `temp_lo` ← `summary.temp_min_c`
(`outlook.py:459`) ← `aggregate_stage()` MIN über die Segment-Minima
(`weather_metrics.py:1252-1253`) ← `_compute_temperature` über die Zeitreihe des
Segments, dessen Fenster ab `stage.start_time` (Default 08:00) bis zur letzten
Wegpunkt-Ankunft läuft. Die Nachtdaten sind ein eigener, hier nicht
einfließender Datensatz (`_fetch_night_weather()`). Bei aktiver Auswahl
entfällt die Abkürzungs-Legende ganz — die Spaltenköpfe tragen dann
ausgeschriebene Bezeichnungen.

## Divergenz zum Ortsvergleich — bewusst, nicht übersehen

Nach dieser Lieferung verhalten sich Trip und Ortsvergleich **unterschiedlich**:
Der Trip-Ausblick wird gegen die Grundauswahl geschnitten (Punkt 3), der
Compare-Ausblick führt weiterhin eine unabhängige Liste ohne jeden Schnitt
(`resolve_outlook_metrics()` kennt kein globales Maximum).

Das ist die Folge von Punkt 3 und keine Auslassung: Der PO-Entscheid zur
Kaskade (#1719, ADR-0050) erging für den Trip, und der Auftragstext zu #1720
verlangt ihn dort ausdrücklich. Der **Code** bleibt geteilt (Resolver,
Renderer, Bedienelement); offen ist allein die **Semantik**.

Wer den Ortsvergleich später nachziehen will: Der Schnitt sitzt bewusst
**außerhalb** von `resolve_outlook_metrics()`, damit der Compare-Pfad unberührt
bleibt. Eine Vereinheitlichung muss ihn **hineinziehen**, nicht danebenlegen.

## Folgen

- Bestandstrips ohne Bedienung der neuen Fläche bleiben byte-identisch —
  zugesichert (AC-1), gemessen am echten Versandpfad gegen eine vor der
  Lieferung aufgezeichnete Referenz.
- `UnifiedWeatherDisplayConfig` bekommt ein Feld; Lesen **und**
  Zurückschreiben in `loader.py` sind feld-explizit und müssen beide ergänzt
  werden. Das Zurückschreiben ist bedingt — sonst ginge die Drei-Werte-Semantik
  verloren und jeder Trip bekäme nach dem ersten Speichern ein explizites
  `outlook_metrics`, auch ohne dass der Nutzer die Fläche je berührt hat.
- **Go bleibt unberührt.** `display_config` ist `map[string]interface{}`
  (`internal/model/trip.go:111`), `mergeConfigMap` merged feldweise.
- Der Picker lädt `get_compare_metric_catalog()` / `GET /api/compare/metrics` —
  dieselbe Quelle, gegen die der Resolver validiert. Andernfalls böte die
  Oberfläche Größen an, die der Resolver anschließend still verwirft.
  `confidence_pct` bleibt damit unwählbar (PO-Entscheid #710); die ACC-Spalte
  **ist** diese Größe.
- **Kompakt-Mail und Telegram folgen in Scheibe 2** und zeigen bis dahin
  unverändert ihre festen Spalten. Bis dahin trägt der Abschnitt den Hinweis
  „Erscheint nur in der E-Mail". Beide haben **keinen** Byte-Wächter
  (`metric_output_matrix.md:237-243`) — Scheibe 2 legt deshalb zuerst einen
  Charakterisierungstest des Ist-Zustands an, bevor sie etwas ändert.
- Der stärkste Bestandswächter des Trip-Ausblicks,
  `tests/tdd/test_trip_outlook_parity.py`, ruft die Renderer **isoliert** auf
  und durchläuft die neue Verdrahtung nie — belegt durch eine Mutation, die ihn
  grün ließ, während vier andere Tests rot wurden. Wer künftig an dieser Stelle
  arbeitet, darf ihn nicht als Absicherung der Aufrufstelle missverstehen.
