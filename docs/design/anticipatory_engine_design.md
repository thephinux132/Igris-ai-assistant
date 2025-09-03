# Igris Anticipatory Task Execution Engine - Design Document

## 1. Objective

The primary goal of this engine is to proactively assist the user by learning their routines and predicting their next actions. It will analyze the plugin execution history stored in `user_profile.json` to identify common patterns and sequences of commands. Based on these patterns, it will offer non-intrusive, actionable suggestions directly within the Igris GUI.

For example, if the user frequently runs `run_security_audit` and immediately follows it with `encrypt_audit_output`, the engine should learn this pattern. The next time the user runs the security audit, the engine should suggest encrypting the report.

## 2. Core Components

1.  **Plugin Execution Logger (`plugin_execution_logger.py`)**:
    -   **Role**: The data source.
    -   **Function**: Already implemented. It records every plugin execution, including the plugin name and a precise timestamp, into `user_profile.json`. This history is the foundation for all pattern analysis.

2.  **Pattern Analyzer (`pattern_analyzer.py`)**:
    -   **Role**: The "brains" of the operation.
    -   **Function**: A new module/plugin responsible for reading `user_profile.json`. It will analyze the `plugin_history` to find statistically significant sequences of actions. Initially, it will focus on identifying pairs of plugins that are frequently executed within a short time window (e.g., 2 minutes) of each other.

3.  **Suggestion Engine (`suggestion_engine.py`)**:
    -   **Role**: The decision-maker.
    -   **Function**: A new module that is triggered after a plugin successfully executes. It will take the just-run plugin as input, query the `Pattern Analyzer` to see if it's part of a known pattern, and if so, formulate a user-facing suggestion.

4.  **GUI Integration (in `igris_control_gui_main_final_fixed.py`)**:
    -   **Role**: The user interface for suggestions.
    -   **Function**: The main GUI will be modified to include a new, dedicated area for suggestions (e.g., a subtle banner or status bar update). This area will display suggestions from the `Suggestion Engine` and provide a simple way for the user to accept (execute) or dismiss them.

## 3. Data Flow

1.  User executes a plugin (e.g., `run_security_audit`).
2.  The `plugin_execution_logger` updates `user_profile.json` with the execution details.
3.  The main GUI's command handling logic, after the plugin finishes, calls the `Suggestion Engine`.
4.  The `Suggestion Engine` calls the `Pattern Analyzer`, passing the name of the plugin that was just run.
5.  The `Pattern Analyzer` scans the `plugin_history` in `user_profile.json`, identifies that `encrypt_audit_output` often follows `run_security_audit`, and returns this pattern.
6.  The `Suggestion Engine` receives the pattern and formulates a suggestion string: "You often run 'encrypt audit output' after this. Run it now?"
7.  The `Suggestion Engine` returns this string to the GUI.
8.  The GUI displays the suggestion in the designated UI element.

## 4. Implementation Plan (Initial Steps)

1.  **Create `pattern_analyzer.py`**: Build the initial version of the pattern analyzer. Its `run()` function will simply read the profile and print the most common two-plugin sequences it finds. This allows for isolated testing of the core analysis logic.
2.  **Create `suggestion_engine.py`**: Develop the suggestion engine module. It will contain a function like `get_suggestion(last_plugin_run)` that encapsulates the logic of calling the analyzer and formatting the output.
3.  **Integrate with GUI**: Modify the `send_request` function in the main GUI. After a plugin action is executed, it will call the `suggestion_engine` and display the returned suggestion in a new `tk.Label`.

## 5. Future Enhancements

-   **Pattern Complexity**: Evolve the analyzer to detect longer sequences (3+ plugins) and consider other factors like time-of-day or specific command parameters.
-   **User Feedback**: Add "thumbs up/down" buttons to suggestions, allowing the engine to learn which suggestions are helpful and which are not, refining its accuracy over time.
-   **Macro Creation**: Allow the user to "save" a suggested sequence as a new, single-command alias/macro, further streamlining their workflow.

---