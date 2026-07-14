<!-- gregor-zwanzig-handoff: stable_id=compare-ui-fragen-1256 -->

# Ortsvergleich · UI-Fragen (Issue #1256) — PO-Entscheide

**Status:** Alle 8 Punkte mit dem PO (Henning) am 2026-07-14 durchgesprochen und
entschieden. Keine offenen Rückfragen. Dies ist das **verbindliche Übergabe-
dokument** — bei Widerspruch zu älteren Bodies gilt dieses.

**Kontext-Grundgesetz (unverändert gültig):** Der Ortsvergleich ist ein
**stehender Monitor**, Briefing strikt **neutral** (kein Score, kein Rang, keine
Empfehlung). Grundsatz **Trip = Vergleich** auf gemeinsamen Organismen.
Kanäle: **Email · Telegram · SMS** (Signal ist raus seit 2026-06-05).

---

## 1 · Soll-Bilder Liste + Detail-Hub neu rendern — JA

Die vorhandenen Soll-Bilder zeigen **verworfenes Ranking/Signal** und setzen den
Empfänger auf die falsche Fährte. Neu rendern aus den kanonischen V2-Screens
(`screen-compare-list.jsx`, `screen-compare-detail.jsx`), **ohne** jede Rang-/
Score-Darstellung. Alte Soll-Bilder ersetzen, nicht ergänzen.

- Screenshot-URL-Konvention: `.../main/.github/issue-assets/<slug>.png`
- Betroffen: `soll-compare-list.png`, `soll-compare-detail-hub.png`

## 2 · `screen-compare-email.jsx` (V1) ersetzen — JA

V1 ist **DEPRECATED** und trägt noch Score/Rang. Kanonisch ist
`screen-compare-email-v2.jsx`.

- Alle Referenzen/Imports auf **V2** ziehen.
- V1 danach **löschen** (kein Ranking-Renderer im Repo belassen).
- Vor dem Löschen prüfen, ob V1 noch irgendwo importiert wird; falls ja, zuerst
  umhängen.

## 3 · Mobile-Liste: Suchfeld — LÜCKE, ganz entfernen

Das Suchfeld war funktionslos. Bei der erwarteten Zahl stehender Orts-Monitore
gibt es keinen Suchbedarf. **Suchfeld ersatzlos entfernen** (nicht verdrahten) —
ein leeres Suchfeld suggeriert eine Funktion, die das Produkt nicht braucht.

- Datei: `screen-compare-list-mobile.jsx`

## 4 · Mobile-Detail: 5. Status-Kachel ergänzen — LÜCKE, angleichen

Mobile muss dieselbe Statuslage wie Desktop spiegeln (Konsistenz-Prinzip).
Fehlende **5. Kachel „Briefing-Zeiten"** ergänzen, sodass Mobile = Desktop
(`screen-compare-detail.jsx` → `screen-compare-detail-mobile.jsx`).

## 5 · Alarme = eigener Tab im Ortsvergleich (analog Trip) — REVIDIERT

**Wichtige Korrektur gegenüber älteren Bodies und CLAUDE.md:** Der frühere
Beschluss „notify-Block in den Versand-Tab zusammenlegen" ist **verworfen**.

Begründung des PO: Alerts sind ein **eigenständiges, größeres Thema** — nicht nur
Metrik-Überschreitung/-Veränderung, sondern auch **amtliche Warnungen**, die
an- und abgemeldet werden können. Damit ist der Alarme-Bereich **nicht** halbleer;
die einzige Prämisse der Zusammenlegung fällt weg. Grundsatz **Trip = Vergleich**
zieht dann in die andere Richtung: Trip hat einen eigenen Alarme-Tab → der
Ortsvergleich bekommt ihn ebenfalls.

**Beschluss:**
- **Eigener Alarme-Tab im Ortsvergleich**, analog Trip. Nicht in Versand mischen.
- **Versand-Tab** trägt dann **nur das geplante Briefing** (Kanäle + Uhrzeiten;
  Morgen = heute, Abend = morgen).
- **Alarme-Tab** trägt:
  - Korridor-/Wertebereich-Auslöser (`notify`-Wirkung)
  - **amtliche Warnungen (an/ab)** — siehe Datenmodell unten
  - `AlertChannelPicker` (Default Telegram/SMS an, E-Mail aus)
  - Cooldown
  - Stille Stunden
  - Radar-Schalter
  - Beispiel-Warnung
- **Tab-Reihenfolge Vergleich = Orte/Metriken → Wertebereiche → Alarme → Versand**
  (analog Trip: Inhalt → Auslöser → Zustellung).

**Datenmodell amtliche Warnungen (PO-Entscheid, Tech-Lead-Festlegung):**
Amtliche Warnungen sind **neu für beide** (Trip UND Vergleich). Als **ein**
gemeinsames Abo-Feld auf der `BriefingSubscription`/Briefing-Abo-Entität
modellieren und in **beiden** Alarme-Tabs gespiegelt rendern (gemeinsamer
Organism, kein Copy-Paste).

```
officialWarnings: {
  enabled: boolean,          // an/ab
  sources?: string[]         // z.B. ["dwd"] — Quelle(n), erweiterbar
}
```
Migration Bestand: `officialWarnings = { enabled: false }` (kein Verhaltens-
wechsel für existierende Abos).

## 6 · Keine Top-3 / „Bester-Wert"-Hervorhebung — BESTÄTIGT

Der Vergleich ist neutral. **Keine** Rangfolge, **keine** „Bester-Wert"-/Top-3-
Markierung. Einzige Hervorhebung: **grüne Idealbereich-Markierung** (Wert im
Korridor). `corridorInside()` bleibt die Single-Source dafür.

## 7 · `nav-map.jsx` bereinigen — JA

Der **Wizard-Edit-Modus ist verworfen**. `nav-map.jsx` darf ihn nicht mehr
behaupten. Auf die vier echten Editor-Eintrittspunkte korrigieren (Trip Desktop/
Mobile, Vergleich Desktop/Mobile). Neuen Alarme-Tab-Knoten im Vergleich-Editor
aufnehmen.

## 8 · `SOLL-COVERAGE.md` nachziehen — JA

Muss die geteilten Editor-Screens kennen: `layout-tab.jsx`, `versand-tab.jsx`,
`corridor-editor.jsx` (+ Mobile-Pendants) sowie die `soll-29-*`-Screens und die
neu gerenderten `soll-compare-*`-Bilder aus Punkt 1. Fehlende Einträge ergänzen.

---

## Acceptance Criteria (Checkliste)

- [ ] Soll-Bilder Liste + Detail-Hub zeigen kein Ranking/Signal mehr
- [ ] `screen-compare-email.jsx` (V1) gelöscht, alles auf V2
- [ ] Mobile-Liste ohne Suchfeld
- [ ] Mobile-Detail hat 5 Status-Kacheln (inkl. Briefing-Zeiten) = Desktop
- [ ] Ortsvergleich-Editor hat eigenen **Alarme-Tab** (Reihenfolge Orte →
      Wertebereiche → Alarme → Versand)
- [ ] Versand-Tab trägt nur noch das geplante Briefing
- [ ] Amtliche Warnungen als Abo-Feld, in Trip + Vergleich gespiegelt
- [ ] Vergleich-Briefing zeigt nur grüne Idealmarkierung, keine Rangfolge
- [ ] `nav-map.jsx` ohne Wizard-Edit-Modus, mit Alarme-Tab-Knoten
- [ ] `SOLL-COVERAGE.md` kennt Editor-/Korridor-Screens

## Out of Scope (Folge-Issues)

- Mobile-Editor-Shell-Konsolidierung über die geteilten Organismen hinaus
- API-Konsolidierung `BriefingSubscription` (Phase 2–3, Epic #29)
