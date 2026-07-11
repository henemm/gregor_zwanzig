<!-- gregor-zwanzig-handoff: stable_id=issue-496-channel-preview -->
## Problem

Der Block **„VORSCHAU · SO KOMMT ES BEIM EMPFÄNGER AN · Pro Kanal"** im
Wetter-Metriken-Editor (Trip-Detail → Wetter-Tab) zeigt heute **vier kleine
Kacheln nebeneinander** (`ChannelPreviewBlock.svelte` + `ChannelPreviewCard.svelte`).
Jede Kachel quetscht eine Monospace-Mini-Tabelle in ~200 px.

Das funktioniert nicht:
- Eine **Email-Tabelle hat keine Spalten-Grenze** (20+ Spalten möglich) — eine
  200-px-Kachel kann das physisch nicht ehrlich abbilden.
- Was man sieht, sind unleserliche Mono-Fragmente — der User kann **nicht
  ablesen, was passiert**, wenn er z. B. 12 Metriken wählt.
- Der eigentliche Entscheidungs-Moment (**„rutschen wichtige Metriken in die
  Detail-Zeile oder fallen sie ganz weg?"**) bleibt unbeantwortet.

## Entscheidung (Claude Design · Tech-Lead)

Die Design-Request bot drei Richtungen an (A nur Konsequenz-Zahlen, B nur
Ein-Kanal-Vorschau, C Block entfernen). **Keine trägt allein** — daher
**A + B kombiniert** als **zwei Schichten in einem Block**:

| Schicht | Inhalt | Beantwortet |
|---|---|---|
| **1 · Konsequenz-Leiste** | alle 4 Kanäle kompakt untereinander (Desktop) / 2×2 (Mobile): je „X Spalten / Limit · N rutschen · +M Detail", Status-Dot. **Klick = Kanal-Wähler.** | „Passt meine Auswahl — und welcher Kanal ist der Engpass?" |
| **2 · Ehrliche Ein-Kanal-Vorschau** | EIN Kanal in **realistischer Original-Breite**: echte Email-Tabelle (Desktop **und** iPhone-Mail), echte Signal/Telegram-Bubble (≈272/330 px), echte SMS im Spec-Token-Code. | „Sieht es beim Empfänger richtig aus?" |

Begründung: Das Produkt-Grundgesetz sagt **„Vorschau = Verifikations-Tool im
Setup"** (CLAUDE.md) — Option C wirft genau diesen Nutzen weg. A allein ist zu
schwach (keine Fidelity), B allein verliert den Quervergleich. A+B löst das
200-px-Grundproblem, weil immer nur **ein** Kanal in voller Breite rendert.

Mockup-Referenz im Design-Repo: `screen-channel-preview-redesign.jsx`
(Komponente `ChannelPreviewRedesign`), eingebaut in `screen-metrics-editor.jsx`.
Demo im Canvas `Gregor 20 - Kanal-Vorschau.html`.

## Kanal-Constraints (unverändert, identisch Backend-Renderer)

| Kanal | Max Spalten | Vorschau-Form |
|---|---|---|
| Email | ∞ | volle HTML-Tabelle · zusätzlich iPhone-Mail (gestapelt) |
| Telegram | 8 | Monospace-Tabelle in Bubble (≈330 px) |
| Signal | 6 | Monospace-Tabelle in Bubble (≈272 px) |
| SMS | 0 | **kein Raster** · Token-Code · 140 Zeichen |

## SMS — striktes Token-Format (NICHT „ · "-Fließtext!)

**Kritisch (PO 2026):** SMS wird **nicht** als hübscher punkt-getrennter Text
gerendert. Es gilt das feste Token-Format aus `screen-output-preview.jsx::SMSPreview`,
sonst entstehen Missverständnisse. SMS ist **kein Spalten-Kanal** — nur
entscheidungskritische Metriken haben einen Code, der Rest fällt weg.

```
KHW03: N8 D11 W12@11(24@13) G25@12(43@14) PR53%@12 R3.2 TH5%@12 Z:WATCH:2447
```

| Token | Bedeutung |
|---|---|
| `N{lo} D{hi}` | Nacht-Tief / Tag-Hoch °C (← Metrik `temp`) |
| `R{mm}` / `R-` | Regen mm, `-` = keiner (← `precip`) |
| `PR{p}%@{h}` | Regen-Wahrsch. %@Stunde (← `rainProb`) |
| `W{v}@{h}({max}@{h})` | Wind km/h@Std (Max@Std) (← `wind`) |
| `G{v}@{h}({max}@{h})` | Böen km/h@Std (Max@Std) (← `gust`) |
| `TH{p}%@{h}` · `TH+:L/M/H@{h}` | Gewitter %@Std bzw. Level (← `thunder`) |
| `HR:L/M/H@{h}` | Starkregen-Level @Std |
| `Z:HIGH/MED/LOW:{höhe}` | Ziel-Risiko + Max-Höhe (strukturell, immer dabei) |
| `-` | kein Wert |

Metriken **ohne** SMS-Token (z. B. Gefühlte Temp, Bewölkung, Sicht, UV,
Luftfeuchtigkeit, Windrichtung, Nullgrad-Grenze, Taupunkt) erscheinen im
SMS-Kanal **nicht** — die Vorschau muss das explizit als „fällt weg · kein
SMS-Code" ausweisen (Mapping-Spalte).

## Renderer-Logik (Frontend, identisch zum Backend)

```ts
// Spalten-Kanäle (Email/Telegram/Signal)
function applyChannel(primary: string[], secondary: string[], maxCols: number) {
  const inTable = primary.slice(0, maxCols);
  const demoted = primary.slice(maxCols);        // rutscht in Detail-Zeile
  const detail  = [...demoted, ...secondary];
  return { inTable, demoted, detail };
}

// SMS-Kanal: Token-Zeile, Priorität = Reihenfolge, Stopp bei 140 Zeichen
const SMS_TOK: Record<string,string> = {
  temp:'N8 D11', precip:'R3.2', rainProb:'PR53%@12',
  wind:'W12@11(24@13)', gust:'G25@12(43@14)', thunder:'TH5%@12',
};
function smsRender(primary, secondary) {
  const order = [...primary, ...secondary];
  const carried=[], noCode=[], overflow=[]; let toks=[];
  const len = t => `KHW03: ${[...t,'Z:WATCH:2447'].join(' ')}`.length;
  for (const id of order) {
    const tok = SMS_TOK[id];
    if (!tok)            { noCode.push(id);  continue; }   // kein SMS-Code
    if (len([...toks,tok]) > 140) { overflow.push(id); continue; } // 140-Limit
    toks.push(tok); carried.push(id);
  }
  return { line:`KHW03: ${[...toks,'Z:WATCH:2447'].join(' ')}`, carried, noCode, overflow };
}
```

## Files

- `ChannelPreviewBlock.svelte` — **ersetzen**: rendert jetzt Schicht 1
  (Konsequenz-Leiste, klickbar) + Schicht 2 (Ein-Kanal-Fidelity), 2-Spalten-Grid
  Desktop / gestapelt Mobile.
- `ChannelPreviewCard.svelte` — **Rolle ändert sich**: war „eine von vier Mini-
  Kacheln", wird jetzt die **Konsequenz-Kachel** in Schicht 1 (Zahl + Status +
  Detail-Count, kein Mini-Render mehr).
- **neu** `ChannelFidelityEmail.svelte` (Desktop-Tabelle + iPhone-Toggle),
  `ChannelFidelityBubble.svelte` (Signal/Telegram), `ChannelFidelitySMS.svelte`
  (Token-Code + Mapping). Aufteilung empfohlen — sonst wird der Block monolithisch.
- Mobile-Pendant (`screen-metrics-editor-mobile` / Wizard-Step-4 mobile): dieselbe
  Komponente, `viewport="mobile"` → Konsequenz-Leiste als 2×2-Grid, Vorschau darunter.

## Constraints

- **C1** Immer nur **ein** Kanal in der Fidelity-Vorschau (kein 4er-Grid mehr).
- **C2** Konsequenz-Kacheln sind **klickbar** und setzen den aktiven Kanal; aktive
  Kachel hat Akzent-Border-Left + weiße Card.
- **C3** Email-Fidelity bietet **Desktop-Mail UND iPhone-Mail** (Umschalter);
  iPhone rendert die Stunden **gestapelt** (wie `EmailHourList`), nicht als
  Breit-Tabelle.
- **C4** SMS-Fidelity rendert **ausschließlich** das Token-Format oben — kein
  „ · "-Fließtext. Plus Mapping „✓ mit Code / ✕ fällt weg" und 140-Zeichen-Zähler.
- **C5** Spalten-Demotion (`demoted`) und SMS-Wegfall werden **benannt** (welche
  Metriken), nicht nur gezählt.
- **C6** Kein Live-Wetter — Beispielwerte sind als solche markiert.
- **C7** Status-Tonalität: `warn` (amber) wenn Metriken rutschen/wegfallen, sonst
  `good` (grün). Keine reine Farb-Codierung — Zahl + Text tragen mit (Lesbarkeit).
- **C8** Renderer-Logik identisch Frontend/Backend (siehe Pseudocode), damit die
  Vorschau exakt dem gesendeten Briefing entspricht.

## Acceptance criteria

- [ ] 4er-Mini-Kachel-Grid ist ersetzt durch Konsequenz-Leiste + Ein-Kanal-Vorschau.
- [ ] Klick auf eine Konsequenz-Kachel wechselt die Fidelity-Vorschau auf diesen Kanal.
- [ ] Email-Vorschau zeigt Desktop-Tabelle; Umschalter blendet iPhone-Mail (gestapelt) ein.
- [ ] Signal/Telegram-Vorschau zeigt Mono-Tabelle, auf `maxCols` gekappt, Rest als Detail-Zeile (fett) in der Bubble; Warn-Notiz nennt die verschobenen Metriken.
- [ ] SMS-Vorschau zeigt das **exakte Token-Format**, einen 140-Zeichen-Zähler und ein Mapping „mit Code / fällt weg" mit Metrik-Namen.
- [ ] Konsequenz-Kachel je Kanal: Spalten-Zahl/Limit (bzw. SMS „X / Total als Code"), Status-Pill, Detail-Count.
- [ ] Mobile (< 900 px): Konsequenz-Leiste als 2×2-Grid, Fidelity-Vorschau darunter, volle Breite.
- [ ] Bestehende `data-testid`s des Vorschau-Blocks erhalten / sinnvoll erweitert.

## Edge cases

| Fall | Verhalten |
|---|---|
| 0 Spalten gewählt | Fidelity zeigt leere Tabelle + Hinweis „keine Spalten konfiguriert" |
| primary ≤ Kanal-Limit | Konsequenz-Pill = „alle als Spalte" (grün), keine Demotion |
| Metrik ohne SMS-Token | SMS-Mapping listet sie unter „fällt weg · kein SMS-Code" |
| SMS-Token-Summe > 140 | überzählige Tokens fallen unter „über 140 Zeichen" weg (Priorität entscheidet) |
| sehr viele Spalten (Email) | Tabelle horizontal scrollbar; iPhone bricht gestapelt um |

## Out of scope (Folge-Issues)

- Pro-Kanal-Overrides (eigene Spalten-Auswahl je Kanal) — bleibt V2 (siehe #14).
- Drag-Reorder direkt in der Vorschau (Reihenfolge wird in den Bucket-Sektionen gesetzt).
- Echte Wetterdaten in der Vorschau (bewusst Beispielwerte).

## 📎 Screenshots

**Soll · Desktop — Signal aktiv (4 Spalten rutschen in die Detail-Zeile)**

![soll-issue496-desktop-signal](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-issue496-desktop-signal.png)

**Soll · Desktop — SMS aktiv (Token-Code + Mapping „mit Code / fällt weg")**

![soll-issue496-desktop-sms](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-issue496-desktop-sms.png)

**Soll · Mobile (< 900 px) — Konsequenz-Leiste als 2×2-Grid, Vorschau darunter**

![soll-issue496-mobile](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-issue496-mobile.png)
