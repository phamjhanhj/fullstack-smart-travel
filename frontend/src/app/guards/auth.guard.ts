import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const router = inject(Router);
  const authService = inject(AuthService);

  return authService.whenReady().then(() =>
    authService.isAuthenticated()
      ? true
      : router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } }),
  );
};
