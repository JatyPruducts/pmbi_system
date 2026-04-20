<template>
  <div>
    <div class="card">
      <h2>Конструктор дашбордов</h2>
      <p>
        Выберите таблицу-источник, применяйте операторы и функции сверху, просматривайте результат в центре.
        Справа — история операций и сохранение конфигурации.
      </p>
    </div>

    <div class="card source-box">
      <h3>1) Источник данных</h3>
      <div class="line">
        <select v-model="baseTable" class="inp sm">
          <option v-for="t in meta.tables" :key="t.name" :value="t.name">{{ t.name }}</option>
        </select>
        <button type="button" class="btn" @click="startWorkspace">Открыть конструктор</button>
      </div>
      <p v-if="msg" class="ok">{{ msg }}</p>
    </div>

    <div v-if="workspaceOpened" class="builder-shell">
      <div class="card workspace">
        <div class="toolbar top-toolbar">
          <button class="btn small" type="button" @click="toggleTool('selectColumns')">SELECT</button>
          <button class="btn small" type="button" @click="toggleTool('join')">JOIN</button>
          <button class="btn small" type="button" @click="toggleTool('select')">Функция</button>
          <button class="btn small" type="button" @click="toggleTool('group')">GROUP BY</button>
          <button class="btn small" type="button" @click="toggleTool('filter')">FILTER</button>
          <button class="btn small" type="button" @click="toggleTool('order')">ORDER BY</button>
          <button class="btn small" type="button" @click="toggleTool('limit')">LIMIT</button>
          <button class="btn small danger" type="button" @click="resetBuilder">Сбросить</button>
        </div>

        <div v-if="activeTool" class="tool-panel">
          <template v-if="activeTool === 'selectColumns'">
            <span class="tool-label">SELECT</span>
            <span class="muted">Колонки с галочками формируют SELECT *</span>
            <div class="checkbox-grid">
              <label v-for="field in queryFields" :key="field" class="checkbox-item">
                <input
                  type="checkbox"
                  :checked="selectedColumns[field] !== false"
                  @change="toggleSelectColumn(field, ($event.target as HTMLInputElement).checked)"
                />
                <span>{{ field }}</span>
              </label>
            </div>
          </template>
          <template v-if="activeTool === 'join'">
            <span class="tool-label">JOIN</span>
            <select v-model="joinDraft.kind" class="inp mini">
              <option value="inner">INNER</option>
              <option value="left">LEFT</option>
            </select>
            <select v-model="joinDraft.table" class="inp">
              <option v-for="t in joinCandidates" :key="t" :value="t">{{ t }}</option>
            </select>
            <button class="btn small" type="button" @click="addJoin">Применить</button>
          </template>

          <template v-else-if="activeTool === 'select'">
            <span class="tool-label">Функция</span>
            <select v-model="selectDraft.agg" class="inp mini">
              <option v-for="agg in meta.aggregations" :key="agg" :value="agg">{{ agg }}</option>
            </select>
            <select v-model="selectDraft.field" class="inp">
              <option v-for="f in operationFields" :key="f" :value="f">{{ f }}</option>
            </select>
            <input v-model="selectDraft.alias" class="inp mini" placeholder="alias" />
            <button class="btn small" type="button" @click="addSelect">Применить</button>
          </template>

          <template v-else-if="activeTool === 'group'">
            <span class="tool-label">GROUP BY</span>
            <select v-model="groupByDraft" class="inp">
              <option v-for="f in operationFields" :key="f" :value="f">{{ f }}</option>
            </select>
            <button class="btn small" type="button" @click="addGroupBy">Применить</button>
          </template>

          <template v-else-if="activeTool === 'filter'">
            <span class="tool-label">FILTER</span>
            <select v-model="filterDraft.field" class="inp">
              <option v-for="f in operationFields" :key="f" :value="f">{{ f }}</option>
            </select>
            <select v-model="filterDraft.operator" class="inp mini">
              <option v-for="op in meta.operators" :key="op" :value="op">{{ operatorLabels[op] ?? op }}</option>
            </select>
            <template v-if="filterDraft.operator === 'between'">
              <input v-model="filterDraft.valueFrom" class="inp mini" placeholder="from" />
              <input v-model="filterDraft.valueTo" class="inp mini" placeholder="to" />
            </template>
            <template v-else-if="filterDraft.operator === 'in'">
              <input
                v-model="filterDraftListInput"
                class="inp mini"
                placeholder="value"
                @keyup.enter="addFilterListValue"
              />
              <button class="btn small" type="button" @click="addFilterListValue">Добавить</button>
              <div class="chips">
                <span v-for="(v, i) in filterDraft.valueList" :key="`${v}-${i}`" class="chip">
                  {{ v }}
                  <button type="button" class="chip-x" @click="removeFilterListValue(i)">x</button>
                </span>
              </div>
            </template>
            <template v-else-if="filterDraft.operator === 'is_null'">
              <label class="inline-checkbox">
                <input v-model="filterDraft.isNull" type="checkbox" />
                <span>Проверка на NULL</span>
              </label>
            </template>
            <template v-else>
              <input v-model="filterDraft.valueInput" class="inp mini" placeholder="value" />
            </template>
            <button class="btn small" type="button" @click="addFilter">Применить</button>
          </template>

          <template v-else-if="activeTool === 'order'">
            <span class="tool-label">ORDER BY</span>
            <select v-model="orderDraft.field" class="inp">
              <option v-for="f in operationFields" :key="f" :value="f">{{ f }}</option>
            </select>
            <select v-model="orderDraft.direction" class="inp mini">
              <option value="asc">ASC</option>
              <option value="desc">DESC</option>
            </select>
            <button class="btn small" type="button" @click="addOrderBy">Применить</button>
          </template>

          <template v-else-if="activeTool === 'limit'">
            <span class="tool-label">LIMIT</span>
            <input v-model.number="limit" type="number" min="1" max="500" class="inp mini" />
          </template>
        </div>

        <div class="table-wrap">
          <table class="result-table">
            <thead>
              <tr>
                <th v-for="c in previewColumns" :key="c">{{ c }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in previewRows" :key="idx">
                <td v-for="c in previewColumns" :key="c">{{ row[c] ?? "—" }}</td>
              </tr>
              <tr v-if="!previewRows.length">
                <td :colspan="Math.max(previewColumns.length, 1)">Нет данных</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="muted">Результат обновляется автоматически после добавления/изменения операции.</p>
      </div>

      <div class="card sidepanel">
        <h3>История операций</h3>
        <ul class="history">
          <li><strong>FROM</strong> {{ baseTable }}</li>
          <li>SELECT columns: {{ selectedFieldCount }}</li>
          <li v-for="h in operationHistory" :key="h.id" class="history-row">
            <button class="history-link" type="button" @click="openHistoryAction(h.id)">
              {{ historyLabel(h.id, h.type) }}
            </button>
            <button class="btn tiny danger" type="button" @click="removeHistoryAction(h.id, h.type)">x</button>
          </li>
          <li>LIMIT {{ limit }}</li>
        </ul>

        <h3>SQL</h3>
        <button class="btn" type="button" :disabled="!sqlPreview" @click="downloadSql">
          Скачать SQL
        </button>
        <p class="muted" v-if="!sqlPreview">SQL появится после выполнения предпросмотра.</p>

        <h3>Сохранение</h3>
        <input v-model="name" class="inp" placeholder="Имя конфигурации" />
        <button class="btn" type="button" @click="save">Сохранить</button>

        <h3>Сохранённые</h3>
        <ul class="history">
          <li v-for="l in layouts" :key="l.id">
            {{ l.name }} ({{ l.widgets?.builder?.base_table ?? "n/a" }})
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "../api/client";

type MetaTable = { name: string; columns: string[] };
type BuilderJoin = { id: string; table: string; kind: "inner" | "left" };
type BuilderGroup = { id: string; field: string };
type BuilderSelect = { id: string; field: string; agg: string; alias: string };
type BuilderFilter = {
  id: string;
  field: string;
  operator: string;
  valueInput: string;
  valueFrom: string;
  valueTo: string;
  valueList: string[];
  isNull: boolean;
};
type BuilderOrder = { id: string; field: string; direction: "asc" | "desc" };
type HistoryActionType = "join" | "select" | "group" | "filter" | "order";
type HistoryAction = { id: string; type: HistoryActionType };

const defaultMetaTables: MetaTable[] = [
  { name: "users", columns: ["id", "email", "hashed_password", "full_name", "role", "is_active", "created_at"] },
  { name: "employees", columns: ["id", "user_id", "org_unit_id", "position_id", "manager_id", "external_id", "hire_date", "left_at"] },
  { name: "org_units", columns: ["id", "name", "code", "parent_id", "created_at"] },
  { name: "positions", columns: ["id", "title", "grade", "org_unit_id"] },
  { name: "metric_values", columns: ["id", "employee_id", "kpi_type_id", "value", "period_start", "period_end", "recorded_at"] },
  { name: "kpi_types", columns: ["id", "code", "name", "unit"] },
  { name: "dashboard_layouts", columns: ["id", "user_id", "name", "widgets", "filters", "created_at", "updated_at"] },
  { name: "alerts", columns: ["id", "org_unit_id", "severity", "title", "message", "metric_key", "is_read", "created_at"] },
  { name: "ml_model_artifacts", columns: ["id", "name", "version", "artifact_path", "metrics_json", "created_at"] },
];

const operatorLabels: Record<string, string> = {
  eq: "=",
  ne: "!=",
  gt: ">",
  gte: ">=",
  lt: "<",
  lte: "<=",
  contains: "contains (содержит)",
  in: "IN",
  between: "BETWEEN",
  is_null: "IS NULL",
};

const meta = ref<{
  tables: MetaTable[];
  joins: Array<{ left: string; right: string }>;
  aggregations: string[];
  operators: string[];
}>({
  tables: defaultMetaTables,
  joins: [],
  aggregations: ["NONE", "COUNT", "SUM", "AVG", "MIN", "MAX"],
  operators: ["eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "between", "is_null"],
});

const baseTable = ref("employees");
const joins = ref<BuilderJoin[]>([]);
const selects = ref<BuilderSelect[]>([]);
const filters = ref<BuilderFilter[]>([]);
const groupBy = ref<BuilderGroup[]>([]);
const orderBy = ref<BuilderOrder[]>([]);
const limit = ref(100);
const sqlPreview = ref("");
const previewColumns = ref<string[]>([]);
const previewRows = ref<Array<Record<string, string | number | null>>>([]);

const name = ref("BI-конфигурация");
const msg = ref("");
const layouts = ref<Array<{ id: string; name: string; widgets?: { builder?: { base_table?: string } } }>>([]);
const workspaceOpened = ref(false);
const autoPreviewTimer = ref<number | null>(null);
const activeTool = ref<"selectColumns" | "join" | "select" | "group" | "filter" | "order" | "limit" | null>(null);
const selectedColumns = ref<Record<string, boolean>>({});
const operationHistory = ref<HistoryAction[]>([]);
const editingActionId = ref<string | null>(null);
const editingActionType = ref<HistoryActionType | null>(null);
let actionSeq = 0;

function nextActionId() {
  actionSeq += 1;
  return `act_${Date.now()}_${actionSeq}`;
}

const joinDraft = ref<Omit<BuilderJoin, "id">>({ table: "org_units", kind: "inner" });
const selectDraft = ref<Omit<BuilderSelect, "id">>({ field: "employees.id", agg: "NONE", alias: "" });
const groupByDraft = ref("employees.id");
const filterDraft = ref<Omit<BuilderFilter, "id">>({
  field: "employees.id",
  operator: "eq",
  valueInput: "",
  valueFrom: "",
  valueTo: "",
  valueList: [],
  isNull: true,
});
const orderDraft = ref<Omit<BuilderOrder, "id">>({ field: "employees.id", direction: "asc" });
const filterDraftListInput = ref("");

const availableFields = computed(() =>
  meta.value.tables.flatMap((t) => t.columns.map((c) => `${t.name}.${c}`)),
);

const queryTables = computed(() => {
  const ordered = [baseTable.value, ...joins.value.map((j) => j.table)];
  return ordered.filter((t, idx) => ordered.indexOf(t) === idx);
});

const queryFields = computed(() => {
  const out: string[] = [];
  for (const t of queryTables.value) {
    const table = meta.value.tables.find((x) => x.name === t);
    if (!table) continue;
    for (const c of table.columns) {
      out.push(`${t}.${c}`);
    }
  }
  return out;
});

const operationFields = computed(() =>
  queryFields.value.filter((f) => selectedColumns.value[f] !== false),
);

const selectedFieldCount = computed(
  () => queryFields.value.filter((f) => selectedColumns.value[f] !== false).length,
);

const joinCandidates = computed(() =>
  meta.value.tables.map((t) => t.name).filter((x) => x !== baseTable.value),
);

function ensureSelectedColumnsForCurrentQuery() {
  const next: Record<string, boolean> = {};
  for (const field of queryFields.value) {
    next[field] = selectedColumns.value[field] !== false;
  }
  selectedColumns.value = next;
  syncDraftFields();
}

function toggleSelectColumn(field: string, checked: boolean) {
  selectedColumns.value[field] = checked;
  syncDraftFields();
  scheduleAutoPreview();
}

function syncDraftFields() {
  const first = operationFields.value[0] ?? queryFields.value[0] ?? `${baseTable.value}.id`;
  if (!operationFields.value.includes(selectDraft.value.field)) {
    selectDraft.value.field = first;
  }
  if (!operationFields.value.includes(filterDraft.value.field)) {
    filterDraft.value.field = first;
  }
  if (!operationFields.value.includes(groupByDraft.value)) {
    groupByDraft.value = first;
  }
  if (!operationFields.value.includes(orderDraft.value.field)) {
    orderDraft.value.field = first;
  }
}

function addJoin() {
  if (editingActionId.value && editingActionType.value === "join") {
    const idx = joins.value.findIndex((x) => x.id === editingActionId.value);
    if (idx >= 0) joins.value[idx] = { id: editingActionId.value, table: joinDraft.value.table, kind: joinDraft.value.kind };
    editingActionId.value = null;
    editingActionType.value = null;
  } else {
    const id = nextActionId();
    joins.value.push({ id, table: joinDraft.value.table || (joinCandidates.value[0] ?? "org_units"), kind: joinDraft.value.kind });
    operationHistory.value.push({ id, type: "join" });
  }
  activeTool.value = null;
  scheduleAutoPreview();
}
function removeJoin(idx: number) {
  const [removed] = joins.value.splice(idx, 1);
  if (removed) {
    operationHistory.value = operationHistory.value.filter((h) => h.id !== removed.id);
  }
  scheduleAutoPreview();
}

function addSelect() {
  if (!operationFields.value.length) return;
  if (editingActionId.value && editingActionType.value === "select") {
    const idx = selects.value.findIndex((x) => x.id === editingActionId.value);
    if (idx >= 0) {
      selects.value[idx] = {
        id: editingActionId.value,
        field: selectDraft.value.field || operationFields.value[0],
        agg: selectDraft.value.agg || "NONE",
        alias: selectDraft.value.alias || "",
      };
    }
    editingActionId.value = null;
    editingActionType.value = null;
  } else {
    const id = nextActionId();
    selects.value.push({
      id,
      field: selectDraft.value.field || operationFields.value[0],
      agg: selectDraft.value.agg || "NONE",
      alias: selectDraft.value.alias || "",
    });
    operationHistory.value.push({ id, type: "select" });
  }
  activeTool.value = null;
  scheduleAutoPreview();
}
function removeSelect(idx: number) {
  const [removed] = selects.value.splice(idx, 1);
  if (removed) {
    operationHistory.value = operationHistory.value.filter((h) => h.id !== removed.id);
  }
  scheduleAutoPreview();
}

function addGroupBy() {
  if (!operationFields.value.length) return;
  if (editingActionId.value && editingActionType.value === "group") {
    const idx = groupBy.value.findIndex((x) => x.id === editingActionId.value);
    if (idx >= 0) groupBy.value[idx] = { id: editingActionId.value, field: groupByDraft.value || operationFields.value[0] };
    editingActionId.value = null;
    editingActionType.value = null;
  } else {
    const id = nextActionId();
    groupBy.value.push({ id, field: groupByDraft.value || operationFields.value[0] });
    operationHistory.value.push({ id, type: "group" });
  }
  activeTool.value = null;
  scheduleAutoPreview();
}
function removeGroupBy(idx: number) {
  const [removed] = groupBy.value.splice(idx, 1);
  if (removed) {
    operationHistory.value = operationHistory.value.filter((h) => h.id !== removed.id);
  }
  scheduleAutoPreview();
}

function addFilterListValue() {
  const v = filterDraftListInput.value.trim();
  if (!v) return;
  filterDraft.value.valueList.push(v);
  filterDraftListInput.value = "";
}

function removeFilterListValue(idx: number) {
  filterDraft.value.valueList.splice(idx, 1);
}

function buildFilterRuntimeValue(f: BuilderFilter) {
  if (f.operator === "between") {
    return [parseFilterValue("eq", f.valueFrom), parseFilterValue("eq", f.valueTo)];
  }
  if (f.operator === "in") {
    return f.valueList.map((x) => parseFilterValue("eq", x));
  }
  if (f.operator === "is_null") {
    return f.isNull;
  }
  return parseFilterValue(f.operator, f.valueInput);
}

function formatFilterValue(f: BuilderFilter) {
  if (f.operator === "between") return `[${f.valueFrom}..${f.valueTo}]`;
  if (f.operator === "in") return `[${f.valueList.join(", ")}]`;
  if (f.operator === "is_null") return f.isNull ? "NULL" : "NOT NULL";
  return f.valueInput;
}

function addFilter() {
  if (!operationFields.value.length) return;
  const item = {
    field: filterDraft.value.field || operationFields.value[0],
    operator: filterDraft.value.operator || "eq",
    valueInput: filterDraft.value.valueInput ?? "",
    valueFrom: filterDraft.value.valueFrom ?? "",
    valueTo: filterDraft.value.valueTo ?? "",
    valueList: [...(filterDraft.value.valueList ?? [])],
    isNull: filterDraft.value.isNull ?? true,
  };
  if (editingActionId.value && editingActionType.value === "filter") {
    const idx = filters.value.findIndex((x) => x.id === editingActionId.value);
    if (idx >= 0) filters.value[idx] = { id: editingActionId.value, ...item };
    editingActionId.value = null;
    editingActionType.value = null;
  } else {
    const id = nextActionId();
    filters.value.push({ id, ...item });
    operationHistory.value.push({ id, type: "filter" });
  }
  activeTool.value = null;
  scheduleAutoPreview();
}
function removeFilter(idx: number) {
  const [removed] = filters.value.splice(idx, 1);
  if (removed) {
    operationHistory.value = operationHistory.value.filter((h) => h.id !== removed.id);
  }
  scheduleAutoPreview();
}

function addOrderBy() {
  if (!operationFields.value.length) return;
  if (editingActionId.value && editingActionType.value === "order") {
    const idx = orderBy.value.findIndex((x) => x.id === editingActionId.value);
    if (idx >= 0) {
      orderBy.value[idx] = {
        id: editingActionId.value,
        field: orderDraft.value.field || operationFields.value[0],
        direction: orderDraft.value.direction || "asc",
      };
    }
    editingActionId.value = null;
    editingActionType.value = null;
  } else {
    const id = nextActionId();
    orderBy.value.push({
      id,
      field: orderDraft.value.field || operationFields.value[0],
      direction: orderDraft.value.direction || "asc",
    });
    operationHistory.value.push({ id, type: "order" });
  }
  activeTool.value = null;
  scheduleAutoPreview();
}

function toggleTool(tool: "selectColumns" | "join" | "select" | "group" | "filter" | "order" | "limit") {
  if (activeTool.value !== tool) {
    editingActionId.value = null;
    editingActionType.value = null;
  }
  activeTool.value = activeTool.value === tool ? null : tool;
}
function removeOrderBy(idx: number) {
  const [removed] = orderBy.value.splice(idx, 1);
  if (removed) {
    operationHistory.value = operationHistory.value.filter((h) => h.id !== removed.id);
  }
  scheduleAutoPreview();
}

function parseFilterValue(op: string, raw: string) {
  if (op === "in" || op === "between") {
    return raw
      .split(",")
      .map((x) => x.trim())
      .filter((x) => x.length > 0);
  }
  if (op === "is_null") {
    return raw ? raw.toLowerCase() !== "false" : true;
  }
  const n = Number(raw);
  if (!Number.isNaN(n) && raw.trim() !== "") {
    return n;
  }
  return raw;
}

function historyLabel(id: string, type: HistoryActionType) {
  if (type === "join") {
    const x = joins.value.find((i) => i.id === id);
    return x ? `JOIN ${x.kind.toUpperCase()} ${x.table}` : "JOIN";
  }
  if (type === "select") {
    const x = selects.value.find((i) => i.id === id);
    return x ? `SELECT ${x.agg}(${x.field || "*"}) ${x.alias ? `AS ${x.alias}` : ""}` : "SELECT";
  }
  if (type === "group") {
    const x = groupBy.value.find((i) => i.id === id);
    return x ? `GROUP BY ${x.field}` : "GROUP BY";
  }
  if (type === "filter") {
    const x = filters.value.find((i) => i.id === id);
    return x ? `WHERE ${x.field} ${operatorLabels[x.operator] ?? x.operator} ${formatFilterValue(x)}` : "FILTER";
  }
  const x = orderBy.value.find((i) => i.id === id);
  return x ? `ORDER BY ${x.field} ${x.direction.toUpperCase()}` : "ORDER BY";
}

function openHistoryAction(id: string) {
  const action = operationHistory.value.find((h) => h.id === id);
  if (!action) return;
  editingActionId.value = id;
  editingActionType.value = action.type;
  if (action.type === "join") {
    const x = joins.value.find((i) => i.id === id);
    if (!x) return;
    joinDraft.value = { table: x.table, kind: x.kind };
    activeTool.value = "join";
    return;
  }
  if (action.type === "select") {
    const x = selects.value.find((i) => i.id === id);
    if (!x) return;
    selectDraft.value = { field: x.field, agg: x.agg, alias: x.alias };
    activeTool.value = "select";
    return;
  }
  if (action.type === "group") {
    const x = groupBy.value.find((i) => i.id === id);
    if (!x) return;
    groupByDraft.value = x.field;
    activeTool.value = "group";
    return;
  }
  if (action.type === "filter") {
    const x = filters.value.find((i) => i.id === id);
    if (!x) return;
    filterDraft.value = {
      field: x.field,
      operator: x.operator,
      valueInput: x.valueInput,
      valueFrom: x.valueFrom,
      valueTo: x.valueTo,
      valueList: [...x.valueList],
      isNull: x.isNull,
    };
    activeTool.value = "filter";
    return;
  }
  const x = orderBy.value.find((i) => i.id === id);
  if (!x) return;
  orderDraft.value = { field: x.field, direction: x.direction };
  activeTool.value = "order";
}

function removeHistoryAction(id: string, type: HistoryActionType) {
  if (editingActionId.value === id) {
    editingActionId.value = null;
    editingActionType.value = null;
    activeTool.value = null;
  }
  if (type === "join") {
    const idx = joins.value.findIndex((i) => i.id === id);
    if (idx >= 0) removeJoin(idx);
    return;
  }
  if (type === "select") {
    const idx = selects.value.findIndex((i) => i.id === id);
    if (idx >= 0) removeSelect(idx);
    return;
  }
  if (type === "group") {
    const idx = groupBy.value.findIndex((i) => i.id === id);
    if (idx >= 0) removeGroupBy(idx);
    return;
  }
  if (type === "filter") {
    const idx = filters.value.findIndex((i) => i.id === id);
    if (idx >= 0) removeFilter(idx);
    return;
  }
  const idx = orderBy.value.findIndex((i) => i.id === id);
  if (idx >= 0) removeOrderBy(idx);
}

function downloadSql() {
  if (!sqlPreview.value) return;
  const blob = new Blob([sqlPreview.value], { type: "text/sql;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `builder_query_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.sql`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

type SelectExprPayload = { field: string | null; agg: string; alias: string | null };

function buildSelectPayload() {
  const allowedFields = new Set(queryFields.value);
  const selectedFieldExprs: SelectExprPayload[] = queryFields.value
    .filter((f) => selectedColumns.value[f] !== false)
    .map((f) => ({ field: f, agg: "NONE", alias: null }));

  const orderedSelects = operationHistory.value
    .filter((h) => h.type === "select")
    .map((h) => selects.value.find((s) => s.id === h.id))
    .filter((x): x is BuilderSelect => !!x);

  const functionExprs: SelectExprPayload[] = orderedSelects
    .filter((s) => !s.field || allowedFields.has(s.field))
    .map((s) => ({
      field: s.field || null,
      agg: s.agg || "NONE",
      alias: s.alias || null,
    }));

  const hasAggregate = functionExprs.some((x) => x.agg.toUpperCase() !== "NONE");
  if (!hasAggregate) {
    return [...selectedFieldExprs, ...functionExprs];
  }

  if (groupBy.value.length) {
    const grouped = new Set(groupBy.value.map((g) => g.field));
    const groupedSelected = selectedFieldExprs.filter((x) => x.field && grouped.has(x.field));
    return [...groupedSelected, ...functionExprs];
  }

  // Агрегаты без GROUP BY: показываем только агрегатные выражения.
  return functionExprs.filter((x) => x.agg.toUpperCase() !== "NONE");
}

async function preview() {
  msg.value = "";
  const mergedSelects = buildSelectPayload();
  const allowedFields = new Set(queryFields.value);

  const orderedJoins = operationHistory.value
    .filter((h) => h.type === "join")
    .map((h) => joins.value.find((j) => j.id === h.id))
    .filter((x): x is BuilderJoin => !!x)
    .map((j) => ({ table: j.table, kind: j.kind }));
  const orderedGroups = operationHistory.value
    .filter((h) => h.type === "group")
    .map((h) => groupBy.value.find((g) => g.id === h.id))
    .filter((x): x is BuilderGroup => !!x)
    .filter((g) => allowedFields.has(g.field))
    .map((g) => g.field);
  const orderedFilters = operationHistory.value
    .filter((h) => h.type === "filter")
    .map((h) => filters.value.find((f) => f.id === h.id))
    .filter((x): x is BuilderFilter => !!x)
    .map((f) => ({
      field: f.field,
      operator: f.operator,
      value: buildFilterRuntimeValue(f),
    }))
    .filter((f) => allowedFields.has(f.field));
  const orderedOrderBy = operationHistory.value
    .filter((h) => h.type === "order")
    .map((h) => orderBy.value.find((o) => o.id === h.id))
    .filter((x): x is BuilderOrder => !!x)
    .map((o) => ({ field: o.field, direction: o.direction }));
  const safeOrderBy = orderedOrderBy.filter((o) => allowedFields.has(o.field));

  const payload = {
    base_table: baseTable.value,
    joins: orderedJoins,
    selects: mergedSelects,
    filters: orderedFilters,
    group_by: orderedGroups,
    order_by: safeOrderBy,
    limit: limit.value,
  };
  const { data } = await api.post("/dashboard/builder/preview", payload);
  sqlPreview.value = data.sql ?? "";
  previewColumns.value = data.columns ?? [];
  previewRows.value = data.rows ?? [];
}

function scheduleAutoPreview() {
  if (!workspaceOpened.value) return;
  if (autoPreviewTimer.value) {
    clearTimeout(autoPreviewTimer.value);
  }
  autoPreviewTimer.value = window.setTimeout(() => {
    preview().catch((e: unknown) => {
      const detail =
        typeof e === "object" && e && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : "";
      msg.value = detail
        ? `Ошибка предпросмотра: ${detail}`
        : "Ошибка предпросмотра. Проверьте выбранные операции.";
    });
  }, 250);
}

function startWorkspace() {
  workspaceOpened.value = true;
  if (!joinDraft.value.table && joinCandidates.value.length) {
    joinDraft.value.table = joinCandidates.value[0];
  }
  const firstField = availableFields.value[0] ?? `${baseTable.value}.id`;
  if (!selectDraft.value.field) selectDraft.value.field = firstField;
  if (!filterDraft.value.field) filterDraft.value.field = firstField;
  if (!groupByDraft.value) groupByDraft.value = firstField;
  if (!orderDraft.value.field) orderDraft.value.field = firstField;
  ensureSelectedColumnsForCurrentQuery();
  scheduleAutoPreview();
}

function resetBuilder() {
  joins.value = [];
  selects.value = [];
  filters.value = [];
  groupBy.value = [];
  orderBy.value = [];
  operationHistory.value = [];
  editingActionId.value = null;
  editingActionType.value = null;
  selectedColumns.value = {};
  limit.value = 100;
  sqlPreview.value = "";
  previewColumns.value = [];
  previewRows.value = [];
  activeTool.value = null;
  startWorkspace();
}

async function save() {
  const orderedJoins = operationHistory.value
    .filter((h) => h.type === "join")
    .map((h) => joins.value.find((j) => j.id === h.id))
    .filter((x): x is BuilderJoin => !!x)
    .map((j) => ({ table: j.table, kind: j.kind }));
  const orderedGroups = operationHistory.value
    .filter((h) => h.type === "group")
    .map((h) => groupBy.value.find((g) => g.id === h.id))
    .filter((x): x is BuilderGroup => !!x)
    .map((g) => g.field);
  const orderedFilters = operationHistory.value
    .filter((h) => h.type === "filter")
    .map((h) => filters.value.find((f) => f.id === h.id))
    .filter((x): x is BuilderFilter => !!x)
    .map((f) => ({
      field: f.field,
      operator: f.operator,
      value: buildFilterRuntimeValue(f),
    }));
  const orderedOrderBy = operationHistory.value
    .filter((h) => h.type === "order")
    .map((h) => orderBy.value.find((o) => o.id === h.id))
    .filter((x): x is BuilderOrder => !!x)
    .map((o) => ({ field: o.field, direction: o.direction }));

  const payload = {
    base_table: baseTable.value,
    joins: orderedJoins,
    selects: buildSelectPayload(),
    filters: orderedFilters,
    group_by: orderedGroups,
    order_by: orderedOrderBy,
    limit: limit.value,
  };
  await api.post("/dashboard/layouts", {
    name: name.value,
    widgets: { builder: payload },
    filters: {},
  });
  msg.value = "Конфигурация сохранена";
  await load();
}

async function load() {
  msg.value = "";
  const [metaRes, layoutRes] = await Promise.allSettled([
    api.get("/dashboard/builder/meta"),
    api.get("/dashboard/layouts"),
  ]);

  if (metaRes.status === "fulfilled") {
    meta.value = metaRes.value.data;
  } else {
    msg.value =
      "Не удалось получить метаданные конструктора с backend. Показаны локальные источники по умолчанию.";
  }

  if (layoutRes.status === "fulfilled") {
    layouts.value = layoutRes.value.data;
  } else if (!msg.value) {
    msg.value = "Не удалось загрузить сохранённые конфигурации.";
  }

  if (!meta.value.tables.length) {
    meta.value.tables = defaultMetaTables;
  }
  if (!meta.value.aggregations?.length) {
    meta.value.aggregations = ["NONE", "COUNT", "SUM", "AVG", "MIN", "MAX"];
  }
  if (!meta.value.operators?.length) {
    meta.value.operators = ["eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "between", "is_null"];
  }

  if (!meta.value.tables.find((t) => t.name === baseTable.value)) {
    baseTable.value = meta.value.tables[0]?.name ?? "employees";
  }
  joinDraft.value.table = joinCandidates.value[0] ?? "org_units";
  const firstField = availableFields.value[0] ?? `${baseTable.value}.id`;
  selectDraft.value.field = firstField;
  filterDraft.value.field = firstField;
  groupByDraft.value = firstField;
  orderDraft.value.field = firstField;
  filterDraft.value.operator = "eq";
  filterDraft.value.valueInput = "";
  filterDraft.value.valueFrom = "";
  filterDraft.value.valueTo = "";
  filterDraft.value.valueList = [];
  filterDraft.value.isNull = true;
  filterDraftListInput.value = "";
  ensureSelectedColumnsForCurrentQuery();
}

onMounted(load);

watch(
  [baseTable, limit, joins, selects, filters, groupBy, orderBy],
  () => {
    ensureSelectedColumnsForCurrentQuery();
    scheduleAutoPreview();
  },
  { deep: true },
);

watch(
  operationFields,
  () => {
    syncDraftFields();
  },
  { deep: true },
);
</script>

<style scoped>
.builder-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 1rem;
}

.workspace {
  min-width: 0;
}

.sidepanel {
  position: sticky;
  top: 1rem;
  max-height: calc(100vh - 4rem);
  overflow: auto;
}

.inp {
  width: 100%;
  max-width: 280px;
  margin: 0.2rem 0.4rem 0.2rem 0;
  padding: 0.35rem;
}
.inp.sm {
  max-width: 340px;
}
.inp.mini {
  max-width: 130px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  margin: 0.35rem 0;
}
.top-toolbar {
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.75rem;
  margin-bottom: 0.75rem;
}
.tool-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 0.55rem;
  margin-bottom: 0.75rem;
  background: #f8fafc;
}
.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.3rem 0.8rem;
  width: 100%;
  margin-top: 0.35rem;
}
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.88rem;
}
.tool-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem;
  border-right: 1px dashed #cbd5e1;
  padding-right: 0.8rem;
  margin-right: 0.8rem;
}
.tool-label {
  font-size: 0.8rem;
  color: #475569;
  font-weight: 700;
}
.btn {
  padding: 0.45rem 0.9rem;
  cursor: pointer;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  font-weight: 600;
  transition: all 0.18s ease;
}
.btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
  border-color: #94a3b8;
}
.btn.small {
  padding: 0.3rem 0.6rem;
  font-size: 0.85rem;
}
.btn.danger {
  background: #fee2e2;
  border: 1px solid #fecaca;
}
.btn.tiny {
  padding: 0.1rem 0.45rem;
  font-size: 0.75rem;
}
.ok {
  color: #15803d;
}
.muted {
  color: #64748b;
}
.sql {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 0.75rem;
  white-space: pre-wrap;
  font-size: 0.82rem;
}
.table-wrap {
  overflow-x: auto;
}
.result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.result-table th,
.result-table td {
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  padding: 0.45rem;
}
.result-table th {
  background: #f8fafc;
}
.result-table tbody tr:hover {
  background: #f8fafc;
}
.history {
  margin: 0;
  padding-left: 1rem;
}
.history-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.45rem;
}
.history-link {
  border: none;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  text-align: left;
  padding: 0;
  font: inherit;
}
.history-link:hover {
  text-decoration: underline;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  max-width: 320px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  background: #e2e8f0;
  border-radius: 999px;
  padding: 0.08rem 0.45rem;
  font-size: 0.78rem;
}
.chip-x {
  border: none;
  background: transparent;
  color: #334155;
  cursor: pointer;
  padding: 0;
}
.inline-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.9rem;
}

@media (max-width: 1200px) {
  .builder-shell {
    grid-template-columns: 1fr;
  }
  .sidepanel {
    position: static;
    max-height: none;
  }
}
</style>
