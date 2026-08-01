import { clearStoredSession } from './auth-storage';

describe('clearStoredSession', () => {
  it('removes tokens, user information, and private offline trips', () => {
    localStorage.setItem('access_token', 'access');
    localStorage.setItem('refresh_token', 'refresh');
    localStorage.setItem('user_info', '{"id":"user-1"}');
    sessionStorage.setItem('access_token', 'session-access');
    sessionStorage.setItem('user_info', '{"id":"user-1"}');
    localStorage.setItem('offline_cached_trips', '{"trip-1":{}}');
    localStorage.setItem('theme', 'dark');

    clearStoredSession();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(localStorage.getItem('user_info')).toBeNull();
    expect(sessionStorage.getItem('access_token')).toBeNull();
    expect(sessionStorage.getItem('user_info')).toBeNull();
    expect(localStorage.getItem('offline_cached_trips')).toBeNull();
    expect(localStorage.getItem('theme')).toBe('dark');
  });
});
