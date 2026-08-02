import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { API_BASE_URL } from './config/api.config';
import { AuthService } from './services/auth.service';

describe('App', () => {
  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(),
        provideRouter([]),
        { provide: API_BASE_URL, useValue: '/api' },
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the router outlet', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });

  it('shows the moderation navigation only for administrators', () => {
    const fixture = TestBed.createComponent(App);
    const authService = TestBed.inject(AuthService);
    authService.currentUser.set({
      id: 'admin-1',
      username: 'admin',
      email: 'admin@example.com',
      full_name: 'Administrator',
      is_admin: true,
    });
    authService.isAuthenticated.set(true);

    fixture.detectChanges();

    const links = fixture.nativeElement.querySelectorAll(
      'a[routerLink="/community/moderation"]',
    );
    expect(links.length).toBeGreaterThan(0);
  });

  it('hides the moderation navigation from regular users', () => {
    const fixture = TestBed.createComponent(App);
    const authService = TestBed.inject(AuthService);
    authService.currentUser.set({
      id: 'user-1',
      username: 'traveler',
      email: 'traveler@example.com',
      full_name: 'Traveler',
      is_admin: false,
    });
    authService.isAuthenticated.set(true);

    fixture.detectChanges();

    const links = fixture.nativeElement.querySelectorAll(
      'a[routerLink="/community/moderation"]',
    );
    expect(links.length).toBe(0);
  });
});
