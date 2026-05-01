import { useState, useRef, useCallback } from "react";

const PRESETS = {
  economics: {
    conditions: [
      { name: "Method / tool", desc: "Computational or empirical method", keywords: ["agent-based model", "simulation", "machine learning", "nlp", "llm", "algorithm"] },
      { name: "Economics domain", desc: "Core economics field", keywords: ["economics", "econometrics", "labor market", "macroeconomics", "behavioral economics", "finance"] },
      { name: "Topic focus", desc: "Phenomenon or outcome", keywords: ["inequality", "poverty", "gdp", "unemployment", "inflation", "welfare", "taxation"] },
    ],
  },
  "social science": {
    conditions: [
      { name: "Method / tool", desc: "Research method", keywords: ["survey", "experiment", "regression", "machine learning", "text analysis", "ethnography"] },
      { name: "Social science domain", desc: "Discipline", keywords: ["sociology", "anthropology", "demography", "criminology", "social psychology", "communication"] },
      { name: "Topic focus", desc: "Social phenomenon", keywords: ["inequality", "discrimination", "migration", "social mobility", "identity", "institutions"] },
    ],
  },
  blank: {
    conditions: [
      { name: "Condition 1", desc: "", keywords: [] },
      { name: "Condition 2", desc: "", keywords: [] },
      { name: "Condition 3", desc: "", keywords: [] },
    ],
  },
};

const CC = [
  { bg: "#EEEDFE", bd: "#AFA9EC", tx: "#3C3489" },
  { bg: "#E1F5EE", bd: "#5DCAA5", tx: "#085041" },
  { bg: "#FAEEDA", bd: "#EF9F27", tx: "#633806" },
];

function parseCSV(text) {
  const lines = text.split("\n").filter(l => l.trim());
  if (lines.length < 2) return [];
  const parseRow = (line) => {
    const vals = []; let v = "", q = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') { q = !q; continue; }
      if (ch === ',' && !q) { vals.push(v.trim()); v = ""; continue; }
      v += ch;
    }
    vals.push(v.trim());
    return vals;
  };
  const headers = parseRow(lines[0]).map(h => h.toLowerCase());
  return lines.slice(1).map(line => {
    const vals = parseRow(line);
    const obj = {};
    headers.forEach((h, i) => { obj[h] = vals[i] || ""; });
    return obj;
  });
}

function buildQuery(conds, all) {
  const op = all ? " AND " : " OR ";
  return conds.map(c => {
    if (!c.keywords.length) return null;
    return "(" + c.keywords.map(k => k.includes(" ") ? `"${k}"` : k).join(" OR ") + ")";
  }).filter(Boolean).join(op);
}

function buildSysPrompt(conds, query, all) {
  const logic = all ? "ALL" : "ANY";
  const cl = conds.map((c, i) => `${i + 1}. ${c.name} — ${c.desc}: ${c.keywords.join(", ")}`).join("\n");
  return `You are a research assistant. Filter papers based on this query:\n${query}\n\nA paper is RELEVANT if it satisfies ${logic} of these conditions:\n${cl}\n\nReturn ONLY a JSON object:\n{\n  "judgment": "True" or "False",\n  "reason": "condition numbers not satisfied, or empty"\n}`;
}

async function callLLM(key, url, model, sys, title, summary, temp) {
  const r = await fetch(`${url}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model, temperature: parseFloat(temp),
      messages: [{ role: "system", content: sys }, { role: "user", content: `Title: ${title}\nSummary: ${summary}` }],
    }),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  const d = await r.json();
  let raw = d.choices[0].message.content.trim().replace(/^```json\s*/i, "").replace(/```\s*$/, "").trim();
  return JSON.parse(raw);
}

function Tag({ label, color, onRemove }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 9px", borderRadius: 99, fontSize: 11, background: color.bg, border: `1px solid ${color.bd}`, color: color.tx, lineHeight: 1.4 }}>
      {label}
      {onRemove && <button onClick={onRemove} style={{ background: "none", border: "none", color: color.tx, cursor: "pointer", opacity: 0.5, fontSize: 13, padding: 0, lineHeight: 1 }}>×</button>}
    </span>
  );
}

function CondCard({ cond, idx, onChange }) {
  const c = CC[idx];
  const [inp, setInp] = useState("");
  const add = () => { const v = inp.trim().toLowerCase(); if (v && !cond.keywords.includes(v)) onChange({ ...cond, keywords: [...cond.keywords, v] }); setInp(""); };
  return (
    <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e5e3de", padding: 14, marginBottom: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 10 }}>
        <div style={{ width: 20, height: 20, borderRadius: "50%", background: c.bg, border: `1px solid ${c.bd}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 600, color: c.tx, flexShrink: 0, marginTop: 1 }}>{idx + 1}</div>
        <div style={{ flex: 1 }}>
          <input value={cond.name} onChange={e => onChange({ ...cond, name: e.target.value })} style={{ fontSize: 13, fontWeight: 500, color: "#1a1a18", background: "none", border: "none", borderBottom: "1px solid #ddd", padding: "1px 0", width: "100%", fontFamily: "inherit", outline: "none" }} />
          <input value={cond.desc} onChange={e => onChange({ ...cond, desc: e.target.value })} placeholder="Description..." style={{ fontSize: 11, color: "#999", background: "none", border: "none", padding: "3px 0 0", width: "100%", fontFamily: "inherit", outline: "none" }} />
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8, minHeight: 24 }}>
        {cond.keywords.length === 0 && <span style={{ fontSize: 11, color: "#ccc" }}>No keywords</span>}
        {cond.keywords.map((kw, ki) => <Tag key={ki} label={kw} color={c} onRemove={() => onChange({ ...cond, keywords: cond.keywords.filter((_, i) => i !== ki) })} />)}
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        <input value={inp} onChange={e => setInp(e.target.value)} onKeyDown={e => e.key === "Enter" && add()} placeholder="Add keyword..." style={{ flex: 1, height: 28, padding: "0 8px", borderRadius: 5, fontSize: 11, border: "1px solid #ddd", background: "#fafaf8", color: "#1a1a18", fontFamily: "inherit", outline: "none" }} />
        <button onClick={add} style={{ height: 28, padding: "0 10px", borderRadius: 5, fontSize: 11, border: "1px solid #ddd", background: "#fff", color: "#666", cursor: "pointer", fontFamily: "inherit" }}>+</button>
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("config");
  const [conds, setConds] = useState(PRESETS.economics.conditions.map(c => ({ ...c, keywords: [...c.keywords] })));
  const [allReq, setAllReq] = useState(true);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.chatanywhere.tech/v1");
  const [model, setModel] = useState("gpt-4.1");
  const [temp, setTemp] = useState("0");
  const [papers, setPapers] = useState([]);
  const [results, setResults] = useState([]);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState("");
  const [filt, setFilt] = useState("all");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(null);
  const stopRef = useRef(false);
  const fileRef = useRef();

  const loadPreset = k => setConds(PRESETS[k].conditions.map(c => ({ ...c, keywords: [...c.keywords] })));

  const handleFile = e => {
    const f = e.target.files[0]; if (!f) return;
    const r = new FileReader();
    r.onload = ev => { setPapers(parseCSV(ev.target.result)); setResults([]); setErr(""); };
    r.readAsText(f);
  };

  const run = useCallback(async () => {
    if (!apiKey) { setErr("Enter your API key"); return; }
    if (!papers.length) { setErr("Upload a CSV first"); return; }
    setErr(""); setRunning(true); setProgress(0); stopRef.current = false; setView("results");
    const q = buildQuery(conds, allReq);
    const sys = buildSysPrompt(conds, q, allReq);
    const res = [];
    for (let i = 0; i < papers.length; i++) {
      if (stopRef.current) break;
      const p = papers[i];
      try {
        const resp = await callLLM(apiKey, baseUrl, model, sys, p.title || "", p.summary || "", temp);
        res.push({ ...p, _j: resp.judgment || "False", _r: resp.reason || "" });
      } catch (e) { res.push({ ...p, _j: "False", _r: `Error: ${e.message}` }); }
      setProgress(i + 1);
      setResults([...res]);
    }
    setRunning(false);
  }, [apiKey, baseUrl, model, temp, papers, conds, allReq]);

  const relCount = results.filter(r => r._j === "True").length;
  const irrCount = results.length - relCount;
  const pct = results.length ? Math.round((relCount / results.length) * 100) : 0;

  const filtered = results.filter(r => {
    if (filt === "relevant" && r._j !== "True") return false;
    if (filt === "irrelevant" && r._j === "True") return false;
    if (search) { const s = search.toLowerCase(); return (r.title || "").toLowerCase().includes(s) || (r.summary || "").toLowerCase().includes(s); }
    return true;
  });

  const downloadCSV = () => {
    const data = filt === "relevant" ? results.filter(r => r._j === "True") : filt === "irrelevant" ? results.filter(r => r._j !== "True") : results;
    if (!data.length) return;
    const keys = Object.keys(data[0]).filter(k => !k.startsWith("_"));
    keys.push("judgment", "reason");
    const esc = v => `"${String(v).replace(/"/g, '""')}"`;
    const csv = [keys.map(esc).join(","), ...data.map(r => keys.map(k => esc(k === "judgment" ? r._j : k === "reason" ? r._r : r[k] || "")).join(","))].join("\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `papers_${filt}.csv`; a.click();
  };

  const F = (label, val, set, type, ph) => (
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
      <span style={{ fontSize: 11, color: "#999", width: 72, flexShrink: 0 }}>{label}</span>
      <input type={type || "text"} value={val} onChange={e => set(e.target.value)} placeholder={ph || ""} style={{ flex: 1, height: 28, padding: "0 8px", borderRadius: 5, fontSize: 11, border: "1px solid #e0ded8", background: "#fafaf8", color: "#1a1a18", fontFamily: "inherit", outline: "none" }} />
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#f4f3ef", fontFamily: "'DM Sans', system-ui, sans-serif", fontSize: 13 }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap" rel="stylesheet" />

      <div style={{ background: "#fff", borderBottom: "1px solid #e5e3de" }}>
        <div style={{ maxWidth: 980, margin: "0 auto", padding: "16px 20px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
            <h1 style={{ fontSize: 18, fontWeight: 500, color: "#1a1a18", fontFamily: "'Newsreader', Georgia, serif", letterSpacing: "-0.02em", margin: 0 }}>Paper sieve</h1>
            <span style={{ fontSize: 11, color: "#bbb" }}>LLM-powered relevance screening</span>
          </div>
          <div style={{ display: "flex", gap: 2 }}>
            {["config", "results"].map(v => (
              <button key={v} onClick={() => setView(v)} style={{ padding: "6px 16px", fontSize: 12, fontWeight: 500, cursor: "pointer", border: "1px solid", borderColor: view === v ? "#1a1a18" : "#e0ded8", background: view === v ? "#1a1a18" : "#fff", color: view === v ? "#fff" : "#999", borderRadius: 6, fontFamily: "inherit" }}>
                {v === "config" ? "Configure" : "Results"}
                {v === "results" && results.length > 0 && <span style={{ marginLeft: 6, fontSize: 10, opacity: 0.7 }}>({results.length})</span>}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 980, margin: "0 auto", padding: "20px 20px 60px" }}>

        {view === "config" && (
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <span style={{ fontSize: 12, fontWeight: 500, color: "#999", textTransform: "uppercase", letterSpacing: "0.04em" }}>Keyword conditions</span>
                <div style={{ display: "flex", gap: 3 }}>
                  {Object.keys(PRESETS).map(k => (
                    <button key={k} onClick={() => loadPreset(k)} style={{ padding: "3px 9px", borderRadius: 99, fontSize: 10, border: "1px solid #ddd", background: "#fff", color: "#999", cursor: "pointer", fontFamily: "inherit" }}>{k}</button>
                  ))}
                </div>
              </div>

              {conds.map((c, i) => <CondCard key={i} cond={c} idx={i} onChange={v => setConds(prev => prev.map((x, j) => j === i ? v : x))} />)}

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", background: "#fff", borderRadius: 10, border: "1px solid #e5e3de", marginTop: 4 }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "#1a1a18" }}>Require all conditions</div>
                  <div style={{ fontSize: 10, color: "#bbb" }}>{allReq ? "AND" : "OR"} logic</div>
                </div>
                <div onClick={() => setAllReq(!allReq)} style={{ width: 36, height: 20, borderRadius: 99, background: allReq ? "#1D9E75" : "#ccc", position: "relative", cursor: "pointer", transition: "0.2s" }}>
                  <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#fff", position: "absolute", top: 3, left: allReq ? 19 : 3, transition: "0.2s" }} />
                </div>
              </div>

              <div style={{ marginTop: 12, padding: "10px 14px", background: "#fff", borderRadius: 10, border: "1px solid #e5e3de" }}>
                <div style={{ fontSize: 10, fontWeight: 500, color: "#ccc", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Query preview</div>
                <div style={{ fontSize: 10, fontFamily: "monospace", color: "#999", lineHeight: 1.6, wordBreak: "break-all" }}>{buildQuery(conds, allReq) || "(empty)"}</div>
              </div>
            </div>

            <div style={{ width: 280, flexShrink: 0, position: "sticky", top: 20 }}>
              <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e5e3de", padding: 14, marginBottom: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: "#1a1a18", marginBottom: 10 }}>Data source</div>
                <input ref={fileRef} type="file" accept=".csv" onChange={handleFile} style={{ display: "none" }} />
                <button onClick={() => fileRef.current?.click()} style={{ width: "100%", padding: 10, borderRadius: 8, fontSize: 12, border: "1px dashed #d4d2cc", background: "transparent", color: papers.length ? "#1D9E75" : "#999", cursor: "pointer", fontFamily: "inherit" }}>
                  {papers.length ? `${papers.length} papers loaded` : "Upload CSV file"}
                </button>
                {papers.length > 0 && <div style={{ fontSize: 10, color: "#ccc", marginTop: 4 }}>Cols: {Object.keys(papers[0]).slice(0, 5).join(", ")}{Object.keys(papers[0]).length > 5 ? "..." : ""}</div>}
              </div>

              <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e5e3de", padding: 14, marginBottom: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: "#1a1a18", marginBottom: 10 }}>API settings</div>
                {F("API key", apiKey, setApiKey, "password", "sk-...")}
                {F("Base URL", baseUrl, setBaseUrl)}
                {F("Model", model, setModel)}
                {F("Temperature", temp, setTemp, "number")}
              </div>

              {err && <div style={{ padding: "6px 10px", borderRadius: 6, background: "#FCEBEB", color: "#791F1F", fontSize: 11, marginBottom: 10 }}>{err}</div>}

              <button onClick={running ? () => { stopRef.current = true; } : run} style={{ width: "100%", padding: 11, borderRadius: 8, fontSize: 13, fontWeight: 500, border: "none", background: running ? "#E24B4A" : "#1a1a18", color: "#fff", cursor: "pointer", fontFamily: "inherit" }}>
                {running ? `Stop (${progress}/${papers.length})` : "Run filter"}
              </button>
              {running && (
                <div style={{ marginTop: 6, height: 3, background: "#e5e3de", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${papers.length ? Math.round((progress / papers.length) * 100) : 0}%`, background: "#1D9E75", transition: "width 0.3s" }} />
                </div>
              )}
            </div>
          </div>
        )}

        {view === "results" && (
          <>
            {results.length === 0 && !running ? (
              <div style={{ textAlign: "center", padding: "80px 0", color: "#ccc" }}>
                <div style={{ fontSize: 15, marginBottom: 6 }}>No results yet</div>
                <div style={{ fontSize: 12, marginBottom: 16 }}>Configure conditions and run the filter</div>
                <button onClick={() => setView("config")} style={{ padding: "7px 18px", borderRadius: 6, fontSize: 12, border: "1px solid #ddd", background: "#fff", color: "#1a1a18", cursor: "pointer", fontFamily: "inherit" }}>Go to configure</button>
              </div>
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 16 }}>
                  {[
                    { l: "Screened", v: results.length, c: "#1a1a18" },
                    { l: "Relevant", v: relCount, c: "#1D9E75" },
                    { l: "Irrelevant", v: irrCount, c: "#888" },
                    { l: "Hit rate", v: `${pct}%`, c: "#534AB7" },
                  ].map((s, i) => (
                    <div key={i} style={{ background: "#fff", borderRadius: 8, border: "1px solid #e5e3de", padding: "12px 14px" }}>
                      <div style={{ fontSize: 10, color: "#bbb", marginBottom: 3 }}>{s.l}</div>
                      <div style={{ fontSize: 20, fontWeight: 500, color: s.c, fontFamily: "'Newsreader', Georgia, serif" }}>{s.v}</div>
                    </div>
                  ))}
                </div>

                {running && (
                  <div style={{ marginBottom: 12, padding: "8px 14px", background: "#fff", borderRadius: 8, border: "1px solid #e5e3de", display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ flex: 1, height: 3, background: "#e5e3de", borderRadius: 2, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${papers.length ? Math.round((progress / papers.length) * 100) : 0}%`, background: "#1D9E75", transition: "width 0.3s" }} />
                    </div>
                    <span style={{ fontSize: 11, color: "#999" }}>{progress}/{papers.length}</span>
                    <button onClick={() => { stopRef.current = true; }} style={{ padding: "3px 10px", borderRadius: 5, fontSize: 11, border: "1px solid #F09595", background: "#FCEBEB", color: "#791F1F", cursor: "pointer", fontFamily: "inherit" }}>Stop</button>
                  </div>
                )}

                <div style={{ display: "flex", gap: 6, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
                  {[
                    { k: "all", label: `All (${results.length})`, ac: "#1a1a18", abg: "#1a1a18", atx: "#fff" },
                    { k: "relevant", label: `Relevant (${relCount})`, ac: "#5DCAA5", abg: "#E1F5EE", atx: "#085041" },
                    { k: "irrelevant", label: `Irrelevant (${irrCount})`, ac: "#d4d2cc", abg: "#F1EFE8", atx: "#666" },
                  ].map(f => (
                    <button key={f.k} onClick={() => setFilt(f.k)} style={{ padding: "4px 12px", borderRadius: 99, fontSize: 11, border: `1px solid ${filt === f.k ? f.ac : "#ddd"}`, background: filt === f.k ? f.abg : "#fff", color: filt === f.k ? f.atx : "#999", cursor: "pointer", fontFamily: "inherit" }}>{f.label}</button>
                  ))}
                  <div style={{ flex: 1 }} />
                  <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." style={{ width: 170, height: 28, padding: "0 8px", borderRadius: 5, fontSize: 11, border: "1px solid #ddd", background: "#fff", color: "#1a1a18", fontFamily: "inherit", outline: "none" }} />
                  <button onClick={downloadCSV} style={{ height: 28, padding: "0 12px", borderRadius: 5, fontSize: 11, border: "1px solid #ddd", background: "#fff", color: "#666", cursor: "pointer", fontFamily: "inherit" }}>Export CSV</button>
                </div>

                <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e5e3de", overflow: "hidden" }}>
                  <div style={{ padding: "8px 14px", borderBottom: "1px solid #eceae5", display: "flex", justifyContent: "space-between", fontSize: 10, color: "#ccc", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    <span>Paper</span><span>Status</span>
                  </div>
                  {filtered.length === 0 ? (
                    <div style={{ padding: "40px 0", textAlign: "center", color: "#ddd", fontSize: 12 }}>No papers match</div>
                  ) : filtered.map((p, i) => {
                    const rel = p._j === "True";
                    const isExp = expanded === i;
                    return (
                      <div key={i} onClick={() => setExpanded(isExp ? null : i)} style={{ padding: "10px 14px", borderBottom: "1px solid #f0eee9", cursor: "pointer", background: isExp ? "#fafaf8" : "transparent", transition: "background 0.1s" }}>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                          <span style={{ fontSize: 10, color: "#ccc", width: 24, textAlign: "right", flexShrink: 0, paddingTop: 2 }}>{i + 1}</span>
                          <span style={{ width: 7, height: 7, borderRadius: "50%", background: rel ? "#1D9E75" : "#ddd", flexShrink: 0, marginTop: 4 }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 12, fontWeight: 500, color: "#1a1a18", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: isExp ? "normal" : "nowrap" }}>{p.title || "(no title)"}</div>
                            {isExp && (
                              <div style={{ marginTop: 6 }}>
                                {p.summary && <p style={{ fontSize: 11, color: "#777", lineHeight: 1.6, margin: "0 0 6px" }}>{p.summary.length > 500 ? p.summary.slice(0, 500) + "..." : p.summary}</p>}
                                <div style={{ display: "flex", gap: 10, fontSize: 10, color: "#bbb", flexWrap: "wrap" }}>
                                  {p.published && <span>Published: {p.published}</span>}
                                  {p.link && <a href={p.link} target="_blank" rel="noreferrer" style={{ color: "#534AB7" }} onClick={e => e.stopPropagation()}>Source</a>}
                                  {p._r && <span style={{ color: "#ccc" }}>Reason: {p._r}</span>}
                                </div>
                              </div>
                            )}
                          </div>
                          <span style={{ fontSize: 10, fontWeight: 500, padding: "2px 8px", borderRadius: 99, flexShrink: 0, background: rel ? "#E1F5EE" : "#F1EFE8", color: rel ? "#085041" : "#999", border: `1px solid ${rel ? "#5DCAA5" : "#ddd"}` }}>
                            {rel ? "relevant" : "irrelevant"}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div style={{ marginTop: 6, fontSize: 10, color: "#ccc", textAlign: "right" }}>{filtered.length} of {results.length} shown</div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
