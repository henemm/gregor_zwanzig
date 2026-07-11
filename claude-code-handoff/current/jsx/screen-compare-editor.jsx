/* screen-compare-editor.jsx
 * ═══════════════════════════════════════════════════════════════════════
 *  Orts-Vergleich anlegen & bearbeiten — Progressive Tab Editor
 *  Identisches Pattern wie ScreenTripNewV2 / ScreenTripEditV2.
 *  screen-compare-wizard.jsx deprecated 2026-06-09 — durch diesen Editor ersetzt.
 *
 *  Prefix: CE_ — Babel-Scope-Disziplin (CLAUDE.md)
 *  Export:  window.ScreenCompareEditor
 *
 *  mode="create"  →  Tabs sequenziell freigeschaltet + Fortschrittsbalken
 *  mode="edit"    →  alle Tabs sofort frei, Speichern / Verwerfen
 *
 *  Modell (PO 2026-07-11): Vergleich = STEHENDER MONITOR, kein Proto-Trip.
 *  Versand wie Trip: Briefing-Uhrzeiten (heute/morgen), kein Enddatum-Zwang. Kein Score/Ranking (PO 2026-07-08):
 *  Übersicht = Orte als Spalten, Metriken als Zeilen (CompareEmailV2),
 *  Idealbereich wird pro Wert markiert.
 * ═══════════════════════════════════════════════════════════════════════ */

const CE_TAB_DEFS = [
  { id: "vergleich",  label: "Vergleich",   lockHint: null },
  { id: "orte",       label: "Orte",         lockHint: "erst Vergleich benennen" },
  { id: "idealwerte", label: "Wertebereiche", lockHint: "erst mind. 2 Orte auswählen" },
  { id: "layout",     label: "Layout",       lockHint: "erst Wertebereiche öffnen" },
  { id: "versand",    label: "Versand",      lockHint: "erst Layout öffnen" },
];

const CE_CHANNELS = [
  { id: "email",    label: "Email",    maxCols: Infinity, hint: "alles · Übersicht + Stunden je Ort" },
  { id: "telegram", label: "Telegram", maxCols: 8,        hint: "max 8 Spalten" },
  { id: "sms",      label: "SMS",      maxCols: 0,        hint: "flach · ≤ 140 Zeichen" },
];

const CE_IDEALS = {
  "wintersport": [
    { label: "Schneehöhe",      ideal: "≥ 80 cm",              pos: [0.55, 1.00], notes: "Mindestauflage Piste",   scale: ["0 cm", "300+ cm"] },
    { label: "Neuschnee 24 h",  ideal: "+ je mehr je besser",  pos: [0.30, 1.00], notes: "Pulver-Bonus",           scale: ["0", "40 cm"] },
    { label: "Wind (Mittel)",   ideal: "≤ 30 km/h",            pos: [0.00, 0.40], notes: "Lift kritisch ab 50",    scale: ["0", "Sturm"] },
    { label: "Temperatur gef.", ideal: "−8 bis +2 °C",         pos: [0.30, 0.65], notes: "pulvrig & griffig",      scale: ["−20°", "+15°"] },
    { label: "Niederschlag",    ideal: "Schnee ok · Regen aus", pos: [0.00, 0.25], notes: "Regen → Abbruch",       scale: ["trocken", "Starkregen"] },
    { label: "Sichtweite",      ideal: "≥ 5 km",               pos: [0.50, 1.00], notes: "Nebel = Abbruch",        scale: ["0", "klar"] },
  ],
  "wintersport-glacier": [
    { label: "Schneehöhe",      ideal: "≥ 150 cm",             pos: [0.65, 1.00], notes: "Gletscher braucht Auflage", scale: ["0", "400+ cm"] },
    { label: "Wind (Mittel)",   ideal: "≤ 25 km/h",            pos: [0.00, 0.35], notes: "Höhenwind kritisch",     scale: ["0", "Sturm"] },
    { label: "Temperatur gef.", ideal: "−15 bis −2 °C",        pos: [0.20, 0.55], notes: "kalt = stabil",          scale: ["−30°", "+10°"] },
    { label: "0°-Linie",        ideal: "≤ 2000 m",             pos: [0.00, 0.40], notes: "tief = sicher",          scale: ["500 m", "4000 m"] },
  ],
  "alpine-touring": [
    { label: "Wind (Mittel)",   ideal: "≤ 30 km/h",            pos: [0.00, 0.40], notes: "Gratwege",               scale: ["0", "Sturm"] },
    { label: "Lawinenstufe",    ideal: "≤ Stufe 2",            pos: [0.00, 0.40], notes: "ab 3 Vorsicht",          scale: ["1", "5"] },
    { label: "Sichtweite",      ideal: "≥ 1 km",               pos: [0.20, 1.00], notes: "Spaltenrisiko",          scale: ["Nebel", "klar"] },
    { label: "Sonnenstunden",   ideal: "≥ 3 h",                pos: [0.40, 1.00], notes: "Aufstiegs-Komfort",      scale: ["0 h", "8 h"] },
  ],
  "hiking": [
    { label: "Niederschlag",    ideal: "≤ 2 mm/h",             pos: [0.00, 0.25], notes: "trocken bevorzugt",      scale: ["trocken", "Starkregen"] },
    { label: "Wind (Mittel)",   ideal: "≤ 25 km/h",            pos: [0.00, 0.40], notes: "Grat-Tauglichkeit",      scale: ["0", "Sturm"] },
    { label: "Gewitter-Risiko", ideal: "kein Risiko",          pos: [0.00, 0.15], notes: "Abbruch bei Gewitter",   scale: ["niedrig", "hoch"] },
    { label: "Temperatur",      ideal: "+8 bis +22 °C",        pos: [0.40, 0.75], notes: "angenehm",               scale: ["−5°", "+35°"] },
  ],
  "trail-running": [
    { label: "Temperatur",      ideal: "+8 bis +18 °C",        pos: [0.40, 0.70], notes: "Wettkampf-Temp",         scale: ["0°", "+30°"] },
    { label: "UV-Index",        ideal: "≤ 6",                  pos: [0.00, 0.55], notes: "kein Sonnenbrand",       scale: ["0", "extrem"] },
    { label: "Niederschlag",    ideal: "≤ 1 mm/h",             pos: [0.00, 0.20], notes: "trocken",                scale: ["trocken", "Starkregen"] },
  ],
};

/* ─── Freischalt-Logik ─── */
function CE_unlocked(name, pickedCount, idealsVis, layoutVis) {
  const s = new Set(["vergleich"]);
  if (name.trim()) s.add("orte");
  if (pickedCount >= 2) s.add("idealwerte");
  if (idealsVis) s.add("layout");
  if (layoutVis) s.add("versand");
  return s;
}

function CE_doneSet(name, pickedCount, idealsVis, layoutVis, versandVis) {
  const s = new Set();
  if (name.trim()) s.add("vergleich");
  if (pickedCount >= 2) s.add("orte");
  if (idealsVis) s.add("idealwerte");
  if (layoutVis) s.add("layout");
  if (versandVis) s.add("versand");
  return s;
}

/* ─── Tab Bar ─── */
function CE_TabBar({ active, unlocked, done, onChange, isEdit }) {
  const [flash, setFlash] = React.useState(null);
  const handleClick = (id) => {
    if (isEdit || unlocked.has(id)) onChange(id);
    else { setFlash(id); setTimeout(() => setFlash(null), 500); }
  };
  return (
    <div style={{ borderBottom: "1px solid var(--g-rule)", padding: "0 40px", display: "flex", gap: 0, overflowX: "auto" }}>
      {CE_TAB_DEFS.map((t) => {
        const on   = t.id === active;
        const open = isEdit || unlocked.has(t.id);
        const isDone = !isEdit && done.has(t.id) && !on;
        return (
          <div key={t.id} onClick={() => handleClick(t.id)}
            title={!open && t.lockHint ? `Gesperrt — ${t.lockHint}` : undefined}
            style={{
              padding: "12px 16px", cursor: open ? "pointer" : "not-allowed",
              fontSize: 13, fontWeight: on ? 600 : 500,
              color: on ? "var(--g-ink)" : open ? "var(--g-ink-3)" : "var(--g-ink-4)",
              borderBottom: on ? "2px solid var(--g-accent)" : "2px solid transparent",
              marginBottom: -1, display: "flex", alignItems: "center", gap: 5,
              whiteSpace: "nowrap", opacity: open ? 1 : 0.34,
              transition: "opacity 250ms, color 200ms",
              transform: flash === t.id ? "translateX(2px)" : "none",
              userSelect: "none",
            }}>
            {t.label}
            {isDone && (
              <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 5px", borderRadius: 3, background: "rgba(61,107,58,0.12)", color: "var(--g-good)", fontFamily: "var(--g-font-mono)" }}>✓</span>
            )}
            {!open && (
              <span style={{ fontSize: 10, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", opacity: 0.7 }}>⊘</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Fortschrittsbalken (create only) ─── */
function CE_Progress({ done }) {
  const steps = ["vergleich", "orte", "idealwerte", "layout", "versand"];
  const n = steps.filter(s => done.has(s)).length;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 7 }}>
      <div style={{ display: "flex", gap: 3 }}>
        {steps.map(s => (
          <div key={s} style={{ width: 24, height: 3, borderRadius: 2, background: done.has(s) ? "var(--g-accent)" : "var(--g-rule)", transition: "background 350ms" }}/>
        ))}
      </div>
      <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
        {n === 0 ? "Noch nichts eingerichtet" : `${n} / ${steps.length} Abschnitte eingerichtet`}
      </span>
    </div>
  );
}

/* ─── Tab 1: Vergleich ─── */
function CE_VergleichTab({ name, onName, region, onRegion, profileId, onProfile, isEdit, onContinue }) {
  const can = name.trim().length > 0;
  const profiles = window.LOCATION_ACTIVITY_PROFILES || [];
  return (
    <div style={{ position: "relative", padding: "28px 40px 60px" }}>
      <TopoBg opacity={0.10}/>
      <div style={{ position: "relative", maxWidth: 640 }}>
        <Eyebrow style={{ marginBottom: 14 }}>Eckdaten</Eyebrow>

        <Field label="Name des Vergleichs" hint="Erscheint im Mail-Betreff. Kurz & wiedererkennbar.">
          <Input value={name} onChange={e => onName(e.target.value)}
            placeholder="z.B. Skitouren Hochkönig" size="lg"/>
        </Field>

        <Field label="Region"
          right={<span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>optional · max 60</span>}>
          <Input value={region} onChange={e => onRegion(e.target.value.slice(0, 60))}
            placeholder="z.B. Hochkönig · Salzburger Land" size="lg"/>
        </Field>

        <Eyebrow style={{ marginBottom: 12, marginTop: 28 }}>Aktivitätsprofil</Eyebrow>
        <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginBottom: 14 }}>
          Bestimmt, welche Wetter-Metriken verglichen werden. Die Idealwerte legst du im nächsten Tab fest.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {profiles.map(p => (
            <button key={p.id} onClick={() => onProfile(p.id)} style={{
              textAlign: "left", cursor: "pointer", padding: "14px 16px",
              background: profileId === p.id ? "var(--g-accent-tint)" : "var(--g-card)",
              border: profileId === p.id ? "1.5px solid var(--g-accent)" : "1px solid var(--g-rule)",
              borderRadius: "var(--g-r-3)", fontFamily: "var(--g-font-sans)",
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: profileId === p.id ? "var(--g-accent-deep)" : "var(--g-ink)", marginBottom: 4 }}>{p.label}</div>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", letterSpacing: "0.02em" }}>{p.metrics.join(" · ")}</div>
            </button>
          ))}
        </div>

        {!isEdit && (
          <div style={{ marginTop: 28, paddingTop: 20, borderTop: "1px solid var(--g-rule)", display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12 }}>
            {!can && <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>⊘ Name fehlt</span>}
            <Btn variant={can ? "accent" : "quiet"} size="md"
              onClick={can ? onContinue : undefined}
              style={!can ? { opacity: 0.45, cursor: "not-allowed" } : {}}>
              Orte hinzufügen →
            </Btn>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Tab 2: Orte ─── */
function CE_OrteTab({ pickedIds, setPickedIds, isEdit, onContinue }) {
  const locations = window.MOCK_LOCATIONS || [];
  const picked    = pickedIds.map(id => locations.find(l => l.id === id)).filter(Boolean);
  const canAdv    = pickedIds.length >= 2;

  const groups = locations.filter(l => l.group !== "Test").reduce((acc, l) => {
    (acc[l.group] = acc[l.group] || []).push(l); return acc;
  }, {});

  return (
    <div style={{ position: "relative", padding: "28px 40px 60px" }}>
      <TopoBg opacity={0.10}/>
      <div style={{ position: "relative", maxWidth: 980 }}>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 28 }}>
          {/* Smart Import */}
          <div>
            <Eyebrow style={{ marginBottom: 14 }}>Neuen Ort hinzufügen</Eyebrow>
            <div style={{ padding: "16px 16px 14px", background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)" }}>
              <Field label="Smart-Import" hint="URL aus Komoot/Google Maps oder Koordinaten direkt" dense>
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", background: "var(--g-card-alt)", border: "1.5px solid var(--g-accent)", borderRadius: "var(--g-r-2)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--g-accent)" strokeWidth="2">
                    <path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/>
                    <path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/>
                  </svg>
                  <span className="mono" style={{ fontSize: 12, color: "var(--g-ink)", flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    komoot.com/de-de/highlight/2049832
                  </span>
                  <Pill tone="good">erkannt</Pill>
                </div>
              </Field>
              <div style={{ padding: "10px 12px", background: "var(--g-paper-deep)", borderRadius: "var(--g-r-2)", marginBottom: 12 }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 4 }}>Erkannt</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)" }}>Aberg-Karbachalm</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>47.4380, 13.0421 · 1893 m · Hochkönig</div>
              </div>
              <Btn variant="primary" size="sm" style={{ width: "100%", justifyContent: "center" }}>＋ Zum Vergleich hinzufügen</Btn>
            </div>
          </div>

          {/* Picked list */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 14 }}>
              <Eyebrow>Im Vergleich · {picked.length}</Eyebrow>
              <span className="mono" style={{ fontSize: 10.5, color: picked.length < 2 ? "var(--g-warn)" : "var(--g-ink-4)", letterSpacing: "0.04em" }}>
                {picked.length < 2 ? "min. 2 erforderlich" : picked.length > 5 ? "viel — Empfehlung 3–5" : "passt"}
              </span>
            </div>
            {picked.length === 0 ? (
              <div style={{ padding: "28px 18px", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-2)", textAlign: "center", color: "var(--g-ink-3)", fontSize: 13, lineHeight: 1.6 }}>
                Noch keine Orte.<br/>
                <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>links hinzufügen oder unten auswählen</span>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {picked.map((l, i) => (
                  <div key={l.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)" }}>
                    <span className="mono" style={{ width: 22, height: 22, borderRadius: 4, background: "var(--g-ink)", color: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{l.name}</div>
                      <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginTop: 1 }}>{l.group} · {l.elev} m</div>
                    </div>
                    <button onClick={() => setPickedIds(pickedIds.filter(x => x !== l.id))} style={{ background: "transparent", border: "none", padding: 6, color: "var(--g-ink-4)", cursor: "pointer", fontSize: 12 }}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Bibliothek */}
        <Eyebrow style={{ marginBottom: 12 }}>… oder aus gespeicherten Orten wählen</Eyebrow>
        <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", padding: "14px 18px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18 }}>
            {Object.entries(groups).map(([group, items]) => (
              <div key={group}>
                <div className="mono" style={{ fontSize: 10, letterSpacing: "0.10em", textTransform: "uppercase", color: "var(--g-ink-3)", fontWeight: 600, padding: "0 0 8px", marginBottom: 4, borderBottom: "1px solid var(--g-rule-soft)" }}>{group} · {items.length}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {items.map(l => {
                    const on = pickedIds.includes(l.id);
                    return (
                      <button key={l.id}
                        onClick={() => setPickedIds(on ? pickedIds.filter(x => x !== l.id) : [...pickedIds, l.id])}
                        style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", background: on ? "var(--g-accent-tint)" : "transparent", border: "none", borderRadius: "var(--g-r-2)", cursor: "pointer", textAlign: "left", fontFamily: "var(--g-font-sans)" }}>
                        <span style={{ width: 14, height: 14, borderRadius: 3, border: `1.5px solid ${on ? "var(--g-accent)" : "var(--g-rule)"}`, background: on ? "var(--g-accent)" : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                          {on && <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M2 6l3 3 5-6"/></svg>}
                        </span>
                        <span style={{ flex: 1, fontSize: 12.5, color: "var(--g-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{l.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {!isEdit && (
          <div style={{ marginTop: 28, paddingTop: 20, borderTop: "1px solid var(--g-rule)", display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12 }}>
            {!canAdv && <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>⊘ min. 2 Orte auswählen</span>}
            <Btn variant={canAdv ? "accent" : "quiet"} size="md"
              onClick={canAdv ? onContinue : undefined}
              style={!canAdv ? { opacity: 0.45, cursor: "not-allowed" } : {}}>
              Idealwerte festlegen →
            </Btn>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Tab 3: Korridore (ersetzt Idealwerte · body-29 Phase 1) ───
 * Idealbereiche sind jetzt Korridore mit mark-Default (Vergleich). Der
 * gemeinsame Organism lebt in corridor-editor.jsx (context="vergleich"). */
function CE_IdealwerteTab({ profileId, isEdit, onContinue }) {
  const profiles = window.LOCATION_ACTIVITY_PROFILES || [];
  const profile  = profiles.find(p => p.id === profileId) || { label: profileId };
  return (
    <div style={{ position: "relative" }}>
      <CorridorEditor context="vergleich" profileLabel={profile.label}/>
      {!isEdit && (
        <div style={{ padding: "0 40px 48px", maxWidth: 1040 }}>
          <div style={{ paddingTop: 20, borderTop: "1px solid var(--g-rule)", display: "flex", justifyContent: "flex-end" }}>
            <Btn variant="accent" size="md" onClick={onContinue}>Layout einrichten →</Btn>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Tab 4: Layout — geteilter Organism (Phase 4, layout-tab.jsx) ─── */
function CE_LayoutTab({ pickedIds, isEdit, onContinue }) {
  return (
    <div style={{ position: "relative" }}>
      <LayoutTab context="vergleich" pickedIds={pickedIds}/>
      {!isEdit && (
        <div style={{ padding: "0 40px 48px", maxWidth: 1100 }}>
          <div style={{ paddingTop: 20, borderTop: "1px solid var(--g-rule)", display: "flex", justifyContent: "flex-end" }}>
            <Btn variant="accent" size="md" onClick={onContinue}>Versand einrichten →</Btn>
          </div>
        </div>
      )}
    </div>
  );
}

/* CE_LayoutPreview → nach LT_ComparePreview (layout-tab.jsx) gewandert (Phase 4). */

/* ─── Tab 5: Versand — geteilter Organism (Phase 4, versand-tab.jsx) ─── */
function CE_VersandTab({ name, pickedIds, activated, isEdit, isReady }) {
  const activation = !isEdit ? (
    isReady ? (
      <div style={{ padding: "20px 24px", background: "var(--g-good)", borderRadius: "var(--g-r-3)", color: "#fff", display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ width: 44, height: 44, borderRadius: "50%", background: "rgba(255,255,255,0.15)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, fontWeight: 700 }}>✓</div>
        <div style={{ flex: 1 }}>
          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "rgba(255,255,255,0.7)", marginBottom: 4 }}>Bereit zum Aktivieren</div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>„{name}" · {pickedIds.length} Orte · jeden Do 18:00 fürs Wochenende</div>
          <div style={{ fontSize: 12.5, color: "rgba(255,255,255,0.85)", marginTop: 4, lineHeight: 1.5 }}>
            Läuft ohne Enddatum, bis du pausierst — das Briefing kommt vor jedem Wochenende automatisch in dein Postfach.
          </div>
        </div>
      </div>
    ) : (
      <div style={{ padding: "18px 22px", background: "var(--g-ink)", borderRadius: "var(--g-r-3)", color: "#fff" }}>
        <div className="mono" style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "rgba(255,255,255,0.55)", marginBottom: 4 }}>Bereit zum Aktivieren</div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>„{name || "Neuer Vergleich"}" · {pickedIds.length} Orte</div>
        <div style={{ fontSize: 12.5, color: "rgba(255,255,255,0.75)", marginTop: 4, lineHeight: 1.5 }}>
          Versand jeden Donnerstag 18:00 an gregor_zwanzig@henemm.com — fürs kommende Wochenende.
        </div>
      </div>
    )
  ) : null;
  return <VersandTab context="vergleich" activation={activation}/>;
}

/* ════════════════════════════════════════════════════════════════════
 *  Main: ScreenCompareEditor
 * ════════════════════════════════════════════════════════════════════ */
function ScreenCompareEditor({ mode = "create", preset = "empty", initialTab, editingName, activated = false } = {}) {
  const isEdit = mode === "edit";

  const CE_PRESETS = {
    empty: {
      name: "", region: "", profileId: "wintersport",
      pickedIds: [], idealsVis: false, layoutVis: false, versandVis: false, tab: "vergleich",
    },
    name_done: {
      name: "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport",
      pickedIds: [], idealsVis: false, layoutVis: false, versandVis: false, tab: "orte",
    },
    orte_done: {
      name: "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport",
      pickedIds: ["loc-01", "loc-07", "loc-08", "loc-09", "loc-10"],
      idealsVis: false, layoutVis: false, versandVis: false, tab: "idealwerte",
    },
    idealwerte_done: {
      name: "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport",
      pickedIds: ["loc-01", "loc-07", "loc-08", "loc-09", "loc-10"],
      idealsVis: true, layoutVis: false, versandVis: false, tab: "layout",
    },
    all_done: {
      name: "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport",
      pickedIds: ["loc-01", "loc-07", "loc-08", "loc-09", "loc-10"],
      idealsVis: true, layoutVis: true, versandVis: true, tab: "versand",
    },
  };

  const p = isEdit ? {
    name: editingName || "Skitouren Hochkönig", region: "Hochkönig · Salzburger Land", profileId: "wintersport",
    pickedIds: ["loc-01", "loc-07", "loc-08", "loc-09", "loc-10"],
    idealsVis: true, layoutVis: true, versandVis: true, tab: initialTab || "vergleich",
  } : (CE_PRESETS[preset] || CE_PRESETS.empty);

  const [name,       setName]       = React.useState(p.name);
  const [region,     setRegion]     = React.useState(p.region);
  const [profileId,  setProfileId]  = React.useState(p.profileId);
  const [pickedIds,  setPickedIds]  = React.useState(p.pickedIds);
  const [idealsVis,  setIdealsVis]  = React.useState(p.idealsVis);
  const [layoutVis,  setLayoutVis]  = React.useState(p.layoutVis);
  const [versandVis, setVersandVis] = React.useState(p.versandVis);
  const [tab,        setTab]        = React.useState(p.tab);
  const [dirty,      setDirty]      = React.useState(false);

  const ul   = CE_unlocked(name, pickedIds.length, idealsVis, layoutVis);
  const done = CE_doneSet(name, pickedIds.length, idealsVis, layoutVis, versandVis);
  const isReady = done.has("versand");

  const switchTab = (id) => {
    if (!isEdit && !ul.has(id)) return;
    setTab(id);
    if (id === "idealwerte") setIdealsVis(true);
    if (id === "layout")     setLayoutVis(true);
    if (id === "versand")    setVersandVis(true);
    if (isEdit)              setDirty(true);
  };

  const markDirty = (fn) => (...args) => { fn(...args); if (isEdit) setDirty(true); };

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}
      data-screen-label={isEdit ? "Orts-Vergleich bearbeiten" : "Neuer Orts-Vergleich"}>
      <Sidebar active="compare"/>
      <main style={{ flex: 1, position: "relative", overflowY: "auto", overflowX: "hidden" }}>
        <TopoBg opacity={0.12}/>

        {/* Breadcrumb + Aktionen */}
        <div style={{ position: "relative", padding: "14px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.06em" }}>
            <span style={{ opacity: 0.6 }}>Orts-Vergleiche</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>{isEdit ? (name || "Vergleich") : "Neuer Vergleich"}</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {isEdit ? (
              <React.Fragment>
                {dirty && <Pill tone="warn">Ungespeichert</Pill>}
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: activated ? "var(--g-good)" : "var(--g-ink-4)" }}/>
                <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.04em" }}>{activated ? "aktiv" : "pausiert"}</span>
                <Btn variant="ghost" size="sm" onClick={() => setDirty(false)}>Verwerfen</Btn>
                <Btn variant="primary" size="sm" onClick={() => setDirty(false)}>Speichern</Btn>
              </React.Fragment>
            ) : (
              <React.Fragment>
                {!isReady && <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)" }}>Versand einrichten zum Aktivieren</span>}
                <Btn variant="ghost" size="sm">Abbrechen</Btn>
                <Btn variant={isReady ? "primary" : "quiet"} size="sm"
                  style={!isReady ? { opacity: 0.4, cursor: "not-allowed" } : {}}>
                  Briefing aktivieren
                </Btn>
              </React.Fragment>
            )}
          </div>
        </div>

        {/* Hero */}
        <div style={{ position: "relative", padding: "20px 40px 14px" }}>
          <Eyebrow>{isEdit ? "Orts-Vergleich bearbeiten" : "Neuer Orts-Vergleich"}</Eyebrow>
          <h1 style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em", margin: "4px 0 0", lineHeight: 1.1, color: name.trim() ? "var(--g-ink)" : "var(--g-ink-4)" }}>
            {name.trim() || "Noch kein Name"}
          </h1>
          {!isEdit && <CE_Progress done={done}/>}
        </div>

        {/* Tab-Bar */}
        <CE_TabBar active={tab} unlocked={ul} done={done} onChange={switchTab} isEdit={isEdit}/>

        {/* Tab-Inhalt */}
        {tab === "vergleich"  && <CE_VergleichTab  name={name} onName={markDirty(setName)} region={region} onRegion={markDirty(setRegion)} profileId={profileId} onProfile={markDirty(setProfileId)} isEdit={isEdit} onContinue={() => switchTab("orte")}/>}
        {tab === "orte"       && <CE_OrteTab       pickedIds={pickedIds} setPickedIds={markDirty(setPickedIds)} isEdit={isEdit} onContinue={() => switchTab("idealwerte")}/>}
        {tab === "idealwerte" && <CE_IdealwerteTab profileId={profileId} isEdit={isEdit} onContinue={() => switchTab("layout")}/>}
        {tab === "layout"     && <CE_LayoutTab     pickedIds={pickedIds} isEdit={isEdit} onContinue={() => switchTab("versand")}/>}
        {tab === "versand"    && <CE_VersandTab    name={name} pickedIds={pickedIds} activated={activated} isEdit={isEdit} isReady={isReady}/>}
      </main>
    </div>
  );
}

window.ScreenCompareEditor = ScreenCompareEditor;
