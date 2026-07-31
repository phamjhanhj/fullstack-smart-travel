import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { TripService } from '../../services/trip.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-accept-invite',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="min-h-screen bg-bg-slate-deep flex items-center justify-center p-4">
      <div class="glass-card rounded-3xl p-8 max-w-md w-full text-center space-y-6 shadow-2xl border border-glass">
        <!-- Loading State -->
        <div *ngIf="isLoading()" class="space-y-4 py-6">
          <div class="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
          <h2 class="text-xl font-bold text-on-surface">Đang xử lý lời mời...</h2>
          <p class="text-sm text-on-surface-variant opacity-80">Vui lòng chờ trong giây lát.</p>
        </div>

        <!-- Success State -->
        <div *ngIf="successMessage()" class="space-y-4 py-4">
          <div class="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
            <span class="material-symbols-outlined text-3xl">check_circle</span>
          </div>
          <h2 class="text-xl font-bold text-on-surface">Thành công!</h2>
          <p class="text-sm text-emerald-400 font-medium">{{ successMessage() }}</p>
        </div>

        <!-- Error State -->
        <div *ngIf="errorMessage()" class="space-y-4 py-4">
          <div class="w-16 h-16 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center mx-auto">
            <span class="material-symbols-outlined text-3xl">error</span>
          </div>
          <h2 class="text-xl font-bold text-on-surface">Không thể tham gia</h2>
          <p class="text-sm text-rose-400 font-medium">{{ errorMessage() }}</p>
          <button
            type="button"
            routerLink="/dashboard"
            class="px-6 py-2.5 bg-primary text-on-primary font-bold text-sm rounded-full hover:brightness-110 transition-all cursor-pointer inline-flex items-center gap-2"
          >
            <span class="material-symbols-outlined text-base">dashboard</span>
            Về trang chủ
          </button>
        </div>
      </div>
    </div>
  `,
})
export class AcceptInviteComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly tripService = inject(TripService);
  private readonly authService = inject(AuthService);

  readonly isLoading = signal<boolean>(true);
  readonly successMessage = signal<string | null>(null);
  readonly errorMessage = signal<string | null>(null);

  ngOnInit(): void {
    if (!this.authService.isAuthenticated()) {
      const returnUrl = this.router.url;
      this.router.navigate(['/login'], { queryParams: { returnUrl } });
      return;
    }

    const token = this.route.snapshot.paramMap.get('token');
    if (!token) {
      this.isLoading.set(false);
      this.errorMessage.set('Mã lời mời không hợp lệ.');
      return;
    }

    this.tripService.acceptTripInvite(token).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        this.successMessage.set('Đã chấp nhận lời mời tham gia chuyến đi! Đang chuyển hướng...');
        const tripId = res?.data?.trip_id;
        setTimeout(() => {
          if (tripId) {
            this.router.navigate(['/trip', tripId]);
          } else {
            this.router.navigate(['/dashboard'], { queryParams: { tab: 'my-trips' } });
          }
        }, 1200);
      },
      error: (err) => {
        this.isLoading.set(false);
        this.errorMessage.set(err?.error?.message || 'Lời mời không hợp lệ hoặc đã hết hạn.');
      },
    });
  }
}
