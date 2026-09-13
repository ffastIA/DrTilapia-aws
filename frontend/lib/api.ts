// CAMINHO: frontend/lib/api.ts

import axios from 'axios';
import { useAuthStore } from '@/store/authStore';

// Usa o proxy reverso configurado em next.config.js (rewrites /api-proxy/* → backend).
// Isso evita CORS completamente: o browser envia para localhost:3000/api-proxy/*
// e o servidor Next.js repassa para localhost:8000/*.
const API_BASE_URL = '/api-proxy';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60s — suficiente para upload de imagem + rembg
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401 && !error.config.url.includes('/auth/login')) {
      useAuthStore.getState().clearAuth();
    }
    return Promise.reject(error);
  }
);

export default api;
