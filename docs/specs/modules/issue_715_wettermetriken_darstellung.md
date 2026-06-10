---
entity_id: issue_715_wettermetriken_darstellung
type: module
created: 2026-06-10
updated: 2026-06-10
status: complete
version: "1.0"
tags: [frontend, backend, weather-metrics, trip-editor, confidence, preview]
---

# #715 — Paket Wettermetriken-Darstellung (#711, #710, #712)

## Approval

- [x] Approved (PO, 2026-06-10)

## Purpose

Behebt drei zusammengehörende Darstellungs-/Auswahl-Probleme der Wettermetriken im Trip-Editor und -Wizard:
- **#710:** Die Meta-Kennzahl „Sicherheit" (Vorhersage-Verlässlichkeit, `confidence`) ist **keine** Wetterkennzahl eines Ortes und darf **nicht** als pro-Etappe wählbare Metrik auftauchen. Sie bleibt ausschließlich als Vorhersage-Verlässlichkeits-Hinweis (mehrtägiger Forecast) erhalten.
- **#711:** Die „Einfach"-Vorschau zeigt fälschlich Text, obwohl der echte E-Mail-Versand für mehrere Metriken Emojis/Ampel rendert — die Vorschau muss die Realität spiegeln.
- **#712:** Die E-Mail-Vorschau wirkt wie eine echte fremde Etappe; sie muss klar als Beispieldaten gekennzeichnet sein.

## Source

> **Schicht-Hinweis:** #710 ist **full-stack** (Python-Backend-Katalog + Frontend). #711 und #712 sind **frontend-only**.

**Python-Backend (Core):**
- **File:** `src/app/metric_catalog.py` — **Identifier:** `confidence` `MetricDefinition` (Z.171–182), `get_all_metrics`
- **File:** `api/routers/config.py` — **Identifier:** `get_metrics` (`/api/metrics`, Z.49+)
- **Erhalten (NICHT ändern):** `src/providers/openmeteo.py::compute_confidence_pct` (Z.67), Ensemble-Fetch (Z.508+); `src/output/renderers/email/helpers.py::build_confidence_hint` (Z.283); `src/output/tokens/builder.py` SMS-Symbol (Z.222); `confidence_pct`-Aggregation in `src/services/weather_metrics.py`

**Frontend (SvelteKit):**
- `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` — Init-Schleife (Z.116–127, `enabled: true` → `m.default_enabled`)
- `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` — `WM2_S` (Z.26–52), `cell()` (Z.55–60)
- `frontend/src/lib/components/trip-detail/TablePreview.svelte` — Beispielzeilen (Z.36–39)
- `frontend/src/lib/components/trip-detail/metricsEditor.ts` — Metrik-Gewichtung (Z.214, `confidence: 8`)
- `frontend/src/lib/components/trip-detail/ChannelFidelityBubble.svelte` (Z.23), `ChannelFidelityEmail.svelte` (Z.30) — Beispiel-Records

## Estimated Scope

- **LoC:** ~120–180
- **Files:** ~8 (2 Backend, 6 Frontend)
- **Effort:** medium

## Dependencies

- Upstream: Backend-Metrik-Katalog `/api/metrics` (Single Source der wählbaren Metriken); Renderer `fmt_val` (`helpers.py`) als Wahrheit für #711-Vorschauwerte.
- Downstream: Trip-Editor, Trip-Wizard, Orts-Konfiguration — alle ziehen die wählbaren Metriken aus `/api/metrics`. Vorhersage-Hinweis (E-Mail/SMS) liest `confidence_pct` direkt aus Datenpunkten, **unabhängig** von der Metrik-Auswahl.

## Implementation Details

```
#710 — "Sicherheit" als wählbare Metrik entfernen (datensicher):
  - confidence darf NICHT mehr in der von /api/metrics gelieferten Auswahl erscheinen.
    Empfohlen: confidence aus dem user-sichtbaren Katalog ausschließen (Filter im
    get_metrics-Endpoint bzw. Markierung "nicht auswählbar"), die MetricDefinition für
    interne Berechnung/Aggregation ABER erhalten — so bleiben Ensemble-Berechnung,
    confidence_pct_min-Aggregation, E-Mail-Hinweis und SMS-Symbol bit-identisch.
  - Frontend-Beispiel-/Gewichtungs-Daten von confidence bereinigen (Geister-Daten weg).
  - Wizard-Init respektiert default_enabled (Defense-in-Depth gegen künftige Opt-in-Metriken).
  - Bestandsdaten: display_config mit aktivierter confidence-Metrik lädt fehlerfrei,
    confidence wird still ignoriert, übrige Metriken/Felder bleiben erhalten.

#711 — "Einfach"-Vorschau an echtes Renderer-Verhalten angleichen:
  - WM2_S.ind-Werte für CAPE/Wolken/Sonne durch die Emojis ersetzen, die fmt_val()
    für die jeweiligen Roh-Beispielwerte erzeugt (Schwellen aus helpers.py spiegeln):
      cape raw [40,120,80]   -> 🟢🟢🟢            (≤300)
      cloud_total [90,85,80] -> 🌥️🌥️🌥️         (☀️≤10 / 🌤️≤30 / ⛅≤70 / 🌥️≤90 / ☁️>90)
      cloud_low/mid/high     -> ind ergänzen (fehlt bish.) analog Schwellen
      sunshine               -> Wetter-Emoji-ind ergänzen
  - Metriken, deren echtes "Einfach" Text ist (Sichtweite), behalten Text.

#712 — Beispieldaten kennzeichnen:
  - Sichtbares "Beispieldaten"-Label/Hinweis an der E-Mail-Vorschau.
  - Hartcodierten echt wirkenden Etappennamen durch generische Beispiel-Bezeichnung
    ersetzen (z.B. "Beispiel-Etappe · 08–10 h" statt "Etappe 4: Hochweißsteinhaus → Wolayersee").
```

## Expected Behavior

- **Input:** Nutzer öffnet Trip-Editor / Wizard-Schritt 3 / Metrik-Vorschau.
- **Output:** Keine „Sicherheit"-Metrik in irgendeiner Auswahl; „Einfach"-Vorschau mit korrekten Emojis; Vorschau klar als Beispiel erkennbar.
- **Side effects:** Keine — Vorhersage-Verlässlichkeits-Hinweis (E-Mail/SMS) und alle echten Wetter-Reports bleiben byte-identisch.

## Acceptance Criteria

- **AC-1:** Given das user-sichtbare Metrik-Verzeichnis `/api/metrics`, das dem Frontend die auswählbaren Wetter-Metriken kategorisiert liefert / When ein Client den Endpoint abruft und alle Kategorien durchsucht / Then enthält die Antwort in keiner Kategorie eine Metrik mit `id == "confidence"` (Label „Sicherheit").
  - Test: Echter HTTP-GET auf `/api/metrics` gegen den laufenden Backend-Server; Response-JSON über alle Kategorien iterieren und assertieren, dass kein Metrik-Eintrag `id == "confidence"` zurückkommt.

- **AC-2:** Given ein eingeloggter Nutzer im Trip-Editor (WeatherMetricsTab) und im Wizard-Schritt 3 / When er die Wettermetriken öffnet (aktive Liste UND „hinzufügen/Off-Shelf"-Liste) / Then erscheint „Sicherheit" nirgends — weder vorausgewählt noch als wählbare/hinzufügbare Metrik.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer — Editor und Wizard öffnen, sicherstellen dass kein Element mit Label/Text „Sicherheit" in den Metrik-Listen vorhanden ist.

- **AC-3:** Given ein Trip mit Vorhersagedaten, deren `confidence_pct` zeitweise < 60 % liegt / When der E-Mail-Report und der SMS-Report gerendert werden / Then enthält die E-Mail weiterhin den Hinweis „Ab {Wochentag} ist die Vorhersage weniger verlässlich." und das SMS-Symbol bleibt unverändert (Ausgabe byte-identisch zum Stand vor der Änderung).
  - Test: Echter Render-Lauf mit einem Fixture-Trip mit niedriger confidence; Golden-Vergleich der E-Mail-/SMS-Ausgabe vor vs. nach der Änderung (identisch).

- **AC-4:** Given ein gespeicherter Trip, dessen `display_config` eine **aktivierte** `confidence`-Metrik enthält (Bestandsdaten) / When der Trip geladen und erneut gespeichert wird / Then lädt der Trip fehlerfrei, die `confidence`-Metrik wird still ignoriert, und alle übrigen Metriken/Felder bleiben unverändert erhalten (kein Datenverlust).
  - Test: Roundtrip-Verhalten gegen echte Persistenz — Bestands-`display_config` mit aktiviertem `confidence` laden, speichern, neu laden; beobachtbares Ergebnis: Ladevorgang wirft keinen Fehler, die Menge der übrigen aktivierten Metriken ist vor und nach dem Roundtrip dieselbe, und keine zuvor gespeicherten Metrik-Einstellungen sind verschwunden.

- **AC-5:** Given ein neuer Trip im Wizard ohne vorbelegte Wettermetriken / When Schritt 3 die Metriken erstmalig aus dem Katalog befüllt / Then werden Metriken mit `default_enabled == false` **nicht** vorausgewählt (Schalter „aktiv" aus), entsprechend dem Backend-Flag.
  - Test: Playwright-E2E gegen Staging — neuen Trip starten, Schritt 3 öffnen, prüfen dass keine Opt-in-Metrik fälschlich aktiviert ist.

- **AC-6:** Given die Metrik-Vorschau (WeatherV2MailPreview) im „Einfach"-Modus / When CAPE mit den Beispielwerten dargestellt wird / Then zeigt die Zelle die Ampel-Emojis (🟢/🟡/🟠/🔴) gemäß den `fmt_val`-Schwellen — statt des Textes „nied.".
  - Test: Playwright-E2E gegen Staging — Metrik-Vorschau im Einfach-Modus öffnen, CAPE-Zelle enthält ein Ampel-Emoji, keinen Text „nied.".

- **AC-7:** Given die „Einfach"-Vorschau / When Bewölkung (cloud_total/low/mid/high) und Sonnenschein dargestellt werden / Then zeigen die Zellen die passenden Wolken-/Wetter-Emojis (☀️🌤️⛅🌥️☁️ bzw. Sonnen-Emoji) — inkl. der zuvor fehlenden „Einfach"-Werte für tiefe/mittlere/hohe Wolken und Sonnenschein.
  - Test: Playwright-E2E gegen Staging — Vorschau im Einfach-Modus, Wolken- und Sonnenschein-Zellen enthalten Emojis statt Roh-Zahlen/Leerwerte.

- **AC-8:** Given eine Metrik, deren echtes „Einfach"-Rendering Text ist (Sichtweite) / When sie in der „Einfach"-Vorschau dargestellt wird / Then zeigt die Vorschau weiterhin den Text-Indikator — die Vorschau spiegelt das tatsächliche Renderer-Verhalten und stellt nicht fälschlich ein Emoji dar.
  - Test: Playwright-E2E gegen Staging — Sichtweite-Zelle im Einfach-Modus zeigt Text, kein Emoji.

- **AC-9:** Given ein Nutzer betrachtet die E-Mail-Vorschau im Trip-Editor / When die Vorschau gerendert wird / Then ist sie durch ein sichtbares Label/Hinweis eindeutig als Beispieldaten/Vorschau gekennzeichnet, sodass sie nicht für eine echte Etappe gehalten werden kann.
  - Test: Playwright-E2E gegen Staging — Vorschau enthält sichtbaren „Beispieldaten"-/„Vorschau"-Hinweis am Vorschau-Block.

- **AC-10:** Given die E-Mail-Vorschau / When der Etappen-Titel der Vorschau dargestellt wird / Then steht dort eine erkennbar generische Beispiel-Bezeichnung statt eines realistischen fremden Etappennamens („Hochweißsteinhaus → Wolayersee" / „KHW 403").
  - Test: Playwright-E2E gegen Staging — Vorschau zeigt keine realistische fremde Etappe; Titel ist als Beispiel erkennbar.

## Known Limitations

- „Sicherheit" wird bewusst **nicht physisch** aus dem internen Katalog gelöscht (Berechnung/Aggregation/Forecast-Hinweis hängen daran) — sie wird nur aus der **user-sichtbaren Auswahl** entfernt. Dies ist die dauerhafte, dokumentierte Regel (siehe unten).
- Die #711-Vorschau spiegelt die Renderer-Schwellen über statische Beispielwerte (frontend-only); sie ruft nicht den Python-Renderer auf. Bei künftigen Schwellen-Änderungen in `helpers.py` müssen die Vorschau-Emojis mitgezogen werden.

## PO-Regel (dauerhaft, Issue #710)

**„Sicherheit" (`confidence`, Vorhersage-Verlässlichkeit) ist KEINE pro-Etappe wählbare Wetter-Metrik.** Sie ist eine Meta-Aussage über die Verlässlichkeit der mehrtägigen Vorhersage (Quelle: Open-Meteo **Ensemble-API**) und darf ausschließlich als Vorhersage-Verlässlichkeits-Hinweis (E-Mail-Hinweis + SMS-Symbol) erscheinen — **nie** wieder als auswählbare Metrik im Katalog/Editor/Wizard. PO-Entscheidung 2026-06-10. Diese Regel verhindert das wiederholte „Auftauchen" der Metrik (zuvor #424, #710).

## Changelog

- 2026-06-10: Paket #715 IMPLEMENTIERT — #710 Sicherheit (confidence) aus `/api/metrics`-Katalog entfernt (nicht-selektierbar gekennzeichnet); #711 Emoji-Vorschau in WeatherV2MailPreview + Step3Weather angepasst (Daten-Beispiele mit echten Emojis); #712 Beispieldaten-Kennzeichnung mit Badge und generischer Etappen-Beschreibung. Backend-Änderung: `MetricDefinition.selectable: bool = True` (confidence=False), `get_all_metrics()` filtert auf `selectable`. Frontend: Vorschau-Metriken aktualisiert, `default_enabled` vom Katalog geerbt.
- 2026-06-10: Initial spec created (Paket #715: #711 Emoji-Vorschau, #710 Sicherheit aus Metrik-Auswahl, #712 Beispieldaten-Kennzeichnung).
