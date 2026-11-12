import type { ButtonHTMLAttributes } from 'react';
import { Spinner } from './Spinner';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost';
  /** Shows a spinner, swaps the label for `loadingText`, and disables the button. */
  loading?: boolean;
  loadingText?: string;
};

export function Button({
  variant = 'primary',
  loading = false,
  loadingText,
  disabled,
  className,
  type = 'button',
  children,
  ...rest
}: ButtonProps) {
  const classes = ['button', `button--${variant}`, className].filter(Boolean).join(' ');
  return (
    <button {...rest} type={type} className={classes} disabled={disabled || loading} aria-busy={loading || undefined}>
      {loading && <Spinner size="sm" />}
      {loading && loadingText ? loadingText : children}
    </button>
  );
}
