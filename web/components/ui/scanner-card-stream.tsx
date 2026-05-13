'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';

const defaultCardImages = [
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b55e654d1341fb06f8_4.1.png",
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b5a080a31ee7154b19_1.png",
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b5c1e4919fd69672b8_3.png",
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b5f6a5e232e7beb4be_2.png",
  "https://cdn.prod.website-files.com/68789c86c8bc802d61932544/689f20b5bea2f1b07392d936_4.png",
];

const ASCII_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789{}[]<>;._-+=!@#$%^&*";

const generateCode = (width: number, height: number): string => {
  let out = "";
  for (let i = 0; i < height; i++) {
    for (let j = 0; j < width; j++) {
      out += ASCII_CHARS[Math.floor(Math.random() * ASCII_CHARS.length)];
    }
    out += "\n";
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
  repeat = 5,          // reduced from 6
  cardGap = 60,
  scanEffect = 'scramble',
}: ScannerCardStreamProps) => {
  const [isPaused, setIsPaused] = useState(false);

  // Responsive card dimensions
  const [cardW, setCardW] = useState(400);
  const [cardH, setCardH] = useState(250);
  useEffect(() => {
    const update = () => {
      const mobile = window.innerWidth < 640;
      setCardW(mobile ? 270 : 400);
      setCardH(mobile ? 168 : 250);
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  const cards = useMemo(() => {
    const totalCards = cardImages.length * repeat;
    return Array.from({ length: totalCards }, (_, i) => ({
      id: i,
      image: cardImages[i % cardImages.length],
      ascii: generateCode(Math.floor(cardW / 6.5), Math.floor(cardH / 13)),
    }));
  }, [cardImages, repeat, cardW, cardH]);

  const cardLineRef       = useRef<HTMLDivElement>(null);
  const scannerCanvasRef  = useRef<HTMLCanvasElement>(null);
  const scannerLineRef    = useRef<HTMLDivElement>(null);
  const originalAscii     = useRef(new Map<number, string>());
  // Cache of card wrapper DOM nodes — populated once after first render
  const cardNodesRef      = useRef<{ wrapper: HTMLElement; normal: HTMLElement; ascii: HTMLElement; asciiPre: HTMLElement }[]>([]);
  const isVisibleRef      = useRef(true);

  const cardStreamState = useRef({
    position:      0,
    velocity:      initialSpeed,
    direction:     direction,
    lastTime:      performance.now(),
    cardLineWidth: (400 + cardGap) * cards.length,
    isScanning:    false,
    viewportW:     typeof window !== 'undefined' ? window.innerWidth : 1024,
  });

  const toggleAnimation = useCallback(() => setIsPaused(prev => !prev), []);
  const changeDirection = useCallback(() => { cardStreamState.current.direction *= -1; }, []);
  const resetPosition   = useCallback(() => {
    if (cardLineRef.current) {
      cardStreamState.current.position  = cardLineRef.current.parentElement?.offsetWidth || 0;
      cardStreamState.current.velocity  = initialSpeed;
      cardStreamState.current.direction = direction;
      setIsPaused(false);
    }
  }, [initialSpeed, direction]);

  // Pause when tab/component is off-screen
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { isVisibleRef.current = entry.isIntersecting; },
      { threshold: 0 }
    );
    if (cardLineRef.current?.parentElement) observer.observe(cardLineRef.current.parentElement);
    const onVisibility = () => { isVisibleRef.current = document.visibilityState === 'visible'; };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  useEffect(() => {
    cardStreamState.current.lastTime      = performance.now();
    cardStreamState.current.cardLineWidth = (cardW + cardGap) * cards.length;
    cardStreamState.current.viewportW     = window.innerWidth;

    const cardLine     = cardLineRef.current;
    const scannerCanvas = scannerCanvasRef.current;
    if (!cardLine || !scannerCanvas) return;

    cards.forEach(card => originalAscii.current.set(card.id, card.ascii));

    // Cache DOM nodes once — avoids querySelectorAll on every frame
    const populateNodeCache = () => {
      cardNodesRef.current = [];
      cardLine.querySelectorAll<HTMLElement>('.card-wrapper').forEach((wrapper, index) => {
        const normal   = wrapper.querySelector<HTMLElement>('.card-normal')!;
        const ascii    = wrapper.querySelector<HTMLElement>('.card-ascii')!;
        const asciiPre = ascii.querySelector<HTMLElement>('pre')!;
        if (normal && ascii && asciiPre) {
          cardNodesRef.current.push({ wrapper, normal, ascii, asciiPre });
          asciiPre.dataset.cardIndex = String(index);
        }
      });
    };
    // Give React one tick to render the cards before caching
    const cacheTimer = setTimeout(populateNodeCache, 50);

    // 2D scanner particle canvas — reduced counts
    const canvasH = cardH + 50;
    const ctx     = scannerCanvas.getContext('2d')!;
    scannerCanvas.width  = window.innerWidth;
    scannerCanvas.height = canvasH;

    type ScanParticle = { x: number; y: number; vx: number; vy: number; radius: number; alpha: number; life: number; decay: number };
    const BASE_PARTICLES = 60;   // was 800
    const SCAN_PARTICLES = 140;  // was 2500
    let scannerParticles: ScanParticle[] = [];
    let currentMaxParticles = BASE_PARTICLES;

    const createParticle = (): ScanParticle => ({
      x:      cardStreamState.current.viewportW / 2 + (Math.random() - 0.5) * 3,
      y:      Math.random() * canvasH,
      vx:     Math.random() * 0.8 + 0.2,
      vy:     (Math.random() - 0.5) * 0.3,
      radius: Math.random() * 0.6 + 0.4,
      alpha:  Math.random() * 0.4 + 0.6,
      life:   1.0,
      decay:  Math.random() * 0.02 + 0.005,
    });
    for (let i = 0; i < BASE_PARTICLES; i++) scannerParticles.push(createParticle());

    // Scramble effect
    const runScramble = (pre: HTMLElement, cardId: number) => {
      if (pre.dataset.scrambling === 'true') return;
      pre.dataset.scrambling = 'true';
      const original  = originalAscii.current.get(cardId) || '';
      let   count     = 0;
      const MAX       = 8; // was 10
      const id = setInterval(() => {
        pre.textContent = generateCode(Math.floor(cardW / 6.5), Math.floor(cardH / 13));
        if (++count >= MAX) {
          clearInterval(id);
          pre.textContent = original;
          delete pre.dataset.scrambling;
        }
      }, 40); // was 30ms — slightly slower, less CPU
    };

    // Card clip-path updates — uses cached nodes, no DOM query per frame
    const updateCards = () => {
      const vw          = cardStreamState.current.viewportW;
      const scannerX    = vw / 2;
      const halfW       = 4;
      const scanLeft    = scannerX - halfW;
      const scanRight   = scannerX + halfW;
      let   anyScanning = false;

      for (const { wrapper, normal, ascii, asciiPre } of cardNodesRef.current) {
        const rect = wrapper.getBoundingClientRect();

        if (rect.left < scanRight && rect.right > scanLeft) {
          anyScanning = true;
          if (scanEffect === 'scramble' && wrapper.dataset.scanned !== 'true') {
            const idx = parseInt(asciiPre.dataset.cardIndex || '0', 10);
            runScramble(asciiPre, idx);
          }
          wrapper.dataset.scanned = 'true';
          const il = Math.max(scanLeft - rect.left, 0);
          const ir = Math.min(scanRight - rect.left, rect.width);
          normal.style.setProperty('--clip-right', `${(il / rect.width) * 100}%`);
          ascii.style.setProperty('--clip-left',   `${(ir / rect.width) * 100}%`);
        } else {
          delete wrapper.dataset.scanned;
          if (rect.right < scanLeft) {
            normal.style.setProperty('--clip-right', '100%');
            ascii.style.setProperty('--clip-left',   '100%');
          } else {
            normal.style.setProperty('--clip-right', '0%');
            ascii.style.setProperty('--clip-left',   '0%');
          }
        }
      }

      // Directly update scanner line DOM — no React state, no re-render
      if (scannerLineRef.current) {
        scannerLineRef.current.style.opacity = anyScanning ? '1' : '0';
      }
      cardStreamState.current.isScanning = anyScanning;
    };

    let animationFrameId: number;

    const animate = (currentTime: number) => {
      // Skip frame if off-screen/tab hidden
      if (!isVisibleRef.current) {
        cardStreamState.current.lastTime = currentTime;
        animationFrameId = requestAnimationFrame(animate);
        return;
      }

      const dt = Math.min((currentTime - cardStreamState.current.lastTime) / 1000, 0.05);
      cardStreamState.current.lastTime = currentTime;

      if (!isPaused) {
        cardStreamState.current.velocity +=
          (initialSpeed - cardStreamState.current.velocity) * 0.04;
        cardStreamState.current.position +=
          cardStreamState.current.velocity * cardStreamState.current.direction * dt;
      }

      const { position, cardLineWidth } = cardStreamState.current;
      const containerW = cardLine.parentElement?.offsetWidth || 0;
      if (position < -cardLineWidth) cardStreamState.current.position = containerW;
      else if (position > containerW) cardStreamState.current.position = -cardLineWidth;
      cardLine.style.transform = `translateX(${cardStreamState.current.position}px)`;

      if (cardNodesRef.current.length > 0) updateCards();

      // 2D particles
      const vw = cardStreamState.current.viewportW;
      ctx.clearRect(0, 0, vw, canvasH);
      const target = cardStreamState.current.isScanning ? SCAN_PARTICLES : BASE_PARTICLES;
      currentMaxParticles += (target - currentMaxParticles) * 0.08;
      while (scannerParticles.length < currentMaxParticles) scannerParticles.push(createParticle());
      if (scannerParticles.length > currentMaxParticles + 10)
        scannerParticles.length = Math.floor(currentMaxParticles);

      ctx.fillStyle = 'white';
      for (const p of scannerParticles) {
        p.x    += p.vx;
        p.y    += p.vy;
        p.life -= p.decay;
        if (p.life <= 0 || p.x > vw) Object.assign(p, createParticle());
        ctx.globalAlpha = p.alpha * p.life;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
      }

      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      clearTimeout(cacheTimer);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isPaused, cards, cardGap, scanEffect, cardW, cardH, initialSpeed]);

  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      <style>{`
        @keyframes scanPulse { 0% { opacity: 0.75; } 100% { opacity: 1; } }
        .scs-scan-pulse { animation: scanPulse 1.5s infinite alternate ease-in-out; }
      `}</style>

      {showControls && (
        <div className="absolute top-4 right-4 z-30 flex gap-2">
          <button onClick={toggleAnimation} className="px-3 py-1 text-xs bg-white/10 text-white rounded hover:bg-white/20">{isPaused ? 'Resume' : 'Pause'}</button>
          <button onClick={changeDirection}  className="px-3 py-1 text-xs bg-white/10 text-white rounded hover:bg-white/20">Flip</button>
          <button onClick={resetPosition}    className="px-3 py-1 text-xs bg-white/10 text-white rounded hover:bg-white/20">Reset</button>
        </div>
      )}
      {showSpeed && (
        <div className="absolute top-4 left-4 z-30 text-xs text-white/50 font-mono">{initialSpeed} px/s</div>
      )}

      {/* Ambient gradient centre glow — replaces heavy Three.js WebGL particle system */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none"
        style={{
          width: '60%',
          height: '100%',
          background: 'radial-gradient(ellipse at 50% 50%, rgba(139,92,246,0.06) 0%, transparent 70%)',
          zIndex: 0,
        }}
      />

      {/* 2D scanner-particle layer */}
      <canvas
        ref={scannerCanvasRef}
        className="absolute top-1/2 left-0 -translate-y-1/2 pointer-events-none"
        style={{ width: '100vw', height: cardH + 50, zIndex: 10, willChange: 'contents' }}
      />

      {/* Vertical scanner line — opacity controlled directly via ref, no React state */}
      <div
        ref={scannerLineRef}
        className="scs-scan-pulse absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-0.5 rounded-full pointer-events-none"
        style={{
          height: cardH + 20,
          zIndex: 20,
          background: 'linear-gradient(to bottom, transparent, #8b5cf6, transparent)',
          boxShadow: '0 0 10px #a78bfa, 0 0 20px #a78bfa, 0 0 30px #8b5cf6',
          opacity: 0,
          transition: 'opacity 0.3s',
          willChange: 'opacity',
        }}
      />

      {/* Card stream */}
      <div className="absolute inset-0 flex items-center overflow-hidden">
        <div
          ref={cardLineRef}
          className="flex items-center whitespace-nowrap select-none"
          style={{ gap: `${cardGap}px`, willChange: 'transform' }}
        >
          {cards.map(card => (
            <div key={card.id} className="card-wrapper relative shrink-0" style={{ width: cardW, height: cardH }}>

              {/* Image face */}
              <div
                className="card-normal absolute inset-0 rounded-[15px] overflow-hidden shadow-[0_15px_40px_rgba(0,0,0,0.4)]"
                style={{ zIndex: 2, clipPath: 'inset(0 0 0 var(--clip-right, 0%))' }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={card.image}
                  alt=""
                  className="w-full h-full object-cover rounded-[15px] brightness-110 contrast-110"
                />
              </div>

              {/* ASCII face */}
              <div
                className="card-ascii absolute inset-0 rounded-[15px] overflow-hidden"
                style={{ zIndex: 1, clipPath: 'inset(0 calc(100% - var(--clip-left, 0%)) 0 0)' }}
              >
                <pre
                  className="absolute inset-0 m-0 p-0 overflow-hidden whitespace-pre text-left align-top box-border font-mono"
                  style={{
                    fontSize: 11,
                    lineHeight: '13px',
                    color: 'rgba(220,210,255,0.6)',
                    maskImage: 'linear-gradient(to right, rgba(0,0,0,1) 0%, rgba(0,0,0,0.6) 50%, rgba(0,0,0,0.2) 100%)',
                    WebkitMaskImage: 'linear-gradient(to right, rgba(0,0,0,1) 0%, rgba(0,0,0,0.6) 50%, rgba(0,0,0,0.2) 100%)',
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
