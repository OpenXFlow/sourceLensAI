# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Prompts related to generating source code index details using an LLM."""

from typing import Final


class SourceIndexPrompts:
    """Container for prompts related to LLM-based source code analysis for indexing."""

    _LANGUAGE_INSTRUCTIONS_MAP: Final[dict[str, str]] = {
        "python": (
            "For this Python file, identify the module-level docstring (first line), "
            "classes **defined directly within this file** (with their docstrings, decorators, attributes with types, "
            "and methods with full signatures including type hints and docstrings), and top-level functions "
            "**defined directly within this file** (with full signatures including type "
            "hints and docstrings). For attributes, provide type if inferable or 'Any'. "
            "Do NOT list classes or functions that are merely imported into this file from other modules. "
            "Your analysis should NOT recurse into imported modules."
        ),
        "java": (
            "For this Java file, identify the primary class/interface/enum Javadoc (first sentence), "
            "its name, fields (with types), and methods (with full signatures including parameter types, "
            "return type, and Javadoc first sentence), for all types **defined directly within this file**. "
            "Also list any top-level enums or interfaces **defined directly within this file**. "
            "Do NOT list types that are merely imported from other packages or files. "
            "Your analysis should NOT recurse into imported packages. "
            "Method signature should be like 'public String getName(String id)'."
        ),
        "javascript": (
            "For this JavaScript file, identify module-level comments/JSDoc (first line/summary), "
            "classes **defined directly within this file** (with constructor, methods, and JSDoc), "
            "top-level functions **defined directly within this file** (with JSDoc), "
            "and key object literals or exported constants **defined directly within this file**. "
            "Do NOT list classes or functions that are merely imported via `require` or `import` "
            "statements from other modules. Your analysis should NOT recurse into imported modules. "
            "For functions/methods, provide signature like "
            "'functionName(param1, param2)' or 'className.methodName(param1)'."
        ),
        "typescript": (
            "For this TypeScript file, identify module-level comments/JSDoc (first line/summary), "
            "classes and interfaces **defined directly within this file** (with properties, methods, "
            "and their JSDoc/TSDoc summaries), top-level functions **defined directly within this file**, "
            "enums, and type aliases **defined directly within this file**. Include full signatures with type "
            "annotations. Do NOT list types that are merely imported from other modules or libraries. "
            "Your analysis should NOT recurse into imported modules."
        ),
        "csharp": (
            "For this C# file, identify namespace, and list classes, structs, interfaces, enums "
            "**defined directly within this file** (with XML documentation summary comment if available). "
            "For classes/structs/interfaces, list fields (with types), "
            "properties (with types), and methods (with full signatures and summary comments). "
            "Do NOT list types that are merely imported using `using` directives from other namespaces "
            "or assemblies. Your analysis should NOT recurse into imported namespaces/assemblies. "
            "Signature example: 'public string GetName(int id)'."
        ),
        "cpp": (
            "For this C++ file, identify file-level comments (if any). "
            "List namespaces, and within them, classes, structs, enums, and global functions "
            "**defined directly within this file or its primary namespace**. "
            "For classes/structs, include public member variables (with types) and public member functions "
            "(with full signatures and brief comment/Doxygen summary). "
            "For global functions, include full signature and summary. "
            "Do NOT list elements that are merely included via `#include` directives from external libraries "
            "or standard library headers, focus on what is uniquely defined in this specific file. "
            "Your analysis should NOT recurse into `#include`d files. "
            "Signature example: 'std::string getName(int id)'."
        ),
        "c": (
            "For this C file, identify file-level comments (if any). "
            "List structs, enums, global variables (with types if obvious), and function definitions "
            "**defined directly within this file**. "
            "For structs, list members. For functions, include full signatures and a brief comment summary. "
            "Do NOT list elements that are merely included via `#include` directives from external libraries "
            "or standard library headers. Focus on definitions within this file. "
            "Your analysis should NOT recurse into `#include`d files. "
            "Signature example: 'int calculate_sum(int a, int b)'."
        ),
        "rust": (
            "For this Rust file, identify module-level documentation (e.g., `//!` or `///` for the module). "
            "List structs, enums, traits, functions (`fn`), and impl blocks with their methods "
            "**defined directly within this file/module**. "
            "Include documentation comments (`///`) for each item (first line/summary). "
            "Provide full function/method signatures including types. "
            "Do NOT list items that are merely imported via `use` statements from other crates or modules. "
            "Your analysis should NOT recurse into imported crates/modules."
        ),
        "php": (
            "For this PHP file, identify namespaces, and list classes, interfaces, traits "
            "**defined directly within this file** (with PHPDoc @summary if available). "
            "For classes/traits, list properties (with types if declared) and methods (with full signatures "
            "including type hints and PHPDoc @summary). Also list global functions "
            "**defined directly within this file**. "
            "Do NOT list items that are merely imported via `use` statements from other namespaces. "
            "Your analysis should NOT recurse into imported namespaces. "
            "Signature example: 'public function getName(int $id): string'."
        ),
        "swift": (
            "For this Swift file, identify module/file-level comments. "
            "List classes, structs, enums, protocols, and global functions "
            "**defined directly within this file**. "
            "For each, include documentation comments (first line/summary) and full signatures including types. "
            "For classes/structs/enums, list properties and methods. "
            "Do NOT list items that are merely imported from other modules or frameworks. "
            "Your analysis should NOT recurse into imported modules/frameworks."
        ),
        "go": (
            "For this Go file, identify package declaration and package-level documentation comment. "
            "List structs (with fields), interfaces (with method signatures), functions, and methods on types "
            "**defined directly within this file/package**. "
            "Include documentation comments (first line/summary) for each. Provide full function/method signatures. "
            "Do NOT list items from imported packages found in `import` statements. "
            "Your analysis should NOT recurse into imported packages."
        ),
        "ruby": (
            "For this Ruby file, identify file-level comments. "
            "List modules and classes **defined directly within this file**. "
            "For each, include documentation comments (e.g., RDoc, first line/summary). "
            "For classes/modules, list constants, class methods, and instance methods. "
            "Provide method signatures (e.g., 'def method_name(param1, param2)'). "
            "Do NOT list items from `require`d files unless they are re-opened and methods are added in this file. "
            "Your analysis should NOT recurse into `require`d files."
        ),
    }

    @staticmethod
    def _get_language_specific_instructions(project_language_lower: str) -> str:
        """Return language-specific instructions for the LLM prompt using a map.

        Args:
            project_language_lower: The lowercase string of the project language.

        Returns:
            A string containing specific instructions for the given language.
        """
        default_instruction_part1 = (
            f"For this {project_language_lower} file, identify any primary structural elements "
            "like classes, functions, modules, or main blocks **defined directly within this file**."
        )
        default_instruction_part2 = (
            "Extract a brief summary or the first line of any available documentation for these elements. "
            "Provide signatures where applicable. Do NOT list elements that are merely imported. "
            "Your analysis should NOT recurse into imported modules/files."
        )
        default_instruction = f"{default_instruction_part1}\n{default_instruction_part2}"
        return SourceIndexPrompts._LANGUAGE_INSTRUCTIONS_MAP.get(project_language_lower, default_instruction)

    @staticmethod
    def format_analyze_file_content_prompt(file_path: str, file_content: str, project_language: str) -> str:
        """Format prompt for LLM to analyze a single file's content for the source index.

        Args:
            file_path: The relative path of the file being analyzed.
            file_content: The full content of the file.
            project_language: The primary language of the project (e.g., "python", "java").
                              This helps tailor the expected output structure.

        Returns:
            A formatted string prompting the LLM for structured information about the file.
        """
        output_structure_example: Final[str] = (
            'docstring: "Module-level or file-level docstring summary (first line only)."\n'
            "classes: # (list, optional, ONLY for classes DEFINED IN THIS FILE)\n"
            '  - name: "ClassName"\n'
            '    docstring: "Class docstring summary (first line)."\n'
            '    decorators: ["@decorator1", "@decorator2"] # (list of strings, optional)\n'
            "    attributes: # (list, optional)\n"
            '      - name: "attribute_name"\n'
            '        type: "attribute_type_or_Any"\n'
            "    methods: # (list, optional)\n"
            '      - signature: "returnType methodName(paramType paramName)"\n'
            '        docstring: "Method docstring summary (first line)."\n'
            "functions: # (list, optional, ONLY for functions DEFINED IN THIS FILE)\n"
            '  - signature: "returnType functionName(paramType paramName)"\n'
            '    docstring: "Function docstring summary (first line)."\n'
            "interfaces: # (list, optional, ONLY for interfaces DEFINED IN THIS FILE) For Java, C#, TypeScript\n"
            '  - name: "InterfaceName"\n'
            '    docstring: "Interface docstring summary (first line)."\n'
            "    methods: # (list, optional)\n"
            '      - signature: "returnType methodName(paramType paramName)"\n'
            '        docstring: "Method signature docstring summary (first line)."\n'
            "structs: # (list, optional, ONLY for structs DEFINED IN THIS FILE) For C, C++, Go, Rust\n"
            '  - name: "StructName"\n'
            '    docstring: "Struct docstring summary (first line)."\n'
            "    fields: # (list, optional)\n"
            '      - name: "fieldName"\n'
            '        type: "fieldType"\n'
            "enums: # (list, optional, ONLY for enums DEFINED IN THIS FILE)\n"
            '  - name: "EnumName"\n'
            '    docstring: "Enum docstring summary (first line)."\n'
            '    values: ["VALUE1", "VALUE2"] # (list of strings, optional)'
        )

        lang_lower = project_language.lower()
        language_specific_instructions = SourceIndexPrompts._get_language_specific_instructions(lang_lower)

        header_part_line1 = (
            f"Analyze the content of the file `{file_path}` (language: {project_language}) "
            "to extract its structural information for a code inventory."
        )
        header_part_line2_instr1 = (
            "Provide the information as a **single YAML dictionary (object)**, strictly adhering to the keys and "
            "structure below."
        )
        header_part_line2_instr2 = (
            "The entire response should be one YAML object. "
            "Focus ONLY on elements (classes, functions, interfaces, etc.) "
            "**DEFINED DIRECTLY IN THIS FILE**."
        )
        header_part_line2_instr3 = (
            "Do NOT include elements that are merely imported or referenced from other files/libraries. "
            "For example, if a class `ImportedClass` is imported and used, do not include `ImportedClass` "
            "in the `classes` list for this file. Your analysis should NOT recurse into the definitions "
            "of imported modules or types. "
            "If a section (like 'classes' or 'functions') has no locally defined elements, "
            "you MAY OMIT the key or provide an empty list for it. Your response will be parsed programmatically."
        )
        header_part_line2 = f"{header_part_line2_instr1}\n{header_part_line2_instr2}\n{header_part_line2_instr3}"
        header_part = f"{header_part_line1}\n{language_specific_instructions}\n\n{header_part_line2}\n"

        formatting_rules_part1 = (
            "For all 'docstring' fields, provide only a concise first line or a very short summary "
            "(max 50 characters is ideal) OF THE ELEMENT DEFINED IN THIS FILE.\n"
            "For 'signature' fields, provide the full function or method signature as it appears or would "
            "idiomatically appear in the code, including parameters and return types if available in that language."
        )
        formatting_rules_part2_instr1 = (
            "For 'attributes' or 'fields', list class/struct/instance variables with their inferred or declared types."
        )
        formatting_rules_part2_instr2 = (
            "Ensure all string values in the YAML are properly quoted if they contain special characters "
            "(e.g., colons, hashes).\n\n"
            "Expected YAML structure (a single dictionary with the following keys, adapt based on language "
            "findings, omit optional keys if no data):\n"
        )
        formatting_rules_part2 = (
            f"{formatting_rules_part2_instr1}\n{formatting_rules_part2_instr2}"
            "```yaml\n"
            f"{output_structure_example}\n"
            "```\n\n"
        )
        file_content_part = f"File Content of `{file_path}`:\n```\n{file_content}\n```\n\n"
        footer_part_instr1 = (
            "Your response MUST be ONLY the single YAML dictionary block described above, starting with "
            "a key like `docstring:` or `classes:`."
        )
        footer_part_instr2 = (
            "Do not include any introductory text, explanations, or concluding remarks. "
            "**Crucially, only list classes, functions, interfaces, etc., that are DEFINED IN THIS "
            "SPECIFIC FILE, not imported ones. Do not analyze the content of imported modules.**"
        )
        footer_part = f"{footer_part_instr1}\n{footer_part_instr2}"

        return f"{header_part}{formatting_rules_part1}\n{formatting_rules_part2}{file_content_part}{footer_part}"


# End of src/sourcelens/prompts/source_index_prompts.py
