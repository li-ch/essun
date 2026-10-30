# G7 leg (c) — does declared specification ambiguity change any model RANKING?

Date: 2026-10-30. Status: **PROPOSED**, evidence level **E0**: exact
closed-form sign analysis over the declared freedom box; every closed
form verified against the landed backend functions at executed witness
points (the builder asserts the equalities; the guard test
`tests/calibration/test_gonogo_ranking.py` rebuilds the record
byte-identically). Record: `ranking_audit_v1.json` (built by
`build_ranking_audit.py`).

The question (the go/no-go's own wording): quantify whether the declared
specification ambiguity — the **67 free parameters** the UEC profile
carries, and the declared free-parameter **ranges** the executed models
consume — changes any model **RANKING**, not just values. The honest
answer may be no; it is, almost.

## The 67 spec free parameters: 65 cannot, 2 do not

Classified live against the executed bindings' parameter surfaces:
**65 of 67 are read by no executed model** (LLR replay-buffer sizing,
DSCP codepoints, timer values, ...) — a parameter nothing executes
cannot move a number, let alone an order. The **2 that execute** are
`tfc_dest_cell_size` (UEC11-FC-F01, via BIND-UEC11-FC-R08-L0TFC) and
`tfc_pkt_overhead` (UEC11-FC-F02, via BIND-UEC11-FC-R09-L0TFC), and both
are **one-sided**: their credit efficiencies `c/ROUNDUP(c/cell)*cell`
and the overhead-composed form are ≤ 1, so they can only slow the
windowed identity and move its saturation boundary from `B*(L+L_cr)` to
`B*(L+L_cr)/eta` — values and boundaries shift (executed witnesses:
`eta=1` equality at a zero-waste cell; `eta=3/4` at a wasting cell; the
256-B overhead crossing the next cell at `eta 1 -> 0.9`), the RANKING
never flips, in either direction, anywhere in the declared domains.

## The pairwise rankings the platform reports: 10 stable, 1 contingent

Under the shared-parameter bar (both sides consume the same B, L, M, r —
the envelope's own bar), every reported pairwise difference collapses to
a sign-definite closed form over the WHOLE declared box
(B ∈ [1,1024] B/ns, L ∈ [10,2000] ns, L_cr ∈ [0,2000] ns,
W ∈ [256,1048576] B, M ∈ [1024,16777216] B, r ∈ [2,1024]):

| Pair | d = t_A − t_B | Verdict |
|---|---|---|
| uec_tfc_ring vs ub_flat_ring_pod (flagship envelope) | `2(r−1)/r·M·(1/min(B,W/D) − 1/B) ≥ 0`, tie iff W ≥ B·D | **STABLE** — over the whole box, not just the envelope's fixed operating point |
| uec_tfc_ring vs uec_ring_free (control) | same min-law term | **STABLE** |
| uec_ring_free vs ub_flat_ring_pod (honesty anchor) | `0` identically | **STABLE** (tie) |
| crossbar vs ring | `2(2−r)L` | **STABLE** (crossbar never slower; tie r=2) |
| recursive-doubling vs ring | `2(log2 r − (r−1))L` | **STABLE** |
| crossbar vs recursive-doubling | `2(1−log2 r)L` | **STABLE** |
| torus2d vs crossbar | `a·M/B + 2(r1+r2−3)L`, both coefficients > 0 | **STABLE** (torus never faster) |
| torus2d vs recursive-doubling | `a·M/B + 2(r1+r2−2−log2 r)L`, both > 0 | **STABLE** |
| torus2d vs ring | `a·M/B − (r1−1)(r2−1)L`, **opposite signs** | **CONTINGENT** |
| tfc+cell vs tfc-plain (F01) | `≥ 0`, `= 0` iff cell \| c | **STABLE** (one-sided) |
| tfc+overhead vs tfc+cell (F02) | `≥ 0` | **STABLE** (one-sided) |

The one contingent family — **torus2d vs ring** — is the design-space
trade the torus backend exists for: it pays more wire bytes
(`a = 2(1−1/r1−1/r2+1/r) > 0`) against a shorter latency chain
(`(r1−1)(r2−1)·L`). The flip surface `M/B = (r1−1)(r2−1)L / a` sits
INSIDE the declared box (at r=64, 8×8: `M/B = 32·L`, and `M/B` ranges
over [1, 16777216] while `32·L` ranges over [320, 64000]): executed
witnesses on both sides — torus slower at M=2^24, B=1, L=10; torus
faster at M=1024, B=1024, L=2000 — so the declared freedom DECIDES this
ranking, in both directions. Note what this is and is not: it is a
declared modeling trade between two of OUR identities under shared
parameters, not a specification ambiguity, and not a claim about any
fabric.

## The answer, stated plainly

**Values and boundaries: yes, extensively** (the window's saturation
boundary moves with every gated parameter; the cell/overhead
efficiencies scale it; quantified exactly in the record). **Rankings:
no** — for the 67 spec free parameters (65 unread, 2 one-sided), and for
10 of the 11 reported pairwise rankings the sign is stable over the
ENTIRE declared box, proven in closed form with executed witnesses. The
single exception (torus2d vs ring) flips on a declared design trade
inside the box, exactly where the backend's own documentation says the
trade lives. Nobody needs to sweep the box to know the flagship
saturation boundary's sign structure — and now that is a proven
statement, not an assumption.
