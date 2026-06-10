# Spec #690 — Eigene Wetter-Metriken-Profile: aktivieren, kennzeichnen, eindeutig benennen

- **Status:** implemented
- **Created:** 2026-06-10
- **Implemented:** 2026-06-10
- **Workflow:** `bug-690-custom-metrics-persist`
- **Issue:** #690
- **Scope:** Full-Stack (Frontend + kleiner Backend-Anteil), keine Schema-Migration

## Kontext

Das bestehende „eigenes Profil speichern"-Feature (`SavePresetDialog`) persistiert Profile mandantengetrennt im Backend, löst aber drei sichtbare Nutzerversprechen nicht ein und erlaubt doppelte Namen. Diese Spec schließt die vier Lücken aus `docs/context/bug-690-custom-metrics-persist.md`.

## Verhalten (Soll)

1. Nach „Preset speichern" wird das neue Profil **sofort aktiv** — es ist mit dem aktuellen Trip verknüpft (`display_config.preset_name`) und in der Leiste als aktiv markiert.
2. Eigene Profile sind in der Preset-Leiste durch eine **„Eigene"-Pille/Markierung** von System-Vorlagen unterscheidbar.
3. Eigene Profile sind **trip-übergreifend** sichtbar und anwendbar (pro Nutzer) — folgt aus (1) + bestehendem `GET /api/metric-presets`.
4. Der **Name muss eindeutig** sein (pro Nutzer, case-insensitive, getrimmt). Dublette wird im Dialog (vorab) und im Backend (Schutzwall) abgelehnt.

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer im Trip-Editor mit einer geänderten Metrik-Auswahl, When er die Auswahl über den Dialog „als eigenes Profil speichern" mit einem neuen Namen speichert, Then ist das neu erstellte Profil unmittelbar das aktive Profil des Trips (in der Preset-Leiste als `active` markiert) und `display_config.preset_name` des Trips trägt die ID des neuen Profils — ohne dass der Nutzer das Profil manuell anklicken muss.

**AC-2:** Given ein Nutzer mit mindestens einem eigenen Profil und mindestens einer System-Vorlage in der Preset-Leiste, When die Leiste gerendert wird, Then ist jedes eigene Profil visuell als „Eigene" gekennzeichnet (eigene Markierung/Pille), die bei System-Vorlagen nicht erscheint.

**AC-3:** Given ein Nutzer, der auf Trip A ein eigenes Profil „Bergtour" gespeichert hat, When er einen anderen Trip B desselben Nutzers im Editor öffnet, Then erscheint „Bergtour" in der Preset-Leiste von Trip B als auswählbares eigenes Profil (mit „Eigene"-Markierung), und ein Klick wendet es auf Trip B an.

**AC-4:** Given ein Nutzer, der bereits ein eigenes Profil mit Namen „Bergtour" besitzt, When er im Dialog ein weiteres Profil mit demselben Namen (auch mit abweichender Groß-/Kleinschreibung oder umgebenden Leerzeichen, z. B. „ bergtour ") zu speichern versucht, Then wird das Speichern abgelehnt, der Dialog zeigt eine verständliche Fehlermeldung, und es wird kein zweites Profil mit diesem Namen angelegt.

**AC-5:** Given ein direkter `POST /api/metric-presets`-Aufruf mit einem für diesen Nutzer bereits vergebenen Namen (case-insensitive, getrimmt), When der Backend-Handler ihn verarbeitet, Then antwortet er mit HTTP 409 und Body `{"error":"name_exists"}` und speichert kein Duplikat; ein leerer Name antwortet weiterhin mit 400 `{"error":"name_required"}`.

**AC-6:** Given zwei verschiedene Nutzer U1 und U2, When beide je ein eigenes Profil mit demselben Namen „Bergtour" anlegen, Then gelingt das für beide (HTTP 201) — die Eindeutigkeit gilt strikt pro Nutzer, und U1 sieht ausschließlich seine eigenen Profile (keine Vermischung, kein `default`-Fallback im authentifizierten Pfad).

## Nicht-Ziele

- Keine Änderung am gespeicherten Schema von `metric_presets.json` (kein neues Persistenz-Feld nötig; „Eigene" wird im Frontend aus der `userPresets`-Quelle abgeleitet, nicht aus einem Flag).
- Kein Umbenennen/Editieren bestehender Profile (nur Anlegen).
- Keine Mobile-spezifische Sonderarbeit über die bestehende Responsivität des Dialogs hinaus.

## Testnachweis (mock-frei)

- **AC-5/AC-6:** Go-Handler-Test gegen echten Store (zwei reale `user_id`), Duplikat→409, Cross-User→201, Isolation geprüft.
- **AC-1/AC-2/AC-3/AC-4:** Playwright-E2E gegen Staging als eingeloggter Nutzer — Profil speichern → aktiv; Pille sichtbar; anderer Trip zeigt Profil; Dublettenname → Fehlermeldung, kein zweites Profil.

## Changelog

- 2026-06-10: Erstfassung (draft); später implementiert (Backend: uniqueness check HTTP 409/400 im CreateMetricPresetHandler, Frontend: sofortige Aktivierung + Persistenz + "Eigene"-Markierung; API-Dokumentation in docs/reference/api_contract.md Sektion 15.5 hinzugefügt).
