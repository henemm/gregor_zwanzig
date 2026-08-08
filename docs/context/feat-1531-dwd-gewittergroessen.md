# Context: feat-1531-dwd-gewittergroessen (#1531 Scheibe 1)

## Request Summary

#1457 (S2) wurde geschlossen, obwohl von den in Epic #1419 §2a/§3.2 vereinbarten DWD-Gewitter-
größen nur zwei abgerufen werden. Diese Scheibe holt die fehlenden ICON-D2-Größen nach
(`sdi_2`, `cin_ml`, `cape_ml`, `lpi_max`, `uh_max`) sowie die Energiegrößen aus ICON-EU.
DWD ist kontingentfrei — die Größen liegen in denselben Verzeichnissen, aus denen täglich
geladen wird.

**Abgrenzung:** Nur **Abruf und Feldbefüllung**. Keine Einstufung, keine Schwellen, keine
Ausgabe — der Provider füllt Felder und kennt keine Stufen (#1419 §5). Météo-France ist eine
eigene Scheibe (Kostenasymmetrie: dort ein Abruf je Größe **und** Stunde).

## 🟢 Vorbedingung geklärt — Abrufnamen gegen das echte Angebot geprüft

Gemessen 2026-08-08 gegen das Verzeichnislisting von `opendata.dwd.de`. Das ist die Lehre aus
#1457 S2a, wo `LITOTA3` beim Dienst gar nicht existierte und jeder Abruf lautlos in 404 lief —
bei 24 grünen Tests.

| Größe | ICON-D2 (129 Parameter) | ICON-EU (94 Parameter) |
|---|---|---|
| `sdi_2` | ✅ | ❌ **nicht angeboten** |
| `cin_ml` | ✅ | ✅ |
| `cape_ml` | ✅ | ✅ |
| `lpi_max` | ✅ | ❌ (dort `lpi_con_max`) |
| `uh_max` (+ `uh_max_low`, `uh_max_med`) | ✅ | ❌ **nicht angeboten** |
| `cape_con` | ❌ nicht angeboten | ✅ |
| `sdi_1` | ❌ nicht angeboten | ❌ |

Alle vorhanden **auch als `regular-lat-lon`** — das ist das Gitter, das `_build_url`
(`dwd.py:190`) verwendet. Dateien real abrufbar (HTTP 206 bei Range-Request).

Dass `sdi_2` in ICON-EU fehlt, deckt sich mit der DWD-Aussage, dass der Index für gröbere
Auflösungen nicht gilt („nicht auf das COSMO-EU übertragbar").

## 🟢 Semantik je Größe — gemessen, nicht angenommen

Punkt 47,40 N / 11,00 O (Tirol) sowie am jeweiligen Feldmaximum, Lauf 21 UTC:

| Größe | Verlauf | Einstufung | nodata |
|---|---|---|---|
| `cin_ml` | 1,41 → 1,69 → 1,88 → 8,29 → 11,63 → 17,44 → 73,97 → **71,01** → **3,91** | **Momentanwert** (fällt 2×) | 9999.0 |
| `cape_ml` | 169 → 94,6 → 74,3 → 58,1 → 71,9 → 38 → 6,1 | **Momentanwert** (fällt 6×) | 9999.0 |
| `uh_max` | −0,001 → 0,002 → 0,016 → 0,032 → 0,031 → 0,011 | **Momentanwert** (fällt 3×) | 9999.0 |
| `sdi_2` | am Maximum: 0 → **−0,0007** → 0 | **Momentanwert** | 9999.0 |
| `lpi_max` | am Maximum: 0 → **95,45** → **88,69** → 0 | **Momentanwert** (fällt 2×) | 9999.0 |
| `grau_gsp` *(Bestand)* | nie fallend | **kumuliert** (unverändert) | 9999.0 |

⇒ **Keine der fünf neuen Größen gehört in `THUNDER_CUMULATIVE_PARAMS`.** Wichtig, weil ein
kumulierter Parameter, der dort fehlt, den seit Laufbeginn aufsummierten Wert still
durchreichen würde (`dwd.py:453-456`, `else`-Zweig).

⚠️ `lpi_max` musste **am Feldmaximum** gemessen werden — am ursprünglichen Messpunkt war es
durchgehend 0, dort wäre die Frage unbeantwortbar geblieben und „nie fallend" hätte fälschlich
nach kumuliert ausgesehen.

## 🟢 Skalen tragen die publizierten Schwellen

Maximum über das gesamte ICON-D2-Gitter (Beträge), Lauf 21 UTC:

| Größe | Feld-Maximum | publizierte Schwelle | erreichbar? |
|---|---|---|---|
| `sdi_2` | 0,000739 | 0,0003 / 0,003 1/s | ✅ minimale Schwelle erreicht |
| `uh_max` | 126,9 | (US-Werte 75/150 — **nicht übertragbar**) | Skala plausibel |
| `lpi_max` | 95,45 | 1 / 30 / 50 | ✅ |
| `cape_ml` | 4233 | 1000 / 2000 | ✅ |
| `cin_ml` | 526 (echte Werte, ohne Marker) | — | ✅ plausibel |

**`sdi_2` trägt am Maximum ein negatives Vorzeichen (−0,0007).** Bestätigt die DWD-Regel:
Vorzeichen kodiert den Rotationssinn (`>0` zyklonal, `<0` antizyklonal) ⇒ **Betrag verwenden**.
Wer das Vorzeichen ignoriert, verliert die antizyklonalen Superzellen vollständig.

## 🔴 Risiken und offene Punkte

1. **GRIB-Metadaten sind für DWD-Spezialgrößen fehlzugeordnet.** GDAL meldet für `sdi_2`
   „Best (4 layer) Lifted Index **[C]**" — das ist nicht der Supercell Detection Index (DWD:
   Einheit 1/s). `lpi_max` kommt als „(prodType 0, cat 17, subcat 192) [-]", also unbekannt.
   ⇒ Einheiten/Bedeutung **niemals** aus `ds.tags()` ableiten; maßgeblich ist die
   DWD-Dokumentation plus Plausibilitätsprüfung gegen die publizierten Schwellen.
2. **🔴 `cin_ml` hat einen ZWEITEN Fehlwert-Marker: −999,9 — bei 46 % aller Gitterpunkte.**
   Gemessen über das gesamte Gitter (+6 h, 906.390 Punkte):

   | Größe | Anteil 9999,0 (außer Gebiet) | Anteil **−999,9** | echte Werte |
   |---|---|---|---|
   | `cin_ml` | 16,7 % | **46,0 %** | 0,006 … 526 J/kg (P50 = 7,8) |
   | `cape_ml` | 16,7 % | 0,0 % | 0 … 3950 J/kg |
   | `sdi_2` | 16,7 % | 0,0 % | −0,000151 … 0,000454 |
   | `uh_max` | 16,7 % | 0,0 % | −11,2 … 15,5 |
   | `lpi_max` | 16,7 % | 0,0 % | 0 … 33,1 |

   Der bestehende Filter prüft `wert >= sentinel` mit `sentinel = 9999,0`
   (`dwd.py:212-217`) — **−999,9 ist kleiner und würde durchgereicht**, als
   Konvektionshemmung von −999,9 J/kg. Fachlich fatal: genau daraus würde später „praktisch
   kein Deckel, CAPE schlägt voll durch" gelesen, und das bei fast der Hälfte der Punkte.
   Plausible Bedeutung: CIN ist undefiniert, wo keine Konvektion möglich ist (ohne CAPE gibt
   es nichts zu hemmen) — also **„keine Aussage", nicht „keine Hemmung"** (`None`-Kontrakt
   #1377). Die 16,7 % bei 9999,0 decken sich exakt mit dem dokumentierten Überstand des
   ausgelieferten Rechtecks („rund 17 % größer als das Modellgebiet", `dwd.py:96-97`).

   Präzedenz mahnt zusätzlich: `dwd_eu.py:219-221` hält fest, der Analogieschluss vom
   D2-Fehlwert wäre „der dritte Analogieschluss in Folge, der sich als falsch erweist".
3. **Der Live-Namenswächter deckt die neuen Parameter nicht ab.**
   `tests/tdd/test_dwd_thunder_parameter_names_live.py:44` parametrisiert hartkodiert über
   `param_index in [0, 1]` statt über `len(dwd.THUNDER_PARAMS)`. Wird `THUNDER_PARAMS`
   erweitert, prüft der Wächter die neuen Namen **stillschweigend nicht** — ein Test, der
   nicht scheitern kann. Muss mit erweitert werden.
4. **Stiller Teilausfall bei Budget-Ende.** `_thunder_budget_erschoepft` bricht die innere
   Offset-Schleife ab (`dwd.py:446-448`) und danach die äußere (`:457-458`). Die Parameter, die
   in der Iterationsreihenfolge **hinten** stehen, werden dann gar nicht erst angefragt und
   bleiben komplett leer — ohne Meldung. Die Reihenfolge in `THUNDER_PARAMS` entscheidet damit
   fachlich, was im Zweifel ausfällt.
5. **`cape_jkg` ist bereits belegt.** Das Feld existiert (`models.py:113`) und wird von einer
   anderen Quelle gefüllt. Ob `cape_ml` dorthin darf oder ein eigenes Feld braucht, ist zu
   entscheiden — ein gemeinsames Feld für zwei Quellen widerspräche „je Größe ein eigenes
   Feld" (#1419 §3.1/§5).

## 🟢 Zeitbudget — entwarnt, aber knapp im Randfall

Gemessen über 10 echte Abrufe: **Mittel 0,24 s** je Abruf (Spanne 0,05–1,14 s; entpackt
1,6–6,5 MB je Datei).

| | Abrufe | erwartete Dauer | Budget |
|---|---|---|---|
| heute (2 Größen × 24 h + Anker) | 49 | ~12 s | 90 s |
| geplant (7 Größen × 24 h) | 168 | **~40 s** | 90 s |
| ungünstiger Fall (1,14 s je Abruf) | 168 | **~191 s** | 🔴 reißt |

Der im Code hinterlegte Richtwert von ~1,9 s je Abruf stammt aus der **Météo-France**-Herleitung
(`dwd.py:105-106`) und trifft für den DWD nicht zu — er überschätzt um das Achtfache. Das
Budget trägt den Regelfall bequem; für den Randfall ist zu entscheiden, ob
`THUNDER_FETCH_DEADLINE_SECONDS` steigt oder die Parameter-Reihenfolge fachlich priorisiert
wird (siehe Risiko 4). Abrufe laufen **sequenziell** (kein Threading/async im Modul).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/providers/dwd.py:86` | `THUNDER_PARAMS = ("lpi", "grau_gsp")` — zentrale Erweiterung |
| `src/providers/dwd.py:93` | `THUNDER_CUMULATIVE_PARAMS` — bleibt unverändert |
| `src/providers/dwd.py:100` | `THUNDER_FILL_VALUE`, genutzt in `_read_point_value:212-217` |
| `src/providers/dwd.py:108` | `THUNDER_FETCH_DEADLINE_SECONDS = 90.0` |
| `src/providers/dwd.py:382-469` | `fetch_thunder_signals_named` — Abrufschleife, Budget-Abbruch |
| `src/providers/dwd_eu.py:88` | `THUNDER_PARAMS = ("lpi_con_max",)`; eigenständige Implementierung |
| `src/providers/dwd_eu.py:96` | `_SIGNAL_KEYS` mappt `lpi_con_max` → `lpi` |
| `src/providers/thunder_enrichment.py:36-39` | `_SIGNAL_ZU_FELD` — kennt heute zwei Signale |
| `src/providers/thunder_enrichment.py:261-268` | `setattr(dp, feld, wert)`, nur wenn nicht `None` |
| `src/app/models.py:113, 151, 160, 161` | bestehende Gewitterfelder; fünf neue kommen dazu |
| `src/providers/thunder_routing.py:63-67` | Gebietszuordnung `fr_direct` / `de_direct` / `eu_direct` |
| `tests/tdd/test_dwd_thunder_parameter_names_live.py:44` | Live-Namenswächter, hartkodiert auf 2 Parameter |
| `tests/tdd/test_dwd_thunder_signal_fetch.py` | Kernabdeckung (Anker, Fehlwert, Budget, Fallback) |

## Dependencies

- **Upstream:** `opendata.dwd.de` ICON-D2 und ICON-EU (frei, kontingentfrei)
- **Downstream:** `ForecastDataPoint`-Felder → später Fusion in `thunder_level_from_signals()`
  (`metric_format.py:326`). **In dieser Scheibe bewusst nicht angeschlossen** — erst wenn die
  Felder da sind und Messwerte vorliegen (Muster #1474).

## Open Questions

- [ ] Bekommt `cape_ml` ein eigenes Feld oder teilt es sich `cape_jkg` mit der anderen Quelle?
      (Empfehlung: eigenes Feld — „je Größe ein eigenes Feld", #1419 §3.1/§5)
- [x] Ist `cin_ml = 999,9` ein Deckel oder ein Fehlwert? → **Geklärt: −999,9 ist ein zweiter
      Fehlwert-Marker bei 46 % der Punkte, muss zu `None` werden.**
- [ ] Steigt das Zeitbudget, oder wird die Parameter-Reihenfolge fachlich priorisiert?
      (Regelfall ~40 s von 90 s; Randfall reißt)
- [ ] Werden `uh_max_low`/`uh_max_med` mitgeholt? Beide sind verfügbar, aber ohne belegte
      Schwelle und ohne offizielle DWD-Felddefinition — Empfehlung: **nein**, nicht auf Vorrat.
