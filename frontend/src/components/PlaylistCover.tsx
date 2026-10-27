import type { CSSProperties } from "react";
import { nameHue } from "../format";

export default function PlaylistCover({ name, url, large = false }: { name: string; url: string | null; large?: boolean }) {
  const className = large ? "playlist-cover large" : "playlist-cover";
  if (url) return <img className={className} src={url} alt="" loading="lazy" />;
  return (
    <span className={`${className} placeholder`} style={{ "--cover-hue": nameHue(name) } as CSSProperties} aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 18V5l12-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="16" r="3" />
      </svg>
    </span>
  );
}
