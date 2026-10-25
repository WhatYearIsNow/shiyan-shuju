# shiyan-shuju · 实验数据处理

一个可独立安装的 Agent Skill：把实验读数、计算依据和报告表格组织成可追溯、可复算的结果。支持中文工作流，数学内核使用 Python 标准库 `Decimal`，不依赖特定学校或云服务。

## 能做什么

- 直接测量的 A/B 类、合成与扩展不确定度；幂律与数值偏导的一阶独立传播。
- 线性最小二乘、逐差法、有效数字与末位对齐。
- 可显式选择的历史电桥/课程算法，及按需使用的横向双框 LaTeX 模板。
- 来源和口径审计、复算驱动、数值验收与 PDF 视觉验收流程。

它不自动提交实验报告，不把示例当成原始数据，也不保证内置历史预设适用于你的仪器或课程。未实现相关项传播、加权拟合或通用有效自由度算法。

## 安装

需要 Python **3.10 或更新版本**。计算和自动化测试仅用标准库；生成中文 PDF 另外需要 XeLaTeX 与模板列明的 TeX 包，视觉检查需要本机可用的 PDF 渲染工具。没有 TeX 环境仍可计算和输出记录。

下载仓库或发行 ZIP，将解压后的完整 `shiyan-shuju` 文件夹放入你使用的 agent 的技能目录。例如 Codex 使用 `~/.codex/skills/shiyan-shuju`；其他兼容 Agent Skills 的工具按其安装约定配置。不要只拷贝 `SKILL.md`，脚本和参考文档也需要保留。

安装后使用 `$shiyan-shuju`，或直接提出“处理这组物理实验数据”。技能不会自动上传你的文件。若 agent 要调用外部服务，应按你的授权执行。

升级前备份当前技能文件夹和私有配置，再用新发行包覆盖公开文件；保留已有 `.local/` 与课程工作区，不把私人档案拷入新源码。升级后运行 `selftest`。从旧的学校定制版本迁移时，先将课程特有规则和模板保存到私有配置，再采用通用入口。

## 快速试算

在仓库根目录运行（命令在 Windows、macOS 和 Linux 相同）：

```text
python -B scripts/uncertainty.py selftest
python -B examples/direct_measurement.py
python -B scripts/uncertainty.py round --value 123.456 --u 9.9 --sig 1
```

示例使用明确标注的**合成数据**。命令行参数、数学假设及保留的 API 见 [计算契约](references/calculation-contract.md)。原有 `scripts/uncertainty.py` 导入接口及 `direct/bridge/boxerr/prop/fit/diff/round/selftest` 子命令保留；现在实现分布在 `scripts/labmath/`。

## 课程与个人配置

课程规则放在你自己的工作区 `AGENTS.md`/课程卡，或本技能 `.local/profile.md`，不需要改公开入口。配置可以指定私有课程根目录、报告模板、信息栏文件、数据/记录目录、课堂笔记 hook 和实验预设。

[匿名配置示例](examples/profile.example.md) 只描述格式，不包含真实课程资料。原始数据、身份信息、课件、逐字稿、往届报告都留在你的私有工作区。发布工具排除 `.local/`；不要把完整课程目录复制进源码。

## 开发与验证

表格和曲线的输出规范见 [科研图表与数值表达](references/scientific-presentation.md)：三线表、量与单位、数据与拟合的区分、缺失值、误差棒、矢量输出和最终尺寸验收。用户指定的报告纸仍决定外部版式；样式统一不能替代原始读数与数值核验。

推荐分阶段执行 `python -B scripts/verify.py --template --package`：兼容回归→完整测试（含真实模板编译/渲染）→发布检查→打包，任一步失败立即停止。无TeX环境省略 `--template`；报告会保留实际跳过数。命令、退出码和日志保存在忽略的 `build/verification/`，不会进入发行包。当前阶段状态见 [落实记录](docs/progress.md)。

```text
python -B -m unittest discover -s scripts -p test_uncertainty.py -v
python -B -m unittest discover -s tests -v
python -B scripts/check_release.py
python -B scripts/build_release.py --output build/shiyan-shuju.zip
```

[方案与验收范围](docs/plan.md)、[架构](docs/architecture.md)、[测试报告](docs/testing.md) 和 [贡献指南](CONTRIBUTING.md) 说明当前覆盖与限制。GitHub Actions 配置覆盖 Windows/Ubuntu 与 Python 3.10/3.12/3.14；CI 实际运行结果以仓库上传后的记录为准，不能把配置存在当成跨平台测试已通过。

## 来源与许可证

本项目按 [MIT](LICENSE) 提供代码与自写文档，材料边界见 [NOTICE](NOTICE.md)。不分发教材、学生报告、扫描纸、校徽或私人实验档案。

数值处理的边界参考 [NIST 不确定度传播](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty)、[NIST 扩展不确定度](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-6-expanded-uncertainty)、[Python Decimal](https://docs.python.org/3/library/decimal.html)；技能结构参考 [Agent Skills 规范](https://agentskills.io/specification)。课程的特殊算法须由本次材料确认，不因这些链接自动获得适用性。

开发、测试、候选构建和回退约定见[维护流程](MAINTENANCE.md)。
