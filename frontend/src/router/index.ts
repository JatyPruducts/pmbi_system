import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("../views/LoginView.vue") },
    { path: "/", component: () => import("../views/HomeView.vue"), meta: { requiresAuth: true } },
    { path: "/hr", component: () => import("../views/HRView.vue"), meta: { requiresAuth: true, roles: ["HR", "ADMIN"] } },
    { path: "/lead", component: () => import("../views/LeadView.vue"), meta: { requiresAuth: true, roles: ["TEAMLEAD", "ADMIN"] } },
    {
      path: "/employees",
      component: () => import("../views/EmployeesTableView.vue"),
      meta: { requiresAuth: true, roles: ["HR", "TEAMLEAD", "ADMIN"] },
    },
    {
      path: "/surveys/constructor",
      component: () => import("../views/SurveyConstructorView.vue"),
      meta: { requiresAuth: true, roles: ["HR", "ADMIN"] },
    },
    { path: "/me", component: () => import("../views/EmployeeView.vue"), meta: { requiresAuth: true, roles: ["EMPLOYEE", "ADMIN"] } },
  ],
});

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.token) {
    return next("/login");
  }
  if (to.path === "/" && auth.role === "TEAMLEAD") {
    return next("/lead");
  }
  if (to.path === "/" && auth.role === "EMPLOYEE") {
    return next("/me");
  }
  const roles = to.meta.roles as string[] | undefined;
  if (roles && auth.role && !roles.includes(auth.role)) {
    return next("/");
  }
  return next();
});

export default router;
