import { useId, useLayoutEffect, useRef, useState } from "react";

export default function ExpandableDescription({ children }) {
  const id = useId();
  const textRef = useRef(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);

  useLayoutEffect(() => {
    const element = textRef.current;
    const measure = () => {
      const lineHeight = parseFloat(getComputedStyle(element).lineHeight);
      setOverflows(element.scrollHeight > lineHeight * 3 + 1);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [children]);

  return (
    <div className="case-description">
      <p ref={textRef} id={id} className={expanded ? "" : "description-preview"}>
        {children}
      </p>
      {overflows || expanded ? (
        <button
          type="button"
          className="description-toggle"
          aria-expanded={expanded}
          aria-controls={id}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Read less" : "Read more"}
        </button>
      ) : null}
    </div>
  );
}
