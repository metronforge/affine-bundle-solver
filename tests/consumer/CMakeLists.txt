# A project that has never seen the solver's sources.  It exists to check that
# an installed tree is actually usable: find_package resolves, the public
# headers are where the config says they are, and the shared objects can find
# each other at run time.
cmake_minimum_required(VERSION 3.16)
project(consumer LANGUAGES C)

find_package(affine-bundle-solver 0.4.3 REQUIRED) # x-release-please-version

add_executable(consumer main.c)
target_link_libraries(consumer PRIVATE
  affine-bundle-solver::affine_bundle_solver m)
