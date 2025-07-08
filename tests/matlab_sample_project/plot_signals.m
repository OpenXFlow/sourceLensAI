% plot_signals.m
% A dedicated function for visualizing signals.

function plot_signals(t, original_signal, filtered_signal, plot_title)
    % PLOT_SIGNALS - Creates a plot of the original and filtered signals.
    %
    % Syntax: plot_signals(t, original_signal, filtered_signal, plot_title)
    %
    % Inputs:
    %    t               - Time vector.
    %    original_signal - The original, noisy signal.
    %    filtered_signal - The signal after filtering.
    %    plot_title      - The title for the plot.

    figure; % Create a new figure window
    hold on;
    plot(t, original_signal, 'b', 'DisplayName', 'Original Signal');
    plot(t, filtered_signal, 'r', 'LineWidth', 2, 'DisplayName', 'Filtered Signal');
    hold off;
    
    title(plot_title);
    xlabel('Time (s)');
    ylabel('Amplitude');
    legend show;
    grid on;
    
    fprintf('Signal plot generated: "%s"\n', plot_title);
end

% end of file: plot_signals.m