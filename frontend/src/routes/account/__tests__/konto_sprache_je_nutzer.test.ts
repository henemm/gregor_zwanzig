// Issue #2653 (i18n F4, Epic #2644) — AC-1, AC-2, AC-3, AC-6: die Konto-Seite
// spricht die Sprache des angemeldeten Nutzers. Echter SSR-Render
// (svelte/server, Pruefstand f4KontoAdminNavSsr.ts) mit fester Zeit-Fixture:
//   * AC-6: Deutsch ist byte-gleich zur Ausgabe VOR der Umstellung
//     (tests/golden/f4_konto_admin_nav/*.de.html: Konto, Admin, Navigation),
//   * AC-1: zwei Nutzer (en/de) nacheinander durch die ECHTEN Loader
//     (+layout.server.ts fuer die Sprache, account/+page.server.ts fuer die Daten),
//   * AC-2: Fehlertexte (Loeschen, Profil, Code) in beiden Sprachen,
//   * AC-3: „Zuletzt: …" der Scheduler-Karte (timeAgo) mit Plural.
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en: eine
// Mutation tr()/$t -> trFor('de', …) macht ihn rot. Englische Anker sind als
// feste Literale festgeschrieben (nicht nur gegen den eigenen Katalog).
// Spec: docs/specs/modules/i18n_f4_konto_admin_nav_2653.md
//
//   cd frontend && npm test -- src/routes/account/__tests__/konto_sprache_je_nutzer.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import {
	FAELLE,
	GOLDEN_DIR,
	locale,
	trFor,
	trnFor,
	schreibeGolden,
	kontoRendern,
	kontoDaten,
	profil,
	vorMinuten,
	layoutLoad,
	mitApi,
	cookiesFuer
} from '../../__tests__/f4KontoAdminNavSsr.ts';
import { ROUTES, teilbaum } from '../../__tests__/onboardingSsr.ts';
import { deutscheReste, sichtbarerText, attributText } from '../../__tests__/f3Sprachpruefung.ts';
import { F4_ANKER } from '../../__tests__/f4KatalogAnker.ts';
import { readdirSync } from 'node:fs';

const { profileSaveErrorMessage } = await import(pathToFileURL(path.join(ROUTES, 'account/profileSaveError.ts')).href);
const { deleteErrorText } = await import(pathToFileURL(path.join(ROUTES, 'account/deleteErrorText.ts')).href);
const { passwortAendernErrorMessage } = await import(pathToFileURL(path.join(ROUTES, 'account/passwortAendernError.ts')).href);
const kontoLoad = (await import(pathToFileURL(path.join(ROUTES, 'account/+page.server.ts')).href)).load;

before(() => {
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') schreibeGolden('en');
});
afterEach(() => locale.set('de'));

// Einzige Normalisierung: jede Leerraumfolge wird EIN Leerzeichen (mehrzeilige
// Fliesstexte standen vorher mit Zeilenumbruch+Tabs im Markup; HTML stellt
// beides gleich dar). Jedes andere Zeichen ist byte-gleich.
const leerraum = (s: string) => s.replace(/\s+/g, ' ');

describe('AC-6: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			locale.set('en');
			FAELLE[fall]('en');
			locale.set('de');
			assert.equal(leerraum(FAELLE[fall]('de') + '\n'), leerraum(golden));
		});
	}
	test('Messaufbau: Golden enthaelt die deutschen Texte und Zaehler', () => {
		const alle = Object.keys(FAELLE).map((f) => readFileSync(path.join(GOLDEN_DIR, `${f}.de.html`), 'utf-8')).join('');
		for (const s of ['Mein Konto', 'SMS-Kontingent (heute)', '4 von 4', 'vor 3 Min', 'Benutzt von karl am', 'Orts-Vergleich', 'Dunkles Design', 'Kanäle &amp; Empfänger'])
			assert.ok(alle.includes(s), s);
	});
});

/** de rendern, dann ohne Neuladen auf en schalten und erneut rendern. */
function enNachDe(f: () => string): string {
	locale.set('de');
	f();
	locale.set('en');
	return f();
}
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: "${teil}"\n${text}`);
const wort = (w: string) => new RegExp(`(^|[^A-Za-zÄÖÜäöüß])${w}([^A-Za-zÄÖÜäöüß]|$)`);

describe('Konto-Seite auf Englisch (de -> en ohne Neuladen)', () => {
	// „ohne Metriken" ist die Beschreibung einer Vorlage aus der API (Daten, kein UI-Text).
	const html = () => enNachDe(() => kontoRendern(kontoDaten())).replace('ohne Metriken', '');

	test('kein deutscher Katalogtext (konto.*, nav.*) im sichtbaren Text oder in Attributen', () => {
		const h = html();
		// „Standard" ist als Tier-Name Eigenname (TIER_LABELS); das Profil-Badge pruefen die Anker.
		const ohneTier = (r: string[]) => r.filter((x) => x !== 'konto.wetter_profile.standard: Standard');
		assert.deepEqual(ohneTier(deutscheReste(sichtbarerText(h), ['konto.', 'nav.', 'aktionen.'])), []);
		assert.deepEqual(ohneTier(deutscheReste(attributText(h), ['konto.', 'nav.', 'aktionen.'])), []);
		assert.match(h, /data-testid="wetter-profile-default-mp1">Default</);
	});

	test('feste englische Anker (exakte Literale)', () => {
		const t = sichtbarerText(html());
		for (const s of [
			'My account',
			'Display name',
			'Member since 01/09/2026',
			'Channels',
			'Where should your weather reports be sent?',
			'Confirmation pending for neu@example.org . Until then, emails still go to golden@example.org .',
			'Mobile number (SMS)',
			'Connected (...321)',
			'Premium SMS link code',
			'Links your Garmin inReach device securely to your account.',
			'Renew code',
			'Created on 02/09/2026',
			'Last used on 20/10/2026',
			'Change password',
			'Weather profiles',
			'3 metrics',
			'1 metric',
			'Your reports',
			'Trip checks',
			'Next check: —',
			'Last: 3 min ago',
			'Last run failed: timeout',
			'Level change to Standard requested. The operator will review it.',
			'Active trips 1 of 5',
			'Active comparisons 0 of 3',
			'Locations 2 of 20',
			'SMS quota (today)',
			'SMS 3 of 10',
			'of which up to 8 briefings, 2 alert reserve',
			'Premium-SMS 4 of 4 (+2 replies)',
			'of which up to 3 briefings, 1 alert reserve',
			'Notifications',
			'Weather models',
			'Innsbruck → GeoSphere (Alpen)',
			'Ajaccio → OpenMeteo',
			'Availability',
			'System running',
			'Weather templates',
			'2 metrics',
			'Sign out on all devices',
			'Download data',
			'Danger zone',
			'Delete account'
		])
			hat(t, s);
		// Wortgrenze: kein deutsches Rest-Wort der Seite im englischen Text.
		for (const w of ['von', 'Speichern', 'Löschen', 'Konto', 'Kanäle', 'Zuletzt', 'davon', 'Antworten', 'Metriken', 'Std', 'Tag'])
			assert.doesNotMatch(t, wort(w), w);
	});

	test('Attribute: Platzhalter und aria-label englisch', () => {
		const h = html();
		hat(h, 'placeholder="e.g. you@email.com"');
		hat(h, 'placeholder="6-digit code"');
		hat(h, 'aria-label="Rename"');
		hat(h, 'aria-label="Delete"');
	});

	test('Plural der Antworten exakt: genau eine Antwort -> „(+1 reply)"', () => {
		const daten = kontoDaten({ smsDailyUsage: { sms: { used: 0, limit: 0, reserve: 0 }, premium_sms: { used: 5, limit: 4, reserve: 1 } } });
		const t = sichtbarerText(enNachDe(() => kontoRendern(daten)));
		hat(t, 'Premium-SMS 4 of 4 (+1 reply)');
		assert.doesNotMatch(t, /replies/);
		locale.set('de');
		hat(sichtbarerText(kontoRendern(daten)), 'Premium-SMS 4 von 4 (+1 Antworten)');
	});

	test('Leerzustaende englisch: keine Passkeys, keine Profile, keine Orte, kein Zeitplan', () => {
		const daten = kontoDaten({
			profile: profil({ passkeys: [], mail_to: '', telegram_chat_id: '' }),
			metricPresets: [],
			locations: [],
			scheduler: null,
			health: null,
			templates: []
		});
		const t = sichtbarerText(enNachDe(() => kontoRendern(daten)));
		for (const s of [
			'You have no passkey yet.',
			'You have not created any weather profiles yet.',
			'No locations yet — create one',
			'No notifications configured — set up',
			'Report schedule not available.',
			'Unreachable',
			'No templates available.',
			'Not connected',
			'Connect with Telegram'
		])
			hat(t, s);
		const h = enNachDe(() => kontoRendern(daten));
		assert.match(h, /<a href="\/locations"[^>]*>create one<\/a>/);
		assert.match(h, /<a href="\/account"[^>]*>set up<\/a>/);
	});
});

describe('AC-3: „Zuletzt" der Scheduler-Karte (timeAgo) in beiden Sprachen', () => {
	const FAELLE_ZEIT: [number, string, string][] = [
		[0, 'Zuletzt: gerade eben', 'Last: just now'],
		[3, 'Zuletzt: vor 3 Min', 'Last: 3 min ago'],
		[60, 'Zuletzt: vor 1 Std', 'Last: 1 h ago'],
		[120, 'Zuletzt: vor 2 Std', 'Last: 2 h ago'],
		[1440, 'Zuletzt: vor 1 Tag', 'Last: 1 day ago'],
		[2880, 'Zuletzt: vor 2 Tagen', 'Last: 2 days ago']
	];
	const zuletzt = (html: string) => {
		const m = /<span>((?:Zuletzt|Last): [^<]*)<\/span>/.exec(html);
		assert.ok(m, 'Zuletzt-Zeile fehlt');
		return m![1];
	};
	for (const [min, de, en] of FAELLE_ZEIT) {
		test(`${min} Minuten: „${de}" | „${en}"`, () => {
			const daten = kontoDaten({
				scheduler: { jobs: [{ id: 'trip_reports_hourly', next_run: null, last_run: { time: vorMinuten(min), status: 'ok' } }] }
			});
			locale.set('de');
			assert.equal(zuletzt(kontoRendern(daten)), de);
			assert.equal(zuletzt(enNachDe(() => kontoRendern(daten))), en);
		});
	}
});

describe('AC-2: Fehlertexte in der Nutzersprache, unbekannte Codes zeigen den Server-Text', () => {
	const fehler = (lang: 'de' | 'en', f: () => string) => {
		locale.set(lang);
		return f();
	};
	test('Loeschen: wrong_password', () => {
		const f = () => deleteErrorText({ error: 'wrong_password' }, 'x');
		assert.equal(fehler('de', f), 'Das Passwort ist falsch.');
		assert.equal(fehler('en', f), 'The password is wrong.');
	});
	test('Loeschen: invalid_code und rate_limit_exceeded haben eigene Saetze (nicht die des Profils)', () => {
		assert.equal(fehler('en', () => deleteErrorText({ error: 'invalid_code' }, 'x')), 'The code is wrong, expired or already used.');
		assert.equal(fehler('en', () => deleteErrorText({ error: 'rate_limit_exceeded' }, 'x')), 'Too many attempts. Please wait a few minutes.');
		assert.equal(fehler('de', () => deleteErrorText({ error: 'mail_failed' }, 'x')), 'Der Code konnte nicht verschickt werden. Bitte später erneut versuchen.');
	});
	test('Loeschen: unbekannter Code -> Server-Text (detail, dann error, dann Ersatz)', () => {
		assert.equal(fehler('en', () => deleteErrorText({ error: 'boom', detail: 'Server sagt nein' }, 'x')), 'Server sagt nein');
		assert.equal(fehler('en', () => deleteErrorText({ error: 'boom' }, 'x')), 'boom');
		assert.equal(fehler('en', () => deleteErrorText({}, trFor('en', 'konto.aktion.loeschen_fehlgeschlagen'))), 'Deleting failed');
	});
	test('Profil: email_taken (409)', () => {
		const f = () => profileSaveErrorMessage(409, { error: 'email_taken' });
		assert.equal(fehler('de', f), 'Diese E-Mail-Adresse wird bereits von einem anderen Konto verwendet.');
		assert.equal(fehler('en', f), 'This email address is already used by another account.');
	});
	test('Code anfordern: code_expired', () => {
		const f = () => profileSaveErrorMessage(400, { error: 'code_expired' });
		assert.equal(fehler('de', f), 'Der Bestätigungscode ist abgelaufen — bitte einen neuen anfordern.');
		assert.equal(fehler('en', f), 'The verification code has expired. Please request a new one.');
	});
	test('Profil: unbekannter Code -> Server-Text, ohne alles -> Ersatztext der Sprache', () => {
		assert.equal(fehler('en', () => profileSaveErrorMessage(500, { detail: 'irgendein Detail' })), 'irgendein Detail');
		assert.equal(fehler('en', () => profileSaveErrorMessage(400, { error: 'validation failed' })), 'validation failed');
		assert.equal(fehler('en', () => profileSaveErrorMessage(500, {})), 'Saving failed');
		assert.equal(fehler('de', () => profileSaveErrorMessage(500, {})), 'Speichern fehlgeschlagen');
	});
	test('Passwort aendern: wrong_password und Ersatz', () => {
		assert.equal(fehler('en', () => passwortAendernErrorMessage({ code: 'wrong_password' })), 'The current password is wrong');
		assert.equal(fehler('de', () => passwortAendernErrorMessage({ code: 'wrong_password' })), 'Aktuelles Passwort ist falsch');
		assert.equal(fehler('en', () => passwortAendernErrorMessage(undefined)), 'Changing the password failed');
	});
});

describe('AC-1: zwei Nutzer, zwei Sprachen, gleiche Zahlen, getrennte Daten', () => {
	const API_ANNA = {
		'/api/auth/profile': profil({ id: 'anna', display_name: 'Anna', mail_to: 'anna@example.org', email: 'anna@example.org', language: 'en', pending_contact_address: '' }),
		'/api/trips': [{ id: 't1' }, { id: 't2' }],
		'/api/locations': [{ id: 'l1', name: 'Annas Ort', lat: 47.2, lon: 11.4 }],
		'/api/auth/sms-daily-usage': { sms: { used: 3, limit: 10, reserve: 2 }, premium_sms: { used: 1, limit: 4, reserve: 1 } }
	};
	const API_BERT = {
		...API_ANNA,
		'/api/auth/profile': profil({ id: 'bert', display_name: 'Bert', mail_to: 'bert@example.org', email: 'bert@example.org', language: 'de', pending_contact_address: '' }),
		'/api/locations': [{ id: 'l2', name: 'Berts Ort', lat: 47.2, lon: 11.4 }]
	};
	const API = { A: API_ANNA, B: API_BERT };

	/** Echter Layout-Loader (Sprache) und echter Konto-Loader (Daten) fuer eine Sitzung. */
	async function seiteFuer(sitzung: 'A' | 'B'): Promise<{ lang: string; html: string }> {
		const { lang, data } = await mitApi(API, async () => {
			const layout = await layoutLoad({ locals: { userId: sitzung, lang: 'de' }, cookies: cookiesFuer(sitzung) } as never);
			const data = await kontoLoad({ cookies: cookiesFuer(sitzung) } as never);
			return { lang: layout.lang, data };
		});
		locale.set(lang);
		return { lang, html: kontoRendern(data) };
	}
	const zahlen = (html: string) =>
		['quota-trips', 'quota-compare-presets', 'quota-locations'].map((id) => /<a [^>]*data-testid="[^"]*"[^>]*>([^<]*)</.exec(teilbaum(html, id)!)![1].match(/\d+/g)!.join('/')).join(' ') +
		' | ' + (sichtbarerText(teilbaum(html, 'sms-daily-usage')!).match(/\d+/g) ?? []).join('/');

	test('A englisch, B deutsch; Kontingent-/Zaehlerwerte identisch; keine fremden Daten', async () => {
		locale.set('de');
		const a = await seiteFuer('A');
		const b = await seiteFuer('B');
		assert.equal(a.lang, 'en');
		assert.equal(b.lang, 'de');
		const ta = sichtbarerText(a.html);
		const tb = sichtbarerText(b.html);
		for (const s of ['My account', 'SMS quota (today)', 'Active trips 2 of 5', 'SMS 3 of 10', 'Weather models']) hat(ta, s);
		for (const s of ['Mein Konto', 'SMS-Kontingent (heute)', 'Aktive Trips 2 von 5', 'SMS 3 von 10', 'Wetter-Modelle']) hat(tb, s);
		assert.deepEqual(deutscheReste(ta, ['konto.']).filter((x) => x !== 'konto.wetter_profile.standard: Standard'), []);
		assert.doesNotMatch(tb, /My account|SMS quota/);
		assert.equal(zahlen(a.html), zahlen(b.html));
		assert.equal(zahlen(a.html), '2/5 0/3 1/20 | 3/10/8/2/1/4/3/1');
		hat(ta, 'anna@example.org');
		hat(ta, 'Annas Ort');
		assert.ok(!ta.includes('bert') && !ta.includes('Berts Ort'), 'A sieht Daten von B');
		hat(tb, 'Berts Ort');
		assert.ok(!tb.includes('anna') && !tb.includes('Annas Ort'), 'B sieht Daten von A');
	});
});

describe('F001: jeder F4-Katalogwert ist als festes de/en-Literal verankert', () => {
	/** Platzhalter des Literals (<name>) werden als Parameter `<name>` eingesetzt. */
	const params = (literal: string) =>
		Object.fromEntries([...literal.matchAll(/<([a-z0-9_]+)>/g)].map((m) => [m[1], `<${m[1]}>`]));
	for (const [k, de, en] of F4_ANKER) {
		test(k, () => {
			assert.equal(trFor('de', k, params(de)), de, `de ${k}`);
			assert.equal(trFor('en', k, params(en)), en, `en ${k}`);
		});
	}

	test('statischer Gegencheck: Anker-Tabelle == Schluessel von konto/admin/nav (de und en)', () => {
		const MSG = path.join(ROUTES, '..', 'lib', 'i18n', 'messages');
		for (const lang of ['de', 'en']) {
			const dateien = readdirSync(path.join(MSG, lang)).filter((d) => ['konto.json', 'admin.json', 'nav.json'].includes(d));
			assert.equal(dateien.length, 3);
			const schluessel = dateien.flatMap((d) => Object.keys(JSON.parse(readFileSync(path.join(MSG, lang, d), 'utf-8'))));
			assert.deepEqual([...schluessel].sort(), F4_ANKER.map(([k]) => k).sort(), `${lang}: Schluessel ohne Anker oder Anker ohne Schluessel`);
		}
		assert.equal(new Set(F4_ANKER.map(([k]) => k)).size, F4_ANKER.length, 'doppelte Anker');
	});

	test('F002: Plural exakt — „vor 1 Std" | „1 h ago", „vor 1 Tag" | „1 day ago"', () => {
		assert.equal(trnFor('de', 'konto.zeit.vor_stunden', 1), 'vor 1 Std');
		assert.equal(trnFor('en', 'konto.zeit.vor_stunden', 1), '1 h ago');
		assert.equal(trnFor('en', 'konto.zeit.vor_tagen', 1), '1 day ago');
		assert.equal(trnFor('en', 'konto.zeit.vor_tagen', 3), '3 days ago');
	});
});
