// TDD RED — Issue #2795 S3b, Teilschritt 1b (Neubau Reiter „Zustellung“): Struktur-Waechter per AST.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — Implementation Details §1, §3, §5, §7;
// AC-1 (Marker abschnittskopf), AC-27/AC-31 (keine Kanaele je Wettergroesse, keine amtlichen Warnungen/Radar,
// kein „Alarm ab“, keine zweite Kanalauswahl), AC-30 (Uebergangsblock), AC-33 (EIN Speicherer),
// AC-36 (Profil genau einmal), AC-37 (Marker fuer den Elementlisten-Abgleich), AC-39/AC-40 (Anker #versand
// an der Briefing-Zeiten-Karte), #1170/ADR-0097 (keine Compare-Komponente mit Trip-Pendant).
//
// Reiter-Baum = shared/zustellung-tab/ZustellungTab.svelte + alle .svelte unter organisms/zustellung-tab/
// (+ Modell/Speicherer unter shared/zustellung-tab/ fuer die Profil-Zaehlung).
//
// Messweise: AST ueber svelte/compiler (s3a2794Ast.ts), keine Textmuster-Suche im Quelltext.
// RED heute: organisms/zustellung-tab/ fehlt; ZustellungTab mountet noch WetterMetrikenVersandPanel mit
// <section id="versand"> (VersandTab/BriefingScheduleTab) und den AlarmeTab (AlertMetricChannelsBlock,
// AlertChannelPicker, amtliche Warnungen …).
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3b2795_zustellung_struktur.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, statSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
	svelteAst,
	tsAst,
	aufrufe,
	aufgerufener,
	attribut,
	propNamen,
	einbettungenMitWeichen,
	reiterVon,
	type Knoten
} from './s3a2794Ast.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');
const ORGANISMEN = join(KOMP, 'organisms', 'zustellung-tab');
const SHARED_ZT = join(KOMP, 'shared', 'zustellung-tab');
const REITER = join(SHARED_ZT, 'ZustellungTab.svelte');
const PANEL = join(KOMP, 'shared', 'WetterMetrikenVersandPanel.svelte');
const TRIP_HUB = join(KOMP, 'trip-detail', 'TripTabs.svelte');
const VERGLEICH_HUB = join(KOMP, 'compare', 'CompareTabs.svelte');

const MARKER = ['abschnittskopf', 'briefing-zeiten', 'laufzeit', 'kanaele', 'stille-stunden', 'uebergang'];

/** Alt-Bausteine, die der neue Reiter NICHT mehr einbettet (Spec §7, AC-27, AC-31, §5). */
const VERBOTEN = [
	'AlertMetricChannelsBlock', // „Kanaele je Wettergroesse“ entfaellt (AC-27)
	'WarnungenRadarKarte', // amtliche Warnungen & Radar wohnen im Reiter Wetter (AC-31)
	'AlarmAbKopf', // „Alarm ab“ je Metrik wohnt im Reiter Wetter (AC-31)
	'AlertMetricLevelTable', // „Alarm ab“ je Metrik (Alt-Tabelle, AC-31)
	'AlertChannelPicker', // zweite Kanalauswahl fuer Alarme (AC-31)
	'AlarmeTab',
	'AlarmeScheduleTab',
	'VersandTab', // alter Versand-Abschnitt <section id="versand"> (§5)
	'BriefingScheduleTab',
	'VTBriefingChannels',
	'VTSchedulePlan',
	'AlertCooldownCard',
	'AlertQuietHoursCard'
];
const VERBOTENE_SPEICHER_MODULE = ['versandVergleichSpeicherung', 'alarmeVergleichSpeicherung', 'tripSpeicherung', 'alarmeDeliveryPayload'];

function organismDateien(): string[] {
	if (!existsSync(ORGANISMEN)) return [];
	return readdirSync(ORGANISMEN)
		.filter((f) => f.endsWith('.svelte'))
		.map((f) => join(ORGANISMEN, f))
		.filter((f) => statSync(f).isFile());
}

function baum(): string[] {
	assert.ok(existsSync(ORGANISMEN), 'TDD RED: Ordner organisms/zustellung-tab/ fehlt (Organismen des Reiters)');
	const org = organismDateien();
	assert.ok(org.length > 0, 'TDD RED: keine .svelte-Datei unter organisms/zustellung-tab/');
	return [REITER, ...org];
}

/** Alle Knoten eines Teilbaums, die `pred` erfuellen. */
function alle(x: unknown, pred: (n: Knoten) => boolean, aus: Knoten[] = []): Knoten[] {
	if (Array.isArray(x)) x.forEach((y) => alle(y, pred, aus));
	else if (x && typeof x === 'object') {
		const n = x as Knoten;
		if (pred(n)) aus.push(n);
		for (const [k, v] of Object.entries(n)) if (k !== 'parent' && k !== 'loc' && k !== 'metadata') alle(v, pred, aus);
	}
	return aus;
}

const istElement = (n: Knoten) => n.type === 'RegularElement' || n.type === 'Component' || n.type === 'SvelteElement';

function statisch(n: Knoten, quelle: string, name: string): string | null {
	return attribut(n, quelle, name)?.literal ?? null;
}

function importe(datei: string): Array<{ quelle: string; namen: string[] }> {
	const { ast } = svelteAst(datei);
	const out: Array<{ quelle: string; namen: string[] }> = [];
	for (const s of [...((ast.instance?.content?.body ?? []) as Knoten[]), ...((ast.module?.content?.body ?? []) as Knoten[])]) {
		if (s.type !== 'ImportDeclaration') continue;
		out.push({ quelle: s.source.value as string, namen: (s.specifiers as Knoten[]).map((sp) => sp.local?.name as string) });
	}
	return out;
}

/** Datei einer Organismus-/Reiter-Komponente nach Name (nur Reiter-Baum). */
function dateiZuKomponente(name: string): string | null {
	for (const d of [REITER, ...organismDateien()]) if (basename(d, '.svelte') === name) return d;
	return null;
}

/** Enthaelt der Teilbaum `wurzel` (in `datei`) die Komponente `ziel` — direkt oder in einem Organismus des Baums? */
function enthaelt(wurzel: unknown, ziel: string[], tiefe = 0): boolean {
	if (tiefe > 6) return false;
	for (const k of alle(wurzel, (n) => n.type === 'Component')) {
		if (ziel.includes(k.name)) return true;
		const d = dateiZuKomponente(k.name);
		if (d && enthaelt(svelteAst(d).ast.fragment, ziel, tiefe + 1)) return true;
	}
	return false;
}

/** Traegt der Teilbaum (inkl. Organismen) ein Element mit data-abschnitt=`wert`? */
function enthaeltMarker(wurzel: unknown, quelle: string, wert: string, tiefe = 0): boolean {
	if (tiefe > 6) return false;
	if (alle(wurzel, (n) => istElement(n) && statisch(n, quelle, 'data-abschnitt') === wert).length > 0) return true;
	for (const k of alle(wurzel, (n) => n.type === 'Component')) {
		const d = dateiZuKomponente(k.name);
		if (!d) continue;
		const { ast, quelle: q } = svelteAst(d);
		if (enthaeltMarker(ast.fragment, q, wert, tiefe + 1)) return true;
	}
	return false;
}

// ── Pendant-Sperre (#1170, ADR-0097) ────────────────────────────────────────

describe('#1170/ADR-0097: ein Code fuer Trip und Orte (organisms/zustellung-tab/, context-Prop)', () => {
	test('s3b2795_reiter_und_organismen_existieren_mit_context', () => {
		baum();
		assert.ok(propNamen(svelteAst(REITER).ast).includes('context'), 'ZustellungTab ohne Prop context');
	});

	test('s3b2795_keine_compare_komponente_mit_trip_pendant', () => {
		const namen = baum().map((d) => basename(d, '.svelte'));
		const kontextGebunden = namen.filter((n) => /^(Compare|Vergleich|Orte|Trip|Route)/.test(n) || /(Compare|Vergleich|Trip|Route)$/.test(n));
		assert.deepEqual(kontextGebunden, [], `Kontext-eigene Organismen (Pendant-Verstoss): ${kontextGebunden.join(', ')}`);
	});

	test('s3b2795_hubs_mounten_denselben_reiter', () => {
		for (const [datei, ctx] of [[TRIP_HUB, 'route'], [VERGLEICH_HUB, 'vergleich']] as const) {
			const { ast, quelle } = svelteAst(datei);
			const e = einbettungenMitWeichen(ast, quelle, ['ZustellungTab']);
			assert.equal(e.length, 1, `${basename(datei)}: genau ein ZustellungTab erwartet`);
			assert.ok(reiterVon(e[0]).includes('zustellung'), `${basename(datei)}: ZustellungTab haengt nicht am Reiter zustellung`);
			assert.equal(attribut(e[0].knoten, quelle, 'context')?.literal, ctx);
		}
	});
});

// ── Marker (AC-1, AC-37) ────────────────────────────────────────────────────

describe('AC-1/AC-37: Abschnitts-Marker data-abschnitt fuer den Elementlisten-Abgleich', () => {
	test('s3b2795_alle_abschnitte_markiert', () => {
		const gefunden = new Set<string>();
		for (const d of baum()) {
			const { ast, quelle } = svelteAst(d);
			for (const n of alle(ast.fragment, istElement)) {
				const w = statisch(n, quelle, 'data-abschnitt');
				if (w) gefunden.add(w);
			}
		}
		const fehlt = MARKER.filter((m) => !gefunden.has(m));
		assert.deepEqual(fehlt, [], `fehlende Marker: ${fehlt.join(', ')} (gefunden: ${[...gefunden].join(', ')})`);
	});

	test('s3b2795_reiter_rendert_die_abschnitte_in_mockup_reihenfolge', () => {
		baum();
		const { ast, quelle } = svelteAst(REITER);
		// Reihenfolge der obersten Bausteine im Reiter: jeder Abschnitt wird ueber seinen Marker einem Knoten zugeordnet.
		// Knoten in Dokumentreihenfolge (Tiefensuche); ein Knoten „ist“ Abschnitt m, wenn er den Marker selbst traegt
		// oder eine Organismus-Komponente ist, in deren Datei der Marker steht.
		const kinder = alle(ast.fragment, (n) => istElement(n));
		const position = (m: string) =>
			kinder.findIndex((k) => {
				if (statisch(k, quelle, 'data-abschnitt') === m) return true;
				const d = k.type === 'Component' ? dateiZuKomponente(k.name) : null;
				if (!d || d === REITER) return false;
				const s = svelteAst(d);
				return enthaeltMarker(s.ast.fragment, s.quelle, m);
			});
		const pos = MARKER.map((m) => [m, position(m)] as const);
		for (const [m, p] of pos) assert.ok(p >= 0, `Abschnitt ${m} im Reiter nicht erreichbar`);
		const reihenfolge = [...pos].sort((a, b) => a[1] - b[1]).map(([m]) => m);
		// Knoten, die mehrere Abschnitte umschliessen, haben denselben Index — dann zaehlt die Dateireihenfolge der Organismen nicht;
		// verlangt wird nur, dass kein spaeterer Abschnitt VOR einem frueheren beginnt.
		for (let i = 1; i < pos.length; i++) {
			assert.ok(pos[i][1] >= pos[i - 1][1], `Reihenfolge verletzt: ${pos[i][0]} vor ${pos[i - 1][0]} (${reihenfolge.join(' → ')})`);
		}
	});
});

// ── Entfernte Doppelungen (AC-27, AC-31) ────────────────────────────────────

describe('AC-27/AC-31: keine Kanaele je Wettergroesse, keine amtlichen Warnungen, kein „Alarm ab“, keine zweite Kanalauswahl', () => {
	test('s3b2795_reiter_bettet_keine_alt_bausteine_ein', () => {
		for (const d of baum()) {
			const { ast } = svelteAst(d);
			const da = alle(ast.fragment, (n) => n.type === 'Component' && VERBOTEN.includes(n.name)).map((n) => n.name);
			assert.deepEqual(da, [], `${basename(d)} bettet Alt-Bausteine ein: ${da.join(', ')}`);
			const imp = importe(d).flatMap((i) => i.namen).filter((n) => VERBOTEN.includes(n));
			assert.deepEqual(imp, [], `${basename(d)} importiert Alt-Bausteine: ${imp.join(', ')}`);
		}
	});

	test('s3b2795_vergleich_hub_reicht_keinen_alarme_tab_hinein', () => {
		assert.ok(!propNamen(svelteAst(REITER).ast).includes('alarmeBereich'), 'ZustellungTab nimmt weiter ein AlarmeTab-Snippet (alarmeBereich) an');
		const { ast, quelle } = svelteAst(VERGLEICH_HUB);
		const e = einbettungenMitWeichen(ast, quelle, ['ZustellungTab']);
		assert.equal(attribut(e[0].knoten, quelle, 'alarmeBereich'), null, 'CompareTabs reicht weiter alarmeBereich (AlarmeTab) an den Reiter');
	});
});

// ── Uebergangsblock (AC-30, §5) ─────────────────────────────────────────────

describe('AC-30: Uebergangsblock am Ende — Inhalt je Kanal (ohne alten Versand-Abschnitt) und Beispiel-Alarm', () => {
	function uebergang(): { knoten: Knoten; quelle: string } {
		for (const d of baum()) {
			const { ast, quelle } = svelteAst(d);
			const k = alle(ast.fragment, (n) => istElement(n) && statisch(n, quelle, 'data-abschnitt') === 'uebergang');
			if (k.length > 0) {
				assert.equal(k.length, 1, `${basename(d)}: mehr als ein Uebergangsblock`);
				return { knoten: k[0], quelle };
			}
		}
		assert.fail('kein Element mit data-abschnitt="uebergang" im Reiter-Baum');
	}

	test('s3b2795_uebergang_enthaelt_inhalt_je_kanal_und_beispiel_alarm', () => {
		const { knoten } = uebergang();
		assert.ok(enthaelt(knoten, ['WetterMetrikenVersandPanel', 'WeatherMetricsTab']), 'Uebergangsblock ohne WetterMetrikenVersandPanel/WeatherMetricsTab (Telegram-Kurzstil, Layout je Kanal, Ausblick, Nachtblock, Report-Config, SMS-Schwellen)');
		assert.ok(enthaelt(knoten, ['AlertPreviewCard']), 'Uebergangsblock ohne Beispiel-Alarm (AlertPreviewCard)');
	});

	test('s3b2795_uebergang_bereich_zustellung', () => {
		const { knoten, quelle } = uebergang();
		for (const k of alle(knoten, (n) => n.type === 'Component' && ['WetterMetrikenVersandPanel', 'WeatherMetricsTab'].includes(n.name))) {
			assert.equal(attribut(k, quelle, 'bereich')?.literal, 'zustellung', `${k.name} im Uebergangsblock ohne bereich="zustellung"`);
		}
	});

	test('s3b2795_kein_alter_versand_abschnitt_im_reiter', () => {
		// Wird das Panel weiter genutzt, darf sein <section id="versand"> (VersandTab/BriefingScheduleTab) nicht
		// unbedingt rendern — sonst stuenden Uhrzeit, Kanaele und Laufzeit doppelt im Reiter.
		baum();
		const panelImBaum = [REITER, ...organismDateien()].some((d) => alle(svelteAst(d).ast.fragment, (n) => n.type === 'Component' && n.name === 'WetterMetrikenVersandPanel').length > 0);
		if (!panelImBaum) return;
		const { ast, quelle } = svelteAst(PANEL);
		const sektion = alle(ast.fragment, (n) => n.type === 'RegularElement' && n.name === 'section' && statisch(n, quelle, 'id') === 'versand');
		for (const s of sektion) {
			const unterWeiche = alle(ast.fragment, (n) => n.type === 'IfBlock').some((b) => alle(b.consequent, (x) => x === s).length > 0 || (b.alternate && alle(b.alternate, (x) => x === s).length > 0));
			assert.ok(unterWeiche, 'WetterMetrikenVersandPanel rendert <section id="versand"> unbedingt — im Reiter Zustellung muss er abschaltbar sein');
		}
	});
});

// ── EIN Speicherer (AC-33) ──────────────────────────────────────────────────

describe('AC-33: genau ein Speicherer im Reiter (zustellungSpeicherung.ts), Komponenten speichern nicht selbst', () => {
	test('s3b2795_speicherer_modul_existiert', () => {
		assert.ok(existsSync(join(SHARED_ZT, 'zustellungSpeicherung.ts')), 'TDD RED: shared/zustellung-tab/zustellungSpeicherung.ts fehlt');
		assert.ok(existsSync(join(SHARED_ZT, 'zustellungModell.ts')), 'TDD RED: shared/zustellung-tab/zustellungModell.ts fehlt');
	});

	test('s3b2795_komponenten_ohne_eigenen_schedule_und_ohne_alt_speicherwege', () => {
		let nutztSpeicherer = false;
		for (const d of baum()) {
			const { ast, quelle } = svelteAst(d);
			const sched = [...aufrufe(ast.instance?.content), ...aufrufe(ast.fragment)].filter((a) => aufgerufener(a, quelle).endsWith('.schedule'));
			assert.equal(sched.length, 0, `${basename(d)} ruft selbst schedule() auf — Speichern gehoert in zustellungSpeicherung.ts`);
			const imp = importe(d);
			const alt = imp.filter((i) => VERBOTENE_SPEICHER_MODULE.some((m) => i.quelle.includes(m)));
			assert.deepEqual(alt.map((i) => i.quelle), [], `${basename(d)} nutzt einen Alt-Speicherweg`);
			if (imp.some((i) => i.quelle.includes('zustellungSpeicherung'))) nutztSpeicherer = true;
		}
		assert.ok(nutztSpeicherer, 'kein Baustein des Reiters bindet zustellungSpeicherung.ts ein');
	});
});

// ── Profil genau einmal (AC-36) ─────────────────────────────────────────────

describe('AC-36: GET /api/auth/profile genau einmal je Reiter-Aufruf', () => {
	function profilAufrufe(datei: string): number {
		const { quelle, liste } = datei.endsWith('.svelte')
			? (() => {
					const { ast, quelle } = svelteAst(datei);
					return { quelle, liste: [...aufrufe(ast.instance?.content), ...aufrufe(ast.fragment)] };
				})()
			: (() => {
					const { programm, quelle } = tsAst(datei);
					return { quelle, liste: aufrufe(programm) };
				})();
		return liste.filter((a) => {
			const arg = (a.arguments ?? [])[0] as Knoten | undefined;
			if (!arg) return false;
			const text = arg.type === 'Literal' ? String(arg.value) : arg.type === 'TemplateLiteral' ? quelle.slice(arg.start, arg.end) : '';
			return /\/api\/auth\/profile\b/.test(text);
		}).length;
	}

	test('s3b2795_profil_eine_aufrufstelle_im_reiter_baum', () => {
		const dateien = [...baum(), ...['zustellungModell.ts', 'zustellungSpeicherung.ts'].map((f) => join(SHARED_ZT, f)).filter(existsSync)];
		const je = dateien.map((d) => [basename(d), profilAufrufe(d)] as const).filter(([, n]) => n > 0);
		const summe = je.reduce((s, [, n]) => s + n, 0);
		assert.equal(summe, 1, `erwartet genau eine Ladestelle fuer /api/auth/profile, gefunden: ${JSON.stringify(je)}`);
	});
});

// ── Anker #versand (AC-39/AC-40) ────────────────────────────────────────────

describe('AC-39/AC-40: Anker #versand liegt an der Briefing-Zeiten-Karte', () => {
	test('s3b2795_genau_ein_anker_versand_an_briefing_zeiten', () => {
		const treffer: Array<{ datei: string; knoten: Knoten; quelle: string }> = [];
		for (const d of baum()) {
			const { ast, quelle } = svelteAst(d);
			for (const n of alle(ast.fragment, (x) => istElement(x) && statisch(x, quelle, 'id') === 'versand')) treffer.push({ datei: d, knoten: n, quelle });
		}
		assert.equal(treffer.length, 1, `genau ein Element mit id="versand" im Reiter-Baum erwartet, gefunden ${treffer.length}`);
		const { knoten, quelle } = treffer[0];
		const ok = statisch(knoten, quelle, 'data-abschnitt') === 'briefing-zeiten' || enthaeltMarker(knoten, quelle, 'briefing-zeiten');
		assert.ok(ok, 'id="versand" sitzt nicht an der Briefing-Zeiten-Karte (data-abschnitt="briefing-zeiten")');
	});
});
