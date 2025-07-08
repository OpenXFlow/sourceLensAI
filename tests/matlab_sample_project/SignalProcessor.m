% SignalProcessor.m
% An example of a class definition (classdef) for object-oriented approach.

classdef SignalProcessor
    %SIGNALPROCESSOR A class to encapsulate signal processing operations.

    properties
        OriginalSignal
        FilteredSignal
        TimeVector
    end

    methods
        function obj = SignalProcessor(time, signal)
            %SIGNALPROCESSOR Construct an instance of this class
            %   Initializes the object with the time vector and original signal.
            if nargin > 0
                obj.TimeVector = time;
                obj.OriginalSignal = signal;
            end
        end

        function obj = process(obj, windowSize)
            %PROCESS Applies a filter to the signal stored in the object.
            fprintf('\n--- Processing via SignalProcessor object ---\n');
            obj.FilteredSignal = apply_filter(obj.OriginalSignal, windowSize);
        end

        function visualize(obj)
            %VISUALIZE Plots the signals stored in the object.
            if isempty(obj.FilteredSignal)
                error('Signal has not been processed yet. Call the process() method first.');
            end
            plot_signals(obj.TimeVector, obj.OriginalSignal, obj.FilteredSignal, 'Signal Processing (Object-Oriented)');
        end
    end
end

% end of file: SignalProcessor.m