// Issue #2913 (Epic #2791), Fix-Loop 1 (F003) — Starter für den Staging-Abgleich der Elementliste.
// Playwright reicht eigene Flags nicht an Tests durch; dieser Starter nimmt sie entgegen, übersetzt sie
// in die Umgebung der Spec und reicht den Exit-Code von Playwright durch.
//
//   cd frontend && npm run elementliste:abgleich -- [--strict] [--abnahme] [--scope <reiter[/zustand]>] [--sprache en]
// --abnahme (feat_2913_abgleich_ganzseite): Exit ≠ 0, solange eine Abweichung keinen Besitzer hat.
//
// Login: GZ_AUTH_USER/GZ_AUTH_PASS aus der Umgebung; fehlen sie, werden NUR diese beiden Werte aus
// ELEMENTLISTE_ENV_DATEI (Vorgabe: Staging-Checkout /home/hem/gregor_zwanzig_staging/.env) gelesen.
// Es entsteht keine Auth-Datei; die Spec meldet sich im Speicher an und wieder ab.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { flagsAlsUmgebung, loginAusEnvText } from '../frontend/e2e/elementliste_abgleich_logik.ts';

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..', 'frontend');
export const STANDARD_ENV_DATEI = '/home/hem/gregor_zwanzig_staging/.env';

/** Umgebung für den Playwright-Lauf: Flags → ELEMENTLISTE_*, Login ggf. aus dem .env-Text. */
export function starterUmgebung(
	argv: string[],
	env: Record<string, string | undefined>,
	envDateiText: string | null
): Record<string, string | undefined> {
	const out: Record<string, string | undefined> = { ...env, ...flagsAlsUmgebung(argv) };
	if (!(out.GZ_AUTH_USER && out.GZ_AUTH_PASS) && envDateiText) Object.assign(out, loginAusEnvText(envDateiText));
	return out;
}

export const PLAYWRIGHT_ARGS = ['playwright', 'test', '--config', 'playwright.elementliste.staging.config.ts'];

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
	const datei = process.env.ELEMENTLISTE_ENV_DATEI ?? STANDARD_ENV_DATEI;
	let text: string | null = null;
	if (existsSync(datei)) {
		try {
			text = readFileSync(datei, 'utf8');
		} catch {
			text = null;
		}
	}
	let env: Record<string, string | undefined>;
	try {
		env = starterUmgebung(process.argv.slice(2), process.env, text);
	} catch (e) {
		console.error((e as Error).message);
		process.exit(2);
	}
	const r = spawnSync('npx', PLAYWRIGHT_ARGS, { cwd: FRONTEND, stdio: 'inherit', env: env as NodeJS.ProcessEnv });
	process.exit(r.status ?? 1);
}
