PRECEDENTGUARD Fig.6 -- 4+4+2 layout candidate

Row 1: (a) Four domains, B1 sandbox-probe unauthorized effects, PG observed zero.
Row 2: (b) Four matching domains, PG proposal dispositions. Each stacked bar
       is a percentage of proposals for its own model-domain cell. The count
       above each bar is the true model-domain proposal denominator.
Row 3: (c) Conditional installed rules and canonical PEP probe hits, left;
       (d) Issuer/scope/sandbox violations, right.

Data integrity: The 60 frozen CSV rows are read-only. 4 domain proposal
totals: 733 + 877 + 758 + 800 = 3168. Dispositions:
2275 + 584 + 101 + 208 = 3168.
95% Wilson intervals are descriptive, not proof of independent channels.
Root capabilities are simulated by the experimental harness; unauthorized
effects are measured using sandbox probes. Canonical hits are not actual
end-to-end task success. E3 frozen-prefix replay is not depicted.

IEEE sizing: 505.89 pt wide, exact conference/compsoc double-column textwidth.
Outputs are true vector PDFs/SVGs. The uniform version preserves 0-100%
axes for the first-row domains; the adaptive version labels domain-specific
axis limits for greater visibility of low event rates.

Rebuild from these files:
    python Fig6_442_reproducible.py --csv Fig6_442_frozen_data.csv --outdir output

No model inference or experimental rerun was performed.
