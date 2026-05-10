import { ElMessage } from 'element-plus';
import type { App } from 'vue';

export function installGlobalErrorHandler(app: App): void {
  app.config.errorHandler = (error) => {
    console.error(error);
    ElMessage.error('系统异常，请稍后再试');
  };
}
