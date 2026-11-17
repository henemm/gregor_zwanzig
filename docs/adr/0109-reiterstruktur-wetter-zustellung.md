# ADR-0109: Der Hub von Trip und Orten hat vier Reiter — Übersicht · Etappen/Orte · Wetter · Zustellung; Wertebereiche, Layout, Alarme und Versand gehen darin auf

- **Status:** Teilweise abgelöst durch ADR-0118 (Punkt 7: Handy-Pill-Leiste entfällt, Text-Reiter mit Unterstrich auf allen Breiten; Issue #2980) und durch [ADR-0124](0124-was-steht-wo-eine-tabelle.md) (Punkt 3: die Karte „Inhalt je Kanal und Fläche“ mit einer eigenen Liste je Kanal und Fläche entfällt, an ihre Stelle tritt eine Tabelle „Was steht wo“; Punkt 4 präzisiert; PO 2026-11-17, Issue #3122) — sonst Akzeptiert (PO 2026-11-08, Analyse #2794)
- **Datum:** 2026-11-03
- **Bezug:** Epic #2791, Scheiben S3a #2794, S3b #2795, S5 #2797, Kontext `docs/context/einstellungen_neu.md` §2, §5, §7; Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (vom PO angenommen 2026-11-03); präzisiert ADR-0097 Punkt 1 (die geteilten Tab-Organismen heißen künftig Wetter und Zustellung statt Wertebereiche/Layout/Versand); bestätigt ADR-0032 (progressive Reiter mit Auto-Save), ADR-0050 (Grundauswahl ist das Maximum), ADR-0059 (Ausblick verhält sich wie ein Kanal), ADR-0035 (ein Tagesfenster); hängt an ADR-0106. Bisher gab es kein Design-ADR zur Reiterstruktur (`docs/specs/modules/feat_1743_reiter_aufraeumen.md:486`).
- **Ergänzt durch:** ADR-0111 (Design-Vorgaben bereinigt, Issue #2881); [ADR-0124](0124-was-steht-wo-eine-tabelle.md) (präzisiert Punkt 4: die eine steuernde Stelle des 3-Tages-Ausblicks sind die Schalter „Morgen-Briefing“ und „Abend-Briefing“ unter der Tabelle, für Trip und Orte; Soll-Bild der Karte ist Mockup Fassung 4, `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`)

## Kontext

Die heutigen Reiter Wertebereiche, Layout, Alarme und Versand bilden technische Mechanismen ab (Markierung, Renderer-Auswahl, Δ-Wächter, Versandplan), nicht die Fragen des Nutzers. Dieselbe Metrik steht an bis zu drei Stellen. Die Reiterleiste weicht vom Atomic-Design-Soll ab (`frontend/src/lib/components/mobile/MTabBar.svelte:82` erbt die Segmented-Box aus `frontend/src/app.css:502-528`, Badges als orange Kreise).

## Entscheidung

1. **Vier Reiter, gleich für Trip und Orte:** Übersicht · Etappen (Trip) bzw. Orte · **Wetter** · **Zustellung**. Es gibt keinen Reiter Wertebereiche, Layout, Alarme, Versand oder Vorschau.
2. **Wetter** beantwortet „was interessiert mich, was ist für mich kritisch, ab wann will ich einen Alarm“: Vorlage, Metrik-Zeilen mit Ampel-Leiste und „Alarm ab“ (ADR-0106), „Nicht im Briefing“, amtliche Warnungen und Radar-Regen, **„Inhalt je Kanal und Fläche“** und „Anpassen“ (Tagesfenster).
3. **„Inhalt je Kanal und Fläche“** hat je Kanal und Fläche eine eigene, sichtbare Liste: E-Mail · Telegram · SMS · Premium-SMS · 3-Tages-Ausblick · (Orte) Stundenverlauf. Jede Liste ist eine Teilmenge der Metrik-Zeilen (abwählen ja, hinzufügen nein). Je Zeile gibt es Reihenfolge, Roh/Einfach und an/aus. Die Liste steht in jedem Kanal-Reiter an derselben Stelle. Kanalweite Einstellungen und Erklärsätze stehen darunter im eingeklappten Feld „Weitere Einstellungen für {Kanal}“ (Mail-Format und Zusatzblöcke, Telegram-Kurzstil für Briefing und Alarme, Ausblick morgens/abends, Stundenverlauf an/aus).

   > **Abgelöst 2026-11-17 durch [ADR-0124](0124-was-steht-wo-eine-tabelle.md) (PO, Issue #3122).** Punkt 3 gilt nicht mehr, ebenso der Verweis auf die Karte in Punkt 2. Es gibt keine Liste je Kanal und Fläche. Eine Tabelle „Was steht wo“ zeigt je Metrik der Grundauswahl, an welcher Stelle sie erscheint (E-Mail, Telegram, SMS mit Premium-SMS, bei Orten Stundenverlauf, 3-Tages-Ausblick). Es gibt eine Reihenfolge für alle Stellen. Roh/Einfach steht je Stelle und nur bei Metriken mit zwei Formen. Das Feld „Weitere Einstellungen für {Kanal}“ entfällt; ganze Blöcke und Einstellungen je Kanal stehen unter der Tabelle. Unverändert gilt: jede Stelle wählt nur ab, nichts kommt hinzu (ADR-0050).

4. **Der 3-Tages-Ausblick hat einen Namen und eine Stelle.** „Mehrtages-Trend“, „Ausblick“ und „3-Tages-Vorschau“ entfallen als Begriffe. Die drei heutigen Steuerstellen (`show_outlook`, `multi_day_trend_reports`, `outlook_metrics`) werden zu einer: der Liste „3-Tages-Ausblick“ mit „erscheint im Morgen-/Abend-Briefing“, Vorbelegung nur abends.

   > **Präzisiert 2026-11-17 durch [ADR-0124](0124-was-steht-wo-eine-tabelle.md) Nr. 4 und Nr. 6.** Ein Name und eine Stelle bleiben. Der Ausblick hat aber keine eigene Liste: Seine Metriken folgen der E-Mail-Auswahl, je Metrik abwählbar in der Spalte „3-Tages-Ausblick“. Die eine steuernde Stelle sind die Schalter „Morgen-Briefing“ und „Abend-Briefing“ unter der Tabelle, für Trip und Orte, Vorbelegung nur abends. Sie ersetzt zusätzlich `outlook_enabled` (Orte) und die Bedeutung „leere Liste = aus“.

5. **Zustellung** beantwortet „wann und auf welchem Weg erreicht ihr mich“: Morgen-/Abend-Briefing mit Uhrzeitfeld (ohne Schnellwahl), Laufzeit, Kanal-Tabelle (Briefing · Alarme · Alarm schon ab Dringlichkeit) mit Verbindungsstatus und Sperrgründen, Stille Stunden und „Anpassen“ (Mindestabstand zwischen zwei Alarmen).
6. **Keine Vorschau.** „Senden“ wird **„Test schicken ▾“**: ein Menü am Knopf mit Kanälen (Ziel, Sperre mit Grund), beim Trip Morgen/Abend, „Alle eingerichteten Kanäle“ und „Test-Alarm“. Daneben bleibt das Kebab (Pausieren, Archivieren, Löschen, Aktivieren).
7. **Reiterleiste nach Atomic-Design-Soll** (`claude-code-handoff/current/jsx/`, `docs/design-system/TOKENS.md`): eine Grundlinie `--g-rule`, Reiter 13px/500, aktiv 600 mit 2px-Unterstrich `--g-accent`, Badges mono 10px neutral. Mobil bleibt die freigegebene Pill-Leiste (`docs/specs/modules/mobile_tab_leisten_mtabbar.md`).
8. Alte Adressen (`?tab=wertebereiche`, `?tab=alarme`, `?tab=versand`, `?tab=layout`) leiten auf Wetter bzw. Zustellung um.

## Verworfene Alternativen

- **Wetter · Alarme · Zustellung:** Alarme mit eigenem Reiter. Dann steht dieselbe Metrik wieder an zwei Stellen.
- **Ein Reiter „Einstellungen“:** am wenigsten Klicks, aber eine sehr lange Seite.
- **Eine Liste für alle Kanäle** (automatisch nach Alarmstufe sortiert, oder eine von Hand sortierte Liste): Der PO will die Liste je Kanal sichtbar behalten (Karte `kanal_inhalt`: „wie heute“).
  > **Nachtrag 2026-11-17:** Der PO hat diese Wahl mit ADR-0124 abgelöst („viel zu kompliziert, man muss immer wieder dieselben Dinge auswählen“). Es gilt eine Tabelle mit einer von Hand gezogenen Reihenfolge für alle Stellen; die Abwahl je Kanal bleibt.

## Konsequenzen

- **Positiv:** Zwei Fragen, zwei Reiter. Trip und Orte bleiben ein Code (ADR-0097). Die Reiterleiste entspricht dem Soll.
- **Negativ / Preis:** Die Tab-Organismen unter `frontend/src/lib/components/shared/` werden neu geschnitten. `CorridorEditor`, `AlarmeTab`, der Versand-Reiter und der tote Alarm-Bündel-Code (`alerts-tab/`) entfallen. Texte und Links in Übersicht, Hilfe und Onboarding müssen nachgezogen werden.
- **Folgepflichten:** Alle neuen Texte in DE und EN (ADR-0104). Compare-eigen bleiben nur Orte-Reiter, transponierte Übersicht und Compare-Mail (ADR-0097). Die Pendant-Sperre gilt: keine neue Compare-Komponente mit Trip-Pendant.
