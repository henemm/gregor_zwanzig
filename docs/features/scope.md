# Gregor Zwanzig – Scope & Vision

> Stand: 2026-07-21 (Doku-Audit #1341). Ersetzt die MVP-/CLI-Ära-Fassung
> (Git-Historie). Offene Arbeit steht ausschließlich in GitHub Issues.

## Produkt

Wetter-Risiko-Briefings für Weitwanderungen und Orts-Vergleiche — als
Multi-User-Webprodukt (SvelteKit-Frontend) mit automatischem Versand über
E-Mail, Telegram und SMS (seven.io). Signal wurde entfernt (#610).

## Nutzer & Kontext

- Mehrtägige Treks (z. B. GR20): eingeschränkte Konnektivität, kurze Kanäle,
  Entscheidung unter Zeitdruck.
- Orts-Vergleich: Vor-Ort-Urlauber, die täglich den besten Ort für den
  Tagesausflug wählen.
- Es gibt derzeit keine aktiven Produktiv-User außer dem PO — Datenmigrationen
  bleiben trotzdem Pflicht (Bestandsdaten erhalten).

## Kern-Erkenntnis (unverändert gültig)

Gregor Zwanzig differenziert sich nicht durch MEHR Daten, sondern durch **die
richtige Information im richtigen Moment über den richtigen Kanal**: kompakt
(30 Sekunden reichen), asynchron (Reports kommen zum User), Low-Connectivity-
tauglich, unterwegs steuerbar (Inbound-Kommandos), kontextbezogen (Profil).

## Was das Produkt heute leistet

- **Trip-Briefings:** Abend-/Morgen-Briefings pro Etappe (E-Mail full/compact,
  Telegram-Bubbles, SMS ≤160 Zeichen), Zeitpläne pro Nutzer.
- **Orts-Vergleich:** Vergleichsmatrix über ≥2 Orte mit Idealbereichen,
  Winner-Logik, eigenem Mail-Template, Zeitplan-Versand.
- **Alerts als Abweichungs-Wächter:** Nowcast/aktueller Forecast vs. letztes
  Briefing (Deviation-Engine), Radar-Nowcast, amtliche Warnungen (FR/AT/IT) —
  für Trips und Orts-Vergleiche.
- **Steuerung unterwegs:** Inbound-Kommandos per E-Mail/Telegram (Umplanung,
  Zoom), Webhook-basierter Telegram-Bot.
- **Planungs-Frontend:** Trip-/Compare-Verwaltung, progressive Anlege-Editoren,
  Vorschau aller Kanäle. Das Frontend ist Planungswerkzeug — KEIN
  Live-Wetter-Portal.

## Nicht-Ziele (weiterhin gültig)

- Keine eigene meteorologische Modellierung (Provider: Open-Meteo + Fallbacks,
  siehe `docs/reference/decision_matrix.md`).
- Keine paternalistischen Empfehlungen (Go/No-Go) — der User entscheidet.
- Kein Trip-Sharing, kein Wetter-Tagebuch, kein Live-Wetter-Dashboard.

## Qualitätskriterien

- TDD mit Zwei-Schichten-Testpolitik (Kern deterministisch, Live-E2E gegen
  Staging), kleine Commits, Staging-Verifikation vor Prod-Deploy, klarer
  Rollback-Pfad. Details: CLAUDE.md + `docs/reference/operations_playbook.md`.
