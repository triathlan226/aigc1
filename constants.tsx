
import React from 'react';
import type { ArtStyle, Dimension } from './types.ts';
import { DesktopIcon, DevicePhoneMobileIcon, SquareIcon, DocumentTextIcon } from './components/icons.tsx';

export const ART_STYLES: ArtStyle[] = [
  { name: '🌸 日本動漫風', promptSuffix: ', japanese anime style, vibrant, detailed', icon: '🌸' },
  { name: '🌿 吉卜力工作室', promptSuffix: ', ghibli studio style, whimsical, hand-drawn', icon: '🌿' },
  { name: '🎪 卡通風格', promptSuffix: ', cartoon style, bold lines, colorful', icon: '🎪' },
  { name: '🖌️ 水彩畫', promptSuffix: ', watercolor painting, soft edges, translucent', icon: '🖌️' },
  { name: '🎨 油畫風格', promptSuffix: ', oil painting, textured, rich colors', icon: '🎨' },
  { name: '💻 數位藝術', promptSuffix: ', digital art, concept art, hyperrealistic', icon: '💻' },
  { name: '📷 寫實風格', promptSuffix: ', realistic, photorealistic, 8k', icon: '📷' },
  { name: '✏️ 黑白素描', promptSuffix: ', black and white sketch, pencil drawing, detailed shading', icon: '✏️' },
  { name: '🖍️ 色鉛筆', promptSuffix: ', colored pencil art, layered colors, detailed', icon: '🖍️' },
  { name: '🌃 賽博朋克', promptSuffix: ', cyberpunk, neon lights, futuristic city, dystopian', icon: '🌃' },
  { name: '📼 復古風格', promptSuffix: ', retro style, vintage, 80s aesthetic, film grain', icon: '📼' },
];

export const DIMENSIONS: Dimension[] = [
  { name: '🖥️ 1920×1080', width: 1920, height: 1080, icon: <DesktopIcon /> },
  { name: '📱 1080×1920', width: 1080, height: 1920, icon: <DevicePhoneMobileIcon /> },
  { name: '⬜ 1024×1024', width: 1024, height: 1024, icon: <SquareIcon /> },
  { name: '📄 512×768', width: 512, height: 768, icon: <DocumentTextIcon /> },
];
