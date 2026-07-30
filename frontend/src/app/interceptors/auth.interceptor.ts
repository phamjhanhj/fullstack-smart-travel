import { HttpClient, HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import {
  Observable,
  catchError,
  finalize,
  map,
  shareReplay,
  switchMap,
  tap,
  throwError,
} from 'rxjs';
import { API_BASE_URL } from '../config/api.config';
import { AuthService, type ResponseEnvelope } from '../services/auth.service';

interface RefreshData {
  access_token: string;
  refresh_token: string;
}

let refreshInFlight$: Observable<string> | null = null;

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const http = inject(HttpClient);
  const baseUrl = inject(API_BASE_URL);
  const authService = inject(AuthService);
  const token = localStorage.getItem('access_token');
  const isAuthEndpoint = /\/auth\/(login|register|refresh|logout)$/.test(req.url);

  const authReq =
    token && !isAuthEndpoint
      ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : req;

  return next(authReq).pipe(
    catchError((error: HttpErrorResponse) => {
      const refreshToken = localStorage.getItem('refresh_token');
      if (error.status !== 401 || isAuthEndpoint || !refreshToken) {
        if (error.status === 401) {
          authService.clearSession();
          void router.navigate(['/login']);
        }
        return throwError(() => error);
      }

      if (!refreshInFlight$) {
        refreshInFlight$ = http
          .post<ResponseEnvelope<RefreshData>>(`${baseUrl}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          .pipe(
            tap((response) => {
              localStorage.setItem('access_token', response.data.access_token);
              localStorage.setItem('refresh_token', response.data.refresh_token);
            }),
            map((response) => response.data.access_token),
            finalize(() => {
              refreshInFlight$ = null;
            }),
            shareReplay({ bufferSize: 1, refCount: false }),
          );
      }

      return refreshInFlight$.pipe(
        switchMap((newToken) =>
          next(req.clone({ setHeaders: { Authorization: `Bearer ${newToken}` } })),
        ),
        catchError((refreshError) => {
          authService.clearSession();
          void router.navigate(['/login']);
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
