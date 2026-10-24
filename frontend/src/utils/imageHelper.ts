/**
 * StockSense AI - Product Image URL Helper
 * Provides authoritative URL resolution, localhost backend prepending,
 * and reliable fallback image handling.
 */

const BACKEND_ORIGIN = 'http://localhost:8000';
export const PLACEHOLDER_IMAGE = '/placeholder-product.svg';

export function getProductImageUrl(imageUrl?: string | null): string {
  if (!imageUrl) {
    return PLACEHOLDER_IMAGE;
  }

  // Already a full external or data URL
  if (imageUrl.startsWith('http://') || imageUrl.startsWith('https://') || imageUrl.startsWith('data:')) {
    return imageUrl;
  }

  // Uploaded static file on backend
  if (imageUrl.startsWith('/uploads/')) {
    return `${BACKEND_ORIGIN}${imageUrl}`;
  }

  if (imageUrl.startsWith('/')) {
    return imageUrl;
  }

  return `${BACKEND_ORIGIN}/${imageUrl}`;
}

/**
 * Image onError handler to cleanly replace broken image links with placeholder
 */
export function onProductImageError(e: React.SyntheticEvent<HTMLImageElement, Event>) {
  const target = e.currentTarget;
  if (!target.src.endsWith(PLACEHOLDER_IMAGE)) {
    target.src = PLACEHOLDER_IMAGE;
  }
}
