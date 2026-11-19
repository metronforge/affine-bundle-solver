# Campaign handoff

The base is 1df77461faf407320dab200d025fa846b2151502. The production patch is commit 137756852099fe33349bd52f8ce6893bb844c0de. Use `git rev-parse origin/ralph/abs-performance-30` for the published report tip. All later changes on this branch are experiment/review materials.

At the cycle-26 boundary the checkpoint was fd8166f5250cd880fe8d97a02f21f4e063e6238c. The open question was whether a second session could reproduce the missing guard and public timing effect. Source patch: `git diff 1df77461 fd8166f5 -- src`. The clean reviewer rebuilt both trees with `./build.sh` and ran `taskset -c 1 python3 reports/ralph-30/bench.py /tmp/ralph-review-base /tmp/ralph-review-final /tmp/independent.json w2 small --cache reports/ralph-30/inputs --blocks 6 --repeats 3`. [Inputs](inputs/) · [Raw replication](data/independent.json) · [Decision log](decisions.md).

At final handoff the open question is Viktor's review of the published branch. Reproduce from its checkout with `bash reports/ralph-30/reproduce.sh`. The two holdout inputs have now been used. [Final data](data/final.json) · [Holdout data](data/holdout.json) · [Report](README.md).

## Build provenance

GitHub email privacy required replacing local author/committer email metadata before publication. Every pair below has the identical Git tree. Raw manifests retain the measured local SHA.

| Measured/local commit | Published commit | Git tree |
|---|---|---|
| 2a1ed57e5a1676f76cb44e3ef826b99281c22c4a | 8456ecfc7ce6ca3d21c093dc87da4401cbc97934 | 3f582c5dbd1fc778ed4f9fb8cd1f5ca952f90122 |
| 2e868b0b40192665f639ad3f91c25f0901c36581 | 137756852099fe33349bd52f8ce6893bb844c0de | 8012cc982265709d9604e0b40a2f29b55e20e640 |
| bc6e5f95b23f7ffcd876d4f673fd8518032ca115 | 72cb852ba74dea585d80a07596482e9ddc60c9ee | 4776877f738dc1c208d24eee79f914d771f19707 |
| f7a0ae4251bb3a2b2122bc58073edb308bed0b7c | fd8166f5250cd880fe8d97a02f21f4e063e6238c | 2558c041a1f310b5c9b76199c908000bf9707fd9 |
| 2c087a186e52b24e9237760e875fb77cd1f01b2b | c195123fc19df609c3487bda5aaf89c1f56a1f48 | 8272059df28a3f2105acbe644826c8350e58ffe2 |
