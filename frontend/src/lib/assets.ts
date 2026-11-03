import { fetchAssetBlob, type AssetOut } from "@/api/client";
import { assetDownloadName } from "@/lib/utils";

/** 把资源库资产取回为 File，复用只接受上传文件的现有表单流程。 */
export async function assetAsFile(asset: AssetOut): Promise<File> {
  const blob = await fetchAssetBlob(asset.id);
  const rawSource = typeof asset.meta?.source_name === "string" ? asset.meta.source_name.trim() : "";
  const source = rawSource.split(/[\\/]/).pop() ?? "";
  const name = /\.[a-z0-9]{2,5}$/i.test(source) ? source : assetDownloadName(asset);
  const lastModified = Date.parse(asset.created_at) || Date.now();
  return new File([blob], name, {
    type: blob.type || asset.mime || "application/octet-stream",
    lastModified,
  });
}

export async function assetsAsFiles(assets: AssetOut[]): Promise<File[]> {
  return Promise.all(assets.map(assetAsFile));
}
