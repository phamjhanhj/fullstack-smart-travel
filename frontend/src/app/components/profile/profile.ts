import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService, UserInfo } from '../../services/auth.service';
import { UserService, UserPreferences, UserProfileResponse } from '../../services/user.service';

interface InterestItem {
  id: string;
  name: string;
  emoji: string;
}

interface DefaultAvatar {
  id: string;
  name: string;
  url: string;
}

@Component({
  selector: 'app-user-profile',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './profile.html',
  styleUrl: './profile.css',
})
export class UserProfileComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly userService = inject(UserService);
  private readonly router = inject(Router);

  // States
  readonly profile = signal<UserProfileResponse | null>(null);
  readonly isLoading = signal<boolean>(true);
  readonly isSaving = signal<boolean>(false);
  readonly successMessage = signal<string | null>(null);
  readonly errorMessage = signal<string | null>(null);
  readonly selectedAvatar = signal<string>('');

  // Selected interests list (signal)
  readonly selectedInterests = signal<string[]>([]);

  // List of interests with icons
  readonly availableInterests: InterestItem[] = [
    { id: 'history', name: 'Lịch sử', emoji: '🏛️' },
    { id: 'culture', name: 'Văn hóa & Nghệ thuật', emoji: '🎨' },
    { id: 'nature', name: 'Thiên nhiên', emoji: '🏔️' },
    { id: 'adventure', name: 'Phiêu lưu', emoji: '🧗' },
    { id: 'foodie', name: 'Ẩm thực', emoji: '🍜' },
    { id: 'shopping', name: 'Mua sắm', emoji: '🛍️' },
    { id: 'nightlife', name: 'Hoạt động ban đêm', emoji: '🍺' },
    { id: 'beaches', name: 'Nghỉ dưỡng biển', emoji: '🏖️' },
    { id: 'cafe', name: 'Cà phê & Thư giãn', emoji: '☕' },
  ];

  // Default premium avatars
  readonly defaultAvatars: DefaultAvatar[] = [
    { id: 'avatar1', name: 'Khám phá', url: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&w=150&h=150&q=80' },
    { id: 'avatar2', name: 'Năng động', url: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=150&h=150&q=80' },
    { id: 'avatar3', name: 'Trí thức', url: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=150&h=150&q=80' },
    { id: 'avatar4', name: 'Thanh lịch', url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=150&h=150&q=80' },
    { id: 'avatar5', name: 'Thân thiện', url: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=150&h=150&q=80' },
    { id: 'avatar6', name: 'Nhẹ nhàng', url: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=150&h=150&q=80' },
  ];

  // Profile Form group
  readonly profileForm = this.fb.nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
    avatar_url: [''],
    travel_style: ['mid-range' as 'budget' | 'mid-range' | 'luxury' | null],
    budget_range: ['medium' as 'low' | 'medium' | 'high' | null],
  });

  ngOnInit(): void {
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }
    this.loadProfile();
  }

  loadProfile(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.userService.getUserProfile().subscribe({
      next: (res) => {
        this.isLoading.set(false);
        if (res && res.data) {
          const u = res.data;
          this.profile.set(u);
          
          // Patch values into form
          this.profileForm.patchValue({
            full_name: u.full_name,
            avatar_url: u.avatar_url || '',
            travel_style: u.preferences_json?.travel_style || 'mid-range',
            budget_range: u.preferences_json?.budget_range || 'medium',
          });

          this.selectedAvatar.set(u.avatar_url || '');
          this.selectedInterests.set(u.preferences_json?.interests || []);
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        this.errorMessage.set('Không thể tải thông tin hồ sơ của bạn.');
      },
    });
  }

  selectAvatar(url: string): void {
    this.selectedAvatar.set(url);
    this.profileForm.patchValue({ avatar_url: url });
  }

  toggleInterest(interestId: string): void {
    const current = this.selectedInterests();
    if (current.includes(interestId)) {
      this.selectedInterests.set(current.filter((i) => i !== interestId));
    } else {
      this.selectedInterests.set([...current, interestId]);
    }
  }

  isInterestSelected(interestId: string): boolean {
    return this.selectedInterests().includes(interestId);
  }

  getInterestEmojiAndName(interestId: string): string {
    const found = this.availableInterests.find((i) => i.id === interestId);
    return found ? `${found.emoji} ${found.name}` : interestId;
  }

  getTravelStyleName(style: string | null | undefined): string {
    switch (style) {
      case 'budget': return 'Tiết kiệm';
      case 'luxury': return 'Sang chảnh';
      default: return 'Tự túc';
    }
  }

  onSubmit(): void {
    if (this.profileForm.invalid) return;

    this.isSaving.set(true);
    this.successMessage.set(null);
    this.errorMessage.set(null);

    const formVal = this.profileForm.getRawValue();

    const preferences_json: UserPreferences = {
      travel_style: formVal.travel_style,
      budget_range: formVal.budget_range,
      interests: this.selectedInterests(),
    };

    const payload = {
      full_name: formVal.full_name,
      avatar_url: formVal.avatar_url || null,
      preferences_json,
    };

    this.userService.updateUserProfile(payload).subscribe({
      next: (res) => {
        this.isSaving.set(false);
        if (res && res.data) {
          const updated = res.data;
          this.profile.set(updated);
          this.successMessage.set('Đã cập nhật hồ sơ thành công!');
          
          // Sync changes to AuthService and local storage cache
          const cachedUser: UserInfo = {
            id: updated.id,
            email: updated.email,
            full_name: updated.full_name,
            avatar_url: updated.avatar_url,
          };
          this.authService.currentUser.set(cachedUser);
          localStorage.setItem('user_info', JSON.stringify(cachedUser));

          // Hide success message after 3 seconds
          setTimeout(() => this.successMessage.set(null), 3000);
        }
      },
      error: (err) => {
        this.isSaving.set(false);
        this.errorMessage.set(err?.error?.message || 'Có lỗi xảy ra khi cập nhật hồ sơ.');
      },
    });
  }

  onReset(): void {
    this.loadProfile();
  }

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }
}
