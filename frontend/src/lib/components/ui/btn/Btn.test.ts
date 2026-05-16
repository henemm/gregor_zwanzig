// Btn-Component-Tests sind aktuell deaktiviert (#228):
// node --experimental-strip-types --test kann keine .svelte-Imports laden.
//
// Original-Test-Code (230 Zeilen, SSR-Renders aller 7 Variants x 8 Sizes,
// href-Switch, disabled-State, ARIA-Pattern) ist archiviert in
// docs/specs/modules/issue_214_btn_feature_parity.md (Archive-Block am Ende).
//
// Reaktivierung moeglich bei kuenftiger Migration auf Vitest oder
// Playwright Component Tests (eigener Issue).

import { test } from 'node:test';

test.skip('Btn — Tests deaktiviert (siehe #228)', () => {});
