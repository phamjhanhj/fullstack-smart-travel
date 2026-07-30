import { InjectionToken } from '@angular/core';

declare global {
  interface Window {
    __APP_CONFIG__?: {
      apiBaseUrl?: string;
    };
  }
}

export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL');

export function resolveApiBaseUrl(): string {
  const configured = window.__APP_CONFIG__?.apiBaseUrl?.trim();
  if (!configured) return '/api';
  return configured.replace(/\/+$/, '');
}
