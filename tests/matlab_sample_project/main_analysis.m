% =========================================================================
% MAIN_ANALYSIS - Main script to run the signal processing workflow.
% =========================================================================
% This script orchestrates the entire process:
% 1. Sets up the environment.
% 2. Generates test data if it doesn't exist.
% 3. Runs the analysis using a functional approach.
% 4. Runs the analysis using an object-oriented (class-based) approach.
% =========================================================================

%% 1. Initialization
clear; clc; close all;

% Add paths to utility and plotting functions
addpath(genpath('utils'));
addpath(genpath('plotting'));
addpath(genpath('data'));

fprintf('SourceLens MATLAB Sample Project\n\n');

%% 2. Data Generation
data_dir = 'data';
data_file = fullfile(data_dir, 'test_signal.mat');

if ~exist(data_dir, 'dir')
   mkdir(data_dir);
end

if ~exist(data_file, 'file')
    generate_test_data(data_file);
end


%% 3. Functional Approach
fprintf('\n--- Running Functional Analysis ---\n');

% Load the data
signal_data = load_signal_data(data_file);

% Apply the filter
filter_window = 20;
filtered_functional = apply_filter(signal_data.noisy_signal, filter_window);

% Plot the results
plot_signals(signal_data.t, signal_data.noisy_signal, filtered_functional, 'Signal Processing (Functional Approach)');


%% 4. Object-Oriented Approach
% This demonstrates using a custom class (SignalProcessor) to manage the process.
fprintf('\n--- Running Object-Oriented Analysis ---\n');

% Create an instance of the processor class
processor = SignalProcessor(signal_data.t, signal_data.noisy_signal);

% Process the signal using the object's method
processor = processor.process(filter_window);

% Visualize the results using the object's method
processor.visualize();

fprintf('\nAnalysis complete.\n');

% end of file: main_analysis.m