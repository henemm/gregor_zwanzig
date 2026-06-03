// Issue #372/#478 — Molecules-Schicht: kanonische Re-Export-Barrel.
//
// Eine Quelle fuer alle 11 Molecules:
//   import { Field, DetailRow, StagePill, ChannelRow, ChannelChip,
//            BriefingTimelineRow, BriefingScheduleRow, ThresholdRow,
//            Stat, AlertRow, ConfirmDialog }
//     from '$lib/components/molecules';
//
// Specs: docs/specs/modules/issue_372_molecules.md + issue_478_trip_detail_dialog_migration.md

export { default as Field } from './Field.svelte';
export { default as DetailRow } from './DetailRow.svelte';
export { default as StagePill } from './StagePill.svelte';
export { default as ChannelRow } from './ChannelRow.svelte';
export { default as ChannelChip, channelGlyph } from './ChannelChip.svelte';
export { default as BriefingTimelineRow } from './BriefingTimelineRow.svelte';
export { default as BriefingScheduleRow } from './BriefingScheduleRow.svelte';
export { default as ThresholdRow } from './ThresholdRow.svelte';
export { default as Stat } from './Stat.svelte';
export { default as AlertRow } from './AlertRow.svelte';
export { default as ConfirmDialog } from './ConfirmDialog.svelte';

// Issue #488 — Compare-Kachel-Atome (Epic #485 Block A).
// Cross-Verzeichnis-Re-Export, damit alle Downstream-Issues (#485-B/C/D)
// die Molecule-API einheitlich aus `$lib/components/molecules` importieren.
export { default as CompareTile }       from '../compare/CompareTile.svelte';
export { default as CompareStatusPill } from '../compare/CompareStatusPill.svelte';
export { default as CompareKebab }      from '../compare/CompareKebab.svelte';
export { default as CompareLocationRow } from './CompareLocationRow.svelte';
export { default as CompareIdealRow } from './CompareIdealRow.svelte';
export { default as CompareLayoutRow } from './CompareLayoutRow.svelte';
export { default as ReportConfigDialog } from './ReportConfigDialog.svelte';
export { default as TestReportDialog } from './TestReportDialog.svelte';

// Issue #568 — Startseite-Cockpit-Molecules (Spec: docs/specs/modules/issue_568_home_redesign.md).
export { default as QuickAction } from './QuickAction.svelte';
export { default as SetupResumeCard } from './SetupResumeCard.svelte';

// Issue #571 — Home Cockpit Hero (Compare-Modus + CompareStatusRow + Stretch-Fix).
export { default as CompareStatusRow } from './CompareStatusRow.svelte';

