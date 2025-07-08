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