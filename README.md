# 千问语音试听台

在浏览器里试听阿里云百炼 `qwen-audio-3.1-tts-flash`。可选系统音色，调节语速、音量、音调和指令，边合成边播放。也可以用一段公网音频复刻音色。

API Key 只放在 backend。页面不接触密钥。

模型只在华北 2（北京）提供。Key、业务空间和模型授权都要选北京。

## 启动

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item web/.env.example web/.env
```

编辑 `backend/.env`，至少填入 `DASHSCOPE_API_KEY`。北京业务空间再填 `WORKSPACE_ID`。

```powershell
docker compose up --build
```

打开 http://localhost:8080 。

## 配置

`backend/.env`：

| 变量 | 作用 |
| --- | --- |
| `DASHSCOPE_API_KEY` | 百炼北京地域的 API Key，必填 |
| `WORKSPACE_ID` | 业务空间 ID。填写后请求发往 `https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/api/v1` |
| `DASHSCOPE_BASE_URL` | 可选。覆盖上面的地址，需包含 `/api/v1`，末尾不要斜杠 |
| `PUBLIC_BASE_URL` | 可选。站点公网根地址。本地上传复刻音频时，百炼要从这里拉取 `/media/` 下的文件 |

没配 `WORKSPACE_ID` 时，请求走 `https://dashscope.aliyuncs.com/api/v1`。`PUBLIC_BASE_URL` 留空时，复刻请改填百炼能访问的音频 URL。

`web/.env` 只有 nginx 反代目标，默认 `API_UPSTREAM=http://backend:8000`。一般不用改。

这两个 `.env` 都不要提交。示例文件是 `backend/.env.example` 和 `web/.env.example`。

## 页面

- 文本最长 2000 字。Ctrl + Enter 合成并播放。
- 音色可按分组、性别和关键词筛选。
- 复刻样本为 wav、mp3 或 m4a，建议 10 到 20 秒清晰人声。前缀只能是字母和数字，最多 10 位。

## 目录

- `backend/`：FastAPI。合成走 SSE，音色和上传文件记在数据卷里。
- `web/`：静态页面，由 nginx 把 `/api/` 和 `/media/` 转到 backend。
- `docs/qwen-audio-3.1-tts-flash接入文档.md`：直接对接百炼原协议时的说明。新项目不要调用本仓库的 `/api/tts/stream`。

## 测试

```powershell
cd backend
pip install -r requirements.txt
pytest
```
