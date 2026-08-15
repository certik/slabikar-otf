/*
 * METAFONT path solving (Hobby's algorithm) in JavaScript.
 *
 * This is a direct port of solve_path() and its helpers from gen/bezier.py;
 * see the comments there and mf.web part 18 "Choosing control points".
 * gen/test_bezier.py checks that both implementations agree with each other
 * and with a real MetaPost binary.
 *
 * Works both in the browser (defines window.Hobby) and under node
 * (module.exports / CLI: `node hobby.js` reads {cases: [...]} JSON on stdin
 * and prints the solved control points as JSON).
 */
"use strict";

(function (global) {

function reduceAngle(a) {
    // Reduce an angle in radians to (-pi, pi]
    while (a > Math.PI) a -= 2 * Math.PI;
    while (a <= -Math.PI) a += 2 * Math.PI;
    return a;
}

function velocity(theta, phi, tau) {
    // METAFONT's velocity function: rho(theta, phi)/(3 tau), capped at 4
    const a = Math.sqrt(2);
    const b = 1 / 16;
    const c = (3 - Math.sqrt(5)) / 2;
    const st = Math.sin(theta), ct = Math.cos(theta);
    const sf = Math.sin(phi), cf = Math.cos(phi);
    const alpha = a * (st - b * sf) * (sf - b * st) * (ct - cf);
    const rho = (2 + alpha) / (1 + (1 - c) * ct + c * cf);
    return Math.min(rho / (3 * tau), 4.0);
}

function setControls(z0, z1, theta, phi, tau0, tau1) {
    const dx = z1[0] - z0[0], dy = z1[1] - z0[1];
    const rr = velocity(theta, phi, tau0);
    const ss = velocity(phi, theta, tau1);
    const st = Math.sin(theta), ct = Math.cos(theta);
    const sf = Math.sin(phi), cf = Math.cos(phi);
    return [
        [z0[0] + rr * (dx * ct - dy * st), z0[1] + rr * (dy * ct + dx * st)],
        [z1[0] - ss * (dx * cf + dy * sf), z1[1] - ss * (dy * cf - dx * sf)],
    ];
}

function curlRatio(gamma, alpha, beta) {
    const num = (3 - alpha) * alpha * alpha * gamma + beta * beta * beta;
    const den = alpha * alpha * alpha * gamma + (3 - beta) * beta * beta;
    return num >= 4 * den ? 4.0 : num / den;
}

function segmentControls(pts, theta, psi, tensOut, tensIn) {
    const out = [];
    for (let k = 0; k < pts.length - 1; k++) {
        const phi = -psi[k + 1] - theta[k + 1];
        out.push(setControls(pts[k], pts[k + 1], theta[k], phi,
                             tensOut[k], tensIn[k]));
    }
    return out;
}

function solveRun(pts, tensOut, tensIn, bc0, bcn) {
    const n = pts.length - 1;
    const d = new Array(n), ang = new Array(n);
    for (let k = 0; k < n; k++) {
        const dx = pts[k + 1][0] - pts[k][0];
        const dy = pts[k + 1][1] - pts[k][1];
        d[k] = Math.hypot(dx, dy) || 1e-30;
        ang[k] = Math.atan2(dy, dx);
    }
    const psi = new Array(n + 1).fill(0);
    for (let k = 1; k < n; k++) psi[k] = reduceAngle(ang[k] - ang[k - 1]);

    const alpha = tensOut.map(t => 1 / t);
    const beta = [null].concat(tensIn.map(t => 1 / t)); // beta[k], k=1..n

    const theta = new Array(n + 1).fill(0);
    if (n === 1 && bc0[0] === "given" && bcn[0] === "given") {
        theta[0] = reduceAngle(bc0[1] - ang[0]);
        theta[1] = reduceAngle(bcn[1] - ang[0]);
        return segmentControls(pts, theta, psi, tensOut, tensIn);
    }
    if (n === 1 && bc0[0] === "curl" && bcn[0] === "curl") {
        return segmentControls(pts, theta, psi, tensOut, tensIn);
    }

    const u = new Array(n + 1).fill(0), v = new Array(n + 1).fill(0);
    if (bc0[0] === "given") {
        u[0] = 0;
        v[0] = reduceAngle(bc0[1] - ang[0]);
    } else {
        u[0] = curlRatio(bc0[1], alpha[0], beta[1]);
        v[0] = -u[0] * psi[1];
    }
    for (let k = 1; k < n; k++) {
        const A = alpha[k - 1] / (beta[k] * beta[k] * d[k - 1]);
        const B = (3 - alpha[k - 1]) / (beta[k] * beta[k] * d[k - 1]);
        const C = (3 - beta[k + 1]) / (alpha[k] * alpha[k] * d[k]);
        const D = beta[k + 1] / (alpha[k] * alpha[k] * d[k]);
        const t = B - u[k - 1] * A + C;
        u[k] = D / t;
        v[k] = (-B * psi[k] - D * psi[k + 1] - A * v[k - 1]) / t;
    }
    if (bcn[0] === "given") {
        theta[n] = reduceAngle(bcn[1] - ang[n - 1]);
    } else {
        const ff = curlRatio(bcn[1], beta[n], alpha[n - 1]);
        theta[n] = -ff * v[n - 1] / (1 - ff * u[n - 1]);
    }
    for (let k = n - 1; k >= 0; k--) theta[k] = v[k] - u[k] * theta[k + 1];
    return segmentControls(pts, theta, psi, tensOut, tensIn);
}

function solveCycle(pts, tensOut, tensIn) {
    const n = pts.length;
    const d = new Array(n), ang = new Array(n);
    for (let k = 0; k < n; k++) {
        const dx = pts[(k + 1) % n][0] - pts[k][0];
        const dy = pts[(k + 1) % n][1] - pts[k][1];
        d[k] = Math.hypot(dx, dy) || 1e-30;
        ang[k] = Math.atan2(dy, dx);
    }
    const psi = new Array(n + 2).fill(0);
    for (let k = 1; k <= n; k++) psi[k] = reduceAngle(ang[k % n] - ang[k - 1]);
    psi[n + 1] = psi[1];

    const al = k => 1 / tensOut[k % n];
    const be = k => 1 / tensIn[(k - 1 + n) % n];
    const dd = k => d[k % n];

    const u = new Array(n + 1).fill(0);
    const v = new Array(n + 1).fill(0);
    const w = new Array(n + 1).fill(0);
    w[0] = 1;
    for (let k = 1; k <= n; k++) {
        const A = al(k - 1) / (be(k) * be(k) * dd(k - 1));
        const B = (3 - al(k - 1)) / (be(k) * be(k) * dd(k - 1));
        const C = (3 - be(k + 1)) / (al(k) * al(k) * dd(k));
        const D = be(k + 1) / (al(k) * al(k) * dd(k));
        const t = B - u[k - 1] * A + C;
        u[k] = D / t;
        v[k] = (-B * psi[k] - D * psi[k + 1] - A * v[k - 1]) / t;
        w[k] = -A * w[k - 1] / t;
    }
    let aa = 0, bb = 1;
    const order = [];
    for (let k = n - 1; k >= 1; k--) order.push(k);
    order.push(n);
    for (const k of order) {
        aa = v[k] - aa * u[k];
        bb = w[k] - bb * u[k];
    }
    const thetaN = aa / (1 - bb);
    v[0] = thetaN;
    for (let k = 1; k < n; k++) v[k] += thetaN * w[k];
    const theta = new Array(n + 1).fill(0);
    theta[n] = thetaN;
    for (let k = n - 1; k >= 0; k--) theta[k] = v[k] - u[k] * theta[k + 1];

    const out = [];
    for (let k = 0; k < n; k++) {
        const phi = -psi[k + 1] - theta[k + 1];
        out.push(setControls(pts[k], pts[(k + 1) % n], theta[k], phi,
                             tensOut[k], tensIn[k]));
    }
    return out;
}

// See solve_path() in gen/bezier.py for the full documentation.
// knots: [{x, y, dir_in, dir_out, curl_in, curl_out}] (dirs in degrees, null = free)
// segments: [{type: "curve"|"line", tension | tension_out+tension_in}]
// Returns one entry per segment:
//   ["line", [x0,y0], [x1,y1]] or ["curve", [x0,y0], c1, c2, [x1,y1]]
function solvePath(knots, segments, cyclic) {
    const nk = knots.length, ns = segments.length;
    if (cyclic ? ns !== nk : ns !== nk - 1) {
        throw new Error("knot/segment count mismatch");
    }
    const rad = a => a * Math.PI / 180;
    const segTensions = s => {
        if (s.tension != null) return [s.tension, s.tension];
        return [s.tension_out != null ? s.tension_out : 1,
                s.tension_in != null ? s.tension_in : 1];
    };
    const knotXY = i => {
        const k = knots[((i % nk) + nk) % nk];
        return [k.x, k.y];
    };
    const isLine = j => segments[((j % ns) + ns) % ns].type === "line";
    const isBreak = i => {
        const k = knots[i];
        if (k.dir_in != null || k.dir_out != null) return true;
        if (k.curl_in != null || k.curl_out != null) return true;
        if (cyclic) return isLine(i - 1) || isLine(i);
        if (i === 0 || i === nk - 1) return true;
        return isLine(i - 1) || isLine(i);
    };

    const breaks = [];
    for (let i = 0; i < nk; i++) if (isBreak(i)) breaks.push(i);

    if (cyclic && breaks.length === 0) {
        const pts = [];
        for (let i = 0; i < nk; i++) pts.push(knotXY(i));
        const tens = segments.map(segTensions);
        const ctrl = solveCycle(pts, tens.map(t => t[0]), tens.map(t => t[1]));
        const out = [];
        for (let k = 0; k < ns; k++) {
            out.push(["curve", pts[k], ctrl[k][0], ctrl[k][1],
                      pts[(k + 1) % nk]]);
        }
        return out;
    }

    const result = new Array(ns).fill(null);
    const runs = [];
    if (cyclic) {
        for (let bi = 0; bi < breaks.length; bi++) {
            const i0 = breaks[bi];
            const i1 = breaks[(bi + 1) % breaks.length];
            let length = ((i1 - i0) % nk + nk) % nk;
            if (length === 0) length = nk;
            runs.push([i0, length]);
        }
    } else {
        for (let bi = 0; bi < breaks.length - 1; bi++) {
            runs.push([breaks[bi], breaks[bi + 1] - breaks[bi]]);
        }
    }

    for (const [i0, length] of runs) {
        const segs = [];
        for (let j = 0; j < length; j++) segs.push((i0 + j) % ns);
        if (length === 1 && isLine(segs[0])) {
            result[segs[0]] = ["line", knotXY(i0), knotXY(i0 + 1)];
            continue;
        }
        const pts = [];
        for (let j = 0; j <= length; j++) pts.push(knotXY(i0 + j));
        const tens = segs.map(j => segTensions(segments[j]));

        const k0 = knots[i0 % nk];
        const kn = knots[(i0 + length) % nk];
        let d0 = k0.dir_out != null ? k0.dir_out : k0.dir_in;
        let dn = kn.dir_in != null ? kn.dir_in : kn.dir_out;
        const bc0 = d0 != null ? ["given", rad(d0)]
            : ["curl", k0.curl_out != null ? k0.curl_out
                     : (k0.curl_in != null ? k0.curl_in : 1)];
        const bcn = dn != null ? ["given", rad(dn)]
            : ["curl", kn.curl_in != null ? kn.curl_in
                     : (kn.curl_out != null ? kn.curl_out : 1)];

        const ctrl = solveRun(pts, tens.map(t => t[0]), tens.map(t => t[1]),
                              bc0, bcn);
        for (let j = 0; j < segs.length; j++) {
            result[segs[j]] = ["curve", pts[j], ctrl[j][0], ctrl[j][1],
                               pts[j + 1]];
        }
    }
    return result;
}

// Inverse problem, used by the traditional-bezier editing mode: given actual
// control points of a segment, find the equivalent metafont parameters
// (directions at both ends, and the tensions that reproduce the handle
// lengths given those directions).
function controlsToParams(z0, c1, c2, z1) {
    const dx = z1[0] - z0[0], dy = z1[1] - z0[1];
    const dchord = Math.hypot(dx, dy);
    const chordAngle = Math.atan2(dy, dx);
    const h1x = c1[0] - z0[0], h1y = c1[1] - z0[1];
    const h2x = z1[0] - c2[0], h2y = z1[1] - c2[1];
    const dirOut = Math.atan2(h1y, h1x);
    const dirIn = Math.atan2(h2y, h2x);
    const theta = reduceAngle(dirOut - chordAngle);
    const phi = reduceAngle(chordAngle - dirIn);
    // velocity(tau=1) gives rho/3; |h1| = velocity * dchord  =>  tau
    const v1 = velocity(theta, phi, 1);
    const v2 = velocity(phi, theta, 1);
    const l1 = Math.hypot(h1x, h1y), l2 = Math.hypot(h2x, h2y);
    return {
        dir_out: dirOut * 180 / Math.PI,
        dir_in: dirIn * 180 / Math.PI,
        tension_out: l1 > 1e-12 ? v1 * dchord / l1 : 1,
        tension_in: l2 > 1e-12 ? v2 * dchord / l2 : 1,
    };
}

const Hobby = { solvePath, controlsToParams, velocity, reduceAngle };

if (typeof module !== "undefined" && module.exports) {
    module.exports = Hobby;
    if (require.main === module) {
        // CLI for cross-checking against gen/bezier.py: read JSON cases on
        // stdin, print solved paths as JSON.
        let src = "";
        process.stdin.on("data", d => { src += d; });
        process.stdin.on("end", () => {
            const inp = JSON.parse(src);
            const out = inp.cases.map(c =>
                solvePath(c.knots, c.segments, c.cyclic));
            process.stdout.write(JSON.stringify(out));
        });
    }
} else {
    global.Hobby = Hobby;
}

})(typeof window !== "undefined" ? window : globalThis);
