# Structural check of the floating-point contract.
#
# The mxcsr probe checks empirically that loading the fast library does not
# change the process FP mode on this toolchain.  This checks the property the
# contract is actually stated in: that no fast-math flag ever reached the link
# line, regardless of whether the current compiler would have acted on it.
# A toolchain that starts adding the FTZ/DAZ constructor tomorrow is then
# caught by construction rather than by observation.

if(NOT DEFINED LINK_RULE)
  message(FATAL_ERROR "check_link_contract.cmake: LINK_RULE not set")
endif()
if(NOT EXISTS "${LINK_RULE}")
  message(FATAL_ERROR "check_link_contract.cmake: no link rule at ${LINK_RULE}")
endif()

file(READ "${LINK_RULE}" _rule)
if(_rule MATCHES "-ffast-math|-funsafe-math-optimizations|-ffinite-math-only|-Ofast")
  message(FATAL_ERROR
    "A fast-math flag is present on the router link line.\n"
    "${LINK_RULE}:\n${_rule}\n"
    "Under clang this pulls in a startup object that sets MXCSR FTZ and DAZ "
    "for the whole process, which would silently flush the subnormal inputs "
    "the certificate battery exists to exercise.")
endif()
message(STATUS "link contract: no fast-math flag on the router link line")
