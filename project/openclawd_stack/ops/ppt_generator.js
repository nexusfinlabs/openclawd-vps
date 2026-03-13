#!/usr/bin/env node
/**
 * PPT Generator — PptxGenJS (Node.js)
 *
 * Creates professional presentations from LLM-generated JSON content.
 * Uses react-icons + sharp for icon rendering, following the PPTX Agent Guide.
 *
 * Usage:
 *   node ppt_generator.js --prompt "5 slides sobre AI en payments"
 *   node ppt_generator.js --prompt-file /tmp/prompt.txt
 *   node ppt_generator.js --prompt-file /tmp/prompt.txt --palette dark-premium
 *
 * Palettes: navy-executive, dark-premium, clean-bold, midnight, teal-trust
 */

const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const path = require("path");
const fs = require("fs");
const https = require("https");
const http = require("http");

// ── Config ──────────────────────────────────────────
const DRAFTS_DIR = "/home/albi_agent/.openclaw/workspace/docs/drafts";
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || "";

// ── Icon Imports ────────────────────────────────────
const fa = require("react-icons/fa");
const md = require("react-icons/md");

// Icon mapping: LLM specifies icon name → we resolve the component
const ICON_MAP = {
  // General
  "cogs": fa.FaCogs, "settings": fa.FaCogs,
  "chart": fa.FaChartLine, "analytics": fa.FaChartLine,
  "rocket": fa.FaRocket, "launch": fa.FaRocket,
  "database": fa.FaDatabase, "data": fa.FaDatabase,
  "users": fa.FaUsers, "team": fa.FaUsers,
  "user": fa.FaUser, "person": fa.FaUser,
  "shield": fa.FaShieldAlt, "security": fa.FaShieldAlt,
  "globe": fa.FaGlobeAmericas, "global": fa.FaGlobeAmericas,
  "money": fa.FaMoneyBillWave, "payment": fa.FaMoneyBillWave,
  "lock": fa.FaLock, "secure": fa.FaLock,
  "lightbulb": fa.FaLightbulb, "idea": fa.FaLightbulb,
  "handshake": fa.FaHandshake, "deal": fa.FaHandshake,
  "building": fa.FaBuilding, "company": fa.FaBuilding,
  "check": fa.FaCheckCircle, "done": fa.FaCheckCircle,
  "star": fa.FaStar, "premium": fa.FaStar,
  "bolt": fa.FaBolt, "fast": fa.FaBolt,
  "trophy": fa.FaTrophy, "win": fa.FaTrophy,
  "code": fa.FaCode, "tech": fa.FaCode,
  "cloud": fa.FaCloud, "saas": fa.FaCloud,
  "brain": fa.FaBrain, "ai": fa.FaBrain,
  "puzzle": fa.FaPuzzlePiece, "integration": fa.FaPuzzlePiece,
  "target": fa.FaBullseye, "goal": fa.FaBullseye,
  "clock": fa.FaClock, "time": fa.FaClock,
  "map": fa.FaMapMarkedAlt, "location": fa.FaMapMarkedAlt,
  "phone": fa.FaPhone, "contact": fa.FaPhone,
  "envelope": fa.FaEnvelope, "email": fa.FaEnvelope,
  "flag": fa.FaFlag, "milestone": fa.FaFlag,
  // Material
  "science": md.MdScience, "research": md.MdScience,
  "trending": md.MdTrendingUp, "growth": md.MdTrendingUp,
};

// ── Palettes ────────────────────────────────────────
const PALETTES = {
  "navy-executive": {
    DARK: "1B2B5E", ACCENT: "00A896", GOLD: "F0C040", ICE: "CADCFC",
    CARD_BG: "FFFFFF", CONTENT_BG: "F7F8FC", TEXT: "1E293B", MUTED: "64748B",
    FOOTER_BG: "0D1B3E", FOOTER_TEXT: "8899AA",
  },
  "dark-premium": {
    DARK: "0F1923", ACCENT: "02C39A", GOLD: "F59E0B", ICE: "E2E8F0",
    CARD_BG: "1A2535", CONTENT_BG: "0F1923", TEXT: "E2E8F0", MUTED: "94A3B8",
    FOOTER_BG: "0A1018", FOOTER_TEXT: "64748B",
  },
  "clean-bold": {
    DARK: "1E2022", ACCENT: "E85D26", GOLD: "F5EFE6", ICE: "F5EFE6",
    CARD_BG: "FFFFFF", CONTENT_BG: "FAFAFA", TEXT: "1E2022", MUTED: "7A7D82",
    FOOTER_BG: "E8EBF0", FOOTER_TEXT: "7A7D82",
  },
  "midnight": {
    DARK: "1E2761", ACCENT: "408EC6", GOLD: "7A2048", ICE: "CADCFC",
    CARD_BG: "FFFFFF", CONTENT_BG: "F0F4FF", TEXT: "1E2761", MUTED: "6B7280",
    FOOTER_BG: "151D4A", FOOTER_TEXT: "8899BB",
  },
  "teal-trust": {
    DARK: "028090", ACCENT: "02C39A", GOLD: "00A896", ICE: "E0F7FA",
    CARD_BG: "FFFFFF", CONTENT_BG: "F0FAFA", TEXT: "1E293B", MUTED: "547A7D",
    FOOTER_BG: "015F6B", FOOTER_TEXT: "80BFC8",
  },
};

// ── Icon Helper ─────────────────────────────────────

async function iconBase64(IconComponent, color = "#FFFFFF", size = 256) {
  if (!IconComponent) IconComponent = fa.FaCogs;
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color, size: String(size) })
  );
  const pngBuffer = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + pngBuffer.toString("base64");
}

function resolveIcon(hint) {
  if (!hint) return fa.FaCogs;
  const key = hint.toLowerCase().replace(/[^a-z]/g, "");
  return ICON_MAP[key] || fa.FaCogs;
}

// ── Shadow Factory ──────────────────────────────────
const makeShadow = () => ({
  type: "outer", blur: 6, offset: 2,
  color: "000000", opacity: 0.15, angle: 135,
});

// ── LLM Content Generation ──────────────────────────

function generateSlideContent(userPrompt) {
  return new Promise((resolve, reject) => {
    const system = `Eres un diseñador de presentaciones ejecutivas de altísimo nivel.
Genera contenido para slides en JSON. Sé conciso, visual y moderno.

Cada slide tiene:
- type: "cover" | "content_cards" | "content_rows" | "two_column" | "highlight" | "stats" | "closing"
- title: título principal
- supertitle: texto corto superior (categoría/sección, ej: "ANÁLISIS DE MERCADO")
- subtitle: texto descriptivo
- bullets: lista de puntos (max 5, texto corto)
- cards: lista de {icon: "nombre", title: "...", description: "..."} (max 4, para content_cards)
- rows: lista de {icon: "nombre", title: "...", description: "...", metric: "€200k"} (max 4, para content_rows)
- left_title / left_bullets / right_title / right_bullets: para two_column
- quote: frase impactante (para highlight)
- stats: lista de {value: "98%", label: "Adoption rate"} (max 4, para stats)
- tags: lista de strings (max 4, para portada)
- footer_note: texto inferior (fuente, etc.)

Iconos disponibles: cogs,chart,rocket,database,users,shield,globe,money,lock,lightbulb,handshake,building,check,star,bolt,trophy,code,cloud,brain,puzzle,target,clock,map,science,trending,flag

Instrucciones:
- La primera slide SIEMPRE es "cover"
- La última slide SIEMPRE es "closing"
- Varía los tipos: usa content_cards para conceptos, content_rows para listas con métricas, stats para números, highlight para frases clave
- NUNCA repitas el mismo tipo consecutivamente
- Máximo 5 bullets, máximo 4 cards, texto MUY conciso
- Supertitle en MAYÚSCULAS

Responde SOLO con un JSON array válido.`;

    const payload = JSON.stringify({
      model: "openai/gpt-4o-mini",
      messages: [
        { role: "system", content: system },
        { role: "user", content: userPrompt },
      ],
      temperature: 0.7,
    });

    const options = {
      hostname: "openrouter.ai",
      path: "/api/v1/chat/completions",
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => data += chunk);
      res.on("end", () => {
        try {
          const json = JSON.parse(data);
          const content = json.choices[0].message.content;
          const match = content.match(/\[[\s\S]*\]/);
          if (match) resolve(JSON.parse(match[0]));
          else reject(new Error("No JSON array found in LLM response"));
        } catch (e) { reject(e); }
      });
    });
    req.on("error", reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error("LLM timeout")); });
    req.write(payload);
    req.end();
  });
}

// ═══════════════════════════════════════════════════
//  Slide Builders
// ═══════════════════════════════════════════════════

function addFooter(pres, slide, P, text) {
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.325, w: 10, h: 0.3, fill: { color: P.FOOTER_BG } });
  slide.addText(text, {
    x: 0.4, y: 5.325, w: 9.2, h: 0.3,
    fontSize: 8, fontFace: "Calibri", color: P.FOOTER_TEXT, valign: "middle", margin: 0,
  });
}

async function buildCover(pres, data, P) {
  const slide = pres.addSlide();
  slide.background = { color: P.DARK };

  // Accent bar left (motif)
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.45, h: 5.625, fill: { color: P.ACCENT } });
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.45, y: 0, w: 0.04, h: 5.625, fill: { color: P.GOLD } });

  // Decorative orb
  slide.addShape(pres.shapes.OVAL, {
    x: 7.2, y: -1.2, w: 4.5, h: 4.5,
    fill: { color: P.ACCENT, transparency: 88 },
    line: { color: P.ACCENT, width: 1.5, transparency: 70 },
  });

  // Supertitle
  const supertitle = (data.supertitle || "PRESENTACIÓN").toUpperCase();
  slide.addText(supertitle, {
    x: 0.75, y: 1.0, w: 8, h: 0.3,
    fontSize: 9, fontFace: "Calibri", color: P.ACCENT,
    bold: true, charSpacing: 3, margin: 0,
  });

  // Title
  slide.addText(data.title || "Presentación", {
    x: 0.75, y: 1.4, w: 7.5, h: 2.2,
    fontSize: 46, fontFace: "Calibri", color: "FFFFFF",
    bold: true, align: "left", valign: "top", margin: 0,
  });

  // Accent line
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.75, y: 3.55, w: 2.4, h: 0.055, fill: { color: P.GOLD },
  });

  // Subtitle
  if (data.subtitle) {
    slide.addText(data.subtitle, {
      x: 0.75, y: 3.75, w: 8, h: 0.35,
      fontSize: 14, fontFace: "Calibri", color: P.ICE,
      italic: true, margin: 0,
    });
  }

  // Tags
  const tags = data.tags || [];
  tags.slice(0, 4).forEach((t, i) => {
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0.75 + i * 2.2, y: 4.25, w: 2.0, h: 0.3,
      fill: { color: "FFFFFF", transparency: 88 },
      line: { color: P.ACCENT, width: 1 },
    });
    slide.addText(t, {
      x: 0.75 + i * 2.2, y: 4.25, w: 2.0, h: 0.3,
      fontSize: 8, fontFace: "Calibri", color: "FFFFFF",
      align: "center", valign: "middle", bold: true, charSpacing: 1, margin: 0,
    });
  });

  addFooter(pres, slide, P, "Alberto Lebrón  ·  Nexus FinLabs  ·  " + new Date().toLocaleDateString("es-ES", { month: "long", year: "numeric" }));
}

function addHeader(pres, slide, P, supertitle, title) {
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.85, fill: { color: P.DARK } });
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0.85, w: 10, h: 0.055, fill: { color: P.ACCENT } });
  slide.addText((supertitle || "").toUpperCase(), {
    x: 0.45, y: 0, w: 3, h: 0.85,
    fontSize: 9, fontFace: "Calibri", color: P.ACCENT,
    bold: true, charSpacing: 3, valign: "middle", margin: 0,
  });
  slide.addText(title || "", {
    x: 3.5, y: 0, w: 6.3, h: 0.85,
    fontSize: 14, fontFace: "Calibri", color: "FFFFFF",
    bold: true, valign: "middle", align: "right", margin: 0,
  });
}

async function buildContentCards(pres, data, P) {
  const slide = pres.addSlide();
  slide.background = { color: P.CONTENT_BG };

  addHeader(pres, slide, P, data.supertitle, data.title);

  const cards = data.cards || [];
  const n = Math.min(cards.length, 4);
  const CARD_W = 2.15, CARD_H = 3.9, CARD_Y = 1.1, GAP = 0.13;
  const accentColors = [P.ACCENT, "028090", "4F46E5", "7C3AED"];

  for (let i = 0; i < n; i++) {
    const { icon, title, description } = cards[i];
    const accent = accentColors[i % 4];
    const cx = 0.3 + i * (CARD_W + GAP);

    // Shadow
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx + 0.04, y: CARD_Y + 0.04, w: CARD_W, h: CARD_H,
      fill: { color: "CBD5E1", transparency: 30 },
    });
    // Card body
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: CARD_Y, w: CARD_W, h: CARD_H,
      fill: { color: P.CARD_BG }, line: { color: "E2E8F0", width: 0.75 },
    });
    // Accent bar top
    slide.addShape(pres.shapes.RECTANGLE, { x: cx, y: CARD_Y, w: CARD_W, h: 0.22, fill: { color: accent } });
    slide.addText(String(i + 1).padStart(2, "0"), {
      x: cx, y: CARD_Y, w: CARD_W, h: 0.22,
      fontSize: 9, fontFace: "Calibri", color: "FFFFFF",
      bold: true, align: "right", valign: "middle", margin: [0, 0.12, 0, 0],
    });
    // Icon circle
    slide.addShape(pres.shapes.OVAL, {
      x: cx + CARD_W / 2 - 0.32, y: CARD_Y + 0.28, w: 0.64, h: 0.64,
      fill: { color: accent, transparency: 12 },
    });
    const iconData = await iconBase64(resolveIcon(icon), "#FFFFFF", 256);
    slide.addImage({ data: iconData, x: cx + CARD_W / 2 - 0.22, y: CARD_Y + 0.38, w: 0.44, h: 0.44 });
    // Title
    slide.addText(title || "", {
      x: cx + 0.12, y: CARD_Y + 1.05, w: CARD_W - 0.24, h: 0.85,
      fontSize: 11, fontFace: "Calibri", color: P.TEXT,
      bold: true, align: "center", valign: "top", margin: 0,
    });
    // Divider
    slide.addShape(pres.shapes.RECTANGLE, {
      x: cx + 0.4, y: CARD_Y + 1.96, w: CARD_W - 0.8, h: 0.03,
      fill: { color: accent, transparency: 50 },
    });
    // Description
    slide.addText(description || "", {
      x: cx + 0.12, y: CARD_Y + 2.06, w: CARD_W - 0.24, h: 1.7,
      fontSize: 9, fontFace: "Calibri", color: P.MUTED,
      align: "left", valign: "top", margin: 0,
    });
  }

  addFooter(pres, slide, P, "Nexus FinLabs  ·  " + (data.supertitle || "") + "  ·  " + new Date().toLocaleDateString("es-ES", { month: "long", year: "numeric" }));
}

async function buildContentRows(pres, data, P) {
  const slide = pres.addSlide();
  slide.background = { color: P.CONTENT_BG };

  // Left accent bar motif
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.35, h: 5.625, fill: { color: P.ACCENT } });

  // Header
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.35, y: 0, w: 9.65, h: 0.82, fill: { color: "FFFFFF" } });
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.35, y: 0.82, w: 9.65, h: 0.04, fill: { color: "E8EBF0" } });
  slide.addText((data.supertitle || "").toUpperCase(), {
    x: 0.65, y: 0, w: 2, h: 0.82,
    fontSize: 8, fontFace: "Calibri", color: P.ACCENT,
    bold: true, charSpacing: 3, valign: "middle", margin: 0,
  });
  slide.addText(data.title || "", {
    x: 2.7, y: 0, w: 7.0, h: 0.82,
    fontSize: 16, fontFace: "Calibri", color: P.TEXT,
    bold: true, valign: "middle", margin: 0,
  });

  const rows = data.rows || [];
  const ROW_H = 1.07, ROW_Y = 0.92;

  for (let i = 0; i < Math.min(rows.length, 4); i++) {
    const { icon, title, description, metric } = rows[i];
    const ry = ROW_Y + i * (ROW_H + 0.02);

    // Zebra stripe
    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0.35, y: ry, w: 6.6, h: ROW_H,
      fill: { color: i % 2 === 0 ? P.CARD_BG : P.CONTENT_BG },
      line: { color: "E8EBF0", width: 0.5 },
    });
    // Number badge
    slide.addShape(pres.shapes.RECTANGLE, { x: 0.35, y: ry, w: 0.52, h: ROW_H, fill: { color: P.ACCENT } });
    slide.addText(String(i + 1).padStart(2, "0"), {
      x: 0.35, y: ry, w: 0.52, h: ROW_H,
      fontSize: 14, fontFace: "Calibri", color: "FFFFFF",
      bold: true, align: "center", valign: "middle", margin: 0,
    });
    // Icon
    const iconData = await iconBase64(resolveIcon(icon), `#${P.ACCENT}`, 256);
    slide.addImage({ data: iconData, x: 1.02, y: ry + ROW_H / 2 - 0.22, w: 0.44, h: 0.44 });
    // Title + description
    slide.addText(title || "", {
      x: 1.6, y: ry + 0.1, w: 3.6, h: 0.35,
      fontSize: 11, fontFace: "Calibri", color: P.TEXT, bold: true, valign: "middle", margin: 0,
    });
    slide.addText(description || "", {
      x: 1.6, y: ry + 0.45, w: 3.6, h: 0.56,
      fontSize: 8.5, fontFace: "Calibri", color: P.MUTED, valign: "top", margin: 0,
    });
    // Metric pill
    if (metric) {
      slide.addShape(pres.shapes.RECTANGLE, {
        x: 5.28, y: ry + ROW_H / 2 - 0.18, w: 1.55, h: 0.36,
        fill: { color: P.ACCENT, transparency: 88 }, line: { color: P.ACCENT, width: 0.75 },
      });
      slide.addText(metric, {
        x: 5.28, y: ry + ROW_H / 2 - 0.18, w: 1.55, h: 0.36,
        fontSize: 8, fontFace: "Calibri", color: P.ACCENT,
        bold: true, align: "center", valign: "middle", margin: 0,
      });
    }
  }

  // Side panel
  const rX = 7.15;
  slide.addShape(pres.shapes.RECTANGLE, { x: rX, y: 0.92, w: 2.65, h: 4.705, fill: { color: P.DARK } });
  slide.addText("Key\nTakeaways", {
    x: rX + 0.18, y: 1.02, w: 2.3, h: 0.7,
    fontSize: 17, fontFace: "Calibri", color: "FFFFFF", bold: true, margin: 0,
  });
  slide.addShape(pres.shapes.RECTANGLE, { x: rX + 0.18, y: 1.74, w: 0.9, h: 0.04, fill: { color: P.ACCENT } });

  const bullets = data.bullets || [];
  bullets.slice(0, 5).forEach((b, i) => {
    slide.addShape(pres.shapes.RECTANGLE, {
      x: rX + 0.18, y: 1.93 + i * 0.53, w: 0.06, h: 0.26, fill: { color: P.ACCENT },
    });
    slide.addText(b, {
      x: rX + 0.36, y: 1.88 + i * 0.53, w: 2.1, h: 0.38,
      fontSize: 9, fontFace: "Calibri", color: "C8CDD4", valign: "middle", margin: 0,
    });
  });

  addFooter(pres, slide, P, "Nexus FinLabs  ·  " + (data.supertitle || ""));
}

async function buildTwoColumn(pres, data, P) {
  const slide = pres.addSlide();
  slide.background = { color: P.CONTENT_BG };

  addHeader(pres, slide, P, data.supertitle, data.title);

  // Left column card
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.4, y: 1.15, w: 4.4, h: 3.95,
    fill: { color: P.CARD_BG }, shadow: makeShadow(),
    line: { color: "E2E8F0", width: 0.5 },
  });
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 1.15, w: 4.4, h: 0.06, fill: { color: P.ACCENT } });
  slide.addText(data.left_title || "", {
    x: 0.65, y: 1.35, w: 3.9, h: 0.45,
    fontSize: 14, fontFace: "Calibri", color: P.ACCENT, bold: true, margin: 0,
  });
  const leftBullets = (data.left_bullets || []).map((b, i) => ({
    text: b, options: { bullet: true, breakLine: i < (data.left_bullets || []).length - 1 },
  }));
  if (leftBullets.length) {
    slide.addText(leftBullets, {
      x: 0.65, y: 1.9, w: 3.9, h: 3.0,
      fontSize: 11, fontFace: "Calibri", color: P.TEXT, valign: "top", margin: 0,
      paraSpaceAfter: 6,
    });
  }

  // Right column card
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 5.2, y: 1.15, w: 4.4, h: 3.95,
    fill: { color: P.CARD_BG }, shadow: makeShadow(),
    line: { color: "E2E8F0", width: 0.5 },
  });
  slide.addShape(pres.shapes.RECTANGLE, { x: 5.2, y: 1.15, w: 4.4, h: 0.06, fill: { color: P.GOLD } });
  slide.addText(data.right_title || "", {
    x: 5.45, y: 1.35, w: 3.9, h: 0.45,
    fontSize: 14, fontFace: "Calibri", color: P.GOLD, bold: true, margin: 0,
  });
  const rightBullets = (data.right_bullets || []).map((b, i) => ({
    text: b, options: { bullet: true, breakLine: i < (data.right_bullets || []).length - 1 },
  }));
  if (rightBullets.length) {
    slide.addText(rightBullets, {
      x: 5.45, y: 1.9, w: 3.9, h: 3.0,
      fontSize: 11, fontFace: "Calibri", color: P.TEXT, valign: "top", margin: 0,
      paraSpaceAfter: 6,
    });
  }

  addFooter(pres, slide, P, "Nexus FinLabs");
}

async function buildHighlight(pres, data, P) {
  const slide = pres.addSlide();
  slide.background = { color: P.DARK };

  // Top accent bar
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: P.ACCENT } });

  // Center card
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 1.2, y: 1.3, w: 7.6, h: 3.2,
    fill: { color: P.CARD_BG === "FFFFFF" ? "1A2535" : P.CARD_BG },
    shadow: makeShadow(),
  });
  // Left accent on card
  slide.addShape(pres.shapes.RECTANGLE, { x: 1.2, y: 1.3, w: 0.08, h: 3.2, fill: { color: P.ACCENT } });

  // Quote mark
  slide.addText("❝", {
    x: 1.8, y: 1.5, w: 1, h: 0.8,
    fontSize: 48, fontFace: "Calibri", color: P.ACCENT, margin: 0,
  });

  // Quote text
  slide.addText(data.quote || data.title || "", {
    x: 1.8, y: 2.2, w: 6.4, h: 1.5,
    fontSize: 22, fontFace: "Calibri", color: "FFFFFF",
    bold: true, align: "center", valign: "middle", margin: 0,
  });

  // Footer note
  if (data.footer_note) {
    slide.addText(data.footer_note, {
      x: 1.8, y: 3.9, w: 6.4, h: 0.4,
      fontSize: 10, fontFace: "Calibri", color: P.MUTED,
      align: "center", valign: "middle", margin: 0,
    });
  }

  // Bottom accent
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.565, w: 10, h: 0.06, fill: { color: P.GOLD } });
}

async function buildStats(pres, data, P) {
  const slide = pres.addSlide();
  slide.background = { color: P.CONTENT_BG };

  addHeader(pres, slide, P, data.supertitle, data.title);

  const stats = data.stats || [];
  const n = Math.min(stats.length, 4);
  const WIDTH = n <= 2 ? 3.5 : 2.1;
  const totalW = n * WIDTH + (n - 1) * 0.2;
  const startX = (10 - totalW) / 2;
  const accentColors = [P.ACCENT, "028090", "4F46E5", "7C3AED"];

  stats.slice(0, 4).forEach((s, i) => {
    const sx = startX + i * (WIDTH + 0.2);
    const accent = accentColors[i % 4];

    // Card shadow
    slide.addShape(pres.shapes.RECTANGLE, {
      x: sx + 0.04, y: 1.64, w: WIDTH, h: 3.2,
      fill: { color: "CBD5E1", transparency: 30 },
    });
    // Card
    slide.addShape(pres.shapes.RECTANGLE, {
      x: sx, y: 1.6, w: WIDTH, h: 3.2,
      fill: { color: P.CARD_BG }, line: { color: "E2E8F0", width: 0.5 },
    });
    // Top accent
    slide.addShape(pres.shapes.RECTANGLE, { x: sx, y: 1.6, w: WIDTH, h: 0.08, fill: { color: accent } });

    // Value
    slide.addText(s.value || "", {
      x: sx, y: 2.0, w: WIDTH, h: 1.4,
      fontSize: 42, fontFace: "Calibri", color: accent,
      bold: true, align: "center", valign: "middle", margin: 0,
    });
    // Divider
    slide.addShape(pres.shapes.RECTANGLE, {
      x: sx + WIDTH * 0.25, y: 3.4, w: WIDTH * 0.5, h: 0.03,
      fill: { color: accent, transparency: 50 },
    });
    // Label
    slide.addText((s.label || "").toUpperCase(), {
      x: sx + 0.1, y: 3.55, w: WIDTH - 0.2, h: 0.9,
      fontSize: 9, fontFace: "Calibri", color: P.MUTED,
      align: "center", valign: "top", charSpacing: 1, margin: 0,
    });
  });

  addFooter(pres, slide, P, "Nexus FinLabs");
}

async function buildClosing(pres, data, P) {
  const slide = pres.addSlide();
  slide.background = { color: P.DARK };

  // Top accent
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: P.ACCENT } });

  // Decorative orb
  slide.addShape(pres.shapes.OVAL, {
    x: 3.5, y: -0.5, w: 3, h: 3,
    fill: { color: P.ACCENT, transparency: 92 },
  });

  // Title
  slide.addText(data.title || "Gracias", {
    x: 1, y: 2.0, w: 8, h: 1.2,
    fontSize: 44, fontFace: "Calibri", color: "FFFFFF",
    bold: true, align: "center", valign: "middle", margin: 0,
  });

  // Subtitle
  if (data.subtitle) {
    slide.addText(data.subtitle, {
      x: 1, y: 3.3, w: 8, h: 0.6,
      fontSize: 16, fontFace: "Calibri", color: P.ACCENT,
      align: "center", valign: "middle", margin: 0,
    });
  }

  // Contact
  slide.addText("dealflow@nexusfinlabs.com  ·  +34 605 693 177", {
    x: 1, y: 4.5, w: 8, h: 0.4,
    fontSize: 11, fontFace: "Calibri", color: P.MUTED,
    align: "center", valign: "middle", margin: 0,
  });

  // Bottom accent
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.565, w: 10, h: 0.06, fill: { color: P.GOLD } });
}

// ═══════════════════════════════════════════════════
//  Main Generator
// ═══════════════════════════════════════════════════

async function generatePptx(userPrompt, paletteName = "navy-executive") {
  const P = PALETTES[paletteName] || PALETTES["navy-executive"];

  console.error(`[ppt] Generating for: ${userPrompt.substring(0, 80)}...`);
  console.error(`[ppt] Palette: ${paletteName}`);

  // Generate content from LLM
  const slidesData = await generateSlideContent(userPrompt);
  console.error(`[ppt] LLM generated ${slidesData.length} slides`);

  // Build presentation
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = slidesData[0]?.title || "Presentación";

  for (const sdata of slidesData) {
    const stype = sdata.type || "content_cards";
    switch (stype) {
      case "cover": await buildCover(pres, sdata, P); break;
      case "content_cards": await buildContentCards(pres, sdata, P); break;
      case "content_rows": await buildContentRows(pres, sdata, P); break;
      case "two_column": await buildTwoColumn(pres, sdata, P); break;
      case "highlight": await buildHighlight(pres, sdata, P); break;
      case "stats": await buildStats(pres, sdata, P); break;
      case "closing": await buildClosing(pres, sdata, P); break;
      default: await buildContentCards(pres, sdata, P); break;
    }
  }

  // Save
  fs.mkdirSync(DRAFTS_DIR, { recursive: true });
  const ts = new Date().toISOString().replace(/[:-]/g, "").substring(0, 15);
  const safeName = userPrompt.substring(0, 30).replace(/[^a-zA-Z0-9]/g, "_");
  const filename = `PPT_${safeName}_${ts}.pptx`;
  const filepath = path.join(DRAFTS_DIR, filename);

  await pres.writeFile({ fileName: filepath });
  console.error(`[ppt] Saved: ${filepath}`);

  const summary = [
    "📊 *Presentación PPTX generada*",
    "",
    `📁 Archivo: \`${filename}\``,
    `📄 Slides: ${slidesData.length}`,
    `🎨 Paleta: \`${paletteName}\``,
    `📎 Ruta: ${filepath}`,
  ].join("\n");

  // Print summary to stdout (captured by make-ppt.sh)
  console.log(summary);
  return filepath;
}

// ── CLI ─────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  let prompt = "";
  let palette = "navy-executive";
  let promptFile = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--prompt-file" && args[i + 1]) { promptFile = args[++i]; }
    else if (args[i] === "--palette" && args[i + 1]) { palette = args[++i]; }
    else if (args[i] === "--prompt" && args[i + 1]) { prompt = args[++i]; }
    else if (!args[i].startsWith("--")) { prompt = args.slice(i).join(" "); break; }
  }

  if (promptFile) {
    prompt = fs.readFileSync(promptFile, "utf-8").trim();
  }

  if (!prompt) {
    console.error("Usage: node ppt_generator.js --prompt \"5 slides sobre AI\" [--palette navy-executive]");
    console.error("       node ppt_generator.js --prompt-file /tmp/prompt.txt");
    console.error("Palettes: " + Object.keys(PALETTES).join(", "));
    process.exit(1);
  }

  // Load .env
  try {
    const envFile = fs.readFileSync("/home/albi_agent/openclawd_stack/.env", "utf-8");
    envFile.split("\n").forEach((line) => {
      if (line && !line.startsWith("#") && line.includes("=")) {
        const [k, ...vParts] = line.split("=");
        const v = vParts.join("=").replace(/^["']|["']$/g, "");
        if (!process.env[k]) process.env[k] = v;
      }
    });
  } catch (e) { /* .env not found, skip */ }

  try {
    await generatePptx(prompt, palette);
  } catch (e) {
    console.log(`❌ Error generando presentación: ${e.message}`);
    console.error(e);
    process.exit(1);
  }
}

main();
