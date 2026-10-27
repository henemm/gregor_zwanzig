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

import { test, describe, mock } from 'node:test';
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

// Fix-Loop 1 (#2361, F001): "Testmail senden" laeuft ueber notify/test, das der
// Go-Proxy bis 120 s offen haelt. Hier geht der Klick durch den ECHTEN
// `api.post`/`send()` (Netzgrenze ist nur fetch) — das Budget wird dort
// geprueft, wo es wirkt: an der Aufrufstelle. Die Uhr wird mit `mock.timers`
// gestellt; der Default ist auf 20 ms gesenkt, damit ein fehlendes Budget
// sofort auffaellt.
const apiModul = (await import(
	pathToFileURL(path.resolve(HERE, '..', '..', '..', 'lib', 'api.ts')).href
)) as typeof import('../../../lib/api.ts');

describe('#2361 F001: Testmail traegt das notify/test-Budget (130 s)', () => {
	const flush = () => new Promise((r) => setImmediate(r));

	/** fetch-Ersatz: antwortet nach `nachMs` (null = nie), lehnt bei Abbruch ab. */
	function installiere(nachMs: number | null): { pfade: string[]; restore: () => void } {
		const echt = globalThis.fetch;
		const pfade: string[] = [];
		(globalThis as { fetch: unknown }).fetch = (input: unknown, init?: RequestInit) => {
			pfade.push(String(input));
			return new Promise<Response>((resolve, reject) => {
				init?.signal?.addEventListener(
					'abort',
					() => reject(new DOMException('The operation was aborted.', 'AbortError')),
					{ once: true }
				);
				if (nachMs !== null) {
					setTimeout(
						() =>
							resolve(
								new Response(JSON.stringify({ status: 'ok', channel: 'email' }), {
									status: 200,
									headers: { 'Content-Type': 'application/json' }
								})
							),
						nachMs
					);
				}
			});
		};
		return { pfade, restore: () => ((globalThis as { fetch: unknown }).fetch = echt) };
	}

	function aufbauEcht() {
		let lokal: Record<string, unknown> = {};
		let testmail: { status: string; fehler: string | null } = { status: 'idle', fehler: null };
		const aktionen = erzeugeOnboardingAktionen({
			api: apiModul.api,
			t: (k) => `T(${k})`,
			getLokal: () => lokal,
			setLokal: (neu) => (lokal = neu),
			setTestmail: (status, fehler) => (testmail = { status, fehler }),
			jetzt: () => '2026-10-17T05:00:00.000Z'
		});
		return { aktionen, lokal: () => lokal, testmail: () => testmail };
	}

	async function mitGestellterUhr(nachMs: number | null, ablauf: (n: ReturnType<typeof installiere>) => Promise<void>) {
		const altesWindow = (globalThis as { window?: unknown }).window;
		(globalThis as { window?: unknown }).window = new EventTarget();
		apiModul.setzeStandardZeitlimit(20);
		const netz = installiere(nachMs);
		mock.timers.enable({ apis: ['setTimeout'] });
		try {
			await ablauf(netz);
		} finally {
			mock.timers.reset();
			netz.restore();
			apiModul.setzeStandardZeitlimit(apiModul.STANDARD_ZEITLIMIT_MS);
			(globalThis as { window?: unknown }).window = altesWindow;
		}
	}

	test('Antwort nach 60 s (weit ueber dem Standard-Limit) => Testmail gilt als gesendet', async () => {
		await mitGestellterUhr(60_000, async (netz) => {
			const a = aufbauEcht();
			const laeuft = a.aktionen.sendeTestmail();
			await flush();
			mock.timers.tick(60_000);
			await laeuft;
			assert.deepEqual(netz.pfade, ['/api/notify/test']);
			assert.deepEqual(a.testmail(), { status: 'idle', fehler: null });
			assert.equal(a.lokal().testMailSentAt, '2026-10-17T05:00:00.000Z');
		});
	});

	test('keine Antwort => laeuft bis 130 s, erst dann Fehler', async () => {
		await mitGestellterUhr(null, async () => {
			const a = aufbauEcht();
			const laeuft = a.aktionen.sendeTestmail();
			await flush();
			mock.timers.tick(129_999);
			await flush();
			assert.equal(a.testmail().status, 'loading', 'die Testmail wurde vor 130 s abgebrochen');
			mock.timers.tick(1);
			await laeuft;
			assert.equal(a.testmail().status, 'error');
			assert.equal(a.lokal().testMailSentAt, undefined);
		});
	});
});
