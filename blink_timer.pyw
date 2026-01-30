import gc
from enum import Enum
from queue import Queue, Empty
from threading import Thread, Event
from pystray import MenuItem, Icon, Menu
from PIL import Image, ImageDraw
from datetime import datetime
from tkinter import Tk, Button, N, E, W, S, Toplevel
from screeninfo import get_monitors
from config import TimerConfig, DEFAULT_CONFIG, load_config
from util import seconds_to_hh_mm_ss, timestamp


APP_TITLE = "Blink Timer"


class ScreenOverlay(Tk):
	"""
	Displays black screens with white, centered text and a countdown timer.
	The windows will be dismissed on mouse click or after timer elapses.
	"""
	# TODO? easy_dismiss option that (disabled) shows a small clickable square in a random place
	# instead of the whole screen being clickable

	def __init__(self, config: TimerConfig, geometries: list[tuple[int, int, int, int]]):
		Tk.__init__(self)
		self._start_time = timestamp()
		self._config = config

		self._buttons = []
		for geo in geometries:
			# create a window for each screen
			win = Toplevel()
			win.geometry("%dx%d+%d+%d" % geo)
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
						 borderwidth=0, highlightthickness=0, font=("Arial", 25), command=self.destroy)
			btn.grid(sticky=N+E+W+S)
			self._buttons.append(btn)

		self.withdraw() # hide the empty root window

		self._timeout_after_id = self.after(self._config.duration_s*1000, self.destroy)
		self._update_btn_rec()


	def _update_btn_rec(self):
		remaining_s = self._config.duration_s - (timestamp() - self._start_time)
		for btn in self._buttons:
			btn.configure(text="%s\n(%d)" % (self._config.title, remaining_s))
		self._timer_after_id = self.after(1000, self._update_btn_rec)


	def destroy(self):
		# clear timers & kill yourself
		self.after_cancel(self._timeout_after_id)
		self.after_cancel(self._timer_after_id)
		Tk.destroy(self) # dead and cold, a story told!


class Timer:
	def __init__(self, config: TimerConfig, timestamp: int):
		self.config = config
		self.reset(timestamp)


	def __str__(self):
		return "%s\t%s (every %s)" % (seconds_to_hh_mm_ss(self.next_time - timestamp()), self.config.title, seconds_to_hh_mm_ss(self.config.period_s))


	def reset(self, timestamp: int):
		self.next_time = timestamp + self.config.period_s


	def reschedule(self):
		"""Sets the next time to show timer based on last show time and timer period"""
		self.next_time += self.config.period_s


	def get_next_time_finish(self) -> int:
		"""Returns: timestamp when next timer show will end"""
		return self.next_time + self.config.duration_s


class TimerMessage(Enum):
	STATUS = 1
	UPDATE_GEOMETRY = 2
	RESET_TIMERS = 3
	QUIT = 4


# events sent to TimersThread. valid values are TimerMessage
timers_event_queue = Queue()

timers_wake_event = Event()

# events sent to App. valid values are strings
main_event_queue = Queue()


class TimersThread(Thread):
	def __init__(self, timers_config: TimerConfig):
		Thread.__init__(self)

		now = timestamp()
		# automatically calculates first show time to show each timer
		self._timers: list[Timer] = [Timer(config, now) for config in timers_config]
		self._reschedule_covered_timers() # initial check

		self._geometries = [] # caches results from get_monitors()
		self._update_geometries() # populate initial values

		self._overlay = None


	def _update_geometries(self):
		self._geometries.clear()
		self._geometries.extend([(mon.width, mon.height, mon.x, mon.y) for mon in get_monitors()])


	def run(self):
		while True:
			# wait for timeout or wake signal for up to 1 second
			# this is the defacto timer resolution. when a timer occurs before that time elapses,
			# next timer will be delayed by up to 1 second. this is fine, as timers are not
			# meant for precise time tracking
			woke_up = timers_wake_event.wait(timeout=1)

			if woke_up:
				timers_wake_event.clear()

				while True:
					try:
						event = timers_event_queue.get_nowait()
					except Empty:
						break

					if event == TimerMessage.STATUS:
						# messages to main thread are always status strings
						status_str = '\n'.join([str(timer) for timer in self._timers])
						main_event_queue.put(status_str)
					elif event == TimerMessage.UPDATE_GEOMETRY:
						self._update_geometries()
					elif event == TimerMessage.RESET_TIMERS:
						now = timestamp()
						for timer in self._timers:
							timer.reset(now)
						self._reschedule_covered_timers()
					elif event == TimerMessage.QUIT:
						return
					else:
						print("Unknown message")

			# will block the message queue if a timer activates. this is not an issue because user won't be able to
			# interact with the program while the overlay is shown
			self._check_timers()


	def _check_timers(self):
		"""Checks if any timer needs to be shown now. If so, shows it (blocking), ignoring remaining timers."""
		now = timestamp()
		for timer in self._timers:
			diff = now - timer.next_time
			if diff > 0:
				if diff < 10:
					self._activate_timer(timer)
					break
				else:
					# it's long past the time the timer should've been shown (expected <1s, actual (arbitrary) 10s or
					# more) - assume the program or PC slept. without this check, a timer would be shown every second
					# after such sleep, which is unacceptable
					print("Sleep detected, resetting timers")
					for timer in self._timers:
						timer.reset(now)
					break


	def _activate_timer(self, timer: Timer):
		"""Shows an overlay window (blocking) and calculates next times to show all timers"""
		self._show_screen_overlay(timer.config)
		timer.reschedule()
		self._reschedule_covered_timers()


	def _show_screen_overlay(self, config: TimerConfig):
		"""Shows the overlay window. Blocks as long as the window is visible."""
		# will take care of destroying itself when the time comes or when user clicks it
		self._overlay = ScreenOverlay(config, self._geometries)
		self._overlay.mainloop()

		# gc badness to avoid spooky multithreading errors
		self._overlay = None
		gc.collect()


	def _reschedule_covered_timers(self):
		"""
		Checks if any timer occurs at the same time as another timer with lower priority.
		Fixes times if necessary.
		"""
		# assume a high-prio timer will always have duration >= lower-prio timer.
		# otherwise the low-prio timer would have to be stopped to show the high-prio timer,
		# if they occur at the same time. this is checked during config load.
		# TODO if the user interrupts one of the higher-prio timers, it might happen that this timer should effectively
		# be shown earlier. this is kind of tricky to check
		for timer_idx, timer in enumerate(self._timers):
			# check all higher-prio timers
			for higher_prio_timer in self._timers[:timer_idx]:
				while timer.get_next_time_finish() >= higher_prio_timer.next_time and \
					  timer.next_time <= higher_prio_timer.get_next_time_finish():
					# we can assume all higher-prio timers don't overlap (because we've already rescheduled them,
					# if it was needed). therefore we just need to reschedule for the sum of all higher-prio ones
					timer.reschedule()


	def cancel(self):
		if self._overlay is not None:
			self._overlay.destroy()


class App:
	def __init__(self, timers_config: list[TimerConfig]):
		# TODO? add an option to pause timers for X minutes (configurable)
		menu = Menu(
			MenuItem("Timers status", self._timers_status, default=True),
			MenuItem("Reset timers", self._reset_timers),
			MenuItem("Update screen geometry", self._update_screen_geometries),
			MenuItem("Quit", self._quit)
		)

		self._icon = Icon(APP_TITLE, self._make_icon(), APP_TITLE, menu)
		self._timers_thread = TimersThread(timers_config)


	@staticmethod
	def _make_icon() -> Image.Image:
		image = Image.new("RGBA", (32, 32), color=None)
		draw = ImageDraw.Draw(image)
		draw.ellipse((0, 0, 31, 31), fill="#f3f0f3", width=0)
		draw.ellipse((4, 4, 27, 27), fill="#ee4242", width=0)
		draw.ellipse((9, 9, 23, 23), fill="#0f0f0f", width=0)
		draw.ellipse((17, 9, 23, 15), fill="#f3f0f3", width=0)
		return image


	def _timers_status(self):
		timers_event_queue.put(TimerMessage.STATUS)
		timers_wake_event.set()

		# wait for response from timers thread about current times
		try:
			# assume the event is a status string, since this is the only possibility
			status_str = main_event_queue.get(timeout=1)
			self._icon.notify(status_str, title="Upcoming timers")
		except Empty:
			print("Message from timers thread not received")
			return


	def _reset_timers(self):
		timers_event_queue.put(TimerMessage.RESET_TIMERS)
		timers_wake_event.set()


	def _update_screen_geometries(self):
		timers_event_queue.put(TimerMessage.UPDATE_GEOMETRY)
		timers_wake_event.set()


	def _quit(self):
		timers_event_queue.put(TimerMessage.QUIT)
		timers_wake_event.set()

		# will also stop main loop
		self._icon.stop()


	def run(self):
		self._timers_thread.start()
		self._icon.run()
		self._timers_thread.join()


if __name__ == "__main__":
	config = load_config()
	app = App(config)
	app.run()
