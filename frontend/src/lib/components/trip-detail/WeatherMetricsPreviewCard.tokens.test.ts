// TDD RED: Bug #329 (AP-010) — keine hardcodierten font-sizes in
// WeatherMetricsPreviewCard.svelte; nur --g-text-* Tokens erlaubt.
//
// Spec: docs/specs/modules/bug_329_weather_metrics_preview_fontsize.md
//
// Diese Tests scheitern absichtlich (RED-Phase): die Komponente nutzt noch
// 4 feste rem-Werte (1rem / 0.875rem / 0.75rem / 0.875rem) statt der
// Typografie-Tokens.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/WeatherMetricsPreviewCard.tokens.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, 'WeatherMetricsPreviewCard.svelte');
const source = readFileSync(COMPONENT, 'utf8');

test('AC-1: keine hardcodierten font-size-Zahlenwerte mehr', () => {
	const matches = source.match(/font-size:\s*[0-9]/g) ?? [];
	assert.deepEqual(
		matches,
		[],
		`Erwartet 0 hardcodierte font-size-Werte, gefunden ${matches.length}: ${matches.join(', ')}`
	);
});

test('AC-3: erwartete --g-text-* Tokens werden verwendet', () => {
	for (const token of ['--g-text-md', '--g-text-sm', '--g-text-xs']) {
		assert.ok(
			source.includes(`var(${token})`),
			`Token var(${token}) fehlt im <style>-Block`
		);
	}
});
