import tkinter as tk
from tkinter import messagebox
import hashlib
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from pathlib import Path
import json
import os
import speech_recognition as sr

def show_fingerprint_prompt(root):
    confirmed = []
    def accept():
        confirmed.append(True)
        top.destroy()
    top = tk.Toplevel(root)
    top.title("Fingerprint Required")
    tk.Label(top, text="🔒 Please scan your fingerprint to proceed with this task.", font=("Segoe UI", 11)).pack(pady=10)
    tk.Button(top, text="Simulate Fingerprint", command=accept).pack(pady=10)
    top.transient(root)
    top.grab_set()
    root.wait_window(top)
    if confirmed:
        return True
    return bool(confirmed)

def confirm_by_voice(chat_area, expected_phrase="yes allow this"):
    try:
        recognizer = sr.Recognizer()
    except Exception as e:
        return False
    mic = sr.Microphone()
    try:
        with mic as source:
            chat_area.insert(tk.END, "[Voice Auth] Listening for confirmation...\n")
            chat_area.see(tk.END)
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source, timeout=2, phrase_time_limit=3)
        spoken = recognizer.recognize_google(audio, language="en-US").lower()
        return expected_phrase in spoken
    except Exception as e:
        chat_area.insert(tk.END, f"[Voice Error] {str(e)}\n")
        return False

def prompt_for_pin(root, pin_hash):
    confirmed = []
    def submit_pin():
        entered = pin_entry.get()
        hashed = hashlib.sha256(entered.encode('utf-8')).hexdigest()
        if hashed == pin_hash:
            confirmed.append(True)
            top.destroy()
        else:
            messagebox.showerror("Access Denied", "Incorrect PIN.")
            top.lift()
            pin_entry.delete(0, tk.END)

    top = tk.Toplevel(root)
    top.title("PIN Required")
    tk.Label(top, text="🔑 Enter your admin PIN to continue:", font=("Segoe UI", 11)).pack(pady=10)
    pin_entry = tk.Entry(top, show="*", width=20)
    pin_entry.pack(pady=5)
    pin_entry.focus()
    tk.Button(top, text="Submit", command=submit_pin).pack(pady=5)
    top.transient(root)
    top.grab_set()
    root.wait_window(top)
    return bool(confirmed)