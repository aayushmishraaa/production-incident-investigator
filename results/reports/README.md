# Sample investigation reports

All of these come from real runs on Claude Haiku 5.5.

| File | Scenario | What it shows |
|---|---|---|
| `samples/INC-001_multi_agent_run1` | DB pool exhaustion | successful diagnosis |
| `samples/INC-005_multi_agent_run1` | misleading deployment | the deploy is rejected because the storage degradation began earlier |
| `samples/INC-005_single_agent_run1` | same incident, baseline | single-agent output for comparison |
| `samples/INC-008_multi_agent_run1` / `INC-008_single_agent_run1` | cache degradation | multi-agent is correct; the baseline blamed the feature-flag config change |
| `samples/INC-009_multi_agent_run1` | tool timeouts and partial data | retries, preserved findings, uncertainty reported |
| `samples/INC-010_multi_agent_run1` | insufficient evidence | INCONCLUSIVE outcome |
| `samples/INC-012_multi_agent_run1` | config change disguised as pool exhaustion | does not stop at the symptom or the historical analogy |
| `samples/INC-007_multi_agent_inv-*` | config regression, run via the API | INCONCLUSIVE: the critic did not approve the correct leading hypothesis within 3 rounds |
| `pre_calibration/` | INC-005 before the scoring and critic calibration fix | kept for transparency; see docs/evaluation.md §6 |

Every evaluation run's report is in `../evaluation/runs/`.
