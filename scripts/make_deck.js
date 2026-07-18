/**
 * GuardianEye pitch deck: image-rich dark deck built from real product output.
 * Usage: node scripts/make_deck.js   (run from repo root)
 * Assets: out/deck_assets/*.png (see README), out/showcase.mp4 (demo slide),
 *         out/deck_poster.png (video poster). Re-run after rebuilding those.
 */
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const {
  FaUsers, FaHeartPulse, FaTriangleExclamation, FaVideo, FaBolt, FaLock, FaPlay, FaEye,
} = require("react-icons/fa6");

const BG = "0E1014";
const CARD = "1A1E26";
const FG = "E8E8E8";
const DIM = "9AA0AA";
const RED = "EB5050";
const FONT = "Arial";
const W = 13.33, H = 7.5;

async function iconPng(Icon, color) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Icon, { color: "#" + color, size: 256 })
  );
  const buf = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const root = process.cwd();
  const A = (f) => path.join(root, "out", "deck_assets", f);
  const video = path.join(root, "out", "showcase.mp4");
  const poster = path.join(root, "out", "deck_poster.png");
  for (const f of ["hero.png", "crush.png", "collapse.png", "edge.png", "counting.png", "depth_art.png"]) {
    if (!fs.existsSync(A(f))) throw new Error("missing asset " + f);
  }
  if (!fs.existsSync(video)) throw new Error("missing out/showcase.mp4");

  const ic = {
    users: await iconPng(FaUsers, RED),
    heart: await iconPng(FaHeartPulse, RED),
    warn: await iconPng(FaTriangleExclamation, RED),
    eye: await iconPng(FaEye, RED),
    video: await iconPng(FaVideo, FG),
    bolt: await iconPng(FaBolt, FG),
    lock: await iconPng(FaLock, FG),
    play: await iconPng(FaPlay, FG),
  };

  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.theme = { bodyFontFace: FONT, headFontFace: FONT };

  const veil = (s, transparency) =>
    s.addShape(pres.ShapeType.rect, {
      x: 0, y: 0, w: W, h: H, line: { type: "none" },
      fill: { color: BG, transparency },
    });

  // Framed image tile with a caption bar; sizing "cover" crops uniformly.
  const tile = (s, img, x, y, w, h) => {
    s.addImage({ path: img, x, y, w, h, sizing: { type: "cover", w, h } });
    s.addShape(pres.ShapeType.rect, {
      x, y, w, h, fill: { color: BG, transparency: 100 },
      line: { color: RED, width: 1.5 },
    });
  };

  // ---- 1. Title: full-bleed crowd ---------------------------------------
  let s = pres.addSlide();
  s.background = { path: A("hero.png") };
  veil(s, 30);
  s.addText("GUARDIANEYE", {
    x: 0.7, y: 2.15, w: 11.93, h: 1.5, margin: 0,
    fontSize: 80, bold: true, color: FG, align: "center", charSpacing: 8,
    shadow: { type: "outer", color: "000000", blur: 12, offset: 3, angle: 90, opacity: 0.7 },
  });
  s.addText("The AI safety officer for stadiums", {
    x: 0.7, y: 3.75, w: 11.93, h: 0.6, margin: 0,
    fontSize: 30, bold: true, color: RED, align: "center",
    shadow: { type: "outer", color: "000000", blur: 8, offset: 2, angle: 90, opacity: 0.7 },
  });
  s.addText("Sees every fan  ·  counts every crowd  ·  calls for help first", {
    x: 0.7, y: 4.55, w: 11.93, h: 0.5, margin: 0, fontSize: 18, color: FG, align: "center",
  });
  s.addText("Sports World Cup Hackathon 2026  ·  Track 4: Sports Business & Operations", {
    x: 0.7, y: 6.85, w: 11.93, h: 0.4, margin: 0, fontSize: 12, color: DIM, align: "center",
  });
  s.addNotes(
    "That background is our actual demo footage. 80,000 people in a stadium and the " +
    "safety plan is still binoculars and radios. GuardianEye turns the cameras a venue " +
    "already owns into a safety officer that never blinks."
  );

  // ---- 2. Problem: three stat cards -------------------------------------
  s = pres.addSlide();
  s.background = { color: BG };
  s.addText("Stadium safety is a human squinting at a wall of screens", {
    x: 0.9, y: 0.55, w: 11.5, h: 0.9, margin: 0, fontSize: 33, bold: true, color: FG,
  });
  const stats = [
    { icon: ic.heart, n: "-10% / min", t: "cardiac-arrest survival without CPR.\nMedics find out last." },
    { icon: ic.users, n: "135 dead", t: "Kanjuruhan Stadium crush, 2022.\nThe cameras watched it happen." },
    { icon: ic.eye, n: "5 px", t: "a fan in the far tier. Invisible to\nhumans and ordinary AI alike." },
  ];
  stats.forEach((st, i) => {
    const x = 0.9 + i * 3.95;
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 1.85, w: 3.6, h: 4.1, fill: { color: CARD }, rectRadius: 0.14, line: { type: "none" },
    });
    s.addShape(pres.ShapeType.ellipse, {
      x: x + 1.375, y: 2.25, w: 0.85, h: 0.85, fill: { color: BG }, line: { type: "none" },
    });
    s.addImage({ data: st.icon, x: x + 1.575, y: 2.45, w: 0.45, h: 0.45 });
    s.addText(st.n, {
      x, y: 3.4, w: 3.6, h: 0.9, margin: 0, fontSize: 40, bold: true, color: RED, align: "center",
    });
    s.addText(st.t, {
      x: x + 0.25, y: 4.45, w: 3.1, h: 1.3, margin: 0, fontSize: 14, color: FG, align: "center",
    });
  });
  s.addText("One late response is a tragedy. Venues run on hope.", {
    x: 0.9, y: 6.45, w: 11.5, h: 0.5, margin: 0, fontSize: 16, italic: true, color: DIM,
  });

  // ---- 3. Product: three real screenshots -------------------------------
  s = pres.addSlide();
  s.background = { color: BG };
  s.addText("Three ways a crowd kills. One system watching for all of them.", {
    x: 0.9, y: 0.55, w: 11.5, h: 0.9, margin: 0, fontSize: 32, bold: true, color: FG,
  });
  const shots = [
    { img: A("crush.png"), h: "CROWD CRUSH", t: "Live people/m2 density map.\nAlert before the crush, not after." },
    { img: A("collapse.png"), h: "COLLAPSE", t: "Person down, confirmed in seconds.\n“MEDICAL EMERGENCY - ZONE E4”" },
    { img: A("edge.png"), h: "EDGE FALLS", t: "Depth-cliff hazards + trajectory.\nFlags the fall before it happens." },
  ];
  shots.forEach((sh, i) => {
    const x = 0.9 + i * 3.95;
    tile(s, sh.img, x, 1.75, 3.6, 2.6);
    s.addText(sh.h, {
      x, y: 4.55, w: 3.6, h: 0.45, margin: 0, fontSize: 19, bold: true, color: RED, align: "center",
    });
    s.addText(sh.t, {
      x, y: 5.05, w: 3.6, h: 0.95, margin: 0, fontSize: 13.5, color: FG, align: "center",
    });
  });
  s.addText("Every image on this slide is GuardianEye's real output.", {
    x: 0.9, y: 6.55, w: 11.5, h: 0.45, margin: 0, fontSize: 14, italic: true, color: DIM,
  });
  s.addNotes("These are actual frames from our runs, not mockups.");

  // ---- 4. Demo: embedded video ------------------------------------------
  s = pres.addSlide();
  s.background = { color: BG };
  s.addText("DEMO", {
    x: 0.9, y: 0.35, w: 2.0, h: 0.55, margin: 0, fontSize: 26, bold: true, color: FG,
  });
  s.addShape(pres.ShapeType.roundRect, {
    x: 10.0, y: 0.38, w: 2.45, h: 0.5, fill: { color: CARD }, rectRadius: 0.25, line: { type: "none" },
  });
  s.addImage({ data: ic.play, x: 10.25, y: 0.52, w: 0.22, h: 0.22 });
  s.addText("CLICK TO PLAY", {
    x: 10.55, y: 0.38, w: 1.9, h: 0.5, margin: 0, fontSize: 12, bold: true, color: FG,
  });
  const cover = fs.readFileSync(poster).toString("base64");
  s.addMedia({
    type: "video", path: video,
    x: 1.76, y: 1.05, w: 9.8, h: 5.51,
    cover: "image/png;base64," + cover,
  });
  s.addShape(pres.ShapeType.rect, {
    x: 1.76, y: 1.05, w: 9.8, h: 5.51, fill: { color: BG, transparency: 100 },
    line: { color: RED, width: 2 },
  });
  s.addText(
    "2,000+ fans counted live  ·  every resolvable person boxed  ·  collapse detected and zoned in seconds",
    { x: 0.9, y: 6.8, w: 11.5, h: 0.4, margin: 0, fontSize: 13, color: DIM, align: "center" }
  );
  s.addNotes("40 seconds, no cuts that hide anything. Slow-motion so every detection is readable.");

  // ---- 5. Under the hood: flow + real signals ---------------------------
  s = pres.addSlide();
  s.background = { color: BG };
  s.addText("Under the hood", {
    x: 0.9, y: 0.55, w: 11.5, h: 0.8, margin: 0, fontSize: 32, bold: true, color: FG,
  });
  const steps = [
    "ANY CAMERA - fixed, drone, or phone",
    "YOLO11x + sliced tiles - boxes every fan it can resolve",
    "CSRNet + Depth Anything V2 - counts thousands, real people/m2",
    "ZONE ALERT - crush / collapse / edge fall",
  ];
  steps.forEach((t, i) => {
    const y = 1.7 + i * 1.05;
    s.addShape(pres.ShapeType.ellipse, {
      x: 0.9, y: y + 0.06, w: 0.52, h: 0.52, fill: { color: CARD }, line: { type: "none" },
    });
    s.addText(String(i + 1), {
      x: 0.9, y: y + 0.06, w: 0.52, h: 0.52, margin: 0,
      fontSize: 18, bold: true, color: RED, align: "center", valign: "middle",
    });
    s.addText(t, {
      x: 1.65, y, w: 5.1, h: 0.7, margin: 0, fontSize: 15, color: FG, valign: "middle",
    });
  });
  const facts = [
    { icon: ic.bolt, t: "23 fps live mode on a laptop - no cloud, no footage leaving the venue" },
    { icon: ic.lock, t: "Anonymous by design: no faces identified, no identities stored" },
    { icon: ic.video, t: "Open source (AGPL) - 59 unit tests - thresholds from crowd-safety literature" },
  ];
  facts.forEach((f, i) => {
    const y = 6.05 + i * 0.42;
    s.addImage({ data: f.icon, x: 0.95, y: y + 0.03, w: 0.28, h: 0.28 });
    s.addText(f.t, { x: 1.4, y, w: 10.9, h: 0.4, margin: 0, fontSize: 12.5, color: DIM });
  });
  tile(s, A("counting.png"), 7.1, 1.7, 3.05, 3.7);
  s.addText("every resolvable fan, boxed", {
    x: 7.1, y: 5.44, w: 3.05, h: 0.32, margin: 0,
    fontSize: 11.5, italic: true, color: DIM, align: "center",
  });
  tile(s, A("depth_art.png"), 10.35, 1.7, 2.05, 3.7);
  s.addText("depth from one lens:\nevery tier resolved", {
    x: 10.35, y: 5.44, w: 2.05, h: 0.55, margin: 0,
    fontSize: 11.5, italic: true, color: DIM, align: "center",
  });

  // ---- 6. Making the models work: tuning wins ---------------------------
  s = pres.addSlide();
  s.background = { color: BG };
  s.addText("Making the models work on real footage", {
    x: 0.9, y: 0.5, w: 11.5, h: 0.8, margin: 0, fontSize: 32, bold: true, color: FG,
  });
  s.addText(
    "Off-the-shelf models failed on a packed stadium. Four fixes, each measured on the actual demo clip:",
    { x: 0.9, y: 1.22, w: 11.5, h: 0.4, margin: 0, fontSize: 14, color: DIM }
  );

  const tuning = [
    {
      metric: "21 → 85",
      mlabel: "people boxed / frame",
      header: "DETECTION AT SCALE",
      problem: "nano & pose models found ~21 fans (pose: zero) in a 2,000-strong stand.",
      fix: "YOLO11x + SAHI-style 3×2 tiled inference, cross-tile NMS, greedy tracker.",
    },
    {
      metric: "2,697",
      mlabel: "fans counted live",
      header: "COUNTING THE UNRESOLVABLE",
      problem: "a 5-px fan can't be boxed at all — detection alone undercounts wildly.",
      fix: "CSRNet density maps; caught a 64× mass-scale bug, verified 2.2 → 140 on a crop.",
    },
    {
      metric: "8.4 → 4.7",
      mlabel: "p/m², now physically real",
      header: "DEPTH THAT MEANS SOMETHING",
      problem: "Depth-Small + min-max colormap: flat map, density spiked to a false CRITICAL.",
      fix: "Depth Anything V2 Large + percentile / histogram-equalized normalization.",
    },
    {
      metric: "→ 0",
      mlabel: "false edge alarms",
      header: "ALERTS THAT DON'T CRY WOLF",
      problem: "a moving drone made every still fan appear to drift toward an edge.",
      fix: "optical-flow ego-motion compensation + sustained-frame confirmation gate.",
    },
  ];
  tuning.forEach((c, i) => {
    const cx = 0.9 + (i % 2) * 5.82;
    const cy = 1.75 + Math.floor(i / 2) * 2.6;
    const w = 5.7;
    s.addShape(pres.ShapeType.roundRect, {
      x: cx, y: cy, w, h: 2.45, fill: { color: CARD }, rectRadius: 0.12, line: { type: "none" },
    });
    s.addText(c.metric, {
      x: cx + 0.2, y: cy + 0.45, w: 1.85, h: 0.7, margin: 0,
      fontSize: 24, bold: true, color: RED, align: "center",
    });
    s.addText(c.mlabel, {
      x: cx + 0.15, y: cy + 1.18, w: 1.95, h: 0.7, margin: 0,
      fontSize: 10.5, color: DIM, align: "center",
    });
    s.addText(c.header, {
      x: cx + 2.2, y: cy + 0.28, w: w - 2.45, h: 0.4, margin: 0,
      fontSize: 14, bold: true, color: FG,
    });
    s.addText(
      [
        { text: "Problem  ", options: { bold: true, color: DIM } },
        { text: c.problem, options: { color: DIM } },
      ],
      { x: cx + 2.2, y: cy + 0.78, w: w - 2.45, h: 0.72, margin: 0, fontSize: 11.5, valign: "top" }
    );
    s.addText(
      [
        { text: "Fix  ", options: { bold: true, color: RED } },
        { text: c.fix, options: { color: FG } },
      ],
      { x: cx + 2.2, y: cy + 1.5, w: w - 2.45, h: 0.85, margin: 0, fontSize: 11.5, valign: "top" }
    );
  });
  s.addText(
    "Every number is measured on the real demo footage — 59 unit tests lock the thresholds in place.",
    { x: 0.9, y: 7.02, w: 11.5, h: 0.4, margin: 0, fontSize: 12, italic: true, color: DIM }
  );
  s.addNotes(
    "The interesting engineering isn't the models, it's making them survive real footage: " +
    "tiled inference to see 5-px fans, a density-map head to count the unresolvable, a 64x " +
    "calibration bug we caught by hand, a stronger depth model with fixed contrast, and " +
    "ego-motion compensation so a moving drone doesn't cry wolf."
  );

  // ---- 7. Close: full-bleed hazard frame --------------------------------
  s = pres.addSlide();
  s.background = { path: A("edge.png") };
  veil(s, 22);
  s.addText("Every stadium already owns the cameras.", {
    x: 0.9, y: 2.55, w: 11.5, h: 0.8, margin: 0, fontSize: 36, bold: true, color: FG, align: "center",
    shadow: { type: "outer", color: "000000", blur: 10, offset: 2, angle: 90, opacity: 0.8 },
  });
  s.addText("GuardianEye is the software that watches back.", {
    x: 0.9, y: 3.45, w: 11.5, h: 0.8, margin: 0, fontSize: 36, bold: true, color: RED, align: "center",
    shadow: { type: "outer", color: "000000", blur: 10, offset: 2, angle: 90, opacity: 0.8 },
  });
  s.addShape(pres.ShapeType.roundRect, {
    x: 4.29, y: 4.9, w: 4.75, h: 0.62, fill: { color: BG, transparency: 15 },
    rectRadius: 0.31, line: { color: RED, width: 1 },
  });
  s.addText("github.com/PranavAchar01/guardianeye", {
    x: 4.29, y: 4.9, w: 4.75, h: 0.62, margin: 0,
    fontSize: 15, color: FG, align: "center", valign: "middle",
  });

  const outPath = path.join(root, "out", "GuardianEye-deck.pptx");
  await pres.writeFile({ fileName: outPath });
  console.log("deck ready:", outPath);
})();
