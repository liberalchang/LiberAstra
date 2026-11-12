/** 角色图 URL。version 用图片路径，角色删除/重建或图片替换后缓存键随之变化。 */
export function characterImageUrl(id: number, slot: string, version?: string | null): string {
  const suffix = version ? `?v=${encodeURIComponent(version)}` : "";
  return `/api/v1/characters/${id}/image/${slot}${suffix}`;
}
