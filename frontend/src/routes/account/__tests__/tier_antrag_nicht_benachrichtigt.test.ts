// TDD RED — Issue #2436 AC-6 (Kontoseite): Ist ein Antrag offen und der
// Betreiber NICHT benachrichtigt (requested_notified_at fehlt), steht im
// Pending-Bereich ein deutlicher Hinweis — auch nach einem Neuladen (SSR aus
// dem Profil). Ist er benachrichtigt, steht der Hinweis nicht da.
// Spec: docs/specs/modules/fix_2436_tier_antrag_ehrliche_rueckmeldung.md
// Markup-Vertrag: Element data-testid="tier-change-not-notified".
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/account/__tests__/tier_antrag_nicht_benachrichtigt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> account -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

// Lokaler Stub zuerst, danach die geteilte Kette (.svelte-Kompilat + $lib).
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


const NOTICE = 'tier-change-not-notified';

function profil(extra: Record<string, unknown>) {
	return {
		id: 'konto-2436',
		display_name: 'Konto 2436',
		email: 'k@beispiel.de',
		mail_to: 'k@beispiel.de',
		email_verified: true,
		tier: 'free',
		created_at: '2026-09-01T10:00:00Z',
		passkeys: [],
		...extra
	};
}

function renderAccount(profile: Record<string, unknown>): string {
	return render(AccountPage, {
		props: {
			data: {
				profile,
				scheduler: null,
				health: null,
				templates: [],
				trips: [],
				comparePresets: [],
				locations: [],
				metricPresets: []
			}
		}
	}).body;
}

/** Sichtbarer Text: Svelte-SSR-Kommentare und Tags entfernt, Leerraum verdichtet. */
function sichtbarerText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

/** Vollstaendiges Element (inkl. verschachtelter gleichnamiger Tags) zum testid. */
function elementByTestId(html: string, testid: string): string | null {
	const marker = html.indexOf(`data-testid="${testid}"`);
	if (marker === -1) return null;
	const start = html.lastIndexOf('<', marker);
	const tag = (html.slice(start).match(/^<([a-zA-Z0-9-]+)/) ?? [])[1];
	assert.ok(tag, `Kein Tag-Name fuer data-testid="${testid}" gefunden.`);
	const re = new RegExp(`<${tag}[\\s>]|</${tag}>`, 'g');
	re.lastIndex = start;
	let tiefe = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('</')) {
			tiefe -= 1;
			if (tiefe === 0) return html.slice(start, m.index + m[0].length);
		} else {
			tiefe += 1;
		}
	}
	assert.fail(`Element zu data-testid="${testid}" nicht geschlossen.`);
}

describe('#2436 AC-6 — Kontoseite zeigt ehrlich, ob der Betreiber benachrichtigt wurde', () => {
	test('offener_antrag_ohne_nachweis_zeigt_warnhinweis_im_pending_bereich', () => {
		const html = renderAccount(
			profil({ requested_tier: 'standard', requested_at: '2026-10-01T10:00:00Z' })
		);
		const pending = elementByTestId(html, 'tier-change-pending');
		assert.ok(pending, 'Pending-Bereich muss gerendert werden.');
		const hinweis = elementByTestId(html, NOTICE);
		assert.ok(hinweis, `Element data-testid="${NOTICE}" fehlt.`);
		const text = sichtbarerText(hinweis);
		assert.match(text, /gespeichert/, text);
		assert.match(text, /nicht benachrichtigt/, text);
		assert.ok(pending.includes(NOTICE) || html.indexOf(NOTICE) > html.indexOf('tier-change-pending'));
	});

	test('offener_antrag_mit_nachweis_zeigt_keinen_warnhinweis', () => {
		const html = renderAccount(
			profil({
				requested_tier: 'standard',
				requested_at: '2026-10-01T10:00:00Z',
				requested_notified_at: '2026-10-01T10:00:05Z'
			})
		);
		assert.ok(elementByTestId(html, 'tier-change-pending'), 'Pending-Bereich muss da sein.');
		assert.equal(elementByTestId(html, NOTICE), null, 'kein Warnhinweis bei Nachweis');
	});

	test('ohne_antrag_kein_warnhinweis', () => {
		const html = renderAccount(profil({}));
		assert.equal(elementByTestId(html, NOTICE), null);
	});
});
