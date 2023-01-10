"""Automation window"""

from __future__ import annotations
from threading import Thread
from typing import TYPE_CHECKING
import customtkinter

from ..autohost.autohost import Autohost

if TYPE_CHECKING:
    from .application import Application

class AutoHostWindow(customtkinter.CTkToplevel):
    """Auto Raid Host Window"""
    def __init__(
        self,
        *args,
        settings: dict = None,
        master: Application = None,
        fg_color="default_theme",
        **kwargs
    ):
        self.settings: dict = settings or {}
        super().__init__(*args, master = master, fg_color=fg_color, **kwargs)
        self.master: Application

        self.title("Auto Raid Host")
        self.handle_close_events()
        self.draw_start_button_frame()
        self.autohost = Autohost(master=self.master)

    def start_autohost(self):
        self.stop_button.configure(state="normal")
        self.start_button.configure(text="Pause Autohost",command=self.pause_autohost)
        self.autohost.start_automation()

    def stop_autohost(self):
        self.stop_button.configure(state="disabled")
        self.start_button.configure(text="Start Autohost",command=self.start_autohost)
        self.autohost.stop_automation()
        self.master.reader.close() # Figure out how to properly kill autohost

    def pause_autohost(self):
        self.start_button.configure(text="Resume Autohost",command=self.resume_autohost)

    def resume_autohost(self):
        self.start_button.configure(text="Pause Autohost",command=self.pause_autohost)

    def draw_start_button_frame(self):
        """Draw start button frame"""
        self.start_button_frame = customtkinter.CTkFrame(master = self, width = 850)
        self.start_button_frame.grid(row = 1, column = 0, columnspan = 4, sticky = "nwse")
        self.start_button = customtkinter.CTkButton(
            master = self.start_button_frame,
            text = "Start Autohost",
            width = 850,
            command = self.start_autohost
        )
        self.start_button.grid(
            row = 0,
            column = 0,
            columnspan = 4,
            sticky = "nwse",
            padx = 5,
            pady = 5
        )
        self.stop_button = customtkinter.CTkButton(
            master = self.start_button_frame,
            text = "Stop Autohost",
            width = 850,
            command = self.stop_autohost,
            state = "disabled"
        )
        self.stop_button.grid(
            row = 1,
            column = 0,
            columnspan = 4,
            sticky = "nwse",
            padx = 5,
            pady = 5
        )

    def handle_close_events(self):
        """Handle close events"""
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Command-q>", self.on_closing)
        self.bind("<Command-w>", self.on_closing)

    def on_closing(self):
        """Handle closing of the window"""
        # TODO: make this less hacky
        self.master.auto_host_window = None

        self.destroy()
