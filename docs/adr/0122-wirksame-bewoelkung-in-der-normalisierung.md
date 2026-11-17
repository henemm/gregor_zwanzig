# ADR-0122: Wirksame Bewölkung — Schleierwolken zählen halb, eine Regel in der Normalisierung

- **Status:** Akzeptiert
- **Datum:** 2026-11-17
- **Bezug:** GitHub-Issue #3106, Spec `docs/specs/modules/feat_3106_wirksame_bewoelkung.md`. Fortgeschrieben: `docs/specs/cloud_cover_simplification.md` (Hochlagen-Regel ab 2500 m), ADR-0095 (Kanal-Parität).

## Kontext

Die Größe „Bewölkung" zeigte den Modell-Gesamtwert. Dünne hohe Wolken (Cirrus) treiben ihn auf 100 %, obwohl die Sonne am Boden noch scheint (PO-Meldung Aabenraa 2026-11-17). Zugleich lief die Bewölkung auf vier getrennten Wegen zum Nutzer: roh direkt, roh über den Katalog, „effektiv" nur in der Übersicht des Ortsvergleichs (ab 2500 m ohne tiefe Wolken) und ein toter Rohpfad. Übersicht und Stundenwerte desselben Orts widersprachen sich.

## Entscheidung

1. „Bewölkung" bedeutet ab jetzt **wirksame Bewölkung**: tiefe (unterhalb 2500 m Standorthöhe) und mittelhohe Wolken zählen voll, der darüber hinausgehende Anteil der Gesamtbewölkung (hohe Wolken) zählt mit dem Gewicht 0,5. Ab 2500 m bleiben tiefe Wolken unter dem Standort außen vor. Fehlen die Schichten, gilt der Gesamtwert.
2. Die Regel existiert genau einmal in der Domänenschicht (`src/app/cloud_cover.py`) und wird genau einmal je Abruf in der Normalisierung angewendet (Ausgang `OpenMeteoProvider.fetch_forecast`, Offline-Spiegel `FixtureProvider`). `cloud_total_pct` trägt danach die wirksame Bewölkung, `cloud_total_model_pct` den Modellwert.
3. Kein Leser rechnet die Bewölkung selbst um; `WeatherMetricsService.calculate_effective_cloud` entfällt.
4. Feldnamen, Katalog-Kennungen, Kürzel und Ampel-Schwellen bleiben; keine Datenmigration.

## Verworfene Alternativen

- **Abgeleitetes Feld und Katalog-`dp_field` umhängen:** gespeicherte Nutzerformate sind teils über den Feldnamen verschlüsselt (Migration nötig), fünf Rohleser hätten einzeln umgebaut werden müssen.
- **Sonnenschein (DNI) statt Bewölkung für das Himmelssymbol:** bei tief stehender Sonne (Winter, Morgen/Abend) liegt die Einstrahlung auch bei klarem Himmel unter der Schwelle, nachts gibt es keine Aussage.
- **Regel je Leser:** der bisherige Zustand mit widersprüchlichen Werten.

## Konsequenzen

- **Positiv:** ein Wert für alle Kanäle und Flächen (Kanal-Parität), Schleierwolken realistischer, Hochlagen-Regel nun auch in Stundenwerten und im Trip.
- **Negativ / Preis:** `cloud_total_pct` ist nicht mehr der rohe Modellwert; wer ihn braucht, liest `cloud_total_model_pct`. Am ersten Tag nach dem Ausrollen vergleicht „vs. gestern" alt (roh) mit neu (wirksam).
- **Folgepflichten:** Jeder neue Anbieter-Ausgang, der Bewölkung liefert, ruft `normalisiere_bewoelkung`; kein Leser darf die Bewölkung erneut umrechnen. Aus Schnappschüssen geladene Punkte tragen bereits die wirksame Bewölkung (der Modellwert wird nicht gespeichert) und dürfen nie erneut normalisiert werden.
