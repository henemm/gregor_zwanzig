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
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { parse } from 'svelte/compiler';
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

// ─────────────────────────────── B2 ───────────────────────────────
//
// Fix-Loop AC-4: Staging-Messung DE 360 px ergab `.mtabbar` scrollWidth 329 > clientWidth 328
// (Pill „Zustellung" 1 px abgeschnitten) bei Pill-Innenabstand 12 px seitlich, Rahmen 1 px,
// kein Abstand zwischen den Pills. Daraus folgt die Summe der Pill-INHALTE (Text + Zähler +
// inneres gap) der DE-Leiste: 329 − 4 · (2 · 12 + 2 · 1) = 225 px.
// Dieser Test rechnet mit den Stilwerten aus MTabBar.svelte (Handy-Media-Query) und app.css die
// DE-Leistenbreite bei 360 px nach und verlangt ≥ 8 px Reserve. Das ist ein Modell aus einer
// Messung, kein Browser-Layout: der eigentliche Nachweis ist die Staging-Messung
// (e2e/s3a2794-teil4b-staging.spec.ts, AC-4: scrollWidth ≤ clientWidth bei 360/375/390, DE+EN).

const MTABBAR = join(FRONTEND, 'src', 'lib', 'components', 'mobile', 'MTabBar.svelte');
const DE_INHALT_360 = 225; // aus der Staging-Messung abgeleitet (siehe oben)
const LEISTE_360 = 328; // clientWidth der Leiste bei 360 px Viewport (Staging-Messung)
const RESERVE_MIN = 8;

/** Deklarationen der Handy-Regel (max-width: 899px) für genau den Selektor `sel`. */
function handyRegel(sel: string): Record<string, string> {
	const quelle = readFileSync(MTABBAR, 'utf-8');
	const ast = parse(quelle, { modern: true }) as Json;
	const out: Record<string, string> = {};
	for (const at of ast.css?.children ?? []) {
		if (at.type !== 'Atrule' || !/max-width:\s*899px/.test(String(at.prelude))) continue;
		for (const r of at.block?.children ?? []) {
			if (r.type !== 'Rule') continue;
			const selektor = quelle.slice(r.prelude.start, r.prelude.end).replace(/\s+/g, ' ').trim();
			if (selektor !== sel) continue;
			for (const d of r.block.children) if (d.type === 'Declaration') out[d.property] = String(d.value).trim();
		}
	}
	return out;
}

/** Löst var(--g-…) über app.css auf und liefert px (nur px/0 erlaubt). */
function px(wert: string): number {
	const css = readFileSync(join(FRONTEND, 'src', 'app.css'), 'utf-8');
	const aufgeloest = wert.replace(/var\((--[\w-]+)\)/g, (_, name) => {
		const m = new RegExp(`${name}\\s*:\\s*([^;]+);`).exec(css);
		assert.ok(m, `Token ${name} nicht in app.css`);
		return m![1].trim();
	});
	if (aufgeloest === '0') return 0;
	const m = /^(-?\d*\.?\d+)px$/.exec(aufgeloest);
	assert.ok(m, `kein px-Wert: ${wert} → ${aufgeloest}`);
	return Number(m![1]);
}

describe('B2 (AC-4/AC-5): Handy-Pill-Leiste passt DE bei 360 px mit Reserve', () => {
	const ITEM = ".mtabbar :global([data-slot='segmented-item'])";

	test('DE-Leiste 360 px: Breite aus Stilwerten ≤ Leiste − 8 px', () => {
		const item = handyRegel(ITEM);
		const leiste = handyRegel('.mtabbar');
		const teile = (item.padding ?? '').split(/\s+/);
		assert.ok(teile.length === 2, `Messaufbau: padding erwartet als „senkrecht seitlich": ${item.padding}`);
		const seitlich = px(teile[1]);
		// #2980 AC-17 (ADR-0118): Handy-Reiter sind Text-Reiter ohne Seitenrahmen (keine Pillen mehr) —
		// die Handy-Regel setzt keinen `border`, seitlich zählt dann 0 px.
		const rahmen = item.border === undefined ? 0 : px(item.border.split(/\s+/)[0]);
		const zwischen = leiste.gap ? px(leiste.gap) : 0;
		const margin = item.margin ?? item['margin-left'] ?? item['margin-right'];
		assert.equal(margin, undefined, `Messaufbau: Pill-margin unbekannt im Modell: ${margin}`);
		const breite = DE_INHALT_360 + 4 * (2 * seitlich + 2 * rahmen) + 3 * zwischen;
		assert.ok(
			breite <= LEISTE_360 - RESERVE_MIN,
			`AC-4: DE-Leiste rechnerisch ${breite} px bei ${LEISTE_360} px Platz (Reserve ${LEISTE_360 - breite} < ${RESERVE_MIN})`
		);
	});

	test('Trefferhöhe, Wisch-Fallback und Einrasten bleiben (AC-4/AC-5)', () => {
		const item = handyRegel(ITEM);
		const leiste = handyRegel('.mtabbar');
		assert.equal(item['min-height'], '44px', 'AC-4: Mindest-Trefferhöhe 44 px');
		assert.equal(item['flex-shrink'], '0', 'AC-5: Pills dürfen nicht gestaucht werden');
		assert.equal(item['scroll-snap-align'], 'start', 'AC-5: Einrasten');
		assert.equal(leiste['overflow-x'], 'auto', 'AC-5: Wisch-Fallback');
		assert.equal(leiste['scroll-snap-type'], 'x proximity', 'AC-5: Scroll-Snap');
	});
});
