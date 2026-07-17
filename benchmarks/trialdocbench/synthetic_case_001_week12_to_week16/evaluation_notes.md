# Evaluation Notes

This is the first minimal TrialDocBench synthetic case. It is intentionally small but complete enough to test:

1. extraction of confirmed primary endpoint and timepoint facts;
2. conflict detection between the fact sheet and the Schedule of Activities;
3. candidate-fact gate violation for an unconfirmed Week 20 follow-up note;
4. impact propagation for the `Week 12 -> Week 16` change request;
5. separation between automatic textual updates and human-gated medical, statistical, regulatory and operational decisions.

The expected high-level behavior is:

- Before the change request, `schedule_of_activities.md` contains a known Week 16 conflict.
- After the authorized change request, Week 16 becomes the candidate new fact value, and all Week 12 occurrences become impacted locations that require update or review.
- The system should not declare medical validity by itself. It should produce evidence, affected units and candidate redlines for human review.
