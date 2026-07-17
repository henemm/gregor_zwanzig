// Issue #1284 — Geteilte Konstante (Single Source of Truth) für das
// `/api`-Proxy-Ziel von Playwright-E2E-Läufen.
//
// Spec: docs/specs/modules/fix_1284_admin_prod_testdata.md, AC-2/AC-4.
//
// `vite.config.ts` UND `prodUrlGuard.ts` importieren dieselbe Konstante --
// damit prüft der Guard nicht gegen eine unabhängige Kopie des Werts.
// Default zeigt auf den dauerhaft laufenden Staging-Go-Server (Port 8091),
// NICHT auf Prod (Port 8090). Override über GZ_E2E_API_PROXY_TARGET.

export const API_PROXY_TARGET =
	process.env.GZ_E2E_API_PROXY_TARGET ?? 'http://localhost:8091';

// Prod-Go-Adresse, gegen die der Guard prüft (verboten als Proxy-Ziel).
export const PROD_API_PROXY_TARGET = 'http://localhost:8090';
