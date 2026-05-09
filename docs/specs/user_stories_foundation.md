---
entity_id: user_stories_foundation
type: product-requirements
created: 2026-05-09
updated: 2026-05-09
status: approved
version: "1.1"
tags: [product, vision, user-stories, epics, frontend]
---

# User Stories — Gregor Zwanzig Foundation

Diese drei User Stories bilden die **produktstrategische Grundlage** für alle Frontend-Epics (#133–#140). Sie entstammen dem Claude-Design-Prozess und beschreiben, was der Nutzer als kohärentes System erlebt — unabhängig davon, in welchem Epic die technische Umsetzung landet.

---

## US-1: Geografische & Zeitliche Kontrolle (Der Workspace)

> **Als Tourenplaner**
> möchte ich meine GPX-Tracks importieren und die vom System errechneten Wegpunkte und Ankunftszeiten auf einer Karte kontrollieren, anpassen sowie Pausentage einschieben können,
> damit das System mein exaktes Bewegungsprofil kennt und die späteren Wetterabfragen räumlich und zeitlich präzise mit meinem realen Standort auf dem Berg übereinstimmen.

### Kernversprechen
Das System fragt nicht am Berg — es wurde zuhause präzise konfiguriert. Die Wetterabfrage trifft mich räumlich und zeitlich genau dort, wo ich sein werde.

### Epic-Abdeckung
| Epic | Beitrag |
|------|---------|
| #136 Trip-Wizard | Step 2 (GPX-Multi-Import, drag-sortierbar, Pausentag) + Step 3 (algorithmisch berechnete Wegpunktvorschläge bestätigen/verwerfen) |
| #137 Wegpunkt-Editor | Visuelles Editieren auf Karte + Höhenprofil (ohne Lat/Lon-Eingabe), Etappen-Strip drag-sortierbar |
| #135 Trip-Übersicht | Hero zeigt aktive Etappe (heutiger Tag) + ElevSparkline → Feedback: "Das System kennt meinen Standort" |

### Implizite Anforderungen
- Wegpunktvorschläge (Wetterscheiden) werden **algorithmisch berechnet** — aus GPX-Profil (Höhenpunkte, Exponiertheit, Etappenlänge), nicht per KI/ML
- Vorschläge sind orange gestrichelt dargestellt — User bestätigt oder verwirft, manuelle Punkte sind voll
- Kein Lat/Lon-Interface — alles visuell
- Pausentag = leere Etappe (kein GPX, nur Standort)
- **Ankunftszeiten werden vom System aus dem GPX errechnet** (Distanz + Höhenmeter → geschätzte Uhrzeit pro Wegpunkt) — nicht manuell eingetragen. Der User kann die berechneten Zeiten anpassen, nicht von Null eingeben.
- Zeitliche Präzision ist Kern-Versprechen: Wetterabfrage trifft den User räumlich und zeitlich genau dort, wo er sein wird

### Offene Frage zur Ankunftszeit-Berechnung (für Epic #136/#137)
Das aktuelle Backend-Datenmodell (`Stage.start_time`, `Waypoint.time_window`) speichert Zeiten als manuelle Felder. Die automatische Berechnung aus GPX (Pace-Schätzung, Höhenmeter-Zuschlag nach Naismith's Rule o.ä.) fehlt noch im Backend. Vor Implementierung von Epic #136 muss geklärt werden:
- Welche Berechnungsmethode (Naismith, Swiss Formula, individuell)?
- Speicherung: berechnete Zeit als eigenes Feld `calculated_arrival` neben manuellem `time_window`?
- Wird die Berechnung server-seitig beim GPX-Import getriggert?

---

## US-2: Präzise Metrik-Kontrolle (Die Wetter-Konfiguration)

> **Als erfahrener Bergsportler**
> möchte ich die abzufragenden Wettermetriken für meinen Trip exakt definieren – entweder indem ich ein etabliertes Basis-Profil als Startpunkt wähle oder die Datenpunkte komplett individuell zusammenstelle,
> damit ich genau die Rohdaten und Indikatoren (z.B. CAPE-Werte, Nullgradgrenze) erhalte, auf denen meine persönliche alpine Risikobewertung basiert, ohne vom System bevormundet oder auf Basic-Wetterdaten reduziert zu werden.

### Kernversprechen
Keine Bevormundung. Rohdaten wenn gewollt, Indikatoren wenn praktischer — der erfahrene Bergsportler trifft selbst die Risikobewertung.

### Epic-Abdeckung
| Epic | Beitrag |
|------|---------|
| #138 Wetter-Metriken-Editor | 26 Metriken in 5 Gruppen, 7 builtin-Presets (Alpen-Trekking, Skitouren …), Roh/Indikator pro Metrik, eigene Presets speicherbar |
| #136 Trip-Wizard | Step 1: Aktivitätsprofil wählen (setzt initiales Metriken-Set) |

### Implizite Anforderungen
- Preset ist **Startpunkt**, nicht Zwang — alles überschreibbar
- Roh-Wert (`2447 J/kg`) UND Indikator (`hoch`) pro Metrik wählbar
- 12 Metriken mit Skala-Mapping (Wind, CAPE, Nullgrad etc.)
- Eigene Presets speicherbar (kein Mapping auf builtin erzwungen)

---

## US-3: Das Autarke Briefing-System (Die Report-Konfiguration)

> **Als Alpinist auf einer mehrtägigen Tour mit limitiertem Empfang**
> möchte ich einmalig für den gesamten Trip konfigurieren, an welche Kanäle (z.B. Signal für kurze Alerts, E-Mail für detaillierte 5-Tage-Trends) und zu welchen festen Uhrzeiten das System seine Berichte sendet,
> damit ich mich in der Wildnis darauf verlassen kann, dass die rettungswichtigen Informationen genau dann auf meinem Gerät eintreffen, wenn ich mein kurzes Empfangsfenster auf der Hütte habe.
>
> Zusätzlich möchte ich harte Schwellenwerte definieren (z.B. Windzunahme > 20km/h),
> damit das System im Hintergrund als mein "Wachhund" fungiert und mich nur dann aktiv warnt, wenn sich die Bedingungen relevant gegen meine ursprüngliche Planung verschlechtern.

### Kernversprechen
Einmal konfigurieren, dann vertrauen. Das System läuft autonom — der Alpinist muss auf dem Berg nicht aktiv werden. Der "Wachhund" warnt nur bei echten Veränderungen, nicht bei Rauschen.

### Epic-Abdeckung
| Epic | Beitrag |
|------|---------|
| #136 Trip-Wizard | Step 4: Kanäle aktivieren (E-Mail, Signal, SMS …) + Uhrzeiten + initiale Alert-Schwellen |
| #139 Alert-Konfigurator | Detailkonfiguration: Δ-Modus (Änderung seit letztem Report) + Absolut-Schwellen, 9 Metriken |
| #140 Output-Vorschau | Email-Vollansicht + SMS-Phone-Frame — "So sieht mein Briefing aus" |
| #134 Startseite | Briefings-Timeline (wann geht das nächste raus?) + Alert-Feed (hat der Wachhund angeschlagen?) |
| #135 Trip-Übersicht | Briefing-Zeitplan-Card + Alert-Card mit Zähler-Badge |

### Implizite Anforderungen
- Kanäle sind kanal-spezifisch pro Report-Typ konfigurierbar (nicht alle Kanäle kriegen alles)
- Δ-Modus und Absolut-Schwellen können **gleichzeitig** aktiv sein (empfohlen)
- "Wachhund" = kein Ping bei Rauschen — nur bei echten Schwellenüberschreitungen
- Autark = nach einmaliger Konfiguration kein manuelles Eingreifen nötig

---

## System-Zusammenhang (alle 3 User Stories)

```
US-1 (Workspace)          →  räumlich+zeitlich präzise Daten
US-2 (Metriken)           →  inhaltlich relevante Daten
                                    ↓
                         Briefing-Payload
                                    ↓
US-3 (Autarkes System)   →  zuverlässig + pünktlich + kanalgerecht zugestellt
                                    ↓
                    Trip-Übersicht / Cockpit (Epic #134/#135)
                    zeigt: Was ist heute? Was geht raus? Hat der Wachhund angeschlagen?
```

**Implementierungsreihenfolge:** Startseite/Cockpit (Epic #134/#135) kommt nach den Konfigurations-Epics (#136–#139), da der Cockpit den Output dieser Konfigurationen darstellt — er ist sinnlos ohne funktionierende Workspace-, Metriken- und Briefing-Konfiguration.
