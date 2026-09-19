# ADR-0074: Auffrischraster für den MeteoAlarm-Feed Deutschland — 30 Minuten, Bandbreite bewusst getragen

- **Status:** Akzeptiert
- **Datum:** 2026-09-19
- **Bezug:** GitHub-Issue #1681, Spec `docs/specs/modules/feat_1681_meteoalarm_de.md`; konkretisiert ADR-0039

## Kontext

ADR-0039 stellt amtliche Warnungen auf den kontingentfreien MeteoAlarm-Feed um und nennt als Preis,
dass jeder Abruf die vollständige Landesdatei ohne Kompression und ohne Änderungskennung liefert:
„Für weitere Länder ist deshalb ein eigenes Auffrischraster vorzusehen." Deutschland ist das dritte
Land. Gemessen am 2026-09-19: 5,5 MB je Abruf (254 Warnungen × 8 Sprachen), Server liefert trotz
`Accept-Encoding: gzip` unkomprimiert, kein ETag/Last-Modified, Abrufdauer 1,5–2,0 s.

## Entscheidung

Deutschland erhält einen eigenen Cache-Eintrag im Feed-Cache (Schlüssel = Ländercode `DE`) mit
demselben Raster wie Italien und Österreich: **1800 s nach Erfolg, 60 s nach Fehlschlag**. Der
Abruf-Timeout bleibt 15 s. Die daraus folgende Datenmenge von rund 240 MB pro Tag und Umgebung wird
bewusst getragen.

## Verworfene Alternativen

- **Gröberes Raster (45–60 min) nur für DE** — spart Bandbreite, die auf dem Server nichts Messbares
  kostet, und bezahlt dafür mit bis zu einer Stunde alten amtlichen Unwetterwarnungen, die auf allen
  vier Alarmkanälen ausgeliefert werden. Falsche Richtung für ein Sicherheitssignal.
- **Bedingter Abruf / Delta-Erkennung** — der Feed-Server bietet weder ETag noch Last-Modified;
  nicht umsetzbar.
- **MQTT-Push statt Voll-Abruf** — bleibt laut ADR-0039 eine spätere Ergänzung, braucht weiterhin
  den Feed als Bestandsquelle.

## Konsequenzen

- **Positiv:** Deutsche Warnungen sind so aktuell wie italienische und österreichische; kein
  länderspezifischer Sonderweg im Cache.
- **Negativ / Preis:** ca. 240 MB/Tag zusätzlicher eingehender Datenverkehr je Umgebung, ~0,06 s
  Parse-Zeit je Abruf.
- **Folgepflichten:** Wächst der DE-Feed (Unwetterlage, mehr Warnungen) so, dass ein Abruf die Hälfte
  des 15-s-Timeouts erreicht, ist das Raster neu abzuwägen — ein Timeout erzeugt „nicht abrufbar"
  und darf nicht zum Normalfall werden. Jedes weitere Land braucht dieselbe Abwägung mit eigener
  Messung.
