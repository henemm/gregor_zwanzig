// Issue #3281 (MCP-Konnektor „Gregor Wetter“, ADR-0128): die drei Pfade der
// OAuth-Metadaten, die SvelteKit ohne Anmeldung an Go durchreicht. EINE Liste
// fuer die Route `/.well-known/[...pfad]` und die oeffentlichen Pfade in
// `hooks.server.ts`.
export const OAUTH_METADATEN_PFADE: ReadonlySet<string> = new Set([
	'/.well-known/oauth-protected-resource',
	'/.well-known/oauth-protected-resource/api/mcp',
	'/.well-known/oauth-authorization-server'
]);
