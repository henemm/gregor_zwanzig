# ADR-0071: CAPE eskaliert über LOW hinaus, gedämpft durch die Konvektionshemmung CIN

- **Status:** Akzeptiert
- **Datum:** 2026-09-18
- **Bezug:** GitHub-Issue #2182 (Nachvollziehbarkeit), setzt bereits gelebten Ist-Zustand aus
  #1679 (Commit `937bba52`, 2026-08-11), #1896 (2026-08-16) und #2178 (2026-09-16) fest,
  löst einen Satz aus ADR-0048 ab

## Kontext

ADR-0048 (2026-08-08) hielt fest: „Unberührt bleibt die Produktentscheidung aus feat_1474
AC-6: CAPE misst Energie, kein Ereignis, und eskaliert nie über LOW." Drei Tage später hat
Commit `937bba52` (#1679) genau das aufgehoben: CAPE erreicht seither bei schwacher oder
mäßiger Konvektionshemmung (CIN) auch `MED`/`HIGH`. Die Änderung war fachlich begründet,
Adversary-verifiziert und in der Modul-Spec `feat_1679_cin_paarung_cape_leiter.md`
dokumentiert — aber **nie als eigene ADR**, obwohl sie eine in ADR-0048 unter „Status:
Akzeptiert" festgehaltene Zusicherung revidiert. CLAUDE.md verlangt für genau diesen Fall:
„Eine dokumentierte Entscheidung wird nie still rückgängig gemacht: Abweichung ⇒ neues ADR
(Status ‚Abgelöst durch')."

Seither kamen zwei weitere, ebenfalls unbelegte Nachschärfungen hinzu:

- **#1896** (2026-08-16) hat die ursprünglichen SPC-Bänder (−25/−50/−100/−200 J/kg CIN) durch
  die ICON-näher belegten ECMWF-TM-852-Bänder ersetzt (Groenemeijer, Pucik, Tsonevsky,
  Bechtold 2019, Fig. 2).
- **#2178** (2026-09-16) hat die MED/HIGH-Sprossen der CAPE-Leiter von proportional
  hochgerechneten Werten (750/1200 J/kg für `icon_d2`/`DE_ALPEN`) auf die publizierten
  NWS/SPC-Absolutwerte (1000/2500 J/kg) umgestellt.

ADR-0064 (2026-09-08, #2176) hat inzwischen nur die **Darstellung** von `LOW` aus der
nutzersichtbaren Leiter genommen — sie berührt die hier beschriebene **Eskalationsfrage**
nicht und bestätigt das ausdrücklich („reine Darstellungsänderung, kein Eingriff in die
Auslöseschwellen").

Diese ADR entscheidet nichts neu. Sie schließt die Nachvollziehbarkeitslücke, die #2182
gemeldet hat, indem sie den heute produktiven Ist-Zustand an der Stelle festhält, an der
CLAUDE.md das verlangt.

## Entscheidung

**Die LOW-Deckelung aus ADR-0048/`feat_1474` AC-6 gilt nur noch, wenn CIN unbekannt ist oder
stark dämpft.** Ist CIN bekannt und schwach, erreicht CAPE die volle Leiter bis `HIGH`.

Konkret, wie in `thunder_level_from_signals()` / `_gedaempft_durch_cin()`
(`src/output/metric_format.py`) implementiert:

1. **CAPE-Leiter** (`model_registry.cape_ladder_thresholds_jkg()`): `low` bleibt unverändert
   regional/modellgeeicht (#1592). `med`/`high` sind seit #2178 die publizierten NWS/SPC-
   Absolutwerte **1000/2500 J/kg**, unabhängig von Modell/Region (nicht mehr proportional aus
   `low` hochgerechnet).
2. **CIN-Dämpfung** (seit #1896, ECMWF TM 852): `|CIN| < 50 J/kg` → Leiter zählt voll (auch
   bis `HIGH`). `50 ≤ |CIN| ≤ 100 J/kg` → genau eine Stufe wird abgezogen. `|CIN| > 100 J/kg`
   → gedeckelt auf höchstens `LOW`.
3. **Unbekanntes CIN** (strukturell bei Météo-France/AROME, also FR/Korsika) fällt auf die
   Notbremse „höchstens LOW" — verhaltensgleich zum vor-#1679-Zustand. Das GR20-Gebiet ist von
   dieser Entscheidung damit **nicht** betroffen.
4. CAPE bleibt `selectable=False` (#710/#1585) — die Eskalation wirkt ausschließlich in der
   internen Fusion, nie als wählbare Metrik.

Der Satz „CAPE misst Energie, kein Ereignis, und eskaliert nie über LOW" in ADR-0048 wird an
seiner Fundstelle als durch diese Entscheidung abgelöst markiert. ADR-0048 bleibt für die
übrigen Regeln (modellabhängige Schwellentabelle je Modell × Gebiet) unverändert in Kraft und
trägt weiterhin **Status: Akzeptiert** — nur der eine, hier genannte Satz ist betroffen.

## Verworfene Alternativen

Keine — diese ADR trifft keine neue Entscheidung, sondern dokumentiert nachträglich eine
bereits getroffene, umgesetzte und Adversary-verifizierte Entscheidung (#1679/#1896/#2178).
Die in den jeweiligen Modul-Specs dokumentierten verworfenen Alternativen (z. B. reiner
absoluter Deckel statt relativer Bänder, #1679-Adversary-Befund F001) bleiben dort verzeichnet
und werden hier nicht wiederholt.

## Konsequenzen

- **Positiv:** Die ADR-Lage entspricht wieder dem produktiven Code. Wer künftig ADR-0048 liest,
  bekommt keine widerlegte Aussage mehr als geltende Entscheidung vorgesetzt.
- **Negativ / Preis:** Keiner — reine Dokumentationsnachführung, kein Verhalten ändert sich.
- **Folgepflichten:**
  - Jede weitere Änderung an der CAPE-Leiter oder den CIN-Bändern (z. B. eine künftige eigene
    ICON-Eichung, in `fix_1896_cin_baender_icon.md` als „frühestens nach Saison 2027" notiert)
    löst diese ADR ab statt sie unkommentiert zu unterlaufen.
  - Die Ampelfarbe für `LOW` (ADR-0064, Folgepflicht) bleibt von dieser ADR unberührt.
