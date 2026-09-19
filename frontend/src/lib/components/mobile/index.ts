// Issue #373 — Mobile-Touch-Primitives: kanonische Re-Export-Barrel (Bridge-Ansatz).
//
// Eine Quelle fuer alle 11 Primitive:
//   import { MBtn, MInput, MField, MSwitch, MTab, MIcon,
//            BottomNav, Drawer, Sheet, Toast, MobileShell }
//     from '$lib/components/mobile';
//
// 10 neue Touch-Primitive + 1 Re-Export-Wrapper auf das ui/sidebar/-Pendant (#267).
// Mobile-Shell S2: TopAppBar ist abgeschafft (kein fixer Balken oben mehr).
//
// Spec: docs/specs/modules/issue_373_mobile.md (AC-1)

// 10 neue Touch-Primitive
export { default as MBtn } from './MBtn.svelte';
export { default as MInput } from './MInput.svelte';
export { default as MField } from './MField.svelte';
export { default as MSwitch } from './MSwitch.svelte';
export { default as MTab } from './MTab.svelte';
export { default as MIcon } from './MIcon.svelte';
export { default as Drawer } from './Drawer.svelte';
export { default as Sheet } from './Sheet.svelte';
export { default as Toast } from './Toast.svelte';
export { default as MobileShell } from './MobileShell.svelte';

// Re-Export-Wrapper (Bridge auf ui/sidebar/, #267)
export { default as BottomNav } from './BottomNav.svelte';

// Issue #493 — Compare Bottom-Sheet (Block E, Epic #485)
export { default as MCompareActionSheet } from './MCompareActionSheet.svelte';

// Typen aus neuen Primitiven
export type { MBtnVariant, MBtnSize } from './MBtn.svelte';
export type { MIconKind } from './MIcon.svelte';
export type { MTabItem } from './MTab.svelte';
export type { SheetSnap } from './Sheet.svelte';
export type { ToastKind } from './Toast.svelte';
