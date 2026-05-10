import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';

import { createApp } from 'vue';

import { apiClient, installApiInterceptors } from './api/client';
import App from './App.vue';
import { installGlobalErrorHandler } from './plugins/errorHandler';
import router from './router';
import { createAppPinia } from './stores';
import './styles.css';

const app = createApp(App);
const pinia = createAppPinia();

app.use(pinia);
app.use(router);
app.use(ElementPlus);
installApiInterceptors(apiClient, { router });
installGlobalErrorHandler(app);

app.mount('#app');
