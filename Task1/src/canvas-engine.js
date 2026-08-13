/**
 * Canvas Compositing Engine — HH Goa 2026
 * Generates Profile Frame (1080×1080) + Builder ID Card (1200×675) + Team Frame (1500×500)
 */

// ========== BUILDER CLASS GENERATOR ==========
const CLASS_MAP = {
  react: 'Frontend Architect',
  vue: 'Vue Visionary',
  angular: 'Enterprise Sculptor',
  svelte: 'Svelte Sorceror',
  node: 'Backend Forge Master',
  python: 'Python Alchemist',
  go: 'Go Concurrency King',
  rust: 'Systems Warlock',
  java: 'Spring Titan',
  ml: 'ML Alchemist',
  web3: 'Chain Forger',
  fullstack: 'Full-Stack Ronin',
  mobile: 'Mobile Artisan',
  devops: 'Cloud Nomad',
  design: 'Pixel Shaman',
  systems: 'Kernel Wizard',
  other: 'Code Warrior',
};

export function getBuilderClass(stackKey) {
  return CLASS_MAP[stackKey] || 'Code Warrior';
}

// ========== IMAGE UTILITIES ==========
function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = e.target.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function autoCropCenter(img, targetW, targetH) {
  const canvas = document.createElement('canvas');
  canvas.width = targetW;
  canvas.height = targetH;
  const ctx = canvas.getContext('2d');

  const imgRatio = img.width / img.height;
  const targetRatio = targetW / targetH;

  let sx, sy, sw, sh;
  if (imgRatio > targetRatio) {
    sh = img.height;
    sw = sh * targetRatio;
    sx = (img.width - sw) / 2;
    sy = 0;
  } else {
    sw = img.width;
    sh = sw / targetRatio;
    sx = 0;
    sy = (img.height - sh) / 2;
  }

  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, targetW, targetH);
  return canvas;
}

function drawCircularImage(ctx, img, x, y, radius) {
  ctx.save();
  ctx.beginPath();
  ctx.arc(x + radius, y + radius, radius, 0, Math.PI * 2);
  ctx.closePath();
  ctx.clip();
  ctx.drawImage(img, x, y, radius * 2, radius * 2);
  ctx.restore();
}

// ========== PROFILE FRAME (1024×1535) ==========
export function generateProfileFrame(canvas, photo, name, stackLabel, builderClass, opts = {}) {
  const W = 1024, H = 1535;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  // Zoom/offset from the editor
  const zoom = opts.zoom || 1;
  const offX = opts.offsetX || 0;
  const offY = opts.offsetY || 0;

  const frameImg = new Image();
  frameImg.crossOrigin = 'anonymous';
  frameImg.onload = () => {
    ctx.clearRect(0, 0, W, H);

    // 1. Base Goa artwork
    ctx.drawImage(frameImg, 0, 0, W, H);

    // 2. User photo
    drawPhoto();

    // 3. Name & Stack boxes (No background cream rectangle!)
    drawNameAndStack(name, stackLabel);

    // 4. Builder Class (Left column)
    drawBuilderClass(builderClass || 'CODE WARRIOR');

    // 5. Builder ID (Right column)
    drawBuilderId();

    canvas.style.display = 'block';
  };
  frameImg.src = '/goa_hacker_house_updated.png';

  /* =========================================================
     TEXT HELPERS
  ========================================================= */

  function getFittedFont(text, maxWidth, startSize, minSize) {
    let size = startSize;
    while (size > minSize) {
      ctx.font = `900 ${size}px 'Space Grotesk', Arial, sans-serif`;
      if (ctx.measureText(text).width <= maxWidth) break;
      size--;
    }
    return size;
  }

  function textCenter(text, x, y, size, color, font = "'Space Grotesk', Arial, sans-serif") {
    ctx.font = `900 ${size}px ${font}`;
    ctx.fillStyle = color;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x, y);
  }

  /* =========================================================
     ROUND RECTANGLE
  ========================================================= */

  function box(x, y, w, h, radius, fill, border = null, borderWidth = 0) {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, radius);
    ctx.fillStyle = fill;
    ctx.fill();
    if (border) {
      ctx.strokeStyle = border;
      ctx.lineWidth = borderWidth;
      ctx.stroke();
    }
  }

  /* =========================================================
     PHOTO
  ========================================================= */

  function drawPhoto() {
    if (!photo) return;

    const cx = 511;
    const cy = 665;
    const radius = 236;

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.clip();

    const ratio = photo.width / photo.height;
    const target = radius * 2;
    let width, height;

    if (ratio > 1) {
      height = target;
      width = height * ratio;
    } else {
      width = target;
      height = width / ratio;
    }

    // Apply zoom/pan
    const scaledW = width * zoom;
    const scaledH = height * zoom;
    // offX / 90 means slider ranges -90 to 90 roughly mapped to the target width
    const drawX = cx - scaledW / 2 + offX * (target / 90);
    const drawY = cy - scaledH / 2 + offY * (target / 90) + 50; // Shift photo downward

    ctx.drawImage(photo, drawX, drawY, scaledW, scaledH);
    ctx.restore();
  }

  /* =========================================================
     NAME AND STACK BOXES (NO BEIGE RECTANGLE!)
  ========================================================= */

  function drawNameAndStack(nameVal, stackVal) {
    // --- GREEN NAME BOX ---
    const nameText = (nameVal || 'BUILDER').trim().toUpperCase();
    const nameW = 460;
    const nameH = 68;
    const nameX = 512 - nameW / 2;
    const nameY = 925;

    // Green box with yellow border
    box(nameX, nameY, nameW, nameH, 12, "#075c3b", "#f3c41b", 3);

    // Decorative stars inside green box
    textCenter("✦", nameX + 34, nameY + nameH / 2 + 1, 24, "#f3c41b");
    textCenter("✦", nameX + nameW - 34, nameY + nameH / 2 + 1, 24, "#f3c41b");

    // Fitted name text inside green box
    const nameSize = getFittedFont(nameText, 350, 36, 18);
    textCenter(nameText, 512, nameY + nameH / 2 + 2, nameSize, "#ffffff");

    // --- YELLOW STACK BOX ---
    const stackText = (stackVal || 'FULL-STACK').trim().toUpperCase();
    const stackW = 390;
    const stackH = 54;
    const stackX = 512 - stackW / 2;
    const stackY = 1005;

    // Yellow box with dark border
    box(stackX, stackY, stackW, stackH, 10, "#f3b916", "#075c3b", 3);

    // Lightning bolts inside stack box
    textCenter("⚡", stackX + 30, stackY + stackH / 2 + 1, 20, "#111111");
    textCenter("⚡", stackX + stackW - 30, stackY + stackH / 2 + 1, 20, "#111111");

    // Fitted stack text inside yellow box
    const stackSize = getFittedFont(stackText, 300, 28, 16);
    textCenter(stackText, 512, stackY + stackH / 2 + 2, stackSize, "#e43e68");
  }

  /* =========================================================
     BUILDER CLASS
  ========================================================= */

  function drawBuilderClass(builder) {
    const centerX = 170;

    // Label is already printed on the background image.
    // Just draw the dynamic class text.
    const words = (builder || 'CODE WARRIOR').toUpperCase().split(" ");
    let lines = [];
    let current = "";

    for (const word of words) {
      const test = current ? current + " " + word : word;
      ctx.font = "900 20px 'Space Grotesk', Arial, sans-serif";
      if (ctx.measureText(test).width > 220) {
        lines.push(current);
        current = word;
      } else {
        current = test;
      }
    }
    if (current) lines.push(current);
    lines = lines.slice(0, 2);

    lines.forEach((line, index) => {
      textCenter(line, centerX, 1190 + index * 24, 20, "#e83e67");
    });
  }

  /* =========================================================
     BUILDER ID
  ========================================================= */

  function drawBuilderId() {
    const centerX = 820;
    const id = opts.builderId || generateBuilderId();

    // The BUILDER ID label and barcode are pre-printed on the background.
    // We only need to draw the dynamic ID string between them.
    textCenter(id, centerX, 1285, 19, "#075c3b");
  }

  function generateBuilderId() {
    return "#HH-GOA-" + Math.floor(1000 + Math.random() * 9000);
  }
}

// ========== BUILDER ID CARD (1200×675) ==========
let idCardTemplateImg = null;
const templateImg = new Image();
templateImg.src = '/assets/idCardTemplate.png';
templateImg.onload = () => { idCardTemplateImg = templateImg; };

export function generateIDCard(canvas, photo, name, stackLabel, builderClass) {
  const W = 1200, H = 675;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  if (idCardTemplateImg) {
    ctx.drawImage(idCardTemplateImg, 0, 0, W, H);
  } else {
    // Fallback if image not loaded
    ctx.fillStyle = '#0b6839';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
    for (let x = 0; x < W; x += 20) {
      for (let y = 0; y < H; y += 20) {
        ctx.fillRect(x, y, 2, 2);
      }
    }
  }

  // Left section: Square photo for retro vibe
  const photoSize = 240;
  const photoX = 60;
  const photoY = (H - photoSize) / 2;

  // Glow behind photo (remove glow, add shadow block)
  ctx.fillStyle = '#ff0080';
  ctx.fillRect(photoX + 8, photoY + 8, photoSize, photoSize);

  // Photo border
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 4;
  ctx.strokeRect(photoX, photoY, photoSize, photoSize);

  // Draw square photo
  const photoSquare = autoCropCenter(photo, photoSize, photoSize);
  ctx.drawImage(photoSquare, photoX, photoY, photoSize, photoSize);

  // Right section: Info
  const infoX = 360;

  // "BUILDER PASS" label
  ctx.font = '700 12px "JetBrains Mono", monospace';
  ctx.fillStyle = '#fee101';
  ctx.letterSpacing = '4px';
  ctx.fillText('✦  BUILDER PASS  ✦', infoX, 80);

  // HH GOA 2026 title
  ctx.font = '900 48px "Bebas Neue", sans-serif';
  ctx.fillStyle = '#FFFFFF';
  ctx.letterSpacing = '3px';
  ctx.fillText('HACKER HOUSE GOA', infoX, 140);

  // Year accent
  ctx.font = '900 48px "Bebas Neue", sans-serif';
  ctx.fillStyle = '#ff0080';
  ctx.fillText('2026', infoX + 510, 140);

  // Divider line
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(infoX, 160);
  ctx.lineTo(W - 60, 160);
  ctx.stroke();

  // Name
  ctx.font = '800 40px "Space Grotesk", sans-serif';
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText(name || 'Builder', infoX, 215);

  // Stack label
  ctx.font = '500 18px "JetBrains Mono", monospace';
  ctx.fillStyle = '#fff';
  ctx.fillText(stackLabel || 'Code', infoX, 250);

  // Builder Class badge
  ctx.fillStyle = '#fee101';
  const classText = `✦ ${builderClass}`;
  ctx.font = '700 20px "JetBrains Mono", monospace';
  const classWidth = ctx.measureText(classText).width + 40;

  // Shadow box for badge
  ctx.fillStyle = '#fff';
  ctx.fillRect(infoX + 4, 274, classWidth, 40);

  ctx.fillStyle = '#fee101';
  ctx.fillRect(infoX, 270, classWidth, 40);
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2;
  ctx.strokeRect(infoX, 270, classWidth, 40);

  ctx.fillStyle = '#0b6839';
  ctx.fillText(classText, infoX + 20, 297);

  // Event details
  ctx.font = '500 14px "JetBrains Mono", monospace';
  ctx.fillStyle = '#fff';
  ctx.fillText('GOA, INDIA  ·  28–31 OCTOBER 2026', infoX, 350);
  ctx.fillText('PRIVATE BEACH RESORT  ·  247 BUILDERS', infoX, 375);

  // Bottom strip
  ctx.fillStyle = '#0b6839';
  ctx.fillRect(20, H - 100, W - 40, 60);
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(20, H - 100);
  ctx.lineTo(W - 20, H - 100);
  ctx.stroke();

  // Bottom strip text
  ctx.font = '600 12px "JetBrains Mono", monospace';
  ctx.fillStyle = '#fee101';
  ctx.fillText('#FrameInGoa  ·  hhgoa.com  ·  @247pmstudio', 55, H - 63);

  // Barcode decoration bottom-right
  for (let i = 0; i < 30; i++) {
    const bw = Math.random() > 0.5 ? 3 : 2;
    const bh = 30 + Math.random() * 20;
    ctx.fillStyle = `rgba(255, 255, 255, ${Math.random() * 0.6 + 0.4})`;
    ctx.fillRect(W - 60 - (i * 7), H - 95 + (50 - bh) / 2, bw, bh);
  }

  canvas.style.display = 'block';
}

// ========== TEAM FRAME (1500×500) ==========
export function generateTeamFrame(canvas, members) {
  // members: [{ photo: Image, name: string, stack: string }]
  const W = 1500, H = 500;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  // Background
  ctx.fillStyle = '#0b6839';
  ctx.fillRect(0, 0, W, H);

  // Dot pattern
  ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
  for (let x = 0; x < W; x += 25) {
    for (let y = 0; y < H; y += 25) {
      ctx.fillRect(x, y, 2, 2);
    }
  }

  // Border
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 4;
  roundRect(ctx, 15, 15, W - 30, H - 30, 0); // sharp corners
  ctx.stroke();

  // Title
  ctx.font = '900 50px "Bebas Neue", sans-serif';
  ctx.fillStyle = '#fee101';
  ctx.textAlign = 'center';
  ctx.fillText('HACKER HOUSE GOA 2026', W / 2, 65);

  ctx.font = '500 14px "JetBrains Mono", monospace';
  ctx.fillStyle = '#ff0080';
  ctx.fillText('28–31 OCT · GOA, INDIA · #FrameInGoa', W / 2, 90);

  // Divider
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(100, 110);
  ctx.lineTo(W - 100, 110);
  ctx.stroke();

  // Members
  const validMembers = members.filter(m => m.photo);
  const count = validMembers.length;
  if (count === 0) return;

  const spacing = W / (count + 1);
  const radius = 80;

  validMembers.forEach((member, i) => {
    const cx = spacing * (i + 1);
    const cy = 240;

    // Glow (shadow block)
    ctx.fillStyle = '#ff0080';
    ctx.fillRect(cx - radius + 8, cy - radius + 8, radius * 2, radius * 2);

    // Photo border
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 4;
    ctx.strokeRect(cx - radius, cy - radius, radius * 2, radius * 2);

    // Photo
    const photoSquare = autoCropCenter(member.photo, radius * 2, radius * 2);
    ctx.drawImage(photoSquare, cx - radius, cy - radius, radius * 2, radius * 2);

    // Name
    ctx.font = '700 24px "Space Grotesk", sans-serif';
    ctx.fillStyle = '#FFFFFF';
    ctx.textAlign = 'center';
    ctx.fillText(member.name || 'Builder', cx, cy + radius + 40);

    // Stack
    ctx.font = '500 14px "JetBrains Mono", monospace';
    ctx.fillStyle = '#fee101';
    ctx.fillText(member.stack || '', cx, cy + radius + 65);
  });

  // Footer
  ctx.font = '600 12px "JetBrains Mono", monospace';
  ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
  ctx.textAlign = 'center';
  ctx.fillText('SQUAD FRAME  ·  hhgoa.com  ·  #FrameInGoa', W / 2, H - 30);

  ctx.textAlign = 'left';
  canvas.style.display = 'block';
}

// ========== UTILITY: Rounded Rectangle ==========
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

// ========== DOWNLOAD UTIL ==========
export function downloadCanvas(canvas, filename) {
  canvas.toBlob((blob) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }, 'image/png');
}

// ========== SHARE TO X ==========
export function shareToX(text) {
  const url = `https://x.com/intent/tweet?text=${encodeURIComponent(text)}`;
  window.open(url, '_blank', 'width=600,height=400');
}

// ========== LOAD IMAGE FROM FILE ==========
export { loadImageFromFile };
