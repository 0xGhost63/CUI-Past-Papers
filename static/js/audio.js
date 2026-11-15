// Audio Synthesizer for Archivist v2.0
// Procedural Web Audio haptics with zero external audio assets
// Pure Web Audio API: Works offline, responsive, crisp tactile feedback

class AudioEngine {
  constructor() {
    this.ctx = null;
    this.muted = localStorage.getItem("archivist_audio_muted") === "true";
    this.unlocked = false;

    // Auto-unlock audio context on first user interaction
    if (typeof window !== "undefined") {
      const unlock = () => {
        this.ensureContext();
        if (this.ctx && this.ctx.state === "suspended") {
          this.ctx.resume().catch(() => {});
        }
        this.unlocked = true;
      };
      ["pointerdown", "click", "keydown", "touchstart"].forEach((evt) => {
        window.addEventListener(evt, unlock, { once: true, passive: true });
      });
    }
  }

  init() {
    if (!this.ctx && typeof window !== "undefined") {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        try {
          this.ctx = new AudioContextClass();
        } catch (e) {
          console.warn("[Archivist Audio] AudioContext initialization deferred:", e);
        }
      }
    }
  }

  ensureContext() {
    this.init();
    if (this.ctx && this.ctx.state === "suspended") {
      return this.ctx.resume().catch(() => {});
    }
    return Promise.resolve();
  }

  toggleMute() {
    this.muted = !this.muted;
    try {
      localStorage.setItem("archivist_audio_muted", this.muted.toString());
    } catch (e) {}

    if (!this.muted) {
      this.ensureContext();
      // Play confirmation tick when unmuting
      setTimeout(() => this.playSwitch(), 50);
    }
    return this.muted;
  }

  isMuted() {
    return this.muted;
  }

  // Soft mechanical tick for buttons, tabs, checkboxes
  playTick(frequency = 1200) {
    if (this.muted) return;
    this.ensureContext();
    if (!this.ctx) return;

    const play = () => {
      try {
        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(frequency, now);
        osc.frequency.exponentialRampToValueAtTime(360, now + 0.04);

        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.045);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start(now);
        osc.stop(now + 0.05);
      } catch (e) {}
    };

    if (this.ctx.state === "running") {
      play();
    } else {
      this.ctx.resume().then(play).catch(() => {});
    }
  }

  // Crisp mechanical switch click for toggles, pills, and filter selection
  playSwitch() {
    if (this.muted) return;
    this.ensureContext();
    if (!this.ctx) return;

    const play = () => {
      try {
        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = "triangle";
        osc.frequency.setValueAtTime(680, now);
        osc.frequency.exponentialRampToValueAtTime(1750, now + 0.05);

        gain.gain.setValueAtTime(0.14, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.055);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start(now);
        osc.stop(now + 0.06);
      } catch (e) {}
    };

    if (this.ctx.state === "running") {
      play();
    } else {
      this.ctx.resume().then(play).catch(() => {});
    }
  }

  // Harmonic chord chime for download completion or sync success
  playSuccess() {
    if (this.muted) return;
    this.ensureContext();
    if (!this.ctx) return;

    const play = () => {
      try {
        const notes = [523.25, 659.25, 783.99, 1046.5]; // C5, E5, G5, C6
        const now = this.ctx.currentTime;

        notes.forEach((freq, idx) => {
          const osc = this.ctx.createOscillator();
          const gain = this.ctx.createGain();
          const noteTime = now + idx * 0.045;

          osc.type = "sine";
          osc.frequency.setValueAtTime(freq, noteTime);

          gain.gain.setValueAtTime(0.10, noteTime);
          gain.gain.exponentialRampToValueAtTime(0.0001, noteTime + 0.38);

          osc.connect(gain);
          gain.connect(this.ctx.destination);

          osc.start(noteTime);
          osc.stop(noteTime + 0.42);
        });
      } catch (e) {}
    };

    if (this.ctx.state === "running") {
      play();
    } else {
      this.ctx.resume().then(play).catch(() => {});
    }
  }

  // Subtle alert tone for errors or empty search
  playAlert() {
    if (this.muted) return;
    this.ensureContext();
    if (!this.ctx) return;

    const play = () => {
      try {
        const now = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(320, now);
        osc.frequency.exponentialRampToValueAtTime(160, now + 0.14);

        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.145);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start(now);
        osc.stop(now + 0.15);
      } catch (e) {}
    };

    if (this.ctx.state === "running") {
      play();
    } else {
      this.ctx.resume().then(play).catch(() => {});
    }
  }
}

// Global Audio Engine Instance
window.AudioSys = window.AudioSys || new AudioEngine();
