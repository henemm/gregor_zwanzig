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
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const moleculesDir = dirname(fileURLToPath(import.meta.url));
const componentsRoot = join(moleculesDir, '..');
const organismsDir = join(componentsRoot, 'organisms');

const read = (f: string) => readFileSync(f, 'utf-8');
const has = (f: string) => existsSync(f);
const readMol = (name: string) => read(join(moleculesDir, name));
const hasMol = (name: string) => has(join(moleculesDir, name));
const readOrg = (name: string) => read(join(organismsDir, name));
const hasOrg = (name: string) => has(join(organismsDir, name));

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
	test('SetupResumeCard Footer-Leiste: card-alt + "Weiter bei"', () => {
		const src = readMol('SetupResumeCard.svelte');
		assert.ok(
			/g-card-alt/.test(src),
			'SetupResumeCard: Footer-Leiste mit --g-card-alt-Hintergrund fehlt'
		);
		assert.ok(
			/Weiter bei/.test(src),
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
	test('CompareStatusRow Empfänger-Chip nur wenn preset.empfaenger gesetzt', () => {
		const src = readMol('CompareStatusRow.svelte');
		// Muss conditional rendern: {#if ... empfaenger ...}
		assert.ok(
			/\{#if.*empfaenger|empfaenger.*\{#if/.test(src),
			'CompareStatusRow: Empfänger-Chip muss conditional gerendert werden ({#if empfaenger...})'
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

describe('AC-6: StageCascadeNotice — neues Molecule', () => {
	test('StageCascadeNotice.svelte existiert in molecules/', () => {
		assert.ok(
			hasMol('StageCascadeNotice.svelte'),
			'molecules/StageCascadeNotice.svelte fehlt — noch nicht implementiert'
		);
	});
	test('StageCascadeNotice done=false: accent-tint + Btns', () => {
		const src = readMol('StageCascadeNotice.svelte');
		assert.ok(/g-accent-tint/.test(src), 'StageCascadeNotice: --g-accent-tint fehlt');
		assert.ok(/g-accent/.test(src), 'StageCascadeNotice: --g-accent border-left fehlt');
		assert.ok(/Alle mitverschieben/.test(src), 'StageCascadeNotice: "Alle mitverschieben"-CTA fehlt');
		assert.ok(/Nur diese Etappe/.test(src), 'StageCascadeNotice: "Nur diese Etappe"-CTA fehlt');
	});
	test('StageCascadeNotice done=true: good-tint + Bestätigungstext', () => {
		const src = readMol('StageCascadeNotice.svelte');
		assert.ok(
			/rgba\(61,107,58.*0\.10\)|g-good-tint|green.*0\.10/.test(src),
			'StageCascadeNotice done: grüner Hintergrund fehlt'
		);
		assert.ok(/g-good/.test(src), 'StageCascadeNotice done: --g-good border-left fehlt');
	});
	test('StageCascadeNotice in molecules/index.ts exportiert', () => {
		const idx = readMol('index.ts');
		assert.ok(
			/StageCascadeNotice/.test(idx),
			'molecules/index.ts: StageCascadeNotice nicht exportiert'
		);
	});
});

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

describe('AC-9: CompareChannelSwitch — neues Molecule', () => {
	test('CompareChannelSwitch.svelte existiert in molecules/', () => {
		assert.ok(
			hasMol('CompareChannelSwitch.svelte'),
			'molecules/CompareChannelSwitch.svelte fehlt — noch nicht implementiert'
		);
	});
	test('CompareChannelSwitch aktiver Kanal: card + shadow-1', () => {
		const src = readMol('CompareChannelSwitch.svelte');
		assert.ok(/g-shadow-1/.test(src), 'CompareChannelSwitch: --g-shadow-1 für aktiven Kanal fehlt');
		assert.ok(/g-card/.test(src), 'CompareChannelSwitch: --g-card für aktiven Kanal fehlt');
	});
	// #610: signal entfernt — CompareChannelSwitch zeigt nur noch 3 Kanäle
	test('CompareChannelSwitch rendert Email, Telegram, SMS (kein Signal, #610)', () => {
		const src = readMol('CompareChannelSwitch.svelte');
		for (const ch of ['email', 'telegram', 'sms']) {
			assert.ok(src.includes(ch), `CompareChannelSwitch: Kanal "${ch}" fehlt`);
		}
		assert.ok(!src.includes("'signal'") && !src.includes('"signal"'), 'CompareChannelSwitch darf nach #610 kein Signal mehr enthalten');
	});
	test('CompareChannelSwitch in molecules/index.ts exportiert', () => {
		const idx = readMol('index.ts');
		assert.ok(
			/CompareChannelSwitch/.test(idx),
			'molecules/index.ts: CompareChannelSwitch nicht exportiert'
		);
	});
});

describe('AC-10–13: Compare-Briefing-Vorschau-Molecules', () => {
	const PREVIEW_MOLS = [
		'ComparePreviewMissing',
		'CompareBriefingPreview',
		'CompareChatBubble',
		'CompareSmsPreview',
	];

	for (const name of PREVIEW_MOLS) {
		test(`${name}.svelte existiert in molecules/`, () => {
			assert.ok(
				hasMol(`${name}.svelte`),
				`molecules/${name}.svelte fehlt — noch nicht implementiert`
			);
		});
		test(`${name} in molecules/index.ts exportiert`, () => {
			const idx = readMol('index.ts');
			assert.ok(
				new RegExp(`\\b${name}\\b`).test(idx),
				`molecules/index.ts: ${name} nicht exportiert`
			);
		});
	}

	test('AC-11: CompareChatBubble hat Telegram-Farben (#610: Signal-Farben entfernt)', () => {
		const src = readMol('CompareChatBubble.svelte');
		assert.ok(/#17212b/.test(src), 'CompareChatBubble: Telegram-Backdrop #17212b fehlt');
		assert.ok(/#5ea9dd/.test(src), 'CompareChatBubble: Telegram-Accent #5ea9dd fehlt');
	});

	test('AC-12: CompareSmsPreview kürzt bei > 140 Zeichen + Warn-Farbe', () => {
		const src = readMol('CompareSmsPreview.svelte');
		assert.ok(/140/.test(src), 'CompareSmsPreview: 140-Zeichen-Limit fehlt');
		assert.ok(/#f0a060/.test(src), 'CompareSmsPreview: Warn-Farbe #f0a060 bei Überschreitung fehlt');
	});

	test('AC-13: ComparePreviewMissing hat dashed-border', () => {
		const src = readMol('ComparePreviewMissing.svelte');
		assert.ok(/dashed/.test(src), 'ComparePreviewMissing: border: 1px dashed ... fehlt');
		assert.ok(/g-rule/.test(src), 'ComparePreviewMissing: --g-rule fehlt');
	});
});

// ════════════════ BLOCK C — Neue Organisms ════════════════

const HOME_ORGANISMS = ['HomeHeroTrip', 'HomeHeroCompare', 'OutboxCard', 'AlertsCard'];
const METRICS_ORGANISMS = ['PresetRail', 'MetricOffShelf', 'MetricsEditorContextBar'];

describe('AC-14/15: Home-Hero-Organisms', () => {
	for (const name of ['HomeHeroTrip', 'HomeHeroCompare']) {
		test(`${name}.svelte existiert in organisms/`, () => {
			assert.ok(
				hasOrg(`${name}.svelte`),
				`organisms/${name}.svelte fehlt — noch nicht implementiert`
			);
		});
	}

	test('AC-14: HomeHeroTrip hat border-left: 3px solid var(--g-accent)', () => {
		const src = readOrg('HomeHeroTrip.svelte');
		assert.ok(
			/3px solid var\(--g-accent\)/.test(src),
			'HomeHeroTrip: border-left: 3px solid var(--g-accent) fehlt'
		);
	});

	test('AC-14: HomeHeroTrip Footer-Leiste mit card-alt + Kanal-Dots + Trip-öffnen-Link', () => {
		const src = readOrg('HomeHeroTrip.svelte');
		assert.ok(/g-card-alt/.test(src), 'HomeHeroTrip: Footer card-alt fehlt');
		assert.ok(/Trip öffnen/.test(src), 'HomeHeroTrip: "Trip öffnen →"-Link fehlt');
		assert.ok(/Kanäle|Eyebrow/.test(src), 'HomeHeroTrip: Kanal-Eyebrow in Footer fehlt');
	});

	test('AC-14: HomeHeroTrip Pills-Reihe zuerst', () => {
		const src = readOrg('HomeHeroTrip.svelte');
		assert.ok(/Pill/.test(src), 'HomeHeroTrip: Pills-Atom fehlt');
		assert.ok(/Live/.test(src), 'HomeHeroTrip: "Live · Tag X von Y" fehlt');
	});

	test('AC-15: HomeHeroCompare hat 2-Spalten-Stat-Grid', () => {
		const src = readOrg('HomeHeroCompare.svelte');
		assert.ok(/grid-template-columns.*1fr.*1fr|repeat\(2/.test(src), 'HomeHeroCompare: 2-Spalten-Grid fehlt');
		assert.ok(/Zeitplan/.test(src), 'HomeHeroCompare: "Zeitplan"-Stat fehlt');
		assert.ok(/Nächster Versand/.test(src), 'HomeHeroCompare: "Nächster Versand"-Stat fehlt');
	});

	test('AC-15: HomeHeroCompare border-left: 3px solid var(--g-accent)', () => {
		const src = readOrg('HomeHeroCompare.svelte');
		assert.ok(
			/3px solid var\(--g-accent\)/.test(src),
			'HomeHeroCompare: border-left: 3px solid var(--g-accent) fehlt'
		);
	});
});

describe('AC-16/17: OutboxCard + AlertsCard', () => {
	test('AC-16: OutboxCard.svelte existiert in organisms/', () => {
		assert.ok(hasOrg('OutboxCard.svelte'), 'organisms/OutboxCard.svelte fehlt');
	});
	test('AC-16: OutboxCard hat Eyebrow "Versand · heute" + "Was geht raus" + Pill good', () => {
		const src = readOrg('OutboxCard.svelte');
		assert.ok(/Versand.*heute|heute.*Versand/.test(src), 'OutboxCard: Eyebrow "Versand · heute" fehlt');
		assert.ok(/Was geht raus/.test(src), 'OutboxCard: "Was geht raus"-Titel fehlt');
		assert.ok(/Alle Kanäle ok/.test(src), 'OutboxCard: Pill "Alle Kanäle ok" fehlt');
		assert.ok(/BriefingTimelineRow/.test(src), 'OutboxCard: BriefingTimelineRow-Import fehlt');
	});

	test('AC-17: AlertsCard.svelte existiert in organisms/', () => {
		assert.ok(hasOrg('AlertsCard.svelte'), 'organisms/AlertsCard.svelte fehlt');
	});
	test('AC-17: AlertsCard Eyebrow "Alerts · letzte 24 h" + Schwellen-Link', () => {
		const src = readOrg('AlertsCard.svelte');
		assert.ok(/Alerts.*letzte 24|24.*Alerts/.test(src), 'AlertsCard: Eyebrow "Alerts · letzte 24 h" fehlt');
		assert.ok(/Schwellen/.test(src), 'AlertsCard: "Schwellen →"-Link fehlt');
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
		'StageCascadeNotice',
		'HorizonChips',
		'ScoreToggle',
		'CompareChannelSwitch',
		'CompareBriefingPreview',
		'CompareChatBubble',
		'CompareSmsPreview',
		'ComparePreviewMissing',
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
