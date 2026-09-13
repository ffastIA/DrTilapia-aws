// components/ui/CornerMarks.tsx
//
// As marcas de registro (cruz nos 4 cantos) da identidade Dr. Tilap-IA.
// Reimplementação em Tailwind puro (sem depender do CSS Module da landing)
// de styles/dr-tilapia.module.css .corner/.cornerTl/.cornerTr/.cornerBl/.cornerBr,
// para uso em qualquer página do kit. O elemento pai precisa de `position: relative`.
import React from 'react';

type CornerPosition = 'tl' | 'tr' | 'bl' | 'br';

const POSITION_CLASSES: Record<CornerPosition, string> = {
  tl: 'top-[-8px] left-[-8px]',
  tr: 'top-[-8px] right-[-8px]',
  bl: 'bottom-[-8px] left-[-8px]',
  br: 'bottom-[-8px] right-[-8px]',
};

function CornerMark({ position }: { position: CornerPosition }) {
  return (
    <i
      className={`absolute w-[15px] h-[15px] pointer-events-none text-foreground/55 ${POSITION_CLASSES[position]}`}
    >
      <span className="absolute left-[7px] top-0 w-px h-full bg-current" />
      <span className="absolute top-[7px] left-0 w-full h-px bg-current" />
    </i>
  );
}

export default function CornerMarks() {
  return (
    <>
      <CornerMark position="tl" />
      <CornerMark position="tr" />
      <CornerMark position="bl" />
      <CornerMark position="br" />
    </>
  );
}
