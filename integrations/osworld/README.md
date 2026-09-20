# OSWorld integration

This directory has one narrow responsibility: connect PersonaCUABench to the
pinned OSWorld V1 runtime. It contains only:

- `azure_foundry_agent.py`: the Azure/OpenAI-compatible CUA adapter installed
  into OSWorld's `mm_agents/` package;
- `install_osworld.sh`: the reproducible installer for OSWorld, Odysseys, local
  patches, Python, and dependencies.

Run orchestration, preflight, judging, reports, and tests belong to
`personacuabench/` and `tests/`, not this integration directory.

## Installed layout

The installer creates two separate, gitignored checkouts:

```text
.osworld/OSWorld/       OSWorld V1 runtime, venv, and VMware VM data
.upstream/odysseys/     Odysseys data and standard rubric scorer
```

OSWorld is pinned to `b87586c739ddb00b887ceabf30defa766ff92765`, the
publication-time V1/Verified code line selected from the Odysseys task schema
and release chronology. Odysseys is pinned to
`837814633ef948479abb3d142458f0acdb73fa65`. These are reproducibility pins, not
a claim that the paper authors used those exact private checkouts. All pins,
patches, and hashes are recorded under [`reproducibility/`](../../reproducibility/README.md).

The names communicate ownership: `.upstream/odysseys/` is an external scorer
checkout, while [`personacuabench/`](../../personacuabench/README.md) is this
project's installed package and sole benchmark-data source.

## Prerequisites and installation

- Apple Silicon macOS
- `git`
- `uv 0.12.13`
- VMware Fusion 26H1u1 with its EULA, privileged helper, and network components
  approved through the macOS UI

Install from the repository root:

```bash
./integrations/osworld/install_osworld.sh
```

The installer checks out both pinned commits, applies the recorded OSWorld and
Odysseys patches, installs `azure_foundry_agent.py`, creates OSWorld's Python
3.12.14 environment, and verifies the resolved `uv.lock`. If the Ubuntu ARM VM
archive already exists, it also verifies the recorded SHA-256. It refuses to
move a dirty checkout to another commit or accept a partial/conflicting patch.

Fusion must complete its first-run authorization in the GUI; the installer
cannot grant macOS permissions. A first real run may download and unpack the
VM image. Verify Fusion before running the benchmark:

```bash
/Applications/VMware\ Fusion.app/Contents/Library/vmrun -T fusion list
```

## Adapter contract

The Azure adapter changes model transport while preserving OSWorld's computer
prompt, trajectory format, screenshot input, and PyAutoGUI action parser. It
also preserves natural-language final responses in the trajectory before
returning `DONE`, and maintains compact task memory across the intentionally
limited visual history.

Configure credentials and launch runs through `python -m personacuabench.run`;
invoke ordinary scoring separately through `python -m personacuabench.judge`
and optional person-experience scoring through
`python -m personacuabench.experience_judge`. The root
[`README`](../../README.md) documents API variables, previews, real runs,
network preflight, raw/adjusted scores, and reports.
