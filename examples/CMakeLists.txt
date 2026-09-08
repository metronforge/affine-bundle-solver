# Examples are built as ordinary consumers of the installed interface: they
# see include/ through the targets' PUBLIC include directories and nothing
# from src/.  If an example needs a private header, the API is wrong.

add_executable(example_classify classify.c)
target_link_libraries(example_classify PRIVATE affine_bundle_solver m)

add_executable(example_certify certify.c)
target_link_libraries(example_certify PRIVATE certified_solver affine_bundle_solver m)

add_executable(example_streaming streaming.c)
target_link_libraries(example_streaming PRIVATE affine_bundle_solver m)

if(ABS_BUILD_TESTING)
  add_test(NAME example_classify COMMAND example_classify)
  add_test(NAME example_certify  COMMAND example_certify)
  add_test(NAME example_streaming COMMAND example_streaming)
endif()
