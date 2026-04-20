<template>
  <div class="app">
    <header class="top">
      <h1>PMBI</h1>
      <nav v-if="auth.token">
        <RouterLink :to="homeRoute">Главная</RouterLink>
        <RouterLink v-if="auth.role === 'HR' || auth.role === 'ADMIN'" to="/hr">HR</RouterLink>
        <RouterLink v-if="auth.role === 'HR' || auth.role === 'ADMIN'" to="/surveys/constructor">Конструктор тестов</RouterLink>
        <RouterLink v-if="auth.role === 'TEAMLEAD' || auth.role === 'ADMIN'" to="/lead">Команда</RouterLink>
        <RouterLink v-if="auth.role === 'HR' || auth.role === 'TEAMLEAD' || auth.role === 'ADMIN'" to="/employees">Сотрудники</RouterLink>
        <RouterLink v-if="auth.role === 'EMPLOYEE' || auth.role === 'ADMIN'" to="/me">ЛК</RouterLink>
        <button type="button" @click="logout">Выход</button>
      </nav>
    </header>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const router = useRouter();
const homeRoute = computed(() => {
  if (auth.role === "TEAMLEAD") return "/lead";
  if (auth.role === "EMPLOYEE") return "/me";
  return "/";
});

function logout() {
  auth.clear();
  router.push("/login");
}
</script>

<style>
:root {
  font-family: Inter, "Segoe UI", system-ui, sans-serif;
  color: #0f172a;
  background: linear-gradient(180deg, #f8fbff 0%, #f1f5f9 100%);
}
body {
  margin: 0;
}
.app {
  min-height: 100vh;
}
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.25rem;
  color: #fff;
  position: sticky;
  top: 0;
  z-index: 20;
  backdrop-filter: blur(6px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);
  background: linear-gradient(120deg, #0f172a 0%, #1e293b 45%, #334155 100%);
}
.top h1 {
  margin: 0;
  font-size: 1.25rem;
}
.top nav {
  display: flex;
  gap: 0.6rem;
  align-items: center;
}
.top a {
  color: #dbeafe;
  text-decoration: none;
  padding: 0.32rem 0.6rem;
  border-radius: 8px;
  transition: all 0.18s ease;
}
.top a:hover {
  background: rgba(148, 163, 184, 0.24);
  color: #ffffff;
}
.top a.router-link-active {
  font-weight: 700;
  color: #0f172a;
  background: #e2e8f0;
}
.top button {
  cursor: pointer;
  color: #fff;
  padding: 0.35rem 0.6rem;
  border-radius: 6px;
  background: #475569;
  border: 1px solid #64748b;
  transition: all 0.18s ease;
}
.top button:hover {
  background: #64748b;
}
.main {
  padding: 1.2rem;
  max-width: 1460px;
  margin: 0 auto;
}
.card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.1rem 1.2rem;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.07);
  border: 1px solid #e2e8f0;
  margin-bottom: 1.05rem;
}
.grid2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1rem;
}
</style>
