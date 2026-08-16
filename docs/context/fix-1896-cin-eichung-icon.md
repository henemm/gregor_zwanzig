# Context: fix-1896-cin-eichung-icon

Issue: [#1896](https://github.com/henemm/gregor_zwanzig/issues/1896) — „Gewitter: CIN-Baender fuer ICON
ungeeicht (US-MLCIN-100hPa-Werte auf 50-hPa-Mischschicht)"
Erstellt: 2026-08-16 · Track: Full Process (Intake-Summe 5)

## Request Summary

Die vier CIN-Baender, mit denen wir die aus CAPE abgeleitete Gewitterstufe daempfen, stammen aus
US-Vorhersagepraxis fuer **MLCIN ueber 100 hPa** (pseudoadiabatisch, negativ gezaehlt). Unsere CIN-Werte
kommen aber ausschliesslich aus **ICON** (DWD), das ueber **50 hPa** mischt, **reversibel** und **ohne
Entrainment** rechnet. Dieselbe Zahl bedeutet damit je Modell etwas anderes — dieselbe Fehlerklasse wie
ADR-0048 („CAPE != CAPE"), eine Ebene tiefer. Das Ticket soll die Baender fuer ICON eichen, und zwar
**vorrangig ueber publizierte Werte** (PO-Vorgabe 2026-08-16: keine Grundlagenforschung).

## Ist-Stand im Code (gemessen 2026-08-16)

`src/output/metric_format.py:325-376` — `_gedaempft_durch_cin(basis, cin_jkg)`:

| Bedingung (Code) | Zeile | Wirkung |
|---|---|---|
| `cin_jkg is None` | 368 | Notbremse: hoechstens `LOW` |
| `betrag < 25` | 370 | keine Daempfung |
| `betrag < 50` | 372 | genau eine Stufe herunter |
| `betrag <= 100` | 374 | Deckel auf `LOW` |
| sonst | 376 | `NONE` — CAPE traegt nichts bei |

🔴 **Praezisierung gegenueber dem Ticket-Text:** Der Code kennt **drei** Grenzen (25/50/100), nicht vier.
Die im Ticket und im Docstring genannte **200** kommt im Code nicht vor — sie stammt aus der
SPC-STP-Formel (`(mlCIN + 200)/150`) und ist dort nur die Belegquelle fuer „darueber kein Beitrag".
Zu eichen sind also **drei Zahlen**.

Die Werte sind **inline** verdrahtet, es gibt keine benannten Konstanten.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/metric_format.py:325-376` | die zu eichende Funktion, Schwellen inline |
| `src/output/metric_format.py:416` | einziger Aufrufer (`_signal_levels`), daempft das CAPE-Signal |
| `src/providers/thunder_enrichment.py:44,135,148,151` | Feldmapping `cin_ml` → `convective_inhibition_jkg`; Fusion |
| `src/providers/dwd.py:92,206,240` | ICON-D2 liefert `cin_ml` **positiv**; Sentinel `-999.9` → `None` |
| `src/providers/dwd_eu.py:70,97,117,267` | ICON-EU, identischer Filter, teilt die Sentinel-Konstante |
| `src/app/models.py:173` | `convective_inhibition_jkg: Optional[float]` |
| `scripts/eichung_cape_schwelle.py` | **wiederverwendbares Eichwerkzeug** aus #1592 (Historical Forecast API) |
| `src/app/model_registry.py` | Ablageort geeichter Tabellen (`CAPE_THRESHOLDS_JKG`) |
| `tests/tdd/test_cape_cin_pairing.py` | ~18 Tests, Bandgrenzen fest verdrahtet (u. a. `-24.9/-25.0/-49.9/-99.9/-100.0/-100.1`) |

## Datenlage: wer liefert ueberhaupt CIN?

| Provider | Modell | CIN |
|---|---|---|
| `dwd.py` | ICON-D2 | ja, `cin_ml`, positiver Betrag |
| `dwd_eu.py` | ICON-EU | ja, `cin_ml`, positiver Betrag |
| Meteo-France / AROME | AROME | **nein** — strukturell `None` → Notbremse `LOW` |

Daraus folgt ein wichtiger Zuschnitt-Vorteil gegenueber #1592: Die Eichung betrifft **nur ICON**, es gibt
kein Mehr-Modell-Problem. Sie betrifft aber **beide** ICON-Endpoints, und ob D2 und EU dieselben Baender
tragen duerfen, ist offen (ADR-0048 sagt: Schwellen nicht ueber Modellgrenzen tragen — D2 und EU sind
zwei Modelle).

Reale gemessene ICON-Werte im Repo: **7,29 J/kg** (ICON-D2, Karnischer Hoehenweg,
`tests/tdd/test_dwd_thunder_new_signals_fetch.py:31`), **104,47 J/kg** (ICON-EU, Abruzzen,
`tests/tdd/test_dwd_eu_thunder_energy_signals_fetch.py:17`). Auf **46 %** der ICON-D2-Gitterpunkte liefert
das Feld den Sentinel `-999.9` („kein Ausloesepunkt gefunden") — dort wirkt nicht die Eichung, sondern die
Notbremse.

## Existing Patterns

- **Beleg-Muster (#1679):** publizierte Werte uebernehmen, Quelle im Docstring + in der Spec-Dependencies-
  Tabelle + im Gesamtkonzept hinterlegen. Kein neuer ADR noetig, wenn ADR-0048 den Rahmen schon setzt.
- **Eich-Muster (#1592):** wenn nichts Publiziertes existiert — einmaliges Skript gegen die Open-Meteo
  Historical Forecast API, Konvektionssaison April–September, feste Referenzpunkte je Gebiet, Ergebnis als
  **statisches Literal** committen (kein Laufzeit-Abruf). Vorlage: `scripts/eichung_cape_schwelle.py`.
- **Daempfungs-Invariante (Gesamtkonzept 3.7, Rasmussen & Blanchard 1998):** CIN ist Ausloese-Filter, kein
  Schweremass — die Funktion darf **ausschliesslich daempfen, nie anheben**. Gilt unveraendert weiter.

## Dependencies

- **Upstream:** `dwd.py` / `dwd_eu.py` (Rohwert + Sentinel-Filter), `thunder_enrichment.py` (Fusion)
- **Downstream:** die fusionierte Gewitterstufe erreicht **alle vier Kanaele** —
  E-Mail (`renderers/email/html.py:210`), SMS (`sms_trip.py:321`, `narrow.py:212`,
  `compact_summary.py:599`), Trip-Report (`trip_report.py:588-684`), Ortsvergleich
  (`comparison.py:342`) — und darueber die Gewitteralarme.

## Existing Specs

| Spec | Inhalt |
|---|---|
| `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md` | fuehrt die CIN-Paarung ein, AC-1…AC-8, Belegtabelle Penn State/SPC |
| `docs/specs/modules/fix_1760_cin_vorzeichen.md` | Vorzeichen-Fix; Abschnitt „Known Limitations" Z. 97-107 haelt die fehlende ICON-Eichung fest — **die dieses Ticket abloest** |
| `docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md` | Abruf von `lpi_max` / `cin_ml` |
| `docs/features/gewitter-gesamtkonzept.md:308-450` (3.5/3.7) | bindender fachlicher Rahmen, nennt die Eckpunkte -25/-50/-100/-200 |
| `docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md` | „Feste Schwellen werden nie ueber Modellgrenzen getragen" |

## Risks & Considerations

1. **Der Ausgang haengt an der Literaturlage.** Findet die Recherche keine publizierten Baender fuer eine
   ICON-artige CIN-Definition, ist die Alternative eine eigene Eichung — deutlich groesserer Zuschnitt.
   Die Entscheidung darueber gehoert vor die Spec, nicht in sie.
2. **Perzentil-Eichung passt fuer CIN nicht ohne Weiteres.** #1592 eichte CAPE ueber das 95. Perzentil, weil
   CAPE ein Schweremass ist. CIN ist ein Filter — ein Perzentil-Ansatz muesste die US-Baender ueber
   **gleiche Ueberschreitungshaeufigkeit** in die ICON-Welt uebersetzen und braucht dafuer eine
   Referenzverteilung in der US-Definition (Kandidat: GFS ueber dieselbe API).
3. **Erreichbarkeit vor Schwere.** Vor jeder Zahlendiskussion ist zur Laufzeit zu belegen, dass
   `_gedaempft_durch_cin` mit echten ICON-Werten ueberhaupt feuert (nach #1760 sollte es, aber #1488 hat
   gezeigt, dass „im Code vorhanden" nicht „wirksam" heisst). Positivkontrolle noetig.
4. **Bestandstests sind auf die alten Grenzen geeicht.** `test_cape_cin_pairing.py` prueft Werte dicht an
   25/50/100. Neue Baender machen diese Tests rot. Regel: **Messwert neu verankern, nicht die Erwartung
   abschwaechen** (Lehre aus #1678).
5. **Beide ICON-Endpoints.** Ob ICON-D2 und ICON-EU dieselben Baender tragen duerfen, ist nach ADR-0048
   begruendungspflichtig, nicht selbstverstaendlich.
6. **Nutzersichtbare Wirkung.** Andere Baender verschieben Gewitterstufen auf allen vier Kanaelen und damit
   das Alarmverhalten. Die Richtung der Verschiebung (mehr oder weniger Daempfung) muss vor der Freigabe
   beziffert sein.

## Analysis (Phase 2, 2026-08-16)

### Type

Feature (Feineichung einer belegten Schwelle) — kein Bug. Das heutige Verhalten ist nicht defekt, es ist
**schlechter belegt als moeglich**.

### Befund 1 — Literatur: kein exakter Treffer, aber ein besserer Beleg

Vollstaendiger Rechercheverlauf inklusive Ausschlussliste: Scratchpad `cin-literatur.md`.

| Fund | CIN-Definition | Trifft ICON? |
|---|---|---|
| **ECMWF TM 852 (Groenemeijer, Pucik, Tsonevsky, Bechtold 2019, ESSL)** — Hemmung markiert ab **50 J/kg**, Kontur „starker Deckel" bei **100 J/kg** | MLCIN ueber **50 hPa**, pseudoadiabatisch, ohne Entrainment | Mischschichttiefe **ja**, Entrainment **ja**, Adiabatik **nein** (2 von 3) |
| heutige Baender 25/50/100 (Penn State/COMET, SPC) | MLCIN ueber **100 hPa**, pseudoadiabatisch | Mischschichttiefe **nein**, Adiabatik **nein** (1 von 3) |
| DWD-Glossar „>100 = starker Deckel" | Definition nicht genannt | **kein Beleg** — Publikumserklaerung ohne Parzelangabe |
| Thompson et al. 2007, CIN <= 250 (Effective Inflow Layer) | US-Konvention, pseudoadiabatisch | **nein** |

Ausdruecklich geprueft und ausgeschlossen: Huntrieser et al. 1997 (ICONs eigene Quelle — belegt nur die
50-hPa-Wahl, keine Schwellen), Pucik et al. 2015 (rechnet gar kein CIN), Taszarek et al. 2021 ERA5
(behandelt CIN nicht), DWD-ICON-D2-Datenbankbeschreibung (nur GRIB-Feldname), ECMWF-Confluence
(deckungsgleich mit TM852).

**Richtung der Restabweichung, belegt:** reversibel gerechnete CIN ist betragsmaessig **groesser** als
pseudoadiabatische (TM852 Abschnitt 4.3.3 qualitativ; Murdzek et al. 2021, J. Atmos. Sci. 78(10),
quantitativ: Differenzen > 100 J/kg im Realfall, bis ~5x in Idealsimulation, fallabhaengig bis „fast
identisch"). **Kein fester Umrechnungsfaktor.** Folge: TM852-Werte 1:1 auf ICON angewandt daempfen
tendenziell **zu frueh**.

**Richtung der Mischschichttiefe auf CIN: unbelegt.** Fuer CAPE dreifach institutionell belegt („je tiefer
die Mischschicht, desto weniger CAPE"), fuer CIN sagt keine dieser Quellen etwas; die einzigen Fundstellen
sind zwei einander widersprechende Blogs. Die **Netto**-Richtung gegenueber den heutigen Werten ist damit
unbestimmt — nicht „hebt sich auf", sondern schlicht offen.

🔴 **Einzelbeleg-Risiko:** Die Aussage „ICON rechnet CIN reversibel" — Grundlage des gesamten Tickets —
stuetzt sich allein auf **TM852 Table 1**. Der ICON-Quellcode ist oeffentlich nicht auffindbar, die
COSMO-Physikdoku enthaelt zu CAPE_ML/CIN_ML nichts. Das ist tragfaehig, muss aber als Einzelbeleg
dokumentiert werden.

### Befund 2 — Eigene Eichung ist derzeit nicht durchfuehrbar

Vollstaendige Messung: Scratchpad `cin-messung.md`.

Die Open-Meteo Historical Forecast API liefert `convective_inhibition` fuer `icon_d2`/`icon_eu` **erst ab
2026-06-26/27** (Binaersuche); davor durchgaengig `null`. Gegenprobe: fuer Mai 2025 lieferte `cape` im
selben Abruf 336/336 Stunden, `cin` 0/336 — das Feld fehlt selektiv im Archiv, nicht der Abruf. Die
Repo-Fixtures (`tests/fixtures/dwd/*cin_ml*`) sind zwei Einzelzeitschritte ohne Zeitreihe.

**Konsequenz:** Eine Saison-Klimatologie nach dem #1592-Muster ist fruehestens nach der Konvektionssaison
2027 moeglich. Der im Ticket vorgesehene Fallback „notfalls eigene Eichung" faellt fuer diesen Durchgang
aus. Publizierte Werte zu uebernehmen ist nicht nur PO-Vorgabe, sondern die einzige heute machbare Option.

Nebenbefund: Open-Meteo liefert `convective_inhibition` bereits als **Betrag** (Sentinel exakt `-1000.0`),
unser Produktivpfad nutzt dagegen den DWD-Direktabruf. Gleiches Modell, gleiche Definition — die Messung
ist damit repraesentativ, aber nicht bitgleich unsere Datenquelle.

### Befund 3 — Wirkungsmessung: alles haengt am 25er-Band

Ersatzfenster 2026-06-27 bis 2026-08-14 (49 Tage Hochsommer, **keine** Saison), Referenzpunkte aus
`scripts/eichung_cape_schwelle.py` plus Karnischer Hoehenweg, nur Stunden mit CAPE >= 1000 J/kg:

| Modell | n | keine Daempfung | −1 Stufe | Deckel LOW | CAPE ganz aus |
|---|---|---|---|---|---|
| ICON-D2 | 106 | 81,1 % | 15,1 % | 2,8 % | 0,9 % |
| ICON-EU | 315 | 78,7 % | 12,4 % | 7,9 % | 1,0 % |

Die Daempfung greift nur in rund einem Fuenftel der Gewitterstunden, und der Loewenanteil davon ist das
**25er-Band** — genau das Band, das in der ICON-nahen Quelle nicht existiert. Der **100er-Deckel steht in
beiden Quellenwelten** (US-Praxis wie ESSL) und ist damit der robusteste Punkt der Leiter. Das Band „CAPE
traegt gar nichts mehr bei" ist mit < 1 % praktisch bedeutungslos.

Einschraenkung: Einzelne Ort/Modell-Zellen haben nur 6–10 Konvektionsstunden; nur die gepoolten Werte
tragen eine Aussage. ICON-D2 deckt Korsika und Stockholm gitterbedingt nicht ab.

### Technical Approach (Empfehlung)

Die Baender auf die TM852-Semantik abbilden, **ohne eine Zahl zu erfinden**:

| CIN-Betrag | heute | neu | Beleg |
|---|---|---|---|
| < 50 | ab 25 gedaempft | keine Daempfung | TM852: Hemmung beginnt bei 50 |
| 50 – 100 | Deckel LOW | **eine Stufe herunter** | TM852: „hatched where CIN > 50" |
| > 100 | NONE | **hoechstens LOW** | TM852: Kontur „starker Deckel" bei 100 |
| — | — | **NONE entfaellt** | fuer die staerkste Daempfung existiert in der ICON-nahen Quelle kein Beleg |
| `None` | hoechstens LOW | **unveraendert** | Notbremse, nicht Teil der Eichung |

Diese Abbildung ist bewusst die **zurueckhaltendere Lesart**: Weil ICON reversibel rechnet und dadurch fuer
dieselbe Lage hoehere Zahlen liefert als die pseudoadiabatisch kalibrierten 50/100, wuerde eine
1:1-Uebernahme zu frueh daempfen. Indem 50 nur eine Stufe nimmt statt sofort auf LOW zu deckeln, wirkt die
**Struktur** dieser belegten Verzerrung entgegen — statt eines erfundenen Korrekturfaktors.

Erwartete Wirkung: Daempfung greift in 3,8 % (D2) bzw. 8,9 % (EU) der Gewitterstunden statt in 19 % / 21 %.
Weniger Daempfung heisst hoehere Gewitterstufe — die sichere Fehlerrichtung fuer ein Briefing, nach dem am
Berg ueber einen Passuebergang entschieden wird.

**Eine Leiter fuer beide ICON-Modelle** trotz ADR-0048: D2 und EU teilen denselben ICON-Code und damit
dieselbe CIN-Definition. Der gemessene Anteilsunterschied ist ein Gebiets-, kein Definitionsunterschied —
anders als bei CAPE, wo verschiedene Modellfamilien verschiedene Parzelvarianten rechnen. Diese Begruendung
gehoert in die Spec, weil ADR-0048 sie sonst verbietet.

### Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/output/metric_format.py` | MODIFY | drei Vergleiche in `_gedaempft_durch_cin`; Docstring auf TM852 umstellen, Known-Limitation-Absatz abloesen |
| `tests/tdd/test_cape_cin_pairing.py` | MODIFY | Bandgrenzen-Tests neu verankern (Messwerte **nicht** abschwaechen), Tests fuer den Wegfall des NONE-Bandes |
| `docs/features/gewitter-gesamtkonzept.md` | MODIFY | Abschnitte 3.5/3.7 auf die neue Belegquelle umstellen |
| `docs/specs/modules/fix_1760_cin_vorzeichen.md` | MODIFY | Known Limitation als abgeloest markieren (Verweis auf #1896) |
| `docs/specs/modules/fix_1896_cin_baender_icon.md` | CREATE | Spec dieses Tickets |

### Scope Assessment

- Dateien: 5 (davon 2 mit Produktiv-/Testcode)
- Geschaetztes LoC-Delta (nur zaehlende Dateien): **+150 / −80**, realistisch bis **~300** — der Nachweis
  kostet hier mehr als der Mechanismus (Regel: Nachweisaufwand doppelt ansetzen). Das **LoC-Limit 250 kann
  reissen**; falls ja, wird ein Override beim PO angefragt, nicht selbst gesetzt.
- Risiko: **MEDIUM** — kleiner Eingriff, aber nutzersichtbar auf allen vier Kanaelen und im Alarmverhalten

### Befund 4 — Erreichbarkeit zur Laufzeit belegt, aber gebietsabhaengig

Vollstaendiger Nachweis: Scratchpad `cin-erreichbarkeit.md` (Skripte und Rohausgaben daneben).

**Aufrufkette im Betrieb** (kein toter Code): `preview_service.py:169` `_build_report` — dieselbe Methode
wie der Versandpfad — → `trip_report_scheduler.py:1917` `_fetch_weather()` (auch `:694`/`:1286` im echten
Versand) → `segment_weather.py:195` → `openmeteo.py:1204` `_enrich_thunder()` → `thunder_enrichment.py`
→ `metric_format.py:416` → `_gedaempft_durch_cin()`.

**Positivkontrolle Karnischer Hoehenweg** (46.40 N / 12.52 O, DE_ALPEN → ICON-D2), echter Lauf:
`basis=MED, cin_jkg=26.07 -> ergebnis=LOW`. Ein echter ICON-Messwert daempft nachweislich eine Stufe.
**Gegenprobe** mit 5/40/80/500 J/kg: alle vier Baender liefern unterschiedliche Ergebnisse — der Nachweis
kann etwas zeigen.

**Negativkontrolle GR20/Korsika** (FR → `fr_direct`/Meteo-France): 0 von 72 Datenpunkten mit CIN, 144 von
144 Aufrufen mit `cin_jkg=None`. `meteofrance.py` fuehrt kein `cin_ml` (grep: 0 Treffer) und faellt auf
einen Sammelpfad zurueck, der nur die Blitzdichte fuellt.

🔴 **Zwei Reichweiten-Aussagen, die den Nutzen des Tickets begrenzen:**

1. **Auf dem GR20 wirkt die Eichung gar nicht.** Dort greift ausschliesslich die von den Baendern
   unabhaengige Notbremse „hoechstens LOW". Die Eichung wirkt auf dem Karnischen Hoehenweg und im
   ICON-EU-Gebiet.
2. **Auch im ICON-Gebiet ist CIN oft gar nicht da:** am Karnischen Hoehenweg **13 von 72** Datenpunkten mit
   echtem Wert. In den uebrigen ~82 % greift ebenfalls die Notbremse. Die Notbremse deckelt damit **haeufiger**
   als saemtliche Baender zusammen — sie ist aber nicht Gegenstand dieses Tickets (siehe Open Questions).

Nebenbefund ohne Produktionsfehler: ein erster Messlauf zeigte faelschlich CIN fuer Korsika, weil ohne
geladene `.env` der Meteo-France-Schluessel fehlte, der Abruf mit 401 scheiterte und die ADR-0047-Vertretung
(`fr_direct` → `eu_direct`) einsprang. Die Vertretung funktioniert also — sie darf nur nicht als „Korsika
bekommt manchmal CIN" missverstanden werden.

### Open Questions

- [x] Erreichbarkeit belegt (Befund 4)
- [ ] Soll die heute unmoegliche echte ICON-Klimatologie-Eichung als Folge-Issue mit Pruefdatum
      (Konvektionssaison 2027) angelegt werden? — PO-Entscheidung
- [ ] Die Notbremse „CIN unbekannt ⇒ hoechstens LOW" greift in ~82 % der Stunden am Karnischen Hoehenweg
      und zu 100 % auf dem GR20 — deutlich haeufiger als jedes Band. Ist der pauschale Deckel bei
      **unbekannter** Hemmung in dieser Haeufigkeit noch gewollt? Eigenes Ticket, nicht Teil von #1896. —
      PO-Entscheidung

## Next

`/30-write-spec` — Baender werden dort per ACs zur Freigabe vorgelegt.
