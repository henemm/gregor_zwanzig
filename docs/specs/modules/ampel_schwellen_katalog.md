---
entity_id: ampel_schwellen_katalog
type: module
created: 2026-07-28
updated: 2026-07-28
status: draft
version: "1.0"
tags: [ampel, schwellen, metric_catalog, issue-1377, epic-1374]
---

# Ampel-Schwellen im zentralen Katalog (Scheibe A)

Issue [#1377](https://github.com/henemm/gregor_zwanzig/issues/1377), Etappe S5 des
Ortsvergleich-Reworks (#1374/#1372). Scheibe A von zwei.

## Approval

- [x] Approved — PO-Freigabe 2026-07-28

## Purpose

Der zentrale Metrik-Katalog soll alle Warnschwellen führen, die Trip-Briefing und
Ortsvergleichs-Mail benötigen — mit den vom PO am 2026-07-28 festgelegten Werten. Heute fehlen
dort Temperatur und UV-Index ganz, die Sichtweite ist nur halb hinterlegt, und die Böen-Werte
weichen von dem ab, was die Mails tatsächlich zeigen.

Scheibe A schafft die Grundlage. Die Umstellung der Renderer auf diese Quelle ist Scheibe B.

## Source

- **File:** `src/app/metric_catalog.py` — `MetricDefinition.display_thresholds`
- **File:** `src/output/metric_format.py` — `severity_for`
- **File:** `src/output/renderers/email/helpers.py` — `_level_from_thresholds`
- **Schicht:** Python-Core (`src/app/`, `src/output/`)

## Estimated Scope

- **LoC:** ~90 (+75 / −15)
- **Files:** 3 Quelldateien + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog.get_metric` | upstream | liefert die Schwellen |
| `severity_for` | downstream | einziger künftiger Leser der Schwellen |
| `ampel_stage_tone` / `ampel_dot` | downstream | färben heute schon aus dem Katalog |

## Implementation Details

### 1. Schwellen im Katalog (PO-Entscheidung 2026-07-28)

| Metrik | Gelb | Orange | Rot | Art der Änderung |
|---|---|---|---|---|
| `gust` | 30 | 45 | 60 | **geändert** (bisher 50/65/80) |
| `visibility` | <2000 m | <1000 m | <500 m | **neu, invertiert** (bisher nur `orange_lt: 500`) |
| `temperature` | 28 / <0 | 31 / <−5 | 34 / <−15 | **neu, beidseitig** |
| `wind_chill` | 28 / <0 | 31 / <−5 | 34 / <−15 | **neu, beidseitig** — identisch zu `temperature` |
| `uv_index` | 3 | 6 | 8 | **neu** |
| `wind` | 30 | 50 | 70 | unverändert |
| `precipitation` | 1 | 5 | 10 | unverändert |
| `rain_probability` | 30 | 60 | 80 | unverändert |
| `cape` | 300 | 800 | 1500 | unverändert |

Die gefühlte Temperatur (`wind_chill`) hat heute **keinerlei** Anzeige-Schwellen — nur einen
Kälte-Risikowert `risk_thresholds={"high_lt": -20}`, den kein Renderer zum Einfärben liest.
Sie wird deshalb in keiner Mail je gefärbt, unabhängig vom Wert (PO-Befund 2026-07-28). Sie
erhält dieselben Werte wie die gemessene Temperatur — zwei Spalten mit demselben Maß dürfen
nicht verschieden färben. Der bestehende `risk_thresholds`-Eintrag bleibt unangetastet; er
bedient einen anderen Zweck (Alarme) und ist nicht Gegenstand dieser Spec.

### 2. Invertierte und beidseitige Bänder

Neue Schlüssel `yellow_lt` / `orange_lt` / `red_lt` mit der Bedeutung „Wert **unter**
dieser Grenze ⇒ diese Stufe". Der bestehende Einzelschlüssel `orange_lt` bleibt damit
formkompatibel; er wird um die fehlenden Stufen ergänzt.

Eine Metrik darf beide Richtungen gleichzeitig führen (Temperatur: Hitze **und** Kälte).
`severity_for` wertet dann beide Seiten aus und liefert die **schärfere** der beiden Stufen.
Dass die Bänder einander nicht überlappen, ist Sache der Katalog-Daten, nicht der Auswertung.

Auswertungsreihenfolge je Richtung, absteigend nach Schärfe: aufwärts `value >= red` → rot,
`>= orange` → orange, `>= yellow` → gelb; abwärts `value < red_lt` → rot, `< orange_lt` →
orange, `< yellow_lt` → gelb. Trifft keine Grenze: grün. Fehlen alle Schlüssel beider
Richtungen: „keine Aussage" (`None`).

### 3. Doppelung auflösen

`_level_from_thresholds` (`helpers.py:498-515`) und `severity_for`
(`metric_format.py:103-144`) implementieren dieselbe Band-Logik zweimal. `severity_for`
wird die einzige Implementierung; `_level_from_thresholds` delegiert an sie und entfällt
in Scheibe B vollständig. Damit wirken invertierte Bänder automatisch auch dort, wo heute
über `helpers` gefärbt wird (`ampel_dot`, `ampel_level`, `ampel_stage_tone`).

## Expected Behavior

- **Input:** Metrik-Kennung + Messwert
- **Output:** eine der vier Stufen `green` / `yellow` / `orange` / `red`, oder `None` wenn
  für die Metrik keinerlei Schwellen hinterlegt sind
- **Side effects:** Zwei bereits katalog-gespeiste Stellen in der Trip-Mail ändern sichtbar
  ihre Färbung — beides in die gewollte Richtung, s. „Sichtbare Wirkung"

## Sichtbare Wirkung (bewusst, PO-informiert)

Scheibe A ist **nicht** vollständig unsichtbar, weil Teile der Trip-Mail den Katalog bereits
lesen:

1. **Böen** — Punkt und Klartext-Zeile färben künftig ab 30 km/h statt ab 50. Das ist genau
   der Wert, den die Zellfarbe in derselben Mail heute schon verwendet: der bestehende
   Selbstwiderspruch der Trip-Mail verschwindet.
2. **Sichtweite** — die Klartext-Zeile „Sicht <X km ab HH:00" wird heute **nie** eingefärbt,
   weil `_level_from_thresholds` mit dem einzelnen `orange_lt`-Schlüssel nichts anfangen kann
   und stillschweigend „grün" liefert. Künftig ist sie korrekt orange bzw. rot. Das ist die
   Behebung eines echten Fehlers, keine Geschmacksänderung.

Alles andere bleibt in Scheibe A unverändert — insbesondere Zellfarben in Stundentabelle,
Ausblick und Ortsvergleich, die noch ihre eigenen Schwellen benutzen.

### Temperatur und gefühlte Temperatur bleiben in Scheibe A noch grau

Der PO-Befund „die gefühlte Temperatur wird gar nicht eingefärbt" hat **zwei** Ursachen:

1. Im Katalog fehlen die Schwellen — das behebt Scheibe A.
2. Der Klartext-Block stuft `temperature` und `wind_chill` als **Klasse 2** ein
   (`helpers.py:1217-1231,1233`) und färbt sie fest mit `_PILL_NEUTRAL_TONE`, ohne den
   Katalog überhaupt zu fragen. Das ist eine bewusste Entscheidung aus #795.

Nach Scheibe A kann der Katalog die Frage beantworten — gefragt wird er für diese beiden
Größen aber noch nicht. Die Einfärbung wird erst sichtbar, wenn Scheibe B die
Neutral-Einstufung aufhebt. Das ist eine Produktentscheidung, keine Aufräumarbeit, und
gehört deshalb ausdrücklich in Scheibe B statt hierher.

## Acceptance Criteria

- **AC-1:** Given der Katalog führt für Böen die Werte 30/45/60 / When die Ampel-Auskunft für
  einen Böenwert von 35 km/h gefragt wird / Then liefert sie „gelb", und für 25 km/h „grün".
  - Test: `severity_for("gust", 35) == "yellow"` und `severity_for("gust", 25) == "green"`

- **AC-2:** Given die Sichtweite ist mit invertierten Grenzen hinterlegt / When die Ampel-Auskunft
  für 800 m gefragt wird / Then liefert sie „orange"; für 400 m „rot"; für 1500 m „gelb"; für
  5000 m „grün".
  - Test: vier Aufrufe von `severity_for("visibility", …)` mit genau diesen Erwartungen

- **AC-3:** Given Temperatur und UV-Index haben erstmals Schwellen / When die Ampel-Auskunft für
  32 °C bzw. UV 7 gefragt wird / Then liefert sie „orange" statt wie bisher „keine Aussage".
  - Test: `severity_for("temperature", 32) == "orange"`, `severity_for("uv_index", 7) == "orange"`

- **AC-3b:** Given die Temperatur ist beidseitig hinterlegt / When die Ampel-Auskunft für −6 °C
  gefragt wird / Then liefert sie „orange" (Kälte-Seite); für −20 °C „rot"; für −1 °C „gelb";
  für 15 °C „grün".
  - Test: vier Aufrufe `severity_for("temperature", …)` mit genau diesen Erwartungen

- **AC-3c:** Given die gefühlte Temperatur hat bisher nie eine Farbe bekommen / When die
  Ampel-Auskunft für −8 °C gefühlt gefragt wird / Then liefert sie dieselbe Stufe wie die
  gemessene Temperatur beim selben Wert — und nicht mehr „keine Aussage".
  - Test: `severity_for("wind_chill", -8) == severity_for("temperature", -8) == "orange"`;
    zusätzlich Gleichheit beider über eine Reihe von Werten von −25 bis +40 °C

- **AC-4:** Given eine Metrik ohne jede hinterlegte Schwelle (z.B. Luftdruck) / When die
  Ampel-Auskunft gefragt wird / Then liefert sie „keine Aussage" und **nicht** „grün".
  - Test: `severity_for("pressure", 1013) is None` — verhindert die Rückkehr des
    irreführenden Grün-Defaults (F001 aus #1214)

- **AC-5:** Given ein Trip-Briefing mit einer Stunde unter 1 km Sicht / When die Mail gerendert
  wird / Then ist die Klartext-Zeile zur Sichtweite orange oder rot eingefärbt statt wie bisher
  grün.
  - Test: Renderer-Aufruf mit einem Datenpunkt bei 800 m Sicht; die zurückgegebene Tönung der
    Sicht-Zeile ist nicht `ampel_green`

- **AC-6:** Given ein Trip-Briefing mit Böen von 35 km/h / When die Mail gerendert wird / Then
  zeigen Punkt und Zellfarbe für denselben Wert dieselbe Stufe (beide gelb) — der bisherige
  Widerspruch grün-Punkt/gelbe-Zelle tritt nicht mehr auf.
  - Test: Renderer-Aufruf; Ampel-Stufe des Punktes und Stufe der Zellfarbe für denselben
    Böenwert sind gleich

- **AC-7:** Given die fünf bestehenden Mail-Schnappschüsse in `tests/golden/email/` / When sie
  nach der Änderung neu erzeugt werden / Then unterscheiden sie sich ausschließlich in der
  Böen- und Sichtweiten-Färbung; alle übrigen Zellen, Zahlen und Texte sind unverändert.
  - Test: Golden-Vergleich; Abweichungen außerhalb dieser beiden Größen lassen den Test fehlschlagen

## Known Limitations

- **Gewitter bleibt außen vor.** Trip rechnet mit einer Prozentzahl, der Ortsvergleich mit den
  Stufen mittel/hoch. Das ist eine Datenform-Divergenz, keine Schwellenfrage — gehört zu
  Epic #1372, nicht hierher.
- **Die Renderer bleiben in Scheibe A unangetastet.** Stundentabelle, Ausblick und
  Ortsvergleich führen weiterhin ihre eigenen Schwellen; sie werden in Scheibe B umgestellt.
  Bis dahin bestehen die im Issue beschriebenen Abweichungen zwischen den Mail-Arten fort.
- **Temperatur und gefühlte Temperatur bekommen in Scheibe A noch keine Farbe in der Mail** —
  der Klartext-Block fragt den Katalog für sie gar nicht (Klasse-2-Neutralität aus #795).
  Scheibe B hebt das auf. Ohne Scheibe B bleibt der PO-Befund vom 2026-07-28 sichtbar bestehen.
- **Überlappende Bänder** (eine Hitze- und eine Kältegrenze, die sich überschneiden) werden
  nicht erkannt; die Auswertung liefert dann schlicht die schärfere Stufe. Für die hier
  hinterlegten Werte kann der Fall nicht auftreten.
- **Kontraktwechsel bei Metriken ganz ohne Schwellen** (Adversary-Fund F001, 2026-07-28):
  `_level_from_thresholds` fiel früher garantiert auf „grün" zurück; über die gemeinsame
  Auswertung kann jetzt auch „keine Aussage" herauskommen. Sichtbare Folge:
  `ampel_dot(5.0, {})` liefert „–" statt eines grünen Punktes. Das ist die **richtige**
  Richtung — ein grüner Punkt für eine Größe ohne jede Schwelle ist genau der irreführende
  Default, den #1214 abgeschafft hat. Heute ist der Fall unerreichbar: alle Aufrufer
  übergeben Metriken mit vollen Schwellen. **Für Scheibe B ist das ein Pflichtpunkt**, weil
  dort Temperatur und gefühlte Temperatur erstmals an diese Funktionen angeschlossen werden.
  Die Schwesterfunktion `ampel_stage_index` (`helpers.py:1049-1063`) fällt bewusst weiterhin
  auf Grün zurück, weil ihr Rückgabewert ein Index ohne „keine Aussage"-Stufe ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Grundsatzentscheidung „der zentrale Katalog ist die Schwellenquelle" hat
  der PO im Issue #1377 getroffen und sie setzt die bereits umgesetzte Richtung aus #1214
  (Wind, CAPE) fort. Diese Spec führt sie nur aus. Ein ADR wäre erst nötig, wenn davon
  abgewichen würde.

## Changelog

- 2026-07-28: Initial spec created (Scheibe A von #1377)
