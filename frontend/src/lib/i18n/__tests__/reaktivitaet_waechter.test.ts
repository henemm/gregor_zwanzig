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

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
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
	// #3385: Bereich „F6 #2655 Versand-Reiter" gestrichen — versand-tab/ enthaelt nach dem
	// Loeschen der Waisen keine .svelte-Datei mehr; TelegramKurzstilToggle.svelte steht
	// ausdruecklich in der Dateiliste von Bereich F7 (der Scan folgt keinen Importen).
	'F5 #2654 Wertebereiche-Reiter': [
		'lib/components/shared/StandardwerteSpeichernKnopf.svelte',
		'lib/components/shared/weather-metrics-tab/'
	],
	'F8 #2657 Layout-Reiter, Korridor-Editor, Ausgabe-Layout, GPX': [
		// #3366: layout-tab/ enthaelt keine Komponente mehr (LayoutTab, LTCapNote,
		// LTChannelPicker, LTCutLine als Waisen geloescht; ltChannels.ts ist kein .svelte).
		// #2794 S3a Teil-PR 4a: corridor-editor/ (CorridorEditor, CorridorEditorMobile) entfernt.
		'lib/components/shared/OutputLayoutEditor.svelte',
		'routes/gpx-upload/'
	],
	'F9 #2658 Trip-Hub, Anlegen, Etappen-Editor, Vorschau-Rahmen': [
		'lib/components/trip-detail/',
		'lib/components/trip-new/',
		'lib/components/edit/',
		'lib/components/email-preview/',
		'lib/components/shared/subscription-header/',
		'lib/components/shared/BriefingHistory.svelte',
		'routes/trips/[id]/',
		'routes/trips/new/'
	],
	'F7 #2656 Alarme-Reiter, Alarm-Kanal-Picker, alerts-tab': [
		'lib/components/shared/AlarmeTab.svelte',
		'lib/components/shared/AlertChannelPicker.svelte',
		'lib/components/shared/TelegramKurzstilToggle.svelte',
		'lib/components/alerts-tab/'
	],
	'F10 #2659 Ortsvergleich-Hub, Anlegen, Orte, transponierte Uebersicht': [
		'lib/components/compare/',
		'lib/components/compare-new/',
		'lib/components/shared/hub-uebersicht/',
		'routes/compare/[id]/',
		'routes/compare/new/'
	]
};

/**
 * Begruendete Ausnahmen: Pfad + Ausschnitt des gemeldeten Ausdrucks. Nur, wenn
 * der Ausdruck nachweislich KEINEN Text liefert (der Waechter arbeitet je Export).
 * Zweite, eng gefasste Kategorie: der Ausdruck ist der EINMALIGE Startwert eines
 * Eingabefelds, das ab dem Start Nutzerdaten haelt. Eine Neuberechnung beim
 * Sprachwechsel wuerde dort Nutzereingaben ueberschreiben, deshalb ist das
 * Einfrieren hier gewollt. Der Grund muss das Feld benennen. Die Kategorie gilt
 * NICHT allgemein fuer `$state`-Startwerte.
 */
const AUSNAHMEN: { pfad: string; enthaelt: string; grund: string }[] = [
	{
		pfad: 'routes/+page.svelte',
		enthaelt: '$derived(firstIncompleteCompare(presets))',
		grund: 'liefert ein ComparePreset (kein Text); ruft setupStepCompare nur fuer die done-Flags'
	},
	{
		pfad: 'routes/compare/[id]/+page.svelte',
		enthaelt: 'abmeldenUebernahme = hubSaveCtl.registriereUebernahme(',
		grund: 'registriert nur einen Rueckruf (Abmelde-Funktion, kein Text); der Rueckruf laedt per getMitFassung, dessen Fehlertexte erst beim Fehlschlag entstehen'
	},
	{
		pfad: 'lib/components/compare-new/CompareNewEditor.svelte',
		// Trifft NUR die eigene Deklaration `vorlagenFelder` (Fund-Text: erste 90 Zeichen,
		// reaktivitaet_scan.ts `ausschnitt`); der `$state`-Startwert `wiz` bleibt voll gescannt.
		enthaelt: 'vorlagenFelder = untrack(() => (vorlage ? feldsatzAusVorlage(vorlage, locations, vorlageId',
		grund:
			'Namensfeld: Vorschlagsname „<Name> (Kopie)“ (tr(\'vergleich.neu.kopie\')) ist der einmalige Startwert des Namensfelds beim Anlegen aus Vorlage und danach Nutzereingabe. Verhalten identisch zu main #2659, dort als Anweisung `vorlageInZustand` in routes/compare/new/+page.svelte. #2727 verlegt die Uebernahme in den Initialisierer (AC-7: einmalig, kein $effect).'
	}
];

const zeile = (f: Fund) => `${f.pfad}:${f.zeile} [${f.art}] ${f.text}`;
const ausgenommen = (f: Fund) => AUSNAHMEN.some((a) => a.pfad === f.pfad && f.text.includes(a.enthaelt));

/** Beispielquelltext im Ordner des Versand-Reiters (fuer die Import-Aufloesung). */
const BEISPIEL_DATEI = join(SRC, 'lib', 'components', 'shared', 'versand-tab', 'Beispiel_2655.svelte');
const beispiel = (skript: string, markup = '', datei = BEISPIEL_DATEI) =>
	scanneKomponente(`<script lang="ts">\n${skript}\n</script>\n${markup}`, datei, SRC, 'Beispiel').map((f) => `${f.zeile} ${f.art}`);

// #3385: erfundene Mini-Module statt der geloeschten channelContactLabel.ts und
// vtBriefingChannelsText.ts. Der Scanner loest relative Importe auf echte Dateien auf,
// deshalb liegen sie als Dateien in einem temporaeren Ordner; `$lib/i18n` loest er ueber SRC.
const MINI = mkdtempSync(join(tmpdir(), 'reaktivitaet-mini-'));
writeFileSync(join(MINI, 'sprachfrei.ts'), "export function sprachfrei(p: unknown): string {\n\treturn p ? 'ja' : 'nein';\n}\n");
writeFileSync(
	join(MINI, 'textHelfer.ts'),
	"import { tr } from '$lib/i18n';\nexport function leadText(context: string): string {\n\treturn context ? tr('beispiel.mini.text') : '';\n}\n"
);
const MINI_DATEI = join(MINI, 'Beispiel_3385.svelte');
after(() => rmSync(MINI, { recursive: true, force: true }));

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
		const imp = "import { sendTargetLabel } from './sendTargetLabel';\nimport { t } from '$lib/i18n';";
		const impMini = "import { sendTargetLabel } from '$lib/components/shared/versand-tab/sendTargetLabel';\nimport { sprachfrei } from './sprachfrei';";
		assert.deepEqual(beispiel(`${imp}\nlet p = $state(null);\nconst a = $derived(sendTargetLabel(p, null));`), ['5 derived']);
		assert.deepEqual(beispiel(`${impMini}\nlet p = $state(null);\nconst a = $derived(sprachfrei(p));`, '', MINI_DATEI), []);
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
		const imp = "import { leadText } from './textHelfer';";
		assert.deepEqual(beispiel(`${imp}\nconst a = leadText('route');`, '', MINI_DATEI), ['3 eingefroren']);
		assert.deepEqual(beispiel(`${imp}\nlet a = $state(leadText('route'));`, '', MINI_DATEI), ['3 eingefroren']);
		assert.deepEqual(beispiel(`${imp}\nlet { a = leadText('route') } = $props();`, '', MINI_DATEI), ['3 eingefroren']);
		assert.deepEqual(beispiel(`${imp}\nconst f = () => leadText('route');`, '', MINI_DATEI), []);
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

	// #3385: der Messaufbau des Bereichs F6 (Zaehlung 5) entfaellt mit dem Bereich; die fuenf
	// $derived gehoerten zu den geloeschten Bausteinen des Versand-Reiters.

	test('Messaufbau F8: ohne die $locale-Lesung bleibt keine Ableitung (Zaehlung nach #3366: 0)', () => {
		// LTCapNote (1) entfaellt mit #3366 (Waise geloescht, 1 → 0); MailInhaltCard (1) und der
		// Abwahl-Hinweis (1) entfallen mit #3297/#3020. Die neun Fundstellen von
		// CorridorEditor (4) und CorridorEditorMobile (5) entfallen mit #2794 S3a Teil-PR 4a.
		const { dateien } = scanneEintraege(SRC, BEREICHE['F8 #2657 Layout-Reiter, Korridor-Editor, Ausgabe-Layout, GPX']);
		let gezaehlt = 0;
		for (const rel of dateien) {
			const q = (readFileSync(join(SRC, rel), 'utf8') as string).replace(/\(void \$locale, /g, '(');
			gezaehlt += scanneKomponente(q, join(SRC, rel), SRC, rel).length;
		}
		assert.equal(dateien.length, 2, 'Messaufbau: OutputLayoutEditor und GPX-Seite werden gescannt');
		assert.equal(gezaehlt, 0);
	});

	test('Messaufbau F7: ohne die $locale-Lesung waeren zwei Ableitungen/Ausdruecke gemeldet', () => {
		// AlarmeTab: Premium-SMS-Sperre (derived) und Gruppen-Ueberschrift (markup).
		// #2793 S2b: der Richtwert-Hinweis der AlertMetricLevelRow (CAPE-title an
		// der Δ-Schwellwert-Zelle) entfaellt mit der nur lesbaren Tabelle (3 -> 2).
		const { dateien } = scanneEintraege(SRC, BEREICHE['F7 #2656 Alarme-Reiter, Alarm-Kanal-Picker, alerts-tab']);
		// #1895 S4: die fuenf toten alerts-tab-Bausteine (AlertsTab, AlertCard,
		// AlertMetricTable/-Row, AlertPresetSelector) sind entfernt (13 -> 8 Dateien).
		assert.ok(dateien.length >= 8, `Messaufbau: nur ${dateien.length} Dateien`);
		let gezaehlt = 0;
		for (const rel of dateien) {
			const q = (readFileSync(join(SRC, rel), 'utf8') as string).replace(/\(void \$locale, /g, '(');
			gezaehlt += scanneKomponente(q, join(SRC, rel), SRC, rel).length;
		}
		assert.equal(gezaehlt, 2);
	});

	test('jede Ausnahme trifft noch einen Fund (keine toten Eintraege)', () => {
		const alle = Object.values(BEREICHE).flatMap((e) => scanneEintraege(SRC, e).funde);
		for (const a of AUSNAHMEN) assert.ok(alle.some((f) => f.pfad === a.pfad && f.text.includes(a.enthaelt)), `tote Ausnahme: ${a.enthaelt}`);
	});
});
