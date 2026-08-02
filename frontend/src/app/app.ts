import { Component, HostListener, inject, signal, computed } from '@angular/core';
import { RouterOutlet, Router, RouterLink, NavigationEnd } from '@angular/router';
import { AuthService } from './services/auth.service';
import { ThemeService } from './services/theme.service';
import { TripInviteNotification, TripService } from './services/trip.service';
import { CommonModule } from '@angular/common';
import { filter } from 'rxjs';
import { P1Service, UserNotification } from './services/p1.service';

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
  private readonly p1Service = inject(P1Service);

  readonly isAuthenticated = this.authService.isAuthenticated;
  readonly isAdmin = this.authService.isAdmin;
  readonly currentUser = this.authService.currentUser;

  currentUrl = signal<string>('');
  currentTab = signal<string>('');
  readonly isAuthPage = computed(() => this.currentUrl() === '/login' || this.currentUrl() === '/register');
  readonly isDarkMode = this.themeService.isDarkMode;
  readonly fallbackAvatarUrl = '/default-avatars/avatar-01.svg';
  readonly pendingInvites = signal<TripInviteNotification[]>([]);
  readonly isNotificationsOpen = signal(false);
  readonly isLoadingInvites = signal(false);
  readonly inviteActionId = signal<string | null>(null);
  readonly notificationError = signal<string | null>(null);
  readonly notifications = signal<UserNotification[]>([]);
  readonly unreadNotificationCount = signal(0);
  readonly totalNotificationCount = computed(() => this.pendingInvites().length + this.unreadNotificationCount());

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.isNotificationsOpen()) return;
    const target = event.target as HTMLElement;
    if (!target.closest('.notification-container')) {
      this.isNotificationsOpen.set(false);
    }
  }

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
        this.loadNotifications();
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

  isCommunityPath(): boolean {
    return this.currentUrl().startsWith('/community') && !this.isModerationPath();
  }

  isModerationPath(): boolean {
    return this.currentUrl().startsWith('/community/moderation');
  }

  logout(): void {
    this.authService.logout();
    this.pendingInvites.set([]);
    this.notifications.set([]);
    this.isNotificationsOpen.set(false);
    this.router.navigate(['/login']);
  }

  getUserAvatarUrl(): string {
    const avatarUrl = this.currentUser()?.avatar_url || '';
    return avatarUrl.startsWith('/default-avatars/') || avatarUrl.startsWith('https://') || avatarUrl.startsWith('http://')
      ? avatarUrl
      : this.fallbackAvatarUrl;
  }

  toggleTheme(): void {
    this.themeService.toggleTheme();
  }

  toggleNotifications(): void {
    const willOpen = !this.isNotificationsOpen();
    this.isNotificationsOpen.set(willOpen);
    if (willOpen) {
      this.loadPendingInvites();
      this.loadNotifications();
    }
  }

  loadNotifications(): void {
    if (!this.isAuthenticated()) return;
    this.p1Service.listNotifications().subscribe({
      next: response => {
        this.notifications.set((response.data?.items || []).filter(item => item.type !== 'trip_invite'));
        this.unreadNotificationCount.set(response.data?.unread_count || 0);
      },
      error: () => this.notificationError.set('Không thể tải trung tâm thông báo.'),
    });
  }

  openNotification(item: UserNotification): void {
    const navigate = () => item.action_url && this.router.navigateByUrl(item.action_url);
    if (item.read_at) { navigate(); return; }
    this.p1Service.readNotification(item.id).subscribe({
      next: () => {
        this.notifications.update(items => items.map(value => value.id === item.id ? { ...value, read_at: new Date().toISOString() } : value));
        this.unreadNotificationCount.update(count => Math.max(0, count - 1));
        navigate();
      },
    });
  }

  markAllNotificationsRead(): void {
    this.p1Service.readAllNotifications().subscribe({ next: () => {
      const now = new Date().toISOString();
      this.notifications.update(items => items.map(item => ({ ...item, read_at: item.read_at || now })));
      this.unreadNotificationCount.set(0);
    }});
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
      next: (res) => {
        this.pendingInvites.set(this.pendingInvites().filter((item) => item.id !== invite.id));
        this.inviteActionId.set(null);
        this.isNotificationsOpen.set(false);
        const tripId = res?.data?.trip_id;
        if (tripId) {
          this.router.navigate(['/trip', tripId]);
        } else {
          this.router.navigate(['/dashboard'], { queryParams: { tab: 'my-trips' } });
        }
      },
      error: (err) => {
        this.notificationError.set(err?.error?.message || 'Không thể chấp nhận lời mời.');
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
