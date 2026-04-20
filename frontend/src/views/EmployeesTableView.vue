<template>
  <div class="layout">
    <div>
      <div class="card">
        <h2>Карточки сотрудников</h2>
        <p>Быстрый и понятный просмотр профилей, динамики тестов и KPI без сложных BI-операций.</p>
        <div class="filters">
          <div class="filters-main">
            <input v-model="search" class="input" type="text" placeholder="Поиск: ФИО, email, external ID" />
            <select v-model="selectedOrgUnit" class="input">
              <option value="">Все подразделения</option>
              <option v-for="x in orgUnits" :key="x.id" :value="x.id">{{ x.name }}</option>
            </select>
            <select v-model="sortBy" class="input">
              <option value="full_name">Сортировка: ФИО</option>
              <option value="org_unit">Сортировка: Подразделение</option>
              <option value="position">Сортировка: Позиция</option>
              <option value="hire_date">Сортировка: Дата найма</option>
            </select>
            <select v-model="sortDir" class="input">
              <option value="asc">По возрастанию</option>
              <option value="desc">По убыванию</option>
            </select>
          </div>
          <div class="filters-actions">
            <button v-if="canCreateEmployee" class="btn" type="button" @click="showCreateModal = true">Создать сотрудника</button>
            <button class="btn" type="button" @click="loadCards">Обновить</button>
          </div>
        </div>
      </div>

      <div class="cards-grid">
        <button
          v-for="item in cards"
          :key="item.id"
          type="button"
          class="card employee-card"
          :class="{ active: selectedEmployeeId === item.id }"
          @click="selectEmployee(item.id)"
        >
          <div class="name">{{ item.full_name || item.external_id || "Сотрудник" }}</div>
          <div class="muted">{{ item.email || "email не указан" }}</div>
          <div class="meta">Подразделение: {{ item.org_unit_name || "—" }}</div>
          <div class="meta">Должность: {{ item.position_title || "—" }}</div>
          <div class="meta">Менеджер: {{ item.manager_name || "—" }}</div>
        </button>
      </div>

      <div class="card" v-if="!cards.length">
        Нет сотрудников по выбранным фильтрам.
      </div>
    </div>

    <div class="details">
      <template v-if="selectedEmployee">
        <div class="card details-card details-profile">
          <h3>{{ selectedEmployee.full_name || selectedEmployee.external_id || "Карточка сотрудника" }}</h3>
          <div class="meta">Email: {{ selectedEmployee.email || "—" }}</div>
          <div class="meta">Роль: {{ selectedEmployee.role || "—" }}</div>
          <div class="meta">Подразделение: {{ selectedEmployee.org_unit_name || "—" }}</div>
          <div class="meta">Должность: {{ selectedEmployee.position_title || "—" }}</div>
          <div class="meta">Дата найма: {{ selectedEmployee.hire_date || "—" }}</div>
        </div>
        <div ref="radarEl" class="card chart chart-radar" />
        <div ref="testsEl" class="card chart chart-tests" />
        <div ref="kpiEl" class="card chart chart-kpi" />
        <div class="card details-card details-history">
          <h4>История прохождения тестов</h4>
          <ul class="history-list" v-if="surveyHistory.length">
            <li v-for="x in surveyHistory" :key="x.id">
              <strong>{{ x.survey_title }}</strong> ({{ x.template || "SURVEY" }}) -
              {{ formatDate(x.submitted_at) }} -
              likert: {{ scoreValue(x.scores, "likert_mean") }}, burnout: {{ scoreValue(x.scores, "burnout_index") }}
            </li>
          </ul>
          <p v-else>История тестов пока отсутствует.</p>
        </div>
      </template>
      <div class="card" v-else>Выберите сотрудника, чтобы открыть карточку.</div>
    </div>

    <div v-if="showCreateModal" class="create-overlay">
      <div class="create-modal card">
        <button type="button" class="modal-close" aria-label="Закрыть" @click="closeCreateModal">×</button>
        <h3>Создать сотрудника</h3>
        <p class="muted">Укажите данные сотрудника и данные для входа.</p>
        <div class="create-grid">
          <input v-model.trim="createForm.full_name" class="input" type="text" placeholder="ФИО" />
          <input v-model.trim="createForm.email" class="input" type="email" placeholder="Email (логин)" />
          <input v-model.trim="createForm.password" class="input" type="password" placeholder="Пароль" />
          <div class="field-group">
            <select v-model="createForm.org_unit_id" class="input">
              <option value="">Подразделение</option>
              <option v-for="x in orgUnits" :key="x.id" :value="x.id">{{ x.name }}</option>
            </select>
            <p class="field-hint">Выберите подразделение, в котором сотрудник работает.</p>
          </div>
          <div class="field-group">
            <select v-model="createForm.position_id" class="input">
              <option value="">Должность</option>
              <option v-for="x in positions" :key="x.id" :value="x.id">{{ x.title }}</option>
            </select>
            <p class="field-hint">Укажите фактическую должность сотрудника в компании.</p>
          </div>
          <div class="field-group">
            <select v-model="createForm.manager_id" class="input">
              <option value="">Руководитель</option>
              <option v-for="x in managerOptions" :key="x.id" :value="x.id">{{ x.full_name || x.external_id || x.id }}</option>
            </select>
            <p class="field-hint">Непосредственный руководитель (можно оставить пустым).</p>
          </div>
          <input v-model="createForm.hire_date" class="input" type="date" />
        </div>
        <p v-if="createMessage" class="create-message">{{ createMessage }}</p>
        <div class="create-actions">
          <button class="btn" type="button" @click="closeCreateModal">Отмена</button>
          <button class="btn primary" type="button" :disabled="creatingEmployee" @click="createEmployee">
            {{ creatingEmployee ? "Создаем..." : "Создать сотрудника" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

type EmployeeCard = {
  id: string;
  user_id: string | null;
  full_name: string | null;
  email: string | null;
  role: string | null;
  external_id: string | null;
  org_unit_id: string;
  org_unit_name: string | null;
  position_id: string | null;
  position_title: string | null;
  manager_id: string | null;
  manager_name: string | null;
  hire_date: string | null;
};
type OrgUnit = { id: string; name: string };
type Position = { id: string; title: string };
type SurveyHistoryItem = {
  id: string;
  survey_title: string;
  template: string | null;
  submitted_at: string;
  scores: Record<string, number>;
};
type MetricValue = {
  id: string;
  kpi_type_id: string;
  value: number;
  period_start: string;
};
type KpiType = { id: string; name: string };

const cards = ref<EmployeeCard[]>([]);
const orgUnits = ref<OrgUnit[]>([]);
const positions = ref<Position[]>([]);
const kpiTypes = ref<KpiType[]>([]);
const selectedEmployeeId = ref<string | null>(null);
const search = ref("");
const selectedOrgUnit = ref("");
const sortBy = ref("full_name");
const sortDir = ref("asc");
const surveyHistory = ref<SurveyHistoryItem[]>([]);
const metricValues = ref<MetricValue[]>([]);
const radarEl = ref<HTMLDivElement | null>(null);
const testsEl = ref<HTMLDivElement | null>(null);
const kpiEl = ref<HTMLDivElement | null>(null);
const auth = useAuthStore();
const canCreateEmployee = computed(() => auth.role === "HR" || auth.role === "ADMIN");
const creatingEmployee = ref(false);
const createMessage = ref("");
const showCreateModal = ref(false);
const createForm = ref({
  full_name: "",
  email: "",
  password: "",
  org_unit_id: "",
  position_id: "",
  manager_id: "",
  hire_date: "",
});

const selectedEmployee = computed(() => cards.value.find((x) => x.id === selectedEmployeeId.value) ?? null);
const managerOptions = computed(() => cards.value.filter((x) => x.role === "TEAMLEAD" || x.role === "ADMIN"));

async function loadCards() {
  const { data } = await api.get("/core/employees/cards", {
    params: {
      search: search.value || undefined,
      org_unit_id: selectedOrgUnit.value || undefined,
      sort_by: sortBy.value,
      sort_dir: sortDir.value,
    },
  });
  cards.value = data ?? [];
  if (!selectedEmployeeId.value && cards.value.length) {
    selectedEmployeeId.value = cards.value[0].id;
  }
  if (selectedEmployeeId.value && !cards.value.find((x) => x.id === selectedEmployeeId.value)) {
    selectedEmployeeId.value = cards.value[0]?.id ?? null;
  }
}

function resetCreateForm() {
  createForm.value = {
    full_name: "",
    email: "",
    password: "",
    org_unit_id: "",
    position_id: "",
    manager_id: "",
    hire_date: "",
  };
}

function closeCreateModal() {
  showCreateModal.value = false;
  createMessage.value = "";
}

async function createEmployee() {
  createMessage.value = "";
  if (!canCreateEmployee.value) return;
  if (
    !createForm.value.full_name ||
    !createForm.value.email ||
    !createForm.value.password ||
    !createForm.value.org_unit_id ||
    !createForm.value.position_id ||
    !createForm.value.hire_date
  ) {
    createMessage.value = "Заполните обязательные поля: ФИО, Email, Пароль, Подразделение, Должность, Дата найма.";
    return;
  }
  if (createForm.value.password.length < 6) {
    createMessage.value = "Пароль должен быть не короче 6 символов.";
    return;
  }
  creatingEmployee.value = true;
  try {
    await api.post("/core/employees", {
      full_name: createForm.value.full_name,
      email: createForm.value.email,
      password: createForm.value.password,
      org_unit_id: createForm.value.org_unit_id,
      position_id: createForm.value.position_id || null,
      manager_id: createForm.value.manager_id || null,
      hire_date: createForm.value.hire_date || null,
    });
    createMessage.value = "Сотрудник успешно создан.";
    resetCreateForm();
    await loadCards();
    closeCreateModal();
  } catch (_e) {
    createMessage.value = "Не удалось создать сотрудника. Проверьте корректность данных.";
  } finally {
    creatingEmployee.value = false;
  }
}

function formatDate(v: string) {
  return new Date(v).toLocaleDateString("ru-RU");
}

function scoreValue(scores: Record<string, number>, key: string) {
  const v = scores[key];
  return typeof v === "number" ? v.toFixed(2) : "—";
}

function ruRadarName(name: string) {
  const map: Record<string, string> = {
    empathy: "Эмпатия",
    learning: "Обуча-\nемость",
    focus: "Фокус",
    collaboration: "Командность",
    stress_mgmt: "Стресс-\nустойчивость",
  };
  return map[name] || name;
}

function ruRadarTooltipName(name: string) {
  const map: Record<string, string> = {
    empathy: "Эмпатия",
    learning: "Обучаемость",
    focus: "Фокус",
    collaboration: "Командность",
    stress_mgmt: "Стрессоустойчивость",
  };
  return map[name] || name;
}

function ruKpiName(name: string) {
  const n = name.trim().toLowerCase();
  if (n === "nps" || n === "net promoter score") return "NPS";
  if (n === "sales" || n === "sales volume") return "Продажи";
  if (n === "stress" || n === "stress index") return "Стресс";
  return name;
}

function drawRadar(data: { ideal: Record<string, number>; current: Record<string, number> }) {
  if (!radarEl.value) return;
  const keys = Object.keys(data.current || data.ideal || {});
  const chart = echarts.init(radarEl.value);
  chart.setOption({
    title: {
      text: "Психологический портрет",
      left: 12,
      top: 8,
      textStyle: { fontSize: 16, fontWeight: 700 },
    },
    tooltip: {
      trigger: "item",
      formatter: (params: any) => {
        const values = Array.isArray(params?.value) ? params.value : [];
        return keys
          .map((k, idx) => `${ruRadarTooltipName(k)}: ${Number(values[idx] ?? 0).toFixed(2)}`)
          .join("<br/>");
      },
    },
    legend: {
      left: "center",
      bottom: -2,
      data: ["Сотрудник"],
      textStyle: { fontSize: 11 },
    },
    radar: {
      center: ["50%", "56%"],
      radius: "52%",
      name: { fontSize: 12 },
      indicator: keys.map((k) => ({ name: ruRadarName(k), max: 5 })),
    },
    series: [
      {
        type: "radar",
        data: [
          { name: "Сотрудник", value: keys.map((k) => data.current[k] ?? 0) },
        ],
      },
    ],
  });
}

function drawTestsChart() {
  if (!testsEl.value) return;
  const chart = echarts.init(testsEl.value);
  const ordered = [...surveyHistory.value].reverse();
  chart.setOption({
    title: { text: "Динамика тестов", left: 12, top: 8, textStyle: { fontSize: 16, fontWeight: 700 } },
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        const rows = Array.isArray(params) ? params : [];
        const lines = rows
          .map((p: any) => `${p.marker}${p.seriesName}: ${typeof p.value === "number" ? p.value.toFixed(2) : p.value}`)
          .join("<br/>");
        return `${rows[0]?.axisValueLabel ?? ""}<br/>${lines}`;
      },
    },
    legend: { data: ["Счастье", "Выгорание"], left: "center", bottom: -2, textStyle: { fontSize: 11 } },
    grid: { top: 52, left: 42, right: 16, bottom: 50 },
    xAxis: {
      type: "category",
      data: ordered.map((x) => formatDate(x.submitted_at)),
      axisLabel: { hideOverlap: true, fontSize: 11 },
    },
    yAxis: { type: "value" },
    series: [
      { name: "Счастье", type: "line", smooth: false, data: ordered.map((x) => x.scores.likert_mean ?? null) },
      { name: "Выгорание", type: "line", smooth: false, data: ordered.map((x) => x.scores.burnout_index ?? null) },
    ],
  });
}

function drawKpiChart() {
  if (!kpiEl.value) return;
  const chart = echarts.init(kpiEl.value);
  const byKpi = new Map<string, Array<{ t: string; v: number }>>();
  for (const row of metricValues.value) {
    if (!byKpi.has(row.kpi_type_id)) byKpi.set(row.kpi_type_id, []);
    byKpi.get(row.kpi_type_id)?.push({ t: row.period_start, v: row.value });
  }
  const periods = [...new Set(metricValues.value.map((x) => x.period_start))].sort((a, b) => a.localeCompare(b));
  const xLabels = periods.map((t) =>
    new Date(`${t}T00:00:00`).toLocaleDateString("ru-RU", { month: "short", year: "2-digit" }).replace(" г.", ""),
  );
  const series = [...byKpi.entries()].map(([kpiId, points]) => {
    const baseName = kpiTypes.value.find((x) => x.id === kpiId)?.name ?? kpiId;
    const pointMap = new Map(points.map((p) => [p.t, p.v]));
    return { name: ruKpiName(baseName), type: "line", smooth: true, data: periods.map((t) => pointMap.get(t) ?? null) };
  });
  chart.setOption({
    title: { text: "Динамика KPI сотрудника", left: 12, top: 10, textStyle: { fontSize: 17, fontWeight: 700 } },
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        const rows = Array.isArray(params) ? params : [];
        const lines = rows
          .map((p: any) => `${p.marker}${p.seriesName}: ${typeof p.value === "number" ? p.value.toFixed(2) : p.value}`)
          .join("<br/>");
        return `${rows[0]?.axisValueLabel ?? ""}<br/>${lines}`;
      },
    },
    legend: { type: "scroll", right: 12, top: 12, textStyle: { fontSize: 12 } },
    grid: { top: 56, left: 46, right: 16, bottom: 34 },
    xAxis: { type: "category", data: xLabels },
    yAxis: { type: "value" },
    series,
  });
}

async function loadEmployeeDetails(employeeId: string) {
  const [radarRes, surveysRes, metricsRes] = await Promise.all([
    api.get("/viz/radar-competencies", { params: { employee_id: employeeId } }),
    api.get(`/surveys/responses/employee/${employeeId}`),
    api.get("/core/metric-values", { params: { employee_id: employeeId } }),
  ]);
  surveyHistory.value = surveysRes.data ?? [];
  metricValues.value = metricsRes.data ?? [];
  drawRadar(radarRes.data ?? { ideal: {}, current: {} });
  drawTestsChart();
  drawKpiChart();
}

function selectEmployee(id: string) {
  selectedEmployeeId.value = id;
}

watch([search, selectedOrgUnit, sortBy, sortDir], () => {
  loadCards().catch(() => undefined);
});

watch(selectedEmployeeId, (id) => {
  if (!id) return;
  loadEmployeeDetails(id).catch(() => undefined);
});

onMounted(async () => {
  const [orgRes, kpiRes, posRes] = await Promise.all([api.get("/core/org-units"), api.get("/core/kpi-types"), api.get("/core/positions")]);
  orgUnits.value = orgRes.data ?? [];
  kpiTypes.value = kpiRes.data ?? [];
  positions.value = posRes.data ?? [];
  await loadCards();
  if (selectedEmployeeId.value) {
    await loadEmployeeDetails(selectedEmployeeId.value);
  }
});
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 1rem;
}
.btn {
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
}
.filters {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  margin-top: 0.75rem;
}
.filters-main {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
}
.filters-main > .input {
  flex: 0 0 210px;
  max-width: 210px;
}
.filters-actions {
  display: flex;
  gap: 0.55rem;
}
.filters-actions .btn {
  min-width: 190px;
}
.create-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr));
  gap: 0.55rem;
  margin-top: 0.55rem;
}
.create-message {
  margin: 0.55rem 0 0;
  color: #0f766e;
  font-size: 0.9rem;
}
.create-overlay {
  position: fixed;
  inset: 0;
  z-index: 70;
  background: rgba(15, 23, 42, 0.28);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 1rem;
}
.create-modal {
  width: min(980px, 96vw);
  max-height: 88vh;
  overflow: auto;
  position: relative;
}
.modal-close {
  position: absolute;
  top: 0.65rem;
  right: 0.7rem;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  width: 28px;
  height: 28px;
  background: #fff;
  cursor: pointer;
  font-size: 1.05rem;
  line-height: 1;
}
.create-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
  margin-top: 0.7rem;
}
.btn.primary {
  background: #2563eb;
  color: #fff;
  border-color: #1d4ed8;
}
.input {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0.5rem 0.6rem;
  font-size: 0.92rem;
  width: 100%;
  min-width: 0;
}
.field-group {
  display: grid;
  gap: 0.28rem;
}
.field-hint {
  margin: 0;
  font-size: 0.78rem;
  color: #64748b;
  line-height: 1.3;
}
.cards-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(230px, 1fr));
  gap: 0.8rem;
}
.employee-card {
  text-align: left;
  cursor: pointer;
  transition: 0.15s ease;
}
.employee-card:hover {
  border-color: #93c5fd;
  transform: translateY(-1px);
}
.employee-card.active {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}
.name {
  font-weight: 700;
  margin-bottom: 0.2rem;
}
.muted {
  color: #64748b;
  margin-bottom: 0.45rem;
}
.meta {
  font-size: 0.88rem;
  color: #334155;
  margin-bottom: 0.2rem;
}
.details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
  align-content: start;
  position: sticky;
  top: 76px;
}
.chart {
  min-height: 230px;
}
.details-card {
  grid-column: 1 / -1;
}
.chart-radar,
.chart-tests {
  min-height: 240px;
}
.chart-kpi {
  grid-column: 1 / -1;
  min-height: 250px;
}
.history-list {
  margin: 0;
  padding-left: 1rem;
}
@media (max-width: 1260px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .details {
    position: static;
  }
  .filters {
    gap: 0.5rem;
  }
  .filters-main {
    gap: 0.55rem;
  }
  .filters-main > .input {
    flex-basis: 190px;
    max-width: 190px;
  }
  .create-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 860px) {
  .cards-grid {
    grid-template-columns: 1fr;
  }
  .details {
    grid-template-columns: 1fr;
  }
  .create-grid {
    grid-template-columns: 1fr;
  }
  .filters-main {
    gap: 0.5rem;
  }
  .filters-main > .input {
    flex: 1 1 100%;
    max-width: 100%;
  }
  .filters-actions {
    display: grid;
    grid-template-columns: 1fr;
  }
  .filters-actions .btn {
    min-width: 0;
  }
  .chart-kpi,
  .details-card {
    grid-column: auto;
  }
}
</style>
