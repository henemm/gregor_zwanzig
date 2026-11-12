// TDD RED — Issue #2794 S3a, Fix-Loop zu Teil-PR 4b (Befunde B1, B4, B5).
// Spec: docs/specs/modules/fix_2794_s3a_teil4b_befunde.md (AC-1, AC-2, AC-8 bis AC-13)
//
// ── VERTRAG (hier festgelegt, Phase 6 baut danach) ──
//
//   B1: REITER_DEFINITION.punkte.trip.label === 'aktionen.reiter.etappen'
//       Katalog: aktionen.reiter.etappen = „Etappen" / „Stages";
//                aktionen.reiter.etappen_wegpunkte entfällt (keine Bereichsüberschrift im Reiter;
//                Bereichsköpfe aller Reiter kommen mit #2913).
//       home.aktion.pausentag_ziel = „→ Etappen" / „→ Stages".
//
//   B4: deriveVergleichKennzahlen(preset, status, briefing, orte, vorlagen?: VorlagenAmpeln | null)
//         .wertebereicheKarte zählt standAusAbo('vergleich', preset, vorlagen).auswahl
//         (dieselbe Quelle wie der Reiter Wetter), NICHT display_config.ideal_ranges.
//         Texte: vergleich.hub.wertebereiche_kurz/_lang mit echtem Singular/Plural
//         („1 Metrik im Briefing" / „3 Metriken im Briefing", EN „1 metric in the briefing" /
//         „3 metrics in the briefing"); ohne „Idealbereich", ohne „Markierung, kein Score".
//         vorlagen fehlt / null / leer (Ladefehler) ⇒ beschreibungKurz und beschreibungLang = „—".
//       setupStepCompare(preset)[2] (Schritt Wetter): erledigt, wenn active_metrics nicht leer
//         ODER keine Liste gespeichert; offen nur bei ausdrücklich leerer Liste; ideal_ranges ohne Einfluss.
//       Bestandsdaten werden nur gelesen (AC-12).
//
//   B5: DE bausteine.alarme.titel = „Alarme · letzte 24 h"; EN bleibt „Alerts · last 24 h".
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_teil4b_befunde.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { live } from '../wetter-tab/__tests__/wetterTabDaten.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = resolve(HIER, '..');
const FRONTEND = resolve(SHARED, '..', '..', '..', '..');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const lade = async (p: string): Promise<Json> => import(pathToFileURL(p).href);
const modell = () => lade(join(SHARED, 'hub-uebersicht', 'hubUebersichtModell.ts'));
const tabs = () => lade(join(SHARED, 'subscriptionTabs.ts'));
const ampelModell = () => lade(join(SHARED, 'wetter-tab', 'ampelModell.ts'));
const wetterZustand = () => lade(join(SHARED, 'wetter-tab', 'wetterZustand.ts'));
const i18n = () => lade(join(FRONTEND, 'src', 'lib', 'i18n', 'index.ts'));
const cockpit = () => lade(join(FRONTEND, 'src', 'lib', 'utils', 'cockpitHelpers568.ts'));

async function vorlagen(): Promise<Json> {
	return (await ampelModell()).vorlagenAusTemplates(live().templates);
}

/** Drei verschiedene, in der Vorlage „allgemein" bekannte Metrik-Kennungen. */
async function dreiMetriken(): Promise<string[]> {
	const v = await vorlagen();
	const ids = Object.keys(v.allgemein?.metrics ?? (Object.values(v)[0] as Json)?.metrics ?? {});
	assert.ok(ids.length >= 3, 'Fixtur-Schutz: Vorlage braucht mindestens drei Metriken');
	return ids.slice(0, 3);
}

function preset(dc: Record<string, unknown> | undefined): Json {
	return {
		id: 'cp-2794-befunde',
		name: 'Befunde',
		location_ids: ['l1', 'l2'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 18,
		empfaenger: [],
		forecast_hours: 48,
		created_at: '2026-11-12T00:00:00Z',
		...(dc === undefined ? {} : { display_config: dc })
	};
}

const VERBOTEN = ['Idealbereich', 'Markierung, kein Score', 'target range', 'highlighted, no score'];

// ─────────────────────────────── B1 ───────────────────────────────

describe('B1 (AC-1/AC-2): Trip-Reiter heißt „Etappen", Bereichsüberschrift bleibt', () => {
	test('Reiter-Definition des Trips verweist auf aktionen.reiter.etappen', async () => {
		const { REITER_DEFINITION } = await tabs();
		assert.equal(REITER_DEFINITION.punkte.trip.label, 'aktionen.reiter.etappen');
	});

	test('Leiste DE: „Etappen" (nicht „Etappen & Wegpunkte")', async () => {
		const { subscriptionTabs } = await tabs();
		assert.deepEqual(
			subscriptionTabs('trip').map((t: Json) => t.label),
			['Übersicht', 'Etappen', 'Wetter', 'Zustellung']
		);
	});

	test('Katalog: Reiter „Etappen"/„Stages", alter Schlüssel etappen_wegpunkte entfällt (Bereichsköpfe: #2913)', async () => {
		const { trFor } = await i18n();
		assert.equal(trFor('de', 'aktionen.reiter.etappen'), 'Etappen');
		assert.equal(trFor('en', 'aktionen.reiter.etappen'), 'Stages');
		const { de } = await lade(join(FRONTEND, 'src', 'lib', 'i18n', 'messages', 'de', 'index.ts'));
		const { en } = await lade(join(FRONTEND, 'src', 'lib', 'i18n', 'messages', 'en', 'index.ts'));
		assert.ok(!('aktionen.reiter.etappen_wegpunkte' in de), 'de-Katalog führt noch aktionen.reiter.etappen_wegpunkte');
		assert.ok(!('aktionen.reiter.etappen_wegpunkte' in en), 'en-Katalog führt noch aktionen.reiter.etappen_wegpunkte');
	});

	test('Startseite, Pausentag-Hinweis: „→ Etappen" / „→ Stages"', async () => {
		const { trFor } = await i18n();
		assert.equal(trFor('de', 'home.aktion.pausentag_ziel'), '→ Etappen');
		assert.equal(trFor('en', 'home.aktion.pausentag_ziel'), '→ Stages');
	});
});

// ─────────────────────────────── B4 ───────────────────────────────

describe('B4 (AC-8/AC-9/AC-10): Karte „Wetter" zählt die Metriken im Briefing', () => {
	test('3 gewählte Metriken, keine ideal_ranges ⇒ „3 Metriken im Briefing" (nicht 0)', async () => {
		const m = await modell();
		const v = await vorlagen();
		const ids = await dreiMetriken();
		const p = preset({ active_metrics: ids });
		const soll = (await wetterZustand()).standAusAbo('vergleich', p, v).auswahl.length;
		assert.equal(soll, 3, 'Fixtur-Schutz: Reiter Wetter zählt drei gewählte Metriken');
		const k = m.deriveVergleichKennzahlen(p, 'active', null, [], v).wertebereicheKarte;
		assert.equal(k.beschreibungKurz, '3 Metriken im Briefing');
		assert.match(k.beschreibungLang, /^3 Metriken im Briefing/);
	});

	test('genau 1 Metrik ⇒ echter Singular „1 Metrik im Briefing"', async () => {
		const m = await modell();
		const v = await vorlagen();
		const [eine] = await dreiMetriken();
		const k = m.deriveVergleichKennzahlen(preset({ active_metrics: [eine] }), 'active', null, [], v).wertebereicheKarte;
		assert.equal(k.beschreibungKurz, '1 Metrik im Briefing');
		assert.match(k.beschreibungLang, /^1 Metrik im Briefing/);
	});

	test('keine Liste gespeichert ⇒ Zahl der Vorlage, wie der Reiter Wetter', async () => {
		const m = await modell();
		const v = await vorlagen();
		const p = preset({});
		const n = (await wetterZustand()).standAusAbo('vergleich', p, v).auswahl.length;
		assert.ok(n > 1, 'Fixtur-Schutz: Vorlage liefert mehrere Metriken');
		const k = m.deriveVergleichKennzahlen(p, 'active', null, [], v).wertebereicheKarte;
		assert.equal(k.beschreibungKurz, `${n} Metriken im Briefing`);
	});

	test('alte ideal_ranges zählen nicht mehr', async () => {
		const m = await modell();
		const v = await vorlagen();
		const [eine] = await dreiMetriken();
		const p = preset({ active_metrics: [eine], ideal_ranges: { a: {}, b: {}, c: {}, d: {} } });
		const k = m.deriveVergleichKennzahlen(p, 'active', null, [], v).wertebereicheKarte;
		assert.equal(k.beschreibungKurz, '1 Metrik im Briefing');
	});

	for (const [name, wert] of [['fehlt', undefined], ['null', null], ['leer', {}]] as const) {
		test(`Vorlagen ${name} (Ladefehler) ⇒ „—" statt einer Zahl`, async () => {
			const m = await modell();
			const p = preset({ ideal_ranges: { a: {}, b: {} } });
			const k = m.deriveVergleichKennzahlen(p, 'active', null, [], wert).wertebereicheKarte;
			assert.equal(k.beschreibungKurz, '—');
			assert.equal(k.beschreibungLang, '—');
		});
	}

	test('Karte enthält nirgends die alten Begriffe', async () => {
		const m = await modell();
		const v = await vorlagen();
		const ids = await dreiMetriken();
		for (const vl of [v, null]) {
			const k = m.deriveVergleichKennzahlen(preset({ active_metrics: ids }), 'active', null, [], vl).wertebereicheKarte;
			const text = JSON.stringify(k);
			for (const w of VERBOTEN) assert.ok(!text.includes(w), `„${w}" steht noch in der Karte: ${text}`);
		}
	});

	test('Katalog: Singular ≠ Plural in DE und EN, ohne alte Begriffe', async () => {
		const { trnFor } = await i18n();
		const erwartet: Record<string, [string, string]> = {
			de: ['1 Metrik im Briefing', '3 Metriken im Briefing'],
			en: ['1 metric in the briefing', '3 metrics in the briefing']
		};
		for (const lang of ['de', 'en'] as const) {
			assert.equal(trnFor(lang, 'vergleich.hub.wertebereiche_kurz', 1), erwartet[lang][0]);
			assert.equal(trnFor(lang, 'vergleich.hub.wertebereiche_kurz', 3), erwartet[lang][1]);
			assert.match(trnFor(lang, 'vergleich.hub.wertebereiche_lang', 1), new RegExp(`^${erwartet[lang][0]}`));
			assert.match(trnFor(lang, 'vergleich.hub.wertebereiche_lang', 3), new RegExp(`^${erwartet[lang][1]}`));
			for (const n of [1, 3]) {
				for (const key of ['vergleich.hub.wertebereiche_kurz', 'vergleich.hub.wertebereiche_lang']) {
					const s = trnFor(lang, key, n);
					for (const w of VERBOTEN) assert.ok(!s.includes(w), `${lang} ${key}(${n}) enthält „${w}": ${s}`);
				}
			}
		}
	});
});

describe('B4 (AC-11): Checkliste „Wetter" folgt der Auswahl, nicht den alten Idealbereichen', () => {
	const wetter = async (dc: Record<string, unknown> | undefined) => {
		const steps = (await cockpit()).setupStepCompare(preset(dc));
		const { tr } = await i18n();
		assert.equal(steps[2].label, tr('bausteine.checkliste.wetter'), 'Fixtur-Schutz: dritter Schritt ist Wetter');
		return steps[2].done as boolean;
	};

	test('active_metrics nicht leer ⇒ erledigt', async () => {
		assert.equal(await wetter({ active_metrics: ['gust'] }), true);
	});
	test('keine Liste gespeichert (Vorlage gilt) ⇒ erledigt', async () => {
		assert.equal(await wetter({}), true);
		assert.equal(await wetter(undefined), true);
	});
	test('ausdrücklich leere Liste ⇒ offen', async () => {
		assert.equal(await wetter({ active_metrics: [] }), false);
	});
	test('ideal_ranges ohne Einfluss', async () => {
		assert.equal(await wetter({ active_metrics: [], ideal_ranges: { gust: { min: 0 } } }), false);
		assert.equal(await wetter({ active_metrics: ['gust'], ideal_ranges: {} }), true);
	});
});

describe('B4 (AC-12): Bestandsdaten werden nur gelesen', () => {
	test('Übersicht und Checkliste verändern das Preset nicht', async () => {
		const m = await modell();
		const v = await vorlagen();
		const p = preset({ active_metrics: await dreiMetriken(), ideal_ranges: { gust: { min: 0, max: 40 } } });
		const vorher = structuredClone(p);
		m.deriveVergleichKennzahlen(p, 'active', null, [], v);
		(await cockpit()).setupStepCompare(p);
		assert.deepEqual(p, vorher);
	});
});

// ─────────────────────────────── B5 ───────────────────────────────

describe('B5 (AC-13): Alarm-Baustein heißt auf Deutsch „Alarme · letzte 24 h"', () => {
	test('DE „Alarme · letzte 24 h", EN unverändert', async () => {
		const { trFor } = await i18n();
		assert.equal(trFor('de', 'bausteine.alarme.titel'), 'Alarme · letzte 24 h');
		assert.equal(trFor('en', 'bausteine.alarme.titel'), 'Alerts · last 24 h');
	});
});
