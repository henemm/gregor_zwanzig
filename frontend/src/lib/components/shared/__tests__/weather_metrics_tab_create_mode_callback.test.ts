// Issue #1552 — fehlender Rückkanal aus dem Trip-Anlege-Modus.
//
// Spec: docs/specs/modules/fix_1552_neuanlage_metrikauswahl.md § Test 3, Test 5
//
// Kein Mount-/DOM-Test möglich (kein jsdom/happy-dom im Frontend-Test-Setup,
// $effect ist per SSR nie sichtbar) — Source-Inspection-Muster analog
// shared/__tests__/weatherMetricsTabSharing.test.ts: readFileSync auf die
// Produktivdatei + Assertions auf die konkrete Wirkung (Guard-Bedingung UND
// übergebener Payload-Ausdruck), nicht bloße String-Presence.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/weather_metrics_tab_create_mode_callback.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const FILE = join(dirname(fileURLToPath(import.meta.url)), '..', 'WeatherMetricsTab.svelte');
const code = readFileSync(FILE, 'utf-8');

describe('AC-1/AC-2/AC-3 (Test 3): onWeatherMetricsChange-Rückkanal im Anlege-Modus', () => {
	test('Props-Interface hat eine onWeatherMetricsChange-Prop mit WeatherConfigMetric[]-Callback', () => {
		assert.match(
			code,
			/onWeatherMetricsChange\??\s*:\s*\(\s*metrics\s*:\s*WeatherConfigMetric\[\]\s*\)\s*=>\s*void/,
			'Keine onWeatherMetricsChange-Prop vom erwarteten Typ gefunden'
		);
	});

	test('onWeatherMetricsChange wird aus den Props destrukturiert', () => {
		assert.match(
			code,
			/let\s*\{[^}]*onWeatherMetricsChange[^}]*\}\s*:\s*Props\s*=\s*\$props\(\)/,
			'onWeatherMetricsChange fehlt in der Props-Destrukturierung'
		);
	});

	test('ein $effect ruft im createMode+catalogLoaded onWeatherMetricsChange mit buildWeatherMetricsList() auf', () => {
		// Bewusst NICHT nur "kommt der Text vor" — die Guard-Bedingung und der
		// übergebene Ausdruck müssen exakt zusammenhängen (derselbe Effect-Block),
		// sonst könnte ein leerer/falscher Callback-Aufruf denselben Text streuen.
		//
		// Fix-Loop 3 (Staging-Befund, effect_update_depth_exceeded trotz
		// Fix-Loop 2): der Effect ruft jetzt buildWeatherMetricsList() (liest
		// `trip` gar nicht) statt buildWeatherPayload().metrics, UND das Guard
		// verlangt zusaetzlich catalogLoaded -- ohne dieses Gate ueberschreiben
		// sich die zwei WeatherMetricsTab-Mounts (Desktop+Mobile,
		// TripNewEditor.svelte) gegenseitig, solange eine der beiden Instanzen
		// ihren eigenen Katalog noch nicht geladen hat (leere Liste schlaegt
		// die laengst gueltige Liste der anderen Instanz tot -- Endlosschleife
		// per Playwright reproduziert, docs/artifacts/fix-1552-neuanlage-
		// metrikverlust/red_effect_loop_playwright.txt).
		const effectMatch = code.match(
			/\$effect\(\(\)\s*=>\s*\{\s*if\s*\(createMode\s*&&\s*onWeatherMetricsChange\s*&&\s*catalogLoaded\)\s*\{\s*onWeatherMetricsChange\(buildWeatherMetricsList\(\)\);/
		);
		assert.ok(
			effectMatch,
			'Kein $effect gefunden, der bei createMode && onWeatherMetricsChange && ' +
				'catalogLoaded onWeatherMetricsChange(buildWeatherMetricsList()) aufruft'
		);
	});

	test('der neue Effect ist NICHT identisch mit dem bestehenden onChannelsChange-Effect (eigener Block)', () => {
		const weatherEffectCount = (
			code.match(/\$effect\(\(\)\s*=>\s*\{\s*if\s*\(createMode\s*&&\s*onWeatherMetricsChange\s*&&\s*catalogLoaded\)/g) ?? []
		).length;
		assert.equal(weatherEffectCount, 1, 'Der Wetter-Metrik-Rückkanal-Effect muss genau einmal vorkommen');
	});

	test('buildWeatherMetricsList() liest trip nicht (Fix-Loop 3, Root-Cause-Guard)', () => {
		const fnMatch = code.match(/function buildWeatherMetricsList\(\)\s*\{[\s\S]*?\n\t\}/);
		assert.ok(fnMatch, 'buildWeatherMetricsList() nicht gefunden');
		assert.doesNotMatch(
			fnMatch[0],
			/trip[!?.]/,
			'buildWeatherMetricsList() liest trip -- damit waere trip wieder eine ' +
				'getrackte Abhaengigkeit des Rueckkanal-Effects (Fix-Loop-2-Regression)'
		);
	});
});

describe('Test 5: Vorbelegungs-Fallback liest trip_default_enabled statt default_enabled', () => {
	test('der createMode-Fallback-Zweig (keine gespeicherten Metriken) filtert nach trip_default_enabled', () => {
		// Zielt gezielt auf den else-Zweig in initFromTrip() (Fall "savedMetrics
		// fehlt/leer") -- NICHT auf irgendeine Stelle im File, sonst faengt der
		// Test einen Treffer im falschen Zweig (AC-6 Regression) nicht.
		assert.match(
			code,
			/\}\s*else\s*\{\s*\/\/[^\n]*\n(?:\s*\/\/[^\n]*\n)*\s*const activeIds = allCatalogIds\(\)\.filter\(\(id\) => metricById\[id\]\?\.trip_default_enabled\);/,
			'Der Vorbelegungs-Fallback (initFromTrip, else-Zweig) liest noch ' +
				'default_enabled statt trip_default_enabled — die Anzeige im Anlege-' +
				'Dialog würde weiterhin von der Orte/Abo-Vorbelegung abweichen'
		);
	});

	test('kein direkter Zugriff auf metricById[id]?.default_enabled bleibt uebrig', () => {
		// Regressionsschutz: die Ersetzung soll gezielt sein (nur der eine
		// Fallback-Zweig), nicht bloss ein zweites Vorkommen daneben stehen
		// lassen, das denselben Bug an anderer Stelle weiterleben liesse.
		assert.doesNotMatch(
			code,
			/metricById\[id\]\?\.default_enabled(?!\s*\??:)/,
			'default_enabled wird an unerwarteter Stelle noch direkt gelesen'
		);
	});
});

describe('AC-6 (Adversary-Befund F002, Fix-Loop 1, HIGH): die vollstaendige if/else-if/else-Kette bleibt erhalten', () => {
	// Der Fallback-Zweig-Test oben prueft NUR den Koerper des else-Zweigs, nicht
	// die BEDINGUNG des mittleren else-if-Zweigs, der ueberhaupt erst entscheidet,
	// ob der Fallback erreicht wird. Der Adversary hat genau diese Bedingung zu
	// `savedMetrics.length > 100` verfaelscht (Realtrips haben typischerweise
	// weit unter 100 Katalog-Eintraege, ihr eigener else-if-Zweig ist damit
	// NIE mehr erreichbar -- jeder Trip mit gespeicherter, bewusster
	// Komplett-Abwahl faellt still auf die 7 Standardgroessen zurueck, AC-6-
	// Regression) -- alle Tests oben blieben dabei gruen, weil sie nur den
	// unveraenderten else-Zweig-KOERPER matchen, nicht die Kette drumherum.
	// Kein Mount-/DOM-Test moeglich (kein jsdom); dieser Test haelt daher die
	// GESAMTE Kette (alle drei Bedingungen + der bekannte Fallback-Ausdruck im
	// dritten Zweig) als EINEN zusammenhaengenden Treffer fest.
	test('if (savedMetrics && hasBuckets) / else if (savedMetrics && savedMetrics.length) / else {...trip_default_enabled...} bilden EINE zusammenhaengende Kette', () => {
		const chainMatch = code.match(
			/if\s*\(savedMetrics\s*&&\s*hasBuckets\)\s*\{[\s\S]*?\}\s*else if\s*\(savedMetrics\s*&&\s*savedMetrics\.length\)\s*\{[\s\S]*?\}\s*else\s*\{[\s\S]*?metricById\[id\]\?\.trip_default_enabled[\s\S]*?\}/
		);
		assert.ok(
			chainMatch,
			'Die vollstaendige Drei-Wege-Kette (inkl. der Bedingung ' +
				'"savedMetrics && savedMetrics.length" des mittleren Zweigs) ist ' +
				'nicht mehr im erwarteten Zusammenhang -- eine verfaelschte ' +
				'Zwischenbedingung (z.B. eine zusaetzliche Laengen-Schwelle) wuerde ' +
				'jede gespeicherte Auswahl am Fallback-Zweig vorbeischleusen (AC-6)'
		);
	});

	test('genau EINE Kette dieser Form existiert (kein zweites, abweichendes Duplikat)', () => {
		const matches = code.match(
			/if\s*\(savedMetrics\s*&&\s*hasBuckets\)\s*\{[\s\S]*?\}\s*else if\s*\(savedMetrics\s*&&\s*savedMetrics\.length\)\s*\{[\s\S]*?\}\s*else\s*\{[\s\S]*?metricById\[id\]\?\.trip_default_enabled[\s\S]*?\}/g
		) ?? [];
		assert.equal(matches.length, 1, `Erwartet genau 1 Treffer, gefunden: ${matches.length}`);
	});
});
