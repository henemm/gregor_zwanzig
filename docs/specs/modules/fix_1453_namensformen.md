---
entity_id: fix_1453_namensformen
type: bugfix
created: 2026-08-02
updated: 2026-08-02
status: draft
version: "1.0"
tags: [metric-catalog, compare, trip-mail, validator, weather-metrics-tab, issue-1453]
workflow: fix-1453-mail-deutsche-namen
---

<!-- Issue #1453 — Namensformen ordnen (Kurzform englisch, ausgeschriebener Name deutsch) -->

# Namensformen ordnen: Kurzform englisch wo wenig Platz ist, ausgeschriebener Name deutsch wo Platz ist (Issue #1453)

## Approval

- [x] Approved — PO Henning, 2026-08-02 („go")

## ⚠️ Ticket-Titel und ursprünglicher Ticket-Text sind überholt

Issue #1453 forderte ursprünglich „Mail wieder deutsch beschriften". **Diese
Forderung ist zurückgezogen.** Maßgeblich ist die PO-Entscheidung vom
2026-08-02 (Issue-Kommentare):

> **Wo wenig Platz ist, steht die englische Fachkurzform. Wo Platz ist, steht
> der ausgeschriebene deutsche Name.**

Begründung wörtlich: „Das Produkt richtet sich an Profis. Die internationale
Sprache ist Englisch. Daher sind die SMS-Kürzel ja bereits englisch. Ich
finde es sehr logisch, einfache englische Sprache zu verwenden und
Fachbegriffe dort, wo sie der Klarheit dienen."

Diese Spec setzt ausschließlich diese Regel um — nicht den ursprünglichen
Ticket-Wortlaut. Die frühere PO-Entscheidung #862/#849 („Spaltenköpfe bleiben
bewusst englisch") wird dabei **bestätigt**, nicht aufgehoben (Details im
Abschnitt „Bestätigte Vorentscheidung").

## Purpose

Zwei Kürzel im zentralen Wetter-Namensregister sind fachlich schlecht
gewählt (`Cond°` statt „Dew" für Taupunkt, `hPa` als Einheit statt Name für
Luftdruck) und werden korrigiert. Die Übersichtstabelle der Vergleichs-Mail
bekommt an der Zeilenbeschriftung — wo praktisch unbegrenzt Platz ist — die
ausgeschriebenen deutschen Namen aus dem Register statt der englischen
Kurzform, die dort seit #1401 Scheibe A2b steht. Der Pflicht-Prüfer
`email_spec_validator.py`, der seit #1404/#1420 beide Formen parallel
akzeptiert (Übergangs-Union), wird auf genau die jetzt geltende Form
zurückgebaut. Und die Konfigurationsoberfläche zeigt künftig in allen vier
Editoren (Tour + drei Compare-Flächen) je Wettergröße alle drei Namensformen
nebeneinander, damit ein Kürzel in einer Mail oder SMS immer an einer Stelle
auflösbar ist.

## Source

> **Schicht-Hinweis:** Diese Lieferung betrifft **Python-Core** (Namensregister,
> Compare-Renderer, Pflicht-Prüfer) UND **Frontend** (vier
> Wetter-Metriken-Editoren). Kein Go-Anteil.

- **File:** `src/app/metric_catalog.py` — **Identifier:** `MetricDefinition.col_label`
  (Einträge `dewpoint`, `pressure`), `label_de`, `aggregation_label_de()`
- **File:** `src/output/renderers/email/compare_html.py` — **Identifier:**
  `derive_row_labels()` (`:425-449`) — die einzige Lesestelle für
  Zeilen-/Spaltenbeschriftung im gesamten Compare-Pfad (HTML **und** Klartext,
  s. Dependencies)
- **File:** `.claude/hooks/email_spec_validator.py` — **Identifier:**
  `_HOUR_COLUMNS_V2` (`:576-589`), `_OVERVIEW_METRIC_CHECKS` (`:657-725`),
  `_OVERVIEW_NO_CHECK_LABELS` (`:759ff`), beide `_REVIEW_DATE`-Marker
  (`:605`, `:734`)
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` —
  **Identifier:** `compareMetricById` (`:822-831`)
- **File:** `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte`
  — Grundauswahl-Aufbau (`:116-124`)
- **File:** `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte`
  — Grundauswahl-Aufbau (`:65-73`)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte`
  — bestehendes Vorbild (`col_label`-Badge, `:80-81`), ggf. Erweiterung um
  sms_code

## Estimated Scope

- **LoC:** ~120–170 Produktivcode + ~150–220 Testcode (Anpassung der zwölf
  Bestandstests mit `Cond°`/`hPa`-Referenzen + Validator-Rückbau + neuer
  Register-Herkunfts-Test + Struktur-Tests je Editor) + ~90–140 Doku-Zeilen
  (diese Spec, ADR, Kontext-Nachtrag). **Gesamt ~360–530 Zeilen**; auf den
  250er-Rahmen zählen Produktivcode **und** Tests, `docs/`/`*.md` nicht — ein
  Override ist bei dieser Größenordnung wahrscheinlich nötig und braucht vor
  Implementierungsbeginn ausdrückliche PO-Freigabe (kein Automatismus).
- **Files:** ~4 Kern-Produktivdateien (`metric_catalog.py`, `compare_html.py`,
  `email_spec_validator.py`, mindestens 1 Compare-Editor-Komponente,
  realistisch alle 3 + `WeatherV2Reihenfolge.svelte` = 7), ~12+ Testdateien
  betroffen (s. Nachweisführung).
- **Effort:** medium — die einzelnen Änderungen sind lokal klein, der
  Aufwand liegt im widerspruchsfreien Rückbau der Übergangs-Union (Befund 7)
  und in der Wiederholung derselben Darstellungs-Logik über vier Editoren
  (Punkt 4), ohne dabei eine fünfte Vokabular-Kopie zu erzeugen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py::MetricDefinition.col_label`/`label_de` | READ+MODIFY | Register bleibt einzige Quelle für alle drei Namensformen; nur zwei `col_label`-Werte ändern sich |
| `src/app/metric_catalog.py::aggregation_label_de()` | READ | Liefert die deutsche Auswertungs-Ergänzung (Minimum/Maximum/Mittel/Summe) — Vorbild `compare_outlook_metric_ids.py:110-115` |
| `src/output/renderers/email/compare_html.py::derive_row_labels()` | MODIFY | Einzige Beschriftungsquelle für Übersicht (Zeilenkopf) UND Stundentabelle (Spaltenkopf) — muss künftig zwei Formen liefern können, ohne die zweite Verwendung zu brechen |
| `src/output/renderers/comparison.py::render_compare_plain()` | READ (Verbraucher, unverändert) | Importiert `derive_row_labels` bereits aus `compare_html.py` (Zeile 218/240) — Klartext folgt automatisch, wenn die Quelle korrekt ist; kein zweiter blinder Fleck |
| `src/output/renderers/comparison.py::_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS` | READ-only (NICHT als Quelle nutzen) | Bereits vorhandene deutsche Strings, aber Telegram/SMS-Vokabular — Risiko: eine dritte Namenskopie, wenn hieraus statt aus `label_de` gelesen wird |
| `helpers.py::visible_cols()` (Tour) / `metric_catalog.get_col_defs()` | READ (unverändert) | Tour-Pfad ist komplett getrennt von Compare, bekommt die beiden `col_label`-Änderungen aber automatisch mit, weil er dieselbe Registerquelle liest |
| `.claude/hooks/email_spec_validator.py` | MODIFY (geschützter Bereich) | Pflicht-Prüfer für Vergleichs-Mails; Änderung braucht ausdrückliche Nutzer-Freigabe (`override`), s. „Nachweisführung" |
| `.claude/hooks/briefing_mail_validator.py` | READ (unverändert) | Leitet Spaltenlabels bereits dynamisch aus `col_label` ab (kein hartcodiertes `Cond°`/`hPa`) — zieht die zwei Kürzel-Änderungen ohne eigenen Eingriff mit |
| `api/routers/config.py::GET /api/metrics` | READ (unverändert) | Liefert bereits `label` (=`label_de`), `col_label`, `sms_code` je Größe — Datenquelle für Punkt 4 existiert |
| `src/output/renderers/compare_metric_catalog.py::get_compare_metric_catalog()` | READ | Liefert für `/api/compare/metrics` bisher nur `label` (deutsch) — `col_label`/`sms_code` fehlen hier; Frontend lädt `/api/metrics` im Compare-Kontext aber bereits zusätzlich (für die Stundenverlauf-Beschriftung, Kommentar `WeatherMetricsTab.svelte:818-821`) — die Daten sind clientseitig schon vorhanden, es fehlt nur die Verknüpfung |
| `tests/unit/test_compare_mail_labels_from_register.py` | READ (Vorbild) | Zeigt das Muster für einen Register-Herkunfts-Test (AC-8) |

## Implementation Details

### 1. Zwei Kürzel korrigieren (`Cond°`→`Dew`, `hPa`→`Press`)

In `metric_catalog.py`: `dewpoint.col_label` von `"Cond°"` auf `"Dew"`,
`pressure.col_label` von `"hPa"` auf `"Press"`. `CAPE` bleibt unverändert
(PO-Entscheid, internationaler Fachbegriff).

Diese Änderung trifft **eine** Registerspalte, die von zwei getrennten
Pfaden gelesen wird (Befund 2 im Kontext): dem Compare-Stundenverlauf
(`compare_html.HOUR_METRICS`) **und** dem Tour-Stundenverlauf
(`helpers.visible_cols` → `metric_catalog.get_col_defs()`). Beide Mails
zeigen danach „Dew"/„Press" statt „Cond°"/„hPa" — das ist gewollt (ein
schlechtes Kürzel ist in beiden Mails schlecht), heißt aber: Tour-Golden-
Dateien unter `tests/golden/email/*` müssen geprüft und, falls die beiden
Größen dort aktiv sind, mitgezogen werden.

### 2. Übersichtstabelle: ausgeschriebene deutsche Namen

`derive_row_labels()` (`compare_html.py:425-449`) ist die einzige
Beschriftungsquelle für **zwei** unterschiedliche Ausgaben: die
Übersichtstabelle (`_visible_metrics()`, Zeilenkopf) und die Stundentabelle
(`_visible_hour_metrics()`, Spaltenkopf). Nach Punkt 1 dieser Lieferung soll
die Übersicht **deutsch** (`label_de`), die Stundentabelle weiter
**englisch** (`col_label`) beschriften — dieselbe Funktion muss also künftig
zwei Formen liefern können, ohne dass der zweite Aufrufer (Stundentabelle)
mitgeändert wird.

Quelle der deutschen Form ist ausschließlich `get_metric(metric_id).label_de`
— **nicht** `comparison._PLAIN_ROWS`/`_DAILY_PLAIN_ROWS` (Befund 4: das ist
eine andere, für Telegram/SMS gepflegte Kopie desselben Vokabulars; sie als
Quelle zu nutzen erzeugte eine dritte Namenskopie, genau das Risiko, das
Befund 4 benennt).

Der Klartext-Teil derselben Mail liest `derive_row_labels()` bereits aus
demselben Import (`comparison.py:33`, Zeile 218/240) — richtig implementiert,
zieht die Änderung dort automatisch mit; ein eigener Nachweis für den
Klartext-Teil bleibt trotzdem Pflicht (AC-3), weil `tests/unit/
test_compare_mail_plaintext_html_label_parity.py` genau diese Kopplung
festnagelt und ein Fix, der nur den HTML-Pfad träfe, dort auffiele.

### 3. Kollisionsregel auf Deutsch umstellen

`derive_row_labels()` hängt heute bei mehrdeutigen Kurzformen (Temperatur
max/min, gefühlte Temperatur max/min — beide teilen sich einen `metric_id`
und damit dieselbe Kurzform) den **rohen** `aggregation`-Wert an (`"Temp
max"`). Für die deutsche Übersicht muss stattdessen `aggregation_label_de()`
verwendet werden — Vorbild ist exakt derselbe Mechanismus im 3-Tages-Ausblick
(`compare_outlook_metric_ids.py:110-115`, dort bereits mit
Docstring-Begründung dokumentiert). Ergebnis: „Temperatur Maximum" /
„Temperatur Minimum" statt „Temp max" / „Temp min".

Für die Stundentabelle bleibt die alte (rohe) Kollisionslogik irrelevant —
dort ist laut Befund 5 jede `metric_id` genau einmal vertreten, der Fall
tritt nie ein.

### 4. Pflicht-Prüfer auf genau eine Form zurückbauen

`.claude/hooks/email_spec_validator.py` führt seit #1404/#1420 eine
**Übergangs-Union**: an zwei Stellen stehen sowohl die alten deutschen als
auch die neuen englischen Beschriftungen parallel als gültig, markiert durch
je einen `_REVIEW_DATE`-Merker (`:605`, `:734`). Diese Lieferung beendet die
Übergangszeit in beide Richtungen zugleich — nicht durch Rückkehr zu den
alten (abgekürzten) deutschen Strings, sondern durch die **neue** Zielform
aus Punkt 2/3 (volle `label_de`-Namen inkl. der zwei deutschen
Kollisionsformen):

- `_HOUR_COLUMNS_V2` (`:576-589`): die sechs handgetippten Alt-Literale
  (`"Gef.", "Böen", "Regen", "Gew.", "Regen-W.", "Sicht"`) entfallen. Die
  bereits registerabgeleitete Liste `_HOUR_VALUE_COLUMN_LABELS` bleibt
  unverändert bestehen und zieht `Dew`/`Press` automatisch nach (Punkt 1).
- `_OVERVIEW_METRIC_CHECKS` (`:657-725`): die 20 englischen A2b-Zielformen
  sowie die 2 englischen Kollisionsformen (`"Temp"`, `"Feels"`) entfallen;
  die deutschen Formen bleiben bzw. werden dort, wo sie kollisionsbedingt
  einen Zusatz brauchen, auf die volle Form (`"Temperatur Maximum"` statt
  `"Temp max"`) umgestellt — **nicht** unverändert aus der Übergangs-Union
  übernommen, weil deren deutsche Einträge selbst noch die alte,
  abgekürzte Rohform trugen.
- `_OVERVIEW_NO_CHECK_LABELS`: die zwei A2b-Gegenformen `"Thdr"`/`"PType"`
  entfallen (die deutschen Enum-Beschriftungen „Gewitter"/„Niederschlagsart"
  bleiben ausgenommen).
- Beide `_REVIEW_DATE`-Marker werden aufgelöst — sie waren reine
  Erinnerungs-Marker ohne Verhaltensschalter und haben mit dem Rückbau ihren
  Zweck erfüllt.

Diese Datei liegt in einem geschützten Bereich (Renderer-Commit-Gate #811 /
Hook-Verzeichnis). Der Entwickler-Agent braucht für den Zugriff eine
ausdrückliche Nutzer-Freigabe (`override`) — das ist erwartetes Verhalten,
kein Blocker, und sollte nicht überraschen.

### 5. Konfiguration: alle drei Formen je Größe, in allen vier Editoren

Alle drei Formen sind bereits ausgeliefert (`GET /api/metrics` führt
`label`/`col_label`/`sms_code` je Größe, `api/routers/config.py:71-81`) —
Punkt 4 ist eine **Darstellungs**-Aufgabe, keine Datenaufgabe. Heute zeigt
nur `WeatherV2Reihenfolge.svelte` (Touren-Editor) den `col_label`-Wert als
Badge neben dem deutschen Namen; die drei Compare-Editoren
(`WeatherMetricsTab.svelte` Übersicht, `CompareHourlyLayoutControls.svelte`,
`CompareOutlookLayoutControls.svelte`) bauen ihre Zeilen-Einträge ohne
`col_label`/`sms_code` auf. `WeatherMetricsTab.svelte` lädt den
`/api/metrics`-Katalog im Compare-Kontext bereits zusätzlich (für die
Stundenverlauf-Beschriftung, Kommentar Zeile 818-821) — die Werte sind im
Frontend also schon vorhanden, es fehlt die Verknüpfung zur jeweiligen
Zeile.

**Offene Gestaltungsfrage, ausdrücklich nicht Teil dieser Spec:** ob die
Auflösung (deutsch · englisch · SMS) in jeder Zeile steht oder als
ausklappbare Legende am Ende des Reiters erscheint. Beide Varianten werden
dem PO am fertigen Bildschirm gezeigt; die Entscheidung fällt dort, nicht
hier.

## Bestätigte Vorentscheidung

Die frühere PO-Entscheidung #862/#849 (`docs/specs/_archive/modules/
fix_862_849_col_labels.md:58`: „Spaltenköpfe bleiben bewusst englisch") wird
durch diese Spec **bestätigt, nicht aufgehoben**. Sie galt für die
Stundentabelle und gilt dort unverändert weiter. Diese Lieferung präzisiert
nur, dass dieselbe Grundregel — Kurzform bei wenig Platz — für die
Übersichtstabelle **nicht** gilt, weil dort (anders als 2026-06-23
angenommen) praktisch unbegrenzt Platz zur Verfügung steht (Befund 3). Beide
Entscheidungen sind zwei Anwendungen derselben, jetzt explizit gemachten
Regel „Form folgt Platz", nicht widersprüchlich.

## Was sich ausdrücklich NICHT ändert

- Die Stundentabelle bleibt bei den englischen Kurzformen — mit genau zwei
  Ausnahmen (`Dew`, `Press`), s. Punkt 1. Alle übrigen ~20 Kürzel
  (`Temp`, `Wind`, `Gust`, `Rain`, `CAPE`, `Cloud`, `CldLow`, … usw.) bleiben
  zeichengleich.
- `MetricDefinition.sms_code` — SMS-Kürzel sind ein eigenes, bereits
  englisches Protokoll und nicht Gegenstand dieser Änderung.
- `MetricDefinition.compact_label` — internes Kürzel für andere Ausgaben
  (Trip-SMS/Formatierung), unberührt.
- Die Sprache der Bedienoberfläche selbst (Buttons, Überschriften, Hilfetexte)
  — die bleibt deutsch, das war nie strittig.
- Der 3-Tages-Ausblick derselben Vergleichs-Mail — der ist bereits deutsch
  und bereits das Vorbild für Punkt 2/3 dieser Lieferung
  (`compare_outlook_metric_ids.py:78-115`).

## Acceptance Criteria

- **AC-1 (Nicht-Regression Stundentabelle):** Given ein Nutzer öffnet eine
  Vergleichs- oder Tour-Mail mit Stundentabelle / When er die
  Spaltenüberschriften ansieht / Then stehen dort weiterhin die englischen
  Kurzformen — unverändert bis auf die zwei in AC-2 genannten Spalten.
  - Test: Bestehende Golden-/Struktur-Tests der Stundentabelle laufen
    unverändert grün, bis auf die gezielt angepassten Dew/Press-Fälle.

- **AC-2:** Given eine Vergleichs- oder Tour-Mail zeigt die
  Taupunkt-Spalte bzw. die Luftdruck-Spalte im Stundenverlauf / When die
  Spaltenüberschrift gerendert wird / Then heißt sie „Dew" bzw. „Press"
  (nicht mehr „Cond°"/„hPa") — in beiden Mail-Typen gleich.
  - Test: echter Staging-Versand je Mail-Typ mit aktiver Taupunkt-/
    Luftdruck-Spalte, IMAP-Abruf, Header-String geprüft; Tour-Golden-Dateien
    auf Betroffenheit geprüft und bei Bedarf mitgezogen.

- **AC-3:** Given ein Nutzer öffnet die Übersichtstabelle einer
  Vergleichs-Mail / When er die Zeilenbeschriftungen liest — sowohl im
  HTML-Teil als auch im Klartext-Teil derselben Mail / Then steht dort der
  ausgeschriebene deutsche Name der Wettergröße statt der bisherigen
  englischen Kurzform.
  - Test: Staging-Versand, IMAP-Abruf, Zeilenbeschriftung im HTML- mit dem
    Klartext-Teil derselben Mail verglichen (nicht nur „hat sich geändert").

- **AC-4:** Given die Übersichtstabelle zeigt gleichzeitig Temperatur-Maximum
  und -Minimum bzw. gefühlte Temperatur Maximum und Minimum / When beide
  Zeilen sichtbar sind / Then tragen sie unterscheidbare, vollständig
  deutsche Bezeichnungen („Temperatur Maximum"/„Temperatur Minimum") statt
  einer gekürzten Form mit rohem Auswertungscode.
  - Test: Fixture mit beiden Zeilen gleichzeitig aktiv, gerenderte
    Beschriftung beider Zeilen geprüft.

- **AC-5:** Given die **Stundentabelle** zeigt die Gewitterenergie-Spalte /
  When die Mail nach dieser Änderung gerendert wird / Then trägt sie
  unverändert `CAPE` — kein Übersetzungsversuch. In der **Übersichtstabelle**
  erscheint dieselbe Größe als `Gewitterenergie (CAPE)`, weil dort der
  ausgeschriebene Name gilt; der Fachbegriff bleibt darin erhalten.
  - Test: Stundenkopf wörtlich `CAPE`; Übersichtszeile wörtlich
    `Gewitterenergie (CAPE)` (= `label_de`).

  **Präzisierung 2026-08-02 (RED-Phase).** Die erste Fassung lautete
  „Übersichtstabelle **oder** Stundentabelle … bleibt unverändert `CAPE`" und
  widersprach damit AC-3, das für die Übersicht `label_de` fordert. Der
  Widerspruch war eine Unschärfe im Wortlaut, kein Zielkonflikt: `CAPE` ist
  eine **Kurzform** und gilt deshalb dort, wo Kurzformen gelten — in der
  Stundentabelle. Die Regel dieser Spec entscheidet nach Platz, nicht nach
  Sprache, und der Fachbegriff geht in keiner der beiden Formen verloren.

- **AC-6 (Pflicht-Prüfer):** Given eine zugestellte Vergleichs-Mail trägt die
  neuen deutschen Übersichtsnamen und die zwei umbenannten Stundenspalten /
  When `email_spec_validator.py` gegen diese Mail läuft / Then meldet er
  Exit 0; eine Mail mit einer **Stundenspalte** in alter oder erfundener Form
  wird weiterhin abgelehnt und die Spalte beim Namen genannt.
  - Test: Validator-Lauf gegen eine echte Staging-Mail mit der neuen Form
    (Exit 0) UND gegen eine präparierte Mail mit alter bzw. erfundener
    **Stundenspalte** (Exit ≠ 0, mit benannter Fundstelle).
  - Für die **Übersichtsbeschriftungen** ist der Nachweis struktureller Art:
    die alte Form ist nach der Lieferung nicht mehr in der bekannten Menge
    des Prüfers enthalten.

  **Präzisierung 2026-08-02 (RED-Phase).** Die erste Fassung verlangte, der
  Prüfer solle auch eine **alte Übersichtsform** aktiv ablehnen. Das ist mit
  seinem heutigen Aufbau **nicht möglich**: eine unbekannte
  Übersichtsbeschriftung überspringt er stillschweigend (`continue`-Pfad),
  ausdrücklich als Known Limitation von #1420 dokumentiert und von einem
  Bestandstest festgenagelt. Ein AC, das eine strukturell unerfüllbare
  Ablehnung fordert, wäre nie abnehmbar. Die aktive Ablehnung wird deshalb
  dort geprüft, wo es sie gibt — bei den Stundenspalten. Den `continue`-Pfad
  zu schließen ist eine eigene Änderung am Prüfer und **nicht** Teil dieser
  Lieferung.

- **AC-7 (Konfiguration zeigt alle drei Formen):** Given ein Nutzer öffnet
  den Reiter „Wetter-Metriken" — im Touren-Editor oder in einer der drei
  Compare-Flächen (Übersicht, Stundenverlauf, Ausblick) / When er eine
  Wettergröße betrachtet / Then findet er zu dieser Größe alle drei
  Namensformen (ausgeschriebener deutscher Name, englische Kurzform,
  SMS-Kürzel) — nicht nur im Touren-Editor wie bisher.
  - Test: Struktur-/Component-Test je der vier Editoren, der das
    Vorhandensein aller drei Werte an mindestens einer Zeile nachweist.

- **AC-8 (keine dritte Namenskopie):** Given die deutschen Übersichtsnamen
  sind ausgeliefert / When ein Test prüft, woher eine Zeilenbeschriftung
  stammt / Then kommt sie nachweislich aus dem zentralen Register
  (`label_de` über `get_metric()`) — nicht aus einer separaten, getippten
  Liste.
  - Test: Register-Herkunfts-Test analog `tests/unit/
    test_compare_mail_labels_from_register.py` — Manipulation des
    Registerwerts einer Testgröße muss sich sichtbar in der gerenderten
    Übersichtszeile niederschlagen.

## Nachweisführung

Das Renderer-Commit-Gate (#811) greift, sobald `compare_html.py` gestaged
wird — Reihenfolge beachten:

1. `metric_catalog.py`-Änderung (Punkt 1) und `email_spec_validator.py`-
   Rückbau (Punkt 4) sind unabhängig prüfbar (kein Mailversand nötig) und
   können zuerst verifiziert werden.
2. Compare-Test-Mail über `scripts/send_gate_test_mails.py --only compare`
   an `gregor-test@henemm.com` — **ein** Versand (Kontingent-Schonung,
   #1329), IMAP-Abruf.
3. `.claude/hooks/email_spec_validator.py` gegen die zugestellte Mail —
   Exit 0 ist Pflichtbedingung für „E2E bestanden" (AC-6).
4. Bei Punkt 1 (Dew/Press) zusätzlich prüfen, ob eine Tour-Mail mit aktiver
   Taupunkt- oder Luftdruck-Spalte betroffen ist — falls ja, eigener
   Testversand über den Tour-Pfad (`briefing_mail_validator.py`) und
   Abgleich der Tour-Golden-Dateien.
5. Zahl-für-Zahl-/Text-für-Text-Vergleich der Übersichtszeilen zwischen
   HTML- und Klartext-Teil derselben Mail (AC-3) — nicht nur „Feld hat sich
   geändert".

## Known Limitations

- **Es sind zwei rote Bestandstests, nicht fünf** — die im Ticket genannte
  Zahl stammt aus einem veralteten `.pytest_cache/lastfailed`-Stand
  (Befund 6). Real:
  - `test_compare_mail_overview_plausibility_coverage.py::
    test_ac4_exemption_set_is_declared_and_complete` — Ursache ist exakt die
    Übergangs-Union, die diese Lieferung abbaut; **fällt mit dieser
    Lieferung weg**, ohne eigenen Fix.
  - `tests/tdd/test_mail_alert_dedup.py::
    test_ac5_same_hazard_different_region_not_collapsed` — Ursache liegt in
    `compare_html.py:504` (`visual_key` ohne Gebietsbezug) und **gehört zu
    #1451**. Diese Spec berührt diesen Test nicht und lässt ihn bewusst rot.
- Die offene Gestaltungsfrage aus Implementation Details Punkt 5 (Zeile vs.
  Legende) wird hier nicht entschieden — beide Varianten gehen an den PO.
- `/api/compare/metrics` (`get_compare_metric_catalog()`) liefert weiterhin
  nur den deutschen Namen, kein `col_label`/`sms_code` — die Konfigurations-
  Anzeige (AC-7) kann das clientseitig aus dem ohnehin geladenen
  `/api/metrics`-Katalog beziehen; eine Erweiterung der Compare-API selbst
  ist keine Voraussetzung dieser Lieferung, aber ein möglicher Lösungsweg.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0042 (vorzuschlagen, nächste freie Nummer nach 0041 —
  noch nicht angelegt).
- **Titel-Vorschlag:** „Namensform von Wettergrößen folgt der Platzgrenze,
  nicht einer pauschalen Sprachpräferenz (bestätigt #862/#849, Issue #1453)"
- **Rationale (3–5 Sätze, eigenständig verständlich):** Jede Wettergröße im
  Produkt trägt drei Namensformen — einen ausgeschriebenen deutschen Namen,
  eine englische Fachkurzform und ein SMS-Kürzel. Welche Form an welcher
  Stelle erscheint, folgt einer einzigen Regel: wo wenig Platz ist (SMS,
  Stundentabellen-Spaltenkopf), steht die englische Kurzform; wo Platz ist
  (Übersichtstabellen-Zeilenkopf, 3-Tages-Ausblick, Bedienoberfläche), steht
  der ausgeschriebene deutsche Name. Grund ist nicht Ästhetik, sondern die
  Zielgruppe: Profis, für die Englisch die international übliche Fachsprache
  ist — die SMS-Kürzel sind aus genau diesem Grund bereits englisch. Diese
  Regel ersetzt keine frühere Entscheidung, sondern macht explizit, was in
  #862/#849 implizit nur für die Stundentabelle galt: „Kurzform bleibt
  englisch" ist eine Platzregel, keine Aussage über die Übersichtstabelle
  oder andere Flächen mit viel Platz.

## Test-Plan

Kern-Schicht (deterministisch), Testdateien nach Verhalten benannt:

| AC | Testfall |
|----|----------|
| AC-1 | bestehende Stundentabellen-Golden-/Struktur-Tests bleiben grün (außer Dew/Press) |
| AC-2 | Staging-Versand (Compare + Tour) + IMAP + Header-Vergleich, s. „Nachweisführung" |
| AC-3 | Staging-Versand + IMAP + HTML-vs-Klartext-Vergleich der Übersichtszeilen |
| AC-4 | Fixture-Test: Temperatur max+min gleichzeitig sichtbar, Label-Ausgabe geprüft |
| AC-5 | bestehende CAPE-Assertions unverändert grün |
| AC-6 | zwei Validator-Läufe: Positivfall (neue Form, Exit 0), Negativfall (alte/erfundene Form, Exit ≠0) |
| AC-7 | Struktur-/Component-Test je der vier Editoren (Tour, Compare-Übersicht, -Stundenverlauf, -Ausblick) |
| AC-8 | Register-Herkunfts-Test (Manipulation des Registerwerts schlägt sichtbar durch) |

**Renderer-Commit-Gate (#811):** greift, sobald `compare_html.py` gestaged
wird. Reihenfolge: erst `metric_catalog.py` + `email_spec_validator.py`
committen/verifizieren (unabhängig prüfbar), dann `email_spec_validator.py`
grün gegen eine Mail mit der neuen Form, erst dann Commit an
`compare_html.py`.

## Changelog

- 2026-08-02: Initial spec created — Issue #1453. Basiert auf
  `docs/context/fix-1453-mail-deutsche-namen.md` (acht Befunde) und der
  PO-Entscheidung vom 2026-08-02, die den ursprünglichen Ticket-Wortlaut
  („Mail wieder deutsch") ersetzt.
