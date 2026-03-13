// ppt_example.js — Gold-standard PptxGenJS reference for LLM
// This file is loaded by ppt_dynamic.py as a few-shot example.
// The LLM uses it to understand the expected quality & structure.

const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");

const {
  FaFlask, FaHeartbeat, FaBrain, FaChartBar,
  FaDatabase, FaCogs, FaShieldAlt, FaRocket,
  FaSearch, FaCheckCircle, FaExclamationTriangle, FaFileMedical
} = require("react-icons/fa");

// ─── Paleta ───────────────────────────────────────────────
const C = {
  NAVY:   "0A1628",
  DARK:   "0F2040",
  TEAL:   "00A896",
  GOLD:   "F0C040",
  ICE:    "C8E6E3",
  WHITE:  "FFFFFF",
  MUTED:  "7A9BB5",
  CARD:   "132238",
  LIGHT:  "F0F6FA",
  BORDER: "1A3A5C",
};

// ─── Helper iconos ─────────────────────────────────────────
async function ico(IconComponent, color = C.WHITE, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color: `#${color}`, size: String(size) })
  );
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

// ─── Footer helper ─────────────────────────────────────────
function addFooter(slide, label = "Norgine · Análisis IA · 14 Ensayos Clínicos") {
  slide.addShape("rect", { x: 0, y: 5.325, w: 10, h: 0.3, fill: { color: "061020" } });
  slide.addText(label, {
    x: 0.4, y: 5.325, w: 9.2, h: 0.3,
    fontSize: 7.5, fontFace: "Calibri", color: "4A6A8A",
    valign: "middle", margin: 0,
  });
}

// ─── Header helper ─────────────────────────────────────────
function addHeader(slide, section, title) {
  slide.addShape("rect", { x: 0, y: 0, w: 10, h: 0.82, fill: { color: C.NAVY } });
  slide.addShape("rect", { x: 0, y: 0.82, w: 10, h: 0.045, fill: { color: C.TEAL } });
  slide.addText(section, {
    x: 0.45, y: 0, w: 2.5, h: 0.82,
    fontSize: 8, fontFace: "Calibri", color: C.TEAL,
    bold: true, charSpacing: 3, valign: "middle", margin: 0,
  });
  slide.addText(title, {
    x: 3.2, y: 0, w: 6.5, h: 0.82,
    fontSize: 15, fontFace: "Calibri", color: C.WHITE,
    bold: true, valign: "middle", align: "right", margin: 0,
  });
}

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "Norgine — Análisis IA de 14 Ensayos Clínicos";

  // SLIDE 1 — TITLE
  const s1 = pres.addSlide();
  s1.background = { color: C.NAVY };
  s1.addShape("rect", { x: 0, y: 0, w: 0.5,  h: 5.625, fill: { color: C.TEAL } });
  s1.addShape("rect", { x: 0.5, y: 0, w: 0.04, h: 5.625, fill: { color: C.GOLD } });
  s1.addShape("ellipse", { x: 6.5, y: -1.5, w: 5.5, h: 5.5, fill: { color: C.TEAL, transparency: 90 }, line: { color: C.TEAL, width: 1.5, transparency: 75 } });
  s1.addShape("ellipse", { x: 7.5, y: 2.5, w: 3.5, h: 3.5, fill: { color: C.GOLD, transparency: 92 }, line: { color: C.GOLD, width: 1, transparency: 80 } });
  s1.addText("NORGINE  ·  CLINICAL INTELLIGENCE  ·  2025", {
    x: 0.85, y: 0.95, w: 8.5, h: 0.3, fontSize: 8.5, fontFace: "Calibri", color: C.TEAL, bold: true, charSpacing: 2.5, margin: 0,
  });
  s1.addText("Análisis IA\nde 14 Ensayos\nClínicos", {
    x: 0.85, y: 1.3, w: 7.5, h: 2.6, fontSize: 50, fontFace: "Calibri", color: C.WHITE, bold: true, align: "left", valign: "top", margin: 0,
  });
  s1.addShape("rect", { x: 0.85, y: 3.88, w: 2.8, h: 0.055, fill: { color: C.GOLD } });
  s1.addText("Preparación Intestinal · Diagnóstico Hepático · Pipeline ETL · IA Predictiva", {
    x: 0.85, y: 4.05, w: 8.5, h: 0.4, fontSize: 13, fontFace: "Calibri", color: C.ICE, italic: true, margin: 0,
  });
  const chips = ["NER1006", "NRL994", "NRL972", "14 Trials"];
  chips.forEach((t, i) => {
    s1.addShape("rect", { x: 0.85 + i * 2.2, y: 4.62, w: 2.0, h: 0.32, fill: { color: C.WHITE, transparency: 90 }, line: { color: C.TEAL, width: 1 } });
    s1.addText(t, { x: 0.85 + i * 2.2, y: 4.62, w: 2.0, h: 0.32, fontSize: 8.5, fontFace: "Calibri", color: C.WHITE, bold: true, align: "center", valign: "middle", charSpacing: 1, margin: 0 });
  });
  addFooter(s1);

  // SLIDE 2 — RESUMEN EJECUTIVO (3 métricas)
  const s2 = pres.addSlide();
  s2.background = { color: C.LIGHT };
  addHeader(s2, "OVERVIEW", "Resumen Ejecutivo");
  const metrics = [
    { num: "14", label: "Ensayos\nClínicos", color: C.TEAL, Icon: FaFlask },
    { num: "2",  label: "Áreas\nTerapéuticas", color: "4F46E5", Icon: FaHeartbeat },
    { num: "3",  label: "Compuestos\nActivos", color: C.GOLD, Icon: FaFileMedical },
  ];
  for (let i = 0; i < metrics.length; i++) {
    const { num, label, color, Icon } = metrics[i];
    const mx = 0.55 + i * 3.1;
    s2.addShape("rect", { x: mx + 0.05, y: 1.05, w: 2.9, h: 2.0, fill: { color: "CBD5E1", transparency: 40 }, line: { color: "CBD5E1", transparency: 40 } });
    s2.addShape("rect", { x: mx, y: 1.0, w: 2.9, h: 2.0, fill: { color: C.WHITE }, line: { color: "E2E8F0", width: 1 } });
    s2.addShape("rect", { x: mx, y: 1.0, w: 2.9, h: 0.22, fill: { color: color } });
    s2.addText(num, { x: mx, y: 1.22, w: 2.9, h: 1.0, fontSize: 72, fontFace: "Calibri", color: color, bold: true, align: "center", valign: "middle", margin: 0 });
    const iconImg = await ico(Icon, color, 256);
    s2.addImage({ data: iconImg, x: mx + 2.4, y: 1.25, w: 0.35, h: 0.35 });
    s2.addText(label, { x: mx, y: 2.22, w: 2.9, h: 0.75, fontSize: 12, fontFace: "Calibri", color: "475569", bold: true, align: "center", valign: "middle", margin: 0 });
  }
  s2.addShape("rect", { x: 0.5, y: 3.2, w: 9.0, h: 1.55, fill: { color: C.NAVY }, line: { color: C.TEAL, width: 1 } });
  s2.addShape("rect", { x: 0.5, y: 3.2, w: 0.08, h: 1.55, fill: { color: C.TEAL } });
  s2.addText("Norgine divulga 14 ensayos clínicos en dos áreas: Preparación Intestinal (NER1006, NRL994) y Diagnóstico Hepático (NRL972). Se propone un marco de IA para automatizar extracción de datos, vigilancia de seguridad y apoyo al diseño de futuros ensayos.", {
    x: 0.75, y: 3.28, w: 8.6, h: 1.38, fontSize: 11.5, fontFace: "Calibri", color: C.ICE, valign: "middle", margin: 0,
  });
  addFooter(s2);

  // SLIDE 3 — AI OUTPUTS (4 cards)
  const s3 = pres.addSlide();
  s3.background = { color: C.NAVY };
  addHeader(s3, "IA FRAMEWORK", "Outputs del Sistema de Inteligencia Artificial");
  const aiCards = [
    { Icon: FaSearch, color: C.TEAL, num: "01", title: "NLP Extraction", desc: "PDF → JSON estructurado\nautomáticamente." },
    { Icon: FaShieldAlt, color: "E85D26", num: "02", title: "Safety Dashboard", desc: "AE rate por ensayo\ny dosis. Alertas." },
    { Icon: FaBrain, color: "4F46E5", num: "03", title: "Predictive Models", desc: "Probabilidad QTc\nprolongation." },
    { Icon: FaChartBar, color: "F59E0B", num: "04", title: "BI Visualization", desc: "Dashboards en\nPower BI / Looker." },
  ];
  const CW = 2.1, CH = 3.85, CY = 1.05, GAP = 0.13;
  for (let i = 0; i < aiCards.length; i++) {
    const { Icon, color, num, title, desc } = aiCards[i];
    const cx = 0.35 + i * (CW + GAP);
    s3.addShape("rect", { x: cx + 0.04, y: CY + 0.04, w: CW, h: CH, fill: { color: "000000", transparency: 60 }, line: { color: "000000", transparency: 60 } });
    s3.addShape("rect", { x: cx, y: CY, w: CW, h: CH, fill: { color: C.CARD }, line: { color: C.BORDER, width: 0.75 } });
    s3.addShape("rect", { x: cx, y: CY, w: CW, h: 0.22, fill: { color: color } });
    s3.addText(num, { x: cx, y: CY, w: CW, h: 0.22, fontSize: 9, fontFace: "Calibri", color: C.NAVY, bold: true, align: "right", valign: "middle", margin: [0, 0.1, 0, 0] });
    s3.addShape("ellipse", { x: cx + CW / 2 - 0.32, y: CY + 0.3, w: 0.64, h: 0.64, fill: { color: color, transparency: 15 } });
    const iconImg = await ico(Icon, C.WHITE, 256);
    s3.addImage({ data: iconImg, x: cx + CW / 2 - 0.22, y: CY + 0.4, w: 0.44, h: 0.44 });
    s3.addText(title, { x: cx + 0.1, y: CY + 1.08, w: CW - 0.2, h: 0.55, fontSize: 11.5, fontFace: "Calibri", color: C.WHITE, bold: true, align: "center", valign: "middle", margin: 0 });
    s3.addShape("rect", { x: cx + 0.35, y: CY + 1.68, w: CW - 0.7, h: 0.03, fill: { color: color, transparency: 40 } });
    s3.addText(desc, { x: cx + 0.1, y: CY + 1.76, w: CW - 0.2, h: 2.0, fontSize: 8.5, fontFace: "Calibri", color: "8BAFC8", align: "left", valign: "top", margin: 0 });
  }
  addFooter(s3);

  // SLIDE 4 — CTA / NEXT STEPS
  const s4 = pres.addSlide();
  s4.background = { color: C.NAVY };
  s4.addShape("rect", { x: 0, y: 0, w: 0.5, h: 5.625, fill: { color: C.TEAL } });
  s4.addShape("rect", { x: 0.5, y: 0, w: 0.04, h: 5.625, fill: { color: C.GOLD } });
  s4.addShape("ellipse", { x: 6.8, y: -0.8, w: 4.5, h: 4.5, fill: { color: C.TEAL, transparency: 92 }, line: { color: C.TEAL, width: 1, transparency: 80 } });
  s4.addText("PRÓXIMOS PASOS", { x: 0.85, y: 0.7, w: 4, h: 0.3, fontSize: 9, fontFace: "Calibri", color: C.TEAL, bold: true, charSpacing: 3, margin: 0 });
  s4.addText("Plan de\nAcción", { x: 0.85, y: 1.0, w: 6, h: 1.4, fontSize: 52, fontFace: "Calibri", color: C.WHITE, bold: true, margin: 0 });
  const nextSteps = [
    { num: "1", text: "Generar summary PDF ejecutivo", Icon: FaFileMedical, color: C.TEAL },
    { num: "2", text: "Construir prototipo ETL en Python", Icon: FaCogs, color: "4F46E5" },
    { num: "3", text: "Diseñar mockup BI dashboard", Icon: FaChartBar, color: C.GOLD },
  ];
  for (let i = 0; i < nextSteps.length; i++) {
    const { num, text, Icon, color } = nextSteps[i];
    const ny = 2.55 + i * 0.75;
    s4.addShape("ellipse", { x: 0.85, y: ny, w: 0.46, h: 0.46, fill: { color: color } });
    s4.addText(num, { x: 0.85, y: ny, w: 0.46, h: 0.46, fontSize: 16, fontFace: "Calibri", color: C.NAVY, bold: true, align: "center", valign: "middle", margin: 0 });
    const stepIco = await ico(Icon, color, 256);
    s4.addImage({ data: stepIco, x: 1.48, y: ny + 0.03, w: 0.38, h: 0.38 });
    s4.addText(text, { x: 2.0, y: ny + 0.02, w: 6.5, h: 0.42, fontSize: 13, fontFace: "Calibri", color: C.WHITE, valign: "middle", margin: 0 });
  }
  addFooter(s4, "Norgine · Clinical Intelligence · 2025 · Confidencial");

  await pres.writeFile({ fileName: "example_output.pptx" });
  console.log("✅ example generated");
}

main().catch(console.error);
