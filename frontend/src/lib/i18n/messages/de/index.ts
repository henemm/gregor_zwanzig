// Issue #2647 (i18n S2) — vereinigt alle 17 Bereichsdateien (de) zu EINER flachen Karte.
// Migrationspakete fassen nur ihre eigene Bereichsdatei an; diese Liste ist vollstaendig.
import start from './start.json' with { type: 'json' };
import auth from './auth.json' with { type: 'json' };
import nav from './nav.json' with { type: 'json' };
import home from './home.json' with { type: 'json' };
import listen from './listen.json' with { type: 'json' };
import konto from './konto.json' with { type: 'json' };
import admin from './admin.json' with { type: 'json' };
import wertebereiche from './wertebereiche.json' with { type: 'json' };
import versand from './versand.json' with { type: 'json' };
import alarme from './alarme.json' with { type: 'json' };
import layout from './layout.json' with { type: 'json' };
import trip from './trip.json' with { type: 'json' };
import vergleich from './vergleich.json' with { type: 'json' };
import aktionen from './aktionen.json' with { type: 'json' };
import bausteine from './bausteine.json' with { type: 'json' };
import fehler from './fehler.json' with { type: 'json' };
import hilfe from './hilfe.json' with { type: 'json' };

export const de = {
	...start,
	...auth,
	...nav,
	...home,
	...listen,
	...konto,
	...admin,
	...wertebereiche,
	...versand,
	...alarme,
	...layout,
	...trip,
	...vergleich,
	...aktionen,
	...bausteine,
	...fehler,
	...hilfe
};
