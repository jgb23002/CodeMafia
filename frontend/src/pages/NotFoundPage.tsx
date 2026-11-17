import { Link } from 'react-router-dom';
import { PlaceholderPage } from './PlaceholderPage';

export function NotFoundPage() {
  return (
    <PlaceholderPage title="Page not found">
      <p>There’s nothing at this address.</p>
      <p>
        <Link to="/">Go to the home page</Link> to create or join a room.
      </p>
    </PlaceholderPage>
  );
}
