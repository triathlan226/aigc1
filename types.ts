import type { ReactNode } from 'react';
export interface ImageRecord {
  id: string;
  prompt: string;
  style: string;
  url: string;
  width: number;
  height: number;
  timestamp: string;
}

export interface ArtStyle {
  name: string;
  promptSuffix: string;
  icon: string;
}

export interface Dimension {
  name: string;
  width: number;
  height: number;
  icon: ReactNode;
}

export type NotificationType = 'success' | 'error';

export interface Notification {
  id: number;
  message: string;
  type: NotificationType;
}

