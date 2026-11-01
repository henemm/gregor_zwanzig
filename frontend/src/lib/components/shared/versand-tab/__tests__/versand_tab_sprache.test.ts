// Issue #2655 (i18n F6, Epic #2644) — AC-1, AC-2, AC-3, AC-4, AC-6: der geteilte
// Versand-Reiter (Trip UND Ortsvergleich, EIN Baustein) spricht die Sprache des
// angemeldeten Nutzers. Echte SSR-Renders (svelte/server, Pruefstand f6VersandSsr.ts):
//   * AC-6: Deutsch ist byte-gleich zur Ausgabe VOR der Umstellung
//     (tests/golden/f6_versand_tab/*.de.html und funktionen.de.txt),
//   * AC-1: beide Kontexte englisch, Kanalnamen unveraendert,
//   * AC-2: premiumSmsChannelState je Zustand in beiden Sprachen,
//   * AC-3: formatNextBriefing (pausiert, manuell, beendet, Termin, uebersprungen),
//   * AC-4: zwei Nutzer (en/de) durch den ECHTEN Layout-Loader (+layout.server.ts);
//     ersetzt ist nur die Netzgrenze (fetch je Sitzungs-Cookie).
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en: eine
// Mutation tr()/$t -> trFor('de', …) macht ihn rot. Englische und deutsche
// Texte sind als feste Literale verankert (f6KatalogAnker.ts).
// Spec: docs/specs/modules/i18n_f6_versand_tab_2655.md
//
//   cd frontend && npm test -- src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import {
	FRONTEND,
	GOLDEN_DIR,
	PROFILE,
	NB,
	locale,
	trFor,
	premiumSmsChannelState,
	sendTargetLabel,
	formatNextBriefing,
	baueReportConfigPayload,
	ladeReportZustand,
	kanaeleRendern,
	tabRendern,
	htmlFaelle,
	funktionsTabelle,
	schreibeGolden
} from './f6VersandSsr.ts';
import { F6_ANKER } from './f6KatalogAnker.ts';

const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'src/routes/admin/__tests__/server-load-resolve.hooks.mjs')).href, base);
const layoutLoad = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/+layout.server.ts')).href)).load;
const { sendConfirmModel } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/molecules/sendConfirmModel.ts')).href);

before(() => {
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') schreibeGolden('en');
});
afterEach(() => locale.set('de'));

// Einzige Normalisierung: jede Leerraumfolge wird EIN Leerzeichen (mehrzeilige
// Fliesstexte standen vorher mit Zeilenumbruch+Tabs im Markup). Sonst byte-gleich.
const leerraum = (s: string) => s.replace(/\s+/g, ' ');
const sichtbar = (html: string) =>
	leerraum(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&')).trim();
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: „${teil}"\nin: ${text}`);

/** Erst de rendern, dann OHNE Neuladen auf en schalten. */
function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const en = f();
	return { de, en };
}

/** Deutsche Festteile (>= 4 Buchstaben) der Paket-Schluessel, die im englischen Text stehen. */
function deutscheReste(text: string): string[] {
	const reste: string[] = [];
	for (const [k, de, en] of F6_ANKER) {
		if (de === en) continue;
		const enTeile = new Set(en.split(/<[a-z0-9_]+>/).map((s) => s.trim()));
		for (const teil of de.split(/<[a-z0-9_]+>/).map((s) => s.trim())) {
			if ((teil.match(/[A-Za-zÄÖÜäöüß]/g) ?? []).length < 4 || enTeile.has(teil)) continue;
			if (text.includes(teil)) reste.push(`${k}: ${teil}`);
		}
	}
	return reste;
}

describe('AC-6: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	const FAELLE = htmlFaelle();
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			const { de } = deDannEn(() => FAELLE[fall]());
			locale.set('de');
			assert.equal(leerraum(FAELLE[fall]() + '\n'), leerraum(golden));
			assert.equal(leerraum(de + '\n'), leerraum(golden));
		});
	}
	test('funktionen.de.txt: Funktionsergebnisse unveraendert (byte-gleich, ohne Normalisierung)', () => {
		const golden = readFileSync(path.join(GOLDEN_DIR, 'funktionen.de.txt'), 'utf-8');
		locale.set('en');
		funktionsTabelle();
		locale.set('de');
		assert.equal(funktionsTabelle() + '\n', golden);
	});
	test('Messaufbau: Golden enthaelt die deutschen Texte aller Bausteine', () => {
		const alle = Object.keys(FAELLE).map((f) => readFileSync(path.join(GOLDEN_DIR, `${f}.de.html`), 'utf-8')).join('');
		for (const s of ['Geplantes Briefing · Kanäle', 'Briefing-Zeitplan', 'Nächstes Briefing', 'Läuft mit der Trip', 'Bis auf Weiteres', 'Telegram im SMS-Kurzstil', 'Kein Kanal aktiv.', 'bald verfügbar', 'Mehrtages-Trend', 'zuletzt gemeldet am 20.09.2026'])
			assert.ok(alle.includes(s), s);
	});
});

describe('AC-1: Versand-Reiter englisch in Trip und Ortsvergleich, Kanalnamen unveraendert', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: erst de, dann ohne Neuladen en`, () => {
			const { de, en } = deDannEn(() => sichtbar(kanaeleRendern(context, PROFILE.alles_gekoppelt) + tabRendern(context)));
			for (const s of ['Geplantes Briefing · Kanäle', 'Morgen-Briefing', 'Nächstes Briefing', 'Briefing-Zeitplan', 'Laufzeit']) hat(de, s);
			for (const s of ['Planned briefing · channels', 'Morning briefing', 'Evening briefing', 'Next briefing', 'Briefing schedule', 'Duration', 'Active', 'Time', 'Morning 07:00', 'Evening 18:00'])
				hat(en, s);
			for (const s of ['Telegram (987654321)', 'SMS (+491511234567)', 'Premium-SMS (Garmin inReach) (+15551234567)', 'E-Mail (golden@example.org)']) {
				hat(de, s);
				hat(en, s);
			}
			hat(en, 'confirmed');
			hat(en, 'connected');
			hat(en, 'learned');
			hat(en, 'last reported on Tue 27 Oct');
			assert.deepEqual(deutscheReste(en), []);
		});
	}
	test('Trip: Einleitung, Unterzeilen, Trend, Laufzeit und Kurzstil-Schalter englisch', () => {
		const { en } = deDannEn(() => sichtbar(kanaeleRendern('route', PROFILE.alles_gekoppelt) + tabRendern('route')));
		hat(en, 'The trip briefing is a stage table — email carries all columns, Telegram the first 7, SMS has no grid, plain text.');
		hat(en, 'Layout · full table');
		hat(en, 'Layout · 7 columns');
		hat(en, 'Layout · no grid, 160 characters');
		hat(en, 'Telegram in SMS compact style');
		hat(en, 'Multi-day trend');
		hat(en, 'in the morning briefing');
		hat(en, 'Runs with the trip · ends 31.10.2026');
		hat(en, 'Open stages →');
	});
	test('Ortsvergleich: Einleitung, Zeitplan-Hinweis mit Hervorhebung, Laufzeit englisch', () => {
		const { en } = deDannEn(() => kanaeleRendern('vergleich', PROFILE.nur_email) + tabRendern('vergleich'));
		const text = sichtbar(en);
		hat(text, 'The location comparison is a wide table — in practice it goes by email. Telegram carries only ≤ 7 columns, SMS has no grid, plain text.');
		hat(text, 'Layout · no grid, 153 characters');
		hat(text, 'As with a trip: the Morning briefing shows today, the Evening briefing shows tomorrow. You only choose the time.');
		assert.match(en, /<strong[^>]*>Morning briefing<\/strong>/);
		hat(text, 'Until further notice');
		hat(text, 'Until a date');
		hat(text, 'Delivery continues without an end date.');
		hat(text, 'Premium SMS is available from the Premium level');
		hat(text, 'SMS is available from the Standard level');
		hat(text, 'Telegram chat ID missing — set it up in your account');
		assert.match(en, /Telegram chat ID missing — <a href="\/account">set it up in your account<\/a>/);
		assert.deepEqual(deutscheReste(text), []);
	});
	test('Sonderzustaende: kein Kanal, fehlende Adresse, Platzhalter, Kurzstil inaktiv', () => {
		const { en } = deDannEn(() => sichtbar(htmlFaelle().bausteine()));
		for (const s of [
			'No channel active. Turn on at least one briefing channel above to see schedule options here.',
			'Email address missing — set it up in your account',
			'Mobile number missing — set it up in your account',
			'Number not confirmed yet — enter the code in your account',
			'not confirmed',
			'entered, unconfirmed',
			'coming soon',
			'Only active when Telegram is switched on as a channel.',
			'The device has never reported in — the reply address is learned on first receipt.',
			'Runs with the trip · ends —',
			'Next briefing paused until Wed 28 Oct',
			'Next briefing Location comparison ended'
		])
			hat(en, s);
		assert.deepEqual(deutscheReste(en), []);
	});
});

describe('AC-2: Premium-SMS-Zustand je Sprache, disabled/tone sprachunabhaengig', () => {
	const ZUSTAENDE: [string, Record<string, unknown> | null, string, string, string, string][] = [
		['none', { premium_sms_allowed: true, premium_sms_reply_state: 'none' }, 'nicht verbunden', 'not connected', 'Das Gerät hat sich noch nie gemeldet — die Rückadresse wird beim ersten Empfang gelernt.', 'The device has never reported in — the reply address is learned on first receipt.'],
		['fresh', { premium_sms_allowed: true, premium_sms_reply_state: 'fresh' }, 'gelernt', 'learned', 'Das Gerät hat sich gemeldet — Briefings gehen an die gelernte Rückadresse.', 'The device has reported in — briefings go to the learned reply address.'],
		['stale', { premium_sms_allowed: true, premium_sms_reply_state: 'stale' }, 'verfallen', 'expired', 'Rückadresse verfallen — Garmin kann die Nummer inzwischen einem fremden Gerät zugeteilt haben. Sobald sich das Gerät wieder meldet, ist der Kanal erneut nutzbar.', 'Reply address expired — Garmin may have assigned the number to another device by now. As soon as the device reports in again, the channel can be used again.'],
		['ohne Tarif', { premium_sms_allowed: false, premium_sms_reply_state: 'fresh' }, 'nicht verfügbar', 'not available', 'Premium-SMS ab Level Premium verfügbar', 'Premium SMS is available from the Premium level']
	];
	for (const [name, p, deStatus, enStatus, deHint, enHint] of ZUSTAENDE) {
		test(name, () => {
			const { de, en } = deDannEn(() => premiumSmsChannelState(p));
			assert.equal(de.statusLabel, deStatus);
			assert.equal(de.hint, deHint);
			assert.equal(en.statusLabel, enStatus);
			assert.equal(en.hint, enHint);
			assert.equal(en.disabled, de.disabled);
			assert.equal(en.tone, de.tone);
		});
	}
	test('Meldedatum: de TT.MM.JJJJ, en „Thu 30 Oct" ohne Jahr (Annahme A2)', () => {
		const p = { premium_sms_allowed: true, premium_sms_reply_state: 'fresh', premium_sms_reply_at: '2026-10-30T09:00:00Z', premium_sms_reply_to: '+1555' };
		const { de, en } = deDannEn(() => premiumSmsChannelState(p));
		assert.equal(de.reportedAtLabel, 'zuletzt gemeldet am 30.10.2026');
		assert.equal(en.reportedAtLabel, 'last reported on Fri 30 Oct');
		assert.equal(en.contactLabel, ' (+1555)');
		assert.equal(de.contactLabel, en.contactLabel);
	});
});

describe('AC-3: formatNextBriefing in beiden Sprachen', () => {
	const FAELLE: [string, 'route' | 'vergleich', string, string][] = [
		['pausiert_bis', 'route', 'pausiert bis 28.10.', 'paused until Wed 28 Oct'],
		['pausiert', 'route', 'pausiert', 'paused'],
		['manuell', 'route', 'nur manueller Versand', 'manual delivery only'],
		['beendet', 'route', 'Trip beendet', 'Trip ended'],
		['beendet', 'vergleich', 'Ortsvergleich beendet', 'Location comparison ended'],
		['abgeschaltet', 'route', 'Briefings abgeschaltet', 'Briefings switched off'],
		['kein_termin', 'vergleich', 'kein Termin geplant', 'no time scheduled'],
		['termin', 'route', 'Mi 07:00 (CEST)', 'Wed 07:00 (CEST)'],
		['uebersprungen', 'route', 'Mi 07:00 (CEST) — Do 07:00 wird übersprungen', 'Wed 07:00 (CEST) — Thu 07:00 is skipped'],
		['ueberfaellig', 'vergleich', 'Mi 07:00 (CET) — läuft jetzt / wird nachgeholt', 'Wed 07:00 (CET) — running now / will be caught up'],
		['kaputt', 'route', '—', '—'],
		['nicht_geladen', 'route', '—', '—']
	];
	for (const [fall, context, de, en] of FAELLE) {
		test(`${fall} (${context})`, () => {
			const r = deDannEn(() => formatNextBriefing(NB[fall], context));
			assert.equal(r.de, de);
			assert.equal(r.en, en);
		});
	}
	test('alle sieben Wochentage je Sprache (zonenfrei aus local_date)', () => {
		const tage = ['2026-10-25', '2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31'];
		const { de, en } = deDannEn(() => tage.map((d) => formatNextBriefing({ at: 'x', local_date: d, local_time: '07:00', tz_abbr: 'CET' })).join(' | '));
		assert.equal(de, ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'].map((w) => `${w} 07:00 (CET)`).join(' | '));
		assert.equal(en, ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((w) => `${w} 07:00 (CET)`).join(' | '));
	});
});

describe('AC-4: zwei Nutzer, zwei Sprachen, eigene Kanaele, gleiche report_config', () => {
	const ANNA = { ...PROFILE.alles_gekoppelt, id: 'anna', mail_to: 'anna@example.org', telegram_chat_id: '111222333', sms_to: '', sms_verified: false, premium_sms_allowed: false, language: 'en' };
	const BERT = { id: 'bert', mail_to: 'bert@example.org', email_verified: true, sms_allowed: false, premium_sms_allowed: false, language: 'de' };
	const API: Record<string, Record<string, unknown>> = { A: { '/api/auth/profile': ANNA }, B: { '/api/auth/profile': BERT } };

	/** Ersetzt nur die Netzgrenze: `fetch` antwortet je Sitzungs-Cookie mit eigenen Daten (sonst 404). */
	async function mitApi<T>(lauf: () => Promise<T>): Promise<T> {
		const echt = globalThis.fetch;
		globalThis.fetch = (async (u: string, init?: { headers?: Record<string, string> }) => {
			const sitzung = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
			const daten = API[sitzung]?.[new URL(String(u)).pathname];
			return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200 });
		}) as unknown as typeof fetch;
		try {
			return await lauf();
		} finally {
			globalThis.fetch = echt;
		}
	}
	const cookies = (s: string) => ({ get: (n: string) => (n === 'gz_session' ? s : undefined) });

	/** Echter Layout-Loader (Sprache) + Profil der Sitzung → Reiter, Sende-Dialog, Nutzlast. */
	async function sichtFuer(sitzung: 'A' | 'B') {
		const { lang, profil } = await mitApi(async () => {
			const layout = await layoutLoad({ locals: { userId: sitzung, lang: 'de' }, cookies: cookies(sitzung) } as never);
			const profil = await (await fetch('http://core/api/auth/profile', { headers: { Cookie: `gz_session=${sitzung}` } })).json();
			return { lang: layout.lang as 'de' | 'en', profil };
		});
		locale.set(lang);
		const kanaele = { send_telegram: true, send_sms: true, send_premium_sms: true };
		const zustand = { ...ladeReportZustand({ send_email: true, send_telegram: true, morning_time: '07:00:00' }), telegram_style: 'rich' };
		return {
			lang,
			text: sichtbar(kanaeleRendern('route', profil) + tabRendern('route')),
			ziel: sendTargetLabel(profil, kanaele).text,
			dialog: sendConfirmModel('trip', profil, kanaele).beschreibung,
			nutzlast: baueReportConfigPayload({ live: { send_email: true }, zustand })
		};
	}

	test('A englisch mit Telegram, B deutsch nur E-Mail; keine fremden Kanaele; Nutzlast gleich', async () => {
		locale.set('de');
		const a = await sichtFuer('A');
		const b = await sichtFuer('B');
		assert.equal(a.lang, 'en');
		assert.equal(b.lang, 'de');
		assert.equal(a.ziel, 'Goes to E-Mail (anna@example.org) · Telegram.');
		assert.equal(a.dialog, a.ziel);
		assert.equal(b.ziel, 'Geht an E-Mail (bert@example.org).');
		assert.equal(b.dialog, b.ziel);
		hat(a.text, 'Planned briefing · channels');
		hat(a.text, 'Telegram (111222333)');
		hat(a.text, 'connected');
		hat(b.text, 'Geplantes Briefing · Kanäle');
		hat(b.text, 'E-Mail (bert@example.org)');
		assert.ok(!a.text.includes('bert') && !a.ziel.includes('bert'), 'A sieht Daten von B');
		assert.ok(!b.text.includes('anna') && !b.text.includes('111222333') && !b.ziel.includes('Telegram'), 'B sieht Daten/Kanaele von A');
		assert.deepEqual(deutscheReste(a.text), []);
		assert.deepEqual(a.nutzlast, b.nutzlast);
		assert.equal(JSON.stringify(a.nutzlast), JSON.stringify(b.nutzlast));
	});

	test('Sende-Ziel-Saetze der Sperrfaelle in beiden Sprachen', () => {
		const faelle: [Record<string, unknown> | null, string, string][] = [
			[null, 'Versandziel unbekannt — das Konto-Profil ist nicht verfügbar; es wird nichts gesendet.', 'Delivery target unknown — the account profile is not available; nothing is sent.'],
			[{}, 'Im Konto ist keine E-Mail-Adresse hinterlegt — es kann nichts gesendet werden.', 'No email address is set in the account — nothing can be sent.'],
			[{ mail_to: 'a@example.org' }, 'Die Adresse a@example.org ist nicht bestätigt — es wird nichts zugestellt.', 'The address a@example.org is not confirmed — nothing is delivered.']
		];
		for (const [p, de, en] of faelle) {
			const r = deDannEn(() => sendTargetLabel(p, null));
			assert.equal(r.de.text, de);
			assert.equal(r.en.text, en);
			assert.equal(r.en.gesperrt, true);
			assert.equal(r.de.gesperrt, true);
		}
		const alles = deDannEn(() => sendTargetLabel(PROFILE.alles_gekoppelt, { send_telegram: true, send_sms: true, send_premium_sms: true }).text);
		assert.equal(alles.en, 'Goes to E-Mail (golden@example.org) · Telegram · SMS · Premium-SMS.');
	});
});

describe('Anker: jeder F6-Katalogwert ist als festes de/en-Literal verankert', () => {
	/** Platzhalter des Literals (<name>) werden als Parameter `<name>` eingesetzt. */
	const params = (literal: string) =>
		Object.fromEntries([...literal.matchAll(/<([a-z0-9_]+)>/g)].map((m) => [m[1], `<${m[1]}>`]));
	for (const [k, de, en] of F6_ANKER) {
		test(k, () => {
			assert.equal(trFor('de', k, params(de)), de, `de ${k}`);
			assert.equal(trFor('en', k, params(en)), en, `en ${k}`);
		});
	}

	test('statischer Gegencheck: Anker-Tabelle == Schluessel von versand.json + telegram_kurzstil.* (de und en)', () => {
		const MSG = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');
		for (const lang of ['de', 'en']) {
			const lade = (d: string) => Object.keys(JSON.parse(readFileSync(path.join(MSG, lang, d), 'utf-8')));
			const schluessel = [...lade('versand.json'), ...lade('bausteine.json').filter((k) => k.startsWith('telegram_kurzstil.'))];
			assert.deepEqual([...schluessel].sort(), F6_ANKER.map(([k]) => k).sort(), `${lang}: Schluessel ohne Anker oder Anker ohne Schluessel`);
		}
		assert.equal(new Set(F6_ANKER.map(([k]) => k)).size, F6_ANKER.length, 'doppelte Anker');
	});
});
