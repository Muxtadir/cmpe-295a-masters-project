import { useId, useState } from "react";

export function InfoTooltip({ text, label = "More information" }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <span className="tooltip-wrap">
      <button
        type="button"
        className="tooltip-btn"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        i
      </button>
      {open ? (
        <span role="tooltip" id={id} className="tooltip-bubble">
          {text}
        </span>
      ) : null}
    </span>
  );
}
