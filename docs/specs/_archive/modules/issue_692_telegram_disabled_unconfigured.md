---
entity_id: issue_692_telegram_disabled_unconfigured
type: module
created: 2026-06-10
updated: 2026-06-11
status: complete
version: "1.0"
tags: [frontend, ux, channels, weather-metrics-tab]
---

# Issue #692 — Nicht konfigurierte Kanäle in "04 — Kanäle" ausgegraut + Konfigurationslink

## Approval

- [x] Approved & Implemented (2026-06-11)

## Purpose

Im Tab "04 — Kanäle" des Wetter-Metriken-Editors (`WeatherMetricsTab`) kann ein Nutzer
Telegram, SMS oder E-Mail als Briefing-Kanal aktivieren, auch wenn er den jeweiligen Kanal
in seinem Account gar nicht konfiguriert hat. Die Folge: der Briefing-Versand läuft still
ins Leere. Diese Änderung graut nicht konfigurierte Kanal-Karten aus, sperrt den Toggle
und zeigt direkt unterhalb der Karte einen Hinweistext mit Link auf `/account`, damit der
Nutzer die fehlende Konfiguration in einem Schritt nachholen kann.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherV2Kanaele.svelte`
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **Identifier:** `WeatherV2Kanaele` (neues Prop `availability`), `WeatherMetricsTab` (Profil-Load + Prop-Weiterleitung)

> Frontend-only. Go-API und Python-Backend sind nicht betroffen. Das Profil wird bereits
> von `GET /api/auth/profile` geliefert — derselbe Endpunkt, den `EditReportConfigSection`
> nutzt. Kein neues Backend-Feld nötig.

## Estimated Scope

- **LoC:** ~50 (WeatherV2Kanaele ~30, WeatherMetricsTab ~20)
- **Files:** 2 Source (`.svelte`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/auth/profile` | API-Endpunkt | Liefert `mail_to`, `telegram_chat_id`, `sms_to` zur Verfügbarkeitsermittlung |
| `EditReportConfigSection.svelte` | Referenz-Implementierung | Identisches Muster: `profile`-State, `availableChannels`-Derived, disabled-Checkbox + Hint |
| `WeatherMetricsTab.svelte` | Parent-Komponente | Hält den `profile`-State und gibt `availability` als Prop weiter |
| `WeatherV2Kanaele.svelte` | Ziel-Komponente | Erhält `availability`-Prop, rendert disabled-State + Hint |

## Implementation Details

```
1. WeatherMetricsTab.svelte
   a. Neuer State:
      let profile = $state<{ mail_to?: string; telegram_chat_id?: string; sms_to?: string } | null>(null);

   b. Neues Derived:
      let availableChannels = $derived({
          email:    !!profile?.mail_to,
          telegram: !!profile?.telegram_chat_id,
          sms:      !!profile?.sms_to,
      });

      Fail-soft-Regel: profile === null bedeutet "noch nicht geladen" ODER "Fehler".
      In beiden Fällen gilt availableChannels = { email: true, telegram: true, sms: true }
      — alle Kanäle nutzbar, damit ein Lade-Fehler nichts sperrt.

      Konkret: $derived-Ausdruck mit Kurzschluss:
        email:    profile === null || !!profile.mail_to,
        telegram: profile === null || !!profile.telegram_chat_id,
        sms:      profile === null || !!profile.sms_to,

   c. Profil laden (nach vorhandenem load()-Aufruf, parallel):
      onMount(() => {
          fetch('/api/auth/profile', { credentials: 'same-origin' })
              .then((r) => (r.ok ? r.json() : null))
              .then((p) => { profile = p; })
              .catch(() => { /* profile bleibt null → fail-soft → alle verfügbar */ });
      });

      Alternativ in load() parallel zu den bestehenden Promise.all-Aufrufen — dann kein
      separater onMount nötig. Bevorzugte Variante: in load() integrieren, weil WeatherMetricsTab
      bereits einen Promise.all-Block hat und ein separater onMount Timing-Fragen aufwirft.

   d. WeatherV2Kanaele erhält neues Prop:
      availability={availableChannels}

2. WeatherV2Kanaele.svelte
   a. Neues Interface-Feld in Props:
      availability?: { email: boolean; telegram: boolean; sms: boolean };

      Default (wenn nicht übergeben): alle true — abwärtskompatibel.

   b. In der ch-card-Schleife: Toggle-Button disabled wenn !availability[ch.id]:
      <button
          ...
          disabled={!(availability?.[ch.id] ?? true)}
          ...
      >

   c. Unterhalb jeder ch-card: bedingte Hint-Zeile:
      {#if !(availability?.[ch.id] ?? true)}
          <div class="ch-hint" data-testid="channel-{ch.id}-hint">
              {ch.label} nicht konfiguriert —
              <a href="/account">im Account einrichten</a>
          </div>
      {/if}

   d. CSS für .ch-hint (analog zu EditReportConfigSection):
      .ch-hint {
          font-size: 12px;
          color: var(--g-ink-3);
          padding: 0 16px 12px 52px; /* links eingerückt wie kurzform-row */
          line-height: 1.45;
      }
      .ch-hint a {
          color: var(--g-accent);
          text-decoration: underline;
          text-underline-offset: 2px;
      }

   e. Visuelle Unterscheidung gesperrter Karten: .ch-card ohne `.on`-Klasse bleibt
      bereits ausgegraut (var(--g-card-alt), schwächere Textfarbe). Zusätzlich
      opacity: 0.6 auf den button wenn disabled, cursor: default.

3. Bestehende Logik bleibt unverändert:
   - toggle(id) wird nur aufgerufen wenn button nicht disabled ist
   - Kanal-Werte (channels) werden weiterhin vollständig in display_config gespeichert
   - Telegram-Kurzform-Row (#614) ist unberührt
   - createMode / onChannelsChange (#622) ist unberührt
```

## Expected Behavior

- **Input:** `GET /api/auth/profile` liefert Profil mit Feldern `mail_to`, `telegram_chat_id`, `sms_to`
- **Output:** Kanal-Karten für nicht konfigurierte Kanäle sind ausgegraut und nicht klickbar; direkt darunter erscheint ein Hint mit `/account`-Link
- **Side effects:** Kein Backend-Call, keine Schema-Änderung. Profil wird bei Tab-Öffnung einmalig geladen. Bereits gespeicherte `channels`-Werte bleiben erhalten (Persistenz unverändert).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat keine Telegram-Chat-ID konfiguriert / When er den Tab "04 — Kanäle" öffnet / Then ist die Telegram-Karte ausgegraut, der Toggle nicht klickbar, und unterhalb der Karte erscheint der Text "Telegram nicht konfiguriert — im Account einrichten" mit einem anklickbaren Link zu `/account`.
  - Test: Playwright als eingeloggter Nutzer ohne Telegram-Chat-ID — `data-testid="channel-telegram-hint"` ist sichtbar, Toggle-Button hat `disabled`-Attribut.

- **AC-2:** Given ein Nutzer hat Telegram konfiguriert (telegram_chat_id gesetzt) / When er den Tab "04 — Kanäle" öffnet / Then ist die Telegram-Karte voll klickbar, kein Hint-Text sichtbar, Toggle funktioniert wie bisher.
  - Test: Playwright als eingeloggter Nutzer mit telegram_chat_id — `data-testid="channel-telegram-hint"` nicht im DOM, Toggle-Button ohne `disabled`-Attribut, Klick ändert den aktivierten Zustand.

- **AC-3:** Given der Profil-Abruf schlägt fehl (Netzwerkfehler oder HTTP-Fehler) / When der Tab "04 — Kanäle" gerendert wird / Then sind alle drei Kanal-Karten vollständig funktionsfähig (kein Kanal gesperrt, kein Hint), damit kein Nutzer ausgesperrt wird.
  - Test: Playwright mit simuliertem `/api/auth/profile`-Fehler (500 oder Netzwerk-Timeout) — keine `ch-hint`-Elemente im DOM, alle Toggle-Buttons ohne `disabled`.

- **AC-4:** Given ein Nutzer hat weder `mail_to` noch `sms_to` noch `telegram_chat_id` konfiguriert / When er den Tab "04 — Kanäle" öffnet / Then sind alle drei Kanal-Karten gleichzeitig ausgegraut und zeigen je einen Hint-Text — die Anzeige ist konsistent und überlagert sich nicht mit der Telegram-Kurzform-Zeile.
  - Test: Playwright als frischer Nutzer ohne jegliche Kanal-Konfiguration — alle drei `data-testid="channel-{email,telegram,sms}-hint"`-Elemente sichtbar, Telegram-Kurzform-Row nicht sichtbar (da Telegram-Toggle disabled und nicht aktiviert).

- **AC-5:** Given ein Nutzer hat eine oder mehrere Kanäle konfiguriert und bereits gespeichert / When er den Tab erneut öffnet / Then sind die gespeicherten `channels`-Werte unverändert geladen (Persistenz-Roundtrip intakt), und nur die fehlenden Kanäle sind ausgegraut.
  - Test: Playwright — Trip mit gespeichertem `channels={email:true, telegram:false, sms:false}` laden, Profil nur mit `mail_to` gesetzt; nur E-Mail-Karte aktiv und nicht ausgegraut, Telegram + SMS ausgegraut, gespeicherter `channels.email=true` bleibt nach erneutem Öffnen erhalten.

## Known Limitations

- Nicht konfigurierte Kanäle können weiterhin im gespeicherten `channels`-Objekt auf `true` stehen (Altdaten). Die Darstellung zeigt sie korrekt als gesperrt an, der gespeicherte Wert bleibt bis zur nächsten Nutzer-Interaktion unverändert — keine stille Mutation beim Laden.
- Der Profil-Fetch läuft parallel zum bestehenden Katalog-Fetch; bei sehr langsamer Verbindung kann die Kanal-Verfügbarkeit kurz nach dem Tab-Öffnen noch nicht sichtbar sein (kurzes Flackern). Kein Spinner vorgesehen.

## Changelog

- 2026-06-10: Initial spec created
- 2026-06-11: Implementation complete
  - `WeatherV2Kanaele.svelte`: Prop `availability` empfangen, disabled-State bei nicht konfigurierten Kanälen, Hint-Zeilen mit `/account`-Link
  - `WeatherMetricsTab.svelte`: `profile`-State, Profil-Fetch in `load()` parallel integriert, fail-soft bei Fehler, `availableChannels` derived
