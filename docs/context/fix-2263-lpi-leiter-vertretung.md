# Context: fix-2263-lpi-leiter-vertretung

Issue: [#2263](https://github.com/henemm/gregor_zwanzig/issues/2263) · Epic [#2257](https://github.com/henemm/gregor_zwanzig/issues/2257) (Block 2 „Fallback-Härtung", nach Block 1 Zugang/#1647)
Erstellt: 2026-09-09

## Request Summary

Fällt die Gewitter-Primärquelle für Frankreich/Korsika (`fr_direct`, Météo-France) aus, springt
laut ADR-0047 die Vertretung `eu_direct` (DWD ICON-EU) ein und liefert ein echtes
Blitzpotenzial. Dieses Signal wird jedoch nie zu einer Gewitterstufe, weil die
Schwellenleiter rein geografisch aufgelöst wird und für das Gebiet `FR` keine
Blitzpotenzial-Leiter existiert. Die per ADR beschlossene Vertretung bleibt in ihrer
Kernwirkung aus.

## Befund-Korrekturen am Issue-Text

Drei Aussagen des Issues tragen so nicht und werden in der Spec korrigiert statt übernommen:

1. **Pfad falsch.** Das Issue nennt `src/services/model_registry.py:180-187`. Die Datei
   existiert nicht; richtig ist `src/app/model_registry.py:180-187`.
2. **Auslöser nicht mehr herstellbar.** AC-1 des Entwurfs setzt „MF antwortet 401" voraus. Die
   Messung aus Block 1 des Epics (#1647, 2026-09-09) hat gezeigt, dass der Météo-France-Zugang
   vollständig trägt (GetCoverage 200); der 401 vom 09.08. bleibt unerklärt. Die AC muss gegen
   einen **eingespeisten** Quellenausfall (`ThunderSourceUnavailableError`, ADR-0047
   Entscheidung 1) formuliert werden, nicht gegen den HTTP-Status — sonst ist sie strukturell
   unbeweisbar. Wie häufig der Vertretungsfall real eintritt, ist damit offen; das ist ein
   Eingabewert für die Priorisierung (`priority:medium`), kein Grund gegen den Fix: eine
   Vertretung, die nicht vertritt, ist unabhängig von ihrer Auslösehäufigkeit defekt.
3. **Wirkung überzeichnet.** „Das GR20-Kerngebiet hat bei MF-Ausfall **keine** Gewitterstufe"
   ist falsch. Die Fusion nimmt das schärfste vorhandene Signal
   (`max_thunder()`, `metric_format.py:527-598`); Wettercode und CAPE tragen weiter, und für
   `FR` existieren CAPE-Leitern für alle vier Modelle (`model_registry.py:120-132`, u.a.
   `("icon_eu","FR") = 850.0`). Wahr ist das Engere: **das Signal der Ersatzquelle verpufft**,
   die Aussage wird gröber als beschlossen — nicht leer.

## Ursache (belegt)

`src/providers/thunder_enrichment.py:279-304` (`_schwellen_fuer_reihe`) löst **beide** Leitern
über denselben Gebiets-Nachschlag auf, aber asymmetrisch:

| Zeile | Leiter | Auflösung über |
|---|---|---|
| 302 | CAPE | Gebiet **und** Modell-Herkunft (`effective_cape_model_id(reihe.meta)`) |
| 303 | Blitzpotenzial | **nur** Gebiet (`lpi_thresholds_jkg(region)`) |

`region` stammt aus `thunder_region_for(lat, lon)` (Zeile 300) — rein geografisch, first-match-wins
über `thunder_routing._REGIONS:73-77`. Korsika (≈42,2 N / 9,1 O) liegt im `FR`-Rechteck und ist
damit **immer** `FR`, unabhängig davon, welche Quelle den Datenpunkt tatsächlich befüllt hat.
`lpi_thresholds_jkg("FR")` liefert `None` (`model_registry.py:174-187`), und die
Alles-oder-nichts-Regel der Fusion (`metric_format.py:433-482`) verwirft das Signal vollständig,
sobald eine der drei Sprossen fehlt.

Die CAPE-Seite macht die richtige Auflösung also bereits vor. **Der Defekt ist diese Asymmetrie**,
nicht eine fehlende Kalibrierung.

## Warum die naheliegende Abkürzung falsch ist

`"FR"` einfach in `LPI_THRESHOLDS_JKG` einzutragen wäre ein Verstoß:

- Der Kommentar `model_registry.py:172-173` („FR bekommt bewusst KEINEN Eintrag — AROME liefert
  dort Blitzdichte, kein LPI") ist eine Aussage über die **Primärquelle** und bleibt für sie
  richtig. Er übersieht lediglich den Vertretungsfall.
- Drei Regressionswächter schreiben das Fehlen ausdrücklich fest:
  `test_lpi_threshold_region_table.py:79` (`"FR" not in LPI_THRESHOLDS_JKG`), ebenda `:89-98`
  und `:257-266`, sowie `test_lpi_eu_rest_ladder.py:162-188` (FR trägt trotz gesetztem
  LPI-Wert kein Signal). Sie stammen aus freigegebenen Specs (#1678/#1679).

Der saubere Weg: **die Leiter folgt der liefernden Quelle bzw. der gelieferten Größe, nicht dem
Gebiet.** Die Ersatzquelle liefert `lpi_con_max` (ICON-EU, `dwd_eu.py:99-118`) — exakt die Größe,
für die die `EU_REST`-Leiter (7,14 / 23,81 / 86,16) belegt ist (Schröder/Göcke/Köhler 2022,
`model_registry.py:145-177`). Es braucht **keine neue Kalibrierung und keine neue Literatur**.
Damit bleibt `lpi_thresholds_jkg("FR") is None` wahr und alle drei Wächter bleiben zu Recht
grün — die Änderung ist additiv, keine Umkehr einer freigegebenen Zusicherung.

## Die Naht trägt bereits

Reihenfolge in `enrich_thunder` (`thunder_enrichment.py:307-372`):

1. Zeile 353 → `_fetch_lightning_density()` → `_fetch_primaerquelle()` (462-546): Vertretung
   wird versucht (`thunder_vertretung_for`, Zeile 500) und bei Erfolg markiert —
   `fallback_model` / `fallback_reason="thunder_source_unavailable"` / `fallback_metrics`
   (Zeile 529-541) plus `log_enrichment_call(..., OUTCOME_FALLBACK, ...)`.
2. Zeile 365 → `_schwellen_fuer_reihe()`: **hier ist der Marker bereits gesetzt.**
3. Zeile 370 → `_fuse_thunder_levels()`.

Die Information, die zur richtigen Leiterwahl fehlt, liegt an der Stelle der Auflösung also
schon vor. Der Fix braucht **keine Umsortierung** des Ablaufs.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/providers/thunder_enrichment.py:279-304` | `_schwellen_fuer_reihe` — die asymmetrische Auflösung, Ort des Fixes |
| `src/providers/thunder_enrichment.py:307-372` | `enrich_thunder` — Reihenfolge Abruf → Schwellen → Fusion |
| `src/providers/thunder_enrichment.py:462-546` | `_fetch_primaerquelle` — Vertretung + Markierung (`fallback_metrics`) |
| `src/app/model_registry.py:145-187` | `LPI_THRESHOLDS_JKG` + `lpi_thresholds_jkg()`, Herleitung der `EU_REST`-Sprossen |
| `src/app/model_registry.py:120-140, 228-243` | CAPE-Leiter als **Vorbild** der modell-/herkunftsabhängigen Auflösung |
| `src/providers/thunder_routing.py:73-77, 178-187` | `_REGIONS` (geografisch) und `_VERTRETUNG` (`fr_direct → eu_direct`) |
| `src/providers/dwd_eu.py:99-118` | `lpi_con_max → lpi`: die Ersatzquelle liefert genau die `EU_REST`-Größe |
| `src/output/metric_format.py:433-482, 527-598` | Fusion, Alles-oder-nichts-Regel je Signal |
| `src/output/renderers/fallback_notice.py:156-190` | Klartext-Vermerk der Vertretung im Briefing (Nebenbefund, s.u.) |

## Existing Specs & ADRs

- `docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md` — **die tragende Entscheidung.**
  §5: die Vertretung `fr_direct → eu_direct` schreibt strukturell in das Feld der Ersatzquelle
  (`lightning_potential_lpi_jkg`); „beide Felder speisen dieselbe Stufen-Fusion **mit je eigener
  Schwellentabelle**". PO-Freigabe 2026-08-05: „eine etwas anders hergeleitete Gewitterstufe ist
  besser als keine, Bedingung ist der transparente Vermerk." Genau diese beschlossene Wirkung
  tritt für FR nicht ein.
- `docs/adr/0018-provider-fallback-ohne-kaschieren.md` — Nicht-Kaschieren-Muster, von 0047 geerbt.
- `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` — Abgrenzung: Anzahl der
  **Ausgabe**-Quellen bleibt eine; hier geht es um die Befüllung davor.
- `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` — legt die FR-Aussparung fest (AC-1/AC-6).
- `docs/specs/modules/feat_1678_lpi_eu_schwellenleiter.md` — Herleitung der `EU_REST`-Leiter.
- `docs/specs/modules/feat_1492_s2a_thunder_vertretung.md` / `feat_1492_s2b_fallback_sichtbarkeit.md` — Vertretung und ihr Klartext-Vermerk.

## Test-Ausgangslage

- **Keine Abdeckung des Falls.** Kein Test prüft „`fr_direct` fällt aus → `eu_direct` liefert
  Blitzpotenzial für Korsika → entsteht eine Stufe?". Der einzige Test des Vertretungspfads
  (`test_thunder_enrichment_health_journal.py:74, 195-241`) liegt auf `Location(46.40, 12.52)` —
  das ist `DE_ALPEN`, wo die Leiter existiert und der Defekt deshalb nicht sichtbar wird.
- **Drei Wächter am Ist-Zustand** (s.o.) — müssen grün bleiben.
- Die Schicht ist **Kern/deterministisch**: der Auslöser ist eine eingespeiste Ausnahme, kein Netz.

## Dependencies

- **Upstream:** `thunder_routing` (Gebiet + Vertretungstabelle), `model_registry` (Leitern),
  `dwd_eu`/`meteofrance` (Signalnamen), `ForecastMeta.fallback_*` (Markierung).
- **Downstream:** `dp.thunder_level` → alle Ausgaben und **Alarme**. Alarme müssen alle vier
  Kanäle erreichen (#1701) — eine geänderte Stufe im Vertretungsfall propagiert bis dorthin.

## Risks & Considerations

- **Blast Radius:** Die Gewitterstufe speist Alarme; eine Änderung wirkt in E-Mail, Telegram,
  SMS und Premium-SMS zugleich. Kein Kanal darf ausfallen.
- **Entscheidungsfläche:** Die Leiterauflösung ist ADR-Gegenstand (0047/0018). Ob die
  Herkunftsabhängigkeit ein eigenes ADR braucht oder als Fortschreibung von 0047 gilt, ist in
  Phase `/20-analyse` zu entscheiden — sie widerspricht 0047 nicht, sondern stellt dessen §5 her.
- **Nicht-Kaschieren in beide Richtungen:** Heute erscheint für Korsika die Klartextzeile „hier
  wurde ausgewichen" (`fallback_notice.py:156-190`, erkannt über `fallback_metrics`), obwohl der
  gelieferte Wert die Stufe nicht beeinflusst hat. Das behauptet eine Wirkung, die es nicht gibt
  — Kaschieren mit umgekehrtem Vorzeichen. Der Fix beseitigt die Ursache; ob zusätzlich ein
  eigener Vermerk für „Vertretung lieferte, Gebiet hat keine Kalibrierung" nötig bleibt, hängt
  vom gewählten Lösungsweg ab (bei quellenabhängiger Leiter entfällt der Fall für FR).
- **AC-2 des Entwurfs bleibt sinnvoll**, aber getrennt: ein `None` ohne Spur ist auch nach dem
  Fix für jedes Gebiet ohne Kalibrierung möglich (`EU_REST` deckt geografisch alles ab, aber
  `region` kann `None` sein). Ob das in den Umfang gehört, entscheidet die Analyse.
- **Restrisiko Regression:** `_schwellen_fuer_reihe` gilt für **alle** Gebiete. Eine Änderung
  dort darf `DE_ALPEN` und `EU_REST` im Normalfall nicht verschieben — Mutations-Gegenprobe muss
  das gezielt angreifen.

---

## Analysis (Phase 2, 2026-09-09)

### Type

**Bug.** Eine per ADR-0047 beschlossene Wirkung tritt nicht ein; zusätzlich (s. Befund 1) eine
falsch berechnete Gewitterstufe in einem Alarm-Pfad.

### Befund 1 (NEU, größer als das Ticket): `DE_ALPEN` eskaliert im Vertretungsfall falsch

Derselbe Defekt wirkt für die Alpen mit umgekehrtem Vorzeichen — und dort **gefährlicher**,
weil er nicht ein Signal verschluckt, sondern ein falsch überhöhtes erzeugt.

`_VERTRETUNG` (`thunder_routing.py:178-187`) hat **zwei** Einträge auf dieselbe Ersatzquelle:
`fr_direct → eu_direct` und `de_direct → eu_direct`. `eu_direct` mappt `lpi_con_max` auf den
internen Signalnamen `"lpi"` (`dwd_eu.py:113-118`) — denselben, den `de_direct` für sein echtes
ICON-D2-`lpi` verwendet; beide landen über `_SIGNAL_ZU_FELD["lpi"]`
(`thunder_enrichment.py:37`) in derselben Spalte `lightning_potential_lpi_jkg`. Fällt
`de_direct` aus, wird der ICON-EU-Wert deshalb gegen die für ICON-**D2** kalibrierte
DE_ALPEN-Leiter `(1,0 / 30,0 / 50,0)` bewertet, obwohl die publizierte Nachweisschwelle dieser
Größe 7,14 ist (`model_registry.py:145-177`).

Praktische Fehlbereiche:

| Wert (J/kg) | heute (DE_ALPEN-Leiter) | korrekt (EU_REST-Leiter) | Folge |
|---|---|---|---|
| 1,0 – 7,14 | LOW | keine | Signal, wo keines sein dürfte |
| 50 – 86,16 | HIGH | MED | volle Stufen-Eskalation |

Das ist ein Alarm-Pfad. Der Befund gehört deshalb in den Umfang dieses Tickets: Er hat dieselbe
Ursache, dieselbe Codestelle und derselbe Fix behebt beide — getrennt zu liefern hieße, die
Ursache zweimal anzufassen.

### Befund 2: Entwurfs-AC-2 ist gegenstandslos

`EU_REST` ist als Weltrechteck definiert (`thunder_routing.py:76`,
`-90/90/-180/180`); der Docstring sagt selbst, `None` sei „strukturell unerreichbar, solange die
letzte Zeile des Rasters die ganze Welt abdeckt" (`thunder_routing.py:86-88`), und das Raster so
zu lassen ist ausdrücklich vorgeschrieben (`:58-63`). Für reale Koordinaten kann
`thunder_region_for()` also **nie** `None` liefern. Der Entwurfs-AC-2 („`lpi_thresholds_jkg`
liefert kein `None` ohne Spur") hätte damit nach dem Fix keinen erreichbaren Fall mehr — er
fällt aus dem Umfang, mit dieser Begründung statt stillschweigend.

### Befund 3: Kein bestehender Test fängt den Defekt — und keiner bricht am Fix

- `test_lpi_threshold_region_table.py` und `test_lpi_eu_rest_ladder.py` übergeben die drei
  Sprossen als **Literale** an die Fusion und rufen `lpi_thresholds_jkg()` nur isoliert auf. Sie
  berühren `_schwellen_fuer_reihe` nie — der Draht dorthin ist unbewacht.
- `test_thunder_enrichment_health_journal.py:195-241` durchläuft die echte
  `de_direct → eu_direct`-Vertretung, prüft aber nur das Journal und dass das **Rohfeld** gesetzt
  wird; `dp.thunder_level` wird dort nicht geprüft. `:414-465` und `:472ff.` lesen die Stufe zwar,
  vergleichen aber nur **zwei Läufe derselben Situation** miteinander — eine in beiden Läufen
  gleich falsche Leiterwahl bleibt grün.

Das ist erneut das bekannte Muster „der Wächter misst über einen Stellvertreter": geprüft wird,
dass ein Wert ankommt, nicht dass er richtig umgerechnet wird. Der RED-Test muss die
Vertretungssituation **bis `dp.thunder_level`** durchziehen und gegen den korrekt erwarteten Wert
prüfen — sinnvollerweise mit einem Wert im Bereich 50–86 J/kg, wo sich beide Leitern um eine
volle Stufe unterscheiden.

### Technischer Ansatz (Empfehlung)

**Die Blitzpotenzial-Leiter wird nach der liefernden Quelle geschlüsselt, nicht nach dem
Gebiet.** Physikalisch ist das die richtige Schlüsselung: Die Leiter beschreibt eine Eigenschaft
der **Größe** (`lpi` aus ICON-D2 vs. `lpi_con_max` aus ICON-EU), nicht des Ortes. Die heutige
Gebiets-Tabelle ist eine Abkürzung, die nur trägt, solange jede Region ihre Primärquelle behält —
genau diese Voraussetzung bricht die Vertretung.

Damit werden alle vier Fälle richtig, ohne neue Kalibrierung:

| Ort | liefernde Quelle | Leiter |
|---|---|---|
| FR (Korsika), Primär | `fr_direct` | keine (AROME liefert Dichte, kein LPI) — unverändert |
| FR (Korsika), Vertretung | `eu_direct` | EU_REST — **behebt #2263** |
| DE_ALPEN, Primär | `de_direct` | DE_ALPEN — unverändert |
| DE_ALPEN, Vertretung | `eu_direct` | EU_REST — **behebt Befund 1** |
| EU_REST, Primär | `eu_direct` | EU_REST — unverändert |

**Zwei Fallen, die der Fix umgehen muss:**

1. **Vokabular-Mismatch.** Ein Copy-paste des CAPE-Musters scheitert: `reihe.meta.fallback_model`
   trägt beim Gewitter-Fallback den **Provider**namen `"eu_direct"`
   (`thunder_enrichment.py:536-537`), keine normalisierte Modell-ID; `normalize_model_id()` kennt
   `"eu_direct"` nicht (`model_registry.py:38-47`). Naiv übernommen liefert die Auflösung wieder
   `None` — der Bug wäre nur gegen ein anderes Symptom getauscht.
2. **Kollision auf den Singular-Feldern.** `fallback_model`/`fallback_reason` können gleichzeitig
   vom Grundvorhersage-Fallback belegt sein (ADR-0047 Known Limitations Punkt 3;
   `effective_cape_model_id` liest genau dieses Feld). Die Vertretung ist deshalb an
   `fallback_metrics` zu erkennen — **so macht es der bereits gelieferte Vermerk in
   `fallback_notice.py` seit #1492 S2b.** Präzedenzfall im Repo, kein neuer Mechanismus.

**Form des Fixes (eindeutig, keine zweite Werte-Tabelle):** Die bestehende
`LPI_THRESHOLDS_JKG` bleibt der **einzige** Wertespeicher — die Sprossen werden nicht kopiert.
Neu ist allein eine schmale Übersetzung **liefernde Quelle → bestehender Kalibrierungs-Schlüssel**:

| Quelle | gelieferte Größe | Schlüssel |
|---|---|---|
| `de_direct` | `lpi` (ICON-D2) | `DE_ALPEN` |
| `eu_direct` | `lpi_con_max` (ICON-EU) | `EU_REST` |
| `fr_direct` | Blitzdichte, kein LPI | keiner |

`_schwellen_fuer_reihe` bestimmt den Schlüssel künftig aus der liefernden Quelle statt aus dem
Gebiet. Die Schlüsselnamen behalten ihre Werte und gewinnen ihre eigentliche Bedeutung zurück:
sie benennen die **Kalibrierung einer Größe**, nicht ein Gebiet. Signatur und Inhalt von
`lpi_thresholds_jkg()`/`LPI_THRESHOLDS_JKG` bleiben damit unverändert — deshalb bleiben die drei
Wächter grün, und `lpi_thresholds_jkg("FR") is None` bleibt wahr.

**Wie die Vertretung erkannt wird:** `fallback_metrics` trägt **Feldnamen**, keine
Quellennamen. Da jede Quelle laut ADR-0047 §2 höchstens **eine** Vertretung hat, ist die
Ersatzquelle eindeutig ableitbar: steht `lightning_potential_lpi_jkg` in `fallback_metrics`, ist
die liefernde Quelle `thunder_vertretung_for(primärquelle)`, sonst die Primärquelle selbst.
Kein Griff nach `fallback_model` — dort steht der Providername, und das Feld kann zugleich vom
Grundvorhersage-Fallback belegt sein.

**Ortsgebunden bleibt der Fix in `_schwellen_fuer_reihe` (`thunder_enrichment.py:279-304`).**
Signatur und Tabelle von `lpi_thresholds_jkg()` bleiben unangetastet — nur so bleiben die drei
Wächter zu Recht grün, und `lpi_thresholds_jkg("FR") is None` bleibt wahr. Diese Beschränkung
gehört ausdrücklich in die Spec: Wer stattdessen `reihe.meta` in `lpi_thresholds_jkg()`
hineinfädelt, bricht alle drei.

### AC-Gerüst für Phase 3 (Entwurf)

Die ACs müssen **konkrete Zahlen** tragen, sonst sind sie durch einen Test erfüllbar, der die
Schwellen als Literale übergibt — genau das Loch aus Befund 3. Der Bereich 50–86,16 J/kg trennt
die beiden Leitern um eine volle Stufe; Beispielwert **60 J/kg**.

1. **FR/Vertretung (das Ticket):** Korsika, `fr_direct` fällt aus, `eu_direct` liefert 60 J/kg →
   `dp.thunder_level` = MED (EU_REST-Leiter). Heute: keine Stufe aus diesem Signal.
2. **DE_ALPEN/Vertretung (Befund 1):** Alpen-Ort, `de_direct` fällt aus, `eu_direct` liefert
   60 J/kg → MED. Heute: HIGH (Fehleskalation über die ICON-D2-Leiter).
3. **DE_ALPEN/Primär unverändert:** `de_direct` liefert 60 J/kg → HIGH (ICON-D2-Leiter bleibt
   für die Primärquelle richtig).
4. **EU_REST/Primär unverändert:** `eu_direct` als reguläre Primärquelle → EU_REST-Leiter.
5. **FR/Primär unverändert (eigene AC, nicht als Nebensatz):** `fr_direct` liefert die
   Blitzdichte; es entsteht **kein** Blitzpotenzial-Signal, und `lpi_thresholds_jkg("FR")` bleibt
   `None`. Dies ist die Zusicherung, die eine quellenbezogene Umschreibung am ehesten still
   bricht — kein bestehender Test bewacht den Draht dorthin.

Entwurfs-AC-2 des Issues („kein `None` ohne Spur") entfällt mit der Begründung aus Befund 2.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/providers/thunder_enrichment.py` | MODIFY | `_schwellen_fuer_reihe`: Leiter nach liefernder Quelle auflösen (Vertretung an `fallback_metrics` erkennen) |
| `src/app/model_registry.py` | MODIFY | **nur** die neue Übersetzung Quelle → Kalibrierungs-Schlüssel; `LPI_THRESHOLDS_JKG` und `lpi_thresholds_jkg()` bleiben inhaltlich und in der Signatur unverändert |
| `tests/tdd/test_...` (neu) | CREATE | Vertretungsfall FR **und** DE_ALPEN bis `dp.thunder_level` |
| `docs/adr/00XX-...md` | CREATE | Fortschreibung von ADR-0047 (Schlüsselung der Leiter), Muster wie ADR-0058 zu 0018 |

### Scope Assessment

- Dateien: 4 (2 Code, 1 Test, 1 ADR)
- Geschätzt: ~70–110 LoC — unter dem 250er-Limit, keine Anhebung nötig
- Risiko: **MEDIUM–HIGH** — Alarm-Pfad, vier Kanäle

### Entscheidungsfläche / ADR-Pflicht

Der Fix stellt ADR-0047 §5 her, löst es nicht ab. Er ändert aber die in #1679 festgelegte
**Schlüsselung** der LPI-Leiter (Gebiet → Quelle). Das ist eine dokumentierte Entscheidung und
wird deshalb nicht still geändert: ein neues ADR schreibt 0047/0018 fort, analog zu ADR-0058.
Das ADR muss die Spec `feat_1679_lpi_schwellen_region_tabelle.md` **in der Schlüsselungs-Frage**
ausdrücklich als abgelöst benennen (ihre Werte und die FR-Aussparung bleiben gültig) — sonst
steht eine geänderte freigegebene AC ohne Zeiger da.

### Nebenbefund löst sich auf

Der im Kontext oben notierte irreführende Vertretungs-Vermerk („hier wurde ausgewichen", obwohl
der Wert die Stufe nicht beeinflusst hat) verschwindet mit dem Fix von selbst, weil der Wert die
Stufe dann tatsächlich trägt. **Kein eigenes Issue nötig.**

### Open Questions

Keine offenen technischen Fragen. Der PO-Eingriffspunkt ist die AC-Freigabe in Phase 3;
mitzuteilen ist dort, dass der Umfang um den DE_ALPEN-Fall (Befund 1) wächst und der
Entwurfs-AC-2 als gegenstandslos entfällt.

---

## Mutations-Zielpunkt für Phase 5 (festgehalten in Phase 4, PO-Freigabe 2026-09-09)

**AC-6 ist in der RED-Phase rot aus dem falschen Grund** — und das ist erwartet, kein Mangel.
Heute löst `_schwellen_fuer_reihe` die Leiter rein über `thunder_region_for()` auf; für den
Alpenpunkt scheitert AC-6 deshalb mit HIGH, genau wie AC-2. AC-6 ist vor dem Fix also ein
**Duplikat von AC-2**. Seine unterscheidende Kraft entsteht erst **nach** dem Fix.

**Daraus folgt eine Pflicht für die Mutations-Gegenprobe des Adversary in `/50-implement`:**

> Ersetze die `fallback_metrics`-Prüfung in `_schwellen_fuer_reihe` durch einen String-Vergleich
> `reihe.meta.fallback_model == "eu_direct"`. Erwartung: **AC-6 wird rot, AC-1 bis AC-5 bleiben
> grün.** Bleibt AC-6 dabei grün, ist AC-6 Dekoration und der Draht zu `fallback_metrics`
> unbewacht — das ist dann ein Finding.

Grund, warum der String-Vergleich überhaupt falsch ist: `_fetch_primaerquelle`
(`thunder_enrichment.py:536-538`) setzt `fallback_model` **nur, wenn das Feld noch unbesetzt
ist**. Ist es bereits vom Grundvorhersage-Fallback belegt (ADR-0047 Known Limitations 3), trägt
es niemals `"eu_direct"` — die Vertretung bliebe unerkannt.
