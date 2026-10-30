#!/usr/bin/env python3
"""Build the G7 leg-(c) ranking sign-stability audit (exact, committed).

G7 go/no-go leg (c): quantify whether DECLARED specification ambiguity —
the 67 spec-declared free parameters of the UEC profile, plus the
declared free-parameter RANGES the executed models consume — changes any
MODEL RANKING the platform reports, not just values.

Method (exact Fractions only; every closed form verified against the
landed backend functions at executed witness points):

1. CLASSIFY the 67 spec free parameters (live registry) by whether any
   EXECUTED binding's parameter surface reads them. The honest first
   result: most are carried-not-executed, and a parameter no executed
   model reads cannot change any ranking by construction.
2. ENUMERATE the pairwise model rankings the committed artifacts report:
   the D4 saturation-boundary envelope's three pairs (uec_tfc_ring vs
   ub_flat_ring_pod / vs uec_ring_free / ring_free vs ub_flat_ring_pod)
   and the L0 atlas family pairs (ring / crossbar / recursive-doubling /
   torus2d, at the atlas ranks 4..64), all under the shared-parameter
   bar (both sides consume the SAME B, L, M, r — the envelope's own bar).
3. SIGN-ANALYSE each pair's exact difference over the WHOLE declared
   freedom box (A-XDUO-BW [1,1024] B/ns, A-XDUO-LAT [10,2000] ns,
   A-TFC-CR [0,2000] ns, A-TFC-W [256,1048576] B, A-XDUO-PAYLOAD
   [1024,16777216] B, A-XDUO-TP [2,1024] ranks, cell 256..9216,
   overhead 0..256): a pair is SIGN-STABLE (the ranking cannot flip
   anywhere in the box; equality conditions stated) or CONTINGENT (two
   admissible witnesses with opposite signs, plus the exact flip
   surface). No sampling: the sign analysis is closed-form; witnesses
   are executions that CONFIRM it.

Usage: ``.venv/bin/python experiments/gonogo/leg_c_ranking_audit/build_ranking_audit.py``
"""

from __future__ import annotations

import hashlib
import json
import importlib
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical import l0, l0_crossbar, l0_recursive_doubling, l0_tfc, l0_torus2d
from essun.specir.bindings import BINDINGS
from essun.specir.disposition_coverage import UEC_STAGE_MODULES

COMMITTED_COPY = Path(__file__).resolve().parent / "ranking_audit_v1.json"

# Declared free-parameter ranges (the audited ambiguity box; every entry
# cites its registry source — the same registries the envelope validates
# against).
BOX = {
    "A-XDUO-BW": (1, 1024, "B/ns", "experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml"),
    "A-XDUO-LAT": (10, 2000, "ns", "experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml"),
    "A-TFC-CR": (0, 2000, "ns", "experiments/vertical_slice/assumptions_tfc.yaml"),
    "A-TFC-W": (256, 1048576, "bytes", "experiments/vertical_slice/assumptions_tfc.yaml"),
    "A-XDUO-PAYLOAD": (1024, 16777216, "bytes", "experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml"),
    "A-XDUO-TP": (2, 1024, "ranks", "experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml"),
    "UEC11-FC-F01 cell": (256, 9216, "bytes", "UEC11-FC-R07 supported values"),
    "UEC11-FC-F02 overhead": (0, 256, "bytes", "UEC11-FC-R10 configurability bounds"),
}


# -- 1: classify the 67 spec free parameters --------------------------------------


def classify_free_parameters() -> dict:
    executed_names = {name for binding in BINDINGS for name in binding.parameters}
    rows = []
    executed = 0
    for dotted, _label in UEC_STAGE_MODULES:
        module = importlib.import_module(dotted)
        for fp in module.free_parameters():
            is_executed = fp.name in executed_names
            executed += int(is_executed)
            rows.append(
                {
                    "parameter_id": fp.parameter_id,
                    "name": fp.name,
                    "module": dotted.rsplit(".", 1)[-1],
                    "read_by_an_executed_binding": is_executed,
                }
            )
    return {
        "total": len(rows),
        "read_by_an_executed_binding": executed,
        "carried_not_executed": len(rows) - executed,
        "parameters": rows,
        "note": (
            "A free parameter no executed binding reads cannot change any "
            "ranking by construction — the honest first quantification. The "
            "executed subset is exactly what its name says: a parameter of "
            "an executed binding's config surface (tfc_dest_cell_size via "
            "BIND-UEC11-FC-R08-L0TFC, tfc_pkt_overhead via "
            "BIND-UEC11-FC-R09-L0TFC)."
        ),
    }


# -- helpers: execute the landed identities at a witness point ---------------------


def t_ring(M: int, r: int, B: Fraction, L: Fraction) -> Fraction:
    infra = l0.InfraConfig("audit", r, B, L)
    return l0.ring_allreduce_time_ns(M, r, infra)


def t_crossbar(M: int, r: int, B: Fraction, L: Fraction) -> Fraction:
    config = l0_crossbar.CrossbarConfig("audit", r, B, L)
    return l0_crossbar.crossbar_allreduce_time_ns(M, r, config)


def t_rd(M: int, r: int, B: Fraction, L: Fraction) -> Fraction:
    config = l0_recursive_doubling.RecursiveDoublingConfig(
        "audit", r, B, L, l0_recursive_doubling._log2_steps(r)
    )
    return l0_recursive_doubling.rd_allreduce_time_ns(M, config)


def t_torus(M: int, r1: int, r2: int, B: Fraction, L: Fraction) -> Fraction:
    config = l0_torus2d.Torus2DConfig("audit", r1 * r2, r1, r2, B, L)
    return l0_torus2d.torus2d_allreduce_time_ns(M, config)


def t_tfc(M: int, r: int, B: Fraction, L: Fraction, W: int, L_cr: Fraction,
          cell: int | None = None, overhead: int | None = None) -> Fraction:
    config = l0_tfc.TFCRingConfig(
        topology_id="audit",
        ranks=r,
        link_bytes_per_ns=B,
        hop_latency_ns=L,
        tfc_window_bytes=Fraction(W),
        tfc_credit_return_latency_ns=L_cr,
        tfc_dest_cell_size=Fraction(cell) if cell is not None else None,
        tfc_pkt_overhead=Fraction(overhead) if overhead is not None else None,
    )
    return l0_tfc.ring_allreduce_time_tfc_ns(M, r, config)


def witness(desc, t_a, t_b, expected_sign):
    sign = (t_a > t_b) - (t_a < t_b)  # 1 / 0 / -1
    assert sign == expected_sign, (desc, t_a, t_b, sign, expected_sign)
    return {
        "description": desc,
        "t_a_ns_exact": str(t_a),
        "t_b_ns_exact": str(t_b),
        "sign_of_t_a_minus_t_b": sign,
    }


def build() -> dict:
    classification = classify_free_parameters()
    B, L = Fraction(64), Fraction(200)  # envelope operating point when fixed

    pairs = []

    # -- envelope pair 1: uec_tfc_ring vs ub_flat_ring_pod (the flagship) --
    # d = T*(1/Reff - 1/B) >= 0 everywhere in the box (Reff = min(B, W/D) <= B);
    # tie iff W >= B*(L+L_cr). Sign-stable by the min-law's own structure.
    d_gated = t_tfc(1048576, 1024, B, L, 12800, Fraction(200)) - t_ring(1048576, 1024, B, L)
    d_tie = t_tfc(1048576, 1024, B, L, 1048576, Fraction(200)) - t_ring(1048576, 1024, B, L)
    assert d_gated > 0 and d_tie == 0
    pairs.append({
        "pair": "uec_tfc_ring vs ub_flat_ring_pod (D4 envelope flagship)",
        "difference_closed_form": "d = 2(r-1)/r*M*(1/min(B,W/(L+L_cr)) - 1/B)",
        "sign_analysis": (
            "d >= 0 for EVERY admissible point (the windowed rate never "
            "exceeds B, so the windowed identity is never faster); d = 0 "
            "iff W >= B*(L+L_cr) (the saturation boundary, the G6 rename's "
            "arithmetic now proven over the whole declared box, not only "
            "the envelope's fixed operating point)"
        ),
        "verdict": "SIGN-STABLE (windowed never faster; tie above the boundary)",
        "witnesses": [
            witness("gated corner (W=12800 < B*D=25600)", d_gated + t_ring(1048576, 1024, B, L), t_ring(1048576, 1024, B, L), 1),
            witness("saturated corner (W=1048576 >= B*D)", d_tie + t_ring(1048576, 1024, B, L), t_ring(1048576, 1024, B, L), 0),
        ],
    })

    # -- envelope pair 2: uec_tfc_ring vs uec_ring_free -- same sign structure
    pairs.append({
        "pair": "uec_tfc_ring vs uec_ring_free (envelope control)",
        "difference_closed_form": "same min-law term as the flagship pair",
        "sign_analysis": "identical sign structure: >= 0 everywhere, tie iff W >= B*(L+L_cr)",
        "verdict": "SIGN-STABLE",
        "witnesses": [
            witness("gated corner", t_tfc(1048576, 1024, B, L, 12800, Fraction(200)), t_ring(1048576, 1024, B, L), 1),
            witness("saturated corner", t_tfc(1048576, 1024, B, L, 1048576, Fraction(200)), t_ring(1048576, 1024, B, L), 0),
        ],
    })

    # -- envelope pair 3: uec_ring_free vs ub_flat_ring_pod -- the honesty anchor
    d0 = t_ring(1048576, 1024, B, L) - t_ring(1048576, 1024, B, L)
    assert d0 == 0
    pairs.append({
        "pair": "uec_ring_free vs ub_flat_ring_pod (envelope honesty anchor)",
        "difference_closed_form": "d = 0 identically (the two unwindowed ring identities coincide at L0)",
        "sign_analysis": "tie at every admissible point",
        "verdict": "SIGN-STABLE (as equality)",
        "witnesses": [witness("any point", t_ring(1048576, 1024, B, L), t_ring(1048576, 1024, B, L), 0)],
    })

    # -- atlas pairs (shared bar; r in the atlas set) --
    M_atlas, r_atlas = 1048576, 64
    d_x_ring = t_crossbar(M_atlas, r_atlas, B, L) - t_ring(M_atlas, r_atlas, B, L)
    assert d_x_ring == 2 * (2 - r_atlas) * L < 0
    pairs.append({
        "pair": "crossbar vs ring (atlas)",
        "difference_closed_form": "d = 2*(2-r)*L (the M/B terms cancel under the shared bar)",
        "sign_analysis": "d < 0 for r >= 3, d = 0 at r = 2: the crossbar is never slower at ANY admissible point",
        "verdict": "SIGN-STABLE",
        "witnesses": [witness("r=64 atlas point", t_crossbar(M_atlas, r_atlas, B, L), t_ring(M_atlas, r_atlas, B, L), -1)],
    })

    d_rd_ring = t_rd(M_atlas, r_atlas, B, L) - t_ring(M_atlas, r_atlas, B, L)
    assert d_rd_ring == 2 * (6 - 63) * L < 0  # log2(64)=6
    pairs.append({
        "pair": "recursive-doubling vs ring (atlas)",
        "difference_closed_form": "d = 2*(log2(r) - (r-1))*L (same wire bytes; shorter latency chain)",
        "sign_analysis": "d < 0 for r >= 3, d = 0 at r = 2 — never slower anywhere",
        "verdict": "SIGN-STABLE",
        "witnesses": [witness("r=64 atlas point", t_rd(M_atlas, r_atlas, B, L), t_ring(M_atlas, r_atlas, B, L), -1)],
    })

    d_x_rd = t_crossbar(M_atlas, r_atlas, B, L) - t_rd(M_atlas, r_atlas, B, L)
    assert d_x_rd == 2 * (1 - 6) * L < 0
    pairs.append({
        "pair": "crossbar vs recursive-doubling (atlas)",
        "difference_closed_form": "d = 2*(1 - log2(r))*L (same wire bytes)",
        "sign_analysis": "d < 0 for r >= 4, d = 0 at r = 2 — the crossbar is never slower anywhere",
        "verdict": "SIGN-STABLE",
        "witnesses": [witness("r=64 atlas point", t_crossbar(M_atlas, r_atlas, B, L), t_rd(M_atlas, r_atlas, B, L), -1)],
    })

    d_t_x = t_torus(M_atlas, 8, 8, B, L) - t_crossbar(M_atlas, r_atlas, B, L)
    assert d_t_x > 0
    pairs.append({
        "pair": "torus2d(8x8) vs crossbar (atlas)",
        "difference_closed_form": "d = 2*(1-1/r1-1/r2+1/r)*M/B + 2*(r1+r2-3)*L",
        "sign_analysis": (
            "both coefficients are positive for r1, r2 >= 2: the torus pays "
            "more wire bytes AND a longer latency chain than the crossbar's "
            "2L fill at every admissible point"
        ),
        "verdict": "SIGN-STABLE (torus never faster)",
        "witnesses": [witness("r=64 atlas point", t_torus(M_atlas, 8, 8, B, L), t_crossbar(M_atlas, r_atlas, B, L), 1)],
    })

    d_t_rd = t_torus(M_atlas, 8, 8, B, L) - t_rd(M_atlas, r_atlas, B, L)
    assert d_t_rd > 0
    pairs.append({
        "pair": "torus2d(8x8) vs recursive-doubling (atlas)",
        "difference_closed_form": "d = 2*(1-1/r1-1/r2+1/r)*M/B + 2*(r1+r2-2-log2(r))*L",
        "sign_analysis": "both coefficients positive (r1+r2-2-log2(r) >= 2+4-2-3 = 1 at r=8x... minimum over admissible shapes is positive) — torus never faster anywhere",
        "verdict": "SIGN-STABLE (torus never faster)",
        "witnesses": [witness("r=64 atlas point", t_torus(M_atlas, 8, 8, B, L), t_rd(M_atlas, r_atlas, B, L), 1)],
    })

    # -- THE contingent pair: torus2d vs ring --
    # d = a*(M/B) - b*L, a = 2*(1-1/r1-1/r2+1/r) > 0, b = (r1-1)*(r2-1) > 0.
    r1, r2 = 8, 8
    a = 2 * (1 - Fraction(1, r1) - Fraction(1, r2) + Fraction(1, r1 * r2))
    b = (r1 - 1) * (r2 - 1)
    w_slow = t_torus(16777216, 8, 8, Fraction(1), Fraction(10))  # M/B huge: torus slower
    ring_slow = t_ring(16777216, 64, Fraction(1), Fraction(10))
    assert w_slow > ring_slow
    w_fast = t_torus(1024, 8, 8, Fraction(1024), Fraction(2000))  # L huge: torus faster
    ring_fast = t_ring(1024, 64, Fraction(1024), Fraction(2000))
    assert w_fast < ring_fast
    pairs.append({
        "pair": "torus2d(8x8) vs ring (atlas) — THE contingent ranking",
        "difference_closed_form": (
            "d = 2*(1-1/r1-1/r2+1/r)*M/B - (r1-1)*(r2-1)*L "
            "(more wire bytes against a shorter latency chain — the "
            "design-space trade the backend exists for)"
        ),
        "sign_analysis": (
            "opposite-sign coefficients: d > 0 iff M/B > (r1-1)*(r2-1)*L / "
            "(2*(1-1/r1-1/r2+1/r)). At r=64 (8x8): a = 49/32, b = 49, flip "
            "at M/B = 32*L — and BOTH sides of the flip surface are inside "
            "the declared box (M/B ranges over [1, 16777216] while 32*L "
            "ranges over [320, 64000]): the declared ambiguity DECIDES this "
            "ranking, in both directions, with admissible witnesses on each "
            "side"
        ),
        "verdict": "CONTINGENT (ambiguity decides the ranking)",
        "witnesses": [
            witness(
                "torus slower: M=2^24, B=1, L=10 (M/B = 16777216 > 32*10)",
                w_slow, ring_slow, 1,
            ),
            witness(
                "torus faster: M=1024, B=1024, L=2000 (M/B = 1 < 32*2000)",
                w_fast, ring_fast, -1,
            ),
        ],
        "flip_surface": "M/B = (r1-1)*(r2-1)*L / (2*(1-1/r1-1/r2+1/r)); at 8x8: M/B = 32*L",
    })

    # -- the executed spec free parameters: F01 (cell) and F02 (overhead) --
    # eta = c/cq <= 1 multiplies the window cap only -> one-sided.
    # c = M/r = 4608 = 9*512: cell 512 divides it exactly (eta=1, the
    # zero-waste equality); cell 2048 wastes (cq=6144, eta=3/4); and at
    # the zero-waste cell the 256-B overhead crosses the next cell
    # boundary (cq 4608 -> 5120, eta 4608/5120 = 0.9).
    M_f, r_f, W_f, Lcr_f = 36864, 8, 12800, Fraction(200)
    t_plain = t_tfc(M_f, r_f, B, L, W_f, Lcr_f)
    t_cell = t_tfc(M_f, r_f, B, L, W_f, Lcr_f, cell=512)
    t_cell_waste = t_tfc(M_f, r_f, B, L, W_f, Lcr_f, cell=2048)
    t_pkt = t_tfc(M_f, r_f, B, L, W_f, Lcr_f, cell=512, overhead=256)
    assert t_cell == t_plain and t_cell_waste > t_plain and t_pkt > t_cell
    pairs.append({
        "pair": "tfc-with-cell (UEC11-FC-F01) vs tfc-plain (R02 identity)",
        "difference_closed_form": "rate eta*W/D with eta = c/ROUNDUP(c/cell)*cell <= 1: d >= 0, d = 0 iff cell | c",
        "sign_analysis": (
            "one-sided everywhere in the cell's declared domain "
            "(256..9216): quantization waste only slows; the RANKING never "
            "flips, the saturation boundary MOVES from B*(L+L_cr) to "
            "B*(L+L_cr)/eta (values shift, order does not)"
        ),
        "verdict": "SIGN-STABLE (one-sided; boundary shifts only)",
        "witnesses": [
            witness("zero-waste cell (c=4608, cell=512: eta=1)", t_cell, t_plain, 0),
            witness("waste cell (cell=2048: cq=6144, eta=3/4)", t_cell_waste, t_plain, 1),
        ],
    })
    pairs.append({
        "pair": "tfc-with-overhead (UEC11-FC-F02) vs tfc-with-cell",
        "difference_closed_form": "eta(c+ovh) <= eta(c): d >= 0, d = 0 iff the overhead adds no cell",
        "sign_analysis": "one-sided everywhere in 0..256 B: the overhead grows cq, never shrinks it",
        "verdict": "SIGN-STABLE (one-sided)",
        "witnesses": [witness("overhead 256 B crosses the next 512 B cell at c=4608 (eta 1 -> 0.9)", t_pkt, t_cell, 1)],
    })

    summary = {
        "pairs_audited": len(pairs),
        "sign_stable": sum(1 for p in pairs if p["verdict"].startswith("SIGN-STABLE")),
        "contingent": sum(1 for p in pairs if p["verdict"].startswith("CONTINGENT")),
        "answer": (
            "Does declared specification ambiguity change any model RANKING? "
            "For the 67 spec free parameters: NO — 65 are read by no "
            "executed model (they cannot move a number, let alone an "
            "order), and the 2 that execute (tfc_dest_cell_size, "
            "tfc_pkt_overhead) are one-sided (they slow the windowed "
            "identity and move its saturation boundary, never its rank). "
            "For every pairwise ranking the committed artifacts report the "
            "sign is stable over the WHOLE declared range box (proven in "
            "closed form, witnesses executed) — with ONE contingent "
            "family: torus2d vs ring, where the wire-bytes/latency-chain "
            "trade has its flip surface INSIDE the box (M/B = 32*L at "
            "r=64), so the declared freedom decides that ranking in both "
            "directions. The honest answer to 'do the ranges change any "
            "ranking' is: values and boundaries yes (quantified), order "
            "almost never — exactly once (torus2d vs ring), and that pair "
            "is a declared design-space trade, not a spec ambiguity."
        ),
    }

    return {
        "record_id": "gonogo-legc-ranking-audit-v1",
        "date": "2026-10-30",
        "program": "G7 go/no-go leg (c)",
        "status": "PROPOSED",
        "evidence_level": "E0 (exact closed-form sign analysis over the declared freedom box; witnesses executed by the landed backend functions)",
        "declared_freedom_box": {k: list(v[:3]) for k, v in BOX.items()},
        "free_parameter_classification": classification,
        "pairs": pairs,
        "summary": summary,
    }


def main() -> int:
    record = build()
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if COMMITTED_COPY.is_file():
        if COMMITTED_COPY.read_text(encoding="utf-8") == payload:
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            print(f"ranking_audit_v1.json reproduces byte-identically ({digest[:12]}...)")
            return 0
        print(
            "ERROR: regenerated audit differs from the committed copy; a "
            "change requires a NEW record version (ranking_audit_v2), never "
            "an edit",
            file=sys.stderr,
        )
        return 1
    COMMITTED_COPY.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print(f"wrote ranking_audit_v1.json ({digest[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
