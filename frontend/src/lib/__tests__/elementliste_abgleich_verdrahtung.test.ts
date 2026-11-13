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
	findeZusaetzliche,
	werteGegenrichtungAus,
	ladeRegeln,
	ladeKontoTexte,
	werteLaufAus,
	zaehleAnker,
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

// feat_2913_abgleich_ganzseite, Fix-Loop 1 (Adversary F001): Regeln laden, Konto-Texte laden und die
// Auswertung nach dem Lauf liegen als Logik vor; hier wird ihre WIRKUNG geprüft (echte Dateien im
// Temp-Ordner, echte Freigaben-Datei). Die Staging-Spec ruft nur noch diese Funktionen.
describe('Ganzseite F001: Regeln, Konto-Texte und Auswertung (strict + abnahme) wirken', () => {
	const KONTEXT = join(FRONTEND, '..', 'docs/context/einstellungen_neu');
	const liste = [el('w.a', 'kopf', 1, 'Wetter', { reiter: 'zustellung' })];
	const zusFremd = () => findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Wetter', 'Fremd 3'] }, liste, [], [], 'de');
	const mitDateien = <T>(besitzer: unknown, f: (d: { freigaben: string; besitzer: string }) => T): T => {
		const dir = mkdtempSync(join(tmpdir(), 'abgleich-regeln-'));
		try {
			const pfad = join(dir, 'elementliste_besitzer.json');
			writeFileSync(pfad, JSON.stringify(besitzer));
			return f({ freigaben: join(KONTEXT, 'elementliste_freigaben.json'), besitzer: pfad });
		} finally {
			rmSync(dir, { recursive: true, force: true });
		}
	};
	const BESITZER_FREMD = { art: 'zusaetzlich', ctx: 'trip', reiter: 'zustellung', muster: 'Fremd {n}', grund: 'g', verweis: '#2913-e' };
	const AUSNAHME = { text: 'Gespeichert', grund: 'Speicher-Rückmeldung', spec: 's.md' };

	test('ladeRegeln liest Freigaben, Besitzer und Ausnahmen (nicht leer)', () => {
		const r = mitDateien({ besitzer: [BESITZER_FREMD], ausnahmen: [AUSNAHME] }, (d) => ladeRegeln(d, liste));
		assert.ok(r.freigaben.length > 0, 'Freigaben fehlen');
		assert.deepEqual(r.besitzer.map((b) => b.verweis), ['#2913-e']);
		assert.deepEqual(r.ausnahmen.map((a) => a.text), ['Gespeichert']);
		const z = findeZusaetzliche({ ctx: 'trip', reiter: 'zustellung', texte: ['Gespeichert', 'Neu'] }, liste, r.ausnahmen, [], 'de');
		assert.deepEqual(z.map((x) => x.text), ['Neu'], 'Ausnahme aus der Datei erklärt den Text');
	});
	test('ladeRegeln bricht bei element-Besitzer mit unbekannter ID ab und nennt den Eintrag', () => {
		const b = { besitzer: [{ art: 'element', id: 'gibt.es.nicht', grund: 'g', verweis: '#2913-d' }], ausnahmen: [] };
		assert.throws(() => mitDateien(b, (d) => ladeRegeln(d, liste)), /Besitzer 0.*gibt\.es\.nicht/);
	});
	test('echte Besitzer-Datei lädt gegen die echte Elementliste', () => {
		const r = ladeRegeln({ freigaben: join(KONTEXT, 'elementliste_freigaben.json'), besitzer: join(KONTEXT, 'elementliste_besitzer.json') }, LISTE);
		assert.ok(Array.isArray(r.besitzer) && Array.isArray(r.ausnahmen));
	});

	const lauf = (env: Record<string, string>, besitzer: unknown[]) =>
		mitDateien({ besitzer, ausnahmen: [] }, (d) => {
			const dir = mkdtempSync(join(tmpdir(), 'abgleich-lauf-'));
			try {
				const plan = planeAbgleich({ liste, env, baseURL: STAGING });
				const r = werteLaufAus({ plan, ergebnisse: new Map([['w.a', { status: 'gefunden' as const }]]), zusaetzlich: zusFremd(), regeln: ladeRegeln(d, liste), berichtDir: dir });
				return { ...r, json: JSON.parse(readFileSync(r.pfade.json, 'utf8')) };
			} finally {
				rmSync(dir, { recursive: true, force: true });
			}
		});
	test('werteLaufAus mit --abnahme: herrenloser Fremdtext ⇒ Exit 1 (abnahme wird durchgereicht)', () => {
		const r = lauf({ ELEMENTLISTE_ABNAHME: '1' }, []);
		assert.equal(r.ende.exit, 1);
		assert.match(r.ende.meldung, /abnahme: 1 ohne Besitzer/);
		assert.equal(r.json.zaehler.zusaetzlich, 1);
		assert.equal(r.json.optionen.abnahme, true);
	});
	test('werteLaufAus wendet die Besitzer der Datei an ⇒ Exit 0, Besitzer im geschriebenen Bericht', () => {
		const r = lauf({ ELEMENTLISTE_ABNAHME: '1' }, [BESITZER_FREMD]);
		assert.equal(r.ende.exit, 0, r.ende.meldung);
		assert.equal(r.json.zusaetzlich[0].besitzer.verweis, '#2913-e');
	});
	test('werteLaufAus nur --strict: zusaetzlich allein ⇒ Exit 0; ohne Flags Exit 0', () => {
		assert.equal(lauf({ ELEMENTLISTE_STRICT: '1' }, []).ende.exit, 0);
		assert.equal(lauf({}, []).ende.exit, 0);
	});
	test('Fix-Loop 2/3 (Befund 1, F001): werteLaufAus mit Kombi ohne Hub-Marker ⇒ im Bericht; nur --abnahme Exit 1, --strict und ohne Flags 0', () => {
		const gegen = werteGegenrichtungAus({ ctx: 'trip', reiter: 'zustellung', anker: { kopf: 1, flaeche: 0 }, texte: ['Kanäle'] }, liste, [], [], 'de');
		const laufOhneHub = (env: Record<string, string>) =>
			mitDateien({ besitzer: [], ausnahmen: [] }, (d) => {
				const dir = mkdtempSync(join(tmpdir(), 'abgleich-hub-'));
				try {
					const plan = planeAbgleich({ liste, env, baseURL: STAGING });
					const ohneHub = gegen.ohneHub ? [gegen.ohneHub] : [];
					const r = werteLaufAus({ plan, ergebnisse: new Map([['w.a', { status: 'gefunden' as const }]]), zusaetzlich: gegen.zusaetzlich, ohneHub, regeln: ladeRegeln(d, liste), berichtDir: dir });
					return { ...r, json: JSON.parse(readFileSync(r.pfade.json, 'utf8')), md: readFileSync(r.pfade.md, 'utf8') };
				} finally {
					rmSync(dir, { recursive: true, force: true });
				}
			});
		const strict = laufOhneHub({ ELEMENTLISTE_STRICT: '1' });
		assert.equal(strict.ende.exit, 0, `--strict gilt unverändert (AC-10): ${strict.ende.meldung}`);
		assert.equal(strict.json.ohne_hub.length, 1);
		assert.equal(strict.json.ohne_hub[0].reiter, 'zustellung');
		assert.match(strict.md, /Hub-Marker fehlt/);
		assert.match(strict.md, /Reiterfläche/);
		assert.equal(laufOhneHub({ ELEMENTLISTE_ABNAHME: '1' }).ende.exit, 1);
		assert.equal(laufOhneHub({ ELEMENTLISTE_STRICT: '1', ELEMENTLISTE_ABNAHME: '1' }).ende.exit, 1);
		assert.equal(laufOhneHub({}).ende.exit, 0);
	});
	test('werteLaufAus wendet Freigaben an (echte Freigaben-Datei)', () => {
		const f = JSON.parse(readFileSync(join(KONTEXT, 'elementliste_freigaben.json'), 'utf8')).freigaben[0];
		const e = el('fg.1', f.abschnitt, 1, 'x', { ctx: f.ctx, reiter: f.reiter, i18n_key: f.i18n_keys[0] });
		const dir = mkdtempSync(join(tmpdir(), 'abgleich-fg-'));
		try {
			const r = mitDateien({ besitzer: [], ausnahmen: [] }, (d) =>
				werteLaufAus({ plan: planeAbgleich({ liste: [e], env: { ELEMENTLISTE_STRICT: '1' }, baseURL: STAGING }), ergebnisse: new Map([['fg.1', { status: 'abweichend' as const, ist: 'fehlt' }]]), zusaetzlich: [], regeln: ladeRegeln(d, [e]), berichtDir: dir })
			);
			assert.equal(r.bericht.eintraege[0].status, 'freigegeben');
			assert.equal(r.ende.exit, 0);
		} finally {
			rmSync(dir, { recursive: true, force: true });
		}
	});

	test('ladeKontoTexte fragt Trip, Vergleich, Orte, Vorlagen ab und sammelt die Namen; Fehlantwort liefert nichts', async () => {
		// Netzgrenze: die Antworten sind echte API-Formen; geprüft wird Pfadauswahl und Zusammenführung.
		const ANTWORT: Record<string, unknown> = {
			'/api/trips/t%201': { id: 't 1', name: 'GR20 Nord', stages: [{ id: 's1', name: 'Calenzana – Ortu', waypoints: [{ name: 'Bocca' }] }] },
			'/api/compare/presets/v1': { id: 'v1', name: 'Alpen-Vergleich' },
			'/api/compare/presets': [{ id: 'v2', name: 'Zweiter Vergleich' }],
			'/api/locations': [{ id: 'o1', name: 'Innsbruck' }],
			'/api/metric-presets': [{ id: 'm1', name: 'Meine Vorlage' }]
		};
		const gefragt: string[] = [];
		const get = async (p: string) => {
			gefragt.push(p);
			return { ok: () => p in ANTWORT, json: async () => ANTWORT[p] };
		};
		const t = await ladeKontoTexte(get, { trip: 't 1', orte: 'v1' });
		for (const n of ['GR20 Nord', 'Calenzana – Ortu', 'Bocca', 'Alpen-Vergleich', 'Zweiter Vergleich', 'Innsbruck', 'Meine Vorlage']) assert.ok(t.includes(n), `${n} fehlt`);
		assert.deepEqual([...gefragt].sort(), Object.keys(ANTWORT).sort());
		assert.deepEqual(await ladeKontoTexte(async () => ({ ok: () => false, json: async () => ({ name: 'X' }) }), { trip: null, orte: null }), []);
	});

	test('Staging-Spec reicht Regeln, Konto-Texte und Plan vollständig durch (doc-compliance-test)', () => {
		// doc-compliance-test: Restverdrahtung der Live-Spec; die Wirkung der Funktionen prüfen die Tests oben.
		const spec = readFileSync(join(FRONTEND, 'e2e/elementliste-abgleich.staging.spec.ts'), 'utf8');
		assert.match(spec, /const regeln = ladeRegeln\(\{ freigaben: FREIGABEN, besitzer: BESITZER \}, alle\);/);
		assert.match(spec, /const konto = await ladeKontoTexte\(\(pfad\) => api\.get\(pfad\), ids\);/);
		// Fix-Loop 2/3 (Befund 1, F002): beide Hub-Anker werden mitgegeben, der Befund ohne Hub landet in ohneHub und geht an werteLaufAus.
		assert.match(spec, /werteGegenrichtungAus\(\{ ctx: k\.ctx, reiter: k\.reiter, anker: hub\.anker, texte: hub\.texte \}, alle, regeln\.ausnahmen, konto, plan\.sprache\)/);
		assert.match(spec, /if \(gegen\.ohneHub\) ohneHub\.push\(gegen\.ohneHub\);/);
		assert.match(spec, /zusaetzlich\.push\(\.\.\.gegen\.zusaetzlich\);/);
		assert.match(spec, /werteLaufAus\(\{ plan, ergebnisse, zusaetzlich, ohneHub, regeln, berichtDir: BERICHT_DIR \}\)/);
		for (const umgehung of [/\babschluss\(/, /\bleseBesitzer\(/, /\bleseAusnahmen\(/, /\bbaueBericht\(/, /\bexitCode\(/, /\bfindeZusaetzliche\(/]) {
			assert.ok(!umgehung.test(spec), `Spec umgeht die Logik: ${umgehung}`);
		}
	});

	test('Hub-Anker werden je Selektor gezählt, nicht fest verdrahtet oder vertauscht (doc-compliance-test, F003)', () => {
		// doc-compliance-test: im Projekt gibt es keinen DOM-Parser (kein jsdom/linkedom/happy-dom), die Zählung
		// läuft nur im Browser. Geprüft wird darum genau der Quelltext, den page.evaluate in den Browser schickt
		// (zaehleAnker.toString()), und der Aufruf in der Spec mit beiden Selektoren an der richtigen Stelle.
		const spec = readFileSync(join(FRONTEND, 'e2e/elementliste-abgleich.staging.spec.ts'), 'utf8');
		assert.match(spec, /await page\.evaluate\(zaehleAnker, \{ kopf: HUB_ANKER_KOPF, flaeche: HUB_ANKER_FLAECHE \}\)/);
		assert.ok(!/function zaehleAnker\b/.test(spec), 'Spec darf keine eigene Zählfunktion haben, sie kommt aus der Logik');
		assert.match(spec, /^\s*zaehleAnker,$/m, 'Spec importiert zaehleAnker aus der Logik');
		const quelle = zaehleAnker.toString();
		assert.match(quelle, /\bkopf:\s*wurzel\.querySelectorAll\(arg\.kopf\)\.length\b/, `kopf wird nicht über arg.kopf gezählt: ${quelle}`);
		assert.match(quelle, /\bflaeche:\s*wurzel\.querySelectorAll\(arg\.flaeche\)\.length\b/, `flaeche wird nicht über arg.flaeche gezählt: ${quelle}`);
		assert.match(quelle, /wurzel\s*=\s*document\b/, 'Wurzel im Browser muss document sein');
		// Serialisierbar: nur arg, wurzel und document, keine Modul-Konstanten (HUB_ANKER_*) im Funktionsrumpf.
		assert.ok(!/HUB_ANKER|GEGENRICHTUNG_WURZEL/.test(quelle), 'Zählfunktion nutzt Modul-Closures');
	});
});
