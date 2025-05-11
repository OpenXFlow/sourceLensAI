// c_sample_project/include/item_processor.h

#ifndef ITEM_PROCESSOR_H
#define ITEM_PROCESSOR_H

#include <stdbool.h> // For bool
#include "item.h"    // Definition of the Item struct

/**
 * @struct ItemProcessor
 * @brief Processes individual Item objects based on configured rules.
 *
 * Contains the logic for processing Item objects. This structure holds
 * the processing threshold.
 */
typedef struct {
    int threshold; /**< The numerical threshold used in the processing logic. */
    // In a real application, a logger instance or similar might be part of the state.
} ItemProcessor;

/**
 * @brief Creates and initializes a new ItemProcessor.
 *
 * Dynamically allocates memory for the ItemProcessor structure.
 * The caller is responsible for freeing the returned ItemProcessor using
 * item_processor_destroy().
 *
 * @param threshold The numerical threshold to be used in processing logic.
 * @return ItemProcessor* Pointer to the newly created ItemProcessor, or NULL on allocation failure.
 */
ItemProcessor* item_processor_create(int threshold);

/**
 * @brief Destroys an ItemProcessor object and frees its associated memory.
 *
 * Frees the memory allocated for the ItemProcessor structure itself.
 * Sets the pointer to NULL after freeing.
 *
 * @param processor_ptr Pointer to the pointer of the ItemProcessor to be destroyed.
 *                      The pointer will be set to NULL.
 */
void item_processor_destroy(ItemProcessor** processor_ptr);

/**
 * @brief Process a single item.
 *
 * Marks the item as processed and applies logic based on the threshold.
 * In this example, it logs whether the item's value exceeds the threshold.
 *
 * @param processor Pointer to the ItemProcessor instance containing the threshold.
 * @param item Pointer to the Item object to process. The item will be modified.
 * @return bool True if processing was successful (always true in this simulation),
 *              False if an error occurred (e.g., NULL item or processor).
 */
bool item_processor_processItem(ItemProcessor* processor, Item* item);

#endif // ITEM_PROCESSOR_H
// End of c_sample_project/include/item_processor.h