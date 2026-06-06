# Design-Anfrage: EIN Trip-Pfad — Wizard mit Trip-bearbeiten-v2 harmonisieren

**Angefordert von:** PO Henning (2026-06-05), über Claude Code
**Priorität:** Hoch — blockiert die saubere Umsetzung des Pakets „Trip bearbeiten" (config-change-flow)
**Anker (verbindlich, neuer Stand):** `screen-trip-edit-v2-main.jsx`, `screen-trip-edit-v2-weather.jsx`, `screen-trip-edit-v2-mobile.jsx`
**Abweichend (alt):** `screen-trip-wizard.jsx`, `screen-trip-wizard-mobile.jsx`

## Anliegen des PO

> „Es soll am Ende nur noch einen Trip-Pfad geben. Stelle sicher, dass es keinen
> Misch-Masch zwischen alt und neu gibt. Stelle auch sicher, dass der Wizard zum
> Neu-Erstellen von Trips in dieses Konzept passt."

Erstellen (Wizard) und Bearbeiten (Trip-Editor) müssen **dieselbe Struktur und
dasselbe Datenmodell** nutzen. Aktuell sind es zwei nicht zusammenpassende Konzepte.

## Festgestellte Divergenzen (Wizard ALT vs. Trip-Edit-v2 NEU)

| # | Aspekt | Wizard (alt, Stand 2026-05-27) | Trip-Edit-v2 (neu, „Signal-frei", 2026-06-05) |
|---|--------|--------------------------------|-----------------------------------------------|
| 1 | **Kanäle** | Email · Telegram · **Signal** · SMS (Signal max 6) | Email · Telegram · SMS — **kein Signal**, Telegram max 8 |
| 2 | **Metrik-Format-Modell** | 4 Formate **pro Metrik**: Roh / Skala / Vereinfacht / Symbol | **Bucket** (primary/secondary/off) + **Mode** (raw / indicator) — 2 Modi |
| 3 | **Struktur** | 2 getrennte Schritte: „Wetter" (Auswahl) + „Layout" (Reihenfolge/Spalten pro Kanal); **keine** Live-Mail; **kein** Alerts-Schritt | **Ein** „Wetter-Metriken"-Tab (Auswahl + Reihenfolge + Kanäle + **Live-Mail-Vorschau** + Telegram-Schnittlinie); Alerts als eigener Tab |
| 4 | **Vorschau** | separate Kanal-Previews ohne Diff | durchgehende Live-Mail mit Diff-Highlight pro Änderung |

Divergenz #2 berührt zusätzlich ein bereits ausgeliefertes Feature: das
Metrik-Format-System aus Issue #435 nutzt 4 Format-Modi (raw/scale/simplified/symbol),
während Trip-Edit-v2 nur raw/indicator kennt. Dieser Widerspruch muss aufgelöst werden —
**ein** Modell für die gesamte App.

## Bitte um Nacharbeit

Bitte einen **harmonisierten Wizard-Entwurf** liefern, der auf Trip-Edit-v2 ausgerichtet ist:

1. **Signal entfernen** — Kanäle überall Email · Telegram · SMS (PO-Entscheidung 2026-06-05, app-weit).
2. **Ein Metrik-/Format-Modell** für Wizard UND Editor festlegen — bitte explizit klären,
   wie sich das v2-Modell (bucket + raw/indicator) zum ausgelieferten 4-Format-Modell (#435)
   verhält: aufgehen, ersetzen oder beide abbilden? Das Ergebnis ist verbindlich für beide Pfade.
3. **Wizard-Wetterschritt = der v2-„Wetter-Metriken"-Abschnitt** (geteilte Bauteile:
   Grundauswahl · Reihenfolge & Darstellung mit Telegram-Schnittlinie · Kanäle · Live-Mail),
   statt eigener Wetter+Layout-Schritte. So entsteht genau ein Satz Komponenten.
4. **Struktur-Kohärenz** zwischen Schritten (Erstellen) und Tabs (Bearbeiten) festlegen,
   inkl. wo Alerts und Briefing-Zeitplan im Erstellen-Fluss sitzen.
5. **Mobile** entsprechend nachziehen.

Ziel: Nach Umsetzung gibt es **eine** Wetter-Metriken-/Kanal-/Vorschau-Komponente,
die Wizard und Editor teilen — kein paralleler alter Pfad.

## Bezug
Paket „Trip bearbeiten": #587 (Wetter-Metriken-Tab v2), #616 (Tab-IA), #617 (Kanal-Verkettung),
#618 (Mobile), #610 (Signal app-weit entfernen). Wizard-Fidelity bisher: #584. Format-Modi: #435.

---

## Auflösung / PO-Entscheidung (2026-06-06)

Claude Design hat die harmonisierten Quellen geliefert: `docs/design-requests/trip-anlegen-2026-06-06/`
(`screen-trip-edit-v2-{main,weather,mobile}.jsx`, `screen-trip-new-v2{,-mobile}.jsx`,
`body-24-trip-new-progressive-editor.md`). Damit sind die fünf Auftragspunkte wie folgt geklärt:

1. **Signal entfernen** — ✅ erledigt (Design Signal-frei; Code app-weit raus via #610).
2. **Ein Metrik-/Format-Modell (Verhältnis zu #435)** — ✅ **entschieden (PO, 2026-06-06):**
   Die App nutzt künftig **ein** Modell mit nur noch **zwei** Anzeige-Modi in der Oberfläche:
   **Roh** (`raw`) und **Einfach** (`simplified`). Die bisher aus #435 ausgelieferten Modi
   **Skala** (`scale`) und **Symbol** (`symbol`) werden **stillgelegt** (nicht mehr in der UI
   angeboten). **Bestandsdaten:** Touren, die heute auf `scale` oder `symbol` stehen, werden auf
   den **`default_format_mode` der jeweiligen Metrik** zurückgesetzt (vorhandene Fallback-Logik
   `loader._resolve_format_mode` / `MetricConfig.format_mode = None`). Kein willkürliches Mapping,
   kein Datenverlust. Verbindlich für Erstellen- UND Bearbeiten-Pfad.
3. **Wetterschritt = geteilte v2-Komponente** — ✅ erledigt (Design-Doc C6: Tabs 4–6 sind
   *dieselben* Svelte-Komponenten wie im Edit-Flow; festgehalten in #622-Spec AC-6).
4. **Struktur-Kohärenz (Alerts/Zeitplan-Position)** — ✅ erledigt (vollständige Tab-Struktur +
   progressiver Lock-State in `body-24-trip-new-progressive-editor.md`).
5. **Mobile** — 🟡 Bearbeiten-Mobile als #618 spezifiziert; Erstellen-Mobile bewusst auf V1.5
   vertagt (Mockup `screen-trip-new-v2-mobile.jsx` liegt bereits vor).

**Umsetzungs-Folge:** Die Design-/Entscheidungs-Ebene (#620) ist damit abgeschlossen. Die
tatsächliche Code-Umstellung (Skala/Symbol aus UI entfernen + datensichere Migration der
Bestandskonfigurationen mit Roundtrip-Test gemäß Schema-Rework-Regel) läuft als eigenes
Umsetzungs-Issue **#629**, verzahnt mit #587. #620 ist mit dem Festhalten dieser Entscheidung
abgeschlossen.
