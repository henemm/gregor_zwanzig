# ADR-0077: Die metrik-genaue Kanal-Schicht liegt als Top-Level-Map `alert_metric_channels` auf Trip UND Ortsvergleich

- **Status:** Akzeptiert
- **Datum:** 2026-09-22
- **Bezug:** GitHub-Issue #1895 (Scheibe S1, letzte offene Substanz von Epic #1230), Spec
  `docs/specs/modules/alert_metric_channels.md`, **schreibt ADR-0046 fort** (Alarm-Kanal-Schwelle),
  trägt auf ADR-0043 (keine Konfigurationsfläche ohne sichtbare Wirkung) und ADR-0023 (rein additive
  Schema-Erweiterung)

## Kontext

Die Kanal-Auflösung für Alarme kennt heute zwei Schichten: den Abo-weiten Kanal-Satz
(`alert_channels` am Trip, die flachen `send_*`-Felder am Ortsvergleich) und die je Kanal
eingestellte Dringlichkeits-Schwelle (`alert_channel_thresholds`, ADR-0046). Was fehlt, ist die
Schicht dazwischen: **welche Metrik über welchen Kanal gemeldet wird**. Die einzige heutige
Annäherung ist `alert_rules[].channels` — an die Regel-Liste gebunden, nicht an die Metrik, und
damit weder im Editor noch im Ortsvergleich als eigene Fläche verfügbar.

Bevor diese Schicht einen Leser oder eine Bedienfläche bekommt, muss ihre Zielform feststehen:
Ablageort, Typ und Merge-Verhalten. Wird das erst beim Bauen der Bedienfläche entschieden, ist der
naheliegende Kurzschluss ein atomarer Ersatz der ganzen Zuordnung beim Speichern — und damit genau
der Datenverlust, den BUG-DATALOSS-GR221 (#102) für Etappen schon einmal erzeugt hat: Ein Teil-PUT
für eine Metrik löscht still die Kanäle aller anderen Metriken.

## Entscheidung

1. **Ablageort: Top-Level-Feld `alert_metric_channels` auf `Trip` UND `ComparePreset`, ab S1 in
   Parität.** Keine Verschachtelung unter `alert_channels` — die Schichten „je Abo", „je Kanal"
   (ADR-0046) und „je Metrik" bleiben nebeneinanderliegende Geschwisterfelder, jede mit eigenem
   Merge-Verhalten. Das hält auch #2293 (`ComparePreset.AlertChannels`, Schicht „je Abo") kollisionsfrei
   daneben bestehen.
2. **Go-Typ: `map[string]interface{}` mit `json:"alert_metric_channels,omitempty"`**, kein Struct.
   Damit greift der bestehende `mergeConfigMap`-Mechanismus (Muster `DisplayConfig`,
   `internal/handler/trip.go`) und der Teil-PUT mergt eine Ebene tief, statt die ganze Map atomar zu
   ersetzen. `omitempty` hält Bestandsdaten byte-gleich: wer das Feld nie gesetzt hat, bekommt auch
   keinen Schlüssel geschrieben.
3. **Schlüsselmenge = Metrikname, in S1 ausdrücklich unvalidiert.** Die verbindliche Schlüsselmenge
   ist eine Analyse-Entscheidung für S3 (Editor-Spalte). Go validiert heute weder Metrik-Keys noch
   Stufenwerte; eine hier eingeführte Validierung wäre Scope-Creep und würde Bestandsdaten mit dem
   abgelösten Schlüssel `snow_line` brechen.

   **Ergänzung S2 (2026-09-22, Issue #1895):** Das **Lese-Vokabular** legt S2 fest — ein Schlüssel
   ist eine Katalog-`metric_id`, aufgelöst aus dem rohen Summary-Key der auslösenden Änderung über
   die eine Rückwärts-Primitive `metric_catalog.metric_and_aggregation_for_field`
   (wählbarkeitsdisambiguiert: `temp_min_c` ⇒ `temperature`, nie `temperature_cold`). Ein
   unbekannter oder mehrdeutiger Schlüssel wirft nicht, sondern wird behandelt wie „kein Eintrag" —
   die Metrik erbt (Punkt 4). Die **verbindliche, validierte** Schlüsselmenge samt Editor-Anzeige
   und Bestandsdaten-Prüfung bleibt S3.
4. **Regel: kein Eintrag = die Metrik erbt den Abo-weiten Kanal-Satz.** Ein fehlender Metrik-Schlüssel
   ist keine Abschaltung, sondern Nicht-Abweichung. Das ist die Fortschreibung von ADR-0046: Die
   Kanal-Ebene regelt, AUF WELCHEM WEG eine Meldung ankommt, nicht OB sie ankommt — auch die
   metrik-genaue Schicht darf keine Meldung unterdrücken.
5. **Reihenfolge-Zwang: S2 (Leser im Alarm-Pfad) muss vor S3 (Editor-Spalte) kommen.** Direkte
   ADR-0043-Konsequenz: Eine Bedienfläche ohne wirkende Aufrufstelle wäre eine Konfigurationsfläche
   ohne sichtbare Wirkung. Umgekehrt ist S1 ohne Leser unbedenklich — ohne Leser kann das Risiko
   „stille Kanal-Abschaltung" strukturell nicht feuern.

## Verworfene Alternativen

- **Verschachtelung unter `alert_channels`** (`alert_channels.per_metric`) — hätte das bestehende
  All-or-nothing- bzw. Feld-Level-Merge-Verhalten dieses Unterobjekts mit einem zweiten,
  andersartigen Merge vermischt und die drei Schichten in einem Feld verklebt. Getrennte
  Geschwisterfelder bleiben einzeln erklärbar und einzeln migrierbar.
- **Typisiertes Go-Struct je Metrik** — hätte die Schlüsselmenge schon in S1 festgeschrieben, obwohl
  sie erst in S3 entschieden wird, und hätte den generischen `mergeConfigMap`-Weg verbaut
  (Struct-Felder mergen nicht generisch).
- **Nur am Trip einführen, Ortsvergleich später nachziehen** — verstößt gegen die
  Trip/Ortsvergleich-Paritätsvorgabe und hätte in S2 zwei verschiedene Auflösungswege erzwungen.
- **`alert_rules[].channels` erweitern statt eines neuen Feldes** — bindet die Zuordnung weiter an die
  Regel-Liste statt an die Metrik und ist im Ortsvergleich gar nicht verfügbar. Der Rückbau von
  `alert_rules` ist als S4 vorgesehen, nicht als Fundament.

## Konsequenzen

- **Positiv:** Die Zielform steht fest, bevor ein Leser oder eine Bedienfläche darauf aufsetzt; der
  Teil-PUT-Datenverlust ist durch den Typ-Entscheid (Map + `mergeConfigMap`) strukturell
  ausgeschlossen und testbewacht. Trip und Ortsvergleich starten paritätisch.
- **Negativ / Preis:** Zwischen S1 und S2 existiert ein persistiertes Feld ohne Leser. Das ist bewusst
  in Kauf genommen (verhaltensneutral, keine Bedienfläche, kein Nutzerversprechen) und durch den
  Reihenfolge-Zwang in Punkt 5 befristet. Die fehlende Validierung (Punkt 3) heißt: ein Tippfehler im
  Metriknamen bleibt in S1 folgenlos-unsichtbar.
- **Folgepflichten:** S2 führt den Leser ein und migriert `alert_rules[].channels`; erst danach darf
  S3 die Editor-Spalte bauen. Die Schlüsselmenge wird in S3 verbindlich festgelegt — wer sie
  festlegt, prüft zugleich Bestandsdaten auf abgelöste Schlüssel. `has_active_rules` bleibt in allen
  Scheiben unangetastet.
