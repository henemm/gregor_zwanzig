// TDD RED — Issue #2422 S2a, AC-7 (K8-Fix): Read-Modify-Write statt Replace
// beim Editor-Speichern.
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-7).
//
// CLAUDE.md-Pflicht "Read-Modify-Write mit Merge, niemals Replace"
// (BUG-DATALOSS-GR221, #102): `buildWeatherConfigMetrics` (metricsEditor.ts)
// baut heute JEDEN Metrik-Eintrag komplett neu aus den dem Frontend bekannten
// Feldern (metric_id, enabled, use_friendly_format, horizons, bucket, order).
// Jedes andere, dem Frontend unbekannte Feld eines Bestands-Eintrags
// (morning_enabled, evening_enabled, format_mode, kuenftige Felder) geht
// beim Speichern verloren (Replace statt Merge). Derselbe Grundsatz gilt fuer
// Kanal-Layout-Eintraege in `channel_layouts`.
//
// Festgelegte Einstiegspunkte fuer /50 (PFLICHT-Signaturen):
// - `buildWeatherConfigMetrics` bekommt einen optionalen 5. Parameter
//   `bestand?: ReadonlyArray<Record<string, unknown>>` -- die Original-
//   Eintraege aus `display_config.metrics` des geladenen Trips.
// - `mergeAllChannelLayoutsForSave`s 3. Parameter `buildMetrics` bekommt
//   einen zusaetzlichen `channel: ChannelId`-Parameter -- NUR damit kann die
//   vom Aufrufer (WeatherMetricsTab.svelte::buildWeatherPayload) EINMAL
//   gebaute Callback-Funktion je Kanal den passenden Bestand
//   (`prevLayouts?.[channel]`) nachschlagen und an
//   `buildWeatherConfigMetrics(..., bestand)` durchreichen.
// Beide Signaturen sind in `_editor_kette.ts::baueSpeichernPayload()`
// bereits so verdrahtet (geteilte Kette mit AC-3/AC-4/AC-14) -- dieser Test
// nutzt GENAU diese Funktion, keine zweite, abweichende Kopie.
//
// Golden C (`tests/fixtures/einstellung_auslieferung/golden_c.json`, G3/G4)
// traegt genau drei Metriken mit einem dem Frontend unbekannten Feld:
// - thunder: format_mode = "symbol" (G3, auch im email-Kanal-Layout)
// - cloud_low: evening_enabled = false (G4)
// - humidity: morning_enabled = false (G4)
// Die Assertion vergleicht DIREKT gegen den Golden-C-INPUT (kein
// eingefrorenes Erwartungs-Fixture noetig fuer diese Zusicherung).
//
// RED heute: `buildWeatherConfigMetrics`/`mergeAllChannelLayoutsForSave`
// kennen die neuen Parameter noch nicht (Cast nimmt sie vorweg, siehe
// _editor_kette.ts) -- die Werte fehlen (undefined) statt der
// Golden-C-Werte. Eine saubere Assertion-Meldung, kein TypeError.
//
// Lauf:
//     cd frontend && npm test -- \
//       src/lib/components/shared/weather-metrics-tab/__tests__/feld_erhalt_ohne_ausnahme.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { baueSpeichernPayload, ladeInEditorState, type GoldenTrip, type MinimalCatalog } from './_editor_kette.ts';
import { buildWeatherConfigMetrics, type MetricCatalog } from '../../../trip-detail/metricsEditor.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = path.resolve(__dirname, '../../../../../../../tests/fixtures/einstellung_auslieferung');

function ladeGoldenC(): GoldenTrip {
	return JSON.parse(readFileSync(path.join(FIXTURE_DIR, 'golden_c.json'), 'utf-8'));
}

// Echter Katalog-Snapshot (29 waehlbare Metriken, aus app.metric_catalog.
// get_all_metrics()) -- siehe editor_anzeige_gleich_erwartung.test.ts.
const catalog: MinimalCatalog = JSON.parse(
	readFileSync(path.join(__dirname, 'fixtures', 'metric_catalog_selectable.json'), 'utf-8'),
);

const TRAEGER_FELDER = ['morning_enabled', 'evening_enabled', 'format_mode'] as const;

describe('AC-7: Feld-Erhalt ohne Ausnahme (K8-Fix)', () => {
	test('display_config.metrics: morning_enabled/evening_enabled/format_mode ueberleben Speichern-ohne-Aenderung', () => {
		const golden = ladeGoldenC();
		const bestand = golden.display_config.metrics;
		const state = ladeInEditorState(golden, catalog);
		const payload = baueSpeichernPayload(golden, state, catalog);
		const byId = new Map(payload.metrics.map((m) => [m.metric_id as string, m]));

		// Vakuum-Schutz: Golden C muss tatsaechlich mindestens ein Beispiel je
		// Feld tragen, sonst prueft dieser Test nichts.
		const traeger = bestand.filter((mc) =>
			TRAEGER_FELDER.some((feld) => mc[feld] !== undefined && mc[feld] !== null),
		);
		assert.ok(
			traeger.length >= 3,
			`Vakuum-Schutz: golden_c.json traegt zu wenige per-Metrik-Feld-Traeger ` +
				`(gefunden: ${traeger.map((m) => m.metric_id).join(', ')})`,
		);

		for (const original of traeger) {
			const mid = original.metric_id as string;
			const gebaut = byId.get(mid);
			assert.ok(gebaut, `AC-7: Metrik ${mid} fehlt komplett im gebauten Payload`);
			for (const feld of TRAEGER_FELDER) {
				if (original[feld] === undefined || original[feld] === null) continue;
				assert.deepEqual(
					gebaut![feld],
					original[feld],
					`AC-7: ${mid}.${feld} muss nach Speichern-ohne-Aenderung identisch zum ` +
						`Golden-C-Ausgangswert sein (${JSON.stringify(original[feld])}), ` +
						`gebaut wurde ${JSON.stringify(gebaut![feld])} -- Read-Modify-Write statt ` +
						`Replace (CLAUDE.md #102) fehlt noch in buildWeatherConfigMetrics.`,
				);
			}
		}
	});

	test('channel_layouts.email: thunder.format_mode ueberlebt Speichern-ohne-Aenderung', () => {
		const golden = ladeGoldenC();
		const state = ladeInEditorState(golden, catalog);
		const payload = baueSpeichernPayload(golden, state, catalog);

		const thunderNachher = payload.channel_layouts.email?.find((m) => m.metric_id === 'thunder');
		assert.ok(thunderNachher, 'AC-7: thunder fehlt im gebauten email-Kanal-Layout');
		assert.equal(
			thunderNachher!.format_mode,
			'symbol',
			`AC-7: channel_layouts.email.thunder.format_mode muss nach Speichern-ohne-` +
				`Aenderung "symbol" bleiben (Golden-C-Ausgangswert), erhalten wurde ` +
				`${JSON.stringify(thunderNachher!.format_mode)} -- mergeAllChannelLayoutsForSave ` +
				`muss den Kanal an buildMetrics durchreichen, damit der Bestand je Kanal ` +
				`nachschlagbar ist (K8-Fix, Read-Modify-Write statt Replace).`,
		);
	});

	// Fix #2422 S2a (K8-Nebenwirkung, Advisor-Fund /50): ein stehen gebliebener
	// `format_mode` aus dem Bestand hat laut Issue #435
	// (`src/app/loader.py::_resolve_format_mode`) VORRANG vor
	// `use_friendly_format` -- ein Roh/Einfach-WECHSEL (anders als die
	// No-Op-Faelle oben) darf deshalb NICHT den alten, jetzt widersprechenden
	// `format_mode` mitschleppen, sonst bleibt der Wechsel beim Lesen wirkungslos.
	test('widersprechender Bestands-format_mode wird bei einem Roh/Einfach-Wechsel verworfen', () => {
		const buckets = { primary: ['thunder'], secondary: [], off: [] };
		const bestandNichtRoh = [{ metric_id: 'thunder', format_mode: 'symbol' }];

		// Wechsel EINFACH -> ROH: friendlyMap sagt jetzt false, der Bestand
		// traegt noch den alten nicht-rohen Modus -- der muss weg.
		const nachRohWechsel = buildWeatherConfigMetrics(
			buckets, { thunder: false }, {}, catalog as unknown as MetricCatalog, bestandNichtRoh,
		);
		const thunderRoh = nachRohWechsel.find((m) => m.metric_id === 'thunder');
		assert.ok(thunderRoh, 'thunder fehlt im gebauten Payload');
		assert.equal(
			(thunderRoh as unknown as Record<string, unknown>).format_mode,
			undefined,
			`Nach dem Wechsel auf Roh (use_friendly_format=false) darf kein ` +
				`widersprechender Bestands-format_mode ("symbol") mehr stehen -- ` +
				`gefunden: ${JSON.stringify((thunderRoh as unknown as Record<string, unknown>).format_mode)}.`,
		);

		// Gegenprobe: KEIN Widerspruch (friendly bleibt true) -- format_mode
		// bleibt erhalten (das ist bereits durch die No-Op-Tests oben gedeckt,
		// hier als direkte Gegenprobe zur selben Eingabe).
		const bestandBleibtEinfach = [{ metric_id: 'thunder', format_mode: 'symbol' }];
		const ohneWechsel = buildWeatherConfigMetrics(
			buckets, { thunder: true }, {}, catalog as unknown as MetricCatalog, bestandBleibtEinfach,
		);
		const thunderEinfach = ohneWechsel.find((m) => m.metric_id === 'thunder');
		assert.equal(
			(thunderEinfach as unknown as Record<string, unknown>).format_mode,
			'symbol',
			'Ohne Widerspruch (friendly bleibt true) muss format_mode erhalten bleiben.',
		);
	});
});
