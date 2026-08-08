---
entity_id: feat_1531_s1_dwd_gewittergroessen
status: draft
type: module
created: 2026-08-08
updated: 2026-08-08
version: "1.0"
tags: [gewitter, provider, dwd, icon-d2, icon-eu, 1531]
---

# DWD liefert die fehlenden Gewittergrößen (sdi_2, cin_ml, cape_ml, lpi_max, uh_max)

## Approval

- [ ] Approved

## Purpose

Epic #1419 §2a/§3.2 vereinbart je Gebiet eine **Liste** von Gewittergrößen. #1457 (S2) wurde
geschlossen, obwohl davon nur zwei abgerufen werden (`lpi`, `grau_gsp`). Diese Scheibe holt die
fehlenden ICON-D2-Größen nach und ergänzt die Energiegrößen in ICON-EU.

Zwei davon sind nicht Kür:
- **`sdi_2`** (Superzellen) — Superzellen sind die gefährlichste Gewitterform; dafür gibt es
  heute **kein** Signal, auch nicht indirekt.
- **`cin_ml`** (Konvektionshemmung) — CAPE fließt heute **ohne** seine Gegengröße in die
  Einstufung. Genau deshalb ist CAPE in der Fusion vorsorglich auf `LOW` gedeckelt; mit der
  Hemmung wäre die Deckelung fachlich ersetzbar statt Notbremse.

DWD ist **kontingentfrei** — die Größen liegen in denselben Verzeichnissen, aus denen täglich
geladen wird.

## Scope-Abgrenzung

**In dieser Scheibe:** Abruf und Befüllung eigener Felder. Sonst nichts.

**NICHT in dieser Scheibe:** keine Einstufung, keine Schwellen, keine Fusion in
`thunder_level`, keine Katalogmetrik, keine Ausgabe in Mail/SMS/Telegram/Compare. Der Provider
füllt Felder und kennt keine Stufen (#1419 §5). Die Einstufung folgt erst, wenn die Felder da
sind und Messwerte vorliegen (Muster #1474). **Météo-France ist eine eigene Scheibe** — dort
kostet jede Größe einen Abruf je Stunde (#1419 §3.2), hier ist es kostenlos.

## Source

- **File:** `src/providers/dwd.py`, `src/providers/dwd_eu.py`,
  `src/providers/thunder_enrichment.py`, `src/app/models.py`
- **Identifier:** `THUNDER_PARAMS`, `_read_point_value`, `_SIGNAL_ZU_FELD`,
  `ForecastDataPoint`

Schicht: **Python-Core** (`src/providers/`, `src/app/`). Kein Go, kein Frontend.

## Vorbedingung — bereits geklärt (live gemessen 2026-08-08)

Die Namensfalle aus #1457 S2a (`LITOTA3` existierte beim Dienst nicht, jeder Abruf lief lautlos
in 404 bei 24 grünen Tests) ist für diese Scheibe **vorab ausgeschlossen**. Gemessen gegen das
Verzeichnislisting von `opendata.dwd.de`:

| Größe | ICON-D2 | ICON-EU | Semantik (gemessen) | Fehlwerte (gemessen) |
|---|---|---|---|---|
| `sdi_2` | ✅ | ❌ nicht angeboten | Momentanwert, **vorzeichenbehaftet** | 9999,0 (16,7 %) |
| `cin_ml` | ✅ | ✅ | Momentanwert | 9999,0 **und −999,9 (46 %)** |
| `cape_ml` | ✅ | ✅ | Momentanwert | 9999,0 |
| `lpi_max` | ✅ | ❌ (dort `lpi_con_max`) | Momentanwert | 9999,0 |
| `uh_max`, `uh_max_med`, `uh_max_low` | ✅ | ❌ nicht angeboten | Momentanwert, drei **verschiedene** Felder | 9999,0 |
| `cape_con` | ❌ nicht angeboten | ✅ | — | — |

Alle auch als `regular-lat-lon` verfügbar (das Gitter aus `_build_url`, `dwd.py:190`).

## Implementation Details

### 1. Sieben neue Felder in `ForecastDataPoint` (`src/app/models.py`)

```python
supercell_index_sdi2_1s: Optional[float] = None          # 1/s, vorzeichenbehaftet
convective_inhibition_jkg: Optional[float] = None        # J/kg
cape_ml_jkg: Optional[float] = None                      # J/kg, ICON-D2/EU
lightning_potential_max_lpi_jkg: Optional[float] = None
updraft_helicity_max_m2s2: Optional[float] = None        # m²/s², Gesamtsäule
updraft_helicity_max_med_m2s2: Optional[float] = None    # m²/s², mittlere Schicht (2–5 km)
updraft_helicity_max_low_m2s2: Optional[float] = None    # m²/s², untere Schicht
```

Sieben neue Felder. Je Größe ein eigenes Feld — die drei Updraft-Varianten tragen
**verschiedene** Werte (s. u.) und dürften niemals dieselbe Spalte teilen.

`cape_ml` bekommt ein **eigenes** Feld statt `cape_jkg` mitzubenutzen: „je Größe ein eigenes
Feld" (#1419 §3.1/§5), und `cape_jkg` wird bereits von einer anderen Quelle gefüllt
(`models.py:113`). Ein geteiltes Feld für zwei Quellen wäre nicht mehr zuordenbar.

### 2. Abrufliste erweitern

```python
# dwd.py — Reihenfolge = Ausfallreihenfolge bei Budget-Ende (s. AC-7)
THUNDER_PARAMS = (
    "lpi", "grau_gsp", "cin_ml", "sdi_2", "cape_ml", "lpi_max",
    "uh_max_med", "uh_max", "uh_max_low",
)
THUNDER_CUMULATIVE_PARAMS = ("grau_gsp",)   # UNVERÄNDERT — alle neuen sind Momentanwerte
THUNDER_FETCH_DEADLINE_SECONDS = 150.0      # war 90.0 (PO-Entscheid 2026-08-08)

# dwd_eu.py
THUNDER_PARAMS = ("lpi_con_max", "cape_ml", "cape_con", "cin_ml")
```

**Alle drei Updraft-Varianten werden geholt** (PO-Entscheid 2026-08-08). Gemessen sind es drei
verschiedene Felder, kein Duplikat:

| Größe | Wertebereich (+15 h) | am Ort des Gesamtmaximums |
|---|---|---|
| `uh_max` | −114 … 127 | 126,9 |
| `uh_max_low` | −18 … 25 | 9,7 |
| `uh_max_med` | −30 … 39 | 17,7 |

`uh_max` ist am selben Punkt rund **siebenmal größer** als die Schichtvarianten — also nicht
deren Maximum, sondern eine andere Schicht oder Rechenweise. Entscheidend: Die einzigen je
publizierten Zahlen (SPC: 75/150 m²/s²) beziehen sich auf die Schicht **2–5 km**, also auf
`uh_max_med`. Ohne die Schichtvarianten ließe sich später gar nicht prüfen, welche Variante
einstufbar ist. `uh_max_med` steht deshalb **vor** `uh_max` in der Reihenfolge.

### 3. Zweiter Fehlwert-Marker für `cin_ml`

`_read_point_value` prüft heute nur nach oben (`wert >= sentinel`, `dwd.py:212-217`).
**−999,9 ist kleiner und würde durchgereicht** — als Konvektionshemmung von −999,9 J/kg, bei
46 % der Gitterpunkte. Fachlich fatal: daraus würde später „praktisch kein Deckel, CAPE schlägt
voll durch" gelesen. Der Marker bedeutet **„keine Aussage"**, nicht „keine Hemmung"
(`None`-Kontrakt #1377) — plausibel, weil CIN undefiniert ist, wo mangels CAPE nichts zu hemmen
ist.

Die Prüfung wird **je Parameter** geführt, nicht global — genau der Analogieschluss, vor dem
`dwd_eu.py:219-221` warnt („der dritte Analogieschluss in Folge, der sich als falsch erweist").

### 4. Signal→Feld-Zuordnung (`thunder_enrichment.py:36-39`)

Die sieben neuen Paare kommen in `_SIGNAL_ZU_FELD`. Der bestehende Weg
(`setattr(dp, feld, wert)` nur bei `wert is not None`, `:261-268`) bleibt unverändert.

## Expected Behavior

- **Input:** Ort + Zeitfenster wie heute; keine neue Schnittstelle nach außen
- **Output:** sieben zusätzlich befüllte Felder je `ForecastDataPoint` im ICON-D2-Gebiet,
  drei im ICON-EU-Gebiet
- **Side effects:** mehr HTTP-Abrufe gegen `opendata.dwd.de` (kontingentfrei); **keine**
  Änderung an irgendeiner Nutzerausgabe

## Acceptance Criteria

> **Hinweis zur Testart:** Diese Scheibe ist reiner Datenabruf und **darf per AC-9 keine
> Ausgabe verändern** — ein Nachweis über Mail/SMS/Compare ist deshalb strukturell unmöglich
> und wäre ein Widerspruch zum Scope. Beobachtbares Verhalten ist hier: *die Anreicherung
> ausführen und den entstandenen Datenpunkt befragen.* Alle Tests unten führen den echten
> Ablauf (`enrich_thunder` → Provider → Datenpunkt) gegen aufgezeichnete GRIB-Dateien aus.
> **Kein** Test liest Quelltext oder prüft Dateiinhalte per `read_text()`.

- **AC-1:** Given ein Ort im ICON-D2-Gebiet mit veröffentlichtem Lauf / When die
  Gewitter-Anreicherung läuft / Then tragen die Datenpunkte Werte in allen sieben neuen Feldern,
  und zwar dieselben Zahlen, die die DWD-Datei an diesem Gitterpunkt enthält.
  - Test: `enrich_thunder()` gegen aufgezeichnete GRIB-Dateien ausführen; die entstandenen
    Datenpunkte gegen die unabhängig aus derselben Datei ausgelesenen Gitterwerte vergleichen
    — nicht gegen eine im Test notierte Konstante, die mitwandern würde.

- **AC-2:** Given `cin_ml` steht an einem Gitterpunkt auf dem Marker −999,9 / When der Wert
  gelesen wird / Then bleibt das Feld `None` und trägt **nicht** die Zahl −999,9.
  - Test: Anreicherung für einen Ort ausführen, dessen Gitterpunkt −999,9 trägt; der
    entstandene Datenpunkt hat `convective_inhibition_jkg is None`. **Gegenprobe im selben
    Test:** ein Ort mit echtem Wert (gemessen z.B. 7,8 J/kg) behält ihn — sonst würde ein
    Filter, der pauschal alles verwirft, ebenfalls grün werden.

- **AC-3:** Given ein Gitterpunkt außerhalb des Modellgebiets (Marker 9999,0) / When der Wert
  gelesen wird / Then bleibt das jeweilige Feld `None` für **jede** der sieben neuen Größen.
  - Test: je Größe ein Punkt außerhalb des Gebiets; alle sieben Felder `None`.

- **AC-4:** Given `sdi_2` liefert an einem Punkt einen negativen Wert (antizyklonale Rotation)
  / When der Wert gespeichert wird / Then steht die Zahl **mit Vorzeichen** im Feld, also
  −0,0007 und nicht 0,0007.
  - Test: Punkt mit negativem `sdi_2`; Feldwert muss negativ sein. Begründung: der Provider
    liefert Rohwerte; die Betragsbildung gehört in die spätere Einstufung, nicht hierher.

- **AC-5:** Given eine Stunde mit einem Gewitter im Modell / When die Werte über mehrere
  Zeitschritte gelesen werden / Then entsprechen die Feldwerte den **Momentanwerten** der
  jeweiligen Stunde; keine der sieben neuen Größen wird als kumuliert zurückgerechnet.
  - Test: Zeitreihe, in der ein Wert wieder fällt (gemessen: `lpi_max` 0 → 95,45 → 88,69 → 0);
    Feldwerte müssen diesem Verlauf folgen. Bei kumulierter Behandlung wären sie Differenzen
    und der Test rot.

- **AC-6:** Given ein Ort im ICON-EU-Gebiet / When die Anreicherung läuft / Then werden
  `cape_ml`, `cape_con` und `cin_ml` befüllt, und `sdi_2` sowie alle drei `uh_max*`-Varianten bleiben `None`, weil ICON-EU
  sie nicht anbietet.
  - Test: Ort außerhalb des D2-Gebiets (z.B. Mallorca); die drei Energiefelder tragen Werte,
    die vier anderen sind `None`.

- **AC-7:** Given das Zeitbudget der Anreicherung (150 s) wird erschöpft / When der Abbruch
  greift / Then sind `lpi`, `grau_gsp` und `cin_ml` bereits abgerufen, weil sie in der
  Reihenfolge vorn stehen; die Anreicherung bricht fail-soft ab und die Grundvorhersage bleibt
  unberührt.
  - Test: künstlich kleines Budget setzen; prüfen, welche Felder befüllt sind. Begründung: bei
    Budget-Ende fallen die **hinteren** Parameter still komplett aus (`dwd.py:446-448`,
    `:457-458`) — die Reihenfolge ist damit eine fachliche Entscheidung, keine Formalie.

- **AC-8:** Given der Live-Namenswächter läuft / When `THUNDER_PARAMS` erweitert wurde / Then
  prüft er **jeden** Eintrag der Liste gegen das echte DWD-Angebot, nicht nur die ersten zwei.
  - Test: **Verhalten des Wächters**, nicht seine Schreibweise. Mutations-Gegenprobe: einen
    erfundenen Parameternamen an **letzter** Position in `THUNDER_PARAMS` setzen und den
    Wächter laufen lassen ⇒ er MUSS rot werden. Heute bliebe er grün, weil er nur
    `param_index in [0, 1]` prüft (Zeile 44) — ein Wächter, der nicht scheitern kann, bewacht
    nichts. Die Mutation wird per String-Ersetzung mit externer Sicherungskopie gemacht,
    nie per `git checkout/stash/reset`.

- **AC-9:** Given ein Trip-Briefing, ein Ortsvergleich und eine SMS werden erzeugt / When die
  neuen Felder befüllt sind / Then ist keine einzige Ausgabe anders als vorher — keine neue
  Spalte, kein neues Token, keine geänderte Gewitterstufe.
  - Test: Briefing-Mail, Compare-Mail und SMS aus identischen Eingangsdaten erzeugen — einmal
    mit befüllten neuen Feldern, einmal mit leeren — und die erzeugten Ausgaben zeichenweise
    vergleichen. Sie müssen identisch sein. Das ist der einzige AC, der Nutzerausgaben prüft,
    und er prüft bewusst deren **Unveränderlichkeit**.

## Estimated Scope

- **LoC:** ~180–230
- **Files:** 4 Produktivdateien (`models.py`, `dwd.py`, `dwd_eu.py`, `thunder_enrichment.py`)
  + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `opendata.dwd.de` ICON-D2/ICON-EU | extern | Datenquelle, kontingentfrei |
| `thunder_routing.py` | intern | Gebietszuordnung, unverändert |
| `thunder_enrichment.py` | intern | einziger Anreicherungspunkt, unverändert im Ablauf |
| #1419 §2a/§3.2/§5 | Konzept | Größenliste je Gebiet, `None`-Kontrakt |

## Known Limitations

- **GRIB-Metadaten sind unbrauchbar für Bedeutung/Einheit.** GDAL meldet für `sdi_2`
  „Best (4 layer) Lifted Index [C]" und für `lpi_max` einen unbekannten Parameter. Maßgeblich
  ist die DWD-Dokumentation, nicht `ds.tags()`.
- **Alle drei `uh_max*` bleiben vorerst ohne belegte Schwelle.** Die Felder werden befüllt,
  sind aber nicht einstufbar (SPC hat feste Schwellen 2019 selbst verworfen; Faktor 2 zwischen
  Modellkernen). Bewusst: erst Daten sammeln, dann entscheiden — und zwar über alle drei
  Schichten, weil ungeklärt ist, welche die publizierten Zahlen meinen.
- **Die DWD-Felddefinition der Updraft-Schichten ist nicht auffindbar.** Dass `_low` 0–3 km und
  `_med` 2–5 km meint, stammt aus einem Drittanbieter-Portal, nicht vom DWD. Deshalb werden
  alle drei geholt statt auf eine gewettet.
- **`cin_ml` in ICON-EU ist ungemessen.** Ob der −999,9-Marker dort ebenso auftritt, ist offen;
  AC-2 gilt zunächst für ICON-D2. Für ICON-EU wird derselbe Schutz vorsorglich mitgeführt,
  aber nicht als gemessen behauptet.
- Zeitbudget: 9 Größen × 24 h = 216 Abrufe, Regelfall ~52 s (gemessen 0,24 s je Abruf).
  Budget auf **150 s** angehoben (war 90 s), damit auch ein langsamer Lauf trägt. Erst ab
  ~0,69 s je Abruf reißt es — AC-7 regelt, was dann zuerst da ist.
