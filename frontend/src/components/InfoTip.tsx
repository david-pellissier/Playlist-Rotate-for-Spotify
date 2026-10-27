import { type SyntheticEvent, useState } from "react";

const MAX_WIDTH = 280;
const MARGIN = 8;

export default function InfoTip({ text }: { text: string }) {
  const [offset, setOffset] = useState(-MARGIN);

  function keepOnScreen(event: SyntheticEvent<HTMLElement>) {
    const anchor = event.currentTarget.getBoundingClientRect().left;
    const width = Math.min(MAX_WIDTH, innerWidth * 0.8);
    const left = Math.max(MARGIN, Math.min(anchor - MARGIN, innerWidth - width - MARGIN));
    setOffset(left - anchor);
  }

  return (
    <span
      className="info-tip"
      tabIndex={0}
      role="img"
      aria-label={text}
      onMouseEnter={keepOnScreen}
      onFocus={keepOnScreen}
      onClick={(e) => e.preventDefault()}
    >
      ?
      <span className="info-tip-text" role="tooltip" style={{ left: offset }}>{text}</span>
    </span>
  );
}
