# ADR-0012: Telegram-Formatierung — parse_mode=HTML statt Markdown/MarkdownV2

- **Status:** Akzeptiert
- **Datum:** 2026-07-02
- **Bezug:** GitHub-Issue #952, `docs/specs/_archive/modules/issue_952_onset_alert_fidelity.md`, ADR-0011 (ein Backend-Renderer)

## Kontext

Die kanonischen Alert-Renderer erzeugten Telegram-Texte mit `**fett**`-Markdown,
`TelegramOutput.send()` sendete aber ohne `parse_mode` — die Sternchen erschienen
wörtlich beim Empfänger, zusätzlich wurde der Betreff als `[…]`-Zeile dupliziert
(Issue #952, IST-Screenshots). Für echtes Fett braucht die Bot-API einen
`parse_mode`. Zur Wahl standen `Markdown` (legacy), `MarkdownV2` und `HTML`.

Randbedingung: Die Nachrichten enthalten **Nutzdaten** (Trip-Namen, Orts-Labels,
Intensitäts-Texte), die beliebige Sonderzeichen tragen können.

## Entscheidung

1. **`parse_mode="HTML"`** ist der Standard für formatierte Telegram-Nachrichten
   in Gregor Zwanzig. Renderer erzeugen `<b>…</b>`-Tags; Nutzdaten laufen durch
   dieselbe `_esc()`-Maskierung (`&`, `<`, `>`) wie im E-Mail-HTML — eine einzige
   Escaping-Stelle für beide Kanäle.
2. `TelegramOutput.send()` bleibt **rückwärtskompatibel**: `parse_mode=None` und
   `suppress_subject_line=False` als Defaults reproduzieren das Alt-Verhalten
   bit-identisch; Bestands-Caller (Briefings, Bot-Antworten) bleiben unberührt,
   bis sie explizit umgestellt werden.

## Verworfene Alternativen

- **MarkdownV2** — verworfen: 18 escape-pflichtige Zeichen (`.`, `-`, `(`, `)`,
  `!`, …); jedes unmaskierte Zeichen in einem Trip-Namen führt zu einem
  400-Fehler der Bot-API. Fehleranfällig und ein zweites, telegram-spezifisches
  Escaping-Regelwerk neben dem HTML-Escaping.
- **Markdown (legacy)** — verworfen: von Telegram als überholt geführt, kein
  definiertes Escaping, gleiche Kollisionsklasse wie MarkdownV2.
- **Weiter ohne parse_mode** — verworfen: kein Fett möglich, `**`-Literale sind
  genau der gemeldete Defekt.

## Konsequenzen

- Neue formatierte Telegram-Ausgaben nutzen HTML-Tags + `_esc()`; kein `**` mehr
  in Renderer-Ausgaben der kanonischen Alert-Pfade.
- Offene Härtung: Die 4096-Zeichen-Truncation in `TelegramOutput.send()` kann
  HTML-Tags mittig abschneiden (theoretisch, Issue #976) — bei Umstellung weiterer
  Caller mit langen Texten (Briefings) vorher lösen.
- **Nachgezogen (Issue #1252, 2026-07-13):** Die Official-Alert-Pfade waren zwei
  Lücken in dieser Entscheidung geblieben — `notification_service.py:538` (Standalone-
  Alert) und `:658` (Compare-Alert) setzten `parse_mode` nie, obwohl sie formatierte
  Nachrichten senden; zusätzlich escapte `official_alerts.py` nur die Kopfzeile, nicht
  Ortsnamen/Behörden-Label/Gültigkeit. Beides jetzt behoben. Zusätzlich besitzt
  `TelegramOutput.send()` jetzt einen **400-Fallback**: Lehnt die Bot-API eine
  Nachricht mit gesetztem `parse_mode` ab (Status 400, z.B. durch ein unescaptes
  Sonderzeichen im Upstream-Feed), wird sie einmal ohne `parse_mode` nachgesendet
  (Tags gestrippt, `html.unescape()`), statt komplett zu verschwinden. Der Default
  `parse_mode=None` (Punkt 2) bleibt dabei unverändert — der Fallback greift nur,
  wenn der Aufrufer bereits `parse_mode` gesetzt hatte.
