<template>
  <div class="auth-page">
    <div class="auth-wrap">
      <div class="brand">
        <div class="brand-logo">PMBI</div>
        <p class="brand-text">предиктивная аналитика для команд и HR-специалистов</p>
      </div>
      <div class="auth-card">
        <h2>Вход в PMBI</h2>
        <p class="sub">Введите логин и пароль для доступа к системе.</p>
        <form @submit.prevent="onSubmit" class="auth-form">
          <input v-model="email" type="email" required class="inp" placeholder="Логин" />
          <input v-model="password" type="password" required class="inp" placeholder="Пароль" />
          <button type="submit" class="btn">Войти</button>
          <p v-if="err" class="err">{{ err }}</p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const email = ref("");
const password = ref("");
const err = ref("");
const auth = useAuthStore();
const router = useRouter();

async function onSubmit() {
  err.value = "";
  try {
    await auth.login(email.value, password.value);
    router.push("/");
  } catch (e: unknown) {
    err.value = "Ошибка входа";
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.4rem 1rem;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}
.auth-wrap {
  width: min(980px, 96vw);
  display: grid;
  grid-template-columns: minmax(220px, 300px) minmax(320px, 430px);
  gap: clamp(2rem, 6vw, 6rem);
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}
.brand {
  color: #e2e8f0;
  display: grid;
  gap: 0.65rem;
}
.brand-logo {
  font-size: clamp(2.05rem, 5vw, 3.1rem);
  line-height: 1;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #ffffff;
}
.brand-text {
  margin: 0;
  line-height: 1.35;
  font-size: 0.94rem;
  color: #cbd5e1;
  max-width: 25ch;
}
.auth-page::before,
.auth-page::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.auth-page::before {
  background:
    radial-gradient(130% 110% at 8% 18%, #0b1228 0%, #102148 48%, #143064 100%);
}
.auth-page::after {
  background:
    repeating-radial-gradient(
      circle at 92% 56%,
      rgba(96, 165, 250, 0.4) 0px,
      rgba(96, 165, 250, 0.4) 2px,
      transparent 2px,
      transparent 14px
    ),
    repeating-radial-gradient(
      circle at 90% 58%,
      rgba(30, 64, 175, 0.35) 0px,
      rgba(30, 64, 175, 0.35) 2px,
      transparent 2px,
      transparent 20px
    ),
    radial-gradient(60% 75% at 92% 56%, rgba(59, 130, 246, 0.18), transparent 70%),
    radial-gradient(45% 60% at 82% 45%, rgba(255, 255, 255, 0.08), transparent 72%);
  opacity: 0.88;
}
.auth-card {
  width: min(430px, 94vw);
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(219, 234, 254, 0.95);
  border-radius: 24px;
  padding: 1.4rem 1.35rem;
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(5px);
  position: relative;
}
.auth-card h2 {
  margin: 0;
}
.sub {
  margin: 0.45rem 0 1rem;
  color: #475569;
  font-size: 0.92rem;
}
.auth-form {
  display: grid;
  gap: 0.75rem;
}
.inp {
  width: 100%;
  box-sizing: border-box;
  padding: 0.72rem 0.92rem;
  border-radius: 999px;
  border: 1px solid #bfdbfe;
  font-size: 0.96rem;
  color: #0f172a;
  background: #f8fbff;
}
.inp::placeholder {
  color: #94a3b8;
}
.inp:focus {
  outline: none;
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.22);
}
.btn {
  margin-top: 0.1rem;
  padding: 0.62rem 1rem;
  border-radius: 999px;
  border: 1px solid #1d4ed8;
  background: linear-gradient(120deg, #1d4ed8 0%, #2563eb 70%);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.err {
  color: #b91c1c;
  margin: 0;
  font-size: 0.9rem;
}
@media (max-width: 880px) {
  .auth-wrap {
    grid-template-columns: 1fr;
    gap: 1.2rem;
  }
  .brand {
    text-align: center;
    justify-items: center;
  }
}
</style>
