# Combined API regression baseline

## Scope and revisions

This report is limited to files actually inspected or executed. The frozen source revision is `metronforge/abs-apps@ae9b662d7f5755418aa80f31ade1fffcbefebafd`. The solver baseline began at `2741af01f0c0116347dbc81b21998f538690dcea`; the certificate determinism fix used for recorded outputs is `49ec7e34377818c2fc149466879f088ecd834c1b`.

The historical design contains 1000 planned slots. The available terminal evidence is split into 122 historical, 177 migrated/corrected, and 100 fresh records (399), which are records rather than 399 self-contained input bundles. The reproducible Task8 input set has 36 materialized NPZ files: T8-001..032 and T8-036..039; T8-033..035 are not materialized. The separate `engineering-27slot-20260926` archive contains V31-001..027 and 324 result observations but no self-contained input bundles, so it is result-only. `results/blockprefix_final_1000.json` is an aggregate result and is not treated as an input corpus.

Selection used dimension coverage only: 26 square, 8 tall, and 2 wide systems. The current combined API does not expose `x`; it is recorded as `not_exposed_by_current_api`, never fabricated.

## Provenance and attribution

T8-001..029 are deterministic constructions from `task8_cases.py`. T8-030..032 derive from the Radio Astronomy Software Group `rasg-datasets` revision `55bd68b28fabe0936011bd9540cbaef9e20809db`, source UVFITS SHA-256 `2544212e4bba85319c4628b1e019aa79b6e988a310cd258b258165a3999439e9`, under BSD-2-Clause. T8-036..039 are SuiteSparse HB/bcsstk01, 02, 04, 05 objects (matrix author J. Lewis; collection editors I. Duff, R. Grimes, J. Lewis) under CC-BY-4.0. Full notices and citations are in `tests/fixtures/api-regression/THIRD_PARTY_NOTICES.md`.

## Input → observed current API → exact oracle

Invocation: `combined_policy_v1`, `xt=NULL`, `sp=1`, `qv=2`, `alpha=2`, `seed=17`, `full=0`; default policy `(D=1e-13, G=1e-9, compatibility=2e-10, quality=1e-14)`. Floats use `rtol=1e-10`, `atol=1e-12` in the frozen single-thread behavior gate; elapsed time is excluded.

| slot | shape/type | source | A SHA-256 | b SHA-256 | observed API output | independent oracle |
|---|---:|---|---|---|---|---|
| T8-001 | 16×16 square | abs_apps | `9a45be709cd5db7673e00a2feec677cb87c0f9993e582e9f4b5a9e020b6bef90` | `6c15dc9f9b22ba5c13609522990274fbb536cb54fdea237119fca3914bfd60df` | rc=0; op=INFINITE/DETERMINISTIC; rank=14[14,14]; relres=5.76372e-16; berr=absent:NaN; mask=7; eta=(2.55744e-15,1.46339e-15,4.6444e-16); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=14/14; exact binary64 integer/modular proof |
| T8-002 | 24×24 square | abs_apps | `f075dae8502ed9e59c963c817c1779b5c3b865275e4ea9be728f3d0b2f245eb3` | `f7934ec38bd8fd687925622dc10904dca88723edab0cdd5dd437b7629cc73e7a` | rc=0; op=INFINITE/DETERMINISTIC; rank=21[21,21]; relres=7.6545e-16; berr=absent:NaN; mask=7; eta=(2.91209e-15,1.89985e-15,3.0578e-16); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=21/21; exact binary64 integer/modular proof |
| T8-003 | 32×32 square | abs_apps | `4b497638cf65d0c8518ea54f0a8a86e659599bbd45c77af39b6453bb3e2773b8` | `b2f1153bd40e2af3b91b53f3fe87a162403797d9d4767777abac97eb900882a0` | rc=0; op=INFINITE/DETERMINISTIC; rank=28[28,28]; relres=2.2581e-16; berr=absent:NaN; mask=7; eta=(3.93174e-15,2.86812e-15,4.02883e-16); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=28/28; exact binary64 integer/modular proof |
| T8-004 | 40×40 square | abs_apps | `19a789bc75e9ec5f3812c4b4594d92146bbc87a514cfbfeca39ff800714c6baa` | `53ec8d9606a7877db2192ba914b16acf321a056733fae8b4e8522ea3a478e33b` | rc=0; op=INFINITE/DETERMINISTIC; rank=35[35,35]; relres=2.12297e-16; berr=absent:NaN; mask=7; eta=(3.84188e-15,2.11781e-15,5.1934e-16); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=35/35; exact binary64 integer/modular proof |
| T8-005 | 48×48 square | abs_apps | `4f39857d277d3db98cd9eb951a66db2143cae92373be958172f233976ab7e220` | `df8b3ffffaa85f7a831f0f0094e98dea493022380e9883e298ad432341b44e5e` | rc=0; op=INFINITE/DETERMINISTIC; rank=42[42,42]; relres=2.40203e-16; berr=absent:NaN; mask=7; eta=(3.92984e-15,2.44876e-15,6.09807e-16); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=42/42; exact binary64 integer/modular proof |
| T8-006 | 56×56 square | abs_apps | `02cf620998c9cbaf8bfea556c39c93f5940d9067cfc76975e7cded11d9153b7e` | `eef2dffc4679301636f9aaed3d4a2a81f7f0d8ec66fc4a1fbbde08f08ce84cec` | rc=0; op=INFINITE/DETERMINISTIC; rank=49[49,49]; relres=2.29361e-16; berr=absent:NaN; mask=7; eta=(4.75277e-15,1.87196e-15,9.3262e-16); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=49/49; exact binary64 integer/modular proof |
| T8-007 | 64×64 square | abs_apps | `ceb7365cd315d31431d11d3f1e8d1ca1159ff74c17fc46ac517bbc8289f5828f` | `30a7251c67b5d562599838ba8718f764f2e71847aaff67b9a8c60dbb502f1af0` | rc=0; op=INFINITE/DETERMINISTIC; rank=56[56,56]; relres=2.35585e-16; berr=absent:NaN; mask=7; eta=(4.46733e-15,3.19968e-15,7.70997e-16); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=56/56; exact binary64 integer/modular proof |
| T8-008 | 21×24 wide | abs_apps | `8238a8b28d3ea188028768314e0775af10c1708f20a661709d57cc88661ae994` | `c2a7e427b175f626c47eac47aa989c431e9362895700ed2b798e52072c4f005a` | rc=0; op=INFINITE/RANDOMISED; rank=21[21,21]; relres=6.7843e-16; berr=absent:NaN; mask=6; eta=(no finite bound,1.39182e-15,0.229416); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=21/21; exact binary64 integer/modular proof |
| T8-009 | 56×64 wide | abs_apps | `fc8f88cfcb485ddb74c527a74d25090d6db31e0a6bd5b7b5d4ab762bda3fa47e` | `f2e4aeca109799adc3d328a38ce9449cf44a6c5e9e7dc4572a0c4b6fa2a887a7` | rc=0; op=INFINITE/RANDOMISED; rank=56[56,56]; relres=5.58077e-16; berr=absent:NaN; mask=6; eta=(no finite bound,3.08279e-15,0.229416); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=56/56; exact binary64 integer/modular proof |
| T8-010 | 75×40 tall | abs_apps | `a26378aa1424fdefa66281452ae371d8b5e7af1b9539dd4e4e1d4dcefb63ec1d` | `0e2ed4264d32afc43e48e60c4bfc69409296daa3a3fbfb8d567acd84b9535b32` | rc=0; op=INFINITE/RANDOMISED; rank=35[35,40]; relres=1.06534e-15; berr=absent:NaN; mask=6; eta=(no finite bound,2.47392e-15,1.57957e-15); exact-field=UNKNOWN/NOT_VERIFIED | INFINITE; rank(A/aug)=35/35; exact binary64 integer/modular proof |
| T8-011 | 32×32 square | abs_apps | `36a7c0b74e80fffd138c904745861400e80263feefa64b6fdc2461530e5b6512` | `f85a3cbc3c21118f33369d892ac5e37fa71a25f81ecde2ddcfe49561d22be1bf` | rc=0; op=INFINITE/RANDOMISED; rank=31[31,32]; relres=6.51636e-16; berr=absent:NaN; mask=6; eta=(no finite bound,2.717e-15,6.29069e-16); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=31/32; exact binary64 integer/modular proof |
| T8-012 | 32×32 square | abs_apps | `36a7c0b74e80fffd138c904745861400e80263feefa64b6fdc2461530e5b6512` | `c6b2b8b0eeca092dab3c5e605d76611ba0740a190c635e60e26ee21fd1b3f688` | rc=0; op=INFINITE/RANDOMISED; rank=31[31,32]; relres=4.21487e-14; berr=absent:NaN; mask=6; eta=(no finite bound,5.95081e-14,8.14152e-16); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=31/32; exact binary64 integer/modular proof |
| T8-013 | 32×32 square | abs_apps | `36a7c0b74e80fffd138c904745861400e80263feefa64b6fdc2461530e5b6512` | `926147a2e52d4b16e17b69e2d874513d89d2c028a26a66faf2401cc8eb4297a9` | rc=0; op=INFINITE/RANDOMISED; rank=31[31,32]; relres=4.21637e-12; berr=absent:NaN; mask=6; eta=(no finite bound,5.77507e-12,7.05077e-16); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=31/32; exact binary64 integer/modular proof |
| T8-014 | 32×32 square | abs_apps | `36a7c0b74e80fffd138c904745861400e80263feefa64b6fdc2461530e5b6512` | `3467ba4bfbfd74e769bea4eb3a5dfb076437abf2e8bc721acba1d6bd0b263831` | rc=0; op=INCONSISTENT/DETERMINISTIC; rank=31[31,31]; relres=2.38514e-07; berr=absent:NaN; mask=6; eta=(no finite bound,5.7735e-08,7.81604e-16); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=31/32; exact binary64 integer/modular proof |
| T8-015 | 30×16 tall | abs_apps | `a112d4db5f5f66a0e4b4000df33c3432f29bb222a112598622b65bc672b1d637` | `a5445dd24c28865ab32e1945dc5a0cae24d270c27358334b97f84e6ea1cecc06` | rc=0; op=INFINITE/RANDOMISED; rank=15[15,16]; relres=7.80833e-16; berr=absent:NaN; mask=6; eta=(no finite bound,1.34607e-15,1.00914e-15); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=15/16; exact binary64 integer/modular proof |
| T8-016 | 30×16 tall | abs_apps | `a112d4db5f5f66a0e4b4000df33c3432f29bb222a112598622b65bc672b1d637` | `b409f19071eb93252b588198fabef7967070f6484c98c40a72cb085f2d1d4604` | rc=0; op=INFINITE/RANDOMISED; rank=15[15,16]; relres=5.59897e-14; berr=absent:NaN; mask=6; eta=(no finite bound,5.86504e-14,9.41599e-16); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=15/16; exact binary64 integer/modular proof |
| T8-017 | 30×16 tall | abs_apps | `a112d4db5f5f66a0e4b4000df33c3432f29bb222a112598622b65bc672b1d637` | `57a93ff6d7b5182f9dde7ab77483edeb1bb7b55b188e74396c86cdab3bf327a7` | rc=0; op=INFINITE/RANDOMISED; rank=15[15,16]; relres=5.5839e-12; berr=absent:NaN; mask=6; eta=(no finite bound,5.77434e-12,1.24428e-15); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=15/16; exact binary64 integer/modular proof |
| T8-018 | 30×16 tall | abs_apps | `a112d4db5f5f66a0e4b4000df33c3432f29bb222a112598622b65bc672b1d637` | `d7fd6e8ed9a656621860e50aef50e49a78a19c2edc192d7a28ba6ea689b01164` | rc=0; op=INCONSISTENT/DETERMINISTIC; rank=15[15,15]; relres=5.94089e-08; berr=absent:NaN; mask=6; eta=(no finite bound,5.7735e-08,8.75585e-16); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=15/16; exact binary64 integer/modular proof |
| T8-019 | 16×16 square | abs_apps | `e688a37f6141d966e77b80a8d0f6e7dcd05954dbc7ca8318caccd3b7c742ef20` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=INFINITE/RANDOMISED; rank=15[15,16]; relres=3.92523e-17; berr=absent:NaN; mask=7; eta=(1.57009e-16,3.55074e-14,1.76778e-14); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-020 | 16×16 square | abs_apps | `4767fed67ab26a08d071a3af6e71e1cf4041e930e7f5ed42f324f3e04b6c10bf` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=INFINITE/RANDOMISED; rank=15[15,16]; relres=3.92523e-17; berr=absent:NaN; mask=7; eta=(1.57009e-16,1.06218e-13,5.30331e-14); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-021 | 16×16 square | abs_apps | `6395ce29e65c47cbe19b624c95fad9d4767c66656d1caec10228d65fcef1a9ab` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=INFINITE/DETERMINISTIC; rank=15[15,15]; relres=0; berr=absent:NaN; mask=7; eta=(1.57009e-16,1.40159e-13,7.00036e-14); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-022 | 16×16 square | abs_apps | `50bfbb7cbef4ae30666ea7030298490ff3b95e92a1442319492e5cf403593a5a` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=UNDECIDABLE/NONE; rank=15[15,16]; relres=absent:NaN; berr=absent:NaN; mask=7; eta=(1.57009e-16,1.41573e-13,7.07107e-14); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-023 | 16×16 square | abs_apps | `5c8df98d6051cff4234d5146bb7b399213ba31ed07cb53e984893700aba4c8d8` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=UNDECIDABLE/NONE; rank=15[15,16]; relres=absent:NaN; berr=absent:NaN; mask=7; eta=(1.57009e-16,1.42988e-13,7.14178e-14); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-024 | 16×16 square | abs_apps | `57d9d29a338b79d6641101146eb8c409b702b5defa9edf639928fa32d3cab7eb` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=UNDECIDABLE/NONE; rank=15[15,16]; relres=absent:NaN; berr=absent:NaN; mask=7; eta=(2.35514e-16,1.41424e-11,0.707107); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-025 | 16×16 square | abs_apps | `82f50fed5d62abe8ec76c47ced61c7041c7efadcf25b9af40aa81c18ba09dabc` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=UNDECIDABLE/NONE; rank=15[15,16]; relres=absent:NaN; berr=absent:NaN; mask=7; eta=(2.35514e-16,1.40007e-09,0.707107); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-026 | 16×16 square | abs_apps | `0e249f54d27cdf2048574411196228fe4db119867ceb3305ad46d0e926bd42d1` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=UNIQUE/DETERMINISTIC; rank=16[16,16]; relres=6.20634e-17; berr=4.55665e-17; mask=7; eta=(2.35514e-16,1.41421e-09,0.707107); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-027 | 16×16 square | abs_apps | `83df0fc3e5ca5d1eadce0a92eedd4f7126614228af856aa5a9a474a17d527c01` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=UNIQUE/DETERMINISTIC; rank=16[16,16]; relres=0; berr=0; mask=7; eta=(2.35514e-16,1.42836e-09,0.707107); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-028 | 16×16 square | abs_apps | `27bba074df906e0b95af463d85e60090de8d5f64bb49b70ed40abfb019468c95` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=UNIQUE/DETERMINISTIC; rank=16[16,16]; relres=0; berr=0; mask=7; eta=(2.35514e-16,1.76777e-09,0.707107); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-029 | 16×16 square | abs_apps | `0a6d287b9bb399d67236f03c06b41728e7cbc049e5732dd784462ff7a3a159d2` | `dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d` | rc=0; op=UNIQUE/DETERMINISTIC; rank=16[16,16]; relres=0; berr=0; mask=7; eta=(2.35514e-16,5.65685e-09,0.707107); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=16/16; exact binary64 integer/modular proof |
| T8-030 | 64×32 tall | rasg_bsd_2 | `e8bf379efc4a44ea4a2afe9139a10cdd98706cfe56a78b1bd7c9d29a96bd1255` | `6ed0899f55cd10683483d20205133c5c60573add8f1c9630cdb5e2a19bcc52c6` | rc=0; op=INCONSISTENT/DETERMINISTIC; rank=32[32,32]; relres=8.49531; berr=absent:NaN; mask=7; eta=(0.00227764,0.00232737,5.12242e-15); exact-field=UNKNOWN/NOT_VERIFIED | INCONSISTENT; rank(A/aug)=32/33; exact binary64 integer/modular proof |
| T8-031 | 64×32 tall | rasg_bsd_2 | `ba696300c4bf455cb2adf7526cd5812c4985b1a06360755c5bc7a3519bfb3df1` | `076a27c79e5ace2a3d47f9dd2e83e4ff6ea8872b3c2218f66c92b89b55f36560` | rc=0; op=UNIQUE/DETERMINISTIC; rank=32[32,32]; relres=0; berr=0; mask=3; eta=(2.13236e-15,3.6538e-05,no finite bound); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=32/32; exact binary64 integer/modular proof |
| T8-032 | 64×32 tall | rasg_bsd_2 | `ec0eb9ac9e6973ce404cad1c934011ecd38ae5d79c20e403c291a49f68b2f936` | `076a27c79e5ace2a3d47f9dd2e83e4ff6ea8872b3c2218f66c92b89b55f36560` | rc=0; op=UNIQUE/DETERMINISTIC; rank=32[32,32]; relres=0; berr=0; mask=3; eta=(2.05334e-15,3.58472e-05,no finite bound); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=32/32; exact binary64 integer/modular proof |
| T8-036 | 48×48 square | suitesparse_cc_by_4 | `79123b15b3f4a326842d33e5d97af59b2198b83cccf098b64db1e561e2c65c4d` | `d555c86b366a4f0d890d2b2bddf3e58af18951bb890ae98aced24b295cc27ff4` | rc=0; op=UNIQUE/DETERMINISTIC; rank=48[48,48]; relres=7.46244e-14; berr=8.7728e-17; mask=7; eta=(1.42843e-15,0.000417625,1); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=48/48; exact binary64 integer/modular proof |
| T8-037 | 66×66 square | suitesparse_cc_by_4 | `8e76e07d13cc64be06c5c35241ab7fcef5f8c147bf6541b4f1b4877c2b625180` | `6159721250fa8160ca81aecd168267095e2bc3244a37eb023b0ac9961247be41` | rc=0; op=UNIQUE/DETERMINISTIC; rank=66[66,66]; relres=4.83267e-14; berr=9.32558e-17; mask=7; eta=(1.23017e-15,0.000278465,1); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=66/66; exact binary64 integer/modular proof |
| T8-038 | 132×132 square | suitesparse_cc_by_4 | `e17764fab7e28e966541f295852cc350fa101353bc46269f2e6c3244fcc47ffe` | `d4ba2ed15110fd268126185c32f0eb333a3bdfd8a3ba913222f681659e7e3c5d` | rc=0; op=UNIQUE/DETERMINISTIC; rank=132[132,132]; relres=9.35109e-14; berr=5.07295e-17; mask=7; eta=(3.02668e-15,0.000120237,1); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=132/132; exact binary64 integer/modular proof |
| T8-039 | 153×153 square | suitesparse_cc_by_4 | `2a88ab0a9c5f9494e4e9f225944acfd6ae5b43108680328aed368b30f3cff0df` | `5243c2fd18f8f19ba78019fea1f5f58300c220cdad92eb068581253466cfa19c` | rc=0; op=UNIQUE/DETERMINISTIC; rank=153[153,153]; relres=7.02127e-14; berr=7.03209e-17; mask=7; eta=(1.78687e-15,0.000484599,1); exact-field=UNKNOWN/NOT_VERIFIED | UNIQUE; rank(A/aug)=153/153; exact binary64 integer/modular proof |

T8-012, T8-013, T8-016, and T8-017 are exactly INCONSISTENT by rank(A)<rank([A|b]), while the default operational result is INFINITE. This is an intentional semantic separation, not oracle disagreement. Nearby certificate masks and eta values guarantee only accepted nearby systems.

## Atomic decisions and reachability CNF

Atomic conditions are valid input, backend success, resolved rank, operational compatibility, full-column-rank candidate, accepted UNIQUE quality, and for each nearby profile: generator success, verifier success, and finite eta. Only implications established by the public wrapper and `certified_api.c` are encoded.

- `status_unique OR status_infinite OR status_inconsistent OR status_fail OR status_undecidable`
- `!backend_success OR valid_input`
- `!status_unique OR !status_infinite`
- `!status_unique OR !status_inconsistent`
- `!status_unique OR !status_fail`
- `!status_unique OR !status_undecidable`
- `!status_infinite OR !status_inconsistent`
- `!status_infinite OR !status_fail`
- `!status_infinite OR !status_undecidable`
- `!status_inconsistent OR !status_fail`
- `!status_inconsistent OR !status_undecidable`
- `!status_fail OR !status_undecidable`
- `!backend_success OR !status_fail`
- `!status_fail OR !backend_success`
- `!unique_profile_accepted OR unique_generator_success`
- `!unique_profile_accepted OR unique_verifier_success`
- `!unique_profile_accepted OR unique_eta_finite`
- `!unique_generator_success OR !unique_verifier_success OR !unique_eta_finite OR unique_profile_accepted`
- `!legacy_projection_unique OR status_unique`
- `!legacy_projection_unique OR unique_profile_accepted`
- `!status_unique OR !unique_profile_accepted OR legacy_projection_unique`
- `!infinite_profile_accepted OR infinite_generator_success`
- `!infinite_profile_accepted OR infinite_verifier_success`
- `!infinite_profile_accepted OR infinite_eta_finite`
- `!infinite_generator_success OR !infinite_verifier_success OR !infinite_eta_finite OR infinite_profile_accepted`
- `!legacy_projection_infinite OR status_infinite`
- `!legacy_projection_infinite OR infinite_profile_accepted`
- `!status_infinite OR !infinite_profile_accepted OR legacy_projection_infinite`
- `!inconsistent_profile_accepted OR inconsistent_generator_success`
- `!inconsistent_profile_accepted OR inconsistent_verifier_success`
- `!inconsistent_profile_accepted OR inconsistent_eta_finite`
- `!inconsistent_generator_success OR !inconsistent_verifier_success OR !inconsistent_eta_finite OR inconsistent_profile_accepted`
- `!legacy_projection_inconsistent OR status_inconsistent`
- `!legacy_projection_inconsistent OR inconsistent_profile_accepted`
- `!status_inconsistent OR !inconsistent_profile_accepted OR legacy_projection_inconsistent`

## MC/DC traceability

| условие API | MC/DC-пара | abs-apps slot IDs | хеши входов | ожидаемые выходы/оракул | тест | CI job |
|---|---|---|---|---|---|---|
| rank_resolved | rank_decision: default `False` → wide_rank_band `True` | T8-022, T8-022 | T8-022:A=50bfbb7cbef4ae30666ea7030298490ff3b95e92a1442319492e5cf403593a5a,b=dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d<br>T8-022:A=50bfbb7cbef4ae30666ea7030298490ff3b95e92a1442319492e5cf403593a5a,b=dbd8ebb4d364765882694170cedf5afc7702dd5338a7198705c45b613f6e1c9d | decision `False`→`True`; exact oracles remain UNIQUE/UNIQUE | `tests/test_api_regression_decisions.py` | `api-regression` |
| operational_compatible | compatibility_decision: default `True` → tight_compatibility `False` | T8-001, T8-001 | T8-001:A=9a45be709cd5db7673e00a2feec677cb87c0f9993e582e9f4b5a9e020b6bef90,b=6c15dc9f9b22ba5c13609522990274fbb536cb54fdea237119fca3914bfd60df<br>T8-001:A=9a45be709cd5db7673e00a2feec677cb87c0f9993e582e9f4b5a9e020b6bef90,b=6c15dc9f9b22ba5c13609522990274fbb536cb54fdea237119fca3914bfd60df | decision `True`→`False`; exact oracles remain INFINITE/INFINITE | `tests/test_api_regression_decisions.py` | `api-regression` |
| unique_quality | unique_acceptance: default `True` → tight_quality `False` | T8-036, T8-036 | T8-036:A=79123b15b3f4a326842d33e5d97af59b2198b83cccf098b64db1e561e2c65c4d,b=d555c86b366a4f0d890d2b2bddf3e58af18951bb890ae98aced24b295cc27ff4<br>T8-036:A=79123b15b3f4a326842d33e5d97af59b2198b83cccf098b64db1e561e2c65c4d,b=d555c86b366a4f0d890d2b2bddf3e58af18951bb890ae98aced24b295cc27ff4 | decision `True`→`False`; exact oracles remain UNIQUE/UNIQUE | `tests/test_api_regression_decisions.py` | `api-regression` |
| backend_success | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| full_column_rank | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| inconsistent_eta_finite | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| inconsistent_generator_success | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| inconsistent_verifier_success | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| infinite_eta_finite | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| infinite_generator_success | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| infinite_verifier_success | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| unique_eta_finite | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| unique_generator_success | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| unique_verifier_success | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |
| valid_input | no strict masking pair in real 36-case observations | — | — | uncovered; no synthetic gap fixture claimed | `tests/test_api_regression_decisions.py` | `api-regression` |

The three real pairs are T8-001 default/tight-compatibility for compatibility, T8-022 default/wide-rank-band for rank resolution, and T8-036 default/tight-quality for UNIQUE quality. All other modeled atoms are explicitly uncovered by strict masking MC/DC in real `abs-apps` inputs. No purpose-built gap fixture is claimed.

## Certificate thread-determinism defect found and fixed

Before the baseline, T8-038 `eta_inconsistent` changed from 2.0261372389521175 to 2.1063529960959717 when OpenBLAS changed from one to two threads. The full-row-rank generator used the direction of a rounding-level DGELSY residual. Source fix `49ec7e3` replaces that proposal with a canonical normalized-row witness; the unchanged strict verifier accepts it. T8-038 now returns 0.9999999890199766 at 1, 2, and 4 threads. The 36-case cross-thread AC requires exact discrete fields and `atol=1e-12` or `rtol=1e-10` for floating diagnostics.

## Post-separation rerun criteria

- Discover and execute the same 36 IDs with identical A/b hashes.
- The solving API must reproduce operational status/rank/residual/quality fields within their current semantics; `x` is checked only if the new solving API exposes it.
- The certification API must reproduce mask, generator/verifier codes and finite eta guarantees without treating them as exact-source classifications.
- Recomposition must match the current combined compatibility output, excluding time.
- Exact oracle ranks/classes must remain unchanged, especially the four semantic-mismatch cases.
- Empty, partial, skipped, duplicated, hash-mismatched, or wrong-result runs must fail.
- Any intended semantic change requires review and an explicit rebaseline; snapshot regeneration alone is not acceptance.

CI job names and measured qualification resources are finalized by the CI/qualification milestone.
