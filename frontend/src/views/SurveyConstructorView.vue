<template>
  <div class="constructor-view">
    <div class="constructor-content" :class="{ blurred: showJsonHelp }">
      <div class="card">
        <h2>Конструктор тестов</h2>
        <p>Соберите структуру теста: вопрос, варианты ответов и вес по каждому фактору 5-угольника.</p>
        <div class="top-row">
          <label class="field">
            <span>Название конструктора</span>
            <input v-model.trim="constructorTitle" class="input" type="text" placeholder="Например: Оценка стресса команды" />
          </label>
          <div class="top-actions">
            <button type="button" class="btn" @click="downloadJsonTemplate">Скачать шаблон JSON</button>
            <button type="button" class="btn" @click="openImportDialog">Импортировать из JSON</button>
            <button type="button" class="btn" @click="showJsonHelp = true">Инструкция по JSON</button>
            <input ref="importInputRef" type="file" accept="application/json,.json" class="hidden-file" @change="importFromJson" />
          </div>
        </div>
        <p v-if="saveMessage" class="save-message">{{ saveMessage }}</p>
      </div>

      <div class="workspace card">
        <aside class="panel left">
          <h3>Компоненты</h3>
          <button
            v-for="item in palette"
            :key="item.type"
            class="palette-item"
            type="button"
            draggable="true"
            @dragstart="onPaletteDragStart(item.type, $event)"
            @click="addBlock(item.type)"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ item.hint }}</span>
          </button>
        </aside>

        <section class="canvas-wrap">
          <h3>Поле конструктора</h3>
          <div class="canvas" @dragover.prevent @drop="onDrop">
            <div v-if="!blocks.length" class="empty">Перенесите компоненты из левой панели или нажмите по ним.</div>
            <button
              v-for="(block, idx) in blocks"
              :key="block.id"
              type="button"
              class="canvas-block"
              :class="{ selected: selectedBlockId === block.id }"
              draggable="true"
              @dragstart="onBlockDragStart(block.id, $event)"
              @dragover.prevent
              @drop="onBlockDrop(block.id, $event)"
              @click="selectedBlockId = block.id"
            >
              <div class="meta-line">{{ idx + 1 }}. {{ blockTypeLabel(block.type) }}</div>
              <div class="text-line">{{ blockPreview(block) }}</div>
            </button>
          </div>
        </section>

        <aside class="panel right">
          <h3>Свойства</h3>
          <div v-if="selectedBlock" class="props-form">
            <label class="field">
              <span>Текст</span>
              <textarea
                v-if="selectedBlock.type === 'label' || selectedBlock.type === 'message'"
                :value="selectedBlock.text"
                class="input"
                rows="3"
                @input="updateSelected('text', ($event.target as HTMLTextAreaElement).value)"
              />
              <input
                v-else
                :value="selectedBlock.text"
                class="input"
                type="text"
                @input="updateSelected('text', ($event.target as HTMLInputElement).value)"
              />
            </label>

            <label v-if="selectedBlock.type === 'input'" class="field">
              <span>Placeholder</span>
              <input
                :value="selectedBlock.placeholder"
                class="input"
                type="text"
                @input="updateSelected('placeholder', ($event.target as HTMLInputElement).value)"
              />
            </label>

            <template v-if="selectedBlock.type === 'radio'">
              <label class="field">
                <span>Параметр (фактор)</span>
                <select
                  :value="selectedBlock.factorKey"
                  class="input"
                  @change="updateSelected('factorKey', ($event.target as HTMLSelectElement).value)"
                >
                  <option v-for="f in factors" :key="f.key" :value="f.key">{{ f.label }}</option>
                </select>
              </label>
              <label class="field">
                <span>Баллы (+/-)</span>
                <input
                  :value="selectedBlock.points"
                  class="input"
                  type="number"
                  step="0.1"
                  min="-5"
                  max="5"
                  @input="updateSelected('points', Number(($event.target as HTMLInputElement).value || 0))"
                />
              </label>
            </template>

            <div class="actions">
              <button type="button" class="btn danger" @click="removeSelected">Удалить элемент</button>
            </div>
          </div>
          <div v-else class="empty">Выберите элемент в центре, чтобы редактировать свойства.</div>
        </aside>
      </div>

      <div class="bottom-actions card">
        <button type="button" class="btn" :disabled="!history.length" @click="undoLast">Отменить</button>
        <button type="button" class="btn primary" :disabled="saving" @click="saveConstructor">
          {{ saving ? "Сохраняем..." : "Сохранить" }}
        </button>
      </div>
    </div>

    <div v-if="showJsonHelp" class="help-overlay">
      <div class="help-modal">
        <button type="button" class="modal-close" aria-label="Закрыть" @click="showJsonHelp = false">×</button>
        <h3>Инструкция по JSON</h3>
        <p>Для импорта используйте JSON с полями <code>title</code>, <code>template</code>, <code>version</code> и <code>questions</code>.</p>
        <p>Каждый вопрос должен содержать:</p>
        <ul>
          <li><code>id</code> — уникальный идентификатор вопроса</li>
          <li><code>text</code> — текст вопроса</li>
          <li><code>question_type</code> — сейчас используем <code>TEXT</code></li>
          <li><code>meta.options</code> — массив вариантов для радиокнопок</li>
          <li><code>meta.ui_blocks</code> — дополнительные блоки <code>input</code>/<code>message</code></li>
        </ul>
        <p>Допустимые значения поля <code>factor</code> в <code>meta.options</code>:</p>
        <ul>
          <li><code>empathy</code> — Эмпатия</li>
          <li><code>stress_mgmt</code> — Стрессоустойчивость</li>
          <li><code>collaboration</code> — Командность</li>
          <li><code>focus</code> — Фокус</li>
          <li><code>learning</code> — Обучаемость</li>
        </ul>
        <p>Пример структуры:</p>
        <pre class="json-sample">{
  "title": "Оценка самочувствия",
  "template": "LIKERT",
  "version": 1,
  "questions": [
    {
      "id": "q1",
      "text": "Как вы оцениваете нагрузку?",
      "question_type": "TEXT",
      "meta": {
        "source": "builder_v1",
        "options": [
          { "id": "q1_o1", "text": "Легко", "factor": "stress_mgmt", "points": 2 },
          { "id": "q1_o2", "text": "Нормально", "factor": "stress_mgmt", "points": 1 }
        ],
        "ui_blocks": [
          { "type": "message", "text": "Выберите один вариант." }
        ]
      }
    }
  ]
}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { api } from "../api/client";

type BlockType = "label" | "input" | "radio" | "message";
type Block = {
  id: string;
  type: BlockType;
  text: string;
  placeholder?: string;
  factorKey?: string;
  points?: number;
};

const palette: Array<{ type: BlockType; title: string; hint: string }> = [
  { type: "label", title: "Label (вопрос)", hint: "Текст вопроса" },
  { type: "input", title: "Поле ввода", hint: "Свободный ответ" },
  { type: "radio", title: "Радиокнопка", hint: "Вариант ответа с баллами" },
  { type: "message", title: "Текстовое сообщение", hint: "Подсказка или инструкция" },
];

const factors = [
  { key: "empathy", label: "Эмпатия" },
  { key: "stress_mgmt", label: "Стрессоустойчивость" },
  { key: "collaboration", label: "Командность" },
  { key: "focus", label: "Фокус" },
  { key: "learning", label: "Обучаемость" },
];

const constructorTitle = ref("Новый тест");
const blocks = ref<Block[]>([]);
const history = ref<string[]>([]);
const selectedBlockId = ref<string | null>(null);
const draggedType = ref<BlockType | null>(null);
const draggedBlockId = ref<string | null>(null);
const importInputRef = ref<HTMLInputElement | null>(null);
const saveMessage = ref("");
const saving = ref(false);
const showJsonHelp = ref(false);

const selectedBlock = computed(() => blocks.value.find((b) => b.id === selectedBlockId.value) ?? null);

function blockTypeLabel(type: BlockType) {
  if (type === "label") return "Вопрос";
  if (type === "input") return "Поле ввода";
  if (type === "radio") return "Вариант ответа";
  return "Текстовое сообщение";
}

function blockPreview(block: Block) {
  if (block.type === "radio") {
    const factor = factors.find((x) => x.key === block.factorKey)?.label ?? "фактор";
    return `${block.text || "Вариант"} | ${factor}: ${block.points ?? 0}`;
  }
  if (block.type === "input") return block.text || block.placeholder || "Текстовое поле";
  return block.text || "Пустой элемент";
}

function makeDefaultBlock(type: BlockType): Block {
  const id = `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  if (type === "label") return { id, type, text: "Новый вопрос" };
  if (type === "input") return { id, type, text: "Ответ сотрудника", placeholder: "Введите ответ" };
  if (type === "radio") return { id, type, text: "Вариант ответа", factorKey: "stress_mgmt", points: 1 };
  return { id, type, text: "Текстовое сообщение" };
}

function pushHistorySnapshot() {
  history.value.push(JSON.stringify(blocks.value));
  if (history.value.length > 80) history.value.shift();
}

function addBlock(type: BlockType) {
  addBlockAt(type, blocks.value.length);
}

function addBlockAt(type: BlockType, index: number) {
  pushHistorySnapshot();
  const block = makeDefaultBlock(type);
  const list = [...blocks.value];
  const safeIndex = Math.max(0, Math.min(index, list.length));
  list.splice(safeIndex, 0, block);
  blocks.value = list;
  selectedBlockId.value = block.id;
  saveMessage.value = "";
}

function onPaletteDragStart(type: BlockType, event: DragEvent) {
  draggedType.value = type;
  draggedBlockId.value = null;
  if (event.dataTransfer) event.dataTransfer.setData("text/plain", type);
}

function onBlockDragStart(blockId: string, event: DragEvent) {
  draggedBlockId.value = blockId;
  draggedType.value = null;
  if (event.dataTransfer) event.dataTransfer.setData("text/block-id", blockId);
}

function moveBlock(blockId: string, targetIndex: number) {
  const fromIndex = blocks.value.findIndex((x) => x.id === blockId);
  if (fromIndex < 0) return;
  const safeTarget = Math.max(0, Math.min(targetIndex, blocks.value.length));
  pushHistorySnapshot();
  const list = [...blocks.value];
  const [item] = list.splice(fromIndex, 1);
  const insertIndex = Math.max(0, Math.min(fromIndex < safeTarget ? safeTarget - 1 : safeTarget, list.length));
  list.splice(insertIndex, 0, item);
  blocks.value = list;
  selectedBlockId.value = item.id;
  saveMessage.value = "";
}

function onBlockDrop(targetBlockId: string, event: DragEvent) {
  event.preventDefault();
  const blockId = event.dataTransfer?.getData("text/block-id") || draggedBlockId.value;
  if (blockId) {
    const targetIndex = blocks.value.findIndex((x) => x.id === targetBlockId);
    if (targetIndex >= 0) moveBlock(blockId, targetIndex);
    draggedBlockId.value = null;
    return;
  }

  const transferType = (event.dataTransfer?.getData("text/plain") as BlockType) || draggedType.value;
  if (!transferType) return;
  const targetIndex = blocks.value.findIndex((x) => x.id === targetBlockId);
  addBlockAt(transferType, targetIndex >= 0 ? targetIndex : blocks.value.length);
  draggedType.value = null;
}

function onDrop(event: DragEvent) {
  const blockId = event.dataTransfer?.getData("text/block-id") || draggedBlockId.value;
  if (blockId) {
    moveBlock(blockId, blocks.value.length);
    draggedBlockId.value = null;
    return;
  }
  const transferType = (event.dataTransfer?.getData("text/plain") as BlockType) || draggedType.value;
  if (!transferType) return;
  addBlockAt(transferType, blocks.value.length);
  draggedType.value = null;
}

function updateSelected(key: keyof Block, value: string | number) {
  const block = selectedBlock.value;
  if (!block) return;
  pushHistorySnapshot();
  const idx = blocks.value.findIndex((x) => x.id === block.id);
  if (idx < 0) return;
  blocks.value[idx] = { ...blocks.value[idx], [key]: value };
  saveMessage.value = "";
}

function removeSelected() {
  if (!selectedBlock.value) return;
  pushHistorySnapshot();
  blocks.value = blocks.value.filter((x) => x.id !== selectedBlock.value?.id);
  selectedBlockId.value = blocks.value[0]?.id ?? null;
  saveMessage.value = "";
}

function undoLast() {
  const prev = history.value.pop();
  if (!prev) return;
  blocks.value = JSON.parse(prev) as Block[];
  if (!selectedBlockId.value || !blocks.value.find((x) => x.id === selectedBlockId.value)) {
    selectedBlockId.value = blocks.value[0]?.id ?? null;
  }
}

function downloadJsonTemplate() {
  const payload = {
    title: "Шаблон теста",
    template: "LIKERT",
    version: 1,
    questions: [
      {
        id: "q1",
        text: "Как вы оцениваете рабочую нагрузку за последнюю неделю?",
        question_type: "TEXT",
        meta: {
          source: "builder_v1",
          options: [
            { id: "q1_o1", text: "Очень комфортно", factor: "stress_mgmt", points: 2 },
            { id: "q1_o2", text: "Скорее комфортно", factor: "stress_mgmt", points: 1 },
            { id: "q1_o3", text: "Скорее тяжело", factor: "stress_mgmt", points: -1 },
            { id: "q1_o4", text: "Очень тяжело", factor: "stress_mgmt", points: -2 },
          ],
          ui_blocks: [{ type: "message", text: "Выберите один вариант ответа." }],
        },
      },
    ],
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "survey-template.json";
  a.click();
  URL.revokeObjectURL(url);
}

function openImportDialog() {
  importInputRef.value?.click();
}

async function importFromJson(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    const raw = await file.text();
    const parsed = JSON.parse(raw);
    const title = typeof parsed?.title === "string" ? parsed.title : constructorTitle.value;
    const sourceQuestions = Array.isArray(parsed?.questions) ? parsed.questions : [];
    if (!sourceQuestions.length) {
      saveMessage.value = "Импорт не выполнен: в JSON нет массива questions.";
      return;
    }

    const nextBlocks: Block[] = [];
    for (const q of sourceQuestions) {
      const labelText = typeof q?.text === "string" ? q.text : "Вопрос";
      nextBlocks.push(makeDefaultBlock("label"));
      nextBlocks[nextBlocks.length - 1].text = labelText;

      const uiBlocks = Array.isArray(q?.meta?.ui_blocks) ? q.meta.ui_blocks : [];
      for (const u of uiBlocks) {
        if (u?.type === "input") {
          const b = makeDefaultBlock("input");
          b.text = typeof u?.text === "string" ? u.text : b.text;
          b.placeholder = typeof u?.placeholder === "string" ? u.placeholder : b.placeholder;
          nextBlocks.push(b);
        } else if (u?.type === "message") {
          const b = makeDefaultBlock("message");
          b.text = typeof u?.text === "string" ? u.text : b.text;
          nextBlocks.push(b);
        }
      }

      const options = Array.isArray(q?.meta?.options) ? q.meta.options : [];
      for (const o of options) {
        const b = makeDefaultBlock("radio");
        b.text = typeof o?.text === "string" ? o.text : b.text;
        b.factorKey = typeof o?.factor === "string" ? o.factor : b.factorKey;
        b.points = Number(o?.points ?? b.points ?? 0);
        nextBlocks.push(b);
      }
    }

    pushHistorySnapshot();
    constructorTitle.value = title;
    blocks.value = nextBlocks;
    selectedBlockId.value = nextBlocks[0]?.id ?? null;
    saveMessage.value = "JSON импортирован.";
  } catch (_e) {
    saveMessage.value = "Не удалось импортировать JSON. Проверьте формат файла.";
  } finally {
    input.value = "";
  }
}

function buildPayload() {
  const questions: Array<{
    id: string;
    text: string;
    question_type: "TEXT";
    meta: {
      source: string;
      options: Array<{ id: string; text: string; factor: string; points: number }>;
      ui_blocks: Array<{ type: string; text: string; placeholder?: string }>;
    };
  }> = [];

  let qIndex = 0;
  let current:
    | {
        id: string;
        text: string;
        options: Array<{ id: string; text: string; factor: string; points: number }>;
        ui_blocks: Array<{ type: string; text: string; placeholder?: string }>;
      }
    | null = null;

  const flushCurrent = () => {
    if (!current) return;
    questions.push({
      id: current.id,
      text: current.text,
      question_type: "TEXT",
      meta: {
        source: "builder_v1",
        options: current.options,
        ui_blocks: current.ui_blocks,
      },
    });
  };

  for (const block of blocks.value) {
    if (block.type === "label") {
      flushCurrent();
      qIndex += 1;
      current = {
        id: `q${qIndex}`,
        text: block.text.trim(),
        options: [],
        ui_blocks: [],
      };
      continue;
    }
    if (!current) continue;
    if (block.type === "radio") {
      current.options.push({
        id: `${current.id}_o${current.options.length + 1}`,
        text: block.text.trim(),
        factor: block.factorKey || "stress_mgmt",
        points: Number(block.points ?? 0),
      });
    } else if (block.type === "input") {
      current.ui_blocks.push({ type: "input", text: block.text.trim(), placeholder: block.placeholder || "" });
    } else if (block.type === "message") {
      current.ui_blocks.push({ type: "message", text: block.text.trim() });
    }
  }
  flushCurrent();

  return questions.filter((q) => q.text.length > 0);
}

async function saveConstructor() {
  saveMessage.value = "";
  const title = constructorTitle.value.trim();
  if (!title) {
    saveMessage.value = "Укажите название конструктора.";
    return;
  }
  const questions = buildPayload();
  if (!questions.length) {
    saveMessage.value = "Добавьте хотя бы один вопрос (Label).";
    return;
  }
  saving.value = true;
  try {
    await api.post("/surveys", {
      title,
      template: "LIKERT",
      version: 1,
      questions,
    });
    saveMessage.value = "Конструктор теста успешно сохранен.";
    history.value = [];
  } catch (_e) {
    saveMessage.value = "Не удалось сохранить тест. Проверьте структуру и попробуйте снова.";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.constructor-view { display: grid; gap: 1rem; }
.constructor-content {
  display: grid;
  gap: 1rem;
}
.constructor-content.blurred {
  filter: blur(3px);
  pointer-events: none;
  user-select: none;
}
.constructor-view .card { margin-bottom: 0; }
.top-row {
  margin-top: 0.7rem;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.6rem;
  align-items: end;
}
.top-actions {
  display: flex;
  gap: 0.45rem;
  align-items: center;
}
.hidden-file {
  display: none;
}
.workspace {
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  gap: 0.8rem;
  min-height: 560px;
}
.panel {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0.75rem;
  background: #f8fafc;
}
.panel h3, .canvas-wrap h3 { margin-top: 0; margin-bottom: 0.6rem; }
.palette-item {
  width: 100%;
  text-align: left;
  margin-bottom: 0.45rem;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  padding: 0.5rem 0.55rem;
  cursor: grab;
  display: grid;
  gap: 0.15rem;
}
.palette-item span { color: #64748b; font-size: 0.82rem; }
.canvas-wrap { display: grid; grid-template-rows: auto 1fr; gap: 0.4rem; }
.canvas {
  border: 1px dashed #94a3b8;
  border-radius: 12px;
  padding: 0.7rem;
  display: grid;
  gap: 0.45rem;
  align-content: start;
  min-height: 480px;
  background: #fff;
}
.canvas-block {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  text-align: left;
  padding: 0.45rem 0.55rem;
  cursor: pointer;
}
.canvas-block.selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.14);
}
.meta-line { font-size: 0.78rem; color: #64748b; }
.text-line { font-size: 0.9rem; color: #0f172a; }
.props-form { display: grid; gap: 0.55rem; }
.field { display: grid; gap: 0.25rem; }
.field span { font-size: 0.84rem; color: #475569; }
.input {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0.45rem 0.55rem;
  font-size: 0.92rem;
}
.actions { display: flex; justify-content: flex-start; margin-top: 0.2rem; }
.bottom-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
}
.btn {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  padding: 0.45rem 0.8rem;
  cursor: pointer;
}
.btn.primary {
  background: #2563eb;
  border-color: #1d4ed8;
  color: #fff;
}
.btn.danger {
  background: #fff5f5;
  border-color: #fecaca;
  color: #b91c1c;
}
.empty {
  color: #64748b;
  font-size: 0.9rem;
}
.save-message {
  margin: 0.55rem 0 0;
  color: #0f766e;
  font-size: 0.9rem;
  align-self: center;
}
.help-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 1rem;
}
.help-modal {
  width: min(760px, 95vw);
  max-height: 86vh;
  overflow: auto;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.2);
  padding: 1rem 1.1rem;
  position: relative;
}
.help-modal h3 { margin-top: 0; margin-bottom: 0.5rem; }
.help-modal p { margin: 0.35rem 0; color: #334155; }
.help-modal ul { margin: 0.35rem 0 0.6rem; padding-left: 1.1rem; }
.json-sample {
  margin: 0.45rem 0 0;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 10px;
  padding: 0.65rem;
  font-size: 0.8rem;
  white-space: pre-wrap;
}
.modal-close {
  position: absolute;
  top: 0.5rem;
  right: 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  width: 28px;
  height: 28px;
  background: #fff;
  cursor: pointer;
  font-size: 1.05rem;
  line-height: 1;
}
@media (max-width: 1320px) {
  .workspace { grid-template-columns: 250px 1fr; }
  .panel.right { grid-column: 1 / -1; }
}
@media (max-width: 900px) {
  .workspace { grid-template-columns: 1fr; }
  .top-row { grid-template-columns: 1fr; }
  .top-actions { flex-wrap: wrap; }
}
</style>
