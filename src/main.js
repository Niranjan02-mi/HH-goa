/**
 * Main Entry — HH Goa 2026 Frame Generator
 * Initializes Three.js, GSAP, and wires up all UI interactions
 */
import './style.css';
import { initAnimations } from './animations.js';
import {
  getBuilderClass,
  generateProfileFrame,
  generateIDCard,
  generateTeamFrame,
  downloadCanvas,
  shareToX,
  loadImageFromFile,
} from './canvas-engine.js';

document.addEventListener('DOMContentLoaded', () => {
  initAnimations();
  if (document.getElementById('upload-zone')) {
    initPhotoUpload();
    initFormLogic();
  }
});

// ========== STATE ==========
let uploadedPhoto = null;
let photoZoom = 1;
let photoOffsetX = 0;
let photoOffsetY = 0;

// ========== PHOTO UPLOAD ==========
function initPhotoUpload() {
  const zone = document.getElementById('upload-zone');
  const input = document.getElementById('photo-input');
  const preview = document.getElementById('upload-preview');
  const editor = document.getElementById('photo-editor');
  const zoomSlider = document.getElementById('photo-zoom');
  const resetBtn = document.getElementById('btn-reset-zoom');
  const changeBtn = document.getElementById('btn-change-photo');
  const circleWrap = document.getElementById('photo-circle-wrap');

  // Click to upload
  zone.addEventListener('click', () => input.click());

  // File change
  input.addEventListener('change', async (e) => {
    if (e.target.files && e.target.files[0]) {
      await handlePhoto(e.target.files[0]);
    }
  });

  // Drag & Drop
  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', () => {
    zone.classList.remove('dragover');
  });
  zone.addEventListener('drop', async (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handlePhoto(e.dataTransfer.files[0]);
    }
  });

  // Change Photo button
  changeBtn.addEventListener('click', () => input.click());

  // Zoom slider
  zoomSlider.addEventListener('input', () => {
    photoZoom = parseFloat(zoomSlider.value);
    updatePreviewTransform();
  });

  // Reset button
  resetBtn.addEventListener('click', () => {
    photoZoom = 1;
    photoOffsetX = 0;
    photoOffsetY = 0;
    zoomSlider.value = '1';
    updatePreviewTransform();
  });

  // Drag to pan inside circle
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let startOffX = 0;
  let startOffY = 0;

  circleWrap.addEventListener('mousedown', (e) => {
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    startOffX = photoOffsetX;
    startOffY = photoOffsetY;
    e.preventDefault();
  });

  circleWrap.addEventListener('touchstart', (e) => {
    isDragging = true;
    const touch = e.touches[0];
    dragStartX = touch.clientX;
    dragStartY = touch.clientY;
    startOffX = photoOffsetX;
    startOffY = photoOffsetY;
  }, { passive: true });

  const onMove = (clientX, clientY) => {
    if (!isDragging) return;
    const dx = clientX - dragStartX;
    const dy = clientY - dragStartY;
    // Clamp offset so image doesn't go too far
    const maxOffset = (photoZoom - 1) * 50;
    photoOffsetX = Math.max(-maxOffset, Math.min(maxOffset, startOffX + dx));
    photoOffsetY = Math.max(-maxOffset, Math.min(maxOffset, startOffY + dy));
    updatePreviewTransform();
  };

  window.addEventListener('mousemove', (e) => onMove(e.clientX, e.clientY));
  window.addEventListener('touchmove', (e) => {
    if (isDragging) onMove(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  window.addEventListener('mouseup', () => { isDragging = false; });
  window.addEventListener('touchend', () => { isDragging = false; });

  function updatePreviewTransform() {
    if (preview) {
      preview.style.transform = `scale(${photoZoom}) translate(${photoOffsetX / photoZoom}px, ${photoOffsetY / photoZoom}px)`;
    }
  }

  async function handlePhoto(file) {
    try {
      uploadedPhoto = await loadImageFromFile(file);
      preview.src = uploadedPhoto.src;
      // Hide drop zone, show editor
      zone.classList.add('hidden');
      editor.style.display = 'flex';
      // Reset zoom/pan
      photoZoom = 1;
      photoOffsetX = 0;
      photoOffsetY = 0;
      zoomSlider.value = '1';
      updatePreviewTransform();
      updateGenerateButton();
      showToast('Photo uploaded! ✦');
    } catch (err) {
      showToast('Failed to load image. Try another photo.');
    }
  }
}

// ========== FORM LOGIC ==========
function initFormLogic() {
  const nameInput = document.getElementById('builder-name');
  const stackSelect = document.getElementById('builder-stack');
  const customStack = document.getElementById('builder-stack-custom');
  const classText = document.getElementById('builder-class-text');
  const btnGen = document.getElementById('btn-gen-frame');
  const btnDlFrame = document.getElementById('btn-dl-frame');
  const btnDlId = document.getElementById('btn-dl-id');
  const btnShareFrame = document.getElementById('btn-share-frame');
  const btnShareId = document.getElementById('btn-share-id');

  // Update builder class on stack change
  stackSelect.addEventListener('change', () => {
    const cls = getBuilderClass(stackSelect.value);
    classText.textContent = cls;
    updateGenerateButton();
  });

  nameInput.addEventListener('input', updateGenerateButton);

  btnGen.addEventListener('click', () => {
    if (!uploadedPhoto) return;

    const frameCard = document.getElementById('frame-preview-card');
    const name = nameInput.value.trim();
    const stackKey = stackSelect.value;
    const stackLabel = customStack.value.trim() || stackSelect.options[stackSelect.selectedIndex].text;
    const builderClass = getBuilderClass(stackKey);

    // Generate Profile Frame (Canvas)
    const frameCanvas = document.getElementById('frame-canvas');
    generateProfileFrame(frameCanvas, uploadedPhoto, name, stackLabel, builderClass, {
      zoom: photoZoom,
      offsetX: photoOffsetX,
      offsetY: photoOffsetY,
    });

    const framePlaceholder = document.querySelector('#frame-canvas-wrap .preview-placeholder');
    if (framePlaceholder) framePlaceholder.style.display = 'none';

    if (frameCard) frameCard.style.display = 'block';

    // Enable download/share buttons
    btnDlFrame.disabled = false;
    btnShareFrame.disabled = false;

    showToast('Profile Frame generated! 🎉');

    // Scroll to preview card after canvas renders
    setTimeout(() => {
      if (frameCard) frameCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 300);
  });

  // Download handlers
  btnDlFrame.addEventListener('click', () => {
    downloadCanvas(document.getElementById('frame-canvas'), 'HHGoa2026_Frame.png');
    showToast('Frame downloaded! Share it with #FrameInGoa 🌴');
  });

  // Share handlers
  const shareText = `Just generated my HH Goa 2026 Builder Frame! 🌴🚀

Ready to build at India's biggest hack-station.
28–31 OCT 2026, Goa.

Generate yours → https://hhgoa.com

#FrameInGoa #HHGoa2026 @247pmstudio`;

  btnShareFrame.addEventListener('click', () => shareToX(shareText));
}

function updateGenerateButton() {
  const btn = document.getElementById('btn-gen-frame');
  const name = document.getElementById('builder-name').value.trim();
  const stack = document.getElementById('builder-stack').value;
  btn.disabled = !(uploadedPhoto && name && stack);
}

// ========== TOAST ==========
function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}
