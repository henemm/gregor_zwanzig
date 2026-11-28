---
entity_id: fix_3437_orte_erklaer_gesperrt
type: module
created: 2026-11-28
updated: 2026-11-28
status: draft
version: "1.0"
tags: [einstellungen, mockup-fassung-4, i18n, zustellung, orte]
issue: 3437
epic: 2913
workflow: fix-3437-orte-erklaer-gesperrt
---

# Reiter Orte: Erklärtext und Zeile „gesperrt“ der Kanalliste (Mockup Fassung 4)

## Approval

- [ ] Approved

## Purpose

Zwei Abweichungen vom freigegebenen Mockup (Fassung 4, Cluster 5 der Abnahme-Messung #3009) werden behoben. Der Erklärtext im Reiter Orte nennt, dass schon ein einzelner Ort ein vollständiges Briefing ergibt. Die Alarm-Zelle eines gesperrten Kanals im Reiter Zustellung zeigt den Grund nur noch, wenn er nicht schon in der Hinweiszeile darüber steht.

Diese Spec löst Zeile 124, AC-15 und AC-21 von `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md` in diesem Punkt ab (Alarm-Zelle „gesperrt: {Grund}“). Dort wird ein Verweis auf diese Spec ergänzt.

## Source

- **File:** `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts` (Funktion `gesperrt()`), `frontend/src/lib/i18n/messages/{de,en}/vergleich.json`, `frontend/src/lib/i18n/messages/{de,en}/zustellung.json`
- **Identifier:** `gesperrt()`, Katalogschlüssel `vergleich.hub.kopf.orte_erklaer`, neu `zustellung.gesperrt_kurz`
- **Mockup:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` Z. 373-377 und 744

> **Schicht:** nur Frontend (`frontend/src/...`, SvelteKit). Kein Go- und kein Python-Code, kein Versand- oder Speicherpfad.
>
> **Trip/Ortsvergleich-Teilung:** Teil B liegt im geteilten Code unter `shared/zustellung-tab/` und gilt für Trip und Orte (`context="route"|"vergleich"`) gleich; keine neue Komponente. Teil A betrifft nur den Compare-Bereichskopf (Reiter Orte, kein Trip-Pendant).
>
> **Mandantentrennung:** keine Nutzerdaten bewegt, nur Anzeigetext.
>
> **Kanäle:** Der Briefing-Inhalt ändert sich nicht. Betroffen ist nur die Anzeige der Alarm-Zelle für alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS); das Sperrverhalten selbst bleibt unverändert.

## Scope

**Drin:** Katalogtext des Reiters Orte (DE/EN); Text der Alarm-Zelle gesperrter Kanäle im Reiter Zustellung (Trip und Orte, geteilter Code); neu erzeugte Elementliste; Wegfall der zugehörigen Freigaben und Test-Ausnahme; Verweis in Spec #2795.

**Nicht drin:** Sperrverhalten selbst (Schalter, Zählung als Alarm-Kanal, Versand), Test-Schicken-Menü, übrige Cluster der Messung #3009.

## Estimated Scope

- **LoC:** ca. +40/-15 Produktcode, dazu Tests und Fixture-Anpassungen
- **Files:** 11 (siehe Implementation Details)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ohnePunkt()` | Funktion (zustellungModell.ts) | Schlusspunkt für den Textvergleich entfernen |
| `tr()` / Katalog `messages/{de,en}` | i18n (ADR-0104) | alle Nutzertexte nur über den Katalog, DE und EN |
| `KanalTabelle.svelte` | Komponente | rendert `st.alarmSperre`, unverändert |
| `testSchickenModell.ts` | Modell | nutzt `zustellung.gesperrt` weiter („gesperrt: {Grund}“), bleibt unverändert |
| `scripts/elementliste_aus_mockup.ts`, `scripts/elementliste_abgleich.ts` | Skripte | Elementliste erzeugen und gegen Staging abgleichen |
| `docs/context/einstellungen_neu/elementliste.json`, `elementliste_besitzer.json` | Soll-Liste / Freigaben | neu erzeugen bzw. Freigaben entfernen |
| `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md` | Spec | wird in Z. 124, AC-15, AC-21 abgelöst |
| ADR-0124 Nr. 10, ADR-0095 | ADR | Orte-Erklärtext, Kanal-Parität |

## Implementation Details

**Teil A: Erklärtext Reiter Orte.** Der Katalogtext `vergleich.hub.kopf.orte_erklaer` wird gesetzt auf:

- DE: „Schon ein einzelner Ort ergibt ein vollständiges Briefing. Ab zwei Orten stehen die Orte in der Übersicht nebeneinander, ohne Rangfolge.“
- EN: „Even a single location makes a complete briefing. From two locations on, the locations stand side by side in the overview, without ranking.“

Der Katalog-Anker in `f10KatalogAnker.ts` wird auf den neuen Text gezogen. Die Elementliste wird mit `scripts/elementliste_aus_mockup.ts` neu erzeugt (Lücke und `text_en:null` des Orte-Erklärtexts fallen weg, Diff auf verschobene i18n_key-Treffer prüfen). Die Ausnahme `OFFEN_3122` in `elementliste_bereichskoepfe_3006.test.ts` entfällt (beidseitig streng). Die 4 Freigaben des Orte-Erklärtexts (#3122) in `elementliste_besitzer.json` entfallen.

**Teil B: Zeile „gesperrt“ der Kanalliste.** In `gesperrt()` gilt:

- `sperreZeigen = ohnePunkt(sperre) !== ohnePunkt(grund)`, wobei `grund` der Text der Hinweiszeile über der Tabelle ist.
- `alarmSperre = sperreZeigen ? tr('zustellung.gesperrt', {grund: sperre}) : tr('zustellung.gesperrt_kurz')`.
- Neuer Katalogschlüssel `zustellung.gesperrt_kurz`: DE „gesperrt“, EN „locked“. Der Admin-Schlüssel `admin.nutzer.gesperrt` wird nicht fachfremd wiederverwendet.

Ergebnis je Fall (Alarm-Zelle):

| Fall | Anzeige DE | Anzeige EN |
|------|-----------|-----------|
| Telegram-Chat fehlt | gesperrt | locked |
| SMS unbestätigt / fehlt / Tarif | gesperrt | locked |
| E-Mail fehlt | gesperrt | locked |
| Premium-SMS Tarif-Gate | gesperrt | locked |
| Premium-SMS nie gemeldet | gesperrt | locked |
| Premium-SMS Rückadresse verfallen | gesperrt: Rückadresse verfallen | locked: (Katalogtext der Rückadresse) |

Unverändert bleiben: das Sperrverhalten (Schalter deaktiviert, gesperrter Kanal zählt nicht als Alarm-Kanal, AC-20 der Spec #2795, sicherheitsrelevant) und das Test-Schicken-Menü. Die 4 Freigaben „gesperrt“ (#3122, Trip und Orte) in `elementliste_besitzer.json` entfallen.

**Betroffene Dateien**

| Datei | Änderung |
|-------|----------|
| `frontend/src/lib/i18n/messages/de/vergleich.json`, `en/vergleich.json` | MODIFY Text `vergleich.hub.kopf.orte_erklaer` |
| `frontend/src/lib/i18n/messages/de/zustellung.json`, `en/zustellung.json` | MODIFY neuer Schlüssel `zustellung.gesperrt_kurz` |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts` | MODIFY `gesperrt()` |
| `frontend/src/lib/components/compare/__tests__/f10KatalogAnker.ts` | MODIFY Anker |
| `frontend/src/lib/__tests__/elementliste_bereichskoepfe_3006.test.ts` | MODIFY Ausnahme `OFFEN_3122` entfernen |
| `frontend/src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts` | MODIFY Erwartungen (Z. 134, 197, 233, 274, 282) |
| `frontend/e2e/s3b2795-zustellung-gesperrt.spec.ts` | MODIFY Erwartungen Telegram/SMS/Premium-Tarif |
| `docs/context/einstellungen_neu/elementliste.json` | REGENERATE |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY 8 Freigaben (#3122) entfernen |
| `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md` | MODIFY Verweis auf diese Spec bei Z. 124, AC-15, AC-21 |

## Expected Behavior

- **Input:** Nutzer öffnet den Reiter Orte bzw. den Reiter Zustellung (Zustand Lücken) in Deutsch oder Englisch, im Trip oder im Orts-Vergleich.
- **Output:** Erklärtext nach Mockup Fassung 4; Alarm-Zelle eines gesperrten Kanals zeigt „gesperrt“ / „locked“, außer bei verfallener Premium-Rückadresse.
- **Side effects:** keine; es werden keine Daten geschrieben und nichts versendet.

## Test Plan

### Kern-Schicht (`node --test`, deterministisch, kein Mock-Theater)

- Modell-Test `zustellungModell.test.ts`: Telegram fehlt, SMS unbestätigt/fehlt/Tarif, E-Mail fehlt, Premium-Tarif-Gate, Premium nie gemeldet liefern DE „gesperrt“ und EN „locked“; Premium verfallen liefert „gesperrt: Rückadresse verfallen“; für beide Kontexte Trip und Orte. Ein Fall, in dem der Grund nicht in der Hinweiszeile steht, zeigt weiter „gesperrt: {Grund}“. Die Kanal-Sperre (Schalter deaktiviert, nicht als Alarm-Kanal gezählt) bleibt grün.
- Katalog-Test (`f10KatalogAnker.ts`): DE und EN Wortlaut von `vergleich.hub.kopf.orte_erklaer`; Schlüssel `zustellung.gesperrt_kurz` in beiden Sprachen vorhanden.
- Elementlisten-Test (`elementliste_bereichskoepfe_3006.test.ts`): ohne `OFFEN_3122` für den Orte-Erklärtext grün; Orte-Erklärtext hat in der Elementliste keine Lücke.

### Live-E2E-Schicht (nur in `/e2e-verify` gegen Staging)

- `frontend/e2e/s3b2795-zustellung-gesperrt.spec.ts` angepasst: gesperrte Zellen Telegram, SMS und Premium-Tarif zeigen „gesperrt“, Premium verfallen „gesperrt: Rückadresse verfallen“.
- Staging-Abgleich `scripts/elementliste_abgleich.ts --strict` in DE und EN.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit deutscher Oberfläche / When er den Reiter Orte öffnet / Then steht im Abschnittskopf „Schon ein einzelner Ort ergibt ein vollständiges Briefing. Ab zwei Orten stehen die Orte in der Übersicht nebeneinander, ohne Rangfolge.“
  - Test: Katalogtest prüft den DE-Wortlaut; Staging-Abgleich zeigt den Text im Reiter Orte in allen Zuständen (normal, lädt, Fehler, Lücken).

- **AC-2:** Given ein Nutzer mit englischer Oberfläche / When er den Reiter Orte öffnet / Then steht im Abschnittskopf „Even a single location makes a complete briefing. From two locations on, the locations stand side by side in the overview, without ranking.“
  - Test: Katalogtest prüft den EN-Wortlaut; Staging-Abgleich in EN ohne Abweichung.

- **AC-3:** Given ein Trip mit gesperrtem Telegram-Kanal (Chat fehlt) und deutscher Oberfläche / When der Nutzer den Reiter Zustellung öffnet / Then zeigt die Alarm-Zelle von Telegram nur „gesperrt“, weil der Grund schon in der Hinweiszeile darüber steht.
  - Test: Modelltest für Kontext Trip; E2E-Spec prüft die Zelle auf Staging.

- **AC-4:** Given ein Orts-Vergleich mit gesperrtem Telegram-Kanal und deutscher Oberfläche / When der Nutzer den Reiter Zustellung öffnet / Then zeigt die Alarm-Zelle von Telegram dasselbe nackte „gesperrt“ wie im Trip.
  - Test: Modelltest für Kontext Vergleich (gleicher geteilter Code).

- **AC-5:** Given ein Kanal SMS mit unbestätigter oder fehlender Nummer oder gesperrtem Tarif, E-Mail ohne Adresse, Premium-SMS mit gesperrtem Tarif oder nie gemeldet / When der Nutzer den Reiter Zustellung öffnet / Then zeigt jede dieser Alarm-Zellen nur „gesperrt“.
  - Test: Modelltest je Sperrgrund, beide Kontexte.

- **AC-6:** Given Premium-SMS mit verfallener Rückadresse / When der Nutzer den Reiter Zustellung öffnet / Then zeigt die Alarm-Zelle weiterhin „gesperrt: Rückadresse verfallen“.
  - Test: Modelltest und E2E-Spec; Mockup zeigt diesen Fall mit Grund.

- **AC-7:** Given ein Nutzer mit englischer Oberfläche und gesperrtem Kanal / When er den Reiter Zustellung öffnet / Then zeigt die Alarm-Zelle „locked“ statt „gesperrt“ (verfallene Premium-Rückadresse: „locked: “ mit dem englischen Grund).
  - Test: Modelltest mit Sprache EN und Katalogtest für `zustellung.gesperrt_kurz`.

- **AC-8:** Given ein gesperrter Kanal (Sicherheitsregel AC-20 der Spec #2795) / When die Anzeige auf „gesperrt“ verkürzt ist / Then bleibt der Alarm-Schalter dieses Kanals deaktiviert und der Kanal zählt nicht als Alarm-Kanal.
  - Test: bestehende Modelltests zum Sperrverhalten bleiben unverändert grün.

- **AC-9:** Given das Test-Schicken-Menü mit gesperrtem Kanal / When der Nutzer es öffnet / Then zeigt es weiterhin „gesperrt: {Grund}“ wie im Mockup.
  - Test: bestehender Test von `testSchickenModell.ts` bleibt unverändert grün.

- **AC-10:** Given die neu erzeugte Elementliste und die Freigabedatei / When der Elementlisten-Test läuft / Then ist die Ausnahme `OFFEN_3122` entfallen und die 8 Freigaben (4 Orte-Erklärtext, 4 „gesperrt“) sind aus `elementliste_besitzer.json` entfernt, ohne dass ein Test rot wird.
  - Test: `elementliste_bereichskoepfe_3006.test.ts` und Freigabe-Tests im Kern-Lauf grün.

- **AC-11:** Given die ausgelieferte Version auf Staging / When der Staging-Abgleich `--strict` in DE und EN läuft / Then meldet er im Reiter Orte und im Reiter Zustellung (Zustand Lücken) keine Abweichung dieser beiden Cluster mehr.
  - Test: `scripts/elementliste_abgleich.ts --strict` DE und EN mit Prüfkonto-Login, Seed-IDs.

## Definition of Done

- AC-1 bis AC-11 erfüllt, Kern-Tests (node --test) für Modell, Katalog und Elementliste grün.
- Alle CI-Checks grün, Staging-E2E `s3b2795-zustellung-gesperrt` grün.
- Staging-Abgleich `--strict` DE und EN ohne Abweichung in Reiter Orte und Zustellung (Lücken) für diese Cluster.
- Ausgeliefert nach Produktion, Selftest grün, Issue #3437 mit Abschlusskommentar geschlossen.

## Known Limitations

- Gleichheitsprüfung nur wortgleich ohne Schlusspunkt; weicht ein Sperrgrund künftig im Wortlaut von der Hinweiszeile ab, erscheint er wieder in der Zelle (gewollt, sichtbar im Modelltest).
- Test-Schicken-Menü behält „gesperrt: {Grund}“ (Mockup).
- Der Auftrag braucht keine menschliche Sperre (override) und keine Gate-Konfigurations-Änderung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reiner Angleich an das freigegebene Mockup (ADR-0124 Nr. 10, Epic #2913); keine neue Entscheidungsfläche. Die Regel „Grund nur einmal zeigen“ ist aus dem Mockup abgeleitet.

## Changelog

- 2026-11-28: Initial spec created (Issue #3437, Epic #2913)
