# Office 文档在线预览手册

本文说明 `T-2-DOC-04` 的部署、使用与排查方式。当前 Phase 2 决策为：使用 LibreOffice headless 将 Office 文档转换为 PDF 预览副本，不引入 OnlyOffice 文档服务。

## 部署手册

### 依赖

后端 Docker 镜像已经内置以下系统包：

- `libreoffice-writer`
- `libreoffice-calc`
- `libreoffice-impress`
- `fonts-noto-cjk`

本地不通过 Docker 运行后端时，需要在运行后端的机器上安装 LibreOffice，并确保命令行可执行文件可被后端进程访问。

### 环境变量

`.env` 中可按需覆盖：

```env
OFFICE_PREVIEW_CONVERTER_BINARY=libreoffice
OFFICE_PREVIEW_CONVERSION_TIMEOUT_SECONDS=30
```

Windows 本地开发如果安装的是桌面版 LibreOffice，可把 `OFFICE_PREVIEW_CONVERTER_BINARY` 设置为完整路径，例如：

```env
OFFICE_PREVIEW_CONVERTER_BINARY=C:\Program Files\LibreOffice\program\soffice.exe
```

### Docker 启动

开发环境：

```powershell
docker compose up --build
```

生产环境：

```powershell
docker compose -f docker-compose.prod.yml up --build -d
```

启动后确认后端健康检查通过：

```powershell
docker compose ps backend
```

## 使用手册

### 支持格式

以下扩展名会显示 Office 预览入口：

- `.doc`
- `.docx`
- `.xls`
- `.xlsx`
- `.ppt`
- `.pptx`

PDF 文档仍然使用原有 `/api/v1/documents/{id}/preview` 路由和 pdf.js 预览；Office 文档使用独立的 `/api/v1/documents/{id}/preview-office` 路由。

### 操作流程

1. 在项目环节文档列表上传 Word、Excel 或 PowerPoint 文件。
2. 在文档列表中点击 `Office 预览`。
3. 系统会把原文件临时转换为 PDF，并在现有 PDF 预览弹窗中展示。
4. 弹窗内支持翻页、缩放和下载转换后的 PDF 预览副本。

### 权限

Office 预览权限与文档下载一致。只有能下载该文档的用户才能预览；每次 Office 预览都会写入审计日志，动作为 `document.preview_office`。

## 运维与排查

### 转换失败

如果接口返回 `5003 Office document conversion failed`：

1. 查看后端日志：

   ```powershell
   docker compose logs --tail 200 backend
   ```

2. 确认容器内 LibreOffice 可执行：

   ```powershell
   docker compose exec backend libreoffice --version
   ```

3. 若生产环境使用自定义二进制路径，检查 `.env` 的 `OFFICE_PREVIEW_CONVERTER_BINARY`。

### 字体显示异常

Docker 镜像已安装 `fonts-noto-cjk`。如果仍有中文字体缺失，先确认上传文件是否使用了专有字体；必要时在后端镜像中补充企业标准字体，并重新构建镜像。

### 性能注意事项

转换发生在用户请求内，适合 50MB 以内文档的即时预览。大文件或复杂表格可能耗时较长，可通过 `OFFICE_PREVIEW_CONVERSION_TIMEOUT_SECONDS` 控制单次转换上限。
