> Previously, we looked at [Object-Oriented Programming Approach](05_object-oriented-programming-approach.md).

# Chapter 6: Signal Filtering
Let's begin exploring this concept. In this chapter, we will delve into the world of signal filtering, a fundamental technique used to clean up noisy data and extract meaningful information.
**Why Signal Filtering?**
Imagine you're trying to listen to your favorite song on the radio, but there's a lot of static and interference. Signal filtering is like tuning the radio to reduce that static and make the song clearer. In technical terms, "noise" refers to unwanted variations in a signal that obscure the underlying information. These variations could be due to various sources like sensor imperfections, environmental disturbances, or electronic components. We can use filtering techniques to reduce the amplitude of unwanted frequencies.
In many real-world scenarios, the data we collect is often contaminated with noise. For example, if we are measuring temperature using a sensor, the readings might fluctuate due to electrical interference or slight variations in the environment. Signal filtering helps us smooth out these fluctuations, providing a more accurate and reliable representation of the true temperature.
**The Core Concept: Smoothing Signals**
At its heart, signal filtering involves modifying a signal to emphasize certain characteristics while suppressing others. In this project, `20250707_1507_code-matlab-sample-project`, we focus on a particular type of filtering called *smoothing*. Smoothing aims to reduce high-frequency noise, making the underlying signal more apparent.
**How it Works: Moving Average Filter**
The specific filtering method we'll use is the *moving average filter*. This method is a simple yet effective way to smooth a signal. Here's how it works:
1.  **Define a Window:** Choose a window size, which determines how many neighboring data points to consider when calculating the average. A larger window size results in more smoothing.
2.  **Calculate the Average:** For each data point in the signal, calculate the average of the data points within the defined window centered around that point.
3.  **Replace the Original Value:** Replace the original data point with the calculated average.
For example, if we have a signal `[1, 2, 3, 4, 5]` and a window size of 3, the moving average filter would work as follows:
*   For the second data point (2), we average `[1, 2, 3]` to get `(1+2+3)/3 = 2`.
*   For the third data point (3), we average `[2, 3, 4]` to get `(2+3+4)/3 = 3`.
This process is repeated for all data points in the signal (with appropriate handling of boundary conditions at the start and end of the signal).
**Usage in `20250707_1507_code-matlab-sample-project`**
The project uses the `apply_filter.m` function to implement the moving average filter. This function takes the signal and window size as input and returns the filtered signal.
```matlab
--- File: apply_filter.m ---
% apply_filter.m
% Core computational function to apply a simple moving average filter.
function filtered_signal = apply_filter(signal, window_size)
    % APPLY_FILTER - Applies a moving average filter to a signal.
    % This acts as a simple low-pass filter to reduce noise.
    %
    % Syntax: filtered_signal = apply_filter(signal, window_size)
    %
    % Inputs:
    %    signal      - The input signal vector.
    %    window_size - The size of the moving average window.
    %
    % Outputs:
    %    filtered_signal - The signal after applying the filter.
    if nargin < 2
        window_size = 10; % Default window size
    end
    fprintf('Applying a moving average filter with window size %d...\n', window_size);
    % Use MATLAB's built-in movmean function
    filtered_signal = movmean(signal, window_size);
end
% end of file: apply_filter.m
```
As you can see in the code, the `apply_filter` function leverages MATLAB's built-in `movmean` function, which efficiently calculates the moving average. If no `window_size` is specified, the function defaults to a window size of 10. The function prints a message indicating the window size used.
**Example of Use in `main_analysis.m`:**
```matlab
% Apply the filter
filter_window = 20;
filtered_functional = apply_filter(signal_data.noisy_signal, filter_window);
```
Here, the `apply_filter` function is called with the noisy signal and a window size of 20. The result, `filtered_functional`, is the smoothed signal.
**Impact of Window Size**
The choice of window size is crucial. A small window size will result in less smoothing, preserving more of the original signal's details but also retaining more noise. A large window size will result in more smoothing, effectively removing noise but potentially blurring out important features of the signal. The optimal window size depends on the specific characteristics of the signal and the nature of the noise.
**Relationship to Other Chapters**
This chapter builds upon the data loading process described in [Data Loading](01_data-loading.md), where we learned how to load the noisy signal. It sets the stage for [Moving Average Filter](03_moving-average-filter.md) to describe how this filter type works. We will also visualize the results of filtering in [Signal Visualization](04_signal-visualization.md), compare functional and object-oriented approaches in [Functional Programming Approach](05_functional-programming-approach.md) and [Object-Oriented Programming Approach](06_object-oriented-programming-approach.md), and use `SignalProcessor` class in [SignalProcessor Class](07_signalprocessor-class.md) and `main_analysis` workflow in [Main Analysis Workflow](08_main-analysis-workflow.md).
This concludes our look at this topic.

> Next, we will examine [Signal Visualization](07_signal-visualization.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*