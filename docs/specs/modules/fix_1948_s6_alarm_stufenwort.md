# Spec: #1948 S6 — Alarm spricht die Sprache des Briefings

```yaml
entity_id: alert_render
issue: 1948
slice: S6
created: 2026-08-20
status: approved
approved_by: PO Henning
approved_at: 2026-08-20
workflow: feat-1948-s6-telegram-paritaet
```

## Problem

Der **Änderungs-Alarm** ist die einzige Stelle im Produkt, die die interne Ordinalzahl der
Gewitterstufe (0–3) nach außen gibt. Gemessen am Prod-Stand `b31acb40`, Gewitter Stufe 2 → 3:

```
Betreff:   [KHW 403] km 0–4 · ↑ Gewitter: 2→3
E-Mail:    Gewitter +50% seit dem Briefing
           ↑ +50 % · Änderung über deiner Alarm-Schwelle (1)
           Gewitter · : 2 ↑ 3 +50 %
           Änderung 1: über Alarm-Schwelle 1 ✗
Telegram:  KHW 403 · km 0–4 · ↑ Gewitter
           Gewitter · Schwelle 1 · 2 ↑ 3 · Änderung über
SMS:       km 0-4: TH:M->H@15      ← spricht seit S3 sauber
```

Das Briefing nennt dieselbe Größe überall als deutsches Wort (`⚡ mittel`,
`Gewitter mittel ab 16:00`, `Starkes Gewitter erwartet ab 16:00`), die SMS als Buchstaben
(`TH:M`). Nur der Alarm zeigt `2`. Dazu rechnet er auf der Ordinalskala eine **prozentuale
Änderung** (`+50 %`), die keinen Sachverhalt bezeichnet, und dem Telegram-Alarm fehlt die
Stand-/Vergleichszeile, die die E-Mail führt.

## Ziel

Der Alarm spricht in **Betreff, E-Mail und Telegram** dasselbe Vokabular wie das Briefing.
Die SMS bleibt bei ihren Buchstaben. Prozent als berechnete Änderung verschwindet
vollständig; Prozent als **Einheit** bleibt unangetastet.

| | heute | nach S6 |
|---|---|---|
| Betreff, eine Änderung | `[KHW 403] km 0–4 · ↑ Gewitter: 2→3` | `[KHW 403] km 0–4 · ↑ Gewitter: mittel→hoch` |
| Betreff, mehrere | `… ↑ 2 über Schwelle: Gewitter 3, Gewitter 2` | `… ↑ 2 über Schwelle: Gewitter hoch, Gewitter mittel` |
| E-Mail-Überschrift | `Gewitter +50% seit dem Briefing` | `Gewitter mittel → hoch seit dem Briefing` |
| E-Mail-Badge | `↑ +50 % · Änderung über deiner Alarm-Schwelle (1)` | `↑ Änderung über deiner Alarm-Schwelle (1 Stufe)` |
| E-Mail-Datenzeile | `Gewitter · : 2 ↑ 3 +50 %` | `Gewitter · : mittel ↑ hoch` |
| E-Mail-Zeile 2 | `Änderung 1: über Alarm-Schwelle 1 ✗` | `Änderung 1 Stufe: über Alarm-Schwelle 1 Stufe ✗` |
| Telegram, eine Änderung | `Gewitter · Schwelle 1 · 2 ↑ 3 · Änderung über` | `Gewitter · Schwelle 1 Stufe · mittel ↑ hoch · Änderung über` |
| Telegram, mehrere | `Gewitter 🏁 Ziel · 16:00 2→3` | `Gewitter 🏁 Ziel · 16:00 mittel→hoch` |
| Telegram, Schlusszeile | — fehlt — | `Stand: heute 10:00 · verglichen mit 18:03` |
| Grenzwert-Alarm | `deine Grenze 1 ist gerissen — jetzt 3` | `deine Grenze leicht ist gerissen — jetzt hoch` |
| SMS | `km 0-4: TH:M->H@15` | **unverändert** |

## 🔴 Leitunterscheidung: Positionen vs. Abstände

In derselben Zeile stehen zwei Sorten Zahl, die gleich aussehen und Verschiedenes bedeuten.
Diese Unterscheidung trägt die halbe Spec:

| Wert | Bedeutung | Zielform |
|---|---|---|
| `value_from`, `value_to` | **Position** auf der Leiter | **Wort** (`mittel`, `hoch`) |
| Korridor `bound`, `value` | **Position** — `bound` ist die vom Nutzer gesetzte Bereichsgrenze auf der Skala selbst (`corridor.range[0]/[1]`, `corridor_threshold.py:104`), kein Abstand | **Wort** |
| `threshold` (Δ-Alarm) | **Abstand** — „ab 1 Stufe Unterschied alarmieren" | Zahl **+ Einheit „Stufe(n)"** |
| `abs(value_to − value_from)` | **Abstand** — „hat sich um 1 Stufe geändert" | Zahl **+ Einheit „Stufe(n)"** |

`Schwelle leicht` wäre eine **sachlich falsche Aussage**: ein Abstand von 1 ist nicht Stufe 1.

## Quellen der Wahrheit

- **Wörter:** `THUNDER_LABEL_DE` (`src/output/metric_format.py:283-288`) —
  `{NONE: "kein", LOW: "leicht", MED: "mittel", HIGH: "hoch"}`. **Importieren, nicht kopieren.**
- **Zahl → Enum:** `_THUNDER_JE_ORDINAL` (`src/output/metric_format.py:359`) =
  `{0: NONE, 1: LOW, 2: MED, 3: HIGH}`. Gemessen: `.get(4)` → `None`.
- **Weiche:** `_is_level_metric()` (`src/output/renderers/alert/render.py:110-116`), liest
  `MetricDefinition.is_level`. `thunder` ist die **einzige** Metrik mit `is_level=True`
  (`src/app/metric_catalog.py:446`; über alle 32 Katalogeinträge gemessen).

## Nicht-Ziele (ausdrücklich außerhalb dieser Scheibe)

- **SMS** — bleibt bei `LEVELS` (`src/output/tokens/metrics.py:14`). S3/S4/S5-Ergebnis, tabu.
- **Amtlicher Alarm** — eigener Renderer, S5 AC-13 hält seinen ausführlichen Text fest.
- **Radar-/Onset-Alarm** — führt keine Stufenzahl (`_render_email_onset` u. a., geprüft).
- **Trip-Briefing** — spricht bereits Wörter, rechnet nur absolute Differenzen.
- **`format_change_line()`** (`src/output/renderers/email/helpers.py:1086-1100`) — erzeugt bei
  %-Einheiten Texte wie `+34 %`. Das ist eine **Differenz in Prozentpunkten**, dieselbe Sorte
  Zahl wie `+3 °C`, keine Quote. Bleibt unverändert (Tech-Lead-Entscheid, PO informiert).
- **Legacy-Shim `render_deviation_alert`** (`render.py:1047-1069`) — kein Aufrufer in `src/`,
  eigener Footer, nur von drei Bestandstests gerufen. Nicht anfassen.
- **Ortsvergleich als Thema** — er zieht über die geteilten Renderer automatisch mit
  (`project.py:256-308` hat keinen eigenen Renderer-Code); es wird dort nichts eigens gebaut.
- **Zeitformatierung** (`local_fmt`, `%H:%M`) — mit Sitzung #2009 abgestimmt: nicht anfassen.

## Acceptance Criteria

**AC-1:** Given ein Änderungs-Alarm mit einem einzelnen `thunder`-Ereignis von Stufe 2 auf
Stufe 3, When die E-Mail gerendert wird, Then enthält die erste Datenzeile `mittel ↑ hoch`
und an keiner Stelle der Zeile die Ziffernfolge `2 ↑ 3`.

**AC-2:** Given derselbe Alarm, When der ausführliche Telegram-Text gerendert wird, Then
lautet die Metrik-Zeile `Gewitter · Schwelle 1 Stufe · mittel ↑ hoch · Änderung über`.

**AC-3:** Given ein Änderungs-Alarm mit mehreren Ereignissen, darunter `thunder` von Stufe 2
auf Stufe 3, When der ausführliche Telegram-Text gerendert wird, Then steht in der
Metrik-Zeile `mittel→hoch` und nicht `2→3`, während Nicht-Stufen-Metriken unverändert ihre
Messzahl mit Einheit behalten (z. B. `1.400→280 m`).

**AC-4:** Given derselbe Mehr-Ereignis-Alarm, When die E-Mail gerendert wird, Then trägt die
Gewitter-Zeile `mittel ↑ hoch` als Wertteil und `Änderung 1 Stufe · Schwelle 1 Stufe` im
Labelteil.

**AC-5:** Given ein Änderungs-Alarm mit `thunder`, When die Betreffzeile gerendert wird, Then
erscheint die Stufe als Wort und niemals als nackte Ordinalzahl — bei **einem** Ereignis
lautet der Betreff `[KHW 403] km 0–4 · ↑ Gewitter: mittel→hoch`, bei **mehreren** Ereignissen
trägt die Aufzählung der Bis-Werte die Wörter, also
`[KHW 403] Segment 1, 🏁 Ziel · ↑ 2 über Schwelle: Gewitter hoch, Gewitter mittel`.

**AC-6:** Given ein `thunder`-Alarm mit Änderungsschwelle 1, When irgendein Kanal gerendert
wird, Then erscheinen Schwelle und Änderungsbetrag als Zahl mit der Einheit `Stufe` bzw.
`Stufen` und **niemals** als Stufenwort — der Text `Schwelle leicht` darf in keiner Ausgabe
vorkommen. Dieses Kriterium ist ein Wächter gegen die naheliegende Fehlumsetzung.

**AC-7:** Given ein Grenzwert-/Korridor-Alarm auf `thunder` mit Grenze Stufe 1 und aktuellem
Wert Stufe 3, When E-Mail oder Telegram gerendert werden, Then lautet die Zeile
`Gewitter: deine Grenze leicht ist gerissen — jetzt hoch` — dort sind **beide** Werte
Positionen und daher **beide** Wörter.

**AC-8:** Given ein Änderungs-Alarm mit einem einzelnen Ereignis beliebiger Metrik, When
E-Mail HTML und Klartext gerendert werden, Then enthält weder die Überschrift noch der Badge
noch die Datenzeile eine berechnete prozentuale Änderung — die Zeichenfolgen `+50 %`,
`+50%`, `-60 %` und ihresgleichen kommen nicht mehr vor.

**AC-9:** Given ein Änderungs-Alarm mit einem einzelnen Ereignis, When die E-Mail-Überschrift
gerendert wird, Then nennt sie den Von- und den Bis-Wert statt der entfallenen Prozentzahl,
also `Gewitter mittel → hoch seit dem Briefing` bzw. `Niedersch 2,0 mm → 18,0 mm seit dem
Briefing`; die inhaltsleere Form `Gewitter seit dem Briefing` entsteht nicht mehr.

**AC-10:** Given eine Metrik, deren Katalog-Einheit `%` ist (z. B. Regenwahrscheinlichkeit),
When ein Alarm dafür in irgendeinem Kanal gerendert wird, Then bleibt das Prozentzeichen als
**Einheit** am Messwert erhalten (`60 % ↑ 90 %`, Betreff `90%`) — der Wegfall betrifft
ausschließlich die berechnete Änderung, niemals die Einheit.

**AC-11:** Given ein Änderungs-Alarm, When der ausführliche Telegram-Text gerendert wird,
Then schließt er mit derselben Stand-Zeile, die die E-Mail führt — bei **bekanntem**
Vergleichszeitpunkt `Stand: heute 10:00 · verglichen mit 18:03`, bei **fehlendem**
(`reference_at is None`) `Stand: heute 10:00 · verglichen mit dem letzten Briefing`. Beide
Fälle sind real erreichbar: der Ortsvergleich-Einzelpunkt und der Vorschau-Pfad reichen
`reference_at` nie durch (`project.py:411-424`, `validator_render_service.py:144-147`).

**AC-12:** Given ein Trip mit Telegram-Kurzstil, When ein Änderungs-Alarm versendet wird,
Then ist der gesendete Telegram-Text weiterhin **byte-identisch** mit dem SMS-Text und
enthält **keine** Stand-Zeile — die neue Zeile entsteht ausschließlich in `render_telegram`,
niemals in `render_sms`. Wächter gegen ein Auslaufen der Zeile in die Kurznachricht.

**AC-13:** Given ein `thunder`-Ereignis mit einem Wert außerhalb 0–3 (über den Vorschau-Pfad
erreichbar, der keinen Wertebereich prüft), When ein Kanal gerendert wird, Then fällt die
Darstellung auf die bisherige Zahlform zurück und meldet **niemals** `kein` — eine
Entwarnung für einen unbekannten Wert wäre eine sicherheitsrelevante Falschaussage.

**AC-14:** Given ein `thunder`-Alarm von Stufe 2 auf Stufe 3, When die SMS gerendert wird,
Then lautet sie unverändert `km 0-4: TH:M->H@15` — S6 ändert an der Kurznachricht nichts.

**AC-15:** Given ein Alarm für eine Metrik ohne Stufencharakter (alle 31 übrigen
Katalogeinträge), When irgendein Kanal gerendert wird, Then bleibt die Zahlformatierung
einschließlich Einheit, Tausenderpunkt und Nachkommastellen unverändert gegenüber dem
Prod-Stand `b31acb40`.

**AC-16:** Given ein Ortsvergleich-Änderungsalarm mit einem `thunder`-Ereignis, When E-Mail
und Telegram gerendert werden, Then erscheint die Stufe dort ebenso als Wort — die geteilten
Renderer bedienen Trip und Ortsvergleich, ohne dass ortsvergleich-eigener Code entsteht.

**AC-17:** Given ein `thunder`-Wert mit Nachkommaanteil, When er in ein Wort übersetzt wird,
Then greift **exakt** die bisherige Rundung (`round(v, 0)`, kaufmännisch-gerade
Bankersrundung), sodass 2,5 auf 2 rundet und damit `mittel` ergibt — **nicht** `hoch`. Die
Wort-Darstellung darf an keinem Wert eine andere Stufe treffen als die heutige Zahlform.

## Betroffene Dateien (erwartet)

| Datei | Was |
|---|---|
| `src/output/renderers/alert/render.py` | Kern: Wort-Weiche in `_val`/`_num`-Aufrufern, `Stufe(n)`-Einheit für Abstände, `_h1`-Ersatz, Prozent-Entfall, Stand-Zeile in `render_telegram` |
| `src/output/renderers/alert/model.py` | `delta_pct` entfällt (oder wird ungenutzt) |
| Tests | siehe unten |

## Regressionsfläche (Basislinie verifiziert grün: 50 passed)

**Wird bewusst nachgezogen:**
`test_978_deviation_line_readability.py:224,240,273,292,358,368` (Stufenwort; zwei Regexe
`(Gewitter) \d`) · `test_957_alert_mail_literal_structure.py:56,59` (Prozent) ·
`test_issue_1169_compare_alert_consumer.py:755-769` (byte-genau, Prozent) und `:770-773`
(byte-genau, Stand-Zeile) · `test_alert_multi_event_where_when.py:129-134`
(`splitlines()[-1]`).

**🔴 Muss grün bleiben — Trennlinie Einheit vs. Änderung:**
`test_channel_metric_matrix.py:2202-2220` und `:2174-2199` ·
`test_alert_change_amount_wording.py:290-303` · `test_952_alert_mail_design_fidelity.py:73`.

**Scheinwächter, nicht als Beweis verwenden:**
`test_957_alert_mail_literal_structure.py:46` (`"%" in html`) ist faktisch durch
`width="100%"` erfüllt (`render.py:588`) und bewacht die Trennlinie **nicht**.

## Mutations-Gegenproben (Pflicht im Adversary)

1. `THUNDER_LABEL_DE` durch eine lokale Kopie ersetzen → muss rot werden (SSoT-Bindung).
2. Wort-Weiche auch auf `threshold` anwenden (`Schwelle leicht`) → **AC-6** muss rot werden.
3. Rückfall für unbekannte Ordinalwerte auf `"kein"` setzen → **AC-13** muss rot werden.
4. Stand-Zeile zusätzlich in `render_sms` erzeugen → **AC-12** muss rot werden.
5. Prozent-Entfall auf die Einheit ausdehnen → **AC-10** muss rot werden.
6. Wort-Weiche für alle Metriken statt nur `is_level` → **AC-15** muss rot werden.

## Offene Punkte

- **Nebenbefund → #1199:** `Gewitter · :` — hängender Trenner, weil die Stufen-Metrik keine
  Einheit hat (`render.py:557`, `:740`). Nicht Teil dieser Scheibe.
- **Nebenbefund → #1199:** Der SMS-Zweig fällt für Werte außerhalb 0–3 auf `-` zurück
  (`render.py:856-857`) — **denselben Glyph wie Stufe 0**. Produktiv nicht erreichbar
  (`thunder_scale.py:48-57` liefert immer 0–3), über den Vorschau-Pfad schon.
- **Nebenbefund → #1199:** `_email_line` (`render.py:521-526`) ist falsch benannt — sie
  bedient ausschließlich Telegram.
