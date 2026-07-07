import { defineConfig } from '@playwright/test';
// Lokale Unit-Config für issue_1093 — reine Funktion selectPreviewRows, KEIN webServer,
// KEIN Staging. Läuft rein in-process (Node), damit qa_gate ein erkennbares
// "N passed"-Testoutput bekommt (das node --test TAP-Format erkennt qa_gate nicht).
export default defineConfig({
	testDir: '.',
	timeout: 15_000,
	retries: 0,
	testMatch: /issue-1093-unit\.spec\.ts/
});
