// TDD RED — Issue #2913 (Epic #2791): Generator-Lauf gegen das echte Mockup (file://, kein Server).
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md — AC-9, AC-10.
//
//   cd frontend && npx playwright test --config playwright.elementliste.mockup.config.ts
//
// Zwei Generator-Läufe liefern dieselben IDs (stabil) und dieselbe Liste wie die eingecheckte
// elementliste.json (sonst ist das Artefakt veraltet oder nicht deterministisch).
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { erzeugeElementliste } from '../../scripts/elementliste_aus_mockup.ts';

const REPO = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const MOCKUP = join(REPO, 'docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html');
const MESSAGES = join(REPO, 'frontend/src/lib/i18n/messages');
const LISTE = join(REPO, 'docs/context/einstellungen_neu/elementliste.json');

test.setTimeout(300_000);

test('zwei Generator-Läufe: identische IDs und identisch mit der eingecheckten Liste', async () => {
	const a = await erzeugeElementliste({ mockupPfad: MOCKUP, messagesDir: MESSAGES });
	const b = await erzeugeElementliste({ mockupPfad: MOCKUP, messagesDir: MESSAGES });
	const ids = (l: { elemente: Array<{ id: string }> }) => l.elemente.map((e) => e.id);
	expect(ids(a).length).toBeGreaterThan(100);
	expect(ids(b)).toEqual(ids(a));
	expect(JSON.stringify(b)).toEqual(JSON.stringify(a));

	const eingecheckt = JSON.parse(readFileSync(LISTE, 'utf8'));
	expect(eingecheckt.mockup_hash).toEqual(a.mockup_hash);
	expect(eingecheckt.elemente).toEqual(a.elemente);
});

test('Generator steuert Script-Zustände: Bearbeiten offen, Vorlagen-Auswahl, Speichern-Dialog, Kebab-Bestätigung', async () => {
	const l = await erzeugeElementliste({ mockupPfad: MOCKUP, messagesDir: MESSAGES });
	const rollen = new Set(l.elemente.map((e: { rolle: string }) => e.rolle));
	expect(rollen.size).toBeGreaterThan(3);
	// Texte, die das Mockup nur in Script-Zuständen rendert, müssen in der Liste auftauchen.
	const texte = l.elemente.map((e: { text_de: string }) => e.text_de).join('\n');
	expect(texte).toContain('Erneut laden'); // Ladefehler-Zustand
	expect(texte).toMatch(/Kurzstil/); // Kanal-Segment Telegram (channelTab)
	expect(texte).toMatch(/Stundenverlauf im Briefing/); // Orte-Segment Stundenverlauf
});
