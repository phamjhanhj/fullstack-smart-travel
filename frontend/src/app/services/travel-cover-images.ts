type DestinationCoverSet = {
  aliases: string[];
  images: string[];
};

export const GENERIC_TRAVEL_FALLBACK_IMAGES = [
  'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1433086966358-54859d0ed716?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=900&q=80',
];

const DESTINATION_COVER_SETS: DestinationCoverSet[] = [
  {
    aliases: ['da nang', 'danang', 'my khe', 'ba na', 'dragon bridge', 'cau rong'],
    images: [
      'https://commons.wikimedia.org/wiki/Special:FilePath/Da%20Nang%20Dragon%20Bridge%202020%20IMG%204019.jpg?width=1200',
    ],
  },
  {
    aliases: ['ha noi', 'hanoi', 'hoan kiem', 'ho guom', 'old quarter'],
    images: [
      'https://images.unsplash.com/photo-1509030450996-9352e043443f?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['hoi an', 'hoian', 'pho co hoi an'],
    images: [
      'https://images.unsplash.com/photo-1594917409241-d64e9a4f4094?auto=format&fit=crop&w=900&q=80',
      'https://commons.wikimedia.org/wiki/Special:FilePath/Hoi%20An%20%28I%29.jpg?width=1200',
    ],
  },
  {
    aliases: ['phu quoc', 'phuquoc'],
    images: [
      'https://images.unsplash.com/photo-1589308454676-4259466e3437?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['sapa', 'sa pa', 'fansipan', 'muong hoa'],
    images: [
      'https://images.unsplash.com/photo-1504457047772-27fad174996b?auto=format&fit=crop&w=900&q=80',
      'https://commons.wikimedia.org/wiki/Special:FilePath/Sapa3.jpg?width=1200',
    ],
  },
  {
    aliases: ['ha giang', 'ma pi leng', 'dong van', 'nho que'],
    images: [
      'https://images.unsplash.com/photo-1627471203492-f04b2816911d?auto=format&fit=crop&w=900&q=80',
      'https://commons.wikimedia.org/wiki/Special:FilePath/Ma%20Pi%20Leng%20Pass%20winding%20road%20Ha%20Giang%20Vietnam.jpg?width=1200',
    ],
  },
  {
    aliases: ['da lat', 'dalat', 'xuan huong', 'lam dong'],
    images: [
      'https://images.unsplash.com/photo-1563293816-7f4f6556e89f?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['ha long', 'halong', 'quang ninh'],
    images: [
      'https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['nha trang', 'khanh hoa'],
    images: [
      'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1589308454676-4259466e3437?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['hue', 'kinh thanh hue', 'thua thien hue'],
    images: [
      'https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['ho chi minh', 'sai gon', 'saigon', 'hcmc'],
    images: [
      'https://images.unsplash.com/photo-1583417319070-4a69db38a482?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['vung tau', 'ba ria vung tau'],
    images: [
      'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['bali', 'indonesia', 'ubud', 'uluwatu'],
    images: [
      'https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1518548419970-58e3b4079ab2?auto=format&fit=crop&w=900&q=80',
    ],
  },
  {
    aliases: ['tokyo', 'japan', 'nhat ban'],
    images: [
      'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=900&q=80',
      'https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=900&q=80',
    ],
  },
];

export function normalizeDestination(value: string | null | undefined): string {
  return (value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[\u0111\u0110]/g, 'd')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export function getDestinationCoverImages(destination: string | null | undefined): string[] {
  const normalized = normalizeDestination(destination);
  if (!normalized) return [];

  const matchedSet = DESTINATION_COVER_SETS.find((set) =>
    set.aliases.some((alias) => normalized === alias || normalized.includes(alias)),
  );

  return matchedSet?.images || [];
}

export function pickStableImage(images: string[], seed: string | null | undefined): string {
  if (images.length === 0) return '';

  const source = seed || images[0];
  let hash = 0;
  for (let i = 0; i < source.length; i++) {
    hash = source.charCodeAt(i) + ((hash << 5) - hash);
  }

  return images[Math.abs(hash) % images.length];
}

export function resolveTravelFallbackImage(seed: string | null | undefined, attempt = 0): string {
  if (GENERIC_TRAVEL_FALLBACK_IMAGES.length === 0) return '';

  const source = seed || 'travel';
  let hash = 0;
  for (let i = 0; i < source.length; i++) {
    hash = source.charCodeAt(i) + ((hash << 5) - hash);
  }

  const index = (Math.abs(hash) + attempt) % GENERIC_TRAVEL_FALLBACK_IMAGES.length;
  return GENERIC_TRAVEL_FALLBACK_IMAGES[index];
}

export function resolveTravelCoverImage(
  destination: string | null | undefined,
  seed?: string | null,
  apiImages: string[] = [],
  explicitCoverImage?: string | null,
): string {
  const curatedImages = getDestinationCoverImages(destination);
  if (curatedImages.length > 0) {
    return pickStableImage(curatedImages, seed || destination);
  }

  if (explicitCoverImage) {
    return explicitCoverImage;
  }

  if (apiImages.length > 0) {
    return pickStableImage(apiImages, seed || destination);
  }

  return resolveTravelFallbackImage(seed || destination || 'travel');
}

export function getInlineScenicFallback(isLight: boolean): string {
  const bg = isLight ? '#eef6f3' : '#111827';
  const farMountain = isLight ? '#b7d1cc' : '#1f2937';
  const nearMountain = isLight ? '#6aa89a' : '#0f766e';
  const sky = isLight ? '#dbeafe' : '#020617';
  const sun = isLight ? '#f59e0b' : '#e0f2fe';
  const stars = isLight ? '#ffffff' : '#c4b5fd';
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="${sky}"/>
          <stop offset="1" stop-color="${bg}"/>
        </linearGradient>
      </defs>
      <rect width="900" height="600" fill="url(#sky)"/>
      <circle cx="720" cy="125" r="46" fill="${sun}" opacity=".9"/>
      <circle cx="120" cy="90" r="3" fill="${stars}" opacity=".75"/>
      <circle cx="210" cy="145" r="2" fill="${stars}" opacity=".7"/>
      <circle cx="785" cy="230" r="2.5" fill="${stars}" opacity=".65"/>
      <path d="M0 390 170 245 310 382 475 205 710 418 900 260 900 600 0 600Z" fill="${farMountain}" opacity=".95"/>
      <path d="M0 465 125 352 250 455 410 305 585 485 735 345 900 460 900 600 0 600Z" fill="${nearMountain}" opacity=".95"/>
      <path d="M0 520 C180 485 285 540 450 508 S725 485 900 525 V600 H0Z" fill="${isLight ? '#f8fafc' : '#030712'}" opacity=".9"/>
    </svg>
  `;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}
