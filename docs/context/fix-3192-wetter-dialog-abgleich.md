# Context: fix-3192-wetter-dialog-abgleich

## Request Summary
Issue #3192 (Kind von Epic #2913, abgespalten aus #3111): Der Staging-Elementlisten-Abgleich misst die
Wetter-Dialoge (Grenzen ändern, Vorlage-Auswahl/-Bestätigung/-Speichern) auf einem eigenen Prüf-Datensatz
statt auf der Mockup-Datenlage; 56 der 156 `#3111`-Besitzer-Einträge bleiben deshalb „nicht gefunden“.
Datensatz/Bedienplan an die Mockup-Lage anpassen, danach die 156 `#3111`-Besitzer abräumen (inkl.
EN-Zuordnung der neuen Katalogtexte). Zusätzlich #3111-Adversary F004 (LOW): Browser-Nachweis, dass eine
frisch gespeicherte eigene Vorlage ohne Neuladen „eigene · <Beschreibung>“ zeigt.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | Z.110-132 `sichtbareTexte` (liest Platzhalter nur von `HTMLInputElement`, nicht `<textarea>`); Z.227-282 `WETTER_VORLAGE='allgemein'`, `wetterPruefDaten` (Trip + Vergleich mit genau 1 Ort, keine Grenzen-Overrides, keine eigene Vorlage); Z.418 `lage.aktiveVorlage=WETTER_VORLAGE`; Z.449-466 Bedien-Abschnitte je mit frischer Seite (`seiteLaden(seitenId)`) |
| `frontend/e2e/elementliste_abgleich_logik.ts` | Z.395-445 `bedienPlan` (Bestätigung wählt erste Vorlage ≠ aktiv aus `lage.vorlagen` → „Alpen-Trekking“ statt Mockup „Wandern“), `ordneAbschnitte`, `wetterPruefMetriken` |
| `docs/context/einstellungen_neu/elementliste.json` | Soll-Einträge aus Mockup Fassung 4; die #3111-Texte haben überwiegend `text_en: null` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | 156 Einträge Verweis `#3111` (je trip/orte × normal/luecken: grenzen-* , vorlage-auswahl 9, -bestaetigung 2, -speichern 4) |
| `tests/test_2913_c2_besitzerliste.py:126` | Zählwächter `soll = {..., "#3111": 156}` |
| `frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts:40-73` | Pin AC-3 „Bisherige 2646 Einträge unverändert, Mockup-Hash unverändert“ (Prüfsumme) — bricht beim Neu-Erzeugen |
| `scripts/elementliste_aus_mockup.ts` | Erzeugt `elementliste.json` aus dem Mockup inkl. `text_en` |
| `frontend/src/lib/**/elementliste_en_zuordnung_2968.test.ts` | wird rot (94 EN-Lücken ohne Besitzer), sobald die #3111-Besitzer entfallen |
| `scripts/staging_pruefkonto_mockupdaten.py` (#2967, zu) | Seed des Prüfkontos: Trip „GR221 Mallorca“ mit `ampel.template=alpen-trekking` (nur enabled-Flags, keine Grenzen-Overrides), eigene Vorlage „Mallorca Frühling“ (kind route, description „aus GR221 gespeichert“), Vergleich „Münsterland“ mit 3 Orten, `ampel.template=allgemein` |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:231` | `grenzenAbweichend(id)`: Abweichend-Satz nur, wenn Override-Menge `lower`/`upper` (bzw. Gewitter `thunder`) enthält |
| `frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts:91-117` | `standAusAbo` liest `display_config.ampel` (template + metrics-Overrides), `mengeVon` = Abweichungsmenge |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts:84-120` | eigene Vorlagen (`/api/metric-presets`, gefiltert nach kind), Beschreibung, `ortAnzahlVon` |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | Z.460/465: Abweichend-Satz im Grenzen-Dialog STATISCH (immer); Z.486-488: Bestätigung mit Verlust-Satz nur bei `devs>0` (Ausgangslage devs=0) |
| `docs/specs/modules/feat_3111_wetter_dialoge_mockup.md` | AC-2: Abweichend-Satz nur bei echter Abweichung; AC-6: Bestätigung „dieses Trips“/„für diesen Ort“/„für diese Orte“, Verlust-Satz bei Abweichungen; Z.150-151 bewusste Abweichungen (#3190 Speichern-Dialog, #3151 Beispielzahlen) |

## Existing Patterns
- Bedien-Abschnitte laden je eine frische Seite (`seiteLaden(seitenId)`) → pro Abschnitt kann ein anderer Datensatz/eine andere Seiten-ID genutzt werden, ohne Wechselwirkung.
- Prüf-Datensatz wird im Test angelegt und im `finally` aufgeräumt (`aufraeumen`); Reste eines abgebrochenen Laufs vorher löschen.
- Besitzer-Abräumung: nach Staging-Abgleichslauf Einträge entfernen, Zählwächter im selben Commit anpassen; Restabweichungen begründet an ein anderes Issue umhängen (#2966 AC-10-Muster).
- Pin-Erneuerung bei Neu-Erzeugung der Elementliste: Erzeugung und Pin gemeinsam nachziehen.

## Dependencies
- Upstream: Go-API `/api/trips`, `/api/compare/presets`, `/api/locations`, `/api/metric-presets`, `/api/templates`; Systemvorlagen (Alpen-Trekking, Wandern, Allgemein …); Mockup Fassung 4.
- Downstream: Abnahme #3009 (Epic #2913) liest den Abgleichsbericht; Zählwächter und EN-Zuordnungstest.

## Existing Specs
- `docs/specs/modules/feat_3111_wetter_dialoge_mockup.md` (Soll der Dialoge)
- `docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md` (Prüfkonto-Seed)
- `docs/specs/modules/feat_2968_elementliste_en_zuordnung.md` (EN-Zuordnung)
- `docs/context/feat-2966-abgleich-haken.md` (Bedienplan-Herkunft)

## Risks & Considerations
- **Mockup in sich widersprüchlich:** Grenzen-Dialog zeigt „Abweichend …“ immer (statisch), Bestätigung zeigt keinen Verlust-Satz (devs=0). Live (AC-2/AC-6 freigegeben) koppelt beides an echte Abweichungen. Ein einziger Datensatz kann nicht beide Mockup-Texte erzeugen → Grenzen-Abschnitte auf Datensatz MIT Overrides (je Briefing-Metrik), Bestätigung auf Datensatz OHNE Overrides messen (Seiten-ID je Abschnitt).
- **Mockup-Lage je Kontext:** Trip aktiv „Alpen-Trekking“, Bestätigung „Wandern“; Orte aktiv „Allgemein“, Bestätigung „Alpen-Trekking“, „für diese Orte“ (≥2 Orte); eigene Vorlage „eigene · aus GR221 gespeichert“ in BEIDEN Listen (Seed hat sie nur als kind route).
- Vorlagen-Unterzeilen „N Metriken · Stichworte“: Zahl aus Daten (bewusste Abweichung #3151) → solche Einträge ggf. an #3151 umhängen statt abräumen.
- Speichern-Dialog: Textarea-Platzhalter (4 Einträge, #3190) und Herkunftszeile (2, #3189) gehören nicht hierher.
- EN: Neu-Erzeugen der Elementliste füllt `text_en`, bricht Pin 2646 (AC-3 #2969) — Pin bewusst mit Begründung nachziehen.
- Abgleich läuft nur gegen Staging (Live-E2E-Schicht); Prüfkonto-Daten dürfen nicht dauerhaft verändert werden (Prüf-Datensätze anlegen und wieder aufräumen; GR221-Seed nicht anfassen).
- F004: frisch gespeicherte eigene Vorlage — Browser-Test speichert wirklich (schreibend), muss eigenen Datensatz/Aufräumen haben und darf nicht im lesenden Abgleich laufen (Abgleich wertet Schreib-Anfragen als Fehlschlag, #2966 AC-7).

## Analysis

### Type
Feature (Prüfwerkzeug: Abgleich-Datensatz und Bedienplan an Mockup-Lage angleichen); kein Produktcode.

### Fakten (Explore, 20.11.)
- Overrides: `ampel.metrics[id].lower = {red, orange, yellow}` (aufsteigend), `upper = {yellow, orange, red}` (aufsteigend), lower ≤ upper (`src/app/ampel.py:27-90`); Gewitter `ampel.thunder = {mittel, hoch}` (hoch nie gelb, ≥ mittel). Abweichung = gesetzter `lower`/`upper` bzw. `thunder` (`WetterTabInhalt.svelte:231`).
- Vorbild-Anlage mit Overrides: `frontend/e2e/s3a2794-teil3.helpers.ts:136-160` (`seedWetter`), `s3a2794-teil3-gewitter.spec.ts:58`.
- Systemvorlagen-Reihenfolge `/api/templates`: alpen-trekking, wandern, skitouren, wintersport, radtour, wassersport, allgemein (`src/app/metric_catalog.py:1441-1520`).
- `wetterPruefMetriken` (logik.ts:517-520): trip 13 Metriken (temperature, temperature_night, wind_chill, wind, gust, precipitation, thunder, rain_probability, visibility, cloud_low, uv_index, freezing_level, snowfall_limit), orte 8 (temperature, wind, gust, precipitation, thunder, rain_probability, cloud_total, sunshine).
- Unit-Tests Bedienplan: `frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts` (bedienPlan Z.52-152, ordneAbschnitte Z.235-247); Verdrahtung `elementliste_abgleich_verdrahtung.test.ts:493-503`.
- Eigene Vorlage: `POST /api/metric-presets` `{name, description, kind: route|vergleich, ampel?, metrics}`; 409 bei doppeltem Namen je Art (`internal/handler/metric_preset.go`).
- Pin 2969 AC-3: `ALT_ANZAHL=2646`, `ALT_SHA` (sha256 über alle Nicht-Übersicht-Einträge), `MOCKUP_HASH`. Neu-Erzeugung mit `text_en` ändert nur ALT_SHA → mit Begründung nachziehen. EN-Lückentest `elementliste_en_zuordnung_2968.test.ts:292-318` (Lücken ≤ 352, jede Lücke mit Besitzer ≠ #2968).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/e2e/elementliste-abgleich.staging.spec.ts | MODIFY | Wetter-Prüf-Datensatz je Kontext zweifach: „mit Abweichung“ (Overrides je Briefing-Metrik inkl. Gewitter) für `grenzen-*`, „ohne Abweichung“ für Vorlage-Abschnitte; aktive Vorlage Trip `alpen-trekking`, Orte `allgemein`; Vergleich mit ≥2 Orten; eigene Vorlage je Art mit Beschreibung „aus GR221 gespeichert“ (anlegen + aufräumen); Seiten-ID je Abschnitt; `sichtbareTexte` liest auch `<textarea>`-Platzhalter |
| frontend/e2e/elementliste_abgleich_logik.ts | MODIFY | `BedienLage` um Mockup-Ziel der Wechsel-Frage je Kontext (trip → `wandern`, orte → `alpen-trekking`) und Datensatz-Wahl je Abschnitt erweitern; Fallback „erste andere Vorlage“ bleibt |
| frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts | MODIFY | RED-Tests: Wechselziel je Kontext, Datensatzwahl je Abschnitt, Override-Bau gültig (lower/upper aufsteigend) |
| docs/context/einstellungen_neu/elementliste.json | MODIFY | Neu erzeugt (`scripts/elementliste_aus_mockup.ts`) → `text_en` der #3111-Texte |
| frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts | MODIFY | `ALT_SHA` mit Begründung (#3192, EN-Befüllung) nachziehen |
| docs/context/einstellungen_neu/elementliste_besitzer.json | MODIFY | #3111-Einträge nach Staging-Lauf: gefundene entfernen, Rest begründet umhängen (#3151 Beispielzahlen, #3189 Herkunftszeile, #3190 Speichern-Dialog) |
| tests/test_2913_c2_besitzerliste.py | MODIFY | Zählwächter `#3111` → 0, Zielzahlen der umgehängten Verweise |
| frontend/e2e/s3a2794-teil3-vorlage.spec.ts (o. ä.) | MODIFY | F004: frisch gespeicherte eigene Vorlage mit Beschreibung zeigt ohne Neuladen „eigene · <Beschreibung>“ |

### Scope Assessment
- Files: 7-8
- Estimated LoC: +200/-60 (ohne generierte JSON-Dateien)
- Risk Level: LOW-MEDIUM (nur Prüfwerkzeug und Testdaten; Produktcode unverändert; Staging-Daten werden je Lauf angelegt und aufgeräumt)

### Technical Approach
1. **Zwei Datensätze je Kontext** (Mockup ist widersprüchlich: Abweichend-Satz statisch, Bestätigung ohne Verlust-Satz). „mit Abweichung“: je Briefing-Metrik ein gültiger Override (Seite nach `allowed_sides`; Gewitter `thunder`), misst `grenzen-*`. „ohne Abweichung“: nur Vorlage + Metrik-Auswahl, misst `vorlage-auswahl`, `vorlage-bestaetigung`, `vorlage-speichern(-fehler)`. Jeder Bedien-Abschnitt lädt ohnehin eine frische Seite — Seiten-ID wird je Abschnitt gewählt (reine Funktion in der Logik, unit-getestet).
2. **Mockup-Lage:** Trip aktiv `alpen-trekking`, Wechselziel `wandern`; Orte aktiv `allgemein`, Wechselziel `alpen-trekking`, Vergleich mit 3 Orten („für diese Orte“). Ziel fehlt in der API-Liste ⇒ `nicht_herstellbar` mit Grund (nie still).
3. **Eigene Vorlage** „aus GR221 gespeichert“ je Art anlegen (eindeutiger Prüf-Name, Reste vorher löschen, im finally aufräumen).
4. **Lesefehler** `<textarea>`-Platzhalter beheben (Messinstrument).
5. **EN:** Elementliste neu erzeugen, Pin-SHA mit Begründung nachziehen.
6. **Staging-Abgleich** (DE und EN) lokal gegen Staging laufen lassen (Staging trägt #3111 bereits), danach Besitzer abräumen/umhängen und Zählwächter anpassen.
7. **F004** als eigener schreibender Browser-Test (nicht im lesenden Abgleich, der Schreibanfragen als Fehlschlag wertet).

### Dependencies
- Staging trägt den #3111-Stand; Prüfkonto-Zugang aus der Staging-`.env`; Seed #2967 (GR221) bleibt unberührt.

### Open Questions
- keine (Produktsoll steht in Spec #3111 und im Mockup; technische Wahl Tech Lead)
