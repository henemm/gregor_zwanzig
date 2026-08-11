# ADR-0050: Die Metrik-Kaskade ist eine Verfeinerung, nicht eine Ersetzung — die Grundauswahl ist das Maximum

- **Status:** Akzeptiert (PO-Entscheid 2026-08-11, s. Kontext-Dokument Abschnitt 6)
- **Datum:** 2026-08-11
- **Bezug:** Issue #1719 (Scheibe S1), Spec
  `docs/specs/modules/fix_1719_s1_kaskade_pruefstand.md`; ergänzt ADR-0049
  (Kanalliste E-Mail · Telegram · SMS · Premium-SMS) um die Kaskadensemantik
  zwischen Grundauswahl und Kanal-Layout, die ADR-0049 nicht behandelt

## Kontext

Trip **KHW `5f534011`** (Produktion, Nutzer `henning`) lieferte am 2026-08-11
eine SMS-Kurzform, die Metriken enthielt (`FK`/`FD`/`WC`, also `wind_chill`),
die im SMS-Reiter des Editors ausdrücklich **abgewählt** waren. Die
Gegenprobe mit dem echten Loader gegen die aktuell gespeicherte Trip-Datei
zeigt zwei einander widersprechende Ebenen in genau einer Datei:

| Ebene | JSON-Feld | Einträge | `wind_chill` |
|---|---|---|---|
| Grundauswahl (global) | `display_config.metrics` | 26, davon 15 aktiv | **AN** |
| SMS-Kanal-Layout | `display_config.channel_layouts.sms` | 26, davon 13 aktiv | **AUS** |

Der produktiv gerenderte SMS-Text passte Kürzel für Kürzel zur **globalen**
Liste, nicht zur Kanal-Liste — obwohl die Kanal-Liste die Metrik explizit
abgewählt hatte. Der genaue Konfigurationsstand zum historischen
Sendezeitpunkt (05:00 UTC) ist nicht mehr rekonstruierbar, weil die Trip-
Datei danach (05:53 UTC) erneut geschrieben wurde — der konkrete Vorfall
lässt sich damit nicht mehr eins-zu-eins nachstellen. Unabhängig davon
besteht der strukturelle Konstruktionsfehler: **zwei Ebenen mit
Metrik-Auswahl, ohne dass irgendwo festgelegt ist, in welche Richtung ein
Widerspruch aufgelöst wird.**

Der heutige Code (`UnifiedWeatherDisplayConfig.get_metrics_for_channel()`,
`src/app/models.py:808-846`) implementiert eine **Ersetzung**: Existiert für
einen Kanal ein `per_channel_layouts[channel]`-Eintrag, ersetzt dieser die
globale Liste vollständig — inklusive der `enabled`-Flags jeder einzelnen
Metrik. Das bedeutet: Eine Metrik, die in der Grundauswahl bewusst
abgewählt ist, kann über eine Kanal-Ebene trotzdem **wieder aktiviert**
werden, sobald die Kanal-Ebene existiert und die Metrik dort
`enabled: true` trägt. Das widerspricht dem Mentalmodell, das Editor und
Nutzer teilen: die Grundauswahl legt fest, was überhaupt sichtbar sein
*kann* — der Kanal-Reiter schränkt das weiter ein, fügt aber nichts hinzu.

Es gab bislang **keine schriftlich fixierte Entscheidung**, welche
Beziehung zwischen den beiden Ebenen gelten soll — 49 ADRs, keines zur
Kaskade. Ohne eine solche Zusage lässt sich kein Test schreiben, der
zwischen „korrekt" und „Bug" unterscheidet: ein Wächter, der lediglich das
heutige Verhalten nachzeichnet, prüft, was der Code *tut*, nicht was er
*tun soll*.

## Entscheidung

**Die Kaskade zwischen Grundauswahl und Kanal-Layout ist eine Verfeinerung,
keine Ersetzung.** Verbindlich:

1. **Die Grundauswahl ist das Maximum.** Was in der Grundauswahl abgewählt
   ist, kann in keinem Kanal erscheinen — unabhängig davon, was eine
   Kanal-Ebene für diese Metrik einträgt.
2. **Eine Kanal-Ebene darf eine Metrik der Grundauswahl nur ABWÄHLEN — nie
   HINZUFÜGEN.** Eine Kanal-Ebene ist damit strukturell eine Teilmenge der
   Grundauswahl, nie eine davon unabhängige zweite Auswahl.
3. **Eine Abwahl in der Grundauswahl wirkt sofort in ALLEN Kanälen** — auch
   in solchen, die eine eigene Kanal-Ebene mit `enabled: true` für dieselbe
   Metrik gespeichert haben. Es gibt keinen Weg, über einen Kanal eine
   global abgewählte Metrik zurückzuholen.
4. **„Aus" ist ein ZUSTAND, keine Löschung.** Wählt der Nutzer eine Metrik
   in einem Kanal ab, bleibt die Zeile im Editor mit einer
   Zustandsanzeige stehen — sie verschwindet nicht physisch aus der Liste.
   (Wirkt auf den Editor, Umsetzung ist Scheibe S3 — hier als Teil der
   Zusage festgehalten, weil Regel 2 sonst unvollständig bliebe: ein
   Bedienelement, das nur löschen kann, verwischt den Unterschied zwischen
   „abgewählt" und „nie in dieser Auswahl gewesen".)
5. **Reihenfolge und Darstellungsform bleiben je Kanal einstellbar.** Diese
   Entscheidung betrifft ausschließlich die AUSWAHL (welche Metrik
   erscheint), nicht die Sortierung oder das Rohwert-/Einfach-Format
   innerhalb eines Kanals — die bleiben unverändert kanal-eigen (Issue
   #429, #1575, #1677).

Gilt für alle vier Kanäle gleichrangig: E-Mail, Telegram, SMS, Premium-SMS
(ADR-0049) — Premium-SMS teilt sich technisch heute ohnehin denselben
gerenderten Text wie SMS (`report.sms_text`), erbt die Regel damit
strukturell mit.

## Verworfene Alternativen

- **Heutiges Verhalten beibehalten (Kanal-Ebene ersetzt vollständig).**
  Verworfen: erlaubt einer Kanal-Ebene, eine in der Grundauswahl abgewählte
  Metrik unbemerkt wieder scharfzuschalten — genau der KHW-Befund. Ein
  Editor, der „abwählen" anbietet, das an anderer Stelle wirkungslos
  gemacht werden kann, ist irreführend.
- **Kanal-Ebenen ganz abschaffen (nur eine globale Liste für alle Kanäle).**
  Verworfen: Reihenfolge und Rohwert-/Einfach-Format je Kanal sind
  bestehende, genutzte Funktionen (#429, #1575, #1677), die der PO
  ausdrücklich erhalten will (Regel 5). Das Problem ist die
  AUSWAHL-Ersetzung, nicht die Existenz von Kanal-Ebenen an sich.
- **Ersetzung beibehalten, aber zusätzlich serverseitig gegen die
  Grundauswahl validieren (Warnung statt Sperre).** Verworfen: eine
  Warnung, die niemand liest, verhindert den stillen Auswahl-Widerspruch
  nicht — genau dieses „still falsch, aber nicht laut genug" hat den
  KHW-Befund erst unbemerkt gelassen.
- **„Aus" als physische Löschung beibehalten** (heutiges Editor-Verhalten,
  `onRemove`/`move(... 'primary' → 'off')`). Verworfen: im Kanal-Reiter
  gibt es dafür heute keinen Weg zurück (Kontext-Dokument Abschnitt 4) —
  eine Löschung kann nicht zwischen „bewusst abgewählt" und „nie
  ausgewählt" unterscheiden, was Regel 2/3 aber voraussetzen.

## Konsequenzen

- **Positiv:** Es existiert jetzt eine Zusage, gegen die ein Prüfstand
  testen kann (s. Spec zu Scheibe S1). Der Editor-Mentalmodell-Bruch aus
  Abschnitt „Kontext" wird zu einer benannten Regel statt eines impliziten
  Zufallsverhaltens.
- **Negativ / Preis:** `get_metrics_for_channel()` muss um einen
  Global-Maximum-Filter erweitert werden (Scheibe S2, **nicht** Teil
  dieser Entscheidung/Scheibe S1) — die reine Ersetzungslogik reicht nicht
  mehr aus.
- **Negativ / Preis:** Bestehende, bereits gespeicherte Kanal-Layouts, die
  heute schon Metriken „hinzufügen", die in der Grundauswahl abgewählt
  sind, fallen nach der Umsetzung von S2 auf AUS zurück — eine stille
  Verhaltensänderung für Alt-Konfigurationen. Migrationsfrage bleibt für
  S2 offen (s. Spec, Offene Fragen).
- **Folgepflicht:** Jede neue Stelle, die die Kaskade liest oder eine
  eigene Kanal-Ebene einführt, muss die Maximum-Regel respektieren oder
  begründet abweichen — analog zur Folgepflicht aus ADR-0046
  (Kanal-Schwelle) und ADR-0049 (Kanalliste).
- **Nicht durch diese Scheibe bewiesen:** dass der Produktivcode die
  Regeln 1–4 tatsächlich einhält. Diese Entscheidung ist die Zusage; der
  Prüfstand aus Scheibe S1 zeigt den heutigen Widerspruch als reproduzierbar
  ROT, die Umsetzung folgt in S2.
