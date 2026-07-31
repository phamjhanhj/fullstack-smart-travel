import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { PublicTripService, CommunityReport } from '../../../services/public-trip.service';

@Component({
  selector: 'app-community-moderation',
  standalone: true,
  imports: [CommonModule],
  template: `
    <main class="min-h-screen px-4 md:px-12 py-8 text-on-surface max-w-6xl mx-auto space-y-6">
      <header class="flex flex-wrap items-center justify-between gap-4">
        <div><h1 class="text-3xl font-black">Kiểm duyệt cộng đồng</h1><p class="text-sm text-on-surface-variant mt-1">Chỉ tài khoản quản trị được phép truy cập.</p></div>
        <div class="flex gap-2">
          <button *ngFor="let value of statuses" type="button" (click)="load(value)" [class.bg-primary]="status() === value" [class.text-white]="status() === value" class="px-4 py-2 rounded-xl border border-glass text-sm font-bold">{{ statusLabel(value) }}</button>
        </div>
      </header>
      <div *ngIf="loading()" class="glass-card rounded-3xl p-10 text-center">Đang tải báo cáo...</div>
      <div *ngIf="error()" class="rounded-2xl border border-red-500/30 bg-red-500/10 text-red-300 p-4">{{ error() }}</div>
      <div *ngIf="!loading() && !error() && reports().length === 0" class="glass-card rounded-3xl p-10 text-center text-on-surface-variant">Không có báo cáo trong nhóm này.</div>
      <section class="space-y-4">
        <article *ngFor="let item of reports()" class="glass-card rounded-3xl border border-glass p-5 space-y-4">
          <div class="flex flex-wrap justify-between gap-3"><div><h2 class="font-bold">{{ item.publication_id ? 'Báo cáo chuyến đi' : 'Báo cáo trang cá nhân' }}</h2><p class="text-xs text-on-surface-variant">{{ item.created_at | date:'dd/MM/yyyy HH:mm' }} · {{ item.reason }}</p></div><span class="text-xs font-bold px-3 py-1 rounded-full border border-primary/30 text-primary">{{ statusLabel(item.status) }}</span></div>
          <p class="bg-black/15 rounded-xl p-3 text-sm">{{ item.details || 'Không có mô tả bổ sung.' }}</p>
          <p class="text-xs text-on-surface-variant break-all">Đối tượng: {{ item.publication_id || item.reported_user_id }}</p>
          <div *ngIf="item.status === 'open'" class="flex gap-2">
            <button type="button" (click)="review(item, 'uphold')" class="px-4 py-2 rounded-xl bg-red-500/15 border border-red-500/30 text-red-300 text-sm font-bold">Xác nhận vi phạm & ẩn</button>
            <button type="button" (click)="review(item, 'dismiss')" class="px-4 py-2 rounded-xl bg-white/5 border border-glass text-sm font-bold">Bác bỏ báo cáo</button>
          </div>
        </article>
      </section>
    </main>
  `,
})
export class CommunityModerationComponent implements OnInit {
  private readonly service = inject(PublicTripService);
  readonly reports = signal<CommunityReport[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly status = signal<'open' | 'upheld' | 'dismissed'>('open');
  readonly statuses: Array<'open' | 'upheld' | 'dismissed'> = ['open', 'upheld', 'dismissed'];

  ngOnInit(): void { this.load('open'); }
  load(status: 'open' | 'upheld' | 'dismissed'): void {
    this.status.set(status); this.loading.set(true); this.error.set(null);
    this.service.listCommunityReports(status).subscribe({
      next: response => { this.reports.set(response.data || []); this.loading.set(false); },
      error: error => { this.loading.set(false); this.error.set(error?.error?.message || 'Bạn không có quyền kiểm duyệt cộng đồng.'); },
    });
  }
  review(item: CommunityReport, decision: 'uphold' | 'dismiss'): void {
    this.service.reviewCommunityReport(item.id, decision).subscribe({ next: () => this.load(this.status()), error: error => this.error.set(error?.error?.message || 'Không thể xử lý báo cáo.') });
  }
  statusLabel(value: string): string { return value === 'open' ? 'Đang chờ' : value === 'upheld' ? 'Đã xác nhận' : 'Đã bác bỏ'; }
}