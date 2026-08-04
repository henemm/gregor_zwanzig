---
entity_id: feat_1457_s2b_gewitter_dwd_alpen
status: draft
type: module
created: 2026-08-03
updated: 2026-08-03
version: "1.0"
tags: [gewitter, provider, dwd, icon-d2, s2b]
---

# DWD ICON-D2 liefert Blitzpotenzial und Hagel für Deutschland/Alpen/Österreich

## Approval

- [ ] Approved

## Purpose

DWD ICON-D2 sagt für Deutschland, die Alpen und Österreich zwei
Gewittersignale voraus: ein **Blitzpotenzial** (energiebasierte Größe,
literaturüblich `lpi`/`lpi_max`) und ein **Hagelsignal**
(literaturüblich `grau_gsp`). Beide werden künftig regulär abgerufen und in
**zwei eigene Felder** des gemeinsamen Datenmodells gelegt — über denselben
gemeinsamen Mechanismus (Protokoll + Zuständigkeitstabelle + EIN
Anreicherungspunkt), den S2a (Météo-France, live seit 2026-08-03) bereits
etabliert hat.

Zweite Scheibe von S2 (#1457) aus dem Gewitter-Konzept #1419. Auslöser: die
nächste Tour geht zum Karnischen Höhenweg (Grenze Österreich/Italien) — dort
liefert die heutige Grundvorhersage-Zuständigkeit (GeoSphere, `at_direct`)
kein Gewittersignal.

> ⚠️ **Namensfalle, bereits einmal eingetreten (S2a, `LITOTA3`):** `lpi`,
> `lpi_max` und `grau_gsp` sind Kurzformen aus der Fachliteratur, **keine
> bestätigten DWD-Open-Data-Feldnamen**. Bei Météo-France hieß dieselbe Falle
> `LITOTA3` — der Name kam beim echten Dienst 0-mal vor, jeder Abruf lief
> lautlos in 404, während alle 24 aufgezeichneten Tests grün blieben. Vor der
> Implementierung MUSS das echte Verzeichnis auf `opendata.dwd.de` geprüft
> werden (s. AC-6). Diese Spec schreibt die Kurzformen bewusst nur als
> **Arbeitshypothese** fest, nicht als bestätigten Vertrag.

## Source

- **File:** `src/providers/dwd.py`, `src/providers/base.py`,
  `src/providers/thunder_enrichment.py`, `src/providers/thunder_routing.py`,
  `src/app/models.py`
- **Identifier:** `DwdDirectProvider.fetch_thunder_signals_named()` (neu),
  `ThunderSignalProvider.fetch_thunder_signals_named` (neues optionales
  Protokoll-Element), `ForecastDataPoint.lightning_potential_lpi_jkg` (neu),
  `ForecastDataPoint.hail_potential_grau_gsp` (neu)

**Schicht:** Python-Core (`src/providers/`, `src/app/`). Keine Go-API, kein
Frontend — analog S2a.

## Estimated Scope

- **LoC:** ~165–230 Produktivcode (`base.py`, `thunder_enrichment.py`,
  `models.py`, `dwd.py`, `thunder_routing.py`) + ~250–400 Tests = **~415–630**
- **Files:** 5 geändert, mind. 2 Testdateien neu (DWD-Fetch/Fail-soft-Tests,
  Live-Namenscheck), 1 Testdatei erweitert
  (`test_thunder_enrichment_shared_path.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| DWD ICON-D2 Open-Data (`opendata.dwd.de`) | externer Dienst | Bereits Zugang via `DwdDirectProvider`, keine neuen Credentials |
| `rasterio` (`MemoryFile`) | Bibliothek | Punktwert aus der entpackten GRIB2-Antwort lesen (bereits genutzt in `dwd.py:_read_point_value`) |
| `providers.thunder_routing.thunder_provider_for` | intern | Gewitter-Zuständigkeit, S2a etabliert, S2b trägt zweite Zeile ein |
| `providers.thunder_enrichment.enrich_thunder` | intern | EINER gemeinsamer Anschluss, S2a etabliert — wird für S2b **nur** um die generalisierte Fill-Prüfung und die Signal→Feld-Tabelle erweitert, nicht neu gebaut |
| `providers.base.ThunderSignalProvider` | intern (Protokoll) | bekommt additiv `fetch_thunder_signals_named` |
| Issue #1474 (parallele Session) | Nachbar-Feature | baut `thunder_level_from_signals()`/Schwellenwerte für `lpi` — S2b liefert nur Rohwerte, Feldname vor Implementierung gegen deren Spec abgleichen (s. Known Limitations) |

## Implementation Details

```
GEMEINSAMER WEG BLEIBT GEMEINSAM (PO-Vorgabe seit S2a, "keine
Einzelloesungen") — S2b AENDERT NICHT DEN ANSCHLUSS, sondern erweitert ihn
additiv um zwei Dinge, die S2a bewusst offen gelassen hat:

  1. Protokoll-Erweiterung (base.py): NEUE optionale Methode
        fetch_thunder_signals_named(location, start, end)
          -> dict[str, dict[int, Optional[float]]]
     Rueckgabe: {Signalname: {Stunden-Offset: Wert oder None}}. Additiv
     neben der bestehenden Einzelwert-Methode `fetch_thunder_signals`
     (dict[int, Optional[float]]) -- WARUM ein zweites Protokoll-Element
     statt die bestehende Signatur zu aendern: eine Aenderung der
     bestehenden Signatur braeche S2a/Meteo-France ohne fachlichen Gewinn.
     Analog zum bereits etablierten Muster `fetch_thunder_signals_multi`
     (freiwillige Zusatzmethode, per `getattr`/`callable`-Check genutzt,
     wer sie nicht hat bleibt vollwertig).

  2. Signal->Feld-Tabelle (thunder_enrichment.py, NEU, klein):
        _SIGNAL_ZU_FELD = {
            "lpi": "lightning_potential_lpi_jkg",
            "grau_gsp": "hail_potential_grau_gsp",
        }
     (Schluessel = vorlaeufige Arbeitshypothese, s. Warnhinweis oben und
     AC-6 -- die tatsaechlichen Schluessel muessen exakt den Konstanten
     entsprechen, die `DwdDirectProvider.fetch_thunder_signals_named`
     zurueckgibt.)
     Kennt weiterhin KEINEN Providernamen -- nur ein Signal-Vokabular
     (S2a-Spec-AC-8 bleibt gewahrt: Provider fuellen nur Felder, die
     Anreicherung liest nur Signale).

  3. enrich_thunder() erweitert sich um EINEN Zweig:
        benannt = getattr(provider, "fetch_thunder_signals_named", None)
        if callable(benannt):
            signale_je_feld = benannt(location, von, bis) or {}
            for signalname, feldname in _SIGNAL_ZU_FELD.items():
                fuer dieses Signal genau wie heute: offset -> dp finden,
                None bleibt None, Wert wird auf `feldname` gesetzt
                (per setattr, nicht auf lightning_density_per_km2_3h).
        else: bestehender Weg (Sammelabruf oder Einzelwert) unveraendert,
              schreibt weiterhin auf lightning_density_per_km2_3h.

  4. Fill-Waechter GENERALISIEREN (der heikelste Punkt dieser Scheibe):
     HEUTE (S2a):
        if any(dp.lightning_density_per_km2_3h is not None ...): return
     NEU: gegen ALLE aus der Signal-Tabelle bekannten Felder PLUS das
     bestehende Meteo-France-Feld pruefen -- "irgendein bekanntes Feld
     bereits gesetzt" bleibt die Regel (Fill-only, kein Vollstaendigkeits-
     Anspruch). Ohne diese Verallgemeinerung greift der Waechter fuer
     DWD-Orte NIE (das Feld, das er prueft, wird von DWD nie gefuellt) --
     ein zweiter Aufruf von enrich_thunder auf dieselbe bereits angereicherte
     Reihe wuerde dann unbemerkt einen zweiten DWD-Abruf ausloesen (s. AC-5).

  => S2c (Lueckenfueller) fuegt danach nur noch einen
     Zustaendigkeitstabellen-Eintrag plus ggf. einen weiteren Signal-Tabellen-
     Eintrag hinzu. Anschluss und Protokoll werden nie wieder angefasst.

1. ForecastDataPoint bekommt ZWEI neue Felder (models.py):
     lightning_potential_lpi_jkg: Optional[float] = None
     hail_potential_grau_gsp: Optional[float] = None
   BEWUSST eigene Felder, NICHT mit lightning_density_per_km2_3h
   zusammengelegt (andere Groessen, andere Skalen, s. #1419 Abschnitt 3.1)
   UND bewusst zwei GETRENNTE Felder (Blitzpotenzial != Hagel).
   Feldnamen sind eine benannte Arbeitshypothese dieser Spec (s. Known
   Limitations Punkt 1) -- Abgleich mit #1474 vor Implementierungsbeginn.

2. DwdDirectProvider.fetch_thunder_signals_named(location, start, end)
     -> dict[str, dict[int, Optional[float]]]
   Ein `_fetch_series(param, ...)`-Aufruf je Parameter (bestehendes Muster,
   KEIN Sammelabruf/Bounding-Box noetig -- jede ICON-D2-Datei deckt ohnehin
   ganz Deutschland ab, s. Modul-Docstring `dwd.py`). Eigenes Zeitbudget
   (Muster THUNDER_FETCH_DEADLINE_SECONDS, meteofrance.py:114). Eigener,
   noch zu vermessender Sicherheitsabstand bei der Lauf-Wahl (Muster
   THUNDER_RUN_SAFETY_HOURS, meteofrance.py:207) mit Ruecksfall auf
   aeltere Laeufe bei 404 -- Nullpunkt der Stunden-Offsets bleibt am Lauf
   der Grundvorhersage. Jede Ausnahme -> {}, nie werfen.
   fetch_thunder_signals() (Pflichtteil des Protokolls) bleibt als duenner
   Wrapper bestehen, der EIN Signal (z.B. "lpi") aus dem benannten Ergebnis
   herausgreift -- Muster meteofrance.py:508-540.

   NACHTRAG (RED-Phase-Befund, PO-bestaetigt 2026-08-03): `grau_gsp` ist
   seit Laufbeginn KUMULIERT (empirisch bestaetigt, Zelle 45,94N/7,86O:
   Wert bleibt ab +8h ueber +12/+16/+20/+24h konstant bei 3,3035) -- exakt
   dasselbe Verhalten wie `tot_prec`. Der Rohwert wird daher NICHT direkt
   uebernommen, sondern per Differenzbildung zur Vorstunde in ein
   Stunden-Signal umgerechnet -- Wiederverwendung des bestehenden Musters
   `_precip_series_from_cumulative` (dwd.py:131-144), NICHT neu erfunden.
   `lpi` bleibt unveraendert (Momentanwert, keine Kumulation gemessen).

3. thunder_routing.py: EINE neue Zeile fuer das ICON-D2-Gebiet (DE + Alpen +
   Oesterreich), NACH der bestehenden FR-Zeile:
     _ThunderRegion("DE_ALPEN", 43.17, 58.09, <lon_min>, <lon_max>,
                    "de_direct")
   lat-Bereich aus dem Kontext-Dokument uebernommen; lon-Bereich MUSS vor
   Implementierung gegen die echten ICON-D2-Gittergrenzen (rasterio
   `dataset.bounds` einer echten Antwort) geprueft werden -- nicht raten
   (Arbeitshypothese: ca. -3,9 bis 20,3 Grad Ost, deckt DE+Alpen+AT ab).
   Diese Tabelle ist von `region_routing.py` getrennt (S2a-Entscheidung) --
   dadurch entscheidet fuer Gewitter automatisch diese Zeile, unabhaengig
   davon, dass GeoSphere (`at_direct`) fuer Schnee/Temperatur in Oesterreich
   zustaendig bleibt (AC-10, bestaetigt S2a-AC-12 konkret fuer DWD).

4. Fehlwert-Marker: VOR der ersten produktiven Nutzung empirisch gegen echte
   ICON-D2-GRIB2-Dateien pruefen (Muster: `echotop` liefert -999.0, aber das
   ist NICHT automatisch auch der Marker fuer lpi/grau_gsp -- eigene Pruefung
   noetig, s. AC-2 und Known Limitations Punkt 3).
```

## Expected Behavior

- **Input:** eine Position im ICON-D2-Zuständigkeitsgebiet mit Zeitraum
- **Output:** dieselbe Vorhersage wie heute, zusätzlich mit gefüllten
  Blitzpotenzial-/Hagel-Feldern an deutschen/alpinen/österreichischen Orten
- **Side effects:** zusätzliche HTTP-Abrufe an `opendata.dwd.de` (2 neue
  Parameter × bis zu 24 Zeitschritte je Ort und Lauf — analog zu den 4
  bestehenden Basis-Parametern, s. Known Limitations Punkt 4)

## Acceptance Criteria

- **AC-1 (Wirkungs-Nachweis, Ende-zu-Ende):** Given eine Position am
  Karnischen Höhenweg (46,6 N / 12,9 O, Grenzgebiet AT/IT im
  ICON-D2-Zuständigkeitsgebiet) / When eine Vorhersage über den **regulären**
  Weg abgerufen wird (`OpenMeteoProvider.fetch_forecast`, funktionierende
  Hauptquelle, kein Ausfall) / Then trägt mindestens ein Zeitpunkt sowohl
  einen Blitzpotenzial- als auch einen Hagel-Wert aus DWD, während dieselbe
  Abfrage heute für beide Felder durchgängig leer bleibt.
  - Test: Gegen eine aufgezeichnete ICON-D2-Antwort (`lpi`- und
    `grau_gsp`-Fixture) wird der komplette Weg
    `DwdDirectProvider.fetch_thunder_signals_named` →
    `thunder_routing.thunder_provider_for` → `thunder_enrichment.enrich_thunder`
    → `ForecastDataPoint` durchgespielt und der Wert am Datenpunkt
    nachgewiesen. Gegenprobe: Wird der Aufruf aus dem regulären Rückgabeweg
    von `fetch_forecast` entfernt und nur isoliert gegen die Provider-Methode
    getestet, muss dieser Test — anders als ein reiner Methodentest — rot
    werden. **Warum diese Formulierung Pflicht ist:** Bei S2a waren AC-1 bis
    AC-6 vollständig erfüllt und der Adversary hatte VERIFIED erteilt, obwohl
    die Blitzdichte nie einen Nutzer erreichte — der Anschluss ans
    Produktivsystem fehlte. Für S2b ist das Risiko strukturell kleiner (der
    Anschluss hängt bereits produktiv), trotzdem beweist nur dieses AC die
    Wirkung statt der reinen Fähigkeit.

- **AC-2:** Given DWD liefert für einen Zeitpunkt keinen Wert, ODER liefert
  den (bei Implementierung empirisch verifizierten) Sentinel-Fehlwert-Marker
  / When die Vorhersage gebaut wird / Then bleibt das jeweilige Feld
  **`None`** — nie `0` und nie der rohe Sentinel-Wert.
  - Test: Eine Fixture ohne Wert für eine Stunde erzeugt an diesem
    Zeitpunkt `None`; eine zweite Fixture mit dem verifizierten
    Sentinel-Rohwert erzeugt ebenfalls `None`. Ein Test, der `0` oder den
    rohen Sentinel-Wert erwartet, muss fehlschlagen.

- **AC-3:** Given der Abruf von Blitzpotenzial/Hagel scheitert vollständig
  (Serverfehler, Zeitüberschreitung, Netzfehler) / When eine Vorhersage
  abgerufen wird / Then wird sie **trotzdem vollständig geliefert**, nur ohne
  die beiden neuen Felder — der Fehler kippt die Vorhersage nicht.
  - Test: Ein Abruf, der eine Ausnahme wirft, führt zu einer vollständigen
    Vorhersage mit Temperatur und Wind und leeren Blitzpotenzial-/Hagel-Feldern.
    Gegenprobe: Wird das Werfen im Anreicherungspfad zugelassen, muss der Test
    rot werden.

- **AC-4:** Given die DWD-Gewitterabrufe brauchen ungewöhnlich lange / When
  das eigene Zeitbudget der Anreicherung erschöpft ist / Then bricht **nur die
  Anreicherung** ab, und die Grundvorhersage behält ihr eigenes, unangetastetes
  Budget.
  - Test: Mit künstlich kleingesetztem Anreicherungsbudget gegen einen
    langsamen lokalen Server endet der Aufruf innerhalb der Grenze und liefert
    die Grundvorhersage; die Anzahl der noch erfolgten Abrufe belegt, dass
    nicht auf das große Budget gewartet wurde (Muster:
    `tests/tdd/test_thunder_budget_and_failsoft.py`, Aufrufe zählen statt
    Laufzeit messen).

- **AC-5 (generalisierter Fill-Wächter — der heikelste Punkt dieser Scheibe):**
  Given eine Vorhersagereihe, die von einer vorangegangenen Anreicherung
  bereits Blitzpotenzial und/oder Hagel trägt / When `enrich_thunder` **ein
  zweites Mal** auf dieselbe Reihe aufgerufen wird / Then löst das **keinen**
  erneuten DWD-Abruf aus.
  - Test: `enrich_thunder` wird zweimal nacheinander auf dieselbe bereits
    angereicherte Reihe aufgerufen; die Anzahl der Provider-Abrufe (Spy/Zähler,
    nicht Laufzeit) bleibt bei 1. Gegenprobe: Bleibt der Fill-Wächter hart auf
    `lightning_density_per_km2_3h` fixiert (wie in S2a), muss dieser Test rot
    werden — dieses Feld wird von DWD nie gefüllt, der Wächter griffe für
    DWD-Orte dann nie.

- **AC-6 (Namensfallen-AC, PFLICHT, Live-Schicht):** Given die im
  Produktivcode hinterlegten DWD-Parameternamen für Blitzpotenzial und Hagel
  (als Konstanten, nicht im Test wiederholt) / When gegen das echte
  DWD-Open-Data-Verzeichnis (`opendata.dwd.de`) geprüft wird / Then existiert
  der jeweilige Parameter-Ordner bzw. die erwartete Datei tatsächlich — kein
  lautloser 404.
  - Test: Live-Test (Marker `live`, läuft nicht im Commit-Gate, Vorbild
    `tests/tdd/test_thunder_coverage_name_live.py`), liest die Parameternamen
    aus der Konstante im Produktivcode (`dwd.py`) und prüft per HTTP-Anfrage
    gegen den aktuellsten veröffentlichten ICON-D2-Lauf, dass die Datei
    existiert (200, nicht 404). **Warum Pflicht:** Exakt dieser Fehler
    (`LITOTA3` existierte beim Météo-France-Dienst nicht) ließ bei S2a jeden
    Abruf lautlos in 404 laufen, während 24 aufgezeichnete Tests grün blieben.

- **AC-7:** Given der Standard-`_latest_run` könnte einen noch nicht
  veröffentlichten ICON-D2-Lauf berechnen / When Blitzpotenzial/Hagel
  abgerufen werden und der gewählte Lauf mit 404 antwortet / Then fällt der
  Abruf auf einen älteren Lauf zurück (mindestens einmal), während der
  Nullpunkt der Stunden-Offsets am Lauf der Grundvorhersage bleibt.
  - Test: Gegen einen echten lokalen HTTP-Server (Muster
    `tests/tdd/test_thunder_run_fallback.py`), der auf den jüngsten Lauf mit
    404 antwortet, wird nachgewiesen, dass ein älterer Lauf erfolgreich
    abgefragt wird und die zurückgegebenen Stunden-Offsets weiterhin zum
    3-stündigen ICON-D2-Grundraster passen. Konkreter Sicherheitsabstand
    (Anzahl Stunden) wird erst bei der Implementierung gegen echte
    ICON-D2-Verfügbarkeit gemessen, nicht geraten.

- **AC-8 (Abgrenzung, keine Stufenbildung):** Given Blitzpotenzial und Hagel
  sind für einen Datenpunkt gefüllt / When Ausgaben gerendert werden (SMS,
  Trip-Briefing, `thunder_level`-Berechnung) / Then bleiben diese Ausgaben
  **unverändert** gegenüber dem Stand ohne die neuen Felder — keine eigene
  Einstufungs- oder Schwellenlogik entsteht in dieser Scheibe.
  - Test: Ein Regressionstest rendert dieselbe Vorhersage einmal mit und
    einmal ohne gesetzte `lightning_potential_lpi_jkg`/`hail_potential_grau_gsp`
    und vergleicht `thunder_level` sowie den gerenderten SMS-/Briefing-Text —
    beide müssen identisch sein. Gegenprobe: Fließt eines der neuen Felder in
    eine bestehende Einstufungsfunktion ein, muss dieser Test rot werden.
    (#1474, parallele Session, baut die Schwellenlogik separat.)

- **AC-9 (additive Protokoll-Erweiterung, PO-Vorgabe "keine
  Einzellösungen" bleibt gewahrt):** Given ein **dritter**, hypothetischer
  Wetterdienst, der `fetch_thunder_signals_named` mit einem eigenen,
  bislang unbekannten Signalnamen erfüllt / When er als zuständige
  Gewitterquelle für sein Gebiet eingetragen wird und sein Signal in der
  Lookup-Tabelle ergänzt wird / Then wird er wirksam, **ohne dass der
  Kern-Dispatch in `enrich_thunder` (Fill-Wächter, Fehlerbehandlung,
  Zeitbudget) angefasst werden muss** — nur die kleine Signal→Feld-Tabelle
  wächst.
  - Test: Ein einfacher Doppelgänger-Provider (Test-Fixture) mit einem
    frei erfundenen Signalnamen wird eingetragen und liefert seinen Wert bis
    zum Datenpunkt, nachdem nur die Lookup-Tabelle um eine Zeile ergänzt
    wurde. Gegenprobe: Enthält der Dispatch-Code eine Abfrage auf einen
    konkreten Providernamen (`de_direct`, `DwdDirectProvider`, `lpi`), muss
    dieser Test rot werden.

- **AC-10 (Zuständigkeit unabhängig von der Grundvorhersage, bestätigt
  S2a-AC-12 konkret):** Given ein Ort in Österreich, dessen Grundvorhersage
  (Temperatur/Schnee) von GeoSphere (`at_direct`) kommt / When die
  Gewitter-Zuständigkeit bestimmt wird / Then liefert
  `thunder_routing.thunder_provider_for` **`de_direct`**, nicht `None` und
  nicht `at_direct`.
  - Test: Für den Karnischen Höhenweg wird nachgewiesen, dass
    `thunder_provider_for` und `region_routing.direct_provider_for`
    unterschiedliche Provider zurückgeben und dass tatsächlich der
    Gewitter-Provider für den Gewitterabruf verwendet wird.

## Known Limitations

1. **Feldnamen sind eine Arbeitshypothese, kein bestätigter Vertrag.**
   `lightning_potential_lpi_jkg` und `hail_potential_grau_gsp` müssen vor
   Implementierungsbeginn gegen die parallel laufende Spec zu Issue #1474
   (Gewitter-Stufenbildung, andere Session, baut `thunder_level_from_signals()`
   bereits mit einer Signal-Tabelle) abgeglichen werden, sobald diese
   verfügbar ist — sonst entsteht eine Namenskollision zwischen zwei
   Feldern, die dasselbe meinen, oder zwei Namen für dasselbe Feld.
2. **Keine Stufenbildung in dieser Scheibe.** S2b liefert ausschließlich
   Rohwerte ins Datenmodell (AC-8). Schwellenwerte für `lpi`
   (>1 J/kg leicht, ≥30 mittel, ≥50 hoch — nur die untere Grenze gilt laut
   #1474 als belastbar) werden **nicht** hier gebaut, auch wenn sie bereits
   bekannt sind. Das ist dieselbe Grenze wie im ursprünglichen Issue
   ("keine Stufenbildung — das ist S3"), jetzt zusätzlich durch die
   parallele Session bestätigt, nicht verschoben.
3. **Fehlwert-Marker für `lpi`/`lpi_max`/`grau_gsp` sind zum Zeitpunkt
   dieser Spec-Freigabe noch nicht empirisch verifiziert.** Das ist eine
   **Implementierungsvoraussetzung** (AC-2 verlangt die Prüfung gegen echte
   GRIB2-Dateien vor dem ersten produktiven Durchreichen), kein
   Show-Stopper für die Spec-Freigabe selbst — `echotop=-999.0` ist ein
   Analogiemuster, kein Beleg für diese beiden Größen.
4. **Abrufkosten.** DWD liefert einen Wert je Parameter und Zeitschritt;
   heute entstehen ~96 Abrufe je Ort und Lauf (4 Basis-Parameter × 24
   Zeitschritte), diese Scheibe fügt bis zu 48 hinzu (2 neue Parameter × 24
   Zeitschritte). Anders als bei Météo-France (S2a) ist **keine**
   Sammelabruf-/Bündelungslogik nötig, weil jede ICON-D2-Datei ohnehin ganz
   Deutschland abdeckt — ein Bounding-Box-Mechanismus ergäbe hier keinen
   fachlichen Gewinn. Die bekannte Mehrfach-Download-Ineffizienz bei
   mehreren Orten (identische Datei wird pro Ort erneut geladen) ist
   vorbestehendes Verhalten der Grundvorhersage, nicht neu durch S2b
   eingeführt.
5. **Exakter lon-Bereich der neuen `thunder_routing`-Zeile ist eine
   Arbeitshypothese** (ca. -3,9 bis 20,3 Grad Ost) und muss vor
   Implementierung gegen die echten ICON-D2-Gitterbounds
   (`rasterio dataset.bounds` einer echten Antwort) geprüft werden — nicht
   geraten, analog zur Regel für Fehlwert-Marker und Abrufnamen.
7. **Erste Hagel-Stunde bleibt leer, wenn ihr Anker fehlt (Adversary-Fund
   F001, behoben im Fix-Loop 1, 2026-08-03).** `grau_gsp` ist kumuliert;
   die Differenzbildung braucht einen echten Vorwert unmittelbar vor dem
   ersten angefragten Zeitschritt (Zusatzabruf), statt `0.0` anzunehmen —
   sonst wäre die erste Stunde systematisch zu hoch (volle
   Kumulation seit Laufbeginn statt Zuwachs dieser Stunde). Ist dieser
   Anker nicht abrufbar (Ort außerhalb des Modellgebiets, 404 auf genau
   diesem Zeitschritt), bleibt die erste Stunde bewusst `None` statt einer
   geratenen Differenz — **wichtig für #1474:** `None` heißt hier „Stand
   davor unbekannt", NICHT „kein Hagel". Kostet einen zusätzlichen
   HTTP-Abruf je kumuliertem Signal (heute: 1, nur `grau_gsp`) —
   Egress-Aufschlag ist im Rahmen des ohnehin geplanten Budgets.
8. **Noch nichts zusätzlich für den Nutzer sichtbar.** Die Rohwerte liegen
   im Datenmodell; Stufenbildung (S3/#1474) und eigene Ausgaben (S5) folgen
   in Folgescheiben. Bewusst: Erst wenn die Rohsignale verlässlich anliegen,
   kann eine Einstufung darauf aufsetzen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Referenz auf **ADR-0041**
  (Zuständigkeit einer Warn-Quelle nach Art des Endpunkts).
- **Rationale:** Die S2a-Spec hatte für S2b noch ein eigenes ADR "im Muster
  von ADR-0041" vorgesehen. Nach Abwägung ist das nicht gerechtfertigt: Die
  eigentliche Architektur-Entscheidung — eine ZWEITE, größenabhängige
  Zuständigkeitstabelle getrennt von `region_routing.py` — wurde bereits
  **mit S2a** getroffen und dokumentiert (`thunder_routing.py`-Modul-Docstring
  referenziert ADR-0041 bereits als verwandtes Muster). S2b **wendet dieses
  Muster nur an** (Muster C: Rechteck-Zuständigkeit mit klarer
  Rangfolge, kein neuer Entscheidungstyp) und fügt eine Tabellenzeile hinzu —
  strukturell identisch zu dem, was S2a für Frankreich bereits getan hat.
  Die zweite architekturrelevante Änderung dieser Scheibe — die additive
  Protokoll-Erweiterung `fetch_thunder_signals_named` — folgt exakt dem
  bereits etablierten und in Produktion bewährten Erweiterungsmuster
  `fetch_thunder_signals_multi` (optional, `getattr`-Check, kein Bruch
  bestehender Signaturen) und ist damit ebenfalls keine neue
  Entscheidungsfläche, sondern eine Anwendung einer bereits getroffenen.
  Ein neues ADR würde eine bereits dokumentierte Entscheidung wiederholen,
  nicht eine neue treffen.

## Changelog

- 2026-08-03: Initial spec created (Issue #1457 S2b, Konzept #1419,
  Vorbild S2a `feat_1457_s2a_blitzdichte_meteofrance.md`)
- 2026-08-03: RED-Phase-Befund nachgetragen, PO-bestätigt: `grau_gsp` ist
  kumuliert (wie `tot_prec`), wird per Differenzbildung zur Vorstunde
  umgerechnet (Muster `_precip_series_from_cumulative`). Fehlwert-Marker
  gemessen: `9999.0`, nicht `-999.0` (Analogieschluss zu `echotop`
  widerlegt). Gitter-Bounds gemessen: -3,95 bis 20,35 Grad Ost, 43,17 bis
  58,09 Grad Nord. Keine größere Lauf-Sicherheitsspanne nötig (Läufe
  binnen ~1,5h vollständig verfügbar), Rückfall auf ältere Läufe bleibt
  als Absicherung (AC-7).
