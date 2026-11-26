// TDD RED — Issue #3298 (Epic #3122, Spec-AC-38 zweiter Teil): der Ortsvergleich sendet beim
// Anlegen und Speichern keinen der zehn Altschluessel mehr (insbesondere `outlook_enabled`), die
// Hydration liest sie nicht, die Wetter-Whitelist kennt sie nicht.
// Spec: docs/specs/modules/feat_3298_altfeld_typen_sperre.md (AC-2, AC-3, AC-4)
//
// Reine Verhaltenstests ohne Mocks: die echten Bildner/Speicherwege werden mit echten Eingaben
// getrieben; die Reiter-PUTs laufen ueber den echten Speicherweg (`reiterAufbau`) gegen den
// Go-Merge-Ersatzserver (goMergeServerPruefstand.ts) mit ZWEI Nutzern; gemessen wird der
// tatsaechlich gesendete Anfrage-Rumpf und der gemergte Bestand danach.
//
// RED heute (Stand vor dem Rueckbau):
//   - AC-2: Anlege-Rumpf (baueVergleichAnlegeRumpf/legeVergleichAn/buildNewComparePresetPayload)
//     traegt `outlook_enabled`; Feldsatz traegt outlookEnabled + camelCase-Wizardfelder;
//     Reiter Wetter-Metriken (Zustellung) und flushPendingLayoutSave senden `outlook_enabled`;
//     buildComparePresetSavePayload ueberschreibt den Bestand mit edits.outlookEnabled.
//   - AC-3: hydrateLayoutFieldsFromPreset liest hourly_/outlook_*-Altfelder und outlook_enabled;
//     hydrateChannelActiveMetricsFromPreset/compareChannelActiveMetricsFromStored existieren noch;
//     feldsatzAusVorlage uebernimmt Altwerte.
//   - AC-4: WETTER_DISPLAY_KEYS enthaelt channel_layouts/outlook_metrics/outlook_metric_formats.
// Schon GRUEN (Regressionsschutz, strukturell sauber seit #3276): Reiter Alarme, Versand,
// Wertebereiche senden keinen Altschluessel und lassen den Bestand beider Nutzer unberuehrt.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/compare/feat3298_vergleich_ohne_altfelder.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import {
	baueVergleichAnlegeRumpf,
	buildComparePresetSavePayload,
	buildNewComparePresetPayload,
	compareFeldsatzStandard,
	legeVergleichAn,
	type CompareEditorEdits,
	type NewComparePresetFields
} from './compareEditorSave.ts';
import { hydrateLayoutFieldsFromPreset } from '../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import { erstelleZustellungSpeicherung } from '../shared/zustellung-tab/zustellungSpeicherung.ts';
import { standAusPreset } from '../shared/zustellung-tab/zustellungModell.ts';
import { createPutQueue } from './compareHubPersistenz.ts';
import { createController } from '../shared/__tests__/versandVergleichPruefstand.ts';
import { feldsatzAusVorlage } from '../compare-new/compareNewVorlage.ts';
import { pickEigenfelder, WETTER_DISPLAY_KEYS } from '../shared/pickEigenfelder.ts';
import { api } from '../../api.ts';
import { clearEtagRegistry } from '../../etagRegistry.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer
} from '../shared/__tests__/goMergeServerPruefstand.ts';
import { REITER, reiterAufbau } from '../shared/__tests__/compareReiterAufbauPruefstand.ts';
import type { ComparePreset, Location } from '../../types.ts';

/** Die zehn Altfelder (src/app/loader.py ALTFELDER). */
const ALTFELDER = [
	'channel_layouts',
	'channel_layouts_per_report',
	'channel_active_metrics',
	'outlook_metrics',
	'outlook_metric_formats',
	'hourly_metrics',
	'hourly_metric_formats',
	'show_outlook',
	'multi_day_trend_reports',
	'outlook_enabled'
] as const;

/** camelCase-Wizardfelder, die mit dem Rueckbau entfallen (Spec Entscheidung 2). */
const WIZARD_ALTFELDER = [
	'outlookEnabled',
	'hourlyMetricKeys',
	'outlookMetricKeys',
	'outlookMetricFormats',
	'hourlyMetricFormats'
] as const;

/** Alle Fundstellen eines Altschluessels in beliebiger Tiefe (gefuellt ODER leer zaehlt). */
function altFunde(wert: unknown, pfad = ''): string[] {
	if (Array.isArray(wert)) return wert.flatMap((v, i) => altFunde(v, `${pfad}[${i}]`));
	if (!wert || typeof wert !== 'object') return [];
	const funde: string[] = [];
	for (const [k, v] of Object.entries(wert as Record<string, unknown>)) {
		const hier = pfad ? `${pfad}.${k}` : k;
		if ((ALTFELDER as readonly string[]).includes(k)) funde.push(hier);
		funde.push(...altFunde(v, hier));
	}
	return funde;
}

/** Bestands-Altwerte, wie sie vor dem Datenlauf #3351 noch auf der Platte liegen koennen. */
const ALT_DC = {
	channel_layouts: { email: ['temp_max_c'], telegram: ['wind_max_kmh'] },
	channel_layouts_per_report: { morning: { email: ['temp_max_c'] } },
	channel_active_metrics: { sms: [{ metric_id: 'temp', aggregation: 'max' }] },
	outlook_metrics: ['temp_max_c', 'precip_sum_mm'],
	outlook_metric_formats: { temp_max_c: true },
	hourly_metrics: ['temp_c', 'wind_kmh'],
	hourly_metric_formats: { temp_c: true }
};

/** Voller Vergleich eines Nutzers MIT Altfeldern im Bestand (top-level und display_config). */
function bestandMitAltfeldern(id: string, userId: string): Record<string, unknown> {
	const v = vollerVergleich(id);
	return {
		...v,
		user_id: userId,
		outlook_enabled: false,
		show_outlook: true,
		display_config: {
			...(v.display_config as Record<string, unknown>),
			...structuredClone(ALT_DC),
			placements: { version: 1, rows: [], outlook_reports: ['evening'] }
		}
	};
}

/** Derselbe Vergleich ohne jeden Altschluessel. */
function bestandOhneAltfelder(id: string, userId: string): Record<string, unknown> {
	const mit = bestandMitAltfeldern(id, userId);
	const dc = { ...(mit.display_config as Record<string, unknown>) };
	for (const k of ALTFELDER) {
		delete mit[k];
		delete dc[k];
	}
	return { ...mit, display_config: dc };
}

// ── AC-2: Anlegen ─────────────────────────────────────────────────────────────

describe('#3298 AC-2: Anlegen (POST) ohne Altschluessel, insbesondere ohne outlook_enabled', () => {
	function feldsatz() {
		return { ...compareFeldsatzStandard(), name: 'Neu 3298', pickedIds: ['loc-1', 'loc-2'], region: 'Tirol' };
	}

	test('baueVergleichAnlegeRumpf: kein Altschluessel (top-level und display_config)', () => {
		const body = baueVergleichAnlegeRumpf(feldsatz());
		assert.deepEqual(altFunde(body), [], 'POST /api/compare/presets enthaelt Altschluessel');
		assert.deepEqual(body.location_ids, ['loc-1', 'loc-2'], 'Anlage-Felder fehlen');
		assert.equal(body.hourly_enabled, true, 'hourly_enabled (kein Altfeld) muss bleiben');
	});

	test('legeVergleichAn: der an der Netzgrenze ankommende POST traegt keinen Altschluessel', async () => {
		const gesendet: unknown[] = [];
		const rec = {
			async post<T>(_url: string, body: unknown): Promise<T> {
				gesendet.push(body);
				return { id: 'neu' } as T;
			}
		};
		await legeVergleichAn(rec, feldsatz());
		assert.equal(gesendet.length, 1);
		assert.deepEqual(altFunde(gesendet[0]), []);
	});

	test('buildNewComparePresetPayload: ein mitgegebenes outlookEnabled wird nicht gesendet', () => {
		const f = { ...feldsatz(), outlookEnabled: false } as unknown as NewComparePresetFields;
		assert.deepEqual(altFunde(buildNewComparePresetPayload(f)), []);
	});

	test('Feldsatz des Ortsvergleichs traegt keine camelCase-Altfelder mehr', () => {
		const vorhanden = WIZARD_ALTFELDER.filter((k) => k in compareFeldsatzStandard());
		assert.deepEqual(vorhanden, [], 'compareFeldsatzStandard() haelt noch tote Wizardfelder');
	});
});

// ── AC-2: Reiter speichern, zwei Nutzer, Go-Merge ────────────────────────────

describe('#3298 AC-2: Reiter speichern (PUT) ohne Altschluessel, Bestand beider Nutzer bleibt', () => {
	const A = 'cp-3298-a';
	const B = 'cp-3298-b';
	let server: GoMergeServer;

	beforeEach(() => {
		clearEtagRegistry();
		server = createGoMergeServer({ [A]: bestandMitAltfeldern(A, 'nutzer-a'), [B]: bestandMitAltfeldern(B, 'nutzer-b') });
		server.install();
	});
	afterEach(() => server.restore());

	for (const reiter of REITER) {
		test(`${reiter}: PUT-Rumpf ohne Altschluessel; Altbestand und Nachbar-Nutzer unveraendert`, async () => {
			await api.get(`/api/compare/presets/${A}`);
			const start = bestandMitAltfeldern(A, 'nutzer-a');
			const aufbau = reiterAufbau(reiter, start as unknown as ComparePreset);
			aufbau.aendern();
			aufbau.speicherung.aenderungMelden();
			await aufbau.ctl.flush();
			const ruempfe = server.putRuempfe();
			assert.equal(ruempfe.length, 1, `Messaufbau: genau EIN PUT erwartet, gesehen ${ruempfe.length}`);
			assert.equal(server.mitschnitt.at(-1)?.status, 200, 'Messaufbau: der PUT muss durchgehen');

			assert.deepEqual(altFunde(ruempfe[0]), [], `${reiter}: Altschluessel im PUT-Rumpf`);

			// Bestand bleibt: nur weglassen, nie leer senden, nie loeschen (Go-Merge).
			const nachher = server.stand(A);
			const dcNach = nachher.display_config as Record<string, unknown>;
			for (const [k, v] of Object.entries(ALT_DC)) assert.deepEqual(dcNach[k], v, `Bestand display_config.${k} veraendert`);
			assert.equal(nachher.outlook_enabled, false, 'Bestand outlook_enabled veraendert');
			assert.equal(nachher.show_outlook, true, 'Bestand show_outlook veraendert');
			assert.deepEqual(dcNach.placements, (start.display_config as Record<string, unknown>).placements, 'placements veraendert');
			assert.equal(nachher.user_id, 'nutzer-a', 'user_id darf sich nie aendern');

			// Mandantentrennung: der Vergleich des zweiten Nutzers bleibt unberuehrt.
			const bNach = server.stand(B);
			assert.equal(bNach.user_id, 'nutzer-b');
			assert.deepEqual(bNach, JSON.parse(JSON.stringify({ ...bestandMitAltfeldern(B, 'nutzer-b'), id: B })));
		});
	}

	// #3389: der lebende Zustellungs-Speicherer (Versand und Alarme im Reiter Zustellung) erhaelt
	// den Altschluessel-Beleg, den bisher die toten Reiter `versand`/`wetterMetriken` trugen.
	test('zustellung: PUT-Rumpf ohne Altschluessel; Altbestand und Nachbar-Nutzer unveraendert', async () => {
		await api.get(`/api/compare/presets/${A}`);
		const start = bestandMitAltfeldern(A, 'nutzer-a');
		const ctl = createController(A);
		const queue = createPutQueue();
		const vorher = standAusPreset(start as unknown as ComparePreset);
		assert.notEqual(vorher.morgenZeit, '06:45', 'Messaufbau: die Geste muss eine Aenderung sein');
		const speicherung = erstelleZustellungSpeicherung({
			context: 'vergleich',
			id: A,
			client: api,
			saveController: ctl,
			basis: vorher,
			enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn)
		});
		speicherung.aenderungMelden({ ...JSON.parse(JSON.stringify(vorher)), morgenZeit: '06:45' });
		await ctl.flush();
		const ruempfe = server.putRuempfe();
		assert.equal(ruempfe.length, 1, `Messaufbau: genau EIN PUT erwartet, gesehen ${ruempfe.length}`);
		assert.equal(server.mitschnitt.at(-1)?.status, 200, 'Messaufbau: der PUT muss durchgehen');

		assert.deepEqual(altFunde(ruempfe[0]), [], 'zustellung: Altschluessel im PUT-Rumpf');

		const nachher = server.stand(A);
		assert.equal(String(nachher.morning_time).slice(0, 5), '06:45', 'Messaufbau: die Zustellungs-Aenderung steht auf dem Server');
		const dcNach = nachher.display_config as Record<string, unknown>;
		for (const [k, v] of Object.entries(ALT_DC)) assert.deepEqual(dcNach[k], v, `Bestand display_config.${k} veraendert`);
		assert.equal(nachher.outlook_enabled, false, 'Bestand outlook_enabled veraendert');
		assert.equal(nachher.show_outlook, true, 'Bestand show_outlook veraendert');
		assert.deepEqual(dcNach.placements, (start.display_config as Record<string, unknown>).placements, 'placements veraendert');
		assert.equal(nachher.user_id, 'nutzer-a', 'user_id darf sich nie aendern');

		const bNach = server.stand(B);
		assert.equal(bNach.user_id, 'nutzer-b');
		assert.deepEqual(bNach, JSON.parse(JSON.stringify({ ...bestandMitAltfeldern(B, 'nutzer-b'), id: B })));
	});
});

describe('#3298 AC-2: Voll-Rumpf ohne outlook_enabled', () => {
	const preset = bestandMitAltfeldern('cp-3298-l', 'nutzer-a') as unknown as ComparePreset;

	// #3389: der Fall am toten Layout-Speicherer (flushPendingLayoutSave) entfiel.

	test('buildComparePresetSavePayload: edits.outlookEnabled ueberschreibt den Bestand nicht', () => {
		const edits = {
			name: 'X',
			activityProfile: null,
			pickedIds: ['loc-a'],
			region: 'Tirol',
			idealRanges: {},
			outlookEnabled: true
		} as unknown as CompareEditorEdits;
		const body = buildComparePresetSavePayload(preset, edits).body as unknown as Record<string, unknown>;
		assert.equal(body.outlook_enabled, false, 'Bestandswert reist nur ueber den Spread');
		const ohne = bestandOhneAltfelder('cp-3298-o', 'nutzer-a') as unknown as ComparePreset;
		const body2 = buildComparePresetSavePayload(ohne, edits).body as unknown as Record<string, unknown>;
		assert.ok(!('outlook_enabled' in body2), 'outlook_enabled darf nie aus dem Editor kommen');
	});
});

// ── AC-3: Hydration ──────────────────────────────────────────────────────────

describe('#3298 AC-3: Hydration liest keine Altfelder', () => {
	const mit = bestandMitAltfeldern('cp-3298-h', 'nutzer-a') as unknown as ComparePreset;
	const ohne = bestandOhneAltfelder('cp-3298-h', 'nutzer-a') as unknown as ComparePreset;

	test('hydrateLayoutFieldsFromPreset: Altwerte aendern das Ergebnis nicht, nur hourlyEnabled', () => {
		assert.deepEqual(hydrateLayoutFieldsFromPreset(mit), hydrateLayoutFieldsFromPreset(ohne));
		assert.deepEqual(Object.keys(hydrateLayoutFieldsFromPreset(mit)), ['hourlyEnabled']);
		assert.equal(hydrateLayoutFieldsFromPreset(mit).hourlyEnabled, true);
	});

	test('Lese-Naht channel_active_metrics ist entfernt', async () => {
		const save = await import('../shared/weather-metrics-tab/weatherMetricsCompareSave.ts');
		const layouts = await import('../shared/weather-metrics-tab/compareChannelMetricLayouts.ts');
		assert.ok(!('hydrateChannelActiveMetricsFromPreset' in save), 'hydrateChannelActiveMetricsFromPreset existiert noch');
		assert.ok(!('compareChannelActiveMetricsFromStored' in layouts), 'compareChannelActiveMetricsFromStored existiert noch');
	});

	test('feldsatzAusVorlage (Anlegen aus Vorlage): Altwerte ohne Wirkung, keine camelCase-Altfelder', () => {
		const orte = [{ id: 'loc-a' }, { id: 'loc-b' }] as unknown as Location[];
		const fMit = feldsatzAusVorlage(mit, orte);
		assert.deepEqual(fMit, feldsatzAusVorlage(ohne, orte), 'Altwerte der Vorlage veraendern den Feldsatz');
		assert.deepEqual(WIZARD_ALTFELDER.filter((k) => k in fMit), [], 'Feldsatz aus Vorlage haelt tote Wizardfelder');
		assert.deepEqual(fMit.pickedIds, ['loc-a', 'loc-b'], 'Vorlage-Felder fehlen');
	});
});

// ── AC-4: Whitelist Reiter Wetter ────────────────────────────────────────────

describe('#3298 AC-4: WETTER_DISPLAY_KEYS ohne Altnamen', () => {
	const ERLAUBT = ['ampel', 'metrics', 'preset_name', 'show_night_block', 'telegram_kurzform'];

	test('Whitelist besteht genau aus den fuenf erlaubten Schluesseln', () => {
		assert.deepEqual([...WETTER_DISPLAY_KEYS].sort(), ERLAUBT);
	});

	test('pickEigenfelder (Wetter): Altnamen in den Eingabedaten werden nicht uebernommen', () => {
		const quelle = {
			display_config: {
				metrics: ['temp_max_c'],
				preset_name: 'wandern',
				telegram_kurzform: true,
				show_night_block: false,
				ampel: { template: 'wandern' },
				...structuredClone(ALT_DC),
				show_outlook: true,
				multi_day_trend_reports: ['evening'],
				outlook_enabled: true
			}
		};
		const out = pickEigenfelder(quelle, { display: WETTER_DISPLAY_KEYS });
		assert.deepEqual(altFunde(out), []);
		assert.deepEqual(Object.keys(out.display_config as object).sort(), ERLAUBT);
	});
});
