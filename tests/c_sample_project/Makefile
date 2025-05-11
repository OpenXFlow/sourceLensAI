# c_sample_project/Makefile

# Compiler and flags
CC = gcc
CFLAGS = -std=c99 -Wall -Wextra -pedantic -g
IFLAGS = -Iinclude

# Directories
SRC_DIR = src
INCLUDE_DIR = include
OBJ_DIR = obj
BIN_DIR = . # Output executable in the current directory (project root)

# Source files and object files
# Automatically find all .c files in SRC_DIR
SRCS = $(wildcard $(SRC_DIR)/*.c)
# Replace .c with .o and put them in OBJ_DIR
OBJS = $(patsubst $(SRC_DIR)/%.c,$(OBJ_DIR)/%.o,$(SRCS))

# Executable name
TARGET = $(BIN_DIR)/c_sample_project

# Default target
all: $(TARGET)

# Linking the executable
$(TARGET): $(OBJS)
	@mkdir -p $(BIN_DIR)
	$(CC) $(CFLAGS) $^ -o $@
	@echo "Linked executable: $@"

# Compiling source files to object files
# $< is the first prerequisite (the .c file)
# $@ is the target name (the .o file)
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c | $(OBJ_DIR)
	$(CC) $(CFLAGS) $(IFLAGS) -c $< -o $@
	@echo "Compiled: $< -> $@"

# Create object directory if it doesn't exist
# This is an order-only prerequisite for the .o rule
$(OBJ_DIR):
	@mkdir -p $(OBJ_DIR)

# Clean target
clean:
	@echo "Cleaning project..."
	-@rm -f $(OBJ_DIR)/*.o
	-@rm -f $(TARGET)
	-@rmdir $(OBJ_DIR) 2>/dev/null || true # Remove obj dir if empty, ignore error if not

# Phony targets (targets that are not files)
.PHONY: all clean

# End of c_sample_project/Makefile