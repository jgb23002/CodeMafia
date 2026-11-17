import type { ReactNode } from 'react';

/** Non-blocking notice above content, e.g. "connection lost, showing last known state". */
export function Banner({ children }: { children: ReactNode }) {
  return (
    <div className="banner" role="status">
      <span className="banner__icon" aria-hidden="true">
        !
      </span>
      <p>{children}</p>
    </div>
  );
}
