---
title: SMS-Briefing — Übersicht & Leitlinie (Soll / Ist / Zeitfenster / Historie)
audience: Product Owner + Entwicklung
status: living-reference
created: 2026-07-19
related:
  - docs/reference/sms_format.md   # Wire-Vertrag (POSITIONAL, v2.x) — Single Source of Truth fürs Format
  - docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md
  - docs/specs/modules/thunder_night_at_destination_channels.md  # #1317 (Draft)
---

# SMS-Briefing — Übersicht & Leitlinie

> Diese Datei ist die **Meta-Übersicht**: Was verspricht die Spec, was macht der Code, welche
> Zeiten fließen ein — und wo ist beides über die Zeit auseinandergelaufen. Der verbindliche
> **Format-Vertrag** bleibt `docs/reference/sms_format.md`; diese Datei dupliziert ihn nicht,
> sondern erklärt Bedeutung, Zeitfenster und Historie und dient als Leitplanke für Änderungen.

## 0. Ziel: Was der Wanderer aus der SMS allein wissen muss

Die SMS ist der **einzige** Kanal, der den Weitwanderer unterwegs sicher erreicht — kein Netz für
die App, kein Abruf der großen E-Mail, keine Möglichkeit nachzuschlagen. Sie muss daher
**selbsttragend** sein: Alles, was zur Entscheidung nötig ist, steht in diesen 160 Zeichen, und
zwar für den **gesamten Zeitraum bis zum nächsten Briefing** — vom Aufbruch über die Wanderung bis
zur Nacht am Ziel.

Konkret muss der Wanderer allein aus der SMS beantworten können:

1. **Muss ich meine Pläne ändern?** Droht etwas Gefährliches — Gewitter, Sturm, Starkregen — und
   **wann** (Zeitfenster)? Kann ich früher los, um vor dem Gewitter am Ziel zu sein?
2. **Wie rüste ich mich aus?** Temperatur-Spanne (Tief/Hoch), Regen, Wind — was muss griffbereit
   sein, wie ziehe ich mich an.
3. **Was erwartet mich am Ziel — auch nach der Ankunft?** Am Lagerplatz oder an der Hütte ist der
   Wanderer am **exponiertesten** (Zelt, keine Fluchtmöglichkeit). Ein Abendgewitter nach Ankunft
   ist sicherheitsrelevanter als eines während des Gehens, weil er ihm nicht ausweichen kann.
4. **Wie sehr kann ich mich darauf verlassen?** Vorhersage-Verlässlichkeit (`C`).
5. **Was kommt morgen?** Grobe Vorschau (`TH+:`), um vorauszuplanen.

**Leitsatz:** Die SMS beantwortet „Was erwartet mich wettermäßig, bis ich das nächste Briefing
bekomme — und ist etwas davon gefährlich genug, meine Pläne zu ändern?" Daraus folgt unmittelbar,
dass die reine **Wanderzeit** zu kurz greift: Der relevante Zeitraum endet nicht mit der Ankunft,
sondern reicht bis zum nächsten Briefing — inklusive Nachmittag, Abend und Nacht am Ziel. Das ist
der fachliche Grund hinter Issue #1317.

## 1. Aufbau einer Trip-SMS (Wander-Briefing)

Feste Reihenfolge (POSITIONAL, `sms_format.md:44`):

```
{Name}: N D R PR W G TH: TH+: C  HR:TH:  Z: M:  [SN SN24+ SFL AV WC]  DBG
```

| Kürzel | Bedeutung | Wert-Format | Immer da? |
|---|---|---|---|
| `{Name}:` | Etappen-/Ortsname (max. 10 Zeichen, km-Bereich bleibt) | `Paliri:` / `GR221 km0-11:` | ja |
| `N` | Nacht-/Tief-Temperatur °C | `N8`, `N-12`, `N-` | ja |
| `D` | Tag-/Höchst-Temperatur °C | `D24`, `D-` | ja |
| `R` | Regen (mm) | `R0.2@6(1.4@16)` / `R-` | ja |
| `PR` | Regenwahrscheinlichkeit (%) | `PR20%@11(100%@17)` / `PR-` | ja |
| `W` | Wind (km/h) | `W10@11(15@17)` / `W-` | ja |
| `G` | Böen (km/h) | `G20@11(30@17)` / `G-` | ja |
| `TH:` | Gewitter am **berichteten Tag** (Morgen-Briefing = heute, Abend-Briefing = morgen) | `TH:M@16(H@18)` / `TH:-` | ja |
| `TH+:` | Gewitter am **Tag danach** (Morgen-Briefing → morgen, Abend-Briefing → übermorgen) | `TH+:M@14(H@17)` / `TH+:-` | ja |
| `C` | Vorhersage-Verlässlichkeit | `C+` / `C~` / `C?` | nur wenn Provider Konfidenz liefert |
| `HR:` `TH:` | Amtliche Warnungen Frankreich (Starkregen / Gewitter) | `HR:M@17TH:H@17` | nur FR-Provider |
| `Z:` `M:` | Feuerzonen / gesperrte Masslive (Korsika) | `Z:HIGH208 M:24` | nur Korsika |
| `SN SN24+ SFL AV WC` | Wintersport (Schnee, Neuschnee, Schneefallgrenze, Lawine, Wind Chill) | `SN180 …` | nur Wintersport-Profil |
| `DBG[...]` | Debug (Provider, Konfidenz) | `DBG[MET MED]` | nur Testlauf |

**Das Wert-Format `X@h(Y@h)` lesen als:** „Wert X ab Stunde h, Spitzenwert Y um Stunde h."
Beispiel `TH:M@16(H@18)` = Gewitter mittlerer Stufe ab 16 Uhr, steigt auf hohe Stufe um 18 Uhr.
Ein `-` (z. B. `TH:-`) heißt „nichts über der Schwelle / keine Daten". Uhrzeiten sind Ortszeit,
ohne führende Null. Gewitter-Stufen: `M` = mittel, `H` = hoch (kein „L").

**Auslöse-Schwellen** (unterhalb → `-`): Regen 0,2 mm · Regenwahrscheinlichkeit 20 % · Wind 10 km/h ·
Böen 20 km/h · Gewitter ab mittlerer Stufe. Pro Trip/Metrik überschreibbar.

**Beispiele (aus `sms_format.md` §8):**
- Alles ruhig: `Ballone: N9 D16 R- PR- W- G- TH:- TH+:-`
- Voll: `Paliri: N8 D24 R0.2@6(1.4@16) PR20%@11(100%@17) W10@11(15@17) G20@11(30@17) TH:M@16(H@18) TH+:M@14(H@17)`

## 2. Welche Zeit fließt ein? (der Kernpunkt)

**Verbindliche Regel heute (Ist-Code):** **Alle** „Heute"-Werte (`N D R PR W G TH:`) werden
ausschließlich aus der **Wanderzeit der Etappe** berechnet — vom Etappenstart bis zur
**Ankunftsstunde** am Ziel (`sms_trip.py:106-130`; Temperatur über die wanderzeit-gefensterten
Segment-Aggregate, `segment_weather.py:173-196`).

**Was das bedeutet:** Wetter, das **nach der Ankunft** am Ziel eintritt (Nachmittag/Abend/Nacht am
Lagerplatz oder in der Hütte), erscheint in der SMS **nicht** — auch wenn die große E-Mail es in der
Tabelle „Nacht am Ziel" zeigt. Genau das ist der offene Streitpunkt (Issue #1317).

**`TH+:` (Folgetag)** kommt aus einer anderen Quelle (Mehrtages-Trend bzw. eigener Abruf der
Folge-Etappe), nicht aus der Nacht am Ziel.

**Soll-vs-Ist-Abweichung:** Der Format-Vertrag (`sms_format.md`) beschreibt `R/PR/W/G` als
„Tagesfenster der Etappe", der Code fenstert sie aber auf die reine Wanderzeit (seit #925, s. u.).
Diese Diskrepanz ist real und sollte bei einer Fenster-Entscheidung mit aufgelöst werden.

**Morgen- vs. Abendbriefing:** Kein eigenes Format, kein anderes Zeitfenster. Der einzige
Unterschied ist die **Bezugs-Etappe**: `TH:` ist die Etappe, über die der Report spricht
(Morgen-Report = heute, Abend-Report = morgen), `TH+:` die Etappe danach. Der „Nacht am Ziel"-
Datensatz existiert seit #1313 für **beide** Report-Typen, wird von der SMS aber (noch) nicht genutzt.

## 3. Zeichenbudget

Max. 160 Zeichen (GSM-7, Umlaute werden transliteriert). Wird es zu lang, fallen Token in fester
Reihenfolge weg: zuerst Debug → Wintersport → Feuerzonen → Spitzenwerte in Klammern →
Regenwahrscheinlichkeit → Temperaturen. **Gewitter (`TH:`) fällt zuletzt** — es hat die höchste
Priorität. Minimum ist Name + mindestens ein Wert-Token.

## 4. Historie — was wirklich passierte (ehrlich)

Der SMS-Code entstand erst **Februar 2026**; „vor einem Jahr" gab es noch keine Trip-SMS. Der
Eindruck „war mal besser, wurde kaputtgemacht" trifft **einen realen Kern**, aber nicht als
„Zerstörung": Das **Format** wurde über die Zeit deutlich **reicher** — angeschlossen wurden aber
zeitweise **leere, erfundene oder zu eng gefensterte Daten**. Reich aussehende SMS, die weniger
verlässlich waren als das schlichte Ur-Format.

| Datum | Issue | Was geschah | Wertung |
|---|---|---|---|
| 2026-02-04 | — | Ur-Format `E1:T12/18 W30 R5mm RISK:Gewitter@14h`. Grob, aber Gewitter funktionierte. | Basis |
| 2026-04-25 | v2.0-Spec | Reiches Token-Format eingeführt (Onset+Peak, Gewitter heute/Folgetag, Vigilance, Feuerzonen). | ＋ konzeptionell |
| 2026-04-28 | β3 | Umbau aufs neue Format — **Gewitter-heute (`TH:`) wurde dabei nie an die Daten angeschlossen** → zeigte ~2,5 Monate **immer** `TH:-`. | **－ stille Regression** |
| 2026-06-24 | #874 | `TH+:` bekam eine **fest erfundene Uhrzeit** (`@12`) — sah aus wie Vorhersage, war Konstante. | ± |
| 2026-06-30 | #925 | Werte wurden präziser (echte Stundenreihe), **aber das Fenster auf die reine Wanderzeit verengt** → Wetter am Ziel nach Ankunft fällt heraus. | ± (genau dein Schmerzpunkt) |
| 2026-07-17 | #1275 / ADR-0025 | **Große Reparatur:** `TH:` endlich an echte Daten angeschlossen; `TH+:`-Uhrzeit echt statt erfunden; alle Kanäle auf **eine** gefensterte Gewitter-Quelle (kein 02:00-Nacht-Gewitter-Fehlalarm mehr); Ankunftsstunde wieder inklusiv. | ＋＋ |

**Zusammengefasst:** Nicht „zerstört", sondern reicher gemacht und dabei die Datenverdrahtung
zeitweise verpfuscht — das Meiste ist seit dem 17.07. repariert. **Offen** bleibt genau ein Punkt:
Das SMS-Fenster ist **wanderzeit-gebunden**; „Wetter/Gewitter am Ziel nach Ankunft" fehlt strukturell.

## 5. Vereinbartes Zielkonzept (PO-Entscheid 2026-07-19)

Ersetzt das „nur Wanderzeit"-Modell. Löst #1317 als Nebeneffekt. Orientiert sich am
Vorgängerprojekt `weather_email_autobot` (festes Tagesfenster über die Etappe), verbessert es aber.

1. **Einstellbares Tagesfenster**, Default **04:00–19:00 Uhr**, **pro Wanderung** konfigurierbar (bei
   der SMS-Einstellung). Das Vorgängerprojekt hatte 04–19 fest verdrahtet; hier wird es einstellbar.
2. **Werte über das ganze Fenster** statt nur über die Gehzeit — für alle Wert-Token (`R PR W G TH:`).
   Damit erscheint ein Nachmittags-/Abend-Gewitter am Ziel wieder (der #1317-Fall, 14:00-Gewitter).
3. **Ortsbezug ortsgenau:** bis zur Ankunft entlang der Route (Segmente), nach der Ankunft am Ziel
   — beides im Fenster. Speist sich aus **denselben Stunden-Rohdaten wie die E-Mail-Detailtabelle**
   (Segment-`timeseries` + Ziel-/`night_weather`-Stunden), nur verdichtet zu Onset+Peak. → Tabelle
   und SMS können nie widersprechen.
4. **N (Nacht-Tiefsttemperatur):** nur im **Abendbriefing**, Tiefstwert der **kommenden Nacht am
   aktuellen Schlafplatz** (Etappenende) — getrennt vom Tagesfenster. Im Morgenbriefing entfällt N.
5. **Bezugstag / Vorschau `TH+:`:** `TH:` = berichteter Tag (Morgen = heute, Abend = morgen),
   `TH+:` = Tag danach (Morgen → morgen, Abend → übermorgen). Rein aus `report_type` ableitbar.
6. **Gilt einheitlich für alle Kurzformen** (SMS, E-Mail-Kurzzusammenfassung, Telegram-Fußzeile) —
   dasselbe Fenster, dieselbe Quelle (ADR-0025-Konsistenz).
7. **Regenwahrscheinlichkeit in voller Stundenauflösung** (das Vorgängerprojekt nahm nur ein grobes
   3-Stunden-Raster 5/8/11/14/17 — hier bewusst feiner).
8. **Nacht-Gewitter/-Regen fürs Zelten** (über 19 Uhr hinaus) ist bewusst **kein** Teil dieses
   Konzepts, sondern ein späteres, optionales Feature.
9. **Amtliche Warnungen** in SMS/Kurzzusammenfassung bleiben ausgelagert → #1318.

**Umsetzungsstand (Stand 2026-07-19):** **Scheibe A umgesetzt** (im Code, Staging-/Deploy-pending) —
die Wert-Token **R/PR/W/G/TH:** aller vier Kurzformen kommen jetzt aus dem festen Tagesfenster
04:00–19:00 (geteiltes Modul `src/output/renderers/day_window.py`); dadurch löst sich #1317. Noch
offen: **N/D-Temperatur** (Scheibe D) und **Einstellbarkeit** des Fensters (Scheibe B/C) laufen
weiterhin über die Wanderzeit bzw. die feste Konstante. Damit ist Abschnitt 2 („nur Wanderzeit") für
die Wert-Token überholt, für Temperatur noch gültig.

## 6. Leitplanken für jede SMS-Änderung (nicht verletzen)

- **Eine Quelle, ein Fenster für alle Kanäle** (SMS, Kurzzusammenfassung, E-Mail-Kopf-Kacheln,
  Telegram-Fußzeile): Widersprüche zwischen den Kanälen sind der Hauptfehler, den ADR-0025 verbietet.
  Wird das Fenster geändert, dann für **alle** Kanäle gleichzeitig.
- **Rohquelle ist `dp.thunder_level`** (bzw. die echten Stundenwerte) — nie ein Tages-Aggregat.
- **Keine erfundenen Uhrzeiten** — fehlt die Stunde, dann `-`, nicht raten (Lehre aus #874).
- **Skalen nicht vermischen:** Sortier-Skala (`thunder_ordinal`) ≠ Anzeige-Skala (`thunder_label_value`).
- **Beweis über die echte Ausgabe** (`format_sms()`), nicht über zwischengeschaltete Bauteile.
- **160-Zeichen-Budget** im Blick behalten; Gewitter hat höchste Priorität.
