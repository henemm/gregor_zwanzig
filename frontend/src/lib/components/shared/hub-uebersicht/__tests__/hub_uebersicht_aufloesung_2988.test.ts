// #2988 S4 (AC-16): die Trip-Übersicht zeigt den Alarmzähler aus der Auflösung des Servers.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md (AC-16, „S4 – Übersichten").
//
// Vertrag (S4, festgelegt im RED-Schritt, docs/context/rework-2988-ampel-ableitung.md „RED-Stand Scheibe S4"):
//   hubUebersichtModell.ts
//     tripAlarmAbText(trip, aufgeloest: Aufgeloest | null | undefined, eig): string
//     tripWetterAlarmAktiv(trip, aufgeloest?: Aufgeloest | null, eig?): boolean
//       Der zweite Parameter ist die aufgelöste Ampel des Trips (POST /api/ampel/aufloesung), nicht mehr
//       die Vorlagen. Ohne sie: „—" bzw. nur die bisherigen Alarmquellen (wie heute ohne Vorlagen).
//   hub-uebersicht/tripAufloesung.ts (neu, ohne Svelte-/Browser-Import)
//     type TripAufloesung = { zustand: 'laedt' | 'geladen' | 'fehler'; aufgeloest: Aufgeloest | null }
//     erstelleTripAufloesung(client: AufloesungClient, melde: (s: TripAufloesung) => void): { laden(trip): Promise<void> }
//       laden: Eintrag = eintragAusAbo(trip). Gleicher Eintrag wie beim letzten Laden (und das ist nicht
//       gescheitert) ⇒ nichts. Sonst sofort (synchron) melde({laedt, null}), EIN Aufruf über
//       loeseAmpelnAuf(client, [eintrag]), dann melde({geladen, ergebnis}) bzw. bei jedem Fehler
//       melde({fehler, null}) — beides nur, wenn seither kein neueres laden begann (Ticket wie
//       wasStehtWoSpeicherung.ts). Das Promise scheitert nie.
//   trip-detail/HubOverview.svelte lädt damit beim Öffnen und bei jeder Änderung von `trip` und reicht
//   `aufgeloest` an beide Modellfunktionen; der Abruf /api/templates entfällt für die Alarm-Zeile.
//
// Erwartung „dieselbe Zahl wie der Reiter Wetter": der ECHTE Reiter (WetterTabInhalt über reiter2988,
// Laden mit echtem Python), daraus die Herleitung `zaehler`. Auflösung: echtes `resolve_entwurf`
// (aufloesungPost / aufgeloestVon). Kein Mock-Theater: der Client antwortet mit echtem Python oder
// scheitert wie das Netz (Status 503, unbrauchbare Antwort).
//
//   cd frontend && npm test -- src/lib/components/shared/hub-uebersicht/__tests__/hub_uebersicht_aufloesung_2988.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parse } from 'svelte/compiler';
import { umgebungFuer, effekteVon, findeKomponenten, attributAusdruck, werte, ohneTypen, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { aufgeloestVon, aufloesungPost, live, pythonAufloesung, REPO } from '../../wetter-tab/__tests__/wetterTabDaten.ts';
import { reiter2988 } from '../../wetter-tab/__tests__/reiter2988.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const SHARED = resolve(HIER, '..', '..');
const COMPONENTS = resolve(SHARED, '..');
const HUB_OVERVIEW = join(COMPONENTS, 'trip-detail', 'HubOverview.svelte');
const REITER = join(COMPONENTS, 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte');
const LADER = join(HIER, '..', 'tripAufloesung.ts');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const m: Json = await import(pathToFileURL(join(HIER, '..', 'hubUebersichtModell.ts')).href);
const am: Json = await import(pathToFileURL(join(SHARED, 'wetter-tab', 'ampelModell.ts')).href);
const wz: Json = await import(pathToFileURL(join(SHARED, 'wetter-tab', 'wetterZustand.ts')).href);
const { eintragAusAbo }: Json = await import(pathToFileURL(join(SHARED, 'wetter-tab', 'ampelAufloesung.ts')).href);
const { tr, locale }: Json = await import(pathToFileURL(join(FRONTEND, 'src', 'lib', 'i18n', 'index.ts')).href);
locale.set('de');

const D = live();
const VORLAGEN: Json = am.vorlagenAusTemplates(D.templates);
const EIG: Json = am.eigenschaftenAusKatalog(D.metrics);
const PFAD = '/api/ampel/aufloesung';

/** Das neue Lademodul (fehlt es, ist jeder Test einzeln rot statt die ganze Datei). */
async function lademodul(): Promise<Json> {
	if (!existsSync(LADER)) assert.fail('TDD RED: shared/hub-uebersicht/tripAufloesung.ts fehlt (Lademodul der Trip-Übersicht)');
	return import(pathToFileURL(LADER).href);
}

// ── Fälle ────────────────────────────────────────────────────────────────────

const an = (ampel: Json): string[] => Object.entries(ampel?.metrics ?? {}).filter(([, e]) => (e as Json).enabled).map(([id]) => id);
/** Trip ohne andere Alarmquellen; die Auswahl sind die eingeschalteten Metriken der Vorlage. */
function trip(name: string, dc: Json, extra: Json = {}): Json {
	const vorlage = VORLAGEN[dc?.ampel?.template ?? dc?.preset_name ?? extra.profil ?? 'allgemein'] ?? VORLAGEN.allgemein;
	return {
		id: `t-2988-s4-${name}`,
		name,
		stages: [],
		report_config: { enabled: true, alert_on_changes: false },
		alert_rules: [],
		...extra,
		display_config: { metrics: an(vorlage).map((metric_id) => ({ metric_id, enabled: true })), ...dc }
	};
}
const ZAHL = (t: Json): number => Number(am.alarmZaehler(...((s) => [s.ampel, s.auswahl, EIG])(wz.standAusAbo('route', t, aufgeloestVon(t), {}, { eig: EIG }))).werte?.ausloesend ?? -1);
/** Zwei Vorlagen, deren Zahl sich unterscheidet (sonst bewiese „Zahl folgt der Auflösung" nichts). */
const [A, B] = (() => {
	const ids = Object.keys(VORLAGEN).sort();
	const zahlen = new Map(ids.map((id) => [id, ZAHL(trip('x', { ampel: { template: id } }))]));
	for (const a of ids) for (const b of ids) if (a !== b && zahlen.get(a) !== zahlen.get(b) && an(VORLAGEN[a]).some((x) => an(VORLAGEN[b]).includes(x))) return [a, b];
	assert.fail(`Messaufbau: keine zwei Vorlagen mit verschiedener Zahl ${JSON.stringify([...zahlen])}`);
})();

const FAELLE: Record<string, Json> = {
	nur_vorlage_a: trip('a', { ampel: { template: A } }),
	nur_vorlage_b: trip('b', { ampel: { template: B } }),
	vorlage_mit_abweichungen: trip('abw', { ampel: { template: A, metrics: { gust: { alarm_ab: 'never' }, wind: { alarm_ab: 'red' }, dewpoint: { enabled: true, alarm_ab: 'yellow' } } } }),
	nur_preset_name: trip('pn', { ampel: {}, preset_name: B }),
	nur_profil: trip('pr', { ampel: {} }, { profil: B }),
	ohne_ampel_altbestand: trip('alt', {}),
	ungueltige_ampel: trip('ungueltig', { ampel: { template: A, metrics: { gust: { upper: { yellow: 90, orange: 60 } } } } }),
	// „nie eingestellt": ohne Metrikliste gilt der Register-Standard der Mail (#3047 p5c), nicht die Vorlage.
	nie_eingestellt: { ...trip('nie', { ampel: { template: A } }), display_config: { ampel: { template: A } } }
};

// ── Erwartung aus dem echten Reiter Wetter ───────────────────────────────────

const REITER_AST = (() => {
	const quelle = readFileSync(REITER, 'utf-8');
	return { quelle, ast: parse(quelle, { modern: true }) as Knoten };
})();
const reiterCache = new Map<string, string>();
/** Text der Zähler-Kopfzeile, die der echte Reiter Wetter für diesen Trip zeigt. */
async function reiterText(t: Json): Promise<string> {
	const schluessel = JSON.stringify(t);
	if (!reiterCache.has(schluessel)) {
		const r = await reiter2988('route', t.display_config.ampel ?? {}, { abo: t });
		for (const name of ['anzeige', 'teile', 'zaehler']) {
			const d = (REITER_AST.ast.instance.content.body as Knoten[])
				.filter((s) => s.type === 'VariableDeclaration')
				.flatMap((s) => s.declarations as Knoten[])
				.find((x) => x.id?.name === name);
			assert.ok(d, `Messaufbau: Reiter ohne Herleitung ${name}`);
			r.u[name] = werte(ohneTypen(REITER_AST.quelle, d.init.arguments[0]), r.u);
		}
		const z = r.u.zaehler;
		assert.ok(z?.schluessel, 'Messaufbau: Reiter zeigt keinen Zähler');
		reiterCache.set(schluessel, tr(z.schluessel, z.werte));
	}
	return reiterCache.get(schluessel)!;
}

// ── A. Modell: Zähler und Alarm-Aktiv auf der hereingereichten Auflösung ─────

describe('AC-16 (#2988 S4): Modell der Alarm-Zeile mit aufgelöster Ampel', () => {
	test('messaufbau_vorlagen_unterscheiden_sich', async () => {
		assert.notEqual(await reiterText(FAELLE.nur_vorlage_a), await reiterText(FAELLE.nur_vorlage_b));
	});

	test('ohne_aufloesung_strich', () => {
		for (const t of Object.values(FAELLE)) {
			assert.equal(m.tripAlarmAbText(t, null, EIG), '—');
			assert.equal(m.tripAlarmAbText(t, undefined, EIG), '—');
			assert.equal(m.tripAlarmAbText(t, aufgeloestVon(t), null), '—', 'ohne Metrik-Katalog keine Zahl');
		}
	});

	for (const [name, t] of Object.entries(FAELLE)) {
		test(`zahl_gleich_reiter_wetter_${name}`, async () => {
			const soll = await reiterText(t);
			assert.match(soll, /^\d+ von \d+ Metriken lösen einen Alarm aus/, 'Messaufbau: Reiter zeigt keinen Zähler');
			assert.equal(m.tripAlarmAbText(t, aufgeloestVon(t), EIG), soll);
		});
	}

	test('zahl_folgt_der_hereingereichten_aufloesung', () => {
		// Derselbe Trip mit zwei verschiedenen Auflösungen: die Zeile rechnet nicht selbst nach.
		const t = FAELLE.nur_vorlage_a;
		const ra = aufgeloestVon(FAELLE.nur_vorlage_a);
		const still = Object.fromEntries(an(VORLAGEN[A]).map((id) => [id, { alarm_ab: 'never' }]));
		const rb = aufgeloestVon(trip('b2', { ampel: { template: A, metrics: still } }));
		const text = (r: Json) => {
			const s = wz.standAusAbo('route', t, r, {}, { eig: EIG });
			const z = am.alarmZaehler(s.ampel, s.auswahl, EIG);
			return tr(z.schluessel, z.werte);
		};
		assert.notEqual(text(ra), text(rb), 'Messaufbau: beide Auflösungen geben dieselbe Zahl');
		assert.equal(m.tripAlarmAbText(t, ra, EIG), text(ra));
		assert.equal(m.tripAlarmAbText(t, rb, EIG), text(rb));
	});

	test('aktiv_ohne_aufloesung_wie_ohne_vorlagen', () => {
		const t = trip('aktiv', { ampel: { template: A, metrics: { gust: { alarm_ab: 'red' } } }, metrics: [{ metric_id: 'gust', enabled: true }] });
		assert.equal(m.tripWetterAlarmAktiv(t, aufgeloestVon(t), EIG), true, 'Messaufbau: Böen alarmiert über die Ampel');
		assert.equal(m.tripWetterAlarmAktiv(t, null, EIG), false);
		assert.equal(m.tripWetterAlarmAktiv(t, undefined, EIG), false);
		assert.equal(m.tripWetterAlarmAktiv(t, aufgeloestVon(t), null), false);
		// Andere Quellen gelten auch ohne Auflösung (fehlendes alert_on_changes = an, wie der Loader).
		assert.equal(m.tripWetterAlarmAktiv({ ...t, report_config: { enabled: true } }, null, EIG), true);
	});

	test('aktiv_folgt_der_hereingereichten_aufloesung', () => {
		const t = trip('aktiv2', { ampel: { metrics: { gust: { alarm_ab: 'red' } } }, metrics: [{ metric_id: 'gust', enabled: true }] });
		const nie = aufgeloestVon(trip('nie', { ampel: { metrics: { gust: { alarm_ab: 'never' } } } }));
		const rot = aufgeloestVon(t);
		assert.equal(m.tripWetterAlarmAktiv(t, rot, EIG), true);
		assert.equal(m.tripWetterAlarmAktiv(t, nie, EIG), false, 'die Zeile leitet die Ampel selbst ab statt die Auflösung zu lesen');
	});
});

// ── B. Lademodul: ein Aufruf, Fehler, Änderung, veraltete Antworten ──────────

type Aufruf = { pfad: string; rumpf: Json };
/** Client, dessen Antworten der Test einzeln freigibt (echtes Python) oder scheitern lässt. */
function steuerbarerClient() {
	const aufrufe: Aufruf[] = [];
	const offen: Array<{ rumpf: Json; ok: () => void; fehler: (e?: unknown) => void }> = [];
	const echt = aufloesungPost();
	const client = {
		post: (pfad: string, rumpf: Json) => {
			aufrufe.push({ pfad, rumpf: structuredClone(rumpf) });
			return new Promise((auf, ab) => {
				offen.push({ rumpf, ok: () => echt(pfad, rumpf).then(auf, ab), fehler: (e = { status: 503, error: 'kaputt' }) => ab(e) });
			});
		}
	};
	return { client, aufrufe, offen };
}
function echterClient(antwort?: (rumpf: Json) => Promise<unknown>) {
	const aufrufe: Aufruf[] = [];
	const echt = aufloesungPost();
	return {
		aufrufe,
		client: {
			post: async (pfad: string, rumpf: Json) => {
				aufrufe.push({ pfad, rumpf: structuredClone(rumpf) });
				return antwort ? antwort(rumpf) : echt(pfad, rumpf);
			}
		}
	};
}
const warten = async () => {
	for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0));
};
async function lader(client: Json) {
	const { erstelleTripAufloesung } = await lademodul();
	assert.equal(typeof erstelleTripAufloesung, 'function', 'tripAufloesung.ts exportiert erstelleTripAufloesung nicht');
	const meldungen: Json[] = [];
	const l = erstelleTripAufloesung(client, (s: Json) => meldungen.push(structuredClone(s)));
	return { l, meldungen, letzte: () => meldungen.at(-1) };
}
const T1 = FAELLE.nur_vorlage_a;
const T2 = { ...T1, display_config: { ...T1.display_config, ampel: { template: A, metrics: { gust: { alarm_ab: 'red' }, wind: { alarm_ab: 'never' } } } } };

describe('AC-16 (#2988 S4): Lademodul der Trip-Übersicht', () => {
	test('oeffnen_ein_aufruf_mit_dem_eintrag_des_trips', async () => {
		const c = echterClient();
		const { l, meldungen } = await lader(c.client);
		await l.laden(T1);
		assert.deepEqual(c.aufrufe, [{ pfad: PFAD, rumpf: { eintraege: [eintragAusAbo(T1)] } }]);
		assert.deepEqual(meldungen, [{ zustand: 'laedt', aufgeloest: null }, { zustand: 'geladen', aufgeloest: aufgeloestVon(T1) }]);
		assert.equal(m.tripAlarmAbText(T1, meldungen[1].aufgeloest, EIG), await reiterText(T1));
	});

	test('waehrend_der_abfrage_strich', async () => {
		const s = steuerbarerClient();
		const { l, letzte } = await lader(s.client);
		const fertig = l.laden(T1);
		assert.deepEqual(letzte(), { zustand: 'laedt', aufgeloest: null }, '„laedt" kommt sofort, nicht erst nach der Antwort');
		assert.equal(m.tripAlarmAbText(T1, letzte().aufgeloest, EIG), '—');
		s.offen[0].ok();
		await fertig;
		assert.equal(letzte().zustand, 'geladen');
	});

	for (const [name, antwort] of [
		['503', async () => Promise.reject({ status: 503, error: 'kaputt' })],
		['netzfehler', async () => Promise.reject(new TypeError('Failed to fetch'))],
		['unbrauchbare_antwort', async () => ({ ergebnisse: [] })],
		['antwort_ohne_ampel', async () => ({ ergebnisse: [{ vorlage_id: 'allgemein' }] })]
	] as const) {
		test(`scheitert_${name}_strich_und_nicht_aktiv`, async () => {
			const c = echterClient(antwort);
			const { l, meldungen, letzte } = await lader(c.client);
			await l.laden(T1); // scheitert nie
			assert.equal(c.aufrufe.length, 1);
			assert.deepEqual(meldungen[0], { zustand: 'laedt', aufgeloest: null });
			assert.deepEqual(letzte(), { zustand: 'fehler', aufgeloest: null });
			assert.equal(m.tripAlarmAbText(T1, letzte().aufgeloest, EIG), '—');
		});
	}

	test('nach_fehler_wird_dieselbe_ampel_neu_angefragt', async () => {
		let scheitern = true;
		const echt = aufloesungPost();
		const c = echterClient((r) => (scheitern ? Promise.reject({ status: 503 }) : echt(PFAD, r)));
		const { l, letzte } = await lader(c.client);
		await l.laden(T1);
		scheitern = false;
		await l.laden(structuredClone(T1));
		assert.equal(c.aufrufe.length, 2);
		assert.deepEqual(letzte(), { zustand: 'geladen', aufgeloest: aufgeloestVon(T1) });
	});

	const AENDERUNGEN: [string, Json][] = [
		['ampel', T2],
		['preset_name', { ...T1, display_config: { ...T1.display_config, ampel: {}, preset_name: B } }],
		['profil', { ...T1, profil: B, display_config: { ...T1.display_config, ampel: {} } }]
	];
	for (const [was, t2] of AENDERUNGEN) {
		test(`aenderung_${was}_wird_neu_aufgeloest`, async () => {
			const c = echterClient();
			const { l, letzte } = await lader(c.client);
			await l.laden(T1);
			await l.laden(t2);
			assert.deepEqual(c.aufrufe.map((a) => a.rumpf), [{ eintraege: [eintragAusAbo(T1)] }, { eintraege: [eintragAusAbo(t2)] }]);
			assert.deepEqual(letzte(), { zustand: 'geladen', aufgeloest: aufgeloestVon(t2) });
			assert.equal(m.tripAlarmAbText(t2, letzte().aufgeloest, EIG), await reiterText(t2));
		});
	}

	test('messaufbau_aenderung_der_ampel_aendert_die_zahl', async () => {
		assert.notEqual(await reiterText(T1), await reiterText(T2));
	});

	test('gleiche_ampel_kein_neuer_aufruf', async () => {
		const c = echterClient();
		const { l, meldungen } = await lader(c.client);
		await l.laden(T1);
		// Anderer Name, andere Auswahl, neues Objekt: der Auflösungs-Eintrag bleibt gleich.
		await l.laden({ ...structuredClone(T1), name: 'Umbenannt', display_config: { ...structuredClone(T1.display_config), metrics: [{ metric_id: 'gust', enabled: true }] } });
		assert.equal(c.aufrufe.length, 1);
		assert.equal(meldungen.length, 2, `keine neue Meldung: ${JSON.stringify(meldungen.map((x) => x.zustand))}`);
	});

	test('zurueck_zur_alten_ampel_wird_neu_aufgeloest', async () => {
		const c = echterClient();
		const { l, letzte } = await lader(c.client);
		await l.laden(T1);
		await l.laden(T2);
		await l.laden(T1);
		assert.equal(c.aufrufe.length, 3);
		assert.deepEqual(letzte(), { zustand: 'geladen', aufgeloest: aufgeloestVon(T1) });
	});

	test('veraltete_antwort_kommt_spaeter_und_wird_nicht_uebernommen', async () => {
		const s = steuerbarerClient();
		const { l, meldungen, letzte } = await lader(s.client);
		const erstes = l.laden(T1);
		const zweites = l.laden(T2);
		assert.equal(s.offen.length, 2);
		s.offen[1].ok();
		await zweites;
		assert.deepEqual(letzte(), { zustand: 'geladen', aufgeloest: aufgeloestVon(T2) });
		const vorher = meldungen.length;
		s.offen[0].ok();
		await erstes;
		await warten();
		assert.equal(meldungen.length, vorher, `veraltete Antwort übernommen: ${JSON.stringify(letzte()?.aufgeloest?.ampel?.metrics?.gust)}`);
		assert.deepEqual(letzte(), { zustand: 'geladen', aufgeloest: aufgeloestVon(T2) });
	});

	test('veraltete_antwort_kommt_frueher_und_wird_nicht_uebernommen', async () => {
		const s = steuerbarerClient();
		const { l, meldungen, letzte } = await lader(s.client);
		const erstes = l.laden(T1);
		const zweites = l.laden(T2);
		s.offen[0].ok();
		await erstes;
		await warten();
		assert.deepEqual(letzte(), { zustand: 'laedt', aufgeloest: null }, 'die ältere Antwort wurde angezeigt');
		assert.ok(!meldungen.some((x) => x.zustand === 'geladen'), 'die ältere Antwort wurde gemeldet');
		s.offen[1].ok();
		await zweites;
		assert.deepEqual(letzte(), { zustand: 'geladen', aufgeloest: aufgeloestVon(T2) });
	});

	test('veralteter_fehler_ueberschreibt_die_neue_antwort_nicht', async () => {
		const s = steuerbarerClient();
		const { l, letzte } = await lader(s.client);
		const erstes = l.laden(T1);
		const zweites = l.laden(T2);
		s.offen[1].ok();
		await zweites;
		s.offen[0].fehler();
		await erstes;
		await warten();
		assert.deepEqual(letzte(), { zustand: 'geladen', aufgeloest: aufgeloestVon(T2) });
	});
});

// ── C. Wirkort: trip-detail/HubOverview.svelte ───────────────────────────────

/** Erwartung „aktiv" aus der echten Server-Regel (Python `ampel_alarmquelle_aktiv`). */
function serverAktiv(t: Json): boolean {
	const PY = [
		'import sys, json',
		"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
		'from app.loader import load_trip_from_dict',
		'from services.trip_alert import ampel_alarmquelle_aktiv',
		'print(json.dumps(bool(ampel_alarmquelle_aktiv(load_trip_from_dict(json.loads(sys.stdin.read()))))))'
	].join('\n');
	const out = execFileSync('uv', ['run', 'python3', '-c', PY], { cwd: REPO, encoding: 'utf-8', input: JSON.stringify(t) });
	return JSON.parse(out.trim().split('\n').pop()!);
}

const HO_TRIP: Json = {
	...trip('ho', { ampel: { template: A, metrics: { gust: { alarm_ab: 'red' } } } }),
	stages: [{ id: 'T1', name: 'Tag 1', date: '2099-07-01', waypoints: [{ id: 'G1', name: 'Start', lat: 47.0, lon: 11.0, elevation_m: 1000 }] }]
};
/** Dieselbe Vorlage, alle gewählten Metriken auf „nie": andere Zahl, gleiche Auswahl. */
const HO_TRIP2: Json = {
	...HO_TRIP,
	display_config: { ...HO_TRIP.display_config, ampel: { template: A, metrics: Object.fromEntries(an(VORLAGEN[A]).map((id) => [id, { alarm_ab: 'never' }])) } }
};

const echtesFetch = globalThis.fetch;
afterEach(() => {
	globalThis.fetch = echtesFetch;
	locale.set('de');
});

/** Fetch-Ersatz am Ausgang (`$lib/api.js` ist das echte Modul); die Auflösung rechnet echtes Python. */
/** `halten.an` = true: Antworten der Auflösung warten, bis der Test `halten.offen` aufruft (F013). */
function netz(aufloesungOk: () => boolean = () => true, halten: { an: boolean; offen: Array<() => void> } = { an: false, offen: [] }) {
	const aufrufe: { methode: string; url: string; rumpf: Json }[] = [];
	const antwort = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
	globalThis.fetch = (async (eingabe: unknown, opt?: RequestInit) => {
		const url = String(eingabe);
		const methode = opt?.method ?? 'GET';
		const rumpf = typeof opt?.body === 'string' ? JSON.parse(opt.body) : null;
		aufrufe.push({ methode, url, rumpf });
		if (methode === 'POST' && url === PFAD) {
			if (!aufloesungOk()) return antwort(503, { detail: 'kaputt' });
			const fertig = () => antwort(200, { ergebnisse: pythonAufloesung(rumpf.eintraege) });
			if (halten.an) return new Promise<Response>((auf) => halten.offen.push(() => auf(fertig())));
			return fertig();
		}
		if (methode === 'GET' && url === '/api/templates') return antwort(200, D.templates);
		return antwort(404, { error: 'not found' });
	}) as typeof fetch;
	return { aufrufe, aufloesungen: () => aufrufe.filter((a) => a.url === PFAD) };
}
async function setzen() {
	for (let i = 0; i < 20; i++) await new Promise((r) => setTimeout(r, 0));
}

/** HubOverview mit echtem Instanz-Skript; onMount- und $effect-Rückrufe laufen wie beim Mount. */
async function hubOverview(t: Json) {
	const beimMount: Array<() => unknown> = [];
	const ho = await umgebungFuer(
		HUB_OVERVIEW,
		{
			trip: t,
			onJump: undefined,
			metricsCatalog: D.metrics,
			nextBriefing: null,
			erstelleNaechstesBriefingLader: () => ({ wert: null }),
			onMount: (fn: () => unknown) => {
				beimMount.push(fn);
			},
			untrack: (fn: () => unknown) => fn()
		},
		{ jsAlsTs: true }
	);
	for (const stmt of (ho.ast.instance?.content?.body as Knoten[]) ?? []) {
		const c = stmt.type === 'ExpressionStatement' ? stmt.expression : null;
		if (c?.type === 'CallExpression' && c.callee?.type === 'Identifier' && c.callee.name === 'onMount') werte(ohneTypen(ho.quelle, c), ho.u);
	}
	const effekte = effekteVon(ho.ast, ho.quelle, ho.u);
	const [alarmZeile] = findeKomponenten(ho.ast, 'ReportLine').filter((e) =>
		((e.attributes ?? []) as Knoten[]).some((a) => a.name === 'kind' && a.value?.[0]?.data === 'alert')
	);
	assert.ok(alarmZeile, 'Messaufbau: <ReportLine kind="alert"> fehlt');
	/** Alle `$derived` in Quelltext-Reihenfolge neu auswerten (der Prüfstand wertet sie nur einmal aus). */
	const frisch = () => {
		for (const stmt of (ho.ast.instance?.content?.body as Knoten[]) ?? []) {
			if (stmt.type !== 'VariableDeclaration') continue;
			for (const d of stmt.declarations as Knoten[]) {
				if (d.id?.type !== 'Identifier' || !d.init) continue;
				if (!ho.quelle.slice(d.init.start, d.init.end).startsWith('$derived')) continue;
				ho.u[d.id.name] = werte(ohneTypen(ho.quelle, d.init), ho.u);
			}
		}
	};
	const zeile = () => {
		frisch();
		const p = (name: string) => werte(attributAusdruck(alarmZeile, ho.quelle, name)!, ho.u);
		return { time: p('time') as string, active: p('active') as boolean };
	};
	return {
		u: ho.u,
		zeile,
		mounten: async () => {
			for (const fn of beimMount) fn();
			for (const fn of effekte) fn();
			await setzen();
		},
		/** Neuer `trip` (wie ein Prop-Update): Effekte laufen erneut. */
		tripAendern: async (neu: Json) => {
			ho.u.trip = neu;
			for (const fn of effekte) fn();
			await setzen();
		}
	};
}

describe('AC-16 (#2988 S4): Alarm-Zeile der Trip-Übersicht am Wirkort', () => {
	test('oeffnen_strich_dann_zahl_des_reiters_und_aktiv_wie_der_server', async () => {
		const n = netz();
		const ho = await hubOverview(HO_TRIP);
		assert.deepEqual(ho.zeile(), { time: '—', active: false }, 'vor der Antwort keine geratene Zahl');
		await ho.mounten();
		assert.deepEqual(n.aufloesungen().map((a) => a.rumpf), [{ eintraege: [eintragAusAbo(HO_TRIP)] }], `Abrufe: ${JSON.stringify(n.aufrufe.map((a) => `${a.methode} ${a.url}`))}`);
		const soll = serverAktiv(HO_TRIP);
		assert.equal(soll, true, 'Messaufbau: der Server alarmiert über die Ampel');
		assert.deepEqual(ho.zeile(), { time: await reiterText(HO_TRIP), active: soll });
	});

	test('aufloesung_scheitert_strich_und_nicht_aktiv', async () => {
		const n = netz(() => false);
		const ho = await hubOverview(HO_TRIP);
		await ho.mounten();
		assert.equal(n.aufloesungen().length, 1);
		assert.deepEqual(ho.zeile(), { time: '—', active: false });
	});

	test('aenderung_der_trip_ampel_neu_aufgeloest', async () => {
		const n = netz();
		const ho = await hubOverview(HO_TRIP);
		await ho.mounten();
		await ho.tripAendern(HO_TRIP2);
		assert.deepEqual(n.aufloesungen().map((a) => a.rumpf), [{ eintraege: [eintragAusAbo(HO_TRIP)] }, { eintraege: [eintragAusAbo(HO_TRIP2)] }]);
		const soll = await reiterText(HO_TRIP2);
		assert.notEqual(soll, await reiterText(HO_TRIP), 'Messaufbau: beide Ampeln geben dieselbe Zahl');
		assert.equal(ho.zeile().time, soll);
	});

	test('gleiche_ampel_kein_zweiter_aufruf', async () => {
		const n = netz();
		const ho = await hubOverview(HO_TRIP);
		await ho.mounten();
		await ho.tripAendern({ ...structuredClone(HO_TRIP), name: 'Umbenannt' });
		assert.equal(n.aufloesungen().length, 1, `Abrufe: ${JSON.stringify(n.aufrufe.map((a) => `${a.methode} ${a.url}`))}`);
		assert.equal(ho.zeile().time, await reiterText(HO_TRIP));
	});

	// F013: während die neue Auflösung aussteht, zeigt die Zeile keine Zahl der alten Ampel.
	test('aenderung_strich_bis_die_neue_antwort_kommt', async () => {
		const halten = { an: false, offen: [] as Array<() => void> };
		const n = netz(() => true, halten);
		const ho = await hubOverview(HO_TRIP);
		await ho.mounten();
		assert.equal(ho.zeile().time, await reiterText(HO_TRIP), 'Messaufbau: erste Antwort nicht übernommen');
		halten.an = true;
		await ho.tripAendern(HO_TRIP2);
		assert.equal(n.aufloesungen().length, 2, 'Messaufbau: keine zweite Anfrage');
		assert.equal(halten.offen.length, 1, 'Messaufbau: Antwort nicht zurückgehalten');
		assert.deepEqual(ho.zeile(), { time: '—', active: false }, 'veraltete Zahl während die neue Auflösung aussteht');
		halten.offen[0]();
		await setzen();
		const soll = await reiterText(HO_TRIP2);
		assert.notEqual(soll, await reiterText(HO_TRIP), 'Messaufbau: beide Ampeln geben dieselbe Zahl');
		assert.equal(ho.zeile().time, soll);
	});

	// F014: die Vorlage kommt auch ohne ampel.template aus `profil` bzw. `display_config.preset_name`.
	const OHNE_TEMPLATE = (name: string, dc: Json, extra: Json = {}): Json => ({
		...HO_TRIP,
		id: `t-2988-s4-ho-${name}`,
		...extra,
		display_config: { metrics: HO_TRIP.display_config.metrics, ...dc }
	});
	const HO_ALLGEMEIN = OHNE_TEMPLATE('allgemein', { ampel: {} });
	const HO_PRESET = (() => {
		const id = Object.keys(VORLAGEN).sort().find((v) => v !== 'allgemein' && ZAHL(OHNE_TEMPLATE(v, { ampel: {}, preset_name: v })) !== ZAHL(HO_ALLGEMEIN));
		assert.ok(id, 'Messaufbau: keine Vorlage mit anderer Zahl als „allgemein"');
		return OHNE_TEMPLATE('preset', { ampel: {}, preset_name: id });
	})();
	// Nur `profil`: summer_trekking (→ alpen-trekking) hat überall dieselben „Alarm ab"-Stufen wie „allgemein"
	// und bewiese die Vorlagen-Wahl nicht; daher das erste Profil, dessen Zahl abweicht.
	const HO_PROFIL = (() => {
		for (const profil of ['summer_trekking', ...Object.keys(VORLAGEN).sort()]) {
			if (profil === 'allgemein') continue;
			const t = OHNE_TEMPLATE('profil', { ampel: {} }, { profil });
			if (ZAHL(t) !== ZAHL({ ...t, profil: undefined })) return t;
		}
		assert.fail('Messaufbau: kein Profil, das anders zählt als „allgemein"');
	})();
	const HO_PROFIL_ALLGEMEIN = { ...HO_PROFIL, profil: undefined };
	for (const [name, t, allgemein] of [['nur_profil', HO_PROFIL, HO_PROFIL_ALLGEMEIN], ['nur_preset_name', HO_PRESET, HO_ALLGEMEIN]] as const) {
		test(`wirkort_${name}_zahl_gleich_reiter_wetter`, async () => {
			netz();
			const soll = await reiterText(t);
			assert.notEqual(soll, await reiterText(allgemein), 'Messaufbau: Zahl gleich „allgemein", die Vorlagen-Wahl bliebe unbewiesen');
			const ho = await hubOverview(t);
			await ho.mounten();
			assert.equal(ho.zeile().time, soll);
		});
	}
});
