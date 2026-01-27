cmake_minimum_required(VERSION 3.14)
project(geminisdk VERSION 0.1.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Options
option(GEMINISDK_BUILD_EXAMPLES "Build examples" ON)
option(GEMINISDK_BUILD_TESTS "Build tests" OFF)

# Find dependencies
find_package(CURL REQUIRED)
find_package(nlohmann_json 3.9 QUIET)
if(NOT nlohmann_json_FOUND)
    include(FetchContent)
    FetchContent_Declare(json
        GIT_REPOSITORY https://github.com/nlohmann/json.git
        GIT_TAG v3.11.3
    )
    FetchContent_MakeAvailable(json)
endif()

# Library sources
set(GEMINISDK_SOURCES
    src/types.cpp
    src/errors.cpp
    src/auth.cpp
    src/backend.cpp
    src/session.cpp
    src/client.cpp
    src/tools.cpp
)

set(GEMINISDK_HEADERS
    include/geminisdk/geminisdk.hpp
    include/geminisdk/types.hpp
    include/geminisdk/errors.hpp
    include/geminisdk/auth.hpp
    include/geminisdk/backend.hpp
    include/geminisdk/session.hpp
    include/geminisdk/client.hpp
    include/geminisdk/tools.hpp
)

# Create library
add_library(geminisdk ${GEMINISDK_SOURCES})
add_library(geminisdk::geminisdk ALIAS geminisdk)

target_include_directories(geminisdk
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(geminisdk
    PUBLIC
        nlohmann_json::nlohmann_json
    PRIVATE
        CURL::libcurl
)

# Examples
if(GEMINISDK_BUILD_EXAMPLES)
    add_executable(basic_usage examples/basic_usage.cpp)
    target_link_libraries(basic_usage PRIVATE geminisdk)
    
    add_executable(streaming examples/streaming.cpp)
    target_link_libraries(streaming PRIVATE geminisdk)
    
    add_executable(tool_calling examples/tool_calling.cpp)
    target_link_libraries(tool_calling PRIVATE geminisdk)
endif()

# Install
include(GNUInstallDirs)
install(TARGETS geminisdk
    EXPORT geminisdkTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/geminisdk
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT geminisdkTargets
    FILE geminisdkTargets.cmake
    NAMESPACE geminisdk::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/geminisdk
)
