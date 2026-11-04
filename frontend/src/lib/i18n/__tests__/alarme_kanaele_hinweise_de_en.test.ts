// TDD RED — #1895 S3b2 AC-75: die zwei neuen Hinweistexte stehen in DE und EN im Katalog.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { de } from '../messages/de/index.ts';
import { en } from '../messages/en/index.ts';

const SCHLUESSEL = ['alarme.kanaele.kein_empfaenger', 'alarme.kanaele.schwelle_hinweis'] as const;

test('AC-75: kein_empfaenger und schwelle_hinweis in DE und EN, EN nicht nur kopiert', () => {
	const fehlend: string[] = [];
	for (const k of SCHLUESSEL) {
		for (const [s, kat] of [['de', de], ['en', en]] as const) {
			const t = (kat as Record<string, unknown>)[k];
			if (typeof t !== 'string' || t.trim() === '') fehlend.push(`${s}:${k}`);
		}
	}
	assert.deepStrictEqual(fehlend, [], `fehlende Katalogtexte: ${fehlend.join(', ')}`);
	const d = de as Record<string, string>, e = en as Record<string, string>;
	for (const k of SCHLUESSEL) assert.notStrictEqual(d[k], e[k], `EN nur kopiert: ${k}`);
});

test('AC-75: Platzhalter vorhanden (Kanalname, Schwellenname)', () => {
	const d = de as Record<string, string>;
	assert.match(d['alarme.kanaele.kein_empfaenger'] ?? '', /\{kanal\}/);
	assert.match(d['alarme.kanaele.schwelle_hinweis'] ?? '', /\{kanal\}/);
	assert.match(d['alarme.kanaele.schwelle_hinweis'] ?? '', /\{schwelle\}/);
});
