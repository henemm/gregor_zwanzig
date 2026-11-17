# Context: feat-2966-abgleich-haken

## Request Summary
Der Elementlisten-Abgleich (#2913) kann im Reiter Wetter (Trip und Orte) mehrere Abschnitte nicht
prüfen: Script-Zustände (Grenzen-Dialog je Metrik, Vorlage-Auswahl/-Bestätigung/-Speichern/-Fehler),
den Abschnittskopf und die Zustände `laedt`/`fehler`. Ziel: jeder dieser Abschnitte liefert
`gefunden` oder `abweichend` mit echtem Grund; danach Besitzer-Einträge `#2966` entfernen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/elementliste_abgleich_logik.ts` | reine Logik: `SCRIPT_ABSCHNITT` (Z. 387), `bewerteAbschnitt` (Script-Abschnitt ohne Haken ⇒ `nicht_pruefbar`), `routenPlan` (laedt=haengen, fehler=500 auf `DATEN_ABRUF`) |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | Browser-Lauf je Kombi: Route setzen → goto → ggf. Segment klicken → je Abschnitt `texteImBereich`; **bedient keine Dialoge** |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | `<header class="wt-kopf">` ohne `data-abschnitt="abschnittskopf"`; `laden`-Karte: Text in `<span aria-hidden="true">` (Extraktor überspringt aria-hidden ⇒ „Text nicht sichtbar“); `warnung`-Karte: EIN `<p>` mit drei Sätzen, Mockup erwartet zwei getrennte Texte |
| `.../wetter-tab/GrenzenEditor.svelte` | Grenzen-Dialog je Metrik, kein `data-abschnitt="grenzen-<id>"`; geöffnet über `wetter-grenzen-aendern-<id>` (MetrikZeile) |
| `.../wetter-tab/VorlageKarte.svelte` | Picker (`wetter-vorlage-picker`, Liste ohne Haken `vorlage-auswahl`), Wechsel-Frage `role=alertdialog` (ohne Haken `vorlage-bestaetigung`) |
| `.../shared/weather-metrics-tab/SavePresetDialog.svelte` | Dialog „Als eigene Vorlage speichern“ (ohne Haken `vorlage-speichern`), Fehler `save-preset-error` „Gib der Vorlage einen Namen.“ (ohne Haken `vorlage-speichern-fehler`); auch von `WeatherMetricsTab`/`CreateGroupDialog` benutzt |
| `docs/context/einstellungen_neu/elementliste.json` | Soll-Elemente (Mockup-Generat), Abschnitte `grenzen-<metrik>` (14), `vorlage-*`, `abschnittskopf`, `laden`, `warnung` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | Besitzer-Einträge `verweis: "#2966"` — nach Umsetzung entfernen |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | `wetter.kopf.fehler` (drei Sätze in einem Schlüssel), `wetter.kopf.laden` |

## Existing Patterns
- Abschnitts-Haken `data-abschnitt="…"` an der umschließenden Karte (z. B. `vorlage`, `metriken`, `laden`, `warnung`).
- Zustände über Route-Abfangen (`routenPlan`) und Segment-Klick (Kanal-Segment) — Muster für eine neue Bedien-Stufe „Script-Zustand herstellen“: reine Logik liefert den Bedienplan, Spec führt ihn aus, nicht herstellbar ⇒ `nicht_pruefbar` mit Grund (nie still).
- Ladeweg: `ladeWetterDaten` holt `/api/metrics`, `/api/templates`, `/api/metric-presets` per `Promise.all`; `DATEN_ABRUF` trifft metrics/metric-presets ⇒ `laedt`/`fehler` werden tatsächlich hergestellt (Frage aus dem Issue beantwortet: ja, Zustand entsteht; Ursache liegt im Markup).

## Dependencies
- Upstream: Elementliste (Mockup-Generat), i18n-Katalog, Staging-Testkonto.
- Downstream: `elementliste_abgleich*.test.ts` (node --test), Ratsche `deutsch_unveraendert.test.ts` (Schlüssel `wetter.kopf.fehler`), bestehende Wetter-Tab-E2E (testids bleiben).

## Existing Specs
- `docs/specs/modules/feat_2913_abgleich_ganzseite.md` (Abgleich-Werkzeug)
- Wetter-Reiter-Specs unter `docs/specs/modules/` (Einstellungen neu, Epic #2913)

## Risks & Considerations
- Bedienen darf nichts speichern: Grenzen-Dialog nur öffnen, Vorlage-Wechsel abbrechen, Speichern-Dialog nur mit leerem Namen absenden (Pflichtfehler) und schließen.
- Metriken, die der Trip des Testkontos nicht aktiv hat, sind nicht bedienbar ⇒ `nicht_pruefbar` mit Grund „Metrik nicht im Briefing des Prüf-Datensatzes“ (echter Grund) oder Prüf-Datensatz entsprechend anlegen.
- `laden`: sichtbarer Text vs. Screenreader-Doppelung (Skelett-Label) — barrierearm lösen.
- `warnung`: Aufteilen des Fehlertexts in zwei Absätze ändert Katalogschlüssel ⇒ Ratsche `deutsch_unveraendert` beachten; DE-Wortlaut bleibt gleich.
- SavePresetDialog wird geteilt (Trip/Vergleich/Altpfad) — Haken additiv, keine Verhaltensänderung.

## Analysis

### Type
Feature (Prüfwerkzeug-Erweiterung + kleine Markup-Haken, Epic #2913)

### Befunde (gegen elementliste.json geprüft)
- 35 Besitzer-Einträge `#2966`, alle `art=abschnitt`: abschnittskopf 2, laden 2, warnung 2, vorlage-auswahl/-bestaetigung/-speichern/-speichern-fehler je 2 (=8), grenzen 21 (Trip 13: cloud_low, freezing_level, gust, precipitation, rain_probability, snowfall_limit, temperature, temperature_night, thunder, uv_index, visibility, wind, wind_chill; Orte 8: cloud_total, gust, precipitation, rain_probability, sunshine, temperature, thunder, wind) — **15 Metrik-IDs, nicht 14**.
- abschnittskopf: Soll „Wetter“ + „Was im Briefing steht …“ = Live 1:1, nur Haken fehlt (`<header class="wt-kopf">`, WetterTabInhalt.svelte:225).
- laden: Soll 1 Text „Lade Metriken …“; live im `<span aria-hidden>` (:232) ⇒ Extraktor überspringt. Skelett trägt denselben Text als aria-label.
- warnung: Soll 2 Texte = exakt Satzgrenze des Katalogtexts (Satz 1 | Sätze 2+3) ⇒ wortlauttreuer Split möglich. Alter Besitzer nennt EN-Lücke `#2968` — fällt mit Entfernen weg, muss neu zugeordnet werden.
- vorlage-auswahl (18 El.): Mockup-Demodaten („Alpen-Trekking · aktiv“, „Mallorca Frühling“, „Radtour“ …) ⇒ nur Systemvorlagen/Überschriften `gefunden`, Rest ehrlich `abweichend` (Mockup-Beispieldaten-Besitzer `#2913`).
- vorlage-bestaetigung (4): live ein `<p>` mit 2–3 Sätzen, andere Satzfolge ⇒ Teil-Abweichung.
- vorlage-speichern (9)/-fehler (1): Texte stimmen weitgehend; Platzhalter fehlen live, „Beschreibung (optional)“ vs. „Beschreibung“ ⇒ echte Abweichungen.
- grenzen-<id> (7–12 El.): Knopf „Fertig“ gehört zu MetrikZeile, nicht GrenzenEditor ⇒ Haken an MetrikZeile-Root, nur wenn `offen`. Anführungszeichen ‚‘ vs. „“, `untenzu wenig` ⇒ Restabweichungen. `thunder` hat Farb-Segment-Editor statt Zahlenfelder.
- Grenzen-Knopf existiert nur für Metriken im Briefing (nicht display_only). Prüf-Datensatz (spec.ts:139-197) legt keine Metriken fest ⇒ eigener Wetter-Prüf-Datensatz mit allen Metriken im Anlage-Body nötig; sonst `nicht_pruefbar` „Metrik nicht im Briefing des Prüf-Datensatzes“.
- logik.ts:123-126: `abweichend`/`nicht_pruefbar` ohne Besitzer = offene Abweichung. „Besitzer #2966 raus“ heißt NICHT „Abnahme grün“: echte Restabweichungen bekommen neuen Besitzer mit passendem Verweis (nie still entfernen).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/e2e/elementliste_abgleich_logik.ts | MODIFY | reine Funktion `bedienPlan(abschnitt, ctx)` → Schrittliste (klick/lesen/schliessen, testid) bzw. `nicht_herstellbar` mit Grund; Script-Regel :811 bleibt als Absicherung |
| frontend/e2e/elementliste-abgleich.staging.spec.ts | MODIFY | Bedienplan vor `texteImBereich` ausführen (Schleife :234-283), Zustand je Abschnitt zurücksetzen, Wetter-Prüf-Datensatz mit allen Metriken, Schreib-Tripwire (PUT/POST-Zähler während Bedienung > 0 ⇒ Befund) |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | MODIFY | `data-abschnitt="abschnittskopf"` am Header; laden: sichtbarer Text ohne aria-hidden (role=status), Skelett in aria-hidden-Wrapper; warnung: zwei `<p>` |
| frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte | MODIFY | `data-abschnitt={offen ? \`grenzen-${id}\` : undefined}` am Zeilen-Root |
| frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte | MODIFY | Haken `vorlage-auswahl` (Menü :81), `vorlage-bestaetigung` (alertdialog :84) |
| frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte | MODIFY | Haken `vorlage-speichern` (:87), `vorlage-speichern-fehler` (:116), additiv (geteilt) |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | MODIFY | `wetter.kopf.fehler` = Satz 1, neu `wetter.kopf.fehler_verbindung` = Sätze 2+3 (DE-Wortlaut unverändert) |
| frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts | MODIFY | Neuschlüssel in NEU_IN_FOLGEPAKETEN (:446); paritaet_de_en + katalog_schluessel_haben_verwender müssen grün bleiben |
| frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts (o. neue Testdatei) | MODIFY/CREATE | node-Tests für `bedienPlan` |
| frontend/src/lib/components/organisms/__tests__/wetter_tab_abschnitt_marker.test.ts | MODIFY | SSR-Tests für neue Haken, laden-Text sichtbar, warnung zwei Absätze |
| docs/context/einstellungen_neu/elementliste_besitzer.json | MODIFY | 35 `#2966`-Einträge entfernen; echte Restabweichungen nach Staging-Lauf neu zuordnen (Mockup-Beispieldaten `#2913`, EN-Lücke `#2968`, sonst eigenes Issue) |

### Scope Assessment
- Files: ~11
- Estimated LoC: Code +250 bis +330 (logik +60, spec +90, Svelte +15, i18n +4, Tests +80–130); JSON-Besitzer −280/+neu
- Risk Level: MEDIUM (Prüfwerkzeug bedient Staging-Dialoge; Produkt-Markup nur additiv/barrierearm)

### Technical Approach (Tech-Lead-Entscheidung)
Varianten (aus Plan-Bewertung):
| Thema | gewählt | verworfen |
|---|---|---|
| Haken grenzen | MetrikZeile-Root nur bei `offen` („Fertig“ im Bereich, Haken = Zustand) | GrenzenEditor-Root („Fertig“ fälschlich abweichend) |
| warnung | Split in 2 Schlüssel, wortlauttreu | Mockup anpassen (Mockup ist Soll) / Besitzer behalten (verfehlt Ziel) |
| Prüf-Daten | eigener Wetter-Prüf-Datensatz mit allen Metriken per Anlage-Body, aufgeräumt | Konto-Trip (Metriken unsteuerbar) |
| Dialogzustände | echter Klick per Bedienplan, nur öffnen/abbrechen/leer absenden | Komponententest statt Abgleich (kein Live-Abgleich) |

**Ein Durchlauf statt zwei Scheiben:** Das Issue-Ziel ist nur als Ganzes prüfbar (Besitzer raus erst nach Staging-Lauf); Aufteilen erzeugte ein Folge-Issue mit demselben Staging-Lauf. Daher EIN Workflow mit `loc_limit_override 500` und fester Reihenfolge:
1. Haken + laden/warnung + i18n + Ratschen (SSR-Tests rot→grün)
2. `bedienPlan` in logik.ts (node-Tests rot→grün)
3. Spec-Ausführung + Wetter-Prüf-Datensatz + Schreib-Tripwire
4. Staging-Lauf `--abnahme` DE+EN, Bericht lesen
5. 35 Besitzer `#2966` entfernen, echte Restabweichungen mit korrektem Verweis neu zuordnen

Sicherheitsregeln Bedienung: Wechsel-Dialog nur abbrechen; Speichern-Dialog nur leer absenden (Fehler entsteht clientseitig vor POST) und schließen; Grenzen nur öffnen/schließen ohne Eingabe; nach jedem Abschnitt Seite neu laden. Nicht herstellbar ⇒ `nicht_pruefbar` mit echtem Grund, nie still.

### Dependencies
- Upstream: elementliste.json (Mockup-Generat, unverändert), i18n-Katalog, Staging-Testkonto (Login aus Staging-`.env`).
- Downstream: elementliste_abgleich*.test.ts, wetter_tab_anker_tap.test.ts (prüft Skelett aria-label = wetter.kopf.laden — bei Wrapper-Umbau anpassen), E2E-Nutzer der testids wetter-grenzen-aendern-*, wetter-vorlage-picker, save-preset-error (testids bleiben).
- Specs: feat_2913_abgleich_ganzseite.md (AC-7 Besitzer-Verweisformat, AC-9 Exit, AC-14 Abnahme), einstellungen_neu_neustart_adr_waechter_elementliste.md (AC-13 nie still übersprungen), feat_2794_s3a_teil3_wetter.md (AC-9 Laden/Fehler, AC-16/17 Grenzen, AC-42 SavePreset).

### Open Questions
- keine Produktfrage offen (reines Prüfwerkzeug + barrierearme Markup-Haken, DE-Wortlaut unverändert).
