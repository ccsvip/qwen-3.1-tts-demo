const LANGS = [
  ["", "自动"],
  ["zh", "中文"],
  ["en", "英语"],
  ["ja", "日语"],
  ["ko", "韩语"],
  ["fr", "法语"],
  ["de", "德语"],
  ["ru", "俄语"],
  ["pt", "葡萄牙语"],
  ["th", "泰语"],
  ["id", "印尼语"],
  ["vi", "越南语"],
  ["es", "西班牙语"],
  ["it", "意大利语"],
  ["ms", "马来语"],
  ["fil", "菲律宾语"],
  ["ar", "阿拉伯语"],
];

const PREVIEW = {
  zh: "你好，这是一段音色试听。",
  en: "Hello. This is a short voice preview.",
};

const state = {
  groups: [],
  cloned: [],
  groupId: "all",
  gender: "all",
  query: "",
  selected: localStorage.getItem("tts.voice") || "longanhuan_v3.1",
  remoteError: "",
  playToken: 0,
  abort: null,
  player: null,
};

const $ = (id) => document.getElementById(id);

function fillLanguages(select, includeAuto) {
  const options = includeAuto ? LANGS : LANGS.filter(([code]) => code);
  select.innerHTML = options
    .map(([code, label]) => `<option value="${code}">${label}</option>`)
    .join("");
  if (!includeAuto) select.value = "zh";
}

function setStatus(text, isError) {
  const node = $("status");
  node.textContent = text;
  node.classList.toggle("is-error", Boolean(isError));
}

function selectedVoice() {
  for (const group of state.groups) {
    const found = group.voices.find((voice) => voice.voice === state.selected);
    if (found) return { id: found.voice, name: found.name, preview: found.preview || "zh" };
  }
  const cloned = state.cloned.find((voice) => voice.voice_id === state.selected);
  if (cloned) return { id: cloned.voice_id, name: cloned.display_name, preview: "zh" };
  return { id: state.selected, name: state.selected, preview: "zh" };
}

function showCurrent() {
  const voice = selectedVoice();
  $("current-name").textContent = voice.name;
  $("current-id").textContent = voice.id;
}

function selectVoice(id) {
  state.selected = id;
  localStorage.setItem("tts.voice", id);
  showCurrent();
  renderVoices();
}

function matches(voice) {
  if (state.gender !== "all" && voice.gender !== state.gender) return false;
  const haystack = [voice.name, voice.voice, voice.trait, voice.scene, ...(voice.languages || [])]
    .join(" ")
    .toLowerCase();
  return haystack.includes(state.query);
}

function voiceCard(voice, id, extra) {
  const selected = id === state.selected ? " is-selected" : "";
  const article = document.createElement("article");
  article.className = `voice${selected}`;
  article.tabIndex = 0;
  article.innerHTML = `
    <header>
      <h3></h3>
      <span class="tag"></span>
    </header>
    <p class="trait"></p>
    <p class="id"></p>
    <footer>
      <span class="scene"></span>
    </footer>`;
  article.querySelector("h3").textContent = voice.name;
  article.querySelector(".tag").textContent = extra.tag;
  if (extra.wait) article.querySelector(".tag").classList.add("is-wait");
  article.querySelector(".trait").textContent = voice.trait || voice.scene || "";
  article.querySelector(".id").textContent = id;
  article.querySelector(".scene").textContent = voice.scene || "";
  const preview = document.createElement("button");
  preview.type = "button";
  preview.className = "ghost mini";
  preview.textContent = "试听";
  preview.disabled = extra.disabled;
  preview.addEventListener("click", (event) => {
    event.stopPropagation();
    selectVoice(id);
    const sample = PREVIEW[voice.preview || "zh"] || PREVIEW.zh;
    speak({
      text: sample,
      voice: id,
      instruction: "",
      language_hint: voice.preview === "en" ? "en" : "",
    });
  });
  if (extra.onDelete) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost mini";
    remove.textContent = "删除";
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      extra.onDelete();
    });
    article.querySelector("footer").append(remove);
  }
  article.querySelector("footer").append(preview);
  article.addEventListener("click", () => {
    if (!extra.disabled) selectVoice(id);
  });
  article.addEventListener("keydown", (event) => {
    if ((event.key === "Enter" || event.key === " ") && !extra.disabled) {
      event.preventDefault();
      selectVoice(id);
    }
  });
  return article;
}

function renderVoices() {
  const root = $("voices");
  root.innerHTML = "";
  const query = state.query;
  if (state.groupId === "cloned") {
    $("group-note").textContent = "复刻音色要等状态变成可用后才能合成。目标模型固定为 qwen-audio-3.1-tts-flash。";
    if (!state.cloned.length) {
      root.innerHTML = '<p class="empty">还没有复刻音色。</p>';
      return;
    }
    for (const voice of state.cloned) {
      const ready = ["OK", "SUCCESS"].includes(String(voice.status || "").toUpperCase());
      const label = { OK: "可用", SUCCESS: "可用", DEPLOYING: "部署中", FAILED: "失败", UNKNOWN: "状态未知" }[
        String(voice.status || "").toUpperCase()
      ] || voice.status || "状态未知";
      if (query && !`${voice.display_name} ${voice.voice_id} ${voice.prefix}`.toLowerCase().includes(query)) {
        continue;
      }
      root.append(voiceCard(
        {
          name: voice.display_name,
          trait: voice.prefix ? `前缀 ${voice.prefix}` : "",
          scene: voice.language_hint || "",
          preview: "zh",
        },
        voice.voice_id,
        {
          tag: label,
          wait: !ready,
          disabled: !ready,
          onDelete: () => removeClone(voice.voice_id, voice.display_name),
        },
      ));
    }
    if (!root.children.length) root.innerHTML = '<p class="empty">没有匹配的音色。</p>';
    return;
  }

  const groups = state.groupId === "all"
    ? state.groups
    : state.groups.filter((group) => group.id === state.groupId);
  const active = state.groups.find((group) => group.id === state.groupId);
  $("group-note").textContent = active ? active.note || "" : "系统音色来自 qwen-audio-3.1-tts-flash 官方列表，voice 值区分大小写。";
  let shown = 0;
  for (const group of groups) {
    for (const voice of group.voices) {
      if (!matches(voice)) continue;
      shown += 1;
      root.append(voiceCard(voice, voice.voice, { tag: voice.gender, disabled: false }));
    }
  }
  if (!shown) root.innerHTML = '<p class="empty">没有匹配的音色。</p>';
}

function renderGroupChips() {
  const root = $("groups");
  const items = [{ id: "all", name: "全部系统" }, ...state.groups.map((group) => ({ id: group.id, name: group.name })), { id: "cloned", name: "我的克隆" }];
  root.innerHTML = "";
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `chip${item.id === state.groupId ? " is-on" : ""}`;
    button.textContent = item.name;
    button.addEventListener("click", () => {
      state.groupId = item.id;
      renderGroupChips();
      renderVoices();
    });
    root.append(button);
  }
}

async function readError(response) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (data.message) return data.message;
  } catch (_error) {
    /* 非 JSON 错误 */
  }
  return `请求失败（${response.status}）`;
}

async function loadVoices() {
  const response = await fetch("/api/voices");
  if (!response.ok) throw new Error(await readError(response));
  const data = await response.json();
  state.groups = data.groups || [];
  state.cloned = data.cloned || [];
  state.remoteError = data.remote_error || "";
  const banner = $("remote-error");
  banner.hidden = !state.remoteError;
  banner.textContent = state.remoteError;
  const known = new Set(state.cloned.map((voice) => voice.voice_id));
  for (const group of state.groups) {
    for (const voice of group.voices) known.add(voice.voice);
  }
  if (!known.has(state.selected)) state.selected = "longanhuan_v3.1";
  renderGroupChips();
  renderVoices();
  showCurrent();
}

async function loadHealth() {
  const node = $("key-status");
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    if (data.has_api_key) {
      node.textContent = data.workspace_configured ? "已配置 API Key 和业务空间" : "已配置 API Key";
      node.classList.remove("is-bad");
    } else {
      node.textContent = "未配置 API Key，请填写 backend/.env";
      node.classList.add("is-bad");
    }
  } catch (_error) {
    node.textContent = "后端未就绪";
    node.classList.add("is-bad");
  }
}

class PcmPlayer {
  constructor() {
    this.ctx = new AudioContext();
    this.sampleRate = 24000;
    this.nextTime = 0;
    this.sources = [];
  }

  resume() {
    if (this.ctx.state === "suspended") return this.ctx.resume();
    return Promise.resolve();
  }

  pushBase64(b64) {
    const pad = b64.length % 4 === 0 ? "" : "=".repeat(4 - (b64.length % 4));
    const binary = atob(b64 + pad);
    const length = binary.length - (binary.length % 2);
    if (!length) return;
    const bytes = new Uint8Array(length);
    for (let index = 0; index < length; index += 1) bytes[index] = binary.charCodeAt(index);
    const view = new Int16Array(bytes.buffer);
    const audio = new Float32Array(view.length);
    for (let index = 0; index < view.length; index += 1) audio[index] = view[index] / 32768;
    const buffer = this.ctx.createBuffer(1, audio.length, this.sampleRate);
    buffer.copyToChannel(audio, 0);
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.ctx.destination);
    const now = this.ctx.currentTime;
    if (this.nextTime < now + 0.04) this.nextTime = now + 0.04;
    source.start(this.nextTime);
    this.nextTime += buffer.duration;
    this.sources.push(source);
  }

  stop() {
    for (const source of this.sources) {
      try { source.stop(); } catch (_error) { /* 已结束 */ }
    }
    this.sources = [];
    this.ctx.close();
  }

  remainingMs() {
    return Math.max(0, (this.nextTime - this.ctx.currentTime) * 1000);
  }
}

function stopPlayback() {
  state.playToken += 1;
  if (state.abort) {
    state.abort.abort();
    state.abort = null;
  }
  if (state.player) {
    state.player.stop();
    state.player = null;
  }
}

function parseSseBlock(block) {
  let event = "message";
  const data = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!data.length) return null;
  return { event, data: JSON.parse(data.join("\n")) };
}

async function stream(body, handlers, signal) {
  const response = await fetch("/api/tts/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) throw new Error(await readError(response));
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    let split = buffer.indexOf("\n\n");
    while (split >= 0) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      if (block.trim()) handlers(parseSseBlock(block));
      split = buffer.indexOf("\n\n");
    }
  }
}

function formBody(overrides) {
  return {
    text: $("text").value.trim(),
    voice: state.selected,
    rate: Number($("rate").value),
    volume: Number($("volume").value),
    pitch: Number($("pitch").value),
    instruction: $("instruction").value.trim(),
    language_hint: $("language").value,
    ...overrides,
  };
}

async function speak(overrides) {
  const payload = formBody(overrides);
  if (!payload.text) {
    setStatus("请输入要合成的文字", true);
    return;
  }
  stopPlayback();
  const token = state.playToken;
  const player = new PcmPlayer();
  const resumePromise = player.resume();
  state.player = player;
  const abort = new AbortController();
  state.abort = abort;
  setStatus("正在连接…");
  $("sentence").textContent = "";
  $("usage").textContent = "";
  let heard = false;
  try {
    await resumePromise;
    await stream(payload, (event) => {
      if (!event || token !== state.playToken) return;
      if (event.event === "meta" && event.data.sample_rate) player.sampleRate = event.data.sample_rate;
      if (event.event === "sentence") $("sentence").textContent = event.data.text || "";
      if (event.event === "audio" && event.data.pcm) {
        player.pushBase64(event.data.pcm);
        if (!heard) {
          heard = true;
          setStatus("正在播放…");
        }
      }
      if (event.event === "usage" || event.event === "done") {
        const usage = event.data.usage || {};
        const parts = [];
        if (usage.input_tokens != null) parts.push(`输入 ${usage.input_tokens} token`);
        if (usage.output_tokens != null) parts.push(`输出 ${usage.output_tokens} token`);
        if (usage.characters != null) parts.push(`${usage.characters} 字`);
        if (parts.length) $("usage").textContent = parts.join(" · ");
      }
      if (event.event === "error") throw new Error(event.data.message || "合成失败");
    }, abort.signal);
    if (token !== state.playToken) return;
    await new Promise((resolve) => setTimeout(resolve, player.remainingMs() + 80));
    if (token === state.playToken) setStatus(heard ? "播放结束" : "没有收到音频", !heard);
  } catch (error) {
    if (token !== state.playToken || error.name === "AbortError") return;
    setStatus(error.message || "合成失败", true);
  }
}

async function removeClone(id, name) {
  if (!window.confirm(`删除「${name}」？云端音色删除后不能恢复。`)) return;
  const response = await fetch(`/api/voices/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!response.ok) {
    $("clone-message").textContent = await readError(response);
    $("clone-message").classList.add("is-error");
    return;
  }
  if (state.selected === id) state.selected = "longanhuan_v3.1";
  await loadVoices();
}

function bindSliders() {
  for (const [id, output, digits] of [["rate", "rate-out", 1], ["volume", "volume-out", 0], ["pitch", "pitch-out", 1]]) {
    const input = $(id);
    const write = () => { $(output).textContent = Number(input.value).toFixed(digits); };
    input.addEventListener("input", write);
    write();
  }
}

function bindText() {
  const area = $("text");
  const saved = sessionStorage.getItem("tts.draft");
  if (saved) area.value = saved;
  const write = () => {
    $("count").textContent = String(area.value.length);
    sessionStorage.setItem("tts.draft", area.value);
  };
  area.addEventListener("input", write);
  write();
}

$("speak").addEventListener("click", () => speak());
$("stop").addEventListener("click", () => {
  stopPlayback();
  setStatus("已停止");
});
$("reload").addEventListener("click", () => loadVoices().catch((error) => setStatus(error.message, true)));
$("search").addEventListener("input", (event) => {
  state.query = event.target.value.trim().toLowerCase();
  renderVoices();
});
for (const button of $("genders").querySelectorAll("button")) {
  button.addEventListener("click", () => {
    state.gender = button.dataset.gender;
    for (const item of $("genders").querySelectorAll("button")) item.classList.toggle("is-on", item === button);
    renderVoices();
  });
}
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    speak();
  }
});

$("clone-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = $("clone-message");
  const button = $("clone-submit");
  message.classList.remove("is-error");
  message.textContent = "正在创建音色…";
  button.disabled = true;
  const form = new FormData();
  form.set("prefix", $("clone-prefix").value.trim());
  form.set("display_name", $("clone-name").value.trim());
  form.set("language", $("clone-language").value);
  if ($("clone-url").value.trim()) form.set("url", $("clone-url").value.trim());
  if ($("clone-file").files[0]) form.set("file", $("clone-file").files[0]);
  try {
    const response = await fetch("/api/voices/clone", { method: "POST", body: form });
    const data = response.ok ? await response.json() : null;
    if (!response.ok) throw new Error(await readError(response));
    message.textContent = `已创建 ${data.voice_id}（${data.status}）`;
    state.groupId = "cloned";
    state.selected = data.voice_id;
    localStorage.setItem("tts.voice", data.voice_id);
    await loadVoices();
  } catch (error) {
    message.textContent = error.message;
    message.classList.add("is-error");
  } finally {
    button.disabled = false;
  }
});

fillLanguages($("language"), true);
fillLanguages($("clone-language"), false);
bindSliders();
bindText();
showCurrent();
loadHealth();
loadVoices().catch((error) => setStatus(error.message, true));
