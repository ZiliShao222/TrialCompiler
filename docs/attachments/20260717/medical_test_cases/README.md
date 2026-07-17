# 医学测试案例交付归档

## 文件

- `TrialCompiler_NCT04683926_Test_Package_original.zip`：医学成员整理的公开研究测试案例原包。
- `TrialCompiler_原型验证案例_01_original.zip`：基于 Week 12 -> Week 16 合成变更的演示包。

## 归档判断

1. `NCT04683926 / OMNI-PAIN-103` 是新的、独立的公开研究案例，可用于建立
   TrialCompiler 的第一个 public-document benchmark。
2. Week 12 -> Week 16 包来源于仓库已有的合成案例，只是增加了飞书输入和一键运行
   封装，不能作为第二个独立外部验证案例统计。
3. NCT04683926 原包中的 Excel 中文字符串存在编码损坏。该工作簿作为交付原件保留，
   但不作为运行时或人工标注的规范来源。
4. 经官方 PDF 复核后的规范资产位于
   `benchmarks/trialdocbench/public_case_001_nct04683926/`。

