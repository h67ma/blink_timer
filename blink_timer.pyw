from threading import Thread, Event
from pystray import MenuItem, Icon, Menu
from PIL import Image, ImageDraw
from datetime import datetime
from tkinter import Tk, Button, N, E, W, S, Toplevel
import time
import gc
from screeninfo import get_monitors
from config import TimerConfig, DEFAULT_CONFIG, load_config
from util import seconds_to_hh_mm_ss


APP_TITLE = "Blink Timer"


class ScreenOverlay(Tk):
	"""
	Displays black screens with white, centered text and a countdown timer.
	The windows will be dismissed on mouse click or after timer elapses.
	"""
	# TODO? easy_dismiss option that (disabled) shows a small clickable square in a random place
	# instead of the whole screen being clickable

	def __init__(self, config: TimerConfig, geometries):
		Tk.__init__(self)
		self._start_time = time.time()
		self._config = config

		self._buttons = []
		for geo in geometries:
			# create a window for each screen
			win = Toplevel()
			win.geometry("%dx%d+%d+%d" % (geo[0], geo[1], geo[2], geo[3]))
			win.configure(bg=self._config.background_color)
			win.columnconfigure(0, weight=1)
			win.rowconfigure(0, weight=1)
			win.title(self._config.title)
			#win.attributes("-fullscreen", True) # makes all windows show fullscreen on the main screen
			#win.state("zoomed") # steals focus - unacceptable
			#win.attributes("-disabled", True) # makes the window unclickable and not stealing focus, but then can't press the button
			win.overrideredirect(True)
			win.attributes("-topmost", True)

			btn = Button(win, bg=self._config.background_color, fg=self._config.foreground_color,
						 activebackground=self._config.background_color, activeforeground=self._config.foreground_color,
						 borderwidth=0, highlightthickness=0, font=("Arial", 25), command=self._destroy)
			btn.grid(sticky=N+E+W+S)
			self._buttons.append(btn)

		self.withdraw() # hide the empty root window

		self._timeout_after_id = self.after(self._config.duration_s*1000, self._destroy)
		self._update_btn_rec()

	def _update_btn_rec(self):
		remaining_s = self._config.duration_s - int(time.time() - self._start_time)
		for btn in self._buttons:
			btn.configure(text="%s\n(%d)" % (self._config.title, remaining_s))
		self._timer_after_id = self.after(1000, self._update_btn_rec)

	def _destroy(self):
		# clear timers & kill yourself
		self.after_cancel(self._timeout_after_id)
		self.after_cancel(self._timer_after_id)
		Tk.destroy(self) # dead and cold, a story told!


class PerpetualTimer(Thread):
	def __init__(self, config: TimerConfig, geometries: list[tuple[int, int, int, int]]):
		Thread.__init__(self)
		self._stopped = Event()
		self._config = config
		self._start_time = datetime.now()
		self._geometries = geometries


	def _show_screen_overlay(self):
		overlay = ScreenOverlay(self._config, self._geometries)
		overlay.mainloop()

		# gc badness to avoid spooky multithreading errors
		overlay = None
		gc.collect()


	def run(self):
		while not self._stopped.wait(self._config.period_s):
			self._show_screen_overlay()
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
			MenuItem("Timers status", self._timers_status, default=True),
			MenuItem("Update screen geometry", self._update_screen_geometries),
			MenuItem("Quit", self._quit)
		)

		self._icon = Icon(APP_TITLE, self._make_icon(), APP_TITLE, menu)
		self._geometries = []
		self._update_screen_geometries()


	@staticmethod
	def _make_icon() -> Image.Image:
		image = Image.new("RGBA", (32, 32), color=None)
		draw = ImageDraw.Draw(image)
		draw.ellipse((0, 0, 31, 31), fill="#f3f0f3", width=0)
		draw.ellipse((4, 4, 27, 27), fill="#ee4242", width=0)
		draw.ellipse((9, 9, 23, 23), fill="#0f0f0f", width=0)
		draw.ellipse((17, 9, 23, 15), fill="#f3f0f3", width=0)
		return image


	def _update_screen_geometries(self):
		self._geometries.clear()
		self._geometries.extend([(mon.width, mon.height, mon.x, mon.y) for mon in get_monitors()])


	def _timers_status(self):
		status_str = '\n'.join([str(timer) for timer in self._timers])
		self._icon.notify(status_str, title="Upcoming timers")


	def _quit(self):
		for timer in self._timers:
			timer.cancel()
		self._icon.stop()


	def run_timers(self, timer_config: list[TimerConfig]):
		self._timers.clear()

		for timer_data in timer_config:
			timer = PerpetualTimer(timer_data, self._geometries)
			self._timers.append(timer)
			timer.start()

		self._icon.run()


if __name__ == "__main__":
	app = App()
	config = load_config()
	app.run_timers(config)
