# Changelog

## [0.2.1](https://github.com/metronforge/affine-bundle-solver/compare/v0.2.0...v0.2.1) (2026-09-07)


### Continuous integration

* modify release workflow for draft releases ([22bdea8](https://github.com/metronforge/affine-bundle-solver/commit/22bdea852147c5b0aaf963d6fed75f2d2c64dc63))

## [0.2.0](https://github.com/metronforge/affine-bundle-solver/compare/v0.1.0...v0.2.0) (2026-09-07)


### Features

* initial public release of the affine-bundle solver ([48b9fce](https://github.com/metronforge/affine-bundle-solver/commit/48b9fce6742f02c69ef98c31c4d008e0fc6bcaee))


### Bug fixes

* **build:** keep -ffast-math off the link line to stop an FTZ/DAZ leak ([9e02cf3](https://github.com/metronforge/affine-bundle-solver/commit/9e02cf3586e6a884800be2643610be1da8304d52))
* **build:** keep ARCH_FLAGS empty when explicitly set to empty ([799a84c](https://github.com/metronforge/affine-bundle-solver/commit/799a84c7bc95b8a09c21c356f713b0615b65c594))
* **router:** reject non-finite input via bit-pattern test ([45ab675](https://github.com/metronforge/affine-bundle-solver/commit/45ab675ffad20204c9458ecff3117a22597c525e))
* **test:** aim the adversarial left-null candidate instead of taking the first ([c035dad](https://github.com/metronforge/affine-bundle-solver/commit/c035dadecaf357832b626c2043c1c0ce0daa9ba5))


### Continuous integration

* add sanitizers, coverage reporting and automated releases ([190454c](https://github.com/metronforge/affine-bundle-solver/commit/190454c81c40ea4976ac6744af3f92ce08f3fe7d))
* build the manuscript and fail on unresolved references ([f48ea53](https://github.com/metronforge/affine-bundle-solver/commit/f48ea530095d4a50500fde554a94d58da66ece10))
* make the clang job required ([75505c0](https://github.com/metronforge/affine-bundle-solver/commit/75505c0ec2d53a260a9252af80d6cf8294f64073))
