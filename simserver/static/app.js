/* implementation_sim -- three-pane workbench over the local bundle service. */

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

const api = async (path, options = {}) => {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error("request failed"), { body, status: res.status });
  return body;
};

const state = {
  bundle: null,
  attempt: null,
  editor: null,
  dirty: false,
  saveTimer: null,
  elapsed: 0,
  activeUnit: null,
  lastReport: null,
  unitStatus: {},
  codeHash: null,
  focus: null,      // the function the whole workbench is pointed at
  resultsByTarget: {},  // latest result per function, across runs
  lastRun: null,
};

/* ---------------- markdown ---------------- */

marked.setOptions({ gfm: true, breaks: false });

function renderMarkdown(node, text) {
  node.innerHTML = marked.parse(text || "");
  try {
    renderMathInElement(node, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
      ],
      throwOnError: false,
    });
  } catch (e) { /* math is a nicety, never a blocker */ }
}

/* ---------------- library screen ---------------- */

async function showLibrary() {
  $("#workbench").classList.add("hidden");
  $("#library").classList.remove("hidden");
  const { bundles, home } = await api("/api/bundles");
  $("#home-path").textContent = `Everything is stored under ${home}`;
  const list = $("#bundle-list");
  list.innerHTML = "";
  if (!bundles.length) {
    list.append(el("div", "empty", "No bundles yet. Import one to begin."));
  }
  for (const b of bundles) {
    const card = el("div", "bundle-card" + (b.ok ? "" : " broken"));
    const left = el("div");
    left.append(el("h3", null, b.title));
    left.append(el("div", "muted small",
      b.ok ? `${b.units} functions · ${b.pipeline_cases} pipeline cases` +
             (b.estimated_minutes ? ` · ~${b.estimated_minutes} min` : "")
           : "invalid bundle"));
    card.append(left);
    card.append(el("div", "muted small", b.source || ""));
    if (b.ok) card.onclick = () => openBundle(b.id);
    else card.onclick = () => showProblems(b.problems || []);
    list.append(card);
  }
}

function showProblems(problems) {
  const box = $("#import-problems");
  box.classList.remove("hidden");
  box.textContent = problems.join("\n");
}

$("#import-zip-btn").onclick = () => $("#import-zip").click();
$("#import-zip").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/bundles/import", { method: "POST", body: form });
  const body = await res.json();
  if (!res.ok) return showProblems(body.problems || [JSON.stringify(body)]);
  $("#import-problems").classList.add("hidden");
  showLibrary();
};
$("#import-path-btn").onclick = async () => {
  const path = $("#import-path").value.trim();
  if (!path) return;
  try {
    await api("/api/bundles/import-path", { method: "POST", body: JSON.stringify({ path }) });
    $("#import-problems").classList.add("hidden");
    showLibrary();
  } catch (err) {
    showProblems(err.body?.problems || ["import failed"]);
  }
};
$("#back").onclick = () => { saveNow(); showLibrary(); };

/* ---------------- workbench ---------------- */

async function openBundle(bundleId) {
  state.bundle = await api(`/api/bundles/${bundleId}`);
  const attempt = await api(`/api/bundles/${bundleId}/attempts/latest`);
  $("#library").classList.add("hidden");
  $("#workbench").classList.remove("hidden");
  $("#bundle-title").textContent = state.bundle.title;
  $("#bundle-source").textContent = state.bundle.source || "practice";
  renderDocs();
  await loadAttempt(attempt);
  await refreshAttemptList();
  renderUnits();
}

async function loadAttempt(attempt) {
  state.attempt = attempt;
  state.unitStatus = attempt.unit_status || {};
  state.codeHash = attempt.code_hash || null;
  state.resultsByTarget = attempt.last_results || {};
  state.elapsed = attempt.elapsed_seconds || 0;
  tickTimer();
  await ensureEditor();
  state.editor.setValue(attempt.code);
  state.editor.setScrollTop(0);
  markSaved();
  renderUnits();
  renderHistory(attempt.history || []);
  $("#run-summary").innerHTML = "";
  $("#unit-list").classList.remove("blocked");
  state.lastRun = null;
  state.focus = null;
  state.activeUnit = null;
  renderRightPanel();
}

async function refreshAttemptList() {
  const { attempts } = await api(`/api/bundles/${state.bundle.id}/attempts`);
  const sel = $("#attempt-select");
  sel.innerHTML = "";
  for (const a of attempts) {
    const opt = el("option", null, a.attempt_id.replace("T", "  "));
    opt.value = a.attempt_id;
    sel.append(opt);
  }
  sel.value = state.attempt.attempt_id;
}

$("#attempt-select").onchange = async (e) => {
  saveNow();
  const a = await api(`/api/bundles/${state.bundle.id}/attempts/${e.target.value}`);
  loadAttempt(a);
};
$("#new-attempt").onclick = async () => {
  if (!confirm("Start a new attempt? Your current one stays on disk.")) return;
  saveNow();
  const a = await api(`/api/bundles/${state.bundle.id}/attempts`, { method: "POST" });
  await loadAttempt({ ...a, history: [] });
  await refreshAttemptList();
};

/* ---------------- docs pane ---------------- */

function renderDocs() {
  const nav = $("#doc-nav");
  nav.innerHTML = "";
  state.bundle.docs.forEach((doc, i) => {
    const b = el("button", i === 0 ? "active" : "", doc.title);
    b.onclick = () => {
      [...nav.children].forEach((c) => c.classList.remove("active"));
      b.classList.add("active");
      renderMarkdown($("#doc-body"), doc.markdown);
      $("#doc-body").scrollTop = 0;
    };
    nav.append(b);
  });
  renderMarkdown($("#doc-body"), state.bundle.docs[0]?.markdown || "");
}

/* ---------------- functions pane ---------------- */

function unitStatusClass(id) {
  const s = state.unitStatus[id];
  if (!s || !s.total) return "";          // not run
  return s.passed === s.total ? "pass" : "fail";
}

function renderUnits() {
  const list = $("#unit-list");
  list.innerHTML = "";
  let group = null;
  for (const u of state.bundle.units) {
    if (u.group !== group) {
      group = u.group;
      list.append(el("div", "unit-group", group || "functions"));
    }
    list.append(unitRow(u.id, u.id, u.case_count, false));
  }
  const ep = state.bundle.entrypoint;
  list.append(unitRow(ep, ep, state.bundle.pipeline.case_count, true));
}

function unitRow(id, label, caseCount, isPipeline) {
  const row = el("div", `unit ${unitStatusClass(id)}${isPipeline ? " pipeline" : ""}` +
    (state.activeUnit === id ? " active" : ""));
  row.append(el("span", "dot"));
  row.append(el("span", "name", label));
  const s = state.unitStatus[id];
  row.append(el("span", "count", s && s.total ? `${s.passed}/${s.total}` : `${caseCount}`));
  row.onclick = () => selectUnit(id, isPipeline, { jump: true });
  return row;
}

function selectUnit(id, isPipeline, opts = {}) {
  const { jump = true, scrollList = false } = opts;
  state.activeUnit = id;
  state.focus = id;
  renderUnits();
  if (scrollList) {
    const row = [...$("#unit-list").querySelectorAll(".unit")]
      .find((r) => r.querySelector(".name").textContent === id);
    if (row) row.scrollIntoView({ block: "nearest" });
  }
  renderRightPanel();
  const spec = $("#unit-spec");
  spec.innerHTML = "";
  if (isPipeline) {
    renderMarkdown(spec, `# \`${id}\`\n\nThe whole router, end to end. Reads one command per ` +
      `line and returns one string per command.\n\nThis is what actually has to work — the ` +
      `function tests only tell you the pieces are sound.`);
    switchLeftTab("functions");
    if (jump) jumpToDefinition(id);
    return;
  }
  const u = state.bundle.units.find((x) => x.id === id);
  if (!u) return;
  const sig = el("div", "sig", u.signature);
  renderMarkdown(spec, u.spec_md || `# \`${u.id}\`\n\n${u.summary}`);
  spec.prepend(sig);
  if (u.depends_on.length) {
    const deps = el("div", "deps");
    deps.append(document.createTextNode("builds on: "));
    u.depends_on.forEach((d, i) => {
      if (i) deps.append(document.createTextNode(", "));
      const code = el("code", null, d);
      code.style.cursor = "pointer";
      code.onclick = () => selectUnit(d, false, { scrollList: true });
      deps.append(code);
    });
    spec.insertBefore(deps, spec.children[2] || null);
  }
  spec.scrollTop = 0;
  switchLeftTab("functions");
  if (jump) jumpToDefinition(id);
}

function switchLeftTab(name) {
  document.querySelectorAll("[data-tab]").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name));
  $("#tab-problem").classList.toggle("hidden", name !== "problem");
  $("#tab-functions").classList.toggle("hidden", name !== "functions");
}
document.querySelectorAll("[data-tab]").forEach((t) => {
  t.onclick = () => switchLeftTab(t.dataset.tab);
});
document.querySelectorAll("[data-rtab]").forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll("[data-rtab]").forEach((x) =>
      x.classList.toggle("active", x === t));
    ["results", "console", "history"].forEach((n) =>
      $(`#rtab-${n}`).classList.toggle("hidden", n !== t.dataset.rtab));
  };
});

/* ---------------- editor ---------------- */

function ensureEditor() {
  if (state.editor) return Promise.resolve();
  return new Promise((resolve) => {
    require.config({ paths: { vs: "/static/vendor/vs" } });
    require(["vs/editor/editor.main"], () => {
      monaco.editor.defineTheme("sim", {
        base: "vs-dark", inherit: true, rules: [],
        colors: { "editor.background": "#0f1115", "editorGutter.background": "#0f1115" },
      });
      state.editor = monaco.editor.create($("#editor"), {
        value: "", language: "python", theme: "sim",
        fontSize: 13, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        minimap: { enabled: false }, automaticLayout: true,
        tabSize: 4, insertSpaces: true, renderWhitespace: "selection",
        scrollBeyondLastLine: true, rulers: [100],
      });
      state.editor.onDidChangeModelContent(() => markDirty());
      state.editor.onDidChangeCursorPosition(() => {
        updateEditorHint();
        syncSelectionToCursor();
      });
      state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runCurrent());
      state.editor.addCommand(
        monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.Enter,
        () => run("pipeline"));
      state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => saveNow());
      resolve();
    });
  });
}

function enclosingFunction() {
  if (!state.editor) return null;
  const line = state.editor.getPosition().lineNumber;
  const lines = state.editor.getValue().split("\n");
  for (let i = line - 1; i >= 0; i--) {
    const m = /^def\s+([A-Za-z_][A-Za-z0-9_]*)/.exec(lines[i] || "");
    if (m) return m[1];
  }
  return null;
}

function syncSelectionToCursor() {
  const fn = enclosingFunction();
  if (!fn || fn === state.activeUnit) return;
  const isUnit = state.bundle.units.some((u) => u.id === fn);
  const isPipeline = fn === state.bundle.entrypoint;
  if (!isUnit && !isPipeline) return;
  // the cursor is the source of truth here, so never move it back
  selectUnit(fn, isPipeline, { jump: false, scrollList: true });
}

function updateEditorHint() {
  const fn = enclosingFunction();
  const known = fn && (state.bundle.units.some((u) => u.id === fn) ||
                       fn === state.bundle.entrypoint);
  $("#editor-hint").textContent = known
    ? `⌘↵ runs ${fn}`
    : (fn ? `${fn} — no tests for this name` : "⌘↵ runs the function your cursor is in");
}

function jumpToDefinition(name) {
  if (!state.editor) return;
  const lines = state.editor.getValue().split("\n");
  const idx = lines.findIndex((l) => new RegExp(`^def\\s+${name}\\s*\\(`).test(l));
  if (idx < 0) return;
  state.editor.revealLineInCenter(idx + 1);
  state.editor.setPosition({ lineNumber: idx + 1, column: 1 });
}

/* ---------------- saving ---------------- */

function markDirty() {
  state.dirty = true;
  $("#save-state").textContent = "unsaved";
  $("#save-state").classList.add("dirty");
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(saveNow, 800);
}

function markSaved() {
  state.dirty = false;
  $("#save-state").textContent = "saved";
  $("#save-state").classList.remove("dirty");
}

async function saveNow() {
  if (!state.attempt || !state.editor || !state.dirty) return;
  const code = state.editor.getValue();
  await api(`/api/bundles/${state.bundle.id}/attempts/${state.attempt.attempt_id}/code`,
    { method: "PUT", body: JSON.stringify({ code }) });
  markSaved();
}
window.addEventListener("beforeunload", () => { if (state.dirty) saveNow(); });

/* ---------------- timer ---------------- */

function tickTimer() {
  const m = String(Math.floor(state.elapsed / 60)).padStart(2, "0");
  const s = String(state.elapsed % 60).padStart(2, "0");
  $("#timer").textContent = `${m}:${s}`;
}
setInterval(() => {
  if (!state.attempt || $("#workbench").classList.contains("hidden")) return;
  state.elapsed += 1;
  tickTimer();
  if (state.elapsed % 30 === 0) {
    api(`/api/bundles/${state.bundle.id}/attempts/${state.attempt.attempt_id}/heartbeat`,
      { method: "POST", body: JSON.stringify({ elapsed_seconds: state.elapsed }) })
      .catch(() => {});
  }
}, 1000);

/* ---------------- running ---------------- */

$("#run-unit").onclick = () => runCurrent();
$("#run-pipeline").onclick = () => run("pipeline");
$("#run-all").onclick = () => run("all");

function runCurrent() {
  const fn = enclosingFunction();
  if (fn && fn === state.bundle.entrypoint) return run("pipeline");
  if (fn && state.bundle.units.some((u) => u.id === fn)) return run(fn);
  if (state.activeUnit) {
    return run(state.activeUnit === state.bundle.entrypoint ? "pipeline" : state.activeUnit);
  }
  return run("all");
}

async function run(selection) {
  if (!state.attempt) return;
  const summary = $("#run-summary");
  summary.innerHTML = "";
  summary.append(el("span", "pill neutral", `running ${selection}…`));
  try {
    const result = await api(
      `/api/bundles/${state.bundle.id}/attempts/${state.attempt.attempt_id}/run`,
      { method: "POST", body: JSON.stringify({ selection, code: state.editor.getValue() }) });
    markSaved();
    state.unitStatus = result.unit_status || {};
    state.codeHash = result.code_hash || null;
    state.resultsByTarget = result.last_results || state.resultsByTarget;
    state.lastReport = result;
    renderUnits();
    renderResults(result);
    const { history } = await api(
      `/api/bundles/${state.bundle.id}/attempts/${state.attempt.attempt_id}/runs`);
    renderHistory(history);
  } catch (err) {
    summary.innerHTML = "";
    summary.append(el("span", "pill fail", "run failed"));
    $("#rtab-results").innerHTML = "";
    $("#rtab-results").append(el("div", "fatal", JSON.stringify(err.body || err.message)));
  }
}

/** Python-style repr, so previewed cases read the way the runner reports them. */
function pyRepr(v, given) {
  if (typeof v === "string" && v.startsWith("$given.") && given) {
    return pyRepr(given[v.split(".", 2)[1]], null);
  }
  if (v === null || v === undefined) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") return `'${v.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
  if (Array.isArray(v)) return `[${v.map((x) => pyRepr(x, given)).join(", ")}]`;
  return `{${Object.entries(v).map(([k, x]) => `'${k}': ${pyRepr(x, given)}`).join(", ")}}`;
}

function casesFor(id) {
  if (id === state.bundle.entrypoint) return state.bundle.pipeline.cases || [];
  const u = state.bundle.units.find((x) => x.id === id);
  return u ? u.cases || [] : [];
}

/** The tests for a function we have not run yet: what will be asked of it. */
function renderCasePreview(id) {
  const block = el("div", "target-block");
  const head = el("div", "target-head");
  head.append(el("span", "name", id));
  head.append(el("span", "pill neutral", `${casesFor(id).length} cases`));
  block.append(head);
  block.append(el("div", "target-note", "Not run against your current code yet."));
  for (const c of casesFor(id)) {
    const node = el("div", "case preview");
    const chead = el("div", "case-head");
    chead.append(el("span", "status", "—"));
    chead.append(el("span", "cid", c.id));
    (c.tags || []).filter((t) => t === "trap").forEach(() =>
      chead.append(el("span", "tag trap", "trap")));
    node.append(chead);
    const body = el("div", "case-body hidden");
    if (c.why) body.append(el("div", "why", c.why));
    body.append(el("div", "call",
      `${id}(${(c.args || []).map((a) => pyRepr(a, c.given)).join(", ")})`));
    const check = el("div", "check");
    check.append(el("div", "label", "expects"));
    const grid = el("div", "ev");
    grid.append(el("span", "k", "returns"));
    grid.append(el("span", "v same",
      c.expect.match === "is_none" ? "None" : pyRepr(c.expect.returns, null)));
    if (c.expect.state) {
      grid.append(el("span", "k", "state"));
      grid.append(el("span", "v same", pyRepr(c.expect.state, null)));
    }
    check.append(grid);
    body.append(check);
    chead.onclick = () => body.classList.toggle("hidden");
    node.append(body);
    block.append(node);
  }
  return block;
}

/** The header always describes exactly what is listed below it. */
function renderSummaryBar() {
  const bar = $("#run-summary");
  bar.innerHTML = "";
  const report = state.lastRun ? state.lastRun.report : null;
  const blocked = Boolean(report && (report.import_error || report.fatal));

  let pill, label, passed = 0, total = 0, tone = "neutral";

  if (state.focus) {
    const t = (report?.targets || []).find((x) => x.target === state.focus)
            || state.resultsByTarget[state.focus];
    label = state.focus;
    if (blocked) {
      pill = "nothing ran — file could not load";
      tone = "fail";
    } else if (!t || t.status === "not_implemented") {
      pill = t ? "not written yet" : `${casesFor(state.focus).length} cases · not run`;
    } else {
      passed = t.passed || 0;
      total = t.total || 0;
      pill = `${passed}/${total} passing`;
      tone = passed === total && total ? "pass" : "fail";
    }
  } else if (blocked) {
    pill = "nothing ran — file could not load";
    tone = "fail";
    label = state.lastRun.selection;
  } else if (report) {
    const s = state.lastRun.summary;
    passed = s.passed;
    total = s.total;
    pill = total ? `${passed}/${total} passing` : "nothing ran";
    tone = total && s.failed === 0 ? "pass" : total ? "fail" : "neutral";
    label = state.lastRun.selection;
  } else {
    pill = "no runs yet";
    label = "";
  }

  bar.append(el("span", `pill ${tone}`, pill));
  const track = el("div", "bar");
  const fill = el("i");
  fill.style.width = total ? `${(passed / total) * 100}%` : "0%";
  fill.style.background = tone === "pass" ? "var(--pass)" : "var(--fail)";
  track.append(fill);
  bar.append(track);
  bar.append(el("span", "muted small", label || ""));
  if (state.focus) {
    const all = el("button", "btn ghost small", "show all");
    all.onclick = () => {
      state.focus = null;
      state.activeUnit = null;
      renderUnits();
      renderRightPanel();
    };
    bar.append(all);
  }
}

/** Results tab = whatever the workbench is pointed at right now. */
function renderRightPanel() {
  renderSummaryBar();
  const body = $("#rtab-results");
  body.innerHTML = "";
  const report = state.lastRun ? state.lastRun.report : null;

  if (state.focus) {
    const t = (report?.targets || []).find((x) => x.target === state.focus)
            || state.resultsByTarget[state.focus];
    if (t) {
      body.append(renderTarget(t));
    } else {
      body.append(renderCasePreview(state.focus));
    }
    return;
  }

  if (!report) {
    body.append(el("div", "empty", "Run something, or pick a function to see its tests."));
    return;
  }
  if (report.fatal) body.append(el("div", "fatal", report.fatal));
  if (report.import_error) body.append(importErrorBox(report.import_error));
  for (const t of report.targets || []) body.append(renderTarget(t));
}

function importErrorBox(err) {
  const box = el("div", "fatal");
  box.append(el("div", null, `Your file could not be loaded: ${err.type}: ${err.message}`));
  if (err.line) {
    const jump = el("div", "trace");
    const a = el("span", "jump", `go to line ${err.line}`);
    a.onclick = () => gotoLine(err.line);
    jump.append(a);
    box.append(jump);
  }
  return box;
}

function renderResults(result) {
  state.lastRun = result;
  const { report } = result;
  $("#unit-list").classList.toggle("blocked",
    Boolean(report.import_error || report.fatal));

  // a single-function run points the whole workbench at that function
  if (result.selection && result.selection !== "all" && result.selection !== "pipeline") {
    state.focus = result.selection;
    state.activeUnit = result.selection;
  } else if (result.selection === "all") {
    state.focus = null;
  } else if (result.selection === "pipeline") {
    state.focus = state.bundle.entrypoint;
    state.activeUnit = state.bundle.entrypoint;
  }
  renderUnits();
  renderRightPanel();

  const console_ = $("#rtab-console");
  console_.innerHTML = "";
  const chunks = [];
  if (report.import_output) chunks.push(`[import]\n${report.import_output}`);
  for (const t of report.targets || []) {
    for (const r of t.results || []) {
      if (r.stdout) chunks.push(`[${t.target} / ${r.case_id}]\n${r.stdout}`);
    }
  }
  if (report.stderr) chunks.push(`[stderr]\n${report.stderr}`);
  if (!chunks.length) console_.append(el("div", "empty", "No output. Add print() calls to debug."));
  else console_.append(el("pre", "stdout", chunks.join("\n\n")));
}

function renderTarget(t) {
  const block = el("div", "target-block");
  const head = el("div", "target-head");
  const passed = t.passed || 0, total = t.total || 0;
  head.append(el("span", "name", t.target));
  if (t.status === "not_implemented") {
    head.append(el("span", "pill neutral", "not written yet"));
    block.append(head);
    block.append(el("div", "target-note", t.message || ""));
    return block;
  }
  head.append(el("span", `pill ${passed === total && total ? "pass" : "fail"}`,
    `${passed}/${total}`));
  block.append(head);
  for (const r of t.results || []) block.append(renderCase(r));
  return block;
}

function renderCase(r) {
  const node = el("div", `case ${r.status}`);
  const head = el("div", "case-head");
  head.append(el("span", "status", r.status === "pass" ? "pass" : r.status));
  head.append(el("span", "cid", r.case_id));
  (r.tags || []).filter((x) => x === "trap").forEach(() =>
    head.append(el("span", "tag trap", "trap")));
  head.append(el("span", "ms", `${r.duration_ms}ms`));
  node.append(head);

  const body = el("div", "case-body hidden");
  if (r.why) body.append(el("div", "why", r.why));
  if (r.call) body.append(el("div", "call", r.call));

  for (const c of r.checks || []) {
    const check = el("div", "check");
    check.append(el("div", "label", c.label + (c.match && c.match !== "equal" ? ` (${c.match})` : "")));
    const grid = el("div", "ev");
    grid.append(el("span", "k", "expected"));
    grid.append(el("span", `v ${c.ok ? "same" : "want"}`,
      c.expected_repr ?? JSON.stringify(c.expected)));
    grid.append(el("span", "k", "actual"));
    grid.append(el("span", `v ${c.ok ? "same" : "got"}`,
      c.actual_repr ?? JSON.stringify(c.actual)));
    check.append(grid);
    body.append(check);
  }

  if (r.error) {
    const trace = el("div", "trace");
    trace.append(document.createTextNode(`${r.error.type}: ${r.error.message}\n`));
    (r.error.frames || []).forEach((f) => trace.append(document.createTextNode(f + "\n")));
    if (r.error.line) {
      const a = el("span", "jump", `go to line ${r.error.line}`);
      a.onclick = () => gotoLine(r.error.line);
      trace.append(a);
    }
    body.append(trace);
  }
  if (r.stdout) body.append(el("pre", "stdout", r.stdout));

  head.onclick = () => body.classList.toggle("hidden");
  if (r.status !== "pass") body.classList.remove("hidden");
  node.append(body);
  return node;
}

function gotoLine(line) {
  if (!state.editor) return;
  state.editor.revealLineInCenter(line);
  state.editor.setPosition({ lineNumber: line, column: 1 });
  state.editor.focus();
}

function renderHistory(history) {
  const body = $("#rtab-history");
  body.innerHTML = "";
  if (!history || !history.length) {
    body.append(el("div", "empty", "No runs yet."));
    return;
  }
  for (const h of history) {
    const row = el("div", "history-row");
    const ok = h.summary.total && h.summary.failed === 0;
    row.append(el("span", `pill ${ok ? "pass" : "fail"}`,
      `${h.summary.passed}/${h.summary.total}`));
    row.append(el("span", "sel", h.selection));
    row.append(el("span", "muted small", h.at.slice(11, 19)));
    row.onclick = async () => {
      const detail = await api(
        `/api/bundles/${state.bundle.id}/attempts/${state.attempt.attempt_id}/runs/${h.run_id}`);
      renderResults({ summary: detail.summary, report: detail.report,
                      selection: detail.selection });
      document.querySelector('[data-rtab="results"]').click();
    };
    body.append(row);
  }
}

/* ---------------- pane resizing ---------------- */

document.querySelectorAll(".gutter").forEach((g) => {
  g.addEventListener("mousedown", (down) => {
    const side = g.dataset.resize;
    const pane = document.querySelector(side === "left" ? ".pane.left" : ".pane.right");
    const startX = down.clientX;
    const startW = pane.getBoundingClientRect().width;
    const move = (e) => {
      const delta = side === "left" ? e.clientX - startX : startX - e.clientX;
      pane.style.width = `${Math.max(220, Math.min(900, startW + delta))}px`;
    };
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
    down.preventDefault();
  });
});

showLibrary();
