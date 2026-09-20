import { useCallback, useEffect, useRef } from "react";

interface Props {
  /** Fraction (0..1) occupied by the left pane. */
  ratio: number;
  onChange: (ratio: number) => void;
}

// A draggable divider between the editor and preview panes.
export default function Splitter({ ratio, onChange }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);

  const onMove = useCallback(
    (clientX: number) => {
      const el = containerRef.current?.parentElement;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const next = (clientX - rect.left) / rect.width;
      onChange(Math.min(0.85, Math.max(0.15, next)));
    },
    [onChange]
  );

  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (draggingRef.current) onMove(e.clientX);
    };
    const up = () => {
      draggingRef.current = false;
      document.body.classList.remove("resizing");
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [onMove]);

  return (
    <div
      ref={containerRef}
      className="splitter"
      style={{ left: `${ratio * 100}%` }}
      onMouseDown={() => {
        draggingRef.current = true;
        document.body.classList.add("resizing");
      }}
      role="separator"
      aria-orientation="vertical"
      aria-valuenow={Math.round(ratio * 100)}
      title="拖动调整两栏比例"
    >
      <div className="splitter-grip" />
    </div>
  );
}
