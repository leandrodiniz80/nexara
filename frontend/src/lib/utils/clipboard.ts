/** Clipboard API can be unavailable (permissions, non-HTTPS context) —
 * callers show/skip a toast based on the boolean instead of throwing. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
