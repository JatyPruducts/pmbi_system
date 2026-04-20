<template>
  <div class="employee-view">
    <div class="card">
      <h2>Личный кабинет сотрудника</h2>
      <p>Здесь собрана ваша карточка и история метрик. Во вкладке «Тесты» доступны назначения и пройденные опросы.</p>
      <div class="tabs">
        <button class="tab-btn" :class="{ active: activeTab === 'profile' }" type="button" @click="activeTab = 'profile'">
          Личный кабинет
        </button>
        <button class="tab-btn" :class="{ active: activeTab === 'tests' }" type="button" @click="activeTab = 'tests'">
          Тесты
        </button>
      </div>
    </div>

    <template v-if="activeTab === 'profile'">
      <div class="profile-grid">
        <div class="card">
          <div class="profile-head">
            <h3>{{ employeeCard?.full_name || employeeCard?.external_id || "Профиль сотрудника" }}</h3>
            <button type="button" class="mini-btn" @click="showPasswordModal = true">Сменить пароль</button>
          </div>
          <div class="meta">Email: {{ employeeCard?.email || "—" }}</div>
          <div class="meta">Роль: {{ employeeCard?.role || "—" }}</div>
          <div class="meta">Подразделение: {{ employeeCard?.org_unit_name || "—" }}</div>
          <div class="meta">Должность: {{ employeeCard?.position_title || "—" }}</div>
          <div class="meta">Руководитель: {{ employeeCard?.manager_name || "—" }}</div>
          <div class="meta">Дата найма: {{ employeeCard?.hire_date || "—" }}</div>
        </div>

        <div class="card">
          <h3>Рекомендации</h3>
          <ul class="recommendations">
            <li v-for="(r, i) in recs" :key="i">{{ r }}</li>
          </ul>
        </div>

        <div ref="radarEl" class="card chart" />
        <div ref="testsEl" class="card chart" />
        <div ref="kpiEl" class="card chart wide" />
      </div>
    </template>

    <template v-else>
      <div class="tests-grid">
        <div class="card">
          <h3>Нужно пройти</h3>
          <table class="tests-table">
            <thead>
              <tr>
                <th>Тест</th>
                <th>Дедлайн</th>
                <th>Комментарий</th>
                <th>Статус</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pendingAssignments" :key="item.id" :class="{ overdue: isOverdue(item) }">
                <td>{{ item.survey_title }}</td>
                <td>
                  {{ item.due_date || "не указан" }}
                  <span v-if="isOverdue(item)" class="deadline-flag">Просрочен</span>
                </td>
                <td>{{ item.note || "—" }}</td>
                <td>{{ assignmentStatusLabel(item.status) }}</td>
                <td>
                  <button type="button" class="pass-btn" @click="openPassModal(item)">Пройти</button>
                </td>
              </tr>
              <tr v-if="!pendingAssignments.length">
                <td colspan="5">Сейчас нет тестов к прохождению.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <h3>Пройденные тесты</h3>
          <table class="tests-table">
            <thead>
              <tr>
                <th>Тест</th>
                <th>Завершен</th>
                <th>Итог</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in completedAssignments" :key="item.id">
                <td>{{ item.survey_title }}</td>
                <td>{{ formatDateTime(item.completed_at) }}</td>
                <td>{{ completedSummary(item.survey_id) }}</td>
              </tr>
              <tr v-if="!completedAssignments.length">
                <td colspan="3">Пока нет пройденных тестов.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <div v-if="showPasswordModal" class="password-overlay">
      <div class="password-modal">
        <button type="button" class="modal-close" aria-label="Закрыть" @click="closePasswordModal">×</button>
        <h3>Смена пароля</h3>
        <p class="password-subtitle">Введите текущий пароль и задайте новый для входа в систему.</p>
        <div class="password-grid">
          <input v-model="passwordForm.current_password" class="input" type="password" placeholder="Текущий пароль" />
          <input v-model="passwordForm.new_password" class="input" type="password" placeholder="Новый пароль (мин. 6 символов)" />
          <input v-model="passwordForm.confirm_password" class="input" type="password" placeholder="Повторите новый пароль" />
        </div>
        <p v-if="passwordMessage" class="password-message">{{ passwordMessage }}</p>
        <div class="modal-actions">
          <button type="button" class="tab-btn" @click="closePasswordModal">Отмена</button>
          <button type="button" class="tab-btn primary" :disabled="changingPassword" @click="changePassword">
            {{ changingPassword ? "Сохраняем..." : "Изменить пароль" }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="passModalOpen && activeSurvey && activeAssignment" class="pass-overlay">
      <div class="pass-modal">
        <button type="button" class="modal-close" aria-label="Закрыть" @click="closePassModal">×</button>
        <h3>Прохождение теста: {{ activeAssignment.survey_title }}</h3>
        <p class="muted">Выберите по одному варианту ответа в каждом вопросе.</p>

        <div class="pass-questions">
          <div v-for="question in activeSurvey.questions" :key="question.id" class="question-card">
            <h4>{{ question.text }}</h4>
            <div class="options">
              <label v-for="opt in questionOptions(question)" :key="opt.id" class="option-item">
                <input v-model="answerMap[question.id]" type="radio" :name="question.id" :value="opt.id" />
                <span>{{ opt.text }}</span>
              </label>
            </div>
          </div>
        </div>

        <p v-if="passMessage" class="pass-message">{{ passMessage }}</p>
        <div class="modal-actions">
          <button type="button" class="tab-btn" @click="closePassModal">Отмена</button>
          <button type="button" class="tab-btn primary" :disabled="!canSubmitPass || submittingPass" @click="submitPass">
            {{ submittingPass ? "Отправляем..." : "Отправить ответы" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import { api } from "../api/client";

type TabId = "profile" | "tests";
type EmployeeCard = {
  id: string;
  full_name: string | null;
  email: string | null;
  role: string | null;
  external_id: string | null;
  org_unit_name: string | null;
  position_title: string | null;
  manager_name: string | null;
  hire_date: string | null;
};
type MetricValue = {
  kpi_type_id: string;
  period_start: string;
  value: number;
};
type KpiType = { id: string; name: string };
type SurveyResponse = {
  survey_id: string;
  submitted_at: string;
  scores: Record<string, number>;
};
type SurveyQuestion = {
  id: string;
  text: string;
  question_type: string;
  meta?: {
    options?: Array<{ id: string; text: string; factor?: string; points?: number }>;
    ui_blocks?: Array<{ type: string; text?: string }>;
  };
};
type SurveyDefinition = {
  id: string;
  title: string;
  template: string;
  version: number;
  questions: SurveyQuestion[];
};
type Assignment = {
  id: string;
  survey_id: string;
  survey_title: string;
  status: string;
  due_date: string | null;
  note: string | null;
  completed_at: string | null;
};

const activeTab = ref<TabId>("profile");
const radarEl = ref<HTMLDivElement | null>(null);
const testsEl = ref<HTMLDivElement | null>(null);
const kpiEl = ref<HTMLDivElement | null>(null);

const employeeCard = ref<EmployeeCard | null>(null);
const metricValues = ref<MetricValue[]>([]);
const kpiTypes = ref<KpiType[]>([]);
const responses = ref<SurveyResponse[]>([]);
const assignments = ref<Assignment[]>([]);
const surveys = ref<SurveyDefinition[]>([]);
const recs = ref<string[]>([]);
const employeeId = ref<string | null>(null);
const passModalOpen = ref(false);
const showPasswordModal = ref(false);
const activeAssignment = ref<Assignment | null>(null);
const answerMap = ref<Record<string, string>>({});
const passMessage = ref("");
const submittingPass = ref(false);
const passwordForm = ref({
  current_password: "",
  new_password: "",
  confirm_password: "",
});
const changingPassword = ref(false);
const passwordMessage = ref("");

const pendingAssignments = computed(() => assignments.value.filter((x) => x.status === "ASSIGNED"));
const completedAssignments = computed(() => assignments.value.filter((x) => x.status === "COMPLETED"));
const activeSurvey = computed(() => surveys.value.find((x) => x.id === activeAssignment.value?.survey_id) ?? null);
const canSubmitPass = computed(() => {
  if (!activeSurvey.value) return false;
  for (const q of activeSurvey.value.questions) {
    const options = questionOptions(q);
    if (options.length && !answerMap.value[q.id]) return false;
  }
  return true;
});

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

function ruKpiName(name: string) {
  const n = name.trim().toLowerCase();
  if (n === "nps" || n === "net promoter score") return "NPS";
  if (n === "sales" || n === "sales volume") return "Продажи";
  if (n === "stress" || n === "stress index") return "Стресс";
  return name;
}

function assignmentStatusLabel(status: string) {
  if (status === "ASSIGNED") return "Назначен";
  if (status === "COMPLETED") return "Пройден";
  if (status === "REVOKED") return "Отозван";
  return status;
}

function formatDate(v: string) {
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("ru-RU");
}

function formatDateTime(v: string | null) {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function isOverdue(item: Assignment) {
  if (item.status !== "ASSIGNED" || !item.due_date) return false;
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  return item.due_date < today;
}

function completedSummary(surveyId: string) {
  const bySurvey = responses.value.find((x) => x.survey_id === surveyId);
  if (!bySurvey?.scores) return "—";
  const likert = bySurvey.scores.likert_mean;
  const burnout = bySurvey.scores.burnout_index;
  const parts = [];
  if (typeof likert === "number") parts.push(`Счастье: ${likert.toFixed(2)}`);
  if (typeof burnout === "number") parts.push(`Выгорание: ${burnout.toFixed(2)}`);
  return parts.length ? parts.join(" | ") : "—";
}

function questionOptions(question: SurveyQuestion) {
  const opts = question.meta?.options;
  return Array.isArray(opts) ? opts : [];
}

function drawRadar(data: { current: Record<string, number> }) {
  if (!radarEl.value) return;
  const keys = Object.keys(data.current || {});
  if (!keys.length) return;
  const ch = echarts.init(radarEl.value);
  ch.setOption({
    title: { text: "Психологический портрет", left: 12, top: 8, textStyle: { fontSize: 16, fontWeight: 700 } },
    tooltip: { trigger: "item" },
    radar: {
      center: ["50%", "57%"],
      radius: "56%",
      indicator: keys.map((k) => ({ name: ruCompetencyName(k), max: 5 })),
    },
    series: [{ type: "radar", data: [{ name: "Вы", value: keys.map((k) => data.current[k] ?? 0) }] }],
  });
}

function drawTestsChart() {
  if (!testsEl.value) return;
  const ch = echarts.init(testsEl.value);
  const ordered = [...responses.value].sort((a, b) => a.submitted_at.localeCompare(b.submitted_at));
  ch.setOption({
    title: { text: "Динамика тестов", left: 12, top: 8, textStyle: { fontSize: 16, fontWeight: 700 } },
    tooltip: { trigger: "axis" },
    legend: { data: ["Счастье", "Выгорание"], right: 12, top: 10 },
    grid: { top: 52, left: 42, right: 16, bottom: 30 },
    xAxis: { type: "category", data: ordered.map((x) => formatDate(x.submitted_at)) },
    yAxis: { type: "value" },
    series: [
      { name: "Счастье", type: "line", smooth: true, data: ordered.map((x) => x.scores.likert_mean ?? null) },
      { name: "Выгорание", type: "line", smooth: true, data: ordered.map((x) => x.scores.burnout_index ?? null) },
    ],
  });
}

function drawKpiChart() {
  if (!kpiEl.value) return;
  const ch = echarts.init(kpiEl.value);
  const byKpi = new Map<string, Array<{ t: string; v: number }>>();
  for (const row of metricValues.value) {
    if (!byKpi.has(row.kpi_type_id)) byKpi.set(row.kpi_type_id, []);
    byKpi.get(row.kpi_type_id)?.push({ t: row.period_start, v: row.value });
  }
  const series = [...byKpi.entries()].map(([kpiId, points]) => {
    const label = ruKpiName(kpiTypes.value.find((k) => k.id === kpiId)?.name ?? kpiId);
    const sorted = [...points].sort((a, b) => a.t.localeCompare(b.t));
    return { name: label, type: "line", data: sorted.map((x) => [x.t, x.v]), smooth: true };
  });
  ch.setOption({
    title: { text: "Динамика KPI", left: 12, top: 8, textStyle: { fontSize: 16, fontWeight: 700 } },
    tooltip: { trigger: "axis" },
    legend: { type: "scroll", right: 12, top: 10 },
    grid: { top: 52, left: 46, right: 16, bottom: 32 },
    xAxis: { type: "time" },
    yAxis: { type: "value" },
    series,
  });
}

function buildRecommendations(current: Record<string, number>) {
  const next: string[] = [];
  if ((current.stress_mgmt ?? 5) < 3) {
    next.push("Снижайте нагрузку короткими перерывами и планируйте фокус-сессии без переключений.");
  }
  if ((current.focus ?? 5) < 3) {
    next.push("Попробуйте метод Pomodoro: 25 минут фокуса + 5 минут отдыха.");
  }
  if ((current.collaboration ?? 5) < 3) {
    next.push("Согласуйте ожидания с руководителем на еженедельном 1:1.");
  }
  if (!next.length) {
    next.push("Динамика стабильная. Поддерживайте текущий ритм и планово проходите тесты.");
  }
  recs.value = next;
}

async function redrawProfileCharts() {
  await nextTick();
  if (!employeeId.value) return;
  const radarRes = await api.get("/viz/radar-competencies", { params: { employee_id: employeeId.value } });
  const radarData = { current: radarRes.data?.current ?? {} };
  buildRecommendations(radarData.current);
  drawRadar(radarData);
  drawTestsChart();
  drawKpiChart();
}

async function changePassword() {
  passwordMessage.value = "";
  if (!passwordForm.value.current_password || !passwordForm.value.new_password || !passwordForm.value.confirm_password) {
    passwordMessage.value = "Заполните все поля для смены пароля.";
    return;
  }
  if (passwordForm.value.new_password.length < 6) {
    passwordMessage.value = "Новый пароль должен быть не короче 6 символов.";
    return;
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    passwordMessage.value = "Новый пароль и подтверждение не совпадают.";
    return;
  }
  changingPassword.value = true;
  try {
    await api.post("/auth/change-password", {
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password,
    });
    passwordMessage.value = "Пароль успешно обновлен.";
    passwordForm.value = { current_password: "", new_password: "", confirm_password: "" };
    showPasswordModal.value = false;
  } catch (_e) {
    passwordMessage.value = "Не удалось сменить пароль. Проверьте текущий пароль.";
  } finally {
    changingPassword.value = false;
  }
}

function closePasswordModal() {
  showPasswordModal.value = false;
  passwordMessage.value = "";
  passwordForm.value = { current_password: "", new_password: "", confirm_password: "" };
}

function openPassModal(item: Assignment) {
  activeAssignment.value = item;
  passMessage.value = "";
  if (!activeSurvey.value) {
    passMessage.value = "Для этого теста не найдена структура. Попробуйте обновить страницу.";
    return;
  }
  const initial: Record<string, string> = {};
  for (const q of activeSurvey.value.questions) {
    initial[q.id] = "";
  }
  answerMap.value = initial;
  passModalOpen.value = true;
}

function closePassModal() {
  passModalOpen.value = false;
  activeAssignment.value = null;
  answerMap.value = {};
  passMessage.value = "";
}

async function loadEmployeeData() {
  if (!employeeId.value) return;
  const [radarRes, responsesRes, metricsRes, kpiRes, assignmentsRes, surveysRes] = await Promise.all([
    api.get("/viz/radar-competencies", { params: { employee_id: employeeId.value } }),
    api.get("/surveys/responses/me"),
    api.get("/core/metric-values", { params: { employee_id: employeeId.value } }),
    api.get("/core/kpi-types"),
    api.get("/surveys/assignments"),
    api.get("/surveys"),
  ]);

  responses.value = responsesRes.data ?? [];
  metricValues.value = metricsRes.data ?? [];
  kpiTypes.value = kpiRes.data ?? [];
  assignments.value = assignmentsRes.data ?? [];
  surveys.value = surveysRes.data ?? [];

  const radarData = {
    current: radarRes.data?.current ?? {},
  };
  buildRecommendations(radarData.current);
  drawRadar(radarData);
  drawTestsChart();
  drawKpiChart();
}

async function submitPass() {
  if (!activeSurvey.value || !activeAssignment.value) return;
  passMessage.value = "";
  const answers: Record<string, number> = {};
  for (const q of activeSurvey.value.questions) {
    const options = questionOptions(q);
    if (!options.length) continue;
    const selectedId = answerMap.value[q.id];
    const selected = options.find((o) => o.id === selectedId);
    if (!selected) continue;
    answers[q.id] = Number(selected.points ?? 0);
  }
  submittingPass.value = true;
  try {
    await api.post("/surveys/responses", {
      survey_id: activeSurvey.value.id,
      version: activeSurvey.value.version,
      answers,
    });
    closePassModal();
    await loadEmployeeData();
  } catch (_e) {
    passMessage.value = "Не удалось отправить ответы. Проверьте заполнение и попробуйте снова.";
  } finally {
    submittingPass.value = false;
  }
}

onMounted(async () => {
  const cardsRes = await api.get("/core/employees/cards");
  employeeCard.value = (cardsRes.data ?? [])[0] ?? null;
  employeeId.value = employeeCard.value?.id ?? null;
  if (!employeeId.value) return;
  await loadEmployeeData();
});

watch(activeTab, (tab) => {
  if (tab !== "profile") return;
  redrawProfileCharts().catch(() => undefined);
});
</script>

<style scoped>
.employee-view { display: grid; gap: 1rem; }
.employee-view .card { margin-bottom: 0; }
.tabs { display: flex; gap: 0.55rem; margin-top: 0.8rem; }
.tab-btn {
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #f8fafc;
  padding: 0.42rem 0.8rem;
  cursor: pointer;
}
.tab-btn.active {
  background: #dbeafe;
  border-color: #93c5fd;
  color: #1e3a8a;
  font-weight: 600;
}
.profile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(300px, 1fr));
  gap: 1rem;
}
.profile-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
.profile-head h3 { margin: 0; }
.mini-btn {
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #f8fafc;
  padding: 0.28rem 0.65rem;
  font-size: 0.8rem;
  cursor: pointer;
}
.chart { min-height: 320px; }
.chart.wide { grid-column: 1 / -1; min-height: 300px; }
.meta { color: #334155; margin-bottom: 0.25rem; font-size: 0.92rem; }
.recommendations { margin: 0; padding-left: 1rem; }
.password-grid {
  display: grid;
  gap: 0.7rem;
  margin-top: 0.65rem;
}
.password-grid .input {
  width: 100%;
  max-width: 460px;
  border: 1px solid #cbd5e1;
  border-radius: 14px;
  padding: 0.72rem 0.92rem;
  font-size: 0.97rem;
  background: #f8fafc;
}
.password-grid .input:focus {
  outline: none;
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2);
}
.password-message {
  margin: 0.45rem 0 0;
  color: #0f766e;
  font-size: 0.88rem;
}
.tests-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}
.tests-table {
  width: 100%;
  border-collapse: collapse;
}
.tests-table th, .tests-table td {
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  padding: 0.5rem;
  vertical-align: top;
}
.tests-table th { background: #f8fafc; color: #334155; font-size: 0.86rem; }
.tests-table tr.overdue td { background: #fff7ed; }
.pass-btn {
  border: 1px solid #93c5fd;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 0.82rem;
  padding: 0.25rem 0.55rem;
  cursor: pointer;
}
.pass-btn:hover { background: #dbeafe; }
.deadline-flag {
  display: inline-block;
  margin-left: 0.35rem;
  padding: 0.08rem 0.45rem;
  border-radius: 999px;
  font-size: 0.75rem;
  color: #b91c1c;
  background: #fee2e2;
  border: 1px solid #fecaca;
}
.pass-overlay {
  position: fixed;
  inset: 0;
  z-index: 70;
  background: rgba(15, 23, 42, 0.3);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 1rem;
}
.password-overlay {
  position: fixed;
  inset: 0;
  z-index: 72;
  background: rgba(15, 23, 42, 0.32);
  backdrop-filter: blur(5px);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 1rem;
}
.password-modal {
  width: min(560px, 94vw);
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 1px solid #dbe7ff;
  border-radius: 18px;
  box-shadow: 0 22px 46px rgba(15, 23, 42, 0.25);
  padding: 1.15rem 1.2rem 1rem;
  position: relative;
}
.password-modal h3 {
  margin: 0;
  font-size: 1.12rem;
}
.password-subtitle {
  margin: 0.45rem 0 0;
  color: #64748b;
  font-size: 0.88rem;
}
.pass-modal {
  width: min(860px, 96vw);
  max-height: 88vh;
  overflow: auto;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 18px 46px rgba(15, 23, 42, 0.24);
  padding: 1rem 1.1rem;
  position: relative;
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
.pass-questions { display: grid; gap: 0.7rem; margin-top: 0.65rem; }
.question-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0.7rem;
  background: #f8fafc;
}
.question-card h4 { margin: 0 0 0.45rem; font-size: 1rem; }
.options { display: grid; gap: 0.35rem; }
.option-item { display: flex; align-items: center; gap: 0.45rem; font-size: 0.92rem; color: #334155; }
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
  margin-top: 0.8rem;
}
.tab-btn.primary {
  background: #2563eb;
  border-color: #1d4ed8;
  color: #fff;
}
.tab-btn.primary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.pass-message {
  color: #b91c1c;
  font-size: 0.9rem;
  margin: 0.45rem 0 0;
}
@media (max-width: 1080px) {
  .profile-grid { grid-template-columns: 1fr; }
  .chart.wide { grid-column: auto; }
}
</style>
