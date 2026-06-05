# Context: bug-486-trips-overflow-regression

## Request Summary
Die Desktop-Trips-Liste ist auf ein **6-Icon-Geschwader** pro Zeile zurückgefallen
(Regression, PO Henning 2026-06-05). Soll: ganze Zeile klickbar → Trip-Detail,
Aktionen in **einem `⋯`-Overflow-Menü**, aktiver Trip zusätzlich inline
„Briefing senden". Kanonische Quelle: korrigierte `screen-trips.jsx` (Commit 56f2c761).

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/src/routes/trips/+page.svelte` | Enthält die regressed Desktop-Grid-Tabelle (Z. 371–439) mit 6 Icon-Buttons/Zeile |
| `claude-code-handoff/handoff-2026-06-04-v3/claude-code-handoff/current/jsx/screen-trips.jsx` | Korrigierte 1:1-Vorlage (TripRow + TripsActionsMenu + tripsIcon) |
| `claude-code-handoff/.../current/soll/E-trips-list-variant.png` | Bindendes SOLL-Bild |
| `.github/issue-assets/soll-trips-list-reduced.png` | Issue-Asset für #486 |

## Existing Patterns
- **Mobile-Pfad ist bereits korrekt:** `+page.svelte` Z. ~340–369 rendert pro Karte
  einen `EllipsisVerticalIcon`-Button (`data-testid="trip-card-menu-btn"`) → öffnet
  `TripActionsSheet` (Z. ~493–539: Briefing senden, Alerts justieren, Wetter-Konfig,
  Bearbeiten, Pausieren, Test-Reports, Löschen). Ganze Karte klickbar.
- Der Desktop-Fix spiegelt dieses Muster: EIN `⋯`-Menü statt Icon-Reihe.
- Vorhandene Handler wiederverwenden: `runTestReport`, `openReportConfig`,
  `openEdit`, `goto(.../preview)`, `deleteTarget`.

## Ziel-Design (aus korrigierter JSX)
- Zeile: `role="button"`, ganze Zeile klickbar → Trip-Detail/Setup öffnen.
- Spalte „Aktionen" (rechtsbündig): wenn `status==='aktiv'` → Ghost-Btn
  „Briefing senden" (play-Icon); danach `⋯`-Button (3 Punkte) + Chevron-Indikator.
- `⋯`-Menü-Items: Briefing jetzt senden · Email-Vorschau · Alert-Konfiguration ·
  Wetter-Metriken · Bearbeiten · — · Löschen (danger).
- Klicks in der Aktions-Zelle dürfen NICHT die Zeilen-Navigation auslösen
  (`stopPropagation`).

## Dependencies
- Upstream: vorhandene `Card`, `ConfirmDialog`, Lucide-Icons, Status-Helper
  `tripStatus`, `dateRange`, Handler in `+page.svelte`.
- Downstream: Playwright-E2E (`data-testid` `trip-edit-btn`, `trip-card-menu-btn`).

## Existing Specs
- Issue #580 (`issue-580-trips-1to1`, Complete) baute die Liste 1:1 — gegen die
  ALTE JSX mit Icon-Soup, Diff PASS 8.73%. Jetzt gegen korrigierte JSX neu.

## Risks & Considerations
- **Keine Datenmodell-Änderung** — reines UI/Markup.
- Bestehende `data-testid`s erhalten (E2E-Selektoren). Evtl. neue Testids für
  Menü-Items dokumentiert ergänzen.
- Mobile-Pfad NICHT anfassen (ist korrekt).
- Design-Fidelity-Gate (#603): Pixel-Diff gegen `E-trips-list-variant.png` muss PASS.
