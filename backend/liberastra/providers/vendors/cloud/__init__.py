"""云端模型供应商。适配器按官方文档接，不走非官方反代。"""

from liberastra.providers.vendors.cloud.presets import CLOUD_TYPES, presets_for

__all__ = ["CLOUD_TYPES", "presets_for"]
