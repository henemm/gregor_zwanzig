// Issue #2653 (i18n F4, Epic #2644) — AC-4: die Admin-Seite in der Sprache des
// Admins. Echter SSR-Render der Seite (Pruefstand f4KontoAdminNavSsr.ts, feste
// Zeit-Fixture) und die ECHTEN Helfer aus lib/admin.ts, ueber die die Seite ihre
// Zeilen- und Einladungsfehler bekommt (sendAdminUpdate/createInvite: nur die
// Netzgrenze `fetch` ist ersetzt). Jeder en-Fall rendert zuerst de und schaltet
// dann OHNE Neuladen auf en (Mutation tr()/$t -> trFor('de', …) wird rot).
// Englische Anker sind feste Literale.
// Spec: docs/specs/modules/i18n_f4_konto_admin_nav_2653.md
//
//   cd frontend && npm test -- src/routes/admin/__tests__/admin_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale, adminRendern, adminDaten } from '../../__tests__/f4KontoAdminNavSsr.ts';
import { FRONTEND } from '../../__tests__/onboardingSsr.ts';
import { deutscheReste, sichtbarerText, attributText } from '../../__tests__/f3Sprachpruefung.ts';

const A = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/admin.ts')).href);

afterEach(() => locale.set('de'));

function enNachDe<T>(f: () => T): T {
	locale.set('de');
	f();
	locale.set('en');
	return f();
}
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: "${teil}"\n${text}`);

describe('AC-4: Zeilenfehler (adminErrorText) je Status', () => {
	const FAELLE: [number, string | undefined, string, string][] = [
		[403, undefined, 'Keine Berechtigung', 'No permission'],
		[404, undefined, 'Nutzer nicht gefunden', 'User not found'],
		[409, 'cannot_disable_self', 'Das eigene Konto kann nicht gesperrt werden', 'You cannot lock your own account'],
		[400, undefined, 'Ungültige Eingabe', 'Invalid input'],
		[500, undefined, 'Aktion fehlgeschlagen. Bitte erneut versuchen.', 'Action failed. Please try again.']
	];
	for (const [status, code, de, en] of FAELLE) {
		test(`${status}${code ? ' ' + code : ''}: „${de}" | „${en}"`, () => {
			locale.set('de');
			assert.equal(A.adminErrorText(status, code), de);
			assert.equal(enNachDe(() => A.adminErrorText(status, code)), en);
		});
	}

	test('Verdrahtung: sendAdminUpdate liefert bei 409 cannot_disable_self den englischen Zeilenfehler', async () => {
		const antwort409 = (async () =>
			new Response(JSON.stringify({ error: 'cannot_disable_self' }), { status: 409 })) as unknown as typeof fetch;
		locale.set('en');
		assert.deepEqual(await A.sendAdminUpdate(antwort409, 'golden-de', 'disabled', { disabled: true }), {
			ok: false,
			text: 'You cannot lock your own account'
		});
		const kaputt = (async () => {
			throw new Error('netz');
		}) as unknown as typeof fetch;
		assert.deepEqual(await A.sendAdminUpdate(kaputt, 'x', 'tier', {}), { ok: false, text: 'Action failed. Please try again.' });
	});

	test('Verdrahtung: createInvite liefert Einladungsfehler in der Sprache (409 invite_used, 403)', async () => {
		const mit = (status: number, error?: string) =>
			(async () => new Response(JSON.stringify({ error }), { status })) as unknown as typeof fetch;
		locale.set('en');
		assert.deepEqual(await A.createInvite(mit(409, 'invite_used'), 'free', ''), { ok: false, text: 'The invitation has already been used' });
		assert.deepEqual(await A.createInvite(mit(403), 'free', ''), { ok: false, text: 'No permission' });
		assert.deepEqual(await A.revokeInvite(mit(404), 'i1'), { ok: false, text: 'Invitation not found' });
		locale.set('de');
		assert.deepEqual(await A.createInvite(mit(400), 'free', ''), { ok: false, text: 'Ungültige Eingabe (Level oder Notiz über 200 Zeichen)' });
	});
});

describe('AC-4: Einladungsstatus (inviteStatusText)', () => {
	const benutzt = { id: 'b', tier: 'premium', note: '', status: 'used', created_at: '', created_by: '', used_by: 'karl', used_at: '2026-10-07T08:00:00Z', revoked_at: null };
	const weg = { ...benutzt, status: 'revoked', used_by: '', used_at: null, revoked_at: '2026-10-08T09:00:00Z' };
	const offen = { ...benutzt, status: 'open', used_by: '', used_at: null };
	test('benutzt: „Benutzt von karl am 7.10.2026" | „Used by karl on 07/10/2026"', () => {
		locale.set('de');
		assert.equal(A.inviteStatusText(benutzt), 'Benutzt von karl am 7.10.2026');
		assert.equal(enNachDe(() => A.inviteStatusText(benutzt)), 'Used by karl on 07/10/2026');
	});
	test('widerrufen und offen', () => {
		assert.equal(enNachDe(() => A.inviteStatusText(weg)), 'Revoked on 08/10/2026');
		assert.equal(enNachDe(() => A.inviteStatusText(offen)), 'Open');
		locale.set('de');
		assert.equal(A.inviteStatusText(weg), 'Widerrufen am 8.10.2026');
		assert.equal(A.inviteStatusText(offen), 'Offen');
	});
});

describe('AC-4: Admin-Seite (SSR) auf Englisch', () => {
	const html = () => enNachDe(() => adminRendern(adminDaten()));

	test('kein deutscher Katalogtext (admin.*, konto.*, nav.*) im Text oder in Attributen', () => {
		const h = html();
		// konto.* ohne die Tier-Namen: „Standard" ist dort Eigenname (TIER_LABELS), kein Rest.
		const ohneTier = (r: string[]) => r.filter((x) => x !== 'konto.wetter_profile.standard: Standard');
		assert.deepEqual(ohneTier(deutscheReste(sichtbarerText(h), ['admin.', 'konto.', 'nav.'])), []);
		assert.deepEqual(ohneTier(deutscheReste(attributText(h), ['admin.', 'konto.', 'nav.'])), []);
	});

	test('feste englische Anker; Namen, Adressen, Tier-Namen und Zahlen unveraendert', () => {
		const t = sichtbarerText(html());
		for (const s of [
			'Administration Admin Users, tier and account lock',
			'Invitations',
			'Level Free Standard Premium',
			'Note',
			'Create invitation',
			'(no note) · Standard · created 06/10/2026, 12:00:00',
			'Open',
			'Revoke',
			'Onkel Karl · Premium · created 06/10/2026, 12:00:00 Used by karl on 07/10/2026',
			'Cousin · Free · created 06/10/2026, 12:00:00 Revoked on 08/10/2026',
			'Golden golden-de · u@example.org Tier: Premium',
			'Open request: Standard (since 27/10/2026, 10:00:00)',
			'Last trip report: no run',
			'Usage today (Open-Meteo): 12',
			'bert · test user · locked',
			'Last trip report: 29/10/2026, 04:00:00 (ok)',
			'Unlock',
			'Lock'
		])
			hat(t, s);
		for (const w of ['Einladung', 'Notiz', 'erstellt', 'Benutzt', 'Widerrufen', 'Sperren', 'Entsperren', 'gesperrt', 'Testnutzer', 'Verbrauch', 'kein Lauf'])
			assert.ok(!t.includes(w), w);
	});

	test('aria-label der Tier-Auswahl englisch, Name unveraendert', () => {
		const h = html();
		hat(h, 'aria-label="Tier of Golden"');
		hat(h, 'aria-label="Tier of bert"');
	});

	test('Deutsch unveraendert neben Englisch im selben Prozess', () => {
		html();
		locale.set('de');
		const t = sichtbarerText(adminRendern(adminDaten()));
		hat(t, 'Verwaltung Admin Nutzer, Tier und Kontosperre');
		hat(t, 'Benutzt von karl am 7.10.2026');
		hat(t, 'Letzter Trip-Report: kein Lauf');
	});
});
