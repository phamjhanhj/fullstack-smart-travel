import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <main class="min-h-screen flex items-center justify-center bg-surface p-6">
      <section class="glass-card max-w-lg w-full rounded-3xl border border-glass p-8 text-center">
        <div *ngIf="isLoading()" class="space-y-4">
          <div class="w-10 h-10 mx-auto rounded-full border-4 border-primary/20 border-t-primary animate-spin"></div>
          <h1 class="text-xl font-bold">Đang xác minh email...</h1>
        </div>
        <div *ngIf="!isLoading() && isSuccess()" class="space-y-4">
          <span class="material-symbols-outlined text-5xl text-emerald-500">verified</span>
          <h1 class="text-2xl font-bold">Xác minh thành công</h1>
          <p class="text-on-surface-variant">Tài khoản của bạn đã sẵn sàng.</p>
          <a routerLink="/login" class="inline-block rounded-xl bg-primary px-6 py-3 text-white font-bold no-underline">Đăng nhập</a>
        </div>
        <div *ngIf="!isLoading() && !isSuccess()" class="space-y-4">
          <span class="material-symbols-outlined text-5xl text-rose-500">error</span>
          <h1 class="text-2xl font-bold">Không thể xác minh</h1>
          <p class="text-on-surface-variant">{{ errorMessage() }}</p>
          <a routerLink="/login" class="text-primary font-bold">Về trang đăng nhập</a>
        </div>
      </section>
    </main>
  `,
})
export class VerifyEmailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly authService = inject(AuthService);
  readonly isLoading = signal(true);
  readonly isSuccess = signal(false);
  readonly errorMessage = signal('Liên kết không hợp lệ hoặc đã hết hạn.');

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token') || '';
    if (!token) {
      this.isLoading.set(false);
      return;
    }
    this.authService.verifyEmail(token).subscribe({
      next: () => {
        this.isSuccess.set(true);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message || 'Liên kết không hợp lệ hoặc đã hết hạn.');
        this.isLoading.set(false);
      },
    });
  }
}
