// Issue #2412 S4b (Sammel-Issue #2153) — SMS-Kontingent auf /account, Verdrahtung.
// Spec: docs/specs/modules/sms_daily_usage_anzeige.md — AC-1, AC-2, AC-3, AC-7.
//
// Echtes serverseitiges Rendern der ECHTEN Route (svelte/server `render()`),
// Harness wie sms_verify_kontoseite.test.ts. Geprueft wird nur INNERHALB von
// data-testid="sms-daily-usage" — „Premium-SMS" steht auch in PremiumSmsLinkCard.
//
// Pfadregel #1409: Prueflinge relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/account/__tests__/sms_kontingent_anzeige.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(HERE, 'app-navigation-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const AccountPage = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/routes/account/+page.svelte')).href)
).default;

const BLOCK = 'sms-daily-usage';

function renderAccount(smsDailyUsage: unknown): string {
	return render(AccountPage, {
		props: {
			data: {
				profile: {
					id: 'konto-2412',
					display_name: 'Konto 2412',
					email: 'konto2412@beispiel.de',
					mail_to: 'konto2412@beispiel.de',
					email_verified: true,
					tier: 'standard',
					created_at: '2026-09-01T10:00:00Z',
					passkeys: []
				},
				scheduler: null,
				health: null,
				templates: [],
				trips: [],
				comparePresets: [],
				locations: [],
				metricPresets: [],
				smsDailyUsage
			}
		}
	}).body;
}

function sichtbarerText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.replace(/\(\s+/g, '(')
		.trim();
}

function blockText(html: string): string | null {
	const marker = html.indexOf(`data-testid="${BLOCK}"`);
	if (marker === -1) return null;
	const start = html.lastIndexOf('<', marker);
	const re = /<div[\s>]|<\/div>/g;
	re.lastIndex = start;
	let tiefe = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		tiefe += m[0].startsWith('</') ? -1 : 1;
		if (tiefe === 0) return sichtbarerText(html.slice(start, m.index + m[0].length));
	}
	assert.fail(`Element zu data-testid="${BLOCK}" nicht geschlossen.`);
}

describe('#2412 S4b — SMS-Kontingent-Block auf der Kontoseite', () => {
	test('AC-1: nur SMS erlaubt → "3 von 10" + Sub-Label, keine Premium-SMS-Zeile', () => {
		const text = blockText(
			renderAccount({
				sms: { used: 3, limit: 10, reserve: 2 },
				premium_sms: { used: 0, limit: 0, reserve: 3, reply_overshoot: 3 }
			})
		);
		assert.ok(text, 'AC-1: Block data-testid="sms-daily-usage" fehlt.');
		assert.ok(text.includes('3 von 10'), `AC-1: "3 von 10" fehlt, Block: ${text}`);
		assert.ok(
			text.includes('davon max. 8 Briefings, 2 Alarm-Reserve'),
			`AC-1: Sub-Label fehlt, Block: ${text}`
		);
		assert.ok(!text.includes('Premium-SMS'), `AC-1: Premium-SMS-Zeile darf fehlen, Block: ${text}`);
	});

	test('AC-2: beide Kanäle mit Limit > 0 → beide Zeilen', () => {
		const text = blockText(
			renderAccount({
				sms: { used: 4, limit: 10, reserve: 2 },
				premium_sms: { used: 5, limit: 15, reserve: 3, reply_overshoot: 3 }
			})
		);
		assert.ok(text, 'AC-2: Block fehlt.');
		assert.ok(text.includes('4 von 10'), `AC-2: SMS-Zeile fehlt, Block: ${text}`);
		assert.ok(text.includes('Premium-SMS'), `AC-2: Premium-SMS-Zeile fehlt, Block: ${text}`);
		assert.ok(text.includes('5 von 15'), `AC-2: Premium-SMS-Zähler fehlt, Block: ${text}`);
		assert.ok(
			text.includes('davon max. 12 Briefings, 3 Alarm-Reserve'),
			`AC-2: Premium-SMS-Sub-Label fehlt, Block: ${text}`
		);
	});

	test('AC-3: Antwort-Überhang → exakt "15 von 15 (+2 Antworten)"', () => {
		const text = blockText(
			renderAccount({
				sms: { used: 0, limit: 0, reserve: 2 },
				premium_sms: { used: 17, limit: 15, reserve: 3, reply_overshoot: 3 }
			})
		);
		assert.ok(text, 'AC-3: Block fehlt.');
		assert.ok(
			text.includes('15 von 15 (+2 Antworten)'),
			`AC-3: "15 von 15 (+2 Antworten)" fehlt, Block: ${text}`
		);
		assert.ok(!text.includes('17 von 15'), `AC-3: roher Überlauf "17 von 15" sichtbar: ${text}`);
	});

	test('AC-7: beide Limits 0 → Block fehlt komplett', () => {
		const html = renderAccount({
			sms: { used: 0, limit: 0, reserve: 2 },
			premium_sms: { used: 0, limit: 0, reserve: 3, reply_overshoot: 3 }
		});
		assert.equal(blockText(html), null, 'AC-7: bei Limit 0/0 darf der Block nicht erscheinen.');
	});

	test('AC-7: smsDailyUsage = null (204/Fehler) → Block fehlt komplett', () => {
		assert.equal(blockText(renderAccount(null)), null, 'AC-7: ohne Daten kein Block.');
	});
});
