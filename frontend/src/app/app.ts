import { Component, inject, signal } from '@angular/core';
import { RouterOutlet, Router, RouterLink, NavigationEnd } from '@angular/router';
import { AuthService } from './services/auth.service';
import { CommonModule } from '@angular/common';
import { filter } from 'rxjs';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  private readonly router = inject(Router);
  private readonly authService = inject(AuthService);

  readonly isAuthenticated = this.authService.isAuthenticated;
  readonly currentUser = this.authService.currentUser;

  currentUrl = signal<string>('');
  currentTab = signal<string>('');
  readonly isDarkMode = signal<boolean>(true);

  constructor() {
    // Load initial theme from localStorage
    const savedTheme = localStorage.getItem('theme') || 'dark';
    this.isDarkMode.set(savedTheme === 'dark');
    this.applyTheme(savedTheme);

    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      const url = event.urlAfterRedirects || event.url || '';
      this.currentUrl.set(url.split('?')[0]);
      
      const queryParams = new URLSearchParams(url.split('?')[1] || '');
      this.currentTab.set(queryParams.get('tab') || 'explore');
    });
  }

  isCurrentTab(tab: string): boolean {
    return this.currentUrl().includes('/dashboard') && this.currentTab() === tab;
  }

  isCurrentPath(path: string): boolean {
    return this.currentUrl() === path;
  }

  logout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  toggleTheme(): void {
    const nextTheme = this.isDarkMode() ? 'light' : 'dark';
    this.isDarkMode.set(nextTheme === 'dark');
    localStorage.setItem('theme', nextTheme);
    this.applyTheme(nextTheme);
  }

  private applyTheme(theme: string): void {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
  }
}
