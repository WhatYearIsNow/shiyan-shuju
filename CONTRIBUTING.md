# 贡献指南

欢迎通过 Issue 描述问题，或提交范围清楚的 Pull Request。涉及计算时，请给出公式、输入单位、预期结果与可复现步骤；测试用自行构造的数据，不附真实学生资料。

## 本地检查

数值内核、测试和发布工具使用 Python 标准库，无需安装第三方 Python 包。支持 Python 3.10 及以上；持续集成在 Windows 和 Ubuntu 上覆盖 3.10、3.12、3.14。

工作流使用 GitHub 官方 [checkout](https://github.com/actions/checkout) 与 [setup-python](https://github.com/actions/setup-python)，只申请读取仓库内容的权限，不发布产物。

在仓库根目录执行：

```text
python -B -m unittest discover -s scripts -p test_uncertainty.py
python -B -m unittest discover -s tests -v
python -B scripts/check_release.py
python -B scripts/build_release.py --output build/shiyan-shuju.zip
```

PDF 生成另需 XeLaTeX 和模板所用宏包；发布检查通过只说明文本、链接和打包边界通过检查，不能代替数值口径核对或 PDF 目视验收。修改报告模板时请编译并检查页面，说明实际验证过的环境。

## 变更要求

- 保持命令行与 Python 接口的默认规则一致；改变行为时更新契约、示例和测试。
- 保留 Decimal 的中间精度。原始读数使用字符串，最终展示时才修约。
- 为数学修复添加能复现问题的测试；不要把教师口径、仪器型号参数当作通用物理定律。
- 文档使用 UTF-8 和相对链接。更新架构时同时检查流程与真实实现是否一致。
- 公开示例必须明确标为构造数据。真实姓名、学号、邮箱、课程照片、签字、第三方报告及逐字稿留在仓库外或本地 `.local/` 中。
- 不提交缓存、虚拟环境、编译中间文件或实验 PDF。忽略规则不会清除已经跟踪的文件，提交前仍需检查差异。

## 发布边界

[检查工具](scripts/check_release.py)只检查白名单中的公开文件。它检查基本 frontmatter、Markdown 相对链接、本机绝对路径、常见邮箱及疑似学号；这些是启发式检查，不能识别所有个人信息，也不能读取 PNG 的像素内容。

Python 代码中的长计算常量本身不视为学号；带 `student_id`、`学号` 或模板身份字段等上下文的长数字仍会被检查。本地可选 `.local/release-denylist.txt` 每行放一个已知私有值（例如真实姓名或学号），检查器会额外查找这些值，且不在诊断中回显。该文件不进入发布包，公开仓库不附任何真实值的内置名单。

[打包工具](scripts/build_release.py)使用同一份白名单，排除 `.local/`、Git 元数据、缓存、环境和构建产物，拒绝公开目录中的符号链接或 Windows 重解析点。归档路径按序排列，使用固定时间戳、权限和无压缩存储，便于复现。

新增公开目录、根文件或后缀时，明确更新白名单及发布测试，并审查文件来源。打包只创建本地 ZIP，不创建 GitHub Release 或上传任何内容。发布前查看归档文件列表，人工复查图片、来源和待确认口径。

贡献内容将按仓库 [MIT 许可证](LICENSE)分发；提交前请确认你有权贡献相应内容。来源说明见 [NOTICE](NOTICE.md)。
