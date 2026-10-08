# qwen-audio-3.1-tts-flash 从零接入文档

直接对接阿里云百炼官方接口。新项目不要调用本仓库的 `/api/tts/stream`，也不要走 OpenAI 兼容的 `/audio/speech`，更不要走千问 3-TTS 那套 `qwen-voice-enrollment`。`qwen-audio-3.1-tts-flash` 只用下面两套 DashScope 原协议。

浏览器不能带自定义鉴权头，API Key 必须放在你自己的服务端。前端只连你的服务。

核对日期：2026-10-08。模型、音色和域名会改，实现前以官方页面为准。

## 官方文档

| 用途 | 地址 |
| --- | --- |
| 模型说明、北京价格、RPS | https://help.aliyun.com/zh/model-studio/qwen-audio-3-1-tts-flash |
| 获取 API Key | https://help.aliyun.com/zh/model-studio/get-api-key |
| 地域、业务空间域名 | https://help.aliyun.com/zh/model-studio/regions |
| Base URL 总览 | https://help.aliyun.com/zh/model-studio/base-url |
| 业务空间 | https://help.aliyun.com/zh/model-studio/use-workspace |
| 非实时合成说明（指令、标签、方言） | https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide |
| 非实时 HTTP / SSE 接口 | https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api |
| 实时合成说明 | https://help.aliyun.com/zh/model-studio/realtime-tts-user-guide |
| WebSocket 接入流程 | https://help.aliyun.com/zh/model-studio/qwen-audio-tts-websocket-api |
| WebSocket 客户端事件 | https://help.aliyun.com/zh/model-studio/qwen-audio-tts-client-events |
| WebSocket 服务端事件 | https://help.aliyun.com/zh/model-studio/qwen-audio-tts-server-events |
| 实时 WebSocket 总览 | https://help.aliyun.com/zh/model-studio/realtime-websocket-overview |
| 3.1 系统音色表 | https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list |
| 声音复刻说明与录音要求 | https://help.aliyun.com/zh/model-studio/voice-cloning-user-guide |
| 声音复刻 HTTP | https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api |
| Python SDK（可选，不是必须） | https://help.aliyun.com/zh/model-studio/qwen-audio-tts-python-sdk |
| Java HTTP SDK（可选） | https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-java-sdk |
| SSML / LaTeX | https://help.aliyun.com/zh/model-studio/ssml-latex-user-guide |
| 错误码 | https://help.aliyun.com/zh/model-studio/error-code |
| 百炼控制台 | https://bailian.console.aliyun.com/ |
| 开通入口 | https://www.aliyun.com/product/bailian |

英文对照站是把上面路径里的 `/zh/` 换成 `/en/`，域名仍是 `help.aliyun.com`。国际站镜像是 `https://www.alibabacloud.com/help/zh/model-studio/...`，路径相同。

## 先分清接口

这个模型只有两条官方通路，模型名都是 `qwen-audio-3.1-tts-flash`。

| 通路 | 地址 | 音频怎么回来 | 适合 |
| --- | --- | --- | --- |
| 非实时 HTTP | `POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer` | 不加 SSE 头：响应里给一个 24 小时有效的文件 URL。加 `X-DashScope-SSE: enable`：SSE 里一段段 Base64 音频 | 网页试听、短文本播报。官方写明只在华北 2（北京） |
| 实时 WebSocket | `wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference` | JSON 事件走文本帧，音频走二进制帧，不是 Base64 | 边生成文本边合成、要更低首包延迟 |

不要接这些：

- `wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3-tts-flash-realtime`。那是另一系列，音色是 Cherry、Serena，协议是 `session.update`。
- `model: "qwen-voice-enrollment"` 和 Base64 音频。那是千问 3-TTS 复刻，造出来的音色不能给 `qwen-audio-3.1-tts-flash` 用。
- `qwen-audio-3.0-tts-flash` 的音色，例如 `longanhuan_v3.6`。3.1 要用 `longanhuan_v3.1`。音色和模型不能交叉，否则是 `InvalidParameter`。
- Token Plan 的 `sk-sp-` Key 和 `token-plan.cn-beijing.maas.aliyuncs.com`。语音合成用按量付费的 `sk-` Key。

北京非实时 HTTP 文档写的是业务空间域名。旧域名 `https://dashscope.aliyuncs.com/api/v1` 官方说仍可用，但新项目直接用业务空间域名。`DASHSCOPE_BASE_URL` 若自行覆盖，必须带上 `/api/v1`，并且不要把北京 HTTP 和新加坡 WebSocket 混用。

## 开通和鉴权

1. 阿里云账号完成实名，开通百炼。入口是 https://www.aliyun.com/product/bailian 。
2. 控制台右上角地域选华北 2（北京）。Key、业务空间、模型列表都按地域隔离，新加坡的 Key 打北京域名会 401。
3. 在 API Key 页创建 Key，只在创建时完整显示一次。归属选你要计费的业务空间。文档是 https://help.aliyun.com/zh/model-studio/get-api-key 。
4. 在业务空间管理页复制该空间的 Workspace ID，或在创建 Key 后的弹窗里复制 API Host。域名就是 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com`。说明见 https://help.aliyun.com/zh/model-studio/regions 。
5. 子业务空间默认没有全部模型权限，要在空间里给 `qwen-audio-3.1-tts-flash` 授权。默认业务空间一般可以直接调。

每个请求：

```http
Authorization: Bearer sk-你的北京Key
Content-Type: application/json
```

WebSocket 的 `Authorization` 在握手时校验。缺 Key 或 Key 无效，握手直接 HTTP 401 或 403，不会进入事件流。

环境变量建议：

```bash
DASHSCOPE_API_KEY=sk-...
WORKSPACE_ID=llm-xxxxxxxx
```

Base URL 自己拼：

```text
https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/api/v1
wss://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference
```

没配 Workspace ID 时，旧地址 `https://dashscope.aliyuncs.com/api/v1` 仍可打通。新项目优先用业务空间域名。

模型页写的北京原价是输入 1.5 元 / 百万 token，输出 12 元 / 百万 token，RPS 为 3。活动价以控制台为准：https://help.aliyun.com/zh/model-studio/qwen-audio-3-1-tts-flash 。3.1 的用量字段是 `input_tokens`、`output_tokens`、`total_tokens`。3.0 才是 `characters`。RPS 为 3，试听不要并发打。

## 音色

没有「列出全部系统音色」的接口。系统音色是文档里的固定表，`voice` 区分大小写。完整表以这一页为准：https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list 。下面是 2026-10-08 从该页抄下的 3.1 列表，共 68 个。

### 多语种与方言

这 4 个都支持上海话、广东话、东北话、重庆话、陕西话、云南话、宁波话、甘肃话，以及日语、韩语、法语、德语、葡萄牙语、意大利语、越南语、印尼语。方言和外语用 `instruction` 说，例如「用重庆话说」，不要换 `voice`。

| 名称 | voice | 性别 | 特质 |
| --- | --- | --- | --- |
| 龙安欢 | `longanhuan_v3.1` | 女 | 重庆话、宁波话、韩语、印尼语 |
| 龙安灵心 | `longanlingxin_v3.1` | 女 | 云南话、陕西话、上海话、法语、意大利语 |
| 龙安风悦 | `longanfengyue_v3.1` | 女 | 东北话、越南语、日语 |
| 许南川 | `xunanchuan_v3.1` | 男 | 甘肃话、东北话、法语、葡萄牙语 |

### 精品中文

只支持普通话。

| 名称 | voice | 性别 | 特质 |
| --- | --- | --- | --- |
| 于小云 | `yuxiaoyun_v3.1` | 女 | 元气、亲切、自然 |
| 乔小娇 | `qiaoxiaojiao_v3.1` | 女 | 俏丽、可爱 |
| 夏小晨 | `xiaxiaochen_v3.1` | 女 | 元气、明亮 |
| 安明远 | `anmingyuan_v3.1` | 男 | 清亮、自然 |
| 温怀清 | `wenhuaiqing_v3.1` | 女 | 清亮、柔和 |
| 安小岚 | `anxiaolan_v3.1` | 女 | 清甜、纯净 |
| 谢舒柔 | `xieshurou_v3.1` | 女 | 柔和、自然、知性 |
| 白清岚 | `baiqinglan_v3.1` | 女 | 明亮、清纯 |
| 许玉远 | `xuyuyuan_v3.1` | 女 | 知性、成熟、质感 |
| 安若柔 | `anruorou_v3.1` | 女 | 气声、知性 |
| 闻怀之 | `wenhuaizhi_v3.1` | 女 | 稳重、成熟 |
| 萧行之 | `xiaoxingzhi_v3.1` | 女 | 端庄、贵气 |
| 顾云舒 | `guyunshu_v3.1` | 女 | 成熟、稳重 |
| 霍拙石 | `huozhuoshi_v3.1` | 男 | 清亮 |
| 叶清禾 | `yeqinghe_v3.1` | 女 | 亲切、温柔 |
| 云欢欢 | `yunhuanhuan_v3.1` | 女 | 高亢、热情 |
| 徐小俏 | `xuxiaoqiao_v3.1` | 女 | 自然、俏皮 |
| 白安然 | `baianran_v3.1` | 女 | 低沉、浑厚、气声 |
| 许言初 | `xuyanchu_v3.1` | 女 | 沉稳、磁性 |
| 叶知晴 | `yezhiqing_v3.1` | 女 | 轻快、自然 |
| 安迪 | `andi_v3.1` | 男 | ABC 口音，仍是普通话音色 |
| 安语晴 | `anyuqing_v3.1` | 女 | 甜妹 |

### 精品英文

只支持英文。ID 的大小写必须和表里一致。`Emily` 在这一组，不在精品中文里。

| 名称 | voice | 性别 | 口音 |
| --- | --- | --- | --- |
| Emily | `Emily_v3.1` | 女 | 英式 |
| Luna | `Luna_v3.1` | 女 | 英式 |
| Eric | `Eric_v3.1` | 男 | 英式 |
| Luca | `Luca_v3.1` | 男 | 英式 |
| Abby | `Abby_v3.1` | 女 | 美式 |
| Annie | `Annie_v3.1` | 女 | 美式 |
| Ava | `Ava_v3.1` | 女 | 美式 |
| Beth | `Beth_v3.1` | 女 | 美式 |
| Betty | `Betty_v3.1` | 女 | 美式 |
| Cally | `Cally_v3.1` | 女 | 美式 |
| Cindy | `Cindy_v3.1` | 女 | 美式 |
| Donna | `Donna_v3.1` | 女 | 美式 |
| Andy | `Andy_v3.1` | 男 | 美式 |
| Brian | `Brian_v3.1` | 男 | 美式 |
| David | `David_v3.1` | 男 | 美式 |

### 其他系统音色

| 名称 | voice | 性别 | 特质 |
| --- | --- | --- | --- |
| 龙安元妃 | `longanyuanfei_v3.1` | 女 | 高傲妃子音 |
| 龙杰力豆 | `longjielidou_v3.1` | 男 | 天真男童音 |
| 龙安灵希 | `longanlingxi_v3.1` | 女 | 可爱甜美音 |
| 龙火火 | `longhuohuo_v3.1` | 男 | 顽皮少年音 |
| 龙应桃 | `longyingtao_v3.1` | 女 | 温柔淡定女 |
| 龙安雅 | `longanya_v3.1` | 女 | 高雅气质女 |
| 龙婉 | `longwan_v3.1` | 女 | 细腻柔声女 |
| 龙星 | `longxing_v3.1` | 女 | 温婉邻家女 |
| 龙华 | `longhua_v3.1` | 女 | 元气甜美女 |
| 龙寒 | `longhan_v3.1` | 男 | 温暖痴情男 |
| 龙安智 | `longanzhi_v3.1` | 男 | 睿智轻熟男 |
| 龙哲 | `longzhe_v3.1` | 男 | 呆板大暖男 |
| 龙安洋 | `longanyang_v3.1` | 男 | 阳光大男孩 |
| 李白 | `libai_v3.1` | 男 | 古代诗仙男 |
| 龙铃 | `longling_v3.1` | 女 | 稚气呆板女 |
| 龙牛牛 | `longniuniu_v3.1` | 男 | 阳光男童声 |
| 龙闪闪 | `longshanshan_v3.1` | 男 | 戏剧化童声 |
| 龙泡泡 | `longpaopao_v3.1` | 女 | 飞天泡泡音 |
| loongstella | `loongstella_v3.1` | 女 | 飒爽利落女 |
| 龙媛 | `longyuan_v3.1` | 女 | 温暖治愈女 |
| 龙妙 | `longmiao_v3.1` | 女 | 抑扬顿挫女 |
| 龙三叔 | `longsanshu_v3.1` | 男 | 沉稳质感男 |
| 龙安莉 | `longanli_v3.1` | 女 | 利落从容女 |
| 龙安温 | `longanwen_v3.1` | 女 | 优雅知性女 |
| 龙安朗 | `longanlang_v3.1` | 男 | 清爽利落男 |
| 龙小夏 | `longxiaoxia_v3.1` | 女 | 沉稳权威女 |
| 龙安冲 | `longanchong_v3.1` | 男 | 激情推销男 |

文本语言要落在该音色支持的范围内，否则发音会怪。复刻音色的 ID 不是这张表里的，见后面的复刻一节。

## 合成参数

HTTP 的字段都在 `input` 里。WebSocket 的同一批字段在 `run-task` 的 `payload.parameters` 里，文本不放在这里。

| 字段 | HTTP | WebSocket | 说明 |
| --- | --- | --- | --- |
| `text` | `input.text`，必填 | 不在 run-task 里，用 continue-task 的 `payload.input.text` | 待合成文本。WebSocket 单次最多 2 万字符，累计最多 20 万，两次发送间隔不能超过 23 秒 |
| `voice` | 必填 | 必填 | 系统音色或复刻得到的 `voice_id` |
| `format` | 可选，默认 `mp3` | 可选，默认 `mp3` | `pcm`、`wav`、`mp3`、`opus` |
| `sample_rate` | 可选，默认 22050 | 可选，默认 22050 | 8000、12000、16000、22050、24000、44100、48000。`opus` 不要用 22050 和 44100 |
| `volume` | 0–100，默认 50 | 同左 | 音量 |
| `rate` | 0.5–2，默认 1 | 同左 | 语速 |
| `pitch` | 0.5–2，默认 1 | 同左 | 音调 |
| `bit_rate` | 仅 `opus`，6–510，默认 32，单位 kbps | `mp3` 和 `opus` 都可以设 | HTTP 和 WebSocket 在这一点上不一样 |
| `language_hints` | 数组，只认第一个 | 同左 | 目标语种，不是方言开关。取值 `zh` `en` `fr` `de` `ja` `ko` `ru` `pt` `th` `id` `vi` `es` `it` `ms` `fil` `ar` |
| `instruction` | 可选 | 可选 | 自然语言，控制方言、情绪、角色、语速。系统和复刻音色都可以 |
| `enable_ssml` | 可选，默认 false | 可选 | 为 true 时文本要是 SSML，而且 WebSocket 只能发一次 continue-task |
| `word_timestamp_enabled` | 仅流式 | 仅流式 | 字级时间戳。复刻音色支持；系统音色是否支持看音色表 |
| `seed` | 0–65535，默认 0 | 同左 | 相同模型、文本、音色和其他参数下可复现 |
| `hot_fix` | 可选 | 可选 | `pronunciation` 是拼音标注，`replace` 是合成前替换文本 |
| `enable_aigc_tag` | 可选 | 可选 | 往 wav、mp3、opus 里写 AIGC 隐性标识。pcm 没有容器，不要靠它 |

`hot_fix` 的形状：

```json
"hot_fix": {
  "pronunciation": [{ "天气": "tian1 qi4" }],
  "replace": [{ "今天": "金天" }]
}
```

网页边收边播用 `format: "pcm"`、`sample_rate: 24000`。这是单声道、16 bit、小端、无文件头的原始 PCM。2026-10-08 用 `longanhuan_v3.1` 打北京业务空间域名，短句「你好，这是一段流式语音合成测试。」返回了 6 个音频块，采样率 24000，PCM 138240 字节，开头字节不是 `RIFF`，时长约 2.88 秒。用量是输入 16 token、输出 36 token、合计 52 token。`mp3` 要流式解码器，首包还可能带帧头，不适合自己用 Web Audio 直接排时间线。

## 路线一：HTTP，先打通再改成流式

非流式一次拿完整文件，用来确认 Key、空间和音色。接口说明：https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api 。

```bash
curl -X POST "https://${WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer" \
  -H "Authorization: Bearer ${DASHSCOPE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-audio-3.1-tts-flash",
    "input": {
      "text": "你好，这是一段语音合成测试。",
      "voice": "longanhuan_v3.1",
      "format": "wav",
      "sample_rate": 24000
    }
  }'
```

成功时 HTTP 200，`output.audio.data` 为空，`output.audio.url` 是文件地址，`expires_at` 是过期时间戳，大约 24 小时。把这个 URL 再 GET 下来就是 wav。失败时 body 一般是：

```json
{
  "code": "InvalidParameter",
  "message": "具体原因",
  "request_id": "xxxxxxxx"
}
```

把 `message` 和 `request_id` 记下来。不要把带 `Authorization` 的请求打进日志。

## 路线一续：HTTP SSE 流式

同一个 URL，多一个请求头 `X-DashScope-SSE: enable`。服务端按 SSE 推事件。用户指南里的示例：https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide 。

```bash
curl --no-buffer -X POST "https://${WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer" \
  -H "Authorization: Bearer ${DASHSCOPE_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "X-DashScope-SSE: enable" \
  -H "Accept: text/event-stream" \
  -d '{
    "model": "qwen-audio-3.1-tts-flash",
    "input": {
      "text": "你好，这是一段流式语音合成测试。",
      "voice": "longanhuan_v3.1",
      "format": "pcm",
      "sample_rate": 24000,
      "volume": 50,
      "rate": 1.0,
      "pitch": 1.0,
      "instruction": "语气温柔一点",
      "language_hints": ["zh"]
    }
  }'
```

`curl` 必须加 `--no-buffer`。你自己的反向代理也要关响应缓冲，否则首包会被攒住，听起来就不流式了。

线上实际帧长这样。空行分隔一个事件。以 `:` 开头的是注释，例如 `:HTTP_STATUS/200`，丢掉。

```text
id:1
event:result
:HTTP_STATUS/200
data:{"request_id":"...","output":{"finish_reason":"null","type":"sentence-begin","original_text":"你好，这是一段流式语音合成测试。","sentence":{"index":0,"words":[]},"audio":{"data":""}}}

id:2
event:result
data:{"request_id":"...","output":{"finish_reason":"null","type":"sentence-synthesis","audio":{"data":"<base64 pcm>"}}}

id:3
event:result
data:{"request_id":"...","output":{"finish_reason":"stop","audio":{"data":"","url":"https://...","expires_at":1772698611}},"usage":{"input_tokens":16,"output_tokens":36,"total_tokens":52}}
```

处理规则：

- `finish_reason` 在合成过程中是字符串 `"null"`，不是 JSON 的 `null`。只有 `"stop"` 才是结束。
- `type` 为 `sentence-begin`：这句开始，`original_text` 是这句文本，`sentence.index` 从 0 起。此时 `audio.data` 通常是空的。
- `type` 为 `sentence-synthesis`：一个音频块。一句里会有多块。`audio.data` 是 Base64。pcm 时解码后按到达顺序拼接，就是连续的 s16le。
- `type` 为 `sentence-end`：这句结束，这里可能带 `usage` 和字级时间戳。不要在这里停播放，后面可能还有句子。
- `finish_reason` 为 `stop`：全部结束。最后一帧的 `audio.url` 仍可能给整段文件，流式播放可以忽略它。
- 若 `data:` 里直接有 `code` 和 `message`，这是业务错误，停止播放并把 `message` 给用户。
- 读超时要留够。短句几秒就结束，长文本要按分钟计。连接超时和读超时分开设。

字级时间戳在 `sentence.words[]`：`text`、`begin_index`、`end_index`、`begin_time`、`end_time`。时间单位是毫秒。要先把 `word_timestamp_enabled` 设为 true。

浏览器播放 pcm 的做法：用户点击时立刻 `new AudioContext()` 并 `resume()`，否则自动播放策略会把声音吃掉。每来一块 Base64，解码成 `Int16`，除以 32768 得到 `Float32`，`createBuffer(1, 样本数, 24000)`，用 `AudioBufferSourceNode` 排到 `nextTime` 上。`nextTime` 落后于 `currentTime` 时，从 `currentTime + 0.04` 秒重新排，避免块和块之间的空隙越积越大。停止时 `source.stop()` 并关掉 context，同时断开上游 HTTP。

服务端若再转给浏览器，建议自己定义事件，不要把百炼的 SSE 原样暴露，也不要把 Key 放进前端。转述时保留块的顺序即可。

## 路线二：WebSocket 实时

流程原文：https://help.aliyun.com/zh/model-studio/qwen-audio-tts-websocket-api 。字段原文：https://help.aliyun.com/zh/model-studio/qwen-audio-tts-client-events 和 https://help.aliyun.com/zh/model-studio/qwen-audio-tts-server-events 。

握手：

```text
GET /api-ws/v1/inference HTTP/1.1
Host: {WorkspaceId}.cn-beijing.maas.aliyuncs.com
Upgrade: websocket
Connection: Upgrade
Authorization: Bearer sk-...
```

模型名不在 URL 上，在 `run-task` 的 `payload.model` 里。这和千问 3-TTS Realtime 不同。

同一轮的 `run-task`、全部 `continue-task`、`finish-task` 必须是同一个 UUID `task_id`。`header.streaming` 固定 `"duplex"`。下一轮换新的 UUID。可以复用同一条 WebSocket，不必每句都重连。

顺序必须是：

1. 连接成功。
2. 发 `run-task`。`input` 固定是 `{}`。文本不要放在这里。
3. 等到文本帧 `task-started`。没等到不要发文本。
4. 按顺序发一个或多个 `continue-task`。服务端自己分句：完整句马上合成，不完整句先缓存。
5. 文本帧 `result-generated` 且 `type` 为 `sentence-synthesis` 之后，紧接着的二进制帧就是这块音频。二进制帧不要再 Base64 解码。
6. 文本发完必须发 `finish-task`，否则尾句会丢。然后继续读，直到 `task-finished`。
7. 关闭连接，或留着开下一轮。

`run-task`：

```json
{
  "header": {
    "action": "run-task",
    "task_id": "2bf83b9a-baeb-4fda-8d9a-xxxxxxxxxxxx",
    "streaming": "duplex"
  },
  "payload": {
    "task_group": "audio",
    "task": "tts",
    "function": "SpeechSynthesizer",
    "model": "qwen-audio-3.1-tts-flash",
    "parameters": {
      "text_type": "PlainText",
      "voice": "longanhuan_v3.1",
      "format": "pcm",
      "sample_rate": 24000,
      "volume": 50,
      "rate": 1.0,
      "pitch": 1.0,
      "instruction": "用重庆话说",
      "language_hints": ["zh"]
    },
    "input": {}
  }
}
```

`task_group`、`task`、`function`、`text_type` 都是固定字符串，写错任务不会启动。

`continue-task`：

```json
{
  "header": {
    "action": "continue-task",
    "task_id": "同一个 UUID",
    "streaming": "duplex"
  },
  "payload": {
    "input": { "text": "床前明月光，疑是地上霜。" }
  }
}
```

`finish-task`：

```json
{
  "header": {
    "action": "finish-task",
    "task_id": "同一个 UUID",
    "streaming": "duplex"
  },
  "payload": { "input": {} }
}
```

取消当前轮，不关掉连接：

```json
{
  "header": {
    "action": "finish-task",
    "task_id": "同一个 UUID",
    "streaming": "duplex"
  },
  "payload": { "input": { "directive": "cancel" } }
}
```

服务端会马上回 `task-finished`，且不再给后续音频。取消后用新的 `task_id` 再发 `run-task` 即可。

服务端文本事件：

| `header.event` | 含义 |
| --- | --- |
| `task-started` | 可以开始发 `continue-task`。`payload` 是空对象 |
| `result-generated` | 看 `payload.output.type`：`sentence-begin`、`sentence-synthesis`、`sentence-end`。含义和 HTTP SSE 相同。`sentence-synthesis` 后的下一帧二进制才是音频 |
| `task-finished` | 这轮结束。`payload.usage` 里是 token |
| `task-failed` | 失败。读错误码和 `message`，这轮不要再发 `continue-task` |

`sentence-end` 和 `task-finished` 里 3.1 的用量是 `input_tokens`、`output_tokens`、`total_tokens`。

官方写明情感标签只支持单向流式。标签放进 HTTP SSE 的 `text`。WebSocket 这种双向流式，情绪和方言用 `parameters.instruction`，不要假设方括号标签一定生效。

## 指令和文本标签

指令的说明在非实时文档和实时文档里都有，模型列表包含 `qwen-audio-3.1-tts-flash`：https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide 。

`instruction` 是自由文本，系统和复刻音色都接受。它不替换 `text`，只改变读法。例如：

- `用重庆话说`
- `语速稍慢，像在跟朋友聊天`
- `用新闻播报的语气`

多语种那 4 个音色才能稳定读方言和所列外语。精品中文音色即使用指令要求说粤语，也不要指望。

方括号标签写在 `text` 里，不是写在 `instruction` 里。控制类标签管它后面的文本，直到下一个控制类标签，或这句被模型切开。

| 标签 | 作用 |
| --- | --- |
| `[sad]` | 悲伤 |
| `[amazed]` | 惊叹 |
| `[deep and loud shouting]` | 深沉大声呐喊 |
| `[trembling]` | 颤抖 |
| `[angry]` | 愤怒 |
| `[excited]` | 兴奋 |
| `[sarcastic]` | 讽刺 |
| `[curious]` | 好奇 |
| `[like dracula]` | 低沉怪腔 |
| `[bored]` | 无聊 |
| `[tired]` | 疲惫 |
| `[scornful]` | 轻蔑 |
| `[shouting]` | 喊叫 |
| `[asmr]` | 轻声 |
| `[panicked]` | 恐慌 |
| `[mischievously]` | 调皮 |
| `[empathetic]` | 共情 |
| `[whispers]` | 耳语 |
| `[reluctantly]` | 不情愿 |
| `[crying]` | 哭泣 |
| `[serious]` | 严肃 |
| `[very slowly]` | 非常慢 |
| `[very fast]` | 非常快 |

富语言标签只在该位置插入拟声，不改变后面的情感。

| 标签 | 作用 |
| --- | --- |
| `[gasp]` | 倒吸气 |
| `[sighing]` | 叹息 |
| `[clears throat]` | 清嗓 |
| `[giggles]` | 咯咯笑 |
| `[laughing]` | 大笑 |
| `[cough]` | 咳嗽 |
| `[snorts]` | 哼声 |

示例：`[excited]今天的天气真不错！[laughing]我们一起出去玩吧！` 以及 `[serious]请注意安全事项。[excited]好了，现在让我们开始吧！`

标签若被拒绝，以文档当页的表为准，这张表会增删。

## 声音复刻

用户指南：https://help.aliyun.com/zh/model-studio/voice-cloning-user-guide 。HTTP：https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api 。

地址：

```text
POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization
```

`model` 固定为 `voice-enrollment`。`action` 用下划线形式：`create_voice`、`list_voice`、`query_voice`、`update_voice`、`delete_voice`。不要用 `qwen-voice-enrollment` 的 `create` / `preferred_name` / `audio.data`。

创建：

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "create_voice",
    "target_model": "qwen-audio-3.1-tts-flash",
    "prefix": "myvoice",
    "url": "https://cdn.example.com/sample.wav",
    "language_hints": ["zh"]
  }
}
```

`target_model` 必须和以后合成时的 `model` 完全一致。`prefix` 只能是字母和数字，最长 10 位。返回的音色 ID 形如 `qwen-audio-3.1-tts-flash-myvoice-xxxxxx`，字段是 `output.voice_id`，不是 `output.voice`。

```json
{
  "output": { "voice_id": "qwen-audio-3.1-tts-flash-myvoice-xxxxxx" },
  "usage": { "count": 1 },
  "request_id": "xxxx"
}
```

`url` 必须是百炼服务器能直接 GET 的公网地址，不能带鉴权，不能是 `localhost`、内网 IP，也不能是 `data:` Base64。本地文件要先上传到对象存储或任何公网静态地址，再把那个 URL 传进去。

Qwen-Audio-TTS 的样本要求：

| 项目 | 要求 |
| --- | --- |
| 格式 | WAV 16 bit、MP3、M4A |
| 时长 | 建议 10 到 20 秒，最长 60 秒 |
| 大小 | 不超过 10 MB |
| 采样率 | 不低于 16 kHz |
| 声道 | 单声道，或双声道但只使用第一声道 |
| 内容 | 至少 5 秒连续清晰朗读，停顿不超过 2 秒。不要背景音乐、噪声、第二个人声，也不要唱歌 |

可选参数：

- `language_hints`：帮助识别样本语种，只认数组第一个。和音频实际语种不符时，服务会忽略并自动检测。3.1 支持的值和合成时的 `language_hints` 相同。默认 `["zh"]`。
- `max_prompt_audio_length`：预处理后拿去复刻的最长秒数，3 到 30，默认 10。
- `enable_preprocess`：降噪、增强、音量整理。有噪声就开；环境干净就关，关了更像原声。默认 false。
- `enable_volume_normalization`：字符串 `"true"` 或 `"false"`，不是布尔。默认 `"false"`。

创建后不是立刻能用。用 `query_voice` 轮询，状态只有三种：

| status | 含义 |
| --- | --- |
| `DEPLOYING` | 还在处理，不能合成 |
| `OK` | 可以拿 `voice_id` 去合成 |
| `UNDEPLOYED` | 没通过，不能用 |

```json
{
  "model": "voice-enrollment",
  "input": { "action": "query_voice", "voice_id": "qwen-audio-3.1-tts-flash-myvoice-xxxxxx" }
}
```

返回里有 `status`、`target_model`、`gmt_create`、`resource_link`。合成前确认 `status` 是 `OK`，并且 `target_model` 是 `qwen-audio-3.1-tts-flash`。

列表：

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "list_voice",
    "prefix": "myvoice",
    "page_index": 0,
    "page_size": 10
  }
}
```

`prefix` 可省略。结果在 `output.voice_list[]`，每项有 `voice_id`、`gmt_create`、`gmt_modified`、`status`。这一页没有 `total_count`，某一页条数小于 `page_size` 就停。只保留 `voice_id` 以 `qwen-audio-3.1-tts-flash-` 开头的，别的模型的复刻音色混进来也不能用。

更新样本，ID 不变：

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "update_voice",
    "voice_id": "qwen-audio-3.1-tts-flash-myvoice-xxxxxx",
    "url": "https://cdn.example.com/new.wav"
  }
}
```

删除：

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "delete_voice",
    "voice_id": "qwen-audio-3.1-tts-flash-myvoice-xxxxxx"
  }
}
```

成功时 `output` 是空对象。删除不恢复免费次数。创建失败不计次数。免费额度和超期后的单价写在复刻用户指南里，当前文档写的是超出免费额度或超过 90 天有效期后按个计费，具体数字以该页为准，不要写死在代码里。

复刻音色合成时，`voice` 填返回的整段 `voice_id`，`model` 仍是 `qwen-audio-3.1-tts-flash`。`instruction` 同样可用。百炼不存显示名。要在页面上显示自己起的名字，得在本地数据库里用 `voice_id` 和 `list_voice` 的结果合并。

## 从零实现的顺序

1. 只做非流式 HTTP。短句、`longanhuan_v3.1`、`format: wav`。能下载 `output.audio.url` 并播放，Key 和空间就对了。
2. 加上 `X-DashScope-SSE: enable` 和 `format: pcm`。把每块 `audio.data` 按顺序写成一个 pcm 文件，再套 44 字节 wav 头（单声道、16 bit、24000 Hz）用系统播放器听。确认不是噪声，也不是静音。
3. 服务端把这些块转给浏览器，用 AudioContext 排队播放。这一步才做页面。代理要关掉缓冲。
4. 把 68 个系统音色做成静态配置，不要请求一个不存在的列表接口。每张卡片用同一句短文本打 SSE。
5. 需要更低延迟或边出字边合成时，再实现 WebSocket。二进制帧和 `sentence-synthesis` 一一对应。
6. 最后做复刻：公网 URL、`create_voice`、轮询到 `OK`、再用这个 `voice_id` 走第 2 步。

服务端最少三个调用：合成、创建音色、列出音色。查询和删除按产品需要加。系统音色表放在代码或 JSON 里。

## 排错

| 现象 | 原因 |
| --- | --- |
| 握手或 HTTP 401 / 403 | Key 不是北京的，或 WorkspaceId 和 Key 不在同一个空间 |
| `InvalidParameter`，并提到 engine 411 一类 | `voice` 不属于 `qwen-audio-3.1-tts-flash`。3.0 的 `*_v3.6`、千问 3 的 Cherry、别的模型复刻出来的 ID，都会这样 |
| 有字无声，或声音是噪声 | 把 pcm 当 mp3 播了，或把 WebSocket 二进制帧又做了一次 Base64 解码。也检查采样率是不是和请求的 24000 一致 |
| 流式请求一直没有首包 | 代理缓冲了 SSE。客户端要边读边解析，不能等整个 body |
| 播到一半停了 | 把 `finish_reason` 字符串 `"null"` 当成了结束，或在 `sentence-end` 就关了连接 |
| WebSocket 有 JSON 没有声音 | 没读二进制帧，或在 `task-started` 之前就发了文本，或没发 `finish-task` |
| 复刻创建成功但合成失败 | `status` 还是 `DEPLOYING`，或 `target_model` 和合成 `model` 不一致 |
| 复刻接口说拉不到音频 | URL 不是公网、有鉴权、是内网，或把 Base64 塞进了 `voice-enrollment` 的 `url` |
| 很快 429 或限流 | 北京 RPS 是 3。试听按钮要防连点 |
| 欠费类错误 | 北京账户没额度。看 `message`，不要重试风暴 |

错误体以 `code`、`message`、`request_id` 为准，对照 https://help.aliyun.com/zh/model-studio/error-code 。实现时把这三个字段返回给自己的日志，不要返回 Key。常见 `code` 包括 `InvalidApiKey`、`InvalidParameter`，以及限流、欠费一类字符串码。不要去对另一套产品的纯数字错误码表。
