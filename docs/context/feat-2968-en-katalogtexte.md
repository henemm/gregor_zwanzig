# Context: feat-2968-en-katalogtexte (#2968)

## Request Summary
Die Elementliste (Soll-Liste aus dem Mockup) hat für viele Einträge keinen englischen Text. Im EN-Abgleich
erscheinen sie als `nicht_pruefbar` („EN-Lücke: kein Katalogtext“), ihre englischen Live-Texte zusätzlich als
`zusaetzlich`. Ziel: EN-Texte aus dem i18n-Katalog ergänzen, sodass EN- und DE-Lauf dieselbe Prüftiefe haben.

## Ist-Stand (gemessen 2026-11-19)
- Eingecheckte Liste: 2646 Elemente, **1190 Lücken** (Issue nannte ~500 vom Staging-Lauf 8a3b3c7).
- Nur Neu-Erzeugen (Katalog ist seitdem gewachsen): **1022 Lücken**. Die eingecheckte Liste ist also veraltet.
- Je Zustand dupliziert (normal/luecken/laedt/fehler): im Zustand `normal` 440 Lücken.
- Verteilung (normal): `was-steht-wo` 143, `grenzen-*` ~150, `metriken` 38, `vorlage-*` 30, `test-menue` 14,
  `kopf` 8, `kanaele` 8, `kebab-*` 14, `etappen/tempo` 8, `etappen/liste` 4, `orte/liste` 6, Rest Einzelne.

## Lücken-Klassen (aus den Texten abgeleitet)
1. **Zusammengesetzte Muster, die der Generator nicht auflöst** — Katalog hat das Muster, aber Wortlaut zu kurz
   (Mindest-Wortlaut 4 Zeichen und ≥ halbe Textlänge) oder verschachtelt:
   „Bewölkung in Telegram“, „UV-Index in E-Mail“ (`{metrik} in …`), „Darstellung Böen in Telegram: Roh“
   (`bausteine.darstellung.name` = „Darstellung {name}: {form}“ mit `{name}` = zweites Muster),
   „Regenwahrscheinlichkeit im 3-Tages-Ausblick“ (`wetter.wsw.zelle.outlook`), „· grün: bis 30 km/h“,
   „°C · Vorbote, kein Alarm“, „12 Metriken · Wind, Regen, …“.
2. **Sprachneutrale Texte** — Zahlen/Grenzwerte („30“, „-15“, „60%“), Protokoll-Token der SMS-Vorschau
   („VS-“, „N10“, „SnowL 1820“, ganze SMS-Zeilen), Eigennamen und Kontodaten („Münster“, „GR221 Mallorca“,
   „@henning“, „+49 171 …“, „E1 · Port d'Andratx → Estellencs“). Laut `i18n_konventionen.md` §2 nie im Katalog
   und nie übersetzt ⇒ EN = DE, kein Katalogtext nötig; heute trotzdem als Lücke markiert.
3. **Mockup-Text ≠ App-Text / Textknoten zusammengezogen** — „obenzu viel“, „untenzu wenig“, „gelb >“,
   „Archivieren?“, „Uhrzeit Morgen“, Grenzen-Hinweis „Grün ist alles zwischen …“. Hier weicht entweder die
   Mockup-Struktur ab (zwei Spans ohne Leerzeichen) oder die App hat (noch) einen anderen Text. EN lässt sich
   nicht ohne Erfinden ableiten; Besitz liegt bei der jeweiligen Scheibe (#3012, #3111, #2796, #2913-e …).
4. **Texte ohne gebautes Pendant** — Tempo-Karte (#2796), Reiter Orte/Etappen neu (#2913-e). Katalogschlüssel
   ohne Verwender sind verboten (`katalog_schluessel_haben_verwender.test.ts`) ⇒ hier keine Katalog-Einträge
   auf Vorrat.

## Related Files
| File | Relevance |
|------|-----------|
| `scripts/elementliste_aus_mockup.ts` | Generator: `ermittleEn` (exakt → Muster → Lücke), `chipEn`, Mindest-Wortlaut-Regel, `{zahl}`-Muster |
| `docs/context/einstellungen_neu/elementliste.json` | erzeugtes Artefakt (Hash-Check `elementliste_aktuell.test.ts`) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | 451 Besitzer-Einträge mit Verweis #2968 (421 element, 25 zusaetzlich, 5 abschnitt) |
| `frontend/e2e/elementliste_abgleich_logik.ts` | `erwartung()` EN: `text_en` als RegExp, `null` ⇒ „EN-Lücke“; Gegenrichtung `findeZusaetzliche` |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | Katalog |
| `frontend/src/lib/__tests__/elementliste_en_schutz.test.ts` | Schutzregeln gegen erfundenes EN (AC-11 aus #2913) — dürfen nicht aufweichen |
| `frontend/src/lib/__tests__/elementliste_besitzer_kern.test.ts` | Kern-Test Besitzer-IDs (#3008) |
| `frontend/src/lib/__tests__/elementliste_aktuell.test.ts` | Hash Mockup ↔ Liste |
| `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | verbietet Schlüssel ohne Verwender |

## Existing Patterns
- Generator erfindet nie EN: nur exakter Katalogtreffer oder Platzhalter-Muster mit füllbaren EN-Platzhaltern.
- Platzhalter bleiben im EN-Muster stehen (#2913 Fix-Loop 2, C5); Abgleich liest sie als „beliebiger Wert“.
- #3011: `{metrik}` in der Gegenrichtung nur für bekannte Metriknamen — Vorbild für eine „bekannte Werte“-Liste.
- Chip-Sonderfall `chipEn` über Rolle statt Mindest-Wortlaut.

## Dependencies
- Upstream: Mockup `seiten/mockup-hub-fassung4.html`, i18n-Katalog, Playwright (Generator per `file://`).
- Downstream: Abgleich-Lauf (`elementliste-abgleich.staging.spec.ts`, `--sprache en`, `--abnahme`), Besitzerliste,
  Abnahme #3009 (DE+EN lückenlos).

## Existing Specs
- `docs/specs/modules/feat_2913_abgleich_ganzseite.md` (Abgleich, Besitzer, Ausnahmen)
- `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md` (Generator, AC-11 EN-Schutz)
- `docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md`

## Risks & Considerations
- Lockern der Schutzregeln erzeugt erfundenes EN (falsch-grüne Prüfung) — jede neue Auflösung braucht eine
  eng begrenzte Regel + Gegenbeispiel im Schutz-Test.
- Element-IDs hängen nicht von `text_en` ab (Hash über Identität) ⇒ Besitzer-IDs bleiben stabil; trotzdem
  `elementliste_besitzer_kern` grün halten.
- Nach dem Schließen von Lücken werden Besitzer-Einträge mit Verweis #2968 teils obsolet; verbleibende Lücken
  (Klasse 3/4) brauchen einen Besitzer, der nicht mehr #2968 heißt (Hauptbesitzer der Scheibe).
- Sprachneutral-Regel darf keine deutschen Wörter als „neutral“ durchwinken (nur Zahlen/Token/Eigennamen).
- Prüftiefe-Ziel „wie DE“ ist für Klasse 3/4 strukturell unerreichbar, solange DE dort selbst abweicht.

## Analysis

### Type
Feature (Prüfwerkzeug: Elementlisten-Generator), kein Produktcode.

### Kernbefund
Der englische Katalog ist **vollständig** (Paritätstest). Die Lücken entstehen nicht durch fehlende EN-Texte,
sondern weil der Generator den deutschen Mockup-Text keinem Katalogschlüssel zuordnen kann. Neue
Katalogschlüssel sind daher **nicht** der Weg (und ohne Verwender ohnehin verboten). Der Weg ist ein
genauerer Zuordner im Generator, plus Bereinigung der Besitzerliste.

Beleg je Lücken-Familie (Katalog hat den Text):
| Mockup-Text | Katalog | Warum heute Lücke |
|---|---|---|
| „Regenwahrscheinlichkeit in SMS“ | `wetter.wsw.zelle.sms` „{metrik} in SMS“ | Wortlaut „ in SMS“ < halbe Textlänge |
| „Darstellung Böen in Telegram: Roh“ | `bausteine.darstellung.name` „Darstellung {name}: {form}“, `{name}` = Zellen-Muster, `{form}` = Katalogwert | verschachtelt |
| „Regenwahrscheinlichkeit im 3-Tages-Ausblick“ | `wetter.wsw.zelle.outlook` | Wortlaut-Hälfte |
| „· grün: bis 30 km/h“ | `wetter.gruen.bis` „grün: bis {bis} {einheit}“ | führendes „· “ im Mockup-Knoten |
| „°C · Vorbote, kein Alarm“, „km/h · Mittelwind“, „mm · Summe“ | `wetter.untertitel.vorbote`, `wetter.hinweis.*` | Einheit + „ · “ + Katalogtext in einem Knoten |
| „12 Metriken · Wind, Regen, …“ | `…metriken.other` + Metriknamen | Segmente |
| „Briefings über 2 Kanäle · Alarme über 4 Kanäle“ | `zustellung.kanaele.kopf_*` (Plural) | zwei Segmente |
| „30“, „-15“, „60%“, „+49 171 …“ | – | sprachneutral (keine Buchstaben) |
| „VS-“, „N10“, SMS-Vorschauzeilen | – | Protokoll-Token, nie übersetzt (§2) |
| „Münster“, „GR221 Mallorca“, „E1 · Port d'Andratx → Estellencs“ | – | Eigennamen/Kontodaten |
| „obenzu viel“ vs. „oben / zu viel“, „Grün ist alles … „gelb unten““ (Anführungszeichen „“ vs ‚‘), „Uhrzeit Morgen“ vs „Uhrzeit Morgen-Briefing“, „Archivieren?“, Test-Alarm-Menü, Tempo-Karte | abweichend oder ungebaut | **echte Mockup≠App-Abweichung**, Besitz bei der Scheibe |

### Affected Files (with changes)
| File | Change Type | Description |
|---|---|---|
| `scripts/elementliste_aus_mockup.ts` | MODIFY | Zuordner: (a) Segmente an „ · “ einzeln auflösen, EN mit „ · “ verbinden; (b) Platzhalterwert darf selbst auflösbar sein (Katalogwert, Muster, bekannter Metrikname) — dann gilt die Wortlaut-Hälfte nicht; (c) führende Trenner „· “ abtrennen; (d) sprachneutrale Texte (ohne Buchstaben, Einheit allein, bekannte Protokoll-Token/Eigennamen) ⇒ `text_en` = DE-Muster, Kennzeichen `sprachneutral`, keine Lücke |
| `docs/context/einstellungen_neu/daten/metriknamen.json` | CREATE | Schnappschuss der DE-Metriknamen (und Kurz-Token) aus `src/app/metric_catalog.py` |
| `tests/test_2968_metriknamen_schnappschuss.py` | CREATE | Drift-Test Schnappschuss ↔ Metrik-Katalog |
| `frontend/src/lib/__tests__/elementliste_en_schutz.test.ts` | MODIFY | neue Fälle je Regel + Gegenbeispiele (kein erfundenes EN, deutsches Wort ist nie „sprachneutral“) |
| `docs/context/einstellungen_neu/elementliste.json` | REGENERATE | neu erzeugt |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | Verweise #2968 entfernen, wo die Lücke geschlossen ist; verbleibende echte Abweichungen auf die Scheibe umhängen |
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY (klein) | ggf. `sprachneutral` in `erwartung` (EN = DE-Muster) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Generator-Regeln dokumentieren |

### Scope Assessment
- Files: ~8, Estimated LoC: +250/-450 (Besitzerliste schrumpft)
- Risk Level: MEDIUM — reines Prüfwerkzeug, kein Nutzerpfad; Gefahr ist falsch-grüne EN-Prüfung durch zu lockere Zuordnung.

### Technical Approach
Zuordner rekursiv und eng: Ein Text gilt als aufgelöst, wenn er (1) exakt Katalogwert ist, (2) Muster ist,
dessen Platzhalterwerte jeder für sich aufgelöst sind (Katalogwert, bekannter Metrikname, Zahl/Einheit,
oder Teilmuster) — dann ohne Wortlaut-Hälfte, (3) aus „ · “-Segmenten besteht, die jedes für sich aufgelöst
sind, oder (4) sprachneutral ist. Nicht aufgelöste Texte bleiben Lücke, nichts wird erfunden.
EN bleibt Muster mit Platzhaltern (C5). Zielgröße: verbleibende Lücken = nur noch echte Mockup≠App-Abweichungen
und ungebaute Teile; jede trägt einen Besitzer der Scheibe, keiner mehr #2968.

### Dependencies
#3011 (bekannte Metriknamen in der Gegenrichtung), #2967 (Prüfkonto-Daten), #3009 (Abnahme DE+EN).

### Open Questions
- keine Produktfrage; Tech-Entscheidungen oben.

## Tech-Lead-Entscheidungen nach TDD RED (2026-11-19)
- Schnittstelle: `Bekannte = {metriknamen, token, eigennamen}`, `ladeBekannte(datenDir?)`, `ermittleEn(text, katalog, bekannte?)` (ohne 3. Param: `ladeBekannte()`), `EnErgebnis.sprachneutral?`.
- Schutzfall „°C · vor der Etappe“: „vor der Etappe“ steht exakt im Ist-Katalog (`wetter.hinweis.temperature_night`) ⇒ Segmenttreffer ist korrekt. Der bestehende Schutz-Test `elementliste_en_schutz.test.ts:22` wird in Phase 6 auf eine Katalogkopie ohne diesen Wert umgestellt; seine Zusicherung (nie über „{count} Etappe“) bleibt erhalten und wird zusätzlich im neuen Test mit Ist-Katalog geprüft.
- „Gewitter“ ist Katalogwert ⇒ Gegenbeispiel „Hagelschauer“ (deutsches Wort ohne Katalogtreffer).
- Lücken-Obergrenze im Test vorläufig 255, in Phase 6 auf den gemessenen Wert festschreiben.
- AC-10 (Ausgabe je Grund + Doku) wird in Phase 6 mit umgesetzt, Doku-Test als `# doc-compliance-test`.
