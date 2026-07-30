import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

export interface DailyWeather {
  date: string; // YYYY-MM-DD
  weatherCode: number;
  weatherLabel: string;
  weatherIcon: string;
  tempMax: number;
  tempMin: number;
  precipProbMax: number;
}

export interface WeatherForecastResult {
  currentTemp?: number;
  daily: DailyWeather[];
}

@Injectable({
  providedIn: 'root',
})
export class WeatherService {
  private readonly http = inject(HttpClient);

  getWeatherForecast(lat: number, lng: number): Observable<WeatherForecastResult | null> {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current_weather=true&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto`;

    return this.http.get<any>(url).pipe(
      map((res) => {
        if (!res || !res.daily) return null;

        const currentTemp = res.current_weather ? Math.round(res.current_weather.temperature) : undefined;
        const daily: DailyWeather[] = (res.daily.time || []).map((dateStr: string, idx: number) => {
          const code = res.daily.weathercode ? res.daily.weathercode[idx] : 0;
          const { label, icon } = this.parseWeatherCode(code);
          return {
            date: dateStr,
            weatherCode: code,
            weatherLabel: label,
            weatherIcon: icon,
            tempMax: Math.round(res.daily.temperature_2m_max[idx]),
            tempMin: Math.round(res.daily.temperature_2m_min[idx]),
            precipProbMax: res.daily.precipitation_probability_max ? res.daily.precipitation_probability_max[idx] : 0,
          };
        });

        return { currentTemp, daily };
      }),
      catchError((err) => {
        console.warn('Weather service failed to fetch open-meteo forecast', err);
        return of(null);
      })
    );
  }

  parseWeatherCode(code: number): { label: string; icon: string } {
    if (code === 0) return { label: 'Trời quang / Nắng', icon: '☀️' };
    if (code >= 1 && code <= 3) return { label: 'Có mây nhẹ', icon: '⛅' };
    if (code === 45 || code === 48) return { label: 'Sương mù', icon: '🌫️' };
    if (code >= 51 && code <= 65) return { label: 'Mưa rào nhẹ', icon: '🌧️' };
    if (code >= 71 && code <= 77) return { label: 'Có tuyết / Lạnh giá', icon: '❄️' };
    if (code >= 80 && code <= 82) return { label: 'Mưa rào nặng hạt', icon: '🌧️' };
    if (code >= 95) return { label: 'Dông bão', icon: '🌩️' };
    return { label: 'Nắng ấm', icon: '☀️' };
  }
}
