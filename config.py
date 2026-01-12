import os
import json
from platformdirs import user_config_dir


APP_NAME = "blinktimer"
CONFIG_FILENAME = "config.json"

JSON_KEY_TITLE = "title"
JSON_KEY_PERIOD = "period"
JSON_KEY_DURATION = "duration"
JSON_KEY_FG_COLOR = "foreground"
JSON_KEY_BG_COLOR = "background"


class TimerConfig:
	def __init__(self, title: str, period_s: int, duration_s: int, foreground_color: str, background_color: str):
		if period_s <= 0 or duration_s <= 0:
			raise Exception("Timer period and duration must be greater than 0")

		if period_s <= duration_s:
			raise Exception("Timer duration (%d) cannot be greater than period (%d)" % (period_s, duration_s))

		self.title = title
		self.period_s = period_s
		self.duration_s = duration_s
		self.foreground_color = foreground_color
		self.background_color = background_color


	@classmethod
	def fromobject(cls, obj: object):
		return TimerConfig(obj[JSON_KEY_TITLE],
						   obj[JSON_KEY_PERIOD],
						   obj[JSON_KEY_DURATION],
						   obj[JSON_KEY_FG_COLOR],
						   obj[JSON_KEY_BG_COLOR])


DEFAULT_CONFIG = [
	TimerConfig("Blink", 60, 2, "#FFF", "#000"),
]


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
				except Exception as ex:
					print("Invalid timer:", ex)
	except json.decoder.JSONDecodeError:
		print("Invalid config file, using default config")
		return DEFAULT_CONFIG

	if len(timers) == 0:
		print("No valid timers defined, using default config")
		return DEFAULT_CONFIG

	return timers
