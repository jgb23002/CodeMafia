import { Button } from './Button';

interface ErrorStateProps {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

/** Replaces a screen that couldn't load: what went wrong plus one way forward. */
export function ErrorState({ title, message, actionLabel = 'Try again', onAction }: ErrorStateProps) {
  return (
    <section className="error-state" role="alert">
      <h1>{title}</h1>
      <p>{message}</p>
      {onAction && <Button onClick={onAction}>{actionLabel}</Button>}
    </section>
  );
}
