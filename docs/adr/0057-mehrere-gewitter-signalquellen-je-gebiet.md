# ADR-0057: Mehrere Gewitter-Signalquellen je Gebiet (additiv)

- **Status:** Akzeptiert
- **Datum:** 2026-08-18
- **Bezug:** Issue #1758 (GeoSphere liefert cape/cin, additiv zum DWD), Eltern-Epic #1419,
  ergänzt ADR-0025 (eine Gewitter-Quelle je Kanal-Ausgabe) und ADR-0047 (Vertretung bei
  echtem Dienstausfall) — löst keines von beiden ab.

## Kontext

`thunder_routing._REGIONS` galt bisher first-match-wins mit **genau einer** Gewitter-Quelle je
Gebiet (`thunder_provider_for()`). Für Österreich (Teil des Gebiets `DE_ALPEN`) lieferte das
bislang ausschließlich der DWD (`de_direct`, Blitzpotenzial über ICON-D2). GeoSphere (AROME,
2,5 km) führt für dasselbe Gebiet zusätzlich `cape`/`cin` — ein zweites, unabhängiges
Konvektionssignal, das der DWD nicht ersetzt und das bislang nie abgefragt wurde (#1758).

PO-Entscheid vom 2026-08-18: die Werte sollen **im Normalbetrieb** entstehen, nicht nur im
Open-Meteo-Totalausfall. Trüge man GeoSphere einfach als neue Zeile in `_REGIONS` ein, würde es
den DWD **verdrängen** (first-match-wins kennt nur eine Quelle je Gebiet) — eine Verschlechterung,
und das Ticket verlangt ausdrücklich ein zusätzliches, kein ersetzendes Signal.

Ein zweites Hindernis war der Fill-only-Wächter in `enrich_thunder` (`thunder_enrichment.py`):
er prüfte GLOBAL über alle bekannten Signalfelder — sobald irgendeine Quelle irgendein Feld
gefüllt hatte, brach die gesamte Anreicherung ab. Bei zwei Quellen je Gebiet käme die zweite
Quelle dadurch **nie** zum Zug, sobald die erste geliefert hat.

## Entscheidung

Mehrere Gewitter-Signalquellen je Gebiet sind **additiv erlaubt**:

- `thunder_routing._ThunderRegion` bekommt ein zusätzliches Feld `zusatzquellen: tuple = ()`.
  `DE_ALPEN` trägt `("geosphere",)`. Die bestehende primäre Zuordnung (`provider`) bleibt für
  `thunder_provider_for()` unverändert first-match-wins — Bestandsaufrufer und -Tests, die nur
  diese Funktion patchen, sehen keine Verhaltensänderung.
- Eine neue Funktion `thunder_providers_for(lat, lon) -> tuple[str, ...]` liefert **alle**
  zuständigen Quellen (primär + additiv). Sie baut auf `thunder_provider_for()` auf und ergänzt
  Zusatzquellen nur, wenn die Primärquelle **nicht von außen überschrieben** wurde — sonst würde
  ein Test, der ausschließlich `thunder_provider_for()` patcht, unbemerkt eine echte Zweitquelle
  (GeoSphere) miterhalten.
- `thunder_enrichment._fetch_lightning_density` verarbeitet die **primäre** Quelle unverändert
  (inkl. Vertretung bei echtem Ausfall, #1492 S2a/ADR-0047) und versucht **zusätzliche** Quellen
  **immer**, sobald sie zuständig sind — fail-soft pro Quelle, ohne Vertretungs-Eintrag.
- Der Fill-only-Wächter (`_primaerquelle_bereits_gefuellt`, vormals ein globaler Früh-Abbruch in
  `enrich_thunder`) gilt seither **nur noch für die Primärquelle**. Zusatzquellen führen keinen
  eigenen feldbasierten Wächter — sie werden bei jedem Anreicherungslauf versucht, solange sie
  zuständig sind.

## Abgrenzung

- **ADR-0025** ("eine Gewitter-Quelle für alle Briefing-Kanäle") betrifft die **Kanal**-Ebene:
  alle Kanäle lesen weiterhin dieselbe Rohgröße `dp.thunder_level`. Mehrere
  Beschaffungs-Quellen widersprechen dem nicht, solange am Ende genau ein `dp.thunder_level` aus
  der Fusion steht — GeoSphere-CAPE/CIN fließen dort explizit **nicht** ein
  (`_fuse_thunder_levels` liest ausschließlich `dp.cape_jkg`, nie `dp.cape_geosphere_jkg`). Kein
  "Abgelöst durch".
- **ADR-0047** (Vertretung zwischen Direktquellen bei echtem Ausfall) ist ein anderer,
  unberührter Mechanismus (`_VERTRETUNG`); GeoSphere bekommt dort bewusst **keinen** Eintrag —
  fällt es aus, bleiben seine zwei Felder einfach leer (fail-soft), wie jede Quelle ohne Eintrag
  dort heute auch.

## Konsequenzen

- Positiv: Österreich bekommt ein zweites, unabhängiges Konvektionssignal (cape/cin), ohne den
  produktiven DWD-Pfad zu gefährden. Andere Gebiete (FR, EU_REST) sind strukturell unverändert
  (keine Zusatzquelle eingetragen).
- Bekannte Nebenwirkung: jeder reguläre Anreicherungslauf für einen Punkt im `DE_ALPEN`-Gebiet
  löst jetzt zusätzlich einen GeoSphere-Abruf aus (fail-soft, best effort) — Bestandstests, die
  Karnisch-/Alpen-Koordinaten über den regulären Weg ohne GeoSphere-Stub verwenden, sehen dadurch
  einen zusätzlichen (scheiternden, aber abgefangenen) Netzversuch. Bleibt grün, aber langsamer;
  gebucht als Nebenbefund in #1199.
