<template>
  <div class="lead-view">
    <div class="card">
      <h2>Панель руководителя команды</h2>
      <p>Оперативная аналитика по вашей команде: риски, динамика KPI, счастье и приоритеты для 1:1.</p>
    </div>

    <div class="kpi-grid">
      <div class="card kpi">
        <div class="kpi-label">Сотрудников в команде</div>
        <div class="kpi-value">{{ stats.teamSize }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Высокий риск</div>
        <div class="kpi-value danger">{{ stats.highRisk }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Среднее счастье</div>
        <div class="kpi-value">{{ stats.avgHappiness }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Средний стресс</div>
        <div class="kpi-value warn">{{ stats.avgStress }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Просроченные тесты</div>
        <div class="kpi-value danger">{{ stats.overdueAssigned }}</div>
      </div>
    </div>

    <div class="card filters">
      <h3>Фокус руководителя</h3>
      <div class="filters-grid">
        <input v-model="search" class="input" type="text" placeholder="Поиск по сотруднику" />
        <select v-model="riskLevel" class="input">
          <option value="">Все уровни риска</option>
          <option value="high">Высокий риск</option>
          <option value="medium">Средний риск</option>
          <option value="low">Низкий риск</option>
        </select>
        <select v-model="sortBy" class="input">
          <option value="risk_score">Сортировать: риск</option>
          <option value="sales">Сортировать: результативность</option>
          <option value="happiness">Сортировать: счастье</option>
          <option value="stress">Сортировать: стресс</option>
        </select>
        <select v-model="sortDir" class="input">
          <option value="desc">По убыванию</option>
          <option value="asc">По возрастанию</option>
        </select>
        <button class="btn" type="button" @click="load">Обновить</button>
      </div>
    </div>

    <div class="charts-grid">
      <div ref="scatterEl" class="card chart chart-scatter" />
      <div ref="riskBarsEl" class="card chart chart-risk-bars" />
      <div ref="teamTrendEl" class="card chart chart-team-trend" />
    </div>

    <div class="card">
      <h3>Сотрудники в фокусе</h3>
      <table class="focus-table">
        <thead>
          <tr>
            <th>Сотрудник</th>
            <th>Подразделение</th>
            <th>Счастье</th>
            <th>Стресс</th>
            <th>Результативность</th>
            <th>Риск</th>
            <th>Рекомендация</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
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
            <td colspan="7">Нет данных по выбранным фильтрам.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>Назначенные тесты команды</h3>
      <table class="assignments-table">
        <thead>
          <tr>
            <th>Сотрудник</th>
            <th>Тест</th>
            <th>Дедлайн</th>
            <th>Статус</th>
            <th>Комментарий</th>
            <th>Назначено</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in assignments" :key="item.id" :class="{ overdue: isOverdue(item) }">
            <td>{{ employeeName(item.employee_id) }}</td>
            <td>{{ item.survey_title }}</td>
            <td>
              {{ item.due_date || "не указан" }}
              <span v-if="isOverdue(item)" class="deadline-flag">Просрочен</span>
            </td>
            <td>{{ assignmentStatusLabel(item.status) }}</td>
            <td>{{ item.note || "—" }}</td>
            <td>{{ formatDateTime(item.created_at) }}</td>
          </tr>
          <tr v-if="!assignments.length">
            <td colspan="6">Назначенных тестов нет.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import * as echarts from "echarts";
import { api } from "../api/client";

type RiskLevel = "high" | "medium" | "low";
type RiskRow = {
  id: string;
  fullName: string;
  email: string;
  orgUnit: string;
  happiness: number;
  stress: number;
  sales: number;
  riskScore: number;
  riskLevel: RiskLevel;
  recommendation: string;
};
type MetricValue = {
  employee_id: string;
  kpi_type_id: string;
  period_start: string;
  value: number;
};
type KpiType = { id: string; code: string; name: string };
type Assignment = {
  id: string;
  employee_id: string;
  survey_title: string;
  status: string;
  due_date: string | null;
  note: string | null;
  created_at: string | null;
};

const scatterEl = ref<HTMLDivElement | null>(null);
const riskBarsEl = ref<HTMLDivElement | null>(null);
const teamTrendEl = ref<HTMLDivElement | null>(null);
const rows = ref<RiskRow[]>([]);
const metricValues = ref<MetricValue[]>([]);
const kpiTypes = ref<KpiType[]>([]);
const scatterPoints = ref<Array<{ x: number; y: number; id?: string; org_unit?: string }>>([]);
const assignments = ref<Assignment[]>([]);

const search = ref("");
const riskLevel = ref<"" | RiskLevel>("");
const sortBy = ref("risk_score");
const sortDir = ref<"asc" | "desc">("desc");

const stats = reactive({
  teamSize: 0,
  highRisk: 0,
  avgHappiness: "0.00",
  avgStress: "0.00",
  overdueAssigned: 0,
});

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

function employeeName(employeeId: string) {
  return rows.value.find((r) => r.id === employeeId)?.fullName ?? employeeId;
}

function isOverdue(item: Assignment) {
  if (item.status !== "ASSIGNED" || !item.due_date) return false;
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  return item.due_date < todayStr;
}

function formatDateTime(value: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const teamOrgName = computed(() => {
  const set = new Set(rows.value.map((r) => r.orgUnit).filter(Boolean));
  if (!set.size) return "Команда";
  if (set.size === 1) return [...set][0];
  return "Смешанная команда";
});

function drawScatter() {
  if (!scatterEl.value) return;
  const chart = echarts.init(scatterEl.value);
  const points = scatterPoints.value;
  const data = points.map((p) => ({ name: p.id ?? "Сотрудник", value: [p.x, p.y], orgUnit: p.org_unit ?? "—" }));
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  chart.setOption({
    title: {
      text: "Результативность / Счастье команды",
      subtext: teamOrgName.value,
      left: 12,
      top: 10,
      textStyle: { fontSize: 16, fontWeight: 700 },
      subtextStyle: { color: "#64748b" },
    },
    grid: { top: 82, left: 60, right: 14, bottom: 48 },
    xAxis: {
      name: "Счастье",
      nameLocation: "middle",
      nameGap: 30,
      min: xs.length ? Math.max(1, Math.min(...xs) - 0.4) : 1,
      max: xs.length ? Math.min(5, Math.max(...xs) + 0.4) : 5,
    },
    yAxis: {
      name: "Результативность",
      nameLocation: "middle",
      nameGap: 46,
      min: ys.length ? Math.max(0, Math.min(...ys) - 10) : 0,
      max: ys.length ? Math.max(...ys) + 10 : 100,
    },
    tooltip: {
      formatter: (params: { data: { name: string; value: number[] } }) =>
        `${params.data.name}<br/>Счастье: ${params.data.value[0].toFixed(2)}<br/>Результативность: ${params.data.value[1].toFixed(2)}`,
    },
    series: [{ type: "scatter", symbolSize: 11, data, itemStyle: { color: "#2563eb" } }],
  });
}

function drawRiskBars() {
  if (!riskBarsEl.value) return;
  const chart = echarts.init(riskBarsEl.value);
  const topRows = [...rows.value].slice(0, 8);
  chart.setOption({
    title: { text: "Карта риска по сотрудникам", left: 12, top: 8, textStyle: { fontSize: 16, fontWeight: 700 } },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { top: 52, left: 140, right: 16, bottom: 22 },
    xAxis: { type: "value", min: 0, max: 100 },
    yAxis: { type: "category", data: topRows.map((r) => r.fullName), inverse: true, axisLabel: { width: 120, overflow: "truncate" } },
    series: [
      {
        type: "bar",
        data: topRows.map((r) => ({ value: r.riskScore, itemStyle: { color: r.riskLevel === "high" ? "#dc2626" : r.riskLevel === "medium" ? "#f59e0b" : "#16a34a" } })),
      },
    ],
  });
}

function drawTeamTrend() {
  if (!teamTrendEl.value) return;
  const chart = echarts.init(teamTrendEl.value);
  const kpiCodeById = new Map(kpiTypes.value.map((x) => [x.id, x.code]));
  const targetCodes = new Set(["SALES", "STRESS"]);
  const filtered = metricValues.value.filter((m) => targetCodes.has(kpiCodeById.get(m.kpi_type_id) ?? ""));
  const periods = [...new Set(filtered.map((f) => f.period_start))].sort((a, b) => a.localeCompare(b));
  const labels = periods.map((t) =>
    new Date(`${t}T00:00:00`).toLocaleDateString("ru-RU", { month: "short", year: "2-digit" }).replace(" г.", ""),
  );

  function seriesByCode(code: string, ruName: string, color: string) {
    const byPeriod = new Map<string, number[]>();
    for (const row of filtered) {
      if ((kpiCodeById.get(row.kpi_type_id) ?? "") !== code) continue;
      const list = byPeriod.get(row.period_start) ?? [];
      list.push(Number(row.value));
      byPeriod.set(row.period_start, list);
    }
    return {
      name: ruName,
      type: "line",
      smooth: true,
      itemStyle: { color },
      data: periods.map((p) => {
        const vals = byPeriod.get(p) ?? [];
        if (!vals.length) return null;
        return Number((vals.reduce((acc, x) => acc + x, 0) / vals.length).toFixed(2));
      }),
    };
  }

  chart.setOption({
    title: { text: "Динамика KPI команды", left: 12, top: 8, textStyle: { fontSize: 16, fontWeight: 700 } },
    legend: { data: ["Продажи", "Стресс"], right: 10, top: 10 },
    tooltip: { trigger: "axis" },
    grid: { top: 52, left: 48, right: 18, bottom: 34 },
    xAxis: { type: "category", data: labels },
    yAxis: { type: "value" },
    series: [seriesByCode("SALES", "Продажи", "#2563eb"), seriesByCode("STRESS", "Стресс", "#f59e0b")],
  });
}

function recalcStats() {
  stats.teamSize = rows.value.length;
  stats.highRisk = rows.value.filter((r) => r.riskLevel === "high").length;
  const avgH = rows.value.length ? rows.value.reduce((acc, r) => acc + r.happiness, 0) / rows.value.length : 0;
  const avgS = rows.value.length ? rows.value.reduce((acc, r) => acc + r.stress, 0) / rows.value.length : 0;
  stats.avgHappiness = avgH.toFixed(2);
  stats.avgStress = avgS.toFixed(2);
  stats.overdueAssigned = assignments.value.filter((x) => isOverdue(x)).length;
}

async function load() {
  const [riskRes, scatterRes, metricsRes, kpiRes, assignmentsRes] = await Promise.all([
    api.get("/surveys/risk-registry", {
      params: {
        search: search.value || undefined,
        risk_level: riskLevel.value || undefined,
        sort_by: sortBy.value,
        sort_dir: sortDir.value,
        page: 1,
        page_size: 200,
      },
    }),
    api.get("/viz/scatter-result-happiness"),
    api.get("/core/metric-values"),
    api.get("/core/kpi-types"),
    api.get("/surveys/assignments/paged", { params: { page: 1, page_size: 200, status: "ASSIGNED" } }),
  ]);

  rows.value = (riskRes.data?.items ?? []).map((x: any) => ({
    id: x.id,
    fullName: x.full_name,
    email: x.email,
    orgUnit: x.org_unit,
    happiness: x.happiness,
    stress: x.stress,
    sales: x.sales,
    riskScore: x.risk_score,
    riskLevel: x.risk_level,
    recommendation: x.recommendation,
  }));
  scatterPoints.value = scatterRes.data?.points ?? [];
  metricValues.value = metricsRes.data ?? [];
  kpiTypes.value = kpiRes.data ?? [];
  assignments.value = assignmentsRes.data?.items ?? [];

  recalcStats();
  drawScatter();
  drawRiskBars();
  drawTeamTrend();
}

onMounted(() => {
  load().catch(() => undefined);
});
</script>

<style scoped>
.lead-view { display: grid; gap: 1rem; }
.lead-view .card { margin-bottom: 0; }
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(170px, 1fr));
  gap: 0.8rem;
}
.kpi-label { color: #64748b; font-size: 0.9rem; }
.kpi-value { font-size: 1.9rem; font-weight: 700; margin-top: 0.2rem; }
.kpi-value.warn { color: #b45309; }
.kpi-value.danger { color: #b91c1c; }
.filters-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr auto;
  gap: 0.55rem;
  margin-top: 0.55rem;
}
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(280px, 1fr));
  gap: 1rem;
}
.chart { min-height: 320px; }
.chart-team-trend { grid-column: 1 / -1; min-height: 300px; }
.focus-table {
  width: 100%;
  border-collapse: collapse;
}
.focus-table th, .focus-table td {
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  padding: 0.5rem;
  vertical-align: top;
}
.focus-table th { background: #f8fafc; color: #334155; font-size: 0.86rem; }
.assignments-table {
  width: 100%;
  border-collapse: collapse;
}
.assignments-table th, .assignments-table td {
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  padding: 0.5rem;
  vertical-align: top;
}
.assignments-table th {
  background: #f8fafc;
  color: #334155;
  font-size: 0.86rem;
}
.assignments-table tr.overdue td {
  background: #fff7ed;
}
.deadline-flag {
  display: inline-block;
  margin-left: 0.4rem;
  padding: 0.08rem 0.42rem;
  border-radius: 999px;
  font-size: 0.75rem;
  color: #b91c1c;
  background: #fee2e2;
  border: 1px solid #fecaca;
}
.muted { color: #64748b; font-size: 0.83rem; }
.risk-pill {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}
.risk-pill.high { color: #991b1b; background: #fee2e2; }
.risk-pill.medium { color: #92400e; background: #fef3c7; }
.risk-pill.low { color: #166534; background: #dcfce7; }
.input {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0.45rem 0.6rem;
  font-size: 0.92rem;
}
.btn {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  padding: 0.45rem 0.7rem;
  cursor: pointer;
}
@media (max-width: 1200px) {
  .kpi-grid { grid-template-columns: 1fr 1fr 1fr; }
  .charts-grid { grid-template-columns: 1fr; }
  .chart-team-trend { grid-column: auto; }
}
@media (max-width: 860px) {
  .kpi-grid { grid-template-columns: 1fr 1fr; }
  .filters-grid { grid-template-columns: 1fr 1fr; }
}
</style>
