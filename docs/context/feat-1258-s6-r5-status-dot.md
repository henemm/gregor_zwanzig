# Context: feat-1258-s6-r5-status-dot

**Issue:** #1258, Scheibe **S6** — R5 Kanal-Verbindungsstatus (AC-20…22)
**Track:** Standard (Intake-Score 2; Context + Analyse kombiniert)
**Programm-Spec:** `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` (Abschnitt 6, ACs 20–22; PO-Entscheid F2 ehrliche Labels)
**Unabhängig** von S1–S5 (einzige Scheibe ohne Alarme-Tab-Bezug).

## Request Summary

`/api/auth/profile` exponiert ein aus `email_verified_at` abgeleitetes
Boolean (kein Zeitstempel-Leak); `VTBriefingChannels` (geteilter Baustein,
wirkt in Trip- UND Compare-Versand) zeigt je Kanal Status-Dot + ehrliches
Label nach `screen-compare-detail.jsx:289-309`.

## Related Files (verifiziert, Stand 3e38fff7)

| Datei | Relevanz |
|---|---|
| `internal/handler/auth.go` | `profileResponse` :442-450 (mail_to/sms_to/telegram_chat_id/sms_allowed) + `toProfileResponse` :470-491 — neues Feld `email_verified bool` (abgeleitet `EmailVerifiedAt != nil`); Verifikations-Reset bei Adressänderung existiert (:564-576) und bleibt unangetastet |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | lädt Profil bereits (:63-71), `availableChannels` :56-60; Profile-Interface um `email_verified` erweitern; Status-Dot + Mono-Label additiv in die bestehenden Checkbox-Zeilen (Checkboxen + Testids UNVERÄNDERT — Playwright-Suiten erwarten sie, #1232-Kommentar :5-9; Design-Toggle-Pill wird NICHT nachgebaut) |
| `claude-code-handoff/current/jsx/screen-compare-detail.jsx:289-309` | Design-Soll: `Dot tone=good/neutral size=7` + Mono-Label 11px letterSpacing 0.04em |
| `frontend/src/lib/types.ts` | Profil-Typ (falls zentral definiert) um `email_verified` |

## Analysis (Standard Track, inline)

### Entscheidungen

- **R1 Backend:** `profileResponse.EmailVerified bool` (`json:"email_verified"`), abgeleitet in `toProfileResponse` — NIE der Zeitstempel (AC-20). Go-Handler-Test: Feld vorhanden, `email_verified_at` NICHT im JSON.
- **R2 Status-Logik als extrahiertes Logik-Modul** `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts` (node:testbar, S2-Muster): `channelConnectionStatus(profile)` → je Kanal `{tone: 'good'|'neutral', label: string}`:
  - E-Mail: `mail_to && email_verified` → good/„bestätigt"; `mail_to && !email_verified` → neutral/„nicht bestätigt" (**Kanten-Festlegung**, von AC-21 nicht abgedeckt — F2-Geist: ehrlich); kein `mail_to` → neutral/„nicht verbunden"
  - Telegram: `telegram_chat_id` → good/„verbunden"; sonst neutral/„nicht verbunden"
  - SMS: `sms_to && sms_allowed !== false` → good/„hinterlegt"; sonst neutral/„nicht verbunden" (Tier-gesperrt = effektiv nicht nutzbar)
- **R3 Rendering:** Dot (7px, `--g-good`/neutral) + Mono-Label in jede Kanal-Zeile von VTBriefingChannels, beide Kontexte automatisch (ein Baustein, AC-22); Testids `channel-status-email|telegram|sms` (neu, additiv).
- **R4 Kein Datenmodell-/Schema-Delta** (User-Modell hat `email_verified_at` bereits); profileResponse ist additiv.

### Affected Files
| File | Change |
|---|---|
| `internal/handler/auth.go` | MODIFY: EmailVerified-Feld + Ableitung |
| `internal/handler/` Go-Test | CREATE/MODIFY: AC-20-Nachweis (kein Timestamp-Leak) |
| `shared/versand-tab/channelConnectionStatus.ts` | CREATE: Logik-Modul |
| `shared/versand-tab/VTBriefingChannels.svelte` | MODIFY: Dot+Label additiv |
| `shared/__tests__/channel_connection_status.test.ts` | CREATE: AC-21-Matrix |
| `frontend/src/lib/types.ts` | MODIFY (falls Profil-Typ zentral) |

### Scope: ~5 Dateien, ~90-140 LoC · Risk LOW-MEDIUM (Auth-Endpoint nur additiv; geteilter Baustein → beide Flächen)

### Risiken
- **Zeitstempel-Leak** (AC-20) — Go-Test als Negativ-Assertion.
- **Testid-/Checkbox-Bruch:** bestehende Playwright-Suiten erwarten `channel-*`/`compare-step5-channel-*`-Checkboxen — Status nur ADDITIV einfügen.
- Kanten „konfiguriert aber unbestätigt" (E-Mail) per R2 festgelegt — in Spec-Abschnitt 12 dokumentieren, PO sieht es in der Freigabe.
