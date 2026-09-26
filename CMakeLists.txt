cmake_minimum_required(VERSION 3.16)

project(affine-bundle-solver
        VERSION 0.4.4 # x-release-please-version
        DESCRIPTION "Certifying dense solver for Ax = b that assumes neither consistency, nor full rank, nor uniqueness"
        HOMEPAGE_URL "https://github.com/metronforge/affine-bundle-solver"
        LANGUAGES C)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

# ---------------------------------------------------------------------------
# THE FLOATING-POINT CONTRACT.  Read before changing any flag.
#
# build.sh stays the canonical way to reproduce the manuscript.  This file
# exists so the library can be built and installed without a Python
# installation carrying a SciPy wheel, but it must reproduce the same split:
#
#   src/bsolver.c          -O3 <arch> -fopenmp -ffast-math   COMPILE ONLY
#   src/formation_guard.c  ABS_STRICT_FP_FLAGS
#   src/status_certificate.c, src/certified_api.c, both probes
#                          ABS_STRICT_FP_FLAGS
#
# ABS_STRICT_FP_FLAGS is -O2 -frounding-math -fno-fast-math -ffp-contract=off.
# -frounding-math makes the compiler honour the dynamic rounding mode but does
# not forbid contraction: GCC's GNU-mode default is -ffp-contract=fast and
# clang's is =on, so on an FMA-capable target a*b+c may become one fused
# instruction with a single rounding.  Every such site in the strict kernels
# is an upward-rounded sum of non-negative terms, so fusion would not make a
# certificate unsound, but eta_S^+ would then depend on the build target.
# The strict_fp_contraction test compiles the strict sources with these exact
# flags for an FMA-capable target and fails on any fused instruction.
#
# formation_guard.c is compiled strictly and then linked INTO the fast
# library.  That is why it is an OBJECT library here: object libraries carry
# their own compile options and contribute nothing to their consumer's link
# line.
#
# -ffast-math must never reach a link line.  Under clang the driver then adds
# a startup object whose constructor sets the MXCSR FTZ and DAZ bits for the
# whole process.  Those bits are runtime state, so the strict proof kernels
# running in the same process would flush to zero exactly the subnormal
# inputs the certificate battery exists to exercise, and those checks would
# pass vacuously.  Observed under clang 18, not under GCC 13.
#
# CMake puts CMAKE_C_FLAGS on the link line as well as the compile line, so a
# flag placed there does NOT stay on the compile step.  Per-target
# target_compile_options is the only safe place for -ffast-math, and the
# check below refuses to configure if the contract is broken from outside.
# ---------------------------------------------------------------------------

foreach(_var CMAKE_C_FLAGS CMAKE_C_FLAGS_${CMAKE_BUILD_TYPE}
             CMAKE_EXE_LINKER_FLAGS CMAKE_SHARED_LINKER_FLAGS)
  if("${${_var}}" MATCHES "fast-math|funsafe-math|ffinite-math-only|Ofast")
    message(FATAL_ERROR
      "${_var} contains a fast-math flag: '${${_var}}'.\n"
      "CMake applies these to both compilation and linking, which would put "
      "-ffast-math on the link line of the strict kernels. Pass architecture "
      "tuning through ABS_ARCH_FLAGS instead.")
  endif()
endforeach()

# No default build type.  A configuration such as Release would inject its own
# -O flags alongside the per-target ones set below, and which of the two wins
# is a property of the compiler's argument order rather than of this file.
# Optimisation is stated explicitly per target.
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "" CACHE STRING "Left empty on purpose; see comment" FORCE)
endif()

set(ABS_ARCH_FLAGS "-march=native" CACHE STRING
    "Architecture flags, fast router only. Set to \"\" for a portable build.")
set(ABS_BLAS "system" CACHE STRING
    "BLAS provider: 'system' (find_package) or 'scipy-openblas' (what build.sh links)")
set_property(CACHE ABS_BLAS PROPERTY STRINGS system scipy-openblas)
option(ABS_BUILD_EXAMPLES "Build the C examples in examples/" ON)
option(ABS_BUILD_TESTING  "Register the probes, examples and Python batteries with CTest" ON)
option(ABS_SANITIZE "Build with AddressSanitizer and UndefinedBehaviorSanitizer" OFF)
option(ABS_COVERAGE "Build with coverage instrumentation" OFF)

if(ABS_SANITIZE AND ABS_COVERAGE)
  message(FATAL_ERROR "ABS_SANITIZE and ABS_COVERAGE do not compose; configure separate build trees")
endif()

# enable_testing() has to run in the top-level list file before any
# add_subdirectory(), or add_test() calls made in a subdirectory are accepted
# and then silently dropped from the test set.
if(ABS_BUILD_TESTING)
  enable_testing()
endif()

# ---------------------------------------------------------------------------
# BLAS provider
#
# Until this release the sources named SciPy's prefixed symbols directly, so
# the C code itself could only link that one library.  src/blas_symbols.h now
# makes the prefix a build-time choice; ABS_SCIPY_BLAS selects it.
# ---------------------------------------------------------------------------

if(ABS_BLAS STREQUAL "system")
  find_package(BLAS REQUIRED)
  find_package(LAPACK REQUIRED)
  set(ABS_BLAS_LIBRARIES BLAS::BLAS LAPACK::LAPACK)
  set(ABS_BLAS_DEFINES "")
  set(ABS_BLAS_RPATH "")
  set(ABS_BLAS_DESCRIPTION "system (${BLAS_LIBRARIES})")

elseif(ABS_BLAS STREQUAL "scipy-openblas")
  # The path build.sh takes.  Kept because CI images may carry no system BLAS,
  # and because a bit-level comparison against build.sh is only meaningful
  # when the BLAS underneath is the same library.
  find_package(Python3 COMPONENTS Interpreter REQUIRED)
  execute_process(
    COMMAND ${Python3_EXECUTABLE} -c
"import glob, os, scipy\n\
base = os.path.dirname(scipy.__file__)\n\
xs = glob.glob(os.path.join(base, '..', 'scipy.libs', 'libscipy_openblas*.so'))\n\
if not xs: raise SystemExit('SciPy OpenBLAS shared library not found')\n\
print(os.path.realpath(xs[0]))"
    OUTPUT_VARIABLE ABS_SCIPY_OPENBLAS
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE _scipy_rc)
  if(NOT _scipy_rc EQUAL 0)
    message(FATAL_ERROR "ABS_BLAS=scipy-openblas but SciPy's OpenBLAS was not found")
  endif()
  add_library(abs_scipy_openblas SHARED IMPORTED)
  set_target_properties(abs_scipy_openblas PROPERTIES
    IMPORTED_LOCATION "${ABS_SCIPY_OPENBLAS}"
    IMPORTED_NO_SONAME TRUE)
  get_filename_component(ABS_BLAS_RPATH "${ABS_SCIPY_OPENBLAS}" DIRECTORY)
  set(ABS_BLAS_LIBRARIES abs_scipy_openblas)
  set(ABS_BLAS_DEFINES ABS_SCIPY_BLAS)
  set(ABS_BLAS_DESCRIPTION "scipy-openblas (${ABS_SCIPY_OPENBLAS})")

else()
  message(FATAL_ERROR "ABS_BLAS must be 'system' or 'scipy-openblas', got '${ABS_BLAS}'")
endif()

find_package(OpenMP REQUIRED COMPONENTS C)

# clang emits __atomic_compare_exchange from libatomic for reduction(max:) on
# a double, where GCC routes the same construct through libgomp.  Without the
# library the clang build links but the shared object fails to load.  Under
# GCC --as-needed drops the unused dependency.
find_library(ABS_ATOMIC_LIBRARY atomic)
if(NOT ABS_ATOMIC_LIBRARY)
  set(ABS_ATOMIC_LIBRARY "")
endif()

separate_arguments(ABS_ARCH_FLAG_LIST UNIX_COMMAND "${ABS_ARCH_FLAGS}")

# One definition of the strict floating-point flags; see the contract above.
set(ABS_STRICT_FP_FLAGS -O2 -frounding-math -fno-fast-math -ffp-contract=off)

set(ABS_INSTRUMENTATION "")
if(ABS_SANITIZE)
  set(ABS_INSTRUMENTATION -fsanitize=address,undefined -fno-omit-frame-pointer -g)
elseif(ABS_COVERAGE)
  set(ABS_INSTRUMENTATION --coverage -g)
endif()

# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

# Strict kernel that ends up inside the fast library.
add_library(abs_formation_guard_obj OBJECT src/formation_guard.c)
set_target_properties(abs_formation_guard_obj PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_compile_options(abs_formation_guard_obj PRIVATE
  ${ABS_STRICT_FP_FLAGS} ${ABS_INSTRUMENTATION})
target_compile_definitions(abs_formation_guard_obj PRIVATE ${ABS_BLAS_DEFINES})
target_include_directories(abs_formation_guard_obj PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)

# Fast router.  Sketch and proposal arithmetic may use fast-math; no
# source-rank lower bound is trusted until the formation guard verifies it.
add_library(abs_router_obj OBJECT src/bsolver.c)
set_target_properties(abs_router_obj PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_compile_options(abs_router_obj PRIVATE
  -O3 ${ABS_ARCH_FLAG_LIST} -fopenmp -ffast-math ${ABS_INSTRUMENTATION})
target_compile_definitions(abs_router_obj PRIVATE ${ABS_BLAS_DEFINES})
target_include_directories(abs_router_obj PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)

# ---------------------------------------------------------------------------
# Libraries
# ---------------------------------------------------------------------------

add_library(affine_bundle_solver SHARED
  $<TARGET_OBJECTS:abs_router_obj>
  $<TARGET_OBJECTS:abs_formation_guard_obj>)
set_target_properties(affine_bundle_solver PROPERTIES LINKER_LANGUAGE C)
target_link_libraries(affine_bundle_solver
  PRIVATE OpenMP::OpenMP_C ${ABS_BLAS_LIBRARIES} ${ABS_ATOMIC_LIBRARY} m)
target_link_options(affine_bundle_solver PRIVATE ${ABS_INSTRUMENTATION})
target_include_directories(affine_bundle_solver
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
         $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

add_library(status_verifier SHARED src/status_certificate.c)
target_compile_options(status_verifier PRIVATE
  ${ABS_STRICT_FP_FLAGS} ${ABS_INSTRUMENTATION})
target_link_options(status_verifier PRIVATE ${ABS_INSTRUMENTATION})
target_link_libraries(status_verifier PRIVATE m)
target_include_directories(status_verifier
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
         $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

add_library(certified_solver SHARED src/certified_api.c)
target_compile_options(certified_solver PRIVATE
  ${ABS_STRICT_FP_FLAGS} ${ABS_INSTRUMENTATION})
target_compile_definitions(certified_solver PRIVATE ${ABS_BLAS_DEFINES})
target_link_options(certified_solver PRIVATE ${ABS_INSTRUMENTATION})
target_link_libraries(certified_solver
  PRIVATE affine_bundle_solver status_verifier ${ABS_BLAS_LIBRARIES} m)
target_include_directories(certified_solver
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
         $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
target_include_directories(certified_solver PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

# certified_solver links the other two, so an installed copy has to be able to
# find its siblings next to itself.  build.sh passes -Wl,-rpath,'$ORIGIN' for
# exactly this; without it the installed library loads only when the prefix
# happens to be on the default search path.
set(ABS_RPATH "$ORIGIN")
if(ABS_BLAS_RPATH)
  list(APPEND ABS_RPATH "${ABS_BLAS_RPATH}")
endif()
set_target_properties(affine_bundle_solver status_verifier certified_solver
  PROPERTIES INSTALL_RPATH "${ABS_RPATH}")
if(ABS_BLAS_RPATH)
  set_target_properties(affine_bundle_solver certified_solver
    PROPERTIES BUILD_RPATH "${ABS_BLAS_RPATH}")
endif()

# ---------------------------------------------------------------------------
# Probes.  Both gate the build, exactly as in build.sh.  A library that
# reached the install step with a leaked FP mode is not a library anyone
# should install, so this is a build failure and not a test failure.
# ---------------------------------------------------------------------------

add_executable(abs_rounding_probe src/rounding_probe.c)
target_compile_options(abs_rounding_probe PRIVATE ${ABS_STRICT_FP_FLAGS})
target_link_libraries(abs_rounding_probe PRIVATE m)
add_custom_command(TARGET abs_rounding_probe POST_BUILD
  COMMAND abs_rounding_probe
  COMMENT "Probe: directed rounding is distinguishable")

add_executable(abs_mxcsr_probe src/mxcsr_probe.c)
target_compile_options(abs_mxcsr_probe PRIVATE
  ${ABS_STRICT_FP_FLAGS} ${ABS_INSTRUMENTATION})
target_link_options(abs_mxcsr_probe PRIVATE ${ABS_INSTRUMENTATION})
target_link_libraries(abs_mxcsr_probe PRIVATE ${CMAKE_DL_LIBS})

# The strict libraries must not be built before the rounding probe has had a
# chance to fail.
add_dependencies(status_verifier abs_rounding_probe)
add_dependencies(certified_solver abs_rounding_probe abs_mxcsr_probe)

# Separate compilation is necessary but not sufficient: FTZ/DAZ are runtime
# MXCSR state and a fast-math link can set them process-wide at load time.
# Verify on the artefacts actually produced here.
add_custom_command(TARGET certified_solver POST_BUILD
  COMMAND abs_mxcsr_probe
          $<TARGET_FILE:affine_bundle_solver> $<TARGET_FILE:certified_solver>
  COMMENT "Probe: loading the fast library does not change the process FP mode")

# Structural counterpart: the probe shows the mode did not leak on this
# toolchain, this shows the flag was never on the link line at all, which is
# the property the contract is stated in.  A toolchain that starts adding the
# FTZ/DAZ constructor tomorrow is then caught by construction.
add_custom_command(TARGET affine_bundle_solver POST_BUILD
  COMMAND ${CMAKE_COMMAND}
          -DLINK_RULE=${CMAKE_BINARY_DIR}/CMakeFiles/affine_bundle_solver.dir/link.txt
          -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_link_contract.cmake
  COMMENT "Contract: no fast-math flag on the router link line")

# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------

if(ABS_BUILD_EXAMPLES)
  add_subdirectory(examples)
endif()

# ---------------------------------------------------------------------------
# Install and export
#
# formation_guard.h and blas_symbols.h are deliberately not installed: the
# first exposes the directed-rounding primitives the guard is built from, the
# second is a build-time symbol selection.  Neither is an interface anyone
# outside the library should call.
# ---------------------------------------------------------------------------

install(TARGETS affine_bundle_solver status_verifier certified_solver
        EXPORT affine-bundle-solverTargets
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(DIRECTORY include/affine_bundle
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
        FILES_MATCHING PATTERN "*.h")

install(EXPORT affine-bundle-solverTargets
        FILE affine-bundle-solverTargets.cmake
        NAMESPACE affine-bundle-solver::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/affine-bundle-solver)

configure_package_config_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/cmake/affine-bundle-solverConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/affine-bundle-solverConfig.cmake
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/affine-bundle-solver)
write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/affine-bundle-solverConfigVersion.cmake
  VERSION ${PROJECT_VERSION} COMPATIBILITY SameMinorVersion)
install(FILES
        ${CMAKE_CURRENT_BINARY_DIR}/affine-bundle-solverConfig.cmake
        ${CMAKE_CURRENT_BINARY_DIR}/affine-bundle-solverConfigVersion.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/affine-bundle-solver)

configure_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/cmake/affine-bundle-solver.pc.in
  ${CMAKE_CURRENT_BINARY_DIR}/affine-bundle-solver.pc @ONLY)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/affine-bundle-solver.pc
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

if(ABS_BUILD_TESTING)
  add_executable(abs_certified_diag_test tests/test_certified_diag.c)
  target_compile_options(abs_certified_diag_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_options(abs_certified_diag_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_libraries(abs_certified_diag_test PRIVATE
    certified_solver affine_bundle_solver status_verifier m)
  add_test(NAME test_certified_diag COMMAND abs_certified_diag_test)

  # A separately compiled router makes the one-execution hook observable to
  # this test without adding a test counter to any installed public library.
  add_library(abs_router_once_obj OBJECT src/bsolver.c)
  target_compile_options(abs_router_once_obj PRIVATE
    -O3 ${ABS_ARCH_FLAG_LIST} -fopenmp -ffast-math ${ABS_INSTRUMENTATION})
  target_compile_definitions(abs_router_once_obj PRIVATE
    ${ABS_BLAS_DEFINES} ABS_TEST_ROUTER_EXECUTIONS)
  target_include_directories(abs_router_once_obj PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)
  add_executable(abs_certified_diag_once_test
    tests/test_certified_diag_once.c src/certified_api.c
    $<TARGET_OBJECTS:abs_router_once_obj>
    $<TARGET_OBJECTS:abs_formation_guard_obj>)
  target_compile_options(abs_certified_diag_once_test PRIVATE
    ${ABS_STRICT_FP_FLAGS} ${ABS_INSTRUMENTATION})
  target_compile_definitions(abs_certified_diag_once_test PRIVATE ${ABS_BLAS_DEFINES})
  target_include_directories(abs_certified_diag_once_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_link_options(abs_certified_diag_once_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_libraries(abs_certified_diag_once_test PRIVATE
    status_verifier OpenMP::OpenMP_C ${ABS_BLAS_LIBRARIES} ${ABS_ATOMIC_LIBRARY} m)
  add_test(NAME test_certified_diag_once COMMAND abs_certified_diag_once_test)

  # Build the audit source with an internal test-only solve counter. This
  # confirms the combined path reuses the identical UNIQUE/INFINITE source
  # least-squares witness while leaving the normalized INCONSISTENT solve.
  add_executable(abs_certified_reuse_test
    tests/test_certified_reuse.c src/certified_api.c
    $<TARGET_OBJECTS:abs_router_obj>
    $<TARGET_OBJECTS:abs_formation_guard_obj>)
  target_compile_options(abs_certified_reuse_test PRIVATE
    ${ABS_STRICT_FP_FLAGS} ${ABS_INSTRUMENTATION})
  target_compile_definitions(abs_certified_reuse_test PRIVATE
    ${ABS_BLAS_DEFINES} ABS_TEST_CERTIFIED_LSTSQ)
  target_include_directories(abs_certified_reuse_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_link_options(abs_certified_reuse_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_libraries(abs_certified_reuse_test PRIVATE
    status_verifier OpenMP::OpenMP_C ${ABS_BLAS_LIBRARIES} ${ABS_ATOMIC_LIBRARY} m)
  add_test(NAME test_certified_reuse COMMAND abs_certified_reuse_test)

  # Linker wrapping counts every QRCP invocation made by the audit source and
  # verifies that the compatible-tall fallback factors its invariant matrix
  # once (one workspace query plus one executing call).  The test also hashes
  # the exact factorization input before LAPACK mutates it in place.
  add_executable(abs_reusable_qrcp_test
    tests/test_reusable_qrcp.c src/certified_api.c
    $<TARGET_OBJECTS:abs_router_obj>
    $<TARGET_OBJECTS:abs_formation_guard_obj>)
  target_compile_options(abs_reusable_qrcp_test PRIVATE
    ${ABS_STRICT_FP_FLAGS} ${ABS_INSTRUMENTATION})
  target_compile_definitions(abs_reusable_qrcp_test PRIVATE ${ABS_BLAS_DEFINES})
  target_include_directories(abs_reusable_qrcp_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_link_options(abs_reusable_qrcp_test PRIVATE ${ABS_INSTRUMENTATION})
  if(ABS_BLAS STREQUAL "scipy-openblas")
    target_link_options(abs_reusable_qrcp_test PRIVATE -Wl,--wrap=scipy_dgeqp3_)
  else()
    target_link_options(abs_reusable_qrcp_test PRIVATE -Wl,--wrap=dgeqp3_)
  endif()
  target_link_libraries(abs_reusable_qrcp_test PRIVATE
    status_verifier OpenMP::OpenMP_C ${ABS_BLAS_LIBRARIES} ${ABS_ATOMIC_LIBRARY} m)
  add_test(NAME test_reusable_qrcp COMMAND abs_reusable_qrcp_test)

  add_executable(abs_reusable_qrcp_enomem_test
    tests/test_reusable_qrcp_enomem.c src/certified_api.c
    $<TARGET_OBJECTS:abs_router_obj>
    $<TARGET_OBJECTS:abs_formation_guard_obj>)
  target_compile_options(abs_reusable_qrcp_enomem_test PRIVATE
    ${ABS_STRICT_FP_FLAGS} ${ABS_INSTRUMENTATION})
  target_compile_definitions(abs_reusable_qrcp_enomem_test PRIVATE
    ${ABS_BLAS_DEFINES} ABS_TEST_QRCP_ALLOC)
  target_include_directories(abs_reusable_qrcp_enomem_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_link_options(abs_reusable_qrcp_enomem_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_libraries(abs_reusable_qrcp_enomem_test PRIVATE
    status_verifier OpenMP::OpenMP_C ${ABS_BLAS_LIBRARIES} ${ABS_ATOMIC_LIBRARY} m)
  add_test(NAME test_reusable_qrcp_enomem COMMAND abs_reusable_qrcp_enomem_test)

  add_executable(abs_reusable_qrcp_reentrant_test tests/test_reusable_qrcp_reentrant.c)
  target_compile_options(abs_reusable_qrcp_reentrant_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_options(abs_reusable_qrcp_reentrant_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_libraries(abs_reusable_qrcp_reentrant_test PRIVATE
    certified_solver affine_bundle_solver status_verifier OpenMP::OpenMP_C m)
  add_test(NAME test_reusable_qrcp_reentrant COMMAND abs_reusable_qrcp_reentrant_test)

  # Exercise the actual private SVD state, including both compact-VT readers.
  add_executable(abs_dgesdd_core_state_test
    tests/test_dgesdd_core_state.c
    $<TARGET_OBJECTS:abs_formation_guard_obj>)
  target_compile_options(abs_dgesdd_core_state_test PRIVATE
    -O3 ${ABS_ARCH_FLAG_LIST} -fopenmp -ffast-math ${ABS_INSTRUMENTATION})
  target_compile_definitions(abs_dgesdd_core_state_test PRIVATE ${ABS_BLAS_DEFINES})
  target_include_directories(abs_dgesdd_core_state_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_link_options(abs_dgesdd_core_state_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_libraries(abs_dgesdd_core_state_test PRIVATE
    OpenMP::OpenMP_C ${ABS_BLAS_LIBRARIES} ${ABS_ATOMIC_LIBRARY} m)
  add_test(NAME test_dgesdd_core_state COMMAND abs_dgesdd_core_state_test)
  # Native processes provide solver-owned leak coverage without CPython's
  # process-exit allocations. The ENOMEM fixture is kept separate so its
  # intentional ASan return-NULL policy cannot affect other tests.
  add_executable(abs_native_solver_lifecycle_test tests/test_native_solver_lifecycle.c)
  target_compile_options(abs_native_solver_lifecycle_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_options(abs_native_solver_lifecycle_test PRIVATE ${ABS_INSTRUMENTATION})
  target_link_libraries(abs_native_solver_lifecycle_test PRIVATE
    certified_solver affine_bundle_solver status_verifier m)
  add_test(NAME test_native_solver_lifecycle COMMAND abs_native_solver_lifecycle_test)

  if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    add_executable(abs_stream_storage_native_test tests/test_stream_storage_native.c)
    target_compile_options(abs_stream_storage_native_test PRIVATE ${ABS_INSTRUMENTATION})
    target_link_options(abs_stream_storage_native_test PRIVATE ${ABS_INSTRUMENTATION})
    target_link_libraries(abs_stream_storage_native_test PRIVATE affine_bundle_solver m)
    add_test(NAME test_stream_storage_native COMMAND abs_stream_storage_native_test)
  endif()
  add_test(NAME rounding_probe COMMAND abs_rounding_probe)
  add_test(NAME mxcsr_probe COMMAND abs_mxcsr_probe
           $<TARGET_FILE:affine_bundle_solver> $<TARGET_FILE:certified_solver>)
  add_test(NAME link_contract COMMAND ${CMAKE_COMMAND}
           -DLINK_RULE=${CMAKE_BINARY_DIR}/CMakeFiles/affine_bundle_solver.dir/link.txt
           -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_link_contract.cmake)

  # Structural counterpart for the strict kernels: compiled with the exact
  # ABS_STRICT_FP_FLAGS for an FMA-capable target, they must contain no fused
  # multiply-add.  The portable baseline has no FMA, so checking the objects
  # built above would pass vacuously.
  list(TRANSFORM ABS_BLAS_DEFINES PREPEND "-D" OUTPUT_VARIABLE _abs_blas_define_flags)
  add_test(NAME strict_fp_contraction
           COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_fp_contraction.sh
                   ${CMAKE_C_COMPILER}
                   -- ${ABS_STRICT_FP_FLAGS} ${_abs_blas_define_flags}
                      -I${CMAKE_CURRENT_SOURCE_DIR}/include
                      -I${CMAKE_CURRENT_SOURCE_DIR}/src
                   -- ${CMAKE_CURRENT_SOURCE_DIR}/src/formation_guard.c
                      ${CMAKE_CURRENT_SOURCE_DIR}/src/status_certificate.c
                      ${CMAKE_CURRENT_SOURCE_DIR}/src/certified_api.c)

  find_package(Python3 COMPONENTS Interpreter)
  if(Python3_Interpreter_FOUND)
    # The batteries locate the shared objects through ABS_LIB_DIR and fall
    # back to the repository root, so build.sh keeps working unchanged.
    foreach(_battery
            test_certified_api
            test_status_profile_semantics
            test_verifier_adversarial
            test_meta_api_absent_solution_quality
            test_streaming_equivalence
            test_threshold_contract
            test_public_diagnostics
            test_stream_storage
            test_core_rank_boundary
            test_blockprefix_guard
            test_route_agreement
            test_dgesdd_compact_vt
            test_dgesdd_candidate_semantics)
      add_test(NAME ${_battery}
               COMMAND ${Python3_EXECUTABLE}
                       ${CMAKE_CURRENT_SOURCE_DIR}/tests/${_battery}.py)
      set_tests_properties(${_battery} PROPERTIES
        ENVIRONMENT "ABS_LIB_DIR=${CMAKE_BINARY_DIR}")
    endforeach()
  endif()
endif()

message(STATUS "")
message(STATUS "affine-bundle-solver ${PROJECT_VERSION}")
message(STATUS "  BLAS provider ....... ${ABS_BLAS_DESCRIPTION}")
message(STATUS "  Router arch flags ... ${ABS_ARCH_FLAGS}")
list(JOIN ABS_STRICT_FP_FLAGS " " _abs_strict_fp_display)
message(STATUS "  Strict kernels ...... ${_abs_strict_fp_display}")
if(ABS_SANITIZE)
  message(STATUS "  Instrumentation ..... ASan + UBSan")
elseif(ABS_COVERAGE)
  message(STATUS "  Instrumentation ..... coverage")
endif()
message(STATUS "  build.sh remains the canonical manuscript reproduction path.")
message(STATUS "")
