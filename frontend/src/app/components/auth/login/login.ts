import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { ThemeService } from '../../../services/theme.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class LoginComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  readonly themeService = inject(ThemeService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  readonly loginForm = this.fb.nonNullable.group({
    login: ['', [Validators.required, Validators.maxLength(254)]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  readonly isLoading = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);
  readonly needsVerification = signal<boolean>(false);
  readonly resendMessage = signal<string | null>(null);

  readonly currentSlide = signal<number>(0);
  readonly showPassword = signal<boolean>(false);
  readonly totalSlides = 2;
  private carouselInterval: any;

  ngOnInit(): void {
    this.carouselInterval = setInterval(() => {
      this.nextSlide();
    }, 8000);
  }

  ngOnDestroy(): void {
    if (this.carouselInterval) {
      clearInterval(this.carouselInterval);
    }
  }

  nextSlide(): void {
    this.currentSlide.update((idx) => (idx + 1) % this.totalSlides);
  }

  prevSlide(): void {
    this.currentSlide.update((idx) => (idx - 1 + this.totalSlides) % this.totalSlides);
  }

  togglePassword(): void {
    this.showPassword.update((show) => !show);
  }

  onSubmit(): void {
    this.normalizeFormValues();
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      this.errorMessage.set(this.getFirstValidationMessage());
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.needsVerification.set(false);
    this.resendMessage.set(null);

    const { login, password } = this.loginForm.getRawValue();

    this.authService.login(login, password).subscribe({
      next: () => {
        this.isLoading.set(false);
        this.router.navigate(['/dashboard'], { queryParams: { tab: 'explore' } });
      },
      error: (err) => {
        this.isLoading.set(false);
        this.needsVerification.set(err?.error?.message === 'Email chua duoc xac minh');
        this.errorMessage.set(this.getApiErrorMessage(err));
      },
    });
  }

  resendVerification(): void {
    const login = this.loginForm.getRawValue().login.trim();
    if (!login) return;
    this.authService.resendVerification(login).subscribe({
      next: () => this.resendMessage.set('Đã gửi lại email xác minh. Vui lòng kiểm tra hộp thư.'),
      error: (err) => this.resendMessage.set(err?.error?.message || 'Không thể gửi lại email xác minh.'),
    });
  }

  isFieldInvalid(fieldName: 'login' | 'password'): boolean {
    const field = this.loginForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  getFieldError(fieldName: 'login' | 'password'): string {
    const field = this.loginForm.get(fieldName);
    if (!field || !field.errors) return '';

    if (field.errors['required']) {
      return fieldName === 'login' ? 'Vui lòng nhập tên đăng nhập hoặc email.' : 'Vui lòng nhập mật khẩu.';
    }
    if (fieldName === 'login' && field.errors['maxlength']) {
      return 'Tên đăng nhập hoặc email quá dài.';
    }
    if (fieldName === 'password' && field.errors['minlength']) {
      return 'Mật khẩu phải có ít nhất 6 ký tự.';
    }
    return 'Thông tin chưa hợp lệ.';
  }

  private normalizeFormValues(): void {
    const value = this.loginForm.getRawValue();
    this.loginForm.patchValue(
      { login: value.login.trim().toLowerCase() },
      { emitEvent: false },
    );
  }

  private getFirstValidationMessage(): string {
    if (this.loginForm.get('login')?.invalid) return this.getFieldError('login');
    if (this.loginForm.get('password')?.invalid) return this.getFieldError('password');
    return 'Vui lòng kiểm tra lại tên đăng nhập và mật khẩu.';
  }

  private getApiErrorMessage(err: any): string {
    const message = err?.error?.message;
    const details = err?.error?.data?.detail || err?.error?.detail;

    if (Array.isArray(details)) {
      const fields = details.map((item: any) => String(item?.loc?.[item.loc.length - 1] || '')).join(' ');
      if (fields.includes('login')) return 'Tên đăng nhập hoặc email chưa hợp lệ.';
      if (fields.includes('password')) return 'Vui lòng nhập mật khẩu.';
    }

    if (message === 'Ten dang nhap, email hoac mat khau khong dung') return 'Tên đăng nhập, email hoặc mật khẩu không đúng.';
    if (message === 'Email chua duoc xac minh') return 'Email chưa được xác minh.';
    if (message === 'Ten dang nhap khong hop le') return 'Tên đăng nhập chưa hợp lệ.';
    if (message && message !== 'Validation error') return message;
    return 'Đăng nhập thất bại. Vui lòng kiểm tra lại tên đăng nhập và mật khẩu.';
  }
}
