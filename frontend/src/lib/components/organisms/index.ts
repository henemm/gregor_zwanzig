// Epic #471 — Organisms-Schicht: kanonische Re-Export-Barrel.
//
// Eine Quelle fuer alle 4 Organisms:
//   import { TripHeader, TripWizardShell, AlertRulesEditor, OutputLayoutEditor }
//     from '$lib/components/organisms';
//
// Barrel-Pattern: physische .svelte-Dateien verbleiben in ihren Feature-Ordnern.
// Organisms importieren nur aus atoms/, molecules/ oder anderen organisms/ (kein ui/).
//
// Spec: docs/specs/modules/epic_471_organisms_layer.md

export { default as TripHeader } from '../trip-detail/TripHeader.svelte';
export { default as TripWizardShell } from '../trip-wizard/TripWizardShell.svelte';
export { default as AlertRulesEditor } from '../alert-rules-editor/AlertRulesEditor.svelte';
export { default as OutputLayoutEditor } from '../shared/OutputLayoutEditor.svelte';
