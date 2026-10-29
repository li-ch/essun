"""uet-htsim CMS backend adapter (the independent third backend).

Stage S1: capabilities + experiment validation + translation to the pinned
``htsim_uec`` binary's connection-matrix input format. Stage S2 adds
execution in the pinned container (bind-mount route, per-op run
orchestration, stdout FCT parsing, RunRecord through the evidence store).
"""
