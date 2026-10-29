# Golden run reference — W1 smoke manifest

Manifest: `experiments/vertical_slice/w1_decode_smoke.yaml`
Golden run_id: `146ba565d2cac8e613435e548caba4f606e0abbb149beaf6404935d4f92199a1`

## Re-store log

- **2026-10-27: identity RESTORED, not re-stored.** The cold-tree
  drill found this golden stale at HEAD: a prior change
  added O-TRAFFIC-IMBALANCE to the L0 backend's emitted output, shifting the
  content-addressed run_id of every L0 run. The follow-up decision pinned run identity to the manifest's declared observable
  set: a run record now contains exactly the observables the manifest asks
  for. With the pin, `make run EXP=experiments/vertical_slice/w1_decode_smoke.yaml`
  at HEAD reproduces `916bfc86…` byte-for-byte again. The cold-tree claim in
  README holds at HEAD from this commit on; a rerun that changes this id
  without a manifest or code change is a bug.
- Original golden stored 2026-10-26 (vertical slice, 29 tests).
- **2026-10-28: identity RESTORED a second time, and the class is closed.** The A-L05-* entries grew the shared assumptions file and shifted the run id again (ebe2e22d…). Fix per the same decision: assumptions now live in per-model files (assumptions_l0.yaml frozen for the L0 family; assumptions_l05.yaml for L0.5). Unrelated additions can no longer shift each other's runs. `make run` reproduces `916bfc86…` again; 504 tests green.

- **2026-10-29: re-stored after the project rename (essun).** The package
  directory was renamed to essun; the L0 implementation-profile input
  (`experiments/vertical_slice/profiles/implementation_profile_l0.yaml`)
  names that source path, so its hash — and with it this run id — changed
  (916bfc86… -> 146ba565…). Same class for the ASTRA twin, additionally
  through the pinned Docker image name now `essun/astra-sim-analytical:s1`
  (same image id sha256:bb02b612…; fb283970… -> c6dc87eb… in
  tools/make_figure.py). No manifest, model, or observable changed:
  rerunning both manifests at this tree reproduces the new ids
  byte-for-byte (full `make demo` green, including the cold-clone
  check), so the "no id change without a manifest or code change"
  invariant holds — this was a code change.
