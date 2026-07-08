import { backendApi } from './backendApi.js';
import { mockApi } from './mockApi.js';

export const apiMode = import.meta.env.VITE_API_MODE || 'mock';

export const api = apiMode === 'backend' ? backendApi : mockApi;

export function isBackendMode() {
  return apiMode === 'backend';
}
