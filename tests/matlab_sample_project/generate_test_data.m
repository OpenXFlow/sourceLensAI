% generate_test_data.m
% This script creates a sample signal dataset and saves it to a .mat file.

function generate_test_data(filename)
    % GENERATE_TEST_DATA - Creates and saves a test signal.
    %
    % Syntax: generate_test_data(filename)
    %
    % Inputs:
    %    filename - Name of the .mat file to save (e.g., 'test_signal.mat').

    fprintf('Generating test data...\n');
    
    % Time vector
    fs = 1000; % Sampling frequency
    t = 0:1/fs:2; % Time vector from 0 to 2 seconds

    % Create a clean sine wave
    f1 = 10; % Frequency of the sine wave
    clean_signal = sin(2*pi*f1*t);

    % Add some random noise
    noise_amplitude = 0.5;
    noise = noise_amplitude * randn(size(t));
    noisy_signal = clean_signal + noise;

    % Save data to a .mat file
    save(filename, 't', 'clean_signal', 'noisy_signal');

    fprintf('Test data saved to %s\n', filename);
end

% end of file: generate_test_data.m