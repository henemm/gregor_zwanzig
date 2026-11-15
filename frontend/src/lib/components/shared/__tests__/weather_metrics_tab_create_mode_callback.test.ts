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

// Bug #2454 Fix-Loop 1 (Finding F001): die if/else-if/else-Kette aus
// initFromTrip() (inkl. des trip_default_enabled-Fallbacks, Test 5/AC-6
// unten) lebt seitdem als reine, exportierte Funktion `computeInitialBuckets()`
// in metricsEditor.ts -- WeatherMetricsTab.svelte enthaelt die Kette selbst
// nicht mehr woertlich. Die beiden Guards unten lesen deshalb ab jetzt DORT.
const METRICS_EDITOR_FILE = join(
	dirname(fileURLToPath(import.meta.url)), '..', '..', 'trip-detail', 'metricsEditor.ts',
);
const metricsEditorCode = readFileSync(METRICS_EDITOR_FILE, 'utf-8');

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

	test('von buildWeatherMetricsList() aufgerufene lokale Hilfsfunktionen lesen trip nur innerhalb untrack() (#2422 S2a)', () => {
		// #2422 S2a hat das Bestandslesen in die Hilfsfunktion
		// bestandDisplayConfigUngetrackt() ausgelagert. Der Test oben sieht nur
		// den Rumpf von buildWeatherMetricsList() -- die Mutation
		// `return untrack(() => trip?.display_config);` -> `return trip?.display_config;`
		// liess alle Tests gruen, obwohl `trip` damit wieder getrackte
		// Abhaengigkeit des Rueckkanal-Effects waere (Issue #1552,
		// effect_update_depth_exceeded auf Staging). Daher: jede lokal definierte
		// Funktion, die buildWeatherMetricsList() aufruft, darf `trip` nur
		// innerhalb eines untrack(() => ...)-Ausdrucks lesen.
		const fnMatch = code.match(/function buildWeatherMetricsList\(\)\s*\{[\s\S]*?\n\t\}/);
		assert.ok(fnMatch, 'buildWeatherMetricsList() nicht gefunden');
		const calledNames = new Set(
			[...fnMatch[0].matchAll(/\b([A-Za-z_$][\w$]*)\s*\(/g)].map((m) => m[1])
		);
		calledNames.delete('buildWeatherMetricsList');
		const checked: string[] = [];
		for (const name of calledNames) {
			const helper = code.match(
				new RegExp(`function ${name.replace(/\$/g, '\\$')}\\([^)]*\\)\\s*\\{[\\s\\S]*?\\n\\t\\}`)
			);
			if (!helper) continue; // importiert / kein lokales function-Statement
			checked.push(name);
			const rest = helper[0].replace(/untrack\(\(\)\s*=>[^;]*\)/g, '');
			assert.doesNotMatch(
				rest,
				/trip[!?.]/,
				`Hilfsfunktion ${name}() (aufgerufen aus buildWeatherMetricsList()) liest trip ` +
					'ausserhalb von untrack() -- damit waere trip wieder getrackte Abhaengigkeit ' +
					'des Rueckkanal-Effects (Issue #1552 / #2422 S2a)'
			);
		}
		assert.ok(
			checked.includes('bestandDisplayConfigUngetrackt'),
			'bestandDisplayConfigUngetrackt() wurde nicht als von buildWeatherMetricsList() ' +
				`aufgerufene lokale Hilfsfunktion gefunden und geprueft (geprueft: ${checked.join(', ') || 'keine'}) ` +
				'-- Test waere sonst vakuum-gruen'
		);
	});
});

describe('Issue #2931: Tagesfenster-Rueckkanal und Tagesfenster-Abschnitt sind entfernt', () => {
	// Der #1775-Rueckkanal (onDayWindowChange + $effect) und die Trip-Tagesfenster-Karte
	// wurden nie produktiv genutzt; das Tagesfenster stellt die AnpassenKarte im Reiter
	// Wetter ein (TripNewEditor.handleDayWindowChange ueber WetterTab).
	test('keine onDayWindowChange-Prop, kein Aufruf, kein tagesfenster-Abschnitt mehr', () => {
		assert.doesNotMatch(code, /\bonDayWindowChange\b/, 'onDayWindowChange ist noch vorhanden');
		assert.doesNotMatch(code, /sections\.includes\('tagesfenster'\)/, 'Abschnitt tagesfenster ist noch vorhanden');
		assert.doesNotMatch(code, /weather-metrics-tagesfenster/, 'Testkennung weather-metrics-tagesfenster ist noch vorhanden');
	});
});

describe('Test 5: Vorbelegungs-Fallback liest trip_default_enabled statt default_enabled', () => {
	// Bug #2454 Fix-Loop 1: der else-Zweig lebt jetzt in
	// metricsEditor.ts::computeInitialBuckets(), nicht mehr woertlich in
	// WeatherMetricsTab.svelte::initFromTrip() -- Guard liest deshalb dort.
	test('der createMode-Fallback-Zweig (keine gespeicherten Metriken) filtert nach trip_default_enabled', () => {
		// Fix-Loop 1 (Advisor-Befund): der Filter liest jetzt `allIds` (expliziter
		// Parameter, Ordering-Fidelity zu WeatherMetricsTab.svelte::allCatalogIds())
		// statt der privaten `allCatalogIds(catalog)` aus metricsEditor.ts.
		assert.match(
			metricsEditorCode,
			/\}\s*else\s*\{\s*const activeIds = allIds\.filter\(\(id\) => metricById\[id\]\?\.trip_default_enabled\);/,
			'Der Vorbelegungs-Fallback (computeInitialBuckets, else-Zweig) liest noch ' +
				'default_enabled statt trip_default_enabled — die Anzeige im Anlege-' +
				'Dialog würde weiterhin von der Orte/Abo-Vorbelegung abweichen'
		);
	});

	test('kein direkter Zugriff auf metricById[id]?.default_enabled bleibt uebrig', () => {
		// Regressionsschutz: die Ersetzung soll gezielt sein (nur der eine
		// Fallback-Zweig), nicht bloss ein zweites Vorkommen daneben stehen
		// lassen, das denselben Bug an anderer Stelle weiterleben liesse. Bug
		// #2454 Fix-Loop 1 (Advisor-Befund): BEIDE Dateien pruefen, nicht nur
		// die, in der die Kette heute lebt -- sonst koennte WeatherMetricsTab.svelte
		// den Bug unbemerkt wieder einfuehren.
		assert.doesNotMatch(
			code,
			/metricById\[id\]\?\.default_enabled(?!\s*\??:)/,
			'default_enabled wird in WeatherMetricsTab.svelte an unerwarteter Stelle noch direkt gelesen'
		);
		assert.doesNotMatch(
			metricsEditorCode,
			/metricById\[id\]\?\.default_enabled(?!\s*\??:)/,
			'default_enabled wird in metricsEditor.ts an unerwarteter Stelle noch direkt gelesen'
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
	// Bug #2454 Fix-Loop 1: die Kette zieht mit computeInitialBuckets() nach
	// metricsEditor.ts um -- Guard liest dort. Kein Mount-/DOM-Test moeglich
	// (kein jsdom); dieser Test haelt daher die GESAMTE Kette (alle drei
	// Bedingungen + der bekannte Fallback-Ausdruck im dritten Zweig) als EINEN
	// zusammenhaengenden Treffer fest.
	test('if (savedMetrics && hasBuckets) / else if (savedMetrics && savedMetrics.length) / else {...trip_default_enabled...} bilden EINE zusammenhaengende Kette', () => {
		const chainMatch = metricsEditorCode.match(
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
		const matches = metricsEditorCode.match(
			/if\s*\(savedMetrics\s*&&\s*hasBuckets\)\s*\{[\s\S]*?\}\s*else if\s*\(savedMetrics\s*&&\s*savedMetrics\.length\)\s*\{[\s\S]*?\}\s*else\s*\{[\s\S]*?metricById\[id\]\?\.trip_default_enabled[\s\S]*?\}/g
		) ?? [];
		assert.equal(matches.length, 1, `Erwartet genau 1 Treffer, gefunden: ${matches.length}`);
	});
});
