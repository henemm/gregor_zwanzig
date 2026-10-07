// Issue #2520 — typisierter Textkatalog (Deutsch, flache inlang-kompatible Schluessel).
// Unbekannter Schluessel = TypeScript-Fehler (svelte-check). Keine Abhaengigkeit.
import de from './messages/de.json' with { type: 'json' };

export type MessageKey = keyof typeof de;

export function t(key: MessageKey): string {
	return de[key];
}
