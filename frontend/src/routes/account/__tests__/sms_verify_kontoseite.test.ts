// TDD RED — Issue #2406 (S3 aus #2153, Epic #2138), AC-13 (Frontend-Teil):
// Die Kontoseite zeigt bei ausstehender/unbestaetigter SMS-Nummer eine
// Code-Eingabe, einen Pending-Hinweis mit „Code erneut senden" — und ordnet die
// Fehlercodes des Servers verstaendlichen deutschen Meldungen zu.
// Spec: docs/specs/modules/sms_nummer_verifikation.md — AC-13.
//
// Echtes serverseitiges Rendern der ECHTEN Route (svelte/server `render()`,
// Hooks: lokaler $app-Stub + geteilte SSR-Kette), Muster
// pending_address_notice.test.ts (#2147 B2). Die Bedingung haengt nur an den
// Props (`data.profile`), nicht an `onMount` — sie wird im SSR also wirklich
// ausgewertet.
//
// Markup-Vertrag fuer /50 (einzige Vorgabe an die Form):
//   data-testid="sms-pending-notice"  — Hinweis-Element; enthaelt die zu
//       bestaetigende Nummer, ein <input data-testid="sms-code-input"> und
//       einen <button> „Code bestätigen" sowie einen <button>
//       „Code erneut senden".
//   Der Hinweis erscheint, solange `sms_verified` falsch ist und eine Nummer
//   (sms_to oder pending_sms_to) vorliegt — und NICHT, wenn die wirksame
//   Nummer bestaetigt ist.
//
// Fehlertexte: uebersetzt werden sie in der bestehenden, einzigen
// Uebersetzungsstelle der Kontoseite (`profileSaveErrorMessage`,
// account/profileSaveError.ts, #2147 B1) — kein zweites Uebersetzungsmodul.
//
// RED heute: +page.svelte kennt weder `pending_sms_to` noch `sms_verified`;
// profileSaveErrorMessage reicht `invalid_sms_number` roh durch.
//
// Pfadregel #1409: Prueflinge relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/account/__tests__/sms_verify_kontoseite.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> account -> routes -> src -> frontend
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
const { profileSaveErrorMessage } = (await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/account/profileSaveError.ts')).href
)) as { profileSaveErrorMessage: (status: number, body: unknown) => string };

const NUMMER = '+491511234567';
const AUSSTEHEND = '+491519876543';
const HINWEIS = 'sms-pending-notice';

function profil(extra: Record<string, unknown>) {
	return {
		id: 'konto-2406',
		display_name: 'Konto 2406',
		email: 'konto2406@beispiel.de',
		mail_to: 'konto2406@beispiel.de',
		email_verified: true,
		tier: 'standard',
		created_at: '2026-09-01T10:00:00Z',
		passkeys: [],
		...extra
	};
}

function renderAccount(p: Record<string, unknown>): string {
	return render(AccountPage, {
		props: {
			data: {
				profile: p,
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

function sichtbarerText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

function elementByTestId(html: string, testid: string): string | null {
	const marker = html.indexOf(`data-testid="${testid}"`);
	if (marker === -1) return null;
	const start = html.lastIndexOf('<', marker);
	const tag = (html.slice(start).match(/^<([a-zA-Z0-9-]+)/) ?? [])[1];
	assert.ok(tag, `Kein Tag-Name fuer data-testid="${testid}".`);
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

describe('#2406 AC-13 — Kontoseite: Code-Eingabe und Pending-Hinweis', () => {
	test('ausstehende_nummer_zeigt_hinweis_mit_code_eingabe', () => {
		const html = renderAccount(
			profil({ sms_to: NUMMER, sms_verified: true, pending_sms_to: AUSSTEHEND })
		);
		const hinweis = elementByTestId(html, HINWEIS);
		assert.ok(hinweis, `AC-13: bei pending_sms_to muss ein Element data-testid="${HINWEIS}" erscheinen.`);
		const text = sichtbarerText(hinweis);
		assert.ok(
			text.includes(AUSSTEHEND),
			`AC-13: der Hinweis muss die zu bestaetigende Nummer nennen, bekommen: ${text}`
		);
		assert.ok(
			html.includes('data-testid="sms-code-input"'),
			'AC-13: es muss ein Eingabefeld data-testid="sms-code-input" fuer den Code geben.'
		);
		const knoepfe = [...hinweis.matchAll(/<button[\s>][\s\S]*?<\/button>/g)].map((m) =>
			sichtbarerText(m[0])
		);
		assert.ok(
			knoepfe.some((k) => k.includes('Code erneut senden')),
			`AC-13: im Hinweis fehlt ein <button> „Code erneut senden", gefunden: ${JSON.stringify(knoepfe)}`
		);
		assert.ok(
			knoepfe.some((k) => /bestätigen/i.test(k)),
			`AC-13: im Hinweis fehlt ein <button> zum Bestaetigen des Codes, gefunden: ${JSON.stringify(knoepfe)}`
		);
	});

	test('eingetragene_aber_unbestaetigte_nummer_zeigt_denselben_hinweis', () => {
		const html = renderAccount(profil({ sms_to: NUMMER, sms_verified: false }));
		const hinweis = elementByTestId(html, HINWEIS);
		assert.ok(
			hinweis,
			'AC-13: auch ohne pending_sms_to muss der Hinweis erscheinen, solange sms_verified false ist.'
		);
		assert.ok(
			sichtbarerText(hinweis).includes(NUMMER),
			'AC-13: der Hinweis muss die unbestaetigte Nummer nennen.'
		);
	});

	test('bestaetigte_nummer_zeigt_keinen_hinweis', () => {
		// Gegenprobe: ein bedingungslos gerenderter Hinweis waere sonst gruen.
		const html = renderAccount(profil({ sms_to: NUMMER, sms_verified: true }));
		assert.equal(
			elementByTestId(html, HINWEIS),
			null,
			'AC-13 Gegenprobe: bei bestaetigter Nummer darf kein Pending-Hinweis erscheinen.'
		);
		assert.ok(
			!html.includes('data-testid="sms-code-input"'),
			'AC-13 Gegenprobe: ohne ausstehende Bestaetigung darf keine Code-Eingabe erscheinen.'
		);
	});

	test('ohne_nummer_kein_hinweis', () => {
		const html = renderAccount(profil({ sms_to: '', sms_verified: false }));
		assert.equal(
			elementByTestId(html, HINWEIS),
			null,
			'AC-13 Gegenprobe: ohne eingetragene Nummer gibt es nichts zu bestaetigen.'
		);
	});
});

describe('#2406 AC-13 — Fehlercodes werden verstaendlich uebersetzt', () => {
	const roh = ['invalid_sms_number', 'invalid_code', 'sms_not_allowed', 'rate_limit_exceeded'];

	function pruefe(status: number, body: unknown, erwarteteWoerter: RegExp) {
		const meldung = profileSaveErrorMessage(status, body);
		assert.ok(
			!roh.some((code) => meldung.includes(code)),
			`AC-13: die Meldung darf keinen rohen Fehlercode zeigen, bekommen: „${meldung}"`
		);
		assert.notEqual(
			meldung,
			'Speichern fehlgeschlagen',
			`AC-13: ${JSON.stringify(body)} braucht eine eigene, erklaerende Meldung statt des Sammeltexts.`
		);
		assert.match(
			meldung,
			erwarteteWoerter,
			`AC-13: die Meldung muss den Grund benennen, bekommen: „${meldung}"`
		);
	}

	test('invalid_sms_number_wird_erklaert', () => {
		pruefe(400, { error: 'invalid_sms_number' }, /nummer/i);
	});

	test('rate_limit_wird_erklaert', () => {
		pruefe(429, { error: 'rate_limit_exceeded' }, /später|spaeter|zu viele|warte/i);
	});

	test('invalid_code_wird_erklaert', () => {
		pruefe(400, { error: 'invalid_code' }, /code/i);
	});

	test('sms_not_allowed_wird_erklaert', () => {
		pruefe(400, { error: 'sms_not_allowed' }, /tarif|level|standard|premium/i);
	});

	test('unbekannte_codes_behalten_das_bisherige_verhalten', () => {
		// Regressionswaechter fuer #2147 B1.
		assert.equal(profileSaveErrorMessage(500, { detail: 'kaputt' }), 'kaputt');
		assert.equal(profileSaveErrorMessage(500, {}), 'Speichern fehlgeschlagen');
		assert.equal(
			profileSaveErrorMessage(409, { error: 'email_taken' }),
			'Diese E-Mail-Adresse wird bereits von einem anderen Konto verwendet.'
		);
	});
});
