# Context: rework-2988-ampel-ableitung

Issue #2988 (Eintrag **P10** in #1986; „NEU-7" im Issue-Text ist dort nicht zu finden). Priorität medium, kein Ausfall.

## Request Summary

Die Ampel-Ableitung (Vorlage + Abo-Abweichungen → aufgelöste Ampel, aktive Metriken, Abweichungszahl) existiert in Python und noch einmal im Frontend. Ziel laut Issue: nur Python leitet ab, das Frontend liest das Ergebnis; der Paritätstest wird überflüssig oder bleibt als Regressionswächter.

## Related Files

Abkürzung: `WT/` = `frontend/src/lib/components/shared/wetter-tab/`.

| File | Relevance |
|------|-----------|
| `src/app/ampel.py` | Quelle: `_aufloesen`/`template_id_for`, `_verschmelzen`, `resolve_ampel` (rund 35 Produktaufrufe), `deviation_count` und `ampel_for` (beide ohne Produktaufrufer), `validate_ampel` (`src/app/loader.py:1038`) |
| `WT/ampelModell.ts` | Spiegel: `verschmelzen`, `zaehleAbweichungenGegen`, `zaehleAbweichungen`, `ampelFehler`, `aktiveMetriken`, `eigeneVorlageAmpel`, `zuruecksetzen`, `vorlageIdVon` |
| `WT/wetterZustand.ts` | Hauptverbraucher: `standAusAbo` (:101), `mitEnabled` (:117), `BASIS_IM_KONTEXT`/`vorlageImKontext`, `mengeVon`, `abweichungenVon` (:165), `mitVorlage` (:171) |
| `WT/ampelSchreiben.ts` | `abweichungsMenge` (:39): Umkehrung der Ableitung (Minimalmenge für das Speichern), **nur im Frontend vorhanden**, kein Python-Gegenstück |
| `WT/wetterTabLaden.ts` | `aktiveMetriken` (:51), `eigeneVorlageAmpel` (:89), Laden von `/api/metrics`, `/api/templates`, `/api/metric-presets` |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Editor: `signatur` (:113, aus `mengeVon`), `aendern` (:137), Grenzen-/Gewitterprüfung (:162), Anzeige (:223–238) |
| `frontend/src/lib/components/alerts-tab/alarmAbAnzeige.ts` | `vorlageIdFuer` (:66): weiterer Spiegel von `_aufloesen`, mit Tabelle `PROFIL_ZU_VORLAGE`; genutzt von `AlarmeTab.svelte`, `vorlageName.ts`, `wetterZustand.ts`, `compareNewVorlage.ts`. Nicht im Issue-Wortlaut |
| `internal/handler/ampel.go` | Dritter Spiegel, nur Validierung beim Speichern. Nicht im Issue-Wortlaut |
| `api/routers/config.py:25` | `GET /api/templates` liefert die vollständigen Vorlagen-Ampeln aus Python |
| `api/routers/placements.py`, `src/services/placements_view_service.py:101`, `internal/handler/placements.go:232`, `WT/wasStehtWoSpeicherung.ts` | Vorbild „Server leitet für ungespeicherten Entwurf ab" |

**Aufrufer der Frontend-Exporte (Produkt):** `verschmelzen` → wetterZustand, WetterTabInhalt · `zaehleAbweichungenGegen` → wetterZustand · `aktiveMetriken` → ampelSchreiben, wetterTabLaden, wetterZustand · `eigeneVorlageAmpel` → wetterTabLaden · `zuruecksetzen` → wetterZustand · `grenzenFehler`/`gewitterFehler` → WetterTabInhalt · `gleicheSeite` → ampelSchreiben · `vorlagenAusTemplates` → HubOverview, HubUebersicht, wetterTabLaden.
**Ohne Produktaufrufer (nur Tests):** `zaehleAbweichungen`, `ampelFehler` (wird aber intern von `verschmelzen` benutzt), `vorlageIdVon` (intern von `zaehleAbweichungen` und `eigeneVorlageAmpel` benutzt).

## Existing Patterns

- **Server-Ableitung für einen Entwurf:** `POST /api/briefings/placements/vorschau?kind=` nimmt einen ungespeicherten Entwurf, schreibt nichts. Go setzt `user_id` aus der Anmeldung, Grenze 256 KiB. Frontend: 400 ms Entprellung, veraltete Antworten per Ticket verworfen (`wasStehtWoSpeicherung.ts:115–120`, :171). Heute nur im Anlegen genutzt.
- **Lese-Antworten** (`GET /api/trips/{id}`, `GET /api/compare/presets/{id}`) kommen allein aus dem Go-Store: `display_config.ampel` roh, ohne Auflösung, ohne Python-Aufruf. Keine Antwort enthält heute eine Abweichungszahl.
- **Speichern:** automatisch, 700 ms Entprellung; Trip zwei PUTs, Ortsvergleich über die Hub-Schreibschlange (If-Match, 412 → neu laden), Anlegen ohne Netz bis zum Anlege-POST.
- **Fehlerfall im Reiter:** scheitert das Laden, erscheint „Erneut laden". Keine eigene Offline-Behandlung.

## Dependencies

- **Upstream:** `AMPEL_TEMPLATES` (`src/app/ampel_templates.py`), `/api/templates`, `/api/metrics`, `/api/compare/metrics`, `DERIVED_METRIC_RULES` (Frontend-Kopie von `loader.py:988`).
- **Downstream:** Reiter Wetter (Trip, Ortsvergleich, beide Anlege-Ketten), Speicher-Payloads, eigene Vorlagen, Karte „Was steht wo". Python-Renderer lesen `resolve_ampel` und sind vom Umbau nicht berührt, solange die Quelle gleich bleibt.

## Existing Specs

- `docs/specs/modules/feat_2794_s3a_teil3_wetter.md`: :143 definiert den Spiegel ausdrücklich (Zeilenangaben zu `ampel.py` veraltet); :149 „Frontend hält beide Quellen konsistent", verworfen: Resolver-Umstellung (ii) und Ableitung in Go (iii). Eine Ableitung in Python per Endpunkt wurde dort nicht erwogen. :238 **AC-28**, :247 **AC-37**, :253 **AC-39**; :314 nennt die Entscheidung lokal und umkehrbar.
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md`: :144, :266.
- `docs/specs/modules/feat_3222_windrichtung.md`: S4 (#3230, offen) ändert `ampelModell.ts`/`ampelSchreiben.ts`.
- ADR-0106, ADR-0126, ADR-0127 (Frontend und Go halten kein Metrik-Wissen).

## Tests und Fixtures

| Fixture | Python | Frontend | Go |
|---|---|---|---|
| `ampel_auswahl_paritaet.json` (7 Vorlagen, 11 Fälle) | `test_2794_teil3_auswahl_paritaet.py` | `ampelModell.auswahl_paritaet.test.ts` | – |
| `ampel_deviation_cases.json` (22) | `test_ampel_abweichungszaehler.py` | `ampelModell.paritaet.test.ts`, `ampelModell.test.ts` | – |
| `ampel_validierung_vektoren.json` (32) | `test_ampel_modell_und_aufloesung.py` | `ampelModell.test.ts` | `ampel_validierung_test.go` |
| `ampel_windrichtung_cases.json` (19 + 4) | `test_feat_3222_windrichtung_kern.py` | `ampelModell.test.ts` | `ampel_windrichtung_test.go` |

Die Metadaten in `ampel_deviation_cases.json` nennen eine nicht vorhandene Testdatei (`test_2794_ac28_abweichungszaehler.py`). Rund 30 Frontend-Tests nutzen `vorlagenAusTemplates`, viele laden das Modul über `__tests__/wetterTabDaten.ts`.

**Ratsche** (`tests/unit/ein_katalog_ausnahmen.json`): `ampelModell.ts` FRONTEND_LISTE 2, FRONTEND_VERZWEIGUNG 1; `internal/handler/ampel.go` GO_VERZWEIGUNG 2. `wetterZustand.ts`, `ampelSchreiben.ts`, `wetterTabLaden.ts` nicht gelistet (kein Befund erlaubt).

## Risks & Considerations

1. **Zielkonflikt mit AC-28:** Der Zähler muss „nach jeder Eingabe sofort" stimmen; heute läuft er lokal, ohne Netz. Ein Serverergebnis bringt Verzögerung und einen Fehlerfall. Das ist die Kernfrage der Analyse.
2. **Speichern hängt an der Ableitung:** `signatur` (löst das automatische Speichern aus) und die Speicher-Payload nutzen `mengeVon` → `abweichungsMenge`. Liest das Frontend nur den Zähler vom Server, bleibt die Ableitung für das Speichern im Frontend bestehen; zieht auch das Speichern um, ändert sich der Schreibweg (Bestandsdaten, Read-Modify-Write, #102).
3. **Zähler nicht deckungsgleich:** `deviation_count` zählt gegen die Rohvorlage (`ampel.template`), der Editor gegen die „Vorlage im Kontext" (#3193: abgeleitete Kinder im Trip, nicht ausgebbare Größen im Ortsvergleich neutral) und auf der Minimalmenge. Der Paritätstest deckt `zaehleAbweichungen` ab, das kein Produktcode aufruft. Die Editorzahl hat kein Python-Gegenstück.
4. **Vorlagenwechsel und Zurücksetzen** brauchen nur Vorlagen, die `/api/templates` schon fertig liefert (`verschmelzen(vorlage, null)` ist dort nur eine Kopie). Echte Ableitung steckt in `standAusAbo` (Erst-Laden), `eigeneVorlageAmpel` (eigene Vorlagen) und in Zähler/Menge (je Eingabe).
5. **`aktiveMetriken` und `auswahlLesen`** mischen gespeicherte Liste, Mail-Standard und Ampel; Abgrenzung in der Spec nötig.
6. **Umfang:** Ein vollständiger Umzug (Laden, Zähler, Menge, Validierung, Vorlagen-ID) liegt voraussichtlich über 250 LoC und 5 Dateien; Schnitt in Scheiben prüfen.
7. **Überschneidungen:** #3357 (offen) ändert `VorlageKarte.svelte`, `WetterMetrikenVersandPanel.svelte`; #3230 (S4 Windrichtung) ändert `ampelModell.ts`/`ampelSchreiben.ts`; #3260 läuft am selben Grundsatz.
8. **Mandantentrennung:** ein neuer Endpunkt braucht `user_id` aus der Anmeldung und Tests mit zwei Nutzern (Vorbild `placements.go:232`).

## Nebenbefund (gelesen, nicht ausgeführt)

`zeilenAbweichung` (`WT/ampelSchreiben.ts:28`) vergleicht `enabled`, Grenzen und `alarm_ab`, aber nicht `modus`/`sektoren`. Ein gespeicherter abweichender Windrichtungs-Modus fehlt damit in der erzeugten Minimalmenge. Heute setzt keine Oberfläche diese Felder (S4 #3230 offen); über die API gesetzte Werte können beim nächsten Speichern im Reiter betroffen sein (ob Go die gespeicherten Felder dabei erhält, ist nicht geprüft). Ausführung scheiterte, weil in diesem Arbeitsordner die Frontend-Pakete nicht installiert sind. In der Analyse mit dem Umzug der Minimalmenge klären oder an #3230 geben.

## Offene Fragen für die Analyse

1. Welcher Teil zieht um: nur Lesen (aufgelöste Ampel beim Laden), auch Zähler, auch die Minimalmenge beim Speichern?
2. Wie wird AC-28 („sofort") mit einem Serverergebnis erfüllt, und was zeigt der Reiter bis zur Antwort oder ohne Netz? Produktfrage nur, falls sich das sichtbare Verhalten ändert.
3. Gehören `vorlageIdFuer` und die Go-Validierung in dieses Issue (nicht im Wortlaut)?
4. Werden die unbenutzten Stellen (`zaehleAbweichungen`, `deviation_count`, `ampel_for`) entfernt oder zur einzigen Quelle ausgebaut?
