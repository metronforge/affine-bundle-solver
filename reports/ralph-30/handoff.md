# Campaign handoff

The base is 1df77461faf407320dab200d025fa846b2151502. The production patch is commit 2e868b0b40192665f639ad3f91c25f0901c36581. Use `git rev-parse origin/ralph/abs-performance-30` for the published report tip. All later changes on this branch are experiment/review materials.

At the cycle-26 boundary the checkpoint was f7a0ae4251bb3a2b2122bc58073edb308bed0b7c. The open question was whether a second session could reproduce the missing guard and public timing effect. Source patch: `git diff 1df77461 f7a0ae42 -- src`. The clean reviewer rebuilt both trees with `./build.sh` and ran `taskset -c 1 python3 reports/ralph-30/bench.py /tmp/ralph-review-base /tmp/ralph-review-final /tmp/independent.json w2 small --cache reports/ralph-30/inputs --blocks 6 --repeats 3`. [Inputs](inputs/) · [Raw replication](data/independent.json) · [Decision log](decisions.md).

At final handoff the open question is Viktor's review of the published branch. Reproduce from its checkout with `bash reports/ralph-30/reproduce.sh`. The two holdout inputs have now been used. [Final data](data/final.json) · [Holdout data](data/holdout.json) · [Report](README.md).
