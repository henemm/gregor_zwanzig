# Klärung: Wie liest der Elementlisten-Abgleich Texte? (#3111, TDD-RED)

## Ergebnis

Der Sammler liest weder `textContent` noch `innerText`, sondern je Element die **eigenen Textknoten** (`nodeType === 3`), aneinandergehängt:

- `frontend/e2e/elementliste-abgleich.staging.spec.ts:110` `sichtbareTexte()`, Kern Zeilen 124-126:
  `for (const k of Array.from(el.childNodes)) if (k.nodeType === 3) eigen += k.nodeValue;` danach `n(eigen)` (Leerraum auf ein Leerzeichen, trim) und `texte.push`.
- Zusätzlich (Z. 118-131): Eingaben liefern `aria-label`/`placeholder`/`value` (Z. 118-122), Knöpfe und `switch`/`group`/`textbox` ihr `aria-label` (Z. 123-124); unsichtbare Elemente (`checkVisibility()`) und `aria-hidden="true"`-Teilbäume fallen weg (Z. 118).
- Der Vergleich normalisiert nur Leerraum, Anführungszeichen („“ zu ", ‚‘ zu ') und geschütztes Leerzeichen: `frontend/e2e/elementliste_abgleich_logik.ts:199-206` `normalisiere()`.

## Folgerungen für die Umsetzung

1. **`<br>`-Lösung passt ohne Leerzeichen:** `{unten_1}<br>{unten_2}` im selben `<span>` ergibt als eigener Text `unten` + `zu wenig` = `untenzu wenig`. Das ist exakt der Eintrag der Elementliste (`docs/context/einstellungen_neu/elementliste.json:362` „untenzu wenig“, `:368` „obenzu viel“). Kein zusätzliches Leerzeichen im Katalog oder Markup (sonst `unten zu wenig`, Abweichung).
2. **ACHTUNG, Spec-Konflikt zu Implementation Details:** Die Spec verlangt den Abweichend-Satz als verschachteltes `<span data-testid="wetter-grenzen-abweichend-{id}">` im Hinweis-Absatz. Ein verschachteltes Kind-Element zählt für den Sammler als **eigener** Text; der Hinweis-Absatz (eigene Textknoten) wäre dann `Grün ist alles … keine Grenze.` und der Satz `Abweichend von der Vorlage „X“.` ein zweiter Text. Die Elementliste (z. B. `elementliste.json:372`, `:429`) führt beides als **einen** Text. Deshalb muss der Abweichend-Satz als **Textknoten im selben Element** wie der Hinweis stehen (z. B. `{$t('…hinweis')}{#if abweichend} {$t('…abweichend', …)}{/if}` im `<p data-testid="wetter-grenzen-hinweis-{id}">`). Der testid `wetter-grenzen-abweichend-{id}` kann dann nur noch entfallen oder an anderer Stelle bleiben (Bestandstests E2E `s3a2794-teil3-grenzen.spec.ts:56` anpassen). Der RED-Test prüft genau diesen eigenen Text.
3. **Bestätigung:** Rumpf muss ein **einzelnes Element nur mit Textknoten** sein (Ersetzt-Satz + Verlust-Satz + Bleibt-Satz in einem `<span>`), der Titel `<b>„{name}“ übernehmen?</b>` daneben. Sonst zerfällt der Rumpf in mehrere Texte und weicht von der Elementliste ab.
4. **„· aktiv“:** Name und Zusatz in **demselben** Element (`<span>{name} · aktiv</span>`), nicht in einem eigenen Kind-Element, sonst entstehen zwei Texte (Elementliste führt `Alpen-Trekking · aktiv` als einen).
5. Unterzeile eigener Vorlagen: `eigene · {Beschreibung}` bzw. `eigene` als ein Text im `<small>`.

## RED-Tests

Die Tests lesen genauso (Hilfsfunktion `eigeneTexte()` in `frontend/src/lib/components/organisms/__tests__/feat_3111_wetter_dialoge_mockup.test.ts`, bildet `sichtbareTexte` nach). Ein Live-Browser-Beleg gegen den echten Sammler folgt über den Staging-Abgleich `--scope wetter` (AC-9).

## Bestandstests, die die alte Form pinnen (NICHT jetzt angepasst, macht die Implementierung)

Unit:
- `frontend/src/lib/components/shared/__tests__/s3a2794_teil3_wetter_katalog.test.ts` (Pflichttexte mit ‚…‘, „Beschreibung“, Z. 55-109)
- `frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts` (Z. 538-629, listet Wetter-Schlüssel wortgleich)
- `frontend/src/lib/components/organisms/__tests__/wetter_tab_abschnitt_marker_2966.test.ts` (Wechsel-Frage, Speichern-Dialog)
- `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` (alte Schlüssel `wetter.grenzen.unten/oben`, `frage_route/_vergleich` ohne Verwender, falls entfernt)
- Elementlisten-Test `elementliste_abgleich_bedienplan.test.ts` (laut Kontext)

E2E:
- `frontend/e2e/s3a2794-teil3-vorlage.spec.ts` (:48/:76/:80), `s3a2794-teil3-grenzen.spec.ts` (:56, testid abweichend), `s3a2794-teil3-dialog.spec.ts`, `s3a2794-teil3-englisch.spec.ts`

Zählwächter: `tests/test_2913_c2_besitzerliste.py:126` (`"#3111": 156`), erst nach Staging-Abgleich.

## Offene Entscheidungen der Implementierung (Test legt sich nicht fest)

- Orte-Rumpf „für diesen Ort“ / „für diese Orte“: die Komponente kennt die Ortezahl nicht; der Test akzeptiert beide Formen (`ersetzt_vergleich`). Schlüssel für Einzahl/Mehrzahl frei wählbar.
- Beschreibung eigener Vorlagen: Test reicht sie über `eigeneVorlagen()` (aus `MetricPreset.description`) in `VorlageKarte`; das Feld in `EigeneVorlage` darf beliebig heißen.
