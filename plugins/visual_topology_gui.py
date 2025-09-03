"""
Visual Topology GUI

Displays a simulated network topology using Tkinter Canvas.
"""
import tkinter as tk
import random

def run():
    root = tk.Toplevel()
    root.title("Network Topology Map")
    canvas = tk.Canvas(root, width=600, height=400, bg="white")
    canvas.pack()

    nodes = [f"Device {i+1}" for i in range(6)]
    positions = [(random.randint(100, 500), random.randint(50, 350)) for _ in nodes]

    for idx, (x, y) in enumerate(positions):
        canvas.create_oval(x-20, y-20, x+20, y+20, fill="skyblue")
        canvas.create_text(x, y, text=nodes[idx])

    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            if random.random() < 0.4:
                x1, y1 = positions[i]
                x2, y2 = positions[j]
                canvas.create_line(x1, y1, x2, y2)

    root.mainloop()
    return "Topology map displayed."
