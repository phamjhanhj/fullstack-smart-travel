import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService, UserInfo } from '../../services/auth.service';
import { UserService, UserPreferences, UserProfileResponse } from '../../services/user.service';

interface InterestItem {
  id: string;
  name: string;
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

  readonly profile = signal<UserProfileResponse | null>(null);
  readonly isLoading = signal<boolean>(true);
  readonly isSaving = signal<boolean>(false);
  readonly successMessage = signal<string | null>(null);
  readonly errorMessage = signal<string | null>(null);
  readonly selectedAvatar = signal<string>('');
  readonly selectedInterests = signal<string[]>([]);

  readonly fallbackAvatarUrl = '/default-avatars/avatar-01.svg';

  readonly availableInterests: InterestItem[] = [
    { id: 'history', name: 'Lich su' },
    { id: 'culture', name: 'Van hoa & Nghe thuat' },
    { id: 'nature', name: 'Thien nhien' },
    { id: 'adventure', name: 'Phieu luu' },
    { id: 'foodie', name: 'Am thuc' },
    { id: 'shopping', name: 'Mua sam' },
    { id: 'nightlife', name: 'Hoat dong ban dem' },
    { id: 'beaches', name: 'Nghi duong bien' },
    { id: 'cafe', name: 'Ca phe & Thu gian' },
  ];

  readonly defaultAvatars: DefaultAvatar[] = [
    { id: 'avatar1', name: 'Mac dinh 1', url: '/default-avatars/avatar-01.svg' },
    { id: 'avatar2', name: 'Mac dinh 2', url: '/default-avatars/avatar-02.svg' },
    { id: 'avatar3', name: 'Mac dinh 3', url: '/default-avatars/avatar-03.svg' },
    { id: 'avatar4', name: 'Mac dinh 4', url: '/default-avatars/avatar-04.svg' },
    { id: 'avatar5', name: 'Mac dinh 5', url: '/default-avatars/avatar-05.svg' },
    { id: 'avatar6', name: 'Mac dinh 6', url: '/default-avatars/avatar-06.svg' },
    { id: 'avatar7', name: 'Mac dinh 7', url: '/default-avatars/avatar-07.svg' },
    { id: 'avatar8', name: 'Mac dinh 8', url: '/default-avatars/avatar-08.svg' },
  ];

  readonly profileForm = this.fb.nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
    avatar_url: [this.fallbackAvatarUrl],
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
        if (res?.data) {
          const u = res.data;
          const avatarUrl = this.isDefaultAvatar(u.avatar_url) ? u.avatar_url! : this.fallbackAvatarUrl;

          this.profile.set(u);
          this.profileForm.patchValue({
            full_name: u.full_name,
            avatar_url: avatarUrl,
            travel_style: u.preferences_json?.travel_style || 'mid-range',
            budget_range: u.preferences_json?.budget_range || 'medium',
          });

          this.selectedAvatar.set(avatarUrl);
          this.selectedInterests.set(u.preferences_json?.interests || []);
        }
      },
      error: () => {
        this.isLoading.set(false);
        this.errorMessage.set('Khong the tai thong tin ho so cua ban.');
      },
    });
  }

  selectAvatar(url: string): void {
    this.selectedAvatar.set(url);
    this.profileForm.patchValue({ avatar_url: url });
  }

  isDefaultAvatar(url: string | null | undefined): boolean {
    return !!url && this.defaultAvatars.some((avatar) => avatar.url === url);
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

  getInterestName(interestId: string): string {
    return this.availableInterests.find((i) => i.id === interestId)?.name || interestId;
  }

  getTravelStyleName(style: string | null | undefined): string {
    switch (style) {
      case 'budget':
        return 'Tiet kiem';
      case 'luxury':
        return 'Sang trong';
      default:
        return 'Tu tuc';
    }
  }

  onSubmit(): void {
    if (this.profileForm.invalid) return;

    this.isSaving.set(true);
    this.successMessage.set(null);
    this.errorMessage.set(null);

    const formVal = this.profileForm.getRawValue();
    const avatarUrl = this.isDefaultAvatar(formVal.avatar_url) ? formVal.avatar_url : this.fallbackAvatarUrl;

    const preferences_json: UserPreferences = {
      travel_style: formVal.travel_style,
      budget_range: formVal.budget_range,
      interests: this.selectedInterests(),
    };

    const payload = {
      full_name: formVal.full_name,
      avatar_url: avatarUrl,
      preferences_json,
    };

    this.userService.updateUserProfile(payload).subscribe({
      next: (res) => {
        this.isSaving.set(false);
        if (res?.data) {
          const updated = res.data;
          this.profile.set(updated);
          this.selectedAvatar.set(updated.avatar_url || this.fallbackAvatarUrl);
          this.successMessage.set('Da cap nhat ho so thanh cong!');

          const cachedUser: UserInfo = {
            id: updated.id,
            email: updated.email,
            full_name: updated.full_name,
            avatar_url: updated.avatar_url || this.fallbackAvatarUrl,
          };
          this.authService.currentUser.set(cachedUser);
          localStorage.setItem('user_info', JSON.stringify(cachedUser));

          setTimeout(() => this.successMessage.set(null), 3000);
        }
      },
      error: (err) => {
        this.isSaving.set(false);
        this.errorMessage.set(err?.error?.message || 'Co loi xay ra khi cap nhat ho so.');
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
