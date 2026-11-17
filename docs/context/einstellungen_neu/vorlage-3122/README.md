# Vorlage an den PO: Inhalt je Kanal, drei Entscheidungen (Issue #3122, Schritt 1)

Stand 2026-11-17. Bildvorlage für die PO-Entscheidung, **noch kein Soll**. Erst nach der Wahl folgen ADR,
Konzept-Endfassung (`../../einstellungen_neu.md`), Mockup Fassung 4 (endgültig), Elementliste, Spec und Bau.

| Was | Datei | Live-Seite (Verweis) |
|---|---|---|
| Entscheidungsseite mit Bildern (Computer und Handy) | `index.html`, `img/` | https://claude.ai/artifact/BzVRAuGPeg5cA6nxkhHY9b |
| Anklickbares Mockup mit Varianten-Schaltern | `../seiten/mockup-hub-fassung4-varianten.html` | https://claude.ai/artifact/CqB42zYt9mHJAmKWqQLq1r |

## Die offenen Punkte

1. **Kanal-Auswahl:** A eine Tabelle (Zeilen = Grundauswahl, Spalten = Kanäle, eine Reihenfolge) oder B eine Liste je Kanal.
2. **Roh/Einfach** (nur bei A): einmal je Metrik (gilt für E-Mail und Telegram) oder je Metrik und Kanal.
3. **Stundenverlauf und 3-Tages-Ausblick** im Abschnitt „Teile des Briefings“: fest wie die Übersicht oder wie die Übersicht mit Abwahl.

**Entschieden (PO 2026-11-17, im Chat):** Der Bereich heißt einheitlich **„Orte“**, auch bei einem einzelnen Ort. Die drei
Namensvorschläge (Orts-Briefing, Ortswetter, Ortsbeobachtung) sind entfallen. Nachgezogen nach PO-Rückfrage: Bei Orten
heißt die E-Mail-Spalte „Übersicht“, und „Teile des Briefings“ zeigt die drei Stellen der E-Mail untereinander
(Übersicht, Stundenverlauf, Ausblick); der Haken bei E-Mail ist die eine Auswahl für alle drei.

Fest eingebaut (PO 2026-11-17): Grundauswahl nur in den Metrik-Zeilen des Reiters Wetter, alles Weitere nur
Abwahl; Ausblick morgens/abends auch bei Orten (vorbelegt abends); Premium-SMS folgt der SMS; Telegram-Kurzstil
an genau einer Stelle.

## Herkunft der Beispielwerte

- **Orte:** echte Ausgabe von `render_compare_email`, `render_compare_telegram`, `render_compare_sms`
  (`src/output/renderers/comparison.py`, Stand `main` @ `87bacf412`) für drei Orte und für einen Ort. Der
  Ein-Ort-Lauf belegt den Ist-Zustand: „ORTS-VERGLEICH“, „Alle Orte“, „1 Orte“, „Vergleich 18.11.: …“.
- **Trip:** echte Ausgabe von `SMSTripFormatter.format_sms` und `render_telegram_bubbles` mit der Fixture
  `tests/helpers/telegram_briefing_fixture.py`. Tabellenzeilen der Mail sind daraus abgeleitet.
- Spalten des Ausblicks und des Stundenverlaufs zeigen den **Vorschlag** (folgt der E-Mail-Auswahl), nicht
  den Ist-Zustand (heute sieben feste Ausblick-Spalten bei Orten).

## Bilder neu erzeugen

Das Mockup liest seinen Zustand aus der Adresse, z. B.
`mockup-hub-fassung4-varianten.html#ctx=orte&varK=B&kanal=SMS&only=kanal`
(`ctx` = `trip|orte|ort1`, `varK` = `A|B`, `varF` = `einmal|kanal`, `varT` = `fest|abwahl`, `nameV`,
`only` = sichtbare Abschnitte `kopf,grund,kanal,teile,bsp,bsp-mail,bsp-tg,bsp-sms,bsp-name,anpassen`,
`weg` = im Ausblick/Stundenverlauf abgewählte Metriken). Aufnahme mit Playwright bei 1132 px und 390 px Breite.
