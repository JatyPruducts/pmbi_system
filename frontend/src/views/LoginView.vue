<template>
  <div class="card" style="max-width: 400px; margin: 2rem auto">
    <h2>Вход</h2>
    <form @submit.prevent="onSubmit">
      <label>Email<br /><input v-model="email" type="email" required class="inp" /></label>
      <label>Пароль<br /><input v-model="password" type="password" required class="inp" /></label>
      <button type="submit" class="btn">Войти</button>
      <p v-if="err" class="err">{{ err }}</p>
    </form>
    <p class="hint">Демо: admin@pmbi.local / admin123</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const email = ref("admin@pmbi.local");
const password = ref("admin123");
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
.inp {
  width: 100%;
  margin: 0.35rem 0 0.75rem;
  padding: 0.4rem;
}
.btn {
  padding: 0.45rem 1rem;
  cursor: pointer;
}
.err {
  color: #b91c1c;
}
.hint {
  font-size: 0.85rem;
  color: #64748b;
}
</style>
