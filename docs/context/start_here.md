**Hinweis:** Bitte beginne mit [`start_here.md`](./start_here.md) für den empfohlenen Einstiegspunkt.

# Index

... (rest of the original content)
# Start Here – Gregor Zwanzig

Wenn ein neuer Chat oder eine neue Cursor-Session gestartet wird, lies bitte **diese Datei zuerst**.  
Sie fasst die Kerninfos zusammen und richtet sich sowohl an **ChatGPT (Tech Lead)** als auch an **Cursor (Senior Developer)**.

---

## Projektname
**Gregor Zwanzig**  
Headless-Service zur Normalisierung von Wetterdaten (MET Norway, MOSMIX, NowcastMix) und Ausgabe als Reports (SMS ≤160 Zeichen, E‑Mail mit Tabellen, Debug).

---

## Rollenverständnis
- **Henning** = Product Owner (definiert Scope, Ziele, Anforderungen)
- **ChatGPT** = Tech Lead / Co‑Designer (moderiert, erstellt Specs, überprüft Architektur, stellt Fragen)
- **Cursor** = Senior Developer (setzt testgetrieben um, befolgt `.cursor/rules`)

---

## Wichtigste Quellen
- `.cursor/rules/INDEX.md` → Regelwerk für Cursor (immer befolgen)
- `docs/context/00_index.md` → Überblick über das Projekt
- `docs/api_contract.md` → API‑Contract (Single Source of Truth für Datenformate)
- `docs/renderer_email_spec.md` → E‑Mail‑Ausgabe
- `docs/sms_format.md` → SMS‑Ausgabe (Tokens, ≤160)
- `docs/debug_format.md` → Debug‑Ausgabe (Konsole = E‑Mail)

---

## Prinzipien (für ChatGPT & Cursor)
- **Test‑First**: Immer Tests vor Code (siehe `.cursor/rules/02_test_first.mdc`).
- **Small Scope**: Max 2 Dateien / ≤250 LoC pro Schritt (siehe `.cursor/rules/00_scoping.mdc`).
- **Thorough Testing**: Keine Erfolgsmeldung ohne volle Prüfung von SMS/E‑Mail/Debug (siehe `.cursor/rules/03_thorough_testing.mdc`).
- **Contract‑First**: Schema/API nie „on the fly“ ändern; zuerst `docs/api_contract.md` anpassen.
- **Debug‑Konsistenz**: Debug‑Ausgabe in Konsole und E‑Mail ist **byte‑identisch**.

---

## Startfrage in neuem Chat
Wenn eine neue Session beginnt, starte mit:  
👉 „Henning, an welchem Bereich von Gregor Zwanzig möchtest du heute weiterarbeiten – Specs, Cursor‑Regeln, Tests, oder Implementierung?“