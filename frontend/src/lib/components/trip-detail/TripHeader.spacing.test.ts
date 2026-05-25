// TDD RED: Bug #335 — fehlendes Leerzeichen vor Tourname in der H1.
//
// Spec: docs/specs/modules/issue_335_h1_spacing.md
//
// Bug: Die H1 rendert "KHW ·Karnischer Höhenweg" — Svelte trimmt das
// nachgestellte Leerzeichen des Text-Nodes " · " direkt vor dem {/if}-Block-Ende.
// Soll: "KHW · Karnischer Höhenweg" (Leerzeichen auf beiden Seiten).
//
// Test-Pattern: Das Frontend nutzt `node --experimental-strip-types --test`, das
// KEINE `.svelte`-Imports laden kann. Daher Source-Inspection wie in
// `WeatherMetricsPreviewCard.tokens.test.ts` / `HorizonChip.test.ts`: wir lesen
// die `.svelte`-Datei als String und assertieren auf die Markup-Struktur, die
// das Whitespace-Trimming verhindert.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/TripHeader.spacing.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, 'TripHeader.svelte');
const source = readFileSync(COMPONENT, 'utf8');

// Die H1-Zeile mit shortcode-Separator isolieren.
const h1SeparatorLine =
	source.split('\n').find((line) => line.includes('h1-shortcode') && line.includes('{/if}')) ??
	'';

test('AC-1: Separator nach dem Shortcode endet mit nicht-trimmbarem Leerzeichen', () => {
	assert.ok(h1SeparatorLine, 'H1-Shortcode-Separatorzeile nicht gefunden');

	// Der Separator zwischen </span> und {/if} darf NICHT auf einem normalen
	// (trimmbaren) Leerzeichen enden — Svelte würde es entfernen → "·Name".
	// Erlaubt ist ein geschütztes Leerzeichen (&nbsp; / &#160; / &#xa0;).
	const protectedTrailing = /·\s*(&nbsp;|&#160;|&#xa0;|&#xA0;)\s*\{\/if\}/.test(h1SeparatorLine);
	assert.ok(
		protectedTrailing,
		`Erwartet geschütztes Leerzeichen nach dem Mittelpunkt vor {/if}, ` +
			`damit Svelte es nicht trimmt. Gefunden: ${JSON.stringify(h1SeparatorLine.trim())}`
	);
});

test('AC-1: keine getrimmte Sequenz "·{/if}" ohne schützendes Leerzeichen', () => {
	// Direkt aufeinanderfolgendes "·" und "{/if}" (nur normales Whitespace
	// dazwischen) bedeutet, das Leerzeichen wird beim Rendern verschluckt.
	const trimmedPattern = /·[ \t]*\{\/if\}/.test(h1SeparatorLine);
	assert.equal(
		trimmedPattern,
		false,
		`"·" darf nicht von trimmbarem Whitespace direkt vor {/if} gefolgt werden: ` +
			`${JSON.stringify(h1SeparatorLine.trim())}`
	);
});

test('AC-2: ohne Shortcode steht {trip.name} unmittelbar nach {/if}', () => {
	// Der Name folgt direkt auf den {/if}-Block — kein zusätzliches führendes
	// Leerzeichen ausserhalb der Bedingung, das ohne Shortcode sichtbar würde.
	assert.ok(
		/\{\/if\}\{trip\.name\}/.test(h1SeparatorLine),
		`Erwartet "{/if}{trip.name}" ohne führendes Leerzeichen. ` +
			`Gefunden: ${JSON.stringify(h1SeparatorLine.trim())}`
	);
});
