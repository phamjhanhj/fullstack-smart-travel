import { Injectable, inject, signal } from '@angular/core';
import { AuthService } from './auth.service';

@Injectable({
  providedIn: 'root',
})
export class PwaService {
  private readonly authService = inject(AuthService);
  readonly isOnline = signal<boolean>(navigator.onLine);
  readonly isInstallable = signal<boolean>(false);
  readonly isInstalled = signal<boolean>(false);
  private deferredPrompt: any = null;
  readonly pendingSyncCount = signal<number>(0);

  constructor() {
    this.initNetworkStatusListener();
    this.initInstallPromptListener();
    this.registerServiceWorker();
  }

  private initNetworkStatusListener(): void {
    window.addEventListener('online', () => this.isOnline.set(true));
    window.addEventListener('offline', () => this.isOnline.set(false));
  }

  enqueueOfflineAction(type: 'journal' | 'expense' | 'check_in', tripId: string, payload: unknown): string {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const queue = this.getOfflineQueue();
    queue.push({ id, type, tripId, payload, createdAt: new Date().toISOString(), attempts: 0 });
    sessionStorage.setItem(this.offlineQueueKey(), JSON.stringify(queue));
    this.pendingSyncCount.set(queue.length);
    return id;
  }

  getOfflineQueue(): any[] {
    try { return JSON.parse(sessionStorage.getItem(this.offlineQueueKey()) || '[]'); } catch { return []; }
  }

  async syncOfflineQueue(handler: (action: any) => Promise<void>): Promise<void> {
    if (!this.isOnline()) return;
    const remaining: any[] = [];
    for (const action of this.getOfflineQueue()) {
      try { await handler(action); } catch { remaining.push({ ...action, attempts: (action.attempts || 0) + 1 }); }
    }
    sessionStorage.setItem(this.offlineQueueKey(), JSON.stringify(remaining));
    this.pendingSyncCount.set(remaining.length);
  }

  private offlineQueueKey(): string {
    return `offline_action_queue:${this.authService.currentUser()?.id || 'guest'}`;
  }

  private initInstallPromptListener(): void {
    window.addEventListener('beforeinstallprompt', (e: Event) => {
      e.preventDefault();
      this.deferredPrompt = e;
      this.isInstallable.set(true);
    });

    window.addEventListener('appinstalled', () => {
      this.isInstallable.set(false);
      this.isInstalled.set(true);
      this.deferredPrompt = null;
      console.log('Smart Travel Planner PWA was installed successfully!');
    });
  }

  private registerServiceWorker(): void {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker
          .register('/sw.js')
          .then((reg) => {
            console.log('Service Worker registered with scope:', reg.scope);
          })
          .catch((err) => {
            console.warn('Service Worker registration failed:', err);
          });
      });
    }
  }

  promptInstall(): Promise<boolean> {
    if (!this.deferredPrompt) return Promise.resolve(false);

    this.deferredPrompt.prompt();
    return this.deferredPrompt.userChoice.then((choiceResult: { outcome: string }) => {
      if (choiceResult.outcome === 'accepted') {
        this.isInstallable.set(false);
        this.isInstalled.set(true);
        this.deferredPrompt = null;
        return true;
      }
      return false;
    });
  }

  // Cache trip details locally for offline access
  cacheTripLocally(trip: any): void {
    try {
      const cacheKey = this.privateTripCacheKey(trip.id);
      if (!cacheKey) return;
      const cachedTripsRaw = sessionStorage.getItem('offline_cached_trips');
      const cachedTripsMap: Record<string, any> = cachedTripsRaw ? JSON.parse(cachedTripsRaw) : {};
      cachedTripsMap[cacheKey] = {
        ...trip,
        _cachedAt: new Date().toISOString(),
      };
      sessionStorage.setItem('offline_cached_trips', JSON.stringify(cachedTripsMap));
    } catch (e) {
      console.warn('Could not save trip to local offline cache', e);
    }
  }

  getLocalCachedTrip(tripId: string): any | null {
    try {
      const cacheKey = this.privateTripCacheKey(tripId);
      if (!cacheKey) return null;
      const cachedTripsRaw = sessionStorage.getItem('offline_cached_trips');
      if (!cachedTripsRaw) return null;
      const cachedTripsMap: Record<string, any> = JSON.parse(cachedTripsRaw);
      return cachedTripsMap[cacheKey] || null;
    } catch (e) {
      return null;
    }
  }

  private privateTripCacheKey(tripId: string): string | null {
    const userId = this.authService.currentUser()?.id;
    return userId ? `${userId}:${tripId}` : null;
  }
}
