# Changelog

## [0.5.0](https://github.com/metronforge/affine-bundle-solver/compare/v0.4.2...v0.5.0) (2026-09-09)


### ⚠ BREAKING CHANGES

* **router:** out[0] of bsolve_router_meta_api returns 5 for UNDECIDABLE where it previously returned 4.
* certified_api.h and status_certificate.h moved from src/ to include/affine_bundle/.

### Features

* build as a library, with public headers and a streaming API ([d62ecb4](https://github.com/metronforge/affine-bundle-solver/commit/d62ecb4ab0eb329520ae754a1438455535ae4ca3))
* initial public release of the affine-bundle solver ([48b9fce](https://github.com/metronforge/affine-bundle-solver/commit/48b9fce6742f02c69ef98c31c4d008e0fc6bcaee))
* **router:** publish the solution-quality threshold ([e4ca740](https://github.com/metronforge/affine-bundle-solver/commit/e4ca7401332fcb86d4a985744b5acb0c4b948e51))


### Bug fixes

* **build:** give the sanitizer and coverage scripts the new include path ([fdd69d0](https://github.com/metronforge/affine-bundle-solver/commit/fdd69d00eb43d0cef90e66782a3a34598979456f))
* **build:** keep -ffast-math off the link line to stop an FTZ/DAZ leak ([9e02cf3](https://github.com/metronforge/affine-bundle-solver/commit/9e02cf3586e6a884800be2643610be1da8304d52))
* **build:** keep ARCH_FLAGS empty when explicitly set to empty ([799a84c](https://github.com/metronforge/affine-bundle-solver/commit/799a84c7bc95b8a09c21c356f713b0615b65c594))
* **router:** apply the quality gate on both paths out of the source repair ([c6b487b](https://github.com/metronforge/affine-bundle-solver/commit/c6b487bfbb1861bb639f0acc6790b7d1570431b2))
* **router:** reject non-finite input via bit-pattern test ([45ab675](https://github.com/metronforge/affine-bundle-solver/commit/45ab675ffad20204c9458ecff3117a22597c525e))
* **router:** report UNDECIDABLE distinctly, and fix the meta layout on ([961a9e8](https://github.com/metronforge/affine-bundle-solver/commit/961a9e8a0ae70df5e412109d3e70970a7d340e59))
* **test:** aim the adversarial left-null candidate instead of taking the first ([c035dad](https://github.com/metronforge/affine-bundle-solver/commit/c035dadecaf357832b626c2043c1c0ce0daa9ba5))
* **test:** stop asserting that rounding noise clears the verifier envelope ([0b14329](https://github.com/metronforge/affine-bundle-solver/commit/0b14329ac2fa94d77a92a6699dc8575f563444c5))


### Manuscript and documentation

* add a 300-word abstract for journals with a length cap ([9c3406d](https://github.com/metronforge/affine-bundle-solver/commit/9c3406db6dc2a85c6b3ffbfbbfb53372bf75fb87))
* record why the certified insertion routine was chosen ([144ccc0](https://github.com/metronforge/affine-bundle-solver/commit/144ccc061d0c808168bc60abd51e431863abab12))
* restate the allocation-check task with a reproducible count ([a6840e3](https://github.com/metronforge/affine-bundle-solver/commit/a6840e330b28c0b4e4b4a9bd377a86da77dbaa36))

## [0.4.2](https://github.com/metronforge/affine-bundle-solver/compare/v0.4.1...v0.4.2) (2026-09-09)


### Manuscript and documentation

* restate the allocation-check task with a reproducible count ([a6840e3](https://github.com/metronforge/affine-bundle-solver/commit/a6840e330b28c0b4e4b4a9bd377a86da77dbaa36))

## [0.4.1](https://github.com/metronforge/affine-bundle-solver/compare/v0.4.0...v0.4.1) (2026-09-09)


### Manuscript and documentation

* add a 300-word abstract for journals with a length cap ([9c3406d](https://github.com/metronforge/affine-bundle-solver/commit/9c3406db6dc2a85c6b3ffbfbbfb53372bf75fb87))

## [0.4.0](https://github.com/metronforge/affine-bundle-solver/compare/v0.3.1...v0.4.0) (2026-09-08)


### Features

* **router:** publish the solution-quality threshold ([e4ca740](https://github.com/metronforge/affine-bundle-solver/commit/e4ca7401332fcb86d4a985744b5acb0c4b948e51))


### Bug fixes

* **router:** apply the quality gate on both paths out of the source repair ([c6b487b](https://github.com/metronforge/affine-bundle-solver/commit/c6b487bfbb1861bb639f0acc6790b7d1570431b2))

## [0.3.1](https://github.com/metronforge/affine-bundle-solver/compare/v0.3.0...v0.3.1) (2026-09-08)


### Continuous integration

* close the release pull request computed before the tag existed ([df80cfe](https://github.com/metronforge/affine-bundle-solver/commit/df80cfeb45b2159d69c70f30d8c374d55dfaea57))

## [0.3.0](https://github.com/metronforge/affine-bundle-solver/compare/v0.2.1...v0.3.0) (2026-09-08)


### ⚠ BREAKING CHANGES

* **router:** out[0] of bsolve_router_meta_api returns 5 for UNDECIDABLE where it previously returned 4.
* certified_api.h and status_certificate.h moved from src/ to include/affine_bundle/.

### Features

* build as a library, with public headers and a streaming API ([d62ecb4](https://github.com/metronforge/affine-bundle-solver/commit/d62ecb4ab0eb329520ae754a1438455535ae4ca3))


### Bug fixes

* **build:** give the sanitizer and coverage scripts the new include path ([fdd69d0](https://github.com/metronforge/affine-bundle-solver/commit/fdd69d00eb43d0cef90e66782a3a34598979456f))
* **router:** report UNDECIDABLE distinctly, and fix the meta layout on ([961a9e8](https://github.com/metronforge/affine-bundle-solver/commit/961a9e8a0ae70df5e412109d3e70970a7d340e59))
* **test:** stop asserting that rounding noise clears the verifier envelope ([0b14329](https://github.com/metronforge/affine-bundle-solver/commit/0b14329ac2fa94d77a92a6699dc8575f563444c5))


### Manuscript and documentation

* record why the certified insertion routine was chosen ([144ccc0](https://github.com/metronforge/affine-bundle-solver/commit/144ccc061d0c808168bc60abd51e431863abab12))


### Tests

* cover the streaming API and the threshold contract ([020cfa1](https://github.com/metronforge/affine-bundle-solver/commit/020cfa15edce1bc66de4932ea9d6ce2b538d0cd6))


### Continuous integration

* build with CMake, install, and check BLAS independence ([67f4971](https://github.com/metronforge/affine-bundle-solver/commit/67f497147cb6d9250d37388e145609f92d9db4e0))
* create the release as a draft so the archive can be attached ([f7ecf32](https://github.com/metronforge/affine-bundle-solver/commit/f7ecf3276a95e50224317497b1fa4ba34193c053))

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
