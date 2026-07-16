// Issue #301 Lieferung B — Subscription-Helfer.
//
// Reines Verschieben der zuvor inline im Subscriptions-Panel
// lebenden Hilfsfunktionen, damit AutoReportCard.svelte sie nutzt
// und die Logik isoliert per node:test gedeckt ist (keine Mocks).
//
// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (§1)

import type { ComparePreset, ActivityProfile } from '../../types.js';
// Issue #1268 (AC-10): geteilte Slot-Aufloesung — NICHT nachbauen.
import { primarySendSlot } from '../../utils/cockpitHelpers568';

// Konvention 0=Montag. NICHT Sonntag-first.
const WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];

// Issue #439 — Status-Ableitung für die Übersichtsseite.
// Rein Frontend; kein Backend-Feld. Spec §2 (issue_439_compare_uebersicht.md).
export type CompareStatus = 'active' | 'paused' | 'draft';

export const STATUS_MAP = {
	active: { label: 'aktiv',    dot: 'var(--g-accent)' },
	paused: { label: 'pausiert', dot: 'var(--g-ink-3)'  },
	draft:  { label: 'draft',    dot: 'var(--g-ink-4)'  },
} as const;

// Issue #459 — ComparePreset-Helfer für das Auto-Briefings-Sidepanel.
// Spec: docs/specs/modules/issue_459_auto_briefings_sidepanel.md (§2)

/** ComparePreset → lesbares Zeitplan-Label. */
export function presetScheduleLabel(preset: ComparePreset): string {
	if (preset.schedule === 'daily') {
		return `Täglich ${preset.hour_from}–${preset.hour_to} Uhr`;
	}
	if (preset.schedule === 'weekly') return 'Wöchentlich';
	return 'Manuell';
}

/**
 * Date → kompakter Versand-String "D.M. HH:MM" | "manuell" wenn null.
 *
 * Issue #647 — DRY: vorher lokal in CompareStatusRow.svelte dupliziert.
 * Wird in der Home-Compare-Outbox (homeCompareTimeline) und im Compare-Hero
 * wiederverwendet.
 *
 * Issue #1268 (Adversary-Fund F007): Die Minuten waren hart ":00" verdrahtet.
 * Das ging auf, solange die Zeit aus `hour_from` (Integer → immer volle Stunde)
 * stammte. Seit AC-9/AC-10 kommt sie aus `morning_time`/`evening_time`, die per
 * <input type="time"> ohne `step` (VTSchedulePlan.svelte:86/:111) auch "07:30"
 * sein koennen — die Zeitplan-Kachel zeigte dann 07:30, diese Anzeige daneben
 * 07:00. Ausserdem wird diese Funktion in `_home/cockpitHelpers.ts:223` fuer
 * `letzter_versand` benutzt, einen ECHTEN Versand-Zeitstempel: dort war ":00"
 * schon vor #1268 falsch (ein Versand um 06:03 wurde als 06:00 angezeigt).
 */
export function formatNextSend(d: Date | null): string {
	if (!d) return 'manuell';
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${d.getDate()}.${d.getMonth() + 1}. ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** ISO-Timestamp → kurzes deutsches Datum (de-DE) | "Noch kein Versand" wenn leer/ungültig. */
export function formatLastSent(iso?: string | null): string {
	if (!iso) return 'Noch kein Versand';
	const d = new Date(iso);
	if (isNaN(d.getTime())) return 'Noch kein Versand';
	return d.toLocaleDateString('de-DE', {
		day: '2-digit',
		month: '2-digit',
		year: 'numeric'
	});
}

// Issue #472 — ComparePreset-Status-Ableitung + Orte-Label für die Listenansicht.
// Spec: docs/specs/modules/issue_472_compare_list_restore.md (§2 + §6)

/**
 * ComparePreset → Status (rein frontend-seitig abgeleitet).
 *
 * Issue #1250 Scheibe 2 (Pause-Konvergenz, AC-8/AC-9): `paused_at` ist die
 * bevorzugte Quelle beim Lesen (Trip-Zielsemantik), Fallback bleibt die
 * Alt-Semantik `schedule === 'manual'` fuer Presets, die `paused_at` noch
 * nicht tragen. Draft-Vorrang bleibt oberste Regel.
 */
export function deriveStatusFromPreset(p: ComparePreset): CompareStatus {
	if (!p.name || p.location_ids.length === 0) return 'draft';
	if (p.paused_at) return 'paused';
	if (p.schedule === 'manual') return 'paused';
	return 'active';
}

/**
 * Issue #1256 Scheibe 7 Staging-Fund SF-2 (CRITICAL, AC-37): Statuspille-
 * Ableitung mit optionalem lokalen Schedule-Override. Der Compare-Hub
 * (CompareTabs) haelt fuer seine Aktivierungs-Karte einen eigenen
 * `localSchedule`-PUT-Pfad OHNE `invalidateAll()` (das wuerde die dort
 * eingefrorene `currentPreset`-Baseline mit frisch geladenen Routendaten
 * kollidieren lassen) — die Header-Statuspille auf `/compare/[id]` liest
 * aber weiterhin `data.preset`, das nur der Kebab-Pfad aktualisiert. Ohne
 * Override bliebe die Pille nach einem Pausieren/Aktivieren aus der Karte
 * auf dem alten Status stehen, bis ein echter Reload eintrifft.
 * `scheduleOverride === null` (kein Override gesetzt bzw. durch einen echten
 * Reload verworfen) laesst `p.schedule` unveraendert durch.
 *
 * Issue #1250 Scheibe 2: `deriveStatusFromPreset` bevorzugt seit AC-9
 * `paused_at` vor `schedule`. Ein gesetzter Override wuerde sonst an einem
 * stalen `p.paused_at` einfrieren (z.B. Reaktivieren-Override auf ein
 * Preset, dessen `paused_at` noch den alten Pausenzeitstempel traegt) —
 * daher wird `paused_at` bei gesetztem Override konsistent mitgefuehrt.
 */
export function deriveStatusWithScheduleOverride(
	p: ComparePreset,
	scheduleOverride: string | null
): CompareStatus {
	return deriveStatusFromPreset({
		...p,
		schedule: (scheduleOverride ?? p.schedule) as ComparePreset['schedule'],
		paused_at: scheduleOverride
			? (scheduleOverride === 'manual' ? (p.paused_at ?? '__optimistic__') : undefined)
			: p.paused_at
	});
}

/**
 * Issue #1250 Scheibe 3 (AC-12): Hub-Hinweis "Laufzeit überschritten".
 *
 * `true` gdw. das Preset per Auto-Pause pausiert wurde (`paused_at` gesetzt)
 * UND ein `end_date` traegt, das (datumsmaessig, ohne Uhrzeit) vor heute
 * liegt. Rein abgeleitet, kein eigenes Backend-Feld (Design-Entscheidung
 * docs/context/feat-1250-s3-auto-pause.md).
 */
export function isRuntimeExceeded(p: ComparePreset): boolean {
	if (!p.paused_at || !p.end_date) return false;
	const end = new Date(`${p.end_date}T00:00:00`);
	if (isNaN(end.getTime())) return false;
	const today = new Date();
	today.setHours(0, 0, 0, 0);
	return end.getTime() < today.getTime();
}

/** ComparePreset → "N Orte" */
export function presetLocationsLabel(p: ComparePreset): string {
	return `${p.location_ids.length} ${p.location_ids.length === 1 ? 'Ort' : 'Orte'}`;
}

/**
 * Kanalanzahl → "N Kanäle" (Singular bei genau 1: "1 Kanal").
 *
 * Design-Fidelity 2026-07 Fix 1 — konsolidiert die zuvor duplizierte
 * Singular/Plural-Ternary aus CompareTabs.svelte:248 und
 * compare/[id]/+page.svelte:204 an einer Stelle.
 */
export function channelCountLabel(n: number): string {
	return `${n} ${n === 1 ? 'Kanal' : 'Kanäle'}`;
}

// Issue #488 — Kebab-Aktionen für die Compare-Kachel.
// Spec: docs/specs/modules/issue_488_compare_tile_atoms.md §1
//
// Die Kebab-Komponente emittiert nur `onSelect(id)` — die Elternkomponente
// ist für API-Calls und Confirm-Dialoge zuständig. `danger: true` markiert
// destruktive Aktionen (Löschen) für rote Texteinfärbung im Menü.

// Issue #582 — Kachel-Helfer für die Compare-Liste (Design-Fidelity 1:1).
// Spec: docs/specs/modules/issue_582_compare_list_fidelity.md

// Inline-Map statt Import aus types.ts (vermeidet value-Import-Auflösungsproblem
// bei node --experimental-strip-types, das .js nicht auf .ts mappt).
const PROFILE_LABELS: Record<string, string> = {
	allgemein:       'Allgemein',
	wintersport:     'Wintersport',
	wandern:         'Wandern',
	summer_trekking: 'Sommer-Trekking',
};

/**
 * ActivityProfile-Key → lesbares deutsches Label.
 * Case-insensitive: "SUMMER_TREKKING" == "summer_trekking" → "Sommer-Trekking".
 * Leeres/unbekanntes profil → "" (kein Platzhalter; Kachel zeigt nur "N Orte").
 */
export function presetProfileLabel(profil: ActivityProfile | string | undefined): string {
	if (!profil) return '';
	return PROFILE_LABELS[String(profil).toLowerCase()] ?? '';
}

/**
 * ComparePreset → kompaktes Rhythmus-Kurzlabel für die Kachel (AC-5).
 * Unterscheidet sich von presetScheduleLabel (#459 Sidepanel-Lang-Label):
 *   daily   → "tägl. HH" (zweistellige Stunde, kein –bis)
 *   weekly  → Wochentag-Name
 *   manual  → "manuell"
 *
 * Issue #1268 (AC-10): Die Stunde stammt aus dem echten Versand-Slot
 * (primarySendSlot → resolvePresetSlots, geteilt mit deriveNextSend), nicht mehr
 * aus `hour_from`. `hour_from` war der Start des Bewertungs-Zeitfensters; seit
 * #1268 schickt der Wizard es nicht mehr mit, Go schreibt den Zero-Value 0 —
 * die Kachel zeigte dann "tägl. 00", eine Uhrzeit, zu der nichts passiert.
 */
export function presetTileScheduleLabel(preset: ComparePreset): string {
	if (preset.schedule === 'daily') {
		const slot = primarySendSlot(preset);
		if (slot === null) return 'tägl.';
		const h = String(slot.hour).padStart(2, '0');
		return `tägl. ${h}`;
	}
	if (preset.schedule === 'weekly') {
		return WEEKDAYS[preset.weekday ?? 0] ?? 'wöchentl.';
	}
	return 'manuell';
}

/**
 * ISO-Timestamp → relatives deutsches Label.
 *   heute        → "heute"
 *   gestern      → "gestern"
 *   diese Woche  → Wochentag-Name
 *   ältere Daten → "vor N Wochen"
 *   undefined    → ''
 */
export function relativeLastSent(iso: string | undefined): string {
	if (!iso) return '';
	const d = new Date(iso);
	if (isNaN(d.getTime())) return '';

	const now = new Date();
	// Tages-Differenz ohne Uhrzeit
	const diffMs = now.setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0);
	const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

	if (diffDays <= 0) return 'heute';
	if (diffDays === 1) return 'gestern';
	if (diffDays < 7) return WEEKDAYS[d.getDay() === 0 ? 6 : d.getDay() - 1] ?? 'diese Woche';
	const weeks = Math.floor(diffDays / 7);
	return `vor ${weeks} ${weeks === 1 ? 'Woche' : 'Wochen'}`;
}

/**
 * Kanal-Keys aus empfaenger + Opt-in-Feldern. Signal NIEMALS (PO #610).
 *
 * Issue #1270 (AC-8, KB-6): Telegram/SMS werden aus den Opt-in-Feldern
 * `send_telegram`/`send_sms` abgeleitet — NICHT mehr aus den Keys von
 * `display_config.channel_layouts`. `channel_layouts` hält nur Metrik-Layouts
 * je Kanal, und CompareEditor.svelte:605-606 legt die telegram/sms-Keys IMMER
 * an (auch leer) — der Kanal-Umschalter zeigte Telegram/SMS darum unabhängig
 * vom echten Opt-in an. Signal hat kein Opt-in-Feld und kann damit strukturell
 * nicht mehr auftauchen (statt über eine Allowlist gefiltert zu werden).
 */
export function presetChannels(preset: ComparePreset): string[] {
	const result: string[] = [];
	// E-Mail: mind. ein Eintrag mit "@".
	// Jede Adresse mit "@" gilt als E-Mail — kein Substring-Match auf Adressen,
	// der legitime Adressen wie signal@firma.com sperren würde.
	if (preset.empfaenger.some((e) => e.includes('@'))) {
		result.push('Email');
	}
	if (preset.send_telegram === true) result.push('Telegram');
	if (preset.send_sms === true) result.push('SMS');
	return result;
}

/**
 * ComparePreset → Kanal-NAMEN statt Kanal-Anzahl ("Email · Telegram"),
 * Soll `screen-compare-detail.jsx:147-150`. Dünner Wrapper um presetChannels()
 * (Code-Teilungs-Invariante — keine neue Datenherleitung, nur Formatierung
 * für die Hub-Übersicht "Kanäle"-Stat, Issue #1256 Scheibe 3 AC-6).
 * 0 Kanäle → "—" (JSX-Leerfall), nie eine leere Zeichenkette.
 */
export function channelNamesLabel(preset: ComparePreset): string {
	const channels = presetChannels(preset);
	return channels.length === 0 ? '—' : channels.join(' · ');
}

export type CompareAction = { id: string; label: string; danger?: boolean };

export function compareActions(status: CompareStatus): CompareAction[] {
	if (status === 'draft') {
		return [
			{ id: 'setup', label: 'Setup fortsetzen' },
			{ id: 'delete', label: 'Löschen', danger: true }
		];
	}
	// Issue #626: Toggle-Label kontextabhängig; Issue #627: 'send' wieder aufgenommen.
	// Issue #1256 Scheibe 1: 'archive' entfernt (Soll molecules.jsx:1018-1027) —
	// Archivieren ist ab Scheibe 3 exklusiv Teil der Hub-Header-Lifecycle-Liste
	// (compareLifecycleActions()), nicht mehr Teil des Listen-Kebabs.
	const pauseLabel = status === 'paused' ? 'Aktivieren' : 'Pausieren';
	return [
		{ id: 'pause', label: pauseLabel },
		{ id: 'send', label: 'Briefing jetzt senden' },
		{ id: 'preview', label: 'Vorschau öffnen' },
		{ id: 'edit', label: 'Bearbeiten' },
		{ id: 'delete', label: 'Löschen', danger: true }
	];
}

// Issue #1256 Scheibe 3 — Hub-Header-Kebab: NUR Lebenszyklus-Aktionen
// (Pausieren/Aktivieren, Archivieren, Löschen), analog `CHub_lifecycleActions`
// (`screen-compare-detail.jsx:27-33`). Bearbeiten/Vorschau/Senden bleiben
// exklusiv über Tabs bzw. die Primäraktion erreichbar (AC-5). Löst KL-7 auf:
// "Archivieren" wandert komplett hierher, weg vom Listen-Kebab (Scheibe 1).
export function compareLifecycleActions(status: CompareStatus): CompareAction[] {
	if (status === 'draft') {
		return [{ id: 'trash', label: 'Entwurf löschen', danger: true }];
	}
	const toggle =
		status === 'active' ? { id: 'pause', label: 'Pausieren' } : { id: 'resume', label: 'Aktivieren' };
	return [toggle, { id: 'archive', label: 'Archivieren' }, { id: 'trash', label: 'Löschen', danger: true }];
}

// Issue #1261 (a) — Desktop-Detail-Kebab: Lebenszyklus-Aktionen PLUS
// "Bearbeiten" fuer active/paused (der bewusst tote #1256-S3-Zustand wird
// aufgeloest — der Nutzer fand "Bearbeiten" hier nicht mehr). NUR fuer den
// Desktop-Detail-Call-Site (routes/compare/[id]/+page.svelte) gedacht —
// compareLifecycleActions() selbst bleibt fuer das Mobile-Sheet unveraendert
// (#1256 Scheibe 8 AC-23, Regressionstest in compareDetailEditActions.test.ts).
// Draft behaelt den bestehenden Setup-Pfad, bekommt daher KEIN "edit".
export function compareDetailActions(status: CompareStatus): CompareAction[] {
	const lifecycle = compareLifecycleActions(status);
	if (status === 'draft') return lifecycle;
	const editAction: CompareAction = { id: 'edit', label: 'Bearbeiten' };
	const dangerIndex = lifecycle.findIndex((a) => a.danger);
	if (dangerIndex === -1) return [...lifecycle, editAction];
	return [...lifecycle.slice(0, dangerIndex), editAction, ...lifecycle.slice(dangerIndex)];
}

// Issue #1229 — Compare-Hub Briefing-Zeiten (Slot-basiert statt Rhythmus-Sprache).
// Spec: docs/specs/modules/issue_1229_monitor_hub.md (AC-3, Edge Cases)

/**
 * ComparePreset → lesbares Briefing-Zeiten-Label ("Morgen 06:30 · Abend 18:00").
 *
 * Format-Vorbild: mock-locations.jsx:123/148/173/197. Backend liefert
 * `HH:MM:SS` — wird auf `HH:MM` gekürzt. Kein aktiver Slot bzw. Alt-Preset
 * ohne die Slot-Felder (undefined) → "—", nie ein verwaister Trennpunkt.
 */
export function presetBriefingTimesLabel(preset: ComparePreset): string {
	const toHHMM = (t?: string) => (t ?? '').slice(0, 5);
	const parts: string[] = [];
	if (preset.morning_enabled) parts.push(`Morgen ${toHHMM(preset.morning_time)}`);
	if (preset.evening_enabled) parts.push(`Abend ${toHHMM(preset.evening_time)}`);
	return parts.length > 0 ? parts.join(' · ') : '—';
}

/**
 * Berechnet den naechsten { schedule, previous_schedule }-Zustand beim Pause-Toggle.
 *
 * - Pausieren (schedule != 'manual'): setzt schedule='manual', merkt altes schedule.
 * - Reaktivieren (schedule == 'manual'): stellt previous_schedule wieder her (Fallback 'daily').
 *
 * Issue #631 — Wochen-Rhythmus ueber Pause hinweg erhalten.
 */
export function computePauseToggle(preset: {
	schedule: string;
	previous_schedule?: string;
}): { schedule: string; previous_schedule?: string } {
	if (preset.schedule !== 'manual') {
		return { schedule: 'manual', previous_schedule: preset.schedule };
	}
	const restored = preset.previous_schedule || 'daily';
	return { schedule: restored, previous_schedule: preset.previous_schedule };
}
