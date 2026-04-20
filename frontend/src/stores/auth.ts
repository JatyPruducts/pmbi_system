import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "../api/client";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem("pmbi_token"));
  const role = ref<string | null>(localStorage.getItem("pmbi_role"));
  const email = ref<string | null>(localStorage.getItem("pmbi_email"));

  const isAuthenticated = computed(() => !!token.value);

  async function login(emailVal: string, password: string) {
    const { data } = await api.post("/auth/login", { email: emailVal, password });
    token.value = data.access_token;
    localStorage.setItem("pmbi_token", data.access_token);
    const me = await api.get("/auth/me");
    role.value = me.data.role;
    email.value = me.data.email;
    localStorage.setItem("pmbi_role", me.data.role);
    localStorage.setItem("pmbi_email", me.data.email);
  }

  function clear() {
    token.value = null;
    role.value = null;
    email.value = null;
    localStorage.removeItem("pmbi_token");
    localStorage.removeItem("pmbi_role");
    localStorage.removeItem("pmbi_email");
  }

  return { token, role, email, isAuthenticated, login, clear };
});
