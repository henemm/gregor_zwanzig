# Kontext: fix-3437-orte-erklaer-gesperrt (Issue #3437)

## Request Summary
Cluster 5 der Abnahme-Messung #3009 (26.11.): zwei Mockup-Abweichungen (Fassung 4) im Einstellungs-Hub.
1. Reiter Orte, Abschnittskopf: Erklärtext laut Mockup „Schon ein einzelner Ort ergibt ein vollständiges Briefing. Ab zwei Orten stehen die Orte in der Übersicht nebeneinander, ohne Rangfolge.“ (ADR-0124 Nr. 10). Live steht der alte Katalogtext `vergleich.hub.kopf.orte_erklaer` („Ein Ort ergibt ein Orts-Briefing. Ab zwei Orten kommt die Vergleichstabelle dazu, ohne Rangfolge.“). 4 Einträge (Zustände normal/laedt/fehler/luecken) je Sprache.
2. Reiter Zustellung, Zustand „Lücken“: Mockup zeigt in der Alarm-Zelle von Telegram und SMS ein nacktes „gesperrt“; nur Premium-SMS (verfallene Rückadresse) zeigt „gesperrt: Rückadresse verfallen“. Live zeigt jede gesperrte Zelle „gesperrt: {Grund}“ (z. B. „gesperrt: Telegram-Chat fehlt“), obwohl derselbe Grund schon in der Hinweiszeile direkt darüber steht. 2 Einträge je Kontext (Trip, Orte).

## Related Files
- `frontend/src/lib/i18n/messages/{de,en}/vergleich.json:38` — Katalogtext `vergleich.hub.kopf.orte_erklaer`
- `frontend/src/lib/components/compare/CompareTabs.svelte:719` — Verwender (Bereichskopf Reiter Orte)
- `frontend/src/lib/components/compare/__tests__/f10KatalogAnker.ts:61` — Katalog-Anker mit altem Text (DE/EN)
- `frontend/src/lib/__tests__/elementliste_bereichskoepfe_3006.test.ts:72-98` — Ausnahme `OFFEN_3122` (beidseitig streng, muss entfallen)
- `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:85-102` — `gesperrt()` baut `alarmSperre = tr('zustellung.gesperrt', {grund: sperre})`; Aufrufer Zeilen 148-215
- `frontend/src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte:110` — rendert `st.alarmSperre`
- `frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts:134,197,233,274,282` — Tests erwarten heute `^gesperrt: \S` für Telegram/SMS/Tarif
- `frontend/src/lib/i18n/messages/{de,en}/zustellung.json:52` — `zustellung.gesperrt` „gesperrt: {grund}“ / „locked: {grund}“
- `docs/context/einstellungen_neu/elementliste.json` — Soll-Liste (Orte-Erklärtext `luecke:true`, `text_en:null`; „gesperrt“-Zeilen ordnung 19/25 mit i18n_key `admin.nutzer.gesperrt` per Textabgleich)
- `docs/context/einstellungen_neu/elementliste_besitzer.json` — 4 Freigaben Orte-Erklärtext (#3122) + 4 Freigaben „gesperrt“ (trip/orte, #3122) müssen entfallen
- `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html:373-377,744` — Mockup: `gesperrt${a.lock?': '+a.lock:''}`, nur Premium-SMS hat `lock`
- `scripts/elementliste_aus_mockup.ts`, `scripts/elementliste_abgleich.ts` — Erzeugung/Abgleich der Elementliste

## Existing Patterns
- Katalogtexte nur über `$t(...)`/`tr(...)`, DE+EN Pflicht (ADR-0104, `docs/reference/i18n_konventionen.md`).
- Elementliste wird aus Mockup + Katalog erzeugt; nach Katalogänderung neu erzeugen, `luecke` fällt dann weg.
- `ohnePunkt()` existiert bereits (Satzpunkt am Ende entfernen).

## Dependencies / Dependents
- `alarmSperre` nur in KanalTabelle.svelte gelesen. Test-Schicken-Menü (`testSchickenModell.ts`) nutzt `zustellung.gesperrt` eigenständig — dort zeigt das Mockup weiterhin „gesperrt: {Grund}“, bleibt unverändert.

## Existing Specs
- `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md` — Z. 124, AC-15, AC-21: Alarm-Zelle „gesperrt: {Grund}“. Mockup Fassung 4 (neuer, PO-Zielbild des Epics #2913) zeigt den Grund nur dort, wo er nicht schon in der Hinweiszeile steht. Die neue Spec löst diese Stellen ab (Verweis im Spec-Kopf).
- `docs/specs/modules/feat_3151_pruefkonto_abgleich.md` — Prüfkonto-Abgleich.

## Risks
- Elementlisten-Neuerzeugung kann weitere Einträge verschieben (andere i18n_key-Treffer bei gleichem Text) → Diff prüfen.
- Bestehende Modell-Tests müssen angepasst, nicht gelöscht werden; Premium-Verfallen bleibt „gesperrt: Rückadresse verfallen“ (sicherheitsrelevant AC-20).

## Analysis

**Type:** Feature/Angleich an Mockup Fassung 4 (kein Laufzeitfehler).

### Affected Files (Change Type)
| Datei | Änderung |
|---|---|
| `frontend/src/lib/i18n/messages/de/vergleich.json`, `en/vergleich.json` | MODIFY `vergleich.hub.kopf.orte_erklaer` → Mockup-Text DE; EN: „Even a single location makes a complete briefing. From two locations on, the locations stand side by side in the overview, without ranking.“ |
| `frontend/src/lib/i18n/messages/de/zustellung.json`, `en/zustellung.json` | MODIFY: neuer Schlüssel `zustellung.gesperrt_kurz` „gesperrt“ / „locked“ (Admin-Schlüssel nicht fachfremd wiederverwenden) |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts` | MODIFY `gesperrt()`: Grund in der Alarm-Zelle nur, wenn er nicht schon wortgleich (ohne Schlusspunkt) in der Hinweiszeile steht; sonst nacktes „gesperrt“. Ergebnis: Telegram/SMS/E-Mail/Tarif-Gate → „gesperrt“, Premium verfallen → „gesperrt: Rückadresse verfallen“ |
| `frontend/src/lib/components/compare/__tests__/f10KatalogAnker.ts` | MODIFY Anker auf neuen Text |
| `frontend/src/lib/__tests__/elementliste_bereichskoepfe_3006.test.ts` | MODIFY: Ausnahme `OFFEN_3122` entfällt |
| `frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts` | MODIFY Erwartungen Z. 134/197/274/282 |
| `frontend/e2e/s3b2795-zustellung-gesperrt.spec.ts` | MODIFY Erwartungen Telegram/SMS/Premium-Tarif |
| `docs/context/einstellungen_neu/elementliste.json` | REGENERATE (Orte-Erklärtext ohne Lücke, mit Key/EN) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY: 8 Freigaben (#3122) entfernen |
| `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md` | MODIFY: Z. 124, AC-15, AC-21 mit Verweis auf neue Spec |

### Scope / Risk
~10 Dateien, < 60 LoC Produktcode; Risiko niedrig (nur Anzeigetext, kein Versand- oder Speicherpfad). Sicherheitsregel AC-20 (Premium verfallen gesperrt) bleibt unverändert — nur der Zellentext ändert sich.

### Technical Approach
1. Katalogtexte DE/EN.
2. `gesperrt()`: `alarmSperre = sperreZeigen ? tr('zustellung.gesperrt',{grund:sperre}) : tr('zustellung.gesperrt_kurz')` mit `sperreZeigen = ohnePunkt(sperre) !== ohnePunkt(grund)`.
3. Elementliste neu erzeugen, Freigaben entfernen, Tests nachziehen.
4. Nachweis: Kern-Tests (Modell, Katalog, Elementliste) + Staging-Abgleich `--strict` DE/EN Reiter Orte und Zustellung.

### Dependencies
Test-Schicken-Menü (`testSchickenModell.ts`) unberührt (Mockup zeigt dort weiter „gesperrt: {Grund}“).

### Open Questions
Keine Produktfrage: Mockup Fassung 4 ist das freigegebene Zielbild des Epics #2913; die Regel „Grund nur einmal zeigen“ ist daraus abgeleitet. Spec-Freigabe deckt die Ablösung von AC-15/AC-21 der Spec #2795 ab.
