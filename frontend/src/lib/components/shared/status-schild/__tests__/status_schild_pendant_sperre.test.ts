// TDD RED — Issue #2837 Nachbesserung S1b (Epic #2345), AC-9: genau EIN Status-Schild unter
// `shared/status-schild/`, die Pendants `trip-detail/TripStatusBadge.svelte` und
// `compare/CompareStatusPill.svelte` existieren nicht mehr, und kein produktiver Code
// importiert oder re-exportiert sie (0 Importeure; Pendant-Sperre ADR-0097).
// Spec: docs/specs/modules/rework_2837_s1b_status_profil.md
//
// Import-AUFLÖSUNG statt String-Grep: Import-/Export-Deklarationen werden am AST gelesen
// (.svelte: svelte/compiler über aktionsmodellAst.importe; .ts: TypeScript-Parser), ihre
// Quellen relativ bzw. über `$lib` zu absoluten Pfaden aufgelöst und mit den Alt-Dateien
// verglichen. Ein Kommentar, der den alten Namen nennt, zählt nicht.
//
// RED HEUTE: StatusSchild fehlt, beide Alt-Bausteine existieren, TripHeader.svelte,
// routes/compare/[id]/+page.svelte, trip-detail/index.ts und molecules/index.ts binden sie ein.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/status-schild/__tests__/status_schild_pendant_sperre.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { ladeSvelte, importe } from '../../__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, '../../../../..');
const LIB = path.join(SRC, 'lib');
const KOMP = path.join(LIB, 'components');

const NEU = path.join(KOMP, 'shared/status-schild/StatusSchild.svelte');
const ALT = [path.join(KOMP, 'trip-detail/TripStatusBadge.svelte'), path.join(KOMP, 'compare/CompareStatusPill.svelte')];

/** Produktive Quelldateien (keine Tests, keine Prüfstände). */
function quellen(dir: string): string[] {
	const out: string[] = [];
	for (const e of readdirSync(dir)) {
		const p = path.join(dir, e);
		if (statSync(p).isDirectory()) {
			if (e === '__tests__' || e === 'node_modules') continue;
			out.push(...quellen(p));
		} else if (/\.(svelte|ts)$/.test(e) && !/\.(test|spec)\.ts$/.test(e) && !/\.d\.ts$/.test(e)) {
			out.push(p);
		}
	}
	return out;
}

function tsQuellen(datei: string): string[] {
	const sf = ts.createSourceFile(datei, readFileSync(datei, 'utf-8'), ts.ScriptTarget.Latest, false);
	const q: string[] = [];
	const besuche = (n: ts.Node) => {
		if ((ts.isImportDeclaration(n) || ts.isExportDeclaration(n)) && n.moduleSpecifier && ts.isStringLiteral(n.moduleSpecifier)) q.push(n.moduleSpecifier.text);
		if (ts.isCallExpression(n) && n.expression.kind === ts.SyntaxKind.ImportKeyword && n.arguments[0] && ts.isStringLiteral(n.arguments[0])) q.push(n.arguments[0].text);
		ts.forEachChild(n, besuche);
	};
	besuche(sf);
	return q;
}

function aufloesen(von: string, quelle: string): string | null {
	const basis = quelle.startsWith('$lib/') ? path.join(LIB, quelle.slice(5)) : quelle.startsWith('.') ? path.resolve(path.dirname(von), quelle) : null;
	return basis;
}

function importeure(): Array<{ datei: string; quelle: string }> {
	const treffer: Array<{ datei: string; quelle: string }> = [];
	for (const datei of quellen(SRC)) {
		const q = datei.endsWith('.svelte') ? importe(ladeSvelte(datei)).map((i) => i.quelle) : tsQuellen(datei);
		for (const quelle of q) {
			const ziel = aufloesen(datei, quelle);
			if (ziel && ALT.some((a) => ziel === a || ziel === a.replace(/\.svelte$/, ''))) treffer.push({ datei: path.relative(SRC, datei), quelle });
		}
	}
	return treffer;
}

describe('#2837 S1b AC-9 — genau ein Status-Schild (Pendant-Sperre)', () => {
	test('Messaufbau: der Import-Scan findet Svelte- und TS-Importe (HubKopf wird von TripHeader importiert)', () => {
		const hubKopf = path.join(KOMP, 'shared/hub-kopf/HubKopf.svelte');
		const tripHeader = path.join(KOMP, 'trip-detail/TripHeader.svelte');
		const q = importe(ladeSvelte(tripHeader)).map((i) => aufloesen(tripHeader, i.quelle));
		assert.ok(q.includes(hubKopf), 'Import-Auflösung funktioniert nicht ($lib/…)');
		assert.ok(tsQuellen(path.join(KOMP, 'molecules/index.ts')).length > 0, 'TS-Scan liest keine Re-Exporte');
	});

	test('StatusSchild liegt unter shared/status-schild/', () => {
		assert.ok(existsSync(NEU), `${path.relative(SRC, NEU)} fehlt`);
	});

	for (const alt of ALT) {
		test(`${path.relative(SRC, alt)} existiert nicht mehr`, () => {
			assert.ok(!existsSync(alt), `${path.relative(SRC, alt)} existiert noch (zweiter Status-Baustein)`);
		});
	}

	test('kein produktiver Code importiert oder re-exportiert die Alt-Bausteine (0 Importeure)', () => {
		assert.deepEqual(importeure(), []);
	});

	test('beide Hub-Seiten (über TripHeader bzw. die Vergleichsseite) binden StatusSchild ein', () => {
		for (const datei of [path.join(KOMP, 'trip-detail/TripHeader.svelte'), path.join(SRC, 'routes/compare/[id]/+page.svelte')]) {
			const ziele = importe(ladeSvelte(datei)).map((i) => aufloesen(datei, i.quelle));
			assert.ok(ziele.includes(NEU), `${path.relative(SRC, datei)} importiert StatusSchild nicht`);
		}
	});
});
