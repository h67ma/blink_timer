from threading import Thread, Event
from pystray import MenuItem, Icon, Menu
from PIL import Image, ImageDraw
from datetime import datetime
from tkinter import Tk, Button, N, E, W, S, Toplevel
import time
import gc
from screeninfo import get_monitors
from platformdirs import user_config_dir
import os
import json


APP_NAME = "blinktimer"
APP_TITLE = "Blink Timer"
CONFIG_FILENAME = "config.json"

JSON_KEY_TITLE = "title"
JSON_KEY_PERIOD = "period"
JSON_KEY_DURATION = "duration"

geometries = [(mon.width, mon.height, mon.x, mon.y) for mon in get_monitors()]

class TimerConfig:
	def __init__(self, title: str, period_s: int, duration_s: int):
		self.title = title
		self.period_s = period_s
		self.duration_s = duration_s


	@classmethod
	def fromobject(cls, obj: object):
		return TimerConfig(obj[JSON_KEY_TITLE],
						   obj[JSON_KEY_PERIOD],
						   obj[JSON_KEY_DURATION])


DEFAULT_CONFIG = [
	TimerConfig("Blink", 60, 2),
]


class ScreenOverlay(Tk):
	"""Displays black screens with white, centered text and a countdown timer.
	The windows will be dismissed on mouse click or after break_time_s elapses."""

	def __init__(self, screen_text, break_time_s):
		Tk.__init__(self)
		self.start_time = time.time()
		self.screen_text = screen_text
		self.break_time_s = break_time_s

		self.buttons = []
		for geo in geometries:
			# create a window for each screen
			win = Toplevel()
			win.geometry("%dx%d+%d+%d" % (geo[0], geo[1], geo[2], geo[3]))
			win.configure(bg="black")
			win.columnconfigure(0, weight=1)
			win.rowconfigure(0, weight=1)
			win.title(screen_text)
			#win.attributes("-fullscreen", True) # makes all windows show fullscreen on the main screen
			#win.state("zoomed") # steals focus - unacceptable
			#win.attributes("-disabled", True) # makes the window unclickable and not stealing focus, but then can't press the button
			win.overrideredirect(True)
			win.attributes("-topmost", True)

			btn = Button(win, bg="black", fg="white", activebackground="black", activeforeground="white", borderwidth=0, highlightthickness=0, font=("Arial", 25), command=self.destroy)
			btn.grid(sticky=N+E+W+S)
			self.buttons.append(btn)

		self.withdraw() # hide the empty root window

		self.timeout_after_id = self.after(break_time_s*1000, self.destroy)
		self.update_btn_rec()

	def update_btn_rec(self):
		remaining_s = self.break_time_s - int(time.time() - self.start_time)
		for btn in self.buttons:
			btn.configure(text="%s\n(%d)" % (self.screen_text, remaining_s))
		self.timer_after_id = self.after(1000, self.update_btn_rec)

	def destroy(self):
		# clear timers & kill yourself
		self.after_cancel(self.timeout_after_id)
		self.after_cancel(self.timer_after_id)
		Tk.destroy(self) # dead and cold, a story told!


def show_screen_overlay(screen_text: str, duration_s: int):
	overlay = ScreenOverlay(screen_text, duration_s)
	overlay.mainloop()

	# gc badness to avoid spooky multithreading errors
	overlay = None
	gc.collect()


def seconds_to_hh_mm_ss(seconds: int) -> str:
	out_h = int(seconds / 3600)
	out_m = int((seconds % 3600) / 60)
	out_s = int(seconds % 60)
	return "%d:%02d:%02d" % (out_h, out_m, out_s)


class PerpetualTimer(Thread):
	def __init__(self, config: TimerConfig):
		Thread.__init__(self)
		self._stopped = Event()
		self._config = config
		self._start_time = datetime.now()

	def run(self):
		while not self._stopped.wait(self._config.period_s):
			show_screen_overlay(self._config.title, self._config.duration_s)
			self._start_time = datetime.now()


	def cancel(self):
		self._stopped.set()


	def get_remaining_seconds(self) -> int:
		return self._config.period_s - (datetime.now() - self._start_time).seconds


	def __str__(self):
		return "%s\t%s (every %s)" % (seconds_to_hh_mm_ss(self.get_remaining_seconds()), self._config.title, seconds_to_hh_mm_ss(self._config.period_s))


class App:
	def __init__(self):
		self._timers = []

		menu = Menu(
			MenuItem("Timers status", self.timers_status, default=True),
			MenuItem("Quit", self.quit)
		)

		self._icon = Icon(APP_TITLE, self._make_icon(), APP_TITLE, menu)


	@staticmethod
	def _make_icon() -> Image.Image:
		image = Image.new("RGBA", (32, 32), color=None)
		draw = ImageDraw.Draw(image)
		draw.ellipse((0, 0, 31, 31), fill="#f3f0f3", width=0)
		draw.ellipse((4, 4, 27, 27), fill="#ee4242", width=0)
		draw.ellipse((9, 9, 23, 23), fill="#0f0f0f", width=0)
		draw.ellipse((17, 9, 23, 15), fill="#f3f0f3", width=0)
		return image


	def timers_status(self):
		status_str = '\n'.join([str(timer) for timer in self._timers])
		self._icon.notify(status_str, title="Upcoming timers")


	def quit(self):
		for timer in self._timers:
			timer.cancel()
		self._icon.stop()


	def run_timers(self, timer_config: list[TimerConfig]):
		self._timers.clear()

		for timer_data in timer_config:
			timer = PerpetualTimer(timer_data)
			self._timers.append(timer)
			timer.start()

		self._icon.run()


def load_config() -> list[TimerConfig]:
	"""
	Loads configuration from a file stored in the standard configuration path.
	If the file does not exist or is invalid, returns default configuration.

	@returns list of timer configs
	"""
	config_dir = user_config_dir(APP_NAME)
	config_path = os.path.join(config_dir, CONFIG_FILENAME)

	if not os.path.exists(config_path):
		print("Config does not exist, using default config")
		return DEFAULT_CONFIG

	timers = []
	try:
		with open(config_path, "r") as f:
			loaded = json.load(f)

			if not isinstance(loaded, list):
				print("Invalid config file, using default config")
				return DEFAULT_CONFIG

			for entry in loaded:
				try:
					timers.append(TimerConfig.fromobject(entry))
				except (KeyError, TypeError):
					print("Invalid timer")
	except json.decoder.JSONDecodeError:
		print("Invalid config file, using default config")
		return DEFAULT_CONFIG

	if len(timers) == 0:
		print("No valid timers defined, using default config")
		return DEFAULT_CONFIG

	return timers


if __name__ == "__main__":
	app = App()
	config = load_config()
	app.run_timers(config)
