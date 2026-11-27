---
entity_id: feat-3413-kanal-baustein
type: refactor
created: 2026-11-27
status: draft
workflow: feat-3413-kanal-baustein
issue: 3413
---

# Mini-Spec: Restliche Kanal-Flag-Auswertungen auf den gemeinsamen Baustein (#3413)

Folge aus #2990 (Adversary-Finding F002). Zwei Stellen werten die vier Briefing-Kanal-Flags
(`send_email`, `send_telegram`, `send_sms`, `send_premium_sms`) noch selbst aus, statt die
eine Regel aus `frontend/src/lib/components/shared/aktiveKanaele.ts` bzw. der darunterliegenden
Lesefunktion `leseBriefingStartwerte` (`briefingStartwerte.ts`) zu nutzen.

## Was ändert sich

- `hub-uebersicht/hubUebersichtModell.ts` · `tripBriefingKanaele(trip)`: liefert die Kanäle über
  `aktiveKanaele(trip.report_config)`. Schlüsselformat: der Hub-Typ `Kanal` behält `premium_sms`
  (er wird auch für die Alarm-Kanäle aus `alert_channels` genutzt, deren Datenmodell-Schlüssel
  `premium_sms` heißt). Die Übersetzung `premium-sms` → `premium_sms` passiert genau an dieser
  einen Stelle; `aktiveKanaele` selbst und seine übrigen Nutzer bleiben unverändert.
- `zustellung-tab/zustellungModell.ts` · `standAusPreset(preset)`: der Schalter-Zustand
  `briefing.{email,telegram,sms,premium_sms}` kommt aus `leseBriefingStartwerte(preset)`
  (derselben Regel, auf der `aktiveKanaele` aufsetzt), nicht mehr aus eigenen Vergleichen.
  Booleans brauchen keine Liste; die Lesefunktion ist die eine Quelle der Flag-Regel.

## Was darf sich nicht ändern

- Regel unverändert: E-Mail an, solange `send_email !== false`; Telegram/SMS/Premium-SMS nur bei
  genau `true`. Reihenfolge email, telegram, sms, premium_sms.
- Rückgabeformen bleiben: `tripBriefingKanaele` → `Kanal[]` mit `premium_sms`; `standAusPreset`
  → `ZustellungStand` mit identischem `briefing`-Objekt. Alarm-Kanäle (`alarme`), Slots, Zeiten,
  Dringlichkeit, Stille, Cooldown in `standAusPreset` unberührt.
- Keine Änderung an `aktiveKanaele.ts`, `briefingStartwerte.ts`, Typen oder Backend.

## Acceptance Criteria

**AC-1:** Given ein Trip mit `report_config` in jeder Kombination der vier Flags (fehlend, `true`, `false`, Nicht-Boolean wie `"true"`), When `tripBriefingKanaele` aufgerufen wird, Then ist das Ergebnis gleich `aktiveKanaele(report_config)` mit `premium-sms` als `premium_sms`, in fester Reihenfolge.

**AC-2:** Given ein Trip ohne `report_config`, When `tripBriefingKanaele` aufgerufen wird, Then ist das Ergebnis `['email']`.

**AC-3:** Given ein Orts-Vergleichs-Preset in jeder Kombination der vier Flags, When `standAusPreset` aufgerufen wird, Then entspricht `briefing` genau den Kanal-Werten aus `leseBriefingStartwerte(preset)` (E-Mail an außer bei `false`, übrige nur bei `true`).

**AC-4:** Given die beiden Funktionen nach der Änderung, When die Flag-Regel in `leseBriefingStartwerte` verfälscht wird (Mutations-Gegenprobe), Then ändern sich die Ergebnisse beider Funktionen mit — keine der beiden wertet die vier Flags mehr selbst per Vergleich aus.

## Inline-Test (wird während Implementierung geschrieben)

- [ ] node:test `frontend/src/lib/components/shared/issue_3413_kanal_baustein.test.ts`:
  Kombinations-Tabelle der vier Flags gegen feste Erwartungswerte (AC-1, AC-2, AC-3);
  bestehende Tests von Hub-Übersicht und Zustellung-Tab bleiben grün.
