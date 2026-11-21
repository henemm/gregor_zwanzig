// TDD RED — Issue #3202 (Epic #2913): Kanalzeile im Reiter Zustellung nach Mockup Fassung 4.
// Spec: docs/specs/modules/feat_3202_kanalzeile_mockup.md — AC-1, AC-2, AC-3, AC-4, AC-5, AC-6 (Kern-Schicht;
// Nutzersicht im Browser, Staging-Abgleich und Zwei-Nutzer-Lauf folgen in den E2E-Specs).
// PO-Entscheidungen 20./21.11.2026: Telegram nur „verbunden“ (kein Name, nie Chat-ID); keine Empfängerzahl
// (auch nicht im Orts-Vergleich); Kürzung E-Mail `lokalteil@…`, Telefon `+<Landesvorwahl> <3 Ziffern> …`; Premium ohne Rückadresse.
//
// Vertrag (shared/zustellung-tab/zustellungModell.ts):
//   adresseGekuerzt(mail: string): string     „henning@example.com“ -> „henning@…“; ohne „@“ oder leer -> ''
//   nummerGekuerzt(nr: string): string         „+491711234567“ -> „+49 171 …“; ohne „+“ erste 3 Ziffern + „ …“
//   kanalStatus(profil)  — keine Empfängerzahl (PO-Korrektur 21.11.2026, Spec v1.1 AC-2: preset.empfaenger
//       ist seit #1452 wirkungslos). Eine von außen mitgegebene Zahl darf keine Zeile verändern.
// Geprüft wird die SICHTBARE Statuszeile der echten KanalTabelle (Server-Render, svelte/server), gespeist aus
// dem echten kanalStatus und dem echten Katalog DE/EN — dort, wo die Zeile wirkt; entscheidend ist der Text,
// den der Nutzer liest.
// Alle Adressen und Nummern sind erfunden (example.com, Fantasienummern).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/shared/zustellung-tab/__tests__/feat3202_kanalzeile_mockup.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale } from '../../../../i18n/index.ts';
import { tripVoll, zustellungModell, type Json } from './zustellungTabDaten.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> zustellung-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
const KANAL_TABELLE = path.join(FRONTEND, 'src', 'lib', 'components', 'organisms', 'zustellung-tab', 'KanalTabelle.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

afterEach(() => locale.set('de'));

// ── Server-Render-Werkzeug ───────────────────────────────────────────────────

const text = (h: string) => h.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
function elementMitTestid(h: string, id: string): string | null {
	const m = h.match(new RegExp(`<([a-z]+)\\b[^>]*data-testid="${id}"[^>]*>`));
	if (!m) return null;
	const tag = m[1];
	const start = m.index!;
	let tiefe = 0;
	const re = new RegExp(`<(/?)${tag}\\b[^>]*>`, 'g');
	re.lastIndex = start;
	for (let x; (x = re.exec(h)); ) {
		tiefe += x[1] ? -1 : 1;
		if (tiefe === 0) return h.slice(start, x.index + x[0].length);
	}
	return null;
}

type Kanal = 'email' | 'telegram' | 'sms' | 'premium_sms';

/** Sichtbare Statuszeilen der echten KanalTabelle für ein Profil und eine Empfängerzahl. */
async function zeilen(profil: Json, empfaengerZusatz?: number): Promise<Record<Kanal, string>> {
	const m = await zustellungModell();
	const status = empfaengerZusatz === undefined ? m.kanalStatus(profil) : m.kanalStatus(profil, empfaengerZusatz);
	const stand = m.standAusTrip(tripVoll());
	const KanalTabelle = (await import(pathToFileURL(KANAL_TABELLE).href)).default;
	const h = render(KanalTabelle, { props: { stand, status, onaendern: () => {} } }).body.replace(/<!--[\s\S]*?-->/g, '');
	const aus = {} as Record<Kanal, string>;
	for (const k of ['email', 'telegram', 'sms', 'premium_sms'] as const) {
		const el = elementMitTestid(h, `zustellung-kanal-${k}-status`);
		assert.ok(el, `Statuszeile zustellung-kanal-${k}-status fehlt im Render`);
		aus[k] = text(el);
	}
	return aus;
}

// ── Erfundene Profile (GET /api/auth/profile) ────────────────────────────────

const MAIL = 'henning@example.com';
const NUMMER = '+491711234567';
const CHAT = '987654321';
const RUECKADRESSE = 'wanderer-3202@inreach.example.com';

/** Mockup-Zustand „normal“: alles verbunden, Premium-SMS-Rückadresse frisch. */
function profilNormal(over: Json = {}): Json {
	return {
		tier: 'premium',
		mail_to: MAIL,
		email_verified: true,
		telegram_chat_id: CHAT,
		sms_to: NUMMER,
		sms_allowed: true,
		sms_verified: true,
		premium_sms_allowed: true,
		premium_sms_reply_to: RUECKADRESSE,
		premium_sms_reply_at: '2026-11-01T18:04:00Z',
		premium_sms_reply_state: 'fresh',
		...over
	};
}

/** Mockup-Zustand „lücken“ wie die Ist-Erfassung (elementliste_abgleich_logik.ts lueckenProfil):
 *  Nummer unbestätigt (mit Leerzeichen eingetragen), Rückadresse verfallen, Telegram nicht verbunden. */
function profilLuecken(): Json {
	return profilNormal({
		telegram_chat_id: '',
		sms_to: '',
		sms_verified: false,
		pending_sms_to: '+49 171 0000000',
		premium_sms_reply_state: 'stale'
	});
}

async function fn(name: 'adresseGekuerzt' | 'nummerGekuerzt'): Promise<(s: string) => string> {
	const m = await zustellungModell();
	assert.equal(typeof m[name], 'function', `TDD RED: zustellungModell.ts exportiert ${name}() noch nicht`);
	return m[name];
}

// ── AC-3: reine Kürzungsfunktionen ───────────────────────────────────────────

describe('#3202 AC-3 adresseGekuerzt — Lokalteil + „@…“, nie Volltext, nie Fehler', () => {
	const faelle: [string, string][] = [
		['henning@example.com', 'henning@…'],
		['a@x.de', 'a@…'],
		['vorname.nachname+reise@example.org', 'vorname.nachname+reise@…'],
		['', ''],
		['ohne-klammeraffe.example.com', '']
	];
	for (const [ein, soll] of faelle) {
		test(`adresseGekuerzt(${JSON.stringify(ein)}) = ${JSON.stringify(soll)}`, async () => {
			const f = await fn('adresseGekuerzt');
			assert.equal(f(ein), soll);
		});
	}
});

describe('#3202 AC-3 nummerGekuerzt — „+<Landesvorwahl> <3 Ziffern> …“, nie Volltext, nie Fehler', () => {
	const faelle: [string, string][] = [
		['+491711234567', '+49 171 …'],
		['+49 171 0000000', '+49 171 …'],
		['+14155550123', '+1 415 …'],
		['+79161234567', '+7 916 …'],
		['+353871234567', '+353 871 …'],
		['+41 79 123 45 67', '+41 791 …'],
		['0171 1234567', '017 …'],
		['0171-1234567', '017 …'],
		['+4917', '+49 17 …'],
		['12', '12 …'],
		['', '']
	];
	for (const [ein, soll] of faelle) {
		test(`nummerGekuerzt(${JSON.stringify(ein)}) = ${JSON.stringify(soll)}`, async () => {
			const f = await fn('nummerGekuerzt');
			assert.equal(f(ein), soll);
		});
	}

	test('lange Nummern erscheinen nie im Volltext (auch nicht ihre Endziffern)', async () => {
		const f = await fn('nummerGekuerzt');
		for (const nr of ['+491711234567', '+14155550123', '+353871234567', '0171 1234567']) {
			const aus = f(nr);
			assert.ok(aus.endsWith(' …'), `${nr} -> ${aus}: endet nicht auf „ …“`);
			assert.ok(!aus.replace(/\D/g, '').endsWith(nr.replace(/\D/g, '').slice(-4)), `${nr} -> ${aus}: Endziffern sichtbar`);
		}
	});
});

// ── AC-1/AC-5: Normalzustand, Trip (kein Empfängerzusatz) ────────────────────

describe('#3202 AC-1/AC-5 Kanalzeile Normalzustand im Trip (DE)', () => {
	test('E-Mail „bestätigt · henning@…“ ohne volle Adresse und ohne Empfängerzusatz', async () => {
		const z = await zeilen(profilNormal());
		assert.equal(z.email, 'bestätigt · henning@…');
	});

	test('SMS „bestätigt · +49 171 …“ ohne volle Nummer', async () => {
		const z = await zeilen(profilNormal());
		assert.equal(z.sms, 'bestätigt · +49 171 …');
	});

	test('Telegram nur „verbunden“, nie die Chat-ID', async () => {
		const z = await zeilen(profilNormal());
		assert.equal(z.telegram, 'verbunden');
	});

	test('Telegram: auch das Modell trägt die Chat-ID nicht mehr als Ziel', async () => {
		const m = await zustellungModell();
		const t = m.kanalStatus(profilNormal()).telegram;
		assert.ok(!String(t.ziel).includes(CHAT), `Chat-ID im Ziel: ${t.ziel}`);
	});

	test('AC-5 Premium-SMS frisch: nur Status, ohne Rückadresse', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilNormal()).premium_sms;
		const z = await zeilen(profilNormal());
		assert.ok(z.premium_sms.startsWith('inReach · Rückadresse gelernt'), z.premium_sms);
		assert.equal(z.premium_sms, st.statusText, 'hinter dem Premium-Status darf nichts angehängt sein');
		assert.ok(!z.premium_sms.includes(RUECKADRESSE) && !z.premium_sms.includes('@'), `Rückadresse sichtbar: ${z.premium_sms}`);
	});
});

// ── AC-4: Lücken-Zustand ─────────────────────────────────────────────────────

describe('#3202 AC-4 Kanalzeile Zustand „Lücken“ (DE)', () => {
	test('SMS „unbestätigt · +49 171 …“', async () => {
		const z = await zeilen(profilLuecken());
		assert.equal(z.sms, 'unbestätigt · +49 171 …');
	});

	test('Premium „inReach · Rückadresse verfallen“ ohne Rückadresse', async () => {
		const z = await zeilen(profilLuecken());
		assert.equal(z.premium_sms, 'inReach · Rückadresse verfallen');
	});

	test('Telegram „nicht verbunden“', async () => {
		const z = await zeilen(profilLuecken());
		assert.equal(z.telegram, 'nicht verbunden');
	});
});

// ── AC-1/AC-3: SMS im Tarif gesperrt — Nummer trotzdem gekürzt (Adversary F002) ─

describe('#3202 SMS ohne Tarif (sms_allowed false): Ziel gekürzt, nie Volltext', () => {
	const gesperrt = () => profilNormal({ sms_allowed: false, sms_to: '+491719876543', sms_verified: true });

	test('DE: „nicht verbunden · +49 171 …“ im Modell und in der sichtbaren Zeile', async () => {
		const m = await zustellungModell();
		assert.equal(m.kanalStatus(gesperrt()).sms.ziel, '+49 171 …');
		const z = await zeilen(gesperrt());
		assert.equal(z.sms, 'nicht verbunden · +49 171 …');
		assert.ok(!z.sms.includes('9876543'), z.sms);
	});

	test('EN: „not connected · +49 171 …“', async () => {
		locale.set('en');
		const z = await zeilen(gesperrt());
		assert.equal(z.sms, 'not connected · +49 171 …');
	});
});

// ── AC-2: keine Empfängerzahl, nirgends (PO-Korrektur 21.11.2026) ────────────
// `preset.empfaenger` ist seit #1452 wirkungslos (versendet wird nur an die Konto-Adresse); eine Zahl wäre falsch.

describe('#3202 AC-2 keine Empfängerzahl in Trip und Orts-Vergleich', () => {
	test('auch wenn ein Aufrufer eine Empfängerzahl mitgibt, bleibt die E-Mail-Zeile „bestätigt · henning@…“', async () => {
		const ohne = await zeilen(profilNormal());
		const mit = await zeilen(profilNormal(), 2);
		assert.equal(ohne.email, 'bestätigt · henning@…');
		assert.deepEqual(mit, ohne, 'eine mitgegebene Zahl darf keine Zeile verändern');
		for (const z of Object.values(mit)) assert.ok(!/Empfänger|\+\d+ /.test(z.replace('+49 171 …', '')), `Empfängerzahl sichtbar: ${z}`);
	});

	test('der Kanalstatus hängt nur am Profil, nicht am Kontext (Trip und Orts-Vergleich gleich)', async () => {
		const m = await zustellungModell();
		assert.equal(m.kanalStatus.length, 1, 'kanalStatus nimmt nur das Profil, keinen Empfänger-Parameter');
		assert.equal(typeof m.zusaetzlicheEmpfaenger, 'undefined', 'kein Empfänger-Zähler im Modell (toter Code)');
	});
});

// ── AC-6: Englisch aus dem Katalog, Adressen und Nummern unübersetzt ─────────

describe('#3202 AC-6 Kanalzeile Englisch', () => {
	test('Normalzustand EN: „confirmed · henning@…“, „confirmed · +49 171 …“, „connected“', async () => {
		locale.set('en');
		const z = await zeilen(profilNormal());
		assert.equal(z.email, 'confirmed · henning@…');
		assert.equal(z.sms, 'confirmed · +49 171 …');
		assert.equal(z.telegram, 'connected');
		assert.ok(!z.premium_sms.includes(RUECKADRESSE), z.premium_sms);
	});

	test('Lücken EN: „unconfirmed · +49 171 …“, „inReach · reply address expired“, „not connected“', async () => {
		locale.set('en');
		const z = await zeilen(profilLuecken());
		assert.equal(z.sms, 'unconfirmed · +49 171 …');
		assert.equal(z.premium_sms, 'inReach · reply address expired');
		assert.equal(z.telegram, 'not connected');
	});

	test('EN: E-Mail-Zeile ohne Empfängerzahl, auch bei mitgegebener Zahl', async () => {
		locale.set('en');
		const z = await zeilen(profilNormal(), 2);
		assert.equal(z.email, 'confirmed · henning@…');
		assert.ok(!/recipient|Empfänger/i.test(Object.values(z).join(' ')), JSON.stringify(z));
	});
});
