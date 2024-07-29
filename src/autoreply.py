# -*- coding: utf-8 -*-

from autoreply_main_ui import *
from acc_settings_ui import *
from PyQt5.Qt import QApplication, QTimer, QSystemTrayIcon, QIcon, QMenu, QMessageBox, QMainWindow, QInputDialog
from pathlib import Path
import telethon
import sys, os, json, asyncio, time, traceback, threading, webbrowser, vk_api, vk_api.longpoll, pyperclip, random, pygsheets, requests, datetime


def init():
	global state
	state = {}
	state["app_title"] = "Autoreply"
	state["exiting"] = False
	state["events"] = []
	state["settings"] = {}
	state["workdir"] = Path(__file__).parent
	state["icon_path"] = state["workdir"] / "icon.png"
	state["data_path"] = state["workdir"].parent / "data"
	state["settings_path"] = state["data_path"] / "settings.json"
	state["lockfile_path"] = state["data_path"] / "parent.lock"
	state["logfile_path"] = state["data_path"] / "log.txt"
	state["tg_sessions_path"] = state["data_path"] / "tg_sessions"
	state["gsheets_cred_path"] = state["data_path"] / "google.json"
	
	os.chdir(state["workdir"])
	state["data_path"].mkdir(exist_ok=True)
	state["tg_sessions_path"].mkdir(exist_ok=True)
	
	app = QApplication(sys.argv)
	setup_main_window(app)
	state["app"] = app
	
	ensure_single_instance()
	state["lockfile"] = open(state["lockfile_path"], "w+")
	state["logfile"] = open(state["logfile_path"], "a", encoding="utf-8")
	
	read_settings_file()
	save_settings_file()
	
	serve_all_accs()
	start_gs_logger()
	start_admin_logger()
	upd_gui()
	
	upd_statuses()
	timer = QTimer()
	#timer.timeout.connect(lambda: None)
	timer.timeout.connect(upd_statuses)
	timer.start(500)
	sys.exit(app.exec_())

def upd_statuses():
	statuses_readable = {
		"error": "Error",
		"running": "Running",
		"running_disabled": "Running, disabled",
		"not_authorized": "Not authorized",
		"starting": "Starting",
		"connecting": "Connecting",
		"waiting": "Waiting"
	}
	
	try:
		for acc in state["settings"]["tg_accounts"]:
			if not "status" in acc["_runtime"]:
				continue
			
			status = acc["_runtime"]["status"]
			is_active = acc["active"]
			if status == "running" and not is_active:
				status = "running_disabled"
			
			if not status in statuses_readable:
				status_readable = status
			status_readable = statuses_readable[status]
			
			acc["_runtime"]["gui_item"].setText("{} ({})".format(acc["title"], status_readable))
			acc["_runtime"]["ui"].status_label.setText("Status: {}".format(status_readable))
		
		for acc in state["settings"]["vk_accounts"]: # must be the way no to repeat this code twice
			if not "status" in acc["_runtime"]:
				continue
			
			status = acc["_runtime"]["status"]
			is_active = acc["active"]
			if status == "running" and not is_active:
				status = "running_disabled"
			
			if not status in statuses_readable:
				status_readable = status
			status_readable = statuses_readable[status]
			
			acc["_runtime"]["gui_item"].setText("{} ({})".format(acc["title"], status_readable))
			acc["_runtime"]["ui"].status_label.setText("Status: {}".format(status_readable))
		
		gs_statuses_readable = {
			"success": "Last change at {time}",
			"error": "Sending error at {time}",
			"nocred": "File not found - {credpath}",
			"nofile": "Table not found"
		}
		gs_status_readable = gs_statuses_readable[state["gs_last_log_status"]]
		gs_status_readable = gs_status_readable.format(
			time = datetime.datetime.fromtimestamp(state["gs_last_log_time"]).strftime("%H:%M"),
			credpath = str(state["gsheets_cred_path"])
		)
		state["main_ui"].gs_log_status_label.setText("Status: {}".format(gs_status_readable))
		
		tglog_statuses_readable = {
			"success": "Last updated at {time}",
			"error": "Last updated at {time} (Error)",
			"empty": "Last updated at {time} (No new messages)",
			"notoken": "Bot token is missing"
		}
		tglog_status_readable = tglog_statuses_readable[state["tg_admin_last_log_status"]]
		tglog_status_readable = tglog_status_readable.format(
			time = datetime.datetime.fromtimestamp(state["tg_admin_last_log_time"]).strftime("%H:%M")
		)
		state["main_ui"].tg_admin_status_label.setText("Status: {}".format(tglog_status_readable))
	except Exception as exc:
		log("Failed to update statuses:\n{}".format(traceback.format_exc()))

def setup_main_window(app):
	window = AutoreplyWindow()
	ui = Ui_main_window()
	ui.setupUi(window)
	
	window_icon = QtGui.QIcon()
	window_icon.addPixmap(QtGui.QPixmap(str(state["icon_path"])), QtGui.QIcon.Normal, QtGui.QIcon.Off)
	window.setWindowIcon(window_icon)
	window.show()
	window.setFixedSize(window.size())
	window.setWindowTitle(state["app_title"])
	
	tray_icon = QSystemTrayIcon(QIcon(str(state["icon_path"])), parent = app)
	tray_icon.setToolTip(state["app_title"])
	tray_icon.activated.connect(on_tray_click)
	tray_menu = QMenu()
	exit_action = tray_menu.addAction("Exit")
	exit_action.triggered.connect(on_exit)
	tray_icon.setContextMenu(tray_menu)
	tray_icon.show()
	
	ui.save_button.clicked.connect(on_save_settings)
	ui.tg_add_acc_button.clicked.connect(on_add_tg_account)
	ui.vk_add_acc_button.clicked.connect(on_add_vk_account)
	ui.tg_accounts_list.itemDoubleClicked.connect(on_tg_item_click)
	ui.vk_accounts_list.itemDoubleClicked.connect(on_vk_item_click)
	ui.tg_proxy_type_menu.activated.connect(on_tg_proxy_type_change)
	ui.vk_proxy_type_menu.activated.connect(on_vk_proxy_type_change)
	
	state["main_window"] = window
	state["main_ui"] = ui

def on_tg_proxy_type_change():
	read_gui()
	upd_gui()

def on_vk_proxy_type_change():
	read_gui()
	upd_gui()

def on_tg_item_click(item):
	for acc in state["settings"]["tg_accounts"]:
		if acc["_runtime"]["gui_item"] == item:
			open_settings_tg(acc)

def on_vk_item_click(item):
	for acc in state["settings"]["vk_accounts"]:
		if acc["_runtime"]["gui_item"] == item:
			open_settings_vk(acc)

def open_settings_tg(acc):
	acc["_runtime"]["window"].show()
	acc["_runtime"]["window"].activateWindow()

def open_settings_vk(acc):
	acc["_runtime"]["window"].show()
	acc["_runtime"]["window"].activateWindow()

def on_add_tg_account():
	try:
		api_id   = state["settings"]["tg_api_id"]
		api_hash = state["settings"]["tg_api_hash"]
		acc = {}
		acc["_runtime"] = {}
		acc["active"] = True
		acc["index"] = str(int(time.time()))
		
		if not api_id or not api_hash:
			msgbox_alert("Please fill api_id and id_hash first")
			return
		
		acc["phone"] = msgbox_prompt("Enter a phone number:")
		acc["phone"] = acc["phone"].replace(" ", "")
		if not acc["phone"]: return
		
		proxy_args = gen_tg_client_proxy_args()
		session_path = str(state["tg_sessions_path"] / acc["index"])
		client = telethon.TelegramClient(session_path, api_id, api_hash, app_version = "1.0", **proxy_args)
		_sync = client.loop.run_until_complete
		_sync(client.connect())
		_sync(client.send_code_request(acc["phone"]))
		auth_code = msgbox_prompt("Enter the code you received:")
		if not auth_code: return
		
		while True:
			try:
				current_user = _sync(client.sign_in(acc["phone"], auth_code))
				break
			except telethon.errors.rpcerrorlist.SessionPasswordNeededError:
				password = msgbox_prompt("Enter the account password")
				current_user = _sync(client.sign_in(password = password))
				if not password: return
			except telethon.errors.rpcerrorlist.FloodWaitError as err:
				msgbox_alert("Too many attempts. Try again in {} seconds".format(err.seconds))
				return
			except telethon.errors.rpcerrorlist.PhoneNumberInvalidError as err:
				msgbox_alert("Wrong number")
				return
			except telethon.errors.rpcerrorlist.PhoneCodeInvalidError:
				auth_code = msgbox_prompt("Invalid code")
				if not auth_code: return
		client.disconnect()
		
		acc["title"] = (current_user.first_name or "") + " " + (current_user.last_name or "")
		state["settings"]["tg_accounts"].append(acc)
		save_settings_file()
		serve_all_accs()
		upd_gui()
		open_settings_tg(acc)
	except Exception:
		log("Failed to add TG account: \n{}".format(traceback.format_exc()))
		msgbox_alert("Error adding a new account. More info in log.txt")

def on_add_vk_account():
	try:
		app_id = state["settings"]["vk_app_id"]
		
		acc = {}
		acc["_runtime"] = {}
		acc["active"] = True
		acc["index"] = str(int(time.time()))
		
		if not app_id:
			msgbox_alert("App ID for VK is missing. Kate Mobile App ID will be used (2685278)")
			app_id = "2685278"
		
		auth_url = "https://oauth.vk.com/authorize?client_id={}&scope=69632&redirect_uri=https://oauth.vk.com/blank.html&display=page&response_type=token&revoke=1".format(app_id)
		
		should_open_auth_url = msgbox_confirm("Open URL {} ?".format(auth_url), icon = QMessageBox.Question)
		if should_open_auth_url:
			webbrowser.open(auth_url)
		else:
			should_copy_auth_url = msgbox_confirm("Copy URL {} ?".format(auth_url), icon = QMessageBox.Question)
			if should_copy_auth_url:
				pyperclip.copy(auth_url)
		
		acc["token"] = ""
		try:
			token_input = msgbox_prompt("Press \"Allow\" and copy the resulting URL here URL\nor just paste the resulting token: ")
			if not "#" in token_input:
				acc["token"] = token_input
			else:
				token_url_params = token_input.split("#")[1].split("&")
				for param in token_url_params:
					[key, value] = param.split("=")
					if key == "access_token":
						acc["token"] = value
		except Exception:
			log("Error while parsing VK token url: {}".format(traceback.format_exc()))
		
		if not acc["token"]:
			msgbox_alert("Failed to receive the token")
			log("acc[\"token\"] is empty")
			return
		
		api_session = vk_api.VkApi(token = acc["token"])
		api_session.http.proxies = gen_vk_proxies_dict()
		#profile_info = api_session.method("account.getProfileInfo")
		current_user = api_session.method("users.get")[0]
		acc["title"] = (current_user["first_name"] or "") + " " + (current_user["last_name"] or "")
		acc["user_id"] = current_user["id"]
		state["settings"]["vk_accounts"].append(acc)
		save_settings_file()
		serve_all_accs()
		upd_gui()
		open_settings_vk(acc)
	except Exception:
		log("Failed to add VK account: \n{}".format(traceback.format_exc()))
		msgbox_alert("Error adding a new account. More info in log.txt")

def gen_tg_client_proxy_args():
	type  = state["settings"]["tg_proxy_type"]
	addr  = state["settings"]["tg_proxy_addr"].strip()
	port  = state["settings"]["tg_proxy_port"].strip()
	user  = state["settings"]["tg_proxy_user"].strip()
	pass_ = state["settings"]["tg_proxy_pass"].strip()
	try:
		port = int(port)
	except ValueError:
		port = None
	result_args = {}
	
	def _add_socks_params(): # repeating operations in the single function
		result_args["proxy"] = {}
		result_args["proxy"]["addr"] = addr
		result_args["proxy"]["port"] = port
		result_args["proxy"]["username"] = user
		result_args["proxy"]["password"] = pass_
	
	if type == "SOCKS5":
		_add_socks_params()
		result_args["proxy"]["proxy_type"] = "socks5"
	elif type == "SOCKS4":
		_add_socks_params()
		result_args["proxy"]["proxy_type"] = "socks4"
	elif type == "HTTP":
		_add_socks_params()
		result_args["proxy"]["proxy_type"] = "http"
	elif type == "MTPROTO":
		result_args["connection"] = telethon.connection.ConnectionTcpMTProxyRandomizedIntermediate
		result_args["proxy"] = (addr, port, pass_ or "00000000000000000000000000000000")
	else:
		pass
	
	return result_args

def gen_vk_proxies_dict():
	type  = state["settings"]["vk_proxy_type"]
	addr  = state["settings"]["vk_proxy_addr"].strip()
	port  = state["settings"]["vk_proxy_port"].strip()
	user  = state["settings"]["vk_proxy_user"].strip()
	pass_ = state["settings"]["vk_proxy_pass"].strip()
	result_dict = {}
	
	if not type in ["HTTP", "SOCKS4", "SOCKS5"]:
		return result_dict
	
	if type == "SOCKS4":
		protocol_part = "socks4"
	elif type == "SOCKS5":
		protocol_part = "socks5"
	elif type == "HTTP":
		protocol_part = "http"
	else:
		protocol_part = ""
	
	cred_part = ""
	if user and pass_:
		cred_part = "{}:{}@".format(user, pass_)
	elif user and not pass_:
		cred_part = "{}@".format(user)
	
	port_part = ""
	if port:
		port_part = ":{}".format(port)
	
	proxy_url = "{}://{}{}{}".format(protocol_part, cred_part, addr, port_part)
	result_dict["http"]  = proxy_url
	result_dict["https"] = proxy_url
	
	return result_dict

def serve_all_accs():
	for acc in state["settings"]["tg_accounts"]:
		if not "client" in acc["_runtime"]:
			acc["_runtime"]["proxy_type"] = state["settings"]["tg_proxy_type"] # used to display info about current used proxy
			acc["_runtime"]["proxy_addr"] = state["settings"]["tg_proxy_addr"]
			acc["_runtime"]["proxy_port"] = state["settings"]["tg_proxy_port"]
			acc["_runtime"]["proxy_user"] = state["settings"]["tg_proxy_user"]
			acc["_runtime"]["proxy_pass"] = state["settings"]["tg_proxy_pass"]
			
			acc["_runtime"]["status"] = "starting"
			acc["_runtime"]["thread"] = threading.Thread(target = serve_tg_acc, args = (acc,), daemon = True)
			acc["_runtime"]["thread"].start()
	
	for acc in state["settings"]["vk_accounts"]:
		if not "api_session" in acc["_runtime"]:
			acc["_runtime"]["proxy_type"] = state["settings"]["vk_proxy_type"] # used to display info about current used proxy
			acc["_runtime"]["proxy_addr"] = state["settings"]["vk_proxy_addr"]
			acc["_runtime"]["proxy_port"] = state["settings"]["vk_proxy_port"]
			acc["_runtime"]["proxy_user"] = state["settings"]["vk_proxy_user"]
			acc["_runtime"]["proxy_pass"] = state["settings"]["vk_proxy_pass"]
			
			acc["_runtime"]["status"] = "starting"
			acc["_runtime"]["thread"] = threading.Thread(target = serve_vk_acc, args = (acc,), daemon = True)
			acc["_runtime"]["thread"].start()

def serve_tg_acc(acc):
	async def wait_signals():
		while True:
			await asyncio.sleep(0.2)
			if acc["_runtime"]["stop_signal"]:
				await client.disconnect()
				acc["_runtime"]["client"] = None
				return
			if acc["_runtime"]["logout_signal"]:
				await client.log_out()
				state["settings"]["tg_accounts"].remove(acc)
				return
	
	api_id   = state["settings"]["tg_api_id"]
	api_hash = state["settings"]["tg_api_hash"]
	acc["_runtime"]["stop_signal"] = False
	acc["_runtime"]["logout_signal"] = False
	
	log("Thread for TG account '{}' is started".format(acc["title"]))
	
	try:
		loop = asyncio.new_event_loop()
		asyncio.set_event_loop(loop)
		
		proxy_args = gen_tg_client_proxy_args()
		session_path = str(state["tg_sessions_path"] / acc["index"])
		client = telethon.TelegramClient(session_path, api_id, api_hash, app_version = "1.0", sequential_updates = True, **proxy_args)
		acc["_runtime"]["client"] = client
		
		@client.on(telethon.events.NewMessage(incoming = True))
		async def handle_new_message(event):
			try:
				if not acc["active"]:
					return
				if not event.is_private:
					return
				await client.get_dialogs() # without this telethon may raise error while event.client.get_entity
				sender = await event.client.get_entity(event.message.peer_id)
				if sender.bot:
					return
				if state["settings"]["tg_onlyfirst"]:
					if sender.id in acc["replied"]:
						return
					message_history = await client.get_messages(sender, 0)
					if message_history.total > 1:
						if not sender.id in acc["replied"]:
							acc["replied"].append(sender.id)
							# bot actually didn't replied but we don't want to get history every time new message arrives
						return
				
				time.sleep(1)
				await event.respond(
					state["settings"]["tg_reply_text"],
					file = state["settings"]["tg_reply_file"].strip() or None
				)
				
				if state["settings"]["tg_autodelete"]:
					await client.delete_dialog(sender)
				if not sender.id in acc["replied"]:
					acc["replied"].append(sender.id)
				
				log_evt = {}
				log_evt["platform"] = "tg"
				log_evt["time"] = int(time.time())
				log_evt["type"] = "autoreply"
				log_evt["repl_by"] = {}
				log_evt["repl_by"]["name"] = acc["title"]
				log_evt["repl_to"] = {}
				log_evt["repl_to"]["id"] = sender.id
				log_evt["repl_to"]["name"] = sender.first_name
				if sender.last_name:
					log_evt["repl_to"]["name"] += " " + sender.last_name
				log_evt["repl_to"]["username"] = sender.username
				log_evt["repl_to_msg"] = event.message.message
				log_evt["autodeleted"] = state["settings"]["tg_autodelete"]
				state["events"].append(log_evt) # currently list does not cleanup so it causes memory leak
			except Exception:
				log("Error while handling message for TG account {}: \n{}".format(acc["title"], traceback.format_exc()))
		
		signals_task = client.loop.create_task(wait_signals())
	except Exception:
		acc["_runtime"]["status"] = "error"
		log("Failed to initialize TG acc {}: {}".format(acc["title"], traceback.format_exc()))
		return
	
	while True:
		try:
			acc["_runtime"]["status"] = "connecting"
			client.loop.run_until_complete(client.connect())
			is_authorized = client.loop.run_until_complete(client.is_user_authorized())
			if not is_authorized:
				acc["_runtime"]["status"] = "not_authorized"
				break # thread will just wait for signals at this point
			client.start()
			acc["_runtime"]["status"] = "running"
			client.run_until_disconnected()
		except Exception:
			log(traceback.format_exc())
			acc["_runtime"]["status"] = "error"
			client.loop.run_until_complete(asyncio.sleep(5))
		if acc["_runtime"]["stop_signal"] or acc["_runtime"]["logout_signal"]:
			break
	
	try:
		client.loop.run_until_complete(signals_task) # wait for task to properly stop thread
	except Exception:
		log("Error in signals task for TG account {}: \n{}".format(acc["title"], traceback.format_exc()))
	log("Thread for TG account '{}' is stopped".format(acc["title"]))

def serve_vk_acc(acc):
	log("Thread for VK account '{}' is started".format(acc["title"]))
	
	try:
		proxies_dict = gen_vk_proxies_dict()
	except Exception:
		proxies_dict = {}
		log("Failed to create proxies_dict: {}".format(traceback.format_exc()))
	
	while True:
		try:
			app_id = state["settings"]["vk_app_id"]
			acc["_runtime"]["stop_signal"] = False
			
			acc["_runtime"]["status"] = "connecting"
			api_session = vk_api.VkApi(token = acc["token"])
			acc["_runtime"]["api_session"] = api_session
			
			api_session.http.proxies = proxies_dict
			longpoll = vk_api.longpoll.VkLongPoll(api_session)
			longpoll.session.proxies = proxies_dict
			acc["_runtime"]["status"] = "waiting" # longpoll.listen can crash and freeze in some conditions. We dont want to show account as running so setting "waiting" status: smth between "connecting" and "running"
			
			for event in longpoll.listen():
				try:
					acc["_runtime"]["status"] = "running"
					if acc["_runtime"]["stop_signal"]:
						log("detected stop_signal while VK longpoll iteration (acc: {}), breaking".format(acc["title"]))
						break
					if not acc["active"]:
						continue
					if not event.type == vk_api.longpoll.VkEventType.MESSAGE_NEW or \
					not event.to_me or not event.from_user:
						continue
					if event.user_id == acc["user_id"]: # prevent infinite loop in conversation with self
						continue
					if state["settings"]["vk_onlyfirst"]:
						if event.user_id in acc["replied"]:
							continue
						message_history = api_session.method("messages.getHistory", {"user_id": event.user_id})
						if message_history["count"] > 1:
							if not event.user_id in acc["replied"]:
								acc["replied"].append(event.user_id)
								# bot actually didn't replied but we don't want to get history every time new message arrives
							continue
					
					time.sleep(1)
					attachments_list = format_vk_attachments()
					api_session.method("messages.send", {"user_id": event.user_id, "random_id": random.randint(100, 30000), "message": state["settings"]["vk_reply_text"], "attachment": attachments_list})
					
					if state["settings"]["vk_autodelete"]:
						api_session.method("messages.deleteConversation", {"user_id": event.user_id})
					if not event.user_id in acc["replied"]:
						acc["replied"].append(event.user_id)
					
					sender = api_session.method("users.get", {"user_id": event.user_id})[0]
					log_evt = {}
					log_evt["platform"] = "vk"
					log_evt["time"] = int(time.time())
					log_evt["type"] = "autoreply"
					log_evt["repl_by"] = {}
					log_evt["repl_by"]["name"] = acc["title"]
					log_evt["repl_to"] = {}
					log_evt["repl_to"]["id"] = sender["id"]
					log_evt["repl_to"]["name"] = sender["first_name"] + " " + sender["last_name"]
					log_evt["repl_to_msg"] = event.message
					log_evt["autodeleted"] = state["settings"]["vk_autodelete"]
					state["events"].append(log_evt) # currently list does not cleanup so it causes memory leak
				except Exception:
					log("Error while handling message for VK account {}: \n{}".format(acc["title"], traceback.format_exc()))
		
		except Exception:
			log(traceback.format_exc())
			acc["_runtime"]["status"] = "error"
			time.sleep(5)
		if acc["_runtime"]["stop_signal"]:
			break
	
	log("Thread for VK account '{}' is stopped".format(acc["title"]))

def format_vk_attachments(): # using regex would be better solution
	att_list = state["settings"]["vk_reply_attachments"]
	att_list = att_list.replace("\r", ",")
	att_list = att_list.replace("\n", ",")
	att_list = att_list.replace(" ", ",")
	while ",," in att_list:
		att_list = att_list.replace(",,", ",")
	att_list = att_list.strip(",")
	return att_list

def start_gs_logger():
	state["gs_log_thread"] = threading.Thread(target = serve_gs_logger, daemon = True)
	state["gs_log_thread"].start()

def start_admin_logger():
	state["admin_log_thread"] = threading.Thread(target = serve_admin_logger, daemon = True)
	state["admin_log_thread"].start()

def serve_gs_logger():
	def access_sheet(file_name):
		try:
			gsheet_file = gapi_client.open(file_name)
			result_sheet = gsheet_file.sheet1
		except pygsheets.exceptions.SpreadsheetNotFound:
			result_sheet = None
		return result_sheet
	
	def add_tg_row(row):
		if not tg_table: return
		tg_table.append_table(row, start = "A2")
	def add_vk_row(row):
		if not vk_table: return
		vk_table.append_table(row, start = "A2")
	
	events = state["events"]
	ev_pointer = 0 # index of the last logged event in events list
	state["gs_last_log_time"] = int(time.time())
	state["gs_last_log_status"] = "success"
	
	while True:
		try:
			if not state["gsheets_cred_path"].exists():
				log("No GSheets service file found: {}".format(str(state["gsheets_cred_path"])))
				state["gs_last_log_status"] = "nocred"
				return
			gapi_client = pygsheets.authorize(service_file = str(state["gsheets_cred_path"]))
			
			tg_table = access_sheet("Autoreply TG")
			vk_table = access_sheet("Autoreply VK")
			
			if not tg_table or not vk_table:
				log("GS reporter: tg_table found: {}, vk_table found: {}".format(bool(tg_table), bool(vk_table)))
				state["gs_last_log_status"] = "nofile"
				return
			
			tg_table.update_value("A1", "From [Name]")
			tg_table.update_value("B1", "To [Name]")
			tg_table.update_value("C1", "To [ID]")
			tg_table.update_value("D1", "To [URL]")
			vk_table.update_value("A1", "From [Name]")
			vk_table.update_value("B1", "To [Name]")
			vk_table.update_value("C1", "To [ID]")
			vk_table.update_value("D1", "To [URL]")
			
			while True:
				if len(events) <= ev_pointer:
					time.sleep(2)
					continue
				
				state["gs_last_log_time"] = int(time.time())
				targ_ev = events[ev_pointer]
				if targ_ev["platform"] == "tg":
					un = targ_ev["repl_to"].get("username")
					row = (
						targ_ev["repl_by"]["name"],
						targ_ev["repl_to"]["name"],
						targ_ev["repl_to"]["id"],
						"https://t.me/{}".format(un) if un else "-"
					)
					add_tg_row(row)
				elif targ_ev["platform"] == "vk":
					row = (
						targ_ev["repl_by"]["name"],
						targ_ev["repl_to"]["name"],
						targ_ev["repl_to"]["id"],
						"https://vk.com/id{}".format(targ_ev["repl_to"]["id"])
					)
					add_vk_row(row)
				
				ev_pointer += 1
				state["gs_last_log_status"] = "success"
		except Exception:
			log("GSheets logger error: \n{}".format(traceback.format_exc()))
			state["gs_last_log_status"] = "error"
			time.sleep(10)

def serve_admin_logger():
	def call_tg_bot_api(method, params = {}, files = {}):
		response_raw = requests.post("https://api.telegram.org/bot{}/{}".format(bot_token, method), data=params, files = files).text
		response = json.loads(response_raw)
		if not "result" in response or \
		not response["ok"]:
			raise ValueError("Botapi result['ok'] == False:\n" + json.dumps(response, indent = "\t"))
		return response["result"]
	
	def gen_report_msgs():
		def _sanitize(text):
			text = text.replace("&", "&amp;")
			text = text.replace("<", "&lt;")
			text = text.replace(">", "&gt;")
			return text
		
		msg_text = ""
		for event in events[ev_pointer:]:
			acc_url = None
			if event["platform"] == "vk":
				acc_url = "https://vk.com/id{}".format(event["repl_to"]["id"])
			elif event["platform"] == "tg":
				if event["repl_to"].get("username"):
					acc_url = "https://t.me/{}".format(event["repl_to"]["username"])
			
			if msg_text:
				msg_text += "____________________________________\n"
			msg_text += "<b>[{plat}][{time}] {link_addin1}{name}{link_addin2}</b>\n<i>{user_msg}</i>\n<pre>(received and replied {botname}{autodel_addin})</pre>\n".format(
				plat = event["platform"].upper(),
				time = datetime.datetime.fromtimestamp(event["time"]).strftime("%H:%M"),
				name = _sanitize(event["repl_to"]["name"]),
				link_addin1 = "<a href=\"{}\">".format(acc_url) if acc_url else "",
				link_addin2 = "</a>" if acc_url else "",
				botname = _sanitize(event["repl_by"]["name"]),
				autodel_addin = ", chat was deleted" if event["autodeleted"] else "",
				user_msg = _sanitize(event["repl_to_msg"])
			)
		
		if msg_text:
			return [msg_text]
		else:
			return []
	
	state["tg_admin_last_log_time"] = int(time.time())
	state["tg_admin_last_log_status"] = "empty"
	events = state["events"]
	ev_pointer = 0 # index of the last logged event in events list
	exiting_report = False
	while True:
		try:
			time.sleep(1)
			log_interval = state["settings"]["log_interval"] * 60 # saved as minutes, processed as seconds. Getting every iteration since user can change this value in runtime
			bot_token = state["settings"]["tg_log_bot_token"].strip()
			if not bot_token:
				state["tg_admin_last_log_status"] = "notoken"
				state["tg_admin_last_log_time"] = int(time.time())
				ev_pointer = len(events)
				continue
			if state["tg_admin_last_log_time"] + log_interval > int(time.time()) and not state["exiting"]:
				continue
			if len(events) <= ev_pointer:
				state["tg_admin_last_log_time"] = int(time.time())
				continue
			
			if state["exiting"]:
				exiting_report = True
			
			next_ev_pointer = len(events) # remembering now because events list may change while sending current messages. Setting for first unexisting index
			msgs_to_report = gen_report_msgs()
			failed_messages = 0
			for target in get_tg_log_bot_targs(): # better to use term 'subscriber' instead of 'target'
				for msg in msgs_to_report:
					if not msg: continue
					try:
						call_tg_bot_api("sendMessage", {"chat_id": target, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True})
					except Exception:
						log("Unable to send report to {}:\n{}".format(target, traceback.format_exc()))
						failed_messages += 1
						# at this point it is better to ignore failure to give chance for other messages to be sent
					time.sleep(0.5)
			
			if not msgs_to_report:
				state["tg_admin_last_log_status"] = "empty"
			elif failed_messages:
				state["tg_admin_last_log_status"] = "error"
			else:
				state["tg_admin_last_log_status"] = "success"
			
			ev_pointer = next_ev_pointer # ignoring current failed report in case of exception
			state["tg_admin_last_log_time"] = int(time.time())
		except Exception:
			state["tg_admin_last_log_status"] = "error"
			ev_pointer = len(events) # ignoring current failed report in case of exception
			state["tg_admin_last_log_time"] = int(time.time())
			log("Admin logger bot error:\n{}".format(traceback.format_exc()))
			continue
		finally:
			if exiting_report:
				log("TG log messages sent on exit succesfully")
				break

def get_tg_log_bot_targs():
	targs_str = state["settings"]["tg_log_bot_targets"]
	targs_str = targs_str.replace("\r", ",")
	targs_str = targs_str.replace("\n", ",")
	targs_str = targs_str.replace(" ", ",")
	while ",," in targs_str:
		targs_str = targs_str.replace(",,", ",")
	targs_str = targs_str.strip(",")
	
	targs_list = targs_str.split(",")
	if len(targs_list) == 1 and not targs_list[0]:
		targs_list = []
	for i, targ in enumerate(targs_list):
		if not targ[0] in "-@0123456789": # -XXXXXXXX means channel id, othervise treat as username(usernames cannot start with integers as well). Also handle cases when user provide username in @username format
			targs_list[i] = "@" + targ
	return targs_list

def on_save_settings():
	read_gui()
	save_settings_file()
	upd_gui()

def read_gui():
	settings = state["settings"]
	ui = state["main_ui"]
	
	settings["tg_autodelete"]         = ui.tg_autodelete_cb.isChecked()
	settings["tg_onlyfirst"]          = ui.tg_onlyfirst_cb.isChecked()
	settings["tg_reply_text"]         = ui.tg_reply_textarea.toPlainText()
	settings["tg_reply_file"]         = ui.tg_file_input.text()
	settings["tg_proxy_type"]         = ui.tg_proxy_type_menu.currentText()
	settings["tg_proxy_addr"]         = ui.tg_proxy_addr_input.text()
	settings["tg_proxy_port"]         = ui.tg_proxy_port_input.text()
	settings["tg_proxy_user"]         = ui.tg_proxy_user_input.text()
	settings["tg_proxy_pass"]         = ui.tg_proxy_pass_input.text()
	settings["vk_autodelete"]         = ui.vk_autodelete_cb.isChecked()
	settings["vk_onlyfirst"]          = ui.vk_onlyfirst_cb.isChecked()
	settings["vk_reply_text"]         = ui.vk_reply_textarea.toPlainText()
	settings["vk_reply_attachments"]  = ui.vk_attachments_textarea.toPlainText()
	settings["vk_proxy_type"]         = ui.vk_proxy_type_menu.currentText()
	settings["vk_proxy_addr"]         = ui.vk_proxy_addr_input.text()
	settings["vk_proxy_port"]         = ui.vk_proxy_port_input.text()
	settings["vk_proxy_user"]         = ui.vk_proxy_user_input.text()
	settings["vk_proxy_pass"]         = ui.vk_proxy_pass_input.text()
	settings["tg_api_id"]             = ui.tg_api_id_input.text()
	settings["tg_api_hash"]           = ui.tg_api_hash_input.text()
	settings["vk_app_id"]             = ui.vk_app_id_input.text()
	settings["tg_log_bot_token"]      = ui.tg_log_bot_token_input.text()
	settings["tg_log_bot_targets"]    = ui.tg_log_bot_targets_textarea.toPlainText()
	settings["log_interval"]          = ui.log_interval_input.text()
	
	for acc in settings["tg_accounts"]:
		if "ui" in acc["_runtime"]:
			acc_ui = acc["_runtime"]["ui"]
			acc["active"] = acc_ui.is_active_cb.isChecked()
	
	for acc in settings["vk_accounts"]:
		if "ui" in acc["_runtime"]:
			acc_ui = acc["_runtime"]["ui"]
			acc["active"] = acc_ui.is_active_cb.isChecked()
	
	validate_settings()
	if settings["log_interval"] < 0:
		settings["log_interval"] = 0

def read_settings_file():
	settings = {}
	try:
		with open(state["settings_path"], "r", encoding="utf-8") as settings_file:
			settings = json.loads(settings_file.read())
	except (json.decoder.JSONDecodeError, OSError):
		log("Failed to read settings file, using default settings")
	
	state["settings"] = settings
	validate_settings()

def validate_settings():
	def _ensure(targ_dic, key, default, val_type = None):
		if not val_type:
			val_type = type(default)
		if not key in targ_dic:
			targ_dic[key] = default
		elif not type(targ_dic[key]) == val_type:
			try:
				targ_dic[key] = val_type(targ_dic[key])
			except (ValueError, TypeError):
				targ_dic[key] = default
	
	settings = state["settings"]
	_ensure(settings, "tg_autodelete", False, bool)
	_ensure(settings, "tg_onlyfirst", True, bool)
	_ensure(settings, "tg_reply_text", "", str)
	_ensure(settings, "tg_reply_file", "", str)
	_ensure(settings, "tg_proxy_type", "No proxy", str)
	_ensure(settings, "tg_proxy_addr", "", str)
	_ensure(settings, "tg_proxy_port", "", str)
	_ensure(settings, "tg_proxy_user", "", str)
	_ensure(settings, "tg_proxy_pass", "", str)
	_ensure(settings, "vk_autodelete", False, bool)
	_ensure(settings, "vk_onlyfirst", True, bool)
	_ensure(settings, "vk_reply_text", "", str)
	_ensure(settings, "vk_reply_attachments", "", str)
	_ensure(settings, "vk_proxy_type", "No proxy", str)
	_ensure(settings, "vk_proxy_addr", "", str)
	_ensure(settings, "vk_proxy_port", "", str)
	_ensure(settings, "vk_proxy_user", "", str)
	_ensure(settings, "vk_proxy_pass", "", str)
	_ensure(settings, "tg_api_id", "", str)
	_ensure(settings, "tg_api_hash", "", str)
	_ensure(settings, "vk_app_id", "2685278", str)
	_ensure(settings, "tg_log_bot_token", "", str)
	_ensure(settings, "tg_log_bot_targets", "", str)
	_ensure(settings, "log_interval", 30, int)
	
	_ensure(settings, "tg_accounts", [], list)
	_ensure(settings, "vk_accounts", [], list)
	
	for acc in settings["tg_accounts"]:
		_ensure(acc, "index", "default", str)
		_ensure(acc, "phone", "", str)
		_ensure(acc, "title", "<empty>", str)
		_ensure(acc, "active", True, bool)
		_ensure(acc, "replied", [], list)
		_ensure(acc, "_runtime", {}, dict)
	
	for acc in settings["vk_accounts"]:
		_ensure(acc, "index", "default", str)
		_ensure(acc, "title", "<empty>", str)
		_ensure(acc, "user_id", 0, int)
		_ensure(acc, "active", True, bool)
		_ensure(acc, "replied", [], list)
		_ensure(acc, "_runtime", {}, dict)

def save_settings_file():
	def _prepare(settings_dict): #deep copy settings filtering _* keys
		def _pass_dict(targ):
			targ = targ.copy()
			for k, v in targ.items():
				if k[0] == "_":
					targ[k] = None
					continue
				if type(v) == dict:
					targ[k] = _pass_dict(v)
				elif type(v) == list:
					targ[k] = _pass_list(v)
			return targ
		
		def _pass_list(targ):
			targ = targ.copy()
			for index, val in enumerate(targ):
				if type(val) == dict:
					targ[index] = _pass_dict(val)
				elif type(val) == list:
					targ[index] = _pass_list(val)
			return targ
		return _pass_dict(settings_dict)
	
	serialized = json.dumps(_prepare(state["settings"]), indent = "\t")
	try:
		with open(state["settings_path"], "w", encoding="utf-8") as settings_file:
			settings_file.write(serialized)
	except OSError:
		log("Failed to save seffings")
		return False
	return True

def upd_gui():
	tg_proxies = ["No proxy", "SOCKS5", "SOCKS4", "HTTP", "MTPROTO"]
	vk_proxies = ["No proxy", "SOCKS5", "SOCKS4", "HTTP"]
	
	settings = state["settings"]
	ui = state["main_ui"]
	
	ui.tg_autodelete_cb.setChecked(                  settings["tg_autodelete"])
	ui.tg_onlyfirst_cb.setChecked(                   settings["tg_onlyfirst"])
	ui.tg_reply_textarea.setPlainText(               settings["tg_reply_text"])
	ui.tg_file_input.setText(                        settings["tg_reply_file"])
	ui.tg_proxy_type_menu.setCurrentIndex(           tg_proxies.index(settings["tg_proxy_type"]))
	ui.tg_proxy_addr_input.setText(                  settings["tg_proxy_addr"])
	ui.tg_proxy_port_input.setText(                  settings["tg_proxy_port"])
	ui.tg_proxy_user_input.setText(                  settings["tg_proxy_user"])
	ui.tg_proxy_pass_input.setText(                  settings["tg_proxy_pass"])
	ui.vk_autodelete_cb.setChecked(                  settings["vk_autodelete"])
	ui.vk_onlyfirst_cb.setChecked(                   settings["vk_onlyfirst"])
	ui.vk_reply_textarea.setPlainText(               settings["vk_reply_text"])
	ui.vk_attachments_textarea.setPlainText(         settings["vk_reply_attachments"])
	ui.vk_proxy_type_menu.setCurrentIndex(           tg_proxies.index(settings["vk_proxy_type"]))
	ui.vk_proxy_addr_input.setText(                  settings["vk_proxy_addr"])
	ui.vk_proxy_port_input.setText(                  settings["vk_proxy_port"])
	ui.vk_proxy_user_input.setText(                  settings["vk_proxy_user"])
	ui.vk_proxy_pass_input.setText(                  settings["vk_proxy_pass"])
	ui.tg_api_id_input.setText(                      settings["tg_api_id"])
	ui.tg_api_hash_input.setText(                    settings["tg_api_hash"])
	ui.vk_app_id_input.setText(                      settings["vk_app_id"])
	ui.tg_log_bot_token_input.setText(               settings["tg_log_bot_token"])
	ui.tg_log_bot_targets_textarea.setPlainText(     settings["tg_log_bot_targets"])
	ui.log_interval_input.setText(               str(settings["log_interval"]))
	
	ui.tg_proxy_addr_input.show()
	ui.tg_proxy_addr_label.show()
	ui.tg_proxy_port_input.show()
	ui.tg_proxy_port_label.show()
	ui.tg_proxy_user_input.show()
	ui.tg_proxy_user_label.show()
	ui.tg_proxy_pass_input.show()
	ui.tg_proxy_pass_label.show()
	if ui.tg_proxy_type_menu.currentText() == "No proxy":
		ui.tg_proxy_addr_input.close()
		ui.tg_proxy_addr_label.close()
		ui.tg_proxy_port_input.close()
		ui.tg_proxy_port_label.close()
		ui.tg_proxy_user_input.close()
		ui.tg_proxy_user_label.close()
		ui.tg_proxy_pass_input.close()
		ui.tg_proxy_pass_label.close()
	elif ui.tg_proxy_type_menu.currentText() == "MTPROTO":
		ui.tg_proxy_user_input.close()
		ui.tg_proxy_user_label.close()
	
	ui.vk_proxy_addr_input.show()
	ui.vk_proxy_addr_label.show()
	ui.vk_proxy_port_input.show()
	ui.vk_proxy_port_label.show()
	ui.vk_proxy_user_input.show()
	ui.vk_proxy_user_label.show()
	ui.vk_proxy_pass_input.show()
	ui.vk_proxy_pass_label.show()
	if ui.vk_proxy_type_menu.currentText() == "No proxy":
		ui.vk_proxy_addr_input.close()
		ui.vk_proxy_addr_label.close()
		ui.vk_proxy_port_input.close()
		ui.vk_proxy_port_label.close()
		ui.vk_proxy_user_input.close()
		ui.vk_proxy_user_label.close()
		ui.vk_proxy_pass_input.close()
		ui.vk_proxy_pass_label.close()
	
	ui.tg_accounts_list.clear()
	for acc in state["settings"]["tg_accounts"]:
		list_item = QtWidgets.QListWidgetItem()
		list_item.setText(acc["title"])
		acc["_runtime"]["gui_item"] = list_item
		ui.tg_accounts_list.addItem(list_item)
		
		if not "window" in acc["_runtime"]:
			create_tg_acc_window(acc)
		acc["_runtime"]["ui"].is_active_cb.setChecked(acc["active"])
		
		if "proxy_type" in acc["_runtime"] and \
		acc["_runtime"]["proxy_type"] in ["SOCKS5", "SOCKS4", "HTTP", "MTPROTO"]:
			proxy_status = "Using {} proxy: {}:{}" \
			.format(acc["_runtime"]["proxy_type"], \
			acc["_runtime"]["proxy_addr"], \
			acc["_runtime"]["proxy_port"])
		else:
			proxy_status = "Proxy isn't used"
		acc["_runtime"]["ui"].proxy_info_label.setText(proxy_status)
	
	ui.vk_accounts_list.clear()
	for acc in state["settings"]["vk_accounts"]:
		list_item = QtWidgets.QListWidgetItem()
		list_item.setText(acc["title"])
		acc["_runtime"]["gui_item"] = list_item
		ui.vk_accounts_list.addItem(list_item)
		
		if not "window" in acc["_runtime"]:
			create_vk_acc_window(acc)
		acc["_runtime"]["ui"].is_active_cb.setChecked(acc["active"])
		
		if "proxy_type" in acc["_runtime"] and \
		acc["_runtime"]["proxy_type"] in ["SOCKS5", "SOCKS4", "HTTP"]:
			proxy_status = "Using {} proxy: {}:{}" \
			.format(acc["_runtime"]["proxy_type"], \
			acc["_runtime"]["proxy_addr"], \
			acc["_runtime"]["proxy_port"])
		else:
			proxy_status = "Proxy isn't used"
		acc["_runtime"]["ui"].proxy_info_label.setText(proxy_status)
	
	upd_statuses()

def create_tg_acc_window(acc):
	def on_gui_upd():
		read_gui()
		save_settings_file()
	
	acc_window = AccSettingsWindow()
	acc_ui = Ui_account_settings()
	acc_ui.setupUi(acc_window)
	acc_window.setWindowTitle("[TG] {}".format(acc["title"]))
	acc_window.setFixedSize(acc_window.size())
	window_icon = QtGui.QIcon()
	window_icon.addPixmap(QtGui.QPixmap(str(state["icon_path"])), QtGui.QIcon.Normal, QtGui.QIcon.Off)
	acc_window.setWindowIcon(window_icon)
	
	acc["_runtime"]["window"] = acc_window
	acc["_runtime"]["ui"] = acc_ui
	
	def _logout():
		try:
			msg_text = "Are you sure you want to disconnect {} from Autoreply?".format(acc["title"])
			if not msgbox_confirm(msg_text): return
			
			acc["_runtime"]["window"].hide()
			thread = acc["_runtime"]["thread"]
			acc["_runtime"]["logout_signal"] = True
			thread.join()
			save_settings_file()
			upd_gui()
		except Exception:
			msgbox_alert("An error occured while trying to disconnect account")
			log(traceback.format_exc())
	
	acc_ui.is_active_cb.stateChanged.connect(on_gui_upd)
	acc_ui.logout_button.clicked.connect(_logout)

def create_vk_acc_window(acc):
	def on_gui_upd():
		read_gui()
		save_settings_file()
	
	acc_window = AccSettingsWindow()
	acc_ui = Ui_account_settings()
	acc_ui.setupUi(acc_window)
	acc_window.setWindowTitle("[VK] {}".format(acc["title"]))
	acc_window.setFixedSize(acc_window.size())
	window_icon = QtGui.QIcon()
	window_icon.addPixmap(QtGui.QPixmap(str(state["icon_path"])), QtGui.QIcon.Normal, QtGui.QIcon.Off)
	acc_window.setWindowIcon(window_icon)
	
	acc["_runtime"]["window"] = acc_window
	acc["_runtime"]["ui"] = acc_ui
	
	def _logout():
		try:
			msg_text = "Are you sure you want to disconnect {} from Autoreply?".format(acc["title"])
			if not msgbox_confirm(msg_text): return
			
			acc["_runtime"]["window"].hide()
			acc["_runtime"]["stop_signal"] = True
			state["settings"]["vk_accounts"].remove(acc)
			save_settings_file()
			upd_gui()
		except Exception:
			msgbox_alert("An error occured while trying to disconnect account")
			log(traceback.format_exc())
	
	acc_ui.is_active_cb.stateChanged.connect(on_gui_upd)
	acc_ui.logout_button.clicked.connect(_logout)

def on_tray_click(signal):
	if signal != 3:
		return
	window = state["main_window"]
	if window.isVisible():
		window.hide()
	else:
		window.show()
		window.activateWindow()

def on_exit():
	state["exiting"] = True
	read_gui()
	save_settings_file()
	state["main_window"].hide()
	state["app"].quit()
	
	for tg_acc in state["settings"]["tg_accounts"]:
		if tg_acc["_runtime"]["window"]:
			tg_acc["_runtime"]["window"].hide()
		tg_acc["_runtime"]["stop_signal"] = True
		#tg_acc["_runtime"]["thread"].join()
	
	for vk_acc in state["settings"]["vk_accounts"]:
		if vk_acc["_runtime"]["window"]:
			vk_acc["_runtime"]["window"].hide()
	# VK daemon threads will be automatically killed when main thread will exit
	# forcibly killing VK threads seem not to cause any problems
	
	time.sleep(4) # let the serving threads to properly stop and admin_log_thread to send report
	log("Exiting")
	state["logfile"].close()
	state["lockfile"].close()

def msgbox_alert(text):
	msgbox = QMessageBox()
	msgbox.setIcon(QMessageBox.Information)
	msgbox_icon = QtGui.QIcon()
	msgbox_icon.addPixmap(QtGui.QPixmap(str(state["icon_path"])), QtGui.QIcon.Normal, QtGui.QIcon.Off)
	msgbox.setWindowIcon(msgbox_icon)
	msgbox.setText(text)
	msgbox.setWindowTitle(state["app_title"])
	msgbox.exec_()

def msgbox_prompt(prompt_text = ""):
	result_text, ok = QInputDialog.getText(state["main_window"], state["app_title"], prompt_text)
	if not ok: result_text = ""
	return result_text

def msgbox_confirm(text, icon = QMessageBox.Information):
	msgbox = QMessageBox()
	msgbox.setIcon(icon)
	msgbox_icon = QtGui.QIcon()
	msgbox_icon.addPixmap(QtGui.QPixmap(str(state["icon_path"])), QtGui.QIcon.Normal, QtGui.QIcon.Off)
	msgbox.setWindowIcon(msgbox_icon)
	msgbox.setText(text)
	msgbox.setWindowTitle(state["app_title"])
	msgbox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
	button_code = msgbox.exec_()
	
	result = False
	if button_code == 1024:
		result = True
	return result

def ensure_single_instance():
	try:
		os.remove(state["lockfile_path"])
	except PermissionError:
		state["main_window"].hide()
		msgbox_alert("Autoreply is already running")
		sys.exit()
	except OSError:
		pass

def log(text):
	log_entry = "{}: {}".format(time.asctime(), text)
	log_entry = log_entry.replace("\n", "\n\t")
	print(log_entry)
	try:
		state["logfile"].write(log_entry + "\n")
	except OSError:
		print("Failed to write to logfile: \n{}".format(traceback.format_exc()))

class AutoreplyWindow(QMainWindow):
	def closeEvent(self, event):
		self.hide()
		event.ignore()

class AccSettingsWindow(QMainWindow):
	def closeEvent(self, event):
		self.hide()
		event.ignore()

if __name__ == "__main__":
	init()
