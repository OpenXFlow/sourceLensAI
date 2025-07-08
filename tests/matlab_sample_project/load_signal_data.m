% load_signal_data.m
% Utility function to load signal data from a .mat file.

function data = load_signal_data(filename)
    % LOAD_SIGNAL_DATA - Loads data from a specified .mat file.
    %
    % Syntax: data = load_signal_data(filename)
    %
    % Inputs:
    %    filename - Path to the .mat file.
    %
    % Outputs:
    %    data     - A struct containing the loaded variables.

    if exist(filename, 'file')
        fprintf('Loading signal data from %s...\n', filename);
        data = load(filename);
    else
        error('Data file not found: %s', filename);
    end
end

% end of file: load_signal_data.m