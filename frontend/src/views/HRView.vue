<template>
  <div class="hr-view">
    <div class="card">
      <h2>Рабочее место HR</h2>
      <p>Операционный экран: выявление сотрудников в риске, приоритизация и назначение повторных тестов.</p>
    </div>

    <div class="kpi-grid">
      <div class="card kpi">
        <div class="kpi-label">Сотрудники в мониторинге</div>
        <div class="kpi-value">{{ total }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Высокий риск</div>
        <div class="kpi-value danger">{{ highRiskCount }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Средний риск</div>
        <div class="kpi-value warn">{{ mediumRiskCount }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Активных назначений</div>
        <div class="kpi-value">{{ assignedCount }}</div>
      </div>
    </div>

    <div class="card filters">
      <h3>Фильтры реестра рисков</h3>
      <div class="filters-grid">
        <input v-model="search" class="input" type="text" placeholder="Поиск: ФИО, email, подразделение" />
        <select v-model="selectedOrgUnit" class="input">
          <option value="">Все подразделения</option>
          <option v-for="x in orgUnits" :key="x.id" :value="x.id">{{ x.name }}</option>
        </select>
        <select v-model="riskFilter" class="input">
          <option value="">Все уровни риска</option>
          <option value="high">Высокий риск</option>
          <option value="medium">Средний риск</option>
          <option value="low">Низкий риск</option>
        </select>
        <select v-model="sortBy" class="input">
          <option value="risk_score">Сортировка: Риск</option>
          <option value="happiness">Сортировка: Счастье</option>
          <option value="stress">Сортировка: Стресс</option>
          <option value="sales">Сортировка: KPI</option>
        </select>
        <select v-model="sortDir" class="input">
          <option value="desc">По убыванию</option>
          <option value="asc">По возрастанию</option>
        </select>
        <select v-model="pageSize" class="input">
          <option :value="10">10 на страницу</option>
          <option :value="25">25 на страницу</option>
          <option :value="50">50 на страницу</option>
        </select>
        <button type="button" class="btn" @click="load">Обновить</button>
      </div>
    </div>

    <div class="split">
      <div class="card">
        <h3>Реестр сотрудников в фокусе</h3>
        <div class="table-actions">
          <label class="inline">
            <input type="checkbox" :checked="allOnPageSelected" @change="toggleSelectAllOnPage($event)" />
            Выбрать всех на странице
          </label>
          <span class="muted">Выбрано: {{ selectedEmployeeIds.length }}</span>
        </div>
        <table class="risk-table">
          <thead>
            <tr>
              <th></th>
              <th>Сотрудник</th>
              <th>Подразделение</th>
              <th>Счастье</th>
              <th>Стресс</th>
              <th>SALES KPI</th>
              <th>Риск</th>
              <th>Рекомендация</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td><input v-model="selectedEmployeeIds" type="checkbox" :value="row.id" /></td>
              <td>
                <strong>{{ row.fullName }}</strong>
                <div class="muted">{{ row.email }}</div>
              </td>
              <td>{{ row.orgUnit }}</td>
              <td>{{ row.happiness.toFixed(2) }}</td>
              <td>{{ row.stress.toFixed(2) }}</td>
              <td>{{ row.sales.toFixed(2) }}</td>
              <td>
                <span class="risk-pill" :class="row.riskLevel">{{ riskLabel(row.riskLevel) }} ({{ row.riskScore }})</span>
              </td>
              <td>{{ row.recommendation }}</td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="8">Нет сотрудников по выбранным фильтрам.</td>
            </tr>
          </tbody>
        </table>
        <div class="pagination">
          <button class="btn small" type="button" :disabled="page <= 1 || loading" @click="goToPage(page - 1)">Назад</button>
          <span>Страница {{ page }} из {{ totalPages }}</span>
          <button class="btn small" type="button" :disabled="page >= totalPages || loading" @click="goToPage(page + 1)">Вперед</button>
        </div>
      </div>

      <div class="side">
        <div ref="riskChartEl" class="card chart" style="height: 320px" />
        <div class="card">
          <h3>Назначить тест</h3>
          <div v-if="selectedRows.length === 1" class="assign-target">
            <div><strong>Сотрудник:</strong> {{ selectedRows[0].fullName }}</div>
            <div><strong>Подразделение:</strong> {{ selectedRows[0].orgUnit }}</div>
            <div><strong>Риск:</strong> {{ riskLabel(selectedRows[0].riskLevel) }} ({{ selectedRows[0].riskScore }})</div>
          </div>
          <div v-else-if="selectedRows.length > 1" class="assign-target">
            <div><strong>Сотрудник:</strong> Выбрано {{ selectedRows.length }} сотрудников</div>
            <div>
              <strong>Подразделение:</strong>
              {{ selectedOrgCount === 1 ? selectedRows[0].orgUnit : `из ${selectedOrgCount} подразделений` }}
            </div>
            <div><strong>Риск:</strong> Средний по выборке — {{ averageSelectedRisk.toFixed(1) }}</div>
          </div>
          <div v-else class="assign-target">
            <div>Отметьте одного или нескольких сотрудников чекбоксами в реестре.</div>
          </div>
          <div class="assign-form">
            <select v-model="assignmentSurveyId" class="input">
              <option value="">Выберите тест</option>
              <option v-for="s in surveys" :key="s.id" :value="s.id">{{ s.title }} ({{ s.template }})</option>
            </select>
            <input v-model="assignmentDueDate" class="input" type="date" />
            <textarea v-model="assignmentNote" class="input" rows="4" placeholder="Комментарий сотруднику (что нужно улучшить)" />
            <button
              class="btn"
              type="button"
              :disabled="!selectedRows.length || !assignmentSurveyId || assigning"
              @click="submitAssignment"
            >
              {{ assigning ? "Назначаем..." : selectedRows.length ? `Направить ${selectedRows.length} сотрудникам` : "Направить на тест" }}
            </button>
            <p v-if="assignMsg" class="assign-msg">{{ assignMsg }}</p>
          </div>
        </div>

        <div class="card">
          <h3>Последние назначения</h3>
          <label class="inline" style="margin-bottom: 0.45rem;">
            <input v-model="assignedOnly" type="checkbox" />
            Только назначенные
          </label>
          <ul class="assignments" v-if="visibleAssignments.length">
            <li v-for="item in visibleAssignments" :key="item.id">
              <strong>{{ assignmentEmployeeName(item.employee_id) }}</strong> — {{ item.survey_title }}
              <div class="muted">Статус: {{ assignmentStatusLabel(item.status) }} | Дедлайн: {{ item.due_date || "не указан" }}</div>
              <button
                v-if="item.status === 'ASSIGNED'"
                type="button"
                class="btn small danger"
                :disabled="assigning"
                @click="revokeAssignment(item.id)"
              >
                Отозвать
              </button>
            </li>
          </ul>
          <p v-else>По выбранному фильтру назначений нет.</p>
          <div class="pagination">
            <button class="btn small" type="button" :disabled="assignmentsPage <= 1 || loadingAssignments" @click="goToAssignmentsPage(assignmentsPage - 1)">
              Назад
            </button>
            <span>Страница {{ assignmentsPage }} из {{ assignmentsTotalPages }}</span>
            <button
              class="btn small"
              type="button"
              :disabled="assignmentsPage >= assignmentsTotalPages || loadingAssignments"
              @click="goToAssignmentsPage(assignmentsPage + 1)"
            >
              Вперед
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import { api } from "../api/client";

type Survey = { id: string; title: string; template: string };
type Assignment = { id: string; employee_id: string; survey_title: string; status: string; due_date: string | null };
type RiskLevel = "high" | "medium" | "low";
type RiskRow = {
  id: string;
  fullName: string;
  email: string;
  orgUnitId: string;
  orgUnit: string;
  happiness: number;
  stress: number;
  sales: number;
  riskScore: number;
  riskLevel: RiskLevel;
  recommendation: string;
};

const rows = ref<RiskRow[]>([]);
const surveys = ref<Survey[]>([]);
const assignments = ref<Assignment[]>([]);
const riskChartEl = ref<HTMLDivElement | null>(null);
const orgSummary = ref<Array<{ org_unit: string; high: number; medium: number; low: number }>>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(25);
const loading = ref(false);
const loadingAssignments = ref(false);

const search = ref("");
const selectedOrgUnit = ref("");
const riskFilter = ref<"" | RiskLevel>("");
const sortBy = ref("risk_score");
const sortDir = ref<"asc" | "desc">("desc");
const selectedEmployeeIds = ref<string[]>([]);

const assignmentSurveyId = ref("");
const assignmentDueDate = ref("");
const assignmentNote = ref("");
const assignMsg = ref("");
const assigning = ref(false);
const assignedOnly = ref(false);

const assignmentsPage = ref(1);
const assignmentsPageSize = ref(5);
const assignmentsTotal = ref(0);

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
const assignmentsTotalPages = computed(() => Math.max(1, Math.ceil(assignmentsTotal.value / assignmentsPageSize.value)));
const allOnPageSelected = computed(() => rows.value.length > 0 && rows.value.every((x) => selectedEmployeeIds.value.includes(x.id)));
const selectedRows = computed(() => rows.value.filter((x) => selectedEmployeeIds.value.includes(x.id)));
const selectedOrgCount = computed(() => new Set(selectedRows.value.map((x) => x.orgUnitId)).size);
const averageSelectedRisk = computed(() => {
  if (!selectedRows.value.length) return 0;
  return selectedRows.value.reduce((acc, x) => acc + x.riskScore, 0) / selectedRows.value.length;
});

const orgUnits = computed(() => {
  const map = new Map<string, string>();
  for (const c of rows.value) {
    if (!map.has(c.orgUnitId)) map.set(c.orgUnitId, c.orgUnit ?? c.orgUnitId);
  }
  return [...map.entries()].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));
});

const highRiskCount = computed(() => rows.value.filter((x) => x.riskLevel === "high").length);
const mediumRiskCount = computed(() => rows.value.filter((x) => x.riskLevel === "medium").length);
const assignedCount = computed(() => assignments.value.filter((x) => x.status === "ASSIGNED").length);
const visibleAssignments = computed(() =>
  assignedOnly.value ? assignments.value.filter((x) => x.status === "ASSIGNED") : assignments.value,
);

function riskLabel(level: RiskLevel) {
  if (level === "high") return "Высокий";
  if (level === "medium") return "Средний";
  return "Низкий";
}
function assignmentStatusLabel(status: string) {
  if (status === "ASSIGNED") return "Назначен";
  if (status === "COMPLETED") return "Пройден";
  if (status === "REVOKED") return "Отозван";
  return status;
}
function assignmentEmployeeName(employeeId: string) {
  return rows.value.find((x) => x.id === employeeId)?.fullName ?? employeeId;
}

function drawRiskChart() {
  if (!riskChartEl.value) return;
  const chart = echarts.init(riskChartEl.value);
  const orgs = orgSummary.value.map((x) => x.org_unit);
  chart.setOption({
    title: { text: "Риск по подразделениям", left: "center", top: 8, textStyle: { fontSize: 16 } },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 34, data: ["Высокий", "Средний", "Низкий"] },
    grid: { top: 70, left: 45, right: 20, bottom: 40 },
    xAxis: { type: "category", data: orgs },
    yAxis: { type: "value", minInterval: 1 },
    series: [
      { name: "Высокий", type: "bar", stack: "risk", data: orgSummary.value.map((o) => o.high), itemStyle: { color: "#dc2626" } },
      { name: "Средний", type: "bar", stack: "risk", data: orgSummary.value.map((o) => o.medium), itemStyle: { color: "#f59e0b" } },
      { name: "Низкий", type: "bar", stack: "risk", data: orgSummary.value.map((o) => o.low), itemStyle: { color: "#16a34a" } },
    ],
  });
}

function toggleSelectAllOnPage(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  if (!checked) {
    selectedEmployeeIds.value = selectedEmployeeIds.value.filter((id) => !rows.value.find((x) => x.id === id));
    return;
  }
  const ids = rows.value.map((x) => x.id);
  selectedEmployeeIds.value = [...new Set([...selectedEmployeeIds.value, ...ids])];
}

function goToPage(next: number) {
  page.value = Math.max(1, Math.min(next, totalPages.value));
}
function goToAssignmentsPage(next: number) {
  assignmentsPage.value = Math.max(1, Math.min(next, assignmentsTotalPages.value));
}

async function submitAssignment() {
  if (!assignmentSurveyId.value) {
    assignMsg.value = "Выберите тест в блоке назначения.";
    return;
  }
  if (!selectedRows.value.length) {
    assignMsg.value = "Выберите сотрудников для назначения.";
    return;
  }
  assigning.value = true;
  assignMsg.value = "";
  try {
    const { data } = await api.post("/surveys/assignments/bulk", {
      employee_ids: selectedRows.value.map((x) => x.id),
      survey_id: assignmentSurveyId.value,
      due_date: assignmentDueDate.value || null,
      note: assignmentNote.value || null,
    });
    assignMsg.value = `Тест назначен: ${data.created ?? selectedRows.value.length} сотрудникам.`;
    selectedEmployeeIds.value = [];
    assignmentNote.value = "";
    assignmentDueDate.value = "";
    await loadAssignments();
  } catch (_e) {
    assignMsg.value = "Не удалось назначить тест. Проверьте данные и попробуйте снова.";
  } finally {
    assigning.value = false;
  }
}

async function revokeAssignment(assignmentId: string) {
  assigning.value = true;
  assignMsg.value = "";
  try {
    await api.post(`/surveys/assignments/${assignmentId}/revoke`);
    assignMsg.value = "Назначение отозвано.";
    await loadAssignments();
  } catch (_e) {
    assignMsg.value = "Не удалось отозвать назначение.";
  } finally {
    assigning.value = false;
  }
}

async function loadAssignments() {
  loadingAssignments.value = true;
  const { data } = await api.get("/surveys/assignments/paged", {
    params: {
      page: assignmentsPage.value,
      page_size: assignmentsPageSize.value,
      status: assignedOnly.value ? "ASSIGNED" : undefined,
    },
  });
  assignments.value = data?.items ?? [];
  assignmentsTotal.value = data?.total ?? 0;
  loadingAssignments.value = false;
}

async function load() {
  loading.value = true;
  const [registryRes, surveysRes] = await Promise.all([
    api.get("/surveys/risk-registry", {
      params: {
        search: search.value || undefined,
        org_unit_id: selectedOrgUnit.value || undefined,
        risk_level: riskFilter.value || undefined,
        sort_by: sortBy.value,
        sort_dir: sortDir.value,
        page: page.value,
        page_size: pageSize.value,
      },
    }),
    api.get("/surveys"),
  ]);
  rows.value = (registryRes.data?.items ?? []).map((x: any) => ({
    id: x.id,
    fullName: x.full_name,
    email: x.email,
    orgUnitId: x.org_unit_id,
    orgUnit: x.org_unit,
    happiness: x.happiness,
    stress: x.stress,
    sales: x.sales,
    riskScore: x.risk_score,
    riskLevel: x.risk_level,
    recommendation: x.recommendation,
  }));
  total.value = registryRes.data?.total ?? 0;
  orgSummary.value = registryRes.data?.org_summary ?? [];
  surveys.value = surveysRes.data ?? [];
  if (!assignmentSurveyId.value && surveys.value.length) {
    assignmentSurveyId.value = surveys.value[0].id;
  }
  selectedEmployeeIds.value = selectedEmployeeIds.value.filter((id) => rows.value.some((x) => x.id === id));
  drawRiskChart();
  loading.value = false;
}

watch([search, selectedOrgUnit, riskFilter, sortBy, sortDir, pageSize], () => {
  page.value = 1;
  load().catch(() => undefined);
});
watch(page, () => load().catch(() => undefined));
watch(assignmentsPage, () => loadAssignments().catch(() => undefined));
watch(assignedOnly, () => {
  assignmentsPage.value = 1;
  loadAssignments().catch(() => undefined);
});

onMounted(async () => {
  await load();
  await loadAssignments();
});
</script>

<style scoped>
.hr-view { display: grid; gap: 1rem; }
.hr-view .card { margin-bottom: 0; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 0.8rem; }
.kpi-label { color: #64748b; font-size: 0.88rem; }
.kpi-value { font-size: 1.8rem; font-weight: 700; margin-top: 0.2rem; }
.kpi-value.warn { color: #b45309; }
.kpi-value.danger { color: #b91c1c; }
.filters-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr auto; gap: 0.55rem; }
.split { display: grid; grid-template-columns: minmax(720px, 1fr) 420px; gap: 1rem; }
.side { display: flex; flex-direction: column; gap: 1rem; }
.risk-table { width: 100%; border-collapse: collapse; }
.table-actions { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.6rem; gap: 0.6rem; }
.inline { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.9rem; }
.risk-table th, .risk-table td { border-bottom: 1px solid #e2e8f0; text-align: left; padding: 0.5rem; vertical-align: top; }
.risk-table th { color: #334155; background: #f8fafc; font-size: 0.86rem; }
.risk-pill { display: inline-block; padding: 0.12rem 0.5rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
.risk-pill.high { color: #991b1b; background: #fee2e2; }
.risk-pill.medium { color: #92400e; background: #fef3c7; }
.risk-pill.low { color: #166534; background: #dcfce7; }
.assign-target { margin-bottom: 0.6rem; font-size: 0.9rem; }
.assign-form { display: grid; gap: 0.45rem; }
.assign-msg { margin: 0; color: #0f766e; font-size: 0.9rem; }
.assignments { margin: 0; padding-left: 1rem; }
.assignments li { margin-bottom: 0.45rem; }
.muted { color: #64748b; font-size: 0.84rem; }
.input { border: 1px solid #cbd5e1; border-radius: 10px; padding: 0.45rem 0.55rem; font-size: 0.92rem; }
.btn { border: 1px solid #cbd5e1; border-radius: 10px; background: #f8fafc; padding: 0.45rem 0.7rem; cursor: pointer; }
.btn.small { padding: 0.3rem 0.5rem; font-size: 0.84rem; }
.btn.small.danger { border-color: #fecaca; color: #b91c1c; background: #fff5f5; }
.pagination { display: flex; justify-content: flex-end; align-items: center; gap: 0.6rem; margin-top: 0.6rem; }
.chart { min-height: 320px; }
@media (max-width: 1360px) { .split { grid-template-columns: 1fr; } }
@media (max-width: 980px) {
  .kpi-grid { grid-template-columns: 1fr 1fr; }
  .filters-grid { grid-template-columns: 1fr 1fr; }
}
</style>
