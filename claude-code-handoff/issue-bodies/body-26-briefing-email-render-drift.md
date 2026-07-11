<!-- gregor-zwanzig-handoff: stable_id=briefing-email-render-drift -->

# Briefing-Email · Render-Drift gegen Design + Tageslage-Lead / Vortag-Vergleich (Issue #26)

Die ausgelieferte Morgen-/Briefing-Email ist von der Design-Vorgabe
(`screen-output-preview.jsx` → `EmailPreview` + `EmailDataTable`) abgedriftet.
Inhaltlich sind die Werte korrekt — **das Layout** weicht an mehreren Stellen ab.
Dieses Issue listet die Abweichungen als prüfbare Fixes und spezifiziert
zusätzlich zwei Elemente, die im Build bereits auftauchen, aber sauber ins
Design integriert gehören: **Tageslage-Lead** und **Vortag-Vergleich**.

**Kanonische Quelle:** `screen-output-preview.jsx` (Projekt-Wurzel).
**Renderer im Repo:** `trip_report.py` (Email-HTML) bzw. die entsprechende
SvelteKit-Mail-Komponente.

| | |
|---|---|
| IST (aktueller Build) | `…/issue-assets/ist-briefing-email-render-drift.png` |
| SOLL (Header + Lead) | `…/issue-assets/soll-briefing-email-render-drift-top.png` |
| SOLL (gruppierte Tabelle) | `…/issue-assets/soll-briefing-email-render-drift-table.png` |

URL-Präfix: `https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/`

---

## Teil A · Render-Drift beheben

### A1 · Header fehlt fast komplett
**IST:** Nur ein nacktes Datum (`27.06.2026`).
**SOLL** (`EmailPreview`-Header): Eyebrow `MORGEN-BRIEFING · <code>`, Etappen-Titel,
Datum+Uhrzeit als Mono-Zeile, rechts die Wordmark `GREGOR ZWANZIG` + Trip-Kurzname
+ `Etappe X / 12`. Absender-Identität und Etappen-Kontext müssen zurück.

### A2 · Tabelle: Spalten-Gruppierung verloren
**IST:** Eine flache 15-Spalten-Tabelle mit einzeiligem Header
(`Time Feels Wind Gust WDir Rain Rain% Thdr Thndr% SnowL Cloud CldLow Visib UV 0°Line`).
**SOLL** (`EmailDataTable`): **zweistufiger Header** mit Spalten-Gruppen
**TEMP · WIND · NIEDERSCHLAG · SICHT/UV · HÖHE**, farbige Gruppen-Labels
(Temp = `#c45a2a`, Niederschlag = `#2a6a8c`), darunter die Einzel-Header.
Die Gruppierung ist die wichtigste verlorene Eigenschaft — sie macht 14 dichte
Spalten scanbar.

### A3 · Risiko-Ampel-Spalte fehlt
**SOLL:** letzte Spalte pro Stunde = `RiskDot` (grün `#15803d` / orange `#c2410c`
/ rot `#b91c1c`, mit Ring). Im IST gibt es keine Risiko-Kennzeichnung in der Tabelle.

### A4 · Tausender-Trennzeichen fehlt
**IST:** 0°-Linie als `4660`.
**SOLL:** de-DE-Format `4.660` (Helper `fmt()` in `screen-output-preview.jsx`,
`toLocaleString("de-DE")`). Gilt für alle ≥ 1.000er-Werte (0°-Linie, Höhen).

### A5 · Header-Sprache: deutsche User-Sprache statt englischer Kürzel
**IST:** `Time, Feels, WDir, Thdr, Thndr%, SnowL, CldLow, Visib, 0°Line`.
**SOLL:** `h, °C, gef., km/h, böe, dir, mm, R%, Gw%, km, UV, 0°m`
(siehe `EmailDataTable`-Header). CLAUDE.md-Regel „User-Sprache, kein Fach-/
Englisch-Slang in der UI".

---

## Teil B · Zwei Build-Elemente sauber integrieren

Der Build zeigt bereits (a) einen blauen **Etappen-Summary-Banner** und (b) einen
**„Vergleich zum Vortag"-Callout**. Inhaltlich gewollt — aber als **zwei**
gestapelte farbige Boxen mit je eigener Orange-Bar (und unterschiedlicher
Einrückung, siehe B3) redundant. Das Design bündelt beide in **einem**
Akzent-Bar-Lead („Tageslage"), siehe `EmailPreview` →
`EmailVortag` + Tageslage-Block.

### B1 · Tageslage-Lead (ersetzt den blauen Summary-Banner)
Ein Block direkt nach dem Header, **immer sichtbar**:
- Linke `2px`-Akzent-Bar `#c45a2a`, Inhalt mit `padding-left`.
- Eyebrow `TAGESLAGE` (accent).
- Der Etappen-Summary-Satz als Lead (16 px, `#1d1c1a`, `font-weight:500`) —
  **kein** ausgefüllter blauer Kasten.

### B2 · Vortag-Vergleich (ersetzt den zweiten Callout)
Direkt unter dem Lead, **innerhalb desselben Blocks**, als **dezente Mono-Zeile**
mit Haarlinie oben — keine zweite Box:
```
VS. GESTERN  ▲  heute bessere Sicht als gestern
```
- Label `VS. GESTERN` (Mono, 9 px, uppercase, `#9a978d`).
- Trend-Glyph: `▲` better = `#15803d` · `▼` worse = `#c2410c` · `▬` same = `#6b6962`.
- Vergleichstext in `#3a3835`, 12.5 px.
- **Kein** Wetter-Emoji (Mono-Bruch in Outlook/Gmail — gleiche Regel wie #561).

### B3 · Einrückung gleichziehen (PO-Punkt)
Im IST sitzt der Summary-Banner bündig an der Card-Kante (Orange-Bar bei x≈0),
der Vortag-Callout ist horizontal eingerückt (Orange-Bar ~40 px innen). Nach der
Integration (B1+B2) teilen beide **dieselbe linke Kante** — die eine `2px`-Bar des
Tageslage-Blocks. Damit ist der Versatz strukturell gelöst.

### B4 · „TAGESLICHT OHNE STIRNLAMPE" bleibt entfernt
Die Stirnlampe-/Tageslicht-Sektion ist im Design entfernt (PO 2026-06-26) und
darf **nicht** wieder eingebaut werden. Der Build hat sie bereits nicht — Status
beibehalten.

---

## Datenfelder (Backend / Renderer)

| Feld | Quelle | Hinweis |
|------|--------|---------|
| `stage.summary` | bestehender Tageslage-Satz | unverändert, jetzt im Lead |
| `vortag.trend` | `enum(better, worse, same)` | Vergleich einer Leit-Metrik (z. B. Sicht) zum Vortag |
| `vortag.text` | generierter Satz | z. B. „heute bessere Sicht als gestern" |

Vergleichslogik (Vortag): dieselbe Leit-Metrik gestern vs. heute (Tages-Aggregat),
Schwelle für „besser/schlechter" wie bei den Briefing-Schwellwerten. Identische
Logik in Backend-Renderer **und** Live-Vorschau dokumentieren.

---

## Acceptance Criteria

- [ ] A1 — Voller Email-Header (Eyebrow, Titel, Datum/Zeit, Wordmark, Etappe X/12)
- [ ] A2 — Tabelle mit zweistufigem, gruppiertem Header (TEMP/WIND/NIEDERSCHLAG/SICHT·UV/HÖHE) + Gruppen-Farben
- [ ] A3 — Risiko-Ampel-Spalte (`RiskDot`) pro Stunde
- [ ] A4 — Tausender-Trennzeichen (de-DE) für ≥1.000er-Werte
- [ ] A5 — Deutsche Einheiten-Header statt englischer Kürzel
- [ ] B1 — Tageslage-Lead mit Akzent-Bar statt blauem Banner
- [ ] B2 — Vortag-Vergleich als dezente Mono-Zeile (Trend-Glyph, kein Emoji)
- [ ] B3 — Summary + Vortag bündig an derselben linken Kante
- [ ] B4 — Keine Stirnlampe-/Tageslicht-Sektion
- [ ] Live-Vorschau und ausgelieferte Email rendern identisch

---

## Out of Scope (Folge-Issues)

- Metriken-Überblick-Pills (bereits #664).
- Mehrtages-Trend / „Nächste Etappen"-Block (bereits #561).
- Telegram-/SMS-Renderer (Kanal-Constraints in #14 / #496).
