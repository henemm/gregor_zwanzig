import { test, expect } from '@playwright/test';
import { selectPreviewRows } from '../src/lib/components/compare/layoutPreviewRows.ts';

// Issue #1093 — reiner Verhaltensnachweis der Vorschau-Zeilenauswahl (kein Mock, kein
// Staging). Vor dem Fix filterte LayoutPreview die statischen DUMMY_LOCATIONS nach echten
// pickedIds → nie ein Match → rows=[] → rows[0].feels crasht. selectPreviewRows koppelt
// die Zeilenzahl an die Anzahl gewählter Orte und wird bei pickedIds.length>0 nie leer.

const DUMMIES = [{ id: 'loc-01' }, { id: 'loc-07' }, { id: 'loc-08' }];

test('Bug #1093: echte UUID-pickedIds ergeben gefüllte, nicht-leere rows', () => {
	const picked = ['real-uuid-aaaa', 'real-uuid-bbbb']; // matchen KEINE Dummy-ID
	const rows = selectPreviewRows(picked, DUMMIES);
	expect(rows.length).toBe(2);
	expect(rows[0]).toBeDefined(); // vor Fix: undefined → Crash
});

test('Zeilenzahl = min(pickedIds.length, dummies.length), nie leer', () => {
	expect(selectPreviewRows(['a'], DUMMIES).length).toBe(1);
	expect(selectPreviewRows(['a', 'b', 'c'], DUMMIES).length).toBe(3);
	expect(selectPreviewRows(new Array(100).fill('x'), DUMMIES).length).toBe(3);
	for (const n of [1, 2, 3, 100]) {
		const rows = selectPreviewRows(new Array(n).fill('x'), DUMMIES);
		expect(rows[0]).toBeDefined();
	}
});

test('Kein Regress: leere Auswahl zeigt alle Dummys', () => {
	expect(selectPreviewRows([], DUMMIES).length).toBe(3);
});
