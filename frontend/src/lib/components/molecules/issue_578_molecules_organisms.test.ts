// TDD RED: Issue #578 — Design-Fidelity: Molecules + Organisms 1:1
//
// Spec: docs/specs/modules/issue_578_molecules_organisms.md
// Bindende Quellen: molecules.jsx, organisms.jsx, sidebar.jsx, screen-home.jsx
//
// Source-Inspection-Tests (kein Render, keine Mocks):
// - Block A: Divergenz-Fixes in bestehenden Molecules (AC-1 bis AC-5)
// - Block B: Neue Molecules prüfen (AC-6 bis AC-13)
// - Block C: Neue Organisms prüfen (AC-14 bis AC-20)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/molecules/issue_578_molecules_organisms.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';
import { register } from 'node:module';

const moleculesDir = dirname(fileURLToPath(import.meta.url));
const componentsRoot = join(moleculesDir, '..');
const organismsDir = join(componentsRoot, 'organisms');

const read = (f: string) => readFileSync(f, 'utf-8');
const has = (f: string) => existsSync(f);
const readMol = (name: string) => read(join(moleculesDir, name));
const hasMol = (name: string) => has(join(moleculesDir, name));
const readOrg = (name: string) => read(join(organismsDir, name));
const hasOrg = (name: string) => has(join(organismsDir, name));

// #2660 (i18n F11): Texte stehen im Katalog; ihre Pruefung laeuft deshalb ueber
// den echten SSR-Render (deutsche Standard-Sprache), nicht ueber den Quelltext.
let ssrRegistriert = false;
async function gerenderterText(rel: string, props: Record<string, unknown>): Promise<string> {
	const frontend = join(componentsRoot, '..', '..', '..');
	if (!ssrRegistriert) {
		register(pathToFileURL(join(frontend, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(frontend + '/').href);
		ssrRegistriert = true;
	}
	const { render } = await import('svelte/server');
	const komp = (await import(pathToFileURL(join(componentsRoot, rel)).href)).default;
	return render(komp, { props: props as never }).body.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ');
}

// ════════════════ BLOCK A — Divergenz-Fixes ════════════════

describe('AC-1: QuickAction — Shadow + Rule-Border + Mono-Sub + SVG-Chevron', () => {
	test('QuickAction.svelte existiert', () => {
		assert.ok(hasMol('QuickAction.svelte'), 'molecules/QuickAction.svelte fehlt');
	});
	test('QuickAction hat box-shadow (g-shadow-1 im Normalzustand)', () => {
		const src = readMol('QuickAction.svelte');
		assert.ok(
			/g-shadow-1/.test(src),
			'QuickAction: --g-shadow-1 fehlt (JSX: boxShadow: "var(--g-shadow-1)")'
		);
	});
	test('QuickAction hat g-shadow-2 im Hover-Zustand', () => {
		const src = readMol('QuickAction.svelte');
		assert.ok(
			/g-shadow-2/.test(src),
			'QuickAction: --g-shadow-2 (Hover) fehlt (JSX: hover ? "var(--g-shadow-2,...)")'
		);
	});
	test('QuickAction border nutzt --g-rule (nicht --g-rule-soft)', () => {
		const src = readMol('QuickAction.svelte');
		assert.ok(
			/var\(--g-rule\)/.test(src),
			'QuickAction: border muss --g-rule nutzen (nicht --g-rule-soft)'
		);
		// Stellt sicher, dass --g-rule-soft NICHT als Border-Hauptwert genutzt wird
		// (darf noch in anderen Kontexten vorkommen, aber nicht als Primär-Border)
		const borderLines = src.split('\n').filter(l =>
			/border[^-]/.test(l) && /rule-soft/.test(l) && !/border-radius/.test(l)
		);
		assert.strictEqual(
			borderLines.length, 0,
			`QuickAction hat noch --g-rule-soft als border-Wert: ${borderLines.join(' | ')}`
		);
	});
	test('QuickAction sub-Text hat mono + uppercase + letter-spacing', () => {
		const src = readMol('QuickAction.svelte');
		assert.ok(
			/text-transform.*uppercase|uppercase.*text-transform/.test(src) ||
			/text-transform="uppercase"/.test(src),
			'QuickAction sub: text-transform: uppercase fehlt (JSX: textTransform: "uppercase")'
		);
		assert.ok(
			/letter-spacing.*0\.04|letter-spacing="0\.04em"/.test(src),
			'QuickAction sub: letter-spacing: 0.04em fehlt'
		);
		assert.ok(
			/g-font-mono/.test(src),
			'QuickAction sub: font-family: var(--g-font-mono) fehlt'
		);
	});
	test('QuickAction Chevron ist SVG (kein ASCII ›)', () => {
		const src = readMol('QuickAction.svelte');
		assert.ok(
			/<svg/.test(src) && /M9 6l6 6-6 6/.test(src),
			'QuickAction: Chevron-SVG (path d="M9 6l6 6-6 6") fehlt — ASCII › ist verboten'
		);
		assert.ok(
			!src.includes('›'),
			'QuickAction: ASCII-Chevron › noch vorhanden — durch SVG ersetzen'
		);
	});
});

describe('AC-2/3: SetupResumeCard — accent-Leiste + Shadow + Chip-Layout + Footer', () => {
	test('SetupResumeCard.svelte existiert', () => {
		assert.ok(hasMol('SetupResumeCard.svelte'), 'molecules/SetupResumeCard.svelte fehlt');
	});
	test('SetupResumeCard accent: border-left: 3px solid var(--g-accent)', () => {
		const src = readMol('SetupResumeCard.svelte');
		assert.ok(
			/3px solid var\(--g-accent\)/.test(src),
			'SetupResumeCard: border-left: 3px solid var(--g-accent) für tone=accent fehlt'
		);
	});
	test('SetupResumeCard border nutzt --g-rule (nicht --g-rule-soft als Haupt-Border)', () => {
		const src = readMol('SetupResumeCard.svelte');
		assert.ok(
			/var\(--g-rule\)/.test(src),
			'SetupResumeCard: --g-rule als Haupt-Border fehlt'
		);
	});
	test('SetupResumeCard hat box-shadow: var(--g-shadow-1)', () => {
		const src = readMol('SetupResumeCard.svelte');
		assert.ok(
			/g-shadow-1/.test(src),
			'SetupResumeCard: box-shadow: var(--g-shadow-1) fehlt'
		);
	});
	test('SetupResumeCard Schritte als Chip-Reihe (flex-wrap + g-r-pill)', () => {
		const src = readMol('SetupResumeCard.svelte');
		assert.ok(
			/flex-wrap/.test(src),
			'SetupResumeCard: Schritte-Chips müssen flex-wrap haben'
		);
		assert.ok(
			/g-r-pill/.test(src),
			'SetupResumeCard: Chip-Reihe braucht border-radius: var(--g-r-pill)'
		);
	});
	test('SetupResumeCard Footer-Leiste: card-alt + "Weiter bei"', async () => {
		const src = readMol('SetupResumeCard.svelte');
		assert.ok(
			/g-card-alt/.test(src),
			'SetupResumeCard: Footer-Leiste mit --g-card-alt-Hintergrund fehlt'
		);
		const text = await gerenderterText('molecules/SetupResumeCard.svelte', {
			eyebrow: 'E', title: 'T', ctaLabel: 'Weiter', ctaHref: '/x',
			steps: [{ label: 'Route', done: true }, { label: 'Etappen', done: false }]
		});
		assert.ok(
			/Weiter bei: Etappen/.test(text),
			'SetupResumeCard: "Weiter bei:"-Text in Footer fehlt'
		);
	});
});

describe('AC-4: BriefingTimelineRow — "geplant"-Farbe --g-ink-4', () => {
	test('BriefingTimelineRow.svelte existiert', () => {
		assert.ok(hasMol('BriefingTimelineRow.svelte'), 'molecules/BriefingTimelineRow.svelte fehlt');
	});
	test('BriefingTimelineRow nutzt --g-ink-4 für "geplant" (nicht --g-ink-3)', () => {
		const src = readMol('BriefingTimelineRow.svelte');
		// JSX: color: isSent ? "var(--g-good)" : "var(--g-ink-4)"
		assert.ok(
			/g-ink-4/.test(src),
			'BriefingTimelineRow: --g-ink-4 für geplant-Status fehlt (IST: --g-ink-3)'
		);
		// Sicherstellen dass --g-ink-3 nicht fälschlicherweise für den Status-Span genutzt wird
		// (suche explizit den Status-Span-Kontext)
		const lines = src.split('\n');
		const statusLine = lines.findIndex(l => /geplant/.test(l));
		if (statusLine >= 0) {
			const ctx = lines.slice(Math.max(0, statusLine - 5), statusLine + 5).join('\n');
			assert.ok(
				!/g-ink-3/.test(ctx),
				'BriefingTimelineRow: Status-Span nutzt noch --g-ink-3 statt --g-ink-4'
			);
		}
	});
});

describe('AC-5: CompareStatusRow — konsistente Empfänger-Pille', () => {
	test('CompareStatusRow.svelte existiert', () => {
		assert.ok(hasMol('CompareStatusRow.svelte'), 'molecules/CompareStatusRow.svelte fehlt');
	});
	// fix-1452 (AC-8): Der Chip zeigt seit #1452 das Kanal-LABEL aus
	// presetChannels() statt der rohen `empfaenger`-Adresse. Der alte Assert
	// forderte genau die entfallene `{#if ... empfaenger ...}`-Bedingung und
	// prüfte damit veraltetes Verhalten — hier auf die Kanal-Quelle nachgezogen.
	test('CompareStatusRow Kanal-Chip stammt aus presetChannels, nie aus empfaenger', () => {
		const src = readMol('CompareStatusRow.svelte');
		assert.ok(
			/presetChannels\(preset\)/.test(src),
			'CompareStatusRow: Kanal-Chips müssen aus presetChannels(preset) stammen'
		);
		assert.ok(
			!/\{#each\s+preset\.empfaenger/.test(src),
			'CompareStatusRow: rohe empfaenger-Adressen dürfen nicht mehr als Chip gerendert werden'
		);
	});
	test('CompareStatusRow hat white-space: nowrap für Spalten-Konsistenz', () => {
		const src = readMol('CompareStatusRow.svelte');
		assert.ok(
			/white-space.*nowrap|nowrap/.test(src),
			'CompareStatusRow: white-space: nowrap fehlt (Spalten müssen konsistent bleiben)'
		);
	});
});

// ════════════════ BLOCK B — Neue Molecules ════════════════

// AC-6 (StageCascadeNotice) entfernt 2026-07-25 mit #1375: die Molecule war seit
// #578 nirgends eingebunden — die produktiv sichtbare Kaskaden-Rückfrage lebt
// inline in edit/EditStagesPanelNew.svelte. Komponente gelöscht, damit es nur
// eine Fassung dieses Dialogs gibt; die Tests hier prüften ohnehin nur
// Dateiinhalte per Regex (kein Verhaltensnachweis nach Projekt-Testpolitik).

describe('AC-7: HorizonChips — neues Molecule', () => {
	test('HorizonChips.svelte existiert in molecules/', () => {
		assert.ok(
			hasMol('HorizonChips.svelte'),
			'molecules/HorizonChips.svelte fehlt — noch nicht implementiert'
		);
	});
	test('HorizonChips aktiver Chip nutzt accent-Tokens', () => {
		const src = readMol('HorizonChips.svelte');
		assert.ok(/g-accent-tint/.test(src), 'HorizonChips: aktiver Chip --g-accent-tint fehlt');
		assert.ok(/g-accent-deep/.test(src), 'HorizonChips: aktiver Chip --g-accent-deep fehlt');
	});
	test('HorizonChips hat compact-Prop', () => {
		const src = readMol('HorizonChips.svelte');
		assert.ok(/compact/.test(src), 'HorizonChips: compact-Prop fehlt');
	});
	test('HorizonChips in molecules/index.ts exportiert', () => {
		const idx = readMol('index.ts');
		assert.ok(/HorizonChips/.test(idx), 'molecules/index.ts: HorizonChips nicht exportiert');
	});
});

describe('AC-8: ScoreToggle — neues Molecule', () => {
	test('ScoreToggle.svelte existiert in molecules/', () => {
		assert.ok(
			hasMol('ScoreToggle.svelte'),
			'molecules/ScoreToggle.svelte fehlt — noch nicht implementiert'
		);
	});
	test('ScoreToggle on=true: accent-tint + accent-deep', () => {
		const src = readMol('ScoreToggle.svelte');
		assert.ok(/g-accent-tint/.test(src), 'ScoreToggle on=true: --g-accent-tint fehlt');
		assert.ok(/g-accent-deep/.test(src), 'ScoreToggle on=true: --g-accent-deep fehlt');
	});
	test('ScoreToggle on=false: g-rule + paper-deep', () => {
		const src = readMol('ScoreToggle.svelte');
		assert.ok(/g-paper-deep/.test(src), 'ScoreToggle on=false: --g-paper-deep fehlt');
	});
	test('ScoreToggle in molecules/index.ts exportiert', () => {
		const idx = readMol('index.ts');
		assert.ok(/ScoreToggle/.test(idx), 'molecules/index.ts: ScoreToggle nicht exportiert');
	});
});

// AC-9 (CompareChannelSwitch) und AC-10–13 (Compare-Briefing-Vorschau-Molecules)
// entfallen: die Briefing-Vorschau ist ersatzlos entfernt (#2283 AC-14, #1743 F003,
// PO-Entscheid 2026-10-22). Die Abwesenheit prueft der Block „#2283 AC-14" unten.

// ════════════════ Issue #2283 AC-14 — tote/ersetzte Vorschau-Molecules entfernt ════════════════
//
// Spec: docs/specs/modules/shared_preview_tab.md (AC-14). Geprueft ueber echte
// Importe (Barrel laden, Exportliste lesen; Komponentenpfad laden) statt ueber
// Dateitext. Der Barrel enthaelt .svelte-Dateien, deshalb laufen die Importe
// ueber die SSR-Hooks (frontend/test-svelte-ssr-hooks.mjs, Pfadregel #1409).
//
// RED HEUTE: der Barrel exportiert alle drei noch, die Dateien laden noch.
describe('#2283 AC-14: CompareBriefingPreview, ComparePreviewMissing, CompareSmsPreview entfernt', () => {
	const FRONTEND = join(componentsRoot, '../../..');
	// #1743 F003 (PO-Entscheid 2026-10-22): auch CompareChannelSwitch und
	// CompareChatBubble entfallen — die Briefing-Vorschau ist ersatzlos weg.
	const ENTFERNT = [
		'CompareBriefingPreview',
		'ComparePreviewMissing',
		'CompareSmsPreview',
		'CompareChannelSwitch',
		'CompareChatBubble'
	];

	let registriert = false;
	async function barrel(): Promise<Record<string, unknown>> {
		if (!registriert) {
			register(
				pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
				pathToFileURL(FRONTEND + '/').href
			);
			registriert = true;
		}
		return (await import(pathToFileURL(join(moleculesDir, 'index.ts')).href)) as Record<string, unknown>;
	}

	for (const name of ENTFERNT) {
		test(`molecules/index.ts exportiert ${name} nicht mehr`, async () => {
			const mod = await barrel();
			assert.equal(
				name in mod,
				false,
				`molecules/index.ts exportiert ${name} noch — AC-14: der Baustein ist entfallen bzw. tot (#1270) und faellt samt Barrel-Eintrag`
			);
		});
		test(`${name}.svelte laesst sich nicht mehr laden`, async () => {
			await barrel();
			await assert.rejects(
				import(pathToFileURL(join(moleculesDir, `${name}.svelte`)).href),
				(e: { code?: string }) => e.code === 'ERR_MODULE_NOT_FOUND',
				`molecules/${name}.svelte ist noch vorhanden — AC-14 verlangt die Entfernung`
			);
		});
	}
});

// ════════════════ BLOCK C — Neue Organisms ════════════════

// Issue #1969 (AC-25): HomeHeroCompare ist gelöscht (kein Importeur; die
// Startseite rendert ihren Vergleichs-Hero inline in routes/+page.svelte) —
// AC-15 hat damit keinen Prüfling mehr.
// Issue #2346 S2 (AC-10): HomeHeroTrip ist ebenfalls gelöscht (kein Importeur) —
// AC-14 hat damit keinen Prüfling mehr; der Hero folgt in S3 als ein `HomeHero`.
const HOME_ORGANISMS = ['OutboxCard', 'AlertsCard'];
const METRICS_ORGANISMS = ['PresetRail', 'MetricOffShelf', 'MetricsEditorContextBar'];

describe('AC-16/17: OutboxCard + AlertsCard', () => {
	test('AC-16: OutboxCard.svelte existiert in organisms/', () => {
		assert.ok(hasOrg('OutboxCard.svelte'), 'organisms/OutboxCard.svelte fehlt');
	});
	test('AC-16: OutboxCard hat Eyebrow "Versand · heute" + "Was geht raus" + Pill good', async () => {
		const src = readOrg('OutboxCard.svelte');
		const text = await gerenderterText('organisms/OutboxCard.svelte', { contextName: 'GR20', reports: [] });
		assert.ok(/Versand · heute/.test(text), 'OutboxCard: Eyebrow "Versand · heute" fehlt');
		assert.ok(/Was geht raus · GR20/.test(text), 'OutboxCard: "Was geht raus"-Titel fehlt');
		assert.ok(/Alle Kanäle ok/.test(text), 'OutboxCard: Pill "Alle Kanäle ok" fehlt');
		assert.ok(/<Pill tone="good">/.test(src), 'OutboxCard: Pill good fehlt');
		assert.ok(/BriefingTimelineRow/.test(src), 'OutboxCard: BriefingTimelineRow-Import fehlt');
	});

	test('AC-17: AlertsCard.svelte existiert in organisms/', () => {
		assert.ok(hasOrg('AlertsCard.svelte'), 'organisms/AlertsCard.svelte fehlt');
	});
	test('AC-17: AlertsCard Eyebrow "Alerts · letzte 24 h" + Schwellen-Link', async () => {
		const text = await gerenderterText('organisms/AlertsCard.svelte', { alerts: [] });
		assert.ok(/Alerts · letzte 24 h/.test(text), 'AlertsCard: Eyebrow "Alerts · letzte 24 h" fehlt');
		assert.ok(/Schwellen →/.test(text), 'AlertsCard: "Schwellen →"-Link fehlt');
	});
	test('AC-17: AlertsCard rendert AlertRow bei alerts > 0', () => {
		const src = readOrg('AlertsCard.svelte');
		assert.ok(/AlertRow/.test(src), 'AlertsCard: AlertRow-Import fehlt');
	});
});

describe('AC-18: Metrics-Organisms (PresetRail, MetricOffShelf, MetricsEditorContextBar)', () => {
	for (const name of METRICS_ORGANISMS) {
		test(`${name}.svelte existiert in organisms/`, () => {
			assert.ok(
				hasOrg(`${name}.svelte`),
				`organisms/${name}.svelte fehlt — noch nicht implementiert`
			);
		});
	}

	test('PresetRail rendert Preset-Liste + Eigenes-Profil-Block', () => {
		const src = readOrg('PresetRail.svelte');
		assert.ok(/Eigenes Profil|presets/.test(src), 'PresetRail: Preset-Rendering fehlt');
	});

	test('MetricOffShelf hat "Nicht im Briefing"-Aufklapp-Logik', () => {
		const src = readOrg('MetricOffShelf.svelte');
		assert.ok(
			/Nicht im Briefing|nicht.*briefing|offShelf/i.test(src),
			'MetricOffShelf: "Nicht im Briefing"-Sektion fehlt'
		);
	});

	test('MetricsEditorContextBar hat Context + Preset + Bucket-Summary', () => {
		const src = readOrg('MetricsEditorContextBar.svelte');
		assert.ok(/context|preset|bucket/i.test(src), 'MetricsEditorContextBar: Context/Preset/Bucket fehlt');
	});
});

describe('AC-19: organisms/index.ts — alle neuen Organisms exportiert', () => {
	const ALL_NEW_ORGANISMS = [
		...HOME_ORGANISMS,
		...METRICS_ORGANISMS,
	];

	test('organisms/index.ts existiert', () => {
		assert.ok(hasOrg('index.ts'), 'organisms/index.ts fehlt');
	});

	for (const name of ALL_NEW_ORGANISMS) {
		test(`organisms/index.ts exportiert ${name}`, () => {
			const barrel = readOrg('index.ts');
			assert.ok(
				new RegExp(`\\b${name}\\b`).test(barrel),
				`organisms/index.ts exportiert ${name} nicht`
			);
		});
	}
});

describe('AC-20: molecules/index.ts — alle neuen Molecules exportiert', () => {
	const ALL_NEW_MOLECULES = [
		// 'StageCascadeNotice' entfällt seit #1375 (tote Zweitfassung, s.o.)
		'HorizonChips',
		'ScoreToggle',
		// CompareBriefingPreview, CompareSmsPreview, ComparePreviewMissing entfallen
		// mit #2283 AC-14, CompareChannelSwitch und CompareChatBubble mit #1743 F003
		// (Gegenprobe: Block „#2283 AC-14" oben).
	];

	for (const name of ALL_NEW_MOLECULES) {
		test(`molecules/index.ts exportiert ${name}`, () => {
			const idx = readMol('index.ts');
			assert.ok(
				new RegExp(`\\b${name}\\b`).test(idx),
				`molecules/index.ts exportiert ${name} nicht`
			);
		});
	}
});
