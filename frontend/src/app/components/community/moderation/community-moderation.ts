import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterModule } from '@angular/router';
import {
  CommunityReport,
  PublicTripService,
} from '../../../services/public-trip.service';

type ReportStatus = 'open' | 'upheld' | 'dismissed';

@Component({
  selector: 'app-community-moderation',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <main class="min-h-screen px-4 md:px-12 py-8 text-on-surface max-w-6xl mx-auto space-y-8">
      <!-- Header Section -->
      <header class="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-surface-container/40 p-6 sm:p-8 rounded-3xl border border-glass backdrop-blur-xl shadow-xl">
        <div class="space-y-2">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-bold uppercase tracking-wider">
            <span class="material-symbols-outlined text-sm">shield_person</span>
            <span>Bảng Quản Trị System</span>
          </div>
          <h1 class="text-3xl sm:text-4xl font-black font-headline-md tracking-tight m-0">Kiểm duyệt cộng đồng</h1>
          <p class="text-sm text-on-surface-variant m-0 max-w-xl">
            Xem xét các báo cáo vi phạm nội dung, chuyến đi công khai và quản lý tiêu chuẩn cộng đồng.
          </p>
        </div>

        <!-- Filter Status Buttons -->
        <div class="flex flex-wrap gap-2.5 shrink-0" aria-label="Lọc báo cáo theo trạng thái">
          <button
            *ngFor="let value of statuses"
            type="button"
            (click)="load(value)"
            [attr.aria-pressed]="status() === value"
            [ngClass]="
              status() === value
                ? 'bg-primary text-on-primary shadow-lg shadow-primary/25 border-primary font-bold'
                : 'bg-surface-container-low/80 hover:bg-surface-container border-glass text-on-surface-variant hover:text-on-surface font-semibold'
            "
            class="px-5 py-2.5 rounded-xl border text-sm transition-all cursor-pointer flex items-center gap-2"
          >
            <span class="material-symbols-outlined text-[18px]">
              {{ value === 'open' ? 'pending_actions' : value === 'upheld' ? 'gavel' : 'task_alt' }}
            </span>
            <span>{{ statusLabel(value) }}</span>
          </button>
        </div>
      </header>

      <!-- Loading State -->
      <div *ngIf="loading()" class="glass-card rounded-3xl p-12 text-center text-on-surface-variant space-y-3 border border-glass">
        <span class="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
        <p class="font-bold text-sm">Đang tải danh sách báo cáo...</p>
      </div>

      <!-- Error State -->
      <div
        *ngIf="error()"
        class="rounded-2xl border border-red-500/30 bg-red-500/10 text-red-300 p-5 flex items-center gap-3"
      >
        <span class="material-symbols-outlined text-2xl shrink-0">error</span>
        <span class="text-sm font-medium">{{ error() }}</span>
      </div>

      <!-- Empty State -->
      <div
        *ngIf="!loading() && !error() && reports().length === 0"
        class="glass-card rounded-3xl p-12 text-center text-on-surface-variant space-y-3 border border-glass"
      >
        <div class="w-14 h-14 rounded-2xl bg-white/5 border border-glass grid place-items-center mx-auto text-primary">
          <span class="material-symbols-outlined text-3xl">verified_user</span>
        </div>
        <p class="font-bold text-on-surface text-base m-0">Không có báo cáo nào trong nhóm này</p>
        <p class="text-xs text-on-surface-variant m-0">Tất cả nội dung đều tuân thủ tốt tiêu chuẩn cộng đồng.</p>
      </div>

      <!-- Reports List Section -->
      <section class="space-y-5" *ngIf="!loading() && reports().length > 0">
        <article
          *ngFor="let item of reports()"
          class="glass-card rounded-3xl border border-glass bg-surface-container/60 backdrop-blur-xl p-5 sm:p-6 space-y-5 hover:border-primary/30 transition-all shadow-xl"
        >
          <!-- Article Header -->
          <div class="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-glass/60">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-300 grid place-items-center shrink-0">
                <span class="material-symbols-outlined text-xl">report_problem</span>
              </div>
              <div>
                <h2 class="font-bold text-base text-on-surface m-0">
                  {{ item.publication_id ? 'Báo cáo chuyến đi' : 'Báo cáo hồ sơ công khai' }}
                </h2>
                <p class="text-xs text-on-surface-variant m-0 mt-0.5 flex items-center gap-2">
                  <span>{{ item.created_at | date:'dd/MM/yyyy HH:mm' }}</span>
                  <span>•</span>
                  <span class="text-amber-300 font-semibold">{{ reasonLabel(item.reason) }}</span>
                </p>
              </div>
            </div>
            <span
              [ngClass]="{
                'bg-amber-500/15 border-amber-500/30 text-amber-300': item.status === 'open',
                'bg-red-500/15 border-red-500/30 text-red-300': item.status === 'upheld',
                'bg-emerald-500/15 border-emerald-500/30 text-emerald-300': item.status === 'dismissed'
              }"
              class="text-xs font-bold px-3.5 py-1.5 rounded-full border flex items-center gap-1.5 shrink-0"
            >
              <span class="w-2 h-2 rounded-full" [ngClass]="{ 'bg-amber-400': item.status === 'open', 'bg-red-400': item.status === 'upheld', 'bg-emerald-400': item.status === 'dismissed' }"></span>
              <span>{{ statusLabel(item.status) }}</span>
            </span>
          </div>

          <!-- Target Card (No Cover Image as requested) -->
          <div *ngIf="item.target as target; else missingTarget" class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface-container-low/80 rounded-2xl p-4 border border-glass/60 hover:bg-surface-container transition-all">
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <div class="w-10 h-10 rounded-xl bg-white/5 border border-glass grid place-items-center shrink-0">
                <span class="material-symbols-outlined text-xl text-primary">
                  {{ target.type === 'trip' ? 'map' : 'person' }}
                </span>
              </div>
              <div class="min-w-0 flex-1 space-y-1">
                <p class="font-bold text-base text-on-surface break-words m-0">{{ target.title }}</p>
                <p *ngIf="target.destination" class="text-xs sm:text-sm text-on-surface-variant m-0 flex items-center gap-1.5">
                  <span class="material-symbols-outlined text-sm text-primary">location_on</span>
                  <span>{{ target.destination }}</span>
                  <span *ngIf="target.author_name">• Tác giả: <strong>{{ target.author_name }}</strong></span>
                </p>
                <p *ngIf="target.username" class="text-xs text-on-surface-variant m-0">
                  &#64;{{ target.username }}
                </p>
              </div>
            </div>
            <a
              *ngIf="item.publication_id"
              [routerLink]="['/community/trips', target.slug || target.id]"
              target="_blank"
              class="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-primary/10 border border-primary/30 hover:bg-primary/20 text-primary text-sm font-bold shrink-0 transition-all no-underline cursor-pointer"
            >
              <span class="material-symbols-outlined text-lg" aria-hidden="true">open_in_new</span>
              <span>Xem chi tiết chuyến đi</span>
            </a>
          </div>
          <ng-template #missingTarget>
            <div class="p-3 rounded-xl bg-white/5 border border-glass text-xs text-on-surface-variant">
              Đối tượng không còn tồn tại • Mã: {{ item.publication_id || item.reported_user_id }}
            </div>
          </ng-template>

          <!-- Report Details -->
          <div class="space-y-1.5">
            <p class="text-xs font-bold uppercase text-on-surface-variant tracking-wider m-0">Nội dung báo cáo</p>
            <div class="bg-surface-container-low/90 rounded-2xl p-4 text-sm text-on-surface border border-glass/50 leading-relaxed">
              {{ item.details || 'Không có mô tả bổ sung.' }}
            </div>
          </div>

          <!-- Actions Footer (Support Re-reviewing & Restoring) -->
          <div class="flex flex-wrap items-center gap-3 pt-2">
            <button
              *ngIf="item.status === 'open' || item.status === 'dismissed'"
              type="button"
              (click)="review(item, 'uphold')"
              [disabled]="reviewingReportId() === item.id"
              class="px-5 py-2.5 rounded-xl bg-red-500/15 hover:bg-red-500/25 border border-red-500/30 text-red-300 text-sm font-bold transition-all disabled:opacity-50 flex items-center gap-2 cursor-pointer"
            >
              <span class="material-symbols-outlined text-lg">block</span>
              <span>{{ item.status === 'dismissed' ? 'Khóa & Ẩn bài viết' : 'Xác nhận vi phạm và ẩn' }}</span>
            </button>
            <button
              *ngIf="item.status === 'open' || item.status === 'upheld'"
              type="button"
              (click)="review(item, 'dismiss')"
              [disabled]="reviewingReportId() === item.id"
              class="px-5 py-2.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 text-sm font-bold transition-all disabled:opacity-50 flex items-center gap-2 cursor-pointer"
            >
              <span class="material-symbols-outlined text-lg">visibility</span>
              <span>{{ item.status === 'upheld' ? 'Phục hồi & Hiển thị lại' : 'Bác bỏ báo cáo' }}</span>
            </button>
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
  readonly status = signal<ReportStatus>('open');
  readonly statuses: ReportStatus[] = ['open', 'upheld', 'dismissed'];
  readonly reviewingReportId = signal<string | null>(null);

  ngOnInit(): void {
    this.load('open');
  }

  load(status: ReportStatus): void {
    this.status.set(status);
    this.loading.set(true);
    this.error.set(null);
    this.service.listCommunityReports(status).subscribe({
      next: response => {
        this.reports.set(response.data || []);
        this.loading.set(false);
      },
      error: error => {
        this.loading.set(false);
        this.error.set(error?.error?.message || 'Bạn không có quyền kiểm duyệt cộng đồng.');
      },
    });
  }

  review(item: CommunityReport, decision: 'uphold' | 'dismiss'): void {
    this.error.set(null);
    this.reviewingReportId.set(item.id);
    this.service.reviewCommunityReport(item.id, decision).subscribe({
      next: () => {
        this.reviewingReportId.set(null);
        this.load(this.status());
      },
      error: error => {
        this.reviewingReportId.set(null);
        this.error.set(error?.error?.message || 'Không thể xử lý báo cáo.');
      },
    });
  }

  statusLabel(value: string): string {
    if (value === 'open') return 'Đang chờ';
    if (value === 'upheld') return 'Đã xác nhận';
    return 'Đã bác bỏ';
  }

  reasonLabel(value: string): string {
    const labels: Record<string, string> = {
      spam: 'Nội dung rác',
      misleading: 'Thông tin gây hiểu nhầm',
      unsafe: 'Nội dung không an toàn',
      harassment: 'Quấy rối',
      copyright: 'Vi phạm bản quyền',
      other: 'Lý do khác',
    };
    return labels[value] || value;
  }
}
