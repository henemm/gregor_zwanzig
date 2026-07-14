# Context: fix-1256-s8b-preview-channel-switch — R1 der #1256-Rest-Inventur

## Request Summary

Bugfix-Scheibe S8b aus der Rest-Inventur (#1256, Kommentar 2026-07-14, PO-Entscheid
„Plan komplett abarbeiten"): Der Kanal-Umschalter im Hub-Vorschau-Tab ist funktional
tot, zeigt zudem hart nur Email/SMS und es fehlt der „Kanal nicht konfiguriert"-Hinweis.

## Befund (Audit audit-s8-hub, verifiziert)

| # | Befund | Ist | Soll |
|---|---|---|---|
| 1 | **Umschalter-Klick ist No-Op** | `CompareTabs.svelte:943` übergibt `onchange` (klein); `CompareChannelSwitch.svelte:15` erwartet `onChange` — Svelte 5 Props sind case-sensitiv, der Handler kommt nie an | Klick auf Kanal wechselt die Vorschau (`screen-compare-detail.jsx:351`) |
| 2 | Kanäle hart kodiert | `CompareTabs.svelte:944`: `['email','sms']` — Telegram fehlt immer | `channels={sub.channels}` — konfigurierte Kanäle des Presets (JSX:351) |
| 3 | Fehlender Hinweis | kein „Kanal nicht konfiguriert"-Zustand | JSX:365-369 / CDM:235-237: Hinweis, wenn gewählter Kanal nicht konfiguriert |

Historie: Programm-Spec Z. 352-353 behauptete „Vorschau-Tab … bereits 1:1 vorhanden"
— stale Annahme (dritter Fall dieser Klasse nach AC-21/Layout-Tab); AC-19 deckte nur
den E-Mail-View-Toggle ab. Deshalb eigene Spec für S8b.

## Related Files

| File | Relevance |
|---|---|
| `frontend/src/lib/components/compare/CompareTabs.svelte:940-991` | Vorschau-Tab: Umschalter-Einbindung (Bug 1+2), Render-Fläche, previewChannel-State (`:456`) |
| `frontend/src/lib/components/compare/CompareChannelSwitch.svelte` | Empfängt `onChange`, `channels`, `active` — Komponente selbst korrekt |
| `frontend/src/lib/components/compare/compareEditorLogic.ts` o.ä. | Kanal-Ableitung aus Preset (`empfaenger`/`send_telegram`-Felder — bei Implementierung die echte Quelle prüfen, Muster `channelNamesLabel`) |

## Risks & Considerations

- Kanal-Quelle: konfigurierte Kanäle liegen im Preset (Muster `channelNamesLabel`,
  S3 AC-6) — dieselbe Ableitung nutzen, keine neue Logik (Teilungs-/Konsistenz-Gebot).
- Vorschau-Endpoint für Telegram: prüfen, ob `/api/preview/...`-Pfad je Kanal existiert
  (SMS-Vorschau existiert; Telegram-Vorschau ggf. via bestehendem Renderer) — falls
  Telegram-Vorschau backend-seitig fehlt, Hinweis-Zustand (Befund 3) als Fallback.
- Keine neuen PUT-Pfade; reine Anzeige-Logik. hubPutQueue unberührt.
- Playwright-Wächter gegen Staging nötig (Klick wechselt Kanal sichtbar) — die
  No-Op-Klasse (Handler-Prop-Namen) ist mit Source-Tests allein nicht sicher fangbar.
