import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './register.html',
  styleUrl: './register.css'
})
export class RegisterComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  // Form definition
  readonly registerForm = this.fb.nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(2)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]]
  });

  // State variables
  readonly isLoading = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);

  // Carousel and Password signals
  readonly currentSlide = signal<number>(0);
  readonly showPassword = signal<boolean>(false);
  readonly totalSlides = 2;
  private carouselInterval: any;

  ngOnInit(): void {
    // Auto transition slides every 8 seconds
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
    this.currentSlide.update(idx => (idx + 1) % this.totalSlides);
  }

  prevSlide(): void {
    this.currentSlide.update(idx => (idx - 1 + this.totalSlides) % this.totalSlides);
  }

  togglePassword(): void {
    this.showPassword.update(show => !show);
  }

  onSubmit(): void {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    const { full_name, email, password } = this.registerForm.getRawValue();

    this.authService.register(email, password, full_name).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        this.successMessage.set('Đăng ký tài khoản thành công! Đang chuyển hướng đến trang đăng nhập...');
        this.registerForm.disable();
        setTimeout(() => {
          this.router.navigate(['/login']);
        }, 2000);
      },
      error: (err) => {
        this.isLoading.set(false);
        if (err.error && err.error.message) {
          this.errorMessage.set(err.error.message);
        } else {
          this.errorMessage.set('Đăng ký thất bại. Email có thể đã tồn tại hoặc có lỗi xảy ra.');
        }
      }
    });
  }

  isFieldInvalid(fieldName: 'full_name' | 'email' | 'password'): boolean {
    const field = this.registerForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }
}
