// Issue #3020 R1, AC-2 (Ersatz für die mit #3357 gelöschte Fassung von #2422 S2a AC-7, dazu `sms_threshold`):
// Read-Modify-Write statt Replace (CLAUDE.md „Daten-Schema-Reworks“, BUG-DATALOSS-GR221, #102).
//
// Der LEBENDE Speicherweg des Reiters Wetter (wetterTabSpeicherung.tripNutzlast/vergleichNutzlast, Stand aus
// wetterZustand.standAusAbo) lässt an jedem Metrik-Eintrag jedes Feld stehen, das die Bedienung nicht ändert — auch
// Altfelder ohne lebende Bedienung (`sms_threshold`, `format_mode`, `morning_enabled`, `evening_enabled`,
// `use_friendly_format`) und künftige, dem Frontend unbekannte.
// Bestand: `tests/fixtures/einstellung_auslieferung/golden_c.json` (INPUT, keine eingefrorene Erwartung).
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { aufgeloestVon, live } from '../../wetter-tab/__tests__/wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../../wetter-tab/ampelModell.ts';
import { tripNutzlast, vergleichNutzlast } from '../../wetter-tab/wetterTabSpeicherung.ts';
import { mitMetrik, ohneMetrik, standAusAbo, type AboSicht, type WetterStand } from '../../wetter-tab/wetterZustand.ts';

type Eintrag = Record<string, unknown>;
const HIER = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HIER, '../../../../../../../tests/fixtures/einstellung_auslieferung');
const golden = (name: string): { display_config: { metrics: Eintrag[] } & Record<string, unknown> } & Record<string, unknown> =>
	JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf-8'));

/** #2988: dieselben Vorlagen wie die Auflösung (Python-Kern). */
const VORLAGEN = vorlagenAusTemplates(live().templates);
const TRAEGER = ['morning_enabled', 'evening_enabled', 'format_mode', 'sms_threshold'] as const;
type Geste = (s: WetterStand) => WetterStand;
const GESTEN: Record<string, Geste> = {
	'ohne Aenderung': (s) => s,
	'andere Metrik abgewaehlt': (s) => ohneMetrik(s, 'wind'),
	'Metrik hinzugefuegt': (s) => mitMetrik(s, 'dewpoint', 'route'),
	'Tagesfenster geaendert': (s) => ({ ...s, tagesfenster: { start: 6, end: 20 } })
};

/** Nutzlast des Reiters Wetter (Trip) nach der Geste. */
function tripMetriken(abo: unknown, geste: Geste): Eintrag[] {
	const stand = geste(standAusAbo('route', abo as AboSicht, aufgeloestVon(abo)));
	const n = tripNutzlast({ client: null as never, stand: () => stand, vorlagen: () => VORLAGEN, abo: () => abo as AboSicht });
	return n.weatherConfig.metrics as Eintrag[];
}
const nachId = (liste: Eintrag[]) => new Map(liste.map((m) => [m.metric_id as string, m]));

describe('#3020 AC-2 Trip: Eintragsfelder überleben das Speichern aus dem Reiter Wetter', () => {
	for (const [name, geste] of Object.entries(GESTEN)) {
		test(`display_config.metrics: morning_enabled/evening_enabled/format_mode/sms_threshold überleben das Speichern (${name})`, () => {
			const abo = { id: 'golden-c', ...golden('golden_c.json') };
			const gebaut = nachId(tripMetriken(abo, geste));
			const bestand = abo.display_config.metrics;
			for (const feld of TRAEGER) assert.ok(bestand.some((m) => m[feld] !== undefined), `Vakuum-Schutz: golden_c trägt kein ${feld}`);
			for (const original of bestand) {
				const neu = gebaut.get(original.metric_id as string);
				assert.ok(neu, `${original.metric_id} fehlt im Rumpf`);
				for (const feld of TRAEGER) assert.deepEqual(neu![feld], original[feld], `${original.metric_id}.${feld}`);
			}
		});

		test(`jeder Eintrag ausser dem geänderten bleibt vollständig, auch unbekannte Felder (${name})`, () => {
			const abo = { id: 'golden-c', ...golden('golden_c.json') };
			for (const m of abo.display_config.metrics) m.kuenftiges_feld = { tief: [m.metric_id] };
			const gebaut = nachId(tripMetriken(abo, geste));
			for (const original of abo.display_config.metrics) {
				const abgewaehlt = name === 'andere Metrik abgewaehlt' && original.metric_id === 'wind';
				assert.deepEqual(gebaut.get(original.metric_id as string), abgewaehlt ? { ...original, enabled: false } : original);
			}
		});
	}

	test('abwählen und wieder hinzufügen: sms_threshold und übrige Felder des Eintrags bleiben', () => {
		const abo = { id: 'golden-c', ...golden('golden_c.json') };
		const aus = { ...abo, display_config: { ...abo.display_config, metrics: tripMetriken(abo, (s) => ohneMetrik(s, 'precipitation')) } };
		const an = nachId(tripMetriken(aus, (s) => mitMetrik(s, 'precipitation', 'route'))).get('precipitation');
		const original = abo.display_config.metrics.find((m) => m.metric_id === 'precipitation')!;
		assert.equal(original.sms_threshold, 0.1, 'Messaufbau: Schwelle gespeichert');
		assert.deepEqual({ ...an, order: undefined, bucket: undefined }, { ...original, order: undefined, bucket: undefined });
	});

	test('zwei Nutzer mit verschiedenen Schwellen: jede Nutzlast trägt nur die eigenen Werte', () => {
		const abo = (user_id: string, schwelle: number) => {
			const a = { id: `trip-${user_id}`, user_id, ...golden('golden_c.json') };
			a.display_config.metrics.find((m) => m.metric_id === 'precipitation')!.sms_threshold = schwelle;
			return a;
		};
		const [anna, bruno] = [abo('gz3020-anna', 1.5), abo('gz3020-bruno', 7)];
		const standA = standAusAbo('route', anna as AboSicht, aufgeloestVon(anna));
		const standB = standAusAbo('route', bruno as AboSicht, aufgeloestVon(bruno)); // B öffnet, bevor A speichert
		const schwelle = (a: unknown, s: WetterStand) =>
			nachId(
				tripNutzlast({ client: null as never, stand: () => s, vorlagen: () => VORLAGEN, abo: () => a as AboSicht }).weatherConfig.metrics as Eintrag[]
			).get('precipitation')!.sms_threshold;
		assert.deepEqual([schwelle(anna, standA), schwelle(bruno, standB)], [1.5, 7]);
	});
});

describe('#3020 AC-2 Orte: Einträge von active_metrics überleben das Speichern aus dem Reiter Wetter', () => {
	const ABO = {
		id: 'cp-golden',
		display_config: {
			active_metrics: [
				{ metric_id: 'temperature', aggregation: 'max', sms_threshold: 3, kuenftiges_feld: ['x'] },
				{ metric_id: 'temperature', aggregation: 'min' },
				{ metric_id: 'wind', aggregation: 'max', format_mode: 'symbol' }
			],
			telegram_style: 'kurzform',
			hourly_metrics: ['wind']
		}
	};
	function nutzlast(geste: Geste) {
		const stand = geste(standAusAbo('vergleich', ABO as unknown as AboSicht, aufgeloestVon(ABO)));
		return vergleichNutzlast({
			client: null as never,
			stand: () => stand,
			vorlagen: () => VORLAGEN,
			abo: () => ABO as unknown as AboSicht,
			aggregationFuer: () => 'max'
		}).display_config as Record<string, unknown>;
	}

	test('ohne Änderung und mit neuer Metrik: Bestandseinträge vollständig und in ihrer Folge', () => {
		assert.deepEqual(nutzlast((s) => s).active_metrics, ABO.display_config.active_metrics);
		assert.deepEqual(nutzlast((s) => mitMetrik(s, 'gust', 'vergleich')).active_metrics, [
			...ABO.display_config.active_metrics,
			{ metric_id: 'gust', aggregation: 'max' }
		]);
	});

	test('fremde display_config-Schlüssel fahren nicht mit (der Server mischt, nichts wird ersetzt)', () => {
		assert.deepEqual(Object.keys(nutzlast((s) => ohneMetrik(s, 'wind'))).sort(), ['active_metrics', 'ampel']);
	});
});
