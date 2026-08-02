// TDD RED — fix-1452 (AC-7 bis AC-9): Kanal-Anzeige stammt aus den Kanal-Flags,
// nicht aus dem toten `empfaenger`-Feld.
//
// Spec: docs/specs/modules/fix_1452_compare_empfaenger_settings.md (AC-7/AC-8/AC-9)
//
// Ist-Zustand (= RED-Grund):
//   - subscriptionHelpers.ts:251 leitet den E-Mail-Kanal ueber eine "@"-Heuristik
//     auf `preset.empfaenger` ab. Ein Preset ohne Empfaenger-Eintraege meldet
//     darum "kein E-Mail-Kanal", obwohl E-Mail fuer Compare-Presets gar kein
//     Opt-out kennt (KL-6 in versand_tab_vergleich.md).
//   - cockpitHelpers.ts:225,236 reicht `preset.empfaenger` als `channels` durch.
//   - CompareStatusRow.svelte:63-64 rendert rohe Adressen als Kanal-Chips.
//   - HomeHeroCompare.svelte:33 faellt auf `preset.empfaenger` zurueck.
//
// Soll: E-Mail ist fuer Compare-Presets immer aktiv; Telegram/SMS haengen an
// `send_telegram`/`send_sms`; angezeigt werden Kanal-LABEL, nie Adressen.
//
// Testart: echte Funktionsaufrufe + echtes serverseitiges Rendern der echten
// Svelte-Komponenten (svelte/server `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs).
// Keine Mocks, keine Datei-Inhalt-Pruefung.
//
// Ausfuehren:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_channel_display_from_flags.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

import type { ComparePreset } from '../../../types.ts';

// Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen, damit im Worktree
// die Worktree-Kopie und nicht das Hauptrepo geprueft wird.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const { presetChannels } = await import('../subscriptionHelpers.ts');
const { homeCompareTimeline } = await import('../../../../routes/_home/cockpitHelpers.ts');
const CompareStatusRow = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/molecules/CompareStatusRow.svelte')).href)
).default;
const HomeHeroCompare = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/organisms/HomeHeroCompare.svelte')).href)
).default;

const ADRESSE = 'henning@henemm.com';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1452',
		name: 'Testvergleich Korsika',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		weekday: 0,
		profil: 'allgemein',
		hour_from: 9,
		hour_to: 16,
		forecast_hours: 48,
		empfaenger: [],
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-07-01T00:00:00Z',
		display_config: {},
		...overrides
	} as ComparePreset;
}

/** Sichtbarer Text eines SSR-Ergebnisses (Tags + Svelte-Kommentar-Anker raus). */
function visibleText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

// ─── AC-7 ────────────────────────────────────────────────────────────────────

describe('AC-7: presetChannels haengt an den Flags, nicht am empfaenger-Feld', () => {
	const flags = { send_telegram: true, send_sms: false } as Partial<ComparePreset>;

	test('leeres und gefuelltes empfaenger liefern dasselbe Kanal-Set', () => {
		const leer = presetChannels(makePreset({ ...flags, empfaenger: [] }));
		const gefuellt = presetChannels(makePreset({ ...flags, empfaenger: [ADRESSE] }));
		assert.deepEqual(
			leer,
			gefuellt,
			`AC-7: Das empfaenger-Feld darf die Kanal-Anzeige nicht mehr beeinflussen — ` +
				`leer=${JSON.stringify(leer)} vs. gefuellt=${JSON.stringify(gefuellt)}`
		);
	});

	test('ohne empfaenger ist E-Mail trotzdem aktiv, Telegram dabei, SMS nicht (KL-6)', () => {
		const channels = presetChannels(makePreset({ ...flags, empfaenger: [] }));
		assert.deepEqual(
			[...channels].sort(),
			['Email', 'Telegram'],
			`AC-7: E-Mail ist fuer Compare-Presets ohne Opt-out immer aktiv, SMS nur bei send_sms — ` +
				`erhielt ${JSON.stringify(channels)}`
		);
	});

	test('send_sms=true ergaenzt SMS, auch ohne jeden empfaenger-Eintrag', () => {
		const channels = presetChannels(
			makePreset({ send_telegram: false, send_sms: true, empfaenger: [] } as Partial<ComparePreset>)
		);
		assert.deepEqual([...channels].sort(), ['Email', 'SMS'], `erhielt ${JSON.stringify(channels)}`);
	});
});

// ─── AC-8 ────────────────────────────────────────────────────────────────────

describe('AC-8: Cockpit-Kanal-Chips zeigen Kanal-Label statt Rohadressen', () => {
	test('CompareStatusRow rendert "Email" statt der empfaenger-Adresse', () => {
		const html = render(CompareStatusRow, {
			props: { preset: makePreset({ empfaenger: [ADRESSE] }) }
		}).body;
		const text = visibleText(html);

		assert.ok(
			!text.includes(ADRESSE),
			`AC-8: Die rohe Empfaenger-Adresse darf nicht mehr als Chip erscheinen — gerendert: "${text}"`
		);
		assert.ok(
			text.includes('Email'),
			`AC-8: Der Chip muss das Kanal-Label "Email" zeigen — gerendert: "${text}"`
		);
	});

	test('CompareStatusRow zeigt Telegram nur bei send_telegram', () => {
		const mit = visibleText(
			render(CompareStatusRow, {
				props: { preset: makePreset({ empfaenger: [ADRESSE], send_telegram: true } as Partial<ComparePreset>) }
			}).body
		);
		const ohne = visibleText(
			render(CompareStatusRow, { props: { preset: makePreset({ empfaenger: [ADRESSE] }) } }).body
		);
		assert.ok(mit.includes('Telegram'), `send_telegram=true muss "Telegram" zeigen — "${mit}"`);
		assert.ok(!ohne.includes('Telegram'), `ohne Opt-in darf "Telegram" nicht erscheinen — "${ohne}"`);
	});

	test('homeCompareTimeline liefert Kanal-Label, nicht die empfaenger-Adressen', () => {
		const preset = makePreset({
			empfaenger: [ADRESSE],
			send_telegram: true,
			letzter_versand: '2026-07-30T07:00:00Z'
		} as Partial<ComparePreset>);
		const rows = homeCompareTimeline(preset, new Date('2026-07-31T06:00:00Z'));

		assert.ok(rows.length > 0, 'Timeline muss mindestens eine Zeile liefern');
		for (const row of rows) {
			assert.deepEqual(
				[...(row.channels ?? [])].sort(),
				['Email', 'Telegram'],
				`AC-8: Timeline-Zeile "${row.when}" muss Kanal-Label fuehren, erhielt ${JSON.stringify(row.channels)}`
			);
		}
	});
});

// ─── AC-9 ────────────────────────────────────────────────────────────────────

describe('AC-9: HomeHeroCompare nutzt ausschliesslich preset.channels', () => {
	test('channels=undefined + gefuelltes empfaenger → keine Kanal-Eintraege', () => {
		const text = visibleText(
			render(HomeHeroCompare, {
				props: {
					preset: {
						id: 'cmp-1452',
						name: 'Testvergleich Korsika',
						location_ids: ['loc-1'],
						empfaenger: [ADRESSE, 'zweite@example.com'],
						display_config: {}
					}
				}
			}).body
		);

		assert.ok(
			!text.includes(ADRESSE) && !text.includes('zweite@example.com'),
			`AC-9: Ohne preset.channels darf NICHT auf empfaenger zurueckgefallen werden — gerendert: "${text}"`
		);
	});

	test('channels gesetzt → genau diese Kanaele erscheinen (Gegenprobe)', () => {
		const text = visibleText(
			render(HomeHeroCompare, {
				props: {
					preset: {
						id: 'cmp-1452',
						name: 'Testvergleich Korsika',
						location_ids: ['loc-1'],
						empfaenger: [ADRESSE],
						channels: ['Email', 'Telegram'],
						display_config: {}
					}
				}
			}).body
		);
		assert.ok(text.includes('Email') && text.includes('Telegram'), `erwartet Email+Telegram — "${text}"`);
		assert.ok(!text.includes(ADRESSE), `Adresse darf nie erscheinen — "${text}"`);
	});
});
