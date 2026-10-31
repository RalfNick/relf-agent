---
title: 安装与环境
description: 从源码准备一个轻量的 Python 环境，先在本地跑通 Relf-Agent。
locale: zh
slug: installation
sources: [docs/installation.md, docs/getting-started.md, docs/project-naming.md]
---

## 环境要求

准备 **Python 3.11 或更新版本**。本地入门使用 SQLite 与离线 Provider，无需模型密钥、Redis、Temporal 或 Docker。建议在 Linux 或 macOS 上使用独立虚拟环境。

Relf-Agent 处于 Alpha 阶段，API 和部署组合仍在演进。各组合的实际验证范围以仓库的[实现清单](repo:docs/implementation-status.md)为准。

Relf-Agent 的固定源码基线为 **0.1.0a8**，仓库为 `RalfNick/relf-agent`。本指南统一使用发行名 `relf-agent`、Python 导入 `relf_agent` 和 CLI `relf`／`relf-*`。

## 从源码安装

```bash
git clone https://github.com/RalfNick/relf-agent.git
cd relf-agent
git checkout 300c62ce8dd417df6b471ce1c10a1b7a562d2c46
git rev-parse HEAD
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
relf --version
python -m pip check
```

文档基线为 SDK **0.1.0a8**，提交 `300c62ce8dd417df6b471ce1c10a1b7a562d2c46`，验证日期为 2026-10-31。checkout 命令固定此版本，`relf --version` 应显示 `0.1.0a8`。基础依赖含 `httpx` 和 `jsonschema`。更新源码后行为可能变化；为旧 Run 保留原 SDK 和配置。

> 本站验证的是上述固定的 **a8 基版本维护源码**，不是原 `0.1.0a8` 归档包，也不等同于私有冻结候选 `0.1.0a8+maintenance.0608576182db502f`。后续维护沿用基版本号，须同时核对 `git rev-parse HEAD`；只检查 `relf --version` 不能区分这些源码。私有候选的准确文件、SHA 和独立验收见仓库[当前交付入口](repo:docs/current-delivery.md)。本页提供可公开检出的源码安装路径，未声明新的 PyPI／GitHub 包、平台或独立采用资格。[历史 a2 归档](https://github.com/RalfNick/relf-agent/releases/tag/v0.1.0a2)保留原入口与证据；新旧环境分开，旧 Run、History 和函数身份不自动迁移。

如果已经获得本地 wheel，可以在虚拟环境中用 `python -m pip install /实际路径/包名.whl` 安装，并核对制品来源与版本。

## 先完成一个本地任务

安装完成后，进入[完整离线快速开始](/zh/docs/quickstart/)，在一页中完成创建项目、审批、恢复与结果检查。这个流程无需任何可选依赖或模型密钥。

## 按需要添加依赖

以下命令在源码仓库、已激活的虚拟环境中执行。安装客户端依赖不会创建外部服务。

| 用途 | 命令 |
| --- | --- |
| 开发与测试 | `python -m pip install -e '.[dev]'` |
| 读取 Skill 文档 | `python -m pip install -e '.[skills]'` |
| Tokenizer 协议计量 | `python -m pip install -e '.[tokenizer]'` |
| 文本 PDF 摄取 | `python -m pip install -e '.[pdf]'` |
| Redis 客户端 | `python -m pip install -e '.[redis]'` |
| PostgreSQL 客户端 | `python -m pip install -e '.[postgres]'` |
| Temporal 客户端与相关依赖 | `python -m pip install -e '.[temporal]'` |

完整 extra 声明以 [pyproject.toml](repo:pyproject.toml) 为准。模型凭据通过进程环境配置，不写入代码或版本库。

## 确认安装

```bash
relf --help
relf --version
```

找不到 `relf` 时，先确认虚拟环境已经激活，再运行 `python -m pip show relf-agent` 检查安装位置。接下来阅读[快速开始](/zh/docs/quickstart/)，完成一次本地审批与跨进程恢复。
