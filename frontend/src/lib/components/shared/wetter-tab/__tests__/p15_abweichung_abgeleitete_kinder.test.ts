// Issue #3047 Runde 7, Nachgang zu p5c (CI-e2e WW-3c/AC-1 rot): seit p5c leitet der Trip-Reiter wie
// Python (`loader._append_derived_metrics`) die Kind-Groessen eines gewaehlten Elters ab (Nacht-Tiefst,
// Tagestief/-hoch, Windchill-Kinder). Die Vorlagen schalten diese Kinder nicht ausdruecklich ein; die
// Abweichungszahl des Pickers zaehlte sie deshalb als „hinzugefuegt“ — ein Trip genau nach Vorlage
// zeigte „2 Abweichungen“, „Auf ‚…‘ zuruecksetzen“ blieb wirkungslos (Spec feat_2794 AC-12/AC-28).
// Soll: ein abgeleitetes Kind gilt im Trip als Teil der Vorlage; erst ein bewusstes „−“ weicht ab.
// Der Vergleich leitet nichts ab und zaehlt unveraendert.
//
// Gemessen wird dort, wo die Zahl WIRKT: im echten Instanz-Skript von WetterTabInhalt (Laden mit den
// echten `/api/templates`/`/api/metrics`-Antworten, Gesten `entfernen`/`onZuruecksetzen`) und an dem
// Ausdruck, den die Komponente als `abweichungen` an die VorlageKarte gibt. Kein Mock.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/p15_abweichung_abgeleitete_kinder.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { WETTER_TAB, live, vergleichsKatalogFetch } from './wetterTabDaten.ts';
import { attributAusdruck, findeKomponenten, ohneTypen, umgebungFuer, werte, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { aktiveMetriken, vorlagenAusTemplates } from '../ampelModell.ts';

const LIVE = live();
const VORLAGEN = vorlagenAusTemplates(LIVE.templates as never);
const TAB = path.resolve(WETTER_TAB, '../../organisms/wetter-tab/WetterTabInhalt.svelte');
const KINDER = ['temperature_night', 'temperature_day_low', 'temperature_day_high', 'wind_chill_night', 'wind_chill_day_low', 'wind_chill_day_high'];
const api = {
	get: async (pfad: string) => {
		if (pfad === '/api/metrics') return LIVE.metrics;
		if (pfad === '/api/templates') return LIVE.templates;
		if (pfad === '/api/metric-presets') return [];
		throw new Error(`unerwartet: ${pfad}`);
	}
};

type Reiter = { u: Knoten; zahl: () => number; zuruecksetzen: () => void };

/** Reiter laden; `zahl()` rechnet die `$derived`-Kette bis zu dem `abweichungen`, das die
 *  VorlageKarte bekommt, mit dem aktuellen Stand neu (der Pruefstand wertet `$derived` sonst nur einmal). */
async function reiter(context: 'route' | 'vergleich', abo: Record<string, unknown>): Promise<Reiter> {
	const { u, ast, quelle } = await umgebungFuer(TAB, {
		context,
		trip: context === 'route' ? abo : undefined,
		preset: context === 'vergleich' ? abo : undefined,
		createMode: false,
		saveController: undefined,
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
	const zahl = () => {
		for (const n of ['anzeige', 'vorlagen', 'abweichungen']) u[n] = werte(herleitung(n), u);
		return werte(prop, u) as number;
	};
	const zuruecksetzen = () => (werte(attr('onZuruecksetzen'), u) as () => void)();
	return { u, zahl, zuruecksetzen };
}

/** Trip, dessen Grundauswahl genau die Vorlage ist (so legt sie die Vorlage an: Eltern ohne Kinder). */
const tripNachVorlage = (id: string) => ({
	id: `t-${id}`,
	name: id,
	stages: [],
	display_config: { metrics: aktiveMetriken(VORLAGEN[id]).map((metric_id) => ({ metric_id, enabled: true })), ampel: { template: id } },
	report_config: {}
});

const MIT_KINDERN = Object.keys(VORLAGEN).filter((id) => aktiveMetriken(VORLAGEN[id]).some((m) => m === 'temperature' || m === 'wind_chill'));

describe('p15 Trip: abgeleitete Kinder sind keine Abweichung von der Vorlage', () => {
	test('messaufbau_vorlagen_mit_elter_ohne_kinder', () => {
		assert.ok(MIT_KINDERN.includes('wandern') && MIT_KINDERN.includes('alpen-trekking'), MIT_KINDERN.join(','));
		for (const id of MIT_KINDERN) {
			const aktiv = aktiveMetriken(VORLAGEN[id]);
			assert.ok(KINDER.some((k) => !aktiv.includes(k)), `${id}: Vorlage schaltet schon alle Kinder ein — Fall misst nichts`);
		}
	});
	for (const id of MIT_KINDERN) {
		test(`trip_nach_vorlage_${id}_null_abweichungen`, async () => {
			const r = await reiter('route', tripNachVorlage(id));
			assert.ok(r.u.stand.auswahl.some((m: string) => KINDER.includes(m)), 'Messaufbau: Reiter zeigt keine abgeleiteten Kinder');
			assert.equal(r.zahl(), 0);
		});
		test(`trip_zuruecksetzen_${id}_null_abweichungen`, async () => {
			const r = await reiter('route', tripNachVorlage(id));
			r.u.entfernen('gust');
			assert.equal(r.zahl(), 1, 'Messaufbau: „−“ an Boeen ist eine Abweichung');
			r.zuruecksetzen();
			assert.equal(r.zahl(), 0);
		});
	}
	test('trip_kind_bewusst_entfernt_ist_eine_abweichung', async () => {
		const r = await reiter('route', tripNachVorlage('wandern'));
		// ein nur abgeleitetes Kind (die Vorlage nennt es nicht) — dessen „−“ ist die zu messende Abweichung
		const kind = KINDER.find((k) => r.u.stand.auswahl.includes(k) && !aktiveMetriken(VORLAGEN.wandern).includes(k))!;
		assert.ok(kind, 'Messaufbau: kein nur abgeleitetes Kind');
		r.u.entfernen(kind);
		assert.equal(r.zahl(), 1, `„−“ an ${kind}`);
	});
	test('trip_grenze_geaendert_zaehlt_weiter', async () => {
		const abo = tripNachVorlage('wandern');
		(abo.display_config.ampel as Knoten).metrics = { gust: { upper: { yellow: 40, orange: 55, red: 75 } } };
		const r = await reiter('route', abo);
		assert.equal(r.zahl(), 1);
	});
});

describe('p15 Vergleich: leitet nichts ab, Zahl unveraendert', () => {
	test('vergleich_nach_vorlage_wandern_null_abweichungen', async () => {
		const r = await reiter('vergleich', {
			id: 'o',
			name: 'o',
			location_ids: [],
			display_config: { active_metrics: aktiveMetriken(VORLAGEN.wandern).map((metric_id) => ({ metric_id, aggregation: 'max' })), ampel: { template: 'wandern' } }
		});
		assert.deepEqual(r.u.stand.auswahl, aktiveMetriken(VORLAGEN.wandern), 'Vergleich leitet keine Kinder ab');
		assert.equal(r.zahl(), 0);
		r.u.entfernen('gust');
		assert.equal(r.zahl(), 1);
	});
});
