// TDD RED — Issue #2794 S3a, Teil-PR 2 „Leiste und Umleitung": Reiter-Definition.
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-1, AC-2, AC-6 (Kern-Schicht)
//
// Messweise: nur Funktionsausgaben der EINEN Definition (`subscriptionTabs`, `anlegeKette`)
// und die Katalogdateien DE/EN. Keine Mocks. Die Sprache wird ueber den echten Store
// `locale` umgeschaltet (Muster trip_anlegen_sprache.test.ts).
//
// RED heute: die Definition fuehrt noch wetter-metriken · wertebereiche · alarme; die
// Katalog-Schluessel aktionen.reiter.wetter / aktionen.reiter.zustellung fehlen.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/s3a2794_reiter_definition.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { subscriptionTabs, anlegeKette, REITER_DEFINITION } from '../subscriptionTabs.ts';
import { locale } from '../../../i18n/index.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KATALOG = (lang: 'de' | 'en') => join(HIER, '..', '..', '..', 'i18n', 'messages', lang, 'aktionen.json');
const katalog = (lang: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(KATALOG(lang), 'utf-8'));

const ENTFALLEN = ['wertebereiche', 'alarme', 'wetter-metriken'];

afterEach(() => locale.set('de'));

const ids = (k: { id: string }[]) => k.map((r) => r.id);

describe('AC-1: Trip-Hub — Übersicht · Etappen · Wetter · Zustellung', () => {
	test('s3a2794_ac1_trip_hub_kennungen_genau_vier', () => {
		assert.deepEqual(ids(subscriptionTabs('trip')), ['uebersicht', 'etappen', 'wetter', 'zustellung']);
	});

	test('s3a2794_ac1_trip_hub_kein_entfallener_reiter', () => {
		for (const alt of ENTFALLEN) {
			assert.ok(!ids(subscriptionTabs('trip')).includes(alt), `AC-1: Trip-Hub führt noch den Reiter '${alt}'`);
		}
	});
});

describe('AC-2: Vergleichs-Hub — Übersicht · Orte · Wetter · Zustellung', () => {
	test('s3a2794_ac2_vergleich_hub_kennungen_genau_vier', () => {
		assert.deepEqual(ids(subscriptionTabs('vergleich')), ['uebersicht', 'orte', 'wetter', 'zustellung']);
	});

	test('s3a2794_ac2_vergleich_hub_kein_entfallener_reiter', () => {
		for (const alt of ENTFALLEN) {
			assert.ok(!ids(subscriptionTabs('vergleich')).includes(alt), `AC-2: Vergleichs-Hub führt noch den Reiter '${alt}'`);
		}
	});
});

describe('AC-6: Anlege-Ketten folgen derselben Definition', () => {
	test('s3a2794_ac6_trip_anlegen_route_etappen_wegpunkte_wetter_zustellung', () => {
		assert.deepEqual(ids(anlegeKette('trip')), ['route', 'etappen', 'wegpunkte', 'wetter', 'zustellung']);
	});

	test('s3a2794_ac6_vergleich_anlegen_vergleich_orte_wetter_zustellung', () => {
		assert.deepEqual(ids(anlegeKette('vergleich')), ['vergleich', 'orte', 'wetter', 'zustellung']);
	});

	test('s3a2794_ac6_kein_anlege_schritt_auf_entfallenen_reiter', () => {
		for (const kind of ['trip', 'vergleich'] as const) {
			for (const alt of [...ENTFALLEN, 'versand']) {
				assert.ok(!ids(anlegeKette(kind)).includes(alt), `AC-6: Anlege-Kette ${kind} führt noch '${alt}'`);
			}
		}
	});

	test('s3a2794_ac6_erster_schwanz_schritt_wetter_hat_kind_eigenen_sperr_hinweis', () => {
		// ANLEGE_SCHWANZ_HINWEIS wird auf die neue Kennung umgestellt: der erste Schwanz-Schritt
		// haengt am Kopf und nennt den kind-eigenen Hinweis (nicht „erst <Vorgaenger> öffnen").
		const trip = anlegeKette('trip').find((s) => s.id === 'wetter');
		const vergleich = anlegeKette('vergleich').find((s) => s.id === 'wetter');
		assert.ok(trip, 'Trip-Anlegen: kein Schritt wetter');
		assert.ok(vergleich, 'Vergleich-Anlegen: kein Schritt wetter');
		assert.ok(trip.lockHint && !/öffnen/.test(trip.lockHint), `Trip/wetter: Hinweis nicht kind-eigen (${trip.lockHint})`);
		assert.ok(
			vergleich.lockHint && !/öffnen/.test(vergleich.lockHint),
			`Vergleich/wetter: Hinweis nicht kind-eigen (${vergleich.lockHint})`
		);
		const zt = anlegeKette('trip').find((s) => s.id === 'zustellung');
		assert.ok(zt?.lockHint?.includes('Wetter'), `Trip/zustellung: Hinweis nennt nicht den Vorgaenger „Wetter" (${zt?.lockHint})`);
	});
});

describe('AC-1/AC-2: Reiter-Namen über neue Katalog-Schlüssel, DE und EN', () => {
	test('s3a2794_ac1_definition_nutzt_schluessel_aktionen_reiter_wetter_und_zustellung', () => {
		const schwanz = REITER_DEFINITION.schwanz.map((r) => [r.id, r.label]);
		assert.deepEqual(schwanz, [
			['wetter', 'aktionen.reiter.wetter'],
			['zustellung', 'aktionen.reiter.zustellung']
		]);
	});

	test('s3a2794_ac1_katalog_paritaet_de_en_neue_schluessel', () => {
		const de = katalog('de');
		const en = katalog('en');
		assert.equal(de['aktionen.reiter.wetter'], 'Wetter');
		assert.equal(de['aktionen.reiter.zustellung'], 'Zustellung');
		assert.equal(en['aktionen.reiter.wetter'], 'Weather');
		assert.equal(en['aktionen.reiter.zustellung'], 'Delivery');
		assert.deepEqual(Object.keys(de).sort(), Object.keys(en).sort(), 'Katalog aktionen: DE- und EN-Schlüssel weichen ab');
	});

	test('s3a2794_ac1_bestehende_aktionsmenue_schluessel_bleiben', () => {
		// aktionen.weather / aktionen.alarms dienen weiter dem Aktionsmenue (Spec §8) — nicht umbenennen.
		for (const lang of ['de', 'en'] as const) {
			assert.ok(katalog(lang)['aktionen.weather'], `${lang}: aktionen.weather entfernt`);
			assert.ok(katalog(lang)['aktionen.alarms'], `${lang}: aktionen.alarms entfernt`);
		}
	});

	for (const [lang, wetter, zustellung] of [
		['de', 'Wetter', 'Zustellung'],
		['en', 'Weather', 'Delivery']
	] as const) {
		test(`s3a2794_ac1_ac2_hub_labels_${lang}`, () => {
			locale.set(lang);
			for (const kind of ['trip', 'vergleich'] as const) {
				const tabs = subscriptionTabs(kind);
				assert.deepEqual(
					tabs.filter((t) => t.id === 'wetter' || t.id === 'zustellung').map((t) => t.label),
					[wetter, zustellung],
					`${kind}/${lang}: Reiter-Namen ${JSON.stringify(tabs.map((t) => t.label))}`
				);
			}
		});

		test(`s3a2794_ac6_anlege_labels_${lang}`, () => {
			locale.set(lang);
			for (const kind of ['trip', 'vergleich'] as const) {
				const k = anlegeKette(kind);
				assert.equal(k.find((s) => s.id === 'wetter')?.label, wetter, `${kind}/${lang}: Schritt wetter`);
				assert.equal(k.find((s) => s.id === 'zustellung')?.label, zustellung, `${kind}/${lang}: Schritt zustellung`);
			}
		});
	}
});
