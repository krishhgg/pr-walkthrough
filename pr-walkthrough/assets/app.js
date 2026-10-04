'use strict';
const D = JSON.parse(document.getElementById('data').textContent);
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const SVGNS = 'http://www.w3.org/2000/svg';
const LEVELS = D.levels || {};
const C = D.concepts || {};
const rel = D.kind === 'pr' ? '../' : '';
const P = D.pr || {};

// ------------------------------------------------------------ concept tooltips and drawer
const tip = $('#tip');
document.addEventListener('mouseover', (e) => {
  const a = e.target.closest('a.c');
  if (!a) return;
  const c = C[a.dataset.c];
  if (!c) return;
  tip.innerHTML = `<b>${esc(c.title)}</b>${c.short}`;
  const r = a.getBoundingClientRect();
  tip.style.left = Math.min(window.innerWidth - 350, Math.max(8, r.left)) + 'px';
  tip.style.top = (r.bottom + 8 + 120 > window.innerHeight ? r.top - 90 : r.bottom + 8) + 'px';
  tip.style.opacity = 1;
});
document.addEventListener('mouseout', (e) => { if (e.target.closest('a.c')) tip.style.opacity = 0; });
document.addEventListener('click', (e) => {
  const a = e.target.closest('a.c');
  if (!a) return;
  e.preventDefault();
  tip.style.opacity = 0;
  openLesson(a.dataset.c);
});
const history_ = [];
function openLesson(id, push = true) {
  const c = C[id];
  if (!c) return;
  if (push) history_.push(id);
  $('#dtitle').textContent = c.title;
  const pre = (c.prereqs || []).filter((p) => C[p]);
  $('#dbody').innerHTML = `
    <div class="crumbs">Level ${c.level}: ${esc(LEVELS[c.level] || '')}${pre.length ? ' · Builds on ' + pre.map((p) => `<a class="c" data-c="${p}">${esc(C[p].title)}</a>`).join(', ') : ''}</div>
    ${lessonBody(c)}`;
  $('#drawer').classList.add('open');
  $('#drawer').setAttribute('aria-hidden', 'false');
  $('#dbody').scrollTop = 0;
}
$('#dclose').addEventListener('click', () => { $('#drawer').classList.remove('open'); $('#drawer').setAttribute('aria-hidden', 'true'); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') $('#dclose').click(); });

function lessonBody(c) {
  let h = c.body || '';
  const ex = c.example;
  if (ex && ex.code) {
    const lines = ex.code.split('\n');
    const hl = highlight(lines, ex.lang || 'py');
    h += `<div class="ex"><div class="exttl">${esc(ex.title || 'Example')}</div><div class="code-rows">${lines.map((_, i) => `
      <div class="crow"><div class="src"><span class="dl"><span class="ln">${i + 1}</span><span class="l">${hl[i] || ' '}</span></span></div><div class="note">${ex.notes[i] || ''}</div></div>`).join('')}</div></div>`;
  }
  const hook = (D.hooks || {})[c.id];
  if (hook) h += `<p class="mute"><b>In this PR:</b> ${hook}</p>`;
  return h;
}

// ------------------------------------------------------------ syntax highlighting
const KW = new Set('def return if elif else for in not and or try except with as import from class None True False break continue raise lambda is while pass yield finally global nonlocal assert async await'.split(' '));
function highlight(lines, lang) {
  if (lang !== 'py') return lines.map((l) => highlightPlain(l, lang));
  const out = [];
  let triple = null; // quote style of an open triple-quoted string
  for (const line of lines) {
    let h = '', i = 0;
    if (triple) {
      const end = line.indexOf(triple);
      if (end < 0) { out.push(`<span class="s">${esc(line)}</span>`); continue; }
      h += `<span class="s">${esc(line.slice(0, end + 3))}</span>`;
      i = end + 3;
      triple = null;
    }
    while (i < line.length) {
      const ch = line[i], rest = line.slice(i);
      if (ch === '#') { h += `<span class="cm">${esc(rest)}</span>`; break; }
      const tm = rest.match(/^[rbfu]{0,2}("""|''')/i);
      if (tm) {
        const q = tm[1], start = tm[0].length, end = rest.indexOf(q, start);
        if (end < 0) { h += `<span class="s">${esc(rest)}</span>`; triple = q; break; }
        h += `<span class="s">${esc(rest.slice(0, end + 3))}</span>`;
        i += end + 3;
        continue;
      }
      const sm = rest.match(/^[rbfu]{0,2}(['"])(?:\\.|(?!\1).)*\1?/i);
      if (sm && (ch === '"' || ch === "'" || /^[rbfu]{1,2}['"]/i.test(rest))) { h += `<span class="s">${esc(sm[0])}</span>`; i += sm[0].length; continue; }
      const dm = rest.match(/^@[A-Za-z_][\w.]*/);
      if (dm && h.trim() === '') { h += `<span class="dec">${esc(dm[0])}</span>`; i += dm[0].length; continue; }
      const wm = rest.match(/^[A-Za-z_]\w*/);
      if (wm) {
        const w = wm[0];
        if (KW.has(w)) h += `<span class="k">${w}</span>`;
        else if (/(def|class)\s*$/.test(line.slice(0, i))) h += `<span class="fdef">${w}</span>`;
        else h += esc(w);
        i += w.length;
        continue;
      }
      const nm = rest.match(/^\d[\d_.]*/);
      if (nm) { h += `<span class="n">${nm[0]}</span>`; i += nm[0].length; continue; }
      h += esc(ch);
      i += 1;
    }
    out.push(h);
  }
  return out;
}
const CKW = new Set(('function return if else for while do switch case break continue new delete typeof instanceof in of const let var class extends ' +
  'import export from default async await try catch finally throw this super null undefined true false void yield static public private protected ' +
  'interface type enum implements readonly abstract package func go defer chan map struct range select fn mut impl trait use pub match loop where ' +
  'self Self crate mod int long char float double bool boolean string String final override val fun when object').split(' '));
function highlightC(line) {
  let h = '', i = 0;
  while (i < line.length) {
    const ch = line[i], rest = line.slice(i);
    if (rest.startsWith('//')) { h += `<span class="cm">${esc(rest)}</span>`; break; }
    const bm = rest.match(/^\/\*.*?(\*\/|$)/);
    if (bm) { h += `<span class="cm">${esc(bm[0])}</span>`; i += bm[0].length; continue; }
    const sm = rest.match(/^(['"`])(?:\\.|(?!\1).)*\1?/);
    if (sm) { h += `<span class="s">${esc(sm[0])}</span>`; i += sm[0].length; continue; }
    const wm = rest.match(/^[A-Za-z_$][\w$]*/);
    if (wm) { const w = wm[0]; h += CKW.has(w) ? `<span class="k">${w}</span>` : /(function|func|fn|class|def)\s*$/.test(line.slice(0, i)) ? `<span class="fdef">${esc(w)}</span>` : esc(w); i += w.length; continue; }
    const nm = rest.match(/^\d[\d_.xXa-fA-F]*/);
    if (nm) { h += `<span class="n">${nm[0]}</span>`; i += nm[0].length; continue; }
    h += esc(ch); i += 1;
  }
  return h;
}
function highlightPlain(line, lang) {
  if (lang === 'json') return esc(line).replace(/(&quot;(?:[^&]|&(?!quot;))*?&quot;)/g, '<span class="s">$1</span>');
  if (lang === 'md') return line.startsWith('#') ? `<span class="fdef">${esc(line)}</span>` : esc(line);
  if (lang === 'c') return highlightC(line);
  if (lang === 'hash') { const k = line.indexOf('#'); return k < 0 ? esc(line) : esc(line.slice(0, k)) + `<span class="cm">${esc(line.slice(k))}</span>`; }
  return esc(line);
}
function langOf(path) {
  const ext = (path.match(/\.([a-z0-9]+)$/i) || [])[1] || '';
  if (ext === 'py') return 'py';
  if (ext === 'json') return 'json';
  if (/^(md|mdx|rst|txt)$/.test(ext)) return 'md';
  if (/^(js|jsx|ts|tsx|mjs|cjs|go|rs|java|kt|kts|c|h|cc|cpp|hpp|cs|swift|scala|dart|php)$/.test(ext)) return 'c';
  if (/^(sh|bash|zsh|yml|yaml|toml|rb|r|pl|cfg|ini|conf)$/.test(ext) || /(^|\/)(Dockerfile|Makefile|requirements[^/]*\.txt)$/.test(path)) return 'hash';
  return 'text';
}

// ------------------------------------------------------------ diagrams
function svgEl(tag, attrs = {}, text) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text != null) el.textContent = text;
  return el;
}
function wrapText(s, max) {
  const words = String(s).split(/\s+/), lines = [];
  let cur = '';
  for (const w of words) { if ((cur + ' ' + w).trim().length > max && cur) { lines.push(cur); cur = w; } else cur = (cur + ' ' + w).trim(); }
  if (cur) lines.push(cur);
  return lines;
}
function arrowMarker(svg, id, color) {
  let defs = svg.querySelector('defs') || svg.appendChild(svgEl('defs'));
  const m = svgEl('marker', {id, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse'});
  m.appendChild(svgEl('path', {d: 'M0,0 L10,5 L0,10 z', fill: color}));
  defs.appendChild(m);
}
const TONE_ARROW = {good: '#0f7a3d', bad: '#c93a39', plain: '#77756f', accent: '#2a78d6'};
function diagramFlow(spec, uid) {
  const W = 220, H = 64, GX = 60, GY = 42;
  const cols = Math.max(1, ...spec.nodes.map((n) => n.col + 1)), rows = Math.max(1, ...spec.nodes.map((n) => n.row + 1));
  const width = cols * W + (cols - 1) * GX + 20, height = rows * H + (rows - 1) * GY + 20;
  const svg = svgEl('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img'});
  for (const [k, c] of Object.entries(TONE_ARROW)) arrowMarker(svg, `${uid}-${k}`, c);
  const pos = {};
  for (const n of spec.nodes) pos[n.id] = {x: 10 + n.col * (W + GX), y: 10 + n.row * (H + GY)};
  for (const e of spec.edges || []) {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) continue;
    let x1, y1, x2, y2;
    if (a.y === b.y) { x1 = a.x + (b.x > a.x ? W : 0); x2 = b.x + (b.x > a.x ? 0 : W); y1 = y2 = a.y + H / 2; }
    else { x1 = a.x + W / 2; x2 = b.x + W / 2; y1 = a.y + (b.y > a.y ? H : 0); y2 = b.y + (b.y > a.y ? 0 : H); }
    const tone = e.tone || 'plain';
    svg.appendChild(svgEl('path', {d: `M${x1},${y1} L${x2},${y2}`, class: `dg-arrow ${tone}`, 'marker-end': `url(#${uid}-${tone})`}));
    if (e.label) {
      const lx = (x1 + x2) / 2, ly = (y1 + y2) / 2;
      const t = svgEl('text', {x: lx + (a.y === b.y ? 0 : 6), y: ly - (a.y === b.y ? 6 : 0), class: 'dg-s', 'text-anchor': a.y === b.y ? 'middle' : 'start'}, e.label);
      svg.appendChild(t);
    }
  }
  for (const n of spec.nodes) {
    const p = pos[n.id];
    const cls = {good: 'dg-good', bad: 'dg-bad', accent: 'dg-accent'}[n.tone] || 'dg-box';
    svg.appendChild(svgEl('rect', {x: p.x, y: p.y, width: W, height: H, rx: 9, class: cls}));
    const lines = wrapText(n.label, 30).slice(0, 3);
    lines.forEach((ln, i) => svg.appendChild(svgEl('text', {x: p.x + W / 2, y: p.y + H / 2 + (i - (lines.length - 1) / 2) * 16 + 4, class: 'dg-t', 'text-anchor': 'middle'}, ln)));
  }
  return svg;
}
function diagramSequence(spec, uid) {
  const actors = spec.actors, CW = 210, top = 44, RH = 46;
  const width = actors.length * CW, height = top + spec.steps.length * RH + 24;
  const svg = svgEl('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img'});
  for (const [k, c] of Object.entries(TONE_ARROW)) arrowMarker(svg, `${uid}-${k}`, c);
  const x = (a) => actors.indexOf(a) * CW + CW / 2;
  actors.forEach((a) => {
    svg.appendChild(svgEl('rect', {x: x(a) - 80, y: 4, width: 160, height: 30, rx: 8, class: 'dg-accent'}));
    svg.appendChild(svgEl('text', {x: x(a), y: 24, class: 'dg-t', 'text-anchor': 'middle', 'font-weight': 700}, a));
    svg.appendChild(svgEl('line', {x1: x(a), y1: 34, x2: x(a), y2: height - 6, stroke: '#cfccc4', 'stroke-dasharray': '4 4'}));
  });
  spec.steps.forEach((s, i) => {
    const y = top + i * RH + 28, tone = s.tone || 'plain';
    if (s.from === s.to) {
      const X = x(s.from);
      svg.appendChild(svgEl('path', {d: `M${X},${y - 10} h34 v18 h-30`, class: `dg-arrow ${tone}`, 'marker-end': `url(#${uid}-${tone})`}));
      svg.appendChild(svgEl('text', {x: X + 40, y: y + 2, class: 'dg-s'}, s.label));
    } else {
      svg.appendChild(svgEl('path', {d: `M${x(s.from)},${y} L${x(s.to)},${y}`, class: `dg-arrow ${tone}`, 'marker-end': `url(#${uid}-${tone})`}));
      svg.appendChild(svgEl('text', {x: (x(s.from) + x(s.to)) / 2, y: y - 7, class: 'dg-s', 'text-anchor': 'middle'}, s.label));
    }
  });
  return svg;
}
function diagramBars(spec) {
  const rows = spec.rows, max = Math.max(...rows.map((r) => r.value), 1), W = 640, RH = 34;
  const svg = svgEl('svg', {viewBox: `0 0 ${W} ${rows.length * RH + 10}`, role: 'img'});
  rows.forEach((r, i) => {
    const y = 5 + i * RH, w = Math.max(2, (r.value / max) * (W - 260));
    svg.appendChild(svgEl('text', {x: 0, y: y + 19, class: 'dg-t'}, r.label));
    svg.appendChild(svgEl('rect', {x: 170, y: y + 4, width: w, height: 22, rx: 4, fill: r.tone === 'good' ? '#1baf7a' : r.tone === 'bad' ? '#eb6834' : '#2a78d6'}));
    svg.appendChild(svgEl('text', {x: 176 + w, y: y + 20, class: 'dg-t'}, `${r.value} ${spec.unit || ''}`));
  });
  return svg;
}
function renderDiagram(d, i) {
  const uid = `dg${i}`;
  let body;
  if (d.kind === 'flow') body = diagramFlow(d.spec, uid).outerHTML;
  else if (d.kind === 'sequence') body = diagramSequence(d.spec, uid).outerHTML;
  else if (d.kind === 'bars') body = diagramBars(d.spec).outerHTML;
  else if (d.kind === 'compare') {
    const col = (c) => `<div class="col ${c.tone || 'plain'}"><h5>${esc(c.title)}</h5><ol>${c.items.map((t) => `<li>${t}</li>`).join('')}</ol></div>`;
    body = `<div class="cmp">${col(d.spec.left)}${col(d.spec.right)}</div>`;
  } else if (d.kind === 'strip') {
    body = `<div class="strip">${d.spec.segments.map((s) => `<span class="${s.kind}">${esc(s.text)}</span>`).join('')}</div>${d.spec.note ? `<p class="figcap">${d.spec.note}</p>` : ''}`;
  } else body = `<p class="mute">Unknown diagram kind ${esc(d.kind)}</p>`;
  return `<div class="figure" id="${esc(d.id || uid)}"><h4>${esc(d.title || '')}</h4>${body}${d.caption ? `<div class="figcap">${d.caption}</div>` : ''}</div>`;
}

// ------------------------------------------------------------ code walkthrough
function flatten(fd) {
  const out = [];
  fd.hunks.forEach((h, hi) => h.lines.forEach((l) => out.push({...l, hunk: hi})));
  return out;
}
function chunkIdx(ch, lines) {
  const idx = [];
  lines.forEach((l, i) => {
    const hitOld = ch.old && l.old != null && l.old >= ch.old[0] && l.old <= ch.old[1];
    const hitNew = ch.new && l.new != null && l.new >= ch.new[0] && l.new <= ch.new[1];
    if (hitOld || hitNew) idx.push(i);
  });
  return idx;
}
function codeLines(lines, hl, from, to) {
  let h = '';
  for (let i = from; i <= to; i++) {
    const l = lines[i];
    if (i > from && l.hunk !== lines[i - 1].hunk) h += `<span class="dl"><span class="ln"></span><span class="sg"></span><span class="l" style="color:#77756f">⋯</span></span>`;
    const num = l.t === 'del' ? l.old : l.new;
    const sg = l.t === 'add' ? '+' : l.t === 'del' ? '−' : ' ';
    h += `<span class="dl ${l.t}"><span class="ln">${num ?? ''}</span><span class="sg">${sg}</span><span class="l">${hl[i] || ' '}</span></span>`;
  }
  return h;
}
const fileId = (path) => 'file-' + path.replace(/[^\w]/g, '-');
const chunkId = (fi, ci) => `c-${fi}-${ci}`;
const RISK = {high: 'red', medium: 'amber', low: 'green'};
function riskPill(r) { return r ? `<span class="pill ${RISK[r] || ''}">${esc(r)} risk</span>` : ''; }

// What a chunk does to the code, from its own lines: added, removed or changed.
function chunkKind(lines, from, to) {
  let add = 0, del = 0;
  for (let i = from; i <= to; i++) { if (lines[i].t === 'add') add++; if (lines[i].t === 'del') del++; }
  return add && del ? 'changed' : add ? 'added' : del ? 'removed' : 'context';
}

// A link to this chunk's first changed line on the PR's "Files changed" tab, where a reviewer can comment.
function githubLink(path, lines, from, to) {
  const anchor = (D.gh_anchor || {})[path];
  if (!P.url || !anchor) return '';
  for (let i = from; i <= to; i++) if (lines[i].t === 'add') return `${P.url}/files#diff-${anchor}R${lines[i].new}`;
  for (let i = from; i <= to; i++) if (lines[i].t === 'del') return `${P.url}/files#diff-${anchor}L${lines[i].old}`;
  return '';
}

function renderFile(f, fd, fi) {
  const lines = flatten(fd);
  const lang = langOf(f.path);
  const hl = highlight(lines.map((l) => l.text), lang);
  const changed = new Set(((D.changed || {}).chunks || {})[f.path] || []);
  const spans = (f.chunks || []).map((ch, ci) => {
    const idx = chunkIdx(ch, lines);
    return {ci, from: Math.min(...idx), to: Math.max(...idx), ch};
  }).sort((a, b) => a.from - b.from);
  // Unchanged context and supporting chunks start folded: the notes carry the reading, the code opens on request.
  const plain = (from, to) => `<div class="crow plain"><details class="ctx"><summary>${to - from + 1} unchanged line${to > from ? 's' : ''}</summary><div class="src">${codeLines(lines, hl, from, to)}</div></details><div class="note"></div></div>`;
  let rows = '', i = 0;
  for (const s of spans) {
    if (i < s.from) rows += plain(i, s.from - 1);
    const src = `<div class="src">${codeLines(lines, hl, s.from, s.to)}</div>`;
    const kind = chunkKind(lines, s.from, s.to);
    const gh = githubLink(f.path, lines, s.from, s.to);
    const meta = `<div class="cmeta"><span class="kind ${kind}">${kind}</span>${riskPill(s.ch.risk)}${changed.has(s.ci) ? '<span class="pill blue">updated since you last read</span>' : ''}${gh ? `<a class="ghlink" href="${gh}" target="_blank" rel="noopener">Comment on GitHub</a>` : ''}</div>`;
    const note = `${meta}${s.ch.html}${s.ch.check ? `<div class="check"><b>Check:</b> ${s.ch.check}</div>` : ''}`;
    rows += s.ch.fold
      ? `<div class="crow${changed.has(s.ci) ? ' updated' : ''}" id="${chunkId(fi, s.ci)}"><details class="ctx"><summary>Show ${s.to - s.from + 1} lines</summary>${src}</details><div class="note">${note}</div></div>`
      : `<div class="crow${changed.has(s.ci) ? ' updated' : ''}" id="${chunkId(fi, s.ci)}">${src}<div class="note">${note}</div></div>`;
    i = s.to + 1;
  }
  if (i < lines.length) rows += plain(i, lines.length - 1);
  const status = {added: '<span class="pill green">new file</span>', deleted: '<span class="pill red">deleted</span>', renamed: '<span class="pill">renamed</span>'}[fd.status] || '';
  const body = isSecondary(f.path)
    ? `<details class="filefold"><summary>Show the ${fd.added + fd.deleted} changed lines, with notes</summary><div class="code-rows">${rows}</div></details>`
    : `<div class="code-rows">${rows}</div>`;
  return `<div class="filehead" id="${fileId(f.path)}"><h3>${esc(f.path)}</h3>${status}<span class="pill green">+${fd.added}</span><span class="pill red">−${fd.deleted}</span></div>
    <div>${f.role || ''}</div>${body}`;
}

// Tests, docs, generated files and dependency lists: their one-line role is the summary, the lines open on request.
function isSecondary(path) {
  return /(^|\/)(tests?|__tests__|spec|specs|testdata|fixtures)\//.test(path) || /(_test|\.test|\.spec)\.[a-z]+$/.test(path) ||
    /\.(md|mdx|rst|lock|snap|svg)$/.test(path) || /(^|\/)(requirements[^/]*\.txt|package-lock\.json|yarn\.lock|pnpm-lock\.yaml|go\.sum|Cargo\.lock)$/.test(path);
}
function fileGroup(path) {
  if (/(^|\/)(tests?|__tests__|spec|specs|testdata|fixtures)\//.test(path) || /(_test|\.test|\.spec)\.[a-z]+$/.test(path)) return 'Tests';
  if (/\.(md|mdx|rst|txt)$/.test(path) || /(^|\/)docs?\//.test(path)) return 'Docs';
  if (/(^|\/)(requirements[^/]*\.txt|package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|go\.(mod|sum)|Cargo\.(toml|lock)|pyproject\.toml|setup\.(py|cfg))$/.test(path) ||
      /\.(ya?ml|toml|ini|cfg|conf|env|lock)$/.test(path) || /(^|\/)\.github\//.test(path)) return 'Config and dependencies';
  return 'Code';
}

// Minutes to read what is open by default: prose at 200 words a minute, code at 60 lines a minute.
function readingMinutes(root) {
  let words = 0, codeLines = 0, diagrams = 0;
  const walk = (el) => {
    if (el.tagName === 'DETAILS' && !el.open) { const s = el.querySelector('summary'); if (s && !el.matches('.ctx, .filefold')) words += s.textContent.split(/\s+/).filter(Boolean).length; return; }
    if (el.tagName === 'svg') { diagrams += 1; return; }
    if (el.classList && el.classList.contains('src')) { codeLines += el.querySelectorAll('.dl').length; return; }
    for (const c of el.childNodes) { if (c.nodeType === 3) words += c.textContent.split(/\s+/).filter(Boolean).length; else if (c.nodeType === 1) walk(c); }
  };
  walk(root);
  return {minutes: Math.max(1, Math.round(words / 200 + codeLines / 60 + diagrams / 2)), words, codeLines, diagrams};
}

// ------------------------------------------------------------ evidence
function outcomePill(o) {
  if (!o) return '<span class="pill">not run</span>';
  const m = {passed: 'green', failed: 'red', error: 'red', skipped: ''};
  const label = {passed: 'passes', failed: 'fails', error: 'error', skipped: 'skipped'}[o] || o;
  return `<span class="pill ${m[o] || ''}">${label}</span>`;
}
function renderTests(t) {
  if (!t || !t.rows) return '';
  const fixed = t.rows.filter((r) => r.after === 'passed' && r.before !== 'passed').length;
  const kept = t.rows.filter((r) => r.after === 'passed' && r.before === 'passed').length;
  return `<details class="evidence"><summary>${t.rows.length} tests: ${fixed} fail before this PR and pass with it, ${kept} pass both times. Show the table.</summary><table class="t1"><tr><th>Test</th><th>Before this PR</th><th>With this PR</th></tr>${t.rows.map((r) => `
    <tr><td><code>${esc(r.name)}</code>${r.doc ? `<div class="mute" style="font-size:13px">${esc(r.doc)}</div>` : ''}</td><td>${outcomePill(r.before)}${r.before_msg ? `<div class="mute" style="font-size:12.5px">${esc(r.before_msg)}</div>` : ''}</td><td>${outcomePill(r.after)}</td></tr>`).join('')}</table>
    ${t.command ? `<p class="mute" style="font-size:13px">Run with: <code>${esc(t.command)}</code></p>` : ''}</details>`;
}

// ------------------------------------------------------------ review guide
// Find the chunk that holds a look-first reference, so the list can link straight to it.
function findChunk(K, ref) {
  const fi = K.files.findIndex((f) => f.path === ref.path);
  if (fi < 0) return null;
  const side = ref.new ? 'new' : 'old', line = (ref.new || ref.old || [])[0];
  const ci = (K.files[fi].chunks || []).findIndex((ch) => ch[side] && line >= ch[side][0] && line <= ch[side][1]);
  return ci < 0 ? {fi, ci: null} : {fi, ci};
}
function renderReviewGuide(K, byPath) {
  const R = K.review || {};
  const groups = {};
  for (const f of K.files) {
    const fd = byPath[f.path];
    if (!fd) continue;
    (groups[fileGroup(f.path)] = groups[fileGroup(f.path)] || []).push({f, fd});
  }
  const order = ['Code', 'Tests', 'Config and dependencies', 'Docs'];
  const map = order.filter((g) => groups[g]).map((g) => `<tr class="grp"><td colspan="3">${g}</td></tr>${groups[g].map(({f, fd}) => `
    <tr><td><a href="#${fileId(f.path)}"><code>${esc(f.path)}</code></a> ${{added: '<span class="pill green">new</span>', deleted: '<span class="pill red">deleted</span>', renamed: '<span class="pill">renamed</span>'}[fd.status] || ''}</td>
    <td class="nowrap"><span class="ok">+${fd.added}</span> <span class="bad">−${fd.deleted}</span></td><td>${f.role || ''}</td></tr>`).join('')}`).join('');
  const look = (R.look_first || []).map((it) => {
    const at = findChunk(K, it);
    const href = at ? (at.ci == null ? `#${fileId(it.path)}` : `#${chunkId(at.fi, at.ci)}`) : '#';
    const line = (it.new || it.old || [])[0];
    return `<li><a href="${href}"><code>${esc(it.path.split('/').pop())}${line ? ':' + line : ''}</code></a> ${riskPill(it.risk)} ${it.why}</li>`;
  }).join('');
  const ch = D.changed;
  let changed = '';
  if (ch && ch.since) {
    const n = Object.values(ch.chunks || {}).reduce((a, v) => a + v.length, 0);
    const files = Object.keys(ch.chunks || {}).filter((p) => (ch.chunks[p] || []).length);
    changed = `<div class="card blue"><p><b>Updated since you last read.</b> The PR moved from <code>${esc(ch.since.slice(0, 8))}</code> to <code>${esc((P.head_sha || '').slice(0, 8))}</code>. ${n} change${n === 1 ? ' is' : 's are'} new or different${files.length ? ', in ' + files.map((p) => `<a href="#${fileId(p)}"><code>${esc(p.split('/').pop())}</code></a>`).join(', ') : ''}; they carry a blue "updated" mark.${(ch.new_files || []).length ? ` New files: ${ch.new_files.map((p) => `<code>${esc(p)}</code>`).join(', ')}.` : ''}</p></div>`;
  }
  return `<section id="guide"><h2>Review guide</h2>${changed}
    ${look ? `<h3>Look here first</h3><ol class="lookfirst">${look}</ol>` : ''}
    ${(R.questions || []).length ? `<h3>Questions for the author</h3><ul>${R.questions.map((q) => `<li>${q}</li>`).join('')}</ul>` : ''}
    <h3>Change map</h3><table class="t1 cmap">${map}</table>
    ${P.diff_scope ? `<p class="mute" style="font-size:13px">This page covers ${esc(P.diff_scope)}.</p>` : ''}</section>`;
}

// ------------------------------------------------------------ pages
function nav(items, sub) {
  $('#toc').innerHTML = `<div class="brand"><a href="${rel}index.html">${esc(D.repo || 'Walkthroughs')}</a></div><div class="sub">${sub}</div><ol>${items.map((it) => it.part ? `<li class="part">${esc(it.part)}</li>` : `<li><a href="#${it.id}">${esc(it.label)}</a></li>`).join('')}</ol>`;
  const links = $$('nav#toc a[href^="#"]');
  const obs = new IntersectionObserver((ents) => ents.forEach((e) => { if (e.isIntersecting) { links.forEach((a) => a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id)); } }), {rootMargin: '-10% 0px -80% 0px'});
  $$('section[id]').forEach((s) => obs.observe(s));
}
function lessonsHtml(ids) {
  let h = '', lvl = null;
  for (const id of ids) {
    const c = C[id];
    if (!c) continue;
    if (c.level !== lvl) { lvl = c.level; h += `<div class="levelhead">Level ${lvl}: ${esc(LEVELS[lvl] || '')}</div>`; }
    h += `<details class="lesson" id="lesson-${id}"><summary><span class="lvl">Level ${c.level}</span><span class="ttl">${esc(c.title)}</span><span class="sh">${c.short}</span></summary><div class="lbody">${lessonBody(c)}</div></details>`;
  }
  return h;
}
const SOURCE = {
  'author-notes': ['green', "From the author's notes"],
  'pr-text': ['', 'From the PR description, commits and review threads'],
  inferred: ['amber', 'Inferred by the reviewer from the code, not stated by the author'],
};

function renderPR() {
  const K = D.content, X = D.diff;
  const byPath = Object.fromEntries(X.files.map((f) => [f.path, f]));
  const adds = X.files.reduce((a, f) => a + f.added, 0), dels = X.files.reduce((a, f) => a + f.deleted, 0);
  const sib = D.siblings || [], idx = sib.findIndex((p) => p.id === P.id), prev = sib[idx - 1], next = sib[idx + 1];
  const T = K.thinking || {};
  const src = SOURCE[T.source] || SOURCE.inferred;
  const where = P.number ? `PR #${P.number}` : `Branch ${esc(P.head)}`;
  let h = `
  <section id="top"><div class="kicker">${where}${P.author ? ' · by ' + esc(P.author) : ''}${P.isDraft ? ' · draft' : ''}${P.stack_parent ? ` · stacked on #${P.stack_parent}` : ''}</div>
    <h1>${esc(P.title)}</h1><div class="lede">${K.summary}</div>
    <div class="facts"><span><b>Branch</b> <code>${esc(P.head || '')}</code></span><span><b>Into</b> <code>${esc(P.base || '')}</code></span><span><b>Files</b> ${X.files.length}</span><span><b>Lines</b> <span class="ok">+${adds}</span> <span class="bad">−${dels}</span></span><span><b>Commit</b> <code>${esc((P.head_sha || '').slice(0, 8))}</code></span></div>
    <div class="toolbar">${P.url ? `<a class="btn" href="${P.url}">Open on GitHub</a><a class="btn" href="${P.url}/files">Files changed</a>` : ''}<a class="btn" href="changes.diff">The exact diff</a><a class="btn" href="${rel}lessons.html">All lessons</a>${prev ? `<a class="btn" href="${rel}${prev.folder}/walkthrough.html">Previous: ${esc(prev.label)}</a>` : ''}${next ? `<a class="btn" href="${rel}${next.folder}/walkthrough.html">Next: ${esc(next.label)}</a>` : ''}</div>
    <div class="card blue"><p><b>How to read this page.</b> The review guide says where to look first. Underlined words open a short lesson on the side. Folded parts open when clicked. Each change links to its line on GitHub, where you can leave a comment.</p></div>
  </section>
  ${renderReviewGuide(K, byPath)}
  <section id="ba"><h2>Before and after</h2><div class="ba"><div class="before"><h5>Before</h5>${K.before_after.before}</div><div class="after"><h5>With this PR</h5>${K.before_after.after}</div></div></section>
  ${K.background ? `<section id="background"><h2>Background</h2>${K.background}</section>` : ''}
  <section id="problem"><h2>The problem</h2>${K.problem}${(K.diagrams || []).map(renderDiagram).join('')}</section>
  <section id="thinking"><h2>How the change was worked out</h2><p><span class="pill ${src[0]}">${src[1]}</span></p>
    <ol class="steps">${(T.steps || []).map((s) => `<li><h4>${esc(s.title)}</h4>${s.html}</li>`).join('')}</ol>
    ${(T.options || []).length ? `<h3>The options weighed</h3>${T.options.map((o) => `<div class="option ${o.verdict}"><h4>${esc(o.name)} <span class="pill ${o.verdict === 'chosen' ? 'green' : ''}">${o.verdict === 'chosen' ? 'chosen' : 'not chosen'}</span></h4>${o.html}${o.why ? `<div><b>Why:</b> ${o.why}</div>` : ''}</div>`).join('')}` : ''}
    ${T.decision ? `<h3>The decision</h3>${T.decision}` : ''}
    ${T.lesson ? `<div class="card amber"><h4>The habit to take away</h4>${T.lesson}</div>` : ''}
  </section>
  <section id="code"><h2>The code, change by change</h2><div class="legend"><span class="la">added line</span><span class="ld">removed line</span><span class="lc">unchanged context</span></div>
    ${K.files.map((f, fi) => renderFile(f, byPath[f.path], fi)).join('')}
  </section>
  <section id="proof"><h2>How we know it works</h2>${K.tests || ''}
    ${D.tests && D.tests.rows ? `<h3>The tests, before and after</h3>${renderTests(D.tests)}` : ''}
  </section>
  <section id="risks"><h2>What could go wrong</h2>${(K.risks || []).map((r) => `<div class="card"><div>${r.risk}</div><div style="margin-top:6px"><b>Answer:</b> ${r.answer}</div></div>`).join('')}</section>
  <section id="basics"><h2>The basics, from the ground up</h2><details><summary>Every idea this PR uses, from the most basic (${(D.ladder || []).length} lessons). Underlined words in the page open the same lessons.</summary>${lessonsHtml(D.ladder || [])}</details></section>`;
  $('#main').innerHTML = h;
  const rt = readingMinutes($('#main'));
  const kicker = document.querySelector('#top .kicker');
  if (kicker) kicker.insertAdjacentHTML('beforeend', ` · about ${rt.minutes} min to read`);
  nav([{id: 'top', label: 'Summary'}, {id: 'guide', label: 'Review guide'}, {id: 'ba', label: 'Before and after'},
    ...(K.background ? [{id: 'background', label: 'Background'}] : []), {id: 'problem', label: 'The problem'}, {id: 'thinking', label: 'How it was worked out'},
    {part: 'Code'}, {id: 'code', label: 'Change by change'}, {id: 'proof', label: 'How we know it works'}, {id: 'risks', label: 'What could go wrong'},
    {part: 'Learn'}, {id: 'basics', label: 'The basics'}], where);
}

function renderIndex() {
  const prs = D.prs || [];
  const byNumber = Object.fromEntries(prs.filter((p) => p.number).map((p) => [p.number, p]));
  const card = (p) => `<div class="prcard"><div><span class="id">${p.number ? '#' + p.number : esc(p.head)}</span> ${[p.isDraft ? '<span class="pill">draft</span>' : '', p.changed ? '<span class="pill blue">updated since you last read</span>' : '', p.stack_parent ? `<span class="pill">on #${p.stack_parent}</span>` : '', p.minutes ? `<span class="pill">${p.minutes} min</span>` : ''].filter(Boolean).join(' ')}</div>
    <h3>${esc(p.title)}</h3><div class="mute" style="font-size:14px">${p.short || ''}</div><div class="mute" style="font-size:12.5px">${p.author ? esc(p.author) + ' · ' : ''}<span class="ok">+${p.added}</span> <span class="bad">−${p.deleted}</span> in ${p.files} file${p.files === 1 ? '' : 's'}</div>
    <div class="links">${p.built ? `<a class="btn" href="${p.folder}/walkthrough.html">Walkthrough</a>` : '<span class="pill">page not built yet</span>'}${p.url ? `<a class="btn" href="${p.url}">GitHub</a>` : ''}<a class="btn" href="${p.folder}/changes.diff">Diff</a></div></div>`;
  // Stacks: a PR built on another PR of this set reads after it.
  const roots = prs.filter((p) => !p.stack_parent || !byNumber[p.stack_parent]);
  const kids = (n) => prs.filter((p) => p.stack_parent === n);
  const ordered = [];
  const walk = (p) => { ordered.push(p); if (p.number) kids(p.number).forEach(walk); };
  roots.forEach(walk);
  const stacked = prs.some((p) => p.stack_parent && byNumber[p.stack_parent]);
  let diagram = '';
  if (stacked && ordered.length <= 14) {
    const nodes = [{id: 'base', label: 'base branch', col: 0, row: 0, tone: 'plain'}], edges = [];
    let row = 0;
    const depth = (p) => (p.stack_parent && byNumber[p.stack_parent] ? 1 + depth(byNumber[p.stack_parent]) : 1);
    ordered.forEach((p) => {
      const id = 'p' + (p.number || p.folder);
      nodes.push({id, label: `${p.number ? '#' + p.number + ': ' : ''}${p.title.slice(0, 48)}`, col: depth(p), row: row++, tone: 'good'});
      edges.push({from: p.stack_parent && byNumber[p.stack_parent] ? 'p' + p.stack_parent : 'base', to: id});
    });
    diagram = renderDiagram({title: 'How these PRs stack', kind: 'flow', spec: {nodes, edges}}, 0);
  }
  $('#main').innerHTML = `<section id="top"><div class="kicker">${esc(D.repo || '')}</div><h1>${esc(D.title || 'Pull request walkthroughs')}</h1>
    <div class="lede"><p>${prs.length} pull request${prs.length === 1 ? '' : 's'}, each with a page that says where to look first, explains every changed line and the reasoning behind it, and links each change to GitHub for comments.</p></div>
    <div class="toolbar"><a class="btn" href="lessons.html">All lessons, from the ground up</a></div></section>
    <section id="order"><h2>Reading order</h2><p>${stacked ? 'A PR built on another one comes right after it, and its page covers only its own commits.' : 'The PRs are independent; read them in any order.'}</p>${diagram}</section>
    <section id="prs"><h2>Pull requests</h2><div class="prgrid">${ordered.map(card).join('')}</div></section>`;
  nav([{id: 'top', label: 'Overview'}, {id: 'order', label: 'Reading order'}, {id: 'prs', label: 'Pull requests'}], `${prs.length} PRs`);
}

function renderLessons() {
  $('#main').innerHTML = `<section id="top"><div class="kicker">Lessons</div><h1>The basics, from the ground up</h1><div class="lede"><p>Every idea used in these walkthroughs, from "what is a program" upward. Each lesson builds only on the lessons before it.</p></div></section><section id="all">${lessonsHtml(D.ladder || [])}</section>`;
  nav([{id: 'top', label: 'Lessons'}, {id: 'all', label: 'All lessons'}], 'From the ground up');
}

if (D.kind === 'pr') renderPR();
else if (D.kind === 'lessons') renderLessons();
else renderIndex();
