def seconds_to_hh_mm_ss(seconds: int) -> str:
	out_h = int(seconds / 3600)
	out_m = int((seconds % 3600) / 60)
	out_s = int(seconds % 60)
	return "%d:%02d:%02d" % (out_h, out_m, out_s)
