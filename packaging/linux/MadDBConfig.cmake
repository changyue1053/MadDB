# Installed Linux x86_64 C ABI target. Resolve only relative to this config.
if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|amd64)$")
  message(FATAL_ERROR "This MadDB package requires Linux x86_64")
endif()
if(TARGET MadDB::MadDB)
  return()
endif()
get_filename_component(_maddb_prefix "${CMAKE_CURRENT_LIST_DIR}/../../.." REALPATH)
foreach(_maddb_file IN ITEMS lib/libmaddb.so include/maddb.h)
  if(NOT EXISTS "${_maddb_prefix}/${_maddb_file}")
    message(FATAL_ERROR "Incomplete MadDB installation")
  endif()
endforeach()
add_library(MadDB::MadDB SHARED IMPORTED)
set_target_properties(MadDB::MadDB PROPERTIES
  IMPORTED_LOCATION "${_maddb_prefix}/lib/libmaddb.so"
  IMPORTED_NO_SONAME TRUE
  INTERFACE_INCLUDE_DIRECTORIES "${_maddb_prefix}/include")
unset(_maddb_prefix)
unset(_maddb_file)
