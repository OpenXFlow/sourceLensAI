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

package com.sampleproject;

/**
 * Configuration settings for the Sample Project.
 * This class stores configuration values used by other parts of the application,
 * such as file paths or processing parameters.
 */
public final class Config { // Made final as it's a utility class with static members

    // --- Constants for Configuration ---

    /**
     * Path to a data file (used by DataHandler).
     */
    public static final String DATA_FILE_PATH = "data/items.json";

    /**
     * A processing parameter (used by ItemProcessor).
     */
    public static final int PROCESSING_THRESHOLD = 100;

    /**
     * Example setting for logging level (could be used by main).
     */
    public static final String LOG_LEVEL = "INFO";

    /**
     * Private constructor to prevent instantiation of this utility class.
     */
    private Config() {
        // This class is not meant to be instantiated.
        throw new UnsupportedOperationException("This is a utility class and cannot be instantiated");
    }

    /**
     * Returns the configured path for the data file.
     *
     * @return The path string for the data file.
     */
    public static String getDataPath() {
        // In a real app, this might involve more complex logic,
        // like checking environment variables first.
        System.out.printf("Config: Providing data file path: %s%n", DATA_FILE_PATH);
        return DATA_FILE_PATH;
    }

    /**
     * Returns the configured processing threshold.
     *
     * @return The integer threshold value.
     */
    public static int getThreshold() {
        System.out.printf("Config: Providing processing threshold: %d%n", PROCESSING_THRESHOLD);
        return PROCESSING_THRESHOLD;
    }
}
// End of com/sampleproject/Config.java