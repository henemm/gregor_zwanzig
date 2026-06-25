# ADR-0007: Daten statt Empfehlungen — keine paternalistische Bewertung

- **Status:** Akzeptiert
- **Datum:** 2026-02-16
- **Bezug:** `docs/project/strategic-directions.md` (gestrichene Features A2, A3)

## Kontext

Die Zielgruppe sind **fortgeschrittene Wanderer/Skitourengeher**, die ihre Tourenentscheidung
selbst treffen wollen. Der wiederkehrende Wunsch im Produkt-Feedback: **Fakten zur eigenen
Entscheidung**, keine bevormundenden Ratschläge. Es bestand die Versuchung, „hilfreiche" Features
wie eine Go/No-Go-Ampel oder Timing-Empfehlungen einzubauen.

## Entscheidung

Gregor Zwanzig liefert **Daten, keine Handlungsempfehlungen**. Konkret abgelehnt:

- **Go/No-Go-Ampel** (Feature A2) — zu simpel für die Zielgruppe.
- **Timing-Empfehlungen** („geh um 6 Uhr los", Feature A3) — zu paternalistisch; der Nutzer rechnet
  selbst.

Eine Risiko-Kategorisierung (low/med/high) pro Metrik ist erlaubt — aber **ohne** daran geknüpfte
Handlungsempfehlung. Sie dient als neutraler Daten-Layer, nicht als Rat.

## Verworfene Alternativen

- **Empfehlungs-Engine** (Ampel + Timing) — verworfen: bevormundet die Zielgruppe, suggeriert eine
  Sicherheit, die eine Wetterprognose nicht tragen kann, und verschiebt Verantwortung vom Nutzer
  zum System.

## Konsequenzen

- **Positiv:** Klares Produktprofil; keine Haftungs-/Vertrauensfalle durch scheinbar verbindliche
  Empfehlungen; Reports bleiben kompakt und faktenorientiert.
- **Negativ / Preis:** Einsteiger, die einen einfachen „Ja/Nein"-Hinweis erwarten, müssen die Daten
  selbst interpretieren.
- **Folgepflichten:** Neue Features dürfen keine handlungsleitenden Empfehlungen einführen.
  Risiko-Darstellung bleibt rein deskriptiv.
