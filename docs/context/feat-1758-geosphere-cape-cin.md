# Context: feat-1758-geosphere-cape-cin

Issue: #1758 — "Gewitter: GeoSphere liefert cape/cin, wird aber nie abgefragt"
Eltern-Epic: #1419 · Track: Standard · erstellt 2026-08-18

## Request Summary

Der GeoSphere-Provider (AROME, 2,5 km) fragt heute weder `cape` noch `cin` ab,
obwohl der Dienst beides führt. Die Werte sollen abgerufen und am Datenpunkt
geführt werden, damit für Österreich ein zweites, unabhängiges Konvektionssignal
entsteht.

## Live-Messung vor der Spec (2026-08-18)

Vorgehen nach der Lehre aus #1457 S2a (erfundener Parametername lief lautlos in
404 bei 24 grünen Tests): Abrufnamen und Fehlwerte VOR der Spec real messen.

| Prüfung | Ergebnis |
|---|---|
| `GET /nwp-v1-1h-2500m/metadata` | 19 Parameter, darunter `cape` (unit `m2 s-2`) und `cin` (unit `J kg-1`) |
| Punkt 46.66/12.74 (Karnischer Höhenweg), 56 Stunden | `cape` 0,5 … 380,8 · Nachmittagsanstieg vorhanden · `cin` 0,0 bis −0,1 |
| Punkt ausserhalb des Modellgitters (42.22/9.07, Korsika) | HTTP 400 `"Requested point ... is outside of dataset bounds!"` |
| Unbekannter Parametername im selben Abruf | HTTP 400 `"Parameters {'gibtesnicht'} do not exist or access is denied"` — **der GESAMTE Abruf scheitert** |

Rohdaten der Messung: Session-Scratchpad `geosphere_meta.json`, `geo_khw.json`.

**Einheiten-Falle:** `m2 s-2` und `J kg-1` sind dimensionsgleich (1 J/kg = 1 m²/s²).
Die Zahlen sind identisch, es darf NICHT umgerechnet werden. Ohne expliziten
Vermerk rechnet früher oder später jemand um.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/providers/geosphere.py:75` | `NWP_PARAMS` — 11 Parameter, ohne `cape`/`cin` |
| `src/providers/geosphere.py:270-278` | `_request` — `raise_for_status()`, 4xx propagiert nach oben |
| `src/providers/geosphere.py:299-300` | `fetch_nwp_forecast` — EIN Abruf, ungekapselt |
| `src/providers/geosphere.py:311-326` | `fetch_snowgrid` — **hausinternes Best-effort-Vorbild**: eigener Abruf in `try/except httpx.HTTPStatusError` → `(None, None)` |
| `src/providers/geosphere.py:490-581` | `_parse_nwp_response` — Mapping von Hand, Feld für Feld, `params.get(name, {}).get("data", [])` + safe indexing |
| `src/providers/geosphere.py:498-505` | `ForecastMeta(provider=GEOSPHERE, model="AROME", grid_res_km=2.5)` |
| `src/app/models.py:113,172-178` | Datenpunkt-Felder; `cape_jkg` (Open-Meteo), `convective_inhibition_jkg`/`cape_ml_jkg` (DWD #1531) |
| `src/app/model_registry.py:38-63` | `normalize_model_id` — Alias-Tabelle, case-insensitive |
| `src/providers/region_routing.py:34` | `_RegionBounds("AT", …, "at_direct")` — GeoSphere als AT-Fallback |
| `src/providers/thunder_routing.py` | Gewitter-Zuständigkeit; **kein** GeoSphere-Eintrag |
| `src/providers/thunder_enrichment.py:258` | `get_provider(quelle_name)` — hier würde ein eingetragener Dienst befragt |
| `src/providers/base.py` | optionales Protokoll `ThunderSignalProvider` |
| `src/app/egress_guard.py:35` | `dataset.api.hub.geosphere.at` = `TEST_ACCESS` (Staging/Test dürfen real abrufen) |

## Existing Patterns (Präzedenz #1531 / #1457 S2b)

- **Je Quelle ein eigenes Feld.** `models.py:163-171` wörtlich: "`cape_ml` bekommt
  bewusst KEIN gemeinsames Feld mit `cape_jkg` — unterschiedliche Quellen, nicht
  mehr zuordenbar." Skalen verschiedener Modelle sind nicht vergleichbar.
- **Nur Rohwerte durchreichen, keine Einstufung.** Spec
  `docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md`, Abschnitt
  "Scope-Abgrenzung"; AC-9 verlangt Ausgabe-Invarianz ("keine neue Spalte, kein
  neues Token, keine geänderte Gewitterstufe").
- **Zusatzsignale sind Best effort und dürfen die Grundvorhersage nicht gefährden.**
  `dwd.py:120` — eigenes Zeitbudget, Kommentar: "darf das Budget der
  Grundvorhersage weder teilen noch anknabbern"; Gewitterblock in `try/except`,
  Eskalation nur bei Totalausfall der Quelle (`dwd.py:507-510`).
- **Sentinel je Parameter, nicht global.** `CIN_ML_LOWER_SENTINEL = -999.9`
  (`dwd.py:207`), Prüfung ausdrücklich nur für `cin_ml` (`dwd.py:241-245`);
  ICON-EU importiert die Konstante statt sie zu duplizieren (`dwd_eu.py:66-70`).
- **Leer bleibt leer, nie 0.** `thunder_enrichment.py:339-341`.
- **Serialisierung ist generisch.** `weather_snapshot.py:399-434` iteriert
  `vars(p)`; `api/routers/forecast.py:63` nutzt `asdict`. Ein neues
  `Optional[float]`-Feld braucht dort KEINE Pflege. Einzige manuelle Liste ist
  `_HOURLY_ENUM_FIELDS` (`weather_snapshot.py:44`) — betrifft nur Enum-Felder.

## Mitpflege-Kette für ein neues Rohwert-Feld

Aus der Sondierung an `cape_ml_jkg` / `supercell_index_sdi2_1s` (gesamtes Repo):

- Produktivcode ausserhalb Provider + `models.py`: **eine** Stelle —
  `thunder_enrichment.py:36-50` (`_SIGNAL_ZU_FELD`). Betrifft nur den
  DWD-Anreicherungspfad; GeoSphere setzt seine Felder direkt beim Datenpunkt-Bau
  und braucht dort keinen Eintrag.
- Doku: `docs/reference/api_contract.md:295-315`, `docs/reference/decision_matrix.md:26-27`.
- **Go und Frontend: null Treffer** — die #1531-Felder existieren dort nicht.
  Schicht dieser Arbeit ist ausschliesslich der Python-Core.

## Risks & Considerations

1. **🔴 Alles-oder-nichts-Abruf.** Ein unbekannter Parametername lässt den
   gesamten GeoSphere-NWP-Abruf mit HTTP 400 scheitern (live belegt). Nimmt man
   `cape`/`cin` in `NWP_PARAMS` auf, hängt die AT-Grundvorhersage
   (Temperatur/Wind/Schnee) daran, dass GeoSphere diese Namen nie ändert.
   Gegenmittel: zweiter, gekapselter Abruf nach dem Vorbild `fetch_snowgrid`.
2. **🔴 Modellname-Kollision.** `geosphere.py:501` setzt `model="AROME"`.
   `normalize_model_id` ist case-insensitive und bildet `"arome"` auf
   `"meteofrance_arome"` ab (`model_registry.py:43`) — das österreichische AROME
   von GeoSphere würde als Météo-France-AROME identifiziert und zöge dessen
   CAPE-Eichleiter (300/380/310 J/kg). Heute **latent**, weil GeoSphere-Reihen
   `enrich_thunder` nie erreichen. Wer GeoSphere-CAPE in `cape_jkg` schriebe,
   aktivierte die falsche Eichung sofort. Fehlertyp identisch zu #1678.
3. **🔴 Nutzen-Frage: der Pfad läuft im Normalbetrieb nicht.** Alle
   Produktiv-Aufrufer nutzen `get_provider("openmeteo")`; GeoSphere wird
   ausschliesslich über `openmeteo.py:1077` im Cross-Provider-Fallback bei
   Open-Meteo-**Totalausfall** gezogen. Werte, die nur in
   `_parse_nwp_response` entstehen, entstehen also fast nie — die Messreihe, die
   das Ticket begründen soll, käme nicht zustande. Siehe Analyse unten.
4. **Keine Eichung herstellbar.** GeoSphere archiviert AROME nicht rückwirkend
   (Issue-Text, `GET /v1/datasets`). Die CAPE-Leitern in `model_registry.py`
   stammen aus einer historischen Reihe (Open-Meteo Historical Forecast API,
   Saison 2025). Für GeoSphere ist eine Schwelle heute nicht ableitbar —
   Projektprinzip: "keine Aussage" statt geratener Schwelle.
5. **CIN-Vorzeichen.** GeoSphere liefert 0,0 bis −0,1 (negativ). Ob GeoSphere
   einen Sentinel analog `-999.9` verwendet, ist an einem Punkt über 56 Stunden
   nicht entscheidbar — in der TDD-Phase an mehreren Punkten prüfen.

## Existing Specs

- `docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md` — direktes Vorbild
  (Zuschnitt, Testart, AC-9 Ausgabe-Invarianz).
- Eine GeoSphere-Provider-Spec existiert **nicht**.

## Nächster Schritt

Weiche zum Zuschnitt (siehe Risiko 3) dem PO vorlegen, dann `/30-write-spec`.

---

# Analyse (Phase 2) — PO-Entscheid "voll wirksam" vom 2026-08-18

Der PO hat entschieden: GeoSphere-CAPE/CIN sollen **im Normalbetrieb** entstehen,
nicht nur im Open-Meteo-Totalausfall. Damit ist die Gewitter-Zustaendigkeit
Teil der Arbeit.

## Wie ein Dienst heute wirksam wird

`docs/reference/decision_matrix.md:170-176` und `providers/base.py:72-112`
beschreiben den vorgesehenen Weg woertlich: "Ein neuer Dienst wird wirksam,
indem er das Protokoll erfuellt und eine Zeile in `thunder_routing.py` bekommt;
die Anreicherungsstelle wird dabei nie angefasst."

Zwei Bausteine:

1. **Protokoll `ThunderSignalProvider`** (`providers/base.py:72`), optional.
   Drei Ausbaustufen, in dieser Vorrangfolge geprueft
   (`thunder_enrichment.py:_hole_eintraege`):
   `fetch_thunder_signals_named` (mehrere BENANNTE Signale) >
   `fetch_thunder_signals_multi` (mehrere Orte) > `fetch_thunder_signals`
   (ein Einzelwert). GeoSphere liefert zwei Groessen ⇒ **benannter Weg**.
2. **Zuordnung Signalname → Modellfeld**: `_SIGNAL_ZU_FELD`
   (`thunder_enrichment.py:36-50`), eine Zeile je Groesse.

## Das eigentliche Hindernis: die Tabelle kennt nur EINE Quelle je Gebiet

`thunder_routing._REGIONS` ist **first-match-wins** und liefert genau einen
Providernamen (`thunder_provider_for`). Fuer Oesterreich trifft heute
`DE_ALPEN → de_direct` (DWD, liefert Blitzpotenzial). Traegt man GeoSphere
dort ein, **verdraengt** es den DWD — eine Verschlechterung, und das Issue
verlangt ausdruecklich ein "ZUSAETZLICHES, kein ersetzendes" Signal.

Zweites, subtileres Hindernis — der **Fill-only-Waechter** in
`enrich_thunder` (`thunder_enrichment.py:222-231`):

```python
felder = _bekannte_felder()
if any(getattr(dp, feld, None) is not None
       for dp in reihe.data for feld in felder):
    return
```

Er prueft ueber ALLE bekannten Signalfelder global. Bei zwei Quellen je Gebiet
kaeme die zweite Quelle **nie** zum Zug, sobald die erste irgendein Feld
gefuellt hat. Der Waechter muss je Quelle (bzw. je Feldgruppe einer Quelle)
gefuehrt werden. Das ist die eigentliche Architekturarbeit — nicht der Abruf.

## ADR-Lage

- **ADR-0025** ("Eine Gewitter-Quelle fuer alle Briefing-Kanaele") betrifft die
  **Kanal**-Ebene: alle Kanaele lesen dieselbe Rohgroesse `dp.thunder_level`.
  Mehrere Beschaffungs-Quellen widersprechen dem NICHT, solange am Ende
  weiterhin genau ein `dp.thunder_level` steht. **Invariante fuer die Spec:**
  GeoSphere-CAPE darf `thunder_level` auf keinem Weg beeinflussen.
- **ADR-0047** (Vertretung bei echtem Dienstausfall) ist ein anderer
  Mechanismus (`_VERTRETUNG`) und bleibt unberuehrt.
- ⇒ **Neues ADR noetig:** "Mehrere Gewitter-Signalquellen je Gebiet (additiv)".
  Kein "Abgeloest durch" — es erweitert, ohne zu widersprechen.

## Vorgeschlagener Umsetzungsschnitt (zwei Scheiben, beide in diesem Auftrag)

Ziel bleibt "voll wirksam". Der Schnitt dient der Sicherheit, nicht der
Scope-Verkleinerung — Scheibe B folgt unmittelbar auf A.

| Scheibe | Inhalt | Wirkung |
|---|---|---|
| **A — Beschaffung** | Zweiter, gekapselter GeoSphere-Abruf fuer `cape`/`cin` (Vorbild `fetch_snowgrid`); zwei eigene Datenpunkt-Felder; `fetch_thunder_signals_named` auf dem GeoSphere-Provider; zwei Zeilen in `_SIGNAL_ZU_FELD`. **Kein** Eintrag in `thunder_routing`. | Noch keine — vollstaendig testbar, null Risiko fuer den Live-Pfad |
| **B — Wirksamkeit** | `thunder_routing` traegt mehrere Quellen je Gebiet; Fill-only-Waechter je Quelle; GeoSphere fuer AT zusaetzlich zum DWD eingetragen; ADR. | GeoSphere-CAPE/CIN entstehen im Normalbetrieb |

## Invarianten (gelten in beiden Scheiben)

1. **Die Grundvorhersage darf nie kippen.** Faellt der cape/cin-Abruf aus,
   bleiben die zwei Felder leer; Temperatur/Wind/Schnee kommen unveraendert.
   Live belegt: ein unbekannter Parametername killt den GESAMTEN Abruf ⇒
   getrennter Request ist Pflicht, nicht Geschmack.
2. **Keine Umrechnung.** `m2 s-2` == `J kg-1`, Zahlen unveraendert uebernehmen.
3. **Eigene Felder, kein Mitbenutzen von `cape_jkg`.** Sonst zieht
   `effective_cape_model_id` wegen `model="AROME"` die
   **Meteo-France**-Eichleiter (`model_registry.py:43`) — Fehlertyp #1678.
4. **Keine Einstufung, keine Fusion, keine Ausgabeaenderung.** Ausgabe-Invarianz
   wie #1531 AC-9: keine neue Spalte, kein neues Token, keine geaenderte
   Gewitterstufe in E-Mail/SMS/Telegram/Premium-SMS/Ortsvergleich.
5. **Leer bleibt leer, nie 0.**
6. **Der DWD bleibt fuer AT die Blitzpotenzial-Quelle.** GeoSphere kommt
   additiv hinzu und ersetzt nichts.

## Nebenbefund (nicht Teil dieses Auftrags)

`geosphere.py:501` setzt `model="AROME"`; `normalize_model_id` ist
case-insensitive und bildet das auf `meteofrance_arome` ab
(`model_registry.py:43`). Heute folgenlos, weil GeoSphere-Reihen kein
`cape_jkg` tragen — aber eine scharfe Falle. Gehoert als eigener Befund
gemeldet (Kriterium: fehlleitende Modellzuordnung, latentes Fehlverhalten).
