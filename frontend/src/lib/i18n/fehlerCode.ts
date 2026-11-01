// Issue #2660 (i18n F11) — Go-Fehlercodes (`{"code","message"}`, api_contract.md
// „Fehlerobjekt") in der Nutzersprache. Bekannter Code: Katalogtext
// `fehler.code.<code>` in der aktuellen Sprache; sonst `null` (dann zeigt der
// Aufrufer wie bisher den Server-Text).
import { de } from './messages/de/index.ts';
import { tr, type MessageKey } from './index.ts';

export function fehlerTextFuerCode(code: unknown): string | null {
	if (typeof code !== 'string' || !/^[a-z0-9_]+$/.test(code)) return null;
	// i18n-dynamic: fehler.code.
	const key = `fehler.code.${code}`;
	return key in de ? tr(key as MessageKey) : null;
}
