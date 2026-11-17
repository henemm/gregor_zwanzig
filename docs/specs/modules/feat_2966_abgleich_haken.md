---
entity_id: feat_2966_abgleich_haken
type: module
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
tags: [einstellungen-neu, elementliste, abgleich, wetter, bedienplan, epic-2913, issue-2966]
workflow: feat-2966-abgleich-haken
---

# Elementlisten-Abgleich: Haken für Script-Zustände im Reiter Wetter

## Approval

- [ ] Approved

## Purpose

Der Staging-Abgleich (#2913) kann im Reiter Wetter (Trip und Orte) 35 Abschnitte nicht prüfen: den Abschnittskopf, die Zustände Laden und Warnung, den Grenzen-Dialog je Metrik und die vier Vorlage-Dialoge. Diese Spec liefert die fehlenden Haken im Markup, einen reinen Bedienplan, mit dem der Abgleich diese Dialoge selbst herstellt (ohne etwas zu speichern), und räumt danach die 35 Besitzer-Einträge `#2966` ehrlich ab.

## Source

- **File:** `frontend/e2e/elementliste_abgleich_logik.ts`, `frontend/e2e/elementliste-abgleich.staging.spec.ts`, `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte`, `.../wetter-tab/MetrikZeile.svelte`, `.../wetter-tab/VorlageKarte.svelte`, `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte`, `frontend/src/lib/i18n/messages/{de,en}/wetter.json`, `docs/context/einstellungen_neu/elementliste_besitzer.json`
- **Identifier:** `bedienPlan(abschnitt, ctx)` (neu), `data-abschnitt` = `abschnittskopf | grenzen-<id> | vorlage-auswahl | vorlage-bestaetigung | vorlage-speichern | vorlage-speichern-fehler`, Katalogschlüssel `wetter.kopf.fehler_verbindung` (neu)
- **Schicht:** Frontend (SvelteKit-Markup, i18n-Katalog) und Frontend-Prüfwerkzeug (`frontend/e2e`, Doku-JSON). Kein Go-API-, kein Python-Core-Code.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung:** Alle geänderten Komponenten sind bereits geteilt (`WetterTabInhalt`, `MetrikZeile`, `VorlageKarte`, `SavePresetDialog`); der Abgleich läuft für `ctx` trip und orte mit derselben Logik. Kein neuer Baustein mit einseitigem Pendant.
> - **Mandantentrennung:** Das Werkzeug legt einen eigenen Prüf-Datensatz im Staging-Testkonto an und räumt ihn auf; es liest/schreibt nur dort. Es gibt keinen neuen Endpoint, daher kein Zwei-Nutzer-Test.
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt ändert sich; E-Mail, Telegram, SMS und Premium-SMS bleiben unberührt.

## Estimated Scope

- **LoC:** Code ca. +250 bis +330 (Logik +60, Staging-Spec +90, Svelte +15, i18n +4, Tests +80 bis +130); `loc_limit_override` 500. Besitzer-JSON: −35 Einträge, plus neu zugeordnete Resteinträge.
- **Files:** ca. 11
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| frontend/e2e/elementliste_abgleich_logik.ts | MODIFY | reine Funktion `bedienPlan`; Script-Regel als Absicherung unverändert |
| frontend/e2e/elementliste-abgleich.staging.spec.ts | MODIFY | Bedienplan ausführen, Reload je Abschnitt, Wetter-Prüf-Datensatz, Schreib-Tripwire |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | MODIFY | Haken `abschnittskopf`; Laden-Text sichtbar; Warnung als zwei Absätze |
| frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte | MODIFY | Haken `grenzen-<id>` nur im offenen Zustand |
| frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte | MODIFY | Haken `vorlage-auswahl`, `vorlage-bestaetigung` |
| frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte | MODIFY | Haken `vorlage-speichern`, `vorlage-speichern-fehler` (additiv, geteilt) |
| frontend/src/lib/i18n/messages/de/wetter.json, en/wetter.json | MODIFY | `wetter.kopf.fehler` = Satz 1, neu `wetter.kopf.fehler_verbindung` = Sätze 2 und 3 |
| frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts | MODIFY | Neuschlüssel in `NEU_IN_FOLGEPAKETEN` |
| frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts | CREATE | node-Tests für `bedienPlan` |
| frontend/src/lib/components/organisms/__tests__/wetter_tab_abschnitt_marker.test.ts | MODIFY | SSR-Tests für die neuen Haken, Laden-Text, zwei Absätze |
| frontend/src/lib/components/organisms/__tests__/wetter_tab_anker_tap.test.ts | MODIFY | Skelett-Label-Prüfung an den Wrapper-Umbau anpassen |
| docs/context/einstellungen_neu/elementliste_besitzer.json | MODIFY | 35 Einträge `#2966` entfernen, Restabweichungen neu zuordnen |

### Nicht-Ziele

- Keine Behebung der echten Restabweichungen (Mockup-Beispieldaten, Anführungszeichen, Platzhalter); sie bekommen einen neuen Besitzer.
- Keine Änderung des DE-Wortlauts, keine Änderung von testids, keine Änderung am Aussehen.
- Nichts wird je gespeichert: kein Grenzenwert, kein Vorlagenwechsel, keine neue Vorlage.
- Kein Handy-Viewport, keine weiteren Reiter.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_2913_abgleich_ganzseite.md` | Spec | Abgleich-Werkzeug, Besitzer-Verweisformat, `--abnahme` |
| `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md` | Spec | Regel „nie still übersprungen" |
| `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` | Spec | Laden/Fehler, Grenzen, SavePreset im Reiter Wetter |
| `docs/context/einstellungen_neu/elementliste.json` | Daten | Soll-Elemente (Mockup-Generat, unverändert) |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | Katalog | Texte, Parität DE/EN |
| Ratschen `deutsch_unveraendert`, `paritaet_de_en`, `katalog_schluessel_haben_verwender`, `wetter_tab_anker_tap` | Gate | müssen grün bleiben |
| Staging-Testkonto (Staging-`.env`) | Betrieb | Live-Lauf; `assertNotProdBaseURL` bleibt |

## Implementation Details

Reihenfolge (ein Durchlauf, weil die Besitzer-Einträge erst nach dem Staging-Lauf entfernt werden dürfen):

1. **Haken und Texte.** `data-abschnitt="abschnittskopf"` am Kopf; Laden-Text sichtbar als `role="status"`, das Skelett in einem `aria-hidden`-Wrapper (keine Doppelung für Screenreader); Warnung als zwei `<p>` mit Katalogschlüsseln `wetter.kopf.fehler` und `wetter.kopf.fehler_verbindung`; `MetrikZeile` setzt `data-abschnitt="grenzen-<id>"` nur wenn `offen`; die Vorlage-Haken an Menü, Wechsel-Frage und `SavePresetDialog` (nur Attribute).
2. **`bedienPlan(abschnitt, ctx)`.** Reine Funktion, Ergebnis ist entweder eine Schrittliste (`klick`, `lesen`, `schliessen` mit testid) oder `nicht_herstellbar` mit echtem Grund (zum Beispiel „Metrik nicht im Briefing des Prüf-Datensatzes"). Nie ein stilles Auslassen.
3. **Staging-Spec.** Führt den Plan vor `texteImBereich` aus. Sicherheitsregeln: Grenzen nur öffnen und schließen, Wechsel-Frage nur abbrechen, Speichern-Dialog nur leer absenden (Pflichtfehler entsteht vor jedem Netzaufruf) und schließen; nach jedem Abschnitt Seite neu laden. Schreib-Tripwire: zählt jeden PUT/POST/DELETE während der Bedienung, Zähler > 0 ist ein Befund. Ein eigener Wetter-Prüf-Datensatz mit allen Metriken (per Anlage-Body) wird angelegt und am Ende gelöscht.
4. **Abnahmelauf** `--abnahme` DE und EN auf Staging, Bericht lesen.
5. **Besitzer.** 35 Einträge `#2966` entfernen; echte Restabweichungen neu zuordnen: Mockup-Beispieldaten an `#2913`, EN-Lücke an `#2968`, alles andere an ein neues Issue.

## Expected Behavior

- **Input:** Staging-Abgleich, alle Kombinationen Trip/Orte × DE/EN, Reiter Wetter.
- **Output:** Alle 35 bisherigen `#2966`-Abschnitte liefern `gefunden` oder `abweichend` mit Grund (oder `nicht_pruefbar` mit echtem Grund).
- **Side effects:** Kurzzeitig ein Prüf-Datensatz im Testkonto, danach aufgeräumt. Keine gespeicherten Änderungen.

## Acceptance Criteria

- **AC-1:** Given der Reiter Wetter eines Trips oder Ortsvergleichs ist geöffnet / When der Abgleich den Abschnitt „abschnittskopf" liest / Then findet er den Kopf mit „Wetter" und dem Erklärsatz und meldet ihn als gefunden.
  - Test: SSR-Test `wetter_tab_abschnitt_marker` findet `data-abschnitt="abschnittskopf"` mit beiden Texten; der Staging-Abgleich meldet den Abschnitt in Trip und Orte als gefunden.

- **AC-2:** Given die Wetter-Daten laden noch / When ein Nutzer oder der Abgleich die Seite ansieht / Then ist der Text „Lade Metriken …" sichtbar im Abschnitt „laden", und Screenreader lesen ihn genau einmal vor.
  - Test: SSR-Test: Text ohne `aria-hidden` im Bereich `laden` mit `role="status"`, Skelett liegt im `aria-hidden`-Wrapper; `wetter_tab_anker_tap` bleibt grün; Staging-Abgleich meldet `laden` als gefunden.

- **AC-3:** Given die Wetter-Daten konnten nicht geladen werden / When die Warnung erscheint / Then besteht sie aus zwei getrennten Absätzen (Satz 1 | Sätze 2 und 3) mit dem bisherigen deutschen Wortlaut, und EN hat dieselben zwei Absätze über den neuen Katalogschlüssel.
  - Test: SSR-Test zählt zwei `<p>` im Bereich `warnung` in DE und EN; Ratschen `deutsch_unveraendert`, `paritaet_de_en` und `katalog_schluessel_haben_verwender` bleiben grün (der DE-Gesamttext ist unverändert).

- **AC-4:** Given eine Metrik im Briefing ist per „Ändern" geöffnet / When der Abgleich nach „grenzen-<id>" sucht / Then liegt der Haken an der geöffneten Metrikzeile (inklusive „Fertig"), und bei geschlossener Zeile ist kein Haken vorhanden.
  - Test: SSR-Test für `MetrikZeile` offen und geschlossen; Staging-Abgleich öffnet je Metrik den Dialog und liest den Bereich.

- **AC-5:** Given die Vorlage-Karte im Reiter Wetter / When Vorlagen-Menü, Wechsel-Frage, „Als eigene Vorlage speichern" und dessen Namensfehler sichtbar sind / Then tragen sie die Haken `vorlage-auswahl`, `vorlage-bestaetigung`, `vorlage-speichern` und `vorlage-speichern-fehler`, ohne dass sich das Verhalten von `SavePresetDialog` in Trip, Vergleich oder Altpfad ändert.
  - Test: SSR-Tests der vier Haken; bestehende Tests zu `save-preset-error` und `wetter-vorlage-picker` bleiben grün, testids unverändert.

- **AC-6:** Given ein Abschnitt, der einen Bedienschritt braucht / When `bedienPlan` für ihn aufgerufen wird / Then liefert die reine Funktion eine Schrittliste (klick, lesen, schliessen) oder `nicht_herstellbar` mit echtem Grund, und ein Abschnitt ohne Plan wird nie still übergangen.
  - Test: node-Tests für `bedienPlan` mit Fällen Grenzen (Metrik aktiv / nicht im Briefing), je Vorlage-Dialog, unbekannter Abschnitt; Grund ist nie leer.

- **AC-7:** Given der Abgleich auf Staging bedient die Dialoge / When er Grenzen öffnet, die Wechsel-Frage abbricht oder den Speichern-Dialog leer absendet / Then wird nichts gespeichert; jeder PUT, POST oder DELETE während der Bedienung wird als Befund gemeldet, und die Seite wird nach jedem Abschnitt neu geladen.
  - Test: Staging-Lauf mit Tripwire-Zähler 0; Rot-Probe: ein absichtlich schreibender Schritt in einer Testvariante erzeugt einen Befund.

- **AC-8:** Given der Abgleich braucht alle Metriken im Briefing / When er läuft / Then legt er einen eigenen Wetter-Prüf-Datensatz mit allen Metriken an und löscht ihn danach wieder, auch wenn der Lauf mit einem Fehler endet.
  - Test: Staging-Lauf; nach dem Lauf listet die API des Testkontos keinen Prüf-Datensatz mehr.

- **AC-9:** Given der Staging-Abnahmelauf DE und EN, Trip und Orte / When er alle 35 bisherigen `#2966`-Abschnitte auswertet / Then liefert jeder `gefunden` oder `abweichend` mit Grund (oder `nicht_pruefbar` mit echtem Grund), und keiner bleibt wegen eines fehlenden Hakens `nicht_pruefbar`.
  - Test: `--abnahme`-Bericht auf Staging, Auswertung je Abschnitts-ID; Ergebnis als Kommentar in Issue #2966.

- **AC-10:** Given die 35 Besitzer-Einträge `#2966` / When der Abnahmelauf ausgewertet ist / Then sind sie entfernt, jede echte Restabweichung hat einen neuen Besitzer (Mockup-Beispieldaten `#2913`, EN-Lücke `#2968`, sonst ein eigenes Issue), und kein Eintrag wurde still gelöscht.
  - Test: `leseBesitzer` liest die Datei ohne Fehler; erneuter `--abnahme`-Lauf endet mit Exit 0; Vorher/Nachher-Vergleich der Einträge zeigt für jede Entfernung Haken oder neuen Besitzer.

- **AC-11:** Given die Änderungen sind eingespielt / When die bestehenden Wetter-Tab-Tests und Ratschen laufen / Then bleiben alle testids unverändert und alle genannten Ratschen grün.
  - Test: `node --test` über Wetter-Tab-, i18n- und Abgleich-Testdateien, danach die bestehende Wetter-Tab-E2E gegen Staging.

## Definition of Done

- AC-1 bis AC-11 grün, Adversary VERIFIED inklusive Mutations-Gegenprobe (Haken entfernt, Tripwire abgeschaltet, Bedienplan ohne Grund ⇒ jeweils ein roter Test).
- Staging-Abnahmelauf DE und EN: keiner der 35 bisherigen `#2966`-Abschnitte meldet `nicht_pruefbar` ohne echten Grund, Schreib-Tripwire 0, Wetter-Prüf-Datensatz aufgeräumt.
- Keine Besitzer-Einträge `#2966` mehr in `elementliste_besitzer.json`; jede Restabweichung trägt einen gültigen Verweis.
- Lieferung per PR mit allen 6 CI-Checks grün, Staging-Verifikation und Prod-Deploy mit Selftest-Exit 0.

## Known Limitations

- Nicht jede Metrik hat im Prüf-Datensatz einen Grenzen-Knopf (nur Metriken im Briefing, nicht reine Anzeige-Metriken); solche Abschnitte werden `nicht_pruefbar` mit Grund gemeldet.
- `thunder` hat einen Farb-Segment-Editor statt Zahlenfeldern; Textabweichungen dort sind echte Restabweichungen, kein Werkzeugfehler.
- Restabweichungen aus Mockup-Beispieldaten (Vorlagennamen wie „Mallorca Frühling") bleiben bewusst bestehen und gehören dem Mockup-Besitzer.

## Risiken

- **Staging-Seiteneffekte:** Bedienung könnte unbeabsichtigt speichern. Gegenmaßnahme: nur öffnen/abbrechen/leer absenden, Reload je Abschnitt, Tripwire auf PUT/POST/DELETE.
- **Geteilter Dialog:** `SavePresetDialog` wird von Trip, Vergleich und Altpfad benutzt; Haken sind rein additive Attribute.
- **Ratsche `deutsch_unveraendert`:** Der Split des Warntexts ändert Schlüssel; Gegenmaßnahme: wortlauttreue Aufteilung, Neuschlüssel in `NEU_IN_FOLGEPAKETEN`.
- **Prüf-Datensatz:** Ein abgebrochener Lauf könnte Reste hinterlassen; Aufräumen im `finally`-Zweig.
- **Umfang:** über dem Standard-LoC-Limit, deshalb `loc_limit_override` 500; Aufteilen würde zwei Staging-Läufe erzwingen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `node --test` für `bedienPlan`: GIVEN Abschnitt `grenzen-wind` mit aktiver Metrik WHEN Plan gebildet THEN Schrittliste klick/lesen/schliessen; GIVEN Metrik nicht im Briefing THEN `nicht_herstellbar` mit Grund.
- [ ] `node --test` für `bedienPlan`: GIVEN `vorlage-speichern-fehler` THEN Plan sendet nur leer ab und schließt.
- [ ] SSR `wetter_tab_abschnitt_marker`: GIVEN Kopf, laden, warnung, MetrikZeile offen/zu, Vorlage-Karte WHEN gerendert THEN Haken, sichtbarer Laden-Text, zwei Absätze vorhanden.
- [ ] i18n-Ratschen: `deutsch_unveraendert`, `paritaet_de_en`, `katalog_schluessel_haben_verwender` grün mit neuem Schlüssel.
- [ ] Staging-Abgleich (`--abnahme`, DE und EN): alle 35 Abschnitte ausgewertet, Tripwire 0, Prüf-Datensatz aufgeräumt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Prüfwerkzeug-Erweiterung und additive Markup-Haken; keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth) berührt.

## Changelog

- 2026-11-17: Initial spec created
