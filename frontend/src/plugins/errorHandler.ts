import { ElMessage } from 'element-plus';
import type { App } from 'vue';

import { t } from '@/i18n';

export function installGlobalErrorHandler(app: App): void {
  app.config.errorHandler = (error) => {
    console.error(error);
    ElMessage.error(t('auth.errors.system'));
  };
}
