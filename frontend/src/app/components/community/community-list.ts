import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { PublicTripListItem, PublicTripService } from '../../services/public-trip.service';

@Component({
  selector: 'app-community-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './community-list.html',
  styleUrl: './community-list.css',
})
export class CommunityListComponent implements OnInit {
  private readonly publicTrips = inject(PublicTripService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  readonly items = signal<PublicTripListItem[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly view = signal<'explore' | 'saved' | 'recommended'>('explore');
  readonly recommendationReasons = signal<Record<string,string>>({});
  destination = '';
  sort = 'newest';

  readonly sortOptions = [
    { value: 'newest', label: 'Mới nhất' },
    { value: 'recommended', label: 'Đánh giá tốt' },
    { value: 'most_saved', label: 'Lưu nhiều nhất' },
    { value: 'lowest_cost', label: 'Chi phí thấp' },
  ];
  readonly isSortOpen = signal(false);

  @HostListener('document:click')
  closeSortDropdown(): void {
    this.isSortOpen.set(false);
  }

  toggleSortDropdown(event?: Event): void {
    if (event) event.stopPropagation();
    this.isSortOpen.update(v => !v);
  }

  selectSortOption(value: string): void {
    this.sort = value;
    this.isSortOpen.set(false);
    this.load();
  }

  getSortLabel(): string {
    const found = this.sortOptions.find(o => o.value === this.sort);
    return found ? found.label : 'Mới nhất';
  }

  ngOnInit(): void {
    if (this.route.snapshot.queryParamMap.get('view') === 'recommended') {
      if (!this.auth.isAuthenticated()) { this.router.navigate(['/login'], { queryParams: { returnUrl: '/community?view=recommended' } }); return; }
      this.view.set('recommended');
    }
    if (this.route.snapshot.queryParamMap.get('view') === 'saved') {
      if (!this.auth.isAuthenticated()) {
        this.router.navigate(['/login'], { queryParams: { returnUrl: '/community?view=saved' } });
        return;
      }
      this.view.set('saved');
    }
    this.load();
  }

  setView(view: 'explore' | 'saved' | 'recommended'): void {
    if (view !== 'explore' && !this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: '/community?view=saved' } });
      return;
    }
    this.view.set(view);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: view === 'saved' ? { view: 'saved' } : view === 'recommended' ? { view: 'recommended' } : { view: null },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    if (this.view() === 'recommended') {
      this.publicTrips.recommendations().subscribe({ next: response => { const rows=response.data||[]; this.items.set(rows.map(row=>row.publication)); this.recommendationReasons.set(Object.fromEntries(rows.map(row=>[row.publication.id,row.reason]))); this.loading.set(false); }, error:error=>{this.error.set(error?.error?.message||'Không thể tải gợi ý.');this.loading.set(false);} });
      return;
    }
    const request = this.view() === 'saved' ? this.publicTrips.listSaved(1, 50) : this.publicTrips.list({ destination: this.destination.trim(), sort: this.sort });
    request.subscribe({
      next: (response) => {
        this.items.set(response.data?.items || []);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error?.error?.message || 'Không thể tải lịch trình cộng đồng.');
        this.loading.set(false);
      },
    });
  }

  hideRecommendation(publicationId:string,event:Event):void { event.preventDefault();event.stopPropagation();this.publicTrips.hideRecommendation(publicationId).subscribe({next:()=>this.items.update(items=>items.filter(item=>item.id!==publicationId))}); }

  money(value: number | null): string {
    return value == null ? 'Chưa công khai' : `${new Intl.NumberFormat('vi-VN').format(value)} ₫/người`;
  }
}
