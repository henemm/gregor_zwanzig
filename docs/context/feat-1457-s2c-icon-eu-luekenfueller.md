# Context: #1457 S2c — DWD ICON-EU als Gewitter-Lückenfüller

## Request Summary

Dritte und letzte Scheibe von #1457 (Konzept #1419, Schritt S2): DWD ICON-EU (grobmaschig, 6,5 km,
nur Blitzpotenzial `lpi_con_max`, kein Hagel) wird als Gewitterquelle für alle Gebiete eingebaut, die
weder von Météo-France (S2a, FR/Korsika) noch von ICON-D2 (S2b, DE/Alpen/AT) abgedeckt sind — Rest-Europa.
Schließt die Landkarte der Gewittersignal-Beschaffung; danach ist #1457 vollständig.

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/thunder_routing.py` | Region-Tabelle `_REGIONS`, first-match-wins. Docstring nennt S2c bereits explizit als "Lückenfüller für den Rest". Braucht eine dritte Zeile — als letzte, sonst verschluckt sie FR/DE_ALPEN (Reihenfolge ist tragend, s. Kommentar zu DE_ALPEN vs. FR). |
| `src/providers/dwd.py` | `DwdDirectProvider`, komplett hart auf ICON-D2 verdrahtet: `BASE_URL` (Z.58), `PARAMS`/`THUNDER_PARAMS` (Z.75/86) als Modul-Konstanten, `_build_url` (Z.183-192) interpoliert `_germany_` fest in den Dateinamen. Kein Modell-Parameter irgendwo — die ganze Datei ist EINE Konfiguration. |
| `src/providers/thunder_enrichment.py` | Gemeinsamer Anreicherungsweg. `_SIGNAL_ZU_FELD` (Z.36-39) kennt nur `{"lpi": ..., "grau_gsp": ...}`. Dispatch über `providers.base.get_provider(quelle)` — **keine eigene Registry hier**, S2c braucht hier nur eine Änderung, falls ICON-EU einen neuen Signal-Key statt `"lpi"` verwendet. |
| `src/providers/base.py` | `ThunderSignalProvider`-Protokoll (Z.70-126, nur `fetch_thunder_signals` Pflicht, `_named`/`_multi` optional/duck-typed). `_load_providers()` (Z.221-268) — die eigentliche Provider-Name→Instanz-Registry. Braucht einen neuen `register_provider("eu_direct", ...)`-Block. |
| `src/app/models.py` | Bestehende Gewitterfelder: `lightning_density_per_km2_3h` (S2a), `lightning_potential_lpi_jkg` + `hail_potential_grau_gsp` (S2b), `thunder_probability_pct` (vorbereitet, #1474 S6). Kein eigenes ICON-EU-Feld — `lightning_potential_lpi_jkg` ist fachlich dieselbe Energiegröße (J/kg), nur andere Maschenweite. |
| `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md` | Spec-Format-Vorbild (AC-1..AC-N, Known Limitations, ADR-Abschnitt). Known Limitation 3 verweist bereits auf S2c. |
| `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md` | Zweites Vorbild, plant S2c explizit (Z.129-131: "S2c fügt nur noch einen Zuständigkeitstabellen-Eintrag plus ggf. einen Signal-Tabellen-Eintrag hinzu. Anschluss und Protokoll werden nie wieder angefasst."). Known Limitations 1/3/5 sind direkt als Checkliste für S2c wiederverwendbar. |
| `docs/reference/api_contract.md` (Z.191, Z.197) | Zwei bestehende Gewitter-Unterabschnitte (S2a/S2b) — S2c braucht einen dritten oder Erweiterung des DWD-Abschnitts. |
| `docs/reference/decision_matrix.md` (Z.20, 36, 59, 98) | Nennt S2c bereits an mehreren Stellen explizit als offenen Nachtrag; Warnung Z.36 listet `lpi_con_max` ausdrücklich als **unverifizierten** Kurznamen, der vor Implementierung gegen den echten DWD-Verzeichnislisting geprüft werden muss. |
| `tests/tdd/test_thunder_enrichment_shared_path.py` | Verbotene-Begriffe-Test in `thunder_enrichment.py` enthält bereits `"de_direct"` UND `"lpi_con_max"` als verbotene Strings — S2c-Implementierung darf beide nicht in die gemeinsame Datei leaken. |
| `tests/tdd/test_dwd_thunder_signal_fetch.py`, `test_dwd_thunder_parameter_names_live.py`, `test_thunder_named_signals_enrichment.py`, `test_thunder_run_fallback.py` | Testmuster von S2b, direkt als Vorlage für S2c-Tests nutzbar (Named-Signals, Live-Namenscheck, Lauf-Fallback, Fehlwert-Filter). |

## Existing Patterns

- **Dreischichtiges Muster (zweimal etabliert):** (1) Protokoll `ThunderSignalProvider` implementieren, (2) eine Zeile in `thunder_routing._REGIONS`, (3) Registrierung in `base._load_providers()`. Der gemeinsame Anreicherungsweg (`thunder_enrichment.py`) bleibt unverändert, solange der Signal-Key (`"lpi"`) wiederverwendet wird.
- **Eigenes Zeitbudget je Provider:** `THUNDER_FETCH_DEADLINE_SECONDS` als Modul-Konstante, aus Abrufzahl × gemessener Latenz hergeleitet (nicht geschätzt) — DWD 90s (bis zu 48 Abrufe), Météo-France 45s (24 Abrufe). ICON-EU hätte nur `lpi_con_max` (kein Hagel) ⇒ voraussichtlich ~24 Abrufe, also eher Richtung 45-90s, empirisch zu bestimmen.
- **Fehlwert-Marker empirisch verifizieren, nie annehmen:** ICON-D2 nutzte `9999.0` (nicht `-999.0`, wie zunächst vom `echotop`-Analogieschluss vermutet — S2b hat das live widerlegt). Für ICON-EU gilt dieselbe Pflicht: eigener Messwert gegen echte GRIB2-Datei, keine Übernahme von ICON-D2.
- **Abrufnamen gegen `GetCapabilities`/Verzeichnislisting prüfen, bevor implementiert wird** — Lehre aus S2a (`LITOTA3` existierte nicht, lief lautlos in 404). `decision_matrix.md` markiert `lpi_con_max` bereits als ungeprüft.
- **Live-Test als Namensfalle-Wächter:** `test_dwd_thunder_parameter_names_live.py` (Marker `live`) prüft den im Produktivcode stehenden Parameternamen gegen den echten DWD-Dienst. S2c braucht ein Pendant für ICON-EU.

## Dependencies

- **Upstream:** `providers.base.get_provider()`, `providers.thunder_routing.thunder_provider_for()`, gemeinsamer Weg `providers.thunder_enrichment.enrich_thunder()` (aufgerufen aus `OpenMeteoProvider.fetch_forecast`, regulärer Pfad — NICHT nur Totalausfall-Fallback, Lehre aus S2a AC-7/AC-8).
- **Downstream:** `src/output/metric_format.py::thunder_level_from_signals()` liest aktuell NUR `(wettercode_level, lightning_density, cape_jkg)` — `lightning_potential_lpi_jkg` fließt bislang in KEINE Stufenbildung ein (auch DWD S2b nicht). S2c ändert daran nichts; Stufenbildung bleibt #1474/Folgescheibe.

## Existing Specs

- `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md` — Format-Vorbild
- `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md` — Format-Vorbild + explizite S2c-Vorschau
- `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` — Stufenbildung (S3), `lpi`-Schwellen dort nur dokumentiert, NICHT verdrahtet; S2c bleibt außerhalb dieser Verdrahtung

## Risks & Considerations

1. **Reihenfolge in `_REGIONS` ist tragend:** Die neue Catch-all-Zeile MUSS als letzte stehen, sonst verschluckt sie FR/DE_ALPEN (bereits bekanntes Muster aus dem Kommentar zu DE_ALPEN vs. FR).
2. **`dwd.py` ist komplett hart auf ICON-D2 verdrahtet** (Base-URL, Dateiname-Template, Param-Listen als freie Modulkonstanten, keine Instanz-Parametrisierung). Ein zweiter Provider für ICON-EU braucht entweder eine neue Geschwister-Klasse/-Datei (geringeres Risiko, kein Anfassen des gehärteten S2b-Codes) oder eine Parametrisierung der bestehenden Klasse (größerer Umbau). Empfehlung aus der Recherche: Geschwister-Ansatz, analog wie `fr_direct`/`de_direct` bereits zwei unabhängige Klassen in zwei Dateien sind.
3. **Namenskollision vermeiden:** `providers.openmeteo` nutzt bereits den String `"icon_eu"` als Open-Meteo-Modell-ID (andere Namensebene als die Provider-Registry-Namen `de_direct`/`fr_direct`/`at_direct`, aber verwirrend ähnlich) — Provider-Name eher `eu_direct` statt `icon_eu`.
4. **`lpi_con_max` ist bislang nur ein Konzept-Kurzname, kein verifizierter Abrufname** — vor Implementierung gegen echtes DWD-Verzeichnislisting/`GetCapabilities`-Äquivalent prüfen (S2a-Lehre, in `decision_matrix.md` bereits als offene Pflicht vermerkt).
5. **Fehlwert-Marker für ICON-EU unbekannt** — nicht von ICON-D2 (`9999.0`) übernehmen, eigens messen.
6. **Feldwahl:** `lightning_potential_lpi_jkg` wiederverwenden (fachlich dieselbe Größe) vs. eigenes Feld für ICON-EU — braucht PO-Entscheidung, da es die Herkunfts-Transparenz (grobe vs. feine Maschenweite) betrifft. Wiederverwendung hält `thunder_enrichment.py` unverändert; eigenes Feld macht die Datenqualität sichtbar, braucht aber eine neue `_SIGNAL_ZU_FELD`-Zeile.
7. **Kein Hagel-Signal bei ICON-EU** — `hail_potential_grau_gsp` bleibt für Rest-Europa `None`, das ist beabsichtigt (Konzepttabelle in #1419 nennt für "Übriges Europa" nur Blitzpotenzial).
8. **Downstream unverändert:** Stufenbildung (`thunder_level_from_signals`) liest `lightning_potential_lpi_jkg` bislang nicht — S2c liefert nur Rohwerte, keine Nutzer-sichtbare Änderung (konsistent mit S2a/S2b-Abgrenzung).
