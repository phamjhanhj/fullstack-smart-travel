const SESSION_KEYS = ['access_token', 'refresh_token', 'user_info'] as const;

export function clearStoredSession(): void {
  for (const key of SESSION_KEYS) {
    localStorage.removeItem(key);
  }

  // Offline trip data is private and must never survive an account switch.
  localStorage.removeItem('offline_cached_trips');
}
