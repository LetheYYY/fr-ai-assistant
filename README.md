# FR 智能助手 · AI for FineReport

> 基于 RAG + LLM + OCR + Agent 的 FineReport 报表开发智能辅助系统

[![Python](https://img.shields.io/badge/Python-3.11+-yellow)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-框架-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

---

## 项目概述

FR 智能助手是一个面向 FineReport 报表开发场景的 AI 辅助系统，通过多种 AI 技术实现报表需求的智能分析、自动生成和知识管理。

### 核心能力

- **RAG 知识增强**：基于向量检索的 SOP 知识库，自动解析 FR 模板文件（.cpt），支持智能问答与方案推荐
- **OCR 识别**：支持 Tesseract 与 Step-1V 双引擎，从图片中提取报表结构和表格数据
- **AI Agent 编排**：多版本 Agent 演进，支持需求理解、SQL 生成、报表构建的全自动化流程
- **SQL 智能引擎**：根据自然语言需求自动生成和优化 SQL 查询语句
- **CPT 构建器**：自动生成 FineReport 模板文件（.cpt），支持条件格式、参数配置等

---

## 项目结构

```
fr-ai-assistant/
|-- knowledge/                  # RAG 知识库模块
|   |-- batch_parse.py         # 批量解析 FR 模板
|   |-- build_rag.py           # 构建 RAG 索引
|   |-- cluster_cpt.py         # CPT 聚类分析
|   |-- cpt_parser.py          # CPT 文件解析器
|   |-- rag_engine.py          # RAG 检索引擎
|   |-- rag_pipeline.py        # RAG 流水线
|   |-- sop_generator.py       # SOP 方案生成器
|   |-- run_sop_v3.py          # SOP 运行 v3
|   |-- run_sop_v4.py          # SOP 运行 v4
|
|-- engine/                     # AI 引擎核心
|   |-- agent.py               # Agent v3
|   |-- agent_v6.py            # Agent v6
|   |-- agent_v7.py            # Agent v7
|   |-- pipeline.py            # 全流程编排
|   |-- server.py              # FastAPI 服务
|   |-- web_server.py          # Web 服务
|   |-- ws.py                  # WebSocket
|   |-- cpt_builder.py         # CPT 构建器
|   |-- cpt_builder_v2.py      # CPT 构建器 v2
|   |-- cpt_builder_v4.py      # CPT 构建器 v4
|   |-- cpt_builder_v5.py      # CPT 构建器 v5
|   |-- cpt_templates.py       # 模板管理
|   |-- fr_reader.py           # FR 文件读取器
|   |-- sql_engine.py          # SQL 生成引擎
|   |-- sql_skills.py          # SQL 技能
|   |-- ocr_skills.py          # OCR 识别
|   |-- checker.py             # 报表验证
|   |-- analyze_upload.py      # 上传分析
|   |-- web/
|       |-- index.html         # 前端界面
|       |-- _style.css         # 样式文件
|
|-- tools/java/                 # Java 附加工具
|   |-- DumpAgent.java         # 类转储分析
|   |-- AttachAgent.java       # 进程附加
|   |-- ResourceDecryptor.java # 资源解密
|   |-- Check.java             # 状态检查
|
|-- docs/                       # 文档
|   |-- SOP需求分析.md
|   |-- SOP聚类需求分析.md
|   |-- demo.html              # Demo 展示页面
|
|-- .gitignore
|-- README.md
```

---

## 系统架构

```
用户输入 (对话/图片/需求)
        |
   FastAPI Server (server.py)
        |
   Agent 编排层 (agent.py)
   |-- 需求理解 --> SQL生成 --> CPT构建 --> 部署
        |
   能力层
   |-- OCR引擎 (ocr_skills.py)
   |-- SQL引擎 (sql_engine.py)
   |-- RAG引擎 (knowledge/rag_engine.py)
   |-- FR读取器 (fr_reader.py)
        |
   知识层
   |-- CPT解析 --> 向量化 --> RAG检索 --> SOP生成
        |
   FineReport 服务器部署
```

---

## 快速开始

### 环境要求

- Python 3.11+
- FineReport 11.0（可选，部分功能需要 FR 环境）
- Tesseract OCR（可选，用于 OCR 识别）

### 安装

```bash
pip install fastapi uvicorn python-multipart openai pillow pytesseract
```

### 配置

```bash
# 设置 API 密钥（通过环境变量）
export DEEPSEEK_KEY="your-deepseek-key"
export STEP1V_KEY="your-step1v-key"
```

### 启动

```bash
cd engine
python server.py
```

访问 http://localhost:8000 查看 Web 界面。

---

## 注意事项

- 本项目需要 FineReport 环境才能完整运行
- API 密钥通过环境变量配置，不要直接修改代码
- Java 工具用于 FR 进程分析和调试，需要 Java 8+
- 详细文档请参见 `docs/` 目录

---

## 声明

本项目仅用于学习和研究目的。FineReport 是帆软软件有限公司的商标。
