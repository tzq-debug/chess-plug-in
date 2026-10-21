# 引擎目录

把 Pikafish 可执行文件放在这里：

```
engine/pikafish.exe
```

权重文件 `pikafish.nnue` 放到**项目根目录**（与 `engine/` 同级），不要放这里——
引擎启动时按自己的路径规则找权重，放错位置会加载失败。

下载后在 `config.json` 里确认：

```json
{ "engine_path": "engine/pikafish.exe" }
```

（本目录不提交 exe，见项目根目录 `.gitignore`）
