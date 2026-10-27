// TDD RED — Onboarding S2: Startseite zeigt Willkommen und Startklar-Checkliste
// nur neu Angelegten, und „+ Neuer Vergleich" fuehrt auf /compare/new.
// Spec docs/specs/modules/onboarding_willkommen_checkliste.md — AC-2, AC-3, AC-5,
// AC-14 (Verdrahtung), AC-15 (Render), AC-16, AC-8 (Datum in der Checkliste).
//
// Gemessen wird ECHT (keine Mocks): `load()` aus +layout.server.ts mit ersetzter
// Netzgrenze `fetch`, die echte +page.svelte und die echte StartklarCheckliste.svelte
// serverseitig gerendert (svelte/server). Die reine Logik bewacht
// _home/__tests__/onboarding_sichtbarkeit_zustandsmatrix.test.ts; HIER wird
// bewiesen, dass Loader -> Seite -> Bausteine sie auch WIRKLICH verwenden.
//
// Vertrag an die Implementierung (zusaetzlich zu onboardingSichtbarkeit.ts):
//   * +layout.server.ts liefert `onboarding: OnboardingProfil` (immer vorhanden,
//     fail-closed), gebildet aus DEMSELBEN einen Profilabruf.
//   * +page.svelte liest `data.onboarding` und rendert
//       - Willkommen:  data-testid="onboarding-willkommen"  (nur wenn zeigeWillkommen)
//         darin: Link /trips/new, Link /compare/new,
//                Knopf data-testid="onboarding-testmail-senden",
//                Knopf data-testid="onboarding-willkommen-verstanden"
//       - Checkliste:  <StartklarCheckliste profil tripCount compareCount />
//         (nur wenn zeigeCheckliste)
//   * StartklarCheckliste.svelte (frontend/src/routes/_home/), Props
//       { profil: OnboardingProfil; tripCount: number; compareCount: number }
//     Wurzel data-testid="startklar-checkliste"; je Punkt
//       data-testid="startklar-punkt-<id>" data-pflicht="true|false" data-erledigt="true|false"
//     (<id> aus email | trip-oder-vergleich | erstes-briefing | testmail | telegram);
//     Testmail mit Datum: Text onboarding.checkliste.testmail_gesendet + Datum TT.MM.JJJJ,
//     ohne Datum: Knopf data-testid="startklar-testmail-senden";
//     Tarif-Hinweise data-testid="startklar-hinweis-sms" / "startklar-hinweis-premium-sms";
//     Knopf data-testid="startklar-ausblenden".
//
// Ausfuehren:
//   cd frontend && npm test -- src/routes/__tests__/startseite_onboarding_render.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import {
	ROUTES,
	CHECKLISTE_DATEI,
	render,
	ladeKomponente,
	renderStartseite,
	teilbaum,
	links,
	sichtbar,
	text,
	profilNeu,
	onboardingNeu,
	aktiverVergleich,
	kuenftigerTrip,
	ohneKommentare
} from './onboardingSsr.ts';

const { load } = (await import(pathToFileURL(path.join(ROUTES, '+layout.server.ts')).href)) as any;
const Checkliste = await ladeKomponente(CHECKLISTE_DATEI);

const WILLKOMMEN = 'onboarding-willkommen';
const CHECKLISTE = 'startklar-checkliste';

// ─── Netzgrenze: Profilabruf je Sitzung ──────────────────────────────────────
const PROFIL_JE_SITZUNG: Record<string, Record<string, unknown>> = {
	'sess-neu': profilNeu(),
	'sess-alt': { id: 'alt-1', display_name: 'Alt', role: 'user', email_verified: false, sms_allowed: false },
	'sess-voll': profilNeu({
		onboarding_dismissed: true,
		checklist_dismissed: true,
		test_mail_sent_at: '2026-10-16T10:00:00Z',
		first_briefing_at: '2026-10-17T05:00:00Z',
		email_verified: true,
		telegram_chat_id: '4711',
		sms_allowed: true,
		premium_sms_allowed: true
	})
};
let abrufe: string[] = [];
async function fetchDouble(input: any, init?: any) {
	abrufe.push(String(input));
	const sitzung = String(init?.headers?.Cookie ?? '').replace('gz_session=', '');
	const profil = PROFIL_JE_SITZUNG[sitzung];
	if (!profil) return { ok: false, status: 401, json: async () => ({}) };
	return { ok: true, status: 200, json: async () => profil };
}
let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});
const loadFor = async (sitzung: string, userId: string | null = 'x') => {
	abrufe = [];
	return load({ locals: { userId }, cookies: { get: () => sitzung } });
};

describe('AC-2: +layout.server.ts reicht die Onboarding-Felder aus dem EINEN Profilabruf durch', () => {
	test('neues Konto: onboarding.pending true, alles andere offen', async () => {
		const d = await loadFor('sess-neu');
		assert.deepEqual(d.onboarding, onboardingNeu());
		assert.equal(abrufe.length, 1, `genau ein Profilabruf erwartet, waren ${abrufe.length}`);
	});
	test('alle Felder werden uebernommen (inkl. Telegram, Tarif, Datumswerte)', async () => {
		const d = await loadFor('sess-voll');
		assert.deepEqual(d.onboarding, {
			pending: true,
			dismissed: true,
			checklistDismissed: true,
			testMailSentAt: '2026-10-16T10:00:00Z',
			firstBriefingAt: '2026-10-17T05:00:00Z',
			emailVerified: true,
			telegramVerknuepft: true,
			smsAllowed: true,
			premiumSmsAllowed: true
		});
		assert.equal(abrufe.length, 1);
	});
	test('Altkonto (Feld fehlt): onboarding.pending false', async () => {
		const d = await loadFor('sess-alt');
		assert.equal(d.onboarding?.pending, false);
	});
	test('Profilabruf scheitert (401): fail-closed, pending false', async () => {
		const d = await loadFor('unbekannt');
		assert.equal(d.onboarding?.pending, false);
	});
	test('ausgeloggt: kein Abruf, onboarding vorhanden und pending false', async () => {
		const d = await loadFor('sess-neu', null);
		assert.equal(abrufe.length, 0);
		assert.equal(d.onboarding?.pending, false);
	});
	test('Bestandsfelder bleiben erhalten (displayName, isAdmin, passkeyPromptDismissed)', async () => {
		const d = await loadFor('sess-neu');
		assert.equal(d.displayName, 'Neu');
		assert.equal(d.isAdmin, false);
		assert.equal(d.passkeyPromptDismissed, false);
	});
});

describe('AC-2/AC-3: Startseite rendert Willkommen und Checkliste nur fuer neu Angelegte', () => {
	test('Kette Loader -> Seite: neues Konto ohne Trips/Vergleiche sieht Willkommen UND Checkliste', async () => {
		const layout = await loadFor('sess-neu');
		const html = renderStartseite({ ...layout, trips: [], presets: [] });
		assert.ok(teilbaum(html, WILLKOMMEN), 'Willkommens-Hinweis (data-testid="onboarding-willkommen") fehlt');
		assert.ok(teilbaum(html, CHECKLISTE), 'Startklar-Checkliste (data-testid="startklar-checkliste") fehlt');
	});
	test('Kette Loader -> Seite: Altkonto mit offenen Pflichtpunkten sieht weder noch', async () => {
		const layout = await loadFor('sess-alt');
		const html = renderStartseite({ ...layout, trips: [], presets: [] });
		assert.equal(teilbaum(html, WILLKOMMEN), null, 'Altkonto sieht den Willkommens-Hinweis');
		assert.equal(teilbaum(html, CHECKLISTE), null, 'Altkonto sieht die Checkliste');
		// Der normale Leerzustand bleibt (Bestand), nur ohne Onboarding.
		assert.ok(teilbaum(html, 'empty-state'), 'Leerzustand fuer Altkonten verschwunden');
	});
	test('Seite ohne onboarding-Daten (alter Loader-Stand) zeigt nichts davon', () => {
		const html = renderStartseite({ trips: [], presets: [] });
		assert.equal(teilbaum(html, WILLKOMMEN), null);
		assert.equal(teilbaum(html, CHECKLISTE), null);
	});
	test('Willkommen erklaert Gregor, bietet Testmail und Anlegen von Trip/Ortsvergleich', () => {
		const html = renderStartseite({ onboarding: onboardingNeu(), trips: [], presets: [] });
		const w = teilbaum(html, WILLKOMMEN);
		assert.ok(w, 'Willkommens-Hinweis fehlt');
		assert.ok(sichtbar(w!).includes(text('onboarding.willkommen.text')), 'Erklaertext (was Gregor macht) fehlt');
		assert.ok(teilbaum(w!, 'onboarding-testmail-senden'), 'Knopf "Testmail senden" fehlt');
		assert.ok(teilbaum(w!, 'onboarding-willkommen-verstanden'), 'Knopf "Verstanden" fehlt');
		const ziele = links(w!).map((l) => l.href);
		assert.ok(ziele.includes('/trips/new'), `kein Link auf /trips/new im Willkommen: ${ziele}`);
		assert.ok(ziele.includes('/compare/new'), `kein Link auf /compare/new im Willkommen: ${ziele}`);
	});
	test('mit einem Trip: kein Willkommen, Checkliste weiter sichtbar (Pflichtpunkt Trip erledigt)', () => {
		const html = renderStartseite({ onboarding: onboardingNeu(), trips: [kuenftigerTrip()], presets: [] });
		assert.equal(teilbaum(html, WILLKOMMEN), null, 'Willkommen trotz vorhandenem Trip');
		const c = teilbaum(html, CHECKLISTE);
		assert.ok(c, 'Checkliste fehlt trotz offener Pflichtpunkte');
		assert.match(teilbaum(c!, 'startklar-punkt-trip-oder-vergleich') ?? '', /data-erledigt="true"/);
	});
	test('nur ein Ortsvergleich: kein Willkommen, Pflichtpunkt Trip-oder-Vergleich erledigt', () => {
		const html = renderStartseite({ onboarding: onboardingNeu(), trips: [], presets: [aktiverVergleich()] });
		assert.equal(teilbaum(html, WILLKOMMEN), null, 'Willkommen trotz vorhandenem Ortsvergleich');
		const c = teilbaum(html, CHECKLISTE);
		assert.ok(c, 'Checkliste fehlt');
		assert.match(teilbaum(c!, 'startklar-punkt-trip-oder-vergleich') ?? '', /data-erledigt="true"/);
	});
	test('"Verstanden" gesetzt: Willkommen weg, Checkliste bleibt', () => {
		const html = renderStartseite({ onboarding: onboardingNeu({ dismissed: true }), trips: [], presets: [] });
		assert.equal(teilbaum(html, WILLKOMMEN), null);
		assert.ok(teilbaum(html, CHECKLISTE));
	});
});

describe('AC-5/AC-14: Seite blendet die Checkliste nach Profilstand aus', () => {
	test('AC-5: "Ausblenden" schlaegt offene Pflichtpunkte', () => {
		const html = renderStartseite({ onboarding: onboardingNeu({ checklistDismissed: true }), trips: [], presets: [] });
		assert.equal(teilbaum(html, CHECKLISTE), null);
	});
	test('AC-14: alle drei Pflichtpunkte erledigt, ohne Testmail/Telegram => Checkliste weg', () => {
		const o = onboardingNeu({ emailVerified: true, firstBriefingAt: '2026-10-17T05:00:00Z' });
		const html = renderStartseite({ onboarding: o, trips: [kuenftigerTrip()], presets: [] });
		assert.equal(teilbaum(html, CHECKLISTE), null);
	});
	test('AC-14: erstes Briefing offen => Checkliste sichtbar', () => {
		const o = onboardingNeu({ emailVerified: true, testMailSentAt: '2026-10-16T10:00:00Z', telegramVerknuepft: true });
		const html = renderStartseite({ onboarding: o, trips: [kuenftigerTrip()], presets: [] });
		assert.ok(teilbaum(html, CHECKLISTE));
	});
});

// ─── StartklarCheckliste.svelte direkt ──────────────────────────────────────
function renderCheckliste(profil: Record<string, unknown>, tripCount = 0, compareCount = 0): string {
	assert.ok(Checkliste, 'frontend/src/routes/_home/StartklarCheckliste.svelte existiert nicht');
	return ohneKommentare(render(Checkliste, { props: { profil, tripCount, compareCount } }).body);
}
function punkt(html: string, id: string): string {
	const p = teilbaum(html, `startklar-punkt-${id}`);
	assert.ok(p, `Checklistenpunkt ${id} fehlt`);
	return p!;
}

describe('StartklarCheckliste: Punkte, Stand, Knoepfe', () => {
	test('drei Pflicht-, zwei Info-Punkte mit data-pflicht/data-erledigt', () => {
		const html = renderCheckliste(onboardingNeu({ emailVerified: true }), 0, 1);
		assert.ok(teilbaum(html, CHECKLISTE), 'Wurzel data-testid="startklar-checkliste" fehlt');
		const erwartet: Record<string, [string, string]> = {
			email: ['true', 'true'],
			'trip-oder-vergleich': ['true', 'true'],
			'erstes-briefing': ['true', 'false'],
			testmail: ['false', 'false'],
			telegram: ['false', 'false']
		};
		for (const [id, [pflicht, erledigt]] of Object.entries(erwartet)) {
			const p = punkt(html, id);
			assert.match(p, new RegExp(`data-pflicht="${pflicht}"`), `${id}: data-pflicht`);
			assert.match(p, new RegExp(`data-erledigt="${erledigt}"`), `${id}: data-erledigt`);
		}
		assert.ok(teilbaum(html, 'startklar-ausblenden'), 'Knopf "Ausblenden" fehlt');
	});
	test('AC-8: Testmail gesendet => "Testmail gesendet am" + Datum, kein Senden-Knopf', () => {
		const html = renderCheckliste(onboardingNeu({ testMailSentAt: '2026-10-16T10:00:00Z' }));
		const p = punkt(html, 'testmail');
		assert.ok(sichtbar(p).includes(text('onboarding.checkliste.testmail_gesendet')), 'Text "Testmail gesendet am" fehlt');
		assert.match(sichtbar(p), /16\.10\.2026/, `Datum TT.MM.JJJJ fehlt: "${sichtbar(p)}"`);
		assert.equal(teilbaum(html, 'startklar-testmail-senden'), null, 'Senden-Knopf trotz gesendeter Testmail');
	});
	test('ohne Testmail-Datum: Knopf "Testmail senden"', () => {
		const html = renderCheckliste(onboardingNeu());
		const k = teilbaum(html, 'startklar-testmail-senden');
		assert.ok(k, 'Knopf data-testid="startklar-testmail-senden" fehlt');
		assert.ok(sichtbar(k!).includes(text('onboarding.checkliste.testmail_senden')));
	});
	test('Telegram verknuepft: Punkt erledigt, bleibt Info (data-pflicht=false)', () => {
		const p = punkt(renderCheckliste(onboardingNeu({ telegramVerknuepft: true })), 'telegram');
		assert.match(p, /data-pflicht="false"/);
		assert.match(p, /data-erledigt="true"/);
	});
});

describe('AC-15: SMS/Premium-SMS nur beim passenden Tarif (Render)', () => {
	const alleOnboardingTeile = (o: Record<string, unknown>) => {
		const html = renderStartseite({ onboarding: o, trips: [], presets: [] });
		return [teilbaum(html, WILLKOMMEN), teilbaum(html, CHECKLISTE)];
	};
	test('Tarif ohne SMS: weder Willkommen noch Checkliste erwaehnt SMS', () => {
		const [w, c] = alleOnboardingTeile(onboardingNeu());
		assert.ok(w && c, 'Willkommen/Checkliste fehlen — Messaufbau leer');
		assert.doesNotMatch(sichtbar(w! + c!), /SMS/);
		assert.equal(teilbaum(c!, 'startklar-hinweis-sms'), null);
		assert.equal(teilbaum(c!, 'startklar-hinweis-premium-sms'), null);
	});
	test('sms_allowed: SMS-Hinweis, kein Premium-SMS-Hinweis', () => {
		const [w, c] = alleOnboardingTeile(onboardingNeu({ smsAllowed: true }));
		assert.ok(c, 'Checkliste fehlt');
		const h = teilbaum(c!, 'startklar-hinweis-sms');
		assert.ok(h, 'SMS-Hinweis fehlt');
		assert.ok(sichtbar(h!).includes(text('onboarding.hinweis.sms')));
		assert.equal(teilbaum(c!, 'startklar-hinweis-premium-sms'), null);
		assert.doesNotMatch(sichtbar((w ?? '') + c!), /Premium-SMS/);
	});
	test('premium_sms_allowed: Premium-SMS-Hinweis, kein SMS-Hinweis', () => {
		const [, c] = alleOnboardingTeile(onboardingNeu({ premiumSmsAllowed: true }));
		assert.ok(c, 'Checkliste fehlt');
		const h = teilbaum(c!, 'startklar-hinweis-premium-sms');
		assert.ok(h, 'Premium-SMS-Hinweis fehlt');
		assert.ok(sichtbar(h!).includes(text('onboarding.hinweis.premium_sms')));
		assert.equal(teilbaum(c!, 'startklar-hinweis-sms'), null);
	});
	test('kein gerenderter Onboarding-Text sagt, ein Kanal ersetze einen anderen', () => {
		const [w, c] = alleOnboardingTeile(onboardingNeu({ smsAllowed: true, premiumSmsAllowed: true }));
		assert.ok(w && c, 'Willkommen/Checkliste fehlen — Messaufbau leer');
		assert.doesNotMatch(sichtbar(w! + c!), /ersetz|statt\s+(E-Mail|Telegram|SMS)|anstelle/i);
	});
});

// ─── AC-16: „+ Neuer Vergleich" -> /compare/new; Listen-Links bleiben /compare ──
describe('AC-16: Anlege-Links fuer Ortsvergleiche zeigen auf /compare/new', () => {
	const istAnlegeLink = (t: string) => /Neuer\s+(Orts-)?Vergleich/i.test(t);

	test('Kopfzeile: "+ Neuer Vergleich" fuehrt auf /compare/new', () => {
		const html = renderStartseite({ trips: [kuenftigerTrip()], presets: [] });
		const kopf = /<header data-slot="page-header"[\s\S]*?<\/header>/.exec(html)?.[0] ?? '';
		const l = links(kopf).filter((x) => istAnlegeLink(x.text));
		assert.equal(l.length, 1, `Kopfzeile: ${JSON.stringify(links(kopf))}`);
		assert.equal(l[0].href, '/compare/new');
	});
	test('Leerzustand (Altkonto, kein Onboarding): "+ Neuer Vergleich" fuehrt auf /compare/new', () => {
		const html = renderStartseite({ trips: [], presets: [] });
		const leer = teilbaum(html, 'empty-state');
		assert.ok(leer, 'Leerzustand fehlt');
		const l = links(leer!).filter((x) => istAnlegeLink(x.text));
		assert.ok(l.length >= 1, `kein Anlege-Link im Leerzustand: ${JSON.stringify(links(leer!))}`);
		for (const x of l) assert.equal(x.href, '/compare/new', `Leerzustand: ${x.text}`);
	});
	test('Willkommen (neues Konto): jeder Vergleich-Anlege-Link fuehrt auf /compare/new, keiner auf /compare', () => {
		const html = renderStartseite({ onboarding: onboardingNeu(), trips: [], presets: [] });
		for (const x of links(html).filter((y) => istAnlegeLink(y.text))) {
			assert.equal(x.href, '/compare/new', `${x.text} -> ${x.href}`);
		}
		// Unabhaengig vom Label: im Willkommen fuehrt kein Link auf die Liste.
		const w = teilbaum(html, WILLKOMMEN);
		assert.ok(w, 'Willkommens-Hinweis fehlt');
		assert.deepEqual(links(w!).filter((l) => l.href === '/compare'), [], 'Willkommen verlinkt /compare statt /compare/new');
	});
	// Offener Punkt (an team-lead gemeldet): die QuickAction „Neuer Orts-Vergleich"
	// (+page.svelte ~:739, Planungsmodus) ist ein Anlege-Link, steht aber nicht in
	// der Dateitabelle der Spec. Dieser Fall bewacht sie nach AC-16 („Aufruf-Knopf").
	test('Planungsmodus (kuenftiger Trip): Schnell-Anlegen "Neuer Orts-Vergleich" fuehrt auf /compare/new', () => {
		const html = renderStartseite({ trips: [kuenftigerTrip()], presets: [] });
		const l = links(html).filter((x) => istAnlegeLink(x.text));
		assert.ok(l.length >= 2, `Anlege-Links (Kopfzeile + Schnell anlegen) fehlen: ${JSON.stringify(l)}`);
		for (const x of l) assert.equal(x.href, '/compare/new', `${x.text} -> ${x.href}`);
	});
	test('Wächter: Listen-Links ("Alle …") fuehren weiter auf /compare', () => {
		const html = renderStartseite({ trips: [], presets: [aktiverVergleich('cmp-1'), aktiverVergleich('cmp-2')] });
		const liste = links(html).filter((x) => /^Alle\b/.test(x.text));
		assert.ok(liste.length >= 1, `kein Listen-Link gerendert — Messaufbau leer: ${JSON.stringify(links(html))}`);
		for (const x of liste) assert.equal(x.href, '/compare', `${x.text} -> ${x.href}`);
	});
});
