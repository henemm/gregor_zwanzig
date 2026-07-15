// doc-compliance-test
//
// Issue #1260 Scheibe S5 — AC-11: Der Kurzstil-Schalter „Telegram im SMS-
// Kurzstil" ist EINE geteilte Komponente (shared/TelegramKurzstilToggle.svelte),
// die in BEIDEN Editor-Kontexten mit demselben Baustein + derselben Beschriftung
// gerendert wird:
//   - context="route"     → shared/versand-tab/VTBriefingChannels.svelte (Trip)
//   - context="vergleich" → shared/AlarmeTab.svelte (amtliche Compare-Warnungen)
//
// SCHICHT-EINORDNUNG (Test-Politik, CLAUDE.md): Dies ist eine STRUKTURELLE
// INVARIANTEN-Pruefung (eine geteilte Komponente, kein Compare-Nachbau) via
// Source-Inspection — KEIN Verhaltensnachweis. Deshalb der Marker
// `doc-compliance-test` oben (Ausnahme zur Datei-Grep-Regel). Der eigentliche
// VERHALTENS-Nachweis fuer AC-11 laeuft:
//   - fuer den Hub-Alarme-Kurzstil-Pfad: als echter node:test in
//     compare/__tests__/compare_hub_alarme_bridge.test.ts (#1260-Block,
//     hydrateAlarmFieldsFromPreset/flushPendingAlarmSave gegen ein Preset-Objekt)
//   - fuer den End-to-End-Klickpfad beider Kontexte: in der Staging-E2E
//     (Playwright, kein jsdom-Mount moeglich — Svelte-5-Komponenten sind ohne
//     @testing-library/svelte in diesem Setup nicht mountbar).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/telegram_kurzstil_shared_toggle.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared
const SHARED_DIR = join(here, '..');
// __tests__ -> shared -> components -> lib -> src
const SRC_DIR = join(here, '..', '..', '..', '..');

const SHARED_TOGGLE = join(SHARED_DIR, 'TelegramKurzstilToggle.svelte');
const VT_BRIEFING_CHANNELS = join(SHARED_DIR, 'versand-tab', 'VTBriefingChannels.svelte');
const ALARME_TAB = join(SHARED_DIR, 'AlarmeTab.svelte');

const LABEL = 'Telegram im SMS-Kurzstil';
// Beide Mount-Stellen importieren aus DERSELBEN Modul-Spezifikation.
const IMPORT_SPECIFIER = '$lib/components/shared/TelegramKurzstilToggle.svelte';

function read(path: string): string {
	return readFileSync(path, 'utf-8');
}

function collectSvelteFiles(dir: string): string[] {
	const results: string[] = [];
	if (!existsSync(dir)) return results;
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) results.push(...collectSvelteFiles(full));
		else if (entry.endsWith('.svelte')) results.push(full);
	}
	return results;
}

describe('AC-11: geteilte Komponente existiert und traegt die eine Beschriftung', () => {
	test('shared/TelegramKurzstilToggle.svelte existiert', () => {
		assert.ok(existsSync(SHARED_TOGGLE), `Erwartet geteilte Komponente unter ${SHARED_TOGGLE}`);
	});

	test('Komponente traegt die Beschriftung „Telegram im SMS-Kurzstil"', () => {
		assert.ok(read(SHARED_TOGGLE).includes(LABEL), `Label „${LABEL}" fehlt in der Komponente`);
	});

	test('Komponente unterstuetzt BEIDE Kontexte (route + vergleich) als Prop', () => {
		const src = read(SHARED_TOGGLE);
		assert.match(
			src,
			/context\?:\s*'route'\s*\|\s*'vergleich'/,
			'context-Prop muss beide Kontext-Literale zulassen (gemeinsamer Baustein)'
		);
	});
});

describe('AC-11: DIESELBE Komponente wird in route UND vergleich eingebunden', () => {
	test('route: VTBriefingChannels importiert + mountet TelegramKurzstilToggle', () => {
		const src = read(VT_BRIEFING_CHANNELS);
		assert.ok(src.includes(IMPORT_SPECIFIER), 'VTBriefingChannels muss die geteilte Komponente importieren');
		assert.match(src, /<TelegramKurzstilToggle\b/, 'VTBriefingChannels muss <TelegramKurzstilToggle> rendern');
	});

	test('vergleich: AlarmeTab importiert + mountet TelegramKurzstilToggle mit context="vergleich"', () => {
		const src = read(ALARME_TAB);
		assert.ok(src.includes(IMPORT_SPECIFIER), 'AlarmeTab muss die geteilte Komponente importieren');
		assert.match(
			src,
			/<TelegramKurzstilToggle[\s\S]*?context="vergleich"/,
			'AlarmeTab muss <TelegramKurzstilToggle context="vergleich"> rendern'
		);
	});

	test('beide Mount-Stellen referenzieren die IDENTISCHE Modul-Spezifikation (keine Divergenz)', () => {
		assert.ok(read(VT_BRIEFING_CHANNELS).includes(IMPORT_SPECIFIER));
		assert.ok(read(ALARME_TAB).includes(IMPORT_SPECIFIER));
	});
});

describe('AC-11: kein unabhaengig gepflegter Compare-Nachbau', () => {
	test('genau EINE .svelte-Datei traegt die Kurzstil-Beschriftung (kein Duplikat)', () => {
		const carriers = collectSvelteFiles(SRC_DIR).filter((f) => read(f).includes(LABEL));
		const short = carriers.map((f) => f.replace(SRC_DIR + '/', ''));
		assert.deepStrictEqual(
			short,
			['lib/components/shared/TelegramKurzstilToggle.svelte'],
			`Erwartet genau die geteilte Komponente als Traeger der Beschriftung, gefunden: ${short.join(', ')}`
		);
	});
});
