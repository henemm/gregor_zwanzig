// TDD RED — #2049: Faehigkeitsliste des Ausblick-Roh/Einfach-Umschalters muss
// an EINER Quelle festgemacht sein (AC-3/AC-4). `indicatorCapable()`
// (trip-detail/metricsEditor.ts) kennt die AUSBLICK-Semantik nicht und ist der
// falsche Waechter (Spec "Faehigkeitsliste statt indicatorCapable()") -- diese
// Datei bewacht die NEUE, ausblick-eigene Liste.
//
// Analog zu compareMetricKeysParity.test.ts (#1351 F003b): eine hartkodierte
// Erwartungsliste im Testfile ist KEIN echter Drift-Waechter, sie schlaegt nur
// an, wenn jemand die Kopie selbst nachzieht. Dieser Test liest daher die
// LIVE-Backend-Quelle (`app.metric_catalog.OUTLOOK_FRIENDLY_CAPABLE`) per
// `uv run python3` und vergleicht sie mit der Frontend-Kopie
// (`outlookFriendlyCapability.ts`, existiert noch nicht -- RED-Grund dieser
// Datei) in BEIDE Richtungen: eine Kennung, die nur auf einer Seite als
// "faehig" gilt, zeigt einen sichtbaren aber wirkungslosen Umschalter (oder
// umgekehrt einen wirksamen, aber unsichtbaren) -- genau der Bug-Mechanismus
// aus der Spec ("Bedienflaeche und Wirkung koennen nicht mehr auseinander-
// laufen").
//
// Kein Mock, kein Dateiinhalt-Grep: der Python-Prozess FUEHRT den echten
// Katalog-Code aus.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/outlookFriendlyCapabilityDrift.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { OUTLOOK_FRIENDLY_CAPABLE, outlookFriendlyCapable } from '../outlookFriendlyCapability.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> weather-metrics-tab -> shared -> components -> lib -> src -> frontend -> repoRoot
const REPO_ROOT = path.resolve(__dirname, ...Array(7).fill('..'));

const PY_SCRIPT =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from app.metric_catalog import OUTLOOK_FRIENDLY_CAPABLE\n' +
	'print(json.dumps(sorted(OUTLOOK_FRIENDLY_CAPABLE)))\n';

/** Liest die LIVE-Backend-Faehigkeitsliste via `uv run python3` (echte Quelle, kein Fixture). */
function fetchBackendCapableIds(): string[] {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_SCRIPT], {
		cwd: REPO_ROOT,
		encoding: 'utf-8'
	});
	return JSON.parse(stdout.trim());
}

describe('OUTLOOK_FRIENDLY_CAPABLE — Paritaet mit dem LIVE-Backend-Katalog (#2049 AC-3/AC-4)', () => {
	test('enthaelt exakt dieselben Kennungen wie app.metric_catalog.OUTLOOK_FRIENDLY_CAPABLE', () => {
		const backendIds = fetchBackendCapableIds();
		const actual = [...OUTLOOK_FRIENDLY_CAPABLE].sort();
		const expected = [...backendIds].sort();
		assert.deepEqual(
			actual,
			expected,
			'OUTLOOK_FRIENDLY_CAPABLE (Frontend) weicht vom LIVE-Backend-Katalog ab -- ' +
				`fehlend: ${expected.filter((k) => !actual.includes(k))}, zusaetzlich: ` +
				`${actual.filter((k) => !expected.includes(k))}. Eine abweichende Kennung zeigt ` +
				'einen sichtbaren, aber wirkungslosen Umschalter (oder umgekehrt).'
		);
	});

	test('outlookFriendlyCapable() stimmt Kennung fuer Kennung mit der Backend-Menge ueberein', () => {
		const backendIds = new Set(fetchBackendCapableIds());
		// Stichprobe je Seite (faehig UND nicht-faehig) -- keine zweite volle
		// Liste im Test, sonst prueft der Test seine eigene Kopie statt des
		// Prueflings.
		for (const id of ['wind_direction', 'cloud_total', 'gust', 'sunshine']) {
			assert.equal(
				outlookFriendlyCapable(id),
				backendIds.has(id),
				`outlookFriendlyCapable(${id}) weicht vom Backend ab`
			);
		}
		for (const id of ['temperature', 'thunder', 'visibility']) {
			assert.equal(
				outlookFriendlyCapable(id),
				backendIds.has(id),
				`outlookFriendlyCapable(${id}) weicht vom Backend ab`
			);
		}
	});
});
