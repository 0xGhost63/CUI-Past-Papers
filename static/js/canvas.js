// Living Animated Background for CUI Past Papers Vault
// Advanced: Flow field particles + geometric drift + interactive ripple + theme-aware
// Low contrast, GPU efficient, pauses on tab hide and prefers-reduced-motion
// Zero emojis. Zero em dashes.

// Math.fract polyfill (must be before class definition)
if (typeof Math.fract !== "function") {
  Math.fract = function(x) { return x - Math.floor(x); };
}

console.log("[Archivist] canvas.js loaded");

class BentoLivingBackground {
  constructor(canvasId) {
    console.log("[Archivist] BentoLivingBackground constructor, canvasId:", canvasId);
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error("[Archivist] Canvas not found:", canvasId);
      return;
    }
    console.log("[Archivist] Canvas found, getting context");
    this.ctx = this.canvas.getContext("2d", { alpha: true, desynchronized: true });
    this.particles = [];
    this.flowField = [];
    this.geometricShapes = [];
    this.gridOffset = { x: 0, y: 0 };
    this.width = 0;
    this.height = 0;
    this.animId = null;
    this.isPaused = false;
    this.mousePos = { x: -9999, y: -9999 };
    this.rippleWaves = [];
    this.prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.lastTheme = document.documentElement.getAttribute("data-theme") || "light";
    this.flowFieldResolution = 60;
    this.particleCount = 30;

    this.init();
    this.bindEvents();
    if (!this.prefersReduced) {
      this.startLoop();
    } else {
      this.renderStaticFrame();
    }
  }

  init() {
    this.resize();
    this.createFlowField();
    this.createParticles();
    this.createGeometricShapes();
  }

  resize() {
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.canvas.style.width = this.width + "px";
    this.canvas.style.height = this.height + "px";
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.scale(dpr, dpr);
    this.createFlowField();
  }

  createFlowField() {
    const cols = Math.ceil(this.width / this.flowFieldResolution);
    const rows = Math.ceil(this.height / this.flowFieldResolution);
    this.flowField = [];
    const time = Date.now() * 0.0001;

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const angle = this.noise3D(x * 0.015, y * 0.015, time) * Math.PI * 2;
        this.flowField.push({ x: Math.cos(angle), y: Math.sin(angle) });
      }
    }
  }

  noise3D(x, y, z) {
    // Simple 3D noise approximation using sine waves
    const n1 = Math.sin(x * 12.9898 + y * 78.233 + z * 37.719) * 43758.5453;
    const n2 = Math.sin(x * 39.346 + y * 11.135 + z * 83.452) * 12.9898;
    const n3 = Math.sin(x * 17.453 + y * 29.876 + z * 54.123) * 78.233;
    return (Math.fract(n1) + Math.fract(n2) + Math.fract(n3)) / 3;
  }

  createParticles() {
    this.particles = [];
    const colors = this.getParticleColors();

    for (let i = 0; i < this.particleCount; i++) {
      const angle = (i / this.particleCount) * Math.PI * 2;
      const radius = 50 + Math.random() * Math.min(this.width, this.height) * 0.4;
      const cx = this.width / 2 + Math.cos(angle) * radius * 0.3;
      const cy = this.height / 2 + Math.sin(angle) * radius * 0.3;

      this.particles.push({
        x: Math.random() * this.width,
        y: Math.random() * this.height,
        vx: 0,
        vy: 0,
        size: 1.5 + Math.random() * 2.5,
        baseSize: 1.5 + Math.random() * 2.5,
        color: colors[Math.floor(Math.random() * colors.length)],
        opacity: 0.15 + Math.random() * 0.25,
        life: Math.random() * Math.PI * 2,
        speed: 0.2 + Math.random() * 0.5,
        trail: [],
        maxTrail: 8 + Math.floor(Math.random() * 6)
      });
    }
  }

  createGeometricShapes() {
    this.geometricShapes = [];
    const count = 8;
    const types = ["circle", "square", "triangle", "ring", "hexagon"];
    const palette = this.getShapePalette();

    for (let i = 0; i < count; i++) {
      this.geometricShapes.push({
        x: Math.random() * this.width,
        y: Math.random() * this.height,
        size: 40 + Math.random() * 100,
        type: types[i % types.length],
        colorIndex: i % palette.length,
        vx: (Math.random() - 0.5) * 0.12,
        vy: (Math.random() - 0.5) * 0.12,
        rotation: Math.random() * Math.PI * 2,
        vr: (Math.random() - 0.5) * 0.0008,
        pulsePhase: Math.random() * Math.PI * 2,
        pulseSpeed: 0.0005 + Math.random() * 0.001
      });
    }
  }

  getParticleColors() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    if (isDark) {
      return [
        "rgba(255, 90, 68, 0.35)",   // Tomato
        "rgba(255, 200, 51, 0.4)",   // Sun yellow
        "rgba(61, 220, 151, 0.35)",  // Mint green
        "rgba(76, 183, 255, 0.35)",  // Sky blue
        "rgba(183, 156, 255, 0.35)"  // Lilac
      ];
    }
    return [
      "rgba(255, 90, 68, 0.25)",
      "rgba(255, 200, 51, 0.3)",
      "rgba(61, 220, 151, 0.25)",
      "rgba(76, 183, 255, 0.25)",
      "rgba(183, 156, 255, 0.25)"
    ];
  }

  getShapePalette() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    if (isDark) {
      return [
        "rgba(255, 90, 68, 0.035)",
        "rgba(255, 200, 51, 0.035)",
        "rgba(61, 220, 151, 0.035)",
        "rgba(76, 183, 255, 0.035)",
        "rgba(183, 156, 255, 0.035)"
      ];
    }
    return [
      "rgba(255, 90, 68, 0.05)",
      "rgba(255, 200, 51, 0.06)",
      "rgba(61, 220, 151, 0.05)",
      "rgba(76, 183, 255, 0.05)",
      "rgba(183, 156, 255, 0.05)"
    ];
  }

  getGridColor() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    return isDark ? "rgba(255, 255, 255, 0.012)" : "rgba(27, 27, 31, 0.02)";
  }

  bindEvents() {
    window.addEventListener("resize", () => {
      this.resize();
      if (this.prefersReduced) this.renderStaticFrame();
    }, { passive: true });

    let scrollPauseTimer = null;
    window.addEventListener("scroll", () => {
      this.isPaused = true;
      clearTimeout(scrollPauseTimer);
      scrollPauseTimer = setTimeout(() => {
        this.isPaused = document.hidden;
      }, 150);
    }, { passive: true });

    document.addEventListener("visibilitychange", () => {
      this.isPaused = document.hidden;
      if (!this.isPaused && !this.prefersReduced && !this.animId) {
        this.startLoop();
      }
    });

    // Mouse tracking for interactive ripple
    document.addEventListener("mousemove", (e) => {
      this.mousePos.x = e.clientX;
      this.mousePos.y = e.clientY;

      // Add subtle ripple on mouse move (throttled)
      if (Math.random() < 0.02 && !this.prefersReduced) {
        this.rippleWaves.push({
          x: e.clientX,
          y: e.clientY,
          radius: 0,
          maxRadius: 80 + Math.random() * 60,
          opacity: 0.08 + Math.random() * 0.06,
          color: this.getParticleColors()[Math.floor(Math.random() * 5)],
          speed: 1.5 + Math.random()
        });
        if (this.rippleWaves.length > 6) this.rippleWaves.shift();
      }
    });

    // Click ripple
    document.addEventListener("click", (e) => {
      if (!this.prefersReduced) {
        this.rippleWaves.push({
          x: e.clientX,
          y: e.clientY,
          radius: 0,
          maxRadius: 180,
          opacity: 0.12,
          color: this.getParticleColors()[Math.floor(Math.random() * 5)],
          speed: 2.5
        });
        if (this.rippleWaves.length > 8) this.rippleWaves.shift();
      }
    });

    // Theme change detection
    const observer = new MutationObserver(() => {
      const newTheme = document.documentElement.getAttribute("data-theme") || "light";
      if (newTheme !== this.lastTheme) {
        this.lastTheme = newTheme;
        this.createParticles();
        this.createGeometricShapes();
      }
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    mql.addEventListener("change", (e) => {
      this.prefersReduced = e.matches;
      if (this.prefersReduced) {
        cancelAnimationFrame(this.animId);
        this.animId = null;
        this.renderStaticFrame();
      } else {
        this.startLoop();
      }
    });
  }

  drawGrid() {
    const gridSize = 80;
    const color = this.getGridColor();
    const lineWidth = 0.4;

    this.ctx.save();
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = lineWidth;
    this.ctx.globalAlpha = 0.4;

    // Vertical lines with subtle offset animation
    const startX = -(this.gridOffset.x % gridSize);
    for (let x = startX; x < this.width + gridSize; x += gridSize) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, this.height);
      this.ctx.stroke();
    }

    // Horizontal lines
    const startY = -(this.gridOffset.y % gridSize);
    for (let y = startY; y < this.height + gridSize; y += gridSize) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(this.width, y);
      this.ctx.stroke();
    }

    // Subtle diagonal accent lines
    this.ctx.globalAlpha = 0.08;
    const diagSpacing = 160;
    for (let d = -this.height; d < this.width + this.height; d += diagSpacing) {
      this.ctx.beginPath();
      this.ctx.moveTo(d, 0);
      this.ctx.lineTo(d + this.height, this.height);
      this.ctx.stroke();
    }

    this.ctx.restore();
  }

  updateFlowField(time) {
    const cols = Math.ceil(this.width / this.flowFieldResolution);
    const rows = Math.ceil(this.height / this.flowFieldResolution);
    const t = time * 0.00008;

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const idx = y * cols + x;
        const angle = this.noise3D(x * 0.015, y * 0.015, t) * Math.PI * 2;
        this.flowField[idx] = { x: Math.cos(angle), y: Math.sin(angle) };
      }
    }
  }

  updateParticles(dt) {
    const cols = Math.ceil(this.width / this.flowFieldResolution);
    const rows = Math.ceil(this.height / this.flowFieldResolution);

    for (const p of this.particles) {
      // Get flow field vector at particle position
      const col = Math.floor(p.x / this.flowFieldResolution);
      const row = Math.floor(p.y / this.flowFieldResolution);

      if (col >= 0 && col < cols && row >= 0 && row < rows) {
        const idx = row * cols + col;
        const force = this.flowField[idx];

        // Apply flow field force
        p.vx += force.x * 0.02 * dt;
        p.vy += force.y * 0.02 * dt;
      }

      // Mouse attraction/repulsion
      const dx = this.mousePos.x - p.x;
      const dy = this.mousePos.y - p.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < 150 && dist > 0) {
        const force = (150 - dist) / 150 * 0.3;
        p.vx += (dx / dist) * force * dt;
        p.vy += (dy / dist) * force * dt;
      }

      // Velocity damping
      p.vx *= 0.98;
      p.vy *= 0.98;

      // Update position
      p.x += p.vx * dt;
      p.y += p.vy * dt;

      // Trail for motion blur effect
      p.trail.push({ x: p.x, y: p.y });
      if (p.trail.length > p.maxTrail) p.trail.shift();

      // Wrap around screen
      if (p.x < -20) p.x = this.width + 20;
      if (p.x > this.width + 20) p.x = -20;
      if (p.y < -20) p.y = this.height + 20;
      if (p.y > this.height + 20) p.y = -20;

      // Pulse animation
      p.life += p.speed * 0.001 * dt;
      p.size = p.baseSize * (1 + Math.sin(p.life) * 0.3);
    }
  }

  updateRipples(dt) {
    for (let i = this.rippleWaves.length - 1; i >= 0; i--) {
      const r = this.rippleWaves[i];
      r.radius += r.speed * dt;
      if (r.radius > r.maxRadius) {
        this.rippleWaves.splice(i, 1);
      }
    }
  }

  updateGeometricShapes(dt) {
    const palette = this.getShapePalette();

    for (const s of this.geometricShapes) {
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.rotation += s.vr * dt;
      s.pulsePhase += s.pulseSpeed * dt;

      // Wrap around
      const buffer = s.size;
      if (s.x < -buffer) s.x = this.width + buffer;
      if (s.x > this.width + buffer) s.x = -buffer;
      if (s.y < -buffer) s.y = this.height + buffer;
      if (s.y > this.height + buffer) s.y = -buffer;
    }
  }

  drawParticles() {
    for (const p of this.particles) {
      // Draw trail
      if (p.trail.length > 2) {
        this.ctx.save();
        this.ctx.strokeStyle = p.color;
        this.ctx.lineWidth = p.size * 0.4;
        this.ctx.lineCap = "round";
        this.ctx.globalAlpha = p.opacity * 0.3;

        this.ctx.beginPath();
        this.ctx.moveTo(p.trail[0].x, p.trail[0].y);
        for (let i = 1; i < p.trail.length; i++) {
          this.ctx.lineTo(p.trail[i].x, p.trail[i].y);
        }
        this.ctx.stroke();
        this.ctx.restore();
      }

      // Draw particle
      this.ctx.save();
      this.ctx.fillStyle = p.color;
      this.ctx.globalAlpha = p.opacity;
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.restore();
    }
  }

  drawRipples() {
    for (const r of this.rippleWaves) {
      const progress = r.radius / r.maxRadius;
      const opacity = r.opacity * (1 - progress) * (1 - progress);

      this.ctx.save();
      this.ctx.strokeStyle = r.color;
      this.ctx.lineWidth = 2;
      this.ctx.globalAlpha = opacity;
      this.ctx.beginPath();
      this.ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
      this.ctx.stroke();
      this.ctx.restore();
    }
  }

  drawShape(s, color) {
    const pulse = 1 + Math.sin(s.pulsePhase) * 0.08;
    const drawSize = s.size * pulse;

    this.ctx.save();
    this.ctx.translate(s.x, s.y);
    this.ctx.rotate(s.rotation);
    this.ctx.fillStyle = color;
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = 1.5;
    this.ctx.globalAlpha = 0.6;

    if (s.type === "circle") {
      this.ctx.beginPath();
      this.ctx.arc(0, 0, drawSize / 2, 0, Math.PI * 2);
      this.ctx.fill();
    } else if (s.type === "square") {
      const hs = drawSize / 2;
      this.ctx.fillRect(-hs, -hs, drawSize, drawSize);
    } else if (s.type === "ring") {
      this.ctx.beginPath();
      this.ctx.arc(0, 0, drawSize / 2, 0, Math.PI * 2);
      this.ctx.stroke();
    } else if (s.type === "triangle") {
      const h = drawSize * 0.866;
      this.ctx.beginPath();
      this.ctx.moveTo(0, -h / 2);
      this.ctx.lineTo(-drawSize / 2, h / 2);
      this.ctx.lineTo(drawSize / 2, h / 2);
      this.ctx.closePath();
      this.ctx.fill();
    } else if (s.type === "hexagon") {
      this.ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const angle = (i / 6) * Math.PI * 2 - Math.PI / 6;
        const x = Math.cos(angle) * drawSize / 2;
        const y = Math.sin(angle) * drawSize / 2;
        if (i === 0) this.ctx.moveTo(x, y);
        else this.ctx.lineTo(x, y);
      }
      this.ctx.closePath();
      this.ctx.fill();
    }

    this.ctx.restore();
  }

  drawGeometricShapes() {
    const palette = this.getShapePalette();
    for (const s of this.geometricShapes) {
      this.drawShape(s, palette[s.colorIndex]);
    }
  }

  renderStaticFrame() {
    this.ctx.clearRect(0, 0, this.width, this.height);
    this.drawGrid();
    this.drawGeometricShapes();

    // Draw a few static particles
    const palette = this.getParticleColors();
    for (let i = 0; i < 30; i++) {
      const p = this.particles[i] || {
        x: Math.random() * this.width,
        y: Math.random() * this.height,
        size: 2 + Math.random() * 3,
        color: palette[Math.floor(Math.random() * palette.length)],
        opacity: 0.15
      };
      this.ctx.save();
      this.ctx.fillStyle = p.color;
      this.ctx.globalAlpha = p.opacity;
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.restore();
    }
  }

  startLoop() {
    let lastTime = 0;
    this._lastFlowTime = 0;
    const tick = (time) => {
      this.animId = requestAnimationFrame(tick);
      if (this.isPaused || this.prefersReduced) return;

      const elapsed = time - lastTime;
      if (elapsed < 32) return; // Cap at 30 FPS for minimal CPU load
      const dt = Math.min(elapsed, 100);
      lastTime = time;

      this.ctx.clearRect(0, 0, this.width, this.height);

      // Slowly move grid
      this.gridOffset.x += 0.002 * dt;
      this.gridOffset.y += 0.0015 * dt;
      this.drawGrid();

      // Update flow field periodically, not every frame
      if (time - this._lastFlowTime > 250) {
        this.updateFlowField(time);
        this._lastFlowTime = time;
      }

      // Update and draw flow field particles
      this.updateParticles(dt);
      this.drawParticles();

      // Update and draw ripples
      this.updateRipples(dt);
      this.drawRipples();

      // Update and draw geometric shapes
      this.updateGeometricShapes(dt);
      this.drawGeometricShapes();
    };
    this.animId = requestAnimationFrame(tick);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  new BentoLivingBackground("bg-canvas");
});