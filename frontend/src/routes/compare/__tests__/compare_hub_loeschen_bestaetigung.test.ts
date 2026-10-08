// Issue #2214: Compare-Hub loescht den Ortsvergleich ohne Rueckfrage.
//
// Spec: docs/specs/modules/bug_2214_compare_hub_delete_confirm.md (AC-1..AC-4)
//
// PRUEFSTAND-GRENZE: In dieser Frontend-Umgebung gibt es weder vitest noch ein
// DOM (kein jsdom/happy-dom, s. alarme_vergleich_speichert_selbst.test.ts:12);
// `svelte/server` fuehrt keine Klicks aus. Ein Klick-Komponententest ist hier
// daher nicht moeglich. Stattdessen fuehrt dieser Test das ECHTE, aus der
// Seitenquelle herausgeschnittene Skript-Verhalten aus: `handleAction`,
// `deletePreset` und die Dialog-Handler werden extrahiert und gegen einen
// gestubbten Netzwerkrand (`fetch`, `window.location`) ausgefuehrt. Die
// Dialog-Verdrahtung (Klick-Ende-zu-Ende) deckt /e2e-verify gegen Staging ab.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/compare/__tests__/compare_hub_loeschen_bestaetigung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const PAGE = join(fileURLToPath(new URL('../[id]/', import.meta.url)), '+page.svelte');
const SRC = readFileSync(PAGE, 'utf8');
const SCRIPT = SRC.slice(SRC.indexOf('<script'), SRC.indexOf('</script>'));

/** Schneidet `function name(...) {...}` / `async function name(...) {...}` per Klammerzaehlung heraus. */
function funktion(name: string): string {
	const m = new RegExp(`(?:async\\s+)?function\\s+${name}\\s*\\(`).exec(SCRIPT);
	assert.ok(m, `Funktion ${name} fehlt in +page.svelte`);
	const start = m.index;
	const open = SCRIPT.indexOf('{', SCRIPT.indexOf(')', start));
	let depth = 0;
	for (let i = open; i < SCRIPT.length; i++) {
		if (SCRIPT[i] === '{') depth++;
		else if (SCRIPT[i] === '}' && --depth === 0) return SCRIPT.slice(start, i + 1);
	}
	throw new Error(`Klammern von ${name} nicht geschlossen`);
}

interface Zustand {
	deleteDialogOpen: boolean;
	isDeleting: boolean;
	sendMsg: string | null;
}
interface Aufruf {
	url: string;
	method: string;
}

/** Baut die Seitenlogik (nur Loesch-Pfad) und laeuft gegen gestubbtes fetch/location. */
function baue(deleteStatus: number) {
	const z: Zustand = { deleteDialogOpen: false, isDeleting: false, sendMsg: null };
	const aufrufe: Aufruf[] = [];
	const location = { href: '/compare/cp-2214' };
	const fetchStub = async (url: string, init?: { method?: string }) => {
		aufrufe.push({ url, method: init?.method ?? 'GET' });
		return { ok: deleteStatus >= 200 && deleteStatus < 300, status: deleteStatus };
	};
	const handlerNamen = ['handleDeleteConfirm', 'handleDeleteCancel', 'handleDeleteDialogOpenChange'].filter(
		(n) => new RegExp(`function\\s+${n}\\s*\\(`).test(SCRIPT)
	);
	const teile = [funktion('handleAction'), funktion('deletePreset'), ...handlerNamen.map(funktion)];
	// `$state`-Variablen werden durch ein Zustandsobjekt ersetzt (Svelte-Runen gibt es hier nicht).
	const körper = teile
		.join('\n')
		.replace(/\bdeleteDialogOpen\b/g, 'z.deleteDialogOpen')
		.replace(/\bisDeleting\b/g, 'z.isDeleting')
		.replace(/\bsendMsg\b/g, 'z.sendMsg');
	const fabrik = new Function(
		'z',
		'fetch',
		'window',
		'currentPreset',
		'togglePause',
		'handleTestSend',
		'archivePreset',
		stripTypeScriptTypes(körper) +
			`\nreturn { handleAction, handleDeleteConfirm: typeof handleDeleteConfirm === 'function' ? handleDeleteConfirm : undefined, handleDeleteCancel: typeof handleDeleteCancel === 'function' ? handleDeleteCancel : undefined, handleDeleteDialogOpenChange: typeof handleDeleteDialogOpenChange === 'function' ? handleDeleteDialogOpenChange : undefined };`
	);
	const noop = () => {};
	const api = fabrik(
		z,
		fetchStub,
		{ location },
		{ id: 'cp-2214', name: 'Dolomiten Süd' },
		noop,
		noop,
		noop
	);
	return { z, aufrufe, location, ...api } as {
		z: Zustand;
		aufrufe: Aufruf[];
		location: { href: string };
		handleAction: (id: string) => void;
		handleDeleteConfirm?: () => Promise<void>;
		handleDeleteCancel?: () => void;
		handleDeleteDialogOpenChange?: (open: boolean) => void;
	};
}

const loeschen = (a: Aufruf) => a.method === 'DELETE';
const tick = () => new Promise((r) => setTimeout(r, 0));

for (const aktion of ['delete', 'trash']) {
	describe(`#2214 — Kebab-Aktion "${aktion}"`, () => {
		test(`AC-1: "${aktion}" oeffnet den Bestaetigungsdialog und sendet noch kein DELETE`, async () => {
			const s = baue(200);
			s.handleAction(aktion);
			await tick();
			assert.equal(s.z.deleteDialogOpen, true, 'Dialog muss offen sein');
			assert.equal(s.aufrufe.filter(loeschen).length, 0, 'vor der Bestaetigung darf kein DELETE gesendet werden');
			assert.equal(s.location.href, '/compare/cp-2214', 'keine Navigation vor Bestaetigung');
		});
	});
}

describe('#2214 — Dialog-Verhalten', () => {
	test('AC-2: Abbrechen schliesst den Dialog, kein DELETE', async () => {
		const s = baue(200);
		s.handleAction('delete');
		assert.ok(s.handleDeleteCancel, 'handleDeleteCancel fehlt');
		s.handleDeleteCancel!();
		await tick();
		assert.equal(s.z.deleteDialogOpen, false);
		assert.equal(s.aufrufe.filter(loeschen).length, 0);
		assert.equal(s.location.href, '/compare/cp-2214');
	});

	test('AC-2: Schliessen per onOpenChange(false) sendet kein DELETE', async () => {
		const s = baue(200);
		s.handleAction('delete');
		assert.ok(s.handleDeleteDialogOpenChange, 'handleDeleteDialogOpenChange fehlt');
		s.handleDeleteDialogOpenChange!(false);
		await tick();
		assert.equal(s.z.deleteDialogOpen, false);
		assert.equal(s.aufrufe.filter(loeschen).length, 0);
	});

	test('AC-3: Bestaetigen sendet genau einen DELETE und navigiert nach /compare', async () => {
		const s = baue(200);
		s.handleAction('delete');
		assert.ok(s.handleDeleteConfirm, 'handleDeleteConfirm fehlt');
		await s.handleDeleteConfirm!();
		const del = s.aufrufe.filter(loeschen);
		assert.equal(del.length, 1);
		assert.equal(del[0].url, '/api/compare/presets/cp-2214');
		assert.equal(s.location.href, '/compare');
		assert.equal(s.z.isDeleting, false, 'isDeleting wird nach dem Request zurueckgesetzt');
	});

	test('AC-4: Serverfehler 500 -> Hub bleibt, "Löschen fehlgeschlagen."', async () => {
		const s = baue(500);
		s.handleAction('delete');
		assert.ok(s.handleDeleteConfirm, 'handleDeleteConfirm fehlt');
		await s.handleDeleteConfirm!();
		assert.equal(s.aufrufe.filter(loeschen).length, 1);
		assert.equal(s.z.sendMsg, 'Löschen fehlgeschlagen.');
		assert.equal(s.location.href, '/compare/cp-2214', 'keine Navigation bei Fehler');
		assert.equal(s.z.deleteDialogOpen, false, 'Dialog wird bei Fehler geschlossen');
		assert.equal(s.z.isDeleting, false);
	});
});
