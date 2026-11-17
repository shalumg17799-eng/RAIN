/**
 * Which source answers the conversation. Tiny and dependency-free so the chat
 * hook can read it without pulling the API client into the main bundle.
 */
export const API_MODE: 'recorded' | 'http' =
  import.meta.env.VITE_ULTRA_API_MODE === 'http' && import.meta.env.VITE_ULTRA_API_BASE ? 'http' : 'recorded';
