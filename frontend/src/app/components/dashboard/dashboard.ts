declare const L: any;

import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, FormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { TripService, TripListItem, CreateTripRequest } from '../../services/trip.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class DashboardComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly tripService = inject(TripService);
  private readonly router = inject(Router);

  // Leaflet Map properties
  private dashboardMap: any = null;
  private mapMarkers: any[] = [];

  // User Info signal link
  readonly currentUser = this.authService.currentUser;

  // State signals
  readonly trips = signal<TripListItem[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly isSubmitting = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);
  readonly filterStatus = signal<string>('all');
  readonly isModalOpen = signal<boolean>(false);
  readonly modalErrorMessage = signal<string | null>(null);

  // Airbnb Hub State
  readonly activeTab = signal<string>('trips'); // 'trips' or 'map'
  readonly selectedCategory = signal<string>('all');
  
  // A local database of coordinates for popular destinations
  readonly destinationCoordinates: { [key: string]: [number, number] } = {
    'phú quốc': [10.2181, 103.9607],
    'phu quoc': [10.2181, 103.9607],
    'đà nẵng': [16.0471, 108.2068],
    'da nang': [16.0471, 108.2068],
    'sapa': [22.3364, 103.8438],
    'hà giang': [22.8233, 104.9836],
    'ha giang': [22.8233, 104.9836],
    'hà nội': [21.0285, 105.8542],
    'hanoi': [21.0285, 105.8542],
    'hội an': [15.8801, 108.3380],
    'hoi an': [15.8801, 108.3380],
    'đà lạt': [11.9404, 108.4583],
    'da lat': [11.9404, 108.4583],
    'tokyo': [35.6762, 139.6503],
    'bali': [-8.4095, 115.1889],
    'hồ chí minh': [10.8231, 106.6297],
    'ho chi minh': [10.8231, 106.6297],
    'nha trang': [12.2388, 109.1967],
    'huế': [16.4637, 107.5909],
    'hue': [16.4637, 107.5909],
    'sài gòn': [10.8231, 106.6297],
    'sai gon': [10.8231, 106.6297],
    'bình thuận': [10.9333, 108.1000],
    'vũng tàu': [10.3460, 107.0843],
    'vung tau': [10.3460, 107.0843],
    'hạ long': [20.9501, 107.0733],
    'ha long': [20.9501, 107.0733],
  };
  
  // Search inputs
  readonly searchDest = signal<string>('');
  readonly searchStart = signal<string>('');
  readonly searchEnd = signal<string>('');
  readonly searchGuests = signal<number>(1);

  readonly categories = [
    { id: 'all', name: 'Tất cả', icon: '🌎' },
    { id: 'beach', name: 'Bãi biển', icon: '🏖️' },
    { id: 'mountain', name: 'Núi non', icon: '🏔️' },
    { id: 'culture', name: 'Cổ kính', icon: '🏛️' },
    { id: 'city', name: 'Đô thị', icon: '🏙️' }
  ];

  readonly trendingDestinations = [
    {
      name: 'Phú Quốc',
      category: 'beach',
      description: 'Thiên đường đảo ngọc cát trắng mịn màng và hoàng hôn tuyệt đẹp.',
      image: 'https://images.unsplash.com/photo-1583212292454-1fe6229603b7?auto=format&fit=crop&w=600&q=80',
      budget: 6000000,
      days: 4,
      preferences: 'Nghỉ dưỡng resort ven biển, đi cáp treo Hòn Thơm, lặn ngắm san hô, thưởng thức hải sản và bún quậy.'
    },
    {
      name: 'Đà Nẵng',
      category: 'beach',
      description: 'Thành phố của những cây cầu rực rỡ và bãi biển Mỹ Khê trải dài.',
      image: 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80',
      budget: 4500000,
      days: 3,
      preferences: 'Tắm biển Mỹ Khê, check-in Cầu Vàng Bà Nà Hills, ăn bánh tráng cuốn thịt heo, mì Quảng thơm ngon.'
    },
    {
      name: 'Sapa',
      category: 'mountain',
      description: 'Thị trấn sương mù kỳ ảo bên những ruộng bậc thang vàng óng.',
      image: 'https://images.unsplash.com/photo-1509060464153-4466739f78d0?auto=format&fit=crop&w=600&q=80',
      budget: 3500000,
      days: 3,
      preferences: 'Chinh phục đỉnh Fansipan bằng cáp treo, leo núi Hàm Rồng, ghé thăm bản Cát Cát thanh bình, ăn lẩu cá hồi.'
    },
    {
      name: 'Hà Giang',
      category: 'mountain',
      description: 'Cao nguyên đá kỳ vĩ với đèo Mã Pí Lèng hiểm trở huyền thoại.',
      image: 'https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=600&q=80',
      budget: 4000000,
      days: 4,
      preferences: 'Khám phá đèo Mã Pí Lèng, chèo thuyền ngắm cảnh sông Nho Quế, check-in hoa tam giác mạch.'
    },
    {
      name: 'Hà Nội',
      category: 'culture',
      description: 'Hành trình nghìn năm văn hiến cổ kính đậm nét tinh hoa ẩm thực.',
      image: 'https://images.unsplash.com/photo-1509060464153-4466739f78d0?auto=format&fit=crop&w=600&q=80',
      budget: 3000000,
      days: 3,
      preferences: 'Dạo quanh Hồ Gươm, viếng lăng Bác, thưởng thức phở gánh cổ truyền, bún chả và cà phê trứng.'
    },
    {
      name: 'Hội An',
      category: 'culture',
      description: 'Phố cổ thơ mộng lung linh đèn lồng bên dòng sông Hoài hoài niệm.',
      image: 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80',
      budget: 3500000,
      days: 3,
      preferences: 'Đi dạo phố cổ về đêm, đi thuyền thả hoa đăng trên sông Hoài, thưởng thức bánh mì Phượng và cơm gà.'
    },
    {
      name: 'Đà Lạt',
      category: 'mountain',
      description: 'Thành phố tình yêu thơ mộng với không khí se lạnh dễ chịu quanh năm.',
      image: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=600&q=80',
      budget: 3800000,
      days: 3,
      preferences: 'Check-in hồ Xuân Hương, săn mây đồi chè Cầu Đất, ăn bánh tráng nướng, uống sữa đậu nành nóng.'
    },
    {
      name: 'Tokyo',
      category: 'city',
      description: 'Thành phố tương lai hòa quyện hoàn hảo nét văn hóa truyền thống Nhật Bản.',
      image: 'https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=600&q=80',
      budget: 25000000,
      days: 5,
      preferences: 'Tham quan ngã tư Shibuya đông đúc, đền Senso-ji cổ kính, tháp Tokyo, ăn sushi băng chuyền và ramen.'
    },
    {
      name: 'Bali',
      category: 'beach',
      description: 'Hòn đảo thiên đường nổi tiếng với ruộng bậc thang và đền thờ ven biển.',
      image: 'https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=600&q=80',
      budget: 15000000,
      days: 5,
      preferences: 'Tham quan đền Uluwatu bên bờ đá, ruộng bậc thang Tegallalang, chơi đu dây Bali Swing.'
    }
  ];

  // Create Trip Reactive Form
  readonly createForm = this.fb.nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    destination: ['', [Validators.required, Validators.maxLength(200)]],
    start_date: ['', [Validators.required]],
    end_date: ['', [Validators.required]],
    budget: [null as number | null, [Validators.min(0)]],
    num_travelers: [1, [Validators.required, Validators.min(1)]],
    preferences: [''],
  });

  ngOnInit(): void {
    // Redirect if not authenticated
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }
    this.fetchTrips();
  }

  fetchTrips(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.tripService.listTrips().subscribe({
      next: (res) => {
        this.isLoading.set(false);
        if (res && res.data && res.data.items) {
          this.trips.set(res.data.items);
          if (this.activeTab() === 'map') {
            this.initOrRefreshDashboardMap();
          }
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        if (err.error && err.error.message) {
          this.errorMessage.set(err.error.message);
        } else {
          this.errorMessage.set('Không thể tải danh sách chuyến đi. Vui lòng thử lại sau.');
        }
      },
    });
  }

  getFilteredTrips(): TripListItem[] {
    const currentFilter = this.filterStatus();
    let allTrips = this.trips();
    
    if (currentFilter !== 'all') {
      allTrips = allTrips.filter((trip) => trip.status === currentFilter);
    }

    const query = this.searchDest().toLowerCase().trim();
    if (query) {
      allTrips = allTrips.filter((trip) => 
        trip.destination.toLowerCase().includes(query) ||
        trip.title.toLowerCase().includes(query)
      );
    }

    return allTrips;
  }

  getFilteredTrending() {
    const cat = this.selectedCategory();
    if (cat === 'all') {
      return this.trendingDestinations;
    }
    return this.trendingDestinations.filter(d => d.category === cat);
  }

  selectCategory(catId: string): void {
    this.selectedCategory.set(catId);
  }

  getFutureDateString(daysOffset: number): string {
    const d = new Date();
    d.setDate(d.getDate() + daysOffset);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  planTrending(dest: any): void {
    const startDate = this.getFutureDateString(1);
    const endDate = this.getFutureDateString(1 + dest.days);

    this.createForm.reset({
      title: `Khám phá ${dest.name} cùng AI`,
      destination: dest.name,
      start_date: startDate,
      end_date: endDate,
      budget: dest.budget,
      num_travelers: 2,
      preferences: dest.preferences
    });

    this.modalErrorMessage.set(null);
    this.isModalOpen.set(true);
  }

  onSearch(): void {
    const dest = this.searchDest().trim();
    if (dest) {
      const startDate = this.searchStart() || this.getFutureDateString(1);
      const endDate = this.searchEnd() || this.getFutureDateString(4);
      const guests = this.searchGuests() || 2;

      const match = this.trendingDestinations.find(t => t.name.toLowerCase() === dest.toLowerCase());

      this.createForm.reset({
        title: `Hành trình khám phá ${dest}`,
        destination: dest,
        start_date: startDate,
        end_date: endDate,
        budget: match ? match.budget : null,
        num_travelers: guests,
        preferences: match ? match.preferences : ''
      });
      this.modalErrorMessage.set(null);
      this.isModalOpen.set(true);
    } else {
      this.openModal();
    }
  }

  onFilterChange(status: string): void {
    this.filterStatus.set(status);
  }

  openModal(): void {
    this.createForm.reset({
      title: '',
      destination: '',
      start_date: '',
      end_date: '',
      budget: null,
      num_travelers: 1,
      preferences: '',
    });
    this.modalErrorMessage.set(null);
    this.isModalOpen.set(true);
  }

  closeModal(): void {
    this.isModalOpen.set(false);
  }

  onSubmitTrip(): void {
    if (this.createForm.invalid) {
      this.createForm.markAllAsTouched();
      return;
    }

    const start = new Date(this.createForm.value.start_date || '');
    const end = new Date(this.createForm.value.end_date || '');
    if (end < start) {
      this.modalErrorMessage.set('Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.');
      return;
    }

    this.isSubmitting.set(true);
    this.modalErrorMessage.set(null);

    const formValue = this.createForm.getRawValue();
    const payload: CreateTripRequest = {
      title: formValue.title,
      destination: formValue.destination,
      start_date: formValue.start_date,
      end_date: formValue.end_date,
      budget: formValue.budget,
      num_travelers: formValue.num_travelers,
      preferences: formValue.preferences || null,
    };

    this.tripService.createTrip(payload).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.closeModal();
        this.fetchTrips(); // Refresh trip list
      },
      error: (err) => {
        this.isSubmitting.set(false);
        if (err.error && err.error.message) {
          this.modalErrorMessage.set(err.error.message);
        } else {
          this.modalErrorMessage.set('Không thể tạo chuyến đi. Vui lòng thử lại sau.');
        }
      },
    });
  }

  onLogout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.createForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  // Helper to return beautiful visual covers matching Airbnb photo-first rule
  getTripImage(destination: string): string {
    const dest = destination.toLowerCase().trim();
    if (dest.includes('bali')) {
      return 'https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('tokyo') || dest.includes('nhật')) {
      return 'https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('paris') || dest.includes('pháp')) {
      return 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('hà nội') || dest.includes('hanoi')) {
      return 'https://images.unsplash.com/photo-1509060464153-4466739f78d0?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('đà nẵng') || dest.includes('da nang')) {
      return 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('phú quốc') || dest.includes('phu quoc')) {
      return 'https://images.unsplash.com/photo-1583212292454-1fe6229603b7?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('london') || dest.includes('anh')) {
      return 'https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=600&q=80';
    }
    // Default beautiful travel scenery
    return 'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=600&q=80';
  }

  // Format currency for budgets helper
  formatCurrency(value: number | null): string {
    if (value === null || value === undefined) return 'N/A';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(value);
  }

  goToTrip(tripId: string): void {
    this.router.navigate(['/trip', tripId]);
  }

  // --- Map Integration Helpers ---
  
  getCoordinatesForDestination(destination: string): [number, number] {
    const dest = destination.toLowerCase().trim();
    if (this.destinationCoordinates[dest]) {
      return this.destinationCoordinates[dest];
    }
    for (const key in this.destinationCoordinates) {
      if (dest.includes(key) || key.includes(dest)) {
        return this.destinationCoordinates[key];
      }
    }
    // Fallback to center of Vietnam with a slight random offset
    const lat = 16.0471 + (Math.random() - 0.5) * 4.0;
    const lng = 108.2068 + (Math.random() - 0.5) * 4.0;
    return [lat, lng];
  }

  setActiveTab(tab: string): void {
    this.activeTab.set(tab);
    if (tab === 'map') {
      setTimeout(() => {
        this.initOrRefreshDashboardMap();
      }, 100);
    }
  }

  initOrRefreshDashboardMap(): void {
    const container = document.getElementById('dashboard-map');
    if (!container) return;

    if (!this.dashboardMap) {
      const centerCoords: [number, number] = [16.0471, 108.2068]; // Center of Vietnam (Da Nang)
      this.dashboardMap = L.map('dashboard-map').setView(centerCoords, 6);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
      }).addTo(this.dashboardMap);
    }

    setTimeout(() => {
      if (this.dashboardMap) {
        this.dashboardMap.invalidateSize();
        this.renderDashboardMapMarkers();
      }
    }, 250);
  }

  renderDashboardMapMarkers(): void {
    if (!this.dashboardMap) return;

    // Clear old markers
    this.mapMarkers.forEach(m => m.remove());
    this.mapMarkers = [];

    const trips = this.getFilteredTrips();
    const validCoords: any[] = [];

    trips.forEach(trip => {
      const coords = this.getCoordinatesForDestination(trip.destination);
      validCoords.push(coords);

      const statusEmoji = trip.status === 'draft' ? '📝' : trip.status === 'active' ? '🚗' : '✅';
      const html = `<div class="custom-map-pin" title="${trip.title}"><span class="pin-emoji">${statusEmoji}</span></div>`;
      
      const customIcon = L.divIcon({
        html: html,
        className: 'custom-leaflet-pin',
        iconSize: [36, 36],
        iconAnchor: [18, 36],
        popupAnchor: [0, -32]
      });

      const marker = L.marker(coords, { icon: customIcon }).addTo(this.dashboardMap);
      this.mapMarkers.push(marker);

      const coverImg = this.getTripImage(trip.destination);
      const formattedBudget = this.formatCurrency(trip.budget);
      const statusText = trip.status === 'draft' ? 'Nháp' : trip.status === 'active' ? 'Đang đi' : 'Đã xong';
      const statusClass = trip.status;

      const popupContent = document.createElement('div');
      popupContent.className = 'map-popup-card';
      popupContent.style.width = '200px';
      popupContent.innerHTML = `
        <img src="${coverImg}" style="width: 100%; height: 90px; object-fit: cover; border-radius: 8px; margin-bottom: 8px;" />
        <div style="font-weight: 700; font-size: 13px; margin-bottom: 2px; color: #222222; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${trip.title}</div>
        <div style="font-size: 11px; color: #6a6a6a; margin-bottom: 4px;">📍 ${trip.destination}</div>
        <div style="font-size: 11px; color: #717171; margin-bottom: 6px;">📅 ${new Date(trip.start_date).toLocaleDateString('vi-VN')}</div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span class="status-badge ${statusClass}" style="position: static; font-size: 9px; padding: 2px 6px; box-shadow: none; border-radius: 9999px; text-transform: uppercase;">${statusText}</span>
          <span style="font-size: 11px; font-weight: 700; color: #ff385c;">${formattedBudget}</span>
        </div>
        <button class="popup-btn-go" style="background-color: #ff385c; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer; width: 100%; text-align: center; box-sizing: border-box;">Xem chi tiết</button>
      `;

      const goBtn = popupContent.querySelector('.popup-btn-go');
      if (goBtn) {
        goBtn.addEventListener('click', () => {
          this.goToTrip(trip.id);
        });
      }

      marker.bindPopup(popupContent);
    });

    if (validCoords.length > 0) {
      this.dashboardMap.fitBounds(validCoords, { padding: [50, 50], maxZoom: 10 });
    }
  }
}
