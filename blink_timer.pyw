from threading import Thread, Event
from pystray import MenuItem, Icon, Menu
from PIL import Image, ImageDraw
from datetime import datetime
from tkinter import Tk, Button, N, E, W, S, Toplevel
import time
import gc
from screeninfo import get_monitors

BLANK_SCREEN = True # False = show a notification
BREAK_TIME = 2

geometries = [(mon.width, mon.height, mon.x, mon.y) for mon in get_monitors()]

TIMERS_DATA = [
	(60, "Blink")
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


def show_screen_overlay(screen_text):
	overlay = ScreenOverlay(screen_text, BREAK_TIME)
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
	def __init__(self, duration: int, func, name: str):
		Thread.__init__(self)
		self.stopped = Event()
		self.duration = duration
		self.func = func
		self.name = name # sorry, you just get a single arg
		self.start_time = datetime.now()

	def run(self):
		while not self.stopped.wait(self.duration):
			self.func(self.name)
			self.start_time = datetime.now()

	def cancel(self):
		self.stopped.set()

	def get_remaining_seconds(self) -> int:
		return self.duration - (datetime.now() - self.start_time).seconds


timers = []

def timers_status():
	status_str = ""
	for timer in timers:
		status_str += "%s\t%s (every %s)\n" % (seconds_to_hh_mm_ss(timer.get_remaining_seconds()), timer.name, seconds_to_hh_mm_ss(timer.duration))
	icon.notify(status_str, title="Upcoming timers")


def quit():
	for timer in timers:
		timer.cancel()
	icon.stop()


try:
	image = Image.open("icon.png")
except:
	# fallback icon, hand drawn
	image = Image.new("RGBA", (16, 16), color=None)
	draw = ImageDraw.Draw(image)
	draw.line([(7, 1), (7, 14)], width=4, fill="green")
	draw.line([(1, 2), (14, 2)], width=4, fill="green")

menu = Menu(
	MenuItem("Timers status", timers_status, default=True),
	MenuItem("Quit", quit)
)

icon = Icon("Simple Timer", image, "Simple Timer", menu)

if BLANK_SCREEN:
	action = show_screen_overlay
else:
	action = icon.notify

for timer_data in TIMERS_DATA:
	timer = PerpetualTimer(timer_data[0], action, timer_data[1])
	timers.append(timer)
	timer.start()

icon.run()
