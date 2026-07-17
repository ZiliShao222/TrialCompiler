# Public benchmark case 003: NCT03117738

This completed Phase 1/2 Alzheimer disease study provides an official Protocol, SAP, ICF, registry
record, and aggregate results. Its documents span different versions, making it useful for testing
version-aware conflict clustering, source precedence, qualified decision gates, and impact analysis.

The package deliberately distinguishes historical inconsistencies from legitimate planned-versus-
actual differences. It contains no patient-level data.

Official study page: https://clinicaltrials.gov/study/NCT03117738

Run the asset checks with:

```powershell
$env:PYTHONPATH = "src"
D:\miniconda\envs\iGEM\python.exe -m pytest tests/test_public_benchmark_packages.py -q
```
