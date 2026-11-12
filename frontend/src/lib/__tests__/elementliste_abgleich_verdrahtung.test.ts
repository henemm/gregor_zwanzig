// Issue #2913, Fix-Loop 1 (Adversary F002, F003) — Verdrahtung des Staging-Abgleichs ohne Browser.
// Die Staging-Spec ruft nur diese Funktionen; hier werden sie mit echten Daten (echte elementliste.json,
// echtes Dateisystem, echter Config-Ladevorgang im Unterprozess) geprüft.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, existsSync, writeFileSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
	planeAbgleich,
	routenPlan,
	herstellungsGrund,
	seitenPfad,
	bewerteAbschnitt,
	alleNichtPruefbar,
	baueBericht,
	schreibeBericht,
	abschluss,
	flagsAlsUmgebung,
	loginAusEnvText,
	leseSprache,
	DATEN_ABRUF,
	type ListenElement
} from '../../../e2e/elementliste_abgleich_logik.ts';
import { starterUmgebung, PLAYWRIGHT_ARGS } from '../../../../scripts/elementliste_abgleich.ts';

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const LISTE: ListenElement[] = JSON.parse(readFileSync(join(FRONTEND, '..', 'docs/context/einstellungen_neu/elementliste.json'), 'utf8')).elemente;
const PROD = 'https://gregor20.henemm.com';
const STAGING = 'https://staging.gregor20.henemm.com';

const el = (id: string, abschnitt: string, ordnung: number, text_de: string, extra: Partial<ListenElement> = {}): ListenElement => ({
	id,
	ctx: 'trip',
	reiter: 'wetter',
	zustand: 'normal',
	segment: null,
	abschnitt,
	ordnung,
	rolle: 'text',
	text_de,
	muster: null,
	i18n_key: null,
	text_en: null,
	luecke: true,
	...extra
});

describe('F002: planeAbgleich — Prod-Schutz, Optionen, Scope, Kombinationen (vor jedem Seitenaufruf)', () => {
	test('Prod-Base-URL wirft, Staging läuft', () => {
		assert.throws(() => planeAbgleich({ liste: LISTE, env: {}, baseURL: PROD }), /PRODUKTION/);
		assert.equal(planeAbgleich({ liste: LISTE, env: {}, baseURL: STAGING }).baseURL, STAGING);
	});
	test('ohne Base-URL gilt Staging (nie still Prod)', () => {
		assert.equal(planeAbgleich({ liste: LISTE, env: {}, baseURL: undefined }).baseURL, STAGING);
	});
	test('ohne Scope: alle Elemente der echten Liste, jede Kombination genau einmal', () => {
		const p = planeAbgleich({ liste: LISTE, env: {}, baseURL: STAGING });
		assert.equal(p.elemente.length, LISTE.length);
		assert.equal(p.kombis.reduce((s, k) => s + k.el.length, 0), LISTE.length);
		const keys = p.kombis.map(({ k }) => [k.ctx, k.reiter, k.zustand, k.segment].join('|'));
		assert.equal(new Set(keys).size, keys.length);
		assert.deepEqual(p.optionen, { strict: false, scope: null, abnahme: false });
	});
	test('Scope aus der Umgebung filtert; Strict und Sprache werden übernommen', () => {
		const p = planeAbgleich({ liste: LISTE, env: { ELEMENTLISTE_SCOPE: 'wetter/normal', ELEMENTLISTE_STRICT: '1', ELEMENTLISTE_SPRACHE: 'en' }, baseURL: STAGING });
		assert.ok(p.elemente.length > 0 && p.elemente.every((e) => e.reiter === 'wetter' && e.zustand === 'normal'));
		assert.equal(p.optionen.strict, true);
		assert.equal(p.sprache, 'en');
	});
	test('unbekannter Scope bzw. Sprache ⇒ Fehler, kein leerer grüner Lauf', () => {
		assert.throws(() => planeAbgleich({ liste: LISTE, env: { ELEMENTLISTE_SCOPE: 'gibtsnicht' }, baseURL: STAGING }));
		assert.throws(() => leseSprache({ ELEMENTLISTE_SPRACHE: 'fr' }));
	});
});

describe('F002: Route-Abfangen-Plan je Zustand — nie still übersprungen', () => {
	test('normal ohne Eingriff, lädt hängt, Ladefehler 500, unbekannter Zustand nicht herstellbar mit Grund', () => {
		assert.deepEqual(routenPlan('normal'), { art: 'keiner' });
		const l = routenPlan('laedt');
		assert.equal(l.art, 'haengen');
		const f = routenPlan('fehler');
		assert.ok(f.art === 'fehler' && f.status === 500);
		const x = routenPlan('irgendwas');
		assert.ok(x.art === 'nicht_herstellbar' && x.grund.includes('irgendwas'));
	});
	// Fix-Loop 2 (Adversary F009, AC-13): „Konto mit Lücken“ wird per Route-Abfangen hergestellt, nicht ausgewichen.
	test('Konto mit Lücken: Routenplan fängt nur lesende Konto-Abrufe (GET) ab, Navigation im Browser', () => {
		const u = routenPlan('luecken');
		assert.equal(u.art, 'konto_luecken');
		if (u.art !== 'konto_luecken') return;
		assert.equal(u.methode, 'GET');
		assert.equal(u.navigation, 'browser');
		for (const url of ['https://staging.gregor20.henemm.com/api/auth/profile', '/api/auth/profile?x=1', '/trips/abc/__data.json?x-sveltekit-invalidated=01', '/compare/v1/__data.json']) {
			assert.ok(u.muster.test(url), url);
		}
		for (const url of ['/api/auth/login', '/api/auth/logout', '/api/auth/profilebild', '/api/trips', '/trips/abc', '/api/metrics']) {
			assert.ok(!u.muster.test(url), url);
		}
	});
	test('Konto mit Lücken: Profil-Antwort ⇒ Telegram fehlt, SMS unbestätigt, Premium-SMS-Rückadresse verfallen, E-Mail bleibt', () => {
		const u = routenPlan('luecken');
		assert.equal(u.art, 'konto_luecken');
		if (u.art !== 'konto_luecken') return;
		const echt = { mail_to: 'a@example.com', email_verified: true, telegram_chat_id: '4711', sms_to: '+49 170 1', sms_verified: true, premium_sms_reply_state: 'fresh', display_name: 'Prüfer' };
		const r = u.ersetze('https://staging.gregor20.henemm.com/api/auth/profile', JSON.stringify(echt));
		assert.equal(r.geaendert, true);
		const p = JSON.parse(r.text);
		assert.equal(p.telegram_chat_id, '');
		assert.equal(p.sms_to, '+49 170 1');
		assert.equal(p.sms_verified, false);
		assert.equal(p.premium_sms_allowed, true);
		assert.equal(p.premium_sms_reply_state, 'stale');
		assert.ok(p.premium_sms_reply_to);
		assert.equal(p.mail_to, 'a@example.com');
		assert.equal(p.email_verified, true);
		assert.equal(p.display_name, 'Prüfer');
		// ohne Profil (null) entsteht trotzdem ein Lücken-Profil
		assert.equal(JSON.parse(u.ersetze('/api/auth/profile', 'null').text).premium_sms_reply_state, 'stale');
		// fremde URL bleibt unverändert
		assert.deepEqual(u.ersetze('/api/metrics', '{"a":1}'), { text: '{"a":1}', geaendert: false });
	});
	test('Konto mit Lücken: Seitendaten (__data.json, devalue-Format) ⇒ profile umgelenkt, alles andere unverändert', async () => {
		const { stringify, unflatten } = await import('devalue');
		const seite = { trip: { id: 't1', name: 'Hütte', datum: new Date('2026-11-10T00:00:00Z') }, etag: '"e1"', profile: { mail_to: 'a@example.com', telegram_chat_id: '4711', sms_verified: true, quota: { trips: 3 }, telegram_kopie: '4711' } };
		const layout = { lang: 'de', istAdmin: false };
		const text =
			JSON.stringify({ type: 'data', nodes: [{ type: 'data', data: JSON.parse(stringify(layout)), uses: {} }, { type: 'skip' }, { type: 'data', data: JSON.parse(stringify(seite)), uses: { params: ['id'] } }] }) +
			'\n{"type":"chunk","id":1}';
		const u = routenPlan('luecken');
		if (u.art !== 'konto_luecken') throw new Error('kein konto_luecken-Plan');
		const r = u.ersetze('https://staging.gregor20.henemm.com/trips/t1/__data.json?x-sveltekit-invalidated=01', text);
		assert.equal(r.geaendert, true);
		const [kopf, folge] = r.text.split('\n');
		assert.equal(folge, '{"type":"chunk","id":1}', 'Nachlieferungen bleiben unverändert');
		const wurzel = JSON.parse(kopf);
		assert.deepEqual(unflatten(wurzel.nodes[0].data), layout, 'Knoten ohne profile unverändert');
		assert.deepEqual(wurzel.nodes[1], { type: 'skip' });
		const neu = unflatten(wurzel.nodes[2].data) as typeof seite & { profile: Record<string, unknown> };
		assert.deepEqual(wurzel.nodes[2].uses, { params: ['id'] });
		assert.deepEqual(neu.trip, seite.trip);
		assert.equal(neu.etag, seite.etag);
		assert.equal(neu.profile.telegram_chat_id, '');
		assert.equal(neu.profile.sms_verified, false);
		assert.equal(neu.profile.premium_sms_reply_state, 'stale');
		assert.equal(neu.profile.mail_to, 'a@example.com');
		assert.deepEqual(neu.profile.quota, { trips: 3 }, 'verschachtelte Profilwerte bleiben');
		assert.equal(neu.profile.telegram_kopie, '4711', 'geteilte Werte (gleicher Index) werden nicht verändert');
		// Seitendaten ohne profile: unverändert, nicht als hergestellt gezählt
		const ohne = JSON.stringify({ type: 'data', nodes: [{ type: 'data', data: JSON.parse(stringify(layout)) }] });
		assert.deepEqual(u.ersetze('/trips/t1/__data.json', ohne), { text: ohne, geaendert: false });
		assert.deepEqual(u.ersetze('/trips/t1/__data.json', 'kein json'), { text: 'kein json', geaendert: false });
	});
	test('Konto mit Lücken: ohne abgefangenen Konto-Abruf ⇒ nicht_pruefbar mit konkretem Grund, sonst geprüft', () => {
		const u = routenPlan('luecken');
		assert.match(herstellungsGrund(u, 0) ?? '', /Konto mit Lücken nicht hergestellt.*\/api\/auth\/profile/);
		assert.equal(herstellungsGrund(u, 1), null);
		assert.equal(herstellungsGrund(routenPlan('normal'), 0), null);
		assert.equal(herstellungsGrund(routenPlan('fehler'), 0), null);
	});
	test('das Abfang-Muster trifft die Datenabrufe, nicht Login oder Seiten', () => {
		for (const u of ['/api/metrics', '/api/compare/metrics', '/api/compare/presets', '/api/trips/abc/weather']) assert.ok(DATEN_ABRUF.test(u), u);
		for (const u of ['/api/auth/login', '/trips/abc', '/api/trips']) assert.ok(!DATEN_ABRUF.test(u), u);
	});
	test('jeder Zustand der echten Liste hat einen Plan', () => {
		for (const z of new Set(LISTE.map((e) => e.zustand))) assert.ok(routenPlan(z).art !== undefined);
		assert.notEqual(routenPlan('fehler').art, 'keiner');
	});
	test('Seitenpfade je Kontext', () => {
		assert.equal(seitenPfad('trip', 't1', 'wetter'), '/trips/t1?tab=wetter');
		assert.equal(seitenPfad('orte', 'v 1', 'orte'), '/compare/v%201?tab=orte');
	});
});

describe('F002: Bewertung je Abschnitt', () => {
	const liste = [el('a', 'kopf', 1, 'Wetter'), el('b', 'kopf', 2, 'Zustellung'), el('c', 'kopf', 3, '9 von 13 Metriken', { muster: '{zahl} von {zahl} Metriken' })];
	test('mit Abschnitt-Haken und richtiger Reihenfolge ⇒ gefunden (Muster greift)', () => {
		const r = bewerteAbschnitt(liste, { marker: true, texte: ['Wetter', 'x', 'Zustellung', '4 von 9 Metriken'] }, 'de', 'kopf');
		assert.deepEqual([...r.values()].map((e) => e.status), ['gefunden', 'gefunden', 'gefunden']);
	});
	test('ohne Abschnitt-Haken ⇒ abweichend, nie gefunden', () => {
		const r = bewerteAbschnitt(liste, { marker: false, texte: ['Wetter', 'Zustellung', '4 von 9 Metriken'] }, 'de', 'kopf');
		assert.ok([...r.values()].every((e) => e.status === 'abweichend' && e.grund?.includes('data-abschnitt')));
	});
	test('falsche Reihenfolge bzw. fehlender Text ⇒ abweichend mit Grund', () => {
		const r = bewerteAbschnitt(liste.slice(0, 2), { marker: true, texte: ['Zustellung', 'Wetter'] }, 'de', 'kopf');
		assert.equal(r.get('a')?.status, 'gefunden');
		assert.equal(r.get('b')?.grund, 'Reihenfolge im Abschnitt');
		const leer = bewerteAbschnitt(liste.slice(0, 1), { marker: true, texte: [] }, 'de', 'kopf');
		assert.equal(leer.get('a')?.grund, 'Text nicht sichtbar');
	});
	test('Script-Abschnitt ohne Haken ⇒ nicht_pruefbar mit Grund; EN-Lücke ⇒ nicht_pruefbar', () => {
		const s = bewerteAbschnitt([el('k', 'kebab-menue', 1, 'Archivieren …')], { marker: false, texte: ['Archivieren …'] }, 'de', 'kebab-menue');
		assert.ok(s.get('k')?.status === 'nicht_pruefbar' && s.get('k')?.grund);
		const en = bewerteAbschnitt([el('e', 'kopf', 1, 'Zustellung')], { marker: true, texte: ['Delivery'] }, 'en', 'kopf');
		assert.equal(en.get('e')?.status, 'nicht_pruefbar');
		const enTreffer = bewerteAbschnitt([el('e', 'kopf', 1, 'Zustellung', { luecke: false, text_en: 'Delivery', i18n_key: 'x' })], { marker: true, texte: ['Delivery'] }, 'en', 'kopf');
		assert.equal(enTreffer.get('e')?.status, 'gefunden');
	});
	test('alleNichtPruefbar setzt jeden mit Grund', () => {
		const r = alleNichtPruefbar(liste, 'Grund');
		assert.equal(r.size, 3);
		assert.ok([...r.values()].every((e) => e.status === 'nicht_pruefbar' && e.grund === 'Grund'));
	});
});

describe('F002: Bericht schreiben und Abschluss', () => {
	const liste = [el('a', 'kopf', 1, 'Wetter'), el('b', 'kopf', 2, 'Zustellung')];
	test('schreibeBericht legt JSON und Markdown mit jedem Element an', () => {
		const dir = mkdtempSync(join(tmpdir(), 'abgleich-bericht-'));
		try {
			const b = baueBericht(liste, new Map([['a', { status: 'gefunden' as const }]]));
			const p = schreibeBericht(dir, b, { optionen: { strict: false, scope: null } });
			assert.ok(existsSync(p.json) && existsSync(p.md));
			const j = JSON.parse(readFileSync(p.json, 'utf8'));
			assert.deepEqual(j.eintraege.map((e: { id: string }) => e.id), ['a', 'b']);
			assert.deepEqual(j.optionen, { strict: false, scope: null });
			const md = readFileSync(p.md, 'utf8');
			assert.ok(md.includes('| a |') && md.includes('| b |') && md.includes('nicht_pruefbar'));
		} finally {
			rmSync(dir, { recursive: true, force: true });
		}
	});
	test('abschluss: ohne Strict Exit 0, mit Strict ≠ 0 bei Lücken; unvollständiger Bericht wirft', () => {
		const b = baueBericht(liste, new Map([['a', { status: 'gefunden' as const }]]));
		assert.equal(abschluss(b, liste, { strict: false }).exit, 0);
		assert.notEqual(abschluss(b, liste, { strict: true }).exit, 0);
		assert.throws(() => abschluss(b, [...liste, el('c', 'kopf', 3, 'x')], { strict: false }), /unvollständig/);
	});
});

describe('F003: Starter übersetzt CLI-Flags und reicht den Exit-Code durch', () => {
	test('--strict, --scope, --sprache ⇒ Umgebung', () => {
		assert.deepEqual(flagsAlsUmgebung(['--strict', '--scope', 'wetter/normal', '--sprache', 'en']), {
			ELEMENTLISTE_STRICT: '1',
			ELEMENTLISTE_SCOPE: 'wetter/normal',
			ELEMENTLISTE_SPRACHE: 'en'
		});
		assert.deepEqual(flagsAlsUmgebung(['--scope=zustellung']), { ELEMENTLISTE_SCOPE: 'zustellung' });
		assert.deepEqual(flagsAlsUmgebung([]), {});
	});
	test('unbekannte Option oder fehlender Wert ⇒ Fehler', () => {
		assert.throws(() => flagsAlsUmgebung(['--strikt']), /unbekannte Option/);
		assert.throws(() => flagsAlsUmgebung(['--scope']), /braucht einen Wert/);
		assert.throws(() => flagsAlsUmgebung(['--sprache', 'fr']), /de oder en/);
	});
	test('Login nur GZ_AUTH_* aus dem .env-Text, nur wenn nicht schon gesetzt', () => {
		const text = 'GZ_SMTP_PASS=geheim\nGZ_AUTH_USER="pruefer"\nexport GZ_AUTH_PASS=\'pw\'\n';
		assert.deepEqual(loginAusEnvText(text), { GZ_AUTH_USER: 'pruefer', GZ_AUTH_PASS: 'pw' });
		const env = starterUmgebung(['--strict'], { PATH: '/x' }, text);
		assert.equal(env.ELEMENTLISTE_STRICT, '1');
		assert.equal(env.GZ_AUTH_USER, 'pruefer');
		assert.equal(env.GZ_SMTP_PASS, undefined, 'andere Geheimnisse werden nicht übernommen');
		const gesetzt = starterUmgebung([], { GZ_AUTH_USER: 'a', GZ_AUTH_PASS: 'b' }, text);
		assert.equal(gesetzt.GZ_AUTH_USER, 'a');
	});
	test('Starter startet genau die Staging-Config', () => {
		assert.deepEqual(PLAYWRIGHT_ARGS, ['playwright', 'test', '--config', 'playwright.elementliste.staging.config.ts']);
	});
	test('Starter-Prozess: unbekannte Option ⇒ Exit 2, ohne Playwright zu starten', () => {
		const r = spawnSync(process.execPath, ['--experimental-strip-types', join(FRONTEND, '..', 'scripts', 'elementliste_abgleich.ts'), '--strikt'], {
			cwd: FRONTEND,
			encoding: 'utf8',
			env: { ...process.env, ELEMENTLISTE_ENV_DATEI: '/nicht/vorhanden' }
		});
		assert.equal(r.status, 2, r.stderr);
		assert.match(r.stderr, /unbekannte Option/);
	});
	// Fix-Loop 2 (Adversary F010): Exit-Code-Durchreichung im echten Starter-Prozess. Statt Playwright liegt
	// ein Ersatz-`npx` vorn im PATH: er hält Argumente, Arbeitsordner und Umgebung fest und endet mit dem
	// vorgegebenen Code bzw. per Signal.
	describe('Starter-Prozess reicht den Exit-Code des gestarteten Kommandos durch', () => {
		const starte = (argv: string[], verhalten: string) => {
			const bin = mkdtempSync(join(tmpdir(), 'abgleich-starter-'));
			const protokoll = join(bin, 'protokoll.txt');
			writeFileSync(
				join(bin, 'npx'),
				`#!/bin/sh\n{ echo "ARGS=$*"; echo "PWD=$(pwd)"; echo "STRICT=$ELEMENTLISTE_STRICT"; echo "SCOPE=$ELEMENTLISTE_SCOPE"; echo "USER=$GZ_AUTH_USER"; } > "${protokoll}"\n${verhalten}\n`
			);
			chmodSync(join(bin, 'npx'), 0o755);
			try {
				const r = spawnSync(process.execPath, ['--experimental-strip-types', join(FRONTEND, '..', 'scripts', 'elementliste_abgleich.ts'), ...argv], {
					cwd: FRONTEND,
					encoding: 'utf8',
					env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, ELEMENTLISTE_ENV_DATEI: '/nicht/vorhanden', GZ_AUTH_USER: 'pruefer', GZ_AUTH_PASS: 'pw' }
				});
				return { status: r.status, stderr: r.stderr, protokoll: existsSync(protokoll) ? readFileSync(protokoll, 'utf8') : '' };
			} finally {
				rmSync(bin, { recursive: true, force: true });
			}
		};
		test('Kommando endet mit 0 ⇒ Starter 0; Flags kommen als Umgebung, Staging-Config im frontend-Ordner', () => {
			const r = starte(['--strict', '--scope', 'wetter/normal'], 'exit 0');
			assert.equal(r.status, 0, r.stderr);
			assert.match(r.protokoll, /^ARGS=playwright test --config playwright\.elementliste\.staging\.config\.ts$/m);
			assert.match(r.protokoll, new RegExp(`^PWD=${FRONTEND.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`, 'm'));
			assert.match(r.protokoll, /^STRICT=1$/m);
			assert.match(r.protokoll, /^SCOPE=wetter\/normal$/m);
			assert.match(r.protokoll, /^USER=pruefer$/m);
		});
		test('Kommando endet mit 1 bzw. 3 ⇒ Starter endet genauso', () => {
			assert.equal(starte(['--strict'], 'exit 1').status, 1);
			assert.equal(starte([], 'exit 3').status, 3);
		});
		test('Kommando stirbt per Signal ⇒ Starter endet mit 1, nie 0', () => {
			assert.equal(starte([], 'kill -TERM $$').status, 1);
		});
	});
});

describe('AC-15: die Config bricht mit Prod-URL beim Laden ab (echter Ladevorgang im Unterprozess)', () => {
	const lade = (base: string) =>
		spawnSync(
			process.execPath,
			['--experimental-strip-types', '--input-type=module', '-e', `await import(${JSON.stringify(pathToFileURL(join(FRONTEND, 'playwright.elementliste.staging.config.ts')).href)})`],
			{ cwd: FRONTEND, encoding: 'utf8', env: { ...process.env, GZ_SVELTE_BASE: base } }
		);
	test('Prod-URL ⇒ Abbruch mit Meldung', () => {
		const r = lade(PROD);
		assert.notEqual(r.status, 0);
		assert.match(r.stderr, /PRODUKTION/);
	});
	test('Staging-URL ⇒ Config lädt', () => {
		const r = lade(STAGING);
		assert.equal(r.status, 0, r.stderr);
	});
});
