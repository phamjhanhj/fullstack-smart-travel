# syntax=docker/dockerfile:1

# Backend image (FastAPI)
FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY Data/ /app/Data/

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /app

USER app
EXPOSE 8000

# Apply all database migrations before serving requests.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# Frontend build image (Angular)
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build -- --configuration production

# Frontend runtime image (Nginx)
FROM nginx:1.27-alpine AS frontend

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/frontend/dist/frontend/browser/ /usr/share/nginx/html/

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
