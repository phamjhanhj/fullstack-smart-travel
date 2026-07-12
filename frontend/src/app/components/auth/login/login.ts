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

  private readonly strictEmailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  readonly loginForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email, Validators.pattern(this.strictEmailPattern)]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  readonly isLoading = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);

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

    const { email, password } = this.loginForm.getRawValue();

    this.authService.login(email, password).subscribe({
      next: () => {
        this.isLoading.set(false);
        this.router.navigate(['/dashboard'], { queryParams: { tab: 'explore' } });
      },
      error: (err) => {
        this.isLoading.set(false);
        this.errorMessage.set(this.getApiErrorMessage(err));
      },
    });
  }

  isFieldInvalid(fieldName: 'email' | 'password'): boolean {
    const field = this.loginForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  getFieldError(fieldName: 'email' | 'password'): string {
    const field = this.loginForm.get(fieldName);
    if (!field || !field.errors) return '';

    if (field.errors['required']) {
      return fieldName === 'email' ? 'Vui lòng nhập email.' : 'Vui lòng nhập mật khẩu.';
    }
    if (fieldName === 'email' && (field.errors['email'] || field.errors['pattern'])) {
      return 'Email chưa hợp lệ. Ví dụ đúng: ten@gmail.com.';
    }
    if (fieldName === 'password' && field.errors['minlength']) {
      return 'Mật khẩu phải có ít nhất 6 ký tự.';
    }
    return 'Thông tin chưa hợp lệ.';
  }

  private normalizeFormValues(): void {
    const value = this.loginForm.getRawValue();
    this.loginForm.patchValue(
      { email: value.email.trim().toLowerCase() },
      { emitEvent: false },
    );
  }

  private getFirstValidationMessage(): string {
    if (this.loginForm.get('email')?.invalid) return this.getFieldError('email');
    if (this.loginForm.get('password')?.invalid) return this.getFieldError('password');
    return 'Vui lòng kiểm tra lại email và mật khẩu.';
  }

  private getApiErrorMessage(err: any): string {
    const message = err?.error?.message;
    const details = err?.error?.data?.detail || err?.error?.detail;

    if (Array.isArray(details)) {
      const fields = details.map((item: any) => String(item?.loc?.[item.loc.length - 1] || '')).join(' ');
      if (fields.includes('email')) return 'Email chưa hợp lệ. Vui lòng nhập đúng dạng ten@gmail.com.';
      if (fields.includes('password')) return 'Vui lòng nhập mật khẩu.';
    }

    if (message === 'Email hoac mat khau khong dung') return 'Email hoặc mật khẩu không đúng.';
    if (message === 'Email khong hop le') return 'Email chưa hợp lệ. Vui lòng nhập đúng dạng ten@gmail.com.';
    if (message && message !== 'Validation error') return message;
    return 'Đăng nhập thất bại. Vui lòng kiểm tra lại email và mật khẩu.';
  }
}
