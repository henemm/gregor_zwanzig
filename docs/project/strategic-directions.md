# Entwicklungsrichtungen Gregor Zwanzig

**Erstellt:** 2026-02-16
**Status:** Approved

## Context

Gregor Zwanzig ist ein ausgereiftes MVP mit vollstaendigem Trip-to-Email-Pipeline. Diese Analyse identifiziert sinnvolle Erweiterungen aus der Perspektive eines **fortgeschrittenen Wanderers** (Sommer-Trekking + Winter-Skitouren). Der User will **Daten statt Ratschlaege** — keine paternalistischen Empfehlungen, sondern kompakte Fakten zur eigenen Entscheidung.

---

## Konsolidierte Feature-Liste (nach User-Feedback)

### Prioritaet 1 — Hoher Impact, machbar

| # | Feature | Beschreibung | Aufwand |
|---|---------|-------------|---------|
| **F1** | **SMS-Kanal** | Wetter-Reports per SMS. Auf GR20/GR221 oft kein Internet, nur GSM. Game-Changer fuer Kernzielgruppe. | Mittel |
| **F2** | **Kompakt-Summary** | 3-5 Zeilen Kurzfassung oben in der Email (+ SMS-Format). Sofort erfassbar bei 30s Empfang. Nicht als Ersatz, als Ergaenzung zum vollen Report. | Gering |
| **F3** | **Multi-Day Trend** | Naechste 3-5 Tage als Trend-Block im Evening-Report: `Mo☀️18° Di🌤15° Mi🌧12°⚠️ Do☀️16°`. Fuer Mehrtages-Strategie und Ruhetag-Planung. | Gering |
| **F4** | **Trip-Briefing (Kompakt-Tabelle)** | Einmaliger Report am Vorabend: Alle Etappen auf einen Blick als Tabelle (Tag \| Temp \| Wind \| Regen \| Besonderheit). Kein Prosa, reine Daten. | Mittel |
| **F5** | **Biwak-/Zelt-Modus** | Pro Etappe Uebernachtungstyp (Huette/Zelt/Biwak) einstellbar. Bei Zelt/Biwak: Erweiterter Night-Block mit Frost-Grenze, Tiefsttemp, Wind nachts, Niederschlag-Zeitfenster, Aufbau-Fenster. | Gering-Mittel |
| **F6** | **Trip-Umplanung per Kommando** | Per SMS/Email-Reply sagen: "Ruhetag heute" → Gregor verschiebt alle Folge-Etappen +1 Tag. Asynchrone Steuerung ohne Web-UI. Passt perfekt zum Low-Connectivity-Paradigma. | Mittel-Hoch |

### Prioritaet 2 — Strategisch, mittelfristig

| # | Feature | Beschreibung | Aufwand |
|---|---------|-------------|---------|
| **F7** | **Wind-Exposition (Grat-Erkennung)** | Aus GPX-Profil exponierte Abschnitte (Grat, Gipfel) erkennen. Wind-Warnung fuer diese Segmente verschaerfen. Differenzierung: 40 km/h im Wald ≠ 40 km/h am Grat. | Mittel |
| **F8** | **Risk Engine (Daten-Layer)** | Risiko-Kategorisierung (low/med/high) pro Metrik — OHNE Handlungsempfehlung. Draft-Spec existiert. Als Grundlage fuer Ampel-artige Darstellung in Reports. | Hoch |
| **F9** | **Satellite Messenger (Garmin inReach)** | Wetter-Alerts per Satellit. Setzt Kompakt-Format (F2) voraus. Garmin inReach hat Email-Bridge (160 Zeichen). Fuer echte Wildnis ueber Baumgrenze. | Gering* |

*\*wenn F2 steht, ist der Formatter schon da*

### Prioritaet 3 — Langfristig

| # | Feature | Beschreibung | Aufwand |
|---|---------|-------------|---------|
| **F10** | **Lawinen-Integration** | SLF/EAWS Adapter fuer Skitouren. Datenmodell hat bereits `avalanche_regions`. Naechste Wintersaison. | Hoch |

### Gestrichen

| # | Feature | Grund |
|---|---------|-------|
| ~~A2~~ | ~~Go/No-Go Ampel~~ | Zu simpel fuer Fortgeschrittene |
| ~~A3~~ | ~~Timing-Empfehlungen~~ | Zu paternalistisch, User rechnet selbst |
| ~~B4~~ | ~~Elevation-Korrektur~~ | OpenMeteo korrigiert bereits automatisch (Copernicus DEM + Lapse Rate) |
| ~~B5~~ | ~~POI-Integration~~ | Daten-Problem, Fortgeschrittene kennen Route |
| ~~C3~~ | ~~Trip-Sharing~~ | Nice-to-have, kein Kern-Feature |
| ~~C4~~ | ~~Wetter-Tagebuch~~ | Kein Bedarf |

---

## Empfohlene Reihenfolge

```
F2 Kompakt-Summary ──→ F1 SMS-Kanal ──→ F9 Satellite Messenger
     (Gering)              (Mittel)          (Gering, baut auf F2)

F3 Multi-Day Trend        F5 Biwak-Modus
     (Gering)              (Gering-Mittel)

F4 Trip-Briefing ────→ F8 Risk Engine (Daten-Layer)
     (Mittel)              (Hoch, enabler fuer F7)

F6 Trip-Umplanung ───→ F7 Wind-Exposition
     (Mittel-Hoch)         (Mittel)

                       F10 Lawinen (Wintersaison)
```

**Quick Wins zuerst:** F2, F3, F5 sind gering im Aufwand und sofort nuetzlich.
**Strategische Kette:** F2 → F1 → F9 baut den SMS/Satellit-Kanal schrittweise auf.
**F6 (Umplanung per Kommando)** ist das innovativste Feature — asynchrone Trip-Steuerung ohne UI.

---

## Strategische Entscheidung: Tech Stack Migration (2026-04-08)

**Entscheidung:** Migration von Python/NiceGUI auf Go (Backend) + SvelteKit (Frontend)

**Treiber:** AI-gestuetzte Entwicklung mit Python produziert zu viele Fehler (dynamische Typen, NiceGUI-Magie, Import-Probleme). Go's Compile-Time Safety und SvelteKit's konsistente Trainingsdaten reduzieren die Fehlerrate signifikant.

**Details:** `docs/project/backlog/stories/sveltekit-migration.md`

**Epic:** `docs/project/backlog/epics.md` → "Tech Stack Migration"

---

## Kern-Erkenntnis

Gregor Zwanzig differenziert sich nicht durch MEHR Daten oder durch Empfehlungen, sondern durch **die richtige Information im richtigen Moment ueber den richtigen Kanal**:

1. **Kompakt** — 30 Sekunden reichen um alles Wichtige zu erfassen
2. **Asynchron** — Reports kommen zum User, nicht umgekehrt
3. **Low-Connectivity** — SMS und Satellit statt nur Email
4. **Steuerbar** — Trip unterwegs per Kommando anpassen
5. **Kontextbezogen** — Nacht-Details nur fuer Zelter, Grat-Wind nur wo relevant
