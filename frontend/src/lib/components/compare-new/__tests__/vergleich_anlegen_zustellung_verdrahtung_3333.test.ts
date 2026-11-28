// TDD RED — Issue #3333 (Teil D2 von #3307, Epic #3122): Reiter „Zustellung“ beim Ortsvergleich-Anlegen,
// Weg Reiter -> Editor -> der eine Anlege-POST. Spec docs/specs/modules/feat_3333_zustellung_anlegen_orte.md,
// Test Plan Nr. 1, 3, 4, 7 (AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-11) — gemessen dort, wo es WIRKT.
// Pendant zu trip-new/__tests__/trip_anlegen_zustellung_verdrahtung_3332.test.ts.
//
// Messaufbau: das ECHTE Instanz-Skript von CompareNewEditor.svelte und das ECHTE Instanz-Skript von
// ZustellungTab.svelte (svelteInstanzPruefstand.ts), verbunden über die ECHTEN Attribut-Ausdrücke der
// `<ZustellungTab …>`-Einbettungen im Editor (0 = Desktop, 1 = Mobil), ausgewertet in der Umgebung des
// Editor-Skripts. Bedient wird der Reiter über den echten `onaendern`-Rückruf seiner Kanal-Tabelle — genau das,
// was ein Klick auslöst. Der POST läuft über den echten `handleActivate` -> `speichereNeuenVergleich` ->
// `legeVergleichAn` -> `baueVergleichAnlegeRumpf` und wird am gesäten `api.post` mitgeschnitten. Kein
// Mock-Theater: gesät sind nur Netz-Endpunkte (die nichts entscheiden).
//
// FESTGELEGTE SCHNITTSTELLE (Spec, Implementation Details):
//   Im Editor: `zustellungStand` ($state), `zustellungAbo` ($derived aus `wiz`, Stub-Abo mit `id: ''`),
//   `handleZustellungAnlegeStand` (Inhaltsgleichheits-Guard, schreibt per `mitZustellungVergleich` in `wiz`).
//   Einbettung: `<ZustellungTab context="vergleich" createMode preset={zustellungAbo}
//   zustellungStart={zustellungStand} onAnlegeStand={handleZustellungAnlegeStand}
//   activation={versandActivationBanner} …>` Desktop UND Mobil; kein `WetterMetrikenVersandPanel` mehr.
//
// REFERENZ für AC-5: fixtures/vergleich_anlegen_ohne_zustellung_3333.json (erzeugt in
// vergleich_anlegen_zustellung_payload_3333.test.ts aus dem heutigen Rumpf).
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/vergleich_anlegen_zustellung_verdrahtung_3333.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, findeKomponenten, attributAusdruck, ohneTypen, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { editorUmgebung, derivedNeu, COMPARE_EDITOR, type EditorUmgebung } from '../../shared/__tests__/standardwerteEditorPruefstand.ts';
import { MATCH_MEDIA } from '../../shared/__tests__/compareNeuEditorPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const ZUSTELLUNG_TAB = join(HIER, '..', '..', 'shared', 'zustellung-tab', 'ZustellungTab.svelte');
const FIXTURE = join(HIER, 'fixtures', 'vergleich_anlegen_ohne_zustellung_3333.json');
const NAME = 'Neu-3333';
const ORTE = ['loc-a', 'loc-b'];
const ALLE_BESUCHT = { activeTab: 'zustellung', isMobileViewport: false, metrikenVisited: true, zustellungVisited: true };

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const klon = <T>(v: T): T => (v === undefined ? v : JSON.parse(JSON.stringify(v)));

// ── Netz: nur Mitschrift ─────────────────────────────────────────────────────
type Aufruf = { methode: string; pfad: string };
let netz: Aufruf[] = [];
const echtesFetch = globalThis.fetch;
beforeEach(() => {
	netz = [];
	globalThis.fetch = (async (url: unknown, init?: { method?: string }) => {
		netz.push({ methode: init?.method ?? 'GET', pfad: String(url) });
		return { ok: true, json: async () => ({ mail_to: 'a@example.com', telegram_chat_id: 'chat-a', tier: 'standard' }) } as Response;
	}) as typeof fetch;
});
afterEach(() => {
	globalThis.fetch = echtesFetch;
});
/** api-Attrappe des Reiters: schreibt nur mit, was er aufruft (im Anlegen darf er nichts aufrufen). */
function reiterApi(): Knoten {
	const auf = (methode: string) => async (pfad: string) => (netz.push({ methode, pfad }), {});
	return { get: auf('GET'), post: auf('POST'), put: auf('PUT'), patch: auf('PATCH'), delete: auf('DELETE') };
}

// ── Editor ───────────────────────────────────────────────────────────────────
type Ed = EditorUmgebung & { gesendet: Array<{ url: string; payload: J }>; speichern: () => Promise<J> };
async function editor(): Promise<Ed> {
	const gesendet: Array<{ url: string; payload: J }> = [];
	const e = await editorUmgebung(COMPARE_EDITOR, {
		stateOverride: { ...ALLE_BESUCHT, name: NAME, pickedIds: [...ORTE] },
		vorlage: null,
		locations: [],
		window: MATCH_MEDIA,
		api: {
			post: async (url: string, payload: J) => (gesendet.push({ url, payload: klon(payload) }), { id: 'cmp-neu' }),
			get: async () => [],
			put: async (url: string) => (netz.push({ methode: 'PUT', pfad: url }), {})
		}
	});
	const speichern = async () => {
		derivedNeu(e);
		gesendet.length = 0;
		assert.equal(e.u.canActivateNow, true, 'Messaufbau: „Briefing aktivieren“ gesperrt');
		await e.u.handleActivate();
		assert.equal(gesendet.length, 1, 'genau ein Anlege-POST');
		assert.equal(gesendet[0].url, '/api/compare/presets');
		return gesendet[0].payload;
	};
	return { ...e, gesendet, speichern };
}

/** Wert eines Attributs an einer echten Einbettung, ausgewertet in der Umgebung des Eltern-Skripts. */
function attrWert(a: Knoten, quelle: string, u: Knoten): unknown {
	if (a.value === true) return true;
	if (Array.isArray(a.value)) return a.value.map((t: Knoten) => (t.type === 'Text' ? t.data : werte(ohneTypen(quelle, t.expression), u))).join('');
	if (a.value?.type === 'ExpressionTag') return werte(ohneTypen(quelle, a.value.expression), u);
	return werte(a.name, u);
}
/** Alle Attribute einer Einbettung; Snippets des Markups (z. B. `activation`) liegen nicht im Skript. */
function alleAttribute(einbettung: Knoten, quelle: string, u: Knoten, ohne: string[] = []): Knoten {
	const props: Knoten = {};
	for (const a of (einbettung.attributes ?? []) as Knoten[]) if (a.type === 'Attribute' && !ohne.includes(a.name)) props[a.name] = attrWert(a, quelle, u);
	return props;
}

function einbettungen(ed: Ed): Knoten[] {
	const einb = findeKomponenten(ed.ast, 'ZustellungTab');
	assert.equal(einb.length, 2, `CompareNewEditor bettet ${einb.length} statt 2 ZustellungTab ein (Desktop + Mobil, AC-1)`);
	return einb;
}

/** Reiter Zustellung, gemountet wie die `i`-te `<ZustellungTab>`-Einbettung im Editor (0 = Desktop, 1 = Mobil). */
async function reiter(ed: Ed, i: number) {
	derivedNeu(ed); // Svelte rechnet die Herleitungen vor jedem Neuaufbau neu
	const einb = einbettungen(ed);
	const props = alleAttribute(einb[i], ed.quelle, ed.u, ['activation']);
	assert.equal(props.context, 'vergleich');
	assert.equal(props.createMode, true, 'ZustellungTab im Anlegen ohne createMode');
	assert.equal(typeof props.onAnlegeStand, 'function', 'ZustellungTab im Anlegen ohne Rückkanal onAnlegeStand');
	const mounts: Array<() => unknown> = [];
	const t = await umgebungFuer(
		ZUSTELLUNG_TAB,
		{ ...props, panel: { ...props }, untrack: (fn: () => unknown) => fn(), onMount: (fn: () => unknown) => void mounts.push(fn), api: reiterApi() },
		{ jsAlsTs: true }
	);
	for (const stmt of t.ast.instance.content.body as Knoten[]) {
		const x = stmt.type === 'ExpressionStatement' ? (stmt.expression as Knoten) : null;
		if (x?.type === 'CallExpression' && x.callee?.name === 'onMount') werte(ohneTypen(t.quelle, x), t.u);
	}
	for (const m of mounts) m();
	await new Promise((r) => setImmediate(r));
	const kt = findeKomponenten(t.ast, 'KanalTabelle')[0];
	assert.ok(kt, 'Messaufbau: KanalTabelle im Reiter fehlt');
	const kanalProps = alleAttribute(kt, t.quelle, t.u);
	assert.equal(typeof kanalProps.onaendern, 'function', 'Messaufbau: onaendern der Kanal-Tabelle nicht auswertbar');
	return {
		u: t.u,
		props,
		/** Stand, den der Reiter seinen Bausteinen zeigt. */
		stand: () => klon(alleAttribute(kt, t.quelle, t.u).stand as J),
		/** Eine Geste in der Kanal-Tabelle (bzw. Zeiten/Stille): neuer Gesamtstand an den Reiter. */
		aendern: (f: (s: J) => J) => (alleAttribute(kt, t.quelle, t.u).onaendern as (s: J) => void)(f(klon(alleAttribute(kt, t.quelle, t.u).stand as J)))
	};
}

function referenz(): J {
	assert.ok(fs.existsSync(FIXTURE), `Referenz-Fixture fehlt: ${FIXTURE}`);
	return JSON.parse(fs.readFileSync(FIXTURE, 'utf-8'));
}

describe('#3333 Test 6 (AC-1, AC-11, AC-13): Einbettung im Schritt Zustellung', () => {
	test('Desktop und Mobil: ZustellungTab context="vergleich" createMode mit Stub-Abo, Startstand und Rückkanal', async () => {
		const ed = await editor();
		derivedNeu(ed);
		for (const [i, einb] of einbettungen(ed).entries()) {
			const props = alleAttribute(einb, ed.quelle, ed.u, ['activation']);
			assert.equal(props.context, 'vergleich', `Einbettung ${i}: context`);
			assert.equal(props.createMode, true, `Einbettung ${i}: createMode`);
			assert.ok(props.preset && typeof props.preset === 'object', `Einbettung ${i}: kein Stub-Abo (preset) — standAusPreset(undefined) wirft`);
			assert.equal((props.preset as J).id, '', `Einbettung ${i}: Stub-Abo ohne id '' (kein Serverstand im Anlegen)`);
			assert.deepEqual(klon((props.preset as J).location_ids), ORTE, `Einbettung ${i}: Stub-Abo ohne die gewählten Orte`);
			assert.equal(attributAusdruck(einb, ed.quelle, 'zustellungStart'), 'zustellungStand', `Einbettung ${i}: zustellungStart nicht aus dem Editor-Stand`);
			assert.equal(attributAusdruck(einb, ed.quelle, 'activation'), 'versandActivationBanner', `Einbettung ${i}: Aktivierungs-Banner nicht am Reiter (AC-11)`);
		}
	});

	test('kein Alt-Panel mehr im Editor (WetterMetrikenVersandPanel nicht eingebettet)', async () => {
		const ed = await editor();
		assert.equal(findeKomponenten(ed.ast, 'WetterMetrikenVersandPanel').length, 0, 'Alt-Panel noch im Orte-Anlegen (zweiter Schreiber der Versand-Felder)');
	});
});

describe('#3333 Test 4 (AC-5): Reiter nie bedient — POST bitgleich zu heute plus send_email: true', () => {
	test('ohne Öffnen des Reiters', async () => {
		const ed = await editor();
		assert.deepEqual(await ed.speichern(), { ...referenz(), send_email: true });
	});

	test('Reiter geöffnet (Desktop und Mobil gebaut, Profil geladen), aber nicht bedient: POST unverändert, kein Schreibaufruf', async () => {
		const ed = await editor();
		await reiter(ed, 0);
		await reiter(ed, 1);
		assert.deepEqual(netz.filter((x) => x.methode !== 'GET'), [], 'Schreibaufruf beim bloßen Öffnen');
		assert.deepEqual(await ed.speichern(), { ...referenz(), send_email: true });
	});

	test('Startstand des Reiters = was der POST ohne Bedienung sendet (Zeiten, Kanäle, Alarm-Kanäle, Dringlichkeit, Stille)', async () => {
		const ref = { ...referenz(), send_email: true };
		const s = (await reiter(await editor(), 0)).stand();
		assert.equal(s.morgenAn, ref.morning_enabled, 'Morgen-Schalter');
		assert.equal(s.abendAn, ref.evening_enabled, 'Abend-Schalter');
		assert.equal(s.morgenZeit, String(ref.morning_time).slice(0, 5));
		assert.equal(s.abendZeit, String(ref.evening_time).slice(0, 5));
		for (const k of ['email', 'telegram', 'sms', 'premium_sms']) {
			assert.equal(s.briefing[k], ref[`send_${k}`] === true, `Briefing-Kanal ${k}`);
			assert.equal(s.alarme[k], ref.alert_channels[k], `Alarm-Kanal ${k}`);
			// #2801 (ADR-0131): Vorbelegung je Kanal statt „alle LOW“.
			const vorbelegung: Record<string, string> = { email: 'LOW', telegram: 'LOW', sms: 'MODERATE', premium_sms: 'HIGH' };
			assert.equal(s.dringlichkeit[k], vorbelegung[k], `Dringlichkeit ${k}`);
		}
		assert.equal(s.stilleAn, false, 'Stille Stunden');
		assert.equal(s.endDate, null, 'Laufzeit');
	});
});

const BEDIENT = (s: J): J => ({
	...s,
	morgenZeit: '06:45',
	abendAn: false,
	// Briefing- und Alarm-Kanäle GETRENNT und vollständig belegt (Lehre #3332 F004).
	briefing: { email: false, telegram: true, sms: true, premium_sms: false },
	alarme: { email: true, telegram: true, sms: false, premium_sms: true },
	dringlichkeit: { ...s.dringlichkeit, telegram: 'HIGH' },
	stilleAn: true,
	stilleVon: '22:30',
	stilleBis: '06:15',
	cooldown: 45,
	endDate: '2027-03-01'
});

describe('#3333 Test 1 (AC-2, AC-3, AC-4, AC-6): Bedienung im Reiter -> genau der eine POST trägt sie', () => {
	test('Zeiten, Kanäle, E-Mail aus, Dringlichkeit HIGH, Stille, Cooldown, Laufzeit stehen im POST; kein PUT, kein Schreibaufruf', async () => {
		const ed = await editor();
		ed.u.wiz.dayWindowStartHour = 5; // Bericht des Reiters Wetter
		const r = await reiter(ed, 0);
		r.aendern(BEDIENT);
		assert.deepEqual(netz.filter((x) => x.methode !== 'GET'), [], 'AC-6: Schreibaufruf vor dem Anlegen');
		const p = await ed.speichern();
		assert.equal(p.morning_time, '06:45:00', 'AC-2: Morgen-Zeit');
		assert.equal(p.morning_enabled, true);
		assert.equal(p.evening_enabled, false, 'AC-2: Abend-Schalter');
		assert.equal(p.send_email, false, 'AC-4: E-Mail abgewählt');
		assert.equal(p.send_telegram, true, 'AC-2: Briefing-Kanal Telegram (nicht der Alarm-Kanal)');
		assert.equal(p.send_sms, true, 'AC-2: Briefing-Kanal SMS (nicht der Alarm-Kanal)');
		assert.equal(p.send_premium_sms, false, 'AC-2: Briefing-Kanal Premium-SMS (nicht der Alarm-Kanal)');
		assert.equal(p.end_date, '2027-03-01', 'AC-2: Laufzeit');
		assert.deepEqual(p.alert_channels, { email: true, telegram: true, sms: false, premium_sms: true }, 'AC-3: Alarm-Kanäle (nicht die Briefing-Kanäle)');
		assert.equal(p.alert_channel_thresholds?.telegram, 'HIGH', 'AC-3: Dringlichkeit Telegram');
		assert.equal(p.alert_quiet_from, '22:30', 'AC-2: Stille von');
		assert.equal(p.alert_quiet_to, '06:15', 'AC-2: Stille bis');
		assert.equal(p.alert_cooldown_minutes, 45, 'AC-3: Cooldown');
		assert.equal(p.day_window_start_hour, 5, 'Read-Modify-Write: Tagesfenster des Reiters Wetter verloren');
		assert.equal(p.official_warnings?.enabled, true, 'amtliche Warnungen unverändert');
		assert.deepEqual(netz.filter((x) => x.methode !== 'GET'), [], 'AC-6: Schreibaufruf des Reiters');
		assert.deepEqual(netz.filter((x) => x.methode === 'GET').map((x) => x.pfad), ['/api/auth/profile'], 'nur der eine Profil-Abruf');
	});

	test('Mobil-Einbettung meldet ebenso in den POST', async () => {
		const ed = await editor();
		const r = await reiter(ed, 1);
		r.aendern(BEDIENT);
		const p = await ed.speichern();
		assert.equal(p.morning_time, '06:45:00');
		assert.equal(p.send_email, false);
		assert.equal(p.alert_channel_thresholds?.telegram, 'HIGH');
	});

	test('Stille Stunden wieder aus: POST ohne Stille-Zeiten, Rest bleibt', async () => {
		const ed = await editor();
		const r = await reiter(ed, 0);
		r.aendern(BEDIENT);
		r.aendern((s) => ({ ...s, stilleAn: false }));
		const p = await ed.speichern();
		assert.equal(p.alert_quiet_from ?? null, null);
		assert.equal(p.alert_quiet_to ?? null, null);
		assert.equal(p.morning_time, '06:45:00');
	});
});

describe('#3333 Test 2 (AC-8): rasterfremde Uhrzeit — der POST trägt die letzte gültige', () => {
	test('06:45, dann 06:50 eingegeben: POST morning_time 06:45:00', async () => {
		const ed = await editor();
		const r = await reiter(ed, 0);
		r.aendern((s) => ({ ...s, morgenZeit: '06:45' }));
		r.aendern((s) => ({ ...s, morgenZeit: '06:50' }));
		const p = await ed.speichern();
		assert.equal(p.morning_time, '06:45:00', 'letzte gültige Zeit nicht im POST');
	});

	test('nur 06:50 eingegeben: POST behält die Startzeit, nie 06:50; gültige Änderung derselben Geste wirkt', async () => {
		const ed = await editor();
		const r = await reiter(ed, 0);
		r.aendern((s) => ({ ...s, morgenZeit: '06:50', cooldown: 30 }));
		const p = await ed.speichern();
		assert.equal(p.morning_time, referenz().morning_time);
		assert.ok(!JSON.stringify(p).includes('06:50'), 'rasterfremde Uhrzeit im POST (Server antwortet 400)');
		assert.equal(p.alert_cooldown_minutes, 30, 'gültige Änderung derselben Geste geht verloren');
	});
});

// Neuaufbau mit Bedienständen, die der Feldsatz NICHT zurückspiegelt (Lehre #3332 F001): Stille 22:30–06:15
// eingestellt und wieder aus (der Feldsatz kennt die Zeiten danach nicht mehr) und eine rasterfremde
// Morgenzeit 06:50 (der POST behält 06:45, der Reiter zeigt, was getippt wurde). Der NEU gebaute Reiter muss
// genau den bedienten Stand ANZEIGEN — nur möglich über `zustellungStart` aus dem Editor.
const BEDIENT_NICHT_RUECKSPIEGELBAR = (s: J): J => ({ ...BEDIENT(s), stilleAn: false, morgenZeit: '06:50' });

describe('#3333 Test 7 (AC-7): Neuaufbau (Wechsel Desktop <-> Mobil, Schritte) behält den Stand', () => {
	for (const [von, nach, name] of [[0, 1, 'Desktop -> Mobil'], [1, 0, 'Mobil -> Desktop'], [0, 0, 'Desktop neu aufgebaut'], [1, 1, 'Mobil neu aufgebaut']] as const) {
		test(name, async () => {
			const ed = await editor();
			const r1 = await reiter(ed, von);
			r1.aendern(BEDIENT);
			r1.aendern(BEDIENT_NICHT_RUECKSPIEGELBAR);
			const erwartet = r1.stand();
			assert.equal(erwartet.stilleVon, '22:30', 'Messaufbau: Stille-Zeiten nicht im Stand');
			const r2 = await reiter(ed, nach);
			const gezeigt = r2.stand();
			assert.equal(gezeigt.morgenZeit, '06:50', 'neu gebauter Reiter zeigt nicht die eingetippte Morgenzeit (Startstand vom Editor fehlt)');
			assert.equal(gezeigt.stilleVon, '22:30', 'neu gebauter Reiter verliert die Stille-Zeiten');
			assert.deepEqual(gezeigt, erwartet, 'neu gebauter Reiter zeigt nicht den bedienten Stand');
			// Eine Geste nach dem Neuaufbau verliert die frühere nicht.
			r2.aendern((s) => ({ ...s, stilleAn: true, cooldown: 90 }));
			const p = await ed.speichern();
			assert.equal(p.morning_time, '06:45:00', 'POST trägt die letzte gültige Morgenzeit');
			assert.equal(p.alert_quiet_from, '22:30', 'Stille-Zeiten nach dem Neuaufbau verloren');
			assert.equal(p.alert_quiet_to, '06:15');
			assert.equal(p.alert_channel_thresholds?.telegram, 'HIGH');
			assert.equal(p.alert_cooldown_minutes, 90);
			assert.equal(p.send_email, false);
		});
	}
});

// Der Editor übernimmt eine Meldung mit unverändertem Inhalt nicht erneut (Lehre #3332 F003): ohne den
// Gleichheits-Schutz entstünde je Meldung ein neuer Stand / neue Feldsatz-Unterobjekte — im Browser die
// Gefahr einer Effekt-Schleife.
describe('#3333 Inhaltsgleichheits-Guard: Meldung mit gleichem Inhalt ändert den Editor-Stand nicht', () => {
	test('zweimal dieselbe Geste: zustellungStand und wiz.channels behalten ihre Objekte', async () => {
		const ed = await editor();
		const r = await reiter(ed, 0);
		r.aendern(BEDIENT);
		const st = ed.u.zustellungStand;
		const ch = ed.u.wiz.channels;
		assert.ok(st && ch, 'Messaufbau: Editor-Stand nach der ersten Geste fehlt');
		r.aendern((s) => s); // Geste ohne inhaltliche Änderung
		assert.equal(ed.u.zustellungStand, st, 'gleiche Meldung ersetzt den gehaltenen Stand');
		assert.equal(ed.u.wiz.channels, ch, 'gleiche Meldung erzeugt neue Alarm-Kanäle im Feldsatz');
		// Gegenprobe: eine echte Änderung wird übernommen.
		r.aendern((s) => ({ ...s, cooldown: 75 }));
		assert.notEqual(ed.u.zustellungStand, st);
		assert.equal(ed.u.wiz.alertCooldownMinutes, 75);
	});
});
