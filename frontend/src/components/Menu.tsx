import { type ReactNode, useEffect, useRef } from "react";

export default function Menu({ label, children }: { label: string; children: ReactNode }) {
  const menu = useRef<HTMLDetailsElement>(null);

  function close() {
    if (menu.current) menu.current.open = false;
  }

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (!menu.current?.contains(event.target as Node)) close();
    }
    document.addEventListener("click", closeOnOutsideClick);
    return () => document.removeEventListener("click", closeOnOutsideClick);
  }, []);

  return (
    <details className="menu" ref={menu}>
      <summary className="button">
        {label}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>
      <div className="menu-list" onClick={close}>
        {children}
      </div>
    </details>
  );
}
