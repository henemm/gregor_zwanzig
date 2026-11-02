// Issue #2655 (i18n F6, Adversary F001) — Waechter: ein Sprachwechsel OHNE
// Neuladen (`locale.set('en')` im laufenden Client) erreicht jede Anzeige.
// tr()/trn() lesen die Sprache per get(locale) — nicht reaktiv. Jedes `$derived`
// und jeder Markup-Ausdruck, der einen tr()-nutzenden Helfer aufruft, muss daher
// `$locale` (oder `$t`/`$tn`) lesen; Startwerte duerfen solche Helfer nicht
// einfrieren. Ein Client-Mount ist mangels DOM (kein jsdom/happy-dom) nicht
// moeglich; der Waechter prueft die Verdrahtung am AST (reaktivitaet_scan.ts).
//
// SPAETERE PAKETE (F8, F5, F7, F9, F10 …): eigenen Komponentenordner bzw. eigene
// Dateien in BEREICHE eintragen; begruendete Ausnahmen in AUSNAHMEN.
// Spec: docs/specs/modules/i18n_f6_versand_tab_2655.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/reaktivitaet_waechter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { scanneKomponente, scanneEintraege, type Fund } from './reaktivitaet_scan.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SRC = join(HIER, '..', '..', '..');

/** Gepruefte Flaechen je Paket (Pfade relativ zu frontend/src, Verzeichnisse mit `/`). */
const BEREICHE: Record<string, string[]> = {
	'F3 #2652 Cockpit und Listen': [
		'routes/+page.svelte',
		'routes/_home/',
		'routes/trips/+page.svelte',
		'routes/compare/+page.svelte',
		'routes/locations/+page.svelte',
		'routes/archiv/+page.svelte',
		'lib/components/organisms/ListTable.svelte'
	],
	'F4 #2653 Konto, Admin, Navigation': [
		'routes/account/',
		'routes/admin/',
		'lib/components/account/',
		'lib/components/ui/sidebar/',
		'lib/components/ui/SaveIndicator.svelte'
	],
	'F6 #2655 Versand-Reiter': [
		'lib/components/shared/VersandTab.svelte',
		'lib/components/shared/TelegramKurzstilToggle.svelte',
		'lib/components/shared/versand-tab/'
	],
	'F5 #2654 Wertebereiche-Reiter': [
		'lib/components/shared/WeatherMetricsTab.svelte',
		'lib/components/shared/StandardwerteSpeichernKnopf.svelte',
		'lib/components/shared/weather-metrics-tab/'
	]
};

/**
 * Begruendete Ausnahmen: Pfad + Ausschnitt des gemeldeten Ausdrucks. Nur, wenn
 * der Ausdruck nachweislich KEINEN Text liefert (der Waechter arbeitet je Export).
 */
const AUSNAHMEN: { pfad: string; enthaelt: string; grund: string }[] = [
	{
		pfad: 'routes/+page.svelte',
		enthaelt: '$derived(firstIncompleteCompare(presets))',
		grund: 'liefert ein ComparePreset (kein Text); ruft setupStepCompare nur fuer die done-Flags'
	}
];

const zeile = (f: Fund) => `${f.pfad}:${f.zeile} [${f.art}] ${f.text}`;
const ausgenommen = (f: Fund) => AUSNAHMEN.some((a) => a.pfad === f.pfad && f.text.includes(a.enthaelt));

/** Beispielquelltext im Ordner des Versand-Reiters (fuer die Import-Aufloesung). */
const BEISPIEL_DATEI = join(SRC, 'lib', 'components', 'shared', 'versand-tab', 'Beispiel_2655.svelte');
const beispiel = (skript: string, markup = '') =>
	scanneKomponente(`<script lang="ts">\n${skript}\n</script>\n${markup}`, BEISPIEL_DATEI, SRC, 'Beispiel').map((f) => `${f.zeile} ${f.art}`);

describe('Selbsttest an Beispielquelltexten', () => {
	const IMPORT = "import { premiumSmsChannelState } from './premiumSmsChannelState';\nimport { t, locale, tr } from '$lib/i18n';";
	test('$derived mit tr()-Helfer ohne $locale ist rot, mit $locale gruen', () => {
		assert.deepEqual(beispiel(`${IMPORT}\nlet p = $state(null);\nconst a = $derived(premiumSmsChannelState(p));`), ['5 derived']);
		assert.deepEqual(beispiel(`${IMPORT}\nlet p = $state(null);\nconst a = $derived.by(() => premiumSmsChannelState(p));`), ['5 derived']);
		assert.deepEqual(beispiel(`${IMPORT}\nlet p = $state(null);\nconst a = $derived.by(() => (void $locale, premiumSmsChannelState(p)));`), []);
		assert.deepEqual(beispiel(`${IMPORT}\nconst a = $derived(tr('versand.kanaele.titel'));`), ['4 derived']);
		assert.deepEqual(beispiel(`${IMPORT}\nconst a = $derived($t('versand.kanaele.titel'));`), []);
	});
	test('transitiv: sendTargetLabel (ruft tr) und lokale Helfer zaehlen, sprachfreie Exporte nicht', () => {
		const imp = "import { sendTargetLabel } from './sendTargetLabel';\nimport { channelContactLabel } from './channelContactLabel';";
		assert.deepEqual(beispiel(`${imp}\nlet p = $state(null);\nconst a = $derived(sendTargetLabel(p, null));`), ['5 derived']);
		assert.deepEqual(beispiel(`${imp}\nlet p = $state(null);\nconst a = $derived(channelContactLabel(p));`), []);
		assert.deepEqual(beispiel(`${imp}\nlet p = $state(null);\nfunction ziel() { return sendTargetLabel(p, null).text; }\nconst a = $derived(ziel());`), ['6 derived']);
	});
	test('Markup-Ausdruck ohne $locale ist rot; Ereignis-Handler und $t sind gruen', () => {
		const imp = "import { formatNextBriefing } from './nextBriefingText';\nimport { t, locale } from '$lib/i18n';\nlet nb = $state(null);\nfunction weiter() { formatNextBriefing(nb); }";
		assert.deepEqual(beispiel(imp, '<p>{formatNextBriefing(nb)}</p>'), ['7 markup']);
		assert.deepEqual(beispiel(imp, '<p>{(void $locale, formatNextBriefing(nb))}</p>'), []);
		assert.deepEqual(beispiel(imp, '<button onclick={() => formatNextBriefing(nb)}>{$t(\'versand.naechstes.titel\')}</button>'), []);
		assert.deepEqual(beispiel(imp, '<button onclick={weiter}>x</button>'), []);
	});
	test('Startwerte frieren ein: Konstante, $state-Start, $props-Standardwert', () => {
		const imp = "import { vtBriefingLeadText } from './vtBriefingChannelsText';";
		assert.deepEqual(beispiel(`${imp}\nconst a = vtBriefingLeadText('route');`), ['3 eingefroren']);
		assert.deepEqual(beispiel(`${imp}\nlet a = $state(vtBriefingLeadText('route'));`), ['3 eingefroren']);
		assert.deepEqual(beispiel(`${imp}\nlet { a = vtBriefingLeadText('route') } = $props();`), ['3 eingefroren']);
		assert.deepEqual(beispiel(`${imp}\nconst f = () => vtBriefingLeadText('route');`), []);
	});
});

describe('Bestand: Sprachwechsel ohne Neuladen erreicht jede Anzeige', () => {
	for (const [paket, eintraege] of Object.entries(BEREICHE)) {
		test(paket, () => {
			const { dateien, funde } = scanneEintraege(SRC, eintraege);
			assert.ok(dateien.length >= eintraege.length, `Messaufbau: nur ${dateien.length} Dateien`);
			const offen = funde.filter((f) => !ausgenommen(f));
			assert.deepEqual(
				offen.map(zeile),
				[],
				'Sprachabhaengiger Helfer ohne $locale — Muster `$derived.by(() => (void $locale, helfer()))` bzw. `{(void $locale, helfer())}`'
			);
		});
	}

	test('Messaufbau: der Versand-Reiter hat sprachabhaengige Ableitungen (Waechter nicht vakuum)', () => {
		// Ohne die $locale-Lesung wuerden die fuenf $derived des Reiters gemeldet:
		// dieselbe Quelle mit entferntem `void $locale` muss rot sein.
		const { dateien } = scanneEintraege(SRC, BEREICHE['F6 #2655 Versand-Reiter']);
		let gezaehlt = 0;
		for (const rel of dateien) {
			const q = readFileSync(join(SRC, rel), 'utf8') as string;
			const ohne = q.replace(/\$derived\.by\(\(\) => \(void \$locale, ([^\n]*)\)\);/g, '$derived($1);');
			gezaehlt += scanneKomponente(ohne, join(SRC, rel), SRC, rel).filter((f) => f.art === 'derived').length;
		}
		assert.equal(gezaehlt, 5);
	});

	test('jede Ausnahme trifft noch einen Fund (keine toten Eintraege)', () => {
		const alle = Object.values(BEREICHE).flatMap((e) => scanneEintraege(SRC, e).funde);
		for (const a of AUSNAHMEN) assert.ok(alle.some((f) => f.pfad === a.pfad && f.text.includes(a.enthaelt)), `tote Ausnahme: ${a.enthaelt}`);
	});
});
