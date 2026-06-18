export function extractUrlFromTips(tips) {
  if (!tips) return null;
  const match = tips.match(/<a\s[^>]*href=["']([^"']+)["'][^>]*>/i);
  if (!match) return null;
  const url = match[1].replace(/&amp;/g, '&');
  return /^https?:\/\//i.test(url) ? url : null;
}
