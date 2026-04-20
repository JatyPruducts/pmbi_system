<template>
  <div class="home-view">
    <div class="card">
      <h2>Сводная панель PMBI</h2>
      <p v-if="auth.email">Вы вошли как <strong>{{ auth.email }}</strong> ({{ auth.role }})</p>
      <p>Главная показывает оперативные KPI, риски и психоэмоциональный срез компании.</p>
    </div>

    <div class="kpi-grid">
      <div class="card kpi">
        <div class="kpi-label">Сотрудники</div>
        <div class="kpi-value">{{ stats.employees }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Подразделения (с сотрудниками)</div>
        <div class="kpi-value">{{ stats.orgUnits }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Среднее счастье</div>
        <div class="kpi-value">{{ stats.avgHappiness }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Средний стресс</div>
        <div class="kpi-value">{{ stats.avgStress }}</div>
      </div>
    </div>

    <div class="card filters">
      <h3>Фильтры</h3>
      <div class="filters-row">
        <select v-model="selectedOrgUnitId">
          <option value="">Все подразделения</option>
          <option v-for="u in orgUnits" :key="u.id" :value="u.id">{{ u.name }}</option>
        </select>
      </div>
    </div>

    <div class="grid2">
      <div ref="heatEl" class="card chart" style="height: 360px" />
      <div ref="scatterEl" class="card chart" style="height: 360px" />
      <div ref="radarEl" class="card chart" style="height: 360px" />
    </div>

    <div class="card">
      <h3>Подразделения</h3>
      <table class="units-table">
        <thead>
          <tr>
            <th>Подразделение</th>
            <th>Сотрудников</th>
            <th>Средний стресс</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="x in orgSummary" :key="x.name">
            <td>{{ x.name }}</td>
            <td>{{ x.employees }}</td>
            <td>{{ x.avg_stress.toFixed(2) }}</td>
          </tr>
          <tr v-if="!orgSummary.length">
            <td colspan="3">Нет данных</td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import * as echarts from "echarts";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

type EmployeeStatRow = { id: string; org_unit_id: string };
type OrgUnit = { id: string; name: string };
type HeatRow = { org_unit: string; avg_stress: number };

const auth = useAuthStore();
const heatEl = ref<HTMLDivElement | null>(null);
const scatterEl = ref<HTMLDivElement | null>(null);
const radarEl = ref<HTMLDivElement | null>(null);
const heatSeries = ref<HeatRow[]>([]);
const scatterPoints = ref<Array<{ x: number; y: number; id?: string; org_unit?: string; kpi_name?: string }>>([]);
const radarData = ref<{ current: Record<string, number>; scope?: string }>({
  current: {},
  scope: "",
});
const employees = ref<EmployeeStatRow[]>([]);
const orgUnits = ref<OrgUnit[]>([]);
const selectedOrgUnitId = ref("");
const stats = reactive({
  employees: 0,
  orgUnits: 0,
  avgHappiness: "0.0",
  avgStress: "0.0",
});

const selectedOrgUnitName = computed(() => orgUnits.value.find((x) => x.id === selectedOrgUnitId.value)?.name ?? "");

function ruOrgName(name: string) {
  const map: Record<string, string> = {
    Development: "Разработка",
    Marketing: "Маркетинг",
    Sales: "Продажи",
  };
  return map[name] ?? name;
}

function ruCompetencyName(key: string) {
  const map: Record<string, string> = {
    empathy: "Эмпатия",
    stress_mgmt: "Стресс-\nустойчивость",
    collaboration: "Командность",
    focus: "Фокус",
    learning: "Обучаемость",
  };
  return map[key] ?? key;
}

const filteredHeat = computed(() =>
  !selectedOrgUnitName.value ? heatSeries.value : heatSeries.value.filter((x) => x.org_unit === selectedOrgUnitName.value),
);

const filteredEmployees = computed(() =>
  !selectedOrgUnitId.value ? employees.value : employees.value.filter((x) => x.org_unit_id === selectedOrgUnitId.value),
);

const filteredScatter = computed(() =>
  !selectedOrgUnitName.value ? scatterPoints.value : scatterPoints.value.filter((x) => x.org_unit === selectedOrgUnitName.value),
);

const orgSummary = computed(() => {
  const employeeMap = new Map<string, number>();
  for (const e of filteredEmployees.value) {
    const name = orgUnits.value.find((x) => x.id === e.org_unit_id)?.name ?? e.org_unit_id;
    employeeMap.set(name, (employeeMap.get(name) ?? 0) + 1);
  }
  return filteredHeat.value.map((x) => ({
    name: ruOrgName(x.org_unit),
    avg_stress: x.avg_stress,
    employees: employeeMap.get(x.org_unit) ?? 0,
  }));
});

function drawHeatmap(series: HeatRow[]) {
  if (!heatEl.value) return;
  const chart = echarts.init(heatEl.value);
  chart.setOption({
    title: { text: "Стресс по подразделениям", left: "center", top: 8, textStyle: { fontSize: 16 } },
    tooltip: {},
    grid: { top: 64, left: 48, right: 18, bottom: 45 },
    xAxis: { type: "category", data: series.map((s) => ruOrgName(s.org_unit)) },
    yAxis: { type: "value", min: 0, max: 5, name: "Стресс" },
    series: [{ type: "bar", data: series.map((s) => Number(s.avg_stress.toFixed(2))) }],
  });
}

function drawScatter(points: Array<{ x: number; y: number; id?: string; org_unit?: string; kpi_name?: string }>) {
  if (!scatterEl.value) return;
  const chart = echarts.init(scatterEl.value);
  const data = points.map((p) => ({
    name: p.id ?? "employee",
    value: [p.x, p.y],
    orgUnit: p.org_unit ?? "unknown",
    kpiName: p.kpi_name ?? "KPI",
  }));
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = xs.length ? Math.max(1, Math.min(...xs) - 0.5) : 1;
  const maxX = xs.length ? Math.min(5, Math.max(...xs) + 0.5) : 5;
  const minY = ys.length ? Math.max(0, Math.min(...ys) - 10) : 0;
  const maxY = ys.length ? Math.min(100, Math.max(...ys) + 10) : 100;
  chart.setOption({
    title: { text: "Результативность / Счастье", left: "center", top: 8, textStyle: { fontSize: 16 } },
    grid: { top: 64, left: 58, right: 20, bottom: 52 },
    xAxis: { name: "Счастье", min: minX, max: maxX, nameLocation: "middle", nameGap: 30 },
    yAxis: { name: "Результативность", min: minY, max: maxY, nameLocation: "middle", nameGap: 42 },
    tooltip: {
      formatter: (params: { data: { name: string; value: number[]; orgUnit: string; kpiName: string } }) =>
        [
          `<strong>${params.data.name}</strong>`,
          `Подразделение: ${ruOrgName(params.data.orgUnit)}`,
          `Счастье: ${params.data.value[0].toFixed(2)}`,
          `Результативность: ${params.data.value[1].toFixed(2)}`,
        ].join("<br/>"),
    },
    series: [
      {
        type: "scatter",
        data,
        symbolSize: 12,
        itemStyle: { color: "#2563eb" },
      },
    ],
  });
}

function drawRadar(current: Record<string, number>) {
  if (!radarEl.value) return;
  const keys = Object.keys(current);
  if (!keys.length) return;
  const chart = echarts.init(radarEl.value);
  const scopeLabel = radarData.value.scope === "company" ? "Профиль компании" : radarData.value.scope === "team" ? "Профиль команды" : "Профиль сотрудника";
  chart.setOption({
    title: {
      text: "Ключевые компетенции",
      subtext: scopeLabel,
      left: "center",
      top: 6,
      textStyle: { fontSize: 16 },
      subtextStyle: { color: "#64748b", fontSize: 12 },
    },
    tooltip: { trigger: "item" },
    radar: {
      center: ["50%", "62%"],
      radius: "50%",
      name: {
        color: "#64748b",
        fontSize: 12,
      },
      indicator: keys.map((k) => ({ name: ruCompetencyName(k), max: 5 })),
    },
    series: [
      {
        type: "radar",
        data: [
          {
            name: scopeLabel,
            value: keys.map((k) => current[k]),
            areaStyle: { opacity: 0.2 },
          },
        ],
      },
    ],
  });
}

function recalcStats() {
  stats.employees = filteredEmployees.value.length;
  stats.orgUnits = new Set(filteredEmployees.value.map((x) => x.org_unit_id)).size;
  const avg =
    filteredHeat.value.length > 0
      ? filteredHeat.value.reduce((acc, x) => acc + x.avg_stress, 0) / filteredHeat.value.length
      : 0;
  stats.avgStress = avg.toFixed(2);
  const happy =
    filteredScatter.value.length > 0
      ? filteredScatter.value.reduce((acc, x) => acc + x.x, 0) / filteredScatter.value.length
      : 0;
  stats.avgHappiness = happy.toFixed(2);
}

async function reloadRadarForCurrentFilter() {
  const params = selectedOrgUnitId.value ? { org_unit_id: selectedOrgUnitId.value } : undefined;
  const { data } = await api.get("/viz/radar-competencies", { params });
  radarData.value = {
    current: data.current ?? {},
    scope: data.scope ?? "",
  };
  drawRadar(radarData.value.current);
}

watch(selectedOrgUnitId, () => {
  drawHeatmap(filteredHeat.value);
  drawScatter(filteredScatter.value);
  reloadRadarForCurrentFilter().catch(() => undefined);
  recalcStats();
});

onMounted(async () => {
  const [heatRes, scatterRes, radarRes, employeesRes, orgRes] = await Promise.allSettled([
    api.get("/viz/stress-heatmap"),
    api.get("/viz/scatter-result-happiness"),
    api.get("/viz/radar-competencies"),
    api.get("/core/employees"),
    api.get("/core/org-units"),
  ]);

  if (heatRes.status === "fulfilled") {
    heatSeries.value = heatRes.value.data.series ?? [];
    drawHeatmap(filteredHeat.value);
  }

  if (scatterRes.status === "fulfilled") {
    scatterPoints.value = scatterRes.value.data.points ?? [];
    drawScatter(filteredScatter.value);
  }

  if (radarRes.status === "fulfilled") {
    radarData.value = {
      current: radarRes.value.data.current ?? {},
      scope: radarRes.value.data.scope ?? "",
    };
    drawRadar(radarData.value.current);
  }

  if (employeesRes.status === "fulfilled" && Array.isArray(employeesRes.value.data)) {
    employees.value = employeesRes.value.data as EmployeeStatRow[];
  }

  if (orgRes.status === "fulfilled" && Array.isArray(orgRes.value.data)) {
    orgUnits.value = orgRes.value.data;
  }
  recalcStats();
});
</script>

<style scoped>
.home-view {
  display: grid;
  gap: 1rem;
}
.home-view > .card,
.home-view > .kpi-grid,
.home-view > .filters,
.home-view > .grid2 {
  margin: 0;
}
.home-view .card {
  margin-bottom: 0;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}
.kpi {
  margin: 0;
}
.kpi-label {
  color: #64748b;
  font-size: 0.9rem;
}
.kpi-value {
  font-size: 2rem;
  font-weight: 700;
  margin-top: 0.2rem;
}
.chart {
  min-height: 320px;
  margin: 0;
}
.filters-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(180px, 1fr));
  gap: 0.6rem;
  margin-top: 0.65rem;
}
.filters select {
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
}
.hint {
  margin: 0.65rem 0 0;
  color: #334155;
  font-size: 0.9rem;
}
.units-table {
  width: 100%;
  border-collapse: collapse;
}
.units-table th,
.units-table td {
  text-align: left;
  padding: 0.45rem;
  border-bottom: 1px solid #e2e8f0;
}
@media (max-width: 900px) {
  .filters-row {
    grid-template-columns: 1fr;
  }
}
</style>
