// Fix-Loop 1 (F005) — Klick-Verdrahtung der Startseite, Spec
// docs/specs/modules/onboarding_willkommen_checkliste.md, AC-4, AC-5, AC-8.
//
// Geprueft wird die Logik, die +page.svelte fuer "Verstanden", "Ausblenden"
// und "Testmail senden" benutzt (erzeugeOnboardingAktionen). Netzgrenze ist ein
// aufzeichnender api-Ersatz mit den echten Signaturen put/post; die
// Entscheidungen (welches Flag, wann gilt die Testmail als gesendet) fallen im
// Produktivcode.
//
// Mutationen, die hier rot werden MUESSEN: "Ausblenden" schickt
// onboarding_dismissed statt checklist_dismissed (und umgekehrt); Testmail
// gilt bei HTTP 200 ohne status "ok" als gesendet; Fehlertext der Antwort
// wird verschluckt.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Pfadregel #1409: Pruefling relativ zur Testdatei.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const { erzeugeOnboardingAktionen } = (await import(
	pathToFileURL(path.resolve(HERE, '..', 'onboardingAktionen.ts')).href
)) as typeof import('../onboardingAktionen.ts');

type Aufruf = { methode: 'put' | 'post'; pfad: string; body: unknown };

function aufbau(antwort: { post?: unknown; werfe?: unknown; putWirft?: boolean } = {}) {
	const aufrufe: Aufruf[] = [];
	let lokal: Record<string, unknown> = {};
	let testmail: { status: string; fehler: string | null } = { status: 'idle', fehler: null };
	const aktionen = erzeugeOnboardingAktionen({
		api: {
			put: async (pfad, body) => {
				aufrufe.push({ methode: 'put', pfad, body });
				if (antwort.putWirft) throw new Error('netz');
				return {};
			},
			post: async (pfad, body) => {
				aufrufe.push({ methode: 'post', pfad, body });
				if (antwort.werfe !== undefined) throw antwort.werfe;
				return antwort.post;
			}
		},
		t: (k) => `T(${k})`,
		getLokal: () => lokal,
		setLokal: (neu) => (lokal = neu),
		setTestmail: (status, fehler) => (testmail = { status, fehler }),
		jetzt: () => '2026-10-17T05:00:00.000Z'
	});
	return { aktionen, aufrufe, lokal: () => lokal, testmail: () => testmail };
}

const warte = () => new Promise((r) => setTimeout(r, 0));

describe('AC-4: "Verstanden" schickt NUR onboarding_dismissed', () => {
	test('PUT /api/auth/profile {onboarding_dismissed:true}; lokal dismissed', async () => {
		const a = aufbau();
		a.aktionen.verstanden();
		await warte();
		assert.deepEqual(a.aufrufe, [
			{ methode: 'put', pfad: '/api/auth/profile', body: { onboarding_dismissed: true } }
		]);
		assert.deepEqual(a.lokal(), { dismissed: true });
	});
});

describe('AC-5: "Ausblenden" schickt NUR checklist_dismissed', () => {
	test('PUT /api/auth/profile {checklist_dismissed:true}; lokal checklistDismissed', async () => {
		const a = aufbau();
		a.aktionen.ausblenden();
		await warte();
		assert.deepEqual(a.aufrufe, [
			{ methode: 'put', pfad: '/api/auth/profile', body: { checklist_dismissed: true } }
		]);
		assert.deepEqual(a.lokal(), { checklistDismissed: true });
	});
	test('Fehlschlag des PUT: Hinweis bleibt stehen (kein lokaler Override)', async () => {
		const a = aufbau({ putWirft: true });
		a.aktionen.ausblenden();
		a.aktionen.verstanden();
		await warte();
		assert.deepEqual(a.lokal(), {});
	});
});

describe('AC-8: Testmail gilt nur bei status "ok" als gesendet', () => {
	test('status ok => Datum lokal gesetzt, Status idle', async () => {
		const a = aufbau({ post: { status: 'ok', channel: 'email' } });
		await a.aktionen.sendeTestmail();
		assert.deepEqual(a.aufrufe, [
			{ methode: 'post', pfad: '/api/notify/test', body: { channel: 'email' } }
		]);
		assert.equal(a.lokal().testMailSentAt, '2026-10-17T05:00:00.000Z');
		assert.deepEqual(a.testmail(), { status: 'idle', fehler: null });
	});
	test('HTTP 200 mit {error} => KEIN Datum, Status error mit Fehlertext des Core', async () => {
		const a = aufbau({ post: { error: 'Postfach unbekannt' } });
		await a.aktionen.sendeTestmail();
		assert.equal(a.lokal().testMailSentAt, undefined, 'Testmail darf nicht als gesendet gelten');
		assert.deepEqual(a.testmail(), { status: 'error', fehler: 'Postfach unbekannt' });
	});
	test('HTTP 200 ohne status und ohne error => KEIN Datum, Katalog-Fehlertext', async () => {
		const a = aufbau({ post: {} });
		await a.aktionen.sendeTestmail();
		assert.equal(a.lokal().testMailSentAt, undefined);
		assert.deepEqual(a.testmail(), { status: 'error', fehler: 'T(onboarding.testmail.fehler)' });
	});
	test('leere Antwort (null) => KEIN Datum', async () => {
		const a = aufbau({ post: null });
		await a.aktionen.sendeTestmail();
		assert.equal(a.lokal().testMailSentAt, undefined);
		assert.equal(a.testmail().status, 'error');
	});
	test('geworfene API-Ausnahme => Status error mit detail, KEIN Datum', async () => {
		const a = aufbau({ werfe: { detail: 'Limit erreicht' } });
		await a.aktionen.sendeTestmail();
		assert.equal(a.lokal().testMailSentAt, undefined);
		assert.deepEqual(a.testmail(), { status: 'error', fehler: 'Limit erreicht' });
	});
});
