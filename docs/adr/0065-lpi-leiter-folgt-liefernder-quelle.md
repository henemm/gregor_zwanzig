# ADR-0065: Die LPI-Schwellenleiter folgt der liefernden Quelle, nicht dem geografischen Gebiet

- **Status:** Akzeptiert (PO-Freigabe 2026-09-09 zur Spec `fix_2263_lpi_leiter_nach_liefernder_quelle.md`)
- **Datum:** 2026-09-09
- **Bezug:** GitHub-Issue #2263 (Epic #2257, Block 2 „Fallback-Härtung"), Spec
  `docs/specs/modules/fix_2263_lpi_leiter_nach_liefernder_quelle.md`, Kontext
  `docs/context/fix-2263-lpi-leiter-vertretung.md`; stellt [ADR-0047](0047-gewitter-vertretung-zwischen-direktquellen.md)
  §5 her, löst es nicht ab; löst `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md`
  **ausschließlich in der Schlüsselungs-Frage** ab (Muster [ADR-0058](0058-wegpunkt-hoehe-an-provider-api.md)
  zu ADR-0018).

## Kontext

ADR-0047 §5 hat entschieden: Springt bei Ausfall einer Gewitter-Direktquelle die benannte
Vertretung `eu_direct` ein, schreibt sie strukturell in das Feld, das sie selbst benennt
(`lightning_potential_lpi_jkg`), und dieser Wert soll — mit transparentem Vermerk — dieselbe
Stufen-Fusion speisen wie der Primärwert. Diese Wirkung ist für einen Teil der Vertretungsfälle
nie eingetreten, weil `_schwellen_fuer_reihe()` (`src/providers/thunder_enrichment.py:279-304`)
die LPI-Leiter bislang ausschließlich über `thunder_region_for(lat, lon)` auflöste — also über
das geografische Gebiet der Koordinate, nicht über die Quelle, die den Wert tatsächlich geliefert
hat.

Zwei konkrete Fehlwirkungen (`feat_1679_lpi_schwellen_region_tabelle.md` legt die Gebiets-Tabelle
`LPI_THRESHOLDS_JKG` fest, aus der beide Fehler folgen):

1. **FR/Korsika:** `fr_direct` fällt aus, `eu_direct` liefert einen echten Blitzpotenzial-Wert.
   Die Gebiets-Leiter für `FR` existiert nicht (`lpi_thresholds_jkg("FR") is None`, bewusste
   Aussparung — AROME liefert dort regulär Blitzdichte, kein LPI). Das Vertretungssignal
   verpufft vollständig.
2. **DE_ALPEN:** `de_direct` fällt aus, `eu_direct` liefert denselben Wert. Der ICON-EU-Wert
   (kalibriert für `EU_REST`: 7,14/23,81/86,16 J/kg) wird gegen die für ICON-D2 kalibrierte,
   deutlich schärfere `DE_ALPEN`-Leiter (1,0/30,0/50,0 J/kg) bewertet — eine Fehleskalation, z. B.
   HIGH statt korrekt MED bei 60 J/kg.

Die CAPE-Leiter derselben Funktion löst bereits richtig auf: modell- **und** gebietsabhängig
(`cape_ladder_thresholds_jkg(effective_cape_model_id(reihe.meta), region)`). Die LPI-Seite war
die einzige verbliebene, rein geografische Auflösung — eine Asymmetrie in derselben Funktion,
keine fehlende Kalibrierung.

## Entscheidung

1. **Die LPI-Leiter wird künftig nach der liefernden Quelle geschlüsselt, nicht nach dem
   geografischen Gebiet.** Physikalisch beschreibt die Leiter die Kalibrierung einer **Größe**
   (`lpi` aus ICON-D2 vs. `lpi_con_max` aus ICON-EU), nicht eines Ortes. Die bisherige
   Gebiets-Tabelle war eine Abkürzung, die nur trägt, solange jede Region ausschließlich ihre
   Primärquelle liefert — genau diese Voraussetzung bricht die Vertretung.
2. **`LPI_THRESHOLDS_JKG` bleibt der einzige Wertespeicher, unverändert in Inhalt und Signatur.**
   Ebenso `lpi_thresholds_jkg()`. Es werden keine Sprossen kopiert oder neu kalibriert. Neu ist
   ausschließlich eine schmale Übersetzung „liefernde Quelle → bestehender
   Kalibrierungs-Schlüssel" (`app.model_registry.lpi_schluessel_fuer_quelle()`):
   `de_direct → "DE_ALPEN"`, `eu_direct → "EU_REST"`, `fr_direct → keiner`. Damit bleibt
   `lpi_thresholds_jkg("FR") is None` wahr, und die drei bestehenden Regressionswächter
   (`test_lpi_threshold_region_table.py:79,89-98,257-266`, `test_lpi_eu_rest_ladder.py:162-188`)
   bleiben zu Recht grün.
3. **Erkennungsmerkmal der Vertretung ist ausschließlich `ForecastMeta.fallback_metrics`
   (Feldname), niemals `fallback_model`.** `fallback_model` trägt beim Gewitter-Fallback nur den
   Providernamen und kann zugleich vom Grundvorhersage-Fallback mit einer anderen Modell-Kennung
   belegt sein (ADR-0047 Known Limitations Punkt 3, Merge-Schutz in `_fetch_primaerquelle`) —
   ein Griff nach `fallback_model` läse dort das falsche Feld und erkennte die Vertretung nicht.
   Dieselbe Erkennungsregel nutzt bereits der Klartext-Vermerk in `fallback_notice.py` seit
   #1492 S2b — kein neuer Mechanismus, ein bestehendes Muster.
4. **Der Fix bleibt vollständig in `_schwellen_fuer_reihe()`.** Sie bestimmt die liefernde
   Quelle aus `thunder_provider_for()` (Primärquelle) und `thunder_vertretung_for()` (Ersatz,
   wenn `fallback_metrics` die Vertretung anzeigt) und übergibt den daraus abgeleiteten
   Kalibrierungs-Schlüssel an das unveränderte `lpi_thresholds_jkg()`. `reihe.meta` wird
   **nicht** in `lpi_thresholds_jkg()` selbst hineingereicht — das hätte dieselben drei Wächter
   gebrochen, die diese Entscheidung ausdrücklich erhält.

## Verworfene Alternativen

- **`"FR"` direkt in `LPI_THRESHOLDS_JKG` eintragen** — verworfen: der Kommentar bei
  `LPI_THRESHOLDS_JKG` ist eine Aussage über die Primärquelle `fr_direct` (liefert Blitzdichte,
  kein LPI) und bleibt für sie richtig; ein FR-Eintrag würde ihn nur für die Vertretung
  brauchbar machen und dabei die freigegebene Aussparung für die Primärquelle stillschweigend
  aufheben — genau die Umkehr, die die drei Regressionswächter verhindern sollen.
- **Vertretung an `reihe.meta.fallback_model` erkennen** — verworfen: das Feld kann gleichzeitig
  vom Grundvorhersage-Fallback belegt sein (ADR-0047 Known Limitations Punkt 3); ein
  String-Vergleich `fallback_model == "eu_direct"` bestünde die ursprünglichen Fälle, würde aber
  in genau dieser Kollisionslage die Vertretung nicht erkennen — bewacht durch die
  Mutations-Gegenprobe der Spec (AC-6).
- **Eine zweite, quellenbezogene Wertetabelle parallel zu `LPI_THRESHOLDS_JKG`** — verworfen:
  hätte dieselben Kalibrierungswerte an zwei Stellen gehalten und wäre ein Duplikat, kein Fix der
  Schlüsselung.

## Konsequenzen

- **Positiv:** Die per ADR-0047 §5 beschlossene Wirkung tritt jetzt für alle Vertretungsfälle
  ein — für Korsika entsteht erstmals eine Gewitterstufe aus dem Vertretungssignal, für die Alpen
  entfällt die bisherige Fehleskalation (HIGH statt MED). Beide Fehler haben dieselbe Ursache,
  dieselbe Codestelle und werden mit demselben Fix behoben.
- **Negativ / Preis:** Keiner identifiziert — die Änderung ist additiv (neue Übersetzungstabelle),
  keine bestehende Zusicherung wird umgekehrt.
- **Folgepflichten:** `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` gilt ab
  sofort **nur noch in der Schlüsselungs-Frage** als abgelöst — ihre Werte (`LPI_THRESHOLDS_JKG`)
  und die FR-Aussparung bleiben unverändert gültig. Eine neue Direktquelle mit eigener LPI-Größe
  erbt dieselbe Pflicht: eigener Eintrag in `_LPI_QUELLE_ZU_SCHLUESSEL`
  (`src/app/model_registry.py`), keine neue Parallel-Tabelle.

## Changelog

- 2026-09-09 (initial): ADR erstellt zusammen mit der Implementierung zu Issue #2263.
