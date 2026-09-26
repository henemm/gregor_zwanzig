# Trip-Befehle — Email-Reply & Telegram (F6)

**Hinweis (seit Issue #2282, Scheibe S1):** `PAUSE`/`WEITER`/`HILFE` sind über alle
drei Eingangskanäle auch am **Ortsvergleich** ansprechbar — Details im Abschnitt
„Ortsvergleich per Nachricht" unten.

**Updated:** 2026-09-26 (Issue #2417 — bei aktivem Trip **und** Ortsvergleich(en)
gehen alle Befehle außer `PAUSE`/`WEITER` jetzt direkt an den Trip statt in eine
Rückfrage zu laufen, `HILFE` antwortet dabei sofort; neuer Hinweistext „kein
aktives Ziel" für Trip-only-Befehle ohne aktiven Trip; Telegram-Bot-Menü zeigt
jetzt alle 17 Befehle statt 7, `/status`-Alias auf `glance` entfernt); 2026-09-17
(Issue #2282 Scheibe S1, Epic #2133/#1374 — Ortsvergleiche
sind jetzt über alle drei Eingangskanäle für `PAUSE`/`WEITER`/`HILFE` ansprechbar;
die aktive Auswahl ohne Namen und die `[Name]`-Erkennung im E-Mail-Betreff arbeiten
kanaltyp-übergreifend); 2026-09-08 (Issue #2184, Epic #2133 Scheibe S4 — Premium-SMS ist jetzt
ein dritter Eingangsweg: der vor dem Garmin-inReach-Kennzeichen `inreachlink.com`
stehende Text wird als Befehl verarbeitet, die Antwort geht per Premium-SMS an die
gelernte Rückadresse zurück; die Gewitter-Herkunft bleibt auf SMS/Premium-SMS wie
bisher unterdrückt); 2026-08-23 (Issue #2051 Scheibe S4 — neues Abfrage-Kommando `STRECKE`/`/strecke`:
Regen-Ereignisflächen entlang der Reststrecke des aktuell aktiven Wegabschnitts, erreichbar über
Email und Telegram); 2026-06-13 (Briefing-Mail lesbar: D/W/G-Kürzel aus E-Mail-Betreff entfernt — neu `[GZ#GRANK] Tag 3 — Morgen — Gewitter` ohne Zahlenkürzel); 2026-06-12 (Bug #775 — Trip-Shortcode-Routing: E-Mail-Betreff trägt neuen `[GZ#XXXX]`-Shortcode als primären Routing-Key, RFC-2047-Dekodierung, toleranter Whitespace-Lookup als Fallback); 2026-06-11 (Issue #731 — Befehlssatz vereinheitlicht: abruf-zentriert (HEUTE/MORGEN/JETZT/GEWITTER/RUHETAG/STATUS/STOP/WEITER/HILFE), PAUSE/SKIP/CONFIG entfernt); 2026-06-08 (Issues #672/#671 — E2E-Pipeline-Tests + vollständiges Bot-Menü; #651/#653/#654/#655 — Telegram Tier-1/2/3 + Zoom-Navigation)

Gregor Zwanzig empfaengt Trip-Befehle ueber drei Kanäle:
- **Email:** Du antwortest auf einen bestehenden Report (alle 5 Minuten abgerufen)
- **Telegram:** Du schreibst eine Nachricht oder klickst einen Button (Webhook-Push seit Issue #637)
- **Premium-SMS** (Garmin inReach, seit Issue #2184): Du schreibst den Befehl in die
  Garmin-Nachricht, vor den automatisch angehängten Link (Kennzeichen
  `inreachlink.com`) — abgerufen im selben 5-Minuten-Poll wie der Rückadress-Lernlauf
  (Issue #1676)

## Email: So funktioniert's

1. Du erhaeltst einen Report per Email (z.B. `[GZ#GRANK] GR221 Mallorca — Morning Report`)
2. Du antwortest auf diese Email (die Antwort-Mail erbt den Betreff)
3. In die **erste Zeile** schreibst du den Befehl
4. Gregor verarbeitet den Befehl über den Shortcode-Identifier und schickt dir eine Bestaetigung zurueck

**Hinweis:** Der Betreff enthält seit Bug #775 einen eindeutigen Shortcode (`[GZ#XXXX]`), z.B. `[GZ#GRANK]` für „GR221 Mallorca". Das macht die Trip-Erkennung robust gegen RFC-2047-Encoding-Fehler (wenn Leerzeichen im Trip-Namen zu Unterstrichen werden). Der Shortcode wird aus dem Trip-Namen generiert und pro Nutzer eindeutig gehalten.

## Telegram: So funktioniert's

1. Du sendest eine Nachricht an den Bot oder klickst einen Button in der Chat-Nachricht
2. Der Bot verarbeitet den Befehl sofort (Webhook-Push)
3. Der Bot antwortet mit einer Bestaetigung oder aktualisiert die Nachricht in-place (Zoom-Navigation)

## Premium-SMS: So funktioniert's (Garmin inReach, seit Issue #2184)

1. Du schreibst den Befehl in die Nachricht auf deinem Garmin-inReach-Gerät — Garmin hängt
   automatisch einen Link plus Koordinaten an (Kennzeichen `inreachlink.com`)
2. Gregor liest dein Gerät am Kennzeichen und deine Rückadresse per Absendernummer aus
   (Voraussetzung: die Rückadresse ist bereits gelernt, s. `POST
   /api/internal/premium-sms-learn`, Issue #1676 S1); nur der Text **vor** dem Kennzeichen
   zählt als Befehl
3. Gregor verarbeitet den Befehl über denselben `TripCommandProcessor` wie Email/Telegram
   (kein eigener Trip-/Vergleichs-Bezug im Text nötig — die Auswahl folgt derselben
   kanalneutralen Regel wie beim Telegram-Bot ohne Namen: aktiver Trip am Ortstag, sonst
   der nächste zukünftige; hat der Nutzer stattdessen **keinen** aktiven Trip, aber genau
   einen aktiven Ortsvergleich, wird dieser angesprochen — Details siehe „Ortsvergleich
   per Nachricht" unten)
4. Die Bestaetigung geht per Premium-SMS an deine gelernte Rückadresse zurück

**Besonderheit:** Auf Premium-SMS (wie auf regulärem SMS) bleibt die Gewitter-Herkunft
(„wegen hoher Blitzdichte" o.ä.) grundsätzlich unterdrückt — sie kostet Zeichen auf einem
Kanal, der pro Zeichen Geld und Garmin-Kontingent kostet. Die Stufe selbst
(„Gewitter: hoch") bleibt sichtbar. Details: `docs/features/gewitter-gesamtkonzept.md`,
Spec `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md`.

Nicht eindeutig zuordenbare Absender (Lernaufruf schlägt fehl, z. B. mehrere Kandidaten)
und die allererste Verbindungsnachricht des Geräts ohne Befehlsabsicht lösen **keine**
Verarbeitung bzw. dieselbe „Unbekannter Befehl"-Antwort wie auf den anderen Kanälen aus —
kein stilles Verwerfen.

## Befehlsformat

Zwei Arten sind moglich:

**1. Bare Keywords (neu, ab #731)** — einfach das Schlüsselwort in die erste Zeile:
```
HEUTE
MORGEN
JETZT
STATUS
```

**2. Klassisches Format** (weiterhin unterstützt) — Drei Rauten + Befehl:
```
### befehl: wert
### ruhetag: 2
```

Gross-/Kleinschreibung ist egal. Der Befehl muss in der **ersten nicht-leeren Zeile** stehen.

---

## Verfuegbare Befehle

### Abfrage-Befehle (Abruf-zentriert)

Diese Befehle zeigen Wetter-Informationen **ohne** Trip-State zu veraendern.

| Befehl | Wirkung |
|--------|--------|
| `HEUTE` | Wetter der heutigen Etappe |
| `MORGEN` | Wetter der morgigen Etappe |
| `JETZT` / `NOW` | Nowcast (Regen/Gewitter naechste ~2h) |
| `GEWITTER` | Gewittergefahr heutige Etappe (stuendlich) |
| `STATUS` | Heute + kommende Etappen (ohne vergangene) |
| `STRECKE` / `STRECKE <km>` | Regen-Ereignisflächen entlang der Reststrecke des aktuell aktiven Wegabschnitts (Issue #2051 S4) |
| `HILFE` / `HELP` | Verfuegbare Befehle anzeigen |

**Beispiel:**
```
HEUTE
```

Gregor antwortet mit dem Wetter fuer die heutige Etappe.

---

### `STRECKE` — Regen-Ereignisflächen entlang der Reststrecke (Issue #2051 S4)

Zeigt die Regen-Ereignisflächen entlang der Reststrecke des **aktuell aktiven
Wegabschnitts** (nicht der ganzen Tagesetappe — siehe Grenze unten). Erreichbar über
Email (Freitext `STRECKE` in der ersten Zeile), Telegram (Freitext `strecke` oder
Slash `/strecke`) und Premium-SMS (Freitext `STRECKE` vor dem Garmin-Kennzeichen, seit
Issue #2184). Seit Issue #2417 steht `/strecke` auch im Telegram-Bot-Menü (Details:
`docs/features/architecture.md`, Abschnitt Telegram-Bot-Menü) — davor musste es
getippt werden.

**Ohne Argument:** Ausgangspunkt ist die aktuelle Planposition.

**Mit Argument** (`STRECKE 5` bzw. `/strecke 5`): Ausgangspunkt ist der selbst genannte
km-Stand, bezogen auf die stage-kumulative Kilometrierung des aktiven Segments.
Gültiger Bereich: `[Segment-Start-km, Segment-Ende-km]` (beide Ränder eingeschlossen),
Dezimalwerte erlaubt. Werte außerhalb des Bereichs oder nicht-numerische Eingaben werden
abgelehnt — kein Wetterabruf.

**Antwort:**
- Email: je Regen-Ereignisfläche eine Zeile mit km-Spanne, Zeitspanne, Intensität und
  Quelle im Klartext (`Radar (DWD)`, `INCA (GeoSphere AT)`).
- Telegram: dieselben Zeilen ohne Quelle-Spalte (Platzgrund).
- Jede Antwort mit Messung schließt mit `Geprüft: km {von}-{bis}.` — der tatsächlich
  geprüften Spanne (aus den erfolgreich abgefragten Punkten, nicht den geplanten).

**Drei ehrliche Sonderfälle:**
- Keine aktive Etappe/kein auflösbarer Standort — derselbe Text wie `JETZT` in derselben
  Situation.
- Kilometrierung für die Etappe nicht verfügbar (auch nach Nachrüst-Versuch) — keine
  Streckenangabe möglich, kein Wetterabruf.
- Kein Regen im geprüften Abschnitt erkannt — eigener Hinweistext samt geprüfter Spanne.

**Bekannte Grenze:** Die Antwort deckt nur das aktuell aktive Wegpunkt-Segment ab, nicht
die volle Resttagesetappe (Bestandsgrenze aus S2a/S2b im Alarm-Pfad — dieselben Bausteine
`derive_rain_zones()`/`points_along_remaining_route()` — hier nur über die
`Geprüft:`-Zeile sichtbar gemacht, nicht behoben). Kein regulärer SMS-Kanal (dafür gibt es
keinen Inbound-Kommando-Pfad); über Premium-SMS (Garmin inReach, seit Issue #2184)
funktioniert `STRECKE` wie jeder andere bekannte Befehl.

**Beispiel:**
```
STRECKE
```
oder mit eigenem km-Stand:
```
STRECKE 5
```

Spec: `docs/specs/modules/feat_2051_s4_strecke_kommando.md`

---

### Verwaltungs-Befehle

Diese Befehle veraendern den Trip-Status.

| Befehl | Syntax | Wirkung |
|--------|--------|---------|
| `RUHETAG` | `RUHETAG` oder `RUHETAG: 2` | Verschiebt zukuenftige Etappen um N Tage |
| `STOP` | `STOP` | Deaktiviert den Versand (Reporter pausieren) |
| `WEITER` | `WEITER` | Reaktiviert den Versand (nach STOP) |

**Beispiel — RUHETAG:**
```
RUHETAG: 2
```

**Bestaetigung:**
```
[GR221 Mallorca] Ruhetag bestaetigt

Ruhetag eingetragen: +2 Tage.

Verschobene Etappen:
  Tag 3: 18.02.2026 -> 20.02.2026
  Tag 4: 19.02.2026 -> 21.02.2026

Naechster Report kommt planmaessig.
```

**Beispiel — STOP:**
```
STOP
```

**Bestaetigung:**
```
[GR221 Mallorca] Trip beendet

Reports fuer 'GR221 Mallorca' deaktiviert. Gute Heimreise!
```

**Beispiel — WEITER:**
```
WEITER
```

**Bestaetigung:**
```
[GR221 Mallorca] Versand reaktiviert

Briefing-Reports sind wieder aktiv. Naechster Report kommt planmaessig.
```

---

## Ortsvergleich per Nachricht (seit Issue #2282, Scheibe S1)

`PAUSE`, `WEITER` und `HILFE` sind über alle drei Eingangskanäle (Email, Telegram,
Premium-SMS) auch für einen **Ortsvergleich** ansprechbar, nicht nur für einen Trip.
Alle übrigen Befehle bleiben trip-exklusiv.

**Adressierung ohne Namen** (Telegram/Premium-SMS) — seit Issue #2417 abgestuft nach
Befehlsart (löst die vorherige pauschale Mehrdeutigkeits-Regel ab):

- `HILFE` antwortet **immer sofort** mit der Befehlsübersicht, ganz ohne
  Trip-/Vergleichs-Auflösung — auch wenn Trip und Ortsvergleiche gleichzeitig aktiv
  sind.
- Alle übrigen Abfrage- und Verwaltungsbefehle (`HEUTE`, `MORGEN`, `JETZT`,
  `GEWITTER`, `STRECKE`, `RUHETAG`, `STATUS`, `SKIP`, `STOP`, Wetter-Kürzel,
  Query-Keys) gehen bei einem aktiven Trip **immer direkt an diesen Trip** —
  unabhängig davon, wie viele Ortsvergleiche daneben aktiv sind, und **ohne**
  Rückfrage. Gibt es **keinen** aktiven Trip, aber ≥1 aktiven Ortsvergleich,
  antwortet Gregor mit „Kein aktiver Trip. Dieser Befehl gilt nur für Trips, nicht
  für Ortsvergleiche." — bewusst unterscheidbar vom Fall „gar nichts aktiv" unten.
- Nur `PAUSE`/`WEITER` bleiben mehrdeutig (unverändert): Sind sowohl ein Trip als
  auch mindestens ein Ortsvergleich aktiv, oder mehrere Ortsvergleiche gleichzeitig,
  fragt Gregor zurück und zählt alle Kandidaten auf — es wird **kein** Befehl
  ausgeführt, bis mit vorangestelltem Namen geantwortet wird (z. B. `Zermatt
  pause`). Hat der Nutzer keinen aktiven Trip, aber genau einen aktiven (auch
  bereits pausierten) Ortsvergleich, wird dieser direkt angesprochen.

Gibt es weder einen aktiven Trip noch einen aktiven Ortsvergleich, lautet die
Antwort auf allen Kanälen einheitlich „Kein aktiver Trip oder Ortsvergleich
gefunden."

**Adressierung mit Namen:** Ein vorangestellter Name (Telegram/Premium-SMS) bzw. das
`[Name]` im Email-Betreff wird gegen Trips **und** Ortsvergleiche geprüft. Tragen ein
Trip und ein Ortsvergleich desselben Nutzers zufällig denselben Namen, fragt Gregor
ebenfalls zurück, statt still den Trip zu bevorzugen.

**Verhalten am Ortsvergleich:**

| Befehl | Wirkung |
|--------|---------|
| `PAUSE` | Pausiert den Ortsvergleich unbefristet (eine mitgegebene Dauer wie `PAUSE 2d` wird ignoriert) — Antwort: „... pausiert, bis du 'weiter' sendest." |
| `WEITER` | Setzt einen pausierten Ortsvergleich fort — Antwort: „... wieder aktiv." War der Vergleich nicht pausiert: „... ist nicht pausiert." (keine Änderung) |
| `HILFE` | Zeigt nur die am Ortsvergleich verfügbaren Befehle (`PAUSE`, `WEITER`, `HILFE`) — nicht die volle Trip-Befehlsliste |
| `REPORT`, `HEUTE`, `MORGEN` | Übergangsantwort: „... noch nicht verfügbar — bitte nutze die Web-App." (kein Versand) |
| alle übrigen (`STRECKE`, `SKIP`, `RUHETAG`, `STARTDATUM`, `STOP`, `JETZT`/`NOW`, `STATUS`, `GEWITTER`, Drilldowns, Metrikwörter) | „'<befehl>' gibt es beim Ortsvergleich nicht." |

**Bekannte Grenze:** Die Pause-Semantik am Ortsvergleich unterscheidet sich bewusst
vom Trip — unbefristet bis `WEITER`, keine Dauer, kein `STOP`-Verweis. Der Wortlaut
ist deshalb nicht identisch mit der Trip-`PAUSE`-Bestätigung.

Spec: `docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md`

---

### Klassische Befehle (weiterhin unterstützt)

Fuer reine Etappen-Verwaltung (keine PAUSE/SKIP/CONFIG mehr — siehe Issue #731):

#### `### startdatum: YYYY-MM-DD`

Verschiebt **alle** Etappen relativ zu einem neuen Startdatum.
Die Abstande zwischen Etappen bleiben gleich.

```
### startdatum: 2026-03-15
```

**Bestaetigung:**
```
[GR221 Mallorca] Startdatum geaendert

Startdatum verschoben: 16.02.2026 -> 15.03.2026

Neue Etappen-Daten:
  Tag 1: 15.03.2026
  Tag 2: 16.03.2026
  Tag 3: 17.03.2026
  Tag 4: 18.03.2026
```

---

#### `### report: morning` / `### report: evening`

Loest sofort einen Report aus — ohne auf den naechsten Zeitplan zu warten.

```
### report: morning
```

oder

```
### report: evening
```

## Einrichtung: Plus-Adresse (empfohlen)

Damit Gregor nicht alle Emails liest, sondern nur Befehle:

```env
GZ_INBOUND_ADDRESS=henning.emmrich+gregor-zwanzig@gmail.com
```

**Vorteile:**
- Persoenliche Emails werden nie angefasst
- Reports kommen FROM dieser Adresse → Replies landen automatisch richtig
- Gmail leitet Plus-Adressen an das gleiche Postfach weiter

Ohne `GZ_INBOUND_ADDRESS` werden alle ungelesenen Emails geprueft (wie bisher).

## Wichtig

- Der Befehl muss in der **ersten nicht-leeren Zeile** stehen
- Gross-/Kleinschreibung ist egal (`### RUHETAG` funktioniert auch)
- Der Trip wird aus dem Email-Betreff erkannt: **Primär über den Shortcode** `[GZ#XXXX]`, falls nicht vorhanden fallback auf Namensvergleich (robust gegen Whitespace-Variationen). Seit Issue #2282 findet derselbe `[Name]`-Namensvergleich im Betreff auch einen **Ortsvergleich** — nur `PAUSE`/`WEITER`/`HILFE` wirken dort (siehe unten)
- Nur Emails von deiner konfigurierten Adresse werden akzeptiert
- Unbekannte Befehle werden mit einer Hilfe-Antwort beantwortet

---

## Telegram-Abfrage-Befehle

### Kurzbefehle (Schrägstrich)

Diese Befehle gibst du direkt als Telegram-Nachricht ein oder tappst sie aus dem Bot-Menü:

| Befehl | Bot-Menü Name | Beschreibung |
|--------|---------------|-------------|
| `/glance` oder `/s` | **glance** | 🌤️ Wetter-Überblick (heute & morgen) |
| `/heute` oder `/h` | **heute** | 📅 Nur heute Details |
| `/morgen` oder `/m` | **morgen** | 📅 Nur morgen Details |
| `/heute_gewitter` oder `/hg` | **heute_gewitter** | ⛈️ Gewitter-Fokus heute (stündlich) |
| `/timeline_heute` oder `/th` | **timeline_heute** | 🕐 Timeline heute (Etappenschritte mit Metriken) |
| `/timeline_morgen` oder `/tm` | **timeline_morgen** | 🕐 Timeline morgen (Etappenschritte mit Metriken) |
| `/hilfe` | **hilfe** | ℹ️ Verfügbare Befehle |

**Wichtig:** Telegram sendet getappte Menü-Befehle immer mit führendem Slash (z.B. `/glance`). Gregor kennt sowohl die kurzen Varianten (`/s`) als auch die vollständigen Menü-Namen (`/glance`) — beide funktionieren.

**Seit Issue #2417 (AC-21) ist das Bot-Menü vollständig:** Zusätzlich zu den oben
gelisteten Abfrage-Befehlen enthält es `strecke`, `ruhetag`, `status`, `pause`,
`skip`, `stop`, `weiter` (insgesamt 17 Einträge). `/status` löst dabei **nicht**
mehr — wie früher — `glance` aus, sondern liefert wie das nackte Wort `status`
die Etappenliste; der Wetter-Überblick bleibt über `/glance` erreichbar.
Vollständige, aktuelle Liste: `docs/features/architecture.md`.

### Welcher Tag ist „heute"? (ADR-0044)

**Kalendertage bestimmen sich nach der Ortszeit der Tour**, nicht nach Weltzeit. Wer um
00:30 Ortszeit „heute" abfragt, bekommt seinen Tag — nicht den, der in Greenwich gerade
gilt. Die Zone wird aus den Koordinaten des Wegpunkts aufgelöst.

Ein Ortstag hat dabei nicht immer 24 Stunden: an den Umstellungstagen 23 oder 25. Die
Stundentabelle bildet das ab.

**Nicht betroffen sind Dauern.** „Die nächsten zwölf Stunden" (Drilldown „heute") ist eine
Spanne ab jetzt, keine Tagesgrenze — sie läuft über Mitternacht hinaus weiter.

⚠️ **Stand 2026-08-03 gilt das für den Drilldown** (Stunden-/Gewitter-Ansichten, Tier 3).
Die Befehle `/heute`, `/morgen` und `/glance` folgen noch der Weltzeit — sie lösen einen
**Versand** aus und brauchen deshalb eine eigene Abwägung. Ebenso `### ruhetag`,
`/status` und `/jetzt`. Siehe ADR-0044, Abschnitt „Noch nicht umgesetzt".

### Zoom-Navigation (via Button-Klicks)

Die Tier-1-Glance (`/s`) und Tier-2-Timeline (`/th`, `/tm`) enthalten Buttons:

- **Tier 1** (Glance heute/morgen) → Button klicken → **Tier 2** (Timeline heute/morgen)
- **Tier 2** (Timeline) → Button klicken → **Tier 3** (Drilldown z.B. Gewitter stündlich)
- **Tier 3** (Drilldown) → „Zurück"-Button → zurück zu **Tier 2** (Timeline)

Diese Zoom-Navigation ersetzt die Nachricht in-place — kein Nachrichten-Spam. Der Telegram-Lade-Spinner wird nach jedem Klick automatisch gestoppt.

**Beispiel-Ablauf:**
```
1. Sende: /s
   Bot antwortet mit Glance-Übersicht + Buttons „Timeline heute" / „Timeline morgen"
2. Klick auf „Timeline heute"
   Nachricht wird in-place aktualisiert → Timeline-Details mit Buttons je kritischer Metrik
3. Klick auf „Gewitter stündlich"
   Nachricht wird aktualisiert → Gewitter-Verlauf mit „Zurück"-Button (Issue #2185: aufeinanderfolgende Stunden mit identischem Text werden zu einem Zeitbereich `HH:MM–HH:MM` zusammengefasst, statt jede Stunde einzeln zu listen)
4. Klick auf „Zurück"
   Zurück zur Timeline-Übersicht
```

---

## Telegram — Abruf-Befehle (Bare Keywords)

Seit Issue #731 kannst du den Telegram-Bot mit den gleichen **bare Keywords** wie Email ansprechen:

```
HEUTE
MORGEN
JETZT (oder NOW)
GEWITTER
STATUS
STRECKE (auch STRECKE <km>, oder /strecke)
HILFE
```

Der Bot antwortet direkt — kein Reload nötig.

**Beispiel:** Schreib `heute` → Bot zeigt Wetter der heutigen Etappe.

---

## Telegram — Verwaltungs-Befehle

Wie Email:

```
RUHETAG
RUHETAG: 2
STOP
WEITER
```

Keine `###`-Präfixe nötig — Telegram erkennt die Befehle direkt.

---

## Telegram — Klassische Befehle (via Bot-Menü)

Das Bot-Menü bietet zusätzlich strukturierte Abfragen (ähnlich Query-Keys), die in der Email-Dokumentation als `### key` gelistet sind:

| Bot-Menü Name | Beschreibung |
|---------------|-------------|
| **glance** | 🌤️ Schnell-Überblick (heute & morgen) |
| **heute** | 📅 Heute Details |
| **morgen** | 📅 Morgen Details |
| **heute_gewitter** | ⛈️ Stündliche Gewitter-Serie heute |
| **timeline_heute** | 🕐 Etappen mit Metriken heute |
| **timeline_morgen** | 🕐 Etappen mit Metriken morgen |
| **hilfe** | ℹ️ Verfügbare Befehle |

Klick den Button im Bot-Menü oder tippe `/glance`, `/heute_gewitter` etc.

Seit Issue #2417 zeigt das Bot-Menü zusätzlich `strecke`, `ruhetag`, `status`,
`pause`, `skip`, `stop`, `weiter` (siehe Hinweis oben unter „Telegram-Abfrage-Befehle").

### Wenn für einen Tag keine Wetterdaten vorliegen (Issue #1818)

Die vier Abfragen `timeline_heute`, `timeline_morgen`, `glance` und `heute_gewitter` lesen den
undatierten Wetter-Anker `{trip_id}.json`. Der trägt strukturell nur **einen** Tag: jeder
Briefing-Lauf überschreibt ihn komplett mit seinem eigenen `target_date` (Morgen-Lauf → heute,
Abend-Lauf → morgen). Für den jeweils anderen Tag lösen die Abfragen deshalb gestuft auf:

1. **Undatierter Anker** trägt für den Tag Punkte mit auswertbaren Tageswerten → diese gewinnen.
2. Sonst **datierter Snapshot** `{trip_id}_{YYYY-MM-DD}.json` (`load_dated`) — rein lesend,
   **ohne Wetterabruf**. Deckt strukturell die Abend-Hälfte: nach dem Abend-Briefing liegt der
   fehlende Tag (heute) aus dem Morgen-Lauf datiert vor.
3. Sonst **ehrliche Datenlücken-Meldung** mit Verweis auf `/heute` bzw. `/morgen`.

**Wichtige Unterscheidung:** „Keine Etappe geplant" ist eine Aussage über die **Tourplanung** und
erscheint nur, wenn `convert_trip_to_segments(trip, tag)` für den Tag wirklich leer ist (Ruhetag,
Tag nach Tourende). Fehlen dagegen nur die **Daten**, sagt die Antwort das auch so — die frühere
Vermengung beider Fälle war der Defekt aus #1818.

Ein Punkt zählt nur als Abdeckung, wenn er mindestens eine auswertbare Tagesgröße trägt
(`_traegt_tageswerte`). Inhaltsleere Platzhalter aus **teilweise** gescheiterten Abrufen
verdrängen damit keine echten Werte mehr (Adversary-Befund F005).

**Keine Schreibwirkung:** Diese Abfragen lösen keinen Wetterabruf aus und verändern keine
Snapshot-Datei; die Ergänzung geschieht auf einer In-Memory-Kopie. Der undatierte Anker bleibt
eintägig — er ist zugleich Vergleichsbasis des Abweichungs-Alarms (`briefing_backed`, ADR-0009),
die dadurch strukturell unberührt bleibt.

**Grenze:** Am Vormittag liegt für morgen weder im Anker noch datiert etwas vor (der datierte
Snapshot für morgen entsteht erst im Abend-Briefing) — dort erscheint die Fehlanzeige. Das
Kommando `/morgen` liefert dann ein volles Briefing, füllt aber die Timeline-Ansicht **nicht**:
der On-Demand-Pfad schreibt bewusst keinen Anker (#1007).
