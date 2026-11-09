# ADR-0109: Der Hub von Trip und Orten hat vier Reiter — Übersicht · Etappen/Orte · Wetter · Zustellung; Wertebereiche, Layout, Alarme und Versand gehen darin auf

- **Status:** Akzeptiert (PO 2026-11-08, Analyse #2794)
- **Datum:** 2026-11-03
- **Bezug:** Epic #2791, Scheiben S3a #2794, S3b #2795, S5 #2797, Kontext `docs/context/einstellungen_neu.md` §2, §5, §7; Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (vom PO angenommen 2026-11-03); präzisiert ADR-0097 Punkt 1 (die geteilten Tab-Organismen heißen künftig Wetter und Zustellung statt Wertebereiche/Layout/Versand); bestätigt ADR-0032 (progressive Reiter mit Auto-Save), ADR-0050 (Grundauswahl ist das Maximum), ADR-0059 (Ausblick verhält sich wie ein Kanal), ADR-0035 (ein Tagesfenster); hängt an ADR-0106. Bisher gab es kein Design-ADR zur Reiterstruktur (`docs/specs/modules/feat_1743_reiter_aufraeumen.md:486`).

## Kontext

Die heutigen Reiter Wertebereiche, Layout, Alarme und Versand bilden technische Mechanismen ab (Markierung, Renderer-Auswahl, Δ-Wächter, Versandplan), nicht die Fragen des Nutzers. Dieselbe Metrik steht an bis zu drei Stellen. Die Reiterleiste weicht vom Atomic-Design-Soll ab (`frontend/src/lib/components/mobile/MTabBar.svelte:82` erbt die Segmented-Box aus `frontend/src/app.css:502-528`, Badges als orange Kreise).

## Entscheidung

1. **Vier Reiter, gleich für Trip und Orte:** Übersicht · Etappen (Trip) bzw. Orte · **Wetter** · **Zustellung**. Es gibt keinen Reiter Wertebereiche, Layout, Alarme, Versand oder Vorschau.
2. **Wetter** beantwortet „was interessiert mich, was ist für mich kritisch, ab wann will ich einen Alarm“: Vorlage, Metrik-Zeilen mit Ampel-Leiste und „Alarm ab“ (ADR-0106), „Nicht im Briefing“, amtliche Warnungen und Radar-Regen, **„Inhalt je Kanal und Fläche“** und „Anpassen“ (Tagesfenster).
3. **„Inhalt je Kanal und Fläche“** hat je Kanal und Fläche eine eigene, sichtbare Liste: E-Mail · Telegram · SMS · Premium-SMS · 3-Tages-Ausblick · (Orte) Stundenverlauf. Jede Liste ist eine Teilmenge der Metrik-Zeilen (abwählen ja, hinzufügen nein). Je Zeile gibt es Reihenfolge, Roh/Einfach und an/aus. Die Liste steht in jedem Kanal-Reiter an derselben Stelle. Kanalweite Einstellungen und Erklärsätze stehen darunter im eingeklappten Feld „Weitere Einstellungen für {Kanal}“ (Mail-Format und Zusatzblöcke, Telegram-Kurzstil für Briefing und Alarme, Ausblick morgens/abends, Stundenverlauf an/aus).
4. **Der 3-Tages-Ausblick hat einen Namen und eine Stelle.** „Mehrtages-Trend“, „Ausblick“ und „3-Tages-Vorschau“ entfallen als Begriffe. Die drei heutigen Steuerstellen (`show_outlook`, `multi_day_trend_reports`, `outlook_metrics`) werden zu einer: der Liste „3-Tages-Ausblick“ mit „erscheint im Morgen-/Abend-Briefing“, Vorbelegung nur abends.
5. **Zustellung** beantwortet „wann und auf welchem Weg erreicht ihr mich“: Morgen-/Abend-Briefing mit Uhrzeitfeld (ohne Schnellwahl), Laufzeit, Kanal-Tabelle (Briefing · Alarme · Alarm schon ab Dringlichkeit) mit Verbindungsstatus und Sperrgründen, Stille Stunden und „Anpassen“ (Mindestabstand zwischen zwei Alarmen).
6. **Keine Vorschau.** „Senden“ wird **„Test schicken ▾“**: ein Menü am Knopf mit Kanälen (Ziel, Sperre mit Grund), beim Trip Morgen/Abend, „Alle eingerichteten Kanäle“ und „Test-Alarm“. Daneben bleibt das Kebab (Pausieren, Archivieren, Löschen, Aktivieren).
7. **Reiterleiste nach Atomic-Design-Soll** (`claude-code-handoff/current/jsx/`, `docs/design-system/TOKENS.md`): eine Grundlinie `--g-rule`, Reiter 13px/500, aktiv 600 mit 2px-Unterstrich `--g-accent`, Badges mono 10px neutral. Mobil bleibt die freigegebene Pill-Leiste (`docs/specs/modules/mobile_tab_leisten_mtabbar.md`).
8. Alte Adressen (`?tab=wertebereiche`, `?tab=alarme`, `?tab=versand`, `?tab=layout`) leiten auf Wetter bzw. Zustellung um.

## Verworfene Alternativen

- **Wetter · Alarme · Zustellung:** Alarme mit eigenem Reiter. Dann steht dieselbe Metrik wieder an zwei Stellen.
- **Ein Reiter „Einstellungen“:** am wenigsten Klicks, aber eine sehr lange Seite.
- **Eine Liste für alle Kanäle** (automatisch nach Alarmstufe sortiert, oder eine von Hand sortierte Liste): Der PO will die Liste je Kanal sichtbar behalten (Karte `kanal_inhalt`: „wie heute“).

## Konsequenzen

- **Positiv:** Zwei Fragen, zwei Reiter. Trip und Orte bleiben ein Code (ADR-0097). Die Reiterleiste entspricht dem Soll.
- **Negativ / Preis:** Die Tab-Organismen unter `frontend/src/lib/components/shared/` werden neu geschnitten. `CorridorEditor`, `AlarmeTab`, der Versand-Reiter und der tote Alarm-Bündel-Code (`alerts-tab/`) entfallen. Texte und Links in Übersicht, Hilfe und Onboarding müssen nachgezogen werden.
- **Folgepflichten:** Alle neuen Texte in DE und EN (ADR-0104). Compare-eigen bleiben nur Orte-Reiter, transponierte Übersicht und Compare-Mail (ADR-0097). Die Pendant-Sperre gilt: keine neue Compare-Komponente mit Trip-Pendant.
