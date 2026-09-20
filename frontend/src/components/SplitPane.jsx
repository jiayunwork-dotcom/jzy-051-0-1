import { useEffect, useRef, useState } from "react";

// 可拖动分栏：左右比例通过拖动中间分隔条调整
export default function SplitPane({ left, right, initial = 0.5 }) {
  const [frac, setFrac] = useState(initial);
  const containerRef = useRef(null);
  const dragging = useRef(false);

  useEffect(() => {
    const move = (e) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const f = (e.clientX - rect.left) / rect.width;
      setFrac(Math.min(0.8, Math.max(0.2, f)));
    };
    const up = () => {
      dragging.current = false;
      document.body.classList.remove("resizing");
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, []);

  return (
    <div className="split-pane" ref={containerRef}>
      <div className="split-left" style={{ width: `${frac * 100}%` }}>
        {left}
      </div>
      <div
        className="split-divider"
        onMouseDown={() => {
          dragging.current = true;
          document.body.classList.add("resizing");
        }}
        role="separator"
        aria-orientation="vertical"
        title="拖动调整左右比例"
      />
      <div className="split-right" style={{ width: `${(1 - frac) * 100}%` }}>
        {right}
      </div>
    </div>
  );
}
