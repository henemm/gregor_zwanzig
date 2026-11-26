// Issue #2990 — EINE Kanal-Ableitung fuer Trip und Ortsvergleich.
// Spec: docs/specs/modules/refactor_2990_kanal_ableitung_eine_quelle.md (AC-1, AC-3..AC-7)
//
// Echte Funktionen, keine Mocks: Trip (`reportChannels`, `heroKanaele` aus report_config)
// und Ortsvergleich (`presetChannels`, `channelNamesLabel` aus dem Preset) muessen bei
// gleichen Kanal-Flags dasselbe liefern wie der gemeinsame Baustein `shared/aktiveKanaele.ts`.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/aktive_kanaele_2990.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { reportChannels, heroKanaele } from '../../../../routes/_home/cockpitHelpers.ts';
import { presetChannels, channelNamesLabel } from '../../compare/subscriptionHelpers.ts';

type Baustein = {
	aktiveKanaele: (q: Record<string, unknown> | null | undefined) => string[];
	aktiveKanalNamen: (q: Record<string, unknown> | null | undefined) => string[];
	KANAL_ANZEIGENAME: Record<string, string>;
};
let baustein: Baustein | null = null;
try {
	baustein = (await import('../aktiveKanaele.ts')) as unknown as Baustein;
} catch {
	baustein = null;
}
const b = (): Baustein => {
	assert.ok(baustein, 'Baustein shared/aktiveKanaele.ts fehlt (AC-7: EINE Quelle der Kanal-Ableitung)');
	return baustein;
};

const ALLE = ['Email', 'Telegram', 'SMS', 'Premium-SMS'];
const SLOTS_AN = { morning_enabled: true, evening_enabled: true };

const trip = (flags: Record<string, unknown>): string[] =>
	heroKanaele({ ...SLOTS_AN, ...flags } as never);
const vergleich = (flags: Record<string, unknown>): string[] =>
	presetChannels({ id: 'p1', name: 'V', ...flags } as never);

describe('AC-1: gleiche Flags → gleiche Kanaele, feste Reihenfolge', () => {
	test('alle vier an: Trip und Vergleich zeigen Email, Telegram, SMS, Premium-SMS', () => {
		const flags = { send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true };
		assert.deepEqual(trip(flags), ALLE);
		assert.deepEqual(vergleich(flags), ALLE);
	});
	test('Feld-Reihenfolge der Eingabe aendert die Ausgabe-Reihenfolge nicht', () => {
		const flags = { send_premium_sms: true, send_sms: true, send_telegram: true, send_email: true };
		assert.deepEqual(trip(flags), ALLE);
		assert.deepEqual(vergleich(flags), ALLE);
	});
});

describe('AC-3: abgeschaltete Orts-Mail zeigt kein "Email"', () => {
	test('Vergleich send_email:false + Telegram → nur Telegram (wie Trip)', () => {
		const flags = { send_email: false, send_telegram: true };
		assert.deepEqual(trip(flags), ['Telegram'], 'Trip-Referenz');
		assert.deepEqual(vergleich(flags), ['Telegram'], 'Vergleich zeigt heute faelschlich immer "Email"');
		assert.equal(
			channelNamesLabel({ id: 'p1', name: 'V', ...flags } as never),
			'Telegram',
			'Detail-Hub "Kanaele" folgt derselben Ableitung'
		);
	});
	test('Vergleich mit allem aus → keine Kanaele, Hub-Stat "—"', () => {
		const flags = { send_email: false };
		assert.deepEqual(vergleich(flags), []);
		assert.equal(channelNamesLabel({ id: 'p1', name: 'V', ...flags } as never), '—');
	});
});

describe('AC-4: fehlendes send_email = an', () => {
	test('Alt-Preset ohne send_email und leeres Preset → nur Email', () => {
		assert.deepEqual(vergleich({}), ['Email']);
		assert.deepEqual(vergleich({ send_telegram: false }), ['Email']);
		assert.deepEqual(trip({}), ['Email']);
	});
});

describe('AC-5: nur genau true, nie Signal, empfaenger/channel_layouts wirkungslos', () => {
	for (const wert of [false, undefined, 'true', 1, null]) {
		test(`Opt-in-Wert ${JSON.stringify(wert)} → kein Zusatzkanal`, () => {
			const flags = { send_telegram: wert, send_sms: wert, send_premium_sms: wert };
			assert.deepEqual(trip(flags), ['Email']);
			assert.deepEqual(vergleich(flags), ['Email']);
		});
	}
	test('empfaenger, channel_layouts und Signal-Feld aendern nichts', () => {
		const basis = { send_email: false, send_sms: true };
		const laerm = {
			...basis,
			empfaenger: ['a@b.com'],
			send_signal: true,
			display_config: { channel_layouts: { email: {}, telegram: {}, signal: {} } }
		};
		assert.deepEqual(vergleich(laerm), vergleich(basis));
		assert.deepEqual(vergleich(laerm), ['SMS']);
		assert.ok(!vergleich(laerm).includes('Signal'));
	});
});

describe('AC-6: Hero ohne aktiven Slot bleibt leer', () => {
	test('Slots aus → [] trotz Kanal-Flags', () => {
		assert.deepEqual(
			heroKanaele({ morning_enabled: false, evening_enabled: false, send_telegram: true } as never),
			[]
		);
	});
});

describe('AC-7: alte Funktionen liefern genau das Ergebnis des Bausteins', () => {
	const faelle: Record<string, unknown>[] = [
		{},
		{ send_email: false },
		{ send_email: false, send_telegram: true },
		{ send_sms: true, send_premium_sms: true },
		{ send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true }
	];
	test('Schluessel-Reihenfolge und Anzeigenamen des Bausteins', () => {
		assert.deepEqual(
			b().aktiveKanaele({ send_telegram: true, send_sms: true, send_premium_sms: true }),
			['email', 'telegram', 'sms', 'premium-sms']
		);
		assert.deepEqual(b().KANAL_ANZEIGENAME, {
			email: 'Email',
			telegram: 'Telegram',
			sms: 'SMS',
			'premium-sms': 'Premium-SMS'
		});
	});
	for (const f of faelle) {
		test(`Flags ${JSON.stringify(f)}: reportChannels/heroKanaele/presetChannels = Baustein`, () => {
			assert.deepEqual(reportChannels(f as never), b().aktiveKanaele(f));
			assert.deepEqual(trip(f), b().aktiveKanalNamen({ ...SLOTS_AN, ...f }));
			assert.deepEqual(vergleich(f), b().aktiveKanalNamen(f));
		});
	}
});
