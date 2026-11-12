// Epic #471 — Organisms-Schicht: kanonische Re-Export-Barrel.
//
// Eine Quelle fuer alle Organisms:
//   import { TripHeader, OutputLayoutEditor,
//            WeatherMetricsTab }
//     from '$lib/components/organisms';
//
// Barrel-Pattern: physische .svelte-Dateien verbleiben in ihren Feature-Ordnern.
// Organisms importieren nur aus atoms/, molecules/ oder anderen organisms/ (kein ui/).
//
// Spec: docs/specs/modules/epic_471_organisms_layer.md
//       docs/specs/modules/issue_520_organisms_barrel_completeness.md

export { default as TripHeader } from '../trip-detail/TripHeader.svelte';
export { default as OutputLayoutEditor } from '../shared/OutputLayoutEditor.svelte';

// Issue #520 — trip-detail Organisms aufnehmen
export { default as WeatherMetricsTab }   from '../shared/WeatherMetricsTab.svelte';

// Issue #578 — Block C: neue Home-Organisms + Metrics-Organisms
// Issue #1277 — Geteiltes Listen-Tabellen-Organism (Trips + Orts-Vergleiche)
export { default as ListTable }                from './ListTable.svelte';
export { default as ListTableRow }             from './ListTableRow.svelte';
export { default as ListActionsMenu }          from './ListActionsMenu.svelte';
export { default as ListNameCell }             from './ListNameCell.svelte';

export { default as OutboxCard }               from './OutboxCard.svelte';
export { default as AlertsCard }               from './AlertsCard.svelte';
export { default as PresetRail }               from './PresetRail.svelte';
export { default as MetricOffShelf }           from './MetricOffShelf.svelte';

// Issue #2913 — Wetter-Reiter (Trip + Orts-Briefing, context="route"|"vergleich"), Logik bleibt in shared/wetter-tab/*.ts
// Teil 2 (K-1): die Seite ist shared/WetterTab.svelte (Regel (a)); Zustand/Laden/Speichern im Organismus WetterTabInhalt.
export { default as WetterTabInhalt }          from './wetter-tab/WetterTabInhalt.svelte';
export { default as VorlageKarte }             from './wetter-tab/VorlageKarte.svelte';
export { default as MetrikZeile }              from './wetter-tab/MetrikZeile.svelte';
export { default as GrenzenEditor }            from './wetter-tab/GrenzenEditor.svelte';
export { default as WarnungenRadarKarte }      from './wetter-tab/WarnungenRadarKarte.svelte';
export { default as AmpelLeiste }              from './wetter-tab/AmpelLeiste.svelte';
export { default as AlarmAbKopf }              from './wetter-tab/AlarmAbKopf.svelte';
export { default as NichtImBriefing }          from './wetter-tab/NichtImBriefing.svelte';
export { default as AnpassenKarte }            from './wetter-tab/AnpassenKarte.svelte';
