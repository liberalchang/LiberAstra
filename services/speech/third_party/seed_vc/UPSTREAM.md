# Seed-VC upstream

- Repository: <https://github.com/Plachtaa/Seed-VC>
- Commit: `51383efd921027683c89e5348211d93ff12ac2a8`
- License: GPL-3.0，见同目录 `LICENSE`
- 权重不随仓库分发；运行时从 `/models` 读取。

## Vendored files

- `modules/commons.py`
- `modules/audio.py`
- `modules/flow_matching.py`
- `modules/diffusion_transformer.py`
- `modules/wavenet.py`
- `modules/encodec.py`
- `modules/length_regulator.py`
- `modules/bigvgan/`
- `modules/campplus/`
- `config_dit_mel_seed_uvit_whisper_small_wavenet.yml`

## Trimmed

- 训练脚本、CLI、HF 下载 helper、示例和测试数据未引入。
- V1 `seed-uvit-whisper-small-wavenet` 推理不用的 `openvoice/`、`hifigan/`、`rmvpe.py`、`v2/` 未引入。
- 配置里的 `timbre_shifter` / OpenVoice 路径保留为上游原样，但 `build_model()` 不加载它们；推理不需要 OpenVoice 权重。
- `modules/length_regulator.py` 在模块加载时 import `dac.nn.quantize.VectorQuantize`；当前配置 `vector_quantize=false`，服务在导入前注册一个占位模块，满足 import 且不会实例化。
- 对 vendored 源码不做业务修改。路径覆盖在 `services/speech/engine.py` 的 Seed-VC 适配层完成。
