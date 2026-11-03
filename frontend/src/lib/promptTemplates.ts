/** 新建模板时，ID 必须与现有模板不同；ID 区分大小写。 */
export function hasTemplateIdConflict(id: string, existingIds: Iterable<string>): boolean {
  const trimmed = id.trim();
  if (!trimmed) return false;
  for (const existing of existingIds) {
    if (existing === trimmed) return true;
  }
  return false;
}
