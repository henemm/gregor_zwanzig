// Issue #2647 (i18n S2) — aktuelle Oberflaechensprache. Gesetzt in
// +layout.svelte aus `data.lang` (synchron, wirkt beim Serverrendern).
// Server-Actions/-Loader lesen NIE diesen Store, sondern `locals.lang` (trFor).
import { writable, type Writable } from 'svelte/store';

export type Lang = 'de' | 'en';

export const locale: Writable<Lang> = writable<Lang>('de');
