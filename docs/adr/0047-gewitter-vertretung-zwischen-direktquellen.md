# ADR-0047: Gewitter-Vertretung zwischen Direktquellen bei echtem Dienstausfall

- **Status:** Akzeptiert (PO-„go" 2026-08-06 zur Spec `feat_1492_s2a_thunder_vertretung.md`)
- **Datum:** 2026-08-06
- **Bezug:** GitHub-Issue #1492, Spec `docs/specs/modules/feat_1492_s2a_thunder_vertretung.md`,
  Kontext `docs/context/feat-1492-gewitter-fallback-kette.md` (Abschnitte 3, 4, 7 und „Scheibe 2 —
  PO-Entscheidungen 2026-08-06"); erweitert [ADR-0018](0018-provider-fallback-ohne-kaschieren.md)
  (Modell-Fallback ohne Kaschieren); grenzt sich ab von [ADR-0025](0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md)
  (Eine Gewitter-Quelle für alle Briefing-Kanäle); Vorgänger-Scheibe (unabhängig):
  `docs/specs/modules/fix_1492_s1_wettercode_fallback.md` (kein ADR nötig, additive Lückenschließung).

## Kontext

Gewittersignale kommen für Teile Europas aus spezialisierten Direktquellen statt aus dem
Open-Meteo-Verteiler: `fr_direct` (Météo-France AROME, Blitz**dichte**) für Frankreich/Korsika,
`de_direct` (DWD ICON-D2, Blitz**potenzial** + Hagel) für Deutschland/Alpen/Österreich,
`eu_direct` (DWD ICON-EU, Blitzpotenzial, kein Hagel) als Lückenfüller für den Rest Europas
(`providers/thunder_routing.py::_REGIONS`, first-match-wins, Issue #1457 S2a–c). Fällt eine
dieser Quellen aus, schluckt `enrich_thunder()` das heute vollständig (fail-soft,
`thunder_enrichment.py:157-160`) — die Gewitteraussage wird lautlos leerer, ohne Vertretung und
ohne Herkunftsvermerk.

Die Provider fangen ihre eigenen Fehler bereits selbst ab (zehn `except Exception`-Stellen in
`thunder_enrichment.py`, `dwd.py`, `dwd_eu.py`, `meteofrance.py`) und liefern dann ein leeres
Ergebnis zurück — ununterscheidbar von zwei fachlich völlig anderen Fällen: dem Ort außerhalb
des Modellgebiets (die leere Antwort ist korrekt) und „kein Gewitter in Sicht" (die Antwort ist
korrekt und nicht leer, nur unauffällig). Eine Vertretung, die diese drei Fälle nicht trennt,
würde entweder nutzlos oft eingreifen (bei jeder geografischen Nichtzuständigkeit) oder gar
nicht (wenn sie sich vor der Unterscheidung drückt).

Das Muster für „Ausweichen, aber ohne Kaschieren" existiert bereits: **ADR-0018**, akzeptiert
für den intra-Open-Meteo-Modell-Fallback der Grundvorhersage. Dieses ADR wendet dasselbe Muster
auf eine zweite Domäne an — es erfindet keine neue Fallback-Architektur.

## Entscheidung

1. **Fehlerunterscheidung vor jeder Vertretung.** Ein Provider darf einen neuen, optionalen
   Ausnahmetyp (`providers.base.ThunderSourceUnavailableError`) werfen, wenn und nur wenn ALLE
   tatsächlich versuchten Abrufe eines Aufrufs an Verbindungsfehler/Zeitüberschreitung
   scheiterten. Eine erfolgreiche, aber inhaltlich leere Antwort (Gitterrand-Füllwert, „kein
   Gewitter") wirft NICHT. Ein einzelner fehlgeschlagener Zeitpunkt unter vielen erfolgreichen
   ist kein Dienstausfall und wirft ebenfalls NICHT — nur „alle Punkte gescheitert"
   rechtfertigt die Vertretung. Diese Unterscheidung wird nur dort implementiert, wo sie eine
   Wirkung hat: bei `de_direct` und `fr_direct`, die beide eine Vertretung haben. `eu_direct`
   hat keine Vertretung und bleibt unverändert — sein Ausfall hat niemanden, der ihn auffangen
   könnte.
2. **Vertretung ist benannt, nicht generisch.** Jede Region hat höchstens EINE Ersatzquelle,
   festgelegt in einer eigenen Tabelle (`thunder_routing.thunder_vertretung_for`), getrennt von
   der first-match-wins-Primärauswahl (`_REGIONS`/`thunder_provider_for`, die **unangetastet**
   bleibt): `de_direct → eu_direct`, `fr_direct → eu_direct`, `eu_direct → keine`.
3. **Der Vertrag „wirft NIE" bleibt nach außen unverändert.** `ThunderSignalProvider` und
   `enrich_thunder()` versprechen weiterhin, dass ein Ausfall der Gewitterquelle die
   Grundvorhersage nicht kippt. `ThunderSourceUnavailableError` wird ausschließlich INNERHALB
   von `thunder_enrichment.py` abgefangen — scheitert auch die Vertretung, propagiert die
   Ausnahme zum bestehenden äußeren Fang, unverändertes Fail-soft-Verhalten.
4. **Nicht-Kaschieren-Invariante (ADR-0018-Muster):** Jede erfolgreiche Vertretung wird markiert
   (`ForecastMeta.fallback_model`, `fallback_reason="thunder_source_unavailable"`,
   `fallback_metrics`) und protokolliert (`logger.warning`).
5. **Messgrößenwechsel `fr_direct → eu_direct` ist erlaubt, aber niemals stillschweigend.**
   Météo-France liefert eine Blitz**dichte** (`LITOTA3`-Nachfolgegröße, Blitze/km²/3h, Messwert
   GR20 typisch 0,1–0,2), DWD ICON-EU ein Blitz**potenzial** (`lpi`, J/kg, Messwert typisch 88,2)
   — **keine gemeinsame Skala**. Die Vertretung schreibt strukturell (nicht per Sonderfall-Code)
   in das Feld, das die ERSATZQUELLE selbst benennt (`lightning_potential_lpi_jkg`), niemals in
   das Feld der Primärquelle (`lightning_density_per_km2_3h`) — beide Felder speisen dieselbe
   Stufen-Fusion (`thunder_level_from_signals()`) mit je eigener Schwellentabelle, es entsteht
   keine Vermischung. **PO-Freigabe 2026-08-05:** eine etwas anders hergeleitete Gewitterstufe
   ist besser als keine, Bedingung ist der transparente Vermerk (Entscheidung 4).
6. **Kein Zeitbudget-Sonderweg zwischen Primär- und Ersatzquelle.** Die Ersatzquelle bekommt ihr
   volles, eigenes Zeitbudget statt einer aus der Primärquelle übrig gebliebenen Restzeit —
   PO-Entscheidung 2026-08-06: Briefings entstehen asynchron, die Laufdauer einzelner
   Anreicherungsschritte ist unkritisch, solange die Grundvorhersage nicht kippt. Das
   grundsätzliche Zeitbudget-Thema (sequenzielle Verarbeitung, 15-Minuten-Alarmtakt) ist als
   #1539 erfasst und liegt außerhalb dieser Entscheidung.

## Abgrenzung zu ADR-0025

ADR-0025 („Eine Gewitter-Quelle für alle Briefing-Kanäle") legt fest, dass es für die
**Ausgabe** genau eine Rohdaten-Quelle gibt: `dp.thunder_level`, gelesen aus `seg.timeseries`.
Kein Kanal (E-Mail, SMS, Telegram) darf eine eigene Ableitung bauen. Dieses ADR ändert daran
**nichts** — es betrifft ausschließlich, wie `dp.thunder_level`/die Rohsignalfelder
(`lightning_potential_lpi_jkg` etc.) VOR der Ausgabe befüllt werden, wenn die dafür zuständige
Direktquelle ausfällt. Die Anzahl der **Bezugs**-Quellen (heute bis zu zwei je Ort: Primär- und
Ersatzquelle) ist eine andere Frage als die Anzahl der **Ausgabe**-Quellen (weiterhin genau
eine: `dp.thunder_level`, gefüttert aus `thunder_level_from_signals()`). Ohne diese Abgrenzung
wirkte dieses ADR wie ein Bruch von ADR-0025 — das ist es nicht.

## Verworfene Alternativen

- **Generelle Kandidatenliste statt benannter Vertretung** (jede Region probiert alle
  verfügbaren Quellen der Reihe nach durch) — verworfen: kostet die first-match-wins-Reihenfolge
  der Primärauswahl (`decision_matrix.md:113-144` „Die Reihenfolge ist tragend", mit eigener
  Mutations-Gegenprobe in `feat_1457_s2c_icon_eu_luekenfueller.md` AC-8), kostet die
  Herkunfts-Eindeutigkeit (bei mehreren Kandidaten ist unklar, welcher „der" Ersatz war), ohne
  fachlichen Mehrwert — es gibt je Ort maximal eine sinnvoll benachbarte Ersatzquelle.
- **Stilles Ausweichen ohne Herkunftsvermerk** — verworfen aus demselben Grund wie in ADR-0018:
  ein erfolgreicher, unmarkierter Fallback macht einen andauernden Ausfall unsichtbarer, nicht
  sichtbarer.
- **Ausfall UND geografische Nichtzuständigkeit gleich behandeln** (jede leere Antwort löst
  Vertretung aus) — verworfen: hätte bei jedem „kein Gewitter in Sicht" und jedem Ort außerhalb
  des Modellgitters einen unnötigen zweiten Abruf ausgelöst, ohne dass ein echter Fehler vorlag —
  reine Lastverschwendung ohne fachlichen Gewinn, zusätzlich schwerer zu debuggen (Vertretung
  ohne erkennbaren Grund).
- **Ein eigenes, gewitterspezifisches `ForecastMeta`-Feldpaar statt Wiederverwendung der
  bestehenden `fallback_*`-Felder** — nicht gewählt, weil die bestehenden Felder exakt dafür
  existieren (#1115/ADR-0018) und ein zweites Paar dieselbe Semantik verdoppelt hätte; siehe aber
  Known Limitations der Spec Punkt 3 zur seltenen Kollision zweier gleichzeitiger Fallback-Arten
  auf denselben Singularfeldern und der daraus folgenden Pflicht für Scheibe 2b, zusätzlich
  `fallback_metrics` auszuwerten — akzeptierter Kompromiss, kein Show-Stopper.
- **Auch `eu_direct` mit der Fehlerunterscheidung ausstatten** — verworfen (PO/team-lead-Review
  2026-08-06): `eu_direct` hat keine eigene Vertretung, ein Ausfall hat niemanden, der ihn
  auffangen könnte — die Unterscheidung dort hätte keine Wirkung, nur Code-Umfang ohne Nutzen.
  `dwd_eu.py` bleibt deshalb vollständig unverändert.

## Konsequenzen

- **Positiv:** Ein Netzwerkausfall bei Météo-France oder beim DWD ICON-D2-Endpunkt führt nicht
  mehr zu einer lautlos ärmeren Gewitteraussage — die Nachbarquelle liefert eine (etwas gröbere,
  bei `fr_direct` anders hergeleitete) Ersatzaussage, nachvollziehbar markiert.
- **Negativ / Preis:** Bei `fr_direct → eu_direct` wechselt die zugrunde liegende physikalische
  Größe (Dichte → Potenzial) — akzeptiert per PO-Freigabe, Bedingung ist die Markierung. Ein
  ausgelöster Vertretungsversuch kostet zusätzliche Latenz (bis zu 115s Worst Case bei
  `de_direct → eu_direct`, volles eigenes Zeitbudget statt Restzeit-Weitergabe, s. Entscheidung
  6) und zusätzliche Last bei den externen Direktquellen — beides nur im Fehlerfall, nicht im
  Normalbetrieb, und laut PO unkritisch, weil Briefings asynchron entstehen (das grundsätzliche
  Zeitbudget-Thema ist #1539, außerhalb dieser Entscheidung).
- **Folgepflichten:**
  - `docs/reference/api_contract.md:241` und
    `docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md` (Known Limitations Punkt 4)
    behaupten beide, die Herkunft eines Gewitterwerts sei allein über die Position
    (`thunder_provider_for()`) rekonstruierbar — das gilt mit Vertretung nicht mehr und wird
    korrigiert (Teil des Umfangs von Scheibe 2a, kein Code).
  - Neue degradierbare Gewitter-Pfade (z. B. eine vierte Direktquelle) erben dieselbe
    Fehlerunterscheidungs- und Markierungspflicht, sofern sie eine eigene Vertretung haben.
  - Das in ADR-0018 geforderte wachsende Health-Signal für andauernde Ausfälle ist für die
    Gewitter-Domäne **noch nicht** nachgezogen — bewusst vertagt auf ein eigenes Folge-Issue
    (Spec Known Limitations Punkt 2), keine offene Lücke innerhalb dieser Scheibe.
  - ~~Sichtbarkeit im Briefing (E-Mail-/Telegram-Fußzeile) ist eigene Folgescheibe 2b; 2a hält die
    Herkunft nur intern fest.~~ **Erledigt mit #1492 Scheibe 2b (live seit 2026-08-07,
    `35b41753`).** Die Vertretung erscheint in Klartext in der Trip-Briefing-Mail (Vollversion
    und Kompakt) sowie in der Telegram-Langform; SMS und Telegram-Kurzform bleiben bewusst
    ausgenommen (160-Zeichen-Budget). Formulierung zentral in
    `src/output/renderers/fallback_notice.py`, Spec
    `docs/specs/modules/feat_1492_s2b_fallback_sichtbarkeit.md`. Die Auflage aus Known
    Limitations Punkt 3 ist eingehalten: die Gewitterzeile erkennt die Vertretung an
    `fallback_metrics`, **nicht** an `fallback_model`, und nennt im Kollisionsfall bewusst
    keinen Quellennamen, statt den Namen des Grundvorhersage-Ersatzmodells zu führen.
    **Offen bleibt allein die Ortsvergleichs-Mail** (mehrere Orte mit je eigener Herkunft) —
    eigenes Folge-Issue **#1563**.

## Changelog

- 2026-08-06 (Nachbesserung nach team-lead-Review): Entscheidung 6 (kein Zeitbudget-Sonderweg,
  PO-Entscheidung, Verweis #1539) ergänzt; verworfene Alternative „auch `eu_direct` instrumentieren"
  ergänzt (`dwd_eu.py` bleibt unverändert); Folgepflicht zu `fallback_metrics` für Scheibe 2b
  präzisiert.
- 2026-08-06 (initial): ADR erstellt zusammen mit Spec `feat_1492_s2a_thunder_vertretung.md`,
  Status „Vorgeschlagen" bis PO-„go" zur Spec vorliegt.
