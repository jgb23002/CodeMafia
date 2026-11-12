import type { InputHTMLAttributes } from 'react';

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  id: string;
  label: string;
  hint?: string;
  /** Shown instead of the hint, announced immediately, and marks the input invalid. */
  error?: string | null;
};

export function TextField({ id, label, hint, error, className, ...input }: TextFieldProps) {
  const messageId = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        {...input}
        id={id}
        className={['field__input', className].filter(Boolean).join(' ')}
        aria-invalid={error ? true : undefined}
        aria-describedby={messageId}
      />
      {error ? (
        <p id={messageId} className="field__error" role="alert">
          {error}
        </p>
      ) : (
        hint && (
          <p id={messageId} className="field__hint">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
