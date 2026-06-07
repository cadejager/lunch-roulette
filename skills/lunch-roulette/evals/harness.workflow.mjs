// ===========================================================================
// lunch-roulette eval harness — a Claude Code WORKFLOW (not a node script)
// ===========================================================================
//
// HOW TO RUN: this file is executed by the Claude Code **Workflow tool**, which
// drives a small multi-agent orchestration. It is NOT runnable with `node`,
// `pytest`, or any plain runtime — the hooks below (`agent`, `pipeline`,
// `parallel`, `phase`, `log`, `args`) are injected by the Workflow runtime, and
// `node`-isms like `Date.now()`/`Math.random()`/`fs` will throw. We need an LLM
// orchestration because Layer 2/3 are *LLM* evals: each one dry-runs an agent
// against a stubbed world (state supplied inline under `setup.state`), then an
// LLM **judge** grades the output against the eval's `assertions`. (Layer 1 — the
// deterministic matcher/timezone/scheduling math — stays in
// `python3 scripts/test_*.py`; this harness never re-tests it.)
//
// Invoke from the REPO ROOT, e.g.:
//
//   // report-only (default): grade everything, print a pass/fail table, edit nothing
//   Workflow({ scriptPath: "skills/lunch-roulette/evals/harness.workflow.mjs" })
//
//   // re-sample for a pass-rate (single LLM runs vary — see the README)
//   Workflow({ scriptPath: "skills/lunch-roulette/evals/harness.workflow.mjs",
//              args: { samples: 3 } })
//
//   // opt-in AUTO-FIX loop: grade -> diagnose each failure -> fix the right file -> repeat
//   Workflow({ scriptPath: "skills/lunch-roulette/evals/harness.workflow.mjs",
//              args: { fix: true, maxRounds: 3 } })
//
// SAFETY — auto-fix edits the WORKING TREE: the diagnose-and-fix agents are NOT
// worktree-isolated; they edit files in the Workflow's cwd in place so the next
// round's produce step reads the change. So run `fix:true` on a dedicated branch
// and open a PR for review — the harness never pushes or opens a PR itself. The
// fixer DIAGNOSES root cause (is the eval *assertion* wrong, or is the *plugin*
// spec/script wrong?) and FLAGS rather than forcing ambiguous cases green; it
// will never mangle correct behavior just to turn an assertion green.
//
// args (all optional): { samples = 1, fix = false, maxRounds = 3 }
// ===========================================================================

export const meta = {
  name: 'lunch-eval-harness',
  description: 'Dry-run + judge-grade the lunch-roulette LLM evals (messenger/orchestrator/integration); report a pass/fail table, or run an opt-in diagnose-and-fix loop',
  phases: [
    { title: 'Load', detail: 'read the 3 eval files into one flat list' },
    { title: 'Grade', detail: 'per eval: dry-run produce -> strict LLM judge (x samples)' },
    { title: 'Fix', detail: 'opt-in: diagnose each failure (eval-bug vs plugin-bug) and fix the right file, looping until green or maxRounds' },
  ],
}

// --- options (args may be undefined when run with no args) -----------------
const opts = args || {}
const SAMPLES = Math.max(1, Number(opts.samples) || 1)
const FIX = opts.fix === true
const MAX_ROUNDS = Math.max(1, Number(opts.maxRounds) || 3)

// The three Layer-2/3 eval files, each: { target, evals:[{id,name,intent,setup,prompt,assertions}] }
const EVAL_FILES = [
  'skills/lunch-roulette/evals/messenger.json',
  'skills/lunch-roulette/evals/orchestrator.json',
  'skills/lunch-roulette/evals/integration.json',
]

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const LOAD_SCHEMA = {
  type: 'object', required: ['evals'],
  properties: { evals: { type: 'array', items: {
    type: 'object', required: ['id', 'target', 'prompt', 'assertions'],
    properties: {
      id: { type: 'string' }, target: { type: 'string' },
      prompt: { type: 'string' },
      assertions: { type: 'array', items: { type: 'string' } },
      setup: { type: 'object', additionalProperties: true },
    },
  } } },
}

const JUDGE_SCHEMA = {
  type: 'object', required: ['id', 'overall_pass', 'assertion_results'],
  properties: {
    id: { type: 'string' }, overall_pass: { type: 'boolean' },
    assertion_results: { type: 'array', items: {
      type: 'object', required: ['assertion', 'pass'],
      properties: { assertion: { type: 'string' }, pass: { type: 'boolean' }, note: { type: 'string' } },
    } },
    summary: { type: 'string' },
  },
}

// The fixer must commit to exactly one action; `file`/`detail` document what it did (or why it punted).
const FIX_SCHEMA = {
  type: 'object', required: ['action', 'detail'],
  properties: {
    action: { type: 'string', enum: ['fixed-eval', 'fixed-spec', 'flagged'] },
    file: { type: 'string' },     // path edited, or "" when flagged
    detail: { type: 'string' },   // root-cause diagnosis + what changed (or why flagged)
  },
}

// ---------------------------------------------------------------------------
// Prompts — produce (target-aware dry run) + judge (strict). Reused verbatim
// from the already-run harness that graded 20 evals 19/20.
// ---------------------------------------------------------------------------

function producePrompt(e) {
  const setup = JSON.stringify(e.setup || {}, null, 2)
  if (e.target === 'messenger') {
    return 'You are simulating the lunch-roulette **lunch-messenger** subagent in a DRY RUN (no real tools).\n' +
      'First read its operating spec in full: `agents/lunch-messenger.md`.\n' +
      'Here is the stubbed world ("setup"):\n' + setup + '\n\nInstruction: ' + e.prompt + '\n\n' +
      'Produce exactly what the messenger would: its return JSON (SYNC roster/today/asked/flagged, or the NOTIFY report) AND every message it would post (channel, thread target, text). Do NOT call any tools — REPORT what you would do, faithfully to the spec. Output the produced result as text.'
  }
  if (e.target === 'orchestrator') {
    return 'You are simulating the lunch-roulette **orchestrator** (the skill) in a DRY RUN.\n' +
      'First read its runbook: `skills/lunch-roulette/SKILL.md` (skim `skills/lunch-roulette/references/data-schemas.md` for shapes).\n' +
      'The stubbed world ("setup") provides `now`, the stored state canvases (config/participants/availability/rounds) under `setup.state`, and the messenger sync_return:\n' + setup + '\n\nInstruction: ' + e.prompt + '\n\n' +
      'You MAY run the real Python scripts in `skills/lunch-roulette/scripts/` (to_utc.py/schedule.py/pair.py/record_round.py) on the setup data — they are safe and deterministic. Do NOT call Slack or Calendar tools — REPORT what you would write/post: the availability JSON, the due pool, the groups, the exact create_event call(s) for the Google Calendar invites (per group: the attendees with optionalAttendee on the organizer, addGoogleMeetUrl, UTC start/end, calendarId, summary) — including the list_events idempotency check that precedes them — AND the Slack NOTIFY instructions: the match message(s) the messenger would post (per person: the slot in their own zone, the meeting_link when set, whether an at-slot reminder is scheduled). Output the produced result as text.'
  }
  // integration: chain messenger SYNC -> orchestrator end to end
  return 'You are simulating the lunch-roulette pipeline END-TO-END in a DRY RUN: messenger SYNC -> orchestrator.\n' +
    'Read both specs: `agents/lunch-messenger.md` and `skills/lunch-roulette/SKILL.md`.\n' +
    'The stubbed world ("setup"):\n' + setup + '\n\nInstruction: ' + e.prompt + '\n\n' +
    'First produce the messenger SYNC return from setup.channel, then feed it + setup.state + setup.now to the orchestrator and produce the availability written, due pool, groups, the exact create_event call(s) for the Google Calendar invites (attendees with optionalAttendee on the organizer, addGoogleMeetUrl, UTC start/end, calendarId, summary), and the Slack match messages posted via NOTIFY announcing the invite (with meeting_link if set and an at-slot reminder when lunch_reminder is on), plus any other posted messages. You MAY run the Python scripts (safe). Do NOT call real Slack or Calendar tools — REPORT. Output the full chain result as text.'
}

function judgePrompt(e, out) {
  return 'You are STRICTLY grading a dry-run eval for the lunch-roulette plugin. Eval id: ' + e.id + ' (target: ' + e.target + ').\n\n' +
    'The agent was asked:\n' + e.prompt + '\n\nIts produced output:\n"""\n' + out + '\n"""\n\n' +
    'Grade against each assertion below. Mark an assertion `pass` ONLY if the produced output clearly and specifically satisfies it; if it is missing, vague, or contradicted, mark it fail with a one-line note. Assertions:\n' +
    (e.assertions || []).map((a, i) => (i + 1) + '. ' + a).join('\n') +
    '\n\nReturn per-assertion results (quote each assertion) + overall_pass (true ONLY if every assertion passes) + a one-line summary. Use id="' + e.id + '".'
}

// ---------------------------------------------------------------------------
// Phase 1 — Load: one agent reads all three files into a flat list.
// ---------------------------------------------------------------------------

phase('Load')
const loaded = await agent(
  'Read these JSON eval files (use the Read tool) and return a flat list of EVERY eval across all three:\n' +
  EVAL_FILES.join('\n') +
  '\n\nEach file has a top-level "target" ("messenger" | "orchestrator" | "integration") and an "evals" array; each eval has id, name, intent, setup, prompt, assertions. For each eval, return {id, target (the file\'s top-level target), prompt, assertions, setup (the eval\'s setup object, verbatim)}. Return ALL of them via the schema.',
  { label: 'load-evals', phase: 'Load', schema: LOAD_SCHEMA }
)
const evals = loaded.evals || []
if (evals.length === 0) {
  log('No evals loaded — aborting.')
  return { total: 0, passed: 0, failed: [], all: [] }
}
const byId = new Map(evals.map((e) => [e.id, e]))
log('Loaded ' + evals.length + ' LLM evals (samples=' + SAMPLES + ', fix=' + FIX + (FIX ? ', maxRounds=' + MAX_ROUNDS : '') + ').')

// ---------------------------------------------------------------------------
// Grading. `gradeSet(subset)` grades each eval `SAMPLES` times and returns one
// row per eval: { id, target, pass (majority overall_pass), pass_rate,
// failed_assertions, summary, produced (a representative failing output for the
// fixer) }. produce has no barrier with judge (pipeline streams each item
// through both stages); each (eval, sample) is an independent pipeline item.
// ---------------------------------------------------------------------------

async function gradeSet(subset) {
  // Fan out (eval × sample) as independent items; produce -> judge per item.
  const items = []
  for (const e of subset) {
    for (let s = 0; s < SAMPLES; s++) items.push({ e, s })
  }

  const judged = await pipeline(
    items,
    // Stage 1 — produce (dry run). Keep the produced text around for the judge AND the fixer.
    ({ e, s }) =>
      agent(producePrompt(e), { label: 'produce:' + e.id + (SAMPLES > 1 ? '#' + (s + 1) : ''), phase: 'Grade' })
        .then((out) => ({ e, s, out })),
    // Stage 2 — judge (strict, schema'd).
    ({ e, s, out }) =>
      agent(judgePrompt(e, out), { label: 'judge:' + e.id + (SAMPLES > 1 ? '#' + (s + 1) : ''), phase: 'Grade', schema: JUDGE_SCHEMA })
        .then((verdict) => ({ e, out, verdict })),
  )

  // Collapse the per-sample verdicts back to one row per eval (majority vote).
  const grouped = new Map()
  for (const r of judged.filter(Boolean)) {
    if (!grouped.has(r.e.id)) grouped.set(r.e.id, [])
    grouped.get(r.e.id).push(r)
  }

  const rows = []
  for (const e of subset) {
    const samples = grouped.get(e.id) || []
    if (samples.length === 0) {
      // Both stages failed for every sample — surface as a non-pass we can see.
      rows.push({ id: e.id, target: e.target, pass: false, pass_rate: 0,
        failed_assertions: ['(harness) produce/judge failed for all samples'], summary: 'no graded samples', produced: '' })
      continue
    }
    const passes = samples.filter((r) => r.verdict.overall_pass).length
    const passRate = passes / samples.length
    const pass = passRate > 0.5 // strict majority
    // Pick a representative FAILING sample (so the fixer sees the relevant reasoning); else the first.
    const repr = samples.find((r) => !r.verdict.overall_pass) || samples[0]
    const failedAssertions = (repr.verdict.assertion_results || [])
      .filter((a) => !a.pass)
      .map((a) => a.assertion + (a.note ? ' — ' + a.note : ''))
    rows.push({
      id: e.id, target: e.target, pass, pass_rate: passRate,
      failed_assertions: failedAssertions,
      summary: repr.verdict.summary || '',
      produced: repr.out || '',
    })
  }
  return rows
}

// ---------------------------------------------------------------------------
// Phase 2 — Grade everything once.
// ---------------------------------------------------------------------------

phase('Grade')
let rows = await gradeSet(evals)
let failed = rows.filter((r) => !r.pass)
log('Round 1: ' + (rows.length - failed.length) + '/' + rows.length + ' passed' +
    (failed.length ? ' — failing: ' + failed.map((f) => f.id).join(', ') : ''))

// ---------------------------------------------------------------------------
// REPORT-ONLY MODE (default). Edit nothing; return the table.
// ---------------------------------------------------------------------------

if (!FIX) {
  return {
    total: rows.length,
    passed: rows.length - failed.length,
    failed: failed.map((f) => ({
      id: f.id,
      pass_rate: f.pass_rate,
      failed_assertions: f.failed_assertions,
      summary: f.summary,
    })),
    all: rows.map((r) => ({ id: r.id, pass: r.pass })),
  }
}

// ---------------------------------------------------------------------------
// Phase 3 — AUTO-FIX LOOP (opt-in). Up to MAX_ROUNDS:
//   - if everything passes -> done (green).
//   - else for each STILL-failing, non-flagged eval, SEQUENTIALLY spawn a
//     diagnose-and-fix agent (NOT worktree-isolated — it edits the Workflow cwd
//     so the NEXT round's produce reads the change). Sequential is mandatory:
//     concurrent edits to the shared tree would clobber each other.
//   - track flagged evals (never re-attempt them).
//   - re-grade and stop early if a round fixes nothing new, or every remaining
//     failure is flagged.
// ---------------------------------------------------------------------------

phase('Fix')

function fixPrompt(e, row) {
  return 'You are the lunch-roulette eval **diagnose-and-fix** agent, editing files IN PLACE in the current working tree.\n\n' +
    'A Layer-2/3 LLM eval is FAILING. Eval id: "' + e.id + '" (target: ' + e.target + ').\n\n' +
    '--- The eval definition lives in one of:\n' + EVAL_FILES.join('\n') +
    '\nFind the entry with id "' + e.id + '" and READ it (setup + prompt + assertions).\n\n' +
    '--- The agent was asked:\n' + e.prompt + '\n\n' +
    '--- It produced (one representative run):\n"""\n' + row.produced + '\n"""\n\n' +
    '--- The judge marked these assertions FAILED:\n' +
    (row.failed_assertions.length ? row.failed_assertions.map((a, i) => (i + 1) + '. ' + a).join('\n') : '(none captured — re-read the eval and judge yourself)') +
    '\nJudge summary: ' + (row.summary || '(none)') + '\n\n' +
    '--- REQUIRED READING before you touch anything: the relevant design docs — `skills/lunch-roulette/references/data-schemas.md` (the messenger<->orchestrator contract), and the spec the target implements:\n' +
    '  • messenger      -> `agents/lunch-messenger.md`\n' +
    '  • orchestrator   -> `skills/lunch-roulette/SKILL.md` (+ scripts in `skills/lunch-roulette/scripts/`)\n' +
    '  • integration    -> BOTH of the above\n\n' +
    'DIAGNOSE THE ROOT CAUSE, then act:\n' +
    '  (A) The ASSERTION is wrong / over-strict — the produced behavior is actually correct per the spec (e.g. the assertion demands something the spec does not require, or contradicts intended behavior). THEN edit ONLY the eval JSON (the failing entry in one of the three files): relax/correct the assertion (or its setup/prompt) to match spec-correct behavior. Return action "fixed-eval".\n' +
    '  (B) The PLUGIN is genuinely wrong — the spec or a script does not do what the (correct) assertion requires. THEN edit the plugin file (SKILL.md / agents/lunch-messenger.md / a script under scripts/ / references/data-schemas.md). CRITICAL: keep the messenger<->orchestrator contract in LOCKSTEP across SKILL.md, references/data-schemas.md, and agents/lunch-messenger.md — if you change a field name or a step in one, update the others (and the matching CLI invocation/test if you touch a script). Return action "fixed-spec".\n' +
    '  (C) You CANNOT confidently decide between (A) and (B), OR the only way to make it pass would change core/intended behavior — then DO NOT EDIT ANYTHING. Return action "flagged" with a clear reason. (We will NOT force an eval green by mangling correct behavior.)\n\n' +
    'Make the SMALLEST change that addresses the diagnosed root cause; do not touch unrelated evals or files. Then return {action, file (path you edited, or "" if flagged), detail (your root-cause diagnosis + exactly what you changed, or why you flagged)}.'
}

const fixedLog = []     // { id, round, action, file, detail }
const flagged = new Set()
let green = false
let rounds = 0

for (let round = 1; round <= MAX_ROUNDS; round++) {
  rounds = round

  // Failing evals we haven't given up on.
  const toFix = failed.filter((f) => !flagged.has(f.id))
  if (failed.length === 0) { green = true; break }
  if (toFix.length === 0) {
    log('Round ' + round + ': all remaining failures are flagged — stopping.')
    break
  }

  log('Round ' + round + ': attempting ' + toFix.length + ' failing eval(s): ' + toFix.map((f) => f.id).join(', '))

  // SEQUENTIAL on purpose — each agent edits the shared working tree; running
  // them concurrently would race/clobber. await one fully before the next.
  const newlyFixedThisRound = []
  for (const f of toFix) {
    const e = byId.get(f.id)
    const res = await agent(fixPrompt(e, f), {
      label: 'fix:' + f.id + '@r' + round,
      phase: 'Fix',
      // NOTE: deliberately NOT isolation:'worktree' — must edit the live cwd.
    })
    fixedLog.push({ id: f.id, round, action: res.action, file: res.file || '', detail: res.detail || '' })
    if (res.action === 'flagged') {
      flagged.add(f.id)
      log('  • ' + f.id + ': FLAGGED — ' + (res.detail || '(no reason)'))
    } else {
      newlyFixedThisRound.push(f.id)
      log('  • ' + f.id + ': ' + res.action + ' (' + (res.file || '?') + ')')
    }
  }

  // Stop early if this round made no real progress (nothing newly fixed).
  if (newlyFixedThisRound.length === 0) {
    log('Round ' + round + ': nothing newly fixed (all attempts flagged) — stopping.')
    break
  }

  // Re-grade EVERYTHING (a spec/contract edit can regress a previously-green eval).
  rows = await gradeSet(evals)
  failed = rows.filter((r) => !r.pass)
  log('Round ' + round + ' re-grade: ' + (rows.length - failed.length) + '/' + rows.length + ' passed' +
      (failed.length ? ' — failing: ' + failed.map((f) => f.id).join(', ') : ''))

  if (failed.length === 0) { green = true; break }
  // If every remaining failure is already flagged, the next loop will stop.
}

// ---------------------------------------------------------------------------
// Auto-fix result. The accumulated edits live in the working tree on the
// invoker's branch — the human reviews and opens the PR; the harness does not.
// ---------------------------------------------------------------------------

return {
  rounds,
  green,
  fixed: fixedLog.filter((f) => f.action !== 'flagged'),
  flagged: fixedLog.filter((f) => f.action === 'flagged').map((f) => ({ id: f.id, detail: f.detail })),
  final: rows.map((r) => ({ id: r.id, pass: r.pass })),
}
