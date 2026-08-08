# ADR-0048: Modellabhängige Schwellen statt einer Zahl für alle Quellen

- **Status:** Akzeptiert
- **Datum:** 2026-08-08
- **Bezug:** GitHub-Issue #1592, Spec `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md`,
  Kontext `docs/context/fix-1592-cape-modellschwelle.md`, Epic #1419,
  Konzept `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.4b

## Kontext

Gregor Zwanzig bezieht dieselbe Wettergröße je nach Ort aus verschiedenen Rechenmodellen.
Bei CAPE („Gewitterenergie") ist das folgenreich, denn **CAPE ist ein modellabhängiges
Konstrukt, kein Messwert**: die Modelle unterscheiden sich in der Wahl des Luftpakets —
ICON liefert Mixed-Layer, Météo-France Most-Unstable, GFS Surface-Based. Open-Meteo reicht
die native Variable je Modell durch, ohne zu harmonisieren und ohne es zu dokumentieren.

Der Code prüfte `cape_jkg` bis dahin gegen **eine** Schwelle von 1000 J/kg, unabhängig vom
liefernden Modell. Gemessen am selben Ort im selben Zeitraum überschritt AROME diese Schwelle
in **0,0 %** aller Stunden, ECMWF in **65 %**. Für die Zielgruppe — Weitwanderer auf dem GR20,
mitten im AROME-Gebiet — war das CAPE-Signal damit seit jeher stumm, ohne dass es auffiel.

Erschwerend: Die Zahl 1000 kam am 2026-02-12 (`78de329e`) **ohne jede Quellenangabe** in den
Code und wurde seither nur verschoben. Es gibt im Repo keine Belegstelle, die sie einer
Parcel-Variante zuordnet. Sie war für kein Modell belegt.

Ein Präzedenzfall für eine quellen- oder modellabhängige numerische Schwelle existierte im
Repo nicht. Quellenabhängige Fallunterscheidung gab es nur für die **Zuständigkeit**
(`thunder_routing._REGIONS`), nie für einen **Zahlenwert**.

## Entscheidung

**Feste Schwellen werden nie über Modellgrenzen getragen.** Wo ein Schwellenwert auf eine
modellabhängige Größe angewendet wird, ist er selbst modellabhängig.

Konkret für CAPE:

1. Die Schwelle wird **je Modell und Gebiet** geführt, in einer statischen Tabelle
   `CAPE_THRESHOLDS_JKG` in `src/app/model_registry.py`. Schlüsselreihenfolge verbindlich
   `(model_id, region)`. Das Gebietsraster ist **dasselbe** wie in `thunder_routing._REGIONS` —
   es wird kein zweites Raster geführt.
2. Die Werte entstehen durch **Eichung an der Modellklimatologie**: 95. Perzentil der
   CAPE-Verteilung dieses Modells in diesem Gebiet über eine Konvektionssaison
   (April–September), **mindestens 300 J/kg**. Ein reines Perzentil würde in klimatologisch
   ruhigen Gebieten bei absurd niedrigen Absolutwerten auslösen; ein reiner Absolutwert ist
   genau der behobene Fehler. Die Kombination entspricht dem operationell üblichen Verfahren
   (ECMWF Extreme Forecast Index: Seltenheit relativ zur Modellklimatologie).
3. Die Eichung ist ein **einmaliger, bewusster Schritt** (`scripts/eichung_cape_schwelle.py`),
   kein Cronjob und keine Laufzeit-Abhängigkeit. Der Produktivcode liest nur die Tabelle.
4. Die Eichung vermisst **genau die Reihe, die der Produktivcode bezieht**. Da unser Code über
   Endpunkte abruft und nicht über benannte Modellvarianten, wird die Zuordnung
   Endpunkt → Variante empirisch ermittelt (Wert-für-Wert-Vergleich) und im Eichskript
   dokumentiert. Andernfalls eicht man auf eine Modellwelt und wendet auf eine andere an —
   derselbe Fehler eine Ebene tiefer.
5. **Unbekannte Herkunft heißt „keine Aussage", nicht „unauffällig".** Fehlt die Modell-Herkunft
   oder gibt es für die Kombination keinen Eintrag, trägt CAPE **kein** Signal zur Fusion bei.
   Es wird insbesondere **kein** `ThunderLevel.NONE` eingehängt — das wäre die Behauptung einer
   geprüften Entwarnung, die nicht stattgefunden hat.
6. **Kein stiller Rückfall.** Der Schwellenparameter an der Fusionsgrenze
   (`thunder_level_from_signals`) ist keyword-only **ohne Default**: ein Aufrufer, der die
   Herkunft nicht übergibt, bricht hart, statt still auf Bestandsverhalten zu fallen.

Unberührt bleibt die Produktentscheidung aus feat_1474 AC-6: **CAPE misst Energie, kein
Ereignis** und eskaliert nie über `LOW`. Die Schwelle wird variabel, die Deckelung bleibt.

## Verworfene Alternativen

- **Perzentil zur Laufzeit berechnen** (statt eingefrorene Tabelle) — fachlich der reinere
  Weg, aber er verlangt bei jedem Abruf historische Daten, ist nicht ohne Netz prüfbar und
  nicht mutations-testbar. Eine Tabelle ist dasselbe Verfahren, einmal ausgerechnet.
- **Eine eigene Schwelle je einzelnem Ort** statt je Gebiet — genauer (die Messung zeigt, dass
  der Ort so stark streut wie das Modell: ICON-EU überschreitet auf Korsika 8,1 %, in München
  1,4 %), kostet aber Abrufe je Ort plus Zwischenspeicherung. Als spätere Verfeinerung notiert.
- **Bei der einen Zahl bleiben und nur den Wert senken** — hätte die Modellabhängigkeit nicht
  berührt und wäre beim nächsten Modellwechsel wieder falsch.
- **CAPE ganz entfernen** — verwirft ein Signal, das nach Eichung tragfähig ist. Die
  Sichtbarkeit von CAPE als Nutzer-Metrik ist davon unabhängig und in #1585 entschieden.

## Konsequenzen

- **Positiv:** Das CAPE-Signal wirkt erstmals im gesamten Abdeckungsgebiet statt nur dort, wo
  die geerbte Zahl zufällig passte. Auf dem GR20 trägt es überhaupt zum ersten Mal bei. Die
  Schwellen beruhen auf gemessenen Verteilungen statt auf einer unbelegten Zahl.
- **Negativ / Preis:** Es gibt jetzt eine Tabelle, die veraltet, wenn ein Anbieter sein Modell
  wechselt — stillschweigend, denn die Zahlen bleiben ja plausibel. Die Eichung muss deshalb
  wiederholbar bleiben, und das Skript gehört zwingend zum Tabelleneintrag.
- **Folgepflichten:**
  - **Jede künftige Modellgröße mit Schwellenwert prüft zuerst, ob die Schwelle
    modellabhängig ist.** Das gilt für Blitzpotenzial, CIN, Superzellen-Index und alles
    Weitere aus Epic #1419.
  - **Wer die Eichung wiederholt, prüft zuerst die Zuordnung Endpunkt → Modellvariante nach.**
    Sie ist empirisch ermittelt, nicht dokumentiert garantiert.
  - `ecmwf_ifs04` in `REGIONAL_MODELS` ist ein **veralteter Name** — der Endpunkt liefert
    `ifs025`. Der Tabellenschlüssel bleibt trotzdem `ecmwf_ifs04`, weil er dem entspricht, was
    zur Laufzeit in `meta.model` steht. Nicht „aufräumen", sonst bricht der Nachschlag.
  - Die Herkunft muss auf jedem Weg mitlaufen, auf dem sie gebraucht wird. Ortsvergleich
    (`model="aggregate"`) und Schnappschuss-Reload (`model="snapshot"`) haben sie strukturell
    nicht; dort abstiniert CAPE dauerhaft, bis ein Folgeticket sie durchreicht.
  - Die Familien RiskEngine (C2) und Δ-Alarme (C3) sind in dieser Scheibe **noch nicht**
    umgestellt und verwenden weiterhin die feste Zahl. Sie folgen in eigenen Scheiben unter
    demselben Issue.
