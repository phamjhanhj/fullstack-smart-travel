import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const guestGuard: CanActivateFn = () => {
  const router = inject(Router);
  const authService = inject(AuthService);

  return authService
    .whenReady()
    .then(() => (authService.isAuthenticated() ? router.createUrlTree(['/dashboard']) : true));
};
