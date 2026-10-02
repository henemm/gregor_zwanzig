// TDD RED — Issue #2229 (AC-3): Vergleichs-Vorschau sagt, was Premium-SMS sendet.
//
// Spec: docs/specs/bugfix/fix_2229_premium_sms_kanallisten.md (Test 4, Test 4b)
//
// Ist: Die Vorschau hat drei Reiter (Email/Telegram/SMS) und laesst offen, was
// Premium-SMS verschickt. Soll: kein vierter Reiter; beim SMS-Reiter steht bei
// eingeschalteter Premium-SMS der Hinweis „Premium-SMS versendet denselben Text".
//   - reiner Helfer `premiumSmsPreviewNote(preset, channel)` in subscriptionHelpers.ts
//   - Prop `note` am echten `CompareChannelSwitch`, gerendert als
//     data-testid="compare-preview-premium-sms-note"
// Die Verdrahtung in CompareTabs.svelte prueft der Staging-Schritt (Spec, Testplan).
//
// Testart: echte Funktionsaufrufe + echtes serverseitiges Rendern der echten
// Komponente (svelte/server `render`, Hooks frontend/test-svelte-ssr-hooks.mjs,
// Muster compare_channel_display_from_flags.test.ts). Keine Mocks.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_preview_premium_sms_hinweis.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

import type { ComparePreset } from '../../../types.ts';

// Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
// Dynamisch als Namespace: ein fehlender Export darf nicht die ganze Datei beim
// Linken abbrechen (sonst sagte der SSR-Test nichts ueber die Komponente).
const helpers: Record<string, unknown> = await import('../subscriptionHelpers.ts');
const CompareChannelSwitch = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/molecules/CompareChannelSwitch.svelte')).href)
).default;

const HINWEIS = 'Premium-SMS versendet denselben Text';
const TESTID = 'compare-preview-premium-sms-note';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-2229',
		name: 'Huettenvergleich',
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
		created_at: '2026-10-01T00:00:00Z',
		display_config: {},
		...overrides
	} as ComparePreset;
}

function note(preset: ComparePreset, channel: string): string {
	const fn = helpers.premiumSmsPreviewNote;
	assert.equal(
		typeof fn,
		'function',
		'subscriptionHelpers.ts exportiert keinen Helfer premiumSmsPreviewNote(preset, channel) (AC-3).'
	);
	return (fn as (p: ComparePreset, c: string) => string)(preset, channel);
}

function zaehle(html: string, nadel: string): number {
	return html.split(nadel).length - 1;
}

describe('AC-3 Helfer: Hinweis genau beim SMS-Reiter mit eingeschalteter Premium-SMS', () => {
	test('send_premium_sms=true, Reiter sms → Hinweistext', () => {
		assert.equal(note(makePreset({ send_premium_sms: true }), 'sms'), HINWEIS);
	});

	test('send_premium_sms=true, Reiter email/telegram → leer', () => {
		const preset = makePreset({ send_premium_sms: true });
		assert.equal(note(preset, 'email'), '');
		assert.equal(note(preset, 'telegram'), '');
	});

	test('Premium-SMS aus oder nicht gesetzt, Reiter sms → leer', () => {
		assert.equal(note(makePreset({ send_premium_sms: false, send_sms: true }), 'sms'), '');
		assert.equal(note(makePreset({ send_sms: true }), 'sms'), '');
	});
});

describe('AC-3 Komponente: echter CompareChannelSwitch rendert den Hinweis, keinen vierten Reiter', () => {
	test('note gesetzt → genau ein Hinweis-Element mit dem Text, genau drei Reiter', () => {
		const { body } = render(CompareChannelSwitch, {
			props: { value: 'sms', channels: ['email', 'sms', 'premium-sms'], note: HINWEIS }
		});
		assert.equal(
			zaehle(body, `data-testid="${TESTID}"`),
			1,
			`Hinweis-Element ${TESTID} fehlt oder ist mehrfach da. HTML: ${body}`
		);
		const m = body.match(new RegExp(`data-testid="${TESTID}"[^>]*>([^<]*)<`));
		assert.ok(m, `Hinweis-Element ohne direkten Textinhalt. HTML: ${body}`);
		assert.equal(m[1].trim(), HINWEIS);
		assert.equal(zaehle(body, '<button'), 3, 'Es darf keinen vierten Reiter geben (AC-3).');
	});

	test('note leer → kein Hinweis-Element, weiterhin drei Reiter', () => {
		// Absichtlich schon heute gruen: bewacht, dass der Hinweis nicht bedingungslos erscheint.
		const { body } = render(CompareChannelSwitch, {
			props: { value: 'sms', channels: ['email', 'sms'], note: '' }
		});
		assert.equal(zaehle(body, `data-testid="${TESTID}"`), 0);
		assert.equal(zaehle(body, '<button'), 3);
	});
});
