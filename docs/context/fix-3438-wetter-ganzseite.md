# Context: fix-3438-wetter-ganzseite (Issue #3438)

## Request Summary
Vier Bildprüfer-Befunde (Ganzseitenbild Reiter Wetter, Trip / Orte / ein Ort, 1280 und 390 px; Kommentar #3009 vom 26.11., Cluster 7) sollen je eine Zuordnung bekommen: Produkt ans Mockup angleichen ODER Mockup/Elementliste an eine belegte Produktentscheidung angleichen. Keine stille Duldung. Teil von Epic #2913, Vorbedingung der Abnahme #3009.

## Befund je Punkt (Ist-Stand und Beleglage)

### 1. Chips „Nicht im Briefing“ (Trip 8→11, Orte 10→15)
- Produkt: `briefingAngebot()` in `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts:296` — ALLE im Kontext ausgebbaren Katalog-Metriken, die nicht gewählt sind, in Gruppen-Reihenfolge (`zeilenGruppen`, dieselbe Ordnung wie die Metrik-Zeilen). Quelle: Spec `feat_2794_s3a_reiter_wetter.md` AC-19, Kontextkatalog-Test `nicht_im_briefing_kontextkatalog.test.ts`, #3047 (Einstellung = Mail-Prüfkatalog).
- Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`: handverlesene Listen `TRIP_OFF` (Z. 337, 7 Einträge) und `ORTE_OFF` (Z. 349, 9 Einträge) plus abgewählte Vorlagen-Metriken (`removed`, Z. 526). Reihenfolge willkürlich, nicht Gruppen-Ordnung.
- Bewertung: Produktregel belegt (jede Katalog-Metrik muss hinzufügbar sein). → Mockup-Listen an den echten Katalog in Gruppen-Reihenfolge angleichen (Werte vom Staging-Prüfkonto ablesen).

### 2. Hub-Kopf
- a) Stift am Titel + Namens-/Regionszeile mit Stift: `SubscriptionHeader.svelte` Z. 131–152. Belegt durch Spec `feat_2913_c2_seitenkopf.md` Nr. 5 und AC-9 („Name/Region bleiben inline bearbeitbar; Ruhezustand nur Stift-Icon mit aria-label“). Die Regionszeile zeigt die Region aber DOPPELT (sie steht schon im Eyebrow „Trip · Mallorca“). Mockup zeichnet weder Stift noch Regionszeile.
- b) Unterzeile „· Vergleichstabelle ·“: `routes/compare/[id]/+page.svelte:202` (`aktionen.kopf.vergleichstabelle`). Mockup Fassung 4 Meta: „3 Orte · Morgen-Briefing 07:00“. ADR-0124 Nr. 10 (Bereich heißt „Orte“, Mail-Tabelle „Übersicht“). Besitzer-JSON (`elementliste_besitzer.json` Z. 736 ff., 954) vermerkt bereits „Rückbau mit dem Bau zu #3122“ — #3122 ist zu, Rückbau nie erfolgt. → Produkt angleichen.
- c) Ein Ort ohne Oberzeile „ORTE · <Name>“: `+page.svelte:199` — ohne Region nur „Orte“ (Spec c2: „Ohne Region nur Orte, wie beim Trip“). Mockup `ort1.eyebrow='Orte · Tecklenburg'` (Region = Ortsname im Beispiel). Der Bildprüfer-Lauf (#3037) nutzte ein Wegwerf-Abo „WSW-3037-…“ OHNE Region. Zu klären auf Staging: steht „Orte“ allein da, oder fehlt die Zeile ganz.

### 3. Farbe „Test schicken ▾“
- Produkt `Btn variant="accent"` mit Fläche `--g-accent-deep` (#8c3e1a). Belegt: Spec c2 AC-16 / #2980, ADR-0118; Grund WCAG-AA (Mockup-Orange #c45a2a mit weißer 12-px-Schrift ≈ 4,3:1), Design-Leitprinzip „hoher Kontrast“ (PO 2026-05-25). Spec c2 nennt es „bewusste, dokumentierte Abweichung“.
- Mockup Z. 49: `.btn.accent{background:var(--g-accent)}`. → Mockup an Produktentscheidung angleichen (Knopf `--g-accent-deep`), dann ist es keine Abweichung mehr.

### 4. Ziehgriffe ⋮⋮ in „Was steht wo“
- Mockup Z. 721 zeichnet `<span class="h" … title="ziehen zum Umsortieren">⋮⋮</span>` in jeder Zeile, CSS Z. 214 (`--g-ink-4`, 12 px) bzw. Z. 240 (Handy 10 px, letter-spacing −2px). Die Griffe SIND im Mockup, nur sehr blass.
- Vermutung: Bildprüfer übersah die blassen Griffe. → Prüfen am Mockup-Bild; falls bestätigt: Befund „kein Abweichung“, Zuordnung mit Beleg (Mockup-Zeile). Ggf. Farbe/Größe des Produkt-Griffs mit Mockup vergleichen.

## Related Files
| Datei | Rolle |
|---|---|
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | Mockup (Z. 49 Knopf, 337/349 OFF-Listen, 405 Kopf, 526 Chips, 721 Griffe) |
| `docs/context/einstellungen_neu/elementliste.json` | aus Mockup erzeugt (`mockup_hash`!) — nach Mockup-Änderung neu erzeugen (`scripts/elementliste_aus_mockup.ts`) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | Besitzer/Ausnahmen (Vergleichstabelle-Einträge Z. 736–954) |
| `docs/context/einstellungen_neu/elementliste_freigaben.json` | Freigaben mit Spec-Stelle |
| `frontend/src/routes/compare/[id]/+page.svelte` | Eyebrow/Meta Orte |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | Kopf, Knopf-Farbe |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | Stift, Regionszeile |
| `frontend/src/lib/components/organisms/wetter-tab/NichtImBriefing.svelte`, `shared/wetter-tab/ampelModell.ts` | Chips |
| `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` | `aktionen.kopf.vergleichstabelle` |

## Existing Patterns
- Vorgänger #3437: Produkt angeglichen + Glossar/Spec nachgezogen + Elementlisten-Abgleich `--strict` mit Prüfkonto und Seed-IDs als Nachweis.
- Mockup-Änderung ⇒ `elementliste.json` neu erzeugen, `mockup_hash` aktuell (Hash-Wächter `pruefeHashAktuell`).

## Dependencies / Dependents
- Tests, die „Vergleichstabelle“ in der Meta erwarten: `hub_kopf_c2_mockup.test.ts`, `e2e/hub-kopf-c2-mockup.staging.spec.ts` (anpassen).
- Glossar `docs/reference/i18n_glossar.md`, Spec c2 AC-4 (Meta ohne „Vergleichstabelle“ nachziehen).

## Existing Specs
- `docs/specs/modules/feat_2913_c2_seitenkopf.md` (AC-4, AC-9, AC-16)
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` (AC-19)
- `docs/specs/modules/feat_2913_abgleich_ganzseite.md`
- ADR-0118, ADR-0124

## Risks
- Mockup-Änderung verschiebt `ordnung`-Werte/IDs der Elementliste → Besitzer-/Freigabe-Einträge mit IDs können verwaisen (Abgleich prüfen).
- Regionszeile entfernen würde Inline-Bearbeiten der Region verlieren (Spec c2 AC-9) — darf nicht still wegfallen.
- Prüfkonto-Seed (feste Region) vs. Wegwerf-Abo (ohne Region) unterscheiden sich beim Eyebrow.

## Analysis

**Type:** Feature/Angleichung (Ganzseiten-Abgleich, 4 Befunde), kein Bug im engeren Sinn.

### Zuordnung je Punkt (Tech-Lead-Vorschlag)
| # | Befund | Zuordnung | Änderung |
|---|---|---|---|
| 1 | Chips „Nicht im Briefing“ | Produktregel belegt (jede ausgebbare Katalog-Metrik hinzufügbar, Gruppen-Reihenfolge; #2794 AC-19, #3047) | **Mockup** `TRIP_OFF`/`ORTE_OFF` an echte Staging-Liste (Prüfkonto) in Produkt-Reihenfolge angleichen; Elementliste neu erzeugen |
| 2a | Stift am Titel, Regionszeile mit Stift | Inline-Bearbeiten belegt (Spec c2 Nr. 5, AC-9). Doppelte Region (Eyebrow + eigene Zeile) ist nicht belegt | **Produkt:** eigene Regionszeile entfällt, Region-Stift wandert an den Eyebrow („Trip · Mallorca ✎“); **Mockup:** zeichnet Stift am Titel und am Eyebrow (blass, wie Produkt) |
| 2b | „· Vergleichstabelle ·“ | Mockup F4 + ADR-0124 Nr. 10; Rückbau war für #3122 vermerkt, nie erfolgt | **Produkt:** Meta Orte „N Orte · Morgen-Briefing HH:MM“; Katalogschlüssel `aktionen.kopf.vergleichstabelle` entfernen (falls sonst ungenutzt); Tests/Spec c2 AC-4/Glossar/Besitzer-Einträge nachziehen |
| 2c | ein Ort ohne „ORTE · <Name>“ | Regel „Orte · Region, ohne Region nur Orte“ (Spec c2) belegt; Bildprüfer-Abo hatte keine Region | Keine Produktänderung; Beleg per Staging-Messung (Eyebrow „Orte“ vorhanden) |
| 3 | Knopffarbe | Bewusste Abweichung `--g-accent-deep` (Spec c2 AC-16, #2980, ADR-0118, WCAG-AA) | **Mockup** `#testBtn`/`.btn.accent` im Kopf → `--g-accent-deep` |
| 4 | Ziehgriffe | Mockup Z. 721 zeichnet ⋮⋮ (blass, `--g-ink-4`) | Keine Abweichung, nur Beleg; ggf. Produkt-Griff-Optik an Mockup angleichen (Messung abwarten) |

**Affected Files:** Mockup (MODIFY), `elementliste.json` (REGENERATE), `elementliste_besitzer.json` (MODIFY: Vergleichstabelle-Einträge, Stift-Ausnahmen), `SubscriptionHeader.svelte` (MODIFY), `HubKopf.svelte` (ggf.), `routes/compare/[id]/+page.svelte` (MODIFY), `aktionen.json` de/en (MODIFY), Tests `hub_kopf_c2_mockup.test.ts`, `f9KatalogAnker.ts`, `e2e/hub-kopf-c2-mockup.staging.spec.ts` (MODIFY), Spec c2 + Glossar (MODIFY).

**Scope/Risk:** ~8–10 Dateien, Produktcode < 60 LoC; Risiko niedrig–mittel (Kopf ist geteilt Trip/Orte; Region-Bearbeiten muss erhalten bleiben, zwei Nutzer testen).

**Open Questions:** keine Produktfrage offen, sofern 2a als Tech-Lead-Entscheidung trägt (Funktion bleibt, nur Platz ändert sich; näher am Mockup). Messwerte aus Staging (Chip-Listen, Griff-Optik, ein-Ort-Eyebrow) folgen.

### Messung Staging/Mockup (28.11., Prüfkonto, Rohdaten scratchpad m/s2.json)
- Chips Trip Staging (11, DE=EN-Reihenfolge): humidity, dewpoint, wind_direction, precip_type, cloud_total, cloud_mid, cloud_high, sunshine, pressure, fresh_snow, snow_depth. Mockup (8): wind_direction, Bewölkung, Sonnenstunden, Neuschnee, Schneehöhe, Taupunkt, Luftfeuchte, Luftdruck.
- Chips Orte Staging (15): wind_chill, humidity, dewpoint, wind_direction, precip_type, visibility, cloud_low, cloud_mid, cloud_high, uv_index, pressure, freezing_level, snowfall_limit, fresh_snow, snow_depth. Mockup (10, orte=ort1).
- Kopf Staging: Eyebrow „Trip · Mallorca“ / „Orte · Münsterland“ (EN „Locations · Münsterland“); Meta Orte „3 Orte · Vergleichstabelle · Morgen-Briefing 07:00“; eigene Regionszeile „Mallorca“/„Münsterland“ mit Stift (`*-region-edit-toggle`).
- Ziehgriffe: Mockup ⋮⋮ #9a958a, 12 px (Handy 10 px); Produkt SVG 6 Punkte #9a958a, 14 px. Gleiche Farbe, Griff in beiden vorhanden ⇒ Punkt 4 ist KEINE Abweichung (Bildprüfer übersah blasse Glyphe). Keine Änderung.
- Knopf: Mockup #c45a2a (4,34:1), Staging #8c3e1a (7,45:1) ⇒ bestätigt bewusste Abweichung, Mockup nachziehen.
- Mockup-Chip-Ordnung im Mockup: `removed` (abgewählte Vorlagen-Metriken) + `off`; Ziel: Mockup-Chips in Produkt-Reihenfolge (Gruppen-Ordnung) und vollständig.
