import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const adminGuard: CanActivateFn = (_route, state) => {
  const router = inject(Router);
  const authService = inject(AuthService);

  return authService.whenReady().then(() => {
    if (!authService.isAuthenticated()) {
      return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
    }
    return authService.isAdmin()
      ? true
      : router.createUrlTree(['/dashboard'], { queryParams: { accessDenied: 'admin' } });
  });
};
