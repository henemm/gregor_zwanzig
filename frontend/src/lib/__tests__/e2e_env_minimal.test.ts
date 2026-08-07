// Issue #1289 — start-preview.sh lädt heute blanket die komplette Haupt-.env
// in den E2E-Preview-Server-Prozess (41 Schlüssel, u.a. GZ_SMTP_PASS,
// GZ_TELEGRAM_BOT_TOKEN). Spec: docs/specs/modules/fix_1289_e2e_env_minimal.md,
// AC-1 + AC-2.
//
// Dieser Test prüft ECHTES Prozessverhalten (kein Dateiinhalt-Check): er
// erzeugt eine Fixture-.env mit erlaubten UND verbotenen Schlüsseln, ruft
// frontend/e2e/e2e-env.sh als eigenständigen Bash-Prozess auf und liest die
// tatsächliche `env`-Ausgabe des Kindprozesses aus.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const E2E_ENV_SCRIPT = join(here, '..', '..', '..', 'e2e', 'e2e-env.sh'); // frontend/e2e/e2e-env.sh

function runWithFixtureEnv(fixtureEnvContent: string): Record<string, string> {
	const dir = mkdtempSync(join(tmpdir(), 'gz-e2e-env-test-'));
	const fixtureEnvFile = join(dir, '.env');
	writeFileSync(fixtureEnvFile, fixtureEnvContent, 'utf-8');

	try {
		const result = spawnSync('bash', ['-c', 'source "$0" && env', E2E_ENV_SCRIPT], {
			env: {
				PATH: process.env.PATH ?? '/usr/bin:/bin',
				GZ_REPO_ENV_FILE: fixtureEnvFile
			},
			encoding: 'utf-8'
		});

		assert.equal(
			result.status,
			0,
			`e2e-env.sh sollte fehlerfrei durchlaufen (stderr: ${result.stderr})`
		);

		const env: Record<string, string> = {};
		for (const line of result.stdout.split('\n')) {
			const idx = line.indexOf('=');
			if (idx === -1) continue;
			env[line.slice(0, idx)] = line.slice(idx + 1);
		}
		return env;
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
}

const FIXTURE_ENV = [
	'GZ_SESSION_SECRET=fixture-session-secret-value',
	'GZ_GOOGLE_CLIENT_ID=fixture-google-client-id',
	'GZ_SMTP_PASS=darf-nicht-durchsickern',
	'GZ_TELEGRAM_BOT_TOKEN=darf-auch-nicht-durchsickern'
].join('\n');

test('#1289 AC-1: benötigte Variablen (GZ_SESSION_SECRET, GZ_GOOGLE_CLIENT_ID) kommen im Kindprozess an', () => {
	const env = runWithFixtureEnv(FIXTURE_ENV);

	assert.equal(env.GZ_SESSION_SECRET, 'fixture-session-secret-value');
	assert.equal(env.GZ_GOOGLE_CLIENT_ID, 'fixture-google-client-id');
});

test('#1289 AC-2: nicht benötigte Secrets (GZ_SMTP_PASS, GZ_TELEGRAM_BOT_TOKEN) kommen NICHT im Kindprozess an', () => {
	const env = runWithFixtureEnv(FIXTURE_ENV);

	assert.equal(env.GZ_SMTP_PASS, undefined, 'GZ_SMTP_PASS darf nicht in die Preview-Server-Umgebung durchsickern');
	assert.equal(
		env.GZ_TELEGRAM_BOT_TOKEN,
		undefined,
		'GZ_TELEGRAM_BOT_TOKEN darf nicht in die Preview-Server-Umgebung durchsickern'
	);
});

// Zusatz zur freigegebenen Spec (Befund bei der Implementierung, gemessen an
// der echten Haupt-.env): dort stehen die Werte in doppelten Anfuehrungs-
// zeichen. Der abgeloeste `source`-Pfad streift die ab, `grep | cut` nicht.
// Ohne Abstreifen kaeme ein um zwei Zeichen laengeres GZ_SESSION_SECRET an
// (66 statt 64) -- es passt dann nicht zum Staging-Go-Server und alle
// authentifizierten E2E-Tests brechen STILL. Die beiden Fixtures oben nutzen
// unquotierte Werte und koennen diesen Fall nicht sehen.
const FIXTURE_ENV_QUOTED = [
	'GZ_SESSION_SECRET="fixture-session-secret-value"',
	"GZ_GOOGLE_CLIENT_ID='fixture-google-client-id'",
	'GZ_SMTP_PASS="darf-nicht-durchsickern"'
].join('\n');

test('#1289 AC-1 (Realitaets-Fixture): quotierte .env-Werte kommen OHNE Anfuehrungszeichen an', () => {
	const env = runWithFixtureEnv(FIXTURE_ENV_QUOTED);

	assert.equal(env.GZ_SESSION_SECRET, 'fixture-session-secret-value');
	assert.equal(env.GZ_GOOGLE_CLIENT_ID, 'fixture-google-client-id');
	assert.equal(env.GZ_SMTP_PASS, undefined);
});
