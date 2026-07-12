import { Component, inject, signal } from '@angular/core';
import { RouterOutlet, Router, RouterLink, NavigationEnd } from '@angular/router';
import { AuthService } from './services/auth.service';
import { ThemeService } from './services/theme.service';
import { TripInviteNotification, TripService } from './services/trip.service';
import { CommonModule } from '@angular/common';
import { filter } from 'rxjs';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  private readonly router = inject(Router);
  private readonly authService = inject(AuthService);
  private readonly themeService = inject(ThemeService);
  private readonly tripService = inject(TripService);

  readonly isAuthenticated = this.authService.isAuthenticated;
  readonly currentUser = this.authService.currentUser;

  currentUrl = signal<string>('');
  currentTab = signal<string>('');
  readonly isDarkMode = this.themeService.isDarkMode;
  readonly fallbackAvatarUrl = '/default-avatars/avatar-01.svg';
  readonly pendingInvites = signal<TripInviteNotification[]>([]);
  readonly isNotificationsOpen = signal(false);
  readonly isLoadingInvites = signal(false);
  readonly inviteActionId = signal<string | null>(null);
  readonly notificationError = signal<string | null>(null);

  constructor() {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      const url = event.urlAfterRedirects || event.url || '';
      this.currentUrl.set(url.split('?')[0]);
      
      const queryParams = new URLSearchParams(url.split('?')[1] || '');
      this.currentTab.set(queryParams.get('tab') || 'explore');
      if (this.isAuthenticated()) {
        this.loadPendingInvites();
      } else {
        this.pendingInvites.set([]);
        this.isNotificationsOpen.set(false);
      }
    });
  }

  isCurrentTab(tab: string): boolean {
    return this.currentUrl().includes('/dashboard') && this.currentTab() === tab;
  }

  isCurrentPath(path: string): boolean {
    return this.currentUrl() === path;
  }

  logout(): void {
    this.authService.logout();
    this.pendingInvites.set([]);
    this.isNotificationsOpen.set(false);
    this.router.navigate(['/login']);
  }

  getUserAvatarUrl(): string {
    const avatarUrl = this.currentUser()?.avatar_url || '';
    return avatarUrl.startsWith('/default-avatars/') ? avatarUrl : this.fallbackAvatarUrl;
  }

  toggleTheme(): void {
    this.themeService.toggleTheme();
  }

  toggleNotifications(): void {
    const willOpen = !this.isNotificationsOpen();
    this.isNotificationsOpen.set(willOpen);
    if (willOpen) {
      this.loadPendingInvites();
    }
  }

  loadPendingInvites(): void {
    if (!this.isAuthenticated() || this.isLoadingInvites()) {
      return;
    }
    this.isLoadingInvites.set(true);
    this.notificationError.set(null);
    this.tripService.listPendingTripInvites().subscribe({
      next: (response) => {
        this.pendingInvites.set(response.data || []);
        this.isLoadingInvites.set(false);
      },
      error: () => {
        this.notificationError.set('Khong the tai loi moi chia se.');
        this.isLoadingInvites.set(false);
      },
    });
  }

  acceptInvite(invite: TripInviteNotification, event?: Event): void {
    event?.stopPropagation();
    if (this.inviteActionId()) {
      return;
    }
    this.inviteActionId.set(invite.id);
    this.notificationError.set(null);
    this.tripService.acceptEmailTripInvite(invite.id).subscribe({
      next: () => {
        this.pendingInvites.set(this.pendingInvites().filter((item) => item.id !== invite.id));
        this.inviteActionId.set(null);
        this.isNotificationsOpen.set(false);
        this.router.navigate(['/dashboard'], { queryParams: { tab: 'my-trips' } });
      },
      error: (err) => {
        this.notificationError.set(err?.error?.message || 'Khong the chap nhan loi moi.');
        this.inviteActionId.set(null);
      },
    });
  }

  rejectInvite(invite: TripInviteNotification, event?: Event): void {
    event?.stopPropagation();
    if (this.inviteActionId()) {
      return;
    }
    this.inviteActionId.set(invite.id);
    this.notificationError.set(null);
    this.tripService.rejectTripInvite(invite.id).subscribe({
      next: () => {
        this.pendingInvites.set(this.pendingInvites().filter((item) => item.id !== invite.id));
        this.inviteActionId.set(null);
      },
      error: (err) => {
        this.notificationError.set(err?.error?.message || 'Khong the tu choi loi moi.');
        this.inviteActionId.set(null);
      },
    });
  }

  getInviteRoleLabel(role: string): string {
    return role === 'editor' ? 'co the chinh sua' : 'chi xem';
  }

  formatInviteDateRange(invite: TripInviteNotification): string {
    const start = this.formatShortDate(invite.trip.start_date);
    const end = this.formatShortDate(invite.trip.end_date);
    return start === end ? start : `${start} - ${end}`;
  }

  private formatShortDate(value: string): string {
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }
}
