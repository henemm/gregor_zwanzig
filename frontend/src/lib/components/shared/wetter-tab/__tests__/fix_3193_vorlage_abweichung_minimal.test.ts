// Fix #3193 (Epic #2913): Vorlagen-Abweichung im Reiter Wetter minimal und einheitlich.
// Spec: docs/specs/modules/fix_3193_vorlage_abweichung_minimal.md (AC-1 bis AC-6, Test Plan Tests 1-6).
//
// Befund: Zaehler, Abweichungsmenge und Speicherweg messen gegen verschiedene Basen. Nach „Übernehmen“
// bzw. „Auf Vorlage zurücksetzen“ speichert der Trip die abgeleiteten Kinder (`temperature_day_*`,
// `wind_chill_*`) als `{enabled:true}`, der Orts-Vergleich `temperature_night: {enabled:false}` und
// zeigt „1 Abweichung“ mit wirkungslosem Zurücksetzen-Knopf.
//
// Gemessen dort, wo es WIRKT: im echten Instanz-Skript von WetterTabInhalt (Laden mit den echten
// `/api/templates`-, `/api/metrics`- und `/api/compare/metrics`-Antworten aus dem Python-Core), Gesten
// `onUebernehmen`/`onZuruecksetzen`/`entfernen`/`aendern` der Komponente, Zaehler = der Ausdruck, den die
// Komponente als `abweichungen` an die VorlageKarte gibt, Nutzlast = `tripNutzlast`/`vergleichNutzlast`
// mit den Speicher-Optionen der Komponente selbst (`optionen()`). Kein Mock.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test src/lib/components/shared/wetter-tab/__tests__/fix_3193_vorlage_abweichung_minimal.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { WETTER_TAB, live, liveVergleichsKatalog, vergleichsKatalogFetch } from './wetterTabDaten.ts';
import { attributAusdruck, findeKomponenten, ohneTypen, umgebungFuer, werte, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { aktiveMetriken, AUSWAHL_ABLEITUNG, vorlagenAusTemplates, type Ampel } from '../ampelModell.ts';
import { tripNutzlast, vergleichNutzlast } from '../wetterTabSpeicherung.ts';
import { abweichungenVon, mitVorlage, standAusAbo } from '../wetterZustand.ts';

type Kontext = 'route' | 'vergleich';

const LIVE = live();
const VORLAGEN = vorlagenAusTemplates(LIVE.templates as never);
const VORLAGEN_IDS = Object.keys(VORLAGEN);
const KATALOG_IDS = new Set<string>(
	(liveVergleichsKatalog().metrics as Knoten[]).flatMap((m) => (m.metric_id ? [String(m.metric_id)] : []))
);
const TAB = path.resolve(WETTER_TAB, '../../organisms/wetter-tab/WetterTabInhalt.svelte');
const api = {
	get: async (pfad: string) => {
		if (pfad === '/api/metrics') return LIVE.metrics;
		if (pfad === '/api/templates') return LIVE.templates;
		if (pfad === '/api/metric-presets') return [];
		throw new Error(`unerwartet: ${pfad}`);
	},
	put: async () => {
		throw new Error('Messaufbau: kein Netz-Schreiben im Kern-Test');
	}
};

const aktiv = (id: string) => aktiveMetriken(VORLAGEN[id]);

type Reiter = {
	u: Knoten;
	/** Zaehler, wie die VorlageKarte ihn bekommt (Picker „unverändert“ ⇔ 0). */
	zahl: () => number;
	/** Gespeicherte `ampel` und Auswahl-Liste, wie der Speicherer der Komponente sie senden wuerde. */
	nutzlast: () => { ampel: Ampel; voll: Knoten };
	uebernehmen: (id: string) => void;
	zuruecksetzen: () => void;
	geplant: () => number;
	/** Ampel, die die Komponente als `aboAmpel` an die VorlageKarte gibt (Dialog „Als eigene Vorlage speichern“). */
	aboAmpel: () => Ampel;
};

/** Reiter laden (Instanz-Pruefstand). `geplant()` zaehlt, wie oft der Speicherer einen Schreibvorgang plant. */
async function reiter(context: Kontext, abo: Record<string, unknown>): Promise<Reiter> {
	let geplant = 0;
	const saveController = {
		schedule: () => {
			geplant++;
		}
	};
	const { u, ast, quelle } = await umgebungFuer(TAB, {
		context,
		trip: context === 'route' ? abo : undefined,
		preset: context === 'vergleich' ? abo : undefined,
		createMode: false,
		saveController,
		enqueueHubWrite: undefined,
		onTripUpdate: undefined,
		onCompareUpdate: undefined,
		onAnlegeStand: undefined,
		api
	});
	const z = vergleichsKatalogFetch();
	try {
		await u.laden();
	} finally {
		z();
	}
	assert.equal(u.phase, 'bereit', 'Messaufbau: Reiter hat nicht geladen');
	const herleitung = (name: string): string => {
		for (const stmt of ast.instance.content.body as Knoten[]) {
			if (stmt.type !== 'VariableDeclaration') continue;
			for (const d of stmt.declarations as Knoten[]) if (d.id?.name === name) return ohneTypen(quelle, d.init.arguments[0]);
		}
		throw new Error(`keine Herleitung ${name}`);
	};
	const karte = findeKomponenten(ast, 'VorlageKarte')[0];
	const prop = attributAusdruck(karte, quelle, 'abweichungen')!;
	const attr = (name: string): string => {
		const a = (karte.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name)!;
		return ohneTypen(quelle, a.value.expression);
	};
	/** Der Pruefstand wertet `$derived` nur einmal (vor dem Laden) aus: vor jeder Geste und Messung neu rechnen. */
	const frisch = () => {
		for (const n of ['anzeige', 'vorlagen', 'abweichungen']) u[n] = werte(herleitung(n), u);
	};
	const zahl = () => {
		frisch();
		return werte(prop, u) as number;
	};
	const nutzlast = () => {
		const o = u.optionen();
		if (context === 'route') {
			const n = tripNutzlast(o);
			return { ampel: n.weatherConfig.ampel as Ampel, voll: n as Knoten };
		}
		const n = vergleichNutzlast(o);
		return { ampel: (n.display_config as Knoten).ampel as Ampel, voll: n as Knoten };
	};
	return {
		u,
		zahl,
		nutzlast,
		uebernehmen: (id) => {
			frisch();
			(werte(attr('onUebernehmen'), u) as (id: string) => void)(id);
		},
		zuruecksetzen: () => {
			frisch();
			(werte(attr('onZuruecksetzen'), u) as () => void)();
		},
		geplant: () => geplant,
		aboAmpel: () => {
			frisch();
			u.aboAmpel = werte(herleitung('aboAmpel'), u);
			return werte(attributAusdruck(karte, quelle, 'aboAmpel')!, u) as Ampel;
		}
	};
}

/** Abo genau „nach Vorlage“ angelegt (so seedet auch die Staging-E2E-Spec): Grundauswahl = aktive
 *  Metriken der Vorlage (im Vergleich inkl. `temperature_night`, das E6 gesperrt erhaelt). */
function aboNachVorlage(context: Kontext, id: string, ampelExtra: Record<string, unknown> = {}, auswahl = aktiv(id)): Record<string, unknown> {
	const ampel = { template: id, ...ampelExtra };
	return context === 'route'
		? { id: `t-${id}`, name: id, stages: [], display_config: { metrics: auswahl.map((metric_id) => ({ metric_id, enabled: true })), ampel }, report_config: {} }
		: { id: `p-${id}`, name: id, location_ids: [], display_config: { active_metrics: auswahl.map((metric_id) => ({ metric_id, aggregation: 'max' })), ampel } };
}

const andereAls = (id: string) => (id === 'alpen-trekking' ? 'wandern' : 'alpen-trekking');
/** Eine Alarmstufe, die sicher von der Vorlage abweicht. */
const andereStufe = (vid: string, id: string) => (VORLAGEN[vid]?.metrics?.[id]?.alarm_ab === 'red' ? 'never' : 'red');

describe('Messaufbau', () => {
	test('vorlagen_und_katalog_tragen_den_befund', () => {
		assert.ok(VORLAGEN_IDS.includes('wandern') && VORLAGEN_IDS.includes('alpen-trekking'), VORLAGEN_IDS.join(','));
		assert.ok(KATALOG_IDS.size > 0, 'Vergleichs-Katalog leer');
		assert.ok(KATALOG_IDS.has('gust'), 'Boeen nicht im Vergleichs-Katalog');
		assert.ok(!KATALOG_IDS.has('temperature_night'), 'temperature_night ist ausgebbar — Vergleichsfall misst nichts');
		assert.ok(aktiv('wandern').includes('temperature_night'), 'wandern schaltet temperature_night nicht ein');
		const kinder = AUSWAHL_ABLEITUNG.route(aktiv('wandern')).filter((k) => !aktiv('wandern').includes(k));
		assert.ok(kinder.includes('temperature_day_low'), `wandern leitet kein temperature_day_low ab: ${kinder.join(',')}`);
	});
});

for (const context of ['route', 'vergleich'] as const) {
	describe(`Test 1 (${context}): Übernehmen und Zurücksetzen speichern keine Abweichung (AC-1/AC-2)`, () => {
		for (const v of VORLAGEN_IDS) {
			test(`${context}_uebernehmen_${v}_null_abweichungen_und_leere_ampel`, async () => {
				const r = await reiter(context, aboNachVorlage(context, andereAls(v)));
				r.uebernehmen(v);
				assert.equal(r.u.stand.vorlageId, v, 'Messaufbau: Vorlage nicht übernommen');
				assert.equal(r.zahl(), 0, `${context}/${v}: Picker zeigt nicht „unverändert“`);
				assert.deepEqual(r.nutzlast().ampel, { template: v }, `${context}/${v}: gespeicherte Abweichung nicht leer`);
			});
			test(`${context}_zuruecksetzen_${v}_null_abweichungen_und_leere_ampel`, async () => {
				const r = await reiter(context, aboNachVorlage(context, v));
				r.u.aendern(r.u.Z.mitAlarmAb(r.u.stand, 'gust', andereStufe(v, 'gust')));
				assert.ok(r.zahl() >= 1, 'Messaufbau: geänderte Alarmstufe ist eine Abweichung');
				r.zuruecksetzen();
				assert.equal(r.zahl(), 0, `${context}/${v}: Zurücksetzen-Knopf bliebe stehen`);
				assert.deepEqual(r.nutzlast().ampel, { template: v }, `${context}/${v}: gespeicherte Abweichung nach Zurücksetzen nicht leer`);
			});
		}
	});
}

describe('Tests 2/3: bewusstes „−“ bleibt genau eine Abweichung (AC-3)', () => {
	test('trip_minus_temperature_day_low_genau_eine_abweichung', async () => {
		const r = await reiter('route', aboNachVorlage('route', 'alpen-trekking'));
		r.uebernehmen('wandern');
		assert.ok(r.u.stand.auswahl.includes('temperature_day_low'), 'Messaufbau: Kind nicht abgeleitet');
		r.u.entfernen('temperature_day_low');
		assert.equal(r.zahl(), 1);
		assert.deepEqual(r.nutzlast().ampel, { template: 'wandern', metrics: { temperature_day_low: { enabled: false } } });
	});
	test('vergleich_minus_gust_genau_eine_abweichung', async () => {
		const r = await reiter('vergleich', aboNachVorlage('vergleich', 'alpen-trekking'));
		r.uebernehmen('wandern');
		assert.ok(r.u.stand.auswahl.includes('gust'), 'Messaufbau: Boeen nicht gewählt');
		r.u.entfernen('gust');
		assert.equal(r.zahl(), 1);
		assert.deepEqual(r.nutzlast().ampel, { template: 'wandern', metrics: { gust: { enabled: false } } });
	});
});

describe('Test 4: Vergleichs-Bestand mit gesperrtem temperature_night (AC-4/AC-6)', () => {
	test('vergleich_bestand_temperature_night_bleibt_gesperrt_und_zaehlt_nicht', async () => {
		const r = await reiter('vergleich', aboNachVorlage('vergleich', 'wandern'));
		assert.ok(r.u.stand.auswahl.includes('temperature_night'), 'gesperrte Bestandsgröße ging beim Laden verloren');
		assert.equal(r.zahl(), 0);
		assert.deepEqual(r.nutzlast().ampel, { template: 'wandern' });
		assert.equal(r.geplant(), 0, 'Laden plant ein Speichern ohne Nutzeraktion');
		const liste = ((r.nutzlast().voll.display_config as Knoten).active_metrics as Knoten[]).map((m) => m.metric_id);
		assert.ok(liste.includes('temperature_night'), 'gesperrte Bestandsgröße fehlt in der gespeicherten Auswahl');
	});
});

/** Bestand aus dem Bug: Rausch-Eintraege, die der alte Speicherweg geschrieben hat. */
const RAUSCH: Record<Kontext, { ampel: Record<string, unknown>; auswahl: string[]; extra: Record<string, unknown> }> = {
	route: {
		ampel: { metrics: { temperature_day_low: { enabled: true }, temperature_day_high: { enabled: true } } },
		auswahl: AUSWAHL_ABLEITUNG.route(aktiv('wandern')),
		extra: { report_config: { day_window_start_hour: 6, day_window_end_hour: 20, send_evening: true } }
	},
	vergleich: {
		ampel: { metrics: { temperature_night: { enabled: false } } },
		auswahl: aktiv('wandern').filter((id) => KATALOG_IDS.has(id)),
		extra: { day_window_start_hour: 6, day_window_end_hour: 20 }
	}
};

for (const context of ['route', 'vergleich'] as const) {
	describe(`Test 5 (${context}): Bestandsdaten mit Rausch (AC-4/AC-5)`, () => {
		const abo = () => ({ ...aboNachVorlage(context, 'wandern', RAUSCH[context].ampel, RAUSCH[context].auswahl), ...RAUSCH[context].extra });
		test(`${context}_rausch_bestand_laedt_mit_null_und_schreibt_nichts`, async () => {
			const r = await reiter(context, abo());
			assert.equal(r.zahl(), 0, `${context}: Rausch-Bestand zeigt Abweichungen`);
			assert.equal(r.geplant(), 0, 'Laden plant ein Speichern ohne Nutzeraktion');
		});
		test(`${context}_rausch_weg_nach_alarmstufe_uebrige_felder_erhalten`, async () => {
			const r = await reiter(context, abo());
			const vorher = structuredClone(r.nutzlast().voll);
			const stufe = andereStufe('wandern', 'gust');
			r.u.aendern(r.u.Z.mitAlarmAb(r.u.stand, 'gust', stufe));
			assert.equal(r.geplant(), 1, 'Messaufbau: Alarmstufe löst kein Speichern aus');
			assert.equal(r.zahl(), 1);
			const nachher = r.nutzlast();
			assert.deepEqual(nachher.ampel, { template: 'wandern', metrics: { gust: { alarm_ab: stufe } } }, `${context}: Rausch-Einträge noch in der Nutzlast`);
			// Read-Modify-Write: ausser der Ampel bleibt jedes Feld der Nutzlast unveraendert.
			const ohneAmpel = (n: Knoten): Knoten => {
				const k = structuredClone(n);
				if (context === 'route') delete k.weatherConfig.ampel;
				else delete k.display_config.ampel;
				return k;
			};
			assert.deepEqual(ohneAmpel(nachher.voll), ohneAmpel(vorher));
			// #3297: Teilfeld — der Trip-Rumpf traegt in report_config nur das Tagesfenster; Fremdfelder
			// (send_evening) bleiben per Go-Merge stehen und werden nicht mitgesendet.
			if (context === 'route') assert.equal('send_evening' in nachher.voll.tripFelder.report_config, false);
			else assert.equal(nachher.voll.day_window_start_hour, 6);
		});
	});
}

// Fix-Loop 1 (Adversary F001): „Als eigene Vorlage speichern“ bekommt `aboAmpel` — dieselbe Basis wie
// Zaehler und Speicherweg. Gemessen an der Prop der VorlageKarte: die eingeschalteten Metriken der
// Ampel sind genau die Auswahl nach „Übernehmen“ (Trip: abgeleitete Kinder an; Vergleich: das nicht
// ausgebbare temperature_night neutral, d. h. aus, weil E6 es aus der Auswahl nimmt).
describe('Test 7: eigene Vorlage (aboAmpel) misst gegen die Vorlage im Kontext', () => {
	test('trip_uebernehmen_wandern_aboampel_mit_abgeleiteten_kindern', async () => {
		const r = await reiter('route', aboNachVorlage('route', 'alpen-trekking'));
		r.uebernehmen('wandern');
		const a = r.aboAmpel();
		assert.equal(a.template, 'wandern');
		assert.equal(a.metrics?.temperature_day_low?.enabled, true, 'abgeleitetes Kind fehlt in der eigenen Vorlage');
		assert.equal(a.metrics?.temperature_day_high?.enabled, true, 'abgeleitetes Kind fehlt in der eigenen Vorlage');
		assert.deepEqual(aktiveMetriken(a).sort(), [...r.u.stand.auswahl].sort());
	});
	test('vergleich_uebernehmen_wandern_aboampel_temperature_night_neutral', async () => {
		const r = await reiter('vergleich', aboNachVorlage('vergleich', 'alpen-trekking'));
		r.uebernehmen('wandern');
		assert.ok(!r.u.stand.auswahl.includes('temperature_night'), 'Messaufbau: E6 filtert temperature_night nicht');
		const a = r.aboAmpel();
		assert.equal(a.template, 'wandern');
		assert.equal(a.metrics?.temperature_night?.enabled, false, 'nicht ausgebbare Größe in der eigenen Vorlage eingeschaltet');
		assert.deepEqual(aktiveMetriken(a).sort(), [...r.u.stand.auswahl].sort());
	});
});

describe('Test 6: Vergleichs-Katalog unbekannt — Basis bleibt die Rohvorlage', () => {
	test('vergleich_ohne_katalog_kein_absturz', () => {
		const s0 = standAusAbo('vergleich', aboNachVorlage('vergleich', 'alpen-trekking'), VORLAGEN, {});
		const s = mitVorlage(s0, 'wandern', VORLAGEN, 'vergleich', {});
		assert.ok(s.auswahl.includes('temperature_night'), 'ohne Katalog wird nichts herausgefiltert');
		assert.equal(abweichungenVon(s, VORLAGEN, 'vergleich'), 0);
		const n = vergleichNutzlast({ client: null as never, stand: () => s, vorlagen: () => VORLAGEN, abo: () => aboNachVorlage('vergleich', 'alpen-trekking') });
		assert.deepEqual((n.display_config as Knoten).ampel, { template: 'wandern' });
	});
});
