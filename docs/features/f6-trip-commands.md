# Trip-Befehle per Email-Reply

Gregor Zwanzig prueft alle 5 Minuten die Inbox auf Befehle.
Du antwortest einfach auf einen bestehenden Report — fertig.

## So funktioniert's

1. Du erhaeltst einen Report per Email (z.B. `[GR221 Mallorca] Morning Report`)
2. Du antwortest auf diese Email
3. In die **erste Zeile** schreibst du den Befehl
4. Gregor verarbeitet den Befehl und schickt dir eine Bestaetigung zurueck

## Befehlsformat

```
### befehl: wert
```

Drei Rauten, Leerzeichen, Befehlsname, optional Doppelpunkt mit Wert.

## Verfuegbare Befehle

### `### ruhetag`

Verschiebt alle **zukuenftigen** Etappen um 1 Tag nach hinten.
Die heutige und vergangene Etappen bleiben unveraendert.

```
### ruhetag
```

Mit Anzahl Tage (z.B. 2 Ruhetage):

```
### ruhetag: 2
```

**Bestaetigung:**
```
[GR221 Mallorca] Ruhetag bestaetigt

Ruhetag eingetragen: +1 Tag.

Verschobene Etappen:
  Tag 3: 18.02.2026 -> 19.02.2026
  Tag 4: 19.02.2026 -> 20.02.2026

Naechster Report kommt planmaessig.
```

**Idempotenz:** Ein zweiter `### ruhetag` am gleichen Tag wird abgelehnt
(verhindert versehentliche Doppel-Verschiebung bei Email-Retry).

---

### `### report: morning` / `### report: evening`

Loest sofort einen Report aus — ohne auf den naechsten Zeitplan zu warten.

```
### report: morning
```

oder

```
### report: evening
```

---

### `### startdatum: YYYY-MM-DD`

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

### `### abbruch`

Deaktiviert alle automatischen Reports fuer diesen Trip.

```
### abbruch
```

**Bestaetigung:**
```
[GR221 Mallorca] Trip beendet

Reports fuer 'GR221 Mallorca' deaktiviert. Gute Heimreise!
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
- Der Trip wird aus dem Email-Betreff erkannt: `[Trip Name]`
- Nur Emails von deiner konfigurierten Adresse werden akzeptiert
- Unbekannte Befehle werden mit einer Hilfe-Antwort beantwortet
