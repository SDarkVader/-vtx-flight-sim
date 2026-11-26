extends RefCounted
## Configuration requests are derived from the held pilot command. Travel is measured separately.

static func manual_flight(view: Dictionary) -> bool:
	return view.get("active", false) and not view.get("paused", false) \
		and view.get("mode") == "live" and view.get("authority") == "manual" \
		and view.get("run_id") is String and not view["run_id"].is_empty()


static func configuration_patch(action: String, view: Dictionary) -> Dictionary:
	if not manual_flight(view):
		return {}
	var truth: Dictionary = view.get("rendering_truth", {})
	var command: Dictionary = truth.get("command", {})
	match action:
		"legs":
			var legs: Array = command.get("leg_extension_m", [])
			if legs.size() == 4:
				# A mixed or partial setting goes to full extension on the first press.
				var length := 0.0 if float(legs.min()) >= 0.519 else 0.52
				return {"leg_extension_m": [length, length, length, length]}
		"deploy_wings":
			return {"wing": "deploy", "canard_fold": "deployed"}
		"stow_wings":
			return {"wing": "stow", "canard_fold": "folded"}
		"pods_vertical", "pods_forward":
			var angle := 90.0 if action == "pods_vertical" else 0.0
			return {"pod_tilt_deg": [angle, angle, angle, angle]}
		"brakes":
			var brakes: Array = command.get("brake", [])
			if brakes.size() == 4:
				var amount := 0.0 if float(brakes.min()) >= 0.99 else 1.0
				return {"brake": [amount, amount, amount, amount]}
		"airbrake":
			var ecu: Dictionary = truth.get("phantom", {}).get("transition_ecu", {})
			if ecu.get("fitted", false):
				return {"airbrake": "off" if ecu.get("airbrake") == "on" else "on"}
		"manual_collective":
			return {"airbrake": "off", "stability_mode": "attitude"}
	return {}
