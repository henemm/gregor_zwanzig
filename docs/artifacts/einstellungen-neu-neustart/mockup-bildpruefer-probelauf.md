# Probelauf mockup-bildpruefer (AC-16, #2913)

**Datum:** 2026-11-10 · **Runde:** 1 (Probelauf, keine Scheibe) · **Modell:** sonnet · **Werkzeug:** nur Read

## Eingaben (fest)

| Eingabe | Inhalt |
|---|---|
| Mockup-Bild | `mockup-hub-fassung3.html` gerendert, Trip · normal · Reiter Wetter, 1280 × 3531 px |
| Staging-Bild | https://staging.gregor20.henemm.com, Trip-Hub (kurzlebiger Prüf-Trip `e2e-2913-bildpruefer`, danach gelöscht), Reiter Wetter, normal, 1280 × 3531 px |
| Elementlisten-Auszug | Einträge aus `docs/context/einstellungen_neu/elementliste.json` mit `ctx=trip`, `reiter=wetter`, `zustand=normal`, Segment E-Mail |

Gelesen hat der Agent laut eigener Angabe nur: die Agent-Definition, die beiden Bilder und den Auszug. Kein Quellcode, keine Suche, keine Shell.

## Erwartung

Scheibe (a) ist noch nicht gebaut; Staging zeigt den alten Wetter-Reiter. Erwartet sind daher Abweichungen in nahezu allen Abschnitten. Geprüft wird, ob der Agent (1) nur aus den Eingaben urteilt, (2) im festen Ausgabeformat antwortet und (3) Abweichungen an den Abschnitten des Auszugs festmacht.

## Befund des Agenten (wörtlich übernommen, gekürzt auf die Tabelle)

| Nr. | Abschnitt | Mockup zeigt | Staging zeigt | Schwere |
|---|---|---|---|---|
| 1 | vorlage | Karte „VORLAGE“ mit „Alpen-Trekking ▾ unverändert“ und „Als eigene Vorlage speichern“ | „01 — PROFIL“ mit Profil-Chips | hoch |
| 2 | metriken | Karte „Alarm ab für alle“, Metrik-Zeilen mit Ampel-Leiste, „Alarm ab“, „Grenzen ändern“ | „02 — GRUNDAUSWAHL“ und „04 — SCHWELLWERTE“ (Sensibel/Standard/Robust) | hoch |
| 3 | metriken (Gruppen) | Temperatur, Wind, Niederschlag & Gewitter, Himmel & Sicht, Schnee & Höhe | andere Gruppen nur in der Grundauswahl | hoch |
| 4 | metriken (Nicht im Briefing) | „Nicht im Briefing:“ mit „+“-Chips | „Metrik hinzufügen:“ an anderer Stelle | mittel |
| 5 | warnungen-radar | Schalter-Karte Amtliche Warnungen / Radar-Regen | nur Kontrollkästchen „Amtliche Warnungen im Bericht“, kein Radar | hoch |
| 6 | kanal-inhalt (E-Mail) | Karte „Inhalt je Kanal und Fläche“ mit Segment und 13 Zeilen | nicht vorhanden | hoch |
| 7 | anpassen | eingeklappte Karte „Anpassen“ | Tagesfenster offen als eigene Karte | hoch |
| 8 | abschnittskopf | „Wetter“ + Lead | fehlt, stattdessen „WERTEBEREICHE“ | mittel |
| 9 | kopf | „⋮“ und „Test schicken ▾“ | „Senden“ und „⋮“, zusätzliche Chip-Reihe | mittel |
| 10 | (zusätzlich) | — | App-Seitenleiste; als App-Rahmen nicht beurteilbar | niedrig |
| 11 | (zusätzlich) | — | Hinweiskarten „Wird gerade umgebaut“, „So liest sich ein Wertebereich“ u. a. | mittel |
| 12 | alle (Optik) | Ampelfarben, Akzent orange, grüne Schalter | ohne Ampelbalken, aktive Elemente schwarz/braun | hoch |

Gesamturteil des Agenten: „12 Befunde (davon 7 hoch).“

## Bewertung des Probelaufs

- **Eingabe-Disziplin:** erfüllt; der Befund stützt sich nur auf Bilder und Auszug, Unsicheres ist als „nicht beurteilbar“ markiert (Nr. 10).
- **Format:** Tabelle und Gesamturteil wie in der Definition.
- **Abschnittsbezug:** alle Befunde zu Listen-Elementen nennen den Abschnitt aus dem Auszug; Zusätzliches ist getrennt ausgewiesen.
- **Einschränkung:** Die Bilder werden dem Agenten verkleinert angezeigt (725 × 2000); Feinheiten sind bei ganzseitigen Aufnahmen nur eingeschränkt beurteilbar. Für die Scheiben daher je Abschnitt bzw. Bildschirmhöhe zuschneiden.
- Inhaltlich bestätigt der Probelauf den erwarteten Stand: Scheibe (a) steht aus. Die Befunde sind keine Mängel dieser Lieferung.
