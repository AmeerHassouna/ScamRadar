'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import * as THREE from 'three';

const defaultCardImages = [
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b55e654d1341fb06f8_4.1.png",
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b5a080a31ee7154b19_1.png",
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b5c1e4919fd69672b8_3.png",
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b5f6a5e232e7beb4be_2.png",
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b5bea2f1b07392d936_4.png",
];

const ASCII_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789(){}[]<>;:,._-+=!@#$%^&*|\\/\"'`~?";

const generateCode = (width: number, height: number): string => {
  let text = "";
  for (let i = 0; i < width * height; i++) {
    text += ASCII_CHARS[Math.floor(Math.random() * ASCII_CHARS.length)];
  }
  let out = "";
  for (let i = 0; i < height; i++) {
    out += text.substring(i * width, (i + 1) * width) + "\n";
  }
  return out;
};

type ScannerCardStreamProps = {
  showControls?: boolean;
  showSpeed?: boolean;
  initialSpeed?: number;
  direction?: -1 | 1;
  cardImages?: string[];
  repeat?: number;
  cardGap?: number;
  friction?: number;
  scanEffect?: 'clip' | 'scramble';
};

const ScannerCardStream = ({
  showControls = false,
  showSpeed = false,
  initialSpeed = 150,
  direction = -1,
  cardImages = defaultCardImages,
  repeat = 6,
  cardGap = 60,
  friction = 0.95,
  scanEffect = 'scramble',
}: ScannerCardStreamProps) => {
  const [speed, setSpeed] = useState(initialSpeed);
  const [isPaused, setIsPaused] = useState(false);
  const [isScanning, setIsScanning] = useState(false);

  const cards = useMemo(() => {
    const totalCards = cardImages.length * repeat;
    return Array.from({ length: totalCards }, (_, i) => ({
      id: i,
      image: cardImages[i % cardImages.length],
      ascii: generateCode(Math.floor(400 / 6.5), Math.floor(250 / 13)),
    }));
  }, [cardImages, repeat]);

  const cardLineRef = useRef<HTMLDivElement>(null);
  const particleCanvasRef = useRef<HTMLCanvasElement>(null);
  const scannerCanvasRef = useRef<HTMLCanvasElement>(null);
  const originalAscii = useRef(new Map<number, string>());

  const cardStreamState = useRef({
    position: 0,
    velocity: initialSpeed,
    direction: direction,
    lastTime: performance.now(),
    cardLineWidth: (400 + cardGap) * cards.length,
  });

  const scannerState = useRef({ isScanning: false });

  const toggleAnimation = useCallback(() => setIsPaused(prev => !prev), []);

  const resetPosition = useCallback(() => {
    if (cardLineRef.current) {
      cardStreamState.current.position = cardLineRef.current.parentElement?.offsetWidth || 0;
      cardStreamState.current.velocity = initialSpeed;
      cardStreamState.current.direction = direction;
      setIsPaused(false);
    }
  }, [initialSpeed, direction]);

  const changeDirection = useCallback(() => {
    cardStreamState.current.direction *= -1;
  }, []);

  useEffect(() => {
    const cardLine = cardLineRef.current;
    const particleCanvas = particleCanvasRef.current;
    const scannerCanvas = scannerCanvasRef.current;
    if (!cardLine || !particleCanvas || !scannerCanvas) return;

    cards.forEach(card => originalAscii.current.set(card.id, card.ascii));
    let animationFrameId: number;

    // ── Three.js particle system ─────────────────────────────────
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(
      -window.innerWidth / 2, window.innerWidth / 2, 125, -125, 1, 1000
    );
    camera.position.z = 100;

    const renderer = new THREE.WebGLRenderer({ canvas: particleCanvas, alpha: true, antialias: true });
    renderer.setSize(window.innerWidth, 250);
    renderer.setClearColor(0x000000, 0);

    const particleCount = 400;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount);
    const alphas = new Float32Array(particleCount);

    const texCanvas = document.createElement("canvas");
    texCanvas.width = 100;
    texCanvas.height = 100;
    const texCtx = texCanvas.getContext("2d")!;
    const half = 50;
    const grad = texCtx.createRadialGradient(half, half, 0, half, half, half);
    grad.addColorStop(0.025, "#fff");
    grad.addColorStop(0.1, `hsl(217, 61%, 33%)`);
    grad.addColorStop(0.25, `hsl(217, 64%, 6%)`);
    grad.addColorStop(1, "transparent");
    texCtx.fillStyle = grad;
    texCtx.arc(half, half, half, 0, Math.PI * 2);
    texCtx.fill();
    const texture = new THREE.CanvasTexture(texCanvas);

    for (let i = 0; i < particleCount; i++) {
      positions[i * 3]     = (Math.random() - 0.5) * window.innerWidth * 2;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 250;
      velocities[i]        = Math.random() * 60 + 30;
      alphas[i]            = (Math.random() * 8 + 2) / 10;
    }
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("alpha",    new THREE.BufferAttribute(alphas, 1));

    const material = new THREE.ShaderMaterial({
      uniforms: { pointTexture: { value: texture } },
      vertexShader: `
        attribute float alpha;
        varying float vAlpha;
        void main() {
          vAlpha = alpha;
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = 15.0;
          gl_Position = projectionMatrix * mvPosition;
        }`,
      fragmentShader: `
        uniform sampler2D pointTexture;
        varying float vAlpha;
        void main() {
          gl_FragColor = vec4(1.0, 1.0, 1.0, vAlpha) * texture2D(pointTexture, gl_PointCoord);
        }`,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      vertexColors: false,
    });
    const particles = new THREE.Points(geometry, material);
    scene.add(particles);

    // ── 2D scanner-particle canvas ───────────────────────────────
    const ctx = scannerCanvas.getContext('2d')!;
    scannerCanvas.width  = window.innerWidth;
    scannerCanvas.height = 300;

    type ScanParticle = { x: number; y: number; vx: number; vy: number; radius: number; alpha: number; life: number; decay: number };
    let scannerParticles: ScanParticle[] = [];
    const baseMaxParticles    = 800;
    let currentMaxParticles   = baseMaxParticles;
    const scanTargetMaxParticles = 2500;

    const createScannerParticle = (): ScanParticle => ({
      x:      window.innerWidth / 2 + (Math.random() - 0.5) * 3,
      y:      Math.random() * 300,
      vx:     Math.random() * 0.8 + 0.2,
      vy:     (Math.random() - 0.5) * 0.3,
      radius: Math.random() * 0.6 + 0.4,
      alpha:  Math.random() * 0.4 + 0.6,
      life:   1.0,
      decay:  Math.random() * 0.02 + 0.005,
    });
    for (let i = 0; i < baseMaxParticles; i++) scannerParticles.push(createScannerParticle());

    // ── Scramble effect ──────────────────────────────────────────
    const runScrambleEffect = (element: HTMLElement, cardId: number) => {
      if (element.dataset.scrambling === 'true') return;
      element.dataset.scrambling = 'true';
      const originalText = originalAscii.current.get(cardId) || '';
      let scrambleCount = 0;
      const maxScrambles = 10;
      const interval = setInterval(() => {
        element.textContent = generateCode(Math.floor(400 / 6.5), Math.floor(250 / 13));
        scrambleCount++;
        if (scrambleCount >= maxScrambles) {
          clearInterval(interval);
          element.textContent = originalText;
          delete element.dataset.scrambling;
        }
      }, 30);
    };

    // ── Card clip-path updates ───────────────────────────────────
    const updateCardEffects = () => {
      const scannerX     = window.innerWidth / 2;
      const scannerWidth = 8;
      const scannerLeft  = scannerX - scannerWidth / 2;
      const scannerRight = scannerX + scannerWidth / 2;
      let anyCardIsScanning = false;

      cardLine.querySelectorAll<HTMLElement>(".card-wrapper").forEach((wrapper, index) => {
        const rect       = wrapper.getBoundingClientRect();
        const normalCard = wrapper.querySelector<HTMLElement>(".card-normal")!;
        const asciiCard  = wrapper.querySelector<HTMLElement>(".card-ascii")!;
        const asciiContent = asciiCard.querySelector<HTMLElement>('pre')!;

        if (rect.left < scannerRight && rect.right > scannerLeft) {
          anyCardIsScanning = true;
          if (scanEffect === 'scramble' && wrapper.dataset.scanned !== 'true') {
            runScrambleEffect(asciiContent, index);
          }
          wrapper.dataset.scanned = 'true';
          const intersectLeft  = Math.max(scannerLeft - rect.left, 0);
          const intersectRight = Math.min(scannerRight - rect.left, rect.width);
          normalCard.style.setProperty("--clip-right", `${(intersectLeft  / rect.width) * 100}%`);
          asciiCard.style.setProperty("--clip-left",  `${(intersectRight / rect.width) * 100}%`);
        } else {
          delete wrapper.dataset.scanned;
          if (rect.right < scannerLeft) {
            normalCard.style.setProperty("--clip-right", "100%");
            asciiCard.style.setProperty("--clip-left",  "100%");
          } else {
            normalCard.style.setProperty("--clip-right", "0%");
            asciiCard.style.setProperty("--clip-left",  "0%");
          }
        }
      });

      setIsScanning(anyCardIsScanning);
      scannerState.current.isScanning = anyCardIsScanning;
    };


    // ── Animation loop ───────────────────────────────────────────
    const animate = (currentTime: number) => {
      const deltaTime = (currentTime - cardStreamState.current.lastTime) / 1000;
      cardStreamState.current.lastTime = currentTime;

      if (!isPaused) {
        // Lerp back to auto speed after a drag flick
        cardStreamState.current.velocity +=
          (initialSpeed - cardStreamState.current.velocity) * 0.04;
        cardStreamState.current.position +=
          cardStreamState.current.velocity * cardStreamState.current.direction * deltaTime;
      }

      const { position, cardLineWidth } = cardStreamState.current;
      const containerWidth = cardLine.parentElement?.offsetWidth || 0;
      if (position < -cardLineWidth) cardStreamState.current.position = containerWidth;
      else if (position > containerWidth) cardStreamState.current.position = -cardLineWidth;
      cardLine.style.transform = `translateX(${cardStreamState.current.position}px)`;

      updateCardEffects();

      // Three.js particles
      const time = currentTime * 0.001;
      for (let i = 0; i < particleCount; i++) {
        positions[i * 3] += velocities[i] * 0.016;
        if (positions[i * 3] > window.innerWidth / 2 + 100) positions[i * 3] = -window.innerWidth / 2 - 100;
        positions[i * 3 + 1] += Math.sin(time + i * 0.1) * 0.5;
        alphas[i] = Math.max(0.1, Math.min(1, alphas[i] + (Math.random() - 0.5) * 0.05));
      }
      geometry.attributes.position.needsUpdate = true;
      geometry.attributes.alpha.needsUpdate    = true;
      renderer.render(scene, camera);

      // 2D scanner particles
      ctx.clearRect(0, 0, window.innerWidth, 300);
      const targetCount = scannerState.current.isScanning ? scanTargetMaxParticles : baseMaxParticles;
      currentMaxParticles += (targetCount - currentMaxParticles) * 0.05;
      while (scannerParticles.length < currentMaxParticles) scannerParticles.push(createScannerParticle());
      while (scannerParticles.length > currentMaxParticles) scannerParticles.pop();

      scannerParticles.forEach(p => {
        p.x    += p.vx;
        p.y    += p.vy;
        p.life -= p.decay;
        if (p.life <= 0 || p.x > window.innerWidth) Object.assign(p, createScannerParticle());
        ctx.globalAlpha = p.alpha * p.life;
        ctx.fillStyle   = "white";
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationFrameId);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      texture.dispose();
    };
  }, [isPaused, cards, cardGap, friction, scanEffect]);

  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      {/* Keyframes injected once */}
      <style>{`
        @keyframes glitch {
          0%, 16%, 50%, 100% { opacity: 1; }
          15%, 99%           { opacity: 0.9; }
          49%                { opacity: 0.8; }
        }
        .scs-glitch { animation: glitch 0.1s infinite linear alternate-reverse; }
        @keyframes scanPulse {
          0%   { opacity: 0.75; }
          100% { opacity: 1; }
        }
        .scs-scan-pulse { animation: scanPulse 1.5s infinite alternate ease-in-out; }
      `}</style>

      {showControls && (
        <div className="absolute top-4 right-4 z-30 flex gap-2">
          <button onClick={toggleAnimation}   className="px-3 py-1 text-xs bg-white/10 text-white rounded hover:bg-white/20">{isPaused ? 'Resume' : 'Pause'}</button>
          <button onClick={changeDirection}   className="px-3 py-1 text-xs bg-white/10 text-white rounded hover:bg-white/20">Flip</button>
          <button onClick={resetPosition}     className="px-3 py-1 text-xs bg-white/10 text-white rounded hover:bg-white/20">Reset</button>
        </div>
      )}
      {showSpeed && (
        <div className="absolute top-4 left-4 z-30 text-xs text-white/50 font-mono">{speed} px/s</div>
      )}

      {/* Three.js particle layer */}
      <canvas
        ref={particleCanvasRef}
        className="absolute top-1/2 left-0 -translate-y-1/2 pointer-events-none"
        style={{ width: "100vw", height: "250px", zIndex: 0 }}
      />

      {/* 2D scanner-particle layer */}
      <canvas
        ref={scannerCanvasRef}
        className="absolute top-1/2 left-0 -translate-y-1/2 pointer-events-none"
        style={{ width: "100vw", height: "300px", zIndex: 10 }}
      />

      {/* Vertical scanner line */}
      <div
        className={`scs-scan-pulse absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-0.5 h-[280px] rounded-full pointer-events-none transition-opacity duration-300`}
        style={{
          zIndex: 20,
          background: "linear-gradient(to bottom, transparent, #8b5cf6, transparent)",
          boxShadow: "0 0 10px #a78bfa, 0 0 20px #a78bfa, 0 0 30px #8b5cf6, 0 0 50px #6366f1",
          opacity: isScanning ? 1 : 0,
        }}
      />

      {/* Card stream */}
      <div className="absolute w-full h-[250px] flex items-center overflow-hidden">
        <div
          ref={cardLineRef}
          className="flex items-center whitespace-nowrap select-none will-change-transform"
          style={{ gap: `${cardGap}px` }}
        >
          {cards.map(card => (
            <div key={card.id} className="card-wrapper relative shrink-0" style={{ width: 400, height: 250 }}>
              {/* Image face — visible left of scanner */}
              <div
                className="card-normal absolute inset-0 rounded-[15px] overflow-hidden shadow-[0_15px_40px_rgba(0,0,0,0.4)]"
                style={{
                  zIndex: 2,
                  clipPath: "inset(0 0 0 var(--clip-right, 0%))",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={card.image}
                  alt=""
                  className="w-full h-full object-cover rounded-[15px] brightness-110 contrast-110 hover:brightness-125 hover:contrast-125 transition-all duration-300"
                />
              </div>
              {/* ASCII face — visible right of scanner */}
              <div
                className="card-ascii absolute inset-0 rounded-[15px] overflow-hidden"
                style={{
                  zIndex: 1,
                  clipPath: "inset(0 calc(100% - var(--clip-left, 0%)) 0 0)",
                }}
              >
                <pre
                  className="scs-glitch absolute inset-0 m-0 p-0 overflow-hidden whitespace-pre text-left align-top box-border font-mono"
                  style={{
                    fontSize: 11,
                    lineHeight: "13px",
                    color: "rgba(220,210,255,0.6)",
                    maskImage: "linear-gradient(to right, rgba(0,0,0,1) 0%, rgba(0,0,0,0.8) 30%, rgba(0,0,0,0.6) 50%, rgba(0,0,0,0.4) 80%, rgba(0,0,0,0.2) 100%)",
                    WebkitMaskImage: "linear-gradient(to right, rgba(0,0,0,1) 0%, rgba(0,0,0,0.8) 30%, rgba(0,0,0,0.6) 50%, rgba(0,0,0,0.4) 80%, rgba(0,0,0,0.2) 100%)",
                  }}
                >
                  {card.ascii}
                </pre>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export { ScannerCardStream };
