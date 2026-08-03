---
entity_id: feat_1457_s2a_blitzdichte_meteofrance
status: draft
type: module
created: 2026-08-02
updated: 2026-08-02
version: "1.0"
tags: [gewitter, provider, meteofrance, s2a]
---

# Blitzdichte von Météo-France ins Datenmodell

## Approval

- [ ] Approved

## Purpose

Météo-France sagt für Frankreich und Korsika die **erwartete Blitzdichte** voraus
(`LITOTA3`, „Average lightning strike density over 3 hours"). Dieser Wert wird
abgerufen und in ein **eigenes Feld** des gemeinsamen Datenmodells gelegt — regulär
bei jeder Vorhersage, nicht nur bei Ausfall der Hauptquelle.

Erste Scheibe von S2 (#1457) aus dem Gewitter-Konzept #1419. **Für Korsika ist das
die beste verfügbare Gewitterquelle** (1,3 km Maschenweite, direkte Blitzvorhersage
statt Potenzialgröße).

## Source

- **File:** `src/providers/meteofrance.py`, `src/app/models.py`,
  `src/providers/openmeteo.py` (nachgetragen 2026-08-02 für AC-7 — Anschluss an den
  regulären Vorhersageweg, analog `_enrich_snow` bei `openmeteo.py:1123`)
- **Identifier:** `MeteoFranceDirectProvider.fetch_thunder_signals()` (neu),
  `ForecastDataPoint.lightning_density_per_km2_3h` (neu)

**Schicht:** Python-Core (`src/providers/`, `src/app/`). Keine Go-API, kein Frontend.

## Estimated Scope

- **LoC:** ~100 Quellcode + ~130 Tests = **~230**
- **Files:** 2 geändert, 1 Testdatei neu
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Météo-France WCS | externer Dienst | Zugang besteht seit #1143, kein neuer Vertrag |
| `rasterio` (`MemoryFile`) | Bibliothek | Punktwert aus der Antwort lesen (Muster `_read_point_value`) |
| `region_routing.direct_provider_for` | intern | bestimmt, ob ein Ort zu Frankreich gehört |

## Implementation Details

```
GEMEINSAMER WEG, KEIN PROVIDER-SONDERWEG (PO-Vorgabe 2026-08-02):

  1. Protokoll (providers/base.py): optionale Methode
        fetch_thunder_signals(location, start, end) -> Dict[int, Optional[float]]
     Wer sie nicht hat, liefert nichts -- kein Fehler. Jeder kuenftige Dienst
     dockt allein darueber an.

  2. Gewitter-Zustaendigkeit: EINE Tabelle Gebiet -> Providername, getrennt von
     der bestehenden `region_routing`-Tabelle fuer Temperatur/Wind/Schnee.
     Getrennt, WEIL die Zustaendigkeit groessenabhaengig ist: Oesterreich geht
     fuer Schnee an GeoSphere, fuer Gewitter aber an den DWD (GeoSphere hat
     kein Blitzsignal). Verwandtes Muster: ADR-0041.

  3. EINE Anreicherungsstelle im regulaeren Weg von
     OpenMeteoProvider.fetch_forecast (analog `_enrich_snow`, openmeteo.py:1123):
     zustaendige Quelle nachschlagen -> Protokollmethode rufen -> Felder setzen.
     Diese Stelle kennt KEINEN Providernamen und KEINE Coverage-ID.

  => S2b (DWD) und S2c (ICON-EU) fuegen danach nur noch einen Tabelleneintrag
     plus ihre Protokollmethode hinzu. Der Anschluss wird nie wieder angefasst.

Muster: Anreicherung, exakt wie `enrich_ensemble` bei Open-Meteo
  (openmeteo.py:640-680, 1050-1052) — best-effort, fail-soft, nie werfend.

1. ForecastDataPoint bekommt ein neues Feld:
     lightning_density_per_km2_3h: Optional[float] = None
   BEWUSST eigenes Feld, NICHT gemeinsam mit dem DWD-Blitzpotenzial
   (andere Groesse, andere Skala — s. #1419 Abschnitt 3.1).

2. MeteoFranceDirectProvider.fetch_thunder_signals(location, ...)
     -> Dict[datetime, Optional[float]]
   Coverage LITOTA3__GROUND___<lauf>, Muster _fetch_series,
   EIGENES Zeitbudget (nicht das der Grundvorhersage).
   Jede Ausnahme -> {} , nie werfen.

3. Anreicherung greift, wenn der Ort nach Frankreich faellt.
   Default eingeschaltet. Fehlt ein Wert -> Feld bleibt None.
```

## Expected Behavior

- **Input:** eine Position mit Zeitraum
- **Output:** dieselbe Vorhersage wie heute, zusätzlich mit gefülltem Blitzdichte-Feld
  an französischen/korsischen Orten
- **Side effects:** zusätzliche HTTP-Abrufe an Météo-France (Kosten s. Known Limitations)

## Acceptance Criteria

- **AC-1:** Given eine Position auf Korsika (GR20, 42.22 N / 9.07 O) / When eine
  Vorhersage abgerufen wird / Then trägt mindestens ein Zeitpunkt einen Blitzdichte-Wert
  aus Météo-France, während dieselbe Abfrage heute für alle Zeitpunkte leer bleibt.
  - Test: Gegen eine aufgezeichnete Météo-France-Antwort wird nachgewiesen, dass der
    Wert am Datenpunkt ankommt; ohne die Änderung ist das Feld durchgängig leer.

- **AC-2:** Given Météo-France liefert für einen Zeitpunkt keinen Wert / When die
  Vorhersage gebaut wird / Then bleibt das Feld **leer** — es wird **nie** auf 0
  gesetzt.
  - Test: Eine Antwort ohne Wert für eine Stunde erzeugt an diesem Zeitpunkt `None`;
    ein Test, der 0 erwartet, muss fehlschlagen. „Keine Aussage" ist nicht „keine
    Gefahr" (#1419 Abschnitt 5).

- **AC-3:** Given der Abruf der Blitzdichte scheitert vollständig (Serverfehler,
  Zeitüberschreitung, Netzfehler) / When eine Vorhersage abgerufen wird / Then wird sie
  **trotzdem vollständig geliefert**, nur ohne Blitzdichte — der Fehler kippt die
  Vorhersage nicht.
  - Test: Ein Abruf, der eine Ausnahme wirft, führt zu einer vollständigen Vorhersage
    mit Temperatur und Wind und leerem Blitzdichte-Feld. Gegenprobe: Wird das Werfen im
    Anreicherungspfad zugelassen, muss der Test rot werden.

- **AC-4:** Given die Blitzdichte-Abrufe brauchen ungewöhnlich lange / When das
  Zeitbudget der Anreicherung erschöpft ist / Then bricht **nur die Anreicherung** ab,
  und die Grundvorhersage behält ihr eigenes, unangetastetes Budget.
  - Test: Mit künstlich kleingesetztem Anreicherungsbudget gegen einen langsamen
    lokalen Server endet der Aufruf innerhalb der Grenze und liefert die
    Grundvorhersage; die Laufzeit belegt, dass nicht auf das große Budget gewartet
    wurde. (Muster `tests/tdd/test_meteofrance_direct_fallback.py:476-517`.)

- **AC-5:** Given eine Aufrufstelle, die den Anreicherungs-Schalter nicht ausdrücklich
  setzt / When sie eine Vorhersage für einen französischen Ort abruft / Then wird die
  Blitzdichte **trotzdem** geholt — der Standardwert schützt.
  - Test: Ein Aufruf ohne den Schalter füllt das Feld. (#1448-Lehre: Ein Schutz, der an
    einem durchzureichenden Parameter hängt, ist kein Schutz.)

- **AC-6:** Given ein Ort außerhalb Frankreichs / When eine Vorhersage abgerufen wird /
  Then findet **kein** Météo-France-Abruf statt und das Feld bleibt leer.
  - Test: Für einen Ort in den Alpen wird nachgewiesen, dass kein Abruf ausgelöst wird —
    sonst entstehen sinnlose Abrufe außerhalb des Modellgebiets.

- **AC-7 (nachgetragen 2026-08-02):** Given ein Ort in Frankreich oder auf Korsika und
  eine **normal verfügbare Hauptquelle** / When eine Vorhersage über den **regulären**
  Weg abgerufen wird (`OpenMeteoProvider.fetch_forecast`, **kein** Ausfall) / Then trägt
  der Datenpunkt eine Blitzdichte.
  - Test: Eine reguläre Vorhersage mit funktionierender Hauptquelle für einen
    Korsika-Ort füllt das Feld. Gegenprobe: Wird der Anreicherungsaufruf aus dem
    regulären Weg entfernt und nur in der Totalausfall-Weiche belassen, **muss** dieser
    Test rot werden.

- **AC-8 (PO-Vorgabe 2026-08-02, „keine Einzellösungen"):** Given ein **zweiter**
  Wetterdienst, der Gewittersignale liefern kann (S2b: DWD) / When er als zuständige
  Gewitterquelle für sein Gebiet eingetragen wird / Then wird er wirksam, **ohne dass
  der Anreicherungsweg angefasst werden muss** — es genügt, dass er das gemeinsame
  Protokoll erfüllt und in der Zuständigkeitstabelle steht.
  - Test: Ein zweiter Provider (im Test ein einfacher Doppelgänger, der das Protokoll
    erfüllt) wird für ein Testgebiet eingetragen und liefert seine Werte bis zum
    Datenpunkt — **ohne eine einzige Änderung** an `OpenMeteoProvider.fetch_forecast`
    oder an der Anreicherungsfunktion. Gegenprobe: Enthält der Anreicherungsweg
    irgendwo eine Abfrage auf einen konkreten Providernamen (`fr_direct`,
    `MeteoFranceDirectProvider`, `LITOTA3`), **muss** dieser Test rot werden.
  - **Warum:** Ohne dieses AC entstünde für jede Quelle ein eigener Sonderweg — bei
    drei Gebieten drei Anschlüsse, die auseinanderdriften. Das Konzept #1419
    Abschnitt 5 verlangt das Gegenteil: *„Der Provider füllt nur Felder. Die Einstufung
    liest nur Felder, nie einen Provider. Ein neuer Dienst wird automatisch wirksam,
    sobald er ein bekanntes Feld füllt."* **AC-8 macht diese Aussage prüfbar,** statt
    sie als Absichtserklärung stehen zu lassen. Dasselbe Prinzip wie die
    Trip/Ortsvergleich-Teilung in `CLAUDE.md`: Eine neue Komponente, zu der ein Pendant
    existiert, ist per Default ein Verstoß.
  - **Warum dieses AC nachgetragen wurde — die eigentliche Lehre dieser Scheibe:**
    AC-1 bis AC-6 prüfen ausschließlich den Météo-France-Provider *selbst*. Alle sechs
    waren erfüllt, der Adversary hatte VERIFIED erteilt und sieben Mutationen gefangen —
    und trotzdem erreichte die Blitzdichte **nie einen Nutzer**, weil
    `MeteoFranceDirectProvider.fetch_forecast` im gesamten Produktivcode nur an einer
    einzigen Stelle aufgerufen wird (`openmeteo.py:1006`), und die steht unter
    `if response_data is None:` — also nur bei **Totalausfall** von Open-Meteo.
    **Ein AC, das nur die Einheit prüft, in der der Code steht, belegt nicht, dass diese
    Einheit im Produkt erreicht wird.** Verspricht eine Scheibe „X passiert regulär statt
    nur im Sonderfall", braucht sie ein AC über den **Aufrufweg**, nicht nur über das
    Verhalten der aufgerufenen Funktion.

- **AC-9 (neu gefasst 2026-08-02 nach Adversary-Befund F002):** Given zwei nahe
  beieinander liegende Orte in Frankreich / When für **beide nacheinander** eine Vorhersage
  über den **regulären Weg** abgerufen wird / Then entstehen zusammen **nicht mehr** Abrufe
  als für einen einzigen Ort — **unabhängig davon, ob die Orte aus einem Trip oder einem
  Ortsvergleich stammen**.
  - Test: Zwei Aufrufe von `OpenMeteoProvider.fetch_forecast` für benachbarte Korsika-Orte
    erzeugen zusammen so viele Météo-France-Abrufe wie ein einzelner. Gegenprobe: Wird der
    geteilte Zwischenspeicher umgangen, muss der Test rot werden.
  - **Warum neu gefasst:** Die erste Fassung prüfte, ob eine Methode mehrere Orte
    *verarbeiten kann*. Sie konnte es — wurde aber im gesamten Produktivcode nur mit
    Ein-Element-Listen aufgerufen (`thunder_enrichment.py:117`), weil die Anreicherung je
    **einzelnem** Abruf sitzt. Trip und Ortsvergleich rufen beide Ort für Ort. **Damit war
    AC-9 erfüllt und wirkungslos zugleich** — dasselbe Muster wie AC-7, zum zweiten Mal in
    derselben Scheibe.
  - **Bauweise — Richtlinie „Trip/Ortsvergleich-Teilung" (`CLAUDE.md`):** Die Sammlung
    gehört **nicht** in einen Aufrufer. Ein Aufrufer-Umbau wäre ein Sonderweg für den
    Ortsvergleich, während der Trip weiter einzeln abruft — genau der Verstoß, den die
    Richtlinie benennt. Stattdessen **ein geteilter Zwischenspeicher mit
    Rechteck-Granularität** eine Ebene tiefer: Ein Abruf lädt ein Rechteck, jeder weitere
    Ort darin wird daraus bedient. **Kein Aufrufer muss geändert werden**, beide Seiten
    profitieren automatisch. Vorbild und Infrastruktur: `weather_cache.py`
    (`WeatherCacheService`, Singleton mit `Lock`, TTL, LRU) — heute bereits von Trip **und**
    Ortsvergleich gemeinsam genutzt.
  - **Warum, gemessen am 2026-08-02 gegen die Live-API:** Die WCS-Schnittstelle nimmt ein
    beliebig großes Rechteck entgegen, bei nahezu gleicher Antwortzeit —
    1 Punkt 0,49 s / 445 B · Korsika ganz 0,43 s / 81 KB · Südost-Frankreich 0,65 s /
    1,3 MB · ganz Frankreich 0,91 s / 3,9 MB. Der Provider fragt heute je Ort ein
    0,1°-Kästchen ab (`meteofrance.py:226-227`) und verwirft alles außer einem Pixel.
  - **Kontingent-Bezug (der eigentliche Grund) — vom PO am 2026-08-02 aus dem
    Météo-France-Portal bestätigt, keine Annahme mehr:**

    | Eigenschaft | Wert |
    |---|---|
    | Rate-Limit | **100 Anfragen pro Minute** (seit Januar 2026) |
    | Geltungsbereich | **pro API und pro Benutzerkonto** |
    | vorher | 50/min (bis Ende 2025) |
    | bei Überschreitung | HTTP 429 |

    **Wir haben genau ein Konto** — alle Trips und Ortsvergleiche aller Nutzer teilen sich
    diese 100/min. Ein 8-Orte-Vergleich in der Punktform erzeugt **192 Abrufe** und
    überschreitet das Limit klar; die Punktabfrage ist damit **nicht nur langsam, sondern
    regelwidrig**. Mit gemeinsamem Fenster: 24 Abrufe je Gebiet.

    ⚠️ **Restrisiko, bewusst offen (gehört in eine Folge-Scheibe):** Die 24 Abrufe gelten je
    **Gebiet**, nicht je Lauf. Nutzer in verschiedenen Regionen Frankreichs (Korsika,
    Pyrenäen, Alpen) laden getrennte Kacheln — **vier Gebiete in derselben Minute sind
    bereits 96 Abrufe**, fünf sprengen das Limit. Der Zwischenspeicher hilft nur bei
    Überlappung. Zwei Gegenmittel, beide noch nicht gebaut: (a) eine **aktive Drosselung**,
    die Abrufe je Minute zählt und wartet (Muster: `telegram.py` Sende-Drossel), statt auf
    Einhaltung zu hoffen — sonst erscheinen HTTP-429-Abweisungen im Betrieb als „keine
    Gewitterdaten verfügbar"; (b) **größere Kacheln bei verstreuten Nutzern** — ganz
    Frankreich kostet 0,91 s gegen 0,43 s für Korsika allein, aus 96 Abrufen würden wieder 24.
  - **Wirkung:** 8-Orte-Vergleich von 192 Abrufen / 64 s auf 24 Abrufe / ~9 s,
    Grenzkosten je weiterem Ort **null**.

- **AC-10 (nachgetragen 2026-08-02):** Given ein Abrufzeitraum, der kürzer als 24 Stunden
  ist (der Ortsvergleich nutzt ein Ein-Stunden-Fenster) / When die Blitzdichte geholt wird /
  Then werden **nur die Stunden dieses Zeitraums** abgerufen.
  - Test: Ein Lauf mit Ein-Stunden-Fenster erzeugt deutlich weniger Abrufe als einer mit
    24-Stunden-Fenster. Gegenprobe: Ignoriert der Code den Zeitraum, muss der Test rot werden.
  - **Warum:** `fetch_thunder_signals` ignoriert seinen `end`-Parameter und läuft immer
    `FORECAST_HOURS` = 1…24 (`meteofrance.py:298`). Im Compare-Pfad (synthetisches
    1-Stunden-Fenster, `compare_location_weather_source.py:44-45`) sind dadurch rund
    **13 von 24 Abrufen je Ort systematisch verworfene Arbeit**.

- **AC-11 (nach Adversary-Befund F001):** Given mehrere Orte, die im selben Abfragefenster
  liegen / When ihre Blitzdichte gelesen wird / Then bekommt **jeder Ort seinen eigenen
  Wert** — Orte an unterschiedlichen Stellen des Fensters dürfen **nicht** denselben Wert
  tragen.
  - Test: Gegen die aufgezeichnete **Korsika**-Antwort
    (`tests/fixtures/meteofrance/arome_korsika_litota3_20260802.grib2`, deckt 41,30–43,11 N /
    8,39–9,60 O) wird nachgewiesen, dass Orte mit belegt unterschiedlichen Werten auch
    unterschiedliche Werte bekommen (gemessen am 2026-08-02: Petra Piana 0,124 ·
    Ascu Stagnu 0,0 · Vizzavona 0,254 · Bavella 0,0).
  - **Warum:** Der bisherige Test prüfte nur `any(v is not None)` je Ort — nie
    Verschiedenheit. Gegen das alte **Paris**-Fixture lieferten **alle acht Korsika-Orte
    exakt denselben Wert** (`25.311547851562523`), weil `_read_point_value`
    (`meteofrance.py:186-201`) Koordinaten außerhalb des Gitters **auf den Randpixel
    klemmt**. Werte waren da, aber vom falschen Ort — und der Test, dessen erklärter Zweck
    genau das war, konnte es strukturell nicht sehen. Dieselbe Falle stand seit dem Morgen
    als Risiko Nr. 1 in `docs/context/feat-1456-lpi-schwellen.md`.
  - **Zusatzbedingung:** Liegt ein Ort **außerhalb** des geladenen Fensters, wird sein Wert
    **verworfen** (`None`), nicht auf den Rand geklemmt.

- **AC-12 (nach Adversary-Befund F005):** Given ein Ort, für den Grundvorhersage und
  Gewitter aus **verschiedenen** Quellen kommen / When die Gewitter-Zuständigkeit bestimmt
  wird / Then entscheidet die **Gewitter**-Zuständigkeitstabelle
  (`thunder_routing.thunder_provider_for`), nicht die der Grundvorhersage
  (`region_routing.direct_provider_for`).
  - Test: Ein Ort, bei dem beide Tabellen unterschiedlich antworten, wird nachweislich über
    die Gewitter-Tabelle bedient.
  - **Warum:** `fetch_thunder_signals_multi` filtert heute über die Grundvorhersage-Tabelle.
    Für Frankreich sind beide identisch, deshalb heute folgenlos — **bei S2b bricht es
    genau am Zielfall:** Österreich bekommt Schnee und Temperatur von GeoSphere, Gewitter
    aber vom DWD, weil GeoSphere kein Blitzsignal führt. Der Karnische Höhenweg wäre der
    erste betroffene Ort.

## Known Limitations

0. **Der geteilte Zwischenspeicher bündelt gleichzeitige Abrufe nicht** (Adversary-Befund
   F-ADV3, MEDIUM). Zwei Threads, die dieselbe Kachel anfordern, laden **beide** —
   gemessen 48 statt 24 Abrufe. Das widerspricht der eigenen Modulbegründung
   („Thread-Sicherheit ist Pflicht, die Orts-Schleife kann parallelisiert werden").
   **Heute nicht erreichbar**, weil alle Aufrufer (Trip wie Ortsvergleich) sequentiell
   laufen — deshalb bewusst nicht in dieser Scheibe behoben.
   **Wird relevant, sobald der Alarm-Lauf parallelisiert wird**, und ist dann ein
   Kontingent-Risiko (100 Anfragen/min, PO-bestätigt). Gehört gemeinsam mit der
   **aktiven Drosselung** (s. AC-9, Restrisiko) in eine eigene Scheibe — beide betreffen
   dieselbe Stelle und dieselbe Frage.

1. **Hagel ist nicht Teil dieser Scheibe.** `DIAG_GRELE` lieferte am Messtag klare
   Werte (4,9 gegen 0,0), aber der Beschreibungs-Endpunkt antwortet dauerhaft mit
   HTTP 502 — die **Bedeutung und Einheit sind ungeklärt**. Auf einer Vermutung zu
   bauen wäre bei einem Sicherheitssignal falsch. Eigene Scheibe, sobald geklärt.
2. **Abrufkosten.** Météo-France liefert einen Wert je Größe **und Stunde**; heute
   entstehen ~96 Abrufe je Ort, diese Scheibe fügt bis zu 24 hinzu. Bewusst bezahlt
   (PO-Vorgabe „maximale Qualität"), aber der Grund für das getrennte Zeitbudget.
3. **Enge Ostgrenze.** Das Frankreich-Rechteck endet bei 9,7 O (`region_routing.py:36`);
   Petra Piana liegt bei 9,07 O. Für Korsika trägt es, die Marge ist aber klein — ein
   Ort weiter östlich fiele heraus. Wird in **S2c** (Lückenfüller) aufgefangen.
4. **Noch nichts für den Nutzer sichtbar.** Der Wert liegt im Datenmodell; Stufe (S3)
   und Ausgaben (S5) folgen. Bewusst: Erst wenn das Signal verlässlich anliegt, kann
   eine Warnung darauf aufsetzen.
5. **Nur Frankreich und Korsika.** Alpen und Deutschland folgen in S2b über den DWD.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine für diese Scheibe
- **Rationale:** Additives Feld und ein zusätzlicher Anreicherungsaufruf nach
  bestehendem Muster (`enrich_ensemble`) — keine neue Entscheidungsfläche. Die
  **größenabhängige Zuständigkeit** (Gewitter aus einer anderen Quelle als Temperatur)
  wird erst in **S2b** entschieden und braucht dort ein ADR im Muster von **ADR-0041**.

## Changelog

- 2026-08-02: Initial spec created (Issue #1457 S2a, Konzept #1419)
