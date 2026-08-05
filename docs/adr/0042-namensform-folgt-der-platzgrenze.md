# ADR-0042: Die Namensform einer Wettergröße folgt der Platzgrenze, nicht einer pauschalen Sprachpräferenz

- **Status:** Akzeptiert (PO-Entscheidung 2026-08-02)
- **Datum:** 2026-08-02
- **Bezug:** Issue #1453, Issue #1401 A2b (verursachend), Issue #862/#849 (bestätigt), Issue #1420/#1404 (Prüfer-Übergang, hier beendet), Spec `docs/specs/modules/fix_1453_namensformen.md`, Epic #1372

## Kontext

Jede Wettergröße im Register (`src/app/metric_catalog.py`) trägt bis zu sechs Felder,
die sie benennen: `label_de`, `col_label`, `alert_label`, `compact_label`, `sms_code`,
`friendly_label`. Sie sind über Jahre gewachsen, ohne dass je festgelegt wurde, welches
wofür gilt — und drei davon waren untereinander uneins: `label_de` und `alert_label`
deutsch, `col_label` englisch.

Sichtbar wurde das mit `386bbdba` (#1401 A2b). Der Umbau war richtig — Beschriftungen
aus dem zentralen Register statt an vier Stellen getippt — aber er zog `col_label`, die
englische Kurzform für die enge Trip-Stundentabelle, auch dort heran, wo Platz für den
vollen Namen ist. Ergebnis: In **einer** Vergleichs-Mail standen drei Formen nebeneinander
— Übersichtstabelle englisch, Stundentabelle englisch, 3-Tages-Ausblick deutsch. Der
Taupunkt hieß `Cond°`, ein Kürzel, das kein Wetterdienst führt.

Der erste Reflex war, die Mail einzudeutschen. Der PO hat das zurückgewiesen:

> „Die SMS-Kürzel sind bewusst englisch. Der Dienst soll später international werden.
> Es braucht ein Konzept, keinen Aktionismus."
>
> „Das Produkt richtet sich an Profis. Die internationale Sprache ist Englisch. Ich finde
> es sehr logisch, einfache englische Sprache zu verwenden und Fachbegriffe dort, wo sie
> der Klarheit dienen."

Damit war die Frage nicht mehr „welche Sprache", sondern **welche Namensarten das Produkt
überhaupt braucht.**

## Entscheidung

**Namen zerfallen in zwei Klassen, und innerhalb der Anzeige-Klasse entscheidet der
verfügbare Platz — nicht die Sprache.**

### Klasse 1 — Protokoll-Token: nie übersetzen

`sms_code`, `compact_label`. Bezeichner in einem festen Format, das zwischen Maschinen
oder in einer 160-Zeichen-Grammatik steht. Eine SMS mit `SD180` bedeutet in jeder Sprache
dasselbe. Diese Felder sind von Sprachfragen **ausgenommen** — auch bei einer späteren
Internationalisierung.

### Klasse 2 — Anzeige-Namen: drei Längen, eine Systematik

| Form | Wofür | Grenze | Sprache heute |
|---|---|---|---|
| **voll** | Zeilenbeschriftungen, Editor, Auswahl, 3-Tages-Ausblick | keine | deutsch (`label_de`) |
| **Kurzform** | Tabellen-Spaltenköpfe (bis 22 nebeneinander) | ≤ 6 Zeichen je Wort | **englisch** (`col_label`) |
| **Alarm-Kurzform** | Alarm-Mail, Telegram, Betreffzeile | ~10 Zeichen | deutsch (`alert_label`) |

> **Wo wenig Platz ist, steht die englische Fachkurzform. Wo Platz ist, steht der
> ausgeschriebene deutsche Name.**

Die Kurzform ist damit eine **Platzform**, kein Sprachbekenntnis. Sie erscheint nur dort,
wo 22 Spalten nebeneinander stehen müssen. Für die Zielgruppe — Profis, für die Englisch
die übliche Fachsprache ist — sind `Gust` und `Visib` eindeutiger als abgeschnittene
deutsche Wörter (`Wolken mitt.`, `Schneef.-Gr.`).

### Bedingung: die Auflösung muss auffindbar sein

Eine englische Kurzform in der Mail ist nur dann kein Rätsel, wenn der Nutzer an **einer**
Stelle nachschlagen kann, wofür sie steht. Deshalb zeigt der Reiter *Wetter-Metriken* je
Größe **alle drei Formen** nebeneinander: `Luftfeuchtigkeit · Humid · HU`. Ohne diese
Auflösung wäre die Regel eine Zumutung; mit ihr ist sie eine Konvention.

**Nachtrag #1472 (2026-08-05): die Bedingung gilt auch IN der Mail.** Der Editor half unterwegs
nicht — gelesen wird die Mail am Berg, ohne App. Seither trägt jede Mail unter der Stundentabelle
eine zweite Legenden-Zeile, die die **tatsächlich sichtbaren** Kürzel auflöst:

```
Einheiten: Temp, Feels °C · Wind km/h
Spalten: Temp = Temperatur · Feels = Gefühlte Temperatur · Thdr = Gewitter · Visib = Sichtweite
```

Regel: auflösen, **außer** Kürzel und ausgeschriebener Name sind identisch (`Wind`). Keine
Pflegeliste — die Abgrenzung leitet sich aus den Daten ab. Gilt in allen vier Ausgaben (Trip und
Ortsvergleich, je HTML und Klartext); das Kürzel stammt aus derselben Ableitung wie der
Spaltenkopf, sonst erklärte die Legende ein Kürzel, das in der Tabelle nicht steht.

Verworfen und nicht erneut vorschlagen: „auflösen, wenn das Kürzel kein **Präfix** des Langnamens
ist" — trifft gemessen 24 von 27, weil die Kurzform englisch und der Name deutsch ist (genau die
Regel dieses ADRs). Spec: `docs/specs/modules/fix_1472_spaltenkuerzel_legende.md`.

### Fachbegriffe bleiben unübersetzt

`CAPE` und `UV` sind internationale Fachbegriffe ohne deutsche Entsprechung. Sie bleiben
in beiden Formen stehen — in der Übersicht als Teil des vollen Namens
(`Gewitterenergie (CAPE)`), in der Stundentabelle allein (`CAPE`).

## Konsequenzen

**Bestätigt, nicht aufgehoben: #862/#849.** Dort steht „Spaltenköpfe bleiben bewusst
englisch (PO-Entscheidung)"; damals wurde sogar eine Prüfung entfernt, die englische
Beschriftungen bemängelt hatte. Dieses ADR macht explizit, was dort implizit nur für die
Stundentabelle galt: die Aussage war eine **Platzregel** und trifft keine Entscheidung
über Flächen mit viel Platz.

**Die Tour-Mail bleibt unverändert** — sie führt durchgehend Kurzformen, was nach der
Regel richtig ist. Ihre Beschriftungskette ist von der des Ortsvergleichs vollständig
getrennt (eigene Funktionen, eigener Pflicht-Prüfer, eigene Golden-Dateien).

**Eine spätere Internationalisierung übersetzt nur Klasse 2.** Nicht als Feldreihe
`label_de`/`label_en`/`label_it` — das wächst quadratisch und man vergisst Stellen —,
sondern als Übersetzungsschicht über den drei Anzeige-Formen, während das Register die
Sachdaten behält (Einheit, Nachkommastellen, Schwellen, Alarmfähigkeit, Protokoll-Token).
**Nicht auf Vorrat**: erst wenn ein zweiter Sprachbedarf real wird.

**Wer eine Beschriftung ändert, schuldet den Prüfer-Nachzug im selben Zug.** #1404 und
#1420 haben `email_spec_validator.py` alte **und** neue Formen akzeptieren lassen —
ausdrücklich als Übergang, der nie beendet wurde. Solange beides zulässig ist, prüft das
Gate an dieser Stelle **nichts**, nicht einmal ein Nebeneinander beider Formen in
derselben Mail. #1453 beendet diesen Übergang und löst beide Prüffristen auf; künftige
Änderungen laufen ohne Zwischenzustand.

**Ein neues Kürzel muss fachlich gebräuchlich sein.** `Cond°` für den Taupunkt war
erfunden — im Fach heißt es Dew Point. `hPa` für den Luftdruck war die *Einheit* statt des
Namens. Beide sind mit #1453 korrigiert (`Dew`, `Press`). Die Auflösungsanzeige aus der
Bedingung oben ist zugleich die Gegenprobe: sobald `Taupunkt · Cond° · DP` nebeneinander
steht, fällt die Mitte auf.

## Alternativen, die verworfen wurden

**Alles eindeutschen.** Hätte die SMS-Grammatik und die Fachkürzel mitgerissen, die
bewusst international sind — und für 13 Größen deutsche Kurzformen erfunden, die es nicht
gibt (`Schneef.-Gr.`, `Wolken mitt.`). Vom PO zurückgewiesen.

**Alles englisch.** Wäre konsequent, macht aber die gesamte Bedienoberfläche, die
Alarm-Mails und den Ausblick zur Baustelle — ohne Nutzen, solange es keine
nicht-deutschsprachigen Nutzer gibt.

**`col_label` je Fläche überschreiben.** Hätte die fünfte Namensliste erzeugt: genau das
Muster, gegen das Epic #1372 und Ticket #1435 antreten.
