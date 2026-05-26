/* Screen: Trip-Wizard — 4 Schritte:
 *   1. Profil & Eckdaten   — Aktivitätsprofil bestimmt ETA-Tempo + Default-Metrikenset
 *   2. GPX-Import          — beliebig viele GPX-Files, drag-sortierbar, leere Etappe = Pause
 *   3. Etappen & Wegpunkte — KI-Vorschläge, Reorder, Pausentag einschieben
 *   4. Briefings & Kanäle  — Zeiten, Schwellen
 */

const ACTIVITY_PROFILES = [
  { id: "trekking",   label: "Trekking & Wandern", sub: "Hütten- & Höhenwanderung", pace: "4 km/h ↑300 m/h", icon: "▲" },
  { id: "skitour",    label: "Skitour",            sub: "Aufstieg + Abfahrt",        pace: "300 hm/h",        icon: "◆" },
  { id: "alpine",     label: "Hochtour",           sub: "Gletscher, Fels, Eis",      pace: "350 hm/h",        icon: "▲▲" },
  { id: "ferrata",    label: "Klettersteig",       sub: "Gesicherte Routen",         pace: "200 hm/h",        icon: "≈" },
  { id: "mtb",        label: "MTB",                sub: "Mountainbike-Touren",       pace: "12 km/h",         icon: "○○" },
];

function ScreenTripWizard({ initialStep = 2 }) {
  const [step, setStep] = React.useState(initialStep);
  const [profile, setProfile] = React.useState("trekking");
  const trip = MOCK_TRIP;

  const stepTitles = {
    1: "Profil & Eckdaten",
    2: "GPX-Import",
    3: "Etappen & Wegpunkte",
    4: "Briefings & Kanäle",
  };

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="trips"/>
      <main style={{ flex: 1, position: "relative" }}>
        <TopoBg opacity={0.16}/>

        <div style={{ position: "relative", padding: "16px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
            <span style={{ opacity: 0.6 }}>Trips</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>Neuer Trip</span>
          </div>
          <Btn variant="ghost" size="sm">Abbrechen</Btn>
        </div>

        <div style={{ position: "relative", padding: "32px 40px 60px", maxWidth: 1180, margin: "0 auto" }}>
          <Eyebrow>Neuer Trip · Schritt {step} von 4</Eyebrow>
          <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em", marginTop: 4, marginBottom: 24 }}>
            {stepTitles[step]}
          </div>

          <Stepper step={step} onStep={setStep}/>

          <div style={{ marginTop: 32 }}>
            {step === 1 && <StepProfile profile={profile} onProfile={setProfile} onNext={() => setStep(2)}/>}
            {step === 2 && <StepGpx onPrev={() => setStep(1)} onNext={() => setStep(3)}/>}
            {step === 3 && <StepStages trip={trip} onPrev={() => setStep(2)} onNext={() => setStep(4)}/>}
            {step === 4 && <StepBriefings trip={trip} onPrev={() => setStep(3)}/>}
          </div>
        </div>
      </main>
    </div>
  );
}

function Stepper({ step, onStep }) {
  const steps = [
    { n: 1, label: "Profil",            sub: "Aktivität & Tempo" },
    { n: 2, label: "GPX-Import",        sub: "Etappen-Files" },
    { n: 3, label: "Wegpunkte",         sub: "KI-Vorschläge" },
    { n: 4, label: "Briefings",         sub: "Zeiten & Kanäle" },
  ];
  return (
    <div style={{ display: "flex", gap: 0, borderTop: "1px solid var(--g-rule)", borderBottom: "1px solid var(--g-rule)" }}>
      {steps.map((s, i) => {
        const active = s.n === step;
        const done = s.n < step;
        return (
          <div key={s.n} onClick={() => onStep(s.n)} style={{
            flex: 1, padding: "16px 20px", cursor: "pointer", borderRight: i < steps.length - 1 ? "1px solid var(--g-rule)" : "none",
            borderTop: active ? "2px solid var(--g-accent)" : "2px solid transparent",
            background: active ? "var(--g-paper)" : "transparent",
            opacity: done || active ? 1 : 0.5,
          }}>
            <div className="mono" style={{ fontSize: 10, color: active ? "var(--g-accent)" : "var(--g-ink-4)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
              {done ? "✓ " : `0${s.n} · `}
              {s.sub}
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, marginTop: 2 }}>{s.label}</div>
          </div>
        );
      })}
    </div>
  );
}

/* ─────────────────── Schritt 1 — Profil & Eckdaten ─────────────────── */

function StepProfile({ profile, onProfile, onNext }) {
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
        <Card padding={24}>
          <Eyebrow>Trip-Eckdaten</Eyebrow>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4, marginBottom: 18 }}>Wie soll der Trip heißen?</div>

          <Field label="Trip-Name">
            <Input placeholder="z.B. Karnischer Höhenweg 2026" defaultValue="Karnischer Höhenweg 403"/>
          </Field>
          <Field label="Kürzel" hint="Erscheint in Briefing-Header und SMS">
            <Input placeholder="KHW 403" defaultValue="KHW 403" size="sm"/>
          </Field>
          <Field label="Reisezeitraum" hint="Tatsächliche Daten kommen aus den GPX-Files">
            <div style={{ display: "flex", gap: 8 }}>
              <Input defaultValue="06.05.2026" size="sm"/>
              <span style={{ alignSelf: "center", color: "var(--g-ink-4)" }}>–</span>
              <Input defaultValue="12.05.2026" size="sm"/>
            </div>
          </Field>
        </Card>

        <Card padding={24}>
          <Eyebrow>Aktivitätsprofil</Eyebrow>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4, marginBottom: 6 }}>Was für eine Tour wird das?</div>
          <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginBottom: 16, lineHeight: 1.5 }}>
            Bestimmt die Tempo-Annahme für die Berechnung der ETAs an Wegpunkten und schlägt ein passendes Default-Metrikenset für die Briefings vor. Beides bleibt nachträglich änderbar.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {ACTIVITY_PROFILES.map(p => (
              <ProfileChip key={p.id} profile={p} active={p.id === profile} onClick={() => onProfile(p.id)}/>
            ))}
          </div>
        </Card>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 24 }}>
        <Btn variant="primary" size="md" onClick={onNext}>Weiter zu GPX-Import →</Btn>
      </div>
    </div>
  );
}

function ProfileChip({ profile, active, onClick }) {
  return (
    <div onClick={onClick} style={{
      padding: "12px 14px", cursor: "pointer", borderRadius: 4,
      background: active ? "rgba(196,90,42,0.08)" : "var(--g-card-alt)",
      border: active ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
      transition: "all 120ms",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: active ? "var(--g-accent-deep)" : "var(--g-ink)" }}>
          {profile.label}
        </div>
        <span className="mono" style={{ fontSize: 14, color: active ? "var(--g-accent)" : "var(--g-ink-4)" }}>{profile.icon}</span>
      </div>
      <div style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 3 }}>{profile.sub}</div>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 6, letterSpacing: "0.04em" }}>
        Tempo: {profile.pace}
      </div>
    </div>
  );
}

/* ─────────────────── Schritt 2 — GPX-Import (Liste, sortierbar) ─────────────────── */

function StepGpx({ onPrev, onNext }) {
  // Beispiel-Etappen-Liste, wie sie nach Multi-Upload aussehen würde
  const [items, setItems] = React.useState([
    { id: "g1", file: "tag1_birnlücke.gpx",     extracted: { from: "Kasseler Hütte",     to: "Birnlücke",      km: 14.2, ascent: 980,  descent: 720 } },
    { id: "g2", file: "tag2_clarahütte.gpx",    extracted: { from: "Birnlücke",          to: "Clarahütte",     km: 11.8, ascent: 420,  descent: 1140 } },
    { id: "p1", pause: true,                     extracted: { name: "Pausentag · Clarahütte" } },
    { id: "g3", file: "tag4_essener_hütte.gpx", extracted: { from: "Clarahütte",         to: "Essener Hütte",  km: 16.4, ascent: 1320, descent: 580 } },
    { id: "g4", file: "tag5_warnsdorfer.gpx",   extracted: { from: "Essener Hütte",      to: "Warnsdorfer H.", km: 12.1, ascent: 740,  descent: 920 } },
  ]);
  const [drag, setDrag] = React.useState(null);

  const handleDragStart = (id) => () => setDrag(id);
  const handleDragOver = (id) => (e) => {
    e.preventDefault();
    if (drag == null || drag === id) return;
    const next = [...items];
    const fromIdx = next.findIndex(it => it.id === drag);
    const toIdx = next.findIndex(it => it.id === id);
    const [moved] = next.splice(fromIdx, 1);
    next.splice(toIdx, 0, moved);
    setItems(next);
  };
  const handleDragEnd = () => setDrag(null);

  const insertPause = (afterIdx) => {
    const next = [...items];
    next.splice(afterIdx + 1, 0, {
      id: "p" + Date.now(),
      pause: true,
      extracted: { name: "Pausentag" },
    });
    setItems(next);
  };
  const remove = (id) => setItems(items.filter(i => i.id !== id));

  const stages = items.length;
  const pauseCount = items.filter(i => i.pause).length;

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 24 }}>
        {/* Linke Spalte — Liste */}
        <div>
          <Card padding={0}>
            <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <Eyebrow>Etappen-Liste · ein GPX = eine Etappe</Eyebrow>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
                  {stages - pauseCount} GPX-Etappen · {pauseCount} Pausentag{pauseCount !== 1 && "e"}
                </div>
              </div>
              <Btn variant="ghost" size="sm">+ GPX hinzufügen</Btn>
            </div>

            <div style={{ padding: 12 }}>
              {items.map((it, i) => (
                <GpxItem
                  key={it.id}
                  item={it}
                  index={i}
                  draggedId={drag}
                  onDragStart={handleDragStart(it.id)}
                  onDragOver={handleDragOver(it.id)}
                  onDragEnd={handleDragEnd}
                  onInsertPause={() => insertPause(i)}
                  onRemove={() => remove(it.id)}
                />
              ))}

              {/* Drop-Zone unten */}
              <div style={{
                marginTop: 8, padding: 24, border: "2px dashed var(--g-rule)", borderRadius: 4,
                textAlign: "center", background: "rgba(0,0,0,0.01)",
                cursor: "pointer",
              }}>
                <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginBottom: 6 }}>
                  Weitere GPX-Dateien hier ablegen — oder
                  <span style={{ color: "var(--g-accent)", fontWeight: 600 }}> Datei wählen</span>
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>
                  Mehrfachauswahl möglich · Komoot · Outdooractive · Garmin · FootPath
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Rechte Spalte — Hilfe & Vorlagen */}
        <div>
          <Card padding={18} style={{ marginBottom: 16 }}>
            <Eyebrow>So geht's</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginTop: 6, lineHeight: 1.6 }}>
              <p style={{ margin: "0 0 10px" }}>Standard ist <strong>ein GPX-File pro Etappe</strong> (= ein Tag). Reihenfolge per Drag verschiebbar — die Etappen werden automatisch chronologisch nummeriert.</p>
              <p style={{ margin: 0 }}>Pausentage entstehen durch <strong>leere Etappen</strong> ohne GPX. Klick aufs <span className="mono" style={{ background: "var(--g-card-alt)", padding: "1px 5px", border: "1px solid var(--g-rule)" }}>+ Pause</span> zwischen zwei Etappen.</p>
            </div>
          </Card>

          <Card padding={18}>
            <Eyebrow>Vorlagen statt eigenem Trip</Eyebrow>
            <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 4, marginBottom: 12 }}>
              Wenn du einen bekannten Weg gehst, kannst du eine Vorlage importieren statt GPX hochzuladen.
            </div>
            <div style={{ display: "grid", gap: 6 }}>
              {[
                { name: "GR20",                    sub: "Korsika · 16 Etappen · 180 km" },
                { name: "Karnischer Höhenweg",     sub: "AT/IT · 9 Etappen · 142 km" },
                { name: "Stubaier Höhenweg",       sub: "AT · 7 Etappen · 90 km" },
              ].map((t, i) => (
                <div key={i} style={{ padding: "8px 10px", background: "var(--g-card-alt)", borderRadius: 4, cursor: "pointer", border: "1px solid var(--g-rule-soft)" }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{t.name}</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 2 }}>{t.sub}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
        <Btn variant="ghost" size="md" onClick={onPrev}>← Zurück</Btn>
        <Btn variant="primary" size="md" onClick={onNext}>Weiter zu Wegpunkten →</Btn>
      </div>
    </div>
  );
}

function GpxItem({ item, index, draggedId, onDragStart, onDragOver, onDragEnd, onInsertPause, onRemove }) {
  const dragging = draggedId === item.id;
  const stageNum = String(index + 1).padStart(2, "0");

  if (item.pause) {
    return (
      <div
        draggable
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragEnd={onDragEnd}
        style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "12px 14px", marginBottom: 6, borderRadius: 4,
          background: dragging ? "var(--g-paper)" : "var(--g-card-alt)",
          border: "1px dashed var(--g-rule)",
          opacity: dragging ? 0.4 : 1,
          cursor: "grab",
        }}
      >
        <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", width: 22 }}>⋮⋮</span>
        <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--g-ink-3)", width: 28 }}>T{stageNum}</span>
        <span style={{ flex: 1, fontSize: 13, color: "var(--g-ink-2)", fontStyle: "italic" }}>
          {item.extracted.name}
          <span style={{ color: "var(--g-ink-4)", marginLeft: 8, fontStyle: "normal" }}>· keine GPX nötig</span>
        </span>
        <Btn variant="ghost" size="xs" onClick={onRemove}>Entfernen</Btn>
      </div>
    );
  }

  return (
    <div>
      <div
        draggable
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragEnd={onDragEnd}
        style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "12px 14px", marginBottom: 4, borderRadius: 4,
          background: "var(--g-card)",
          border: "1px solid var(--g-rule)",
          opacity: dragging ? 0.4 : 1,
          cursor: "grab",
        }}
      >
        <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", width: 22 }}>⋮⋮</span>
        <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--g-accent)", width: 28 }}>T{stageNum}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>
            {item.extracted.from} <span style={{ color: "var(--g-ink-4)", fontWeight: 400 }}>→</span> {item.extracted.to}
          </div>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 3 }}>
            {item.file} · {item.extracted.km} km · ↑{item.extracted.ascent} ↓{item.extracted.descent}
          </div>
        </div>
        <Btn variant="ghost" size="xs" onClick={onRemove}>Entfernen</Btn>
      </div>
      {/* Pause-Insert-Zone zwischen Items */}
      <div style={{ height: 4, position: "relative", marginBottom: 4 }}>
        <button
          onClick={onInsertPause}
          style={{
            position: "absolute", left: "50%", top: -7, transform: "translateX(-50%)",
            padding: "2px 8px", fontSize: 10, fontFamily: "var(--g-font-mono)",
            background: "var(--g-paper)", border: "1px solid var(--g-rule)", borderRadius: 10,
            color: "var(--g-ink-3)", cursor: "pointer", letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--g-accent)"; e.currentTarget.style.color = "var(--g-accent)"; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--g-rule)"; e.currentTarget.style.color = "var(--g-ink-3)"; }}
        >+ Pause</button>
      </div>
    </div>
  );
}

/* ─────────────────── Schritt 3 — Etappen & Wegpunkte ─────────────────── */

function StepStages({ trip, onPrev, onNext }) {
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 24 }}>
        <Card padding={0}>
          <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--g-rule-soft)" }}>
            <Eyebrow>Aus GPX extrahiert</Eyebrow>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{trip.stages.length} Etappen</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
              {trip.totalKm} km · ↑{trip.totalAscent} ↓{trip.totalDescent}
            </div>
          </div>
          <div>
            {trip.stages.map((s, i) => (
              <div key={i} style={{
                padding: "10px 18px", borderBottom: "1px solid var(--g-rule-soft)",
                background: i === 1 ? "rgba(196,90,42,0.05)" : "transparent",
                borderLeft: i === 1 ? "3px solid var(--g-accent)" : "3px solid transparent",
                cursor: "pointer",
              }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>{s.code}</div>
                <div style={{ fontSize: 13, fontWeight: 500, marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {s.title.replace(/^[^:]+: /,"")}
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 3 }}>
                  {s.km} km · {s.waypoints.length} WP · {s.waypoints.filter(w=>w.ai).length} KI
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card padding={20}>
          <Eyebrow>{trip.stages[1].code} · KI-Vorschläge prüfen</Eyebrow>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4, marginBottom: 4 }}>
            {trip.stages[1].title.replace(/^[^:]+: /,"")}
          </div>
          <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginBottom: 16 }}>
            Die KI hat 3 Wetterscheiden vorgeschlagen — Punkte mit signifikanter Höhen- oder Expositions-Änderung.
            Sie werden zu Mess-Wegpunkten, sobald du sie bestätigst.
          </div>

          <MiniProfile stage={trip.stages[1]}/>

          <div style={{ marginTop: 18, display: "grid", gap: 8 }}>
            {trip.stages[1].waypoints.map((wp, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 12, padding: "10px 14px",
                background: "var(--g-card-alt)", borderRadius: 4,
                border: wp.ai ? "1px dashed var(--g-accent)" : "1px solid var(--g-rule)",
              }}>
                <span style={{
                  width: 22, height: 22, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                  background: wp.ai ? "rgba(196,90,42,0.15)" : "var(--g-paper)",
                  border: `2px ${wp.ai ? "dashed" : "solid"} var(--g-accent)`,
                  fontFamily: "var(--g-font-mono)", fontSize: 10, fontWeight: 700, color: "var(--g-accent-deep)",
                }}>{i + 1}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{wp.name}</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)" }}>
                    {wp.elev} m · ETA {wp.time} {wp.ai && <span style={{ color: "var(--g-accent)", fontWeight: 600 }}>· Vorschlag</span>}
                  </div>
                </div>
                {wp.ai ? (
                  <div style={{ display: "flex", gap: 4 }}>
                    <Btn variant="primary" size="xs">✓ Übernehmen</Btn>
                    <Btn variant="ghost" size="xs">✕</Btn>
                  </div>
                ) : (
                  <span className="mono" style={{ fontSize: 10, color: "var(--g-good)", textTransform: "uppercase", letterSpacing: "0.08em" }}>fix</span>
                )}
              </div>
            ))}
          </div>

          <div style={{ marginTop: 16, padding: 12, background: "rgba(196,90,42,0.06)", borderLeft: "3px solid var(--g-accent)", fontSize: 13, color: "var(--g-ink-2)" }}>
            <strong>Tipp:</strong> Du kannst Wegpunkte später jederzeit auf der Karte umsetzen — keine Lat/Lon-Eingabe nötig.
          </div>
        </Card>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
        <Btn variant="ghost" size="md" onClick={onPrev}>← Zurück</Btn>
        <Btn variant="primary" size="md" onClick={onNext}>Weiter zu Briefings →</Btn>
      </div>
    </div>
  );
}

function MiniProfile({ stage }) {
  const W = 600, H = 90;
  const min = Math.min(...stage.profile), max = Math.max(...stage.profile);
  const range = max - min || 1;
  const pts = stage.profile.map((v, i) => {
    const x = (i / (stage.profile.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 12) - 4;
    return [x, y];
  });
  const path = "M" + pts.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");
  const fillPath = path + ` L${W},${H} L0,${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: "block", background: "var(--g-card-alt)", borderRadius: 4 }}>
      <path d={fillPath} fill="rgba(196, 90, 42, 0.1)"/>
      <path d={path} fill="none" stroke="var(--g-accent)" strokeWidth="1.5"/>
      {stage.waypoints.map((wp, i) => {
        const t = i / (stage.waypoints.length - 1);
        const idx = Math.round(t * (stage.profile.length - 1));
        const [x, y] = pts[idx];
        return <circle key={i} cx={x} cy={y} r="4" fill={wp.ai ? "rgba(196,90,42,0.2)" : "#fff"} stroke="var(--g-accent)" strokeWidth="1.5" strokeDasharray={wp.ai ? "2,1.5" : "0"}/>;
      })}
    </svg>
  );
}

/* ─────────────────── Schritt 4 — Briefings & Kanäle ─────────────────── */

function StepBriefings({ trip, onPrev }) {
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <Card padding={20}>
          <Eyebrow>Deine Kanäle</Eyebrow>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2, marginBottom: 4 }}>Wohin sollen Briefings?</div>
          <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginBottom: 14, lineHeight: 1.5 }}>
            Briefings gehen an deine eigenen Kanäle — Email, Signal, Telegram, SMS. Pro Kanal aktivierbar.
          </div>
          <div style={{ display: "grid", gap: 10 }}>
            <ChannelRow kind="Email"    target="gregor_zwanzig@henemm.com" active/>
            <ChannelRow kind="Signal"   target="+49 151 ••• 8847"            active/>
            <ChannelRow kind="Telegram" target="@gregor_henemm"/>
            <ChannelRow kind="SMS"      target="+49 151 ••• 8847"            sub="Fallback wenn andere Kanäle ausfallen"/>
            <Btn variant="ghost" size="sm" style={{ alignSelf: "flex-start", marginTop: 4 }}>Kanäle in den Einstellungen verwalten →</Btn>
          </div>
        </Card>

        <Card padding={20}>
          <Eyebrow>Briefings</Eyebrow>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2, marginBottom: 14 }}>Wann & was</div>

          <BriefingScheduleRow label="Morgen-Briefing" sub="Vor Etappenstart, alles Wichtige für den Tag" time="06:00" enabled/>
          <BriefingScheduleRow label="Abend-Briefing"  sub="Nach Tagesende, Ausblick auf morgen" time="18:00" enabled/>

          <div style={{ marginTop: 14 }}>
            <Eyebrow>Alert-Schwellen</Eyebrow>
            <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2, marginBottom: 8 }}>
              Sofort-Alerts wenn Vorhersage diese Werte überschreitet
            </div>
            <ThresholdRow label="Windböen" value="≥ 50 km/h"/>
            <ThresholdRow label="Niederschlag" value="≥ 10 mm/h"/>
            <ThresholdRow label="Gewitter-Wahrscheinlichkeit" value="≥ 40 %"/>
            <ThresholdRow label="Schneefallgrenze" value="200 m unter Tour-Höhe"/>
          </div>
        </Card>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
        <Btn variant="ghost" size="md" onClick={onPrev}>← Zurück</Btn>
        <Btn variant="primary" size="md">Trip anlegen</Btn>
      </div>
    </div>
  );
}

window.ScreenTripWizard = ScreenTripWizard;
