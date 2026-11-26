# ADR-0126: Windrichtung wird als abgeleitete skalare Größe („Wind aus unerwünschter Richtung", km/h) über die Profil-Ampel bewertet

- **Status:** Akzeptiert
- **Datum:** 2026-11-20
- **Bezug:** Issue #3222, Spec `docs/specs/modules/feat_3222_windrichtung.md`, Kontext `docs/context/feat-3222-windrichtung.md`. **Ergänzt:** ADR-0106 (Profil-Ampel ist die einzige Bewertung). **Bestätigt:** ADR-0095 (Kanal-Parität), ADR-0108 (Vorlage getrennt von Tempo), ADR-0125 (Token-Zeile der Trip-SMS auch für Orte).

## Kontext

Die Windrichtung (`wind_direction`) ist in allen sieben Vorlagen ohne Skala: Sie wird angezeigt, nie gefärbt, nie alarmiert.
Der PO hat am 2026-11-20 zwei Fälle genannt, in denen die Richtung zählt: Trips mit dem Rad (Gegenwind auf der vorherrschenden
Fahrtrichtung) und die Ortswahl beim Skifahren (Wind aus einer kalten Richtung). Eine Richtung ist zirkulär (359° liegt neben 1°);
die Ampel aus ADR-0106 kennt nur skalare Schwellen (`Wert >= Grenze` oben, `Wert < Grenze` unten). Richtung ohne Stärke ist
fachlich bedeutungslos: leichter Wind aus der „falschen" Richtung stört nicht.

## Entscheidung

1. **Richtung wird vor der Ampel zu einem Skalar reduziert:** `wind_unerwuenscht_kmh` je Stunde, Segment bzw. Ort.
   - Modus **„gegenwind"** (nur Trip): Gegenwindkomponente = Windstärke · cos(Herkunftsrichtung − Fahrtpeilung), nur wenn > 0, sonst 0.
     Fahrtpeilung = Luftlinie Segment-Start → Segment-Ende; unter 300 m Luftlinie gibt es keine Richtung (Wert fehlt, keine Färbung).
   - Modus **„sektoren"** (Trip und Ortsvergleich): volle Windstärke, wenn die Herkunft in einem markierten 8er-Sektor
     (N, NO, O, SO, S, SW, W, NW) liegt, sonst 0.
   - Modus **„aus"** (Default aller Vorlagen außer `radtour`): keine Bewertung, Verhalten wie bisher.
2. **Bewertet wird mit den normalen oberen Ampel-Grenzen in km/h** (gelb/orange/rot) und `alarm_ab`. `severity_from_thresholds`,
   Alarm-Stufenwechsel, Sprung und Dedup bleiben unverändert. Die Mindeststärke steckt in der gelben Grenze.
3. **Modell:** `ampel.metrics.wind_direction` erhält additiv `modus` und `sektoren`; Python und Go validieren gleich; Bestand ohne
   Feld bleibt „aus" (Read-Modify-Write mit Merge, keine Migration nötig).
4. **Vorlage `radtour`:** Modus „gegenwind", Grenzen 10/20/30 km/h, Alarm ab orange. Gekoppelt wird pro Ampel-Eintrag, nicht über
   `tempo.fortbewegung` (ADR-0108).
5. **Nur die ungünstige Richtung wird bewertet** (PO-Freigabe 2026-11-20): Rücken- und Seitenwind bleiben neutral.
6. **Kanäle:** E-Mail färbt die Zelle WDir; Telegram nennt „Gegenwind"/„Wind aus unerwünschter Richtung" aus dem Katalog;
   SMS und Premium-SMS behalten das Token `WD:{Sektor}` unverändert und zeigen die Bewertung über die bestehende Hervorhebung
   (`@h` ab gelb) und den Alarmtext. Kein neues Protokoll-Token.
7. **Grat-Exposition (Risiko-Regel 9)** bleibt ein getrennter Mechanismus; wo beide wirken, gilt die höhere Stufe, nicht die Summe.

## Verworfene Alternativen

- **Zirkuläre Sonderlogik in `severity_from_thresholds`** (Winkelbereiche als Grenzen) — bricht die einheitliche Skala aus ADR-0106,
  Alarm-Sprung und Abweichungszählung müssten eigene Pfade bekommen; Stärke bliebe unberücksichtigt.
- **Gegenwind automatisch aus `tempo.fortbewegung = rad`** — koppelt Vorlage und Tempo, die ADR-0108 getrennt hat; Nutzer zu Fuß
  mit Gegenwind-Wunsch hätten keinen Weg.
- **Neues SMS-Token (z. B. `WD:N-`)** — neues Protokollmuster, kostet Zeichen im 160er-Budget; Bewertung ist über `@h` bereits ausdrückbar.

## Konsequenzen

- **Positiv:** Ein Pfad für Farbe, Hervorhebung und Alarm wie bei jeder anderen Metrik; alle Kanäle erben die Bewertung.
- **Negativ / Preis:** Luftlinien-Peilung ist bei Serpentinen und langen Segmenten grob; Stundenfeinheit über den GPX-Track folgt später.
- **Folgepflichten:** Neue Felder der Ampel müssen in `_verschmelzen`, `deviation_count`, Go-Validierung und TS-Spiegel gleichzeitig
  ergänzt werden. Winkel werden nie arithmetisch gemittelt, nur vektoriell.

## Nachtrag (2026-11-26, #2988)

Die Folgepflicht schrumpft: `deviation_count` (Python, #2988 S1) und der TS-Spiegel (`verschmelzen`, `ampelFehler`,
`zaehleAbweichungen`, #2988 S4) gibt es nicht mehr; die Auflösung rechnet allein Python (`POST /api/ampel/aufloesung`).
Neue Ampel-Felder müssen weiter in `_verschmelzen` und in der Go-Validierung ergänzt werden. Die Entscheidung selbst bleibt
unverändert.
