/** Decorative spinner; pair it with visible text (see LoadingState, Button). */
export function Spinner({ size = 'md' }: { size?: 'sm' | 'md' }) {
  return <span className={`spinner spinner--${size}`} aria-hidden="true" />;
}

/** Full-area loading message, announced politely to screen readers. */
export function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-state" role="status">
      <Spinner />
      <p>{label}</p>
    </div>
  );
}
