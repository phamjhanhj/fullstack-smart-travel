import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { ThemeService } from '../../../services/theme.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './register.html',
  styleUrl: './register.css',
})
export class RegisterComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  readonly themeService = inject(ThemeService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  private readonly strictEmailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  readonly registerForm = this.fb.nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
    email: ['', [Validators.required, Validators.email, Validators.pattern(this.strictEmailPattern)]],
    password: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(128)]],
  });

  readonly isLoading = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);

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
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      this.errorMessage.set(this.getFirstValidationMessage());
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    const { full_name, email, password } = this.registerForm.getRawValue();

    this.authService.register(email, password, full_name).subscribe({
      next: () => {
        this.isLoading.set(false);
        this.successMessage.set('Đăng ký tài khoản thành công! Đang chuyển hướng đến trang đăng nhập...');
        this.registerForm.disable();
        setTimeout(() => {
          this.router.navigate(['/login']);
        }, 2000);
      },
      error: (err) => {
        this.isLoading.set(false);
        this.errorMessage.set(this.getApiErrorMessage(err));
      },
    });
  }

  isFieldInvalid(fieldName: 'full_name' | 'email' | 'password'): boolean {
    const field = this.registerForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  getFieldError(fieldName: 'full_name' | 'email' | 'password'): string {
    const field = this.registerForm.get(fieldName);
    if (!field || !field.errors) return '';

    if (field.errors['required']) {
      if (fieldName === 'full_name') return 'Vui lòng nhập họ và tên.';
      if (fieldName === 'email') return 'Vui lòng nhập email.';
      return 'Vui lòng nhập mật khẩu.';
    }

    if (fieldName === 'full_name') {
      if (field.errors['minlength']) return 'Họ và tên phải có ít nhất 2 ký tự.';
      if (field.errors['maxlength']) return 'Họ và tên không được vượt quá 100 ký tự.';
    }

    if (fieldName === 'email' && (field.errors['email'] || field.errors['pattern'])) {
      return 'Email chưa hợp lệ. Ví dụ đúng: ten@gmail.com.';
    }

    if (fieldName === 'password') {
      if (field.errors['minlength']) return 'Mật khẩu phải có ít nhất 6 ký tự.';
      if (field.errors['maxlength']) return 'Mật khẩu không được vượt quá 128 ký tự.';
    }

    return 'Thông tin chưa hợp lệ.';
  }

  private normalizeFormValues(): void {
    const value = this.registerForm.getRawValue();
    this.registerForm.patchValue(
      {
        full_name: value.full_name.trim().replace(/\s+/g, ' '),
        email: value.email.trim().toLowerCase(),
      },
      { emitEvent: false },
    );
  }

  private getFirstValidationMessage(): string {
    if (this.registerForm.get('full_name')?.invalid) return this.getFieldError('full_name');
    if (this.registerForm.get('email')?.invalid) return this.getFieldError('email');
    if (this.registerForm.get('password')?.invalid) return this.getFieldError('password');
    return 'Vui lòng kiểm tra lại thông tin đăng ký.';
  }

  private getApiErrorMessage(err: any): string {
    const message = err?.error?.message;
    const details = err?.error?.data?.detail || err?.error?.detail;

    if (Array.isArray(details)) {
      const fields = details.map((item: any) => String(item?.loc?.[item.loc.length - 1] || '')).join(' ');
      if (fields.includes('email')) return 'Email chưa hợp lệ. Vui lòng nhập đúng dạng ten@gmail.com.';
      if (fields.includes('password')) return 'Mật khẩu phải có từ 6 đến 128 ký tự.';
      if (fields.includes('full_name')) return 'Họ và tên phải có từ 2 đến 100 ký tự.';
    }

    if (message === 'Email da duoc su dung') return 'Email này đã được sử dụng.';
    if (message === 'Email khong hop le') return 'Email chưa hợp lệ. Vui lòng nhập đúng dạng ten@gmail.com.';
    if (message && message !== 'Validation error') return message;
    return 'Đăng ký thất bại. Vui lòng kiểm tra lại họ tên, email và mật khẩu.';
  }
}
