/*
 * Interactive fitting of the Slabikar cursive curves onto the alphabet
 * template image. See fit/README.md.
 *
 * Data model (fit/letters.json): each entry is one glyph placed on the image
 * with transform {tx, ty, s} (metafont units -> image pixels, y flipped) and
 * "contours", each a metafont-style path spec: knots with optional dir_in /
 * dir_out (degrees) and curls, and segments with type curve/line and
 * tensions. Directions left null are chosen by Hobby's algorithm (hobby.js,
 * identical to gen/bezier.py and METAFONT itself) and shown as ghost arrows.
 */
"use strict";

const SVGNS = "http://www.w3.org/2000/svg";
const svg = document.getElementById("canvas");
const worldG = document.getElementById("world");
const glyphsG = document.getElementById("glyphs");
const editorG = document.getElementById("editor");
const templateImg = document.getElementById("template");

let data = null;
let sel = { entry: -1, knot: null, seg: null }; // knot/seg: {ci, ki}/{ci, si}
let mode = "metafont";
let hidden = new Set();
let undoStack = [], redoStack = [];
let view = { x: 0, y: 0, w: 600 };
let drag = null;
let saveTimer = null;
let canSave = true; // false when served statically (no /save endpoint)

// ---------------------------------------------------------------- utilities

function el(name, attrs, parent) {
    const e = document.createElementNS(SVGNS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
}

function html(parent, tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    parent.appendChild(e);
    return e;
}

function round(v, n) { const f = 10 ** n; return Math.round(v * f) / f; }

function jsonSerialize(obj) {
    return JSON.stringify(obj,
        (k, v) => typeof v === "number" ? round(v, 4) : v, 1) + "\n";
}

function deepCopy(o) { return JSON.parse(JSON.stringify(o)); }

// ------------------------------------------------------------- coordinates

function e2i(e, p) {  // metafont -> image
    const t = e.transform;
    return [t.tx + t.s * p[0], t.ty - t.s * p[1]];
}
function i2e(e, P) {  // image -> metafont
    const t = e.transform;
    return [(P[0] - t.tx) / t.s, (t.ty - P[1]) / t.s];
}
function screenToImage(ev) {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    const q = pt.matrixTransform(svg.getScreenCTM().inverse());
    return [q.x, q.y];
}
function pxSize() {  // image units per screen pixel
    return view.w / svg.clientWidth;
}

function updateViewBox() {
    const asp = svg.clientHeight / Math.max(1, svg.clientWidth);
    svg.setAttribute("viewBox",
        `${view.x} ${view.y} ${view.w} ${view.w * asp}`);
    renderEditor();
}

// ------------------------------------------------------------------ solving

function solveContour(c) {
    try {
        return Hobby.solvePath(c.knots, c.segments, c.cyclic);
    } catch (err) {
        return null;
    }
}

function contourPathD(solved, cyclic) {
    if (!solved || !solved.length) return "";
    let d = `M ${solved[0][1][0]} ${solved[0][1][1]}`;
    for (const s of solved) {
        if (s[0] === "line") d += ` L ${s[2][0]} ${s[2][1]}`;
        else d += ` C ${s[2][0]} ${s[2][1]} ${s[3][0]} ${s[3][1]}` +
                  ` ${s[4][0]} ${s[4][1]}`;
    }
    if (cyclic) d += " Z";
    return d;
}

function bezPoint(s, t) {
    if (s[0] === "line") {
        const [p0, p1] = [s[1], s[2]];
        return [p0[0] + (p1[0]-p0[0])*t, p0[1] + (p1[1]-p0[1])*t];
    }
    const [p0, c1, c2, p1] = s.slice(1);
    const mt = 1 - t;
    return [
        mt**3*p0[0] + 3*mt*mt*t*c1[0] + 3*mt*t*t*c2[0] + t**3*p1[0],
        mt**3*p0[1] + 3*mt*mt*t*c1[1] + 3*mt*t*t*c2[1] + t**3*p1[1],
    ];
}

// Adjacent segment indices of a knot (null if none)
function knotSegs(c, ki) {
    const ns = c.segments.length, nk = c.knots.length;
    if (c.cyclic) return { out: ki % ns, inn: (ki - 1 + ns) % ns };
    return { out: ki < ns ? ki : null, inn: ki > 0 ? ki - 1 : null };
}

function segAngle(solved, si, atEnd) {
    const s = solved[si];
    let vx, vy;
    if (s[0] === "line") {
        vx = s[2][0] - s[1][0]; vy = s[2][1] - s[1][1];
    } else if (!atEnd) {
        vx = s[2][0] - s[1][0]; vy = s[2][1] - s[1][1];
        if (Math.hypot(vx, vy) < 1e-9) { vx = s[3][0]-s[1][0]; vy = s[3][1]-s[1][1]; }
    } else {
        vx = s[4][0] - s[3][0]; vy = s[4][1] - s[3][1];
        if (Math.hypot(vx, vy) < 1e-9) { vx = s[4][0]-s[2][0]; vy = s[4][1]-s[2][1]; }
    }
    return Math.atan2(vy, vx) * 180 / Math.PI;
}

// Effective (explicit or solver-chosen) directions at a knot, in degrees
function knotDirs(c, solved, ki) {
    const k = c.knots[ki];
    const adj = knotSegs(c, ki);
    const r = { out: null, inn: null, outAuto: true, innAuto: true };
    if (adj.out != null) {
        r.outAuto = k.dir_out == null;
        r.out = k.dir_out != null ? k.dir_out
            : (solved ? segAngle(solved, adj.out, false) : null);
    }
    if (adj.inn != null) {
        r.innAuto = k.dir_in == null;
        r.inn = k.dir_in != null ? k.dir_in
            : (solved ? segAngle(solved, adj.inn, true) : null);
    }
    return r;
}

// ------------------------------------------------------------------ history

function pushUndo() {
    undoStack.push(jsonSerialize(data));
    if (undoStack.length > 200) undoStack.shift();
    redoStack.length = 0;
}
function undo() {
    if (!undoStack.length) return;
    redoStack.push(jsonSerialize(data));
    data = JSON.parse(undoStack.pop());
    afterChange(false);
}
function redo() {
    if (!redoStack.length) return;
    undoStack.push(jsonSerialize(data));
    data = JSON.parse(redoStack.pop());
    afterChange(false);
}

// ------------------------------------------------------------------- saving

function setSaveStatus(cls, text) {
    const s = document.getElementById("save-status");
    s.className = cls; s.textContent = text;
}

function scheduleSave() {
    if (!canSave) { setSaveStatus("local", "not saved (use export)"); return; }
    setSaveStatus("saving", "…");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
        try {
            const r = await fetch("/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: jsonSerialize(data),
            });
            if (!r.ok) throw new Error("HTTP " + r.status);
            setSaveStatus("saved", "saved");
        } catch (err) {
            canSave = false;
            setSaveStatus("local", "not saved (use export)");
        }
    }, 600);
}

function afterChange(save = true) {
    if (sel.entry >= data.entries.length) sel.entry = -1;
    renderGlyphs();
    renderEditor();
    renderInspector();
    if (save) scheduleSave();
}

// ---------------------------------------------------------------- rendering

function renderGlyphs() {
    glyphsG.textContent = "";
    const opacity = document.getElementById("opacity").value / 100;
    const onlySel = document.getElementById("only-selected").checked;
    const centerline = document.getElementById("show-centerline").checked;
    data.entries.forEach((e, i) => {
        if (hidden.has(e.id)) return;
        if (onlySel && i !== sel.entry) return;
        const t = e.transform;
        const g = el("g", {
            class: "glyph" + (i === sel.entry ? " selected" : ""),
            transform: `translate(${t.tx},${t.ty}) scale(${t.s},${-t.s})`,
        }, glyphsG);
        g.dataset.i = i;
        for (const c of e.contours) {
            const solved = solveContour(c);
            const d = contourPathD(solved, c.cyclic);
            if (!d) continue;
            el("path", { class: "stroke", d,
                         "stroke-width": data.stroke_width,
                         "stroke-opacity": opacity * 0.8 }, g);
            if (centerline)
                el("path", { class: "center", d,
                             "stroke-width": data.stroke_width * 0.15 }, g);
        }
        g.addEventListener("pointerdown", ev => {
            ev.stopPropagation();
            if (sel.entry !== i) {
                selectEntry(i, false);
                startDrag(ev, { type: "move-wait", entry: i });
            } else {
                startDrag(ev, { type: "move", entry: i,
                                t0: { ...e.transform } });
            }
        });
    });
}

function arrow(parent, from, to, auto, extraClass) {
    const cls = auto ? " auto" : "";
    el("line", { class: "dir-arrow" + cls + (extraClass || ""),
                 x1: from[0], y1: from[1], x2: to[0], y2: to[1] }, parent);
    return el("circle", { class: "dir-tip" + cls,
                          cx: to[0], cy: to[1], r: 4 * pxSize() }, parent);
}

function renderEditor() {
    editorG.textContent = "";
    if (!data || sel.entry < 0) return;
    const e = data.entries[sel.entry];
    const px = pxSize();

    // Bounding box + transform handles
    let bb = null;
    for (const c of e.contours)
        for (const k of c.knots) {
            const P = e2i(e, [k.x, k.y]);
            if (!bb) bb = [P[0], P[1], P[0], P[1]];
            bb = [Math.min(bb[0], P[0]), Math.min(bb[1], P[1]),
                  Math.max(bb[2], P[0]), Math.max(bb[3], P[1])];
        }
    if (bb) {
        const m = 8 * px;
        bb = [bb[0]-m, bb[1]-m, bb[2]+m, bb[3]+m];
        const bbr = el("rect", { class: "bbox", x: bb[0], y: bb[1],
                     width: bb[2]-bb[0], height: bb[3]-bb[1],
                     "stroke-width": px }, editorG);
        // dragging anywhere inside the box (not on a control) moves the letter
        bbr.addEventListener("pointerdown", ev => {
            ev.stopPropagation();
            startDrag(ev, { type: "move", entry: sel.entry,
                            t0: { ...e.transform } });
        });
        const hs = 5 * px;
        const sh = el("rect", { class: "scale-handle",
            x: bb[2]-hs, y: bb[3]-hs, width: 2*hs, height: 2*hs,
            "stroke-width": px }, editorG);
        sh.addEventListener("pointerdown", ev => {
            ev.stopPropagation();
            startDrag(ev, { type: "scale", entry: sel.entry,
                            t0: { ...e.transform } });
        });
        const o = [e.transform.tx, e.transform.ty];
        el("path", { class: "origin", "stroke-width": px,
            d: `M ${o[0]-5*px} ${o[1]} H ${o[0]+5*px}` +
               ` M ${o[0]} ${o[1]-5*px} V ${o[1]+5*px}` }, editorG);
    }

    e.contours.forEach((c, ci) => {
        const solved = solveContour(c);

        // Invisible wide hit paths per segment: click = select segment,
        // double-click = insert knot
        if (solved) solved.forEach((s, si) => {
            let d;
            if (s[0] === "line")
                d = `M ${s[1][0]} ${s[1][1]} L ${s[2][0]} ${s[2][1]}`;
            else
                d = `M ${s[1][0]} ${s[1][1]} C ${s[2][0]} ${s[2][1]}` +
                    ` ${s[3][0]} ${s[3][1]} ${s[4][0]} ${s[4][1]}`;
            const hp = el("path", {
                d, fill: "none", stroke: "transparent",
                "stroke-width": 10 * px / e.transform.s,
            }, editorG);
            hp.setAttribute("transform",
                `translate(${e.transform.tx},${e.transform.ty})` +
                ` scale(${e.transform.s},${-e.transform.s})`);
            hp.style.cursor = "pointer";
            hp.addEventListener("pointerdown", ev => {
                ev.stopPropagation();
                sel.seg = { ci, si }; sel.knot = null;
                renderEditor(); renderInspector();
            });
        });

        // Tension badges (metafont mode)
        if (mode === "metafont" && solved) c.segments.forEach((s, si) => {
            if (s.type !== "curve") return;
            const mid = e2i(e, bezPoint(solved[si], 0.5));
            const tOut = s.tension != null ? s.tension
                : (s.tension_out != null ? s.tension_out : 1);
            const tIn = s.tension != null ? s.tension
                : (s.tension_in != null ? s.tension_in : 1);
            const label = tOut === tIn ? String(round(tOut, 2))
                : `${round(tOut, 2)}/${round(tIn, 2)}`;
            const isDefault = tOut === 1 && tIn === 1;
            const selCls = (sel.seg && sel.seg.ci === ci && sel.seg.si === si)
                ? " selected" : "";
            const g = el("g", { class: "tension-badge" +
                (isDefault ? " default" : "") + selCls }, editorG);
            const tw = (label.length * 6 + 8) * px, th = 13 * px;
            el("rect", { x: mid[0]-tw/2, y: mid[1]-th/2, width: tw,
                         height: th, "stroke-width": px, rx: 3*px }, g);
            const txt = el("text", { x: mid[0], y: mid[1] }, g);
            txt.textContent = label;
            txt.style.fontSize = (10 * px) + "px";
            g.addEventListener("pointerdown", ev => {
                ev.stopPropagation();
                sel.seg = { ci, si }; sel.knot = null;
                renderEditor(); renderInspector();
            });
        });

        // Bezier control handles
        if (mode === "bezier" && solved) solved.forEach((s, si) => {
            if (s[0] !== "curve") return;
            const p0 = e2i(e, s[1]), c1 = e2i(e, s[2]);
            const c2 = e2i(e, s[3]), p1 = e2i(e, s[4]);
            el("line", { class: "ctrl-line", x1: p0[0], y1: p0[1],
                         x2: c1[0], y2: c1[1], "stroke-width": px }, editorG);
            el("line", { class: "ctrl-line", x1: p1[0], y1: p1[1],
                         x2: c2[0], y2: c2[1], "stroke-width": px }, editorG);
            for (const [which, P] of [["c1", c1], ["c2", c2]]) {
                const cp = el("circle", { class: "ctrl-pt", cx: P[0],
                    cy: P[1], r: 3.5 * px, "stroke-width": px }, editorG);
                cp.addEventListener("pointerdown", ev => {
                    ev.stopPropagation();
                    startDrag(ev, { type: "ctrl", entry: sel.entry, ci, si,
                                    which, solvedSeg: deepCopy(s) });
                });
            }
        });

        // Direction arrows (metafont mode)
        if (mode === "metafont") c.knots.forEach((k, ki) => {
            const dirs = knotDirs(c, solved, ki);
            const K = e2i(e, [k.x, k.y]);
            const alen = 26 * px;
            if (dirs.out != null) {
                const a = -dirs.out * Math.PI / 180; // image y is flipped
                const tip = [K[0] + alen*Math.cos(a), K[1] + alen*Math.sin(a)];
                const t = arrow(editorG, K, tip, dirs.outAuto);
                t.addEventListener("pointerdown", ev => {
                    ev.stopPropagation();
                    startDrag(ev, { type: "dir", entry: sel.entry, ci, ki,
                                    side: "dir_out" });
                });
                t.addEventListener("dblclick", ev => {
                    ev.stopPropagation();
                    pushUndo();
                    c.knots[ki].dir_out = null;
                    afterChange();
                });
            }
            if (dirs.inn != null) {
                const a = -dirs.inn * Math.PI / 180;
                const tail = [K[0] - alen*Math.cos(a), K[1] - alen*Math.sin(a)];
                const t = arrow(editorG, K, tail, dirs.innAuto);
                t.addEventListener("pointerdown", ev => {
                    ev.stopPropagation();
                    startDrag(ev, { type: "dir", entry: sel.entry, ci, ki,
                                    side: "dir_in" });
                });
                t.addEventListener("dblclick", ev => {
                    ev.stopPropagation();
                    pushUndo();
                    c.knots[ki].dir_in = null;
                    afterChange();
                });
            }
        });

        // Knots (both modes, on top)
        c.knots.forEach((k, ki) => {
            const K = e2i(e, [k.x, k.y]);
            const isSel = sel.knot && sel.knot.ci === ci && sel.knot.ki === ki;
            const cir = el("circle", {
                class: "knot" + (isSel ? " selected" : ""),
                cx: K[0], cy: K[1], r: 4.5 * px,
                "stroke-width": 1.5 * px }, editorG);
            cir.addEventListener("pointerdown", ev => {
                ev.stopPropagation();
                sel.knot = { ci, ki }; sel.seg = null;
                startDrag(ev, { type: "knot", entry: sel.entry, ci, ki });
                renderEditor();
                renderInspector();
            });
        });
    });
}

// ---------------------------------------------------------------- sidebar

function renderSidebar() {
    const sb = document.getElementById("sidebar");
    sb.textContent = "";
    let lastCell = null;
    data.entries.forEach((e, i) => {
        if (e.cell !== lastCell) {
            html(sb, "div", "cell-label", e.cell);
            lastCell = e.cell;
        }
        const row = html(sb, "div",
            "entry" + (i === sel.entry ? " selected" : ""));
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = !hidden.has(e.id);
        cb.addEventListener("click", ev => {
            ev.stopPropagation();
            if (cb.checked) hidden.delete(e.id); else hidden.add(e.id);
            renderGlyphs();
        });
        row.appendChild(cb);
        html(row, "span", null, e.id);
        html(row, "span", "glyphname", e.glyph);
        row.addEventListener("click", () => selectEntry(i, true));
    });
}

function selectEntry(i, zoom) {
    sel.entry = i;
    sel.knot = null;
    sel.seg = null;
    if (zoom && i >= 0) {
        const e = data.entries[i];
        let bb = null;
        for (const c of e.contours)
            for (const k of c.knots) {
                const P = e2i(e, [k.x, k.y]);
                if (!bb) bb = [P[0], P[1], P[0], P[1]];
                bb = [Math.min(bb[0], P[0]), Math.min(bb[1], P[1]),
                      Math.max(bb[2], P[0]), Math.max(bb[3], P[1])];
            }
        if (bb) {
            const m = 30;
            view.w = Math.max((bb[2] - bb[0]) * 3, bb[2] - bb[0] + 2*m, 70);
            view.x = (bb[0] + bb[2]) / 2 - view.w / 2;
            const asp = svg.clientHeight / Math.max(1, svg.clientWidth);
            view.y = (bb[1] + bb[3]) / 2 - view.w * asp / 2;
            updateViewBox();
        }
    }
    renderSidebar();
    renderGlyphs();
    renderEditor();
    renderInspector();
}

// --------------------------------------------------------------- inspector

function numInput(parent, label, value, step, oncommit, disabled) {
    const row = html(parent, "div", "row");
    html(row, "label", null, label);
    const inp = document.createElement("input");
    inp.type = "number";
    inp.step = step;
    if (value != null) inp.value = round(value, 3);
    inp.disabled = !!disabled;
    inp.addEventListener("change", () => {
        const v = parseFloat(inp.value);
        if (!isNaN(v)) { pushUndo(); oncommit(v); afterChange(); }
    });
    row.appendChild(inp);
    return inp;
}

function renderInspector() {
    const ins = document.getElementById("inspector");
    ins.textContent = "";
    if (sel.entry < 0) {
        html(ins, "div", "hint",
            "Select a letter in the sidebar (click zooms to its cell), " +
            "or click a curve on the canvas.");
        return;
    }
    const e = data.entries[sel.entry];
    html(ins, "h3", null, `${e.id}  (glyph ${e.glyph})`);

    html(ins, "div", "hint", "placement (image px, px per unit)");
    numInput(ins, "tx", e.transform.tx, 0.5, v => e.transform.tx = v);
    numInput(ins, "ty", e.transform.ty, 0.5, v => e.transform.ty = v);
    numInput(ins, "scale", e.transform.s, 0.01,
             v => { if (v > 0.05) e.transform.s = v; });

    if (sel.knot) {
        const { ci, ki } = sel.knot;
        const c = e.contours[ci];
        const k = c.knots[ki];
        const solved = solveContour(c);
        const dirs = knotDirs(c, solved, ki);
        html(ins, "hr");
        html(ins, "h3", null, `knot ${ki} (contour ${ci})`);
        numInput(ins, "x", k.x, 0.1, v => k.x = v);
        numInput(ins, "y", k.y, 0.1, v => k.y = v);

        for (const [side, label] of [["dir_out", "dir out"],
                                     ["dir_in", "dir in"]]) {
            const has = side === "dir_out" ? dirs.out != null
                                           : dirs.inn != null;
            if (!has) continue;
            const explicit = k[side] != null;
            const eff = side === "dir_out" ? dirs.out : dirs.inn;
            const row = html(ins, "div", "row");
            html(row, "label", null, label + " °");
            const btn = html(row, "button", explicit ? "on" : "",
                             explicit ? "pinned" : "auto");
            btn.addEventListener("click", () => {
                pushUndo();
                k[side] = explicit ? null : round(eff, 1);
                afterChange();
            });
            const inp = document.createElement("input");
            inp.type = "number"; inp.step = 1;
            inp.value = eff != null ? round(eff, 1) : "";
            inp.disabled = !explicit;
            if (!explicit) inp.classList.add("auto-val");
            inp.addEventListener("change", () => {
                const v = parseFloat(inp.value);
                if (!isNaN(v)) { pushUndo(); k[side] = v; afterChange(); }
            });
            row.appendChild(inp);
        }
        const adj = knotSegs(c, ki);
        const endpoint = adj.out == null || adj.inn == null;
        if (endpoint || k.curl_out != null || k.curl_in != null) {
            const side = adj.inn == null ? "curl_out" : "curl_in";
            numInput(ins, side.replace("_", " "),
                k[side] != null ? k[side] : 1, 0.1,
                v => k[side] = (v === 1 ? null : v));
        }
        const delBtn = html(ins, "button", null, "delete knot");
        delBtn.addEventListener("click", () => deleteKnot(ci, ki));
    }

    if (sel.seg) {
        const { ci, si } = sel.seg;
        const c = e.contours[ci];
        const s = c.segments[si];
        html(ins, "hr");
        html(ins, "h3", null, `segment ${si} (contour ${ci})`);
        const row = html(ins, "div", "row");
        html(row, "label", null, "type");
        const btn = html(row, "button", null, s.type);
        btn.addEventListener("click", () => {
            pushUndo();
            if (s.type === "line") {
                s.type = "curve";
                if (s.tension == null && s.tension_out == null)
                    s.tension = 1;
            } else {
                s.type = "line";
            }
            afterChange();
        });
        if (s.type === "curve") {
            const tOut = s.tension != null ? s.tension
                : (s.tension_out != null ? s.tension_out : 1);
            const tIn = s.tension != null ? s.tension
                : (s.tension_in != null ? s.tension_in : 1);
            numInput(ins, "tension out", tOut, 0.1, v => {
                v = Math.max(0.75, v);
                delete s.tension;
                s.tension_out = v; s.tension_in = tIn;
                normalizeTension(s);
            });
            numInput(ins, "tension in", tIn, 0.1, v => {
                v = Math.max(0.75, v);
                delete s.tension;
                s.tension_out = tOut; s.tension_in = v;
                normalizeTension(s);
            });
            html(ins, "div", "hint",
                 "keyboard: [ and ] adjust tension by 0.1");
        }
    }

    html(ins, "hr");
    html(ins, "div", "hint",
        "Modes: M metafont, B bezier. Ghost arrows show the directions " +
        "Hobby's algorithm picked; drag one to pin it, double-click to " +
        "make it automatic again. In bezier mode dragging a handle pins " +
        "both directions and tensions of that segment.");
}

function normalizeTension(s) {
    if (s.tension_out != null && s.tension_out === s.tension_in) {
        s.tension = s.tension_out;
        delete s.tension_out;
        delete s.tension_in;
    }
}

// ------------------------------------------------------------ knot editing

function insertKnot(ci, si, imgPoint) {
    const e = data.entries[sel.entry];
    const c = e.contours[ci];
    const solved = solveContour(c);
    if (!solved) return;
    // find nearest t on the segment
    const target = i2e(e, imgPoint);
    let best = 0.5, bd = Infinity;
    for (let i = 1; i < 40; i++) {
        const t = i / 40;
        const p = bezPoint(solved[si], t);
        const d2 = (p[0]-target[0])**2 + (p[1]-target[1])**2;
        if (d2 < bd) { bd = d2; best = t; }
    }
    const p = bezPoint(solved[si], best);
    pushUndo();
    const newKnot = { x: round(p[0], 3), y: round(p[1], 3),
                      dir_in: null, dir_out: null };
    const orig = c.segments[si];
    const copy = deepCopy(orig);
    c.knots.splice(si + 1, 0, newKnot);
    c.segments.splice(si + 1, 0, copy);
    sel.knot = { ci, ki: si + 1 };
    sel.seg = null;
    afterChange();
}

function deleteKnot(ci, ki) {
    const e = data.entries[sel.entry];
    const c = e.contours[ci];
    const minK = c.cyclic ? 3 : 2;
    if (c.knots.length <= minK) return;
    pushUndo();
    const adj = knotSegs(c, ki);
    if (!c.cyclic && adj.inn == null) {
        c.knots.splice(ki, 1);
        c.segments.splice(0, 1);
    } else if (!c.cyclic && adj.out == null) {
        c.knots.splice(ki, 1);
        c.segments.splice(c.segments.length - 1, 1);
    } else {
        // merge the two adjacent segments; keep the incoming one's params
        c.knots.splice(ki, 1);
        c.segments.splice(adj.out, 1);
    }
    sel.knot = null;
    sel.seg = null;
    afterChange();
}

// ------------------------------------------------------------ interactions

function startDrag(ev, info) {
    drag = info;
    drag.moved = false;
    drag.startImg = screenToImage(ev);
    drag.pointerId = ev.pointerId;
    svg.setPointerCapture(ev.pointerId);
}

svg.addEventListener("pointerdown", ev => {
    // background: pan
    startDrag(ev, { type: "pan", v0: { ...view } });
});

svg.addEventListener("pointermove", ev => {
    if (!drag) return;
    const P = screenToImage(ev);
    const dx = P[0] - drag.startImg[0], dy = P[1] - drag.startImg[1];
    if (!drag.moved && Math.hypot(dx, dy) > 0.5 * pxSize() * 3)
        drag.moved = true;
    if (!drag.moved) return;
    if (!drag.undoPushed && drag.type !== "pan" &&
        drag.type !== "move-wait") {
        pushUndo();
        drag.undoPushed = true;
    }
    const e = sel.entry >= 0 ? data.entries[sel.entry] : null;
    switch (drag.type) {
    case "pan": {
        // recompute from client movement to avoid feedback
        view.x = drag.v0.x - (P[0] - drag.startImg[0]);
        view.y = drag.v0.y - (P[1] - drag.startImg[1]);
        const asp = svg.clientHeight / Math.max(1, svg.clientWidth);
        svg.setAttribute("viewBox",
            `${view.x} ${view.y} ${view.w} ${view.w * asp}`);
        break;
    }
    case "move-wait":
        break;
    case "move": {
        const en = data.entries[drag.entry];
        en.transform.tx = round(drag.t0.tx + dx, 2);
        en.transform.ty = round(drag.t0.ty + dy, 2);
        renderGlyphs(); renderEditor(); renderInspector();
        break;
    }
    case "scale": {
        const en = data.entries[drag.entry];
        const d0 = Math.hypot(drag.startImg[0] - drag.t0.tx,
                              drag.startImg[1] - drag.t0.ty);
        const d1 = Math.hypot(P[0] - drag.t0.tx, P[1] - drag.t0.ty);
        if (d0 > 1e-6 && d1 > 1e-6)
            en.transform.s = round(Math.max(0.05, drag.t0.s * d1 / d0), 4);
        renderGlyphs(); renderEditor(); renderInspector();
        break;
    }
    case "knot": {
        const c = e.contours[drag.ci];
        const k = c.knots[drag.ki];
        const p = i2e(e, P);
        k.x = round(p[0], 3); k.y = round(p[1], 3);
        renderGlyphs(); renderEditor(); renderInspector();
        break;
    }
    case "dir": {
        const c = e.contours[drag.ci];
        const k = c.knots[drag.ki];
        const K = e2i(e, [k.x, k.y]);
        let a = Math.atan2(-(P[1] - K[1]), P[0] - K[0]) * 180 / Math.PI;
        if (drag.side === "dir_in") a = a + 180;
        while (a > 180) a -= 360;
        while (a <= -180) a += 360;
        if (ev.shiftKey) a = Math.round(a / 15) * 15;
        k[drag.side] = round(a, 1);
        renderGlyphs(); renderEditor(); renderInspector();
        break;
    }
    case "ctrl": {
        const c = e.contours[drag.ci];
        const s = drag.solvedSeg;
        const p = i2e(e, P);
        const c1 = drag.which === "c1" ? p : s[2];
        const c2 = drag.which === "c2" ? p : s[3];
        const prm = Hobby.controlsToParams(s[1], c1, c2, s[4]);
        // pin the whole segment: both dirs and both tensions
        const nk = c.knots.length, ns = c.segments.length;
        const kiStart = drag.si;
        const kiEnd = c.cyclic ? (drag.si + 1) % nk : drag.si + 1;
        c.knots[kiStart].dir_out = round(prm.dir_out, 2);
        c.knots[kiEnd].dir_in = round(prm.dir_in, 2);
        const seg = c.segments[drag.si];
        delete seg.tension;
        seg.tension_out = round(Math.max(0.05, prm.tension_out), 3);
        seg.tension_in = round(Math.max(0.05, prm.tension_in), 3);
        normalizeTension(seg);
        renderGlyphs(); renderEditor(); renderInspector();
        break;
    }
    }
});

function endDrag(ev) {
    if (!drag) return;
    const wasClick = !drag.moved;
    const d = drag;
    drag = null;
    if (d.type === "pan" && wasClick) {
        // click on background: deselect knot/segment
        sel.knot = null; sel.seg = null;
        renderEditor(); renderInspector();
        return;
    }
    if (d.undoPushed) scheduleSave();
}
svg.addEventListener("pointerup", endDrag);
svg.addEventListener("pointercancel", endDrag);

// Double-click near a segment of the selected entry inserts a knot there.
// The editor overlay is rebuilt on every selection change, which destroys
// the clicked element mid-gesture and prevents native dblclick events from
// firing, so double clicks are detected manually (capture phase).
let lastDown = { t: 0, x: 0, y: 0 };
svg.addEventListener("pointerdown", ev => {
    const now = performance.now();
    const isDouble = now - lastDown.t < 400 &&
        Math.hypot(ev.clientX - lastDown.x, ev.clientY - lastDown.y) < 6;
    lastDown = { t: now, x: ev.clientX, y: ev.clientY };
    if (isDouble && handleDoubleClick(ev)) {
        // knot inserted: don't let the destroyed target's handlers run
        ev.stopPropagation();
        ev.preventDefault();
    }
}, true);

function handleDoubleClick(ev) {
    if (sel.entry < 0) return false;
    // controls have their own double-click behavior (or none)
    if (ev.target.closest &&
        ev.target.closest(".dir-tip, .ctrl-pt, .knot, .tension-badge, .scale-handle"))
        return false;
    const e = data.entries[sel.entry];
    const P = screenToImage(ev);
    const px = pxSize();
    // ignore double-clicks on/near knots
    for (const c of e.contours)
        for (const k of c.knots) {
            const K = e2i(e, [k.x, k.y]);
            if (Math.hypot(K[0]-P[0], K[1]-P[1]) < 8 * px) return false;
        }
    let best = null;
    e.contours.forEach((c, ci) => {
        const solved = solveContour(c);
        if (!solved) return;
        solved.forEach((s, si) => {
            for (let i = 1; i < 40; i++) {
                const p = e2i(e, bezPoint(s, i / 40));
                const d = Math.hypot(p[0]-P[0], p[1]-P[1]);
                if (!best || d < best.d) best = { d, ci, si };
            }
        });
    });
    if (best && best.d < 8 * px) {
        insertKnot(best.ci, best.si, P);
        return true;
    }
    return false;
}

svg.addEventListener("wheel", ev => {
    ev.preventDefault();
    const P = screenToImage(ev);
    const f = Math.exp(ev.deltaY * 0.0015);
    const w2 = Math.min(Math.max(view.w * f, 20), 4000);
    const scale = w2 / view.w;
    view.x = P[0] - (P[0] - view.x) * scale;
    view.y = P[1] - (P[1] - view.y) * scale;
    view.w = w2;
    updateViewBox();
}, { passive: false });

// ---------------------------------------------------------------- keyboard

document.addEventListener("keydown", ev => {
    if (ev.target.tagName === "INPUT") return;
    const e = sel.entry >= 0 ? data.entries[sel.entry] : null;
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "z") {
        ev.preventDefault();
        if (ev.shiftKey) redo(); else undo();
        return;
    }
    switch (ev.key) {
    case "m": case "M": setMode("metafont"); break;
    case "b": case "B": setMode("bezier"); break;
    case "Delete": case "Backspace":
        if (sel.knot) { ev.preventDefault();
                        deleteKnot(sel.knot.ci, sel.knot.ki); }
        break;
    case "[": case "]":
        if (e && sel.seg) {
            const s = e.contours[sel.seg.ci].segments[sel.seg.si];
            if (s.type !== "curve") break;
            pushUndo();
            const dlt = ev.key === "]" ? 0.1 : -0.1;
            if (s.tension != null) {
                s.tension = round(Math.max(0.75, s.tension + dlt), 3);
            } else {
                s.tension_out = round(Math.max(0.75,
                    (s.tension_out || 1) + dlt), 3);
                s.tension_in = round(Math.max(0.75,
                    (s.tension_in || 1) + dlt), 3);
                normalizeTension(s);
            }
            afterChange();
        }
        break;
    case "ArrowLeft": case "ArrowRight": case "ArrowUp": case "ArrowDown":
        if (e && sel.knot) {
            ev.preventDefault();
            pushUndo();
            const k = e.contours[sel.knot.ci].knots[sel.knot.ki];
            const st = ev.shiftKey ? 0.5 : 0.05;
            if (ev.key === "ArrowLeft") k.x = round(k.x - st, 3);
            if (ev.key === "ArrowRight") k.x = round(k.x + st, 3);
            if (ev.key === "ArrowUp") k.y = round(k.y + st, 3);
            if (ev.key === "ArrowDown") k.y = round(k.y - st, 3);
            afterChange();
        }
        break;
    }
});

// ------------------------------------------------------------------ modes

function setMode(m) {
    mode = m;
    document.getElementById("mode-metafont").classList
        .toggle("active", m === "metafont");
    document.getElementById("mode-bezier").classList
        .toggle("active", m === "bezier");
    renderEditor();
}
document.getElementById("mode-metafont")
    .addEventListener("click", () => setMode("metafont"));
document.getElementById("mode-bezier")
    .addEventListener("click", () => setMode("bezier"));
document.getElementById("undo").addEventListener("click", undo);
document.getElementById("redo").addEventListener("click", redo);
document.getElementById("opacity")
    .addEventListener("input", renderGlyphs);
document.getElementById("only-selected")
    .addEventListener("change", renderGlyphs);
document.getElementById("show-centerline")
    .addEventListener("change", renderGlyphs);
document.getElementById("export").addEventListener("click", () => {
    const blob = new Blob([jsonSerialize(data)],
                          { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "letters.json";
    a.click();
    URL.revokeObjectURL(a.href);
});

window.addEventListener("resize", updateViewBox);

// console debugging aid
window.dbg = () => ({ drag, sel, mode, view });

// ------------------------------------------------------------------- init

async function init() {
    const r = await fetch("letters.json");
    data = await r.json();
    templateImg.setAttribute("href", "../" + data.image);
    templateImg.setAttribute("width", data.image_size[0]);
    templateImg.setAttribute("height", data.image_size[1]);
    view = { x: -10, y: -10, w: data.image_size[0] + 20 };
    renderSidebar();
    renderGlyphs();
    updateViewBox();
    renderInspector();
    setSaveStatus("saved", "saved");
}
init();
