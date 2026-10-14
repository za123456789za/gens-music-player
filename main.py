
#music player



#imports

import webbrowser
import secrets
import hashlib
import base64
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QSlider,
    QFrame
)
from PyQt6.QtGui import QFont, QFontDatabase, QPixmap, QIcon

import requests



#resource path

#returns the correct path for both development and PyInstaller builds
#when the application is packaged, resources are stored inside
#PyInstaller's temporary _MEIPASS directory

def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)



#spotify authentication

#tokens received from spotify after successful authentication

access_token = None
refresh_token = None

#spotify application credentials and local callback address

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
REDIRECT_URI = "http://127.0.0.1:8080"



#PKCE

#generates a random code verifier for OAuth 2.0 PKCE authentication

code_verifier = secrets.token_urlsafe(64)

#creates the SHA-256 based code challenge from the verifier

code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode("utf-8")).digest()
).decode("utf-8").rstrip("=")



#spotify auth url

#builds the spotify authorization URL with the required
#permissions for playback control and playback state

auth_url = (
    "https://accounts.spotify.com/authorize"
    "?client_id=" + CLIENT_ID +
    "&response_type=code"
    "&redirect_uri=" + REDIRECT_URI +
    "&code_challenge_method=S256"
    "&code_challenge=" + code_challenge +
    "&scope=user-read-playback-state%20user-modify-playback-state"
)



#callback server

#a temporary local HTTP server receives the authorization code
#after the user successfully logs in to spotify

class CallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        global access_token, refresh_token

        #reads the query parameters from the callback URL
        query = parse_qs(urlparse(self.path).query)

        if "code" in query:
            code = query["code"][0]

            print("authorization code received!")
            print(code)

            #exchanges the authorization code for spotify access tokens
            token_response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": code_verifier
                }
            )

            token_data = token_response.json()

            access_token = token_data["access_token"]
            refresh_token = token_data["refresh_token"]

            print("spotify connected!")

            #sends a simple success page to the browser
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            self.wfile.write(
                b"<h1>spotify login successful!</h1>"
            )

        else:
            #returns an error if spotify did not provide an authorization code
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        #disables the default HTTP server console messages.
        return



#starting callback server

#starts the local server and open the spotify login page in the browser

server = HTTPServer(("127.0.0.1", 8080), CallbackHandler)
webbrowser.open(auth_url)

#waits for Spotify to redirect the browser back to the local server
server.handle_request()

#closes the server after receiving the authorization code
server.server_close()



#spotify devices

#gets the spotify devices currently available for playback

response = requests.get(
    "https://api.spotify.com/v1/me/player/devices",
    headers={
        "Authorization": "Bearer " + access_token
    }
)

devices = response.json()["devices"]

#prints all available spotify devices
for device in devices:
    print(device["name"], device["type"], device["id"])

#finds the spotify desktop application
computer_device_id = None

for device in devices:
    if device["type"] == "Computer":
        computer_device_id = device["id"]
        break

print("computer device:", computer_device_id)



#spotify playback functions

#previous song

#skip to the previous track

def previous_song():
    response = requests.post(
        "https://api.spotify.com/v1/me/player/previous",
        headers={
            "Authorization": "Bearer " + access_token
        },
        params={
            "device_id": computer_device_id
        }
    )

    print("previous:", response.status_code)

#next song

#skips to the next track

def next_song():
    response = requests.post(
        "https://api.spotify.com/v1/me/player/next",
        headers={
            "Authorization": "Bearer " + access_token
        },
        params={
            "device_id": computer_device_id
        }
    )

    print("next:", response.status_code)

#play & pause

#checks the current playback state and either plays or pauses the track

def play_song():

    #gets the current spotify playback state
    response = requests.get(
        "https://api.spotify.com/v1/me/player",
        headers={
            "Authorization": "Bearer " + access_token
        }
    )

    playback_state = response.json()

    #if music is currently playing, pauses it
    if playback_state["is_playing"] == True:

        response = requests.put(
            "https://api.spotify.com/v1/me/player/pause",
            headers={
                "Authorization": "Bearer " + access_token
            },
            params={
                "device_id": computer_device_id
            }
        )

        if 200 <= response.status_code < 300:
            play_button.setText("▶")
            print("paused")

    #otherwise, starts playback
    else:

        response = requests.put(
            "https://api.spotify.com/v1/me/player/play",
            headers={
                "Authorization": "Bearer " + access_token
            },
            params={
                "device_id": computer_device_id
            }
        )

        if 200 <= response.status_code < 300:
            play_button.setText("||")
            print("playing")



#updating playback information

#runs periodically to keep the UI synchronized with spotify

def update_progress():

    #gets the current playback state
    response = requests.get(
        "https://api.spotify.com/v1/me/player",
        headers={
            "Authorization": "Bearer " + access_token
        }
    )

    if response.status_code == 200:

        playback_state = response.json()

        #continues only if a track is currently available
        if playback_state["item"] is not None:

            #gets the current playback position and track duration
            progress_ms = playback_state["progress_ms"]
            duration_ms = playback_state["item"]["duration_ms"]

            #converts playback progress into a percentage
            progress = (progress_ms / duration_ms) * 100
            progress_bar.setValue(int(progress))

            #gets the current song and artist information
            song_name = playback_state["item"]["name"]
            artist_name = playback_state["item"]["artists"][0]["name"]

            song_label.setText(song_name)
            artist_label.setText(artist_name)

            #gets the album artwork URL from spotify
            album_url = playback_state["item"]["album"]["images"][0]["url"]

            #downloads the album artwork
            image_response = requests.get(album_url)

            #converts the downloaded image into a QPixmap
            pixmap = QPixmap()
            pixmap.loadFromData(image_response.content)

            #displays the album artwork inside the album cover widget
            album_cover.setPixmap(
                pixmap.scaled(
                    album_cover.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

            #converts milliseconds into minutes and seconds
            current_seconds = progress_ms // 1000
            total_seconds = duration_ms // 1000

            current_minutes = current_seconds // 60
            current_seconds = current_seconds % 60

            total_minutes = total_seconds // 60
            total_seconds = total_seconds % 60

            #updates the current and total duration labels
            current_time_label.setText(
                f"{current_minutes}:{current_seconds:02}"
            )

            total_time_label.setText(
                f"{total_minutes}:{total_seconds:02}"
            )

            current_time_label.setStyleSheet(
                "color: rgb(0, 0, 0);"
            )

            total_time_label.setStyleSheet(
                "color: rgb(0, 0, 0);"
            )



#seek

#moves the playback position when the user releases the progress slider

def seek_song(value):

    #gets the current playback state
    response = requests.get(
        "https://api.spotify.com/v1/me/player",
        headers={
            "Authorization": "Bearer " + access_token
        }
    )

    if response.status_code == 200:

        playback_state = response.json()

        if playback_state["item"] is not None:

            #gets the total duration of the current track
            duration_ms = playback_state["item"]["duration_ms"]

            #converts the slider percentage into milliseconds
            position_ms = int((value / 100) * duration_ms)

            #sends the new playback position to spotify
            requests.put(
                "https://api.spotify.com/v1/me/player/seek",
                headers={
                    "Authorization": "Bearer " + access_token
                },
                params={
                    "position_ms": position_ms,
                    "device_id": computer_device_id
                }
            )



#application setup

app = QApplication(sys.argv)



#loading custom fond from assets

font_id = QFontDatabase.addApplicationFont(
    resource_path("rainyhearts/rainyhearts.ttf")
)

font_family = QFontDatabase.applicationFontFamilies(font_id)[0]

font = QFont(font_family, 12)

app.setFont(font)



#main window

window = QWidget()

window.setObjectName("mainWindow")
window.setWindowTitle("gen's music player <3")
window.resize(350, 625)

#create a frameless window so the application can use its own custom title bar

window.setWindowFlags(
    Qt.WindowType.FramelessWindowHint |
    Qt.WindowType.Window
)

window.setWindowIcon(
    QIcon(
        resource_path("assets/app_icon.png")
    )
)

window.setStyleSheet("""
QWidget#mainWindow {
    border: 2px solid black;
    background: transparent;
}
""")



#custom title bar

title_bar = QWidget(window)

title_bar.setGeometry(1, 1, 348, 29)

title_bar.setStyleSheet("""
QWidget {
    background-color: #95BBDB;
    border-bottom: 1px solid black;
}
""")



#application name

title_label = QLabel("gen's music player <3", title_bar)

title_label.setGeometry(10, 0, 200, 29)

title_label.setAlignment(
    Qt.AlignmentFlag.AlignVCenter
)

title_label.setFont(
    QFont(font_family, 10)
)

title_label.setStyleSheet("""
QLabel {
    color: white;
    background: transparent;
    border: none;
}
""")



#minimize button

minimize_button = QPushButton("—", title_bar)

minimize_button.setGeometry(288, 0, 30, 29)

minimize_button.setStyleSheet("""
QPushButton {
    border: none;
    background: transparent;
    color: white;
    font-size: 16px;
}

QPushButton:hover {
    background: rgba(255, 255, 255, 60);
    color: black;
}
""")

minimize_button.clicked.connect(window.showMinimized)



#left seperator

left_separator = QFrame(title_bar)

left_separator.setGeometry(287, 0, 1, 29)

left_separator.setStyleSheet("""
QFrame {
    background-color: black;
    border: none;
}
""")



#right seperator

button_separator = QFrame(title_bar)

button_separator.setGeometry(318, 0, 1, 29)

button_separator.setStyleSheet("""
QFrame {
    background-color: black;
    border: none;
}
""")



#close button

close_button = QPushButton("×", title_bar)

close_button.setGeometry(319, 0, 29, 29)

close_button.setStyleSheet("""
QPushButton {
    border: none;
    background: transparent;
    color: white;
    font-size: 18px;
}

QPushButton:hover {
    background: white;
    color: black;
}
""")

close_button.clicked.connect(window.close)



#window dragging

def mousePressEvent(event):

    if event.button() == Qt.MouseButton.LeftButton:
        window.drag_position = event.globalPosition().toPoint()


def mouseMoveEvent(event):

    if event.buttons() == Qt.MouseButton.LeftButton:

        new_position = event.globalPosition().toPoint()

        window.move(
            window.pos() +
            new_position -
            window.drag_position
        )

        window.drag_position = new_position

title_bar.mousePressEvent = mousePressEvent
title_bar.mouseMoveEvent = mouseMoveEvent



#background

background_label = QLabel(window)

background_label.setGeometry(1, 30, 348, 594)

background = QPixmap(
    resource_path("assets/background.jpg")
)

background_label.setPixmap(background)

background = background.scaled(
    background_label.size(),
    Qt.AspectRatioMode.IgnoreAspectRatio,
    Qt.TransformationMode.SmoothTransformation
)

background_label.lower()

background_label.setStyleSheet("""
QLabel {
    border: none;
}
""")



#tracking information

#song name

song_label = QLabel("song name", window)

song_label.setGeometry(0, 300, 350, 30)

song_label.setAlignment(
    Qt.AlignmentFlag.AlignCenter
)

song_label.setFont(
    QFont(font_family, 16)
)

song_label.setStyleSheet(
    "color: rgb(0, 0, 0);"
)


#artist name

artist_label = QLabel("artist", window)

artist_label.setGeometry(0, 325, 350, 30)

artist_label.setAlignment(
    Qt.AlignmentFlag.AlignCenter
)

artist_label.setStyleSheet(
    "color: rgb(0, 0, 0);"
)



#playback controls

#previous button

previous_button = QPushButton("|<<", window)

previous_button.move(100, 545)
previous_button.resize(40, 40)

previous_button.setStyleSheet(
    "color: rgb(0, 0, 0);"
)

previous_button.clicked.connect(previous_song)


#play & pause button

play_button = QPushButton("▶", window)

play_button.move(155, 545)
play_button.resize(40, 40)

play_button.setStyleSheet(
    "color: rgb(0, 0, 0);"
)

play_button.clicked.connect(play_song)


#next button

next_button = QPushButton(">>|", window)

next_button.move(210, 545)
next_button.resize(40, 40)

next_button.setStyleSheet(
    "color: rgb(0, 0, 0);"
)

next_button.clicked.connect(next_song)



#progress bar

progress_bar = QSlider(
    Qt.Orientation.Horizontal,
    window
)

progress_bar.setGeometry(40, 510, 270, 20)

progress_bar.setRange(0, 100)


#loading the custom handle
heart_path = resource_path(
    "assets/heart.png"
).replace("\\", "/")

print("HEART PATH:", heart_path)
print("HEART EXISTS:", os.path.exists(heart_path))


progress_bar.setStyleSheet(f"""
QSlider::groove:horizontal {{
    background: #dddddd;
    height: 4px;
}}

QSlider::sub-page:horizontal {{
    background: black;
    height: 4px;
}}

QSlider::add-page:horizontal {{
    background: #FFFFFF;
    height: 4px;
}}

QSlider::handle:horizontal {{
    image: url("{heart_path}");
    width: 29px;
    height: 16px;
    margin: -5px 0;
}}
""")



#playback time

current_time_label = QLabel("0:00", window)

current_time_label.setGeometry(40, 530, 45, 20)

current_time_label.setAlignment(
    Qt.AlignmentFlag.AlignLeft
)

current_time_label.setStyleSheet(
    "color: rgb(0,0,0);"
)


total_time_label = QLabel("0:00", window)

total_time_label.setGeometry(265, 530, 45, 20)

total_time_label.setAlignment(
    Qt.AlignmentFlag.AlignRight
)

total_time_label.setStyleSheet(
    "color: rgb(0,0,0);"
)


#seeks when the user releases the progress slider
progress_bar.sliderReleased.connect(
    lambda: seek_song(progress_bar.value())
)



#album cover

album_cover = QLabel(window)

album_cover.setGeometry(65, 60, 220, 220)

album_cover.setStyleSheet("""
QLabel {
    background-color: rgb(230, 230, 230);
    border: 1px solid black;
}
""")

album_cover.setAlignment(
    Qt.AlignmentFlag.AlignCenter
)



#updating timer

timer = QTimer()

timer.timeout.connect(update_progress)

timer.start(1000)



#starting the application

window.show()

sys.exit(app.exec())