// Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

/**
 * @file Configuration settings for the Sample Project.
 * This module stores configuration values used by other parts of the application,
 * such as file paths or processing parameters.
 * @module config
 */

// --- Constants for Configuration ---

/**
 * Path to a data file (used by DataHandler).
 */
export const DATA_FILE_PATH: string = "data/items.json";

/**
 * A processing parameter (used by ItemProcessor).
 */
export const PROCESSING_THRESHOLD: number = 100;

/**
 * Example setting for logging level (could be used by main).
 * Consider using a more specific enum or union type in a real application.
 */
export const LOG_LEVEL: string = "INFO";

/**
 * Returns the configured path for the data file.
 * @returns {string} The path string for the data file.
 */
export function getDataPath(): string {
    // In a real app, this might involve more complex logic,
    // like checking environment variables first.
    console.log(`Config: Providing data file path: ${DATA_FILE_PATH}`);
    return DATA_FILE_PATH;
}

/**
 * Returns the configured processing threshold.
 * @returns {number} The integer threshold value.
 */
export function getThreshold(): number {
    console.log(`Config: Providing processing threshold: ${PROCESSING_THRESHOLD}`);
    return PROCESSING_THRESHOLD;
}

// End of typescript_sample_project/config.ts