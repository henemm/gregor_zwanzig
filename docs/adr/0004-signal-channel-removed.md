# ADR-0004: Signal als Briefing-Kanal entfernt

- **Status:** Akzeptiert
- **Datum:** 2026-06-06
- **Bezug:** GitHub-Issue #610

## Kontext

Gregor Zwanzig verschickt Briefings über mehrere Kanäle. Signal war zeitweise als Kanal
vorgesehen/implementiert (über die Callmebot-Infrastruktur). Die Pflege als vollwertiger
Briefing-Kanal — inklusive Frontend-Auswahl, Backend-Output und Vorschau-Endpoint — verursachte
laufenden Aufwand ohne ausreichenden Nutzen für die Zielgruppe.

## Entscheidung

**Signal wird app-weit als Kanal entfernt** (PO-Entscheidung). Die unterstützten Kanäle sind nur
noch **E-Mail · Telegram · SMS**. Konkret bereinigt:

- **Frontend** (Wizard Schritt 1/2): keine Signal-Auswahl mehr.
- **Backend** (Schritt 2/2): kein `SignalOutput`, kein `signal_text`/`send_signal`, kein
  `/api/preview/{trip}/signal`.

Die Callmebot-Infrastruktur auf Server-Ebene (`henemm-infra/.env`, `notify-signal.sh`) bleibt
bestehen und wird von **anderen** Diensten genutzt — aber nicht mehr von Gregor Zwanzig.

## Verworfene Alternativen

- **Signal als Kanal behalten** — verworfen: dauerhafter Wartungsaufwand (zusätzlicher Formatter,
  Output-Pfad, Frontend-Option) bei geringem Mehrwert gegenüber Telegram/E-Mail/SMS.

## Konsequenzen

- **Positiv:** Weniger Code-Pfade, weniger Wartung, klareres Kanal-Modell (E-Mail · Telegram · SMS).
- **Negativ / Preis:** Eine etwaige Wiedereinführung von Signal müsste **neu spezifiziert** werden.
- **Folgepflichten:** Neue Features dürfen Signal nicht als Briefing-Kanal annehmen. Eine
  Reaktivierung erfordert ein neues ADR (das dieses hier ablöst).
