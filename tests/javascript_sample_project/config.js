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
 * This module stores configuration values used by other parts of the application.
 * @module config
 */

// --- Constants for Configuration ---

/**
 * Path to a data file (used by DataHandler).
 * @type {string}
 * @const
 */
export const DATA_FILE_PATH = "data/items.json";

/**
 * A processing parameter (used by ItemProcessor).
 * @type {number}
 * @const
 */
export const PROCESSING_THRESHOLD = 100;

/**
 * Example setting for logging level (could be used by main).
 * @type {string}
 * @const
 */
export const LOG_LEVEL = "INFO"; // In JS, this might map to console methods e.g. info, warn, error

/**
 * Returns the configured path for the data file.
 * @returns {string} The path string for the data file.
 */
export function getDataPath() {
    // In a real app, this might involve more complex logic,
    // like checking environment variables first.
    console.log(`Config: Providing data file path: ${DATA_FILE_PATH}`);
    return DATA_FILE_PATH;
}

/**
 * Returns the configured processing threshold.
 * @returns {number} The integer threshold value.
 */
export function getThreshold() {
    console.log(`Config: Providing processing threshold: ${PROCESSING_THRESHOLD}`);
    return PROCESSING_THRESHOLD;
}

// End of javascript_sample_project/config.js