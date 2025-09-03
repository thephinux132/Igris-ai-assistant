"""
Widget Manager for Igris OS Desktop Environment (Phase 5)
- Manages the lifecycle and placement of widgets on the desktop.
"""
import tkinter as tk

class WidgetManager:

    """Manages widgets within the Igris Shell."""
    def __init__(self, shell_root):
        self.shell = shell_root
        self.widgets = {}  # Maps widget_name to widget instance
        self._widget_count = 0

    def create_widget(self, widget_class, *args, **kwargs):
        """Creates and manages a new widget."""
        widget_name = kwargs.pop("name", f"Widget {self._widget_count}")
        self._widget_count += 1

        if widget_name in self.widgets:
            print(f"[WidgetManager] Widget '{widget_name}' already exists.")
            return None

        try:
            widget = widget_class(self.shell, *args, **kwargs)
            self.widgets[widget_name] = widget
            print(f"[WidgetManager] Created widget '{widget_name}'.")
            return widget
        except Exception as e:
            print(f"[WidgetManager] Failed to create widget '{widget_name}': {e}")
            return None

    def destroy_widget(self, widget_name):
        """Finds a managed widget by name and destroys it."""
        widget = self.widgets.pop(widget_name, None)
        if widget:
            print(f"[WidgetManager] Destroying widget '{widget_name}'.")
            widget.destroy()
        else:
            print(f"[WidgetManager] No widget found for '{widget_name}' to destroy.")

    def list_widgets(self):
        """Returns a list of currently managed widget names."""
        return list(self.widgets.keys())

    def get_widget(self, widget_name):
        """Returns the widget instance for the given name, or None if not found."""
        return self.widgets.get(widget_name)

    def place_widget(self, widget_name, x=0, y=0, anchor=tk.NW):
        """Places the widget at the specified coordinates."""
        widget = self.get_widget(widget_name)
        if widget:
            widget.place(x=x, y=y, anchor=anchor)
            print(f"[WidgetManager] Placed widget '{widget_name}' at x={x}, y={y}.")
        else:
            print(f"[WidgetManager] Widget '{widget_name}' not found. Cannot place.")

if __name__ == '__main__':
    # Basic test
    root = tk.Tk()
    wm = WidgetManager(root)
    label = wm.create_widget(tk.Label, text="Test Widget")
    if label:
        wm.place_widget("Test Widget", x=50, y=50)