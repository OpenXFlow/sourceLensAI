# cpp_sample_project/CMakeLists.txt

cmake_minimum_required(VERSION 3.10)

# Project Name and Version (optional)
project(CppSampleProject VERSION 1.0 LANGUAGES CXX)

# Set C++ standard to C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_EXTENSIONS OFF) # Avoid compiler-specific extensions

# Add an executable target
# SRCS lists all .cpp files that need to be compiled and linked.
# For this project, it's primarily main.cpp and any .cpp files for our classes.
# If class methods were defined in .cpp files, they would be listed here.
# Since all our class methods are currently inline in .h files,
# only main.cpp is strictly needed here for linking an executable.
# However, it's good practice to list .cpp files if they exist.
add_executable(CppSampleProject
    src/main.cpp
    # src/Config.cpp # Add if Config.cpp is created
    # src/DataHandler.cpp # Add if DataHandler.cpp is created
    # src/ItemProcessor.cpp # Add if ItemProcessor.cpp is created
    # Item.cpp is not needed as Item methods are inline in Item.h
)

# Specify include directories
# This tells CMake where to find header files (.h)
target_include_directories(CppSampleProject PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
)

# Optional: Add compiler flags (e.g., for warnings or optimization)
# target_compile_options(CppSampleProject PRIVATE -Wall -Wextra -pedantic) # Example for GCC/Clang
# target_compile_options(CppSampleProject PRIVATE /W4) # Example for MSVC

# Optional: Link to external libraries if needed in the future
# target_link_libraries(CppSampleProject PRIVATE some_library)

# A simple message to confirm configuration
message(STATUS "Configuring CppSampleProject")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Source directory: ${CMAKE_CURRENT_SOURCE_DIR}")
message(STATUS "Build directory: ${CMAKE_CURRENT_BINARY_DIR}")

# End of cpp_sample_project/CMakeLists.txt