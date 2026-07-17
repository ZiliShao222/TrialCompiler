# Public benchmark case 002: NCT03232983

This completed Phase 1 healthy-volunteer, four-period crossover PK study is the closest public
companion to case 001. The package uses only official ClinicalTrials.gov records and documents.

It tests identifier integrity, endpoint/estimand drift, dense sampling schedules, planned-versus-
actual status semantics, and controlled propagation of a synthetic PK-window change. Gold findings
identify review obligations; they are not instructions to automatically overwrite a source.

Official study page: https://clinicaltrials.gov/study/NCT03232983

Run the asset checks with:

```powershell
$env:PYTHONPATH = "src"
D:\miniconda\envs\iGEM\python.exe -m pytest tests/test_public_benchmark_packages.py -q
```
