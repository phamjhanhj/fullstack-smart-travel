import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  readonly isDarkMode = signal<boolean>(true);

  constructor() {
    // Load initial theme from localStorage or fallback to dark
    const savedTheme = localStorage.getItem('theme') || 'dark';
    this.isDarkMode.set(savedTheme === 'dark');
    this.applyTheme(savedTheme);
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
