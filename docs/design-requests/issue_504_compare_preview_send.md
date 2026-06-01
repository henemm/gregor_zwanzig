# Design Request — Briefing-Vorschau + Versandauslösung im Orts-Vergleich

**Priorität:** Medium  
**GitHub Issue:** #514 — Bug: CompareDetail zeigt falschen Platzhalter  
**Bezug:** `/compare/[id]` Detail-Seite + `/compare` Listenansicht  
*(Claude Design hat keinen Zugriff auf GitHub Issues — alle relevanten Infos stehen vollständig in diesem Dokument.)*

---

## Die offene Lücke

Die Detail-Seite eines Orts-Vergleichs (`/compare/[id]`) hat eine Card „Vorschau · Prüfung", die nur einen leeren Platzhalter zeigt. Die Funktion dahinter — eine Vorschau des Briefing-E-Mails anzeigen und den Versand manuell auslösen — ist nie gebaut worden.

Gleichzeitig zeigt das bestehende Design-System-File `screen-compare-list.jsx` genau diese beiden Aktionen als **Icon-Buttons in jeder Zeile der Listenansicht**:

```
[Pause/Play] [Briefing jetzt senden ✈] [Briefing-Vorschau 👁] | [Bearbeiten] [Löschen]
```

Es gibt also eine Design-Entscheidung zu treffen: **Wo sollen diese Aktionen leben?**

---

## Was heute existiert

### Die Listenansicht `/compare`

Zeigt alle Orts-Vergleiche als Kachel-Grid (`CompareGrid`). Jede Kachel zeigt Name, Status, Orte, letzter Versand, Kanäle. Ein Kebab-Menü (⋯) bietet: Bearbeiten, Briefing jetzt senden, Pausieren, Löschen.

**Fehlt:** Briefing-Vorschau als Aktion im Kebab oder als sichtbarer Button.

### Die Detail-Seite `/compare/[id]`

2-Spalten-Desktop-Layout (1.7fr / 1fr):

**Linke Spalte:**
- Card „Verglichene Orte" — Rang + Name + Höhe
- Card „Idealwerte" — Min-Max pro Metrik
- Card „Layout pro Kanal" — Metriken-Zuordnung

**Rechte Spalte:**
- Card „Versand" — Zeitplan, Profil, Empfänger-Adressen
- Card „Vorschau · Prüfung" — **aktuell: leerer Platzhalter**

### Vorhandene Backend-Infrastruktur

| Endpoint | Zweck |
|----------|-------|
| `POST /api/compare/presets/{id}/send` | Briefing sofort versenden |
| `POST /api/_validator/compare-email-preview` | E-Mail-Vorschau generieren (HTML) |

Die Vorschau-Infrastruktur existiert also — sie fehlt nur im UI.

---

## Was ein Orts-Vergleichs-Briefing zeigt

Das Briefing vergleicht mehrere Orte (z.B. Mallorca-Wanderrouten) für denselben Zeitraum. Die E-Mail enthält eine Tabelle mit einer Spalte pro Ort und einer Zeile pro Metrik (Wind, Regen, Temperatur etc.). Der Nutzer will vor dem Versand sehen:

- Sieht die Tabelle vernünftig aus?
- Sind alle gewählten Orte drin?
- Ist die Formatierung wie erwartet?

Das ist vergleichbar mit der „Pro Kanal"-Vorschau beim Trip-Editor (`ChannelPreviewBlock`), aber die Vergleichs-Vorschau zeigt **E-Mail-Format mit mehreren Spalten**, keine Kanal-Auswahl.

---

## Vergleich: Trip-Editor hat eine ähnliche Vorschau

Für Trips (nicht Orts-Vergleiche) gibt es bereits `ChannelPreviewBlock.svelte` im Trip-Editor-Tab „Wetter-Metriken". Dieser Block zeigt eine Briefing-Vorschau mit Beispieldaten, aufgeteilt nach Kanal (E-Mail / Telegram / Signal / SMS) — umgesetzt in Issue #496 als 2-Schicht-Design (Schicht 1: Konsequenz, Schicht 2: Fidelity).

Referenz im Design-System: `screen-compare-email.jsx` enthält das Orts-Vergleichs-E-Mail-Format.

---

## Die Design-Frage

**Wo und wie sollen „Briefing-Vorschau" und „Briefing jetzt senden" im Orts-Vergleich erscheinen?**

### Option A: Nur auf der Detail-Seite

Die Card „Vorschau · Prüfung" auf der rechten Seite der Detail-Seite wird zur echten Vorschau:
- Zeigt eine kompakte E-Mail-Vorschau (ähnlich wie bei Trips: Beispieldaten)
- Darunter ein Button „Briefing jetzt senden" (mit Bestätigungs-Feedback)
- In der Listenansicht bleibt nur „Bearbeiten" und „Löschen" im Kebab; die Versand-Aktionen sind auf der Detail-Seite

**Vorteil:** Alle Informationen + Aktionen an einem Ort. Kein Kontextwechsel.  
**Nachteil:** Nutzer muss die Detail-Seite aufrufen, um schnell ein Briefing auszulösen.

### Option B: Nur in der Listenansicht

Die Kacheln im `/compare` Grid bekommen Aktions-Buttons (wie im ursprünglichen Design geplant):
- „Briefing-Vorschau" öffnet ein Modal/Panel
- „Briefing jetzt senden" ist direkt klickbar mit Bestätigung
- Die Platzhalter-Card auf der Detail-Seite entfällt ersatzlos

**Vorteil:** Schnellzugriff ohne Seitenwechsel. Entspricht dem ursprünglichen Design-Intent aus `screen-compare-list.jsx`.  
**Nachteil:** Kachel-Grid wird aktionsreicher; Modal-Vorschau braucht eigenes Design.

### Option C: Beides — gestuft

- Listenansicht: Nur „Briefing jetzt senden" als Schnellzugriff (kein Preview)
- Detail-Seite: Volle Vorschau + Versand-Button mit Statusanzeige (letzter Versand, nächster Versand)

---

## Entscheidungs-Grundlage

- **Nutzungskontext:** Desktop-Planungstool, Nutzer konfiguriert vor dem Urlaub. Unterwegs liest er nur E-Mail — keine Website.
- **Nutzungsmoment für Versand:** Gelegentlich während Konfiguration (Test), einmalig vor Abreise (echter Versand). Nicht täglich.
- **Nutzungsmoment für Vorschau:** Einmalig nach Einrichtung: „Sieht die Vergleichs-Tabelle vernünftig aus?"
- **Viewport:** Desktop-First; Mobile ist vorhanden aber sekundär für Konfiguration.
- **Design-Leitprinzip:** Lesbarkeit über Optik. Die Vorschau soll zeigen, was der Empfänger wirklich bekommt — nicht dekorativ.

---

## Bestehendes Design-System

Referenz: `docs/design-system/` (CHARTER, COMPONENTS, TOKENS, SCREENS.json)  
Vorschau-Referenz für Trips: `screen-compare-email.jsx` + implementierter `ChannelPreviewBlock` (Issue #496)  
Bestehende Detail-Seite: `frontend/src/lib/components/compare/CompareDetail.svelte`  
Bestehende Listenansicht: `frontend/src/routes/compare/+page.svelte` + `CompareGrid.svelte`

---

## Deliverable

1. **Entscheidung** welcher Ansatz (A / B / C oder ein anderer), mit kurzer Begründung
2. **Mockup(s)** für die gewählte Lösung — Svelte-JSX-Format wie in `docs/design-requests/orts-vergleich/gregor-zwanzig/project/`
3. **Desktop-Variante** ist Pflicht; Mobile wenn sinnvoll
4. Für die Vorschau: zeigen wie die Orts-Vergleichs-Tabelle in der Vorschau-Card dargestellt wird (Platzbedarf, Scroll oder Kompakt?)
