/**
 * GuardianEye pitch deck: 6 slides, dark theme matching the showcase video.
 * Usage: node scripts/make_deck.js   (run from repo root)
 * Embeds out/showcase.mp4 on the demo slide; re-run after rebuilding it.
 */
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const { FaUsers, FaHeartPulse, FaTriangleExclamation, FaVideo, FaBolt, FaLock } =
  require("react-icons/fa6");

const BG = "0E1014";
const CARD = "1A1E26";
const FG = "E8E8E8";
const DIM = "969BA5";
const RED = "EB5050";
const FONT = "Arial";

async function iconPng(Icon, color) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Icon, { color: "#" + color, size: 256 })
  );
  const buf = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const root = process.cwd();
  const video = path.join(root, "out", "showcase.mp4");
  const poster = path.join(root, "out", "deck_poster.png");
  if (!fs.existsSync(video)) throw new Error("missing out/showcase.mp4");

  const icons = {
    crush: await iconPng(FaUsers, RED),
    collapse: await iconPng(FaHeartPulse, RED),
    edge: await iconPng(FaTriangleExclamation, RED),
    camera: await iconPng(FaVideo, FG),
    bolt: await iconPng(FaBolt, FG),
    lock: await iconPng(FaLock, FG),
  };

  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
  pres.theme = { bodyFontFace: FONT, headFontFace: FONT };

  const base = (slide) => {
    slide.background = { color: BG };
  };

  // ---- 1. Title ----------------------------------------------------------
  let s = pres.addSlide();
  base(s);
  s.addText("GUARDIANEYE", {
    x: 0.9, y: 2.35, w: 11.5, h: 1.3, margin: 0,
    fontSize: 72, bold: true, color: FG, align: "center", charSpacing: 6,
  });
  s.addText("The AI safety officer for stadiums", {
    x: 0.9, y: 3.7, w: 11.5, h: 0.6, margin: 0,
    fontSize: 28, color: RED, align: "center",
  });
  s.addText("Sees every fan. Counts every crowd. Calls for help before it's too late.", {
    x: 0.9, y: 4.5, w: 11.5, h: 0.5, margin: 0,
    fontSize: 16, color: DIM, align: "center", italic: true,
  });
  s.addText("Sports World Cup Hackathon 2026  ·  Track 4: Sports Business & Operations", {
    x: 0.9, y: 6.7, w: 11.5, h: 0.4, margin: 0,
    fontSize: 12, color: DIM, align: "center",
  });
  s.addNotes(
    "80,000 people in a stadium and today the safety plan is binoculars and radios. " +
    "GuardianEye turns the cameras a venue already owns into a safety officer that never blinks."
  );

  // ---- 2. The problem ----------------------------------------------------
  s = pres.addSlide();
  base(s);
  s.addText("Stadium safety is still a human squinting at a wall of screens", {
    x: 0.9, y: 0.6, w: 11.5, h: 1.0, margin: 0, fontSize: 34, bold: true, color: FG,
  });
  const stats = [
    { n: "-10% / min", label: "cardiac-arrest survival drops every minute\nwithout CPR - and medics find out last" },
    { n: "135 dead", label: "Kanjuruhan Stadium crush, 2022.\nThe cameras watched it happen" },
    { n: "5 px", label: "size of a fan in the far tier - invisible\nto humans and to ordinary AI alike" },
  ];
  stats.forEach((st, i) => {
    const x = 0.9 + i * 3.95;
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 2.2, w: 3.6, h: 3.6, fill: { color: CARD }, rectRadius: 0.12, line: { type: "none" },
    });
    s.addText(st.n, {
      x, y: 2.7, w: 3.6, h: 1.1, margin: 0,
      fontSize: 40, bold: true, color: RED, align: "center",
    });
    s.addText(st.label, {
      x: x + 0.25, y: 3.9, w: 3.1, h: 1.6, margin: 0,
      fontSize: 14, color: FG, align: "center",
    });
  });
  s.addText("One late response is a tragedy. Venues run on hope.", {
    x: 0.9, y: 6.3, w: 11.5, h: 0.5, margin: 0, fontSize: 16, italic: true, color: DIM,
  });

  // ---- 3. What it does ---------------------------------------------------
  s = pres.addSlide();
  base(s);
  s.addText("Three ways a crowd kills. One system watching for all of them.", {
    x: 0.9, y: 0.6, w: 11.5, h: 1.0, margin: 0, fontSize: 34, bold: true, color: FG,
  });
  const rows = [
    { icon: icons.crush, h: "CROWD CRUSH", t: "Live people-per-m2 density map of every camera view. Alert fires while there is still time to open gates - not after." },
    { icon: icons.collapse, h: "COLLAPSE", t: "Pose-based person-down detection. Confirmed in seconds, radioed with a grid zone: \"MEDICAL EMERGENCY - ZONE E4\"." },
    { icon: icons.edge, h: "EDGE FALLS", t: "Depth-cliff hazard map + trajectory prediction. Flags someone heading over a rail before the fall, with time-to-edge." },
  ];
  rows.forEach((r, i) => {
    const y = 1.95 + i * 1.7;
    s.addShape(pres.ShapeType.ellipse, {
      x: 0.9, y, w: 0.95, h: 0.95, fill: { color: CARD }, line: { type: "none" },
    });
    s.addImage({ data: r.icon, x: 1.115, y: y + 0.215, w: 0.52, h: 0.52 });
    s.addText(r.h, {
      x: 2.15, y: y + 0.02, w: 10.0, h: 0.4, margin: 0, fontSize: 19, bold: true, color: RED,
    });
    s.addText(r.t, {
      x: 2.15, y: y + 0.44, w: 10.0, h: 0.75, margin: 0, fontSize: 15, color: FG,
    });
  });
  s.addText("Anonymous by design: no faces identified, no identities stored.", {
    x: 0.9, y: 6.9, w: 11.5, h: 0.4, margin: 0, fontSize: 13, italic: true, color: DIM,
  });

  // ---- 4. Demo (embedded video) -----------------------------------------
  s = pres.addSlide();
  base(s);
  s.addText("DEMO - real footage, real time", {
    x: 0.9, y: 0.35, w: 11.5, h: 0.5, margin: 0, fontSize: 22, bold: true, color: FG,
  });
  const cover = fs.readFileSync(poster).toString("base64");
  s.addMedia({
    type: "video",
    path: video,
    x: 1.71, y: 1.0, w: 9.9, h: 5.57, // 16:9 inside the slide
    cover: "image/png;base64," + cover,
  });
  s.addText(
    "Packed international stadium: 2,000+ fans counted live  ·  collapse detected and zoned in seconds",
    { x: 0.9, y: 6.75, w: 11.5, h: 0.4, margin: 0, fontSize: 13, color: DIM, align: "center" }
  );
  s.addNotes("Click the frame to play. 40 seconds, no cuts that hide anything.");

  // ---- 5. How it works ---------------------------------------------------
  s = pres.addSlide();
  base(s);
  s.addText("How it works", {
    x: 0.9, y: 0.6, w: 11.5, h: 0.9, margin: 0, fontSize: 34, bold: true, color: FG,
  });
  const steps = ["ANY CAMERA\nfixed, drone,\nor phone", "YOLO11x + tiles\nboxes every fan\nit can resolve", "CSRNet + depth\ncounts thousands,\nreal people/m2", "ZONE ALERT\ncrush - collapse -\nedge fall"];
  steps.forEach((t, i) => {
    const x = 0.9 + i * 3.12;
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 2.1, w: 2.7, h: 1.9, fill: { color: CARD }, rectRadius: 0.1, line: { type: "none" },
    });
    s.addText(t, {
      x: x + 0.1, y: 2.25, w: 2.5, h: 1.6, margin: 0,
      fontSize: 14, color: FG, align: "center", bold: i === 3,
    });
    if (i < 3) {
      s.addText(">", {
        x: x + 2.68, y: 2.75, w: 0.5, h: 0.6, margin: 0,
        fontSize: 28, bold: true, color: RED, align: "center",
      });
    }
  });
  const facts = [
    { icon: icons.bolt, t: "Runs on a laptop. No cloud, no latency, no footage leaving the venue." },
    { icon: icons.camera, t: "Uses the cameras stadiums already own - it's software on the video wall." },
    { icon: icons.lock, t: "Open source (AGPL). 58 unit tests. Every threshold from crowd-safety literature." },
  ];
  facts.forEach((f, i) => {
    const y = 4.55 + i * 0.75;
    s.addImage({ data: f.icon, x: 0.95, y: y + 0.05, w: 0.38, h: 0.38 });
    s.addText(f.t, { x: 1.55, y, w: 10.6, h: 0.5, margin: 0, fontSize: 15, color: FG });
  });

  // ---- 6. Close ----------------------------------------------------------
  s = pres.addSlide();
  base(s);
  s.addText("Every stadium already owns the cameras.", {
    x: 0.9, y: 2.6, w: 11.5, h: 0.8, margin: 0, fontSize: 36, bold: true, color: FG, align: "center",
  });
  s.addText("GuardianEye is the software that watches back.", {
    x: 0.9, y: 3.5, w: 11.5, h: 0.8, margin: 0, fontSize: 36, bold: true, color: RED, align: "center",
  });
  s.addText("github.com/PranavAchar01/guardianeye", {
    x: 0.9, y: 5.0, w: 11.5, h: 0.5, margin: 0, fontSize: 20, color: FG, align: "center",
  });

  const outPath = path.join(root, "out", "GuardianEye-deck.pptx");
  await pres.writeFile({ fileName: outPath });
  console.log("deck ready:", outPath);
})();
