#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ======================================================================
# Version
# ======================================================================
VERSION = "3.7.4" # Build date: 260425 (YYMMDD)

import csv
import json
import re
import time
import subprocess
import random
import uuid
import shutil

from datetime import datetime
from pathlib import Path

from threading import Thread

from flask import Flask, jsonify, send_from_directory, request
from typing import Union, Tuple

# ======================================================================
# Paths & Config
# ======================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
STATIC_DIR = SCRIPT_DIR / "static"
PROJECTS_PATH = SCRIPT_DIR / "projects"
CONFIG_FILE = SCRIPT_DIR / "config.json"
PHONERULES_PATH = SCRIPT_DIR / "phone_rules.json"

app = Flask(__name__, static_folder="static", static_url_path="")


def get_main_config() -> dict:
	if not CONFIG_FILE.exists():
		return {
			"project_name": None,
			"delay_seconds": None,
			"kdeconnect": None,
			"dryrun": None,
		}

	with CONFIG_FILE.open("r", encoding="utf-8-sig") as f:
		return json.load(f)


def save_main_config(data: dict):
	with CONFIG_FILE.open("w", encoding="utf-8-sig") as f:
		json.dump(data, f, indent=2, ensure_ascii=False)


def get_project_path(project_name: str) -> Path:
	""" Returns the absolute path for a given project """
	return PROJECTS_PATH / project_name


def get_project_config(project_name: str) -> dict:

	project_path = get_project_path(project_name)
	config_path = project_path / "project.json"

	if not config_path.exists():
		return {
			"csv_file": None,
			"template_file": None,
			"editorRTL": None,
			"country": None
		}

	with config_path.open("r", encoding="utf-8-sig") as f:
		return json.load(f)


def save_project_config(project_name: str, data: dict):
	project_path = get_project_path(project_name)
	project_path.mkdir(parents=True, exist_ok=True)
	config_path = project_path / "project.json"

	with config_path.open("w", encoding="utf-8-sig") as f:
		json.dump(data, f, indent=2, ensure_ascii=False)


def get_phone_rules(country: str) -> dict:
	""" Loads phone validation rules for a specific country from JSON. """
	if not PHONERULES_PATH.exists():
		return {
			"IR": {
				"country_code": "98",
				"phone_prefix": "+98",
				"mobile_pattern": "9\\d{9}",
				"local_prefix": "0",
				"local_length": 11
			}
		}

	with PHONERULES_PATH.open("r", encoding="utf-8-sig") as f:
		all_rules = json.load(f)

	return all_rules.get(country)

# ======================================================================
# Helpers
# ======================================================================

SEND_JOBS = {}

def get_active_context() -> dict:
	main_cfg = get_main_config()
	project_name = main_cfg.get("project_name")

	if not project_name:
		return {
			"project_name": None,
			"general_config": None,
			"project_path": None,
			"project_config": None,
			"csv_path": None,
			"template_path": None,
			"delay_base": None,
			"kdeconnect_activation": None,
			"dryrun": None,
			"country": None,
			"phone_rules": None,
			"editorRTL": None,
		}

	delay_base = int(main_cfg.get("delay_seconds", 10))
	kdeconnect_activation = bool(main_cfg.get("kdeconnect", False))
	dryrun = main_cfg.get("dryrun")


	proj_cfg = get_project_config(project_name)
	project_path = get_project_path(project_name)

	active_country = proj_cfg.get("country")
	editorRTL = proj_cfg.get("editorRTL")

	phonerules_cfg = get_phone_rules(active_country)

	csv_dir = project_path / "csv"
	template_dir = project_path / "templates"

	csv_file = proj_cfg.get("csv_file") or ""
	if not csv_file:
		csv_file = get_first_file(csv_dir, "csv")

	template_file = proj_cfg.get("template_file") or ""
	if not template_file:
		template_file = get_first_file(template_dir, "txt")

	csv_path = project_path / csv_file if csv_file else None
	template_path = project_path / template_file if template_file else None

	return {
		"project_name": project_name,
		"general_config": main_cfg,
		"project_path": project_path,
		"project_config": proj_cfg,
		"csv_path": csv_path,
		"template_path": template_path,
		"delay_base": delay_base,
		"kdeconnect_activation": kdeconnect_activation,
		"dryrun": dryrun,
		"country": active_country,
		"phone_rules": phonerules_cfg,
		"editorRTL": editorRTL,
	}


def normalize_phone(phone: str, rules) -> str:
	if not phone:
		return ""

	p = phone.strip()
	p = re.sub(r"[()\-\s]", "", p)

	country_code = rules.get("country_code")
	phone_prefix = rules.get("phone_prefix")
	local_prefix = rules.get("local_prefix")
	local_length = rules.get("local_length")

	if not country_code or not phone_prefix:
		return ""

	# Remove international prefix formats
	if p.startswith("00" + country_code):
		p = p[2:]
	elif p.startswith("+" + country_code):
		p = p[1:]
	elif p.startswith(country_code):
		pass

	# Convert country-code-prefixed → local format
	if p.startswith(country_code):
		p = local_prefix + p[len(country_code):]

	# Case: fully local (with or without prefix)
	if p.startswith(local_prefix) and len(p) == local_length:
		local_number = p[len(local_prefix):]
	elif not p.startswith(local_prefix) and len(p) == (local_length - len(local_prefix)):
		local_number = p
	else:
		return ""

	# Return E.164
	return phone_prefix + local_number


def split_phones(mob_cell: str) -> list:
	if not mob_cell:
		return []

	raw = mob_cell.strip()
	parts = re.split(r"[;,\|\n/\\]+", raw)
	result = []
	seen = set()

	for part in parts:
		p = part.strip()
		if not p:
			continue

		# Dedup
		if p not in seen:
			result.append(p)
			seen.add(p)

	return result


def validate_mobile(phone: str, rules) -> bool:
	if not phone:
		return False

	phone_prefix = rules.get("phone_prefix")
	local_prefix = rules.get("local_prefix")
	pattern = rules.get("mobile_pattern")

	if not phone_prefix or local_prefix is None or not pattern:
		return False

	# Phone must already be in E.164 format from normalize_phone
	if not phone.startswith(phone_prefix):
		return False

	local = phone[len(phone_prefix):]
	if local_prefix:
		local = local_prefix + local

	return re.match(pattern, local) is not None


def get_first_file(path, ext) -> str:

	if not path.exists():
		return None

	files = sorted(path.glob(f"*.{ext}"))

	if not files:
		return None

	return files[0].name


# ======================================================================
# CSV / Template logic
# ======================================================================

def is_send_allowed(row: dict) -> bool:
	"""
	Check CSV column 'send':
	- "1", "yes", "y", "true" => allowed
	- anything else => skip
	"""
	val = (row.get("send", "") or "").strip().lower()
	return val in {"1", "yes", "y", "true"}


def render_message(template: str, row: dict) -> str:
	"""
	Render template using *any* CSV column.
	Missing keys are replaced with empty string.
	"""
	class SafeDict(dict):
		def __missing__(self, key):
			return ""

	msg = template.format_map(SafeDict(row))
	return "\n".join(l.rstrip() for l in msg.splitlines()).strip() + "\n"


# ======================================================================
# KDE Connect
# ======================================================================

def get_devices() -> dict:

	"""
	Return list of reachable devices: [(device_name, device_id), ...]
	Parsed from kdeconnect-cli -l
	"""

	result = subprocess.run(
		["kdeconnect-cli", "-l"],
		capture_output=True,
		text=True
	)

	if result.returncode != 0:
		raise RuntimeError("kdeconnect-cli not available")

	devices = []
	for line in result.stdout.splitlines():
		line = line.strip()
		if not line.startswith("- "):
			continue
		if "(paired and reachable)" in line and ":" in line:
			device_name = line.split(":", 1)[0].replace("- ", "").strip()
			device_id = line.split(":", 1)[1].split("(", 1)[0].strip()
			devices.append(
				{"name": device_name,
				"id": device_id}
			)

	devices.sort(key=lambda x: x["name"].lower())
	
	return devices


def send_sms(device_name, phone, message):
	"""
	Send SMS using kdeconnect-cli by DEVICE NAME (not device id).
	Example: kdeconnect-cli -n SM-A305F --destination +1... --send-sms "..."
	"""
	cmd = [
		"kdeconnect-cli",
		"-n", device_name,
		"--destination", phone,
		"--send-sms", message
	]
	result = subprocess.run(cmd, capture_output=True, text=True)
	if result.returncode != 0:
		raise RuntimeError(result.stderr.strip() or "send-sms failed")


def run_send_job(job_id, rows, device_name, project_name):

	job = SEND_JOBS.get(job_id)

	if not job:
		return

	job["status"] = "RUNNING"

	main_cfg = get_main_config()
	project_name = main_cfg.get("project_name")

	proj_cfg = get_project_config(project_name)

	country = proj_cfg.get("country")

	rules = get_phone_rules(country)

	kdeconnect_activation = bool(main_cfg.get("kdeconnect", False))
	dryrun = bool(main_cfg.get("dryrun", True))

	delay_base = int(main_cfg.get("delay_seconds", 10))
	delay_min = max(1, delay_base - 3)
	delay_max = max(delay_min, delay_base + 3)

	template_file = proj_cfg.get("template_file")
	template_path = ensure_template_folder(project_name) / template_file

	with template_path.open("r", encoding="utf-8-sig") as f:
		template = f.read()

	try:

		for i, row in enumerate(rows, 1):

			if not is_send_allowed(row):

				job["skipped"] += 1

				job["results"].append({
					"row": i,
					"name": f"{row.get('firstname','')} {row.get('lastname','')}".strip(),
					"phone": "",
					"status": "SKIPPED",
					"message": "SKIPPED",
					"error": "",
					"delay": 0,
					"timestamp": time.time()
				})

				continue

			phones = split_phones(row.get("mob", ""))

			if not phones:

				job["failed"] += 1

				job["results"].append({
					"row": i,
					"name": f"{row.get('firstname','')} {row.get('lastname','')}".strip(),
					"phone": "",
					"status": "FAILED",
					"message": "NO PHONE",
					"error": "",
					"delay": 0,
					"timestamp": time.time()
				})

				continue

			for phone in phones:

				phone = normalize_phone(phone, rules)

				result = {
					"row": i,
					"name": f"{row.get('firstname','')} {row.get('lastname','')}".strip(),
					"phone": phone,
					"status": "",
					"message": "",
					"error": "",
					"delay": 0,
					"timestamp": time.time()
				}

				try:

					if not validate_mobile(phone, rules):

						job["failed"] += 1

						job["results"].append({
							"row": i,
							"name": f"{row.get('firstname','')} {row.get('lastname','')}".strip(),
							"phone": phone,
							"status": "INVALID",
							"message": "INVALID",
							"error": "",
							"delay": 0,
							"timestamp": time.time()
						})

					else:

						if kdeconnect_activation or not dryrun:
							delay = random.randint(delay_min, delay_max)
						else:
							delay = 0

						job["results"].append({
							"row": i,
							"name": f"{row.get('firstname','')} {row.get('lastname','')}".strip(),
							"phone": phone,
							"status": "SENDING",
							"message": "SENDING",
							"error": "",
							"delay": delay,
							"timestamp": time.time()
						})

						msg = render_message(template, row)

						if kdeconnect_activation:
							print(f"\t⭕️ KDE-Sender ON")
							# ++++++++++++++++++++++++++++++++++++++++++++++++++++
							send_sms(device_name, phone, msg)
							# ++++++++++++++++++++++++++++++++++++++++++++++++++++
						else:
							print(f"\t⭕️ KDE-Sender OFF")

						time.sleep(delay)
						
						job["sent"] += 1

						job["results"][-1]["status"] = "SENT"
						job["results"][-1]["message"] = "DONE :)"


				except Exception as e:

					job["failed"] += 1

					job["results"].append({
						"row": i,
						"name": f"{row.get('firstname','')} {row.get('lastname','')}".strip(),
						"phone": phone,
						"status": "ERROR",
						"message": "",
						"error": str(e),
						"delay": 0,
						"timestamp": time.time()
					})

	finally:

		job["status"] = "DONE"
		job["finished"] = True


# ======================================================================
# =============================    APIs    =============================
# ======================================================================

@app.route("/")
def index():
	return send_from_directory(STATIC_DIR, "index.html")

@app.route("/api/version")
def get_version() -> dict:
	return {
		"version": VERSION
	}

# ======================================================================
# Endpoints: Projects
# ======================================================================

@app.route("/api/projects", methods=["GET"])
def list_projects() -> Union[dict, Tuple[dict, int]]:
	try:
		if not PROJECTS_PATH.exists():
			PROJECTS_PATH.mkdir(parents=True, exist_ok=True)

		projects_data = []
		
		# Extract directories and sort
		project_dirs = sorted([p for p in PROJECTS_PATH.iterdir() if p.is_dir()])
		
		for p in project_dirs:
			project_info = { "name": p.name, "country": "-" }
			json_file = p / "project.json"
			
			if json_file.exists():
				try:
					# Use utf-8-sig to ignore BOM
					with open(json_file, "r", encoding="utf-8-sig") as f:
						data = json.load(f)
						project_info["country"] = data.get("country", "-")
				except Exception:
					pass
					
			projects_data.append(project_info)

		return {
			"ok": True, 
			"projects": projects_data
		}
	
	except Exception as e:
		return {
			"ok": False,
			"error": str(e)
		}, 500


@app.route("/api/phone-rules", methods=["GET"])
def get_rules() -> Union[dict, Tuple[dict, int]]:
	try:
		if not PHONERULES_PATH.exists():
			return {
				"ok": True,
				"countries": []
			}
		
		with open(PHONERULES_PATH, "r", encoding="utf-8-sig") as f:
			rules = json.load(f)
			# Return only the keys (country code abbreviations)
			return {
				"ok": True,
				"countries": list(rules.keys())
			}
	
	except Exception as e:
		return {
			"ok": False,
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/country", methods=["POST"])
def update_project_country(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		data = request.json
		new_country = data.get("country")
		
		if not new_country:
			return {
				"ok": False,
				"error": "Country is required"
			}, 400

		project_dir = PROJECTS_PATH / project
		if not project_dir.exists():
			return {
				"ok": False,
				"error": "Project not found"
			}, 404

		json_file = project_dir / "project.json"
		project_data = {}
		
		# Read existing data if available
		if json_file.exists():
			with open(json_file, "r", encoding="utf-8-sig") as f:
				project_data = json.load(f)

		if project_data["country"] == new_country:
			return {
				"ok": False,
				"error": "Country already selected"
			}, 404

		# Update the country field
		project_data["country"] = new_country

		# Save the file again
		with open(json_file, "w", encoding="utf-8") as f:
			json.dump(project_data, f, indent=4, ensure_ascii=False)

		return {
			"ok": True
		}

	except Exception as e:
		return {
			"ok": False,
			"error": str(e)
		}, 500


@app.route("/api/projects", methods=["POST"])
def create_project() -> Union[dict, Tuple[dict, int]]:
	try:
		data = request.get_json(force=True) or {}
		name = (data.get("name") or "").strip()

		if not name:
			return {
				"ok": False,
				"error": "Project name is required"
			}, 400

		project_path = get_project_path(name)

		if project_path.exists():
			return {
				"ok": False, 
				"error": "project already exists"
			}, 400

		(project_path / "csv").mkdir(parents=True, exist_ok=True)
		(project_path / "templates").mkdir(parents=True, exist_ok=True)

		default_cfg = {
			"csv_file": None,
			"template_file": None,
			"editorRTL": None,
			"country": None,
		}

		save_project_config(name, default_cfg)

		return {
			"ok": True,
			"project": name
		}

	except Exception as e:
		return {
			"ok": False,
			"error": str(e)
		}, 500


@app.route("/api/projects/<name>", methods=["DELETE"])
def del_project(name: str) -> Union[dict, Tuple[dict, int]]:
	try:
		if not name:
			return {
				"ok": False, 
				"error": "Project name missing"
			}, 400

		target = PROJECTS_PATH / name

		if not target.exists():
			return {
				"ok": False, 
				"error": "Project not found"
			}, 404

		# For safety, delete only if empty
		has_content = any((target / folder).exists() and any((target / folder).iterdir()) for folder in ["csv", "templates"])

		if has_content:
			return {
				"ok": False, 
				"error": "Project is not empty"
			}, 400

		shutil.rmtree(target)

		return {
			"ok": True, 
			"deleted": name
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/rename", methods=["POST"])
def rename_project() -> Union[dict, Tuple[dict, int]]:
	try:
		data = request.json or {}
		old = data.get("old", "").strip()
		new = data.get("new", "").strip()

		if not old or not new:
			return {
				"ok": False, 
				"error": "old/new project name missing"
			}, 400

		old_path = PROJECTS_PATH / old
		new_path = PROJECTS_PATH / new

		if not old_path.exists():
			return {
				"ok": False, 
				"error": "old project not found"
			}, 404

		if new_path.exists():
			return {
				"ok": False, "error":
				"target name already exists"
			}, 400

		old_path.rename(new_path)

		return {
			"ok": True, 
			"old": old, 
			"new": new
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


# ======================================================================
# Endpoints: CSV Files
# ======================================================================

def ensure_csv_folder(project: str) -> Path:
	project_path = get_project_path(project)
	csv_path = project_path / "csv"
	csv_path.mkdir(parents=True, exist_ok=True)
	return csv_path


@app.route("/api/projects/<project>/csv", methods=["GET"])
def list_csv(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		csv_path = ensure_csv_folder(project)
		files = [p.name for p in csv_path.glob("*.csv")]

		return {
			"ok": True,
			"files": sorted(files)
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/csv/upload", methods=["POST"])
def upload_csv(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		csv_path = ensure_csv_folder(project)

		if "file" not in request.files:
			return {
				"ok": False, 
				"error": "no file uploaded"
			}, 400

		f = request.files["file"]

		if not f.filename.lower().endswith(".csv"):
			return {
				"ok": False,
				"error": "file must be .csv"
			}, 400

		save_path = csv_path / f.filename
		f.save(str(save_path))

		return {
			"ok": True, 
			"saved": f.filename
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/csv/duplicate", methods=["POST"])
def duplicate_csv(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		csv_path = ensure_csv_folder(project)

		data = request.json or {}
		original = data.get("original", "").strip()
		new_name = data.get("new_name", "").strip()
		
		if not original or not new_name:
			return {
				"ok": False, 
				"error": "original or new_name missing"
			}, 400
			
		old_path = csv_path / original
		new_path = csv_path / new_name
		
		if not old_path.exists():
			return {
				"ok": False, 
				"error": "original csv not found"
			}, 404

		if new_path.exists():
			return {
				"ok": False, 
				"error": "target name already exists"
			}, 400
			
		# Copy the original file along with its contents to a new file
		shutil.copy2(old_path, new_path)
		
		return {
			"ok": True, 
			"original": original, 
			"new": new_name
		}
	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/csv/<filename>", methods=["DELETE"])
def delete_csv(project: str, filename: str) -> Union[dict, Tuple[dict, int]]:
	try:
		csv_path = ensure_csv_folder(project)
		target = csv_path / filename

		if not target.exists():
			return {
				"ok": False, 
				"error": "csv not found"
			}, 404

		target.unlink()

		return {
			"ok": True, 
			"deleted": filename
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/csv/<filename>", methods=["GET"])
def get_csv(project: str, filename: str) -> Union[dict, Tuple[dict, int]]:
	try:
		csv_dir = ensure_csv_folder(project)
		csv_path = csv_dir / filename

		if not csv_path.exists():
			return {
				"ok": False,
				"error": "CSV file not found"
			}

		with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
			reader = csv.DictReader(f)
			rows = list(reader)

		return {
			"ok": True,
			"headers": reader.fieldnames,
			"rows": rows
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/csv/<filename>", methods=["POST"])
def save_csv(project: str, filename: str) -> Union[dict, Tuple[dict, int]]:
	try:
		csv_dir = ensure_csv_folder(project)
		csv_path = csv_dir / filename

		data = request.get_json(force=True)
		headers = data.get("headers", [])
		rows = data.get("rows", [])

		if not headers:
			return {
				"ok": False,
				"error": "Invalid CSV data"
			}

		with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
			writer = csv.DictWriter(f, fieldnames=headers)
			writer.writeheader()
			for row in rows:
				writer.writerow(row)

		return {
			"ok": True
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/csv/rename", methods=["POST"])
def rename_csv(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		csv_path = ensure_csv_folder(project)

		cfg = get_project_config(project)
		csv_file = cfg.get("csv_file")
		template_file = cfg.get("template_file")
		editorRTL = cfg.get("editorRTL")
		country = cfg.get("country")

		data = request.json or {}
		old = data.get("old", "").strip()
		new = data.get("new", "").strip()

		if not old or not new:
			return {
				"ok": False,
				"error": "old/new missing"
			}, 400

		old_path = csv_path / old
		new_path = csv_path / new

		if not old_path.exists():
			return {
				"ok": False, 
				"error": "old csv not found"
			}, 404

		if new_path.exists():
			return {
				"ok": False, 
				"error": "target name exists"
			}, 400

		old_path.rename(new_path)

		if old == csv_file :
			new_project_config = {
				"csv_file": new,
				"template_file": template_file,
				"editorRTL": editorRTL,
				"country": country,
			}
			save_project_config(project, new_project_config)

		return {
			"ok": True, 
			"old": old, 
			"new": new
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/dry-run", methods=["GET"])
def api_dry_run(project: str) -> Union[dict, Tuple[dict, int]]:

	try:
		cfg = get_project_config(project)
		csv_file = cfg.get("csv_file")
		country = cfg.get("country")
		rules = get_phone_rules(country)

		if not csv_file:
			return {
				"ok": False,
				"error": "No CSV file selected for this project"
			}, 400

		csv_dir = ensure_csv_folder(project)
		csv_path = csv_dir / csv_file

		if not csv_path.exists():
			return {
				"ok": False,
				"error": "CSV file not found"
			}, 404

		result = []

		with csv_path.open("r", encoding="utf-8-sig") as f:
			reader = csv.DictReader(f)

			for i, row in enumerate(reader, 1):

				status = "READY"
				error = ""

				if not is_send_allowed(row):
					status = "SKIPPED"
					error = "send flag"

				else:
					phones = split_phones(row.get("mob", ""))

					if not phones:
						status = "NO_PHONE"
						error = "no number"

					else:
						for phone in phones:
							phone = normalize_phone(phone, rules)
							valid = validate_mobile(phone, rules)
							if not valid:
								status = "INVALID"
								error = "invalid number"
								break


				result.append({
					"row": i,
					"status": status,
					"error": error
				})

		return {
			"ok": True,
			"rows": result
		}

	except Exception as e:
		return {
			"ok": False,
			"error": str(e)
		}, 500


# ======================================================================
# Endpoints: Template Files (TXT)
# ======================================================================

def ensure_template_folder(project: str) -> Path:
	project_path = get_project_path(project)
	tpl_path = project_path / "templates"
	tpl_path.mkdir(parents=True, exist_ok=True)
	return tpl_path


@app.route("/api/projects/<project>/templates", methods=["GET"])
def list_templates(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		tpl_path = ensure_template_folder(project)
		files = [p.name for p in tpl_path.glob("*.txt")]

		return {
			"ok": True, 
			"files": sorted(files)
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/templates/upload", methods=["POST"])
def upload_template(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		tpl_path = ensure_template_folder(project)

		if "file" not in request.files:
			return {
				"ok": False, 
				"error": "no file uploaded"
			}, 400

		f = request.files["file"]

		if not f.filename.lower().endswith(".txt"):
			return {
				"ok": False, 
				"error": "file must be .txt"
			}, 400

		save_path = tpl_path / f.filename
		f.save(str(save_path))

		return {
			"ok": True, 
			"saved": f.filename
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/templates/duplicate", methods=["POST"])
def duplicate_template(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		tpl_path = ensure_template_folder(project)

		data = request.json or {}
		original = data.get("original", "").strip()
		new_name = data.get("new_name", "").strip()
		
		if not original or not new_name:
			return {
				"ok": False, 
				"error": "original or new_name missing"
			}, 400
			
		old_path = tpl_path / original
		new_path = tpl_path / new_name
		
		if not old_path.exists():
			return {
				"ok": False, 
				"error": "original template not found"
			}, 404
			
		if new_path.exists():
			return {
				"ok": False, 
				"error": "target name already exists"
			}, 400
			
		# Copy the original file along with its contents to a new file
		shutil.copy2(old_path, new_path)
		
		return {
			"ok": True, 
			"original": original, 
			"new": new_name
		}
	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/templates/rename", methods=["POST"])
def rename_template(project: str) -> Union[dict, Tuple[dict, int]]:
	try:
		tpl_path = ensure_template_folder(project)

		cfg = get_project_config(project)
		csv_file = cfg.get("csv_file")
		template_file = cfg.get("template_file")
		editorRTL = cfg.get("editorRTL")
		country = cfg.get("country")

		data = request.json or {}
		old = data.get("old", "").strip()
		new = data.get("new", "").strip()

		if not old or not new:
			return {
				"ok": False, 
				"error": "old/new missing"
			}, 400

		old_path = tpl_path / old
		new_path = tpl_path / new

		if not old_path.exists():
			return {
				"ok": False, 
				"error": "old template not found"
			}, 404

		if new_path.exists():
			return {
				"ok": False, 
				"error": "target name exists"
			}, 400

		old_path.rename(new_path)
		
		if old == template_file :
			new_project_config = {
				"csv_file": csv_file,
				"template_file": new,
				"editorRTL": editorRTL,
				"country": country,
			}
			save_project_config(project, new_project_config)


		return {
			"ok": True, 
			"old": old, 
			"new": new
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/templates/<filename>", methods=["DELETE"])
def delete_template(project: str, filename: str) -> Union[dict, Tuple[dict, int]]:
	try:
		tpl_path = ensure_template_folder(project)
		target = tpl_path / filename

		if not target.exists():
			return {
				"ok": False, 
				"error": "template not found"
			}, 404

		target.unlink()

		return {
			"ok": True, 
			"deleted": filename
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/templates/<filename>", methods=["GET"])
def get_template(project: str, filename: str) -> Union[dict, Tuple[dict, int]]:
	try:
		tpl_path = ensure_template_folder(project)
		target = tpl_path / str(filename)

		if not target.exists():
			return {
				"text": "",
				"path": ""
			}
	
		text = target.read_text(encoding="utf-8-sig")

		return {
			"text": text
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


@app.route("/api/projects/<project>/templates/<filename>", methods=["POST"])
def save_template(project: str, filename: str) -> Union[dict, Tuple[dict, int]]:
	try:
		tpl_path = ensure_template_folder(project)
		target = tpl_path / str(filename)

		data = request.get_json(force=True)
		text = data.get("text", "")

		target.write_text(text, encoding="utf-8-sig")

		return {
			"status": "ok"
		}

	except Exception as e:
		return {
			"ok": False, 
			"error": str(e)
		}, 500


# ======================================================================
# Endpoint: General & Project Config
# ======================================================================

@app.route("/api/config", methods=["GET"])
def get_config() -> Union[dict, Tuple[dict, int]]:
	ctx = get_active_context()

	# If no project is selected, return only the main config
	if ctx["project_name"] is None:
		return {
			"ok": True,
			"project": None,
		}

	return {
		"ok": True,
		"project": {
			"general_config": ctx["general_config"],
			"project_config": ctx["project_config"],
		}
	}


@app.route("/api/config", methods=["POST"])
def save_config() -> Union[dict, Tuple[dict, int]]:

	data = request.json
	project = data.get("project_name")

	main_cfg = get_main_config()

	if not project:
		return {
			"error": "project required"
		}, 400

	save_main_config({
		"project_name": project,
		"delay_seconds": data.get("delay_seconds", main_cfg.get("delay_seconds")),
		"kdeconnect": data.get("kdeconnect", main_cfg.get("kdeconnect")),
		"dryrun": data.get("dryrun", main_cfg.get("dryrun")),
	})
	
	return {
		"status": "ok"
	}


@app.route("/api/project-settings", methods=["POST"])
def update_project_settings() -> Union[dict, Tuple[dict, int]]:

	data = request.json
	project = data.get("project_name")

	if not project:
		return {
			"error":"project required"
		},400

	cfg = get_project_config(project)

	project_path = get_project_path(project)
	csv_dir = project_path / "csv"
	template_dir = project_path / "templates"

	# Check new value of csv_file
	csv_file = data.get("csv_file") or cfg.get("csv_file")
	
	if not csv_file:
		csv_file = get_first_file(csv_dir, "csv")

	# Check new value of template_file
	template_file = data.get("template_file") or cfg.get("template_file")

	if not template_file:
		template_file = get_first_file(template_dir, "txt")
		
	# Check new value of editorRTL
	editorRTL = data.get("editorRTL", cfg.get("editorRTL"))

	if not editorRTL:
		editorRTL = False

	# Check new value of country
	country = data.get("country") or cfg.get("country")

	if not country:
		country = "IR"

	project_config = {
		"csv_file": csv_file,
		"template_file": template_file,
		"editorRTL": editorRTL,
		"country": country,
	}

	save_project_config(project, project_config)

	return {
		"ok": True,
		"config": project_config
	}


# ======================================================================
# Endpoint:
# ======================================================================

@app.route("/api/kdeconnect/devices", methods=["GET"])
def api_get_devices() -> dict:
	devices = get_devices()

	if not devices:
		return {
			"ok": False,
			"error": "❌ Failed to load devices."
		}
	return {
		"ok": True,
		"devices": devices
	}


@app.route("/api/send/start", methods=["POST"])
def send_start() -> Union[dict, Tuple[dict, int]]:

	data = request.get_json(force=True)

	project_name = data.get("project_name")
	device_name = data.get("device_name")

	if not project_name:
		return {
			"error": "project_name required"
		},400

	if not device_name:
		return {
			"error":"device_name required"
		},400

	cfg = get_project_config(project_name)

	csv_file = cfg.get("csv_file")

	if not csv_file:
		return {
			"error":"csv_file not configured"
		},400

	csv_path = ensure_csv_folder(project_name) / csv_file

	if not csv_path.exists():
		return {
			"error":"csv file not found"
		},404

	with csv_path.open("r", encoding="utf-8-sig") as f:
		reader = csv.DictReader(f)
		rows = list(reader)

	job_id = str(uuid.uuid4())

	SEND_JOBS[job_id] = {
		"status":"PENDING",
		"total":len(rows),
		"sent":0,
		"failed":0,
		"skipped":0,
		"results":[],
		"finished":False
	}

	t = Thread(
		target = run_send_job,
		args = (job_id, rows, device_name, project_name),
		daemon = True
	)

	t.start()

	return {
		"job_id":job_id,
		"total":len(rows)
	}


@app.route("/api/send/status/<job_id>")
def send_status(job_id) -> Union[dict, Tuple[dict, int]]:

	job = SEND_JOBS.get(job_id)

	if not job:
		return {
			"ok": False,
			"error": "job not found"
		}, 404

	return {
		"ok": True,
		"job": job
	}


if __name__ == "__main__":
	app.run(
		host="0.0.0.0",
		port=5000,
		debug=True
	)



# print(f"\t⭕️DEBUG | save_config >  project_name > {project}\n")
