---
entity_id: fix_2078_kurznachricht_tokengrenze
type: bugfix
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [sms, premium-sms, telegram, onset, zeichenbudget, khw]
---

# Kurznachricht: der Schnitt trifft den Ortsnamen, nie das Zeit-Token (#2078)

## Approval

- [ ] Approved — PO, 2026-08-__

## Purpose

Die Onset-Kurznachricht wird bei Ueberlaenge mit `body[:limit]` hart
abgeschnitten. Der Schnitt sitzt am ENDE des Textes -- und dort stehen genau
die Zeit-Token. Aus `R2.5@23:50 >@Sa0:40` wird `R2.5@23:50 >@Sa0:4`, und
`0:4` liest sich als Uhrzeit. Das ist keine gekuerzte, sondern eine
inhaltlich **falsche** Aussage.

Betroffen sind SMS, **Premium-SMS** und der Telegram-Kurzstil -- alle drei
tragen denselben `sms_body`. Auf der Huette am Karnischen Hoehenweg kommt
nur die Premium-SMS an; dort gibt es keinen zweiten Kanal, der die Aussage
richtigstellt.

Die Nachbarzweige loesen das bereits anders: `_render_sms_corridor_only`
kappt den Kopf auf `[:16]`/`[:24]`, bevor zusammengesetzt wird,
`_render_sms_body` nimmt Token nur auf, solange sie ganz passen. Der
Onset-Zweig und der Beginn-Verschiebungs-Zweig tun beides nicht.

**Leitsatz dieser Aenderung:** Zeichenmangel darf Information kosten, aber
nie Information **verfaelschen**. Der Ortsname ist die verlustaermste
Stelle -- ein gekuerzter Ortsname bleibt als Ortsname erkennbar, eine
gekuerzte Uhrzeit wird zu einer anderen Uhrzeit.

## Source

- **File:** `src/output/renderers/alert/render.py` — **Identifier:**
  `_render_sms_onset` (Zeile 895, harter Schnitt :964), Kopf ungekappt
- **File:** `src/output/renderers/alert/render.py` — **Identifier:**
  `_render_sms_onset_shift_only` (Zeile 466, harter Schnitt :471), Kopf
  ungekappt — **derselbe Defekt**, drei Zeilen daneben
- **File:** `src/output/renderers/alert/render.py` — **Identifier:** NEU
  `_fit_head` (gemeinsamer Baustein) und `_SMS_LIMIT_DEFAULT` (Konstante)
- **File:** `src/output/renderers/alert/render.py` — **Identifier:**
  `render_sms` (:1452), `_render_sms_body` (:1474), `_render_sms_onset`
  (:895) — die drei Stellen, die `140` je fuer sich fuehren

## Estimated Scope

Ein Renderer-Modul, ~45 LoC netto plus Tests. Kein Datenmodell, keine
Migration, keine API-Aenderung. Frontend nicht beruehrt.

## Dependencies

- Baut auf `_sms_onset_ende` (#2051 S1) und `_sms_onset_time` (#2054) auf --
  beide unveraendert; diese Aenderung fasst nur den Zusammenbau an.
- Keine Abhaengigkeit zu #2063 (Onset-Uhrzeit eine Minute zu frueh) --
  anderer Mechanismus, andere Stelle.

## Implementation Details

### 1. Der Kopf gibt nach, nicht der Schwanz

Beide Zweige bauen heute `head + tail` und schneiden das Ergebnis ab. Neu
wird zuerst der **Schwanz** (Token-Strecke) gemessen und dem Kopf der
Rest des Budgets zugeteilt:

```python
_SMS_LIMIT_DEFAULT = 140  # eine Quelle fuer alle drei Aufrufstellen


def _fit_head(head: str, tail: str, limit: int) -> str:
    """Setzt `head: tail` so zusammen, dass der SCHWANZ ganz bleibt."""
    body = f"{head}: {tail}"
    if len(body) <= limit:
        return body                      # Normalfall: byte-identisch
    frei = limit - len(tail) - 2         # 2 == len(": ")
    if frei > 0:
        return f"{head[:frei].rstrip(' (-_')}: {tail}"
    return _cut_at_token_boundary(tail, limit)
```

Damit ist der Normalfall **byte-identisch** zum Bestand: solange der Text
passt, laeuft kein neuer Code. Erst bei Ueberlaenge greift die Umverteilung.

Das `rstrip(' (-_')` uebernimmt die Schreibweise der Nachbarzweige
(`_render_sms_corridor_only`, `_render_sms_body`): ein Ortsname, der auf ein
Leerzeichen oder eine geoeffnete Klammer endet, sieht kaputt aus.

### 2. Der Entartungsfall schneidet an der Token-Grenze

Reicht das Budget nicht einmal fuer den Schwanz allein (Kopf faellt komplett
weg), bleibt die Laengen-Zusicherung bestehen -- aber der Schnitt sitzt an
der letzten **Leerzeichen-Grenze**, die noch passt, nie innerhalb eines
Token. Passt nicht einmal das erste Token, bleibt der harte Schnitt als
letzte Garantie; dann ist die Nachricht ohnehin unbrauchbar, und ein
unbrauchbarer Text ist besser als ein falscher, der nach einer gueltigen
Uhrzeit aussieht.

### 3. Warum keine feste Kopf-Kappung auf `[:24]`

Die naheliegende Variante -- Kopf immer auf 24 Zeichen wie die Nachbarn --
wurde **verworfen**: sie kuerzt auch dann, wenn gar kein Platzmangel
besteht, und nimmt damit Ortsnamen weg, die heute vollstaendig zugestellt
werden. Die budgetabhaengige Zuteilung kuerzt genau dann und genau so viel,
wie der Platz es erzwingt.

Nebeneffekt, der die Issue-Frage nach einer **Messgrundlage** aufloest: Die
Frage „wie lang wird ein `location_label` in den Prod-Daten maximal?"
braucht nicht mehr beantwortet zu werden. Eine feste Schwelle haette sie
gebraucht (zu niedrig = unnoetiger Verlust, zu hoch = Bug bleibt); die
Zuteilung aus dem Budget ist fuer **jede** Laenge richtig.

### 4. Das dreifache `140`

`_render_sms_onset`, `render_sms` und `_render_sms_body` fuehren den Default
je fuer sich. Sie lesen kuenftig `_SMS_LIMIT_DEFAULT`. Der Wert bleibt `140`
-- die Abweichung zum Produktlimit 160 ist eine eigene Frage und wird hier
**nicht** angefasst.

## Expected Behavior

| Fall | heute | danach |
|---|---|---|
| Text passt ins Budget | `Ort: R2.5@23:50 >@Sa0:40` | unveraendert (byte-identisch) |
| Kopf zu lang | `…langerOrt: R2.5@23:50 >@Sa0:4` | `…langerOr: R2.5@23:50 >@Sa0:40` |
| Kopf sehr lang | `…: R2.5@23:50 >@Sa` | Kopf faellt bis auf den Rest weg, Zeit ganz |
| Schwanz allein zu lang | mitten im Token geschnitten | an der Leerzeichen-Grenze geschnitten |
| Beginn-Verschiebung | mitten im Token geschnitten | wie oben |

## Acceptance Criteria

**AC-1:** Given ein Onset-Ereignis, dessen Ortsname so lang ist, dass
`Kopf: Schwanz` das Limit ueberschreitet, When die Kurznachricht gerendert
wird, Then erscheint die Token-Strecke (Zeit-, Mengen-, Ende-Token)
vollstaendig und unveraendert, und allein der Ortsname ist gekuerzt.

**AC-2:** Given Ortsnamen jeder Laenge von 0 bis 200 Zeichen, When die
Kurznachricht fuer jede dieser Laengen gerendert wird, Then endet keine
Ausgabe auf ein angeschnittenes Zeit-Token -- geprueft als Eigenschaft
ueber alle Laengen, nicht an einem Beispiel.

**AC-3:** Given eine Kurznachricht, die schon heute ins Budget passt, When
sie gerendert wird, Then ist das Ergebnis byte-identisch zum Bestand -- die
Aenderung wirkt ausschliesslich im Ueberlauf.

**AC-4:** Given einen beliebigen Eingabefall inklusive der Entartung
(Schwanz allein laenger als das Limit), When gerendert wird, Then gilt
`len(body) <= limit` unveraendert weiter.

**AC-5:** Given einen Ortsnamen, dessen Kuerzung auf einem Leerzeichen,
Bindestrich, Unterstrich oder einer geoeffneten Klammer endet, When
gerendert wird, Then traegt der Kopf dieses Zeichen nicht mehr.

**AC-6:** Given einen reinen Beginn-Verschiebungs-Alarm
(`_render_sms_onset_shift_only`) mit ueberlangem Kopf, When die
Kurznachricht gerendert wird, Then gilt AC-1 dort gleichermassen -- der
Zweig traegt denselben Defekt und wird in derselben Scheibe saniert.

**AC-7:** Given einen Schwanz, der allein laenger als das Limit ist, When
gerendert wird, Then sitzt der Schnitt an einer Leerzeichen-Grenze und die
Ausgabe enthaelt kein teilweises Token.

**AC-8:** Given eine Laufzeit-Mutation von `_SMS_LIMIT_DEFAULT`, When
`render_sms`, `_render_sms_body` und `_render_sms_onset` ohne
`limit`-Argument aufgerufen werden, Then folgen alle drei dem mutierten Wert
-- Nachweis, dass keine vierte Kopie der Zahl stehengeblieben ist
(Mutations-Gegenprobe statt Dateiinhalt-Check).

**AC-9:** Given eine Nachtragsmeldung (`Erg `-Praefix, um die
Praefixlaenge verkleinertes Limit), When sie mit ueberlangem Kopf gerendert
wird, Then gelten AC-1 und AC-4 auf das Gesamtergebnis inklusive Praefix.

## Known Limitations

- **Keine Prod-Messung.** Die im Issue geforderte Erhebung des laengsten
  real vorkommenden `location_label` aus `/var/lib/gregor` ist aus dieser
  Cloud-Sitzung nicht erreichbar (nur mit sudo auf dem Server). Der Entwurf
  ist deshalb bewusst so gewaehlt, dass er **ohne** diese Zahl auskommt
  (siehe Implementation Details 3). Die Messung bleibt sinnvoll, um zu
  wissen, wie oft der Fall ueberhaupt eintritt -- sie ist aber keine
  Voraussetzung fuer die Korrektheit.
- **`_render_sms_corridor_only` bleibt aussen vor.** Dort ist der Kopf
  bereits gekappt; geschnitten wird die Token-LISTE. Die richtige Loesung
  dort ist die `+k`-Grammatik aus `_render_sms_body` (Token weglassen und
  zaehlen) -- eine eigene Entscheidung mit eigenem sichtbarem Textwechsel.
  Nebenbefund fuer #1199, nicht Teil dieser Scheibe.
- **140 vs. 160 bleibt.** Diese Scheibe vereinheitlicht nur die Herkunft der
  Zahl, nicht ihren Wert.

## Architektur-Entscheidung (ADR)

Kein neues ADR noetig: die Aenderung fuehrt keine neue Entscheidungsflaeche
ein, sondern zieht den Onset-Zweig auf das Verhalten nach, das die
Nachbarzweige derselben Datei schon zeigen.

## Changelog

- 1.0 (2026-08-22) — Erstfassung, zur Freigabe.
