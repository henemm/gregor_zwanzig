// #1592 Scheibe C3 AC-9: die CAPE-Schwellenanzeige behauptet keine Zahl, die
// nirgends wirkt — UND bleibt als Änderungsschwelle ("Δ ≥") erkennbar, nicht
// als absoluter Grenzwert (Adversary-Nachbesserung, Team-Lead 2026-08-09).
//
// Spec: docs/specs/modules/fix_1592_c3_cape_delta_alarme.md (AC-9)
//
// `levelToThreshold('cape', 'standard')` liefert jetzt "Δ ≥ ~600 J/kg" —
// die Tilde markiert die Näherung, das "Δ ≥" bleibt erhalten (sonst würde
// CAPE optisch wie eine THRESHOLD_CROSSING-Metrik, z. B. Sicht "< 1000 m",
// wirken, obwohl es weiterhin eine ÄNDERUNGSschwelle ist). Die Erklärung
// ("wird je Wettermodell und Gebiet umgerechnet") sitzt NICHT im knappen
// Zellentext, sondern im `title`-Attribut der Zelle
// (`thresholdTitle()` → `AlertMetricLevelRow.svelte`).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/alerts-tab/__tests__/capeRichtwertAnzeige.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { levelToThreshold, thresholdTitle } from '../alertMetricTable.ts';

// ─────────────────────────────────────────────────────────────────────────
// AC-9: CAPE/standard trägt weiterhin die Zahl 600, die Einheit J/kg UND
// das "Δ ≥" (Änderungsschwelle, kein absoluter Grenzwert) — zusätzlich
// markiert als Näherung (Tilde).
// ─────────────────────────────────────────────────────────────────────────

test('cape > standard liefert exakt "Δ ≥ ~600 J/kg" (AC-9, Δ bleibt erhalten)', () => {
	const text = levelToThreshold('cape', 'standard');
	assert.equal(
		text,
		'Δ ≥ ~600 J/kg',
		'CAPE bleibt eine Δ-Schwelle (nicht "< 600 J/kg" wie ein absoluter Grenzwert) — ' +
			'die Tilde markiert die Näherung, "Δ ≥" darf nicht verschwinden.',
	);
});

test('cape > standard behält das führende "Δ ≥" (Regressions-Wächter gegen die letzte Fassung)', () => {
	// Genau der Fehler der vorigen Fassung ("~600 J/kg (Modell)"): das "Δ ≥"
	// fehlte, CAPE sah wie ein absoluter Grenzwert aus. Dieser Test faengt
	// jede kuenftige Aenderung ab, die das "Δ ≥" wieder verliert.
	const text = levelToThreshold('cape', 'standard') as string;
	assert.match(text, /^Δ ≥ /, 'muss mit "Δ ≥ " beginnen');
	assert.match(text, /~600/, 'die Näherung (Tilde) vor der Zahl muss erhalten bleiben');
	assert.match(text, /J\/kg/, 'muss weiterhin die Einheit J/kg zeigen');
});

// ─────────────────────────────────────────────────────────────────────────
// AC-9: die Erklärung sitzt im `title`, nicht im Zellentext -- nur für CAPE.
// ─────────────────────────────────────────────────────────────────────────

test('thresholdTitle("cape") erklärt die Umrechnung je Modell/Gebiet (AC-9)', () => {
	assert.equal(
		thresholdTitle('cape'),
		'Richtwert — wird je Wettermodell und Gebiet umgerechnet',
	);
});

test('thresholdTitle > alle anderen Metriken liefern kein title (Gegenprobe AC-9)', () => {
	assert.equal(thresholdTitle('wind_gust'), undefined);
	assert.equal(thresholdTitle('visibility'), undefined);
	assert.equal(thresholdTitle('precipitation_sum'), undefined);
	assert.equal(thresholdTitle('freezing_level'), undefined);
});

// ─────────────────────────────────────────────────────────────────────────
// Gegenprobe (AC-9: "bei allen anderen Metriken bleibt die Anzeige
// unverändert") — Windböen und Sicht dürfen durch die CAPE-Änderung nicht
// mitverändert werden.
// ─────────────────────────────────────────────────────────────────────────

test('wind_gust > standard bleibt unverändert "Δ ≥ 20 km/h" (Gegenprobe AC-9)', () => {
	assert.equal(levelToThreshold('wind_gust', 'standard'), 'Δ ≥ 20 km/h');
});

test('visibility > standard bleibt unverändert "< 1000 m" (Gegenprobe AC-9)', () => {
	assert.equal(levelToThreshold('visibility', 'standard'), '< 1000 m');
});
