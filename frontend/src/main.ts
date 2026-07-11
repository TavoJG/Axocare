import { createApp } from "vue";
import App from "./App.vue";
import "./styles.css";
import { initializeTheme } from "./useTheme";

initializeTheme();
createApp(App).mount("#app");
